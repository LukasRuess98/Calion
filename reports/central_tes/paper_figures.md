# Paper figures — central TES study (Elsevier *Energy* format), figure system v2 (2026-10-16)

Script: `python -m scripts.dhn_study.central_tes.paper_figures` → `results/central_tes/paper_figures/` (local, gitignored).
Each figure as vector PDF (TrueType fonts embedded), 600 dpi PNG and 600 dpi LZW-TIFF. Widths: double column 190 mm;
8 pt labels / 7.5 pt ticks at print size.

**Typeface.** Latin Modern Roman 10 — the Computer Modern of the elsarticle LaTeX class — with maths in Computer Modern.
The OpenType files of the local TeX installation are converted once to TrueType into `results/central_tes/.fontcache`
(local cache under a separate family name, never distributed); without TeX fonts the script falls back to matplotlib's
bundled Computer Modern.

**Colours (fixed roles, institute corporate palette).** TES green #179C7D (tint #CFE8E1 hatched = rolling horizon or
charging), partner A orange #F58220, partner B dark blue #005B7F, reference without the asset grey #A3A9AD, other
identities turquoise #1C8FA0 (TES at the south end, atmospheric tank, Reynolds-dependent friction). Temperature layers
90 → 120 °C from blue #2C6FB7 to deep red #9B1B1E, hot layers stacked on top. Boxed axes, inward ticks, light grid.

**Labels.** Plants CHP (gas CHP), WH (waste incineration), GT, BCHP (biomass CHP), GB (gas peak boiler, south); HW2, PS1,
PS2, V01–V24, site S, partner A / B unchanged. No scenario codes (F000 … F111) in any figure: “no TES, no partners”,
“TES + partners A, B”, “vs. reference”. Units k€/a, M€/a, €/MWh, €/m³, MW, MWh, bar, h/a.

**Paper order.** fig0 → Fig. 1, fig1 → Fig. 2, fig2 → Fig. 3, fig7 → Fig. 4, fig3 → Fig. 5, fig5 → Fig. 6, fig6 → Fig. 7,
fig4 → Fig. 8. fig0 (system concept) is maintained by the author.

| Paper | file | size | content | key numbers shown |
|---|---|---|---|---|
| Fig. 1 | fig0_system_concept | 190 × 92 mm | network schematic and energy–hydraulic coupling (author's version) | – |
| Fig. 2 (proposed: drop, duplicates Table 4) | fig1_value_attribution | 190 × 64 mm | (a) annual saving of the seven asset combinations vs. the reference without TES and partners; (b) Shapley split with shares; (c) TES + A + B (vs. reference) and TES (vs. A + B), perfect foresight vs. rolling horizon (RH share inside the hatched bar) | 406 / 544 k€/a; Shapley 412 / 100 / 32 (76 / 18 / 6 %); RH 324 (59 %), TES 416 → 217 (52 %) |
| Fig. 3 | fig2_operation_week | 190 × 140 mm | week 17–23 Mar 2025 (TES + A + B, Mode E), condensed to four panels: (a) day-ahead price, (b) stored energy per temperature layer with the supply temperature on the right axis, (c) TES discharge (+) and charge (−) by source (network, HP of partner A, EB of partner B), (d) GCHP heat with TES + partners (green, background) vs. without (transparent grey); hours with price ≤ 0 shaded. Partner heat delivered directly to the network is not shown (Fig. 4, Section 4.2) | week: discharge 1 107 MWh, charge 895 MWh from the network and 98 MWh from the partners (all on the weekend, 120 °C layer); GCHP output shifted to price peaks |
| Fig. 4 | fig7_prosumers | 190 × 122 mm | (a) partner A, (b) partner B: value alone over their drivers (band = range, dots = settings, line = reference); (c) partner-B premium window. The Shapley split across PF / RH / price years / gas price is text + Table 4 only (2026-10-20) | A ref. 99 (45–154); B ref. 32 (0–117; 237 at 12 €/MWh); window 10–20 €/MWh |
| Fig. 5 | fig3_pressure_footprint | 190 × 72 mm | (a) duration curves of the required GCHP Δp, no TES vs. TES + A + B, hours above 4 bar; (b) mean change of the GCHP Δp by TES state (bar: calibration A, whiskers: A, B, C). Reversed flows per pipe: text only (2026-10-20) | > 4 bar 30 → 109 h; charging +0.86, discharging −0.16, idle 0.00 bar |
| Fig. 6 | fig5_south_hosting | 190 × 80 mm | south hosting capacity without new capacity: (a) peak heat not deliverable to new customers (pump-curve limits, boxed hosting limits); (b) redispatch cost. GCHP ≤ 4 bar limits and TES values at equal heat: Table 5 only (2026-10-20) | +19 / +20 / +30 % (no TES / TES at S / TES in the south); redispatch 0.25–1.6 M€/a |
| Fig. 7 | fig6_hydraulic_validation | 190 × 72 mm | (a) deviation pandapipes − model: binned median and P5–P95 band per friction law; (b) |deviation| per node (P95 bar, max tick), Reynolds-dependent friction. Parity plot dropped (2026-10-20) | same law max 0.05 bar; Reynolds-dependent max 0.32 bar at site S, V06 P95 ≈ 0.10 bar |
| Fig. 8 | fig4_break_even_investment | 190 × 76 mm | break-even specific TES investment vs. volume and power against the pressurised-tank cost range: (a) perfect foresight with the atmospheric tank and its DEA cost, (b) rolling horizon (day-ahead forecasts; all assets, partner-A heat profile known one day ahead) with the PF → RH drop of the reference TES | 1 258 → 647 €/m³ (−49 %); atmospheric 282 / 166 vs DEA 177 / 143 €/m³ |

Not included on purpose: the new-boiler and pipe-reinforcement runs (not part of current planning; T7b), the electric boiler
at the CHP (not in plan A) and the spec single-state TES model (one sentence in the text).
