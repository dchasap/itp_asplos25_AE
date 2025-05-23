
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from matplotlib.patches import PathPatch
from matplotlib.patches import Path
from matplotlib.colors import ListedColormap
from matplotlib.ticker import MultipleLocator
import seaborn as sns

#default plot parameters, user can overwrite them
plot_conf = {   
                'plot_type': 'scatter',
                'plot_width': 9,
                'plot_height': 3,
								'ylabel': None, 
								'xlabel': None,
								'xmin': None,
								'xmax': None,
								'xstep': None,
								'ymin': None,
								'ymax': None,
								'ystep': None,
								'show_xticks': True,
                'rotation': 0,
                'switch_yaxis': False, 
								'fontsize': 11, 
								'legend_cols': 8, 
								'legend_yoffset': 0, 
								'legend_xoffset': 0,
                'show_legend': False,
								'alpha': 1.0 
						}


def plot(data, x, y, hue, axes):

	plot_type = plot_conf['plot_type']
	if (plot_type == 'histogram'):
		ax = sns.histplot(	data=data, xz=x, y=y, hue=hue, linestyles='', 
							kde=True, ax=axes)
	elif (plot_type == 'violin'):
		ax = sns.violinplot(data=data, y=y, x=hue, linewidth=1, scale='count', ax=axes, color='#aeaeae')
		i = 0
		while (i < len(ax.collections)):
			if (i % 2 == 0):
				ax.collections[i].set_edgecolor('black')
			else:
				ax.collections[i].set_edgecolor('black')
				ax.collections[i].set_linewidth(4)
			i = i + 1
	elif (plot_type == 'box'):
		PROPS = {
			'boxprops':{'facecolor':'#aeaeae', 'edgecolor':'black'},
			'medianprops':{'color':'black'},
			'whiskerprops':{'color':'black'},
			'capprops':{'color':'black'}
		}
		ax = sns.boxplot(data=data, y=y, x=hue, linewidth=1, showfliers=False, ax=axes, color='#aeaeae', **PROPS)
	elif (plot_type == 'swarm'):
		ax = sns.swarmplot(data=data, y=y, x=hue, size=1.5, legend=False, ax=axes, color='#aeaeae')

	elif (plot_type == 'bar'):
#		ax = sns.barplot(	data=data, x=x, y=y, hue=hue, width=0.8,
#							linewidth=1, edgecolor='black', ax=axes)
		ax = sns.barplot(	data=data, x=x, y=y, hue=hue, width=0.8,
							linewidth=1, ax=axes)

	elif (plot_type == 'scatter'):
		#marker_styles = ['o', 'x', '1', '+', '*', 'v', '<', '>', 'D', '.', '1']
		marker_styles = ['s', 'v', 'o', '^', 'P', 'X']
		ax = sns.scatterplot( data=data, x=x, y=y, hue=hue, style=hue, 
													markers=marker_styles, edgecolor='black', alpha=plot_conf['alpha'], ax=axes)
		#ax = sns.pointplot( data=data, x=x, y=y, hue=hue, linestyles='', 
		#					scale=0.5, ax=axes)
	elif (plot_type == 'line'):
		ax = sns.lineplot( data=data, x=x, y=y, hue=hue, style=hue)
	else:
		print(plot_conf['plot_type'] + " is not supported!")
		exit()


	if (plot_conf['show_legend']):
		ax.legend(	loc='center', ncol=plot_conf['legend_cols'], 
								bbox_to_anchor=(plot_conf['legend_yoffset'], plot_conf['legend_xoffset']), frameon=False)
	else:
		if (ax.get_legend() != None):
			ax.get_legend().remove()

	fontsize=plot_conf['fontsize']
	ax.set_ylabel(plot_conf['ylabel'], fontsize=fontsize)
	ax.set_xlabel(plot_conf['xlabel'], fontsize=fontsize)

	if (plot_conf['ymin'] != None):	
		ax.set_ylim(bottom=plot_conf['ymin'])
	if (plot_conf['ymax'] != None):
		ax.set_ylim(top=plot_conf['ymax'])
	if (plot_conf['xstep'] != None):
		ax.xaxis.set_major_locator(MultipleLocator(plot_conf['xstep']))
	if (plot_conf['xmin'] != None):
		ax.set_xlim(left=plot_conf['xmin'])
	if (plot_conf['xmax'] != None):
		ax.set_xlim(right=plot_conf['xmax'])
	if (plot_conf['ystep'] != None):
		ax.yaxis.set_major_locator(MultipleLocator(plot_conf['ystep']))


	if plot_conf['switch_yaxis']:
		ax.yaxis.set_label_position("right")
		ax.yaxis.tick_right()
	#if plot_conf['plot_type'] != 'violin' and plot_conf['plot_type'] != 'bar':
	#	ax.set_xticks([])
	#print(ax.get_xmajorticklabels())
	#ax.set_xticklabels(	ax.get_xmajorticklabels(), rotation=plot_conf['rotation'], 
	#										horizontalalignment='right')
	plt.setp(ax.get_xticklabels(), rotation=plot_conf['rotation'], ha="right")

	#ax.tick_params(axis='x', rotation=plot_conf['rotation'], horizontalalignment='right')

	if not plot_conf['show_xticks']:
		ax.set_xticks([])

	plt.yticks(fontsize=fontsize)
	plt.xticks(fontsize=fontsize)

	ax.set_axisbelow(True)
	ax.grid(visible=True, axis='y', color='grey', alpha=0.5, linestyle='--', linewidth=1.5)

	return ax


