# Zonale Kosten-Dokumentation

## 🎯 Überblick

Diese Dokumentation erklärt, wie Sie **zonale Netzgebühren** (pro Anschlusspunkt unterschiedlich) in CALION modellieren.

Das System hat **3 umkonfigurierbare Varianten**:

| Variante | Beschreibung | Komplexität | Beispiel |
|----------|-------------|-------------|---------|
| **1: Global** | Alle Zonen zahlen gleich | ⭐ | Baseline-Szenarien |
| **2: Global + Zone-Statisch** | Unterschiedliche feste Tarife pro Zone | ⭐⭐ | Zentral vs. Peripherie |
| **3: Global + Zone + Dynamic (CSV)** | Stündlich variable Tarife | ⭐⭐⭐ | Echtzeit-Preismodelle |

---

## 📋 Variante 1: Global Costs Only (Einfach)

**Verwendung:** Alle Zonen zahlen identische Gebühren.

### YAML-Struktur

```yaml
grid:
  demand_charge_eur_per_mw_y: 50000.0    # ← EINZIGE Kostenquelle

costs:
  co2_price_eur_per_t: 100.0
  dump_cost_eur_per_mwh_th: 10.0

# Keine 'costs_config' Sektion!
```

### Was passiert

- ✅ CostResolver wird NICHT verwendet
- ✅ Alle Zonen zahlen: **€50,000/MW/Jahr**
- ✅ Sehr schnell & einfach zu debuggen

### Datei-Beispiel

`configs/paper/L2_costs_example_1_global_only.yaml`

---

## 📋 Variante 2: Global + Zone-Specific Static Costs (Empfohlen)

**Verwendung:** Unterschiedliche Netzgebühren pro Zone, STATISCH (nicht zeitabhängig).

**Best für:** Realistische Tarife mit Zentral (günstig) vs. Peripherie (teuer).

### YAML-Struktur

```yaml
costs_config:
  # GLOBAL (Fallback für alle Zonen)
  global:
    demand_charge_eur_per_mw_y: 50000.0
    energy_fee_eur_per_mwh: 5.0

  # ZONE-SPEZIFISCHE OVERRIDES
  zones:
    plant_main:                              # Zentrale Produktion
      type: "central_plant"
      demand_charge_eur_per_mw_y: 0.0       # ← KEIN Netzentgelt!

    j_central:                               # Zentrale Weiterleitung
      type: "central_junction"
      demand_charge_eur_per_mw_y: 30000.0   # ← Günstiger als Global

    j_north:                                 # Standard (nutzt Global)
      type: "standard"
      # Keine Override → nutzt global

    j_south:                                 # Peripherie
      type: "peripheral"
      demand_charge_eur_per_mw_y: 70000.0   # ← Teurer

# grid section wird ignoriert wenn costs_config vorhanden!
grid:
  demand_charge_eur_per_mw_y: 50000.0      # Wird überschrieben
```

### Auflösungs-Hierarchie

Die **CostResolver** nutzt diese Priorität:

```
Zur Laufzeit für JEDE Zone:
  1. Zone-spezifischer Wert definiert?    → NUTZE DIESEN
  2. Nein?                                 → nutze Global-Standard
  3. Auch nicht?                           → nutze 0.0 (Default)
```

**Beispiel-Ablauf (j_south):**

```python
# Code sucht: j_south.demand_charge_eur_per_mw_y

# 1. Zuerst: Ist es in costs_config.zones definiert?
j_south in cfg['costs_config']['zones']  # ✓ JA
  return 70000.0                            # ← BENUTZE DIES

# Falls "j_south" NICHT definiert wäre:
# 2. Dann: Gibt es einen Global-Standard?
return cfg['costs_config']['global']['demand_charge_eur_per_mw_y']  # 50000.0
```

### Ausgabe-Beispiel

