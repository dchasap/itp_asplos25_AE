/*
 * TX-Child PTE Prefetcher
 *
 * Standalone ChampSim cache prefetcher that uses a local child-prefetch policy
 * to predict child-level PTE cache lines (the PTEs one
 * level lower in the page-table tree that will be accessed next after a given
 * parent PTE is resolved).
 *
 * Requirements:
 *   - Add "prefetch_activate": "LOAD,PREFETCH,TRANSLATION" to the target cache
 *     in champsim_config.json so that TRANSLATION-type accesses reach this hook.
 *   - ptw.cc must encode translation_level into pf_metadata (lower 8 bits).
 *
 * Env vars:
 *   PF_CHILD_TABLE_SIZE      - prediction table entries (default 256)
 *   PF_CHILD_PENDING_SIZE    - in-flight tracking entries (default 64)
 *   PF_CHILD_CONF_THRESHOLD  - confidence threshold (default 2)
 *   PF_CHILD_TRAIN_ON_HIT    - train on demand hits (default 1)
 *   PF_CHILD_ISSUE_ON_HIT    - allow issuing prefetches on demand hits (default 0)
 *   PF_MSHR_GATE_PCT         - MSHR gate percentage (default 50)
 */

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <vector>

#include "cache.h"
#include "champsim_constants.h"
#include "env_var.h"

namespace
{
class TxChildPrefetcher
{
private:
  struct PredEntry {
    uint64_t ip = 0;
    uint64_t translated_vpn = 0;
    uint64_t parent_pte_addr = 0;
    uint64_t child_cl_addr = 0;
    uint8_t confidence = 0;
    bool valid = false;
  };

  struct PendingParent {
    uint64_t ip = 0;
    uint64_t translated_vpn = 0;
    uint64_t pte_addr = 0;
    std::size_t level = 0;
    bool valid = false;
    uint64_t stamp = 0;
  };

  std::size_t table_size;
  std::size_t pending_size;
  uint8_t conf_threshold;
  bool train_on_hit;
  bool issue_on_hit;
  uint32_t mshr_gate_pct;
  uint64_t offset_bits;
  std::vector<PredEntry> table;
  std::vector<PendingParent> pending;
  uint64_t access_tick = 0;

  uint64_t entry_allocations = 0;
  uint64_t entry_replacements = 0;
  uint64_t entry_replaced_before_issue = 0;
  uint64_t entry_survived_to_issue = 0;
  uint64_t replaced_entry_lifetime_sum = 0;

  std::vector<uint64_t> entry_birth_tick;
  std::vector<uint32_t> entry_issued_prefetches;

  uint64_t reason_level0_skipped = 0;
  uint64_t reason_no_pending_parent = 0;
  uint64_t reason_pending_overwrite_collision = 0;
  uint64_t reason_training_replaced_mismatch = 0;
  uint64_t reason_leaf_level_no_predict = 0;
  uint64_t reason_predict_entry_invalid = 0;
  uint64_t reason_predict_tag_mismatch = 0;
  uint64_t reason_predict_conf_blocked = 0;
  uint64_t reason_predict_issued = 0;
  uint64_t reason_issue_mshr_blocked = 0;
  uint64_t reason_issue_enqueue_failed = 0;

  std::size_t pred_index(uint64_t ip, uint64_t parent_pte_addr, uint64_t translated_vpn) const
  {
    return (ip ^ (parent_pte_addr * 2654435761ULL) ^ (translated_vpn * 11400714819323198485ull)) % table_size;
  }

  std::size_t pending_set_index(uint64_t ip, uint64_t translated_vpn, std::size_t level) const
  {
    const uint64_t lvl_mix = static_cast<uint64_t>(level) * 11400714819323198485ull;
    return (ip ^ (translated_vpn * 2654435761ULL) ^ lvl_mix) % pending_size;
  }

  PendingParent* find_pending_parent(uint64_t ip, uint64_t translated_vpn, std::size_t parent_level)
  {
    const std::size_t set = pending_set_index(ip, translated_vpn, parent_level);
    PendingParent& cand = pending[set];
    if (cand.valid && cand.ip == ip && cand.translated_vpn == translated_vpn && cand.level == parent_level)
      return &cand;
    return nullptr;
  }

