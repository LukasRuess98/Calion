# Stadtbach Real Data Requirements

**Anleitung:** Welche echten Daten werden benötigt, um die synthetischen Testdaten zu ersetzen?

## 📋 Übersicht

Aktuell verwendet das Stadtbach-Szenario **synthetische Testdaten** (`data/stadtbach_synthetic_2023_1week.csv`). Dieses Dokument beschreibt die **genauen Anforderungen für echte Betriebsdaten**, um eine realistische Optimierung durchzuführen.

---

## 🎯 Benötigte Datei

### Dateiformat
- **Format**: CSV (Comma-Separated Values)
- **Encoding**: UTF-8
- **Dezimaltrennzeichen**: Punkt (`.`)
- **Zeitstempel**: ISO 8601 Format (`YYYY-MM-DD HH:MM:SS`)
- **Index**: Datetime-Spalte (erste Spalte, kein Name erforderlich)

### Zeitliche Auflösung
- **Auflösung**: Stündlich (empfohlen) oder halbstündlich
- **Mindest-Zeitraum**: 1 Woche (168 Stunden) für Tests
- **Empfohlener Zeitraum**: 1 Jahr (8760 Stunden) für realistische Jahresprognosen
- **Zeitzone**: Lokal (CET/CEST) oder UTC (bitte angeben)

---

## 📊 Erforderliche Spalten

### 1. **waermebedarf_MWth** (PFLICHT)
Stündlicher Wärmebedarf des gesamten Netzwerks

- **Einheit**: MWth (Megawatt thermisch)
- **Typ**: Float
- **Wertebereich**: 0.0 - 100.0 (typisch für Stadtbach)
- **Beispiel**: `45.2`, `38.7`, `52.1`

**Datenquelle:**
- Gemessene Wärmelieferung an allen Abnehmern
- ODER: Summierte Vorlauf-Rücklauf-Temperaturdifferenz × Massenstrom
- ODER: Gaszähler der Heizwerke (umgerechnet auf thermische Leistung)

---

### 2. **strompreis_EUR_MWh** (PFLICHT)
Stündlicher Strompreis für Netzbezug

- **Einheit**: EUR/MWh
- **Typ**: Float
- **Wertebereich**: 20.0 - 300.0 (typisch für 2023-2024)
- **Beispiel**: `85.5`, `120.3`, `65.8`

**Datenquelle:**
- Day-Ahead-Börsenpreise (z.B. EPEX Spot)
- ODER: Vertragliche Strompreise inkl. Abgaben/Umlagen
- ODER: Durchschnittlicher Industriestrompreis

**Hinweis:** Wenn keine stündlichen Preise verfügbar sind, kann ein konstanter Durchschnittspreis verwendet werden (z.B. 100 EUR/MWh).

---

### 3. **T_outdoor** (WICHTIG)
Stündliche Außentemperatur

- **Einheit**: Grad Celsius (°C)
- **Typ**: Float
- **Wertebereich**: -20.0 bis +40.0 (Deutschland)
- **Beispiel**: `5.2`, `-3.5`, `12.8`

**Datenquelle:**
- Wetterstation in der Nähe des Stadtbach-Gebiets
- ODER: DWD (Deutscher Wetterdienst) Klimadaten
- ODER: Online-Wetterdienst (z.B. OpenWeatherMap)

**Verwendung:**
- Beeinflusst Wärmepumpen-COP
- Beeinflusst Netzwerkverluste (Temperaturdifferenz zur Umgebung)

---

### 4. **T_ground** (OPTIONAL, empfohlen für Grundwasser-WP)
Erdreichtemperatur (relevant für Sole/Wasser-Wärmepumpen)

- **Einheit**: Grad Celsius (°C)
- **Typ**: Float
- **Wertebereich**: 5.0 - 15.0 (relativ konstant)
- **Beispiel**: `10.0`, `9.5`, `11.2`

**Datenquelle:**
- Gemessen an Brunnen oder Erdsonden
- ODER: Modelliert (saisonal variierend: Winter ~8°C, Sommer ~12°C)
- ODER: Konstanter Wert (z.B. 10°C)

**Fallback:** Wenn nicht verfügbar, wird ein konstanter Wert von 10°C angenommen.

---

### 5. **WRG1_T_K, WRG2_T_K, WRG3_T_K, WRG4_T_K** (OPTIONAL)
Abwasserwärme-Rückgewinnung (Waste Heat Recovery) - Temperaturen

- **Einheit**: Kelvin (K)
- **Typ**: Float
- **Wertebereich**: 280.0 - 300.0 K (= 7°C - 27°C)
- **Beispiel**: `285.0`, `288.5`, `283.2`

