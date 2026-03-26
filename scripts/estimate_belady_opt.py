#!/usr/bin/env python3

import argparse
import csv
from collections import defaultdict
import heapq
import itertools
import os
import random
import sys
import workloads




parser = argparse.ArgumentParser()
parser.add_argument('--train-workload', dest='train_workload', required=True,
                    help="Workload used to train the Belady rank model.")
parser.add_argument('--eval-workload', dest='eval_workload', required=True,
                    help="Workload to evaluate the replacement policies on.")
parser.add_argument('--num-sets', dest='num_sets', required=True, default=64, help="Number of sets in the cache.")
parser.add_argument('--num-ways', dest='num_ways', required=True, default=16, help="Number of ways in the cache.")
parser.add_argument('--prob-top-k', dest='prob_top_k', type=int, default=3,
                    help="Use only top-k most frequent Belady ranks for probabilistic policy (0 means all).")
parser.add_argument('--rank-model-scope', dest='rank_model_scope', choices=['per-set', 'global'],
                    default='per-set', help="Train rank-frequency model per set or globally.")
parser.add_argument('--seed', dest='seed', type=int, default=1,
                    help="Base random seed for probabilistic replacement simulation.")
parser.add_argument('--rank-sampling', dest='rank_sampling',
                    choices=['weighted', 'uniform-topk'], default='weighted',
                    help="Rank sampling mode: 'weighted' uses Belady frequency counts; "
                         "'uniform-topk' samples equally from the top-k candidates.")
parser.add_argument('--train-fraction', dest='train_fraction', type=float, default=1.0,
                    help="Fraction of each training trace to use (0.0-1.0). E.g. 0.1 uses first 10%%.")
parser.add_argument('--rank-model-file', dest='rank_model_file', default=None,
                    help="Path to a rank model CSV. If the file exists it is loaded (skipping "
                         "training); otherwise training runs and the model is saved here.")
parser.add_argument('--belady-table-dir', dest='belady_table_dir', default=None,
                    help="Directory for per-benchmark Belady tables (CSV). Each table is "
                         "auto-loaded if present, otherwise built and saved.")
parser.add_argument('--train-trace-path-template', dest='train_trace_path_template',
                default='./data/txvc_mem_access/TXVC-{num_sets}KB/{benchmark}_TXVC-{num_sets}KB_txvc_mem_trace.csv',
                help="Template path for training traces. Supports {benchmark} and {num_sets} placeholders.")
parser.add_argument('--eval-trace-path-template', dest='eval_trace_path_template',
                default='./data/txvc_mem_access/TXVC-{num_sets}KB/{benchmark}_TXVC-{num_sets}KB_txvc_mem_trace.csv',
                help="Template path for evaluation traces. Supports {benchmark} and {num_sets} placeholders.")
parser.add_argument('--trace-has-prefetch', dest='trace_has_prefetch', action='store_true',
                    help="Interpret trace lines as records that include a prefetch flag.")
parser.add_argument('--trace-delimiter', dest='trace_delimiter', default=',',
                    help="Delimiter for multi-column traces when --trace-has-prefetch is used.")
parser.add_argument('--trace-address-col', dest='trace_address_col', type=int, default=0,
                    help="Column index for address/PTE in multi-column traces.")
parser.add_argument('--trace-prefetch-col', dest='trace_prefetch_col', type=int, default=1,
                    help="Column index for prefetch flag in multi-column traces.")
parser.add_argument('--learn-pacipv-vectors', dest='learn_pacipv_vectors', action='store_true',
                    help="Learn PACIPV vectors from Belady-guided offline runs on training benchmarks.")
parser.add_argument('--pacipv-max-rrpv', dest='pacipv_max_rrpv', type=int, default=3,
                    help="Maximum RRPV value used for PACIPV vector search.")
parser.add_argument('--pacipv-learn-prefetch', dest='pacipv_learn_prefetch', action='store_true',
                    help="Also learn a separate prefetch PACIPV vector (requires --trace-has-prefetch).")
parser.add_argument('--pacipv-output-file', dest='pacipv_output_file', default='pacipv_vectors.txt',
                    help="Output text file with learned PACIPV vectors and ready-to-use env exports.")
parser.add_argument('--pacipv-train-max-accesses', dest='pacipv_train_max_accesses', type=int, default=0,
                    help="Optional cap of accesses per training benchmark for PACIPV vector learning (0 = no cap).")
parser.add_argument('--policies', dest='policies', default='belady,lfu,learned,prob_rank,pacipv,pacipv_lfu',
                    help="Comma-separated policies to run. Supported: belady,lfu,learned,prob_rank,pacipv,pacipv_lfu")



