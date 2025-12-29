# Plan: Korrekte CO₂-Zuordnung aus Pyomo-Modell

## PROBLEM-ANALYSE

### Was funktioniert aktuell:
✅ Generatoren werden aus Config gelesen (Zeile 298-322)
✅ Pyomo-Variablen werden extrahiert (Zeile 559-564)
✅ CO₂ wird pro Generator berechnet (Zeile 788-799)

### Was möglicherweise NICHT funktioniert:
⚠️ **Alle Aggregate in Emissionsübersicht anzeigen, auch wenn 9 vorhanden sind**
- Dashboard zeigt nur die ersten 5 Quellen im Multiselect (Zeile 1790)
- Wenn ein Generator kein CO₂ erzeugt (z.B. Biomasse/Abfall), könnte er fehlen
- Wenn ein Generator nicht läuft (fuel_MW = 0 für alle Zeitschritte), ist CO₂ = 0

⚠️ **Wärmepumpen-CO₂**
- WP verbrauchen Strom → indirekte Emissionen
- Wird in `P_buy_MW` erfasst, aber nicht separat zugeordnet
- Dashboard zeigt nur "Strombezug (Grid)" - nicht WP-spezifisch

⚠️ **P2H (Power-to-Heat) CO₂**
- Analog zu Wärmepumpen: Stromverbrauch
- Wird in `P_buy_MW` erfasst, aber nicht separat zugeordnet

⚠️ **KWK (Kraft-Wärme-Kopplung) CO₂-Aufteilung**
- Generator erzeugt Wärme UND Strom aus demselben Brennstoff
- Aktuell: Gesamtes Brennstoff-CO₂ wird dem Generator zugeordnet
- Problem: Strom-CO₂ müsste eigentlich abgezogen werden (oder explizit aufgeteilt)

---

## DATENFLUSS: VON PYOMO ZU DASHBOARD

### 1. Pyomo-Modell (energis/models/)

**Thermische Generatoren** (`thermal_gen.py`):
```python
# Pyomo-Variablen pro Generator:
{comp}_Qth[t]   # Wärmeleistung [MW]
{comp}_fuel[t]  # Brennstoffleistung [MW]
{comp}_Pel[t]   # Elektrische Leistung [MW] (nur wenn CHP)
```

**Wärmepumpen** (`heat_pump.py`):
```python
{hp_id}_Q_th[t]   # Wärmeleistung [MW]
{hp_id}_P_el[t]   # Stromverbrauch [MW]
```

**P2H** (`p2h.py`):
```python
P2H_Qth[t]  # Wärmeleistung [MW]
P2H_Pel[t]  # Stromverbrauch [MW]
```

**Grid**:
```python
P_buy[t]   # Strombezug [MW]
P_sell[t]  # Stromeinspeisung [MW]
```

---

### 2. Extraktion aus Pyomo (`rolling_horizon.py`)

#### Zeile 298-322: Config → meta["generators"]
```python
for key, par in syscfg.get("generators", {}).items():
    if not par.get("enabled", False):
        continue  # ⚠️ Generator wird übersprungen wenn disabled!

    meta["generators"].append({
        "key": key,              # z.B. "hkw"
        "name": key.upper(),     # z.B. "HKW"
        "cap_th": ...,
        "fuel_bus": "gas",       # ⚠️ Wichtig für CO₂-Faktor!
        "fuel_price": ...,
        "fuel_emission": 201.6,  # kg CO₂/MWh Brennstoff
        "has_el": True/False     # ⚠️ Ist es ein BHKW?
    })
```

#### Zeile 559-564: Pyomo → series
```python
for gen in meta["generators"]:
    comp = gen["name"]  # z.B. "HKW"

    # Extrahiere aus Pyomo-Modell:
    _extract(model.HKW_Qth,  "HKW_Q_th_MW")   # Wärme
    _extract(model.HKW_fuel, "HKW_fuel_MW")   # Brennstoff
    _extract(model.HKW_Pel,  "HKW_Pel_MW")    # Strom (wenn CHP)
```

