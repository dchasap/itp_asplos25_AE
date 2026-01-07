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

#ifndef INSTRUCTION_H
#define INSTRUCTION_H

#include <algorithm>
#include <array>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <vector>

#include "trace_instruction.h"

// branch types
enum branch_type {
  NOT_BRANCH = 0,
  BRANCH_DIRECT_JUMP = 1,
  BRANCH_INDIRECT = 2,
  BRANCH_CONDITIONAL = 3,
  BRANCH_DIRECT_CALL = 4,
  BRANCH_INDIRECT_CALL = 5,
  BRANCH_RETURN = 6,
  BRANCH_OTHER = 7
};

struct ooo_model_instr {
  uint64_t instr_id = 0;
  uint64_t ip = 0;
  uint64_t event_cycle = 0;

  bool is_branch = 0;
  bool branch_taken = 0;
  bool branch_prediction = 0;
  bool branch_mispredicted = 0; // A branch can be mispredicted even if the direction prediction is correct when the predicted target is not correct

  std::array<uint8_t, 2> asid = {std::numeric_limits<uint8_t>::max(), std::numeric_limits<uint8_t>::max()};

  uint8_t branch_type = NOT_BRANCH;
  uint64_t branch_target = 0;

  uint8_t dib_checked = 0;
  uint8_t fetched = 0;
  uint8_t decoded = 0;
  uint8_t scheduled = 0;
  uint8_t executed = 0;

  unsigned completed_mem_ops = 0;
  int num_reg_dependent = 0;

  std::vector<uint8_t> destination_registers = {}; // output registers
  std::vector<uint8_t> source_registers = {};      // input registers

  std::vector<uint64_t> destination_memory = {};
  std::vector<uint64_t> source_memory = {};

  // these are indices of instructions in the ROB that depend on me
  std::vector<std::reference_wrapper<ooo_model_instr>> registers_instrs_depend_on_me;

#ifdef _MULTIPLE_PAGE_SIZE
  std::vector<uint64_t> base_vpn_destination = {};
	std::vector<uint64_t> base_vpn_source = {};

	std::vector<uint8_t> page_size_destination = {};
	std::vector<uint8_t> page_size_source = {};

	// keep around a record of what the original virtual addresses were
	//std::vector<uint64_t> destination_virtual_address = {};
	//std::vector<uint64_t> source_virtual_address = {};
#endif

private:
  template <typename T>
  ooo_model_instr(T instr, std::array<uint8_t, 2> local_asid) : ip(instr.ip), is_branch(instr.is_branch), branch_taken(instr.branch_taken), asid(local_asid)
  {
    std::remove_copy(std::begin(instr.destination_registers), std::end(instr.destination_registers), std::back_inserter(this->destination_registers), 0);
    std::remove_copy(std::begin(instr.source_registers), std::end(instr.source_registers), std::back_inserter(this->source_registers), 0);
    std::remove_copy(std::begin(instr.destination_memory), std::end(instr.destination_memory), std::back_inserter(this->destination_memory), 0);
    std::remove_copy(std::begin(instr.source_memory), std::end(instr.source_memory), std::back_inserter(this->source_memory), 0);

    bool writes_sp = std::count(std::begin(destination_registers), std::end(destination_registers), champsim::REG_STACK_POINTER);
    bool writes_ip = std::count(std::begin(destination_registers), std::end(destination_registers), champsim::REG_INSTRUCTION_POINTER);
    bool reads_sp = std::count(std::begin(source_registers), std::end(source_registers), champsim::REG_STACK_POINTER);
    bool reads_flags = std::count(std::begin(source_registers), std::end(source_registers), champsim::REG_FLAGS);
    bool reads_ip = std::count(std::begin(source_registers), std::end(source_registers), champsim::REG_INSTRUCTION_POINTER);
    bool reads_other = std::count_if(std::begin(source_registers), std::end(source_registers), [](uint8_t r) {
      return r != champsim::REG_STACK_POINTER && r != champsim::REG_FLAGS && r != champsim::REG_INSTRUCTION_POINTER;
    });

    // determine what kind of branch this is, if any
    if (!reads_sp && !reads_flags && writes_ip && !reads_other) {
      // direct jump
      is_branch = true;
      branch_taken = true;
      branch_type = BRANCH_DIRECT_JUMP;
    } else if (!reads_sp && !reads_flags && writes_ip && reads_other) {
      // indirect branch
      is_branch = true;
      branch_taken = true;
      branch_type = BRANCH_INDIRECT;
    } else if (!reads_sp && reads_ip && !writes_sp && writes_ip && reads_flags && !reads_other) {
      // conditional branch
      is_branch = true;
      branch_taken = instr.branch_taken; // don't change this
      branch_type = BRANCH_CONDITIONAL;
    } else if (reads_sp && reads_ip && writes_sp && writes_ip && !reads_flags && !reads_other) {
      // direct call
      is_branch = true;
      branch_taken = true;
      branch_type = BRANCH_DIRECT_CALL;
    } else if (reads_sp && reads_ip && writes_sp && writes_ip && !reads_flags && reads_other) {
      // indirect call
      is_branch = true;
      branch_taken = true;
      branch_type = BRANCH_INDIRECT_CALL;
    } else if (reads_sp && !reads_ip && writes_sp && writes_ip) {
      // return
      is_branch = true;
      branch_taken = true;
      branch_type = BRANCH_RETURN;
    } else if (writes_ip) {
      // some other branch type that doesn't fit the above categories
      is_branch = true;
      branch_taken = instr.branch_taken; // don't change this
      branch_type = BRANCH_OTHER;
    } else {
      branch_taken = false;
    }
  }

