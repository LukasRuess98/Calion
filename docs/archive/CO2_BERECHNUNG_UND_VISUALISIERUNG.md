# CO₂-Berechnung und Visualisierung im EnerGIS Framework

## 1. CO₂-BERECHNUNG (Backend)

### 1.1 Grid CO₂ (Strombezug - INDIREKTE Emissionen)

**Quelle**: `energis/run/rolling_horizon.py:608-610, 634`

**Formel pro Zeitschritt**:
```python
Grid_CO2_t_per_step[i] = P_buy_MW[i] × grid_co2_kg_MWh[i] × dt_h / 1000.0
```

**Komponenten**:
- `P_buy_MW[i]` = Strombezug in MW zum Zeitpunkt i (aus Optimierung)
- `grid_co2_kg_MWh[i]` = Grid-Emissionsfaktor in kg CO₂/MWh zum Zeitpunkt i (aus Input-Datei)
- `dt_h` = Zeitschrittdauer in Stunden (z.B. 1h)
- `/1000.0` = Umrechnung von kg → Tonnen

**Gesamt (aggregiert)**:
```python
grid_co2_t = sum(Grid_CO2_t_per_step[i] for i in range(n))
```

**Datenquelle Grid-Emissionsfaktor**:
- Kommt aus Input-Tabelle: `table.data.get("grid_co2_kg_MWh", [0.0] * n)`
- Typische Werte: ~300-500 kg CO₂/MWh (abhängig von Strommix)
- Variiert zeitlich (höher bei Kohle/Gas, niedriger bei Wind/Solar)

---

### 1.2 Fuel CO₂ (Brennstoffe - DIREKTE Emissionen)

**Quelle**: `energis/run/rolling_horizon.py:788-799`

**Formel pro Generator und Zeitschritt**:
```python
CO2_{generator}_t_per_step[i] = fuel_MW[i] × dt_h × fuel_emission_kg_MWh / 1000.0
```

**Komponenten**:
- `fuel_MW[i]` = Brennstoffleistung in MW zum Zeitpunkt i (aus Optimierung)
- `dt_h` = Zeitschrittdauer in Stunden
- `fuel_emission_kg_MWh` = Emissionsfaktor des Brennstoffs in kg CO₂/MWh Brennstoff
- `/1000.0` = Umrechnung von kg → Tonnen

**Emissionsfaktoren** (aus `configs/tech_catalog.yaml`):
- **Gas**: 201.6 kg CO₂/MWh Brennstoff
- **Biomasse**: 0.0 kg CO₂/MWh (klimaneutral)
- **Abfall**: 0.0 kg CO₂/MWh (klimaneutral)

**Gesamt Fuel CO₂**:
```python
Fuel_CO2_emissions_t_per_step[i] = sum(CO2_{gen}_t_per_step[i] for gen in generators)
```

**Aggregiert über alle Generatoren**:
```python
fuel_co2_t = sum(Fuel_CO2_emissions_t_per_step[i] for i in range(n))
```

---

### 1.3 Gesamt CO₂

**Formel**:
```python
Total_CO2_t_per_step[i] = Grid_CO2_t_per_step[i] + Fuel_CO2_emissions_t_per_step[i]
total_co2_t = grid_co2_t + fuel_co2_t
```

---

## 2. WAS WIRD EXPORTIERT

### 2.1 In `result.series` (Zeitreihen für CSV-Export und Dashboard)

**Grid CO₂**:
- ✅ `grid_co2_kg_MWh` - Emissionsfaktor des Stromnetzes [kg/MWh] (Zeitreihe)
- ✅ `Grid_CO2_emissions_t_per_step` - Grid CO₂-Emissionen [t] (Zeitreihe)

**Fuel CO₂**:
- ✅ `Fuel_CO2_emissions_t_per_step` - Gesamt Fuel CO₂ [t] (Zeitreihe, aggregiert über alle Erzeuger)
- ✅ `CO2_{generator_name}_t_per_step` - CO₂ pro Generator [t] (Zeitreihe, individuell)
  - Beispiel: `CO2_HKW_t_per_step`, `CO2_BMHKW_t_per_step`, `CO2_HWS_t_per_step`

**Gesamt CO₂**:
- ✅ `Total_CO2_emissions_t_per_step` - Gesamt CO₂ [t] (Zeitreihe)

### 2.2 In `result.summary` (Aggregierte Werte)

**Grid**:
- ❓ `summary['grid']['Grid_CO2_emissions_t']` - Gesamt Grid CO₂ [t]
- ❓ `summary['grid']['Total_CO2_emissions_t']` - Gesamt CO₂ [t]

