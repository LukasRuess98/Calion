# Framework Qualitätssicherungs-Checkliste
**Für: Stadtbach Fernwärmesystem Optimierung**  
**Version: 1.0 (2026-03-27)**

---

## Phase 1: Vor der Optimierung

### Daten-Vorbereitungen
- [ ] CSV Input-Datei vorhanden: `data/Import_Data_*.csv`
- [ ] 8760 oder 8736 Zeilen (ganz Jahr)
- [ ] Keine leeren Zellen (NaN)
- [ ] Spalten korrekt: `timestep`, `heat_demand_MW`, `gas_price`, `electricity_price`, `co2_intensity`
- [ ] Werte in realistischen Bereichen:
  - [ ] Wärmenachfrage: 40-80 MW
  - [ ] Gaspreis: €3-10 per MWh
  - [ ] Strompreis: €20-100 per MWh
  - [ ] CO₂: 50-150 g/kWh

**Command zum Prüfen:**
```bash
python -c "
import pandas as pd
df = pd.read_csv('data/Import_Data_yearly.csv')
print(f'Shape: {df.shape}')
print(f'Nulls: {df.isnull().sum().sum()}')
print(df.describe())
"
```

### Config YAML Validierung
- [ ] `config.yaml` existiert und ist valid YAML
- [ ] Network-Struktur definiert (1 oder mehrere Knoten)
- [ ] Assets definiert (min. Boiler + HP + Storage)
- [ ] Kapazitäten realistisch:
  - [ ] Boiler: 100-200 MW
  - [ ] HP: 50-150 MW
  - [ ] Storage: 200-1000 MWh
- [ ] Input-Datei referenziert (richtige Pfad)
- [ ] Solver konfiguriert: `appsi_highs` (HiGHS)

**Command zum Prüfen:**
```bash
python -c "
import yaml
with open('configs/scenarios/stadtbach_baseline_2023.yaml') as f:
    cfg = yaml.safe_load(f)
print('Network nodes:', len(cfg.get('network', {}).get('nodes', [])))
print('Assets:', list(cfg.get('assets', {}).keys()))
print('Input file:', cfg.get('settings', {}).get('input_data', 'NOT SET'))
"
```

### Umgebung vorbereitet
- [ ] Python Environment aktiviert (`HeatGrid/Scripts/Activate.ps1` auf Windows)
- [ ] Alle Dependencies installiert:
  ```bash
  pip install -r requirements.txt
  python -m pip list | grep -E "pyomo|energis|highs"
  ```
- [ ] HiGHS Solver funktioniert:
  ```bash
  python -c "from pyomo.environ import *; print('✅ Pyomo OK')"
  python -m energis.run --version 2>&1 | head -1
  ```
- [ ] Output-Verzeichnis leer/ready:
  ```bash
  rm -rf outputs/runs/thermal_network_results/*
  mkdir -p outputs/runs/thermal_network_results
  ```

**Checkpoint:** Wenn alle Häkchen, bereit für Optimierung → **Phase 2**

---

## Phase 2: Während die Optimierung läuft

### Solver überwachen
- [ ] Prozess startet ohne Fehler
- [ ] Solver-Output sichtbar (Iterationen werden gezählt)
- [ ] Keine Warnung "infeasible" oder "unbounded"
- [ ] Speicher-Nutzung OK (<4 GB)

**Command zur Überwachung:**
```bash
# Terminal 1:
python -m energis.run configs/scenarios/stadtbach_baseline_2023.yaml

# Terminal 2 (in parallel):
while true; do
  sleep 5
  ls -lh outputs/runs/thermal_network_results/* 2>/dev/null | tail -3
done
```

### Typical Timeline (für 8760 Stunden):
| Phase | Zeit | Status |
|-------|------|--------|
| Modell-Bau | 5-10s | "Building model..." |
| Solver Start | 10-30s | "Solving..." |
| Iterationen | 1-10min | "Iteration X..." |
| Lösung gefunden | 1sec | "**OPTIMAL FOUND**" |
| Export | 5-20s | Dateien werden geschrieben |
| **Total** | **~2min** | ✅ Fertig |

- [ ] Nach ~2 Minuten sollte Lösung gefunden sein
- [ ] Wenn >10 Min: Solver-Parameter überprüfen (Checklist im Debugging)

**Checkpoint:** Solver beendet sich ohne Fehler → **Phase 3**

---

## Phase 3: Nach der Optimierung (Sofort-Checks)

### Export-Dateien vorhanden?
```bash
ls -lh outputs/runs/thermal_network_results/
```

