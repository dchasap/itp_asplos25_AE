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


def parse_policy_list(policy_str):
    supported = ['belady', 'lfu', 'learned', 'prob_rank', 'pacipv', 'pacipv_lfu', 'belady_driven_sampling']
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


def uses_prob_rank(selected_policies):
    return 'prob_rank' in selected_policies


def uses_pacipv(selected_policies):
    return 'pacipv' in selected_policies or 'pacipv_lfu' in selected_policies


def uses_belady_driven_sampling(selected_policies):
    return 'belady_driven_sampling' in selected_policies


def uses_training(selected_policies):
    return uses_prob_rank(selected_policies) or uses_pacipv(selected_policies) or uses_belady_driven_sampling(selected_policies)


def frac_tag(value):
    return f"{value:.3f}".replace('.', 'p')


def alpha_tag(value):
    return f"{value:.3f}".replace('.', 'p')


def materialize_cfg(cfg, selected_policies):
    effective = dict(cfg)
    if uses_training(selected_policies):
        if effective.get('train_workload') is None:
            raise ValueError('train_workload is required for the selected policies')
        if effective.get('train_fraction') is None:
            effective['train_fraction'] = 1.0

    if uses_prob_rank(selected_policies):
        if effective.get('rank_model_scope') is None:
            effective['rank_model_scope'] = 'per-set'
        if effective.get('prob_top_k') is None:
            effective['prob_top_k'] = 3
        if effective.get('rank_sampling') is None:
            effective['rank_sampling'] = 'weighted'
        if effective.get('seed') is None:
            effective['seed'] = 42

    if uses_belady_driven_sampling(selected_policies):
        if effective.get('bds_alpha') is None:
            effective['bds_alpha'] = 1.0

    return effective


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
            bds_alpha=cfg['bds_alpha'],
            bds_alpha_tag=alpha_tag(cfg['bds_alpha']),
        )
    except KeyError as exc:
        raise ValueError(
            f"Invalid placeholder in template '{template}': {exc}. "
            "Supported placeholders: {train_workload}, {eval_workload}, {num_sets}, "
            "{num_ways}, {rank_model_scope}, {prob_top_k}, {rank_sampling}, "
            "{train_fraction}, {train_fraction_tag}, {seed}, {bds_alpha}, {bds_alpha_tag}."
        ) from exc


