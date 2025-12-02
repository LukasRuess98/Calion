# Fehleranalyse und Stolpersteine - Vollständiger Report

**Datum:** 2025-11-19
**Status:** 🔴 **KRITISCHE FEHLER GEFUNDEN**

---

## 🔴 KRITISCHE FEHLER (Müssen behoben werden!)

### **Fehler 1: Falsche Cost-Keys in BenchmarkSuite** ❌ KRITISCH

**Datei:** `energis/comparison/benchmark.py`
**Zeilen:** 209, 261-263

**Problem:**
```python
# FALSCH (Zeile 209):
capex = costs.get('cost_capex', 0) + costs.get('cost_capex_annualized', 0)

# FALSCH (Zeile 261-263):
cost_energy=costs.get('cost_energy', 0),
cost_demand_charge=costs.get('cost_demand_charge', 0),
cost_co2=costs.get('cost_co2', 0),
```

**Tatsächliche Keys (aus rolling_horizon.py):**
```python
_INVESTMENT_KEYS = {
    "objective.Capex_cost_EUR",                  # ← RICHTIG
    "objective.Activation_cost_EUR",
    "objective.Tie_breaker_cost_EUR",
    "objective.Storage_installation_cost_EUR",
}

# Operational Costs:
"objective.Grid_energy_cost_EUR"                 # ← RICHTIG
"objective.Demand_charge_cost_EUR"               # ← RICHTIG
"objective.CO2_cost_EUR"                         # ← RICHTIG
```

**Impact:**
- ❌ CAPEX wird als 0 zurückgegeben (falsch!)
- ❌ OPEX wird als total_cost zurückgegeben (falsch!)
- ❌ cost_energy, cost_demand_charge, cost_co2 alle 0 (falsch!)
- ❌ **Alle Benchmark-Ergebnisse sind falsch!**

**Fix:**
```python
# Zeile 209 ERSETZEN durch:
capex = sum(costs.get(k, 0) for k in [
    "objective.Capex_cost_EUR",
    "objective.Activation_cost_EUR",
    "objective.Tie_breaker_cost_EUR",
    "objective.Storage_installation_cost_EUR"
])

# Zeile 261-263 ERSETZEN durch:
cost_energy=costs.get('objective.Grid_energy_cost_EUR', 0),
cost_demand_charge=costs.get('objective.Demand_charge_cost_EUR', 0),
cost_co2=costs.get('objective.CO2_cost_EUR', 0),
```

---

## ⚠️ WICHTIGE WARNUNGEN (Sollten behoben werden)

### **Warnung 1: Fehlende year in Config**

**Datei:** `configs/scenarios/pf_then_rh_forecast.scenario.yaml`
**Zeile:** 17

**Problem:**
```yaml
horizon:
  type: full_year
  # year: 2023  ← FEHLT!
```

**Impact:**
- ⚠️ Könnte zu Default-Jahr führen oder Fehler werfen

**Fix:**
```yaml
horizon:
  type: full_year
  year: 2023
  enforce: true
```

---

### **Warnung 2: Multiprocessing Logging**

**Datei:** `scripts/run_forecast_benchmark.py`
**Zeilen:** 428, 434, 437

**Problem:**
```python
# In Worker-Process:
logger.info(f"[Worker] Running {method_name} (run {run_idx + 1})")
```

**Impact:**
- ⚠️ Logger in Child-Processes könnte nicht funktionieren (multiprocessing)
- ⚠️ Log-Messages könnten verloren gehen oder falsch formatiert werden

**Fix:**
```python
# Option 1: Print statt Logger in Workers
print(f"[Worker PID {os.getpid()}] Running {method_name}")

# Option 2: Multiprocessing-safe Logger konfigurieren
# (komplexer, aber besser)
```

---

### **Warnung 3: Excel-Export Error-Handling**

**Datei:** `scripts/run_forecast_benchmark.py`
**Zeile:** 492

**Problem:**
```python
try:
    from energis.io.exporter import write_scenario_workbook
except ImportError:
    logger.warning("openpyxl not available, skipping Excel export")
    return
```

