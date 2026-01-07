#ifndef VICTIM_CACHE_H
#define VICTIM_CACHE_H

#include <iostream>
#include <algorithm>
#include <vector>

#include "champsim.h"


class ReplacementPolicy 
{  
  public:
    virtual ~ReplacementPolicy() = default;	
    virtual void update_replacement_state(uint32_t set_idx, uint32_t way_idx, uint64_t curr_cycle, bool hit) = 0;
    virtual uint32_t find_victim(uint32_t set_idx) = 0; 
};


class LFU : public ReplacementPolicy 
{
  private:
      
    uint64_t num_set, num_way;
    std::vector<uint64_t> freq_ctr;
  
  public: 

    LFU(uint64_t _num_set, uint64_t _num_way) : num_set(_num_set), num_way(_num_way) 
    {
      freq_ctr.resize(num_set * num_way);
    }

    virtual void update_replacement_state(uint32_t set_idx, uint32_t way_idx, uint64_t, bool hit)
    {
      // Mark the way as being used on the current cycle
      //if (hit && type == WRITE) { // Skip this for writeback hits
		  //  return;
      //} No writes for PTEs
       
      if (hit) freq_ctr.at(set_idx * num_way + way_idx) ++;
      else freq_ctr.at(set_idx * num_way + way_idx) = 0;
    }

    virtual uint32_t find_victim(uint32_t set_idx)
    {
      auto begin = std::next(std::begin(freq_ctr), set_idx * num_way);
      auto end = std::next(begin, num_way);

      // Find the way whose last use frequency cntr has the lowest value
      auto victim = std::min_element(begin, end);
      assert(begin <= victim);
      assert(victim < end);
      uint32_t victim_idx = static_cast<uint32_t>(std::distance(begin, victim)); // cast protected by prior asserts
	    //std::cout << "victim:" << victim_idx << std::endl;
	    return victim_idx;
    }
};


class LRU : public ReplacementPolicy 
{
  private:

    uint32_t num_set, num_way;
    std::vector<uint64_t> last_used_cycles;

  public:
    LRU(uint64_t _num_set, uint64_t _num_way) : num_set(_num_set), num_way(_num_way) 
    {
      last_used_cycles.resize(num_set * num_way);
    }

    virtual void update_replacement_state(uint32_t set_idx, uint32_t way_idx, uint64_t curr_cycle, bool hit) 
    {
      // Mark the way as being used on the current cycle
      if (!hit) // Skip this for writeback hits
        last_used_cycles.at(set_idx * num_way + way_idx) = curr_cycle; 
    }

    virtual uint32_t find_victim(uint32_t set_idx) 
    {
      auto begin = std::next(std::begin(last_used_cycles), set_idx * num_way);
      auto end = std::next(begin, num_way);

      // Find the way whose last use cycle is most distant
      auto victim = std::min_element(begin, end);
      assert(begin <= victim);
      assert(victim < end);
      return static_cast<uint32_t>(std::distance(begin, victim)); // cast protected by prior asserts
    }
};

#endif