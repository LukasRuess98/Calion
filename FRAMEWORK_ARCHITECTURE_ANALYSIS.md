# EnerGIS Heat Planning Framework - Comprehensive Architecture Analysis

## Executive Summary

The EnerGIS framework is a **component-based energy system optimization framework** for planning industrial heat networks. It uses **Pyomo** for Mixed-Integer Linear Programming (MILP) modeling and implements a **plugin architecture** with automatic component registration. The framework is organized into distinct layers: data I/O, models, runners, and exporters.

---

## 1. DIRECTORY STRUCTURE

```
Planing-Framework-for-Heat/
├── energis/
│   ├── __init__.py
│   ├── constants.py                    # Global constants (COP_MIN, HOURS_PER_YEAR, etc.)
│   ├── models/                         # Core modeling layer
│   │   ├── __init__.py                # Package exports & version (v2.0-alpha)
│   │   ├── component.py               # Base abstractions (Component Protocol, BaseComponent, Flow, BusType)
│   │   ├── bus.py                     # Bus class (network connection points for commodity flows)
│   │   ├── registry.py                # ComponentRegistry for plugin architecture
│   │   ├── system_builder.py          # Main model builder (761 lines) - v1.0 architecture
│   │   └── blocks/                    # Component implementations (converters, storage, generators)
│   │       ├── heat_pump.py           # HeatPumpBlock (183 lines)
│   │       ├── storage.py             # StorageBlock (294 lines)
│   │       ├── stratified_storage.py  # StratifiedStorageBlock (728 lines) - advanced
│   │       ├── thermal_gen.py         # ThermalGeneratorBlock (93 lines)
│   │       └── p2h.py                 # P2HBlock (163 lines)
│   ├── run/                           # Runner/orchestrator layer
│   │   ├── orchestrator.py            # Main runner (run_all() function)
│   │   └── rolling_horizon.py         # Rolling horizon optimization
│   ├── io/                            # Data I/O and export layer
│   │   ├── __init__.py
│   │   ├── loader.py                  # load_input_excel() - reads scenario data
│   │   ├── exporter.py                # export_scenario_bundle() - CSV, Excel outputs
│   │   ├── plotter.py                 # export_plots() - basic visualizations
│   │   ├── model_inspector.py         # export_model_structure() - debug exports
│   │   ├── publication_exporter.py    # Publication-quality exports
│   │   ├── publication_plotter.py     # Publication-quality plots
│   │   └── applied_energies_exporter.py # Journal-specific exports
│   ├── config/                        # Configuration management
│   │   ├── schema.py                  # Configuration schema validation
│   │   ├── merge.py                   # deep_merge(), load_and_merge()
│   │   └── model_settings.py
│   ├── utils/                         # Utilities
│   │   ├── timeseries.py              # TimeSeriesTable class
│   │   ├── config_utils.py            # apply_heat_pump_defaults()
│   │   ├── storage_utils.py           # Storage calculations
│   │   ├── xlsx.py
│   │   └── simple_yaml.py
│   ├── validation/                    # Validation layer
│   │   └── stadtbach.py               # Case study validation
│   └── analysis/                      # Analysis tools
│       └── sensitivity.py             # Sensitivity analysis
├── configs/                           # Configuration files
│   ├── base.yaml                      # Default base configuration
│   ├── tech_catalog.yaml              # Technology parameters
│   ├── overrides.local.yaml
│   ├── sites/                         # Site-specific configurations
│   │   ├── default.site.yaml
│   │   └── synthetic_example.site.yaml
│   ├── scenarios/                     # Scenario definitions
│   │   ├── perfect_forecast_full_year.scenario.yaml
│   │   ├── pf_then_rh.workflow.scenario.yaml
│   │   └── grid_caps.scenario.yaml
│   └── systems/                       # System topology configurations
│       ├── baseline.system.yaml
│       └── district_heating_stratified_example.yaml
├── examples/                          # Usage examples
│   ├── runner_integration_test.py
│   ├── stratified_storage_integration.py
│   ├── publication_sensitivity_analysis.py
│   ├── custom_component_example.py
│   └── README files
├── tests/                             # Test suite
├── docs/                              # Documentation
└── notebooks/                         # Jupyter notebooks
```

---

## 2. NETWORK ARCHITECTURE

