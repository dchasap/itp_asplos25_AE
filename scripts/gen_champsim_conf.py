#!/usr/bin/env python3
import json
import sys,os
import itertools
import functools
import operator
import copy
from collections import ChainMap
import re

#dictionary for translating attributes from short to long names
attr_names = {  'bp':'branch_predictor', 'if': 'ifetch_buffer_size',
                's':'sets', 'w':'ways', 'r':'replacement', 'p':'prefetcher', 
                'h':'force_hit', 'm':'force_mon'}

def load_config(filename):
    config_file = open(filename)
    config = json.load(config_file)
    return config


def save_config(config, filename):
    #print(config_file['L1D']['sets'])
    output_file = open(filename, 'w')
    output_file.write(json.dumps(dict(config), indent=2))


def create_copy(config):
    #return config.copy()
    return copy.deepcopy(config)


def set_entry(config, context, entry, value):
    if context is None:
        config[entry] = value
    else:
        if type(config[context]) is list: # ooo_cpu is a list for some reasone
            config[context][0][entry] = value
        else:
            config[context][entry] = value



### Main ###

if len(sys.argv) >= 4:

    default_config = load_config(sys.argv[1])

    # create l2c-ship_llc-drrip config
    new_config = create_copy(default_config)
    conf_tag = sys.argv[2]
    is_smt = False
    if (sys.argv[3] == "true"):
        is_smt = True

    #print('\nCreating new configuration file with tag ' + conf_tag + "...\n")
    set_entry(new_config, None, 'executable_name', 'champsim_' + conf_tag)

    

    COMPONENTS = [ 'ooo_cpu', 'DTLB', 'ITLB', 'STLB', 'L1I', 'L1D', 'L2C', 'LLC']   
    for component in COMPONENTS:
        component_conf = re.findall( component.lower() + "-[^_]*", conf_tag)
        #print(component_conf)
        if len(component_conf):
            component_conf = re.split( "-", component_conf[0])  
            #print(component_conf)
            component_conf.pop(0)
            print(component)
            for attribute in component_conf:
                attribute = re.split('\.', attribute)
                #print(attribute)
                try: 
                    value = int(attribute[1])
                except:
                    if attribute[1].lower() == 'true':
                        value = True
                    elif attribute[1].lower() == 'false':
                        value = False
                    else:
                        if attribute[1] == "hashed":
                            value = 'hashed_perceptron'
                        else:
                            value = attribute[1]

                print("\t" + attr_names[attribute[0]] + ":" + str(value))
                set_entry(new_config, component, attr_names[attribute[0]], value)

    if (is_smt):
        print("Enabling smt workloads.")
        set_entry(new_config, 'L2C', attr_names['m'], True)  

    print("\nSaved new configuration file sim_conf/champsim_" + conf_tag + '.json.\n')
    save_config(new_config, 'sim_conf/champsim_' + conf_tag + '.json')

else:
    print("Base configuration filename and tag are required!\n")

