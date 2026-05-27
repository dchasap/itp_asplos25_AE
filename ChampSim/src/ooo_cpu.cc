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

#include "ooo_cpu.h"

#include <algorithm>
#include <cmath>
#include <iterator>
#include <numeric>
#include <utility>
#include <vector>
#include <sys/stat.h>

#include "cache.h"
#include "champsim.h"
#include "instruction.h"


#if defined PTP_REPLACEMENT_POLICY
extern uint64_t RETIRED_INSTRS;
extern double STLB_MPKI;
#endif 

constexpr uint64_t DEADLOCK_CYCLE = 1000000;

std::tuple<uint64_t, uint64_t, uint64_t> elapsed_time();

#if defined TRACK_BRANCH_HISTORY

uint64_t global_path_history_MHRP = 0;
uint64_t global_path_history = 0;
uint64_t uncondIndHistory = 0;
uint64_t condHistory = 0;
uint64_t uncondIndHistory_old = 0;
uint64_t condHistory_old = 0;

int folding_factor=2;
int glob_shifts_main = 4;
int globe_bits_mask_main = 3;

void update_history(uint64_t pc, uint64_t& hist) {
	hist <<= 8;
	uint64_t brh = hist;
	hist = (brh | ((pc >> 2) & ((1 << 8) - 1)));
}
#endif 

void update_path_history(uint64_t pc) {
	uint64_t gph;
	global_path_history <<= glob_shifts_main;
	gph = global_path_history;
	global_path_history = (gph | (((pc) & 7)));
	global_path_history_MHRP <<= glob_shifts_main;
	gph = global_path_history_MHRP;
	global_path_history_MHRP = (gph | (((pc >> folding_factor) & globe_bits_mask_main)));
}


void O3_CPU::operate()
{
  retire_rob();                    // retire
  complete_inflight_instruction(); // finalize execution
  execute_instruction();           // execute instructions
  schedule_instruction();          // schedule instructions
  handle_memory_return();          // finalize memory transactions
  operate_lsq();                   // execute memory transactions

  dispatch_instruction(); // dispatch
  decode_instruction();   // decode
  promote_to_decode();

  fetch_instruction(); // fetch
  check_dib();
  initialize_instruction();

  // heartbeat
  if (show_heartbeat && (num_retired >= next_print_instruction)) {
    auto [elapsed_hour, elapsed_minute, elapsed_second] = elapsed_time();

    auto heartbeat_instr{std::ceil(num_retired - last_heartbeat_instr)};
    auto heartbeat_cycle{std::ceil(current_cycle - last_heartbeat_cycle)};

    auto phase_instr{std::ceil(num_retired - begin_phase_instr)};
    auto phase_cycle{std::ceil(current_cycle - begin_phase_cycle)};

    std::cout << "Heartbeat CPU " << cpu << " instructions: " << num_retired << " cycles: " << current_cycle;
    std::cout << " heartbeat IPC: " << heartbeat_instr / heartbeat_cycle;
    std::cout << " cumulative IPC: " << phase_instr / phase_cycle;
    std::cout << " (Simulation time: " << elapsed_hour << " hr " << elapsed_minute << " min " << elapsed_second << " sec) " << std::endl;
    next_print_instruction += STAT_PRINTING_PERIOD;

    last_heartbeat_instr = num_retired;
    last_heartbeat_cycle = current_cycle;
  }

#if defined PTP_REPLACEMENT_POLICY
//	vmem->RETIRED_INSTRS = sim_stats.back().instrs();
	//RETIRED_INSTRS = sim_stats.back().instrs();
	RETIRED_INSTRS = sim_instr();
#endif
}

void O3_CPU::initialize()
{
  // BRANCH PREDICTOR & BTB
  impl_initialize_branch_predictor();
  impl_initialize_btb();

#if defined(MULTIPLE_PAGE_SIZE)
	// init random number generator
  srand((unsigned) time(NULL));

	if (getenv("INSTR_PAGE_SIZE_DIST")) {
		INSTR_PAGE_SIZE_DIST = std::stoi(getenv("INSTR_PAGE_SIZE_DIST"));
		std::cout << "Instruction page size distrubution: " << INSTR_PAGE_SIZE_DIST << std::endl;
	} else {
		INSTR_PAGE_SIZE_DIST = 0;
		std::cout << "Instruction page size distrubution: " << INSTR_PAGE_SIZE_DIST << std::endl;
	}

	if (getenv("INSTR_PAGE_DIST_FILENAME")) { 

		INSTR_PAGE_DIST_FILENAME = getenv("INSTR_PAGE_DIST_FILENAME");

		std::cout << "Loading instruction page size distribution from " << INSTR_PAGE_DIST_FILENAME << std::endl;
		std::ifstream instr_page_dist_file(INSTR_PAGE_DIST_FILENAME, std::ifstream::in);

		// check if exist to load it, elese create it
		struct stat sb;
 		if (stat(INSTR_PAGE_DIST_FILENAME.c_str(), &sb) != 0) {
		//if (!instr_page_dist_file) {
			std::cout << "\tFile not found!" << std::endl;
		} else {
			std::string line; 
			while (std::getline(instr_page_dist_file, line)) {
				//std::cout << line << std::endl;
				std::string _vpage = line.substr(0, line.find(":"));
				std::string _page_size = line.substr(line.find(":") + 1, line.size());
				//std::cout << "vpage(" << _vpage << "):page_size(" << _page_size << ")" << std::endl;
 				uint64_t vpage;
	   		std::istringstream _iss1(_vpage);
    		_iss1 >> vpage;
 				unsigned int page_size;
	   		std::istringstream _iss2(_page_size);
    		_iss2 >> page_size;
				code_page_sizes[vpage] = page_size; 
			}
			instr_page_dist_file.close();
		}
	} else {
		std::cerr << "ERROR: INSTR_PAGE_DIST_FILENAME not defined!" << std::endl;
		exit(1);
	}

	if (getenv("DATA_PAGE_SIZE_DIST")) {
		DATA_PAGE_SIZE_DIST = std::stoi(getenv("DATA_PAGE_SIZE_DIST"));
		std::cout << "Data page size distrubution: " << DATA_PAGE_SIZE_DIST << std::endl;
		//::TLB_STRESS_THRESHOLD = 0;
	} else {
		DATA_PAGE_SIZE_DIST = 0;
		std::cout << "Data page size distrubution: " << DATA_PAGE_SIZE_DIST << std::endl;
	}

	if (getenv("DATA_PAGE_DIST_FILENAME")) { 

		DATA_PAGE_DIST_FILENAME = getenv("DATA_PAGE_DIST_FILENAME");

		std::cout << "Loading data page size distribution from " << DATA_PAGE_DIST_FILENAME << std::endl;
		std::ifstream data_page_dist_file(DATA_PAGE_DIST_FILENAME, std::ifstream::in);

		// check if exist to load it, elese create it
		struct stat sb;
 		if (stat(DATA_PAGE_DIST_FILENAME.c_str(), &sb) != 0) {
		//if (!instr_page_dist_file) {
			std::cout << "\tFile not found!" << std::endl;
		} else {
			std::string line; 
			while (std::getline(data_page_dist_file, line)) {
				//std::cout << line << std::endl;
				std::string _vpage = line.substr(0, line.find(":"));
				std::string _page_size = line.substr(line.find(":") + 1, line.size());
				//std::cout << "vpage(" << _vpage << "):page_size(" << _page_size << ")" << std::endl;
 				uint64_t vpage;
	   		std::istringstream _iss1(_vpage);
    		_iss1 >> vpage;
 				unsigned int page_size;
	   		std::istringstream _iss2(_page_size);
    		_iss2 >> page_size;
				code_page_sizes[vpage] = page_size; 
			}
			data_page_dist_file.close();
		}
	} else {
		std::cerr << "ERROR: DATA_PAGE_DIST_FILENAME not defined!" << std::endl;
		exit(1);
	}

#endif
/*
#if defined(ENABLE_FDIP)
	fdip = new FDIP(16);
#endif
*/
}