**Funktion `_extract()`** (Zeile 520-524):
```python
def _extract(pyomo_var, series_name):
    if pyomo_var is not None:
        series[series_name] = _extract_pyomo_series(
            pyomo_var, times, series_name
        )
```

**`_extract_pyomo_series()`** (Zeile 1036-1070):
- Liest `pyo.value(var[t])` für alle Zeitschritte
- Prüft auf None, NaN, Inf
- Setzt kleine Werte < 1e-9 auf 0.0
- Gibt `List[float]` zurück

---

### 3. CO₂-Berechnung (`rolling_horizon.py`)

#### Zeile 608-610: Grid CO₂
```python
series["Grid_CO2_emissions_t_per_step"] = [
    P_buy_MW[i] * grid_co2_kg_MWh[i] * dt_h / 1000.0
    for i in range(n)
]
```
- `P_buy_MW[i]` enthält **gesamten** Strombezug (inkl. WP + P2H!)
- Keine Unterscheidung welche Komponente den Strom verbraucht

#### Zeile 788-799: Fuel CO₂ pro Generator
```python
for gen in meta["generators"]:
    comp = gen["name"]  # z.B. "HKW"
    fuel_series = series[f"{comp}_fuel_MW"]  # z.B. series["HKW_fuel_MW"]
    fuel_emission_factor = gen["fuel_emission"]  # z.B. 201.6 kg/MWh

    co2_series_per_gen = []
    for i in range(n):
        fuel_co2_t = fuel_series[i] * dt_h * fuel_emission_factor / 1000.0
        co2_series_per_gen.append(fuel_co2_t)
        series["Fuel_CO2_emissions_t_per_step"][i] += fuel_co2_t

    # Export pro Generator
    series[f"CO2_{comp}_t_per_step"] = co2_series_per_gen
```

**Problem bei KWK**:
- Generator verbrennt Brennstoff → Wärme **UND** Strom
- CO₂ wird komplett dem Generator zugeordnet
- Strom wird ins Netz eingespeist (`P_sell`)
- Eigentlich: CO₂ sollte aufgeteilt werden (Wärme vs. Strom)

---

### 4. Dashboard-Aggregation (`dashboard.py`)

#### Zeile 471-496: KPI-Berechnung
```python
# Aus Zeitreihen aggregieren
grid_co2_t = df['Grid_CO2_emissions_t_per_step'].sum()
fuel_co2_t = df['Fuel_CO2_emissions_t_per_step'].sum()
total_co2_t = grid_co2_t + fuel_co2_t
```

#### Zeile 1772-1792: CO₂-Quellen-Auswahl
```python
co2_source_columns = []

# Grid
if 'Grid_CO2_emissions_t_per_step' in df.columns:
    co2_source_columns.append(('Strombezug (Grid)', 'Grid_CO2_emissions_t_per_step'))

# Einzelne Erzeuger
for col in df.columns:
    if col.startswith('CO2_') and col.endswith('_t_per_step'):
        gen_name = col.replace('CO2_', '').replace('_t_per_step', '')
        co2_source_columns.append((gen_name, col))

# Multiselect
co2_source_selector = pn.widgets.MultiChoice(
    name='🏭 CO₂-Quellen',
    options=[label for label, _ in co2_source_columns],
    value=[label for label, _ in co2_source_columns[:5]],  # ⚠️ Nur erste 5!
    ...
)
```

**Problem**: Default zeigt nur erste 5 Quellen!

#### Zeile 1928-1995: Emissionen-Tabelle
```python
for col in df.columns:
    if col.startswith('CO2_') and col.endswith('_t_per_step'):
        gen_name = col.replace('CO2_', '').replace('_t_per_step', '')
        gen_co2_t = df[col].sum()

        if gen_co2_t > 0.001:  # ⚠️ Nur wenn > 0!
            emissions_data.append({
                'Quelle': gen_name,
                'CO2eq_t': gen_co2_t,
                ...
            })
```

