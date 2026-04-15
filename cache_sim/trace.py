def render_trace_path(path_template, benchmark, num_sets):
    """Render one trace path from a CLI template."""
    try:
        return path_template.format(benchmark=benchmark, num_sets=num_sets)
    except KeyError as exc:
        raise ValueError(
            f"Invalid placeholder in trace template '{path_template}': {exc}. "
            "Supported placeholders: {benchmark}, {num_sets}."
        ) from exc


def parse_trace_flag(raw_value):
    value = str(raw_value).strip().lower()
    return value in (
        '1', 'true', 't', 'yes', 'y',
        'prefetch', 'pf',
        'instr', 'instruction', 'i',
    )


def load_trace_entries(path):
    """Load a trace as (pte, is_instr) tuples from address,is_instr CSV lines."""
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            cols = [c.strip() for c in line.split(',')]
            if len(cols) < 2:
                continue

            pte = cols[0]
            is_instr = parse_trace_flag(cols[1])
            entries.append((pte, is_instr))

    return entries


def trace_entries_to_ptes(trace_entries):
    return [pte for pte, _ in trace_entries]
