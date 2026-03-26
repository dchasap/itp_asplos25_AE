#!/usr/bin/env python3

import argparse
import csv
import math
import os
import re
import sys


def parse_csv_list(value, cast=str):
    return [cast(x.strip()) for x in value.split(',') if x.strip()]


def parse_policy_list(policy_str):
    supported = ['belady', 'lfu', 'learned', 'prob_rank', 'pacipv', 'pacipv_lfu']
    raw = [p.strip() for p in policy_str.split(',') if p.strip()]
    if not raw:
        return supported

    unknown = [p for p in raw if p not in supported]
    if unknown:
        raise ValueError(f"Unknown policy/policies: {unknown}. Supported: {supported}")

    out = []
    for p in raw:
        if p not in out:
            out.append(p)
    return out


def policy_rate_key(policy):
    return {
        'belady': 'avg_belady_rate',
        'lfu': 'avg_lfu_rate',
        'learned': 'avg_learned_rate',
        'prob_rank': 'avg_prob_rank_rate',
        'pacipv': 'avg_pacipv_rate',
        'pacipv_lfu': 'avg_pacipv_lfu_rate',
    }[policy]


def policy_input_key(policy):
    return {
        'belady': 'belady_rate',
        'lfu': 'lfu_rate',
        'learned': 'learned_rate',
        'prob_rank': 'prob_rank_rate',
        'pacipv': 'pacipv_rate',
        'pacipv_lfu': 'pacipv_lfu_rate',
    }[policy]


def policy_label(policy):
    return {
        'belady': 'Belady',
        'lfu': 'LFU',
        'learned': 'Learned Table',
        'prob_rank': 'Prob Rank',
        'pacipv': 'PACIPV',
        'pacipv_lfu': 'PACIPV LFU',
    }[policy]


def frac_tag(value):
    return f"{value:.3f}".replace('.', 'p')


OUTPUT_RE = re.compile(
    r"^cache_miss_rates_"
    r"train\.(?P<train_workload>.+?)_"
    r"eval\.(?P<eval_workload>.+?)_"
    r"s(?P<num_sets>\d+)_"
    r"w(?P<num_ways>\d+)_"
    r"scope\.(?P<rank_model_scope>.+?)_"
    r"topk\.(?P<prob_top_k>\d+)_"
    r"sampling\.(?P<rank_sampling>.+?)_"
    r"frac\.(?P<train_fraction>[0-9]+p[0-9]+)_"
    r"seed\.(?P<seed>\d+)\.csv$"
)


def parse_output_cfg_from_name(filename):
    m = OUTPUT_RE.match(filename)
    if not m:
        return None

    cfg = m.groupdict()
    cfg['num_sets'] = int(cfg['num_sets'])
    cfg['num_ways'] = int(cfg['num_ways'])
    cfg['prob_top_k'] = int(cfg['prob_top_k'])
    cfg['seed'] = int(cfg['seed'])
    cfg['train_fraction'] = float(cfg['train_fraction'].replace('p', '.'))
    return cfg


def mean_column(csv_path, column):
    total = 0.0
    count = 0
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or column not in reader.fieldnames:
            return float('nan')
        for row in reader:
            total += float(row[column])
            count += 1
    if count == 0:
        return float('nan')
    return total / count


def safe_mean(values):
    vals = [v for v in values if not math.isnan(v)]
    if not vals:
        return float('nan')
    return sum(vals) / len(vals)


def short_cfg_label(cfg):
    keys = [
        ('train_workload', 'tw'),
        ('eval_workload', 'ew'),
        ('num_sets', 's'),
        ('num_ways', 'w'),
        ('rank_model_scope', 'scope'),
        ('prob_top_k', 'k'),
        ('rank_sampling', 'samp'),
        ('train_fraction', 'f'),
        ('seed', 'seed'),
    ]
    return '|'.join(f"{short}={cfg[k]}" for (k, short) in keys if k in cfg)


