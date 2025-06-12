#!/usr/bin/env python3
import json
import copy


def load_config(filename):
    config_file = open(filename)
    config = json.load(config_file)
    return config


def save_config(config, filename):
    output_file = open(filename, 'w')
    output_file.write(json.dumps(dict(config), indent=2))


def create_copy(config):
    #return config.copy()
    return copy.deepcopy(config)


def set_entry(config, context, entry, value):

    if context is not None and context not in config.keys(): return

    if context is None:
        config[entry] = value
    else:
        if type(config[context]) is list: # ooo_cpu is a list of cpu cores
            config[context][0][entry] = value
        else:
            config[context][entry] = value
