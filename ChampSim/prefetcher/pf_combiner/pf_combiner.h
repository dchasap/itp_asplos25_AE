#ifndef PF_COMBINER_H
#define PF_COMBINER_H

#include <cstdint>
#include <cstddef>
#include <vector>

#include "champsim_constants.h"

class PFCombiner
{
public:
  explicit PFCombiner(uint64_t _offset_bits);

  // Process access; return vector of candidate addresses (if any)
  std::vector<uint64_t> process_translation(uint64_t address, std::size_t translation_level, uint64_t translated_vpn);
  std::vector<uint64_t> process_regular_access(uint64_t address, uint64_t ip, uint8_t type);

  void print_stats() const;

private:
  uint64_t offset_bits;
};

#endif // PF_COMBINER_H
