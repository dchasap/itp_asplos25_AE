import random
from collections import defaultdict

from cache_sim.constants import CTX_DATA, CTX_INST
from cache_sim.belady import simulate_opt
from cache_sim.trace import trace_entries_to_ptes
from cache_sim.utils import safe_mean


def default_ipv_vector(max_rrpv):
    one = min(1, max_rrpv)
    return (0, one, one, 0, max_rrpv)


def clamp_ipv_vector(vec, max_rrpv):
    return tuple(max(0, min(max_rrpv, int(v))) for v in vec)


def context_from_is_instr(is_instr):
    return CTX_INST if is_instr else CTX_DATA


def resolve_ipv_for_context(ipv_spec, is_instr, max_rrpv):
    """Return an IPV vector for this access context."""
    if isinstance(ipv_spec, dict):
        vec = ipv_spec.get(context_from_is_instr(is_instr))
        if vec is None:
            vec = ipv_spec.get(CTX_DATA, default_ipv_vector(max_rrpv))
    else:
        vec = ipv_spec
    return clamp_ipv_vector(vec, max_rrpv)


def _normalize_probability_row(row, fallback_idx):
    cleaned = [max(0.0, float(v)) for v in row]
    total = sum(cleaned)
    if total <= 0.0:
        out = [0.0] * len(cleaned)
        out[fallback_idx] = 1.0
        return out
    return [v / total for v in cleaned]


def _sample_from_probabilities(probs, rng):
    draw = rng.random()
    cumulative = 0.0
    for idx, prob in enumerate(probs):
        cumulative += prob
        if draw <= cumulative:
            return idx
    return len(probs) - 1


def resolve_ipv_distribution_for_context(ipv_dist_spec, is_instr, max_rrpv):
    """Return normalized probabilistic IPV policy for this access context."""
    if isinstance(ipv_dist_spec, dict) and (
        'insert_probs' in ipv_dist_spec or 'hit_transition_probs' in ipv_dist_spec
    ):
        spec = ipv_dist_spec
    elif isinstance(ipv_dist_spec, dict):
        spec = ipv_dist_spec.get(context_from_is_instr(is_instr))
        if spec is None:
            spec = ipv_dist_spec.get(CTX_DATA)
    else:
        spec = ipv_dist_spec

    if spec is None:
        # SRRIP-like fallback.
        insert_fallback = max(0, max_rrpv - 1)
        hit_rows = []
        for old_state in range(max_rrpv + 1):
            fallback_target = max(0, old_state - 1)
            row = [0.0] * (max_rrpv + 1)
            row[fallback_target] = 1.0
            hit_rows.append(row)
        insert_probs = [0.0] * (max_rrpv + 1)
        insert_probs[insert_fallback] = 1.0
        return {
            'hit_transition_probs': hit_rows,
            'insert_probs': insert_probs,
        }

    raw_insert = spec.get('insert_probs', [0.0] * (max_rrpv + 1))
    if len(raw_insert) != (max_rrpv + 1):
        raise ValueError('insert_probs length mismatch for probabilistic PACIPV policy')
    insert_fallback = max(0, max_rrpv - 1)
    insert_probs = _normalize_probability_row(raw_insert, fallback_idx=insert_fallback)

    raw_hit = spec.get('hit_transition_probs', [])
    if len(raw_hit) != (max_rrpv + 1):
        raise ValueError('hit_transition_probs row count mismatch for probabilistic PACIPV policy')

    hit_rows = []
    for old_state in range(max_rrpv + 1):
        row = raw_hit[old_state]
        if len(row) != (max_rrpv + 1):
            raise ValueError('hit_transition_probs column count mismatch for probabilistic PACIPV policy')
        fallback_target = max(0, old_state - 1)
        hit_rows.append(_normalize_probability_row(row, fallback_idx=fallback_target))

    return {
        'hit_transition_probs': hit_rows,
        'insert_probs': insert_probs,
    }


def map_reuse_to_rrpv(reuse_distance, max_rrpv, t1, t2):
    if reuse_distance == float('inf'):
        return max_rrpv
    if reuse_distance <= t1:
        return 0
    if reuse_distance <= t2:
        return max_rrpv - 1
    return max_rrpv


def build_context_rrpv_counts(trace_entries, max_rrpv, t1, t2):
    """Build Belady-guided RRPV histograms for INST/DATA contexts."""
    positions = defaultdict(list)
    for idx, (pte, _) in enumerate(trace_entries):
        positions[pte].append(idx)

    counts = {
        CTX_INST: [0] * (max_rrpv + 1),
        CTX_DATA: [0] * (max_rrpv + 1),
    }

    for i, (addr, is_instr) in enumerate(trace_entries):
        positions[addr].pop(0)
        if positions[addr]:
            next_use = positions[addr][0]
            reuse_distance = next_use - i
        else:
            reuse_distance = float('inf')

        ctx = context_from_is_instr(is_instr)
        rrpv = map_reuse_to_rrpv(reuse_distance, max_rrpv, t1, t2)
        counts[ctx][rrpv] += 1

    return counts