**Problem**: Unsicher ob diese Felder korrekt befüllt werden!

### 2.3 In `result.costs` (Kosten)

- ✅ `objective.CO2_cost_EUR` - CO₂-Kosten in EUR
- ❓ `Fuel_emissions_t` - Gesamt Fuel-Emissionen [t]

### 2.4 Pro Generator in `result.summary['generators']`

Für jeden Generator:
- ✅ `Fuel_emissions_t` - Emissionen dieses Generators [t] (aggregiert)

---

## 3. WAS WIRD IM DASHBOARD VISUALISIERT

**Quelle**: `energis/io/dashboard.py`

### 3.1 KPI-Karten (Oben) - Lines 1729-1736

✅ **4 Karten**:
1. "Gesamt-CO₂-Äquivalente" [t] → `total_co2_t`
2. "CO₂-Äq. aus Strombezug" [t] → `grid_co2_t`
3. "CO₂-Äq. aus Wärmeerzeugung" [t] → `fuel_co2_t`
4. "CO₂-Kosten" [EUR] → `co2_cost_eur`

**Datenaggregation** (Lines 471-496):
```python
# Primär: Aus Zeitreihen aggregieren
grid_co2_t = df['Grid_CO2_emissions_t_per_step'].sum()
fuel_co2_t = df['Fuel_CO2_emissions_t_per_step'].sum()
total_co2_t = df['Total_CO2_emissions_t_per_step'].sum() OR grid_co2_t + fuel_co2_t

# Sekundär: Fallback aus summary/costs (falls Zeitreihen fehlen)
```

### 3.2 Zusammenfassungs-Markdown-Tabelle - Lines 1747-1764

✅ **7 Kennzahlen**:
- Gesamt-CO₂-Äquivalente [t]
- CO₂-Äq. aus Strombezug [t] + (Prozent)
- CO₂-Äq. aus Wärmeerzeugung [t] + (Prozent)
- **CO₂-Intensität [kg/MWh_th]** = total_co2_t × 1000 / total_demand_MWh
- CO₂-Kosten [EUR] + (Prozent der Gesamtkosten)
- Wärmebereitstellung [MWh]

### 3.3 Pie Chart (Breakdown) - Lines 1865-1903

✅ **2 Kategorien**:
- Strombezug (Grid) [t]
- Wärmeerzeugung (Fuel) [t]

**Problem**: Zeigt nur 2 Kategorien, nicht einzelne Erzeuger!

### 3.4 Tabelle "Emissionen nach Quelle" - Lines 1928-1995

✅ **Einzelne Quellen** (sortiert nach Menge):
- Strombezug [t] (Kategorie: Indirekt)
- HKW [t] (Kategorie: Direkt)
- BMHKW [t] (Kategorie: Direkt)
- HWS [t] (Kategorie: Direkt)
- ... (alle Erzeuger mit CO₂ > 0.001t)
- GESAMT [t]

**Spalten**:
- Quelle (Name)
- CO2eq_t (Menge in Tonnen)
- Anteil_% (Prozentbalken)
- Kategorie (Indirekt/Direkt/Summe)

### 3.5 Zeitreihen-Plot - Lines 1977-2078

✅ **Stacked Area Chart**:
- X-Achse: Zeit (timestamp)
- Y-Achse: CO₂-Äquivalente [t/h]
- Eine Linie pro ausgewählter Quelle (via Multiselect)

**Multiselect-Widget** (Lines 1787-1792):
- "🏭 CO₂-Quellen"
- Optionen: Strombezug (Grid) + alle Erzeuger mit CO₂-Daten
- Default: Erste 5 Quellen

**Interaktive Filter**:
- Zeitbereich-Slider (Stunden)
- Quick-Filter: Erste Woche, Winter-Tag, Sommer-Tag, Ganzes Jahr

**Plot-Titel**:
- Zeitraum: Xh | Summe: Y.YY t CO₂eq | Quellen: Z

---

## 4. WAS KÖNNTE NOCH VISUALISIERT WERDEN (ABER WIRD NOCH NICHT)

### 4.1 Detaillierte Breakdown-Analysen

❌ **Pie Chart mit einzelnen Erzeugern** (statt nur Grid vs. Fuel)
- Aktuell: Nur 2 Kategorien (Strombezug, Wärmeerzeugung)
- Potenzial: Strombezug, HKW, BMHKW, HWS, etc. einzeln

