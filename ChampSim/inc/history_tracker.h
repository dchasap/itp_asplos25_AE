
#ifndef HISTORY_TRACKER_H
#define HISTORY_TRACKER_H
/*
class historyTracker 
{
	public:
		uint64_t global_path_history_MHRP = 0;
		uint64_t global_path_history = 0;
		uint64_t uncondIndHistory = 0;
		uint64_t condHistory = 0;
		uint64_t uncondIndHistory_old = 0;
		uint64_t condHistory_old = 0;

		int folding_factor=2;
		int glob_shifts_main = 4;
		int globe_bits_mask_main = 3;

		update_history(uint64_t pc, uint64_t& hist);
		update_path_history(uint64_t pc);

};

void historyTracker::update_history(uint64_t pc, uint64_t& hist) {
	hist <<= 8;
	uint64_t brh = hist;
	hist = (brh | ((pc >> 2) & ((1 << 8) - 1)));
}

void historyTracker::update_path_history(uint64_t pc) {
	uint64_t gph;
	global_path_history <<= glob_shifts_main;
	gph = global_path_history;
	global_path_history = (gph | (((pc) & 7)));
	global_path_history_MHRP <<= glob_shifts_main;
	gph = global_path_history_MHRP;
	global_path_history_MHRP = (gph | (((pc >> folding_factor) & globe_bits_mask_main)));
}
*/
namespace champsim {

}

#endif


