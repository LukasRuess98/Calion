# P11 — Forward evaluator: status + a material finding

Date 2026-08-09. Status: v1 built (`tools/evaluator.py`), runs end-to-end; NOT yet
passing self-consistency. Building it surfaced a finding that affects the paper's
headline numbers, not just the evaluator.

## Finding: ~38% of the L3 objective is non-economic penalty terms

For L3 (`output/paper1_corrected/L3/economics.csv` + `meta.json`):

```
OBJ_value_EUR (= reported "cost", = z used for all v1 bias %) = 225,717
economic components_sum
  = energy_buy − sell + fuel + co2 + dump + demand
  = 85,189 − 30,780 + 58,382 + 26,152 + 0 + 0            = 138,943
Objective_residual_EUR                                    ≈  86,775   (38.4%)
```

Code proof (baseline worktree):
- `constraint_builder.py:478` objective = energy + dump + fuel + co2 + demand + capex
  + activation + tie_break + storage_install + **terminal_value + demand_slack_cost
  + return_anchor_cost**.
- `result_collector.py:1035` `components_sum` **excludes** the last three, and stores
  `Objective_residual_EUR = OBJ_value_EUR − components_sum` (line 1047).

So the residual = `terminal_value + demand_slack_cost + return_anchor_cost`. For a
dispatch run these are: storage terminal-SOC valuation, unmet-demand slack penalty,
and the return-temperature anchoring regularizer. **None is a real economic cost.**

## Why this matters for the revision

1. **The headline bias percentages (L1→L3 = 13.0 %, etc.) are computed on
   `OBJ_value_EUR`, which is ~38 % penalty/regularizer at L3.** If those penalty
   terms differ across levels (they plausibly do — L1 copperplate has no return
   network to anchor, different slack), part of the reported "cost bias" is a
   penalty artifact, not economic cost. **Must re-derive all gaps on
   `components_sum` (real economic cost) and compare to the OBJ-based gaps.** This is
   squarely within R1.2 / R2.1 ("measures the model, not the decision").
2. **Regret must be defined on real economic cost.** The evaluator therefore targets
   `components_sum`, NOT `OBJ_value_EUR`. The P11 self-consistency criterion is
   reformulated: reproduce the economic cost, not the penalty-laden objective.
3. If `demand_slack_cost` is a large share of the residual, some demand is unserved
   in the optimum — a feasibility point a reviewer could raise. Needs quantifying
   per level (the residual breakdown is computed by calion but not exported to the
   run dir — add `terminal_value / demand_slack / return_anchor` to the export).

## Per-level residual + economic-cost gaps (computed from exported economics.csv, no re-run)

| level | OBJ ("cost") | economic cost | residual | resid % |
|---|---|---|---|---|
| L1 | 196,298 | 115,835 | 80,463 | 41.0 |
| L2 | 219,992 | 133,986 | 86,007 | 39.1 |
| L3 | 225,717 | 138,943 | 86,774 | 38.4 |
| L3+ | 226,461 | 140,446 | 86,015 | 38.0 |

| gap | v1 (on OBJ) | **on economic cost** |
|---|---|---|
| L1→L3 | 13.03 % | **16.63 %** |
| L2→L3 | 2.54 % | **3.57 %** |
| L3→L3+ | 0.33 % | **1.08 %** |

**Economic-cost gaps are LARGER** — the ~38–41 % residual inflates the OBJ denominator
and damps the percentages. Good news for the thesis (resolution matters *more*) and for
R2.4 (hydraulics gap triples, 0.33→1.08 %, still small but no longer negligible).
terminal_value is structurally small (single end-of-horizon term), so the residual is
`demand_slack_cost + return_anchor_cost`.

## SECOND finding: energy balance does not close (18–30 %), every level

