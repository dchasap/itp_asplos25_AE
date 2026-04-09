
import stats
import plotting
import pandas as pd
from scipy.stats import gmean


xlabels = {	
			'qualcomm_srv_ap': "Qualcomm Server Workloads",
			'selected_qualcomm_srv_ap': "Qualcomm Server Workloads",
			'smt_qualcomm_srv_ap': "SMT Qualcomm Server Workloads",
			'spec': "SPEC CPU 2006/2017",
      'google_srv': "Google Server Workloads",
			'debug': "srv105_ap"
		}

#FIGURES_DIR = "./figures"


def get_data_files(_data_files, _tags, filter_baseline=False):
	
	input_data_files = []
	tags = []
	i = 0
	for file in _data_files:
		if filter_baseline and "BASELINE" in file:
			i += 1
			continue
		else:
			input_data_files.append(file)
			tags.append(_tags[i])

		i += 1

	return input_data_files, tags


def get_baseline_files(_data_files, _tags):
	
	input_data_files = []
	tags = []
	i = 0
	for file in _data_files:
		if "BASELINE" in file:
			input_data_files.append(file)
			tags.append(_tags[i])
		else:
			continue

		i += 1

	return input_data_files, tags


def update_configuration(orig_conf, new_conf):
	
	for key in orig_conf:
		#print("looking for key: " + key)
		if key == 'plot_type':
			#print("skipping " + key)
			continue
		if key in new_conf:
			#print("updating key: " + key + " from " + str(orig_conf[key]) + " to " + str(new_conf[key]))
			if type(orig_conf[key]) == int:
				orig_conf[key] = int(new_conf[key])
			elif type(orig_conf[key]) == float:
				orig_conf[key] = float(new_conf[key])
			else:
				orig_conf[key] = new_conf[key]
	
	return orig_conf


