# Acceptance criteria

> **ALIGNED 2026-08-10 (see `00_MASTER_STATUS.md`).** Drop the Stadtbach/P12 criteria
> (Shape A). ADD: (a) redesigned ladder built (CP/CP+L/ZN/ND⁰/L1–L6/NL) with one
> phenomenon per step, config-diff-asserted; (b) **defensible trunk U on L1–L3** (no
> ×4.7), **service-lateral losses only at L4+**, total loss ≈ measured only at L4;
> (c) L4/L5 station code ported into worktree with **L1–L3 objectives byte-identical to
> the cent** vs pre-port; (d) exact additive identity holds on defensible-U configs;
> (e) station-hydraulics regret ≈ 0 reported (validated Memmingen + parameterised
> synthetic OOS); (f) NL-ref via exact decomposition, not a solve.

## Discovery (P12)
- [ ] Stadtbach total pipe length vs network extent resolved against DXF; 6 km/54 km explained
- [ ] Shaft inventory complete: count, channels, coverage, measured vs estimated consumers
- [ ] `shaft_pairs.csv` built; elevation known or explicitly flagged unknown
- [ ] Everything undeterminable listed as a data request to swa

## Model and runs
- [ ] `T0P1a/b/c` implemented; `T0P1b` loss energy matches `T2P1` within 0.1 %
- [ ] `T0P1` variable count equals `T0P0`
- [ ] `T2P3` differs from `T2P4` only in the delay flag (config diff asserted)
- [ ] Pump sanity: 0.3–1.5 % of thermal demand, or a documented physical reason
- [ ] Stadtbach modelled pump power consistent with documented PSS/PSW ratings
- [ ] All 81 synthetic configs feasible; IIS classification reported; sizing sensitivity run
- [ ] Stadtbach runs are dispatch-only (`investment.enabled: false`)
- [ ] Full-year `T2P4` attempted on Memmingen; outcome reported either way
- [ ] Every run records objective **and** bound

## Evaluator
- [ ] No PWL, no linearisation, no optimisation inside it
- [ ] Self-consistency: reproduces `z(T2P1)` within 0.1 % under matched physics
- [ ] Validated against measured Memmingen temperatures and Stadtbach pressures
- [ ] Cost accounting identical in structure to the objective (asserted by test)
- [ ] Disaggregation rule for `T0`/`T1` schedules documented in the paper

## Analysis
- [ ] `total = loss_main + topo_main + interaction` to machine precision, every scenario
- [ ] Decomposition reported for **cost and CO2**
- [ ] Every MIQCP comparison has point estimate **and** rigorous bound
- [ ] No claim smaller than the tolerance that resolves it
- [ ] Frozen-adder drift reported across scenarios, pipe lengths, both networks
- [ ] Decision-divergence metrics computed, not asserted
- [ ] ANOVA **and** regression on the balanced factorial
- [ ] Out-of-sample Stadtbach prediction reported, whatever the outcome
- [ ] `changes_vs_v1.csv` complete

## Validation
- [ ] BCM reported **in-sample and out-of-sample** (temporal and spatial holdout)
- [ ] Loss multipliers within a defensible band, residual in an explicit term
- [ ] Both calibrations compared; decomposition shown under each
- [ ] Flow MAPE decomposed by load band and bias vs dispersion

## Manuscript
- [ ] Zero GAP markers, zero unresolved `\result{}`, zero `\todo{}`
- [ ] Zero multi-key citations
- [ ] Abstract one paragraph; Conclusions without subheadings; five sections
- [ ] Novelty concession present **before** the novelty claim
- [ ] "Accuracy" only where it refers to decisions
- [ ] Title matches what the results support
- [ ] Memmingen assets at j1 everywhere including the graphical abstract
- [ ] No percentage with two different values anywhere
- [ ] v1 Table 6 deleted

## Release
- [ ] `results/v1_frozen/` intact
- [ ] **Stadtbach NDA respected**; CI check for identifying data
- [ ] Orphaned config removed
- [ ] Zenodo updated with evaluator, new DOI, CHANGELOG
- [ ] One-command reproduction tested

## Response letter
- [ ] Every comment answered with a manuscript pointer
- [ ] Where a reviewer was right and a conclusion changed, that is the first sentence
- [ ] Internal corrections disclosed proactively