**Problem**: Generatoren mit CO₂ = 0 werden **nicht** angezeigt!

---

## IDENTIFIZIERTE PROBLEME

### Problem 1: Generatoren mit CO₂ = 0 fehlen in Tabelle

**Ursache**: Zeile 1950 in `dashboard.py`
```python
if gen_co2_t > 0.001:  # Nur wenn > 0!
```

**Auswirkung**:
- Biomasse-Generator (ef = 0.0 kg/MWh) wird nicht angezeigt
- Abfall-Generator (ef = 0.0 kg/MWh) wird nicht angezeigt
- Generator der nicht läuft (fuel = 0 für alle t) wird nicht angezeigt

**Lösung**:
- Option A: Immer anzeigen (auch wenn 0)
- Option B: Prüfen ob Generator **aktiv** war (fuel > 0 für mind. 1 Zeitschritt)

---

### Problem 2: Nur erste 5 Quellen im Multiselect

**Ursache**: Zeile 1790 in `dashboard.py`
```python
value=[label for label, _ in co2_source_columns[:5]]  # Default: erste 5
```

**Auswirkung**:
- Bei 9 Generatoren werden nur 5 initial ausgewählt
- Nutzer muss manuell weitere hinzufügen

**Lösung**: Alle Quellen initial auswählen
```python
value=[label for label, _ in co2_source_columns]  # Alle
```

---

### Problem 3: WP/P2H CO₂ nicht separat zugeordnet

**Ursache**:
- WP und P2H verbrauchen Strom → wird zu `P_buy_MW` addiert
- Grid CO₂ wird auf Basis von `P_buy_MW` berechnet
- Keine Information **welche** Komponente den Strom verbraucht

**Auswirkung**:
- Dashboard zeigt nur "Strombezug (Grid)" - nicht WP-spezifisch
- Man kann nicht sehen: "WP1 verursacht X t CO₂"

**Lösung**: Berechne WP-CO₂ separat
```python
# Für jede Wärmepumpe:
for hp in meta["heat_pumps"]:
    hp_id = hp["id"]  # z.B. "HP1"
    pel_series = series[f"{hp_id}_Pel_MW"]  # Stromverbrauch

    co2_series_per_hp = []
    for i in range(n):
        hp_co2_t = pel_series[i] * grid_co2_kg_MWh[i] * dt_h / 1000.0
        co2_series_per_hp.append(hp_co2_t)

    series[f"CO2_{hp_id}_t_per_step"] = co2_series_per_hp

# Analog für P2H
if meta["p2h"]:
    pel_series = series["P2H_Pel_MW"]
    co2_series_p2h = [
        pel_series[i] * grid_co2_kg_MWh[i] * dt_h / 1000.0
        for i in range(n)
    ]
    series["CO2_P2H_t_per_step"] = co2_series_p2h
```

**Anpassung Grid CO₂**:
- Grid CO₂ bleibt gleich (= P_buy gesamt)
- ABER: WP/P2H CO₂ wird zusätzlich separat exportiert
- Dashboard kann dann zeigen: Grid (gesamt) + WP1 + WP2 + P2H + HKW + ...
- Summe: Grid + Fuel (wie bisher)

---

### Problem 4: KWK CO₂-Aufteilung (Wärme vs. Strom)

**Ursache**:
- BHKW erzeugt aus 100 MWh Gas → 74.3 MWh Wärme + 17.7 MWh Strom
- Gesamtes CO₂ (100 × 201.6 / 1000 = 20.16 t) wird dem BHKW zugeordnet
- Stromproduktion wird nicht berücksichtigt

**Frage**: Soll CO₂ aufgeteilt werden?

**Ansätze**:

#### Ansatz A: Keine Aufteilung (Status quo)
- Gesamtes CO₂ → Generator
- Einfach, konservativ
- ✅ Behalten wenn: CO₂-Bilanz des Gesamtsystems im Fokus

