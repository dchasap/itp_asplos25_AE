#!/usr/bin/env python3

import argparse
import csv
from collections import defaultdict
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'scripts')

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import workloads

from cache_sim.belady import (
    build_belady_table,
    load_belady_table,
    save_belady_table,
    simulate_belady_table,
    simulate_opt,
)
from cache_sim.constants import CTX_DATA, CTX_INST
from cache_sim.lfu import simulate_lfu_stack
from cache_sim.pacipv import (
    learn_pacipv_vectors,
    save_pacipv_vectors,
    simulate_pacipv_distribution,
    simulate_pacipv,
    simulate_pacipv_probabilistic,
)
from cache_sim.pacipv_shadow_distill import (
    load_pacipv_shadow_probabilistic_vectors,
    load_pacipv_shadow_vectors,
    save_pacipv_shadow_probabilistic_vectors,
    save_pacipv_shadow_vectors,
    train_pacipv_shadow_distilled_probabilistic,
    train_pacipv_shadow_distilled,
)
from cache_sim.opt_distilled_srrip import (
    load_opt_distilled_srrip,
    save_opt_distilled_srrip,
    simulate_opt_distilled_srrip,
    train_opt_distilled_srrip,
)
from cache_sim.srrip import (
    simulate_vanilla_srrip,
)
from cache_sim.prob_rank import (
    collect_belady_rank_counts,
    load_rank_model,
    save_rank_model,
    simulate_probabilistic_rank_policy,
)
from cache_sim.trace import load_trace_entries, render_trace_path, trace_entries_to_ptes
from cache_sim.utils import safe_mean




parser = argparse.ArgumentParser()
parser.add_argument('--train-workload', dest='train_workload', default=None,
                    help="Workload used to train the Belady rank model.")
parser.add_argument('--eval-workload', dest='eval_workload', required=True,
                    help="Workload to evaluate the replacement policies on.")
parser.add_argument('--num-sets', dest='num_sets', required=True, default=64, help="Number of sets in the cache.")
parser.add_argument('--num-ways', dest='num_ways', required=True, default=16, help="Number of ways in the cache.")
parser.add_argument('--prob-top-k', dest='prob_top_k', type=int, default=None,
                    help="Use only top-k most frequent Belady ranks for probabilistic policy (0 means all).")
parser.add_argument('--rank-model-scope', dest='rank_model_scope', choices=['per-set', 'global'],
                default=None, help="Train rank-frequency model per set or globally.")
parser.add_argument('--seed', dest='seed', type=int, default=None,
                    help="Base random seed for probabilistic replacement simulation.")
parser.add_argument('--rank-sampling', dest='rank_sampling',
                choices=['weighted', 'uniform-topk'], default=None,
                    help="Rank sampling mode: 'weighted' uses Belady frequency counts; "
                         "'uniform-topk' samples equally from the top-k candidates.")
parser.add_argument('--train-fraction', dest='train_fraction', type=float, default=None,
                    help="Fraction of each training trace to use (0.0-1.0). E.g. 0.1 uses first 10%%.")
parser.add_argument('--rank-model-file', dest='rank_model_file', default=None,
                    help="Path to a rank model CSV. If the file exists it is loaded (skipping "
                         "training); otherwise training runs and the model is saved here.")
parser.add_argument('--belady-table-dir', dest='belady_table_dir', default=None,
                    help="Directory for per-benchmark Belady tables (CSV). Each table is "
                         "auto-loaded if present, otherwise built and saved.")
parser.add_argument('--train-trace-path-template', dest='train_trace_path_template',
                default='./data/txvc_mem_access/TXVC-{num_sets}KB/{benchmark}_txvc_mem_trace.csv',
                help="Template path for training traces. Supports {benchmark} and {num_sets} placeholders.")
parser.add_argument('--eval-trace-path-template', dest='eval_trace_path_template',
                default='./data/txvc_mem_access/TXVC-{num_sets}KB/{benchmark}_txvc_mem_trace.csv',
                help="Template path for evaluation traces. Supports {benchmark} and {num_sets} placeholders.")
parser.add_argument('--learn-pacipv-vectors', dest='learn_pacipv_vectors', action='store_true',
                    help="Learn PACIPV vectors from Belady-guided offline runs on training benchmarks.")
parser.add_argument('--pacipv-max-rrpv', dest='pacipv_max_rrpv', type=int, default=3,
                    help="Maximum RRPV value used for PACIPV vector search.")
parser.add_argument('--pacipv-learn-prefetch', dest='pacipv_learn_prefetch', action='store_true',
                    help="Also learn a separate prefetch PACIPV vector (currently ignored).")
parser.add_argument('--pacipv-vectors-file', '--pacipv-output-file', dest='pacipv_output_file', default=None,
                    help="Output text file with learned PACIPV vectors and ready-to-use env exports.")
parser.add_argument('--pacipv-demand-vector', dest='pacipv_demand_vector', default=None,
                help="Hardcoded PACIPV demand vector as comma-separated ints, e.g. 0,1,1,0,3. "
                    "When provided, PACIPV evaluation uses this vector directly instead of learning one.")
parser.add_argument('--pacipv-train-max-accesses', dest='pacipv_train_max_accesses', type=int, default=0,
                    help="Optional cap of accesses per training benchmark for PACIPV vector learning (0 = no cap).")
parser.add_argument('--pacipv-train-per-benchmark', dest='pacipv_train_per_benchmark', action='store_true',
                    help="Train a separate exhaustive PACIPV vector per benchmark and evaluate each benchmark with its own learned vector.")
parser.add_argument('--learn-pacipv-shadow', dest='learn_pacipv_shadow', action='store_true',
                    help="Learn PACIPV vector by Belady-guided shadow SRRIP state distillation.")
parser.add_argument('--pacipv-shadow-max-rrpv', dest='pacipv_shadow_max_rrpv', type=int, default=3,
                    help="Maximum RRPV used for PACIPV shadow distillation (default: 3).")
