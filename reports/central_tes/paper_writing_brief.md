# Paper writing brief — central TES with two industrial prosumers in DHN-A

Self-contained hand-over for the writing session (status 2026-10-12: south expansion reframed as hosting capacity
without new capacity — author decision; RH re-run with leak-free price forecast; literature contrasts added).
Target journal: *Energy* (Elsevier). All material is anonymised; keep it that way (section 10).
Companion files in this package: `paper_tables.md` (generated tables T1–T7), `paper_figures.md` (figure notes),
`figures/` (fig0–fig7 as PDF + 600 dpi PNG), `model_and_deviations.md` (methods detail), `literature_check.md`
(cost sources), `results_v2.md` (full results log), `paper_readiness.md` (design check), `hydraulic_calibration.md`.

---

## 1. Working title and framing

Working title (to refine): *Central thermal energy storage at an industrial prosumer site: value attribution,
hydraulic feasibility and foresight limits in a multi-feed-in district heating network.*

Storyline (author decision: storage **and** prosumers are main parts):
1. A pressurised TES at an industrial prosumer site (partner A: waste heat + heat pump; partner B: spare electrode
   boiler) in an existing, meshed, multi-feed-in network.
2. What the concept is worth and **who creates the value** (factorial + Shapley; perfect foresight vs. rolling horizon).
3. What limits it and what it enables: **hydraulics** (pressure footprint today; south hosting capacity with load
   growth — can the TES replace new capacity?), **foresight**, and **investment** (break-even vs. literature costs).
4. What drives the prosumers (HP size, source temperature, fees, electricity-cost regime, premium window).

Candidate contributions (each backed by results below):
* C1 — Coupled energy–hydraulic assessment of a central TES with two heterogeneous industrial prosumers on a
  calibrated meshed network model, with hydraulic feasibility enforced by linearised cuts (Mode H) and an independent
  pandapipes cross-check.
* C2 — Value attribution by Shapley values under perfect foresight **and** rolling horizon: the prosumer share rises
  from 24 % to 34 % under realistic foresight; the TES keeps only ≈ 52 % of its value (decomposed in 4.5).
* C3 — A temperature-class TES formulation (linear, no mixing) that captures when network water can charge/discharge
  the tank; a single-temperature formulation understates the TES value by a factor of ≈ 24 (TES alone 17 vs 406 k).
* C4 — Location decides whether storage is hydraulic capacity: without new capacity the existing network serves
  +19 % additional south demand (of today's total); a TES at the prosumer site raises this to +20 % only, a TES of the
  same size at the south end to +30…35 % — at the price of ≈ 60 % of its market value (170–183 vs 445–456 kEUR/a).
  An energy-only model sees none of this.
* C5 — Prosumer economics: the HP on a 17 °C source needs 64–87 % investment support; partner B's value is set by the
  electricity-cost regime, with a premium window of 10–20 EUR/MWh.

## 2. Case study (anonymised; numbers from T1)

* Network **DHN-A**: meshed transmission network, 632 GWh/a feed-in incl. losses, peak 187 MW (2025, hourly, measured);
  measured supply temperature mean 99.9 °C (P95 113 °C). Plants (operator plan A): KWK (gas CHP, 127 MW, pressure
  holder), MVA (waste incineration, 45 MW), GT (35 MW), Bio-KWK (14.5 MW, must-run), HW1 (gas peak boiler, 40 MW, south);
  pump stations PS1 (south), PS2 (west); west network supplied via heat exchangers (export, sink).
* **Site S** on the east transport line, 1.25 km from the KWK busbar: TES 5 000 m³ pressurised, 120 °C max,
  T_low 67.5 °C, 40 MW, temperature classes 90–120 °C (5 K); new link DN 400 (v ≤ 2.5 m/s).
* **Partner A** (industrial site at S): four water-based waste-heat streams merged, 37.5 GWh/a; source temperature =
  hourly flow-weighted mix of the streams, 17.4 °C time mean (P95 23.9 °C; 20.9 °C weighted by available heat, 18.3 °C
  by the HP's source use — use 17.4 °C in the text, T1 shows all) (2023 data mapped weekday-preserving to 2025); one HP 5 MW_th (Carnot fraction 0.5, ΔT_app 5 K,
  COP ≈ 2), electricity at day-ahead + 38 EUR/MWh, waste-heat fee 5 EUR/MWh.
* **Partner B**: 10 MW spare electrode boiler, heat price c = (λ + c_el,var)/η + π, c_el,var 60 EUR/MWh (low case
  12), premium π = 10 EUR/MWh. Basis (literature check 7b): levy floor 11.4 + network charge 23.6 / 42.8 / 61.8 EUR/MWh
  (BNetzA monitoring 2025) → 35 / 54 / 73 EUR/MWh; 60 lies in the upper half (conservative for B); no demand charge,
  justified by atypical grid use (§ 19 (2) StromNEV) if the EB avoids the DSO's high-load windows (7 % of its energy falls
  in a typical winter-weekday 8–20 h window; demand charge case in A5).
