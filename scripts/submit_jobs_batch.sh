#!/bin/bash

source ./env.sh

BENCHSUITE=$1 
BIN=$2
DESCR_TAG=$3

source ${ROOT_DIR}/scripts/benchmarks.sh
export TRACE_DIR="${TRACE_DIR}/${TRACES_PATH}"

mkdir -p ${DUMP_DIR}

TRACES_batch=(${TRACES})

if [ "${DEBUG_RUN}" == "True" ]; then
	echo "Running Debug mode"
	DEBUG='gdb -batch -ex "run" -ex "bt" --args'
	JOB_QUEUE=gp_debug
else 
	DEBUG='gdb -batch -ex "run" -ex "bt" --args'
	JOB_QUEUE=gp_bsccs
fi


for (( ti=0; ti < ${#TRACES_batch[@]}; ti++ )) ; do

echo "#!/bin/bash

#SBATCH -o ${DUMP_DIR}/${BENCHSUITE}_${ti}${DESCR_TAG}_run.out 
#SBATCH -J chmpS_${BENCHSUITE}_${ti}${DESCR_TAG}_run
#SBATCH -A bsc18
#SBATCH --qos=${JOB_QUEUE}
#SBATCH --time=${SIM_TIME}

traces=(${TRACES})

for i in {${ti}..$(( ti+BATCH_SIZE ))};do

	trace=\${traces[\$i]}

	#check if there are no more benchmarks
	if [ -z "\${trace}" ]; then
		break;
	fi

	export suffix=.champsimtrace.xz 
	if [ \"${BENCHSUITE}\" == \"google_srv\" ]; then
		export suffix=.champsimtrace.gz
	fi

  export bench=\${trace%\$suffix}


	export PTP_EXTRA_STATS_FILE=${DUMP_DIR}/\${bench}_${DESCR_TAG}_access_rate.csv
	export INSTR_PAGE_DIST_FILENAME=${DUMP_DIR}/\${bench}${INSTR_PAGE_DIST_FILENAME_SUFFIX}.pdst
	export DATA_PAGE_DIST_FILENAME=${DUMP_DIR}/\${bench}${DATA_PAGE_DIST_FILENAME_SUFFIX}.pdst
	export PAGE_ADDRESS_STATS_FILENAME_PREFIX=${DUMP_DIR}/\${bench}${DESCR_TAG}_page_access_stats

	if [[ -v REUSE_DIST_FILENAME_PREFIX ]]; then
		export REUSE_DIST_FILENAME_PREFIX=${DUMP_DIR}/\${bench}${DESCR_TAG}_${REUSE_DIST_FILENAME_PREFIX}
	fi

time ${DEBUG} ${CHAMPSIM_DIR}/bin/${BIN} \
																		--warmup_instructions ${SIM_WARMUP_INSTR} \
																		--simulation_instructions ${SIM_RUN_INSTR} \
																		${TRACE_DIR}/\${trace} > ${DUMP_DIR}/\${bench}${DESCR_TAG}_run.out 
done
" >	simr_${BENCHSUITE}_${ti}${DESCR_TAG}_job.run
		sbatch simr_${BENCHSUITE}_${ti}${DESCR_TAG}_job.run
		#chmod +x simr_${BENCHSUITE}_${ti}${DESCR_TAG}_job.run
		#./simr_${BENCHSUITE}_${ti}${DESCR_TAG}_job.run
		#chmod +x simt_${bench}_job.run
		#./simt_${bench}_job.run
		rm simr_${BENCHSUITE}_${ti}${DESCR_TAG}_job.run

	((ti=ti+${BATCH_SIZE}))
done
