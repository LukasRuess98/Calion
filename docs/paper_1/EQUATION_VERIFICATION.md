# Equation Verification Checklist  —  Paper ↔ Source Code

> **Goal.** For every equation in `Paper_draft.tex`, verify that the source-code implementation is faithful, document any deviation, and either (a) bring code into line with paper, or (b) update paper to match code.
>
> **Usage.** Walk through this file top-to-bottom. For every row of every table:
>   1. Locate the equation in `Paper_draft.tex` (label given).
>   2. Find the implementing function/file (best-guess location given — verify by `rg`/`grep`).
>   3. Run the **check** in the right column.
>   4. Mark `✅` (matches), `⚠️` (matches with caveats — document), or `❌` (does not match — fix).
>   5. Append findings to `output/paper_runs/EQUATION_AUDIT.md`.
>
> **Outcome.** A signed-off `EQUATION_AUDIT.md` table that the user can paste straight into the paper's reproducibility appendix.

---

## How to use the checks

Each check is a small unit-test specification. Implement them in `tests/test_paper_equations.py` (pytest). Use **synthetic mini-instances** (1 node, 1 pipe, 24 h) so failures are easy to localise. Mark each with a pytest marker `@pytest.mark.eq("eq:label")`.

---

## Section 3.2 — Basic MILP (L1 / L2 / L3)

### Objective & costs

| Eq label | Equation | Source (best-guess) | Check |
|---|---|---|---|
| `eq:objective` | `min Z = C^en + C^fuel + C^dump + C^CO2 + C^dem + C^pump` | `src/optimization/objective.py::build_objective` | Sum the six terms from a solved instance and compare to `model.objective.expr()`. Equality up to 1e-6. |
| `eq:cost_energy` | `C^en = Δt Σ_t (P^buy·λ^buy − P^sell·λ^sell)` | `objective.py::cost_energy` | For a 24 h run with constant prices, value matches manual calc. **Sign convention:** P^buy ≥ 0, P^sell ≥ 0, both nonneg vars, simultaneity prevented by Big-M. |
| `eq:cost_fuel` | `C^fuel = Δt Σ_g Σ_t F_{g,t}·λ^fuel_g` | `objective.py::cost_fuel` | Test with 1 generator at 100 % load: expected = capacity × 8760 × λ. |
| `eq:cost_dump` | `C^dump = Δt Σ Q^dump · λ^dump` | `objective.py::cost_dump` | Inject artificial over-supply, check Q^dump pays the penalty. |
| `eq:cost_co2` | `C^CO2 = (λ^CO2/1000)·(Σ E_grid + Σ E_fuel)` | `objective.py::cost_co2` | Set λ^CO2 = 0 → term vanishes. Set EF=0 → term vanishes. |
| `eq:cost_demand` | `C^dem = λ^dem · f^yr · P^peak` | `objective.py::cost_demand` | `f^yr = T·dt/8760`. For full-year run: f^yr = 1. P^peak realised via `P^peak ≥ P^buy_t  ∀t`. |
| App. B (`eq:sell_price`) | Floor / spread / haircut formula | `pricing.py::compute_sell_price` | Build a 4-row truth table covering: above floor, below floor, above zero after fees, below zero after fees. |

### Energy-balance constraints

| Eq label | Equation | Source | Check |
|---|---|---|---|
| `eq:balance_L1` | L1 aggregated balance | `network/aggregated.py::balance` | Σ_t Q_supply_t = Σ_t Q_demand_t exactly (no losses). |
| `eq:balance_prod` / `eq:balance_consumer` | nodal balances for L2/L3 | `network/nodal.py::balance` | For each node: inflow + local production = outflow + local demand + dump. Per-hour residual < 1e-6 MW. |
| `eq:balance_el` | global electricity balance | `network/electricity.py` | P^buy + P_chp_el = P^sell + P_hp_el + P_ek_el + P_pump (last term 0 for L1/L2/L3). |
| `eq:grid_bigm` | Big-M for buy XOR sell | `network/electricity.py::grid_bigm` | z_t binary; P^buy ≤ M·z, P^sell ≤ M·(1−z). Check no hour has both > 0. |

### Loss model (basic)

| Eq label | Equation | Source | Check |
|---|---|---|---|
| `eq:loss_supply` | `Q^loss,sup = U·L·(T_sup − T_ground)/1e6` | `network/loss.py::pipe_loss_supply` | Unit consistency: W·m·K/m·K → W → MW after /1e6. Deterministic given temperature profile. |
| `eq:loss_return` | analogous | same | analogous |

[Hard catch] L1 must have **zero** loss terms. Check `model.constraints['pipe_loss']` is empty for L1.

### Components