  void update_pending_parent(uint64_t ip, uint64_t translated_vpn, uint64_t pte_addr, std::size_t level)
  {
    const std::size_t set = pending_set_index(ip, translated_vpn, level);
    PendingParent& victim = pending[set];
    if (victim.valid && !(victim.ip == ip && victim.translated_vpn == translated_vpn && victim.level == level))
      reason_pending_overwrite_collision++;

    victim.valid = true;
    victim.ip = ip;
    victim.translated_vpn = translated_vpn;
    victim.pte_addr = pte_addr;
    victim.level = level;
    victim.stamp = access_tick;
  }

  std::vector<uint64_t> process_access(uint64_t address, std::size_t translation_level, uint64_t ip, uint64_t translated_vpn, bool allow_prediction)
  {
    access_tick++;
    if (translation_level == 0) {
      reason_level0_skipped++;
      return {};
    }

    const uint64_t cl_addr = address >> offset_bits;
    std::vector<uint64_t> candidates;

    PendingParent* pp = find_pending_parent(ip, translated_vpn, translation_level + 1);
    if (pp != nullptr) {
      const std::size_t idx = pred_index(ip, pp->pte_addr, translated_vpn);
      PredEntry& entry = table[idx];
      if (entry.valid && entry.ip == ip && entry.translated_vpn == translated_vpn && entry.parent_pte_addr == pp->pte_addr) {
        if (entry.child_cl_addr == cl_addr) {
          if (entry.confidence < 3)
            entry.confidence++;
        } else {
          entry.child_cl_addr = cl_addr;
          entry.confidence = 0;
        }
      } else {
        if (entry.valid) {
          reason_training_replaced_mismatch++;
          entry_replacements++;
          replaced_entry_lifetime_sum += (access_tick - entry_birth_tick[idx]);
          if (entry_issued_prefetches[idx] > 0)
            entry_survived_to_issue++;
          else
            entry_replaced_before_issue++;
        }
        entry.valid = true;
        entry.ip = ip;
        entry.translated_vpn = translated_vpn;
        entry.parent_pte_addr = pp->pte_addr;
        entry.child_cl_addr = cl_addr;
        entry.confidence = 0;
        entry_birth_tick[idx] = access_tick;
        entry_issued_prefetches[idx] = 0;
        entry_allocations++;
      }
    } else {
      reason_no_pending_parent++;
    }

    update_pending_parent(ip, translated_vpn, address, translation_level);

    if (!allow_prediction)
      return {};

    if (translation_level > 1) {
      const std::size_t idx = pred_index(ip, address, translated_vpn);
      const PredEntry& entry = table[idx];
      if (!entry.valid) {
        reason_predict_entry_invalid++;
      } else if (!(entry.ip == ip && entry.translated_vpn == translated_vpn && entry.parent_pte_addr == address)) {
        reason_predict_tag_mismatch++;
      } else if (entry.confidence < conf_threshold) {
        reason_predict_conf_blocked++;
      } else {
        candidates.push_back(entry.child_cl_addr << offset_bits);
        entry_issued_prefetches[idx] += 1;
        reason_predict_issued++;
      }
    } else {
      reason_leaf_level_no_predict++;
    }

    return candidates;
  }

public:
  explicit TxChildPrefetcher(uint64_t _offset_bits) : offset_bits(_offset_bits)
  {
    if (auto e = champsim::EnvVar<unsigned long long>::get("PF_CHILD_TABLE_SIZE")) {
      std::size_t value = static_cast<std::size_t>(*e);
      table_size = (value >= 1) ? value : 256;
      if (value < 1)
        std::cerr << "PF_CHILD_TABLE_SIZE must be >= 1, using 256" << std::endl;
    } else {
      table_size = 256;
    }

    if (auto e = champsim::EnvVar<unsigned long long>::get("PF_CHILD_PENDING_SIZE")) {
      std::size_t value = static_cast<std::size_t>(*e);
      pending_size = (value >= 1) ? value : 64;
      if (value < 1)
        std::cerr << "PF_CHILD_PENDING_SIZE must be >= 1, using 64" << std::endl;
    } else {
      pending_size = 64;
    }

    if (auto e = champsim::EnvVar<int>::get("PF_CHILD_CONF_THRESHOLD")) {
      int value = *e;
      if (value < 0 || value > 3) {
        std::cerr << "PF_CHILD_CONF_THRESHOLD must be 0-3, using default 2" << std::endl;
        value = 2;
      }
      conf_threshold = static_cast<uint8_t>(value);
    } else {
      conf_threshold = 2;
    }

    if (auto e = champsim::EnvVar<int>::get("PF_CHILD_TRAIN_ON_HIT"))
      train_on_hit = (*e != 0);
    else
      train_on_hit = true;

    if (auto e = champsim::EnvVar<int>::get("PF_CHILD_ISSUE_ON_HIT"))
      issue_on_hit = (*e != 0);
    else
      issue_on_hit = false;

    if (auto e = champsim::EnvVar<int>::get("PF_MSHR_GATE_PCT")) {
      int value = *e;
      mshr_gate_pct = (value > 0 && value <= 100) ? static_cast<uint32_t>(value) : 50u;
    } else {
      mshr_gate_pct = 50;
    }

    table.resize(table_size);
    pending.resize(pending_size);
    entry_birth_tick.resize(table_size, 0);
    entry_issued_prefetches.resize(table_size, 0);

    std::cout << "PF ChildPrefetcher: table_size=" << table_size
              << " pending_size=" << pending_size
              << " conf_threshold=" << static_cast<int>(conf_threshold)
              << " train_on_hit=" << (train_on_hit ? 1 : 0)
              << " issue_on_hit=" << (issue_on_hit ? 1 : 0)
              << " mshr_gate_pct=" << mshr_gate_pct << std::endl;
  }

