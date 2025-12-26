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
# Run optimization (single config file)
python -m energis.run configs/stadtbach.yaml

# Start interactive dashboard
python start_dashboard.py
```

## Configuration

All settings are in a single YAML file (`configs/stadtbach.yaml`):

```yaml
# Key settings to adjust:

scenario:
  horizon:
    start: "2023-01-01 00:00"
    end: "2023-01-07 23:00"    # Change for longer runs

thermal_network:
  enabled: true                 # Enable/disable network
  brownfield_mode: true         # Fixed topology

costs:
  co2_price_eur_per_t: 100.0   # CO2 price
```

### Configuration Structure

```
configs/
├── stadtbach.yaml         # Complete configuration (recommended)
│
├── networks/              # Network topologies (optional, for variants)
│   └── brownfield.yaml
│
├── systems/               # System variants (optional)
│   ├── baseline.yaml
│   └── high_hp.yaml
│
└── scenarios/             # Scenario variants (optional)
    ├── full_year.yaml
    └── one_week.yaml
```

### Advanced: Multiple Config Files

For scenario comparisons, you can split configs and merge them:

```bash
# Override specific settings
python -m energis.run configs/stadtbach.yaml configs/my_overrides.yaml
```

## Project Structure

```
energis/
├── models/           # Pyomo model builders
│   ├── system_builder.py
│   ├── network_manager.py
│   └── blocks/       # Component blocks
├── run/              # Optimization orchestration
│   └── rolling_horizon.py
├── io/               # Input/output handling
│   └── dashboard.py
└── utils/            # Helper functions

configs/              # Configuration files
notebooks/            # Jupyter notebooks
data/                 # Input data files
```

## Dashboard

Launch the interactive dashboard to visualize results:

```bash
python start_dashboard.py
```

Features:
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
