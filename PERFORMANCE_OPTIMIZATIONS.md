# Performance-Optimierungen für das Berechnungsmodell

## Problem
Mit 15-Minuten-Auflösung über ein Jahr entstehen:
- **35,040 Zeitschritte** (365 Tage × 96 Schritte/Tag)
- **~280,000 Binärvariablen** (8 Binärvariablen × 35,040 Zeitschritte)
- Laufzeit: **2+ Stunden ohne Lösung** mit Gurobi

Dies ist ein extrem großes MILP-Problem, selbst für kommerzielle Solver.

## Durchgeführte Optimierungen

### 1. ✅ Big-M Wert drastisch reduziert
**Datei:** `configs/base.yaml`

**Vorher:** `big_m_grid_mw: 10000.0`
**Nachher:** `big_m_grid_mw: 200.0`

**Effekt:**
- Verbesserte numerische Stabilität
- Bessere LP-Relaxation
- Schnellere Konvergenz
- Realistische Obergrenze basierend auf Systemkapazität

**Zusätzlich:**
- `max_import_mw: 200.0` - Explizites Import-Limit
- `max_export_mw: 100.0` - Explizites Export-Limit

### 2. ✅ Gurobi Solver-Parameter optimiert
**Datei:** `configs/base.yaml`, `energis/run/orchestrator.py`

**Neue Parameter:**
```yaml
solver_options:
  MIPGap: 0.02        # 2% MIP Gap (akzeptiere Suboptimalität für Geschwindigkeit)
  TimeLimit: 3600     # 1 Stunde Zeitlimit
  Threads: 0          # Nutze alle CPU-Kerne
  MIPFocus: 1         # Fokus auf zulässige Lösungen finden
  Presolve: 2         # Aggressive Presolve
  Cuts: 2             # Aggressive Cuts
```

**Effekt:**
- MIPGap 0.02 = bis zu 2% Suboptimalität akzeptabel → **VIEL schneller**
- Zeitlimit verhindert endlose Läufe
- Optimale Solver-Einstellungen für große MILPs

### 3. ✅ Test-Konfiguration mit reduziertem Zeitraum
**Datei:** `configs/scenarios/test_1week.scenario.yaml`

**Zeitraum:** 1 Woche statt 1 Jahr
- **672 Zeitschritte** statt 35,040 (Faktor 52x kleiner!)
- **~5,400 Binärvariablen** statt 280,000 (Faktor 52x kleiner!)

**Verwendung:**
```bash
python -m energis.run.orchestrator \
  configs/base.yaml \
  configs/systems/baseline.system.yaml \
  configs/scenarios/test_1week.scenario.yaml
```

## Erwartete Verbesserungen

| Metrik | Vorher | Nachher (optimiert) |
|--------|--------|---------------------|
| Big-M Wert | 10,000 MW | 200 MW |
| MIP Gap | 0.01% | 2% (einstellbar) |
| Zeitlimit | Kein | 1 Stunde |
| Laufzeit (1 Jahr) | 2+ Stunden (keine Lösung) | ~30-60 Min (mit 2% Gap) |
| Laufzeit (1 Woche Test) | N/A | ~2-5 Minuten |

## Weitere Optimierungsmöglichkeiten

### A. Zeitauflösung reduzieren
Statt 15 Minuten → 1 Stunde:
```yaml
run:
  dt_h: 1.0  # statt 0.25
```
**Effekt:** 4x weniger Zeitschritte = 4x weniger Binärvariablen

### B. Binärvariablen eliminieren

**Wärmepumpen Min-Load:**
Wenn nicht kritisch, in `configs/tech_catalog.yaml` setzen:
```yaml
heat_pumps:
  types:
    standard:
      min_load: 0.0  # statt 0.3
```
Dann können `HP_on` Binärvariablen entfernt werden.

**Speicher-Modes:**
Die 3 Binärvariablen pro Zeitschritt (`charge_mode`, `discharge_mode`, `active`) könnten
durch SOS1-Constraints oder kontinuierliche Formulierung ersetzt werden (erfordert Code-Änderung).

### C. Investment-Entscheidungen vorfixieren
Wenn Kapazitäten bekannt sind:
```yaml
system:
  heat_pumps:
    - id: HP1
      investment:
        enabled: false
      max_th_mw: 40.0  # Fixierte Kapazität
```

### D. Rolling Horizon verwenden
Statt ganzes Jahr auf einmal:
```yaml
scenario:
  mode: PF_THEN_RH
  rolling_horizon:
    heat_horizon_hours: 168.0  # 1 Woche Vorschau
    step_hours: 24.0           # 1 Tag Schritte
```

## Empfohlenes Vorgehen

### Schritt 1: Teste mit 1 Woche
```bash
python -m energis.run.orchestrator \
  configs/base.yaml \
  configs/systems/baseline.system.yaml \
  configs/scenarios/test_1week.scenario.yaml
```
**Erwartete Laufzeit:** 2-5 Minuten

### Schritt 2: Falls OK, erhöhe auf 1 Monat
Passe `test_1week.scenario.yaml` an:
```yaml
horizon:
  start: "2023-01-01 00:00"
  end: "2023-02-01 00:00"  # 1 Monat
```
**Erwartete Laufzeit:** 10-20 Minuten

### Schritt 3: Falls OK, versuche ganzes Jahr
Mit den optimierten Parametern:
```bash
python -m energis.run.orchestrator \
  configs/base.yaml \
  configs/systems/baseline.system.yaml \
  configs/scenarios/perfect_forecast_full_year.scenario.yaml
```
**Erwartete Laufzeit:** 30-90 Minuten (mit MIPGap 0.02)

### Schritt 4: Falls immer noch zu langsam
- Erhöhe MIPGap auf 0.05 (5%)
- Reduziere Zeitauflösung auf 1 Stunde (dt_h: 1.0)
- Verwende Rolling Horizon statt Full Year

## Monitoring während der Optimierung

Gurobi zeigt während des Laufs:
```
Nodes    Current Node    Objective Bounds      Work
 Expl   Unexpl |  Obj  Depth IntInf | Incumbent    BestBd   Gap | It/Node Time

     0     0 1.2345e+06    0  123 1.2500e+06 1.2345e+06  1.24%     -    5s
   100    50 1.2360e+06   12   45 1.2450e+06 1.2360e+06  0.72%   12.3   10s
```

**Wichtige Metriken:**
- **Gap:** Sollte unter MIPGap (2%) fallen
- **Time:** Überwache Fortschritt
- **Incumbent:** Beste gefundene Lösung

## Support

Bei weiteren Performance-Problemen:
1. Prüfe Gurobi-Lizenz (ist sie gültig?)
2. Erhöhe MIPGap weiter (0.05 = 5%, 0.10 = 10%)
3. Reduziere Zeitauflösung oder Zeitraum
4. Kontaktiere Gurobi Support für spezifische Parameter-Tuning

## Changelog

- **2025-01-XX:** Initiale Performance-Optimierungen
  - Big-M von 10000 → 200 MW
  - Gurobi Solver-Parameter hinzugefügt
  - Test-Konfiguration für 1 Woche erstellt
