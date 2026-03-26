#!/usr/bin/env python3

import workloads
import matplotlib.pyplot as plt
import pandas as pd
import seaborn 

#data_dir = './data/txvc_vs_l2c_budget_analysis'
data_dir = './data/tx-sets_vs_l2c_budget_analysis'
figures_dir = './figures'
output_file = 'l2c_set_access_dist'

import plotting

benchmarks = workloads.get_benchmark_names('selected_qualcomm_srv_ap')
#benchmarks = workloads.get_benchmark_names('debug')

plot_width = 8.0
plot_height = 6.0
fig, axes = plt.subplots(nrows=1, ncols=1, figsize=(plot_width, plot_height))
#benchmarks = [ 'srv105_ap' ]

configurations = [ 'BASELINE-L2C-1536KB' ]
#configurations = [ 'L2C-1536-TX-SETS-128' ]
#configurations = [ 'BASELINE-L2C-2048KB' ]
#configurations = [ 'L2C-2048-TX-SETS-64']
#configurations = [ 'L2C-2048-TX-SETS-128']
#configurations = [ 'L2C-2048-TX-SETS-256' ]
#configurations = [ 'L2C-2048-TX-SETS-512' ]

for conf in configurations:
  print(conf)
  
  csv_files = [f'{bench}_{conf}_set_access_stats_cpu0_L2C.csv' for bench in benchmarks]
  df = pd.DataFrame() 

  for csv_file in csv_files:
    df = pd.concat([df, pd.read_csv(data_dir + '/' + conf + '/' + csv_file, header=0)]) 


  # Group the data by the number of sets and calculate the mean accesses
  df = df.groupby('set')['accesses']
  mean_accesses = df.mean()
  
  #print(df)

  # Plot the distribution of the data
  mean_accesses.plot(y='accesses', x='sets')
  #plt.line(df['set'], df['accesses'])
  plt.xlabel('Set#')
  plt.ylabel('Accesses')
  plt.title('')
  #plt.show()

  #plt.grid(True, linestyle='--', alpha=0.5, zorder=1)
  #plt.title('Memory address count for different memory access frequency')
  #plt.ylabel('#Addresses')
  #plt.xlabel('Frequency')

  #plt.show()
  plt.savefig(figures_dir + '/' + output_file + "_" + conf + ".pdf", bbox_inches='tight')