**Required Dateien:**
- [ ] `*.lp` (Pyomo LP format) - sollte >100 MB sein
- [ ] `*.mps` (MPS standard format) - sollte >100 MB sein
- [ ] `*.sol` (Solver solution) - sollte >1 MB sein
- [ ] `unified_timeseries.csv` - sollte >100 KB sein
- [ ] `export_manifest.json` - sollte <10 KB sein

### Solver-Status prüfen
```bash
grep -i "optimal\|infeasible\|unbounded" mpc_log.txt
```

- [ ] Zeile mit "**optimal solution**" vorhanden
- [ ] **Gap %**: sollte 0.0% sein (oder <0.5% akzeptabel)
- [ ] **Time**: sollte <2 Minuten sein

### Schnelle Daten-Checks
```bash
python validate_framework.py
```

Sollte zeigen:
```
✅ ALLE CHECKS BESTANDEN - Framework ist valid!
```

Wenn nicht, dann:
- [ ] Time Coverage: Sollte 8736-8760 Stunden sein
- [ ] No Null Values: 0 nulls (0.00%)
- [ ] Demand Plausible: Min 40-80 MW Range CHECK!

**Checkpoint:** Alle Dateien vorhanden + grüne Checks → **Phase 4**

---

## Phase 4: Detaillierte Ergebnis-Validierung

### Wärmebilanz prüfen
```python
import pandas as pd
df = pd.read_csv('outputs/runs/thermal_network_results/unified_timeseries.csv', sep=';')
demand = df['heat_demand_MW'].sum()
print(f"Annual heat demand: {demand/1000:.1f} GWh")
print(f"Expected: 500-550 GWh für Stadtbach")
```

- [ ] Nachfrage-Summe: **516.6 GWh** ± 2% (realistisch)
- [ ] Damit konsistent: Jährliche Kosten sollten ~€15-16M sein

### Kostenanalyse
```python
import json
manifest = json.load(open('outputs/runs/thermal_network_results/export_manifest.json'))
# Suche objective_value in sol file
import re
sol = open('outputs/runs/thermal_network_results/*.sol').read()
cost = float(re.search(r'Objective Value:\s*([\d.e+-]+)', sol).group(1))
print(f"Total annual cost: €{cost:,.0f}")
print(f"Cost per MWh: €{cost / (demand) * 1000:.2f}")
```

- [ ] Kosten €15-16M (±10%)
- [ ] Cost/MWh: €30-40 (realistisch für CH)
- [ ] Wenn zu niedrig (<€20/MWh): Brennstoff-Preise überprüfen!
- [ ] Wenn zu hoch (>€100/MWh): Kapazitäten überprüfen!

### Komponenten-Mix prüfen
```python
# (Wenn Spalten im CSV verfügbar)
boiler_fraction = df['Q_boiler'].sum() / df['heat_demand_MW'].sum()
hp_fraction = df['Q_hp'].sum() / df['heat_demand_MW'].sum()

print(f"Boiler: {boiler_fraction:.1%}")
print(f"Heat pump: {hp_fraction:.1%}")
```

- [ ] Boiler: ~50-70% (realistisch)
- [ ] HP: ~30-50% (realistisch)
- [ ] Wenn HP >100%: Speicher oder andere Quelle
- [ ] Wenn HP ~0%: Wahrscheinlich zu teuer, Preise überprüfen

### Speicher-Nutzung prüfen
```python
# Falls Speicher im Model:
storage_cycles = len(df[df['storage_charge_MW'] > 0])
storage_utilization = df['storage_SOC_MWh'].mean() / max(df['storage_SOC_MWh'])

print(f"Storage charge cycles: {storage_cycles}")
print(f"Storage utilization: {storage_utilization:.1%}")
```

- [ ] Lade-Zyklen: >50 pro Jahr (nutzt Speicher!)
- [ ] Auslastung: >30% (nicht leer)

**Checkpoint:** Alle Werte plausibel → **Phase 5**

---

## Phase 5: Final Validation Suite

Vollständig automatisierte Prüfung:

```bash
python -m pytest tests/test_exporter.py -v
```

Muss zeigen: **8/8 tests PASSED**

```bash
python validate_framework.py
```

Sollte zeigen: **✅ ALLE CHECKS BESTANDEN**

**Falls Test fehlschlägt:**
→ Siehe [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) für Lösungsschritte

---

## Phase 6: Dokumentation & Reporting

