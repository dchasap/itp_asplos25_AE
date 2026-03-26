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

#include "cache.h"

#include <algorithm>
#include <iomanip>
#include <iterator>
#include <numeric>

#include "champsim.h"
#include "champsim_constants.h"
#include "instruction.h"
#include "util.h"
#include <bits/range_access.h>


#if defined PTP_REPLACEMENT_POLICY
				extern uint64_t RETIRED_INSTRS;
				extern double STLB_MPKI;
#endif

				bool CACHE::handle_fill(const PACKET& fill_mshr)
				{
					cpu = fill_mshr.cpu;

					// find victim
#if defined SPLIT_STLB
					auto [set_begin, set_end] = get_set_span(fill_mshr.address, fill_mshr.is_instr);
					auto way = std::find_if_not(set_begin, set_end, [](auto x) { return x.valid; });
					if (way == set_end)
						way = std::next(set_begin, impl_find_victim(fill_mshr.cpu, fill_mshr.instr_id, get_set_index(fill_mshr.address, fill_mshr.is_instr), &*set_begin, fill_mshr.ip,
																												fill_mshr.address, fill_mshr.type));
#elif defined TX_SPLIT_CACHE
					auto [set_begin, set_end] = get_set_span(fill_mshr.address, fill_mshr.is_pte);
					auto way = std::find_if_not(set_begin, set_end, [](auto x) { return x.valid; });
					if (way == set_end)
						way = std::next(set_begin, impl_find_victim(fill_mshr.cpu, fill_mshr.instr_id, get_set_index(fill_mshr.address, fill_mshr.is_instr), &*set_begin, fill_mshr.ip,
																												fill_mshr.address, fill_mshr.type));
#elif defined TX_SPLIT_CACHE_WAYS
					if (!fill_mshr.is_pte) {
						std::cout << "Filling non-PTE cache line" << std::endl;
						auto [set_begin, set_end] = get_set_span(fill_mshr.address);
						auto way = std::find_if_not(set_begin, set_end, [](auto x) { return x.valid; });
						if (way == set_end)
							way = std::next(set_begin, impl_find_victim(fill_mshr.cpu, fill_mshr.instr_id, get_set_index(fill_mshr.address), &*set_begin, fill_mshr.ip,
																												fill_mshr.address, fill_mshr.type));
					} else {
						std::cout << "Filling PTE cache line" << std::endl;
						auto [set_begin, set_end] = get_set_span(fill_mshr.address);
						auto way = std::next(set_begin, NUM_WAY-1);
					}
#else 
					auto [set_begin, set_end] = get_set_span(fill_mshr.address);
					auto way = std::find_if_not(set_begin, set_end, [](auto x) { return x.valid; });
					if (way == set_end)
						way = std::next(set_begin, impl_find_victim(fill_mshr.cpu, fill_mshr.instr_id, get_set_index(fill_mshr.address), &*set_begin, fill_mshr.ip,
																												fill_mshr.address, fill_mshr.type));
#endif

					assert(set_begin <= way);
					assert(way <= set_end);
					const auto way_idx = static_cast<std::size_t>(std::distance(set_begin, way)); // cast protected by earlier assertion

					if constexpr (champsim::debug_print) {
						std::cout << "[" << NAME << "] " << __func__;
						std::cout << " instr_id: " << fill_mshr.instr_id << " address: " << std::hex << (fill_mshr.address >> OFFSET_BITS);
						std::cout << " full_addr: " << fill_mshr.address;
						std::cout << " full_v_addr: " << fill_mshr.v_address << std::dec;
#if defined SPLIT_STLB
						std::cout << " set: " << get_set_index(fill_mshr.address, fill_mshr.is_instr);
#elif defined TX_SPLIT_CACHE
						std::cout << " set: " << get_set_index(fill_mshr.address, fill_mshr.is_pte);
#else 
						std::cout << " set: " << get_set_index(fill_mshr.address);
#endif
						std::cout << " way: " << way_idx;
						std::cout << " type: " << +fill_mshr.type;
						std::cout << " cycle_enqueued: " << fill_mshr.cycle_enqueued;
						std::cout << " cycle: " << current_cycle << std::endl;
					}

					bool success = true;
					auto metadata_thru = fill_mshr.pf_metadata;
					auto pkt_address = (virtual_prefetch ? fill_mshr.v_address : fill_mshr.address) & ~champsim::bitmask(match_offset_bits ? 0 : OFFSET_BITS);

					if (way != set_end) {
						if (way->valid && way->dirty) {
							PACKET writeback_packet;

							writeback_packet.cpu = fill_mshr.cpu;
							writeback_packet.address = way->address;
							writeback_packet.data = way->data;
							writeback_packet.instr_id = fill_mshr.instr_id;
							writeback_packet.ip = 0;
							writeback_packet.type = WRITE;
							writeback_packet.pf_metadata = way->pf_metadata;

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT
							writeback_packet.is_instr = way->is_instr;
							writeback_packet.is_pte = way->is_pte;
							writeback_packet.translation_level = way->pte_level; // not necessary, ptes are not written back
							//writeback_packet.access_freq = way->access_freq;
#endif	

#if defined MULTIPLE_PAGE_SIZE
							writeback_packet.page_size = way->page_size;
							writeback_packet.base_vpn = way->base_vpn;
#endif

							success = lower_level->add_wq(writeback_packet);
						}

						if (success) {
							auto evicting_address = (ever_seen_data ? way->address : way->v_address) & ~champsim::bitmask(match_offset_bits ? 0 : OFFSET_BITS);


#if defined TRANSLATION_EXCLUSIVE_CACHE
							//FIXME: This is probably the ONLY point we should move something to the victim cache
							if (enable_tx_victim_cache) {

								//assert(NAME.find("_TXC") == std::string::npos);

								PACKET victim_packet;
								victim_packet.cpu = fill_mshr.cpu;
								victim_packet.address = way->address;
								victim_packet.data = way->data;
								victim_packet.instr_id = fill_mshr.instr_id;
								victim_packet.ip = 0;
								victim_packet.type = fill_mshr.type;
								victim_packet.pf_metadata = way->pf_metadata;

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT
								victim_packet.is_instr = way->is_instr;
								victim_packet.is_pte = way->is_pte;
								victim_packet.translation_level = way->pte_level;
#endif	

#if defined MULTIPLE_PAGE_SIZE
								victim_packet.page_size = way->page_size;
								victim_packet.base_vpn = way->base_vpn;
#endif
								bool is_dead = way->is_doa;
								way->is_doa = true; // reset the flag
								uint64_t access_freq = way->access_freq;
								way->access_freq = 0;

								bool vc_entry_cond;
								if (enable_instr_only)
									//std::cout << "instr only!" << std::endl;
									vc_entry_cond = way->is_pte && way->is_instr;
								else if (enable_data_only)
									vc_entry_cond = way->is_pte && !way->is_instr;
									//std::cout << "data only!" << std::endl;
								else 
									vc_entry_cond = way->is_pte;

#if defined SPLIT_STLB
								uint64_t set_idx = get_set_index(victim_packet.address, fill_mshr.is_instr);
#elif defined TX_SPLIT_CACHE
								uint64_t set_idx = get_set_index(victim_packet.address, fill_mshr.is_pte);
#else 
								uint64_t set_idx = get_set_index(victim_packet.address);
#endif

								//set_idx = 0;
								if (victim_packet.is_pte && last_pte_entry[set_idx] == victim_packet.address) {
									//vc_entry_cond = vc_entry_cond; // force doa
									way->is_doa = false;
								}
					
								//bool is_dead = tx_victim_cache->predictDOA(victim_packet.address, way->is_doa);
								//vc_entry_cond = vc_entry_cond && !is_dead;
								//way->is_doa = true; // reset the flag

								//std::cout << "add_req" << std::endl;
								if (vc_entry_cond) {

									if (enable_instr_only)
										assert(victim_packet.is_instr);
									else if (enable_data_only)
										assert(!victim_packet.is_instr);
									//success = tx_cache->add_wq(writeback_packet);
									//tx_cache->add_rq(victim_packet);
									//std::cout << "adding address: " << way->address << std::endl; 
									//tx_victim_cache[way->address] = *way;
									// get set index
									///std::cout << "victim_pkt@" << victim_packet.address << " access freq: " << access_freq << std::endl;
									tx_victim_cache->add_request(victim_packet, current_cycle, is_dead, access_freq);
									//std::cout << "tx_cache size:" << tx_victim_cache.size() << std::endl;
								}
							}
#endif // TRANSLATION_EXCLUSIVE_CACHE

#if defined FORCE_HIT // check if evicted entry is a PTE
							if (NAME.find(_CACHE_) != std::string::npos) {
								if (force_hit && (way->is_pte)) {
									// should use address or v_address
									cached_PTEs[way->address] = *way;
								}
							}
							//TODO: we don't handle really writes, writebacks because pte are never written to
#endif	

							if (way->prefetch)
								sim_stats.back().pf_useless++;

							if (fill_mshr.type == PREFETCH)
								sim_stats.back().pf_fill++;

#if defined ENABLE_PAGE_CROSSING_STATS 
							if ((NAME.find("ITLB") != std::string::npos) && (NAME.find("DTLB") != std::string::npos)
									&& (NAME.find("STLB")) && fill_mshr.prefetch_from_this) {
				
								way->page_crossing = fill_mshr.page_crossing;
							}
#endif

							way->valid = true;
							way->prefetch = fill_mshr.prefetch_from_this;
							way->dirty = (fill_mshr.type == WRITE);
							way->address = fill_mshr.address;
							way->v_address = fill_mshr.v_address;
							way->data = fill_mshr.data;
							//FIXME: should we have the type passed as well?
#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT || defined TRANSLATION_EXCLUSIVE_CACHE
							way->is_instr = fill_mshr.is_instr;
							way->is_pte = fill_mshr.is_pte;
							way->access_freq = fill_mshr.access_freq;
							way->pte_level = fill_mshr.translation_level;
#endif

#if defined MULTIPLE_PAGE_SIZE
							way->page_size = fill_mshr.page_size;
							way->base_vpn = fill_mshr.base_vpn;
#endif

#if defined SPLIT_STLB
							metadata_thru =
									impl_prefetcher_cache_fill(pkt_address, get_set_index(fill_mshr.address, fill_mshr.is_instr), way_idx, fill_mshr.type == PREFETCH, evicting_address, metadata_thru);
#elif defined TX_SPLIT_CACHE
							metadata_thru =
									impl_prefetcher_cache_fill(pkt_address, get_set_index(fill_mshr.address, fill_mshr.is_pte), way_idx, fill_mshr.type == PREFETCH, evicting_address, metadata_thru);
#else 
							metadata_thru =
									impl_prefetcher_cache_fill(pkt_address, get_set_index(fill_mshr.address), way_idx, fill_mshr.type == PREFETCH, evicting_address, metadata_thru);
#endif

	#if defined ENABLE_TRANSLATION_AWARE_REPLACEMENT
							REP_POL_XARGS xargs;
							xargs.is_instr = fill_mshr.is_instr;
							xargs.is_pte = fill_mshr.is_pte;
							xargs.is_replay = !fill_mshr.is_translated;
							xargs.translation_level = fill_mshr.translation_level;
							xargs.access_freq = fill_mshr.access_freq;
	#if defined SPLIT_STLB
							impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address, fill_mshr.is_instr), way_idx, 
																						fill_mshr.address, fill_mshr.ip, evicting_address, 
																						fill_mshr.type, false, xargs);
	#elif defined TX_SPLIT_CACHE
							impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address, fill_mshr.is_pte), way_idx, 
																						fill_mshr.address, fill_mshr.ip, evicting_address,	
																						fill_mshr.type, false, xargs);
	#else
							impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address), way_idx, 
																						fill_mshr.address, fill_mshr.ip, evicting_address, 
																						fill_mshr.type, false, xargs);

	#endif

