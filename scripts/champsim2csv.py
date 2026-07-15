
"""
__name__ = convert_champsim2csv.py
__author__ = Dimitrios Chasapis
__description = Parse the raw output file of ChampSim and creates a csv file with the data
"""

import argparse 
import re
import csv
import pandas as pd
import numpy as np

def parse_champsim_stats(input_file, output_file):
    
    data = open(input_file, "r").read()
    #print(args.input_file)
    # Get Cache and TLB statistics

    CACHES = ['cpu0_DTLB', 'cpu0_ITLB', 'cpu0_STLB', 'cpu0_L1I', 'cpu0_L1D', 'cpu0_L2C', 'LLC', 'TXVC']
    OPERATIONS = ['TOTAL', 'LOAD', 'RFO', 'PREFETCH', 'WRITEBACK', 'TRANSLATION']
    STATS = [   'ACCESS', 'HIT', 'MISS', 'dACCESS', 'dHIT', 'dMISS', 'iACCESS', 'iHIT', 'iMISS', 
                'dtHIT', 'dtMISS', 'itHIT', 'itMISS', 'itACCESS', 'dtACCESS',
                'REQUESTED', 'ISSUED', 'USEFUL', 'USELESS']

    CACHE_STATS = {}
    for cache in CACHES:
        CACHE_STATS[cache] = {}
        for op in OPERATIONS:
            CACHE_STATS[cache][op] = {}
            for line in re.findall( cache + r"\s" + op + ".*", data):
                #print(line)
                for stat in STATS:
                    split_line = re.split(r"\s" + stat, line)
                    # if we did not find the the stat token, skip
                    if(len(split_line) > 1):
                        value = re.findall(r"\d+", split_line[1])[0]
                        CACHE_STATS[cache][op][stat] = value
                        #print(cache + "-" + op + "-" + stat + ":" + value)
                    elif (len(split_line) == 1):
                        if (stat in CACHE_STATS[cache][op] 
                            and CACHE_STATS[cache][op][stat] != 'N/A'):
                                continue
                        #print(CACHE_STATS[cache][op][stat])
                        CACHE_STATS[cache][op][stat] = 'N/A'
                        #print(cache + "-" + op + "-" + stat + ":N/A")
    #print(data)
    # Get average miss latencies
    AVG_MISS_LATENCIES = {}
    for cache in CACHES:
        AVG_MISS_LATENCIES[cache] = {}
        line = re.search(cache + r'\sAVERAGE MISS LATENCY:\s+\d+.\d+', data)
        if (line==None):
            miss_latency = 'N/A'
        else:
            miss_latency = line.group().split()[4]
        #print(cache + ":" + miss_latency)
        AVG_MISS_LATENCIES[cache]['AVERAGE_MISS_LATENCY'] = miss_latency
    
        line = re.search(cache + r'\sAVERAGE iMISS LATENCY:\s+\d+.\d+', data)
        if (line == None):
            imiss_latency = 'N/A'
        else:
            imiss_latency = line.group().split()[4]
        #print(cache + ":" + imiss_latency)
        AVG_MISS_LATENCIES[cache]['AVERAGE_iMISS_LATENCY'] = imiss_latency
        if (line == None):
            dmiss_latency = 'N/A'
        else:
            dmiss_latency = line.group().split()[4]
        #print(cache + ":" + dmiss_latency)
        AVG_MISS_LATENCIES[cache]['AVERAGE_dMISS_LATENCY'] = dmiss_latency

    # Get page crossing
    PAGE_CROSSING = {}
    for cache in CACHES:
        PAGE_CROSSING[cache] = {}
        line = re.search(cache + r'\sPAGE CROSSINGS \(TLB HIT\):\s+\d+', data)
        #print(line.group())
        if (line==None):
            page_cross_hits = 'N/A'
        else:
            page_cross_hits = line.group().split()[5]
        #print(cache + ":" + page_cross_hits)
        PAGE_CROSSING[cache]['PAGE_CROSS_HITS'] = page_cross_hits
      	
        line = re.search(cache + r'\sPAGE CROSSINGS \(TLB MISS\):\s+\d+', data)
        if (line==None):
            page_cross_misses = 'N/A'
        else:
            page_cross_misses = line.group().split()[5]
        #print(cache + ":" + page_cross_misses)
        PAGE_CROSSING[cache]['PAGE_CROSS_MISSES'] = page_cross_misses
    
   # Get average occupancy
    AVG_OCCUPANCY = {}
    for cache in CACHES:
        AVG_OCCUPANCY[cache] = {}
        line = re.search(cache + r'\sMAX OCCUPANCY:\s+\d+', data)
        #print(line.group())
        if (line==None):
            avg_occupancy = 'N/A'
        else:
            avg_occupancy = line.group().split()[3]
        #print(cache + ":" + avg_occupancy)
        AVG_OCCUPANCY[cache] = avg_occupancy

    # Get PTE level statistics (levels 0-4).
    # Note: in output only the first token is prefixed by cache name, e.g.
    # "cpu0_L1D pte_level_accesses 0: ...  pte_level_accesses 1: ..."
    # so we must parse all level/value pairs from that single line.
    PTE_LEVEL_STATS = {}
    PTE_STAT_TYPES = ['pte_level_accesses', 'pte_level_hits', 'pte_level_misses']
    for cache in CACHES:
        PTE_LEVEL_STATS[cache] = {}
        for stat_type in PTE_STAT_TYPES:
            # Initialize defaults first
            for level in range(5):
                PTE_LEVEL_STATS[cache][f'{stat_type}_{level}'] = 'N/A'

            line = re.search(cache + r'\s+' + stat_type + r'.*', data)
            if line is None:
                continue

            # Extract all pairs like: pte_level_accesses 2: 436
            for lvl_str, value in re.findall(stat_type + r'\s+(\d+):\s*(\d+)', line.group()):
                lvl = int(lvl_str)
                if 0 <= lvl < 5:
                    PTE_LEVEL_STATS[cache][f'{stat_type}_{lvl}'] = value

    # Get CACHE FILTER stats
    lines = re.findall(r'DBPRED: prediction accuracy:\s+\d+[\.]?\d*%', data)
    if (len(lines) == 0):
        cache_filter_accuracy = 'N/A'
    else:
        #print(lines)
        cache_filter_accuracy = lines[0].split()[3].replace('%', '')
        #print(cache_filter_accuracy)

    #TODO: Add cache filter specific stats 
    #CACHE_FILTER_STATS = [ '' ]

    # Get total TXVC bypass predictions
    #print(data)
    lines = re.findall(r'FreqFilter: total predictions:\s+\d+', data)
    if (len(lines) == 0):
        total_txvc_predictions = 'N/A'
    else:
        #print(lines)
        total_txvc_predictions = lines[0].split()[3]
        #print(total_txvc_bypasses)

    # Get total TXVC bypasses
    #print(data)
    lines = re.findall(r'FreqFilter: total bypasses:\s+\d+', data)
    if (len(lines) == 0):
        total_txvc_bypasses = 'N/A'
    else:
        #print(lines)
        total_txvc_bypasses = lines[0].split()[3]
        #print(total_txvc_bypasses)

    # Get TXVC prefetch lifetime stats
