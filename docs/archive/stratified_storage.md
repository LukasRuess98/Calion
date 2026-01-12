# Stratified Thermal Energy Storage Component

## Übersicht

Das `StratifiedStorageBlock` ist eine erweiterte Speicherkomponente für große thermische Energiespeicher im Industrie- und Fernwärmebereich. Im Gegensatz zum einfachen `StorageBlock` modelliert diese Komponente die thermische Schichtung (Stratifikation) in zwei Zonen und ermöglicht eine realistische Abbildung von Großspeichern wie:

- Fernwärme-Pufferspeicher (100-500 MWh)
- Saisonale Wärmespeicher (1.000-50.000 MWh)
- Erdbeckenwärmespeicher (Pit Thermal Energy Storage, PTES)
- Industrielle Prozesswärmespeicher

## Hauptmerkmale

### 1. Zwei-Zonen-Modell

Der Speicher wird in zwei thermische Zonen aufgeteilt:
- **Hot Zone** (oben): Hohe Temperatur (z.B. 90°C)
- **Cold Zone** (unten): Niedrige Temperatur (z.B. 40°C)

### 2. Fixe Design-Temperaturen (Linearisierung)

Durch Verwendung fixer Temperaturen bleibt das Modell **vollständig linear** und kann mit MIP-Solvern (CBC, Gurobi, CPLEX) gelöst werden:

```python
E_hot[t] = e_specific × T_hot × V_hot[t]  # LINEAR!
E_cold[t] = e_specific × T_cold × V_cold[t]  # LINEAR!
E_total[t] = E_hot[t] + E_cold[t]
```

### 3. Geometriebasierte Wärmeverluste

Wärmeverluste werden aus der tatsächlichen Geometrie berechnet:
- Zylindrische Tankgeometrie (oberirdisch oder unterirdisch)
- Separate U-Werte für Decke, Seitenwände und Boden
- Oberflächen-zu-Volumen-Verhältnis (bessere Skalierung für große Speicher)

### 4. Piecewise-Linear Verlustmodellierung

Verluste variieren mit dem Füllstand des Speichers (optional):
- Höherer Füllstand → mehr heiße Zone → höhere Verluste
- Niedrigerer Füllstand → mehr kalte Zone → niedrigere Verluste

## Physikalisches Modell

### Energiebilanz

```
E_total[t] = ρ × (V_hot[t] × T_hot + V_cold[t] × T_cold) × cp / 3600000 [MWh]
```

Mit:
- ρ = 1000 kg/m³ (Wasserdichte)
- cp = 4.186 kJ/(kg·K) (spez. Wärmekapazität)
- V_hot[t], V_cold[t] in m³
- T_hot, T_cold in °C

### Volumendynamik

```
V_hot[t] = V_hot[t-1] + ΔV_charge - ΔV_discharge - V_loss
```

Wobei:
```
ΔV_charge = (η_c × Q_c[t] × Δt) / (ρ × cp × ΔT / 3600000)
ΔV_discharge = (Q_d[t] × Δt / η_d) / (ρ × cp × ΔT / 3600000)
```

### Wärmeverluste

```
Q_loss = U_top × A_top × (T_hot - T_ambient) +
         U_side × A_side × ratio_hot × (T_hot - T_ambient) +
         U_side × A_side × (1 - ratio_hot) × (T_cold - T_ambient) +
         U_bottom × A_bottom × (T_bottom - T_ground)
```

## Verwendung

### Grundlegendes Beispiel

```python
from energis.models.blocks.stratified_storage import StratifiedStorageBlock

# Fernwärme-Pufferspeicher
storage = StratifiedStorageBlock(
    name="DH_Buffer",
    # Thermische Parameter
    T_hot_C=90.0,
    T_cold_C=40.0,
    T_ambient_C=15.0,
    T_ground_C=10.0,
    # Geometrie (wird automatisch berechnet)
    aspect_ratio=1.5,  # H/D-Verhältnis
    geometry_type="tank",  # "tank" oder "pit"
    # Wärmeübertragung
    U_top=0.3,    # W/(m²·K) - Decke
    U_side=0.2,   # W/(m²·K) - Seite
    U_bottom=0.15,  # W/(m²·K) - Boden
    # Effizienz
    eff_c=0.95,
    eff_d=0.95,
    # Investment
    investable=True,
    e_cap_min=100.0,   # MWh
    e_cap_max=500.0,   # MWh
    p_cap_min=10.0,    # MW
    p_cap_max=50.0     # MW
)
```

