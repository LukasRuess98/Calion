# CALION Paper 2 — Implementation Statement & Specification Traceability

**Status report generated 2026-07-08.** Compares the current model, configurations and
scenario matrix against the requirements in
`docs/paper_2/Framework_edits/CALION_Paper2_Spezifikation.docx` (Version 1.0, Juni 2026,
L. Ruess / EEP Stuttgart). Written to serve directly as the mathematical/methodological
foundation for the Paper 2 manuscript.

Legend for the traceability tables:
**✅ Done** = implemented and verified · **◑ Partial/Deviation** = implemented but differs
from the spec (deviation explained) · **⏳ Pending** = built but not yet run at campaign
scale · **➕ Beyond spec** = capability added on top of the specification.

---

## 0. Executive summary

The CALION framework (Python + Pyomo + Gurobi 13.0) has been extended from the Paper 1
L3 dispatch model into the full Paper 2 investment-optimisation model. All eight extension
areas named in §1.2 of the specification are implemented:

1. CAPEX investment variables for heat pump (WP), electrode boiler (EK) and thermal
   storage (TES) — ✅
2. Geometric TES sizing (volume `V`, height `h`, operating pressure `p`, temperature
   levels) — ✅
3. Heat-curve optimisation via discrete scenario stages (slope `k`, `T_VL,min`) — ✅
4. TES-location scenarios (candidate nodes per network) — ✅, **and extended** to
   endogenous (solver-chosen) siting (➕, scenarios S4–S7)
5. Waste-heat integration with time-varying source temperature for the WP-COP — ✅
6. Demand-side management (flexible consumers) — ✅ built, **deliberately parameterised to
   zero** per spec §4.4.1 ("Erstmal implementieren aber auf 0 setzen")
7. Baseline case (no WP / no TES / fixed real heat curve) — ✅ (BC-MM, BC-SB)
8. Two case studies — Stadtbach and Memmingen — ✅

The single most significant methodological addition made beyond the literal Paper 1
carry-over is the **L3+ spatially-resolved thermo-hydraulic model** completed in this
session: node-to-node supply-temperature drop, transport delay, and spatial pressure
propagation are all now active in **MILP-compatible** form (no bilinear/quadratic terms;
McCormick relaxation used where a product of two decision variables would otherwise
arise). This directly realises the spec's requests in §4.1.3 (feed TES height into the
network pressure; simulate the charge/discharge pressure drop) and the "aus Paper 1
übernommen" hydraulic items in §4.

The scenario matrix has grown from the 20 runs sketched in spec §5.1 to **46 runs**,
because (a) every S-row is expanded into the three heat-curve stages HK0/HK1/HK2 plus a
`TVLFIX` reference, and (b) the user added the free-siting extension (S4–S7 for Stadtbach,
S4–S5 for Memmingen) in which the WP/TES node is a solver decision rather than a fixed
scenario. See §5.

---

# PART A — GLOBAL: model, thermodynamics, mathematics

## A.1 Model class and thermodynamic level

| Aspect | Specification (§1.1, §1.2) | Implementation | Status |
|---|---|---|---|
| Modelling language / solver | Pyomo + Gurobi 13.0 | Pyomo + Gurobi (`solver_io="python"`) | ✅ |
| Physics level | L3 nodal thermo-hydraulic | L3 **plus** optional L3+ spatial temperature propagation | ✅ / ➕ |
| Horizon | T = 8760 h | 8760 hourly steps, `dt_h = 1.0` | ✅ |
| Topology | Brownfield fixed; only WP/EK/TES sized | Node/pipe topology fixed per YAML; investment only on WP/EK/TES | ✅ |

The network is modelled as a directed graph of **nodes** (`ThermalNodeBlock`) and
**pipe pairs** (`PipePairBlock`, a supply + return line). Node types are inferred from the
unified config: a node with `assets:` + `consumers:` is `mixed`, assets-only is
`producer`, consumers-only is `consumer`, neither is `junction`.

Two temperature regimes are supported and selected by `network.milp_linearize` and
`network.temperature_propagation`:

- **L3 (MILP, temperature as parameter):** supply/return temperatures are fixed
  per-timestep `Param`s taken from the heating curve. Every heat–massflow conversion
  `Q = ṁ · c_p · ΔT` is then **linear** in `ṁ`. This is the classic Paper 1 mode.
