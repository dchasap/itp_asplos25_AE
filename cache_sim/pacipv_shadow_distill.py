import math
import json
from collections import defaultdict

from cache_sim.belady import simulate_opt
from cache_sim.constants import CTX_DATA, CTX_INST
from cache_sim.pacipv import (
    save_pacipv_vectors,
    simulate_pacipv,
    simulate_pacipv_probabilistic,
)
from cache_sim.trace import trace_entries_to_ptes
from cache_sim.utils import safe_mean


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


def _compute_reuse_distance_stats(next_use, thresholds, max_rrpv):
    """
    Compute statistics about reuse distance distribution.
    Shows how many accesses fall into each bucket and identifies long-reuse bias.
    """
    bucket_counts = [0] * (max_rrpv + 1)
    bucket_finite = [0] * (max_rrpv + 1)
    
    for distance in next_use:
        state = _map_to_state(distance, thresholds)
        bucket_counts[state] += 1
        if not math.isinf(distance):
            bucket_finite[state] += 1
    
    total = len(next_use)
    long_reuse_ratio = bucket_counts[-1] / total if total > 0 else 0
    
    return {
        'bucket_counts': bucket_counts,
        'bucket_finite': bucket_finite,
        'total_accesses': total,
        'dead_on_arrival_count': bucket_counts[-1],
        'dead_on_arrival_ratio': long_reuse_ratio,
        'short_reuse_count': sum(bucket_counts[:-1]),
        'short_reuse_ratio': 1.0 - long_reuse_ratio,
    }


def _constrain_hit_transitions_to_mru(hit_votes, max_rrpv):
    """
    Create constrained hit transition table with strict promotion semantics.

    Rules:
    - Keep monotonicity toward MRU.
    - Enforce strict promotion for old_state > 0: new_state <= old_state - 1.
    - Pin hottest state: old_state == 0 can only transition to 0.

    Returns a copy with invalid transitions set to 0.
    """
    constrained = [[0] * (max_rrpv + 1) for _ in range(max_rrpv + 1)]

    for old_state in range(max_rrpv + 1):
        allowed_max_new_state = 0 if old_state == 0 else old_state - 1
        for new_state in range(max_rrpv + 1):
            if new_state <= allowed_max_new_state:
                constrained[old_state][new_state] = hit_votes[old_state][new_state]

    return constrained


def _votes_to_vector_with_constraints(insert_votes, hit_votes, max_rrpv, constrained=False):
    """Generate vector, optionally using constrained hit transitions."""
    if constrained:
        hit_votes_to_use = _constrain_hit_transitions_to_mru(hit_votes, max_rrpv)
    else:
        hit_votes_to_use = hit_votes
    
    return _votes_to_vector(insert_votes, hit_votes_to_use, max_rrpv)


def _print_hit_transition_analysis(hit_votes, hit_votes_constrained, max_rrpv, ctx_name):
    """
    Print detailed analysis comparing original vs constrained hit transitions.
    Shows transitions that move away from MRU and how constraining affects them.
    """
    print(f"\n[pacipv_shadow] Hit transition analysis for {ctx_name}:")
    print(f"  State transitions that move AWAY from MRU (new_state > old_state):")
    
    away_from_mru_votes = 0
    away_from_mru_transitions = []
    
    for old_state in range(max_rrpv + 1):
        for new_state in range(max_rrpv + 1):
            if new_state > old_state:
                votes = hit_votes[old_state][new_state]
                if votes > 0:
                    away_from_mru_votes += votes
                    away_from_mru_transitions.append((old_state, new_state, votes))
    
    if away_from_mru_transitions:
        away_from_mru_transitions.sort(key=lambda x: x[2], reverse=True)
        for old_state, new_state, votes in away_from_mru_transitions[:5]:  # Top 5
            pct = 100.0 * votes / sum(sum(row) for row in hit_votes)
            print(f"    s{old_state} → s{new_state}: {votes} votes ({pct:.2f}%)")
        print(f"  Total votes moving away from MRU: {away_from_mru_votes}")
    else:
        print("    None - all transitions already move toward MRU!")
    
    # Compare original vs constrained
    original_total = sum(sum(row) for row in hit_votes)
    constrained_total = sum(sum(row) for row in hit_votes_constrained)
    lost_votes = original_total - constrained_total
    if lost_votes > 0:
        pct_lost = 100.0 * lost_votes / original_total
        print(f"  Impact of constraining: {lost_votes} votes removed ({pct_lost:.2f}%)")


