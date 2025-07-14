#ifndef _CACHE_FILTER_H
#define _CACHE_FILTER_H

//#define _DOA_BUDGETED

#include <iostream>
#include <cmath>
#include <algorithm>
#include <vector>
#include <set>

#include "champsim.h"
#include "memory_trace.h"

class CacheFilter {
  
  public:
    uint64_t num_sets; 
    uint64_t num_ways;

    bool enabled = false;
    bool skip_lookups = false;

    virtual ~CacheFilter() {}
    virtual bool predict(uint64_t address, bool seems_dead) = 0;
    virtual void update(uint64_t address, bool is_doa, bool is_lookup, uint64_t cycle) = 0;
    virtual void print_stats() = 0;

};


class FilterTracer : public CacheFilter {

  private: 
    bool save_mem_trace;
    MemoryTracer memTracer;
    std::vector<uint64_t> accesses_vector;

  public:

    FilterTracer() {
      
      if (getenv("CACHE_FILTER_MEMORY_TRACE_PATH") != nullptr) { 
        std::string memtrace_filename = getenv("CACHE_FILTER_MEMORY_TRACE_PATH");
        std::cerr << "\tSaving memory trace to " << memtrace_filename << std::endl;
        memTracer.open_tracefile(memtrace_filename);
      } else {
        std::cerr << "CACHE_FILTER_MEMORY_TRACE_PATH not set!" << std::endl;
        exit(1);
      }
    
    }

    virtual bool predict(uint64_t address, bool) 
    {
      memTracer.add_access(address);
      return false;
    };

    virtual void update(uint64_t, bool, bool, uint64_t) { return; };

    virtual void print_stats() 
    {
      memTracer.save_tracefile();
      return;
    }
};



class OracleDOAFilter : public CacheFilter {

  private:

    struct FrequencyNode {
      uint64_t key;
      uint64_t freq;
      uint64_t last_cycle;
    };

    uint64_t freq_threshold;
    std::vector<FrequencyNode> ordered_freq_map;
    
    MemoryTraceReader memTraceReader;
    std::vector<uint64_t> accesses_vector;

    champsim::DebugLogger debugLog;

    // stats
    uint64_t total_predictions = 0, total_correct_predictions = 0, total_wrong_predictions = 0;
    std::map<uint64_t, bool> last_prediction_map;
    uint64_t predictors_agree = 0, predictors_disagree = 0;

