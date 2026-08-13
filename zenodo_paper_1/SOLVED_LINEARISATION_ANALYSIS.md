# Solved temperature-linearisation error (v1.2.0)

This supersedes the "bounded only by exact decomposition" statement in
[`L3NL_LINEARIZATION_ANALYSIS.md`](L3NL_LINEARIZATION_ANALYSIS.md) for the temperature
term: in the APEN revision the linearisation error is **directly solved** on
representative windows, not just bounded.

## Method (fix-and-relax native reference)

The piecewise-linear (PWL) temperature model is compared with the native, non-linearised
temperature propagation at an **identical operating point and identical integer schedule**:

1. Solve the MILP twin (`Memmingen_T2P3_native.yaml` with `milp_linearize: true`, i.e. the
   ordinary `T2P3` model) to optimality.
2. **Fix all binaries** to that solution.
3. Re-solve the continuous problem with `milp_linearize: false` — this restores the native
   heat-loss bilinearities (a non-convex QCP, Gurobi `NonConvex=2`); the pressure model stays
   piecewise-linear, so the *only* thing that changes is the temperature treatment.

The objective difference is then a **solved** measure of the temperature-linearisation error,
not a forward estimate. Config: `configs/memmingen/Memmingen_T2P3_native.yaml`
(`fix_binaries_from_milp: true`); windowed reproducers `_w3_winter_native.yaml`,
`_w3_autumn_native.yaml`. Reduction script: `tools/linearisation_solved.py`.

## Result (`results/analysis/linearisation_solved.csv`)

| Window | MILP cost | Native cost | QCP gap | Linearisation error |
|---|---|---|---|---|
| Winter (13–15 Jan) | 9 511.26 | 9 497.41 | 0.009 % | **−0.15 %** |
| Autumn (14–16 Oct) | 4 260.33 | 4 246.22 | 0.025 % | **−0.33 %** |

Both windows converge to ≤0.03 % gap. The error is small and **negative**: the PWL model
slightly *over*-states cost, so the native physics is marginally cheaper. This is consistent
with the exact-decomposition bound and confirms the paper's `<0.5 %` linearisation claim with a
genuine solve.

## Two limitations, reported as results

- **Full-year native re-solve is intractable.** The non-convex QCP finds no incumbent within the
  solver's QCP time budget, which is why the solved reference is confined to representative weeks.
  (This is the same intractability documented in `L3NL_LINEARIZATION_ANALYSIS.md`.)
- **A low-load summer week is infeasible** under native physics with the PWL schedule fixed: at
  summer flows the piecewise temperatures the optimiser relied on cannot be delivered — the same
  physical-deliverability failure the decision-regret evaluation exposes.

## Relation to the fidelity design rule

`tools/fidelity_rule.py` (→ `results/analysis/fidelity_rule.csv`) derives the a-priori burden
`b = λ/(1+λ)`, `λ = annual loss / annual demand`, validated at R²=0.86 over the 42 synthetic
networks plus Memmingen. See the manuscript's generalisability section and figure `F_rule`.
