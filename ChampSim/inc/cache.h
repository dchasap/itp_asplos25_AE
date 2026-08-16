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

#include <algorithm>
#include <array>
#include <bitset>
#include <unordered_map>
#include <cassert>
#include <deque>
#include <functional>
#include <limits>
#include <list>
#include <string>
#include <vector>
#include <string.h>
#include <iomanip>

#include "champsim.h"
#include "champsim_constants.h"
#include "memory_class.h"
#include "operable.h"
#include "memory_trace.h"
#include <sstream>

#if defined FORCE_HIT || defined MULTIPLE_PAGE_SIZE || defined TRANSLATION_EXCLUSIVE_CACHE
#include "vmem.h"
#endif

#if defined ENABLE_EXTRA_CACHE_STATS
#include "reuse_dist.h"
#include "page_address_stats.h"
#include "address_access_stats.h"
#endif

#if defined PTP_REPLACEMENT_POLICY
#include <cmath>
#endif

#if defined TRANSLATION_EXCLUSIVE_CACHE
#include "cache_filter.h"
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
  // PTE level tracking (levels 0-4)
  std::array<uint64_t, 5> pte_level_accesses = {};
  std::array<uint64_t, 5> pte_level_hits = {};
  std::array<uint64_t, 5> pte_level_misses = {};
#endif

#if defined ENABLE_PAGE_CROSSING_STATS
	uint64_t pf_crossing_pages_tlb_hit = 0;
	uint64_t pf_crossing_pages_tlb_miss = 0;
#endif  

  uint64_t total_miss_latency = 0;
};

// Public tag for VC-targeted prefetches. Prefetchers can set
// PACKET::pf_prefetch_tag to this value to mark fills for the VC.
inline constexpr uint32_t VC_PTE_PREFETCH_METADATA = 0x54585643; // 'TXVC' (kept value for compatibility)
// Public tag for Prefetch-Buffer-targeted prefetches.
inline constexpr uint32_t PB_PTE_PREFETCH_METADATA = 0x50504246; // 'PBUF'

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

    uint64_t pf_metadata = 0;
    uint32_t pf_prefetch_tag = 0;
    CACHE* pf_origin_cache = nullptr;

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined TRANSLATION_EXCLUSIVE_CACHE
		bool is_instr = false;
		bool is_pte = false;
    uint8_t pte_level = 0;
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
    uint64_t access_freq = 0;
  uint64_t txvc_insert_cycle = 0;
  bool txvc_hit_by_demand = false;
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
#if defined TRANSLATION_EXCLUSIVE_CACHE
    uint64_t access_freq = 0;
#endif
	};
#endif

#if defined SPLIT_STLB
  std::pair<set_type::iterator, set_type::iterator> get_set_span(uint64_t address, uint8_t type);
 	std::pair<set_type::const_iterator, set_type::const_iterator> get_set_span(uint64_t address, uint8_t type) const;
  std::size_t get_set_index(uint64_t address, uint8_t type) const;
#elif defined TX_SPLIT_CACHE
  std::pair<set_type::iterator, set_type::iterator> get_set_span(uint64_t address, uint8_t type);
 	std::pair<set_type::const_iterator, set_type::const_iterator> get_set_span(uint64_t address, uint8_t type) const;
  std::size_t get_set_index(uint64_t address, uint8_t type) const;
  std::size_t _get_set_index(uint64_t address, uint32_t num_set) const;
#else 
  std::pair<set_type::iterator, set_type::iterator> get_set_span(uint64_t address);
 	std::pair<set_type::const_iterator, set_type::const_iterator> get_set_span(uint64_t address) const;
  std::size_t get_set_index(uint64_t address) const;
  std::size_t _get_set_index(uint64_t address, uint32_t num_set) const;
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
  bool prefetch_use_full_address = false; // when true, pass unmasked full PTE addr for TRANSLATION
  bool ever_seen_data = false;
  const unsigned pref_activate_mask = (1 << static_cast<int>(LOAD)) | (1 << static_cast<int>(PREFETCH));

  using stats_type = cache_stats;

  std::vector<stats_type> sim_stats{}, roi_stats{};

#if defined ENABLE_EXTRA_CACHE_STATS
	ReuseDistanceMonitor* reuseDistMon;
	PageAddressStatsHanlder* pageAddressStatsMon;
  AddressAccessStatsHanlder* addressAccessStatsMon;
  bool cache_is_full = false;
#endif

#if defined TX_SPLIT_CACHE
  uint32_t TX_NUM_SET;
  bool enable_tx_split_cache;
#endif 

#if defined TX_SPLIT_CACHE
   __uint128_t barret_reciprocal;
   __uint128_t tx_barret_reciprocal;
#else 
   __uint128_t barret_reciprocal; 
#endif

  NonTranslatingQueues& queues;
  std::deque<PACKET> MSHR;
  std::deque<PACKET> inflight_writes;

  //TODO: THIS IS TEMP REMOVE AFTER DEBUGGING
  std::vector<uint64_t> touched_indices;


  void check_touched_indices() {
    
    std::string set_access_filename_prefix = champsim::EnvVar<std::string>::get_or("SET_ACCESS_FILENAME_PREFIX", std::string(""));
    std::ofstream dumpfile = std::ofstream(set_access_filename_prefix + "_" + NAME + ".csv", std::ios::out);
    std::cout << "Saving set accesses to " << set_access_filename_prefix << "_" << NAME << ".csv" << std::endl;
    
    std::cout << NAME + ": Checking that all sets were used." << std::endl;
    
    dumpfile << "set,accesses" << std::endl;

    uint64_t num_sets_untouched = 0;
    std::cout << "Sets map size:" << touched_indices.size() << std::endl;
    for (uint64_t i = 0; i < NUM_SET; i++) {
      uint64_t accesses = touched_indices[i];
      dumpfile << i << "," << accesses << std::endl;
      if(accesses == 0) {
        num_sets_untouched++;
        std::cout << "Set " << i << " was not touched." << std::endl;
      }
    }

    dumpfile.close();
    std::cout << "Done for " << NAME << " with " << num_sets_untouched << " sets not touched." << std::endl;
  }

