#!/usr/bin/env python3

import argparse
import json
import os
from collections import defaultdict, deque


def parse_prefetch_flag(raw_value):
    value = str(raw_value).strip().lower()
    return value in ("1", "true", "t", "yes", "y", "prefetch", "pf")


def load_trace_entries(path, has_prefetch=False, delimiter=",", address_col=0, prefetch_col=1):
    """Load a trace as (pte, is_prefetch) tuples.

    If has_prefetch is False, every entry is treated as demand.
    """
    entries = []
    with open(path, "r") as f:
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


def build_reuse_distance_map(trace):
    """Build pte -> [reuse distances] where the last access uses None for infinity."""
    future_positions = defaultdict(deque)
    for idx, pte in enumerate(trace):
        future_positions[pte].append(idx)

    reuse_distances_by_pte = defaultdict(list)

    for idx, pte in enumerate(trace):
        positions = future_positions[pte]
        if not positions:
            raise RuntimeError(f"Internal error: no recorded positions for pte={pte} at index={idx}")

        # Remove current occurrence.
        current = positions.popleft()
        if current != idx:
            raise RuntimeError(
                f"Internal error: position mismatch for pte={pte}; expected {idx}, got {current}"
            )

        # Next occurrence determines reuse distance.
        if positions:
            reuse_distance = positions[0] - idx
        else:
            reuse_distance = None

        reuse_distances_by_pte[pte].append(reuse_distance)

    return reuse_distances_by_pte


def summarize_reuse_distances(reuse_distances_by_pte):
    finite_values = []
    inf_count = 0
    total = 0

    for distances in reuse_distances_by_pte.values():
        total += len(distances)
        for value in distances:
            if value is None:
                inf_count += 1
            else:
                finite_values.append(value)

    finite_values.sort()
    median = None
    if finite_values:
        n = len(finite_values)
        mid = n // 2
        if n % 2 == 1:
            median = finite_values[mid]
        else:
            median = 0.5 * (finite_values[mid - 1] + finite_values[mid])

    return {
        "total_accesses": total,
        "unique_ptes": len(reuse_distances_by_pte),
        "finite_reuse_count": len(finite_values),
        "infinite_reuse_count": inf_count,
        "finite_reuse_median": median,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build a pte -> [reuse distances] map from a memory trace."
    )
    parser.add_argument("--trace-path", required=True, help="Input memory trace path")
    parser.add_argument(
        "--trace-has-prefetch",
        action="store_true",
        help="Interpret trace lines as multi-column records with a prefetch flag",
    )
    parser.add_argument(
        "--trace-delimiter",
        default=",",
        help="Delimiter for multi-column traces when --trace-has-prefetch is used",
    )
    parser.add_argument(
        "--trace-address-col",
        type=int,
        default=0,
        help="Column index for address/PTE in multi-column traces",
    )
    parser.add_argument(
        "--trace-prefetch-col",
        type=int,
        default=1,
        help="Column index for prefetch flag in multi-column traces",
    )
    parser.add_argument(
        "--output-file",
        default="data/belady_sweep/pte_reuse_distance_map.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--pretty-indent",
        type=int,
        default=2,
        help="JSON indentation (use 0 for compact)",
    )

    args = parser.parse_args()

    trace_entries = load_trace_entries(
        args.trace_path,
        has_prefetch=args.trace_has_prefetch,
        delimiter=args.trace_delimiter,
        address_col=args.trace_address_col,
        prefetch_col=args.trace_prefetch_col,
    )
    trace = trace_entries_to_ptes(trace_entries)
    if not trace:
        raise ValueError(f"Trace is empty: {args.trace_path}")

    reuse_distances_by_pte = build_reuse_distance_map(trace)
    summary = summarize_reuse_distances(reuse_distances_by_pte)

    payload = {
        "format": "pte_reuse_distance_map_v1",
        "trace_path": args.trace_path,
        "summary": summary,
        "note": "null means no future access (infinite reuse distance)",
        "reuse_distances_by_pte": dict(reuse_distances_by_pte),
    }

    output_dir = os.path.dirname(os.path.abspath(args.output_file))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    indent = args.pretty_indent if args.pretty_indent and args.pretty_indent > 0 else None
    with open(args.output_file, "w") as f:
        json.dump(payload, f, indent=indent, sort_keys=True)
        if indent is not None:
            f.write("\n")

    print(f"Trace entries: {len(trace)}")
    print(f"Unique PTEs: {summary['unique_ptes']}")
    print(f"Output written to {args.output_file}")


if __name__ == "__main__":
    main()
