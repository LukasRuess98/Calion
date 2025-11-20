# EnerGIS Framework - Quick Reference Guide

## Core Concepts at a Glance

### 1. The Three-Layer Architecture

```
CONFIGURATION LAYER      YAML files define system topology & scenarios
         ↓
MODEL BUILDING LAYER     system_builder.py creates Pyomo MILP
         ↓
RUNNER/EXPORT LAYER      orchestrator.py solves & exports results
```

### 2. Network Model (Buses & Flows)

**Buses** = Connection points where flows meet
- ELECTRICITY, HEAT, FUEL_GAS, FUEL_BIOMASS, FUEL_WASTE, etc.
- Balance constraint per bus per timestep: `Σ(inputs) * (1-loss) = Σ(outputs)`

**Components** = Converters/storage that connect to buses
- HeatPump: electricity → heat (with COP series)
- Storage: heat ↔ heat (with charge/discharge efficiency)
- ThermalGen: fuel → heat (+ optional electricity)
- P2H: electricity → heat (direct)

### 3. Key Files

| What | Where | Purpose |
|------|-------|---------|
| Network abstractions | `energis/models/bus.py`, `component.py` | Bus & Flow definitions |
| Component implementations | `energis/models/blocks/*.py` | Heat pumps, storage, generators |
| Model builder | `energis/models/system_builder.py` | Pyomo model construction |
| Main runner | `energis/run/orchestrator.py` | Workflow orchestration |
| Data loading | `energis/io/loader.py` | Excel input |
| Data export | `energis/io/exporter.py`, `publication_exporter.py` | CSV/Excel/JSON output |

## Common Tasks

### 1. Run Optimization
```python
from energis.run.orchestrator import run_all

results = run_all([
    "configs/base.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/perfect_forecast_full_year.scenario.yaml"
])

print(results['outdir'])              # Export location
print(results['summary']['objective']) # Cost breakdown
```

### 2. Access Results
```python
# Time series (MW, MWh, EUR, etc.)
P_buy = results['series']['P_buy_MW']          # [0, 1, 2, ...] timesteps
Q_th = results['series']['HP1_Q_th_MW']        # Heat pump output
TES_soc = results['series']['TES_SOC_MWh']     # Storage state

# Summaries
heat_pump_results = results['summary']['heat_pump_HP1']
total_cost = results['summary']['objective']['OBJ_value_EUR']
storage_capacity = results['summary']['storage_TES']['Capacity_MWh']

# Costs
capex = results['costs']['objective.Capex_cost_EUR']
opex = results['costs']['objective.Grid_energy_cost_EUR']
```

### 3. Modify Configuration
```python
# Via YAML file (preferred)
# Edit configs/systems/baseline.system.yaml, then rerun

# Via runtime override
overrides = {
    "costs": {"co2_price_eur_per_t": 150},
    "system": {
        "heat_pumps": [{
            "id": "HP1",
            "max_th_mw": 50.0
        }]
    }
}
results = run_all(config_paths, overrides)
```

### 4. Add New Component Type
```python
# 1. Create class in energis/models/blocks/my_component.py
from energis.models.component import BaseComponent, Flow
from energis.models.registry import register_component

@register_component("my_type", category="converter")
class MyBlock(BaseComponent):
    def attach(self, model, time_set, config, buses):
        # Create Pyomo variables & constraints
        # Return {'flows': {...}, 'investment': {...}, 'state': {...}}
        return results
    
    def get_results(self, model, time_set):
        # Extract and return results
        return results
    
    def validate_config(self, config):
        # Validate configuration
        pass

# 2. Import in energis/models/__init__.py
from .blocks.my_component import MyBlock

# 3. Use in config
# system:
#   my_components:
#     - id: MC1
#       enabled: true
```

## Configuration Structure

```yaml
# Base configuration (base.yaml)
heat_pumps:
  cop:
    tables:
      default:
        x: [263.15, 268.15, ...]  # Source temp (K)
        y: [343.15, 353.15, ...]  # Sink temp (K)
        values: [[2.5, 2.8, ...], [3.0, 3.2, ...]]

costs:
  co2_price_eur_per_t: 100
  dump_cost_eur_per_mwh_th: 1000

grid:
  demand_charge_eur_per_mw_y: 50000
  max_import_mw: 100

# System configuration (systems/baseline.system.yaml)
system:
  heat_pumps:
    - id: HP1
      type: standard
      max_th_mw: 40.0
      investment:
        enabled: true
        capacity_max_mw: 100.0

  storage:
    enabled: true
    max_energy_mwh: 100.0
    max_power_mw: 30.0
    eff_charge: 0.98
    loss_hour: 0.0005

  generators:
    hkw:
      enabled: true
      cap_th_mw: 75.0
    p2h:
      enabled: true
      cap_th_mw: 10.0
```

