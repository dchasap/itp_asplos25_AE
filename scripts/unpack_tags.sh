#!/bin/bash

function unpack_tags() {
  # This function generates the configuration tags for the experiment
  # It replaces the variable declarations with their values in the configuration string
  # and returns the final configuration tag or tags.

  # Arguments:
  # $1: The configuration string/s
  # $2: The envirmental variables table holding the variable declarations
  # Returns: a string with the configuration tag, replacing variables with their values

  local conf_file=$1
  local conf=$2

  source ${conf_file}
  #shift
  #declare -A VAR_DECLARATIONS=("${@}")
  local export_conf=""

  local base_conf=$(echo $conf | sed "s/:{.*}//g")
  #echo "base_conf: ${base_conf}"

  local smt="false"
  if [[ ${benchsuite} == smt_* ]]; then
		smt="true"
		base_conf=${base_conf}_smt
  fi

  local stop=0
  while [ ${stop} -lt ${#VAR_DECLARATIONS[@]} ]; do

	  local curr_conf=${conf}
	  stop=0	
	  local exploring="false"
	  for conf_key in ${!VAR_DECLARATIONS[@]}; do
      
	    declare -a CONF_VALUES=(${VAR_DECLARATIONS[$conf_key]})
	    conf_value=${CONF_VALUES[0]}

	    if [[ ${#CONF_VALUES[@]} -gt 1 ]] && [ "${exploring}" == "false" ]; then
		    VAR_DECLARATIONS[$conf_key]=${CONF_VALUES[@]:1}
		    exploring="true"
	    else
		    stop=$(( $stop + 1  ))
	    fi
	
      #echo size:${#CONF_VALUES[@]}
	    #echo keys:${CONF_VALUES[@]}
	    #echo keys\':${VAR_DECLARATIONS[$conf_key]}
	    #echo key:$conf_value

	    #echo "export ${conf_key}=${conf_value}"
	    export ${conf_key}=${conf_value}

	    curr_conf=$(echo ${curr_conf} | sed "s/{$conf_key}/$conf_value/g")
    done
    
    unpacked_conf="${unpacked_conf} ${curr_conf}"
  
  done

  echo ${unpacked_conf}

}