* Prices 2025: DE-LU day-ahead (mean 89.3 EUR/MWh, 576 h < 0), gas 48 EUR/MWh, CO2 72 EUR/t.

## 3. Methods (detail: `model_and_deviations.md`)

**Energy layer.** Hourly MILP over one year (8 759 h), operator perspective, Pyomo + HiGHS 1.15 (MIP gap 0.1 %,
achieved ≤ 2·10⁻⁴). Existing plants as LP with marginal cost c_g,t = (p_fuel + EF·p_CO2)/η_th + τ_g − (η_el/η_th)·λ_t,
bounds from capacity, mass-flow limits m_max·Δh_t, east parallel-flow limit, MVA monthly availability, Bio-KWK
must-run. HP with four modes (grid, TES, cascade→grid, cascade→TES), exogenous Carnot-fraction COP, binary mode
exclusivity, source limit. EB under a heat-purchase contract. TES temperature classes: Σ_k E_k/e_k ≤ V,
e_k = ρc_p(T_k − T_low); network water charges class k only if T_VL ≥ T_k, class k discharges only if T_k ≥ T_VL;
HP/EB charge the 120 °C class; binary charge/discharge exclusivity; cyclic per class. Link |Q_central| ≤ ρ v A Δh.
Heat balance Σ_g Q_g + Q_central = D_t (measured feed-in incl. losses). Objective: operating cost (fuel, CO2,
energy tax, CHP power credit, HP electricity, waste-heat fee, partner-B heat purchase); in the hosting study, a
penalty on unserved heat of the new south customers (no new capacity).

**Hydraulic layer.** Calibrated meshed equivalent network (25 nodes, 31 edges, 7 meshes) of DHN-A, three calibration
variants A (reference), C, B; quadratic pipe law; KWK as pressure holder with Δp set to the minimum keeping V06
(south end) ≥ 1.2 bar and the city-centre stations ≥ 1.0 bar; PS1 may raise its head up to its pump curve. Hard limits:
pump curves (generic, scaled to the 2025 envelope), return pressure ≥ shutdown pressure, supply pressure ≤ PN25,
KWK net flow; soft limits reported (KWK 4.0 bar operator experience value, east plants 7.5 bar). Calibration quality:
`hydraulic_calibration.md` (high-load holdout RMSE 0.13–0.25 bar at city/east stations, 0.32 bar at V06).

**Coupling.** Mode E: energy-only schedule, hourly hydraulic validation (all calibrations), attribution test. Mode H:
linearised finite-difference cuts on all feed-ins added for violating hours, re-solve until no violation (k_max 10,
margin 0.02 bar). ΔC_hyd = C_H − C_E. Convergence: all runs at today's load (1–4 iterations); 13 of 23 expansion /
reinforcement runs; otherwise 1–8 h left (TES at S), cost change of the last iterations < 1 kEUR/a.

**Validation.** pandapipes cross-check of 90–114 hours per schedule (peak, violating, high central flow, random):
same friction law max 0.055 bar; Reynolds-dependent friction max 0.32 bar (P95 0.16 bar pooled).

**Attribution.** 2³ factorial {A, B, TES}; Shapley values in Mode E, Mode H and rolling horizon; TES interaction term.