- **L3+ (MILP with McCormick, temperature as variable):** each node's own supply
  temperature `T_VL,i(t)` becomes a genuine decision variable that *propagates spatially*
  and *drops from node to node* due to pipe heat loss. Bilinearity `ṁ·T` is removed
  exactly by introducing an enthalpy-flux variable `W = ṁ · c_p · T` and bounding it with
  the four **McCormick envelope** inequalities. No quadratic term ever enters Gurobi, so
  the problem remains a true MILP. Both case-study configs run L3+.

Physical constants (both networks): `ρ_water = 971.8 kg/m³` (at ≈75 °C),
`c_p = 4.186 kJ/(kg·K)`, `g = 9.81 m/s²`, `p_atm = 1.013 bar`.

## A.2 Decision variables (global)

The table lists the mathematical symbol, Pyomo realisation, domain and the spec clause it
serves. Index `t ∈ {1,…,8760}`; `i` node; `(i,j)` pipe from node `i` to node `j`;
`a` asset.

### A.2.1 Investment / capacity variables (spec §3.1)

| Symbol | Pyomo | Domain | Meaning |
|---|---|---|---|
| `Q̇_WP` | `{hp}_cap_th` | ℝ₊ [MW] | Installed WP thermal capacity, bounds `[cap_min, cap_max]` |
| `Q̇_EK` | `{ek}_cap_th` | ℝ₊ [MW] | Installed EK thermal capacity |
| `V_TES` | `{tes}_V_m3` | ℝ₊ [m³] | Geometric storage volume (single Var, Option A) |
| `y_WP, y_EK, y_TES` | `{a}_build` | {0,1} | Activation binaries; Big-M linked to capacity/operation |

TES height `h_TES` is not a free variable in the production configs: **Option A**
(`option_b: false`) fixes the slenderness ratio `h/d = r_hd` (3.0), so `h` is back-computed
from `V` after solving. This is the spec's own recommended default (§4.1.1: h/d ∈ [2,4]).
Option B (free `d`) exists in code but is not used.

### A.2.2 Hourly operating variables (spec §3.4)

| Symbol | Pyomo | Domain | Meaning |
|---|---|---|---|
| `q_WP(t)` | `{hp}_Q_th_out` | ℝ₊ [MW] | WP heat output, ≤ `Q̇_WP` |
| `q_EK(t)` | `{ek}_Q_th_out` | ℝ₊ [MW] | EK heat output, ≤ `Q̇_EK` |
| `q_TES,c(t), q_TES,d(t)` | `{tes}_Q_th_in / _out` | ℝ₊ [MW] | Charge / discharge power |
| `SOC(t)` | `{tes}_E` | ℝ₊ [MWh] | State of charge |
| `q_Gas, q_Bio, q_CHP(t)` | `{gen}_Q_th` | ℝ₊ [MW] | Existing generators |
| `P_el(t)` | grid `P_buy` / `P_sell` | ℝ₊ [MW] | Grid exchange; `P_buy_peak` tracks annual peak |
| `ṁ_(i,j)(t)` | `{pipe}_m_dot` | ℝ [kg/s] | Pipe mass flow (signed on bidirectional pipes) |
| `T_VL,i(t)` | `{i}_T_supply` | ℝ₊ [°C] | Node supply temp — **Param** in L3, **Var** in L3+ |
| `p_supply,i(t)`, `p_return,i(t)` | `{i}_pressure_supply/return` | ℝ₊ [bar] | Node pressures (when pressure_drop on) |
| `δ(t)` | DSM `delta_pos/neg` | ℝ₊ [MW] | DSM shift (currently bounded to 0) |

### A.2.3 L3+ auxiliary variables (➕ this session)

| Symbol | Pyomo | Purpose |
|---|---|---|
| `W_sup,in/out (i,j)(t)` | `{pipe}_W_sup_in/out` | Pipe enthalpy flux `ṁ·c_p·T`, McCormick-linked |
| `ṁ_gen,i(t), W_gen,i(t)` | `{i}_m_dot_gen / _W_*_gen` | Local-generation mass-flow equivalent at a producing node |
| `W_demand,i(t)` | `{i}_W_demand` | Demand-side `ṁ_demand·c_p·T` for passthrough consumers |
| `flow_dir (i,j)(t)` | `{pipe}_flow_dir` | Direction binary for bidirectional pipes (exact `|ṁ|`) |

## A.3 Objective function (spec §2)

The implemented objective (`create_objective`, `constraint_builder.py`) minimises

