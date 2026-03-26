#!/usr/bin/env python3

import workloads
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import stats

l2c_size = '1.25MB'
llc_size = '2MB'
filter = 'freq-filter'
#filter = 'none'

if (llc_size == '2MB'):
    data_dir = 'stats/txvc_budget_eval'
else:
    data_dir = f'stats/txvc_budget_eval_llc_{llc_size}'

figures_dir = 'figures'
output_file = 'all_suites_boxplot'



import plotting

benchsuites = ['spec_cpu_2017', 'gapp', 'selected_qualcomm_srv_ap', 'google_srv']

benchmarks = []
for benchsuite in benchsuites:
    workload = workloads.Workloads(benchsuite)
    
    benchmarks.extend(workload.get_benchmark_names())

configurations = [ f'BASELINE-L2C-{l2c_size}', 
                  f'L2C-{l2c_size}-TXVC-16KB-FILTER-{filter}', 
                  f'L2C-{l2c_size}-TXVC-32KB-FILTER-{filter}',
                  f'L2C-{l2c_size}-TXVC-64KB-FILTER-{filter}' ]

all_data = []
for benchsuite in benchsuites:
  for conf in configurations:

    csv_file = (f'./{data_dir}/{conf}/{benchsuite}_{conf}.csv')

    if ('BASELINE' in conf):
        baseline_df = pd.read_csv(csv_file)
        baseline_df['setup'] = conf
        baseline_df['benchsuite'] = benchsuite
        continue

    df = pd.read_csv(csv_file)
    df['setup'] = conf
    df['benchsuite'] = benchsuite

    df = stats.compute_variation(baseline_df, df, conf, 'IPC', 'IPC_IMPROVEMENT')

    #df = pd.concat([df, pd.read_csv(csv_file, header=0)]) 
    all_data.append(df)
  
  if all_data:
      combined_df = pd.concat(all_data, ignore_index=True)
  else:
      print("No matching CSVs found.")
      exit(1)

bg_colors = [
    "#D9D9D9",
    "#9C9C9C",
    "#D9D9D9",
    "#9C9C9C"
]

# Create the plot
value_column = 'IPC_IMPROVEMENT'
plt.figure(figsize=(10, 6))
ax = sns.boxplot(data=combined_df, x='benchsuite', y=value_column, hue='setup', showfliers=False, palette="Set2")

xticks = ax.get_xticks()
i = 0
for x in xticks:
    ax.axvspan(
        x - 0.5, x + 0.5,
        color=bg_colors[i%len(bg_colors)],
        alpha=0.4,
        zorder=0
    )
    i += 1

ax.set_axisbelow(True)
ax.grid(True, which='major', linestyle='--', alpha=0.5)
plt.title(f'Boxplot of {value_column} per Benchsuite and Setup')
plt.xlabel('Benchsuite')
plt.ylabel('IPC IMPROVEMENT (%)')
plt.legend(title='Setup')
plt.tight_layout()
plt.savefig(f'./{figures_dir}/{output_file}_l2c-{l2c_size}_llc-{llc_size}_filter-{filter}.pdf')  # Save the plot
#plt.show()
