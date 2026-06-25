# Claude Code Task Brief — DH Network Modeling Fidelity Study

> **Project goal.** Produce a complete results package for a paper comparing five DH-modeling fidelity levels (L1, L2, L3, L3⁺, L3^NL) on the Memmingen industrial network, in a way that fills every `\placeholder{…}` in `Paper_draft.tex` and provides every figure / table the paper references. **Solver for all final runs: Gurobi.**
>
> **Working environment.** PowerShell 7 on Windows. Python ≥ 3.11, Gurobi ≥ 11, Pyomo. All paths are repo-relative unless absolute.
>
> **Read this file fully before editing anything.** Then implement section by section. Treat every `[CHECK]` as a hard gate: do not move on until it passes.

---

## 0  Repo Map (expected)

```
repo/
├── Memmingen_L1.yaml
├── Memmingen_L2.yaml
├── Memmingen_L3.yaml          # currently mis-labelled — will become L3-noPhys debug variant
├── Memmingen_L3_MILP.yaml      # this is the "real" L3 (basic physics) per paper
├── Memmingen_L3_MIQP.yaml      # L3^NL
├── Paper_draft.tex
├── data/2025_04_14_Import_Data_Memmingen.xlsx
├── src/                        # framework code
└── output/paper_runs/          # NEW — all paper artefacts go here
```

---

## 1  Pre-Run Config Harmonization  (DO THIS FIRST)

These bugs invalidate every comparison until fixed. Apply them in **separate commits** so reviewers can audit.

### 1.1  Hard bugs

| # | File | Issue | Action |
|---|------|-------|--------|
| B1 | `Memmingen_L3_MIQP.yaml` | Two `assets:` blocks — second silently overrides first, so CHP+HP+TES disappear and only a 200 MW gas boiler remains. | Delete the second `assets:` block (lines ~342–362). Keep CHP+HP+TES. |
| B2 | `Memmingen_L3_MIQP.yaml` | `ef_kg_per_mwh_fuel: 200.0` in the gas fuel block (others use 500). | Change to **200** **everywhere** — 200 kg CO₂/MWh_fuel is the physically correct natural-gas value (≈ 0.20 t/MWh_HHV). All five configs must agree. |
| B3 | `Memmingen_L2.yaml` | Demand fractions sum to 1.17 (over-provisioning by 17 %). | Renormalise to fractions of consumer counts: 11/27, 7/27, 2/27, 2/27, 6/27, 2/27, 1/27 → 0.4074, 0.2593, 0.0741, 0.0741, 0.2222, 0.0741, 0.0370 (Σ = 1.0000). Also fix the comment `(11 consumers)` → `(7 consumers)` for region 1. |
| B4 | `Memmingen_L3.yaml` | `heat_loss: false`, `pressure_drop: false`, `transport_delay: false` — but paper defines L3 = "detailed MILP with steady-state losses". | **Rename the file to `Memmingen_L3_NoPhys.yaml`** (debug-only) and treat `Memmingen_L3_MILP.yaml` as the canonical L3 in all paper runs. Update the run table accordingly. |
| B5 | `Memmingen_L3_MIQP.yaml` | Grid limit 2000 MW vs 5000 MW elsewhere. | Set to 5000 MW everywhere. |
| B6 | All configs | Solver inconsistency (HiGHS vs Gurobi). | Set `run.solver: gurobi` in **all five** configs. Migrate `solver_options:` to the Gurobi-native names (`MIPGap`, `TimeLimit`, `Threads`, `OutputFlag`, `LogToConsole`, `LogFile`). |
| B7 | All configs | `pipe_roughness_mm: 0.05` vs paper 0.5 mm. | Decide: aged steel network → use **0.5 mm** in all configs and update `pump_efficiency: 0.75`. New steel → keep 0.05 mm and update paper. **Default decision: 0.5 mm + 0.75 pump efficiency** (matches "industrial network in operation"). |
| B8 | Time horizon | All configs: 2025-01-01 to 2025-01-31 23:00 (744 h). Paper claims "annual". | Change to `start: "2025-01-01 00:00", end: "2025-12-31 23:00"` for paper-final runs. Keep a `_short` variant of each YAML for development. |

### 1.2  Missing physics: electrode boiler

