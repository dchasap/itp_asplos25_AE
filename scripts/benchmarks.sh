
source ./env.sh

source ${ROOT_DIR}/scripts/spec_cpu_workloads.sh
source ${ROOT_DIR}/scripts/qualcomm_srv_workloads.sh
source ${ROOT_DIR}/scripts/google_srv_workloads.sh

if [ "${BENCHSUITE}" == "qualcomm_srv_ap"  ]; then
			TRACES="${QUALCOMM_SRV_AP}"
			TRACES_PATH="${QUALCOMM_SRV_AP_DIR}"
elif [ "${BENCHSUITE}" == "selected_qualcomm_srv_ap"  ]; then
			TRACES="${SELECTED_QUALCOMM_SRV_AP}"
			TRACES_PATH="${QUALCOMM_SRV_AP_DIR}"
elif [ "${BENCHSUITE}" == "smt_qualcomm_srv_ap"  ]; then
			TRACES="${SMT_QUALCOMM_SRV_AP}"
			TRACES_PATH="${QUALCOMM_SRV_AP_DIR}"
elif [ "${BENCHSUITE}" == "spec" ]; then
			TRACES="${SPEC_CPU_2006} ${SPEC_CPU_2017}"
			TRACES_PATH="${SPEC_CPU_DIR}"
elif [ "${BENCHSUITE}" == "google_srv" ]; then
			TRACES="${GOOGLE_SRV_WORKLOADS}"
			TRACES_PATH="${GOOGLE_SRV_WORKLOADS_DIR}"
elif [ "${BENCHSUITE}" == "test" ]; then
			TRACES=srv12_ap.champsimtrace.xz
			TRACES_PATH="${QUALCOMM_SRV_AP_DIR}"
else
			echo "${BENCHSUITE} is not a valid bechmark suite!"	
fi


SIMPOINTS=''
for trace in $TRACES; do	
	export suffix=.champsimtrace.xz 
	if [ "${BENCHSUITE}" == "google_srv" ]; then
		export suffix=.champsimtrace.gz
	fi
	export bench=${trace%$suffix}
	SIMPOINTS="$SIMPOINTS $bench"
done


BENCHMARKS=''
for simpoint in $SIMPOINTS; do
	export suffix=-*
	export bench=${simpoint%$suffix}
	BENCHMARKS="${BENCHMARKS} ${bench}"
done
BENCHMARKS=$(echo "${BENCHMARKS}" | xargs -n1 | sort -u | xargs)

