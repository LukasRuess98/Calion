# Excel Import für Thermische Netzwerke

## Übersicht

Die Excel-Import-Funktionalität ermöglicht die schnelle und strukturierte Erstellung von Wärmenetz-Szenarien aus einer zentralen Excel-Datei.

**Vorteile gegenüber manuellem YAML:**
- ⚡ **10x schneller**: 30-60 Minuten statt 4-6 Stunden
- 📊 **Übersichtlich**: Tabellenformat statt 500+ Zeilen YAML
- ✅ **Automatisch**: Rücklaufrohre, Knoten, Validierung
- 🎯 **Fehlerfrei**: Eingebaute Validierung vor YAML-Generierung
- 📦 **Alles in einem**: Alle Zeitreihen in einem Sheet

## Schnellstart

### 1. Template erstellen

```bash
python scripts/create_thermal_network_template.py --output data/my_network.xlsx

# Optional: Für Multi-Sheet-Support
pip install openpyxl
```

### 2. Excel ausfüllen

Öffne `data/my_network.xlsx` und fülle 6 Sheets aus:

| Sheet | Inhalt | Zeilen |
|-------|--------|--------|
| **Netzwerk** | Netzwerkparameter (T_Vorlauf, T_Rücklauf, p_nominal) | ~6 |
| **Erzeuger** | Wärmeerzeuger (Kessel, WP, BHKW) mit Bestand/Investition | ~3-10 |
| **Speicher** | Thermische Speicher (optional) | ~0-5 |
| **Rohre** | NUR Vorlaufrohre (Rücklauf wird automatisch generiert!) | ~10-50 |
| **Verbraucher** | Wärmeverbraucher mit Lastgang-Referenzen | ~1-20 |
| **Zeitreihen** | Alle Lastgänge, Preise, Temperaturen | 8760 |

### 3. Konvertieren zu YAML

```python
from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser

# Excel einlesen und parsen
parser = ThermalNetworkExcelParser("data/my_network.xlsx")

# Zusammenfassung anzeigen
print(parser.get_summary())

# Validierung
errors = parser.validate()
if not errors:
    # YAML speichern
    parser.save_yaml("configs/scenarios/my_network.scenario.yaml")
    print("✓ Erfolgreich erstellt!")
else:
    for error in errors:
        print(f"❌ {error}")
```

### 4. Simulation durchführen

```python
from energis.run import ThermalNetworkOptimizer

optimizer = ThermalNetworkOptimizer("configs/scenarios/my_network.scenario.yaml")
results = optimizer.optimize()
results.plot_summary()
```

## Excel-Struktur im Detail

### Sheet 1: Netzwerk

Grundlegende Netzwerkparameter:

```
Parameter           Wert              Einheit  Beschreibung
Name                Musterhausen               Name des Wärmenetzes
T_Vorlauf_nom       90                °C       Nominale Vorlauftemperatur
T_Ruecklauf_nom     50                °C       Nominale Rücklauftemperatur
p_nominal           6                 bar      Nominaler Netzdruck
Netztyp             district_heating           district_heating | building_network
Optimierungsmodus   cost                       cost | emissions | exergy
```

### Sheet 2: Erzeuger

Wärmeerzeuger mit Brownfield/Greenfield-Kennzeichnung:

```
ID        Typ         Bestand?  Investition?  Q_nom_MW  Q_options_MW    CAPEX_€_kW  OPEX_fix  OPEX_var  Wirkungsgrad  COP  Brennstoff  Vorlauf_Knoten  Ruecklauf_Knoten
Kessel_1  boiler      ja        nein          15.0                      300         15        25        0.95               gas         N1              N1_R
WP_1      heat_pump   nein      ja                      5.0,10.0,15.0   800         20        5                      3.5  electricity  N2              N2_R
BHKW_1    chp         ja        nein          8.0                       1200        30        20        0.85               gas         N1              N1_R
```

**Wichtig:**
- `Bestand? = ja` → Komponente existiert bereits (CAPEX = 0, feste Größe)
- `Investition? = ja` → Neue Komponente (Größe wird optimiert)
- Genau EINS von beiden muss `ja` sein!

