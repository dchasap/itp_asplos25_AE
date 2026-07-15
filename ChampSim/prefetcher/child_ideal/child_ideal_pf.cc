/*
 * Child-Ideal PTE Prefetcher
 *
 * A simplified page-walk predictor based on observing parent-to-child PTE relationships.
 * Uses two maps to store observations:
 *   - Table A: (VPN, level) -> PTE_address (discovery table)
 *   - Table B: (parent_PTE_address, VPN) -> child_PTE_address (prediction table)
 *
 * Requirements:
 *   - Add "prefetch_activate": "LOAD,PREFETCH,TRANSLATION" to the target cache
 *     in champsim_config.json so that TRANSLATION-type accesses reach this hook.
 *   - ptw.cc must encode translation_level (lower 8 bits) and VPN (upper 24 bits) into pf_metadata.
 *
 * Env vars:
 *   PF_CHILD_TRAIN_ON_HIT  - train on demand hits (default 1)
 *   PF_CHILD_ISSUE_ON_HIT  - allow issuing prefetches on demand hits (default 0)
 *   PF_MSHR_GATE_PCT       - MSHR gate percentage (default 50)
 */

#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <unordered_set>
#include <utility>
#include <vector>
#include <cassert>

#include "cache.h"
#include "champsim_constants.h"
#include "env_var.h"
#include "child_ideal_pf.h"

namespace {
std::map<CACHE*, ChildIdealPrefetcher*> ideal_pfs;
} // namespace

void CACHE::prefetcher_initialize()
{
  std::cout << NAME << " Child-Ideal PTE prefetcher" << std::endl;
  ideal_pfs[this] = new ChildIdealPrefetcher(OFFSET_BITS);
}

void CACHE::prefetcher_cycle_operate() {}

uint64_t CACHE::prefetcher_cache_operate(uint64_t addr, uint64_t ip, uint8_t cache_hit, uint8_t type, uint64_t metadata_in)
{
  // Only activate on TRANSLATION-type accesses (PTW probes)
  if (static_cast<access_type>(type) != access_type::TRANSLATION)
    return metadata_in;

  auto* pf = ideal_pfs[this];

  // Extract translation_level from lower 4 bits and VPN from upper bits of metadata
  const std::size_t translation_level = static_cast<std::size_t>(metadata_in & 0xF);
  const uint64_t vpn_mask_60 = (1ULL << 60) - 1;
  const uint64_t translated_vpn = (metadata_in >> 4) & vpn_mask_60;

  if (cache_hit) {
    if (!pf->should_train_on_hit()) {
      // Don't train or prefetch on hit
      return metadata_in;
    }

    if (pf->should_issue_on_hit()) {
      // Check MSHR gate
      if (get_occupancy(0, addr) * 100 >= get_size(0, addr) * pf->get_mshr_gate_pct()) {
        pf->notify_mshr_gate_blocked();
        pf->observe_access(addr, translation_level, translated_vpn);
        return metadata_in;
      }

      auto candidates = pf->get_prefetch_candidates(addr, translation_level, translated_vpn);
      for (auto pf_addr : candidates) {
        if (pf_addr == 0) continue;  // Skip invalid addresses
        const std::size_t child_level = (translation_level > 0) ? translation_level - 1 : 0;
        if (prefetch_pte_line(pf_addr, /*fill_this_level=*/true, child_level)) {
            pf->record_prefetch_issued(pf_addr);
        } else {
          pf->notify_enqueue_failed();
        }
      }
    } else {
      // Training only (no prefetch on hit)
      pf->observe_access(addr, translation_level, translated_vpn);
    }
  } else {
    // MSHR gate: back off if MSHR is too full
    if (get_occupancy(0, addr) * 100 >= get_size(0, addr) * pf->get_mshr_gate_pct()) {
      pf->notify_mshr_gate_blocked();
      return metadata_in;
    }

    // Prediction + training path
    auto candidates = pf->get_prefetch_candidates(addr, translation_level, translated_vpn);
      for (auto pf_addr : candidates) {
      if (pf_addr == 0) continue;  // Skip invalid addresses
      const std::size_t child_level = (translation_level > 0) ? translation_level - 1 : 0;
      if (prefetch_pte_line(pf_addr, /*fill_this_level=*/true, child_level)) {
          pf->record_prefetch_issued(pf_addr);
      } else {
        pf->notify_enqueue_failed();
      }
    }
  }

  return metadata_in;
}

uint64_t CACHE::prefetcher_cache_fill(uint64_t addr, uint32_t set, uint32_t way, uint8_t prefetch, uint64_t evicted_addr, uint64_t metadata_in)
{
  return metadata_in;
}

void CACHE::prefetcher_final_stats()
{
  auto it = ideal_pfs.find(this);
  if (it != ideal_pfs.end())
    it->second->print_stats();
}
