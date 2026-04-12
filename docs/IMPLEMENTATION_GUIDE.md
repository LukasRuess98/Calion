# Integration von Zonalen Kosten in system_builder.py

## SCHRITT 1: Import hinzufügen (Oben in der Datei)

```python
from calion.models.cost_resolver import CostResolver
```

## SCHRITT 2: CostResolver instantiieren (In _build_model_unified)

Etwa **nach** dieser Zeile (um Zeile 290):

```python
def _build_model_unified(
    table: TimeSeriesTable,
    cfg: dict[str, Any],
    dt_h: float = 1.0,
    *,
    soc_init_override: float | None = None,
    terminal_target_override: float | None = None,
):
    """Build model from unified config with per-node asset placement."""
    from calion.config.unified_config import parse_unified_config

    ucfg = parse_unified_config(cfg)
    T = len(table)

    m = pyo.ConcreteModel(name="CALION_Unified")
    m.t = pyo.RangeSet(1, T)
    period_frac = float(T * dt_h / HOURS_PER_YEAR)

    # ← NEUE ZEILE: CostResolver instantiieren
    cost_resolver = CostResolver(cfg, table)
    cost_resolver.log_resolution_summary()  # Debug-Output
```

## SCHRITT 3: Statische Zone-Kosten (Während Modell-Setup)

Etwa **um Zeile 350** (nach Grid-Parameter):

```python
    # ── Zone-specific costs (if costs_config present) ───────────────────────
    m.zone_demand_charge = {}  # Dict[zone_id] → Param
    for zone_id, node_cfg in ucfg.nodes.items():
        if node_cfg.type in ("consumer", "junction"):
            # Get static cost from resolver (uses global as fallback)
            charge = cost_resolver.get_zone_cost(
                zone_id, 
                "demand_charge_eur_per_mw_y"
            )
            m.zone_demand_charge[zone_id] = pyo.Param(initialize=charge)
            logger.debug(f"Zone {zone_id}: demand_charge = €{charge:.0f}/MW/Y")
```

## SCHRITT 4: Dynamische Zone-Kosten (Optionalsual für CSV-Tarife)

```python
    # ── Dynamic zone costs (hourly from CSV, if enabled) ──────────────────────
    if cost_resolver.dynamic_enabled:
        m.zone_demand_charge_ts = {}  # Dict[zone_id] → Param(m.t)
        logger.info("Dynamic costs enabled — loading hourly tariffs from CSV")
        
        for zone_id, node_cfg in ucfg.nodes.items():
            if node_cfg.type in ("consumer", "junction"):
                # Build dict: {t: charge_value_for_t}
                charge_dict = {}
                for t in m.t:
                    charge = cost_resolver.get_zone_cost(
                        zone_id,
                        "demand_charge_eur_per_mw_y",
                        timestep=t
                    )
                    charge_dict[t] = charge
                
                m.zone_demand_charge_ts[zone_id] = pyo.Param(
                    m.t,
                    initialize=charge_dict,
                    mutable=True
                )
    else:
        m.zone_demand_charge_ts = {}
```

## SCHRITT 5: Objective anpassen (In model_finalizer.py)

Auf diese Zeile hinarbeiten:

```python
# Alte Version (global):
demand_charge_expr = model.demand_charge_y * model.year_frac * model.P_buy_peak

# Neue Version (zonal):
if hasattr(model, 'zone_demand_charge'):
    demand_charge_expr = sum(
        model.zone_demand_charge[zone_id] * model.year_frac * 
        model.P_buy_peak_by_zone.get(zone_id, model.P_buy_peak)
        for zone_id in model.zone_demand_charge.keys()
    )
elif hasattr(model, 'zone_demand_charge_ts') and model.zone_demand_charge_ts:
    # Dynamic: Summe über alle Zeitschritte
    demand_charge_expr = sum(
        model.zone_demand_charge_ts[zone_id][t] * 
        model.P_buy_by_zone.get(zone_id, model.P_buy)[t] * dt_h
        for zone_id in model.zone_demand_charge_ts.keys()
        for t in model.t
    )
else:
    # Fallback: alte globale Version
    demand_charge_expr = model.demand_charge_y * model.year_frac * model.P_buy_peak
```