def simulate_opt(num_sets, num_ways, trace):
    """Return miss rate for the Belady/OPT algorithm.

    This is essentially the same logic that existed in the original
    __main__ body: build a list of future positions for each PTE and
    evict the line whose next use is farthest in the future.
    """
    # build future positions
    positions = defaultdict(list)  # PTE -> list of future access indices
    for idx, pte in enumerate(trace):
        positions[pte].append(idx)

    # per-set structures
    caches = [set() for _ in range(num_sets)]
    next_use_map = [dict() for _ in range(num_sets)]

    misses = 0
    for current_idx, pte in enumerate(trace):
        set_id = hash(pte) % num_sets
        # pop current access from future list
        positions[pte].pop(0)
        if positions[pte]:
            future_idx = positions[pte][0]
        else:
            future_idx = float('inf')

        cache_set = caches[set_id]
        next_use_set = next_use_map[set_id]

        if pte in cache_set:
            next_use_set[pte] = future_idx
            continue

        misses += 1
        if len(cache_set) < num_ways:
            cache_set.add(pte)
            next_use_set[pte] = future_idx
        else:
            farthest = max(next_use_set, key=lambda k: next_use_set[k])
            cache_set.remove(farthest)
            del next_use_set[farthest]
            cache_set.add(pte)
            next_use_set[pte] = future_idx

    return misses / len(trace)


def simulate_lfu_stack(num_sets, num_ways, trace):
    """Return miss rate for a simple LFU simulator using per-set frequency
    stacks.

    Each set keeps a map from PTE to access frequency.  On a hit the
    frequency is incremented; on a miss we either insert (if there is
    room) or evict the entry with the smallest frequency.  Ties are
    broken arbitrarily (the first encountered).

    This routine is intentionally simple; it does not attempt to maintain
    a complex priority structure, which would be necessary for extreme
    performance, but it still qualifies as a "stack-based" implementation
    because we only ever touch the per-set dictionary.
    """
    caches = [dict() for _ in range(num_sets)]  # pte -> freq
    misses = 0
    for pte in trace:
        set_id = hash(pte) % num_sets
        cache = caches[set_id]
        if pte in cache:
            cache[pte] += 1
            continue

        # miss
        misses += 1
        if len(cache) < num_ways:
            cache[pte] = 1
        else:
            # find least frequently used entry
            victim = min(cache, key=cache.get)
            del cache[victim]
            cache[pte] = 1

    return misses / len(trace)


def lfu_ranked_ptes(freq_map_for_set):
        """Return cache lines ordered by LFU rank.

        Rank convention used throughout this file:
            rank 0 = most frequently used
            rank (num_ways - 1) = least frequently used

        Ties are broken deterministically by the string form of the PTE so the
        learned rank mapping is stable across runs.
        """
        ranked = sorted(freq_map_for_set.items(), key=lambda item: (-item[1], str(item[0])))
        return [pte for pte, _ in ranked]


def lfu_victim(freq_map_for_set):
        ranked = lfu_ranked_ptes(freq_map_for_set)
        return ranked[-1]


def build_belady_table(num_sets, num_ways, trace, feature_fn=None):
    """Run OPT to gather a mapping from features to victim ranks.

    *feature_fn* is a callable that takes the incoming PTE (or any other
    information) and returns a hashable feature.  If not provided the raw
    PTE value is used (which may produce a very large table).  The table
    returned maps each feature to the rank (0..ways-1) that Belady chose
    most often when that feature appeared.

    Belady still chooses the victim using future knowledge, but the rank we
    store is that victim's position in an LFU ordering of the resident lines.
    This lets the learned table be consumed by an oracle-free LFU-ranked
    policy later.
    """
    if feature_fn is None:
        feature_fn = lambda pte: pte

    # use the same infrastructure as simulate_opt but record ranks
    positions = defaultdict(list)
    for idx, pte in enumerate(trace):
        positions[pte].append(idx)

    caches = [set() for _ in range(num_sets)]
    next_use_map = [dict() for _ in range(num_sets)]
    freq_map = [dict() for _ in range(num_sets)]

    # accumulate counts of ranks per feature
    rank_counts = defaultdict(lambda: defaultdict(int))

    for current_idx, pte in enumerate(trace):
        set_id = hash(pte) % num_sets
        positions[pte].pop(0)
        future_idx = positions[pte][0] if positions[pte] else float('inf')

        cache_set = caches[set_id]
        next_use_set = next_use_map[set_id]

        if pte in cache_set:
            next_use_set[pte] = future_idx
            freq_map[set_id][pte] += 1
            continue

        # miss – need to pick a victim if set is full
        if len(cache_set) < num_ways:
            cache_set.add(pte)
            next_use_set[pte] = future_idx
            freq_map[set_id][pte] = 1
            continue

        # victim chosen by Belady would be the one farthest in future
        victim = max(next_use_set, key=lambda k: next_use_set[k])
        rank = lfu_ranked_ptes(freq_map[set_id]).index(victim)

        feat = feature_fn(pte)
        rank_counts[feat][rank] += 1

        # perform the actual eviction/insertion so structure evolves
        cache_set.remove(victim)
        del next_use_set[victim]
        del freq_map[set_id][victim]
        cache_set.add(pte)
        next_use_set[pte] = future_idx
        freq_map[set_id][pte] = 1

    # choose the most common rank for each feature
    table = {}
    for feat, counts in rank_counts.items():
        table[feat] = max(counts, key=counts.get)
    return table


