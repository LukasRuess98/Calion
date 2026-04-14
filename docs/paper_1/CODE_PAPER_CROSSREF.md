# CALION — Code-to-Paper Cross-Reference

> **Purpose:** Ground-truth document for AI-assisted paper verification.
> For each model equation in the paper, this file gives:
> - The canonical paper notation (from `model_equations_and_sources.md`)
> - The exact code location that implements it
> - The mapping of paper symbols → Python/Pyomo variable names
> - Known discrepancies, simplifications, or caveats
>
> An AI agent should compare the paper's mathematical description against the
> "Implementation" column in each table. Any mismatch is a potential error in the paper.

---

## How to Use This Document (for AI agents)

1. Read the paper section under review.
2. Find the corresponding section below.
3. Check: does the paper equation match the "Paper Notation" column?
4. Check: does the paper description match the "Implementation" column?
5. Flag mismatches in notation, sign conventions, units, or missing constraints.

---

## 1. Problem Class

| Aspect | Paper | Implementation |
|--------|-------|----------------|
| Problem type | MILP | Pyomo `ConcreteModel` with `Binary` + `NonNegativeReals` domains |
| Solver | Gurobi (fallback GLPK) | `calion/run/solver.py` |
| Horizon | T timesteps, Δt = 1 h | `Tset = RangeSet(1, T)` in `calion/models/system_builder.py` |
| Optimization modes | Perfect Foresight (PF), Rolling Horizon (RH) | `calion/run/workflow.py`, `calion/run/rolling_horizon.py` |

---

## 2. Objective Function

**Paper equation:**
$$\min Z = C_{\text{energy}} + C_{\text{fuel}} + C_{\text{dump}} + C_{\text{CO}_2} + C_{\text{demand}} + C_{\text{CAPEX}} + C_{\text{act}} + C_{\text{tie}}$$

**Implementation:** `calion/models/cost_calculator.py` + `calion/models/investment_calculator.py`

### 2.1 Energy Cost

| Symbol | Description | Code variable / expression |
|--------|-------------|---------------------------|
| $P_{\text{buy},t}$ | Grid electricity purchase [MW] | `model.P_buy[t]` |
| $P_{\text{sell},t}$ | Electricity sold to grid [MW] | `model.P_sell[t]` |
| $\lambda^{\text{buy}}_t$ | Buy price [EUR/MWh] | `buy_price[idx]` = spot + `energy_fee` + `grid_cost` |
| $\lambda^{\text{sell}}_t$ | Sell price [EUR/MWh] | `sell_price[idx]` = f(spot, haircut, spread, floor, fee, premium) |
| $\Delta t$ | Timestep [h] | `dt_h` parameter |

**Code (cost_calculator.py:71–75):**
```python
energy_cost = sum(
    dt_h * (model.P_buy[t] * buy_price[idx] - model.P_sell[t] * sell_price[idx])
    for idx, t in enumerate(time_steps)
)
```

**Sell price formula (cost_calculator.py:56–66):**
```python
price = max(bp - sell_spread, sell_floor)
price = price * max(0.0, 1.0 - sell_haircut)
price = price - sell_fee + sell_premium
return max(price, 0.0)
```

> **Agent check:** Paper should state that sell price uses a floor (`sell_floor`), a
> haircut (`sell_haircut`), a spread (`sell_spread`), and optional fee/premium.
> If paper shows a simpler formula (e.g., only haircut), flag as incomplete.

### 2.2 Peak Demand Charge

| Symbol | Code variable |
|--------|--------------|
| $\lambda_{\text{demand}}$ [EUR/MW/a] | `model.demand_charge_y` |
| $P_{\text{buy}}^{\text{peak}}$ | `model.P_buy_peak` (Pyomo Var) |
| year fraction | `model.year_frac` = T·Δt / 8760 |

**Code (cost_calculator.py:129):**
```python
return model.demand_charge_y * model.year_frac * model.P_buy_peak
```

### 2.3 CAPEX Annualization