**Rolling horizon.** 72 h window, 24 h commit; prices known up to the end of the delivery day (and of the next day
for decisions after the 12:00 auction), beyond the last known day repeated; demand forecast multiplicative noise σ 5 %
(drawn per window); partner A schedule known day-ahead (reference) or persistence; TES state handed over per
temperature class; tank starts empty, energy left at year end is not credited (conservative); realisation of the
existing plants by merit order. Robustness over seeds and σ: section 4.4.

**Economics.** Break-even investment I_max = annual value / annuity factor (5 %; TES 30 a, HP 20 a, pipe 40 a); cost
data from the literature check (TES 1 000 / 1 500 / 2 500 EUR/m³ + 0.1 M EUR; HP 0.95 M EUR/MW; pipe 3 000 EUR/m).

**South hosting capacity (author decision 2026-10-12: no new boiler).** New customers at the south nodes, +15 … +35 %
of today's annual demand (today's hourly shape; +19 % ≙ ≈ +100 % of the south load). No new capacity: heat that the
existing plants, pumps and PS1 head control cannot deliver within the hydraulic limits is unserved heat of the new
customers (penalty 1 000 EUR/MWh, ≤ their demand, withdrawn from the south nodes like their load). Hosting limit = last
growth level without unserved heat. Variants: no TES, TES at S (± partners), TES at the south end (V06; 5 000 m³ /
40 MW and 20 000 m³ / 80 MW); pump curves as hard limits (reference) and KWK Δp ≤ 4 bar. Values at equal delivered heat
(unserved heat charged at the HW1 heat cost, 72.6 EUR/MWh). Mode H with a south TES: anticipatory cuts (hours within
0.5 bar of a limit), ≤ 20 iterations. The earlier new-boiler and pipe-reinforcement runs are supplementary (T7b).

## 4. Results — key numbers (all k = kEUR/a; sources in brackets)

### 4.1 Value and attribution (fig1, T2–T4)
* Concept A + B + TES saves **544 k/a** (3.5 % of the operating cost); TES alone 406 k, A alone 99 k, B alone 32 k.
* Shapley (PF): TES 412 / A 100 / B 32 k; TES interaction 9.5 k → the TES is a stand-alone asset, not the enabler of
  the prosumers. Mode H gives the same split (±0.2 k).
* Rolling horizon: concept 324 k (59 %), persistence 311 k (57 %); Shapley TES 215 / A 88 / B 21 k → prosumer share
  24 % → **34 %**; the TES keeps 52 %, A 88 %, B 65 %. Price years 2023 / 2024: prosumer share 28 / 36 %.
* Mechanism (fig2): the TES is charged mainly from the network (19.0 GWh/a; HP 1.2, EB 0.4 GWh/a; 69 cycles), shifts
  KWK output to high power prices (price-weighted 109.8 → 117.6 EUR/MWh) and displaces HW1 (10.5 → 4.4 GWh/a);
  CO2 −4.1 %.

### 4.2 Prosumers (fig7, T6 PR/A4/A5)
* Partner A: U_A 6.3 % of the waste heat; unused heat falls in hours with the HP off (30.6 of 35.1 GWh) — the HP heat
  at COP ≈ 2 is dearer than MVA/Bio/KWK heat. Value of A 45–154 k over the variants (alone; 41–154 k with B + TES) (HP size 2.5–15 MW: 69–154 k;
  source +10 / +20 K: 119 / 146 k; Carnot fraction 0.4 / 0.6: 79 / 132 k; fee 0–20 EUR/MWh: 112–70 k; HP grid fee
  55 / 76 EUR/MWh: 69 / 45 k; waste heat × 0.5–1.25: 74–109 k; calendar shift ± 7 d: 96–98 k). The TES does not raise
  A's value (≤ 4.4 k).
* HP economics: justifiable 0.13–0.35 M EUR/MW vs 0.95 M EUR/MW cost → 64–87 % investment support needed at 17 °C
  (62 % with a +20 K source).
* Partner B over the literature cost range (BL, c_el,var 35 / 54 / 73 EUR/MWh; reference 60): Shapley B 117 / 46 / 18 k,
  concept 626 / 556 / 532 k, prosumer share 34 / 26 / 22 % → B's value is set by its electricity cost.
