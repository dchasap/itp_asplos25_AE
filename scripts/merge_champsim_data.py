#!/usr/bin/python3

"""
__name__ = merge_champsim_data.py 
__author__ = Dimitrios Chasapis
__description = Merges all benchmark data into one folder
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


final_df.to_csv(args.output_file, index=False)