def plot_stat(df, tags, stat_name, output_file):

    plot_width = plot_conf['plot_width']
    plot_height = plot_conf['plot_height']
    fig, axes = plt.subplots(	nrows=1, ncols=1, 
								figsize=(plot_width, plot_height))

#    sns.set_palette(sns.color_palette(['#999999', '#777777', '#555555', '#333333']))

    axes = plot(df, x='benchmarks', y=stat_name, hue='tag', axes=axes)
    
    fig.savefig(output_file, bbox_inches='tight')


def plot_stat_w_means(df, means_df, tags, output_file):
 
    plot_width = plot_conf['plot_width']
    plot_height = plot_conf['plot_height']
    fig, axes = plt.subplots(	nrows=1, ncols=2, 
								figsize=(plot_width, plot_height+.1),
								gridspec_kw={	'width_ratios': [plot_width-2, 2], 
												'height_ratios': [plot_height]})

    #sns.set_palette(sns.color_palette(['#999999', '#777777', '#555555', '#333333']))

    ax = plot(df, x='benchmarks', y='IPC_IMPROVEMENT', hue='tag', axes=axes[0])

    plot_conf['plot_type'] = 'bar'
    plot_conf['show_legend'] = False
    ax = plot(means_df, x='benchmarks', y='mean', hue='tag', axes=axes[1])
   
    plt.subplots_adjust(wspace=0.25,hspace=0.001)
    
    fig.savefig(output_file, bbox_inches='tight')
   