| Eq label | Equation | Source | Check |
|---|---|---|---|
| `eq:hp_split` | Q_h = Q_wrg + Q_def | `assets/heat_pump.py` | Sum equality holds in solution. |
| `eq:hp_pel` | P_el = Q_wrg/COP_wrg + Q_def/COP_def | same | For known Q_wrg, Q_def, COPs: manual P_el matches solver output. |
| `eq:hp_cap` | min part-load + capacity | same | For a forced-on hour: Q_h ≥ 0.2·Q̄. For off hour: Q_h = 0. |
| `eq:storage_soc` | SoC dynamics with self-discharge | `assets/storage.py::soc_dynamics` | Multi-step: with α=0, η=1, no charge → SoC constant. With α>0, no charge → SoC[t] = SoC[0]·(1−α)^t. |
| `eq:gen_thermal` | Q = η·F | `assets/boiler.py` | Trivial. |
| `eq:p2h` | Q = η·P_el | `assets/electrode.py` (must add) | Same. |
| (CHP, no eq number) | Heat-to-power coupling | `assets/chp.py` | Q_th/P_el ratio constant; F_gas balances. |

### Emissions

| Eq label | Equation | Source | Check |
|---|---|---|---|
| `eq:em_grid` | E^CO2,grid = P^buy · e_grid · Δt | `accounting/co2.py` | Sum over horizon equals manually computed total. |
| `eq:em_fuel` | E^CO2,fuel = F · e_fuel · Δt | same | analogous |

---

## Section 3.3 — Extended Physics (L3⁺ MILP)

### Pressure drop & pumping

| Eq | Equation | Source | Check |
|---|---|---|---|
| `eq:darcy` | Δp = f_D·L/D · (8 ṁ²)/(ρ²π²D⁴) | `physics/pressure.py::darcy_weisbach` | Mass-flow ↔ pressure scalar test against textbook Moody example (Re=10⁵, f_D=0.018, DN200, 100 m, 50 kg/s). |
| `eq:massflow` | ṁ = Q/(c_p·ΔT) | `physics/massflow.py` | Determinstic given Q and temperature profile. |
| `eq:pressure_pwl` + SOS2 | PWL for Δp(Q) with K segments | `physics/pwl.py::dp_pwl` | (a) Σ w_k = 1 (b) at most two adjacent w_k nonzero (SOS2) (c) interpolated value matches Δp at K+1 breakpoints exactly. |
| `eq:pwl_error_bound` | ε ≤ R·Q̄²/(4K²) | – | Derive the bound for K=5, plug in numerical Q̄ for each pipe, write to `linearization_diagnostics.csv`. |
| `eq:pump_power` | P_pump = (1/η_pump) · Σ ṁ·Δp/ρ | `physics/pump.py` | Closed-form for known operating point matches solver. |
| `eq:pump_pwl` | PWL of P_pump(Q) | `physics/pump.py::pump_pwl` | Same SOS2 invariants as Δp PWL. **Note:** paper uses the same SOS2 weights `w_k` for both Δp and P_pump — verify code re-uses the *same* set, otherwise the equations are inconsistent. |
| `eq:cost_pump` | C^pump = Δt·Σ P_pump·λ^buy | `objective.py` | Sum check. |

> **Catch:** check that the *electricity balance* in §3.2.6 (`eq:balance_el`) actually subtracts P_pump for L3⁺/L3^NL but not for L1/L2/L3. If pump electricity isn't drawn from the same buy/sell pool, the comparison is invalid (pump gets free electricity).

### Temperature propagation

| Eq | Equation | Source | Check |
|---|---|---|---|
| `eq:temp_prop` | Exact exponential decay | – (NL only) | Implemented only in L3^NL (PWL elsewhere). |
| `eq:decay_pwl` | PWL of φ(ṁ) = exp(−c/ṁ) | `physics/decay.py::phi_pwl` | At K nodes: φ_PWL = φ_exact. Worst case off-node error within bound from §App. D. |
| `eq:temp_prop_lin` | Taylor-expanded propagation | `physics/temperature.py::propagate_lin` | Two regimes: ṁ at nominal → equation reduces to ṁ-only PWL form. T_n1 at nominal → reduces to upstream-temperature-only form. |
| `eq:loss_extended` / `eq:loss_ext_lin` | Bilinear loss collapsed to linear | `network/loss.py::pipe_loss_extended` | Set ṁ=ṁ_nom in code, compare loss to basic-physics value (Eq. 13/14). Should match within PWL accuracy. |
| – | Nodal mixing (multiple inflows) | `network/nodal_temp.py` | For tree topology (single inflow): T_node = T_pipe_out. For >1 inflow (synthetic networks with rings or merges): flow-weighted. **Currently primary case is tree; rings would require non-convex bilinear mixing — defer to future work as paper says.** |

### Transport delay

| Eq | Equation | Source | Check |
|---|---|---|---|
| `eq:delay` | τ = L·ρ·A/ṁ_nom | `physics/delay.py::compute_tau` | Plug numerics: Memmingen DN450 trunk, ṁ_nom from peak demand → τ ~ 4–5 min as Tab. 6. |
| `eq:delay_discrete` | k_p = round(τ/Δt) | same | Δt=1 h, k_p ∈ {0,1,…}. For Memmingen primary case: only j_1→…→j_15 path has k_p=1; others k_p=0. |
| `eq:delayed_balance` | Q_delivered_t = Q_{t−k_p} − Q^loss_{t−k_p} | `network/delay.py::apply_delay` | Initial condition for t < k_p: warm-start from steady-state. Check first k_p hours don't violate balance. |