The framework models energy systems as **commodity networks** with explicit flow management:

### 2.1 Core Network Abstractions

**Bus** (`energis/models/bus.py` - 313 lines)
- Central connection points where component flows meet
- Enforces energy/commodity balance: `Σ(inputs) * (1 - loss_factor) = Σ(outputs)`
- Supported bus types: ELECTRICITY, HEAT, COOLING, FUEL_GAS, FUEL_BIOMASS, FUEL_WASTE, HYDROGEN, GENERIC
- Methods:
  - `add_input(flow)` / `add_output(flow)` - Register input/output flows
  - `attach(model, time_set, config, buses)` - Create balance constraint
  - `get_results(model, time_set)` - Extract flow results
  - `is_balanced()` - Check if bus has inputs and outputs

**Example Bus Definitions**:
```python
buses = {
    'electricity': Bus('electricity', BusType.ELECTRICITY),
    'heat': Bus('heat', BusType.HEAT),
    'fuel_gas': Bus('fuel_gas', BusType.FUEL_GAS),
}
```

### 2.2 Network Components (Nodes)

Components are **converter nodes** that connect to buses and have explicit Flow definitions.

**Component Protocol** (`energis/models/component.py` - 322 lines)
- Base abstraction for all components
- Requires implementation of:
  - `attach(model, time_set, config, buses)` → creates variables and constraints
  - `get_results(model, time_set)` → extracts optimization results
  - `validate_config(config)` → validates configuration

**Flow Definition** (dataclass)
- Represents connections between components and buses
- Attributes: `bus`, `direction`, `variable`, `nominal_value`, `investment`
- Example: Heat pump outputs heat to 'heat' bus

### 2.3 Component Registry (Plugin Architecture)

**ComponentRegistry** (`energis/models/registry.py` - 299 lines)
- Central registry for component discovery
- Uses `@register_component` decorator for auto-registration
- Supports metadata: description, category, version, author
- Methods:
  - `register(component_type, component_class, ...)`
  - `create(component_type, **kwargs)`
  - `list_components()` / `list_by_category(category)`
  - `get_metadata(component_type)`

**Registered Components**:
```
heat_pump      - Converter with COP series & waste heat recovery
storage        - Thermal energy storage with power/energy decoupling
thermal_gen    - CHP/fuel generators
p2h            - Power-to-heat converters
stratified_storage - Advanced 2-zone thermal storage
```

---

## 3. NETWORK COMPONENT BLOCKS

### 3.1 Heat Pump Block (`energis/models/blocks/heat_pump.py` - 183 lines)

**Purpose**: Converts electricity to heat with COP (Coefficient of Performance) series

**Key Features**:
- Time-varying COP from lookup tables or analytical calculation
- Waste heat recovery (WRG) with capacity-limited input
- Split between WRG-supplied and fallback heat
- Investment decision variables (capacity and binary on/off)

**Flows**:
- **INPUT**: Electricity from 'electricity' bus (calculated as `Pel = Q_wrg/COP + Q_def/COP_default`)
- **OUTPUT**: Heat to 'heat' bus (Q = Q_wrg + Q_def)

**Variables Created**:
```
{comp}_Q[t]        - Heat output (MW_th)
{comp}_Pel[t]      - Electricity input (MW_e) - Expression, not Var
{comp}_Q_wrg[t]    - Waste heat recovery portion (MW_th)
{comp}_Q_def[t]    - Fallback heat portion (MW_th)
{comp}_on[t]       - Binary on/off (0/1)
{comp}_cap_mw      - Thermal capacity (MW_th) - investment variable
{comp}_build       - Build binary (0/1) - investment variable
{comp}_COP[t]      - COP lookup table parameter
```

**Constraints**:
- Capacity limit: `Q[t] ≤ cap * on[t]`
- Minimum load: `Q[t] ≥ min_load * cap * on[t]`
- Heat split: `Q[t] = Q_wrg[t] + Q_def[t]`
- WRG limit: `Q_wrg[t] ≤ WRG_cap[t]`
- Investment link: `on[t] ≤ build`

**Integration Point**: Connected to 'heat' and 'electricity' buses

### 3.2 Storage Block (`energis/models/blocks/storage.py` - 294 lines)

**Purpose**: Thermal energy storage with power/energy decoupling and time-varying efficiency