	void print_instr() 
	{
  	std::cout << "*** " << instr_id << " ***" << std::endl;
  	std::cout << std::hex << "pc: 0x" << (uint64_t)this->ip << std::dec << std::endl;
  	std::cout << "is_branch:" << (uint32_t)this->is_branch 
							<< ", is taken:" << (uint32_t)this->branch_taken << std::endl;

  	std::cout << "     source_registers: ";
  	for (auto& src_reg : this->source_registers)
    	std::cout << (uint32_t)(src_reg) << " ";
  	std::cout << std::endl;

  	std::cout << "        source_memory: ";
  	for (auto& src_mem : this->source_memory)
    	std::cout << std::hex << "0x" << (uint32_t)(src_mem) << std::dec << " ";
  	std::cout << std::endl;

#if defined(_MULTIPLE_PAGE_SIZE)
  	std::cout << "     source_page_size: ";
  	for (auto& src_pgsz : this->page_size_source)
    	std::cout << (uint32_t)(src_pgsz) << " ";
  	std::cout << std::endl;

  	std::cout << "      source_base_vpn: ";
  	for (auto& src_base_vpn : this->base_vpn_source)
    	std::cout << std::hex << "0x" << (uint32_t)(src_base_vpn) << std::dec << " ";
  	std::cout << std::endl;
#endif

  	std::cout << "destination_registers: ";
  	for (auto& dest_reg : this->destination_registers)
    	std::cout << (uint32_t)(dest_reg) << " ";
  	std::cout << std::endl;

  	std::cout << "   destination_memory: ";
  	for (auto& dest_mem : this->destination_memory)
    	std::cout << std::hex << "0x" << (uint32_t)(dest_mem) << std::dec << " ";
  	std::cout << std::endl;

#if defined(_MULTIPLE_PAGE_SIZE)
  	std::cout << "destination_page_size: ";
  	for (auto& dest_pgsz : this->page_size_destination)
    	std::cout << (uint32_t)(dest_pgsz) << " ";
  	std::cout << std::endl;

  	std::cout << " destination_base_vpn: ";
  	for (auto& dest_base_vpn : this->base_vpn_destination)
    	std::cout << std::hex << "0x" << (uint32_t)(dest_base_vpn) << std::dec << " ";
  	std::cout << std::endl;
#endif
  	std::cout << std::endl;
		instr_id++;
	}
public:

#if defined(_MULTIPLE_PAGE_SIZE)
	ooo_model_instr(uint8_t cpu, input_instr instr, page_size_info pgsz_info) : ooo_model_instr(instr, {cpu, cpu}) 
{
		// Why use back inserter??? 
	std::remove_copy(std::begin(pgsz_info.base_vpn_destination), std::end(pgsz_info.base_vpn_destination), std::back_inserter(this->base_vpn_destination), 0);
	std::remove_copy(std::begin(pgsz_info.page_size_destination), std::end(pgsz_info.page_size_destination), std::back_inserter(this->page_size_destination), 0);
	std::remove_copy(std::begin(pgsz_info.base_vpn_source), std::end(pgsz_info.base_vpn_source), std::back_inserter(this->base_vpn_source), 0);
	std::remove_copy(std::begin(pgsz_info.page_size_source), std::end(pgsz_info.page_size_source), std::back_inserter(this->page_size_source), 0);

	//this->print_instr();
}

  ooo_model_instr(uint8_t, cloudsuite_instr instr, page_size_info pgsz_info) : ooo_model_instr(instr, {instr.asid[0], instr.asid[1]}) 
{
	std::remove_copy(std::begin(pgsz_info.base_vpn_destination), std::end(pgsz_info.base_vpn_destination), std::back_inserter(this->base_vpn_destination), 0);
	std::remove_copy(std::begin(pgsz_info.page_size_destination), std::end(pgsz_info.page_size_destination), std::back_inserter(this->page_size_destination), 0);
	std::remove_copy(std::begin(pgsz_info.base_vpn_source), std::end(pgsz_info.base_vpn_source), std::back_inserter(this->base_vpn_source), 0);
	std::remove_copy(std::begin(pgsz_info.page_size_source), std::end(pgsz_info.page_size_source), std::back_inserter(this->page_size_source), 0);
}

#else
  ooo_model_instr(uint8_t cpu, input_instr instr) : ooo_model_instr(instr, {cpu, cpu}) {}
  ooo_model_instr(uint8_t, cloudsuite_instr instr) : ooo_model_instr(instr, {instr.asid[0], instr.asid[1]}) {}
#endif

  std::size_t num_mem_ops() const { return std::size(destination_memory) + std::size(source_memory); }

  static bool program_order(const ooo_model_instr& lhs, const ooo_model_instr& rhs) { return lhs.instr_id < rhs.instr_id; }


};
#endif
