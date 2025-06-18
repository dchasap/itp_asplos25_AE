#ifndef DOA_PREDICTOR_H
#define DOA_PREDICTOR_H

#define _DOA_BUDGETED

#include <iostream>
#include <algorithm>
#include <vector>

class DOAPredictor {

  private:
    uint64_t num_sets; 
    uint64_t num_ways;

    uint32_t max_counter; // Maximum value for the prediction counter
    uint32_t min_counter = 0; // Minimum value for the prediction counter
    uint32_t prediction_thrhld; // Threshold for prediction confidence

    bool use_bias_flag = false;
    bool enabled = false;

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


    uint64_t get_hash(uint64_t address) const {
      return address % (num_sets * num_ways); //TODO: check bibliography for better hash function
    }


  public:

    DOAPredictor(uint64_t sets, uint64_t ways, uint32_t max_counter_value, uint32_t thrhld, bool _enabled) : num_sets(sets), num_ways(ways), 
        max_counter(max_counter_value), enabled(_enabled) // Set threshold to half of the max counter value 
    {

      if (!enabled) return;

      // Initialize the predictor
      // std::cout << "DOA Predictor initialized." << std::endl;
			if (thrhld > 0) { 
        prediction_thrhld = thrhld;
      } else {
        prediction_thrhld = max_counter / 2;
      }

      prediction_table.resize(num_sets * num_ways);

      char* use_bias = getenv("TXC_DBPRED_USE_BIAS");
		  if (strcmp(use_bias, "true") == 0) {
			  use_bias_flag = true;
		  }

      std::cout << "TXVC: Using DOA prediction:" << std::endl;
#if defined _DOA_BUDGETED
      std::cout << "\t- sets: " << num_sets << std::endl;
      std::cout << "\t- ways: " << num_ways << std::endl;
#else 
      std::cout << "\t- No collisions!" << std::endl;
#endif
      std::cout << "\t- max_counter_value: " << max_counter << std::endl;
      std::cout << "\t- prediction theshold: " << prediction_thrhld << std::endl; 
      std::cout << "\t- Use bias: " << (use_bias_flag?"true":"false") << std::endl;
    }

#if defined _DOA_BUDGETED
    bool predict(uint64_t address, bool seems_dead) 
    {

      if (!enabled) return false;
        // FIXME: This overrides the predictor with the bias of L1D 
        //if (seems_dead) return true;
        //else return false;
        
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


    void update(uint64_t address, bool is_doa) 
    {

        if (!enabled) return;

        uint32_t hash_index = get_hash(address);

        if (prediction_table[hash_index].address != address) {
            // If the address is not found, initialize it
            prediction_table[hash_index].address = address;
            prediction_table[hash_index].pred_cnt = 0; // Start with a neutral prediction
        }

        if (is_doa) {
          prediction_table[hash_index].pred_cnt = std::min(prediction_table[hash_index].pred_cnt++, max_counter); // Increase confidence
        } else {
          prediction_table[hash_index].pred_cnt = std::max(prediction_table[hash_index].pred_cnt--, min_counter); // Decrease confidence
        }

    }

#else

    bool predict(uint64_t address, bool seems_dead) 
    {
        // FIXME: This overrides the predictor with the bias of L1D 
        //if (seems_dead) return true;
        //else return false;
        
        if (!enabled) return false;

        //use_bias_flag = false;
				uint32_t bias = 0;
				if (seems_dead && use_bias_flag) bias = max_counter / 2;
        
        total_predictions++;

        std::cout << "BDPredictor: Looking up " << address << std::endl;
        auto pred_it = prediction_map.find(address);

        if (pred_it == prediction_map.end()) {
            // If the address is not found, initialize it
            //prediction_map[address] = 0; // should use insert instead?
            std::cout << "\tnot found, inserting with cntr value " << bias << std::endl;
            prediction_map.insert({address, bias});
            std::cout << "\tprediction false" << std::endl;
            return false;
        }

				
        uint32_t prediction = prediction_map[address];
        last_prediction_map.insert({address, prediction}); // this is for statistics
        
        if (prediction >= prediction_thrhld) {
            std::cout << "\tprediction true" << std::endl;
            return true; // Prediction is doa
        } else {
            std::cout << "\tprediction false" << std::endl;
            //std::cout << "Prediction miss for address: " << address << std::endl;
            return false; // Prediction is not doa
        }

    }


    void update(uint64_t address, bool is_doa) 
    {
        
        if (!enabled) return false;

        std::cout << "BDPredictor: Updating " << address << std::endl;
        auto pred_it = prediction_map.find(address);

        if (pred_it == prediction_map.end()) {
            // If the address is not found, initialize it
            //prediction_map[address] = 0; // should use insert instead?
            std::cout << "\tnot found, inserting now" << std::endl;
            prediction_map.insert({address, 0});
            last_prediction_map.insert({adddress, 0});
          }

        uint32_t prediction_val = prediction_map[address];
        if (is_doa) {
          std::cout << "\tincreasing cntr value to " << std::min(prediction_val+1, max_counter); << std::endl;
          prediction_map[address] = std::min(prediction_val+1, max_counter); // Increase confidence
        } else {
          std::cout << "\tdecreasing cntr value to " << std::max(prediction_val-1, max_counter); << std::endl;
          prediction_map[address] = std::max(prediction_val-1, min_counter); // Decrease confidence
        }

        if (predictions_val == last_prediction_map[address]) {
          total_correct_predictions++;
        } else {
          total_wrong_predictions++;
        }

    }
#endif

    void print_stats(void) 
    {
      if (total_predictions > 0)
        std::cout << "BdPRED: prediction accuracy: " << (total_correct_predictions*100) / total_predictions << std::endl; 
      else
      std::cout << "BdPRED: prediction accuracy: 0" << std::endl;  

      std::cout << "BDPRED: total predictions: " << total_predictions << std::endl;
      std::cout << "BDPRED: total correct predictions: " << total_correct_predictions << std::endl;
      std::cout << "BDPRED: total wrong predictions: " << total_wrong_predictions << std::endl; 
    } 

};

#endif // DOA_PREDICTOR_H
