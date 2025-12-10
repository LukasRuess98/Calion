# Stadtbach Real Data Optimization Guide

**Date**: 2025-12-10
**Status**: Ready for real data integration
**Priority**: Short-term (1-2 weeks)

## Overview

This guide explains how to prepare and run real optimization scenarios for the Stadtbach district heating network using actual operational data instead of synthetic test data.

## Current Status

### ✅ Complete
1. **Network Topology**: 12 nodes, 11 pipes configured in `configs/networks/stadtbach_network.yaml`
2. **System Configuration**: Heat pumps, generators, storage in `configs/systems/stadtbach.system.yaml`
3. **Scenario Template**: `configs/scenarios/stadtbach_1week.scenario.yaml` ready
4. **Thermal Network Model**: MIQP formulation with temperature-dependent heat losses
5. **Results Export**: CSV and JSON exports for all network variables

### 🔄 Pending
1. **Real Time Series Data**: Demand, weather, prices, WRG temperatures
2. **Data Validation**: Quality checks and preprocessing
3. **Calibration**: Match model to actual network performance
4. **Historical Baseline**: Compare optimization to actual operation

## Required Data

### 1. Heat Demand Time Series

**File**: `data/stadtbach_demand.csv` (create this file)

**Required Columns**:
```csv
timestamp,waermebedarf_MWth
2023-01-01 00:00,45.2
2023-01-01 01:00,42.8
2023-01-01 02:00,40.5
...
```

**Details**:
- Hourly resolution (or finer: 15-min, 30-min)
- Total network heat demand in MWth
- At least 1 week for testing, ideally 1 year
- Should match actual metered data from main plants

**Data Sources**:
- SWA Netze monitoring system
- Heat meter data from distribution points
- Aggregated customer demand profiles

### 2. Electricity Prices

**File**: `data/stadtbach_strompreis.csv`

**Required Columns**:
```csv
timestamp,strompreis_EUR_MWh
2023-01-01 00:00,85.3
2023-01-01 01:00,78.2
...
```

**Details**:
- Day-ahead prices from EPEX Spot
- Or bilateral contract prices
- Include grid fees (Netzentgelte) if separate

**Data Sources**:
- EPEX Spot market data
- Energy supplier invoices
- Internal procurement records

### 3. Waste Heat Recovery (WRG) Temperatures

**File**: `data/stadtbach_wrg.csv`

**Required Columns**:
```csv
timestamp,WRG1_T_K,WRG2_T_K,WRG3_T_K,WRG4_T_K,WRG1_Q_cap,WRG2_Q_cap,WRG3_Q_cap,WRG4_Q_cap
2023-01-01 00:00,288.15,285.0,290.0,287.0,5.0,3.5,4.2,3.8
2023-01-01 01:00,287.5,284.8,289.5,286.5,5.0,3.5,4.2,3.8
...
```

**Details**:
- Temperatures in Kelvin (T_K)
- Available capacity in MW (Q_cap)
- One column pair per WRG source
- If not metered: Use typical industrial waste heat profiles

**Data Sources**:
- Industrial partner measurements
- Process monitoring systems
- If unavailable: Use conservative estimates (280-290 K, Q_cap from contracts)

### 4. Outdoor Temperature (Optional but Recommended)

**File**: `data/stadtbach_weather.csv`

**Required Columns**:
```csv
timestamp,T_outdoor,T_ground
2023-01-01 00:00,5.2,10.0
2023-01-01 01:00,4.8,10.0
...
```

**Details**:
- T_outdoor: Ambient air temperature [°C]
- T_ground: Soil temperature [°C] (defaults to 10°C if not available)
- Used for heat loss calculations in pipes

**Data Sources**:
- Local weather station (DWD)
- On-site sensors
- If unavailable: Use standard weather data for region

### 5. Grid CO2 Intensity

**File**: `data/stadtbach_grid_co2.csv`

**Required Columns**:
```csv
timestamp,grid_co2_kg_MWh
2023-01-01 00:00,420.0
2023-01-01 01:00,410.0
...
```

**Details**:
- German grid mix CO2 intensity [kg CO2/MWh]
- Varies by time of day (more renewables during day)

**Data Sources**:
- Agora Energiewende API
- Electricity Maps
- Default: Use 2023 German average (~400 kg/MWh)

## Data Preparation Workflow

### Step 1: Collect Raw Data

Create a `data/stadtbach_raw/` directory with:
```
data/stadtbach_raw/
├── demand_2023.csv          # From SCADA/metering
├── prices_epex_2023.csv     # From EPEX or supplier
├── wrg_temperatures.csv     # From industrial partners
├── weather_dwd_2023.csv     # From DWD station
└── grid_co2_2023.csv        # From Agora/Electricity Maps
```

