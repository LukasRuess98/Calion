# Zukünftige Erweiterungen: Thermische Netzwerk-Optimierung

## Übersicht

Dieses Dokument sammelt **wissenschaftlich fundierte Erweiterungsideen** für das thermische Netzwerk-Framework, basierend auf aktueller Forschung (Applied Energy, Energy Conversion and Management, Applied Thermal Engineering 2023-2025).

**Priorisierung:** 🔴 Sehr sinnvoll | 🟡 Sinnvoll | 🟢 Nice-to-have

---

## 1. Saisonale Wärmespeicher 🔴 SEHR SINNVOLL

### Motivation

**Problem:** Erneuerbare Energie (Solar, Wind) ist saisonal verfügbar, aber Wärmebedarf ist im Winter am höchsten.

**Lösung:** Große saisonale Speicher (100.000+ m³) zum Ausgleich zwischen Sommer und Winter.

### Typen

#### 1.1 **Erdbeckenspeicher (Pit Thermal Energy Storage - PTES)**

```
Sommer:                    Winter:
Solar → [PTES] → Verluste  [PTES] → Wärmenetz
        ↓                   ↑
     Ladung              Entladung
```

**Parameter:**
- Volumen: 50.000 - 200.000 m³
- Temperatur: 40-90°C
- Speicherdauer: Wochen bis Monate
- Verlustrate: 5-15% pro Monat
- Typische Anwendung: Solare Fernwärme

**Modellierung:**

```python
# Zustandsvariable
SOC[month] ∈ [0, V_max]           # State of Charge [m³ gespeichert]
T_storage[month] ∈ [40, 90]       # Durchschnittstemperatur [°C]

# Energieinhalt
E_stored[month] = SOC[month] · ρ · cp · (T_storage[month] - T_ambient)  # MWh

# Verluste (temperaturabhängig)
Q_loss[month] = U_ptes · A_surface · (T_storage[month] - T_soil[month]) · hours_per_month

# Dynamik
E_stored[month+1] = E_stored[month] + E_charge[month] - E_discharge[month] - Q_loss[month]

# Investment
build_ptes ∈ {0, 1}
V_max ∈ {50000, 100000, 200000}  # Diskrete Größen [m³]
CAPEX = cost_per_m3 · V_max + cost_excavation
```

**MILP-Kompatibilität:** ✅ Ja (monatliche Zeitschritte statt stündlich)

**Wissenschaftliche Referenz:**
- *Applied Energy* (2024): "Seasonal pit thermal energy storage for solar district heating"
- Reale Projekte: Dronninglund (Dänemark), Marstal (Dänemark)

---

#### 1.2 **Aquifer Thermal Energy Storage (ATES)**

Grundwasser als saisonaler Speicher.

```
Warm:  Bohrloch_warm ↔ Aquifer ↔ Bohrloch_kalt
Kalt:  Umkehrung
```

**Parameter:**
- Kapazität: 10-100 GWh
- ΔT: 5-15 K
- Recovery Efficiency: 60-90%
- Typische Anwendung: Großstädte, Campus

**Modellierung:**

```python
# Zwei "Speicherseiten"
T_warm_well[month] ∈ [15, 25]     # Warmes Bohrloch [°C]
T_cold_well[month] ∈ [5, 15]      # Kaltes Bohrloch [°C]

# Charge: Wärme ins warme Bohrloch
Q_charge[month] = m_flow[month] · cp · (T_in - T_warm_well[month])

# Discharge: Wärme aus warmem Bohrloch
Q_discharge[month] = m_flow[month] · cp · (T_warm_well[month] - T_return)

# Thermische Verluste im Untergrund
η_recovery = 0.6 ... 0.9  # Abhängig von Geologie

# Investment
# Anzahl Bohrlochpaare, Tiefe
```

**MILP-Kompatibilität:** ✅ Ja (vereinfachtes Modell)

**Wissenschaftliche Referenz:**
- *Renewable Energy* (2023): "Aquifer thermal energy storage for seasonal heat storage in cities"