def simulate_belady_table(num_sets, num_ways, trace, table, feature_fn=None):
    """
    Simulate a policy that consults *table* for victim rank decisions.

    The table keys are features produced by *feature_fn* from the incoming
    block. Stored ranks are interpreted in LFU order, so rank 0 maps to the
    most frequently used resident line and rank (num_ways - 1) maps to the
    least frequently used one. If a feature is missing, the policy falls back
    to LFU eviction within the set.
    """
    if feature_fn is None:
        feature_fn = lambda pte: pte

    caches = [set() for _ in range(num_sets)]
    freq_map = [dict() for _ in range(num_sets)]

    misses = 0
    for pte in trace:
        set_id = hash(pte) % num_sets

        cache_set = caches[set_id]

        if pte in cache_set:
            freq_map[set_id][pte] += 1
            continue

        misses += 1
        if len(cache_set) < num_ways:
            cache_set.add(pte)
            freq_map[set_id][pte] = 1
        else:
            feat = feature_fn(pte)
            victim_rank = table.get(feat)
            if victim_rank is None:
                # fall back to LFU within this set
                victim = lfu_victim(freq_map[set_id])
            else:
                # pick element at that LFU rank
                sorted_pte = lfu_ranked_ptes(freq_map[set_id])
                # clamp rank to valid range
                r = min(victim_rank, len(sorted_pte) - 1)
                victim = sorted_pte[r]
            cache_set.remove(victim)
            del freq_map[set_id][victim]

            cache_set.add(pte)
            freq_map[set_id][pte] = 1

    return misses / len(trace)


def collect_belady_rank_counts(num_sets, num_ways, trace):
    """Collect LFU-relative ranks of Belady victims from one trace.

    Returns:
      per_set_counts: list[num_sets] of dict(rank -> count)
      global_counts: dict(rank -> count)
    """
    positions = defaultdict(list)
    for idx, pte in enumerate(trace):
        positions[pte].append(idx)

    caches = [set() for _ in range(num_sets)]
    next_use_map = [dict() for _ in range(num_sets)]
    freq_map = [dict() for _ in range(num_sets)]

    per_set_counts = [defaultdict(int) for _ in range(num_sets)]
    global_counts = defaultdict(int)

    for current_idx, pte in enumerate(trace):
        set_id = hash(pte) % num_sets
        positions[pte].pop(0)
        future_idx = positions[pte][0] if positions[pte] else float('inf')

        cache_set = caches[set_id]
        next_use_set = next_use_map[set_id]

        if pte in cache_set:
            next_use_set[pte] = future_idx
            freq_map[set_id][pte] += 1
            continue

        if len(cache_set) < num_ways:
            cache_set.add(pte)
            next_use_set[pte] = future_idx
            freq_map[set_id][pte] = 1
            continue

        victim = max(next_use_set, key=lambda k: next_use_set[k])
        rank = lfu_ranked_ptes(freq_map[set_id]).index(victim)

        per_set_counts[set_id][rank] += 1
        global_counts[rank] += 1

        cache_set.remove(victim)
        del next_use_set[victim]
        del freq_map[set_id][victim]
        cache_set.add(pte)
        next_use_set[pte] = future_idx
        freq_map[set_id][pte] = 1

    return per_set_counts, global_counts


def sample_rank_from_counts(counts, num_ways, rng, top_k=0, uniform=False):
    """Sample a victim rank from observed candidates.

    *uniform=False* (default): weighted sampling proportional to Belady counts.
    *uniform=True*: sample equally from the top-k candidates (stress-test mode).
    """
    if not counts:
        return None

    items = [(rank, cnt) for rank, cnt in counts.items() if 0 <= rank < num_ways and cnt > 0]
    if not items:
        return None

    items.sort(key=lambda x: (-x[1], x[0]))
    if top_k and top_k > 0:
        items = items[:top_k]

    if uniform:
        # uniform-topk: ignore frequencies, pick any surviving candidate equally
        candidates = [rank for rank, _ in items]
        if not candidates:
            return None
        return rng.choice(candidates)
    else:
        # weighted: sample proportional to observed Belady frequency counts
        total = sum(cnt for _, cnt in items)
        if total <= 0:
            return None
        draw = rng.uniform(0, total)
        running = 0
        for rank, cnt in items:
            running += cnt
            if draw <= running:
                return rank
        return items[-1][0]


