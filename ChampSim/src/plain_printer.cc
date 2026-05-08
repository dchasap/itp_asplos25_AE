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

#include <iomanip>
#include <iostream>
#include <numeric>
#include <sstream>
#include <utility>
#include <vector>

#include "stats_printer.h"

void champsim::plain_printer::print(O3_CPU::stats_type stats)
{
  constexpr std::array<std::pair<std::string_view, std::size_t>, 6> types{
      {std::pair{"BRANCH_DIRECT_JUMP", BRANCH_DIRECT_JUMP}, std::pair{"BRANCH_INDIRECT", BRANCH_INDIRECT}, std::pair{"BRANCH_CONDITIONAL", BRANCH_CONDITIONAL},
       std::pair{"BRANCH_DIRECT_CALL", BRANCH_DIRECT_CALL}, std::pair{"BRANCH_INDIRECT_CALL", BRANCH_INDIRECT_CALL},
       std::pair{"BRANCH_RETURN", BRANCH_RETURN}}};

  auto total_branch = std::ceil(
      std::accumulate(std::begin(types), std::end(types), 0ll, [tbt = stats.total_branch_types](auto acc, auto next) { return acc + tbt[next.second]; }));
  auto total_mispredictions = std::ceil(
      std::accumulate(std::begin(types), std::end(types), 0ll, [btm = stats.branch_type_misses](auto acc, auto next) { return acc + btm[next.second]; }));

  stream << std::endl;
  stream << stats.name << " cumulative IPC: " << std::ceil(stats.instrs()) / std::ceil(stats.cycles()) << " instructions: " << stats.instrs()
         << " cycles: " << stats.cycles() << std::endl;
  stream << stats.name << " Branch Prediction Accuracy: " << (100.0 * std::ceil(total_branch - total_mispredictions)) / total_branch
         << "% MPKI: " << (1000.0 * total_mispredictions) / std::ceil(stats.instrs());
  stream << " Average ROB Occupancy at Mispredict: " << std::ceil(stats.total_rob_occupancy_at_branch_mispredict) / total_mispredictions << std::endl;

  std::vector<double> mpkis;
  std::transform(std::begin(stats.branch_type_misses), std::end(stats.branch_type_misses), std::back_inserter(mpkis),
                 [instrs = stats.instrs()](auto x) { return 1000.0 * std::ceil(x) / std::ceil(instrs); });

  stream << "Branch type MPKI" << std::endl;
  for (auto [str, idx] : types)
    stream << str << ": " << mpkis[idx] << std::endl;
  stream << std::endl;

#if defined MULTIPLE_PAGE_SIZE
	stream << "Instructions large pages: " << stats.total_instr_large_pages << std::endl;
	stream << "Instructions small pages: " << stats.total_instr_small_pages << std::endl;
	stream << "Large page distribution for instructions: " << ((100.0 * stats.total_instr_large_pages) / (stats.total_instr_large_pages + stats.total_instr_small_pages)) << "%" << std::endl;
	stream << std::endl;

	stream << "Data large pages: " << stats.total_data_large_pages << std::endl;
	stream << "Data small pages: " << stats.total_data_small_pages << std::endl;
	stream << "Large page distribution for data: " << ((100.0 * stats.total_data_large_pages) / (stats.total_data_large_pages + stats.total_data_small_pages)) << "%" << std::endl;
	stream << std::endl;

#endif
}

