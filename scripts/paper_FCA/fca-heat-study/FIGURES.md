# FIGURES — what the paper needs

Every coded figure exists and runs (F1–F20 incl. F2b). Only F0, a hand-drawn system schematic,
remains. This file is the specification for all of them.

**Rules for every figure.** Written to `results/figures/<name>.html` and `.svg` by `show()`.
Arial, plotly_white, no chartjunk, colour-blind-safe. Regime colours from
`figures.FCA_COLOR`, storage configurations from `figures.SCEN_COLOR` — never hard-code a colour
in a new figure. Every figure must be readable in greyscale: if two series are only distinguished
by hue, add a dash pattern or a marker.

---

## Built and working

| ID | Function | Shows | Supports the claim | Paper |
|---|---|---|---|---|
| F1 | `fig_demand_overview` | monthly mean electricity and heat, five sites | the sites are genuinely different | §3 |
| F2 | `fig_duration_curves` | load duration curves, electricity and heat | introduces load factor as the organising variable | §3 |
| **F2b** | `fig_archetype_scatter` | load factor × heat-to-power, marker area = annual heat | **go/no-go: do the sites span the design space or cluster?** | §3 |
| **F3** | `fig_limit_profile` | $P_\text{limit}(t)$ per regime over one week, demand behind it | **the reader's entry point — the paper is unreadable without it** | §4.1 |
| **F4** | `fig_feasibility_matrix` | unserved heat, storage configuration × regime | the feasibility boundary | §4.4 |
| **F5** | `fig_storage_vs_regime` | TES and BES size by regime | **the headline: restriction structure sets storage size** | §4.3 |
| F6 | `fig_dispatch` | one winter week, three panels, restriction windows shaded | how it actually operates; shows pre-charging | §4.5 |
| F7 | `fig_grid_duration` | grid draw duration curve per regime | where the limit binds | §4.5 |
| F8 | `fig_kpi_comparison` | TES / LCOH / peak / unserved across sites | cross-site consistency | §4.3 |
| F9 | `fig_cost_stack` | CAPEX vs energy vs capacity charge | where the money goes | §4.6 |
| F10 | `fig_tornado` | one-at-a-time sensitivity | robustness | §4.10 |
| F12 | `fig_notice_value` | foresight gap at 0.25 h vs 24 h notice | notification interval as a contract lever | §4.9 |
| F16 | `fig_shadow_price` | connection-constraint dual, duration curve + monthly mean | EUR/MW value of capacity — practitioner-facing | §4.6 |
| **F11** | `fig_contract_space` | width × β grid, feasibility shaded + TES contour, faceted | **practitioner output / graphical abstract: which agreements a design can live with** | §4.8 |
| F13 | `fig_restriction_bite` | reserved vs binding restriction share per regime | the negotiating argument: capacity reserved but never needed | §4.4 |
| F14 | `fig_block_length_vs_storage` | longest recurring restricted block × required TES | **mechanism: block length, not total hours, sets storage** | §4.3 |
| F19 | `fig_seed_robustness` | required TES over 10–20 call seeds, box per dynamic regime | makes the dynamic-regime results defensible | §4.10 |
| F15 | `fig_sensitivity_grid` | two-way heat map (TES CAPEX × price spread), BES share | boundary where BES stops losing to TES | §4.10 |
| F17 | `fig_hp_eb_split` | HP vs EB heat, sites ordered by supply temperature | justifies the 160 °C HP admissibility gate | §4.5 |
| F18 | `fig_co2_accounting` | certificate CO₂ vs physical CO₂, baseline + configs | makes the biomethane assumption visible | §4.7 |
| F20 | `fig_year_validation` | fixed design operated over all years, unserved/peak | out-of-sample: sizing-year robustness | §4.9 |

## To build

### F0 · System schematic
Hand-drawn (draw.io / Inkscape), not code. Site boundary, grid connection with the time-varying
limit, heat pump, electrode boiler, TES, BES, heat network, gas boiler greyed out. Mark where
$P_\text{limit}(t)$ acts. Every energy-system paper has one and reviewers look for it.

---

## Figure order in the manuscript

F0 schematic → F1, F2, F2b (case studies) → **F3** (what an agreement is) → F4 (feasibility) →
**F5** (headline) → F13, F14 (why) → F6, F7 (operation) → F17 (technology split) → F9, F16
(economics) → F18 (carbon) → **F11** (contract space) → F12, F20 (operation under uncertainty) →
F10, F15, F19 (sensitivity and robustness).

Graphical abstract: **F11**, simplified to one site.

## Figures deliberately not built

* Sankey diagrams of energy flow — pretty, uninformative here.
* Per-site cost waterfalls — F9 covers it.
* Monthly storage utilisation heat maps — interesting in exploration, doesn't support a claim.

If a figure doesn't map to a row in the claims table of `docs/05_manuscript_draft.md`, it belongs
in the appendix or nowhere.
