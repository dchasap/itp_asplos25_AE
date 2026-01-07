
#ifndef PAGE_ADDRESS_STATS_H
#define PAGE_ADDRESS_STATS_H

#include <iostream>
#include <fstream>
#include <string>
#include <list>
#include <vector>
#include <iterator>
#include <algorithm>
#include "msl/bits.h"


class PageAddressStatsHanlder 
{
	public:
		PageAddressStatsHanlder(uint32_t _offset_bits,
														std::string filename, 
														bool enable) : 
				enabled(enable), offset_bits(_offset_bits)
		{ 
				if (!enabled) return;

				dumpfile = std::ofstream(filename , std::ios::out);

				total_accesses = 0;
		};


		~PageAddressStatsHanlder() {}; 


		void add_access(uint64_t address, uint8_t type) 
		{
				if (!enabled) return;
		
				if (type == 1) {	
					if (accessedInstrPages.find(address >> offset_bits) != accessedInstrPages.end()) {
						accessedInstrPages[address >> offset_bits] = accessedInstrPages[address >> offset_bits] + 1;
					}	else {
						accessedInstrPages[address >> offset_bits] = 1;
					}
				} else {
					if (accessedDataPages.find(address >> offset_bits) != accessedDataPages.end()) {
						accessedDataPages[address >> offset_bits] = accessedDataPages[address >> offset_bits] + 1;
					}	else {
						accessedDataPages[address >> offset_bits] = 1;
					}
				}

				total_accesses++;
		};

	
		void dump() 
		{
				if (!enabled) return;

				dumpfile << "address,type,accesses" << std::endl;

				for (auto page_it = accessedInstrPages.begin(); page_it != accessedInstrPages.end(); ++page_it) {

					dumpfile << page_it->first << ",instr," << page_it->second << std::endl;
				}

				for (auto page_it = accessedDataPages.begin(); page_it != accessedDataPages.end(); ++page_it) {

					dumpfile << page_it->first << ",data," << page_it->second << std::endl;
				}

				dumpfile.close();
		};

	private:
		bool enabled;
		uint32_t offset_bits, total_accesses;
		std::ofstream dumpfile;
		std::map<uint64_t, uint32_t> accessedInstrPages;
		std::map<uint64_t, uint32_t> accessedDataPages;
};

#endif
