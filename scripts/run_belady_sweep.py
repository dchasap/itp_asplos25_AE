#!/usr/bin/env python3

import argparse
import csv
import itertools
import os
import subprocess
import sys
from pathlib import Path


def parse_csv_list(value, cast=str):
    return [cast(x.strip()) for x in value.split(',') if x.strip()]


def frac_tag(value):
    return f"{value:.3f}".replace('.', 'p')


def render_cfg_template(template, cfg):
    if not template:
        return None
    try:
        return template.format(
            train_workload=cfg['train_workload'],
            eval_workload=cfg['eval_workload'],
            num_sets=cfg['num_sets'],
            num_ways=cfg['num_ways'],
            rank_model_scope=cfg['rank_model_scope'],
            prob_top_k=cfg['prob_top_k'],
            rank_sampling=cfg['rank_sampling'],
            train_fraction=cfg['train_fraction'],
            train_fraction_tag=frac_tag(cfg['train_fraction']),
            seed=cfg['seed'],
        )
    except KeyError as exc:
        raise ValueError(
            f"Invalid placeholder in template '{template}': {exc}. "
            "Supported placeholders: {train_workload}, {eval_workload}, {num_sets}, "
            "{num_ways}, {rank_model_scope}, {prob_top_k}, {rank_sampling}, "
            "{train_fraction}, {train_fraction_tag}, {seed}."
        ) from exc


