import csv
import os
import random
from collections import defaultdict

from cache_sim.lfu import lfu_ranked_ptes, lfu_victim


def collect_belady_rank_counts(num_sets, num_ways, trace):
    """Collect LFU-relative ranks of Belady victims from one trace."""
    positions = defaultdict(list)
    for idx, pte in enumerate(trace):
        positions[pte].append(idx)

    caches = [set() for _ in range(num_sets)]
    next_use_map = [dict() for _ in range(num_sets)]
    freq_map = [dict() for _ in range(num_sets)]

    per_set_counts = [defaultdict(int) for _ in range(num_sets)]
    global_counts = defaultdict(int)

    for _, pte in enumerate(trace):
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
    """Sample a victim rank from observed candidates."""
    if not counts:
        return None

    items = [(rank, cnt) for rank, cnt in counts.items() if 0 <= rank < num_ways and cnt > 0]
    if not items:
        return None

    items.sort(key=lambda x: (-x[1], x[0]))
    if top_k and top_k > 0:
        items = items[:top_k]

    if uniform:
        candidates = [rank for rank, _ in items]
        if not candidates:
            return None
        return rng.choice(candidates)

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
    """Simulate replacement using probabilistic Belady-rank sampling with LFU ordering."""
    rng = random.Random(seed)

    caches = [set() for _ in range(num_sets)]
    freq_map = [dict() for _ in range(num_sets)]

    misses = 0
    evictions = 0
    fallback_lfu = 0
    fallback_global = 0
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


def save_rank_model(path, per_set_counts, global_counts):
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
