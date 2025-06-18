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

#if defined FORCE_HIT || defined MULTIPLE_PAGE_SIZE || defined TRANSLATION_EXCLUSIVE_CACHE
#include "vmem.h"
#endif

#if defined ENABLE_EXTRA_CACHE_STATS
#include "reuse_dist.h"
#include "page_address_stats.h"
#endif

#if defined PTP_REPLACEMENT_POLICY
#include <cmath>
#endif

#if defined TRANSLATION_EXCLUSIVE_CACHE
#include "doa_predictor.h"
#include "victim_cache.h"
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

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined TRANSLATION_EXCLUSIVE_CACHE
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

#if defined TRANSLATION_EXCLUSIVE_CACHE
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

#if defined TRANSLATION_EXCLUSIVE_CACHE
	CACHE *tx_cache;
	bool enable_tx_victim_cache = false;
  bool enable_tx_cache = false;
	bool enable_instr_only = false;
  bool enable_data_only = false;
  bool enable_doa_filtering = false;
  std::vector<uint64_t> last_pte_entry;  // one entry per set
  //std::map<uint64_t, BLOCK> tx_victim_cache;

  //TODO: Cannot move to victim_cache.h because it uses BLOCK
  class VICTIM_CACHE 
  {
    private:
      uint64_t num_set, num_way, offset_bits;
      std::vector<BLOCK>  blocks;
      ReplacementPolicy* replacementPol;

#if defined ENABLE_EXTRA_CACHE_STATS
      ReuseDistanceMonitor* reuseDistMon;
#endif

      DOAPredictor* dbPred;

      uint32_t get_set(uint64_t address) 
      {
        return (address >> offset_bits) & champsim::bitmask(champsim::lg2(num_set));
      }
    
    public:
      VICTIM_CACHE(uint64_t _num_set, uint64_t _num_way, uint64_t _offset_bits)
        : num_set(_num_set), num_way(_num_way), offset_bits(_offset_bits), blocks(_num_set * _num_way) 
      {
        std::cout << "TXVC initialized with " << num_set << " sets and " << num_way << " ways." << std::endl;
				if (getenv("TXVC_REP_POLICY") != nullptr) {
					char* rep_pol_name = getenv("TXVC_REP_POLICY");
					if (strcmp(rep_pol_name, "lru") == 0) {
            std::cout << "\tUsing LRU replacement policy for TXVC" << std::endl;
					  replacementPol = new LRU(num_set, num_way);
					} else if (strcmp(rep_pol_name, "lfu") == 0) {
            std::cout << "\tUsing LFU replacement policy for TXVC" << std::endl;
            replacementPol = new LFU(num_set, num_way);
          } else {
            std::cerr << "Unknown replacement policy for TXVC: " << rep_pol_name << std::endl;
            exit(1);
          }
				} else {
          std::cerr << "TXVC_REP_POLICY not set!" << std::endl;
          exit(1);
        }

        // TODO: parametrize
        
				uint32_t dbpred_cntr_sz = 0;
        if (getenv("TXC_DBPRED_CNTR_SZ")) {
					dbpred_cntr_sz = std::stoull(getenv("TXC_DBPRED_CNTR_SZ"));
				} else {
					std::cerr << "TXC_BPRED_CNTR_SZ not set!" << std::endl;
					exit(0);
				}
        
				uint32_t dbpred_thrhld = 0;
        if (getenv("TXC_DBPRED_THRESHOLD")) {
					dbpred_thrhld = std::stoull(getenv("TXC_DBPRED_THRESHOLD"));
				} else {
					std::cerr << "TXC_DBPRED_THRESHOLD not set!" << std::endl;
					exit(0);
				}

        dbPred = new DOAPredictor(num_set, num_way, dbpred_cntr_sz, dbpred_thrhld, true);

#if defined ENABLE_EXTRA_CACHE_STATS        
        std::string reuse_dist_filename_prefix = getenv("REUSE_DIST_FILENAME_PREFIX");
	    
        reuseDistMon = new ReuseDistanceMonitor(num_set, num_way, offset_bits,
																						reuse_dist_filename_prefix + "_" + "TXVC" + ".csv",
																						true, true);
#endif
      }


      ~VICTIM_CACHE() 
      {
        delete replacementPol;
        delete dbPred;
      }


      void add_request(PACKET& request, uint64_t curr_cycle) 
      {
        uint64_t set_idx = get_set(request.address);
        auto set_begin = std::next(blocks.begin(), set_idx * num_way);
        auto set_end = std::next(set_begin, num_way);
        auto way = std::find_if(set_begin, set_end, [](const BLOCK& block) { return !block.valid; });

        if (way != set_end) {
          way->valid = true;
        } else {
          uint32_t way_idx = replacementPol->find_victim(set_idx);
          way = std::next(blocks.begin(), (set_idx * num_way) + way_idx);
          replacementPol->update_replacement_state(set_idx, way_idx, curr_cycle, false);  
        }

        dbPred->update(way->address, way->is_doa); // update with the victims info

        way->prefetch = request.prefetch_from_this;
        way->dirty = (request.type == WRITE);
        way->address = request.address;
        way->v_address = request.v_address;
        way->data = request.data;

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined TRANSLATION_EXCLUSIVE_CACHE
				way->is_instr = request.is_instr;
				way->is_pte = request.is_pte;
#endif

#if defined MULTIPLE_PAGE_SIZE
				way->page_size = request.page_size;
				way->base_vpn = request.base_vpn;
#endif

        way->is_doa = true;
//#if defined ENABLE_EXTRA_CACHE_STATS
//        reuseDistMon->add_access(request.address);
//#endif

      }


      std::pair<BLOCK, bool> lookup(uint64_t address, uint64_t curr_cycle) 
      {
        uint32_t set_idx = get_set(address);
        auto set_begin = std::next(blocks.begin(), set_idx * num_way);
        auto set_end = std::next(set_begin, num_way);
        auto way = std::find_if(set_begin, set_end, eq_addr<BLOCK>(address, offset_bits));
        uint32_t way_idx = std::distance(set_begin, way);
				const auto hit = (way != set_end);

#if defined ENABLE_EXTRA_CACHE_STATS
        reuseDistMon->add_access(address);
#endif
        
        //dbPred->update(address, hit);

        if (hit) {
          way->is_doa = false;
          replacementPol->update_replacement_state(set_idx, way_idx, curr_cycle,  hit);
          return {blocks.at((set_idx * num_way) + way_idx), hit};
        } else {
          return {blocks.at(0), hit};
        }
      }

      bool predictDOA(uint64_t address, bool seems_dead) 
      {
        //uint32_t bias = 0;
        //if (seems_dead) {
        //  bias = 4; 
        //}

        return dbPred->predict(address, seems_dead);
      }

      void print_stats(void) 
      {
#if defined ENABLE_EXTRA_CACHE_STATS
        reuseDistMon->dump();
        delete reuseDistMon;
#endif

        dbPred->print_stats();
      }

  };

  VICTIM_CACHE* tx_victim_cache;
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