#else
							impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address), way_idx, fill_mshr.address, fill_mshr.ip, evicting_address, fill_mshr.type,
																						false);
#endif
							way->pf_metadata = metadata_thru;
						}
					} else {
						// Bypass
						assert(fill_mshr.type != WRITE);

#if defined (SPLIT_STLB)
						metadata_thru = impl_prefetcher_cache_fill(pkt_address, get_set_index(fill_mshr.address, fill_mshr.is_instr), way_idx, fill_mshr.type == PREFETCH, 0, metadata_thru);
#elif defined (TX_SPLIT_CACHE)
						metadata_thru = impl_prefetcher_cache_fill(pkt_address, get_set_index(fill_mshr.address, fill_mshr.is_pte), way_idx, fill_mshr.type == PREFETCH, 0, metadata_thru);
#else 
						metadata_thru = impl_prefetcher_cache_fill(pkt_address, get_set_index(fill_mshr.address), way_idx, fill_mshr.type == PREFETCH, 0, metadata_thru);
#endif 

#if defined ENABLE_TRANSLATION_AWARE_REPLACEMENT
						REP_POL_XARGS xargs;
						xargs.is_instr = fill_mshr.is_instr;
						xargs.is_pte = fill_mshr.is_pte;
						xargs.is_replay = !fill_mshr.is_translated;
						xargs.translation_level = fill_mshr.translation_level;
						xargs.access_freq = fill_mshr.access_freq;
	#if defined (SPLIT_STLB)
						impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address, fill_mshr.is_instr), way_idx, 
																					fill_mshr.address, fill_mshr.ip, 0, 
																					fill_mshr.type, false, xargs);
	#elif defined (TX_SPLIT_CACHE)
						impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address, fill_mshr.is_pte), way_idx, 
																					fill_mshr.address, fill_mshr.ip, 0, 
																					fill_mshr.type, false, xargs);
	#else 
						impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address), way_idx, 
																					fill_mshr.address, fill_mshr.ip, 0, 
																					fill_mshr.type, false, xargs);
	#endif

#else

	#if defined (SPLIT_STLB)
						impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address, fill_mshr.is_instr), way_idx, fill_mshr.address, fill_mshr.ip, 0, fill_mshr.type, false);
	#elif defined (TX_SPLIT_CACHE)
						impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address, fill_mshr.is_pte), way_idx, fill_mshr.address, fill_mshr.ip, 0, fill_mshr.type, false); 
	#else
						impl_update_replacement_state(fill_mshr.cpu, get_set_index(fill_mshr.address), way_idx, fill_mshr.address, fill_mshr.ip, 0, fill_mshr.type, false);
	#endif 

#endif
					}

					if (success) {
#if defined ENABLE_EXTRA_CACHE_STATS
						if (fill_mshr.is_instr && !fill_mshr.is_pte) {
							sim_stats.back().total_imiss_latency += current_cycle - (fill_mshr.cycle_enqueued + 1);
						} else if (!fill_mshr.is_instr && !fill_mshr.is_pte) {
							sim_stats.back().total_dmiss_latency += current_cycle - (fill_mshr.cycle_enqueued + 1);
						} else if (fill_mshr.is_instr && fill_mshr.is_pte) {
							sim_stats.back().total_itmiss_latency += current_cycle - (fill_mshr.cycle_enqueued + 1);
						} else if (!fill_mshr.is_instr && fill_mshr.is_pte) {
							sim_stats.back().total_dtmiss_latency += current_cycle - (fill_mshr.cycle_enqueued + 1);
						} else {
							//sim_stats.back().ihits[handle_pkt.type][handle_pkt.cpu]++;
							std::cout << "Oups, something went wrong..." << std::endl;
							std::cout << "\ttype:" << (uint32_t)fill_mshr.type << std::endl;
							std::cout << "\tis_instr:" << (fill_mshr.is_instr?"true":"false") << std::endl;
							assert(false);
						}
#endif

						// COLLECT STATS
						sim_stats.back().total_miss_latency += current_cycle - (fill_mshr.cycle_enqueued + 1);
						//std::cout << NAME << ":checkpoint 8" << std::endl;
						try {
						auto copy{fill_mshr};
						//std::cout << "checkpoint 8.1" << std::endl;
						copy.pf_metadata = metadata_thru;
						for (auto ret : copy.to_return) {
						//std::cout << "checkpoint 8.2" << std::endl;
							ret->return_data(copy);
							//std::cout << "checkpoint 8.3" << std::endl;
						}
					
						}
						catch (const std::bad_array_new_length& e) {
							std::cout << "Error: " << e.what() << std::endl;
						}

					}
										
#if defined ENABLE_EXTRA_CACHE_STATS
					// Measure cache occupancy
					if (NAME.find("L1D_VC") != std::string::npos) {
					
						unsigned int occupied_elements = 0;
						for (unsigned int _set_idx = 0; _set_idx < NUM_SET; _set_idx++) {
							for (unsigned int _way_idx = 0; _way_idx < NUM_WAY; _way_idx++) {
								if (block[_set_idx * NUM_WAY + _way_idx].valid) {
									occupied_elements++;
								}
							}
						}

						double occupancy = double(occupied_elements * 100) / double(NUM_SET * NUM_WAY);
						if (occupancy > sim_stats.back().max_cache_occupancy) {
							sim_stats.back().max_cache_occupancy = occupancy;
						}

						if (occupancy >= 100 && !cache_is_full) {
							cache_is_full = true;
							std::cout << "Cache full@" << current_cycle << " cycle!" << std::endl;
						}
					}	