### Sheet 3: Speicher

Thermische Speicher (optional):

```
ID          Typ             Bestand?  Investition?  Kapazitaet_MWh  Kapazitaet_options_MWh  T_max_C  T_min_C  Verlustrate_1_h  CAPEX_€_kWh
Speicher_1  hot_water_tank  ja        nein          30.0                                    95       40       0.001            50
PTES_1      ptes            nein      ja                            50,100,200              80       40       0.0005           25
```

### Sheet 4: Rohre

**NUR Vorlaufrohre!** Rücklaufrohre werden automatisch generiert mit ID `<ID>_return`:

```
ID  Von_Knoten    Zu_Knoten     Laenge_m  Bestand?  Investition?  DN_fix  Daemmung_fix  Baujahr  Zustand  DN_options              Daemmung_options  CAPEX_€_m
P1  gaskessel_01  junction_ctr  100       ja        nein          DN200   standard      2010     good
P2  chp_01        junction_ctr  150       ja        nein          DN150   standard      2010     good
P3  junction_ctr  altstadt      5000      ja        nein          DN200   standard      2010     good
P4  wp_neu        junction_ctr  500       nein      ja                                                    DN150,DN200,DN250   standard,enhanced 250
```

**Automatisch generiert:**
- `P1_return`: altstadt → junction_ctr (100m, DN200)
- `P2_return`: junction_ctr → chp_01 (150m, DN150)
- `P3_return`: altstadt → junction_ctr (5000m, DN200)
- `P4_return`: junction_ctr → wp_neu (500m, DN150/200/250)

### Sheet 5: Verbraucher

Wärmeverbraucher mit Referenzen zu Lastgängen:

```
ID        Knoten    Lastgang                Spitzenlast_MW  Jahresbedarf_MWh  T_Vorlauf_min_C  T_Ruecklauf_C
Altstadt  altstadt  heat_demand_altstadt    12.0            45000             70               45
Neustadt  neustadt  heat_demand_neustadt    8.0             30000             70               45
```

**Wichtig:** `Lastgang` muss mit Spaltennamen in Sheet "Zeitreihen" übereinstimmen!

### Sheet 6: Zeitreihen

Alle Zeitreihen in EINER Tabelle (8760 Zeilen für Gesamtjahr):

```
Zeitstempel             heat_demand_altstadt  heat_demand_neustadt  Strompreis_€_MWh  Gaspreis_€_MWh  Aussentemperatur_C
2023-01-01 00:00:00     8.5                   5.2                   65.2              35.0            -2.5
2023-01-01 01:00:00     8.2                   5.0                   62.1              35.0            -3.1
2023-01-01 02:00:00     7.9                   4.8                   58.3              35.0            -3.5
...
2023-12-31 23:00:00     9.1                   5.8                   70.5              35.0            -1.2
```

**Format:**
- Erste Spalte: Zeitstempel (optional, für Referenz)
- Weitere Spalten: Lastgänge, Preise, Temperaturen
- Genau 8760 Zeilen für Jahressimulation

## Brownfield/Greenfield-Szenarien

### Beispiel 1: Reines Greenfield (Neues Netz)

Alle Komponenten mit `Investition? = ja`:

```
Erzeuger:
WP_1      heat_pump   nein  ja  -  2.0,4.0,6.0  800  ...
Kessel_1  boiler      nein  ja  -  1.0,2.0,3.0  300  ...

Rohre:
P1  N1  N2  500  nein  ja  -  DN100,DN150,DN200  250
P2  N2  N3  300  nein  ja  -  DN100,DN150,DN200  250
```

→ Optimierer wählt:
- Optimale Größe für WP (2, 4 oder 6 MW)
- Optimale Größe für Kessel (1, 2 oder 3 MW)
- Optimale DN für alle Rohre

### Beispiel 2: Reines Brownfield (Bestehendes Netz)

Alle Komponenten mit `Bestand? = ja`:

```
Erzeuger:
Kessel_1  boiler  ja  nein  15.0  -  300  ...

Rohre:
P1  N1  N2  500  ja  nein  DN200  standard  2010  good
P2  N2  N3  300  ja  nein  DN150  standard  2010  good
```

