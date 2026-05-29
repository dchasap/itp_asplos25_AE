#!/usr/bin/env python3

import argparse
import configparser
import fnmatch
import os
import subprocess
import traceback

# custom modules

import printer
import conf_preprocessor
import champsimconf
import workloads
import simulation
try:
	import champsim2csv
	import champsim2plot
	parsing_plotting_module_available = True
except ImportError:
	printer.print_warning("Could not load all modules, parsing and plotting disabled.")
	parsing_plotting_module_available = False



import params_registry

# Derived maps populated at runtime after registration
default_enviromental_variables = None
confnames_to_envars = None
components = None

# CPU parameters (per-component json/env options)
cpu_def_parameters = ['instruction_perfetcher']
cpu_json_parameters = []
cpu_env_parameters = None

# Cache-like parameters (used for all cache components in the old code)
cache_json_parameters = ['sets', 'ways', 'prefetcher', 'prefetch_activate', 'replacement', 'force_hit']
cache_env_parameters = None


def _split_simulations(value):
	return [simulation.strip() for simulation in value.split(',') if simulation.strip()]


def _flatten_overrides(raw_overrides):
	flat_overrides = []
	for group in raw_overrides:
		if isinstance(group, list):
			flat_overrides.extend(group)
		else:
			flat_overrides.append(group)
	return flat_overrides


def apply_cli_overrides(config, raw_overrides):
	overrides = _flatten_overrides(raw_overrides)
	if not overrides:
		return

	experiment_simulations = []
	if config.has_section('EXPERIMENT') and config.has_option('EXPERIMENT', 'simulations'):
		experiment_simulations = _split_simulations(config['EXPERIMENT']['simulations'])

	for override in overrides:
		if '=' not in override:
			printer.print_error("Malformed override (missing '='): " + override)
			exit(1)

		target, value = override.split('=', 1)
		target = target.strip()
		value = value.strip()

		if '.' not in target:
			printer.print_error("Malformed override target (expected section.option): " + target)
			exit(1)

		section_selector, option = target.split('.', 1)
		section_selector = section_selector.strip()
		option = option.strip()

		if not section_selector or not option:
			printer.print_error("Malformed override target (empty section or option): " + target)
			exit(1)

		is_wildcard = any(token in section_selector for token in ['*', '?', '['])

		if is_wildcard:
			matched_sections = [
				section
				for section in experiment_simulations
				if fnmatch.fnmatch(section, section_selector)
			]

			for section in matched_sections:
				if not config.has_section(section):
					config.add_section(section)
				config.set(section, option, value)

			printer.print_default(
				"Override applied: " + target + "='" + value + "' to " + str(len(matched_sections)) + " experiment section(s)."
			)
		else:
			if not config.has_section(section_selector):
				printer.print_error("Explicit override section not found: " + section_selector)
				exit(1)

			config.set(section_selector, option, value)
			printer.print_default(
				"Override applied: " + target + "='" + value + "'"
			)


def set_champsim_json_params(config, json_conf, sim, component, parameters):

	for param in parameters:
		if config.has_option(sim, component+'.'+param):
			value = config[sim][component+'.'+param]
			#print(component+'.'+param, ':', config[sim][component+'.'+param])
			champsimconf.set_entry(json_conf, component.upper(), param, value)



def set_champsim_env_params(config, enviromental_variables, sim, component, parameters):
	
	if not config.has_section(sim): 
		printer.print_error("ERROR:" + sim + " parameters not found!")
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


def prepare_experiment(config, build_champsim, run):

	root_dir = config['BASE']['ROOT_DIR']
	champsim_dir = config['BASE']['CHAMPSIM_DIR']
	exp_name = config['EXPERIMENT']['name']

	json_conf = champsimconf.load_config(champsim_dir + "/champsim_fdip_baseline.json")
	
	debug_run = config['EXPERIMENT'].getboolean('debug_run')

	parallel_run = False
	if (config.has_option('EXPERIMENT', 'parallel_run')):
		parallel_run = config['EXPERIMENT'].getboolean('parallel_run')

	# first get the simulations' names
	#if debug_run:
	#	simulations = [ 'debug' ]
	#else: 
	simulations = config['EXPERIMENT']['simulations'].replace(" ", "").split(",")

	
	for sim in simulations:

		if config.has_option(sim, 'skip_simulation'):
			skip = config[sim].getboolean('skip_simulation')
			if skip:
				printer.print_warning("Skipping simulation for " + sim)
				continue

		printer.print_default("Setting up simulation for " + sim)
		new_json_conf = champsimconf.create_copy(json_conf)
		champsimconf.set_entry(new_json_conf, None, 'executable_name', exp_name + '/champsim_' + sim)

		# Setup simulation parameters
		enviromental_variables = default_enviromental_variables # FIXME: is this a swallow copy?

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
		if (build_champsim):
			#os.system(champsim_dir + '/config.sh --compile-all-modules ' + root_dir + '/sim_conf/' + exp_name + '/' + sim + '.json')
			os.system(champsim_dir + '/config.sh ' + root_dir + '/sim_conf/' + exp_name + '/' + sim + '.json')
			os.system('make -C ' + champsim_dir)
			printer.print_success("Build completed successfully")

		# Run simulation
		if (run):
			trace_dir = config['BASE']['TRACE_DIR']
			dump_dir = config['BASE']['dump_dir'] + "/" + exp_name + "/" + sim
			workload_name = config['EXPERIMENT']['workload'] # TODO: adjust for multiple workloads
			printer.print_default("Submitting simulation jobs for " + sim)
			#print(enviromental_variables)
			simulation.run_simulation_batch(root_dir, trace_dir, dump_dir, sim, exp_name, workload_name, config['SIMULATION'], enviromental_variables, parallel_run, debug_run)
			printer.print_success("Jobs submitted succefully")