  uint32_t get_mshr_gate_pct() const { return mshr_gate_pct; }
  bool should_issue_on_hit() const { return issue_on_hit; }
  void notify_mshr_gate_blocked() { reason_issue_mshr_blocked++; }
  void notify_enqueue_failed() { reason_issue_enqueue_failed++; }
  void notify_useful() {}
  void notify_useless() {}

  void observe_access(uint64_t address, std::size_t translation_level, uint64_t ip, uint64_t translated_vpn)
  {
    if (!train_on_hit)
      return;
    process_access(address, translation_level, ip, translated_vpn, false);
  }

  std::vector<uint64_t> get_prefetch_candidates(uint64_t address, std::size_t translation_level, uint64_t ip, uint64_t translated_vpn)
  {
    return process_access(address, translation_level, ip, translated_vpn, true);
  }

  void print_stats() const
  {
    uint64_t live_entries = 0;
    uint64_t live_entries_with_issue = 0;
    for (std::size_t i = 0; i < table.size(); ++i) {
      if (!table[i].valid)
        continue;
      live_entries++;
      if (entry_issued_prefetches[i] > 0)
        live_entries_with_issue++;
    }

    const double avg_replaced_lifetime =
        (entry_replacements != 0) ? static_cast<double>(replaced_entry_lifetime_sum) / static_cast<double>(entry_replacements) : 0.0;

    std::cout << "PF CHILD ENTRY-LIFETIME "
              << "ALLOC:" << entry_allocations << " "
              << "REPL:" << entry_replacements << " "
              << "REPL_BEFORE_ISSUE:" << entry_replaced_before_issue << " "
              << "REPL_AFTER_ISSUE:" << entry_survived_to_issue << " "
              << "AVG_REPL_LIFETIME_TICKS:" << avg_replaced_lifetime << " "
              << "LIVE:" << live_entries << " "
              << "LIVE_WITH_ISSUE:" << live_entries_with_issue
              << std::endl;

    std::cout << "PF CHILD DROP-REASONS "
              << "LEVEL0_SKIP:" << reason_level0_skipped << " "
              << "NO_PENDING_PARENT:" << reason_no_pending_parent << " "
              << "PENDING_OVERWRITE_COLLISION:" << reason_pending_overwrite_collision << " "
              << "TRAIN_REPLACE_MISMATCH:" << reason_training_replaced_mismatch << " "
              << "LEAF_NO_PREDICT:" << reason_leaf_level_no_predict << " "
              << "PRED_INVALID:" << reason_predict_entry_invalid << " "
              << "PRED_TAG_MISMATCH:" << reason_predict_tag_mismatch << " "
              << "PRED_CONF_BLOCKED:" << reason_predict_conf_blocked << " "
              << "PRED_ISSUED:" << reason_predict_issued << " "
              << "ISSUE_MSHR_BLOCKED:" << reason_issue_mshr_blocked << " "
              << "ISSUE_ENQUEUE_FAILED:" << reason_issue_enqueue_failed
              << std::endl;
  }
};

std::map<CACHE*, TxChildPrefetcher*> child_pfs;
} // namespace

