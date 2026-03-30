# CALION: Integrated Optimization for Electrified Industrial Heating

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python framework for the joint investment planning and operational optimization of electrified industrial heating systems, based on Mixed-Integer Linear Programming (MILP).

## Overview

CALION co-optimizes investment decisions and operational dispatch for industrial heat networks undergoing electrification — replacing fossil-fuel-based supply with heat pumps, power-to-heat, and sector-coupled technologies:

- **Joint investment and operation**: Simultaneous capacity sizing and hourly dispatch in a single MILP — no sequential approximation
- **Electrification focus**: Heat pumps with temperature-dependent COP, power-to-heat, and flexible electricity market coupling
- **Multi-stage optimization**: Perfect Foresight (PF) for design optimization and Rolling Horizon (RH) for operational simulation
- **Physical network modeling**: Industrial heat networks with physical heat loss calculation (Q = U × L × ΔT)
- **Comprehensive component library**: Heat pumps, CHP units, stratified thermal storage, P2H, biomass boilers
- **Multi-energy carrier support**: Explicit buses for electricity, gas, biomass, and waste heat with CO₂ tracking

## Installation

```bash
# Clone the repository
git clone https://github.com/LukasRuess98/Planing-Framework-for-Heat.git
cd Planing-Framework-for-Heat

# Install in editable mode (includes core dependencies)
pip install -e .

# Install with all optional dependencies (solver, plots, notebooks, dev tools)
pip install -e ".[all]"

# Optional: Install Gurobi solver (recommended for large problems)
# Framework falls back to GLPK if Gurobi is unavailable
```

### Requirements

- Python 3.10+
- Pyomo (optimization modeling)
- mathematical solver (Gurobi, Highs, CBC)
- pandas, numpy, pyyaml, openpyxl

## Quick Start

### Command Line

```bash
# Run optimization with a scenario config
python -m calion.run configs/scenarios/stadtbach_baseline_2023.yaml

# Results are written to outputs/runs/
```

### Jupyter Notebook

```bash
jupyter notebook notebooks/calion.ipynb
```

The notebook provides interactive access to:
- Running optimization scenarios
- Visualizing results (heat balance, costs, emissions)
- Analyzing thermal network performance

## Configuration

CALION uses YAML configuration files layered on top of `configs/base.yaml`.
See `configs/scenarios/stadtbach_baseline_2023.yaml` for a complete example:

```yaml
scenario:
  title: "District Heating Optimization"
  workflow: [PF]
  time:
    start: "2023-01-01 00:00"
    end: "2023-12-31 23:00"
    freq: "1h"

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
  topology_file: configs/05_networks/brownfield.yaml

costs:
  co2_price_eur_per_t: 100.0
```

## Project Structure

```
calion/              # Python package
  models/             # Pyomo model components
  run/                # Optimization orchestration
  io/                 # Input/output utilities
  config/             # Configuration handling
  analysis/           # Sensitivity and post-processing
  comparison/         # Benchmarking tools

configs/              # YAML configuration files
  base.yaml           # Shared defaults
  scenarios/          # Ready-to-run scenarios
  templates/          # Minimal templates (level1–3)
  assets/             # Asset/technology definitions
  05_networks/        # Thermal network topologies

data/                 # Input time-series (CSV)
outputs/              # Runtime results (gitignored)
  runs/               # Per-run CSVs, plots, solver files
  workflows/          # Saved notebook workflows
scripts/              # Utilities (migrate_outputs, start_dashboard)
notebooks/            # Jupyter notebooks
tests/                # Test suite
docs/                 # Documentation
archive/              # Development artifacts (not active code)
```

## Documentation

- [Technical Methodology](docs/METHODOLOGY.md) - Detailed model formulation
- [User Guide](docs/USER_GUIDE.md) - Configuration and usage instructions
- [Data Format](docs/DATA_FORMAT.md) - Input data requirements

## Testing

```bash
# Run all unit tests
pytest tests/ -v

# Run without coverage (faster)
pytest tests/ -v --no-cov
```

## Citation

If you use CALION in your research, please cite:

```bibtex
@software{ruess2026calion,
  author       = {Ruess, Lukas},
  title        = {{CALION: Integrated Optimization for Electrified Industrial Heating}},
  year         = {2026},
  version      = {1.0.0-alpha},
  institution  = {Institut für Energieeffizienz in der Produktion (EEP), Universität Stuttgart},
  url          = {https://github.com/LukasRuess98/Planing-Framework-for-Heat}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