def normalize_context_rrpv_counts(counts, max_rrpv):
    probs = {
        CTX_INST: [0.0] * (max_rrpv + 1),
        CTX_DATA: [0.0] * (max_rrpv + 1),
    }
    for ctx in (CTX_INST, CTX_DATA):
        total = sum(counts[ctx])
        if total > 0:
            probs[ctx] = [c / total for c in counts[ctx]]
    return probs


def sample_distribution(prob_ctx, rng, max_rrpv):
    draw = rng.random()
    cumulative = 0.0
    for rrpv in range(max_rrpv + 1):
        cumulative += prob_ctx[rrpv]
        if draw < cumulative:
            return rrpv
    return max_rrpv


def infer_insert_rrpv_from_distribution(prob_ctx, max_rrpv):
    return max(range(max_rrpv + 1), key=lambda r: (prob_ctx[r], -r))


def _build_ipv_vector_from_distribution(prob_ctx, max_rrpv, seed=1):
    """Construct a PACIPV tuple from a target RRPV distribution.

    This adapts the state-allocation pseudocode into the existing PACIPV
    tuple representation (p0..p{max_rrpv}, insert).
    """
    n_states = max_rrpv + 1
    states_per_rrpv = [0] * (max_rrpv + 1)

    total = 0
    for rrpv in range(max_rrpv + 1):
        states_per_rrpv[rrpv] = int(round(prob_ctx[rrpv] * n_states))
        total += states_per_rrpv[rrpv]

    top_prob_rrpv = max(range(max_rrpv + 1), key=lambda r: (prob_ctx[r], -r))
    while total < n_states:
        states_per_rrpv[top_prob_rrpv] += 1
        total += 1

    while total > n_states:
        largest_bucket = max(range(max_rrpv + 1), key=lambda r: states_per_rrpv[r])
        if states_per_rrpv[largest_bucket] == 0:
            break
        states_per_rrpv[largest_bucket] -= 1
        total -= 1

    state_to_rrpv = []
    for rrpv in range(max_rrpv + 1):
        state_to_rrpv.extend([rrpv] * states_per_rrpv[rrpv])

    if not state_to_rrpv:
        # Fallback for degenerate inputs.
        one = min(1, max_rrpv)
        return (0, one, one, 0, max_rrpv)

    # Enforce exact cardinality even under edge-case rounding behavior.
    if len(state_to_rrpv) < n_states:
        state_to_rrpv.extend([top_prob_rrpv] * (n_states - len(state_to_rrpv)))
    elif len(state_to_rrpv) > n_states:
        state_to_rrpv = state_to_rrpv[:n_states]

    rng = random.Random(seed)
    rng.shuffle(state_to_rrpv)

    # Build cycle transitions over abstract states and map back to RRPV transitions.
    next_state = [(i + 1) % n_states for i in range(n_states)]
    representative_state = {}
    for i, rrpv in enumerate(state_to_rrpv):
        representative_state.setdefault(rrpv, i)

    hit_transitions = []
    for old_rrpv in range(max_rrpv + 1):
        src_state = representative_state.get(old_rrpv, representative_state[top_prob_rrpv])
        dst_state = next_state[src_state]
        hit_transitions.append(state_to_rrpv[dst_state])

    insert_rrpv = state_to_rrpv[0]
    return tuple(hit_transitions + [insert_rrpv])


def build_context_ipv_vectors_from_distribution(probs, max_rrpv):
    # Build vectors from full distributions (not only insertion argmax).
    data_vec = _build_ipv_vector_from_distribution(probs[CTX_DATA], max_rrpv, seed=1)
    inst_vec = _build_ipv_vector_from_distribution(probs[CTX_INST], max_rrpv, seed=2)
    return {
        CTX_DATA: data_vec,
        CTX_INST: inst_vec,
    }


