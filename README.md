# EnerGIS: Modular District Heating Optimization Framework

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modular Mixed-Integer Linear Programming (MILP) framework for optimal planning and operation of district heating systems with thermal network integration.

## Overview

EnerGIS provides a transparent, modular approach to district heating optimization, addressing key challenges in the decarbonization of heating networks:

- **Multi-stage optimization**: Perfect Foresight (PF) for design optimization and Rolling Horizon (RH) for operational simulation
- **Physical network modeling**: Brownfield networks with physical heat loss calculation (Q = U × L × ΔT)
- **Investment optimization**: Capacity sizing for heat pumps, thermal storage, and generators
- **Comprehensive component library**: Heat pumps with COP modeling, CHP units, stratified storage, P2H, biomass boilers
- **Multi-fuel support**: Explicit fuel buses (electricity, gas, biomass, waste) with CO₂ tracking

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
# Run optimization with single configuration file
python -m energis.run configs/stadtbach.yaml

# Results are exported to exports/stadtbach/
```

### Jupyter Notebook

```bash
jupyter notebook notebooks/energis.ipynb
```

The notebook provides interactive access to:
- Running optimization scenarios
- Visualizing results (heat balance, costs, emissions)
- Analyzing thermal network performance
- Comparing different system configurations

## Configuration

EnerGIS uses a single YAML configuration file that defines all system parameters:

```yaml
# configs/stadtbach.yaml - Example configuration

scenario:
  title: "District Heating Optimization"
  workflow: [PF]  # Perfect Foresight mode
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

  storage:
    enabled: true
    energy_mwh: 500.0
    investment:
      enabled: true
      min_energy_mwh: 100.0
      max_energy_mwh: 5000.0

thermal_network:
  enabled: true
  topology_file: configs/networks/brownfield.yaml

costs:
  co2_price_eur_per_t: 100.0
```

### Configuration Structure

```
configs/
├── stadtbach.yaml           # Complete configuration (recommended)
├── tech_catalog.yaml        # Technology parameters (efficiencies, costs)
├── networks/
│   └── brownfield.yaml      # Thermal network topology
├── scenarios/               # Scenario variants
└── systems/                 # System configuration variants
```

## Model Formulation

### Decision Variables

| Variable | Domain | Description |
|----------|--------|-------------|
| `P_buy[t]` | ℝ⁺ | Grid electricity purchase [MW] |
| `P_sell[t]` | ℝ⁺ | Grid electricity export [MW] |
| `HP_Q[t]` | ℝ⁺ | Heat pump thermal output [MW] |
| `HP_cap_mw` | ℝ⁺ | Heat pump installed capacity [MW] |
| `HP_build` | {0,1} | Heat pump investment decision |
| `TES_E[t]` | ℝ⁺ | Storage energy content [MWh] |
| `TES_Qc[t]` | ℝ⁺ | Storage charging power [MW] |
| `TES_Qd[t]` | ℝ⁺ | Storage discharging power [MW] |

### Constraints

**Heat Balance:**
```
∑ Q_gen[t] + TES_Qd[t] = Q_demand[t] + TES_Qc[t] + Q_loss[t]  ∀t
```

**Electricity Balance:**
```
P_buy[t] + ∑ P_gen[t] = P_sell[t] + ∑ HP_Pel[t] + P2H[t]  ∀t
```

**Investment Bounds:**
```
cap_min × build ≤ cap ≤ cap_max × build
```

### Objective Function

Minimize total system cost:
```
min  ∑_t (C_fuel + C_elec + C_CO2 + C_dump) × Δt
   + CAPEX_annual + Activation_cost
```

Where:
- `C_fuel`: Fuel costs (gas, biomass, waste)
- `C_elec`: Net electricity costs (purchase - sale)
- `C_CO2`: Carbon emission costs
- `CAPEX_annual`: Annualized investment costs

## Thermal Network Model

The framework supports brownfield thermal networks with physical heat loss calculation:

```
Q_loss = U × L × (T_supply - T_ambient)
```

Where:
- `U`: Heat transfer coefficient [W/(m·K)]
- `L`: Pipe length [m]
- `T_supply`, `T_ambient`: Supply and ambient temperatures [K]

Network topology is defined in YAML:

```yaml
# configs/networks/brownfield.yaml
pipes:
  - id: P1
    from_node: source
    to_node: consumer1
    length_m: 500
    diameter_mm: 200
    u_value_w_per_mk: 0.5
```

## Output Structure

```
exports/stadtbach/
├── summary.json           # Key performance indicators
├── timeseries.csv         # Hourly dispatch results
├── costs_breakdown.csv    # Detailed cost analysis
├── emissions.csv          # CO₂ emissions by source
└── investment.csv         # Optimal capacities
```

## Project Structure

```
energis/
├── models/               # Pyomo model components
│   ├── system_builder.py # Main model construction
│   ├── network_manager.py# Thermal network handling
│   └── blocks/           # Component blocks (HP, storage, etc.)
├── run/                  # Optimization orchestration
│   └── rolling_horizon.py# PF and RH workflows
├── io/                   # Input/output utilities
│   ├── loader.py         # Data loading
│   └── exporter.py       # Results export
├── config/               # Configuration handling
└── utils/                # Helper functions

configs/                  # Configuration files
notebooks/                # Jupyter notebooks
tests/                    # Test suite
docs/                     # Documentation
```

## Testing

```bash
# Run comprehensive system test
python tests/test_full_system.py

# Run all unit tests
pytest tests/ -v
```

## Documentation

- [Technical Methodology](docs/METHODOLOGY.md) - Detailed model formulation
- [User Guide](docs/USER_GUIDE.md) - Configuration and usage instructions
- [Data Format](docs/DATA_FORMAT.md) - Input data requirements

## Citation

If you use EnerGIS in your research, please cite:

```bibtex
@article{energis2024,
  title={EnerGIS: A Modular MILP Framework for District Heating System Optimization},
  author={[Authors]},
  journal={Applied Energy},
  year={2024},
  volume={},
  pages={},
  doi={}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This work was developed as part of research on district heating decarbonization at [Institution]. The Stadtbach case study data is based on real-world operational data from a German district heating network.
