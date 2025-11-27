#!/usr/bin/env python3
"""
Save workflow results to file for later dashboard use.

Usage:
    python save_workflow_results.py

Output:
    workflow_results.pkl - Saved workflow object
"""

import sys
import pickle
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("💾 EnerGIS - Workflow Ergebnisse speichern")
print("="*70)

from energis.run import rolling_horizon as rh

print("\n1. Lade Konfiguration...")
CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/sites/default.site.yaml',
    'configs/systems/baseline.system.yaml',
    'configs/scenarios/pf_then_rh.workflow.scenario.yaml',
]

print("   ✅ Konfiguration geladen")

print("\n2. Führe Optimierung aus...")
print("   ⏳ Dies kann einige Minuten dauern...")

try:
    workflow = rh.run_workflow(CONFIG_PATHS)
    print("   ✅ Optimierung abgeschlossen!")

    # Check results
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None

    print(f"\n3. Verfügbare Ergebnisse:")
    print(f"   PF: {'✅' if has_pf else '❌'}")
    print(f"   RH: {'✅' if has_rh else '❌'}")

    if has_pf or has_rh:
        # Save workflow
        output_file = project_root / 'workflow_results.pkl'

        print(f"\n4. Speichere Ergebnisse...")
        with open(output_file, 'wb') as f:
            pickle.dump(workflow, f, protocol=pickle.HIGHEST_PROTOCOL)

        file_size_mb = output_file.stat().st_size / 1024 / 1024
        print(f"   ✅ Gespeichert: {output_file}")
        print(f"   📦 Größe: {file_size_mb:.2f} MB")

        # Show stats
        result = workflow.pf_result or workflow.rh_result
        print(f"\n📈 Zusammenfassung:")
        print(f"   Zeitschritte: {len(result.table):,}")
        if result.costs:
            obj_value = result.costs.get('objective.OBJ_value_EUR', 0)
            print(f"   Gesamtkosten: {obj_value:,.0f} EUR")

        print("\n" + "="*70)
        print("✅ ERFOLG! Ergebnisse gespeichert!")
        print("="*70)

        print("\n📊 Nächste Schritte:")
        print("   1. Starte Dashboard: panel serve load_dashboard.py --show")
        print("   2. Oder in Jupyter: siehe notebooks/interactive_dashboard.ipynb")

    else:
        print("\n❌ Keine Ergebnisse zum Speichern")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ Fehler: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