**Key Features**:
- Separate energy capacity (MWh) and power capacity (MW)
- Time-varying charge/discharge efficiencies
- Time-varying hourly loss rate
- SOC (State of Charge) tracking
- Investment decisions

**Flows**:
- **INPUT**: Heat from 'heat' bus (charging)
- **OUTPUT**: Heat to 'heat' bus (discharging)

**Variables Created**:
```
{comp}_E[t]        - State of charge (MWh)
{comp}_Qc[t]       - Charge flow (MW_th)
{comp}_Qd[t]       - Discharge flow (MW_th)
{comp}_cap_energy  - Energy capacity (MWh) - investment
{comp}_cap_power   - Power capacity (MW) - investment
{comp}_build       - Build binary - investment
```

**Constraints**:
- Energy balance: `E[t] = E[t-1] * (1-loss[t]) - Qd[t]/eff_d[t] + Qc[t]*eff_c[t]`
- Power limits: `Qc[t] ≤ cap_power`, `Qd[t] ≤ cap_power`
- Capacity coupling: `E[t] ≤ cap_energy`
- Terminal constraint: Optional SOC target at end

**Advanced Features**:
- Terminal state policies: "free", "return_to_initial", "enforce_target"
- Capacity active series: Time-varying available capacity
- Power/energy coupling ratio for optimization hints

### 3.3 Thermal Generator Block (`energis/models/blocks/thermal_gen.py` - 93 lines)

**Purpose**: CHP/fuel generators with optional electricity output

**Flows**:
- **INPUT**: Fuel from bus (gas, biomass, waste)
- **OUTPUT**: Heat to 'heat' bus, optional electricity to 'electricity' bus

**Variables Created**:
```
{comp}_Qth[t]      - Thermal output (MW_th)
{comp}_Pel[t]      - Electrical output (MW_e) - optional
{comp}_fuel[t]     - Fuel input (MW_fuel)
```

### 3.4 Power-to-Heat Block (`energis/models/blocks/p2h.py` - 163 lines)

**Purpose**: Direct electric heating (resistive or reversible heat pump)

**Flows**:
- **INPUT**: Electricity from 'electricity' bus
- **OUTPUT**: Heat to 'heat' bus

**Variables Created**:
```
{comp}_Qth[t]      - Heat output (MW_th)
{comp}_Pel[t]      - Electricity input (MW_e)
```

### 3.5 Stratified Storage Block (`energis/models/blocks/stratified_storage.py` - 728 lines)

**Purpose**: Advanced 2-zone thermal storage (hot/cold zones)

**Key Features**:
- Dual-zone temperature stratification
- Zone-specific heat losses and mixing
- Realistic storage operation modeling
- Charging/discharging with zone preference

---

## 4. THE SYSTEM BUILDER: Model Construction

**File**: `/home/user/Planing-Framework-for-Heat/energis/models/system_builder.py` (761 lines)

### 4.1 Main Entry Point: `build_model()`

```python
def build_model(table: TimeSeriesTable, cfg: Dict[str, Any], dt_h: float = 1.0):
    """
    Build a Pyomo ConcreteModel for energy system optimization.
    
    Returns:
        pyo.ConcreteModel with:
        - Decision variables for flows, capacities, investment
        - Constraints for balances and operational limits
        - Objective function minimizing total system cost
    """
```

### 4.2 Model Construction Flow

1. **Initialize Pyomo Model**
   - Create `ConcreteModel` with time set `m.t = RangeSet(1, T)`
   - Define time-varying parameters: price, demand, grid CO2

2. **Create Grid Interface Variables**
   - `m.P_buy[t]` - Electricity purchase (MW)
   - `m.P_sell[t]` - Electricity sales (MW)
   - `m.Q_dump[t]` - Heat dump (MW_th)
   - `m.P_buy_peak` - Peak import (for demand charges)

3. **Instantiate Component Blocks**
   ```python
   for hp in heat_pumps:
       cop_series = _cop_series_from_table(table, wrg_col, cfg, hp_type)
       block = HeatPumpBlock(
           name=hp_id,
           min_load=min_load,
           cop_series=cop_series,
           capacity_min_mw=cap_min,
           capacity_max_mw=cap_max,
           ...
       )
       flows = block.attach(m, m.t, cfg, buses)
       # flows dict contains Pyomo variables
   ```