**Datenquelle:**
- Gemessene Abwassertemperaturen an WRG-Standorten
- ODER: Industrieabwärme-Temperaturen
- ODER: Modelliert (typisch: 280-290 K für Abwasser)

**Fallback:** Wenn nicht verfügbar, werden die WRG-Anlagen deaktiviert oder mit konstanten 285 K angenommen.

---

### 6. **WRG1_Q_cap, WRG2_Q_cap, WRG3_Q_cap, WRG4_Q_cap** (OPTIONAL)
Abwasserwärme-Rückgewinnung - Verfügbare thermische Kapazität

- **Einheit**: MW (Megawatt thermisch)
- **Typ**: Float
- **Wertebereich**: 0.0 - 10.0 (typisch pro WRG-Anlage)
- **Beispiel**: `2.5`, `3.0`, `1.8`

**Datenquelle:**
- Berechnete oder gemessene WRG-Potenziale
- ODER: Massenstrom × Temperaturdifferenz × spezifische Wärmekapazität

**Fallback:** Wenn nicht verfügbar, wird eine konstante Kapazität von 5 MW pro WRG-Anlage angenommen.

---

### 7. **grid_co2_kg_MWh** (OPTIONAL, für CO2-Optimierung)
Stündliche CO2-Intensität des Stromnetzes

- **Einheit**: kg CO2eq / MWh
- **Typ**: Float
- **Wertebereich**: 100.0 - 800.0 (Deutschland, je nach Erneuerbare-Anteil)
- **Beispiel**: `350.5`, `280.2`, `520.8`

**Datenquelle:**
- Öffentliche CO2-Intensitätsdaten (z.B. electricityMap, ENTSO-E)
- ODER: Durchschnittswert des deutschen Strommix (ca. 400 kg/MWh 2023)
- ODER: Konstanter Wert

**Fallback:** Wenn nicht verfügbar, wird ein konstanter Wert von 400 kg/MWh angenommen.

---

## 📁 Beispiel CSV-Struktur

```csv
,waermebedarf_MWth,strompreis_EUR_MWh,T_outdoor,T_ground,WRG1_T_K,WRG2_T_K,WRG3_T_K,WRG4_T_K,WRG1_Q_cap,WRG2_Q_cap,WRG3_Q_cap,WRG4_Q_cap,grid_co2_kg_MWh
2023-01-01 00:00:00,52.3,85.2,5.0,10.0,285.0,287.5,283.0,288.0,2.5,3.0,2.0,2.5,380.5
2023-01-01 01:00:00,48.7,78.5,4.5,10.0,284.5,287.0,282.5,287.5,2.5,3.0,2.0,2.5,360.2
2023-01-01 02:00:00,45.2,72.3,4.0,10.0,284.0,286.5,282.0,287.0,2.5,3.0,2.0,2.5,340.8
2023-01-01 03:00:00,43.1,68.5,3.8,10.0,283.8,286.2,281.8,286.8,2.5,3.0,2.0,2.5,330.5
...
```

**Minimal-CSV (nur Pflichtfelder):**

```csv
,waermebedarf_MWth,strompreis_EUR_MWh,T_outdoor
2023-01-01 00:00:00,52.3,85.2,5.0
2023-01-01 01:00:00,48.7,78.5,4.5
2023-01-01 02:00:00,45.2,72.3,4.0
...
```

---

## 🔧 Integration der echten Daten

### Schritt 1: CSV-Datei bereitstellen

Speichern Sie die echte Datendatei im `data/` Verzeichnis:

```bash
# Beispiel
data/stadtbach_real_2023_full_year.csv
```

### Schritt 2: Szenario-Konfiguration anpassen

Passen Sie `configs/scenarios/stadtbach_1week.scenario.yaml` an:

```yaml
# Ersetze synthetische durch echte Daten
data_file: stadtbach_real_2023_full_year.csv  # ⚠️ GEÄNDERT

scenario:
  run_mode: PF_ONLY  # Oder RH für Rolling Horizon
  title: "Stadtbach_Real_Data_Full_Year"
  description: "Stadtbach-Optimierung mit echten Betriebsdaten 2023"

system_file: stadtbach.system.yaml

thermal_network:
  enabled: true
  topology_file: stadtbach_network.yaml

run:
  dt_h: 1.0  # Stündliche Auflösung

  # Zeitraum anpassen (z.B. ganzes Jahr)
  # start_date: "2023-01-01"  # Optional: explizit angeben
  # end_date: "2023-12-31"    # Optional: explizit angeben
```

### Schritt 3: Optimierung ausführen

```python
# In runner.ipynb oder per CLI
from energis.workflows.run_workflow import run_workflow

workflow = run_workflow(
    scenario_config_path='configs/scenarios/stadtbach_1week.scenario.yaml',
    save=True,
    display=True
)

# Dashboard öffnen
from energis.io.dashboard import create_dashboard
dashboard = create_dashboard(workflow)
dashboard
```