parser.add_argument('--pacipv-shadow-per-context', dest='pacipv_shadow_per_context', action='store_true',
                    help="Learn separate INST/DATA vectors for PACIPV shadow distillation.")
parser.add_argument('--pacipv-shadow-train-per-benchmark', dest='pacipv_shadow_train_per_benchmark', action='store_true',
                    help="Train a separate PACIPV shadow vector per benchmark and evaluate each benchmark with its own learned vector.")
parser.add_argument('--pacipv-shadow-vectors-file', dest='pacipv_shadow_vectors_file', default=None,
                    help="Path to save/load PACIPV shadow-distilled vectors.")
parser.add_argument('--learn-pacipv-shadow-dist', dest='learn_pacipv_shadow_dist', action='store_true',
                    help="Learn probabilistic PACIPV policy via shadow SRRIP distillation.")
parser.add_argument('--pacipv-shadow-dist-vectors-file', dest='pacipv_shadow_dist_vectors_file', default=None,
                    help="Path to save/load probabilistic PACIPV shadow policy (JSON).")
parser.add_argument('--learn-opt-distilled-srrip', dest='learn_opt_distilled_srrip', action='store_true',
                    help="Learn OPT-distilled SRRIP IPV + hit-correction from training traces.")
parser.add_argument('--opt-distilled-srrip-file', dest='opt_distilled_srrip_file', default=None,
                    help="Path to save/load OPT-distilled SRRIP policy parameters.")
parser.add_argument('--opt-distilled-max-rrpv', dest='opt_distilled_max_rrpv', type=int, default=3,
                    help="Maximum RRPV for OPT-distilled SRRIP policy.")
parser.add_argument('--opt-distilled-insert-policy', dest='opt_distilled_insert_policy',
                    choices=['sample', 'argmax'], default='sample',
                    help="Insertion policy for OPT-distilled SRRIP runtime: sample or argmax IPV.")
parser.add_argument('--opt-distilled-seed', dest='opt_distilled_seed', type=int, default=1,
                    help="Base seed for OPT-distilled SRRIP sampling at evaluation time.")
parser.add_argument('--srrip-max-rrpv', dest='srrip_max_rrpv', type=int, default=None,
                    help="Maximum RRPV for vanilla SRRIP (default: num_ways-1).")
parser.add_argument('--srrip-hit-delta', dest='srrip_hit_delta', type=int, default=1,
                    help="Hit promotion delta for vanilla SRRIP (default: 1).")
parser.add_argument('--output-dir', dest='output_dir', default='.',
                    help="Directory where the per-run result CSV will be written.")
parser.add_argument('--policies', dest='policies', default='belady,lfu,learned,prob_rank,pacipv',
                    help="Comma-separated policies to run. Supported: belady,lfu,learned,prob_rank,pacipv,pacipv_shadow,pacipv_shadow_dist,srrip,opt_distilled_srrip")


def parse_policy_list(policy_str):
    supported = ['belady', 'lfu', 'learned', 'prob_rank', 'pacipv', 'pacipv_shadow', 'pacipv_shadow_dist', 'srrip', 'opt_distilled_srrip']
    selected = [p.strip() for p in policy_str.split(',') if p.strip()]
    invalid = [p for p in selected if p not in supported]
    if invalid:
        raise ValueError(
            f"Unsupported policies: {invalid}. Supported policies: {supported}"
        )
    if not selected:
        raise ValueError("No policies selected. Use --policies with at least one valid policy.")
    return selected


def uses_prob_rank(selected_policies):
    return 'prob_rank' in selected_policies


def uses_pacipv(selected_policies):
    return 'pacipv' in selected_policies


def uses_training(selected_policies):
    return (
        uses_prob_rank(selected_policies)
        or uses_pacipv(selected_policies)
        or ('pacipv_shadow' in selected_policies)
        or ('pacipv_shadow_dist' in selected_policies)
        or ('opt_distilled_srrip' in selected_policies)
    )


def pacipv_requires_training(args, selected_policies):
    return uses_pacipv(selected_policies) and not args.pacipv_demand_vector


def requires_training_inputs(args, selected_policies):
    return (
        uses_prob_rank(selected_policies)
        or pacipv_requires_training(args, selected_policies)
        or ('pacipv_shadow' in selected_policies)
        or ('pacipv_shadow_dist' in selected_policies)
        or ('opt_distilled_srrip' in selected_policies)
    )


def resolve_runtime_options(args, selected_policies):
    needs_training = requires_training_inputs(args, selected_policies)

    if needs_training and not args.train_workload:
        raise ValueError(
            "--train-workload is required when prob_rank, pacipv, or "
            "pacipv_shadow, pacipv_shadow_dist, or opt_distilled_srrip is enabled."
        )

    return {
        'train_fraction': args.train_fraction if needs_training and args.train_fraction is not None else (1.0 if needs_training else None),
        'rank_model_scope': args.rank_model_scope if uses_prob_rank(selected_policies) and args.rank_model_scope is not None else ('per-set' if uses_prob_rank(selected_policies) else None),
        'prob_top_k': args.prob_top_k if uses_prob_rank(selected_policies) and args.prob_top_k is not None else (3 if uses_prob_rank(selected_policies) else None),
        'rank_sampling': args.rank_sampling if uses_prob_rank(selected_policies) and args.rank_sampling is not None else ('weighted' if uses_prob_rank(selected_policies) else None),
        'seed': args.seed if uses_prob_rank(selected_policies) and args.seed is not None else (1 if uses_prob_rank(selected_policies) else None),
        'pacipv_output_file': (args.pacipv_output_file or 'pacipv_vectors.txt') if pacipv_requires_training(args, selected_policies) else None,
        'pacipv_shadow_vectors_file': (args.pacipv_shadow_vectors_file or 'pacipv_shadow_vectors.txt') if ('pacipv_shadow' in selected_policies) else None,
        'pacipv_shadow_dist_vectors_file': (args.pacipv_shadow_dist_vectors_file or 'pacipv_shadow_dist_vectors.json') if ('pacipv_shadow_dist' in selected_policies) else None,
        'opt_distilled_srrip_file': (args.opt_distilled_srrip_file or 'opt_distilled_srrip.txt') if ('opt_distilled_srrip' in selected_policies) else None,
    }


