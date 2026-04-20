import math
import random

from cache_sim.belady import simulate_opt
from cache_sim.trace import trace_entries_to_ptes


def _normalize_trace(trace_or_entries):
    if not trace_or_entries:
        return []
    first = trace_or_entries[0]
    if isinstance(first, tuple) and len(first) >= 1:
        return trace_entries_to_ptes(trace_or_entries)
    return list(trace_or_entries)


def precompute_next_use(trace_or_entries):
    trace = _normalize_trace(trace_or_entries)
    next_use = [float('inf')] * len(trace)
    last_seen = {}

    for idx in range(len(trace) - 1, -1, -1):
        addr = trace[idx]
        if addr in last_seen:
            next_use[idx] = last_seen[addr] - idx
        last_seen[addr] = idx

    return next_use


def precompute_lifetimes(trace_or_entries, next_use=None):
    trace = _normalize_trace(trace_or_entries)
    if next_use is None:
        next_use = precompute_next_use(trace)
    if len(next_use) != len(trace):
        raise ValueError('next_use length must match trace length')
    return list(next_use)


def compute_percentile_thresholds(values, num_states):
    if num_states <= 0:
        raise ValueError('num_states must be positive')
    if num_states == 1:
        return []

    finite_vals = sorted(v for v in values if not math.isinf(v))
    if not finite_vals:
        return [float('inf')] * (num_states - 1)

    thresholds = []
    for bucket_idx in range(1, num_states):
        percentile = bucket_idx / num_states
        value_idx = min(len(finite_vals) - 1, int(percentile * len(finite_vals)))
        thresholds.append(finite_vals[value_idx])
    return thresholds


def map_to_state(value, thresholds):
    if math.isinf(value):
        return len(thresholds)

    for state, threshold in enumerate(thresholds):
        if value <= threshold:
            return state
    return len(thresholds)