### Schritt 4: Ergebnisse validieren

Prüfen Sie:
- ✅ Netzwerk-KPIs im Dashboard (Tab "🌡️ Thermisches Netzwerk")
- ✅ Wärmeverluste liegen im realistischen Bereich (< 2%)
- ✅ Temperaturen liegen im zulässigen Bereich (60-90°C Vorlauf, 30-50°C Rücklauf)
- ✅ Keine Solver-Fehler oder Infeasibilities

---

## ⚙️ Datenqualität & Validierung

### Empfohlene Checks vor der Optimierung:

```python
import pandas as pd

# CSV laden
df = pd.read_csv('data/stadtbach_real_2023_full_year.csv', index_col=0, parse_dates=True)

# 1. Vollständigkeit prüfen
print("Fehlende Werte:")
print(df.isnull().sum())

# 2. Wertebereich prüfen
print("\nWertebereich:")
print(df.describe())

# 3. Zeitliche Lücken prüfen
time_diff = df.index.to_series().diff()
gaps = time_diff[time_diff > pd.Timedelta('1 hour')]
if not gaps.empty:
    print(f"\n⚠️ Zeitliche Lücken gefunden: {len(gaps)}")
    print(gaps)

# 4. Plausibilität
assert df['waermebedarf_MWth'].min() >= 0, "Negativer Wärmebedarf!"
assert df['waermebedarf_MWth'].max() < 150, "Unrealistisch hoher Wärmebedarf!"
assert df['T_outdoor'].between(-25, 45).all(), "Unrealistische Außentemperaturen!"

print("\n✅ Datenqualität OK")
```

---

## 🆘 Troubleshooting

### Problem: "Keine Wärmebedarf-Spalte gefunden"

**Ursache:** Spaltenname stimmt nicht überein

**Lösung:** Benennen Sie die Spalte exakt als `waermebedarf_MWth` (case-sensitive) oder passen Sie `energis/io/dashboard.py` an:

```python
# In dashboard.py, Zeile ~326
demand_col_names = ['waermebedarf_MWth', 'Waermebedarf_MWth', 'IHR_SPALTENNAME']
```

---

### Problem: Solver findet keine Lösung (Infeasible)

**Mögliche Ursachen:**
1. **Zu hoher Wärmebedarf**: Peak-Demand > Anlagen-Kapazität
   - **Lösung**: Erhöhen Sie Anlagen-Kapazitäten in `stadtbach.system.yaml`

2. **Unrealistische WRG-Temperaturen**: Zu niedrig für Wärmepumpen
   - **Lösung**: Prüfen Sie WRG_T_K Werte (sollten > 280 K sein)

3. **Netzwerk-Constraints zu eng**: Temperaturgrenzen nicht erfüllbar
   - **Lösung**: Lockern Sie `T_supply_min` / `T_supply_max` in `stadtbach_network.yaml`

---

### Problem: Optimierung läuft sehr lange (> 10 Minuten)

**Ursachen:**
1. **Zu viele Zeitschritte**: 1 Jahr = 8760 Stunden → MIQP sehr groß
2. **Komplexes Netzwerk**: Viele Knoten/Rohre → viele Variablen

**Lösungen:**
1. **Reduzieren Sie Zeitschritte**: Testen Sie zunächst mit 1 Woche
2. **Vereinfachen Sie Netzwerk**: Aggregieren Sie weniger wichtige Knoten
3. **Verwenden Sie Rolling Horizon**: `run_mode: RH` statt `PF_ONLY`
4. **Erhöhen Sie MIPGap**: In `stadtbach.system.yaml`:
   ```yaml
   solver:
     options:
       MIPGap: 0.05  # 5% statt 1%
   ```

---

## 📞 Kontakt & Support

Bei Fragen zur Datenbereitstellung:

1. **Email**: [Ihre Email]
2. **GitHub Issues**: https://github.com/IHR-REPO/issues
3. **Dokumentation**: `docs/THERMAL_NETWORK_QUICKSTART.md`

---

## 📌 Zusammenfassung

**Minimal erforderlich für erste Tests:**
- `waermebedarf_MWth` (Wärmebedarf)
- `strompreis_EUR_MWh` (Strompreis)
- `T_outdoor` (Außentemperatur)

**Empfohlen für realistische Optimierung:**
- Alle oben genannten Spalten
- Mindestens 1 Jahr Daten (8760 Stunden)
- Validierte Datenqualität (keine Lücken, plausible Werte)

**Dateipfad in Konfiguration:**
```yaml
data_file: stadtbach_real_2023_full_year.csv
```

---

**Letzte Aktualisierung**: 2025-12-10
**Version**: 1.0
