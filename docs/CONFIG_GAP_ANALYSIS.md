# Config Gap Analysis: New Schema vs. system_builder.py Requirements

## 📋 Purpose

Verify that the new config schema (from CONFIG_REFACTORING_PROPOSAL.md) covers **ALL** functionality currently used by `system_builder.py`.

---

## ✅ Full Coverage Matrix

### 🔥 Heat Pumps

| Parameter | Current Usage | New Schema | Status | Notes |
|-----------|---------------|------------|--------|-------|
| **Identification** |
| `id` | Component name | `assets/components.yaml` → `heat_pumps.HP1` | ✅ | |
| `enabled` | Skip if false | Implicit (present = enabled) | ✅ | |
| `type` | COP calculation model | `technology: high_temp_heat_pump` | ✅ | |
| **Data Sources** |
| `wrg_source_column` | Waste heat temp series | `waste_heat_source.temperature_column` | ✅ | |
| `wrg_capacity_column` | Available heat series | `waste_heat_source.available_power_column` | ✅ | |
| **Operational** |
| `min_load` | Part-load limit | ❌ **MISSING** | ⚠️ | **ADD to tech_library/heat_pumps.yaml** |
| `cop_default` | Fallback COP | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| **Capacity** |
| `max_th_mw` | Fixed/existing cap | `existing.thermal_capacity_mw` | ✅ | |
| `capacity_min_mw` | Min if built | `expansion.min_additional_capacity_mw` | ✅ | |
| `capacity_max_mw` | Max possible | `expansion.max_additional_capacity_mw` | ✅ | |
| **Investment** |
| `capex_eur_per_mw` | Capital cost | `expansion.capex_eur_per_mw` | ✅ | |
| `activation_cost_eur` | Fixed install cost | ❌ **MISSING** | ⚠️ | **ADD to expansion schema** |
| `lifetime_years` | Economic life | `expansion.lifetime_yr` | ✅ | |
| `tie_breaker_eur_per_mw` | Optimization tie-break | ❌ **MISSING** | ⚠️ | **ADD (optional)** |
| **COP Calculation** |
| `cop.cop_fallback` | Default COP | ❌ **MISSING** | ⚠️ | **ADD to tech_library/heat_pumps.yaml** |
| `cop.cop_min/max` | Physical bounds | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `cop.deltaT_K` | Temperature lift | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `cop.tables.standard` | 2D COP lookup | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `cop.sink_defaults.Tsink_out_K` | Default supply temp | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |

**Action Items for Heat Pumps:**
```yaml
# tech_library/heat_pumps.yaml (NEW - COMPLETE VERSION)
heat_pumps:
  high_temp_heat_pump:
    description: "High-temperature heat pump for district heating"

    # Operational limits
    min_load_fraction: 0.30         # Minimum part-load (30%)

    # COP calculation
    cop_model:
      type: lookup_table_2d         # or: analytical, constant
      fallback_cop: 2.5
      cop_bounds: [1.5, 6.0]

      # 2D lookup table (source temp x sink temp)
      lookup_table:
        source_temps_K: [273.15, 283.15, 293.15, 303.15, 313.15, 323.15]
        sink_temps_K: [343.15, 353.15, 363.15, 373.15]
        cop_values:
          - [2.45, 2.86, 3.43, 4.29, 5.72, 8.58]  # Sink 70°C
          - [2.21, 2.52, 2.94, 3.53, 4.41, 5.88]  # Sink 80°C
          - [2.02, 2.27, 2.59, 3.02, 3.63, 4.54]  # Sink 90°C
          - [1.87, 2.07, 2.33, 2.67, 3.11, 3.73]  # Sink 100°C

      # Analytical model (alternative to lookup)
      analytical:
        carnot_efficiency: 0.50     # 50% of Carnot
        delta_T_pinch_K: 5.0
        heat_loss_factor: 0.10

    # Default costs (can be overridden in assets)
    costs:
      capex_eur_per_mw: 400000
      opex_eur_per_mw_yr: 8000
      activation_cost_eur: 250000   # Fixed installation cost
      lifetime_yr: 15
```

---

### 📦 Thermal Storage