→ Optimierer:
- Geometrie ist fix (keine CAPEX)
- Optimiert nur Betriebsweise (OPEX)

### Beispiel 3: Gemischtes Szenario (Brownfield + Greenfield)

Bestehende Komponenten erweitern:

```
Erzeuger:
Kessel_1  boiler      ja    nein  15.0              -  300   ...  (BESTAND)
WP_1      heat_pump   nein  ja    -    5.0,10.0,15.0  800   ...  (NEU)

Speicher:
Speicher_1  hot_water_tank  ja    nein  30.0                -  50  (BESTAND)
PTES_1      ptes            nein  ja    -     50,100,200     25  (NEU)

Rohre:
P1  gaskessel_01  junction_ctr  100   ja    nein  DN200                    -  (BESTAND)
P2  chp_01        junction_ctr  150   ja    nein  DN150                    -  (BESTAND)
P4  wp_neu        junction_ctr  500   nein  ja    -      DN150,DN200,DN250  250  (NEU)
```

→ Optimierer:
- Bestandskomponenten: Feste Geometrie, nur Betriebsoptimierung
- Neue Komponenten: Optimierung von Größe UND Betrieb
- Gesamtkosten: OPEX (alle) + CAPEX (nur neue)

## Validierung

Der Parser führt automatische Validierung durch:

### ✅ Geprüfte Bedingungen

1. **Rohrpaare**: Jedes Vorlaufrohr muss Rücklaufrohr haben (automatisch generiert)
2. **Bestand XOR Investition**: Jede Komponente muss ENTWEDER `Bestand?=ja` ODER `Investition?=ja` haben
3. **Investitionsoptionen**: Bei `Investition?=ja` müssen Optionen angegeben sein
4. **Bestandsparameter**: Bei `Bestand?=ja` müssen feste Parameter angegeben sein
5. **Knotenreferenzen**: Alle in Rohren/Komponenten referenzierten Knoten müssen existieren
6. **Lastgangreferenzen**: Alle in Verbrauchern referenzierten Lastgänge müssen in Zeitreihen existieren

### ❌ Typische Fehler

```
❌ Producer 'WP_1': Cannot have both existing=True and invest=True
   → Fix: Setze entweder "Bestand?" ODER "Investition?" auf ja, nicht beide

❌ Producer 'WP_1': invest=True requires Q_options
   → Fix: Gib bei "Q_options_MW" eine kommagetrennte Liste ein: "5.0,10.0,15.0"

❌ Pipe 'P1': from_node 'N99' not found
   → Fix: Prüfe Tippfehler in "Von_Knoten" (Knoten werden automatisch aus Verbindungen extrahiert)

❌ Consumer 'Altstadt': demand_profile 'heat_demand_altstadt' not found in timeseries
   → Fix: Prüfe, dass Spaltenname in "Zeitreihen"-Sheet mit "Lastgang"-Eintrag übereinstimmt
```

## Integration mit bestehendem Workflow

### Ausgabedateien

Nach `parser.save_yaml(output_path)` werden erstellt:

1. **YAML-Konfiguration**: `configs/scenarios/my_network.scenario.yaml`
   - Enthält alle Netzwerk-, Komponenten- und Simulationsparameter
   - Referenziert Zeitreihendaten

2. **Zeitreihen-CSV**: `configs/scenarios/my_network_timeseries.csv`
   - Enthält alle Spalten aus "Zeitreihen"-Sheet
   - 8760 Zeilen für Jahressimulation

### Verwendung in Simulation

```python
# Standard-Workflow
from energis.run import ThermalNetworkOptimizer

optimizer = ThermalNetworkOptimizer("configs/scenarios/my_network.scenario.yaml")
results = optimizer.optimize()

# Ergebnisse analysieren
results.plot_operation()        # Betriebsweise über Zeit
results.plot_investments()      # Gewählte Investitionen
results.plot_costs()            # Kostenaufschlüsselung
results.export_to_excel("results/my_network_results.xlsx")
```

## FAQ

### Muss ich openpyxl installieren?

**Nein**, aber empfohlen für Multi-Sheet-Templates:
```bash
pip install openpyxl
```

