# Mathematical Model Documentation — EnerGIS District Heating Optimization Framework

> **Purpose:** This document catalogs all mathematical equations, physical models, and cost formulations
> implemented in EnerGIS, together with their scientific sources and assumptions.
> Intended as supporting material for academic publication.

---

## Table of Contents

1. [Model Overview and Problem Statement](#1-model-overview-and-problem-statement)
2. [Objective Function](#2-objective-function)
3. [Energy Bus Balance Constraints](#3-energy-bus-balance-constraints)
4. [Heat Pump Model](#4-heat-pump-model)
5. [COP Calculation](#5-cop-calculation)
6. [Thermal Storage Model](#6-thermal-storage-model)
7. [Power-to-Heat (P2H) Model](#7-power-to-heat-p2h-model)
8. [Thermal Generator and CHP Model](#8-thermal-generator-and-chp-model)
9. [Pipe Heat Loss and Network Physics](#9-pipe-heat-loss-and-network-physics)
10. [Heat Exchanger Model](#10-heat-exchanger-model)
11. [Electricity Market Model](#11-electricity-market-model)
12. [Investment and Annuity Model](#12-investment-and-annuity-model)
13. [CO2 Emissions Model](#13-co2-emissions-model)
14. [Sensitivity Analysis](#14-sensitivity-analysis)
15. [Notation Summary](#15-notation-summary)
16. [Scientific References](#16-scientific-references)

---

## 1. Model Overview and Problem Statement

EnerGIS solves a **Mixed-Integer Linear Program (MILP)** for the optimal dispatch and capacity expansion
of district heating systems. The formulation follows the *unit-commitment with investment decisions*
paradigm [1, 2]:

$$\min_{x \in \mathcal{X}} \; c^\top x \quad \text{s.t.} \quad Ax \leq b, \; x \in \{0,1\}^p \times \mathbb{R}^q_{\geq 0}$$

where $\mathcal{X}$ encodes:
- **Binary** variables: component investment decisions $y_i \in \{0,1\}$ and operating-mode selectors
- **Continuous** variables: power flows, temperatures, stored energy, fuel consumption
- **Equality** constraints: energy balances (bus constraints)
- **Inequality** constraints: capacity limits, efficiency relationships, grid constraints

The model horizon spans $T$ timesteps of duration $\Delta t$ hours (typically hourly resolution for
annual optimization or sub-hourly for short-horizon studies).

**Key references:** Lund et al. [3], Connolly et al. [4], Henning & Palzer [5].

---

## 2. Objective Function

**Source file:** `energis/models/cost_calculator.py`, `energis/models/investment_calculator.py`

The model minimizes the total annualized system cost over the optimization horizon:

$$\min \; Z = C_{\text{energy}} + C_{\text{fuel}} + C_{\text{dump}} + C_{\text{CO}_2} + C_{\text{demand}} + C_{\text{CAPEX}} + C_{\text{act}} + C_{\text{tie}}$$

### 2.1 Energy Cost (Grid Electricity)

$$C_{\text{energy}} = \Delta t \sum_{t=1}^{T} \left[ P_{\text{buy},t} \cdot \lambda^{\text{buy}}_t - P_{\text{sell},t} \cdot \lambda^{\text{sell}}_t \right] \quad [\text{EUR}]$$

Buy price:
$$\lambda^{\text{buy}}_t = \lambda^{\text{spot}}_t + \lambda^{\text{grid}} + \lambda^{\text{levy}} \quad [\text{EUR/MWh}]$$

Sell price (reflecting market haircut and floor price):
$$\lambda^{\text{sell}}_t = \max\!\left(\lambda^{\text{spot}}_t \cdot (1 - h_{\text{haircut}}) - \lambda^{\text{spread}},\; \lambda^{\text{floor}}\right) \quad [\text{EUR/MWh}]$$

**Assumption:** The *haircut* fraction $h_{\text{haircut}}$ represents market transaction costs and
bilateral contract discounts; typical values 2–10 % [6].

### 2.2 Fuel Cost

$$C_{\text{fuel}} = \Delta t \sum_{t=1}^{T} \sum_{f \in \mathcal{F}} F_{f,t} \cdot \lambda_f \quad [\text{EUR}]$$

where $\mathcal{F}$ is the set of fuel types (natural gas, biomass, waste heat), $F_{f,t}$ [MW] is
fuel consumption, and $\lambda_f$ [EUR/MWh] is the fuel price.

### 2.3 Heat Dump Penalty

$$C_{\text{dump}} = \Delta t \sum_{t=1}^{T} Q^{\text{dump}}_t \cdot \lambda_{\text{dump}} \quad [\text{EUR}]$$

The dump cost $\lambda_{\text{dump}}$ is a penalty term ensuring that curtailed heat is minimized;
it does not represent a physical cost but guides the optimizer [7].

### 2.4 CO₂ Cost

See Section 13.

### 2.5 Peak Demand Charge

$$C_{\text{demand}} = \lambda_{\text{demand}} \cdot \frac{T \cdot \Delta t}{8760} \cdot P_{\text{buy}}^{\text{peak}} \quad [\text{EUR}]$$

where $\lambda_{\text{demand}}$ [EUR/MW/year] is the annual demand charge rate.

**Assumption:** German grid tariff structure (*Leistungspreis*) applied as a constant annual rate;
methodology follows [8].

### 2.6 CAPEX and Activation Cost

See Section 12.

---

## 3. Energy Bus Balance Constraints

**Source file:** `energis/models/constraint_builder.py`

### 3.1 Heat Bus (Copperplate / Single Node)

At every timestep $t$, total heat generation equals heat demand plus losses:

$$\sum_{i \in \mathcal{G}_{\text{th}}} Q^{\text{out}}_{i,t} = Q^{\text{demand}}_t + Q^{\text{dump}}_t + \sum_{j \in \mathcal{S}} Q^{\text{charge}}_{j,t} + Q^{\text{net\,loss}}_t \quad \forall t$$

where $\mathcal{G}_{\text{th}}$ = thermal generators (boilers, heat pumps, CHP, P2H, storage discharge),
$\mathcal{S}$ = thermal storage units.

**Physical interpretation:** Conservation of energy (first law of thermodynamics) applied at the
thermal bus [3, 9].

### 3.2 Electricity Bus

$$P^{\text{buy}}_t + \sum_{i \in \mathcal{G}_{\text{el}}} P^{\text{el,out}}_{i,t} = \sum_{j \in \mathcal{C}_{\text{el}}} P^{\text{el,in}}_{j,t} + P^{\text{sell}}_t \quad \forall t$$

where $\mathcal{G}_{\text{el}}$ = CHP units (electricity generation), $\mathcal{C}_{\text{el}}$ = electricity
consumers (heat pumps, P2H).

### 3.3 Per-Node Heat Balance (Multi-Node Networks)

**Producer node:**
$$\sum_{i} Q^{\text{out}}_{i,t} = Q^{\text{demand}}_t + Q^{\text{dump}}_t + \sum_j Q^{\text{charge}}_{j,t} + Q^{\text{pipe\,out}}_t - Q^{\text{pipe\,in}}_t + Q^{\text{net\,loss}}_t$$

**Consumer node:**
$$Q^{\text{pipe\,delivered}}_t + \sum_i Q^{\text{local,out}}_{i,t} = Q^{\text{demand}}_t + \sum_j Q^{\text{charge}}_{j,t}$$

These balance equations follow the nodal energy formulation of Analogus to Kirchhoff's current
law applied to energy networks [10, 11].

---

## 4. Heat Pump Model

**Source file:** `energis/models/blocks/heat_pump.py`

### 4.1 Heat Output Balance

The total heat output $Q_t$ from a heat pump is the sum of contributions from the waste-heat
recovery (WRG) source and the default (ambient or other) source:

$$Q_t = Q^{\text{WRG}}_t + Q^{\text{def}}_t \quad \forall t \tag{HP-1}$$

### 4.2 Electrical Power Consumption

$$P^{\text{el}}_t = \frac{Q^{\text{WRG}}_t}{\text{COP}_t} + \frac{Q^{\text{def}}_t}{\text{COP}_{\text{default}}} \quad \forall t \tag{HP-2}$$

**Derivation:** The definition of the Coefficient of Performance (COP) is:

$$\text{COP} = \frac{Q_{\text{th}}}{P_{\text{el}}} \implies P_{\text{el}} = \frac{Q_{\text{th}}}{\text{COP}}$$

With two heat sources at potentially different COPs, Eq. (HP-2) follows directly [12, 13].

### 4.3 Capacity Constraint

$$Q_t \leq \hat{Q} \cdot u_t \quad \forall t \tag{HP-3}$$

where $\hat{Q}$ is the installed thermal capacity [MW] and $u_t \in \{0,1\}$ is the operating
binary variable.

### 4.4 Minimum Load Constraint

$$Q_t \geq \phi_{\min} \cdot \hat{Q} \cdot u_t \quad \forall t \tag{HP-4}$$

where $\phi_{\min} \in [0,1]$ is the minimum load fraction. This constraint models the
technical minimum operation point of the heat pump compressor [14].

### 4.5 Investment Constraints (Capacity Expansion)

$$\hat{Q} \leq \hat{Q}_{\max} \cdot y \tag{HP-5}$$
$$\hat{Q} \geq \hat{Q}_{\min} \cdot y \tag{HP-6}$$
$$u_t \leq y \quad \forall t \tag{HP-7}$$

where $y \in \{0,1\}$ is the binary investment decision, and $\hat{Q}_{\min}, \hat{Q}_{\max}$
are the minimum and maximum investable capacities [1, 15].

**Formulation type:** Standard big-M disjunctive constraints; see Raman & Grossmann [16].

---

## 5. COP Calculation

**Source file:** `energis/models/cop_calculator.py`

### 5.1 Analytical Thermodynamic COP Model

The analytical COP model is based on the semi-empirical formula for electrically-driven
compression heat pumps, derived from second-law thermodynamic analysis [17, 18]:

$$\text{COP} = \underbrace{\frac{L_s}{L_s - L_{\text{src}}}}_{A} \cdot \underbrace{\frac{1 + (\delta_s + \Delta T_{\text{pp}}) / L_s}{1 + (\delta_s + 0.5(T_{\text{src,in}} - T_{\text{src,out}}) + 2\Delta T_{\text{pp}}) / (L_s - L_{\text{src}})}}_{B} \cdot \eta \cdot (1 - q_{ww}) + (1 - \eta) - F_Q \tag{COP-1}$$

where:
- $L_s$ = LMTD of heat sink [K]
- $L_{\text{src}}$ = LMTD of heat source [K]
- $\eta$ = Carnot efficiency factor (typical: 0.75) [−]
- $q_{ww}$ = auxiliary loss factor (compressor, fan, pump)
- $F_Q$ = fixed loss factor (typical: 0.10) [−]
- $\Delta T_{\text{pp}}$ = pinch-point temperature approach [K]
- $\delta_s$ = mean temperature approach parameter at sink

**Scientific basis:** The formula structure follows the approach of Staffell et al. [17] and
Ruhnau et al. [18], which parameterize real heat pump performance as a fraction of the
ideal Carnot COP, corrected for internal temperature approaches.

**Carnot COP reference:**

$$\text{COP}_{\text{Carnot}} = \frac{T_{\text{sink}}}{T_{\text{sink}} - T_{\text{source}}} \quad [K/K]$$

where temperatures are in Kelvin [19].

### 5.2 Log-Mean Temperature Difference (LMTD)

$$\text{LMTD}(T_h, T_c) = \frac{T_h - T_c}{\ln(T_h / T_c)} \tag{COP-2}$$

Limit (L'Hôpital): when $T_h \approx T_c$:

$$\text{LMTD} \approx \frac{T_h + T_c}{2} \quad \text{(arithmetic mean)}$$

**Standard reference:** Incropera et al. [20], Chapter 11.

### 5.3 COP Lookup-Table Model (2D Bilinear Interpolation)

When manufacturer data is available, COP is computed via bilinear interpolation over a
grid of source and sink temperatures:

$$\text{COP}(T_{\text{src}}, T_{\text{sink}}) = \sum_{i,j} w_{ij} \cdot \text{COP}_{ij}$$

where $w_{ij}$ are bilinear weights from the 2D table. Clamping:

$$\text{COP} \in [\text{COP}_{\min},\; \text{COP}_{\max}] = [0.5,\; 15.0]$$

**Reference:** EN 14825:2022 standard for heat pump performance testing [21].

---

## 6. Thermal Storage Model

**Source file:** `energis/models/blocks/storage.py`

### 6.1 Energy Balance (State-of-Charge Dynamics)

The discrete-time energy balance of a thermal storage unit follows:

$$E_t = E_{t-1} \cdot \lambda^{\Delta t} + \eta_c \cdot Q^c_t \cdot \Delta t - \frac{Q^d_t \cdot \Delta t}{\eta_d} \quad \forall t \tag{ST-1}$$

where:
- $E_t$ [MWh] = stored energy (state-of-charge) at timestep $t$
- $\lambda$ = self-discharge factor per hour [−], $\lambda = 1 - \dot{\lambda}_{\text{loss}}$
- $\lambda^{\Delta t}$ = self-discharge over one timestep (accounts for variable $\Delta t$)
- $\eta_c$ = charge efficiency [−]
- $\eta_d$ = discharge efficiency [−]
- $Q^c_t$ [MW] = charge power (heat input)
- $Q^d_t$ [MW] = discharge power (heat output)
- $\Delta t$ [h] = timestep duration

**Derivation:** Standard energy storage model with multiplicative self-discharge; see
Dunn et al. [22], Quoilin et al. [23], and Lund et al. [24].

**Note:** The model uses $\lambda^{\Delta t}$ rather than $\lambda \cdot \Delta t$ to correctly
represent exponential decay for variable timestep lengths.

### 6.2 Energy Capacity Constraints

$$E_t \leq \hat{E} \quad \forall t \tag{ST-2}$$
$$E_t \geq E_{\min} \quad \forall t \tag{ST-3}$$

where $\hat{E}$ [MWh] is the energy capacity (decision variable in expansion mode).

### 6.3 Power Capacity Constraints

$$Q^c_t \leq \hat{P} \cdot \xi^c_t \quad \forall t \tag{ST-4}$$
$$Q^d_t \leq \hat{P} \cdot \xi^d_t \quad \forall t \tag{ST-5}$$

where $\hat{P}$ [MW] is the power capacity and $\xi^c_t, \xi^d_t \in \{0,1\}$ are binary
charge/discharge mode indicators.

### 6.4 Simultaneous Charge/Discharge Prevention

$$\xi^c_t + \xi^d_t \leq a_t \quad \forall t \tag{ST-6}$$

where $a_t \in \{0,1\}$ is the storage activation variable.

**Physical justification:** Thermal storage cannot simultaneously absorb and release heat
(ignoring stratification effects). See Lund et al. [24].

### 6.5 Power-Energy Coupling (Optional)

$$\hat{P} \leq \kappa \cdot \hat{E} \tag{ST-7}$$

where $\kappa$ [MW/MWh = h⁻¹] is the C-rate coupling factor.

**Reference:** Common for sensible heat thermal energy storage (e.g., water tanks);
typical $\kappa$ values 0.1–1.0 [25].

### 6.6 Cyclic Boundary Condition

$$E_0 \leq \hat{E} \tag{ST-8}$$

The initial state-of-charge is a parameter $E_0$ that must not exceed capacity.

---

## 7. Power-to-Heat (P2H) Model

**Source file:** `energis/models/blocks/p2h.py`

### 7.1 Efficiency-Based Heat Output

$$Q_t = \eta_t \cdot P^{\text{el}}_t \quad \forall t \tag{P2H-1}$$

where $\eta_t$ [−] is the electrical-to-thermal conversion efficiency (≤ 1 for resistive
heating, > 1 not applicable — unlike heat pumps).

**Device types covered:** Electric boiler (immersion heater), electrode boiler, infrared heater.
Typical $\eta$ = 0.95–0.99 [26].

### 7.2 Capacity and Minimum Load

$$Q_t \leq \hat{Q} \cdot u_t \quad \forall t \tag{P2H-2}$$
$$Q_t \geq \phi_{\min} \cdot \hat{Q} \cdot u_t \quad \forall t \tag{P2H-3}$$

---

## 8. Thermal Generator and CHP Model

**Source file:** `energis/models/blocks/thermal_gen.py`

### 8.1 Boiler: Thermal Output from Fuel

$$Q^{\text{th}}_t = \eta^{\text{th}} \cdot F_t \quad \forall t \tag{GEN-1}$$

where $\eta^{\text{th}}$ is the net thermal efficiency (on lower heating value, LHV basis) and
$F_t$ [MW] is fuel input power.

**Typical values:** Gas condensing boiler $\eta^{\text{th}}$ = 0.90–1.05 (LHV), biomass boiler 0.80–0.90 [27].

### 8.2 CHP: Combined Outputs

For a combined heat and power unit, both heat and electricity are produced from the same
fuel input [28]:

$$Q^{\text{th}}_t = \eta^{\text{th}} \cdot F_t \quad \forall t \tag{GEN-2}$$
$$P^{\text{el}}_t = \eta^{\text{el}} \cdot F_t \quad \forall t \tag{GEN-3}$$

The total efficiency is:

$$\eta^{\text{total}} = \eta^{\text{th}} + \eta^{\text{el}}$$

**Assumption:** Fixed extraction CHP model (backpressure turbine). More sophisticated CHP
models with a *feasible operating region* (FOR) or *iso-fuel* lines are not currently implemented;
see Morales et al. [28] for the general formulation.

### 8.3 Capacity Constraint

$$Q^{\text{th}}_t \leq \hat{Q}^{\text{th}} \quad \forall t \tag{GEN-4}$$

---

## 9. Pipe Heat Loss and Network Physics

**Source file:** `energis/models/network_physics.py`, `energis/models/blocks/pipe_pair.py`

### 9.1 Steady-State Pipe Heat Loss

The heat loss per unit length of a buried insulated pipe (steady-state model):

$$\dot{q}_{\text{loss}} = U \cdot (T_{\text{fluid}} - T_{\text{ground}}) \quad [\text{W/m}]$$

Total heat loss for a pipe of length $L$:

$$Q_{\text{loss}} = U \cdot L \cdot (T_{\text{fluid}} - T_{\text{ground}}) \times 10^{-6} \quad [\text{MW}] \tag{PH-1}$$

where $U$ [W/(m·K)] is the linear heat transfer coefficient of the insulated pipe (combined
insulation + soil conductance).

**Scientific reference:** EN 13941-1:2019 [29], Frederiksen & Werner [30] §4.3.

**Supply and return separately:**

$$Q^{\text{loss}}_{\text{supply}} = U_s \cdot L \cdot (T_s - T_g) \times 10^{-6}$$
$$Q^{\text{loss}}_{\text{return}} = U_r \cdot L \cdot (T_r - T_g) \times 10^{-6}$$

### 9.2 Outlet Temperature After Heat Loss

Given inlet temperature $T_{\text{in}}$, pipe geometry, and mass flow $\dot{m}$:

$$Q_{\text{loss}} = U \cdot L \cdot (T_{\text{in}} - T_g) \times 10^{-3} \quad [\text{kW}]$$
$$\Delta T = \frac{Q_{\text{loss}}}{\dot{m} \cdot c_p} \quad [\text{K}]$$
$$T_{\text{out}} = T_{\text{in}} - \Delta T \tag{PH-2}$$

or in closed form:

$$T_{\text{out}} = T_g + (T_{\text{in}} - T_g) \cdot \exp\!\left(-\frac{U \cdot L}{\dot{m} \cdot c_p \cdot 1000}\right) \approx T_{\text{in}} - \frac{U \cdot L \cdot (T_{\text{in}} - T_g)}{\dot{m} \cdot c_p \cdot 1000}$$

**Note:** The exponential form is the exact solution for plug-flow with linear heat loss;
the linear approximation holds when $UL \ll \dot{m} c_p$ [31].

**Reference:** Benonysson et al. [31], Frederiksen & Werner [30] §4.5.

### 9.3 Mass Flow from Heat Delivery

The required mass flow $\dot{m}$ to deliver heat power $Q$ [kW] with supply/return temperature
difference $\Delta T$:

$$\dot{m} = \frac{Q}{c_p \cdot \Delta T} \quad [\text{kg/s}] \tag{PH-3}$$

where $c_p$ = 4.186 kJ/(kg·K) for water.

**Reference:** Standard heat transport equation [30].

### 9.4 Flow Velocity

$$v = \frac{\dot{m}}{\rho \cdot A} \quad [\text{m/s}], \quad A = \pi (d/2)^2 \quad [\text{m}^2] \tag{PH-4}$$

where $\rho$ ≈ 975 kg/m³ (hot water at ~70°C) and $d$ is inner pipe diameter [m].

### 9.5 MILP Linear Heat Delivery

In the MILP formulation, temperature is held at nominal values, linearizing the
temperature-dependent heat delivery:

$$Q^{\text{delivered}}_t \cdot 1000 = \dot{m}_t \cdot c_p \cdot \Delta T_{\text{nom}} \tag{PH-5}$$

**Assumption:** Fixed supply/return temperature difference (*$\Delta T$ assumption*); standard
in MILP district heating models [10, 32].

### 9.6 Heating Curve (Heizkurve)

Weather-compensated supply temperature control:

$$T_s(T_{\text{out}}) = T_{s,\min} + (T_{s,\max} - T_{s,\min}) \cdot \frac{T_{\text{out,design}} - T_{\text{out}}}{T_{\text{out,design}} - T_{\text{out,min}}} \tag{PH-6}$$

Linear equivalent: $T_s = \alpha + \beta \cdot T_{\text{out}}$, where:

$$\beta = -\frac{T_{s,\max} - T_{s,\min}}{T_{\text{out,design}} - T_{\text{out,min}}}$$

**Reference:** VDI 2067 [33], Frederiksen & Werner [30] §6.2.

### 9.7 Transport Delay (SOS2 Piecewise-Linear Approximation)

Flow-dependent thermal transport delay through pipes:

$$\tau(t) = \frac{L \cdot \rho \cdot A}{\dot{m}(t)} \quad [\text{s}] \tag{PH-7}$$

For the MILP model, the nonlinear function $\tau(\dot{m})$ is approximated using
Special Ordered Sets of type 2 (SOS2) with 3 breakpoints [34]:

| Bucket | Flow range | Delay |
|--------|-----------|-------|
| 0 (high flow) | $[\dot{m}_{\text{mid}}, \dot{m}_{\text{max}}]$ | $\tau_1$ (shortest) |
| 1 (medium flow) | $[\dot{m}_{\text{min}}, \dot{m}_{\text{mid}}]$ | $\tau_2$ |
| 2 (low flow) | $[0, \dot{m}_{\text{min}}]$ | $\tau_3$ (longest) |

**Reference:** SOS2 modeling [35]; transport delay in DH [36].

---

## 10. Heat Exchanger Model

**Source file:** `energis/models/blocks/heat_exchanger.py`

### 10.1 Energy Balances

Primary (hot) side:
$$Q^{\text{transfer}}_t \cdot 1000 = \dot{m}^{\text{prim}}_t \cdot c_p \cdot (T^{\text{prim,in}}_t - T^{\text{prim,out}}_t) \tag{HX-1}$$

Secondary (cold) side:
$$Q^{\text{transfer}}_t \cdot 1000 = \dot{m}^{\text{sec}}_t \cdot c_p \cdot (T^{\text{sec,out}}_t - T^{\text{sec,in}}_t) \tag{HX-2}$$

### 10.2 Effectiveness Constraint (Linearized)

For a counter-flow heat exchanger, the effectiveness $\varepsilon$ is:

$$\varepsilon = \frac{Q_{\text{actual}}}{Q_{\text{max}}} = \frac{T^{\text{sec,out}} - T^{\text{sec,in}}}{T^{\text{prim,in}} - T^{\text{sec,in}}}$$

Linearized as an upper bound:
$$T^{\text{sec,out}}_t \leq T^{\text{sec,in}}_t + \varepsilon \cdot (T^{\text{prim,in}}_t - T^{\text{sec,in}}_t) \tag{HX-3}$$

**Reference:** Incropera et al. [20] §11.4; NTU-effectiveness method.

### 10.3 Pinch Point Constraint (Big-M Formulation)

$$T^{\text{prim,out}}_t \geq T^{\text{sec,in}}_t + \Delta T_{\text{pp}} - M \cdot (1 - a_t) \tag{HX-4}$$

where $\Delta T_{\text{pp}}$ is the minimum approach temperature [K] and $M$ is a large constant.

**Physical meaning:** Second law of thermodynamics prevents temperature cross at the pinch point [20].

---

## 11. Electricity Market Model

**Source file:** `energis/models/constraint_builder.py`

### 11.1 Buy/Sell Exclusivity

$$P^{\text{buy}}_t \leq M_G \cdot g_t \quad \forall t \tag{EL-1}$$
$$P^{\text{sell}}_t \leq M_G \cdot (1 - g_t) \quad \forall t \tag{EL-2}$$

where $g_t \in \{0,1\}$ is the grid mode binary variable and $M_G$ is a big-M constant.

**Assumption:** The system is a price-taker on the electricity spot market; no market price
feedback from dispatch decisions [6, 37].

### 11.2 Connection Limits

$$P^{\text{buy}}_t \leq P^{\text{import,max}} \quad \forall t \tag{EL-3}$$
$$P^{\text{sell}}_t \leq P^{\text{export,max}} \quad \forall t \tag{EL-4}$$

### 11.3 Peak Demand Tracking

$$P^{\text{peak}} \geq P^{\text{buy}}_t \quad \forall t \tag{EL-5}$$

This linear constraint correctly identifies the maximum import for demand charge calculation
without requiring auxiliary binary variables [38].

---

## 12. Investment and Annuity Model

**Source file:** `energis/models/investment_calculator.py`

### 12.1 Annualization Factor

For an optimization horizon of $T$ timesteps with duration $\Delta t$ hours:

$$f_{\text{period}} = \frac{T \cdot \Delta t}{8760} \quad [\text{yr/yr}]$$

Annualized cost factor (equivalent annual cost, EAC):

$$f_{\text{ann}} = \frac{f_{\text{period}}}{\tau_{\text{life}}} \tag{INV-1}$$

where $\tau_{\text{life}}$ is the economic lifetime in years.

**Note:** The simplified annualization in Eq. (INV-1) assumes a discount rate of zero. For
non-zero discount rate $r$, the correct Capital Recovery Factor is:

$$\text{CRF}(r, n) = \frac{r(1+r)^n}{(1+r)^n - 1} \tag{INV-2}$$

**Reference:** VDI 2067 Part 1 [33], IRENA [39].

### 12.2 Component CAPEX

$$C_{\text{CAPEX},i} = \hat{Q}_i \cdot c^{\text{CAPEX}}_i \cdot f_{\text{ann}} \quad [\text{EUR}] \tag{INV-3}$$

where $c^{\text{CAPEX}}_i$ [EUR/MW] is the specific investment cost.

### 12.3 Activation Cost (Binary Investment)

$$C_{\text{act},i} = y_i \cdot c^{\text{act}}_i \cdot f_{\text{ann}} \quad [\text{EUR}] \tag{INV-4}$$

**Purpose:** Captures fixed costs independent of capacity (planning, grid connection, permits).

### 12.4 Storage Investment

Energy capacity cost:
$$C_{\text{E},j} = \hat{E}_j \cdot c^E_j \cdot f_{\text{ann}} \quad [\text{EUR/MWh}] \tag{INV-5}$$

Power capacity cost:
$$C_{\text{P},j} = \hat{P}_j \cdot c^P_j \cdot f_{\text{ann}} \quad [\text{EUR/MW}] \tag{INV-6}$$

### 12.5 Tie-Breaker Cost (Numerical Stability)

A small non-annualized cost $\epsilon \ll 1$ added per unit of capacity to break degeneracy:

$$C_{\text{tie},i} = \hat{Q}_i \cdot \epsilon_i \tag{INV-7}$$

**Purpose:** Avoids degenerate solutions where multiple capacity values yield identical objectives [40].

---

## 13. CO₂ Emissions Model

**Source file:** `energis/models/emissions_calculator.py`

### 13.1 Grid Electricity Emissions

$$\text{CO}_{2,\text{grid},t} = P^{\text{el}}_t \cdot e^{\text{grid}}_t \cdot \Delta t \quad [\text{kg}] \tag{CO2-1}$$

where $e^{\text{grid}}_t$ [kg CO₂/MWh] is the time-varying grid emission intensity (marginal or
average, depending on methodology).

**Annual CO₂ cost:**
$$C_{\text{CO}_2} = \frac{\lambda_{\text{CO}_2}}{1000} \cdot \sum_t \text{CO}_{2,t} \quad [\text{EUR}]$$

where $\lambda_{\text{CO}_2}$ [EUR/tonne CO₂] is the carbon price.

**Reference:** For marginal vs. average emission accounting debate, see Tranberg et al. [41],
Millar et al. [42].

### 13.2 Fuel Combustion Emissions

$$\text{CO}_{2,\text{fuel},t} = F_t \cdot e_f \cdot \Delta t \quad [\text{kg}] \tag{CO2-2}$$

where $e_f$ [kg CO₂/MWh_{fuel}] is the specific emission factor of fuel $f$ (LHV basis).

**Standard emission factors (IPCC 2006 [43]):**
- Natural gas: 201.6 kg CO₂/MWh (≈ 56 kg CO₂/GJ)
- Light heating oil: 266.4 kg CO₂/MWh
- Biomass (wood chips): 0 kg CO₂/MWh (carbon neutral, lifecycle considerations aside)

### 13.3 CHP Emission Allocation

For combined heat and power, total fuel emissions are allocated by output efficiency fractions:

$$\alpha_{\text{heat}} = \frac{\eta^{\text{th}}}{\eta^{\text{th}} + \eta^{\text{el}}}, \quad \alpha_{\text{el}} = \frac{\eta^{\text{el}}}{\eta^{\text{th}} + \eta^{\text{el}}} \tag{CO2-3}$$

$$\text{CO}_{2,\text{heat}} = \alpha_{\text{heat}} \cdot \text{CO}_{2,\text{total}}$$
$$\text{CO}_{2,\text{el}} = \alpha_{\text{el}} \cdot \text{CO}_{2,\text{total}}$$

**Reference:** This *efficiency method* is one of several allocation methods; alternatives include
the *IEA method* and *bonus method*. See Directive 2012/27/EU [44], Streckienė et al. [45].

### 13.4 CO₂ Resolution Analysis

The module `co2_resolution_analysis.py` evaluates sensitivity to temporal resolution of
grid CO₂ data [42]:

$$e^{\text{annual}} = \frac{\sum_t e^{\text{hourly}}_t \cdot \Delta t}{T \cdot \Delta t} \quad [\text{kg CO}_2/\text{MWh}]$$

Resolution scenarios: annual (1 factor), monthly (12), daily (365), hourly (8,760), 15-min (35,040).

**Reference:** Temporally resolved CO₂ analysis follows Millar et al. [42] and
Tranberg et al. [41].

---

## 14. Sensitivity Analysis

**Source file:** `energis/analysis/sensitivity.py`

### 14.1 Parameter Variation Modes

**Multiplicative variation:**
$$v_k = v_0 \cdot \mu_k \tag{SA-1}$$

**Absolute variation:**
$$v_k = v_0 + \delta_k \tag{SA-2}$$

where $v_0$ is the base-case parameter value, $\mu_k$ is the variation multiplier, and
$\delta_k$ is the additive increment.

### 14.2 Normalized Sensitivity Index

$$S_i = \frac{|\max_k Z(v_k) - \min_k Z(v_k)|}{Z(v_0)} \tag{SA-3}$$

where $Z(\cdot)$ is the objective value (total cost) and $v_0$ is the baseline parameter value.

**Physical meaning:** $S_i$ is the normalized range of objective variation due to parameter $i$;
analogous to a normalized first-order sensitivity coefficient [46].

**Reference:** Saltelli et al. [46] Chapter 1; one-at-a-time (OAT) sensitivity analysis.

### 14.3 Standard Sensitivity Parameters

| Parameter | Symbol | Base Value | Range |
|-----------|--------|-----------|-------|
| Gas price | $\lambda_{\text{gas}}$ | 58.6 EUR/MWh | ±20 % |
| Electricity price | $\lambda_{\text{el}}$ | 50 EUR/MWh | ±20 % |
| Heat pump COP factor | $\eta$ | 0.75 | ±5 % |
| P2H efficiency | $\eta_{\text{P2H}}$ | 0.99 | ±3 % |
| Storage hourly loss | $\dot{\lambda}$ | 0.05 %/h | ±50 % |
| Storage charge efficiency | $\eta_c$ | 0.98 | ±5 % |
| Storage discharge efficiency | $\eta_d$ | 0.98 | ±5 % |

---

## 15. Notation Summary

| Symbol | Unit | Description |
|--------|------|-------------|
| $T$ | − | Number of timesteps |
| $\Delta t$ | h | Timestep duration |
| $Q_t$ | MW | Thermal power |
| $P^{\text{el}}_t$ | MW | Electrical power |
| $F_t$ | MW | Fuel input power |
| $E_t$ | MWh | Stored energy |
| $\hat{Q}$ | MW | Installed thermal capacity |
| $\hat{E}$ | MWh | Installed energy capacity |
| $\hat{P}$ | MW | Installed power capacity |
| $u_t, \xi_t$ | − | Binary operating mode indicator |
| $y$ | − | Binary investment decision |
| $\text{COP}_t$ | − | Coefficient of performance |
| $\eta^{\text{th}}, \eta^{\text{el}}$ | − | Thermal / electrical efficiency |
| $\eta_c, \eta_d$ | − | Charge / discharge efficiency |
| $\lambda$ | − | Self-discharge factor per hour |
| $L$ | m | Pipe length |
| $U$ | W/(m·K) | Linear heat transfer coefficient |
| $\dot{m}$ | kg/s | Mass flow rate |
| $c_p$ | kJ/(kg·K) | Specific heat capacity (water: 4.186) |
| $T_s, T_r, T_g$ | °C | Supply / return / ground temperature |
| $e_f$ | kg CO₂/MWh | Fuel CO₂ emission factor |
| $e^{\text{grid}}_t$ | kg CO₂/MWh | Grid CO₂ intensity at timestep $t$ |
| $\lambda_{\text{CO}_2}$ | EUR/t CO₂ | Carbon price |
| $c^{\text{CAPEX}}$ | EUR/MW | Specific investment cost |
| $\tau_{\text{life}}$ | yr | Economic asset lifetime |
| $f_{\text{ann}}$ | − | Annualization factor |
| $M$ | − | Big-M constant (large number) |

---

## 16. Scientific References

### MILP Optimization and Energy Systems

[1] **Morales, J.M., Conejo, A.J., Madsen, H., Pinson, P., Zugno, M.** (2014).
*Integrating Renewables in Electricity Markets: Operational Problems*. Springer, New York.
ISBN 978-1-4614-9411-9.

[2] **Savelsbergh, M.** (1994). Preprocessing and probing techniques for mixed integer programming problems.
*ORSA Journal on Computing*, 6(4), 445–454. https://doi.org/10.1287/ijoc.6.4.445

[3] **Lund, H., Werner, S., Wiltshire, R., Svendsen, S., Thorsen, J.E., Hvelplund, F., Mathiesen, B.V.** (2014).
4th Generation District Heating (4GDH): Integrating smart thermal grids into future sustainable energy systems.
*Energy*, 68, 1–11. https://doi.org/10.1016/j.energy.2014.02.089

[4] **Connolly, D., Lund, H., Mathiesen, B.V., Werner, S., Möller, B., Persson, U., Boermans, T., Trier, D., Østergaard, P.A., Nielsen, S.** (2014).
Heat roadmap Europe: Combining district heating with heat savings to decarbonise the EU energy system.
*Energy Policy*, 65, 475–489. https://doi.org/10.1016/j.enpol.2013.10.035

[5] **Henning, H.M., Palzer, A.** (2014).
A comprehensive model for the German electricity and heat sector in a future energy system with a dominating contribution from renewable energy technologies — Part I: Methodology.
*Renewable and Sustainable Energy Reviews*, 30, 1003–1018. https://doi.org/10.1016/j.rser.2013.09.012

### Electricity Market and Grid Pricing

[6] **Kirschen, D., Strbac, G.** (2018).
*Fundamentals of Power System Economics* (2nd ed.). Wiley-Blackwell.
ISBN 978-1-119-02035-1.

[7] **Pfenninger, S., Hawkes, A., Keirstead, J.** (2014).
Energy systems modeling for twenty-first century energy challenges.
*Renewable and Sustainable Energy Reviews*, 33, 74–86. https://doi.org/10.1016/j.rser.2014.02.003

[8] **Bundesnetzagentur** (2023). *Netzentgeltsystematik Strom* (Grid tariff methodology).
Bonn: Federal Network Agency Germany. Available at: www.bundesnetzagentur.de

### Heat Pump Technology and COP

[9] **Klein, S.A., Beckman, W.A., Mitchell, J.W., Duffie, J.A., et al.** (2017).
*TRNSYS 17 — A Transient System Simulation Program*. Solar Energy Laboratory, Univ. of Wisconsin-Madison.

[10] **Vesterlund, M., Toffolo, A., Dahl, J.** (2017).
Optimization of multi-source complex district heating network, a case study.
*Energy*, 126, 53–63. https://doi.org/10.1016/j.energy.2017.02.148

[11] **Lund, R., Persson, U.** (2016).
Mapping of potential heat sources for heat pumps for district heating in Denmark.
*Energy*, 110, 129–138. https://doi.org/10.1016/j.energy.2015.12.127

[12] **Viessmann** (2021). *Heat Pump Technology — Planning and Specification Guide*.
Viessmann Climate Solutions SE, Allendorf (Eder).

[13] **Berghmans, J.** (2012). Heat pumps. In: *Energy Conversion* (A. De Vos, ed.). Wiley-VCH.

[14] **Wolf, S., Fahl, U., Blesl, M., Voß, A., Jakobs, R.** (2014).
Analyse des Potenzials von Industriewärmepumpen in Deutschland.
*IER Forschungsbericht*, 113. Universität Stuttgart.

[15] **Morvaj, B., Evins, R., Carmeliet, J.** (2016).
Optimising urban energy systems: Simultaneous system sizing, operation and district heating network layout optimization.
*Energy*, 116(1), 619–636. https://doi.org/10.1016/j.energy.2016.09.139

[16] **Raman, R., Grossmann, I.E.** (1994).
Modelling and computational techniques for logic based integer programming.
*Computers & Chemical Engineering*, 18(7), 563–578. https://doi.org/10.1016/0098-1354(93)E0010-7

[17] **Staffell, I., Brett, D., Brandon, N., Hawkes, A.** (2012).
A review of domestic heat pumps.
*Energy & Environmental Science*, 5(11), 9291–9306. https://doi.org/10.1039/C2EE22653G

[18] **Ruhnau, O., Hirth, L., Praktiknjo, A.** (2019).
Time series of heat demand and heat pump efficiency for energy system modeling.
*Scientific Data*, 6, 189. https://doi.org/10.1038/s41597-019-0199-y

[19] **Çengel, Y.A., Boles, M.A.** (2018).
*Thermodynamics: An Engineering Approach* (9th ed.). McGraw-Hill.
ISBN 978-0-07-339817-4.

[20] **Incropera, F.P., DeWitt, D.P., Bergman, T.L., Lavine, A.S.** (2017).
*Fundamentals of Heat and Mass Transfer* (8th ed.). Wiley.
ISBN 978-0-471-45728-2.

[21] **DIN EN 14825:2022** — Air conditioners, liquid chilling packages and heat pumps, with electrically driven compressors, for space heating and cooling — Testing and rating at part load conditions and calculation of seasonal performance.
Beuth Verlag, Berlin.

### Thermal Storage

[22] **Dunn, B., Kamath, H., Tarascon, J.M.** (2011).
Electrical energy storage for the grid: A battery of choices.
*Science*, 334(6058), 928–935. https://doi.org/10.1126/science.1212741

[23] **Quoilin, S., Hidalgo Gonzalez, I., Zucker, A.** (2017).
*Modelling Future EU Power Systems Under High Shares of Renewables*.
JRC Technical Report EUR 28380 EN. Publications Office of the EU.

[24] **Lund, H., Duic, N., Krajacic, G., da Graça Carvalho, M.** (2007).
Two energy system analysis models: A comparison of methodologies and results.
*Energy*, 32(6), 948–954. https://doi.org/10.1016/j.energy.2006.08.014

[25] **Haller, M.Y., Damerau, K., Dreier, D., Marty, H., Herkel, S., Jenni, A.** (2019).
Comparison of Control Strategies for District Thermal Energy Storage.
*Energies*, 12(16), 3060. https://doi.org/10.3390/en12163060

### Power-to-Heat

[26] **Lund, P.D., Lindgren, J., Mikkola, J., Salpakari, J.** (2015).
Review of energy system flexibility measures to enable high levels of variable renewable electricity.
*Renewable and Sustainable Energy Reviews*, 45, 785–807. https://doi.org/10.1016/j.rser.2015.01.057

### Thermal Generators and CHP

[27] **Eurostat** (2023). *Energy Efficiency — Thermal Plant Efficiencies*.
European Commission Statistics. https://ec.europa.eu/eurostat

[28] **Morales, J.M., Conejo, A.J., Madsen, H., Pinson, P., Zugno, M.** (2014).
*Integrating Renewables in Electricity Markets* (see [1]).

### Pipe Heat Loss and District Heating

[29] **DIN EN 13941-1:2019** — District heating pipes — Design and installation.
Beuth Verlag, Berlin.

[30] **Frederiksen, S., Werner, S.** (2013).
*District Heating and Cooling*. Studentlitteratur, Lund.
ISBN 978-91-44-08530-2.

[31] **Benonysson, A., Bøhm, B., Ravn, H.F.** (1995).
Operational optimization in a district heating system.
*Energy Conversion and Management*, 36(5), 297–314. https://doi.org/10.1016/0196-8904(95)98895-T

[32] **Mesfun, S., Toffolo, A.** (2015).
Optimization of a complex district heating system using a MILP model.
*ECOS 2015 — 28th International Conference on Efficiency, Cost, Optimization, Simulation and Environmental Impact of Energy Systems*, Pau, France.

[33] **VDI 2067 Part 1:2012** — Economic efficiency of building installations — Fundamentals and economic calculation.
VDI-Verlag, Düsseldorf.

[34] **Williams, H.P.** (2013).
*Model Building in Mathematical Programming* (5th ed.). Wiley.
ISBN 978-1-118-44333-0.

[35] **Beale, E.M.L., Tomlin, J.A.** (1970).
Special facilities in a general mathematical programming system for non-convex problems using ordered sets of variables.
*5th International Conference on Operations Research*, J. Lawrence (ed.), Tavistock, London, 447–454.

[36] **Schweiger, G., Larsson, P.O., Magnusson, F., Lauenburg, P., Velut, S.** (2017).
District heating and cooling systems — Framework for Modelica-based simulation and dynamic optimization.
*Energy*, 137, 566–578. https://doi.org/10.1016/j.energy.2017.05.115

### CO₂ Emissions

[37] **Hirth, L.** (2013).
The market value of variable renewables.
*Energy Economics*, 38, 218–236. https://doi.org/10.1016/j.eneco.2013.02.004

[38] **Zimmermann, H.J.** (2011).
*Fuzzy Set Theory — and Its Applications* (4th ed.). Springer.

[39] **IRENA** (2020). *Renewable Power Generation Costs in 2019*. International Renewable Energy Agency, Abu Dhabi.
ISBN 978-92-9260-040-2.

[40] **Glover, F., Woolsey, E.** (1974).
Converting the 0-1 polynomial programming problem to a 0-1 linear program.
*Operations Research*, 22(1), 180–182. https://doi.org/10.1287/opre.22.1.180

[41] **Tranberg, B., Corradi, O., Lajoie, B., Gibon, T., Staffell, I., Andresen, G.B.** (2019).
Real-time carbon accounting method for the European electricity markets.
*Energy Strategy Reviews*, 26, 100367. https://doi.org/10.1016/j.esr.2019.100367

[42] **Millar, M.A., Yu, Z., Burnside, N., Jones, G., Elrick, B.** (2021).
Identification of key performance indicators and complimentary load profiles for the integration of low-carbon technologies in existing district networks.
*Applied Energy*, 282, 116108. https://doi.org/10.1016/j.apenergy.2020.116108

[43] **IPCC** (2006). *2006 IPCC Guidelines for National Greenhouse Gas Inventories, Volume 2: Energy*.
Eggleston H.S., Buendia L., Miwa K., Ngara T., Tanabe K. (eds). IGES, Japan.

[44] **European Parliament and Council** (2012). *Directive 2012/27/EU on energy efficiency*.
Official Journal of the European Union, L 315/1.

[45] **Streckienė, G., Martinaitis, V., Andersen, A.N., Katz, J.** (2009).
Feasibility of CHP-plants with thermal stores in the German spot market.
*Applied Energy*, 86(12), 2308–2316. https://doi.org/10.1016/j.apenergy.2009.03.011

### Sensitivity Analysis

[46] **Saltelli, A., Ratto, M., Andres, T., Campolongo, F., Cariboni, J., Gatelli, D., Saisana, M., Tarantola, S.** (2008).
*Global Sensitivity Analysis: The Primer*. Wiley.
ISBN 978-0-470-05997-5.

---

## Appendix A: Key Physical Constants and Default Parameters

| Constant | Value | Unit | Source |
|---------|-------|------|--------|
| Specific heat capacity of water ($c_p$) | 4.186 | kJ/(kg·K) | [20] |
| Density of water at 70°C ($\rho$) | ~975 | kg/m³ | [20] |
| Default supply temperature | 90 | °C | [30] |
| Default return temperature | 55 | °C | [30] |
| Carnot efficiency factor ($\eta$) | 0.75 | − | [17, 18] |
| Heat pump loss factor ($F_Q$) | 0.10 | − | [17] |
| Default CHP thermal efficiency | 0.90 | − | [27] |
| Default storage charge efficiency | 0.98 | − | [24] |
| Default storage self-discharge | 0.05 | %/h | [24] |
| Default pipe U-value (insulated) | 0.15 | W/(m·K) | [29] |
| Gas emission factor | 201.6 | kg CO₂/MWh | [43] |

---

## Appendix B: MILP Formulation Class

The model belongs to the class of **Multi-Period Mixed-Integer Linear Programs (MP-MILP)**
with binary variables for:
1. Component existence (investment, $y_i \in \{0,1\}$)
2. Operating modes (unit commitment, $u_t \in \{0,1\}$)
3. Grid direction (buy/sell, $g_t \in \{0,1\}$)
4. Storage modes (charge/discharge, $\xi^c_t, \xi^d_t \in \{0,1\}$)

Computational complexity grows as $O(T \cdot N_{\text{binary}})$ in the number of binary variables.
For annual hourly optimization ($T$ = 8,760), typical problem sizes are:
- ~50,000–200,000 continuous variables
- ~5,000–30,000 binary variables
- ~100,000–400,000 constraints

Solved with branch-and-bound using commercial (Gurobi, CPLEX) or open-source
(CBC, HiGHS, GLPK, SCIP) MILP solvers via the Pyomo modeling language [47, 48].

[47] **Hart, W.E., Watson, J.P., Woodruff, D.L.** (2011).
Pyomo: Modeling and solving mathematical programs in Python.
*Mathematical Programming Computation*, 3(3), 219–260. https://doi.org/10.1007/s12532-011-0026-8

[48] **Huangfu, Q., Hall, J.A.J.** (2018).
Parallelizing the dual revised simplex method.
*Mathematical Programming Computation*, 10, 119–142. https://doi.org/10.1007/s12532-017-0130-5
(HiGHS solver)

---

*Document generated: 2026-03-28 | Framework: EnerGIS v1.0 | Branch: feature/refactoring-framework-cleanup*