def simulate_pacipv_distribution(num_sets, num_ways, trace_entries, probs, max_rrpv=3, seed=1):
    """Simulate miss handling with context-conditioned sampled insertion RRPVs."""
    rng = random.Random(seed)
    sets = [dict() for _ in range(num_sets)]
    misses = 0

    for pte, is_instr in trace_entries:
        set_id = hash(pte) % num_sets
        cache = sets[set_id]

        if pte in cache:
            cache[pte] = 0
            continue

        misses += 1

        if len(cache) >= num_ways:
            while True:
                victim = None
                for cand, rrpv in cache.items():
                    if rrpv == max_rrpv:
                        victim = cand
                        break
                if victim is not None:
                    del cache[victim]
                    break
                for cand in list(cache.keys()):
                    cache[cand] = min(max_rrpv, cache[cand] + 1)

        ctx = context_from_is_instr(is_instr)
        ins_rrpv = sample_distribution(probs[ctx], rng, max_rrpv)
        cache[pte] = max(0, min(max_rrpv, ins_rrpv))

    return misses / len(trace_entries)


def simulate_pacipv(num_sets, num_ways, trace_entries, ipv_vec, max_rrpv=3):
    sets = [dict() for _ in range(num_sets)]
    misses = 0

    for pte, is_instr in trace_entries:
        set_id = hash(pte) % num_sets
        cache = sets[set_id]
        ctx_ipv = resolve_ipv_for_context(ipv_vec, is_instr, max_rrpv)

        if pte in cache:
            old_rrpv = max(0, min(max_rrpv, cache[pte]))
            cache[pte] = max(0, min(max_rrpv, ctx_ipv[old_rrpv]))
            continue

        misses += 1

        if len(cache) >= num_ways:
            while True:
                victim = None
                for cand, rrpv in cache.items():
                    if rrpv == max_rrpv:
                        victim = cand
                        break
                if victim is not None:
                    del cache[victim]
                    break
                for cand in list(cache.keys()):
                    cache[cand] = min(max_rrpv, cache[cand] + 1)

        cache[pte] = max(0, min(max_rrpv, ctx_ipv[4]))

    return misses / len(trace_entries)


def simulate_pacipv_probabilistic(num_sets, num_ways, trace_entries, ipv_dist_spec, max_rrpv=3, seed=1):
    """Simulate PACIPV with sampled hit transitions and sampled insertions."""
    rng = random.Random(seed)
    sets = [dict() for _ in range(num_sets)]
    misses = 0

    for pte, is_instr in trace_entries:
        set_id = hash(pte) % num_sets
        cache = sets[set_id]
        ctx_policy = resolve_ipv_distribution_for_context(ipv_dist_spec, is_instr, max_rrpv)

        if pte in cache:
            old_rrpv = max(0, min(max_rrpv, int(cache[pte])))
            row = ctx_policy['hit_transition_probs'][old_rrpv]
            cache[pte] = _sample_from_probabilities(row, rng)
            continue

        misses += 1

        if len(cache) >= num_ways:
            while True:
                victim = None
                for cand, rrpv in cache.items():
                    if rrpv == max_rrpv:
                        victim = cand
                        break
                if victim is not None:
                    del cache[victim]
                    break
                for cand in list(cache.keys()):
                    cache[cand] = min(max_rrpv, cache[cand] + 1)

        cache[pte] = _sample_from_probabilities(ctx_policy['insert_probs'], rng)

    return misses / len(trace_entries)


def reachable_ipv_states(ipv, max_rrpv):
    reachable = {ipv[4]}
    changed = True
    while changed:
        changed = False
        new_states = set()
        for state in reachable:
            if state < max_rrpv:
                new_states.add(state + 1)
            new_states.add(ipv[state])
        for state in new_states:
            if state not in reachable:
                reachable.add(state)
                changed = True
    return reachable


def all_ipv_vectors(max_rrpv):
    candidates = []
    all_positions = set(range(max_rrpv + 1))

    if max_rrpv != 3:
        raise ValueError("PACIPV search currently expects pacipv-max-rrpv=3")

    for p0 in range(0, 1):
        for p1 in range(0, 2):
            for p2 in range(0, 3):
                for p3 in range(0, 4):
                    for insert in range(0, max_rrpv + 1):
                        cand = (p0, p1, p2, p3, insert)
                        if reachable_ipv_states(cand, max_rrpv) == all_positions:
                            candidates.append(cand)

    return candidates