def _normalize_votes(votes_dict, max_rrpv):
    """Convert vote counts to probabilities for each context."""
    probs = {}
    for ctx in [CTX_DATA, CTX_INST]:
        votes = votes_dict.get(ctx, [0] * (max_rrpv + 1))
        total = sum(votes)
        if total == 0:
            probs[ctx] = [0.0] * (max_rrpv + 1)
        else:
            probs[ctx] = [v / total for v in votes]
    return probs


def _normalize_hit_votes(hit_votes_dict, max_rrpv):
    """Convert 2D hit vote counts to probabilities for each context and old_state."""
    probs = {}
    for ctx in [CTX_DATA, CTX_INST]:
        hit_votes = hit_votes_dict.get(ctx, [[0] * (max_rrpv + 1) for _ in range(max_rrpv + 1)])
        probs[ctx] = []
        for old_state in range(max_rrpv + 1):
            row = hit_votes[old_state]
            total = sum(row)
            if total == 0:
                probs[ctx].append([0.0] * (max_rrpv + 1))
            else:
                probs[ctx].append([v / total for v in row])
    return probs


def _normalize_row(values, fallback_idx):
    row = [max(0.0, float(v)) for v in values]
    total = sum(row)
    if total <= 0.0:
        out = [0.0] * len(row)
        out[fallback_idx] = 1.0
        return out
    return [v / total for v in row]


def _constrain_hit_votes_monotonic(hit_votes, max_rrpv):
    """
    Enforce monotonic hit transitions: new_state <= old_state.

    This guarantees hits never move to a higher RRPV value (colder state).
    """
    constrained = [[0] * (max_rrpv + 1) for _ in range(max_rrpv + 1)]
    for old_state in range(max_rrpv + 1):
        for new_state in range(old_state + 1):
            constrained[old_state][new_state] = hit_votes[old_state][new_state]
    return constrained


def _build_probabilistic_policy(insert_votes_ctx, hit_votes_ctx, max_rrpv):
    insert_fallback = max(0, max_rrpv - 1)
    insert_probs = _normalize_row(insert_votes_ctx, insert_fallback)

    hit_transition_probs = []
    for old_state in range(max_rrpv + 1):
        # If the row has no votes, fallback to one-step promotion toward MRU.
        fallback_target = max(0, old_state - 1)
        row = _normalize_row(hit_votes_ctx[old_state], fallback_target)
        hit_transition_probs.append(row)

    return {
        'insert_probs': insert_probs,
        'hit_transition_probs': hit_transition_probs,
    }


def _categorize_hit_transitions(hit_votes_dict, max_rrpv):
    """
    Categorize hit transitions as promotions (toward MRU), demotions (away), or stays.
    Returns dicts with totals, promotions, demotions, stays for each context and old_state.
    """
    categorized = {
        'hit_total': {},
        'hit_promotions': {},
        'hit_demotions': {},
        'hit_stays': {},
    }
    
    for ctx in [CTX_DATA, CTX_INST]:
        hit_votes = hit_votes_dict.get(ctx, [[0] * (max_rrpv + 1) for _ in range(max_rrpv + 1)])
        
        totals = []
        promotions = []
        demotions = []
        stays = []
        
        for old_state in range(max_rrpv + 1):
            total = sum(hit_votes[old_state])
            promote = sum(hit_votes[old_state][new_state] for new_state in range(old_state))  # new < old
            demote = sum(hit_votes[old_state][new_state] for new_state in range(old_state + 1, max_rrpv + 1))  # new > old
            stay = hit_votes[old_state][old_state]
            
            totals.append(total)
            promotions.append(promote)
            demotions.append(demote)
            stays.append(stay)
        
        categorized['hit_total'][ctx] = totals
        categorized['hit_promotions'][ctx] = promotions
        categorized['hit_demotions'][ctx] = demotions
        categorized['hit_stays'][ctx] = stays
    
    return categorized