The paper (§3.2.4 + abstract) and the user's research scope require **electrode boilers**. None of the configs have one. Add to every config (capacity to be confirmed by user — placeholder 20 MW, η=0.99):

```yaml
assets:
  ...
  ek_main:
    type: power_to_heat   # or whatever the framework calls electrode/resistance
    capacity_mw: 20.0
    min_load: 0.0
    thermal_efficiency: 0.99
```

Attach to node `j_1` together with CHP / HP / TES.

> **[USER INPUT NEEDED]** Electrode boiler capacity, min-load, location. If unavailable: leave commented and run without; document in the "Limitations" subsection of the discussion.

### 1.3  HP capacity sanity check

`hp_main.capacity_mw: 100.0` while peak demand ≈ 76 MW. A 100 MW HP at a 76 MW peak network is unusual — verify with the user whether this should be **10 MW** (typo) or actually 100 MW (e.g., shared with grid services). **Do not silently change.** Print a warning and ask the user once.

### 1.4  Insulation parameters

The pipe definitions only carry `length_m` and `diameter_mm`. The paper's loss model needs U-value per pipe. Two options:

- (a) extend each pipe with `U_value_W_mK: 0.28` (and 0.30 for return) — preferred, because EN 253 U depends on DN.
- (b) use a DN→U lookup table inside the framework.

Pick (a), default `U = 0.28` W/(m·K) for DN ≤ 200, `U = 0.32` for DN ≥ 250 (rough EN 253 averages). Document the choice in `output/paper_runs/00_config_resolution.md`.

### 1.5  CO₂ price

All configs: 1000 €/t. This is policy-scenario, not market. Keep as primary case but add a sensitivity at 100 €/t (current EU-ETS market) and 500 €/t (mid-policy). See §4.

### 1.6  Validation gate
[CHECK V1] Re-run a 168 h horizon for L1 + L3_MILP + L3_MIQP after applying §1. Energy balance must close to < 0.1 % per hour. Total cost L1 ≤ L3_MILP (no losses → cheaper). Total cost L3_MIQP within ±2 % of L3_MILP_extended for the same physics.

---

## 2  Required Runs

After §1, generate exactly these runs. Output directory: `output/paper_runs/<run_id>/`.

| run_id | Config | Solver | Horizon | Purpose |
|--------|--------|--------|---------|---------|
| `L1` | `Memmingen_L1.yaml` | Gurobi | 8760 h | Topology comparison (RQ1) |
| `L2` | `Memmingen_L2.yaml` | Gurobi | 8760 h | Topology comparison (RQ1) |
| `L3` | `Memmingen_L3_MILP.yaml` (basic physics only — disable `pressure_drop` & `transport_delay`) | Gurobi | 8760 h | Topology + physics baseline (RQ1, RQ2) |
| `L3plus` | `Memmingen_L3_MILP.yaml` (full extended physics: pressure_drop=true, transport_delay=true, temperature_propagation=true) | Gurobi | 8760 h | Physics fidelity (RQ2) |
| `L3NL` | `Memmingen_L3_MIQP.yaml` | Gurobi (`NonConvex=2`) | 8760 h | Linearization error (RQ3) |
| `L1_sens_*`, `L2_sens_*`, … | per-config sensitivities | Gurobi | 8760 h | §4 sensitivity table |
| `synth_<id>` | 36 synthetic YAMLs (§5) | Gurobi | 8760 h | Generalisability (RQ4) |

> **Important:** "L3" in the paper *intentionally* runs the L3_MILP config but with extended physics flags off — this guarantees identical topology between L3 and L3⁺ and is the controlled-comparison protocol. Implement a CLI flag `--physics basic|extended` that toggles `pressure_drop`, `transport_delay`, and the temperature-propagation block at runtime, so the **same YAML** drives both runs.

> **MIQP convergence safety net:** for `L3NL`, `MIPGap=0.005`, `TimeLimit=86400`, `NumericFocus=3`, `Heuristics=0.2`. If gap > 1 % after time limit, log final gap, persist the incumbent, continue. Do not crash.

[CHECK R1] Each run writes `solution.json` with `status`, `mip_gap`, `solve_time_s`, `objective`, `vars`. Status must be `optimal` or (for L3NL only) `time_limit` with `mip_gap < 0.01`.

---

## 3  Required Output Artefacts (per run)

All under `output/paper_runs/<run_id>/`. **CSV columns are the contract**, do not deviate.

