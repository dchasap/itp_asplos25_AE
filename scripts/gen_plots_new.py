
import os
import argparse	
import stats
import plotting
import pandas as pd
from scipy.stats import gmean


xlabels = {	
			'qualcomm_srv_ap': "Qualcomm Server Workloads",
			'selected_qualcomm_srv_ap': "Qualcomm Server Workloads",
			'smt_qualcomm_srv_ap': "SMT Qualcomm Server Workloads",
			'spec': "SPEC CPU 2006/2017",
      'google_srv': "Google Server Workloads"
		}

FIGURES_DIR = "./figures"


def gen_plot(figure_name, benchsuite, data_files, file_type):

	if (figure_name == "plot_impki"):

		input_data_files =	[ "./stats/" + benchsuite  + "_fdip_baseline_llc-s.1537-w.16.csv" ]

		cache_type = "cpu0_STLB"
		op_type = "TOTAL"

		tags = [ "LRU" ]

		data_df = stats.load_df(input_data_files, tags, cache_type, op_type)

		plotting.plot_conf['plot_type'] = 'scatter'
		plotting.plot_conf['xlabel'] = xlabels[benchsuite]
		plotting.plot_conf['ylabel'] = "instruction translation MPKI"
		plotting.plot_conf['plot_width'] = 9
		plotting.plot_conf['plot_height'] = 3
		plotting.plot_conf['rotation'] = 20
	
		output_file = FIGURES_DIR + "/fig_impki_" + benchsuite + "." + file_type
		print(FIGURES_DIR + "/fig_impki_eval_" + benchsuite + "." + file_type)
		plotting.plot_stat(data_df, tags, 'iMPKI', output_file)
	

	if (figure_name == "plot_itp_eval_per_bench"):

		input_baseline_files =	[ "./stats/" + benchsuite  + "_fdip_baseline_llc-s.1537-w.16.csv" ]
	
		input_data_files = []
		data_files = data_files.replace('\t', '')
		data_files = data_files.split('\n')

		for data_file in data_files:

			if (data_file == ""): continue
			
			input_data_files.append("./stats/" + benchsuite + "_" + data_file + ".csv")	

		tags = [
							"LRU",
							"TDRRIP",
							"PTP",
							"CHiRP",
							"ChiRP+TDRRIP",
							"ChiRP+PTP",
							"iTP",
							"iTP+TDRRIP",
							"iTP+PTP",
							"iTP+xPTP"
						]

		cache_type = "cpu0_STLB"
		op_type = "TOTAL"

		baseline_df = stats.load_df(input_baseline_files, tags, cache_type, op_type)
		data_df = stats.load_df(input_data_files, tags, cache_type, op_type)


		data_df = stats.compute_variation(baseline_df, data_df, tags, 'IPC', 'IPC_IMPROVEMENT')
		means_df = stats.compute_mean(data_df, tags, 'IPC_IMPROVEMENT', 'mean')


		print(data_df['benchmarks'].str.split('.').str[0])
		data_df['benchmarks'] = data_df['benchmarks'].str.split('.').str[0]
	
		plotting.plot_conf['plot_type'] = 'scatter'
		plotting.plot_conf['xlabel'] = xlabels[benchsuite]
		plotting.plot_conf['ylabel'] = "IPC Improvement (%)"
		plotting.plot_conf['plot_width'] = 9
		plotting.plot_conf['plot_height'] = 3
		plotting.plot_conf['rotation'] = 20
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['legend_cols'] = 5
		plotting.plot_conf['legend_yoffset'] = 0.5
		plotting.plot_conf['legend_xoffset'] = 1.2
		#plotting.plot_cols[']
	
		output_file = FIGURES_DIR + "/fig_itp_eval_" + benchsuite + "." + file_type
		print(FIGURES_DIR + "/fig_itp_eval_" + benchsuite + "." + file_type)
		plotting.plot_stat_w_means(data_df, means_df, tags, output_file)
	

	if (figure_name == "plot_ipc"): 

		input_baseline_files =	[ "./stats/" + benchsuite  + "_fdip_baseline_llc-s.1537-w.16.csv" ]
		#input_baseline_files =	[ "./stats/" + benchsuite  + "_fdip_baseline.csv" ]
	
		input_data_files = []
		data_files = data_files.replace('\t', '')
		data_files = data_files.split('\n')

		for data_file in data_files:

			if (data_file == ""): continue
			print(data_file)	
			input_data_files.append("./stats/" + benchsuite + "_" + data_file + ".csv")	

		tags = [ 	"LRU",
							"iTP",
							"xPTP",
							"iTP+xPTP",
							"L1D-VC",
							"iTP+L1D-VC",
							"xPTP+L1D-VC",
							"iTP+L1D-VC+xPTP"
					]
	
		tags = [ 	
							"xPTP+L1D-VC",
							"iTP+L1D-VC+xPTP",
							"xPTP+L1D-VC-PERFECT",
							"iTP+L1D-VC-PERFECT+xPTP"
					]
	
		tags = [ 	
							"iTP",
							"xPTP",
							"iTP+xPTP",
							"L1D-VC-PERFECT",
							"L1D-VC-PERFECT+xPTP",
							"L1D-VC-256KB",
							"L1D-VC-256KB+xPTP",
							"L1D-VC-32KB",
							"L1D-VC-32KB+xPTP",
							"L1D-VC-8KB",
							"L1D-VC-8KB+xPTP"
					]
	
		tags = [ 	
							"L1D-VC-256KB+xPTP",
							"L1D-iVC-256KB+xPTP",
							"L1D-VC-32KB+xPTP",
							"L1D-iVC-32KB+xPTP",
					]

		tags = [
							"L1D-VC",
							"L1D-IVC"
					]

		cache_type = "cpu0_STLB"
		op_type = "TOTAL"

		baseline_df = stats.load_df(input_baseline_files, tags, cache_type, op_type)
		data_df = stats.load_df(input_data_files, tags, cache_type, op_type)


		data_df = stats.compute_variation(baseline_df, data_df, tags, 'IPC', 'IPC_IMPROVEMENT')
		#means_df = stats.compute_mean(data_df, tags, 'IPC_IMPROVEMENT', 'mean')


		print(data_df['benchmarks'].str.split('.').str[0])
		data_df['benchmarks'] = data_df['benchmarks'].str.split('.').str[0]
	
		plotting.plot_conf['plot_type'] = 'box'
		plotting.plot_conf['xlabel'] = xlabels[benchsuite]
		plotting.plot_conf['ylabel'] = "IPC Improvement (%)"
		plotting.plot_conf['plot_width'] = 9
		plotting.plot_conf['plot_height'] = 3
		plotting.plot_conf['rotation'] = 20
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['legend_cols'] = 5
		plotting.plot_conf['legend_yoffset'] = 0.5
		plotting.plot_conf['legend_xoffset'] = 1.2
		#plotting.plot_cols[']
	
		output_file = FIGURES_DIR + "/fig_l1dvc_ipc_" + benchsuite + "." + file_type
		print(FIGURES_DIR + "/fig_l1dvc_ipc_" + benchsuite + "." + file_type)
		plotting.plot_stat(data_df, tags, 'IPC_IMPROVEMENT', output_file)
	

	if (figure_name == "plot_mpki"):
	
		input_data_files = []
		data_files = data_files.replace('\t', '')
		data_files = data_files.split('\n')

		for data_file in data_files:

			if (data_file == ""): continue
			print(data_file)	
			input_data_files.append("./stats/" + benchsuite + "_" + data_file + ".csv")	

	
		tags = [ 	"LRU",
							"iTP",
							"xPTP",
							"iTP+xPTP",
							"L1D-VC",
							"iTP+L1D-VC",
							"L1D-VC+xPTP",
							"iTP+L1D-VC+xPTP"
					]
	
		tags = [ 	"LRU",
							"xPTP",
							"L1D-VC+PERFECT+xPTP",
							"iTP+L1D-VC-PERFECT+xPTP",
							"ïTP+L1D-VC"
					]
	
		tags = [ 	"no VC",
							"64x6",
							"32x6",
							"16x6",
							"8x6",
							"4x6"
					]


		tags = [
							"L1D_VC",
							"L1D_IVC"
					]
		
		cache_types=["cpu0_L1D_VC", "cpu0_L1D", "cpu0_L2C", "LLC"]
		op_type = "TOTAL"

		df = stats.load_df(input_data_files, tags, cache_types, op_type)

		df = stats.compute_stat(df, "HIT_RATIO")

		stat_names = [ "MPKI", "dMPKI", "iMPKI", "itMPKI", "dtMPKI", "HIT_RATIO" ] 
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

		output_file = FIGURES_DIR + "/fig_l1dvc_mpki_impact_" + benchsuite + ".pdf"
		print(FIGURES_DIR + "/fig_l1dvc_mpki_impact_" + benchsuite + ".pdf")
		plotting.plot_average_multiple_caches(input_data_files, means_df, tags, 
																					cache_types, op_type, "MPKI", 
																					output_file)


		plotting.plot_conf['ylabel'] = "Hit Ratio(%)"	
		output_file = FIGURES_DIR + "/fig_l1dvc_hit_ratio_" + benchsuite + "_xptp.pdf"
		print(FIGURES_DIR + "/fig_l1dvc_hit_ratio_" + benchsuite + ".pdf")
		plotting.plot_average_multiple_caches(input_data_files, means_df, tags, 
																					cache_types, op_type, "HIT_RATIO", 
																					output_file)


		#plot_conf['show_legend'] = True
		#plot_conf['extra_xlabels'] = True
		#plot_conf['ylabel'] = "Avg Miss Latency"
		#output_file = FIGURES_DIR + "/fig09_soa_avg_miss_lat_comparison.pdf"
		#print(FIGURES_DIR + "/fig09_soa_avg_miss_lat_comparison.pdf")
		#plots.plot_average_multiple_caches_single_fig(	input_st_data_files, input_smt_data_files, 
		#																								input_tags, cache_types, op_type, 
		#																								"AVERAGE_MISS_LATENCY", plot_conf, output_file)

		plotting.plot_conf['ylabel'] = "MPKI"
		stat_names = [ "dMPKI", "iMPKI", "dtMPKI", "itMPKI" ] 
		for cache_type in cache_types:

			means_df_single_cache = means_df.loc[(means_df['cache'] == cache_type)]

			#means_df['iMPKI'] = means_df['iMPKI'] + means_df['dMPKI'] + means_df['itMPKI'] + means_df['dtMPKI']
			#means_df['dMPKI'] = means_df['dMPKI'] + means_df['itMPKI'] + means_df['dtMPKI']
			#means_df['itMPKI'] = means_df['itMPKI'] + means_df['dtMPKI']

			plotting.plot_conf['plot_width'] = 8
			plotting.plot_conf['plot_height'] = 1.8
			plotting.plot_conf['fontsize'] = 18

			output_file = FIGURES_DIR + "/fig_pte_mpki_impact_" + cache_type + "_" + benchsuite + "2.pdf"
			print(FIGURES_DIR + "/fig_pte_mpki_impact_" + cache_type + "_" + benchsuite + ".pdf")
			plotting.plot_average_single_cache(	input_data_files, means_df_single_cache, tags, 
																					cache_types, op_type, stat_names, 
																					output_file)
	

	if (figure_name == "plot_l2c_eval"): 

		input_baseline_files =	[ "./stats/" + benchsuite  + "_fdip_baseline_llc-s.1537-w.16.csv" ]
	
		input_data_files = []
		data_files = data_files.replace('\t', '')
		data_files = data_files.split('\n')

		for data_file in data_files:

			if (data_file == ""): continue
			print(data_file)	
			input_data_files.append("./stats/" + benchsuite + "_" + data_file + ".csv")	

		tags = [ 	"!L2C",
							"iTP"
					]

		cache_type = "cpu0_STLB"
		op_type = "TOTAL"

		baseline_df = stats.load_df(input_baseline_files, tags, cache_type, op_type)
		data_df = stats.load_df(input_data_files, tags, cache_type, op_type)


		data_df = stats.compute_variation(baseline_df, data_df, tags, 'IPC', 'IPC_IMPROVEMENT')
		#means_df = stats.compute_mean(data_df, tags, 'IPC_IMPROVEMENT', 'mean')


		plotting.plot_conf['plot_type'] = 'box'
		plotting.plot_conf['xlabel'] = xlabels[benchsuite]
		plotting.plot_conf['ylabel'] = "IPC Improvement (%)"
		plotting.plot_conf['plot_width'] = 9
		plotting.plot_conf['plot_height'] = 3
		plotting.plot_conf['rotation'] = 20
		plotting.plot_conf['show_legend'] = True
		plotting.plot_conf['legend_cols'] = 5
		plotting.plot_conf['legend_yoffset'] = 0.5
		plotting.plot_conf['legend_xoffset'] = 1.2
		#plotting.plot_cols[']
	
		output_file = FIGURES_DIR + "/fig_l2c_eval_" + benchsuite + "." + file_type
		print(FIGURES_DIR + "/fig_pte_l2c_eval_" + benchsuite + "." + file_type)
		plotting.plot_stat(data_df, tags, 'IPC_IMPROVEMENT', output_file)


	if (figure_name == "reuse_distance"):
		
		input_data_files = []
		data_files = data_files.replace('\t', '')
		data_files = data_files.split('\n')

		for data_file in data_files:

			if (data_file == ""): continue
			print(data_file)	
			input_data_files.append("./stats/" + benchsuite + "_" + data_file + "_recall_dist_L1D_VC.csv")	

		tags = 	[
							"L1D_VC",
							"L1D_IVC"
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

		output_file = FIGURES_DIR + "/fig_recall_distance_l1d_" + benchsuite + "." + file_type
		print(FIGURES_DIR + "/fig_recall_distance_" + benchsuite + "." + file_type)
		plotting.plot_reuse_distance(data_df, tags, output_file)

## end gen_plot



### Command Line Arguments ###
parser = argparse.ArgumentParser()
parser.add_argument('--figure', dest='figure_name', required=True, default=None, help="Name of figure to generate.")
parser.add_argument('--benchsuites', dest='benchsuites', required=True, default=None, nargs='+', help="Name of benchmarksuite to use.")
parser.add_argument('--data_files', dest='data_files', required=True, default=None, help="List of experiments configuration names.")
parser.add_argument('--file_type', dest='file_type', required=False, default="pdf", help="Filetype of the figure.")


if __name__ == "__main__":

	args = parser.parse_args()
	print("main")
	FIGURES_DIR = os.environ.get('FIGURES_DIR', './figures')
	if not os.path.exists(FIGURES_DIR):
		os.makedirs(FIGURES_DIR)
	
	for benchsuite in args.benchsuites:
		print(args.benchsuites)
		gen_plot(args.figure_name, benchsuite, args.data_files, args.file_type)	