void O3_CPU::finalize()
{
#if defined(MULTIPLE_PAGE_SIZE)

	std::ofstream instr_page_dist_file(INSTR_PAGE_DIST_FILENAME, std::ios_base::out);
	std::cout << "Saving instructions large page distribution to " << INSTR_PAGE_DIST_FILENAME << "..." << std::endl;
	for (auto it = code_page_sizes.begin(); it != code_page_sizes.end(); ++it) {
		unsigned int page_size = (uint32_t)(it->second);
		//std::cout << it->first << ":" << page_size << std::endl;
		instr_page_dist_file << it->first << ":" << page_size << std::endl;	
	}
	instr_page_dist_file.close();

	std::ofstream data_page_dist_file(DATA_PAGE_DIST_FILENAME, std::ios_base::out);
	std::cout << "Saving data large page distribution to " << DATA_PAGE_DIST_FILENAME << "..." << std::endl;
	for (auto it = data_page_sizes.begin(); it != data_page_sizes.end(); ++it) {
		unsigned int page_size = (uint32_t)(it->second);
		//std::cout << it->first << ":" << page_size << std::endl;
		data_page_dist_file << it->first << ":" << page_size << std::endl;	
	}
	data_page_dist_file.close();
#endif
}

void O3_CPU::begin_phase()
{
  begin_phase_instr = num_retired;
  begin_phase_cycle = current_cycle;

  // Record where the next phase begins
  stats_type stats;
  stats.name = "CPU " + std::to_string(cpu);
  stats.begin_instrs = num_retired;
  stats.begin_cycles = current_cycle;
  sim_stats.push_back(stats);
}

void O3_CPU::end_phase(unsigned finished_cpu)
{
  // Record where the phase ended (overwrite if this is later)
  sim_stats.back().end_instrs = num_retired;
  sim_stats.back().end_cycles = current_cycle;

#if defined(MULTIPLE_PAGE_SIZE)
	sim_stats.back().total_instr_large_pages = 0;
	sim_stats.back().total_instr_small_pages = 0;
	for (auto _it = code_page_sizes.begin(); _it != code_page_sizes.end(); ++_it) {
		if (_it->second == 2)
			sim_stats.back().total_instr_large_pages++;
		else 
			sim_stats.back().total_instr_small_pages++;
	}

	sim_stats.back().total_data_large_pages = 0;
	sim_stats.back().total_data_small_pages = 0;
	for (auto _it = data_page_sizes.begin(); _it != data_page_sizes.end(); ++_it) {
		if (_it->second == 2)
			sim_stats.back().total_data_large_pages++;
		else 
			sim_stats.back().total_data_small_pages++;
	}
#endif

  if (finished_cpu == this->cpu) {
    finish_phase_instr = num_retired;
    finish_phase_cycle = current_cycle;

    roi_stats.push_back(sim_stats.back());
  }
}

void O3_CPU::initialize_instruction()
{
  auto instrs_to_read_this_cycle = std::min(FETCH_WIDTH, static_cast<long>(IFETCH_BUFFER_SIZE - std::size(IFETCH_BUFFER)));

  while (current_cycle >= fetch_resume_cycle && instrs_to_read_this_cycle > 0 && !std::empty(input_queue)) {
    instrs_to_read_this_cycle--;

    auto stop_fetch = do_init_instruction(input_queue.front());
    if (stop_fetch)
      instrs_to_read_this_cycle = 0;

    // Add to IFETCH_BUFFER
    IFETCH_BUFFER.push_back(input_queue.front());
    input_queue.pop_front();

    IFETCH_BUFFER.back().event_cycle = current_cycle;
  }
#if defined(ENABLE_FDIP)
  std::deque<ooo_model_instr>* TARGET_BUFFER = &IFETCH_BUFFER;
  CACHE* TARGET_CACHE = static_cast<CACHE*>(L1I_bus.lower_level);
  auto last_inst_id = fdip.getLastAddedInstr();
  auto last_inst_addr = (std::begin(*TARGET_BUFFER));  
  if (fdip.isEnabled()){
    while ((last_inst_id >= last_inst_addr->instr_id) && 
          (last_inst_addr != std::end(*TARGET_BUFFER))) last_inst_addr++;

    for (; last_inst_addr != std::end(*TARGET_BUFFER); ++last_inst_addr){
      fdip.push_back(last_inst_addr);
    }

    fdip.prune();
    // Prefetch
    uint32_t sent = 0;
    while ((!fdip.empty()) && ( sent < fdip.getAggresivity())) {
      auto tuple = fdip.get_prefetch_line();
      uint64_t pf_addr = tuple.first;
      uint64_t instr_id = tuple.second;
      // Do not prefetch if the ip is already inflight
      if (std::end(IFETCH_BUFFER) == std::find_if(std::begin(IFETCH_BUFFER), std::end(IFETCH_BUFFER), [pf_addr] (auto x){
        return ((x.fetched > 0) && ((x.ip >> LOG2_BLOCK_SIZE) == (pf_addr >> LOG2_BLOCK_SIZE)));
      } ) ){   
        if (TARGET_CACHE->prefetch_line(pf_addr,
                true,
                0)) {
          fdip.issue_prefetch(instr_id, current_cycle);
        }
        sent++;
        
      }
    }
  }
#endif
}