  public: 
    OracleDOAFilter(uint64_t sets, uint64_t ways, bool _skip_lookups) 
    {

      freq_threshold = 1;

      num_sets = sets;
      num_ways = ways;
      skip_lookups = _skip_lookups;

      std::cout << "CACHE_FILTER: Oracle DOA" << std::endl;

      if (getenv("CACHE_FILTER_MEMORY_TRACE_PATH") != nullptr) { 
        std::string memtrace_filename = getenv("CACHE_FILTER_MEMORY_TRACE_PATH");
        if (memTraceReader.open_tracefile(memtrace_filename)) {
          std::cout << "\tReading memory trace from " << memtrace_filename << std::endl;
          accesses_vector = memTraceReader.get_accesses();
          memTraceReader.close_tracefile();

          for (auto it = accesses_vector.begin(); it != accesses_vector.end(); ++it) {
            
            //debugLog << "Access: " << *it << std::endl;
            auto access_it = std::find_if(ordered_freq_map.begin(), ordered_freq_map.end(), [it](auto x) { return x.key == *it; });
            uint64_t i = std::distance(ordered_freq_map.begin(), access_it);
            if (access_it != ordered_freq_map.end()) {
            //if (i < ordered_freq_map.size() && *it == ordered_freq_map[i].key) {
              
              //debugLog << "\tfreq:" << (ordered_freq_map[i].freq+1) << std::endl;
              ordered_freq_map[i].freq++;
              // sort the frequency map - maybe we can sort it after populating it?
              for (int64_t j = (i-1); j >= 0; j--) {
                
                if (ordered_freq_map[i].freq > ordered_freq_map[j].freq) {
                  std::swap(ordered_freq_map[i], ordered_freq_map[j]);
                  i = j;
                }
              }
            } else {
              
              //debugLog << "\tfreq:1" << std::endl;
              ordered_freq_map.push_back({*it, 1, 0});
            }

            i++;
          }

          //for (auto it = ordered_freq_map.begin(); it != ordered_freq_map.end(); ++it) {
          //  std::cout << it->key << " - " << it->freq << std::endl;
          //}

          // eliminate all the elements with freq <= 1
          for (auto it = ordered_freq_map.begin(); it != ordered_freq_map.end(); ) {
            if (it->freq > freq_threshold) {
              it = ordered_freq_map.erase(it);
            } else {
              ++it;
            }
          }

          std::cout << "-Set (filtered) size: " << ordered_freq_map.size() << std::endl;
 
        } else {
          std::cerr << "\tMemory trace " << memtrace_filename << " not found!" << std::endl;
          exit(1);
        }

      } else {
        std::cerr << "CACHE_FILTER_MEMORY_TRACE_PATH not set!" << std::endl;
        exit(1);
      }

    }
    
    
    // Return true if address is not in the top N frequencies
    virtual bool predict(uint64_t address, bool seems_dead) 
    {
      total_predictions++;
      for (auto access_it = ordered_freq_map.begin(); access_it != ordered_freq_map.end(); ++access_it) {
        
        debugLog << "Comparing " << address << " with " << access_it->key << std::endl; 

        if (access_it->key == address) {
          debugLog << "Address " << address << " found in doa list"  << std::endl;
          if (seems_dead) predictors_agree++;
          else predictors_disagree++;
          last_prediction_map.insert({address, true});
          return true;
        }
      }

      debugLog << "Address " << address << " not found"  << std::endl;
      if (seems_dead) predictors_disagree++;
      else predictors_agree++;
      last_prediction_map.insert({address, false});
      return false;
    }

    virtual void update(uint64_t address, bool is_doa, bool, uint64_t) 
    { 
      if (is_doa == last_prediction_map[address]) {
        total_correct_predictions++;
      } else {
        total_wrong_predictions++;
      }
    }

    virtual void print_stats() 
    {
      std::cout << "DBPRED: predictors agree: " << double((predictors_agree*100) / (predictors_agree+predictors_disagree)) << "%" << std::endl;
      std::cout << "DBPRED: predictor accuracy: " << double((total_correct_predictions*100) / (total_correct_predictions+total_wrong_predictions)) << "%" << std::endl;
    }
};

class SimpleDOAFilter : public CacheFilter {

  private:
    // stats
    uint64_t total_predictions = 0, total_correct_predictions = 0, total_wrong_predictions = 0;
    std::map<uint64_t, bool> last_prediction_map;

  public: 
    SimpleDOAFilter() {};

    virtual bool predict(uint64_t address, bool seems_dead) 
    {
      last_prediction_map.insert({address, seems_dead}); // this is for statistics
      return seems_dead;
    }

    virtual void update(uint64_t address, bool is_doa, bool, uint64_t) 
    {
      total_predictions++;
      if (is_doa == last_prediction_map[address]) {
        total_correct_predictions++;
      } else {
        total_wrong_predictions++;
      }
    }

    virtual void print_stats() 
    {
      if (total_predictions > 0)
        std::cout << "DBPRED: prediction accuracy: " << double((total_correct_predictions*100) / total_predictions) << "%" << std::endl; 
      else
        std::cout << "DBPRED: prediction accuracy: 0" << std::endl;  

      std::cout << "DBPRED: total predictions: " << total_predictions << std::endl;
      std::cout << "DBPRED: total correct predictions: " << total_correct_predictions << std::endl;
      std::cout << "DBPRED: total wrong predictions: " << total_wrong_predictions << std::endl; 
    }
};

class DOAPredictor : public CacheFilter {