#### Ansatz B: Exergetische Aufteilung
```python
# Aufteilung nach Energieinhalt (problematisch weil Strom > Wärme)
fuel_mwh = 100
heat_mwh = 74.3
elec_mwh = 17.7
total_output = heat_mwh + elec_mwh  # = 92 MWh

heat_fraction = heat_mwh / total_output  # = 0.807
elec_fraction = elec_mwh / total_output  # = 0.193

co2_heat = 20.16 * heat_fraction  # = 16.27 t (für Wärme)
co2_elec = 20.16 * elec_fraction  # = 3.89 t (für Strom)
```
- Problem: Unterschätzt Strom (exergetisch wertvoller als Wärme)

#### Ansatz C: Stromgutschrift-Methode
```python
# Brennstoff-CO₂:
co2_total = 20.16 t

# Strom-Gutschrift (vermiedener Grid-Strom):
elec_mwh = 17.7
grid_co2_factor = 400 kg/MWh  # Durchschnitt
co2_credit = elec_mwh * grid_co2_factor / 1000  # = 7.08 t

# Netto-CO₂ (für Wärme):
co2_net_heat = co2_total - co2_credit  # = 13.08 t
```
- ✅ Anerkennt dass Strom Grid-Emissionen vermeidet
- Problem: Abhängig vom Grid-Emissionsfaktor

#### Ansatz D: Finnische Methode (Wärmebonus)
```python
# Alles CO₂ → Strom
# Wärme bekommt 0 CO₂
```
- Für KWK-Förderung
- Nicht für Gesamtbilanz geeignet

**Empfehlung**:
1. **Kurzfristig**: Status quo beibehalten (Ansatz A)
2. **Optional**: Stromgutschrift in separatem Feld anzeigen (Ansatz C)
3. **Dokumentation**: Im Dashboard erklären wie KWK-CO₂ zugeordnet wird

---

## IMPLEMENTIERUNGS-PLAN

### Phase 1: BUGFIXES (Priorität HOCH)

#### Fix 1.1: Alle Generatoren in Tabelle anzeigen (auch mit CO₂ = 0)
**Datei**: `energis/io/dashboard.py:1928-1995`

**Änderung**:
```python
# ALT:
if gen_co2_t > 0.001:  # Nur wenn > 0!
    emissions_data.append({...})

# NEU:
# Prüfe ob Generator überhaupt aktiv war
gen_fuel_col = col.replace('CO2_', '').replace('_t_per_step', '') + '_fuel_MW'
was_active = False
if gen_fuel_col in self.df.columns:
    was_active = self.df[gen_fuel_col].sum() > 0.001

# Zeige Generator wenn:
# - CO₂ > 0 ODER
# - War aktiv (fuel > 0) ODER
# - Immer zeigen (Option für vollständige Übersicht)
if gen_co2_t > 0.001 or was_active:
    emissions_data.append({
        'Quelle': gen_name,
        'CO2eq_t': gen_co2_t,
        'Anteil_%': (gen_co2_t / self.total_co2_t * 100) if self.total_co2_t > 0 else 0,
        'Kategorie': 'Direkt' if gen_co2_t > 0.001 else 'Direkt (klimaneutral)'
    })
```

---

#### Fix 1.2: Alle Quellen initial im Multiselect auswählen
**Datei**: `energis/io/dashboard.py:1790`

**Änderung**:
```python
# ALT:
value=[label for label, _ in co2_source_columns[:5]]  # Nur erste 5

# NEU:
value=[label for label, _ in co2_source_columns]  # Alle auswählen
```

**Alternative** (wenn zu viele Quellen → Performance-Problem):
```python
# Intelligente Auswahl: Top 10 nach CO₂-Menge
co2_amounts = {}
for label, col in co2_source_columns:
    if col in self.df.columns:
        co2_amounts[label] = self.df[col].sum()

# Sortiere nach CO₂-Menge, nimm Top 10
sorted_sources = sorted(co2_amounts.items(), key=lambda x: x[1], reverse=True)
top_sources = [label for label, _ in sorted_sources[:10]]

value=top_sources
```