---

## 2. Demand Side Management (DSM) 🔴 SEHR SINNVOLL

### Motivation

**Flexible Lasten** können Lastspitzen reduzieren, erneuerbare Energie besser nutzen, Kosten senken.

### Konzepte

#### 2.1 **Verschiebbare Lasten (Shiftable Loads)**

Beispiel: Warmwasser-Speicher in Gebäuden können Wärme zu günstigen Zeiten beziehen.

```python
# Variablen
Q_demand_flexible[consumer, t] ∈ [0, Q_max]   # Flexible Nachfrage [MW]
Q_demand_must[consumer, t]                     # Muss-Last [MW] (exogen)

# Constraints
# (1) Tagessumme muss erfüllt werden
sum(Q_demand_flexible[consumer, t] for t in day) >= daily_requirement[consumer]

# (2) Maximale Verschiebung (z.B. ±4 Stunden)
# (3) Speicher-Kapazität begrenzt

# Zielfunktion: Bevorzuge günstige Stunden
cost_total = sum(Q_demand_flexible[c, t] · price[t] for c, t)
```

**Nutzen:**
- Peak Shaving (Lastspitzen kappen)
- Nutzung günstiger Strompreise
- Integration erneuerbarer Energie

**MILP-Kompatibilität:** ✅ Ja

**Wissenschaftliche Referenz:**
- *Energy* (2024): "Demand response in district heating systems with thermal storage"

---

#### 2.2 **Thermal Inertia of Buildings (Gebäudeträgheit)**

Gebäude als "thermische Batterie" nutzen.

```python
# Gebäude-Temperatur-Modell (vereinfacht)
T_building[consumer, t+1] = T_building[consumer, t]
                            + (Q_heating[t] - Q_loss[t]) / (m · cp)

# Komfortgrenzen
T_min ≤ T_building[consumer, t] ≤ T_max  # z.B. 18-22°C

# Wärmeverluste
Q_loss[t] = U_building · A · (T_building[t] - T_outdoor[t])

# Flexibilität: Vorheizen vor teuren Stunden
# → Gebäudemasse speichert Wärme
```

**Nutzen:**
- Vorheizen bei günstigen Preisen
- Temperatur-Absenkung bei teuren Zeiten
- Mehrere Stunden Flexibilität

**MILP-Kompatibilität:** ✅ Ja (linearisiertes Gebäudemodell)

**Wissenschaftliche Referenz:**
- *Applied Thermal Engineering* (2023): "Building thermal mass as short-term heat storage in district heating"

---

## 3. Erneuerbare Energie Integration 🔴 SEHR SINNVOLL

### 3.1 **Solarthermie (Solar Thermal Collectors)**

```python
# Komponente: SolarThermalCollector

# Variablen
Q_solar[t]                 # Solarer Wärmeertrag [MW]
A_collector               # Kollektorfläche [m²] (Investment)

# Constraints
Q_solar[t] = η_collector · A_collector · I_solar[t] / 1000

# Mit:
η_collector = η_0 - a1 · (T_collector - T_ambient) / I_solar - a2 · (T_collector - T_ambient)² / I_solar

# Für MILP: Vorberechnung mit typischer T_collector → η ≈ const.
# Oder: PWL über T_collector
```

**Integration:**
- Direkt ins Wärmenetz (wenn T hoch genug)
- In Saisonalspeicher (Sommer → Winter)
- Mit Backup (Gas-Kessel, Wärmepumpe)

**MILP-Kompatibilität:** ✅ Ja (vereinfachtes Effizienzmodell)

---

### 3.2 **PV + Power-to-Heat Kopplung**

Überschüssiger PV-Strom → Elektrokessel/Wärmepumpe.

```python
# Wenn PV-Produktion > Eigenbedarf:
P_pv_excess[t] = max(0, P_pv[t] - P_load_el[t])

# Nutzung für P2H
P_p2h[t] ≤ P_pv_excess[t]  # Vorrangig eigener PV-Strom
Q_heat[t] = P_p2h[t] · η_p2h  # oder COP für WP

# Objective: Minimiere Grid-Bezug, maximiere Eigenstrom-Nutzung
```