#if defined TRANSLATION_EXCLUSIVE_CACHE
  std::string _CACHE_;
	CACHE *tx_cache;
	bool enable_tx_victim_cache = false;
  bool enable_tx_cache = false;
	bool enable_instr_only = false;
  bool enable_data_only = false;
  std::vector<uint64_t> last_pte_entry;  // one entry per set
  //std::map<uint64_t, BLOCK> tx_victim_cache;

  //TODO: Cannot move to victim_cache.h because it uses BLOCK
  class VICTIM_CACHE 
  {
    private:
      uint64_t num_set, num_way, offset_bits;
      //std::queue<PACKET> rd_queue;
      std::vector<BLOCK>  blocks;
      PrefetchPolicy* prefetchPolicy = nullptr;
      ReplacementPolicy* replacementPol;
      std::string _name_;

      bool enable_cache_filtering = false;

      //stats
      uint64_t total_accesses = 0, total_itaccesses = 0, total_dtaccesses = 0;
      uint64_t total_hits = 0, total_ithits = 0, total_dthits = 0;
      uint64_t total_misses = 0, total_itmisses = 0, total_dtmisses = 0;
      uint64_t pf_requested = 0, pf_issued = 0, pf_fill = 0, pf_useful = 0, pf_useless = 0;
      uint64_t pf_cache_lines_inserted = 0;
      uint64_t pf_cache_lines_first_use = 0;
      uint64_t pf_cache_lines_evicted_without_use = 0;
      uint64_t pf_cache_lines_evicted_after_use = 0;
      uint64_t pf_cache_first_use_latency_sum = 0;
      uint64_t pf_cache_residency_cycles_sum = 0;
      uint64_t pf_cache_residency_cycles_evicted_after_use_sum = 0;
      bool roi_phase_started = false;

      bool save_mem_accesses;
      MemoryTracer memTracer;

#if defined ENABLE_EXTRA_CACHE_STATS
      ReuseDistanceMonitor* reuseDistMon;
#endif

      CacheFilter* cacheFilter;

      IndexHash* setIndexer;

      /*
      uint32_t get_set(uint64_t address) 
      {
        return (address >> offset_bits) & champsim::bitmask(champsim::lg2(num_set));
      }
      */
    
    public:
      VICTIM_CACHE(uint64_t _num_set, uint64_t _num_way, uint64_t _offset_bits, std::string _name)
        : num_set(_num_set), num_way(_num_way), offset_bits(_offset_bits), blocks(_num_set * _num_way), _name_(_name) 
      {

        std::cout << "TXVC initialized with " << num_set << " sets and " << num_way << " ways." << std::endl;

        if (auto v = champsim::EnvVar<std::string>::get("TXVC_SET_INDEXER")) {
            std::string set_indexer_name = *v;
            if (set_indexer_name == "default") {
              std::cout << "\tUsing Default hash as set indexer for TXVC" << std::endl;
              setIndexer = new DefaultHash(num_set, num_way, offset_bits);
            } else if (set_indexer_name == "modulo") {
              std::cout << "\tUsing Modulo hash as set indexer for TXVC" << std::endl;
              setIndexer = new ModuloHash(num_set, num_way, offset_bits);
            } else if (set_indexer_name == "xor") {
              std::cout << "\tUsing XOR hash as set indexer for TXVC" << std::endl;
              setIndexer = new XORHash(num_set, num_way);
            } else if (set_indexer_name == "knuth") {
              std::cout << "\tUsing Multiplicative-Knuth hash as set indexer for TXVC" << std::endl;
              setIndexer = new MultiplicativeHash(num_set, num_way);
            } else {
              std::cerr << "Unknown hash indexer for TXVC: " << set_indexer_name << std::endl;
              exit(1);
            }
          } else {
            std::cerr << "TXVC_SET_INDEXER not set!" << std::endl;
            exit(1);
          }

        if (auto v = champsim::EnvVar<std::string>::get("TXVC_REP_POLICY")) {
            std::string rep_pol_name = *v;
            if (rep_pol_name == "lru") {
              std::cout << "\tUsing LRU replacement policy for TXVC" << std::endl;
              replacementPol = new LRU(num_set, num_way);
            } else if (rep_pol_name == "lfu") {
              std::cout << "\tUsing LFU replacement policy for TXVC" << std::endl;
              replacementPol = new LFU(num_set, num_way);
            } else if (rep_pol_name == "lfu_leaf") {
              std::cout << "\tUsing LFU_Leaf replacement policy for TXVC" << std::endl;
              replacementPol = new LFU_Leaf(num_set, num_way);
            } else if (rep_pol_name == "lfupp") {
              std::cout << "\tUsing LFU++ replacement policy for TXVC" << std::endl;
              replacementPol = new LFUPP(num_set, num_way);
            } else if (rep_pol_name == "lfu_decay") {
              std::cout << "\tUsing LFU with Decay replacement policy for TXVC" << std::endl;
              replacementPol = new LFUwDecay(num_set, num_way);
            } else if (rep_pol_name == "lfu_pchot") {
              std::cout << "\tUsing LFU+PC-hotness replacement policy for TXVC" << std::endl;
              replacementPol = new LFU_PCHot(num_set, num_way);
            } else if (rep_pol_name == "lrfu") {
              std::cout << "\tUsing LRFU replacement policy for TXVC" << std::endl;
              replacementPol = new LRFU(num_set, num_way);
            } else if (rep_pol_name == "lrfu_wss") {
              std::cout << "\tUsing LRFU_WSS replacement policy for TXVC" << std::endl;
              replacementPol = new LRFU_WSS(num_set, num_way);
            } else if (rep_pol_name == "lfu_halving") {
              std::cout << "\tUsing LFU_Halving replacement policy for TXVC" << std::endl;
              replacementPol = new LFU_Halving(num_set, num_way);
            } else if (rep_pol_name == "srrip") {
              std::cout << "\tUsing SRRIP replacement policy for TXVC" << std::endl;
              replacementPol = new SRRIP(num_set, num_way, 3);
            } else if (rep_pol_name == "srrip_leaf") {
              std::cout << "\tUsing SRRIP replacement policy for TXVC" << std::endl;
              replacementPol = new SRRIP_Leaf(num_set, num_way, 3);
            } else if (rep_pol_name == "pacipv") {
              std::cout << "\tUsing PACIPV replacement policy for TXVC" << std::endl;
              replacementPol = new PACIPV(num_set, num_way, 3);
            } else {
              std::cerr << "Unknown replacement policy for TXVC: " << rep_pol_name << std::endl;
              exit(1);
            }
          } else {
            std::cerr << "TXVC_REP_POLICY not set!" << std::endl;
            exit(1);
          }

        if (auto v = champsim::EnvVar<bool>::get("TXVC_CACHE_FILTERING")) {
          if (*v) enable_cache_filtering = true;
        } else {
          std::cerr << "TXVC_CACHE_FILTERING not defined!" << std::endl;
        }

        if (enable_cache_filtering) {
          

          if (auto v = champsim::EnvVar<std::string>::get("TXVC_CACHE_FILTER")) {

				  std::string dbpred_name = *v;
            if (dbpred_name == "doa-simple") {
              std::cout << "\tTXVC: Using DOA-simpe filter" << std::endl;
					    cacheFilter = new SimpleDOAFilter();
            } else if (dbpred_name == "oracle-doa") {
              std::cout << "\tTXVC: Using Oracle DOA filter" << std::endl;
					    cacheFilter = new OracleDOAFilter(num_set, num_way, true);  
            } else if (dbpred_name == "doa") {
              std::cout << "\tTXVC: Using DOA filter" << std::endl;
					    cacheFilter = new DOAPredictor(num_set, num_way, true);
            } else if (dbpred_name == "mfu") {
              std::cout << "\tTXVC: Using MFU filter" << std::endl;
              cacheFilter = new MFUFilter(num_set, num_way, false);
            } else if (dbpred_name == "oracle-mfu") {
              std::cout << "\tTXVC: Using Oracle MFU filter" << std::endl;
              cacheFilter = new OracleMFUFilter(num_set, num_way, true); 
            } else if (dbpred_name == "trace-mem") {
              std::cout << "\tTXVC: Generating a memory trace for the cache filter" << std::endl;
              cacheFilter = new FilterTracer();   
            } else if (dbpred_name == "simple-freq-filter") {
              std::cout << "\tTXVC: Using simple freq filter" << std::endl;
					    cacheFilter = new SimpleFreqFilter();
            } else if (dbpred_name == "bloom-freq-filter") {
              std::cout << "\tTXVC: Using bloom freq filter" << std::endl;
					    cacheFilter = new BloomFreqFilter();
            } else if (dbpred_name == "freq-filter") {
              std::cout << "\tTXVC: Using freq filter" << std::endl;
              cacheFilter = new FreqFilter();
            } else if (dbpred_name == "none") {
              std::cout << "\tTXVC: Using dummy freq filter" << std::endl;
              cacheFilter = new DummyFilter();
            } else if (dbpred_name == "beladyOPT-set") {
              std::cout << "\tTXVC: Using BeladyOPT per set filter" << std::endl;
              cacheFilter = new BeladyOPTSetFilter(num_set, num_way, offset_bits);
            } else if (dbpred_name == "reuse-distance") {
              std::cout << "\tTXVC: Using reuse-distance filter" << std::endl;
              cacheFilter = new ReuseDistanceFilter(num_set, num_way, true);
            } else {
              std::cerr << "TXVC: Unknown cache filter " << dbpred_name << "!" << std::endl;
              exit(1);
            }

            //std::cout << "\tCache filtering: " << dbpred_name << std::endl;
				  
          } else {
            std::cerr << "TXVC_CACHE_FILTER not set!" << std::endl;
            exit(1);
          }

        } else {
          std::cout << "\tCache filtering disabled." << std::endl;      
        }


        if (auto v = champsim::EnvVar<std::string>::get("TXVC_MEMORY_TRACE_PATH")) {
          const std::string& _mem_trace_filename = *v;
          std::cout << "TXVC: Saving memory accesses to " << _mem_trace_filename << std::endl;
          memTracer.open_tracefile(_mem_trace_filename.c_str());
          save_mem_accesses = true;
        } else {
          std::cout << "TXVC_MEMORY_TRACE_PATH not set!" << std::endl;
          save_mem_accesses = false;
        }


#if defined ENABLE_EXTRA_CACHE_STATS        
        std::string reuse_dist_filename_prefix;
        if (auto v = champsim::EnvVar<std::string>::get("REUSE_DIST_FILENAME_PREFIX")) {
              reuse_dist_filename_prefix = *v;
          std::cout << "REUSE_DIST_FILENAME_PREFIX set to " << reuse_dist_filename_prefix << std::endl;
            } else {
              std::cout << "REUSE_DIST_FILENAME_PREFIX not set!" << std::endl;
              exit(1);
          	}
        
        reuseDistMon = new ReuseDistanceMonitor(num_set, num_way, offset_bits,
																						    reuse_dist_filename_prefix + "_" + "TXVC" + ".csv",
																						    false, true);
#endif

        if (auto pf = champsim::EnvVar<std::string>::get("TXVC_PF_POLICY")) {
          const std::string& pf_policy_name = *pf;
          if (pf_policy_name == "stride") {
            std::cout << "\tUsing stride prefetch policy for TXVC" << std::endl;
            prefetchPolicy = new StridePrefetcher(offset_bits);
          } else if (pf_policy_name == "sibling") {
            std::cout << "\tUsing sibling prefetch policy for TXVC" << std::endl;
            prefetchPolicy = new SiblingPrefetcher(offset_bits);
          } else if (pf_policy_name == "child") {
            std::cout << "\tUsing child prefetch policy for TXVC" << std::endl;
            prefetchPolicy = new ChildPrefetcher(offset_bits);
          } else if (pf_policy_name == "combined") {
            std::cout << "\tUsing combined (child+sibling+stride) prefetch policy for TXVC" << std::endl;
            prefetchPolicy = new CombinedPrefetcher(offset_bits);
          } else if (pf_policy_name == "none") {
            std::cout << "\tUsing none prefetch policy for TXVC" << std::endl;
            prefetchPolicy = new NonePrefetcher();
          } else {
            std::cerr << "Unknown prefetch policy for TXVC: " << pf_policy_name << std::endl;
            exit(1);
          }
        } else {
          // default to stride behavior when not set
          std::cout << "\tUsing stride prefetch policy for TXVC" << std::endl;
          prefetchPolicy = new StridePrefetcher(offset_bits);
        }
      }


      ~VICTIM_CACHE() 
      {
#if defined ENABLE_EXTRA_CACHE_STATS
        delete reuseDistMon;
#endif
        delete prefetchPolicy;
        delete replacementPol;
        delete cacheFilter;
      }


      void add_request(PACKET& request, uint64_t curr_cycle, bool seems_dead, uint64_t access_freq, bool skip_filter = false) 
      {

        if (enable_cache_filtering && !skip_filter) {
          //std::cout << "access_freq:" << access_freq << std::endl;
          bool bypass = cacheFilter->predict(request.address, seems_dead, access_freq);
          // also check if its a demand access 
          //bool is_demand = request.type != PREFETCH;
          bool is_demand = true; // TEMP: DISABLE BYPASS FOR PREFETCHES FOR NOW
          bypass = bypass || !is_demand;
          if (bypass) {
            //std::cout << "Block " << request.address << " bypassed." << std::endl;
            return;
          }
        }

        auto [way, found] = lookup(request.address, request.is_instr, curr_cycle, request.ip);
        if (!found) {
          fill(request, curr_cycle);
        }
      }

      void fill(PACKET& request, uint64_t curr_cycle) 
      {
        uint64_t set_idx = setIndexer->get_set(request.address);
        auto set_begin = std::next(blocks.begin(), set_idx * num_way);
        auto set_end = std::next(set_begin, num_way);
        auto way = std::find_if(set_begin, set_end, [](const BLOCK& block) { return !block.valid; });

        uint32_t way_idx;
        if (way != set_end) {
          // filling an empty slot
          way_idx = static_cast<uint32_t>(std::distance(set_begin, way));
          //std::cout << "Filling empty block in set " << set_idx << " with address " << way->address << std::endl;
          way->valid = true;
          ReplacementPolicy::REP_POL_ARGS xargs;
          // no previous frequency
          xargs.access_freq = 0;
          xargs.pte_level = request.translation_level;
          xargs.pc = request.ip;
          xargs.pte_address = request.address;
          xargs.is_prefetch = request.prefetch_from_this;
          replacementPol->update_replacement_state(set_idx, way_idx, curr_cycle, false, xargs);
        } else {
          way_idx = replacementPol->find_victim(set_idx);
          way = std::next(blocks.begin(), (set_idx * num_way) + way_idx);
          ReplacementPolicy::REP_POL_ARGS xargs;
          xargs.access_freq = way->access_freq;
          xargs.pte_level = way->pte_level;
          xargs.pc = request.ip;
          xargs.pte_address = request.address;
          xargs.is_prefetch = request.prefetch_from_this;
          replacementPol->update_replacement_state(set_idx, way_idx, curr_cycle, false, xargs);  
        }

        // Prefetched-line cache survivability at eviction time.
        if (way->valid && way->prefetch) {
          const uint64_t residency = curr_cycle - way->txvc_insert_cycle;
          pf_cache_residency_cycles_sum += residency;
          if (way->txvc_hit_by_demand) {
            pf_cache_lines_evicted_after_use++;
            pf_cache_residency_cycles_evicted_after_use_sum += residency;
          } else {
            pf_cache_lines_evicted_without_use++;
          }
        }
        
        //std::cout << "Filling block in set " << set_idx << " with address " << request.address << std::endl;

        if (enable_cache_filtering)
          cacheFilter->update(way->address, way->is_doa, false, curr_cycle); 

        way->prefetch = request.prefetch_from_this;
        way->dirty = (request.type == WRITE);
        way->address = request.address;
        way->v_address = request.v_address;
        way->data = request.data;

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined TRANSLATION_EXCLUSIVE_CACHE
				way->is_instr = request.is_instr;
				way->is_pte = request.is_pte;
        way->pte_level = request.translation_level;
        way->access_freq = request.access_freq;
#endif

#if defined MULTIPLE_PAGE_SIZE
				way->page_size = request.page_size;
				way->base_vpn = request.base_vpn;
#endif

        way->is_doa = true;

        if (request.prefetch_from_this) {
          pf_cache_lines_inserted++;
          way->txvc_insert_cycle = curr_cycle;
          way->txvc_hit_by_demand = false;
        } else {
          way->txvc_insert_cycle = 0;
          way->txvc_hit_by_demand = false;
        }
//#if defined ENABLE_EXTRA_CACHE_STATS
//        reuseDistMon->add_access(request.address);
//#endif

      }

      std::vector<uint64_t> get_prefetch_candidates(uint64_t address, std::size_t translation_level, uint64_t ip, uint64_t translated_vpn)
      {
        return prefetchPolicy->get_prefetch_candidates(address, translation_level, ip, translated_vpn);
      }

      void observe_prefetch_access(uint64_t address, std::size_t translation_level, uint64_t ip, uint64_t translated_vpn)
      {
        prefetchPolicy->observe_access(address, translation_level, ip, translated_vpn);
      }

      uint32_t get_pf_mshr_gate_pct() const
      {
        return prefetchPolicy->get_mshr_gate_pct();
      }

      void notify_pf_mshr_blocked()
      {
        prefetchPolicy->notify_mshr_gate_blocked();
      }

      void notify_pf_enqueue_failed()
      {
        prefetchPolicy->notify_enqueue_failed();
      }


      std::pair<BLOCK, bool> lookup(uint64_t address, bool is_instr, uint64_t curr_cycle, uint64_t pc, bool is_prefetch_request = false) 
      {
        uint32_t set_idx = setIndexer->get_set(address);
        auto set_begin = std::next(blocks.begin(), set_idx * num_way);
        auto set_end = std::next(set_begin, num_way);
        auto way = std::find_if(set_begin, set_end, eq_addr<BLOCK>(address, offset_bits));
        uint32_t way_idx = std::distance(set_begin, way);
				const auto hit = (way != set_end);

#if defined ENABLE_EXTRA_CACHE_STATS
        if (enable_cache_filtering) {
          bool bypass = cacheFilter->predict(address, false, 0);
          if (!bypass) {
            //std::cout << "Block " << request.address " byapassed." << std::endl;
            reuseDistMon->add_access(address);
          }
        }

#endif
        if (save_mem_accesses)
          memTracer.add_access(address, is_instr);
        
        if (enable_cache_filtering)
          cacheFilter->update(address, !hit, true, curr_cycle); // if hit, not doa

        // Categorize access using the incoming request's is_instr flag, not the cached block's
        total_accesses++;
        if (is_instr)
          total_itaccesses++;
        else
          total_dtaccesses++;

        if (hit) {
          total_hits++;
          if (is_instr)
            total_ithits++;
          else
            total_dthits++;
          way->is_doa = false;

          // First demand hit on a prefetched TXVC line: this is cache-side usefulness latency.
          if (way->prefetch && !is_prefetch_request && !way->txvc_hit_by_demand) {
            way->txvc_hit_by_demand = true;
            pf_cache_lines_first_use++;
            pf_cache_first_use_latency_sum += (curr_cycle - way->txvc_insert_cycle);
            // Attribute usefulness to originating cache/prefetcher if available
            if (way->pf_origin_cache) {
              way->pf_origin_cache->sim_stats.back().pf_useful++;
            }
          }

          ReplacementPolicy::REP_POL_ARGS xargs;
          xargs.access_freq = way->access_freq;
          xargs.pte_level = way->pte_level;
          xargs.pc = pc;
          xargs.pte_address = address;
          xargs.is_prefetch = way->prefetch;
          replacementPol->update_replacement_state(set_idx, way_idx, curr_cycle, hit, xargs);
          return {blocks.at((set_idx * num_way) + way_idx), hit};
        } else {
          total_misses++;
          if (is_instr)
            total_itmisses++;
          else 
            total_dtmisses++;
          return {blocks.at(0), hit};
        }
      }

      /*
      bool predictDOA(uint64_t address, bool seems_dead) 
      {
        //uint32_t bias = 0;
        //if (seems_dead) {
        //  bias = 4; 
        //}
        //std::cout << "Calling predictDOA(" << address << ", " << seems_dead << ")" << std::endl;
        return dbPred->predict(address, seems_dead);
      }
      */

      void print_stats(void) 
      {
        if (save_mem_accesses) {
          memTracer.save_tracefile();
        }

        std::cout << "TXVC";
        std::cout << " TOTAL       ";
        std::cout << "ACCESSES:" << std::setw(10) << total_accesses << "  ";
        std::cout << "HIT:" << std::setw(10) << total_hits << "  "; 
        std::cout << "MISS:" << std::setw(10) << total_misses << " ";
        std::cout << "itACCESSES:" << std::setw(10) << total_itaccesses << "  ";
        std::cout << "itHIT:" << std::setw(10) << total_ithits << "  "; 
        std::cout << "itMISS:" << std::setw(10) << total_itmisses << " ";
        std::cout << "dtACCESSES:" << std::setw(10) << total_dtaccesses << "  ";
        std::cout << "dtHIT:" << std::setw(10) << total_dthits << "  "; 
        std::cout << "dtMISS:" << std::setw(10) << total_dtmisses;
        std::cout << std::endl;

        std::cout << "TXVC PREFETCH   ";
        std::cout << "REQUESTED:" << std::setw(10) << pf_requested << "  ";
        std::cout << "ISSUED:" << std::setw(10) << pf_issued << "  ";
        std::cout << "FILL:" << std::setw(10) << pf_fill << "  ";
        std::cout << "USEFUL:" << std::setw(10) << pf_useful << "  ";
        std::cout << "USELESS:" << std::setw(10) << pf_useless;
        std::cout << std::endl;

        uint64_t live_prefetched = 0;
        uint64_t live_prefetched_used = 0;
        for (const auto& block : blocks) {
          if (!block.valid || !block.prefetch)
          continue;
          live_prefetched++;
          if (block.txvc_hit_by_demand)
          live_prefetched_used++;
        }

        const double pf_first_use_rate =
          (pf_cache_lines_inserted != 0) ? 100.0 * static_cast<double>(pf_cache_lines_first_use) / static_cast<double>(pf_cache_lines_inserted) : 0.0;
        const double pf_avg_first_use_latency =
          (pf_cache_lines_first_use != 0) ? static_cast<double>(pf_cache_first_use_latency_sum) / static_cast<double>(pf_cache_lines_first_use) : 0.0;
        const uint64_t pf_evicted_total = pf_cache_lines_evicted_without_use + pf_cache_lines_evicted_after_use;
        const double pf_evicted_useful_rate =
          (pf_evicted_total != 0) ? 100.0 * static_cast<double>(pf_cache_lines_evicted_after_use) / static_cast<double>(pf_evicted_total) : 0.0;
        const double pf_avg_evicted_residency =
          (pf_evicted_total != 0) ? static_cast<double>(pf_cache_residency_cycles_sum) / static_cast<double>(pf_evicted_total) : 0.0;
        const double pf_avg_useful_evicted_residency =
          (pf_cache_lines_evicted_after_use != 0)
            ? static_cast<double>(pf_cache_residency_cycles_evicted_after_use_sum) / static_cast<double>(pf_cache_lines_evicted_after_use)
            : 0.0;

        std::cout << "TXVC PREFETCH-LIFETIME ";
        std::cout << "INSERTED:" << std::setw(10) << pf_cache_lines_inserted << "  ";
        std::cout << "FIRST_USE:" << std::setw(10) << pf_cache_lines_first_use << "  ";
        std::cout << "FIRST_USE_RATE(%):" << std::setw(8) << pf_first_use_rate << "  ";
        std::cout << "AVG_FIRST_USE_LAT(cyc):" << std::setw(10) << pf_avg_first_use_latency << "  ";
        std::cout << "EVICTED_NO_USE:" << std::setw(10) << pf_cache_lines_evicted_without_use << "  ";
        std::cout << "EVICTED_AFTER_USE:" << std::setw(10) << pf_cache_lines_evicted_after_use << "  ";
        std::cout << "EVICTED_USEFUL_RATE(%):" << std::setw(8) << pf_evicted_useful_rate << "  ";
        std::cout << "AVG_EVICTED_RES(cyc):" << std::setw(10) << pf_avg_evicted_residency << "  ";
        std::cout << "AVG_USEFUL_EVICTED_RES(cyc):" << std::setw(10) << pf_avg_useful_evicted_residency << "  ";
        std::cout << "LIVE_PREF:" << std::setw(10) << live_prefetched << "  ";
        std::cout << "LIVE_PREF_USED:" << std::setw(10) << live_prefetched_used;
        std::cout << std::endl;

        prefetchPolicy->print_stats();
       
        if (enable_cache_filtering)
          cacheFilter->print_stats();

#if defined ENABLE_EXTRA_CACHE_STATS
        reuseDistMon->dump();
#endif
      }

      void record_pf_requested() { pf_requested++; }
      void record_pf_issued() { pf_issued++; }
      void record_pf_fill() { pf_fill++; }
      void record_pf_useful()  { pf_useful++;  prefetchPolicy->notify_useful();  }
      void record_pf_useless() { pf_useless++; prefetchPolicy->notify_useless(); }

      void reset_phase_stats()
      {
        total_accesses = 0;
        total_itaccesses = 0;
        total_dtaccesses = 0;
        total_hits = 0;
        total_ithits = 0;
        total_dthits = 0;
        total_misses = 0;
        total_itmisses = 0;
        total_dtmisses = 0;
        pf_requested = 0;
        pf_issued = 0;
        pf_fill = 0;
        pf_useful = 0;
        pf_useless = 0;
        pf_cache_lines_inserted = 0;
        pf_cache_lines_first_use = 0;
        pf_cache_lines_evicted_without_use = 0;
        pf_cache_lines_evicted_after_use = 0;
        pf_cache_first_use_latency_sum = 0;
        pf_cache_residency_cycles_sum = 0;
        pf_cache_residency_cycles_evicted_after_use_sum = 0;
      }

      void on_phase_begin(bool in_warmup)
      {
        if (in_warmup)
          return;

        if (!roi_phase_started) {
          reset_phase_stats();
          roi_phase_started = true;
        }
      }

  };

  VICTIM_CACHE* tx_victim_cache;
