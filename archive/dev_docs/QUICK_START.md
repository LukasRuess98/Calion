# 🚀 Quick Start - Framework Validierung

**Erstellt:** 2026-03-27  
**Für Verwendung:** Unmittelbar nach Installation

---

## Die 4 wichtigsten Dateien

| Datei | Größe | Zweck | Öffnen mit |
|-------|-------|-------|-----------|
| [VALIDATION_README.md](VALIDATION_README.md) | 9 KB | **START HIER** - Dokumentations-Index | VS Code |
| [QA_CHECKLIST.md](QA_CHECKLIST.md) | 11 KB | 8-Phasen Checkliste (vor → nach) | Drucken & abhaken |
| [VALIDATION_STRATEGIES.md](VALIDATION_STRATEGIES.md) | 9 KB | 10 Strategien zum Verstehen | Entwickler |
| [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) | 13 KB | 7 Probleme + Lösungen | Wenn Error auftritt |
| [validate_framework.py](validate_framework.py) | 11 KB | Automatische Validierung (10s) | Terminal |

---

## THE FÜR VERSCHIEDENE ROLLEN

### 👔 Projekt-Manager / Team-Lead

```bash
# VOR Optimierung starten
→ Öffne: QA_CHECKLIST.md Phase 1
→ Häkchen abhaken (5 min)

# NACH Optimierung
→ Terminal: python validate_framework.py
→ Sollte grün sein ✅
→ Öffne: QA_CHECKLIST.md Phase 3-5 (prüfe Details)

# Mit Stakeholdern
→ Lese: QA_CHECKLIST.md Phase 6 (Report)
→ Zeige VALIDATION_README.md (zeigt Rigor)
```

---

### 💻 Entwickler / Data Engineer

```bash
# Framework verstehen
→ Lese: VALIDATION_README.md (Überblick - 10 min)
→ Lese: VALIDATION_STRATEGIES.md (Details - 30 min)

# Vor jedem Code-Commit
python -m pytest tests/ -v
python validate_framework.py

# Bei neuer Komponente
→ Öffne: VALIDATION_STRATEGIES.md
→ Wähle passende Strategie
→ Implementiere zusätzliche Tests

# Wenn Bug-Report kommt
→ Öffne: DEBUGGING_GUIDE.md
→ Suche nach Symptom
→ Folge Debug-Schritte
```

---

### 🔧 Betreiber / Operations

```bash
# Nach automatischer Optimierung
python validate_framework.py
# → Wenn ✅: Ready to publish
# → Wenn ❌: Review QA_CHECKLIST.md Phase 3

# Monatliche Überwachung
→ Öffne: QA_CHECKLIST.md Phase 8

# Problem?
→ Öffne: DEBUGGING_GUIDE.md
→ Suche Fehlermeldung
→ Folge Schritte
```

---

### 👨‍🎓 Neu im Team

**Onboarding in 1 Stunde:**

```bash
# 1. Überblick (10 min)
Lese: VALIDATION_README.md

# 2. Prozess verstehen (20 min)
Öffne: QA_CHECKLIST.md
Lese alle 8 Phasen als Übersicht

# 3. Konzepte (20 min)
Lese: VALIDATION_STRATEGIES.md "Strategie 1-3"

# 4. Pratisch ausprobieren (10 min)
Terminal: python validate_framework.py
```

---

## One-Liners für häufige Tasks

### ✅ "Sind die Ergebnisse OK?"
```bash
python validate_framework.py
```
→ Grün = OK, Rot = Problem

---

### 📋 "Ich muss eine Optimierung durchführen"
```bash
# Öffne und folge Phase 1 + 2
code QA_CHECKLIST.md

# Nach ~2 Min:
python validate_framework.py
```

---

### 🔍 "Warum sind die Kosten so hoch?"
```bash
# Öffne Debug-Guide Section 4
code DEBUGGING_GUIDE.md +200  # Line 200 = Cost section

# Dann Terminal:
python -c "
import pandas as pd
df = pd.read_csv('outputs/runs/thermal_network_results/unified_timeseries.csv', sep=';')
demand_gwh = df['heat_demand_MW'].sum() / 1000
print(f'Demand: {demand_gwh:.1f} GWh')
# → Vergleich mit expected für Stadtbach
"
```

---

### 🐛 "Solver gibt Error - was tun?"
```bash
# 1. Error kopieren
python -m energis.run config.yaml 2>&1 | tail -10

# 2. Guide öffnen
code DEBUGGING_GUIDE.md

# 3. Nach des Fehlermeldung suchen
# z.B. "infeasible" → Problem 1
# z.B. "export empty" → Problem 3

# 4. Folge Debug-Schritte
```

---

### ⌚ "Tests durchlaufen?"
```bash
# Alle Tests
python -m pytest tests/ -v

# Export-Tests nur
python -m pytest tests/test_exporter.py -v

# Mit Coverage
python -m pytest tests/ --cov=energis --cov-report=html
```

---

