
import pandas as pd
from scipy.stats import gmean
import itertools


ENABLE_DEBUG = True

def debug_print(message):
    
    if (ENABLE_DEBUG):
        print(message)


def load_df(input_data_files, tags, cache_type, op_type, sort = False, sorted_index = None):
		# create data dataframe
		df = pd.DataFrame()
		i = 0
		for input_file in input_data_files:
				print(input_file)
				print(tags)
				tag = tags[i] #.pop(0) 
				new_df = pd.read_csv(input_file, sep=',', index_col='benchmarks')

				if (isinstance(cache_type, list)):
					new_df = new_df.loc[(new_df['CACHE'].isin(cache_type)) & (new_df['OP'] == op_type)]
				else:
					new_df = new_df.loc[(new_df['CACHE'] == cache_type) & (new_df['OP'] == op_type)]

				new_df['tag'] = tag
				new_df['MPKI'] = (new_df['MISS'] * 1000) / new_df['INSTRUCTIONS']
				new_df['iMPKI'] = (new_df['iMISS'] * 1000) / new_df['INSTRUCTIONS']
				new_df['dMPKI'] = (new_df['dMISS'] * 1000) / new_df['INSTRUCTIONS']
				new_df['itMPKI'] = (new_df['itMISS'] * 1000) / new_df['INSTRUCTIONS']
				new_df['dtMPKI'] = (new_df['dtMISS'] * 1000) / new_df['INSTRUCTIONS']

				if df.empty:
						if (sort):
							if (sorted_index is None):
								new_df = new_df.sort_values(by=['MPKI'], ascending=False)		
								sorted_index = new_df.index.values.tolist() 
							else:
								new_df = new_df.reindex(sorted_index)

						new_df['benchmarks'] = new_df.index
						df = new_df
				else:
						if (sort):
							new_df = new_df.reindex(sorted_index)

						new_df['benchmarks'] = new_df.index
						df = pd.concat([df, new_df])

				i += 1 # that's for tags' list

		return df

def load_reuse_dist_df(input_data_files, tags):
		# create data dataframe
		df = pd.DataFrame()
		i = 0
		for input_file in input_data_files:
				tag = tags[i] #.pop(0) 
				new_df = pd.read_csv(input_file, sep=',')

				new_df['tag'] = tag

				if df.empty:
						df = new_df
				else:
						df = pd.concat([df, new_df])

				i += 1 # that's for tags' list

		print(df)
		return df


def compute_variation(baseline_df, df, tags, col_name, new_col_name, revert=False): 

	# scale baseline_df is smaller than df
	if (len(df.index) > len(baseline_df.index)):
		scale_by = int(len(df.index) / len(baseline_df.index))
		baseline_orig_df = baseline_df
		for i in range(1, scale_by):
			baseline_df['tag1'] = tags[i] #FIXME: is this correct? why tag1?
			baseline_df = pd.concat([baseline_df, baseline_orig_df])
	# compue improvement
	if (revert):
		df[new_col_name] = ((baseline_df[col_name] - df[col_name]) * 100 / df[col_name])
	else:
		print(len(df))
		print(len(baseline_df))
		df[new_col_name] = ((df[col_name] - baseline_df[col_name]) * 100 / baseline_df[col_name])

	return df


def compute_stat(df, stat_name):

	if stat_name == "MPKI":
		return df
	elif stat_name == "MISS_CYCLES_":
		df['MISS_CYCLES'] = (df['MISS'] * df['AVERAGE_MISS_LATENCY'].fillna(1))
		df['MISS_CYCLES'] = df['MISS_CYCLES'] / ( df['CYCLES'])
		df['MISS_CYCLES'] = df['MISS_CYCLES'] * 100
		#TODO: this is only valid for ITLB
		#TODO: 6 is hardcoded value for fetch width
	elif stat_name == "MISS_CYCLES":
		speedup = 1.00 + (df["IPC_IMPROVEMENT"] / 100)
		df["MISS_CYCLES"] = (1 - (1/speedup)) * 100
	elif stat_name == "HIT_RATIO":
		df['HIT_RATIO'] = (df['HIT'] / df['ACCESS']) * 100

	return df


def filter_df(df, col, thrshld):

	return df[df[col] >= thrshld]


def sort_df(df, orig_tags, col, order):

	df = df.sort_values(by=['IPC_IMPROVEMENT'], ascending=order)
	new_df = pd.DataFrame()
	for tag in orig_tags:	
		filtered_df = df.loc[df['tag'] == tag]
		#filtered_df = filtered_df.sort_values(by=['IPC_IMPROVEMENT'], ascending=order)
		new_df = new_df.append(filtered_df, ignore_index=False)

	df = new_df

	return df


def compute_mean(df, tags, stat_name, mean_func, inplace=False):
 
	means = []
	for tag in tags:
		if (mean_func == "geomean"):
			mean = gmean(abs(df.loc[(df['tag'] == tag)][stat_name]))
		elif (mean_func == "mean"):
			mean = df.loc[(df['tag'] == tag)][stat_name].mean()
		elif (mean_func == "median"):
			mean = df.loc[(df['tag'] == tag)][stat_name].median()
		else:
			print(mean_func + " is not a valid mean function!")
		
		means.append(mean)
	    
		debug_print(tag + ":" + str(mean))	

	#if (inplace):
		
	means_df = pd.DataFrame({'benchmarks':mean_func, 'tag':tags, 'mean':means})
	debug_print(means_df)

	return means_df

def compute_means(df, cache_types, tags, stat_names, mean_func, inplace=False):
	
	means = {}
	for stat in stat_names:		
		means[stat] = []
		  
	caches = []
	confs = []
	for cache in cache_types: 
		for tag in tags:
			for stat in stat_names:
				if (mean_func == "geomean"):
					mean = gmean(abs(df.loc[(df['tag'] == tag)][stat]))
				elif (mean_func == "mean"):
					mean = df.loc[(df['tag'] == tag)][stat].mean()
				elif (mean_func == "median"):
					mean = df.loc[(df['tag'] == tag)][stat].median()
				else:
					print(mean_func + " is not a valid mean function!")
		
				means[stat].append(mean)
			
			caches.append(cache)
			confs.append(tag)	
	    
			debug_print(tag + ":" + stat + ":" + str(mean))	
		
	means_df = pd.DataFrame({'benchmarks':'geomean', 'cache':caches, 'tag': confs, 'mean':means['MPKI']})
	for stat in stat_names:
		means_df[stat] = means[stat]
	
	debug_print(means_df)
	
	return means_df