  private:
    uint32_t max_counter_value; // Maximum value for the prediction counter
    uint32_t min_counter_value = 0; // Minimum value for the prediction counter
    uint32_t prediction_thrhld; // Threshold for prediction confidence

    bool use_bias_flag = false;

    // stats
    uint64_t total_predictions = 0, total_correct_predictions = 0, total_wrong_predictions = 0;

    // Prediction table: holds the confidence values for each entry
    // TODO: change to saturating counter
    struct ptable_entry_t { 
      uint64_t address; // Address associated with this entry
      uint32_t pred_cnt; // Confidence value for the prediction
    }; 

    std::vector<ptable_entry_t> prediction_table;
    std::map<uint64_t, uint32_t> prediction_map; // For unlimited storage
    std::map<uint64_t, bool> last_prediction_map;

    champsim::DebugLogger debugLog;

    uint64_t get_hash(uint64_t address) const {
      return address % (num_sets * num_ways); //TODO: check bibliography for better hash function
    }


  public:

    DOAPredictor(uint64_t sets, uint64_t ways, bool _skip_lookups)
    {
      
      //debugLog.enable();

      num_sets = sets;
      num_ways = ways;
      skip_lookups = _skip_lookups;

      uint32_t cntr_sz = 0;
      if (getenv("TXC_DBPRED_CNTR_SZ")) {
				cntr_sz = std::stoull(getenv("TXC_DBPRED_CNTR_SZ"));
        max_counter_value = std::exp2(cntr_sz);
			} else {
				std::cerr << "TXC_BPRED_CNTR_SZ not set!" << std::endl;
				exit(0);
			}
        
			uint32_t thrhld = 0;
      if (getenv("TXC_DBPRED_THRESHOLD")) {
				thrhld = std::stoull(getenv("TXC_DBPRED_THRESHOLD"));
			} else {
				std::cerr << "TXC_DBPRED_THRESHOLD not set!" << std::endl;
				exit(0);
			}

      if (getenv("TXC_DBPRED_USE_BIAS")) {
				char* _enable_bias_str = getenv("TXC_DBPRED_USE_BIAS");
        if (strcmp(_enable_bias_str, "true") == 0) {
          use_bias_flag = true;
        }
			} else {
				std::cerr << "TXC_DBPRED_USE_BIAS not set!" << std::endl;
				exit(0);
			}

      // Initialize the predictor
      // std::cout << "DOA Predictor initialized." << std::endl;
			if (thrhld > 0) { 
        prediction_thrhld = thrhld;
      } else {
        prediction_thrhld = max_counter_value / 2;
      }

      prediction_table.resize(num_sets * num_ways);

      char* use_bias = getenv("TXC_DBPRED_USE_BIAS");
		  if (strcmp(use_bias, "true") == 0) {
			  use_bias_flag = true;
		  }

      //std::cout << "TXVC: Using DOA prediction:" << std::endl;
#if defined _DOA_BUDGETED
      std::cout << "\t- sets: " << num_sets << std::endl;
      std::cout << "\t- ways: " << num_ways << std::endl;
#else 
      std::cout << "\t- No collisions!" << std::endl;
#endif
      std::cout << "\t- counter size: " << cntr_sz << std::endl;
      std::cout << "\t- prediction theshold: " << prediction_thrhld << std::endl; 
      std::cout << "\t- Use bias: " << (use_bias_flag?"true":"false") << std::endl;
    }

#if defined _DOA_BUDGETED
    virtual bool predict(uint64_t address, bool seems_dead) 
    {  
        // Implement prediction logic here
        // std::cout << "Predicting for address: " << address << std::endl;
        uint32_t hash_index = get_hash(address);

        if (prediction_table[hash_index].address != address) {
            // If the address is not found, initialize it
            prediction_table[hash_index].address = address;
            prediction_table[hash_index].pred_cnt = 0; // Start with a neutral prediction
            return false;
        }

				uint32_t bias = 0;
				if (seems_dead && use_bias_flag) bias = max_counter / 2;
        uint32_t prediction = prediction_table[hash_index].pred_cnt + bias;
        
        if (prediction >= prediction_thrhld) {
            //std::cout << "Prediction hit for address: " << address << std::endl;
            return true; // Prediction is doa
        } else {
            //std::cout << "Prediction miss for address: " << address << std::endl;
            return false; // Prediction is not doa
        }
    }