### Step 2: Preprocess and Validate

Create preprocessing script: `scripts/prepare_stadtbach_data.py`

```python
#!/usr/bin/env python3
"""
Prepare Stadtbach real data for optimization.
Combines raw data sources into single input Excel/CSV.
"""
import pandas as pd
from pathlib import Path

# Configuration
RAW_DIR = Path('data/stadtbach_raw')
OUTPUT_FILE = 'data/stadtbach_input_2023.xlsx'

# Time range for optimization
START_DATE = '2023-01-01'
END_DATE = '2023-12-31'  # Full year

def load_and_resample(file_path, timestamp_col='timestamp', freq='H'):
    """Load CSV and resample to hourly."""
    df = pd.read_csv(file_path, parse_dates=[timestamp_col])
    df = df.set_index(timestamp_col)
    return df.resample(freq).mean()  # Average for upsampling, mean for downsampling

def main():
    print("Loading raw data...")

    # 1. Load heat demand
    demand = load_and_resample(RAW_DIR / 'demand_2023.csv')
    demand = demand.rename(columns={'demand_mw': 'waermebedarf_MWth'})

    # 2. Load electricity prices
    prices = load_and_resample(RAW_DIR / 'prices_epex_2023.csv')
    prices = prices.rename(columns={'price': 'strompreis_EUR_MWh'})

    # 3. Load WRG data
    wrg = load_and_resample(RAW_DIR / 'wrg_temperatures.csv')
    # Convert Celsius to Kelvin if needed
    for col in ['WRG1_T_K', 'WRG2_T_K', 'WRG3_T_K', 'WRG4_T_K']:
        if col.replace('_K', '_C') in wrg.columns:
            wrg[col] = wrg[col.replace('_K', '_C')] + 273.15

    # 4. Load weather
    weather = load_and_resample(RAW_DIR / 'weather_dwd_2023.csv')
    weather = weather.rename(columns={'temp': 'T_outdoor'})
    if 'T_ground' not in weather.columns:
        weather['T_ground'] = 10.0  # Default

    # 5. Load grid CO2
    co2 = load_and_resample(RAW_DIR / 'grid_co2_2023.csv')
    co2 = co2.rename(columns={'co2_intensity': 'grid_co2_kg_MWh'})

    # Merge all data
    print("Merging datasets...")
    combined = demand.join(prices, how='outer')
    combined = combined.join(wrg, how='outer')
    combined = combined.join(weather, how='outer')
    combined = combined.join(co2, how='outer')

    # Filter to date range
    combined = combined.loc[START_DATE:END_DATE]

    # Quality checks
    print("\nData Quality Checks:")
    print(f"  Total timesteps: {len(combined)}")
    print(f"  Date range: {combined.index.min()} to {combined.index.max()}")
    print(f"\nMissing values:")
    print(combined.isnull().sum())

    # Fill missing values (forward fill for continuity)
    combined = combined.fillna(method='ffill').fillna(method='bfill')

    # Validate ranges
    assert combined['waermebedarf_MWth'].min() >= 0, "Negative demand detected"
    assert combined['strompreis_EUR_MWh'].min() >= 0, "Negative prices detected"
    assert combined['T_outdoor'].between(-30, 50).all(), "Unrealistic outdoor temp"

    print("\n✓ All quality checks passed")

    # Export
    print(f"\nExporting to {OUTPUT_FILE}...")
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        combined.to_excel(writer, sheet_name='timeseries', index=True)

        # Add metadata sheet
        metadata = pd.DataFrame({
            'Parameter': ['Start Date', 'End Date', 'Timesteps', 'Resolution', 'Source'],
            'Value': [
                str(combined.index.min()),
                str(combined.index.max()),
                len(combined),
                '1 hour',
                'Stadtbach 2023 Real Data'
            ]
        })
        metadata.to_excel(writer, sheet_name='metadata', index=False)

    print(f"✓ Data exported successfully: {len(combined)} timesteps")
    print(f"\nColumns: {list(combined.columns)}")

if __name__ == '__main__':
    main()
```

**Run**:
```bash
python scripts/prepare_stadtbach_data.py
```

**Output**: `data/stadtbach_input_2023.xlsx` ready for optimization

### Step 3: Update Scenario Configuration

Edit `configs/scenarios/stadtbach_1week.scenario.yaml`:

```yaml
scenario:
  run_mode: PF_ONLY
  title: "Stadtbach_Real_2023_1Week"
  tag: "stadtbach-real-2023-jan-week1"

  # Test with first week of January 2023
  horizon:
    type: "date_range"
    start: "2023-01-01 00:00"
    end: "2023-01-08 00:00"

# Point to real data file
data_file: stadtbach_input_2023.xlsx

# ... rest of config ...
```

## Running Optimizations

### Test Run (1 Week)

```bash
# Windows (PowerShell)
python -m energis.run `
  configs/base.yaml `
  configs/tech_catalog.yaml `
  configs/scenarios/stadtbach_1week.scenario.yaml

# Linux/Mac
python -m energis.run \
  configs/base.yaml \
  configs/tech_catalog.yaml \
  configs/scenarios/stadtbach_1week.scenario.yaml
```

**Expected Output**:
```
Running EnerGIS with 3 config files:
  - configs/base.yaml
  - configs/tech_catalog.yaml
  - configs/scenarios/stadtbach_1week.scenario.yaml

Loading data from: data/stadtbach_input_2023.xlsx
Building model...
  Heat pumps: 4 (HP1, HP2, HP3, HP4)
  Storage: 1 (100-10000 MWh)
  Generators: 7
  Thermal network: 12 nodes, 11 pipes

Solving with Gurobi...
  Solve time: 2.3s
  MIP Gap: 0.5%
  Objective: 125,432 EUR

Extracting results...
  Total heat delivered: 840.2 MWh
  Network heat losses: 5.8 MWh (0.69%)
  Grid import: 245.1 MWh
  Total cost: 125,432 EUR

✓ Success! Results exported to: exports/20251210_153045_stadtbach-real-2023-jan-week1/
```

**Check Outputs**:
```bash
ls exports/20251210_153045_stadtbach-real-2023-jan-week1/

# Should contain:
  pf_timeseries.csv               # All decision variables
  pf_network_timeseries.csv       # Network temperatures, flows, losses
  pf_network_summary.csv          # Network KPIs
  design.json                     # Heat pump and storage capacities
  manifest.json                   # Run metadata
```

### Full Year Run (Rolling Horizon)

For annual optimization, use rolling horizon to manage computational load:

**Create**: `configs/scenarios/stadtbach_2023_full_year.scenario.yaml`

```yaml
scenario:
  run_mode: RH_ONLY
  workflow:
    - RH
  title: "Stadtbach_Real_2023_Full_Year"
  tag: "stadtbach-2023-rh-annual"

  # Full year
  horizon:
    type: "date_range"
    start: "2023-01-01 00:00"
    end: "2023-12-31 23:00"

  # Rolling horizon settings
  rolling_horizon:
    heat_horizon_hours: 168.0   # 1 week lookahead
    step_hours: 24.0            # 1 day step
    terminal_policy: geq

system_file: stadtbach.system.yaml

thermal_network:
  enabled: true
  topology_file: stadtbach_network.yaml
  use_outdoor_temperature: true  # Use real weather data

run:
  dt_h: 1.0
  solver: gurobi
  solver_options:
    Threads: 32              # Use all cores
    ConcurrentMIP: 4         # 4 parallel strategies
    MIPGap: 0.02             # 2% gap (faster)
    TimeLimit: 600           # 10 min per window
    Method: 2                # Barrier
    NumericFocus: 1
```

**Run**:
```bash
python -m energis.run configs/base.yaml configs/tech_catalog.yaml configs/scenarios/stadtbach_2023_full_year.scenario.yaml
```

**Expected Runtime**:
- 365 days / 1 day step = 365 windows
- ~30s per window = ~3 hours total
- With 32 threads and optimized solver settings

## Validation and Calibration

### 1. Compare to Historical Baseline

Load actual operational data:
```python
import pandas as pd

# Load optimization results
opt_results = pd.read_csv('exports/.../rh_timeseries.csv', index_col=0, parse_dates=True)

# Load actual operation from SCADA
actual = pd.read_csv('data/stadtbach_actual_2023.csv', index_col=0, parse_dates=True)

# Compare key metrics
comparison = pd.DataFrame({
    'Actual Grid Import [MWh]': actual['grid_import_mwh'].sum(),
    'Optimized Grid Import [MWh]': opt_results['P_buy_MW'].sum(),
    'Savings [MWh]': actual['grid_import_mwh'].sum() - opt_results['P_buy_MW'].sum(),
    'Actual Cost [EUR]': actual['total_cost_eur'].sum(),
    'Optimized Cost [EUR]': opt_results['Total_cost_EUR'].sum(),
    'Savings [EUR]': actual['total_cost_eur'].sum() - opt_results['Total_cost_EUR'].sum(),
    'Savings [%]': (1 - opt_results['Total_cost_EUR'].sum() / actual['total_cost_eur'].sum()) * 100
}, index=[0])