**Impact:**
- ⚠️ Fehler in write_scenario_workbook() werden nicht gefangen
- ⚠️ Könnte Benchmark abbrechen bei Excel-Export-Fehler

**Fix:**
```python
try:
    from energis.io.exporter import write_scenario_workbook
except ImportError:
    logger.warning("openpyxl not available, skipping Excel export")
    return

try:
    write_scenario_workbook(...)
except Exception as e:
    logger.error(f"Excel export failed: {e}")
    return  # Continue without Excel
```

---

## 💡 POTENZIELLE STOLPERSTEINE (Nice-to-have)

### **Stolperstein 1: Keine Validierung der base_configs**

**Datei:** `scripts/run_forecast_benchmark.py`
**Zeile:** 32

**Problem:**
```python
def get_base_configs():
    return [
        "configs/base.yaml",
        "configs/tech_catalog.yaml",
        "configs/sites/default.site.yaml",
        "configs/systems/baseline.system.yaml",
    ]
```

**Impact:**
- ⚠️ Wenn Dateien nicht existieren → cryptischer Fehler später
- ⚠️ User hat keine klare Fehlermeldung

**Fix:**
```python
def get_base_configs():
    configs = [
        "configs/base.yaml",
        "configs/tech_catalog.yaml",
        "configs/sites/default.site.yaml",
        "configs/systems/baseline.system.yaml",
    ]
    # Validate
    for cfg in configs:
        if not os.path.exists(cfg):
            raise FileNotFoundError(f"Base config not found: {cfg}")
    return configs
```

---

### **Stolperstein 2: PF-Baseline könnte fehlen**

**Datei:** `energis/comparison/benchmark.py`
**Zeile:** 115-123

**Problem:**
```python
# Run baseline PF first
pf_cost = None
for method_name, overrides in methods:
    if method_name == "PF":
        # ...
        break

if pf_cost is None:
    logger.warning("No PF baseline found, using first method as reference")
```

**Impact:**
- ⚠️ Wenn User PF nicht in methods hat → keine cost_vs_pf Berechnung
- ⚠️ Warning wird geloggt aber könnte übersehen werden

**Fix:**
- Akzeptabel, aber könnte expliziter sein
- Alternativ: PF immer zuerst laufen lassen (auch wenn nicht in Liste)

---

### **Stolperstein 3: Parallelisierung ohne PF-Baseline**

**Datei:** `scripts/run_forecast_benchmark.py`
**Zeile:** 458

**Problem:**
```python
# In run_parallel_benchmark:
# Extract PF baseline cost
if method_name == "PF" and pf_cost is None and result.pf_result:
    pf_cost = sum(result.pf_result.costs.values())
```

**Impact:**
- ⚠️ Bei paralleler Ausführung: Welcher Worker findet PF zuerst?
- ⚠️ Race condition möglich
- ⚠️ cost_vs_pf könnte inkonsistent sein

**Fix:**
```python
# Besser: PF sequenziell VOR paralleler Ausführung
if "PF" in [m[0] for m in methods]:
    # Run PF first, sequentially
    pf_result = run_single_method("PF")
    pf_cost = sum(pf_result.pf_result.costs.values())

    # Then run others in parallel
    other_methods = [m for m in methods if m[0] != "PF"]
    results = run_parallel(other_methods)
```

---

### **Stolperstein 4: Series Keys inkonsistent**

**Datei:** `energis/comparison/benchmark.py`
**Zeile:** 234-236

**Problem:**
```python
grid_import = sum(series.get('P_buy', [0])) if 'P_buy' in series else 0
grid_export = sum(series.get('P_sell', [0])) if 'P_sell' in series else 0
demand = sum(series.get('demand_mw', [0])) if 'demand_mw' in series else 0
```

**Impact:**
- ⚠️ Keys könnten anders heißen (z.B. 'Grid_import_MW')
- ⚠️ Werte könnten 0 sein wenn Keys falsch

