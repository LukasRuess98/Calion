## Gate G6 report — 2026-10-08
**Status:** PASSED — results consolidated; open author decisions listed below before the writing session

### Done
- 195 runs consolidated in `results/central_tes/scenario_comparison.csv` (factorial E/H × 3 calibrations, A1–A6, A2x, RH, exploratory KWK-hard and spec Mode H).
- Draft figures 2–7 (`results/central_tes/figures/`); figure 1 (system concept) left to the writing session.
- Scientific sanity check: `reports/central_tes/scientific_sanity_check.md`.
- Spec Mode H (bisection on Q_central) run as a variant: it removes the 1–7 attributable hours at ΔC_hyd ≤ 25 EUR/a and leaves 90–93 non-attributable hours → not converged in any scenario. This supports D3.

### Files added / changed
- `scripts/dhn_study/central_tes/{consolidate,figures}.py`
- `reports/central_tes/gate_G0…G6.md`, `reports/central_tes/scientific_sanity_check.md`

### Tests
14 / 0 (`tests/test_central_tes.py`), 34 / 0 (`tests/test_dhn_study.py`).

### Key numbers
| metric | value | unit | scenario |
|---|---|---|---|
| operating cost, reference | 21 464 283 | EUR/a | F000-E |
| v(F111) PF / RH day-ahead / RH persistence | 436.2 / 336.9 / 297.4 | kEUR/a | F111 |
| Shapley partner A / partner B / TES (E ≈ H) | 268.0 / 84.3 / 83.9 | kEUR/a | factorial |
| TES interaction term | 118.8 | kEUR/a | F111 |
| storage value with A+B (F111 − F110): fixed / monthly / daily | 135.2 / 128.6 / 208.6 | kEUR/a | A3 |
| ΔC_hyd(F111) A / C / B | 2.44 / 2.47 / 2.63 (F000: 2.51 / 2.54 / 2.67) | kEUR/a | Mode H (cuts) |
| ΔC_hyd(F111), spec Mode H | 0.025 (90 non-attributable h remain) | kEUR/a | exploratory |
| ΔC_hyd with KWK ≤ 4.0 bar hard | 29.6–29.9 for every scenario | kEUR/a | exploratory |
| partner-A utilisation U_A | 14.6 (F110 13.2) | % | F111 |
| partner-B full-load hours / price-weighted price | 410 / −6.8 | h / EUR/MWh | F111 |
| TES discharge / equivalent full cycles | 6.9 / 23 | GWh / – | F111 |
| v(F111) range over A5 cost regimes | 354–771 | kEUR/a | A5 |
| CO2 net | 34 019 → 32 734 (−3.8 %) | t/a | F000 → F111 |

### Findings for the writing session (one sentence each)
- The value of the central concept (≈ 2 % of the operating cost) comes mainly from partner A's waste heat; partner B and the TES contribute equally and the TES mostly as an enabler of the two sources (interaction term 119 of 135 kEUR/a).
- At 2025 load the central feed-in is hydraulically benign: the energy-only dispatch is infeasible in ≈ 95 h, but because of the existing plants, and repairing it costs ≈ 2.5 kEUR/a irrespective of the new assets.
- The TES temperature strategy (charging mask) changes the storage value by a factor of up to 10 for the TES alone; power and link DN hardly matter.
- Rolling horizon loses 23–32 % of the PF value, mostly through partner-A forecast quality.

### Deviations from spec (+ reason)
D1–D9 (`docs/dhn_storage_study/central_tes/model_and_deviations.md`); exploratory runs flagged; Priority B not run.

### Questions for the authors (consolidated, numbered)
1. Approve D3 (cut-based Mode H) and D4–D6 (plant mass-flow limits, envelope pump curves, MVA availability/Bio-KWK must-run).
2. Partner A: confirm that the ≈ 17 °C cooling-water discharges are the intended source (spec: ≈ 40 °C).
3. Partner B cost regime (reference high) and premium; demand charge applicability.
4. Reference TES strategy: fixed (spec) or daily; ΔT_tol of the charging mask.
5. Fuel/CO2 prices and the 9.9 MW electric boiler of the existing configuration.
6. Should the KWK 4.0 bar experience value become a hard limit (it is respected in 2025 operation in all but 6 h)?
7. Approve Priority-B sensitivities (B1–B4).

### Proposed next step
Author decisions on 1–7; then re-run the affected blocks (factorial ≈ 45 min, A1 ≈ 100 min on 2 cores) and start the writing session.