def simulate_probabilistic_rank_policy(num_sets, num_ways, trace,
                                       per_set_rank_counts, global_rank_counts,
                                       top_k=0, seed=1, verbose=False, uniform=False):
    """Simulate replacement using probabilistic Belady-rank sampling with LFU ordering.

    The policy samples an eviction rank from learned frequency counts, then uses
    LFU-based ordering to map that rank to a concrete victim line. This is a
    practical, oracle-free policy suitable for hardware implementation.

    Ranking (based on frequency):
      rank 0 = most frequently used (best to keep)
      rank (num_ways-1) = least frequently used (best to evict by LFU)

    The policy uses per-set counts first (if provided), then global counts,
    and finally falls back to pure LFU when no rank statistics are available.
    """
    rng = random.Random(seed)

    caches = [set() for _ in range(num_sets)]
    freq_map = [dict() for _ in range(num_sets)]

    misses = 0
    evictions = 0
    fallback_lfu = 0
    fallback_global = 0
    for current_idx, pte in enumerate(trace):
        set_id = hash(pte) % num_sets
        cache_set = caches[set_id]

        if pte in cache_set:
            freq_map[set_id][pte] += 1
            continue

        misses += 1
        if len(cache_set) < num_ways:
            cache_set.add(pte)
            freq_map[set_id][pte] = 1
            continue

        evictions += 1

        rank = None
        if per_set_rank_counts is not None:
            rank = sample_rank_from_counts(per_set_rank_counts[set_id], num_ways, rng, top_k=top_k, uniform=uniform)
        if rank is None:
            rank = sample_rank_from_counts(global_rank_counts, num_ways, rng, top_k=top_k, uniform=uniform)
            if rank is not None:
                fallback_global += 1

        if rank is None:
            victim = lfu_victim(freq_map[set_id])
            fallback_lfu += 1
        else:
            sorted_pte = lfu_ranked_ptes(freq_map[set_id])
            victim = sorted_pte[min(rank, len(sorted_pte) - 1)]

        cache_set.remove(victim)
        del freq_map[set_id][victim]

        cache_set.add(pte)
        freq_map[set_id][pte] = 1

    if verbose:
        print(f"  evictions: {evictions}  fallback-to-global: {fallback_global}  fallback-to-LFU: {fallback_lfu}")

    return misses / len(trace)


# ---------------------------------------------------------------------------
# Serialization helpers  (CSV-based so the files are easy to read in C++)
# ---------------------------------------------------------------------------

def save_rank_model(path, per_set_counts, global_counts):
    """Persist the probabilistic rank model to a CSV file.

    Columns: set_id, rank, count
    set_id == -1 encodes the global (across-all-sets) histogram.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['set_id', 'rank', 'count'])
        for rank in sorted(global_counts):
            writer.writerow([-1, rank, global_counts[rank]])
        for set_id, counts in enumerate(per_set_counts):
            for rank in sorted(counts):
                writer.writerow([set_id, rank, counts[rank]])
    print(f"Rank model saved to {path}")


def load_rank_model(path, num_sets):
    """Load a rank model previously saved with save_rank_model.

    Returns (per_set_counts, global_counts) with the same types used during
    training (list of defaultdict(int), defaultdict(int)).
    """
    per_set_counts = [defaultdict(int) for _ in range(num_sets)]
    global_counts = defaultdict(int)
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            set_id = int(row['set_id'])
            rank = int(row['rank'])
            cnt = int(row['count'])
            if set_id == -1:
                global_counts[rank] += cnt
            elif 0 <= set_id < num_sets:
                per_set_counts[set_id][rank] += cnt
    print(f"Rank model loaded from {path}")
    return per_set_counts, global_counts


def save_belady_table(path, table):
    """Persist a {feature -> rank} Belady table to a CSV file.

    Columns: feature, rank
    'feature' is the raw PTE value (or whatever hash was used); 'rank' is
    the majority-vote Belady eviction rank for that feature.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['feature', 'rank'])
        for feat in sorted(table.keys()):
            writer.writerow([feat, table[feat]])
    print(f"Belady table saved to {path}  ({len(table)} entries)")


def load_belady_table(path):
    """Load a Belady table previously saved with save_belady_table.

    Returns a plain dict {feature_str -> int rank}.
    The feature key is returned as a string (matching what feature_fn
    produces when pte values are strings from the trace).
    """
    table = {}
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            table[row['feature']] = int(row['rank'])
    print(f"Belady table loaded from {path}  ({len(table)} entries)")
    return table


def safe_mean(values):
    if not values:
        return float('nan')
    return sum(values) / len(values)