## Model Output Structure

```
exports/{timestamp}_{scenario}/
├── scenario_timeseries.csv          # All time series (input + output)
├── costs.json                       # Cost breakdown
├── summary.json                     # Component summaries & KPIs
├── metadata.json                    # Run info & solver details
├── merged_config.json               # Final configuration
├── scenario_data.xlsx               # Excel bundle
├── manifest.json                    # Export manifest
├── plots/                           # Plots (demand vs supply, costs, etc.)
├── publication_plots/               # Publication-quality plots (300 dpi)
├── publication_latex/               # LaTeX tables for papers
└── applied_energies/                # Journal-specific outputs
```

## Key Variables in Model

### Grid Interface
- `P_buy[t]` - Grid electricity import (MW)
- `P_sell[t]` - Grid electricity export (MW)
- `Q_dump[t]` - Heat dump (MW_th)
- `P_buy_peak` - Peak import (for demand charges)

### Heat Pump (HP1)
- `HP1_Q[t]` - Heat output (MW_th)
- `HP1_Pel[t]` - Electricity input (MW_e) [Expression]
- `HP1_Q_wrg[t]` - Waste heat recovery portion
- `HP1_on[t]` - On/off binary
- `HP1_cap_mw` - Capacity (MW) [Investment variable]
- `HP1_build` - Build binary [Investment variable]

### Storage (TES)
- `TES_E[t]` - State of charge (MWh)
- `TES_Qc[t]` - Charge flow (MW_th)
- `TES_Qd[t]` - Discharge flow (MW_th)
- `TES_cap_energy` - Energy capacity (MWh) [Investment]
- `TES_cap_power` - Power capacity (MW) [Investment]

### Generators
- `{GEN}_Qth[t]` - Thermal output
- `{GEN}_fuel[t]` - Fuel input
- `{GEN}_Pel[t]` - Electrical output (if equipped)

## Energy Balances

### Electricity Bus
```
P_buy[t] + Σ(Gen_Pel) = HP_Pel[t] + P2H_Pel[t] + P_sell[t]
```

### Heat Bus
```
HP_Q[t] + Gen_Qth[t] + P2H_Qth[t] + TES_Qd[t] = 
    Demand[t] + TES_Qc[t] + Q_dump[t]
```

### Storage Energy
```
E[t] = E[t-1] * (1 - loss[t]) - Qd[t]/eff_d + Qc[t]*eff_c
```

## Tips & Tricks

1. **Disable investment**: Set `capacity_max_mw = capacity_init_mw` to fix capacity
2. **Time-varying losses**: Add `storage_loss_hour` column to input Excel
3. **Waste heat recovery**: Add `WRG1_T_K` and `WRG1_Q_cap` columns to input
4. **Demand response**: Modify `waermebedarf_MWth` column in input data
5. **Publication plots**: Set `enable_publication_exports: true` in config
6. **Debug model**: Check `exports/*/model_structure/` for model variables/constraints

## Performance Tuning

1. Reduce time periods: Use hourly data instead of 15-min
2. Fix non-investable capacities: Reduces binary variables
3. Use warm start: Provide initial solutions from previous run
4. Solver settings: Modify Gurobi parameters in code
5. Model export: Use `export_model_structure: true` for debugging

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Pyomo not available" | Install: `pip install pyomo` |
| Solver not found | Install Gurobi/GLPK: `apt-get install glpk` or Gurobi license |
| No solution found | Check capacity vs demand; reduce time horizon; relax constraints |
| Memory error | Reduce time periods; use rolling horizon mode |
| Infeasible model | Check bus balances; increase capacity/flexibility bounds |

## References

- Full documentation: `/home/user/Planing-Framework-for-Heat/FRAMEWORK_ARCHITECTURE_ANALYSIS.md`
- Examples: `/home/user/Planing-Framework-for-Heat/examples/`
- Tests: `/home/user/Planing-Framework-for-Heat/tests/`
- Documentation: `/home/user/Planing-Framework-for-Heat/docs/`

