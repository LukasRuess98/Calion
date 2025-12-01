#!/usr/bin/env python3
"""
Debug-Skript: Zeigt welche Dashboard-Version geladen ist.

Verwende dieses Skript um zu prüfen, ob die neueste dashboard.py Version
im Jupyter Kernel geladen ist.
"""

import sys
from pathlib import Path

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("🔍 Dashboard Version Check")
print("="*70)

# Check if dashboard is already imported
if 'energis.io.dashboard' in sys.modules:
    print("\n⚠️  Dashboard ist bereits importiert!")

    import energis.io.dashboard as dashboard_module

    # Get file path
    dashboard_file = Path(dashboard_module.__file__)
    print(f"📁 Geladene Datei: {dashboard_file}")

    # Check modification time
    import datetime
    mtime = datetime.datetime.fromtimestamp(dashboard_file.stat().st_mtime)
    print(f"⏰ Letzte Änderung: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

    # Check if _prepare_data has new code
    import inspect
    source = inspect.getsource(dashboard_module.EnerGISDashboard._prepare_data)

    # Look for new features
    has_flexible_demand = "demand_col_names" in source
    has_validation = "result.series" in source and "len(values) == len(self.df)" in source
    has_logging = "logging.warning" in source

    print(f"\n🔍 Feature-Check:")
    print(f"   {'✅' if has_flexible_demand else '❌'} Flexible Demand-Erkennung")
    print(f"   {'✅' if has_validation else '❌'} Series-Validierung")
    print(f"   {'✅' if has_logging else '❌'} Logging-Warnungen")

    if has_flexible_demand and has_validation and has_logging:
        print(f"\n✅ NEUE VERSION IST GELADEN!")
    else:
        print(f"\n❌ ALTE VERSION IST NOCH GELADEN!")
        print(f"\n💡 Lösung: Kernel neu starten!")
        print(f"   Jupyter: Kernel > Restart Kernel")
        print(f"   VS-Code: Klick auf 'Restart' im Kernel-Auswahlfeld")
else:
    print("\n✅ Dashboard ist noch nicht importiert")
    print("   Erstes Import wird neue Version laden")

# Try to import fresh
print(f"\n🔄 Teste frischen Import...")
from energis.io.dashboard import create_dashboard

# Check version
import inspect
source = inspect.getsource(create_dashboard)

print(f"✅ Dashboard-Modul geladen")
print(f"📦 Modul-Pfad: {create_dashboard.__module__}")

# Detailed check
from energis.io.dashboard import EnerGISDashboard
source = inspect.getsource(EnerGISDashboard._prepare_data)

print(f"\n📋 _prepare_data Methode:")
print(f"   Zeilen: {len(source.splitlines())}")

# Count features
n_demand_names = source.count("demand_col_names")
n_logging = source.count("logging.warning")
n_validation = source.count("len(values)")

print(f"   demand_col_names: {n_demand_names}x")
print(f"   logging.warning: {n_logging}x")
print(f"   Validierungen: {n_validation}x")

if n_demand_names > 0 and n_logging > 3 and n_validation > 0:
    print(f"\n✅ NEUE VERSION BESTÄTIGT!")
    print(f"\n💡 Wenn Dashboard trotzdem nicht funktioniert:")
    print(f"   1. Prüfe ob Optimierung erfolgreich war")
    print(f"   2. Schaue in Logs: logging.basicConfig(level=logging.WARNING)")
    print(f"   3. Prüfe result.series: print(workflow.rh_result.series.keys())")
else:
    print(f"\n⚠️  VERSION UNKLAR oder ALTE VERSION")
    print(f"\n💡 Bitte Kernel neu starten!")

print("\n" + "="*70)
