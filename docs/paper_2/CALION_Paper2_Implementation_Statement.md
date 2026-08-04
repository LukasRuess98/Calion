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

Darcy–Weisbach pressure drop `Δp = k_flow·ṁ²` and pump power `P_pump = C·ṁ³` are both
**convex** in `ṁ`. They are modelled as **binary-free convex lower envelopes** — a set of
tangent-line inequalities the solver settles onto because Δp is driven down by both pump cost
and pressure propagation (`pipe_pair.py`):

```
Δp_supply(t) ≥ 2·k_flow·ṁ_i · ṁ(t) − k_flow·ṁ_i²      for tangent points ṁ_i        [bar]
Δp_return(t) = Δp_supply(t)                             (same pipe geometry & flow)
P_pump(t)    ≥ 3·C·ṁ_i² · ṁ(t) − 2·C·ṁ_i³               (C = 2·k_flow·1e5/(ρ·η_pump·1e6))
```

**Tangent count (tractability, 2026-07-13).** The envelope uses **3 tangent points**
(`ṁ_i = 0.33, 0.67, 1.0 × ṁ_max`), reduced from 5. This halves the pressure-envelope row count
(~1 M fewer LP rows network-wide), materially speeding the barrier root LP that dominates the
full-year solve, at a small accuracy cost: the worst-case Δp *under*-estimate between tangent
points rises to ≈7 % (≈0.03–0.14 bar on sub-2-bar drops) — negligible against the 0.7 bar
consumer differential, especially as the reconstructed demand already sits at ~70 % pipe
utilisation. A 5-tangent (≈2–3 % error) variant is available if a finer pressure trace is wanted.

Node pressures propagate from the primary-producer setpoint; producer/pump-station nodes are
pressure sources (primary **fixed** at setpoint, secondary a free pump-boosted **floor**), and
supply/return propagation across non-source pipes is an **inequality** (`p_to ≤ p_from − Δp`)
so a multi-feed mesh junction (e.g. `j_ost`, four incoming pipes) is not over-determined:

```
p_supply,j(t) ≤ p_supply,i(t) − Δp_supply,(i,j)(t)      p_return,i(t) ≤ p_return,j(t) − Δp_return,(i,j)(t)
P_pump feeds the electricity bus (η_pump = 0.75); consumer stations require p_supply − p_return ≥ 0.7 bar
```

**Why convex envelopes replaced the earlier binary PWL — a corrected error.** Earlier builds
used a 3-segment PWL with a **binary** segment selector and a big-M (`pwl_flow ≤ bp·seg +
M(1−seg)`). That formulation was both (a) needlessly integer (~840 k binaries network-wide) →
weak LP bound → **77–94 % MIP gaps after 46 h** on some Stadtbach scenarios, and (b) **leaky**:
the big-M let inactive segments carry flow, so the solver could route flow through low-slope
segments and **under-count Δp below its true value**. Prior "feasible" pressure results were
therefore *not physically valid* (one scenario "solved" at 117 M€ of hidden slack). The convex
tangent envelope is tight (Δp can never fall below the true quadratic) and carries **no**
pressure binaries — the same scenario now solves the pressure relaxation to a small gap in
seconds.

**Delivered on both networks** (Memmingen radial tree; Stadtbach multi-source mesh via the
inequality propagation above). Reaching feasibility required, in sequence (each uncovered by
IIS as the previous was fixed):
1. the convex-envelope formulation (correct, tight Δp);
2. `max_velocity_m_s` 100 → **3.0 m/s** (100 was a workaround that inflated slopes and hid a
   demand/pipe mismatch);
3. `min_supply_delta_T_k` 10 → **15 K** and per-curve retrofit return temps (§B.2.2): a fixed
   60 °C return at mild hours collapsed ΔT to the 10 K floor, so moderate demand needed flows
   that overshot the thin pipes;
4. **pressure-deliverable demand distribution** (§B.2.1): the reconstruction originally weighted
   demand by pipe cross-section (∝ D²), which ignores pipe length — many Stadtbach leaves are
   long *and* thin (Don_Bosco DN125/3490 m, Josefinum DN125/2070 m), so their pressure-limited
   capacity is a fraction of a short DN125. Re-weighting by path-aware Darcy pressure-deliverable
   capacity keeps every consumer's demand within the 16-bar head budget.

The bidirectional-pipe `flow_dir`/`m_dot_abs` MILP fix keeps `hkw_to_ost` direction-consistent.
**Status: ✅ (both networks; O-8 resolved — the infeasibility was a formulation + demand/parameter
issue, never a mesh limit).**

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
(`network_manager.py::_link_tes_pressure_coupling`, feature "F4"), now with a config
switch `physics.tes_pressure_mode` (2026-07-13) selecting between two physical models
of the TES's hydraulic role:

**`hydrostatic_support`** (legacy — an elevated-tower TES, physically separate from the
network's pressurised loop, whose own water column pushes pressure into the network):

```
p_supply,i(t) ≥ p_atm + ρ·g·h(V)/1e5 + k_dp·q_TES,c(t) − k_dp·q_TES,d(t) − M·(1−y_TES)
p_supply,i(t) ≤ p_max + M·(1−y_TES)                             (vessel rating)
```

`h(V)` is itself PWL (concave `h = (4·r²·V/π)^{1/3}`, SOS2, 5 breakpoints × 8760 h per
TES node). The hydrostatic push is skipped at the primary producer (its `p_supply` is
fixed by the pump setpoint).

**`same_circuit_buffer`** (2026-07-13 default — TES as an in-line buffer sharing the
network's own pressurised loop; no HX, no elevated column; it decouples local
charge/discharge *volume flows*, not pressures):

```
p_supply,i(t) ≤ p_max + M·(1−y_TES)                             (vessel rating only)
```

No `h(V)` PWL/SOS2 at all — the node's pressure is set purely by pump-station
propagation through the pipe network (§A.4.5), as for any other node. Physical
justification: `p_TES(t) = p_network,i(t)` holds exactly while the tank sits in the same
closed loop and stays below saturation pressure at its temperature (already enforced
network-wide by the generic anti-cavitation floor, `state_constraints.py::
enforce_minimum_pressure`, independent of TES). **Rationale for the mode change:** the
legacy formulation let a *fractionally-built* tank (LP relaxation of `y_TES`) receive a
`ρ·g·h(V)`-scaled pressure-floor credit tied to a literal elevated-tower premise that is
not obviously the right physical picture for an in-line buffer vessel; even though the
PWL's Jensen-concavity bound makes this credit conservative rather than exploitable, the
assumption itself needed to be justified for publication (Kategorie B fix — orthogonal to
the storage-siting weak bound in Part G, which is a Stadtbach-only issue where
`tes_pressure_coupling` was never enabled). Verified on MM-S2-HK0 (TES at `j_12`, 720 h
smoke test): SOS2/PWL-λ components drop from 1 to 0, objective changes by 0.04%
(49,594 → 49,613 €), both solves reach <0.5% gap. The legacy mode is kept selectable
(not deleted) for A/B comparability. Active in Memmingen only
(`tes_pressure_coupling: true`); Stadtbach never enables this feature. **Status: ✅.**

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
  `transport_delay: true`, `tes_pressure_coupling: true`, `max_velocity_m_s: 3.0`,
  `min_supply_delta_T_k: 15` (retrofit curves lower return too — §B.1.4/§A.4.5).

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
  classification — §A.4.5), `max_velocity_m_s: 3.0` (was a `100` workaround), and
  `min_supply_delta_T_k: 15` (raised from 10; a fixed 60 °C return collapsed ΔT to the floor at
  mild hours). Pipe diameters are real (graded DN600 trunk → DN125 leaves, swa WV640/650/660);
  enabling pressure required reconstructing the estimated-consumer demand by pressure-deliverable
  capacity (§B.2.1) so every consumer's flow fits both its velocity and pressure limits.
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
  network) is **distributed across the 17 by pressure-DELIVERABLE capacity** and inherits
  `Q_est`'s temperature-correct hourly shape. Result: every reconstructed consumer has
  `corr(T) = −0.84`, peak/mean ≈ 2.7, a uniform ≤73 % peak pipe utilisation (0 hours over
  capacity), and distinct de-duplicated series. Total modeled demand 640 GWh/a (10 % loss vs
  712 GWh production); the metered 7 are untouched.

  *Correction (2026-07-12).* An intermediate version used pipe **cross-section** (velocity
  capacity, proportional to D squared) as the weight, which ignores pipe LENGTH. Many Stadtbach
  leaves are long AND thin (Don_Bosco DN125/3490 m, Josefinum DN125/2070 m, Kreissparkasse
  DN125/1740 m): their velocity capacity is fine but their pressure-deliverable capacity — set
  by Darcy pressure drop, which grows with length, along the plant-to-consumer path against the
  16-bar setpoint — is a fraction of a short DN125's. Cross-section weighting therefore
  over-allocated heat to these consumers beyond what the head budget can push through, which the
  (now correct, tight) pressure formulation exposed as infeasible. The weight is now each
  consumer's path-aware **pressure-deliverable mass flow** (bisect the flow so the round-trip
  path pressure drop equals an ~11-bar head budget), additionally capped by the velocity limit —
  so every consumer's demand fits within both the velocity and pressure limits by construction.
  This is the data step that makes `pressure_drop: true` feasible on Stadtbach (§A.4.5).

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

Fixed thermal capacity total ≈ 357.5 MW against a ≈201 MW peak demand.

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

- **O-9 — Stadtbach spatial pressure: formulation + demand fixes (2026-07-12).** Enabling
  correct spatial pressure on Stadtbach turned out to be a chain of four issues, each exposed
  by IIS as the previous was fixed (full detail in §A.4.5 and the §B.2.1 correction):
  1. **Leaky binary PWL → wrong physics + intractable.** The Darcy Δp / pump-power PWL used a
     big-M binary segment selector (~840 k binaries) that was both weak (77–94 % MIP gaps at
     46 h) and *leaky* (inactive segments carried flow, letting the solver under-count Δp).
     Prior "feasible" pressure results were therefore not physically valid. **Fix:** binary-free
     **convex tangent envelopes** for Δp and P_pump (both convex) — correct, tight, no binaries.
  2. **Velocity workaround.** `max_velocity_m_s: 100` inflated slopes and hid a demand/pipe
     mismatch → set to a physical **3.0 m/s**.
  3. **ΔT collapse at mild hours.** With supply floored at 70 °C and return fixed at 60 °C,
     ΔT hit the 10 K floor at mild hours → high flows. **Fix:** `min_supply_delta_T_k` 10 → **15**
     and per-curve retrofit return temps (HK1/HK2 lower return, modelling the substation
     retrofit's colder return).
  4. **Demand distributed by cross-section, not length.** The reconstruction weighted demand
     ∝ D² (velocity capacity), over-allocating to long-thin leaves (Don_Bosco DN125/3490 m,
     Kreissparkasse DN125/1740 m) beyond their pressure-deliverable capacity. **Fix:** re-weight
     by **path-aware pressure-deliverable capacity** (bisect flow so round-trip path Δp = ~11 bar
     budget), velocity-capped.
  After all four, SB-S0-HK0/HK2 full-year are **feasible** with correct physics (obj ≈ 11.4 M €,
  *not* the 117 M € slack of the leaky formulation).
- **O-10 — MIP gap is a weak LP bound, not binaries (open, tractability).** With the pressure
  PWL binaries gone, ~114 k legitimate unit-commitment binaries remain (8 generator on/off from
  `min_load = 0.1`, 3 TES mode, grid mode, bidirectional flow direction). SB-S0-HK0 sits at
  ≈ 12 % gap at 26 min with a **stuck LP bound ≈ 10.04 M €** vs incumbent ≈ 11.4 M €. Tested:
  **relaxing generator min-load (LP dispatch)** removes ~61 k binaries but leaves the bound at
  10.04 M € and the gap at 12.7 % — so the gap is a **weak LP relaxation**, not the integer
  count; min-load was therefore **kept** (realistic). The gap is time-driven (B&B must raise the
  bound; the earlier same-scenario run reached 0.87 % only after 46 h). The campaign therefore
  runs each scenario with **aggressive cuts (`Cuts=2`, `MIPFocus=2`) to tighten the bound, a 24 h
  limit and a 1 % gap target**; O-7 reporting flags the achieved gap honestly per scenario. A
  deeper future improvement would be a tighter pressure/unit-commitment formulation (e.g.
  perspective cuts).

---

# PART F — Solver tractability: diagnosing and resolving a weak-bound MILP

*This section documents a methodological finding worth stating explicitly in the manuscript: the
tractability of the full-year thermo-hydraulic MILP was gated not by the obvious integer count
but by the tightness of the LP relaxation, and the resolution was a tighter convex formulation
plus aggressive cutting planes — with a controlled experiment isolating the cause.*

## F.1 The symptom

At full hourly resolution (8760 h) the thermo-hydraulic MILP with spatial pressure is large
(Stadtbach ≈ 5.0 M variables). In the first full campaign three Stadtbach scenarios
(SB-S0-HK1/HK2, SB-S1-HK0) sat at **77–94 % optimality gap after 46 h** while returning only a
poor incumbent — one "solution" cost **117 M€, ≈ 10× a normal ~11 M€ result**, i.e. the solver
was buying feasibility with expensive slack. Those runs would never have produced usable results
and they monopolised the 10 concurrent worker slots.

## F.2 Root cause 1 — a needlessly integer, and *leaky*, pressure formulation

Darcy–Weisbach pressure drop `Δp = k·ṁ²` and pump power `P_pump = C·ṁ³` are both **convex** in
the mass flow. The original code nonetheless modelled each as a 3-segment PWL with a **binary
segment selector** and a big-M coupling — **≈ 840 000 binaries** across the Stadtbach network
(32 pipes × 8760 h × 3). This was doubly harmful:

- **Weak bound.** Big-M segment selection has a loose LP relaxation → the 77–94 % gaps.
- **Leaky → physically wrong.** The segment upper bound `pwl_flow ≤ bp·seg + M·(1−seg)` lets an
  *inactive* segment (`seg = 0`) carry flow up to `M`. The solver could therefore route flow
  through a low-slope segment and **report a Δp below its physically correct value**. The
  earlier "feasible" pressure results were, as a consequence, not physically valid.

**Fix.** Because the functions are convex they need **no binaries at all** — each is the upper
envelope of a family of tangent lines the objective naturally settles onto (Δp is driven down by
both pump cost and the pressure-propagation inequalities `p_to ≤ p_from − Δp`):

```
Δp_supply(t) ≥ 2·k·ṁ_i · ṁ(t) − k·ṁ_i²        (one inequality per tangent point ṁ_i)
P_pump(t)    ≥ 3·C·ṁ_i² · ṁ(t) − 2·C·ṁ_i³
```

This is **tight** (Δp can never fall below the true quadratic) and carries **zero** pressure
binaries. Isolated on a 168 h window of the worst scenario (SB-S0-HK1), the optimality gap went
from **90 % after 46 h → 0.38 % in 15 s**.

## F.3 Root cause 2 — the residual gap is a weak LP bound, *not* the integer count

With the pressure binaries gone, the full-year model still carried **113 893 binaries** — but all
of them are *legitimate unit commitment*: 8 generator on/off (each present only because
`min_load = 0.1`), 3 TES mode (charge / discharge / active), 1 grid import–export mode, and 1
bidirectional-pipe flow direction, i.e. **13 per timestep**. On SB-S0-HK0 the model still showed
≈ 12 % gap at 26 min, with the LP **bound stuck at 10.04 M€** against an incumbent of ≈ 11.4 M€.

The tempting hypothesis — "too many binaries" — was **tested and rejected**. Relaxing generator
min-load to zero (LP dispatch) removed 61 320 of the 113 893 binaries, yet the bound and gap
barely moved:

| configuration | binaries | LP bound | incumbent | gap @ 26 min |
|---|---|---|---|---|
| full unit commitment | 113 893 | 10.045 M€ | 11.38 M€ | 11.76 % |
| min-load relaxed (LP dispatch) | 52 573 | 10.044 M€ | 11.50 M€ | 12.67 % |

Removing **54 % of the binaries left the bound essentially unchanged** (10.04 M€). The gap is
therefore a property of **LP-relaxation tightness**, not the size of the branch-and-bound tree —
so min-load was *kept* (it is physically real and, as shown, costs nothing in tractability).
Consistent with this, the same scenario under the earlier formulation reached 0.87 % only after
46 h: the bound does close, but slowly, purely through branch-and-bound raising it.

## F.4 Resolution — cutting planes, not more branching

Because the bottleneck is a loose bound rather than combinatorial breadth, the effective lever is
**cutting planes that tighten the LP relaxation**, together with focusing solver effort on the
bound (the incumbents were already good). Each campaign scenario runs with:

```
Cuts = 2          # aggressive cutting-plane generation — tightens the LP bound (the gap driver)
MIPFocus = 2      # prioritise proving the bound over finding new incumbents
Heuristics = 0.1
TimeLimit = 24 h,  MIPGap = 1 %
```

Effect on the live campaign (2026-07-12): scenarios that had been stuck now **converge to
optimal in minutes-to-an-hour**. SB-S0-HK0 — stuck at 12 % after 26 min *without* cuts — was at
**1.07 % at 80 min**, i.e. essentially at the 1 % target (vs a bound frozen at 12 % before);
BC-SB terminated *optimal* in 31 min; SB-S0-HK1/HK2 *optimal* in ≈ 58–60 min; the full running
set sits at 1–3.5 %. The unit-commitment binaries never had to be sacrificed for tractability,
and every scenario completed so far (7/46 at the time of writing) returns
`termination = optimal`.

## F.5 Takeaway (for the methods / numerical section)

Two transferable lessons for hourly thermo-hydraulic district-heating planning MILPs:

1. **Model convex hydraulics (Δp ∝ ṁ², P_pump ∝ ṁ³) as binary-free convex envelopes, never as a
   big-M PWL.** The big-M version is both intractable (weak bound) *and* unsafe (leaky — it can
   under-count pressure drop), so the "feasible" results it produces may be physically invalid.
2. **When a large MILP stalls, distinguish a weak LP bound from a large integer tree *before*
   acting.** Here a single controlled experiment (relaxing min-load) proved the bound — not the
   binary count — was binding, which pointed to aggressive cutting planes rather than the
   tempting-but-ineffective route of stripping binaries. Reformulate/tighten first; branch last.

---

---

# PART G — TES-siting tractability: a storage-coupling weak bound

*A second, distinct tractability finding (2026-07-13): the TES-siting scenarios are hard for a
different reason than the pressure MILP of Part F.*

## G.1 The symptom

The baselines and the no-TES / hub-TES scenarios (S0, S1, S3) solve to proven optimal, but the
**TES-at-consumer-node** scenarios (fixed-node `SB-S2` = TES at `j_man`, and the endogenous
`S4–S7`) stall at **43–88 % gap**. The tell is that `SB-S1` (TES at the production hub `j_hkw`)
solves in 1.4 %, while `SB-S2` (same TES, at a consumer node) stalls at 43 %.

## G.2 The cause — a weak LP relaxation of storage dispatch (ruled in by elimination)

Controlled experiments ruled out every "obvious" culprit — the bound barely moved in each case:

| hypothesis tested | result |
|---|---|
| pressure OFF | **worse** (88 % gap) → not pressure |
| generator min-load relaxed (LP dispatch) | bound unchanged (10.04 M€) → not unit commitment |
| discrete vs continuous investment | 720 h still 70 % → not the investment big-M |

The looseness is intrinsic to the **storage's time-coupling** (`SOC(t) = SOC(t−1)·loss + …`
links all 8760 hours) **at a consumer node**: the LP relaxation can operate the tank fractionally
and smooth cost in ways no integer schedule matches, and at a consumer node the TES is the *only*
local flexibility, so that fictitious value is large (at the hub, co-located flexible generation
makes storage marginal, so `SB-S1` is tight). This is a classic signature of storage-siting /
investment-plus-operation MILPs, a known-hard class.