| Symbol | Description | Code |
|--------|-------------|------|
| $\alpha = \tau / L$ | Annualization factor | `annual_factor()` in `investment_calculator.py:102–112` |
| $\tau$ | Period fraction = T·Δt/8760 | `period_frac` |
| $L$ | Component lifetime [a] | `lifetime_years` |

**Formula used (simplified straight-line, NOT annuity):**
$$C_{\text{CAPEX,period}} = \frac{\text{CAPEX}_{\text{EUR/MW}} \cdot \hat{Q}}{L} \cdot \tau$$

> **Agent check:** If the paper uses an annuity factor
> $\frac{r(1+r)^L}{(1+r)^L - 1}$ (with discount rate $r$),
> this does NOT match the code. The code uses straight-line depreciation
> (`CAPEX / lifetime * period_frac`). Flag if paper claims annuity.

**Code (investment_calculator.py:138):**
```python
terms.capex.append(capacity_var * config.capex_eur_per_mw * af)
```
where `af = period_frac / lifetime_years`.

---

## 3. Energy Bus Constraints

**Implementation:** `calion/models/constraint_builder.py`

### 3.1 Heat Bus (Single-Node / Copperplate)

**Paper:**
$$\sum_{i \in \mathcal{G}_{\text{th}}} Q^{\text{out}}_{i,t} = Q^{\text{demand}}_t + Q^{\text{dump}}_t + \sum_{j \in \mathcal{S}} Q^{\text{charge}}_{j,t} + Q^{\text{net\,loss}}_t$$

| Symbol | Code variable |
|--------|--------------|
| $Q^{\text{out}}_{i,t}$ | Pyomo outputs summed into `heat_bus` |
| $Q^{\text{demand}}_t$ | `model.Q_demand[t]` (Param from timeseries) |
| $Q^{\text{dump}}_t$ | `model.Q_dump[t]` (Var, NonNegativeReals) |
| $Q^{\text{charge}}_{j,t}$ | `{storage}_Qc[t]` for each storage block |
| $Q^{\text{net\,loss}}_t$ | Pipe loss (Param, precomputed) for L2/L3; = 0 for L1 |

### 3.2 Electricity Bus

**Paper:**
$$P^{\text{buy}}_t + \sum_{i \in \mathcal{G}_{\text{el}}} P^{\text{el,out}}_{i,t} = \sum_{j \in \mathcal{C}_{\text{el}}} P^{\text{el,in}}_{j,t} + P^{\text{sell}}_t$$

| Symbol | Code variable |
|--------|--------------|
| $P^{\text{buy}}_t$ | `model.P_buy[t]` |
| $P^{\text{el,out}}_{i,t}$ | `{chp}_Pel[t]` for CHP units |
| $P^{\text{el,in}}_{j,t}$ | `{hp}_Pel[t]` (Expression), `{p2h}_Pel[t]` |
| $P^{\text{sell}}_t$ | `model.P_sell[t]` |

---

## 4. Heat Pump Model

**Implementation:** `calion/models/blocks/heat_pump.py`

### Symbol–Variable Mapping

| Paper symbol | Pyomo variable / param | Description |
|-------------|----------------------|-------------|
| $Q_t$ | `{hp}_Q[t]` | Total heat output [MW] |
| $Q^{\text{WRG}}_t$ | `{hp}_Q_wrg[t]` | Heat from waste-heat recovery source |
| $Q^{\text{def}}_t$ | `{hp}_Q_def[t]` | Heat from default (ambient) source |
| $\text{COP}_t$ | `{hp}_COP[t]` (Param, time-varying) | COP for WRG source |
| $\text{COP}_{\text{default}}$ | `{hp}_COP_default` (Param, scalar) | COP for ambient source |
| $P^{\text{el}}_t$ | `{hp}_Pel` (Expression) | Electricity consumption [MW] |
| $\hat{Q}$ | `{hp}_cap_mw` (Var) | Installed capacity [MW] |
| $u_t$ | `{hp}_on[t]` (Binary Var) | Operating mode indicator |
| $y$ | `{hp}_build` (Binary Var) | Investment decision |
| $\phi_{\min}$ | `{hp}_minload` (Param) | Minimum load fraction |
| $\hat{Q}_{\min}$ | `{hp}_cap_min` (Param) | Min investable capacity |
| $\hat{Q}_{\max}$ | `{hp}_cap_max` (Param) | Max investable capacity |