### 📈 "Sensitvitätsanalyse: Was wenn Strompreis 2x höher?"
```bash
# Siehe VALIDATION_STRATEGIES.md Strategie 4

# Template:
for price in 30 60 90 120; do
    echo "=== Testing electricity price $price EUR/MWh ==="
    python -m energis.run config.yaml --override electricity_price=$price
    python validate_framework.py
done
```

---

### 🔄 "Unterschied zu Vormonat?"
```bash
# Siehe DEBUGGING_GUIDE.md Problem 6

# Speichere Baseline
python -m energis.run config.yaml > baseline_result.json

# Nach Code-Änderung
python -m energis.run config.yaml > current_result.json

# Vergleiche
python -c "
import json
b = json.load(open('baseline_result.json'))
c = json.load(open('current_result.json'))
diff = abs(c['cost'] - b['cost']) / b['cost'] * 100
print(f'Cost change: {diff:+.2f}%')
print('OK' if diff < 1 else 'REGRESSION!')
"
```

---

## Befehle für CI/CD Integration

### GitHub Actions
```yaml
name: Framework Validation
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v
      - run: python validate_framework.py
```

### Cron-Job (tägliche Validierung)
```bash
# Crontab: Täglich um 23:55 Uhr
55 23 * * * cd /path/to/project && python validate_framework.py && mail -s "Daily Validation" admin@company.ch < report.txt
```

---

## Dateistruktur für euer Team

```
📂 Verzeichnis-Layout
├─ VALIDATION_README.md        ← START HIER (Überblick)
├─ QA_CHECKLIST.md             ← Projekt-Manager nutzen
├─ VALIDATION_STRATEGIES.md    ← Entwickler nutzen
├─ DEBUGGING_GUIDE.md          ← Wenn was schiefgeht
├─ validate_framework.py       ← Terminal tool
│
├─ configs/scenarios/
│  └─ stadtbach_baseline_2023.yaml
│
├─ data/
│  └─ Import_Data_yearly.csv
│
├─ outputs/runs/thermal_network_results/
│  ├─ *.lp (Pyomo LP format)
│  ├─ *.mps (Standard MPS)
│  ├─ *.sol (Solution detail)
│  ├─ unified_timeseries.csv
│  └─ export_manifest.json
│
└─ tests/
   ├─ test_exporter.py         (8 tests ✅)
   ├─ test_system_builder.py
   └─ test_full_system.py
```

---

## Fehlerbehebungs-Flussdiagramm

```
┌──── Fehler tritt auf
│
├─→ "Solver gibt error" → DEBUGGING_GUIDE Problem 1
│
├─→ "Ergebnisse unrealistisch" → DEBUGGING_GUIDE Problem 2
│
├─→ "CSV ist leer" → DEBUGGING_GUIDE Problem 3
│
├─→ "Kosten merkwürdig" → DEBUGGING_GUIDE Problem 4
│
├─→ "Zu langsam" → DEBUGGING_GUIDE Problem 5
│
├─→ "Unterschied zu früher" → DEBUGGING_GUIDE Problem 6
│
└─→ "Exports beschädigt" → DEBUGGING_GUIDE Problem 7
```

---

## Checkliste für erste Woche

- [ ] VALIDATION_README.md gelesen (10 min)
- [ ] QA_CHECKLIST.md Phase 1 durchlaufen (5 min)
- [ ] Erste Optimierung erfolgreich (python -m energis.run)
- [ ] validate_framework.py ausgeführt (1 min)
- [ ] VALIDATION_STRATEGIES.md Überblick gelesen (10 min)
- [ ] DEBUGGING_GUIDE.md durchgeblättert (5 min)
- [ ] Alle Unit Tests grün (pytest tests/ -v)
- [ ] Ergebnisse mit Team besprochen

**→ Team ist dann ready für Produkteinsatz! ✅**

---

## Support-Matrix

| Frage | Datei | Zeile | Befehl |
|-------|-------|-------|--------|
| "Was validieren wir?" | VALIDATION_README.md | Top | - |
| "Wie mache ich das?" | QA_CHECKLIST.md | Phase X | - |
| "Warum tun wir das?" | VALIDATION_STRATEGIES.md | Strategie X | - |
| "Was ist schief?" | DEBUGGING_GUIDE.md | Problem X | - |
| "Schnell prüfen!" | - | - | `python validate_framework.py` |

---

## Was als nächstes?

### Option A: Erste Optimierung  
→ Öffne: **QA_CHECKLIST.md Phase 1** und folge den Schritten

### Option B: Framework verstehen  
→ Lese: **VALIDATION_STRATEGIES.md** (20 min)

### Option C: Team onboarden  
→ Teile: **VALIDATION_README.md** mit dem Team

### Option D: Problem debuggen  
→ Öffne: **DEBUGGING_GUIDE.md** und suche nach Fehlermeldung

---

**Version:** 1.0  
**Status:** ✅ Ready  
**Questions?** → Konsultiere die entsprechende Datei oben  

🚀 Viel Erfolg beim Optimieren!