### 3.1  `meta.json`
- run_id, config_path, git_sha, gurobi_version, solve_time_s, mip_gap, objective, num_vars, num_bin, num_constr, num_quad_constr, model_class (MILP/MIQCP), wall_clock, peak_RAM_GB.

### 3.2  `economics.csv`  (single-row KPI table)
Columns: `cost_total_eur, cost_energy_buy_eur, revenue_sell_eur, cost_fuel_eur, cost_co2_eur, cost_dump_eur, cost_demand_charge_eur, cost_pump_eur, energy_buy_MWh, energy_sell_MWh, gas_consumption_MWh, co2_total_t, co2_grid_t, co2_fuel_t, peak_import_MW, peak_export_MW, lcoh_eur_per_MWh_th, share_HP_pct, share_CHP_pct, share_EK_pct`.

### 3.3  `dispatch_hourly.csv`  (T rows × ~25 cols)
`timestamp, Q_demand_total_MW, Q_chp_MW, P_chp_el_MW, F_chp_gas_MW, Q_hp_total_MW, Q_hp_wrg_MW, Q_hp_def_MW, P_hp_el_MW, COP_hp_wrg, Q_ek_MW, P_ek_el_MW, Q_storage_charge_MW, Q_storage_discharge_MW, SOC_MWh, P_buy_MW, P_sell_MW, lambda_buy_eur_MWh, lambda_sell_eur_MWh, ef_grid_kg_MWh, P_pump_MW, T_supply_C, T_return_C, Q_loss_total_MW, Q_dump_MW`.

### 3.4  `pipes.csv`  (one row per pipe — static)
`pipe_id, from, to, length_m, diameter_mm, U_value_W_mK, R_resistance, m_dot_max_kg_s, v_max_m_s, dp_max_Pa, transport_delay_min, k_p_steps, annual_loss_MWh, annual_loss_share_pct, peak_velocity_m_s, peak_dp_bar, annual_pump_energy_MWh`.

### 3.5  `pipe_state_hourly.parquet`  (long format, T·P rows)
`timestamp, pipe_id, Q_pipe_MW, m_dot_kg_s, dp_Pa, T_in_C, T_out_C, P_pump_pipe_MW, Q_loss_pipe_MW`.
Parquet because CSV gets huge for 14 pipes × 8760 h.

### 3.6  `linearization_diagnostics.csv`  (L3⁺ and L3^NL only)
For each pipe: `pipe_id, K_breakpoints, dp_PWL_max_err_Pa, dp_PWL_RMSE_Pa, phi_PWL_max_err, taylor_residual_K`.

### 3.7  `validation.json`  (L3 only)
Comparison against measured operational data:
`gas_consumption_meas_MWh, gas_consumption_model_MWh, MAPE_gas, elec_buy_meas, elec_buy_model, MAPE_elec, chp_hours_meas, chp_hours_model, MAPE_chp_hours, hp_hours_meas, hp_hours_model, MAPE_hp_hours, peak_import_meas_MW, peak_import_model_MW, error_peak_pct`.
> **[USER INPUT NEEDED]** Path to the measured-data file. Until provided, leave `validation.json` with `status: "no_measured_data"`.

[CHECK O1] Every run produces all of 3.1–3.6. Schemas validated against `output/paper_runs/_schemas/*.json`.

---

## 4  Sensitivity Cases  (Table `tab:gap_stability` in paper)

Run each of L1, L2, L3, L3⁺ for these scenarios. **Only one parameter changes per scenario, all others at baseline:**

| Scenario | Change |
|---|---|
| `baseline` | as-is |
| `gas_high` | gas price ×1.20 |
| `elec_low` | spot price ×0.80 |
| `co2_high` | CO₂ price → 200 €/t (above ETS) **AND** an additional `co2_market` run at 100 €/t |
| `cold` | T_ground +3 K, demand ×1.05 |
| `warm` | T_ground −3 K, demand ×0.95 |
| `cop_low` | Carnot efficiency 0.6 → 0.54 (−10 %) |

**Output:** `output/paper_runs/sensitivity/<level>_<scenario>/economics.csv` plus a single roll-up `output/paper_runs/sensitivity/summary.csv` with one row per (level × scenario).

---

## 5  Synthetic Generalizability Network  (RQ4)