#endif
					//std::cout << "checkpoint 9" << std::endl;
					return success;
				}

				bool CACHE::try_hit(const PACKET& handle_pkt)
				{

					cpu = handle_pkt.cpu;

#if defined ENABLE_PAGE_CROSSING_STATS
					if (((NAME.find("L1I") != std::string::npos) || (NAME.find("L1D") != std::string::npos))
							&& (handle_pkt.type == PREFETCH) && (handle_pkt.page_crossing > 0)) {

						if (handle_pkt.page_crossing == 1) sim_stats.back().pf_crossing_pages_tlb_hit++;
						else if (handle_pkt.page_crossing == 2) sim_stats.back().pf_crossing_pages_tlb_miss++;
					}
#endif

					// access cache
#if defined SPLIT_STLB
					auto [set_begin, set_end] = get_set_span(handle_pkt.address, handle_pkt.is_instr);
#elif defined TX_SPLIT_CACHE
					auto [set_begin, set_end] = get_set_span(handle_pkt.address, handle_pkt.is_pte);
#else
					auto [set_begin, set_end] = get_set_span(handle_pkt.address);
#endif
					auto way = std::find_if(set_begin, set_end, eq_addr<BLOCK>(handle_pkt.address, OFFSET_BITS));
					const auto hit = (way != set_end);

					if constexpr (champsim::debug_print) {
						std::cout << "[" << NAME << "] " << __func__;
						std::cout << " instr_id: " << handle_pkt.instr_id << " address: " << std::hex << (handle_pkt.address >> OFFSET_BITS);
						std::cout << " full_addr: " << handle_pkt.address;
						std::cout << " full_v_addr: " << handle_pkt.v_address << std::dec;
#if defined SPLIT_STLB
						std::cout << " set: " << get_set_index(handle_pkt.address, handle_pkt.is_instr);
#elif defined TX_SPLIT_CACHE
						std::cout << " set: " << get_set_index(handle_pkt.address, handle_pkt.is_pte);
#else
						std::cout << " set: " << get_set_index(handle_pkt.address);
#endif
						std::cout << " way: " << std::distance(set_begin, way) << " (" << (hit ? "HIT" : "MISS") << ")";
						std::cout << " type: " << +handle_pkt.type;
						std::cout << " cycle: " << current_cycle << std::endl;
					}

					// update prefetcher on load instructions and prefetches from upper levels
					auto metadata_thru = handle_pkt.pf_metadata;
					if (should_activate_prefetcher(handle_pkt)) {
						uint64_t pf_base_addr = (virtual_prefetch ? handle_pkt.v_address : handle_pkt.address) & ~champsim::bitmask(match_offset_bits ? 0 : OFFSET_BITS);
						metadata_thru = impl_prefetcher_cache_operate(pf_base_addr, handle_pkt.ip, hit, handle_pkt.type, metadata_thru);
					}

#if defined TRANSLATION_EXCLUSIVE_CACHE
					if (handle_pkt.is_pte) {
						// we should also store the evicting address to last_pte_entry in the set (if it's pte)
#if defined SPLIT_STLB
						uint64_t set_idx = get_set_index(handle_pkt.address, fill_mshr.is_instr);
#elif defined TX_SPLIT_CACHE
						uint64_t set_idx = get_set_index(handle_pkt.address, handle_pkt.is_pte);
#else 
						uint64_t set_idx = get_set_index(handle_pkt.address);
#endif
						//set_idx = 0;
						last_pte_entry[set_idx] = handle_pkt.address;
					}
#endif

					if (hit) {

						sim_stats.back().hits[handle_pkt.type][handle_pkt.cpu]++;

#if defined ENABLE_EXTRA_CACHE_STATS
						hit_hook(handle_pkt);
#endif

						// update replacement policy
						const auto way_idx = static_cast<std::size_t>(std::distance(set_begin, way)); // cast protected by earlier assertion
#if defined ENABLE_TRANSLATION_AWARE_REPLACEMENT
						REP_POL_XARGS xargs;
						xargs.is_instr = handle_pkt.is_instr;
						xargs.is_pte = handle_pkt.is_pte;
						xargs.is_replay = !handle_pkt.is_translated;
						xargs.translation_level = handle_pkt.translation_level;
						xargs.access_freq = handle_pkt.access_freq;
	#if defined SPLIT_STLB
						impl_update_replacement_state(handle_pkt.cpu, get_set_index(handle_pkt.address, handle_pkt.is_instr), way_idx, 
																					handle_pkt.address, handle_pkt.ip, 0, 
																					handle_pkt.type, false, xargs);
	#elif defined TX_SPLIT_CACHE
						impl_update_replacement_state(handle_pkt.cpu, get_set_index(handle_pkt.address, handle_pkt.is_pte), way_idx, 
																					handle_pkt.address, handle_pkt.ip, 0, 
																					handle_pkt.type, false, xargs);
	#else 
						impl_update_replacement_state(handle_pkt.cpu, get_set_index(handle_pkt.address), way_idx, 
																					handle_pkt.address, handle_pkt.ip, 0, 
																					handle_pkt.type, false, xargs);
	#endif

#else

	#if defined SPLIT_STLB
						impl_update_replacement_state(handle_pkt.cpu, get_set_index(handle_pkt.address, handle_pkt.is_instr), way_idx, way->address, handle_pkt.ip, 0, handle_pkt.type, true);
	#elif defined TX_SPLIT_CACHE
						impl_update_replacement_state(handle_pkt.cpu, get_set_index(handle_pkt.address, handle_pkt.is_pte), way_idx, way->address, handle_pkt.ip, 0, handle_pkt.type, true);
	#else
						impl_update_replacement_state(handle_pkt.cpu, get_set_index(handle_pkt.address), way_idx, way->address, handle_pkt.ip, 0, handle_pkt.type, true);
	#endif 

#endif

						auto copy{handle_pkt};
						copy.data = way->data;
						copy.pf_metadata = metadata_thru;

#if defined ENABLE_PAGE_CROSSING_STATS
						if ((NAME.find("STLB") != std::string::npos) && (handle_pkt.page_crossing == 2)) {

							copy.page_crossing = 1;
						}
#endif  

						for (auto ret : copy.to_return)
							ret->return_data(copy);

						way->dirty = (handle_pkt.type == WRITE);
						// update prefetch stats and reset prefetch bit
						if (way->prefetch && !handle_pkt.prefetch_from_this) {
							sim_stats.back().pf_useful++;
							way->prefetch = false;
//#if defined(ENABLE_PAGE_CROSSING_STATS)
//							if (way->page_crossing == 2) sim_stats.back().pf_crossing_pages_tlb_miss++;
//							else if (way->page_crossing == 1) sim_stats.back().pf_crossing_pages_tlb_hit++;
//#endif
						}

#if defined TRANSLATION_EXCLUSIVE_CACHE
						// If we have a hit, we need to change doa status at the block in the cache
						//if (enable_tx_victim_cache) {
						way->is_doa = false;
						if (NAME.find(_CACHE_) != std::string::npos) {
							way->access_freq++; //FIXME: This is currently only for hits, need to handle misses as well
						}
						//}
#endif

					} else {

#if defined FORCE_HIT
						// Dimitrios: updating replacement policy doesn't really matter at this point
						// update replacement policy
				/*
							const auto way_idx = static_cast<std::size_t>(std::distance(set_begin, way)); // cast protected by earlier assertion
							impl_update_replacement_state(handle_pkt.cpu, get_set_index(handle_pkt.address), way_idx, way->address, handle_pkt.ip, 0, handle_pkt.type, true);
				*/
						auto copy_pkt{handle_pkt};
						bool hit_forced = false;

						if (NAME.find("STLB") != std::string::npos) {
							if ((force_hit) && !handle_pkt.is_instr) { //FIXME: 
								if (handle_pkt.translation_level == 0) {
									//std::tie(copy.data, penalty) = vmem->va_to_pa(handle_pkt.cpu, handle_pkt.v_address);
									copy_pkt.data = vmem->va_to_pa(handle_pkt.cpu, handle_pkt.v_address).first;
									hit_forced = true;
								}
								else	{
									std::cout << "Force hit not implemented for Caches." << std::endl;
									assert(false);
								}		
							}
						}

						if (NAME.find("L1D") != std::string::npos) {
							if (force_hit && (handle_pkt.is_pte)) {
								//copy.data = vmem->get_pte_pa(handle_pkt.cpu, handle_pkt.v_address, handle_pkt.translation_level).first;
								auto it = cached_PTEs.find(handle_pkt.address);
								if (it != cached_PTEs.end()) {
									copy_pkt.data = (it->second).data;
									hit_forced = true;	
								}
							}
						} 

						if (hit_forced) { 

							sim_stats.back().hits[handle_pkt.type][handle_pkt.cpu]++;

	#if defined ENABLE_EXTRA_CACHE_STATS
							hit_hook(handle_pkt);
	#endif
							
							copy_pkt.pf_metadata = metadata_thru;
							for (auto ret : copy_pkt.to_return)
								ret->return_data(copy_pkt);

							/*
								* Dimitrios: not necessary for TLBs and PTEs, but we can leave it, it should always be false
								* way->dirty = (handle_pkt.type == WRITE);
								*
								*	// Dimitrios: useless too 
								*	// update prefetch stats and reset prefetch bit
								*	if (way->prefetch && !handle_pkt.prefetch_from_this) {
								*		sim_stats.back().pf_useful++;
								*		way->prefetch = false;
								*	}
								*
								*/
								
							return true; //forcing hit
						}
#endif // FORCED_HIT			
#if 0 //defined TRANSLATION_EXCLUSIVE_CACHE

						if (NAME.find(_CACHE_) != std::string::npos) {
							//PACKET txc_copy_pkt{handle_pkt};
							bool entry_found = false;
							
							bool vc_entry_cond;
							if (enable_instr_only)
								vc_entry_cond = handle_pkt.is_pte && handle_pkt.is_instr;
							else if (enable_data_only)
								vc_entry_cond = handle_pkt.is_pte && !handle_pkt.is_instr;
							else 
								vc_entry_cond = handle_pkt.is_pte;
							
							if (enable_tx_victim_cache && vc_entry_cond) {

								auto [_entry, _entry_found] = tx_victim_cache->lookup(handle_pkt.address, handle_pkt.is_instr, current_cycle, handle_pkt.ip);
								entry_found = _entry_found;
								//copy_pkt.data = _entry.data;

								if (entry_found) { 

									PACKET txvc_mshr_packet;
									txvc_mshr_packet.address = handle_pkt.address;
									txvc_mshr_packet.type = handle_pkt.type;
									txvc_mshr_packet.is_instr = handle_pkt.is_instr;
									txvc_mshr_packet.cpu = 0; // Possible issue for multicore
									txvc_mshr_packet.address = _entry.address;
									txvc_mshr_packet.data = _entry.data;
									txvc_mshr_packet.instr_id = handle_pkt.instr_id;
									txvc_mshr_packet.ip = handle_pkt.ip;
									txvc_mshr_packet.type = handle_pkt.type;
									txvc_mshr_packet.pf_metadata = _entry.pf_metadata; // not sure

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT
									txvc_mshr_packet.is_instr = _entry.is_instr;
									txvc_mshr_packet.is_pte = _entry.is_pte;
#endif	

#if defined MULTIPLE_PAGE_SIZE
									txvc_mshr_packet.page_size = _entry.page_size;
									txvc_mshr_packet.base_vpn = _entry.base_vpn;
#endif
 			
									handle_fill(txvc_mshr_packet);
								
									//return true; // This skips pushing the miss to the L2C
								}
							}
						} 
#endif
#if 0 //defined TRANSLATION_EXCLUSIVE_CACHE
						// Dimitrios: updating replacement policy doesn't really matter at this point
						// update replacement policy
				/*
							const auto way_idx = static_cast<std::size_t>(std::distance(set_begin, way)); // cast protected by earlier assertion
							impl_update_replacement_state(handle_pkt.cpu, get_set_index(handle_pkt.address), way_idx, way->address, handle_pkt.ip, 0, handle_pkt.type, true);
				*/
						if (NAME.find(_CACHE_) != std::string::npos) {
							PACKET txc_copy_pkt{handle_pkt};
							bool entry_found = false;
							//FIXME: NEED TO ADD CHECK FRO ONLY DATA/INSTR
							if (enable_tx_victim_cache && (handle_pkt.is_pte)) {
								//std::cout << "looking address: " << way->address << std::endl; 
								//copy.data = vmem->get_pte_pa(handle_pkt.cpu, handle_pkt.v_address, handle_pkt.translation_level).first;
								/*
								auto it = tx_victim_cache.find(handle_pkt.address);
								if (it != tx_victim_cache.end()) {
									//std::cout << "Found it!" << std::endl;
									copy_pkt.data = (it->second).data;
									entry_found = true;	
								}
								*/
								auto [_entry, _entry_found] = tx_victim_cache->lookup(handle_pkt.address, handle_pkt.is_instr, current_cycle, handle_pkt.ip);
								entry_found = _entry_found;
								//std::cout << "segfault" << std::endl;	
								copy_pkt.data = _entry.data;
								//std::cout << "moving on..." << std::endl;
							}

							if (entry_found) { 

								sim_stats.back().hits[handle_pkt.type][handle_pkt.cpu]++;

	#if defined ENABLE_EXTRA_CACHE_STATS
								hit_hook(handle_pkt);
	#endif
					
								txc_copy_pkt.pf_metadata = metadata_thru;
								for (auto ret : txc_copy_pkt.to_return)
									ret->return_data(txc_copy_pkt);
								
								return true; //forcing hit
							}
						} 
#endif		

#if defined MULTIPLE_PAGE_SIZE
						//TODO: Lookup entire TLB in case of large pages
						// 			Ignore caches for now
						if (NAME.find("STLB") != std::string::npos 
								|| NAME.find("DTLB") != std::string::npos 
								|| NAME.find("ITLB") != std::string::npos) {
							if (handle_pkt.page_size == 2) { // this is a large page!
								//std::cout << "OoOo, we got a laaarge page on our hands boys!" << std::endl;
								//std::cout << "\tLooking up in the entire cache for the base vpn..." << std::endl;
								for (unsigned int i = 0; i < (NUM_SET * NUM_WAY); i++) {
									//std::cout << "block@" << std::hex << block[i].base_vpn << " =? pkt@" 
									//					<< handle_pkt.base_vpn << std::dec << std::endl;
									if (block[i].base_vpn == handle_pkt.base_vpn) {
										// Need to handle this as a hit
										//std::cout << "Found it!" << std::endl;
										
										auto copy{handle_pkt}; // the warning related to line 454 is not important, we can shadow the variable here

										if (handle_pkt.translation_level == 0) {
											copy.data = vmem->va_to_pa(handle_pkt.cpu, handle_pkt.v_address).first;
										}
										assert(handle_pkt.translation_level == 0);

										sim_stats.back().hits[handle_pkt.type][handle_pkt.cpu]++;
	
										#if defined ENABLE_EXTRA_CACHE_STATS
										hit_hook(handle_pkt);
	#endif

										copy.pf_metadata = metadata_thru;
										for (auto ret : copy.to_return)
										ret->return_data(copy);

										return true;
									}
								}
								//std::cout << "Not found, continuing as miss." << std::endl; 
							} else {
								//std::cout << "Yet another small pen...page, I meant page!" << std::endl;
							}
						}
#endif // MULTIPLE_PAGE_SIZE

						sim_stats.back().misses[handle_pkt.type][handle_pkt.cpu]++;

#if defined PTP_REPLACEMENT_POLICY
						if (NAME.find("STLB") != std::string::npos) {
							//uint32_t total_accesses = sim_stats.back().misses[handle_pkt.type][handle_pkt.cpu] + sim_stats.back().hits[handle_pkt.type][handle_pkt.cpu];
							uint32_t total_misses = sim_stats.back().misses[handle_pkt.type][handle_pkt.cpu];
							//double miss_ratio  = static_cast<double>(total_misses) / static_cast<double>(total_accesses);
							//TODO: add a polling mechanism, to avoid running this every time
							//vmem->STLB_MISS_RATE = std::round( (100*miss_ratio) * 0.5f ) * 2;
							double retired_instrs = static_cast<double>(RETIRED_INSTRS);
							STLB_MPKI = (static_cast<double>(total_misses) * 1000.0) / retired_instrs;
							//std::cout << "STLB_MPKI:" << STLB_MPKI << std::endl; 
							//std::cout << "STLB_MISS_RATE:" << vmem->STLB_MISS_RATE << std::endl; 
						}
#endif

#if defined ENABLE_EXTRA_CACHE_STATS
						miss_hook(handle_pkt);
#endif

					}

					return hit;
				}

				bool CACHE::handle_miss(const PACKET& handle_pkt)
				{
					if constexpr (champsim::debug_print) {
						std::cout << "[" << NAME << "] " << __func__;
						std::cout << " instr_id: " << handle_pkt.instr_id << " address: " << std::hex << (handle_pkt.address >> OFFSET_BITS);
						std::cout << " full_addr: " << handle_pkt.address;
						std::cout << " full_v_addr: " << handle_pkt.v_address << std::dec;
						std::cout << " type: " << +handle_pkt.type;
						std::cout << " local_prefetch: " << std::boolalpha << handle_pkt.prefetch_from_this << std::noboolalpha;
						std::cout << " cycle: " << current_cycle << std::endl;
					}

					cpu = handle_pkt.cpu;

#if defined TRANSLATION_EXCLUSIVE_CACHE
					BLOCK txvc_block_entry;
					bool entry_found = false;
					if (NAME.find(_CACHE_) != std::string::npos) {
						//PACKET txc_copy_pkt{handle_pkt};
							
						bool vc_entry_cond;
						if (enable_instr_only)
							vc_entry_cond = handle_pkt.is_pte && handle_pkt.is_instr;
						else if (enable_data_only)
							vc_entry_cond = handle_pkt.is_pte && !handle_pkt.is_instr;
						else 
							vc_entry_cond = handle_pkt.is_pte;
							
						if (enable_tx_victim_cache && vc_entry_cond) {

							auto [_entry, _entry_found] = tx_victim_cache->lookup(handle_pkt.address, handle_pkt.is_instr, current_cycle, handle_pkt.ip);
							entry_found = _entry_found;
							txvc_block_entry = _entry;
							//copy_pkt.data = _entry.data;
						}
					}
#endif

					// check mshr
					auto mshr_entry = std::find_if(MSHR.begin(), MSHR.end(), eq_addr<PACKET>(handle_pkt.address, OFFSET_BITS));
					bool mshr_full = (MSHR.size() == MSHR_SIZE);

					if (mshr_entry != MSHR.end()) // miss already inflight
					{
						auto instr_copy = std::move(mshr_entry->instr_depend_on_me);
						auto ret_copy = std::move(mshr_entry->to_return);

						std::set_union(std::begin(instr_copy), std::end(instr_copy), std::begin(handle_pkt.instr_depend_on_me), std::end(handle_pkt.instr_depend_on_me),
													 std::back_inserter(mshr_entry->instr_depend_on_me), ooo_model_instr::program_order);
						std::set_union(std::begin(ret_copy), std::end(ret_copy), std::begin(handle_pkt.to_return), std::end(handle_pkt.to_return),
													 std::back_inserter(mshr_entry->to_return));

						if (mshr_entry->type == PREFETCH && handle_pkt.type != PREFETCH) {
							// Mark the prefetch as useful
							if (mshr_entry->prefetch_from_this)
								sim_stats.back().pf_useful++;

							uint64_t prior_event_cycle = mshr_entry->event_cycle;
							auto to_return = std::move(mshr_entry->to_return);
							*mshr_entry = handle_pkt;

							// in case request is already returned, we should keep event_cycle
							mshr_entry->event_cycle = prior_event_cycle;
							mshr_entry->cycle_enqueued = current_cycle;
							mshr_entry->to_return = std::move(to_return);
#if defined ENABLE_PAGE_CROSSING_STATS
							mshr_entry->page_crossing = 0;
#endif 
						}
					} else {
						if (mshr_full)  // not enough MSHR resource
							return false; // TODO should we allow prefetches anyway if they will not be filled to this level?

						auto fwd_pkt = handle_pkt;

						if (fwd_pkt.type == WRITE)
							fwd_pkt.type = RFO;

						if (handle_pkt.fill_this_level)
							fwd_pkt.to_return = {this};
						else
							fwd_pkt.to_return.clear();

						fwd_pkt.fill_this_level = true; // We will always fill the lower level
						fwd_pkt.prefetch_from_this = false;
#if defined TRANSLATION_EXCLUSIVE_CACHE
							
						if (!entry_found) {
							bool success = false;
							if (prefetch_as_load || handle_pkt.type != PREFETCH)
								success = lower_level->add_rq(fwd_pkt);
							else
								success = lower_level->add_pq(fwd_pkt);

							if (!success)
								return false;
						}
#else
						bool success = false;
						if (prefetch_as_load || handle_pkt.type != PREFETCH)
							success = lower_level->add_rq(fwd_pkt);
						else
							success = lower_level->add_pq(fwd_pkt);

						if (!success)
							return false;
#endif

						// Allocate an MSHR
						if (!std::empty(fwd_pkt.to_return)) {
							mshr_entry = MSHR.insert(std::end(MSHR), handle_pkt);
							mshr_entry->pf_metadata = fwd_pkt.pf_metadata;
							mshr_entry->cycle_enqueued = current_cycle;
							mshr_entry->event_cycle = std::numeric_limits<uint64_t>::max();
#if defined ENABLE_PAGE_CROSSING_STATS
							mshr_entry->page_crossing = fwd_pkt.page_crossing;
#endif
						}
					}

#if defined TRANSLATION_EXCLUSIVE_CACHE
					if (NAME.find(_CACHE_) != std::string::npos) {
						//PACKET txc_copy_pkt{handle_pkt};
						//bool entry_found = false;
						/*	
						bool vc_entry_cond;
						if (enable_instr_only)
							vc_entry_cond = handle_pkt.is_pte && handle_pkt.is_instr;
						else if (enable_data_only)
						vc_entry_cond = handle_pkt.is_pte && !handle_pkt.is_instr;
							auto [_entry, _entry_found] = tx_victim_cache->lookup(handle_pkt.address, handle_pkt.is_instr, current_cycle, handle_pkt.ip);
							entry_found = _entry_found;
							//copy_pkt.data = _entry.data;
						*/
							if (entry_found) { 

								PACKET txvc_mshr_packet;
								txvc_mshr_packet.address = handle_pkt.address;
								txvc_mshr_packet.type = handle_pkt.type;
								txvc_mshr_packet.is_instr = handle_pkt.is_instr;
								txvc_mshr_packet.cpu = 0; // Possible issue for multicore
								txvc_mshr_packet.address = txvc_block_entry.address;
								txvc_mshr_packet.data = txvc_block_entry.data;
								txvc_mshr_packet.instr_id = handle_pkt.instr_id;
								txvc_mshr_packet.ip = handle_pkt.ip;
								txvc_mshr_packet.type = handle_pkt.type;
								txvc_mshr_packet.pf_metadata = txvc_block_entry.pf_metadata; // not sure

#if defined ENABLE_EXTRA_CACHE_STATS || defined FORCE_HIT
								txvc_mshr_packet.is_instr = txvc_block_entry.is_instr;
								txvc_mshr_packet.is_pte = txvc_block_entry.is_pte;
								txvc_mshr_packet.translation_level = txvc_block_entry.pte_level;
								//txvc_mshr_packet.access_freq = txvc_block_entry.access_freq;
#endif	

#if defined MULTIPLE_PAGE_SIZE
								txvc_mshr_packet.page_size = txvc_block_entry.page_size;
								txvc_mshr_packet.base_vpn = txvc_block_entry.base_vpn;
#endif
 			
								//handle_fill(txvc_mshr_packet);
								//txc_copy_pkt.pf_metadata = metadata_thru;
								//for (auto ret : txc_copy_pkt.to_return)
								return_data(txvc_mshr_packet);
								//return true; // This skips pushing the miss to the L2C
							}
						//}
					} 
#endif

					//sim_stats.back().misses[handle_pkt.type][handle_pkt.cpu]++;
					return true;
				}

				bool CACHE::handle_write(const PACKET& handle_pkt)
				{
					if constexpr (champsim::debug_print) {
						std::cout << "[" << NAME << "] " << __func__;
						std::cout << " instr_id: " << handle_pkt.instr_id;
						std::cout << " full_addr: " << std::hex << handle_pkt.address;
						std::cout << " full_v_addr: " << handle_pkt.v_address << std::dec;
						std::cout << " type: " << +handle_pkt.type;
						std::cout << " local_prefetch: " << std::boolalpha << handle_pkt.prefetch_from_this << std::noboolalpha;
						std::cout << " cycle: " << current_cycle << std::endl;
					}

					inflight_writes.push_back(handle_pkt);
					inflight_writes.back().event_cycle = current_cycle + (warmup ? 0 : FILL_LATENCY);
					inflight_writes.back().cycle_enqueued = current_cycle;

					//sim_stats.back().misses[handle_pkt.type][handle_pkt.cpu]++;
					return true;
				}

				template <typename R, typename F>
				long int operate_queue(R& queue, long int sz, F&& func)
				{
					auto [begin, end] = champsim::get_span_p(std::cbegin(queue), std::cend(queue), sz, std::forward<F>(func));
					auto retval = std::distance(begin, end);
					queue.erase(begin, end);
					return retval;
				}

				void CACHE::operate()
				{

#if defined TRANSLATION_EXCLUSIVE_CACHE
					//std::cout << "operate" << std::endl;
					//FIXME: Not sure if we should operate the cache_queue as well
					//if (enable_tx_cache || enable_tx_victim_cache) {
					//	tx_cache->queues.operate(); //FIXME: Not sure about this line
					//	tx_cache->operate();
					//}
#endif

					auto tag_bw = MAX_TAG;
					auto fill_bw = MAX_FILL;

					auto do_fill = [cycle = current_cycle, this](const auto& x) {
						return x.event_cycle <= cycle && this->handle_fill(x);
					};

					auto operate_readlike = [&, this](const auto& pkt) {
						return queues.is_ready(pkt) && (this->try_hit(pkt) || this->handle_miss(pkt));
					};

					auto operate_writelike = [&, this](const auto& pkt) {
						return queues.is_ready(pkt) && (this->try_hit(pkt) || this->handle_write(pkt));
					};

					for (auto q : {std::ref(MSHR), std::ref(inflight_writes)})
						fill_bw -= operate_queue(q.get(), fill_bw, do_fill);

					if (match_offset_bits) {
						// Treat writes (that is, stores) like reads
						for (auto q : {std::ref(queues.WQ), std::ref(queues.PTWQ), std::ref(queues.RQ), std::ref(queues.PQ)})
							tag_bw -= operate_queue(q.get(), tag_bw, operate_readlike);
					} else {
						// Treat writes (that is, writebacks) like fills
						tag_bw -= operate_queue(queues.WQ, tag_bw, operate_writelike);

						for (auto q : {std::ref(queues.PTWQ), std::ref(queues.RQ), std::ref(queues.PQ)}) {
							tag_bw -= operate_queue(q.get(), tag_bw, operate_readlike);
						}
					}

					impl_prefetcher_cycle_operate();

				}

