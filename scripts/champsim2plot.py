
import stats
import plotting
import pandas as pd
import numpy as np
from scipy.stats import gmean
import os
from pathlib import Path


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
		cache_types=["cpu0_L1D", "cpu0_L2C", "LLC"]
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
		
	# Prefetch accuracy: useful / issued (per-tag boxplot)
	if (figure_type == "prefetch_accuracy"):

		input_data_files, tags = get_data_files(data_files, _tags, True)  # filter_baseline=True
		op_type = "PREFETCH"

		# Infer cache level from tag and load data per-tag with appropriate cache type
		df_list = []
		for i, tag in enumerate(tags):
			tag_lower = tag.lower()
			if 'l1d' in tag_lower or 'l1i' in tag_lower:
				cache_type = "cpu0_L1D"
			elif 'llc' in tag_lower:
				cache_type = "LLC"
			else:
				cache_type = "cpu0_L2C"  # default to L2C
			
			df_tag = stats.load_df([input_data_files[i]], [tag], cache_type, op_type)
			df_list.append(df_tag)
		
		df_pref = pd.concat(df_list, ignore_index=True)

		# Compute per-benchmark accuracy
		df_pref['ISSUED'] = pd.to_numeric(df_pref['ISSUED'], errors='coerce').fillna(0)
		df_pref['USEFUL'] = pd.to_numeric(df_pref['USEFUL'], errors='coerce').fillna(0)
		df_pref['PREFETCH_ACCURACY'] = df_pref.apply(lambda r: (100.0 * r['USEFUL'] / r['ISSUED']) if r['ISSUED'] > 0 else float('nan'), axis=1)

		plotting.plot_conf['plot_type'] = 'box'
		plotting.plot_conf['plot_width'] = 8
		plotting.plot_conf['plot_height'] = 3
		plotting.plot_conf['ylabel'] = 'Prefetch Accuracy (%)'
		plotting.plot_conf['rotation'] = 45

		output_file = figure_dir + "/" + figure_name + "_prefetch_accuracy_" + benchsuite + "." + file_type
		print(output_file)
		# Keep only rows with numeric accuracy
		df_plot = df_pref[[ 'benchmarks', 'tag', 'PREFETCH_ACCURACY' ]].copy()
		df_plot = df_plot.dropna(subset=['PREFETCH_ACCURACY'])
		if df_plot.empty:
			print("No PREFETCH_ACCURACY values available to plot.")
		else:
			# Print boxplot statistics
			print("\n=== PREFETCH_ACCURACY Statistics (%) ===")
			for tag in tags:
				tag_data = df_plot[df_plot['tag'] == tag]['PREFETCH_ACCURACY']
				if not tag_data.empty:
					print(f"{tag:20} count={len(tag_data):3d}  min={tag_data.min():6.2f}  q1={tag_data.quantile(0.25):6.2f}  median={tag_data.median():6.2f}  q3={tag_data.quantile(0.75):6.2f}  max={tag_data.max():6.2f}  mean={tag_data.mean():6.2f}")
			print("")
			plotting.plot_stat(df_plot, tags, 'PREFETCH_ACCURACY', output_file)

	# Prefetch coverage proxy: useful / translation misses (per-tag boxplot)
	if (figure_type == "prefetch_coverage"):

		input_data_files, tags = get_data_files(data_files, _tags, True)  # filter_baseline=True
		
		# Load PREFETCH and TRANSLATION data per-tag with appropriate cache type
		df_pref_list = []
		df_trans_list = []
		for i, tag in enumerate(tags):
			tag_lower = tag.lower()
			if 'l1d' in tag_lower or 'l1i' in tag_lower:
				cache_type = "cpu0_L1D"
			elif 'llc' in tag_lower:
				cache_type = "LLC"
			else:
				cache_type = "cpu0_L2C"  # default to L2C
			
			df_pref_tag = stats.load_df([input_data_files[i]], [tag], cache_type, "PREFETCH")
			df_trans_tag = stats.load_df([input_data_files[i]], [tag], cache_type, "TRANSLATION")
			df_pref_list.append(df_pref_tag)
			df_trans_list.append(df_trans_tag)
		
		df_pref = pd.concat(df_pref_list, ignore_index=True)
		df_trans = pd.concat(df_trans_list, ignore_index=True)

		# Prepare merge on benchmarks and tag
		# Ensure 'benchmarks' is a column (not ambiguous index)
		# Ensure 'benchmarks' exists as a column (some dataframes already have it)
		df_pref = df_pref.copy()
		# ensure index is unnamed to avoid ambiguity when merging
		df_pref.index.name = None
		if 'benchmarks' not in df_pref.columns:
			df_pref['benchmarks'] = df_pref.index
		df_trans = df_trans.copy()
		df_trans.index.name = None
		if 'benchmarks' not in df_trans.columns:
			df_trans['benchmarks'] = df_trans.index
		left = df_pref[['benchmarks','tag','USEFUL']].rename(columns={'USEFUL':'PREFETCH_USEFUL'})
		right = df_trans[['benchmarks','tag','MISS']].rename(columns={'MISS':'TRANSLATION_MISS'})
		merged = pd.merge(left, right, on=['benchmarks','tag'], how='inner')
		merged['PREFETCH_USEFUL'] = pd.to_numeric(merged['PREFETCH_USEFUL'], errors='coerce').fillna(0)
		merged['TRANSLATION_MISS'] = pd.to_numeric(merged['TRANSLATION_MISS'], errors='coerce').fillna(0)
		merged['PREFETCH_COVERAGE'] = merged.apply(lambda r: (100.0 * r['PREFETCH_USEFUL'] / r['TRANSLATION_MISS']) if r['TRANSLATION_MISS'] > 0 else float('nan'), axis=1)

		plotting.plot_conf['plot_type'] = 'box'
		plotting.plot_conf['plot_width'] = 8
		plotting.plot_conf['plot_height'] = 3
		plotting.plot_conf['ylabel'] = 'Coverage Proxy (%)'
		plotting.plot_conf['rotation'] = 45

		output_file = figure_dir + "/" + figure_name + "_prefetch_coverage_" + benchsuite + "." + file_type
		print(output_file)
		# Keep only rows with numeric coverage
		df_plot = merged[['benchmarks','tag','PREFETCH_COVERAGE']].copy()
		df_plot = df_plot.dropna(subset=['PREFETCH_COVERAGE'])
		if df_plot.empty:
			print("No PREFETCH_COVERAGE values available to plot.")
		else:
			# Print boxplot statistics
			print("\n=== PREFETCH_COVERAGE Statistics (%) ===")
			for tag in tags:
				tag_data = df_plot[df_plot['tag'] == tag]['PREFETCH_COVERAGE']
				if not tag_data.empty:
					print(f"{tag:20} count={len(tag_data):3d}  min={tag_data.min():6.2f}  q1={tag_data.quantile(0.25):6.2f}  median={tag_data.median():6.2f}  q3={tag_data.quantile(0.75):6.2f}  max={tag_data.max():6.2f}  mean={tag_data.mean():6.2f}")
			print("")
			plotting.plot_stat(df_plot, tags, 'PREFETCH_COVERAGE', output_file)

	# Actual prefetch coverage: (baseline_misses - prefetcher_misses) / baseline_misses
	if (figure_type == "prefetch_coverage_true"):

		input_data_files, tags = get_data_files(data_files, _tags, True)  # filter_baseline=True
		
		# Need to find BASELINE data files - match them by replacing tag directory with BASELINE
		baseline_data_files = []
		for data_file in data_files:
			# Convert to Path for easier manipulation
			p = Path(data_file)
			# Replace the parent directory (which contains the tag) with BASELINE
			# E.g., stats/exp/childpf_l2c/file.csv -> stats/exp/BASELINE/file.csv
			baseline_path = p.parent.parent / "BASELINE" / p.name
			if baseline_path.exists():
				baseline_data_files.append(str(baseline_path))
		
		if not baseline_data_files:
			print("No BASELINE files found for actual coverage computation")
			print(f"Searched for baseline files by replacing tag directories with BASELINE")
			if data_files:
				print(f"Example: {data_files[0]} -> {Path(data_files[0]).parent.parent / 'BASELINE' / Path(data_files[0]).name}")
		else:
			# Load TRANSLATION misses per-tag with appropriate cache type
			df_baseline_list = []
			df_prefetch_list = []
			
			for i, tag in enumerate(tags):
				tag_lower = tag.lower()
				if 'l1d' in tag_lower or 'l1i' in tag_lower:
					cache_type = "cpu0_L1D"
				elif 'llc' in tag_lower:
					cache_type = "LLC"
				else:
					cache_type = "cpu0_L2C"  # default to L2C
				
				# Load baseline translation misses
				df_base_tag = stats.load_df([baseline_data_files[i] if i < len(baseline_data_files) else baseline_data_files[0]], 
											 ["BASELINE"], cache_type, "TRANSLATION")
				df_base_tag['tag_prefetcher'] = tag  # Track which prefetcher to compare against
				df_baseline_list.append(df_base_tag)
				
				# Load prefetcher translation misses
				df_pref_tag = stats.load_df([input_data_files[i]], [tag], cache_type, "TRANSLATION")
				df_prefetch_list.append(df_pref_tag)
			
			df_baseline = pd.concat(df_baseline_list, ignore_index=True)
			df_prefetch = pd.concat(df_prefetch_list, ignore_index=True)

			# Prepare merge on benchmarks
			df_baseline = df_baseline.copy()
			df_baseline.index.name = None
			if 'benchmarks' not in df_baseline.columns:
				df_baseline['benchmarks'] = df_baseline.index
			
			df_prefetch = df_prefetch.copy()
			df_prefetch.index.name = None
			if 'benchmarks' not in df_prefetch.columns:
				df_prefetch['benchmarks'] = df_prefetch.index
			
			# Merge baseline and prefetcher data
			left = df_baseline[['benchmarks','tag_prefetcher','MISS']].rename(columns={'MISS':'BASELINE_MISS'})
			right = df_prefetch[['benchmarks','tag','MISS']].rename(columns={'MISS':'PREFETCHER_MISS'})
			merged = pd.merge(left, right, left_on=['benchmarks','tag_prefetcher'], 
							  right_on=['benchmarks','tag'], how='inner')
			
			merged['BASELINE_MISS'] = pd.to_numeric(merged['BASELINE_MISS'], errors='coerce').fillna(0)
			merged['PREFETCHER_MISS'] = pd.to_numeric(merged['PREFETCHER_MISS'], errors='coerce').fillna(0)
			merged['MISS_REDUCTION'] = merged['BASELINE_MISS'] - merged['PREFETCHER_MISS']
			merged['ACTUAL_COVERAGE'] = merged.apply(
				lambda r: (100.0 * r['MISS_REDUCTION'] / r['BASELINE_MISS']) if r['BASELINE_MISS'] > 0 else float('nan'), 
				axis=1
			)

			plotting.plot_conf['plot_type'] = 'box'
			plotting.plot_conf['plot_width'] = 8
			plotting.plot_conf['plot_height'] = 3
			plotting.plot_conf['ylabel'] = 'Actual Coverage (%)'
			plotting.plot_conf['rotation'] = 45

			output_file = figure_dir + "/" + figure_name + "_prefetch_coverage_true_" + benchsuite + "." + file_type
			print(output_file)
			
			# Keep only rows with numeric coverage
			df_plot = merged[['benchmarks','tag','ACTUAL_COVERAGE']].copy()
			df_plot = df_plot.dropna(subset=['ACTUAL_COVERAGE'])
			
			if df_plot.empty:
				print("No ACTUAL_COVERAGE values available to plot.")
			else:
				# Print boxplot statistics
				print("\n=== ACTUAL_COVERAGE Statistics (%) ===")
				for tag in tags:
					tag_data = df_plot[df_plot['tag'] == tag]['ACTUAL_COVERAGE']
					if not tag_data.empty:
						print(f"{tag:20} count={len(tag_data):3d}  min={tag_data.min():6.2f}  q1={tag_data.quantile(0.25):6.2f}  median={tag_data.median():6.2f}  q3={tag_data.quantile(0.75):6.2f}  max={tag_data.max():6.2f}  mean={tag_data.mean():6.2f}")
				print("")
				plotting.plot_stat(df_plot, tags, 'ACTUAL_COVERAGE', output_file)


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
		

	if (figure_type == "txvc_prefetcher_survivability"):

		input_data_files, tags = get_data_files(data_files, _tags, True)

		cache_types=["TXVC"]
		op_type = "TOTAL"

		df = stats.load_df(input_data_files, tags, cache_types, op_type)

		entry_stats = [
						'TXVC_PREFETCHER_ENTRY_ALLOC',
						'TXVC_PREFETCHER_ENTRY_REPL',
						'TXVC_PREFETCHER_ENTRY_REPL_BEFORE_ISSUE',
						'TXVC_PREFETCHER_ENTRY_LIVE',
						'TXVC_PREFETCHER_ENTRY_LIVE_WITH_ISSUE'
				]

		for stat in entry_stats:
			df[stat] = pd.to_numeric(df[stat], errors='coerce').fillna(0)

		df['CHURN'] = 0.0
		df['CHURN'] = np.where(
			df['TXVC_PREFETCHER_ENTRY_ALLOC'] > 0,
			(df['TXVC_PREFETCHER_ENTRY_REPL'] * 100.0) / df['TXVC_PREFETCHER_ENTRY_ALLOC'],
			0.0
		)

		df['OVERWRITE_BEFORE_LEARNING'] = 0.0
		df['OVERWRITE_BEFORE_LEARNING'] = np.where(
			df['TXVC_PREFETCHER_ENTRY_REPL'] > 0,
			(df['TXVC_PREFETCHER_ENTRY_REPL_BEFORE_ISSUE'] * 100.0) / df['TXVC_PREFETCHER_ENTRY_REPL'],
			0.0
		)

		df['EMITABILITY'] = 0.0
		df['EMITABILITY'] = np.where(
			df['TXVC_PREFETCHER_ENTRY_LIVE'] > 0,
			(df['TXVC_PREFETCHER_ENTRY_LIVE_WITH_ISSUE'] * 100.0) / df['TXVC_PREFETCHER_ENTRY_LIVE'],
			0.0
		)

		means = []
		metrics = []
		confs = []
		metric_map = {
			'CHURN': 'Replacement Rate',
			'OVERWRITE_BEFORE_LEARNING': 'Overwrite Before Issue',
			'EMITABILITY': 'Active Entry Rate'
		}

		for metric in metric_map:
			for tag in tags:
				mean = df.loc[(df['tag'] == tag)][metric].mean()
				means.append(mean)
				metrics.append(metric_map[metric])
				confs.append(tag)

		means_df = pd.DataFrame({'metric': metrics, 'tag': confs, 'mean': means})
		print(means_df)

		plotting.plot_conf['plot_type'] = 'bar'
		plotting.plot_conf['plot_width'] = 8
		plotting.plot_conf['plot_height'] = 2.5
		plotting.plot_conf['fontsize'] = 12
		plotting.plot_conf['ylabel'] = "Ratio (%)"
		plotting.plot_conf['xlabel'] = None
		plotting.plot_conf['rotation'] = 15
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['legend_cols'] = len(tags)
		plotting.plot_conf['legend_yoffset'] = 0.5
		plotting.plot_conf['legend_xoffset'] = 1.25

		fig, axes = plotting.plt.subplots(	nrows=1, ncols=1,
														figsize=(plotting.plot_conf['plot_width'], plotting.plot_conf['plot_height']))
		plotting.plot(means_df, x='metric', y='mean', hue='tag', axes=axes)

		output_file = figure_dir + "/" + figure_name + "_txvc_prefetcher_survivability_" + benchsuite + "." + file_type
		print(output_file)
		fig.savefig(output_file, bbox_inches='tight')

	if (figure_type == "txvc_prefetch_funnel"):

		input_data_files, tags = get_data_files(data_files, _tags, True)

		issued_df = stats.load_df(input_data_files, tags, "TXVC", "PREFETCH")

		funnel_stats = [
						'ISSUED',
						'REQUESTED',
						'TXVC_PF_LT_FIRST_USE'
				]

		for stat in funnel_stats:
			issued_df[stat] = pd.to_numeric(issued_df[stat], errors='coerce').fillna(0)

		means = []
		stages = []
		confs = []
		stage_map = {
			'ISSUED': 'ISSUED',
			'REQUESTED': 'FILL',
			'TXVC_PF_LT_FIRST_USE': 'FIRST_USE'
		}

		for stage in stage_map:
			for tag in tags:
				mean = issued_df.loc[(issued_df['tag'] == tag)][stage].mean()
				means.append(mean)
				stages.append(stage_map[stage])
				confs.append(tag)

		means_df = pd.DataFrame({'stage': stages, 'tag': confs, 'mean': means})
		print(means_df)

		plotting.plot_conf['plot_type'] = 'bar'
		plotting.plot_conf['plot_width'] = 9
		plotting.plot_conf['plot_height'] = 2.8
		plotting.plot_conf['fontsize'] = 12
		plotting.plot_conf['ylabel'] = "Count"
		plotting.plot_conf['xlabel'] = None
		plotting.plot_conf['rotation'] = 15
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['legend_cols'] = len(tags)
		plotting.plot_conf['legend_yoffset'] = 0.5
		plotting.plot_conf['legend_xoffset'] = 1.25

		fig, axes = plotting.plt.subplots(	nrows=1, ncols=1,
														figsize=(plotting.plot_conf['plot_width'], plotting.plot_conf['plot_height']))
		plotting.plot(means_df, x='stage', y='mean', hue='tag', axes=axes)

		output_file = figure_dir + "/" + figure_name + "_txvc_prefetch_funnel_" + benchsuite + "." + file_type
		print(output_file)
		fig.savefig(output_file, bbox_inches='tight')


	if (figure_type == "txvc_prefetch_failure_split"):

		input_data_files, tags = get_data_files(data_files, _tags, True)

		cache_types=["TXVC"]
		op_type = "TOTAL"

		df = stats.load_df(input_data_files, tags, cache_types, op_type)

		failure_stats = [
						'TXVC_PF_LT_EVICTED_NO_USE',
						'TXVC_PF_LT_EVICTED_AFTER_USE'
				]

		for stat in failure_stats:
			df[stat] = pd.to_numeric(df[stat], errors='coerce').fillna(0)

		rows = []
		for tag in tags:
			tag_df = df.loc[(df['tag'] == tag)]
			no_use = tag_df['TXVC_PF_LT_EVICTED_NO_USE'].mean()
			after_use = tag_df['TXVC_PF_LT_EVICTED_AFTER_USE'].mean()
			rows.append({
				'tag': tag,
				'EVICTED_NO_USE': no_use,
				'EVICTED_AFTER_USE': after_use,
			})

		means_df = pd.DataFrame(rows)
		print(means_df)

		plot_df = means_df.melt(
			id_vars='tag',
			value_vars=['EVICTED_NO_USE', 'EVICTED_AFTER_USE' ],
			var_name='metric',
			value_name='mean'
		)

		plotting.plot_conf['plot_type'] = 'bar'
		plotting.plot_conf['plot_width'] = 8
		plotting.plot_conf['plot_height'] = 2.8
		plotting.plot_conf['fontsize'] = 12
		plotting.plot_conf['ylabel'] = 'Count'
		plotting.plot_conf['xlabel'] = None
		plotting.plot_conf['rotation'] = 15
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['legend_cols'] = 3
		plotting.plot_conf['legend_yoffset'] = 0.5
		plotting.plot_conf['legend_xoffset'] = 1.25

		fig, axes = plotting.plt.subplots(	nrows=1, ncols=1,
														figsize=(plotting.plot_conf['plot_width'], plotting.plot_conf['plot_height']))
		plotting.plot(plot_df, x='tag', y='mean', hue='metric', axes=axes)

		output_file = figure_dir + "/" + figure_name + "_txvc_prefetch_failure_split_" + benchsuite + "." + file_type
		print(output_file)
		fig.savefig(output_file, bbox_inches='tight')
		

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