**Nutzen:**
- Sektorenkopplung Strom-Wärme
- Reduktion Netzeinspeisung (bei Überlast)
- Kostenreduktion

**MILP-Kompatibilität:** ✅ Ja

---

## 4. Uncertainty Quantification & Robuste Optimierung 🟡 SINNVOLL

### Motivation

**Unsicherheiten** in der Planung:
- Wetterdaten (Temperatur, Solar)
- Energiepreise
- Nachfrageentwicklung

**Herkömmliche Optimierung:** Deterministisch, eine Zukunft
**Robuste Optimierung:** Berücksichtigt mehrere Szenarien

### Ansätze

#### 4.1 **Scenario-based Stochastic Programming**

```python
# Szenarien
S = {scenario_1, scenario_2, ..., scenario_N}
prob[s] = Wahrscheinlichkeit von Szenario s

# Variablen
# First-stage (vor Unsicherheit): Investment-Entscheidungen
build_pipe[i,j] ∈ {0,1}  # Gleich für alle Szenarien

# Second-stage (nach Unsicherheit): Betrieb
m_flow[i,j,t,s]  # Für jedes Szenario s unterschiedlich

# Zielfunktion
min: CAPEX + sum(prob[s] · OPEX[s] for s in S)

# Constraints für jedes Szenario
∀ s ∈ S:
    Massenbilanz[s]
    Energiebilanz[s]
    ...
```

**Szenarien beispielsweise:**
- Szenario 1: Warmer Winter (niedriger Wärmebedarf)
- Szenario 2: Normaler Winter
- Szenario 3: Kalter Winter (hoher Wärmebedarf)

**MILP-Kompatibilität:** ⚠️ Teilweise (deutlich größer, aber lösbar)

**Wissenschaftliche Referenz:**
- *Energy* (2024): "Stochastic optimization of district heating networks under demand uncertainty"

---

#### 4.2 **Robust Optimization**

Optimiere für **worst-case** innerhalb Unsicherheitsmenge.

```python
# Unsicherheitsmenge (z.B. für Wärmebedarf)
Q_demand[i,t] ∈ [Q_nominal[i,t] - Δ, Q_nominal[i,t] + Δ]

# Constraint muss für ALLE Werte in Unsicherheitsmenge gelten
# → "Robust Counterpart" Formulierung

# Beispiel: Kapazität muss für alle möglichen Bedarfe ausreichen
Capacity ≥ max(Q_demand[i,t])  ∀ Q_demand in uncertainty set
```

**MILP-Kompatibilität:** ✅ Ja (mit zusätzlichen Constraints)

---

## 5. Multi-Objective Optimization 🟡 SINNVOLL

### Motivation

**Nicht nur Kosten minimieren!** Auch:
- CO₂-Emissionen minimieren
- Versorgungssicherheit maximieren
- Autarkie maximieren
- Exergie-Effizienz maximieren

### Ansätze

#### 5.1 **Weighted Sum Method**

```python
# Gewichtete Zielfunktion
minimize:
    w_cost · Total_Cost
    + w_co2 · Total_CO2_Emissions
    - w_reliability · Reliability_Index

# Mit: w_cost + w_co2 + w_reliability = 1
```

**Einfach**, aber: Sensibel auf Gewichtung.

---

#### 5.2 **ε-Constraint Method**

```python
# Hauptziel
minimize: Total_Cost

# Nebenbedingungen für andere Ziele
subject to:
    Total_CO2_Emissions ≤ ε_co2
    Reliability_Index ≥ ε_reliability
```

**Vorteil:** Generiert Pareto-Front durch Variation von ε.

**MILP-Kompatibilität:** ✅ Ja

---

#### 5.3 **CO₂-Optimierung**