def render_trace_path(path_template, benchmark, num_sets):
    """Render one trace path from a CLI template.

    Supported placeholders are {benchmark} and {num_sets}.  We fail fast
    with a clear error if unsupported or malformed placeholders are used.
    """
    try:
        return path_template.format(benchmark=benchmark, num_sets=num_sets)
    except KeyError as exc:
        raise ValueError(
            f"Invalid placeholder in trace template '{path_template}': {exc}. "
            "Supported placeholders: {benchmark}, {num_sets}."
        ) from exc


def parse_prefetch_flag(raw_value):
    value = str(raw_value).strip().lower()
    return value in ('1', 'true', 't', 'yes', 'y', 'prefetch', 'pf')


def load_trace_entries(path, has_prefetch=False, delimiter=',', address_col=0, prefetch_col=1):
    """Load a trace as (pte, is_prefetch) tuples.

    If has_prefetch is False, every entry is treated as demand.
    """
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if not has_prefetch:
                entries.append((line, False))
                continue

            cols = [c.strip() for c in line.split(delimiter)]
            if address_col >= len(cols):
                continue

            pte = cols[address_col]
            pf = False
            if prefetch_col < len(cols):
                pf = parse_prefetch_flag(cols[prefetch_col])
            entries.append((pte, pf))

    return entries


def trace_entries_to_ptes(trace_entries):
    return [pte for pte, _ in trace_entries]


def default_ipv_vector(max_rrpv):
    one = min(1, max_rrpv)
    return (0, one, one, 0, max_rrpv)


def clamp_ipv_vector(vec, max_rrpv):
    return tuple(max(0, min(max_rrpv, int(v))) for v in vec)


def simulate_pacipv(num_sets, num_ways, trace_entries, ipv_vec, max_rrpv=3):
    """Simulate PACIPV with one IPV used for all accesses."""
    ipv_vec = clamp_ipv_vector(ipv_vec, max_rrpv)

    sets = [dict() for _ in range(num_sets)]  # pte -> rrpv
    misses = 0

    for pte, _ in trace_entries:
        set_id = hash(pte) % num_sets
        cache = sets[set_id]

        if pte in cache:
            old_rrpv = max(0, min(max_rrpv, cache[pte]))
            cache[pte] = max(0, min(max_rrpv, ipv_vec[old_rrpv]))
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

        cache[pte] = max(0, min(max_rrpv, ipv_vec[4]))

    return misses / len(trace_entries)


def simulate_pacipv_lfu(num_sets, num_ways, trace_entries, ipv_vec, max_rrpv=3):
    """Simulate PACIPV_LFU with one IPV used for all accesses."""
    ipv_vec = clamp_ipv_vector(ipv_vec, max_rrpv)

    sets = [dict() for _ in range(num_sets)]  # pte -> freq_bucket
    misses = 0

    for pte, _ in trace_entries:
        set_id = hash(pte) % num_sets
        cache = sets[set_id]

        if pte in cache:
            old_freq = max(0, min(max_rrpv, cache[pte]))
            old_rrpv = max_rrpv - old_freq
            new_rrpv = max(0, min(max_rrpv, ipv_vec[old_rrpv]))
            cache[pte] = max_rrpv - new_rrpv
            continue

        misses += 1

        if len(cache) >= num_ways:
            victim = min(cache, key=lambda k: (cache[k], str(k)))
            del cache[victim]

        ins_rrpv = max(0, min(max_rrpv, ipv_vec[4]))
        cache[pte] = max_rrpv - ins_rrpv

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
    # Demand-only PACIPV search space:
    #   1. No demotion on hit: h_i <= i for every RRPV state i.
    #   2. Reachability: insertion, hit transitions, and aging must be able to
    #      visit every recency state in [0, max_rrpv].
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
    """Memory-efficient PACIPV learning: loads one trace at a time.

    trace_loaders: list of callables, each returning trace_entries for one benchmark.
    """
    candidates = all_ipv_vectors(max_rrpv)

    candidate_sums = [0.0] * len(candidates)
    for loader in trace_loaders:
        trace = loader()
        for i, cand in enumerate(candidates):
            candidate_sums[i] += simulate_pacipv(num_sets, num_ways, trace, cand, max_rrpv)
        del trace

    best_ipv = candidates[candidate_sums.index(min(candidate_sums))]

    # Final stats: one trace at a time.
    pacipv_rates, pacipv_lfu_rates, belady_rates = [], [], []
    for loader in trace_loaders:
        trace = loader()
        pacipv_rates.append(simulate_pacipv(num_sets, num_ways, trace, best_ipv, max_rrpv))
        pacipv_lfu_rates.append(simulate_pacipv_lfu(num_sets, num_ways, trace, best_ipv, max_rrpv))
        belady_rates.append(simulate_opt(num_sets, num_ways, trace_entries_to_ptes(trace)))
        del trace

    return {
        'ipv_vec': tuple(best_ipv),
        'max_rrpv': max_rrpv,
        'num_candidates': len(candidates),
        'avg_belady_rate': safe_mean(belady_rates),
        'avg_pacipv_rate': safe_mean(pacipv_rates),
        'avg_pacipv_lfu_rate': safe_mean(pacipv_lfu_rates),
    }


