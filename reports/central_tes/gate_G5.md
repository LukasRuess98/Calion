## Gate G5 report — 2026-10-08
**Status:** PASSED (Priority A complete; Priority B not run; two exploratory runs flagged)

### Done
- Rolling horizon F111 (72 h window, 24 h commit, merit-order realisation), Mode E with both partner-A forecast modes, Mode H with the converged PF cuts.
- Sensitivities A1–A6 on F111 (E; H with calibration A where required by the spec).
- Exploratory (not in the spec, flagged): A2x = DN sweep with daily strategy and 80 MW TES power (where does the link bind?); KWK 4.0 bar as hard limit (factorial, calibration A); spec Mode H (`central_bisection`, factorial, calibration A).

### Files added / changed
- `scripts/dhn_study/central_tes/{sensitivity,rolling,consolidate,figures}.py`
- results: `results/central_tes/{sensitivities,rolling_horizon,exploratory}/` (gitignored)

### Tests
14 / 0 (unchanged); RH realisation checked: the greedy merit order reproduces the F000 LP exactly (0.00 GWh, 0 EUR).

### Key numbers
**Foresight (7.3)** — v = C_PF(F000) − C(F111); RH F000 = PF F000 (no decisions)

| run | C [EUR/a] | v(F111) [kEUR/a] | share of PF value |
|---|---|---|---|
| PF, Mode E | 21 028 084 | 436.2 | 100 % |
| RH, partner A schedule known day-ahead | 21 127 394 | 336.9 | 77 % |
| RH, partner A persistence (same hour previous week) | 21 166 864 | 297.4 | 68 % |
| RH, Mode H (PF cuts) | 21 127 108 | 337.2 | 77 % |

**A1 – TES energy × power** (value vs F111 without TES, C = 21 162 914 EUR/a; Mode H differs by ≤ 0.1 kEUR/a)

| V [m³] / E [MWh] | Q 10 MW | Q 20 MW | Q 40 MW | Q 80 MW |
|---|---|---|---|---|
| 2 500 / 148 | 110.5 | 116.9 | 118.9 | 119.5 |
| 5 000 / 296 (ref) | 122.2 | 131.3 | **134.8** | 137.0 |
| 10 000 / 591 | 139.0 | 149.6 | 155.7 | 159.3 |
| 20 000 / 1 182 | 166.6 | 178.3 | 185.1 | 191.2 |

kEUR/a. ΔC_hyd 2.39–2.52 kEUR/a in all 17 cases (≈ F000), attributable violations ≤ 7 h.

**A2 – connection DN** (F111, fixed strategy): C_E 21 028 049–21 028 112 EUR/a for DN 300–500 (spread 63 EUR/a) (κ_link 0.24–0.61) — the link never binds at reference sizes. **A2x (daily, 80 MW)**: v(F111) 507.2 / 526.9 / 540.5 kEUR/a for DN 300 / 400 / 500; attributable violations 19 / 25 / 67 h; ΔC_hyd 2.34 / 2.27 / **4.35** kEUR/a.

**A3 – TES temperature strategy** (Mode E; H adds 2.4–2.5 kEUR/a everywhere)

| strategy | v(F001) | V_TES with A (F101−F100) | V_TES with B (F011−F010) | V_TES with A+B (F111−F110) | v(F111) | grid-charging allowed [h] |
|---|---|---|---|---|---|---|
| fixed 120 °C | 16.4 | 117.3 | 82.7 | 135.2 | 436.2 | 43 |
| monthly | 10.4 | 114.4 | 74.3 | 128.6 | 429.6 | 14 |
| daily | 166.8 | 200.7 | 183.1 | 208.6 | 509.6 | 531 |

kEUR/a.

**A4 – partner-B premium** (F111 vs F101 = 21 109 788 EUR/a): v_B(π) = 126.8 / 81.7 / 46.2 / 26.9 / 18.9 / 11.3 kEUR/a for π = 0 / 10 / 20 / 30 / 40 / 60 EUR/MWh; EB heat 4.9 → 0.24 GWh; premium revenue of partner B π·Q = 0 / 40.6 / 60.3 / 30.6 / 26.2 / 14.5 kEUR/a (maximum near π ≈ 20 EUR/MWh). v_B stays > 0 for every π (negative-price hours), so a strict break-even premium does not exist.

**A5 – electricity-cost regime** (v(F111) vs F000, kEUR/a): low/none 770.9; high/none 436.2; low/full 354.4; high/full 354.4 — with the demand charge (127 kEUR/MW·a) the EB is never used.

**A6 – cascade** (F111): cascade off vs T_mid 70/80/90/100 °C: C_E within 0.8 kEUR/a (fixed) and 0.9 kEUR/a (monthly) — below the solver tolerance (≈ 0.4 kEUR/a); cascade share of partner-A heat ≤ 3.6 %.

**Exploratory – KWK 4.0 bar as hard limit** (calibration A): ΔC_hyd = 29.6–29.9 kEUR/a in every scenario (≈ 1 100 cuts), i.e. ×12, but again independent of the central assets (spread 0.4 kEUR/a).

### Deviations from spec (+ reason)
- D8: RH implemented in the study module (window MILP + merit-order realisation); forecast model as CALION's PerfectNoiseForecast (σ = 5 %).
- RH Mode H re-uses the PF cuts; the realised (merit-order) dispatch is not re-validated hydraulically.
- A2x and the KWK-hard run go beyond the spec (marked exploratory); no Priority-B sensitivity was run.

### New assumptions
- `rolling`: σ_D 5 %, prices day-ahead known for 24 h, persistence beyond; window 72 h / commit 24 h; supply temperature known.

### Questions for the authors
1. The TES value is dominated by the charging mask (A3): with ΔT_tol = 0 the network can charge the TES in 43 h (fixed) or 531 h (daily). Should the reference use the daily strategy or a ΔT_tol > 0?
2. Approve running Priority B (B1 partner-A scaling, B2 price years, B3 η_C, B4 Δp limits incl. KWK 4.0 bar hard)?

### Proposed next step
G6: consolidation, figures, sanity check.
