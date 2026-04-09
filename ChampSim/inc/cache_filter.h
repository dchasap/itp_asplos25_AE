#ifndef _CACHE_FILTER_H
#define _CACHE_FILTER_H

//#define _DOA_BUDGETED

#include <iostream>
#include <cmath>
#include <algorithm>
#include <vector>
#include <set>
#include <map>
#include <fstream>
#include <string>
#include <limits>
#include <cstdint>

#include "champsim.h"
#include "memory_trace.h"

class CacheFilter {
  
  public:
    uint64_t num_sets; 
    uint64_t num_ways;

    bool enabled = false;
    bool skip_lookups = false;

    virtual ~CacheFilter() {}
    virtual bool predict(uint64_t address, bool seems_dead, uint64_t access_freq) = 0;
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

    virtual bool predict(uint64_t, bool, uint64_t) 
    {
      return false;
    };

    virtual void update(uint64_t address, bool, bool is_lookup, uint64_t)
    { 
      if (is_lookup)
        memTracer.add_access(address);
      
      return; 
    };

    virtual void print_stats() 
    {
      memTracer.save_tracefile();
      return;
    }
};

class DummyFilter : public CacheFilter {

  private:
    // stats
    uint64_t total_predictions;

  public: 
    DummyFilter() {};

    virtual bool predict(uint64_t, bool, uint64_t) 
    {
      total_predictions++;
      return false;
    }

    virtual void update(uint64_t, bool, bool, uint64_t) {}

