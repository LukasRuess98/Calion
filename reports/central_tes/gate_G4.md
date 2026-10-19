## Gate G4 report — 2026-10-08
**Status:** PASSED

### Done
- Mode H (cut method, D3) for all 8 scenarios × 3 calibrations (24 runs); all hours re-validated in every iteration.
- ΔC_hyd(S) = C_H(S) − C_E(S); Shapley values for Mode E and Mode H (A, C, B).

### Files added / changed
- `results/central_tes/scenario_runs/{code}-H/{A,C,B}/` with `iterations.csv`, `cuts.csv` (gitignored); `shapley.json`, `factorial_summary.csv`

### Tests
Cuts respected in the re-solved schedule (test 11): passed. All 24 Mode-H runs converged (0 violating hours) after 5 iterations.

### Key numbers
| scenario | ΔC_hyd A / C / B [EUR/a] | cuts A | ΔC_hyd(S) − ΔC_hyd(F000), A [EUR/a] |
|---|---|---|---|
| F000 | 2 506 / 2 543 / 2 672 | 135 | 0 |
| F001 | 2 506 / 2 543 / 2 672 | 135 | 0 |
| F100 | 2 521 / 2 558 / 2 687 | – | +15 |
| F010 | 2 506 / 2 543 / 2 675 | 135 | 0 |
| F110 | 2 596 / 2 371 / 2 503 | 139 | +90 |
| F101 | 2 465 / 2 503 / 2 630 | 135 | −41 |
| F011 | 2 452 / 2 489 / 2 615 | 138 | −54 |
| F111 | 2 441 / 2 474 / 2 627 | 141 | −65 |

| Shapley [kEUR/a] | partner A + HP | partner B EB | TES | v(F111) | TES interaction v(F111) − v(F110) − v(F001) |
|---|---|---|---|---|---|
| Mode E | 268.0 | 84.3 | 83.9 | 436.2 | 118.8 |
| Mode H (A) | 268.0 | 84.3 | 83.9 | 436.3 | 118.9 |
| Mode H (C) | 268.1 | 84.3 | 83.8 | 436.3 | 118.7 |
| Mode H (B) | 268.1 | 84.3 | 83.8 | 436.2 | 118.6 |

| Mode-H convergence (F111, A) | iteration 0 → 5 |
|---|---|
| violating hours | 97 → 32 → 6 → 3 → 2 → 0 |
| objective [EUR/a] | 21 028 084 → 21 030 525 |
| re-dispatch F000 E→H | GT −0.13 GWh, HW1 +0.09 GWh, KWK +0.05 GWh |

### Findings (one sentence each)
- The hydraulic repair of the energy-only dispatch costs ≈ 2.4–2.7 kEUR/a (0.01 %) and is achieved by shifting ≈ 0.1 GWh from the GT to HW1/KWK in ≈ 100 hours.
- The central assets do not add to this cost; with TES it even falls slightly (−65 EUR/a), i.e. no measurable hydraulic penalty at reference size (H4 not supported at 2025 load).
- Hydraulics do not shift the Shapley attribution (differences ≤ 0.1 kEUR/a), robust over the three calibrations.

### Deviations from spec (+ reason)
- D3 (cut method). The spec method (bisection on Q_central) is implemented (`hydraulics.mode_h_method: central_bisection`); it cannot remove the non-attributable violations and would leave F000–F111 infeasible in ≈ 90 h.

### Questions for the authors
1. Given the near-zero ΔC_hyd, is the soft KWK limit of 4.0 bar (exceeded in ≈ 670 h by every energy-only schedule, 6 h in 2025 operation) the more relevant hydraulic constraint for the paper? A hard-limit sensitivity is prepared (B4) but not run (priority B).

### Proposed next step
G5: rolling horizon and sensitivities A1–A6.