def learn_pacipv_vectors(num_sets, num_ways, trace_loaders, max_rrpv=3):
    """Learn PACIPV by exhaustive vector search, with Belady-guided distributions as diagnostics."""
    cache_elements = max(1, num_sets * num_ways)
    t1 = cache_elements
    t2 = 4 * cache_elements

    aggregate_counts = {
        CTX_INST: [0] * (max_rrpv + 1),
        CTX_DATA: [0] * (max_rrpv + 1),
    }

    belady_rates = []
    for loader in trace_loaders:
        trace = loader()
        counts = build_context_rrpv_counts(trace, max_rrpv, t1, t2)
        for ctx in (CTX_INST, CTX_DATA):
            for rrpv in range(max_rrpv + 1):
                aggregate_counts[ctx][rrpv] += counts[ctx][rrpv]
        belady_rates.append(simulate_opt(num_sets, num_ways, trace_entries_to_ptes(trace)))
        del trace

    probs = normalize_context_rrpv_counts(aggregate_counts, max_rrpv)

    candidates = all_ipv_vectors(max_rrpv)
    if not candidates:
        raise ValueError("No valid PACIPV candidates were generated.")

    best_vec = None
    best_rate = float('inf')
    for cand in candidates:
        cand_rates = []
        for loader in trace_loaders:
            trace = loader()
            cand_rates.append(simulate_pacipv(num_sets, num_ways, trace, cand, max_rrpv))
            del trace
        cand_avg = safe_mean(cand_rates)
        if best_vec is None or cand_avg < best_rate or (cand_avg == best_rate and cand < best_vec):
            best_vec = cand
            best_rate = cand_avg

    # Per user request: use the same best IPV vector for INST and DATA contexts.
    context_ipv = {
        CTX_DATA: best_vec,
        CTX_INST: best_vec,
    }

    pacipv_dist_rates = []
    pacipv_rates = []
    for trace_idx, loader in enumerate(trace_loaders):
        trace = loader()
        pacipv_dist_rates.append(
            simulate_pacipv_distribution(
                num_sets,
                num_ways,
                trace,
                probs,
                max_rrpv=max_rrpv,
                seed=trace_idx + 1,
            )
        )
        pacipv_rates.append(simulate_pacipv(num_sets, num_ways, trace, context_ipv, max_rrpv))
        del trace

    return {
        'ipv_vec': tuple(context_ipv[CTX_DATA]),
        'ipv_by_context': context_ipv,
        'rrpv_counts_by_context': aggregate_counts,
        'rrpv_probs_by_context': probs,
        'reuse_thresholds': {'t1': t1, 't2': t2},
        'max_rrpv': max_rrpv,
        'num_candidates': len(candidates),
        'avg_belady_rate': safe_mean(belady_rates),
        'avg_pacipv_dist_rate': safe_mean(pacipv_dist_rates),
        'avg_pacipv_rate': safe_mean(pacipv_rates),
    }


def save_pacipv_vectors(path, result):
    ipv_by_context = result.get('ipv_by_context', {CTX_DATA: result['ipv_vec'], CTX_INST: result['ipv_vec']})
    data_ipv_vec = ipv_by_context[CTX_DATA]
    inst_ipv_vec = ipv_by_context[CTX_INST]
    max_rrpv = result['max_rrpv']
    data_ipv_str = ','.join(str(v) for v in data_ipv_vec)
    inst_ipv_str = ','.join(str(v) for v in inst_ipv_vec)
    probs = result.get('rrpv_probs_by_context', {})
    thresholds = result.get('reuse_thresholds', {})

    with open(path, 'w') as f:
        f.write('# Learned PACIPV vector\n')
        f.write(f'# max_rrpv={max_rrpv}\n')
        if thresholds:
            f.write(f'# reuse_thresholds: T1={thresholds.get("t1")} T2={thresholds.get("t2")}\n')
        f.write(f'# avg_belady_rate={result["avg_belady_rate"]:.6f}\n')
        if 'avg_pacipv_dist_rate' in result:
            f.write(f'# avg_pacipv_dist_rate={result["avg_pacipv_dist_rate"]:.6f}\n')
        f.write(f'# avg_pacipv_rate={result["avg_pacipv_rate"]:.6f}\n')
        f.write('\n')

        if probs:
            f.write('# RRPV distributions inferred from Belady reuse distance\n')
            f.write('# rrpv, P_inst, P_data\n')
            for rrpv in range(max_rrpv + 1):
                f.write(
                    f'# {rrpv}, {probs[CTX_INST][rrpv]:.6f}, {probs[CTX_DATA][rrpv]:.6f}\n'
                )
            f.write('\n')

        f.write(f'TXVC_PACIPV_INST_VEC={inst_ipv_str}\n')
        f.write(f'TXVC_PACIPV_DATA_VEC={data_ipv_str}\n')
        f.write(f'TXVC_PACIPV_DEMAND_VEC={data_ipv_str}\n\n')
        f.write('# Example usage\n')
        f.write('export TXVC_PACIPV_INST_VEC="' + inst_ipv_str + '"\n')
        f.write('export TXVC_PACIPV_DATA_VEC="' + data_ipv_str + '"\n')
        f.write('export TXVC_PACIPV_DEMAND_VEC="' + data_ipv_str + '"\n')
        f.write('export TXVC_REP_POLICY=pacipv\n')

    print(f"PACIPV vectors saved to {path}")
