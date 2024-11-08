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

#include "champsim.h"
#include "champsim_constants.h"
#include "memory_class.h"
#include "operable.h"

#if defined FORCE_HIT || defined FORCE_PTE_HIT || defined MULTIPLE_PAGE_SIZE
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
#endif

#if defined(ENABLE_PAGE_CROSSING_STATS)
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

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT
		bool is_instr = false;
		bool is_pte = false;
#endif

#if defined(MULTIPLE_PAGE_SIZE) 
		uint32_t page_size = 0;
		uint64_t base_vpn = 0;
#endif

#if defined(ENABLE_PAGE_CROSSING_STATS)
		uint64_t page_crossing = 0; 
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

#if defined (SPLIT_STLB)
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
//		ReuseDistanceCalculator* reuseDist;
			PageAddressStatsHanlder* pageAddressStatsMon;
			RecallDistanceMonitor* recallDistMon;
#endif

  NonTranslatingQueues& queues;
  std::deque<PACKET> MSHR;
  std::deque<PACKET> inflight_writes;

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
#if defined (SPLIT_STLB)
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

#if defined FORCE_HIT || defined FORCE_PTE_HIT || defined MULTIPLE_PAGE_SIZE
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

#if defined ENABLE_EXTRA_CACHE_STATS
		if (NAME.find("STLB") != std::string::npos) {
			std::string page_address_stats_file_prefix = getenv("PAGE_ADDRESS_STATS_FILENAME_PREFIX");

			pageAddressStatsMon = new PageAddressStatsHanlder(OFFSET_BITS,
																								page_address_stats_file_prefix,
																								false);
		}	else {

			pageAddressStatsMon = new PageAddressStatsHanlder(OFFSET_BITS, "", false);
		}

		std::string recall_dist_filename_prefix = getenv("RECALL_DIST_FILENAME_PREFIX");

		bool enable_recallDistMon = false;
		if (NAME.find("STLB") != std::string::npos) {
			enable_recallDistMon = false;
		} else if ((NAME.find("L1D") != std::string::npos)) {
			enable_recallDistMon = false;
		} else if ((NAME.find("L2C") != std::string::npos)) {
			enable_recallDistMon = false;
		} else if ((NAME.compare("LLC") == 0)) {
			enable_recallDistMon = false;	
		}

		recallDistMon = new RecallDistanceMonitor(NUM_SET, NUM_WAY, OFFSET_BITS,
																							recall_dist_filename_prefix + "_" + NAME + ".csv",
																							true, enable_recallDistMon);

#endif
  }

	//~CACHE() { std::cout << "***** CACHE DESTROYER *****" << std::endl; };
};

#endif