### Constraints (heat_pump.py:111–135)

| Tag | Paper eq. | Code constraint name | Code line |
|-----|-----------|---------------------|-----------|
| HP-1 | $Q_t = Q^{\text{WRG}}_t + Q^{\text{def}}_t$ | `{hp}_split_balance` | line 119–121 |
| HP-2 | $P^{\text{el}}_t = Q^{\text{WRG}}_t / \text{COP}_t + Q^{\text{def}}_t / \text{COP}_{\text{default}}$ | `{hp}_Pel` (Expression) | line 123–126 |
| HP-3 | $Q_t \leq \hat{Q} \cdot u_t$ | `{hp}_cap` | line 111–113 |
| HP-4 | $Q_t \geq \phi_{\min} \cdot \hat{Q} \cdot u_t$ | `{hp}_min` | line 115–117 |
| HP-5 | $\hat{Q} \leq \hat{Q}_{\max} \cdot y$ | `{hp}_cap_hi` | line 129–131 |
| HP-6 | $\hat{Q} \geq \hat{Q}_{\min} \cdot y$ | `{hp}_cap_lo` | line 133–135 |
| HP-7 | $u_t \leq y$ | `{hp}_mode_link` | line 137–139 |

### Unit-Commitment Extensions (heat_pump.py:141–187)

Only active when `min_uptime_h > 0` or `min_downtime_h > 0`.

| Variable | Code variable | Description |
|----------|--------------|-------------|
| $u_t^+$ (startup) | `{hp}_u[t]` | 1 if starts at t |
| $v_t^-$ (shutdown) | `{hp}_v[t]` | 1 if stops at t |

State transition: $y_t - y_{t-1} = u_t - v_t$ → `{hp}_state_transition`

> **Agent check:** If paper mentions min-uptime/downtime constraints, verify these
> formulations match. If paper does NOT mention them, note that the code supports
> them but they are disabled by default (L=0, D=0).

---

## 5. COP Calculation

**Implementation:** `calion/models/cop_calculator.py`

### 5.1 Analytical Model (cop_calculator.py:184–235)

**Paper equation (COP-1):**
$$\text{COP} = A \cdot B \cdot \eta \cdot (1 - q_{ww}) + (1 - \eta) - F_Q$$

| Symbol | Code variable | Typical value |
|--------|--------------|---------------|
| $L_s$ | `Ls = _lmtd(Ts_out, Ts_in)` | — |
| $L_{\text{src}}$ | `Lsrc = _lmtd(Tin, Tout_i)` | — |
| $\eta$ | `eta` from `types[hp_type].eta` | 0.75 |
| $F_Q$ | `FQ` from `types[hp_type].FQ` | 0.10 |
| $\Delta T_{\text{pp}}$ | `dTpp` from `cop.deltaTpp_K` | 5 K |
| $q_{ww}$ | computed inline: `0.0014*(Ts_out-Tout_i+2*dTpp) - 0.0015*(Ts_out-Ts_in) + 0.039` | — |
| $\delta_s$ | `mdts = 0.2*(Ts_out-Tout_i+2*dTpp) + 0.2*(Ts_out-Ts_in) + 0.016` | — |

**LMTD (cop_calculator.py:321–346):**
$$\text{LMTD}(T_h, T_c) = \frac{T_h - T_c}{\ln(T_h / T_c)}$$
Fallback to arithmetic mean when $T_h \approx T_c$.

> **Agent check:** The $q_{ww}$ and $\delta_s$ formulas are semi-empirical and NOT
> standard Carnot expressions. If the paper presents a simplified COP formula
> (e.g., pure Carnot fraction), this is an approximation. Flag if paper
> presents this as exact.