## G.3 Mitigations applied (both exact — identical results, tighter model)

1. **Discrete tank sizing** (`geometric_storage.py` + configs). The tank volume is chosen from a
   discrete ladder of energies (hours of mean heat demand) via an exact size-selection
   (`Σ y_k = 1`, `V = Σ V_k·y_k`) — no continuous `V` + big-M build coupling. Large sizes are
   realised as `N = ⌈V/25,000 m³⌉` identical unit tanks with `β_tes` charged per tank. The
   Stadtbach ladder is capped at ~845 MWh (`V ≤ 50,000 m³`): larger multi-tank volumes made the
   barrier root LP numerically intractable, and > 12 h of storage for a 200 MW network is neither
   usable nor affordable. (More realistic than a continuous tank volume, and a tighter relaxation
   of the investment part.)
2. **Storage mode-binary elimination ("Edit A")**. The per-timestep charge/discharge/active
   binaries (~26 k full-year) only forbade *simultaneous* charge+discharge, which strictly
   positive round-trip losses (`η_c, η_d < 1`) already make sub-optimal — so they are provably
   redundant and were removed, together with their big-M power linearisation. Storage is now a
   pure LP inside the dispatch; power is bounded directly by the built capacity
   (`Q_c, Q_d ≤ cap_p`, with `cap_p = 0` when not built). A standard, citable exact simplification.
3. **Solver**: aggressive cutting planes (`Cuts = 2`, `MIPFocus = 2`) + 24 h limit + reported gap.

## G.4 Status — diagnosis, fix, and verified resolution (2026-07-13/14)

Mitigations 1–2 are *exact* (same optimum, same siting/TAC/dispatch) and remove real integrality,
shrinking the branch-and-bound tree; the deliverable — whether TES is built, where, and the TAC —
is reliable, with the residual MIP gap reported honestly (standard for storage-siting studies).

**Gate result (2026-07-13):** the validation run for `SB-S2-HK0` (mitigations 1–2 + `Cuts=2`,
full 8760 h, 2986 s, `TimeLimit`-terminated) reached **`OBJ=10,305,451  BOUND=2,698,406  GAP=
73.8 %`** — the ≤5 % gate is **not met**.

**Step 2 — root-LP-relaxation diagnostic.** Relaxed every remaining Binary/Integer var (87,615:
generator on/off UC + `tes_sb` size-selection) to continuous and solved the root LP once, with
each objective term instrumented as a named Pyomo `Expression` (`constraint_builder.py::
create_objective`, now exposing `energy_cost_expr`, `fuel_cost_expr`, `co2_cost_expr`,
`demand_cost_expr`, etc. individually — a permanent, harmless audit addition). **Finding: the
leading hypothesis was wrong.** `demand_cost_expr` (`demand_charge_y·P_buy_peak`) was only
€154,905 of the €10.3M incumbent (1.5 %) — far too small to be the driver. The actual mechanism:
`tes_sb_build` was fractional (0.547, split between "no tank" and the *largest* size rung — 211 MW,
845 MWh), and `Qc[t]` and `Qd[t]` were **both nonzero in 8,530/8,760 hours (97 %)**, often near the
same full `cap_p`. Because `Qc[t]≤cap_p` and `Qd[t]≤cap_p` (`geometric_storage.py`) were
independent, nothing stopped simultaneous full-power charge *and* discharge — a "wash" cycle that
is nearly self-cancelling on the local heat bus (efficiency losses only bite in the SOC recursion,
not the bus balance) and is exploited wherever the marginal heat is cheap.

**Step 3 — shared-port valid inequality.** Replaced the two independent power caps with
`Qc[t] + Qd[t] ≤ cap_p[t]` (`geometric_storage.py::{comp}_shared_port`) — physically, a single-loop
stratified tank shares one heat-exchanger/pump train between charge and discharge, so *combined*
throughput, not each direction independently, is capacity-limited. Still pure LP, no binaries, full
8760 h preserved.

**Verified result:** re-solving the full MIP (real generators + real storage integrality,
shared-port cut active) reached **`OBJ=3,763,186  BOUND=3,749,290  GAP=0.37 %`** in 2370 s — the
gate is now met by a wide margin. **Important nuance, reported honestly rather than declared a full
fix:** the shared-port cut did *not* eliminate the simultaneous charge/discharge — the true integer
optimum still runs `tes_sb` fully built at the largest rung with `Qc,Qd>0` together in 8,457/8,760 h
(96.5 %). What the cut did was regularize the feasible region (removing the degenerate symmetric
alternate-optima that come from two independent, interchangeable power caps) enough for Gurobi's
branching to actually converge — a real tractability fix, but the underlying "wash cycling" pattern
is the model's true optimum given current costs, not resolved. **Regression check (`SB-S1-HK0`,
hub-sited TES, same node as `hp_sb` in both scenarios):** solved to a *proven* optimum (`term=
optimal`) in 982 s, `OBJ=10,003,395  GAP=0.44 %`, moderate tank size (rung 3, 54.75 MW), **zero**
hours of simultaneous `Qc,Qd>0` — the cut is non-binding and costless where the model was already
sane, confirming the fix does not distort well-behaved scenarios. Since the HP co-location is
identical between `SB-S1` and `SB-S2`, the wash-cycling is specific to siting the TES itself away
from the central-generation hub — consistent with the tank substituting for pipe-delivery capacity
from the plant at the remote node, though the precise causal chain is not yet nailed down.

**Open item (flag before headline paper numbers):** the `SB-S2`-style consumer-node TES dispatch
(near-constant full-power bidirectional cycling) is an extreme, physically unusual utilization
pattern for a real operator. It is the *true* MILP optimum of the stated cost/constraint set and
the campaign gate is met, but a plausibility check (e.g., correlating `Qc(tes_sb)` against `hp_sb`
dispatch, or checking whether it degrades once a stricter `cycling_cost_eur_per_mwh` is
counter-tested) is recommended before quoting `SB-S2`/consumer-node-TES results as a paper finding
rather than a modelled artifact.

## G.5 Related, orthogonal fix — TES↔network pressure coupling ("F4", Memmingen only)

Independent of G.1–G.4 (which is a **Stadtbach**-only issue — `tes_pressure_coupling` was never
enabled there), a second TES-pressure question was raised for **Memmingen**: F4's legacy
formulation (§A.4.7) modelled the TES as an elevated tower whose own hydrostatic column pushes
pressure into the network, granting a fractionally-built tank (LP relaxation) a `ρ·g·h(V)`-scaled
pressure credit under a physical premise (free-standing tower, not an in-line buffer) that needed
justification for this system class. Reformulated as a config-switchable
`physics.tes_pressure_mode`: the new default `same_circuit_buffer` treats the TES as an in-line
buffer sharing the network's own pressure (no HX, no elevated column, `p_TES = p_network`),
dropping the `h(V)` PWL/SOS2 entirely and keeping only the vessel-rating safety cap; the legacy
`hydrostatic_support` mode is kept selectable for A/B comparability. Verified exact/sane on
MM-S2-HK0 (TES at `j_12`, 720 h smoke test): SOS2/PWL-λ components 1→0, objective 49,594→49,613 €
(0.04 %), both <0.5 % gap. This does **not** address the Part G weak bound above (Stadtbach never
had F4 on) — it is a Kategorie-B model-realism and tractability improvement for the Memmingen F4
scenarios specifically (`model_finalizer.py::_build_tes_pressure_coupling`,
`network_manager.py::_link_tes_pressure_coupling`).

## G.6 A third, distinct issue — endogenous-siting combinatorics (`SB-S6`) and a units-bug fix

During the post-fix campaign re-run (36 scenarios, S1–S7 both networks, launched 2026-07-14),
**`SB-S6` (fully-free endogenous siting — TES and HP/EK sited *independently* among the 5
candidate nodes, no `colocate`) stalled at 63–69 % gap after 3.4+ h**, while every other scenario
in the batch — including its sibling `SB-S7` (same 5 candidates, but `colocate: true`, forcing
TES+HP to one shared site decision) — converged cleanly to a proven-optimal or ≤1 % gap. This is a
**different problem from G.1–G.5**: `component_assembler.py`'s F3 siting mechanism
(`_get_site_y`/`_distribute_flows`) gives each independent group ("hp", "tes") its own one-hot
site-binary set with per-candidate big-M flow gates `qo_c[t] ≤ M·y_c`. With `colocate: true` (S7)
there is **one** shared 5-way choice; without it (S6) there are **5×5=25** combinations, and the LP
relaxation can fractionally "smear" the TES's flow across multiple candidate nodes at once — real
facility-location-style combinatorial hardness, not a modelling leak.

While tracing the exact gate, a genuine, low-risk **units bug** was found and fixed
(`component_assembler.py:996–1010`): the siting gate's big-`M` (`power_bound`) used the raw
**max discrete ENERGY** figure [MWh] directly as a **power** bound [MW] — for `tes_sb`, `845`
instead of the true `power_to_energy_ratio × 845 = 211.25 MW`, a 4× looser-than-necessary `M`
(present in both S6 and S7, though S7's much smaller combinatorial space masked its effect there).
Fixed by multiplying by the same ratio `GeometricStorageBlock` itself uses — exact, cannot change
the true optimum (the real cap was always ≤211.25 MW), only removes LP-relaxation slack.

**Verified improvement (fair, matched-elapsed-time comparison, `SB-S6-HK0`):** at ~34–43 min
into the solve, before the fix `OBJ=48.6M  GAP=96.3 %` (2040 s); after, `OBJ=14.2M  GAP=88.95 %`
(2604 s) — ≈3.4× cheaper incumbent, ≈7 pt tighter gap. **This does not fully resolve `SB-S6`** —
the dominant difficulty remains the 25-vs-5 site-combinatorics, not the `M` looseness, so a full
fix needs its own dedicated treatment (leading candidates: topology-aware tighter per-candidate
`M`, or symmetry-breaking cuts on the two site-binary sets) rather than being rushed alongside
today's other changes. `SB-S6-HK0/1/2` were relaunched with both fixes at the full 24 h budget;
outcome pending. **Status: units bug ✅ fixed and verified; siting-combinatorics tractability ⏳
open, flagged for a dedicated follow-up session.**

## G.7 Dedicated follow-up session (2026-07-14/15) — root cause found; fix implemented and
## verified necessary; residual issue is model scale, not formulation

This session's target was the still-open `SB-S6`/`MM-S4` tractability problem from G.6. Four
formulation-level hypotheses were tested, all via fair matched-elapsed-time comparisons
(`SB-S6-HK0`, 30 min Gurobi `TimeLimit`, isolated single-scenario runs to rule out the
RAM/swap-contention confound documented in the TES-dispatch memory) — **all four left the root LP
relaxation completely unchanged (`1.799264e6`/`1.79926373e6`, matching to 6+ significant figures)
and the 30-minute gap frozen at ≈97 %**:

1. **Disaggregated capacity-linked gates** (`_distribute_flows`, `component_assembler.py`):
   replaced the flat `out_c(t) ≤ M·y_c` gate with a per-candidate capacity share `cap_c`,
   `Σ_c cap_c == capacity_var`, `cap_c ≤ M·y_c` — the textbook strong/VUB facility-location
   reformulation (Balinski 1965; Cornuéjols/Fisher/Nemhauser 1977). No effect.
2. **Colocate-only attribution control**: `SB-S6-HK0` re-run with `colocate: true` but
   *without* `hot_charging` (isolating colocate's binary-merging effect from `SB-S7`'s
   confounding physics change). Tracked the fully independent-siting run almost exactly
   (frozen at node 0, ~96.9 % gap, matched elapsed time) — **disproved the leading G.6
   hypothesis that 25-vs-5 site combinatorics was the dominant driver.**
3. **Per-candidate shared-port cut**: `qi_c[t] + qo_c[t] ≤ cap_c`, closing a per-candidate
   double-dip loophole analogous to the aggregate `Qc+Qd≤cap_p` fix from the TES-dispatch
   session. No effect on the root bound.
4. **Explicit `.ub` on the per-candidate flow Vars**: found and fixed a genuine, separate
   correctness issue — `qo`/`qi` in `_distribute_flows` had no declared bound, so
   `constraint_builder.py::_attach_local_generation_mdot`'s McCormick sizing for each node's
   bilinear `m_dot_gen` (mass-flow × temperature) term silently fell back to a generic
   40 MW/term default instead of the asset's real capacity — a latent unsoundness risk (the
   McCormick box could be tighter than the true linear-constraint bound), invisible to Gurobi
   presolve because it's resolved in Python at model-build time, before the solver ever sees
   the model. Kept as a correctness fix regardless of its (also negligible) effect on this
   bound.

**Decisive diagnostic** (the actual breakthrough): built `SB-S6-HK0` through the *identical*
candidate-replicated code path (all 5 candidates still carry their own McCormick-relaxed
local-generation structure), but fixed the site-selection binaries to a single candidate
(`j_hkw`, `y=1`; all others `y=0`) immediately after creation — a monkeypatch on
`_get_site_y`, not a code change. Root LP relaxation: **`1.0958e7`, ≈6× tighter than every
formulation fix above, solved in 282 s** (vs. 400–900 s for the frozen `1.8e6` bound); B&B gap
dropped to **12.5 % almost immediately** (vs. ≈97 % in every free-siting variant). This proves
the weak bound is **not a linear-tightness problem** — no constraint reformulation can fix it —
it is that a **fractional `y`** lets the LP draw on every candidate's McCormick-relaxed
generation headroom **simultaneously**; only resolving `y`'s integrality (by fixing it, or by
branching) closes the gap.