#if defined SPLIT_STLB

	uint64_t CACHE::get_set(uint64_t address, uint8_t type) const { return get_set_index(address, type); }

	std::size_t CACHE::get_set_index(uint64_t address, uint8_t type) const { 

	/*
		if (NAME.find("STLB") != std::string::npos) {
			std::cout << "address:" << address << " (" << std::bitset<64>(address) << ")" << std::endl;
			std::cout << "OFFSET_BITS:" << OFFSET_BITS << std::endl;
			std::cout << "OFFSETTED ADDRESS:" << (address >> OFFSET_BITS) << " (" << std::bitset<64>((address >> OFFSET_BITS)) << ")" << std::endl; 
			std::cout << "bitmask:" << champsim::bitmask(champsim::lg2(NUM_SET)) << " (" << std::bitset<64>(champsim::bitmask(champsim::lg2(NUM_SET))) << std::endl;
			std::cout << "old set:" << ((address >> OFFSET_BITS) & champsim::bitmask(champsim::lg2(NUM_SET))) << std::endl; 

			std::cout << "bitmask:" << champsim::bitmask(champsim::lg2(NUM_SET))/2 << " (" << std::bitset<64>(champsim::bitmask(champsim::lg2(NUM_SET))/2) << std::endl;
			std::cout << "new set:" << ((address >> OFFSET_BITS) & champsim::bitmask((champsim::lg2(NUM_SET))/2)) << std::endl; 
		}
	*/
		std::size_t orig_set = (address >> OFFSET_BITS) & champsim::bitmask(champsim::lg2(NUM_SET)); 

		if (NAME.find("STLB") != std::string::npos) {

			if (type == 0) {
				return orig_set % (NUM_SET/2);
			} else {
				return (orig_set < (NUM_SET/2))?(orig_set+(NUM_SET/2)):orig_set;
			}
		}
		return orig_set;
	}

	template <typename It>
	std::pair<It, It> get_span(It anchor, typename std::iterator_traits<It>::difference_type set_idx, typename std::iterator_traits<It>::difference_type num_way)
	{
		auto begin = std::next(anchor, set_idx * num_way);
		return {std::move(begin), std::next(begin, num_way)};
	}

	auto CACHE::get_set_span(uint64_t address, uint8_t type) -> std::pair<std::vector<BLOCK>::iterator, std::vector<BLOCK>::iterator>
	{
		const auto set_idx = get_set_index(address, type);
		assert(set_idx < NUM_SET);
		return get_span(std::begin(block), static_cast<std::vector<BLOCK>::difference_type>(set_idx), NUM_WAY); // safe cast because of prior assert
	}

	auto CACHE::get_set_span(uint64_t address, uint8_t type) const -> std::pair<std::vector<BLOCK>::const_iterator, std::vector<BLOCK>::const_iterator>
	{
		const auto set_idx = get_set_index(address, type);
		assert(set_idx < NUM_SET);
		return get_span(std::cbegin(block), static_cast<std::vector<BLOCK>::difference_type>(set_idx), NUM_WAY); // safe cast because of prior assert
	}

	uint64_t CACHE::get_way(uint64_t address, uint8_t type, uint64_t) const
	{
		auto [begin, end] = get_set_span(address, type);
		return std::distance(begin, std::find_if(begin, end, eq_addr<BLOCK>(address, OFFSET_BITS)));
	}

	uint64_t CACHE::invalidate_entry(uint64_t inval_addr, uint8_t type)
	{
		auto [begin, end] = get_set_span(inval_addr, type);
		auto inv_way = std::find_if(begin, end, eq_addr<BLOCK>(inval_addr, OFFSET_BITS));

		if (inv_way != end)
			inv_way->valid = 0;

		return std::distance(begin, inv_way);
	}