| Parameter | Current Usage | New Schema | Status | Notes |
|-----------|---------------|------------|--------|-------|
| **Type** |
| `enabled` | Include storage | Implicit (present = enabled) | ✅ | |
| `type` | `simple` or `stratified` | `technology: stratified_tank` | ✅ | Technology reference |
| **Capacity** |
| `min_energy_mwh` | Min if built | `expansion.min_additional_energy_mwh` | ✅ | |
| `max_energy_mwh` | Max possible | `expansion.max_additional_energy_mwh` | ✅ | |
| `min_power_mw` | Min charge/discharge | `expansion.min_additional_power_mw` | ✅ | |
| `max_power_mw` | Max charge/discharge | `expansion.max_additional_power_mw` | ✅ | |
| **Efficiency** |
| `eff_charge` | Charging efficiency | ❌ **MISSING** | ⚠️ | **ADD to tech_library/storage.yaml** |
| `eff_discharge` | Discharging efficiency | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `loss_hour` | Hourly standby loss | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `eff_charge_series` | Time-varying charge eff | ❌ **MISSING** | ⚠️ | **ADD (optional)** |
| `eff_discharge_series` | Time-varying discharge | ❌ **MISSING** | ⚠️ | **ADD (optional)** |
| `loss_hour_series` | Time-varying loss | ❌ **MISSING** | ⚠️ | **ADD (optional)** |
| **Initial Conditions** |
| `soc0_mwh` | Initial state of charge | ❌ **MISSING** | ⚠️ | **ADD to scenarios/** |
| **Terminal Conditions** (Rolling Horizon) |
| `terminal.state` | `free`, `cyclic`, `target` | ❌ **MISSING** | ⚠️ | **ADD to scenarios/** |
| `terminal.policy` | `equal`, `geq`, `soft`, `value` | ❌ **MISSING** | ⚠️ | **ADD to scenarios/** |
| `terminal.target_mwh` | Target SOC | ❌ **MISSING** | ⚠️ | **ADD to scenarios/** |
| `terminal.salvage_price_eur_mwh` | Terminal value | ❌ **MISSING** | ⚠️ | **ADD to scenarios/** |
| `terminal.soft_penalty_eur_mwh` | Soft constraint penalty | ❌ **MISSING** | ⚠️ | **ADD to scenarios/** |
| **Coupling** |
| `power_energy_coupling` | Fixed P/E ratio | `expansion.coupling_ratio` | ✅ | |
| **Stratified Storage** |
| `T_hot_C` | Hot zone temp | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `T_cold_C` | Cold zone temp | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `T_ambient_C` | Ambient temp | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `T_ground_C` | Ground temp | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `aspect_ratio` | Height/diameter | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `geometry_type` | `tank` or `pit` | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `U_top`, `U_side`, `U_bottom` | Heat loss coefficients | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `V_hot_init_fraction` | Initial hot fraction | ❌ **MISSING** | ⚠️ | **ADD to scenarios/** |
| **Investment** |
| `energy_capex_eur_per_mwh` | Energy capacity cost | `expansion.energy_capex_eur_per_mwh` | ✅ | |
| `power_capex_eur_per_mw` | Power capacity cost | `expansion.power_capex_eur_per_mw` | ✅ | |
| `activation_cost_eur` | Fixed install cost | ❌ **MISSING** | ⚠️ | **ADD** |
| `lifetime_years` | Economic life | `expansion.lifetime_yr` | ✅ | |

**Action Items for Storage:**
```yaml
# tech_library/storage.yaml (NEW)
storage:
  stratified_tank:
    description: "Stratified hot water storage tank"

    # Efficiency parameters
    efficiency:
      charge: 0.95
      discharge: 0.95
      hourly_loss_factor: 0.9999    # 99.99% retained per hour

    # Thermal zones (stratified model)
    thermal:
      hot_zone_temp_c: 90.0
      cold_zone_temp_c: 40.0
      ambient_temp_c: 15.0
      ground_temp_c: 10.0

    # Geometry
    geometry:
      type: tank                      # or: pit
      aspect_ratio: 1.5               # Height/Diameter

    # Heat loss coefficients [W/(m²·K)]
    heat_loss:
      U_top: 0.30
      U_side: 0.20
      U_bottom: 0.15

    # Default costs
    costs:
      energy_capex_eur_per_mwh: 5000
      power_capex_eur_per_mw: 50000
      activation_cost_eur: 50000
      lifetime_yr: 25

  simple_tank:
    description: "Simple single-zone storage"
    efficiency:
      charge: 0.95
      discharge: 0.95
      hourly_loss_factor: 0.9995
```

```yaml
# scenarios/capacity_expansion.yaml (ADDITIONS)
scenario:
  # ... (existing)

  # Initial conditions
  initial_state:
    storage:
      TES1:
        soc_mwh: 500.0
        hot_zone_fraction: 0.5    # For stratified storage

  # Terminal conditions (for rolling horizon)
  terminal_conditions:
    storage:
      state: cyclic               # or: free, target
      policy: equal               # or: geq, soft, value
      target_mwh: null            # null = use initial SOC

      # Value function parameters (for policy=value)
      salvage_price_eur_mwh: 50.0
      soft_penalty_eur_mwh: 100.0

      # Diminishing returns (optional)
      value_function_type: constant  # or: diminishing
      diminishing_decay: 0.3
```

---

### ⚡ Thermal Generators (Boilers, CHP)

| Parameter | Current Usage | New Schema | Status | Notes |
|-----------|---------------|------------|--------|-------|
| **Identification** |
| Generator ID (e.g., `hkw`) | Component key | `assets/components.yaml` → `chp_plants.HKW` | ✅ | |
| **Efficiency** |
| `th_eff` | Thermal efficiency | ❌ **MISSING** | ⚠️ | **ADD to tech_library/generators.yaml** |
| `el_eff` | Electrical efficiency (CHP) | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| **Fuel** |
| `fuel_bus` | `gas`, `biomass`, `waste`, `oil` | ❌ **MISSING** | ⚠️ | **ADD to technology reference** |
| **Operational** |
| `min_load` | Part-load limit | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| **Capacity** |
| `cap_th_mw` | Thermal capacity | `existing.thermal_capacity_mw` | ✅ | |
| `cap_el_mw` | Electrical capacity (CHP) | `existing.electrical_capacity_mw` | ✅ | |

**Action Items for Generators:**
```yaml
# tech_library/generators.yaml (ENHANCED)
generators:
  gas_chp_extraction:
    description: "Gas-fired CHP with extraction turbine"
    fuel_type: natural_gas
    efficiency:
      thermal: 0.743
      electrical: 0.177
    operational:
      min_load_fraction: 0.40
      ramp_rate_per_min: 0.05
    costs:
      fuel_bus_reference: natural_gas  # Links to fuels.yaml

  gas_condensing_boiler:
    description: "High-efficiency gas boiler"
    fuel_type: natural_gas
    efficiency:
      thermal: 0.936
      electrical: null          # Heat-only
    operational:
      min_load_fraction: 0.20
    costs:
      fuel_bus_reference: natural_gas

  biomass_chp:
    description: "Biomass CHP plant"
    fuel_type: biomass
    efficiency:
      thermal: 0.485
      electrical: 0.177
    operational:
      min_load_fraction: 0.60  # Biomass needs stable operation
    costs:
      fuel_bus_reference: biomass

# Assets reference the technology
# assets/components.yaml
chp_plants:
  HKW:
    technology: gas_chp_extraction  # References tech_library
    existing:
      thermal_capacity_mw: 150.0
      electrical_capacity_mw: 35.0
      commissioning_year: 2005
    expansion:
      enabled: false
```

---

### 🔌 Power-to-Heat (P2H)

| Parameter | Current Usage | New Schema | Status | Notes |
|-----------|---------------|------------|--------|-------|
| `enabled` | Include P2H | Implicit | ✅ | |
| `cap_th_mw` | Thermal capacity | `existing.thermal_capacity_mw` | ✅ | |
| `el_to_th_eff` | Electric-to-thermal eff | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |
| `min_load` | Part-load limit | ❌ **MISSING** | ⚠️ | **ADD to tech_library** |

**Action Items for P2H:**
```yaml
# tech_library/p2h.yaml (NEW)
p2h:
  electrode_boiler:
    description: "Electric resistance heater"
    efficiency:
      electric_to_thermal: 0.99
    operational:
      min_load_fraction: 0.0    # Can modulate to zero
      response_time_s: 1        # Very fast response
    costs:
      capex_eur_per_mw: 50000
      opex_eur_per_mw_yr: 500
      lifetime_yr: 20
```

---

### 🌐 Thermal Network

| Parameter | Current Usage | New Schema | Status | Notes |
|-----------|---------------|------------|--------|-------|
| **Basic** |
| `enabled` | Include network | `networks.DH_primary.enabled` | ✅ | |
| `brownfield_mode` | Simplified vs detailed | ❌ **REMOVED** | ⚠️ | **New: Always use node-based model** |
| **Temperatures** |
| `supply_temp_nominal_c` | Supply temp | `supply_temp_bounds_c` | ✅ | Now has bounds |
| `return_temp_nominal_c` | Return temp | `return_temp_bounds_c` | ✅ | Now has bounds |
| **Physical Constants** |
| `cp_water_kj_per_kg_k` | Specific heat | ❌ **MISSING** | ⚠️ | **ADD to tech_library/fluids.yaml** |
| `rho_water_kg_per_m3` | Density | ❌ **MISSING** | ⚠️ | **ADD to tech_library/fluids.yaml** |
| `max_velocity_m_s` | Velocity limit | In `scenarios/` constraints | ✅ | Moved to scenario |
| **Brownfield Simplified Model** |
| `brownfield_temp_drop_per_pipe_c` | Simplified temp loss | ❌ **MISSING** | ⚠️ | **ADD backward compat** |
| `network_Q_loss_bounds_mw` | Total loss bounds | ❌ **MISSING** | ⚠️ | **ADD backward compat** |
| `brownfield_loss_model` | Loss calculation method | ❌ **MISSING** | ⚠️ | **ADD backward compat** |
| `brownfield_loss_ref_heat_mw` | Reference load | ❌ **MISSING** | ⚠️ | **ADD backward compat** |
| **Heating Curve** |
| `heating_curve.enabled` | Outdoor-dependent supply | ❌ **MISSING** | ⚠️ | **ADD to network config** |
| `heating_curve.T_supply_min_c` | Min supply temp | ❌ **MISSING** | ⚠️ | **ADD** |
| `heating_curve.T_supply_max_c` | Max supply temp | ❌ **MISSING** | ⚠️ | **ADD** |
| `heating_curve.T_outdoor_high_c` | Outdoor temp (min supply) | ❌ **MISSING** | ⚠️ | **ADD** |
| `heating_curve.T_outdoor_low_c` | Outdoor temp (max supply) | ❌ **MISSING** | ⚠️ | **ADD** |
| **Costs** |
| `pipe_capex_eur_per_m` | Pipe installation | `pipes.*.expansion.capex_eur_per_m` | ✅ | Per pipe |
| `pump_capex_eur_per_kw` | Pump investment | ❌ **MISSING** | ⚠️ | **ADD to pumps** |
| `heat_loss_cost_eur_per_mwh` | Loss penalty | ❌ **MISSING** | ⚠️ | **ADD to scenario** |

**Action Items for Network:**

```yaml
# tech_library/fluids.yaml (NEW)
fluids:
  water:
    description: "Water properties for district heating"
    properties:
      specific_heat_kj_per_kg_k: 4.186
      density_kg_per_m3: 983         # At ~60°C average
      dynamic_viscosity_pa_s: 0.0004 # Temperature-dependent (TODO)
      thermal_conductivity_w_per_m_k: 0.65

# tech_library/pipes.yaml (NEW)
pipes:
  standard_insulated:
    description: "Pre-insulated steel pipe (standard)"
    heat_loss:
      lambda_insulation_w_per_m_k: 0.025
      thickness_insulation_mm: 80
    hydraulics:
      roughness_mm: 0.05           # Absolute roughness
      friction_factor: darcy_weisbach  # Calculation method
    costs:
      capex_eur_per_m:
        DN100: 400
        DN150: 500
        DN200: 600
        DN250: 700
        DN300: 850
        DN400: 1100
        DN500: 1400

# assets/stadtbach/network_topology.yaml (ADDITIONS FOR BACKWARD COMPAT)
networks:
  DH_primary:
    # ... (existing node/pipe structure)

    # Backward compatibility: Simplified brownfield model
    brownfield_simplified_model:
      enabled: false               # Use detailed model by default

      # If enabled: Use simplified single-bus model
      simplified_params:
        temp_drop_per_pipe_c: 1.0
        total_loss_bounds_mw: [0, 50]
        loss_model: demand_proportional  # or: constant, time_varying
        reference_heat_load_mw: 150.0

    # Heating curve (outdoor-dependent supply temperature)
    heating_curve:
      enabled: true
      outdoor_temp_column: "T_outdoor_C"
      profile:
        T_supply_min_c: 90
        T_supply_max_c: 120
        T_outdoor_high_c: 15   # Outdoor temp for min supply
        T_outdoor_low_c: -10   # Outdoor temp for max supply
```

---

### ⚡ Grid & Market

| Parameter | Current Usage | New Schema | Status | Notes |
|-----------|---------------|------------|--------|-------|
| **Electricity Prices** |
| `strompreis_EUR_MWh` | Time series column | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| **Grid Fees** |
| `grid.energy_fee` | Energy fee (EUR/MWh) | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `grid.grid_cost` | Grid usage fee | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| **Selling Electricity** |
| `grid.sell_floor` | Min selling price | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `grid.sell_haircut` | Price reduction factor | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `grid.sell_spread` | Buy-sell spread | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `grid.sell_fee` | Selling fee | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `grid.sell_premium` | Selling premium | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| **Grid Limits** |
| `grid.max_import` | Max import (MW) | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `grid.max_export` | Max export (MW) | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| **Demand Charges** |
| `grid.demand_charge_y` | Annual demand charge | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |

**Action Items for Grid:**
```yaml
# assets/stadtbach/grid.yaml (NEW - CRITICAL)
grid:
  description: "Grid connection at Stadtbach substation"

  # Physical connection limits
  connection:
    max_import_mw: 100.0
    max_export_mw: 50.0
    voltage_level_kv: 20

  # Electricity pricing
  pricing:
    # Base wholesale price (from time series)
    wholesale_price_column: "strompreis_EUR_MWh"

    # Additional fees for buying
    buy_fees:
      energy_fee_eur_per_mwh: 5.0     # Network energy fee
      grid_usage_eur_per_mwh: 10.0    # Grid usage tariff

    # Selling to grid
    sell_model:
      floor_price_eur_per_mwh: 0.0    # Never sell below this
      haircut_fraction: 0.05          # 5% reduction from wholesale
      spread_eur_per_mwh: 2.0         # Fixed spread
      transaction_fee_eur_per_mwh: 1.0
      premium_eur_per_mwh: 0.0        # Green premium (if applicable)

  # Demand charges (capacity-based)
  demand_charges:
    enabled: true
    annual_charge_eur_per_mw: 50000   # 50k EUR/MW/year for peak demand

  # CO2 intensity of grid electricity
  emissions:
    co2_intensity_column: "grid_co2_kg_MWh"  # Time series
```

---

### 💰 Fuels & Emissions

| Parameter | Current Usage | New Schema | Status | Notes |
|-----------|---------------|------------|--------|-------|
| **Fuel Prices** |
| `fuels.gas.price_eur_mwh` | Gas price | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `fuels.biomass.price_eur_mwh` | Biomass price | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `fuels.waste.price_eur_mwh` | Waste heat price | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `fuels.oil.price_eur_mwh` | Oil price | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| **Emission Factors** |
| `fuels.gas.co2_kg_mwh` | Gas emissions | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `fuels.biomass.co2_kg_mwh` | Biomass emissions | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `fuels.waste.co2_kg_mwh` | Waste emissions | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| `fuels.oil.co2_kg_mwh` | Oil emissions | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| **CO2 Pricing** |
| `costs.co2_price_eur_per_t` | CO2 certificate price | ❌ **MISSING** | 🔴 | **CRITICAL: ADD** |
| **Other Costs** |
| `costs.dump_cost_eur_per_mwh_th` | Heat dumping penalty | ❌ **MISSING** | ⚠️ | **ADD** |

**Action Items for Fuels:**
```yaml
# tech_library/fuels.yaml (ENHANCED)
fuels:
  natural_gas:
    description: "Natural gas (pipeline)"
    heating_value_mwh_per_unit: 1.0  # Already in MWh

    # Pricing (can be overridden in scenarios)
    default_price_eur_per_mwh: 40.0

    # Emissions
    co2_emission_factor_kg_per_mwh: 202.0  # ~0.202 kg/kWh
    ch4_leakage_factor: 0.001              # 0.1% methane leakage

  biomass:
    description: "Wood chips / pellets"
    heating_value_mwh_per_unit: 1.0
    default_price_eur_per_mwh: 25.0
    co2_emission_factor_kg_per_mwh: 0.0   # Carbon neutral

  waste_heat:
    description: "Industrial waste heat recovery"
    default_price_eur_per_mwh: 5.0        # Low cost opportunity
    co2_emission_factor_kg_per_mwh: 0.0   # No combustion

  heating_oil:
    description: "Light heating oil (backup)"
    heating_value_mwh_per_unit: 1.0
    default_price_eur_per_mwh: 80.0
    co2_emission_factor_kg_per_mwh: 266.0

# scenarios/capacity_expansion.yaml (ADDITIONS)
scenario:
  # ... (existing)

  # Economic parameters
  economics:
    # Fuel prices (override tech_library defaults)
    fuel_prices:
      natural_gas_eur_per_mwh: 45.0   # Current market price
      biomass_eur_per_mwh: 28.0
      waste_heat_eur_per_mwh: 5.0
      heating_oil_eur_per_mwh: 90.0

    # Carbon pricing
    co2_price_eur_per_tonne: 100.0

    # Other costs
    heat_dump_penalty_eur_per_mwh: 10.0  # Penalty for dumping heat
```

---

### 🎛️ Run Configuration

| Parameter | Current Usage | New Schema | Status | Notes |
|-----------|---------------|------------|--------|-------|
| **Time** |
| `dt_h` | Timestep duration (hours) | `time.resolution_h` | ✅ | |
| Start/end times | Implicit from data | `time.start`, `time.end` | ✅ | |
| **Solver** |
| `solver.name` | Solver to use | `solver.name` | ✅ | |
| `solver.timelimit_s` | Time limit | `solver.timelimit_s` | ✅ | |
| `solver.mip_gap` | Optimality gap | `solver.mip_gap` | ✅ | |
| **Optimization Flags** |
| `include_co2_cost_in_objective` | Include CO2 | `costs.include_co2` | ✅ | |
| `include_capex_costs` | Include CAPEX | `costs.include_capex` | ✅ | |
| `include_activation_costs` | Include activation | `costs.include_activation` | ✅ | |
| `include_tie_breaker_costs` | Include tie-breaker | `costs.include_tie_breaker` | ✅ | |
| `include_demand_charge` | Include demand charges | `costs.include_demand_charge` | ✅ | |

---

## 🔴 Critical Gaps Summary

### MUST ADD (System won't work without these):

1. **Grid & Market Config** (🔴 CRITICAL)
   - Electricity pricing model
   - Import/export limits
   - Demand charges
   - All currently in `configs/00_base/grid.yaml` - need to map to new structure

2. **Fuels & Emissions** (🔴 CRITICAL)
   - Fuel prices (gas, biomass, waste, oil)
   - CO2 emission factors
   - CO2 price
   - All currently in `configs/01_tech/fuels.yaml` - need to map

3. **Tech Library Completion** (⚠️ HIGH PRIORITY)
   - Heat pump: min_load, COP models
   - Storage: efficiencies, loss factors, thermal parameters
   - Generators: efficiencies, min_load
   - P2H: efficiency
   - Pipes: friction, heat loss models
   - Fluids: physical properties

4. **Scenario-Level Config** (⚠️ HIGH PRIORITY)
   - Initial conditions (SOC, temperatures)
   - Terminal conditions (Rolling Horizon)
   - Heating curve parameters

5. **Backward Compatibility** (⚠️ MEDIUM)
   - Brownfield simplified network model (for existing users)

---

## ✅ Action Plan

### Priority 1: Add Missing Core Configs (Week 1)

1. Create `assets/stadtbach/grid.yaml` - Grid connection & pricing
2. Enhance `tech_library/fuels.yaml` - Fuel prices & emissions
3. Add to `scenarios/*.yaml` - Economics section with CO2 price, fuel prices

### Priority 2: Complete Tech Library (Week 1-2)

1. `tech_library/heat_pumps.yaml` - COP models, min_load
2. `tech_library/storage.yaml` - Efficiencies, thermal params
3. `tech_library/generators.yaml` - Efficiencies, min_load
4. `tech_library/p2h.yaml` - Efficiency
5. `tech_library/pipes.yaml` - Friction & heat loss models
6. `tech_library/fluids.yaml` - Water properties

### Priority 3: Scenario Enhancements (Week 2)

1. Add `initial_state` section - Initial conditions
2. Add `terminal_conditions` section - Rolling Horizon config
3. Add `economics` section - Fuel prices, CO2 price

### Priority 4: Backward Compatibility (Week 3)

1. Add `brownfield_simplified_model` option to network
2. Migration tool: Old config → New config
3. Deprecation warnings

---

## ✅ Validation

After implementing all additions, verify:

1. ✅ All `system_builder.py` config accesses have mapping in new schema
2. ✅ Example config can be converted from old → new format
3. ✅ system_builder.py can read new format (via adapter layer)
4. ✅ All tests pass with new configs

---

**Status:** Gap Analysis Complete - Implementation Plan Ready
**Next Step:** Begin Priority 1 implementations