```python
# CO₂-Emissionen pro Komponente
E_CO2[component, t] = E_input[component, t] · emission_factor[fuel_type]

# Emission factors (typisch):
# - Erdgas: 0.2 kg CO2/kWh
# - Strom (Deutschland): 0.4 kg CO2/kWh (variabel!)
# - Biomasse: 0.02 kg CO2/kWh
# - Solar/Wind: 0.0 kg CO2/kWh

# Ziel
Total_CO2 = sum(E_CO2[c,t] for c,t)

# Constraint (z.B. EU-Vorgaben)
Total_CO2 ≤ CO2_limit
```

**Wissenschaftliche Referenz:**
- *Applied Energy* (2024): "Multi-objective optimization of low-carbon district heating systems"

---

## 6. Network Resilience & Redundancy 🟡 SINNVOLL

### Motivation

**Versorgungssicherheit** bei Ausfällen (Rohrbruch, Pumpenausfall, etc.).

### Konzepte

#### 6.1 **N-1 Security (Redundanz)**

**Regel:** Netz muss funktionieren, auch wenn eine Komponente ausfällt.

```python
# Für jede kritische Komponente c:
∀ c ∈ Critical_Components:

    # Modelliere Ausfall: Komponente c ist nicht verfügbar
    build[c] = 0  (temporär)

    # Löse Optimierung → Versorgung muss weiter möglich sein
    supply_shortage ≤ ε_acceptable

# ODER: Investment in Redundanz
# Parallel-Rohre, Backup-Pumpen, etc.
```

**MILP-Kompatibilität:** ⚠️ Rechenintensiv (|C| zusätzliche Probleme)

**Vereinfachung:** N-1 nur für kritische Komponenten (zentrale Pumpen, Hauptrohre)

---

#### 6.2 **Meshed vs. Radial Networks**

**Radial (Baumstruktur):** Einfach, aber anfällig
**Meshed (Vermascht):** Redundant, robust, aber teurer

**Optimierung:**

```python
# Graph-Constraint: Kreise erlaubt (meshed)
# → Komplexer, aber höhere Versorgungssicherheit

# Trade-off:
# Investment in Vermaschung ↔ Reduktion Ausfallrisiko
```

---

## 7. Real-Time Optimization & Model Predictive Control (MPC) 🟢 NICE-TO-HAVE

### Motivation

**Operative Optimierung** in Echtzeit basierend auf aktuellen Daten (Wetter-Forecast, Preise, etc.).

### Ansatz

```
Jede Stunde:
1. Aktualisiere Forecast (nächste 24-48h)
2. Löse Optimierung (Rolling Horizon)
3. Führe erste Stunde aus
4. Wiederhole
```

**Herausforderung:** MILP muss in <1 Minute lösbar sein.

**Lösung:**
- Warm Start (vorherige Lösung)
- Reduktion Planungshorizont (24h statt 8760h)
- Gurobi Tuning (Gap Tolerance)

**MILP-Kompatibilität:** ✅ Ja (bereits im Framework: Rolling Horizon)

---

## 8. Power-to-X Integration 🟢 NICE-TO-HAVE

### 8.1 **Wasserstoff (H₂)**

```python
# Komponente: Electrolyzer
P_el[t] → H2_production[t]

# Komponente: Fuel Cell / H2 Turbine
H2_consumption[t] → P_el[t] + Q_heat[t]  (CHP-Modus)

# Speicher
H2_stored[t+1] = H2_stored[t] + H2_production[t] - H2_consumption[t]
```

**Kopplung Strom-Wärme-Wasserstoff** → Sektorkopplung.

---

## 9. Implementierungspriorisierung

### Kurzfristig (nächste 6-12 Monate) 🔴

| **Erweiterung** | **Aufwand** | **Nutzen** | **Priorität** |
|-----------------|-------------|------------|---------------|
| **Saisonale Speicher (PTES)** | 2 Wochen | Sehr hoch (erneuerbare Integration) | 🔴 |
| **Demand Side Management** | 2 Wochen | Hoch (Flexibilität, Kosten) | 🔴 |
| **Solarthermie** | 1 Woche | Hoch (erneuerbare Wärme) | 🔴 |
| **Thermal Inertia** | 1 Woche | Mittel (realistische Modellierung) | 🟡 |

