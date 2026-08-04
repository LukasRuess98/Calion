# FIGURES — what the paper needs

Eleven figures exist and run. Nine are missing. This file is the specification for both.

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
| **F3** | `fig_limit_profile` | $P_\text{limit}(t)$ per regime over one week, demand behind it | **the reader's entry point — the paper is unreadable without it** | §4.1 |
| **F4** | `fig_feasibility_matrix` | unserved heat, storage configuration × regime | the feasibility boundary | §4.4 |
| **F5** | `fig_storage_vs_regime` | TES and BES size by regime | **the headline: restriction structure sets storage size** | §4.3 |
| F6 | `fig_dispatch` | one winter week, three panels, restriction windows shaded | how it actually operates; shows pre-charging | §4.5 |
| F7 | `fig_grid_duration` | grid draw duration curve per regime | where the limit binds | §4.5 |
| F8 | `fig_kpi_comparison` | TES / LCOH / peak / unserved across sites | cross-site consistency | §4.3 |
| F9 | `fig_cost_stack` | CAPEX vs energy vs capacity charge | where the money goes | §4.6 |
| F10 | `fig_tornado` | one-at-a-time sensitivity | robustness | §4.10 |
| F12 | `fig_notice_value` | foresight gap at 0.25 h vs 24 h notice | notification interval as a contract lever | §4.9 |

## To build — in priority order

### F2b · Archetype scatter — `fig_archetype_scatter(inp)`
Load factor (x) against heat-to-power ratio (y), one marker per site, marker size = annual heat
demand, annotated with sector. **Build this first and run it the moment real data lands.** If the
five sites cluster, the multi-site framing collapses and the paper must be restructured around one
site with a parameter sweep. Ten minutes of work that can save a month.
Goes in §3, immediately after Table 2.

### F11 · Contract-space map — `fig_contract_space(inp, site, scenario)`
Two-dimensional sweep: restriction width per working day (x, 0–16 h) against granted uplift
$\beta$ (y, 1.0–2.0). Shade each cell by feasibility, and overlay a contour of required TES size.
One panel per site, or a 2×3 facet.

This is the **practitioner-facing output and the graphical-abstract candidate**. It answers the
question a plant actually asks — *which agreements can I live with?* — rather than returning one
sizing number. Implement by looping `solve_case` over the grid with
`overrides={"fca.window_width": w, "fca.P_flex_rel": b}`; both handles already exist. Roughly
8×6 = 48 solves per site at 1 h resolution, a few minutes each.

### F13 · Restriction bite — `fig_restriction_bite(kpi)`
Grouped bars per regime: `restricted_share` (what the operator reserves) against
`restriction_bite_share` (what actually constrains the plant). The gap is capacity reserved but
never needed.

This carries the negotiating argument and it is a new KPI, so it needs its own figure. Current
placeholder numbers: the window regime reserves 27.8 % and binds in 93.7 % of it; the 85/15
dynamic regime reserves 15.1 % and binds in 7.1 %.

### F14 · Why windows cost more — `fig_block_length_vs_storage(inp, site)`
Longest recurring restricted block (x, hours) against required TES (y), one point per regime,
plus a fitted line. **This is the mechanism figure for the paper's most surprising result** — that
a predictable daily window is more expensive than an unpredictable dynamic regime restricting more
hours in total. Without this figure that result looks like an artefact; with it, it looks like
physics. Compute block length from the `restricted` mask with `figures._blocks`.

### F15 · Two-way sensitivity — `fig_sensitivity_grid(inp, site, param_a, param_b)`
Heat map. The pair that matters: TES CAPEX against day-ahead price spread — the boundary where
BES stops losing to TES. Second pair worth running: `fca.netzentgelt_discount` against
`ECON.grid_reinforcement_EUR_per_MW`, i.e. when accepting an agreement beats paying for copper.

### F16 · Value of connection capacity — `fig_shadow_price(inp, site)`
Dual variable of the connection constraint, as a duration curve and as a monthly mean, in
EUR/MW. Nearly free to extract — set `m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)` before
solving and read `m.dual[m.fca_lim[t]]`. Answers "what would this plant pay to jump the queue?"
and "what should the operator charge for firm capacity?" — likely the most-cited figure for a
practitioner readership.

### F17 · Technology split by temperature — `fig_hp_eb_split(kpi, inp)`
Stacked bars of heat supplied by heat pump versus electrode boiler, sites ordered by supply
temperature, with the 160 °C admissibility threshold marked. Shows why the high-temperature sites
behave differently and justifies `HP.T_sink_max_C`.

### F18 · Two carbon accountings — `fig_co2_accounting(kpi)`
`CO2_cert_t` against `CO2_phys_t` for the baseline and each configuration. Makes the biomethane
certificate assumption visible instead of buried, which is the honest way to present it and
pre-empts the obvious reviewer objection.

### F19 · Call-pattern robustness — `fig_seed_robustness(inp, site)`
Box plot of required TES over 10–20 seeds of `_dynamic_calls`. The dynamic-regime results rest on
a price-percentile proxy for operator calls; this figure is what makes them defensible. **Do not
submit the dynamic results without it.**

### F20 · Design year versus operation years — `fig_year_validation(kpi_design, kpi_operation)`
Sizes fixed from the design year via `Case.fixed_sizes`, operated over the other two years.
Unserved energy and peak per year. Answers the reviewer question "what if you had sized on a
different year?"

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