Generate 36 YAMLs in `synth_configs/` from a single template. Parameter grid (3⁴ = 81, retain feasible 36):

```python
LENGTHS_KM = [1.0, 5.0, 15.0]      # total trunk length
HI_LEVELS  = [0.1, 0.4, 0.8]       # demand heterogeneity index
N_NODES    = [5, 15, 30]
STORAGE_H  = [2, 6, 12]            # storage capacity in hours of peak demand
```

Topology rule: balanced binary tree of depth `ceil(log2(N_NODES))`, total trunk length = `LENGTHS_KM`, demand-HI by Gini-style allocation across leaves (HI=0 uniform → HI=1 single leaf). Pipe diameters dimensioned to `v_max=2.5 m/s` at peak.

Demand timeseries: scale Memmingen total-demand profile by HI distribution and by N_NODES.

Run each synthetic config at L1, L2, L3, L3⁺, L3^NL → 36 × 5 = **180 runs**. For L3^NL on 30-node networks, allow `MIPGap=0.005`, fall back to 0.01 if needed.

[CHECK G1] Generate `synth_configs/_README.md` with the parameter table and the feasibility-filter log (which 45 of 81 were dropped and why).

---

## 6  Required Figures

All figures in `output/paper_runs/figures/`, both `.pdf` (for paper) and `.png` (for inspection). Use `matplotlib` with `serif` font, 300 DPI, no chartjunk.

| ID | Filename | Content |
|----|----------|---------|
| F1 | `fig_comparison_design.pdf` | 2D layout of L1→L2→L3→L3⁺→L3^NL with 3 controlled comparison arrows. Schematic, not data-driven. |
| F2 | `fig_topology.pdf` | Memmingen 15-node tree from `Lageplan_Memmingen_drawio.pdf` + computed transport delays per segment. Use `networkx` + a fixed coordinate file. |
| F3 | `fig_cost_topology.pdf` | Stacked bar: cost decomposition (fuel / electricity / CO₂ / demand-charge / pump) for L1, L2, L3. |
| F4 | `fig_cost_extended.pdf` | Same stack for L3 vs L3⁺ vs L3^NL. |
| F5 | `fig_cost_waterfall.pdf` | L3→L3⁺ waterfall: +pumping, −loss-reduction, ±dispatch-shift, =net Δ. |
| F6 | `fig_pump_pwl_vs_quad.pdf` | Hourly scatter P_pump (PWL=L3⁺) vs P_pump (quad=L3^NL), colour by flow level. R² annotated. |
| F7 | `fig_storage_winterweek.pdf` | Mean SOC profile over a representative cold week (Jan, Mon–Sun) for all 5 levels, overlay. Shaded area = ±1 σ. |
| F8 | `fig_storage_charge_hour.pdf` | Histogram of optimal charge-hour-of-day per level (winter only). |
| F9 | `fig_dispatch_heatmap.pdf` | Heatmap (hour-of-year × component) for L3⁺: HP, CHP, EK, storage charge/discharge. |
| F10 | `fig_synth_topology_gap.pdf` | L1→L2 gap [%] vs total pipe length, coloured by HI. 36 points. |
| F11 | `fig_synth_physics_gap.pdf` | L3→L3⁺ gap [%] vs cumulative transport delay τ_max, coloured by pipe length. |
| F12 | `fig_synth_lin_error.pdf` | L3⁺→L3^NL gap [%] vs all 4 axes (4 small panels). Should be flat. |
| F13 | `fig_tornado_sensitivity.pdf` | Tornado plot for L3 cost across all scenarios in §4. |
| F14 | `fig_solve_time.pdf` | Bar chart, log scale, solve time per level for primary case + 30-node synthetic. |

[CHECK F1] Every figure has its data CSV next to it (e.g. `fig_cost_topology.csv`) so reviewers can reproduce.

---

## 7  Required LaTeX Tables (auto-generated)

Output to `output/paper_runs/tables/*.tex`. Each as a standalone `\begin{tabular}` snippet that the paper `\input{}`s.

