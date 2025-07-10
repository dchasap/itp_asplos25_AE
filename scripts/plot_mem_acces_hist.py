#!/usr/bin/env python3

import workloads
import matplotlib.pyplot as plt
import pandas as pd

data_dir = './data/txvc_mem_access_hist/TXVC-4KB'
figures_dir = './figures'

import plotting

benchmarks = workloads.get_benchmark_names('selected_qualcomm_srv_ap')

plot_width = 8.0
plot_height = 6.0
fig, axes = plt.subplots(nrows=1, ncols=1, figsize=(plot_width, plot_height))

average_count = 0;
for bench in benchmarks:

  df = pd.read_csv(data_dir + '/' + bench + '_TXVC-4KB_txvc_mem_trace.csv', names=['address'])
  
  # Create a DataFrame with the number of occurrences for each address
  address_counts = df['address'].value_counts().reset_index()
  address_counts.columns = ['address', 'count']
  address_counts = address_counts.sort_values(by='count', ascending=False)
  print("unique_addresses:", len(address_counts['address'].unique()))
  #address_counts = address_counts.nlargest(1024, 'count')
  print(address_counts)
  #address_counts = address_counts.query('count > 400')
  print(len(address_counts))
  #average_count += len(address_counts)
  
  #print(df['address'])
  #plt.hist(df['address'])
  plt.plot(address_counts['address'], address_counts['count'], color='blue')
  plt.grid(True)
  #plt.legend()
  plt.title('Memory address access frequency for ' + bench)
  plt.xlabel('Memory Address')
  plt.ylabel('Frequency')
  plt.xticks([])

  plt.show()
  exit()
  #plt.savefig(figures_dir + '/' + bench + '_mem_access_hist.png', bbox_inches='tight')

print(average_count / len(benchmarks))
# > 1 -> 2936.67
# > 100 -> 1248.09 
# > 200 -> 514
# > 300 -> 244
# > 400 -> 
# > 500 -> 49