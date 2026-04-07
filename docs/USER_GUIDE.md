# User Guide

This guide provides detailed instructions for configuring and running CALION optimizations.

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Configuration Reference](#2-configuration-reference)
3. [Running Optimizations](#3-running-optimizations)
4. [Understanding Results](#4-understanding-results)
5. [Advanced Features](#5-advanced-features)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Getting Started

### 1.1 Installation

```bash
# Clone repository
git clone https://github.com/LukasRuess98/Planing-Framework-for-Heat.git
cd Planing-Framework-for-Heat

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install with all dependencies
pip install -e ".[all]"
```

### 1.2 Solver Setup

**Gurobi (Recommended)**
- Academic licenses available free at: https://www.gurobi.com/academia/
- Install: `pip install gurobipy`

**GLPK (Open Source)**
- Linux: `sudo apt-get install glpk-utils`
- Mac: `brew install glpk`
- Windows: Download from https://winglpk.sourceforge.io/

### 1.3 First Run

```bash
# Run with example configuration
python -m calion.run configs/stadtbach.yaml

# Check results
ls exports/stadtbach/
```

---

## 2. Configuration Reference

CALION uses YAML configuration files. All settings can be specified in a single file.

### 2.1 Scenario Settings

```yaml
scenario:
  title: "My Optimization Run"
  tag: "scenario_v1"           # Used for output folder naming
  workflow: [PF]               # PF = Perfect Foresight, RH = Rolling Horizon
  fix_design: false            # If true, use existing capacities (no investment)

  horizon:
    type: "date_range"
    start: "2023-01-01 00:00"
    end: "2023-12-31 23:00"
    enforce: false             # If true, error on missing data
```

### 2.2 Data Source

```yaml
data_file: Import_Data.xlsx    # Input data file

site:
  input_file: Import_Data.xlsx
  year_target: 2023            # Filter data to this year
  tz: Europe/Berlin

  columns:                     # Column name mapping
    price_candidates: [Day_Ahead_Price, strompreis]
    heat_candidates: [Waermebedarf_MW, waermebedarf]
    co2_candidates: [CO2_consumption_based, co2]
```

### 2.3 Solver Settings

```yaml
run:
  dt_h: 1.0                    # Time step [hours]
  solver: gurobi               # gurobi or glpk
  solver_options:
    Threads: 0                 # 0 = use all cores
    MIPGap: 0.01              # Optimality gap tolerance
    TimeLimit: 3600           # Max solve time [seconds]
```

### 2.4 Grid and Costs

```yaml
grid:
  energy_fee_eur_mwh: 0.0
  demand_charge_eur_per_mw_y: 127240.0
  gridcost_eur_mwh: 61.6
  max_import_mw: 200.0
  max_export_mw: 100.0

costs:
  co2_price_eur_per_t: 100.0
  dump_cost_eur_per_mwh_th: 1.0
```

### 2.5 Fuels

```yaml
fuels:
  gas:
    price_eur_mwh: 58.6
    ef_kg_per_mwh_fuel: 201.6    # CO2 emission factor
  biomass:
    price_eur_mwh: 20.0
    ef_kg_per_mwh_fuel: 0.0       # Carbon neutral
  waste:
    price_eur_mwh: 10.0
    ef_kg_per_mwh_fuel: 0.0
```

### 2.6 Generators

```yaml
generators:
  hkw:                         # CHP unit
    th_eff: 0.743
    el_eff: 0.177
    fuel_bus: gas
  gtost:                       # Gas turbine with steam turbine
    th_eff: 0.466
    el_eff: 0.36
    fuel_bus: gas
  bmhkw:                       # Biomass CHP
    th_eff: 0.485
    el_eff: 0.177
    fuel_bus: biomass
  hws:                         # Hot water boiler
    th_eff: 0.936
    fuel_bus: gas
  p2h:                         # Power-to-Heat
    el_to_th_eff: 0.99
```

### 2.7 Heat Pumps

```yaml
heat_pumps:
  cop:
    deltaT_K: 20.0             # Temperature lift
    deltaTpp_K: 5.0            # Pinch point
    cop_fallback: 1.67         # COP when source unavailable
    sink_defaults:
      Tsink_out_K: 363.15      # 90°C supply temperature
      Tsink_in_K: 343.15       # 70°C return temperature
  types:
    standard:
      eta: 0.75                # Carnot efficiency factor
      FQ: 0.10                 # Auxiliary power factor
      min_load: 0.30           # Minimum part-load ratio
```

### 2.8 System Configuration

```yaml
system:
  heat_pumps:
    - id: HP1
      enabled: true
      type: standard
      wrg_source_column: WRG1_T_K        # Waste heat source temperature
      wrg_capacity_column: WRG1_Q_cap    # Available waste heat
      capacity_mw: 50.0
      investment:
        enabled: true
        min_mw: 5.0
        max_mw: 100.0
        capex_eur_per_mw: 400000
        activation_cost_eur: 250000
        lifetime_years: 15

  storage:
    enabled: true
    energy_mwh: 500.0
    power_mw: 50.0
    soc0_mwh: 500.0              # Initial state of charge
    investment:
      enabled: true
      min_energy_mwh: 100.0
      max_energy_mwh: 5000.0
      energy_capex_eur_per_mwh: 5000
      activation_cost_eur: 20000
      lifetime_years: 20

  generators:
    hkw:
      enabled: true
      cap_th_mw: 75.0
    gtost:
      enabled: true
      cap_th_mw: 41.3
    # ... other generators
```

### 2.9 Thermal Network

```yaml
thermal_network:
  enabled: true
  topology_file: configs/networks/brownfield.yaml
```

---

## 3. Running Optimizations

### 3.1 Command Line

```bash
# Basic run
python -m calion.run configs/stadtbach.yaml

# Override settings with additional config
python -m calion.run configs/stadtbach.yaml configs/high_co2_price.yaml

# Specify output directory
python -m calion.run configs/stadtbach.yaml --output exports/custom_run/
```

### 3.2 Jupyter Notebook

```python
from calion.config.merge import load_and_merge
from calion.io.loader import load_input_excel
from calion.models.system_builder import build_model
from calion.run.rolling_horizon import perfect_foresight

# Load configuration
cfg = load_and_merge(['configs/stadtbach.yaml'])

# Load input data
site_cfg = cfg.get('site', {})
data_file = cfg.get('data_file', 'Import_Data.xlsx')
table = load_input_excel(data_file, site_cfg)

# Build and solve model
model = build_model(table, cfg)
results = perfect_foresight(cfg, table)
```

### 3.3 Workflow Modes

**Perfect Foresight (PF)**
- Single optimization over entire horizon
- Assumes perfect knowledge of future
- Best for design optimization

**Rolling Horizon (RH)**
- Sequential optimization windows
- More realistic operational simulation
- Configurable look-ahead and commit periods

```yaml
scenario:
  workflow: [RH]
  rolling_horizon:
    window_hours: 48        # Optimization window length
    step_hours: 24          # Hours to commit before re-optimizing
    overlap_hours: 24       # Overlap with previous window
```

---

## 4. Understanding Results

### 4.1 Output Files

After running, results are saved in `exports/<tag>/`:

| File | Description |
|------|-------------|
| `summary.json` | Key performance indicators |
| `timeseries.csv` | Hourly dispatch values |
| `costs_breakdown.csv` | Detailed cost components |
| `emissions.csv` | CO₂ emissions by source |
| `investment.csv` | Optimal capacities |

### 4.2 Key Metrics

```json
{
  "total_cost_eur": 1234567.89,
  "heat_demand_mwh": 50000.0,
  "emissions_tco2": 5000.0,
  "specific_emissions_kgco2_mwh": 100.0,
  "renewable_share": 0.45,
  "network_losses_mwh": 500.0
}
```

### 4.3 Visualization

The Jupyter notebook includes built-in visualizations:

```python
from calion.io.plotter import plot_heat_balance, plot_costs

# Heat balance over time
plot_heat_balance(results, start="2023-01-01", end="2023-01-07")

# Cost breakdown pie chart
plot_costs(results)
```

---

## 5. Advanced Features

### 5.1 Investment Optimization

Enable capacity optimization:

```yaml
system:
  heat_pumps:
    - id: HP1
      investment:
        enabled: true        # Enable investment decision
        min_mw: 5.0          # Minimum size if built
        max_mw: 100.0        # Maximum size
        capex_eur_per_mw: 400000
        activation_cost_eur: 250000
        lifetime_years: 15
```

### 5.2 Stratified Storage

For large storage with temperature stratification:

```yaml
system:
  storage:
    type: stratified
    volume_m3: 10000
    T_hot_K: 363.15
    T_cold_K: 323.15
    insulation_thickness_m: 0.3
    tank_u_value_w_m2k: 0.3
```

### 5.3 Sensitivity Analysis

Run multiple scenarios programmatically:

```python
from calion.analysis.sensitivity import run_sensitivity

parameters = {
    'costs.co2_price_eur_per_t': [50, 100, 150, 200],
    'fuels.gas.price_eur_mwh': [40, 60, 80]
}

results = run_sensitivity('configs/stadtbach.yaml', parameters)
```

---

## 6. Troubleshooting

### 6.1 Common Errors

**"Solver not found"**
```bash
# Install GLPK as fallback
sudo apt-get install glpk-utils  # Linux
brew install glpk                 # Mac
```

**"Infeasible model"**
- Check that heat demand can be met with available capacity
- Verify fuel and electricity prices are reasonable
- Check for conflicting constraints in config

**"Out of memory"**
- Reduce optimization horizon
- Use Rolling Horizon instead of Perfect Foresight
- Increase solver MIPGap tolerance

### 6.2 Performance Tips

1. **Use Gurobi** for problems > 1000 time steps
2. **Increase MIPGap** (e.g., 0.05) for faster solutions
3. **Reduce horizon** for initial testing
4. **Disable unused components** to reduce model size

### 6.3 Logging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 5.4 Phase 1: Network State Validation & Constraints

CALION enforces **physical validity constraints** on thermal network states to ensure optimization results remain realistic.

### 5.4.1 What is Phase 1?

Phase 1 constraints prevent unphysical states like:
- Supply temperature below return temperature ❌
- Operating pressure below cavitation threshold ❌
- Pipe flow velocity causing stagnation or excessive wear ❌

All constraints are **configurable and can be toggled** via YAML configuration.

### 5.4.2 Configuration

Phase 1 constraints are defined in the `state_validation` section:

```yaml
state_validation:
  # Temperature constraints
  temperature_constraints:
    # Enforce T_supply >= T_return at every node
    enforce_supply_ge_return: true
    # Tolerance for numerical stability [°C]
    temperature_tolerance_c: 0.1
  
  # Pressure constraints
  pressure_constraints:
    # Minimum absolute pressure to prevent cavitation [bar]
    min_pressure_bar: 0.5
    # Maximum allowable pressure drop in pipes [bar]
    max_pressure_drop: 2.0
  
  # Flow constraints
  flow_constraints:
    # Minimum velocity to prevent stagnation [m/s]
    min_velocity_m_s: 0.3
    # Maximum velocity for noise/wear control [m/s]
    max_velocity_m_s: 2.5
```

These settings are included in `configs/base.yaml` with sensible defaults.

### 5.4.3 Customization

Override constraints per scenario:

```yaml
# In your scenario YAML
state_validation:
  pressure_constraints:
    min_pressure_bar: 1.0  # Stricter than default
  flow_constraints:
    max_velocity_m_s: 2.0  # Limit maximum velocity
```

Disable constraints entirely:

```yaml
state_validation:
  temperature_constraints:
    enforce_supply_ge_return: false
  flow_constraints:
    min_velocity_m_s: 0.0  # No minimum velocity
```

### 5.4.4 Validation Reports

After optimization, CALION automatically validates network states and exports a report:

```
exports/<tag>/thermal_network/state_validation_report.json
```

Report includes:
- Total issues found (errors and warnings)
- Violations by component type (nodes, pipes)
- Detailed issue descriptions with bounds

**Example**:
```json
{
  "total_issues": 0,
  "errors": 0,
  "warnings": 0,
  "by_severity": {"error": 0, "warning": 0, "info": 0},
  "by_component": {"node": 0, "pipe": 0, "global": 0},
  "passed": true
}
```

### 5.4.5 Programmatic Usage

Access validation results in Python:

```python
from calion.models.network_validator import NetworkValidator

# After solving
validator = NetworkValidator(model, config, time_set)
results = validator.validate_all()

# Check results
if results['passed']:
    print("✓ Network state is physically valid")
else:
    print(f"✗ Found {results['errors']} violations")
    for issue in results['issues']:
        print(f"  {issue}")

# Export detailed report
validator.export_report('validation_report.json')
```

### 5.4.6 Performance Impact

Phase 1 constraints have **minimal computational cost**:
- <5% solver time overhead on typical 24-hour models
- Usually 1-2 additional constraints per node/pipe
- No additional variables needed

### 5.4.7 Troubleshooting

**"Phase 1 constraints causing infeasibility"**

This is rare but can occur if:
1. Network is physically under-designed
2. Demand cannot be met with available capacity
3. Pressure drop exceeds pump capability

**Solution**: 
- Relax bounds temporarily: `min_pressure_bar: 0.1`
- Increase pipe diameter
- Review network design
- Check heat demand availability

---

## Questions?

- Check the [Technical Methodology](METHODOLOGY.md) for model details
- Review [Data Format](DATA_FORMAT.md) for input requirements
- See [Network Topology Analysis](NETWORK_TOPOLOGY_AND_STATE_CONSTRAINTS_ANALYSIS.md) for constraint details
- Open an issue on GitHub for bugs or feature requests
