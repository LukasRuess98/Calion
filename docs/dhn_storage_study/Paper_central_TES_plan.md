# Follow-up paper: central TES with two industrial sources in DHN-A — status, screening and plan

Status: 2026-10-07 · Draft for gate G0 of the coding-agent specification v2 (kept outside the repository) ·
Anonymised like the rest of `docs/dhn_storage_study/`.

**Note on sharing:** This plan is based on anonymised operator data (released for this repository). Get separate
approval before sharing it outside.

---

## 0. Decisions taken

| Topic | Decision |
|---|---|
| Naming | The paper is **anonymised**: network DHN-A, plants by type, consumers V01–V24, industrial partners "A" and "B". |
| Hydraulic layer | The **calibrated meshed Ersatznetz** of this study (`scripts/dhn_study/netzmodell.py`, 25 nodes, 31 edges, 7 meshes, calibration variants A/C/B), **not** the uncalibrated tree of the existing CALION energy configuration. |
| Site of the central feed-in | **Storage site S** (node `S` on the east transport line L5, consumer V22). It is 1.25 km from the KWK busbar: L1a (854 m) to K1, then L5a (394 m). |
| Plants | As defined in `data/dhn_a/plants.yaml` and in the existing energy configuration. |
| Waste heat | The waste-heat columns of the energy-model input are partner B's waste heat. Partner A's waste heat will be provided separately. |
| Compute | Full-year MILP runs with Gurobi on the author's PC (see §7). |

**Mapping to the specification:**

| Spec term | DHN-A |
|---|---|
| Central site, TES, HP, P2H | site S; partner A = low-temperature waste heat (≈ 40 °C) upgraded by an HP; partner B = electrode boiler, 10 MW available |
| "North/east/south" plants | KWK (main plant, gas CHP, **only pressure holder**); east: MVA, GT, Bio-KWK (mass-flow controlled); south: HW1 behind pump station PS1; west: HW2 supplies the secondary network west through heat exchangers |
| Master plant | KWK, which regulates on the remote point V06 (≈ 1.2 bar) — while it runs (§2) |
| Critical nodes | V06 (south end), V03/V10/V12/V23/V24 (Mitte) |

---

## 1. What exists

### 1.1 Energy layer (CALION)

| Spec item | Module | Status |
|---|---|---|
| Heating curve, validated loss model | `network.heating_curve`, `calion/models/blocks/pipe_pair.py` | usable |
| Existing plants with costs | existing energy configuration | usable; reconcile capacities with `plants.yaml` |
| HP with exogenous COP, waste-heat cap, TES-charging channel | `calion/models/blocks/heat_pump.py` | extend: cascade, mode exclusivity, waste-heat cap over all modes, lift flag |
| Electrode boiler | `calion/models/blocks/p2h.py` | extend: partner-B heat price (λ + c_el,var)/η + π, demand-charge switch |
| Pressurised TES | `calion/models/blocks/geometric_storage.py` | extend: time-varying E_max (fixed/monthly/daily), temperature masks with counters; no round-trip η; size as parameter |
| Q_central and link capacity | – | new |
| Rolling horizon, forecast errors | `calion/run/rh_engine.py`, `calion/forecasting/` | usable; partner-A availability forecast modes are new |
| Factorial F000–F111, Shapley, Mode H, result layout | – | new |

### 1.2 Hydraulic layer (this study)

| Spec item (Section 5) | Status |
|---|---|
| Network, calibration, validation against measurements | done (`Netzmodell.md`, Sections 3–4) |
| PandaPipes closed loop | done; ≤ 0.016 bar against our own solver (`Netzmodell.md`, 4.7) |
| Control concept | KWK pressure holder, regulates on V06; east plants mass-flow controlled; PS1/PS2 boosters |
| Limits: min Δp | V06 1.2 bar (±0.2 open), Mitte 1.0 bar |
| Limits: plant outlet Δp | KWK 4.0 bar experience value / ≈ 5.7 bar pump; east plants 7.5 bar experience value |
| Limits: pressure | PN25, static pressure at the pressure-holding point, minimum static pressure per area and supply temperature (`plants.yaml`) |
| Elevations | `plants.yaml` (`dz_m`) |
| Absolute pressure, saturation margin | new: pressure-holding level + elevations + Δp profile |
| Pump power per feed-in | new (Δp × V̇ / η) |
| Flow direction, mixing zones | `netzmodell.quellanteile`, now with additional sources (`quellen=`) |

