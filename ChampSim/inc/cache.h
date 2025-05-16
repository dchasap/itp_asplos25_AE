/*
 *    Copyright 2023 The ChampSim Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef CACHE_H
#define CACHE_H

#include <array>
#include <bitset>
#include <cassert>
#include <deque>
#include <functional>
#include <list>
#include <string>
#include <vector>
#include <string.h>

#include "champsim.h"
#include "champsim_constants.h"
#include "memory_class.h"
#include "operable.h"

#if defined FORCE_HIT || defined MULTIPLE_PAGE_SIZE || defined VICTIM_CACHE
#include "vmem.h"
#endif

#if defined ENABLE_EXTRA_CACHE_STATS
#include "reuse_dist.h"
#include "page_address_stats.h"
#endif

#if defined PTP_REPLACEMENT_POLICY
#include <cmath>
#endif

#if defined TRACK_BRANCH_HISTORY 
extern uint64_t global_path_history_MHRP;
extern uint64_t global_path_history;
extern uint64_t uncondIndHistory;
extern uint64_t condHistory;
extern uint64_t uncondIndHistory_old;
extern uint64_t condHistory_old;
#endif

struct cache_stats {
  std::string name;
  // prefetch stats
  uint64_t pf_requested = 0;
  uint64_t pf_issued = 0;
  uint64_t pf_useful = 0;
  uint64_t pf_useless = 0;
  uint64_t pf_fill = 0;
	uint64_t pf_crossed = 0;

  std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> hits = {};
  std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> misses = {};

#if defined ENABLE_EXTRA_CACHE_STATS
	std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> ihits = {};
  std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> imisses = {};
	std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> dhits = {};
  std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> dmisses = {};
	std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> ithits = {};
  std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> itmisses = {};
	std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> dthits = {};
  std::array<std::array<uint64_t, NUM_CPUS>, NUM_TYPES> dtmisses = {};
	uint64_t total_imiss_latency = 0;
	uint64_t total_dmiss_latency = 0;
	uint64_t total_itmiss_latency = 0;
	uint64_t total_dtmiss_latency = 0;
  double max_cache_occupancy = 0;
#endif

#if defined ENABLE_PAGE_CROSSING_STATS
	uint64_t pf_crossing_pages_tlb_hit = 0;
	uint64_t pf_crossing_pages_tlb_miss = 0;
#endif  

  uint64_t total_miss_latency = 0;
};

struct cache_queue_stats {
  uint64_t RQ_ACCESS = 0;
  uint64_t RQ_MERGED = 0;
  uint64_t RQ_FULL = 0;
  uint64_t RQ_TO_CACHE = 0;
  uint64_t PQ_ACCESS = 0;
  uint64_t PQ_MERGED = 0;
  uint64_t PQ_FULL = 0;
  uint64_t PQ_TO_CACHE = 0;
  uint64_t WQ_ACCESS = 0;
  uint64_t WQ_MERGED = 0;
  uint64_t WQ_FULL = 0;
  uint64_t WQ_TO_CACHE = 0;
  uint64_t WQ_FORWARD = 0;
  uint64_t PTWQ_ACCESS = 0;
  uint64_t PTWQ_MERGED = 0;
  uint64_t PTWQ_FULL = 0;
  uint64_t PTWQ_TO_CACHE = 0;
};

class CACHE : public champsim::operable, public MemoryRequestConsumer, public MemoryRequestProducer
{
  enum [[deprecated(
      "Prefetchers may not specify arbitrary fill levels. Use CACHE::prefetch_line(pf_addr, fill_this_level, prefetch_metadata) instead.")]] FILL_LEVEL{
      FILL_L1 = 1, FILL_L2 = 2, FILL_LLC = 4, FILL_DRC = 8, FILL_DRAM = 16};

  bool try_hit(const PACKET& handle_pkt);
  bool handle_fill(const PACKET& fill_mshr);
  bool handle_miss(const PACKET& handle_pkt);
  bool handle_write(const PACKET& handle_pkt);

  struct BLOCK {
    bool valid = false;
    bool prefetch = false;
    bool dirty = false;

    uint64_t address = 0;
    uint64_t v_address = 0;
    uint64_t data = 0;

    uint32_t pf_metadata = 0;

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined VICTIM_CACHE
		bool is_instr = false;
		bool is_pte = false;
#endif

#if defined MULTIPLE_PAGE_SIZE
		uint32_t page_size = 0;
		uint64_t base_vpn = 0;
#endif

#if defined ENABLE_PAGE_CROSSING_STATS
		uint64_t page_crossing = 0; 
#endif

#if defined VICTIM_CACHE
		bool is_doa = true;
#endif 

/*
#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined FORCE_PTE_HIT
		bool is_instr = false;
		uint8_t type = 0;
#endif
*/
  };
  using set_type = std::vector<BLOCK>;

