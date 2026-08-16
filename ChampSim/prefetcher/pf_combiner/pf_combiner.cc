#include <iostream>

#include "cache.h"
#include "champsim_constants.h"
#include "env_var.h"

#include "../child_ideal/child_ideal_pf.h"
#include "../next_line/next_line.h"
#include "pf_combiner.h"

namespace {

class PFCombinerImpl
{
public:
  explicit PFCombinerImpl(uint64_t _offset_bits) : child_pf(_offset_bits), offset_bits(_offset_bits) { std::cout << "PF PFCombiner: initialized" << std::endl; }

  std::vector<uint64_t> process_translation(uint64_t address, std::size_t translation_level, uint64_t translated_vpn)
  {
    return child_pf.process_access(address, translation_level, translated_vpn);
  }

  std::vector<uint64_t> process_regular_access(uint64_t address, uint64_t ip, uint8_t type)
  {
    (void)ip; (void)type;
    return nl_pf.get_prefetch_candidates(address, /*translation_level=*/0, /*ip=*/ip, /*translated_vpn=*/0);
  }

  bool get_child_fill_this_level() const { return child_pf.get_fill_this_level(); }
  uint32_t get_child_mshr_gate_pct() const { return child_pf.get_mshr_gate_pct(); }

  void print_stats() const { child_pf.print_stats(); nl_pf.print_stats(); }

private:
  ChildIdealPrefetcher child_pf;
  NextLinePrefetcher nl_pf;
  uint64_t offset_bits;
};

std::map<CACHE*, PFCombinerImpl*> pfcombiner_map;

} // namespace

void CACHE::prefetcher_initialize()
{
  std::cout << NAME << " PFCombiner prefetcher" << std::endl;
  pfcombiner_map[this] = new PFCombinerImpl(OFFSET_BITS);
}

void CACHE::prefetcher_cycle_operate() {}

uint64_t CACHE::prefetcher_cache_operate(uint64_t addr, uint64_t ip, uint8_t cache_hit, uint8_t type, uint64_t metadata_in)
{
  auto* pf = pfcombiner_map[this];

  if (static_cast<access_type>(type) == access_type::TRANSLATION) {
    const std::size_t translation_level = static_cast<std::size_t>(metadata_in & 0xF);
    const uint64_t vpn_mask_60 = (1ULL << 60) - 1;
    const uint64_t translated_vpn = (metadata_in >> 4) & vpn_mask_60;

    auto candidates = pf->process_translation(addr, translation_level, translated_vpn);

    if (!candidates.empty()) {
      // MSHR gate check for child prefetcher
      if (get_occupancy(0, addr) * 100 >= get_size(0, addr) * pf->get_child_mshr_gate_pct()) {
        return metadata_in;  // Back off if MSHR too full
      }

      for (auto pf_addr : candidates) {
        if (pf_addr == 0) continue;
        const std::size_t issue_level = (translation_level > 0) ? translation_level - 1 : 0;
        // Use child_pf's configurable fill_this_level and tag prefetches for PrefetchBuffer
        if (!prefetch_pte_line(pf_addr, pf->get_child_fill_this_level(), issue_level, 0, PB_PTE_PREFETCH_METADATA)) {
          // enqueue failed notification could be added
        }
      }
    }
  } else {
    auto candidates = pf->process_regular_access(addr, ip, type);
    if (!candidates.empty()) {
      for (auto pf_addr : candidates) {
        if (pf_addr == 0) continue;
        if (!prefetch_line(pf_addr, /*populate_vc=*/true, metadata_in)) {
          // enqueue failed notification could be added
        }
      }
    }
  }

  return metadata_in;
}

void CACHE::prefetcher_final_stats()
{
  auto it = pfcombiner_map.find(this);
  if (it != pfcombiner_map.end()) it->second->print_stats();
}

uint64_t CACHE::prefetcher_cache_fill(uint64_t addr, uint32_t set, uint32_t way, uint8_t prefetch, uint64_t evicted_addr, uint64_t metadata_in)
{
  (void)addr; (void)set; (void)way; (void)prefetch; (void)evicted_addr;
  // No per-fill special handling required for PFCombiner; just pass through metadata.
  return metadata_in;
}
