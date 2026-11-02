# Model, implementation and deviations – central TES study

Status: 2026-10-10 · anonymised. Code: `scripts/dhn_study/central_tes/`, configuration `configs/central_tes/base.yaml`,
tests `tests/test_central_tes.py`. Entry point:

```
python -m scripts.dhn_study.central_tes.run --factorial            # 8 scenarios, Mode E + Mode H (calibrations A, C, B)
python -m scripts.dhn_study.central_tes.run --scenario F111-H
python -m scripts.dhn_study.central_tes.run --sensitivity <set>    # A1–A6, B2, B4, PR, PS, AT, P, X, X4, XR
python -m scripts.dhn_study.central_tes.run --rh --rh-factorial --rh-tes --rh-at --rh-robust   # rolling horizon
python -m scripts.dhn_study.central_tes.run --rh-foresight                                      # foresight decomposition (≈ 4 h)
python -m scripts.dhn_study.central_tes.validate_pandapipes       # hydraulic cross-check
python -m scripts.dhn_study.central_tes.economics                 # break-even tables
python -m scripts.dhn_study.central_tes.expansion                 # expansion summaries
python -m scripts.dhn_study.central_tes.consolidate               # scenario_comparison.csv
python -m scripts.dhn_study.central_tes.paper_fig_system          # paper figure 0 (system concept)
python -m scripts.dhn_study.central_tes.paper_figures             # paper figures 1–7
python -m scripts.dhn_study.central_tes.paper_tables              # reports/central_tes/paper_tables.md
python -m pytest -o addopts="" tests/test_central_tes.py
```

Solver: HiGHS 1.15 (Pyomo APPSI), MIP gap 0.1 %, seed 1234. Results (gitignored): `results/central_tes/`.

## 1. Energy layer (spec 4)

* **Operator perspective, one year, hourly, perfect foresight** (RH variant: `rolling.py`).
* **Existing plants** KWK, MVA, GT, Bio-KWK, HW1 (LP, no unit commitment). Marginal heat cost
  c_g,t = (p_fuel + EF·p_CO2)/η_th + τ_g − (η_el/η_th)·λ_t (τ_g: energy tax 5.5 EUR/MWh for HW1 and the new boiler; the CHP is relieved). Bounds per hour: nominal capacity (plan A), mass-flow capacity
  m_max·Δh_t (max of plan A and the 2025 maximum), MVA availability = monthly P95 of its 2025 output, Bio-KWK
  must-run (min(cap, D_t)). East parallel-flow limit (plan A, raised to the 2025 envelope):
  Σ_{MVA,GT,Bio} Q_g,t ≤ 455 kg/s · Δh_t.
* **Partner A HP** (one unit, 5 MW_th): modes grid, TES, cascade→grid, cascade→TES; Q = COP·P with exogenous COP
  (Carnot fraction); one binary per mode and hour, Σ z ≤ 1; source limit Σ_m Q_m(1 − 1/COP_m) ≤ Q_A,avail;
  cascade boost Q_EB,boost = r·Q_HP,casc with r = (T_target − T_mid)/(T_mid − T_in), masked where T_target ≤ T_mid.
  Electricity cost (λ + c_el,var,HP)·P, c_el,var,HP = 38 EUR/MWh (operator-side grid fee + levies, flagged).
* **Partner B EB**: P ≤ 10 MW, η P = direct heat (grid, TES) + boost heat; the heat price c = (λ + c_el,var)/η + π applies
  to all heat delivered (incl. boost); demand-charge switch none/full.
* **TES (reference: temperature classes, D10)**: classes k = 90…120 °C (5 K) share the volume, Σ_k E_k/e_k ≤ V with
  e_k = ρc_p(T_k − T_low); E_k,t+1 = E_k,t(1 − λ_loss) + Q_ch,k − Q_dis,k (+ HP/EB charge in the 120 °C class);
  network water charges class k only if T_VL ≥ T_k − ΔT_tol, class k discharges only if T_k ≥ T_VL; binaries for
  charge/discharge exclusivity; cyclic E_k,T = E_k,0 per class. Spec variant (`tes.model: single`): one state with
  E ≤ ρVc_p(T_set,t − T_low) and the masks of T_set (strategies fixed 120 °C / monthly / daily). Location: site S
  (station of partner A, next to partner B).
* **Central feed-in** Q_central = HP(grid, cascade→grid incl. boost) + EB→grid + Q_dis − Q_ch,grid with
  |Q_central| ≤ ṁ_link·Δh_t, ṁ_link = ρ v_max A(DN).
