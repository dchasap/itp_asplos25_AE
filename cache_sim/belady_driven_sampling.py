import random
from collections import defaultdict

from cache_sim.constants import CTX_DATA, CTX_INST
from cache_sim.trace import trace_entries_to_ptes
from cache_sim.belady import simulate_opt
from cache_sim.utils import safe_mean


def _context_from_is_instr(is_instr):
    return CTX_INST if is_instr else CTX_DATA


def _map_reuse_to_rrpv(reuse_distance, max_rrpv, t1, t2):
    if reuse_distance == float('inf'):
        return max_rrpv
    if reuse_distance <= t1:
        return 0
    if reuse_distance <= t2:
        return max_rrpv - 1
    return max_rrpv


def _build_context_rrpv_counts(trace_entries, max_rrpv, t1, t2):
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

        ctx = _context_from_is_instr(is_instr)
        rrpv = _map_reuse_to_rrpv(reuse_distance, max_rrpv, t1, t2)
        counts[ctx][rrpv] += 1

    return counts


def _normalize_context_rrpv_counts(counts, max_rrpv):
    probs = {
        CTX_INST: [0.0] * (max_rrpv + 1),
        CTX_DATA: [0.0] * (max_rrpv + 1),
    }
    for ctx in (CTX_INST, CTX_DATA):
        total = sum(counts[ctx])
        if total > 0:
            probs[ctx] = [c / total for c in counts[ctx]]
    return probs


def _sample_rrpv(prob_ctx, rng, max_rrpv):
    r = rng.random()
    cumulative = 0.0
    for rrpv in range(max_rrpv + 1):
        cumulative += prob_ctx[rrpv]
        if r < cumulative:
            return rrpv
    return max_rrpv


def _expected_rrpv(prob_ctx):
    return sum(rrpv * prob for rrpv, prob in enumerate(prob_ctx))


def learn_belady_driven_sampling(num_sets, num_ways, trace_loaders, max_rrpv=3):
    """Learn context-conditioned insertion distributions from Belady-guided labels."""
    cache_elements = max(1, num_sets * num_ways)
    t1 = cache_elements
    t2 = 4 * cache_elements

    aggregate_counts = {
        CTX_INST: [0] * (max_rrpv + 1),
        CTX_DATA: [0] * (max_rrpv + 1),
    }

    belady_rates = []
    for loader in trace_loaders:
        trace_entries = loader()
        counts = _build_context_rrpv_counts(trace_entries, max_rrpv, t1, t2)
        for ctx in (CTX_INST, CTX_DATA):
            for rrpv in range(max_rrpv + 1):
                aggregate_counts[ctx][rrpv] += counts[ctx][rrpv]
        belady_rates.append(simulate_opt(num_sets, num_ways, trace_entries_to_ptes(trace_entries)))

    probs = _normalize_context_rrpv_counts(aggregate_counts, max_rrpv)
    return {
        'rrpv_counts_by_context': aggregate_counts,
        'rrpv_probs_by_context': probs,
        'reuse_thresholds': {'t1': t1, 't2': t2},
        'max_rrpv': max_rrpv,
        'avg_belady_rate': safe_mean(belady_rates),
    }


def simulate_belady_driven_sampling(num_sets, num_ways, trace_entries, probs, max_rrpv=3, seed=1, alpha=1.0):
    """IPV-guided SRRIP with sampled insertion and expected-value hit rejuvenation."""
    rng = random.Random(seed)
    sets = [[] for _ in range(num_sets)]
    misses = 0
    expected_rrpv = {
        CTX_INST: _expected_rrpv(probs[CTX_INST]),
        CTX_DATA: _expected_rrpv(probs[CTX_DATA]),
    }

    for addr, is_instr in trace_entries:
        set_id = hash(addr) % num_sets
        cache_set = sets[set_id]

        hit_line = None
        for line in cache_set:
            if line['addr'] == addr:
                hit_line = line
                break

        if hit_line is not None:
            # IPV-guided rejuvenation toward expected reuse state for this line context.
            ctx = hit_line['type']
            hit_line['rrpv'] = (1.0 - alpha) * hit_line['rrpv'] + alpha * expected_rrpv[ctx]
            hit_line['rrpv'] = max(0.0, min(float(max_rrpv), hit_line['rrpv']))
            continue

        misses += 1
        ctx = _context_from_is_instr(is_instr)
        rrpv_insert = _sample_rrpv(probs[ctx], rng, max_rrpv)

        if len(cache_set) < num_ways:
            cache_set.append({'addr': addr, 'rrpv': rrpv_insert, 'type': ctx})
            continue

        while True:
            victim_idx = None
            for idx, line in enumerate(cache_set):
                if line['rrpv'] >= max_rrpv:
                    victim_idx = idx
                    break
            if victim_idx is not None:
                cache_set[victim_idx] = {'addr': addr, 'rrpv': rrpv_insert, 'type': ctx}
                break
            for line in cache_set:
                line['rrpv'] = min(float(max_rrpv), line['rrpv'] + 1.0)

    return misses / len(trace_entries)
