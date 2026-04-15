import csv
import os
from collections import defaultdict

from cache_sim.lfu import lfu_ranked_ptes, lfu_victim


def simulate_opt(num_sets, num_ways, trace):
    """Return miss rate for the Belady/OPT algorithm."""
    positions = defaultdict(list)
    for idx, pte in enumerate(trace):
        positions[pte].append(idx)

    caches = [set() for _ in range(num_sets)]
    next_use_map = [dict() for _ in range(num_sets)]

    misses = 0
    for _, pte in enumerate(trace):
        set_id = hash(pte) % num_sets
        positions[pte].pop(0)
        future_idx = positions[pte][0] if positions[pte] else float('inf')

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


def build_belady_table(num_sets, num_ways, trace, feature_fn=None):
    """Run OPT to gather a mapping from features to victim ranks."""
    if feature_fn is None:
        feature_fn = lambda pte: pte

    positions = defaultdict(list)
    for idx, pte in enumerate(trace):
        positions[pte].append(idx)

    caches = [set() for _ in range(num_sets)]
    next_use_map = [dict() for _ in range(num_sets)]
    freq_map = [dict() for _ in range(num_sets)]
    rank_counts = defaultdict(lambda: defaultdict(int))

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

        feat = feature_fn(pte)
        rank_counts[feat][rank] += 1

        cache_set.remove(victim)
        del next_use_set[victim]
        del freq_map[set_id][victim]
        cache_set.add(pte)
        next_use_set[pte] = future_idx
        freq_map[set_id][pte] = 1

    table = {}
    for feat, counts in rank_counts.items():
        table[feat] = max(counts, key=counts.get)
    return table


def simulate_belady_table(num_sets, num_ways, trace, table, feature_fn=None):
    """Simulate a policy that consults *table* for victim rank decisions."""
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
                victim = lfu_victim(freq_map[set_id])
            else:
                sorted_pte = lfu_ranked_ptes(freq_map[set_id])
                r = min(victim_rank, len(sorted_pte) - 1)
                victim = sorted_pte[r]
            cache_set.remove(victim)
            del freq_map[set_id][victim]

            cache_set.add(pte)
            freq_map[set_id][pte] = 1

    return misses / len(trace)


def save_belady_table(path, table):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['feature', 'rank'])
        for feat in sorted(table.keys()):
            writer.writerow([feat, table[feat]])
    print(f"Belady table saved to {path}  ({len(table)} entries)")


def load_belady_table(path):
    table = {}
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            table[row['feature']] = int(row['rank'])
    print(f"Belady table loaded from {path}  ({len(table)} entries)")
    return table