namespace
{
void do_stack_pointer_folding(ooo_model_instr& arch_instr)
{
  // The exact, true value of the stack pointer for any given instruction can usually be determined immediately after the instruction is decoded without
  // waiting for the stack pointer's dependency chain to be resolved.
  bool writes_sp = std::count(std::begin(arch_instr.destination_registers), std::end(arch_instr.destination_registers), champsim::REG_STACK_POINTER);
  if (writes_sp) {
    // Avoid creating register dependencies on the stack pointer for calls, returns, pushes, and pops, but not for variable-sized changes in the
    // stack pointer position. reads_other indicates that the stack pointer is being changed by a variable amount, which can't be determined before
    // execution.
    bool reads_other = std::count_if(std::begin(arch_instr.source_registers), std::end(arch_instr.source_registers), [](uint8_t r) {
      return r != champsim::REG_STACK_POINTER && r != champsim::REG_FLAGS && r != champsim::REG_INSTRUCTION_POINTER;
    });
    if ((arch_instr.is_branch != 0) || !(std::empty(arch_instr.destination_memory) && std::empty(arch_instr.source_memory)) || (!reads_other)) {
      auto nonsp_end = std::remove(std::begin(arch_instr.destination_registers), std::end(arch_instr.destination_registers), champsim::REG_STACK_POINTER);
      arch_instr.destination_registers.erase(nonsp_end, std::end(arch_instr.destination_registers));
    }
  }
}
} // namespace

bool O3_CPU::do_predict_branch(ooo_model_instr& arch_instr)
{
  bool stop_fetch = false;

  // handle branch prediction for all instructions as at this point we do not know if the instruction is a branch
  sim_stats.back().total_branch_types[arch_instr.branch_type]++;
  auto [predicted_branch_target, always_taken] = impl_btb_prediction(arch_instr.ip);
  arch_instr.branch_prediction = impl_predict_branch(arch_instr.ip) || always_taken;
  if (arch_instr.branch_prediction == 0)
    predicted_branch_target = 0;

  if (arch_instr.is_branch) {
    if constexpr (champsim::debug_print) {
      std::cout << "[BRANCH] instr_id: " << arch_instr.instr_id << " ip: " << std::hex << arch_instr.ip << std::dec << " taken: " << +arch_instr.branch_taken
                << std::endl;
    }

    // call code prefetcher every time the branch predictor is used
    static_cast<CACHE*>(L1I_bus.lower_level)->impl_prefetcher_branch_operate(arch_instr.ip, arch_instr.branch_type, predicted_branch_target);

    if (predicted_branch_target != arch_instr.branch_target
        || (arch_instr.branch_type == BRANCH_CONDITIONAL
            && arch_instr.branch_taken != arch_instr.branch_prediction)) { // conditional branches are re-evaluated at decode when the target is computed
      sim_stats.back().total_rob_occupancy_at_branch_mispredict += std::size(ROB);
      sim_stats.back().branch_type_misses[arch_instr.branch_type]++;
      if (!warmup) {
        fetch_resume_cycle = std::numeric_limits<uint64_t>::max();
        stop_fetch = true;
        arch_instr.branch_mispredicted = 1;
      }
    } else {
      stop_fetch = arch_instr.branch_taken; // if correctly predicted taken, then we can't fetch anymore instructions this cycle
    }

    impl_update_btb(arch_instr.ip, arch_instr.branch_target, arch_instr.branch_taken, arch_instr.branch_type);
    impl_last_branch_result(arch_instr.ip, arch_instr.branch_target, arch_instr.branch_taken, arch_instr.branch_type);
  }

  return stop_fetch;
}

bool O3_CPU::do_init_instruction(ooo_model_instr& arch_instr)
{
  // fast warmup eliminates register dependencies between instructions branch predictor, cache contents, and prefetchers are still warmed up
  if (warmup) {
    arch_instr.source_registers.clear();
    arch_instr.destination_registers.clear();
  }

#ifdef TRACK_BRANCH_HISTORY
	if (arch_instr.is_branch) {
		if (arch_instr.branch_type == BRANCH_INDIRECT) {
			update_history(arch_instr.ip, uncondIndHistory);
		} else if (arch_instr.branch_type == BRANCH_CONDITIONAL) {
			update_history(arch_instr.ip, condHistory);
		}
	}
	update_path_history(arch_instr.ip);
	uncondIndHistory_old = uncondIndHistory;
	condHistory_old = condHistory;
#endif

  ::do_stack_pointer_folding(arch_instr);
  return do_predict_branch(arch_instr);
}

void O3_CPU::check_dib()
{
  // scan through IFETCH_BUFFER to find instructions that hit in the decoded instruction buffer
  auto begin = std::find_if(std::begin(IFETCH_BUFFER), std::end(IFETCH_BUFFER), [](const ooo_model_instr& x) { return !x.dib_checked; });
  auto [window_begin, window_end] = champsim::get_span(begin, std::end(IFETCH_BUFFER), FETCH_WIDTH);
  for (auto it = window_begin; it != window_end; ++it)
    do_check_dib(*it);
}

void O3_CPU::do_check_dib(ooo_model_instr& instr)
{
  // Check DIB to see if we recently fetched this line
  if (auto dib_result = DIB.check_hit(instr.ip); dib_result) {
    // The cache line is in the L0, so we can mark this as complete
    instr.fetched = COMPLETED;

    // Also mark it as decoded
    instr.decoded = COMPLETED;

    // It can be acted on immediately
    instr.event_cycle = current_cycle;
  }

  instr.dib_checked = COMPLETED;
}

