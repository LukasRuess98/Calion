#!/usr/bin/env python3
"""
Erstelle Mock-Simulationen mit realistischen Metadaten für Dashboard-Demo.

Dies erstellt mehrere gespeicherte Workflows ohne Optimierung durchzuführen,
sodass das Multi-Workflow Dashboard getestet werden kann.
"""

import sys
import pickle
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import OrderedDict

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("🎨 Erstelle Mock-Simul ationen für Dashboard-Demo")
print("="*70)

# Import necessary classes
from energis.run.rolling_horizon import ScenarioResult, DesignData
from energis.utils.timeseries import TimeSeriesTable
from energis.mock_workflow import MockWorkflow
import numpy as np

def create_mock_workflow(
    name,
    description,
    scenario_name,
    system_name,
    n_steps=168,
    hp_capacities=None,
    storage_capacity=35.0,
    total_cost=234567.89
):
    """Create a mock workflow with specified parameters."""

    # Default heat pumps
    if hp_capacities is None:
        hp_capacities = {'HP_air': 2.5, 'HP_ground': 1.8}

    # Create timestamps
    start_date = datetime(2023, 1, 1)
    timestamps = [start_date + timedelta(hours=i) for i in range(n_steps)]

    # Create mock table data
    demand = 5.0 + 3.0 * np.sin(np.arange(n_steps) * 2 * np.pi / 24)
    strompreis = 50.0 + 20.0 * np.sin(np.arange(n_steps) * 2 * np.pi / 24 + np.pi)

    table = TimeSeriesTable(
        index=timestamps,
        columns=['waermebedarf_MWth', 'strompreis_eur_per_mwh'],
        data={
            'waermebedarf_MWth': list(demand),
            'strompreis_eur_per_mwh': list(strompreis)
        }
    )

    # Create mock series (optimization results)
    total_hp_capacity = sum(hp_capacities.values())
    series = OrderedDict()

    # Heat pumps
    for i, (hp_name, capacity) in enumerate(hp_capacities.items()):
        fraction = capacity / total_hp_capacity
        hp_output = demand * fraction
        cop = 3.5 + i * 0.5  # Different COPs
        series[f'{hp_name}_Q_th_MW'] = list(hp_output)
        series[f'{hp_name}_Pel_MW'] = list(hp_output / cop)

    # Storage
    tes_soc = storage_capacity * 0.5 + storage_capacity * 0.3 * np.sin(np.arange(n_steps) * 2 * np.pi / 168)
    series['TES_SOC_MWh'] = list(tes_soc)
    series['TES_charge_MW'] = list(np.maximum(0, -np.diff(tes_soc, prepend=storage_capacity * 0.5)) * 2)
    series['TES_discharge_MW'] = list(np.maximum(0, np.diff(tes_soc, prepend=storage_capacity * 0.5)) * 2)

    # Grid
    total_pel = np.zeros(n_steps)
    for hp in hp_capacities.keys():
        total_pel += np.array(series[f'{hp}_Pel_MW'])
    series['P_buy_MW'] = list(total_pel)

    # Create mock costs
    capex = total_cost * 0.4
    opex = total_cost * 0.6
    costs = {
        'objective.OBJ_value_EUR': total_cost,
        'objective.Grid_energy_cost_EUR': opex * 0.7,
        'objective.Electricity_base_cost_EUR': opex * 0.2,
        'objective.Electricity_energy_fee_EUR': opex * 0.1,
        'objective.Capex_cost_EUR': capex,
        'objective.Capex_heat_pumps_EUR': capex * 0.8,
        'objective.Capex_storage_EUR': capex * 0.2,
    }

    summary = {'objective': costs}

    # Create mock result
    mock_result = ScenarioResult(
        table=table,
        series=series,
        summary=summary,
        costs=costs,
        solver={'status': 'ok', 'termination_condition': 'optimal'}
    )

    # Create mock design
    mock_design = DesignData(
        heat_pumps={hp: {'capacity_mw': cap} for hp, cap in hp_capacities.items()},
        storage={'capacity_mwh': storage_capacity}
    )

    # Create mock workflow
    return MockWorkflow(mock_result, mock_design, solver_name='glpk', dt_h=1.0), {
        'name': name,
        'description': description,
        'scenario_name': scenario_name,
        'system_name': system_name,
        'hp_capacities': hp_capacities,
        'storage_capacity': storage_capacity,
        'n_steps': n_steps,
        'total_cost': total_cost,
    }