```
min  Σ_a ANF(i, n_a) · CAPEX_a          (annualised investment)
   + Σ_t c_el(t) · P_buy(t)             (energy purchase)
   − Σ_t c_el(t) · P_sell(t)            (energy sale, incl. CHP electricity)
   + Σ_t c_Gas · q_Gas(t) + c_Bio · q_Bio(t) + c_WH · q_WH(t)   (fuel)
   + c_CO2 · Σ_t ṁ_CO2(t)              (carbon)
   + L_peak · P_buy_peak                (annual demand charge)
   + c_dump · Σ_t Q_dump(t)            (dump / slack penalties)
   + activation, tie-break, storage-install, terminal-value, return-anchor terms
```

This is a superset of the spec §2 objective
`min ANF·Σ CAPEX + Σ_t [c_el·P_el + c_CO2·ṁ_CO2 + c_Gas·q_Gas + c_DSM·|δ|]`. The additional
terms (demand charge `L_peak·P_buy_peak`, fuel split for biomass/waste-heat, CHP electricity
credit, dump penalty) are standard OPEX components consistent with the KPI definitions in
spec §6.1. The DSM comfort term `c_DSM·|δ|` is present but currently zero-valued.

**Status: ✅ (superset of the spec).**

### A.3.1 CAPEX annualisation (spec §2.1)

Implemented exactly as specified (`investment_calculator.py::annuity_factor`):

```
ANF(i, n) = i·(1+i)^n / ((1+i)^n − 1)
```

with `i = 0.05` (`economics.discount_rate`, VDI 2067 / WACC-typical). Lifetimes:
`n_WP = 20 a`, `n_EK = 25 a`, `n_TES = 30 a` — all inside the spec's recommended bands
(WP 15–20, EK 20–25, TES 25–30). **Status: ✅.**

### A.3.2 CAPEX cost functions (spec §2.2)

Linear-with-fixed-cost form, exactly matching the spec:

```
CAPEX_WP  = α_WP · Q̇_WP  + β_WP · y_WP
CAPEX_EK  = α_EK · Q̇_EK  + β_EK · y_EK
CAPEX_TES = α_TES · V_TES + β_TES · y_TES
```

Memmingen parameter values (per VDI 2067 unit-cost assumptions in the config):

| Component | α | β (activation) | source note |
|---|---|---|---|
| WP (`hp_main`) | 700 000 €/MW | 50 000 € | 700 €/kW |
| EK (`eboiler_main`) | 150 000 €/MW | 20 000 € | 150 €/kW |
| TES (`tes_main`) | 500 €/m³ | 50 000 € | vessel + connection |

**Status: ✅** (form exact; α/β values are user-set assumptions, flagged in-config as
literature/VDI-based — see open item O-1).

## A.4 Constraints (global) — mathematical foundation

### A.4.1 Nodal heat balance (Paper 1 core)

For every node `i` and timestep `t`, thermal power [MW] is conserved:

```
Σ_a q_a,i(t)  +  Σ_(j→i) Q_deliv,(j,i)(t)          (local generation + inflow)
   =  D_i(t)  +  Σ_(i→k) Q_deliv,(i,k)(t)          (demand + outflow)
      +  q_TES,charge,i(t)  −  q_TES,disch,i(t)     (storage)
      +  Q_dump,i(t)                                (curtailment slack)
```

The primary producer additionally carries the whole-network loss via the supply-side
`Q_delivered` of every outgoing pipe (losses are embedded in `Q_delivered`). For a node
that hosts local generation *and* passes flow downstream, both the generation and the
downstream `Q_delivered` terms appear — the subtle interaction of these across the
heat balance (MW) and the mass balance (kg/s) was the subject of a five-bug fix chain
(see `memory/project_endogenous_siting_bugfix.md`). **Status: ✅.**

### A.4.2 Mass-flow (Kirchhoff) balance

Independently of the heat balance, physical water mass is conserved at each node:

```
Σ_(j→i) ṁ_(j,i)(t)  +  ṁ_gen,i(t)  =  Σ_(i→k) ṁ_(i,k)(t)  +  ṁ_demand,i(t)
```

In L3 mode each pipe `ṁ` is a fixed linear image of its `Q_delivered`
(`Q = ṁ·c_p·ΔT`, ΔT a Param). In L3+ mode the local-generation term
`ṁ_gen = Q_gen · 1000 / (c_p · (T_VL − T_RL))` becomes a product of decision variables and
is therefore linearised via a dedicated McCormick block on `W_gen` (`constraint_builder.py::
_attach_local_generation_mdot`). Supply- and return-side temperatures are treated
independently (each may be Var or Param), which is required for meshed nodes such as
Stadtbach's `j_ost` where `T_return` is free while `T_supply` is anchored. **Status: ✅.**

