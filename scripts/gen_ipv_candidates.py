#!/usr/bin/env python3
"""Generate valid single-IPV candidates for PACIPV.

IPV structure: [h0, h1, h2, h3, ins]
  h_i : new RRPV after a hit when current RRPV is i  (i in 0..MAXRRPV)
  ins : RRPV assigned on insertion

Filters applied:
  1. No demotion on hit: h_i <= i for all i in 0..MAXRRPV.
  2. Reachability: the IPV must be able to visit every recency position
     {0..MAXRRPV} through insertion, hit transitions, and SRRIP-style aging.

Output format:
  INDEX: [h0,h1,h2,h3,ins]

Usage:
  python gen_ipv_candidates.py [output_file]
"""
import sys

MAXRRPV = 3


def all_no_demote_ipvs():
    ipvs = []
    for h0 in range(MAXRRPV + 1):
        if h0 > 0:
            continue
        for h1 in range(MAXRRPV + 1):
            if h1 > 1:
                continue
            for h2 in range(MAXRRPV + 1):
                if h2 > 2:
                    continue
                for h3 in range(MAXRRPV + 1):
                    for ins in range(MAXRRPV + 1):
                        ipvs.append((h0, h1, h2, h3, ins))
    return ipvs


def reachable_states(ipv):
    reachable = {ipv[4]}
    changed = True
    while changed:
        changed = False
        new_states = set()
        for state in reachable:
            if state < MAXRRPV:
                new_states.add(state + 1)
            new_states.add(ipv[state])
        for state in new_states:
            if state not in reachable:
                reachable.add(state)
                changed = True
    return reachable


def valid_ipvs():
    all_positions = set(range(MAXRRPV + 1))
    return [ipv for ipv in all_no_demote_ipvs() if reachable_states(ipv) == all_positions]


def format_ipv(ipv):
    return '[' + ','.join(str(x) for x in ipv) + ']'


def main():
    ipvs = valid_ipvs()

    out = sys.stdout
    if len(sys.argv) > 1:
        out = open(sys.argv[1], 'w')

    print(f"# {len(ipvs)} valid IPV candidates", file=out)
    for idx, ipv in enumerate(ipvs):
        print(f"{idx}: {format_ipv(ipv)}", file=out)

    if out is not sys.stdout:
        out.close()


if __name__ == '__main__':
    main()