### 5.2 Lookup-Table Model (cop_calculator.py:81–181)

2D bilinear interpolation over (source temp, sink temp) grid.
COP clamped to `[COP_MIN=0.5, COP_MAX=15.0]` (constants.py).

> **Agent check:** Paper should state which COP method is active in each scenario.
> Table-based = manufacturer data; analytical = theoretical model.

---

## 6. Thermal Storage

**Implementation:** `calion/models/blocks/storage.py`

### Symbol–Variable Mapping

| Paper symbol | Pyomo variable / param | Description |
|-------------|----------------------|-------------|
| $E_t$ | `{sto}_E[t]` | Stored energy / SoC [MWh] |
| $Q^{\text{c}}_t$ | `{sto}_Qc[t]` | Charge power [MW] |
| $Q^{\text{d}}_t$ | `{sto}_Qd[t]` | Discharge power [MW] |
| $\eta_c$ | `{sto}_effc[t]` (Param, time-indexed) | Charge efficiency |
| $\eta_d$ | `{sto}_effd[t]` (Param, time-indexed) | Discharge efficiency |
| $\sigma_t$ | `{sto}_loss[t]` (Param) | Self-discharge factor per timestep |
| $\hat{E}$ | `{sto}_cap_energy` (Var) | Energy capacity [MWh] |
| $\hat{P}$ | `{sto}_cap_power` (Var) | Power capacity [MW] |
| $y$ | `{sto}_build` (Binary Var) | Investment decision |
| $a_t$ | `{sto}_active[t]` (Binary Var) | Storage active indicator |
| $c_t$ | `{sto}_charge_mode[t]` (Binary Var) | Charging mode |
| $d_t$ | `{sto}_discharge_mode[t]` (Binary Var) | Discharging mode |

### Constraints (storage.py:170–239)

| Description | Paper eq. | Code constraint | Code line |
|-------------|-----------|----------------|-----------|
| SoC dynamics | $E_t = E_{t-1} \cdot \sigma_t + \eta_c \cdot Q^c_t \cdot \Delta t - \frac{Q^d_t \cdot \Delta t}{\eta_d}$ | `{sto}_soc` | line 232–237 |
| Energy bound (upper) | $E_t \leq \hat{E} \cdot a_t$ | `{sto}_ecap_hi` | line 170–171 |
| Energy bound (lower) | $E_t \geq E_{\min} \cdot a_t$ | `{sto}_ecap_lo` | line 173–174 |
| Charge power limit | $Q^c_t \leq \hat{P} \cdot c_t$ | `{sto}_pcap_c` | line 179–180 |
| Discharge power limit | $Q^d_t \leq \hat{P} \cdot d_t$ | `{sto}_pcap_d` | line 182–183 |
| Mutual exclusivity | $c_t + d_t \leq a_t$ | `{sto}_mode_cap` | line 198–199 |
| Capacity investment (upper) | $\hat{E} \leq \hat{E}_{\max} \cdot y$ | `{sto}_capE_hi` | line 204–206 |
| Power-energy coupling | $\hat{P} \leq \kappa \cdot \hat{E}$ | `{sto}_capP_coupling` | line 224–230 |

**SoC initial condition:** $E_0$ = `soc0` parameter; if `soc0 > 0`, constraint `{sto}_soc0_cap` ensures $E_0 \leq \hat{E}$.

**Terminal constraint:** NOT set here — set by `system_builder.py:685–699` based on `terminal_policy` config.

**Self-discharge implementation (storage.py:141):**
```python
loss_map = {idx: float(val) ** self.dt_h for idx, val in loss_base.items()}
```
So $\sigma_t = \sigma_{\text{hourly}}^{\Delta t}$ — the hourly loss factor raised to the power of the timestep duration.

> **Agent check:** If paper states $E_t = E_{t-1}(1 - \sigma) + \ldots$, note that
> the code uses multiplicative form $E_t = E_{t-1} \cdot \sigma$ where $\sigma < 1$
> is the retention factor (not the loss rate). These are equivalent but notation
> must match. Also: efficiency is time-variable in code (series support) but
> paper may describe it as constant.