def save_pacipv_vectors(path, result):
    ipv_vec = result['ipv_vec']
    max_rrpv = result['max_rrpv']
    ipv_str = ','.join(str(v) for v in ipv_vec)

    with open(path, 'w') as f:
        f.write('# Learned PACIPV vector\n')
        f.write(f'# max_rrpv={max_rrpv}\n')
        f.write(f'# num_candidates={result["num_candidates"]}\n')
        f.write(f'# avg_belady_rate={result["avg_belady_rate"]:.6f}\n')
        f.write(f'# avg_pacipv_rate={result["avg_pacipv_rate"]:.6f}\n')
        f.write(f'# avg_pacipv_lfu_rate={result["avg_pacipv_lfu_rate"]:.6f}\n\n')
        f.write(f'TXVC_PACIPV_DEMAND_VEC={ipv_str}\n\n')
        f.write('# Example usage\n')
        f.write('export TXVC_PACIPV_DEMAND_VEC="' + ipv_str + '"\n')
        f.write('export TXVC_REP_POLICY=pacipv\n')
        f.write('# or\n')
        f.write('export TXVC_REP_POLICY=pacipv_lfu\n')

    print(f"PACIPV vectors saved to {path}")


def parse_policy_list(policy_str):
    supported = ['belady', 'lfu', 'learned', 'prob_rank', 'pacipv', 'pacipv_lfu']
    selected = [p.strip() for p in policy_str.split(',') if p.strip()]
    invalid = [p for p in selected if p not in supported]
    if invalid:
        raise ValueError(
            f"Unsupported policies: {invalid}. Supported policies: {supported}"
        )
    if not selected:
        raise ValueError("No policies selected. Use --policies with at least one valid policy.")
    return selected


