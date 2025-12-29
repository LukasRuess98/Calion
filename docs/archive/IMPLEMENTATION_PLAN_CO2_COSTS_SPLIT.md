# Implementierungsplan: CO₂-Kosten-Aufteilung im Pyomo-Modell

## ZIEL

CO₂-Kosten sollen **im Pyomo-Modell** pro Komponente berechnet werden:
- **Pro Generator/WP/P2H** einzeln
- **Aufgeteilt nach Wärme und Strom** (basierend auf Wirkungsgrad)
- **Aufsummiert**: Wärme-CO₂-Kosten, Strom-CO₂-Kosten, Gesamt
- **In Zielfunktion**: Als Summe optimiert
- **Exportiert**: Alle Einzelwerte
- **Dashboard**: Visualisierung

---

## AKTUELLE IMPLEMENTIERUNG (Status Quo)

### 1. Pyomo-Modell (`energis/models/system_builder.py`)

**Zeile 740-741**: CO₂ pro Generator (aggregiert)
```python
for generator in generators:
    fuel_cost_terms.append(sum(fuel_in[t] * price * dt_h for t in m.t))
    fuel_co2_terms.append(sum(fuel_in[t] * ef * dt_h for t in m.t))  # kg CO₂
```

**Zeile 791-793**: Gesamte CO₂-Kosten
```python
co2_grid = sum(m.P_buy[t] * table["grid_co2_kg_MWh"][t - 1] * dt_h for t in m.t)  # kg
co2_fuel = sum(fuel_co2_terms) if fuel_co2_terms else 0  # kg
co2_term = (m.co2_price / 1000.0) * (co2_grid + co2_fuel)  # EUR
```

**Zeile 809-820**: Zielfunktion
```python
m.obj = pyo.Objective(
    expr=energy_cost
        + dump_cost
        + fuel_costs
        + co2_term  # ← Aggregiertes CO₂
        + demand_term
        + capex_total
        + ...,
    sense=pyo.minimize
)
```

### Problem:
- ❌ Keine CO₂-Kosten **pro Komponente**
- ❌ Keine Aufteilung **Wärme/Strom** bei KWK
- ❌ WP/P2H CO₂ nicht separat (versteckt in Grid-CO₂)
- ❌ Einzelwerte nicht exportiert

---

## NEUE IMPLEMENTIERUNG

### 1. Pyomo-Modell: CO₂-Kosten pro Komponente

#### 1.1 Speicher für CO₂-Expressions

**Position**: Nach Zeile 365 (nach `storage_install_terms`)
```python
# CO₂-Kosten pro Komponente
co2_cost_heat_terms: List = []    # CO₂-Kosten für Wärmeerzeugung [EUR]
co2_cost_elec_terms: List = []    # CO₂-Kosten für Stromerzeugung [EUR]
co2_kg_heat_terms: List = []      # CO₂-Emissionen für Wärme [kg]
co2_kg_elec_terms: List = []      # CO₂-Emissionen für Strom [kg]

# Dictionary für Export (Komponenten-spezifisch)
m.co2_component_costs = {}  # {component_name: {'heat_eur': expr, 'elec_eur': expr, ...}}
```

---

#### 1.2 Wärmepumpen: CO₂-Kosten

**Position**: Im WP-Loop (ca. Zeile 367-550)

**Nach Zeile ~549** (nach `activation_terms.append(...)`):
```python
# ✅ NEU: Berechne CO₂-Kosten für Wärmepumpe
# WP verbraucht Strom → indirekte Emissionen
hp_co2_kg = sum(
    hp_block.P_el[t] * table["grid_co2_kg_MWh"][t - 1] * dt_h
    for t in m.t
)
hp_co2_cost_eur = (m.co2_price / 1000.0) * hp_co2_kg

# Speichere für Export
m.co2_component_costs[name] = {
    'heat_kg': 0,  # WP erzeugt Wärme, aber CO₂ kommt vom Strom
    'elec_kg': hp_co2_kg,  # Stromverbrauch → Grid-Emissionen
    'heat_eur': 0,
    'elec_eur': hp_co2_cost_eur,
    'total_kg': hp_co2_kg,
    'total_eur': hp_co2_cost_eur,
    'type': 'heat_pump'
}

# Füge zu Summen hinzu
co2_kg_elec_terms.append(hp_co2_kg)
co2_cost_elec_terms.append(hp_co2_cost_eur)
```