    virtual void print_stats() 
    {
      std::cout << "FreqFilter: total predictions: " << total_predictions << std::endl;
      std::cout << "FreqFilter: total bypasses: " << 0 << std::endl;
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
    virtual bool predict(uint64_t address, bool seems_dead, uint64_t) 
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

    virtual bool predict(uint64_t address, bool seems_dead, uint64_t) 
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
    virtual bool predict(uint64_t address, bool seems_dead, uint64_t) 
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

    virtual bool predict(uint64_t address, bool seems_dead, uint64_t) 
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
    virtual bool predict(uint64_t address, bool, uint64_t) 
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

    uint64_t top_N, last_cycle_cleanup, cleanup_cycle_interval, lower_freq_threshold, upper_freq_threshold;

    std::vector<FrequencyNode> ordered_freq_map;

    bool save_mem_trace;
    MemoryTracer memTracer;
    MemoryTraceReader memTraceReader;
    std::vector<uint64_t> accesses_vector;

    // stats
    uint64_t total_predictions = 0, total_bypasses = 0;

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

      //lower_freq_threshold = 2; // default will remove freq < 2
      if (getenv("CACHE_FILTER_FREQ_THRESHOLD")) {
				std::string freq_threshold = getenv("CACHE_FILTER_FREQ_THRESHOLD");
        size_t start = 0, end = 0;
        while ((end = freq_threshold.find("-", start)) != std::string::npos) {
          lower_freq_threshold = std::stoll(freq_threshold.substr(start, end - start));
          std::cout << "lower_freq_threshold:" << lower_freq_threshold << std::endl;
          start = end + 1;
          upper_freq_threshold = std::stoll(freq_threshold.substr(start));
          std::cout << "upper_freq_threshold:" << lower_freq_threshold << std::endl;
          break;
        }

        if (end == std::string::npos) {
          lower_freq_threshold = upper_freq_threshold = std::stoll(freq_threshold.substr(start));
        }
        
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
      */

      num_sets = sets;
      num_ways = ways;
      //top_N = static_cast<uint64_t>((sets * ways) * top_N_scale);
      skip_lookups = _skip_lookups;

      std::cout << "CACHE_FILTER: Oracle MFU" << std::endl;
      std::cout << "\t-N: " << top_N << std::endl;
      std::cout << "\t-Lower Frequency threshold: " << lower_freq_threshold << std::endl;
      std::cout << "\t-Upper Frequency threshold: " << upper_freq_threshold << std::endl;

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
            //if (it->freq < freq_threshold) {
            //if (it->freq > freq_threshold || it->freq == 1) {
            //if (it->freq != freq_threshold) {
            //if (it->freq < lower_freq_threshold || it->freq >= upper_freq_threshold) {
            if (it->freq < lower_freq_threshold) {
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
    virtual bool predict(uint64_t address, bool, uint64_t) 
    {

      total_predictions++;

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

      //assert(false);

      debugLog << "Address " << address << " not found"  << std::endl;
      total_bypasses++;
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
        /*
        if (access_it->freq <= freq_threshold) {
          ordered_freq_map.erase(access_it);
          return;
        }
        */
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
      if (save_mem_trace) {
        memTracer.save_tracefile();
      } else {
        std::cout << "FreqFilter: total predictions: " << total_predictions << std::endl;
        std::cout << "FreqFilter: total bypasses: " << total_bypasses << std::endl;
      }
    }
};

class ReuseDistanceFilter : public CacheFilter {

  private:
    struct ReuseProfile {
      uint64_t sample_count = 0;
      uint64_t long_count = 0;
      uint64_t inf_count = 0;
      uint64_t median = 0;
      double long_ratio = 0.0;
    };

    uint64_t reuse_threshold = 0;
    uint64_t min_samples = 1;
    double long_ratio_threshold = 1.0;

    std::map<uint64_t, ReuseProfile> profile_by_pte;

    uint64_t total_predictions = 0;
    uint64_t total_bypasses = 0;
    uint64_t trained_unique_ptes = 0;
    uint64_t trained_total_samples = 0;

    static uint64_t parse_u64_env_or_default(const char* key, uint64_t default_value)
    {
      const char* raw = std::getenv(key);
      if (raw == nullptr)
        return default_value;
      try {
        return std::stoull(std::string(raw), nullptr, 0);
      } catch (...) {
        std::cerr << "CACHE_FILTER: invalid value for " << key << "='" << raw
                  << "', using default " << default_value << std::endl;
        return default_value;
      }
    }

    static double parse_double_env_or_default(const char* key, double default_value)
    {
      const char* raw = std::getenv(key);
      if (raw == nullptr)
        return default_value;
      try {
        return std::stod(std::string(raw));
      } catch (...) {
        std::cerr << "CACHE_FILTER: invalid value for " << key << "='" << raw
                  << "', using default " << default_value << std::endl;
        return default_value;
      }
    }

    static uint64_t parse_address(const std::string& line)
    {
      return std::stoull(line, nullptr, 0);
    }

    static std::vector<uint64_t> parse_trace_file(const std::string& trace_path)
    {
      std::ifstream in(trace_path);
      if (!in.is_open()) {
        std::cerr << "CACHE_FILTER: could not open trace file " << trace_path << std::endl;
        std::exit(1);
      }

      std::vector<uint64_t> trace;
      std::string line;
      while (std::getline(in, line)) {
        if (line.empty())
          continue;
        trace.push_back(parse_address(line));
      }

      if (trace.empty()) {
        std::cerr << "CACHE_FILTER: trace file is empty: " << trace_path << std::endl;
        std::exit(1);
      }
      return trace;
    }

    static std::map<uint64_t, std::vector<uint64_t>> build_position_map(const std::vector<uint64_t>& trace)
    {
      std::map<uint64_t, std::vector<uint64_t>> positions;
      for (uint64_t i = 0; i < trace.size(); i++)
        positions[trace[i]].push_back(i);
      return positions;
    }

    static uint64_t median_of(std::vector<uint64_t>& values)
    {
      if (values.empty())
        return 0;

      const size_t n = values.size();
      const size_t mid = n / 2;
      std::nth_element(values.begin(), values.begin() + mid, values.end());
      if (n % 2 == 1)
        return values[mid];

      uint64_t hi = values[mid];
      std::nth_element(values.begin(), values.begin() + mid - 1, values.end());
      uint64_t lo = values[mid - 1];
      return (lo / 2) + (hi / 2) + ((lo & 1) & (hi & 1));
    }

    void build_profiles(const std::vector<uint64_t>& trace)
    {
      auto positions = build_position_map(trace);

      for (const auto& kv : positions) {
        const uint64_t pte = kv.first;
        const std::vector<uint64_t>& pos = kv.second;
        if (pos.empty())
          continue;

        std::vector<uint64_t> finite_reuses;
        finite_reuses.reserve(pos.size() > 0 ? pos.size() - 1 : 0);

        uint64_t long_count = 0;
        uint64_t inf_count = 0;

        for (size_t i = 0; i < pos.size(); i++) {
          if (i + 1 < pos.size()) {
            uint64_t rd = pos[i + 1] - pos[i];
            finite_reuses.push_back(rd);
            if (rd >= reuse_threshold)
              long_count++;
          } else {
            // Last appearance has no next-use: treat as infinite reuse distance.
            inf_count++;
            long_count++;
          }
        }

        ReuseProfile prof;
        prof.sample_count = pos.size();
        prof.long_count = long_count;
        prof.inf_count = inf_count;
        prof.median = median_of(finite_reuses);
        prof.long_ratio = prof.sample_count > 0 ? static_cast<double>(prof.long_count) / static_cast<double>(prof.sample_count) : 0.0;

        profile_by_pte[pte] = prof;
        trained_total_samples += prof.sample_count;
      }

      trained_unique_ptes = profile_by_pte.size();
    }

    bool should_bypass(const ReuseProfile& prof) const
    {
      // One-shot: seen exactly once → reuse distance is infinite by definition → always DOA.
      if (prof.sample_count <= 4)
        return true;
      if (prof.sample_count < min_samples)
        return false;
      if (prof.long_ratio >= long_ratio_threshold)
        return true;
      if (prof.median >= reuse_threshold)
        return true;
      return false;
    }

    void dump_profiles_csv(const std::string& output_path) const
    {
      std::ofstream out(output_path);
      if (!out.is_open()) {
        std::cerr << "CACHE_FILTER: could not open reuse profile log file " << output_path << std::endl;
        std::exit(1);
      }

      out << "pte,sample_count,long_count,inf_count,median_reuse_distance,long_ratio,bypass\n";
      for (const auto& kv : profile_by_pte) {
        const uint64_t pte = kv.first;
        const ReuseProfile& prof = kv.second;
        out << pte << ","
            << prof.sample_count << ","
            << prof.long_count << ","
            << prof.inf_count << ","
            << prof.median << ","
            << prof.long_ratio << ","
            << (should_bypass(prof) ? 1 : 0)
            << "\n";
      }
    }

    void dump_bypassed_ptes(const std::string& output_path) const
    {
      std::ofstream out(output_path);
      if (!out.is_open()) {
        std::cerr << "CACHE_FILTER: could not open bypassed-pte log file " << output_path << std::endl;
        std::exit(1);
      }

      out << "pte\n";
      for (const auto& kv : profile_by_pte) {
        const uint64_t pte = kv.first;
        const ReuseProfile& prof = kv.second;
        if (should_bypass(prof))
          out << pte << "\n";
      }
    }

  public:
    ReuseDistanceFilter(uint64_t sets, uint64_t ways, bool _skip_lookups)
    {
      num_sets = sets;
      num_ways = ways;
      skip_lookups = _skip_lookups;

      // Defaults to cache size in lines for a coarse "won't fit" threshold.
      reuse_threshold = parse_u64_env_or_default("CACHE_FILTER_REUSE_DISTANCE_THRESHOLD", sets * ways);
      min_samples = parse_u64_env_or_default("CACHE_FILTER_REUSE_MIN_SAMPLES", 2);
      long_ratio_threshold = parse_double_env_or_default("CACHE_FILTER_REUSE_LONG_RATIO", 0.7);

      const char* trace_env = std::getenv("CACHE_FILTER_MEMORY_TRACE_PATH");

      if (trace_env == nullptr) {
        std::cerr << "CACHE_FILTER_MEMORY_TRACE_PATH not set!" << std::endl;
        std::exit(1);
      }

      std::string trace_path(trace_env);
      std::cout << "CACHE_FILTER: Building reuse distance profiles from trace..." << std::endl;
      std::vector<uint64_t> trace = parse_trace_file(trace_path);
      build_profiles(trace);

      const char* profile_log_env = std::getenv("CACHE_FILTER_REUSE_PROFILE_LOG_PATH");
      if (profile_log_env != nullptr) {
        dump_profiles_csv(std::string(profile_log_env));
        std::cout << "\tProfile log: " << profile_log_env << std::endl;
      } else {
        std::cout << "\tCACHE_FILTER_REUSE_PROFILE_LOG_PATH not set (profile log disabled)" << std::endl;
      }

      const char* bypass_log_env = std::getenv("CACHE_FILTER_REUSE_BYPASS_LOG_PATH");
      if (bypass_log_env != nullptr) {
        dump_bypassed_ptes(std::string(bypass_log_env));
        std::cout << "\tBypass-only log: " << bypass_log_env << std::endl;
      } else {
        std::cout << "\tCACHE_FILTER_REUSE_BYPASS_LOG_PATH not set (bypass-only log disabled)" << std::endl;
      }

      std::cout << "CACHE_FILTER: ReuseDistanceFilter" << std::endl;
      std::cout << "\tTrace: " << trace_path << std::endl;
      std::cout << "\tReuse threshold: " << reuse_threshold << std::endl;
      std::cout << "\tMin samples: " << min_samples << std::endl;
      std::cout << "\tLong-ratio threshold: " << long_ratio_threshold << std::endl;
      std::cout << "\tTrained PTEs: " << trained_unique_ptes
                << " (samples=" << trained_total_samples << ")" << std::endl;
    }

    virtual bool predict(uint64_t address, bool, uint64_t)
    {
      total_predictions++;
      auto it = profile_by_pte.find(address);
      if (it == profile_by_pte.end())
        return false;

      bool bypass = should_bypass(it->second);
      if (bypass)
        total_bypasses++;
      return bypass;
    }

    virtual void update(uint64_t, bool, bool, uint64_t)
    {
      // Static trace-informed filter: no online state updates.
    }

    virtual void print_stats()
    {
      std::cout << "ReuseDistanceFilter: predictions=" << total_predictions
                << " bypasses=" << total_bypasses;
      if (total_predictions > 0)
        std::cout << " (" << (100.0 * static_cast<double>(total_bypasses) / static_cast<double>(total_predictions)) << "%)";
      std::cout << std::endl;
    }
};

class BeladyOPTSetFilter : public CacheFilter {

  private:

    uint64_t sets, ways, offset_bits;

    bool save_mem_trace;
    MemoryTracer memTracer;
    MemoryTraceReader memTraceReader;
    std::vector<uint64_t> accesses_vector;
    std::map<uint64_t, std::vector<uint64_t>> access_map; // set -> address in access order

    // stats
    uint64_t total_predictions = 0, total_bypasses = 0;

    champsim::DebugLogger debugLog;

    uint32_t get_set(uint64_t address) 
    {
      return (address >> offset_bits) & champsim::bitmask(champsim::lg2(sets));
    }

  public: 
    BeladyOPTSetFilter(uint64_t _sets, uint64_t _ways, uint64_t _offset_bits): sets(_sets), ways(_ways), offset_bits(_offset_bits)
    {

      debugLog.enable();
      
      debugLog << "sets:" << sets << std::endl;
      debugLog << "ways:" << ways << std::endl;
      debugLog << "offset_bits:" << offset_bits << std::endl;
      /*
      double top_N_scale = 1.0;
      if (getenv("TXC_FILTER_TOP_N_FACTOR")) {
				top_N_scale = std::stod(getenv("TXC_FILTER_TOP_N_FACTOR"));
			} else {
				std::cerr << "TXC_FILTER_TOP_N_FACTOR not set!" << std::endl;
				exit(0);
			}
      */

      //lower_freq_threshold = 2; // default will remove freq < 2
      /*
      if (getenv("CACHE_FILTER_FREQ_THRESHOLD")) {
				std::string freq_threshold = getenv("CACHE_FILTER_FREQ_THRESHOLD");
        size_t start = 0, end = 0;
        while ((end = freq_threshold.find("-", start)) != std::string::npos) {
          lower_freq_threshold = std::stoll(freq_threshold.substr(start, end - start));
          std::cout << "lower_freq_threshold:" << lower_freq_threshold << std::endl;
          start = end + 1;
          upper_freq_threshold = std::stoll(freq_threshold.substr(start));
          std::cout << "upper_freq_threshold:" << lower_freq_threshold << std::endl;
          break;
        }

        if (end == std::string::npos) {
          lower_freq_threshold = upper_freq_threshold = std::stoll(freq_threshold.substr(start));
        }
        
			} else {
				std::cerr << "CACHE_FILTER_FREQ_THRESHOLD not set!" << std::endl;
				exit(0);
			}
      */

      /*
      if (getenv("TXC_FILTER_CLEANUP_INTERVAL")) {
				cleanup_cycle_interval = std::stoull(getenv("TXC_FILTER_CLEANUP_INTERVAL"));
			} else {
				std::cerr << "TXC_FILTER_CLEANUP_INTERVAL not set!" << std::endl;
				exit(0);
			}
      */

      std::cout << "CACHE_FILTER: Oracle MFU per set" << std::endl;
      std::cout << "\t-N: " << ways << std::endl;

      save_mem_trace = false;
      if (getenv("CACHE_FILTER_MEMORY_TRACE_PATH") != nullptr) { 
        std::string memtrace_filename = getenv("CACHE_FILTER_MEMORY_TRACE_PATH");
        if (memTraceReader.open_tracefile(memtrace_filename)) {
          std::cout << "\tReading memory trace from " << memtrace_filename << std::endl;
          save_mem_trace = false;
          accesses_vector = memTraceReader.get_accesses();
          memTraceReader.close_tracefile();

          for (auto it = accesses_vector.begin(); it != accesses_vector.end(); ++it) {
            
            //debugLog << "Add Access: " << *it << std::endl;
            uint64_t set = get_set(*it);
            //debugLog << "Add set: " << set << std::endl;
            auto set_it = access_map.find(set);
            if (set_it != access_map.end()) {
              access_map[set].push_back(*it);
            } else {
              access_map[set] = std::vector<uint64_t>();
              access_map[set].push_back(*it);
            }
            
          }
          
        } else {
          assert(0);
          std::cerr << "\tSaving memory trace to " << memtrace_filename << std::endl;
          memTracer.open_tracefile(memtrace_filename);
        }

      } else {
        std::cerr << "CACHE_FILTER_MEMORY_TRACE_PATH not set!" << std::endl;
        exit(1);
      }

    }
    
    
    // Return true if address is not in the top N frequencies
    virtual bool predict(uint64_t address, bool, uint64_t) 
    {

      total_predictions++;

      //std::cout << "Looking up address: " << address << std::endl;
      uint64_t set = get_set(address);
      //std::cout << "Looking up set: " << set << std::endl;
      auto set_it = access_map.find(set);
      if (set_it != access_map.end()) {

        std::vector<uint64_t>& accesses = set_it->second;
        // uint64_t _address = accesses[0];
        // find the address and remove all those before
        // it's better to be wrong and not bypass than to be wrong and bypass
        uint32_t i;
        for (i = 0; i < accesses.size(); i++) {
          if (accesses[i] != address) {
            //std::cout << "next address: " << accesses[i+1] << std::endl;
            break;
          }
        }
        
        //std::cout << "i: " << i << std::endl;
        //std::cout << "accesses.size(): " << accesses.size() << std::endl;
        if (i < accesses.size()) {
          accesses.erase(accesses.begin() + i);
        }
        //std::cout << "next address: " << accesses[0] << std::endl;
        //assert(address == _address);
        //auto access_it = std::find_if(set_it->second.begin(), set_it->second.end(), [address](auto x) { return x == address; });
        //exit(0);
        for (i = 0; i < ways; i++) {
          
          if (accesses[i] == address) {
            return false;
          }
        }

      } else {
        assert(0);  
      }
      
      total_bypasses++;
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

    }

    virtual void print_stats() 
    {
      if (save_mem_trace) {
        memTracer.save_tracefile();
      } else {
        std::cout << "FreqFilter: total predictions: " << total_predictions << std::endl;
        std::cout << "FreqFilter: total bypasses: " << total_bypasses << std::endl;
      }
    }
};


class SimpleFreqFilter : public CacheFilter {

  private:
    uint64_t freq_threshold;
    // stats
    uint64_t total_predictions, total_bypasses; 

  public: 
    SimpleFreqFilter() 
    {
      if (getenv("CACHE_FILTER_FREQ_THRESHOLD")) {
				freq_threshold = std::stoull(getenv("CACHE_FILTER_FREQ_THRESHOLD"));
			} else {
				std::cerr << "CACHE_FILTER_FREQ_THRESHOLD not set!" << std::endl;
				exit(0);
			}

      std::cout << "CACHE_FILTER: Simple Frequency Filter" << std::endl;
      std::cout << "\t-Frequency threshold: " << freq_threshold << std::endl;

      total_predictions = 0;
      total_bypasses = 0;
    };

    virtual bool predict(uint64_t, bool, uint64_t access_freq) override 
    {

      total_predictions++;

      //last_prediction_map.insert({address, seems_dead}); // this is for statistics
      if (freq_threshold > access_freq) {
	      total_bypasses++;
	      return true;
      }
	
      return false;
    }

    virtual void update(uint64_t, bool, bool, uint64_t) {}
    
    virtual void print_stats() 
    {
    	std::cout << "FreqFilter: total predictions: " << total_predictions << std::endl;
	    std::cout << "FreqFilter: total bypasses: " << total_bypasses << std::endl;	
    } 
};

class BloomFreqFilter : public CacheFilter {

  private:
    uint64_t FREQ_THRESHOLD;

    uint32_t FILTER_SIZE; 
    std::vector<uint64_t> prediction_table;
    uint32_t NUM_HASHES;
    std::hash<uint64_t> hasher; 
    
    // stats
    uint64_t total_predictions, total_bypasses; 
    
    // Generate different hash values using the same base hash function
    size_t hash(uint64_t key, size_t seed) {
        return hasher(key + seed * 0xdeadbeef);
    }

  public: 
    BloomFreqFilter() 
    {

      if (getenv("CACHE_FILTER_BLOOM_FILTER_SIZE")) {
				FILTER_SIZE = std::stoull(getenv("CACHE_FILTER_BLOOM_FILTER_SIZE"));
			} else {
				std::cerr << "CACHE_FILTER_BLOOM_FILTER_SIZE not set!" << std::endl;
				exit(0);
			}

      if (getenv("CACHE_FILTER_NUM_HASHES")) {
				NUM_HASHES = std::stoi(getenv("CACHE_FILTER_NUM_HASHES"));
			} else {
				std::cerr << "CACHE_FILTER_NUM_HASHES not set!" << std::endl;
				exit(0);
			}
      
      if (getenv("CACHE_FILTER_FREQ_THRESHOLD")) {
				FREQ_THRESHOLD = std::stoull(getenv("CACHE_FILTER_FREQ_THRESHOLD"));
			} else {
				std::cerr << "CACHE_FILTER_FREQ_THRESHOLD not set!" << std::endl;
				exit(0);
			}
      
      std::cout << "CACHE_FILTER: Bloom Frequency Filter" << std::endl;
      std::cout << "\t-Bloom Filter size: " << FILTER_SIZE << " elements" << std::endl;
      std::cout << "\t-Bloom Filter hashes: " << NUM_HASHES << std::endl;
      std::cout << "\t-Frequency threshold: " << FREQ_THRESHOLD << std::endl;
       
      prediction_table.resize(FILTER_SIZE, 0);

      total_predictions = 0;
      total_bypasses = 0;
    };

    virtual bool predict(uint64_t addr, bool, uint64_t) override 
    {
      total_predictions++;

      // Lookup the minimum count in the prediction table, the min should 
      // represent the frequency counter for the cache line
      uint32_t min_count = UINT32_MAX;
        
      for (size_t i = 0; i < NUM_HASHES; ++i) {
        size_t index = hash(addr, i) % FILTER_SIZE;
        uint32_t count = prediction_table[index];
        min_count = std::min(min_count, count);
      }

      if (min_count < FREQ_THRESHOLD) {
	      total_bypasses++;
	      return true;
      }
	
      return false;
    }

    virtual void update(uint64_t addr, bool, bool is_lookup, uint64_t) 
    {

      if (!is_lookup) return;

      for (size_t i = 0; i < NUM_HASHES; ++i) {
        size_t index = hash(addr, i) % FILTER_SIZE;
        prediction_table[index]++;
      }
    }
    
    virtual void print_stats() 
    {
    	std::cout << "FreqFilter: total predictions: " << total_predictions << std::endl;
	    std::cout << "FreqFilter: total bypasses: " << total_bypasses << std::endl;	

      uint64_t avg_freq = 0;
      uint64_t total_bypass_cells = 0;
      for (auto it = prediction_table.begin(); it != prediction_table.end(); ++it) {
        avg_freq += *it;
        if (*it < FREQ_THRESHOLD) {
          total_bypass_cells++;
        }
      }
      std::cout << "FreqFilter: average frequency: " << (avg_freq / prediction_table.size()) << std::endl;
      std::cout << "FreqFilter: total bypass cells: " << total_bypass_cells << std::endl;
    } 
    
    /*
    // Reset the bloom filter (call periodically to avoid saturation)
    void reset() {
        for (auto& counter : filter) {
            counter.store(0, std::memory_order_relaxed);
        }
    }
    */

};


class FreqFilter : public CacheFilter {

  private:
    uint64_t FREQ_THRESHOLD;

    //uint32_t FILTER_SIZE; 
    std::map<uint64_t, uint64_t> prediction_table; 
    
    // stats
    uint64_t total_predictions, total_bypasses; 

  public: 
    FreqFilter() 
    {
      
      if (getenv("CACHE_FILTER_FREQ_THRESHOLD")) {
				FREQ_THRESHOLD = std::stoull(getenv("CACHE_FILTER_FREQ_THRESHOLD"));
			} else {
				std::cerr << "CACHE_FILTER_FREQ_THRESHOLD not set!" << std::endl;
				exit(0);
			}
      
      std::cout << "CACHE_FILTER: Frequency Filter" << std::endl;
      std::cout << "\t-Frequency threshold: " << FREQ_THRESHOLD << std::endl;
       
      //prediction_table.resize(FILTER_SIZE, 0);

      total_predictions = 0;
      total_bypasses = 0;
    };

    virtual bool predict(uint64_t addr, bool, uint64_t) override 
    {
      
      total_predictions++;

      // Lookup the minimum count in the prediction table, the min should 
      // represent the frequency counter for the cache line
      uint32_t access_freq = UINT32_MAX;
        
      auto it = prediction_table.find(addr);
      if (it != prediction_table.end()) {
        access_freq = it->second;
      }

      if (access_freq < FREQ_THRESHOLD) {
	      total_bypasses++;
	      return true;
      }
	
      return false;
    }

    virtual void update(uint64_t addr, bool, bool is_lookup, uint64_t) 
    {

      if (!is_lookup) return;

      auto it = prediction_table.find(addr);
      if (it == prediction_table.end()) {
        prediction_table[addr] = 1;
      } else {
        it->second++;
      }
    }
    
    virtual void print_stats() 
    {

    	std::cout << "FreqFilter: total predictions: " << total_predictions << std::endl;
	    std::cout << "FreqFilter: total bypasses: " << total_bypasses << std::endl;	

      uint64_t avg_freq = 0;
      uint64_t total_bypass_cells = 0;
      for (auto it = prediction_table.begin(); it != prediction_table.end(); ++it) {
        avg_freq += it->second;
        if (it->second >= FREQ_THRESHOLD) {
          total_bypass_cells++;
        }
      }

      //std::cout << "BoomFreqFilter: average frequency: " << (avg_freq / prediction_table.size()) << std::endl;
      //std::cout << "BoomFreqFilter: total bypass cells: " << total_bypass_cells << std::endl;
    } 
    
    /*
    // Reset the bloom filter (call periodically to avoid saturation)
    void reset() {
        for (auto& counter : filter) {
            counter.store(0, std::memory_order_relaxed);
        }
    }
    */

};
#endif // DOA_PREDICTOR_H
