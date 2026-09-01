# Paper 2 — Publication Figure & Table Redesign

Design spec for the reworked paper (framework + electrification spine + two
demonstrators). **Designs are fixed here; numbers fill in after the tight-gap
re-run.** Colour system: Memmingen = FHG blue, Stadtbach = FHG green (entity
identity); cost components = Paper-1 palette (navy/teal/amber); temperature = red.
All static matplotlib → PDF+SVG+PNG, els-cas double-column.

## Figures (7 main + 3 supplement)

| # | Title | Form | §  | Status / redesign |
|---|---|---|---|---|
| **F1** | *(dropped)* | — | 2 | Equations in text. |
| **F2** | Two networks | 2-panel node-link map | 3 | User replacing. Add a shared legend; mark producer / WP / TES-candidate nodes. |
| **F-ELEC** | **Electrification spine (NEW centrepiece)** | 2×2 small-multiple per network | 4 | Cost (TAC & LCOH), CO₂, annual COP, TES built — all vs HP penetration [% of peak]. Mark the endogenous optimum penetration. THE figure of the paper. |
| **F4** | Heat-curve → COP → cost | 2-panel (physics / economics) | 4 | Keep the new trajectory; add the ±gap band so the electrification-dependence isn't read as noise. |
| **F5** | Cost & CO₂ vs baseline | stacked bar, 2-panel | 4 | Keep (Paper-1 colours). Add a CO₂ panel twin so emissions aren't buried. |
| **F6** | Siting landscape | enumeration heatmap, 2-panel | 5 | Keep (star = optimum, "worst N× best"). Consider a small network inset marking the optimum node. |
| **F7** | Sensitivity tornado | diverging bars, 2-panel | 6 | Upgrade tier-1 → **tier-2 re-dispatch** (captures the SB net-exporter elec sign properly); keep split teal/amber + value labels. |
| **F9** | Storage cycling | line, fixed-vs-endogenous | 5 | Keep; annotate cycles/utilisation. Supplement-or-main by space. |
| S1 (F3) | Capacity–cost surface | heatmap | supp | Cross-validation only. |
| S2 (F8) | Spatial T/p profile | 2-row line | supp | Temp red; **caption caveat: pressure saturates at 20 bar (ceiling artifact)**. |
| S3 | Teil-6 pump comparison | 2-panel | supp | Central vs decentral pump. |

## Tables

| # | Title | Redesign |
|---|---|---|
| **T1** | Network characteristics | Keep (peaks, length, topology, supply temp). |
| **T2** | **Experimental design (rebuilt)** | Factors × levels: {electrification level} × {HK stage} × {TES location} × {charging} × {siting freedom}, defined *identically* per network. Replaces the ad-hoc S0–S7 list; state which study each block feeds (A–E). |
| **T3 / T4** | Scenario KPIs (SB / MM) | Keep + `V_TES [m³]`; **add a `MIP gap [%]` column** (report every scenario's gap). Move the full 46-row versions to supplement; headline subset in main. |
| **T-GAP** | **MIP-gap & method (NEW)** | Per study: solver settings, grid-cap, final gaps (median/max), solve time. Demonstrates the tight-gap claim. |
| **T5** | Validation | Rebuild: energy-balance closure (**after the HP-heat fix, ≤~2%**), COP plausibility band, sweep–MILP consistency, Paper-1 consistency (with price-harmonisation note), **single-year disclosure**. |

## Cross-cutting redesign rules
1. **Report the MIP gap on every quantitative claim**; never rank scenarios whose ΔTAC is within their gaps (add a footnote + the gap band in F4/F-elec).
2. **Electrification level is the organising x-axis** of §4 — F-ELEC leads, F4/F5 support.
3. **Two networks = endpoints**, never "size causes X" — captions phrased as observations.
4. **Every figure caption states**: scenario(s), heat-curve stage, siting, and gap.
5. Keep the entity-colour discipline; cost components never reuse network hues.

## Build order (post-re-run)
F-ELEC first (centrepiece) → T2/T-GAP (design + rigour) → F4/F5 refresh → F6 →
F7 tier-2 → T3/T4/T5 → supplement. Then the draft rewrite to the §2 structure.
