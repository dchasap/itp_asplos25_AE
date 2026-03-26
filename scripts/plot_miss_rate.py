#!/usr/bin/env python3

import workloads
import matplotlib.pyplot as plt
import pandas as pd
import seaborn 


df = pd.DataFrame({'setup': [ 'belady-opt-64KB', 'lfu-64KB', 'learned-64KB', 'belady-opt-128KB', 'lfu-128KB', 'learned-128KB'  ], 'miss_rate': [ 49.6, 73.9, 49.7, 35.3, 58.1, 35.4 ]})

df_128KB = pd.DataFrame({'benchmark': [], 'miss_rate': []})

plt.figure(figsize=(12,4))
ax = plt.gca()
bars = ax.bar(df['setup'], df['miss_rate'], color='grey', zorder=2)
ax.grid(True, linestyle='--', alpha=0.5, zorder=1)

plt.xlabel('Replacement')
plt.ylabel('Miss Rate (%)')
plt.title('')

#bg_colors = [ "#D9D9D9", "#9C9C9C" , "#D9D9D9", "#9C9C9C" ]
bg_colors = [ "#A5C792", "#C79292", "#82C25D", "#CA5D5D" ]
#"#FCDADA"

# How many bars / boxes per group
group_size = 3   # change to 4 or 5 in your case
n_boxes = len(df)

# Add background shading by spanning the x-axis regions
for i in range(0, n_boxes, group_size):
    group_idx = i // group_size
    color_idx = group_idx % len(bg_colors)
    # span from just left of the first bar in the group to just right of the last
    ax.axvspan(i - 0.5, i + group_size - 0.5,
               color=bg_colors[color_idx], alpha=0.5, zorder=0)

output_file = 'miss_rate_comparison.pdf'
plt.savefig('./figures/' + output_file, bbox_inches='tight')