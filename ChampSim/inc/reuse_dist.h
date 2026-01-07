
#ifndef REUSE_DIST_H
#define REUSE_DIST_H

#include <iostream>
#include <fstream>
#include <string>
#include <list>
#include <vector>
#include <iterator>
#include <algorithm>
#include "msl/bits.h"

class ReuseDistanceMonitor
{
	public:
		ReuseDistanceMonitor(uint32_t _num_set, uint32_t _num_way, uint32_t _offset_bits,
														std::string filename, bool _filter_per_set, bool enable) : 
			dumpfilename(filename), enabled(enable), filter_per_set(_filter_per_set) 
		{ 
				
			if (!enabled) return;

			std::cout << "Reuse Distance Monitor: " << filename << std::endl;
			dumpfile = std::ofstream(filename, std::ios::out);
			num_set = _num_set;
			num_way = _num_way;
			offset_bits = _offset_bits;
			//cache_size  = (filter_per_set?(num_way+1):(num_set * num_way));
			cache_size = num_set * num_way;
			reuseDistanceHistogram = std::vector<uint32_t>(cache_size+1, 0);
			accesses = 0;
		};

		//~ReuseDistanceCalculator() {}; 

		void add_access(uint64_t address) 
		{
			if (!enabled) return;
		
			//std::cout << accesses << "#adding addr:" << address << std::endl;
			uint32_t reuse_distance = 0;

			// Step 1. 	Search stack for address
			auto found_access = std::find(accessStack.begin(), accessStack.end(), address);
				
			// Step 2.	If found, count hops from frist to found and remove it.
			if (found_access != accessStack.end()) { 
				//std::cout << accesses << "#found!" << std::endl;
				reuse_distance = distance(accessStack.begin(), found_access) + 1;
				//std::cout << accesses << "#reuse_dist:" << reuse_distance<< std::endl;
				accessStack.erase(found_access);
			}

			// Step 3.  Add address to stack
			accessStack.push_front(address);

			// this is to maintain a smaller stack and speedup things
			// we count discarded entries at the last bucket
			if (accessStack.size() >= cache_size) {
				reuseDistanceHistogram[cache_size]++;
				//accessStack.pop_front();
				accessStack.pop_back();
			}

			// Step 4.	Add reuse_dist to histogram
			if (reuse_distance > 0 && reuse_distance <= cache_size) {
				//std::cout << accesses << "#found addr:" << address;
				reuseDistanceHistogram[reuse_distance]++;
				//std::cout << "-> " << reuseDistanceHistogram[reuse_distance] << std::endl;
			} else if (reuse_distance > 0 && reuse_distance > cache_size) {
				//std::cout << accesses << "#found addr:" << address;
				reuseDistanceHistogram[cache_size]++;
				//std::cout << "-> " << reuseDistanceHistogram[cache_size-1] << std::endl;
			}
			accesses++;
		};


		std::size_t get_set_index(uint64_t address) const { 
			return (address >> offset_bits) & champsim::msl::bitmask(champsim::msl::lg2(num_set)); 
		}


		uint32_t distance(std::list<uint64_t>::iterator first, std::list<uint64_t>::iterator last) 
		{
			if (!filter_per_set)
				return std::distance(first, last);
	
			//auto _first = first;

			uint32_t result = 0;
			while (first != last) {
				//std::cout << "item1:" << (uint64_t)(*first) << " ?? item2:" << (uint64_t)(*last) << std::endl;
				if (get_set_index(*first) == get_set_index(*last)) {
					//std::cout << "set match!" << std::endl;
					++result;
				}
				++first;
			}

			//std::cout << "reuse dist:" << std::distance(_first, last) << ", recall dist:" << result << std::endl;
			return result;
		}


		void dump() 
		{
			if (!enabled) return;
			std::cout << "Saving reuse distance at " << dumpfilename << std::endl;
			dumpfile << "reuse_distance,frequency" << std::endl;
			for (unsigned int i = 0; i < reuseDistanceHistogram.size(); i++) {
				dumpfile << i << "," << reuseDistanceHistogram[i] << std::endl;
			}
				
			dumpfile.close();
		};

	private:
		std::ofstream dumpfile;
		std::string dumpfilename;
		uint32_t num_way, num_set, offset_bits, cache_size;
		std::list<uint64_t> accessStack;
		std::vector<uint32_t> reuseDistanceHistogram;
		bool enabled, filter_per_set;
		uint32_t accesses;
};

#endif
