# P5 — Synthetic full factorial

> **ALIGNED 2026-08-10.** In progress: `_run_synth_factorial.py` runs the decomposition
> cells (T0P0/T2P0-U0/T2P1) across the 42 nets that have copperplates (42×3=126 jobs,
> bounded 6 workers × 8 threads). PoC confirms loss dominates (99 %/0.6 % on a 15 km
> net). Still to do per this prompt: **IIS-diagnose the ~20 nets without copperplates**
> (feasibility, no silent drop); build a **balanced** grid; add the **generation-topology
> moderator** (central vs distributed gen — carries the moderator claim under Shape A);
> run **parameterised L4/L5** (stations ∝ node demand, pressure-study laterals) as the
> out-of-sample station-hydraulics test; ANOVA + regression on loss_main/topo_main/regret.

**Depends on:** P1, P2, P3, P11 · **Blocks:** P7
**Output:** `results/v2/synthetic/…`, `revision/audit/P5_synthetic.md`

## 1. Diagnose the infeasibility before fixing it

v1 dropped 45 of 81 configurations because the L1 LP relaxation was infeasible.
That is not a property of the networks; it means installed capacity was too small
for that demand configuration. The author flags this fix as potentially tricky —
so **diagnose first, do not apply a blanket rule blindly**.

1. For each of the 45, run the LP relaxation and extract the **IIS** (Gurobi
   `computeIIS`). Classify: insufficient generation capacity / storage too small
   to ride the peak / demand unservable within grid limits / other.
2. Report the classification table. If the failures have more than one cause, a
   single sizing rule will not fix them all — say so and handle each class.
3. Adopt **one documented sizing convention**, e.g.
   `Q_gas = 1.25 × peak_demand(config)`, other assets scaled to preserve the
   primary-case ratios, `E_storage = tau_s × peak_demand(config)`.
4. Verify 81/81 feasible at every level. Any remaining failure: report the binding
   constraint. **Never silently drop a configuration.**
5. **Report sensitivity to the convention** on a subset (e.g. 1.15× and 1.4×) —
   the conclusions must not depend on the sizing rule.

This replaces "36 retained after feasibility filtering" with a stated,
reproducible convention, which is what R2.5 asked for.

## 2. Runs

Same T×P codes as the real cases — no remapping.

81 configs × {`T0P0`, `T0P1b_local`, `T0P1b_frozen`, `T1P0`, `T1P1`, `T2P0`,
`T2P1`, `T2P2`} = 648 runs. Small MILPs; parallelise across configs on 66 cores.

`T2P3`/`T2P4` stay real-case only — state this scope limit explicitly.

**Evaluate every schedule** with `tools/evaluator.py` (P11) so regret exists
across the whole factorial, not just the real cases.

## 3. Per-configuration decomposition

```
loss_main   = cost(T0P1b_local) − cost(T0P0)
topo_main   = cost(T2P0)        − cost(T0P0)
total       = cost(T2P1)        − cost(T0P0)
interaction = total − loss_main − topo_main
aggregation = cost(T2P1) − cost(T1P1)
hydraulics  = cost(T2P2) − cost(T2P1)
regret(l)   = z_eval(l) − z_eval(T2P1)
```

Tidy CSV: one row per configuration × term, absolute and % of `z_eval(T2P1)`.

## 4. Statistics — ANOVA and regression

The design is balanced, so report a **variance decomposition** first: η² (or
partial η²) per factor and for the interactions. That is what R2.5's "more
balanced statistical analysis" points to. Then OLS for effect sizes:

```
y ~ log(pipe_length_km) + storage_h + node_count + HI
    + log(pipe_length_km):storage_h
```

Fit separately for `loss_main`, `topo_main` and `regret`. The **contrast between
those three fits** is the generalisable form of the paper's central claim.

Report coefficients with 95 % CIs, R², residual diagnostics, partial dependence.
Keep the median-by-pipe-length table as a descriptive companion only.

Confirm explicitly that the storage/pipe-length confound admitted in v1
(2 h configs unevenly distributed across pipe-length bands) is removed by the
balanced design.

## 5. Generation topology as a synthetic factor

The synthetic generator currently places generation centrally, mirroring
Memmingen. Since generation topology is now a hypothesised moderator (§3 of the
novelty statement), add a **fifth binary factor**: central vs distributed
generation (e.g. two producers at opposite ends with differing marginal cost).

This is the controlled counterpart to the Memmingen/Stadtbach contrast, and it
turns a two-point observation into a tested factor. If implementing it is
expensive, run it as a reduced design on the 27 configurations at
`node_count ∈ {15, 30}` rather than the full 81.

## 6. Checks

- `cost(T0P0) ≤ cost(T2P1)` in all instances
- report how many of 81 have positive total bias
- flag any non-monotonicity in pipe length and investigate rather than smooth over

## Report

`revision/audit/P5_synthetic.md`: IIS classification, sizing convention and its
sensitivity, feasibility confirmation, ANOVA and regression tables, confound
check, generation-topology factor results, anomalies.
