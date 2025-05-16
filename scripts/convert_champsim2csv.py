
"""
__name__ = convert_champsim2csv.py
__author__ = Dimitrios Chasapis
__description = Parse the raw output file of ChampSim and creates a csv file with the data
"""

import argparse 
import re
import csv
import traceback

def parse_champsim_stats(input_file, output_file):
    
    data = open(args.input_file, "r").read()
    #print(args.input_file)
    # Get Cache and TLB statistics

    CACHES = ['cpu0_DTLB', 'cpu0_ITLB', 'cpu0_STLB', 'cpu0_L1I', 'cpu0_L1D', 'cpu0_L2C', 'LLC', 'cpu0_L1D_VC']
    OPERATIONS = ['TOTAL', 'LOAD', 'RFO', 'PREFETCH', 'WRITEBACK', 'TRANSLATION']
    STATS = [   'ACCESS', 'HIT', 'MISS', 'dACCESS', 'dHIT', 'dMISS', 'iACCESS', 'iHIT', 'iMISS', 
                'dtHIT', 'dtMISS', 'itHIT', 'itMISS', 'itACCESS', 'dtACCESS',
                'REQUESTED', 'ISSUED', 'USEFUL', 'USELESS']

    CACHE_STATS = {}
    for cache in CACHES:
        CACHE_STATS[cache] = {}
        for op in OPERATIONS:
            CACHE_STATS[cache][op] = {}
            for line in re.findall( cache + "\s" + op + ".*", data):
                #print(line)
                for stat in STATS:
                    split_line = re.split("\s" + stat, line)
                    # if we did not find the the stat token, skip
                    if(len(split_line) > 1):
                        value = re.findall("\d+", split_line[1])[0]
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
        line = re.search(cache + '\sAVERAGE MISS LATENCY:\s+\d+.\d+', data)
        if (line==None):
            miss_latency = 'N/A'
        else:
            miss_latency = line.group().split()[4]
        #print(cache + ":" + miss_latency)
        AVG_MISS_LATENCIES[cache]['AVERAGE_MISS_LATENCY'] = miss_latency
    
        line = re.search(cache + '\sAVERAGE iMISS LATENCY:\s+\d+.\d+', data)
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
        line = re.search(cache + '\sPAGE CROSSINGS \(TLB HIT\):\s+\d+', data)
        #print(line.group())
        if (line==None):
            page_cross_hits = 'N/A'
        else:
            page_cross_hits = line.group().split()[5]
        #print(cache + ":" + page_cross_hits)
        PAGE_CROSSING[cache]['PAGE_CROSS_HITS'] = page_cross_hits
      	
        line = re.search(cache + '\sPAGE CROSSINGS \(TLB MISS\):\s+\d+', data)
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
        line = re.search(cache + '\sMAX OCCUPANCY:\s+\d+', data)
        #print(line.group())
        if (line==None):
            avg_occupancy = 'N/A'
        else:
            avg_occupancy = line.group().split()[3]
        #print(cache + ":" + avg_occupancy)
        AVG_OCCUPANCY[cache] = avg_occupancy
      	

    # Get IPC
    lines = re.findall('CPU 0 cumulative IPC:\s+\d+[\.]?\d*', data)
    ipc = lines[len(lines)-1].split()[4]

    # Get number of instructions
    lines = re.findall('instructions:\s+\d+', data)
    instructions = lines[len(lines)-4].split()[1]

    # Get number of cycles
    lines = re.findall('cycles:\s+\d+', data)
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
            new_row.append(ipc)
            new_row.append(instructions)
            new_row.append(cycles)
            writer.writerow(new_row)


### Command Line Arguments ###
parser = argparse.ArgumentParser()
parser.add_argument('--input-file', dest='input_file', required=True, default=None, help="Raw champsim output file")
parser.add_argument('--output-file', dest='output_file', required=False, default="data.csv", help="Output csv file name")

args = parser.parse_args()

try:
    parse_champsim_stats(args.input_file, args.output_file)
except Exception as e:
    print("Parsing Failed: " + args.input_file)
    print(e)
    print(traceback.format_exc())

