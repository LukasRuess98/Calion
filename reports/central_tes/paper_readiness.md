# Paper readiness — study design vs. results (2026-10-09)

Results checked against the study design (specification v2 §1, §7–§9, §14–§15; local decisions) after the author
decisions of 2026-10-09: deviations D1–D16 approved, prosumers are a main part of the paper, Priority-B
sensitivities, pipe reinforcement and a literature check of the cost data added. Numbers: `results_v2.md`, generated
tables `paper_tables.md`, figures `paper_figures.md` (fig0–fig7), cost sources `literature_check.md`. TES at site S =
station of partner A, next to partner B.

## 1. Verdict

All research questions, all Priority-A and Priority-B experiments and the author additions (south expansion,
reinforcement, prosumer sensitivities, atmospheric-tank comparison, full factorial under rolling horizon) are done;
every hypothesis has a tested answer; all figures are available, including the system concept (fig0) and a prosumer
figure (fig7). Remaining author items (section 8) do not block writing.

## 2. Proposed storyline (prosumers as a main part)

**A central TES at an industrial prosumer site: value, attribution between storage and prosumers, and the hydraulic,
foresight and investment limits.**

1. Concept and method (fig0): multi-feed-in network, site S with partner A (waste heat + HP) and partner B (EB),
   energy MILP with temperature-class TES coupled to a calibrated meshed hydraulic model, validated with pandapipes (fig6).
2. Value and attribution (fig1): 544 k EUR/a; Shapley TES 412 / A 100 / B 32 k; prosumers 24 % (PF) → 34 % (RH).
3. Operation at the prosumer site (fig2): network water charges the class matching the supply temperature; the
   partners charge the 120 °C class at low prices; KWK output moves to price peaks.
4. Prosumer integration (fig7): what drives partner A (HP size, source temperature, fees, grid fee) and partner B
   (EB size, electricity-cost regime, premium window); attribution robust over foresight and price years.
5. Pressure footprint (fig3) and south hosting capacity (fig5; author decision 2026-10-12: no new boiler): today no cost
   but more KWK head and flow reversals; without new capacity the network serves +19 % more south demand, a TES at S
   +20 %, a TES at the south end +30…35 % (at ≈ 60 % lower market value).
6. Economics (fig4): break-even investment PF vs RH; pressurised vs atmospheric tank; HP support need.

## 3. Research questions

| RQ | Answer (short) | Evidence |
|---|---|---|
| RQ1 value and attribution | 544 k EUR/a (3.5 % of operating cost); Shapley TES 412 / A 100 / B 32 k; under RH 215 / 88 / 21 k (prosumer share 24 → 34 %); price years 2023/2024: prosumer share 28 / 36 % | fig1, fig7c, T2–T4, T6 (B2) |
| RQ2 hydraulic feasibility | today ≈ 100 % survives (|ΔC_hyd| ≤ 0.35 k for all scenarios, DN, sizes, V06 limits); the gap appears with load growth at the south end (redispatch 0.25 / 0.48 / 0.90 / 1.27 M EUR/a at +15/19/25/30 %, hosting limit +19 % without new capacity; fig5), not at the central feed-in; the TES leaves a pressure footprint (KWK > 4 bar 30 → 109 h, ≈ 8 k under a hard 4 bar limit) | fig3, fig5, fig6, T2, T7 |
| RQ3 design drivers | energy capacity before power (power saturates once τ ≲ 4–7 h); link binds only below DN 400; temperature handling dominates (class model 406 k vs single-state 11–187 k); prosumer value driven by HP size, source temperature and electricity-cost regime, not by the TES | fig4, fig7, T5, T6 |
| RQ4 economic thresholds | pressurised TES break-even 1 258 EUR/m³ (PF) / 647 EUR/m³ (RH) for 5 000 m³ vs 1 000–2 500 EUR/m³ cost; atmospheric tank 282 / 166 EUR/m³ (10 000 / 20 000 m³, PF; RH 135 / 86) vs ≈ 177 / ≈ 143; HP 0.13–0.35 M EUR/MW at the 17 °C source vs 0.95 (64–87 % support needed; 0.36 with a +20 K source); link: enabling investment of 0.6 M EUR (35 k EUR/a), small against every asset value; partner-B premium: revenue maximum at ≈ 10 EUR/MWh, window 10–20 EUR/MWh, spec break-even premium > 60 EUR/MWh | fig4, fig7b, T5, T6 |

## 4. Hypotheses