4. **Register Flows with Buses**
   - Heat pump heat output → 'heat' bus output
   - Heat pump electricity input → 'electricity' bus input
   - Storage charge/discharge → 'heat' bus
   - Generators fuel → 'gas'/'biomass'/'waste' buses

5. **Create Bus Balance Constraints**
   ```python
   # For each bus at each time:
   Σ(input flows) * (1 - loss) == Σ(output flows)
   ```

6. **Build Objective Function**
   - Grid costs: `Σ(P_buy[t] * price[t] * dt_h) - Σ(P_sell[t] * sell_price[t] * dt_h)`
   - Fuel costs: `Σ(fuel[t] * fuel_price[t] * dt_h)`
   - CO2 costs: `Σ(emissions[t] * co2_price[t] * dt_h)` (if enabled)
   - Dump costs: `Σ(Q_dump[t] * dump_cost * dt_h)`
   - Demand charges: `P_peak * demand_charge_rate * year_fraction`
   - CAPEX/OPEX: Investment and operational costs

### 4.3 COP Calculation

**Function**: `_cop_series_from_table()` - Sophisticated COP modeling

**Two Methods**:
1. **Lookup Table** (preferred if configured)
   - 2D interpolation: COP(source_temperature, sink_temperature)
   - Supports waste heat recovery temperature as source
   - Clamping to prevent out-of-range values

2. **Analytical Fallback**
   - LMTD (Log Mean Temperature Difference) method
   - Based on thermodynamic efficiency factors
   - COP = A * B * η * (1 - qww) + 1 - η - FQ

**Output**: Time-varying COP series [COP_MIN, COP_MAX] range-clamped

---

## 5. THE RUNNER: Orchestration and Export

**File**: `/home/user/Planing-Framework-for-Heat/energis/run/orchestrator.py`

### 5.1 Main Runner Function: `run_all()`

```python
def run_all(config_paths: List[str], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute complete workflow: load data → build model → solve → export results
    
    Workflow:
    1. Load and merge configurations
    2. Load input time series (Excel)
    3. Apply scenario horizon filter
    4. Validate capacity vs demand
    5. Build Pyomo model (system_builder.build_model)
    6. Optionally export model structure (for debugging)
    7. Solve with configured solver (Gurobi/GLPK)
    8. Collect time series and summary results
    9. Export to multiple formats
    10. Generate plots and publication-quality outputs
    """
```

### 5.2 Key Runner Steps

**Step 1: Configuration Merge**
```python
cfg = load_and_merge(config_paths)  # From energis.config.merge
cfg = deep_merge(cfg, overrides)     # Apply runtime overrides
```

**Step 2: Data Loading**
```python
table = load_input_excel(
    site.get('input_xlsx', 'Import_Data.xlsx'),
    site,
    dt_hours=dt_h
)
```

**Step 3: Model Building**
```python
m = build_model(table, cfg, dt_h=dt_h)  # Returns Pyomo ConcreteModel
```

**Step 4: Solving**
```python
opt = pyo.SolverFactory(solver_requested)
solver_result = opt.solve(m, tee=False)
```

**Step 5: Result Collection**
```python
series, summary_sections, costs = _collect_timeseries_and_summary(
    table, cfg, dt_h, m
)
```

### 5.3 Result Extraction: `_collect_timeseries_and_summary()`

**Returns**: (time_series_dict, summary_sections, costs_dict)

**Time Series** (example keys):
```
P_buy_MW              - Grid electricity import
P_sell_MW             - Grid electricity export
Q_dump_MWth           - Heat dumped
{comp}_Q_th_MW        - Component thermal output
{comp}_Pel_MW         - Component electrical input
{comp}_on             - Component on/off status
{comp}_COP            - Component COP (calculated from flows)
TES_SOC_MWh           - Storage state of charge
TES_charge_MW         - Storage charging rate
TES_discharge_MW      - Storage discharging rate
```