---

## 7. Thermal Generator / CHP

**Implementation:** `calion/models/blocks/thermal_gen.py`

### Symbol–Variable Mapping

| Paper symbol | Pyomo variable / param | Description |
|-------------|----------------------|-------------|
| $Q^{\text{th}}_{g,t}$ | `{gen}_Qth[t]` | Thermal output [MW] |
| $F_{g,t}$ | `{gen}_fuel[t]` | Fuel consumption [MW_fuel] |
| $\eta_{\text{th}}$ | `{gen}_th_eff` (Param) | Thermal efficiency |
| $\hat{Q}^{\text{th}}_g$ | `{gen}_Qmax` (Param) | Thermal capacity [MW] |
| $P^{\text{el}}_{g,t}$ | `{gen}_Pel[t]` (Var, CHP only) | Electrical output [MW] |
| $\eta_{\text{el}}$ | `{gen}_el_eff` (Param, CHP only) | Electrical efficiency |

### Constraints (thermal_gen.py:32–51)

| Description | Equation | Code constraint |
|-------------|----------|----------------|
| Thermal output | $Q^{\text{th}}_{g,t} = \eta_{\text{th}} \cdot F_{g,t}$ | `{gen}_thlink` |
| Capacity limit | $Q^{\text{th}}_{g,t} \leq \hat{Q}^{\text{th}}_g$ | `{gen}_cap` |
| CHP electrical output | $P^{\text{el}}_{g,t} = \eta_{\text{el}} \cdot F_{g,t}$ | `{gen}_ellink` |

> **Agent check:** The CHP model uses fixed heat-to-power ratio (back-pressure turbine
> type). If paper describes extraction turbines or variable power-to-heat ratio,
> this does NOT match the code — flag as discrepancy.

---

## 8. Pipe Heat Loss / Network Physics

**Implementation:** `calion/models/network_physics.py`

### Heat Loss Formula

**Paper:**
$$Q_{\text{loss}} = U \cdot L \cdot (T_{\text{fluid}} - T_{\text{ground}}) \quad [\text{W}]$$

**Code (network_physics.py:59–72):**
```python
def pipe_heat_loss_mw(U_w_per_m_k, length_m, T_fluid_c, T_ground_c):
    delta_T = T_fluid_c - T_ground_c
    return U_w_per_m_k * length_m * delta_T / 1e6
```

| Symbol | Code variable | Unit |
|--------|--------------|------|
| $U$ | `U_w_per_m_k` | W/(m·K) |
| $L$ | `length_m` | m |
| $T_{\text{fluid}}$ | `T_fluid_c` | °C |
| $T_{\text{ground}}$ | `T_ground_c` | °C |
| $Q_{\text{loss}}$ | return value | MW |

> **Agent check:** Loss is computed for supply and return pipes separately (both use same formula,
> different U-values and temperatures). Total = supply + return.
> If paper states a single combined formula, verify it accounts for both.

### Heating Curve (Supply Temperature)

**Code (network_physics.py:241–299):**
$$T_{\text{supply}} = T_{\text{supply,min}} + (T_{\text{supply,max}} - T_{\text{supply,min}}) \cdot \frac{T_{\text{outdoor,high}} - T_{\text{outdoor}}}{T_{\text{outdoor,high}} - T_{\text{outdoor,low}}}$$

| Symbol | Parameter name | Default |
|--------|---------------|---------|
| $T_{\text{supply,min}}$ | `T_supply_min_c` | 80 °C |
| $T_{\text{supply,max}}$ | `T_supply_max_c` | 120 °C |
| $T_{\text{outdoor,high}}$ | `T_outdoor_high_c` | 20 °C |
| $T_{\text{outdoor,low}}$ | `T_outdoor_low_c` | −10 °C |

Result clamped to $[T_{\text{supply,min}}, T_{\text{supply,max}}]$.

---

## 9. Investment Model

**Implementation:** `calion/models/investment_calculator.py`