def gen_plot(benchsuite, _tags, data_files, figure_name, figure_type, file_type, figure_dir, extra_conf=None):

	if extra_conf is not None:
		plotting.plot_conf = update_configuration(plotting.plot_conf, extra_conf)

	if (figure_type == "ipc"): 
		
		input_data_files = []
		input_baseline_files = []
		tags = []
		i = 0
		print(_tags)
		for file in data_files:
			if "BASELINE" in file:
				input_baseline_files.append(file)
				#print(file)
				#print(_tags[i])
			else:
				input_data_files.append(file)
				#print(i)
				#print(file)
				#print(_tags[i])
				tags.append(_tags[i])

			i += 1

		#tags = tags[1:] # this only works if baseline is only one file and is the first
		#print(len(tags))

		cache_type = "cpu0_STLB"
		op_type = "TOTAL"

		baseline_df = stats.load_df(input_baseline_files, tags, cache_type, op_type)
		data_df = stats.load_df(input_data_files, tags, cache_type, op_type)


		data_df = stats.compute_variation(baseline_df, data_df, tags, 'IPC', 'IPC_IMPROVEMENT')

		medians_df = data_df.groupby('tag', as_index=False)['IPC_IMPROVEMENT'].median()

		top10 = medians_df.sort_values('IPC_IMPROVEMENT', ascending=False).head(10)
		print(top10)

		#for bench in data_df['benchmarks'].to_list():
		#	print("\"" + bench + ".champsimtrace.xz\",")

		means_df = stats.compute_mean(data_df, tags, 'IPC_IMPROVEMENT', 'mean')
		print(means_df)

		#print(data_df['benchmarks'].str.split('.').str[0])
		data_df['benchmarks'] = data_df['benchmarks'].str.split('.').str[0]
	
		plotting.plot_conf['plot_type'] = 'box'
		#plotting.plot_conf['xlabel'] = xlabels[benchsuite]
		#plotting.plot_conf['xlabel'] = "Memory Access Frequency"
		#plotting.plot_conf['xlabel'] = "TXVC Size"
		plotting.plot_conf['ylabel'] = "IPC Improvement (%)"
		#plotting.plot_conf['ymax'] = 25
		#plotting.plot_conf['ymin'] = 0
		#plotting.plot_conf['ystep'] = 2.5
		plotting.plot_conf['plot_width'] = 9
		plotting.plot_conf['plot_height'] = 3
		plotting.plot_conf['rotation'] = 45
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['legend_cols'] = 5
		plotting.plot_conf['legend_yoffset'] = 0.5
		plotting.plot_conf['legend_xoffset'] = 1.2

		output_file = figure_dir + "/" + figure_name + "_ipc_" + benchsuite + "." + file_type
		print(output_file)
		plotting.plot_stat(data_df, tags, 'IPC_IMPROVEMENT', output_file)


		#df = data_df

		#top_n = df.sort_values('IPC_IMPROVEMENT', ascending=False).head(200)
		#print(len(top_n))

		#for bench in top_n['benchmarks'].to_list():
		#	print("\"" + bench + ".champsimtrace.xz\",") 

		#print(len(df))
		#df = df[df['IPC_IMPROVEMENT'] >= 0.1]
		#print(len(df))
		#df = df[df['IPC_IMPROVEMENT'] >= 0.2]
		#print(len(df))
		#print(df['benchmarks'].to_list())
		#df = df[df['IPC_IMPROVEMENT'] >= 0.3]
		#print(len(df))

	if (figure_type == "mpki"):
	
		input_data_files, tags = get_data_files(data_files, _tags, False)

		cache_types=["cpu0_L1I", "cpu0_L1D", "cpu0_L2C", "LLC"]
		cache_types=["cpu0_L2C", "TXVC", "LLC"]
		#cache_types=["LLC"]	
		op_type = "TOTAL"

		df = stats.load_df(input_data_files, tags, cache_types, op_type)

		stat_names = [ "MPKI" ] 
		# compute means
		means = {}
		for stat in stat_names:
				means[stat] = []
		caches = []
		confs = []
		means_hr = []
		for cache in cache_types:
			for tag in tags:
				for stat in stat_names:
					mean = gmean(df.loc[(df['tag'] == tag) & (df['CACHE'] == cache)][stat])
					means[stat].append(mean)
				caches.append(cache)
				confs.append(tag)

		means_df = pd.DataFrame({'benchmarks':'geomean', 'cache':caches, 'tag': confs, 'mean':means['MPKI']})
		for stat in stat_names:
			means_df[stat] = means[stat]
		print(means_df)


		plotting.plot_conf['plot_type'] = 'barplot'
		plotting.plot_conf['plot_width'] = 16
		plotting.plot_conf['plot_height'] = 1.8
		plotting.plot_conf['fontsize'] = 14
		plotting.plot_conf['ylabel'] = "MPKI"
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['extra_xlabels'] = True

		output_file = figure_dir + "/" + figure_name + "_mpki_" + benchsuite + "." + file_type
		print(output_file)
		plotting.plot_average_multiple_caches(input_data_files, means_df, tags, 
																					cache_types, op_type, "MPKI", 
																					output_file)

	
	if (figure_type == "mpki_breakdown"):
		
		input_data_files, tags = get_data_files(data_files, _tags, False)

		#cache_types=["cpu0_L1I", "cpu0_L1D", "cpu0_L2C", "LLC"]
		cache_types=[ "cpu0_ITLB", "cpu0_DTLB", "cpu0_STLB", "cpu0_L1D", "cpu0_L1I", "cpu0_L2C", "TXVC", "LLC" ]
		op_type = "TOTAL"

		df = stats.load_df(input_data_files, tags, cache_types, op_type)

		stat_names = [ "iMPKI", "dMPKI", "itMPKI", "dtMPKI" ] 
		# compute means
		means = {}
		for stat in stat_names:
				means[stat] = []
		caches = []
		confs = []
		means_hr = []
		for cache in cache_types:
			for tag in tags:
				for stat in stat_names:
					mean = gmean(df.loc[(df['tag'] == tag) & (df['CACHE'] == cache)][stat])
					means[stat].append(mean)
				caches.append(cache)
				confs.append(tag)

		means_df = pd.DataFrame({'benchmarks':'geomean', 'cache':caches, 'tag': confs})
		for stat in stat_names:
			means_df[stat] = means[stat]
		print(means_df)


		plotting.plot_conf['plot_type'] = 'barplot'
		plotting.plot_conf['plot_width'] = 16
		plotting.plot_conf['plot_height'] = 1.8
		plotting.plot_conf['fontsize'] = 14
		plotting.plot_conf['ylabel'] = "MPKI"
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['extra_xlabels'] = True

		for cache_type in cache_types:

			means_df_single_cache = means_df.loc[(means_df['cache'] == cache_type)]

			plotting.plot_conf['plot_width'] = 8
			plotting.plot_conf['plot_height'] = 1.8
			plotting.plot_conf['fontsize'] = 18

			output_file = figure_dir + "/" + figure_name + "_" + cache_type + "_mpki_breakdown_" + benchsuite + "." + file_type
			print(output_file)
			plotting.plot_average_single_cache(	input_data_files, means_df_single_cache, tags, 
																					cache_types, op_type, stat_names, output_file)	


	if (figure_type == "hit_ratio"):
	
		input_data_files, tags = get_data_files(data_files, _tags, True)

		cache_types=["TXVC", "cpu0_L1D", "cpu0_L2C", "LLC"]
		op_type = "TOTAL"

		df = stats.load_df(input_data_files, tags, cache_types, op_type)

		df = stats.compute_stat(df, "HIT_RATIO")

		stat_names = [ "HIT_RATIO" ] 
		# compute means
		means = {}
		for stat in stat_names:
				means[stat] = []
		caches = []
		confs = []
		means_hr = []
		for cache in cache_types:
			for tag in tags:
				for stat in stat_names:
					mean = gmean(df.loc[(df['tag'] == tag) & (df['CACHE'] == cache)][stat])
					means[stat].append(mean)
				caches.append(cache)
				confs.append(tag)

		means_df = pd.DataFrame({'benchmarks':'geomean', 'cache':caches, 'tag': confs, 'mean':means['HIT_RATIO']})
		for stat in stat_names:
			means_df[stat] = means[stat]
		print(means_df)


		plotting.plot_conf['plot_type'] = 'barplot'
		plotting.plot_conf['plot_width'] = 16
		plotting.plot_conf['plot_height'] = 1.8
		plotting.plot_conf['fontsize'] = 14
		plotting.plot_conf['ylabel'] = "Hit Ratio(%)"
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['extra_xlabels'] = True

		output_file = figure_dir + "/" + figure_name + "_hit_ratio_" + benchsuite + "." + file_type
		print(output_file)
		plotting.plot_average_multiple_caches(input_data_files, means_df, tags, 
																					cache_types, op_type, "HIT_RATIO", 
																					output_file)

	if (figure_type == "miss_rate"):
	
		input_data_files, tags = get_data_files(data_files, _tags, True)

		cache_types=["TXVC" ]
		op_type = "TOTAL"

		df = stats.load_df(input_data_files, tags, cache_types, op_type)

		df = stats.compute_stat(df, "MISS_RATE")

		stat_names = [ "MISS_RATE" ] 
		# compute means
		means = {}
		for stat in stat_names:
				means[stat] = []
		caches = []
		confs = []
		means_hr = []
		for cache in cache_types:
			for tag in tags:
				for stat in stat_names:
					mean = gmean(df.loc[(df['tag'] == tag) & (df['CACHE'] == cache)][stat])
					means[stat].append(mean)
				caches.append(cache)
				confs.append(tag)

		means_df = pd.DataFrame({'benchmarks':'geomean', 'cache':caches, 'tag': confs, 'mean':means['MISS_RATE']})
		for stat in stat_names:
			means_df[stat] = means[stat]
		print(means_df)


		plotting.plot_conf['plot_type'] = 'barplot'
		plotting.plot_conf['plot_width'] = 16
		plotting.plot_conf['plot_height'] = 1.8
		plotting.plot_conf['fontsize'] = 14
		plotting.plot_conf['ylabel'] = "Miss Rate(%)"
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['extra_xlabels'] = True

		output_file = figure_dir + "/" + figure_name + "_miss_rate_" + benchsuite + "." + file_type
		print(output_file)
		plotting.plot_average_multiple_caches(input_data_files, means_df, tags, 
																					cache_types, op_type, "MISS_RATE", 
																					output_file)
		

	if (figure_type == "cache_filter_accuracy"):
		#print(data_files)
		#print(_tags)
		input_data_files, tags = get_data_files(data_files, _tags, True)

		cache_types=["TXVC"]
		op_type = "TOTAL"

		df = stats.load_df(input_data_files, tags, cache_types, op_type)

		stat_names = [ "CACHE_FILTER_ACCURACY" ] 
		# compute means
		means = {}
		for stat in stat_names:
				means[stat] = []
		caches = []
		confs = []
		means_hr = []
		for cache in cache_types:
			for tag in tags:
				for stat in stat_names:
					mean = gmean(df.loc[(df['tag'] == tag) & (df['CACHE'] == cache)][stat])
					means[stat].append(mean)
				caches.append(cache)
				confs.append(tag)

		means_df = pd.DataFrame({'benchmarks':'geomean', 'cache':caches, 'tag': confs, 'mean':means['CACHE_FILTER_ACCURACY']})
		for stat in stat_names:
			means_df[stat] = means[stat]
		print(means_df)


		plotting.plot_conf['plot_type'] = 'bar'
		plotting.plot_conf['plot_width'] = 16
		plotting.plot_conf['plot_height'] = 1.8
		plotting.plot_conf['fontsize'] = 14
		plotting.plot_conf['ylabel'] = "Accuracy(%)"
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['extra_xlabels'] = True

		output_file = figure_dir + "/" + figure_name + "_cache_filter_accuracy_" + benchsuite + "." + file_type
		print(output_file)
		#plotting.plot_stat(df, tags, 'CACHE_FILTER_ACCURACY', output_file)
		plotting.plot_average_single_cache(input_data_files, means_df, tags, cache_types, 
																			op_type, stat_names, output_file)


	if (figure_type == "txvc_bypass"):
		
		input_data_files, tags = get_data_files(data_files, _tags, True)

		cache_types=["TXVC"]
		op_type = "TOTAL"

		df = stats.load_df(input_data_files, tags, cache_types, op_type)

		df = stats.compute_stat(df, "TXVC_BYPASS_RATIO")
		stat_names = [ "TXVC_BYPASS_RATIO" ] 
		# compute means
		means = {}
		for stat in stat_names:
				means[stat] = []
		caches = []
		confs = []
		means_hr = []
		for cache in cache_types:
			for tag in tags:
				for stat in stat_names:
					mean = gmean(df.loc[(df['tag'] == tag) & (df['CACHE'] == cache)][stat])
					means[stat].append(mean)
				caches.append(cache)
				confs.append(tag)

		means_df = pd.DataFrame({'benchmarks':'geomean', 'cache':caches, 'tag': confs, 'mean':means['TXVC_BYPASS_RATIO']})
		for stat in stat_names:
			means_df[stat] = means[stat]
		print(means_df)

		plotting.plot_conf['plot_type'] = 'bar'
		plotting.plot_conf['plot_width'] = 16
		plotting.plot_conf['plot_height'] = 1.8
		plotting.plot_conf['fontsize'] = 14
		plotting.plot_conf['ylabel'] = "Bypasses"
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['extra_xlabels'] = True

		output_file = figure_dir + "/" + figure_name + "_txvc_bypass_" + benchsuite + "." + file_type
		print(output_file)
		#plotting.plot_stat(df, tags, 'CACHE_FILTER_ACCURACY', output_file)
		plotting.plot_average_single_cache(input_data_files, means_df, tags, cache_types, 
																			op_type, stat_names, output_file)

	if (figure_type == "occupancy"):
	
		input_data_files = []

		for data_file in data_files:

			if (data_file == ""): continue

			input_data_files.append("./stats/" + benchsuite + "_" + data_file + ".csv")	

		tags = [
							"32KB",
							"256KB"
					]
		
		cache_types=["cpu0_L1D_VC"]
		op_type = "TOTAL"
		
		data_df = stats.load_df(input_data_files, tags, cache_types, op_type)

		means_df = stats.compute_mean(data_df, tags, 'MAX_OCCUPANCY', 'geomean')

		plotting.plot_conf['plot_type'] = 'box'
		plotting.plot_conf['plot_width'] = 9
		plotting.plot_conf['plot_height'] = 3
		plotting.plot_conf['fontsize'] = 11
		plotting.plot_conf['ylabel'] = "OCCUPANCY (%)"
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['show_xticks'] = False

		output_file = FIGURES_DIR + "/fig_vc_occupancy_" + benchsuite + ".pdf"
		print(FIGURES_DIR + "/fig_vc_occupancy_" + benchsuite + ".pdf")
		#plotting.plot_stat(means_df, tags, 'mean', output_file)
		plotting.plot_stat(data_df, tags, 'MAX_OCCUPANCY', output_file)
		

	if (figure_type == "plot_reuse_dist"):
		
		input_data_files = []
		#data_files = data_files.replace('\t', '')
		#data_files = data_files.split('\n')
		print("reust_dist option:")
		print(data_files)
		for data_file in data_files:

			if (data_file == ""): continue
			print(data_file)	
			#input_data_files.append(".//" + benchsuite + "_" + data_file + "_recall_dist_TXVC.csv")	
			input_data_files.append(data_file)	

		tags = 	[
							"TXVC"
						]

		data_df = stats.load_reuse_dist_df(input_data_files, tags)
		
		plotting.plot_conf['plot_type'] = 'line'
		plotting.plot_conf['xlabel'] = "x"
		plotting.plot_conf['ylabel'] = "y"
		plotting.plot_conf['plot_width'] = 9
		plotting.plot_conf['plot_height'] = 3
		plotting.plot_conf['rotation'] = 20
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['legend_cols'] = 5
		plotting.plot_conf['legend_yoffset'] = 0.5
		plotting.plot_conf['legend_xoffset'] = 1.2

		output_file = FIGURES_DIR + "/fig_txvc_recall_distance_doa2_" + benchsuite + "." + file_type
		print(FIGURES_DIR + "/fig_txvc_recall_distance_doa2_" + benchsuite + "." + file_type)
		plotting.plot_reuse_distance(data_df, tags, output_file)

## end gen_plot