if __name__ == "__main__":
    args = parser.parse_args()
    num_sets = int(args.num_sets)
    num_ways = int(args.num_ways)
    train_fraction = max(0.0, min(1.0, args.train_fraction))

    selected_policies = parse_policy_list(args.policies)
    run_belady = 'belady' in selected_policies
    run_lfu = 'lfu' in selected_policies
    run_learned = 'learned' in selected_policies
    run_prob_rank = 'prob_rank' in selected_policies
    run_pacipv = 'pacipv' in selected_policies
    run_pacipv_lfu = 'pacipv_lfu' in selected_policies

    train_workload = workloads.Workloads(args.train_workload)
    train_benchmarks = train_workload.get_benchmark_names()
    eval_workload = workloads.Workloads(args.eval_workload)
    eval_benchmarks = eval_workload.get_benchmark_names()

    uniform_sampling = (args.rank_sampling == 'uniform-topk')
    # Demand-IPV-only learning mode.
    if args.pacipv_learn_prefetch:
        print("Ignoring --pacipv-learn-prefetch: sweep is configured to learn demand IPV only.")

    if (run_pacipv or run_pacipv_lfu) and not args.learn_pacipv_vectors:
        print("PACIPV policy selected; enabling --learn-pacipv-vectors automatically.")
        args.learn_pacipv_vectors = True
    if not (run_pacipv or run_pacipv_lfu) and args.learn_pacipv_vectors:
        print("Ignoring --learn-pacipv-vectors because neither pacipv nor pacipv_lfu was selected.")
        args.learn_pacipv_vectors = False

    # ------------------------------------------------------------------
    # Rank model: load from file or train from scratch
    # ------------------------------------------------------------------
    train_per_set_counts = [defaultdict(int) for _ in range(num_sets)]
    train_global_counts = defaultdict(int)
    rank_model_path = args.rank_model_file
    if run_prob_rank:
        if rank_model_path and os.path.exists(rank_model_path):
            train_per_set_counts, train_global_counts = load_rank_model(rank_model_path, num_sets)
        else:
            print(
                f"Training probabilistic rank model on '{args.train_workload}' "
                f"(fraction={train_fraction:.2f}, scope={args.rank_model_scope}, "
                f"top_k={args.prob_top_k}, sampling={args.rank_sampling})"
            )

            for benchmark in train_benchmarks:
                trace_path = render_trace_path(args.train_trace_path_template, benchmark, args.num_sets)
                trace_entries = load_trace_entries(
                    trace_path,
                    has_prefetch=args.trace_has_prefetch,
                    delimiter=args.trace_delimiter,
                    address_col=args.trace_address_col,
                    prefetch_col=args.trace_prefetch_col,
                )
                trace = trace_entries_to_ptes(trace_entries)
                if train_fraction < 1.0:
                    trace = trace[:max(1, int(len(trace) * train_fraction))]

                per_set_counts, global_counts = collect_belady_rank_counts(num_sets, num_ways, trace)
                if args.rank_model_scope == 'per-set':
                    for set_id in range(num_sets):
                        for rank, cnt in per_set_counts[set_id].items():
                            train_per_set_counts[set_id][rank] += cnt
                for rank, cnt in global_counts.items():
                    train_global_counts[rank] += cnt

            if rank_model_path:
                save_rank_model(rank_model_path, train_per_set_counts, train_global_counts)

    pacipv_result = None

    # ------------------------------------------------------------------
    # Learn PACIPV vectors from training traces (optional)
    # ------------------------------------------------------------------
    if args.learn_pacipv_vectors:
        def _make_loader(benchmark):
            def _loader():
                te = load_trace_entries(
                    render_trace_path(args.train_trace_path_template, benchmark, args.num_sets),
                    has_prefetch=args.trace_has_prefetch,
                    delimiter=args.trace_delimiter,
                    address_col=args.trace_address_col,
                    prefetch_col=args.trace_prefetch_col,
                )
                if train_fraction < 1.0:
                    te = te[:max(1, int(len(te) * train_fraction))]
                if args.pacipv_train_max_accesses > 0:
                    te = te[:args.pacipv_train_max_accesses]
                return te
            return _loader

        # Validate each benchmark has a non-empty trace (check once, discard data).
        trace_loaders = []
        for benchmark in train_benchmarks:
            loader = _make_loader(benchmark)
            te = loader()
            if te:
                trace_loaders.append(loader)
            del te

        if not trace_loaders:
            print("No training traces found for PACIPV learning.")
            sys.exit(1)

        pacipv_result = learn_pacipv_vectors(
            num_sets,
            num_ways,
            trace_loaders,
            max_rrpv=args.pacipv_max_rrpv,
        )
        save_pacipv_vectors(args.pacipv_output_file, pacipv_result)
        print(
            f"Learned PACIPV vector {pacipv_result['ipv_vec']} "
            f"from {pacipv_result['num_candidates']} candidates"
        )

    # print global rank histogram only when prob_rank is enabled
    if run_prob_rank:
        total_evictions = sum(train_global_counts.values())
        if total_evictions > 0:
            print(f"\nGlobal Belady rank histogram (total evictions: {total_evictions}):")
            print(f"  {'rank':>6}  {'count':>10}  {'%':>7}")
            for rank in sorted(train_global_counts):
                cnt = train_global_counts[rank]
                print(f"  {rank:>6}  {cnt:>10}  {100*cnt/total_evictions:>6.2f}%")
            empty_per_set = sum(1 for s in train_per_set_counts if not s)
            print(f"  (per-set model: {num_sets - empty_per_set}/{num_sets} sets have data)\n")

    print(f"Evaluating on '{args.eval_workload}' ({len(eval_benchmarks)} benchmarks)\n")

    # prepare storage for results as a dict of lists (columns)
    results = {'benchmark': []}
    metric_by_policy = {
        'belady': 'belady_rate',
        'lfu': 'lfu_rate',
        'learned': 'learned_rate',
        'prob_rank': 'prob_rank_rate',
        'pacipv': 'pacipv_rate',
        'pacipv_lfu': 'pacipv_lfu_rate',
    }
    for policy in selected_policies:
        results[metric_by_policy[policy]] = []

    # choose a simple feature extractor; users can modify as needed
    # here we just take the PTE value itself, but in a real experiment this
    # might include PC, page-level bits, frequency, etc.
    feature_fn = lambda pte: pte

    per_set_model = train_per_set_counts if args.rank_model_scope == 'per-set' else None

    for bench_idx, benchmark in enumerate(eval_benchmarks):
        print(f"Processing benchmark: {benchmark}")

        trace_path = render_trace_path(args.eval_trace_path_template, benchmark, args.num_sets)
        trace_entries = load_trace_entries(
            trace_path,
            has_prefetch=args.trace_has_prefetch,
            delimiter=args.trace_delimiter,
            address_col=args.trace_address_col,
            prefetch_col=args.trace_prefetch_col,
        )
        trace = trace_entries_to_ptes(trace_entries)

        belady_rate = simulate_opt(num_sets, num_ways, trace) if run_belady else float('nan')
        lfu_rate = simulate_lfu_stack(num_sets, num_ways, trace) if run_lfu else float('nan')

        # ------------------------------------------------------------------
        # Per-benchmark Belady table: load from file or build and save
        # ------------------------------------------------------------------
        learned_rate = float('nan')
        if run_learned:
            if args.belady_table_dir:
                table_path = os.path.join(
                    args.belady_table_dir,
                    f"{benchmark}_TXVC-{args.num_sets}KB_belady_table.csv"
                )
                if os.path.exists(table_path):
                    table = load_belady_table(table_path)
                else:
                    table = build_belady_table(num_sets, num_ways, trace, feature_fn=feature_fn)
                    os.makedirs(args.belady_table_dir, exist_ok=True)
                    save_belady_table(table_path, table)
            else:
                table = build_belady_table(num_sets, num_ways, trace, feature_fn=feature_fn)

            learned_rate = simulate_belady_table(num_sets, num_ways, trace, table, feature_fn=feature_fn)

        prob_rank_rate = float('nan')
        if run_prob_rank:
            prob_rank_rate = simulate_probabilistic_rank_policy(
                num_sets,
                num_ways,
                trace,
                per_set_model,
                train_global_counts,
                top_k=args.prob_top_k,
                seed=args.seed + bench_idx,
                verbose=True,
                uniform=uniform_sampling,
            )

        pacipv_rate = float('nan')
        pacipv_lfu_rate = float('nan')
        if pacipv_result is not None and (run_pacipv or run_pacipv_lfu):
            pacipv_rate = simulate_pacipv(
                num_sets,
                num_ways,
                trace_entries,
                pacipv_result['ipv_vec'],
                max_rrpv=pacipv_result['max_rrpv'],
            ) if run_pacipv else float('nan')
            pacipv_lfu_rate = simulate_pacipv_lfu(
                num_sets,
                num_ways,
                trace_entries,
                pacipv_result['ipv_vec'],
                max_rrpv=pacipv_result['max_rrpv'],
            ) if run_pacipv_lfu else float('nan')

        metric_parts = [f"total accesses: {len(trace)}"]
        if run_belady:
            metric_parts.append(f"belady misses: {belady_rate:.3f}")
        if run_lfu:
            metric_parts.append(f"lfu misses: {lfu_rate:.3f}")
        if run_learned:
            metric_parts.append(f"learned misses: {learned_rate:.3f}")
        if run_prob_rank:
            metric_parts.append(f"prob-rank misses: {prob_rank_rate:.3f}")
        if run_pacipv:
            metric_parts.append(f"pacipv misses: {pacipv_rate:.3f}")
        if run_pacipv_lfu:
            metric_parts.append(f"pacipv-lfu misses: {pacipv_lfu_rate:.3f}")
        print(', '.join(metric_parts))

        results['benchmark'].append(benchmark)
        if run_belady:
            results['belady_rate'].append(belady_rate)
        if run_lfu:
            results['lfu_rate'].append(lfu_rate)
        if run_learned:
            results['learned_rate'].append(learned_rate)
        if run_prob_rank:
            results['prob_rank_rate'].append(prob_rank_rate)
        if run_pacipv:
            results['pacipv_rate'].append(pacipv_rate)
        if run_pacipv_lfu:
            results['pacipv_lfu_rate'].append(pacipv_lfu_rate)

    if run_belady:
        print(f"Average belady rate: {safe_mean(results['belady_rate']):.4f}")
    if run_lfu:
        print(f"Average lfu rate:    {safe_mean(results['lfu_rate']):.4f}")
    if run_learned:
        print(f"Average learned rate: {safe_mean(results['learned_rate']):.4f}")
    if run_prob_rank:
        print(f"Average prob-rank rate: {safe_mean(results['prob_rank_rate']):.4f}")
    if run_pacipv:
        print(f"Average pacipv rate: {safe_mean(results['pacipv_rate']):.4f}")
    if run_pacipv_lfu:
        print(f"Average pacipv-lfu rate: {safe_mean(results['pacipv_lfu_rate']):.4f}")
    if run_prob_rank and run_belady:
        gaps = [p - b for p, b in zip(results['prob_rank_rate'], results['belady_rate'])]
        print(f"Avg gap (prob-rank - belady): {safe_mean(gaps):.4f}")

    frac_tag = f"{train_fraction:.3f}".replace('.', 'p')
    output_csv = (
        f"cache_miss_rates_train.{args.train_workload}_eval.{args.eval_workload}_"
        f"s{args.num_sets}_w{args.num_ways}_scope.{args.rank_model_scope}_"
        f"topk.{args.prob_top_k}_sampling.{args.rank_sampling}_frac.{frac_tag}_seed.{args.seed}.csv"
    )
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        metric_columns = [metric_by_policy[p] for p in selected_policies]
        writer.writerow(['benchmark'] + metric_columns)
        for i in range(len(results['benchmark'])):
            row = [results['benchmark'][i]]
            for col in metric_columns:
                row.append(results[col][i])
            writer.writerow(row)
    print(f"Results saved to {output_csv}")
