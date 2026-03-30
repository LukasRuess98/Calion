# Framework Debugging & Problem-Lösungs-Guide

## Quick Reference: Häufige Probleme & Lösungen

### Problem 1: "Solver meldet keine optimale Lösung"

```
Status: infeasible / unbounded / error
```

**Debugging-Schritte:**

```python
# Schritt 1: Prüfe ob Model gebaut wurde
python -c "
from calion.run import build_from_config
config = build_from_config('config.yaml')
print(f'Variables: {len(config.model.component_data_objects(ctype=pyo.Var))}')
print(f'Constraints: {len(config.model.component_data_objects(ctype=pyo.Constraint))}')
"

# Schritt 2: Exportiere LP für Analyse
python -m calion.run config.yaml --export-lp-only
# → star_debug.lp (prüfe constraints auf logische Fehler)

# Schritt 3: Versuche relaxierte Version (alle 0-1 zu 0-1 real)
# Im Config: solver_options: { relax_integrality: true }
```

**Häufige Ursachen:**
- ❌ Unrealistische Kapazitäten (zu klein für Demand)
- ❌ Widersprüchliche Constraints (z.B. min > max)
- ❌ Fehlende Input-Daten (NaN in CSV)

---

### Problem 2: "Ergebnisse machen physikalisch keinen Sinn"

**Beispiel:** HP läuft mit CoP = 0.5 (unmöglich!)

```python
# Debugging-Script
import pandas as pd

df = pd.read_csv('outputs/runs/thermal_network_results/unified_timeseries.csv', sep=';')

# Prüfe HP-CoP
for t in df.itertuples():
    if hasattr(t, 'P_hp') and t.P_hp > 0.1:
        cop = t.Q_hp / t.P_hp
        if cop < 2.0 or cop > 5.0:
            print(f"⚠️  Hour {t.Index}: CoP={cop:.2f} - unrealistic!")
            print(f"    Q_hp={t.Q_hp:.1f} MW, P_hp={t.P_hp:.1f} MW")
```

**Häufige Ursachen:**
- ❌ CoP wird nicht als Constraint erzwungen (zu optimistisch)
- ❌ COP-Curve nicht temperaturabhängig (sollte aber sein)
- ❌ Fehlende Grenzen auf Eingangsstrom

**Lösung:**
```yaml
# In config.yaml
assets:
  hp_name:
    cop_min: 2.5               # Add lower bound
    cop_max: 4.5               # Add upper bound
    # oder
    cop_curve: "poly"          # Temperature-dependent
```

---

### Problem 3: "CSV ist leer oder unvollständig"

```
$ ls -lh outputs/runs/thermal_network_results/
-rw-r--r-- 1 user  0 MB unified_timeseries.csv  ❌ Empty!
```

**Debug-Checklist:**

```bash
# 1. Check ob Solver überhaupt lief
grep -i "optimal\|infeasible" mpc_log.txt

# 2. Check ob Export-Code errors hat
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from calion.run import main
main(['config.yaml'])
" 2>&1 | grep -i "export\|error\|warning"

# 3. Check ob Spalteninformationen im Code richtig sind
grep -n "_export_unified_timeseries" calion/io/thermal_network_exporter.py | head -3

# 4. Manueller Test: Kann die Spalte extrahiert werden?
python -c "
from calion.run import build_from_config, solve
config = build_from_config('config.yaml')
model, results = solve(config)
print('Available variables:')
for var in model.component_data_objects(ctype=pyo.Var):
    print(f'  {var.name}')
" 2>&1 | head -20
```

**Häufige Ursachen:**
- ❌ Solver hat nicht gefunden
- ❌ Spalte existiert nicht im Model (z.B. Q_boiler in Copperplate-Model)
- ❌ Export-Funktion hat Exception geschluckt (silent failure)

---

### Problem 4: "Kosten sind unrealistisch (viel zu hoch/niedrig)"