### Saisonaler Erdbeckenspeicher (PTES)

```python
storage_ptes = StratifiedStorageBlock(
    name="Seasonal_PTES",
    # Höhere Temperaturspreizung
    T_hot_C=95.0,
    T_cold_C=30.0,
    T_ambient_C=10.0,
    T_ground_C=8.0,
    # PTES-Geometrie (flach, groß)
    aspect_ratio=0.4,  # H/D ~ 0.3-0.5
    geometry_type="pit",
    # Exzellente Isolierung (Erdreich)
    U_top=0.2,     # Isolierte Abdeckung
    U_side=0.05,   # Erdreich
    U_bottom=0.02,  # Tiefes Erdreich
    # Große Kapazität
    investable=True,
    e_cap_min=5000.0,
    e_cap_max=50000.0,
    p_cap_min=50.0,
    p_cap_max=500.0,
    # Hohe Effizienz
    eff_c=0.98,
    eff_d=0.98,
    # Feinere Piecewise-Linearisierung
    piecewise_n_points=10
)
```

### YAML-Konfiguration

```yaml
system:
  storage:
    - id: seasonal_storage
      component_type: stratified_storage
      # Thermal
      T_hot_C: 90.0
      T_cold_C: 40.0
      T_ambient_C: 10.0
      T_ground_C: 8.0
      # Geometry
      aspect_ratio: 0.4
      geometry_type: pit
      # Heat transfer [W/(m²·K)]
      U_top: 0.2
      U_side: 0.05
      U_bottom: 0.02
      # Efficiency
      eff_c: 0.98
      eff_d: 0.98
      # Capacity
      investable: true
      e_cap_min: 5000.0
      e_cap_max: 50000.0
      p_cap_min: 50.0
      p_cap_max: 500.0
      # Initial state
      soc0: 10000.0
      V_hot_init_fraction: 0.6
      enabled: true
```

## Vergleich: Simple vs. Stratified Storage

| Feature | SimpleStorage | StratifiedStorage |
|---------|---------------|-------------------|
| **Temperaturmodell** | Well-mixed, einheitlich | Zwei Zonen (hot/cold) |
| **Verlustmodell** | Konstanter Prozentsatz | Geometriebasiert |
| **Skalierung** | Nicht optimal für große Speicher | Skaliert gut mit Größe |
| **COP-Kopplung** | Nicht möglich | Erweiterbar |
| **Rechenzeit** | Schnell | Moderat |
| **Anwendung** | Kurzzeit-Puffer (Stunden-Tage) | Groß- und Saisonspeicher |
| **Typische Größe** | 10-100 MWh | 1.000-50.000 MWh |

## Typische Parameter für verschiedene Speichertypen

### Fernwärme-Pufferspeicher (100-500 MWh)

```python
T_hot_C=90.0
T_cold_C=40.0
aspect_ratio=1.5  # Oberirdischer Tank
U_top=0.3
U_side=0.2
U_bottom=0.15
```

**Ergebnisse:**
- Volumen: ~1.700-8.600 m³
- Durchmesser: ~11-19 m
- Höhe: ~17-28 m
- Täglicher Verlust: ~2-5%

### Saisonalspeicher PTES (10.000-50.000 MWh)

```python
T_hot_C=95.0
T_cold_C=30.0
aspect_ratio=0.4  # Flacher Erdbe cken
U_top=0.1-0.2  # Isolierte Abdeckung
U_side=0.02-0.05  # Erdreich
U_bottom=0.01-0.02  # Tiefes Erdreich
```

**Ergebnisse:**
- Volumen: ~140.000-700.000 m³
- Durchmesser: ~75-130 m
- Höhe: ~30-50 m
- Jährlicher Verlust: ~5-15% (mit guter Isolierung)

## Hinweise zur Kalibrierung

