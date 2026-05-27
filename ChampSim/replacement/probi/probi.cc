#include <algorithm>
#include <map>
#include <utility>
#include <string>

#include "cache.h"
#include "util.h"
#include "env_var.h"

namespace {

	struct LRUStackElem {
		uint64_t last_used_cycle;
		bool is_instr;

 	 	bool operator<(const LRUStackElem &other) const { // member function
        return last_used_cycle < other.last_used_cycle;
    }
	};

	std::map<CACHE*, std::vector<LRUStackElem>> last_used_cycles;
	uint32_t instr_eviction_prob;
}


void CACHE::initialize_replacement()
{
	if (auto v = champsim::EnvVar<int>::get("PROBR_INSTR_EVICT_PROB")) {
		instr_eviction_prob = *v;
	} else {
		std::cerr << "PROBR_INSTR_EVICT_PROB not set!" << std::endl;
		exit(1);
	}

	std::cout << this->NAME << " using probabilistic eviction with instr eviction probability " 
						<< instr_eviction_prob << "%" << std::endl;

	::last_used_cycles[this] = std::vector<LRUStackElem>(NUM_SET * NUM_WAY); 

  srand((unsigned) time(NULL));
}

// called on every cache hit and cache fill
void CACHE::update_replacement_state(	uint32_t triggering_cpu, uint32_t set, uint32_t way, 
																			uint64_t full_addr, uint64_t ip, uint64_t victim_addr, 
																			uint32_t type, uint8_t hit,
																			CACHE::REP_POL_XARGS xargs)
{
  // Mark the way as being used on the current cycle
  if (!hit || type != WRITE) { // Skip this for writeback hits
    ::last_used_cycles[this].at(set * NUM_WAY + way).last_used_cycle = current_cycle;
    ::last_used_cycles[this].at(set * NUM_WAY + way).is_instr = xargs.is_instr;
	}

	return;
}

// find replacement victim
uint32_t CACHE::find_victim(uint32_t triggering_cpu, uint64_t instr_id, uint32_t set, const BLOCK* current_set, uint64_t ip, uint64_t full_addr, uint32_t type)
{

	auto begin = std::next(std::begin(::last_used_cycles[this]), set * NUM_WAY);
  auto end = std::next(begin, NUM_WAY);
  auto victim = std::min_element(begin, end); // this is the standar lru victim

	uint64_t probability = rand() % 100;
	if (probability < instr_eviction_prob) {
  	
		uint32_t max_cycle = 0;
		for (auto it = begin; it != end; ++it) {
			if ((max_cycle <= it->last_used_cycle) && it->is_instr) {
				max_cycle = it->last_used_cycle;
				victim = it;
			}
		}
	}
  
  return static_cast<uint32_t>(std::distance(begin, victim)); // cast protected by prior asserts

}


// use this function to print out your own stats at the end of simulation
void CACHE::replacement_final_stats() {}