| H | Verdict | Numbers |
|---|---|---|
| H1 TES raises partner-A utilisation | **not supported** | U_A changes by ±0.1 pp with the TES; A's value alone ≈ with B + TES in every prosumer variant (≤ 4.4 k apart); unused heat falls in hours with the HP off (30.6 of 35.1 GWh) |
| H2 TES shifts partner-B EB to low prices | **supported** | price-weighted −12.5 → −19.0 EUR/MWh (F010 → F011), −13.3 → −21.2 (F110 → F111); EB heat lower (2.31 → 2.10; with A 2.03 → 1.65 GWh); the TES raises B's value only for a 20 MW EB (+5 k) |
| H3 central feed-in shifts flows; relieves or overloads | **supported (overload side)** | reversals up to 848 h (KWK outlet), 777 h (M12), 761 h (L1a), south trunk 274–488 h; KWK Δp P95 2.54 → 2.91 bar |
| H4 ΔC_hyd > 0, depends on connection capacity | **partially supported**: ΔC_hyd > 0 only with load growth; no dependence on the link DN (tested today) | today |ΔC_hyd| ≤ 0.35 k for DN 300–500, all sizes, V06 1.0–1.4 bar; hosting study: 0.25 → 1.27 M EUR/a redispatch at +15 → +30 %; a south TES raises the hosting limit to +30…35 % (new H8) |
| H5 power and link limit value more than energy | **rejected** | each doubling of energy at 40 MW +102…125 k; 40 → 80 MW +29 k at 5 000 m³ (+81 k at 20 000 m³); DN 300 −13 k, DN ≥ 400 no effect |
| H6 temperature strategy trade-off; cascade weakens it | **trade-off confirmed, cascade irrelevant** | lower T_set raises U_A (7.6 → 8.3 %) but lowers V_TES (17 → 11 k); class model 406 k; cascade ≤ 0.3 k; a +20 K warmer source raises A's value by 47 % |
| H7 PF overstates the TES value | **supported, strongly** | RH keeps 59 % of the concept, 52 % of the TES (43–56 % over A1; −2…0 % over noise seeds; 40 / 27 % with σ 10 / 15 %), 88 % of A and 65 % of B; decomposition: perfect information 74 % (72 h) – 87 % (336 h), forecast errors and 24 h commitment explain the rest |

## 5. Design of experiments (spec §7)

| Item | Status |
|---|---|
| 2³ factorial E + H, Shapley E and H, interaction terms | ✓ (T2, T3) |
| Foresight: F111 RH E/H, two partner-A forecast modes | ✓ + all eight scenarios under RH, Shapley under RH, A1 grid under RH (T4, T5) |
| A1 energy × power | ✓ 14 of 16 grid points (2 extreme-τ points left out) + V0; E, H and RH |
| A2 DN, A3 temperature strategy, A4 premium, A5 cost regime, A6 cascade | ✓ (T6) |
| B1 partner-A availability, B2 price year, B3 η_C, B4 V06 limit | ✓ (approved 2026-10-09; T6) |
| Author additions | south hosting capacity (no new capacity; TES at S vs south; pump curves vs KWK 4 bar), supplementary south expansion with boiler X/X4 and reinforcement XR, prosumer set PR (HP size, source temperature, EB size, HP grid fee), partner-A calendar shift PS, RH robustness (seeds, σ), atmospheric tank AT, prices/model variants P, pandapipes cross-check |

## 6. Metrics and sanity check (spec §8, §14)

All §8 metrics are in `annual_metrics.json`; physical feasibility loss E → H is nil (HP −0.008, EB +0.008 GWh);
σ_A 0.059, ψ_central 0.040, κ_link 0.39, τ 7.4 h; pump electricity F000 → F111: KWK 226 → 256 MWh/a, new pump at S
75 MWh/a, HW1 23 → 9 MWh/a; saturation margin ≥ 8.4 bar; link velocity ≤ 2.5 m/s. Sanity answers (§14): see
`results_v2.md` sections 1–6 and the hypotheses above; the τ × κ_link map collapses to τ (κ_link not binding ≥ 0.39),
stated explicitly.

## 7. Changes applied on 2026-10-09

* Deviations D1–D16 approved; D17 (literature cost update), D18 (prosumer and Priority-B sets), D19 (reinforcement).
* Cost data: HP 0.95 M EUR/MW, pressurised TES 1 000 / 1 500 / 2 500 EUR/m³, pipe 3 000 EUR/m, partner-B low
  electricity cost 12 EUR/MWh (A5 re-run), HP grid fee sensitivity 55 / 76 EUR/MWh.
* Figures: fig0 system concept, fig7 prosumers, fig4 with the new cost band and the atmospheric tank.
* Methods statement on Mode H convergence (`model_and_deviations.md`).

## 8. Remaining author items (not blocking)

1. Done 2026-10-12: partner B's cost regime on literature basis (BL range 35–73 EUR/MWh); KWK 4 bar stated as the operator's experience value (no generic literature value); network schematic approved.
2. Optional data-context figure with partner A's anonymised waste-heat profile — needs partner A's consent.
3. Cite the cost sources from `literature_check.md` in the reference manager (DEA editions of 2025/2026).
4. Limitations to state: same hourly shape for new customers; 2023 partner-A data mapped to 2025; demand includes
   losses; Mode H not fully converged in 10 of 23 expansion/reinforcement runs (≤ 8 h left for TES at S); atmospheric
   tank modelled with the same class logic (≤ 95 °C).