def write_summary_csv(path, rows):
    fieldnames = [
        'status',
        'train_workload',
        'eval_workload',
        'num_sets',
        'num_ways',
        'rank_model_scope',
        'prob_top_k',
        'rank_sampling',
        'train_fraction',
        'seed',
        'output_csv',
        'avg_belady_rate',
        'avg_lfu_rate',
        'avg_learned_rate',
        'avg_prob_rank_rate',
        'avg_pacipv_rate',
        'avg_pacipv_lfu_rate',
        'avg_gap_prob_minus_belady',
    ]
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def render_policy_only_plot(rows, plots_dir, prefix, selected_policies, file_format='png'):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"Could not import matplotlib; skipping plots. Error: {exc}")
        return []

    found = [r for r in rows if r['status'] == 'found']
    if not found:
        print('No found rows to plot.')
        return []

    os.makedirs(plots_dir, exist_ok=True)

    labels = [policy_label(p) for p in selected_policies]
    y_vals = []
    for p in selected_policies:
        key = policy_rate_key(p)
        vals = [r[key] for r in found if not math.isnan(r[key])]
        y_vals.append(safe_mean(vals))

    fig, ax = plt.subplots(figsize=(max(7, 1.2 * len(labels)), 5.5))
    x_positions = list(range(len(labels)))
    ax.bar(x_positions, y_vals, width=0.65, alpha=0.9)
    ax.set_title('Miss-Rate by Policy')
    ax.set_xlabel('Policy')
    ax.set_ylabel('Miss-Rate')
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.grid(axis='y', alpha=0.25)
    fig.tight_layout()

    path = os.path.join(plots_dir, f'{prefix}_bar_miss_rates_by_policy.{file_format}')
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return [path]


def render_plots(rows, plots_dir, prefix, baseline_cfg, selected_policies, feature_keys, file_format='png'):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"Could not import matplotlib; skipping plots. Error: {exc}")
        return []

    found = [r for r in rows if r['status'] == 'found']
    if not found:
        print('No found rows to plot.')
        return []

    os.makedirs(plots_dir, exist_ok=True)
    plot_paths = []

    # One grouped bar graph per feature: miss-rates vs feature value.
    # For a selected feature, all other features are fixed to baseline_cfg.
    all_features = [
        ('train_fraction', 'Training Fraction'),
        ('train_workload', 'Train Workload'),
        ('eval_workload', 'Eval Workload'),
        ('num_sets', 'Number of Sets'),
        ('num_ways', 'Number of Ways'),
        ('rank_model_scope', 'Rank Model Scope'),
        ('prob_top_k', 'Top-K'),
        ('rank_sampling', 'Rank Sampling'),
        ('seed', 'Seed'),
    ]
    features = [(k, n) for (k, n) in all_features if k in feature_keys]

    method_specs = [(policy_rate_key(p), policy_label(p)) for p in selected_policies]

    def sort_values(values):
        try:
            return sorted(values, key=float)
        except (TypeError, ValueError):
            return sorted(values, key=str)

    for feature_key, feature_name in features:
        filtered = []
        for row in found:
            keep = True
            for other_key, _ in features:
                if other_key == feature_key:
                    continue
                if row.get(other_key) != baseline_cfg.get(other_key):
                    keep = False
                    break
            if keep:
                filtered.append(row)

        feature_values = sort_values({row[feature_key] for row in filtered})
        if len(feature_values) <= 1:
            print(f"Skipping {feature_key}: only one feature value after fixing others to baseline.")
            continue

        fig, ax = plt.subplots(figsize=(max(8, 1.3 * len(feature_values)), 6))
        tick_labels = [str(v) for v in feature_values]
        x_positions = list(range(len(feature_values)))

        n_methods = len(method_specs)
        bar_width = 0.8 / n_methods
        offset_start = -0.4 + (bar_width / 2.0)

        any_bar = False
        for method_idx, (rate_key, method_label) in enumerate(method_specs):
            y_vals = []
            for value in feature_values:
                value_rows = [r for r in filtered if r[feature_key] == value]
                vals = [r[rate_key] for r in value_rows if not math.isnan(r[rate_key])]
                y_vals.append(safe_mean(vals))

            if any(not math.isnan(v) for v in y_vals):
                any_bar = True

            bar_positions = [x + offset_start + (method_idx * bar_width) for x in x_positions]
            ax.bar(bar_positions, y_vals, width=bar_width, label=method_label, alpha=0.9)

        if not any_bar:
            plt.close(fig)
            print(f"Skipping {feature_key}: no miss-rate data for plotting.")
            continue

        baseline_text = ', '.join(
            f"{k}={baseline_cfg[k]}" for (k, _) in features if k != feature_key and k in baseline_cfg
        )

        ax.set_title(f'Miss-Rate Bar Graph vs {feature_name}')
        ax.set_xlabel(feature_name)
        ax.set_ylabel('Miss-Rate')
        ax.set_xticks(x_positions)
        ax.set_xticklabels(tick_labels)
        ax.set_xlim(-0.5, len(feature_values) - 0.5)
        ax.margins(x=0.01)
        ax.grid(axis='y', alpha=0.25)
        ax.legend(loc='best')

        # Keep labels readable for categorical features with long names.
        if any(len(lbl) > 12 for lbl in tick_labels):
            for tick in ax.get_xticklabels():
                tick.set_rotation(35)
                tick.set_ha('right')

        fig.text(
            0.5, 0.01,
            f"Fixed (baseline): {baseline_text}",
            ha='center', va='bottom', fontsize=7,
            style='italic', color='#444444',
            wrap=True,
        )
        fig.tight_layout(rect=[0, 0.04, 1, 1])
        path = os.path.join(plots_dir, f'{prefix}_bar_miss_rates_vs_{feature_key}.{file_format}')
        fig.savefig(path, dpi=170)
        plot_paths.append(path)
        plt.close(fig)

    return plot_paths