def build_output_csv_name(args, selected_policies, runtime_options):
    parts = ['cache_miss_rates']
    needs_training = requires_training_inputs(args, selected_policies)

    if needs_training and args.train_workload is not None:
        parts.append(f"train.{args.train_workload}")

    parts.append(f"eval.{args.eval_workload}")
    parts.append(f"s{args.num_sets}")
    parts.append(f"w{args.num_ways}")

    if uses_prob_rank(selected_policies) and args.rank_model_scope is not None:
        parts.append(f"scope.{runtime_options['rank_model_scope']}")
    if uses_prob_rank(selected_policies) and args.prob_top_k is not None:
        parts.append(f"topk.{runtime_options['prob_top_k']}")
    if uses_prob_rank(selected_policies) and args.rank_sampling is not None:
        parts.append(f"sampling.{runtime_options['rank_sampling']}")
    if 'srrip' in selected_policies:
        srrip_max_rrpv = args.srrip_max_rrpv if args.srrip_max_rrpv is not None else int(args.num_ways) - 1
        parts.append(f"srrip_max.{srrip_max_rrpv}")
        parts.append(f"srrip_delta.{args.srrip_hit_delta}")
    if 'pacipv_shadow' in selected_policies:
        parts.append(f"pacipv_shadow_rrpv.{args.pacipv_shadow_max_rrpv}")
        parts.append(f"pacipv_shadow_ctx.{1 if args.pacipv_shadow_per_context else 0}")
    if 'pacipv_shadow_dist' in selected_policies:
        parts.append(f"pacipv_shadow_dist_rrpv.{args.pacipv_shadow_max_rrpv}")
        parts.append(f"pacipv_shadow_dist_ctx.{1 if args.pacipv_shadow_per_context else 0}")
    if 'pacipv' in selected_policies and args.pacipv_train_per_benchmark:
        parts.append('pacipv_train.per_benchmark')
    if 'pacipv_shadow' in selected_policies and args.pacipv_shadow_train_per_benchmark:
        parts.append('pacipv_shadow_train.per_benchmark')
    if 'pacipv_shadow_dist' in selected_policies and args.pacipv_shadow_train_per_benchmark:
        parts.append('pacipv_shadow_dist_train.per_benchmark')
    if 'opt_distilled_srrip' in selected_policies:
        parts.append(f"opt_distilled_rrpv.{args.opt_distilled_max_rrpv}")
    if needs_training and args.train_fraction is not None:
        frac_tag = f"{runtime_options['train_fraction']:.3f}".replace('.', 'p')
        parts.append(f"frac.{frac_tag}")
    if uses_prob_rank(selected_policies) and args.seed is not None:
        parts.append(f"seed.{runtime_options['seed']}")

    filename = '_'.join(parts) + '.csv'
    return os.path.join(args.output_dir, filename)


def validate_trace_paths(path_template, benchmarks, num_sets, trace_role):
    missing = []
    resolved_paths = {}

    print(f"[validate] {trace_role} traces: {len(benchmarks)} benchmark(s), num_sets={num_sets}")
    print(f"[validate] template: {path_template}")

    for benchmark in benchmarks:
        path = render_trace_path(path_template, benchmark, num_sets)
        resolved_paths[benchmark] = path
        if not os.path.exists(path):
            missing.append((benchmark, path))
            print(f"  [MISSING] {benchmark}: {path}")

    if missing:
        more_suffix = '' if len(missing) <= 5 else f"\n  ... and {len(missing) - 5} more"
        raise FileNotFoundError(
            f"Missing {trace_role} trace files for {len(missing)}/{len(benchmarks)} benchmark(s) "
            f"with num_sets={num_sets}.\n"
            f"Template: {path_template}\n"
            f"Provide the correct --{trace_role}-trace-path-template or generate the traces first."
        )

    # All found — show a couple of example resolved paths so the user can sanity-check the template
    examples = list(resolved_paths.items())[:3]
    example_str = ', '.join(f"{b}: {p}" for b, p in examples)
    print(f"[validate] All {len(benchmarks)} {trace_role} traces found. Examples: {example_str}")
    return resolved_paths


def _normalize_trace_for_srrip(trace, num_sets):
    """Normalize heterogeneous trace items into (set_id, address) tuples for SRRIP."""
    normalized = []
    for item in trace:
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            first = int(item[0])
            second = int(item[1])
            if 0 <= first < num_sets:
                normalized.append((first, second))
            else:
                # If first field is an address-like value, derive set from it.
                normalized.append((first % num_sets, first))
            continue

        address = int(item)
        normalized.append((address % num_sets, address))

    return normalized


def _resolve_context_ipv(ipv_result):
    """Return (data_vec, inst_vec) from a PACIPV-style result payload."""
    if ipv_result is None:
        return None, None

    ipv_spec = ipv_result.get('ipv_by_context')
    if ipv_spec is None:
        ipv_spec = ipv_result.get('ipv_vec')

    if isinstance(ipv_spec, dict):
        data_vec = ipv_spec.get(CTX_DATA)
        inst_vec = ipv_spec.get(CTX_INST)
        if data_vec is None:
            data_vec = inst_vec
        if inst_vec is None:
            inst_vec = data_vec
    else:
        data_vec = ipv_spec
        inst_vec = ipv_spec

    return data_vec, inst_vec


