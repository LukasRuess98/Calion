#!/usr/bin/env python3
"""
Save workflow results with metadata for later dashboard use.

Usage:
    # Save with auto-generated name
    python save_workflow_results.py

    # Save with custom name
    python save_workflow_results.py --name "baseline_scenario"

    # Save with description
    python save_workflow_results.py --name "test_v1" --description "First test run"

Output:
    saved_workflows/YYYY-MM-DD_HH-MM-SS_<name>/
        ├── workflow.pkl - Workflow object
        └── metadata.json - Scenario details
"""

import sys
import pickle
import json
import argparse
from pathlib import Path
from datetime import datetime

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("💾 EnerGIS - Workflow Ergebnisse speichern")
print("="*70)

from energis.run import rolling_horizon as rh

# ============================================================================
# CONFIGURATION - Passe diese Pfade für dein Szenario an!
# ============================================================================

CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/sites/default.site.yaml',
    'configs/systems/baseline.system.yaml',
    'configs/scenarios/pf_then_rh.workflow.scenario.yaml',
]

# ============================================================================

def extract_metadata(workflow, config_paths, custom_name=None, description=None):
    """Extract metadata from workflow for display in dashboard."""

    # Get scenario name from last config file
    scenario_file = Path(config_paths[-1]).stem
    scenario_name = scenario_file.replace('.workflow.scenario', '').replace('.scenario', '')

    # Get system name
    system_file = Path(config_paths[-2]).stem if len(config_paths) >= 2 else 'unknown'
    system_name = system_file.replace('.system', '')

    # Get site name
    site_file = Path(config_paths[-3]).stem if len(config_paths) >= 3 else 'unknown'
    site_name = site_file.replace('.site', '')

    # Extract workflow steps
    workflow_steps = list(workflow.plan.steps) if workflow.plan else []

    # Check which results are available
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None
    has_mpc = workflow.mpc_result is not None

    results_available = {
        'pf': has_pf,
        'rh': has_rh,
        'mpc': has_mpc,
    }

    # Get primary result for statistics
    result = workflow.pf_result or workflow.rh_result or workflow.mpc_result

    # Extract technologies from design
    technologies = {}
    if workflow.design:
        if workflow.design.heat_pumps:
            technologies['heat_pumps'] = {
                name: {
                    'capacity_mw': data.get('capacity_mw', 0),
                    'type': 'heat_pump'
                }
                for name, data in workflow.design.heat_pumps.items()
            }
        if workflow.design.storage:
            technologies['storage'] = {
                'capacity_mwh': workflow.design.storage.get('capacity_mwh', 0),
                'type': 'thermal_storage'
            }

    # Extract cost summary
    costs_summary = {}
    if result and result.costs:
        costs_summary = {
            'total_eur': result.costs.get('objective.OBJ_value_EUR', 0),
            'capex_eur': result.costs.get('objective.Capex_cost_EUR', 0),
            'opex_eur': result.costs.get('objective.Grid_energy_cost_EUR', 0),
            'fuel_eur': result.costs.get('objective.Fuel_cost_EUR', 0),
        }

    # Build metadata dict
    metadata = {
        'saved_at': datetime.now().isoformat(),
        'name': custom_name or scenario_name,
        'description': description or f'Optimierung: {scenario_name}',
        'scenario': {
            'name': scenario_name,
            'system': system_name,
            'site': site_name,
        },
        'config_files': config_paths,
        'workflow': {
            'steps': workflow_steps,
            'fix_design': workflow.plan.fix_design if workflow.plan else False,
        },
        'results_available': results_available,
        'solver': workflow.solver_name if hasattr(workflow, 'solver_name') else 'unknown',
        'technologies': technologies,
        'statistics': {
            'timesteps': len(result.table) if result else 0,
            'duration_hours': len(result.table) * (workflow.dt_h if hasattr(workflow, 'dt_h') else 1) if result else 0,
        },
        'costs': costs_summary,
    }

    return metadata


