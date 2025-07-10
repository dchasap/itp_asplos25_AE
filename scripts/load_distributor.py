from concurrent.futures import ThreadPoolExecutor
import subprocess

commands = []

def schedule_command(cmd):
    commands.append(cmd)

def execute_command(cmd):
    
  try:
    
      result = subprocess.run(
          cmd,
          shell=True,
          check=True,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          text=True
      )
    
      return {"success": True, "output": result.stdout, "command": cmd}
    
  except subprocess.CalledProcessError as e:
      return {"success": False, "error": e.stderr, "command": cmd}



# MAIN 
parser = argparse.ArgumentParser()
parser.add_argument('--config', dest='config_file', required=True, help="Name of the experiment configuration file.")
parser.add_argument('--cmds', dest='build_binaries', required=False, action='store_true', help='The list of commands to run.')

if __name__ == "__main__":

	args = parser.parse_args()

	config = configparser.ConfigParser()
	config.read(args.config_file)

	config = conf_preprocessor.preprocess(config)

	if args.run_experiment or args.build_binaries:
		prepare_experiment(config, args.build_binaries, args.run_experiment)
	
	if args.parse_data and parsing_plotting_module_available:
		parse_experimental_data(config)

	if args.plot_data and parsing_plotting_module_available:
		plot_experimental_data(config)

	if args.show_data and parsing_plotting_module_available:
		show_experimental_data(config)

distribut_load(workers_num):

  executor = ThreadPoolExecutor(max_workers=workers_num)
  futures = [executor.submit(execute_command, cmd) for cmd in commands]
    
  for future in futures:
    result = future.result()
    if result["success"]:
        print(f"Success {result['command']} succeeded")
        print(result["output"])
    else:
        print(f"Error {result['command']} failed")
        print(result["error"])

  executor.shutdown(wait=True)