void champsim::plain_printer::print(CACHE::stats_type stats)
{
  constexpr std::array<std::pair<std::string_view, std::size_t>, 5> types{
      {std::pair{"LOAD", LOAD}, std::pair{"RFO", RFO}, std::pair{"PREFETCH", PREFETCH}, std::pair{"WRITE", WRITE}, std::pair{"TRANSLATION", TRANSLATION}}};

  for (std::size_t cpu = 0; cpu < NUM_CPUS; ++cpu) {
    uint64_t TOTAL_HIT = 0, TOTAL_MISS = 0;
    for (const auto& type : types) {
      TOTAL_HIT += stats.hits.at(type.second).at(cpu);
      TOTAL_MISS += stats.misses.at(type.second).at(cpu);
    }

#if defined ENABLE_EXTRA_CACHE_STATS
    uint64_t TOTAL_iHIT = 0, TOTAL_iMISS = 0, TOTAL_dHIT = 0, TOTAL_dMISS = 0,
						 TOTAL_itHIT = 0, TOTAL_itMISS = 0, TOTAL_dtHIT = 0, TOTAL_dtMISS = 0;
    for (const auto& type : types) {
      TOTAL_iHIT += stats.ihits.at(type.second).at(cpu);
      TOTAL_iMISS += stats.imisses.at(type.second).at(cpu);
      TOTAL_dHIT += stats.dhits.at(type.second).at(cpu);
      TOTAL_dMISS += stats.dmisses.at(type.second).at(cpu);
      TOTAL_itHIT += stats.ithits.at(type.second).at(cpu);
      TOTAL_itMISS += stats.itmisses.at(type.second).at(cpu);
      TOTAL_dtHIT += stats.dthits.at(type.second).at(cpu);
      TOTAL_dtMISS += stats.dtmisses.at(type.second).at(cpu);
    }
#endif

    stream << stats.name << " TOTAL       ";
    stream << "ACCESS: " << std::setw(10) << TOTAL_HIT + TOTAL_MISS << "  ";
    stream << "HIT: " << std::setw(10) << TOTAL_HIT << "  ";
    stream << "MISS: " << std::setw(10) << TOTAL_MISS;
#if defined ENABLE_EXTRA_CACHE_STATS
		stream << "  ";
    stream << "iACCESS: " << std::setw(10) << TOTAL_iHIT + TOTAL_iMISS << "  ";
    stream << "iHIT: " << std::setw(10) << TOTAL_iHIT << "  ";
    stream << "iMISS: " << std::setw(10) << TOTAL_iMISS << "  ";
    stream << "dACCESS: " << std::setw(10) << TOTAL_dHIT + TOTAL_dMISS << "  ";
    stream << "dHIT: " << std::setw(10) << TOTAL_dHIT << "  ";
    stream << "dMISS: " << std::setw(10) << TOTAL_dMISS << "  ";
    stream << "itACCESS: " << std::setw(10) << TOTAL_itHIT + TOTAL_itMISS << "  ";
    stream << "itHIT: " << std::setw(10) << TOTAL_itHIT << "  ";
    stream << "itMISS: " << std::setw(10) << TOTAL_itMISS << "  ";
    stream << "dtACCESS: " << std::setw(10) << TOTAL_dtHIT + TOTAL_dtMISS << "  ";
    stream << "dtHIT: " << std::setw(10) << TOTAL_dtHIT << "  ";
    stream << "dtMISS: " << std::setw(10) << TOTAL_dtMISS;
#endif
		stream << std::endl;

    for (const auto& type : types) {
      std::ostringstream name;
      name << std::left << std::setw(12) << type.first;
      stream << stats.name << " " << name.str() << " ";
      stream << "ACCESS: " << std::setw(10) << stats.hits[type.second][cpu] + stats.misses[type.second][cpu] << "  ";
      stream << "HIT: " << std::setw(10) << stats.hits[type.second][cpu] << "  ";
      stream << "MISS: " << std::setw(10) << stats.misses[type.second][cpu];
#if defined ENABLE_EXTRA_CACHE_STATS
			stream << "  ";
      stream << "iACCESS: " << std::setw(10) << stats.ihits[type.second][cpu] + stats.imisses[type.second][cpu] << "  ";
      stream << "iHIT: " << std::setw(10) << stats.ihits[type.second][cpu] << "  ";
      stream << "iMISS: " << std::setw(10) << stats.imisses[type.second][cpu] << "  ";
      stream << "dACCESS: " << std::setw(10) << stats.dhits[type.second][cpu] + stats.dmisses[type.second][cpu] << "  ";
      stream << "dHIT: " << std::setw(10) << stats.dhits[type.second][cpu] << "  ";
      stream << "dMISS: " << std::setw(10) << stats.dmisses[type.second][cpu] << "  ";
      stream << "itACCESS: " << std::setw(10) << stats.ithits[type.second][cpu] + stats.itmisses[type.second][cpu] << "  ";
      stream << "itHIT: " << std::setw(10) << stats.ithits[type.second][cpu] << "  ";
      stream << "itMISS: " << std::setw(10) << stats.itmisses[type.second][cpu] << "  ";
      stream << "dtACCESS: " << std::setw(10) << stats.dthits[type.second][cpu] + stats.dtmisses[type.second][cpu] << "  ";
      stream << "dtHIT: " << std::setw(10) << stats.dthits[type.second][cpu] << "  ";
      stream << "dtMISS: " << std::setw(10) << stats.dtmisses[type.second][cpu];
#endif
			stream << std::endl;
    }

    stream << stats.name << " PREFETCH  ";
    stream << "REQUESTED: " << std::setw(10) << stats.pf_requested << "  ";
    stream << "ISSUED: " << std::setw(10) << stats.pf_issued << "  ";
    stream << "CROSSED: " << std::setw(10) << stats.pf_crossed << "  ";
    stream << "USEFUL: " << std::setw(10) << stats.pf_useful << "  ";
    stream << "USELESS: " << std::setw(10) << stats.pf_useless << std::endl;

#if defined ENABLE_EXTRA_CACHE_STATS
    stream << stats.name << " MAX OCCUPANCY: " << stats.max_cache_occupancy << std::endl;
    stream << stats.name << " AVERAGE iMISS LATENCY: " << std::ceil(stats.total_imiss_latency) / std::ceil(TOTAL_MISS) << " cycles" << std::endl;
    stream << stats.name << " AVERAGE dMISS LATENCY: " << std::ceil(stats.total_dmiss_latency) / std::ceil(TOTAL_MISS) << " cycles" << std::endl;
    stream << stats.name << " AVERAGE itMISS LATENCY: " << std::ceil(stats.total_itmiss_latency) / std::ceil(TOTAL_MISS) << " cycles" << std::endl;
    stream << stats.name << " AVERAGE dtMISS LATENCY: " << std::ceil(stats.total_dtmiss_latency) / std::ceil(TOTAL_MISS) << " cycles" << std::endl;
#endif

#if defined ENABLE_PAGE_CROSSING_STATS
	stream << stats.name << " PAGE CROSSINGS (TLB HIT):" << std::setw(10) << stats.pf_crossing_pages_tlb_hit << std::endl;
	stream << stats.name << " PAGE CROSSINGS (TLB MISS):" << std::setw(10) << stats.pf_crossing_pages_tlb_miss << std::endl;
#endif

    stream << stats.name << " AVERAGE MISS LATENCY: " << std::ceil(stats.total_miss_latency) / std::ceil(TOTAL_MISS) << " cycles" << std::endl;

    //stream << " AVERAGE MISS LATENCY: " << (stats.total_miss_latency)/TOTAL_MISS << " cycles " << stats.total_miss_latency << "/" << TOTAL_MISS<< std::endl;
  }
}

