#ifndef _MEMORY_TRACE_H
#define _MEMORY_TRACE_H

#include <iostream>
#include <fstream>
#include <string>

class MemoryTracer 
{
  private:

    struct mem_access {
      uint64_t address;
      bool is_instr;
    };

    std::ofstream tracefile;
		std::string tracefilename;
    std::vector<mem_access> access_vector;

  public:
    MemoryTracer() {};
    
    bool open_tracefile(const std::string& filename) 
    {
      tracefilename = filename;
      tracefile = std::ofstream(filename, std::ios::out);
    
      return tracefile.good();
    }

    void add_access(uint64_t address, bool is_instr) 
    {
      mem_access access = {address, is_instr};
      access_vector.push_back(access);
    }

    void save_tracefile() 
    {
      std::cout << "Saving tracefile " << tracefilename << std::endl;
      for (auto it = access_vector.begin(); it != access_vector.end(); it++) {
        tracefile << it->address << ", " << it->is_instr << std::endl;
      }
      tracefile.close();
    }

};

//TODO: Update trace reader to new format... address, is_instr
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