```json
{
  "zones": {
    "plant_main": {
      "demand_charge_eur_per_mw_y": 0.0,
      "peak_power_mw": 0.0,
      "cost_demand_charge_eur": 0.0
    },
    "j_central": {
      "demand_charge_eur_per_mw_y": 30000.0,
      "peak_power_mw": 65.3,
      "cost_demand_charge_eur": 1959000.0    ← 65.3 × 30000
    },
    "j_south": {
      "demand_charge_eur_per_mw_y": 70000.0,
      "peak_power_mw": 70.1,
      "cost_demand_charge_eur": 4907000.0    ← 70.1 × 70000
    },
    "zone_01": {
      "demand_charge_eur_per_mw_y": 30000.0,  ← Nutzt Zone-Override
      "peak_power_mw": 25.5,
      "cost_demand_charge_eur": 765000.0
    },
    "zone_02": {
      "demand_charge_eur_per_mw_y": 50000.0,  ← Nutzt Global (nicht überschrieben)
      "peak_power_mw": 30.2,
      "cost_demand_charge_eur": 1510000.0
    }
  }
}
```

### Datei-Beispiel

`configs/paper/L2_costs_example_2_zonal_static.yaml`

---

## 📋 Variante 3: Global + Zone + Dynamic (Echtzeit-Tarife)

**Verwendung:** Netzgebühren variieren **STÜNDLICH** (z.B. Echtzeit-Preise).

**Best für:** Realistische Tarife mit:
- Spitzenlast-Zeiten (teuer morgens/abends)
- Off-Peak (günstig mittags)
- Lokale Netzengpässe als Stundentriff

### CSV-Struktur

**Datei:** `data/Import_Data_yearly_zonal_costs.csv`

```csv
Datum,strompreis_EUR_MWh,plant_charge_EUR_MW_h,j_central_charge_EUR_MW_h,j_south_charge_EUR_MW_h
2023-01-01 00:00:00,60.0,0.0,6.50,8.20
2023-01-01 01:00:00,59.0,0.0,6.60,8.30
2023-01-01 06:00:00,55.0,0.0,5.20,6.50    ← Off-Peak (früh morgens)
2023-01-01 12:00:00,65.0,0.0,3.20,4.50    ← Mittags (günstig, viel Solar)
2023-01-01 18:00:00,80.0,0.0,7.50,9.00    ← Abend-Spitze (teuer)
```

**Anforderungen:**
- Genau **8760 Zeilen** für Volljahrr (oder weniger für Horizont)
- **Spalten:** Eine pro Zone + Cost-Typ
- **Format:** Stunden, Euro/MW/h
- **Ausrichtung:** MUSS mit Haupt-CSV zeitlich identisch sein!

### YAML-Struktur

```yaml
site:
  input_xlsx: "data/Import_Data_yearly_zonal_costs.csv"  # ← WICHTIG!

costs_config:
  global:
    demand_charge_eur_per_mw_y: 50000.0    # Backup wenn CSV fehlt

  zones:
    j_central:
      demand_charge_eur_per_mw_y: 30000.0  # Backup Jahreswert
    # ...

  # ← MAIN: DYNAMISCHE KOSTEN
  dynamic:
    enabled: true                                         # ← AKTIVIEREN!
    source: "data/Import_Data_yearly_zonal_costs.csv"    # CSV-Pfad
    mappings:                                             # CSV → Zone-Mapping
      # Format: "{zone_id}_{cost_type}" : "{csv_column}"
      j_central_demand_charge_eur_per_mw_y: "j_central_charge_EUR_MW_h"
      j_south_demand_charge_eur_per_mw_y: "j_south_charge_EUR_MW_h"
      zone_01_demand_charge_eur_per_mw_y: "zone_01_charge_EUR_MW_h"
```

### Auflösungs-Hierarchie (Pro Zeitschritt)

