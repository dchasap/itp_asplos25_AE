#ifndef _MEMORY_TRACE_H
#define _MEMORY_TRACE_H

#include <iostream>
#include <fstream>
#include <string>

class MemoryTracer 
{
  private:
    std::ofstream tracefile;
		std::string tracefilename;
    std::vector<uint64_t> access_vector;

  public:
    MemoryTracer() {};
    
    bool open_tracefile(std::string filename) 
    {
      tracefilename = filename;
      tracefile = std::ofstream(filename, std::ios::out);
    
      return tracefile.good();
    }

    void add_access(uint64_t address) 
    {
      access_vector.push_back(address);
    }

    void save_tracefile() 
    {
      std::cout << "Saving tracefile " << tracefilename << std::endl;
      for (auto it = access_vector.begin(); it != access_vector.end(); it++) {
        tracefile << *it << std::endl;
      }
      tracefile.close();
    }

};

class MemoryTraceReader 
{
  private:
    std::ifstream tracefile;
    std::string tracefilename;
    std::vector<uint64_t> access_vector;

  public:
    MemoryTraceReader() {};

    bool open_tracefile(std::string filename) 
    {
      tracefilename = filename;
      tracefile = std::ifstream(filename, std::ios::in);
      
      return tracefile.good(); 
    }

    uint64_t get_next_access() 
    {
      uint64_t address;
      tracefile >> address;
      return address;
    }

    std::vector<uint64_t> get_accesses() 
    {
      std::string line;
      std::getline(tracefile, line); // consume header
      while (std::getline(tracefile, line)) {
        access_vector.push_back(std::stoull(line));
      }

      return access_vector;
    }

    void close_tracefile() 
    {
      tracefile.close();
    }
};

#endif