❌ **Brennstoff-Typ Breakdown**
- Gas-Emissionen (alle Gaskessel zusammen)
- Biomasse-Emissionen
- Abfall-Emissionen
- Könnte aus `fuel_bus` Information aggregiert werden

❌ **CO₂-Intensität pro Technologie** [kg CO₂/MWh Wärme]
- HKW: X kg/MWh_th
- WP: Y kg/MWh_th
- BMHKW: Z kg/MWh_th
- Formel: `generator_co2_t × 1000 / generator_heat_MWh`

### 4.2 Zeitbasierte Analysen

❌ **Monatliche/Quartalsweise CO₂-Bilanz**
- Balkendiagramm: CO₂ pro Monat
- Aufteilung: Grid vs. Fuel

❌ **CO₂-Lastprofil** (analog zur Jahresdauerlinie)
- Sortierte CO₂-Intensität über Zeitreihe
- Zeigt: Wie oft treten hohe Emissionen auf?

❌ **CO₂-Emissionen vs. Wärmebedarf (Scatter Plot)**
- X-Achse: Wärmebedarf [MW]
- Y-Achse: CO₂-Emissionen [t/h]
- Zeigt Korrelation zwischen Bedarf und Emissionen

### 4.3 Vergleichsmetriken

❌ **CO₂-Vermeidung vs. Referenz**
- Referenz: z.B. reiner Gaskessel
- Ersparnis: X t CO₂eq (Y% weniger)
- CO₂-Vermeidungskosten: EUR/t CO₂

❌ **Grid vs. Fuel Verhältnis über Zeit**
- Zeitreihe: Anteil Grid-CO₂ vs. Fuel-CO₂
- Zeigt: Wie variiert der Mix?

❌ **Marginale CO₂-Intensität**
- Wie viel zusätzliches CO₂ entsteht pro zusätzlicher MWh Wärme?
- Wichtig für Demand-Response-Entscheidungen

### 4.4 Optimierungs-Kontext

❌ **CO₂-Kosten Breakdown**
- Grid CO₂-Kosten [EUR]
- Fuel CO₂-Kosten [EUR]
- Spezifische CO₂-Kosten [EUR/t]

❌ **Shadow Prices / Sensitivitätsanalyse**
- Wie ändern sich Emissionen bei CO₂-Preis +10%?

❌ **Fuel-CO₂ pro Generator als Zeitreihe mit Details**
- Aktuell: Exportiert, aber nicht prominent visualisiert
- Könnte eigenen Sub-Plot haben

### 4.5 Exportierte Daten die nicht visualisiert werden

❌ **grid_co2_kg_MWh Zeitreihe**
- Wird exportiert, aber nicht als separate Zeitreihe geplottet
- Könnte zeigen: Wann ist Grid besonders sauber/dreckig?

❌ **Spezifischer Brennstoffverbrauch pro Generator** [MWh Fuel/MWh Heat]
- Aus `fuel_mwh / heat_mwh`
- Zusammen mit CO₂-Intensität → Efficiency-Emissions-Tradeoff

❌ **CO₂ pro Betriebsstunde** [kg CO₂/h Betrieb]
- Zeigt Emissionsrate wenn Generator läuft

### 4.6 Multi-Szenario-Vergleiche

❌ **CO₂-Vergleich PF vs. RH**
- Wenn beide Workflows vorhanden
- Zeigt: Optimale vs. operative Emissionen

❌ **CO₂-Entwicklung über Iterationen** (bei MPC)
- Wie ändert sich CO₂-Prognose über rolling horizon?

### 4.7 Geografisch/Netzwerkorientiert

❌ **Sankey-Diagramm mit CO₂-Flows**
- Aktuell: Nur Energie-Sankey
- Potenzial: CO₂-Fluss von Quellen zu Senken

---

## 5. MÖGLICHE BERECHNUNGSFEHLER

### 5.1 Potenzielle Inkonsistenzen

⚠️ **Problem 1: summary vs. series Aggregation**
- Dashboard aggregiert aus `series` (Zeitreihen)
- `result.summary` und `result.costs` werden möglicherweise anders berechnet
- Könnte zu Abweichungen führen wenn beide Wege nicht synchron sind

⚠️ **Problem 2: Wärmepumpen-CO₂**
- Wärmepumpen verursachen indirekte Emissionen durch Strombezug
- Werden diese korrekt in `P_buy_MW` erfasst oder separat behandelt?

⚠️ **Problem 3: Eigenstromerzeugung (aus KWK)**
- Wenn BHKW Strom erzeugt: Wird das CO₂ korrekt zugeordnet?
- Brennstoff → Wärme + Strom → Wie wird CO₂ aufgeteilt?