| Filename | Replaces in paper |
|----------|--------------------|
| `tab_validation.tex` | `tab:validation` (§5.1) |
| `tab_cost_topology.tex` | `tab:cost_topology` (§5.x) |
| `tab_cost_extended.tex` | `tab:cost_extended` (§5.3) |
| `tab_linearization.tex` | `tab:linearization` (§5.4) |
| `tab_storage.tex` | `tab:storage` (§5.5) |
| `tab_computation.tex` | `tab:losses_computation` (§5.6) |
| `tab_effect_hierarchy.tex` | `tab:effect_hierarchy` (§5.7) |
| `tab_gap_stability.tex` | `tab:gap_stability` (§5.8) |
| `tab_transport_delays.tex` | `tab:transport_delays` (§4.1.2) |
| `tab_network_params.tex` | `tab:network_params` (§4.1.4) |
| `tab_pwl_breakdown.tex` | new — per-pipe PWL error |

Use a single helper `tools/tablegen.py` so the format is identical (booktabs, `\toprule…\bottomrule`, `siunitx` numbers).

---

## 8  Placeholder Replacement Map

`Paper_draft.tex` contains many `\placeholder{…}` markers. Build `tools/fill_paper.py` that:

1. Reads `output/paper_runs/_placeholders.json` (a flat key→value dict).
2. Walks `Paper_draft.tex`, replaces every `\placeholder{KEY}` with `\textcolor{black}{VALUE}` (keep the macro for traceability).
3. Writes `Paper_filled.tex` (does **not** overwrite the source).

The placeholder keys in the paper currently use natural-language descriptions, not stable IDs. Step 1 of `fill_paper.py` is therefore: **scan paper, list every placeholder, generate stable IDs, and write a `_placeholders_template.json`**. The user fills the IDs the first time, then the script populates values from `economics.csv` etc.

[CHECK P1] After `fill_paper.py`, no `\placeholder{` remains in `Paper_filled.tex`. Compile must succeed (`pdflatex` clean run, no missing references).

---

## 9  Order of Operations

```text
1. Apply §1 fixes  →  commit "config: harmonise (B1–B8)"
2. Run [CHECK V1]   →  commit "test: validate configs"
3. Implement §3 output schema, run L1/L2/L3 only
4. Implement §6 figures F3, F7 from L1/L2/L3
5. Run L3plus, L3NL  →  produces F4, F5, F6, F8
6. Run §4 sensitivities → tornado F13
7. Generate §5 synthetic configs, run all
8. Run figures F10–F12, table tab_effect_hierarchy
9. Generate all tables (§7)
10. Run fill_paper.py → Paper_filled.tex → pdflatex
11. Final review: open Paper_filled.pdf, look for remaining placeholders
```

---

## 10  Things to Ask the User Before Running

Print the following questions on first invocation. **Block** until answered (write answers to `output/paper_runs/00_user_answers.md`):

1. **HP capacity** — 100 MW or 10 MW? (See §1.3.)
2. **Electrode boiler** — capacity, electrical efficiency, location?
3. **Validation data path** — CSV/XLSX with monthly gas, electricity, CHP/HP hours?
4. **Pipe roughness** — confirm 0.5 mm (aged) or 0.05 mm (new)?
5. **CO₂ price** — keep 1000 €/t as primary, or use 100 €/t?
6. **Time horizon for paper-final runs** — confirm 8760 h (full year)?
7. **Excluded heat curtailment** — `dump_cost_eur_per_mwh_th: 10` is very low; raise to 1000? Or keep low + bound `Q_dump = 0` hard?
8. **L3⁺ temperature propagation linearization** — Taylor (Eq. 22 of paper) or McCormick? Currently ambiguous in source.
9. **Citation key style** — does `\bibliographystyle{elsarticle-num}` match the journal target you finally choose? Applied Energy uses author-year, ECM uses numbers — pick journal first.

---

## 11  Definition-of-Done Checklist

- [ ] §1 hard bugs resolved, configs harmonised, `git diff` reviewed
- [ ] All 5 primary runs produce §3 artefacts with passing schema validation
- [ ] All sensitivity runs (§4) complete, summary CSV present
- [ ] Synthetic generation reproducible from `tools/gen_synth.py --seed 42`
- [ ] All 14 figures in `figures/` as both PDF and PNG
- [ ] All 11 tables in `tables/` compile in isolation (`pdflatex -draftmode`)
- [ ] `fill_paper.py` writes `Paper_filled.tex` with zero remaining `\placeholder{` markers
- [ ] `Paper_filled.pdf` builds clean
- [ ] `output/paper_runs/REPORT.md` (auto-generated) summarises every key number against the paper draft