def plot_reuse_distance(df, tags, output_file):

    plot_width = plot_conf['plot_width']
    plot_height = plot_conf['plot_height']
    fig, axes = plt.subplots(	nrows=1, ncols=1, 
								figsize=(plot_width, plot_height))

    #sns.set_palette(sns.color_palette(['#999999', '#777777', '#555555', '#333333']))

    #ax = plot(df, x='reuse_distance', y='frequency', hue='tag', axes=axes)

    #ax.fill_between(df['reuse_distance'], df['frequency'] alpha=0.2)
    last_bucket_freq_1 = round(df.loc[df['tag'] == "L1D_VC"].tail(1)['frequency'].item(), 2)
    last_index = df.loc[df['tag'] == "L1D_VC"].index[-1]
    df = df.drop(index=last_index)
		#last_bucket_freq_2 = round(df.tail(1)['frequency'].item(), 2)
    #df = df[:-1]
    last_bucket_freq_2 = round(df.loc[df['tag'] == "L1D_VC"].tail(1)['frequency'].item(), 2)
    last_index = df.loc[df['tag'] == "L1D_VC-DOA"].index[-1]
    df = df.drop(index=last_index)

    ax = df.loc[df['tag'] == "L1D_VC"].plot.area(x='reuse_distance', y='frequency', color='blue', alpha=0.3, label='L1D_VC')
    ax = df.loc[df['tag'] == "L1D_VC-DOA"].plot.area(x='reuse_distance', y='frequency', color='red', alpha=0.3, label='L1D_VC-DOA', ax = ax)
    #ax = df.loc[df['tag'] == "L1D_TC"].plot.area(x='reuse_distance', y='frequency', color='green', alpha=0.3, label='L2C', ax = ax)
    ax.set_ylabel('Frequency')    
    ax.set_label('Reuse Distance')    

    #ax.set_yscale('log')

    ax.text(512, 1, last_bucket_freq_1, fontsize=11, color='blue', rotation=90)
    ax.text(532, 1, last_bucket_freq_2, fontsize=11, color='red', rotation=90)

    fig = ax.get_figure()

    fig.savefig(output_file, bbox_inches='tight')
 
def plot_reuse_distance_3d(df, tags, output_file):

    plot_width = plot_conf['plot_width']
    plot_height = plot_conf['plot_height']
    fig = plt.figure( figsize=(plot_width, plot_height))
		
    ax = fig.add_subplot(111, projection='3d')

    #sns.set_palette(sns.color_palette(['#999999', '#777777', '#555555', '#333333']))

    #ax = plot(df, x='reuse_distance', y='frequency', hue='tag', axes=axes)

    #ax.fill_between(df['reuse_distance'], df['frequency'] alpha=0.2)
    last_bucket_freq = round(df.tail(1)['frequency'].item(), 2)
    df = df[:-1]

    #ax = df.loc[df['tag'] == "L1D_VC"].plot.area(x='reuse_distance', y='frequency', zdir='benchmark', color='blue', alpha=0.3, label='L1D_VC')
    #ax = df.loc[df['tag'] == "L1D_IVC"].plot.area(x='reuse_distance', y='frequency', color='red', alpha=0.3, label='L1D_IVC', ax = ax)
    print(pd.factorize(df['benchmarks'])[0])
    df['benchmarks'] = pd.factorize(df['benchmarks'])[0]

    df = df.loc[df['reuse_distance'] != 512] 
    df = df.loc[df['tag'] == "L1D_VC"] 
    benchmarks = df['benchmarks'].unique()
    colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
    i = 0
    for bench in benchmarks:
      curr_df = df.loc[df['benchmarks'] == bench]
      plt.plot(ys=curr_df['reuse_distance'], zs=curr_df['frequency'], xs=curr_df['benchmarks'], color=colors[i%8])
      i += 1

    print(ax)
    ax.set_ylabel('Frequency')    
    ax.set_zlabel('Reuse Distance')    
    ax.set_xlabel('Benchmark')
    #ax.set_yscale('log')

    #ax.text(512, 1, 0, last_bucket_freq, fontsize=11, color='red', rotation=90)

    #fig = ax.get_figure()
    plt.show()
    fig.savefig(output_file, bbox_inches='tight')

