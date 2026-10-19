## Gate G1 report — 2026-10-08
**Status:** PASSED (F000 reproduction against measured operation only qualitative, see below)

### Done
- MILP of spec 4.2–4.7 implemented (`scripts/dhn_study/central_tes/milp.py`, `cop.py`), all parameters in `configs/central_tes/base.yaml`.
- HP: four modes, binary exclusivity, source limit over all modes, cascade with exogenous r_d and masks, lift flags.
- Partner B: heat price (λ + c_el,var)/η + π on all EB heat incl. boost; demand-charge switch.
- TES: strategies fixed/monthly/daily, masks with counters, binary exclusivity, cyclic SOC, no round-trip efficiency.
- Q_central explicit, link capacity from DN and v_max with hourly Δh.
- Existing plants with plan-A heat and mass-flow capacities, east parallel-flow limit, MVA availability, Bio-KWK must-run (D4, D6).
- Unit tests of spec 12 (items 1–9, 11) on a 96-h window; existing study tests still pass.

### Files added / changed
- `scripts/dhn_study/central_tes/{config,inputs,cop,milp}.py` — energy layer
- `tests/test_central_tes.py` — 14 tests

### Tests
14 passed / 0 failed (`tests/test_central_tes.py`); 34 passed (`tests/test_dhn_study.py`).

### Key numbers
| metric | value | unit | scenario |
|---|---|---|---|
| objective | 21 464 283 | EUR/a | F000-E |
| objective | 21 028 084 | EUR/a | F111-E |
| MIP gap | 0 / 2.8e-6 | – | F000 / F111 |
| runtime (build + solve) | 0.6 + 2.2 | s | F000-E |
| runtime (build + solve) | 3.7 + 52.7 | s | F111-E |
| F000 dispatch KWK / MVA / GT / Bio / HW1 | 137 / 273 / 44 / 126 / 52 | GWh | F000-E |
| measured 2025 | 159 / 238 / 71 / 126 / 36 | GWh | measured |
| hourly correlation F000 vs measured | KWK 0.80, MVA 0.89, GT 0.40, HW1 0.17 | – | – |
| cost of the measured dispatch, same cost model | 25.47 M (F000 −15.7 %) | EUR/a | – |

### Deviations from spec (+ reason)
- No "existing validated baseline" exists for this network and aggregation; F000 is compared with the measured 2025 dispatch. The energy-only optimum is 15.7 % cheaper than the measured dispatch priced with the same cost model: it uses more MVA heat and less GT, and it drops HW1 in hours where the operator runs it for the south end (see G2). Values v(S) are therefore relative to an idealised dispatch.
- D1 (study model instead of the CALION assembler), D4, D6, D7 (see `model_and_deviations.md`).

### New assumptions (config key, value, justification)
- `plants.m_max_kg_s`, `plants.east_parallel_max_kg_s` 455 — max(plan A, 2025 maximum).
- `plants.MVA.availability` monthly P95; `plants.BIO.must_run` true — 2025 operation.
- `plants.unit_commitment` false — aggregated multi-unit plants.

### Blockers
none new.

### Questions for the authors
1. Is a cost gap of ≈ 16 % between the energy-only optimum and the 2025 operation plausible, or are there contracts (e.g. GT electricity, MVA heat take-over volume) that should constrain F000?

### Proposed next step
G2: hydraulic baseline of F000 on the calibrated Ersatznetz.
