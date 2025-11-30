#!/usr/bin/env python3
"""
Erstellt fehlende metadata.json für alte Workflow-Simulationen.

Verwendung:
    python generate_missing_metadata.py

Oder für spezifischen Ordner:
    python generate_missing_metadata.py saved_workflows/mein_alter_ordner
"""

import sys
import json
import pickle
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import MockWorkflow for pickle loading
from energis.mock_workflow import MockWorkflow

def extract_metadata_from_workflow(workflow, workflow_dir):
    """Extract metadata from workflow object."""

    # Get directory name parts
    dir_name = workflow_dir.name
    parts = dir_name.split('_', 2)
    if len(parts) >= 3:
        saved_at = f"{parts[0]}T{parts[1].replace('-', ':')}:00"
        name = parts[2] if len(parts) > 2 else "unknown"
    else:
        saved_at = datetime.now().isoformat()
        name = dir_name

    # Try to extract from workflow
    scenario_name = "unknown"
    workflow_steps = []

    if hasattr(workflow, 'plan') and workflow.plan:
        workflow_steps = list(workflow.plan.steps)

    # Check results
    has_pf = hasattr(workflow, 'pf_result') and workflow.pf_result is not None
    has_rh = hasattr(workflow, 'rh_result') and workflow.rh_result is not None
    has_mpc = hasattr(workflow, 'mpc_result') and workflow.mpc_result is not None

    # Get result for stats
    result = None
    if has_pf:
        result = workflow.pf_result
    elif has_rh:
        result = workflow.rh_result
    elif has_mpc:
        result = workflow.mpc_result

    # Extract technologies
    technologies = {}
    if hasattr(workflow, 'design') and workflow.design:
        if hasattr(workflow.design, 'heat_pumps') and workflow.design.heat_pumps:
            technologies['heat_pumps'] = {
                hp_name: {
                    'capacity_mw': data.get('capacity_mw', 0),
                    'type': 'heat_pump'
                }
                for hp_name, data in workflow.design.heat_pumps.items()
            }
        if hasattr(workflow.design, 'storage') and workflow.design.storage:
            technologies['storage'] = {
                'capacity_mwh': workflow.design.storage.get('capacity_mwh', 0),
                'type': 'thermal_storage'
            }

    # Extract costs
    costs = {}
    if result and hasattr(result, 'costs') and result.costs:
        costs = {
            'total_eur': result.costs.get('objective.OBJ_value_EUR', 0),
            'capex_eur': result.costs.get('objective.Capex_cost_EUR', 0),
            'opex_eur': result.costs.get('objective.Grid_energy_cost_EUR', 0),
            'fuel_eur': result.costs.get('objective.Fuel_cost_EUR', 0),
        }

    # Build metadata
    metadata = {
        'saved_at': saved_at,
        'name': name,
        'description': f'Automatisch generierte Metadaten für {name}',
        'scenario': {
            'name': scenario_name,
            'system': 'unknown',
            'site': 'unknown',
        },
        'config_files': [],
        'workflow': {
            'steps': workflow_steps,
            'fix_design': False,
        },
        'results_available': {
            'pf': has_pf,
            'rh': has_rh,
            'mpc': has_mpc,
        },
        'solver': getattr(workflow, 'solver_name', 'unknown'),
        'technologies': technologies,
        'statistics': {
            'timesteps': len(result.table) if result and hasattr(result, 'table') else 0,
            'duration_hours': len(result.table) * getattr(workflow, 'dt_h', 1.0) if result and hasattr(result, 'table') else 0,
        },
        'costs': costs,
    }

    return metadata


def process_workflow_dir(workflow_dir):
    """Process a single workflow directory."""

    workflow_file = workflow_dir / 'workflow.pkl'
    metadata_file = workflow_dir / 'metadata.json'

    # Check if workflow.pkl exists
    if not workflow_file.exists():
        print(f"   ⚠️  Überspringe {workflow_dir.name}: Keine workflow.pkl gefunden")
        return False

    # Check if metadata already exists
    if metadata_file.exists():
        print(f"   ℹ️  Überspringe {workflow_dir.name}: metadata.json existiert bereits")
        return False

    # Load workflow
    try:
        with open(workflow_file, 'rb') as f:
            workflow = pickle.load(f)

        # Extract and save metadata
        metadata = extract_metadata_from_workflow(workflow, workflow_dir)

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"   ✅ {workflow_dir.name}: metadata.json erstellt")
        return True

    except Exception as e:
        print(f"   ❌ Fehler bei {workflow_dir.name}: {e}")
        return False


def main():
    """Main execution."""

    print("="*70)
    print("🔧 Generiere fehlende metadata.json Dateien")
    print("="*70)
    print()

    # Get target directory
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1])
        if not target_dir.exists():
            print(f"❌ Ordner nicht gefunden: {target_dir}")
            sys.exit(1)
        workflow_dirs = [target_dir] if target_dir.is_dir() else []
    else:
        saved_workflows_dir = project_root / 'saved_workflows'
        if not saved_workflows_dir.exists():
            print(f"❌ Ordner nicht gefunden: {saved_workflows_dir}")
            sys.exit(1)
        workflow_dirs = [d for d in saved_workflows_dir.iterdir() if d.is_dir()]

    print(f"📁 Prüfe {len(workflow_dirs)} Ordner...")
    print()

    created_count = 0
    for workflow_dir in sorted(workflow_dirs):
        if process_workflow_dir(workflow_dir):
            created_count += 1

    print()
    print("="*70)
    if created_count > 0:
        print(f"✅ {created_count} metadata.json Datei(en) erstellt!")
        print()
        print("💡 Starte Dashboard neu um Änderungen zu sehen:")
        print("   python -m panel serve load_dashboard.py --port 5006 --show")
    else:
        print("ℹ️  Keine neuen metadata.json Dateien erstellt")
        print("   (Alle Ordner haben bereits Metadaten oder keine workflow.pkl)")
    print("="*70)


if __name__ == '__main__':
    main()