    virtual void update(uint64_t address, bool is_doa, bool is_lookup, uint64_t) 
    {

        if (is_lookup && skip_lookups) return;

        uint32_t hash_index = get_hash(address);

        if (prediction_table[hash_index].address != address) {
            // If the address is not found, initialize it
            prediction_table[hash_index].address = address;
            prediction_table[hash_index].pred_cnt = 0; // Start with a neutral prediction
        }

        if (is_doa) {
          prediction_table[hash_index].pred_cnt = std::min(prediction_table[hash_index].pred_cnt++, max_counter_value); // Increase confidence
        } else {
          prediction_table[hash_index].pred_cnt = std::max(prediction_table[hash_index].pred_cnt--, min_counter_value); // Decrease confidence
        }

    }

#else

    virtual bool predict(uint64_t address, bool seems_dead) 
    {

				uint32_t bias = 0;
				if (seems_dead && use_bias_flag) bias = max_counter_value / 2;

        debugLog << "DBPredictor: Looking up " << address << std::endl;
        auto pred_it = prediction_map.find(address);

        if (pred_it == prediction_map.end()) {
            // If the address is not found, initialize it
            //prediction_map[address] = 0; // should use insert instead?
            debugLog << "\tnot found, inserting with cntr value " << bias << std::endl;
            prediction_map.insert({address, bias});
            //std::cout << "\tprediction false" << std::endl;
            //return false;
        }

				
        uint32_t prediction = prediction_map[address];
        last_prediction_map.insert({address, (prediction >= prediction_thrhld?true:false)}); // this is for statistics
        
        if (prediction >= prediction_thrhld) {
            debugLog << "\tprediction true" << std::endl;
            return true; // Prediction is doa
        } else {
            debugLog << "\tprediction false" << std::endl;
            //std::cout << "Prediction miss for address: " << address << std::endl;
            return false; // Prediction is not doa
        }

    }


    virtual void update(uint64_t address, bool is_doa, bool is_lookup, uint64_t) 
    {
      
        if (is_lookup && skip_lookups) return;

        debugLog << "DBPredictor: Updating " << address << std::endl;
        auto pred_it = prediction_map.find(address);

        if (pred_it == prediction_map.end()) {
            // If the address is not found, initialize it
            uint32_t bias = 0;
				    if (is_doa && use_bias_flag) bias = max_counter_value / 2;
            debugLog << "\tnot found, inserting now (" << bias << ")" << std::endl;
            prediction_map.insert({address, bias});
        }

        uint32_t prediction_val = prediction_map[address];
        if (is_doa) {
          debugLog << "\tincreasing cntr value to " << std::min(prediction_val+1, max_counter_value) << std::endl;
          prediction_map[address] = std::min(prediction_val+1, max_counter_value); // Increase confidence
        } else {
          debugLog << "\tdecreasing cntr value to " << std::max(prediction_val-1, max_counter_value) << std::endl;
          prediction_map[address] = std::max(prediction_val-1, min_counter_value); // Decrease confidence
        }

        total_predictions++;
        if (is_doa == last_prediction_map[address]) {
          total_correct_predictions++;
        } else {
          total_wrong_predictions++;
        }

    }
#endif

    virtual void print_stats(void) 
    {
      if (total_predictions > 0)
        std::cout << "DBPRED: prediction accuracy: " << double((total_correct_predictions*100) / total_predictions) << "%" << std::endl; 
      else
        std::cout << "DBPRED: prediction accuracy: 0" << std::endl;  

      std::cout << "DBPRED: total predictions: " << total_predictions << std::endl;
      std::cout << "DBPRED: total correct predictions: " << total_correct_predictions << std::endl;
      std::cout << "DBPRED: total wrong predictions: " << total_wrong_predictions << std::endl; 
    } 

};

