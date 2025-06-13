#!/usr/bin/env python3

import argparse
import configparser
import os
import subprocess
import traceback
# custom modules
import champsimconf
import workloads
import simulation
try:
	import champsim2csv
	import champsim2plot
	parsing_plotting_module_available = True
except ImportError:
	parsing_plotting_module_available = False



default_enviromental_variables = { 
	'ITP_INSTR_POS': "0", 
	'ITP_DATA_POS': "2",
	'ITP_MAX_LRU': "8", 
	'MIN_EVICTION_POSITION': "4", 
	'MIN_EVICTION_POSITION_L1D': "8", 
	'MIN_EVICTION_POSITION_L2C': "4", 
	'TLB_LOWER_STRESS_THRESHOLD': "1",
	'TLB_UPPER_STRESS_THRESHOLD': "4", 
	'INSTR_PAGE_SIZE_DIST': "0",
	'DATA_PAGE_SIZE_DIST': "0",
	'ENABLE_TXVC': "false",
	'ENABLE_TXC': "false",
	'TXC_LATENCY': "0",
	'TXC_NUM_SET': "8",
	'TXC_NUM_WAY': "8",
	'TXVC_REP_POLICY': "lfu",
	'TXC_INSTR_ONLY': "false",
	'TXC_DATA_ONLY': "false",
	'TXC_DOA_FILTERING': "false",	
	'TXC_DBPRED_CNTR_SZ': "3",
	'TXC_DBPRED_THRESHOLD': "0",
	'TXC_DBPRED_USE_BIAS': "false",
	'REUSE_DIST_FILENAME_PREFIX': "reuse_dist"	
	}

confnames_to_envars = {
	'ooo_cpu.enable_txvc': 'ENABLE_TXVC',
	'txvc.sets': 'TXC_NUM_SET',
	'txvc.ways': 'TXC_NUM_WAY',
	'txvc.replacement': 'TXVC_REP_POLICY',
	'txvc.instr_only': 'TXC_INSTR_ONLY',
	'txvc.data_only': 'TXC_DATA_ONLY',
	'txvc.doa_filtering': 'TXC_DOA_FILTERING',
	'txvc.dbpred_use_bias': 'TXC_DBPRED_USE_BIAS',
	'txvc.dbpred_cntr_size': 'TXC_DBPRED_CNTR_SZ',
	'txvc.dbpred_threshold': 'TXC_DBPRED_THRESHOLD'
}

components = ['ooo_cpu', 'itlb', 'dtlb', 'stlb', 'l1i', 'l1d', 'l2c', 'llc', 'txvc']

cpu_def_parameters = [ 'instruction_perfetcher' ]
cpu_json_parameters = [] 
cpu_env_parameters = [ 'enable_txvc' ]

cache_json_parameters = [ 'sets', 'ways', 'prefetcher', 'replacement', 'force_hit' ]
cache_env_parameters = [ 'sets', 'ways', 'replacement', 'doa_filtering', 'dbpred_cntr_size', 'data_only', 'instr_only' ]


def set_champsim_json_params(config, json_conf, sim, component, parameters):

	for param in parameters:
		if config.has_option(sim, component+'.'+param):
			value = config[sim][component+'.'+param]
			#print(component+'.'+param, ':', config[sim][component+'.'+param])
			champsimconf.set_entry(json_conf, component.upper(), param, value)



def set_champsim_env_params(config, enviromental_variables, sim, component, parameters):
	
	if not config.has_section(sim): 
		print("ERROR:" + sim + " parameters not found!")
		exit(1)

	for param in parameters:
		#if (component+'.'+param) in config[].keys():
		#print(component+'.'+param)
		if config.has_option(sim, component+'.'+param) and ((component+'.'+param) in confnames_to_envars.keys()):
			key = confnames_to_envars[component+'.'+param]
			value = config[sim][component+'.'+param]
			#print(key + ":" + value)
			enviromental_variables[key] = value

	return enviromental_variables


def prepare_experiment(config):

	root_dir = config['BASE']['ROOT_DIR']
	champsim_dir = config['BASE']['CHAMPSIM_DIR']
	exp_name = config['EXPERIMENT']['name']

	json_conf = champsimconf.load_config(champsim_dir + "/champsim_fdip_baseline.json")
	
	debug_run = config['EXPERIMENT'].getboolean('debug_run')

	# first get the simulations' names
	#if debug_run:
	#	simulations = [ 'debug' ]
	#else: 
	simulations = config['EXPERIMENT']['simulations'].replace(" ", "").split(",")

	
	for sim in simulations:

		if config.has_option(sim, 'skip_simulation'):
			skip = config[sim].getboolean('skip_simulation')
			if skip:
				print("Skipping simulation for " + sim)
				continue

		print("Setting up simulation for " + sim)
		new_json_conf = champsimconf.create_copy(json_conf)
		champsimconf.set_entry(new_json_conf, None, 'executable_name', exp_name + '/champsim_' + sim)

		# Setup simulation parameters
		enviromental_variables = default_enviromental_variables

		for component in components:

			# check cpu components
			set_champsim_json_params(config, new_json_conf, sim, component, cpu_json_parameters)
			enviromental_variables = set_champsim_env_params(config, enviromental_variables, sim, component, cpu_env_parameters)
			# check cache components
			set_champsim_json_params(config, new_json_conf, sim, component, cache_json_parameters)
			enviromental_variables = set_champsim_env_params(config, enviromental_variables, sim, component, cache_env_parameters)

		os.system("mkdir -p " + root_dir + "/sim_conf/" + exp_name)
		champsimconf.save_config(new_json_conf, root_dir + '/sim_conf/' + exp_name + '/' + sim + '.json')

		# Build champsim
		os.system(champsim_dir + '/config.sh --compile-all-modules ' + root_dir + '/sim_conf/' + exp_name + '/' + sim + '.json')
		os.system('make -C ' + champsim_dir)

		# Run simulation
		trace_dir = config['BASE']['TRACE_DIR']
		dump_dir = config['BASE']['dump_dir'] + "/" + exp_name + "/" + sim
		workload_name = config['EXPERIMENT']['workload'] # TODO: adjust for multiple workloads
		print("Submitting simulation jobs for " + sim)
		simulation.run_simulation_batch(root_dir, trace_dir, dump_dir, sim, exp_name, workload_name, config['SIMULATION'], enviromental_variables, debug_run)



