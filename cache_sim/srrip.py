"""
Vanilla SRRIP (Static RRIP)

Default behavior inserts at max_rrpv - 1 and promotes on hit.
"""

from collections import defaultdict


def simulate_vanilla_srrip(
    trace,
    num_sets,
    num_ways,
    insert_rrpv=None,
    hit_delta=1,
    max_rrpv=3,
):
    """
    Simulate vanilla SRRIP with fixed insertion RRPV.

    Args:
        trace: List of (set_id, address) tuples
        num_sets: Number of cache sets
        num_ways: Number of ways per set
        insert_rrpv: RRPV to insert new lines at (default: max_rrpv - 1)
        hit_delta: Decrement on hit (default: 1, promotes toward 0)
        max_rrpv: Maximum RRPV value (default: 3, so states 0-3)

    Returns:
        dict with keys:
            - misses: total miss count
            - hits: total hit count
            - miss_rate: misses / (hits + misses)
    """
    if insert_rrpv is None:
        insert_rrpv = max(0, max_rrpv - 1)
    insert_rrpv = max(0, min(max_rrpv, insert_rrpv))

    # Per-set cache state: {address -> rrpv}
    cache_state = defaultdict(lambda: defaultdict(int))

    hits = 0
    misses = 0

    for set_id, address in trace:
        cache_set = cache_state[set_id]

        if address in cache_set:
            # Hit: promote line toward 0
            hits += 1
            new_rrpv = cache_set[address] - hit_delta
            cache_set[address] = max(0, new_rrpv)
        else:
            # Miss: insert at insert_rrpv
            misses += 1

            if len(cache_set) < num_ways:
                # Set not full, just insert
                cache_set[address] = insert_rrpv
            else:
                # Set full: canonical SRRIP victim search with global aging.
                # Keep aging all lines until at least one line reaches max_rrpv.
                while True:
                    victim_addr = None
                    for addr, rrpv in cache_set.items():
                        if rrpv == max_rrpv:
                            victim_addr = addr
                            break
                    if victim_addr is not None:
                        break
                    for addr in list(cache_set.keys()):
                        cache_set[addr] = min(max_rrpv, cache_set[addr] + 1)

                del cache_set[victim_addr]
                cache_set[address] = insert_rrpv

    total_accesses = hits + misses
    miss_rate = misses / total_accesses if total_accesses > 0 else 0.0

    return {
        "misses": misses,
        "hits": hits,
        "miss_rate": miss_rate,
    }