def _compute_long_reuse_bias(hit_votes_raw, hit_votes_constrained, next_use, thresholds, max_rrpv):
    """
    Track how many insertions/hits involved infinite (no future) vs finite reuse distances.
    Separately for raw and constrained hit transitions.
    """
    bias = {
        'insert_inf_count': {CTX_DATA: 0, CTX_INST: 0},
        'insert_finite_count': {CTX_DATA: 0, CTX_INST: 0},
        'hit_inf_count': {CTX_DATA: 0, CTX_INST: 0},
        'hit_finite_count': {CTX_DATA: 0, CTX_INST: 0},
        'insert_inf_targets': {CTX_DATA: [], CTX_INST: []},
        'insert_finite_targets': {CTX_DATA: [], CTX_INST: []},
        'hit_inf_targets_raw': {CTX_DATA: [], CTX_INST: []},
        'hit_finite_targets_raw': {CTX_DATA: [], CTX_INST: []},
        'hit_inf_targets_clipped': {CTX_DATA: [], CTX_INST: []},
        'hit_finite_targets_clipped': {CTX_DATA: [], CTX_INST: []},
    }
    
    # Dummy implementation - would need access to trace during training
    # For now, return structured dict for compatibility
    return bias



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
    inst_vec_constrained = None
    data_vec_constrained = None

    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('TXVC_PACIPV_INST_VEC='):
                raw = line.split('=', 1)[1].strip().strip('"')
                inst_vec = tuple(int(x.strip()) for x in raw.split(',') if x.strip())
            elif line.startswith('TXVC_PACIPV_DATA_VEC='):
                raw = line.split('=', 1)[1].strip().strip('"')
                data_vec = tuple(int(x.strip()) for x in raw.split(',') if x.strip())
            elif line.startswith('TXVC_PACIPV_INST_VEC_CONSTRAINED='):
                raw = line.split('=', 1)[1].strip().strip('"')
                inst_vec_constrained = tuple(int(x.strip()) for x in raw.split(',') if x.strip())
            elif line.startswith('TXVC_PACIPV_DATA_VEC_CONSTRAINED='):
                raw = line.split('=', 1)[1].strip().strip('"')
                data_vec_constrained = tuple(int(x.strip()) for x in raw.split(',') if x.strip())

    if data_vec is None and inst_vec is None:
        raise ValueError(f"No PACIPV vectors found in '{path}'")

    if data_vec is None:
        data_vec = inst_vec
    if inst_vec is None:
        inst_vec = data_vec

    if data_vec_constrained is None:
        data_vec_constrained = data_vec
    if inst_vec_constrained is None:
        inst_vec_constrained = inst_vec

    expected_len = max_rrpv + 2
    if (
        len(data_vec) != expected_len
        or len(inst_vec) != expected_len
        or len(data_vec_constrained) != expected_len
        or len(inst_vec_constrained) != expected_len
    ):
        raise ValueError(
            f"Vector length mismatch in '{path}'. Expected {expected_len}, "
            f"got data={len(data_vec)}, inst={len(inst_vec)}, "
            f"data_constrained={len(data_vec_constrained)}, "
            f"inst_constrained={len(inst_vec_constrained)}"
        )

    return {
        'ipv_vec': tuple(data_vec),
        'ipv_vec_constrained': tuple(data_vec_constrained),
        'ipv_by_context': {
            CTX_DATA: tuple(data_vec),
            CTX_INST: tuple(inst_vec),
        },
        'ipv_by_context_constrained': {
            CTX_DATA: tuple(data_vec_constrained),
            CTX_INST: tuple(inst_vec_constrained),
        },
        'max_rrpv': max_rrpv,
    }


def _accumulate_votes_from_trace(
    trace_entries, num_sets, num_ways, max_rrpv, per_context, insert_votes, hit_votes
):
    """
    Process one trace and accumulate shadow SRRIP votes into the provided dicts.

    Shadow state is local to this call, so each trace is processed independently.
    Thresholds are computed per-trace (calibrated to that trace's reuse distances).
    All large temporaries (ptes, next_use, shadow_sets) are freed before returning.
    """
    # Precompute per-trace next-use distances and thresholds
    ptes = trace_entries_to_ptes(trace_entries)
    next_use = _precompute_next_use(ptes)
    thresholds = _compute_thresholds(next_use, max_rrpv + 1)
    del ptes  # free address copy; no longer needed

    reuse_stats = _compute_reuse_distance_stats(next_use, thresholds, max_rrpv)
    print(
        "[pacipv_shadow] reuse-distance thresholds "
        f"(max_rrpv={max_rrpv}, states={max_rrpv + 1}): "
        + ", ".join(f"t{i + 1}={_format_threshold(t)}" for i, t in enumerate(thresholds))
    )
    print(
        f"[pacipv_shadow] Reuse distance distribution: "
        f"dead-on-arrival (state {max_rrpv}): {reuse_stats['dead_on_arrival_count']} "
        f"({reuse_stats['dead_on_arrival_ratio']*100:.1f}%), "
        f"short-reuse (states 0-{max_rrpv-1}): {reuse_stats['short_reuse_count']} "
        f"({reuse_stats['short_reuse_ratio']*100:.1f}%)"
    )
    print(
        f"[pacipv_shadow] Bucket distribution: "
        + ", ".join(f"s{i}={reuse_stats['bucket_counts'][i]}" for i in range(max_rrpv + 1))
    )

    # Shadow simulation — state is local per trace
    shadow_sets = [dict() for _ in range(num_sets)]
    for idx, (addr, is_instr) in enumerate(trace_entries):
        ctx = _context_from_is_instr(is_instr) if per_context else CTX_DATA
        target_state = _map_to_state(next_use[idx], thresholds)
        set_id = hash(addr) % num_sets
        cache = shadow_sets[set_id]

        if addr in cache:
            old_state = max(0, min(max_rrpv, int(cache[addr])))
            hit_votes[ctx][old_state][target_state] += 1
            cache[addr] = target_state
            continue

        insert_votes[ctx][target_state] += 1
        if len(cache) >= num_ways:
            victim = _choose_victim(cache, max_rrpv)
            del cache[victim]
        cache[addr] = target_state

    del next_use
    del shadow_sets


