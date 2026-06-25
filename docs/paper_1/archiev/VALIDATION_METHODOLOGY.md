# Validation Methodology — Memmingen District Heating Model
## Two-Stage Boundary-Condition-Matching Approach

**Document purpose:** Captures all design decisions made in `tools/validation_runner.py`
that affect what claims can be made in the paper about model validity.
Update this file whenever thresholds, KPIs, or the simulation strategy change.

---

## 1. Fundamental constraint: split measurement period

The historical monitoring data (supply/return temperatures, flow rates per substation)
were recorded **before** the heat pump (HP) and electrode boiler (eboiler) were installed.
This means:

- Network physics (pipes, heat losses, hydraulics) **can** be validated directly.
- HP, eboiler, and TES dispatch **cannot** be validated against measurement data —
  only physics-based plausibility checks are possible (Stage 2).

This is consistent with the indirect validation approach in Kus et al. (2025).

---

## 1b. Honest assessment of current validation strength (MILP run)

This section documents the peer-review-level critique of the current validation output
so the paper can be framed honestly.

| Issue | Observed value | Implication for paper claims |
|-------|---------------|------------------------------|
| KPIs evaluable with MILP | 1 of 5 | Only annual energy balance is a hard pass/fail test |
| R² of T_supply vs. outdoor temp | 0.13 | Low dynamic range — annual match is a necessary but weak test |
| Hourly Q_demand MAPE | ~29% | Structurally biased (TES dispatch mismatch) — not citable |
| TES SOC < 5%: share of year | ~91% | TES near-empty most of year — economic value questionable |
| HP / Eboiler dispatched | Never | COP and efficiency completely unverified in this run |
| U-value calibration | None (ratio=1.00) | Nominal values — calibration requires NLP far-end T data |

**Paper framing consequence:** The MILP run alone cannot support a claim of
"validated thermal-hydraulic model." It supports "annual energy balance consistent
with measurements." Full validation requires the MIQP run (see §10 below).

---

## 2. Stage 1 strategy: Boundary-Condition-Matching (BCM)

### What it does

Instead of running a full dispatch-optimisation and comparing outputs, the runner:

1. Reads the measured supply temperature at the source node (j_1) from the monitoring data.
2. Computes its median over the validation period → **T_supply_BC** (e.g. 86.5 °C).
3. Injects T_supply_BC as a fixed boundary condition in the model config
   (`network.supply_temp_c`), bypassing the heating curve.
4. Runs the L3-MILP model in `PF_ONLY` mode (no investment decisions, dispatch only).
5. Compares simulated outputs against measured data.

### Why BCM and not free-running simulation?

A free-running simulation would conflate two error sources:
- Errors in the **dispatch optimiser** (asset scheduling, price signals).
- Errors in the **network physics model** (heat losses, hydraulics).

BCM isolates the network physics by fixing the supply temperature to the measured value,
so any remaining error is attributable to the pipe model alone.

### Known limitation: heating curve interaction

The base config `Memmingen_L3_MILP.yaml` defines:

```yaml
heating_curve:
  enabled: true
  T_supply_min_c: 50.0   # °C at outdoor +15 °C
return_temp_c: 55.0
```

`T_supply_min_c = 50 °C < T_return_c = 55 °C` is physically inconsistent.
When `heating_curve.enabled = true`, the MILP constraint
`Q_delivered = m_dot * cp * (T_supply - T_return)` requires a negative heat delivery
at low-load hours → presolve infeasibility in ~3 seconds.

**Fix applied in `validation_runner.py`:** The BCM overrides inject
`heating_curve: {enabled: false}` alongside the fixed `supply_temp_c`, so the model
uses a constant nominal temperature rather than the curve.

```python
legacy_overrides["network"] = {
    "supply_temp_c": round(t_sup_bc, 1),
    "heating_curve": {"enabled": False},   # prevents T_min < T_return infeasibility
    "physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False},
}
```

---

## 3. MILP model limitations for hydraulic validation

The L3-MILP model uses **linearised** (piecewise-linear, PWL) pipe physics.
This has consequences that determine which KPIs are meaningful:

| KPI | MILP behaviour | Meaningful? |
|-----|---------------|-------------|
| Annual energy balance | TES dispatch differs from measured, but annual totals match | **Yes** (1–2% error) |
| Hourly Q_demand MAPE | Gen-balance demand = constant TES discharge ≠ variable measured demand | **No** — structural mismatch |
| T_supply at far end (j_15) | `T_supply_in` is a fixed Pyomo Param → `T_in = T_out = T_supply_BC` everywhere | **No** — no propagation |
| T_return at source | Fixed at nominal (55 °C) in MILP → constant, std ≈ 0 | **No** — skipped automatically |
| Flow at source | Derived from gen-balance; same TES mismatch as Q_demand | **No** — not in THRESHOLDS |

