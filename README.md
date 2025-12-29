# EnerGIS: Modular District Heating Optimization Framework

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modular Mixed-Integer Linear Programming (MILP) framework for optimal planning and operation of district heating systems with thermal network integration.

## Overview

EnerGIS provides a transparent, modular approach to district heating optimization, addressing key challenges in the decarbonization of heating networks:

- **Multi-stage optimization**: Perfect Foresight (PF) for design optimization and Rolling Horizon (RH) for operational simulation
- **Physical network modeling**: Brownfield networks with physical heat loss calculation (Q = U x L x dT)
- **Investment optimization**: Capacity sizing for heat pumps, thermal storage, and generators
- **Comprehensive component library**: Heat pumps with COP modeling, CHP units, stratified storage, P2H, biomass boilers
- **Multi-fuel support**: Explicit fuel buses (electricity, gas, biomass, waste) with CO2 tracking

## Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/energis.git
cd energis

# Install dependencies
pip install -r requirements.txt

# Optional: Install Gurobi solver (recommended for large problems)
# Framework falls back to GLPK if Gurobi is unavailable
```

### Requirements

- Python 3.9+
- Pyomo (optimization modeling)
- Gurobi or GLPK solver
- pandas, numpy, pyyaml, openpyxl

## Quick Start

### Command Line

```bash
# Run optimization with configuration file
python -m energis.run configs/stadtbach.yaml

# Results are exported to exports/
```

### Jupyter Notebook

```bash
jupyter notebook notebooks/energis.ipynb
```

The notebook provides interactive access to:
- Running optimization scenarios
- Visualizing results (heat balance, costs, emissions)
- Analyzing thermal network performance

## Configuration

EnerGIS uses YAML configuration files. See `configs/stadtbach.yaml` for a complete example:

```yaml
scenario:
  title: "District Heating Optimization"
  workflow: [PF]
  horizon:
    start: "2023-01-01 00:00"
    end: "2023-12-31 23:00"

system:
  heat_pumps:
    - id: HP1
      capacity_mw: 50.0
      investment:
        enabled: true
        min_mw: 5.0
        max_mw: 100.0
        capex_eur_per_mw: 400000

thermal_network:
  enabled: true
  topology_file: configs/networks/brownfield.yaml

costs:
  co2_price_eur_per_t: 100.0
```

## Project Structure

```
energis/              # Python module
  models/             # Pyomo model components
  run/                # Optimization orchestration
  io/                 # Input/output utilities
  config/             # Configuration handling

configs/              # Configuration files
notebooks/            # Jupyter notebooks
tests/                # Test suite
docs/                 # Documentation
```

## Documentation

- [Technical Methodology](docs/METHODOLOGY.md) - Detailed model formulation
- [User Guide](docs/USER_GUIDE.md) - Configuration and usage instructions
- [Data Format](docs/DATA_FORMAT.md) - Input data requirements

## Testing

```bash
# Run comprehensive system test
python tests/test_full_system.py

# Run all unit tests
pytest tests/ -v
```

## Citation

If you use EnerGIS in your research, please cite:

```bibtex
@article{energis2024,
  title={EnerGIS: A Modular MILP Framework for District Heating System Optimization},
  author={[Authors]},
  journal={Applied Energy},
  year={2024}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