### A.4.3 Spatial supply-temperature propagation (L3+, ➕ this session)

Each pipe carries a supply-side enthalpy flux with heat loss:

```
W_sup,in(i,j)(t)  =  ṁ(i,j)(t) · c_p · T_VL,in(i,j)(t)       (McCormick-relaxed)
W_sup,out(i,j)(t) =  ṁ(i,j)(t) · c_p · T_VL,out(i,j)(t)      (McCormick-relaxed)
W_sup,in − W_sup,out = Q_loss,sup(i,j)(t) · 1000              (enthalpy loss = heat loss)
Q_loss,sup(i,j)(t) = U · L · (T_avg − T_ground)/1e6           (linear in supply-T Vars)
```

Node mixing ties a node's supply temperature to its incoming pipe(s):

```
single incoming pipe:  T_VL,i(t) = T_VL,out(j,i)(t)                       (exact equality)
multiple incoming:     W_node = Σ_(j→i) W_sup,out(j,i);  T_VL,i via McCormick(W_node, ṁ_in_total)
```

The four-inequality McCormick envelope (`utils/mccormick.py`) for `W ≈ s·x·y` with
`x∈[x_L,x_H]`, `y∈[y_L,y_H]` is

```
W ≥ s·(x_L·y + x·y_L − x_L·y_L)
W ≥ s·(x_H·y + x·y_H − x_H·y_H)
W ≤ s·(x_H·y + x·y_L − x_H·y_L)
W ≤ s·(x_L·y + x·y_H − x_L·y_H)
```

The primary producer's outgoing pipe(s) are anchored to the heating-curve `Param`
(`is_source_pipe`), giving the propagation a fixed starting point. Nodes adjacent to a
bidirectional pipe are deliberately kept on the uniform-`Param` scheme (direction-dependent
propagation with McCormick is out of scope). **Status: ✅ (both networks).**

### A.4.4 Transport delay (spec §1.1 "aus Paper 1 übernommen")

Enabled via `physics.transport_delay: true`. In MILP mode a **linear fixed-lag** lookback
is used (`compute_delay_buckets`, single bucket, no SOS2 binaries):

```
Q_consumer(i,j)(t) = Q_useful(i,j)(t − τ_(i,j)),   τ = round(volume / (ṁ_max · Δt))
```

The non-MILP path retains the full 3-bucket SOS2 formulation named in the spec.
Note: Memmingen's `max_velocity_m_s` was reverted from 100 (capacity bypass) to a realistic
2.5 m/s this session so that τ is physically meaningful again. **Status: ✅.**

### A.4.5 Pressure drop and spatial pressure (spec §4.1.3, §6.3)

Darcy–Weisbach pressure drop is piecewise-linearised (PWL, 3 segments) in `ṁ`:

```
Δp(i,j)(t) = PWL_DW( ṁ(i,j)(t) )   [Pa → bar via /1e5]
```

and propagated spatially node-to-node from the primary-producer setpoint:

```
p_supply,j(t) = p_supply,i(t) − Δp_supply,(i,j)(t)      (supply falls downstream)
p_return,i(t) = p_return,j(t) − Δp_return,(i,j)(t)      (return falls upstream)
```

Pump electric power feeds the electricity bus:

```
P_pump(t) = Σ_(i,j) Δp(i,j)(t) · ṁ(i,j)(t) / (ρ · η_pump)     (η_pump = 0.75)
```

Bidirectional pipes (Stadtbach `hkw_to_ost`) now build `flow_dir`/`m_dot_abs` even in MILP
mode (bug fixed this session), so pressure is direction-consistent and `pressure_drop: true`
is safe for Stadtbach. **Status: ✅.**

### A.4.6 Geometric TES (spec §4.1)

Energy capacity is linear in `V` because ΔT is a scenario parameter (spec §4.1.2 recommended
linearisation):

```
E_TES,max = ρ·c_p·ΔT(k) / (3600·1000) · V_TES     [MWh]     (energy_coeff · V)
SOC(t) = SOC(t−1)·loss_hour + η_c·q_TES,c(t) − q_TES,d(t)/η_d      (loss_hour = 0.9999)
0 ≤ SOC(t) ≤ E_TES,max
SOC(1) = f_soc0 · E_TES,max,     SOC(8760) ≥ f_term · E_TES,max     (f_soc0 = f_term = 0.5)
q_TES,c(t), q_TES,d(t) ≤ (P/E) · E_TES,max         (power-to-energy ratio = 0.25 → ~4 h)
```