> **Important catch:** the L2 config has `transport_delay: true` although L2 uses **single-segment "star" pipes**. For most L2 pipes, length 100–240 m at v_nom ~ 1 m/s gives τ ~ 2–4 min → k_p = 0. So the delay flag is effectively no-op. Document this in `EQUATION_AUDIT.md`.

---

## Section 3.4 — Quadratic Reference (L3^NL MIQCP)

| Eq | Equation | Source | Check |
|---|---|---|---|
| `eq:darcy_quad` | Δp = R·Q² | `physics/pressure.py::darcy_quadratic` | Convex quadratic (since Q ≥ 0 in tree). Gurobi accepts without `NonConvex`. |
| `eq:pump_power_quad` | P_pump ∝ Q³ | `physics/pump.py::pump_quadratic` | Cubic decomposed via auxiliary W = Q² (eq:aux_quad) and bilinear Q·W (eq:pump_bilinear). Verify W = Q² in solution (within tolerance). |
| `eq:aux_quad` / `eq:pump_bilinear` | Cubic decomposition | same | Solver tolerance: Gurobi `FeasibilityTol=1e-6`. |
| `eq:temp_prop_quad` | Native bilinear propagation | `physics/temperature.py::propagate_quad` | T_out lies between T_ground and T_in at every hour. |
| `eq:bilinear_temp` | Θ = T·φ as bilinear | same | Check `model.NumQConstrs > 0` and one of them is the Θ definition. |
| `eq:loss_ext_quad` | Loss = ṁ·c_p·(T_in − T_out) | same | Trivial after Θ. |

> **Catch (paper claim):** §3.4 says φ remains PWL even in L3^NL. That means L3^NL is **not** a true quadratic reference for the temperature-decay nonlinearity — only for the pressure drop and the T·φ mixing. Document this clearly in §6.3 of the paper (it currently undersells this caveat). The "ground truth" framing should be softened to "highest-fidelity tractable reference within MIQCP".

> **Solver flag:** For Eq. 32 (Q·W), `NonConvex=2` is mandatory. Verify in the Gurobi log that spatial branching kicks in.

---

## Cross-cutting checks

### CC1 — Controlled-matching identities (Tab. `tab:matching` of paper)
For the primary case, verify *programmatically*:

```python
assert sum(U*L for p in pipes_L2) == pytest.approx(sum(U*L for p in pipes_L3), rel=1e-3)
assert demand_L1.sum() == demand_L2.sum() == demand_L3.sum()  # per hour
assert COP_L1 == COP_L2 == COP_L3  # time series equality
assert lambda_buy_L1 == lambda_buy_L2 == lambda_buy_L3
```
**This is non-negotiable.** If `Σ U·L` differs, the L2→L3 comparison is confounded.

### CC2 — Solver-determinism replay
Re-run L3 with `Seed=1` then `Seed=2`. Cost difference < MIPGap. If not, there's a degenerate optimum and §5 numbers are seed-dependent — flag in paper.

### CC3 — L3^NL ↔ L3 reduction test
Disable extended physics in L3^NL (set `pressure_drop=false`, `transport_delay=false`, `temp_propagation=false`). The MIQCP should now be a pure MILP and the optimum must equal L3 within 0.01 %. **This is the cleanest check that the MIQCP solver path is implementing the same balance equations as the MILP path.**

### CC4 — PWL convergence
Run L3⁺ with K = 3, 5, 7, 10. Cost should converge monotonically toward L3^NL value. The K=5 vs K=7 cost difference < 0.1 % validates the choice of K=5 in the paper.

### CC5 — Currency / units
- All cost columns in EUR (`eur`).
- All energy in MWh.
- All power in MW.
- All temperatures °C in I/O, K internally for ratios (Carnot).
- All times in hours, never minutes.
- Pressure in Pa internally, bar in display only.

Add a unit-pint test that asserts dimension consistency on every objective term.

### CC6 — CO₂ accounting
The paper uses a single CO₂ price for both grid and fuel. Verify there's no **double counting** of grid emissions when the user buys electricity that includes upstream gas (no — grid EF is ENTSO-E lifecycle, treated separately). Document in audit.

---

## Audit report template

`output/paper_runs/EQUATION_AUDIT.md`:

```markdown
# Equation Audit — <date>

| Eq | Status | File:line | Notes |
|---|---|---|---|
| eq:objective | ✅ | objective.py:42 | – |
| eq:darcy | ⚠️ | physics/pressure.py:88 | Uses fixed f_D from nominal Re; paper says Colebrook-White at nominal Re — equivalent in steady state, document. |
| eq:temp_prop_lin | ❌ | physics/temperature.py:120 | Uses McCormick instead of Taylor; paper Eq. 22 needs to be rewritten or code switched. **OPEN.** |
| ... | ... | ... | ... |
```

Generate this table automatically by `tools/run_eq_audit.py`.