* Partner B: value 18 / 32 / 52 k for 5 / 10 / 20 MW; premium π: operator net saving 54 → 8 k for π = 0 → 60 EUR/MWh,
  partner revenue max 16.5 k at π = 10 → negotiation window 10–20 EUR/MWh; low electricity cost (12 EUR/MWh): B's
  value 244 k, concept 759 k; with a demand charge the EB is never used. The TES shifts B to lower prices
  (price-weighted −13.3 → −21.2 EUR/MWh) but raises B's value only for a 20 MW EB.

### 4.3 Hydraulics and pressure (fig3, fig5, fig6, T2, T7)
* Today: 3–8 violating hours (pump limits of MVA/GT), Mode H repairs them with |ΔC_hyd| ≤ 0.35 k for every scenario,
  size, DN and V06 limit (zero within solver tolerance) → no cost of hydraulic feasibility.
* Pressure footprint of the TES (F111 vs F000): required KWK Δp P95 2.54 → 2.91 bar; hours above 4 bar 30 → 109;
  flow reversals up to 848 h (KWK outlet), 777 h (mesh M12), 761 h (trunk L1a), south trunk 274–488 h. Under a hard
  4 bar limit this costs ≈ 8 k (X4).
* Footprint vs uncertainty: numerical deviation at V06 (sets the KWK Δp; the KWK Δp itself is an input of the pandapipes
  check) max 0.14 bar, mean +0.01 bar, bias difference F111 vs F000 0.002 bar — the 0.32 bar maximum is at S. Over the
  calibrations A / C / B the footprint is +0.37 / +0.21 / +0.13 bar (P95; no-asset P95 2.54 bar in all three), hours > 4 bar 30 → 109 / 72 / 62, charging
  hours +0.86 / +0.59 / +0.43 bar → sign robust, magnitude calibration-dependent (report the range).
* Sign of the KWK Δp change by TES state (F111 vs F000, Mode E, calibration A; added 2026-10-11): charging from
  the network (728 h, TES draws ≈ 158 kg/s at S, KWK +22 MW): KWK Δp +0.86 bar mean (P95 +2.08), hours > 4 bar 9 → 90;
  discharging (1 354 h, feed-in ≈ 77 kg/s at S): −0.16 bar mean, lower in 70 % of these hours, hours > 4 bar 4 → 2;
  idle 6 677 h: ± 0. → feed-in at S relieves the KWK (as in the prosumer literature); the footprint comes from the
  TES acting as a large consumer at S while charging. V06 (south end) binds in the > 4 bar hours.
* **South hosting capacity, no new capacity (fig5, T7; results §11):** unserved heat of the new customers (peak):
  no TES +19 % served, +20 % 2 MWh/a (1.1 MW), +22.5 % 29 MWh/a (5.2 MW), +25 % 132 MWh/a (9.3 MW), +30 % 1 039 MWh/a
  (18.3 MW), +35 % 4 035 MWh/a (27.7 MW); redispatch cost (Mode H − E; HW1 supplies the south locally) 0.25 / 0.48 /
  0.90 / 1.27 M EUR/a at +15 / 19 / 25 / 30 %. **Hosting limit: no TES +19 %, TES at S +20 % (+21 %: 3 MWh/a;
  +25 %: 97 MWh/a, 8.6 MW), TES in the south +30…35 %** (served up to +30 % with ≤ 0.27 bar residual in 4 h; +35 %:
  1 628 MWh/a, −60 %, peak 27 MW unchanged; 20 000 m³ / 80 MW: 429 MWh/a, peak unchanged). Partners A + B do not
  change the south hydraulics.
* Why: the KWK/MVA/GT pump curves bind (V06 sets the KWK Δp); a TES upstream (at S) cannot relieve the trunk, a TES at
  the south end charges in low-load hours and discharges locally at peak; it stops when cold spells outlast the tank
  (no recharge through the bottleneck).
* Value at equal delivered heat: TES at S 445–456 kEUR/a, TES in the south 170–183 kEUR/a → location trade-off between
  market value and grid value; required KWK Δp P95 7–8 bar at all growth levels.
* KWK Δp ≤ 4 bar as hard limit (operator rule): hosting limit no TES +13.5 %, TES at S ≈ +15 %, TES in the south
  +20…25 % (+25 %: 153 vs 1 531 MWh/a, −90 %) → same ranking, limits ≈ 5–10 pp lower (results §11a).