**Summary Sections** (OrderedDict):
```
objective:
  OBJ_value_EUR                    - Total system cost
  Grid_energy_cost_EUR
  Grid_sell_revenue_EUR
  Fuel_cost_EUR
  CO2_cost_EUR
  Capex_cost_EUR
  Demand_charge_cost_EUR

grid:
  Energy_from_grid_MWh
  Energy_to_grid_MWh
  Heat_dumped_MWh
  Grid_CO2_emissions_t

heat_pump_{comp}:
  Heat_output_MWh
  Electricity_input_MWh
  Thermal_capacity_MW              - Investment decision
  Build_binary
  Average_COP

storage_{comp}:
  Charge_MWh
  Discharge_MWh
  Average_SOC_MWh
  Capacity_MWh                     - Investment decision
  Power_limit_MW
```

---

## 6. DATA I/O: Loaders and Exporters

### 6.1 Input Data Layer

**File**: `energis/io/loader.py`

**Function**: `load_input_excel(filename, site, dt_hours)`

**Input Format**: Excel workbook with:
- Time index column (timestamp)
- **Required columns**:
  - `waermebedarf_MWth` - Heat demand (MW_th)
  - `strompreis_EUR_MWh` - Electricity price (EUR/MWh)
  - `grid_co2_kg_MWh` - Grid CO2 emissions (kg CO2/MWh)
- **Optional columns**:
  - `WRG{i}_T_K` - Waste heat recovery source temperatures (Kelvin)
  - `WRG{i}_Q_cap` - Waste heat recovery capacity (MW_th)
  - `storage_loss_hour` - Time-varying storage loss rate
  - `storage_eff_charge`, `storage_eff_discharge` - Time-varying efficiencies

**Output**: `TimeSeriesTable` with index and columnar data

### 6.2 Export Layer

**Files**:
- `energis/io/exporter.py` - Standard exports (CSV, Excel, JSON)
- `energis/io/plotter.py` - Basic visualizations
- `energis/io/publication_exporter.py` - Publication-quality formats
- `energis/io/applied_energies_exporter.py` - Journal-specific outputs

**Main Export Function**: `export_scenario_bundle()`

**Exports**:
```
exports/{timestamp}_{scenario}/
├── scenario_timeseries.csv          - Input + result time series
├── costs.json                       - Cost breakdown
├── summary.json                     - Component summaries
├── metadata.json                    - Run metadata
├── merged_config.json               - Final configuration used
├── scenario_data.xlsx               - Excel bundle
├── manifest.json                    - Export manifest
├── plots/                           - Basic plots
├── publication_plots/               - Publication-quality plots
│   ├── *_highres.png (300 dpi)
│   └── *_publication.pdf
├── publication_latex/               - LaTeX tables
└── applied_energies/                - Journal-specific exports
```

---

## 7. CONFIGURATION ARCHITECTURE

### 7.1 Configuration Files

**Base Configuration** (`configs/base.yaml`):
```yaml
heat_pumps:
  cop:
    tables:
      default:
        x: [263.15, 268.15, ...]  # Source temps (K)
        y: [343.15, 353.15, ...]  # Sink temps (K)
        values: [[2.5, 2.8, ...], [3.0, 3.2, ...]]
        clamp: true
    sink_defaults:
      Tsink_out_K: 363.15 (90°C)

costs:
  co2_price_eur_per_t: 100
  dump_cost_eur_per_mwh_th: 1000
  include_co2_cost_in_objective: true
  include_capex_costs: true

grid:
  demand_charge_eur_per_mw_y: 0
  energy_fee_eur_mwh: 0
  gridcost_eur_mwh: 0
  max_import_mw: 999999
  max_export_mw: 999999
```

**System Configuration** (`configs/systems/baseline.system.yaml`):
```yaml
system:
  heat_pump_defaults:
    enabled: true
    type: standard
    max_th_mw: 40.0
    min_th_mw: 5.0
    investment:
      enabled: true
      capacity_min_mw: 1.0
      capacity_max_mw: 100.0

  heat_pumps:
    - id: HP1
      wrg_source_column: WRG1_T_K
      wrg_capacity_column: WRG1_Q_cap

  storage:
    enabled: true
    max_energy_mwh: 100.0
    max_power_mw: 30.0
    eff_charge: 0.98
    eff_discharge: 0.98
    loss_hour: 0.0005

  generators:
    hkw:
      enabled: true
      cap_th_mw: 75.0
    p2h:
      enabled: true
      cap_th_mw: 10.0
```

### 7.2 Configuration Merging

**Function**: `deep_merge()` - Recursive dictionary merge with overrides