def train_pacipv_shadow_distilled(
    num_sets,
    num_ways,
    trace_loaders,
    *,
    max_rrpv=3,
    per_context=True,
):
    """
    Learn PACIPV vectors via Belady + Shadow SRRIP Distillation.

    trace_loaders: list of callables, each returning a trace_entries list.
    Processes one trace at a time to avoid loading all benchmarks into memory
    simultaneously — each trace's temporaries (ptes, next_use, shadow cache) are
    freed before the next trace is loaded.

    Algorithm:
    1. Map each access's next-use distance to an SRRIP state (hot/warm/cold/dead).
    2. On miss/insert: record insert_votes[target_state], evict via canonical aging.
    3. On hit: record hit_votes[old_state][target_state], teacher-force shadow to target_state.
    4. Collapse distributions via argmax → deterministic PACIPV vector per context.
    """
    if not trace_loaders:
        raise ValueError('trace_loaders must not be empty')

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

    # ==========================================================================
    # Step 2: Process each trace independently, accumulate votes, then free
    # ==========================================================================
    for loader in trace_loaders:
        trace_entries = loader()
        if not trace_entries:
            continue
        _accumulate_votes_from_trace(
            trace_entries, num_sets, num_ways, max_rrpv, per_context,
            insert_votes, hit_votes,
        )
        del trace_entries

    total_insert = sum(sum(v) for v in insert_votes.values())
    if total_insert == 0:
        raise ValueError('No usable training data found across all trace loaders')

    # ==========================================================================
    # Step 3: Collapse voting distributions → deterministic PACIPV vectors
    #         Compute constrained table ONCE and reuse everywhere below.
    # ==========================================================================
    constrained_hit_votes = {
        CTX_DATA: _constrain_hit_transitions_to_mru(hit_votes[CTX_DATA], max_rrpv),
        CTX_INST: _constrain_hit_transitions_to_mru(hit_votes[CTX_INST], max_rrpv),
    }

    data_vec = _votes_to_vector(insert_votes[CTX_DATA], hit_votes[CTX_DATA], max_rrpv)
    data_vec_constrained = _votes_to_vector(
        insert_votes[CTX_DATA], constrained_hit_votes[CTX_DATA], max_rrpv
    )

    if per_context:
        inst_vec = _votes_to_vector(insert_votes[CTX_INST], hit_votes[CTX_INST], max_rrpv)
        inst_vec_constrained = _votes_to_vector(
            insert_votes[CTX_INST], constrained_hit_votes[CTX_INST], max_rrpv
        )
    else:
        inst_vec = data_vec
        inst_vec_constrained = data_vec_constrained

    ipv_by_context = {CTX_DATA: data_vec, CTX_INST: inst_vec}
    ipv_by_context_constrained = {CTX_DATA: data_vec_constrained, CTX_INST: inst_vec_constrained}

    # Print hit transition analysis (reuse already-computed constrained table)
    _print_hit_transition_analysis(
        hit_votes[CTX_DATA], constrained_hit_votes[CTX_DATA], max_rrpv, "DATA context"
    )
    if per_context:
        _print_hit_transition_analysis(
            hit_votes[CTX_INST], constrained_hit_votes[CTX_INST], max_rrpv, "INST context"
        )

    # ==========================================================================
    # Step 4: Evaluate learned vectors — iterate loaders again (traces freed above)
    # ==========================================================================
    belady_rates = []
    pacipv_rates = []
    pacipv_rates_constrained = []
    for loader in trace_loaders:
        trace_entries = loader()
        if not trace_entries:
            continue
        ptes = trace_entries_to_ptes(trace_entries)
        belady_rates.append(simulate_opt(num_sets, num_ways, ptes))
        del ptes
        pacipv_rates.append(
            simulate_pacipv(num_sets, num_ways, trace_entries, ipv_by_context, max_rrpv=max_rrpv)
        )
        pacipv_rates_constrained.append(
            simulate_pacipv(num_sets, num_ways, trace_entries, ipv_by_context_constrained, max_rrpv=max_rrpv)
        )
        del trace_entries

    # ==========================================================================
    # Step 5: Compute statistics for comprehensive reporting (votes only, no traces)
    # ==========================================================================
    insert_vote_probs = _normalize_votes(insert_votes, max_rrpv)
    hit_vote_probs_raw = _normalize_hit_votes(hit_votes, max_rrpv)
    hit_vote_probs_constrained = _normalize_hit_votes(constrained_hit_votes, max_rrpv)
    hit_transition_stats = _categorize_hit_transitions(hit_votes, max_rrpv)
    hit_transition_stats_constrained = _categorize_hit_transitions(constrained_hit_votes, max_rrpv)
    long_reuse_bias = _compute_long_reuse_bias(
        hit_votes, constrained_hit_votes, None, None, max_rrpv
    )

    return {
        'ipv_vec': tuple(data_vec),
        'ipv_vec_constrained': tuple(data_vec_constrained),
        'ipv_by_context': ipv_by_context,
        'ipv_by_context_constrained': ipv_by_context_constrained,
        'max_rrpv': max_rrpv,
        'avg_belady_rate': safe_mean(belady_rates),
        'avg_pacipv_rate': safe_mean(pacipv_rates),
        'avg_pacipv_rate_constrained': safe_mean(pacipv_rates_constrained),
        'training_method': 'shadow_srrip_state_distillation',
        # Vote counts
        'insert_votes': insert_votes,
        'hit_votes': hit_votes,
        'hit_votes_raw': hit_votes,  # Before constraining
        'hit_votes_constrained': constrained_hit_votes,
        # Probabilities
        'insert_vote_probs': insert_vote_probs,
        'hit_vote_probs': hit_vote_probs_constrained,
        'hit_vote_probs_raw': hit_vote_probs_raw,
        # Hit transition categorization
        'hit_total': hit_transition_stats['hit_total'],
        'hit_promotions': hit_transition_stats['hit_promotions'],
        'hit_demotions': hit_transition_stats['hit_demotions'],
        'hit_stays': hit_transition_stats['hit_stays'],
        'hit_total_constrained': hit_transition_stats_constrained['hit_total'],
        'hit_promotions_constrained': hit_transition_stats_constrained['hit_promotions'],
        'hit_demotions_constrained': hit_transition_stats_constrained['hit_demotions'],
        'hit_stays_constrained': hit_transition_stats_constrained['hit_stays'],
        # Long reuse bias tracking
        'long_reuse_bias': long_reuse_bias,
    }


