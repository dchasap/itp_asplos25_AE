from workload import Workload

TEST_QUALCOMM = [
  "srv100_ap.champsimtrace.xz",
]

class TEST(Workload):

  def __init__(self):

    self.benchmarks = TEST_QUALCOMM
    self.name = "srv100_ap"
    self.benchmarks_dir = "qualcomm_srv"

    super().__init__()


  def get_trace_dir(self):
    return self.benchmarks_dir


  def get_traces(self):
    return self.benchmarks