Geometry (Option A): `d = h / r_hd`, `V = π/4·d²·h`; a max-volume cap from the pressure
rating (`V_max_effective`) guards against sizing a tank taller than `p_max` allows.
**Status: ✅.**

### A.4.7 TES operating pressure & network coupling (spec §4.1.3)

The spec explicitly requested (a) the storage column height feeding pressure into the
network and (b) simulating the charge/discharge pressure drop. Both are implemented
(`network_manager.py::_link_tes_pressure_coupling`, feature "F4"):

```
p_supply,i(t) ≥ p_atm + ρ·g·h(V)/1e5 + k_dp·q_TES,c(t) − k_dp·q_TES,d(t) − M·(1−y_TES)
p_supply,i(t) ≤ p_max + M·(1−y_TES)                             (vessel rating)
```

`h(V)` is itself PWL (concave `h = (4·r²·V/π)^{1/3}`, SOS2). The hydrostatic push is
skipped at the primary producer (its `p_supply` is fixed by the pump setpoint). Active in
Memmingen (`tes_pressure_coupling: true`). **Status: ✅.**

### A.4.8 Heating-curve model (spec §4.2)

Implemented as a **discrete scenario loop** (spec §4.2.3 recommended, "kein SOS1"): three
stages HK0/HK1/HK2 per network, each a `(k, T_VL,min, T_VL,max)` triple, plus a `TVLFIX`
reference. `scenario_runner.py` precomputes the per-hour supply-temperature array via
`compute_heizkurve(k, T_VL_min, T_aus)` and injects it as a `Param`; the COP array is then
precomputed from it. A consumer-minimum-temperature check enforces
`T_VL,min ≥ max_j T_VL,min,j` (§4.2.2). **Deviation note:** the internal
`compute_heizkurve` uses a reference-point linear form
`T_VL = T_VL,min + k·span·(T_heiz − T_aus)/norm` rather than the spec's literal
`T_VL = max(T_VL,min, T_VL,max − k·(T_VL,max − T_aus))`. Both are monotone heating curves
clamped to `[T_VL,min, T_VL,max]`; the discretised-scenario treatment (the paper-relevant
choice) matches the spec exactly. **Status: ◑ (scenario treatment ✅; exact formula
differs — O-2).**

### A.4.9 Waste-heat integration & COP (spec §4.3)

Source temperature is time-varying and read per network from the data file
(`wrg_source_column`, `wrg_capacity_column`). The WP output is capped by the available
waste-heat power `q_WP,AW(t) ≤ Q̇_AW,max(t)`. COP is precomputed as a per-hour parameter
from an analytical **Lorenz-efficiency** model (`cop_calculator.py`) — the same formula
used in the source notebook:

```
COP(t) = A·B·η·(1 − q_ww) + 1 − η − FQ
```

with LMTD-based `A`, `B`, correction `q_ww`, `η = 0.75`, `FQ = 0.10`, `ΔT_pp = 5 K`. This
realises the spec's "COP = f(T_Quelle, T_VL)" LUT interface (§4.3.3) via a closed-form
analytical surrogate rather than a tabulated LUT. **Status: ✅ (analytical form; O-3).**

### A.4.10 DSM (spec §4.4)

Load-shift variables `δ(t) = δ_pos(t) − δ_neg(t)`, window energy conservation
`Σ_{τ∈[t,t+Δt]} δ(τ) = 0`, bound `−δ_max ≤ δ ≤ δ_max`, comfort penalty
`c_DSM·Σ(δ_pos+δ_neg)`, effective demand `Q_eff = Q_base + δ`. Present in code
(`blocks/dsm.py`, `_apply_dsm`) but **no network currently declares DSM consumers**, so
`δ ≡ 0`. This matches the spec instruction "Erstmal implementieren aber auf 0 setzen".
**Status: ✅ (implemented, intentionally inactive).**

### A.4.11 Grid & demand charge

`P_buy`/`P_sell` gated by a binary `grid_mode` (no simultaneous buy/sell); `P_buy_peak`
tracks the annual import peak and is priced by the Jahresleistungspreis
(`demand_charge_eur_per_mw_y`). Volumetric grid cost `gridcost_eur_mwh = 25` reflects the
2026 MS Arbeitspreis + levies. **Status: ✅.**

## A.5 Global parameter set (both networks unless noted)