def train_pacipv_shadow_distilled_probabilistic(
    num_sets,
    num_ways,
    trace_loaders,
    *,
    max_rrpv=3,
    per_context=True,
):
    """
    Learn probabilistic PACIPV policy from shadow SRRIP votes.

    Output policy shape per context:
      {
        'insert_probs': [p(rrpv=0), ..., p(rrpv=max_rrpv)],
        'hit_transition_probs': [
            [p(s0->0), p(s0->1), ...],
            ...,
            [p(sN->0), ..., p(sN->N)]
        ]
      }
    """
    if not trace_loaders:
        raise ValueError('trace_loaders must not be empty')

    insert_votes = {
        CTX_DATA: [0] * (max_rrpv + 1),
        CTX_INST: [0] * (max_rrpv + 1),
    }
    hit_votes = {
        CTX_DATA: [[0] * (max_rrpv + 1) for _ in range(max_rrpv + 1)],
        CTX_INST: [[0] * (max_rrpv + 1) for _ in range(max_rrpv + 1)],
    }

    for loader in trace_loaders:
        trace_entries = loader()
        if not trace_entries:
            continue
        _accumulate_votes_from_trace(
            trace_entries,
            num_sets,
            num_ways,
            max_rrpv,
            per_context,
            insert_votes,
            hit_votes,
        )
        del trace_entries

    total_insert = sum(sum(v) for v in insert_votes.values())
    if total_insert == 0:
        raise ValueError('No usable training data found across all trace loaders')

    monotonic_hit_votes = {
        CTX_DATA: _constrain_hit_votes_monotonic(hit_votes[CTX_DATA], max_rrpv),
        CTX_INST: _constrain_hit_votes_monotonic(hit_votes[CTX_INST], max_rrpv),
    }

    policy_data = _build_probabilistic_policy(
        insert_votes[CTX_DATA], monotonic_hit_votes[CTX_DATA], max_rrpv
    )
    if per_context:
        policy_inst = _build_probabilistic_policy(
            insert_votes[CTX_INST], monotonic_hit_votes[CTX_INST], max_rrpv
        )
    else:
        policy_inst = policy_data

    policy_by_context = {
        CTX_DATA: policy_data,
        CTX_INST: policy_inst,
    }

    belady_rates = []
    pacipv_prob_rates = []
    for trace_idx, loader in enumerate(trace_loaders):
        trace_entries = loader()
        if not trace_entries:
            continue

        ptes = trace_entries_to_ptes(trace_entries)
        belady_rates.append(simulate_opt(num_sets, num_ways, ptes))
        del ptes

        pacipv_prob_rates.append(
            simulate_pacipv_probabilistic(
                num_sets,
                num_ways,
                trace_entries,
                policy_by_context,
                max_rrpv=max_rrpv,
                seed=trace_idx + 1,
            )
        )
        del trace_entries

    return {
        'max_rrpv': max_rrpv,
        'training_method': 'shadow_srrip_probabilistic_distillation',
        'per_context': bool(per_context),
        'ipv_distribution_by_context': policy_by_context,
        'insert_votes': insert_votes,
        'hit_votes_raw': hit_votes,
        'hit_votes_monotonic': monotonic_hit_votes,
        'insert_vote_probs': _normalize_votes(insert_votes, max_rrpv),
        'hit_vote_probs_raw': _normalize_hit_votes(hit_votes, max_rrpv),
        'hit_vote_probs_monotonic': _normalize_hit_votes(monotonic_hit_votes, max_rrpv),
        'avg_belady_rate': safe_mean(belady_rates),
        'avg_pacipv_prob_rate': safe_mean(pacipv_prob_rates),
    }