class MFUFilter : public CacheFilter {

  private:

    struct FrequencyNode {
      uint64_t key;
      uint64_t freq;
      uint64_t last_cycle;
    };

    uint64_t top_N, last_cycle_cleanup, cleanup_cycle_interval;
    //OrderedFrequencyMap<uint64_t, uint64_t> top_accessed_blocks;
    //unordered_map<uint64_t, uint64_t> blocks;
    //unordered_map<uint64_t, uint64_t> freq_map;

    std::vector<FrequencyNode> ordered_freq_map;

  public: 
    MFUFilter(uint64_t sets, uint64_t ways, bool _skip_lookups) 
    {

      double top_N_scale = 1.0;
      if (getenv("TXC_FILTER_TOP_N_FACTOR")) {
				top_N_scale = std::stod(getenv("TXC_FILTER_TOP_N_FACTOR"));
			} else {
				std::cerr << "TXC_FILTER_TOP_N_FACTOR not set!" << std::endl;
				exit(0);
			}
      

      if (getenv("TXC_FILTER_CLEANUP_INTERVAL")) {
				cleanup_cycle_interval = std::stoull(getenv("TXC_FILTER_CLEANUP_INTERVAL"));
			} else {
				std::cerr << "TXC_FILTER_CLEANUP_INTERVAL not set!" << std::endl;
				exit(0);
      }

      num_sets = sets;
      num_ways = ways;
      top_N = static_cast<uint64_t>((sets * ways) * top_N_scale);
      skip_lookups = _skip_lookups;
      last_cycle_cleanup = 0;

      std::cout << "CACHE_FILTER: MFU" << std::endl;
      std::cout << "\t-size: " << num_sets * num_ways << std::endl;
      std::cout << "\t-N: " << top_N << std::endl;
      std::cout << "\t-Cleanup interval: " << cleanup_cycle_interval << std::endl;
    };
    
    
    // Return true if address is not in the top N frequencies
    virtual bool predict(uint64_t address, bool) 
    {
      // search the N top elements for the address
      uint64_t _N = std::min(top_N, ordered_freq_map.size());
      for (uint64_t i = 0; i < _N; i++) {
        if (ordered_freq_map[i].key == address) {
          return false;
        }        
      }

      return true;
    }

    virtual void update(uint64_t address, bool, bool, uint64_t curr_cycle) 
    {

      if ((curr_cycle - last_cycle_cleanup) >= cleanup_cycle_interval) {
        for (uint64_t i = 0; i < ordered_freq_map.size(); i++) {
          if ((curr_cycle - ordered_freq_map[i].last_cycle) >= cleanup_cycle_interval) {
            ordered_freq_map.erase(ordered_freq_map.begin() + i);
            i--;
          }
        }
        last_cycle_cleanup = curr_cycle;
      }

      for (uint64_t i = 0; i < ordered_freq_map.size(); i++) {
        
        if (ordered_freq_map[i].key == address) {
          
          ordered_freq_map[i].freq++;
          ordered_freq_map[i].last_cycle = curr_cycle;

          if ((i > 0) && (ordered_freq_map[i].freq > ordered_freq_map[i-1].freq)) {
            std::swap(ordered_freq_map[i], ordered_freq_map[i-1]);
          } 

          return;
        }
      }

      // add to map
      ordered_freq_map.push_back({address, 1, curr_cycle});
    }

    virtual void print_stats() {}
};

class OracleMFUFilter : public CacheFilter {

  private:

    struct FrequencyNode {
      uint64_t key;
      uint64_t freq;
      uint64_t last_cycle;
    };

