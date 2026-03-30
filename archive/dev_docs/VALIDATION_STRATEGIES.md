# Framework Validierung & Qualitätssicherung
**Datum:** 2026-03-27

## Strategie 1: Unit Tests (Component-Level) ✅

Already in place: `tests/test_*.py`

```bash
# Alle Tests ausführen
python -m pytest tests/ -v

# Spezifische Test-Suites
python -m pytest tests/test_system_builder.py -v                # Model construction
python -m pytest tests/test_exporter.py -v                      # Export functionality
python -m pytest tests/test_full_system.py -v                   # End-to-end
```

**Was wird getestet:**
- ✅ Model building correctness
- ✅ Constraint formulation
- ✅ Variable initialization
- ✅ Export file generation

---

## Strategie 2: Ergebnisvalidierung (Output Checks)

### 2a. **Energie-Bilanz Check**
```python
# Demand ≈ Supply (Wärmefluss-Bilanz)
demand_sum = df['heat_demand_MW'].sum()
supply_sum = df['Q_boiler'].sum() + df['Q_hp'].sum() + df['storage_discharge'].sum()

assert abs(demand_sum - supply_sum) < 1%, "Wärmebilanz nicht ausgeglichen!"
```

**Expected:** ±0.5% Abweichung (Netzwerk-Verluste)

### 2b. **Speicher-Konsistenz**
```python
# Speicher-Laden + Entladen prüfen
soc = df['storage_SOC_MWh']
charge = df['storage_charge_MW']
discharge = df['storage_discharge_MW']

# SOC sollte nie negativ sein
assert (soc >= 0).all(), "Speicher unterschreitet Null!"

# Ladung & Entladung nicht gleichzeitig
assert ((charge > 0) & (discharge > 0)).sum() == 0, "Gleichzeitiges Laden/Entladen!"
```

### 2c. **Kapazitätsgrenzen**
```python
# Alle Outputs ≤ Kapazität
assert (df['Q_hp'] <= 100).all(), "HP überschreitet Kapazität!"
assert (df['P_buy'] <= 20).all(), "Stromkauf überschreitet Limit!"
```

---

## Strategie 3: Wirtschaftliche Validierung

### 3a. **Kostenplausibilität**
```python
# Jahreskosten sollten in sinnvollem Bereich liegen
annual_cost = solver_result.get('objective_value', 0)
cost_per_gwh = annual_cost / (demand_sum / 1000)

# Typisch: 30–60 €/MWh für district heating
assert 30 < cost_per_gwh < 150, f"Kosten unrealistisch: {cost_per_gwh} €/MWh"
```

### 3b. **Brennstoff-Mix Prüfung**
```python
# Wärmepumpe sollte günstiger sein als Boiler (wenn Strom billig)
hp_heat = df['Q_hp'].sum()
boiler_heat = df['Q_boiler'].sum()

if electricity_price < gas_price * 3:  # CoP ≈ 3
    assert hp_heat > boiler_heat * 0.5, "HP unterdimensioniert?"
```

---

## Strategie 4: Sensitivitätsanalyse

### 4a. **Parametervariationen testen**
```python
configs_to_test = [
    ("baseline", base_config),
    ("high_el_price", {**base_config, "electricity_price": 100}),
    ("high_gas_price", {**base_config, "gas_price": 80}),
    ("small_storage", {**base_config, "storage_mwh": 100}),
    ("large_storage", {**base_config, "storage_mwh": 1000}),
]

for name, cfg in configs_to_test:
    result = run_optimization(cfg)
    print(f"{name}: Cost={result['cost']:.0f}, HP={result['hp_fraction']:.1%}")
```

**Expected Behavior:**
- Höherer Strompreis → mehr Boiler
- Höherer Gaspreis → mehr HP
- Größerer Speicher → bessere Arbitrage

---

## Strategie 5: Vergleichstests (Benchmarking)

### 5a. **Known Solutions**
```python
# Test mit analytisch bekannter Lösung
# z.B. reiner Gas-Heizung (ohne HP)
simple_result = {
    'cost': demand_gwh * gas_price / eta_boiler,
    'hp_output': 0,
}

# Unser Optimum sollte günstiger sein
optimized_result = run_optimization(config)
assert optimized_result['cost'] <= simple_result['cost'] * 1.05
```

### 5b. **Cross-Solver Validation**
```bash
# Mit verschiedenen Solvern testen
solvers = ["appsi_highs", "gurobi", "cplex", "cbc"]

for solver in solvers:
    config['run']['solver'] = solver
    result = run_optimization(config)
    results.append(result)

# Alle sollten ≈ gleiche Lösung haben
cost_range = max(r['cost'] for r in results) - min(r['cost'] for r in results)
assert cost_range < max(r['cost'] for r in results) * 0.01  # <1% Abweichung
```

---

## Strategie 6: Physikalische Validierung

### 6a. **CoP-Plausibilität (Wärmepumpe)**
```python
# COP (Coefficient of Performance) sollte realistisch sein
# COP = Wärmeoutput / Elektrizitäts-Input
for t in time_steps:
    if P_hp[t] > 0.1:  # Wenn HP läuft
        cop = Q_hp[t] / P_hp[t]
        assert 2.5 < cop < 5.0, f"Unrealistischer CoP: {cop}"
```