def parse_experimental_data(config):

	root_dir = config['BASE']['ROOT_DIR'] 
	exp_name = config['EXPERIMENT']['name']
	
	
	# get the simulation names
	simulations = config['EXPERIMENT']['simulations'].replace(" ", "").split(",")

	for sim in simulations:

		# download data if needed
		fetch_experiment_data(root_dir, exp_name, sim)

		if config.has_option(sim, 'simulation_stats'):
			printer.print_warning("Skipping " + sim + "...")
			continue

		dump_dir = config['BASE']['DUMP_DIR'] + "/" + exp_name + "/" + sim
		stats_dir = config['BASE']['STATS_DIR'] + "/" + exp_name + "/" + sim
		workload_name = config['EXPERIMENT']['workload']

		workload = workloads.Workloads(workload_name)
		benchmarks = workload.get_benchmark_names()

		parse_raw_data = config['PARSING'].getboolean('parse_raw_stats')
		if parse_raw_data:
			
			os.system("mkdir -p " + stats_dir)
			
			printer.print_default("Parsing results for " + sim + "...")
			csv_benchmark_data_files = []
			for bench in benchmarks:
				simpoints, weights = workload.get_simpoints_n_weights(bench)
		
				if simpoints == None:
					simpoints = [ "" ]
					raw_file_suffix = dump_dir + "/" + bench
					csv_file_suffix = stats_dir + "/" + bench
				else: 
					raw_file_suffix = dump_dir + "/" + bench + "-"
					csv_file_suffix = stats_dir + "/" + bench + "-"

				# get raw data filenames
				raw_simpoint_data_files = []
				for simpoint in simpoints:
					raw_simpoint_data_files.append(raw_file_suffix + simpoint + "_" + sim + "_run.out")
		
				# parse data to stats csv files
				csv_simpoints_data_files = []
				i = 0
				for raw_file in raw_simpoint_data_files:
					csv_file = csv_file_suffix + simpoints[i] + "_" + sim + ".csv" 
					try:
						#print("Parsing " + raw_file + "...")
						champsim2csv.parse_champsim_stats(raw_file, csv_file)
						csv_simpoints_data_files.append(csv_file)
					except Exception as e:
						printer.print_error("Parsing Failed: " + raw_file)
						printer.print_error(e)
						printer.print_error(traceback.format_exc())
				
					i += 1

				# merge simpoint data files
				if i > 1:
					printer.print_default("Merging simpoints of " + bench)
					#weights = workloads.get_simpoints_weights(workload_name, bench)
					csv_benchmark_data_file = stats_dir + "/" + bench + "_" + sim + ".csv"
					# TODO: reduce to a single dataframe, taking weights into account
					champsim2csv.merge_simpoint_data(csv_simpoints_data_files, weights, csv_benchmark_data_file)
				else:
					csv_benchmark_data_file = csv_simpoints_data_files[0] # nothing to reduce, just a single file

				csv_benchmark_data_files.append(csv_benchmark_data_file)

			# merge csv files
			printer.print_default("Merging results to " + stats_dir + "/" + workload_name + "_" + sim + ".csv")
			champsim2csv.merge_champsim_data(csv_benchmark_data_files, benchmarks, stats_dir + "/" + workload_name + "_" + sim + ".csv")
			printer.print_success("Parsing completed successfully")