#    TXVC_PREFETCH_LIFETIME_STATS = {}
#    TXVC_PF_LT_STATS = [
#        'INSERTED', 'FIRST_USE', 'FIRST_USE_RATE', 'AVG_FIRST_USE_LAT',
#        'EVICTED_NO_USE', 'EVICTED_AFTER_USE', 'EVICTED_USEFUL_RATE',
#        'AVG_EVICTED_RES', 'AVG_USEFUL_EVICTED_RES',
#        'LIVE_PREF', 'LIVE_PREF_USED'
#    ]
#    line = re.search(r'TXVC\sPREFETCH-LIFETIME.*', data)
#    for stat in TXVC_PF_LT_STATS:
#        TXVC_PREFETCH_LIFETIME_STATS[stat] = 'N/A'
#    if (line != None):
#       line = line.group()
    #     token_map = {
    #         'INSERTED': r'INSERTED:\s+\d+',
    #         'FIRST_USE': r'FIRST_USE:\s+\d+',
    #         'FIRST_USE_RATE': r'FIRST_USE_RATE\(%\):\s+[\d\.]+',
    #         'AVG_FIRST_USE_LAT': r'AVG_FIRST_USE_LAT\(cyc\):\s+[\d\.]+',
    #         'EVICTED_NO_USE': r'EVICTED_NO_USE:\s+\d+',
    #         'EVICTED_AFTER_USE': r'EVICTED_AFTER_USE:\s+\d+',
    #         'EVICTED_USEFUL_RATE': r'EVICTED_USEFUL_RATE\(%\):\s+[\d\.]+',
    #         'AVG_EVICTED_RES': r'AVG_EVICTED_RES\(cyc\):\s+[\d\.]+',
    #         'AVG_USEFUL_EVICTED_RES': r'AVG_USEFUL_EVICTED_RES\(cyc\):\s+[\d\.]+',
    #         'LIVE_PREF': r'LIVE_PREF:\s+\d+',
    #         'LIVE_PREF_USED': r'LIVE_PREF_USED:\s+\d+'
    #     }
    #     for stat in TXVC_PF_LT_STATS:
    #         _line = re.search(token_map[stat], line)
    #         if (_line != None):
    #             TXVC_PREFETCH_LIFETIME_STATS[stat] = re.findall(r'[\d\.]+', _line.group())[0]

    # # Get TXVC predictor entry lifetime stats (generic prefetcher line)
    # TXVC_ENTRY_LIFETIME_STATS = {}
    # TXVC_ENTRY_STATS = [
    #     'ALLOC', 'REPL', 'REPL_BEFORE_ISSUE', 'REPL_AFTER_ISSUE',
    #     'AVG_REPL_LIFETIME_TICKS', 'LIVE', 'LIVE_WITH_ISSUE'
    # ]
    # for stat in TXVC_ENTRY_STATS:
    #     TXVC_ENTRY_LIFETIME_STATS[stat] = 'N/A'

    # lines = re.findall(r'(?:TXVC\s+\w+|PF\s+CHILD|PF\s+SBLG)\s+ENTRY-LIFETIME.*', data)
    # if (len(lines) > 0):
    #     line = lines[0]
    #     for stat in TXVC_ENTRY_STATS:
    #         _line = re.search(stat + r':\s*[\d\.]+', line)
    #         if (_line != None):
    #             TXVC_ENTRY_LIFETIME_STATS[stat] = re.findall(r'[\d\.]+', _line.group())[0]

    # Parse unified PF drop-reason stats (collect all key:number pairs
    # from any prefetcher "PF ... DROP-REASONS" lines and aggregate). If
    # a key is never seen, export 'N/A'. This mirrors logic in
    # convert_champsim2csv.py.
    # Unified Prefetcher drop-reason keys (union of child & sibling keys)
    PF_DROP_REASON_KEYS = [
        'NO_PENDING_PARENT', 'PENDING_OVERWRITE_COLLISION',
        'TRAIN_REPLACE_MISMATCH', 'LEAF_NO_PREDICT', 'UC_DISABLED',
        'PRED_INVALID', 'PRED_TAG_MISMATCH', 'PRED_CONF_BLOCKED', 'PRED_ZERO_DELTA',
        'PRED_ISSUED', 'ISSUE_MSHR_BLOCKED', 'ISSUE_ENQUEUE_FAILED'
    ]

    PF_DROP_REASON_STATS = {}
    PF_DROP_SEEN = {}
    for key in PF_DROP_REASON_KEYS:
        PF_DROP_REASON_STATS[key] = 0
        PF_DROP_SEEN[key] = False

    matches = re.findall(r'PF\s+DROP-REASONS.*', data)
    for m in matches:
        pairs = re.findall(r'([A-Z0-9_]+):(\d+)', m)
        for k, v in pairs:
            if k in PF_DROP_REASON_STATS:
                PF_DROP_REASON_STATS[k] += int(v)
                PF_DROP_SEEN[k] = True

    # Parse ENTRY-LIFETIME lines (match PF ENTRY-LIFETIME, PF CHILD/SBLG, or TXVC <name> ENTRY-LIFETIME)
    PF_ENTRY_STATS = [
        'ALLOC', 'REPL', 'REPL_BEFORE_ISSUE', 'REPL_AFTER_ISSUE',
        'AVG_REPL_LIFETIME_TICKS', 'LIVE', 'LIVE_WITH_ISSUE'
    ]
    PF_ENTRY_LIFETIME_STATS = {}
    for stat in PF_ENTRY_STATS:
        PF_ENTRY_LIFETIME_STATS[stat] = 'N/A'

    lines = re.findall(r'(?:TXVC\s+\w+|PF(?:\s+\w+)?)\s+ENTRY-LIFETIME.*', data)
    if (len(lines) > 0):
        line = lines[0]
        for stat in PF_ENTRY_STATS:
            _line = re.search(stat + r':\s*[\d\.]+', line)
            if (_line != None):
                PF_ENTRY_LIFETIME_STATS[stat] = re.findall(r'[\d\.]+', _line.group())[0]

    # Parse PF TABLES DIAGNOSTIC lines (ZERO_ENTRIES, KEYS_NOT_IN_UNIQUE_PTES)
    zero_entries = 'N/A'
    keys_not_in_unique = 'N/A'
    m = re.search(r'PF TABLES DIAGNOSTIC .*ZERO_ENTRIES:(\d+) .*KEYS_NOT_IN_UNIQUE_PTES:(\d+)', data)
    if m:
        zero_entries = m.group(1)
        keys_not_in_unique = m.group(2)

    # Get IPC
    lines = re.findall(r'CPU 0 cumulative IPC:\s+\d+[\.]?\d*', data)
    ipc = lines[len(lines)-1].split()[4]

    # Get number of instructions
    lines = re.findall(r'instructions:\s+\d+', data)
    instructions = lines[len(lines)-4].split()[1]

    # Get number of cycles
    lines = re.findall(r'cycles:\s+\d+', data)
    cycles = lines[len(lines)-1].split()[1]


    # Export data to csv format
    output_file = open(output_file, 'w')
    writer = csv.writer(output_file)
    header = [i for i in STATS]
    header.insert(0, 'OP')
    header.insert(0, 'CACHE')

    header.append('MAX_OCCUPANCY')

    header.append('AVERAGE_MISS_LATENCY')
    header.append('AVERAGE_iMISS_LATENCY')
    header.append('AVERAGE_dMISS_LATENCY')

    header.append('PAGE_CROSS_HITS')
    header.append('PAGE_CROSS_MISSES')

    header.append('CACHE_FILTER_ACCURACY')
    header.append('TXVC_PREDICTIONS')
    header.append('TXVC_BYPASSES')

    for stat in PF_ENTRY_STATS:
        header.append('PF_PREFETCHER_ENTRY_' + stat)

    # PF tables diagnostic fields
    header.append('PF_TABLES_ZERO_ENTRIES')
    header.append('PF_TABLES_KEYS_NOT_IN_UNIQUE_PTES')

    for key in PF_DROP_REASON_KEYS:
        header.append('PF_DROP_' + key)

    # Add PTE level statistics columns
    for stat_type in ['pte_level_accesses', 'pte_level_hits', 'pte_level_misses']:
        for level in range(5):  # PTE levels 0-4
            header.append(f'{stat_type}_{level}')

    header.append('IPC')
    header.append('INSTRUCTIONS')
    header.append('CYCLES')

    #print(header)
    writer.writerow(header)
    for cache in CACHE_STATS:
        for op in CACHE_STATS[cache]:
            new_row = [cache, op]
            for stat in CACHE_STATS[cache][op]:
                new_row.append(str(CACHE_STATS[cache][op][stat]))

            new_row.append(AVG_OCCUPANCY[cache])
            new_row.append(AVG_MISS_LATENCIES[cache]['AVERAGE_MISS_LATENCY'])
            new_row.append(AVG_MISS_LATENCIES[cache]['AVERAGE_iMISS_LATENCY'])
            new_row.append(AVG_MISS_LATENCIES[cache]['AVERAGE_dMISS_LATENCY'])
            new_row.append(PAGE_CROSSING[cache]['PAGE_CROSS_HITS'])
            new_row.append(PAGE_CROSSING[cache]['PAGE_CROSS_MISSES'])
            new_row.append(cache_filter_accuracy)
            new_row.append(total_txvc_predictions)
            new_row.append(total_txvc_bypasses)

            for stat in PF_ENTRY_STATS:
                new_row.append(PF_ENTRY_LIFETIME_STATS[stat])

            # PF tables diagnostic values (same for all rows)
            new_row.append(zero_entries)
            new_row.append(keys_not_in_unique)

            # for stat in TXVC_PF_LT_STATS:
            #     new_row.append(TXVC_PREFETCH_LIFETIME_STATS[stat])

            # for stat in TXVC_ENTRY_STATS:
            #     new_row.append(TXVC_ENTRY_LIFETIME_STATS[stat])

            # Append unified PF_DROP_<KEY> values (aggregate across prefetchers)
            for key in PF_DROP_REASON_KEYS:
                if PF_DROP_SEEN.get(key, False):
                    new_row.append(str(PF_DROP_REASON_STATS.get(key, 0)))
                else:
                    new_row.append('N/A')

            # Add PTE level statistics values
            for stat_type in ['pte_level_accesses', 'pte_level_hits', 'pte_level_misses']:
                for level in range(5):  # PTE levels 0-4
                    new_row.append(PTE_LEVEL_STATS[cache][f'{stat_type}_{level}'])

            new_row.append(ipc)
            new_row.append(instructions)
            new_row.append(cycles)
            writer.writerow(new_row)


