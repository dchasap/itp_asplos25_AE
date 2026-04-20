import math
from collections import defaultdict

from cache_sim.belady import simulate_opt
from cache_sim.constants import CTX_DATA, CTX_INST
from cache_sim.pacipv import (
    save_pacipv_vectors,
    simulate_pacipv,
)
from cache_sim.trace import trace_entries_to_ptes


def _context_from_is_instr(is_instr):
    return CTX_INST if is_instr else CTX_DATA


def _precompute_next_use(ptes):
    next_use = [float('inf')] * len(ptes)
    last_seen = {}

    for idx in range(len(ptes) - 1, -1, -1):
        addr = ptes[idx]
        if addr in last_seen:
            next_use[idx] = last_seen[addr] - idx
        last_seen[addr] = idx

    return next_use


def _compute_thresholds(values, num_states):
    finite = sorted(v for v in values if not math.isinf(v))
    if not finite:
        return [float('inf')] * (num_states - 1)

    thresholds = []
    for bucket_idx in range(1, num_states):
        percentile = bucket_idx / num_states
        value_idx = min(len(finite) - 1, int(percentile * len(finite)))
        thresholds.append(finite[value_idx])
    return thresholds


def _map_to_state(distance, thresholds):
    if math.isinf(distance):
        return len(thresholds)
    for state, threshold in enumerate(thresholds):
        if distance <= threshold:
            return state
    return len(thresholds)


def _format_threshold(value):
    if math.isinf(value):
        return 'inf'
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _choose_victim(cache, max_rrpv):
    while True:
        for cand, rrpv in cache.items():
            if rrpv >= max_rrpv:
                return cand
        for cand in list(cache.keys()):
            cache[cand] = min(max_rrpv, cache[cand] + 1)


def _argmax(values, prefer_high=False):
    if prefer_high:
        return max(range(len(values)), key=lambda i: (values[i], i))
    return max(range(len(values)), key=lambda i: (values[i], -i))


def _fallback_ipv(max_rrpv):
    # SRRIP-like fallback: one-step promotion on hit, insert at max-1.
    hit_targets = [0] * (max_rrpv + 1)
    for old in range(max_rrpv + 1):
        hit_targets[old] = max(0, old - 1)
    insert_rrpv = max(0, max_rrpv - 1)
    return tuple(hit_targets + [insert_rrpv])


def _votes_to_vector(insert_votes, hit_votes, max_rrpv):
    if sum(insert_votes) == 0:
        return _fallback_ipv(max_rrpv)

    insert = _argmax(insert_votes, prefer_high=True)
    hit_targets = [0] * (max_rrpv + 1)

    for old_state in range(max_rrpv + 1):
        row = hit_votes[old_state]
        if sum(row) == 0:
            hit_targets[old_state] = max(0, old_state - 1)
        else:
            # Prefer hotter state on hit ties.
            hit_targets[old_state] = _argmax(row, prefer_high=False)

    return tuple(hit_targets + [insert])


def load_pacipv_shadow_vectors(path, max_rrpv=3):
    inst_vec = None
    data_vec = None

    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('TXVC_PACIPV_INST_VEC='):
                raw = line.split('=', 1)[1].strip().strip('"')
                inst_vec = tuple(int(x.strip()) for x in raw.split(',') if x.strip())
            elif line.startswith('TXVC_PACIPV_DATA_VEC='):
                raw = line.split('=', 1)[1].strip().strip('"')
                data_vec = tuple(int(x.strip()) for x in raw.split(',') if x.strip())

    if data_vec is None and inst_vec is None:
        raise ValueError(f"No PACIPV vectors found in '{path}'")

    if data_vec is None:
        data_vec = inst_vec
    if inst_vec is None:
        inst_vec = data_vec

    expected_len = max_rrpv + 2
    if len(data_vec) != expected_len or len(inst_vec) != expected_len:
        raise ValueError(
            f"Vector length mismatch in '{path}'. Expected {expected_len}, "
            f"got data={len(data_vec)}, inst={len(inst_vec)}"
        )

    return {
        'ipv_vec': tuple(data_vec),
        'ipv_by_context': {
            CTX_DATA: tuple(data_vec),
            CTX_INST: tuple(inst_vec),
        },
        'max_rrpv': max_rrpv,
    }


