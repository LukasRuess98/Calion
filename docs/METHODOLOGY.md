# Technical Methodology

This document provides a detailed description of the mathematical model formulation implemented in EnerGIS.

## 1. Model Overview

EnerGIS implements a Mixed-Integer Linear Program (MILP) for optimal planning and operation of district heating systems. The model simultaneously optimizes:

- **Operational decisions**: Hourly dispatch of all generation units, storage operation, grid exchange
- **Investment decisions**: Optimal sizing of heat pumps, thermal storage, and other components

### 1.1 Time Discretization

The model uses hourly time steps over a configurable horizon:

- **Perfect Foresight (PF)**: Single optimization over entire horizon (e.g., one year)
- **Rolling Horizon (RH)**: Sequential optimization windows with overlap for realistic operation

```
T = {1, 2, ..., N}  # Set of time steps
Δt = 1 hour         # Time step duration
```

## 2. Sets and Indices

| Set | Description |
|-----|-------------|
| T | Time steps {1, ..., N} |
| G | Thermal generators (CHP, boilers) |
| HP | Heat pumps |
| F | Fuels (gas, biomass, waste) |

## 3. Parameters

### 3.1 Economic Parameters

| Parameter | Unit | Description |
|-----------|------|-------------|
| `p_el[t]` | €/MWh | Electricity spot price |
| `p_f` | €/MWh | Fuel price for fuel f |
| `p_CO2` | €/t | CO₂ emission price |
| `ef_f` | kg/MWh | Emission factor for fuel f |
| `c_grid` | €/MWh | Grid usage fee |
| `c_demand` | €/(MW·a) | Annual demand charge |

### 3.2 Technical Parameters

| Parameter | Unit | Description |
|-----------|------|-------------|
| `η_th,g` | - | Thermal efficiency of generator g |
| `η_el,g` | - | Electrical efficiency of generator g |
| `COP[t]` | - | Heat pump coefficient of performance |
| `Q_dem[t]` | MW | Heat demand |
| `Q_loss[t]` | MW | Network heat losses |

### 3.3 Investment Parameters

| Parameter | Unit | Description |
|-----------|------|-------------|
| `cap_min` | MW | Minimum capacity if built |
| `cap_max` | MW | Maximum allowable capacity |
| `CAPEX` | €/MW | Specific investment cost |
| `c_act` | € | Activation/fixed cost |
| `L` | years | Component lifetime |

## 4. Decision Variables

### 4.1 Continuous Variables

| Variable | Domain | Description |
|----------|--------|-------------|
| `P_buy[t]` | ℝ⁺ | Grid electricity purchase [MW] |
| `P_sell[t]` | ℝ⁺ | Grid electricity sale [MW] |
| `Q_g[t]` | ℝ⁺ | Thermal output of generator g [MW] |
| `F_g[t]` | ℝ⁺ | Fuel consumption of generator g [MW] |
| `Q_hp[t]` | ℝ⁺ | Heat pump thermal output [MW] |
| `P_hp[t]` | ℝ⁺ | Heat pump electrical consumption [MW] |
| `E[t]` | ℝ⁺ | Storage energy content [MWh] |
| `Q_c[t]` | ℝ⁺ | Storage charge power [MW] |
| `Q_d[t]` | ℝ⁺ | Storage discharge power [MW] |
| `cap` | ℝ⁺ | Installed capacity [MW or MWh] |
| `Q_dump[t]` | ℝ⁺ | Dumped excess heat [MW] |

### 4.2 Binary Variables

| Variable | Description |
|----------|-------------|
| `y_buy[t]` | 1 if buying electricity, 0 otherwise |
| `y_on[t]` | 1 if unit is operating, 0 otherwise |
| `y_build` | 1 if component is built, 0 otherwise |
| `y_charge[t]` | 1 if storage charging, 0 otherwise |

## 5. Constraints

### 5.1 Energy Balances

**Heat Balance:**
```
∑_{g∈G} Q_g[t] + ∑_{hp∈HP} Q_hp[t] + Q_d[t]
= Q_dem[t] + Q_c[t] + Q_loss[t] + Q_dump[t]    ∀t ∈ T
```

**Electricity Balance:**
```
P_buy[t] + ∑_{g∈G} P_el,g[t]
= P_sell[t] + ∑_{hp∈HP} P_hp[t] + P_P2H[t]    ∀t ∈ T
```

### 5.2 Grid Coupling

Mutual exclusivity of buying and selling:
```
P_buy[t] ≤ M · y_buy[t]           ∀t ∈ T
P_sell[t] ≤ M · (1 - y_buy[t])    ∀t ∈ T
```

Where M is a sufficiently large constant (Big-M formulation).

### 5.3 Generator Constraints

**Fuel-to-heat conversion:**
```
Q_g[t] = η_th,g · F_g[t]    ∀g ∈ G, t ∈ T
```

**Co-generation (CHP):**
```
P_el,g[t] = η_el,g · F_g[t]    ∀g ∈ G_CHP, t ∈ T
```

