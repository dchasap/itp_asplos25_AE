#ifndef DOA_PREDICTOR_H
#define DOA_PREDICTOR_H

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

    // Prediction table: holds the confidence values for each entry
    // TODO: change to saturating counter
    struct ptable_entry_t { 
      uint64_t address; // Address associated with this entry
      uint32_t pred_cnt; // Confidence value for the prediction
    }; 

    std::vector<ptable_entry_t> prediction_table;


    uint64_t get_hash(uint64_t address) const {
      return address % (num_sets * num_ways); //TODO: check bibliography for better hash function
    }


  public:

    DOAPredictor(uint64_t sets, uint64_t ways, uint32_t max_counter_value, uint32_t thrhld) : num_sets(sets), num_ways(ways), 
        max_counter(max_counter_value) // Set threshold to half of the max counter value 
    {
        // Initialize the predictor
        // std::cout << "DOA Predictor initialized." << std::endl;
				prediction_thrhld = (max_counter_value / 2) + thrhld;
        prediction_table.resize(num_sets * num_ways);
    }


    bool predict(uint64_t address, bool seems_dead) 
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

        // FIXME: This overrides the predictor with the bias of L1D 
        if (seems_dead) return true;
        else return false;

				uint32_t bias = 0;
				if (seems_dead) bias = max_counter / 2;
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

};

#endif // DOA_PREDICTOR_H