#endif

#if defined PREFETCH_BUFFER
  // -------------------------------------------------------------------
  // PREFETCH_BUFFER: unlimited map-based buffer that holds prefetched
  // lines.  Key = address >> OFFSET_BITS (cache-line granularity) so
  // there are no collisions — every distinct cache line has its own slot.
  // Enabled per cache at runtime via <cache>.enable_pf_buffer = 1
  // (e.g., l2c.enable_pf_buffer = 1, llc.enable_pf_buffer = 0).
  // -------------------------------------------------------------------
  class PrefetchBuffer {
  public:
    enum BufferMode { PREFETCH_MODE = 0, MISS_MODE = 1 };
    enum ReplacementPolicy { LRU = 0, LFU = 1 };

    struct PBEntry {
      bool     valid        = false;
      bool     ever_accessed = false; // Track if entry was ever used for accuracy
      uint64_t tag          = 0; // key tag when using set-assoc table
      uint64_t data         = 0;
      uint64_t insert_cycle = 0;
      uint32_t frequency    = 0; // access frequency for LFU replacement
      uint64_t pf_metadata  = 0;
      uint32_t pf_prefetch_tag = 0;
      CACHE* pf_origin_cache = nullptr;
      uint8_t  type         = 0;
#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined TRANSLATION_EXCLUSIVE_CACHE
      bool     is_pte       = false;
      bool     is_instr     = false;
      uint8_t  pte_level    = 0;
#endif
    };

  private:
    uint32_t offset_bits;
    BufferMode mode = PREFETCH_MODE;
    ReplacementPolicy repl_policy = LRU;
    bool fill_cache_on_hit = false;
    static constexpr uint64_t MAX_ENTRIES = 100000;  // Safeguard against unbounded growth

    // Set-associative table parameters (optional). If num_sets>0 and num_ways>0,
    // the PrefetchBuffer will operate as a bounded set-associative table.
    uint32_t num_sets = 0;
    uint32_t num_ways = 0;
    // table[set][way]
    std::vector<std::vector<PBEntry>> table;

    // Fallback (original) map-based storage when not using table-mode
    std::unordered_map<uint64_t, PBEntry> entries; // key = address >> offset_bits

    uint64_t stat_inserts     = 0;
    uint64_t stat_demand_hits = 0;
    uint64_t stat_evicted_unused = 0;  // Track useless prefetches (evicted without use)
    uint64_t stat_late_demand = 0;     // Track prefetches evicted then later demanded (subset of useless)

    // Track evicted entries to detect late demands (unbounded for accurate stats)
    std::map<uint64_t, uint64_t> evicted_addresses;  // key -> eviction_cycle

    uint64_t make_key(uint64_t address) const { return address >> offset_bits; }

  public:
    // Optional: pass non-zero _num_sets/_num_ways to enable set-associative table mode.
    explicit PrefetchBuffer(uint32_t _offset_bits, BufferMode _mode = PREFETCH_MODE, bool _fill_cache_on_hit=true, uint32_t _num_sets=0, uint32_t _num_ways=0)
      : offset_bits(_offset_bits), mode(_mode), fill_cache_on_hit(_fill_cache_on_hit), num_sets(_num_sets), num_ways(_num_ways)
    {
      // Read replacement policy from env var (LRU=0, LFU=1)
      if (auto e = champsim::EnvVar<int>::get("PF_BUFFER_REPL_POLICY")) {
        repl_policy = (*e == 1) ? LFU : LRU;
      } else {
        repl_policy = LRU;
      }

      const char* mode_str = (mode == MISS_MODE) ? "MISS_MODE" : "PREFETCH_MODE";
      const char* repl_str = (repl_policy == LFU) ? "LFU" : "LRU";
      std::cout << "[DEBUG] PrefetchBuffer constructor: offset_bits=" << _offset_bits << ", mode=" << mode_str << std::endl;
      if (num_sets > 0 && num_ways > 0) {
        table.assign(num_sets, std::vector<PBEntry>(num_ways));
        std::cout << "PREFETCH_BUFFER: set-assoc table mode: sets=" << num_sets << " ways=" << num_ways << " mode=" << mode_str << " repl=" << repl_str << ", fill_cache_on_hit=" << std::boolalpha << fill_cache_on_hit << std::noboolalpha << std::endl;
      } else {
        std::cout << "PREFETCH_BUFFER: map-based (unbounded, collision-free) mode=" << mode_str << ", fill_cache_on_hit=" << std::boolalpha << fill_cache_on_hit << std::noboolalpha << std::endl;
      }
      std::cout << "[DEBUG] PrefetchBuffer constructor completed successfully" << std::endl;
    }

    BufferMode get_mode() const { return mode; }
    void set_mode(BufferMode _mode) { mode = _mode; }
    bool fill_cache_on_hit_enabled() const { return fill_cache_on_hit; }

    void insert(const PACKET& pkt, uint64_t cycle)
    {
      uint64_t key = make_key(pkt.address);

      // Table-mode (bounded set-associative)
      if (num_sets > 0 && num_ways > 0) {
        const uint64_t set_idx = key % num_sets;
        const uint64_t tag = key / num_sets;

        // Search for an existing tag in the set
        int free_way = -1;
        int victim_way = 0;
        uint64_t victim_metric = UINT64_MAX;
        for (uint32_t w = 0; w < num_ways; ++w) {
          auto &way = table[set_idx][w];
          if (way.valid && way.tag == tag) {
            // overwrite existing
            way.data = pkt.data;
            way.insert_cycle = cycle;
            way.pf_metadata = pkt.pf_metadata;
            way.pf_prefetch_tag = pkt.pf_prefetch_tag;
            way.pf_origin_cache = pkt.pf_origin_cache;
            way.type = pkt.type;
#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined TRANSLATION_EXCLUSIVE_CACHE
            way.is_pte = pkt.is_pte;
            way.is_instr = pkt.is_instr;
            way.pte_level = static_cast<uint8_t>(pkt.translation_level);
#endif
            stat_inserts++;
            return;
          }
          if (!way.valid && free_way == -1)
            free_way = static_cast<int>(w);
          if (!way.valid) {
            // treat invalid as best victim candidate
            if (victim_metric == UINT64_MAX) { victim_way = w; victim_metric = 0; }
          } else {
            // Select victim based on replacement policy
            uint64_t metric = (repl_policy == LFU) ? way.frequency : way.insert_cycle;
            if (metric < victim_metric) {
              victim_way = w;
              victim_metric = metric;
            }
          }
        }

        int use_way = (free_way != -1) ? free_way : victim_way;
        auto &victim = table[set_idx][use_way];
        // Track useless prefetch: evicting a valid, never-accessed entry
        if (victim.valid && !victim.ever_accessed) {
          stat_evicted_unused++;
          // Record evicted address for late-demand tracking (unbounded)
          evicted_addresses[key] = cycle;
        }
        victim.valid = true;
        victim.ever_accessed = false;  // Reset access tracking
        victim.tag = tag;
        victim.data = pkt.data;
        victim.insert_cycle = cycle;
        victim.frequency = 0;  // Reset frequency on new insertion
        victim.pf_metadata = pkt.pf_metadata;
        victim.pf_prefetch_tag = pkt.pf_prefetch_tag;
        victim.pf_origin_cache = pkt.pf_origin_cache;
        victim.type = pkt.type;
#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined TRANSLATION_EXCLUSIVE_CACHE
        victim.is_pte = pkt.is_pte;
        victim.is_instr = pkt.is_instr;
        victim.pte_level = static_cast<uint8_t>(pkt.translation_level);
#endif
        stat_inserts++;
        return;
      }

      // Map-based fallback (original behavior)
      // In MISS_MODE, buffer can grow unbounded with demand misses.
      // Safeguard: stop inserting if buffer exceeds MAX_ENTRIES.
      if (mode == MISS_MODE && entries.size() >= MAX_ENTRIES) {
        if (stat_inserts == MAX_ENTRIES) {
          std::cerr << "WARNING: PREFETCH_BUFFER MISS_MODE reached capacity (" << MAX_ENTRIES << " entries). "
                    << "Stopping insertions to prevent OOM. Consider increasing MAX_ENTRIES or using PREFETCH_MODE." << std::endl;
        }
        return;
      }

      auto& e       = entries[key]; // insert or overwrite
      e.data         = pkt.data;
      e.insert_cycle = cycle;
      e.pf_metadata  = pkt.pf_metadata;
      e.pf_prefetch_tag = pkt.pf_prefetch_tag;
      e.pf_origin_cache = pkt.pf_origin_cache;
      e.type         = pkt.type;
#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined TRANSLATION_EXCLUSIVE_CACHE
      e.is_pte       = pkt.is_pte;
      e.is_instr     = pkt.is_instr;
      e.pte_level    = static_cast<uint8_t>(pkt.translation_level);
#endif
      stat_inserts++;
    }

    PBEntry* lookup(uint64_t address)
    {
      uint64_t key = make_key(address);

      // Check if this address was previously evicted (late demand)
      auto evicted_it = evicted_addresses.find(key);
      if (evicted_it != evicted_addresses.end()) {
        stat_late_demand++;
        evicted_addresses.erase(evicted_it);  // Remove to avoid double-counting
      }

      // Table-mode (bounded set-associative)
      if (num_sets > 0 && num_ways > 0) {
        const uint64_t set_idx = key % num_sets;
        const uint64_t tag = key / num_sets;
        for (uint32_t w = 0; w < num_ways; ++w) {
          auto &way = table[set_idx][w];
          if (way.valid && way.tag == tag) {
            stat_demand_hits++;
            way.ever_accessed = true;  // Mark as accessed for accuracy tracking
            // Increment frequency for LFU replacement (saturate at max uint32_max)
            if (way.frequency < UINT32_MAX)
              way.frequency++;
            return &way;
          }
        }
        return nullptr;
      }

      auto it = entries.find(key);
      if (it != entries.end()) {
        stat_demand_hits++;
        return &it->second;
      }
      return nullptr;
    }

    void invalidate(uint64_t address)
    {
      uint64_t key = make_key(address);
      if (num_sets > 0 && num_ways > 0) {
        const uint64_t set_idx = key % num_sets;
        const uint64_t tag = key / num_sets;
        for (uint32_t w = 0; w < num_ways; ++w) {
          auto &way = table[set_idx][w];
          if (way.valid && way.tag == tag) {
            way.valid = false;
            return;
          }
        }
        return;
      }

      entries.erase(key);
    }

    void print_stats() const
    {
      const double hit_rate = (stat_inserts > 0)
                                ? 100.0 * static_cast<double>(stat_demand_hits) / static_cast<double>(stat_inserts)
                                : 0.0;
      const uint64_t useful = stat_demand_hits;
      const uint64_t useless = stat_evicted_unused;
      const uint64_t total_known = useful + useless;
      const double accuracy = (total_known > 0)
                                ? 100.0 * static_cast<double>(useful) / static_cast<double>(total_known)
                                : 0.0;
      const char* mode_str = (mode == MISS_MODE) ? "MISS_MODE" : "PREFETCH_MODE";
      const char* repl_str = (repl_policy == LFU) ? "LFU" : "LRU";
      size_t size_at_end = 0;
      if (num_sets > 0 && num_ways > 0) {
        for (uint32_t s = 0; s < num_sets; ++s)
          for (uint32_t w = 0; w < num_ways; ++w)
            if (table[s][w].valid)
              ++size_at_end;
      } else {
        size_at_end = entries.size();
      }

      // Format matches ChampSim stat patterns for easy parsing: CACHE_NAME already printed by caller
      std::cout << "PREFETCH_BUFFER"
                << " INSERTS: " << stat_inserts
                << " USEFUL: " << useful
                << " USELESS: " << useless
                << " LATE_DEMAND: " << stat_late_demand
                << " ACCURACY: " << std::fixed << std::setprecision(2) << accuracy
                << " COVERAGE: " << hit_rate
                << " MODE: " << mode_str
                << " REPL: " << repl_str
                << " SIZE_AT_END: " << size_at_end
                << std::endl;
    }
  };

  PrefetchBuffer* pf_buffer         = nullptr;
  bool             enable_pf_buffer = false;