def plot_average_single_cache(	input_baseline_files, means_df, input_tags, cache_types, 
																op_type, stat_names, output_file):

		plot_width = plot_conf['plot_width']
		plot_height = plot_conf['plot_height']
		fig, axes = plt.subplots(	nrows=1, ncols=1, 
									figsize=(plot_width, plot_height+2))

		sns.set_style('white')

		i = 0
		hatch_idx = 0
		mpki_legend_handle = [None, None, None, None]
		rep_pol_legend_handle = [None, None, None, None, None, None, None, None]
		for stat_name in stat_names:
			ax = sns.barplot(	data=means_df,
									x='cache', y=stat_name, hue='tag', width=0.8, color='grey',
									linewidth=.5, edgecolor='black', ax=axes)

			hatches = ['', '///', 'xx', '\\\\\\']
			#print("hatch_idx: " + str(hatch_idx*11))
			for j, bar in enumerate(ax.patches):
				# Define a custom hatch pattern
				#custom_hatch = PathPatch(Path([(0, 0), (1, 1)], [Path.MOVETO, Path.LINETO]), hatch='xx', alpha=0.5, color='gray')
				#print("j:" + str(j))
				#print("hatch_idx:" + str(hatch_idx))
								#ax.bar_label(bar, label=str(j), fontsize=9)

				#x = bar.get_x() + bar.get_width()/2
				#y = bar.get_y() + bar.get_height()/2
				#ax.annotate(str(j), (x, y), rotation=0, size = 10)

				if ((j == 0) and (hatch_idx == 0)):
					rep_pol_legend_handle[0] = bar
				elif ((j == 1) and (hatch_idx == 0)):
					rep_pol_legend_handle[1] = bar
				elif ((j == 2) and (hatch_idx == 0)):
					rep_pol_legend_handle[2] = bar
				elif ((j == 3) and (hatch_idx == 0)):
					rep_pol_legend_handle[3] = bar
				elif ((j == 4) and (hatch_idx == 0)):
					rep_pol_legend_handle[4] = bar
				elif ((j == 5) and (hatch_idx == 0)):
					rep_pol_legend_handle[5] = bar
				elif ((j == 6) and (hatch_idx == 0)):
					rep_pol_legend_handle[6] = bar
				elif ((j == 7) and (hatch_idx == 0)):
					rep_pol_legend_handle[7] = bar


				#print("bar[" + str(j) + "] -> " + hatches[hatch_idx % 4])
				if (j > 0 and j <= 7 and hatch_idx == 0):
					#print(j)
					mpki_legend_handle[hatch_idx] = bar
					bar.set_hatch(hatches[hatch_idx])
					#print("bar[" + str(j) + "] -> " + hatches[hatch_idx])
				elif (j > 7 and j <= 13 and hatch_idx == 1):
					#print(j)
					mpki_legend_handle[hatch_idx] = bar
					bar.set_hatch(hatches[hatch_idx])
					#print("bar[" + str(j) + "] -> " + hatches[hatch_idx])
				elif (j > 13 and j <= 19 and hatch_idx == 2):
					#print(j)
					mpki_legend_handle[hatch_idx] = bar
					bar.set_hatch(hatches[hatch_idx])
					#print("bar[" + str(j) + "] -> " + hatches[hatch_idx])
				elif (j > 19 and hatch_idx == 3):
					#print(j)
					mpki_legend_handle[hatch_idx] = bar
					bar.set_hatch(hatches[hatch_idx])
					#print("bar[" + str(j) + "] -> " + hatches[hatch_idx])

			hatch_idx += 1


		mpki_breakdown_legend = ax.legend(handles = [mpki_legend_handle[0], mpki_legend_handle[1], mpki_legend_handle[2], mpki_legend_handle[3]], labels = ['dMPKI', 'iMPKI', 'dtMPKI', 'itMPKI'], loc='upper center', ncol=2, frameon=0, bbox_to_anchor=(0.8,1.45), title = "MPKI Breakdown")
		ax.legend(handles = [	rep_pol_legend_handle[0], rep_pol_legend_handle[1], rep_pol_legend_handle[2],
													rep_pol_legend_handle[3], rep_pol_legend_handle[4], rep_pol_legend_handle[5],
													rep_pol_legend_handle[6], rep_pol_legend_handle[7]], 
												labels = input_tags, loc='upper center', 
												ncol=2, frameon=0, bbox_to_anchor=(0.2,1.45), title = "Replacement Policy")
		
		plt.gca().add_artist(mpki_breakdown_legend)
		#mpki_breakdown_legend.legendHandles[0].set_facecolor('white')
		#mpki_breakdown_legend.legendHandles[1].set_facecolor('white')
		#mpki_breakdown_legend.legendHandles[2].set_facecolor('white')
		#mpki_breakdown_legend.legendHandles[3].set_facecolor('white')

			#hatches = itertools.cycle(['/', '//', '+', '-', 'x', '\\', '*', 'o', 'O', '.'])
			#for j, bar in enumerate(ax.patches):
			#	if (j == 10):
			#		bar.set_hatch('////')
			#	elif j == 9:
			#		bar.set_hatch('...')
			#	elif j == 8:
			#		bar.set_hatch('xxx')
			#	elif j == 7:
			#		bar.set_hatch('OO')
			#	elif j == 6:
			#		bar.set_hatch('\\\\\\')
	
			#i += 1

		ax.set_ylabel(plot_conf['ylabel'])
		#ax.legend(loc='center', ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.1))

		ax.set_xticks([])
		ax.tick_params(axis='y', labelsize=11, pad=-3)

		ax.set_axisbelow(True)
		ax.grid(visible=True, axis='y', color='grey', alpha=0.5, linestyle='--', linewidth=1.5)
		sns.despine(top=True, left=False)
		
		fig.savefig(output_file, bbox_inches='tight')
		matplotlib.pyplot.close()