def save_pacipv_shadow_probabilistic_vectors(path, result):
    """Save probabilistic shadow-distilled PACIPV policy as JSON."""
    payload = {
        'max_rrpv': int(result['max_rrpv']),
        'training_method': result.get('training_method', 'shadow_srrip_probabilistic_distillation'),
        'per_context': bool(result.get('per_context', True)),
        'avg_belady_rate': float(result.get('avg_belady_rate', 0.0)),
        'avg_pacipv_prob_rate': float(result.get('avg_pacipv_prob_rate', 0.0)),
        'ipv_distribution_by_context': result['ipv_distribution_by_context'],
        'insert_vote_probs': result.get('insert_vote_probs', {}),
        'hit_vote_probs_monotonic': result.get('hit_vote_probs_monotonic', {}),
    }
    with open(path, 'w') as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(f"PACIPV shadow probabilistic vectors saved to {path}")


def load_pacipv_shadow_probabilistic_vectors(path, max_rrpv=3):
    with open(path, 'r') as f:
        payload = json.load(f)

    loaded_max_rrpv = int(payload.get('max_rrpv', max_rrpv))
    if loaded_max_rrpv != int(max_rrpv):
        raise ValueError(
            f"max_rrpv mismatch in '{path}': file has {loaded_max_rrpv}, expected {max_rrpv}"
        )

    policy = payload.get('ipv_distribution_by_context')
    if not isinstance(policy, dict):
        raise ValueError(f"No ipv_distribution_by_context found in '{path}'")

    data_policy = policy.get(CTX_DATA)
    inst_policy = policy.get(CTX_INST, data_policy)
    if data_policy is None or inst_policy is None:
        raise ValueError(f"Missing DATA/INST policies in '{path}'")

    return {
        'max_rrpv': loaded_max_rrpv,
        'training_method': payload.get('training_method', 'shadow_srrip_probabilistic_distillation'),
        'per_context': bool(payload.get('per_context', True)),
        'avg_belady_rate': float(payload.get('avg_belady_rate', 0.0)),
        'avg_pacipv_prob_rate': float(payload.get('avg_pacipv_prob_rate', 0.0)),
        'ipv_distribution_by_context': {
            CTX_DATA: data_policy,
            CTX_INST: inst_policy,
        },
        'insert_vote_probs': payload.get('insert_vote_probs', {}),
        'hit_vote_probs_monotonic': payload.get('hit_vote_probs_monotonic', {}),
    }


