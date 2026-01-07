#!/usr/bin/env python3

import workloads
import matplotlib.pyplot as plt
import pandas as pd
import seaborn 

data_dir = './data/txvc_l2c_traces/'
figures_dir = './figures'
output_file = 'l2c_mem_access_hist_range4.pdf'

import plotting

benchmarks = workloads.get_benchmark_names('selected_qualcomm_srv_ap')
#benchmarks = workloads.get_benchmark_names('debug')

plot_width = 8.0
plot_height = 6.0
fig, axes = plt.subplots(nrows=1, ncols=1, figsize=(plot_width, plot_height))

average_count = 0;
average_num_elements = []

ranges = [ [1,2], [2,5], [5,10], [10,40], [40,60], [60, 80], [80,100], [100,200], [200,300], [300,400], [400,500], [500,99999] ]
ranges_cat = [ "[1-2)", "[2-5)", "[5-10)", "[10-40)", "[40-60)", "[60-80]", "[80-100)", "[100-200)", "[200-300)", "[300-400)", "[400-500)", "[500-Inf)" ]
ranges = [ [1,100], [100,500], [500, 99999] ]
ranges_cat = [ "[1-100)", "[100-500)", "[500-Inf)" ]
ranges = [ [2,5], [2,10], [2,40], [2,60], [2, 80], [2,100], [2,200], [2,300], [2,400], [2,500], [2,99999] ]
ranges_cat = [ "[2-5)", "[2-10)", "[2-40)", "[2-60)", "[2-80]", "[2-100)", "[2-200)", "[2-300)", "[2-400)", "[2-500)", "[2-Inf)" ]
ranges = [ [2,500], [5,500], [10,500], [40,500], [60,500], [80,500], [100,500], [200,500], [300,500], [400,500]]
ranges_cat = [ "[2-500)", "[5-500)", "[10-500)", "[40-500)", "[60-500]", "[80-500)", "[100-500)", "[200-500)", "[300-500)", "[400-500)"]
#ranges = [ [2,99999], [5,99999], [10,99999], [40,99999], [60,99999], [80,99999], [100,99999], [200,99999], [300,99999], [400,99999], [500,99999]]
#ranges_cat = [ "[2-Inf)", "[5-Inf)", "[10-Inf)", "[40-Inf)", "[60-Inf]", "[80-Inf)", "[100-Inf)", "[200-Inf)", "[300-Inf)", "[400-Inf)", "[500-Inf)"]

#ranges_cat = [f"[{i[0]}-{i[1]})" for i in ranges]
print (ranges_cat)


for i in ranges:
  average_num_elements.append(0)

for bench in benchmarks:
  print(bench)
  #break;
  df = pd.read_csv(data_dir + '/' + bench + '_txvc_mem_trace.csv', names=['address'], header=0)
  
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
  for i in ranges:
    if type(i) is list: # this is for freq ranges case
      _address_counts = address_counts.query('count >= ' + str(i[0]) + ' and count < ' + str(i[1]))
    else:
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
  plt.xticks(rotation=45)

  #plt.show()
  #exit()
  #plt.savefig(figures_dir + '/' + bench + '_mem_access_hist.png', bbox_inches='tight')

for i in range(0, len(average_num_elements)):
  average_num_elements[i] = average_num_elements[i] / len(benchmarks)

print(average_num_elements)

#average_num_elements = [60.464646464646464, 147.4848484848485, 306.27272727272725, 591.5555555555555, 1352.090909090909, 1493.2929292929293, 1661.3333333333333, 1857.7272727272727, 2108.343434343434, 2433.4343434343436, 2884.040404040404, 3510.4848484848485, 4502.545454545455, 6692.141414141414, 16822.737373737375]

df = pd.DataFrame({'Frequency': ranges_cat, '#Addresses': average_num_elements}) 

plt.bar(df['Frequency'], df['#Addresses'], align='center', alpha=0.8, color='grey', edgecolor='black', linewidth=1, zorder=2)

for i, value in enumerate(df['#Addresses']):
    plt.text(i, value + 0.1, str(value).split('.')[0], ha='center', va='bottom', rotation=90)

#plt.legend()
plt.grid(True, linestyle='--', alpha=0.5, zorder=1)
plt.title('Memory address count for different memory access frequency')
plt.ylabel('#Addresses')
plt.xlabel('Frequency')

#plt.show()
plt.savefig(figures_dir + '/' + output_file, bbox_inches='tight')

# > 1 -> 2936.67
# > 100 -> 1248.09 
# > 200 -> 514
# > 300 -> 244
# > 400 -> 
# > 500 -> 4