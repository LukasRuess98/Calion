## Gate G3 report — 2026-10-08
**Status:** PASSED with a scientific flag — violations exist in every scenario, but almost none is attributable to the central feed-in

### Done
- Full 2³ factorial in Mode E (8 runs), validated hour by hour on calibrations A, C, B.
- Attribution test per violating hour (Q_central → 0 with proportional re-dispatch).
- Stagnation-point analysis (flow reversals vs F000, |ṁ| > 10 kg/s in both) and mixing boundary on L5.

### Files added / changed
- `scripts/dhn_study/central_tes/{run,metrics}.py`; results in `results/central_tes/scenario_runs/{code}-E/` (gitignored)

### Tests
14 / 0.

### Key numbers
| scenario | C_E [EUR/a] | v_E(S) [kEUR/a] | violating h A / C / B | attributable to S (A / C / B) |
|---|---|---|---|---|
| F000 | 21 464 283 | – | 93 / 93 / 100 | – |
| F001 | 21 447 889 | 16.4 | 93 / 93 / 100 | 0 / 0 / 0 |
| F100 | 21 227 114 | 237.2 | 94 / 94 / 101 | 1 / 1 / 1 |
| F010 | 21 393 561 | 70.7 | 93 / 93 / 101 | 0 / 0 / 1 |
| F110 | 21 163 241 | 301.0 | 94 / 94 / 102 | 1 / 1 / 2 |
| F101 | 21 109 788 | 354.5 | 91 / 91 / 98 | 1 / 1 / 1 |
| F011 | 21 310 836 | 153.4 | 93 / 93 / 101 | 3 / 3 / 4 |
| F111 | 21 028 084 | 436.2 | 97 / 97 / 105 | 7 / 7 / 8 |

| metric (F111-E vs F000-E, calibration A) | value |
|---|---|
| required KWK Δp change, heating period mean / P5–P95 | +0.02 bar / −0.07 … +0.25 bar |
| MVA Δp change P95 | +0.47 bar |
| significant flow reversals (h) | L4b–L4d 162–257, L4a 147, M12 59, L1a 48, L5a 26, L1b 25 (C: L1a 18, M12 13; B: M34 53) |
| mixing boundary on L5 shifted | 431 h (387 h in the heating period) |
| water from S reaching K2 (≥ 10 %) | 1 h |
| max. link velocity | 1.78 m/s (limit 2.5) |
| pump electricity | 2 661 MWh (F000: 2 627) |

### Deviations from spec (+ reason)
- G3 rule ("no violation → stop"): not triggered formally, but the violations are a property of the existing-plant dispatch (G2). Attributable to the central feed-in: ≤ 8 h of 8 759 h in every scenario. **At the reference sizes (5 MW HP, 10 MW EB, 40 MW TES, DN 400) the central feed-in is hydraulically uncritical at 2025 load.** The hydraulic story has to come from A1 (80 MW TES), A2 (DN) and A3 (network charging under monthly/daily strategy).

### New assumptions
none.

### Questions for the authors
1. With the hydraulic layer barely binding for S, should the paper frame RQ2/H4 around (a) the cost of hydraulic feasibility of the energy-only dispatch as such (≈ 2.5 kEUR/a, F000 included), and (b) the design space where S becomes binding (A1/A2)?

### Proposed next step
G4: Mode H for all scenarios and calibrations, ΔC_hyd, Shapley E vs H.