#if defined ENABLE_TRANSLATION_AWARE_REPLACEMENT
	struct REP_POL_XARGS {
		bool is_instr = false;
		bool is_pte = false;
		bool is_replay = false;
		std::size_t translation_level = 0;
	};
#endif

#if defined SPLIT_STLB
  std::pair<set_type::iterator, set_type::iterator> get_set_span(uint64_t address, uint8_t type);
 	std::pair<set_type::const_iterator, set_type::const_iterator> get_set_span(uint64_t address, uint8_t type) const;
  std::size_t get_set_index(uint64_t address, uint8_t type) const;
#else
  std::pair<set_type::iterator, set_type::iterator> get_set_span(uint64_t address);
 	std::pair<set_type::const_iterator, set_type::const_iterator> get_set_span(uint64_t address) const;
  std::size_t get_set_index(uint64_t address) const;
#endif

public:
  struct NonTranslatingQueues : public champsim::operable {
    std::deque<PACKET> RQ, PQ, WQ, PTWQ;
    const std::size_t RQ_SIZE, PQ_SIZE, WQ_SIZE, PTWQ_SIZE;
    const uint64_t HIT_LATENCY;
    const unsigned OFFSET_BITS;
    const bool match_offset_bits;

    using stats_type = cache_queue_stats;

    std::vector<stats_type> sim_stats, roi_stats;

    NonTranslatingQueues(double freq_scale, std::size_t rq_size, std::size_t pq_size, std::size_t wq_size, std::size_t ptwq_size, uint64_t hit_latency,
                         unsigned offset_bits, bool match_offset)
        : champsim::operable(freq_scale), RQ_SIZE(rq_size), PQ_SIZE(pq_size), WQ_SIZE(wq_size), PTWQ_SIZE(ptwq_size), HIT_LATENCY(hit_latency),
          OFFSET_BITS(offset_bits), match_offset_bits(match_offset)
    {
    }
    void operate() override;

    template <typename R>
    bool do_add_queue(R& queue, std::size_t queue_size, const PACKET& packet);

    bool add_rq(const PACKET& packet);
    bool add_wq(const PACKET& packet);
    bool add_pq(const PACKET& packet);
    bool add_ptwq(const PACKET& packet);

    virtual bool is_ready(const PACKET& pkt) const;

    bool rq_has_ready() const;
    bool wq_has_ready() const;
    bool pq_has_ready() const;
    bool ptwq_has_ready() const;

    void begin_phase() override;
    void end_phase(unsigned cpu) override;

		void test() { std::cout << "Testing..." << std::endl; sim_stats.back().RQ_ACCESS++; }

  private:
    void check_collision();
  
  };

  struct TranslatingQueues : public NonTranslatingQueues, public MemoryRequestProducer {
    void operate() override final;

    void issue_translation();
    void detect_misses();

    template <typename R>
    void do_issue_translation(R& queue);

    template <typename R>
    void do_detect_misses(R& queue);

    virtual bool is_ready(const PACKET& pkt) const override final;

    void return_data(const PACKET& packet) override final;

    using NonTranslatingQueues::NonTranslatingQueues;
  };

  uint32_t cpu = 0;
  const std::string NAME;
  const uint32_t NUM_SET, NUM_WAY, MSHR_SIZE;
  const uint32_t FILL_LATENCY;
  const unsigned OFFSET_BITS;
  set_type block{NUM_SET * NUM_WAY};
  const long int MAX_TAG, MAX_FILL;
  const bool prefetch_as_load;
  const bool match_offset_bits;
  const bool virtual_prefetch;
  bool ever_seen_data = false;
  const unsigned pref_activate_mask = (1 << static_cast<int>(LOAD)) | (1 << static_cast<int>(PREFETCH));

  using stats_type = cache_stats;

  std::vector<stats_type> sim_stats{}, roi_stats{};

