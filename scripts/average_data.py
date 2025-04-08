#!/usr/bin/python3

"""
__name__ = averge_data.py 
__author__ = Dimitrios Chasapis
__description = Computes the average of multiple data inputs
"""

import argparse	
import pandas as pd
import numpy as np
import csv

### Command Line Arguments ###
parser = argparse.ArgumentParser()
parser.add_argument('--benchmarks', dest='benchmarks', required=True, default=None, nargs='+', help="List of benchmark names, must correspond to the list of csv input files")
parser.add_argument('--input-files', dest='input_files', required=True, default=None, nargs='+', help="List of csv files, eacho corresponding to a different benchmarks")
parser.add_argument('--output-file', dest='output_file', required=False, default="data.csv", help="Output csv file with all benchmarks")

args = parser.parse_args()

benchmarks = args.benchmarks
input_files = args.input_files

merged_df = pd.DataFrame()
for input_file in input_files:

	#bench = benchmarks.pop(0) 
	df = pd.read_csv(input_file, sep=',')
	#df['benchmarks'] = bench

	if merged_df.empty:
		merged_df = df
		continue

	#print("-------- orig final ---------")	
	#print(merged_df.head(5))
	#print("-------- orig  new  ---------")	
	#print(df.head(5))
	merged_df = pd.concat([merged_df, df])
	mean_df = merged_df.groupby(level=0).mean()
	#final_df = by_row_index.mean()
	#print("-------   merged   ---------")	
	#print(mean_df.head(5))


mean_df.to_csv(args.output_file, index=False)