---

### Phase 2: FEATURES (Priorität MITTEL)

#### Feature 2.1: WP/P2H CO₂ separat exportieren
**Datei**: `energis/run/rolling_horizon.py`
**Position**: Nach Zeile 799 (nach Generator-Loop)

**Neue Funktion**:
```python
# ✅ FEATURE: Berechne CO2 für Wärmepumpen (indirekt über Stromverbrauch)
for hp in meta["heat_pumps"]:
    hp_id = hp["id"]  # z.B. "HP1"
    pel_series = series.get(f"{hp_id}_Pel_MW", [0.0] * n)

    co2_series_per_hp = []
    for i in range(n):
        # WP-CO₂ = Stromverbrauch × Grid-Emissionsfaktor
        hp_co2_t = pel_series[i] * grid_co2_series[i] * dt_h / 1000.0
        co2_series_per_hp.append(hp_co2_t)

    # Export als separate Zeitreihe
    series[f"CO2_{hp_id}_t_per_step"] = co2_series_per_hp

    # Füge zu summary hinzu (optional)
    hp_co2_total_t = sum(co2_series_per_hp)
    if f"heat_pump_{hp_id}" in summary_sections:
        summary_sections[f"heat_pump_{hp_id}"]["CO2_emissions_t"] = float(hp_co2_total_t)

# ✅ FEATURE: Berechne CO2 für P2H (indirekt über Stromverbrauch)
if meta["p2h"]:
    pel_series = series.get("P2H_Pel_MW", [0.0] * n)

    co2_series_p2h = []
    for i in range(n):
        p2h_co2_t = pel_series[i] * grid_co2_series[i] * dt_h / 1000.0
        co2_series_p2h.append(p2h_co2_t)

    series["CO2_P2H_t_per_step"] = co2_series_p2h

    # Füge zu summary hinzu (optional)
    p2h_co2_total_t = sum(co2_series_p2h)
    if "p2h" in summary_sections:
        summary_sections["p2h"]["CO2_emissions_t"] = float(p2h_co2_total_t)
```

**Wichtig**: Grid CO₂ bleibt unverändert (= P_buy gesamt)!

**Dashboard-Anpassung** (automatisch):
- WP/P2H-CO₂ wird automatisch erkannt (Spalte `CO2_HP1_t_per_step`)
- Erscheint in Multiselect als "HP1", "HP2", "P2H"
- Erscheint in Tabelle als separate Zeile

---

#### Feature 2.2: KWK-CO₂-Aufteilung (optional)
**Datei**: `energis/run/rolling_horizon.py`
**Position**: In Generator-Loop (Zeile 788-799)

**Erweiterung**:
```python
for gen in meta["generators"]:
    comp = gen["name"]
    fuel_series = series[f"{comp}_fuel_MW"]
    fuel_emission_factor = gen["fuel_emission"]
    has_el = gen["has_el"]

    co2_series_per_gen = []
    co2_heat_series = []  # NEU: Nur Wärme-Anteil
    co2_elec_credit_series = []  # NEU: Strom-Gutschrift

    for i in range(n):
        # Gesamt-CO₂ aus Brennstoff
        fuel_co2_t = fuel_series[i] * dt_h * fuel_emission_factor / 1000.0
        co2_series_per_gen.append(fuel_co2_t)

        # Wenn CHP: Berechne Strom-Gutschrift
        if has_el:
            pel_series = series.get(f"{comp}_Pel_MW", [0.0] * n)
            elec_mwh = pel_series[i] * dt_h
            co2_credit = elec_mwh * grid_co2_series[i] / 1000.0  # Vermiedener Grid-Strom
            co2_elec_credit_series.append(co2_credit)

            # Netto-CO₂ für Wärme
            co2_net_heat = fuel_co2_t - co2_credit
            co2_heat_series.append(max(0.0, co2_net_heat))  # Nicht negativ
        else:
            co2_heat_series.append(fuel_co2_t)
            co2_elec_credit_series.append(0.0)

        # Für Fuel_CO2_emissions_t_per_step: Verwende Gesamt-CO₂
        series["Fuel_CO2_emissions_t_per_step"][i] += fuel_co2_t

    # Export verschiedene Varianten
    series[f"CO2_{comp}_t_per_step"] = co2_series_per_gen  # Gesamt (wie bisher)

    if has_el:
        series[f"CO2_{comp}_heat_t_per_step"] = co2_heat_series  # Nur Wärme-Anteil
        series[f"CO2_{comp}_elec_credit_t_per_step"] = co2_elec_credit_series  # Strom-Gutschrift
```