**Load Order**:
1. Load base configs (left to right)
2. Apply scenario overrides
3. Apply runtime overrides
4. Validate with schema

---

## 8. EXAMPLE USAGE FLOW

### 8.1 Typical Workflow

```python
from energis.run.orchestrator import run_all

# Define configuration files
config_paths = [
    "configs/base.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/perfect_forecast_full_year.scenario.yaml"
]

# Optional runtime overrides
overrides = {
    "costs": {
        "co2_price_eur_per_t": 150
    }
}

# Run complete workflow
results = run_all(config_paths, overrides)

# Access results
print(results['outdir'])              # Export directory
print(results['summary'])             # Summary metrics
print(results['design'])              # Investment decisions
print(results['costs'])               # Cost breakdown
```

### 8.2 Component-Based Model Building

```python
from energis.models import (
    ComponentRegistry,
    Bus,
    HeatPumpBlock,
    StorageBlock,
    BusType
)
from energis.utils.timeseries import TimeSeriesTable
import pyomo.environ as pyo

# Create buses
buses = {
    'heat': Bus('heat', BusType.HEAT),
    'electricity': Bus('electricity', BusType.ELECTRICITY),
}

# Create components
hp = HeatPumpBlock(
    'HP1',
    min_load=0.3,
    cop_series=[3.5] * 24,
    capacity_min_mw=5.0,
    capacity_max_mw=50.0,
    capacity_init_mw=25.0,
    investable=True
)

# Build Pyomo model
m = pyo.ConcreteModel()
m.t = pyo.RangeSet(1, 24)

# Attach components
flows = hp.attach(m, m.t, cfg, buses)
```

---

## 9. FLOW ARCHITECTURE: Component Connections

### 9.1 Energy Network Topology

```
┌─────────────────────────────────────────────────────┐
│                 ELECTRICITY BUS                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ Inputs:                                      │   │
│  │  - P_buy[t]      (grid import)               │   │
│  │  - Generators (CHP output)                   │   │
│  │ Outputs:                                     │   │
│  │  - Heat pumps (consumption)                  │   │
│  │  - P2H (consumption)                         │   │
│  │  - P_sell[t]     (grid export)               │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                    HEAT BUS                         │
│  ┌──────────────────────────────────────────────┐   │
│  │ Inputs:                                      │   │
│  │  - Heat pumps (output)                       │   │
│  │  - Generators (thermal output)               │   │
│  │  - P2H (thermal output)                      │   │
│  │  - Storage discharge                         │   │
│  │ Outputs:                                     │   │
│  │  - Demand (waermebedarf_MWth)                │   │
│  │  - Storage charge                            │   │
│  │  - Q_dump[t] (dump to environment)           │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│              FUEL BUSES (gas, biomass, waste)       │
│  ┌──────────────────────────────────────────────┐   │
│  │ Inputs:  Availability (unlimited or limited)│   │
│  │ Outputs: Generators (fuel consumption)       │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 9.2 Data Flow: Runner → Model → Export

```
CONFIGURATION LAYER
├── base.yaml (defaults)
├── system.yaml (topology)
├── scenario.yaml (horizon, mode)
└── site.yaml (location)
        ↓
        ├── Merged Config
        └── Overrides
            ↓
INPUT DATA LAYER
├── Input Excel (demand, prices, weather)
└── TimeSeriesTable
    ↓
MODEL BUILDING (system_builder.py)
├── Create time set & parameters
├── Create grid variables (P_buy, P_sell, Q_dump)
├── Instantiate components:
│   ├── Heat pumps (with COP series)
│   ├── Storage (with efficiency series)
│   ├── Generators
│   └── P2H
├── Create buses & register flows
├── Create balance constraints
├── Create objective function
└── Return Pyomo ConcreteModel
    ↓
SOLVER LAYER
├── Instantiate solver (Gurobi/GLPK)
├── Solve MILP
└── Return solution
    ↓
RESULT EXTRACTION (orchestrator.py)
├── Extract variable values
├── Calculate time series
├── Aggregate component summaries
├── Calculate KPIs & costs
└── Return {series, summary_sections, costs}
    ↓
