
import qualcomm_srv_workloads
import google_srv_workloads


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
    traces = goole_srv_workloads.get_google_srv()
    traces_dir = google_srv_workloads_dir()

  elif SPEC_CPU_2006 == "spec_cpu_2006":
    traces = spec_cpu_workloads.get_spec_cpu_2006()
    traces_dir = spec_cpu_workloads.get_spec_cpu_dir()
  
  elif SPEC_CPU_2017 == "spec_cpu_2017":
    traces = spec_cpu_workloads.get_spec_cpu_2017()
    traces_dir = spec_cpu_workloads.get_spec_cpu_dir()

  elif workload_name == "debug":
    traces = [ qualcomm_srv_workloads.get_selected_qualcomm_srv()[0] ]
    traces_dir = qualcomm_srv_workloads.get_qualcomm_srv_dir()

  return traces, traces_dir



def get_benchmark_names(workload_name):

  traces, traces_dir = get_benchmark_traces(workload_name)

  names = []
  for trace in traces:
    name = trace.split('.')[0]
    names.append(name)
  
  return names
