#ifndef CHILD_IDEAL_PF_H
#define CHILD_IDEAL_PF_H

#include <cstddef>
#include <cstdint>
#include <iostream>
#include <map>
#include <unordered_set>
#include <unordered_map>
#include <utility>
#include <vector>

#include "champsim_constants.h"
#include "env_var.h"

class ChildIdealPrefetcher
{
private:
  using DiscoveryKey = std::pair<uint64_t, std::size_t>; // (vpn, level)
  std::map<DiscoveryKey, uint64_t> table_a;
  using PredictionKey = uint64_t;
  std::map<PredictionKey, uint64_t> table_b;

  bool train_on_hit;
  bool issue_on_hit;
  uint32_t mshr_gate_pct;
  uint64_t offset_bits;

  // Statistics
  uint64_t access_count = 0;
  uint64_t access_tick = 0;
  uint64_t prediction_lookups = 0;
  uint64_t prediction_hits = 0;
  uint64_t prediction_misses = 0;
  uint64_t training_updates = 0;
  uint64_t discovery_updates = 0;
  uint64_t prefetches_issued = 0;
  uint64_t mshr_gate_blocked = 0;
  uint64_t total_ptes_observed = 0;
  uint64_t total_unique_ptes_observed = 0;
  uint64_t total_unique_parents_observed = 0;
  uint64_t total_unique_children_observed = 0;
  uint64_t total_unique_parent_child_pairs_observed = 0;
  std::unordered_set<uint64_t> unique_ptes;
  std::unordered_set<uint64_t> unique_parents;
  std::unordered_set<uint64_t> unique_children;

  struct PairHash {
    size_t operator()(const std::pair<uint64_t, uint64_t>& p) const noexcept {
      return std::hash<uint64_t>{}(p.first) ^ (std::hash<uint64_t>{}(p.second) << 1);
    }
  };
  struct PairEq {
    bool operator()(const std::pair<uint64_t, uint64_t>& a, const std::pair<uint64_t, uint64_t>& b) const noexcept {
      return a.first == b.first && a.second == b.second;
    }
  };
  std::unordered_set<std::pair<uint64_t, uint64_t>, PairHash, PairEq> unique_parent_child_pairs;
  std::unordered_set<std::pair<uint64_t, uint64_t>, PairHash, PairEq> unique_parent_child_pairs_with_replacement;

  uint64_t reason_no_pending_parent = 0;
  uint64_t reason_pending_overwrite_collision = 0;
  uint64_t reason_training_replaced_mismatch = 0;
  uint64_t reason_leaf_level_no_predict = 0;
  uint64_t reason_predict_entry_invalid = 0;
  uint64_t reason_predict_issued = 0;
  uint64_t reason_issue_mshr_blocked = 0;
  uint64_t reason_issue_enqueue_failed = 0;

  // Replacement / lifetime statistics
  uint64_t repl_total = 0;
  uint64_t repl_before_issue = 0;
  uint64_t repl_after_issue = 0;
  uint64_t repl_lifetime_sum = 0; // sum of lifetimes in cycles

  // Per-entry metadata: allocation cycle and issued flag per parent key
  std::map<PredictionKey, uint64_t> table_b_alloc_cycle;
  std::map<PredictionKey, bool> table_b_issued_flag;
  // Reverse map child_addr -> parent prediction key (for quick lookup on issue)
  std::unordered_map<uint64_t, PredictionKey> child_to_parent;

public:
  explicit ChildIdealPrefetcher(uint64_t _offset_bits) : offset_bits(_offset_bits)
  {
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

    std::cout << "PF ChildIdealPrefetcher: "
              << "train_on_hit=" << (train_on_hit ? 1 : 0)
              << " issue_on_hit=" << (issue_on_hit ? 1 : 0)
              << " mshr_gate_pct=" << mshr_gate_pct << std::endl;
  }

  uint32_t get_mshr_gate_pct() const { return mshr_gate_pct; }
  bool should_issue_on_hit() const { return issue_on_hit; }
  bool should_train_on_hit() const { return train_on_hit; }
  void notify_mshr_gate_blocked() { mshr_gate_blocked++; reason_issue_mshr_blocked++; }
  void notify_enqueue_failed() { reason_issue_enqueue_failed++; }

