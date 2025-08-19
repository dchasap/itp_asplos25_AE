#!/usr/bin/env python3

import workloads
import matplotlib.pyplot as plt
import pandas as pd
import seaborn 

data_dir = './data/txvc_freq_analysis/TXVC-Inf_MFU-FREQ-2'
figures_dir = './figures'

import plotting

benchmarks = workloads.get_benchmark_names('selected_qualcomm_srv_ap')

plot_width = 8.0
plot_height = 6.0
fig, axes = plt.subplots(nrows=1, ncols=1, figsize=(plot_width, plot_height))


for bench in benchmarks:
  #break;
  df = pd.read_csv(data_dir + '/' + bench + '_TXVC-Inf_MFU-FREQ-2__.csv', names=['address'], header=0)
  
  # Create a DataFrame with the number of occurrences for each address
  address_counts = df['address'].value_counts().reset_index()
  address_counts.columns = ['address', 'count']
  #address_counts = address_counts.sort_values(by='count', ascending=False)
  #print("unique_addresses:", len(address_counts['address'].unique()))
  #address_counts = address_counts.nlargest(1024, 'count')
  #print(address_counts)
  #address_counts = address_counts.query('count > 500')
  #print(len(address_counts))
  j = 0
  for i in [ 500, 400, 300, 200, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 8, 6, 4, 2, 1 ]:
    _address_counts = address_counts.query('count >= ' + str(i))
    average_num_elements[j] += len(_address_counts)
    j += 1
  
  #print(num_of_elems)
  #address_counts = address_counts.query('count > 300')
  #address_counts = address_counts.query('count > 200')
  #address_counts = address_counts.query('count > 100')
  #address_counts = address_counts.query('count > 90')
  #address_counts = address_counts.query('count > 80')
  #address_counts = address_counts.query('count > 70')
  #address_counts = address_counts.query('count > 60')
  #address_counts = address_counts.query('count > 50')
  #address_counts = address_counts.query('count > 40')
  #address_counts = address_counts.query('count > 30')
  #address_counts = address_counts.query('count > 20')
  #address_counts = address_counts.query('count > 10')
  #address_counts = address_counts.query('count > 2')
  #average_count += len(address_counts)
  
  #print(df['address'])
  #plt.hist(df['address'])
  #plt.plot(address_counts['address'], address_counts['count'], color='blue')
  #plt.grid(True)
  #plt.legend()
  #plt.title('Memory address access frequency for ' + bench)
  #plt.xlabel('Memory Address')
  #plt.ylabel('Frequency')
  #plt.xticks([])

  #plt.show()
  #exit()
  #plt.savefig(figures_dir + '/' + bench + '_mem_access_hist.png', bbox_inches='tight')

for i in range(0, len(average_num_elements)):
  average_num_elements[i] = average_num_elements[i] / len(benchmarks)

print(average_num_elements)

#average_num_elements = [60.464646464646464, 147.4848484848485, 306.27272727272725, 591.5555555555555, 1352.090909090909, 1493.2929292929293, 1661.3333333333333, 1857.7272727272727, 2108.343434343434, 2433.4343434343436, 2884.040404040404, 3510.4848484848485, 4502.545454545455, 6692.141414141414, 16822.737373737375]

df = pd.DataFrame({'Frequency': [ '500', '400', '300', '200', '100', '90', '80', '70', '60', '50', '40', '30', '20', '10', '8', '6', '4', '2', '1' ], '#Addresses': average_num_elements}) 

plt.bar(df['Frequency'], df['#Addresses'], align='center', alpha=0.8, color='grey', edgecolor='black', linewidth=1, zorder=2)

for i, value in enumerate(df['#Addresses']):
    plt.text(i, value + 0.1, str(value).split('.')[0], ha='center', va='bottom', rotation=90)

#plt.legend()
plt.grid(True, linestyle='--', alpha=0.5, zorder=1)
plt.title('Memory address count for different memory access frequency')
plt.ylabel('#Addresses')
plt.xlabel('Frequency')

#plt.show()
plt.savefig(figures_dir + '/mem_access_hist.pdf', bbox_inches='tight')

# > 1 -> 2936.67
# > 100 -> 1248.09 
# > 200 -> 514
# > 300 -> 244
# > 400 -> 
# > 500 -> 4