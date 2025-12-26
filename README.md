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
# Run baseline full year optimization
python -m energis.run configs/base.yaml configs/tech_catalog.yaml \
    configs/systems/baseline.yaml configs/scenarios/full_year.yaml

# Run quick one-week test
python -m energis.run configs/base.yaml configs/tech_catalog.yaml \
    configs/systems/baseline.yaml configs/scenarios/one_week.yaml

# Start interactive dashboard
python start_dashboard.py
```

## Configuration Structure

```
configs/
├── base.yaml              # Global defaults (solver, grid, costs) - FIXED
├── tech_catalog.yaml      # Technology parameters - FIXED
│
├── networks/              # Network topologies (interchangeable)
│   └── brownfield.yaml    # Existing network infrastructure
│
├── systems/               # System configurations (interchangeable)
│   ├── baseline.yaml      # Standard system with existing capacities
│   └── high_hp.yaml       # High heat pump capacity scenario
│
└── scenarios/             # Scenario definitions (interchangeable)
    ├── full_year.yaml     # Full year optimization
    ├── one_week.yaml      # Quick test (1 week)
    └── high_hp_year.yaml  # Decarbonization scenario
```

### Configuration Philosophy

| Layer | Purpose | Changes |
|-------|---------|---------|
| `base.yaml` | Solver settings, grid parameters | Rarely |
| `tech_catalog.yaml` | Efficiencies, fuel prices, investment costs | Per study |
| `networks/*.yaml` | Network topology (nodes, pipes) | Per network variant |
| `systems/*.yaml` | Component capacities (HP, storage, generators) | Per system variant |
| `scenarios/*.yaml` | Time horizon, run mode, network/system selection | Per run |

### Scenario Combinations

```bash
# Baseline system, full year
python -m energis.run configs/base.yaml configs/tech_catalog.yaml \
    configs/systems/baseline.yaml configs/scenarios/full_year.yaml

# High HP system, full year (decarbonization study)
python -m energis.run configs/base.yaml configs/tech_catalog.yaml \
    configs/systems/high_hp.yaml configs/scenarios/high_hp_year.yaml

# Baseline system, one week test
python -m energis.run configs/base.yaml configs/tech_catalog.yaml \
    configs/systems/baseline.yaml configs/scenarios/one_week.yaml
```

## Usage Examples

### Enable Thermal Network

In your scenario file:
```yaml
thermal_network:
  enabled: true
  topology_file: configs/networks/brownfield.yaml
  brownfield_mode: true
```

### Configure Time Horizon

```yaml
scenario:
  run_mode: PF_ONLY  # or PF_THEN_RH
  horizon:
    start: "2023-01-01 00:00"
    end: "2023-12-31 23:00"
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

configs/              # Configuration files (see above)
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