**Fix:**
- Prüfen welche Keys tatsächlich in series sind
- Dokumentieren oder flexibler machen

---

### **Stolperstein 5: Multiprocessing auf Windows**

**Datei:** `scripts/run_forecast_benchmark.py`
**Zeile:** 443

**Problem:**
```python
with mp.Pool(processes=num_jobs) as pool:
    worker_results = pool.map(worker_fn, work_items)
```

**Impact:**
- ⚠️ Auf Windows: Multiprocessing funktioniert anders (spawn statt fork)
- ⚠️ Könnte zu Pickle-Errors führen
- ⚠️ Logger-Konfiguration geht verloren

**Fix:**
```python
if __name__ == "__main__":
    mp.set_start_method('fork', force=True)  # Linux/Mac
    # oder
    mp.set_start_method('spawn', force=True)  # Windows
```

Besser: Bereits in main() Script implementiert ✓

---

## 📋 Zusammenfassung

### Kritisch (MUSS behoben werden):
1. ❌ **BenchmarkSuite Cost-Keys** - ALLE Metriken falsch!

### Wichtig (SOLLTE behoben werden):
2. ⚠️ Fehlende year in pf_then_rh_forecast.scenario.yaml
3. ⚠️ Multiprocessing Logging
4. ⚠️ Excel-Export Error-Handling

### Nice-to-have (KANN behoben werden):
5. 💡 Validierung base_configs
6. 💡 PF-Baseline Handling in Parallel-Mode
7. 💡 Series Keys Dokumentation
8. 💡 Windows Multiprocessing

---

## 🔧 Prioritäten für Fixes

### Priorität 1: SOFORT (vor nächstem Run!)
- **Fix Benchmark Cost-Keys** → Sonst sind alle Ergebnisse falsch!

### Priorität 2: Vor Production
- Fix pf_then_rh_forecast.scenario.yaml (year hinzufügen)
- Excel-Export Error-Handling

### Priorität 3: Optional
- Multiprocessing Logging
- Validierung base_configs
- PF-Baseline in Parallel

---

## ✅ Action Items

**Sofort:**
1. Fix benchmark.py Zeile 209 (CAPEX)
2. Fix benchmark.py Zeile 261-263 (Energy/CO2)
3. Fix pf_then_rh_forecast.scenario.yaml (year)

**Vor Production:**
4. Add Excel error handling
5. Test Multiprocessing Logging

**Optional:**
6. Add config validation
7. Improve PF-Baseline handling

---

## 🧪 Test-Checklist nach Fixes

Nach den Fixes testen:

```bash
# 1. Test single method
python scripts/run_forecast_benchmark.py --methods PF

# 2. Check cost values
python -c "
import json
with open('exports/benchmark/intermediate_PF.json') as f:
    data = json.load(f)
    print(f\"CAPEX: {data[0]['capex_eur']}\")
    print(f\"OPEX: {data[0]['opex_eur']}\")
    print(f\"Energy: {data[0]['cost_energy']}\")
    # Should NOT be all zeros!
"

# 3. Test parallel
python scripts/run_forecast_benchmark.py \
    --methods PF RH-Forecast-Noisy \
    --parallel --jobs 2

# 4. Test Excel export
python scripts/run_forecast_benchmark.py \
    --methods PF \
    --export-excel

# 5. Full benchmark
python scripts/run_forecast_benchmark.py \
    --mode all \
    --parallel \
    --jobs 4
```

---

## 📌 Hinweise

1. **Cost-Keys sind das größte Problem** - ohne Fix sind alle Benchmarks wertlos!
2. **Multiprocessing funktioniert grundsätzlich** - nur Logging könnte verbessert werden
3. **Excel-Export ist optional** - wenn er fehlschlägt, bleibt CSV
4. **Configs sind größtenteils korrekt** - nur pf_then_rh_forecast braucht year

**Status nach Fixes:** ✅ Production-Ready
**Status JETZT:** 🔴 Kritischer Bug - NICHT verwenden!
