"""Progressive test: build L3 from 1 branch up to 4 to find the infeasibility."""
import sys, os, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
logging.disable(logging.CRITICAL)

from calion.run.workflow import run_workflow
import tempfile, yaml, pathlib

BASE_SITE = {
    'input_xlsx': 'data/stadtbach_synthetic_2023_1week_zonal.csv',
    'columns': {
        'datetime': 'Datum', 'price': 'strompreis_EUR_MWh',
        'co2_grid': 'grid_co2_kg_MWh', 'wrg1_temp': 'T_WRG1_C', 'wrg2_temp': 'T_WRG2_C',
    },
}
BASE_ASSETS = {
    'boiler_main': {
        'type': 'thermal_generator', 'fuel': 'gas',
        'capacity_mw': 200.0, 'min_load': 0.1, 'thermal_efficiency': 0.90,
    }
}
BASE_GRID = {'max_import_mw': 200.0, 'max_export_mw': 200.0, 'gridcost_eur_mwh': 35.0}
BASE_FUELS = {'gas': {'price_eur_mwh': 45.0, 'ef_kg_per_mwh_fuel': 200.0}}
BASE_COSTS = {'co2_price_eur_per_t': 100.0, 'dump_cost_eur_per_mwh_th': 10.0}
BASE_RUN = {'dt_h': 1.0, 'solver': 'appsi_highs'}

BRANCH_DEFS = {
    'north': {
        'junction': 'j_north', 'connector': 'central_to_north',
        'connector_cfg': {'from': 'j_central', 'to': 'j_north', 'length_m': 850, 'diameter_mm': 350},
        'zones': list(range(1, 6)),
        'pipe_cfg': {
            1: {'length_m': 200, 'diameter_mm': 300}, 2: {'length_m': 210, 'diameter_mm': 250},
            3: {'length_m': 220, 'diameter_mm': 200}, 4: {'length_m': 230, 'diameter_mm': 200},
            5: {'length_m': 240, 'diameter_mm': 150},
        },
    },
    'south': {
        'junction': 'j_south', 'connector': 'central_to_south',
        'connector_cfg': {'from': 'j_central', 'to': 'j_south', 'length_m': 820, 'diameter_mm': 350},
        'zones': list(range(6, 12)),
        'pipe_cfg': {
            6: {'length_m': 190, 'diameter_mm': 300}, 7: {'length_m': 200, 'diameter_mm': 250},
            8: {'length_m': 210, 'diameter_mm': 200}, 9: {'length_m': 215, 'diameter_mm': 200},
            10: {'length_m': 220, 'diameter_mm': 150}, 11: {'length_m': 215, 'diameter_mm': 125},
        },
    },
    'east': {
        'junction': 'j_east', 'connector': 'central_to_east',
        'connector_cfg': {'from': 'j_central', 'to': 'j_east', 'length_m': 880, 'diameter_mm': 350},
        'zones': list(range(12, 18)),
        'pipe_cfg': {
            12: {'length_m': 185, 'diameter_mm': 300}, 13: {'length_m': 195, 'diameter_mm': 250},
            14: {'length_m': 200, 'diameter_mm': 200}, 15: {'length_m': 200, 'diameter_mm': 200},
            16: {'length_m': 205, 'diameter_mm': 150}, 17: {'length_m': 195, 'diameter_mm': 125},
        },
    },
    'west': {
        'junction': 'j_west', 'connector': 'central_to_west',
        'connector_cfg': {'from': 'j_central', 'to': 'j_west', 'length_m': 790, 'diameter_mm': 350},
        'zones': list(range(18, 24)),
        'pipe_cfg': {
            18: {'length_m': 195, 'diameter_mm': 300}, 19: {'length_m': 200, 'diameter_mm': 250},
            20: {'length_m': 210, 'diameter_mm': 200}, 21: {'length_m': 215, 'diameter_mm': 200},
            22: {'length_m': 215, 'diameter_mm': 150}, 23: {'length_m': 215, 'diameter_mm': 125},
        },
    },
}


