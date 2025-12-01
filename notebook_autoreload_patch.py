# ============================================================================
# KOPIERE DIESEN CODE IN EINE NEUE ERSTE ZELLE IM NOTEBOOK
# ============================================================================
#
# Füge diese Zelle ganz am Anfang von scenario_studio.ipynb ein,
# VOR allen anderen Zellen!
#
# Was macht das?
# - Aktiviert automatisches Reload von geänderten Modulen
# - Dashboard-Fixes werden automatisch geladen
# - Kein manueller Kernel-Restart mehr nötig bei Code-Änderungen
# ============================================================================

# IPython Magic: Autoreload
%load_ext autoreload
%autoreload 2

# Logging konfigurieren (zeigt Dashboard-Warnungen)
import logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)

print("="*70)
print("✅ AUTORELOAD AKTIVIERT")
print("="*70)
print("📝 Code-Änderungen werden automatisch neu geladen")
print("📋 Logging aktiviert (Level: WARNING)")
print("💡 Dashboard-Probleme werden jetzt im Log angezeigt")
print("="*70)

# ============================================================================
# ENDE DER PATCH-ZELLE
# ============================================================================


# ============================================================================
# OPTIONAL: DEBUG-ZELLE (separate Zelle nach Dashboard-Erstellung)
# ============================================================================
#
# Füge diese Zelle NACH der Dashboard-Erstellung ein,
# wenn du Probleme hast und debuggen möchtest
# ============================================================================

print("\n" + "="*70)
print("🔍 DASHBOARD DEBUG INFO")
print("="*70)

# Prüfe ob Dashboard geladen wurde
try:
    from energis.io.dashboard import EnerGISDashboard
    import inspect

    # Prüfe _prepare_data Methode
    source = inspect.getsource(EnerGISDashboard._prepare_data)

    # Feature-Check
    has_flexible_demand = "demand_col_names" in source
    has_validation = "len(values) == len(self.df)" in source
    has_logging = "logging.warning" in source

    print("\n📦 Dashboard-Version:")
    print(f"   {'✅' if has_flexible_demand else '❌'} Flexible Demand-Erkennung")
    print(f"   {'✅' if has_validation else '❌'} Series-Validierung")
    print(f"   {'✅' if has_logging else '❌'} Logging-Warnungen")

    if has_flexible_demand and has_validation and has_logging:
        print("\n✅ NEUE VERSION IST GELADEN")
    else:
        print("\n❌ ALTE VERSION - Kernel neu starten!")

except Exception as e:
    print(f"\n❌ Fehler beim Version-Check: {e}")

# Prüfe Workflow-Daten
if 'workflow' in locals() and workflow is not None:
    print("\n📊 Workflow-Daten:")
    print(f"   PF: {workflow.pf_result is not None}")
    print(f"   RH: {workflow.rh_result is not None}")
    print(f"   MPC: {workflow.mpc_result is not None}")

    primary_result = workflow.rh_result or workflow.mpc_result or workflow.pf_result

    if primary_result:
        print(f"\n📋 Primäres Ergebnis:")
        print(f"   Type: {type(primary_result).__name__}")
        print(f"   Series Keys: {len(primary_result.series)} Einträge")
        print(f"   Erste 5 Keys: {list(primary_result.series.keys())[:5]}")
        print(f"   table.data Keys: {list(primary_result.table.data.keys())}")
        print(f"   Zeitschritte: {len(primary_result.table)}")

        # Prüfe Kosten
        if hasattr(primary_result, 'costs') and primary_result.costs:
            print(f"\n💰 Kosten:")
            print(f"   Anzahl Einträge: {len(primary_result.costs)}")
            eur_keys = [k for k in primary_result.costs.keys() if k.endswith('_EUR')]
            print(f"   EUR-Einträge: {len(eur_keys)}")
            if eur_keys:
                print(f"   Beispiele: {eur_keys[:3]}")
        else:
            print(f"\n⚠️  Keine Kosten verfügbar")

        # Prüfe Design
        if 'workflow' in locals() and workflow.design:
            print(f"\n🏭 Design:")
            print(f"   Heat Pumps: {len(workflow.design.heat_pumps) if workflow.design.heat_pumps else 0}")
            print(f"   Storage: {'Ja' if workflow.design.storage else 'Nein'}")
        else:
            print(f"\n⚠️  Kein Design verfügbar")
    else:
        print(f"\n❌ Kein primäres Ergebnis gefunden!")
else:
    print("\n⚠️  Workflow noch nicht ausgeführt")

print("\n" + "="*70)

# ============================================================================
# ENDE DER DEBUG-ZELLE
# ============================================================================