## SCHRITT 6: Ausgabe anreichern (In result_collector.py)

```python
def _collect_timeseries_and_summary(...):
    # ... existing code ...
    
    # ← NEU: Zone-Kostenaufschlüsselung
    if hasattr(model, 'zone_demand_charge'):
        summary_sections["zone_costs"] = OrderedDict()
        for zone_id, param in model.zone_demand_charge.items():
            charge = float(pyo.value(param))
            summary_sections["zone_costs"][zone_id] = {
                "demand_charge_eur_per_mw_y": charge,
                "type": cost_resolver.get_zone_type(zone_id),
            }
```

---

## ✅ Checkliste: Integration komplett?

- [ ] `from calion.models.cost_resolver import CostResolver` importiert
- [ ] `CostResolver(cfg, table)` in _build_model_unified instantiiert
- [ ] `m.zone_demand_charge` Dict erstellt für statische Kosten
- [ ] `m.zone_demand_charge_ts` Dict erstellt für dynamische Kosten (falls enabled)
- [ ] Objective-Funktion aktualisiert → summiert über Zonen
- [ ] Result-Sammlung: Zone-Kosten zur Ausgabe hinzugefügt
- [ ] Test ausgeführt: `pytest tests/test_cost_resolver.py`

---

## 🧪 Quick-Test

```bash
# 1. CostResolver direkt testen (keine Optimierung)
cd /c/Users/LKR/Downloads/tespy-dev/Planing-Framework-for-Heat
python tests/test_cost_resolver.py

# 2. Mit echtem Szenario testen
python scripts/paper/run_all_levels.py \
    --config configs/paper/L2_costs_example_2_zonal_static.yaml \
    --horizon 24  # Nur 1 Tag zum schnellen Testen
```

---

## 📊 Erwartete Ausgabe (Debug-Log)

```
CostResolver initialized: 3 global, 5 zone-specific costs, dynamic enabled=False
========================================================================
COST RESOLUTION SUMMARY
========================================================================

Zone: j_central                 Type: central_junction
  demand_charge_eur_per_mw_y   30000.00
  energy_fee_eur_per_mwh       5.00

Zone: j_south                   Type: peripheral
  demand_charge_eur_per_mw_y   70000.00
  energy_fee_eur_per_mwh       5.00

Zone: plant_main                Type: central_plant
  demand_charge_eur_per_mw_y   0.00

========================================================================
```

---

## 🎯 Fehlerbehandlung

### Fehler: "costs_config not found"
- ✓ Das ist OK — Fallback auf alte `grid.demand_charge_eur_per_mw_y`
- Seite einmal nicht vorhanden sein wenn costs_config nicht definiert

### Fehler: "CSV column not found"
- ✓ Automatisches Fallback auf Zone-Static oder Global
- Loggt Warning aber läuft weiter

### Fehler: "Zone-ID nicht in nodes"
- ✓ Einfach Kosten für nicht-existierende Zone ignoriert

---

## 💡 Tipps für Debugging

```python
# 1. Alle Zone-Kosten ausdruck:
all_costs = cost_resolver.get_all_zones_costs()
for zone, costs in all_costs.items():
    print(f"{zone}: {costs}")

# 2. Ein einzelnes Zone-Kosten-Wert:
charge = cost_resolver.get_zone_cost("j_south", "demand_charge_eur_per_mw_y", t=5)
print(f"j_south at t=5: €{charge:.2f}")

# 3. Zone-Typ überprüfen:
ztype = cost_resolver.get_zone_type("j_central")
print(f"j_central type: {ztype}")

# 4. Komplette Zusammenfassung:
cost_resolver.log_resolution_summary()
```
