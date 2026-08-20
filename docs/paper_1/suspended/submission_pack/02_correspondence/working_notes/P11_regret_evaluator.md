# P11 — Forward evaluator and the regret metric

**Depends on:** P1 (validated hydraulics) · **Blocks:** P4, P7
**Output:** `tools/evaluator.py`, `revision/audit/P11_evaluator.md`
**Priority: HIGHEST** together with P1. This is the paper's new contribution.

## What this is

A **forward simulator**, not an optimisation model. Given a fixed dispatch
schedule, it computes the true cost of executing that schedule under
high-fidelity physics, and reports any physical constraint the schedule violates.

Because it never optimises, it has no tractability limit and no linearisation
error anywhere. That is what makes it a defensible physics reference — Reviewer 2
asked for "comparisons against a validated nonlinear reference," and `T2P4` does
not qualify because it still uses PWL for the decay factor φ.

## Interface

```python
evaluate(schedule: DispatchSchedule,
         network: NetworkSpec,
         boundary: BoundaryConditions) -> EvaluationResult
```

`schedule` = per-asset, per-timestep thermal/electrical output plus storage
charge/discharge, extracted from any solved model at any T×P level.
For `T0*` and `T1*` schedules, disaggregate to `T2` nodes by a **fixed, documented
rule** (e.g. proportional to nodal demand share). The rule is part of the method
and must be stated in the paper — a different rule gives different regret.

`EvaluationResult` contains: total cost and every component, CO2, per-pipe losses,
per-pipe Δp, pump energy, node temperatures, and a violation record.

## Physics — no approximations

1. **Temperature propagation:** native exponential
   `T_out = T_gr + (T_in − T_gr)·exp(−U·L/(ṁ·c_p))`. No PWL, no Taylor expansion.
2. **Transport delay:** native. Interpolate sub-hourly rather than rounding to
   integer steps — the model's `k_p = round(τ/Δt)` is itself an approximation
   worth evaluating against.
3. **Hydraulics:** Darcy–Weisbach with computed friction factor at the
   P1-validated roughness; supply and return; `Δp_crit` at the critical consumer;
   pump power `ṁ·Δp/(ρ·η)`.
4. **Storage:** same self-discharge and efficiency model as the optimisation.
5. **Cost:** identical price series, tariffs, demand charge and CO2 accounting as
   the optimisation objective — otherwise regret measures accounting differences,
   not physics. **Assert this explicitly with a test.**

## Violations to record

- pipe velocity above the configured maximum
- Δp at any consumer below the required minimum
- unmet demand at any node after losses and delay
- storage SOC outside bounds
- asset output outside capacity or minimum-load

Report as count of violated timesteps, total violation energy, and worst instance.
**This may be the most important output of the whole task**: a schedule that looks
cheap but is not physically deliverable is a stronger indictment of low fidelity
than any cost difference, and no prior study reports it.

## Metrics

```
bias(l)      = z(l) − z(T2P1)
z_eval(l)    = evaluate(schedule(l)).total_cost
regret(l)    = z_eval(l) − z_eval(T2P1)
infeas(l)    = evaluate(schedule(l)).violations
```

Report bias and regret in absolute EUR, as % of `z_eval(T2P1)`, and for CO2.

## Validation of the evaluator itself

The evaluator must be trustworthy before it can be a reference:

1. **Self-consistency:** evaluate `schedule(T2P1)` with the evaluator configured to
   `T2P1`'s own physics (steady losses, no Δp, no delay). It must reproduce
   `z(T2P1)` within 0.1 %. Any larger difference is an accounting mismatch — fix
   before proceeding.
2. **Against measurement:** run the evaluator on the *measured* historical
   dispatch of Memmingen legacy and compare predicted node temperatures and
   return temperature at source against measurement. This is the same Stage 1
   comparison, applied to the evaluator rather than the optimiser, and it makes
   "validated nonlinear reference" literally true.
3. **Against Stadtbach pressure:** predicted Δp versus measured, from P1.
4. **Optional independent cross-check:** compare against `pandapipes` on a handful
   of representative hours, one appendix table. Do **not** substitute pandapipes
   for the evaluator — a different tool would reintroduce exactly the multi-factor
   confound the reviewers criticised. Days of work, not weeks.

## Runs to evaluate

Every schedule from P4 and P5. Cheap — no optimisation — so evaluate everything,
including all synthetic configurations.

## Report

`revision/audit/P11_evaluator.md`: design, the disaggregation rule, self-consistency
result, validation against measurement, violation summary per level, and a
publication-ready methods paragraph for `GAP:EVALUATOR`.

## Rules

- No PWL, no linearisation, no optimisation inside the evaluator.
- Cost accounting must be byte-identical in structure to the optimisation
  objective; assert with a test.
- If a schedule cannot be evaluated (infeasible boundary conditions), report the
  reason rather than silently substituting values.