**Dashboard-Option**:
- Zusätzliche Ansicht "KWK CO₂-Aufteilung"
- Zeigt: Gesamt / Wärme-Anteil / Strom-Gutschrift

---

### Phase 3: VALIDIERUNG (Priorität HOCH)

#### Validierung 3.1: Prüfe Vollständigkeit der Generatoren

**Neue Funktion** in `energis/run/rolling_horizon.py`:
```python
def _validate_co2_completeness(meta, series, df_columns):
    """Prüfe ob alle Generatoren in CO₂-Export enthalten sind."""

    expected_generators = set(gen["name"] for gen in meta["generators"])
    exported_generators = set()

    for col in df_columns:
        if col.startswith('CO2_') and col.endswith('_t_per_step'):
            gen_name = col.replace('CO2_', '').replace('_t_per_step', '')
            exported_generators.add(gen_name)

    missing = expected_generators - exported_generators
    if missing:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"CO₂-Export: Folgende Generatoren fehlen: {missing}\n"
            f"Erwartet: {expected_generators}\n"
            f"Exportiert: {exported_generators}"
        )

    return {
        'expected': list(expected_generators),
        'exported': list(exported_generators),
        'missing': list(missing),
        'complete': len(missing) == 0
    }
```

**Aufruf**: Nach CO₂-Berechnung (Zeile ~900)

---

#### Validierung 3.2: Konsistenz-Checks

**Neue Tests**:
```python
# Check 1: Summe einzelner Generator-CO₂ = Fuel_CO2_total
fuel_co2_individual = 0.0
for gen in meta["generators"]:
    comp = gen["name"]
    if f"CO2_{comp}_t_per_step" in series:
        fuel_co2_individual += sum(series[f"CO2_{comp}_t_per_step"])

fuel_co2_aggregated = sum(series["Fuel_CO2_emissions_t_per_step"])

if abs(fuel_co2_individual - fuel_co2_aggregated) > 0.01:
    logger.warning(
        f"CO₂-Inkonsistenz: Summe einzelner Generatoren ({fuel_co2_individual:.2f} t) "
        f"≠ Aggregiert ({fuel_co2_aggregated:.2f} t)"
    )

# Check 2: Grid CO₂ Plausibilität
energy_bought_MWh = sum(series["P_buy_MW"]) * dt_h
if energy_bought_MWh > 0:
    avg_grid_factor = sum(grid_co2_series) / len(grid_co2_series) if grid_co2_series else 0
    expected_grid_co2 = energy_bought_MWh * avg_grid_factor / 1000
    actual_grid_co2 = sum(series["Grid_CO2_emissions_t_per_step"])

    # Relative Abweichung
    if expected_grid_co2 > 0:
        rel_diff = abs(actual_grid_co2 - expected_grid_co2) / expected_grid_co2
        if rel_diff > 0.05:  # > 5% Abweichung
            logger.warning(
                f"Grid-CO₂ Abweichung: Berechnet {actual_grid_co2:.2f} t, "
                f"Erwartet ~{expected_grid_co2:.2f} t ({rel_diff*100:.1f}% Abweichung)"
            )
```