def parse_learned_pacipv_vectors(pacipv_vectors_file):
    vectors = {
        'learned_inst_ipv': '',
        'learned_data_ipv': '',
        'learned_demand_ipv': '',
    }
    if not pacipv_vectors_file or not os.path.exists(pacipv_vectors_file):
        return vectors

    with open(pacipv_vectors_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('TXVC_PACIPV_INST_VEC='):
                vectors['learned_inst_ipv'] = line.split('=', 1)[1].strip().strip('"')
            elif line.startswith('TXVC_PACIPV_DATA_VEC='):
                vectors['learned_data_ipv'] = line.split('=', 1)[1].strip().strip('"')
            elif line.startswith('TXVC_PACIPV_DEMAND_VEC='):
                vectors['learned_demand_ipv'] = line.split('=', 1)[1].strip().strip('"')

    return vectors


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


def build_expected_output_csv(cfg, selected_policies, summary_csv_path):
    output_dir = Path(summary_csv_path).parent
    effective_cfg = materialize_cfg(cfg, selected_policies)
    parts = ['cache_miss_rates']

    if uses_training(selected_policies) and effective_cfg['train_workload'] is not None:
        parts.append(f"train.{effective_cfg['train_workload']}")

    parts.append(f"eval.{effective_cfg['eval_workload']}")
    parts.append(f"s{effective_cfg['num_sets']}")
    parts.append(f"w{effective_cfg['num_ways']}")

    if uses_prob_rank(selected_policies):
        parts.append(f"scope.{effective_cfg['rank_model_scope']}")
        parts.append(f"topk.{effective_cfg['prob_top_k']}")
        parts.append(f"sampling.{effective_cfg['rank_sampling']}")
    if uses_belady_driven_sampling(selected_policies):
        parts.append(f"alpha.{alpha_tag(effective_cfg['bds_alpha'])}")
    if uses_training(selected_policies):
        parts.append(f"frac.{frac_tag(effective_cfg['train_fraction'])}")
    if uses_prob_rank(selected_policies):
        parts.append(f"seed.{effective_cfg['seed']}")

    return str(output_dir / ('_'.join(parts) + '.csv'))


def build_summary_row(args, cfg, selected_policies):
    effective_cfg = materialize_cfg(cfg, selected_policies)
    pacipv_vectors_file = render_cfg_template(args.pacipv_vectors_file_template, effective_cfg) if uses_pacipv(selected_policies) else ''
    output_csv = build_expected_output_csv(cfg, selected_policies, args.summary_csv)
    row = dict(cfg)
    row.update({
        'returncode': '',
        'rank_model_file': render_cfg_template(args.rank_model_file_template, effective_cfg) if uses_prob_rank(selected_policies) else '',
        'pacipv_vectors_file': pacipv_vectors_file,
        'learned_inst_ipv': '',
        'learned_data_ipv': '',
        'learned_demand_ipv': '',
        'output_csv': output_csv,
        'avg_belady_rate': '',
        'avg_lfu_rate': '',
        'avg_learned_rate': '',
        'avg_prob_rank_rate': '',
        'avg_pacipv_rate': '',
        'avg_pacipv_dist_rate': '',
        'avg_pacipv_vec_rate': '',
        'avg_pacipv_lfu_rate': '',
        'avg_belady_driven_sampling_rate': '',
        'stderr_tail': '',
        'job_script': '',
    })
    return row


def populate_summary_row_from_files(row, selected_policies):
    output_csv = row['output_csv']
    if not output_csv or not os.path.exists(output_csv):
        row['status'] = 'missing'
        return row

    if uses_pacipv(selected_policies) and row['pacipv_vectors_file']:
        pacipv_vectors = parse_learned_pacipv_vectors(row['pacipv_vectors_file'])
        row['learned_inst_ipv'] = pacipv_vectors['learned_inst_ipv']
        row['learned_data_ipv'] = pacipv_vectors['learned_data_ipv']
        row['learned_demand_ipv'] = pacipv_vectors['learned_demand_ipv']

    row['status'] = 'ok'
    row['avg_belady_rate'] = mean_from_csv(output_csv, 'belady_rate')
    row['avg_lfu_rate'] = mean_from_csv(output_csv, 'lfu_rate')
    row['avg_learned_rate'] = mean_from_csv(output_csv, 'learned_rate')
    row['avg_prob_rank_rate'] = mean_from_csv(output_csv, 'prob_rank_rate')
    row['avg_pacipv_rate'] = mean_from_csv(output_csv, 'pacipv_rate')
    row['avg_pacipv_dist_rate'] = mean_from_csv(output_csv, 'pacipv_dist_rate')
    row['avg_pacipv_vec_rate'] = mean_from_csv(output_csv, 'pacipv_vec_rate')
    row['avg_pacipv_lfu_rate'] = mean_from_csv(output_csv, 'pacipv_lfu_rate')
    row['avg_belady_driven_sampling_rate'] = mean_from_csv(output_csv, 'belady_driven_sampling_rate')
    return row


def build_cmd(args, cfg, selected_policies):
    script = Path(__file__).with_name('estimate_belady_opt.py')
    effective_cfg = materialize_cfg(cfg, selected_policies)
    output_dir = str(Path(args.summary_csv).parent)
    cmd = [
        args.python_exe,
        str(script),
        '--eval-workload', effective_cfg['eval_workload'],
        '--num-sets', str(effective_cfg['num_sets']),
        '--num-ways', str(effective_cfg['num_ways']),
        '--output-dir', output_dir,
        '--policies', args.policies,
    ]
    if uses_training(selected_policies):
        cmd.extend(['--train-workload', effective_cfg['train_workload']])
        cmd.extend(['--train-fraction', str(effective_cfg['train_fraction'])])
    if uses_prob_rank(selected_policies):
        cmd.extend(['--rank-model-scope', effective_cfg['rank_model_scope']])
        cmd.extend(['--prob-top-k', str(effective_cfg['prob_top_k'])])
        cmd.extend(['--rank-sampling', effective_cfg['rank_sampling']])
        cmd.extend(['--seed', str(effective_cfg['seed'])])
    if args.train_trace_path_template:
        cmd.extend(['--train-trace-path-template', args.train_trace_path_template])
    if args.eval_trace_path_template:
        cmd.extend(['--eval-trace-path-template', args.eval_trace_path_template])
    rank_model_file = render_cfg_template(args.rank_model_file_template, effective_cfg) if uses_prob_rank(selected_policies) else None
    if rank_model_file:
        cmd.extend(['--rank-model-file', rank_model_file])

    pacipv_vectors_file = render_cfg_template(args.pacipv_vectors_file_template, effective_cfg) if uses_pacipv(selected_policies) else None
    if pacipv_vectors_file:
        pacipv_vectors_parent = Path(pacipv_vectors_file).parent
        pacipv_vectors_parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(['--pacipv-vectors-file', pacipv_vectors_file])

    # Sweep learns demand IPV over all training benchmarks (prefetch IPV is fixed/default).
    if uses_pacipv(selected_policies):
        cmd.append('--learn-pacipv-vectors')

    if uses_pacipv(selected_policies) and args.pacipv_train_max_accesses > 0:
        cmd.extend(['--pacipv-train-max-accesses', str(args.pacipv_train_max_accesses)])

    if uses_belady_driven_sampling(selected_policies):
        cmd.extend(['--bds-alpha', str(effective_cfg['bds_alpha'])])

    return cmd


def extract_output_csv(stdout_text):
    for line in stdout_text.splitlines()[::-1]:
        if 'Results saved to ' in line:
            return line.split('Results saved to ', 1)[1].strip()
    return None


def extract_failure_tail(proc, max_lines=10):
    chunks = []
    stderr_lines = proc.stderr.splitlines()
    stdout_lines = proc.stdout.splitlines()

    if stderr_lines:
        chunks.append('\n'.join(stderr_lines[-max_lines:]))
    if stdout_lines:
        stdout_tail = '\n'.join(stdout_lines[-max_lines:])
        if not stderr_lines or stdout_tail not in chunks:
            chunks.append(stdout_tail)

    return '\n\n'.join(chunk for chunk in chunks if chunk)


def make_slurm_job(batch_idx, cfgs, sweep_args, job_dir, dump_dir, selected_policies):
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
            cmd = build_cmd(sweep_args, cfg, selected_policies)
            cmd_str = ' '.join(cmd)
            f.write(f"srun --exclusive -n 1 {cmd_str} &\n")

        f.write("\nwait\n")

    return job_path


def main():
    parser = argparse.ArgumentParser(description='Grid sweep runner for estimate_belady_opt.py')
    parser.add_argument('--train-workloads', default=None,
                        help='Comma-separated list, e.g. selected_qualcomm_srv_ap,other_suite')
    parser.add_argument('--eval-workloads', required=True,
                        help='Comma-separated list, e.g. selected_qualcomm_srv_ap,other_suite')
    parser.add_argument('--num-sets-list', default='64', help='Comma-separated ints')
    parser.add_argument('--num-ways-list', default='16', help='Comma-separated ints')
    parser.add_argument('--rank-model-scopes', default=None,
                        help='Comma-separated values from {per-set,global}')
    parser.add_argument('--prob-top-k-list', default=None, help='Comma-separated ints')
    parser.add_argument('--rank-samplings', default=None,
                        help='Comma-separated values from {weighted,uniform-topk}')
    parser.add_argument('--train-fractions', default=None, help='Comma-separated floats in [0,1]')
    parser.add_argument('--seeds', default=None, help='Comma-separated ints')
    parser.add_argument('--bds-alphas', default=None, help='Comma-separated floats for belady_driven_sampling alpha')
    parser.add_argument('--policies',
                        default='belady,lfu,learned,prob_rank,pacipv,pacipv_lfu',
                        help='Comma-separated policies forwarded to estimate_belady_opt.py')
    parser.add_argument('--train-trace-path-template', default=None,
                        help='Forwarded to estimate_belady_opt.py. Supports {benchmark} and {num_sets}.')
    parser.add_argument('--eval-trace-path-template', default=None,
                        help='Forwarded to estimate_belady_opt.py. Supports {benchmark} and {num_sets}.')
    parser.add_argument('--rank-model-file-template', default='data/belady_sweep/rank_model_{train_workload}_to_{eval_workload}_s{num_sets}_w{num_ways}_scope.{rank_model_scope}_topk.{prob_top_k}_sampling.{rank_sampling}_frac.{train_fraction_tag}_seed.{seed}.csv',
                        help='Rendered per config and forwarded as --rank-model-file. Supports '
                             '{train_workload}, {eval_workload}, {num_sets}, {num_ways}, '
                             '{rank_model_scope}, {prob_top_k}, {rank_sampling}, '
                             '{train_fraction}, {train_fraction_tag}, {seed}, {bds_alpha}, and {bds_alpha_tag}.')
    parser.add_argument('--pacipv-vectors-file-template', '--pacipv-output-file-template',
                        dest='pacipv_vectors_file_template',
                        default='data/belady_sweep/pacipv_vectors_{train_workload}_to_{eval_workload}_s{num_sets}_w{num_ways}_frac{train_fraction_tag}_seed{seed}.txt',
                        help='Rendered per config and forwarded as --pacipv-vectors-file. Supports '
                            '{train_workload}, {eval_workload}, {num_sets}, {num_ways}, '
                            '{rank_model_scope}, {prob_top_k}, {rank_sampling}, '
                            '{train_fraction}, {train_fraction_tag}, {seed}, {bds_alpha}, and {bds_alpha_tag}.')
    parser.add_argument('--pacipv-train-max-accesses', type=int, default=0,
                        help='Forwarded to estimate_belady_opt.py to cap accesses per train benchmark '
                            'during IPV learning (0 = no cap).')
    parser.add_argument('--python-exe', default=sys.executable, help='Python interpreter')
    parser.add_argument('--summary-csv', default='data/belady_sweep/belady_sweep_summary.csv', help='Output summary CSV')
    parser.add_argument('--collect-existing-results', action='store_true',
                        help='Do not run or submit jobs; rebuild summary CSV from expected per-config output CSVs already on disk')
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

    selected_policies = parse_policy_list(args.policies)
    if uses_training(selected_policies) and not args.train_workloads:
        parser.error('--train-workloads is required when prob_rank, pacipv, pacipv_lfu, or belady_driven_sampling is enabled')

    train_workloads = parse_csv_list(args.train_workloads) if args.train_workloads else [None]
    eval_workloads = parse_csv_list(args.eval_workloads)
    num_sets_list = parse_csv_list(args.num_sets_list, int)
    num_ways_list = parse_csv_list(args.num_ways_list, int)
    scopes = parse_csv_list(args.rank_model_scopes) if args.rank_model_scopes else [None]
    topk_list = parse_csv_list(args.prob_top_k_list, int) if args.prob_top_k_list else [None]
    samplings = parse_csv_list(args.rank_samplings) if args.rank_samplings else [None]
    fractions = parse_csv_list(args.train_fractions, float) if args.train_fractions else [None]
    seeds = parse_csv_list(args.seeds, int) if args.seeds else [None]
    bds_alphas = parse_csv_list(args.bds_alphas, float) if args.bds_alphas else [None]

    configs = []
    for (train_workload, eval_workload, num_sets, num_ways, scope, topk, sampling, frac, seed, bds_alpha) in itertools.product(
        train_workloads,
        eval_workloads,
        num_sets_list,
        num_ways_list,
        scopes,
        topk_list,
        samplings,
        fractions,
        seeds,
        bds_alphas,
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
            'bds_alpha': bds_alpha,
        })

    print(f'Total configurations: {len(configs)}')
    rows = []

    if args.collect_existing_results:
        for cfg in configs:
            row = build_summary_row(args, cfg, selected_policies)
            row = populate_summary_row_from_files(row, selected_policies)
            rows.append(row)

        summary_path = Path(args.summary_csv)
        fieldnames = [
            'status', 'returncode', 'train_workload', 'eval_workload',
            'num_sets', 'num_ways', 'rank_model_scope', 'prob_top_k',
            'rank_sampling', 'train_fraction', 'seed', 'bds_alpha',
            'rank_model_file',
            'pacipv_vectors_file', 'learned_inst_ipv', 'learned_data_ipv', 'learned_demand_ipv',
            'avg_belady_rate', 'avg_lfu_rate', 'avg_learned_rate', 'avg_prob_rank_rate',
            'avg_pacipv_rate', 'avg_pacipv_dist_rate', 'avg_pacipv_vec_rate', 'avg_pacipv_lfu_rate',
            'avg_belady_driven_sampling_rate',
            'output_csv', 'job_script', 'stderr_tail',
        ]
        with open(summary_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        ok_count = sum(1 for r in rows if r['status'] == 'ok')
        missing_count = sum(1 for r in rows if r['status'] == 'missing')
        print(f'Collected existing results: ok={ok_count}, missing={missing_count}')
        print(f'Summary written to {summary_path}')
        return

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
            job_path = make_slurm_job(batch_idx, batch, args, job_dir, dump_dir, selected_policies)

            status = 'planned' if args.dry_run else 'submitted'
            for cfg in batch:
                row = build_summary_row(args, cfg, selected_policies)
                row['status'] = status
                row['job_script'] = str(job_path)
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
            'rank_sampling', 'train_fraction', 'seed', 'bds_alpha',
            'rank_model_file',
            'pacipv_vectors_file', 'learned_inst_ipv', 'learned_data_ipv', 'learned_demand_ipv',
            'avg_belady_rate', 'avg_lfu_rate', 'avg_learned_rate', 'avg_prob_rank_rate',
            'avg_pacipv_rate', 'avg_pacipv_dist_rate', 'avg_pacipv_vec_rate', 'avg_pacipv_lfu_rate',
            'avg_belady_driven_sampling_rate',
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
        effective_cfg = materialize_cfg(cfg, selected_policies)
        cmd = build_cmd(args, cfg, selected_policies)
        print(f"[{idx}/{len(configs)}] {' '.join(cmd)}")
        if args.dry_run:
            row = build_summary_row(args, cfg, selected_policies)
            row['status'] = 'planned'
            rows.append(row)
            continue

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            # Print full subprocess output to terminal so failures are visible without opening the CSV
            if proc.stdout.strip():
                print("  -- subprocess stdout --")
                print(proc.stdout)
            if proc.stderr.strip():
                print("  -- subprocess stderr --")
                print(proc.stderr)
            row = build_summary_row(args, cfg, selected_policies)
            row['status'] = 'failed'
            row['returncode'] = proc.returncode
            row['stderr_tail'] = extract_failure_tail(proc)
            rows.append(row)
            print(f"  -> FAILED (exit {proc.returncode})")
            if not args.continue_on_error:
                break
            continue

        out_csv = extract_output_csv(proc.stdout)
        if not out_csv or not os.path.exists(out_csv):
            row = build_summary_row(args, cfg, selected_policies)
            row['status'] = 'failed-no-csv'
            row['returncode'] = proc.returncode
            row['output_csv'] = out_csv or row['output_csv']
            row['stderr_tail'] = extract_failure_tail(proc)
            rows.append(row)
            print('  -> FAILED (could not find output csv)')
            if not args.continue_on_error:
                break
            continue

        row = build_summary_row(args, cfg, selected_policies)
        row['status'] = 'ok'
        row['returncode'] = proc.returncode
        row['output_csv'] = out_csv
        row = populate_summary_row_from_files(row, selected_policies)
        row['status'] = 'ok'
        row['returncode'] = proc.returncode
        rows.append(row)
        print(f"  -> ok, avg prob-rank {row['avg_prob_rank_rate']:.4f}")

    if not rows:
        print('No rows to write (dry-run with empty config?)')
        return

    summary_path = Path(args.summary_csv)
    fieldnames = [
        'status', 'returncode', 'train_workload', 'eval_workload',
        'num_sets', 'num_ways', 'rank_model_scope', 'prob_top_k',
        'rank_sampling', 'train_fraction', 'seed', 'bds_alpha',
        'rank_model_file',
        'pacipv_vectors_file', 'learned_inst_ipv', 'learned_data_ipv', 'learned_demand_ipv',
        'avg_belady_rate', 'avg_lfu_rate', 'avg_learned_rate', 'avg_prob_rank_rate',
        'avg_pacipv_rate', 'avg_pacipv_dist_rate', 'avg_pacipv_vec_rate', 'avg_pacipv_lfu_rate',
        'avg_belady_driven_sampling_rate',
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
