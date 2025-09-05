
import qualcomm_srv_workloads
import google_srv_workloads
import spec_cpu_workloads

def get_benchmark_traces(workload_name):

  if workload_name == "qualcomm_srv_ap":
    traces = qualcomm_srv_workloads.get_qualcomm_srv()
    traces_dir = qualcomm_srv_workloads.get_qualcomm_srv_dir()

  elif workload_name == "selected_qualcomm_srv_ap":
    traces = qualcomm_srv_workloads.get_selected_qualcomm_srv()
    traces_dir = qualcomm_srv_workloads.get_qualcomm_srv_dir()
  
  elif workload_name == "smt_qualcomm_srv_ap":
    traces = qualcomm_srv_workloads.get_smt_qualcomm_srv()
    traces_dir = qualcomm_srv_workloads.get_qualcomm_srv_dir()
  
  elif workload_name == "google_srv":
    traces = google_srv_workloads.get_google_srv()
    traces_dir = google_srv_workloads.get_google_srv_dir()

  elif workload_name == "spec_cpu_2006":
    traces = spec_cpu_workloads.get_benchmarks("2006")
    traces_dir = spec_cpu_workloads.get_traces_dir("2006")
  
  elif workload_name == "spec_cpu_2017":
    traces = spec_cpu_workloads.get_benchmarks("2017")
    traces_dir = spec_cpu_workloads.get_traces_dir("2017")

  elif workload_name == "spec_cpu_all":
    traces = spec_cpu_workloads.get_benchmarks("all")
    traces_dir = spec_cpu_workloads.get_traces_dir("all")

  elif workload_name == "debug":
    #traces = [ qualcomm_srv_workloads.get_selected_qualcomm_srv()[0] ]
    #traces_dir = qualcomm_srv_workloads.get_qualcomm_srv_dir()
    traces = [ spec_cpu_workloads.get_benchmarks("2017")[0] ]
    traces_dir = spec_cpu_workloads.get_traces_dir("2017")


  return traces, traces_dir


def get_benchmark_names(workload_name, with_simpoints=False):

  traces, traces_dir = get_benchmark_traces(workload_name)

  names = []
  for trace in traces:
    if workload_name == "spec_cpu_2006" or workload_name == "spec_cpu_2017":
      if with_simpoints:
        name = trace.split('.')[0] + '.' + trace.split('.')[1]
      else:
        name = trace.split('-')[0]
    else:
      name = trace.split('.')[0]
    names.append(name)
  
  # cleanup duplicates (possible with simpoints for example)
  names = [x for i, x in enumerate(names) if x not in names[:i]]

  return names


def get_simpoints_idx(workload_name, benchmark):

  if workload_name == "spec_cpu_2006" or workload_name == "spec_cpu_2017":
    
    simpoints_idx_file = open("./weights/" + benchmark + "/concat.txt")
    simpoints_idx = []
    for line in simpoints_idx_file:
      simpoint_idx = line.split(";")
      print(simpoint_idx)
      if float(simpoint_idx[1]) > 0.05: #TODO: check if that's the correct threshold
        simpoints_idx.append(simpoint_idx[0].strip() + "B")
  
    return simpoints_idx

  else:
    return None


def get_simpoints_n_weights(workload_name, benchmark):
  
  if workload_name == "spec_cpu_2006" or workload_name == "spec_cpu_2017":
    
    simpoints_n_weights_file = open("./weights/" + benchmark + "/concat.txt")
    simpoints = []
    weights = []
    for line in simpoints_n_weights_file:
        simpoint_n_weight = line.split(";")
        simpoint = simpoint_n_weight[0].strip()
        weight = float(simpoint_n_weight[1].strip())
        if weight > 0.05: #TODO: check if that's the correct threshold
          simpoints.append(simpoint + "B") 
          weights.append(weight)
    
    return (simpoints, weights)

  else:
    return (None, None)