# Analyse: Paper 1 vs. EnerGIS Framework

## Executive Summary

Dieses Dokument analysiert den Entwurf für Paper 1 ("High-Fidelity Thermo-Hydraulic Modeling of Electrified District Heating Networks") im Vergleich zur aktuellen Implementierung des EnerGIS Frameworks. Die Analyse identifiziert:

- **Gut umgesetzt**: Grundlegende Komponenten vorhanden
- **Lücken im Framework**: Fehlende Features für Paper-Ansprüche
- **Anpassungen am Paper**: Realistische Darstellung der Implementierung

---

## 1. Detaillierte Komponentenanalyse

### 1.1 Hydraulisches Netzwerkmodell

#### Paper-Anspruch (Section 2.2)
| Feature | Paper-Beschreibung | Status |
|---------|-------------------|--------|
| Massenerhaltung (Eq. 1) | Σ ṁ_in = Σ ṁ_out an jedem Knoten | ✅ Implementiert |
| Darcy-Weisbach (Eq. 2) | ΔP = f·(L/D)·(ρv²/2) | ⚠️ Vereinfacht |
| Colebrook-White (Eq. 4) | Implizite Reibungsfaktor-Berechnung | ❌ Nicht implementiert |
| Swamee-Jain (Eq. 5) | Explizite Approximation | ✅ Implementiert |
| Kirchhoff Schleifen (Eq. 6) | Σ ΔP = 0 für geschlossene Schleifen | ❌ Nicht implementiert |
| Newton-Raphson Solver (Alg. 1) | Iterative Lösung des gekoppelten Systems | ❌ Nicht implementiert |

#### Aktuelle Framework-Implementierung
```python
# pipe_pair.py:455-506
# Vereinfachte lineare Druckverlust-Approximation für MILP:
k_linear = k_pressure * max_velocity**2 / effective_max_flow
delta_p_supply[t] == k_linear * m_dot[t]
```

**Bewertung**: Das Framework verwendet eine **linearisierte Druckverlust-Approximation** statt der vollständigen Newton-Raphson Lösung. Dies ist für MILP-Optimierung notwendig, entspricht aber nicht dem Paper-Anspruch eines "high-fidelity" hydraulischen Modells.

**Empfehlung**:
- **Framework**: Newton-Raphson Solver für Post-Optimierung Validierung implementieren
- **Paper**: Klarstellen, dass hydraulisches Gleichgewicht nur für Validierung (nicht Optimierung) iterativ gelöst wird

---

### 1.2 Thermisches Rohrmodell

#### Paper-Anspruch (Section 2.3)
| Feature | Paper-Beschreibung | Status |
|---------|-------------------|--------|
| 1D Energieerhaltung (Eq. 7) | ρ·cp·A·∂T/∂t + ρ·cp·A·v·∂T/∂x = -U·π·D·(T-T_amb) | ⚠️ Vereinfacht |
| FDM Diskretisierung (Eq. 8) | Implicit upwind mit N Segmenten pro Rohr | ❌ Nicht implementiert |
| Temperaturabhängige U-Werte (Eq. 10) | λ(T) = λ₀·(1 + β·(T-T_ref)) | ✅ Unterstützt |
| Wärmeverlustreihenwiderstand (Eq. 9) | U = [1/α_inner + Σ ln(r/r)/2πλ + 1/α_soil]⁻¹ | ⚠️ Vereinfacht |

#### Aktuelle Framework-Implementierung
```python
# pipe_pair.py:250-286, network_physics.py:44-57
# Vereinfachte Wärmeverlustberechnung:
Q_loss = U * L * (T_avg - T_ground) / 1e6  # [MW]
```

**Bewertung**: Das Framework implementiert:
- Wärmeverlust Q = U·L·ΔT (korrekt)
- **Keine** Finite-Differenzen-Diskretisierung entlang der Rohre
- **Keine** dynamische Temperaturpropagation (Plug-Flow-Ansatz fehlt)
- Brownfield-Modus: Feste Temperaturen ohne Dynamik

