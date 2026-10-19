## Gate G0 report — 2026-10-08
**Status:** PASSED (with substitutes; questions Q1–Q6 open)

### Done
- Repository audit, data inventory, blockers, model/deviation record (`docs/dhn_storage_study/central_tes/`).
- 2025 inputs built on the measurement index (8 759 h): demand incl. losses 632 GWh (peak 187 MW, 335 h imputed), measured T_VL/T_RL, DE-LU day-ahead prices 2023–2025 (15-min → hourly from 01.10.2025).
- Price column of the local energy-model input verified: identical to DE-LU day-ahead (max. deviation 0.00 EUR/MWh).
- Partner A waste heat read from the local file (two cooling-water discharges, 2023), mapped weekday-preserving to 2025.
- Link DN determined from the operator valve table: DN 400 at site S.
- Summer Δp master derived from 2025 data (hours without KWK flow).
- Solver switched to HiGHS (no Gurobi on this machine).

### Files added / changed
- `docs/dhn_storage_study/central_tes/{repo_audit,data_requirements,blockers,model_and_deviations}.md` — Phase-0 deliverables
- `configs/central_tes/base.yaml` — all parameters, assumptions flagged
- `data/prices/raw_{2023,2024,2025}.json`, `data/prices/README.md` — public price data (CC BY 4.0)
- local only (gitignored): `configs/local/central_tes_local.yaml`, `data/local/*` caches

### Tests
n/a in G0 (see G1)

### Key numbers
| metric | value | unit | scenario |
|---|---|---|---|
| demand incl. losses | 632 | GWh/a | 2025 |
| peak demand | 187 | MW | 2025 |
| partner A available heat | 35.6 (4.1 mean, 18.8 P95) | GWh/a (MW) | 2025 calendar |
| partner A source temperature | 16.6 (6–25) | °C | — |
| σ_A = available A heat / demand | 0.056 | – | — |
| HP COP grid / TES / cascade 80 °C | 2.05 / 1.76 / 2.45 | – | mean |
| hours with lift > 70 K (grid mode) | 97.5 | % | — |
| TES reference | 5 000 m³ → 296 MWh, 40 MW, τ 7.4 h | – | — |
| link capacity DN 400, 2.5 m/s | 25–78 (mean 47) | MW | κ_link 0.39 |
| measured supply temperature | mean 99.9, max 124 | °C | heating-curve max 122 |
| summer control (no KWK flow) | KWK Δp median 1.83, std 0.30; MVA std 1.47 | bar | 4 567 h |

### Deviations from spec (+ reason)
- Partner A source ≈ 16.6 °C, not ≈ 40 °C: measured data (the only ≈ 40 °C stream is a 1.4 MW compressor-air source, not used).
- Summer Δp master: the KWK remains the pressure holder at ≈ zero net flow (Δp low variance, V06 is the network minimum in 90 % of the hours; east plants vary with their flow). The Ersatznetz structure (KWK = root) therefore holds all year; Mode-H re-dispatch is not "master takes residual" but cut-based (D3).
- See `model_and_deviations.md` D1–D9.

### New assumptions (config key, value, justification)
- `heat_pump.eta_carnot` 0.50, `dT_app_K` 5, `cop_max` 7, `lift_limit_single_stage_K` 70 — literature (Jesper et al. 2021; David et al. 2017; Arpagaus et al. 2018).
- `heat_pump.c_el_var_eur_MWh` 38 — operator-side MV grid fee + levies with § 9b relief (to verify).
- `electrode_boiler.c_el_var_eur_MWh` low 9 / high 60, reference high; `premium_eur_MWh` 10.
- `tes.volume_m3` 5 000, `T_low_C` 67.5 (P95 return), `loss_per_h` 1e-4, `Q_max` 40 MW.
- `link.v_max_m_s` 2.5.
- `inputs.partner_a.calendar_shift_days` 728, `source_temperature` mean of warm discharge and intake.

### Blockers (Section 13 format)
See `docs/dhn_storage_study/central_tes/blockers.md` (B1, B3, B4, B8 substituted; none stops the runs).

### Questions for the authors (numbered)
1. Plant capacities: plan A (HW1 40 MW, MVA 45, GT 35) vs. the existing configuration (HW1 32 MW) – confirm plan A.
2. The 9.9 MW electric boiler at the KWK (existing configuration, not in plan A): does it exist? It would compete with partner B (disabled by default).
3. Partner A: is the HP meant to use the cooling-water discharges (≈ 16–19 °C) of the data file? The spec assumed ≈ 40 °C.
4. Partner B electricity-cost case: which is closer – HV customer with EnFG/§ 9b relief (low) or full levies for heat sold to a third party (high, reference)?
5. Fuel/CO2 prices of the existing configuration (gas 58.6 EUR/MWh, CO2 100 EUR/t) – keep for 2025?
6. HP electricity cost (38 EUR/MWh on top of λ) – does the operator or partner A bear the grid fee?

### Proposed next step
G1: MILP extensions with HiGHS, unit tests, F000 reproduction.