#if defined ENABLE_EXTRA_CACHE_STATS
	ReuseDistanceMonitor* reuseDistMon;
	PageAddressStatsHanlder* pageAddressStatsMon;
  bool cache_is_full = false;
#endif

  NonTranslatingQueues& queues;
  std::deque<PACKET> MSHR;
  std::deque<PACKET> inflight_writes;

#if defined VICTIM_CACHE
	//NonTranslatingQueues *victim_cache_queues; 
	CACHE *victim_cache;
	bool enable_victim_cache = false;
  bool enable_translation_cache = false;
	bool enable_instr_only = false;
  bool enable_doa_filtering = false;
  std::vector<uint64_t> last_pte_entry;  // one entry per set
#endif

  // functions
  bool add_rq(const PACKET& packet) override final;
  bool add_wq(const PACKET& packet) override final;
  bool add_pq(const PACKET& packet) override final;
  bool add_ptwq(const PACKET& packet) override final;

  void return_data(const PACKET& packet) override final;
  void operate() override final;

  void initialize() override final;
  void begin_phase() override final;
  void end_phase(unsigned cpu) override final;

  std::size_t get_occupancy(uint8_t queue_type, uint64_t address) override final;
  std::size_t get_size(uint8_t queue_type, uint64_t address) override final;
#if defined SPLIT_STLB
  [[deprecated("Use get_set_index() instead.")]] uint64_t get_set(uint64_t address, uint8_t type) const;
  [[deprecated("This function should not be used to access the blocks directly.")]] uint64_t get_way(uint64_t address, uint8_t type, uint64_t set) const;
  uint64_t invalidate_entry(uint64_t inval_addr, uint8_t type);
#else
  [[deprecated("Use get_set_index() instead.")]] uint64_t get_set(uint64_t address) const;
  [[deprecated("This function should not be used to access the blocks directly.")]] uint64_t get_way(uint64_t address, uint64_t set) const;
  uint64_t invalidate_entry(uint64_t inval_addr);
#endif

  int prefetch_line(uint64_t pf_addr, bool fill_this_level, uint32_t prefetch_metadata);

  [[deprecated("Use CACHE::prefetch_line(pf_addr, fill_this_level, prefetch_metadata) instead.")]] int
  prefetch_line(uint64_t ip, uint64_t base_addr, uint64_t pf_addr, bool fill_this_level, uint32_t prefetch_metadata);

  bool should_activate_prefetcher(const PACKET& pkt) const;

  void print_deadlock() override;

#include "cache_modules.inc"

  const std::bitset<NUM_REPLACEMENT_MODULES> repl_type;
  const std::bitset<NUM_PREFETCH_MODULES> pref_type;

#if defined FORCE_HIT || defined MULTIPLE_PAGE_SIZE
	std::map<uint64_t, BLOCK> cached_PTEs;
	bool force_hit = false; 
	bool force_mon = false;
	VirtualMemory	*vmem;
#endif

// constructor
#if defined FORCE_HIT || defined FORCE_PTE_HIT || defined MULTIPLE_PAGE_SIZE
  CACHE(std::string v1, double freq_scale, uint32_t v2, uint32_t v3, uint32_t v8, 
				uint32_t fill_lat, long int max_tag, long int max_fill, unsigned offset_bits, 
        bool pref_load, bool wq_full_addr, bool va_pref, unsigned pref_mask, 
				NonTranslatingQueues& queue_set, MemoryRequestConsumer* ll,
        std::bitset<NUM_PREFETCH_MODULES> pref, std::bitset<NUM_REPLACEMENT_MODULES> repl,
			  bool _force_hit, bool _force_mon, VirtualMemory* _vmem
				)
      : champsim::operable(freq_scale), MemoryRequestProducer(ll), NAME(v1), NUM_SET(v2), NUM_WAY(v3), 
				MSHR_SIZE(v8), FILL_LATENCY(fill_lat), OFFSET_BITS(offset_bits), MAX_TAG(max_tag), 
				MAX_FILL(max_fill), prefetch_as_load(pref_load), match_offset_bits(wq_full_addr), 
				virtual_prefetch(va_pref), pref_activate_mask(pref_mask), queues(queue_set), repl_type(repl), 
				pref_type(pref), force_hit(_force_hit), force_mon(_force_mon), vmem(_vmem)