#elif defined TX_SPLIT_CACHE

	uint64_t CACHE::get_set(uint64_t address, uint8_t type) const { return get_set_index(address, type); }

	std::size_t CACHE::get_set_index(uint64_t address, uint8_t type) const 
	{   

		if (enable_tx_split_cache) {

			uint64_t CACHE_NUM_SET = NUM_SET - TX_NUM_SET;

			if (type == 0) {
				return _get_set_index(address, CACHE_NUM_SET);
			} else {
				return CACHE_NUM_SET + _get_set_index(address, TX_NUM_SET);
			}
		
		} else {

			return _get_set_index(address, NUM_SET);
		}
		
	}

	std::size_t CACHE::_get_set_index(uint64_t address, uint32_t num_set) const 
	{
		//if (champsim::is_power_of_two(num_set))
		//	return (address >> OFFSET_BITS) & champsim::bitmask(log2(num_set));
			
		return (address >> OFFSET_BITS) % num_set;
		
		// If not a power of two, use Barrett reduction
    	__uint128_t t = ( __uint128_t)address * barret_reciprocal;
    	std::size_t q = (std::size_t)(t >> 64);
    	std::size_t r = address - q * num_set;

    	// At most two corrections needed
    	if (r >= num_set) r -= num_set;
    	if (r >= num_set) r -= num_set;

    	return r;
		
	}

	template <typename It>
	std::pair<It, It> get_span(It anchor, typename std::iterator_traits<It>::difference_type set_idx, typename std::iterator_traits<It>::difference_type num_way)
	{
		auto begin = std::next(anchor, set_idx * num_way);
		return {std::move(begin), std::next(begin, num_way)};
	}

	auto CACHE::get_set_span(uint64_t address, uint8_t type) -> std::pair<std::vector<BLOCK>::iterator, std::vector<BLOCK>::iterator>
	{
		const auto set_idx = get_set_index(address, type);
		assert(set_idx < NUM_SET);
		touched_indices[set_idx]++;
		return get_span(std::begin(block), static_cast<std::vector<BLOCK>::difference_type>(set_idx), NUM_WAY); // safe cast because of prior assert
	}

	auto CACHE::get_set_span(uint64_t address, uint8_t type) const -> std::pair<std::vector<BLOCK>::const_iterator, std::vector<BLOCK>::const_iterator>
	{
		const auto set_idx = get_set_index(address, type);
		assert(set_idx < NUM_SET);
		return get_span(std::cbegin(block), static_cast<std::vector<BLOCK>::difference_type>(set_idx), NUM_WAY); // safe cast because of prior assert
	}

	uint64_t CACHE::get_way(uint64_t address, uint8_t type, uint64_t) const
	{
		auto [begin, end] = get_set_span(address, type);
		return std::distance(begin, std::find_if(begin, end, eq_addr<BLOCK>(address, OFFSET_BITS)));
	}

	uint64_t CACHE::invalidate_entry(uint64_t inval_addr, uint8_t type)
	{
		auto [begin, end] = get_set_span(inval_addr, type);
		auto inv_way = std::find_if(begin, end, eq_addr<BLOCK>(inval_addr, OFFSET_BITS));

		if (inv_way != end)
			inv_way->valid = 0;

		return std::distance(begin, inv_way);
	}