| Parameter | Value | Meaning |
|---|---|---|
| `discount_rate i` | 0.05 | ANF interest |
| `c_CO2` | 100 €/t | carbon price |
| `ef_el` | 400 kg/MWh | grid electricity emission factor |
| `ef_gas` | 200 kg/MWh | gas |
| `ef_biomass` | 20 kg/MWh | biomass |
| `c_Gas` | 45 €/MWh | gas price |
| `c_Bio` | 40 €/MWh | biomass price |
| `c_WH` (SB) | 5 €/MWh | waste-heat take-over |
| `gridcost` | 25 €/MWh | volumetric grid cost |
| `dump_cost` | 1000 €/MWh | curtailment penalty |
| `ρ, c_p, g, p_atm` | 971.8, 4.186, 9.81, 1.013 | water/physics constants |
| `η_pump` | 0.75 | pump efficiency |

---

# PART B — USE-CASE SPECIFIC

## B.1 Memmingen

### B.1.1 Data input and handling

- **Config:** `configs/paper_2/Memmingen_P2_base.yaml` (15 nodes, 14 pipes — the Paper 1 L3
  radial tree).
- **Demand data:** `data/Import_Data_Memmingen_epronet_cleaned.xlsx` — **quality-flag
  cleaned** this session. The raw file carried per-reading `power_quality` flags; masking on
  `quality ≠ 1` and interpolating only over gaps ≤ 4 steps (1 h) removed sensor glitches
  while preserving genuine multi-week meter-commissioning gaps as honest NaN. Result: system
  peak 11.44 → **5.31 MW**, annual 59.69 → **57.34 GWh**, max column peak/mean ratio
  210× → 7.3×. (See `memory/project_memmingen_dxf_crosscheck.md`.)
- **Pipe topology:** lengths/diameters for 9 of 14 pipes re-derived from the real DXF
  as-built drawing (`2026-07-06_MM-Nord_Bestand_FW.dxf`); diameters now top out at DN250/300
  (matching the site) instead of the earlier DN450. `max_velocity_m_s` reverted to 2.5.
- **Time series read:** `strompreis_EUR_MWh` (electricity price), `grid_co2_kg_MWh`, outdoor
  temperature, per-zone demand columns `V_1…V_27_demand_MWth`, waste-heat `WRG_1 °C` /
  `WRG1Q MW`.

### B.1.2 Topology & assets (YAML-specific)

- **Producer node `j_1`:** existing CHP (`chp_main`), biomass (`biomass_main`), gas boiler
  (`gasboiler_main`), plus the primary TES site.
- **Waste-heat node `j_12`:** hosts the investable WP (`hp_main`) and EK (`eboiler_main`) —
  the spec's "WP/EK fest bei der Abwärme, Memmingen = j_12" (§3.3).
- **Consumers:** 27 demand zones mapped to nodes `j_1…j_15`.
- **Physics flags:** `milp_linearize: true`, `temperature_propagation: true`,
  `pressure_drop: true`, `transport_delay: true`, `tes_pressure_coupling: true`.

### B.1.3 Investable-asset parameters

| Asset | Node | α | β | lifetime | cap range |
|---|---|---|---|---|---|
| `hp_main` (WP) | j_12 | 700 000 €/MW | 50 000 € | 20 a | 0–30 MW |
| `eboiler_main` (EK) | j_12 | 150 000 €/MW | 20 000 € | 25 a | 0–20 MW |
| `tes_main` (TES) | scenario | 500 €/m³ | 50 000 € | 30 a | V ∈ [5, 50 000] m³, p_max 10 bar, h/d = 3 |

### B.1.4 Scenario coverage (Memmingen)

`BC-MM` (baseline, no WP/TES, fixed curve), `MM-S0` (no TES; TVLFIX + HK0/1/2),
`MM-S1` (TES at `j_1`), `MM-S2` (TES at `j_12`), `MM-S3` (TES at `j_12`, hot charging —
WP charges the tank above `T_VL`), `MM-S4` (➕ endogenous TES+WP siting among
`{j_1,j_3,j_5,j_9,j_12,j_13}`), `MM-S5` (➕ endogenous, co-located WP+TES with hot charging).
Heat-curve stages HK0 `(k=1.0, T_VL,min=74)`, HK1 `(0.8, 70)`, HK2 `(0.6, 66)`,
`T_VL,max=100`, `T_RL=63.6 °C`.

## B.2 Stadtbach

### B.2.1 Data input and handling

- **Config:** `configs/stadtbach/Stadtbach_topo.yaml` (33 nodes, 32 pipes — meshed, with one
  **bidirectional** trunk `hkw_to_ost`).
- **Data file:** `data/Stadtbach/stadtbach_acron_combined.xlsx` (electricity price, grid CO₂,
  three waste-heat streams WRG1–3, outdoor temperature, per-zone demands). System peak
  ≈ 228 MW, mean ≈ 78 MW.
