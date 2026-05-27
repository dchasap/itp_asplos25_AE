#include <algorithm>
#include <map>
#include <utility>
#include <string>

#include "cache.h"
#include "util.h"
#include "env_var.h"

//#define maxRRPV 12
//#define NUM_POLICY 2
//#define SDM_SIZE 32
//#define TOTAL_SDM_SETS NUM_CPUS* NUM_POLICY* SDM_SIZE
//#define BIP_MAX 32
//#define PSEL_WIDTH 10
//#define PSEL_MAX ((1 << PSEL_WIDTH) - 1)
//#define PSEL_THRS PSEL_MAX / 2

//#std::map<CACHE*, unsigned> bip_counter;
//#std::map<CACHE*, std::vector<std::size_t>> rand_sets;
//#std::map<std::pair<CACHE*, std::size_t>, unsigned> PSEL;

uint32_t instr_pos, data_pos;
uint32_t maxRRPV;

std::map<uint64_t, int32_t> vpn_freq_acc;
namespace {
	class SatCnt {
		private:
			uint32_t cnt;
			uint32_t max_value;

		public:
			SatCnt(uint32_t nbits) {
				max_value = 1 << nbits;
				max_value = 50;
				std::cout << "Init sat counter with " << nbits << " bits (max:" << max_value  << ")." << std::endl;
			}

			SatCnt operator++(int) {
				SatCnt tmp = *this;
    		if (cnt < max_value) cnt++;
				return tmp;
    	}

			void reset() {
				cnt = 0;
			}

			bool saturated() {
				return (cnt == max_value);
			}
	};

	uint32_t TLB_LOWER_STRESS_THRESHOLD;
	uint32_t TLB_UPPER_STRESS_THRESHOLD;
	std::map<CACHE*, std::vector<uint64_t>> last_used_cycles;
	std::map<CACHE*, std::vector<uint32_t>> least_recently_used;
	std::map<CACHE*, std::vector<SatCnt>> freq_cnt;
}

void CACHE::initialize_replacement()
{
	if (auto v = champsim::EnvVar<int>::get("TLB_LOWER_STRESS_THRESHOLD")) {
		::TLB_LOWER_STRESS_THRESHOLD = *v;
		//::TLB_STRESS_THRESHOLD = 0;
	}

	if (auto v = champsim::EnvVar<int>::get("TLB_UPPER_STRESS_THRESHOLD")) {
		::TLB_UPPER_STRESS_THRESHOLD = *v;
		::TLB_UPPER_STRESS_THRESHOLD = 2.5;
	}

	if (auto v = champsim::EnvVar<int>::get("ITP_MAX_LRU")) {
	  maxRRPV = *v;
	} else {
	  std::cerr << "ITP_MAX_LRU not set!" << std::endl;
	  exit(1);
	}
	if (auto v = champsim::EnvVar<int>::get("ITP_INSTR_POS")) instr_pos = *v; else { std::cerr << "ITP_INSTR_POS not set!" << std::endl; exit(1); }
	if (auto v = champsim::EnvVar<int>::get("ITP_DATA_POS")) data_pos = *v; else { std::cerr << "ITP_DATA_POS not set!" << std::endl; exit(1); }
	std::cout << this->NAME << " using iTP with max lru@" << maxRRPV << std::endl;
	std::cout << this->NAME << " using iTP with instr@" << instr_pos 
						<< " and data@" << data_pos << std::endl;

	::last_used_cycles[this] = std::vector<uint64_t>(NUM_SET * NUM_WAY); 
	::least_recently_used[this] = std::vector<uint32_t>(NUM_SET * NUM_WAY);
	::freq_cnt[this] = std::vector<SatCnt>(NUM_SET * NUM_WAY, SatCnt(3));
}