#else

	uint64_t CACHE::get_set(uint64_t address) const { return get_set_index(address); }

	std::size_t CACHE::get_set_index(uint64_t address) const 
	{ 
		//return (address >> OFFSET_BITS) & champsim::bitmask(champsim::lg2(NUM_SET)); 
		return _get_set_index(address, NUM_SET);
	}

	std::size_t CACHE::_get_set_index(uint64_t address, uint32_t num_set) const 
	{
		//if (champsim::is_power_of_two(num_set))
		//	return (address >> OFFSET_BITS) & champsim::bitmask(log2(num_set));
			
		return (address >> OFFSET_BITS) % num_set;
		
	}

	template <typename It>
	std::pair<It, It> get_span(It anchor, typename std::iterator_traits<It>::difference_type set_idx, typename std::iterator_traits<It>::difference_type num_way)
	{
		auto begin = std::next(anchor, set_idx * num_way);
		return {std::move(begin), std::next(begin, num_way)};
	}

	auto CACHE::get_set_span(uint64_t address) -> std::pair<std::vector<BLOCK>::iterator, std::vector<BLOCK>::iterator>
	{
		const auto set_idx = get_set_index(address);
		assert(set_idx < NUM_SET);
		touched_indices[set_idx]++;
		return get_span(std::begin(block), static_cast<std::vector<BLOCK>::difference_type>(set_idx), NUM_WAY); // safe cast because of prior assert
	}

	auto CACHE::get_set_span(uint64_t address) const -> std::pair<std::vector<BLOCK>::const_iterator, std::vector<BLOCK>::const_iterator>
	{
		const auto set_idx = get_set_index(address);
		assert(set_idx < NUM_SET);
		return get_span(std::cbegin(block), static_cast<std::vector<BLOCK>::difference_type>(set_idx), NUM_WAY); // safe cast because of prior assert
	}

	uint64_t CACHE::get_way(uint64_t address, uint64_t) const
	{
		auto [begin, end] = get_set_span(address);
		return std::distance(begin, std::find_if(begin, end, eq_addr<BLOCK>(address, OFFSET_BITS)));
	}

	uint64_t CACHE::invalidate_entry(uint64_t inval_addr)
	{
		auto [begin, end] = get_set_span(inval_addr);
		auto inv_way = std::find_if(begin, end, eq_addr<BLOCK>(inval_addr, OFFSET_BITS));

		if (inv_way != end)
			inv_way->valid = 0;

		return std::distance(begin, inv_way);
	}