def _print_used_context_ipv(label, ipv_result, default_max_rrpv=None):
    """Print the effective INST/DATA vectors used at evaluation time."""
    if ipv_result is None:
        return

    data_vec, inst_vec = _resolve_context_ipv(ipv_result)
    max_rrpv = ipv_result.get('max_rrpv', default_max_rrpv)
    print(f"{label} vectors used (max_rrpv={max_rrpv}): data={data_vec}, inst={inst_vec}")


def _resolve_per_benchmark_trace_path(train_trace_paths, benchmark, label):
    trace_path = train_trace_paths.get(benchmark)
    if trace_path is None:
        raise ValueError(
            f"{label} per-benchmark training requires benchmark '{benchmark}' "
            "to exist in both the training and evaluation workloads."
        )
    return trace_path


def _parse_pacipv_vector(raw_value, max_rrpv):
    entries = [item.strip() for item in raw_value.split(',') if item.strip()]
    expected_len = max_rrpv + 2
    if len(entries) != expected_len:
        raise ValueError(
            f"--pacipv-demand-vector expects {expected_len} comma-separated integers "
            f"for max_rrpv={max_rrpv}, got {len(entries)}"
        )

    vector = []
    for item in entries:
        try:
            value = int(item)
        except ValueError as exc:
            raise ValueError(
                f"--pacipv-demand-vector contains a non-integer entry: {item!r}"
            ) from exc
        if value < 0 or value > max_rrpv:
            raise ValueError(
                f"--pacipv-demand-vector entries must be in [0, {max_rrpv}], got {value}"
            )
        vector.append(value)

    return tuple(vector)