def save_workflow(workflow, config_paths, custom_name=None, description=None):
    """Save workflow with metadata to timestamped directory."""

    # Create saved_workflows directory
    save_dir = project_root / 'saved_workflows'
    save_dir.mkdir(exist_ok=True)

    # Create timestamped subdirectory
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    if custom_name:
        dir_name = f"{timestamp}_{custom_name}"
    else:
        # Use scenario name from config
        scenario_file = Path(config_paths[-1]).stem
        scenario_name = scenario_file.replace('.workflow.scenario', '').replace('.scenario', '')
        dir_name = f"{timestamp}_{scenario_name}"

    workflow_dir = save_dir / dir_name
    workflow_dir.mkdir(exist_ok=True)

    # Extract metadata
    metadata = extract_metadata(workflow, config_paths, custom_name, description)

    # Save workflow pickle
    workflow_file = workflow_dir / 'workflow.pkl'
    with open(workflow_file, 'wb') as f:
        pickle.dump(workflow, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Save metadata JSON
    metadata_file = workflow_dir / 'metadata.json'
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return workflow_dir, metadata


def main():
    """Main execution."""

    # Parse arguments
    parser = argparse.ArgumentParser(description='Save EnerGIS workflow results')
    parser.add_argument('--name', type=str, help='Custom name for this workflow')
    parser.add_argument('--description', type=str, help='Description of this workflow')
    args = parser.parse_args()

    print("\n1. Lade Konfiguration...")
    for i, path in enumerate(CONFIG_PATHS, 1):
        print(f"   {i}. {path}")
    print("   ✅ Konfiguration geladen")

    print("\n2. Führe Optimierung aus...")
    print("   ⏳ Dies kann einige Minuten dauern...")

    try:
        workflow = rh.run_workflow(CONFIG_PATHS)
        print("   ✅ Optimierung abgeschlossen!")

        # Check results
        has_pf = workflow.pf_result is not None
        has_rh = workflow.rh_result is not None
        has_mpc = workflow.mpc_result is not None

        print(f"\n3. Verfügbare Ergebnisse:")
        print(f"   PF:  {'✅' if has_pf else '❌'}")
        print(f"   RH:  {'✅' if has_rh else '❌'}")
        print(f"   MPC: {'✅' if has_mpc else '❌'}")

        if not (has_pf or has_rh or has_mpc):
            print("\n❌ Keine Ergebnisse zum Speichern")
            sys.exit(1)

        print(f"\n4. Speichere Ergebnisse...")
        workflow_dir, metadata = save_workflow(
            workflow,
            CONFIG_PATHS,
            args.name,
            args.description
        )

        # Calculate file sizes
        workflow_file = workflow_dir / 'workflow.pkl'
        metadata_file = workflow_dir / 'metadata.json'
        workflow_size_mb = workflow_file.stat().st_size / 1024 / 1024

        print(f"   ✅ Gespeichert in: {workflow_dir.name}")
        print(f"   📦 Workflow: {workflow_size_mb:.2f} MB")
        print(f"   📋 Metadata: {metadata_file.stat().st_size} bytes")

        # Show metadata summary
        print(f"\n📈 Zusammenfassung:")
        print(f"   Name: {metadata['name']}")
        print(f"   Beschreibung: {metadata['description']}")
        print(f"   Scenario: {metadata['scenario']['name']}")
        print(f"   System: {metadata['scenario']['system']}")
        print(f"   Site: {metadata['scenario']['site']}")
        print(f"   Workflow: {' → '.join(metadata['workflow']['steps'])}")
        print(f"   Solver: {metadata['solver']}")

        if metadata['technologies'].get('heat_pumps'):
            print(f"\n   🔥 Wärmepumpen:")
            for name, data in metadata['technologies']['heat_pumps'].items():
                print(f"      • {name}: {data['capacity_mw']:.2f} MW")

        if metadata['technologies'].get('storage'):
            storage = metadata['technologies']['storage']
            print(f"   🔋 Speicher: {storage['capacity_mwh']:.2f} MWh")

        print(f"\n   ⏱️  Zeitschritte: {metadata['statistics']['timesteps']:,}")
        print(f"   📅 Dauer: {metadata['statistics']['duration_hours']:.1f} Stunden")

        if metadata['costs'].get('total_eur'):
            print(f"\n   💰 Kosten:")
            print(f"      Gesamt: {metadata['costs']['total_eur']:,.0f} EUR")
            if metadata['costs'].get('capex_eur'):
                print(f"      CAPEX:  {metadata['costs']['capex_eur']:,.0f} EUR")
            if metadata['costs'].get('opex_eur'):
                print(f"      OPEX:   {metadata['costs']['opex_eur']:,.0f} EUR")

        print("\n" + "="*70)
        print("✅ ERFOLG! Ergebnisse gespeichert!")
        print("="*70)

        print("\n📊 Nächste Schritte:")
        print("   1. Starte Dashboard: panel serve load_dashboard.py --show")
        print("   2. Wähle Simulation aus Dropdown-Liste")
        print("   3. Analysiere Ergebnisse interaktiv")

        print(f"\n💾 Gespeichert in: {workflow_dir.relative_to(project_root)}")

    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
