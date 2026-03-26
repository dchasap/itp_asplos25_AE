from workload import Workload

GAPP_WORKLOADS = [
"tc.twitter-2097B.champsimtrace.xz",
"bfs.twitter-44B.champsimtrace.xz",
"bfs.twitter-242B.champsimtrace.xz",
"bfs.twitter-163B.champsimtrace.xz",
"cc.road-0B.champsimtrace.xz",
"pr.web-3076B.champsimtrace.xz",
"bfs.kron-29B.champsimtrace.xz",
"pr.urand-2209B.champsimtrace.xz",
"sssp.urand-3381B.champsimtrace.xz",
"cc.web-100B.champsimtrace.xz",
"bfs.kron-128B.champsimtrace.xz",
"cc.twitter-16B.champsimtrace.xz",
"sssp.twitter-900B.champsimtrace.xz",
"bc.web-1362B.champsimtrace.xz",
"cc.web-34B.champsimtrace.xz",
"bfs.road-19B.champsimtrace.xz",
"sssp.road-66B.champsimtrace.xz",
"bfs.road-140B.champsimtrace.xz",
"pr.twitter-833B.champsimtrace.xz",
"cc.twitter-15B.champsimtrace.xz",
"cc.twitter-10B.champsimtrace.xz",
"bfs.road-168B.champsimtrace.xz",
"cc.web-35B.champsimtrace.xz",
"bfs.kron-469B.champsimtrace.xz",
"cc.web-24B.champsimtrace.xz",
"sssp.urand-4819B.champsimtrace.xz",
"bfs.kron-542B.champsimtrace.xz",
"cc.kron-10B.champsimtrace.xz",
"bc.web-1627B.champsimtrace.xz",
"bc.twitter-2320B.champsimtrace.xz",
"tc.twitter-4460B.champsimtrace.xz",
"bfs.road-112B.champsimtrace.xz",
"sssp.kron-2397B.champsimtrace.xz",
"bfs.web-1066B.champsimtrace.xz",
"bfs.web-79B.champsimtrace.xz",
"bfs.twitter-408B.champsimtrace.xz",
"tc.road-1B.champsimtrace.xz",
"tc.road-2B.champsimtrace.xz",
"bfs.road-99B.champsimtrace.xz",
"bfs.urand-36B.champsimtrace.xz",
"sssp.twitter-1116B.champsimtrace.xz",
"bfs.web-56B.champsimtrace.xz",
"pr.urand-129B.champsimtrace.xz",
"cc.road-23B.champsimtrace.xz",
"cc.web-99B.champsimtrace.xz",
"bc.road-95B.champsimtrace.xz",
"bc.road-79B.champsimtrace.xz",
"cc.twitter-85B.champsimtrace.xz",
"sssp.twitter-792B.champsimtrace.xz",
"pr.kron-90B.champsimtrace.xz",
"tc.kron-1058B.champsimtrace.xz",
"bfs.twitter-160B.champsimtrace.xz",
"sssp.web-1185B.champsimtrace.xz",
"cc.twitter-17B.champsimtrace.xz",
"pr.twitter-2161B.champsimtrace.xz",
"cc.twitter-69B.champsimtrace.xz",
"cc.twitter-25B.champsimtrace.xz",
"tc.web-2259B.champsimtrace.xz",
"pr.road-600B.champsimtrace.xz",
"bfs.urand-118B.champsimtrace.xz",
"bfs.road-210B.champsimtrace.xz",
"cc.kron-164B.champsimtrace.xz",
"tc.urand-187B.champsimtrace.xz",
"tc.web-5088B.champsimtrace.xz",
"sssp.road-151B.champsimtrace.xz",
"bfs.kron-154B.champsimtrace.xz",
"cc.kron-135B.champsimtrace.xz",
"pr.web-4993B.champsimtrace.xz",
"pr.web-16B.champsimtrace.xz",
"cc.web-98B.champsimtrace.xz",
"tc.twitter-5663B.champsimtrace.xz",
"sssp.urand-5252B.champsimtrace.xz",
"bc.twitter-309B.champsimtrace.xz",
"bc.kron-5154B.champsimtrace.xz",
"pr.road-138B.champsimtrace.xz",
"cc.kron-78B.champsimtrace.xz",
"bfs.web-1825B.champsimtrace.xz",
"tc.twitter-34B.champsimtrace.xz",
"tc.kron-4490B.champsimtrace.xz",
"tc.kron-2469B.champsimtrace.xz",
"bc.web-704B.champsimtrace.xz",
"pr.twitter-3197B.champsimtrace.xz",
"cc.kron-82B.champsimtrace.xz",
"cc.road-36B.champsimtrace.xz",
"sssp.urand-3988B.champsimtrace.xz",
"cc.urand-353B.champsimtrace.xz",
"bc.urand-3004B.champsimtrace.xz",
"sssp.urand-4669B.champsimtrace.xz",
"tc.urand-455B.champsimtrace.xz",
"tc.web-3876B.champsimtrace.xz",
"bfs.urand-161B.champsimtrace.xz",
"cc.web-101B.champsimtrace.xz",
"cc.road-13B.champsimtrace.xz",
"cc.urand-26B.champsimtrace.xz",
"bc.road-174B.champsimtrace.xz",
"pr.kron-349B.champsimtrace.xz",
"cc.kron-17B.champsimtrace.xz",
"tc.road-0B.champsimtrace.xz",
"bfs.web-1306B.champsimtrace.xz",
"cc.web-13B.champsimtrace.xz",
"bfs.urand-410B.champsimtrace.xz",
"pr.web-709B.champsimtrace.xz",
"pr.twitter-168B.champsimtrace.xz",
"bfs.urand-60B.champsimtrace.xz",
"cc.twitter-78B.champsimtrace.xz",
"bc.road-131B.champsimtrace.xz",
"bc.kron-2608B.champsimtrace.xz",
"bfs.twitter-10B.champsimtrace.xz",
"bc.twitter-1658B.champsimtrace.xz",
"tc.urand-825B.champsimtrace.xz",
"sssp.kron-246B.champsimtrace.xz",
"bfs.road-128B.champsimtrace.xz",
"cc.kron-99B.champsimtrace.xz",
"bc.twitter-876B.champsimtrace.xz",
"tc.urand-504B.champsimtrace.xz",
"tc.urand-1112B.champsimtrace.xz",
"pr.twitter-2741B.champsimtrace.xz",
"bfs.twitter-303B.champsimtrace.xz",
"pr.road-28B.champsimtrace.xz",
"bfs.urand-356B.champsimtrace.xz",
"bfs.kron-223B.champsimtrace.xz",
"sssp.twitter-2108B.champsimtrace.xz",
"bc.web-2078B.champsimtrace.xz",
"cc.road-14B.champsimtrace.xz"
]

class GAPP(Workload):

  def __init__(self):

    self.benchmarks = []
    for trace in GAPP_WORKLOADS:
      if (not "sssp" in trace 
          and not "pr.kron-90B" in trace
          and not "pr.kron-349B" in trace
          and not "urand" in trace):  # Exclude problematic trace, OOM error
        self.benchmarks.append(trace)

    self.benchmarks_dir = "gapp"
    self.name = "GAPP"
    super().__init__()


  def get_trace_dir(self):
    return self.benchmarks_dir


  def get_traces(self):
    return self.benchmarks


  def get_benchmarks(self, with_simpoints=False):
    
    traces = self.benchmarks

    names = []
    for trace in traces:
      #if with_simpoints:
      #  name = trace.split('.')[0] + '.' + trace.split('.')[1]
      #else:
      #  name = trace.split('-')[0]

      name = trace.split('.')[0] + '.' + trace.split('.')[1]
      names.append(name)
  
    # cleanup duplicates (possible with simpoints for example)
    names = [x for i, x in enumerate(names) if x not in names[:i]]
    return names