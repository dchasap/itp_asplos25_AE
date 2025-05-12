#!/bin/bash

source env.sh
source ${ROOT_DIR}/scripts/unpack_tags.sh

export CONFIG_FILE=$1
source ${CONFIG_FILE}

UNPACKED_CONFIGURATION_TAGS=$(unpack_tags ${CONFIG_FILE} "${CONFIGURATION_TAGS}")
echo "get_tag returns: ${UNPACKED_CONFIGURATION_TAGS}"	

python3 ${ROOT_DIR}/scripts/gen_plots_new.py	\
																							--figure "plot_ipc" \
																							--benchsuites ${BENCHSUITES} \
																							--data_files ${UNPACKED_CONFIGURATION_TAGS} \
																							--file_type "${PLOT_FILE_TYPE}"