// called on every cache hit and cache fill
void CACHE::update_replacement_state(	uint32_t triggering_cpu, uint32_t set, uint32_t way, 
																			uint64_t full_addr, uint64_t ip, uint64_t victim_addr, 
																			uint32_t type, uint8_t hit,
																			CACHE::REP_POL_XARGS xargs)
{
	/*
	// if policy is disabled use LRU
	if (vmem->STLB_MISS_RATE >= ::TLB_STRESS_THRESHOLD) {  
	  // Mark the way as being used on the current cycle
  	if (!hit || type != WRITE) // Skip this for writeback hits
    	::last_used_cycles[this].at(set * NUM_WAY + way) = current_cycle;

		return;
	}
	*/

	if (!xargs.is_instr) {
		// do not update replacement state for writebacks
		/*
		if (type == WRITEBACK) {
			block[set * NUM_WAY + way].lru = maxRRPV - 1;
			return;
		}
		*/
		// cache hit
		if (hit) {
			::least_recently_used[this][set * NUM_WAY + way] = maxRRPV - data_pos;
			return;
		}

		::least_recently_used[this][set * NUM_WAY + way] = maxRRPV - 1;
		return;
	}

	/*
	 * idip_fac
	 */
	//uint64_t vpn = block[set * NUM_WAY + way].v_address >> LOG2_PAGE_SIZE;
	
	uint64_t vpn = victim_addr >> LOG2_PAGE_SIZE;
	// get access frequency and setup new entry if it doesn't exit
	int32_t acc_freq = 0;
	if (vpn_freq_acc.find(vpn) == vpn_freq_acc.end()) {
		acc_freq = -2;
		vpn_freq_acc[vpn] = -2;
	} else {
		acc_freq = vpn_freq_acc[vpn];
	}

	// choose the correct placement for new block/translation
	if (acc_freq < 50) {
		::least_recently_used[this][set * NUM_WAY + way] = maxRRPV - instr_pos;
	}
	else {
		::least_recently_used[this][set * NUM_WAY + way] = 0;
		//std::cout << maxRRPV - ((acc_freq / 50) % 4) << std::endl;
		//block[set * NUM_WAY + way].lru = maxRRPV - ((acc_freq / 50) % 4);
	}

	// update fac
	vpn_freq_acc[vpn]++;
	
	if (!hit) {
		::freq_cnt[this][set * NUM_WAY + way].reset();	
	} else {
		::freq_cnt[this][set * NUM_WAY + way]++;	
	}
/*
	if (::freq_cnt[this][set * NUM_WAY + way].saturated()) {
		::least_recently_used[this][set * NUM_WAY + way] = 0;
		//::least_recently_used[this][set * NUM_WAY + way] = maxRRPV - instr_pos;
	} else {
		::least_recently_used[this][set * NUM_WAY + way] = 0;
		//::least_recently_used[this][set * NUM_WAY + way] = maxRRPV - instr_pos;
	}
	*/
	return;
}

// find replacement victim
uint32_t CACHE::find_victim(uint32_t triggering_cpu, uint64_t instr_id, uint32_t set, const BLOCK* current_set, uint64_t ip, uint64_t full_addr, uint32_t type)
{

	// if policy is disabled use LRU
	if (((vmem->STLB_MISS_RATE >= ::TLB_LOWER_STRESS_THRESHOLD) && (vmem->STLB_MISS_RATE <= ::TLB_UPPER_STRESS_THRESHOLD)) && false) {  
	  auto begin = std::next(std::begin(::last_used_cycles[this]), set * NUM_WAY);
  	auto end = std::next(begin, NUM_WAY);

  	// Find the way whose last use cycle is most distant
  	auto victim = std::min_element(begin, end);
  	assert(begin <= victim);
  	assert(victim < end);
  	return static_cast<uint32_t>(std::distance(begin, victim)); // cast protected by prior asserts
	}

  // look for the maxRRPV line
  auto begin = std::next(std::begin(::least_recently_used[this]), set * NUM_WAY);
  auto end = std::next(begin, NUM_WAY);
  auto victim = std::find_if(begin, end, [](uint32_t x) { return x == maxRRPV; }); // hijack the lru field
  while (victim == end) {
  	for (auto it = begin; it != end; ++it)
      (*it)++;

  	victim = std::find_if(begin, end, [](uint32_t x) { return x == maxRRPV; });
  }

  return std::distance(begin, victim);
}

bool cmp(const std::pair<uint64_t, uint32_t> &a, const std::pair<uint64_t, uint32_t> &b) 
{
	return (a.second < b.second);
}

// use this function to print out your own stats at the end of simulation
void CACHE::replacement_final_stats() {
/*
	std::vector <pair<uint64_t, uint32_t>> sorted_fac;
	for (auto& i : vpn_freq_acc) {
		sorted_fac.push_back(i);
	}	
	std::sort(sorted_fac.begin(), sorted_fac.end(), cmp);
	for (auto& i : sorted_fac) {
		std::cout << std::hex << i.first << std::dec;
		std::cout << ", " << i.second + maxRRPV + 1 << std::endl;
	}
	*/
}