void O3_CPU::fetch_instruction()
{
  // Fetch a single cache line
  auto fetch_ready = [](const ooo_model_instr& x) {
    return x.dib_checked == COMPLETED && !x.fetched;
  };

  // Find the chunk of instructions in the block
  auto no_match_ip = [](const auto& lhs, const auto& rhs) {
    return (lhs.ip >> LOG2_BLOCK_SIZE) != (rhs.ip >> LOG2_BLOCK_SIZE);
  };

  auto l1i_req_begin = std::find_if(std::begin(IFETCH_BUFFER), std::end(IFETCH_BUFFER), fetch_ready);

#if defined ENABLE_EXTRA_CPU_STATS
  // Check if instructions are stalled due to I-TLB misses
  for (auto it = l1i_req_begin; it != std::end(IFETCH_BUFFER); ++it) {
    if (it->dib_checked == COMPLETED && !it->fetched) {
      // This instruction is ready to fetch but hasn't been fetched
      // Could be stalled due to I-TLB miss
      itlb_stall_potential_cycles++;
    }
  }
#endif

  for (auto to_read = L1I_BANDWIDTH; to_read > 0 && l1i_req_begin != std::end(IFETCH_BUFFER); --to_read) {
    auto l1i_req_end = std::adjacent_find(l1i_req_begin, std::end(IFETCH_BUFFER), no_match_ip);
    if (l1i_req_end != std::end(IFETCH_BUFFER))
      l1i_req_end = std::next(l1i_req_end); // adjacent_find returns the first of the non-equal elements

    // Issue to L1I
    auto success = do_fetch_instruction(l1i_req_begin, l1i_req_end);
    if (success)
      std::for_each(l1i_req_begin, l1i_req_end, [](auto& x) { x.fetched = INFLIGHT; });

    l1i_req_begin = std::find_if(l1i_req_end, std::end(IFETCH_BUFFER), fetch_ready);
  }
}

bool O3_CPU::do_fetch_instruction(std::deque<ooo_model_instr>::iterator begin, std::deque<ooo_model_instr>::iterator end)
{
  PACKET fetch_packet;
  fetch_packet.v_address = begin->ip;
  fetch_packet.instr_id = begin->instr_id;
  fetch_packet.ip = begin->ip;
  fetch_packet.instr_depend_on_me = {begin, end};

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined FORCE_PTE_HIT
	fetch_packet.is_instr = true;
#endif

#if defined(MULTIPLE_PAGE_SIZE) 
	
	uint64_t ip = begin->ip;
	uint8_t page_size = 0;
	bool ip_found = false;
  // first search large pages
  auto ip_it = code_page_sizes.find(ip >> 21);
  if (ip_it != code_page_sizes.end()) {
    page_size = code_page_sizes[ip >> 21];
    ip_found = true;
  }

  ip_it = code_page_sizes.find(ip >> 12);
  if (ip_it != code_page_sizes.end()) {
    page_size = code_page_sizes[ip >> 12];
    ip_found = true;
  }

  // if not found we have a new entry, decide page size with 10% probability.
  if (!ip_found) {
    uint64_t probability = rand() % 100;
    if (probability < INSTR_PAGE_SIZE_DIST) {
      page_size = 2;
      code_page_sizes[ip >> 21] = 2;
    } else {
      page_size = 1;
      code_page_sizes[ip >> 12] = 1;
    }
  }

	fetch_packet.page_size = page_size; //PAGE_SIZE;
	if (page_size == 2)
		fetch_packet.base_vpn = begin->ip >> 21;
	else 
		fetch_packet.base_vpn = begin->ip >> 12;
#endif

  if constexpr (champsim::debug_print) {
    std::cout << "[IFETCH] " << __func__ << " instr_id: " << begin->instr_id << std::hex;
    std::cout << " ip: " << begin->ip << std::dec << " dependents: " << std::size(fetch_packet.instr_depend_on_me);
    std::cout << " event_cycle: " << begin->event_cycle << std::endl;
  }

  return L1I_bus.issue_read(fetch_packet);
}

void O3_CPU::promote_to_decode()
{
  auto available_fetch_bandwidth = std::min<long>(FETCH_WIDTH, DECODE_BUFFER_SIZE - std::size(DECODE_BUFFER));
  auto [window_begin, window_end] = champsim::get_span_p(std::begin(IFETCH_BUFFER), std::end(IFETCH_BUFFER), available_fetch_bandwidth,
                                                         [cycle = current_cycle](const auto& x) { return x.fetched == COMPLETED && x.event_cycle <= cycle; });
  std::for_each(window_begin, window_end,
                [cycle = current_cycle, lat = DECODE_LATENCY, warmup = warmup](auto& x) { return x.event_cycle = cycle + ((warmup || x.decoded) ? 0 : lat); });
  std::move(window_begin, window_end, std::back_inserter(DECODE_BUFFER));
  IFETCH_BUFFER.erase(window_begin, window_end);

  // check for deadlock
  if (!std::empty(IFETCH_BUFFER) && (IFETCH_BUFFER.front().event_cycle + DEADLOCK_CYCLE) <= current_cycle)
    throw champsim::deadlock{cpu};
}

void O3_CPU::decode_instruction()
{
  auto available_decode_bandwidth = std::min<long>(DECODE_WIDTH, DISPATCH_BUFFER_SIZE - std::size(DISPATCH_BUFFER));
  auto [window_begin, window_end] = champsim::get_span_p(std::begin(DECODE_BUFFER), std::end(DECODE_BUFFER), available_decode_bandwidth,
                                                         [cycle = current_cycle](const auto& x) { return x.event_cycle <= cycle; });

  // Send decoded instructions to dispatch
  std::for_each(window_begin, window_end, [&, this](auto& db_entry) {
    this->do_dib_update(db_entry);

    // Resume fetch
    if (db_entry.branch_mispredicted) {
      // These branches detect the misprediction at decode
      if ((db_entry.branch_type == BRANCH_DIRECT_JUMP) || (db_entry.branch_type == BRANCH_DIRECT_CALL)
          || (db_entry.branch_type == BRANCH_CONDITIONAL && db_entry.branch_taken == db_entry.branch_prediction)) {
        // clear the branch_mispredicted bit so we don't attempt to resume fetch again at execute
        db_entry.branch_mispredicted = 0;
        // pay misprediction penalty
        this->fetch_resume_cycle = this->current_cycle + BRANCH_MISPREDICT_PENALTY;
      }
    }

    // Add to dispatch
    db_entry.event_cycle = this->current_cycle + (this->warmup ? 0 : this->DISPATCH_LATENCY);
  });

  std::move(window_begin, window_end, std::back_inserter(DISPATCH_BUFFER));
  DECODE_BUFFER.erase(window_begin, window_end);

  // check for deadlock
  if (!std::empty(DECODE_BUFFER) && (DECODE_BUFFER.front().event_cycle + DEADLOCK_CYCLE) <= current_cycle)
    throw champsim::deadlock{cpu};
}