```python
# Kosten-Validator
def check_cost_plausibility(result_json):
    annual_cost = result_json['metadata']['objective_value']
    heat_gwh = df['heat_demand_MW'].sum() / 1000
    
    cost_per_mwh = annual_cost / (heat_gwh * 1000)
    
    # Typisch für Fernwärme: 30-80 EUR/MWh
    if cost_per_mwh < 20:
        print(f"⚠️  Zu niedrig: {cost_per_mwh:.1f} EUR/MWh")
        print("   → Prüfe ob Brennstoff-Preise zu niedrig sind")
    elif cost_per_mwh > 150:
        print(f"⚠️  Zu hoch: {cost_per_mwh:.1f} EUR/MWh")
        print("   → Prüfe ob Kapazitäten zu klein sind")
    else:
        print(f"✅ Plausibel: {cost_per_mwh:.1f} EUR/MWh")
    
    return cost_per_mwh

# Referenzwerte
```

**Benchmark (Stadtbach):**
| Parameter | Min | Expected | Max |
|-----------|-----|----------|-----|
| Cost/MWh | €25 | €35-45 | €100 |
| HP Share | 0% | 40-50% | 100% |
| Boiler Share | 0% | 50-60% | 100% |
| Storage Cycles | 0 | 50-100 | 365 |

**Debugging:**
```python
# Welche Komponente kostet am meisten?
cost_breakdown = {
    'boiler_fuel': df['Q_boiler'].sum() * gas_price / 0.85,
    'hp_electricity': df['P_buy'].sum() * electricity_price,
    'emissions': df['co2_emitted'].sum() * co2_price,
}

for component, cost in sorted(cost_breakdown.items(), key=lambda x: -x[1]):
    pct = cost / annual_cost * 100
    print(f"{component:20} {cost:12,.0f} EUR = {pct:5.1f}%")
```

---

### Problem 5: "Solver ist sehr langsam (>1 Stunde)"

```bash
# Profile solver performance
time python -m calion.run config.yaml

# real: 0m58.234s → OK für yearly
# real: 5m12.123s → Zu langsam - optimierungsbedürftig
# real: >1h       → Problem!
```

**Lösungsstrategien (in dieser Priorität):**

1. **Solver-Optionen tunen** (schnellste Lösung)
```yaml
run:
  solver: appsi_highs
  solver_options:
    time_limit: 600              # Max 10 min
    presolve: true               # Aktivieren
    parallel: true               # Multithreading
    mip_gap: 0.05                # 5% acceptable
```

2. **Modell vereinfachen**
```yaml
# Reduziere Zeitschritte zum Testen
settings:
  time_subset: [0, 200]          # Nur erste 200h zum Debuggen
```

3. **Speicher/Netzwerk vereinfachen**
```yaml
network:
  nodes: 1                        # Copperplate statt 5node
  storage_enabled: false          # Deaktivieren zum Testen
```

4. **Presolve aktivieren** (entfernt redundante Constraints)
```python
# In config.yaml oder per CLI
python -m calion.run config.yaml --solver-presolve true
```

---

### Problem 6: "Unterschiede zwischen zwei Läufen (Regression)"

```bash
# Run 1: Baseline
python -m calion.run config.yaml > baseline.json

# Nach Code-Änderungen
python -m calion.run config.yaml > current.json

# Vergleich
python -c "
import json
baseline = json.load(open('baseline.json'))
current = json.load(open('current.json'))

diff = abs(current['cost'] - baseline['cost']) / baseline['cost'] * 100
print(f'Cost change: {diff:+.2f}%')

if diff > 1:
    print('❌ REGRESSION DETECTED!')
else:
    print('✅ No significant regression')
"
```

**Root Cause Analysis:**

```bash
# 1. Welche Zeilen wurden geändert?
git diff calion/ --stat

# 2. Unit-Tests für betroffene Module
python -m pytest tests/test_[affected_module].py -v

# 3. Config manuell validieren
python -c "
from calion.config import load_config
cfg = load_config('config.yaml')
# Prüfe auf Unterschiede in den Input-Parametern
print(cfg['costs'])
print(cfg['assets'])
"
```

---

### Problem 7: "Export-Dateien sind beschädigt"