**Empfehlung**:
- **Framework**: Optionale FDM-Diskretisierung für Validierungszwecke hinzufügen
- **Paper**: Tabelle 2 (Komplexitätsstufen) anpassen - L1-L3 ohne Rohr-Diskretisierung

---

### 1.3 Wärmepumpenmodell

#### Paper-Anspruch (Section 2.4)
| Feature | Paper-Beschreibung | Status |
|---------|-------------------|--------|
| Lorenz COP (Eq. 11) | COP = η_Lorenz · T̄_sink / (T̄_sink - T̄_source) | ⚠️ Vereinfacht (Carnot) |
| Jensen Linearisierung (Eq. 12) | COP ≈ a₀ + a₁·T_source + a₂·T_sink | ❌ Nicht explizit |
| Teillast-Performance (Eq. 13-14) | COP_PLR = COP_nom · f_PLR(PLR) | ⚠️ Nur min_load |
| Energiebilanzen (Eq. 15-16) | Q_HP = Q_source + P_el | ✅ Implementiert |

#### Aktuelle Framework-Implementierung
```python
# heat_pump.py:111-115, configs/01_tech/heat_pumps.yaml
# COP als Zeitreihe (extern berechnet):
COP_series[t]  # Vorgegeben, nicht im Modell berechnet

# Vereinfachte Carnot-Effizienz:
eta: 0.75  # Carnot efficiency
```

**Bewertung**:
- COP wird **extern** berechnet und als Zeitreihe übergeben
- Keine explizite Lorenz-Formel im Framework
- Teillast nur über min_load (30%), keine quadratische PLR-Kurve
- Kein temperaturabhängiges COP-Modell im Optimierer

**Empfehlung**:
- **Framework**: Jensen-Linearisierung für COP(T_source, T_sink) hinzufügen
- **Paper**: Klarstellen, dass COP extern (z.B. via TESPy) berechnet und als Parameter übergeben wird

---

### 1.4 Thermischer Speicher

#### Paper-Anspruch (Section 2.5)
| Feature | Paper-Beschreibung | Status |
|---------|-------------------|--------|
| Multi-Node Stratifizierung (Eq. 17) | N horizontale Schichten | ⚠️ Nur 2-Zonen |
| Wärmeleitung (Eq. 18) | Q_cond = λ_eff·A/Δz·(T_i-1 - 2T_i + T_i+1) | ❌ Nicht implementiert |
| Wandverluste (Eq. 19) | Q_loss = U_tank·A·(T - T_amb) | ✅ Implementiert |
| SOC Definition (Eq. 20) | Energiebasiert | ✅ Implementiert |

#### Aktuelle Framework-Implementierung

**StorageBlock** (storage.py):
```python
# Einfaches Single-State Modell:
E[t] = E[t-1] · loss + eff_c · Qc[t] · dt - Qd[t]/eff_d · dt
```

**StratifiedStorageBlock** (stratified_storage.py):
```python
# 2-Zonen Modell (Hot/Cold):
V_hot[t] + V_cold[t] = V_total
E_total[t] = e_specific * T_hot * V_hot[t] + e_specific * T_cold * V_cold[t]
```

**Bewertung**:
- **2-Zonen** statt Multi-Node (N Schichten)
- Geometriebasierte Verluste korrekt implementiert
- Keine Wärmeleitung zwischen Schichten (Konduktion)
- Für MILP geeignet, aber weniger genau als Paper suggeriert

**Empfehlung**:
- **Paper**: Tabelle 2 anpassen: L2 = 2-Zonen (implementiert), L3+ = Multi-Node (optional)
- **Framework**: Optional N-Node Modell für Validierung hinzufügen

---

## 2. Komplexitätsstufen (L1-L5)

