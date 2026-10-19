# Repository audit – central TES study (Phase 0)

Status: 2026-10-08 · anonymised (DHN-A, plants by type, partners A/B, site S).

## 1. What the repository provides

| Item | Where | Use in this study |
|---|---|---|
| Calibrated meshed Ersatznetz (25 nodes, 31 edges, 7 meshes), vectorised loop solver, load distribution, tracer | `scripts/dhn_study/netzmodell.py` | hydraulic layer (unchanged) |
| Published calibrations A (reference), C, B and A_start/D/E | `scripts/dhn_study/kalibrierung/` | all Mode-E validations and Mode-H runs use A, C and B |
| Control-point analysis (`regelpunkt_signatur`), east coupling, pump head → Δp | `scripts/dhn_study/hydraulik.py` | summer control concept (G0 item 7) |
| Measured 2025 hourly data (169 signals), plants, sectors, temperatures | `data/dhn_a/` | demand, temperatures, plant flows/Δp/pressures, PS gains, west export, load at S |
| pandapipes closed loop (≤ 0.016 bar vs. own solver) | `scripts/dhn_study/gegenrechnung_pandapipes.py` | cross-check only (not re-run; the solver and the calibrated resistances are unchanged) |
| Screening of an injection at S | `scripts/dhn_study/screening_einspeisung_s.py` | reproduces; superseded by Mode E/H |
| CALION blocks: HP (exogenous COP), P2H, geometric storage, pipe pair, RH engine, forecasting | `calion/models/blocks/*.py`, `calion/run/rh_engine.py`, `calion/forecasting/` | **formulations reused, not the network assembler** (see deviation D1) |
| Existing energy configuration of the real network (named, not referenced in pushed files) | local | plant efficiencies, fuel and CO2 prices, CHP power credit, 9.9 MW electric boiler (not in plan A) |
| Tests | `tests/test_dhn_study.py` (34 pass) | unchanged; new `tests/test_central_tes.py` (14 pass) |

## 2. What the existing energy configuration contains (relevant items, values copied anonymised)

| Item | Value | Note |
|---|---|---|
| Topology | 32-node **tree** with DN 600 east trunk | not used (decision: calibrated meshed Ersatznetz) |
| Connection pipe to S | not defined | DN from the operator valve table (see data requirements, item 9) |
| KWK | gas CHP, η_th 0.743, η_el 0.177 | capacity from plan A (127 MW, n−1) |
| GT | gas, η_th 0.466, η_el 0.36 | 35 MW (plan A transition value) |
| Bio-KWK | biomass, η_th 0.485, η_el 0.177 | 14.5 MW |
| MVA | heat take-over 10 EUR/MWh, CO2-free | 45 MW (plan A transition value) |
| HW1 | gas boiler η 0.936 | 40 MW (plan A design) vs 32 MW in the configuration |
| Electric boiler at KWK | 9.9 MW, η 0.99 | **not in plan A** → disabled by default, question Q3 |
| Fuel / CO2 prices | gas 58.6, biomass 20 EUR/MWh_fuel; CO2 100 EUR/t | used unchanged (flagged) |
| Grid fee (operator) / demand charge | 61.6 EUR/MWh / 127 240 EUR/MW·a | demand charge reused for partner B (case `full`) |
| Heating curve | 70 °C at 30 °C → 122 °C at −15 °C | measured supply temperature used instead (bias −6.2 K, RMSE 8.3 K vs. curve) |

## 3. Gaps closed in this phase

| Gap | Implementation |
|---|---|
| HP cascade, mode exclusivity, waste-heat cap over all modes, lift flag | `central_tes/milp.py`, `central_tes/cop.py` |
| Partner-B heat price (λ + c_el,var)/η + π, demand-charge switch | `central_tes/milp.py` |
| TES with time-varying E_max (fixed/monthly/daily), masks with counters, no round-trip η | `central_tes/cop.py`, `central_tes/milp.py` |
| Q_central and link capacity | `central_tes/milp.py` |
| Factorial, Shapley, Mode E/H, result layout, RH with partner-A forecast modes | `central_tes/run.py`, `coupling.py`, `metrics.py`, `rolling.py` |
| Absolute pressures, saturation margin, pump curves, pump power | `central_tes/hydraulics.py` |
| Real-name scan before commits | `central_tes/name_scan.py` (term lists read from local files only) |

## 4. Solver

Gurobi is not available on the execution machine. All MILPs are solved with **HiGHS** (highspy 1.x via Pyomo APPSI),
relative MIP gap 0.1 %, fixed random seed, 2 threads. Full-year F111 (≈ 8 759 h, ≈ 52 k binaries): 40–50 s.
