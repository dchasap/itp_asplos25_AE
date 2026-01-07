#!/usr/bin/python3

"""
__name__ = 
__author__ =
__description = Appends two dataframes together
"""

import argparse	
import pandas as pd
import numpy as np
import csv

### Command Line Arguments ###
parser = argparse.ArgumentParser()
parser.add_argument('--row-names', dest='row_names', required=True, default=None, nargs='+', help="List of row names for new dataframe")
parser.add_argument('--input-files', dest='input_files', required=True, default=None, nargs='+', help="List of csv files, each corresponding to a simpoint of a benchmark application")
parser.add_argument('--output-file', dest='output_file', required=False, default="data.csv", help="Output file name")

args = parser.parse_args()

assert(len(args.input_files) > 0)


final_df = pd.DataFrame()
for input_file in args.input_files:

	df = pd.read_csv(input_file, sep=',')
	print(input_file)
	print(df.head(5))

	if final_df.empty:
		final_df = df
		continue
	
	final_df = pd.concat([final_df, df])

print(final_df.head(5))
print(args.row_names)
final_df['benchmark'] = args.row_names
final_df = final_df.dropna(axis=1)
print(final_df.head(5))
final_df.to_csv(args.output_file, index=False)





