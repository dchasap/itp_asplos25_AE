
import os 
import workloads


def export_env_variables(benchmark, sim_name, dump_dir, enviromental_variables):

  export_cmd = "export PTP_EXTRA_STATS_FILE=" + dump_dir + "/" + benchmark + "_" + sim_name + "_access_rate.csv\n"
  export_cmd += "export INSTR_PAGE_DIST_FILENAME=" + dump_dir + "/" + benchmark + "_" + sim_name + "_instr.pdst\n"
  export_cmd += "export DATA_PAGE_DIST_FILENAME=" + dump_dir + "/" + benchmark + "_" + sim_name + "_data.pdst\n"
  export_cmd += "export PAGE_ADDRESS_STATS_FILENAME_PREFIX=" + dump_dir + "/" + benchmark + "_" + sim_name + "_page_access_stats\n"
  #export_cmd += "export TXVC_MEM_ACCESS_TRACE_FILE=" + dump_dir + "/" + benchmark + "_" + sim_name + "_txvc_mem_trace.csv\n"
  #export_cmd += "export TXVC_CACHE_FILTER_=" + dump_dir + "/" + benchmark + "_" + sim_name + "_txvc_mem_histogram.csv\n"

  for var in enviromental_variables:
    if (var == "TXVC_MEMORY_TRACE_PATH"):
      export_cmd += "export " + var + "=" + enviromental_variables[var] + "/" + benchmark + "_txvc_mem_trace.csv\n"
    elif (var == "CACHE_FILTER_MEMORY_TRACE_PATH"):
      export_cmd += "export " + var + "=" + enviromental_variables[var] + "/" + benchmark + "_txvc_mem_trace.csv\n"
    elif (var == "REUSE_DIST_FILENAME_PREFIX"):
      export_cmd += "export REUSE_DIST_FILENAME_PREFIX=" + dump_dir + "/" + benchmark + "_" + sim_name + "_reuse_dist\n"
    else:
      export_cmd += "export " + var + "=" + enviromental_variables[var] + "\n"

  export_cmd += '\n'

  return export_cmd


def inline_export_env_variables(benchmark, sim_name, dump_dir, enviromental_variables):

  export_cmd = "export PTP_EXTRA_STATS_FILE=" + dump_dir + "/" + benchmark + "_" + sim_name + "_access_rate.csv; "
  export_cmd += "export INSTR_PAGE_DIST_FILENAME=" + dump_dir + "/" + benchmark + "_" + sim_name + "_instr.pdst; "
  export_cmd += "export DATA_PAGE_DIST_FILENAME=" + dump_dir + "/" + benchmark + "_" + sim_name + "_data.pdst;"
  export_cmd += "export PAGE_ADDRESS_STATS_FILENAME_PREFIX=" + dump_dir + "/" + benchmark + "_" + sim_name + "_page_access_stats; "
  export_cmd += "export TXVC_MEM_HISTOGRAM_FILE=" + dump_dir + "/" + benchmark + "_" + sim_name + "_txvc_mem_access_histogram.csv\n"

  for var in enviromental_variables:
    export_cmd += "export " + var + "=" + enviromental_variables[var] + "; "

  #export_cmd += '\n'

  return export_cmd


def run_simulation_batch(root_dir, trace_dir, dump_dir, sim_name, exp_name, workload_name, sim_config, enviromental_variables, parallel_run, debug_run):
  
  os.system("mkdir -p " + dump_dir)

  traces, trace_path = workloads.get_benchmark_traces(workload_name)
  trace_dir = trace_dir + "/" + trace_path
  benchmarks = workloads.get_benchmark_names(workload_name, with_simpoints=True)

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

    if parallel_run:
      job.write("#SBATCH --nodes=1\n")
      job.write("#SBATCH --ntasks=" + str(batch_size) + "\n")
      job.write("#SBATCH --cpus-per-task=1\n")
    
    job.write("#SBATCH -o " + dump_dir + "/" + workload_name + "_" + str(ti) + "_" + sim_name + "_run.out\n")
    job.write("#SBATCH -J " + job_prefix + "_" + workload_name + "_" + str(ti) + "_" + sim_name + "_run\n")
    job.write("#SBATCH -A bsc18\n")
    job.write("#SBATCH --qos=" + job_queue + "\n")
    job.write("#SBATCH --time=" + sim_time + "\n")
    job.write('\n')

    #if (parallel_run):
    #  commands = []
    #  print('Parallel run is not supported yet, continuing with serial run.')

    i = 0
    while (i < batch_size) and ((ti+i) < len(traces)):

      trace = traces[ti+i]
      bench = benchmarks[ti+i]

      if (parallel_run):
        #export_env_variables_cmd = inline_export_env_variables(bench, sim_name, dump_dir, enviromental_variables)
        export_env_variables_cmd = export_env_variables(bench, sim_name, dump_dir, enviromental_variables)
      else:
        export_env_variables_cmd = export_env_variables(bench, sim_name, dump_dir, enviromental_variables)

      # simulation command
      run_cmd = ("time " + debug_flags + " " + root_dir + "/bin/" + exp_name + "/champsim_" + sim_name 
      + " --warmup_instructions " + warmup_instr 
      + " --simulation_instructions " + run_instr 
      + " " + trace_dir + "/" + trace + " &> " + dump_dir + "/" + bench + "_" + sim_name + "_run.out")

      # set enviromental variables for champsim runtime
      job.write(export_env_variables_cmd)
      #job.write('\n')

      #os.system(cmd)
      #job.write(run_cmd)
      if (parallel_run):
        job.write(run_cmd + " &\n")
        #job.write(' &\n')
      else:
        job.write(run_cmd + "\n")
        #job.write('\n')

      job.write('\n')
      i += 1

    if (parallel_run):
      job.write("wait\n")

    job.close()
    os.system("sbatch " + job_name + ".run")
    os.system("rm " + job_name + ".run")
    
    ti += batch_size