* Supplementary (T7b, "what new capacity would take", not part of current planning): south boiler 8.4 / 16.9 MW at
  +20 / 30 %; parallel pipe on the south trunk 113–432 kEUR/a dearer than the boiler.
* pandapipes: max 0.055 bar (same friction law), 0.32 bar (Reynolds-dependent; P95 0.16 bar).

### 4.4 Design and economics (fig4, T5, T6 A1–A3/AT)
* Energy before power: each doubling of energy at 40 MW +102…125 k; 40 → 80 MW +29 k at 5 000 m³ (+81 k at 20 000 m³);
  link binds only below DN 400 (DN 300 −13 k).
* Temperature handling: class model 406 k (TES alone) vs single-state fixed / monthly / daily 17 / 11 / 187 k and
  energy-only single state (no temperature limits) 1 017 k (A3e) → the single-state error has either sign (section 11).
* Break-even pressurised TES 5 000 m³ / 40 MW: **1 258 EUR/m³ (PF) → 647 EUR/m³ (RH)** vs 1 000–2 500 EUR/m³
  (reference 1 500); RH keeps 43–56 % over the size grid (the uncredited end-of-year storage, ≤ 376 MWh, biases large
  tanks by at most ≈ 27 k downwards).
* RH robustness: three noise seeds at σ 5 % give V_TES 212–214 k (reference 217 k) and a concept value of 319–324 k (324 k), i.e. −2 %…0 %; a worse demand forecast lowers the TES value strongly: σ 10 % 168 k (40 % of PF), σ 15 % 114 k (27 %) — forecast quality is a first-order driver of the realisable storage value.
* Atmospheric tank (≤ 95 °C, 40 MW): PF break-even 282 / 166 EUR/m³ (10 000 / 20 000 m³) vs DEA 177 / 143 EUR/m³ →
  economic under PF; under RH 135 / 86 EUR/m³ → not economic.
* Whole concept (TES 1 500 EUR/m³ + HP + link) annual capital cost 911 k vs value 544 k → not economic as a bundle;
  the HP is the uneconomic part.

### 4.4b Gas price (T6 PG / P)
* Gas 37 / 42 / 48 EUR/MWh: concept 477 / 503 / 544 k; Shapley TES 402 / 408 / 412 k, A 55 / 72 / 100 k, B 19 / 23 / 32 k
  (prosumer share 16 / 19 / 24 %); TES break-even 1 219 / 1 242 / 1 258 EUR/m³. Upwards (gas 58.6, CO2 100): concept
  758 k. → TES robust to the gas price; the prosumers' value roughly halves at the 2025 spot level.

### 4.5 Foresight decomposition (T4b; discussion in section 11)
* TES value under RH as share of PF: reference 52 %; perfect information 74 % (72 h) → 77 / 78 / 87 / 94 % (120 / 168 /
  336 / 720 h); perfect information + PF guide curve 85 %; realistic forecasts with 120 / 336 h 53 / 58 %; hourly
  re-planning 57 %; perfect prices 61 %; no demand noise 64 %; simple terminal value ± 0.

## 5. Hypotheses (for the discussion)

| H | Verdict | Evidence |
|---|---|---|
| H1 TES raises partner-A utilisation | not supported | U_A ± 0.1 pp; A's value with/without TES ≤ 4.4 k apart |
| H2 TES shifts EB to low prices | supported | price-weighted −12.5 → −19.0 / −13.3 → −21.2 EUR/MWh |
| H3 central feed-in shifts flows/stagnation points | supported (overload side) | reversals up to 848 h; KWK Δp P95 +0.37 bar |
| H4 ΔC_hyd > 0, depends on link capacity | partially | only with load growth (0.25–1.3 M EUR/a redispatch at +15…30 %); no DN dependence today |
| H8 (new) the TES raises the south hosting capacity | location-dependent | at S +19 → +20 %; in the south +19 → +30…35 % at ≈ 60 % lower market value |
| H5 power/link limit value more than energy | rejected | energy doubling +102–125 k vs power +29 k |
| H6 temperature strategy trade-off; cascade helps | trade-off yes, cascade no | U_A 7.6 → 8.3 % vs V_TES 17 → 11 k; cascade ≤ 0.3 k |
| H7 PF overstates TES value | supported | TES keeps 52 % under RH (74 % with perfect information, 72 h) |