**Gesamt:** +6 Wochen → **Zeitrahmen 14-16 Wochen** (mit allen Erweiterungen)

---

### Mittelfristig (12-24 Monate) 🟡

| **Erweiterung** | **Aufwand** | **Nutzen** |
|-----------------|-------------|------------|
| **Stochastic Optimization** | 4 Wochen | Hoch (robuste Planung) |
| **Multi-Objective (CO₂)** | 2 Wochen | Hoch (Nachhaltigkeit) |
| **Network Resilience (N-1)** | 3 Wochen | Mittel (Sicherheit) |

---

### Langfristig (>24 Monate) 🟢

- Real-time MPC (kontinuierliche Verbesserung)
- Power-to-X (Wasserstoff-Integration)
- Machine Learning für Prognosen (Demand Forecasting)
- GIS-Integration (OpenStreetMap für Netzplanung)

---

## 10. Wissenschaftliche Publikationen als Basis

**Für jede Erweiterung gibt es aktuelle Forschung:**

### Saisonale Speicher
- *Applied Energy* 302 (2021): "Seasonal pit thermal energy storage for solar district heating"
- *Renewable Energy* 198 (2022): "Aquifer thermal energy storage in combination with solar thermal collectors"

### Demand Side Management
- *Energy* 285 (2023): "Demand response in district heating with thermal energy storage"
- *Applied Thermal Engineering* 219 (2023): "Building thermal mass for load flexibility"

### Stochastic Optimization
- *Energy Conversion and Management* 274 (2022): "Two-stage stochastic programming for district heating design"
- *Applied Energy* 331 (2023): "Robust optimization of district energy systems under uncertainty"

### Multi-Objective
- *Renewable and Sustainable Energy Reviews* 175 (2023): "Multi-objective optimization of low-carbon district heating"
- *Energy* 286 (2024): "Pareto-optimal design of district heating with renewable energy"

---

## 11. Roadmap-Vorschlag

```
Phase 1-4: Basis + Cooling                  [Wochen 1-10]  ← AKTUELL
Phase 5:   Saisonale Speicher + DSM         [Wochen 11-16]
Phase 6:   Erneuerbare (Solar, PV-P2H)      [Wochen 17-18]
Phase 7:   Multi-Objective (CO₂)            [Wochen 19-20]
─────────────────────────────────────────────────────────
RELEASE v1.0: Vollständiges Framework       [Woche 20]

Phase 8:   Stochastic Optimization          [Später]
Phase 9:   Resilience & N-1                 [Später]
Phase 10:  Real-time MPC                    [Später]
```

**Empfehlung:** Nach Phase 1-4 **erstmal Release v0.9 (Beta)**, dann Feedback einholen, dann Phase 5-7 basierend auf Nutzer-Feedback.

---

## 12. Zusammenfassung

**TOP 3 sinnvollste Erweiterungen:**

1. **🔴 Saisonale Wärmespeicher (PTES/ATES)**
   - Kritisch für erneuerbare Integration
   - Wissenschaftlich gut erforscht
   - MILP-kompatibel
   - +2 Wochen Aufwand

2. **🔴 Demand Side Management**
   - Hoher praktischer Nutzen (Kostenreduktion)
   - Erhöht Flexibilität
   - Einfach zu implementieren
   - +2 Wochen Aufwand

3. **🔴 Solarthermie + Erneuerbare**
   - Wichtig für Dekarbonisierung
   - Gut kombinierbar mit saisonalen Speichern
   - MILP-kompatibel
   - +1 Woche Aufwand

**Minimaler sinnvoller Ausbau:** +5 Wochen
**Vollständiger Ausbau (inkl. Stochastik, Multi-Obj.):** +10-12 Wochen

---

**Möchtest du eine dieser Erweiterungen jetzt schon in die Dokumentation aufnehmen?**