```bash
# LP-Datei validieren
python -c "
from pyomo.environ import *
from pyomo.repn import generate_standard_form

model = AbstractModel()
# ... load from LP
print(f'✓ LP syntax OK')
"

# CSV validieren
python -c "
import pandas as pd
df = pd.read_csv('unified_timeseries.csv', sep=';')
print(f'Shape: {df.shape}')
print(f'Dtypes: {df.dtypes}')
print(f'Nulls: {df.isnull().sum().sum()}')
"

# MPS validieren (manuell prüfen)
head -50 solution.mps  # Sollte mit ROWS/COLS/RHS beginnen
tail -10 solution.mps  # Sollte mit ENDATA enden
```

---

## Systematisches Debug-Prozedere

**Wenn etwas nicht stimmt, in dieser Reihenfolge prüfen:**

```
1. INPUT VALIDIERUNG
   └─> CSV-Daten vollständig? (8760 rows, no NaN)
   └─> Config YAML valid? (no syntax errors)
   └─> Parameter in realistischem Bereich?

2. MODEL BUILDING
   └─> Variables erstellt? (count sollte >1000 sein)
   └─> Constraints hinzugefügt? (count sollte >>variables sein)
   └─> Objective definiert? (sollte minimize sein)

3. SOLVER EXECUTION
   └─> Solver läuft ohne Fehler?
   └─> Lösung gefunden (status = optimal)?
   └─> Gap minimal (<0.1%)?

4. EXPORT
   └─> Alle 5 Dateien vorhanden? (LP, MPS, SOL, CSV, JSON)
   └─> Dateien nicht leer?
   └─> Manifest valid JSON?

5. RESULTS VALIDATION
   └─> Wärmebilanz ausgeglichen? (±5%)
   └─> Kosten plausibel? (€30-80/MWh)
   └─> Physics korrekt? (CoP 2.5-4.5)
```

---

## Logging & Diagnostics aktivieren

```python
# Maximales Logging
python -c "
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

from calion.run import main
main(['config.yaml'])
" 2>&1 | tee full_debug.log
```

**Dann nach Problemen suchen:**
```bash
grep -i "error\|warning\|failed" debug.log
grep -i "export" debug.log              # Export-Probleme
grep -i "solver\|status" debug.log      # Solver-Status
grep -i "constraint\|variable" debug.log # Model issues
```

---

## Validation Checkliste

Vor jeder Produktion-Optimierung:

- [ ] **Input CSV**: 8760 rows, no NaN, realistic values
- [ ] **Config YAML**: Valid syntax, all required fields
- [ ] **Solver**: HiGHS installed (`python -m pip show pyomo-core`)
- [ ] **Previous run**: Latest is <1 week old (regression test)
- [ ] **Disk space**: >5 GB available (LP file can be large)

Nach der Optimierung:

- [ ] **Solver status**: `optimal` or `feasible` (not infeasible)
- [ ] **MIP gap**: <0.1% (or <0.5% for large problems)
- [ ] **Solver time**: <2 hours (else optimize parameters)
- [ ] **Export files**: All 5 files present, not empty
- [ ] **CSV data**: 8736+ rows, all numeric, no giant spikes
- [ ] **Cost check**: €15M ± 20% for Stadtbach yearly
- [ ] **Energy balance**: Supply within ±5% of demand
- [ ] **CoP check**: 2.5-4.5 for heat pump outputs

---

## Support-Kontakt Vorbereitung

Wenn Sie ein Entwickler fragen, bitte mitteilen:

1. **Fehlertext (vollständig):**
   ```bash
   python -m calion.run config.yaml 2>&1 | tail -30
   ```

2. **System-Info:**
   ```bash
   python --version
   python -m pip list | grep -E "pyomo|calion|highs"
   ```

3. **Config (wenn möglich):**
   ```bash
   cat config.yaml  # (ohne sensitive data)
   ```

4. **Solver-Log:**
   ```bash
   tail -100 mpc_log.txt
   ```

5. **Export-Status:**
   ```bash
   ls -lh outputs/runs/thermal_network_results/
   ```

---

## Unit-Test ausführen für Schnell-Debug

```bash
# Alle Tests (schnell - <1min)
python -m pytest tests/ -v

# Nur Export-Tests
python -m pytest tests/test_exporter.py -v

# Nur Config-Tests
python -m pytest tests/test_system_builder.py -v

# Mit Coverage-Report
python -m pytest tests/ --cov=calion --cov-report=html
```

Tests bestanden = Ihr Framework funktioniert! ✅