def parse_learned_demand_ipv(pacipv_output_file):
    if not pacipv_output_file or not os.path.exists(pacipv_output_file):
        return ''

    with open(pacipv_output_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('TXVC_PACIPV_DEMAND_VEC='):
                return line.split('=', 1)[1].strip().strip('"')

    return ''


def mean_from_csv(csv_path, column):
    total = 0.0
    count = 0
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or column not in reader.fieldnames:
            return float('nan')
        for row in reader:
            total += float(row[column])
            count += 1
    return (total / count) if count else float('nan')


def build_cmd(args, cfg):
    script = Path(__file__).with_name('estimate_belady_opt.py')
    cmd = [
        args.python_exe,
        str(script),
        '--train-workload', cfg['train_workload'],
        '--eval-workload', cfg['eval_workload'],
        '--num-sets', str(cfg['num_sets']),
        '--num-ways', str(cfg['num_ways']),
        '--rank-model-scope', cfg['rank_model_scope'],
        '--prob-top-k', str(cfg['prob_top_k']),
        '--rank-sampling', cfg['rank_sampling'],
        '--train-fraction', str(cfg['train_fraction']),
        '--seed', str(cfg['seed']),
        '--policies', args.policies,
    ]
    if args.train_trace_path_template:
        cmd.extend(['--train-trace-path-template', args.train_trace_path_template])
    if args.eval_trace_path_template:
        cmd.extend(['--eval-trace-path-template', args.eval_trace_path_template])
    rank_model_file = render_cfg_template(args.rank_model_file_template, cfg)
    if rank_model_file:
        cmd.extend(['--rank-model-file', rank_model_file])

    pacipv_output_file = render_cfg_template(args.pacipv_output_file_template, cfg)
    if pacipv_output_file:
        pacipv_output_parent = Path(pacipv_output_file).parent
        pacipv_output_parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(['--pacipv-output-file', pacipv_output_file])

    # Sweep learns demand IPV over all training benchmarks (prefetch IPV is fixed/default).
    cmd.append('--learn-pacipv-vectors')

    if args.pacipv_train_max_accesses > 0:
        cmd.extend(['--pacipv-train-max-accesses', str(args.pacipv_train_max_accesses)])

    return cmd


def extract_output_csv(stdout_text):
    for line in stdout_text.splitlines()[::-1]:
        if 'Results saved to ' in line:
            return line.split('Results saved to ', 1)[1].strip()
    return None


def make_slurm_job(batch_idx, cfgs, sweep_args, job_dir, dump_dir):
    """Write a SLURM .run job script that runs each config in the batch in parallel.

    Each config is launched with ``srun --exclusive -n 1`` so all batch_size
    tasks start concurrently, followed by a single ``wait``.  The job file is
    written to *job_dir* and the stdout/stderr of the whole job goes to
    *dump_dir*.
    """
    n = len(cfgs)
    job_name = f"belady_sweep_{batch_idx:04d}_job"
    job_path = Path(job_dir) / (job_name + ".run")

    script = Path(__file__).with_name('estimate_belady_opt.py')

    with open(job_path, 'w') as f:
        f.write("#!/bin/bash\n\n")
        f.write(f"#SBATCH --nodes=1\n")
        f.write(f"#SBATCH --ntasks={n}\n")
        f.write(f"#SBATCH --cpus-per-task=1\n")
        f.write(f"#SBATCH -o {dump_dir}/{job_name}_run.out\n")
        f.write(f"#SBATCH -J {job_name}\n")
        if sweep_args.slurm_account:
            f.write(f"#SBATCH -A {sweep_args.slurm_account}\n")
        f.write(f"#SBATCH --qos={sweep_args.slurm_qos}\n")
        f.write(f"#SBATCH --time={sweep_args.slurm_time}\n")
        f.write("\n")

        for cfg in cfgs:
            cmd = build_cmd(sweep_args, cfg)
            cmd_str = ' '.join(cmd)
            f.write(f"srun --exclusive -n 1 {cmd_str} &\n")

        f.write("\nwait\n")

    return job_path


def main():
    parser = argparse.ArgumentParser(description='Grid sweep runner for estimate_belady_opt.py')
    parser.add_argument('--train-workloads', required=True,
                        help='Comma-separated list, e.g. selected_qualcomm_srv_ap,other_suite')
    parser.add_argument('--eval-workloads', required=True,
                        help='Comma-separated list, e.g. selected_qualcomm_srv_ap,other_suite')
    parser.add_argument('--num-sets-list', default='64', help='Comma-separated ints')
    parser.add_argument('--num-ways-list', default='16', help='Comma-separated ints')
    parser.add_argument('--rank-model-scopes', default='per-set',
                        help='Comma-separated values from {per-set,global}')
    parser.add_argument('--prob-top-k-list', default='3', help='Comma-separated ints')
    parser.add_argument('--rank-samplings', default='weighted',
                        help='Comma-separated values from {weighted,uniform-topk}')
    parser.add_argument('--train-fractions', default='1.0', help='Comma-separated floats in [0,1]')
    parser.add_argument('--seeds', default='42', help='Comma-separated ints')
    parser.add_argument('--policies',
                        default='belady,lfu,learned,prob_rank,pacipv,pacipv_lfu',
                        help='Comma-separated policies forwarded to estimate_belady_opt.py')
    parser.add_argument('--train-trace-path-template', default=None,
                        help='Forwarded to estimate_belady_opt.py. Supports {benchmark} and {num_sets}.')
    parser.add_argument('--eval-trace-path-template', default=None,
                        help='Forwarded to estimate_belady_opt.py. Supports {benchmark} and {num_sets}.')
    parser.add_argument('--rank-model-file-template', default=None,
                        help='Rendered per config and forwarded as --rank-model-file. Supports '
                             '{train_workload}, {eval_workload}, {num_sets}, {num_ways}, '
                             '{rank_model_scope}, {prob_top_k}, {rank_sampling}, '
                             '{train_fraction}, {train_fraction_tag}, and {seed}.')
    parser.add_argument('--pacipv-output-file-template',
                        default='dump/pacipv_vectors/{train_workload}_to_{eval_workload}_s{num_sets}_w{num_ways}_frac{train_fraction_tag}_seed{seed}.txt',
                        help='Rendered per config and forwarded as --pacipv-output-file. Supports '
                            '{train_workload}, {eval_workload}, {num_sets}, {num_ways}, '
                            '{rank_model_scope}, {prob_top_k}, {rank_sampling}, '
                            '{train_fraction}, {train_fraction_tag}, and {seed}.')
    parser.add_argument('--pacipv-train-max-accesses', type=int, default=0,
                        help='Forwarded to estimate_belady_opt.py to cap accesses per train benchmark '
                            'during IPV learning (0 = no cap).')
    parser.add_argument('--python-exe', default=sys.executable, help='Python interpreter')
    parser.add_argument('--summary-csv', default='belady_sweep_summary.csv', help='Output summary CSV')
    parser.add_argument('--continue-on-error', action='store_true',
                        help='Continue running remaining configs if one fails')
    parser.add_argument('--dry-run', action='store_true', help='Print commands without running or submitting')

    # SLURM submission options
    slurm_grp = parser.add_argument_group('SLURM', 'Options for submitting jobs via sbatch')
    slurm_grp.add_argument('--slurm', action='store_true',
                           help='Batch configs into SLURM jobs and submit via sbatch')
    slurm_grp.add_argument('--slurm-batch-size', type=int, default=20,
                           help='Number of configs to run in parallel inside each SLURM job (default: 20)')
    slurm_grp.add_argument('--slurm-account', default='bsc18',
                           help='SLURM account (-A), e.g. bsc18')
    slurm_grp.add_argument('--slurm-qos', default='gp_bsccs',
                           help='SLURM QoS (--qos), e.g. gp_bsccs or debug')
    slurm_grp.add_argument('--slurm-time', default='02:00:00',
                           help='Wall-clock time limit per job, e.g. 02:00:00')
    slurm_grp.add_argument('--slurm-job-dir', default='dump/belady_sweep2',
                           help='Directory where .run job scripts are written')
    slurm_grp.add_argument('--slurm-dump-dir', default='dump/belady_sweep2',
                           help='Directory for SLURM stdout/stderr files')

    args = parser.parse_args()

    train_workloads = parse_csv_list(args.train_workloads)
    eval_workloads = parse_csv_list(args.eval_workloads)
    num_sets_list = parse_csv_list(args.num_sets_list, int)
    num_ways_list = parse_csv_list(args.num_ways_list, int)
    scopes = parse_csv_list(args.rank_model_scopes)
    topk_list = parse_csv_list(args.prob_top_k_list, int)
    samplings = parse_csv_list(args.rank_samplings)
    fractions = parse_csv_list(args.train_fractions, float)
    seeds = parse_csv_list(args.seeds, int)

    configs = []
    for (train_workload, eval_workload, num_sets, num_ways, scope, topk, sampling, frac, seed) in itertools.product(
        train_workloads,
        eval_workloads,
        num_sets_list,
        num_ways_list,
        scopes,
        topk_list,
        samplings,
        fractions,
        seeds,
    ):
        configs.append({
            'train_workload': train_workload,
            'eval_workload': eval_workload,
            'num_sets': num_sets,
            'num_ways': num_ways,
            'rank_model_scope': scope,
            'prob_top_k': topk,
            'rank_sampling': sampling,
            'train_fraction': frac,
            'seed': seed,
        })

    print(f'Total configurations: {len(configs)}')
    rows = []

    # ------------------------------------------------------------------ #
    #  SLURM submission path                                               #
    # ------------------------------------------------------------------ #
    if args.slurm:
        job_dir = Path(args.slurm_job_dir)
        dump_dir = Path(args.slurm_dump_dir)
        job_dir.mkdir(parents=True, exist_ok=True)
        dump_dir.mkdir(parents=True, exist_ok=True)

        batch_size = args.slurm_batch_size
        batches = [configs[i:i + batch_size] for i in range(0, len(configs), batch_size)]
        print(f'Submitting {len(batches)} SLURM job(s) '
              f'({batch_size} configs/job, {len(configs)} configs total)')

        for batch_idx, batch in enumerate(batches):
            job_path = make_slurm_job(batch_idx, batch, args, job_dir, dump_dir)

            status = 'planned' if args.dry_run else 'submitted'
            for cfg in batch:
                row = dict(cfg)
                row.update({
                    'status': status,
                    'returncode': '',
                    'rank_model_file': render_cfg_template(args.rank_model_file_template, cfg) or '',
                    'pacipv_output_file': render_cfg_template(args.pacipv_output_file_template, cfg) or '',
                    'learned_demand_ipv': '',
                    'output_csv': '',
                    'avg_belady_rate': '',
                    'avg_lfu_rate': '',
                    'avg_learned_rate': '',
                    'avg_prob_rank_rate': '',
                    'avg_pacipv_rate': '',
                    'avg_pacipv_lfu_rate': '',
                    'stderr_tail': '',
                    'job_script': str(job_path),
                })
                rows.append(row)

            if args.dry_run:
                print(f'  [DRY-RUN] Would submit: {job_path}')
            else:
                result = subprocess.run(['sbatch', str(job_path)], capture_output=True, text=True)
                if result.returncode == 0:
                    print(f'  Submitted {job_path.name}: {result.stdout.strip()}')
                else:
                    print(f'  FAILED to submit {job_path.name}: {result.stderr.strip()}')
                    if not args.continue_on_error:
                        break

        # Write summary and exit — results are collected later once jobs finish
        summary_path = Path(args.summary_csv)
        fieldnames = [
            'status', 'returncode', 'train_workload', 'eval_workload',
            'num_sets', 'num_ways', 'rank_model_scope', 'prob_top_k',
            'rank_sampling', 'train_fraction', 'seed',
            'rank_model_file',
            'pacipv_output_file', 'learned_demand_ipv',
            'avg_belady_rate', 'avg_lfu_rate', 'avg_learned_rate', 'avg_prob_rank_rate',
            'avg_pacipv_rate', 'avg_pacipv_lfu_rate',
            'output_csv', 'job_script', 'stderr_tail',
        ]
        with open(summary_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        submitted = sum(1 for r in rows if r['status'] == 'submitted')
        planned = sum(1 for r in rows if r['status'] == 'planned')
        if args.dry_run:
            print(f'\nDry-run complete. Planned runs: {planned} across {len(batches)} job(s)')
        else:
            print(f'\nSubmitted {submitted} configs across {len(batches)} SLURM job(s)')
        print(f'Summary written to {summary_path}')
        return

    # ------------------------------------------------------------------ #
    #  Local (sequential) execution path                                   #
    # ------------------------------------------------------------------ #
    for idx, cfg in enumerate(configs, start=1):
        cmd = build_cmd(args, cfg)
        print(f"[{idx}/{len(configs)}] {' '.join(cmd)}")
        if args.dry_run:
            row = dict(cfg)
            row.update({
                'status': 'planned',
                'returncode': '',
                'rank_model_file': render_cfg_template(args.rank_model_file_template, cfg) or '',
                'pacipv_output_file': render_cfg_template(args.pacipv_output_file_template, cfg) or '',
                'learned_demand_ipv': '',
                'output_csv': '',
                'avg_belady_rate': '',
                'avg_lfu_rate': '',
                'avg_learned_rate': '',
                'avg_prob_rank_rate': '',
                'avg_pacipv_rate': '',
                'avg_pacipv_lfu_rate': '',
                'stderr_tail': '',
                'job_script': '',
            })
            rows.append(row)
            continue

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            row = dict(cfg)
            row.update({
                'status': 'failed',
                'returncode': proc.returncode,
                'rank_model_file': render_cfg_template(args.rank_model_file_template, cfg) or '',
                'pacipv_output_file': render_cfg_template(args.pacipv_output_file_template, cfg) or '',
                'learned_demand_ipv': '',
                'output_csv': '',
                'avg_belady_rate': '',
                'avg_lfu_rate': '',
                'avg_learned_rate': '',
                'avg_prob_rank_rate': '',
                'avg_pacipv_rate': '',
                'avg_pacipv_lfu_rate': '',
                'stderr_tail': '\\n'.join(proc.stderr.splitlines()[-10:]),
                'job_script': '',
            })
            rows.append(row)
            print(f"  -> FAILED (exit {proc.returncode})")
            if not args.continue_on_error:
                break
            continue

        out_csv = extract_output_csv(proc.stdout)
        if not out_csv or not os.path.exists(out_csv):
            row = dict(cfg)
            row.update({
                'status': 'failed-no-csv',
                'returncode': proc.returncode,
                'rank_model_file': render_cfg_template(args.rank_model_file_template, cfg) or '',
                'pacipv_output_file': render_cfg_template(args.pacipv_output_file_template, cfg) or '',
                'learned_demand_ipv': '',
                'output_csv': out_csv or '',
                'avg_belady_rate': '',
                'avg_lfu_rate': '',
                'avg_learned_rate': '',
                'avg_prob_rank_rate': '',
                'avg_pacipv_rate': '',
                'avg_pacipv_lfu_rate': '',
                'stderr_tail': '\\n'.join(proc.stderr.splitlines()[-10:]),
                'job_script': '',
            })
            rows.append(row)
            print('  -> FAILED (could not find output csv)')
            if not args.continue_on_error:
                break
            continue

        row = dict(cfg)
        pacipv_output_file = render_cfg_template(args.pacipv_output_file_template, cfg) or ''
        row.update({
            'status': 'ok',
            'returncode': proc.returncode,
            'rank_model_file': render_cfg_template(args.rank_model_file_template, cfg) or '',
            'pacipv_output_file': pacipv_output_file,
            'learned_demand_ipv': parse_learned_demand_ipv(pacipv_output_file),
            'output_csv': out_csv,
            'avg_belady_rate': mean_from_csv(out_csv, 'belady_rate'),
            'avg_lfu_rate': mean_from_csv(out_csv, 'lfu_rate'),
            'avg_learned_rate': mean_from_csv(out_csv, 'learned_rate'),
            'avg_prob_rank_rate': mean_from_csv(out_csv, 'prob_rank_rate'),
            'avg_pacipv_rate': mean_from_csv(out_csv, 'pacipv_rate'),
            'avg_pacipv_lfu_rate': mean_from_csv(out_csv, 'pacipv_lfu_rate'),
            'stderr_tail': '',
            'job_script': '',
        })
        rows.append(row)
        print(f"  -> ok, avg prob-rank {row['avg_prob_rank_rate']:.4f}")

    if not rows:
        print('No rows to write (dry-run with empty config?)')
        return

    summary_path = Path(args.summary_csv)
    fieldnames = [
        'status', 'returncode', 'train_workload', 'eval_workload',
        'num_sets', 'num_ways', 'rank_model_scope', 'prob_top_k',
        'rank_sampling', 'train_fraction', 'seed',
        'rank_model_file',
        'pacipv_output_file', 'learned_demand_ipv',
        'avg_belady_rate', 'avg_lfu_rate', 'avg_learned_rate', 'avg_prob_rank_rate',
        'avg_pacipv_rate', 'avg_pacipv_lfu_rate',
        'output_csv', 'job_script', 'stderr_tail',
    ]

    with open(summary_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    ok_count = sum(1 for r in rows if r['status'] == 'ok')
    planned_count = sum(1 for r in rows if r['status'] == 'planned')
    if args.dry_run:
        print(f"\nDry-run complete. Planned runs: {planned_count}")
    else:
        print(f"\nSweep complete. Successful runs: {ok_count}/{len(rows)}")
    print(f"Summary written to {summary_path}")


if __name__ == '__main__':
    main()