def main():
    parser = argparse.ArgumentParser(
        description='Look up estimate_belady_opt.py outputs and generate summary plots.'
    )
    parser.add_argument('--train-workloads', default=None,
                        help='Optional comma-separated list filter')
    parser.add_argument('--eval-workloads', default=None,
                        help='Optional comma-separated list filter')
    parser.add_argument('--num-sets-list', required=True, help='Comma-separated ints (required)')
    parser.add_argument('--num-ways-list', required=True, help='Comma-separated ints (required)')
    parser.add_argument('--rank-model-scopes', default=None,
                        help='Comma-separated values from {per-set,global}')
    parser.add_argument('--prob-top-k-list', default=None, help='Optional comma-separated ints')
    parser.add_argument('--rank-samplings', default=None,
                        help='Comma-separated values from {weighted,uniform-topk}')
    parser.add_argument('--train-fractions', default=None, help='Optional comma-separated floats in [0,1]')
    parser.add_argument('--seeds', default=None, help='Optional comma-separated ints')
    parser.add_argument('--train-trace-path-template', default=None,
                        help='Accepted for CLI compatibility; not used for CSV lookup naming.')
    parser.add_argument('--eval-trace-path-template', default=None,
                        help='Accepted for CLI compatibility; not used for CSV lookup naming.')

    parser.add_argument('--results-dir', default='.', help='Directory containing output CSV files')
    parser.add_argument('--summary-csv', default='belady_plot_lookup_summary.csv',
                        help='Summary CSV for discovered/missing results')
    parser.add_argument('--plots-dir', default='figures/belady_sweep', help='Output directory for plots')
    parser.add_argument('--plot-prefix', default='belady_lookup', help='Filename prefix for generated plots')
    parser.add_argument('--plot-file-format', choices=['png', 'pdf'], default='png',
                        help='File format for generated plots')
    parser.add_argument('--missing-policy', choices=['skip', 'error'], default='skip',
                        help='How to handle missing expected result files')
    parser.add_argument('--policies',
                        default='belady,lfu,learned,prob_rank,pacipv,pacipv_lfu',
                        help='Comma-separated policies to include in summary/plots '
                             '(same names as run_belady_sweep.py)')

    args = parser.parse_args()
    selected_policies = parse_policy_list(args.policies)

    train_workloads = parse_csv_list(args.train_workloads) if args.train_workloads else None
    eval_workloads = parse_csv_list(args.eval_workloads) if args.eval_workloads else None
    num_sets_list = parse_csv_list(args.num_sets_list, int)
    num_ways_list = parse_csv_list(args.num_ways_list, int)
    scopes = parse_csv_list(args.rank_model_scopes) if args.rank_model_scopes else None
    topk_list = parse_csv_list(args.prob_top_k_list, int) if args.prob_top_k_list else None
    samplings = parse_csv_list(args.rank_samplings) if args.rank_samplings else None
    fractions = parse_csv_list(args.train_fractions, float) if args.train_fractions else None
    seeds = parse_csv_list(args.seeds, int) if args.seeds else None

    provided_filters = {
        'train_workload': train_workloads,
        'eval_workload': eval_workloads,
        'num_sets': num_sets_list,
        'num_ways': num_ways_list,
        'rank_model_scope': scopes,
        'prob_top_k': topk_list,
        'rank_sampling': samplings,
        'train_fraction': fractions,
        'seed': seeds,
    }

    names_for_title = {
        'train_workload': 'Train Workload',
        'eval_workload': 'Eval Workload',
        'num_sets': 'Number of Sets',
        'num_ways': 'Number of Ways',
        'rank_model_scope': 'Rank Model Scope',
        'prob_top_k': 'Top-K',
        'rank_sampling': 'Rank Sampling',
        'train_fraction': 'Training Fraction',
        'seed': 'Seed',
    }
    provided_optional_keys = [
        k for k in ['train_workload', 'eval_workload', 'rank_model_scope', 'prob_top_k', 'rank_sampling', 'train_fraction', 'seed']
        if provided_filters[k] is not None
    ]

    rows = []
    missing = 0
    found = 0

    for name in os.listdir(args.results_dir):
        if not name.startswith('cache_miss_rates_') or not name.endswith('.csv'):
            continue
        cfg = parse_output_cfg_from_name(name)
        if cfg is None:
            continue

        keep = True
        for k, allowed in provided_filters.items():
            if allowed is None:
                continue
            if cfg[k] not in allowed:
                keep = False
                break
        if not keep:
            continue

        output_path = os.path.join(args.results_dir, name)
        row = dict(cfg)
        row['output_csv'] = output_path
        row['status'] = 'found'

        for policy in ['belady', 'lfu', 'learned', 'prob_rank', 'pacipv', 'pacipv_lfu']:
            rate_key = policy_rate_key(policy)
            if policy in selected_policies:
                row[rate_key] = mean_column(output_path, policy_input_key(policy))
            else:
                row[rate_key] = float('nan')

        if 'belady' in selected_policies and 'prob_rank' in selected_policies:
            row['avg_gap_prob_minus_belady'] = row['avg_prob_rank_rate'] - row['avg_belady_rate']
        else:
            row['avg_gap_prob_minus_belady'] = float('nan')

        rows.append(row)
        found += 1

    if not rows:
        print('No matching result CSV files found in results-dir with the provided filters.')
        if args.missing_policy == 'error':
            sys.exit(1)

    write_summary_csv(args.summary_csv, rows)
    print(f'Lookup summary written to {args.summary_csv}')
    print(f'Found {found}, missing {missing}')

    baseline_cfg = rows[0] if rows else {'num_sets': num_sets_list[0], 'num_ways': num_ways_list[0]}
    print('Baseline values for non-varied features:')
    print(f"  {short_cfg_label(baseline_cfg)}")

    if missing and args.missing_policy == 'error':
        print('Missing outputs encountered with --missing-policy error.')
        sys.exit(1)

    dynamic_suffix_parts = []
    for k in ['train_workload', 'eval_workload', 'num_sets', 'num_ways', 'rank_model_scope', 'prob_top_k', 'rank_sampling', 'train_fraction', 'seed']:
        allowed = provided_filters[k]
        if allowed is None:
            continue
        if len(allowed) == 1:
            dynamic_suffix_parts.append(f"{k}.{allowed[0]}")
        else:
            dynamic_suffix_parts.append(f"{k}.multi")
    dynamic_prefix = args.plot_prefix
    if dynamic_suffix_parts:
        dynamic_prefix = f"{args.plot_prefix}_" + '_'.join(dynamic_suffix_parts)

    if not provided_optional_keys:
        plot_paths = render_policy_only_plot(rows, args.plots_dir, dynamic_prefix, selected_policies, args.plot_file_format)
    else:
        feature_keys = [k for k in provided_filters if provided_filters[k] is not None]
        plot_paths = render_plots(rows, args.plots_dir, dynamic_prefix, baseline_cfg, selected_policies, feature_keys, args.plot_file_format)

    # If no feature varies (or all feature plots are skipped), always emit
    # a single policy-comparison bar plot.
    if not plot_paths:
        plot_paths = render_policy_only_plot(rows, args.plots_dir, dynamic_prefix, selected_policies, args.plot_file_format)

    if plot_paths:
        print('Generated plots:')
        for path in plot_paths:
            print(f'  {path}')

    if found and ('belady' in selected_policies and 'prob_rank' in selected_policies):
        found_rows = [r for r in rows if r['status'] == 'found']
        valid_rows = [r for r in found_rows if not math.isnan(r['avg_gap_prob_minus_belady'])]
        if valid_rows:
            best = min(valid_rows, key=lambda r: abs(r['avg_gap_prob_minus_belady']))
            print('\nClosest config to Belady (by absolute gap):')
            print(f"  gap={best['avg_gap_prob_minus_belady']:.6f}  file={best['output_csv']}")
            print(f"  cfg={short_cfg_label(best)}")


if __name__ == '__main__':
    main()