void O3_CPU::do_dib_update(const ooo_model_instr& instr) { DIB.fill(instr.ip); }

void O3_CPU::dispatch_instruction()
{
  std::size_t available_dispatch_bandwidth = DISPATCH_WIDTH;

  // dispatch DISPATCH_WIDTH instructions into the ROB
  while (available_dispatch_bandwidth > 0 && !std::empty(DISPATCH_BUFFER) && DISPATCH_BUFFER.front().event_cycle < current_cycle && std::size(ROB) != ROB_SIZE
         && ((std::size_t)std::count_if(std::begin(LQ), std::end(LQ), std::not_fn(is_valid<decltype(LQ)::value_type>{}))
             >= std::size(DISPATCH_BUFFER.front().source_memory))
         && ((std::size(DISPATCH_BUFFER.front().destination_memory) + std::size(SQ)) <= SQ_SIZE)) {
    ROB.push_back(std::move(DISPATCH_BUFFER.front()));
    DISPATCH_BUFFER.pop_front();
    do_memory_scheduling(ROB.back());

    available_dispatch_bandwidth--;
  }

  // check for deadlock
  if (!std::empty(DISPATCH_BUFFER) && (DISPATCH_BUFFER.front().event_cycle + DEADLOCK_CYCLE) <= current_cycle)
    throw champsim::deadlock{cpu};
}

void O3_CPU::schedule_instruction()
{
  auto search_bw = SCHEDULER_SIZE;
  for (auto rob_it = std::begin(ROB); rob_it != std::end(ROB) && search_bw > 0; ++rob_it) {
    if (rob_it->scheduled == 0)
      do_scheduling(*rob_it);

    if (rob_it->executed == 0)
      --search_bw;
  }
}

void O3_CPU::do_scheduling(ooo_model_instr& instr)
{
  // Mark register dependencies
  for (auto src_reg : instr.source_registers) {
    if (!std::empty(reg_producers[src_reg])) {
      ooo_model_instr& prior = reg_producers[src_reg].back();
      if (prior.registers_instrs_depend_on_me.empty() || prior.registers_instrs_depend_on_me.back().get().instr_id != instr.instr_id) {
        prior.registers_instrs_depend_on_me.push_back(instr);
        instr.num_reg_dependent++;
      }
    }
  }

  for (auto dreg : instr.destination_registers) {
    auto begin = std::begin(reg_producers[dreg]);
    auto end = std::end(reg_producers[dreg]);
    auto ins = std::lower_bound(begin, end, instr, [](const ooo_model_instr& lhs, const ooo_model_instr& rhs) { return lhs.instr_id < rhs.instr_id; });
    reg_producers[dreg].insert(ins, std::ref(instr));
  }

  instr.scheduled = COMPLETED;
  instr.event_cycle = current_cycle + (warmup ? 0 : SCHEDULING_LATENCY);
}

void O3_CPU::execute_instruction()
{
  auto exec_bw = EXEC_WIDTH;
  for (auto rob_it = std::begin(ROB); rob_it != std::end(ROB) && exec_bw > 0; ++rob_it) {
    if (rob_it->scheduled == COMPLETED && rob_it->executed == 0 && rob_it->num_reg_dependent == 0 && rob_it->event_cycle <= current_cycle) {
      do_execution(*rob_it);
      --exec_bw;
    }
  }
}

void O3_CPU::do_execution(ooo_model_instr& rob_entry)
{
  rob_entry.executed = INFLIGHT;
  rob_entry.event_cycle = current_cycle + (warmup ? 0 : EXEC_LATENCY);

  // Mark LQ entries as ready to translate
  for (auto& lq_entry : LQ)
    if (lq_entry.has_value() && lq_entry->instr_id == rob_entry.instr_id)
      lq_entry->event_cycle = current_cycle + (warmup ? 0 : EXEC_LATENCY);

  // Mark SQ entries as ready to translate
  for (auto& sq_entry : SQ)
    if (sq_entry.instr_id == rob_entry.instr_id)
      sq_entry.event_cycle = current_cycle + (warmup ? 0 : EXEC_LATENCY);

  if constexpr (champsim::debug_print) {
    std::cout << "[ROB] " << __func__ << " instr_id: " << rob_entry.instr_id << " event_cycle: " << rob_entry.event_cycle << std::endl;
  }
}