print(comparison)
```

**Expected Savings**:
- Grid electricity: 10-25% reduction
- Total cost: 15-30% reduction
- CO2 emissions: 20-35% reduction (with WRG optimization)

### 2. Validate Network Heat Losses

```python
# Load network results
network = pd.read_csv('exports/.../pf_network_summary.csv', index_col=0, squeeze=True).to_dict()

print(f"Modeled heat loss: {network['Total_heat_loss_MWh']:.1f} MWh ({network['Heat_loss_percentage']:.2f}%)")

# Compare to typical DH network losses (0.5-1.5% for well-insulated networks)
if 0.5 <= network['Heat_loss_percentage'] <= 1.5:
    print("✓ Heat losses within expected range for modern DH network")
else:
    print("⚠ Heat losses outside typical range - check pipe insulation assumptions")
```

### 3. Temperature Validation

Check if supply/return temperatures match operational constraints:

```python
network_ts = pd.read_csv('exports/.../pf_network_timeseries.csv', index_col=0, parse_dates=True)

# Check plant supply temperature
for node in ['plant_ost', 'plant_west_hww', 'plant_sued_hws']:
    T_supply = network_ts[f'NET_{node}_T_supply_C']
    print(f"{node}: T_supply = {T_supply.mean():.1f}°C (min: {T_supply.min():.1f}, max: {T_supply.max():.1f})")

    # Should be close to 100°C nominal
    assert 90 <= T_supply.mean() <= 105, f"{node} supply temp out of range!"

print("✓ All temperatures within operational constraints")
```

## Troubleshooting

### Issue 1: Solver Timeout

**Symptom**: Gurobi hits time limit, suboptimal solution

**Solutions**:
1. Increase `TimeLimit` in solver options (e.g., 1800s = 30 min)
2. Relax `MIPGap` to 5% for faster convergence
3. Use rolling horizon with shorter windows (24-48h instead of 168h)
4. Reduce `dt_h` resolution (use 2h or 4h timesteps)

### Issue 2: Infeasible Model

**Symptom**: "Model is infeasible"

**Check**:
1. Heat pump capacity < peak demand?
   - Increase `max_th_mw` or enable investment
2. Storage capacity too small?
   - Increase `max_energy_mwh`
3. WRG temperatures too low?
   - Check COP calculations, ensure T_source > 278 K
4. Grid import limit too restrictive?
   - Increase `max_import_mw` in grid config

### Issue 3: Unrealistic Results

**Symptom**: Network losses 10%, temperatures 150°C, etc.

**Check**:
1. Pipe U-values in `stadtbach_network.yaml` - should be 0.15-0.30 W/(m·K)
2. Ground temperature - default 10°C reasonable for Germany
3. Mass flow limits - check pipe diameter constraints
4. Temperature bounds - supply 70-120°C, return 40-70°C

## Next Steps

### Week 1: Data Collection
- [ ] Contact SWA Netze for demand and SCADA data
- [ ] Download EPEX prices for 2023
- [ ] Request WRG temperatures from industrial partners
- [ ] Download DWD weather data for Stadtbach region

### Week 2: Data Preparation
- [ ] Run `prepare_stadtbach_data.py` script
- [ ] Validate data quality (no missing values, realistic ranges)
- [ ] Create test scenario with 1 week of data
- [ ] Compare test results to expectations

### Week 3: Calibration
- [ ] Run full year optimization
- [ ] Compare to actual 2023 operation
- [ ] Adjust model parameters if needed (pipe U-values, COP curves)
- [ ] Document calibration results

### Week 4: Scenario Analysis
- [ ] Run sensitivity analyses (what-if scenarios)
- [ ] Test different WRG availability profiles
- [ ] Evaluate pipe upgrade investments (insulation, diameter)
- [ ] Generate reports and recommendations

## References

- **Network Configuration**: `configs/networks/stadtbach_network.yaml`
- **System Configuration**: `configs/systems/stadtbach.system.yaml`
- **Scenario Template**: `configs/scenarios/stadtbach_1week.scenario.yaml`
- **Data Preparation Script**: `scripts/prepare_stadtbach_data.py` (to be created)
- **Test Script**: `scripts/test_thermal_network.py`
- **Performance Guide**: `docs/PERFORMANCE_OPTIMIZATION_THERMAL_NETWORKS.md`

---

**Status**: ✅ Configuration ready, waiting for real data
**Estimated Effort**: 2-4 weeks (depends on data availability)
**Expected Savings**: 15-30% cost reduction vs baseline operation
