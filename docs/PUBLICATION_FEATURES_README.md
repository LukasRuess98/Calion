# Publication-Ready Features - User Guide

**Version:** 2.0 (2025-11-18)
**Target:** Applied Energy and similar peer-reviewed journals
**Status:** ✅ Production-ready

---

## Overview

This guide explains how to use the new publication-ready features in the EnerGIS heat planning framework. All improvements are **backward-compatible** and can be enabled through configuration files.

### What's New?

1. **P2H (Electrode Boiler):** Load-dependent efficiency + minimum load constraints
2. **Storage:** Temperature-dependent losses + literature-based parameters
3. **Sensitivity Analysis:** Comprehensive framework for parameter variation studies
4. **Documentation:** Complete methods section for scientific publications

---

## Table of Contents

- [Quick Start](#quick-start)
- [P2H Improvements](#p2h-improvements)
- [Storage Improvements](#storage-improvements)
- [Sensitivity Analysis](#sensitivity-analysis)
- [Configuration Examples](#configuration-examples)
- [Integration with Runner](#integration-with-runner)
- [Backward Compatibility](#backward-compatibility)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

No additional dependencies required. The improvements are part of the core framework.

```bash
# Verify installation
python -c "from energis.analysis import create_standard_sensitivity_study; print('✓ OK')"
python -c "from energis.utils.storage_utils import recommend_storage_parameters; print('✓ OK')"
```

### Running Integration Tests

```bash
# Test all new features
PYTHONPATH=. python examples/runner_integration_test.py

# Test component usage
PYTHONPATH=. python examples/improved_component_usage.py

# Test sensitivity analysis
PYTHONPATH=. python examples/publication_sensitivity_analysis.py
```

---

## P2H Improvements

### Features

✅ **Minimum Load Constraint:** Realistic operation limits (typically 20-30%)
✅ **Time-Varying Efficiency:** Load-dependent or ambient-dependent efficiency
✅ **Binary On/Off Variable:** Enforces realistic switching behavior
✅ **Backward Compatible:** Old configs still work

### Configuration

#### Option 1: Simple Minimum Load (Recommended Start)

```yaml
# configs/tech_catalog.yaml
generators:
  p2h:
    el_to_th_eff: 0.99
    min_load: 0.25  # NEW: 25% minimum load
```

**Effect:**
- P2H can only operate at ≥25% capacity or be off completely
- Binary variable `on[t]` is automatically created
- Constraints: `Q_th[t] ≥ 0.25 * cap_th * on[t]`

#### Option 2: Time-Varying Efficiency

```yaml
# configs/tech_catalog.yaml
generators:
  p2h:
    el_to_th_eff: 0.99
    min_load: 0.25
    eff_series: [0.99, 0.98, 0.99, 0.98, ...]  # One value per timestep
```

**Effect:**
- Efficiency varies with load or ambient conditions
- Captures ±1-3% realistic variation
- Maintains MILP structure (linear constraint)

#### Option 3: Part-Load Penalty

```yaml
# configs/tech_catalog.yaml
generators:
  p2h:
    el_to_th_eff: 0.99
    min_load: 0.25
    part_load_penalty: 0.02  # 2% efficiency loss at minimum load
```

**Effect:**
- Efficiency penalty at minimum load operation
- For documentation purposes (actual penalty in eff_series)

### Mathematical Formulation

```
Variables:
  Q_th[t] ∈ ℝ≥0       : Thermal output [MW]
  P_el[t] ∈ ℝ≥0       : Electrical input [MW]
  on[t] ∈ {0,1}        : On/off status (if min_load > 0)

Constraints:
  Q_th[t] ≤ cap_th · on[t]                    (capacity)
  Q_th[t] ≥ min_load · cap_th · on[t]         (minimum load)
  Q_th[t] = eff[t] · P_el[t]                  (efficiency link)
```

### Python API Usage

```python
from energis.models.blocks.p2h import P2HBlock

# Create P2H with minimum load
p2h = P2HBlock(
    name="P2H",
    eff=0.99,
    cap_th_mw=10.0,
    min_load=0.25,  # NEW
    eff_series=None,  # Optional
    part_load_penalty=0.0  # Optional
)

# Attach to Pyomo model
fs = p2h.attach(model, timesteps, config, buses)

# Access variables
Q_th = fs["Q_th_out"]
P_el = fs["P_el_in"]
on = fs.get("on", None)  # Binary variable (if min_load > 0)
```

---

## Storage Improvements

### Features

✅ **Temperature-Dependent Losses:** Seasonal variation ±10-20%
✅ **Literature-Based Parameters:** 3 storage types with validated defaults
✅ **Stratification Bonus:** Efficiency improvements from tank geometry
✅ **Multiple Configuration Methods:** Series, columns, or constants

### Configuration

#### Option 1: Temperature-Dependent Losses (Recommended)

```yaml
# configs/tech_catalog.yaml
storage:
  investment_defaults:
    # ... (existing config)

# configs/systems/baseline.system.yaml
storage:
  enabled: true
  max_energy_mwh: 100.0
  max_power_mw: 30.0
  eff_charge: 0.98
  eff_discharge: 0.98
  # Option A: Provide loss series directly in config
  loss_hour_series: [0.000850, 0.000800, ...]  # One value per timestep
  # Option B: Include 'storage_loss_hour' column in input data
  # Option C: Use constant (legacy, less accurate)
  loss_hour: 0.0005
```

#### Option 2: Calculate Loss Series in Python

```python
from energis.utils.storage_utils import calculate_temp_dependent_loss_series

# Load ambient temperature data
ambient_temps_K = [273.15, 278.15, 283.15, ...]  # From weather data

# Calculate loss series
loss_series = calculate_temp_dependent_loss_series(
    ambient_temp_series_K=ambient_temps_K,
    storage_temp_K=363.15,  # 90°C storage
    reference_loss_rate=0.0005,  # Baseline at 50 K ΔT
    reference_delta_T_K=50.0
)

# Use in config
config["storage"]["loss_hour_series"] = loss_series
```

#### Option 3: Use Literature-Based Parameters

```python
from energis.utils.storage_utils import recommend_storage_parameters

# Get recommended parameters
params = recommend_storage_parameters(
    storage_type="hot_water_tank",  # or "pcm", "pit_storage"
    capacity_mwh=100.0
)

print(params)
# {
#     'charge_efficiency': 0.98,
#     'discharge_efficiency': 0.98,
#     'hourly_loss_rate': 0.0005,
#     'min_soc_fraction': 0.05,
#     'max_soc_fraction': 0.95,
#     'power_to_energy_ratio': 0.3,
#     'reference_temp_K': 363.15,
#     'description': '...'
# }

# Apply to config
config["storage"]["eff_charge"] = params["charge_efficiency"]
config["storage"]["eff_discharge"] = params["discharge_efficiency"]
config["storage"]["loss_hour"] = params["hourly_loss_rate"]
```

### Storage Types and Default Parameters

| Storage Type | Charge Eff | Discharge Eff | Daily Loss | Reference |
|--------------|------------|---------------|------------|-----------|
| Hot Water Tank | 0.98 | 0.98 | 1.2% | Energinet (2020) |
| PCM | 0.96 | 0.96 | 0.72% | Sharma et al. (2009) |
| Pit Storage | 0.93 | 0.93 | 0.48% | Schmidt & Miedaner (2012) |

### Mathematical Formulation

```
Variables:
  E[t] ∈ ℝ≥0              : Energy content [MWh]
  Q_c[t] ∈ ℝ≥0            : Charge power [MW]
  Q_d[t] ∈ ℝ≥0            : Discharge power [MW]
  charge_mode[t] ∈ {0,1}  : Charge mode indicator
  discharge_mode[t] ∈ {0,1} : Discharge mode indicator

Constraints:
  E[t] = E[t-1]·loss[t] + eff_c[t]·Q_c[t]·Δt - Q_d[t]·Δt/eff_d[t]
  Q_c[t] ≤ cap_p · charge_mode[t]
  Q_d[t] ≤ cap_p · discharge_mode[t]
  charge_mode[t] + discharge_mode[t] ≤ 1
```

**Key Feature:** `loss[t]` can vary with temperature difference

### Physical Basis

```
Q_loss = h · A · (T_storage - T_ambient)

Where:
  h: Heat transfer coefficient [W/(m²·K)]
  A: Surface area [m²]
  T_storage: Storage temperature [K]
  T_ambient: Ambient temperature [K]

Loss rate = Q_loss / E_storage
```

---

## Sensitivity Analysis

### Features

✅ **Standard Parameter Variations:** Pre-defined ranges for Applied Energy
✅ **Automated Analysis:** One-at-a-time sensitivity study
✅ **Publication Tables:** Markdown-formatted output
✅ **Parameter Ranking:** Identify most critical assumptions

### Quick Example

```python
from energis.analysis import (
    create_standard_sensitivity_study,
    run_sensitivity_analysis,
    format_sensitivity_table,
    calculate_sensitivity_indices,
)

# 1. Create standard variations (±3-5% for efficiencies, ±20% for prices)
variations = create_standard_sensitivity_study()

# 2. Define optimization function
def run_optimization(config):
    # Your optimization code here
    result = optimize_system(config)

    return SensitivityResult(
        param_path="",
        param_value=0.0,
        variation_label="",
        objective_value=result.total_cost,
        key_metrics={
            "co2_emissions": result.emissions,
            "renewable_share": result.renewable_fraction
        }
    )

# 3. Run analysis
results = run_sensitivity_analysis(base_config, variations, run_optimization)

# 4. Generate publication table
table = format_sensitivity_table(results, metric_name="objective_value")
print(table)

# 5. Calculate sensitivity indices
indices = calculate_sensitivity_indices(results)
for param, index in sorted(indices.items(), key=lambda x: x[1], reverse=True):
    print(f"{param}: {index:.4f}")
```

### Standard Variations

| Parameter | Base Value | Variations | Range |
|-----------|------------|------------|-------|
| P2H efficiency | 0.99 | [97%, 100%, 103%] | ±3% |
| HP COP factor | 0.75 | [95%, 100%, 105%] | ±5% |
| Storage loss | 0.0005/h | [50%, 100%, 150%] | ±50% |
| Gas price | 58.6 €/MWh | [80%, 100%, 120%] | ±20% |
| Electricity price | 50.0 €/MWh | [80%, 100%, 120%] | ±20% |

### Custom Variations

```python
from energis.analysis import ParameterVariation

# Define custom variation
custom_var = ParameterVariation(
    param_path="generators.hkw.th_eff",
    base_value=0.743,
    variations=[0.9, 1.0, 1.1],  # ±10%
    variation_type="multiplicative",
    description="HKW thermal efficiency",
    units="-"
)

# Add to variations list
variations = create_standard_sensitivity_study()
variations.append(custom_var)
```

---

## Configuration Examples

### Complete Example: Publication-Ready Setup

```yaml
# configs/tech_catalog.yaml

fuels:
  gas:
    price_eur_mwh: 58.6
    ef_kg_per_mwh_fuel: 201.6

generators:
  p2h:
    el_to_th_eff: 0.99
    min_load: 0.25  # NEW: Realistic minimum load
    # eff_series: null  # Optional: time-varying efficiency

  hkw:
    th_eff: 0.743
    el_eff: 0.177
    fuel_bus: gas

storage:
  investment_defaults:
    enabled: true
    energy_capacity_min_mwh: 1.0
    energy_capacity_max_mwh: 10000.0
    # ... (other parameters)

heat_pumps:
  cop:
    deltaT_K: 20.0
    deltaTpp_K: 5.0
    sink_defaults:
      Tsink_out_K: 363.15
      Tsink_in_K: 343.15
  types:
    standard:
      eta: 0.75
      FQ: 0.10
      min_load: 0.30
```

```yaml
# configs/systems/baseline.system.yaml

system:
  generators:
    p2h:
      enabled: true
      cap_th_mw: 10.0
    hkw:
      enabled: true
      cap_th_mw: 75.0

  storage:
    enabled: true
    min_energy_mwh: 5.0  # 5% dead volume
    max_energy_mwh: 95.0  # 95% max (5% expansion)
    max_power_mw: 30.0
    eff_charge: 0.98
    eff_discharge: 0.98
    # Option 1: Temperature-dependent losses (recommended)
    loss_hour_series: [...]  # Calculate externally
    # Option 2: Constant losses (legacy)
    loss_hour: 0.0005
```

### Input Data with Time Series

```csv
# input_data.csv
timestamp,heat_demand,electricity_price,ambient_temp_K,storage_loss_hour
2025-01-01 00:00,50.0,45.0,273.15,0.000900
2025-01-01 01:00,48.0,42.0,272.15,0.000920
...
```

**Note:** If `storage_loss_hour` column exists, it overrides config value

---

## Integration with Runner

### Step-by-Step Guide

1. **Update Configuration Files**

```bash
# Edit tech catalog
nano configs/tech_catalog.yaml
# Add p2h.min_load = 0.25

# Edit system config
nano configs/systems/baseline.system.yaml
# Adjust storage parameters
```

2. **Prepare Input Data (Optional)**

```python
from energis.utils.storage_utils import calculate_temp_dependent_loss_series
import pandas as pd

# Load existing data
data = pd.read_csv("input/data.csv")

# Calculate loss series
loss_series = calculate_temp_dependent_loss_series(
    ambient_temp_series_K=data["ambient_temp_K"].values,
    storage_temp_K=363.15
)

# Add to data
data["storage_loss_hour"] = loss_series
data.to_csv("input/data_improved.csv", index=False)
```

3. **Run Optimization**

```bash
# Run with improved features
python -m energis.run \
    --config configs/systems/baseline.system.yaml \
    --data input/data_improved.csv \
    --output output/improved/

# Compare with baseline
python -m energis.run \
    --config configs/systems/baseline.system.yaml \
    --data input/data.csv \
    --output output/baseline/
```

4. **Analyze Results**

```python
# Load results
import pandas as pd
baseline = pd.read_csv("output/baseline/results.csv")
improved = pd.read_csv("output/improved/results.csv")

# Compare
print(f"Baseline cost: {baseline['total_cost'].sum():.0f} EUR")
print(f"Improved cost: {improved['total_cost'].sum():.0f} EUR")
```

---

## Backward Compatibility

### Guaranteed Compatibility

✅ **All existing configs work unchanged**
✅ **No breaking API changes**
✅ **Optional parameters with sensible defaults**
✅ **Tested with legacy configurations**

### Default Behavior (No Config Changes)

| Component | Old Behavior | New Behavior (Default) | Status |
|-----------|--------------|------------------------|--------|
| P2H | Constant eff, no min load | Same (min_load=0.0) | ✅ Identical |
| Storage | Constant losses | Same (no loss_series) | ✅ Identical |
| Heat Pump | COP tables | Same (unchanged) | ✅ Identical |

### Migration Guide

**Option 1: Keep Everything As-Is**
- No changes needed
- Framework works exactly as before

**Option 2: Gradual Migration**
```yaml
# Step 1: Add minimum load to P2H (low effort, high benefit)
generators:
  p2h:
    min_load: 0.25

# Step 2: Add temperature-dependent losses (medium effort, medium benefit)
storage:
  loss_hour_series: [...]  # Calculate externally

# Step 3: Run sensitivity analysis (high effort, high publication value)
# Use energis.analysis module
```

**Option 3: Full Upgrade**
- Update all configs with new parameters
- Calculate temperature-dependent loss series
- Run comprehensive sensitivity analysis
- Generate publication-ready plots

---

## Troubleshooting

### Common Issues

#### 1. "No module named 'energis.analysis'"

```bash
# Solution: Verify PYTHONPATH
export PYTHONPATH=/path/to/Planing-Framework-for-Heat:$PYTHONPATH
python -c "from energis.analysis import create_standard_sensitivity_study"
```

#### 2. "min_load must be in [0, 1]"

```yaml
# Problem: Invalid min_load value
generators:
  p2h:
    min_load: 25  # WRONG: Should be fraction, not percentage

# Solution: Use fraction
generators:
  p2h:
    min_load: 0.25  # CORRECT: 25% as fraction
```

#### 3. "Efficiency series length does not match time index length"

```python
# Problem: Wrong number of efficiency values
eff_series = [0.99, 0.98]  # Only 2 values for 24 timesteps

# Solution: Provide correct length
timesteps = len(model.t)
eff_series = [0.99] * timesteps  # Repeat for all timesteps
```

#### 4. Storage loss series not applied

```yaml
# Check configuration order (priority):
# 1. loss_hour_series in config (highest priority)
# 2. 'storage_loss_hour' column in data
# 3. loss_hour constant (lowest priority)

# Verify which source is being used:
# Check system_builder.py line ~490:
# loss_series = sto_cfg.get("loss_hour_series") or column_series("storage_loss_hour")
```

### Performance Issues

**P2H with Binary Variable:**
- Problem: Binary variables increase solve time
- Solution: Only use min_load > 0 if realistic operation requires it
- Impact: ~10-30% longer solve time for MILP

**Temperature-Dependent Losses:**
- Problem: Time-varying parameters slightly increase problem size
- Solution: Use constant losses for preliminary studies, temperature-dependent for final publication
- Impact: Negligible (<5% solve time increase)

---

## Testing and Validation

### Unit Tests

```bash
# Test individual components
PYTHONPATH=. python examples/improved_component_usage.py

# Expected output:
# ✅ P2H with minimum load: OK
# ✅ Storage with temp-dependent losses: OK
# ✅ Recommended parameters: OK
```

### Integration Tests

```bash
# Test framework integration
PYTHONPATH=. python examples/runner_integration_test.py

# Expected output:
# ✅ 5/5 tests passed
# 🎉 ALL TESTS PASSED!
```

### Sensitivity Analysis Test

```bash
# Test sensitivity framework
PYTHONPATH=. python examples/publication_sensitivity_analysis.py

# Expected output:
# Sensitivity indices calculated
# Publication table generated
```

---

## References

### Documentation

- **Complete Methods:** `docs/PUBLICATION_READY_METHODS.md`
- **Component Analysis:** Generated during review (`/tmp/component_analysis.md`)
- **This Guide:** `docs/PUBLICATION_FEATURES_README.md`

### Examples

- `examples/improved_component_usage.py` - Component demonstrations
- `examples/publication_sensitivity_analysis.py` - Sensitivity analysis workflow
- `examples/runner_integration_test.py` - Integration testing

### Literature

- Energinet (2020). Technology Catalogue for Energy Storage
- IEA ECES Annex 15: Thermal Storage Applications
- Schmidt & Miedaner (Energy Procedia, 2012)
- Sharma et al. (Applied Energy, 2009)

---

## Support

### Questions?

1. Check `docs/PUBLICATION_READY_METHODS.md` for detailed methods
2. Review examples in `examples/` directory
3. Run integration tests to verify setup
4. Consult literature references for parameter validation

### Contributing

If you find issues or have improvements:
1. Test with `examples/runner_integration_test.py`
2. Update documentation in `docs/`
3. Add examples if needed
4. Submit with full backward compatibility

---

## Changelog

### Version 2.0 (2025-11-18)

**Added:**
- P2H minimum load constraint and time-varying efficiency
- Storage temperature-dependent losses and literature parameters
- Comprehensive sensitivity analysis framework
- Complete publication-ready documentation

**Changed:**
- Extended `P2HBlock` with optional parameters
- Enhanced system_builder.py to read new config parameters
- Updated config schema in tech_catalog.yaml

**Maintained:**
- Full backward compatibility with existing configurations
- All existing tests pass unchanged
- No breaking API changes

---

**Last Updated:** 2025-11-18
**Framework Version:** 2.0
**Publication Status:** Ready for Applied Energy submission