---

## 2. Hydraulic screening at site S (step P0b)

`python -m scripts.dhn_study.screening_einspeisung_s` → `results/dhn_study/screening/`.

**Set-up:**
* Inputs: all 8 351 hours of 2025 with complete boundary conditions; calibration variants A, C and B.
* Injection at S: +10, +20 and +40 MW; −10 and −20 MW stand for TES charging from the network.
* Control: the KWK supplies the residual and regulates as in operation (V06 at its set point, Mitte ≥ 1.0 bar).
* Cap: an injection may displace KWK water only down to 10 kg/s of KWK flow.
* East-plant Δp: measured value plus the modelled change.

This is a screening with the measured 2025 dispatch, not a Mode-E run.

| Injection at S | −20 MW | −10 MW | 0 | +10 MW | +20 MW | +40 MW |
|---|---|---|---|---|---|---|
| Hours with capped injection (KWK not running) | 0 | 0 | 0 | 4 434 | 4 800 | 6 327 |
| Δ required KWK Δp, heating period, mean [bar] | +0.22…+0.33 | +0.09…+0.12 | 0 | −0.09…−0.10 | −0.16…−0.19 | −0.26…−0.30 |
| Δ required KWK Δp, P95 [bar] | +0.37…+0.60 | +0.15…+0.21 | 0 | 0 | 0 | 0 |
| Hours with required KWK Δp > 4.0 bar | 10–24 | 1–4 | 1 | 1 | 0 | 0 |
| Δ east-plant Δp, heating period, mean / P95 [bar] | −0.25 / −0.1 | −0.13 / −0.07 | 0 | +0.15 / +0.31 | +0.38 / +0.72 | +0.83 / +1.57 |
| MVA hours > 7.5 bar (measured 2025: 548) | 228–261 | 362–386 | 548 | 722–736 | 956–976 | 1 483–1 531 |
| MVA hours > 9.0 bar (2025 maximum; reference calibration) | 0 | 0 | 0 | 13 | 35 | 180 |
| GT hours > 7.5 bar (measured: 69) | 25–31 | 39–45 | 69 | 130–135 | 332–350 | 767–808 |
| Bio-KWK hours > 7.5 bar (measured: 22) | 0 | 4–5 | 22 | 42 | 86–90 | 406–449 |

Ranges: calibration variants A, C, B.

**Flow reversals against the reference (hours of the year):**
* +20 MW: L1a 420–1 884, L1→City link (M12) 686–1 511, L3 241–680.
* +40 MW: L5b/L5c 300–1 199 additionally.
* −20 MW: L1a and L5a reverse in most hours; S then draws from both sides.

**Findings:**
1. **RQ2 holds at 2025 load, but the binding element is not a pipe.**
   * A feed-in at S replaces KWK water and pushes against the east feed on L5. The east plants must then deliver
     clearly more Δp, roughly +0.4 bar at 20 MW.
   * The KWK is relieved, but less than the east plants are loaded.
   * TES charging from the network at S does the opposite: it raises the required KWK Δp by up to 0.6 bar (P95).
2. **H3 is testable.** The feed-in shifts stagnation points into L1, the L1→City link and L3.
   * How often this happens depends strongly on the calibration variant: L1a is ×6.5–24.5 in the three optima.
   * Mode-H and H3 results should therefore always be shown for all three variants.
3. **The limit definition decides the result.**
   * The east plants already exceeded their 7.5-bar experience value in 548 h of 2025 (MVA, maximum 9.0 bar).
   * With 7.5 bar as a hard limit, F000 itself would violate it, which is the G2 stop.
   * Proposal: the hard limit is the flow-dependent pump curve (MVA 2 × 500 t/h, 90 m; operator data needed); the
     substitute is the 2025 maximum per plant. The 7.5 bar value is reported as a soft limit.
4. **The KWK does not run in summer.** Its flow is below 10 kg/s in 99 % of summer hours and in 21 % of heating-period
   hours. In summer the east plants (≈ 29 MW) carry the network.
   * The spec's re-dispatch rule "master takes residual" then fails. A feed-in at S displaces east heat, including the
     cheap MVA waste heat.
   * For Mode H the re-dispatch must follow the MILP merit order (`proportional_to_milp_split`) or be seasonal.
   * The hydraulic effect then reverses: less east flow means lower east-plant Δp.