⚠️ **Problem 4: Stromverkauf**
- Wenn Strom ins Netz eingespeist wird (`P_sell_MW`)
- Sollten diese "negativen Emissionen" berücksichtigt werden?
- Aktuell: Nur `P_buy` verwendet, nicht `P_buy - P_sell`

⚠️ **Problem 5: TES (Thermal Energy Storage)**
- Speicherverluste: Werden diese berücksichtigt?
- Zeitverschiebung: CO₂ bei Beladung vs. Entladung

### 5.2 Validierungsvorschläge

✅ **Check 1: Energiebilanz**
```python
# Grid CO₂ Plausibilität
energy_bought_MWh = sum(P_buy_MW) * dt_h
expected_grid_co2_t = energy_bought_MWh * avg_grid_co2_factor / 1000
assert abs(grid_co2_t - expected_grid_co2_t) < 0.01
```

✅ **Check 2: Fuel CO₂ Plausibilität**
```python
# Für jeden Generator
fuel_consumed_MWh = sum(fuel_MW) * dt_h
expected_co2_t = fuel_consumed_MWh * fuel_emission_factor / 1000
assert abs(generator_co2_t - expected_co2_t) < 0.01
```

✅ **Check 3: Zeitreihen vs. Aggregat**
```python
# Konsistenz prüfen
assert abs(sum(Grid_CO2_t_per_step) - grid_co2_t) < 0.01
assert abs(sum(Fuel_CO2_t_per_step) - fuel_co2_t) < 0.01
```

---

## 6. EMPFOHLENE NÄCHSTE SCHRITTE

### 6.1 Kurzfristig (Bugs fixen)

1. ✅ **Validiere KPI-Aggregation**: Prüfe ob KPI-Karten korrekte Werte zeigen
2. ⚠️ **Prüfe WP-CO₂**: Sind Wärmepumpen-Emissionen korrekt in Grid-CO₂ enthalten?
3. ⚠️ **Prüfe KWK-CO₂**: Wird Brennstoff-CO₂ korrekt zwischen Wärme/Strom aufgeteilt?
4. ⚠️ **Stromverkauf**: Sollte `P_sell` CO₂-Gutschrift geben?

### 6.2 Mittelfristig (Features)

1. 📊 **Detaillierter Pie Chart**: Einzelne Erzeuger statt nur Grid vs. Fuel
2. 📊 **Monatlicher CO₂-Breakdown**: Balkendiagramm
3. 📊 **CO₂-Intensität pro Technologie**: Zusätzliche Tabelle
4. 📊 **Grid-Emissionsfaktor als Zeitreihe**: Zeige wann Grid sauber/dreckig ist

### 6.3 Langfristig (Optimierung)

1. 🔧 **CO₂-Vermeidungsanalyse**: Vergleich mit Referenzszenario
2. 🔧 **Sensitivitätsanalyse**: CO₂-Preis-Variation
3. 🔧 **Multi-Szenario-Dashboard**: PF vs. RH CO₂-Vergleich
4. 🔧 **CO₂-Sankey**: Emissionsflüsse visualisieren

---

## 7. ZUSAMMENFASSUNG: WAS FUNKTIONIERT / WAS FEHLT

### ✅ Funktioniert bereits

- Grid CO₂-Berechnung (inkl. Zeitreihe)
- Fuel CO₂-Berechnung pro Generator (inkl. Zeitreihe)
- KPI-Karten (4 Metriken)
- Zeitreihen-Plot mit Multiselect
- Tabelle mit einzelnen Quellen
- CO₂-Kosten

### ⚠️ Zu überprüfen

- Korrektheit der KPI-Werte (0t Problem)
- Wärmepumpen-CO₂-Zuordnung
- KWK-CO₂-Aufteilung (Wärme vs. Strom)
- Stromverkauf (negative Emissionen?)

### ❌ Fehlt noch

- Detaillierter Pie Chart (pro Erzeuger)
- Brennstoff-Typ-Breakdown
- CO₂-Intensität pro Technologie
- Monatliche/Zeitliche Aggregationen
- Grid-Emissionsfaktor-Zeitreihe
- CO₂-Vermeidungsanalyse
- Multi-Szenario-CO₂-Vergleich
- CO₂-Sankey-Diagramm

---

**Stand**: 2025-12-04
**Framework**: EnerGIS Planing-Framework-for-Heat
**Dateien**: `energis/run/rolling_horizon.py`, `energis/io/dashboard.py`, `configs/tech_catalog.yaml`
