# EnerGIS - District Heating Optimization Framework

A modular MILP-based optimization framework for district heating systems with thermal network integration.

## Features

- **Multi-stage optimization**: Perfect Foresight (PF) and Rolling Horizon (RH) modes
- **Thermal network modeling**: Brownfield and greenfield network optimization
- **Component library**: Heat pumps, CHP, storage, power-to-heat, biomass
- **Investment optimization**: Capacity sizing for heat pumps and storage
- **CO2 and cost tracking**: Detailed emissions and cost breakdown

## Installation

```bash
pip install -r requirements.txt

# Optional: Install Gurobi solver (recommended for large problems)
# Falls back to GLPK if Gurobi unavailable
```

## Quick Start

```bash
# Run optimization with default configuration
python -m energis.run configs/base.yaml configs/tech_catalog.yaml configs/system.yaml configs/scenario.yaml

# Start interactive dashboard
python start_dashboard.py
```

## Configuration Structure

```
configs/
├── base.yaml           # Global defaults (solver, grid, costs)
├── tech_catalog.yaml   # Technology parameters (efficiencies, fuel prices)
├── system.yaml         # System components (generators, heat pumps, storage)
├── network.yaml        # Thermal network topology (nodes, pipes)
└── scenario.yaml       # Scenario settings (horizon, run mode, data source)
```

### Configuration Files

| File | Purpose |
|------|---------|
| `base.yaml` | Solver settings, grid parameters, cost defaults |
| `tech_catalog.yaml` | Generator efficiencies, fuel prices, investment costs |
| `system.yaml` | Heat pumps, storage, thermal generators |
| `network.yaml` | Network topology (plants, consumers, pipes) |
| `scenario.yaml` | Time horizon, run mode, data file, network settings |

## Usage Examples

### Run Full Year Optimization

```yaml
# In scenario.yaml
scenario:
  run_mode: PF_ONLY
  horizon:
    start: "2023-01-01 00:00"
    end: "2023-12-31 23:00"
```

### Enable Thermal Network

```yaml
# In scenario.yaml
thermal_network:
  enabled: true
  topology_file: configs/network.yaml
  brownfield_mode: true
```

## Project Structure

```
energis/
├── models/           # Pyomo model builders
│   ├── system_builder.py
│   ├── network_manager.py
│   └── blocks/       # Component blocks (HP, storage, generators)
├── run/              # Optimization orchestration
│   └── rolling_horizon.py
├── io/               # Input/output handling
│   └── dashboard.py
└── utils/            # Helper functions

notebooks/            # Jupyter notebooks for analysis
data/                 # Input data files
```

## Dashboard

Launch the interactive dashboard to visualize results:

```bash
python start_dashboard.py
```

The dashboard provides:
- Heat balance visualization
- Cost breakdown analysis
- Network hydraulics overview
- CO2 emissions tracking

## Requirements

- Python 3.9+
- Pyomo
- Gurobi or GLPK solver
- pandas, numpy, pyyaml

## License

[Add license information]

## Citation

[Add citation information for Applied Energy publication]