---

### Phase 4: DOKUMENTATION & TESTING

#### Dokumentation 4.1: CO₂-Zuordnungs-Logik

**Neue Datei**: `docs/CO2_ALLOCATION.md`

**Inhalt**:
- Wie wird CO₂ berechnet?
- Welche Komponenten werden erfasst?
- Wie werden KWK-Anlagen behandelt?
- Wie werden WP/P2H zugeordnet?
- Validierungs-Checks
- Bekannte Limitationen

---

#### Testing 4.2: Unit-Tests

**Neue Test-Datei**: `tests/test_co2_allocation.py`

**Test-Cases**:
1. `test_all_generators_exported()` - Alle Generatoren in export
2. `test_fuel_co2_sum_consistency()` - Summe = Einzelne
3. `test_grid_co2_calculation()` - Grid CO₂ korrekt
4. `test_zero_emission_generators()` - Biomasse/Abfall mit 0 CO₂
5. `test_inactive_generators()` - Nicht laufende Generatoren
6. `test_chp_allocation()` - KWK CO₂ (wenn implementiert)
7. `test_hp_co2_attribution()` - WP CO₂ (wenn implementiert)

---

## ZUSAMMENFASSUNG: PRIORISIERTE TASKS

### ✅ SOFORT (heute):

1. **Fix 1.1**: Alle Generatoren in Tabelle anzeigen (auch CO₂ = 0)
   - Datei: `energis/io/dashboard.py:1950`
   - Ändere: `if gen_co2_t > 0.001:` → prüfe auch `was_active`

2. **Fix 1.2**: Alle Quellen initial auswählen
   - Datei: `energis/io/dashboard.py:1790`
   - Ändere: `[:5]` → alle

3. **Validierung 3.1**: Vollständigkeits-Check implementieren
   - Datei: `energis/run/rolling_horizon.py`
   - Neue Funktion: `_validate_co2_completeness()`

### 📅 DIESE WOCHE:

4. **Feature 2.1**: WP/P2H CO₂ separat exportieren
   - Datei: `energis/run/rolling_horizon.py:800`
   - Neue Berechnung nach Generator-Loop

5. **Validierung 3.2**: Konsistenz-Checks
   - Datei: `energis/run/rolling_horizon.py`
   - Nach CO₂-Berechnung

6. **Testing 4.2**: Unit-Tests schreiben
   - Neue Datei: `tests/test_co2_allocation.py`

### 📆 NÄCHSTE WOCHE (optional):

7. **Feature 2.2**: KWK-CO₂-Aufteilung
   - Nur wenn gewünscht
   - Aufwand: ~4h

8. **Dokumentation 4.1**: CO₂-Allocation-Docs
   - `docs/CO2_ALLOCATION.md`

---

## OFFENE FRAGEN FÜR USER

1. **Generatoren mit CO₂ = 0**:
   - Immer in Tabelle anzeigen?
   - Oder nur wenn aktiv (fuel > 0)?
   - Oder nur wenn CO₂ > 0?

2. **Multiselect Default**:
   - Alle Quellen initial auswählen?
   - Oder Top 10 nach CO₂-Menge?
   - Oder nur die mit CO₂ > 0?

3. **WP/P2H CO₂**:
   - Separat exportieren und anzeigen?
   - Oder nur im Grid-Gesamt belassen?

4. **KWK-CO₂-Aufteilung**:
   - Behalten wie aktuell (Gesamt-CO₂ → Generator)?
   - Oder Stromgutschrift-Methode implementieren?
   - Oder nur in separater Ansicht zeigen?

5. **Stromverkauf** (`P_sell`):
   - Soll Stromeinspeisung CO₂-Gutschrift geben?
   - Oder nicht berücksichtigen?

---

**Empfehlung für Start**: Fix 1.1 + 1.2 + Validierung 3.1 → **sofort umsetzen**
Dann mit Testergebnissen weiteren Bedarf klären.
