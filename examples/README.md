# Examples

This directory contains example scripts demonstrating EnerGIS capabilities.

## Available Examples

### 1. standalone_heat_planning_example.py

A complete, standalone heat planning system in a single Python script. Demonstrates:

- Environment variable-based configuration
- Excel data loading with robust time series processing
- COP lookup tables for heat pumps with bilinear interpolation
- Perfect Foresight (PF) design optimization
- Rolling Horizon (RH) operational optimization
- Multi-component system (8+ generators)

**Quick Start:**
```bash
python examples/standalone_heat_planning_example.py
```

**With Configuration:**
```bash
RUN_MODE=PF_THEN_RH \
SCENARIO_TITLE=my_scenario \
SOLVER_NAME=gurobi \
CO2_PRICE_EUR_PER_T=150 \
python examples/standalone_heat_planning_example.py
```

### 2. stratified_storage_example.py

Demonstrates the stratified thermal storage model with two-zone temperature modeling for large storage systems (100-50,000 MWh).

### 3. custom_component_example.py

Shows how to create and register custom components that integrate with the EnerGIS framework.

## Configuration via Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RUN_MODE` | `PF_ONLY`, `RH_ONLY`, or `PF_THEN_RH` | `PF_ONLY` |
| `SOLVER_NAME` | `gurobi`, `glpk`, or `cbc` | `cbc` |
| `SCENARIO_TITLE` | Scenario name for exports | `HP_v3_CO2_100` |
| `YEAR_TARGET` | Target year for data filtering | `2023` |
| `CO2_PRICE_EUR_PER_T` | CO₂ price per ton | `100.0` |
| `GASPREIS_EUR_PER_MWh_th` | Gas price | `58.6` |
| `HEAT_HORIZON_HOURS` | RH optimization window | `168` |
| `STEP_HOURS` | RH commit period | `24` |

See [standalone_heat_planning_example.py](standalone_heat_planning_example.py) source for all available options.

## Running Examples

1. **Ensure dependencies are installed:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure a solver is available:**
   ```bash
   # Install CBC (open source)
   conda install -c conda-forge coincbc

   # Or use GLPK
   sudo apt-get install glpk-utils  # Linux
   brew install glpk                 # macOS
   ```

3. **Ensure input data exists:**
   - Default: `Import_Data.xlsx` in repository root
   - Override: `INPUT_XLSX=/path/to/data.xlsx python example.py`

## Output

Results are exported to the `exports/` directory:

```
exports/
├── {SCENARIO_TITLE}_PF.xlsx    # Perfect Foresight results
├── {SCENARIO_TITLE}_RH.xlsx    # Rolling Horizon results
└── pf_design.json              # Optimized capacities
```