void O3_CPU::do_memory_scheduling(ooo_model_instr& instr)
{
  // load
#if defined(MULTIPLE_PAGE_SIZE)
/*
	std::cout << "checkpoint1.0" << std::endl;
	auto page_size_src = std::begin(instr.page_size_source);
	std::cout << "checkpoint1.1" << std::endl;
	auto base_vpn_src = std::begin(instr.base_vpn_source);
	std::cout << "checkpoint1.2" << std::endl;
*/
#endif
  for (auto& smem : instr.source_memory) {
    auto q_entry = std::find_if_not(std::begin(LQ), std::end(LQ), is_valid<decltype(LQ)::value_type>{});
    assert(q_entry != std::end(LQ));
#if defined(MULTIPLE_PAGE_SIZE)
		uint64_t addr = smem;
		uint8_t page_size = 0;
		uint64_t base_vpn = 0;
		bool addr_found = false;
  	// first search large pages
  	auto addr_it = data_page_sizes.find(addr >> 21);
  	if (addr_it != data_page_sizes.end()) {
    	page_size = data_page_sizes[addr >> 21];
    	addr_found = true;
  	}

  	addr_it = data_page_sizes.find(addr >> 12);
  	if (addr_it != data_page_sizes.end()) {
    	page_size = data_page_sizes[addr >> 12];
    	addr_found = true;
  	}

 	 	// if not found we have a new entry, decide page size with 10% probability.
  	if (!addr_found) {
    	uint64_t probability = rand() % 100;
    	if (probability < DATA_PAGE_SIZE_DIST) {
      	page_size = 2;
      	data_page_sizes[addr >> 21] = 2;
    	} else {
      	page_size = 1;
      	data_page_sizes[addr >> 12] = 1;
    	}
  	}

		if (page_size == 2)
			base_vpn = addr >> 21;
		else 
			base_vpn = addr >> 12;

    //q_entry->emplace(instr.instr_id, smem, instr.ip, instr.asid, *page_size_src++, *base_vpn_src++); // add it to the load queue
    q_entry->emplace(instr.instr_id, smem, instr.ip, instr.asid, page_size, base_vpn); // add it to the load queue
		//std::cout << "checkpoint2" << std::endl;
#else
    q_entry->emplace(instr.instr_id, smem, instr.ip, instr.asid); // add it to the load queue
#endif
    // Check for forwarding
    auto sq_it = std::max_element(std::begin(SQ), std::end(SQ), [smem](const auto& lhs, const auto& rhs) {
      return lhs.virtual_address != smem || (rhs.virtual_address == smem && lhs.instr_id < rhs.instr_id);
    });
    if (sq_it != std::end(SQ) && sq_it->virtual_address == smem) {
      if (sq_it->fetch_issued) { // Store already executed
        q_entry->reset();
        ++instr.completed_mem_ops;

        if constexpr (champsim::debug_print)
          std::cout << "[DISPATCH] " << __func__ << " instr_id: " << instr.instr_id << " forwards from " << sq_it->instr_id << std::endl;
      } else {
        assert(sq_it->instr_id < instr.instr_id);   // The found SQ entry is a prior store
        sq_it->lq_depend_on_me.push_back(*q_entry); // Forward the load when the store finishes
        (*q_entry)->producer_id = sq_it->instr_id;  // The load waits on the store to finish

        if constexpr (champsim::debug_print)
          std::cout << "[DISPATCH] " << __func__ << " instr_id: " << instr.instr_id << " waits on " << sq_it->instr_id << std::endl;
			}
		}
  }

  // store
#if defined(MULTIPLE_PAGE_SIZE)
/*
	auto page_size_dst = std::begin(instr.page_size_destination);
	std::cout << "checkpoint3.1" << std::endl;
	auto base_vpn_dst = std::begin(instr.base_vpn_destination);	
	std::cout << "checkpoint3.2" << std::endl;
*/
#endif
  for (auto& dmem : instr.destination_memory) {
#if defined(MULTIPLE_PAGE_SIZE)
		uint64_t addr = dmem;
		uint8_t page_size = 0;
		uint64_t base_vpn = 0;
		bool addr_found = false;
  	// first search large pages
  	auto addr_it = data_page_sizes.find(addr >> 21);
  	if (addr_it != data_page_sizes.end()) {
    	page_size = data_page_sizes[addr >> 21];
    	addr_found = true;
  	}

  	addr_it = data_page_sizes.find(addr >> 12);
  	if (addr_it != data_page_sizes.end()) {
    	page_size = data_page_sizes[addr >> 12];
    	addr_found = true;
  	}

 	 	// if not found we have a new entry, decide page size with 10% probability.
  	if (!addr_found) {
    	uint64_t probability = rand() % 100;
    	if (probability < DATA_PAGE_SIZE_DIST) {
      	page_size = 2;
      	data_page_sizes[addr >> 21] = 2;
    	} else {
      	page_size = 1;
      	data_page_sizes[addr >> 12] = 1;
    	}
  	}

		if (page_size == 2)
			base_vpn = addr >> 21;
		else 
			base_vpn = addr >> 12;

    //SQ.emplace_back(instr.instr_id, dmem, instr.ip, instr.asid, *page_size_dst++, *base_vpn_dst++); // add it to the store queue
    SQ.emplace_back(instr.instr_id, dmem, instr.ip, instr.asid, page_size, base_vpn); // add it to the store queue
		//std::cout << "checkpoint4" << std::endl;
#else
    SQ.emplace_back(instr.instr_id, dmem, instr.ip, instr.asid); // add it to the store queue
#endif
	}
  if constexpr (champsim::debug_print) {
    std::cout << "[DISPATCH] " << __func__ << " instr_id: " << instr.instr_id << " loads: " << std::size(instr.source_memory)
              << " stores: " << std::size(instr.destination_memory) << std::endl;
  }
}

void O3_CPU::operate_lsq()
{
  auto store_bw = SQ_WIDTH;

  const auto complete_id = std::empty(ROB) ? std::numeric_limits<uint64_t>::max() : ROB.front().instr_id;
  auto do_complete = [cycle = current_cycle, complete_id, this](const auto& x) {
    return x.instr_id < complete_id && x.event_cycle <= cycle && this->do_complete_store(x);
  };

  auto unfetched_begin = std::partition_point(std::begin(SQ), std::end(SQ), [](const auto& x) { return x.fetch_issued; });
  
#if defined ENABLE_EXTRA_CPU_STATS
  for (auto it = unfetched_begin; it != std::end(SQ); ++it) {
    if (it->event_cycle <= current_cycle && !it->fetch_issued) {
      // Store ready but not issued - could be TLB stall
      dtlb_stall_potential_cycles++;
    }
  }
#endif
  
  auto [fetch_begin, fetch_end] = champsim::get_span_p(unfetched_begin, std::end(SQ), store_bw,
                                                       [cycle = current_cycle](const auto& x) { return !x.fetch_issued && x.event_cycle <= cycle; });
  store_bw -= std::distance(fetch_begin, fetch_end);
  std::for_each(fetch_begin, fetch_end, [cycle = current_cycle, this](auto& sq_entry) {
    this->do_finish_store(sq_entry);
    sq_entry.fetch_issued = true;
    sq_entry.event_cycle = cycle;
  });

  auto [complete_begin, complete_end] = champsim::get_span_p(std::cbegin(SQ), std::cend(SQ), store_bw, do_complete);
  store_bw -= std::distance(complete_begin, complete_end);
  SQ.erase(complete_begin, complete_end);

  auto load_bw = LQ_WIDTH;

  for (auto& lq_entry : LQ) {
    if (load_bw > 0 && lq_entry.has_value() && lq_entry->producer_id == std::numeric_limits<uint64_t>::max() && !lq_entry->fetch_issued
        && lq_entry->event_cycle < current_cycle) {
      auto success = execute_load(*lq_entry);
      if (success) {
        --load_bw;
        lq_entry->fetch_issued = true;

#if defined ENABLE_EXTRA_CPU_STATS
        dtlb_stall_potential_cycles++;
#endif

      }
    }
  }
}