**Begründung**:
- WP verbraucht Strom (Grid) → CO₂ aus Strommix
- Wärme ist indirekt, CO₂ wird dem Strom zugeordnet

---

#### 1.3 Generatoren (ohne CHP): CO₂-Kosten

**Position**: Im Generator-Loop (Zeile 714-741)

**ERSETZE Zeile 740-741**:
```python
# ALT (entfernen):
fuel_cost_terms.append(sum(fs["fuel_in"][t] * price * dt_h for t in m.t))
fuel_co2_terms.append(sum(fs["fuel_in"][t] * ef * dt_h for t in m.t))

# NEU:
comp_name = key.upper()  # z.B. "HKW"

# Fuel-Kosten (wie bisher)
fuel_cost_expr = sum(fs["fuel_in"][t] * price * dt_h for t in m.t)
fuel_cost_terms.append(fuel_cost_expr)

# CO₂ aus Brennstoff [kg]
fuel_co2_kg = sum(fs["fuel_in"][t] * ef * dt_h for t in m.t)

# Prüfe ob CHP (hat elektrischen Ausgang)
is_chp = fs.get("P_el_out") is not None

if not is_chp:
    # Reiner Wärmeerzeuger → Alles CO₂ → Wärme
    co2_heat_kg = fuel_co2_kg
    co2_elec_kg = 0
    co2_heat_cost = (m.co2_price / 1000.0) * co2_heat_kg
    co2_elec_cost = 0

    m.co2_component_costs[comp_name] = {
        'heat_kg': co2_heat_kg,
        'elec_kg': 0,
        'heat_eur': co2_heat_cost,
        'elec_eur': 0,
        'total_kg': fuel_co2_kg,
        'total_eur': co2_heat_cost,
        'type': 'thermal_generator'
    }

    co2_kg_heat_terms.append(co2_heat_kg)
    co2_cost_heat_terms.append(co2_heat_cost)

else:
    # CHP → Aufteilung nach Wirkungsgrad (siehe 1.4)
    pass  # Wird im nächsten Abschnitt behandelt
```

---

#### 1.4 Generatoren (CHP): CO₂-Aufteilung Wärme/Strom

**Position**: Im `else`-Zweig oben

**Methode**: Exergetische Aufteilung (basierend auf Wirkungsgrad)

```python
else:
    # CHP-Anlage: Aufteilung nach energetischer Methode
    # Brennstoff → th_eff × Wärme + el_eff × Strom

    th_eff = float(gpar.get("th_eff", 0.9))
    el_eff = float(gpar.get("el_eff", 0.0))
    total_eff = th_eff + el_eff

    if total_eff > 0:
        # Aufteilung: CO₂ proportional zum Wirkungsgrad
        heat_fraction = th_eff / total_eff
        elec_fraction = el_eff / total_eff
    else:
        heat_fraction = 1.0
        elec_fraction = 0.0

    # CO₂ aufteilen [kg]
    co2_heat_kg = fuel_co2_kg * heat_fraction
    co2_elec_kg = fuel_co2_kg * elec_fraction

    # CO₂-Kosten aufteilen [EUR]
    co2_heat_cost = (m.co2_price / 1000.0) * co2_heat_kg
    co2_elec_cost = (m.co2_price / 1000.0) * co2_elec_kg

    m.co2_component_costs[comp_name] = {
        'heat_kg': co2_heat_kg,
        'elec_kg': co2_elec_kg,
        'heat_eur': co2_heat_cost,
        'elec_eur': co2_elec_cost,
        'total_kg': fuel_co2_kg,
        'total_eur': (m.co2_price / 1000.0) * fuel_co2_kg,
        'type': 'chp',
        'th_eff': th_eff,
        'el_eff': el_eff
    }

    co2_kg_heat_terms.append(co2_heat_kg)
    co2_kg_elec_terms.append(co2_elec_kg)
    co2_cost_heat_terms.append(co2_heat_cost)
    co2_cost_elec_terms.append(co2_elec_cost)
```

**Begründung**:
- BHKW mit th_eff=0.743, el_eff=0.177
- Total = 0.92
- Heat fraction = 0.743 / 0.92 = 80.8%
- Elec fraction = 0.177 / 0.92 = 19.2%
- Bei 100 t CO₂: 80.8 t → Wärme, 19.2 t → Strom

---

#### 1.5 P2H: CO₂-Kosten

**Position**: Im P2H-Block (Zeile 694-712)