EXPORT LAYER
├── Write CSV: scenario_timeseries.csv
├── Write Excel: scenario_data.xlsx
├── Write JSON: costs.json, summary.json, metadata.json
├── Plot: plots/*.png
├── Publish: publication_plots/*, publication_latex/*
└── Journal: applied_energies/*
```

---

## 10. KEY FILES SUMMARY

| File | Lines | Purpose | Key Functions/Classes |
|------|-------|---------|----------------------|
| `energis/models/bus.py` | 313 | Network node abstraction | Bus, add_input, add_output, balance constraint |
| `energis/models/component.py` | 322 | Base component abstraction | Component Protocol, BaseComponent, Flow, BusType |
| `energis/models/registry.py` | 299 | Plugin architecture | ComponentRegistry, register_component |
| `energis/models/system_builder.py` | 761 | Main model builder | build_model, _cop_series_from_table |
| `energis/models/blocks/heat_pump.py` | 183 | Heat pump component | HeatPumpBlock |
| `energis/models/blocks/storage.py` | 294 | Storage component | StorageBlock |
| `energis/models/blocks/thermal_gen.py` | 93 | Generator component | ThermalGeneratorBlock |
| `energis/models/blocks/p2h.py` | 163 | Power-to-heat component | P2HBlock |
| `energis/models/blocks/stratified_storage.py` | 728 | Advanced 2-zone storage | StratifiedStorageBlock |
| `energis/run/orchestrator.py` | ~1500 | Main runner | run_all, _collect_timeseries_and_summary |
| `energis/run/rolling_horizon.py` | ~300 | Rolling horizon optimization | - |
| `energis/io/loader.py` | ~200 | Data input | load_input_excel |
| `energis/io/exporter.py` | ~400 | Standard export | export_scenario_bundle |
| `energis/io/plotter.py` | ~300 | Basic plots | export_plots |
| `energis/io/publication_exporter.py` | ~300 | Publication export | export_publication_bundle |
| `energis/config/merge.py` | ~200 | Config merging | deep_merge, load_and_merge |

**Total model code**: ~3,269 lines

---

## 11. ARCHITECTURE PATTERNS

### 11.1 Component Abstraction Pattern
- **Protocol-based design**: Component interface (duck typing)
- **Registration decorator**: `@register_component("type")`
- **Factory pattern**: ComponentRegistry.create("type", **kwargs)
- **Attachment pattern**: `block.attach(model, time_set, config, buses)`

### 11.2 Flow Management Pattern
- **Explicit flow declaration**: Flow(bus, direction, variable)
- **Bus registration**: `bus.add_input(flow)`, `bus.add_output(flow)`
- **Automatic balance**: Pyomo constraint enforces balance per bus per timestep

### 11.3 Configuration Merging Pattern
- **Hierarchical defaults**: base.yaml → system.yaml → scenario.yaml
- **Deep merge**: Recursive dictionary merge with priority
- **Runtime overrides**: Python dict passed to `run_all()`

### 11.4 Result Extraction Pattern
- **Standardized return**: All components return `{flows, investment, state, metadata}`
- **Time series aggregation**: OrderedDict with named series
- **Summary sections**: Nested OrderedDict for reportable metrics

---

## 12. EXTENSION POINTS

### 12.1 Adding New Component Types
1. Create class inheriting from `BaseComponent`
2. Implement `attach()`, `get_results()`, `validate_config()`
3. Use `@register_component("my_type")` decorator
4. Component auto-registers and becomes available

### 12.2 Adding New Bus Types
- Add to `BusType` enum in `energis/models/component.py`
- Bus abstraction handles all bus types identically

### 12.3 Custom Exporters
- Inherit from export functions in `energis/io/`
- Work with time series dict and summary sections
- Examples: `export_plots()`, `export_publication_bundle()`

---

## CONCLUSION

The EnerGIS framework implements a **modular, extensible energy system optimization architecture** with:

1. **Network-centric design**: Explicit buses and flows representing commodity networks
2. **Component-based composition**: Pluggable converters, storage, generators via registry
3. **Configuration-driven**: YAML-based system topology and scenario definition
4. **Comprehensive I/O**: Multiple input formats and publication-quality exports
5. **Solver-agnostic**: Works with Pyomo, supports Gurobi, GLPK, others
6. **Research-ready**: Publication exporters, sensitivity analysis, model inspection

The framework bridges between **high-level scenario definition** (YAML configs) and **low-level optimization** (Pyomo MILP), making it accessible for planning but powerful for research.