def train_pacipv_shadow_distilled(
    num_sets,
    num_ways,
    trace_entries,
    *,
    max_rrpv=3,
    per_context=True,
):
    """
    Learn PACIPV vectors via Belady + Shadow SRRIP Distillation.
    
    Algorithm:
    1. Map each access's next-use distance to an SRRIP state (hot/warm/cold/dead).
    2. On miss/insert: record insert_votes[target_state], evict via canonical aging.
    3. On hit: record hit_votes[old_state][target_state], teacher-force shadow to target_state.
    4. Collapse distributions via argmax → deterministic PACIPV vector per context.
    """
    if not trace_entries:
        raise ValueError('trace_entries must not be empty')

    # ==========================================================================
    # Step 0: Precompute next-use distances and reuse-distance thresholds
    # ==========================================================================
    ptes = trace_entries_to_ptes(trace_entries)
    next_use = _precompute_next_use(ptes)
    thresholds = _compute_thresholds(next_use, max_rrpv + 1)
    print(
        "[pacipv_shadow] reuse-distance thresholds "
        f"(max_rrpv={max_rrpv}, states={max_rrpv + 1}): "
        + ", ".join(
            f"t{i + 1}={_format_threshold(t)}" for i, t in enumerate(thresholds)
        )
    )

    # ==========================================================================
    # Step 1: Initialize voting histograms (distributions)
    # ==========================================================================
    insert_votes = {
        CTX_DATA: [0] * (max_rrpv + 1),
        CTX_INST: [0] * (max_rrpv + 1),
    }
    hit_votes = {
        CTX_DATA: [[0] * (max_rrpv + 1) for _ in range(max_rrpv + 1)],
        CTX_INST: [[0] * (max_rrpv + 1) for _ in range(max_rrpv + 1)],
    }

    shadow_sets = [dict() for _ in range(num_sets)]

    # ==========================================================================
    # Step 2: Simulate shadow SRRIP, accumulating votes from Belady targets
    # ==========================================================================
    for idx, (addr, is_instr) in enumerate(trace_entries):
        ctx = _context_from_is_instr(is_instr) if per_context else CTX_DATA
        
        # Map next-use distance to target SRRIP state (0=hot, 1=warm, 2=cold, 3=dead).
        target_state = _map_to_state(next_use[idx], thresholds)

        set_id = hash(addr) % num_sets
        cache = shadow_sets[set_id]

        # --- ON HIT ---
        if addr in cache:
            old_state = max(0, min(max_rrpv, int(cache[addr])))
            # Record: saw transition from old_state → target_state
            hit_votes[ctx][old_state][target_state] += 1
            # Teacher-force shadow state to align with Belady's future reuse guidance
            cache[addr] = target_state
            continue

        # --- ON MISS/INSERT ---
        # Record: Belady recommended inserting at target_state
        insert_votes[ctx][target_state] += 1

        # If cache is full, evict via canonical SRRIP aging
        if len(cache) >= num_ways:
            victim = _choose_victim(cache, max_rrpv)
            del cache[victim]

        # Insert at target state in shadow SRRIP
        cache[addr] = target_state

    # ==========================================================================
    # Step 3: Collapse voting distributions → deterministic PACIPV vectors
    # ==========================================================================
    data_vec = _votes_to_vector(insert_votes[CTX_DATA], hit_votes[CTX_DATA], max_rrpv)
    if per_context:
        inst_vec = _votes_to_vector(insert_votes[CTX_INST], hit_votes[CTX_INST], max_rrpv)
    else:
        inst_vec = data_vec

    ipv_by_context = {
        CTX_DATA: data_vec,
        CTX_INST: inst_vec,
    }

    # ==========================================================================
    # Step 4: Evaluate learned vectors
    # ==========================================================================
    belady_rate = simulate_opt(num_sets, num_ways, ptes)
    pacipv_rate = simulate_pacipv(num_sets, num_ways, trace_entries, ipv_by_context, max_rrpv=max_rrpv)

    return {
        'ipv_vec': tuple(data_vec),
        'ipv_by_context': ipv_by_context,
        'max_rrpv': max_rrpv,
        'reuse_thresholds': {
            't1': thresholds[0] if thresholds else float('inf'),
            't2': thresholds[1] if len(thresholds) > 1 else float('inf'),
        },
        'avg_belady_rate': belady_rate,
        'avg_pacipv_rate': pacipv_rate,
        'training_method': 'shadow_srrip_state_distillation',
        'insert_votes': insert_votes,
        'hit_votes': hit_votes,
    }


def save_pacipv_shadow_vectors(path, result):
    save_pacipv_vectors(path, result)