def parse_experimental_data(config):

	root_dir = config['BASE']['ROOT_DIR'] 
	exp_name = config['EXPERIMENT']['name']
	
	
	# get the simulation names
	simulations = config['EXPERIMENT']['simulations'].replace(" ", "").split(",")

	for sim in simulations:

		if config.has_option(sim, 'simulation_stats'):
			print("Skipping " + sim + "...")
			continue

		dump_dir = config['BASE']['DUMP_DIR'] + "/" + exp_name + "/" + sim
		stats_dir = config['BASE']['STATS_DIR'] + "/" + exp_name + "/" + sim
		workload_name = config['EXPERIMENT']['workload']

		benchmarks = workloads.get_benchmark_names(workload_name)

		parse_raw_data = config['PARSING'].getboolean('parse_raw_stats')
		if parse_raw_data:
			# get raw data filenames
			raw_champsim_data_files = []
			for bench in benchmarks:
				raw_champsim_data_files.append(dump_dir + "/" + bench + "_" + sim + "_run.out")
		
			# parse data to stats csv files
			os.system("mkdir -p " + stats_dir)
			csv_champsim_data_files = []
			print("Parsing results for " + sim + "...")
			i = 0
			for raw_file in raw_champsim_data_files:
				csv_file = stats_dir + "/" + benchmarks[i] + "_" + sim + ".csv" 
				try:
					#print("Parsing " + raw_file + "...")
					champsim2csv.parse_champsim_stats(raw_file, csv_file)
					csv_champsim_data_files.append(csv_file)
				except Exception as e:
					print("Parsing Failed: " + raw_file)
					print(e)
					print(traceback.format_exc())
				
				i += 1
		
			# merge csv files
			print("Merging results to " + stats_dir + "/" + workload_name + "_" + sim + ".csv")
			champsim2csv.merge_champsim_data(csv_champsim_data_files, benchmarks, stats_dir + "/" + workload_name + "_" + sim + ".csv")




def plot_experimental_data(config):
	
	root_dir = config['BASE']['ROOT_DIR'] 
	exp_name = config['EXPERIMENT']['name']
	figures_dir = config['BASE']['FIGURES_DIR'] + "/" + exp_name
	plot_name = config['PLOTTING']['plot_name']
	plot_type = config['PLOTTING']['plot_type']
	file_type = config['PLOTTING']['file_type']
	workload_name = config['EXPERIMENT']['workload']
               
	if config.has_option('EXPERIMENT', 'alternative_tags'):
		simulations = configp['EXPERIMENT']['alternative_tags'].replace(" ", "").split(",")
	else:
		simulations = config['EXPERIMENT']['simulations'].replace(" ", "").split(",")

	
	csv_data_files = []
	for sim in simulations:

		stats_dir = config['BASE']['STATS_DIR'] + "/" + exp_name + "/" + sim
		
		if config.has_option(sim, 'simulation_stats'):
			csv_data_file = config[sim]['simulation_stats']
		else:
			csv_data_file = stats_dir + "/" + workload_name + "_" + sim + ".csv"
		
		csv_data_files.append(csv_data_file)

	os.system("mkdir -p " + figures_dir)
	champsim2plot.gen_plot(workload_name, simulations, csv_data_files, plot_name, plot_type, file_type, figures_dir)



def show_experimental_data(config):

	print('Opening pdf file...')
	exp_name = config['EXPERIMENT']['name']
	workload = config['EXPERIMENT']['workload']
	figures_dir = config['BASE']['FIGURES_DIR'] + "/" + exp_name
	figure_name = config['PLOTTING']['plot_name']
	file_type = config['PLOTTING']['file_type']
	figure_file = figures_dir + "/" + figure_name + "_" + workload + "." + file_type
	
	#os.system("evince " + figure_file)
	subprocess.Popen(["evince", figure_file])


# MAIN 
parser = argparse.ArgumentParser()
parser.add_argument('--config', dest='config_file', required=True, help="Name of the experiment configuration file.")
parser.add_argument('--run', dest='run_experiment', required=False, action='store_true', help='Run simulations.')
parser.add_argument('--parse', dest='parse_data', required=False, action='store_true', help='Parse simulations\' data.')
parser.add_argument('--plot', dest='plot_data', required=False, action='store_true', help='Plot simulations\' data.')
parser.add_argument('--show', dest='show_data', required=False, action='store_true', help='Show plotted data.')

if __name__ == "__main__":

	args = parser.parse_args()

	config = configparser.ConfigParser()
	config.read(args.config_file)

	if args.run_experiment:
		prepare_experiment(config)
	
	if args.parse_data and parsing_plotting_module_available:
		parse_experimental_data(config)

	if args.plot_data and parsing_plotting_module_available:
		plot_experimental_data(config)

	if args.show_data and parsing_plotting_module_available:
		show_experimental_data(config)