For temperature propagation and hourly flow validation the NLP (L3-MIQP / Gurobi NonConvex=2)
model is required. The MILP is suitable only for annual-level checks.

---

## 4. KPI thresholds (current state)

Defined in `THRESHOLDS` dict in `tools/validation_runner.py`.

### Active thresholds (pass/fail)

| KPI key | Threshold | Rationale |
|---------|-----------|-----------|
| `Q_annual_error_pct` | ≤ 2.0 % | Annual energy balance; MILP achieves ~1.2 % |
| `energy_balance_closure_pct` | ≤ 2.0 % | Instantaneous conservation check |
| `T_supply_farend_MAE_C` | ≤ 1.5 °C | Heat loss validation j_1 → j_15; NLP only |
| `T_return_source_MAE_C` | ≤ 1.0 °C | Return mixing; NLP only |
| `T_return_source_RMSE_C` | ≤ 1.5 °C | NLP only |
| `T_supply_drop_MAE_C` | ≤ 1.0 °C | ΔT trunk; NLP only |

### Removed thresholds (computed and reported, not pass/fail)

| KPI key | Why removed |
|---------|-------------|
| `flow_source_MAPE_pct` | MILP TES dispatch pattern diverges from measured operation; hourly flow derived from gen-balance is structurally inaccurate |
| `Q_demand_total_MAPE_pct` | Same root cause: biomass runs as baseload, TES discharges at a near-constant rate → gen-balance demand is constant in discharge hours while measured demand varies hourly |

These KPIs are still computed and printed to the console and written to `kpis.json`.
They are informational only and should **not** be cited as pass/fail criteria in the paper
for MILP runs.

---

## 5. Q_demand reconstruction for MILP results

In `PF_ONLY` MILP mode, demand enters as a constraint (`V_X_demand_MWth` columns),
not as a decision variable → `Q_demand_total_MW` in the output CSV is zero.

The function `_fix_sim_legacy()` reconstructs it from the generation balance:

```
Q_demand_reconstructed = Q_gen + Q_TES_discharge - Q_TES_charge - Q_loss - Q_dump
```

where `Q_gen = Σ(Q_CHP, Q_gasboiler, Q_biomass, Q_HP, Q_eboiler)`.

This gives the correct **annual** total (error ~1.2 %) but an inaccurate hourly
profile due to TES buffering. See Section 3 above.

---

## 6. T_return handling

MILP sets `T_return` to the nominal value (55 °C) for all timesteps.
`_fix_sim_legacy()` detects this (std < 0.01 °C) and sets a flag
`_T_return_is_nominal = True`.

`compute_stage1_kpis()` then:
- **Skips** the T_return MAE/RMSE KPI (not added to `kpis` dict, not evaluated against threshold).
- **Uses measured ΔT** instead of simulated ΔT when computing the flow KPI
  (avoids a ÷0 error from T_supply - T_return = 0).

---

## 7. Paper framing guidance

### Validation section text (draft)

> Since the heat pump and electrode boiler were installed after the monitoring period,
> direct asset-level validation is not feasible. We adopt a split validation strategy
> consistent with Kus et al. (2025): (1) direct validation of network hydraulics and
> thermal transport against pre-upgrade monitoring data using a boundary-condition-matching
> approach, and (2) indirect validation of asset dispatch through physics-based plausibility
> checks (COP bounds, storage SOC limits, energy balance closure).
>
> For Stage 1, the measured supply temperature at the source (T_supply,BC = 86.5 °C
> annual median) is injected as a fixed boundary condition, isolating pipe-model errors
> from scheduling errors. The MILP-linearised model is evaluated against the annual
> energy balance (error < 2 %) as the primary criterion. Hourly temperature propagation
> and flow validation require the nonlinear (MIQP) model and are reported separately.

### Table 2 caption (KPI table)

> Stage 1 validation results using the boundary-condition-matching approach.
> KPIs marked † require the NLP (MIQP) model; results shown are for L3-MILP
> unless otherwise stated. Threshold sources: Kus et al. (2025), Maldonado et al. (2024).

### What to cite

- **Kus et al. (2025)** — indirect validation approach, T_supply MAE < 1.0 °C target.
- **Maldonado et al. (2024)** — T_return RMSE < 1.0 °C, flow MAPE < 5 % after calibration.

---

## 8. How to run

