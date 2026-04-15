def simulate_lfu_stack(num_sets, num_ways, trace):
    """Return miss rate for a simple LFU simulator using per-set frequency stacks."""
    caches = [dict() for _ in range(num_sets)]  # pte -> freq
    misses = 0
    for pte in trace:
        set_id = hash(pte) % num_sets
        cache = caches[set_id]
        if pte in cache:
            cache[pte] += 1
            continue

        misses += 1
        if len(cache) < num_ways:
            cache[pte] = 1
        else:
            victim = min(cache, key=cache.get)
            del cache[victim]
            cache[pte] = 1

    return misses / len(trace)


def lfu_ranked_ptes(freq_map_for_set):
    ranked = sorted(freq_map_for_set.items(), key=lambda item: (-item[1], str(item[0])))
    return [pte for pte, _ in ranked]


def lfu_victim(freq_map_for_set):
    ranked = lfu_ranked_ptes(freq_map_for_set)
    return ranked[-1]