  std::vector<uint64_t> process_access(uint64_t address, std::size_t translation_level, uint64_t translated_vpn)
  {
    access_count++;
    access_tick++;
    total_ptes_observed++;
    unique_ptes.insert(address);

    std::vector<uint64_t> candidates;
    DiscoveryKey curr_discovery_key = {translated_vpn, translation_level};
    PredictionKey curr_prediction_key = address; // parent_full_addr only

    DiscoveryKey parent_discovery_key = {translated_vpn, translation_level + 1};
    auto parent_it = table_a.find(parent_discovery_key);
    if (parent_it != table_a.end()) {
      uint64_t parent_full_addr = parent_it->second;
      PredictionKey parent_prediction_key = parent_full_addr;
      uint64_t child_full_addr = address;
      auto tb_it = table_b.find(parent_prediction_key);
      if (tb_it == table_b.end()) {
        table_b[parent_prediction_key] = child_full_addr;
        // record allocation metadata (use access_tick)
        table_b_alloc_cycle[parent_prediction_key] = access_tick;
        table_b_issued_flag[parent_prediction_key] = false;
        child_to_parent[child_full_addr] = parent_prediction_key;
        training_updates++;
        unique_children.insert(child_full_addr);
        unique_parent_child_pairs.insert({parent_full_addr, child_full_addr});
        unique_parent_child_pairs_with_replacement.insert({parent_full_addr, child_full_addr});
      } else {
        if (tb_it->second == 0) {
          table_b[parent_prediction_key] = child_full_addr;
          table_b_alloc_cycle[parent_prediction_key] = access_tick;
          table_b_issued_flag[parent_prediction_key] = false;
          child_to_parent[child_full_addr] = parent_prediction_key;
          training_updates++;
          unique_children.insert(child_full_addr);
        } else {
          uint64_t stored_full = tb_it->second;
          if (stored_full != child_full_addr) {
            // replacement: update replacement stats using allocation cycle
            uint64_t alloc = 0;
            auto alloc_it = table_b_alloc_cycle.find(parent_prediction_key);
            if (alloc_it != table_b_alloc_cycle.end()) alloc = alloc_it->second;
            uint64_t lifetime = (access_tick > alloc) ? (access_tick - alloc) : 0;
            repl_total++;
            repl_lifetime_sum += lifetime;
            // check if the replaced entry was issued
            bool was_issued = false;
            auto issued_it = table_b_issued_flag.find(parent_prediction_key);
            if (issued_it != table_b_issued_flag.end()) was_issued = issued_it->second;
            if (was_issued) repl_after_issue++; else repl_before_issue++;

            // remove old child->parent mapping
            child_to_parent.erase(stored_full);

            // perform replacement
            table_b[parent_prediction_key] = child_full_addr;
            table_b_alloc_cycle[parent_prediction_key] = access_tick;
            table_b_issued_flag[parent_prediction_key] = false;
            child_to_parent[child_full_addr] = parent_prediction_key;
            reason_training_replaced_mismatch++;
            unique_parent_child_pairs_with_replacement.insert({parent_full_addr, child_full_addr});
          }
        }
      }
    }

    if (translation_level == 0) {
      reason_leaf_level_no_predict++;
      return candidates;
    }

    auto discovery_it = table_a.find(curr_discovery_key);
    if (discovery_it != table_a.end() && discovery_it->second == address) {
      prediction_lookups++;
      auto pred_it = table_b.find(curr_prediction_key);

      if (pred_it != table_b.end() && pred_it->second != 0) {
        candidates.push_back(pred_it->second);
        prediction_hits++;
        reason_predict_issued++;
        unique_parents.insert(address);
      } else {
        prediction_misses++;
        reason_predict_entry_invalid++;
      }
    } else {
      if (parent_it == table_a.end()) {
        reason_no_pending_parent++;
      }
    }

    table_a[curr_discovery_key] = address;
    auto find_me = table_b.find(curr_prediction_key);
    if (find_me == table_b.end()) {
      table_b[curr_prediction_key] = 0;
    }
    discovery_updates++;

    return candidates;
  }

  std::vector<uint64_t> get_prefetch_candidates(uint64_t address, std::size_t translation_level, uint64_t translated_vpn)
  {
    return process_access(address, translation_level, translated_vpn);
  }

  void observe_access(uint64_t address, std::size_t translation_level, uint64_t translated_vpn)
  {
    process_access(address, translation_level, translated_vpn);
  }

  void record_prefetch_issued(uint64_t child_addr) {
    prefetches_issued++;
    // mark parent entry as having been issued (if we can find it)
    auto it = child_to_parent.find(child_addr);
    if (it != child_to_parent.end()) {
      auto p = it->second;
      table_b_issued_flag[p] = true;
    }
  }