```bash
# From the repository root:

# Full pipeline (Stage 1 + Stage 2):
python tools/validation_runner.py

# Stage 1 only (faster — network KPIs only):
python tools/validation_runner.py --stage 1

# Stage 2 only (asset plausibility, reads existing L3 results):
python tools/validation_runner.py --stage 2

# Dry run — print plan, load data, skip model solve:
python tools/validation_runner.py --dry-run

# Skip U-value calibration loop:
python tools/validation_runner.py --no-calibrate
```

**Prerequisites before running:**

1. L3-MILP results must exist in `output/paper_runs/L3/` (run `scripts/paper/run_all_levels.py` or the legacy runner first).
2. Legacy run results (pre-upgrade dispatch) can be in `output/paper_runs/legacy/`.
   If missing, the runner falls back to the L3 dispatch automatically.
3. Excel data file: `data/Import_Data_Memmingen_epronet.xlsx` (must contain
   `Waermebedarf_MWth`, `V_X_demand_MWth`, temperature and flow columns).

**Key outputs** written to `output/validation/`:

| File | Content |
|------|---------|
| `kpis.json` | All computed KPIs and thresholds in machine-readable form |
| `validation_report.md` | Auto-generated text for paper insertion |
| `stage1_timeseries_winter.png` | Simulated vs. measured (winter week) |
| `stage1_timeseries_summer.png` | Simulated vs. measured (summer week) |
| `stage1_error_histograms.png` | Error distributions with threshold lines |
| `stage2_TES_SOC.png` | Storage state of charge, full year |
| `stage2_energy_stacked_bar.png` | Monthly dispatch mix (all assets) |
| `validation_summary_table.png` | Pass/fail table for paper |

---

## 9. fill_paper.py integration

`tools/fill_paper.py` reads `\placeholder{KEY}` macros from `Paper_draft_v2.tex`
and fills them from `output/paper_runs/_placeholders.json`.

```bash
# Scan paper for all placeholders → generates _placeholders_template.json:
python tools/fill_paper.py --scan

# Auto-fill from run artefacts (reads output/paper_runs/):
python tools/fill_paper.py --auto

# Produce Paper_filled.tex from _placeholders.json:
python tools/fill_paper.py --fill
```

Validation KPIs relevant to the paper (add these `\placeholder{}` macros to the .tex):

| Placeholder | Value source |
|-------------|-------------|
| `\placeholder{T supply BC median C}` | `bc_info.median_C` from `kpis.json` |
| `\placeholder{Q annual error pct}` | `kpis.Q_annual_error_pct` |
| `\placeholder{energy balance closure pct}` | `kpis.energy_balance_closure_pct` |
| `\placeholder{T supply farend MAE C}` | `kpis.T_supply_farend_MAE_C` (NLP run) |
| `\placeholder{T return source MAE C}` | `kpis.T_return_source_MAE_C` (NLP run) |

---

## 10. Completing the validation: MIQP run

The MILP run (Memmingen_L3_MILP.yaml) is **Step 1 of 2**. To obtain all
temperature and flow KPIs, run the NLP model:

```bash
# 1. Run MIQP (nonlinear, Gurobi NonConvex=2) — takes several hours:
python -m calion configs/memmingen/Memmingen_L3_MIQP.yaml

# 2. Re-run validation with MIQP results in output/paper_runs/L3/:
python tools/validation_runner.py --stage 1
```

Expected improvements after MIQP run:

| KPI | Expected from MIQP |
|-----|--------------------|
| `T_supply_farend_MAE_C` | Should be < 1.5°C if U-values are reasonable |
| `T_return_source_MAE_C` | Should be < 1.0°C after T_return mixing is nonlinear |
| `T_supply_drop_MAE_C` | Requires ΔT from nonlinear propagation |
| U-value calibration | Will iterate ratio and update YAML |

After the MIQP run, if `T_supply_farend_MAE_C` > 1.5°C, re-run with calibrated
U-values: `validation_runner.py` writes the ratio to `kpis.json`; copy those
values into `Memmingen_L3_MIQP.yaml` under each pipe's `u_value_supply_w_per_m_k`.

**Forced-dispatch sensitivity for HP/Eboiler:**
Since HP and Eboiler are never dispatched under current price assumptions,
their COP and efficiency cannot be plausibility-checked. To test:

```yaml
# Add to assets in a sensitivity config:
hp_main:
  min_load: 0.5   # force at least 50% dispatch
  capacity_mw: 5.0
```

Run a short (1-month) window and check that COP stays in [2.5, 5.5] and
Eboiler efficiency in [0.93, 1.02]. This constitutes a necessary-condition
check even without matching measurement data.