void O3_CPU::do_finish_store(const LSQ_ENTRY& sq_entry)
{
  sq_entry.finish(std::begin(ROB), std::end(ROB));

  // Release dependent loads
  for (std::optional<LSQ_ENTRY>& dependent : sq_entry.lq_depend_on_me) {
    assert(dependent.has_value()); // LQ entry is still allocated
    assert(dependent->producer_id == sq_entry.instr_id);

    dependent->finish(std::begin(ROB), std::end(ROB));
    dependent.reset();
  }
}

bool O3_CPU::do_complete_store(const LSQ_ENTRY& sq_entry)
{
  PACKET data_packet;
  data_packet.v_address = sq_entry.virtual_address;
  data_packet.instr_id = sq_entry.instr_id;
  data_packet.ip = sq_entry.ip;

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined FORCE_PTE_HIT
	data_packet.is_instr = sq_entry.is_instr;
#endif

#if defined(MULTIPLE_PAGE_SIZE) 
	data_packet.page_size = sq_entry.page_size;
	data_packet.base_vpn = sq_entry.base_vpn;
#endif

  if constexpr (champsim::debug_print) {
    std::cout << "[SQ] " << __func__ << " instr_id: " << sq_entry.instr_id << std::endl;
  }

  return L1D_bus.issue_write(data_packet);
}

bool O3_CPU::execute_load(const LSQ_ENTRY& lq_entry)
{
  PACKET data_packet;
  data_packet.v_address = lq_entry.virtual_address;
  data_packet.instr_id = lq_entry.instr_id;
  data_packet.ip = lq_entry.ip;

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined FORCE_PTE_HIT
	data_packet.is_instr = lq_entry.is_instr;
#endif

#if defined(MULTIPLE_PAGE_SIZE)
	data_packet.page_size = lq_entry.page_size;
	data_packet.base_vpn = lq_entry.base_vpn;
#endif

  if constexpr (champsim::debug_print) {
    std::cout << "[LQ] " << __func__ << " instr_id: " << lq_entry.instr_id << std::endl;
  }

  return L1D_bus.issue_read(data_packet);
}

void O3_CPU::do_complete_execution(ooo_model_instr& instr)
{
  for (auto dreg : instr.destination_registers) {
    auto begin = std::begin(reg_producers[dreg]);
    auto end = std::end(reg_producers[dreg]);
    auto elem = std::find_if(begin, end, [id = instr.instr_id](ooo_model_instr& x) { return x.instr_id == id; });
    assert(elem != end);
    reg_producers[dreg].erase(elem);
  }

  instr.executed = COMPLETED;

  for (ooo_model_instr& dependent : instr.registers_instrs_depend_on_me) {
    dependent.num_reg_dependent--;
    assert(dependent.num_reg_dependent >= 0);

    if (dependent.num_reg_dependent == 0)
      dependent.scheduled = COMPLETED;
  }

  if (instr.branch_mispredicted)
    fetch_resume_cycle = current_cycle + BRANCH_MISPREDICT_PENALTY;
}

void O3_CPU::complete_inflight_instruction()
{
  // update ROB entries with completed executions
  auto complete_bw = EXEC_WIDTH;
  for (auto rob_it = std::begin(ROB); rob_it != std::end(ROB) && complete_bw > 0; ++rob_it) {
    if ((rob_it->executed == INFLIGHT) && (rob_it->event_cycle <= current_cycle) && rob_it->completed_mem_ops == rob_it->num_mem_ops()) {
      do_complete_execution(*rob_it);
      --complete_bw;
    }
  }
}

void O3_CPU::handle_memory_return()
{
  for (auto l1i_bw = FETCH_WIDTH, to_read = L1I_BANDWIDTH; l1i_bw > 0 && to_read > 0 && !L1I_bus.PROCESSED.empty(); --to_read) {
    PACKET& l1i_entry = L1I_bus.PROCESSED.front();

    while (l1i_bw > 0 && !l1i_entry.instr_depend_on_me.empty()) {
      ooo_model_instr& fetched = l1i_entry.instr_depend_on_me.front();
      if ((fetched.ip >> LOG2_BLOCK_SIZE) == (l1i_entry.v_address >> LOG2_BLOCK_SIZE) && fetched.fetched != 0) {
        fetched.fetched = COMPLETED;
        --l1i_bw;

        if constexpr (champsim::debug_print) {
          std::cout << "[IFETCH] " << __func__ << " instr_id: " << fetched.instr_id << " fetch completed" << std::endl;
        }
      }

      l1i_entry.instr_depend_on_me.erase(std::begin(l1i_entry.instr_depend_on_me));
    }

    // remove this entry if we have serviced all of its instructions
    if (l1i_entry.instr_depend_on_me.empty())
      L1I_bus.PROCESSED.pop_front();
  }

  auto l1d_it = std::begin(L1D_bus.PROCESSED);
  for (auto l1d_bw = L1D_BANDWIDTH; l1d_bw > 0 && l1d_it != std::end(L1D_bus.PROCESSED); --l1d_bw, ++l1d_it) {
    for (auto& lq_entry : LQ) {
      if (lq_entry.has_value() && lq_entry->fetch_issued && lq_entry->virtual_address >> LOG2_BLOCK_SIZE == l1d_it->v_address >> LOG2_BLOCK_SIZE) {
        lq_entry->finish(std::begin(ROB), std::end(ROB));
        lq_entry.reset();
      }
    }
  }
  L1D_bus.PROCESSED.erase(std::begin(L1D_bus.PROCESSED), l1d_it);
}