def plot_experimental_data(config):
	
	root_dir = config['BASE']['ROOT_DIR'] 
	exp_name = config['EXPERIMENT']['name']
	figures_dir = config['BASE']['FIGURES_DIR'] + "/" + exp_name
	plot_name = config['PLOTTING']['plot_name']
	file_type = config['PLOTTING']['file_type']
	plots = config['PLOTTING']['plot_type'].replace(" ", "").split(",")

	workload_name = config['EXPERIMENT']['workload']             
	simulations = config['EXPERIMENT']['simulations'].replace(" ", "").split(",")
	
	for plot_type in plots:
		csv_data_files = []
		for sim in simulations:
			stats_dir = config['BASE']['STATS_DIR'] + "/" + exp_name + "/" + sim
			
			if config.has_option(sim, 'include_stats_dir'):
				csv_data_file = config[sim]['include_stats_dir'] + "/" + workload_name + "_" + sim + ".csv"
			else:
				csv_data_file = stats_dir + "/" + workload_name + "_" + sim + ".csv"
			
			#print(csv_data_file)
			csv_data_files.append(csv_data_file)

		if config.has_option('PLOTTING', 'alternative_tags'):
			conf_tags = config['PLOTTING']['alternative_tags'].replace(" ", "").split(",")
		else:
			conf_tags = simulations
		print(simulations)

		os.system("mkdir -p " + figures_dir)
		printer.print_default("Plotting " + plot_name + " for " + workload_name)
		champsim2plot.gen_plot(workload_name, conf_tags, csv_data_files, plot_name, plot_type, file_type, figures_dir, config['PLOTTING'])
		printer.print_success("Plotting completed successfully")



def show_experimental_data(config):

	print('Opening pdf file...')
	exp_name = config['EXPERIMENT']['name']
	workload = config['EXPERIMENT']['workload']
	figures_dir = config['BASE']['FIGURES_DIR'] + "/" + exp_name
	figure_name = config['PLOTTING']['plot_name']
	file_type = config['PLOTTING']['file_type']
	plots = config['PLOTTING']['plot_type'].replace(" ", "").split(",")

	for plot_type in plots:
		
		figure_file = figures_dir + "/" + figure_name + "_" + plot_type + "_" + workload + "." + file_type
		#os.system("evince " + figure_file)
		subprocess.Popen(["evince", figure_file])


def build_presentation(config):
	slides_dir = config['BASE']['SLIDES_DIR']
	#os.system("cd slides")
	os.system("make clean -C " + slides_dir)
	os.system("make -C " + slides_dir)
	#os.system("cd ..")


def fetch_experiment_data(root_dir, exp_name, sim):

	remote = f"bsc018186@transfer1.bsc.es:/gpfs/scratch/bsc18/bsc018186/VMem/data/{exp_name}/{sim}"
	local = f"{root_dir}/data/{exp_name}"
	
	cmd = [
			"rsync", "-av",
			"--include=*/",
			"--include=*.out",
			"--exclude=*",
			remote,
			local
	]
	print(cmd)
	subprocess.run(cmd, check=True)


# MAIN 
parser = argparse.ArgumentParser()
parser.add_argument('--config', dest='config_file', required=True, help="Name of the experiment configuration file.")
parser.add_argument('--build', dest='build_binaries', required=False, action='store_true', help='Build ChampSim binaries.')
parser.add_argument('--run', dest='run_experiment', required=False, action='store_true', help='Run simulations.')
parser.add_argument('--parse', dest='parse_data', required=False, action='store_true', help='Parse simulations\' data.')
parser.add_argument('--plot', dest='plot_data', required=False, action='store_true', help='Plot simulations\' data.')
parser.add_argument('--show', dest='show_data', required=False, action='store_true', help='Show plotted data.')
parser.add_argument('--build-presentation', dest='build_presentation', required=False, action='store_true', help='Build slides.')
parser.add_argument(
	'--override',
	dest='overrides',
	required=False,
	action='append',
	nargs='+',
	default=[],
	help='Override config as section.option=value. Supports multiple values and wildcard section patterns (e.g. "*.txvc.miss_fill_target=l2c txvc") over experiment simulations.'
)

if __name__ == "__main__":

	args = parser.parse_args()

	config = configparser.ConfigParser()
	config.read(args.config_file)
	apply_cli_overrides(config, args.overrides)

	config = conf_preprocessor.preprocess(config, args.config_file)

	# Populate registry at runtime (registrations live in params_registry_data)
	import params_registry_data
	params_registry_data.register_all()

	# Generate the legacy structures from the single-source registry
	default_enviromental_variables = params_registry.generate_default_env()
	confnames_to_envars = params_registry.generate_confnames_map()
	components = params_registry.get_components()
	cpu_env_parameters = params_registry.generate_param_names_for_component('ooo_cpu', 'env')
	cache_env_parameters = params_registry.generate_common_cache_param_names()

	if args.run_experiment or args.build_binaries:
		prepare_experiment(config, args.build_binaries, args.run_experiment)
	
	if args.parse_data and parsing_plotting_module_available:
		parse_experimental_data(config)

	if args.plot_data and parsing_plotting_module_available:
		plot_experimental_data(config)

	if args.show_data and parsing_plotting_module_available:
		show_experimental_data(config)

	if args.build_presentation:
		build_presentation(config)
