/*
 * TX-Combo PTE Prefetcher
 *
 * Combines Child-Ideal and TX-Sibling approaches: train child first and
 * issue child candidates if available; otherwise fall back to sibling.
 */

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "cache.h"
#include "champsim_constants.h"
#include "env_var.h"
#include "../child_ideal/child_ideal_pf.h"
#include "../tx_sibling/tx_sibling.h"

namespace {

class ComboPrefetcher
{
private:
  ChildIdealPrefetcher child_pf;
  TxSiblingPrefetcher sibling_pf;

public:
  explicit ComboPrefetcher(uint64_t _offset_bits)
      : child_pf(_offset_bits), sibling_pf(_offset_bits)
  {
    std::cout << "PF TX-COMBO: using canonical ChildIdeal + Sibling implementations" << std::endl;
  }

  uint32_t get_child_mshr_gate_pct() const { return child_pf.get_mshr_gate_pct(); }
  uint32_t get_sibling_mshr_gate_pct() const { return sibling_pf.get_mshr_gate_pct(); }

  std::vector<uint64_t> process_access_and_get_candidates(uint64_t address, std::size_t translation_level, uint64_t translated_vpn, bool cache_hit, CACHE* cache)
  {
    (void)cache;
    // Child training + prediction
    auto child_candidates = child_pf.process_access(address, translation_level, translated_vpn);

    if (!child_candidates.empty()) {
      // Train sibling but don't run prediction
      sibling_pf.observe_access(address, translation_level, /*ip=*/0, translated_vpn);
      return child_candidates;
    }

    // No child candidates: train and run sibling prediction
    sibling_pf.observe_access(address, translation_level, /*ip=*/0, translated_vpn);
    auto s_candidates = sibling_pf.get_prefetch_candidates(address, translation_level, /*ip=*/0, translated_vpn);
    return s_candidates;
  }

  void record_child_prefetch_issued(uint64_t child_addr) { child_pf.record_prefetch_issued(child_addr); }
  void notify_child_enqueue_failed() { child_pf.notify_enqueue_failed(); }
  void notify_sibling_enqueue_failed() { sibling_pf.notify_enqueue_failed(); }
  void notify_child_mshr_blocked() { child_pf.notify_mshr_gate_blocked(); }
  void notify_sibling_mshr_blocked() { sibling_pf.notify_mshr_gate_blocked(); }

  void print_stats() const { child_pf.print_stats(); sibling_pf.print_stats(); }
};

std::map<CACHE*, ComboPrefetcher*> combo_pfs;

} // namespace

void CACHE::prefetcher_initialize()
{
  std::cout << NAME << " TX-Combo PTE prefetcher" << std::endl;
  combo_pfs[this] = new ComboPrefetcher(OFFSET_BITS);
}

void CACHE::prefetcher_cycle_operate() {}

uint64_t CACHE::prefetcher_cache_operate(uint64_t addr, uint64_t ip, uint8_t cache_hit, uint8_t type, uint64_t metadata_in)
{
  if (static_cast<access_type>(type) != access_type::TRANSLATION)
    return metadata_in;

  auto* pf = combo_pfs[this];

  const std::size_t translation_level = static_cast<std::size_t>(metadata_in & 0xF);
  const uint64_t vpn_mask_60 = (1ULL << 60) - 1;
  const uint64_t translated_vpn = (metadata_in >> 4) & vpn_mask_60;

  // Always attempt child first (training happens inside). The combo returns either
  // child candidates or sibling candidates depending on availability.
  auto candidates = pf->process_access_and_get_candidates(addr, translation_level, translated_vpn, cache_hit, this);

  // Choose MSHR gate based on which policy provided candidates
  bool used_child = false;
  if (!candidates.empty()) used_child = true; // assume child produced them when present

  uint32_t gate_pct = used_child ? pf->get_child_mshr_gate_pct() : pf->get_sibling_mshr_gate_pct();
  if (get_occupancy(0, addr) * 100 >= get_size(0, addr) * gate_pct) {
    if (used_child) pf->notify_child_mshr_blocked(); else pf->notify_sibling_mshr_blocked();
    // still trained above; don't issue
    return metadata_in;
  }

  if (!candidates.empty()) {
    for (auto pf_addr : candidates) {
      if (pf_addr == 0) continue;
      // child candidates correspond to child PTEs (one level below)
      const std::size_t issue_level = (translation_level > 0) ? translation_level - 1 : 0;
      if (prefetch_pte_line(pf_addr, /*fill_this_level=*/true, issue_level)) {
        if (used_child) pf->record_child_prefetch_issued(pf_addr);
      } else {
        if (used_child) pf->notify_child_enqueue_failed(); else pf->notify_sibling_enqueue_failed();
      }
    }
  }

  return metadata_in;
}

void CACHE::prefetcher_final_stats()
{
  auto it = combo_pfs.find(this);
  if (it != combo_pfs.end()) it->second->print_stats();
}