    uint64_t top_N, last_cycle_cleanup, cleanup_cycle_interval, freq_threshold;
    //OrderedFrequencyMap<uint64_t, uint64_t> top_accessed_blocks;
    //unordered_map<uint64_t, uint64_t> blocks;
    //unordered_map<uint64_t, uint64_t> freq_map;

    /*
    struct FrequencyNodeComparator {
      bool operator()(const FrequencyNode& a, const FrequencyNode& b) const
      {
        return a.freq < b.freq;
      }
    };
    */

    std::vector<FrequencyNode> ordered_freq_map;

    bool save_mem_trace;
    MemoryTracer memTracer;
    MemoryTraceReader memTraceReader;
    std::vector<uint64_t> accesses_vector;

    champsim::DebugLogger debugLog;

  public: 
    OracleMFUFilter(uint64_t sets, uint64_t ways, bool _skip_lookups) 
    {

      //debugLog.enable();
      
      /*
      double top_N_scale = 1.0;
      if (getenv("TXC_FILTER_TOP_N_FACTOR")) {
				top_N_scale = std::stod(getenv("TXC_FILTER_TOP_N_FACTOR"));
			} else {
				std::cerr << "TXC_FILTER_TOP_N_FACTOR not set!" << std::endl;
				exit(0);
			}
      */

      freq_threshold = 2; // default will remove freq < 2
      if (getenv("CACHE_FILTER_FREQ_THRESHOLD")) {
				freq_threshold = std::stoll(getenv("CACHE_FILTER_FREQ_THRESHOLD"));
			} else {
				std::cerr << "CACHE_FILTER_FREQ_THRESHOLD not set!" << std::endl;
				exit(0);
			}
      
      /*
      if (getenv("TXC_FILTER_CLEANUP_INTERVAL")) {
				cleanup_cycle_interval = std::stoull(getenv("TXC_FILTER_CLEANUP_INTERVAL"));
			} else {
				std::cerr << "TXC_FILTER_CLEANUP_INTERVAL not set!" << std::endl;
				exit(0);
			}

      char* _histogram_filename = nullptr;
      if (getenv("TXC_FILTER_HISTOGRAM_DATA_FILE")) {
				_histogram_filename = getenv("TXC_FILTER_HISTOGRAM_DATA_FILE");
        histogram_filename.assign(histogram_filename);
        histogram_file.open(_histogram_filename, 'w');
			} else {
				std::cerr << "TXC_FILTER_HISTOGRAM_DATA_FILE not set!" << std::endl;
				exit(0);
			}
      */

      num_sets = sets;
      num_ways = ways;
      //top_N = static_cast<uint64_t>((sets * ways) * top_N_scale);
      skip_lookups = _skip_lookups;

      std::cout << "CACHE_FILTER: Oracle MFU" << std::endl;
      std::cout << "\t-N: " << top_N << std::endl;
      std::cout << "\t-Frequency threshold: " << freq_threshold << std::endl;

      save_mem_trace = true;
      if (getenv("CACHE_FILTER_MEMORY_TRACE_PATH") != nullptr) { 
        std::string memtrace_filename = getenv("CACHE_FILTER_MEMORY_TRACE_PATH");
        if (memTraceReader.open_tracefile(memtrace_filename)) {
          std::cout << "\tReading memory trace from " << memtrace_filename << std::endl;
          save_mem_trace = false;
          accesses_vector = memTraceReader.get_accesses();
          memTraceReader.close_tracefile();

          for (auto it = accesses_vector.begin(); it != accesses_vector.end(); ++it) {
            
            //debugLog << "Access: " << *it << std::endl;
            auto access_it = std::find_if(ordered_freq_map.begin(), ordered_freq_map.end(), [it](auto x) { return x.key == *it; });
            uint64_t i = std::distance(ordered_freq_map.begin(), access_it);
            if (access_it != ordered_freq_map.end()) {
            //if (i < ordered_freq_map.size() && *it == ordered_freq_map[i].key) {
              
              //debugLog << "\tfreq:" << (ordered_freq_map[i].freq+1) << std::endl;
              ordered_freq_map[i].freq++;
              // sort the frequency map - maybe we can sort it after populating it?
              for (int64_t j = (i-1); j >= 0; j--) {
                
                if (ordered_freq_map[i].freq > ordered_freq_map[j].freq) {
                  std::swap(ordered_freq_map[i], ordered_freq_map[j]);
                  i = j;
                }
              }
            } else {
              
              //debugLog << "\tfreq:1" << std::endl;
              ordered_freq_map.push_back({*it, 1, 0});
            }

            i++;
          }

          //for (auto it = ordered_freq_map.begin(); it != ordered_freq_map.end(); ++it) {
          //  std::cout << it->key << " - " << it->freq << std::endl;
          //}

          debugLog << "Set size: " << ordered_freq_map.size() << std::endl;

          // eliminate all the elements with freq <= 1
          for (auto it = ordered_freq_map.begin(); it != ordered_freq_map.end(); ) {
            if (it->freq < freq_threshold) {
              it = ordered_freq_map.erase(it);
            } else {
              ++it;
            }
          }

          std::cout << "- Set (filtered) size: " << ordered_freq_map.size() << std::endl;
 
        } else {
          std::cerr << "\tSaving memory trace to " << memtrace_filename << std::endl;
          memTracer.open_tracefile(memtrace_filename);
        }

      } else {
        std::cerr << "CACHE_FILTER_MEMORY_TRACE_PATH not set!" << std::endl;
        exit(1);
      }

    }
    
    
    // Return true if address is not in the top N frequencies
    virtual bool predict(uint64_t address, bool) 
    {
      /*
      auto access_it = std::find_if(ordered_freq_map.begin(), ordered_freq_map.end(), [address](auto x) { return x.key == address; });
      if (access_it != ordered_freq_map.end()) {
        return false;
      } 
      */
      //uint64_t _N = std::min(top_N, ordered_freq_map.size());
      uint64_t i = 0;
      //debugLog << "N:" << _N << std::endl;
      for (auto access_it = ordered_freq_map.begin(); access_it != ordered_freq_map.end(); ++access_it) {
        
        debugLog << "Comparing " << address << " with " << access_it->key << std::endl; 

        //if (i >= _N) {
        //  debugLog << "Address " << address << " not found in top N"  << std::endl;
        //  break;
        //}

        if (access_it->key == address) {
          debugLog << "Address " << address << " found"  << std::endl;
          return false;
        }

        i++;
      }

      debugLog << "Address " << address << " not found"  << std::endl;
      return true;
    }

