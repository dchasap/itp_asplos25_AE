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

#ifndef CHAMPSIM_H
#define CHAMPSIM_H

#include <cstdint>
#include <exception>
#include <iostream>
#include <sstream>

#define MULTIPLE_PAGE_SIZE
#define ENABLE_EXTRA_CPU_STATS
#define ENABLE_EXTRA_CACHE_STATS
#define ENABLE_PAGE_CROSSING_STATS
#define ENABLE_PTW_STATS
#define FORCE_HIT
#define TRANSLATION_EXCLUSIVE_CACHE
//#define TX_SPLIT_CACHE
//#define SPLIT_STLB
//#define XDIP_REPLACEMENT_POLICY
#define PTP_REPLACEMENT_POLICY
#define ENABLE_TRANSLATION_AWARE_REPLACEMENT
#define ENABLE_FDIP
//#define _CACHE_ "L1D"


#define TRACK_BRANCH_HISTORY // needed for chirp

namespace champsim
{
struct deadlock : public std::exception {
  const uint32_t which;
  explicit deadlock(uint32_t cpu) : which(cpu) {}
};

#ifdef DEBUG_PRINT
constexpr bool debug_print = true;
#else
constexpr bool debug_print = false;
#endif

class DebugLogger {
  
  private:
    bool enabled;
    std::ostringstream buffer;

  public:
    
    DebugLogger() { enabled = false; }

    void enable() { enabled = true; }
    void disable() { enabled = false; }

    // Overload << to collect the message
    template<typename T>
    DebugLogger& operator<<(const T& msg) {
        if (enabled) {
            buffer << msg;
        }
        return *this;
    }

    // Handle std::endl and other manipulators
    DebugLogger& operator<<(std::ostream& (*manip)(std::ostream&)) {
        if (enabled) {
            manip(buffer);
            // Flush the buffer to cout when endl is received
            std::cout << buffer.str();
            buffer.str(""); // Clear buffer
        }
        return *this;
    }
  };

} // namespace champsim

#endif