### 6b. **Netzwerk-Verluste**
```python
# Bei Dispatchmodellen gering halten
network_loss_percent = df['network_loss_MW'].sum() / demand_sum

# Typisch 5-15% für Fernwärme
assert network_loss_percent < 0.25, "Zu hohe Netzwerk-Verluste!"
```

---

## Strategie 7: Automated Validation Suite

```python
"""
validation.py - Automatisierte Qualitätsprüfung
"""

from pathlib import Path
import pandas as pd

class OptimizationValidator:
    def __init__(self, result_dir):
        self.df = pd.read_csv(f"{result_dir}/unified_timeseries.csv", sep=';')
        self.manifest = json.load(open(f"{result_dir}/export_manifest.json"))
    
    def validate_all(self):
        """Führe alle Checks durch"""
        checks = [
            self.check_energy_balance,
            self.check_storage_limits,
            self.check_capacity_limits,
            self.check_cost_plausibility,
            self.check_no_nans,
            self.check_time_coverage,
        ]
        
        results = {}
        for check in checks:
            try:
                check()
                results[check.__name__] = "✅ PASSED"
            except AssertionError as e:
                results[check.__name__] = f"❌ FAILED: {e}"
        
        return results
    
    def check_energy_balance(self):
        """Wärmebilanz"""
        demand = self.df['heat_demand_MW'].sum()
        # ... impl
    
    def check_storage_limits(self):
        """Speicher nie negativ"""
        assert (self.df['storage_SOC_MWh'] >= 0).all()
    
    # ... weitere Checks

# Verwendung:
validator = OptimizationValidator("outputs/runs/thermal_network_results")
results = validator.validate_all()

for check, result in results.items():
    print(f"{check:40} {result}")
```

---

## Strategie 8: Regression Tests

```bash
# Speichere bekannte gute Ergebnisse
python -m calion.run configs/baseline.yaml > baseline_results.json

# Später: Prüfe ob sich Ergebnisse signifikant ändern
python -m calion.run configs/baseline.yaml > current_results.json

# Vergleich
cost_diff = abs(current - baseline) / baseline
assert cost_diff < 0.01, "Regression detected!"  # Max 1% Abweichung
```

---

## Strategie 9: Integration Tests

```python
"""
Test mit verschiedenen Config-Kombinationen
"""

scenarios = [
    "level1_copperplate.yaml",           # Einfach: 1 Knoten
    "level2_5node.yaml",                 # Mittel: 5 Knoten
    "level3_30node_template.yaml",       # Komplex: 30 Knoten
]

for scenario in scenarios:
    result = run_optimization(f"configs/{scenario}")
    
    # Basis-Checks
    assert result['status'] == 'optimal'
    assert result['cost'] > 0
    assert len(result['timeseries']) > 0
    
    print(f"✅ {scenario}: {result['cost']:,.0f} EUR")
```

---

## Strategie 10: Dokumentation & Referenzen

### Dokumentieren Sie wichtige Benchmarks:

```yaml
# benchmarks.yaml - Referenzergebnisse für Vergleiche

baseline_scenario:
  annual_cost_eur: 15925510
  heat_output_gwh: 516.59
  cop_average: 3.2
  solver_time_s: 100
  solver_gap_percent: 0.0

scenarios:
  high_price:
    annual_cost_eur: 17250000    # +8%
    hp_percentage: 45%            # < baseline
  
  large_storage:
    annual_cost_eur: 15800000    # -0.8%
    hp_on_hours: 7500             # Mehr Flexibilität
```

---

## Checkliste: Framework-Validierung

- [ ] **Unit Tests** - Alle `pytest` Tests bestanden
- [ ] **Energy Balance** - Demand ≈ Supply (±0.5%)
- [ ] **Storage Limits** - SOC ∈ [0, max_capacity]
- [ ] **Capacity Limits** - Alle Assets ≤ Kapazität
- [ ] **Cost Plausibility** - 30–80 €/MWh (realistic)
- [ ] **No NaN/Null** - Alle Daten vollständig
- [ ] **Time Coverage** - Alle 8,760 Stunden
- [ ] **CoP Realistic** - 2.5–5.0 (Wärmepumpe)
- [ ] **Solver Optimality** - Gap < 0.1% (or target)
- [ ] **Cross-Solver** - ±1% Abweichung zwischen Solvern
- [ ] **Regression Test** - Vs. Baseline < 1% Drift
- [ ] **Sensitivity** - Plausible Reaktionen auf Parameter

---

## Ausgehen in die Praxis

```bash
# 1. Run complete validation
python validate_exports.py
python check_csv_completeness.py
python analyze_solution_variables.py

# 2. Run tests
python -m pytest tests/ -v

# 3. Run regression benchmark
python -m calion.run configs/scenarios/stadtbach_baseline_2023.yaml
# → Vergleiche mit EXPORT_VERIFICATION_REPORT.md

# 4. Check sensitivity
for price in 40 60 80 100; do
  python -m calion.run --override "costs.co2_price_eur_per_t=$price"
done
```

---

## Tipps für Ihre Gruppe

1. **Automatisiert testen** - CI/CD Pipeline (GitHub Actions)
2. **Dokumentiert Benchmarks** - Bekannte gute Ergebnisse speichern
3. **Regression früh merken** - Baseline vor jedem Change
4. **Domain Experts einbinden** - Physikalische Plausibilität prüfen
5. **Solver-Vergleich** - Nicht nur HiGHS testen

Welcher Validierungsaspekt ist für euch am wichtigsten?