## 6. Figures (files in `figures/`; notes in `paper_figures.md`)

| Paper fig. | File | Message |
|---|---|---|
| 1 | fig0_system_concept | network schematic + energy–hydraulic coupling (maintained by the author) |
| 2 | fig1_value_attribution | value of all combinations, Shapley split, PF vs RH |
| 3 | fig2_operation_week | how the layered TES and the partners operate in one week; heat flows at site S |
| 4 | fig7_prosumers | drivers of partner A and partner B, premium window, value split across foresight, price years and gas price |
| 5 | fig3_pressure_footprint | CHP Δp duration, Δp change by TES state, flow reversals |
| 6 | fig5_south_hosting | south hosting capacity without new capacity — TES at S vs in the south |
| 7 | fig6_hydraulic_validation | pandapipes cross-check (parity, binned deviation, per node) |
| 8 | fig4_break_even_investment | break-even TES investment PF vs RH (day-ahead forecasts), atmospheric alternative |

Figure system v2 (2026-10-16; details `paper_figures.md`): Latin Modern Roman (elsarticle Computer Modern), 190 mm,
PDF with embedded TrueType + 600 dpi PNG/TIFF. Colour roles: green = TES, orange = partner A, dark blue = partner B,
grey = reference without the asset, turquoise = other identities (TES in the south, atmospheric tank, Reynolds-dependent
model); temperature layers blue (90 °C) → deep red (120 °C). Plant labels in figures: CHP, WH, GT, BCHP, GB; “temperature
layer” (not class); no scenario codes. RH in Fig. 8 covers all assets — “partner-A schedule known” only means the
partner-A heat profile is forecast perfectly one day ahead.

## 7. Tables (in `paper_tables.md`)

T1 inputs and assumptions → paper Table 1; T2 factorial + T3 Shapley → Table 2; T4 foresight → Table 3 (or text);
T5 size × power with PF/RH break-even → Table 4 or SI; T6 sensitivities → SI; T7 south hosting capacity → Table 5 (or
text); T7b new-capacity runs → SI.

## 8. Limitations to state

* One year (2025 weather, demand and prices); price years 2023/2024 change prices only (weather–price link lost).
* Partner-A data 2023 mapped to 2025 (± 7 d shift changes A's value by ≤ 4 %); daily stream spread evenly.
* Exogenous supply/return temperatures; TES class model without mixing/thermocline; T_low = P95 of the return.
* Existing plants as LP without minimum loads/unit commitment; CHP power credited at the day-ahead price.
* HP: Carnot-fraction COP, 97 % of HP heat at lifts > 70 K (two-stage HP implied), single-stage cost data.
* Demand = measured feed-in incl. losses and the west export; new south customers use today's hourly shape.
* Hosting study: unserved heat as a penalised slack (not an economic value of lost load); Mode H with a TES in the south
  needs anticipatory cuts and ≤ 20 iterations, residual ≤ 0.27 bar in ≤ 4 h at +30 / 35 % (marked in fig5); perfect
  foresight (a south TES under rolling horizon would bridge less).
* Rolling horizon: merit-order realisation not re-validated hydraulically; i.i.d. hourly demand noise (robustness 4.4);
  24 h commitment of the central decisions (hourly re-planning +5 pp, T4b); window 72 h (longer windows: T4b).
* PS1 head control (operator lever) is part of the hydraulic control; the 4 bar KWK value is an operator experience
  value without a literature source.
* Hydraulic validation = model vs pandapipes (code-to-code) plus the calibration holdout vs measurements; V06 holdout
  RMSE 0.32 bar with weak correlation (r 0.18); pressure footprint magnitude depends on the calibration variant (×2–3).
* Gas price 48 EUR/MWh (2025 forward-based); at the 2025 spot level (≈ 37) the prosumer value falls by ≈ 45 % (PG).

## 9. Literature (verify editions; details and URLs in `literature_check.md`)

Jesper et al. 2021 (RSER 137, 110646) — large HP COP; David et al. 2017 (Energies 10, 578) — large HPs in DH;
Arpagaus et al. 2018 (Energy 152, 985–1010) — high-temperature HPs; AEE INTEC 2024 — pressurised DH storage;
Gülich, *Centrifugal Pumps* — pump curves; Danish Energy Agency technology catalogues (heat generation, storage,
energy transport) — costs; BNetzA/SMARD via energy-charts — prices; EEX — gas and EUA; 2025 DSO price sheets / §19
StromNEV / StromStG / EnFG — grid fees and levies; pandapipes (Lohmeier et al. 2020, Sustainability 12, 9899).

## 10. Rules for the writing session

* Anonymity: network "DHN-A", "the operator", plants CHP, WH, GT, BCHP, GB (earlier KWK, MVA, GT, Bio-KWK, HW1), HW2, PS1, PS2, stations V01–V24,
  site S, "partner A", "partner B". Never use real names of the city, network, operator, partners, plants or streets
  in text, figures, file names or metadata.
* Do not quote the authors' Paper 2 network-specific numbers; Paper 1 (loss visibility) and Paper 2 (TES sizing) are
  cited as related work only.
* No new results in the writing session: every number comes from `paper_tables.md` / `results_v2.md`.
* Author decisions 2026-10-12: partner B's cost regime and the hydraulic limits rest on literature / regulatory values
  (literature check 7b, 10); the KWK 4 bar value is stated as the operator's experience value (no generic literature
  value exists; soft threshold only); the anonymised network schematic is approved. Optional partner-A profile figure
  not planned.

