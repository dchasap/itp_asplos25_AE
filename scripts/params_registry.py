"""
Parameter registry for ChampSim env/json parameters.
Keep registrations here. No external deps.

API:
 - register_parameter(env_name, conf_name=None, components=None, category='env', ptype='str', default=None, doc=None)
 - generate_default_env() -> dict
 - generate_confnames_map() -> dict
 - get_components() -> list
 - generate_param_names_for_component(component, category='env'|'json') -> list of option names (suffixes)
 - generate_common_cache_param_names() -> list used by cache components

Register each parameter once below.
"""

from typing import List, Dict, Optional

_registry = []


def register_parameter(env_name: str,
                       conf_name: Optional[str] = None,
                       components: Optional[List[str]] = None,
                       category: str = 'env',
                       ptype: str = 'str',
                       default: Optional[str] = None,
                       doc: Optional[str] = None):
    entry = {
        'env_name': env_name,
        'conf_name': conf_name,
        'components': components or [],
        'category': category,
        'ptype': ptype,
        'default': default,
        'doc': doc,
    }
    _registry.append(entry)


def generate_default_env() -> Dict[str, str]:
    return {e['env_name']: str(e['default']) for e in _registry if e['default'] is not None}


def generate_confnames_map() -> Dict[str, str]:
    return {e['conf_name']: e['env_name'] for e in _registry if e['conf_name']}


def get_components() -> List[str]:
    comps = set()
    for e in _registry:
        for c in e['components']:
            comps.add(c)
    # keep some stable ordering with common components first if present
    ordering = ['ooo_cpu', 'itlb', 'dtlb', 'stlb', 'l1i', 'l1d', 'l2c', 'llc', 'tx', 'txvc']
    ordered = [c for c in ordering if c in comps]
    ordered += sorted([c for c in comps if c not in ordering])
    return ordered


def generate_param_names_for_component(component: str, category: str = 'env') -> List[str]:
    names = set()
    for e in _registry:
        if e['category'] != category:
            continue
        if component in e['components'] and e['conf_name']:
            # conf_name is like 'txvc.sets' -> extract suffix after '.'
            if '.' in e['conf_name']:
                names.add(e['conf_name'].split('.', 1)[1])
    return sorted(names)


def generate_common_cache_param_names() -> List[str]:
    # Return union of env-parameters registered for cache-like components
    cache_like = {'itlb', 'dtlb', 'stlb', 'l1i', 'l1d', 'l2c', 'llc', 'tx', 'txvc'}
    names = set()
    for e in _registry:
        if e['category'] != 'env':
            continue
        if any(c in cache_like for c in e['components']) and e['conf_name']:
            names.add(e['conf_name'].split('.', 1)[1])
    return sorted(names)


# Export helper lists for convenience
def all_registered():
    return list(_registry)


# If run as script, print a short summary
if __name__ == '__main__':
    print('Registered', len(_registry), 'parameters')
