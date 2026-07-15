"""
Registrations for params_registry. Separated for easier management.
Call `register_all()` to populate the registry at runtime.
"""

import params_registry as r


def register_all():
    # ooo_cpu
    r.register_parameter('ENABLE_TXVC', 'ooo_cpu.enable_txvc', components=['ooo_cpu'], category='env', ptype='bool', default='false', doc='Enable TXVC')

    # txvc (cache component)
    r.register_parameter('TXVC_NUM_SET', 'txvc.sets', components=['txvc'], category='env', ptype='int', default='8')
    r.register_parameter('TXVC_NUM_WAY', 'txvc.ways', components=['txvc'], category='env', ptype='int', default='8')
    r.register_parameter('TXVC_SET_INDEXER', 'txvc.set_indexer', components=['txvc'], category='env', ptype='str', default='default')
    r.register_parameter('TXVC_REP_POLICY', 'txvc.replacement', components=['txvc'], category='env', ptype='str', default='lru')
    r.register_parameter('TXVC_REP_PTE_THRESHOLD', 'txvc.replacement_pte_threshold', components=['txvc'], category='env', ptype='int', default='0')
    r.register_parameter('TXVC_REP_EVICT_LEAF_NODES', 'txvc.replacement_evict_leaf_nodes', components=['txvc'], category='env', ptype='bool', default='true')
    r.register_parameter('TXVC_REP_ALLOWED_FREQ_DELTA', 'txvc.replacement_allowed_freq_delta', components=['txvc'], category='env', ptype='int', default='10')
    r.register_parameter('TXVC_REP_DECAY', 'txvc.replacement_decay', components=['txvc'], category='env', ptype='int', default='1')
    r.register_parameter('TXVC_REP_HALVE_PERIOD', 'txvc.halve_period', components=['txvc'], category='env', ptype='int', default='1000000')
    r.register_parameter('TXVC_REP_THRESHOLD', 'txvc.replacement_threshold', components=['txvc'], category='env', ptype='float', default='0.5')
    r.register_parameter('TXVC_REP_WINDOW_SIZE', 'txvc.replacement_window_size', components=['txvc'], category='env', ptype='int', default='1000')
    r.register_parameter('TXVC_REP_PC_RESET_INTERVAL', 'txvc.replacement_pc_reset_interval', components=['txvc'], category='env', ptype='int', default='1000000')
    r.register_parameter('TXVC_PACIPV_DEMAND_VECTOR_FILE', 'txvc.pacipv_demand_vector_file', components=['txvc'], category='env', ptype='str', default='srrip_vectors.ipv')
    r.register_parameter('TXVC_PACIPV_DEMAND_VECTOR_IDX', 'txvc.pacipv_demand_vector_idx', components=['txvc'], category='env', ptype='int', default='0')
    r.register_parameter('TXVC_LFU_CNTR_BITS', 'txvc.lfu_cntr_bits', components=['txvc'], category='env', ptype='int', default='3')
    r.register_parameter('TXVC_INSTR_ONLY', 'txvc.instr_only', components=['txvc'], category='env', ptype='bool', default='false')
    r.register_parameter('TXVC_DATA_ONLY', 'txvc.data_only', components=['txvc'], category='env', ptype='bool', default='false')
    r.register_parameter('TXVC_CACHE_FILTERING', 'txvc.cache_filtering', components=['txvc'], category='env', ptype='bool', default='false')
    r.register_parameter('TXVC_CACHE_FILTER', 'txvc.cache_filter', components=['txvc'], category='env', ptype='str', default='')
    r.register_parameter('TXVC_CACHE_LEVEL', 'txvc.level', components=['txvc'], category='env', ptype='int', default='1')
    r.register_parameter('TXVC_PF_POLICY', 'txvc.pf_policy', components=['txvc'], category='env', ptype='str', default='stride')
    r.register_parameter('TXVC_PF_STRIDE_TABLE_SIZE', 'txvc.pf_stride_table_size', components=['txvc'], category='env', ptype='int', default='64')
    r.register_parameter('TXVC_PF_STRIDE_CONF_THRESHOLD', 'txvc.pf_stride_conf_threshold', components=['txvc'], category='env', ptype='int', default='2')
    r.register_parameter('TXVC_PF_MSHR_GATE_PCT', 'txvc.pf_mshr_gate_pct', components=['txvc'], category='env', ptype='int', default='50')
    r.register_parameter('TXVC_PF_SBLG_TABLE_SIZE', 'txvc.pf_sblg_table_size', components=['txvc'], category='env', ptype='int', default='128')
    r.register_parameter('TXVC_PF_SBLG_CONF_THRESHOLD', 'txvc.pf_sblg_conf_threshold', components=['txvc'], category='env', ptype='int', default='2')
    r.register_parameter('TXVC_PF_SBLG_ACC_WINDOW', 'txvc.pf_sblg_acc_window', components=['txvc'], category='env', ptype='int', default='32')
    r.register_parameter('TXVC_PF_SBLG_ACC_THRESHOLD', 'txvc.pf_sblg_acc_threshold', components=['txvc'], category='env', ptype='int', default='20')
    r.register_parameter('TXVC_PF_SBLG_DEGREE', 'txvc.pf_sblg_degree', components=['txvc'], category='env', ptype='int', default='1')
    r.register_parameter('TXVC_PF_CHILD_TABLE_SIZE', 'txvc.pf_child_table_size', components=['txvc'], category='env', ptype='int', default='256')
    r.register_parameter('TXVC_PF_CHILD_PENDING_SIZE', 'txvc.pf_child_pending_size', components=['txvc'], category='env', ptype='int', default='64')
    r.register_parameter('TXVC_PF_CHILD_CONF_THRESHOLD', 'txvc.pf_child_conf_threshold', components=['txvc'], category='env', ptype='int', default='2')
    r.register_parameter('TXVC_PF_CHILD_TRAIN_ON_HIT', 'txvc.pf_child_train_on_hit', components=['txvc'], category='env', ptype='int', default='1')
    r.register_parameter('TXVC_PREFETCH_FILL_TARGET', 'txvc.prefetch_fill_target', components=['txvc'], category='env', ptype='str', default='txvc')
    r.register_parameter('TXVC_MISS_FILL_TARGET', 'txvc.miss_fill_target', components=['txvc'], category='env', ptype='str', default='l2c')
    r.register_parameter('TXVC_DBPRED_CNTR_SZ', 'txvc.dbpred_cntr_size', components=['txvc'], category='env', ptype='int', default='3')
    r.register_parameter('TXVC_DBPRED_THRESHOLD', 'txvc.dbpred_threshold', components=['txvc'], category='env', ptype='int', default='0')
    r.register_parameter('TXVC_DBPRED_USE_BIAS', 'txvc.dbpred_use_bias', components=['txvc'], category='env', ptype='bool', default='false')
    r.register_parameter('TXVC_FILTER_CLEANUP_INTERVAL', 'txvc.filter_cleanup_interval', components=['txvc'], category='env', ptype='int', default='9999999999999999')
    r.register_parameter('TXVC_FILTER_TOP_N_FACTOR', 'txvc.filter_top_n_factor', components=['txvc'], category='env', ptype='float', default='1.0')
    r.register_parameter('TXVC_MEMORY_TRACE_PATH', 'txvc.mem_trace_path', components=['txvc'], category='env', ptype='str', default='./data') 

    # cache filter / reuse
    r.register_parameter('CACHE_FILTER_FREQ_THRESHOLD', 'txvc.filter_frequency_threshold', components=['txvc'], category='env', ptype='int', default='2')
    r.register_parameter('CACHE_FILTER_MEMORY_TRACE_PATH', 'txvc.filter_mem_trace_path', components=['txvc'], category='env', ptype='str', default='./data')
    r.register_parameter('CACHE_FILTER_BLOOM_FILTER_SIZE', 'txvc.filter_size', components=['txvc'], category='env', ptype='int', default='1024')
    r.register_parameter('CACHE_FILTER_NUM_HASHES', 'txvc.filter_num_hashes', components=['txvc'], category='env', ptype='int', default='5')

    # reuse / output prefixes (assign to cache)
    r.register_parameter('REUSE_DIST_FILENAME_PREFIX', None, components=['l2c','llc','txvc'], category='env', ptype='str', default='reuse_dist')
    r.register_parameter('ACCESS_FREQ_STATS_FILENAME_PREFIX', None, components=['l2c','llc','txvc'], category='env', ptype='str', default='page_access_stats')
    r.register_parameter('SET_ACCESS_FILENAME_PREFIX', None, components=['l2c','llc','txvc'], category='env', ptype='str', default='set_access_stats')

    # PTE / ITP / general CPU params
    r.register_parameter('ITP_INSTR_POS', None, components=['ooo_cpu'], category='env', ptype='int', default='0')
    r.register_parameter('ITP_DATA_POS', None, components=['ooo_cpu'], category='env', ptype='int', default='2')
    r.register_parameter('ITP_MAX_LRU', None, components=['ooo_cpu'], category='env', ptype='int', default='8')
    r.register_parameter('MIN_EVICTION_POSITION', None, components=['l2c','llc'], category='env', ptype='int', default='4')
    r.register_parameter('MIN_EVICTION_POSITION_L1D', None, components=['l1d'], category='env', ptype='int', default='8')
    r.register_parameter('MIN_EVICTION_POSITION_L2C', None, components=['l2c'], category='env', ptype='int', default='4')
    r.register_parameter('TLB_LOWER_STRESS_THRESHOLD', None, components=['ooo_cpu'], category='env', ptype='int', default='1')
    r.register_parameter('TLB_UPPER_STRESS_THRESHOLD', None, components=['ooo_cpu'], category='env', ptype='int', default='4')
    r.register_parameter('INSTR_PAGE_SIZE_DIST', None, components=['ooo_cpu'], category='env', ptype='int', default='0')
    r.register_parameter('DATA_PAGE_SIZE_DIST', None, components=['ooo_cpu'], category='env', ptype='int', default='0')

    # Prefetch Buffer (compile flag: -DPREFETCH_BUFFER)
    # ENABLE_PF_BUFFER: per-cache boolean flag to enable prefetch buffer for that cache.
    # Set to 1 (or true) to enable, 0 (or false/None) to disable.
    # PF_BUFFER_MODE: "PREFETCH" (default, prefetch fills go to buffer) or "MISS" (demand misses go to buffer)
    for comp in ['l1d', 'l2c', 'llc']:
        r.register_parameter(f'{comp.upper()}_ENABLE_PF_BUFFER', f'{comp}.enable_pf_buffer', components=[comp], category='env', ptype='int', default='0')
        r.register_parameter(f'{comp.upper()}_PF_BUFFER_MODE', f'{comp}.pf_buffer_mode', components=[comp], category='env', ptype='str', default='PREFETCH')

    # Standalone page-table prefetchers attached as normal cache prefetchers.
    # Register per cache-like component so config keys like l2c.pf_child_table_size
    # map cleanly through the common-cache parameter path.
    for comp in ['l1d', 'l2c', 'llc']:
        r.register_parameter('PF_MSHR_GATE_PCT', f'{comp}.pf_mshr_gate_pct', components=[comp], category='env', ptype='int', default='50')
        r.register_parameter('PF_SBLG_TABLE_SIZE', f'{comp}.pf_sblg_table_size', components=[comp], category='env', ptype='int', default='128')
        r.register_parameter('PF_SBLG_CONF_THRESHOLD', f'{comp}.pf_sblg_conf_threshold', components=[comp], category='env', ptype='int', default='2')
        r.register_parameter('PF_SBLG_ACC_WINDOW', f'{comp}.pf_sblg_acc_window', components=[comp], category='env', ptype='int', default='32')
        r.register_parameter('PF_SBLG_ACC_THRESHOLD', f'{comp}.pf_sblg_acc_threshold', components=[comp], category='env', ptype='int', default='20')
        r.register_parameter('PF_SBLG_DEGREE', f'{comp}.pf_sblg_degree', components=[comp], category='env', ptype='int', default='1')
        r.register_parameter('PF_CHILD_TABLE_SIZE', f'{comp}.pf_child_table_size', components=[comp], category='env', ptype='int', default='256')
        r.register_parameter('PF_CHILD_PENDING_SIZE', f'{comp}.pf_child_pending_size', components=[comp], category='env', ptype='int', default='64')
        r.register_parameter('PF_CHILD_CONF_THRESHOLD', f'{comp}.pf_child_conf_threshold', components=[comp], category='env', ptype='int', default='2')
        r.register_parameter('PF_CHILD_TRAIN_ON_HIT', f'{comp}.pf_child_train_on_hit', components=[comp], category='env', ptype='int', default='1')
        r.register_parameter('PF_CHILD_ISSUE_ON_HIT', f'{comp}.pf_child_issue_on_hit', components=[comp], category='env', ptype='int', default='0')
        # Per-cache control to enable passing the full unmasked PTE address to prefetchers
        r.register_parameter(f'{comp.upper()}_PF_PREFETCH_FULL_ADDR', f'{comp}.pf_prefetch_full_addr', components=[comp], category='env', ptype='int', default='0')
        r.register_parameter('PF_BUFFER_FILL_CACHE_ON_HIT', f'{comp}.pf_buffer_fill_cache_on_hit', components=[comp], category='env', ptype='int', default='1')

    # other tx/tvc defaults
    r.register_parameter('TXVC_LATENCY', None, components=['txvc'], category='env', ptype='int', default='0')
    r.register_parameter('TXVC_REP_DECAY', None, components=['txvc'], category='env', ptype='int', default='1')
