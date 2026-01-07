#!/usr/bin/python3

"""
__name__ = 
__author__ =
__description = Accepts n number of simpoints' data and corresponding 
                weights in a file and produces the summed data
"""

import argparse 
import pandas as pd
from pandas.api.types import is_string_dtype
from pandas.api.types import is_numeric_dtype
import numpy as np
import csv

### Command Line Arguments ###
parser = argparse.ArgumentParser()
parser.add_argument('--input-files', dest='input_files', required=True, default=None, nargs='+', help="List of csv files, each corresponding to a simpoint of a benchmark application")
parser.add_argument('--simpoints-file', dest='simpoints_file', required=True, default=None, help='File containing the simpoint ids')
parser.add_argument('--weights-file', dest='weights_file', required=True, default=None, help='File containing the weights of the corresponding simpoint csv files')
parser.add_argument('--exclude-columns', dest='exclude_cols', required=False, default=list(), nargs='+', help='List of columns to exclude from weights (fist df\'s values are gonna be preserved)')
parser.add_argument('--output-file', dest='output_file', required=False, default="data.csv", help="Output file name")

### Main ###
args = parser.parse_args()

assert(len(args.input_files) > 0)

# first load the weights
weights = []
weights_file = open(args.weights_file)
simpoints_file = open(args.simpoints_file, 'r')

simpoint_weights = dict()
for weight, simpoint_id in zip(weights_file, simpoints_file):
    weight = weight.split(' ')[0].replace('\n','')
    simpoint_id = simpoint_id.split(' ')[0].replace('\n', '')
    simpoint_weights[int(simpoint_id)] = float(weight)


#print(simpoint_weights)
# loading csv data #
final_df = pd.DataFrame()
#weight_index = 0
weights_sum = 0
for input_file in args.input_files:

    #parse the input file to get the simpoint id
    simpoint_id = int((input_file.split('-')[1]).split('B')[0])
    #print(simpoint_id)

    df = pd.read_csv(input_file, sep=',')
    #print(df['AVERGE_MISS_LATENCY'])
    columns = df.columns.values.tolist()
    #print(input_file)
    #print(df.head(5))

    if final_df.empty:
        final_df = df
        # remove columns that should not get weights applied
        for col in args.exclude_cols:
            columns.remove(col)     
        for col in columns:
            if not is_numeric_dtype(final_df[col]):
                continue
            final_df[col] = final_df[col] * simpoint_weights[simpoint_id]
        #weight_index += 1
        weights_sum = simpoint_weights[simpoint_id]
        continue

    # remove columns that should not get weights applied
    for col in args.exclude_cols:
        columns.remove(col)     

    # get df columns so we can iterate over all of them
    for col in columns:
        if not is_numeric_dtype(final_df[col]):
            continue
        final_df[col] = final_df[col] + (df[col] * simpoint_weights[simpoint_id])

    #weight_index += 1
    weights_sum += simpoint_weights[simpoint_id]

# apply denominator
for col in columns:
    if not is_numeric_dtype(final_df[col]):
        continue
    final_df[col] = final_df[col] / weights_sum

#print(final_df.head(5))
final_df.to_csv(args.output_file, index=False)











