
source env.sh

CONFIG_FILE=$1
source $CONFIG_FILE


python3 ${ROOT_DIR}/scripts/gen_plots_new.py	\
																							--figure "plot_ipc" \
																							--benchsuites ${BENCHSUITES} \
																							--data_files "${CONFIGURATION_TAGS}" \
																							--file_type "${PLOT_FILE_TYPE}"



#																							--figure "plot_pte_cache_eval" \
#																							--figure "plot_pte_mpki_impact" \