def save_mock_workflow(workflow, params):
    """Save mock workflow with metadata."""

    # Create saved_workflows directory
    save_dir = project_root / 'saved_workflows'
    save_dir.mkdir(exist_ok=True)

    # Create timestamped subdirectory
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    dir_name = f"{timestamp}_{params['name']}"

    workflow_dir = save_dir / dir_name
    workflow_dir.mkdir(exist_ok=True)

    # Build metadata
    metadata = {
        'saved_at': datetime.now().isoformat(),
        'name': params['name'],
        'description': params['description'],
        'scenario': {
            'name': params['scenario_name'],
            'system': params['system_name'],
            'site': 'default',
        },
        'config_files': [
            'configs/base.yaml',
            'configs/tech_catalog.yaml',
            'configs/sites/default.site.yaml',
            f'configs/systems/{params["system_name"]}.system.yaml',
            f'configs/scenarios/{params["scenario_name"]}.workflow.scenario.yaml',
        ],
        'workflow': {
            'steps': ['PF', 'RH'],
            'fix_design': False,
        },
        'results_available': {
            'pf': True,
            'rh': False,
            'mpc': False,
        },
        'solver': 'glpk',
        'technologies': {
            'heat_pumps': {
                name: {'capacity_mw': cap, 'type': 'heat_pump'}
                for name, cap in params['hp_capacities'].items()
            },
            'storage': {
                'capacity_mwh': params['storage_capacity'],
                'type': 'thermal_storage'
            }
        },
        'statistics': {
            'timesteps': params['n_steps'],
            'duration_hours': params['n_steps'] * 1.0,
        },
        'costs': {
            'total_eur': params['total_cost'],
            'capex_eur': params['total_cost'] * 0.4,
            'opex_eur': params['total_cost'] * 0.6,
            'fuel_eur': 0.0,
        }
    }

    # Save workflow pickle
    workflow_file = workflow_dir / 'workflow.pkl'
    with open(workflow_file, 'wb') as f:
        pickle.dump(workflow, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Save metadata JSON
    metadata_file = workflow_dir / 'metadata.json'
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return workflow_dir, metadata


# Create 3 different mock simulations
simulations = [
    {
        'name': 'baseline',
        'description': 'Baseline-Konfiguration mit Standard-Wärmepumpen',
        'scenario_name': 'pf_then_rh',
        'system_name': 'baseline',
        'n_steps': 168,  # 1 week
        'hp_capacities': {'HP_air': 2.5, 'HP_ground': 1.8},
        'storage_capacity': 35.0,
        'total_cost': 234567.89,
    },
    {
        'name': 'large_storage',
        'description': 'Erhöhte Speicherkapazität von 35 auf 50 MWh',
        'scenario_name': 'pf_then_rh',
        'system_name': 'baseline',
        'n_steps': 168,
        'hp_capacities': {'HP_air': 2.5, 'HP_ground': 1.8},
        'storage_capacity': 50.0,
        'total_cost': 228450.23,  # Lower cost with bigger storage
    },
    {
        'name': 'optimized',
        'description': 'Optimierte Konfiguration mit größeren Wärmepumpen und Speicher',
        'scenario_name': 'pf_then_rh',
        'system_name': 'baseline',
        'n_steps': 168,
        'hp_capacities': {'HP_air': 3.0, 'HP_ground': 2.2, 'HP_water': 1.5},
        'storage_capacity': 60.0,
        'total_cost': 221345.67,  # Even lower with optimization
    },
]

print(f"\n📦 Erstelle {len(simulations)} Mock-Simulationen...\n")

for i, sim_params in enumerate(simulations, 1):
    print(f"{i}. {sim_params['name']}")
    print(f"   {sim_params['description']}")

    # Create mock workflow
    workflow, params = create_mock_workflow(**sim_params)

    # Save it
    workflow_dir, metadata = save_mock_workflow(workflow, params)

    print(f"   ✅ Gespeichert: {workflow_dir.name}")
    print(f"   📊 Kosten: {metadata['costs']['total_eur']:,.0f} EUR")
    print()

print("="*70)
print("✅ ERFOLG! 3 Mock-Simulationen erstellt!")
print("="*70)

print("\n📊 Dashboard starten:")
print("   panel serve load_dashboard.py --show")

print("\n💡 Du kannst jetzt:")
print("   • Zwischen 3 Simulationen wechseln (Dropdown)")
print("   • Metadaten für jede Simulation sehen")
print("   • Dashboard-Features erkunden")
print("   • Kosten und Technologien vergleichen")

print("\n" + "="*70)