"""
__name__ = merge_champsim_data.py 
__author__ = Dimitrios Chasapis
__description = Merges all benchmark data into one folder
"""
def merge_champsim_data(input_files, benchmarks, output_file):

    final_df = pd.DataFrame()
    for input_file in input_files:

        bench = benchmarks.pop(0)
        df = pd.read_csv(input_file, sep=',')
        df['benchmarks'] = bench
        
        if final_df.empty:
            final_df = df
            continue

    #	print("-------- orig final ---------")	
    #	print(final_df.head(5))
    #	print("-------- orig  new  ---------")	
    #	print(df.head(5))
        final_df = pd.concat([final_df, df], axis=0)
    #	print("-------   merged   ---------")	
    #	print(final_df.head(50))

    final_df.to_csv(output_file, index=False)



def merge_simpoint_data(input_files, weights, output_file):
    
    dfs = []
    for input_file in input_files:
        df = pd.read_csv(input_file, sep=',')
        dfs.append(df)

    # Ensure weights sum to 1
    weights = np.array(weights) / sum(weights)

    # Auto-detect column types if not specified
    sample_df = dfs[0]
    numeric_cols = sample_df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = sample_df.select_dtypes(exclude=[np.number]).columns.tolist()
    
    #print(f"Numeric columns: {numeric_cols}")
    #print(f"Categorical columns: {categorical_cols}")

    # Create weighted dataframes
    weighted_dfs = []
    for df, weight in zip(dfs, weights):
        weighted_df = df[numeric_cols] * weight
        weighted_dfs.append(weighted_df)

    # Sum the weighted dataframes
    numeric_df = pd.concat(weighted_dfs).groupby(level=0).sum()

    # For categorical columns, just take the first dataframe's values
    # (assuming they're identical across all dataframes)
    categorical_df = dfs[0][categorical_cols].copy()
    
    # Combine the results
    final_df = pd.concat([numeric_df, categorical_df], axis=1)
    
    # Reorder columns to match original order
    original_order = dfs[0].columns.tolist()
    final_df = final_df[original_order]
    #print(final_df)
    final_df.to_csv(output_file, index=False)