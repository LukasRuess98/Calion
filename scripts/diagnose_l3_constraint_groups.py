"""Systematically deactivate constraint groups to find what causes LP infeasibility."""
import sys, os, logging, yaml, tempfile, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
logging.disable(logging.CRITICAL)

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers.highs import Highs

BRANCH_DEFS = {
    'north': {'junction': 'j_north', 'connector': 'central_to_north',
              'conn': {'from': 'j_central', 'to': 'j_north', 'length_m': 850, 'diameter_mm': 350},
              'zones': list(range(1, 6)),
              'pcfg': {1: {'length_m': 200, 'diameter_mm': 300}, 2: {'length_m': 210, 'diameter_mm': 250},
                       3: {'length_m': 220, 'diameter_mm': 200}, 4: {'length_m': 230, 'diameter_mm': 200},
                       5: {'length_m': 240, 'diameter_mm': 150}}},
    'south': {'junction': 'j_south', 'connector': 'central_to_south',
              'conn': {'from': 'j_central', 'to': 'j_south', 'length_m': 820, 'diameter_mm': 350},
              'zones': list(range(6, 12)),
              'pcfg': {6: {'length_m': 190, 'diameter_mm': 300}, 7: {'length_m': 200, 'diameter_mm': 250},
                       8: {'length_m': 210, 'diameter_mm': 200}, 9: {'length_m': 215, 'diameter_mm': 200},
                       10: {'length_m': 220, 'diameter_mm': 150}, 11: {'length_m': 215, 'diameter_mm': 125}}},
    'east': {'junction': 'j_east', 'connector': 'central_to_east',
             'conn': {'from': 'j_central', 'to': 'j_east', 'length_m': 880, 'diameter_mm': 350},
             'zones': list(range(12, 18)),
             'pcfg': {12: {'length_m': 185, 'diameter_mm': 300}, 13: {'length_m': 195, 'diameter_mm': 250},
                      14: {'length_m': 200, 'diameter_mm': 200}, 15: {'length_m': 200, 'diameter_mm': 200},
                      16: {'length_m': 205, 'diameter_mm': 150}, 17: {'length_m': 195, 'diameter_mm': 125}}},
    'west': {'junction': 'j_west', 'connector': 'central_to_west',
             'conn': {'from': 'j_central', 'to': 'j_west', 'length_m': 790, 'diameter_mm': 350},
             'zones': list(range(18, 24)),
             'pcfg': {18: {'length_m': 195, 'diameter_mm': 300}, 19: {'length_m': 200, 'diameter_mm': 250},
                      20: {'length_m': 210, 'diameter_mm': 200}, 21: {'length_m': 215, 'diameter_mm': 200},
                      22: {'length_m': 215, 'diameter_mm': 150}, 23: {'length_m': 215, 'diameter_mm': 125}}},
}


def build_yaml_config(zones_per_branch):
    nodes = {'plant_main': {'type': 'producer', 'assets': ['boiler_main']}, 'j_central': {'type': 'junction'}}
    pipes = {'plant_to_central': {'from': 'plant_main', 'to': 'j_central', 'length_m': 3200, 'diameter_mm': 500}}
    for b in BRANCH_DEFS.values():
        junc = b['junction']
        nodes[junc] = {'type': 'junction'}
        pipes[b['connector']] = b['conn']
        for z in b['zones'][:zones_per_branch]:
            nodes[f'zone_{z:02d}'] = {'type': 'consumer', 'demand': {'column': f'zone_{z:02d}_demand_MWth'}}
            pipes[f'{junc}_to_z{z}'] = {'from': junc, 'to': f'zone_{z:02d}', **b['pcfg'][z]}
    return {
        'site': {'input_xlsx': 'data/stadtbach_synthetic_2023_1week_zonal.csv',
                 'columns': {'datetime': 'Datum', 'price': 'strompreis_EUR_MWh', 'co2_grid': 'grid_co2_kg_MWh',
                             'wrg1_temp': 'T_WRG1_C', 'wrg2_temp': 'T_WRG2_C'}},
        'scenario': {'name': 'test_lp', 'run_mode': 'PF_ONLY'},
        'network': {'physics': {'heat_loss': False, 'pressure_drop': False, 'transport_delay': False},
                    'supply_temp_c': 90.0, 'return_temp_c': 55.0, 'ground_temp_c': 10.0,
                    'nodes': nodes, 'pipes': pipes},
        'assets': {'boiler_main': {'type': 'thermal_generator', 'fuel': 'gas', 'capacity_mw': 200.0,
                                    'min_load': 0.1, 'thermal_efficiency': 0.90}},
        'grid': {'max_import_mw': 200.0, 'max_export_mw': 200.0, 'gridcost_eur_mwh': 35.0},
        'fuels': {'gas': {'price_eur_mwh': 45.0, 'ef_kg_per_mwh_fuel': 200.0}},
        'costs': {'co2_price_eur_per_t': 100.0, 'dump_cost_eur_per_mwh_th': 10.0},
        'run': {'dt_h': 1.0, 'solver': 'appsi_highs'},
    }