**Nach Zeile 712** (nach `ht_out.append(...)`):
```python
# ✅ NEU: Berechne CO₂-Kosten für P2H
# P2H verbraucht Strom → indirekte Emissionen
p2h_co2_kg = sum(
    fs["P_el_in"][t] * table["grid_co2_kg_MWh"][t - 1] * dt_h
    for t in m.t
)
p2h_co2_cost_eur = (m.co2_price / 1000.0) * p2h_co2_kg

m.co2_component_costs["P2H"] = {
    'heat_kg': 0,  # Wärme aus Strom, CO₂ dem Strom zugeordnet
    'elec_kg': p2h_co2_kg,
    'heat_eur': 0,
    'elec_eur': p2h_co2_cost_eur,
    'total_kg': p2h_co2_kg,
    'total_eur': p2h_co2_cost_eur,
    'type': 'p2h'
}

co2_kg_elec_terms.append(p2h_co2_kg)
co2_cost_elec_terms.append(p2h_co2_cost_eur)
```

---

#### 1.6 Grid-CO₂ (Rest-Strombezug)

**Position**: Ersetze Zeile 791-793

```python
# ALT (entfernen):
co2_grid = sum(m.P_buy[t] * table["grid_co2_kg_MWh"][t - 1] * dt_h for t in m.t)
co2_fuel = sum(fuel_co2_terms) if fuel_co2_terms else 0
co2_term = (m.co2_price / 1000.0) * (co2_grid + co2_fuel) if include_co2 else 0

# NEU:
# Grid-CO₂ ist bereits in WP/P2H enthalten!
# Wir berechnen nur noch "direkten" Strombezug (falls vorhanden)
# ABER: P_buy enthält WP+P2H+sonstigen Verbrauch
# Problem: Doppelzählung vermeiden!

# Lösung: Nur noch Summen verwenden
co2_cost_heat_total = sum(co2_cost_heat_terms) if co2_cost_heat_terms else 0
co2_cost_elec_total = sum(co2_cost_elec_terms) if co2_cost_elec_terms else 0
co2_cost_total = co2_cost_heat_total + co2_cost_elec_total

# Speichere Gesamt-Expressions am Modell
m.co2_cost_heat_expr = co2_cost_heat_total
m.co2_cost_elec_expr = co2_cost_elec_total
m.co2_cost_total_expr = co2_cost_total

co2_term = co2_cost_total if include_co2 else 0
```

**WICHTIG**: Grid-CO₂ wird jetzt **nur noch** über WP/P2H erfasst!

---

#### 1.7 Zielfunktion (unverändert)

**Zeile 809-820**: Bleibt gleich!
```python
m.obj = pyo.Objective(
    expr=energy_cost
        + dump_cost
        + fuel_costs
        + co2_term  # ← Jetzt Summe aller Komponenten-CO₂-Kosten
        + demand_term
        + capex_total
        + ...,
    sense=pyo.minimize
)
```

---

### 2. Export-Anpassungen (`energis/run/rolling_horizon.py`)

#### 2.1 Export CO₂-Kosten pro Komponente

**Position**: Nach Zeile 570 (nach `objective["OBJ_value_EUR"] = ...`)

**Neue Funktion**:
```python
def _extract_co2_costs_from_model(model, meta, objective):
    """Extrahiere CO₂-Kosten pro Komponente aus Pyomo-Modell."""

    if not hasattr(model, 'co2_component_costs'):
        return  # Kein CO₂-Dict im Modell

    co2_components = {}

    for comp_name, co2_data in model.co2_component_costs.items():
        co2_components[comp_name] = {
            'CO2_heat_kg': float(pyo.value(co2_data['heat_kg'])),
            'CO2_elec_kg': float(pyo.value(co2_data['elec_kg'])),
            'CO2_total_kg': float(pyo.value(co2_data['total_kg'])),
            'CO2_heat_cost_EUR': float(pyo.value(co2_data['heat_eur'])),
            'CO2_elec_cost_EUR': float(pyo.value(co2_data['elec_eur'])),
            'CO2_total_cost_EUR': float(pyo.value(co2_data['total_eur'])),
            'type': co2_data['type']
        }

        # Füge zu objective hinzu
        objective[f"CO2_{comp_name}_heat_kg"] = co2_components[comp_name]['CO2_heat_kg']
        objective[f"CO2_{comp_name}_elec_kg"] = co2_components[comp_name]['CO2_elec_kg']
        objective[f"CO2_{comp_name}_total_kg"] = co2_components[comp_name]['CO2_total_kg']
        objective[f"CO2_{comp_name}_heat_cost_EUR"] = co2_components[comp_name]['CO2_heat_cost_EUR']
        objective[f"CO2_{comp_name}_elec_cost_EUR"] = co2_components[comp_name]['CO2_elec_cost_EUR']
        objective[f"CO2_{comp_name}_total_cost_EUR"] = co2_components[comp_name]['CO2_total_cost_EUR']

    # Gesamt-Summen
    if hasattr(model, 'co2_cost_heat_expr'):
        objective["CO2_heat_total_cost_EUR"] = float(pyo.value(model.co2_cost_heat_expr))

    if hasattr(model, 'co2_cost_elec_expr'):
        objective["CO2_elec_total_cost_EUR"] = float(pyo.value(model.co2_cost_elec_expr))

    if hasattr(model, 'co2_cost_total_expr'):
        objective["CO2_total_cost_EUR"] = float(pyo.value(model.co2_cost_total_expr))

    return co2_components
```

