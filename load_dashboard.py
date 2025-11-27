#!/usr/bin/env python3
"""
Load pre-computed workflow results and display dashboard.

This provides FAST startup by using saved results instead of re-running optimization.

Usage:
    panel serve load_dashboard.py --show

Requirements:
    workflow_results.pkl file (created by save_workflow_results.py)
"""

import sys
import pickle
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("🎛️ EnerGIS Dashboard - Gespeicherte Ergebnisse laden")
print("="*70)

results_file = project_root / 'workflow_results.pkl'

# Check if results file exists
if not results_file.exists():
    print(f"\n❌ FEHLER: Keine gespeicherten Ergebnisse gefunden!")
    print(f"   Erwartet: {results_file}")
    print(f"\n💡 Lösung:")
    print("   1. Führe zuerst aus: python save_workflow_results.py")
    print("   2. Dann starte Dashboard: panel serve load_dashboard.py --show")
    sys.exit(1)

print(f"\n1. Lade Ergebnisse aus {results_file.name}...")

try:
    with open(results_file, 'rb') as f:
        workflow = pickle.load(f)

    file_size_mb = results_file.stat().st_size / 1024 / 1024
    print(f"   ✅ Geladen ({file_size_mb:.2f} MB)")

    # Check what's available
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None
    has_mpc = workflow.mpc_result is not None

    print(f"\n2. Verfügbare Ergebnisse:")
    print(f"   PF:  {'✅' if has_pf else '❌'}")
    print(f"   RH:  {'✅' if has_rh else '❌'}")
    print(f"   MPC: {'✅' if has_mpc else '❌'}")

    if not (has_pf or has_rh or has_mpc):
        print("\n❌ Keine gültigen Ergebnisse in der Datei!")
        sys.exit(1)

    # Show quick stats
    result = workflow.pf_result or workflow.rh_result or workflow.mpc_result
    print(f"\n3. Ergebnis-Übersicht:")
    print(f"   Zeitschritte: {len(result.table):,}")
    if result.costs:
        obj_value = result.costs.get('objective.OBJ_value_EUR', 0)
        print(f"   Gesamtkosten: {obj_value:,.0f} EUR")

    print("\n4. Erstelle Dashboard...")

    from energis.io.dashboard import create_dashboard

    dashboard = create_dashboard(
        workflow,
        title="EnerGIS Dashboard - Gespeicherte Ergebnisse"
    )

    print("   ✅ Dashboard erstellt!")

    print("\n" + "="*70)
    print("✅ SUCCESS! Dashboard ist bereit!")
    print("="*70)

    print("\n📊 Dashboard wird als Webapp bereitgestellt...")
    print("   URL: http://localhost:5006/load_dashboard")
    print("   Zum Beenden: Strg+C")

    # Make dashboard servable
    dashboard.servable()

except FileNotFoundError:
    print(f"\n❌ Datei nicht gefunden: {results_file}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Fehler beim Laden: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