calion's own `validation.json.energy_balance` reports `closure_pass = 0` at every level:
L1 30.4 %, L2 17.8 %, L3/L3+ 18.1 %. `generation_MWh` (8,588 at L1) < `demand + losses`.
Likely the same class as the L1 phantom-loss artifact: electric-boiler/P2H heat from grid
import is not counted in `generation_MWh` (a reporting gap) — BUT it may also be partly
genuine `demand_slack` (the objective pays a slack penalty rather than serving demand).
**Cannot be disentangled from exported files.** This is reviewer-exposable (R2 recomputes
balances) and must be resolved.

## RESOLVED by reading the code (no re-run): what the residual is and is not

- **Losses ARE in the heat balance.** `constraint_builder.py:363` consumer balance is
  `local_supply + pipe_in == demand − slack + dump + charge`, and `pipe_in` is the
  pipe's *delivered* heat = source input − pipe loss. So the producer must generate
  demand + losses. **The "loss visibility" thesis is structurally sound**, and the
  18–30 % `energy_balance` closure gap is a *reporting* inconsistency in how
  `generation_MWh` vs losses are tallied for validation.json — NOT losses being free.
  (Fix the reporting; it is reviewer-exposable as-is.)
- **The residual is NOT demand-slack.** `network_manager.py:896-898`: slack defaults
  OFF with penalty 1e6; the paper configs don't enable it. If it were active, even a
  few MWh unserved would dwarf the 225k objective. So `demand_slack_cost ≈ 0`.
- **terminal_value is small** (single end-of-horizon storage term).
- **By elimination the ~38–41 % residual is `return_anchor_cost`** — a soft
  return-temperature regularizer (`return_temp_anchor_penalty_terms`, thermal_node).
  My earlier "supply < demand by 17 %" reconstruction was a double-count (Q_gen already
  nets losses/storage); the balance constraint proves demand is served.

**Consequence unchanged and important:** ~38–41 % of the reported objective is a
regularizer, not economic cost, so **report bias/regret on economic cost** (energy −
sell + fuel + co2 + dump + demand). Economic gaps 16.6 / 3.6 / 1.08 % vs v1's 13.0 /
2.5 / 0.33 %. Confirm the return_anchor magnitude with the instrumented re-run below,
but the reporting decision does not depend on it.

Safety: worktree tracked changes captured at
`revision/audit/baseline_worktree_uncommitted.patch` (non-invasive; git untouched).
Note: the worktree also has untracked prior-v2 work (e.g. `synth_configs/*_L1cp.yaml`
copperplate variants, `run_synth_parallel.py`) — assess before building new synth work.

## To CONFIRM the return_anchor magnitude + fix closure reporting (instrumented re-run)

1. Instrument the export (baseline worktree): dump `terminal_value`, `demand_slack_cost`,
   `return_anchor_cost` per level, and fix `generation_MWh` to include electric-boiler/P2H
   heat from grid import.
2. Re-run L1 + L3 (~5–14 min, Gurobi). If `demand_slack` ≈ 0 → residual is the benign
   return-anchor regularizer → report economic gaps cleanly (strengthens the paper). If
   `demand_slack` is large → the v1 comparison has an unserved-demand confound → real fix
   needed (raise capacity / relax the anchor) before any gap is trustworthy.
3. **Blocker:** the baseline worktree is uncommitted/detached — must be stabilized
   (committed to a branch) BEFORE editing+running there, or the reproducing state is at risk.

## EVALUATOR LOCKED DOWN (2026-08-09) — validated + headline result