#endif // PREFETCH_BUFFER

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
#elif defined TX_SPLIT_CACHE
  [[deprecated("Use get_set_index() instead.")]] uint64_t get_set(uint64_t address, uint8_t type) const;
  [[deprecated("This function should not be used to access the blocks directly.")]] uint64_t get_way(uint64_t address, uint8_t type, uint64_t set) const;
  uint64_t invalidate_entry(uint64_t inval_addr, uint8_t type);
#else
  [[deprecated("Use get_set_index() instead.")]] uint64_t get_set(uint64_t address) const;
  [[deprecated("This function should not be used to access the blocks directly.")]] uint64_t get_way(uint64_t address, uint64_t set) const;
  uint64_t invalidate_entry(uint64_t inval_addr);
#endif

  int prefetch_line(uint64_t pf_addr, bool fill_this_level, uint32_t prefetch_metadata);
  int prefetch_pte_line(uint64_t pf_addr, bool fill_this_level, std::size_t translation_level, uint64_t prefetch_metadata = 0, uint32_t prefetch_tag = 0);

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

    // Read environment variables to control whether this cache should pass
    // the unmasked full PTE address to prefetchers for TRANSLATION packets.
    // Per-cache variable (preferred):
    //   - L1D_PF_PREFETCH_FULL_ADDR, L2C_PF_PREFETCH_FULL_ADDR, LLC_PF_PREFETCH_FULL_ADDR
    //     set to a non-zero value to enable passing raw full PTE addresses for that cache.
    std::string per_cache_var;
    if (NAME.find("L1D") != std::string::npos) {
      per_cache_var = "L1D_PF_PREFETCH_FULL_ADDR";
    } else if (NAME.find("L2C") != std::string::npos) {
      per_cache_var = "L2C_PF_PREFETCH_FULL_ADDR";
    } else if (NAME.find("LLC") != std::string::npos) {
      per_cache_var = "LLC_PF_PREFETCH_FULL_ADDR";
    }

    if (!per_cache_var.empty()) {
      if (auto vv = champsim::EnvVar<int>::get(per_cache_var.c_str())) {
        if (*vv != 0) {
          prefetch_use_full_address = true;
        }
      }
    }

    if (prefetch_use_full_address) std::cout << NAME << ": PF_PREFETCH_FULL_ADDR per-cache enabled via " << per_cache_var << std::endl;

