---
title: 
    - EPIC Meeting
subtitle: 
    - ChampSim, Set indexing Bug
author: 
    - Alexander V. Jamet
    - Dimitrios Chasapis
    - Georgios Vavouliotis
    - Marc Casas
institute: 
    - Barcelona Supercomputing Center (BSC)
theme: 
    - Singapore
navigation: 
    - horizontal
lang: 
    - en-GB
---

# Content

\tableofcontents


# TXVC-128KB vs L2C 1535KB 

![](../figures/txvc_vs_l2c_budget_analysis/txvc_128KB_vs_l2c_1536KB_budget_analysis2_selected_qualcomm_srv_ap.pdf){width=100%}

# TXVC-128KB vs L2C 2048KB 

![](../figures/txvc_vs_l2c_budget_analysis/txvc_128KB_vs_l2c_2048KB_budget_analysis2_selected_qualcomm_srv_ap.pdf){width=100%}

# Alternative implementation using SETS
* Steal some sets of the cache to use exclusively for PTEs
* ...

# TX-SET vs L2C 1536KB
![](../figures/tx-sets_vs_l2c_budget_analysis/tx-sets_vs_l2c_1536KB_budget_analysis_selected_qualcomm_srv_ap.pdf){width=100%}

# TX-SET vs L2C 2048KB
![](../figures/tx-sets_vs_l2c_budget_analysis/tx-sets_vs_l2c_2048KB_budget_analysis_selected_qualcomm_srv_ap.pdf){width=100%}

# TX-SET vs L2C 1536KB, closer look -> MPKI
![](../figures/tx-sets_vs_l2c_budget_analysis/tx-sets_vs_l2c_1536KB_budget_analysis_mpki_selected_qualcomm_srv_ap.pdf){width=100%}

# TX-SET vs L2C 2048KB, closer look -> MPKI
![](../figures/tx-sets_vs_l2c_budget_analysis/tx-sets_vs_l2c_2048KB_budget_analysis_mpki_selected_qualcomm_srv_ap.pdf){width=100%}

# TX-SET vs L2C 1536KB, closer look -> set utilization
![](../figures/l2c_set_access_dist_BASELINE-L2C-1536KB.pdf){width=100%}

# TX-SET vs L2C 1536KB, closer look -> set utilization
![](../figures/l2c_set_access_dist_L2C-1536-TX-SETS-128.pdf){width=100%}

# TX-SET vs L2C 2048KB, closer look -> set utilization
![](../figures/l2c_set_access_dist_BASELINE-L2C-2048KB.pdf){width=100%}

# TX-SET vs L2C 2048KB, closer look -> set utilization
![](../figures/l2c_set_access_dist_L2C-2048-TX-SETS-128.pdf){width=100%}