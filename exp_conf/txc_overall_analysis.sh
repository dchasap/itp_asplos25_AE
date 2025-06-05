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
	['TXC_NUM_SET']="20480"
	['TXC_NUM_WAY']="8"
	['TXVC_REP_POLICY']="lfu"
	['TXC_INSTR_ONLY']="false"
	['TXC_DATA_ONLY']="false"
	['TXC_DOA_FILTERING']="false"	
	['TXC_DBPRED_CNTR_SZ']="2"
	['TXC_DBPRED_THRESHOLD']="0"
	['REUSE_DIST_FILENAME_PREFIX']="${REUSE_DIST_FILENAME_PREFIX}"
)
# 8 16
#	['TXC_NUM_SET']="20480"

# overall analysis
export CONFIGURATION_TAGS="
fdip_stlb-r.itp_llc-s.1537-w.16
fdip_l2c-r.xptp_llc-s.1537-w.16
fdip_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc2.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.false-l.{TXC_LATENCY}-s.20480-w.{TXC_NUM_WAY}-r.lfu_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-doa.false-cntr_sz.{TXC_DBPRED_CNTR_SZ}-thrhld.{TXC_DBPRED_THRESHOLD}-s.20480-w.{TXC_NUM_WAY}_stlb-r.itp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-doa.false-cntr_sz.{TXC_DBPRED_CNTR_SZ}-thrhld.{TXC_DBPRED_THRESHOLD}-s.20480-w.{TXC_NUM_WAY}_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-doa.false-cntr_sz.{TXC_DBPRED_CNTR_SZ}-thrhld.{TXC_DBPRED_THRESHOLD}-s.20480-w.{TXC_NUM_WAY}_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc2.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.true-l.{TXC_LATENCY}-s.20480-w.{TXC_NUM_WAY}-r.lfu_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-doa.true-cntr_sz.{TXC_DBPRED_CNTR_SZ}-thrhld.{TXC_DBPRED_THRESHOLD}-s.20480-w.{TXC_NUM_WAY}_stlb-r.itp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-doa.true-cntr_sz.{TXC_DBPRED_CNTR_SZ}-thrhld.{TXC_DBPRED_THRESHOLD}-s.20480-w.{TXC_NUM_WAY}_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-doa.true-cntr_sz.{TXC_DBPRED_CNTR_SZ}-thrhld.{TXC_DBPRED_THRESHOLD}-s.20480-w.{TXC_NUM_WAY}_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.8-w.{TXC_NUM_WAY}-r.lfu_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.8-w.{TXC_NUM_WAY}-r.lfu_stlb-r.itp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.8-w.{TXC_NUM_WAY}-r.lfu_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.8-w.{TXC_NUM_WAY}-r.lfu_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.16-w.{TXC_NUM_WAY}-r.lfu_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.16-w.{TXC_NUM_WAY}-r.lfu_stlb-r.itp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.16-w.{TXC_NUM_WAY}-r.lfu_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.16-w.{TXC_NUM_WAY}-r.lfu_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.lfu_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.lfu_stlb-r.itp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.lfu_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-txc.{ENABLE_TXC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-l.{TXC_LATENCY}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}-r.lfu_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
"

export CONFIGURATION_TAGS="
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-cntr_sz.{TXC_DBPRED_CNTR_SZ}-thrhld.{TXC_DBPRED_THRESHOLD}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}_stlb-r.itp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-cntr_sz.{TXC_DBPRED_CNTR_SZ}-thrhld.{TXC_DBPRED_THRESHOLD}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}_l2c-r.xptp_llc-s.1537-w.16
fdip_xcache-txvc.{ENABLE_TXVC}-i.{TXC_INSTR_ONLY}-doa.{TXC_DOA_FILTERING}-cntr_sz.{TXC_DBPRED_CNTR_SZ}-thrhld.{TXC_DBPRED_THRESHOLD}-s.{TXC_NUM_SET}-w.{TXC_NUM_WAY}_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
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