### U-Werte ermitteln

1. **Oberirdische Tanks:**
   - U_top: 0.2-0.5 W/(m²·K) (abhängig von Isolierung)
   - U_side: 0.15-0.3 W/(m²·K)
   - U_bottom: 0.1-0.2 W/(m²·K)

2. **Erdbeckenspeicher (PTES):**
   - U_top: 0.05-0.2 W/(m²·K) (isolierte Abdeckung)
   - U_side: 0.01-0.05 W/(m²·K) (Erdreich)
   - U_bottom: 0.005-0.02 W/(m²·K) (tiefes Erdreich)

3. **Aus Messungen:**
   ```python
   # Gemessener Energieverlust über Zeit
   E_loss_measured_MWh = 100  # MWh über einen Monat
   t_hours = 720  # Stunden
   delta_T_avg = 70  # K (durchschnittliche Temperaturdifferenz)
   A_total = geometry["A_total_m2"]

   # Durchschnittlicher U-Wert
   U_avg = (E_loss_measured_MWh * 1000) / (A_total * delta_T_avg * t_hours)
   ```

### Verluste validieren

```python
storage = StratifiedStorageBlock(...)
summary = storage.get_summary()

print(f"Jährliche Verlustrate: {summary['losses']['annual_loss_rate_pct']:.2f}%")

# Typische Werte:
# - Kurzzeit-Puffer: 50-80% pro Jahr (OK, da nicht für Langzeit gedacht)
# - Wochenspeicher: 20-40% pro Jahr
# - Saisonspeicher: 5-15% pro Jahr
```

## Erweiterte Funktionen

### Piecewise-Linear Verluste

```python
storage = StratifiedStorageBlock(
    ...,
    piecewise_n_points=10  # Mehr Punkte = genauer
)

# Verlustdaten abfragen
loss_data = storage.calculate_loss_piecewise_data()
print(loss_data)
# {
#   "breakpoints": [0.0, 0.1, 0.2, ..., 1.0],
#   "energy_losses": [Q_loss_MW für jedes ratio_hot],
#   "volume_losses": [V_loss_m3_per_h für jedes ratio_hot]
# }
```

### Zusammenfassung abrufen

```python
summary = storage.get_summary()
print(summary)
# {
#   "thermal": {T_hot, T_cold, delta_T, ...},
#   "geometry": {volume, diameter, height, A_total, ...},
#   "capacity": {E_max, E_cap_range, P_cap_range, ...},
#   "losses": {avg_loss_MW, annual_loss_rate_pct, ...},
#   "efficiency": {charge, discharge, roundtrip}
# }
```

## Limitationen

1. **Fixe Temperaturen**: Temperaturen variieren nicht mit Betrieb
   - Gut für: Fernwärmenetze mit festen Vor-/Rücklauftemperaturen
   - Einschränkung: Keine COP-Variation mit Speichertemperatur

2. **Zwei Zonen**: Keine feinere vertikale Auflösung
   - Gut für: Grobe Abschätzung, schnelle Optimierung
   - Einschränkung: Thermokline-Dynamik vereinfacht

3. **Vereinfachte Verlustallokation**: Verluste primär der heißen Zone zugeordnet
   - Gut für: Konservative Abschätzung
   - Einschränkung: Nicht exakt für komplexe Lastprofile

## Weiterführende Entwicklung

Mögliche Erweiterungen:

1. **Temperaturvariable Modellierung** (mit Linearisierung)
2. **Multi-Layer-Stratifikation** (N Schichten)
3. **COP-Kopplung** für Wärmepumpen
4. **Dynamische U-Werte** (temperaturabhängig)
5. **Saisonale Bodentemperatur-Variation**

## Beispiele

Siehe:
- `examples/stratified_storage_example.py` - Vollständige Beispiele
- `exports/stratified_storage_example.json` - Exported data

## Referenzen

Weitere Informationen zur Implementierung:
- `energis/models/blocks/stratified_storage.py` - Hauptimplementierung
- `energis/models/blocks/storage.py` - Einfaches Speichermodell (Vergleich)
- `examples/custom_component_example.py` - Component Registry Pattern