class _D(yaml.Dumper): pass
_D.add_representer(list, lambda d, v: d.represent_sequence('tag:yaml.org,2002:seq', v, flow_style=True))


def build_model(cfg_dict):
    tmp = pathlib.Path(tempfile.mktemp(suffix='.yaml', dir='configs/paper'))
    try:
        with open(tmp, 'w') as f:
            yaml.dump(cfg_dict, f, Dumper=_D, default_flow_style=False, sort_keys=False)
        from calion.config.merge import load_and_merge
        from calion.io.loader import load_input_excel
        from calion.models.system_builder import build_model as _bm
        cfg = load_and_merge([str(tmp)])
        site_cfg = cfg.get('site', {})
        table = load_input_excel(site_cfg.get('input_xlsx', ''), site_cfg, dt_hours=1.0)
        return _bm(table, cfg), cfg
    finally:
        tmp.unlink(missing_ok=True)


def relax_binaries(model):
    binary_refs = []
    for v in model.component_objects(pyo.Var, active=True):
        for idx in v:
            if v[idx].domain == pyo.Binary:
                v[idx].domain = pyo.NonNegativeReals
                if v[idx].ub is None:
                    v[idx].setub(1.0)
                binary_refs.append((v, idx))
    return binary_refs


def solve_lp(model):
    opt = Highs()
    opt.config.load_solution = False
    result = opt.solve(model)
    return str(result.termination_condition)


def is_feasible(tc):
    return 'optimal' in tc.lower() or ('feasible' in tc.lower() and 'infeasible' not in tc.lower())


print('=== Constraint Group Isolation ===\n')
print('Building 5-zones/branch infeasible model...')
model, cfg = build_model(build_yaml_config(5))
relax_binaries(model)

# Catalog all constraint groups
groups = {}
for c in model.component_objects(pyo.Constraint, active=True):
    name = c.name
    # Classify by keyword
    key = None
    for kw in ['heat_loss', 'temp_drop', 'heat_delivered', 'velocity', 'pressure',
               'pwl', 'pump', 'demand', 'mass_balance', 'junction', 'network_loss',
               'temp_mixing', 'link_pipe', 'link_heat', 'link_demand', 'no_delay',
               'supply_ge_return', 'min']:
        if kw in name.lower():
            key = kw
            break
    if key is None:
        key = 'other'
    if key not in groups:
        groups[key] = []
    groups[key].append(c)

print(f'Constraint groups: {list(groups.keys())}')
total_cons = sum(sum(1 for _ in c) for cs in groups.values() for c in cs)
print(f'Total constraints (LP): {total_cons}\n')

# Baseline: confirm infeasible
tc = solve_lp(model)
print(f'Baseline (all active): {tc}')
if is_feasible(tc):
    print('Model is actually FEASIBLE - nothing to investigate!')
    sys.exit(0)

print()
print('Testing constraint groups (deactivate one at a time)...')
for gname, cons_list in groups.items():
    for c in cons_list:
        c.deactivate()
    tc = solve_lp(model)
    status = 'FEASIBLE *** THIS GROUP CAUSES INFEASIBILITY' if is_feasible(tc) else 'still infeasible'
    n = sum(1 for c in cons_list for _ in c)
    print(f'  Without {gname!r} ({n} constraints): {status}')
    for c in cons_list:
        c.activate()

print('\nDone.')
