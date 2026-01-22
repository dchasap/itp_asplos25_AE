from workload import Workload

_GOOGLE_SRV_WORKLOADS = [
"benchbase-twitter.champsimtrace.gz",
"benchbase-wikipedia.champsimtrace.gz",
"charlie.1006518.champsimtrace.gz",
"dacapo-kafka.champsimtrace.gz",
"dacapo-spring.champsimtrace.gz",
"dacapo-tomcat.champsimtrace.gz",
"delta.507252.champsimtrace.gz",
"merced.467915.champsimtrace.gz",
"mwnginxfpm-wiki.champsimtrace.gz",
"nodeapp-nodeapp.champsimtrace.gz",
"renaissance-finagle-chirper.champsimtrace.gz",
"renaissance-finagle-http.champsimtrace.gz",
"whiskey.426708.champsimtrace.gz"
]

GOOGLE_SRV_WORKLOADS= [
"arizona_0000.champsim.gz",
"arizona_0001.champsim.gz",
"arizona_0002.champsim.gz",
"charlie_0000.champsim.gz",
"charlie_0001.champsim.gz",
"charlie_0002.champsim.gz",
"charlie_0003.champsim.gz",
"charlie_0004.champsim.gz",
"merced_0000.champsim.gz",
"merced_0001.champsim.gz",
"merced_0002.champsim.gz",
"merced_0003.champsim.gz",
"merced_0004.champsim.gz",
"sierra.a.3_0000.champsim.gz",
"sierra.a.3_0001.champsim.gz",
"sierra.a.3_0002.champsim.gz",
"sierra.a.3_0003.champsim.gz",
"sierra.a.3_0004.champsim.gz",
"sierra.a.4_0000.champsim.gz",
"sierra.a.4_0001.champsim.gz",
"sierra.a.4_0002.champsim.gz",
"sierra.a.4_0003.champsim.gz",
"sierra.a.4_0004.champsim.gz",
"sierra.a.6_0000.champsim.gz",
"sierra.a.6_0001.champsim.gz",
"sierra.a.6_0002.champsim.gz",
"sierra.a.6_0003.champsim.gz",
"sierra.a.6_0004.champsim.gz",
"tahoe_0000.champsim.gz",
"tahoe_0001.champsim.gz",
"tahoe_0002.champsim.gz",
"tahoe_0003.champsim.gz",
"tahoe_0004.champsim.gz",
"tango_0000.champsim.gz",
"tango_0001.champsim.gz",
"tango_0002.champsim.gz",
"tango_0003.champsim.gz",
"tango_0004.champsim.gz",
"yankee_0000.champsim.gz",
"yankee_0001.champsim.gz",
"yankee_0002.champsim.gz",
"yankee_0003.champsim.gz",
"yankee_0004.champsim.gz"
]


class GoogleSRV(Workload):

  def __init__(self):
    self.benchmarks = GOOGLE_SRV_WORKLOADS
    self.benchmarks_dir = "google_traces_dpc4"
    super().__init__()


  def get_benchmarks(self):
    traces = self.benchmarks

    names = []
    for trace in traces:

      if ("sierra" in trace):
        name = trace.split('.' )[2]
      else:
        name = trace.split('.')[0]

      names.append(name)
  
    # cleanup duplicates (possible with simpoints for example)
    names = [x for i, x in enumerate(names) if x not in names[:i]]
    return names

  def get_trace_dir(self):
    return self.benchmarks_dir
  
  def get_traces(self):
    return self.benchmarks