Redesigned cost model = **economic cost (calion's own economics.csv conventions) +
forward physics deltas** (extra loss the schedule ignored × marginal heat cost, +
recomputed pump electricity). This sidesteps reverse-engineering calion's CHP
self-use CO2 credit / sell valuation, and makes self-consistency structural.

Fixes applied to `tools/evaluator.py`:
- **U-values read from config** (`u_value_supply/return_w_per_m_k`), not the
  unpopulated `pipes.csv` U column (was 0 → loss computed as 0). Now forward loss =
  1,284 MWh vs calion 1,330 (−3.4 %, per-pipe 2–6 %); the native exponential is
  correctly a touch below calion's linear approximation. **physics_pass=True.**
- **Economic cost matches calion exactly** (L3 = 138,943, reproduced to the cent).
  Self-consistency: z_eval − econ = +0.56 % = the pump electricity the model omitted.
- **Copperplate loss attribution**: `models_loss=False` when config `heat_loss:false`
  (L1 has `pipes:{}`), so the copperplate pays for the losses it ignored.

**Headline result (`results/v2/analysis/bias_regret.csv`):**

| level | bias (economic) | regret (forward) |
|---|---|---|
| L1 copperplate | **−16.6 %** | **+23.4 %** |
| L2 | −3.6 % | −3.6 % |
| L3 (ref) | 0 | 0 |
| L3+ | +1.1 % | +1.1 % |

**Bias and regret have OPPOSITE SIGNS for the copperplate** — it looks 16.6 % cheaper
but its loss-ignoring schedule costs 23.4 % more to execute on the real network.
Levels that model losses have regret ≈ bias (executable schedules). This is the
R1.2/R2.1 headline, quantified.

**Correctness fix during double-check (2026-08-09):** the regret was executing each
level's schedule on a network built from THAT level's own config; the copperplate
(pipes:{}) fell back to default U (0.30/0.32) not the real 0.32/0.34, understating
L1 loss (1,115 vs 1,284). Fixed: every schedule now runs on the SAME real T2 network
(built once from the T2 config), only schedule + models_loss vary. L1 regret corrected
23.4 % -> 29.4 % (gas fuel-only basis).

**Regret sensitivity DONE (`results/v2/analysis/regret_sensitivity.csv`,
`tools/regret_sensitivity.py`):** L1 (copperplate) regret vs the two documented
assumptions:

| marginal heat cost | demand-wtd | uniform |
|---|---|---|
| biomass+CO2 ~47 | +26.8 % | +27.0 % |
| gas fuel-only 50 | +29.4 % | +29.7 % |
| **gas+CO2 72 (primary)** | **+49.8 %** | **+50.2 %** |
| EK-ish 90 | +66.2 % | +66.7 % |

Conclusions: (1) **disaggregation rule is immaterial** (<0.3 pp between demand-wtd and
uniform) — regret is not a rule artifact; (2) **sign is invariant** — regret is
strongly positive (+27 % to +66 %) across the whole plausible range while bias is
−16.6 %, so "looks cheaper, costs more" holds under every assumption; only the
magnitude moves with marginal cost. Report gas+CO2 (+50 %) as primary (extra loss
burns gas AND incurs its CO2), with the range. L2 −0.7..+2.1 %, L3+ +1.08 % (invariant
to marginal since extra_loss=0). Pump 7.9 vs impact 10.6 MWh (independent est., ~75 %).
Closure/generation_MWh reporting fix still owed (separate; doesn't affect these
numbers since regret uses econ + physics deltas, not generation_MWh).

## Evaluator earlier v1 notes + next steps

- Runs; self-consistency err 21.95 % against OBJ (expected — wrong target + an
  accounting bug: z_eval 275k > economic 139k, so the evaluator over-costs, likely
  fuel double-count / CHP fuel valuation / co2 basis).
- NEXT: (a) export the 3 residual sub-terms per level from result_collector;
  (b) re-target self-consistency to `components_sum`; (c) fix the fuel/co2/energy
  accounting to match `_cost_accounting` ↔ result_collector term-by-term; (d) re-run
  L1/L2/L3 gaps on economic cost and report OBJ-based vs economic-based side by side.

## Deliverable already in place

- `tools/evaluator.py`: radial-tree forward sim — native-exponential temperature
  decay (no PWL), Darcy–Weisbach supply+return, **station Δp pump work included**
  (the term Paper 1 omitted, per R2.4), violation records, bias/regret/selfcheck.
  Physics constants matched to calion (cp 4.186, ρ_flow 983, ρ_pump 1000).
