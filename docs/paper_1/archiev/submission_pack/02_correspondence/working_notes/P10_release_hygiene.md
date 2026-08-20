# P10 — Reproducibility and release hygiene

**Depends on:** P4, P5, P6 · **Output:** `revision/audit/P10_release.md`

## NDA — read first

**Stadtbach raw data and configs containing identifiable operational data do not
go to Zenodo.** The data-availability statement must state this explicitly and
distinguish what is published from what is not:

- Memmingen: model source, configs, post-processing (as in v1) — published
- Stadtbach: **structure only** (anonymised topology, no absolute demands, no
  consumer names, no shaft identifiers), or excluded entirely with a statement
- Input time series for both: NDA, anonymised summary statistics only

Add a CI check that fails on any commit containing absolute demand values,
consumer names or shaft identifiers in a published path.

## Tasks

1. **Remove the orphaned config** `Memmingen_L3_NoPhys.yaml` (truncated horizon,
   divergent parameters, referenced by nothing), or move it to `deprecated/` with
   a README stating it is not part of the study.

2. **Config-to-paper consistency script**: assert every parameter quoted in the
   manuscript matches its config — `eta_pump`, roughness, U-values, capacities,
   efficiencies, emission factors, heating-curve points, storage parameters,
   prices, **and both networks' total pipe length**. Emit paper vs config vs
   PASS/FAIL. This is the error class that produced the j1/j12 discrepancy, the
   10.4/10.5 mismatch and the 6 km/54 km header comment.

3. **One-command reproduction** (`make reproduce` or a documented PowerShell
   script) regenerating every table and figure from committed configs plus a
   results archive. Document runtime and which steps require Gurobi.

4. **Pin versions and seeds**: Gurobi, Pyomo, Python. Note in the paper that MIQCP
   results are solver-version dependent.

5. **Update Zenodo**: new version with the T×P configs, the new variants, the 81
   synthetic configs, `tools/evaluator.py`, the P7 analysis CSVs, and a
   `CHANGELOG.md` explaining v1.0.0 → this version and why. Keep CC-BY-4.0.
   Reserve the DOI and update the manuscript citation.

6. **Evaluator as a citable artefact.** `tools/evaluator.py` is a contribution in
   its own right — document its interface, include the validation results from
   P11, and make it usable standalone.

## Report

`revision/audit/P10_release.md`: deletion confirmation, parameter consistency
table, reproduction runtime, Zenodo version/DOI, NDA check result.