```
Für JEDEN Zeitschritt t=1..8760:

  1. CostResolver sucht CSV-Spalte?
     "j_south_demand_charge_eur_per_mw_y" in mappings?  ✓ JA
     
  2. CSV-Spaltenname suche in Tabelle
     "j_south_charge_EUR_MW_h" in table.columns?  ✓ JA
     
  3. Wert für Zeitschritt abrufen
     → table["j_south_charge_EUR_MW_h"][t-1]  ← 0-basiert!
     → z.B. 9.00 für 18:00 Uhr
     ← NUTZE DIESEN WERT!
     
  Fallback (wenn CSV-Spalte FEHLT):
  4. Suche Zone-spezifischen statischen Wert
     j_south in costs_config.zones?  ✓ JA (70000.0/365/24 annualisiert)
     
  5. Fallback zu Global
     return 50000.0 / 365 / 24
```

### Ausgabe-Beispiel (Durchschnitte)

```json
{
  "zones": {
    "j_central": {
      "demand_charge_type": "dynamic",
      "csv_column": "j_central_charge_EUR_MW_h",
      "hourly_values": {
        "min": 3.20,
        "max": 8.90,
        "average": 5.43
      },
      "peak_power_mw": 65.3,
      "cost_demand_charge_eur": 2385504.0    ← durchschn. 5.43 * 65.3 * 8760h
    }
  }
}
```

### Datei-Beispiel

- YAML: `configs/paper/L2_costs_example_3_zonal_dynamic.yaml`
- CSV: `data/Import_Data_yearly_zonal_costs.csv` (24 Beispielstunden)

---

## 🔧 Implementation in system_builder.py

### Code-Integration (Pseudo-Code)

```python
from calion.models.cost_resolver import CostResolver

def _build_model_unified(table, cfg, dt_h):
    # ...
    
    # 1. INSTANTIIERE COST RESOLVER
    cost_resolver = CostResolver(cfg, table)
    cost_resolver.log_resolution_summary()  # Debug-Output
    
    # 2. STATISCHE ZONE-KOSTEN (während Modellbau)
    m.zone_demand_charge = {}  # Dict[zone_id] → Param
    for zone_id in ucfg.nodes:
        charge = cost_resolver.get_zone_cost(zone_id, "demand_charge_eur_per_mw_y")
        m.zone_demand_charge[zone_id] = pyo.Param(initialize=charge)
    
    # 3. DYNAMISCHE ZONE-KOSTEN (pro Zeitschritt)
    if cost_resolver.dynamic_enabled:
        m.zone_demand_charge_ts = {}  # Dict[zone_id] → Param(m.t)
        for zone_id in ucfg.nodes:
            charge_dict = {
                t: cost_resolver.get_zone_cost(
                    zone_id, 
                    "demand_charge_eur_per_mw_y", 
                    timestep=t
                )
                for t in m.t
            }
            m.zone_demand_charge_ts[zone_id] = pyo.Param(
                m.t, 
                initialize=charge_dict
            )
    
    # 4. OBJECTIVE: Sommiere über alle Zonen
    demand_charge_expr = 0
    for zone_id in ucfg.nodes:
        if cost_resolver.dynamic_enabled:
            # Zeitabhängig
            demand_charge_expr += sum(
                m.P_buy_by_zone.get(zone_id, m.P_buy)[t] * 
                m.zone_demand_charge_ts[zone_id][t] 
                for t in m.t
            )
        else:
            # Statisch (Annual)
            demand_charge_expr += (
                m.zone_demand_charge[zone_id] * 
                m.year_frac * 
                m.P_buy_peak_by_zone.get(zone_id, m.P_buy_peak)
            )
```

---

## ✅ Checkliste: Welche Variante wählen?

| Frage | Ja → Var. | Nein → Var. |
|-------|-----------|------------|
| Alle Zonen identisch? | 1 | → |
| Zentral/Peripherie unterschiedlich? | 2 | 1 |
| Stündliche Tarif-Variation nötig? | 3 | 2 |
| Haben Sie CSV mit 8760 Zeilen? | 3 | 2 |
| Produktion vs. Verbrauch unterschiedl.? | 2/3 | 1 |

---

## 🎓 Praktisches Beispiel: Stadtbach mit 3 Branchen

### Szenario
- **Plant Main**: Central, 0€ Netzentgelt
- **Junction North**: Standard, €30k/MW/Jahr
- **Junction South**: Teuer (Peripherie), €70k/MW/Jahr
- **Zone 01-23**: Consumer, meist teuer