**Capacity limits:**
```
Q_g[t] ≤ cap_g · y_on,g[t]    ∀g ∈ G, t ∈ T
```

### 5.4 Heat Pump Constraints

**COP relationship:**
```
Q_hp[t] = COP[t] · P_hp[t]    ∀hp ∈ HP, t ∈ T
```

**Capacity constraints with minimum load:**
```
Q_hp[t] ≤ cap_hp                          ∀t ∈ T
Q_hp[t] ≥ λ_min · cap_hp · y_on[t]       ∀t ∈ T
Q_hp[t] ≤ cap_max · y_on[t]              ∀t ∈ T
```

Where λ_min is the minimum part-load ratio.

**COP Calculation:**

The coefficient of performance is calculated based on source and sink temperatures:
```
COP = η_Carnot · T_sink / (T_sink - T_source)
```

With practical efficiency factor η_Carnot ≈ 0.5-0.6.

### 5.5 Storage Constraints

**State of charge dynamics:**
```
E[t] = E[t-1] · (1 - λ_loss) + (η_c · Q_c[t] - Q_d[t]/η_d) · Δt    ∀t ∈ T
```

**Capacity limits:**
```
E[t] ≤ E_cap                    ∀t ∈ T
Q_c[t] ≤ P_cap                  ∀t ∈ T
Q_d[t] ≤ P_cap                  ∀t ∈ T
```

**Mode exclusivity:**
```
Q_c[t] ≤ P_cap · y_charge[t]           ∀t ∈ T
Q_d[t] ≤ P_cap · (1 - y_charge[t])     ∀t ∈ T
```

### 5.6 Investment Constraints

**Capacity bounds linked to build decision:**
```
cap_min · y_build ≤ cap ≤ cap_max · y_build
```

This ensures:
- If y_build = 0: cap = 0 (not built)
- If y_build = 1: cap_min ≤ cap ≤ cap_max (built with minimum size)

## 6. Objective Function

Minimize total system cost:

```
min Z = C_fuel + C_elec + C_CO2 + C_dump + C_demand + C_invest
```

### 6.1 Fuel Costs
```
C_fuel = ∑_{t∈T} ∑_{g∈G} p_f(g) · F_g[t] · Δt
```

### 6.2 Electricity Costs
```
C_elec = ∑_{t∈T} [(p_el[t] + c_grid) · P_buy[t] - p_el[t] · P_sell[t]] · Δt
```

### 6.3 CO₂ Costs
```
C_CO2 = p_CO2 · ∑_{t∈T} [∑_{g∈G} ef_f(g) · F_g[t] + ef_grid[t] · P_buy[t]] · Δt / 1000
```

### 6.4 Investment Costs (Annualized)
```
C_invest = ∑_{c∈Components} (CAPEX_c · cap_c + c_act,c · y_build,c) · (T_horizon / L_c)
```

Where T_horizon is the optimization horizon as fraction of a year.

## 7. Thermal Network Model

### 7.1 Heat Loss Calculation

For brownfield networks with known pipe parameters:

```
Q_loss,pipe = U · L · (T_supply - T_ambient) / 1000  [MW]
```

| Parameter | Unit | Description |
|-----------|------|-------------|
| U | W/(m·K) | Overall heat transfer coefficient |
| L | m | Pipe length |
| T_supply | K | Supply temperature |
| T_ambient | K | Ground/ambient temperature |

### 7.2 Total Network Loss

```
Q_loss[t] = ∑_{pipe} Q_loss,pipe    ∀t ∈ T
```

For brownfield mode with constant temperatures, losses are time-invariant.

## 8. Stratified Storage Model (Optional)

For large thermal storage (>100 MWh), a two-zone stratified model is available:

### 8.1 Temperature Zones

- **Hot zone**: Volume V_hot at temperature T_hot
- **Cold zone**: Volume V_cold at temperature T_cold

### 8.2 Energy Content
```
E = ρ · c_p · V_hot · (T_hot - T_cold) / 3.6e9  [MWh]
```

### 8.3 Geometry-Based Losses

Surface area calculation for cylindrical tank:
```
A_surface = 2π · r² + 2π · r · h
```

Heat loss through insulation:
```
Q_loss = U_tank · A_surface · (T_avg - T_ambient)
```

## 9. Solver Configuration

The model uses Pyomo as algebraic modeling language with:

- **Primary solver**: Gurobi (recommended for large problems)
- **Fallback solver**: GLPK (open-source alternative)

### 9.1 Solver Parameters

```yaml
run:
  solver: gurobi
  solver_options:
    Threads: 0      # Use all available cores
    MIPGap: 0.01    # 1% optimality gap tolerance
    TimeLimit: 3600 # Maximum solve time [s]
```

## 10. References

1. Lund, H., et al. (2014). "4th Generation District Heating (4GDH)". Energy, 68, 1-11.
2. Münster, M., et al. (2012). "The role of district heating in the future Danish energy system". Energy, 48(1), 47-55.
3. Connolly, D., et al. (2014). "Heat Roadmap Europe: Combining district heating with heat savings to decarbonise the EU energy system". Energy Policy, 65, 475-489.