#else
  CACHE(std::string v1, double freq_scale, uint32_t v2, uint32_t v3, uint32_t v8, uint32_t fill_lat, long int max_tag, long int max_fill, unsigned offset_bits,
        bool pref_load, bool wq_full_addr, bool va_pref, unsigned pref_mask, NonTranslatingQueues& queue_set, MemoryRequestConsumer* ll,
        std::bitset<NUM_PREFETCH_MODULES> pref, std::bitset<NUM_REPLACEMENT_MODULES> repl)
      : champsim::operable(freq_scale), MemoryRequestProducer(ll), NAME(v1), NUM_SET(v2), NUM_WAY(v3), MSHR_SIZE(v8), FILL_LATENCY(fill_lat),
        OFFSET_BITS(offset_bits), MAX_TAG(max_tag), MAX_FILL(max_fill), prefetch_as_load(pref_load), match_offset_bits(wq_full_addr), virtual_prefetch(va_pref),
        pref_activate_mask(pref_mask), queues(queue_set), repl_type(repl), pref_type(pref)
#endif
  {
#if defined FORCE_HIT 
		if (force_hit) {
			if (NAME.find("STLB") != std::string::npos) {
				std::cout << "Using perfect instruction " << NAME << "." << std::endl;
			}	else if (NAME.find("L1D") != std::string::npos) {
				std::cout << "Using secret unlimited cache for data PTEs in " << NAME << "." << std::endl;
			} else {
				std::cout << "Force hit not supported for " << NAME << "!" << std::endl;
				assert(false);
			}
		}
#endif 

#if defined VICTIM_CACHE

		if (NAME.find("L1D") != std::string::npos 
				&& NAME.find("_VC") == std::string::npos) {

      char* victim_cache_flag = getenv("ENABLE_VICTIM_CACHE");
			if (strcmp(victim_cache_flag, "true") == 0) {
				enable_victim_cache = true;
			}

      char*  translation_cache_flag = getenv("ENABLE_TRANSLATION_CACHE");
			if (strcmp(translation_cache_flag, "true") == 0) {
				enable_translation_cache = true;
			}

      //assert(!enable_victim_cache || !enable_translation_cache);
      //assert((enable_victim_cache != enable_translation_cache) || (!enable_victim_cache && !enable_translation_cache));
      //assert((enable_translation_cache && !enable_doa_filtering) || !enable_translation_cache); // This does not work at the moment so check before proceeding

			if (enable_victim_cache || enable_translation_cache) {

			
				//FIXME: Not sure we should use braces for constructor - but maybe we need to (???)
				// Create and connect a new victim cache between L1D and L2C
				uint32_t num_set = 64;
				uint32_t num_way = 8;
				uint32_t mshr_size = 8; //64;
				NonTranslatingQueues* victim_cache_queues = new NonTranslatingQueues(1.0, num_set, num_way, mshr_size, 5, 4, champsim::lg2(64), 0);
				// Only first level caches should enable match_offset_bits
/*
				victim_cache = new CACHE(NAME+"_VC", 1.0, 64, 12, 16, 1, 2, 2, champsim::lg2(64), 0, 0, 0, 
																	(1 << LOAD) | (1 << PREFETCH), *l1dv_queues, ll, 
																	pref_type, repl_type, 0, 0, vmem);
*/
				uint32_t vc_num_set = 64;
				uint32_t vc_num_way = 8;
				uint32_t vc_latency = 1;
				uint32_t vc_mshr_size = 8; //64;

				if (getenv("VC_LATENCY")) {
					vc_latency = std::stoull(getenv("VC_LATENCY"));
				} else {
					std::cerr << "VC_LATENCY not set!" << std::endl;
					exit(0);
				}

				if (getenv("VC_NUM_SET")) {
					vc_num_set = std::stoull(getenv("VC_NUM_SET"));
				} else {
					std::cerr << "VC_NUM_SET not set!" << std::endl;
					exit(0);
				}

				if (getenv("VC_NUM_WAY")) {
					vc_num_way = std::stoull(getenv("VC_NUM_WAY"));
				} else {
					std::cerr << "VC_NUM_WAY not set!" << std::endl;
					exit(0);
				}

				if (getenv("VC_INSTR_ONLY")) {
					char* instr_only_flag = getenv("VC_INSTR_ONLY");
					if (strcmp(instr_only_flag, "true") == 0) {
						enable_instr_only = true;
					}
				}

				if (getenv("VC_DOA_FILTERING")) {
					char* doa_filtering_flag = getenv("VC_DOA_FILTERING");
					if (strcmp(doa_filtering_flag, "true") == 0) {
						enable_doa_filtering = true;
            last_pte_entry.reserve(vc_num_set);
					}
				}

				std::cout << NAME << ": Using PTE " << (enable_victim_cache?"victim":"translation")  << " cache." << std::endl;
				std::cout << "\t\tLATENCY: " << vc_latency << std::endl;
				std::cout << "\t\tSETS: " << vc_num_set << std::endl;
				std::cout << "\t\tWAYS: " << vc_num_way << std::endl;
				if (enable_instr_only) 
					std::cout << "\t\tAllowing only instuction PTEs." << std::endl;
				else 
					std::cout << "\t\tAllowing both instuction and data PTEs." << std::endl;
        
        std::cout << "\t\tDOA filtering: " << (enable_doa_filtering?"enabled":"disabled") << std::endl;

				victim_cache = new CACHE(NAME+"_VC", 1.0, vc_num_set, vc_num_way, vc_mshr_size, vc_latency, 2, 2, champsim::lg2(64), 0, 0, 0, 
																	(1 << LOAD) | (1 << PREFETCH), *victim_cache_queues, ll, 
																	CACHE::pprefetcherDno, CACHE::rreplacementDlfu, 0, 0, vmem);
			}
		}
#endif

#if defined ENABLE_EXTRA_CACHE_STATS
		if (NAME.find("STLB") != std::string::npos) {
			std::string page_address_stats_file_prefix = getenv("PAGE_ADDRESS_STATS_FILENAME_PREFIX");

			pageAddressStatsMon = new PageAddressStatsHanlder(OFFSET_BITS,
																								page_address_stats_file_prefix,
																								false);
		}	else {

			pageAddressStatsMon = new PageAddressStatsHanlder(OFFSET_BITS, "", false);
		}

		std::string reuse_dist_filename_prefix = getenv("REUSE_DIST_FILENAME_PREFIX");

		bool enable_reuseDistMon = false;
		if (NAME.find("STLB") != std::string::npos) {
			enable_reuseDistMon = false;
		} else if (NAME.find("L1D") != std::string::npos) {
			enable_reuseDistMon = true;
			if (NAME.find("VC") != std::string::npos) {
				std::cout << NAME << " enabled reuse distance monitor." << std::endl;
				enable_reuseDistMon = true;
			}
		} else if ((NAME.find("L2C") != std::string::npos)) {
			enable_reuseDistMon = false;
		} else if ((NAME.compare("LLC") == 0)) {
			enable_reuseDistMon = false;	
		}

		reuseDistMon = new ReuseDistanceMonitor(NUM_SET, NUM_WAY, OFFSET_BITS,
																						reuse_dist_filename_prefix + "_" + NAME + ".csv",
																						false, enable_reuseDistMon);
#endif
  }

#if defined ENABLE_EXTRA_CACHE_STATS
  void hit_hook();
  void miss_hook();
#endif

	//~CACHE() { std::cout << "***** CACHE DESTROYER *****" << std::endl; };
};

#endif