    virtual void update(uint64_t address, bool, bool is_lookup, uint64_t) 
    {

      return;
      if (skip_lookups && is_lookup) return;

      if (save_mem_trace) {
        memTracer.add_access(address);
        return;
      }

      //address = 8886256;
      auto access_it = std::find_if(ordered_freq_map.begin(), ordered_freq_map.end(), [address](auto x) { return x.key == address; });
      uint64_t i = std::distance(ordered_freq_map.begin(), access_it);
      if (access_it != ordered_freq_map.end()) {
        debugLog << "Address " << address << " found and reducing frequency"  << std::endl;
        ordered_freq_map[i].freq--;
        
        if (access_it->freq <= freq_threshold) {
          ordered_freq_map.erase(access_it);
          return;
        }
        
        // sort the frequency map - maybe we can sort it after populating it?
        for (uint64_t j = i+1; j < ordered_freq_map.size(); j++) {
          if (ordered_freq_map[i].freq < ordered_freq_map[j].freq) {
            std::swap(ordered_freq_map[i], ordered_freq_map[j]);
            i = j;
          }
        }

        //for (auto it = ordered_freq_map.begin(); it != ordered_freq_map.end(); ++it) {
        //  std::cout << it->key << " - " << it->freq << std::endl;
        //}
      }

    }

    virtual void print_stats() 
    {
      if (save_mem_trace)
        memTracer.save_tracefile();
    }
};

#endif // DOA_PREDICTOR_H
