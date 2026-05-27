#include <algorithm>
#include <iterator>
#include <map>
#include <string>
#include <cmath>

#include "cache.h"
#include "util.h"
#include "env_var.h"


/*
 * Note: Hardware Implementation of paper:
 * Every Walk is Hit
 */

//#define MIN_EVICTION_POSITION 6

namespace {

	typedef struct _eviction_entry 
	{
		uint32_t lru_value;
		bool is_pte;

		_eviction_entry() : lru_value(0), is_pte(false) {}
	} eviction_entry;

	std::map<CACHE*, std::vector<eviction_entry>> least_recently_used;
	uint32_t TLB_STRESS_THRESHOLD;
	double PTE_EVICTION_RATIO; 
	std::map<CACHE*, double> current_pte_eviction_ratio;
	std::map<CACHE*, uint32_t> total_pte_evictions, total_evictions;
	std::map<CACHE*, uint32_t> current_tlb_stress_threshold;
}

void CACHE::initialize_replacement() 
{
	if (auto v = champsim::EnvVar<int>::get("TLB_STRESS_THRESHOLD")) {
		::TLB_STRESS_THRESHOLD = *v;
	}

	if (auto v = champsim::EnvVar<double>::get("PTE_EVICTION_RATIO")) {
		::PTE_EVICTION_RATIO = *v;
	}

	std::cout << NAME << " is using PTP replacement policy:" << std::endl; 
	std::cout << "\tTLB_STRESS_THRESHOLD:" << ::TLB_STRESS_THRESHOLD << std::endl;
	std::cout << "\tPTE_EVICTION_RATIO:" << ::PTE_EVICTION_RATIO << std::endl;
	::current_pte_eviction_ratio[this] = 0.0;
	::total_pte_evictions[this] = 0;
	::total_evictions[this] = 0;
	::current_tlb_stress_threshold[this] = 0;
	::least_recently_used[this] = std::vector<eviction_entry>(NUM_SET * NUM_WAY); 
}

// find replacement victim
uint32_t CACHE::find_victim(uint32_t triggering_cpu, uint64_t instr_id, uint32_t set, const BLOCK* current_set, uint64_t ip, uint64_t full_addr, uint32_t type)
{

	// first lookup for an invalid entry
	for (uint32_t i = 0; i < NUM_WAY; i++) {
		if (!current_set[i].valid) {
			//std::cout << "invalid:" << i << std::endl;
			return i;

		}
	}

	::total_evictions[this]++;

	bool found_data_candidate = false;
	uint32_t lru_victim_index = 0;
	uint32_t alt_victim_index = 0, max_alt_lru = 0;
	for (uint32_t i = 0; i < NUM_WAY; i++) {
		//std::cout << "lru:" << least_recently_used[this][set * NUM_WAY + i].lru << std::endl;
		if (::least_recently_used[this][set * NUM_WAY + i].lru_value == (NUM_WAY-1)) {
			lru_victim_index = i;
		}
/*	
		std::cout << "\tis_data:" << ::least_recently_used[this][set * NUM_WAY + i].is_data << std::endl;  
		std::cout << "\tis_pte:" << ::least_recently_used[this][set * NUM_WAY + i].is_pte << std::endl;  
		std::cout << "\tlru:" << ::least_recently_used[this][set * NUM_WAY + i].lru_value << std::endl;  
		std::cout << "\tmax_lru:" << max_alt_lru << std::endl;  
*/
		if (!(::least_recently_used[this][set * NUM_WAY + i].is_pte) && ::least_recently_used[this][set * NUM_WAY + i].lru_value > max_alt_lru) {
			//std::cout << "updating alt lru" << std::endl;
			found_data_candidate = true;
			max_alt_lru = ::least_recently_used[this][set * NUM_WAY + i].lru_value;
			alt_victim_index = i;
		}
	
	}

		//TODO: compute current pte eviction ratio
		double pte_eviction_ratio = static_cast<double>(::total_pte_evictions[this]) / static_cast<double>(::total_evictions[this]);
		::current_pte_eviction_ratio[this] = std::round( (100*pte_eviction_ratio) * 0.5f ) * 2;
//	std::cout << "alt_lru:" << max_alt_lru << std::endl;
	if (found_data_candidate
			//&& (vmem->STLB_MISS_RATE >= ::TLB_STRESS_THRESHOLD) 
			&& (::current_pte_eviction_ratio[this] <= ::PTE_EVICTION_RATIO)) {
		// adjust lru value to entries that should have been evicted instead
		for (uint32_t i = 0; i < NUM_WAY; i++) {
    	if (::least_recently_used[this][set * NUM_WAY + i].lru_value >= max_alt_lru) {
    		::least_recently_used[this][set * NUM_WAY + i].lru_value--;
			}
  	}

		//std::cout << "evicting alt:" << alt_victim_index << std::endl;
		//std::cout << "\tis_pte:" << ::least_recently_used[this][set * NUM_WAY + alt_victim_index].is_pte << std::endl;  

		return alt_victim_index;
		//return MIN_EVICTION_POSITION;
	}
/*
	std::cout << "evictin lru:" << lru_victim_index << std::endl;
	std::cout << "\tis_data:" << ::least_recently_used[this][set * NUM_WAY + lru_victim_index].is_data << std::endl;  
	std::cout << "\tis_pte:" << ::least_recently_used[this][set * NUM_WAY + lru_victim_index].is_pte << std::endl;  
*/
	if(::least_recently_used[this][set * NUM_WAY + lru_victim_index].is_pte)
		::total_pte_evictions[this]++;

	return lru_victim_index;
	//return MIN_EVICTION_POSITION;
}

// called on every cache hit and cache fill
void CACHE::update_replacement_state(	uint32_t triggering_cpu, uint32_t set, uint32_t way, 
																			uint64_t full_addr, uint64_t ip, uint64_t victim_addr, 
																			uint32_t type, uint8_t hit, REP_POL_XARGS xargs)
{
/*
	if (!hit || type != WRITE) 
		return;
*/
  uint32_t hit_lru = ::least_recently_used[this][set * NUM_WAY + way].lru_value;

  for (uint32_t i = 0; i < NUM_WAY; i++) {
    if (::least_recently_used[this][set * NUM_WAY + i].lru_value <= hit_lru) {
    	::least_recently_used[this][set * NUM_WAY + i].lru_value++;
		}
  }
  ::least_recently_used[this][set * NUM_WAY + way].lru_value = 0; // promote to the MRU position
/*
	std::cout << "addr::" << std::hex << full_addr << std::dec << std::endl;  
	std::cout << "\tis_data:" << !(static_cast<bool>(type)) << std::endl;  
	std::cout << "\tis_pte:" << (static_cast<bool>(hit)) << std::endl;  
*/
	//::least_recently_used[this][set * NUM_WAY + way].is_pte = static_cast<bool>(hit);
	::least_recently_used[this][set * NUM_WAY + way].is_pte = xargs.is_pte;
	return;
}

void CACHE::replacement_final_stats() {}

