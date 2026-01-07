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


# Set indexing limitations

![](../figures/l2c_set_access_dist_L2C-1536-TX-SETS-128_barret.pdf){width=50%}

* Simplified version of indexing -> (address >> OFSSET_BITS) & bitmask(ln2(NUM_SETS))
    * Bitmask can only handle powers of two 
* This is what actually hardware does

# Solutions in simulators
* Simulators often use different method to be able to compute indexes for arbitrary number of sets
    * Barrett / Granlund–Montgomery

* Tried the Barret method, but again noticed bad performance when comparing bitmask to barret version
    * Implementation of Barret resulted in very uneven distribution of addresses to sets. (see next slide)

* Implementation with just the mod operator provides better distribution, such as with the bitmask
    * Tried it and performance is good, which is the reason not to use it in a simualtor
    * The compiler actually does a similatr transformation to that of Barret

# Barret vs Real Mod operator
![Barret](../figures/l2c_set_access_dist_BASELINE-L2C-1536KB_barret.pdf){width=45%}
![Modulo](../figures/l2c_set_access_dist_BASELINE-L2C-1536KB.pdf){width=45%}


# Performance of TX setsL: L2C 1.5MB
![](../figures/tx-sets_vs_l2c_budget_analysis/tx-sets_vs_l2c_1536KB_budget_analysis_selected_qualcomm_srv_ap.pdf)

# Performance of TX setsL: L2C 2MB
![](../figures/tx-sets_vs_l2c_budget_analysis/tx-sets_vs_l2c_2048KB_budget_analysis_selected_qualcomm_srv_ap.pdf)