def build_config(branch_names, zones_per_branch=None):
    """Build a scenario config with the given branches (subset of L3)."""
    nodes = {
        'plant_main': {'type': 'producer', 'assets': ['boiler_main']},
        'j_central': {'type': 'junction'},
    }
    pipes = {
        'plant_to_central': {'from': 'plant_main', 'to': 'j_central', 'length_m': 3200, 'diameter_mm': 500},
    }

    for bname in branch_names:
        b = BRANCH_DEFS[bname]
        junc = b['junction']
        nodes[junc] = {'type': 'junction'}
        pipes[b['connector']] = b['connector_cfg']

        z_list = b['zones']
        if zones_per_branch is not None:
            z_list = z_list[:zones_per_branch]

        for z in z_list:
            zname = f'zone_{z:02d}'
            nodes[zname] = {'type': 'consumer', 'demand': {'column': f'zone_{z:02d}_demand_MWth'}}
            pcfg = b['pipe_cfg'][z]
            pipes[f'{junc.replace("j_", "j_")}_to_z{z}'] = {
                'from': junc, 'to': zname, **pcfg
            }

    n_nodes = len(nodes)
    n_pipes = len(pipes)
    label = f'{"+".join(branch_names)} ({zones_per_branch or "all"} zones/branch)'

    cfg = {
        'site': BASE_SITE,
        'scenario': {'name': f'test_{"-".join(branch_names)}', 'run_mode': 'PF_ONLY'},
        'network': {
            'physics': {'heat_loss': False, 'pressure_drop': False, 'transport_delay': False},
            'supply_temp_c': 90.0, 'return_temp_c': 55.0, 'ground_temp_c': 10.0,
            'nodes': nodes, 'pipes': pipes,
        },
        'assets': BASE_ASSETS,
        'grid': BASE_GRID, 'fuels': BASE_FUELS, 'costs': BASE_COSTS, 'run': BASE_RUN,
    }
    return cfg, label, n_nodes, n_pipes


class _InlineListDumper(yaml.Dumper):
    """Dump lists as inline flow style so the calion simple_yaml parser accepts them."""
    pass
_InlineListDumper.add_representer(
    list,
    lambda dumper, data: dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
)


def run_test(cfg, label, n_nodes, n_pipes):
    tmp = pathlib.Path(tempfile.mktemp(suffix='.yaml', dir='configs/paper'))
    try:
        with open(tmp, 'w') as f:
            yaml.dump(cfg, f, Dumper=_InlineListDumper, default_flow_style=False, sort_keys=False)
        result = run_workflow([str(tmp)])
        pf = result.pf_result
        status = pf.solver.get('termination_condition', '?') if pf else 'NO_RESULT'
        print(f'  [{n_nodes} nodes, {n_pipes} pipes] {label}: {status}')
        return status
    except Exception as e:
        print(f'  [{n_nodes} nodes, {n_pipes} pipes] {label}: ERROR - {e}')
        return 'error'
    finally:
        tmp.unlink(missing_ok=True)


print('=== Progressive L3 Topology Test ===')
print()

# Test 1: Single branch with increasing zones
print('--- Single branch (north), increasing zones ---')
for nz in [1, 2, 3, 4, 5]:
    cfg, label, n, p = build_config(['north'], zones_per_branch=nz)
    run_test(cfg, f'north branch, {nz} zone(s)', n, p)

print()

# Test 2: Two branches
print('--- Two branches ---')
for branches in [['north', 'south'], ['north', 'east']]:
    cfg, label, n, p = build_config(branches)
    run_test(cfg, label, n, p)

print()

# Test 3: Three branches
print('--- Three branches ---')
cfg, label, n, p = build_config(['north', 'south', 'east'])
run_test(cfg, label, n, p)

print()

# Test 4: All four branches
print('--- Four branches (full L3) ---')
cfg, label, n, p = build_config(['north', 'south', 'east', 'west'])
run_test(cfg, label, n, p)

print()
print('Done.')