Ohne openpyxl wird ein einfaches Single-Sheet-Template erstellt.

### Wie viele Rohre muss ich eingeben?

**Nur Vorlaufrohre!** Rücklaufrohre werden automatisch generiert:
- Input: 10 Vorlaufrohre → Output: 20 Rohre (10 Vorlauf + 10 Rücklauf)

### Wie definiere ich Knoten?

**Gar nicht!** Knoten werden automatisch aus Verbindungen extrahiert:
- Rohre: `Von_Knoten`, `Zu_Knoten`
- Erzeuger/Speicher: `Vorlauf_Knoten`, `Ruecklauf_Knoten`
- Verbraucher: `Knoten`

Alle eindeutigen Namen werden zu Knoten.

### Kann ich Excel UND YAML mischen?

**Ja!** Der Excel-Parser erstellt YAML-Dateien, die dann manuell weiterbearbeitet werden können.

Workflow:
1. Excel → YAML generieren (80% der Arbeit)
2. YAML manuell feintunen (20% der Arbeit)
3. Simulation durchführen

### Wie viele Zeitschritte brauche ich?

- **Test/Entwicklung**: 24-168 Stunden (1-7 Tage)
- **Vollständige Simulation**: 8760 Stunden (1 Jahr)
- **Mehrjahressimulation**: 17520+ Stunden (2+ Jahre)

### Was passiert bei Validierungsfehlern?

`parser.validate()` gibt Liste von Fehlermeldungen zurück:
```python
errors = parser.validate()
if errors:
    for error in errors:
        print(f"❌ {error}")
    # Fix errors in Excel
else:
    parser.save_yaml(...)  # Safe to save
```

YAML wird **nicht** gespeichert, bis alle Fehler behoben sind.

## Beispiele

### Vollständiges Beispiel im Notebook

Siehe: `notebooks/thermal_network_excel_import.ipynb`

- Schritt-für-Schritt-Anleitung
- Brownfield/Greenfield-Beispiele
- Validierung und Troubleshooting
- Integration mit Simulation

### Template-Erstellung

```bash
# Standard-Template
python scripts/create_thermal_network_template.py

# Benutzerdefinierter Pfad
python scripts/create_thermal_network_template.py --output data/projekt_xy.xlsx
```

### Programmmatische Verwendung

```python
from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser

# Parser initialisieren
parser = ThermalNetworkExcelParser("data/my_network.xlsx")

# Zusammenfassung anzeigen
summary = parser.get_summary()
print(summary)

# Validierung
errors = parser.validate()
assert not errors, f"Validation failed: {errors}"

# Zugriff auf geparste Daten
print(f"Anzahl Erzeuger: {len(parser.config['producers'])}")
print(f"Anzahl Rohre: {len(parser.config['pipes'])}")  # Inkl. Rücklauf!
print(f"Anzahl Knoten: {len(parser.config['nodes'])}")  # Auto-extrahiert

# Speichern
parser.save_yaml("configs/scenarios/my_network.scenario.yaml")
```

## Zusammenfassung

| Feature | Excel-Import | Manuelles YAML |
|---------|--------------|----------------|
| **Zeitaufwand** | 30-60 min | 4-6 h |
| **Fehleranfälligkeit** | Niedrig (Validierung) | Hoch |
| **Übersichtlichkeit** | Hoch (Tabellen) | Mittel (Text) |
| **Rücklaufrohre** | Automatisch | Manuell |
| **Knoten** | Automatisch | Manuell |
| **Validierung** | Eingebaut | Zur Laufzeit |
| **Lernkurve** | Flach (Excel) | Steil (YAML-Syntax) |
| **Versionskontrolle** | Binär (Git-LFS) | Text (Git) |

**Empfehlung:** Excel-Import für neue Szenarien, YAML-Feintuning für Details.

## Weiterführende Dokumentation

- **Thermal Network Requirements**: `docs/thermal_network_requirements.md`
- **Implementation Plan**: `docs/thermal_network_implementation_plan.md`
- **Brownfield Quickstart**: `docs/brownfield_quickstart_guide.md`
- **Example Notebook**: `notebooks/thermal_network_excel_import.ipynb`