### Paper-Anspruch (Table 2)
| Level | Netzwerk | TES | COP | MILP | Anwendung |
|-------|----------|-----|-----|------|-----------|
| L1 | Aggregiert | Single-State | Konstant | ✓ | Screening |
| L2 | Nur Knoten | 2-Zonen | Lorenz | ✓ | Konzept |
| L3 | 5 Seg./Rohr | Multi-Node (5) | Jensen lin. | ✓ | Jahresopt. |
| L4 | 10 Seg./Rohr | Multi-Node (10) | Jensen nonl. | - | Detailopt. |
| L5 | 50 Seg./Rohr | 3D-FEM | Thermo. | - | Validierung |

### Aktuelle Framework-Implementierung

| Level | Verfügbar | Beschreibung |
|-------|-----------|--------------|
| L1 | ✅ | Aggregiertes Modell (heat balance ohne Netzwerk) |
| L2 | ⚠️ | Brownfield-Modus: Knoten + 2-Zonen TES |
| L3 | ❌ | **Nicht implementiert** - keine Rohr-Diskretisierung |
| L4 | ❌ | **Nicht implementiert** |
| L5 | ❌ | **Nicht implementiert** |

**Kritische Lücke**: Das Framework unterstützt keine Rohr-Diskretisierung (Segmente pro Rohr). Alle Komplexitätsstufen L3-L5 sind **nicht verfügbar**.

**Empfehlungen**:
- **Option A (Framework erweitern)**: FDM-Rohrmodell für Validierung hinzufügen
- **Option B (Paper anpassen)**: Komplexitätsstufen realistisch beschreiben:
  - L1: Aggregiert (ohne Netzwerk)
  - L2: Brownfield mit festen Temperaturen (implementiert)
  - L3: Greenfield mit Temperaturvariablen (implementiert)
  - L4/L5: Externe Validierung (z.B. Modelica, CFD)

---

## 3. Validierung und Benchmarks

### Paper-Anspruch (Section 4-5)
| Feature | Beschreibung | Status |
|---------|--------------|--------|
| CFD Benchmark | Vergleich mit 3D CFD | ❌ Keine Infrastruktur |
| RMSE/MBE/MAPE | Validierungsmetriken | ❌ Nicht implementiert |
| Echtdaten-Validierung | 12 Monate Betriebsdaten | ⚠️ Datenstruktur vorhanden |
| Sensitivitätsanalyse | Parameter-Unsicherheit | ✅ Modul vorhanden |

**Empfehlungen**:
- **Framework**: Validierungsmodul mit Metriken (RMSE, MBE, MAPE) hinzufügen
- **Paper**: Konkrete Validierungsergebnisse erst nach Framework-Erweiterung einfügen

---

## 4. Zusammenfassende Bewertung

### Was ist gut umgesetzt (Stärken):

1. **MILP-Optimierungsframework** mit Pyomo vollständig funktional
2. **Wärmeverlustberechnung** Q = U·L·ΔT korrekt implementiert
3. **2-Zonen-Speicher** mit geometriebasierter Verlustberechnung
4. **Investitionsoptimierung** für WP, Speicher, Erzeuger
5. **Brownfield/Greenfield-Modi** unterschieden
6. **Hydraulische Post-Validierung** verfügbar

### Was fehlt oder angepasst werden muss:

| Bereich | Lücke | Priorität | Aufwand |
|---------|-------|-----------|---------|
| Newton-Raphson Hydraulik | Nicht implementiert | Hoch | Mittel |
| FDM Rohr-Diskretisierung | Nicht implementiert | Hoch | Hoch |
| Multi-Node Speicher (N>2) | Nur 2-Zonen | Mittel | Mittel |
| Jensen COP-Linearisierung | Nur externe COP | Mittel | Niedrig |
| Validierungsmetriken | Keine RMSE/MBE | Hoch | Niedrig |
| Komplexitätsstufen L3-L5 | Nicht verfügbar | Hoch | Hoch |

---

