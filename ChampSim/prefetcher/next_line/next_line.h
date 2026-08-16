#ifndef NEXT_LINE_H
#define NEXT_LINE_H

#include <cstdint>
#include <vector>
#include "champsim_constants.h"

class NextLinePrefetcher
{
public:
  NextLinePrefetcher() {}

  // Return next-line candidate(s) for a given address.
  // Signature mirrors other prefetcher helpers used in the codebase.
  std::vector<uint64_t> get_prefetch_candidates(uint64_t address, std::size_t /*translation_level*/, uint64_t /*ip*/, uint64_t /*translated_vpn*/)
  {
    std::vector<uint64_t> candidates;
    const uint64_t pf_addr = address + (1ULL << LOG2_BLOCK_SIZE);
    candidates.push_back(pf_addr);
    return candidates;
  }

  void print_stats() const {}
};

#endif // NEXT_LINE_H