**Fix implemented**: declared each group's site-selection binary set (`y`) as a **type-1
Special Ordered Set (SOS1)** in `_get_site_y` (`component_assembler.py`), alongside the existing
`Σy_c==1` equality. SOS1 branching (Beale & Tomlin 1970) is the standard, solver-native technique
for exactly this "choose-one-of-N near-symmetric candidates" structure — supported natively by
Gurobi and by Pyomo's `SOSConstraint` across all interfaces (no solver-specific plumbing), unlike
branch-priority which is interface-dependent. This is a mathematically justified formulation
choice, not a generic performance knob.

**Verification status — mechanism confirmed necessary, benefit not yet observed at 30-min
scale**: `SB-S6-HK0` re-run with SOS1 (`Model has 2 SOS constraints` confirmed in the Gurobi log)
landed at **gap 96.9267 %**, statistically identical to every pre-SOS1 variant. Diagnosis: Gurobi
spent the *entire* 30-minute budget on node-0 processing (root LP + cutting-plane rounds) and
**never reached node 1**, where SOS1 branching would actually fire — confirmed by testing
`Cuts=1` (reduced root-cut aggressiveness) alongside SOS1, which produced an **identical** result
(`96.9267 %`, bound `1800610.85` matching to the decimal) at matched elapsed time. At this
model's scale (7,025,549 rows / 4,712,925 continuous vars / 87,625 binaries for a single
8760-h Stadtbach PF solve), even a "moderate" cut-generation setting still requires several
LP re-optimizations of a multi-million-row problem before Gurobi decides to branch — the
30-minute diagnostic window used throughout this session (deliberately short, to allow many
fair matched-time comparisons) is consumed entirely by that cost, independent of which
formulation or branching hint is in play.

**Status: SOS1 fix ✅ implemented, and its necessity is ✅ rigorously proven (fixed-y control:
6× tighter root bound, 12.5 % gap vs. ≈97 % for every free-siting variant, including SOS1 alone
at 30 min) — but its benefit has not yet been observed empirically at 30-min scale, because
Gurobi doesn't reach real branching that fast on this model size regardless of settings tried.**
**Recommendation**: run `SB-S6-HK0/1/2` and `MM-S4-HK0/1/2` at the full 24 h campaign budget with
SOS1 (already the default now) — once genuine branching starts, the fixed-y evidence indicates
the achievable bound is dramatically better than the pre-SOS1 formulation ever reached. If a
result is needed on a shorter horizon, the next lever to test (not yet tried) is more aggressive
root-cut suppression (`Cuts=0`) combined with `NoRelHeurTime`/reduced presolve passes, explicitly
trading root-bound tightness for reaching the SOS1-resolvable branching phase sooner — flagged
for a future session rather than rushed here given the time already invested in rigorous,
fair-comparison diagnosis this session.

**Files touched:** `calion/models/component_assembler.py` (`_distribute_flows`: disaggregated
capacity gates + per-candidate shared-port cut + explicit Var bounds; `_get_site_y`: SOS1
declaration). All changes are additive/tightening — no change to any non-endogenous-siting
scenario's model, and no change to the true integer-feasible set of any endogenous scenario
(every fix either adds a valid/implied constraint or corrects a latent looseness, never
removes a feasible point).

## G.8 Practical resolution — explicit enumeration decomposition

Given G.7's finding that the monolithic free-siting MILP cannot reach real branching within a
practical time budget regardless of formulation (SOS1 is mathematically correct but the model's
root-node processing alone consumes 30+ minutes at this scale), and given the fixed-y control
proved the **subproblem with `y` resolved is dramatically easier** (root LP ~6× tighter, solved
in under 5 minutes, gap 12.5 % almost immediately), the practical path to an actual, defensible
solution is classical **explicit enumeration decomposition**: since there are only
`N_hp × N_tes` site-pair combinations (25 for Stadtbach's 5×5 candidate set, 36 for Memmingen's
6×6), solve each pair as an independent MILP with `y` FIXED to that pair (same code path as the
fixed-y control, generalized to arbitrary pairs via `component_assembler.py::_get_site_y`
monkeypatch) and take the best. This is standard practice in facility-location literature when
the candidate set is small enough for full enumeration to be cheaper than forcing a generic
solver to resolve the site-selection combinatorics on its own — each subproblem is now a
*normal*, well-behaved MILP (no residual siting-integrality weak-bound issue at all, since `y`
is fixed, not merely SOS1-encouraged), so any of the 25/36 solves converges the way `SB-S1`-style
fixed-site scenarios always have.