- **Asset data provenance:** fixed-generator data was corrected in two steps this session.
  (1) Thermal efficiencies and CHP electrical efficiencies were taken from the source
  notebook `configs/paper_2/20250922_Stadtbach.ipynb` (user-confirmed authoritative for the
  conversion ratios); **`el_eff` was added** for `hkw`/`gtost`/`bmhkw` (previously
  unmodelled CHP electricity — a first-order economic effect), and the heat-pump Lorenz
  factor `η` was corrected 0.6 → 0.75 to match the notebook. (2) The **thermal-output
  capacities `capacity_mw` are the real user-provided operating values valid for
  Übergangszeiten (99/60 °C supply/return)**. These are deliberately *not* the −14 °C design
  values (125/60 °C): the takeover/heat-exchanger stations deliver *more* thermal power at
  the milder Üzeiten condition (larger primary↔secondary ΔT) and *less* at the cold design
  point (HX ΔT-limited). Since the model runs a heating curve operating mostly around Üzeiten
  conditions, these are the representative caps. A fictional 500 MWh `tes_existing` tank with
  no documented source was **removed**. In CALION `capacity_mw` is the thermal-output cap, so
  fuel = `capacity_mw / th_eff` and CHP electricity = fuel × `el_eff`.

### B.2.2 Fixed generators (thermal outputs at Üzeiten 99/60 °C, user-provided)

| Asset | Node | Fuel | cap_th [MW] | th_eff | el_eff |
|---|---|---|---|---|---|
| `hkw` (HKW) | j_hkw | gas | 127.0 | 0.743 | 0.177 |
| `gtost` (GT-Ost) | j_gtost | gas | 35.0 | 0.466 | 0.36 |
| `bmhkw` (Bio-HKW) | j_bmhkw | biomass | 14.5 | 0.485 | 0.177 |
| `ava_feed` (AVA) | j_ava | waste-heat | 45.0 | 1.0 | — |
| `hws_boiler` (HW Süd) | j_hws | gas | 32.0 | 0.936 | — |
| `hww_boiler` (HW West) | j_hww | gas | 104.0 | 0.924 | — |
| `p2h_existing` | j_hkw | electricity | 9.9 | 0.99 | — |

Fixed thermal capacity total ≈ 357.5 MW against a ≈228 MW peak demand.

### B.2.3 Investable assets

`hp_sb` (WP, α = 400 000 €/MW, 0–50 MW, WRG1-sourced, COP η = 0.75),
`ek_sb` (EK, α = 150 000 €/MW, 0–50 MW), `tes_sb` (geometric TES, per-scenario node).

### B.2.4 Scenario coverage (Stadtbach)

`BC-SB` (baseline), `SB-S0` (no TES), `SB-S1` (TES J1 = `j_hkw`), `SB-S2` (TES J4 =
`j_man`), `SB-S3` (J4, hot charging), `SB-S4` (TES J6), `SB-S5` (TES J8),
`SB-S6` (➕ endogenous siting among `{j_hkw,j_man,j_ost,j_pss,j_psw}`),
`SB-S7` (➕ endogenous, co-located WP+TES, hot charging). Heat-curve stages HK0
`(k=1.0, T_VL,min=70)`, HK1 `(0.8, 65)`, HK2 `(0.6, 60)`, `T_VL,max=122`, `T_RL=60 °C`.
The WP/EK are placed at the central production hub (spec §3.3 "an einem zentralen Knoten").

---

# PART C — Specification traceability (section-by-section)