### Kosten-Konfiguration

```yaml
costs_config:
  global:
    demand_charge_eur_per_mw_y: 50000.0
    energy_fee_eur_per_mwh: 5.0

  zones:
    plant_main:
      demand_charge_eur_per_mw_y: 0.0
    j_central:
      demand_charge_eur_per_mw_y: 30000.0
    j_north:
      demand_charge_eur_per_mw_y: 35000.0     # Etwas günstiger
    j_south:
      demand_charge_eur_per_mw_y: 65000.0     # Sehr teuer
    
    # Consumer-Zonen (nutzen meist zone-spezifisch)
    zone_01:
      demand_charge_eur_per_mw_y: 55000.0
    zone_02:
      demand_charge_eur_per_mw_y: 50000.0     # Nutzt global, da nicht überschrieben
    zone_03:
      demand_charge_eur_per_mw_y: 60000.0
```

### Erwartete Ergebnisse

```
Zone Ranking nach Entgelte (jährlich):

1. Plant Main    : €0         (Zentrale — kostenlos)
2. J North       : €35k/MW    (Nord-Stamm — Standard)
3. J Central     : €30k/MW    (Zentral — Premium)
4. J South       : €65k/MW    (Süd-Stamm — Peripherie)
5. Zone 01-23    : €50k-60k/MW (Consumer — teuer)

Optimizer-Verhalten:
- Bevorzugt: Erzeugung bei Plant Main (0€ Gebühren)
- Vermeidet: Große Importe in J South (zu teuer)
- Nutzt Storage: Puffert Lastypen zwischen billigen/teuren Zonen
```

---

## 🐛 Debugging & Validierung

### 1. CostResolver-Zusammenfassung loggen

```python
cost_resolver.log_resolution_summary()
```

Zeigt:
```
COST RESOLUTION SUMMARY
Zone: plant_main                Type: central_plant
  demand_charge_eur_per_mw_y   0.00
Zone: j_central                 Type: central_junction
  demand_charge_eur_per_mw_y   30000.00
  energy_fee_eur_per_mwh       5.00
...
```

### 2. Alle Zones-Kosten abrufen

```python
all_costs = cost_resolver.get_all_zones_costs()
for zone_id, costs in all_costs.items():
    print(f"{zone_id}: {costs}")
```

### 3. Einzelnen Zone-Wert prüfen

```python
central_charge = cost_resolver.get_zone_cost("j_central", "demand_charge_eur_per_mw_y")
print(f"j_central Charge: €{central_charge:.2f}/MW/Year")
```

### 4. Dynamische Werte (CSV) validieren

```python
# Stündliche Werte für Zone/Zeitschritt
t = 18  # 18 Uhr (6 PM)
charge_18h = cost_resolver.get_zone_cost("j_central", "demand_charge_eur_per_mw_y", t)
print(f"18h peak charge: €{charge_18h:.2f}/MW/h")
```

---

## 📚 Weitere Ressourcen

- **Docs:** `docs/ZONAL_COSTS_GUIDE.md` (diese Datei)
- **Config-Beispiele:**
  - `configs/paper/L2_costs_example_1_global_only.yaml`
  - `configs/paper/L2_costs_example_2_zonal_static.yaml`
  - `configs/paper/L2_costs_example_3_zonal_dynamic.yaml`
- **CSV-Beispiel:** `data/Import_Data_yearly_zonal_costs.csv`
- **Modul:** `calion/models/cost_resolver.py`

---

## 🎯 TL;DR (Kurz-Zusammenfassung)

1. **Global Costs:** Keine `costs_config` → alle Zonen identisch
2. **Zone-Statisch:** `costs_config.zones` definieren → Overrides per Zone
3. **Zone-Dynamic:** `costs_config.dynamic` aktivieren + CSV → stündliche Tarife
4. **Auflösung:** Dynamic > Zone > Global > 0.0
5. **Debugging:** `cost_resolver.log_resolution_summary()` nutzen