#if defined FORCE_HIT 
		if (force_hit) {
			if (NAME.find("STLB") != std::string::npos) {
				std::cout << "Using perfect instruction " << NAME << "." << std::endl;
			//}	else if (NAME.find(_CACHE_) != std::string::npos) {
			//	std::cout << "Using secret unlimited cache for data PTEs in " << NAME << "." << std::endl;
			} else {
				std::cout << "Force hit not supported for " << NAME << "!" << std::endl;
				assert(false);
			}
		}
#endif 

#if defined TRANSLATION_EXCLUSIVE_CACHE

    if (auto v = champsim::EnvVar<int>::get("TXVC_CACHE_LEVEL")) {
      uint32_t _level = static_cast<uint32_t>(*v);
      switch (_level) {
        case 1:
            _CACHE_ = "cpu0_L1D";
            break;
          case 2:
            _CACHE_ = "cpu0_L2C";
            break;
          case 3:
            _CACHE_ = "LLC";
            break; 
      }
    }

    //TODO: remove this var, we can assume TXVC_CACHE_LEVEL enables it
    if (NAME.find(_CACHE_) != std::string::npos) {
      if (auto v = champsim::EnvVar<bool>::get("ENABLE_TXVC")) {
        if (*v) enable_tx_victim_cache = true;
      }
    }


    if (enable_tx_victim_cache || enable_tx_cache) {
      
      if (NAME.find(_CACHE_) != std::string::npos) {
        //FIXME: Not sure we should use braces for constructor - but maybe we need to (???)
        // Create and connect a new victim cache between L1D and L2C
        //uint32_t num_set = 64;
        //uint32_t num_way = 8;
        //uint32_t mshr_size = 8; //64;
        //NonTranslatingQueues* tx_cache_queues = new NonTranslatingQueues(1.0, num_set, num_way, mshr_size, 5, 4, champsim::lg2(64), 0);

        uint32_t txvc_num_set = 64;
        uint32_t txvc_num_way = 8;
        uint32_t txvc_latency = 1;
        //uint32_t txvc_mshr_size = 8; //64;

        if (auto v = champsim::EnvVar<unsigned long long>::get("TXVC_LATENCY")) {
          txvc_latency = *v;
        } else {
          std::cerr << "TXVC_LATENCY not set!" << std::endl;
          exit(0);
        }

        if (auto v = champsim::EnvVar<unsigned long long>::get("TXVC_NUM_SET")) {
          txvc_num_set = static_cast<uint32_t>(*v);
        } else {
          std::cerr << "TXVC_NUM_SET not set!" << std::endl;
          exit(0);
        }

        if (auto v = champsim::EnvVar<unsigned long long>::get("TXVC_NUM_WAY")) {
          txvc_num_way = static_cast<uint32_t>(*v);
        } else {
          std::cerr << "TXVC_NUM_WAY not set!" << std::endl;
          exit(0);
        }

        if (auto v = champsim::EnvVar<bool>::get("TXVC_INSTR_ONLY")) {
          std::cout << "found instruction only flag" << std::endl;
          if (*v) enable_instr_only = true;
        }

        if (auto v = champsim::EnvVar<bool>::get("TXVC_DATA_ONLY")) {
          std::cout << "found data only flag" << std::endl;
          if (*v) enable_data_only = true;
        }

        std::cout << NAME << ": Using PTE " << (enable_tx_victim_cache?"victim":"exclusive")  << " cache." << std::endl;
        std::cout << "\t\tLEVEL: " << _CACHE_ << std::endl;
        std::cout << "\t\tLATENCY: " << txvc_latency << std::endl;
        std::cout << "\t\tSETS: " << txvc_num_set << std::endl;
        std::cout << "\t\tWAYS: " << txvc_num_way << std::endl;
        if (enable_instr_only) 
          std::cout << "\t\tAllowing only instuction PTEs." << std::endl;
        else if (enable_data_only)
          std::cout << "\t\tAllowing only data PTEs." << std::endl;
        else 
          std::cout << "\t\tAllowing both instuction and data PTEs." << std::endl;
        
        

        //tx_cache = new CACHE( NAME+"_TXC", 1.0, txvc_num_set, txvc_num_way, txvc_mshr_size, txvc_latency, 2, 2, champsim::lg2(64), 0, 0, 0, 
        //											(1 << LOAD) | (1 << PREFETCH), *tx_cache_queues, ll, 
        //											CACHE::pprefetcherDno, CACHE::rreplacementDlfu, 0, 0, vmem);

        tx_victim_cache = new VICTIM_CACHE(txvc_num_set, txvc_num_way, champsim::lg2(64), _CACHE_ + "_TXVC");
        
      }
		}

    last_pte_entry.reserve(NUM_SET);
