# P7 — Analysis: bias, regret, decomposition, prediction

**Depends on:** P4, P5, P6, P11 · **Blocks:** P8, P9
**Output:** `results/v2/analysis/*.csv`, `revision/audit/P7_findings.md`

Every number in the manuscript traces to a row in one of these CSVs.

## CSVs

### `bias_regret.csv`
One row per (case, scenario, level):
`case, scenario, level_code, z_model, z_eval, bias_abs, bias_pct, regret_abs,
regret_pct, co2_bias, co2_regret, n_violation_steps, violation_energy_mwh,
worst_violation`

### `decomposition.csv`
Per case and scenario, for **cost and CO2**:
`total, loss_main, topo_main, interaction, aggregation, hydraulics,
drift_T0P1_frozen`, absolute and % of `z_eval(T2P1)`.
**Assert `total = loss_main + topo_main + interaction` to machine precision; fail if not.**

### `linearisation_bounds.csv`
Per MIQCP comparison and window:
`comparison, window, z_A, z_B, bound_A, bound_B, gap_A, gap_B, point_estimate,
rigorous_bound, cross_feasible, defensible_statement`

`defensible_statement` is generated, not written by hand:
- `rigorous_bound > 0` → "the effect increases cost by at least X %"
- `rigorous_bound ≤ 0 < point_estimate` → "no improvement can be demonstrated at
  the attained tolerance; point estimate X %, solver gap Y %"
- both ≤ 0 → "the effect does not increase cost"

This mechanism prevents v1's error of asserting 0.35 % under a 1.99 % gap.

### `decision_divergence.csv`
Regret is a cost. These are the *decisions*:
`hours_hp_state_differs_pct, eboiler_energy_share_delta, peak_grid_import_delta_mw,
tes_cycle_count_delta, tes_soc_timing_shift_h, merit_order_inversions,
producer_share_delta_by_node`

The last one matters most for Stadtbach: does the simplified model source heat
from the wrong producer? v1 asserted storage dispatch was "indistinguishable
across levels" — quantify rather than assert, and re-check after the pump fix.

### `synthetic_anova.csv`, `synthetic_regression.csv`
From P5. ANOVA (η² per factor and interaction) **and** OLS with CIs, fitted
separately for `loss_main`, `topo_main` and `regret`.

### `prediction_oos.csv`
The a-priori estimator fitted on Memmingen + synthetic, predicting Stadtbach
**without refitting**:
`predictor_form, fitted_on, predicted_target, predicted_value, actual_value,
error_pct, within_ci`

### `robustness.csv`, `computational.csv`, `changes_vs_v1.csv`

---

## Findings report — answer each explicitly, with numbers

`revision/audit/P7_findings.md`. State where an answer contradicts v1.

1. **What fraction of total bias is `loss_main`?** If it is the large majority,
   "topology dominates" is unsupported and the title changes.
2. **How large is `interaction`?** This is the quantitative content of the claim
   that resolution is what makes loss endogenous.
3. **Does `topo_main` differ between Memmingen (central generation) and Stadtbach
   (distributed)?** The moderator result. If Stadtbach also shows ≈0, that is a
   *more* surprising finding — write that sentence too.
4. **How does regret compare to bias, per level and per case?** The headline of
   the reframed paper.
5. **Are there physical violations** in schedules from low-fidelity levels? How
   many hours, how much energy?
6. **Does the frozen `T0P1` adder drift** across scenarios, across pipe length,
   and between networks? The transferability evidence.
7. **New `T2P2 − T2P1`** after the hydraulic fix, versus +0.11 %. Does the
   abstract's "<1 %" still hold?
8. **Isolated linearisation** (`T2P3−T2P2`) and **isolated delay** (`T2P4−T2P3`):
   defensible against their bounds?
9. **Does the decomposition hold in Case A** (the validated configuration) and
   change in Case C (electrified)?
10. **Does the a-priori estimator predict Stadtbach out-of-sample?**
11. **Do the three `T0P1` calibration sources (a/b/c) differ materially?** If the
    measurement-calibrated version behaves differently from the oracle versions,
    that is worth a sentence — it is what a practitioner would actually have.

## Rules

- No number in the paper that is not in these CSVs.
- Round only at presentation time.
- Record every v1 number that changed in `changes_vs_v1.csv`; the response letter
  depends on it.