**Aufruf**: Nach Zeile 571
```python
objective["P_buy_peak_MW"] = float(pyo.value(model.P_buy_peak)) if hasattr(model, "P_buy_peak") else 0.0

# ✅ NEU: Extrahiere CO₂-Kosten
co2_components = _extract_co2_costs_from_model(model, meta, objective)
```

---

#### 2.2 Export zu summary

**Position**: Ersetze/Erweitere Generator-Sections (Zeile 755-799)

**In Generator-Loop** (nach Zeile 784):
```python
# Füge CO₂-Informationen hinzu
if co2_components and comp in co2_components:
    co2_info = co2_components[comp]
    entry["CO2_heat_kg"] = co2_info['CO2_heat_kg']
    entry["CO2_elec_kg"] = co2_info['CO2_elec_kg']
    entry["CO2_total_kg"] = co2_info['CO2_total_kg']
    entry["CO2_heat_cost_EUR"] = co2_info['CO2_heat_cost_EUR']
    entry["CO2_elec_cost_EUR"] = co2_info['CO2_elec_cost_EUR']
    entry["CO2_total_cost_EUR"] = co2_info['CO2_total_cost_EUR']
```

**Analog für WP** (nach Zeile 752):
```python
# Füge CO₂-Informationen hinzu
if co2_components and hp_id in co2_components:
    co2_info = co2_components[hp_id]
    hp_section["CO2_elec_kg"] = co2_info['CO2_elec_kg']
    hp_section["CO2_elec_cost_EUR"] = co2_info['CO2_elec_cost_EUR']
```

**Analog für P2H** (nach Zeile 808):
```python
# Füge CO₂-Informationen hinzu
if co2_components and "P2H" in co2_components:
    co2_info = co2_components["P2H"]
    p2h_section["CO2_elec_kg"] = co2_info['CO2_elec_kg']
    p2h_section["CO2_elec_cost_EUR"] = co2_info['CO2_elec_cost_EUR']
```

---

### 3. Dashboard-Anpassungen (`energis/io/dashboard.py`)

#### 3.1 Neue KPI-Karten

**Position**: Ersetze Zeile 1729-1736

```python
# ALT (4 Karten): Gesamt, Grid, Fuel, Kosten
# NEU (6 Karten): Gesamt, Wärme, Strom, Kosten Wärme, Kosten Strom, Kosten Gesamt

result = self.primary_result

# Extrahiere CO₂-Kosten
co2_heat_cost = result.costs.get('CO2_heat_total_cost_EUR', 0) if hasattr(result, 'costs') else 0
co2_elec_cost = result.costs.get('CO2_elec_total_cost_EUR', 0) if hasattr(result, 'costs') else 0
co2_total_cost = result.costs.get('CO2_total_cost_EUR', self.co2_cost_eur) if hasattr(result, 'costs') else self.co2_cost_eur

co2_kpis = pn.GridBox(
    self._create_kpi_card("Gesamt-CO₂-Äquivalente", f"{self.total_co2_t:,.1f} t", "warning"),
    self._create_kpi_card("CO₂-Äq. Wärmeerzeugung", f"{self.fuel_co2_t:,.1f} t", "danger"),
    self._create_kpi_card("CO₂-Äq. Strombezug", f"{self.grid_co2_t:,.1f} t", "info"),
    self._create_kpi_card("CO₂-Kosten Wärme", f"{co2_heat_cost:,.0f} €", "danger"),
    self._create_kpi_card("CO₂-Kosten Strom", f"{co2_elec_cost:,.0f} €", "info"),
    self._create_kpi_card("CO₂-Kosten Gesamt", f"{co2_total_cost:,.0f} €", "primary"),
    ncols=3,  # 2 Zeilen à 3 Karten
    sizing_mode='stretch_width'
)
```