#endif

#if defined TX_SPLIT_CACHE

    enable_tx_split_cache = false;
    std::string _TX_SPLIT_CACHE_ = "none";
    if (auto v = champsim::EnvVar<int>::get("TX_SPLIT_CACHE_LEVEL")) {
      uint32_t _level = static_cast<uint32_t>(*v);
      switch (_level) {
        case 1:
            _TX_SPLIT_CACHE_ = "cpu0_L1D";
            break;
          case 2:
            _TX_SPLIT_CACHE_ = "cpu0_L2C";
            break;
          case 3:
            _TX_SPLIT_CACHE_ = "LLC";
            break; 
      }


      if (NAME.find(_TX_SPLIT_CACHE_) != std::string::npos) {
        
        enable_tx_split_cache = true;
        if (auto v2 = champsim::EnvVar<unsigned long long>::get("TX_NUM_SETS")) {
          TX_NUM_SET = static_cast<uint32_t>(*v2);

          std::cout << NAME << ": Using PTE exclusive sets:" << std::endl;
          std::cout << "\t\tSETS: " << TX_NUM_SET << std::endl;
        
        } else {
          std::cerr << "TX_NUM_SETS not set!" << std::endl;
          exit(0);
        }

      } else {
        std::cout << NAME + " is not using any Translations exclusive cache sets." << std::endl; 
      }
      } else {
        std::cout << "TX_SPLIT_CACHE_LEVEL not set." << std::endl;
      }