* **Heat balance** Σ_g Q_g + Q_central (+ Q_tes_ext for a TES at another node, + Q_EBK for the optional electric
  boiler at the KWK) = D_t (measured feed-in incl. losses, + D_extra in the expansion study).
* **Objective**: plant costs + partner-B heat purchase + HP electricity + partner-A waste-heat fee π_A·Q_src + demand
  charge; capital cost only for the new south boiler in the expansion study (annualised); no penalties.
* **Rolling horizon** (`rolling.py`): 72 h window, 24 h commit; the TES state is handed over per temperature class;
  the tank starts empty and the energy left at year end is not credited.

## 2. Hydraulic layer (spec 5)

`hydraulics.py`, calibrated meshed Ersatznetz (variants A, C, B), see module docstring. Control: KWK pressure holder,
Δp set to the minimum keeping V06 ≥ 1.2 bar and the city-centre stations (V03, V10, V12, V23, V24) ≥ 1.0 bar — also in summer (2025 data: KWK holds 1.8 bar at ≈ zero
net flow). Hard limits: pump curves (KWK, MVA, GT, Bio-KWK, HW1), plant return pressure ≥ shutdown pressure, supply
pressure ≤ min(shutdown, PN25), KWK net flow ≥ −10 kg/s. Plant Δp anchored to the measured 2025 value of the hour.
Soft limits reported: KWK 4.0 bar, east plants 7.5 bar. Saturation margin and pump power reported.

## 3. Coupling (spec 6)

* Mode E: validation of every hour for all three calibrations; attribution test (Q_central → 0 with proportional
  re-dispatch removes the violation?).
* Mode H (default `cuts`): linearised hydraulic cuts on all feed-ins, re-validation of all hours each iteration,
  k_max = 10, margin 0.02 bar. The spec method (`central_bisection`) is available as an option.

## 4. Deviations from the specification (need approval)

| # | Deviation | Reason |
|---|---|---|
| D1 | The energy layer is a study model (`central_tes/milp.py`) at feed-in resolution, reusing CALION's block formulations (HP with exogenous COP, P2H, storage) rather than the CALION network assembler | decision P0 §3.2 (feed-in points + aggregated losses); the CALION tree topology is not the calibrated network; full-year runs in ≈ 1–2 min per MILP with HiGHS (class model) |
| D2 | Losses embedded in the measured feed-in instead of re-running the Paper-1 loss model | T_VL/T_RL exogenous → losses exogenous either way; the measured feed-in is network-specific |
| D3 | Mode H uses linearised cuts on all feed-ins (incl. existing plants), not only bisection on Q_central | in v1 (before D4/D5, D11) the energy-only F000 violated hydraulic limits in 93 h (A; v2: 3 h), caused by the dispatch of the existing plants (HW1 south support missing, east flow high); bisection on Q_central cannot repair them (G2) |
| D4 | Plant mass-flow capacities and the east parallel-flow limit of plan A are enforced in the energy layer | otherwise F000-E is infeasible in 485 h (HW1 above its pump capacity, east plants above plan flow) |
| D5 | Pump curves scaled to the 2025 envelope (MVA ×1.18) | measured 2025 operation exceeds the nominal-anchored generic curve (G2 rule: reported, not silent) |
| D6 | MVA availability = monthly P95 of the 2025 output; Bio-KWK must-run | the LP otherwise runs the MVA at 45 MW in months with revisions/limited waste and idles the flat-running Bio-KWK |
| D7 | Measured supply temperature instead of the heating curve | 2025 operation deviates from the curve (bias −6.2 K) |
| D8 | Rolling horizon implemented in `rolling.py` (72 h window, 24 h commit, realisation by merit order) instead of `calion/run/rh_engine.py` | the CALION engine is tied to the network assembler; forecast error: multiplicative i.i.d. noise per hour D_t(1+ε_t), σ = 5 % (simplification of `calion.forecasting.PerfectNoiseForecast`); robustness over three seeds and σ = 10 / 15 % (`--rh-robust`); prices known up to the end of the delivery day (next day after the 12:00 auction), beyond the last known day repeated (since 2026-10-11, D21) |
| D9 | Result and report paths: `results/central_tes/…`, `docs/dhn_storage_study/central_tes/…`, `reports/central_tes/…` | keeps the study separate from earlier work |

## 4a. Version 2 (2026-10-08, after the author decisions)

