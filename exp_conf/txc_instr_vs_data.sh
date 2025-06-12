### CONFIGURATION SPACE EXPLORATION ###

export INSTR_PAGE_SIZE_DIST=0
export DATA_PAGE_SIZE_DIST=0
# quick fix for parsing script	
export REUSE_DIST_FILENAME_PREFIX="recall_dist"

declare -A VAR_DECLARATIONS=( 
	['ITP_INSTR_POS']="0" 
	['ITP_DATA_POS']="2" 
	['ITP_MAX_LRU']="8" 
	['MIN_EVICTION_POSITION']="4" 
	['MIN_EVICTION_POSITION_L1D']="8" 
	['MIN_EVICTION_POSITION_L2C']="4" 
	['TLB_LOWER_STRESS_THRESHOLD']="1"
	['TLB_UPPER_STRESS_THRESHOLD']="4" 
	['INSTR_PAGE_SIZE_DIST']="${INSTR_PAGE_SIZE_DIST}"
	['DATA_PAGE_SIZE_DIST']="${DATA_PAGE_SIZE_DIST}"
	['ENABLE_TXVC']="true"
	['ENABLE_TXC']="false"
	['TXC_LATENCY']="0"
	['TXC_NUM_SET']="8 16 64 20480"
	['TXC_NUM_WAY']="8"
	['TXVC_REP_POLICY']="lfu"
	['TXC_INSTR_ONLY']="false"
	['TXC_DATA_ONLY']="true"
	['TXC_DOA_FILTERING']="true"	
	['TXC_DBPRED_CNTR_SZ']="2"
	['TXC_DBPRED_THRESHOLD']="0"
	['REUSE_DIST_FILENAME_PREFIX']="${REUSE_DIST_FILENAME_PREFIX}"
)

# TODO: need to manually set instr and data flags
# explore instr vs data
export _CONFIGURATION_TAGS="
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-d.{TXC_DATA_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.{TXVC_REP_POLICY}_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-d.{TXC_DATA_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.{TXVC_REP_POLICY}_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
"

export _CONFIGURATION_TAGS="
fdip_xcache-txvc.{ENABLE_TXVC}-i.true-d.false-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.{TXVC_REP_POLICY}_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.false-d.true-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.{TXVC_REP_POLICY}_llc-s.1537-w.16
"

export _CONFIGURATION_TAGS="
fdip_xcache-txvc.{ENABLE_TXVC}-i.true-d.false-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.{TXVC_REP_POLICY}_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.false-d.true-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.{TXVC_REP_POLICY}_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
"

#export CONFIGURATION_TAGS="test_xcache"

# GENERIC CONFIGURATION
export ROOT_DIR=`pwd`
export EXP_NAME=""
#export BENCHSUITES="selected_qualcomm_srv_ap smt_qualcomm_srv_ap"
export BENCHSUITES="selected_qualcomm_srv_ap"
#export BENCHSUITES="smt_qualcomm_srv_ap"
#export BENCHSUITES="test"
#export BENCHSUITES="google_srv"

# SIMULATION 
export SIM_WARMUP_INSTR=50000000
export SIM_RUN_INSTR=100000000
export SIM_TIME="04:00:00"
export DEBUG_RUN="False"
#export SIM_WARMUP_INSTR=50000
#export SIM_RUN_INSTR=100000
#export SIM_TIME="00:00:30"
#export DEBUG_RUN="True"
export BUILD_CHAMPSIM=true

# PARSING AND PLOTTING
export GENERATE_STATS="True"
export GENERATE_EXTRA_STATS="False"
export GENERATE_REUSE_DISTANCE_STATS="False"
export GENERATE_PLOTS="False"
export PLOT_TYPE="plot_ipc"
export PLOT_FILE_TYPE="pdf"


