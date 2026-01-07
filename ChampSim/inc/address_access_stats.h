
#ifndef ADDRESS_ACCESS_STATS_H
#define ADDRESS_ACCESS_STATS_H

#include <iostream>
#include <fstream>
#include <string>
#include <list>
#include <vector>
#include <iterator>
#include <algorithm>
#include "msl/bits.h"


class AddressAccessStatsHanlder 
{
	public:
		AddressAccessStatsHanlder(std::string filename, bool enable) : enabled(enable)
		{ 
				if (!enabled) return;

				dumpfile = std::ofstream(filename , std::ios::out);
		};


		~AddressAccessStatsHanlder() {}; 


		void add_access(uint64_t address, bool hit) 
		{
				if (!enabled) return;
		
				if (hit) {	
					if (accessedAddress.find(address) != accessedAddress.end()) {
						accessedAddress[address].total_hits++;
					}	else {
						accessedAddress[address].total_hits = 1;
					}
				} else {
					if (accessedAddress.find(address) != accessedAddress.end()) {
						accessedAddress[address].total_misses;
					}	else {
						accessedAddress[address].total_misses = 1;
					}
				}
		};

	
		void dump() 
		{
				if (!enabled) return;

				dumpfile << "address,accesses,hits,misses" << std::endl;

				for (auto it = accessedAddress.begin(); it != accessedAddress.end(); ++it) {

                    uint64_t hits = (it->second).total_hits;
                    uint64_t misses = (it->second).total_misses;
					dumpfile << it->first << "," << (hits+misses) << "," << hits  << "," << misses << std::endl;
				}

				dumpfile.close();
		};

	private:
		bool enabled;
		std::ofstream dumpfile;

        struct ACCESS_STATS {
            uint64_t total_hits = 0;
            uint64_t total_misses = 0;
        };
		std::map<uint64_t, ACCESS_STATS> accessedAddress;
};

#endif
