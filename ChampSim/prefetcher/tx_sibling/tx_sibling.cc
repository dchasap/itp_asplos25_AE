/*
 * TX-Sibling PTE Prefetcher
 *
 * Standalone ChampSim cache prefetcher that uses a local sibling-prefetch policy
 * to predict sibling PTE cache lines (PTEs that reside on
 * the same page-table page as the currently accessed PTE).
 *
 * Requirements:
 *   - Add "prefetch_activate": "LOAD,PREFETCH,TRANSLATION" to the target cache
 *     in champsim_config.json so that TRANSLATION-type accesses reach this hook.
 *   - ptw.cc must encode translation_level into pf_metadata (lower 8 bits).
 *
 * Env vars:
 *   PF_SBLG_TABLE_SIZE     - prefetch table entries (default 128)
 *   PF_SBLG_DEGREE         - max candidates per access (default 1)
 *   PF_SBLG_CONF_THRESHOLD - confidence threshold (default 2)
 *   PF_SBLG_ACC_WINDOW     - usefulness window size (default 32)
 *   PF_SBLG_ACC_THRESHOLD  - usefulness threshold percentage (default 20)
 *   PF_MSHR_GATE_PCT       - MSHR gate percentage (default 50)
 */

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <vector>

#include "cache.h"
#include "env_var.h"

namespace {
#include "tx_sibling.h"

std::map<CACHE*, TxSiblingPrefetcher*> sibling_pfs;
} // namespace

void CACHE::prefetcher_initialize()
{
  std::cout << NAME << " TX-Sibling PTE prefetcher" << std::endl;
  sibling_pfs[this] = new TxSiblingPrefetcher(OFFSET_BITS);
}

void CACHE::prefetcher_cycle_operate() {}

uint64_t CACHE::prefetcher_cache_operate(uint64_t addr, uint64_t ip, uint8_t cache_hit, uint8_t type, uint64_t metadata_in)
{
  // Only activate on TRANSLATION-type accesses (PTW probes)
  if (static_cast<access_type>(type) != access_type::TRANSLATION)
    return static_cast<uint64_t>(metadata_in);

  auto* pf = sibling_pfs[this];

  // Extract translation_level from lower 4 bits of metadata
  // (encoded by ptw.cc step_translation)
  const std::size_t translation_level = static_cast<std::size_t>(metadata_in & 0xF);

  if (cache_hit) {
    // Train on hits without issuing prefetches.
    pf->observe_access(addr, translation_level, ip, /*translated_vpn=*/0);
    return metadata_in;
  }

  // MSHR gate: back off if MSHR is too full, but still train.
  if (get_occupancy(0, addr) * 100 >= get_size(0, addr) * pf->get_mshr_gate_pct()) {
    pf->notify_mshr_gate_blocked();
    pf->observe_access(addr, translation_level, ip, /*translated_vpn=*/0);
    return metadata_in;
  }

  auto candidates = pf->get_prefetch_candidates(addr, translation_level, ip, /*translated_vpn=*/0);
  for (auto pf_addr : candidates) {
    if (!prefetch_pte_line(pf_addr, /*fill_this_level=*/true, translation_level))
      pf->notify_enqueue_failed();
  }

  return metadata_in;
}

uint64_t CACHE::prefetcher_cache_fill(uint64_t addr, uint32_t set, uint32_t way, uint8_t prefetch, uint64_t evicted_addr, uint64_t metadata_in)
{
  return metadata_in;
}

void CACHE::prefetcher_final_stats()
{
  auto it = sibling_pfs.find(this);
  if (it != sibling_pfs.end())
    it->second->print_stats();
}
