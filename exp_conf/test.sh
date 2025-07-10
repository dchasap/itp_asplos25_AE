### CONFIGURATION SPACE EXPLORATION ###

export INSTR_PAGE_SIZE_DIST=0
export DATA_PAGE_SIZE_DIST=0

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
)

export CONFIGURATION_TAGS="
fdip_baseline_llc-s.1537-w.16	
fdip_l2c-r.tdrrip_llc-s.1537-w.16	
fdip_l2c-r.ptp_llc-s.1537-w.16	
fdip_stlb-r.chirp_llc-s.1537-w.16
fdip_stlb-r.chirp_l2c-r.tdrrip_llc-s.1537-w.16
fdip_stlb-r.chirp_l2c-r.ptp_llc-s.1537-w.16
fdip_stlb-r.itp_llc-s.1537-w.16
fdip_stlb-r.itp_l2c-r.tdrrip_llc-s.1537-w.16
fdip_stlb-r.itp_l2c-r.ptp_llc-s.1537-w.16
fdip_stlb-r.itp_l2c-r.xptp_llc-s.1537-w.16
"

export CONFIGURATION_TAGS="
fdip_l2c-s.1-w.1_llc-s.1537-w.16
"

# GENERIC CONFIGURATION
export ROOT_DIR=`pwd`
export EXP_NAME=""
#export BENCHSUITES="selected_qualcomm_srv_ap smt_qualcomm_srv_ap"
export BENCHSUITES="selected_qualcomm_srv_ap"
#export BENCHSUITES="google_srv"

# SIMULATION 
export SIM_WARMUP_INSTR=50000000
export SIM_RUN_INSTR=100000000
export BUILD_CHAMPSIM=true

# PARSING AND PLOTTING
export GENERATE_STATS="True"
export GENERATE_EXTRA_STATS="False"
export GENERATE_PLOTS="False"
export PLOT_FILE_TYPE="pdf"

