# EnerGIS Notebooks - Welches soll ich nutzen?

## 🎯 Entscheidungsbaum

```
                    START HIER
                        │
                        ▼
              ┌─────────────────────┐
              │ Was möchtest du tun?│
              └─────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   Optimieren?     Validieren?     Lernen?
        │               │               │
        ▼               ▼               ▼
  ┌─────────┐    ┌──────────┐   ┌──────────┐
  │ Eigene  │    │ Stadtbach│   │Syntheti- │
  │ Daten?  │    │Reference │   │sche Demo │
  └─────────┘    └──────────┘   └──────────┘
   │      │            │              │
   Ja    Nein          │              │
   │      │            ▼              ▼
   ▼      ▼      validation.ipynb  synthetic_
runner  scenario_                  example.ipynb
.ipynb  studio.ipynb
```

**Schnellwahl:**
- ✅ **Echte Daten optimieren** → `runner.ipynb`
- 📊 **Szenarien analysieren** → `scenario_studio.ipynb`
- 🎓 **Framework lernen** → `synthetic_example.ipynb`
- 🔬 **Legacy validieren** → `validation.ipynb`

---

## 📚 Notebook-Details

### 1️⃣ **runner.ipynb** - Production Workflow
**Wann:** Du hast echte Daten (Import_Data.xlsx) und willst Optimierung durchführen

**Features:**
- ✅ Vollständiger PF→RH Workflow
- ✅ Export nach Excel/CSV/JSON
- ✅ Flexibler Config-Override
- ✅ Detaillierte Ergebnis-Zusammenfassung
- ⏱️ **Laufzeit:** 5-60 Min (je nach Datenmenge)

**Schnellstart:**
```python
# Alle Zellen nacheinander ausführen
# Config-Pfade in Zelle 2 anpassen falls nötig
```

**Voraussetzungen:**
- Import_Data.xlsx im Projekt-Root
- Solver installiert (gurobi/glpk/highs)

---

### 2️⃣ **scenario_studio.ipynb** - Interactive Analysis
**Wann:** Du willst verschiedene Szenarien interaktiv analysieren und visualisieren

**Features:**
- ✅ Detaillierte Visualisierungen (Matplotlib)
- ✅ KPI-Dashboard
- ✅ Korrelationsanalysen
- ✅ Komponenten-Auslastung
- ✅ Sensitivitätsanalysen
- ⏱️ **Laufzeit:** 2-30 Min

**Schnellstart:**
```python
# Für schnelle Tests: Solver auf 'glpk' setzen
overrides = {"run": {"solver": "glpk"}}
```

**Ideal für:**
- 📊 Detaillierte Ergebnis-Exploration
- 🔍 "Was-wäre-wenn" Analysen
- 📈 Visualisierungen für Präsentationen

---

### 3️⃣ **synthetic_example.ipynb** - Tutorial
**Wann:** Du lernst das Framework kennen ODER hast keine echten Daten

**Features:**
- ✅ Funktioniert out-of-the-box (keine Import_Data.xlsx nötig)
- ✅ Synthetische 24h-Daten
- ✅ Kompaktes Beispiel
- ✅ Energie- und Kostenbilanzen
- ✅ Plot-Export
- ⏱️ **Laufzeit:** < 2 Min

**Ideal für:**
- 🎓 Neue Nutzer / Onboarding
- 🧪 Framework-Tests
- 📦 CI/CD Smoke Tests
- 📚 Dokumentations-Beispiele

**Datenquelle:**
```
data/synthetic_site/synthetic_load_profile.csv
```

---

### 4️⃣ **validation.ipynb** - Research/Quality Assurance
**Wann:** Du validierst gegen Legacy Stadtbach-Referenz

**Features:**
- ✅ Automatischer Vergleich EnerGIS ↔ Legacy
- ✅ CSV-Export für CI-Artefakte
- ✅ Parity-Check
- ✅ Kennzahlen-Tabelle
- ⏱️ **Laufzeit:** 2-5 Min

**Nutzung:**
- 🔬 Für Entwickler bei Code-Änderungen
- 📊 Für Publikationen (Paper-Validierung)
- ✅ Regression Testing

**Referenz-Daten:**
```
tests/data/stadtbach_legacy_reference.json
```

---

## ⚡ Quick Commands

```bash
# Alle Notebooks clearen (vor Git-Commit)
jupyter nbconvert --clear-output --inplace notebooks/*.ipynb

# Einzelnes Notebook als Python-Skript exportieren
jupyter nbconvert --to script runner.ipynb

# Notebook im Browser öffnen
jupyter notebook runner.ipynb

# Alle Notebooks ausführen (Smoke Test)
jupyter nbconvert --execute --to notebook --inplace notebooks/*.ipynb
```

---

## 🔧 Troubleshooting

### "Import_Data.xlsx not found"
**Lösung:**
1. Nutze `synthetic_example.ipynb` stattdessen
2. Oder passe `configs/sites/default.site.yaml` an

### "Solver not available"
**Lösung:**
```bash
# GLPK installieren (Open-Source)
conda install -c conda-forge glpk

# Oder in Config explizit setzen:
overrides = {"run": {"solver": "glpk"}}
```

### "Module 'energis' not found"
**Lösung:**
Stelle sicher, dass du im Projekt-Root bist:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
```

---

## 📖 Weitere Ressourcen

- [README.md](../README.md) - Hauptdokumentation & CLI-Nutzung
- [ARCHITECTURE_V2.md](../ARCHITECTURE_V2.md) - Technische Architektur & Plugin-System
- [docs/methodology.md](../docs/methodology.md) - MILP-Modellbeschreibung
- [examples/custom_component_example.py](../examples/custom_component_example.py) - Eigene Komponenten entwickeln

---

## 💡 Best Practices

1. **Vor Git-Commit:** Immer Outputs clearen
   ```bash
   jupyter nbconvert --clear-output --inplace notebooks/*.ipynb
   ```

2. **Für Reproduzierbarkeit:** Config-Overrides dokumentieren
   ```python
   # Am Anfang des Notebooks:
   # Config-Override für diesen Run:
   overrides = {
       "run": {"solver": "glpk"},
       "costs": {"co2_price_eur_per_t": 150.0}
   }
   ```

3. **Für lange Läufe:** Zwischenstände exportieren
   ```python
   # Nach PF-Schritt:
   workflow.pf_result.to_json("pf_checkpoint.json")
   ```

4. **Für Debugging:** Verbose Logging aktivieren
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

---

**Viel Erfolg mit EnerGIS! 🚀**