---

#### 3.2 Neue Tabelle: CO₂-Kosten pro Komponente

**Position**: Neue Funktion nach `_create_emissions_table()`

```python
def _create_co2_costs_table(self):
    """Create detailed CO₂ costs table per component (Heat/Elec split)."""

    result = self.primary_result
    if not hasattr(result, 'costs'):
        return pn.pane.Markdown("*Keine CO₂-Kosten verfügbar*")

    costs = result.costs
    co2_data = []

    # Finde alle CO₂-Kosten-Einträge
    for key, value in costs.items():
        if key.startswith('CO2_') and key.endswith('_total_cost_EUR'):
            # Extrahiere Komponenten-Namen
            comp_name = key.replace('CO2_', '').replace('_total_cost_EUR', '')

            if comp_name in ['heat_total', 'elec_total', 'total']:
                continue  # Überspringen (Summen)

            # Hole Wärme/Strom-Kosten
            heat_cost = costs.get(f'CO2_{comp_name}_heat_cost_EUR', 0)
            elec_cost = costs.get(f'CO2_{comp_name}_elec_cost_EUR', 0)
            total_cost = costs.get(f'CO2_{comp_name}_total_cost_EUR', 0)

            heat_kg = costs.get(f'CO2_{comp_name}_heat_kg', 0) / 1000.0  # kg → t
            elec_kg = costs.get(f'CO2_{comp_name}_elec_kg', 0) / 1000.0
            total_kg = costs.get(f'CO2_{comp_name}_total_kg', 0) / 1000.0

            co2_data.append({
                'Komponente': comp_name,
                'CO2_Wärme_t': heat_kg,
                'CO2_Strom_t': elec_kg,
                'CO2_Gesamt_t': total_kg,
                'Kosten_Wärme_EUR': heat_cost,
                'Kosten_Strom_EUR': elec_cost,
                'Kosten_Gesamt_EUR': total_cost
            })

    # Sortiere nach Gesamt-Kosten
    co2_data = sorted(co2_data, key=lambda x: x['Kosten_Gesamt_EUR'], reverse=True)

    # Summen-Zeile
    total_heat_cost = sum(d['Kosten_Wärme_EUR'] for d in co2_data)
    total_elec_cost = sum(d['Kosten_Strom_EUR'] for d in co2_data)
    total_total_cost = sum(d['Kosten_Gesamt_EUR'] for d in co2_data)

    co2_data.append({
        'Komponente': '═══ SUMME ═══',
        'CO2_Wärme_t': sum(d['CO2_Wärme_t'] for d in co2_data[:-1]),
        'CO2_Strom_t': sum(d['CO2_Strom_t'] for d in co2_data[:-1]),
        'CO2_Gesamt_t': sum(d['CO2_Gesamt_t'] for d in co2_data[:-1]),
        'Kosten_Wärme_EUR': total_heat_cost,
        'Kosten_Strom_EUR': total_elec_cost,
        'Kosten_Gesamt_EUR': total_total_cost
    })

    if not co2_data:
        return pn.pane.Markdown("*Keine CO₂-Kosten verfügbar*")

    df = pd.DataFrame(co2_data)

    table = pn.widgets.Tabulator(
        df,
        sizing_mode='stretch_width',
        theme='modern',
        show_index=False,
        formatters={
            'CO2_Wärme_t': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 2, 'symbol': ' t'},
            'CO2_Strom_t': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 2, 'symbol': ' t'},
            'CO2_Gesamt_t': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 2, 'symbol': ' t'},
            'Kosten_Wärme_EUR': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 0, 'symbol': ' €'},
            'Kosten_Strom_EUR': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 0, 'symbol': ' €'},
            'Kosten_Gesamt_EUR': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 0, 'symbol': ' €'}
        }
    )

    return table
```

---

#### 3.3 Integration in Emissions-Tab

**Position**: Ersetze/Erweitere `_create_emissions_tab()` (Zeile 1856-1857)

```python
# ALT:
pn.pane.Markdown("### Emissionen nach Quelle (Gesamtzeitraum)"),
emissions_table,

# NEU:
pn.pane.Markdown("### Emissionen nach Quelle (Gesamtzeitraum)"),
emissions_table,
pn.layout.Divider(),
pn.pane.Markdown("### CO₂-Kosten pro Komponente (Wärme/Strom-Aufteilung)"),
self._create_co2_costs_table(),
```