  void print_stats() const
  {
    std::cout << "PF TABLES "
              << "TABLE_A_SIZE:" << table_a.size() << " "
              << "TABLE_B_SIZE:" << table_b.size() << std::endl;

    std::cout << "PF OPERATIONS "
              << "ACCESS_COUNT:" << access_count << " "
              << "DISCOVERY_UPDATES:" << discovery_updates << " "
              << "TRAINING_UPDATES:" << training_updates << std::endl;

    std::cout << "PF PREDICTIONS "
              << "LOOKUPS:" << prediction_lookups << " "
              << "HITS:" << prediction_hits << " "
              << "MISSES:" << prediction_misses << " "
              << "HIT_RATE:" << (prediction_lookups > 0 ? (100.0 * prediction_hits / prediction_lookups) : 0.0) << "%" << std::endl;

    std::cout << "PF PREFETCH "
              << "ISSUED:" << prefetches_issued << " "
              << "MSHR_BLOCKED:" << mshr_gate_blocked << std::endl;

    uint64_t live_entries = table_b.size();
    uint64_t live_entries_with_issue = prefetches_issued;

    double avg_repl_lifetime = (repl_total > 0) ? (static_cast<double>(repl_lifetime_sum) / repl_total) : 0.0;
    std::cout << "PF ENTRY-LIFETIME "
              << "ALLOC:" << table_b.size() << " "
              << "REPL:" << repl_total << " "
              << "REPL_BEFORE_ISSUE:" << repl_before_issue << " "
              << "REPL_AFTER_ISSUE:" << repl_after_issue << " "
              << "AVG_REPL_LIFETIME_TICKS:" << avg_repl_lifetime << " "
              << "LIVE:" << live_entries << " "
              << "LIVE_WITH_ISSUE:" << live_entries_with_issue
              << std::endl;

    std::cout << "PF DROP-REASONS "
              << "NO_PENDING_PARENT:" << reason_no_pending_parent << " "
              << "PENDING_OVERWRITE_COLLISION:" << reason_pending_overwrite_collision << " "
              << "TRAIN_REPLACE_MISMATCH:" << reason_training_replaced_mismatch << " "
              << "LEAF_NO_PREDICT:" << reason_leaf_level_no_predict << " "
              << "PRED_INVALID:" << reason_predict_entry_invalid << " "
              << "PRED_ISSUED:" << reason_predict_issued << " "
              << "ISSUE_MSHR_BLOCKED:" << reason_issue_mshr_blocked << " "
              << "ISSUE_ENQUEUE_FAILED:" << reason_issue_enqueue_failed
              << std::endl;
    // Diagnostic: count placeholder/zero entries in table_b and keys not present in unique_ptes
    size_t zero_entries = 0;
    size_t keys_not_in_unique = 0;
    std::vector<uint64_t> sample_missing_keys;
    for (const auto &kv : table_b) {
      if (kv.second == 0) ++zero_entries;
      if (unique_ptes.find(kv.first) == unique_ptes.end()) {
        ++keys_not_in_unique;
        if (sample_missing_keys.size() < 10) sample_missing_keys.push_back(kv.first);
      }
    }
    std::cout << "PF TABLES DIAGNOSTIC "
              << "ZERO_ENTRIES:" << zero_entries << " "
              << "KEYS_NOT_IN_UNIQUE_PTES:" << keys_not_in_unique << std::endl;
    if (!sample_missing_keys.empty()) {
      std::cout << "PF SAMPLE_KEYS_NOT_IN_UNIQUE:";
      for (auto k : sample_missing_keys) std::cout << k << ",";
      std::cout << std::endl;
    }

    std::cout << "PF UNIQUE COUNTS "
              << "TOTAL_PTES_OBSERVED:" << total_ptes_observed << " "
              << "TOTAL_UNIQUE_PTES_OBSERVED:" << unique_ptes.size() << " "
              << "TOTAL_UNIQUE_PARENTS_OBSERVED:" << unique_parents.size() << " "
              << "TOTAL_UNIQUE_CHILDREN_OBSERVED:" << unique_children.size() << " "
              << "TOTAL_UNIQUE_PARENT_CHILD_PAIRS_OBSERVED:" << unique_parent_child_pairs.size() << " "
              << "TOTAL_UNIQUE_PARENT_CHILD_PAIRS_WITH_REPLACEMENT_OBSERVED:" << unique_parent_child_pairs_with_replacement.size()
              << std::endl;
  }
};

#endif // CHILD_IDEAL_PF_H
