#!/usr/bin/env python3

import argparse
import numpy as np
import matplotlib.pyplot as plt
import workloads


# -----------------------------
# Fenwick Tree
# -----------------------------

class FenwickTree:
    def __init__(self, n):
        self.n = n
        self.tree = np.zeros(n + 1, dtype=np.int64)

    def update(self, i, delta):
        i += 1
        while i <= self.n:
            self.tree[i] += delta
            i += i & -i

    def query(self, i):
        s = 0
        i += 1
        while i > 0:
            s += self.tree[i]
            i -= i & -i
        return s

    def range_sum(self, l, r):
        return self.query(r) - self.query(l - 1)


# -----------------------------
# Trace utilities
# -----------------------------

# For memory efficiency we avoid keeping the entire trace in memory.
# Instead we process each file twice: first to count lines (so we can
# size the Fenwick tree) and then to stream through the addresses while
# updating reuse‑distance statistics on the fly.

# In the old code `load_trace` built a list of every address and the
# caller collected every reuse distance into a giant list.  For large
# traces those lists could consume gigabytes of RAM and eventually
# trigger the OOM killer.  The new helpers below only keep a small
# fixed‑size Fenwick tree, a dictionary of last positions, and a
# counter of reuse distances.


def count_lines(filename):
    """Return the number of non‑empty lines in *filename*."""
    n = 0
    with open(filename) as f:
        for _ in f:
            n += 1
    return n


def compute_reuse_distances_to_counter(filename, counter):
    """Read *filename* and update *counter* (a ``collections.Counter``)
    with reuse‑distance frequencies.

    The file is read twice: once for the line count so we can create a
    Fenwick tree of the correct size, and once to actually compute
    distances while streaming.  No intermediate list of traces or
    reuse distances is built, keeping peak memory constant.
    """

    n = count_lines(filename)
    fenwick = FenwickTree(n)
    last_pos = {}

    with open(filename) as f:
        for i, line in enumerate(f):
            addr = line.strip()
            if not addr:
                continue
            if addr in last_pos:
                prev = last_pos[addr]
                rd = fenwick.range_sum(prev + 1, i)
                counter[rd] += 1
                fenwick.update(prev, -1)
            fenwick.update(i, 1)
            last_pos[addr] = i


# -----------------------------
# Compute reuse distance
# -----------------------------

def compute_reuse_distance(trace):

    n = len(trace)

    fenwick = FenwickTree(n)

    last_pos = {}

    reuse_distances = []

    for i, addr in enumerate(trace):

        if addr in last_pos:

            prev = last_pos[addr]

            rd = fenwick.range_sum(prev + 1, i)

            reuse_distances.append(rd)

            fenwick.update(prev, -1)

        fenwick.update(i, 1)

        last_pos[addr] = i

    return reuse_distances


# MAIN 
parser = argparse.ArgumentParser()
parser.add_argument('--workload', default='selected_qualcomm_srv_ap',
                    help='Workload name to expand into benchmarks.')
parser.add_argument('--exp-name', default='TXVC-64KB',
                    help='Experiment name used in directory and filename construction.')
parser.add_argument('--data-dir', default='./data/txvc_mem_access',
                    help='Base directory containing trace subdirectories.')
parser.add_argument('--figures-dir', default='./figures',
                    help='Output directory for generated figures.')

if __name__ == "__main__":
    args = parser.parse_args()

    #------------------------------
    # Basic Configuration
    #------------------------------
    bench_suite = args.workload
    exp_name = args.exp_name
    data_dir = args.data_dir
    figures_dir = args.figures_dir

    # -----------------------------
    # Process multiple traces
    # -----------------------------
    workload = workloads.Workloads(bench_suite)
    benchmarks = workload.get_benchmark_names()

    trace_files = []
    for benchmark in benchmarks:
        trace_files.append(
            data_dir + '/' + exp_name + '/' + benchmark + '_' + exp_name + '_txvc_mem_trace.csv'
        )

    # Instead of collecting every reuse distance in a giant list we
    # tally them in a Counter to keep memory usage bounded.
    from collections import Counter

    reuse_counter = Counter()

    for trace_file in trace_files:
        print("Processing", trace_file)
        compute_reuse_distances_to_counter(trace_file, reuse_counter)

    total_samples = sum(reuse_counter.values())
    print("Samples:", total_samples)

    # For plotting we can use the keys/values directly rather than
    # expanding into a huge array.
    reuse_values = np.fromiter(reuse_counter.keys(), dtype=np.int64)
    reuse_counts = np.fromiter(reuse_counter.values(), dtype=np.int64)

    # -----------------------------
    # Histogram
    # -----------------------------
    plt.figure(figsize=(10, 6))
    plt.hist(
        reuse_values,
        bins=200,
        weights=reuse_counts,
        log=False,
    )
    plt.xlabel("Reuse Distance")
    plt.ylabel("Frequency (log)")
    plt.title("Reuse Distance Histogram")

    # Add VC size lines
    plt.axvline(x=1024, color='orange', linestyle='--', linewidth=2, label='VC 1024 entries')
    plt.axvline(x=2048, color='red', linestyle='--', linewidth=2, label='VC 2048 entries')

    output_file = figures_dir + '/' + bench_suite + '_' + exp_name + '_reuse_dist.pdf'
    plt.savefig(output_file, bbox_inches='tight')

    # -----------------------------
    # CDF
    # -----------------------------
    order = np.argsort(reuse_values)
    sorted_vals = reuse_values[order]
    sorted_counts = reuse_counts[order]
    cdf = np.cumsum(sorted_counts) / float(total_samples)

    plt.figure(figsize=(10, 6))
    plt.plot(sorted_vals, cdf)
    plt.xlabel("Reuse Distance")
    plt.ylabel("CDF")
    plt.title("Reuse Distance CDF")
    plt.grid(True)

    # Highlight VC sizes
    plt.axvline(x=1024, color='orange', linestyle='--', linewidth=2, label='VC 1024 entries')
    plt.axvline(x=2048, color='red', linestyle='--', linewidth=2, label='VC 2048 entries')

    output_file = figures_dir + '/' + bench_suite + '_' + exp_name + '_reuse_dist_cdf.pdf'
    plt.savefig(output_file, bbox_inches='tight')