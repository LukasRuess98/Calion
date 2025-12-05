# Dashboard-Anpassungen für CO₂-Kosten-Visualisierung

## STATUS

✅ **Fertig**: Pyomo-Modell + Export
⏳ **Ausstehend**: Dashboard-Visualisierung

---

## DASHBOARD-ÄNDERUNGEN (TODO)

### Datei: `energis/io/dashboard.py`

---

### 1. KPI-Karten erweitern (Zeile ~1729-1736)

**Aktuell**: 4 Karten
**Neu**: 6 Karten (mit Wärme/Strom-Kosten)

```python
# ERSETZE Zeile 1729-1736:
result = self.primary_result

# Extrahiere CO₂-Kosten (Wärme/Strom)
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

### 2. Neue Tabelle: CO₂-Kosten pro Komponente

**Position**: Neue Funktion nach `_create_emissions_table()` (nach Zeile 1995)

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
    if co2_data:
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

### 3. Integration in Emissions-Tab

**Position**: Zeile ~1856 in `_create_emissions_tab()`

**ERSETZE**:
```python
pn.pane.Markdown("### Emissionen nach Quelle (Gesamtzeitraum)"),
emissions_table,
pn.layout.Divider(),
pn.pane.Markdown("### CO₂-Äquivalente Zeitverlauf"),
```

**MIT**:
```python
pn.pane.Markdown("### Emissionen nach Quelle (Gesamtzeitraum)"),
emissions_table,
pn.layout.Divider(),
pn.pane.Markdown("### CO₂-Kosten pro Komponente (Wärme/Strom-Aufteilung)"),
self._create_co2_costs_table(),
pn.layout.Divider(),
pn.pane.Markdown("### CO₂-Äquivalente Zeitverlauf"),
```

---

## VALIDIERUNG

Nach den Dashboard-Änderungen solltest du sehen:

1. **6 KPI-Karten**:
   - Gesamt-CO₂-Äquivalente [t]
   - CO₂-Äq. Wärmeerzeugung [t]
   - CO₂-Äq. Strombezug [t]
   - CO₂-Kosten Wärme [EUR]
   - CO₂-Kosten Strom [EUR]
   - CO₂-Kosten Gesamt [EUR]

2. **Neue Tabelle "CO₂-Kosten pro Komponente"**:
   - Spalten: Komponente, CO2_Wärme_t, CO2_Strom_t, CO2_Gesamt_t, Kosten_Wärme_EUR, Kosten_Strom_EUR, Kosten_Gesamt_EUR
   - Sortiert nach Gesamt-Kosten (höchste zuerst)
   - Summen-Zeile am Ende

3. **Für jede Komponente**:
   - Reiner Wärmeerzeuger (z.B. HWS): CO2_Wärme > 0, CO2_Strom = 0
   - CHP (z.B. HKW): CO2_Wärme ~80%, CO2_Strom ~20% (je nach Wirkungsgrad)
   - WP (z.B. HP1): CO2_Wärme = 0, CO2_Strom > 0
   - P2H: CO2_Wärme = 0, CO2_Strom > 0

---

## BEISPIEL: KWK-Aufteilung

**HKW (th_eff=0.743, el_eff=0.177)**:
- Gesamt-Brennstoff: 100 MWh Gas → 20.16 t CO₂
- Wärme-Anteil: 0.743 / 0.92 = 80.8% → 16.29 t CO₂
- Strom-Anteil: 0.177 / 0.92 = 19.2% → 3.87 t CO₂
- Bei 100 EUR/t CO₂:
  - Wärme-Kosten: 1,629 EUR
  - Strom-Kosten: 387 EUR
  - Gesamt: 2,016 EUR

---

## NÄCHSTE SCHRITTE

1. ✅ Pyomo + Export sind fertig und committed
2. ⏳ Dashboard-Änderungen implementieren (oben beschrieben)
3. ⏳ Testen mit einem Szenario
4. ⏳ Commit + Push

**Geschätzter Aufwand für Dashboard**: ~30 Minuten