---

## 3. Proposed deviations from the specification (need approval)

1. **Hydraulic layer:** the calibrated Ersatznetz with our own vectorised solver for production runs; pandapipes as the
   cross-check. Our solver is ≈ 10³ times faster (8 351 hours in 0.5 s), which Mode H's bisection over all hours and
   iterations needs.
2. **MILP resolution:** feed-in points plus the aggregated validated loss model. Demand is distributed to nodes in the
   hydraulic layer with the calibrated load weights.
3. **Limits:**
   * East plants: flow-dependent pump curve; substitute is the 2025 maximum per plant.
   * KWK: pump limit; 4.0 bar is reported as the experience value.
   * Minimum static pressure per area and supply temperature from `plants.yaml` (saturation check).
4. **Re-dispatch in Mode H:** the MILP merit order (`proportional_to_milp_split`) instead of "master takes residual",
   because the KWK is off in summer.
5. **Robustness:** Mode-H and stagnation-point results for all three calibration variants.

---

## 4. Remaining blockers

| # | Parameter | Substitute |
|---|---|---|
| B1 | Partner A waste heat Q_avail(t), T_source(t), year, resolution | announced by the author |
| B2 | HP at site S: capacity, units, owner, performance map | sweep around a reference size |
| B3 | Partner B: electricity-cost components (grid level, levies, reductions), premium range, availability, demand charge | low/high pair (A5), constant 10 MW (flagged) |
| B4 | TES reference volume, design pressure, T_low | rule-based reference + A1 grid |
| B5 | Day-ahead prices: year/source of the price column in the energy-model input; 15-min MTU after 1 Oct 2025 | ENTSO-E/SMARD 2025 |
| B6 | Pump curves of the east plants and the KWK | 2025 maximum per plant |
| B7 | Connection pipe S ↔ network: DN, route | DN sweep (A2) |
| B8 | Capacities: `plants.yaml` (plan A) vs. the existing energy configuration | plan A values, flagged |

---

## 5. Phase plan

| Phase | Content | Status |
|---|---|---|
| P0 | Audit, data requirements, blockers, implementation plan (this document) | draft |
| P0b | Hydraulic screening at S | **done** (§2) |
| P1 | MILP extensions (Sections 4.2–4.7), unit tests 1–9, F000 reproduction | next, locally with Gurobi |
| P2 | Hydraulic baseline F000: absolute pressure, saturation margin, pump power, limit definition (G2) | after P1 or in parallel |
| P3 | Factorial Mode E (8 runs) + post-hoc validation (G3) | |
| P4 | Mode H, ΔC_hyd, Shapley E vs. H, all calibration variants (G4) | |
| P5 | Rolling horizon (F111), sensitivities A1–A6 (G5) | |
| P6 | Consolidation, draft figures, sanity check (G6) | |

---

## 6. Open questions

1. **Partner B waste heat:** is it a second HP source at S (same HP, a second HP) or out of scope? In the specification
   the HP uses only partner A's waste heat.
2. **Summer operation:** which plant holds Δp when the KWK is off? The KWK Δp is still measured in summer.
3. **Pump curves** of the east plants and the KWK — available from the operator?
4. B2–B5 and B7 as in §4.

---

## 7. Continuing locally (Gurobi)

```
git fetch origin claude/dreamy-turing-jjcno2 && git checkout claude/dreamy-turing-jjcno2
pip install -e ".[study]" gurobipy pandapipes        # pyomo comes with the base dependencies
python -m scripts.dhn_study.run_netzmodell --ohne-kalibrierung
python -m scripts.dhn_study.screening_einspeisung_s
python -m pytest -o addopts="" tests/test_dhn_study.py
```

* Inputs that stay local (gitignored, not anonymised): the energy-model input of the real network (prices, grid CO₂,
  partner B waste heat) and partner A's waste heat. Only anonymised derivatives go into the repository.
* First steps locally: answer §6, then P1 starting with the TES block (strategies, masks) and Q_central with link
  capacity, then the HP cascade.