---

## ZUSAMMENFASSUNG: ÄNDERUNGEN

### Pyomo-Modell (`energis/models/system_builder.py`)

| Zeile | Änderung | Beschreibung |
|-------|----------|--------------|
| 365+ | **NEU** | Listen für CO₂-Kosten (Wärme/Strom) |
| 367-550 | **Erweitert** | WP: CO₂-Kosten berechnen |
| 694-712 | **Erweitert** | P2H: CO₂-Kosten berechnen |
| 714-741 | **Ersetzt** | Generatoren: CO₂-Aufteilung Wärme/Strom |
| 791-793 | **Ersetzt** | CO₂-Summen aus Komponenten |

### Export (`energis/run/rolling_horizon.py`)

| Zeile | Änderung | Beschreibung |
|-------|----------|--------------|
| 570+ | **NEU** | Funktion `_extract_co2_costs_from_model()` |
| 752 | **Erweitert** | WP-summary: CO₂-Kosten |
| 784 | **Erweitert** | Generator-summary: CO₂-Kosten |
| 808 | **Erweitert** | P2H-summary: CO₂-Kosten |

### Dashboard (`energis/io/dashboard.py`)

| Zeile | Änderung | Beschreibung |
|-------|----------|--------------|
| 1729-1736 | **Ersetzt** | 6 KPI-Karten (inkl. Wärme/Strom-Kosten) |
| 1856+ | **NEU** | Tabelle CO₂-Kosten pro Komponente |
| 1856 | **Erweitert** | Integration in Emissions-Tab |

---

## VALIDIERUNG

### Test-Cases

1. **Reiner Wärmeerzeuger (z.B. HWS)**:
   - CO₂_heat_kg > 0
   - CO₂_elec_kg = 0
   - Kosten nur bei Wärme

2. **CHP (z.B. HKW mit th_eff=0.743, el_eff=0.177)**:
   - CO₂_heat_kg = 80.8% von total
   - CO₂_elec_kg = 19.2% von total
   - Summe = 100%

3. **Wärmepumpe (z.B. HP1)**:
   - CO₂_heat_kg = 0
   - CO₂_elec_kg > 0 (aus Grid)
   - Kosten nur bei Strom

4. **P2H**:
   - Analog zu WP
   - CO₂ aus Stromverbrauch

5. **Gesamt-Summen**:
   - CO2_heat_total_cost_EUR = Summe aller heat_cost
   - CO2_elec_total_cost_EUR = Summe aller elec_cost
   - CO2_total_cost_EUR = heat + elec

---

## OFFENE FRAGEN

### 1. KWK CO₂-Aufteilung: Welche Methode?

**Option A: Energetische Aufteilung** (vorgeschlagen)
```
heat_fraction = th_eff / (th_eff + el_eff)
```
- Einfach
- Nachvollziehbar
- Unterschätzt Strom (exergetisch)

**Option B: Exergetische Aufteilung**
```
heat_fraction = th_eff / (th_eff + el_eff × 2.5)  # Strom höher gewichtet
```
- Physikalisch korrekter
- Komplizierter

**Option C: Stromgutschrift**
```
co2_heat = co2_total - (elec_output × grid_co2_factor)
```
- Anerkennt vermiedene Grid-Emissionen
- Abhängig vom Grid-Mix

**Empfehlung**: Option A (energetisch) → **User-Entscheidung nötig**

---

### 2. Stromverkauf: CO₂-Gutschrift?

Wenn BHKW Strom ins Netz einspeist (`P_sell`):
- Soll das CO₂-Gutschrift geben?
- Oder neutral behandeln?

**Vorschlag**: Neutral (keine Gutschrift) → vereinfacht Rechnung

---

## NEXT STEPS

1. ✅ **Plan erstellt**
2. ⏳ **User-Fragen klären**:
   - KWK-Aufteilungs-Methode?
   - Stromverkauf-Behandlung?
3. ⏳ **Implementierung**:
   - Phase 1: Pyomo-Modell
   - Phase 2: Export
   - Phase 3: Dashboard
4. ⏳ **Testing & Validierung**

---

**Geschätzter Aufwand**: 6-8 Stunden
**Komplexität**: Mittel-Hoch (Pyomo-Modell-Änderungen)