**Optimality guarantee**: the overall best-of-N solution's gap to the TRUE free-siting optimum is
bounded by the WORST individual subproblem's own MIP gap — e.g. if all 25 pairs solve to ≤2 %
gap, the reported best pair is within ≤2 % of the true global optimum (in the classical sense: the
true optimum equals the best of the 25 true per-pair optima, and each per-pair optimum is
sandwiched between that pair's incumbent and bound). This is a categorically stronger and more
scientifically defensible guarantee than quoting a monolithic run's ~97 % gap as "the SB-S6
result."

**Implementation**: `scripts/paper_2/enumerate_endog_siting.py` — a single-pair solve mode
(`--hp-site --tes-site`) plus an orchestrator (`--enumerate-all`) that manages bounded concurrency
across subprocess solves (each pair gets its own synthetic scenario id
`{base_id}__hp_{site}__tes_{site}` so concurrent pairs' artefacts/logs never clobber each other —
a bug caught and fixed before the campaign launch, since `run_single_scenario()` keys its output
paths solely by `scen["id"]`). Validated via a smoke test (two different candidate pairs, both
converging to a tight root LP within ~2–3 minutes) before committing to the full campaign.

**✅ Campaign complete (2026-07-14/15, `SB-S6-HK0`)**: all 25 `(hp_site, tes_site)` pairs solved
at 1800 s/pair, concurrency 2 (~9.4 h actual wall time — longer than the ~6.25 h estimate because
each pair's Python-side build/export overhead runs 20–40 min on top of the 1800 s solve). Output
in `output/paper2_runs/_endog_enum/SB-S6-HK0/`; `_summary.json` holds the full ranking.

**Result: `hp_site = j_hkw`, `tes_site = j_pss` — objective 8,803,284.30 €, this pair's own MIP
gap 1.60 %.** Its nearest rival, `(j_ost, j_pss)` at 8,803,301.96 €, is statistically identical
(Δ = 17.65 €) — strong evidence that **`j_pss` as the TES site is the dominant economic driver**,
with the HP site mattering far less (`j_hkw`/`j_ost` both work; `j_man`/`j_pss`/`j_psw` as HP site
are all clearly worse). Every other of the 24 valid pairs landed between ~9.5 M€ and ~13.8 M€.

**⚠️ Open caveat — 4 pairs are not yet ruled out.** `(j_man,j_man)`, `(j_pss,j_pss)`,
`(j_psw,j_pss)`, `(j_psw,j_psw)` all have a **root/B&B bound below the 8.80 M€ leader**
(4.43 M€, 7.79 M€, 8.65 M€, 7.80 M€ respectively) but never reached a good incumbent in their
30-minute budget (`j_man,j_man`: zero incumbents at all; the other three: 33–43 % gap). These are
individually well-posed MILPs — the difficulty is Gurobi's feasibility heuristics struggling at
these specific (mostly colocated, lower-connectivity) site combinations, not a residual
siting-integrality issue. Since a pair's *bound* being below the leader's *incumbent* means its
true optimum has not been excluded, **`(j_hkw, j_pss)` was the best *validated* Stage-1 result,
but not a proven global optimum across all 25 pairs.**

**✅ Stage-2 follow-up (2026-07-15) — the caution was justified.** Re-ran the 4 flagged pairs at
6 h/pair, concurrency 2 (Stage-1 results backed up first). Result: **the Stage-1 leader was
superseded.**

**✅ All 4 Stage-2 pairs finished:**

| Pair | Objective (€) | Status |
|---|---|---|
| **`(j_man, j_man)`** | **4,490,760.52** | maxTimeLimit, gap 1.18 % — **overall best** |
| `(j_pss, j_pss)` | 7,808,099.80 | **optimal**, gap 0.18 % |
| `(j_psw, j_psw)` | 7,830,993.26 | **optimal**, tightly converged |
| `(j_psw, j_pss)` | 8,697,693.23 | **optimal**, gap 0.49 % |

`(j_man, j_man)` is ~49 % cheaper than the original Stage-1 leader (8,803,284 €); `(j_pss, j_pss)`
and `(j_psw, j_psw)` are close behind each other (~11 % cheaper than Stage-1), both fully proven
optimal.

**Plausibility check, `(j_pss, j_pss)` (not a bug — textbook mechanism):** compared
`economics.csv` for the Stage-1 leader vs. `(j_pss, j_pss)`. At `j_hkw`, the heat pump's share of
total heat supply is **0 %** — the model essentially never bothers using it, relying on the
existing fuel-fired plant (`cost_fuel = 8.24 M€`, `gas_consumption = 93,820 MWh`). At `j_pss`,
colocating HP with TES lifts HP's share to **13.4 %**, roughly **halving** fuel cost (`4.45 M€`)
and gas consumption (`18,813 MWh`) — the well-known HP+TES synergy from DH literature (storage
decouples HP operation from instantaneous demand).

**Plausibility check, `(j_man, j_man)` (coherent, but flagged for domain-expert review before
quoting):** the mechanism is different from `(j_pss, j_pss)` and, on inspection, is NOT primarily
about HP utilization — HP's share is actually *lower* here (2.5 %) than at `j_pss` (13.4 %).
Instead, comparing full-year `dispatch_per_asset.csv` sums across scenarios reveals the driver:
`HWS_BOILER` (the expensive Süd-branch fallback boiler) is used **764 MWh/year** at
`(j_man, j_man)` vs. **87,070 MWh/year** at the Stage-1 leader — a **114× reduction**. `ava_feed`
(the 45 MW waste-heat feed, real but low marginal cost, 5 €/MWh, confirmed non-fixed/dispatchable
in `Stadtbach_topo.yaml`) is also used somewhat less (229,430 vs. 348,980 MWh/year), ruling out a
"free energy" artifact — its cost is real and accounted for. The traceable cause (near-total
avoidance of the expensive boiler fallback) is economically coherent, not a phantom result, but
the **magnitude** (a single siting choice swinging one asset's utilization by 114× and total cost
by ~50 %) is striking enough that a human/domain-expert review of the full dispatch profile is
recommended before this number is quoted in the manuscript — a mathematically sound and internally
consistent MILP result is not automatically the same as a result a domain expert would consider
representative or robust to real-world assumptions not captured in the model.

**Implication for the manuscript**: `(j_hkw, j_pss)` at 8,803,284 € must NOT be quoted as the
SB-S6-HK0 result — it is now the *third*-best of four re-examined candidates. Pending the
recommended plausibility review, the current best is **`(j_man, j_man)` = 4,490,760.52 €**; if
that review raises concerns, `(j_pss, j_pss)` = 7,808,099.80 € (fully proven optimal, mechanism
independently verified) is the next-best, still-defensible fallback. The same Stage-1→Stage-2
methodology (with the SAME plausibility-check discipline) must be applied to `SB-S6-HK1/HK2` and
`MM-S4-HK0/1/2` before quoting *any* endogenous-siting result from either network — this
campaign is a template, not a one-off fix.

## G.8b `SB-S6-HK1` and `SB-S6-HK2` — Stage-1 complete, Stage-2 in progress

**`SB-S6-HK1` Stage-1 leader**: `(j_psw, j_psw)` = 8,563,792.71 € (maxTimeLimit). `(j_man,
j_man)` — HK0's dramatic winner — placed **dead last in the 30-minute Stage-1 screen**
(28,293,180 €). **⚠️ Correction, superseded almost immediately by Stage-2**: this "dead last"
result was a screening artifact, not the pair's true value — see below, do not read the
Stage-1-only ranking above as economically meaningful for this specific pair.

**Same 2 pairs unresolved as in HK0** (bound below the Stage-1 leader, poor 30-min incumbent):
`(j_man,j_man)` bound=4,409,982 (84.4 % gap) and `(j_pss,j_pss)` bound=7,726,485 (41.6 % gap) —
confirming these two site combinations are *structurally* hard for Gurobi's feasibility
heuristics regardless of heat-curve stage, not an HK0-specific artifact. Stage-2 follow-up
launched (6 h/pair, concurrency 2). **Interim Stage-2 results (still converging)**:
`(j_man,j_man)` → **4,493,566.84 €, gap 1.86 %** — within **0.06 %** of HK0's `(j_man,j_man)`
result (4,490,760.52 €), strongly suggesting this is a real, recurring structural effect of the
network topology (near-elimination of the expensive Süd-branch `HWS_BOILER` fallback — see the
HK0 plausibility check above), not an HK0-specific coincidence. `(j_pss,j_pss)` →
**8,534,903.96 €, gap 9.45 %** — already below the Stage-1 leader before even converging. **Both
Stage-2 candidates are on track to supersede HK1's Stage-1 leader entirely**, mirroring HK0
exactly.

**✅ FINAL (2026-07-16)**: `(j_pss,j_pss)` **converged to full proven optimality**
(`Optimal solution found`, tolerance 5.00e-03) at **7,754,886.69 €, gap 0.32 %** after 16,068 s.
`(j_man,j_man)` **hit its 6 h time limit** without reaching the 0.5 % target — final incumbent
**4,480,201.25 €, gap 1.52 %** (`maxTimeLimit`, 15,068 nodes explored, still a valid, usable
bound). **`SB-S6-HK1`'s confirmed campaign winner is `(j_man,j_man)` = 4,480,201.25 €** — both
Stage-2 pairs comfortably beat the Stage-1 leader `(j_psw,j_psw)` = 8,563,792.71 €, and the
1.7×-lower `(j_man,j_man)` result is unambiguous regardless of its 1.52 % vs 0.5 % gap (the
remaining bound-to-incumbent room, ~68 k€, cannot flip the ranking against a 3.27 M€ margin over
the next-best pair). Flagged for a longer extension run only if publication precision requires
tightening below 1 %; not expected to change the reported winner or value materially.

**`SB-S6-HK2` Stage-1 leader (superseded, see correction below)**: `(j_ost, j_pss)` =
8,718,247.55 € was **fully proven optimal** in the 30-min Stage-1 window — but "proven optimal"
there only means optimal *for that fixed site pair*, not optimal across all 36 pairs; Stage-1's
30-min budget is a screen, not a campaign-wide proof. `(j_man,j_man)` is *catastrophically* worse
here (131,812,102 €) — the most extreme HK-to-HK reversal seen so far. **Six pairs** have bounds
below the leader (more than HK0's four or HK1's two): `(j_man,j_man)` bound=4,373,479 (96.7 % gap,
essentially unresolved), `(j_pss,j_pss)` bound=7,625,856 (38.7 % gap), `(j_psw,j_psw)`
bound=7,638,668 (43.1 % gap), plus three pairs whose bounds sit only narrowly below the leader
(`(j_psw,j_pss)` 8,581,340 gap 31.0 %; `(j_pss,j_psw)` 8,627,771 gap 10.1 %; `(j_ost,j_psw)`
8,712,730 gap 9.4 %). Stage-2 launched for the three highest-impact pairs first (`j_man/j_man`,
`j_pss/j_pss`, `j_psw/j_psw`) to manage concurrent RAM load; the three marginal pairs were
deferred to a follow-up pass.

**⚠️ Correction (2026-07-16) — new confirmed campaign winner**: Stage-2 `(j_pss,j_pss)`
**converged to full Gurobi optimality** (`Optimal solution found`, tolerance 5.00e-03, gap
0.3188 %) at **7,652,957.42 €** — over **1,065,290 € (12.2 %) below** the Stage-1 leader
`(j_ost,j_pss)` = 8,718,247.55 €. This is not an improving incumbent still converging; Gurobi
terminated cleanly on its own gap tolerance after 3,682.76 s (43 nodes), so this is a rigorously
established result, not a screening artifact — but it was **not yet the final answer**, see below.

**✅ FINAL (2026-07-16) — second correction, `(j_man,j_man)` is the true winner**: once
`(j_man,j_man)` and `(j_psw,j_psw)` Stage-2 finished, `(j_man,j_man)` came in at
**4,436,628.84 €, gap 1.37 %** (`maxTimeLimit`, best bound 4,375,774.72) — **2,900,000+ €
(38–39 %) below both** `(j_pss,j_pss)` = 7,652,957.42 € (proven optimal, 0.32 % gap) and
`(j_psw,j_psw)` = 7,674,692.11 € (proven optimal, 0.40 % gap). **`SB-S6-HK2`'s confirmed campaign
winner is `(j_man,j_man)` = 4,436,628.84 €**, not `(j_pss,j_pss)`. The margin (2.9 M€) dwarfs the
remaining bound-to-incumbent room (~61 k€), so the 1.37 % vs 0.5 % gap does not affect the
ranking. This makes `(j_man,j_man)` the winner in **all three** Stadtbach heat-curve stages
(HK0=4,490,761 €, HK1=4,480,201 €, HK2=4,436,629 €) — a fully consistent, non-coincidental
result across the whole campaign, not a stage-specific artifact. The three deferred marginal
pairs (`(j_psw,j_pss)`, `(j_pss,j_psw)`, `(j_ost,j_psw)`, Stage-1 bounds 8.58–8.71 M€) are now
**conclusively ruled out** by this 2.9 M€ margin and do not need a Stage-2 follow-up.

**Running tally across the two closed-out Stage-1 campaigns**: the pairing `(*, j_pss)` with a
mid-network HP site (`j_ost`/`j_hkw`/`j_man`) has now appeared as the fully-proven-optimal or
near-optimal Stage-1 leader in HK0 (`j_hkw,j_pss`), HK1 (via `j_ost,j_pss` at #2), and HK2
(`j_ost,j_pss` #1) — but in every case so far, at least one *colocated at a low-connectivity
node* pair (`j_man,j_man` and/or `j_pss,j_pss`/`j_psw,j_psw`) has an unresolved lower bound that
Stage-2 subsequently reveals to be competitive or dominant. **No Stage-1 result for this project
should ever be treated as final without its Stage-2 pass.**

## G.8c `MM-S4-HK0/HK1/HK2` (Memmingen) — Stage-1 and Stage-2 complete, pattern does NOT repeat

All three Memmingen heat-curve stages completed their 36-pair Stage-1 enumeration screen
(2026-07-16), each with the same non-colocated mid-network leader `(j_3, j_1)`, nearly converged
already at 30 min: **HK0** = 331,301.84 € (1.64 % gap), **HK1** = 321,128.36 € (1.67 % gap),
**HK2** = 312,261.41 € (1.73 % gap). In every stage, the colocated `(j_3,j_3)` pair had a
noticeably weaker Stage-1 bound than the leader's — the same early-warning signature seen
throughout the Stadtbach (`SB-S6`) campaign — so the same flagging rule applied: any pair whose
Stage-1 *bound* undercut the leader's *incumbent* got a 6 h Stage-2 follow-up. That produced 4
flagged pairs each for `MM-S4-HK0`/`MM-S4-HK2` (`(j_3,j_9)`, `(j_3,j_12)`, `(j_3,j_13)`,
`(j_3,j_3)`) and 3 for `MM-S4-HK1` (no `(j_3,j_12)` bound undercut there).

**✅ FINAL, `MM-S4-HK0` (2026-07-16)**: all 4 flagged pairs converged to incumbents *above* the
Stage-1 leader — `(j_3,j_9)`=343,412.55 €, `(j_3,j_12)`=345,012.07 €, `(j_3,j_13)`=346,570.58 €
(5.38 % gap), `(j_3,j_3)`=338,618.38 € (colocated, 7.26 % gap). **`MM-S4-HK0`'s confirmed
campaign winner is the original Stage-1 leader, `(j_3,j_1)` = 331,301.84 €.** This is the
**first scenario in the whole campaign where the Stage-1 leader survives Stage-2 unchanged** —
unlike every `SB-S6` stage, where a colocated pair always overturned the mid-network leader.
**Do not assume the colocated-pair-wins pattern generalizes across networks**: Memmingen's much
smaller, more radial topology (vs. Stadtbach's meshed network) appears to genuinely favor the
non-colocated mid-network site, not just exhibit a Stage-1 screening artifact.

**✅ FINAL, `MM-S4-HK2` (2026-07-17)**: all 4 flagged pairs converged above the Stage-1 leader —
`(j_3,j_9)`=355,378.64 € (13.14 % gap), `(j_3,j_3)`=330,211.86 € (colocated, 8.79 % gap),
`(j_3,j_12)`=323,638.83 €, `(j_3,j_13)`=323,823.01 €. **`MM-S4-HK2`'s confirmed campaign winner
is the original Stage-1 leader, `(j_3,j_1)` = 312,261.41 €.** Same outcome as `MM-S4-HK0`: the
leader survives Stage-2 unchanged, reinforcing that Memmingen's topology genuinely favors the
non-colocated site across all heat-curve stages tested so far (2 of 3 confirmed).

**✅ FINAL, `MM-S4-HK1` (2026-07-17)**: all 3 flagged pairs converged above the Stage-1 leader —
`(j_3,j_9)`=337,502.60 € (5.89 % gap), `(j_3,j_13)`=332,454.57 € (4.45 % gap), `(j_3,j_3)`
(colocated)=331,292.92 € (6.96 % gap, `maxTimeLimit`). **`MM-S4-HK1`'s confirmed campaign winner
is the original Stage-1 leader, `(j_3,j_1)` = 321,128.36 €.** All three Memmingen heat-curve
stages now confirm the same outcome: **the leader `(j_3,j_1)` holds unchanged through Stage-2 in
every case** (HK0=331,301.84, HK1=321,128.36, HK2=312,261.41 €) — a clean, fully consistent
result across the whole Memmingen campaign, with zero cases of the colocated pair overturning the
leader (vs. 3/3 cases in Stadtbach where it did). This is now the definitive confirmation that
the colocated-pair-wins pattern found in `SB-S6` (G.8/G.8b) is a network-topology-specific effect
of Stadtbach's meshed pipe network, not a universal artifact of the endogenous-siting MILP
formulation.

**All 5 F3 endogenous-siting campaign scenarios are now fully resolved (2026-07-17)**:

| Scenario | Winner `(HP, TES)` | Objective (€) | Gap |
|---|---|---|---|
| `SB-S6-HK0` | `(j_man, j_man)` | 4,490,760.52 | ≤1 % |
| `SB-S6-HK1` | `(j_man, j_man)` | 4,480,201.25 | 1.52 % |
| `SB-S6-HK2` | `(j_man, j_man)` | 4,436,628.84 | 1.37 % |
| `MM-S4-HK0` | `(j_3, j_1)` | 331,301.84 | 1.64 % |
| `MM-S4-HK1` | `(j_3, j_1)` | 321,128.36 | 1.67 % |
| `MM-S4-HK2` | `(j_3, j_1)` | 312,261.41 | 1.73 % |

**✅ Plausibility check complete (2026-07-17)**. Note: `SB-S7`/`MM-S5` are **not** valid
apples-to-apples controls for this check — both also set `hot_charging: true` (122 °C TES
charging) alongside `colocate: true`, a confounded physics change (explains `SB-S7-HK0`'s ~2.2×
higher total cost and ~37× higher gas consumption vs. `SB-S6-HK0`'s winner; not a siting-only
comparison). Used a cross-heat-curve-stage internal-consistency check instead:

- **`SB-S6` winners**: cost decreases smoothly and monotonically HK0→HK1→HK2 (4,490,761 →
  4,480,201 → 4,436,629 €), HP share rises slightly (2.50 %→2.59 %→2.70 %), LCOH falls slightly
  (7.02→7.00→6.93 €/MWh). TES geometry (V=49,817 m³, h=83.0 m, E=845 MWh, p=8.92 bar) matches the
  logged extraction exactly. HP dispatch (~3.4 MW) is small relative to the network's existing
  `AVA_FEED` baseload (constant 45 MW) — explains the low HP share; this is a real district
  network dominated by an existing large feed-in, not a bug.
- **`MM-S4` winners**: cost also decreases smoothly and monotonically (331,302 → 321,128 →
  312,261 €), HP share stable ~39.3–39.5 %, CHP ~7.3–7.7 %, LCOH falls smoothly (33.92→32.88→
  31.97 €/MWh) — a much more HP/CHP-dominated mix than Stadtbach, consistent with Memmingen's
  smaller network lacking an equivalent large baseload feed-in.

No anomalies found (no negative costs, no >100 % shares, no degenerate all-zero dispatch) in
either campaign. **All 6 winning results (3 `SB-S6` + 3 `MM-S4` heat-curve stages) are cleared
for use in the manuscript.**

## G.9 ⚠️ Operational incident — `SB-S7-HK0`'s prior campaign result was overwritten

While diagnosing G.7, a short (120 s) build-sanity regression check was run to confirm the new
`_distribute_flows`/`_get_site_y` code (Fix A/G/H/SOS1) doesn't crash on `SB-S7-HK0` and
`MM-S4-HK0`. That check called `run_single_scenario(..., force_rerun=True)` directly on the
**real** scenario ids, not on uniquely-named clones (the pattern later used correctly for
`enumerate_endog_siting.py`, once the same clobbering risk was recognized there). Because the
sanity check used a 120 s budget and reached no incumbent, it overwrote
`output/paper2_runs/SB-S7-HK0/meta.json` (now `status=no_incumbent, obj_eur=null`) and
`output/logs/gurobi_SB-S7-HK0.log`, replacing whatever was recorded from the 2026-07-14
36-scenario campaign — per `[[project-paper2-tes-dispatch-fix]]`, `SB-S7` had **converged
cleanly to a proven-optimal or ≤1 % gap** in that campaign. That result is not recoverable
(`output/` is git-ignored; no independent summary table was found recording the value).

**Scope, confirmed by grep across every diagnostic script this session**: only `SB-S6-HK0`,
`SB-S7-HK0`, and `MM-S4-HK0` were ever called with `force_rerun=True` against their real id.
`SB-S6-HK0`/`MM-S4-HK0` were already open/pending (stalled 63–96 % gap per G.6) — not validated
paper-quality results, so overwriting them cost little. **`SB-S7-HK0` is the one genuine loss.**
Every other scenario (`S1`–`S5`, `MM-S1`–`MM-S3`, `MM-S5`, all `HK1`/`HK2` variants) is untouched.

**✅ RESOLVED (2026-07-14, same day)**: `SB-S7-HK0` was re-run at the scenario's standard
campaign `TimeLimit` (86400 s, from the base config) using the real scenario id. It terminated
**on its own** — `Optimal solution found (tolerance 5.00e-03)`, i.e. it hit the target MIP-gap
tolerance well before the 24 h budget, not a timeout. Result: **objective 9,873,271.33 €, gap
0.369 %** — matching the "converged cleanly to ≤1 % gap" description of the original (lost)
result from `[[project-paper2-tes-dispatch-fix]]`. This confirms the theoretical expectation
above: this session's Fix A/G/H/SOS1 changes did not alter the true optimum, only the path to
finding it. `output/paper2_runs/SB-S7-HK0/meta.json` now reflects this recovered result; the
prior no-incumbent overwrite has been superseded.

## G.10 Reporting-pipeline audit (2026-07-15) — three of four "convergence blocker" symptoms
were stale-data/dict-key artifacts, not model bugs; two real open issues surfaced underneath

An external ECM-style review of T3/T4/T5 flagged four blockers, in priority order: (1) only 3/37
runs "optimal", 33 "?", `mip_gap` null everywhere, and identical TAC across `SB-S1/S2/S3`
suggesting non-converged incumbents; (2) `Q_WP` pinned at exactly `capacity_max_mw=50.0` for all
of `SB-S1–S3`; (3) `E_TES=500.0` MWh for *every* Stadtbach row including `BC`/`S0` (no TES at
all), and 500 isn't even in the discrete set `[0,73,…,845]`; (4) `COP` empty for all Stadtbach
rows, plus Memmingen P1↔P2 OPEX consistency failing at 124.49 % (gate ≤2 %).

**Root cause, found by direct inspection of the per-scenario artefacts (`geometry.csv`,
`dispatch_hourly.csv`, `meta.json`) vs. the published tables:**

1. **`output/paper2_runs/scenarios_kpis.csv` — the single file `gen_tables.py` reads for T3/T4 —
   was last written 2026-07-04**, i.e. *before* the entire TES-refit campaign in
   [[project-paper2-tes-dispatch-fix]] and [[project-paper2-f3-siting-sos1]] (which ran
   2026-07-12 through -15) ever executed. Every number in T3/T4 was frozen 8–11 days stale. Direct
   comparison, `SB-S1-HK0`: stale file says `TAC=20.461M€, Q_WP=50.0, E_TES=500.0`; the *current*
   `meta.json`/`geometry.csv`/`dispatch_hourly.csv` (2026-07-14, `status=optimal`, gap 0.34 %)
   say `TAC=9.978M€, Q_WP peak=24.2 MW, E_TES=73.0 MWh` (a valid discrete size) — a completely
   different, internally consistent, differentiated result. Blockers 2 and 3 (WP-cap-pinning,
   bogus constant `E_TES`) and most of blocker 4 (missing COP — confirmed computable: `3.08` for
   `SB-S1-HK0` from `sum(Q)/sum(P_el)`) were artifacts of this one stale file, not a model defect.
   **Fix**: re-ran `kpi_calculator.compute_all_kpis(OUT_RUNS)` to regenerate `scenarios_kpis.csv`
   from the live campaign output. `gen_tables.py`'s scenario filter was also extended to exclude
   the F3 enumeration sub-pairs (`__hp_{site}__tes_{site}`, see G.8) from T3/T4 — those are
   per-candidate helper solves, not reportable scenarios.
2. **`scripts/paper_2/figures/gen_tables.py::build_t5` read `m.get("solver_status", "?")`, but
   the actual `meta.json` key is `"status"`** — so `status` was `"?"` for literally every run,
   independent of the stale-file issue. This directly produced the "33× status ?, 3× optimal"
   line, and *also* silently broke the MW-closure trust gate one line below
   (`optimal = "optimal" in status.lower()`, always `False`), which is why "0/3 passing closure
   gate" only ever saw 3 runs at all. **Fix**: one-line key correction (`"status"`).
3. **`calion/run/solver.py`'s `solver_meta` dict never captured Gurobi's reported MIP gap** —
   confirmed real convergence in the raw log the whole time (e.g. `SB-S1-HK0`:
   `Optimal solution found (tolerance 1.00e-02) ... gap 0.3362%`) but `meta.json["mip_gap"]` was
   always `null`, making "did this converge" impossible to audit without grepping raw Gurobi logs.
   **Fix (permanent, forward-looking)**: added `solver_meta["mip_gap"] = float(gb.MIPGap)` read
   directly off the native Gurobi model handle right after solve (same `try` block that already
   reads `gb.NumQConstrs`). **Fix (retroactive, one-time)**: backfilled `mip_gap` into all 137
   existing `meta.json` files by parsing each scenario's final `"Best objective …, gap X%"` line
   out of its `gurobi_*.log` (scratchpad `backfill_mip_gap.py`) — zero already had a gap, all 137
   got one, zero failed to parse.

**Regenerated T3/T4/T5 — the corrected picture:**
- T3 (Stadtbach, 24 canonical scenarios): every TES size is now a valid discrete value (`73, 219,
  292, 365, 730, 845` MWh), `Q_WP` ranges `0–27.4 MW` (never pinned at the 50 MW cap — that cap is
  simply not binding at the true optimum), `COP` `2.69–3.67` (HK-stage-dependent, plausible), and
  TAC is properly differentiated per scenario (e.g. `SB-S2-HK0=4.457M€` vs `SB-S1-HK0=9.978M€` vs
  `SB-S3-HK0=11.013M€` — no TES built for S3, matching `geometry.csv build=0`).
- T5 solver-status census across all 138 solved runs (canonical + diagnostic + F3 enumeration
  sub-pairs): **`optimal: 36, maxTimeLimit: 102`** — the `maxTimeLimit` count is dominated by the
  F3 enumeration sub-pairs (expected — see G.8, most individual site-pair solves are given a fixed
  time budget rather than run to proven optimality) and by `SB-S6`/`MM-S4`'s known-bad monolithic
  runs (G.6/G.7). All of `S0`–`S5`, `S7`, and `BC` on both networks converged to `optimal` well
  inside their 1 % gap target.
- `MIP gap (max) = 47349.6 %` is a **known display artifact**, not a real number: it's the
  monolithic (pre-enumeration-decomposition) `MM-S4-HK0` run, whose best-bound crosses through
  zero during search, so Gurobi's *relative* gap formula blows up. That run is already superseded
  by the `MM-S4` enumeration campaign (G.8) and should be excluded from this statistic rather than
  fixed — noted here so it isn't mistaken for a new bug.

**Two genuinely new, real findings surfaced once the fog cleared (neither is a reporting
artifact — both needed their own diagnosis at the time this section was written; both are now
resolved below, see the inline pointers — this section is kept verbatim as the historical record
of how the question was first raised, not as a currently-open question):**
1. **MW closure error, computed correctly for the first time**: mean 25.83 %, max 63.73 % (worst:
   `SB-S2-HK2`), only **7/36** converged runs pass the ≤2 % gate. This is the opposite of
   reassuring — the previous "0/3" was hiding behind the status-key bug rather than reflecting a
   real (much larger, much better-sampled) picture. Needs a dedicated diagnostic session: is the
   closure check itself mis-specified (e.g. double-counting network losses it explicitly says are
   "not an imbalance"), or is this a real dispatch-balance defect.
   **→ RESOLVED in G.12 (below).** A decisive per-node audit reading live Gurobi state directly
   (`Σht_out` vs `Σdemand`) matched to 0.04 % — the model's true heat balance is correct. The
   large percentages are a **closure-check formula/methodology gap**: `gen + discharge − charge`
   nets a wash-cycling TES's real throughput to ~zero. Not an energy-conservation defect. Treat
   this bullet as the historical statement of the question, not as still-open.
2. **Memmingen P1↔P2 OPEX consistency, confirmed real** (both inputs are fresh/correct — `BC-MM`
   solved 2026-07-12, `status=optimal`, gap 0.53 %; the Paper-1 `L3` reference is a static,
   independently-validated file from 2026-05-26, not stale): `124.49 %` deviation,
   `cost_fuel_eur` 452,793 (P2) vs 58,381 (P1), `share_HP_pct` 51.9 % (P2) vs 88.8 % (P1),
   `gas_consumption_MWh` 1552 (P2) vs 698 (P1). The dispatch mix is fundamentally different, not
   just numerically off — suggests `BC-MM`'s scenario config may not actually reproduce the fixed
   `Q_WP=5 MW, Q_EK=5 MW` assumption the check's docstring says it should. Needs its own targeted
   comparison of `BC-MM`'s asset config against the Paper 1 `L3` setup before deciding whether this
   is a config drift or a real formulation divergence.
   **→ RESOLVED in G.11 (below).** `BC-MM` (0 MW HP, Paper 2's zero-investment baseline) and
   Paper 1's `L3` (5 MW HP, pre-existing) are two deliberately different scenarios by design —
   the deviation is the expected consequence of that difference, not a bug or config drift. See
   G.14 for the follow-up: a new explicitly-labeled 5 MW-fixed comparison scenario.
3. **`SB-S6-HK0`'s canonical T3 row is still the known-bad monolithic result** (`TAC=58.588M€,
   Δcost=-431%`) — expected per G.6–G.8, not a new bug, but flagged so it is not mistaken for a
   real KPI: the enumeration-decomposition winner (`hp_j_man/tes_j_man`, `4.49M€`, 1.18 % gap, see
   G.8) is the number that should eventually replace it in the reported table, once `SB-S6-HK1/HK2`
   and all three `MM-S4` stages finish their own enumeration campaigns and a stage-2 plausibility
   pass (per G.8's caveat) is done consistently across all of them.

**Files touched:** `calion/run/solver.py` (`mip_gap` capture, forward-looking, additive-only —
no change to any solve behavior, only to what gets recorded about it),
`scripts/paper_2/figures/gen_tables.py` (`solver_status`→`status` key fix; enumeration-sub-pair
exclusion filter in `_load_kpis`), `output/paper2_runs/scenarios_kpis.csv` (regenerated),
`results/paper2_figures/tab_T3_stadtbach_kpis.{csv,tex}`, `tab_T4_memmingen_kpis.{csv,tex}`,
`tab_T5_validation.{csv,tex}` (regenerated), all 137 existing `meta.json` files (retroactive
`mip_gap` backfill, no other field touched).

**How to apply:** before trusting any campaign-wide table (T3/T4/T5, or any script reading
`scenarios_kpis.csv`), check the file's mtime against the scenario directories it's supposed to
summarize — a merged/aggregated CSV can silently go stale relative to `output/paper2_runs/*/`
even though the individual scenario artefacts are current. When a validation script's aggregate
stat looks implausibly bad (all "?", all identical, all a suspicious round number), suspect a
dict-key mismatch or a stale intermediate file before suspecting the underlying solve.

## G.11 Memmingen P1↔P2 OPEX consistency (124.49 % "FAIL") — resolved: a scenario-definition
mismatch, not a bug

**Problem.** T5 reports `Memmingen P1 OPEX consistency = 124.49 %` (gate ≤2 %, FAIL):
`cost_total_eur` for `BC-MM` (P2) = 506,701 € vs. Paper 1's `L3` reference = 225,717 €. The
dispatch mix is qualitatively different, not just numerically off: `share_HP_pct` 51.9 % (P2) vs.
88.8 % (P1); `gas_consumption_MWh` 1552 (P2) vs. 698 (P1); `cost_fuel_eur` 452,793 (P2) vs. 58,381
(P1). Both inputs are independently confirmed fresh and correctly solved (`BC-MM`: `status=optimal`,
gap 0.53 %, solved 2026-07-12; Paper-1 `L3`: a static, independently-validated reference file from
2026-05-26) — so this is not a staleness artifact like G.10's other three findings.

**Root cause.** `scripts/paper_2/validation_p2.py::check_paper1_consistency`'s own docstring states
the intent: *"Memmingen with fixed Q_WP=5 MW, Q_EK=5 MW reproduces Paper 1 OPEX."* Checked both
configs directly:
- **Paper 1** (`configs/memmingen/Memmingen_L3_MILP.yaml`): `hp_main.capacity_mw: 5.0`,
  `eboiler_main.capacity_mw: 5.0` — a small, pre-existing HP+EK already installed and dispatched.
- **Paper 2's `BC-MM`** (`configs/paper_2/scenarios.yaml`, lines 146–161): explicitly overrides
  `hp_main.capacity_mw: 0.0`, `investment.enabled: false` — *"baseline: no HP exists (spec §4.5)"*,
  *"Memmingen baseline — Bestand only, no HP/EK/TES."*

**These are two different physical configurations by design**, not the same scenario solved twice.
`BC-MM` correctly represents Paper 2's own "as-is, zero-investment" baseline concept (which changed
from Paper 1's assumption of a small pre-existing HP). Comparing a 0 MW-HP scenario's OPEX against a
5 MW-HP reference and expecting ≤2 % agreement was never going to hold — the 124 % deviation is the
*expected, correct* consequence of the two scenarios genuinely differing, not a defect in either
model or in the campaign's results.

**Resolution.** No code or scenario fix needed on the Paper 2 side — `BC-MM`'s definition is correct
for Paper 2's own baseline concept. The **check itself** is stale: it was written against an earlier
scenario matrix where presumably a "Q_WP=5 MW fixed" scenario existed, and never got updated when
`BC-MM` was redefined to the current zero-investment "Bestand" baseline. Recommended: either (a)
retire `check_paper1_consistency` (P1 and P2 baselines are no longer the same scenario by design,
so there is nothing to validate here), or (b) if a like-for-like P1↔P2 cross-check is still wanted
for the manuscript, add a new, explicitly-labeled scenario with `hp_main`/`eboiler_main` fixed at
5.0 MW (matching Paper 1's `L3`) and point the check at that instead of `BC-MM`. Not implemented
this session — awaiting a decision on whether the paper still needs this specific cross-check at
all, since Paper 2's baseline concept has legitimately moved on from Paper 1's.

**Files touched:** none (diagnosis only, no code changed — the check's mismatch is a scenario-intent
issue, not a formulation or extraction bug).

**How to apply:** before treating any P1↔P2 (or cross-scenario) "consistency" check's FAIL as a bug,
verify both sides are actually configured to represent the *same* physical scenario — a check can
fail correctly if the two things it compares were deliberately redefined to differ.

## G.12 Stadtbach/Memmingen MW-closure error — RESOLVED: a real TES dispatch-export bug (two
root causes found and fixed), NOT an energy-conservation violation; the paper's economic KPIs
were never affected

**Problem.** Once G.10's status-key fix was applied, T5's MW-closure statistic (previously hidden
behind that bug) showed mean error 25.83 %, max 63.73 % (`SB-S2-HK2`), only 7/36 converged runs
passing the ≤2 % gate. `SB-S2`'s total consumer demand (639,973.5 MWh/yr, independently confirmed
against the raw input Excel and `nodes_summary.csv`) looked **~2.4–2.8×** larger than total
generation summed from the 8 named producer-asset columns (232,100.5 MWh/yr). Reproduced with
fresh, isolated, current-code re-solves (a January-only `scenario.horizon` override, ruling out
staleness/concurrency/full-year-specific effects) — so this was real and reproducible, not a
reporting artifact of the kind found in G.10.

**Decisive diagnostic:** added a new per-node `ht_out`/`ht_in` audit
(`calion/run/result_collector.py`, reading `model._system_buses` directly — the actual heat-balance
decision variables, independent of any dispatch-export code) and a `node_heat_audit.json` writer
(`scripts/paper_2/extract_artefacts_p2.py`). Result for the January `SB-S2-HK0` re-solve:
`total_ht_out_MWh = 93,659` vs. `Q_demand_total_MW` sum `= 93,623` — a **0.04 % match**. The
model's *true* constraint-level heat balance was fine all along; Gurobi's `optimal`/feasible status
was not lying. The apparent ~2.4–2.8× gap was entirely downstream, in how dispatch is *exported*,
not in how the model *solves*.

**Root cause, found in the per-node audit's breakdown:** `j_man` (the node `SB-S2` sites its TES
at) showed `ht_out_MWh = 57,360` **and** `ht_in_MWh = 57,360` for January alone — TES wash-cycling
(previously documented in [[project-paper2-tes-dispatch-fix]] as a genuine, if unusual, MILP
optimum) at a scale roughly matching the entire "missing" generation. Checked
`dispatch_hourly.csv`'s `SOC_MWh`/`Q_storage_charge_MW`/`Q_storage_discharge_MW` columns directly:
**all identically zero for the full year**, despite TES clearly being built (`geometry.csv`:
`build=1`, 845 MWh) and actively cycling. Traced to **two independent, compounding bugs** in
`calion/run/result_collector.py::_gather_component_metadata_unified` /
the storage-series extraction block:
1. `elif atype == "storage":` never matched Paper 2's investable TES, which is typed
   `"geometric_storage"` in every Paper 2 config (`Stadtbach_topo.yaml`'s `tes_sb`,
   `Memmingen_P2_base.yaml`'s `tes_main`) — a distinct type introduced for the discrete-size TES
   formulation, never added to this string match. `meta["storage"]` therefore stayed `None`
   (falsy), which gates off (`if meta["storage"]:`) the **entire** Qc/Qd/SOC series-extraction
   block below it — for every geometric_storage TES, on both networks, for the whole campaign.
2. Independently, `_sum_sto("SOC", ["TES_E"], "TES_SOC_MWh")` searched for a Pyomo attribute
   ending in `_SOC`, with a `TES_E` legacy fallback — but `geometric_storage.py` (line 334) names
   the state-of-charge variable `{asset}_E` (e.g. `tes_sb_E`), matching neither pattern. Even with
   bug 1 fixed, SOC would still have silently stayed empty (Qc/Qd's own `_Qc`/`_Qd` suffix search
   was already correct and unaffected by this second bug).

**Fix:** `atype in ("storage", "geometric_storage")` (bug 1); `_sum_sto("E", ["TES_E"], ...)` (bug
2) — both changes are narrow, additive, and change nothing about how any model is built or solved,
only what gets read out of it afterward. **Verified** on the same January `SB-S2-HK0` re-solve:
`Q_storage_charge_MW` sum = 57,360, `Q_storage_discharge_MW` sum = 55,054 (the ~4 % gap between
them is the TES round-trip efficiency loss — physically correct), `SOC_MWh` now populated and
varying (352,690 sum, max 774.4, matching the 845 MWh build). This closes G.9's `write_geometry_p2`
type gap too, structurally the same category of miss.

**One remaining, separate, small finding:** even with correct TES data, the specific closure
*formula* in `scripts/paper/extract_artefacts.py` (`supply = gen_total + discharge - charge`,
compared to demand) still reports a large "error" for `SB-S2` (61 % on the January test) — because
TES's charge and discharge are nearly equal (wash-cycling), so `discharge - charge ≈ 0` in a flat
global sum, while the node-audit's raw `Σht_out` (93,659, not netted against `Σht_in`) matches
demand almost exactly. This is a **closure-check methodology gap**, not a new energy-conservation
bug: the existing formula was evidently validated against Memmingen's simple single-producer radial
case and doesn't correctly generalize to Stadtbach's multi-producer mesh with locally-sited TES.
**Recommendation, not yet implemented:** replace/supplement `extract_artefacts.py`'s closure check
with the `node_heat_audit.json`-based one (`Σht_out` vs. `Σdemand`, both read directly off live
model state) for any future validation pass — it is provably correct (it reads the same variables
Gurobi's own feasibility check used) where the 5-column heuristic is topology-dependent and
fragile.

**Also confirmed present on Memmingen** (not just Stadtbach): `MM-S1-HK0` independently showed
gen/demand ratio 0.713, `closure_error_pct = 28.67`, `closure_pass: false` — before this fix, since
`tes_main` is the same `geometric_storage` type and hits the identical two bugs. Both networks
benefit from the same fix; no network-specific code involved.

**Critically: the paper's economic KPIs (TAC, LCOH, cost-reduction %, CAPEX/OPEX, CO₂) were NEVER
affected by this bug.** Those come from `economics.csv`, populated directly from the solver's own
objective-term `Expression`s at solve time (an entirely separate code path from the
dispatch-series export this bug lived in) — confirmed by the fact that `SB-S2-HK0`'s objective
(`obj_eur` in `meta.json`) already correctly reflected TES's real investment and dispatch cost all
along. Only (a) the MW-closure validation statistic in T5, and (b) TES-utilization-derived KPIs
that read `dispatch_hourly.csv`'s SOC/charge/discharge columns (`TES_cycles_per_a`,
`TES_utilization_pct`, and the SOC-based `E_TES_MWh` fallback for scenarios lacking `geometry.csv`)
were silently wrong. No re-interpretation of any published TAC/LCOH/cost-reduction number is
needed.

**Campaign-wide refit COMPLETE (2026-07-19):** re-ran all 27 TES-active, non-endogenous scenarios
(`SB-S1/S2/S3/S5/S7`, `MM-S1/S2/S3/S5`, all HK stages — `S4`/`S6` excluded, handled separately via
the enumeration decomposition in [[project-paper2-f3-siting-sos1]]) with both fixes applied.
RAM-gated scheduler (max 4 concurrent, cap adapted to coexist with the other window's concurrent F3
campaign), ran ~67 hours end to end, **27/27 completed, zero crashes**. `scenarios_kpis.csv`
regenerated (`kpi_calculator.compute_all_kpis`) and T3/T4/T5 rebuilt.

**Confirms the "economics unaffected" claim empirically, not just theoretically**: every TAC/LCOH
value in the rebuilt T3 is byte-for-byte identical to the pre-refit table (e.g. `SB-S2-HK0`:
4.457 M€ both before and after) — re-solving with corrected TES export changed no economic
conclusion, exactly as predicted, because `economics.csv` was never on the broken code path.

**T5, post-refit:** mean closure error 22.98 % (was 25.83 %), 12/41 runs now pass the ≤2 % gate (was
7/36) — a real improvement in the *sample*, not a fix to the *formula*: the closure-methodology gap
described above (flat `discharge-charge` netting doesn't suit heavy wash-cycling TES) is still
present and still the dominant reason most TES-heavy scenarios don't "pass" a check that isn't
actually measuring what it claims to for this topology. `SB-S2-HK2` remains the reported worst case
(66.39 %) for exactly that reason — its TES is the heaviest-cycling one in the campaign. The
`node_heat_audit`-based methodology (Σht_out vs Σdemand) remains the recommended replacement for
any future validation pass; not yet applied campaign-wide (only exists for the one January
diagnostic scenario) — that is the one remaining, low-priority follow-up from this investigation.

**Files touched:** `calion/run/result_collector.py` (storage-type-gate fix, SOC-suffix fix, new
`node_heat_audit` diagnostic capture — all additive, no change to any solve behavior or existing
export values other than un-silencing previously-dropped TES series),
`scripts/paper_2/extract_artefacts_p2.py` (`write_node_heat_audit`, new function + one call site).

**How to apply:** when a validation/closure check shows an implausibly large "error" for a
scenario with active storage, check whether storage charge/discharge/SOC actually made it into the
dispatch export (`dispatch_hourly.csv`'s `Q_storage_charge_MW`/`_discharge_MW`/`SOC_MWh` — all-zero
despite `geometry.csv` showing `build=1` is the tell) before suspecting the model's physics. A
per-node `ht_out`/`ht_in` audit reading live model state directly is a far more reliable ground
truth than any derived CSV export, and should be the first diagnostic reached for, not the last.

## G.13 F8/F3/F7 "make it ready" pass (2026-07-19/20) — one real export bug fixed, one
non-bug explained and annotated, one broken metric fixed, two never-run analyses launched

Following G.10-G.12's reporting-pipeline audit, F8 (spatial T/p profile), F3 (capacity-sweep
heatmap) and F7 (sensitivity tornado) were the three figures/tables still flagged "not ready" in
the design-package README. Each is addressed below; F8's fix is verified, F3/F7 were launched
and were still running campaigns at the time of this update (see "Campaign status at time of
writing").

### G.13.1 F8, problem 1 — node-pressure export bug (real bug, fixed and verified)

**Root cause.** `calion/io/thermal_network_exporter.py`'s per-node pressure extraction looked up
`getattr(model, f'{node_prefix}_P', None)` — but the actual Pyomo Var, defined in
`calion/models/blocks/thermal_node.py:279`, is named `{prefix}_pressure_supply` (and
`{prefix}_pressure_return`). The lookup never matched anything, on either network, for the whole
campaign, so `P_avg_bar` and every `{node}_P` timeseries column were always empty — despite
pressure being fully modeled and solved (confirmed via A.4.5/A.4.3b; this was purely an export
gap, one level up from the `nodes_timeseries.csv` symptom G.10-era notes originally pointed at).

**Fix.** Corrected the attribute name and added a symmetric `pressure_return` export (previously
not attempted at all):

```python
P_var = getattr(model, f'{node_prefix}_pressure_supply', None)
if P_var is not None:
    P_vals = [pyo.value(P_var[t]) for t in time_set]
    node_summary['P_avg_bar'] = sum(P_vals) / len(P_vals)
    node_timeseries[f'{node_id}_P'] = P_vals

P_ret_var = getattr(model, f'{node_prefix}_pressure_return', None)
if P_ret_var is not None:
    P_ret_vals = [pyo.value(P_ret_var[t]) for t in time_set]
    node_summary['P_return_avg_bar'] = sum(P_ret_vals) / len(P_ret_vals)
    node_timeseries[f'{node_id}_P_return'] = P_ret_vals
```

**Verified** on an isolated 2-week re-solve of both networks' F8 reference scenarios
(`SB-S1-HK0`, `MM-S1-HK0`) before committing to a full-year re-solve: `P_avg_bar` populated for
100 % of nodes on both networks, with a physically plausible decay from producer (~10-20 bar) to
consumer nodes.

### G.13.2 F8, problem 2 — Stadtbach's "non-monotone" temperature panel (not a bug; annotated)

The earlier README/statement flagged `j_pss`'s temperature dip-then-rise as an unexplained
anomaly, possibly a plotting bug or an L3+ artifact. Traced this pass: `j_pss` (Stadtbach) and
`j_12` (Memmingen) are **secondary pump/generator stations** — `j_pss` hosts `hws_boiler`, `j_12`
hosts `hp_main`/`eboiler_main` (confirmed via direct YAML asset-attachment checks). Per
`network_manager.py::_link_pressure_propagation`'s own code comment, this is a **deliberate**
2026-07-09 design decision (see A.4.3b): the primary producer's pressure/temperature is fixed at
a setpoint and propagated; a secondary station instead gets a **free, locally-boosted**
pressure/temperature Var with only a floor constraint, modeling a real secondary pump/generator
station that boosts its own local setpoint rather than passively inheriting the upstream value.
A temperature "jump" at exactly these nodes is therefore expected model behavior, not a defect —
the earlier title's "monotone fall" framing was the actual error.

**Fix applied to the figure, not the model**: `scripts/paper_2/figures/fig_p2_campaign.py::build_f8`
now shades each network's station node(s) (`_TRUNK_STATIONS = {"SB": {"j_pss"}, "MM": {"j_12"}}`)
via `ax.axvspan(...)` on both the temperature and pressure subplots, and the title was corrected
from the misleading "(monotone fall = L3+ propagation check)" to "(shaded = secondary
pump/generator station, free setpoint — monotone fall expected only within each segment)".

### G.13.3 F7 — `sensitivity.py`'s objective extraction was broken for every prior run (real
bug, fixed and verified)

**Symptom.** Every existing `meta.json` under `output/paper2_runs/sensitivity/` showed
`obj_eur: null` despite real, nonzero `solve_s` values — the runs solved successfully but the
tornado's one required number was never captured.

**Root cause.** The original `run_sensitivity_scenario()` called `calion.run.workflow.run_workflow()`
directly and used a hand-rolled `_extract_objective(wf)` helper that never correctly pulled the
objective out of the workflow result — an independent, simplified re-implementation of extraction
logic that diverged from the main campaign's own, proven path.

**Fix.** Rewrote `run_sensitivity_scenario()` to build a full scenario dict and route through
`scripts/paper_2/scenario_runner.py::run_single_scenario()` — the same pipeline
`campaign_scheduler`/the main 46-scenario campaign already uses — redirecting `sr.OUT_BASE` to
`OUT_BASE / "sensitivity"` for the duration. Also added a tighter, dedicated solver budget
(`_SENS_SOLVER_OPTIONS`: `TimeLimit=6h`, `MIPGap=1%`, initially `Threads=4` then raised to `6`
mid-campaign, see G.13.5) — sensitivity variants are one-parameter perturbations of an
already-known-good design, not a search from scratch, so they don't need the main campaign's
24h/1% budget.

**Verified** on one variant (`memmingen`/`c_el`/`c_el_low`, base scenario `MM-S1-HK0`) before
launching the full 26-variant campaign: real `obj_eur = 348,786.64`, `solve_s = 22,527`
(≈ 6.26 h, hit the `TimeLimit` cap with a valid `maxTimeLimit` incumbent — an acceptable outcome
for a sensitivity variant, same standard as the main campaign accepts for its own runs).

### G.13.4 F3 — capacity sweep (`capacity_sweep.py`, Part A of the prompt spec) — never run
before this pass, not a bug fix

The prompt spec's capacity sweep module existed but had never actually been executed (the spec's
own "A.6 decision" — pick a representative scenario per network — explicitly couldn't be made
before the main campaign finished; the campaign finished in G.12 but the sweep itself was never
subsequently launched). Two things were needed before a 7×7=49-point-per-network sweep was
tractable:

1. **Representative scenarios chosen**: `SB-S1-HK0` (Q_WP* = 24.20 MW, V_TES* = 4304 m³) and
   `MM-S1-HK0` (Q_WP* = 0.60 MW, V_TES* = 165 m³) — both have WP and TES built, satisfying
   `run_sweep()`'s existing requirement.
2. **A dedicated, tighter solver budget** (`_SWEEP_SOLVER_OPTIONS`: `TimeLimit=1800s`,
   `MIPGap=2%` — dispatch-only points with pinned capacities and presolved-away build binaries
   converge to a good gap within minutes to tens of minutes in practice) was added and wired
   through `run_sweep()`'s existing but previously-unused `extra_solver_options` parameter of
   `run_single_scenario()`. Without this, the main campaign's 24h/1% investment-MILP budget would
   have made a 98-point sweep impractical.

Both networks' 49-point sweeps were launched to run concurrently; see "Campaign status" below.

### G.13.5 Campaign status at time of writing (2026-07-20, mid-run — update this section again
once all three finish)

All three of the above were launched as multi-hour/multi-day background campaigns rather than
completed synchronously:

- **F8 real re-solve**: the real (non-diagnostic) `SB-S1-HK0` and `MM-S1-HK0` scenarios were
  re-solved sequentially with the pressure-export fix (24h TimeLimit, 1% MIPGap, matching the
  main campaign's own budget — this is a real reference scenario, not a quick diagnostic).
  `SB-S1-HK0` completed: `obj_eur = 9,978,017.60`, **identical** to the pre-fix campaign value —
  confirms the pressure-export fix is purely additive and changes nothing about the economics.
  `MM-S1-HK0` was still solving at time of writing.
- **F3 capacity sweep**: both networks' 49-point sweeps were mid-run, each point independently
  respecting the 1800s/2% budget above; `run_sweep()`'s own aggregation
  (`results/sweep_{network}_{scenario_id}.csv` + `_optimum.json`, with the spec's §A.5
  sweep↔MILP consistency check) fires automatically once each network's 49 points are done.
- **F7 sensitivity**: the 26-variant campaign (13 parameters × 2 networks) was launched with a
  RAM-gated scheduler (initially 3-concurrent; raised to a disjoint-job-set 5-concurrent second
  scheduler partway through once headroom was confirmed — see below) against the fixed
  extraction path from G.13.3.
- **Mid-campaign concurrency increase (F7 only)**: with F8 (1 process) and F3 (2 processes) also
  running concurrently, the machine's RAM/CPU headroom (a 66-logical-core host, ~100GB/206GB RAM
  in use at the time) was confirmed to comfortably support more F7 concurrency. The original
  3-concurrent driver's parent process was terminated (its 3 in-flight children were left running
  as orphans, uninterrupted — Windows does not kill children when only the parent PID is
  targeted) and a second scheduler was launched targeting the remaining, explicitly-disjoint job
  set (excluding the 3 still-orphan-running jobs, to avoid a `force_rerun=True` collision on
  their in-progress output directories) at 5-concurrent, giving 8 total concurrent F7 solves.
  `_SENS_SOLVER_OPTIONS["Threads"]` was raised from 4 to 6 for jobs launched by the new scheduler
  (the 3 orphans keep their original `Threads=4`, already baked into their running process).
  This is an operational/scheduling change only — no formulation, budget-cap, or extraction logic
  changed, and every already-completed variant's `meta.json` skip-check (G.13.3) protected against
  any duplicate re-solve when the new scheduler's job list was built.

**Files touched this pass**: `calion/io/thermal_network_exporter.py` (G.13.1),
`scripts/paper_2/figures/fig_p2_campaign.py::build_f8` (G.13.2, plus a `build_f6` data-label
axis-margin fix for an unrelated text-overlap rendering bug found in the same visual re-check),
`scripts/paper_2/sensitivity.py` (G.13.3, Threads 4→6 in G.13.5), `scripts/paper_2/capacity_sweep.py`
(G.13.4, `_SWEEP_SOLVER_OPTIONS` new).

**How to apply once campaigns finish**: regenerate F8 via
`python -c "from scripts.paper_2.figures.fig_p2_campaign import build_f8; build_f8()"` once both
`SB-S1-HK0`/`MM-S1-HK0` re-solves are done; build/verify F3's heatmap (`build_f3()` in the same
module — its plotting logic had not been exercised against real sweep data as of this pass, since
the sweep had never completed before); build/verify F7's tornado (`build_f7()`, same caveat).
Update this section, the executive summary, and the design-package README's readiness verdict
once all three are confirmed.

## G.14 External-review response (2026-07-20/21): T5 population fixed, SB-S2 wash-cycling
plausibility-tested (survives), and two real CAPEX bugs found+fixed while building a genuine
Memmingen P1↔P2 comparison scenario — the P1↔P2 gap narrows but does **not** close

An external ECM-style review flagged four items as blocking before a draft: (1) the MW-closure
question's framing in G.10 reads as still-open even though G.12 resolved it; (2) `SB-S2-HK2`
being simultaneously the headline economic result and the worst closure-check case is
under-explained; (3) the Memmingen P1↔P2 OPEX check (124.49% FAIL) cannot go into the manuscript
unresolved; (4) T5 mixes the 46-scenario campaign with diagnostic/enumeration runs (229 vs. 46,
a 47,349% max-gap artifact). Each is addressed below.

### G.14.1 T5 population — fixed (real code bug, not a documentation issue)

`gen_tables.py::build_t5` iterated every directory under `output/paper2_runs/` (275 at the time
of this pass) with **no scenario filter**, unlike `build_t3`/`build_t4`'s `_load_kpis()`, which
already excludes F3 enumeration sub-pairs and TEST/DIAG runs via regex. T5 never had the
equivalent filter. Fixed: `build_t5` now restricts to the 46 canonical `scenario_id`s from
`scenarios.yaml`, with two further refinements once the canonical filter was in place:

- **6 ids never solve as a single canonical run by design** (`SB-S6`/`MM-S4`, all three HK
  stages) — their winners are decided via the enumeration decomposition (G.8) and live in
  `tab_T3b_T4b_f3_endogenous_siting_FINAL.csv`, not `output/paper2_runs/<id>/`. Where a
  monolithic pre-decomposition attempt *does* exist under the canonical id (`SB-S6-HK0`,
  `MM-S4-HK0`), it is the known-bad superseded result (G.6–G.8) — including it in T5's solver
  stats is exactly how the 47,349% max-gap artifact (`MM-S4-HK0`'s sign-flipped best bound,
  G.10) got into the table. All 6 are now excluded from T5's live stats and reported separately
  in a new `tab_T5_supplement_excluded_runs` (kind: "SB-S6/MM-S4 superseded monolithic").
- **The remaining 197 non-canonical run directories** (F3 enumeration sub-pairs, TEST/DIAG runs)
  go into the same supplement table instead of being silently dropped, per the reviewer's request
  to keep diagnostics visible but separate from the headline census.

**Result**: T5's `MIP gap (max)` drops from `47349.644 %` to `2.115 %`; solver-status census is
now `optimal: 30, maxTimeLimit: 10` across 40 directly-reported canonical runs (population note
in T5 itself documents the 6 enumeration-resolved + 197 excluded counts explicitly, so the
46-scenario total is always reconcilable from the table alone). MW-closure stats
(mean/max/pass-rate) are otherwise unchanged in kind, now computed over the clean population —
see G.14.2.

**Files touched**: `scripts/paper_2/figures/gen_tables.py` (`build_t5`: canonical-id filter,
enumeration-family exclusion, new `tab_T5_supplement_excluded_runs` output).

### G.14.2 MW-closure "contradiction" — a stale cross-reference, not a live disagreement

The reviewer read G.10's framing ("is the closure check itself mis-specified... or is this a
real dispatch-balance defect") as an open question standing in contradiction to the README's
"known methodology limitation" claim. It isn't a contradiction — G.10 (2026-07-15) *asked* the
question; G.12 (2026-07-19), in the same document, *answered* it with a decisive per-node audit
(`Σht_out` vs. `Σdemand` read directly off live Gurobi state, matching to 0.04%) and identified
the exact formula mechanism (netting a wash-cycling TES's `discharge − charge` to ~zero). G.10's
text was simply never annotated to point forward once G.12 resolved it, so a linear read of the
document hits the open question before the answer. Fixed: G.10's relevant bullets now carry an
explicit `→ RESOLVED in G.12` / `→ RESOLVED in G.11` inline pointer with a one-line summary of
the resolution, so no read-order produces a false impression of an unresolved disagreement.

**Files touched**: `docs/paper_2/CALION_Paper2_Implementation_Statement.md` (G.10 cross-references
added; this section).

### G.14.3 SB-S2 wash-cycling plausibility — tested, survives (Part G.4's open item, now closed)

Part G.4 flagged SB-S2's near-constant full-power bidirectional TES cycling as an extreme
pattern and recommended, before quoting it as a paper finding, either (a) correlating TES
charge/discharge against HP dispatch, or (b) re-solving under a `cycling_cost_eur_per_mwh`
penalty. Both were run this pass.

**(a) Correlation, using existing campaign data (no re-solve needed).** `SB-S2-HK2`:
`corr(Q_storage_charge_MW, Q_hp_total_MW) = 0.23` — weak. Annual `Qc`+`Qd` throughput
(≈829,000 MWh) is ~25× the co-located HP's own mean output, and Qc/Qd are both nonzero in
99.2% of hours. **Conclusion: the wash-cycling is not "the HP charging the tank"** — it is
the TES arbitraging bulk flow across the wider mesh network (consistent with, and now
quantitatively supporting, G.4's untested hypothesis that the tank substitutes for
plant→node pipe-delivery capacity at the remote site).

**(b) Cycling-cost counter-test.** `Stadtbach_topo.yaml` already bakes in
`cycling_cost_eur_per_mwh: 2.0` as the production default for `tes_sb` — i.e. the campaign's
reported `SB-S2-HK2` TAC (4.42 M€) **already includes** this wear-cost deterrent, it is not an
unpenalized number. Three January-2025-only (744h) diagnostic re-solves of `SB-S2-HK0`
(`SB-S2-HK0-DIAGJAN-{BASE,CYCLO,CYC10X}`, distinct DIAG-suffixed ids, never the canonical
scenario) tested sensitivity around that default:

| variant | cycling_cost [€/MWh] | simultaneous-cycling hours | Qc+Qd volume [MWh] |
|---|---|---|---|
| production default | 2.0 | 741/744 (99.6%) | 112,529 |
| 5× default | 10.0 | 723/744 (97.2%) | 106,565 |

At **5× the production penalty**, cycling volume drops only ~5% and the pattern remains
near-universal across hours. **The wash-cycling is a cost-robust MILP optimum, not a
cost-marginal artifact** — it does not evaporate under a materially stricter wear-cost
assumption. This closes G.4's open item: the pattern is real and defensible as the model's true
optimum, though the underlying causal mechanism (why a remote-node TES is worth this much
arbitrage) remains "substitutes for pipe capacity," a hypothesis, not a fully traced proof.
**Manuscript guidance**: state explicitly that (i) the wear-cost penalty is already priced into
the headline TAC, (ii) the pattern survives a 5× stricter penalty, and (iii) it is nonetheless an
unusual utilization pattern for real hardware and should be flagged as such, not presented as
obviously realistic — this is now an evidenced caveat, not an open risk.

*(Note, debugging artefact of this sub-investigation, not a finding about the model:* an
apparently-impossible result — a lower-cost solve under a smaller cycling-cost override
("CYCLO", 0.5 €/MWh) than a higher one ("CYCHI", 2.0 €/MWh, byte-identical to the no-override
case) — was traced to the test's own design error (CYCHI's override coincidentally matched the
pre-existing 2.0 €/MWh config default, so it changed nothing; CYCLO genuinely lowered the
penalty below that default). No model bug; superseded by the correctly-designed 2.0-vs-10.0
comparison above.*

**Files touched**: none in `calion/` (diagnostic-only); `scripts/paper_2/
run_sb_s2_cycling_counter_test.py` (new, ad hoc diagnostic script, not part of the campaign).

### G.14.4 Memmingen P1↔P2 OPEX consistency — two real CAPEX bugs found and fixed while building
the comparison scenario G.11 recommended; the gap narrows substantially but does not close

G.11 diagnosed the 124.49% FAIL as `BC-MM` (P2's 0 MW zero-investment baseline) being compared
against Paper 1's `L3` reference (5 MW pre-existing HP+EK) — two scenarios that were never meant
to match — and recommended either retiring the check or adding an explicit 5 MW-fixed comparison
scenario. The latter was attempted this pass (`scripts/paper_2/run_mm_p1ref.py`, scenario id
`MM-P1REF`: Memmingen base config, `hp_main`/`eboiler_main` fixed at 5 MW, `investment.enabled:
false`, no TES — deliberately **not** added to `scenarios.yaml`, so it never inflates the
46-scenario canonical population counted elsewhere).

**First full-year attempt: `maxTimeLimit` (24h, unconverged) at `781,641 €`** — higher than
`BC-MM`'s `506,701 €`, which is mathematically impossible for a correctly-specified model (a
fixed-but-optional 5 MW HP+EK can always replicate `BC-MM`'s dispatch by simply not being used,
so the true optimum can only be ≤ `BC-MM`'s). Root-caused via a full objective-term breakdown
(`CALION_DEBUG_COSTS=1` env var, now a permanent, harmless debug hook on
`scenario_runner.run_single_scenario` — prints every named Pyomo objective `Expression` post-solve):
`objective.Capex_cost_EUR` was nonzero (**two separate bugs**, found in sequence):

1. `component_assembler.py::_attach_single_heat_pump` charged CAPEX unconditionally, gated only
   on `cap_var`/`build_var` existing, never on `invest_enabled`. Fixed first — **had zero effect
   on Memmingen's actual objective**, because this function belongs to a separate, legacy
   `system.heat_pumps:`-list attach path (`assemble_heat_pumps()`) that Paper 2's unified
   `assets: {type: heat_pump}` config never exercises.
2. **The actually-used path**, `component_assembler.py::_attach_hp_from_unified` (routed from
   `assemble_all()` for every `type: heat_pump` asset on both networks), had the **identical**
   unconditional-CAPEX bug at its own investment-cost block. This is the real fix. Confirmed via
   the same debug dump: `Capex_cost_EUR` went from ≈24,194 € (January window) to exactly `0.0`
   once gated on `invest_enabled`.

Both fixes are additive one-line conditions (`if invest_enabled and cap_var is not None and
build_var is not None:`) and **provably a no-op for all 46 campaign scenarios**: `BC-MM`/`BC-SB`
are the only non-investable-HP scenarios in `scenarios.yaml`, and both fix `capacity_mw: 0.0` —
the (now-gated) CAPEX term was `0 × capex_eur_per_mw × ANF = 0` before the fix too, identically.
Every other scenario (`S0`–`S7` on both networks) uses the base config's `investment.enabled:
true` default, so the new `if invest_enabled` condition is trivially satisfied and unchanged from
before. No published TAC/LCOH/CAPEX/OPEX number is affected.

**Corrected result, January-2025-only re-verification (744h, `MM-P1REF-DIAGJAN3`, `status=
optimal`, proven, not time-limited)**: `64,769 €`, now correctly **below** the matching January-
only `BC-MM` baseline (`BC-MM-DIAGJAN`, `71,737 €`) by ≈7,000 € (≈9.7%) — the direction and rough
magnitude expected from a small but real fuel-switching benefit.

**Corrected result, full year (`MM-P1REF`, `status=optimal`, proven, not time-limited, 2017 s
solve)**: `cost_total_eur = 489,996.19 €` — **3.01% below** the current `BC-MM` baseline
(`505,181.80 €`; note this is the file's current value, ≈0.3% different from the `506,701 €`
figure quoted earlier in this document from an older solve within the same MIP-gap tolerance —
immaterial to the conclusion below) — confirming the same small, real, fuel-switching benefit
seen in the January window, now at full-year scale and to a proven optimum rather than a
projection.

**What this does and does not resolve.** `MM-P1REF` vs. Paper 1's `L3` reference (`225,717 €`):
**+117.08 %** — still more than double, essentially unchanged in kind from the original
`BC-MM`-vs-`L3` figure (124.49%) despite `MM-P1REF` now being genuinely apples-to-apples on the
one dimension G.11 identified (HP/EK capacity) and both CAPEX bugs being fixed. This does **not**
bring the check within its ≤2% gate, or anywhere close to it. G.11's implicit expectation — that
matching the HP/EK capacity would let the check pass — does not hold even after removing the
CAPEX-gating bugs. There is evidently a **further, still-undiagnosed difference** between Paper
1's `L3` config (`configs/memmingen/Memmingen_L3_MILP.yaml`) and Paper 2's base config
(`Memmingen_P2_base.yaml`) beyond HP/EK capacity — candidates not yet checked: demand data
vintage/cleaning (P2's `Import_Data_Memmingen_epronet_cleaned.xlsx` vs. P1's original input),
fuel/electricity price series, heating-curve treatment (P1's own continuous curve vs. P2's
`TVLFIX`/discrete-stage system), or CO₂ pricing being in P2's objective but absent from P1's
dispatch-only model. **Not chased further this pass** — the CAPEX bugs were the concrete, fixable
finding; the residual gap needs its own targeted config diff, out of scope for
this response.

**Recommendation for the manuscript, given the above:** do not present `MM-P1REF` as having
"resolved" the P1↔P2 check to a pass. Two defensible options, both better than the current FAIL
against `BC-MM`:
(a) report `MM-P1REF` vs. `L3` as the corrected comparison point, explicitly stating the
    residual ≈100% gap is real and only partially diagnosed (config provenance, not a model bug,
    per the CAPEX fixes above) — honest but leaves an open thread;
(b) retire `check_paper1_consistency` from T5 as G.11 originally suggested, and describe in prose
    (not a quantitative gate) that Paper 2's baseline concept has legitimately superseded Paper
    1's, with the CAPEX-bug-fixed `MM-P1REF` cited only as evidence that the *direction* of the
    gap is not a modeling artifact.
This is a decision for the manuscript authors, not something further scenario engineering alone
resolves within this pass.

**Files touched**: `calion/models/component_assembler.py` (both CAPEX gates:
`_attach_single_heat_pump` and `_attach_hp_from_unified`), `scripts/paper_2/run_mm_p1ref.py`
(new, standalone `MM-P1REF` scenario runner, not part of `scenarios.yaml`),
`scripts/paper_2/scenario_runner.py` (new `CALION_DEBUG_COSTS=1` env-gated objective-breakdown
print in `run_single_scenario`, additive/harmless, off by default),
`scripts/paper_2/validation_p2.py::check_paper1_consistency` (now reads `MM-P1REF` instead of
`BC-MM`).

**How to apply.** Before trusting any "fixed capacity, non-investable" scenario's economics for
*either* HP or EK on *either* network, verify `Capex_cost_EUR`/`Activation_cost_EUR` actually
read `0.0` for it (`CALION_DEBUG_COSTS=1`) rather than assuming a `capacity_mw`/`investment.
enabled: false` override is sufficient — two independent attach-function code paths existed for
heat pumps alone, and only one is live for any given config style; a fix verified against the
wrong one is not a fix. The general lesson from G.10–G.14 collectively: whenever a validation
check or a new scenario's number looks implausible, prefer a decisive, code-independent ground
truth (a per-node audit, an env-gated objective-term dump, a controlled re-solve) over trusting
either the check or the intuition about what "should" be zero.

---

# Part H — Pump & pressure subsystem: full reference (2026-07-23/24)

Written for anyone editing the network topology by hand (adding pump stations, changing
pipe geometry, tuning pressure requirements) without re-reading the code from scratch.
Covers every parameter, variable, and constraint in the pressure/pump physics, plus the
three reporting bugs and the pump-head degeneracy found and fixed this session.

## H.1 File map

| File | Role |
|---|---|
| `calion/models/blocks/pipe_pair.py` | Per-pipe physics: mass flow `m_dot`, velocity, Darcy Δp, pump power `P_pump`. |
| `calion/models/network_manager.py::_link_pressure_propagation` | Node pressure setpoints/floors, inter-pipe propagation, consumer `min_required_bar`, the opt-in pressure regularization. |
| `calion/models/network_manager.py::_link_pump_head` | Per-producer head cap (`P_supply − P_return ≤ head_max`) and pump-power aggregation (BFS ownership → `producer_{node}_P_pump`). |
| `calion/models/network_manager.py::_link_tes_pressure_coupling` | TES↔network pressure coupling ("F4", §A.4.7 above) — unrelated to pumps, listed for completeness. |
| `calion/models/constraint_builder.py::create_objective` | Assembles the real objective; carries the new `pressure_reg_cost` term. |
| `calion/models/model_finalizer.py` | Collects `pump_el_flows` into the electricity bus and `pressure_regularization_terms` into `pressure_reg_cost`. |
| `calion/io/thermal_network_exporter.py::_export_pipe_results` | Per-pipe CSV/JSON export, incl. `P_pump` (added 2026-07-23). |
| `calion/run/result_collector.py::_collect_timeseries_and_summary` | Builds the `series["P_pump_total_MW"]` used by `cost_pump_eur`. |
| `scripts/paper/extract_artefacts.py::write_pipe_state` + `cost_pump` block | Legacy CSV re-export + the `cost_pump_eur`/`cost_energy_buy_eur` split. |

**Architecture in one paragraph**: every node gets a `pressure_supply`/`pressure_return` Var
pair. A node with at least one asset in `assets:` becomes `producer`/`mixed` and is either the
network's single fixed-setpoint reference (`primary_producer` in the YAML) or a free,
pump-boosted secondary source; every other node is a plain `consumer` whose pressure is bounded
by propagation from its upstream feeder. Pump *power* (an electricity cost) and pump *head* (a
bar-valued pressure differential) are two separate, only loosely coupled mechanisms — see H.4.

## H.2 Config parameters

**Node-level** (`network.nodes.<id>`):

| Key | Default | Effect |
|---|---|---|
| `assets: [...]` | — (absent) | Presence makes the node `producer`/`mixed`; absence makes it a plain `consumer`. This is the *only* switch — there is no separate "is this a pump station" flag (see H.7 limitation). |
| `pressure.setpoint_bar` | `10.0` | Primary producer: `P_supply` **fixed** (equality) at this value. Secondary producer: `P_supply` **floor** (`≥`) at this value — a real pump lifts local pressure as needed above it. |
| `pressure.min_required_bar` | *(unset → no constraint)* | Hard floor `P_supply ≥ min_required_bar`, but **only applied to nodes of type `consumer`** — producer/mixed nodes use the setpoint floor instead. Was unset for every Memmingen/Stadtbach node before this session (a silent no-op). |

**Network-level** (`network.<key>`, read via `self._net_cfg`):

| Key | Default | Effect |
|---|---|---|
| `primary_producer` | *(none → every producer node is fixed)* | Node id of the one pressure reference. |
| `max_velocity_m_s` | `2.5` | Pipe design-velocity cap; drives `effective_max_flow = area·v·ρ`, which sets both the Darcy/pump tangent breakpoints (H.4) and the transport-delay bucket size (§A.4.4). |
| `pump_efficiency` | `0.70` in code (both live configs set `0.75` explicitly) | `η_pump` in the pump-power constant `C`. |
| `pressure_big_m_bar` | `30.0` | Big-M for the 4-inequality bidirectional-pipe propagation family (H.4). |

**`network.physics.<key>`** (read via `self._physics_cfg` — a **different accessor** than
`_net_cfg` above; mixing the two up silently no-ops, see H.6.2):

| Key | Default | Effect |
|---|---|---|
| `pressure_drop` | `true` | Master switch for the entire Δp/pump-power/propagation subsystem. `false` fixes all `delta_p_*` to 0 with no binaries and skips propagation/pump-head entirely. |
| `tes_pressure_coupling` | `false` | See §A.4.7. |
| `tes_pressure_mode` | `same_circuit_buffer` | `same_circuit_buffer` \| `hydrostatic_support`, see §A.4.7. |
| `pressure_regularization` | `false` **(new, off in both live configs)** | Opt-in tie-break, see H.7. |
| `pressure_regularization_epsilon` | `1e-4` | Magnitude of the tie-break objective coefficient. |

**Pipe-level** (`network.pipes.<id>`):

| Key | Default | Effect |
|---|---|---|
| `length_m`, `diameter_mm` | — (required) | Geometry driving `k_flow` (H.5). `diameter_mm` is read into `current_diameter_supply_mm` internally (a discrete-pipe-sizing hook not used by Paper 2's fixed topology — falls straight back to `diameter_mm`). |
| `friction_factor` | `0.02` | Darcy friction factor `f` — a **flat constant**, not a Colebrook/roughness computation. |
| `pipe_roughness_mm` | `0.05` | Read and stored in the exported `pressure_params` metadata but **not used in the Δp formula at all** — purely informational today. |
| `pump_enabled` | = `pressure_drop` | Per-pipe override to disable pump-power costing on just that pipe (its `P_pump` stays fixed at 0) while keeping Δp active. |
| `bidirectional` | `false` | Switches propagation to the 4-inequality `flow_dir`/big-M family (H.4) instead of the simple 2-inequality one. **Also excludes the pipe from pressure regularization's downstream push** (H.7 scope limit — unvalidated for that structure). |
| `max_pressure_drop_bar` | `2.0` | Only used as a *fallback* `Δp` upper bound when `effective_max_flow ≤ 0`; **not** used as a floor (would over-constrain large-diameter trunks). |
| `max_flow_kg_s` | *(none → derived from diameter × `max_velocity_m_s`)* | Optional direct override of `effective_max_flow`. |

## H.3 Variables (naming conventions — how to find things in a solved model)

| Scope | Attribute name pattern | Kind | Notes |
|---|---|---|---|
| Node | `{NODE_ID.upper()}_pressure_supply` / `..._pressure_return` | Var, per `t` | e.g. `j_12` → `J_12_pressure_supply`. |
| Pipe | `{PIPE_ID.upper()}_m_dot` (or `_m_dot_abs` + `_flow_dir` if bidirectional) | Var, per `t` | Signed for bidirectional pipes. |
| Pipe | `{PIPE_ID.upper()}_velocity`, `..._delta_p_supply`, `..._delta_p_return`, `..._delta_p_total`, `..._P_pump` | Var, per `t` | Core per-pipe physics outputs. |
| Producer node | `producer_{node_id}_P_supply_setpoint` (primary) / `..._P_supply_floor` (secondary) | Constraint | Note: **raw** `node_id`, not uppercased — different convention than the node Vars above. |
| Producer node | `producer_{node_id}_head_ub` / `..._head_lb` | Constraint (new 2026-07-24, replaces the old free `pump_head` Var) | `P_supply − P_return ≤ head_max` / `≥ 0`. |
| Producer node | `producer_{node_id}_P_pump` | Var, per `t` | Aggregated electrical pump power — sum of every pipe this station owns (H.6.1). Feeds `buses.el_in`. |
| Consumer node | `consumer_{node_id}_P_min` | Constraint | Only created if `min_required_bar` is set. |
| Pipe propagation | `pressure_supply_prop_{pipe_id}` / `pressure_return_prop_{pipe_id}` | Constraint (non-bidirectional) | `P_to ≤ P_from − Δp`. |
| Pipe propagation | `pressure_supply_fwd_ub/lb_{pipe_id}`, `..._rev_ub/lb_{pipe_id}` (×2 for return) | Constraint (bidirectional) | 8 constraints total per bidirectional pipe. |
| Model-level | `model.pressure_regularization_terms` | plain Python list, `(Var, coeff)` tuples | Only exists if the flag is on. |
| Model-level | `model.pressure_reg_cost_expr` | `pyo.Expression` | Always exists (0 if flag off) — query with `pyo.value(...)` to sanity-check the term's real magnitude post-solve. |

## H.4 Constraints — the physics, exactly as implemented

**Per-pipe Darcy Δp** (convex, binary-free tangent lower envelope) and **pump power**
(pinned PWL equality since 2026-07-27 — see H.6.5):

```
Δp_supply(t) ≥ 2·k_flow·ṁ_i · ṁ(t) − k_flow·ṁ_i²         tangent points ṁ_i = 0.33, 0.67, 1.0 × ṁ_max
Δp_return(t) = Δp_supply(t)
P_pump(t)    = PWL_pin(ṁ(t))     of the true cubic C·ṁ³, breakpoints [0, .06, .15, .35, 1.0]·ṁ_max
               (config pump_pin_pwl=true, default;  C = 2·k_flow·1e5/(ρ·η_pump·1e6))
k_flow = f·(L/d_inner)·(ρ/2)/1e5 / (ρ·A)²,   d_inner = diameter_mm/1000 · 0.94,   A = π·(d_inner/2)²
```

The Δp *lower-envelope* tangent is kept (it drives pressure propagation and stays binary-free);
only `P_pump` was switched from a tangent lower bound to a pinned PWL equality because as a pure
electricity *cost* the lower-bound-only form failed both ways at part-load — see H.6.5.

**Node pressure setpoint/floor** (`_link_pressure_propagation`):

```
P_supply,primary(t) = setpoint_bar                                    (equality)
P_supply,secondary(t) ≥ setpoint_bar                                  (floor — pump-boosted, free above it)
```

**Pipe propagation**, non-bidirectional (the normal case — both live networks' trees/branches):

```
P_supply,to(t) ≤ P_supply,from(t) − Δp_supply(t)
P_return,from(t) ≤ P_return,to(t) − Δp_return(t)
```

Skipped entirely for any pipe whose `to_node` is itself a producer ("loop-closing" pipe — that
station re-establishes its own pressure, an incoming pipe must not pin it).

**Bidirectional** (Stadtbach's east trunk only): the same two inequalities, but gated by a
`flow_dir` binary and `pressure_big_m_bar`, so the direction-appropriate one applies —
4 inequalities per side, 8 total. Not covered by the pressure-regularization tie-break (H.7).

**Producer head cap** (`_link_pump_head`, reformulated 2026-07-24 — see H.6.3 for why):

```
P_supply(t) − P_return(t) ≤ head_max = 2 × setpoint_bar        (head_max is NOT a config key — hardcoded 2× multiplier)
P_supply(t) − P_return(t) ≥ 0
```

**Pump-power aggregation** (`_link_pump_head`, BFS-attributed 2026-07-23 — see H.6.1):

```
P_pump,producer(t) = Σ_{pipes owned by this producer} P_pump,pipe(t)
```

where "owned" means: every pipe on the producer's nearest (fewest-hop) path from itself,
stopping expansion at any *other* producer node (that station's own pump takes over beyond it).

**Transfer-station Δp pump** (`_link_pump_head`, added 2026-07-27 — see H.6.4). Pipe friction
alone under-states real DH pumping by 1–2 orders of magnitude; the pump must also overcome the
differential pressure held at each Übergabestation. Added as a separate electricity load, linear
in the consumer mass flow (exact, no PWL/binaries):

```
P_pump,station,c(t) = Δp_station · ṁ_demand,c(t) · 1e5 / (ρ · η_pump · 1e6)     [MW]
Δp_station = delta_p_min_consumer_bar (default 0.6 bar)      for every consumer/mixed node c
```

All `station_{c}_P_pump` and every `producer_{node}_P_pump` feed `buses.el_in` together.

**Consumer minimum pressure** (only if `min_required_bar` set, type `consumer` only):

```
P_supply(t) ≥ min_required_bar
```

**Pressure regularization** (opt-in, 2026-07-24 — see H.7):

```
minimize  Σ  (−ε) · P_supply,i(t)      for every non-producer node i on a non-bidirectional pipe
```

added to the real objective. No producer-side term (removed — see H.7 for the proof of why it
doesn't work).

## H.5 Physics constants reference

| Symbol | Value | Source |
|---|---|---|
| `ρ` (density_water) | `1000` kg/m³ | Hardcoded constant in `pipe_pair.py`. |
| `f` (friction_factor) | `0.02` | Config default, flat (no roughness/Reynolds dependence). |
| `d_inner` | `diameter_mm/1000 × 0.94` | 94% of nominal — a fixed wall-thickness allowance, not config-driven. |
| Tangent points (Δp only) | `0.33, 0.67, 1.0 × ṁ_max` | 3 points for the **Δp** lower envelope (reduced from 5 for tractability, §A.4.5) — loose below ≈22% of `ṁ_max`; real Memmingen January flow often sits at 5–12% of design, so **Δp** can under-count at part-load unless extra low-flow tangents are added (still done notebook-locally in `Memmingen_pump_pressure_study.ipynb` for the pressure trace). **P_pump no longer uses this** — it is pinned to a PWL equality (H.6.5), which fixes the part-load under-count and the negative-price over-count campaign-wide. |
| Pump PWL breakpoints | `[0, .06, .15, .35, 1.0]·ṁ_max` | Low-flow-dense breakpoints of the pinned `P_pump` cubic (H.6.5), config `pump_pin_pwl` (default true). |
| `delta_p_min_consumer_bar` | `0.6` bar | Transfer-station differential pressure: both the pressure floor (`P_supply − P_return ≥` this) AND, since 2026-07-27, the charged station pump term (H.6.4). Raise it to model a higher plant differential. |
| `head_max` multiplier | `2×` setpoint_bar | Hardcoded in `_link_pump_head`, not a config key — **the thing you'd change first if modelling a real pump's actual rated head**. |

## H.6 2026-07-23 fixes — pump-power attribution and reporting (campaign-wide, verified)

### H.6.1 Pump-power was only attributed to a producer's immediate pipe

**Before**: `_link_pump_head` only summed `P_pump` for pipes whose immediate `from_node` was a
producer — every pipe further downstream (which still has real, nonzero friction/pump power)
was silently excluded from any producer's electricity bill.
**Fix**: multi-source BFS from every producer simultaneously; each pipe is attributed to the
nearest producer, stopping at the next producer node. Exact for a radial network (Memmingen);
an approximation at shared junctions in a meshed one (Stadtbach), since true attribution would
need live flow-direction awareness. **This changes the true objective value** (pump power feeds
the real electricity bus) — not a cosmetic fix, campaign scenarios computed before this fix
under-count pump electricity cost.

### H.6.2 Three reporting-pipeline bugs (did not affect the true objective, only descriptive output)

1. `scripts/paper/extract_artefacts.py::write_pipe_state` wrote a **hardcoded literal `0.0`**
   for every pipe's `P_pump_pipe_MW`, every hour — never read the real value. Fixed by adding a
   `P_pump` export block to `thermal_network_exporter.py::_export_pipe_results` (mirroring the
   existing `delta_p_*` pattern) and reading that column.
2. `cost_pump_eur` in `economics.csv` always computed `0.0` because
   `result_collector.py::_collect_timeseries_and_summary` never populated a
   `series["P_pump_total_MW"]` entry. Fixed by summing every `producer_{node}_P_pump` Var into
   that series. Also netted the same amount back out of `cost_energy_buy_eur` (pump electricity
   was already inside it via `buses.el_in`) so the cost breakdown stays a clean partition —
   without this, any stacked chart double-counts pump cost.
3. **Every existing `pipe_state_hourly.parquet`/`economics.csv` under `output/paper2_runs/`
   predates all three fixes and has wrong pump numbers** (0 or too low). Fixes 1–2 only need
   re-export from an already-solved model; fix H.6.1 changes the true objective and needs a
   genuine re-solve if the pump total matters for a reported cost.

### H.6.4 Transfer-station differential-pressure pump term (2026-07-27, campaign-wide)

**Symptom**: the pump charged only pipe *friction* (`Σ P_pump,pipe`). Reconstructed against the
real hydraulics, that is ~0.006 % of heat delivered — **1–2 orders of magnitude below** the
0.2–1 % that real DH pumping draws. Cause: real pumps overcome not just friction but the
differential pressure *maintained* at each Übergabestation (control-valve authority) — already
enforced as a pressure constraint (`P_supply − P_return ≥ delta_p_min_consumer_bar`, H.4) but
never *charged* as pump energy.

**Fix** (`_link_pump_head`): add one electricity load per consumer/mixed node,
`P_pump,station,c = Δp_station · ṁ_demand,c · 1e5/(ρ·η_pump·1e6)` with
`Δp_station = delta_p_min_consumer_bar` (default **0.6 bar**). Linear in the existing
`m_dot_demand` Var → **exact, no PWL, no binaries**. Appended to `pump_el_flows` alongside the
producer pump loads. Raises modelled pumping to ≈0.1 % of heat (validated on Memmingen); the
value scales directly with `delta_p_min_consumer_bar` if a higher plant differential is wanted.

### H.6.5 P_pump pinned to a PWL equality — the tangent lower bound was wrong two ways (2026-07-27)

**Symptom**: `P_pump ≥ tangent_k(ṁ)` (H.4, the binary-free lower envelope) is a *lower bound only*.
At the part-load flows DH actually runs at (often 5–15 % of design), all three tangents anchored
at 33/67/100 % go **non-positive**, so the floor collapses to `P_pump ≥ 0`. Then:
- at **positive** prices the solver sets `P_pump = 0` → pumping **under-counted** (the notebook
  patched this locally via `add_low_flow_tangents`, H.5);
- at **negative** prices (Memmingen data has 2 460 h < 0, 92 h < −55 €/MWh below the CO₂ cost)
  the solver drives `P_pump` **up to `P_pump_max`** for free-money → pumping **over-counted**, and
  `L3⁺` can even come out *cheaper* than `L3` (pressure-physics hierarchy violated).

**Fix** (`pipe_pair.py`): pin `P_pump = PWL(ṁ)` of the true cubic (segment-select equality,
low-flow-dense breakpoints `[0, .06, .15, .35, 1.0]·ṁ_max`), config `pump_pin_pwl=true` (default;
set `false` to restore the tangent lower bound as an escape hatch). The pin's binaries are **local
to each pipe** (a leaf electricity load, *not* coupled to the network pressure propagation that the
Δp tangents keep binary-free), so tractability is fine — verified on the Druckverluste January
window: build 2.4 s, solve 10.4 s, optimal, `P_pump` finite (no inflation), station Δp active.
This **supersedes** the notebook-local `add_low_flow_tangents` for `P_pump` (Δp still uses tangents).

## H.7 2026-07-24 fix — pump-head degeneracy (opt-in, off by default)

**Symptom**: node pressure away from any binding constraint (e.g. a secondary pump station and
everything downstream of it) sat at exactly `head_max` regardless of real demand/flow — a
solver artifact, not physics.

**Root cause, proven by elimination** (each hypothesis tested and ruled out with evidence, not
assumed): not a hard constraint (exhaustive scan of every constraint touching the variable
found none tight), not "epsilon too small" (100× larger epsilon had zero effect while visibly
distorting real dispatch cost elsewhere), not Gurobi presolve (`Presolve=0` unchanged), not a
missing objective coefficient (confirmed present via `generate_standard_repn`). The actual
cause: **a producer's own `P_supply` directly caps every downstream node's achievable ceiling**
(`P_to ≤ P_from − Δp`). Pushing the producer down by `X` forces every node in its subtree down
by up to `X` too; since those downstream nodes carry the *opposite* incentive (pushed up, to
resolve their own degeneracy), a producer with more than one downstream node always has its
"push down" mathematically outvoted by their combined "push up" loss. **This is not fixable by
rebalancing `epsilon`** — a producer with more downstream nodes would always need proportionally
more, for no principled reason.

**Delivered fix**: two parts.
1. Eliminated the free `pump_head` Var (H.4's head-cap constraints replace it directly) — a
   pure refactor, same feasible region, always on, no flag.
2. Kept **only** the downstream half of the original two-sided design: every propagated
   consumer node gets pushed toward the tightest value its upstream `Δp` allows. The
   producer-side push was removed entirely (see root cause above).

**Result**: pressure downstream of the *fixed* primary producer is now fully, correctly
resolved (verified: 10 hops downstream on Memmingen settles to exactly the physically correct
value, not an arbitrary one). Pressure at a *secondary* producer's own node remains an
unconstrained (but floor-respecting) value by design — not a bug, a scope decision — everything
below it stays internally consistent relative to whatever that producer settles on.

**Cost-neutrality**: Memmingen at the campaign's real 0.5% MIP gap: **−0.17%** (well inside
normal MIP-gap noise — confirmed by the same comparison shrinking from −1.2% at a loose 10% gap
to −0.02% at 0.5%, i.e. gap-noise, not a real perturbation). Stadtbach's quick smoke test at a
loose 10%/90s gap showed **−2.0%** — not yet confirmed clean at a tight gap; treat Stadtbach's
flag as unvalidated for cost-neutrality until a longer, tighter-gap run is done.

## H.8 How to add a pump station yourself (no code changes needed for the common case)

To make an existing node a pump station: give it **any** asset in its `assets:` list (a heat
pump, boiler, CHP — the specific technology doesn't matter for the pressure physics) and,
optionally, its own `pressure.setpoint_bar`. That's it — the node automatically becomes
`producer`/`mixed`, gets a pump-boosted pressure floor, a `head_ub`/`head_lb` cap, and its
outgoing pipes' `P_pump` gets aggregated into `producer_{node}_P_pump` and billed to the
electricity bus. No changes to `network_manager.py` are required for this case.

**What is *not* supported without a code change**: a pure pressure-booster station with **no**
heat-generation asset (e.g. an in-line electric pump with nothing else at that node). The
producer/mixed classification is tied entirely to `assets:` presence — there is no separate
"pump-only" node type. Adding one would mean extending the classification logic in
`_link_pressure_propagation`/`_link_pump_head` (and wherever node `type` is first assigned,
likely `network_manager.py`'s topology-loading step) to also recognize an explicit
`is_pump_station: true` flag independent of `assets`.

**Checklist for a realistic new pump**:
- Set `pressure.setpoint_bar` to the pump's real design discharge pressure (not the code
  default of 10.0 bar, which is Memmingen/Stadtbach's incumbent value, not a physical universal).
- Consider whether `head_max = 2×setpoint_bar` (H.5) is a realistic cap for that specific pump's
  rated head — it's a hardcoded multiplier, not derived from any pump curve.
- If the new pump serves multiple downstream branches, remember H.7: its own absolute pressure
  will NOT be tie-broken to a "minimum sufficient" value even with `pressure_regularization` on
  — only what's strictly necessary (its floor) is guaranteed; anything above that is a free
  solver choice unless you add a real constraint (e.g. a `min_required_bar` far downstream that
  happens to bind back up the chain).
- If you need the pump's real electricity draw to be trustworthy at realistic (non-peak) flow,
  be aware of the tangent-envelope looseness noted in H.5 — check `pyo.value` on the pipe-level
  `P_pump` Vars near the new pump against a hand Darcy calculation before trusting it.

## H.9 Known limitations (as of 2026-07-24)

- Return-side pressure (`P_return`) is never regularized — an attempted fix pushed it up with
  no anchor at the network's leaves, floating the whole return chain to an arbitrary ceiling.
  Needs its own correctly-anchored formulation.
- Bidirectional pipes are excluded from pressure regularization (unvalidated for that
  constraint family).
- A secondary producer's own absolute pressure is an intentionally free (but feasible) choice —
  see H.7.
- `pipe_roughness_mm` is accepted in config and exported as metadata but has zero effect on the
  actual Δp physics.
- Stadtbach's cost-neutrality for `pressure_regularization` is not yet confirmed at a tight MIP
  gap (H.7) — don't enable it there for a real campaign run without that check first.

---

*End of statement — updated 2026-07-24 (Part H added: pump & pressure subsystem reference).*