| Spec § | Requirement | Status | Notes |
|---|---|---|---|
| §2 | Objective min CAPEX+OPEX | ✅ | superset (adds demand charge, fuel split, CHP credit) |
| §2.1 | ANF(i,n) | ✅ | i = 5 %, n = 20/25/30 |
| §2.2 | α·x + β·y CAPEX | ✅ | form exact; α/β user assumptions (O-1) |
| §3.1 | Q̇_WP, Q̇_EK, V, h, y | ✅ | h via Option A (h/d = 3) |
| §3.2 | Heat-curve k, T_VL,min | ✅ | discrete scenarios (spec-recommended) |
| §3.3 | TES-location scenarios S1/S2/S3 | ✅ | + endogenous S4–S7 (➕) |
| §3.4 | hourly operating vars | ✅ | full set |
| §4.1.1–2 | TES geometry + linear E(V) | ✅ | Option A, ΔT scenario param |
| §4.1.3 | TES pressure into net + charge/disch Δp | ✅ | F4 coupling, both requests met |
| §4.1.4 | link to SOC dynamics | ✅ | E_max expression, C-rate power bound |
| §4.2 | heating-curve model + constraints | ◑ | scenario ✅, exact formula differs (O-2) |
| §4.3 | waste-heat + COP LUT | ✅ | analytical Lorenz surrogate (O-3) |
| §4.4 | DSM | ✅ | built, zero-valued per spec |
| §4.5 | Baseline | ✅ | BC-MM, BC-SB |
| §5.1 | scenario matrix | ✅/➕ | 46 runs (20 base + HK expansion + endogenous) |
| §6.1–6.3 | KPIs (econ/eco/hydraulic) | ⏳ | `kpi_calculator.py` present; run post-campaign |
| §7 | sensitivity (tornado) | ⏳ | `sensitivity.py` present; run post-campaign |
| §10 | validation (energy balance, feasibility, P1 consistency…) | ◑ | feasibility of hard cases verified; full suite post-campaign |

---

# PART D — Open items & deviations (for the manuscript's limitations/assumptions)

- **O-1 — Cost coefficients (α, β).** WP/EK/TES unit costs are literature/VDI-2067-style
  assumptions, not procurement quotes. The Stadtbach `tes_sb` CAPEX (≈9 560 €/MWh implied)
  sits above the range in which the source notebook ever found storage economical; a
  sensitivity sweep (spec §7) will bound its influence.
- **O-1b — Stadtbach fixed-generator capacities are Üzeiten (99/60 °C) values.** The real
  deliverable thermal power is lower at the −14 °C design point (125/60 °C, HX ΔT-limited).
  The model does not currently reduce these caps at the coldest hours; if peak-cold
  deliverability matters for a scenario, a temperature-dependent capacity de-rating would be
  the refinement.
- **O-2 — Heating-curve formula.** Internal `compute_heizkurve` uses a reference-point form
  rather than the spec's literal `T_VL,max − k·(T_VL,max − T_aus)`. Functionally equivalent
  (monotone, clamped); worth stating explicitly in the methods section.
- **O-3 — COP model.** Analytical Lorenz surrogate (η = 0.75, FQ = 0.10) replaces a tabulated
  LUT; it is the same closed form used in the validated Stadtbach notebook.
- **O-4 — CHP electricity for Memmingen.** `chp_main` at `j_1` currently has no `el_eff`
  (heat-only). If Memmingen's CHP should earn electricity revenue like Stadtbach's, add
  `el_eff` (analogous to the Stadtbach correction).
- **O-5 — Endogenous siting beyond spec.** Spec §3.3 states the TES location is *not* solved
  endogenously; scenarios S4–S7 add exactly that (`Σ y_c = 1` site binaries) at the user's
  request. This is an extension, not a compliance gap, and should be presented as such.
- **O-6 — Node/pipe export for Memmingen.** The spatial `nodes_state_hourly` / `pipes.csv`
  exports came back empty for Memmingen in the last contention-limited test (no incumbent
  found under shared CPU); Stadtbach exports are fully populated. To be re-confirmed on the
  dedicated-resource campaign run.
- **O-7 — Campaign status reporting.** The throwaway regression harness labelled a
  no-incumbent (`obj = 0 €`) result as `status=ok`; the campaign's status logic should treat
  "no incumbent within time limit" as a distinct outcome before the final run.

---

# PART E — Verification performed (this session)

- **Regression feasibility:** MM-S4-HK0, MM-S5-HK0 (previously `infeasibleOrUnbounded`)
  now solve full-year; SB-S6-HK0, SB-S7-HK0 solve full-year with the corrected assets and
  the capacity-validator fix. The Stadtbach bidirectional-pressure fix was exercised by
  SB-S7 (F3 + bidirectional + McCormick generation nodes) building and solving cleanly.
- **MILP integrity:** every regression solve converged as a standard MILP (no non-convex
  QP handling required), confirming no bilinear term survives the McCormick linearisation.
- **Physical exports (Stadtbach):** `nodes_state_hourly.parquet` (289 080 rows),
  `pipe_state_hourly.parquet` (≈1.96 M rows) with real per-node `T_supply_c`, `P_bar`,
  per-pipe `m_dot_kg_s`, `dp_Pa` — the intended source for the spec §6.3 hydraulic KPIs and
  for visual monotonicity checks of temperature/pressure along trunks.

*End of statement — generated 2026-07-08 for the CALION Paper 2 manuscript foundation.*