def plot_average_multiple_caches(	input_baseline_files, means_df, input_tags, cache_types, 
																	op_type, stat_name, output_file):

		plot_width = plot_conf['plot_width']
		plot_height = plot_conf['plot_height']
		fig, axes = plt.subplots(	nrows=2, ncols=4, 
									figsize=(plot_width, plot_height+2),
									gridspec_kw={	'width_ratios': [plot_width/4, plot_width/4, plot_width/4, plot_width/4], 
													'height_ratios': [2, plot_height]})

		axes[0][0].remove()
		axes[0][1].remove()
		axes[0][2].remove()
		axes[0][3].remove()

		sns.set_style('white')

		i = 0
#		plt.yticks(fontsize=5)
#		plt.xticks(fontsize=5)

		for cache in cache_types:
			plot_conf['xlabel'] = cache
			plot_conf['ylabel'] = plot_conf['ylabel']

			ax = sns.barplot(	data=means_df.loc[means_df['cache'] == cache],
								x='cache', y=stat_name, hue='tag', width=0.8, color='grey',
								linewidth=.5, edgecolor='black', ax=axes[1][i])

			#hatches = itertools.cycle(['/', '//', '+', '-', 'x', '\\', '*', 'o', 'O', '.'])
			for j, bar in enumerate(ax.patches):
				if (j == 10):
					bar.set_hatch('////')
				elif j == 9:
					bar.set_hatch('...')
				elif j == 8:
					bar.set_hatch('xxx')
				elif j == 7:
					bar.set_hatch('OO')
				elif j == 6:
					bar.set_hatch('\\\\\\')
			#	hatch = next(hatches)
	
			if (i == 0):
				ax.set_ylabel(plot_conf['ylabel'])
				ax.legend(loc='center', ncol=3, frameon=False, bbox_to_anchor=(1.6, 1.3))
			else:
				ax.set_ylabel('')
				ax.get_legend().remove()

			if (cache == "cpu0_L1D"):
				ax.set_xlabel("L1D")
			if (cache == "cpu0_L1D_VC"):
				ax.set_xlabel("L1D_VC")
			elif (cache == "cpu0_L2C"):
				ax.set_xlabel("L2C")
			elif (cache == "cpu0_DTLB"):
				ax.set_xlabel("DTLB")
			elif (cache == "cpu0_STLB"):
				ax.set_xlabel("STLB")
			else:
				ax.set_xlabel("LLC")

			ax.set_xticks([])
			ax.tick_params(axis='y', labelsize=11, pad=-3)

			ax.set_axisbelow(True)
			ax.grid(visible=True, axis='y', color='grey', alpha=0.5, linestyle='--', linewidth=1.5)
			sns.despine(top=True, left=False)

			i += 1		

		fig.savefig(output_file, bbox_inches='tight')
		matplotlib.pyplot.close()