void CACHE::prefetcher_initialize()
{
  std::cout << NAME << " TX-Child PTE prefetcher" << std::endl;
  child_pfs[this] = new TxChildPrefetcher(OFFSET_BITS);
}

void CACHE::prefetcher_cycle_operate() {}

uint32_t CACHE::prefetcher_cache_operate(uint64_t addr, uint64_t ip, uint8_t cache_hit, uint8_t type, uint32_t metadata_in)
{
  // Only activate on TRANSLATION-type accesses (PTW probes)
  if (static_cast<access_type>(type) != access_type::TRANSLATION)
    return metadata_in;

  auto* pf = child_pfs[this];

  // Extract translation_level from lower 8 bits of metadata
  // (encoded by ptw.cc step_translation)
  const std::size_t translation_level = static_cast<std::size_t>(metadata_in & 0xFF);

  // Use the physical page number of the PTE address as a proxy for the VPN.
  // This gives per-PT-page discrimination for the pending table.
  const uint64_t translated_vpn = addr >> LOG2_PAGE_SIZE;

  if (cache_hit) {
    if (pf->should_issue_on_hit()) {
      if (get_occupancy(0, addr) * 100 >= get_size(0, addr) * pf->get_mshr_gate_pct()) {
        pf->notify_mshr_gate_blocked();
        pf->observe_access(addr, translation_level, ip, translated_vpn);
        return metadata_in;
      }

      auto candidates = pf->get_prefetch_candidates(addr, translation_level, ip, translated_vpn);
      for (auto pf_addr : candidates) {
        const std::size_t child_level = (translation_level > 0) ? translation_level - 1 : 0;
        if (!prefetch_pte_line(pf_addr, /*fill_this_level=*/true, child_level))
          pf->notify_enqueue_failed();
      }
    } else {
      // Training path: observe access without predicting (respects PF_CHILD_TRAIN_ON_HIT)
      pf->observe_access(addr, translation_level, ip, translated_vpn);
    }
  } else {
    // MSHR gate: back off if MSHR is too full
    if (get_occupancy(0, addr) * 100 >= get_size(0, addr) * pf->get_mshr_gate_pct()) {
      pf->notify_mshr_gate_blocked();
      return metadata_in;
    }

    // Prediction + training path
    auto candidates = pf->get_prefetch_candidates(addr, translation_level, ip, translated_vpn);
    for (auto pf_addr : candidates) {
      // Child PTEs are one level deeper; prefetch them at the same level
      const std::size_t child_level = (translation_level > 0) ? translation_level - 1 : 0;
      if (!prefetch_pte_line(pf_addr, /*fill_this_level=*/true, child_level))
        pf->notify_enqueue_failed();
    }
  }

  return metadata_in;
}

uint32_t CACHE::prefetcher_cache_fill(uint64_t addr, uint32_t set, uint32_t way, uint8_t prefetch, uint64_t evicted_addr, uint32_t metadata_in)
{
  return metadata_in;
}

void CACHE::prefetcher_final_stats()
{
  auto it = child_pfs.find(this);
  if (it != child_pfs.end())
    it->second->print_stats();
}