### CAPEX Terms

| Component | Energy CAPEX | Power CAPEX | Activation | Tie-breaker |
|-----------|-------------|------------|------------|-------------|
| Heat pump | `capex_eur_per_mw * cap_mw * af` | — | `activation_cost_eur * build * af` | `tie_breaker_eur_per_mw * cap_mw` |
| Storage | `energy_capex_eur_per_mwh * cap_e * af` | `power_capex_eur_per_mw * cap_p * af` | `activation_cost_eur * build * af` | `tie_breaker_eur_per_mwh * cap_e` |

**Note on tie-breaker:** NOT annualized (`af` not applied). Small constant that helps solver
choose non-zero capacities without oscillating. Should NOT appear in paper as a real cost.

> **Agent check:** If paper includes tie-breaker in cost breakdown, flag — this is a
> numerical artifact, not a physical/economic cost.

---

## 10. CO2 Emissions

**Implementation:** `calion/models/emissions_calculator.py`, `calion/models/cost_calculator.py`

### Emission Categories

| Category | Code | Description |
|----------|------|-------------|
| Fuel → heat | `co2_kg_fuel_to_heat` | Boilers, biomass: $\text{EF}_f \cdot F_{g,t}$ |
| Fuel → electricity (CHP) | `co2_kg_fuel_to_elec` | CHP electrical share |
| Grid → electricity | `co2_kg_grid_to_elec` | Heat pumps, P2H: $\text{EF}_{\text{grid},t} \cdot P^{\text{el}}_t$ |

**Assignment logic (cost_calculator.py:287–297):**
- `heat_pump`, `p2h` → grid emissions
- `thermal_generator` (no el_eff) → fuel-to-heat
- `chp` (`thermal_generator` with el_eff) → split between heat and elec shares

> **Agent check:** If paper assigns grid emissions from heat pumps to a different
> category (e.g., "operational emissions" vs "system emissions"), verify consistency
> with this three-category split.

---

## 11. Optimization Levels (L1 / L2 / L3)

These are scenario configurations, not separate code modules.

| Level | Config file | Network model | COP model | Storage |
|-------|-------------|--------------|-----------|---------|
| L1 (Copperplate) | `configs/paper/L1_copperplate_dispatch.yaml` | Single heat bus, no pipe losses | Fixed COP series | Simple storage |
| L2 (Simplified) | `configs/paper/L2_simplified_dispatch.yaml` | Pipe losses as fixed Param | Analytical COP | Simple storage |
| L3 (Detailed) | `configs/paper/L3_detailed_dispatch.yaml` | Per-node balances, full physics | Table-based COP | Stratified storage |

> **Agent check:** Paper must clearly state which level is used for which result.
> Results from L1 are NOT comparable to L3 without adjustment for network losses.

---

## 12. Known Code–Paper Gaps / Caveats

| # | Issue | Severity |
|---|-------|----------|
| 1 | Annualization is straight-line (`CAPEX/L`), not annuity formula | Medium — affects quantitative comparison with other papers |
| 2 | Sell price includes 5 parameters (haircut, spread, floor, fee, premium) — paper may simplify | Low if documented in footnote |
| 3 | COP $q_{ww}$ and $\delta_s$ are semi-empirical with inline coefficients (0.0014, 0.0015, 0.039, 0.2, 0.016) — not standard textbook | Medium — scientific source must be cited |
| 4 | Self-discharge: multiplicative factor $\sigma^{\Delta t}$, not additive rate | Low — equivalent but must use same notation |
| 5 | Terminal SoC constraint policy (equal / ≥) set at system_builder level, not in storage block | Low — must state policy used in experiments |
| 6 | Tie-breaker costs in objective are numerical artifacts — should NOT be in paper's cost equation | High if paper includes them |
| 7 | Min-uptime/downtime UC constraints exist in code but disabled at L1/L2 — paper may not mention them | Low |
| 8 | CHP uses fixed heat-power ratio (back-pressure) — extraction turbines not modeled | High if paper claims variable ratio |
