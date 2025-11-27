#!/usr/bin/env python3
"""
Run optimization with custom config and display dashboard as webapp.

This allows running different scenarios by specifying config files.

Usage:
    # Use default config
    panel serve run_dashboard.py --show

    # Custom config (set CONFIG_PATHS in this file before running)
    panel serve run_dashboard.py --show

Features:
    - Runs optimization when webapp starts
    - Can use any config combination
    - Results are computed fresh each time
"""

import sys
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("🎛️ EnerGIS Dashboard - Optimierung + Webapp")
print("="*70)

# ============================================================================
# CONFIGURATION - Passe diese Pfade an für verschiedene Szenarien!
# ============================================================================

CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/sites/default.site.yaml',
    'configs/systems/baseline.system.yaml',
    'configs/scenarios/pf_then_rh.workflow.scenario.yaml',
]

# Oder z.B. für einen anderen Workflow:
# CONFIG_PATHS = [
#     'configs/base.yaml',
#     'configs/tech_catalog.yaml',
#     'configs/sites/custom.site.yaml',
#     'configs/systems/advanced.system.yaml',
#     'configs/scenarios/mpc.workflow.scenario.yaml',
# ]

# ============================================================================

from energis.io.dashboard import create_dashboard
from energis.run import rolling_horizon as rh

print("\n1. Lade Konfiguration...")
for i, path in enumerate(CONFIG_PATHS, 1):
    print(f"   {i}. {path}")

print("   ✅ Konfiguration geladen")

print("\n2. Führe Optimierung aus...")
print("   ⏳ Dies kann einige Minuten dauern...")
print("   💡 Die Webapp startet nach Abschluss der Optimierung")

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

    if has_pf or has_rh or has_mpc:
        print("\n4. Erstelle Dashboard...")

        # Build title from config
        scenario_name = Path(CONFIG_PATHS[-1]).stem.replace('.workflow.scenario', '')
        dashboard = create_dashboard(
            workflow,
            title=f"EnerGIS Dashboard - {scenario_name}"
        )
        print("   ✅ Dashboard erstellt!")

        # Show stats
        result = workflow.pf_result or workflow.rh_result or workflow.mpc_result
        print(f"\n📈 Ergebnis-Übersicht:")
        print(f"   Zeitschritte: {len(result.table):,}")
        if result.costs:
            obj_value = result.costs.get('objective.OBJ_value_EUR', 0)
            print(f"   Gesamtkosten: {obj_value:,.0f} EUR")

        print("\n" + "="*70)
        print("✅ SUCCESS! Dashboard wird gestartet...")
        print("="*70)

        print("\n📊 Webapp läuft auf:")
        print("   URL: http://localhost:5006/run_dashboard")
        print("   Zum Beenden: Strg+C")

        print("\n💡 Tipp: Um verschiedene Szenarien zu vergleichen:")
        print("   1. Speichere Ergebnisse: python save_workflow_results.py")
        print("   2. Ändere CONFIG_PATHS oben in diesem Skript")
        print("   3. Führe erneut aus und vergleiche")

        # Make dashboard servable
        dashboard.servable()

    else:
        print("\n❌ Keine Ergebnisse verfügbar - Optimierung fehlgeschlagen")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ Fehler: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