#elif defined TX_SPLIT_CACHE_WAYS
    //NUM_WAY -= 1; // Reserve one way for PTEs
    assert(NUM_WAY > 1); // Need at least 2 ways to split
#endif

#if defined TX_SPLIT_CACHE
  // Only used if num_sets is NOT a power of two
  barret_reciprocal = ( ( __uint128_t)1 << 64 ) / (NUM_SET - TX_NUM_SET);
  
  if (TX_NUM_SET != 0) {
    tx_barret_reciprocal = ( ( __uint128_t)1 << 64 ) / (TX_NUM_SET);
  } else {
    tx_barret_reciprocal = 0;
  }
#endif

#if defined ENABLE_EXTRA_CACHE_STATS
		if (NAME.find("STLB") != std::string::npos) {
            std::string page_address_stats_file_prefix = champsim::EnvVar<std::string>::get_or("PAGE_ADDRESS_STATS_FILENAME_PREFIX", std::string(""));

            pageAddressStatsMon = new PageAddressStatsHanlder(OFFSET_BITS,
                                                                                                page_address_stats_file_prefix,
                                                                                                false);
		}	else {

			pageAddressStatsMon = new PageAddressStatsHanlder(OFFSET_BITS, "", false);
		}

        if (auto v = champsim::EnvVar<std::string>::get("ACCESS_FREQ_STATS_FILENAME_PREFIX")) {
          std::string access_freq_stats_filename_prefix = *v;
          if (NAME.find("cpu0_L2C") != std::string::npos) {
            addressAccessStatsMon = new AddressAccessStatsHanlder(access_freq_stats_filename_prefix + "_" + NAME + ".csv", true);
          } else {
            addressAccessStatsMon = new AddressAccessStatsHanlder(access_freq_stats_filename_prefix + "_" + NAME + ".csv", false);
          }

    } else {
        std::cerr << "ACCESS_FREQ_STATS_FILENAME_PREFIX not set!" << std::endl;
        exit(0);
    }

    std::string reuse_dist_filename_prefix = champsim::EnvVar<std::string>::get_or("REUSE_DIST_FILENAME_PREFIX", std::string(""));

		bool enable_reuseDistMon = false;
		if (NAME.find("STLB") != std::string::npos) {
			enable_reuseDistMon = false;
		} else if (NAME.find("L1D") != std::string::npos) {
			enable_reuseDistMon = false;
			if (NAME.find("TXC") != std::string::npos) {
				std::cout << NAME << " enabled reuse distance monitor." << std::endl;
				enable_reuseDistMon = false;
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
  
#if defined PREFETCH_BUFFER
    // ENABLE_PF_BUFFER: runtime flag (0 or 1) to enable prefetch buffer.
    // Set via config: <cache>.enable_pf_buffer = 1
    // Environment variable is cache-specific: L1D_ENABLE_PF_BUFFER, L2C_ENABLE_PF_BUFFER, LLC_ENABLE_PF_BUFFER
    // PF_BUFFER_MODE: "PREFETCH" (default) or "MISS" to switch behavior
    std::string env_var_name;
    if (NAME.find("L1D") != std::string::npos) {
      env_var_name = "L1D_ENABLE_PF_BUFFER";
    } else if (NAME.find("L2C") != std::string::npos) {
      env_var_name = "L2C_ENABLE_PF_BUFFER";
    } else if (NAME.find("LLC") != std::string::npos) {
      env_var_name = "LLC_ENABLE_PF_BUFFER";
    }
    
    std::cerr << "[DEBUG] " << NAME << " checking env var: '" << env_var_name << "'" << std::endl;
    if (!env_var_name.empty()) {
      if (auto v = champsim::EnvVar<int>::get(env_var_name.c_str())) {
        std::cerr << "[DEBUG] " << NAME << " found env var " << env_var_name << " = " << *v << std::endl;
        if (*v != 0) {
          enable_pf_buffer = true;
          
          // Determine buffer mode from environment
          PrefetchBuffer::BufferMode mode = PrefetchBuffer::PREFETCH_MODE;
          
          // Check for specific mode env var
          std::string cache_prefix;
          if (NAME.find("L1D") != std::string::npos) {
            cache_prefix = "L1D_PF_BUFFER_MODE";
          } else if (NAME.find("L2C") != std::string::npos) {
            cache_prefix = "L2C_PF_BUFFER_MODE";
          } else if (NAME.find("LLC") != std::string::npos) {
            cache_prefix = "LLC_PF_BUFFER_MODE";
          }
          
          if (!cache_prefix.empty()) {
            if (auto mode_str = champsim::EnvVar<std::string>::get(cache_prefix.c_str())) {
              if (*mode_str == "MISS") {
                mode = PrefetchBuffer::MISS_MODE;
              }
            }
          }
          
          bool fill_cache_on_hit = true;
          if (auto vv = champsim::EnvVar<bool>::get("PF_BUFFER_FILL_CACHE_ON_HIT")) {
              fill_cache_on_hit = *vv;
          }

          std::cout << "[DEBUG] " << NAME << " about to create PrefetchBuffer with OFFSET_BITS=" << OFFSET_BITS << std::endl;
          std::cout << NAME << " enabling PREFETCH_BUFFER (mode=" 
                    << (mode == PrefetchBuffer::MISS_MODE ? "MISS" : "PREFETCH") << ", fill_cache_on_hit=" << std::boolalpha << fill_cache_on_hit << std::noboolalpha << ")" << std::endl;

          // Optional set-associative parameters from environment
          uint32_t pf_buf_sets = 0;
          uint32_t pf_buf_ways = 0;
          if (auto s = champsim::EnvVar<uint32_t>::get("PF_BUFFER_SETS"))
            pf_buf_sets = *s;
          if (auto w = champsim::EnvVar<uint32_t>::get("PF_BUFFER_WAYS"))
            pf_buf_ways = *w;

          if (pf_buf_sets > 0 && pf_buf_ways > 0)
            std::cout << "[DEBUG] " << NAME << " PREFETCH_BUFFER: using set-assoc table sets=" << pf_buf_sets << " ways=" << pf_buf_ways << std::endl;

          pf_buffer = new PrefetchBuffer(OFFSET_BITS, mode, fill_cache_on_hit, pf_buf_sets, pf_buf_ways);
          std::cout << "[DEBUG] " << NAME << " PrefetchBuffer created at address " << pf_buffer << ", enable_pf_buffer=" << enable_pf_buffer << std::endl;
          std::cout << "[DEBUG] " << NAME << " Buffer allocation and initialization complete" << std::endl;
        }
      }
    }
#endif // PREFETCH_BUFFER

    // other debugging and stats 
    touched_indices.reserve(NUM_SET);
    for (uint32_t i = 0; i < NUM_SET; i++) {
      touched_indices[i] = 0;
    }
}

#if defined ENABLE_EXTRA_CACHE_STATS
  void hit_hook(const PACKET&);
  void miss_hook(const PACKET&);
#endif

	//~CACHE() { std::cout << "***** CACHE DESTROYER *****" << std::endl; };
};

#endif