## 5. Konkrete Handlungsempfehlungen

### Option A: Framework erweitern (empfohlen für vollständiges Paper)

1. **Phase 1** (2-3 Wochen): Newton-Raphson Solver für hydraulisches Gleichgewicht
2. **Phase 2** (3-4 Wochen): FDM-Rohrmodell mit N Segmenten (für Validierung, nicht MILP)
3. **Phase 3** (1-2 Wochen): N-Node Speichermodell
4. **Phase 4** (1 Woche): Validierungsmodul mit RMSE/MBE/MAPE

### Option B: Paper anpassen (schnellere Veröffentlichung)

1. **Titel anpassen**: "MILP-Based Planning Framework" statt "High-Fidelity Modeling"
2. **Komplexitätsstufen reduzieren**: L1-L3 statt L1-L5
3. **Fokus auf Optimierung**: Weniger Simulation, mehr Planung
4. **Externe Validierung**: CFD/Modelica-Ergebnisse als Referenz importieren
5. **Ehrliche Limitationen**: Vereinfachungen klar kommunizieren

### Option C: Hybrid-Ansatz

1. Framework für L1-L2 (Optimierung) nutzen
2. Externe Tools (Modelica, TESPy) für L4-L5 (Validierung) verwenden
3. Kopplung über Zeitreihen-Export/Import

---

## 6. Paper-Struktur Anpassungsvorschläge

### Titel
**Aktuell**: "Integrated High-Fidelity Thermo-Hydraulic Modeling..."

**Vorschlag**: "A Modular MILP Framework for Planning Electrified District Heating Networks: Multi-Level Modeling and Validation"

### Abstract (Anpassungen)
- "High-fidelity" → "Computationally tractable"
- "Five complexity levels" → "Multiple complexity levels from aggregated to detailed"
- "Newton-Raphson iteration for hydraulic equilibrium" → Entfernen oder als Option beschreiben

### Section 2.2 (Hydraulic Model)
- Klarstellen: Newton-Raphson wird für **Post-Optimization Validation** verwendet, nicht im MILP
- Linearisierte Druckverluste für Optimierung beschreiben

### Table 2 (Complexity Levels)
Anpassen auf tatsächlich implementierte Features:

| Level | Netzwerk | TES | COP | Solver | Implementiert |
|-------|----------|-----|-----|--------|---------------|
| L1 | Aggregiert | Single | Konstant | MILP | ✅ |
| L2 | Brownfield | 2-Zonen | Zeitreihe | MILP | ✅ |
| L3 | Greenfield | 2-Zonen | Zeitreihe | MILP/QP | ✅ |
| L4 | + Hydraulik-Val. | Multi-Node | Jensen | NLP | Geplant |
| L5 | Externe CFD | 3D-FEM | Thermo. | - | Referenz |

---

## 7. Fazit

Das EnerGIS Framework bietet eine **solide Basis** für die Optimierung von Fernwärmenetzen mit Wärmepumpen und Speichern. Die Kernfunktionalität (MILP-Optimierung, Wärmebilanzen, Investitionsentscheidungen) ist gut implementiert.

**Jedoch** gibt es eine **signifikante Diskrepanz** zwischen dem Paper-Anspruch ("High-Fidelity Thermo-Hydraulic Modeling") und der aktuellen Implementierung. Die im Paper beschriebenen Features wie Newton-Raphson Hydraulik, FDM-Rohr-Diskretisierung und Multi-Node Speicher sind **nicht vollständig implementiert**.

**Empfohlene Strategie**:
1. Kurzfristig: Paper-Fokus auf implementierte Features ausrichten
2. Mittelfristig: Framework um Validierungskomponenten erweitern
3. Langfristig: Vollständige L1-L5 Hierarchie implementieren

---

*Analyse erstellt: 2026-01-22*
*Framework-Version: EnerGIS v1.0*
*Paper-Entwurf: Paper 1 - Energy Conversion and Management*