#endif 


bool CACHE::add_rq(const PACKET& packet)
{
  if constexpr (champsim::debug_print) {
    std::cout << "[" << NAME << "_RQ] " << __func__ << " instr_id: " << packet.instr_id << " address: " << std::hex << (packet.address >> OFFSET_BITS);
    std::cout << " full_addr: " << packet.address << " v_address: " << packet.v_address << std::dec << " type: " << +packet.type
              << " occupancy: " << std::size(queues.RQ) << " current_cycle: " << current_cycle << std::endl;
  }

  return queues.add_rq(packet);
}

bool CACHE::add_wq(const PACKET& packet)
{
  if constexpr (champsim::debug_print) {
    std::cout << "[" << NAME << "_WQ] " << __func__ << " instr_id: " << packet.instr_id << " address: " << std::hex << (packet.address >> OFFSET_BITS);
    std::cout << " full_addr: " << packet.address << " v_address: " << packet.v_address << std::dec << " type: " << +packet.type
              << " occupancy: " << std::size(queues.WQ) << " current_cycle: " << current_cycle << std::endl;
  }

  return queues.add_wq(packet);
}

bool CACHE::add_ptwq(const PACKET& packet)
{
  if constexpr (champsim::debug_print) {
    std::cout << "[" << NAME << "_PTWQ] " << __func__ << " instr_id: " << packet.instr_id << " address: " << std::hex << (packet.address >> OFFSET_BITS);
    std::cout << " full_addr: " << packet.address << " v_address: " << packet.v_address << std::dec << " type: " << +packet.type
              << " occupancy: " << std::size(queues.PTWQ) << " current_cycle: " << current_cycle;
  }

  return queues.add_ptwq(packet);
}

int CACHE::prefetch_line(uint64_t pf_addr, bool fill_this_level, uint32_t prefetch_metadata)
{
  sim_stats.back().pf_requested++;

  PACKET pf_packet;
  pf_packet.type = PREFETCH;
  pf_packet.prefetch_from_this = true;
  pf_packet.fill_this_level = fill_this_level;
  pf_packet.pf_metadata = prefetch_metadata;
  pf_packet.cpu = cpu;
  pf_packet.address = pf_addr;
  pf_packet.v_address = virtual_prefetch ? pf_addr : 0;

#if defined ENABLE_PAGE_CROSSING_STATS
	pf_packet.page_crossing = prefetch_metadata ? 2 : 0;
#endif


#if defined ENABLE_EXTRA_CACHE_STATS
	//FIXME: This works only without prefetchers, otherwise all PREFETCH accesses 
	// cannot be accounted as instr or not
	//pf_packet.is_instr = xx;
	// this is a fix for getting the is_instr value, but this doesn't work for
	// prefetches which are issued by L2C (we don't care for them however, since 
	// they go to main memory)
	pf_packet.is_pte = false;
	pf_packet.access_freq = 0;

	if (NAME.find("L1I") != std::string::npos) {
		pf_packet.is_instr = true;
	}	else if (NAME.find("L1D") == std::string::npos) {
		pf_packet.is_instr = false;
	}
	//assert(NAME.compare("cpu0_ITLB") != 0);
	//assert(NAME.compare("cpu0_DTLB") != 0);
	//assert(NAME.compare("cpu0_STLB") != 0);
#endif

#if defined(MULTIPLE_PAGE_SIZE)
	if (NAME.find("L1I") != std::string::npos) {
		pf_packet.page_size = PAGE_SIZE;
		pf_packet.base_vpn = pf_addr;
	} else if (NAME.find("L1D") != std::string::npos) {
		//FIXME:
		pf_packet.page_size = PAGE_SIZE;
		pf_packet.base_vpn = pf_addr;
	}
#endif

  auto success = this->add_pq(pf_packet);
  if (success) {
    ++sim_stats.back().pf_issued;
		if (pf_packet.pf_metadata == 1)
			++sim_stats.back().pf_crossed;
	}
  return success;
}

int CACHE::prefetch_line(uint64_t, uint64_t, uint64_t pf_addr, bool fill_this_level, uint32_t prefetch_metadata)
{
  return prefetch_line(pf_addr, fill_this_level, prefetch_metadata);
}

bool CACHE::add_pq(const PACKET& packet)
{
  if constexpr (champsim::debug_print) {
    std::cout << "[" << NAME << "_PQ] " << __func__ << " instr_id: " << packet.instr_id << " address: " << std::hex << (packet.address >> OFFSET_BITS);
    std::cout << " full_addr: " << packet.address << " v_address: " << packet.v_address << std::dec << " type: " << +packet.type
              << " from this: " << std::boolalpha << packet.prefetch_from_this << std::noboolalpha << " occupancy: " << std::size(queues.PQ)
              << " current_cycle: " << current_cycle;
  }

  return queues.add_pq(packet);
}

void CACHE::return_data(const PACKET& packet)
{
  // check MSHR information
  auto mshr_entry = std::find_if(MSHR.begin(), MSHR.end(), eq_addr<PACKET>(packet.address, OFFSET_BITS));
  auto first_unreturned = std::find_if(MSHR.begin(), MSHR.end(), [](auto x) { return x.event_cycle == std::numeric_limits<uint64_t>::max(); });

  // sanity check
  if (mshr_entry == MSHR.end()) {
#if defined TRANSLATION_EXCLUSIVE_CACHE
		//MSHR.erase(mshr_entry);
		return;
#else
    std::cerr << "[" << NAME << "_MSHR] " << __func__ << " instr_id: " << packet.instr_id << " cannot find a matching entry!";
    std::cerr << " address: " << std::hex << packet.address;
    std::cerr << " v_address: " << packet.v_address;
    std::cerr << " address: " << (packet.address >> OFFSET_BITS) << std::dec;
    std::cerr << " event: " << packet.event_cycle << " current: " << current_cycle << std::endl;
    assert(0);
#endif
	}

  // MSHR holds the most updated information about this request
  mshr_entry->data = packet.data;
  mshr_entry->pf_metadata = packet.pf_metadata;
  mshr_entry->event_cycle = current_cycle + (warmup ? 0 : FILL_LATENCY);

  if constexpr (champsim::debug_print) {
    std::cout << "[" << NAME << "_MSHR] " << __func__ << " instr_id: " << mshr_entry->instr_id;
    std::cout << " address: " << std::hex << mshr_entry->address;
    std::cout << " data: " << mshr_entry->data << std::dec;
    std::cout << " event: " << mshr_entry->event_cycle << " current: " << current_cycle << std::endl;
  }

  // Order this entry after previously-returned entries, but before non-returned
  // entries
  std::iter_swap(mshr_entry, first_unreturned);
}

std::size_t CACHE::get_occupancy(uint8_t queue_type, uint64_t)
{
  if (queue_type == 0)
    return std::size(MSHR);
  else if (queue_type == 1)
    return std::size(queues.RQ);
  else if (queue_type == 2)
    return std::size(queues.WQ);
  else if (queue_type == 3)
    return std::size(queues.PQ);

  return 0;
}

std::size_t CACHE::get_size(uint8_t queue_type, uint64_t)
{
  if (queue_type == 0)
    return MSHR_SIZE;
  else if (queue_type == 1)
    return queues.RQ_SIZE;
  else if (queue_type == 2)
    return queues.WQ_SIZE;
  else if (queue_type == 3)
    return queues.PQ_SIZE;
  else if (queue_type == 4)
    return queues.PTWQ_SIZE;

  return 0;
}

