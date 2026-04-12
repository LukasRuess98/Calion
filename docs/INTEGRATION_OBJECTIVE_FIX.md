# FIX: So wird die Objective-Funktion ZONAL gemacht

## IN model_finalizer.py (Zeile 428-430)

### VORHER (Global nur):

```python
        demand_term = calculate_demand_charge(m, include_demand=flags.include_demand)
```

### NACHHER (Mit zonal support):

```python
        # ← NEUE ZEILEN: Nutze zonal-aware Variante
        from calion.models.cost_calculator_zonal import (
            calculate_demand_charge_zonal,
            calculate_demand_charge_zonal_dynamic,
        )
        
        # Entscheide: Sind dynamische Kosten aktiviert?
        if hasattr(m, 'zone_demand_charge_ts') and m.zone_demand_charge_ts:
            # Dynamic (CSV-basiert)
            demand_term = calculate_demand_charge_zonal_dynamic(
                m, 
                include_demand=flags.include_demand
            )
        else:
            # Statisch (YAML oder global)
            demand_term = calculate_demand_charge_zonal(
                m, 
                include_demand=flags.include_demand
            )
```

---

## Das ist die MINIMALE Änderung!

**Nur 2 Dinge müssen sich ändern:**

### 1. Import hinzufügen (oben in model_finalizer.py)

```python
from calion.models.cost_calculator_zonal import (
    calculate_demand_charge_zonal,
    calculate_demand_charge_zonal_dynamic,
)
```

### 2. Zeile 430 ersetzen

```python
# ALT (zeile 430):
demand_term = calculate_demand_charge(m, include_demand=flags.include_demand)

# NEU:
if hasattr(m, 'zone_demand_charge_ts') and m.zone_demand_charge_ts:
    demand_term = calculate_demand_charge_zonal_dynamic(m, include_demand=flags.include_demand)
else:
    demand_term = calculate_demand_charge_zonal(m, include_demand=flags.include_demand)
```

---

## BEISPIEL: Was sich ÄNDERT

Angenommen:
- `j_central`: 30,000 EUR/MW/Year
- `j_south`: 70,000 EUR/Year  
- Peak Power `j_central`: 65 MW
- Peak Power `j_south`: 70 MW

### ALT (Global, FALSCH):
```python
demand = 50,000 EUR/MW/Y × 1.0 × 75 MW = 3,750,000 EUR
# Alle Zonen zahlen gleich — FALSCH!
```

### NEU (Zonal, RICHTIG):
```python
demand = (
    30,000 × 1.0 × 65 +      # j_central
    70,000 × 1.0 × 70        # j_south
)
= 1,950,000 + 4,900,000 
= 6,850,000 EUR
# Jede Zone zahlt ihre eigenen Kosten — RICHTIG!
```

**Differenz: +3,100,000 EUR** (84% teurer!)
→ Das ist der Impact von zonalen Kosten!

---

## KOMPLETTER PATCH (Einfach kopieren)

In `calion/models/model_finalizer.py`, in der `build_and_set_objective()` Funktion, ersetze:

```python
        demand_term = calculate_demand_charge(m, include_demand=flags.include_demand)
```

...mit:

```python
        # Zonal-aware demand charge calculation
        from calion.models.cost_calculator_zonal import (
            calculate_demand_charge_zonal,
            calculate_demand_charge_zonal_dynamic,
        )
        
        # Determine which variant to use based on model state
        has_dynamic_costs = hasattr(m, 'zone_demand_charge_ts') and m.zone_demand_charge_ts
        if has_dynamic_costs:
            # Dynamic (hourly) zonal costs from CSV
            demand_term = calculate_demand_charge_zonal_dynamic(
                m, 
                include_demand=flags.include_demand
            )
            logger.debug("Using dynamic zonal demand charges (hourly from CSV)")
        elif hasattr(m, 'zone_demand_charge') and m.zone_demand_charge:
            # Static zonal costs from YAML
            demand_term = calculate_demand_charge_zonal(
                m, 
                include_demand=flags.include_demand
            )
            logger.debug(
                "Using static zonal demand charges: %d zones",
                len(m.zone_demand_charge)
            )
        else:
            # Fallback: Global cost (backward compatibility)
            from calion.models.cost_calculator import calculate_demand_charge
            demand_term = calculate_demand_charge(
                m, 
                include_demand=flags.include_demand
            )
            logger.debug("Using global demand charge (no zones defined)")
```

---

## WICHTIG: Auch das braucht es!

### In `system_builder.py` (Zeile ~290, nach Modell-Setup):

```python
# Zonale Peak-Power Variablen pro Zone
m.P_buy_peak_by_zone = {}
for zone_id in cost_resolver.zone_costs.keys():
    m.P_buy_peak_by_zone[zone_id] = pyo.Var(domain=pyo.NonNegativeReals)

# Zonale Macht-Variablen (für dynamic)
m.P_buy_by_zone = {}
for zone_id in cost_resolver.zone_costs.keys():
    m.P_buy_by_zone[zone_id] = pyo.Var(m.t, domain=pyo.NonNegativeReals)
```

Und in Constraints:
```python
# Peak tracking per Zone
for zone_id in m.P_buy_peak_by_zone.keys():
    m.add_component(
        f"peak_track_{zone_id}",
        pyo.Constraint(
            m.t,
            rule=lambda m, t, z=zone_id: m.P_buy_peak_by_zone[z] >= m.P_buy_by_zone[z][t]
        )
    )
```

---

## TESTING

```bash
# Mit Zonen testen (sollte anders sein als vorher)
python tests/test_cost_resolver.py

# Mit echtem Szenario
python scripts/paper/run_all_levels.py \
    --config configs/paper/L2_costs_example_2_zonal_static.yaml \
    --horizon 24
```

### Erwartete Ausgabe:

```
[DEBUG] Using static zonal demand charges: 5 zones
[DEBUG] Zone j_central: 30000.0 EUR/MW/Y
[DEBUG] Zone j_south: 70000.0 EUR/MW/Y
...
Objective: 6,850,000 EUR  (mit zonalen Kosten)
vs.
Objective: 3,750,000 EUR  (alte global-Only version)
```

---

## SUMMARY: Wo geht es hin?

```
CALION Zielfunktion:

                    ┌─────────────────────────────┐
                    │ GESAMTKOSTEN                │
                    └──────────┬──────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
       ┌────▼─────┐       ┌───▼────┐        ┌────▼─────┐
       │ Energie  │       │ Fuel   │        │ Demand   │  ◄── IHR FOKUS
       │ Costs    │       │ Costs  │        │ Charges  │
       └──────────┘       └────────┘        └────┬─────┘
                                                 │
                                    ┌────────────┴────────────┐
                                    │ JETZT ZONAL!           │
                                    │                        │
                               ┌────▼────┐            ┌──────▼──┐
                               │ Zone A  │   +   ...  │ Zone N  │
                               │ (€30k)  │            │ (€70k)  │
                               └─────────┘            └─────────┘
                               
                               ← DIESE SUMME geht in Zielfunktion!
```
