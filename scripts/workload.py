
class Workload:

    def __init__(self):
        return


    def get_workload_name(self):
        return self.name


    def get_benchmarks(self, with_simpoints=False):
        traces = self.benchmarks

        names = []
        for trace in traces:

            name = trace.split('.')[0]
            names.append(name)
  
        # cleanup duplicates (possible with simpoints for example)
        names = [x for i, x in enumerate(names) if x not in names[:i]]
        return names


    def get_trace_dir(self):
        raise NotImplementedError("Subclasses must implement run()")


    def get_traces(self):
        raise NotImplementedError("Subclasses must implement run()")


    def has_simpoints(self):
        return False


    def get_simpoints(self, benchmark):
        return None


    def get_weights(self, benchmark):
        return None 

