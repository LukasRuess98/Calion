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

The single most significant methodological addition beyond the literal Paper 1
carry-over is **spatially-resolved thermo-hydraulics in MILP-compatible form**: node-to-node
supply-temperature drop, transport delay, and (Memmingen) spatial pressure propagation.

**Method note — spatial temperature (delivered approach).** A full co-optimised temperature
propagation (temperature as a decision variable, the bilinear `ṁ·T` enthalpy flux relaxed
by McCormick envelopes — "L3+") was implemented and works, but at 8760 h it inflates the
model to ~6 M rows whose root LP relaxation does not solve in reasonable time (see
Part E.1). The **delivered** method is therefore the *lightweight spatial-temperature
offset*: supply temperature stays a per-timestep **parameter** (the heating curve) but each
node's value is reduced by the **cumulative heat-loss temperature drop from the plant along
the trunk**, precomputed as `ΔT_pipe = U·L·(T_avg − T_ground)/(ṁ_design·c_p)` summed over the
plant→node path. This keeps the model a compact, fully-linear MILP (solvable at full year on
both networks) while still producing a physically-correct, monotonic node-to-node
temperature drop (≈0.7 K across Memmingen, ≈1.8 K across Stadtbach's longer trunks). It
trades exact flow↔temperature co-optimisation (the drop is computed from a nominal design
flow, not the solved flow) for tractability — a standard and defensible simplification given
the drop's small magnitude.

Transport delay is active on both networks. Spatial pressure (Darcy-Weisbach PWL + node
propagation, realising spec §4.1.3 incl. TES height→pressure and charge/discharge Δp) is
active on **both networks**. Stadtbach's multi-source mesh is handled by classifying every
producer/pump-station node as a pressure source (primary fixed, secondary pump-boosted floor)
and propagating pressure as an inequality across pipes, so multi-feed junctions (e.g. `j_ost`,
four incoming pipes) are not over-determined (§A.4.5). Enabling it also required a physical
velocity cap (`max_velocity_m_s: 2.5`, previously a `100` workaround) and the energy-balance
demand reconstruction (§B.2.1) so every consumer's flow fits its connection pipe — the earlier
"mesh over-determination" reading of the infeasibility was disproved by IIS (O-8 resolved).

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
| Physics level | L3 nodal thermo-hydraulic | L3 + lightweight spatial-temperature offset (delivered); McCormick L3+ available but off for tractability | ✅ / ➕ |
| Horizon | T = 8760 h | 8760 hourly steps, `dt_h = 1.0` | ✅ |
| Topology | Brownfield fixed; only WP/EK/TES sized | Node/pipe topology fixed per YAML; investment only on WP/EK/TES | ✅ |

The network is modelled as a directed graph of **nodes** (`ThermalNodeBlock`) and
**pipe pairs** (`PipePairBlock`, a supply + return line). Node types are inferred from the
unified config: a node with `assets:` + `consumers:` is `mixed`, assets-only is
`producer`, consumers-only is `consumer`, neither is `junction`.

Supply temperature is a per-timestep **parameter** in the delivered model — but a
*spatially-varying* one: it equals the heating-curve value minus each node's cumulative
heat-loss drop from the plant (§A.4.3). Every heat↔mass-flow conversion `Q = ṁ · c_p · ΔT`
is thus **linear** in `ṁ` (no bilinear `ṁ·T` term, no McCormick, no `W` variables), keeping
the whole model a compact linear MILP.

An alternative **McCormick L3+ mode** (`network.temperature_propagation: true`) makes
temperature a genuine decision variable co-optimised with flow via enthalpy-flux `W = ṁ·c_p·T`
relaxed by the four McCormick envelope inequalities. It is exact-in-spirit and stays a true
MILP, but at 8760 h it is intractable (Part E.1) and is therefore **disabled** in the
delivered configs. It remains in the codebase for coarse-time-resolution or single-window
studies.

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

Each pipe `ṁ` is a fixed linear image of its `Q_delivered` (`Q = ṁ·c_p·ΔT`, ΔT a Param).
The local-generation term `ṁ_gen = Q_gen · 1000 / (c_p · (T_VL − T_RL))` stays linear because
both temperatures are Params in the delivered model. (Where a node's `T_return` is
independently a free Var — Stadtbach junctions such as `j_ost` — the generation term is
McCormick-relaxed per side via `constraint_builder.py::_attach_local_generation_mdot`, which
handles supply/return as independently Var-or-Param; a small, isolated use of McCormick that
does not affect tractability.) **Status: ✅.**

### A.4.3 Spatial supply-temperature drop — delivered method (➕ this session)

Supply temperature is a per-node, per-timestep **parameter** equal to the heating-curve
value minus the cumulative heat-loss temperature drop from the plant to that node. For each
pipe on the plant→node path:

```
ΔT_pipe(i,j) = U · L · (T_avg − T_ground) / (ṁ_design · c_p)          [K]
ṁ_design     = ρ · (π/4 · d²) · v_design      (v_design ≈ 1.0 m/s, from pipe diameter d)
T_VL,i       = T_curve − Σ_{pipes on plant→i path} ΔT_pipe            (node supply temp, Param)
```

Implemented in `scenario_runner._apply_spatial_temperature_offsets`, which BFS-walks the
plant→node paths (least-loss path at mesh convergence) and injects each node's cumulative
drop as its `T_supply_offset_c`. Because `T_VL,i` is a Param, the model gains no variables
and no bilinear terms — it stays a compact linear MILP that solves full-year on both
networks. The drop is monotonic downstream and physically sized (≈0.7 K deepest-leaf on
Memmingen, ≈1.8 K on Stadtbach). **Trade-off:** the drop uses a nominal design flow rather
than the solved flow, so temperature and flow are not co-optimised — acceptable given the
≈1 K magnitude. **Status: ✅ (both networks).**

**Alternative (implemented, disabled): McCormick L3+ co-optimised propagation.** Temperature
becomes a Var; per-pipe enthalpy flux `W = ṁ·c_p·T` is relaxed by the four-inequality
McCormick envelope (`utils/mccormick.py`), node mixing ties `T_VL,i` to incoming pipes'
`W_sup,out`, and the source pipe anchors to the curve `Param`. Exact-in-spirit and
MILP-safe, but ~6 M rows at 8760 h → intractable (Part E.1); off in the delivered configs.

### A.4.3b Node-pressure treatment note

Because supply temperature is a Param, the node-pressure propagation and TES pressure
coupling (below) operate on a linear model. Spatial pressure is delivered on Memmingen
(tree); Stadtbach's mesh is excluded (§A.4.5).

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

**Delivered on both networks.** Memmingen is a radial tree, so each node has one upstream
path and `p_supply,j = p_supply,i − Δp` is well-defined. Stadtbach is a multi-source mesh
(e.g. `j_ost` has four incoming pipes from `j_gtost`/`j_bmhkw`/`j_ava` + the bidirectional
`hkw_to_ost`). An earlier build reported `infeasibleOrUnbounded` and this was *attributed* to
the mesh over-determining node pressure; an IIS-based diagnosis (2026-07-09) proved that
attribution wrong. The mesh is handled correctly by three changes:

1. **Pressure-source classification + inequality propagation.** Every producer/pump-station
   node is a pressure source (primary producer fixed at its setpoint via equality; secondary
   producers and pump stations get a free, pump-boosted *floor* `p ≥ setpoint`). Supply/return
   propagation across non-source pipes is an **inequality** (`p_to ≤ p_from − Δp`), so a
   multi-feed junction takes the tightest consistent pressure instead of writing several
   conflicting equalities. This removes the over-determination without a loop/Kirchhoff
   formulation.
2. **Real velocity cap.** `max_velocity_m_s` was `100` (a workaround) which both inflated the
   PWL pressure-drop slopes and let unphysical flows hide a demand/pipe mismatch; set to the
   physical `2.5` m/s (matching Memmingen).
3. **Pipe-feasible demand.** The IIS ultimately pinned the conflict to specific consumers
   (e.g. Josefinum: 32 MW peak demand on a DN125 / 4.9 MW pipe). Those were the estimated
   consumers whose `merge_acron_sb.py` demand overshot their real connection pipes; the
   energy-balance reconstruction (§B.2.1) brings every estimated consumer to ≤73 % of its
   pipe capacity, so all flows are physically deliverable.

With these, Stadtbach solves with `pressure_drop: true` (72 h feasibility confirmed
2026-07-09: 10 incumbents; full-year via the campaign). The bidirectional-pipe
`flow_dir`/`m_dot_abs` MILP fix keeps `hkw_to_ost` direction-consistent under pressure.
**Status: ✅ (both networks; O-8 resolved — was a demand/parameter issue, not a mesh limit).**

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
- **Physics flags:** `milp_linearize: true`, `temperature_propagation: false` (spatial
  temperature via the per-node offset instead — §A.4.3), `pressure_drop: true`,
  `transport_delay: true`, `tes_pressure_coupling: true`, `max_velocity_m_s: 2.5`.

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
- **Data file:** `data/Stadtbach/stadtbach_acron_combined_cleaned.xlsx` (electricity price,
  grid CO₂, three waste-heat streams WRG1–3, outdoor temperature, per-zone demands). Built by
  `merge_acron_sb.py` then `clean_stadtbach_estimated_demand.py` (§B.2.1). System peak
  ≈ 201 MW, mean ≈ 73 MW, 640 GWh/a.
- **Physics flags:** `milp_linearize: true`, `temperature_propagation: false` (spatial
  temperature via the per-node offset — §A.4.3), `transport_delay: true`,
  **`pressure_drop: true`** (mesh handled by inequality propagation + pressure-source
  classification — §A.4.5), `max_velocity_m_s: 2.5` (physical; was a `100` workaround).
  Pipe diameters are real (graded DN600 trunk → DN125 leaves, swa WV640/650/660); enabling
  pressure required reconstructing the estimated-consumer demand (§B.2.1) so every consumer's
  flow fits its connection pipe.
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

- **Estimated-consumer demand reconstruction** (`clean_stadtbach_estimated_demand.py`,
  2026-07-09). Of the 24 consumers, **7 have direct `Waermeleistung` meters** and are used
  verbatim. The other **17 were "estimated"** by `merge_acron_sb.py`, which distributes a
  zone-total demand (computed from pump-station flow) across stations weighted by each
  station's supply-return ΔT. That method produced two physically impossible artefacts that
  block the hydraulic model: **(i)** the Netz-West zone total `Q_west = c_p·PSW_flow·ΔT` is
  driven by a pump whose flow is ~10.7× higher in August than January (summer recirculation,
  not delivered heat), so West demand *rose* in summer (`corr(demand, T_outdoor)` flipped
  positive); **(ii)** dividing a zone residual by a small per-station ΔT explodes individual
  hours, giving the estimated consumers peak/mean ratios of 6–8 (vs 2.7–3.9 for the metered
  ones) and peaks exceeding their real DN125–DN150 connection pipes for hundreds-to-thousands
  of hours (e.g. Josefinum 32 MW on a 4.9 MW pipe). The 17 estimated consumers are therefore
  reconstructed by **energy balance**: the delivered residual
  `Q_est(t) = (1−loss)·Σ producers(t) − Σ metered(t)` (loss = 10 %; the six producers are
  measured at −0.83 correlation with outdoor temperature and all feed only this modeled
  network) is **distributed across the 17 by connection-pipe hydraulic capacity** and inherits
  `Q_est`'s temperature-correct hourly shape. Result: every reconstructed consumer has
  `corr(T) = −0.84`, peak/mean ≈ 2.7, a uniform ≤73 % peak pipe utilisation (0 hours over
  capacity), and distinct de-duplicated series. Total modeled demand 640 GWh/a (10 % loss vs
  712 GWh production). *Assumption:* pipe capacity is used as the size proxy for an unmetered
  consumer (pipes are sized to peak demand); the metered 7 are untouched. This is the data
  step that makes `pressure_drop: true` feasible on Stadtbach (§A.4.5).

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
| §4.1.3 | TES pressure into net + charge/disch Δp | ✅ | pressure on both networks; explicit F4 head-coupling flag on Memmingen (its TES sits mid-tree). Stadtbach's `tes_sb` is at `j_hkw`, the fixed-setpoint reference node, where hydrostatic-head coupling is redundant |
| §4.1.4 | link to SOC dynamics | ✅ | E_max expression, C-rate power bound |
| §4.2 | heating-curve model + constraints | ◑ | scenario ✅, exact formula differs (O-2) |
| §4.3 | waste-heat + COP LUT | ✅ | analytical Lorenz surrogate (O-3) |
| §4.4 | DSM | ✅ | built, zero-valued per spec |
| §4.5 | Baseline | ✅ | BC-MM, BC-SB |
| §4 (P1) | spatial temperature drop | ✅ | delivered via per-node heat-loss offset (§A.4.3), both networks; McCormick L3+ off for tractability |
| §4 (P1) | transport delay | ✅ | linear lookback, both networks |
| §4 (P1) | spatial pressure | ✅ | both networks; Stadtbach mesh via inequality propagation + pressure-source classification (§A.4.5) |
| §5.1 | scenario matrix | ✅/➕ | 46 runs (20 base + HK expansion + endogenous) |
| §6.1–6.2 | KPIs (econ/eco) | ⏳ | `kpi_calculator.py` present; run post-campaign |
| §6.3 | hydraulic KPIs | ⏳ | temperature/flow/pressure/pump-energy on both networks; compute post-campaign |
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

- **Both networks solve full-year under the delivered (offset) physics.** Memmingen
  MM-S4-HK0 (endogenous siting) finds a real incumbent (obj ≈ 2.26 M €) with the
  spatial-temperature offset + pressure + delay; its spatial exports populate
  (`node_temperatures.csv` 8760×16, `nodes_state_hourly.parquet` 131 400 rows,
  `pipe_state_hourly.parquet` 858 480 rows) with a monotonic node-to-node temperature drop
  (j_1 81.05 °C → j_15 80.35 °C). Stadtbach SB-S6/SB-S7 solve with the corrected assets,
  spatial-temperature offset + delay (pressure off — §A.4.5); exports populated
  (`nodes_state_hourly.parquet` 289 080 rows, `pipe_state_hourly.parquet` ≈1.96 M rows).
- **MILP integrity.** The delivered model is fully linear (temperature is a Param): no
  bilinear terms, no McCormick in Memmingen, and only an isolated per-node McCormick block
  in Stadtbach where a junction `T_return` is a free Var. Every solve converged as a
  standard MILP.

## PART E.1 — CORRECTION & open tractability finding (2026-07-08)

**Correction to an earlier interim claim.** An earlier note that "MM-S4-HK0 / MM-S5-HK0
solve full-year" was **incorrect** — it was produced by the O-7 status-reporting bug, which
labelled a *no-incumbent* run as `status=ok, obj=0 €`. With O-7 fixed, a controlled
MM-S4-HK0 run (solo, 1200 s solve budget) returns the honest result: **no incumbent found.**

**Root cause (diagnosed, not yet resolved).** With the full L3+ physics stack active
(McCormick spatial temperature propagation on every pipe·timestep, F4 TES pressure coupling
via SOS2 PWL, transport delay, spatial pressure), the Memmingen 8760-h model expands to
**≈5.9 M rows × 4.0 M columns (16.6 M nonzeros)**. Gurobi's barrier spent ≈992 s on the
**root LP relaxation alone and did not converge** within 1200 s; branching therefore never
started (0 nodes explored) and no incumbent was produced. The negative "bound" (−1.55·10¹⁰)
is an artefact of the unfinished root LP, not a meaningful value.

**Why Stadtbach solves but Memmingen does not.** The decisive difference is
`tes_pressure_coupling: true` (F4, SOS2 PWL per timestep), enabled for Memmingen only. Its
per-timestep combinatorial + continuous load, stacked on the per-timestep McCormick and
delay constraints, is what pushes the Memmingen LP past the barrier's tractable size at
full hourly resolution. Because the dominant row count is per-timestep, this affects **all**
Memmingen L3+ scenarios (not only the endogenous S4/S5), so it is a genuine tractability
limit of the full-detail model at 8760 h, not a per-scenario feasibility bug.

**RESOLVED (2026-07-08) — lightweight spatial-temperature offset.** Root cause first
clarified: the apparent "Memmingen harder than the larger Stadtbach" paradox was because
Memmingen ran the full McCormick L3+ (1.48 M McCormick rows) while the Stadtbach paper-2
scenarios (which use `Stadtbach_topo.yaml`) had the L3+ flags off entirely — the flags had
been set on the unused `Stadtbach_L3_MILP.yaml`. Under equal physics Stadtbach's 32 pipes
would generate *more* McCormick than Memmingen's 14, i.e. Stadtbach is the structurally
harder network, as expected.

The chosen fix keeps supply temperature a **Param** (no McCormick, model stays at the
solvable ~4 M-row L3 size) but makes it **drop spatially**: each node receives a
`T_supply_offset_c` equal to the cumulative heat-loss temperature drop from the plant along
the trunk, precomputed as `ΔT_pipe = U·L·(T_avg − T_ground)/(ṁ_design·c_p)` summed over the
plant→node path (`scenario_runner._apply_spatial_temperature_offsets`, meshed-safe via the
least-loss path). Verified end-to-end on MM-S4-HK0 via the real run path:

- **Solves** to a real incumbent (was: no incumbent); `status=ok`, obj ≈ 2.26 M €.
- **Spatial drop present in the exported results:** at a mid-year hour, `T_supply` falls
  monotonically j_1 = 81.05 °C → j_15 = 80.35 °C (≈ 0.7 K cumulative), matching the computed
  offsets exactly.
- **Node/pipe spatial exports populate** (`node_temperatures.csv` 8760×16,
  `nodes_state_hourly.parquet` 131 400 rows, `pipe_state_hourly.parquet` 858 480 rows),
  resolving O-6.

`temperature_propagation` (McCormick L3+) is now **off** in `Memmingen_P2_base.yaml`;
transport delay and pressure drop remain on for Memmingen (DXF-real diameters). The offset
applies identically to both networks. Spatial pressure is now active on **both** networks.

- **O-8 — Stadtbach spatial pressure — RESOLVED (2026-07-09).** Stadtbach now runs with
  `pressure_drop: true`. The earlier `infeasibleOrUnbounded` was *not* a mesh over-determination
  limitation (that reading was disproved by IIS). The real causes were three, now fixed:
  (1) the pump-station pressure-source formulation (secondary producers/pump nodes now get a
  free pump-boosted pressure *floor* and propagation is an inequality, so multi-feed junctions
  are not over-determined); (2) `max_velocity_m_s` was `100` (a workaround that inflated PWL
  slopes and masked a demand/pipe mismatch) → set to physical `2.5`; (3) the estimated-consumer
  demand exceeded connection-pipe capacities (e.g. Josefinum 32 MW on a DN125), fixed by the
  energy-balance reconstruction (§B.2.1). Feasibility confirmed on a 72 h window (10 incumbents,
  2026-07-09); full-year via the campaign. Pipe diameters are real (graded DN600→DN125), not
  placeholder — the earlier placeholder note was incorrect. See §A.4.5.

*End of statement — updated 2026-07-09 for the CALION Paper 2 manuscript foundation.*
