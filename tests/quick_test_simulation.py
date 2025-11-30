#!/usr/bin/env python3
"""
Schneller Test: Speichere eine Mini-Simulation für Dashboard-Demo.

Dies ist eine verkürzte Simulation (nur 1 Tag) für schnelles Testen.
"""

import sys
import pickle
import json
from pathlib import Path
from datetime import datetime

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("🚀 EnerGIS - Schnelltest (1 Tag)")
print("="*70)

# Import after path setup
from energis.run import rolling_horizon as rh

# Configuration with smaller horizon for quick test
CONFIG_PATHS = [
    'configs/base.yaml',
    'configs/tech_catalog.yaml',
    'configs/sites/default.site.yaml',
    'configs/systems/baseline.system.yaml',
    'configs/scenarios/pf_then_rh.workflow.scenario.yaml',
]

print("\n1. Lade Konfiguration...")
for i, path in enumerate(CONFIG_PATHS, 1):
    print(f"   {i}. {path}")

print("\n2. Führe Optimierung aus (verkürzte Version)...")
print("   ⏳ Dies kann 2-10 Minuten dauern...")
print("   💡 Für vollständige Simulation: python save_workflow_results.py")

try:
    # Modify for quick test: Only 1 day
    print("\n   🔧 Anpassung für Schnelltest:")
    print("      • Zeitraum: 2023-01-01 (nur 1 Tag statt ganzes Jahr)")
    print("      • Solver: GLPK")

    # Create overrides for quick test
    overrides = {
        'scenario': {
            'horizon': {
                'type': 'date_range',
                'start': '2023-01-01 00:00',
                'end': '2023-01-02 00:00',  # Only 1 day!
            }
        },
        'run': {
            'solver': 'glpk'
        }
    }

    # Run workflow with overrides
    print("\n   ▶️  Optimierung läuft...")
    workflow = rh.run_workflow(CONFIG_PATHS, overrides=overrides)

    print("   ✅ Optimierung abgeschlossen!")

    # Check results
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None

    print(f"\n3. Verfügbare Ergebnisse:")
    print(f"   PF:  {'✅' if has_pf else '❌'}")
    print(f"   RH:  {'✅' if has_rh else '❌'}")

    if not (has_pf or has_rh):
        print("\n❌ Keine Ergebnisse zum Speichern")
        sys.exit(1)

    # Save workflow
    print(f"\n4. Speichere Ergebnisse...")

    # Import save function
    from save_workflow_results import save_workflow

    workflow_dir, metadata = save_workflow(
        workflow,
        CONFIG_PATHS,
        custom_name="schnelltest_1tag",
        description="Test-Optimierung mit 1 Tag für Dashboard-Demo"
    )

    workflow_file = workflow_dir / 'workflow.pkl'
    workflow_size_mb = workflow_file.stat().st_size / 1024 / 1024

    print(f"   ✅ Gespeichert in: {workflow_dir.name}")
    print(f"   📦 Workflow: {workflow_size_mb:.2f} MB")

    # Show metadata summary
    print(f"\n📈 Zusammenfassung:")
    print(f"   Name: {metadata['name']}")
    print(f"   Beschreibung: {metadata['description']}")
    print(f"   Workflow: {' → '.join(metadata['workflow']['steps'])}")
    print(f"   Solver: {metadata['solver']}")
    print(f"   Zeitschritte: {metadata['statistics']['timesteps']:,}")
    print(f"   Dauer: {metadata['statistics']['duration_hours']:.1f} Stunden")

    if metadata['costs'].get('total_eur'):
        print(f"\n   💰 Kosten: {metadata['costs']['total_eur']:,.0f} EUR")

    print("\n" + "="*70)
    print("✅ ERFOLG! Test-Simulation gespeichert!")
    print("="*70)

    print("\n📊 Nächster Schritt:")
    print("   panel serve load_dashboard.py --show")

except Exception as e:
    print(f"\n❌ Fehler: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