| # | Change | Reason / source |
|---|---|---|
| D10 | **TES with temperature classes** (reference): the volume is shared by classes 90…120 °C (5 K); network water charges a class only if T_VL ≥ class temperature, a class discharges only if its temperature ≥ T_VL; HP/EB charge the 120 °C class; Σ E_k/e_k ≤ V. The spec model (single state + strategy) stays as variant `tes.model: single` | the single-state mask let the network charge the tank in only 43 h/a (fixed) and dominated the TES value (factor 10 between strategies); the class model is the conservative linear representation of a stratified tank without mixing |
| D11 | **PS1 head control**: PS1 may raise its head up to its pump curve (1 pump, 429 m³/h at 40 m, no parallel operation) to hold V06; the radial south branch makes this exact without re-solving the flows | operator lever for the south; without it the south expansion is judged against the measured 2025 PS1 gain |
| D12 | **Prices 2025**: gas 48 EUR/MWh (EEX THE futures means 44.7 / 35.5 EUR/MWh for the two delivery halves of 2025 + ≈ 8 EUR/MWh grid/levies), boiler energy tax 5.5 EUR/MWh (CHP relieved), CO2 72 EUR/t (EUA futures means 71.6 / 73.4 EUR/t); old values (58.6 / 100) as sensitivity P | author decision 3 (literature/measurement check) |
| D13 | **Partner A = all four water-based streams merged** (two cooling-water discharges, air-conditioning water, wastewater; the daily wastewater sheet holds kWh/d); source temperature = hourly flow-weighted outlet temperature (time mean 17.4 °C, P95 23.9 °C, max 29.7 °C; heat-weighted mean 20.9 °C); waste-heat fee 5 EUR/MWh (sensitivity 0/10/20); HP electricity at day-ahead + 38 EUR/MWh | author decision 2 |
| D14 | **South expansion study** (+10/20/30 % of today's annual demand as new customers at the south nodes, same hourly shape; ≙ +53/107/160 % of today's south load); a new gas peak boiler at the south end with capacity as a decision (CAPEX 0.1 M EUR/MW, 25 a, 5 % + fixed O&M 2 kEUR/MW/a → 9.1 kEUR/MW/a) | author decision 1; the only MILP with a capacity decision — **superseded 2026-10-12 by D24 (no new boiler); kept as supplement** |
| D15 | Optional 9.9 MW electric boiler at the KWK (sensitivity P) | not in plan A nor in public plant data of the main plant → disabled in the reference |
| D16 | Mode H on calibration A for all scenarios, on A/C/B for F000 and F111 | runtime (class model ≈ 2 min per MILP); v1 showed ≤ 0.3 kEUR/a spread between calibrations |
| D17 | Cost assumptions updated to the literature check of 2026-10-09: HP 0.95 M EUR/MW (DEA), pressurised TES 1 000 / 1 500 / 2 500 EUR/m³ (project data 2013/14 escalated), DN 400 pipe 3 000 EUR/m (DEA energy transport), partner-B low electricity cost 12 EUR/MWh (non-waivable levy floor); HP grid fee kept at 38 EUR/MWh (HV / reduced-fee case) with sensitivity 55 / 76 EUR/MWh | `reports/central_tes/literature_check.md` |
| D18 | Prosumer sensitivities (set PR: HP size, source temperature, EB size, partner-A availability B1, Carnot fraction B3, HP grid fee), price years B2, V06 limit B4, full factorial under RH | author decision 2026-10-09: prosumers are a main part of the paper; Priority B approved |
| D19 | Pipe reinforcement of the south trunk as an alternative to the new south boiler (set XR: parallel pipe of equal DN, K × 0.25, on L4b or L4a–c) | author decision 2026-10-09 |
| D20 | Final check 2026-10-10: (i) HP COP and cascade ratio to the TES use the top class temperature (matters only for the atmospheric set AT, re-run); (ii) RH runs extended: atmospheric set under RH, robustness over forecast-noise seeds and σ = 10 / 15 %; (iii) partner-A calendar shift ± 7 d (set PS); (iv) reported link velocity uses the link flow only | independent pre-writing check; results in `results_v2.md` §3–§5 and `paper_tables.md` |
| D21 | 2026-10-11: (i) RH price forecast corrected — the earlier "same hour of the previous day" used not-yet-known prices for hours 48–71 of each window; all RH results re-run (TES 220 → 217 k, concept 330 → 324 k; archive `rolling_horizon_v1_lag24`); noise now drawn per window from (seed, window start). (ii) Foresight decomposition (`--rh-foresight`): window 72–720 h, hourly re-planning, perfect prices / demand / partner A, terminal value (mean marginal heat cost of the next week, per class where it can discharge), PF guide curve (soft end-of-window target, upper bound), MIP gap 10⁻⁵. (iii) A3e: single-state energy-only storage (`tes.temperature_masks: false`) as upper bound of the storage-model bracket | writer's literature contrasts (foresight 85–97 % in the literature; single-state over- vs underestimation); results `results_v2.md` §10, `paper_tables.md` T4b |
| D22 | 2026-10-12 (writer's open items): (i) T1 reports the source temperature as time mean 17.4 °C with the heat-weighted 20.9 °C in brackets (both correct, different weights); (ii) set PG: gas price 37 / 42 EUR/MWh for all eight scenarios; (iii) footprint vs uncertainty: V06 deviation in the pandapipes check and footprint per calibration variant (`results_v2.md` §10c) | consistency and reviewer robustness |
| D23 | 2026-10-12 author decision "literature values": partner-B electricity cost backed by levy floor + BNetzA network charge (35 / 54 / 73 EUR/MWh, set BL; reference 60 kept, upper half); demand charge none under atypical grid use (§ 19 (2) StromNEV); KWK 4 bar stays the operator experience value (no generic literature value; soft threshold, X4); network schematic approved | literature_check.md 7b, 10 |
| D24 | 2026-10-12 author decision: no new south boiler. **South hosting capacity** (`hosting.py`): new customers at the south nodes, +15…35 % of today's demand; no new capacity; `new_boiler.mode: unserved` turns the NEW variable into unserved heat of the new customers (penalty 1 000 EUR/MWh, ≤ D_extra, no capacity variable, withdrawn from the south nodes with the south weights); hosting limit = last level without unserved heat; values at equal delivered heat (unserved heat at the HW1 heat cost). Variants: no TES, partners, TES at S, TES at V06 (5 000 m³ / 40 MW, 20 000 m³ / 80 MW), pump curves vs KWK ≤ 4 bar. Mode H with a TES away from S: anticipatory cuts for all hours within 0.5 bar of a limit (`hydraulics.anticipate_tes_ext_bar`), k_max 20; residual ≤ 0.05 bar = converged | question "can the storage help the south"; results `results_v2.md` §11, `paper_tables.md` T7, fig5 |

**Approval:** D1–D16 approved by the authors on 2026-10-09 ("apply the suggested changes").

**Convergence (to state in the methods):** Mode H converges in all runs at today's load (1–4 iterations) and in
13 of 23 expansion and reinforcement runs; in the others 1–8 h (TES at S) or 73–109 h (exploratory TES at the south end) remain after
k_max = 10 iterations; the cost change over the last iterations is < 1 kEUR/a for TES at S.

## 5. Literature for assumed parameters (to be checked by the authors)

* Large heat pumps, Carnot fraction 0.4–0.6, COP vs. lift: Jesper M. et al. (2021), *Renew. Sustain. Energy Rev.* 137,
  110646, doi:10.1016/j.rser.2020.110646; David A. et al. (2017), *Energies* 10(4), 578 (Heat Roadmap Europe, large-scale
  electric HPs in DH); Arpagaus C. et al. (2018), *Energy* 152, 985–1010 (high-temperature HPs, lift limits).
* Pressurised DH storage size class: AEE INTEC (2024), *Großwärmespeicher in städtischer Fernwärme* (2 × 5 500 m³
  pressure tanks, up to 150 °C).
* Pump curves: Gülich J.F., *Centrifugal Pumps*, Springer (shut-off head 1.1–1.35 × BEP head for low specific speed).
* 2025 levies (KWKG 0.277, offshore 0.816, §19 StromNEV 1.558/0.050/0.025, concession fee 0.11 ct/kWh): 2025 DSO price
  sheets based on the TSO publication (netztransparenz.de); electricity tax § 3 StromStG 2.05 ct/kWh, § 9b relief
  2.0 ct/kWh; EnFG §§ 30 ff. (surcharge limitation for electricity-cost-intensive companies).
* Prices: Bundesnetzagentur | SMARD.de via energy-charts.info (CC BY 4.0).
* Gas and EUA 2025: means of daily EEX settlement prices (THE natural-gas futures, EUA Dec-25/Dec-26 futures) for
  01.10.2024–31.03.2025 and 01.04.–30.09.2025, as published in German utility index tables (2026).
* Investment (updated 2026-10-09, D17; details and URLs in `reports/central_tes/literature_check.md`): large HP
  0.95 M EUR/MW_th (DEA, waste-heat HP 10 MW, 2025 EUR); gas peak boiler 0.1 M EUR/MW_th (DEA 0.043–0.27); pressurised
  TES 1 000 / 1 500 / 2 500 EUR/m³ + 0.1 M EUR (project data 2013/14, escalated; DEA atmospheric tanks ≈ 220 / 177 / 143 EUR/m³ at 5 000 / 10 000 / 20 000 m³);
  DN 400 pipe 3 000 EUR/m (DEA energy transport); lifetimes TES 30 a (DEA 40), HP 20 a (DEA 25), pipe 40 a (DEA 45).
