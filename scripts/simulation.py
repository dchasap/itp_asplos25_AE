
import os 
import workloads


def export_env_variables(benchmark, sim_name, dump_dir, enviromental_variables):

  export_cmd = "export PTP_EXTRA_STATS_FILE=" + dump_dir + "/" + benchmark + "_" + sim_name + "_access_rate.csv\n"
  export_cmd += "export INSTR_PAGE_DIST_FILENAME=" + dump_dir + "/" + benchmark + "_" + sim_name + "_instr.pdst\n"
  export_cmd += "export DATA_PAGE_DIST_FILENAME=" + dump_dir + "/" + benchmark + "_" + sim_name + "_data.pdst\n"
  export_cmd += "export PAGE_ADDRESS_STATS_FILENAME_PREFIX=" + dump_dir + "/" + benchmark + "_" + sim_name + "_page_access_stats\n"

  for var in enviromental_variables:
    export_cmd += "export " + var + "=" + enviromental_variables[var] + "\n"

  return export_cmd



def run_simulation_batch(root_dir, trace_dir, dump_dir, sim_name, exp_name, workload_name, sim_config, enviromental_variables, debug_run):
  
  os.system("mkdir -p " + dump_dir)

  traces, trace_path = workloads.get_benchmark_traces(workload_name)
  trace_dir = trace_dir + "/" + trace_path
  benchmarks = workloads.get_benchmark_names(workload_name)

  if debug_run:
    print("Simulating in Debug mode.")
    workload = 'debug'
    debug_flags = 'gdb -batch -ex "run" -ex "bt" --args'
    job_queue = 'gp_debug'
    sim_time = '00:00:30'
    warmup_instr = '500000'
    run_instr = '1000000'
    job_prefix = 'debug'
  else: 
    debug_flags = 'gdb -batch -ex "run" -ex "bt" --args'
    job_queue = 'gp_bsccs'
    sim_time = sim_config['time']
    warmup_instr = sim_config['warmup_instructions']
    run_instr = sim_config['run_instructions']
    job_prefix = 'simr'

  batch_size = int(sim_config['batch_size'])

  ti = 0
  while ti < len(traces):

    job_name = "sim_" + exp_name + "_" + sim_name + "_" + workload_name + "_" + str(ti) +"_job"
    job = open(job_name + ".run", 'w')

    job.write("#!/bin/bash\n")
    job.write("#SBATCH -o " + dump_dir + "/" + workload_name + "_" + str(ti) + "_" + sim_name + "_run.out\n")
    job.write("#SBATCH -J " + job_prefix + "_" + workload_name + "_" + str(ti) + "_" + sim_name + "_run\n")
    job.write("#SBATCH -A bsc18\n")
    job.write("#SBATCH --qos=" + job_queue + "\n")
    job.write("#SBATCH --time=" + sim_time + "\n")
    job.write('\n')

    i = 0
    while (i < batch_size) and ((ti+i) < len(traces)):

      trace = traces[ti+i]
      bench = benchmarks[ti+i]

      # set enviromental variables for champsim runtime
      job.write(export_env_variables(bench, sim_name, dump_dir, enviromental_variables))
      job.write('\n')

      # simulation command
      cmd = ("time " + debug_flags + " " + root_dir + "/bin/" + exp_name + "/champsim_" + sim_name 
      + " --warmup_instructions " + warmup_instr 
      + " --simulation_instructions " + run_instr 
      + " " + trace_dir + "/" + trace + " > " + dump_dir + "/" + bench + "_" + sim_name + "_run.out\n")
      
      #os.system(cmd)
      job.write(cmd)
      job.write('\n')
      i += 1

    job.close()
    os.system("sbatch " + job_name + ".run")
    os.system("rm " + job_name + ".run")
    
    ti += batch_size