## 11. Contrasts to the literature (discussion; numbers in `results_v2.md` §10 and T4b)

1. **Foresight (TES keeps 52 % here vs 85–97 % in the literature; nearest DH case ≈ 90 % with a 5-day window).**
   The literature figures refer to perfect forecasts with a finite window. Our comparable case (perfect prices, demand
   and partner A) gives 74 % (72 h), 77 % (120 h), 78 % (168 h), 87 % (336 h) and 94 % (720 h): the model reaches the
   literature range, but only with windows of two weeks and more. Reason: the temperature classes make the tank a
   multi-day to multi-week store (water charged at a high supply temperature is discharged only when the supply
   temperature falls below its class); in PF the tank holds 39 % of its capacity on average. A PF guide curve as end
   target recovers 74 → 85 %; a simple terminal value (mean marginal heat cost of the next week) recovers nothing.
   Realistic forecasts cost another 22 pp (74 → 52 %): demand noise ≈ 10 pp, price forecast ≈ 9 pp; hourly
   re-planning instead of a 24 h commitment +5 pp. The writer's three candidates, quantified: window 72 → 120 h +1 pp
   (realistic) / +3 pp (perfect information); price extrapolation +9 pp; terminal value 0 pp (heuristic) to +5 / +11 pp
   (ideal guide curve). Message: the realisable value is governed by forecast quality and by the temperature-driven
   storage timing that short windows cannot see.
2. **Single-state storage model (underestimates here; overestimation in another recent study; both signs in one
   earlier study).** The sign depends on the temperature assumption of the single-state model: energy-only (no
   temperature limits, 120 °C capacity) 1 017 k > temperature classes 406 k > single state with daily / fixed set
   temperature 187 / 17 k (TES alone, PF). Energy-only books 95–105 °C network water at 120 °C energy density and
   discharges into a hotter supply → overestimate; a fixed 120 °C set temperature lets the network charge in only 43 h/a
   (median supply 96 °C) → underestimate. Check how the cited studies define their single-node model before writing
   which rung they correspond to.
3. **Δp at feed-in (KWK Δp rises here; local relief by a prosumer in the literature).** Not a contradiction. Pressure
   holding (static level) is at one point, the KWK, as in any network; differential pressure comes from several pumps
   (KWK as Δp master for the worst-point stations V06/city centre, feed-in pumps of MVA, GT, Bio-KWK, HW1, booster
   stations PS1 south with head control and PS2 west with measured head). The sign follows the flow direction at S:
   discharge (feed-in, 1 354 h) lowers the KWK Δp by 0.16 bar on average (hours > 4 bar 4 → 2); charging from the
   network (728 h, the tank acts as a 158 kg/s consumer) raises it by 0.86 bar (hours > 4 bar 9 → 90). The annual
   footprint is a charging effect of a tank filled mainly from the network (19.0 of 20.6 GWh/a).