void champsim::plain_printer::print(DRAM_CHANNEL::stats_type stats)
{
  stream << stats.name << std::endl;
  stream << " RQ ROW_BUFFER_HIT: " << std::setw(10) << stats.RQ_ROW_BUFFER_HIT << std::endl;
  stream << "  ROW_BUFFER_MISS: " << std::setw(10) << stats.RQ_ROW_BUFFER_MISS << std::endl;
  stream << " AVG DBUS CONGESTED CYCLE: ";
  if (stats.dbus_count_congested > 0)
    stream << std::setw(10) << std::ceil(stats.dbus_cycle_congested) / std::ceil(stats.dbus_count_congested);
  else
    stream << "-";
  stream << std::endl;
  stream << " WQ ROW_BUFFER_HIT: " << std::setw(10) << stats.WQ_ROW_BUFFER_HIT << std::endl;
  stream << "  ROW_BUFFER_MISS: " << std::setw(10) << stats.WQ_ROW_BUFFER_MISS;
  stream << "  FULL: " << std::setw(10) << stats.WQ_FULL << std::endl;
  stream << std::endl;
}

void champsim::plain_printer::print(champsim::phase_stats& stats)
{
  stream << "=== " << stats.name << " ===" << std::endl;

  int i = 0;
  for (auto tn : stats.trace_names)
    stream << "CPU " << i++ << " runs " << tn << std::endl;

  if (NUM_CPUS > 1) {
    stream << std::endl;
    stream << "Total Simulation Statistics (not including warmup)" << std::endl;

    for (const auto& stat : stats.sim_cpu_stats)
      print(stat);

    for (const auto& stat : stats.sim_cache_stats)
      print(stat);
  }

  stream << std::endl;
  stream << "Region of Interest Statistics" << std::endl;

  for (const auto& stat : stats.roi_cpu_stats)
    print(stat);

  for (const auto& stat : stats.roi_cache_stats)
    print(stat);

#if defined ENABLE_PTW_STATS
	stream << std::endl;
	for (const auto& stat : stats.roi_ptw_stats)
		print(stat);
#endif

  stream << std::endl;
  stream << "DRAM Statistics" << std::endl;
  for (const auto& stat : stats.roi_dram_stats)
    print(stat);
}

void champsim::plain_printer::print(std::vector<phase_stats>& stats)
{
  for (auto p : stats)
    print(p);
}

#if defined ENABLE_PTW_STATS
void champsim::plain_printer::print(PageTableWalker::stats_type stats) 
{
  for (std::size_t cpu = 0; cpu < NUM_CPUS; ++cpu) {

    stream << stats.name << " TOTAL       ";;
    stream << "ACCESS: " << std::setw(10) << stats.total_reads << "  ";
		stream << std::endl;

    stream << stats.name << " AVERAGE LATENCY: " << std::ceil(stats.total_miss_latency) / std::ceil(stats.total_reads) << " cycles" << std::endl;
    stream << stats.name << " TOTAL LATENCY: " << stats.total_miss_latency << " cycles" << std::endl;
  }

}
#endif