void O3_CPU::retire_rob()
{
  auto [retire_begin, retire_end] = champsim::get_span_p(std::cbegin(ROB), std::cend(ROB), RETIRE_WIDTH, [](const auto& x) { return x.executed == COMPLETED; });
  if constexpr (champsim::debug_print) {
    std::for_each(retire_begin, retire_end, [](const auto& x) { std::cout << "[ROB] retire_rob instr_id: " << x.instr_id << " is retired" << std::endl; });
  }
  num_retired += std::distance(retire_begin, retire_end);
  ROB.erase(retire_begin, retire_end);

  // Check for deadlock
  if (!std::empty(ROB) && (ROB.front().event_cycle + DEADLOCK_CYCLE) <= current_cycle)
    throw champsim::deadlock{cpu};
}

void CacheBus::return_data(const PACKET& packet) { PROCESSED.push_back(packet); }

void O3_CPU::print_deadlock()
{
  std::cout << "DEADLOCK! CPU " << cpu << " cycle " << current_cycle << std::endl;

  if (!std::empty(IFETCH_BUFFER)) {
    std::cout << "IFETCH_BUFFER head";
    std::cout << " instr_id: " << IFETCH_BUFFER.front().instr_id;
    std::cout << " fetched: " << +IFETCH_BUFFER.front().fetched;
    std::cout << " scheduled: " << +IFETCH_BUFFER.front().scheduled;
    std::cout << " executed: " << +IFETCH_BUFFER.front().executed;
    std::cout << " num_reg_dependent: " << +IFETCH_BUFFER.front().num_reg_dependent;
    std::cout << " num_mem_ops: " << IFETCH_BUFFER.front().num_mem_ops() - IFETCH_BUFFER.front().completed_mem_ops;
    std::cout << " event: " << IFETCH_BUFFER.front().event_cycle;
    std::cout << std::endl;
  } else {
    std::cout << "IFETCH_BUFFER empty" << std::endl;
  }

  if (!std::empty(ROB)) {
    std::cout << "ROB head";
    std::cout << " instr_id: " << ROB.front().instr_id;
    std::cout << " fetched: " << +ROB.front().fetched;
    std::cout << " scheduled: " << +ROB.front().scheduled;
    std::cout << " executed: " << +ROB.front().executed;
    std::cout << " num_reg_dependent: " << +ROB.front().num_reg_dependent;
    std::cout << " num_mem_ops: " << ROB.front().num_mem_ops() - ROB.front().completed_mem_ops;
    std::cout << " event: " << ROB.front().event_cycle;
    std::cout << std::endl;
  } else {
    std::cout << "ROB empty" << std::endl;
  }

  // print LQ entry
  std::cout << "Load Queue Entry" << std::endl;
  for (auto lq_it = std::begin(LQ); lq_it != std::end(LQ); ++lq_it) {
    if (lq_it->has_value()) {
      std::cout << "[LQ] entry: " << std::distance(std::begin(LQ), lq_it) << " instr_id: " << (*lq_it)->instr_id << " address: " << std::hex
                << (*lq_it)->virtual_address << std::dec << " fetched_issued: " << std::boolalpha << (*lq_it)->fetch_issued << std::noboolalpha
                << " event_cycle: " << (*lq_it)->event_cycle;
      if ((*lq_it)->producer_id != std::numeric_limits<uint64_t>::max())
        std::cout << " waits on " << (*lq_it)->producer_id;
      std::cout << std::endl;
    }
  }

  // print SQ entry
  std::cout << std::endl << "Store Queue Entry" << std::endl;
  for (auto sq_it = std::begin(SQ); sq_it != std::end(SQ); ++sq_it) {
    std::cout << "[SQ] entry: " << std::distance(std::begin(SQ), sq_it) << " instr_id: " << sq_it->instr_id << " address: " << std::hex
              << sq_it->virtual_address << std::dec << " fetched: " << std::boolalpha << sq_it->fetch_issued << std::noboolalpha
              << " event_cycle: " << sq_it->event_cycle << " LQ waiting: ";
    for (std::optional<LSQ_ENTRY>& lq_entry : sq_it->lq_depend_on_me)
      std::cout << lq_entry->instr_id << " ";
    std::cout << std::endl;
  }
}

#if defined(MULTIPLE_PAGE_SIZE)
LSQ_ENTRY::LSQ_ENTRY( uint64_t id, uint64_t addr, uint64_t local_ip, std::array<uint8_t, 2> local_asid, 
										 	uint32_t pgsz, uint64_t vpn) 
    : instr_id(id), virtual_address(addr), ip(local_ip), asid(local_asid), page_size(pgsz), base_vpn(vpn)
{
}
#else
LSQ_ENTRY::LSQ_ENTRY(uint64_t id, uint64_t addr, uint64_t local_ip, std::array<uint8_t, 2> local_asid)
    : instr_id(id), virtual_address(addr), ip(local_ip), asid(local_asid)
{
}
#endif 

void LSQ_ENTRY::finish(std::deque<ooo_model_instr>::iterator begin, std::deque<ooo_model_instr>::iterator end) const
{
  auto rob_entry = std::partition_point(begin, end, [id = this->instr_id](auto x) { return x.instr_id < id; });
  assert(rob_entry != end);
  assert(rob_entry->instr_id == this->instr_id);

  ++rob_entry->completed_mem_ops;
  assert(rob_entry->completed_mem_ops <= rob_entry->num_mem_ops());

  if constexpr (champsim::debug_print) {
    std::cout << "[LSQ] " << __func__ << " instr_id: " << instr_id << std::hex;
    std::cout << " full_address: " << virtual_address << std::dec << " remain_mem_ops: " << rob_entry->num_mem_ops() - rob_entry->completed_mem_ops;
    std::cout << " event_cycle: " << event_cycle << std::endl;
  }
}

bool CacheBus::issue_read(PACKET data_packet)
{
  data_packet.address = data_packet.v_address;
  data_packet.cpu = cpu;
  data_packet.type = LOAD;
  data_packet.to_return = {this};

  return lower_level->add_rq(data_packet);
}

bool CacheBus::issue_write(PACKET data_packet)
{
  data_packet.address = data_packet.v_address;
  data_packet.cpu = cpu;
  data_packet.type = WRITE;

  return lower_level->add_wq(data_packet);
}