def main():
    args = parser.parse_args()

    if args.learn_pacipv_vectors and args.pacipv_demand_vector:
        parser.error('--learn-pacipv-vectors cannot be combined with --pacipv-demand-vector')
    if args.pacipv_train_per_benchmark and args.pacipv_demand_vector:
        parser.error('--pacipv-train-per-benchmark cannot be combined with --pacipv-demand-vector')

    num_sets = int(args.num_sets)
    num_ways = int(args.num_ways)

    selected_policies = parse_policy_list(args.policies)
    needs_training = requires_training_inputs(args, selected_policies)
    run_belady = 'belady' in selected_policies
    run_lfu = 'lfu' in selected_policies
    run_learned = 'learned' in selected_policies
    run_prob_rank = 'prob_rank' in selected_policies
    run_pacipv = 'pacipv' in selected_policies
    run_pacipv_shadow = 'pacipv_shadow' in selected_policies
    run_pacipv_shadow_dist = 'pacipv_shadow_dist' in selected_policies
    run_srrip = 'srrip' in selected_policies
    run_opt_distilled_srrip = 'opt_distilled_srrip' in selected_policies

    runtime_options = resolve_runtime_options(args, selected_policies)
    train_fraction = runtime_options['train_fraction']
    rank_model_scope = runtime_options['rank_model_scope']
    prob_top_k = runtime_options['prob_top_k']
    rank_sampling = runtime_options['rank_sampling']
    seed = runtime_options['seed']
    pacipv_output_file = runtime_options['pacipv_output_file']
    pacipv_shadow_vectors_file = runtime_options['pacipv_shadow_vectors_file']
    pacipv_shadow_dist_vectors_file = runtime_options['pacipv_shadow_dist_vectors_file']
    opt_distilled_srrip_file = runtime_options['opt_distilled_srrip_file']

    train_benchmarks = []
    if needs_training:
        train_workload = workloads.Workloads(args.train_workload)
        train_benchmarks = train_workload.get_benchmark_names()
    eval_workload = workloads.Workloads(args.eval_workload)
    eval_benchmarks = eval_workload.get_benchmark_names()

    train_trace_paths = {}
    if needs_training:
        train_trace_paths = validate_trace_paths(
            args.train_trace_path_template,
            train_benchmarks,
            args.num_sets,
            'train',
        )
    eval_trace_paths = validate_trace_paths(
        args.eval_trace_path_template,
        eval_benchmarks,
        args.num_sets,
        'eval',
    )

    uniform_sampling = (rank_sampling == 'uniform-topk') if run_prob_rank else False
    hardcoded_pacipv_vector = None
    if args.pacipv_demand_vector:
        hardcoded_pacipv_vector = _parse_pacipv_vector(args.pacipv_demand_vector, args.pacipv_max_rrpv)

    # Demand-IPV-only learning mode.
    if args.pacipv_learn_prefetch:
        print("Ignoring --pacipv-learn-prefetch: sweep is configured to learn demand IPV only.")

    if run_pacipv and not args.learn_pacipv_vectors:
        if hardcoded_pacipv_vector is not None:
            print("PACIPV policy selected; using hardcoded demand vector from --pacipv-demand-vector.")
        else:
            print("PACIPV policy selected; enabling --learn-pacipv-vectors automatically.")
            args.learn_pacipv_vectors = True
    if not run_pacipv and args.learn_pacipv_vectors:
        print("Ignoring --learn-pacipv-vectors because pacipv was not selected.")
        args.learn_pacipv_vectors = False

    if run_pacipv_shadow and not args.learn_pacipv_shadow:
        if pacipv_shadow_vectors_file and os.path.exists(pacipv_shadow_vectors_file):
            print(f"Using existing PACIPV shadow vectors from {pacipv_shadow_vectors_file}.")
        else:
            print("pacipv_shadow policy selected; enabling --learn-pacipv-shadow automatically.")
            args.learn_pacipv_shadow = True
    if not run_pacipv_shadow and args.learn_pacipv_shadow:
        print("Ignoring --learn-pacipv-shadow because pacipv_shadow was not selected.")
        args.learn_pacipv_shadow = False

    if run_pacipv_shadow_dist and not args.learn_pacipv_shadow_dist:
        if pacipv_shadow_dist_vectors_file and os.path.exists(pacipv_shadow_dist_vectors_file):
            print(f"Using existing PACIPV shadow probabilistic vectors from {pacipv_shadow_dist_vectors_file}.")
        else:
            print("pacipv_shadow_dist policy selected; enabling --learn-pacipv-shadow-dist automatically.")
            args.learn_pacipv_shadow_dist = True
    if not run_pacipv_shadow_dist and args.learn_pacipv_shadow_dist:
        print("Ignoring --learn-pacipv-shadow-dist because pacipv_shadow_dist was not selected.")
        args.learn_pacipv_shadow_dist = False

    if run_opt_distilled_srrip and not args.learn_opt_distilled_srrip:
        if opt_distilled_srrip_file and os.path.exists(opt_distilled_srrip_file):
            print(f"Using existing OPT-distilled SRRIP policy from {opt_distilled_srrip_file}.")
        else:
            print("opt_distilled_srrip policy selected; enabling --learn-opt-distilled-srrip automatically.")
            args.learn_opt_distilled_srrip = True
    if not run_opt_distilled_srrip and args.learn_opt_distilled_srrip:
        print("Ignoring --learn-opt-distilled-srrip because opt_distilled_srrip was not selected.")
        args.learn_opt_distilled_srrip = False

    # ------------------------------------------------------------------
    # Rank model: load from file or train from scratch
    # ------------------------------------------------------------------
    train_per_set_counts = [defaultdict(int) for _ in range(num_sets)]
    train_global_counts = defaultdict(int)
    rank_model_path = args.rank_model_file
    # Always store rank model in data/belady_sweep/ if not absolute
    if rank_model_path and not os.path.isabs(rank_model_path) and not rank_model_path.startswith('data/belady_sweep/'):
        rank_model_path = os.path.join('data', 'belady_sweep', os.path.basename(rank_model_path))
    if run_prob_rank:
        if rank_model_path and os.path.exists(rank_model_path):
            train_per_set_counts, train_global_counts = load_rank_model(rank_model_path, num_sets)
        else:
            print(
                f"Training probabilistic rank model on '{args.train_workload}' "
                f"(fraction={train_fraction:.2f}, scope={rank_model_scope}, "
                f"top_k={prob_top_k}, sampling={rank_sampling})"
            )

            for benchmark in train_benchmarks:
                trace_path = train_trace_paths[benchmark]
                trace_entries = load_trace_entries(
                    trace_path,
                )
                trace = trace_entries_to_ptes(trace_entries)
                if train_fraction < 1.0:
                    trace = trace[:max(1, int(len(trace) * train_fraction))]

                per_set_counts, global_counts = collect_belady_rank_counts(num_sets, num_ways, trace)
                if rank_model_scope == 'per-set':
                    for set_id in range(num_sets):
                        for rank, cnt in per_set_counts[set_id].items():
                            train_per_set_counts[set_id][rank] += cnt
                for rank, cnt in global_counts.items():
                    train_global_counts[rank] += cnt

            if rank_model_path:
                save_rank_model(rank_model_path, train_per_set_counts, train_global_counts)

    pacipv_result = None
    pacipv_result_by_benchmark = None
    pacipv_shadow_result = None
    pacipv_shadow_result_by_benchmark = None
    pacipv_shadow_dist_result = None
    pacipv_shadow_dist_result_by_benchmark = None
    opt_distilled_srrip_result = None

    if run_pacipv and hardcoded_pacipv_vector is not None:
        pacipv_result = {
            'ipv_vec': hardcoded_pacipv_vector,
            'ipv_by_context': {
                CTX_DATA: hardcoded_pacipv_vector,
                CTX_INST: hardcoded_pacipv_vector,
            },
            'max_rrpv': args.pacipv_max_rrpv,
        }
        _print_used_context_ipv('PACIPV', pacipv_result, default_max_rrpv=args.pacipv_max_rrpv)

    # ------------------------------------------------------------------
    # Learn PACIPV vectors from training traces (optional)
    # ------------------------------------------------------------------
    if args.learn_pacipv_vectors:
        def _make_loader(benchmark):
            def _loader():
                te = load_trace_entries(
                    train_trace_paths[benchmark],
                )
                if train_fraction < 1.0:
                    te = te[:max(1, int(len(te) * train_fraction))]
                if args.pacipv_train_max_accesses > 0:
                    te = te[:args.pacipv_train_max_accesses]
                return te
            return _loader

        # Validate each benchmark has a non-empty trace (check once, discard data).
        trace_loaders = []
        empty_benchmarks = []
        for benchmark in train_benchmarks:
            loader = _make_loader(benchmark)
            te = loader()
            path = train_trace_paths[benchmark]
            size = os.path.getsize(path) if os.path.exists(path) else -1
            if te:
                trace_loaders.append(loader)
            else:
                empty_benchmarks.append((benchmark, path, size))
            del te

        if empty_benchmarks:
            print(f"[pacipv] {len(empty_benchmarks)}/{len(train_benchmarks)} training traces are empty/unreadable:")
            for b, p, sz in empty_benchmarks[:10]:
                print(f"  {b}: {p}  (file size: {sz} bytes)")
            if len(empty_benchmarks) > 10:
                print(f"  ... and {len(empty_benchmarks) - 10} more")

        if not trace_loaders:
            print(f"No usable training traces found for PACIPV learning "
                  f"({len(train_benchmarks)} benchmarks tried).")
            sys.exit(1)
        else:
            print(f"[pacipv] {len(trace_loaders)}/{len(train_benchmarks)} training traces are usable.")

        if args.pacipv_train_per_benchmark:
            pacipv_result_by_benchmark = {}
            for benchmark in eval_benchmarks:
                trace_path = _resolve_per_benchmark_trace_path(
                    train_trace_paths, benchmark, 'PACIPV'
                )
                loader = _make_loader(benchmark)
                te = loader()
                size = os.path.getsize(trace_path) if os.path.exists(trace_path) else -1
                if not te:
                    raise ValueError(
                        f"PACIPV per-benchmark training trace is empty/unreadable for "
                        f"'{benchmark}' ({trace_path}, file size: {size} bytes)"
                    )
                del te

                pacipv_result_by_benchmark[benchmark] = learn_pacipv_vectors(
                    num_sets,
                    num_ways,
                    [loader],
                    max_rrpv=args.pacipv_max_rrpv,
                )
                _print_used_context_ipv(
                    f"PACIPV[{benchmark}]",
                    pacipv_result_by_benchmark[benchmark],
                    default_max_rrpv=args.pacipv_max_rrpv,
                )
        else:
            pacipv_result = learn_pacipv_vectors(
                num_sets,
                num_ways,
                trace_loaders,
                max_rrpv=args.pacipv_max_rrpv,
            )
            save_pacipv_vectors(pacipv_output_file, pacipv_result)
            _print_used_context_ipv('PACIPV', pacipv_result, default_max_rrpv=args.pacipv_max_rrpv)

    if run_pacipv_shadow:
        if args.pacipv_shadow_train_per_benchmark:
            if not train_benchmarks:
                print(
                    f"No usable training traces found for pacipv_shadow "
                    f"({len(train_benchmarks)} benchmarks tried)."
                )
                sys.exit(1)

            def _make_shadow_loader(benchmark, fraction):
                def _loader():
                    te = load_trace_entries(train_trace_paths[benchmark])
                    if fraction < 1.0:
                        te = te[:max(1, int(len(te) * fraction))]
                    return te
                return _loader

            pacipv_shadow_result_by_benchmark = {}
            for benchmark in eval_benchmarks:
                trace_path = _resolve_per_benchmark_trace_path(
                    train_trace_paths, benchmark, 'PACIPV shadow'
                )
                loader = _make_shadow_loader(benchmark, train_fraction)
                te = loader()
                size = os.path.getsize(trace_path) if os.path.exists(trace_path) else -1
                if not te:
                    raise ValueError(
                        f"PACIPV shadow per-benchmark training trace is empty/unreadable for "
                        f"'{benchmark}' ({trace_path}, file size: {size} bytes)"
                    )
                del te

                pacipv_shadow_result_by_benchmark[benchmark] = train_pacipv_shadow_distilled(
                    num_sets,
                    num_ways,
                    [loader],
                    max_rrpv=args.pacipv_shadow_max_rrpv,
                    per_context=args.pacipv_shadow_per_context,
                )
                _print_used_context_ipv(
                    f"PACIPV shadow[{benchmark}]",
                    pacipv_shadow_result_by_benchmark[benchmark],
                    default_max_rrpv=args.pacipv_shadow_max_rrpv,
                )
        elif pacipv_shadow_vectors_file and os.path.exists(pacipv_shadow_vectors_file) and not args.learn_pacipv_shadow:
            pacipv_shadow_result = load_pacipv_shadow_vectors(
                pacipv_shadow_vectors_file,
                max_rrpv=args.pacipv_shadow_max_rrpv,
            )
            _print_used_context_ipv('PACIPV shadow', pacipv_shadow_result, default_max_rrpv=args.pacipv_shadow_max_rrpv)
        else:
            if not train_benchmarks:
                print(
                    f"No usable training traces found for pacipv_shadow "
                    f"({len(train_benchmarks)} benchmarks tried)."
                )
                sys.exit(1)

            def _make_shadow_loader(benchmark, fraction):
                def _loader():
                    te = load_trace_entries(train_trace_paths[benchmark])
                    if fraction < 1.0:
                        te = te[:max(1, int(len(te) * fraction))]
                    return te
                return _loader

            trace_loaders = [
                _make_shadow_loader(b, train_fraction)
                for b in train_benchmarks
            ]
            pacipv_shadow_result = train_pacipv_shadow_distilled(
                num_sets,
                num_ways,
                trace_loaders,
                max_rrpv=args.pacipv_shadow_max_rrpv,
                per_context=args.pacipv_shadow_per_context,
            )
            _print_used_context_ipv('PACIPV shadow', pacipv_shadow_result, default_max_rrpv=args.pacipv_shadow_max_rrpv)
            if pacipv_shadow_vectors_file:
                save_pacipv_shadow_vectors(pacipv_shadow_vectors_file, pacipv_shadow_result)

    if run_pacipv_shadow_dist:
        if args.pacipv_shadow_train_per_benchmark:
            if not train_benchmarks:
                print(
                    f"No usable training traces found for pacipv_shadow_dist "
                    f"({len(train_benchmarks)} benchmarks tried)."
                )
                sys.exit(1)

            def _make_shadow_dist_loader(benchmark, fraction):
                def _loader():
                    te = load_trace_entries(train_trace_paths[benchmark])
                    if fraction < 1.0:
                        te = te[:max(1, int(len(te) * fraction))]
                    return te
                return _loader

            pacipv_shadow_dist_result_by_benchmark = {}
            for benchmark in eval_benchmarks:
                trace_path = _resolve_per_benchmark_trace_path(
                    train_trace_paths, benchmark, 'PACIPV shadow probabilistic'
                )
                loader = _make_shadow_dist_loader(benchmark, train_fraction)
                te = loader()
                size = os.path.getsize(trace_path) if os.path.exists(trace_path) else -1
                if not te:
                    raise ValueError(
                        f"PACIPV shadow probabilistic per-benchmark training trace is empty/unreadable for "
                        f"'{benchmark}' ({trace_path}, file size: {size} bytes)"
                    )
                del te

                pacipv_shadow_dist_result_by_benchmark[benchmark] = train_pacipv_shadow_distilled_probabilistic(
                    num_sets,
                    num_ways,
                    [loader],
                    max_rrpv=args.pacipv_shadow_max_rrpv,
                    per_context=args.pacipv_shadow_per_context,
                )
        elif (
            pacipv_shadow_dist_vectors_file
            and os.path.exists(pacipv_shadow_dist_vectors_file)
            and not args.learn_pacipv_shadow_dist
        ):
            pacipv_shadow_dist_result = load_pacipv_shadow_probabilistic_vectors(
                pacipv_shadow_dist_vectors_file,
                max_rrpv=args.pacipv_shadow_max_rrpv,
            )
        else:
            if not train_benchmarks:
                print(
                    f"No usable training traces found for pacipv_shadow_dist "
                    f"({len(train_benchmarks)} benchmarks tried)."
                )
                sys.exit(1)

            def _make_shadow_dist_loader(benchmark, fraction):
                def _loader():
                    te = load_trace_entries(train_trace_paths[benchmark])
                    if fraction < 1.0:
                        te = te[:max(1, int(len(te) * fraction))]
                    return te
                return _loader

            trace_loaders = [
                _make_shadow_dist_loader(b, train_fraction)
                for b in train_benchmarks
            ]
            pacipv_shadow_dist_result = train_pacipv_shadow_distilled_probabilistic(
                num_sets,
                num_ways,
                trace_loaders,
                max_rrpv=args.pacipv_shadow_max_rrpv,
                per_context=args.pacipv_shadow_per_context,
            )
            if pacipv_shadow_dist_vectors_file:
                save_pacipv_shadow_probabilistic_vectors(
                    pacipv_shadow_dist_vectors_file,
                    pacipv_shadow_dist_result,
                )

    if run_opt_distilled_srrip:
        if opt_distilled_srrip_file and os.path.exists(opt_distilled_srrip_file) and not args.learn_opt_distilled_srrip:
            opt_distilled_srrip_result = load_opt_distilled_srrip(opt_distilled_srrip_file)
        else:
            train_trace = []
            for benchmark in train_benchmarks:
                te = load_trace_entries(train_trace_paths[benchmark])
                ptes = trace_entries_to_ptes(te)
                if train_fraction < 1.0:
                    ptes = ptes[:max(1, int(len(ptes) * train_fraction))]
                train_trace.extend(ptes)

            if not train_trace:
                print(
                    f"No usable training traces found for opt_distilled_srrip "
                    f"({len(train_benchmarks)} benchmarks tried)."
                )
                sys.exit(1)

            opt_distilled_srrip_result = train_opt_distilled_srrip(
                num_sets,
                num_ways,
                train_trace,
                max_rrpv=args.opt_distilled_max_rrpv,
            )
            print(
                "Learned OPT-distilled SRRIP: "
                f"IPV={opt_distilled_srrip_result['ipv_probs']}, "
                f"DELTA={opt_distilled_srrip_result['hit_deltas']}"
            )
            if opt_distilled_srrip_file:
                save_opt_distilled_srrip(opt_distilled_srrip_file, opt_distilled_srrip_result)

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
        'pacipv_shadow': 'pacipv_shadow_rate',
        'pacipv_shadow_dist': 'pacipv_shadow_dist_rate',
        'srrip': 'srrip_rate',
        'opt_distilled_srrip': 'opt_distilled_srrip_rate',
    }
    for policy in selected_policies:
        results[metric_by_policy[policy]] = []

    # choose a simple feature extractor; users can modify as needed
    # here we just take the PTE value itself, but in a real experiment this
    # might include PC, page-level bits, frequency, etc.
    feature_fn = lambda pte: pte

    per_set_model = train_per_set_counts if rank_model_scope == 'per-set' else None

    for bench_idx, benchmark in enumerate(eval_benchmarks):
        print(f"Processing benchmark: {benchmark}")

        trace_path = eval_trace_paths[benchmark]
        trace_entries = load_trace_entries(
            trace_path,
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
                top_k=prob_top_k,
                seed=seed + bench_idx,
                verbose=True,
                uniform=uniform_sampling,
            )

        pacipv_rate = float('nan')
        pacipv_dist_rate = float('nan')
        pacipv_shadow_rate = float('nan')
        pacipv_shadow_dist_rate = float('nan')
        srrip_rate = float('nan')
        opt_distilled_srrip_rate = float('nan')
        current_pacipv_result = None
        if run_pacipv:
            if pacipv_result_by_benchmark is not None:
                current_pacipv_result = pacipv_result_by_benchmark.get(benchmark)
                if current_pacipv_result is None:
                    raise ValueError(
                        f"Missing per-benchmark PACIPV result for evaluation benchmark '{benchmark}'"
                    )
            else:
                current_pacipv_result = pacipv_result

        if current_pacipv_result is not None and run_pacipv:
            learned_ipv = current_pacipv_result.get('ipv_by_context', current_pacipv_result['ipv_vec'])
            pacipv_probs = current_pacipv_result.get('rrpv_probs_by_context')
            if pacipv_probs:
                # Run PACIPV using insertion sampling from learned distributions.
                pacipv_dist_rate = simulate_pacipv_distribution(
                    num_sets,
                    num_ways,
                    trace_entries,
                    pacipv_probs,
                    max_rrpv=current_pacipv_result['max_rrpv'],
                    seed=bench_idx + 1,
                )
            else:
                pacipv_dist_rate = float('nan')
            pacipv_rate = simulate_pacipv(
                num_sets,
                num_ways,
                trace_entries,
                learned_ipv,
                max_rrpv=current_pacipv_result['max_rrpv'],
            )

        current_pacipv_shadow_result = None
        if run_pacipv_shadow:
            if pacipv_shadow_result_by_benchmark is not None:
                current_pacipv_shadow_result = pacipv_shadow_result_by_benchmark.get(benchmark)
                if current_pacipv_shadow_result is None:
                    raise ValueError(
                        f"Missing per-benchmark PACIPV shadow result for evaluation benchmark '{benchmark}'"
                    )
            else:
                current_pacipv_shadow_result = pacipv_shadow_result

        if run_pacipv_shadow and current_pacipv_shadow_result is not None:
            learned_ipv = current_pacipv_shadow_result.get(
                'ipv_by_context_constrained',
                current_pacipv_shadow_result.get('ipv_by_context', current_pacipv_shadow_result['ipv_vec'])
            )
            pacipv_shadow_rate = simulate_pacipv(
                num_sets,
                num_ways,
                trace_entries,
                learned_ipv,
                max_rrpv=current_pacipv_shadow_result['max_rrpv'],
            )

        current_pacipv_shadow_dist_result = None
        if run_pacipv_shadow_dist:
            if pacipv_shadow_dist_result_by_benchmark is not None:
                current_pacipv_shadow_dist_result = pacipv_shadow_dist_result_by_benchmark.get(benchmark)
                if current_pacipv_shadow_dist_result is None:
                    raise ValueError(
                        f"Missing per-benchmark PACIPV shadow probabilistic result for evaluation benchmark '{benchmark}'"
                    )
            else:
                current_pacipv_shadow_dist_result = pacipv_shadow_dist_result

        if run_pacipv_shadow_dist and current_pacipv_shadow_dist_result is not None:
            policy_spec = current_pacipv_shadow_dist_result.get('ipv_distribution_by_context')
            if policy_spec is None:
                raise ValueError('Missing ipv_distribution_by_context for pacipv_shadow_dist evaluation')
            pacipv_shadow_dist_rate = simulate_pacipv_probabilistic(
                num_sets,
                num_ways,
                trace_entries,
                policy_spec,
                max_rrpv=current_pacipv_shadow_dist_result['max_rrpv'],
                seed=bench_idx + 1,
            )

        if run_srrip:
            srrip_max_rrpv = args.srrip_max_rrpv if args.srrip_max_rrpv is not None else num_ways - 1
            if srrip_max_rrpv < 0:
                raise ValueError("--srrip-max-rrpv must be >= 0.")
            # Vanilla SRRIP insertion policy: insert near LRU at max_rrpv-1.
            insert_rrpv = max(0, srrip_max_rrpv - 1)
            srrip_trace = _normalize_trace_for_srrip(trace, num_sets)
            srrip_result = simulate_vanilla_srrip(
                srrip_trace,
                num_sets,
                num_ways,
                insert_rrpv=insert_rrpv,
                hit_delta=args.srrip_hit_delta,
                max_rrpv=srrip_max_rrpv,
            )
            srrip_rate = srrip_result['miss_rate']

        if run_opt_distilled_srrip and opt_distilled_srrip_result is not None:
            opt_distilled_max_rrpv = opt_distilled_srrip_result.get('max_rrpv', args.opt_distilled_max_rrpv)
            opt_distilled_srrip_rate = simulate_opt_distilled_srrip(
                num_sets,
                num_ways,
                trace_entries,
                opt_distilled_srrip_result,
                max_rrpv=opt_distilled_max_rrpv,
                insert_policy=args.opt_distilled_insert_policy,
                seed=args.opt_distilled_seed + bench_idx,
            )

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
            metric_parts.append(f"pacipv(dist) misses: {pacipv_dist_rate:.3f}")
        if run_pacipv_shadow:
            metric_parts.append(f"pacipv-shadow misses: {pacipv_shadow_rate:.3f}")
        if run_pacipv_shadow_dist:
            metric_parts.append(f"pacipv-shadow-dist misses: {pacipv_shadow_dist_rate:.3f}")
        if run_srrip:
            metric_parts.append(f"srrip misses: {srrip_rate:.3f}")
        if run_opt_distilled_srrip:
            metric_parts.append(f"opt-distilled-srrip misses: {opt_distilled_srrip_rate:.3f}")
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
            results.setdefault('pacipv_dist_rate', []).append(pacipv_dist_rate)
        if run_pacipv_shadow:
            results['pacipv_shadow_rate'].append(pacipv_shadow_rate)
        if run_pacipv_shadow_dist:
            results['pacipv_shadow_dist_rate'].append(pacipv_shadow_dist_rate)
        if run_srrip:
            results['srrip_rate'].append(srrip_rate)
        if run_opt_distilled_srrip:
            results['opt_distilled_srrip_rate'].append(opt_distilled_srrip_rate)

    if run_belady:
        print(f"Average belady rate: {safe_mean(results['belady_rate']):.4f}")
    if run_lfu:
        print(f"Average lfu rate:    {safe_mean(results['lfu_rate']):.4f}")
    if run_learned:
        print(f"Average learned rate: {safe_mean(results['learned_rate']):.4f}")
    if run_prob_rank:
        print(f"Average prob-rank rate: {safe_mean(results['prob_rank_rate']):.4f}")
    if run_pacipv:
        print(f"Average pacipv(dist) rate: {safe_mean(results['pacipv_dist_rate']):.4f}")
    if run_pacipv_shadow:
        print(f"Average pacipv-shadow rate: {safe_mean(results['pacipv_shadow_rate']):.4f}")
    if run_pacipv_shadow_dist:
        print(f"Average pacipv-shadow-dist rate: {safe_mean(results['pacipv_shadow_dist_rate']):.4f}")
    if run_srrip:
        print(f"Average srrip rate: {safe_mean(results['srrip_rate']):.4f}")
    if run_opt_distilled_srrip:
        print(f"Average opt-distilled-srrip rate: {safe_mean(results['opt_distilled_srrip_rate']):.4f}")
    if run_prob_rank and run_belady:
        gaps = [p - b for p, b in zip(results['prob_rank_rate'], results['belady_rate'])]
        print(f"Avg gap (prob-rank - belady): {safe_mean(gaps):.4f}")

    output_csv = build_output_csv_name(args, selected_policies, runtime_options)
    output_dir = os.path.dirname(output_csv)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        metric_columns = [metric_by_policy[p] for p in selected_policies]
        if run_pacipv:
            metric_columns.extend(['pacipv_dist_rate'])
        writer.writerow(['benchmark'] + metric_columns)
        for i in range(len(results['benchmark'])):
            row = [results['benchmark'][i]]
            for col in metric_columns:
                row.append(results[col][i])
            writer.writerow(row)
    print(f"Results saved to {output_csv}")


if __name__ == "__main__":
    main()
