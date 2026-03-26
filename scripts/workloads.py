from spec_cpu_workloads import SpecCPU
from gapp_workloads import GAPP
from qualcomm_srv_workloads import QualcommSRV_AP
from google_srv_workloads import GoogleSRV
from test_workloads import TEST


class Workloads:
  
  def __init__(self, workload_name):

    if workload_name == "qualcomm_srv_ap":
      #traces = qualcomm_srv_workloads.get_qualcomm_srv()
      #races_dir = qualcomm_srv_workloads.get_qualcomm_srv_dir()
      self.workload = QualcommSRV_AP(selected=False, smt=False)
    
    elif workload_name == "selected_qualcomm_srv_ap":
      #traces = qualcomm_srv_workloads.get_selected_qualcomm_srv()
      #traces_dir = qualcomm_srv_workloads.get_qualcomm_srv_dir()
      self.workload = QualcommSRV_AP(selected=True, smt=False)
    
    elif workload_name == "smt_qualcomm_srv_ap":
      #traces = qualcomm_srv_workloads.get_smt_qualcomm_srv()
      #traces_dir = qualcomm_srv_workloads.get_qualcomm_srv_dir()
      self.workload = QualcommSRV_AP(selected=False, smt=True)
    
    elif workload_name == "google_srv":
      #traces = google_srv_workloads.get_google_srv()
      #traces_dir = google_srv_workloads.get_google_srv_dir()
      self.workload = GoogleSRV()
    
    elif workload_name == "gapp":
      #traces = gapp_workloads.get_gapp_srv()
      #traces_dir = gapp_workloads.get_gapp_srv_dir()
      self.workload = GAPP()
    
    elif workload_name == "spec_cpu_2006":
      #traces = spec_cpu_workloads.get_benchmarks("2006")
      #traces_dir = spec_cpu_workloads.get_traces_dir("2006")
      self.workload = SpecCPU(version="2006")

    elif workload_name == "spec_cpu_2017":
      #traces = spec_cpu_workloads.get_benchmarks("2017")
      #traces_dir = spec_cpu_workloads.get_traces_dir("2017")
      self.workload = SpecCPU(version="2017")

    elif workload_name == "spec_cpu_all":
      #traces = spec_cpu_workloads.get_benchmarks("all")
      #traces_dir = spec_cpu_workloads.get_traces_dir("all")
      self.workload = SpecCPU(version="all")

    elif workload_name == "test":
      self.workload = TEST()
      
    else:
      print("Workload " + workload_name + " not recognized.")
      exit(1)

    return


  def get_traces(self):
    return self.workload.get_traces()


  def get_trace_dir(self):
    return self.workload.get_trace_dir()


  def get_benchmark_names(self, with_simpoints=False):
    return self.workload.get_benchmarks(with_simpoints=with_simpoints)


  def get_simpoints_n_weights(self, benchmark):
    simpoints = self.workload.get_simpoints(benchmark)
    weights = self.workload.get_weights(benchmark)
    return (simpoints, weights)