def save_pacipv_shadow_vectors(path, result):
    """
    Save PACIPV shadow-distilled vectors with comprehensive statistics.
    
    Outputs include:
    - Reuse distance analysis
    - Insert vote distributions (raw counts and probabilities)
    - Hit vote distributions (raw vs constrained, counts and probabilities)
    - Hit transition categorization (promotions/demotions/stays)
    - Long reuse bias analysis
    - Both original and constrained vectors for comparison
    """
    ipv_by_context = result.get('ipv_by_context', {CTX_DATA: result.get('ipv_vec'), CTX_INST: result.get('ipv_vec')})
    ipv_by_context_constrained = result.get('ipv_by_context_constrained', {})
    
    data_ipv_vec = ipv_by_context[CTX_DATA]
    inst_ipv_vec = ipv_by_context[CTX_INST]
    data_ipv_vec_constrained = ipv_by_context_constrained.get(CTX_DATA, data_ipv_vec)
    inst_ipv_vec_constrained = ipv_by_context_constrained.get(CTX_INST, inst_ipv_vec)
    
    max_rrpv = result['max_rrpv']
    data_ipv_str = ','.join(str(v) for v in data_ipv_vec)
    inst_ipv_str = ','.join(str(v) for v in inst_ipv_vec)
    data_ipv_str_constrained = ','.join(str(v) for v in data_ipv_vec_constrained)
    inst_ipv_str_constrained = ','.join(str(v) for v in inst_ipv_vec_constrained)
    
    thresholds = result.get('reuse_thresholds', {})
    insert_votes = result.get('insert_votes', {})
    insert_vote_probs = result.get('insert_vote_probs', {})
    hit_votes_raw = result.get('hit_votes_raw', {})
    hit_votes = result.get('hit_votes', {})
    hit_vote_probs_raw = result.get('hit_vote_probs_raw', {})
    hit_vote_probs = result.get('hit_vote_probs', {})
    hit_total = result.get('hit_total', {})
    hit_demotions = result.get('hit_demotions', {})
    hit_promotions = result.get('hit_promotions', {})
    hit_stays = result.get('hit_stays', {})
    hit_total_constrained = result.get('hit_total_constrained', {})
    hit_demotions_constrained = result.get('hit_demotions_constrained', {})
    hit_promotions_constrained = result.get('hit_promotions_constrained', {})
    hit_stays_constrained = result.get('hit_stays_constrained', {})
    long_reuse_bias = result.get('long_reuse_bias', {})
    reuse_stats = result.get('reuse_distance_stats', {})

    with open(path, 'w') as f:
        f.write('# Learned PACIPV shadow vector\n')
        f.write(f'# max_rrpv={max_rrpv}\n')
        if thresholds:
            f.write(f'# reuse_thresholds: T1={thresholds.get("t1")} T2={thresholds.get("t2")}\n')
        f.write(f'# avg_belady_rate={result["avg_belady_rate"]:.6f}\n')
        f.write(f'# avg_pacipv_rate={result["avg_pacipv_rate"]:.6f}\n')
        if 'avg_pacipv_rate_constrained' in result:
            f.write(f'# avg_pacipv_rate_constrained={result["avg_pacipv_rate_constrained"]:.6f}\n')
        f.write('\n')
        
        # Write reuse distance statistics
        if reuse_stats:
            f.write('# Reuse distance statistics\n')
            f.write(f'# Total accesses: {reuse_stats.get("total_accesses", 0)}\n')
            f.write(f'# Dead-on-arrival (state {max_rrpv}): {reuse_stats.get("dead_on_arrival_count", 0)} '
                    f'({reuse_stats.get("dead_on_arrival_ratio", 0)*100:.1f}%)\n')
            f.write(f'# Short-reuse (states 0-{max_rrpv-1}): {reuse_stats.get("short_reuse_count", 0)} '
                    f'({reuse_stats.get("short_reuse_ratio", 0)*100:.1f}%)\n')
            f.write('# Bucket distribution: ')
            f.write(', '.join(f's{i}={reuse_stats["bucket_counts"][i]}' 
                            for i in range(len(reuse_stats.get("bucket_counts", [])))))
            f.write('\n\n')

        # Insert vote distributions
        for ctx_name, ctx in [('inst', CTX_INST), ('data', CTX_DATA)]:
            f.write(f'# insert_votes_{ctx_name}={insert_votes.get(ctx, [])}\n')
            f.write(f'# insert_vote_probs_{ctx_name}={[round(v, 6) for v in insert_vote_probs.get(ctx, [])]}\n')

        f.write('\n')
        
        # Hit vote distributions - raw vs constrained
        for ctx_name, ctx in [('inst', CTX_INST), ('data', CTX_DATA)]:
            f.write(f'# hit_votes_raw_{ctx_name}\n')
            for old_state, row in enumerate(hit_votes_raw.get(ctx, [])):
                f.write(f'#   old={old_state} counts={row}\n')
            f.write(f'# hit_vote_probs_raw_{ctx_name}\n')
            for old_state, row in enumerate(hit_vote_probs_raw.get(ctx, [])):
                f.write(f'#   old={old_state} probs={[round(v, 6) for v in row]}\n')

            f.write(f'# hit_votes_clipped_{ctx_name}\n')
            for old_state, row in enumerate(hit_votes.get(ctx, [])):
                f.write(f'#   old={old_state} counts={row}\n')
            f.write(f'# hit_vote_probs_clipped_{ctx_name}\n')
            for old_state, row in enumerate(hit_vote_probs.get(ctx, [])):
                f.write(f'#   old={old_state} probs={[round(v, 6) for v in row]}\n')

            # Raw transition summary
            totals_raw = hit_total.get(ctx, [])
            demotions_raw = hit_demotions.get(ctx, [])
            promotions_raw = hit_promotions.get(ctx, [])
            stays_raw = hit_stays.get(ctx, [])
            f.write(f'# hit_transition_summary_raw_{ctx_name}\n')
            for old_state in range(len(totals_raw)):
                total = totals_raw[old_state]
                if total == 0:
                    f.write(f'#   old={old_state} total=0\n')
                    continue
                f.write(
                    '#   old={} total={} promote={:.6f} stay={:.6f} demote={:.6f}\n'.format(
                        old_state,
                        total,
                        promotions_raw[old_state] / total,
                        stays_raw[old_state] / total,
                        demotions_raw[old_state] / total,
                    )
                )
            
            # Constrained transition summary
            totals_constrained = hit_total_constrained.get(ctx, [])
            demotions_constrained = hit_demotions_constrained.get(ctx, [])
            promotions_constrained = hit_promotions_constrained.get(ctx, [])
            stays_constrained = hit_stays_constrained.get(ctx, [])
            f.write(f'# hit_transition_summary_clipped_{ctx_name}\n')
            for old_state in range(len(totals_constrained)):
                total = totals_constrained[old_state]
                if total == 0:
                    f.write(f'#   old={old_state} total=0\n')
                    continue
                f.write(
                    '#   old={} total={} promote={:.6f} stay={:.6f} demote={:.6f}\n'.format(
                        old_state,
                        total,
                        promotions_constrained[old_state] / total if total > 0 else 0,
                        stays_constrained[old_state] / total if total > 0 else 0,
                        demotions_constrained[old_state] / total if total > 0 else 0,
                    )
                )

        f.write('\n')
        
        # Long reuse bias summary
        if long_reuse_bias:
            for ctx_name, ctx in [('inst', CTX_INST), ('data', CTX_DATA)]:
                f.write(
                    f'# long_reuse_bias_{ctx_name}: '
                    f'insert_inf={long_reuse_bias.get("insert_inf_count", {}).get(ctx, 0)} '
                    f'insert_finite={long_reuse_bias.get("insert_finite_count", {}).get(ctx, 0)} '
                    f'hit_inf={long_reuse_bias.get("hit_inf_count", {}).get(ctx, 0)} '
                    f'hit_finite={long_reuse_bias.get("hit_finite_count", {}).get(ctx, 0)}\n'
                )

        # Output vectors
        f.write('\n')
        f.write(f'TXVC_PACIPV_INST_VEC={inst_ipv_str}\n')
        f.write(f'TXVC_PACIPV_DATA_VEC={data_ipv_str}\n')
        f.write(f'TXVC_PACIPV_DEMAND_VEC={data_ipv_str}\n')
        
        # Constrained versions
        if ipv_by_context_constrained:
            f.write('\n# Constrained vectors (hit transitions monotonic toward MRU)\n')
            f.write(f'TXVC_PACIPV_INST_VEC_CONSTRAINED={inst_ipv_str_constrained}\n')
            f.write(f'TXVC_PACIPV_DATA_VEC_CONSTRAINED={data_ipv_str_constrained}\n')
            f.write(f'TXVC_PACIPV_DEMAND_VEC_CONSTRAINED={data_ipv_str_constrained}\n')

        f.write('\n# Example usage\n')
        f.write('export TXVC_PACIPV_INST_VEC="' + inst_ipv_str + '"\n')
        f.write('export TXVC_PACIPV_DATA_VEC="' + data_ipv_str + '"\n')
        f.write('export TXVC_PACIPV_DEMAND_VEC="' + data_ipv_str + '"\n')
        f.write('export TXVC_REP_POLICY=pacipv\n')

    print(f"PACIPV shadow vectors saved to {path}")