#if defined TRANSLATION_EXCLUSIVE_CACHE

		if (NAME.find("L1D") != std::string::npos 
				&& NAME.find("_TXC") == std::string::npos) {

      char* victim_cache_flag = getenv("ENABLE_TXVC");
			if (strcmp(victim_cache_flag, "true") == 0) {
				enable_tx_victim_cache = true;
			}

/*
      char*  TRANSLATION_EXCLUSIVE_CACHE_flag = getenv("ENABLE_TXC");
			if (strcmp(TRANSLATION_EXCLUSIVE_CACHE_flag, "true") == 0) {
				enable_tx_cache = true;
			}
*/

			if (enable_tx_victim_cache || enable_tx_cache) {

				//FIXME: Not sure we should use braces for constructor - but maybe we need to (???)
				// Create and connect a new victim cache between L1D and L2C
				//uint32_t num_set = 64;
				//uint32_t num_way = 8;
				//uint32_t mshr_size = 8; //64;
				//NonTranslatingQueues* tx_cache_queues = new NonTranslatingQueues(1.0, num_set, num_way, mshr_size, 5, 4, champsim::lg2(64), 0);

				uint32_t txc_num_set = 64;
				uint32_t txc_num_way = 8;
				uint32_t txc_latency = 1;
				//uint32_t txc_mshr_size = 8; //64;

				if (getenv("TXC_LATENCY")) {
					txc_latency = std::stoull(getenv("TXC_LATENCY"));
				} else {
					std::cerr << "TXC_LATENCY not set!" << std::endl;
					exit(0);
				}

				if (getenv("TXC_NUM_SET")) {
					txc_num_set = std::stoull(getenv("TXC_NUM_SET"));
				} else {
					std::cerr << "TXC_NUM_SET not set!" << std::endl;
					exit(0);
				}

				if (getenv("TXC_NUM_WAY")) {
					txc_num_way = std::stoull(getenv("TXC_NUM_WAY"));
				} else {
					std::cerr << "TXC_NUM_WAY not set!" << std::endl;
					exit(0);
				}

				if (getenv("TXC_INSTR_ONLY")) {
					char* instr_only_flag = getenv("TXC_INSTR_ONLY");
					if (strcmp(instr_only_flag, "true") == 0) {
						enable_instr_only = true;
					}
				}

				if (getenv("TXC_DATA_ONLY")) {
					char* data_only_flag = getenv("TXC_DATA_ONLY");
					if (strcmp(data_only_flag, "true") == 0) {
						enable_data_only = true;
					}
				}

				if (getenv("TXC_DOA_FILTERING")) {
					char* doa_filtering_flag = getenv("TXC_DOA_FILTERING");
					if (strcmp(doa_filtering_flag, "true") == 0) {
						enable_doa_filtering = true;
            last_pte_entry.reserve(NUM_SET);
					}
				}

				std::cout << NAME << ": Using PTE " << (enable_tx_victim_cache?"victim":"exclusive")  << " cache." << std::endl;
				std::cout << "\t\tLATENCY: " << txc_latency << std::endl;
				std::cout << "\t\tSETS: " << txc_num_set << std::endl;
				std::cout << "\t\tWAYS: " << txc_num_way << std::endl;
				if (enable_instr_only) 
					std::cout << "\t\tAllowing only instuction PTEs." << std::endl;
        else if (enable_data_only)
          std::cout << "\t\tAllowing only data PTEs." << std::endl;
				else 
					std::cout << "\t\tAllowing both instuction and data PTEs." << std::endl;
        
        std::cout << "\t\tDOA filtering: " << (enable_doa_filtering?"enabled":"disabled") << std::endl;

				//tx_cache = new CACHE( NAME+"_TXC", 1.0, txc_num_set, txc_num_way, txc_mshr_size, txc_latency, 2, 2, champsim::lg2(64), 0, 0, 0, 
				//											(1 << LOAD) | (1 << PREFETCH), *tx_cache_queues, ll, 
				//											CACHE::pprefetcherDno, CACHE::rreplacementDlfu, 0, 0, vmem);

        tx_victim_cache = new VICTIM_CACHE(txc_num_set, txc_num_way, champsim::lg2(64));
        
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
			if (NAME.find("TXC") != std::string::npos) {
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