void CACHE::initialize()
{
  impl_prefetcher_initialize();
  impl_initialize_replacement();
#if defined TRANSLATION_EXCLUSIVE_CACHE
	//if (enable_tx_cache || enable_tx_victim_cache) {
	//	tx_cache->initialize();
	//}
#endif
}

void CACHE::begin_phase()
{
#if defined TRANSLATION_EXCLUSIVE_CACHE
	//if (enable_tx_cache || enable_tx_victim_cache) {
	//	tx_cache->queues.begin_phase();
	//	tx_cache->begin_phase();
	//}
#endif 
  roi_stats.emplace_back();
  sim_stats.emplace_back();

  roi_stats.back().name = NAME;
  sim_stats.back().name = NAME;
}

void CACHE::end_phase(unsigned finished_cpu)
{

#if defined TRANSLATION_EXCLUSIVE_CACHE
	//if (enable_tx_cache || enable_tx_victim_cache) {
	//	tx_cache->queues.end_phase(finished_cpu);
	//	tx_cache->end_phase(finished_cpu);
	//}
#endif 

  for (auto type : {LOAD, RFO, PREFETCH, WRITE, TRANSLATION}) {
    roi_stats.back().hits.at(type).at(finished_cpu) = sim_stats.back().hits.at(type).at(finished_cpu);
    roi_stats.back().misses.at(type).at(finished_cpu) = sim_stats.back().misses.at(type).at(finished_cpu);
#if defined ENABLE_EXTRA_CACHE_STATS
		roi_stats.back().ihits.at(type).at(finished_cpu) = sim_stats.back().ihits.at(type).at(finished_cpu);
    roi_stats.back().imisses.at(type).at(finished_cpu) = sim_stats.back().imisses.at(type).at(finished_cpu);
		roi_stats.back().dhits.at(type).at(finished_cpu) = sim_stats.back().dhits.at(type).at(finished_cpu);
    roi_stats.back().dmisses.at(type).at(finished_cpu) = sim_stats.back().dmisses.at(type).at(finished_cpu);
		roi_stats.back().ithits.at(type).at(finished_cpu) = sim_stats.back().ithits.at(type).at(finished_cpu);
    roi_stats.back().itmisses.at(type).at(finished_cpu) = sim_stats.back().itmisses.at(type).at(finished_cpu);
		roi_stats.back().dthits.at(type).at(finished_cpu) = sim_stats.back().dthits.at(type).at(finished_cpu);
    roi_stats.back().dtmisses.at(type).at(finished_cpu) = sim_stats.back().dtmisses.at(type).at(finished_cpu);

		roi_stats.back().total_imiss_latency = sim_stats.back().total_imiss_latency;
		roi_stats.back().total_dmiss_latency = sim_stats.back().total_dmiss_latency;
		roi_stats.back().total_itmiss_latency = sim_stats.back().total_itmiss_latency;
		roi_stats.back().total_dtmiss_latency = sim_stats.back().total_dtmiss_latency;
		roi_stats.back().max_cache_occupancy = sim_stats.back().max_cache_occupancy;
#endif
  }

  roi_stats.back().pf_requested = sim_stats.back().pf_requested;
  roi_stats.back().pf_issued = sim_stats.back().pf_issued;
  roi_stats.back().pf_useful = sim_stats.back().pf_useful;
  roi_stats.back().pf_useless = sim_stats.back().pf_useless;
  roi_stats.back().pf_fill = sim_stats.back().pf_fill;
  roi_stats.back().pf_crossed = sim_stats.back().pf_crossed;

#if defined ENABLE_PAGE_CROSSING_STATS
	roi_stats.back().pf_crossing_pages_tlb_hit = sim_stats.back().pf_crossing_pages_tlb_hit;
	roi_stats.back().pf_crossing_pages_tlb_miss = sim_stats.back().pf_crossing_pages_tlb_miss;
#endif

  roi_stats.back().total_miss_latency = sim_stats.back().total_miss_latency;

}

bool CACHE::should_activate_prefetcher(const PACKET& pkt) const { return ((1 << pkt.type) & pref_activate_mask) && !pkt.prefetch_from_this; }

void CACHE::print_deadlock()
{
  if (!std::empty(MSHR)) {
    std::cout << NAME << " MSHR Entry" << std::endl;
    std::size_t j = 0;
    for (PACKET entry : MSHR) {
      std::cout << "[" << NAME << " MSHR] entry: " << j++ << " instr_id: " << entry.instr_id;
      std::cout << " address: " << std::hex << entry.address << " v_addr: " << entry.v_address << std::dec << " type: " << +entry.type;
      std::cout << " event_cycle: " << entry.event_cycle << std::endl;
    }
  } else {
    std::cout << NAME << " MSHR empty" << std::endl;
  }

  if (!std::empty(queues.RQ)) {
    for (const auto& entry : queues.RQ) {
      std::cout << "[" << NAME << " RQ] "
                << " instr_id: " << entry.instr_id;
      std::cout << " address: " << std::hex << entry.address << " v_addr: " << entry.v_address << std::dec << " type: " << +entry.type;
      std::cout << " event_cycle: " << entry.event_cycle << std::endl;
    }
  } else {
    std::cout << NAME << " RQ empty" << std::endl;
  }

  if (!std::empty(queues.WQ)) {
    for (const auto& entry : queues.WQ) {
      std::cout << "[" << NAME << " WQ] "
                << " instr_id: " << entry.instr_id;
      std::cout << " address: " << std::hex << entry.address << " v_addr: " << entry.v_address << std::dec << " type: " << +entry.type;
      std::cout << " event_cycle: " << entry.event_cycle << std::endl;
    }
  } else {
    std::cout << NAME << " WQ empty" << std::endl;
  }

  if (!std::empty(queues.PQ)) {
    for (const auto& entry : queues.PQ) {
      std::cout << "[" << NAME << " PQ] "
                << " instr_id: " << entry.instr_id;
      std::cout << " address: " << std::hex << entry.address << " v_addr: " << entry.v_address << std::dec << " type: " << +entry.type;
      std::cout << " event_cycle: " << entry.event_cycle << std::endl;
    }
  } else {
    std::cout << NAME << " PQ empty" << std::endl;
  }
}

#if defined ENABLE_EXTRA_CACHE_STATS
	void CACHE::hit_hook(const PACKET& handle_pkt) {

		if (handle_pkt.is_instr && !handle_pkt.is_pte) {
			sim_stats.back().ihits[handle_pkt.type][handle_pkt.cpu]++;
		} else if (!handle_pkt.is_instr && !handle_pkt.is_pte) {
			sim_stats.back().dhits[handle_pkt.type][handle_pkt.cpu]++;
		} else if (handle_pkt.is_instr && handle_pkt.is_pte) {
			sim_stats.back().ithits[handle_pkt.type][handle_pkt.cpu]++;
		} else if (!handle_pkt.is_instr && handle_pkt.is_pte) {
			sim_stats.back().dthits[handle_pkt.type][handle_pkt.cpu]++;
		} else {
			std::cout << "Oups, something went wrong..." << std::endl;
			std::cout << "\ttype:" << (uint32_t)handle_pkt.type << std::endl;
			std::cout << "\tis_instr:" << (handle_pkt.is_instr?"true":"false") << std::endl;
			assert(false);
		}
						
		pageAddressStatsMon->add_access(handle_pkt.address, handle_pkt.is_instr);
		reuseDistMon->add_access(handle_pkt.address);
		addressAccessStatsMon->add_access(handle_pkt.address, true);
	}

	void CACHE::miss_hook(const PACKET& handle_pkt) {
				
		if (handle_pkt.is_instr && !handle_pkt.is_pte) {
			sim_stats.back().imisses[handle_pkt.type][handle_pkt.cpu]++;
		} else if (!handle_pkt.is_instr && !handle_pkt.is_pte) {
			sim_stats.back().dmisses[handle_pkt.type][handle_pkt.cpu]++;
		} else if (handle_pkt.is_instr && handle_pkt.is_pte) {
			sim_stats.back().itmisses[handle_pkt.type][handle_pkt.cpu]++;
		} else if (!handle_pkt.is_instr && handle_pkt.is_pte) {
			sim_stats.back().dtmisses[handle_pkt.type][handle_pkt.cpu]++;
		} else {
			std::cout << "Oups, something went wrong..." << std::endl;
			std::cout << "\ttype:" << (uint32_t)handle_pkt.type << std::endl;
			std::cout << "\tis_instr:" << (handle_pkt.is_instr?"true":"false") << std::endl;
			assert(false);
		}

		pageAddressStatsMon->add_access(handle_pkt.address, handle_pkt.is_instr);
		reuseDistMon->add_access(handle_pkt.address);
		addressAccessStatsMon->add_access(handle_pkt.address, false);
	}
#endif