### Ergebnis-Report erstellen
```bash
cat > OPTIMIZATION_REPORT_$(date +%Y%m%d).md << 'EOF'
# Optimization Results: Stadtbach 2023
**Date:** $(date)
**Config:** configs/scenarios/stadtbach_baseline_2023.yaml

## Key Metrics
- **Annual Cost:** €15.93M
- **Heat Output:** 516.6 GWh
- **Solver Status:** Optimal
- **Solver Time:** ~100s
- **Gap:** 0.0%

## Export Files
✅ LP (13.7 MB)
✅ MPS (14.7 MB)
✅ SOL (1.4 MB)
✅ CSV (200 KB)
✅ Manifest (1.2 KB)

## Validation
✓ All checks passed
✓ No null values
✓ Energy balance OK
✓ Costs plausible
EOF
```

### Ergebnisse archivieren
```bash
# Timestamped backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p archives/$TIMESTAMP
cp -r outputs/runs/thermal_network_results/* archives/$TIMESTAMP/
cp OPTIMIZATION_REPORT_*.md archives/$TIMESTAMP/
```

- [ ] Report geschrieben
- [ ] Dateien gebackupt
- [ ] Metadata (Config, Data-Version) dokumentiert

---

## Phase 7: Übergabe an Stakeholder

### Deliverables Checkliste
- [ ] **CSV Timeseries** - für Weitere Analysen
  - Format: `timestep;heat_demand_MW;...`
  - 8760 Zeilen mit vollständiger Jahresreihe
  
- [ ] **LP File** - für Solver-Vergleiche
  - Kann mit Gurobi, CPLEX, CBC gelöst werden
  - Ermöglicht externe Validierung
  
- [ ] **SOL File** - für Detailanalysen
  - 43,683 Variablen mit Optimalwerten
  - Objektives: €15,925,510 für 2023
  
- [ ] **Report** - Executive Summary
  - Kostenanalyse
  - Tech-Mix
  - Recommendations

### Qualitätssignoff
- [ ] Technische Lead: "Validator.py grün?"
- [ ] Business Owner: "Kosten realistisch?"
- [ ] Umwelt-Koordinator: "CO₂-Ziele erreicht?"

---

## Phase 8: Laufende Überwachung

### Monatliche Rekalibrierung (wenn neue Daten)
```bash
# Template für regelmäßige Läufe
MONTH=$(date +%Y%m)
echo "=== Optimization für $MONTH ==="

# 1. Update input data
cp data/Import_Data_$MONTH.csv data/Import_Data_current.csv

# 2. Run optimization
python -m energis.run configs/scenarios/stadtbach_$MONTH.yaml

# 3. Validate
python validate_framework.py

# 4. Report
python generate_report.py > reports/report_$MONTH.md

# 5. Diff gegen Vormonat
python compare_results.py reports/report_$(date +%Y%m -d "last month").md \
                          reports/report_$MONTH.md
```

### Jährliche Deep-Dive
- [ ] Unit-Tests updaten if Config geändert
- [ ] Solver-Parameter re-tunen
- [ ] Sensitivitätsanalyse durchführen
- [ ] Kapazitäts-Review (Unter-/Überkapazitäten?)

---

## Troubleshooting Quick Lookup

| Problem | Symptom | Solution |
|---------|---------|----------|
| **Solver zu langsam** | >10 min | Siehe DEBUGGING_GUIDE Abschnitt 5 |
| **Hohe Kosten** | >€50/MWh | Check Gaspreis, HP-Kapazität |
| **Niedrige Kosten** | <€20/MWh | Check ob alle Brennstoffe billig sind |
| **Export leer** | 0 byte CSV | Solver gefunden? Siehe DEBUGGING_GUIDE Abschnitt 3 |
| **Regression** | 1% Kostenunterschied | Vergleiche Config mit backup |
| **Infeasible** | "No solution" | Check Kapazitäten vs Demand, DEBUGGING_GUIDE 1 |

---

## Kontakt & Support

**Interne Fragen:**
→ See: [VALIDATION_STRATEGIES.md](VALIDATION_STRATEGIES.md) & [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md)

**Solver Probleme:**
→ HiGHS Docs: https://github.com/ERGO-Code/HiGHS

**Energy Model Fragen:**
→ EnerGIS Docs: docs/API_REFERENCE.rst

**Data Issues:**
→ Check: data/DATA_FORMAT.md

---

## Sign-Off

| Role | Name | Date | Sign |
|------|------|------|------|
| Optimization Lead | _____ | _____ | ___ |
| Data Engineer | _____ | _____ | ___ |
| Tech Lead | _____ | _____ | ___ |
| Project Manager | _____ | _____ | ___ |

**Approved for Production:** ☐ Yes / ☐ No

---

**Last Updated:** 2026-03-27  
**Version:** 1.0  
**Status:** ✅ Ready for Use