def precompute_srrip_survival(num_sets, num_ways, max_rrpv):
    cache_lines = max(1, num_sets * num_ways)
    base_survival = max(1, cache_lines // 4)
    survival = [0] * (max_rrpv + 1)

    for rrpv in range(max_rrpv, -1, -1):
        survival[rrpv] = base_survival * (2 ** (max_rrpv - rrpv))

    return survival


def find_insertion_state_for_lifetime(lifetime, survival):
    if math.isinf(lifetime):
        return len(survival) - 1

    for state in range(len(survival) - 1, -1, -1):
        if survival[state] >= lifetime:
            return state
    return 0


def optimal_state_from_future_reuse(next_use_distance, thresholds):
    return map_to_state(next_use_distance, thresholds)


def normalize_ipv_counts(ipv_counts):
    total = sum(ipv_counts)
    if total <= 0:
        cold_state = len(ipv_counts) - 1
        probs = [0.0] * len(ipv_counts)
        probs[cold_state] = 1.0
        return probs
    return [count / total for count in ipv_counts]


def average_hit_deltas(delta_sums, delta_counts):
    deltas = [0.0] * len(delta_sums)
    for state in range(len(delta_sums)):
        if delta_counts[state] > 0:
            deltas[state] = delta_sums[state] / delta_counts[state]
    return deltas


def sample_ipv(ipv_probs, rng):
    draw = rng.random()
    cumulative = 0.0
    for state, prob in enumerate(ipv_probs):
        cumulative += prob
        if draw <= cumulative:
            return state
    return len(ipv_probs) - 1


def argmax_ipv(ipv_probs):
    return max(range(len(ipv_probs)), key=lambda state: (ipv_probs[state], state))


def _choose_victim(cache, max_rrpv):
    while True:
        for cand, rrpv in cache.items():
            if rrpv >= max_rrpv:
                return cand
        for cand in list(cache.keys()):
            cache[cand] = min(max_rrpv, cache[cand] + 1)


def _clamp_rrpv(value, max_rrpv):
    return max(0, min(max_rrpv, int(round(value))))


def train_opt_distilled_srrip(num_sets, num_ways, trace_or_entries, max_rrpv=3, survival=None):
    trace = _normalize_trace(trace_or_entries)
    if not trace:
        raise ValueError('trace must not be empty')

    next_use = precompute_next_use(trace)
    lifetimes = precompute_lifetimes(trace, next_use)
    thresholds = compute_percentile_thresholds(lifetimes, max_rrpv + 1)
    survival = list(survival) if survival is not None else precompute_srrip_survival(num_sets, num_ways, max_rrpv)
    if len(survival) != max_rrpv + 1:
        raise ValueError('survival must have length max_rrpv + 1')

    ipv_counts = [0] * (max_rrpv + 1)
    delta_sums = [0.0] * (max_rrpv + 1)
    delta_counts = [0] * (max_rrpv + 1)

    shadow_sets = [dict() for _ in range(num_sets)]
    shadow_misses = 0

    for idx, addr in enumerate(trace):
        set_id = hash(addr) % num_sets
        cache = shadow_sets[set_id]

        if addr in cache:
            old_state = _clamp_rrpv(cache[addr], max_rrpv)
            target_state = optimal_state_from_future_reuse(next_use[idx], thresholds)
            delta_sums[old_state] += old_state - target_state
            delta_counts[old_state] += 1
            cache[addr] = target_state
            continue

        shadow_misses += 1
        if len(cache) >= num_ways:
            victim = _choose_victim(cache, max_rrpv)
            del cache[victim]

        insert_state = find_insertion_state_for_lifetime(lifetimes[idx], survival)
        ipv_counts[insert_state] += 1
        cache[addr] = insert_state

    ipv_probs = normalize_ipv_counts(ipv_counts)
    hit_deltas = average_hit_deltas(delta_sums, delta_counts)
    belady_rate = simulate_opt(num_sets, num_ways, trace)

    return {
        'ipv_probs': ipv_probs,
        'hit_deltas': hit_deltas,
        'thresholds': thresholds,
        'survival': survival,
        'ipv_counts': ipv_counts,
        'delta_counts': delta_counts,
        'avg_shadow_srrip_rate': shadow_misses / len(trace),
        'avg_belady_rate': belady_rate,
        'max_rrpv': max_rrpv,
    }


def simulate_opt_distilled_srrip(
    num_sets,
    num_ways,
    trace_or_entries,
    policy,
    *,
    max_rrpv=None,
    insert_policy='sample',
    seed=1,
):
    trace = _normalize_trace(trace_or_entries)
    if not trace:
        raise ValueError('trace must not be empty')

    ipv_probs = policy['ipv_probs']
    hit_deltas = policy['hit_deltas']
    if max_rrpv is None:
        max_rrpv = policy.get('max_rrpv', len(ipv_probs) - 1)
    if len(ipv_probs) != max_rrpv + 1 or len(hit_deltas) != max_rrpv + 1:
        raise ValueError('policy dimensions do not match max_rrpv')

    if insert_policy not in ('sample', 'argmax'):
        raise ValueError("insert_policy must be one of {'sample', 'argmax'}")

    rng = random.Random(seed)
    sets = [dict() for _ in range(num_sets)]
    misses = 0

    for addr in trace:
        set_id = hash(addr) % num_sets
        cache = sets[set_id]

        if addr in cache:
            old_rrpv = _clamp_rrpv(cache[addr], max_rrpv)
            reduction = hit_deltas[old_rrpv]
            cache[addr] = _clamp_rrpv(old_rrpv - reduction, max_rrpv)
            continue

        misses += 1
        if len(cache) >= num_ways:
            victim = _choose_victim(cache, max_rrpv)
            del cache[victim]

        if insert_policy == 'sample':
            insert_rrpv = sample_ipv(ipv_probs, rng)
        else:
            insert_rrpv = argmax_ipv(ipv_probs)
        cache[addr] = _clamp_rrpv(insert_rrpv, max_rrpv)

    return misses / len(trace)


def train_and_eval_opt_distilled_srrip(
    num_sets,
    num_ways,
    train_trace_or_entries,
    eval_trace_or_entries=None,
    *,
    max_rrpv=3,
    survival=None,
    insert_policy='sample',
    seed=1,
):
    policy = train_opt_distilled_srrip(
        num_sets,
        num_ways,
        train_trace_or_entries,
        max_rrpv=max_rrpv,
        survival=survival,
    )
    eval_trace = train_trace_or_entries if eval_trace_or_entries is None else eval_trace_or_entries
    policy['eval_rate'] = simulate_opt_distilled_srrip(
        num_sets,
        num_ways,
        eval_trace,
        policy,
        max_rrpv=max_rrpv,
        insert_policy=insert_policy,
        seed=seed,
    )
    return policy


def _csv_encode(values):
    return ','.join(str(v) for v in values)


def _csv_decode_floats(raw):
    if raw is None or raw.strip() == '':
        return []
    return [float(x.strip()) for x in raw.split(',') if x.strip()]


def _csv_decode_ints(raw):
    if raw is None or raw.strip() == '':
        return []
    return [int(x.strip()) for x in raw.split(',') if x.strip()]


def save_opt_distilled_srrip(path, policy):
    with open(path, 'w') as f:
        f.write('# OPT-distilled SRRIP policy\n')
        f.write(f"max_rrpv={int(policy.get('max_rrpv', len(policy['ipv_probs']) - 1))}\n")
        f.write(f"ipv_probs={_csv_encode(policy['ipv_probs'])}\n")
        f.write(f"hit_deltas={_csv_encode(policy['hit_deltas'])}\n")
        f.write(f"thresholds={_csv_encode(policy.get('thresholds', []))}\n")
        f.write(f"survival={_csv_encode(policy.get('survival', []))}\n")
        f.write(f"ipv_counts={_csv_encode(policy.get('ipv_counts', []))}\n")
        f.write(f"delta_counts={_csv_encode(policy.get('delta_counts', []))}\n")
        if 'avg_shadow_srrip_rate' in policy:
            f.write(f"avg_shadow_srrip_rate={policy['avg_shadow_srrip_rate']}\n")
        if 'avg_belady_rate' in policy:
            f.write(f"avg_belady_rate={policy['avg_belady_rate']}\n")
        if 'eval_rate' in policy:
            f.write(f"eval_rate={policy['eval_rate']}\n")

    print(f"OPT-distilled SRRIP policy saved to {path}")


def load_opt_distilled_srrip(path):
    data = {}
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip()

    if 'ipv_probs' not in data or 'hit_deltas' not in data:
        raise ValueError(f"Invalid policy file '{path}': missing ipv_probs or hit_deltas")

    policy = {
        'max_rrpv': int(data.get('max_rrpv', len(_csv_decode_floats(data['ipv_probs'])) - 1)),
        'ipv_probs': _csv_decode_floats(data['ipv_probs']),
        'hit_deltas': _csv_decode_floats(data['hit_deltas']),
        'thresholds': _csv_decode_floats(data.get('thresholds', '')),
        'survival': _csv_decode_ints(data.get('survival', '')),
        'ipv_counts': _csv_decode_ints(data.get('ipv_counts', '')),
        'delta_counts': _csv_decode_ints(data.get('delta_counts', '')),
    }

    for optional_key in ('avg_shadow_srrip_rate', 'avg_belady_rate', 'eval_rate'):
        if optional_key in data:
            policy[optional_key] = float(data[optional_key])

    expected_len = policy['max_rrpv'] + 1
    if len(policy['ipv_probs']) != expected_len or len(policy['hit_deltas']) != expected_len:
        raise ValueError(
            f"Invalid policy file '{path}': max_rrpv={policy['max_rrpv']} but "
            f"len(ipv_probs)={len(policy['ipv_probs'])}, len(hit_deltas)={len(policy['hit_deltas'])}"
        )

    print(f"OPT-distilled SRRIP policy loaded from {path}")
    return policy