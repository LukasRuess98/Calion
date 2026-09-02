# Paper 2 — Planned Publication: Reviewer Packet

**Purpose.** A self-contained description of the *planned* paper — thesis, design,
methods, every figure and table, headline findings, and (deliberately) its weak
points — so a critical reviewer can challenge it *before* submission. Target: *Energy
Conversion & Management*. Companion docs: `IMPLEMENTATION_PLAN.md` (build plan),
`PUBLICATION_FIGURES.md` (figure spec), `QC_REVIEW.md` (internal QC),
`PROVENANCE.md` (figure→data trail), `../CALION_Paper2_Implementation_Statement.md`
(full technical traceability, Parts A–I).

> **Status flag.** Figures/tables below are BUILT on the frozen campaign (corrected).
> The tight-gap re-run (grid-fix, §5) is in progress; final numbers may shift a few %
> but the qualitative findings are established. Items marked *(pending)* are not yet built.

---

## 1. Thesis & contribution
A **multi-fidelity district-heating electrification optimisation framework** (fidelity
levels L1–L3+, a tractable linearised MILP), **demonstrated on two contrasting real
German networks** (Memmingen: small radial, 5 MW / 9.5 GWh; Stadtbach: large meshed,
201 MW / 640 GWh). Contributions: (i) the framework/method; (ii) a **controlled
electrification study** mapping cost/CO₂/COP vs heat-pump penetration; (iii) the value
and non-obviousness of HP/TES **siting**; (iv) the heat-curve→COP→cost coupling.

**We explicitly do NOT claim** "network size/topology *causes* X" — n=2 cannot support
it. The two networks are **illustrative endpoints**; cross-network differences are
phrased as observations.

## 2. Headline findings (what the paper argues)
1. **At 2026 prices, heat-pump electrification is *not* cost-effective in either
   network.** Forced HP penetration raises LCOH monotonically (MM 26→56, SB 18→36
   €/MWh) and does not cut CO₂; the HP sits largely idle behind cheaper, already-low-
   carbon CHP/biomass/waste-heat. *(the reframing — F-ELEC)*
2. **The heat-curve's benefit is electrification-dependent** — lowering supply temp
   always raises COP, but only cuts cost where the HP carries real load. *(F4)*
3. **Siting is decisive** — the wrong HP/TES node costs up to 77× (SB) / 4× (MM) the
   optimum; the optimum is non-obvious. *(F6)*
4. **Stadtbach is a net electricity exporter** (CHP), so higher power prices *lower*
   its cost — opposite sign to Memmingen. *(F7)*
5. Savings that *do* exist (e.g. the corrected +44.8% Memmingen vs baseline) come from
   **storage + heat-curve optimisation, not the heat pump.**

## 3. Paper structure
| § | Content | Elements |
|---|---|---|
| 1 Introduction | Motivation, gap, framework framing, scope | — |
| 2 Model formulation | Nodal heat/mass balance, HK stages, HP/EK/TES, investment, L3+ + McCormick **as equations** | eqs |
| 3 Case studies & experimental design | Two networks as endpoints; the DoE (§4 here); parameters | T1, T2, F2 |
| 4 Results — electrification spine | Electrification sweep; heat-curve coupling; cost/CO₂ vs baseline | **F-ELEC**, F4, F5, T3, T4 |
| 5 Results — siting | Siting landscape; fixed vs endogenous; storage cycling | F6, F9 |
| 6 Discussion | Sensitivity; why electrification level governs value; limits | F7, T5 |
| 7 Conclusions | Framework + transferable findings | — |
Supplement: F3, F8, Teil-6 pump comparison, full 46-row KPI tables.

## 4. Experimental design (and its honest critique)
**Studies (factors defined identically per network):**
- **A — Electrification sweep (centrepiece):** HP nameplate fixed at {0,20,…,100}% of
  peak; siting/HK fixed; TES+EK+dispatch endogenous. 6×2 (×3 HK planned).
- **B — Heat-curve coupling:** HK0/1/2 ceteris paribus.
- **C — Siting landscape:** full HP×TES node enumeration (MM 6×6, SB 5×5 = 61).
- **D — TES configuration factorial:** {none, central, at-WP, free} × {normal, hot
  charging} × HK — disentangles charging from siting *(pending rebuild)*.
- **E — Sensitivity tornado:** fixed-design re-dispatch of price/discount parameters.

**DoE weaknesses a reviewer will (rightly) raise — stated up front:**
- **n=2 networks.** No generalisation about size/topology; framed as endpoints.
- The *original* scenario list (S0–S7) had **inconsistent, confounded factor levels**
  across networks (hot-charging tangled with siting/colocation). The rework defines
  factors consistently; the balanced factorial (D) is *pending*.
- **Single weather/price year** — disclosed as a limitation.
- **Electrification is here a *mandated* factor** (Study A forces HP capacity, CAPEX
  counted); the endogenous optimum builds ~minimal HP.

## 5. Methods a reviewer should probe
- **Model:** L3+ nodal MILP; spatial temperature via a lightweight per-node heat-loss
  offset; bilinear Q=ṁcₚΔT handled by McCormick so it stays a true MILP; pressure/pump
  subsystem (Part H). `min_load` on/off binaries; TES charge/discharge-mode binaries.
- **Parameters (harmonised across both networks):** elec = spot timeseries + grid 61.6
  €/MWh + demand charge 127 k€/MW·a; gas 58.6; biomass 20; CO₂ 100 €/t; ef_el 400
  kg/MWh; HP 700 €/kW; EK 150 €/kW; TES 1200 €/m³; discount 5%; lifetimes 20/25/30 y.
- **MIP gap:** the **grid big-M fix** (max import/export 5000→50/500 MW; the 5000 caused
  a −3.8×10¹⁰ root bound) makes Memmingen solve to *optimal*; the campaign reports every
  scenario's gap and never ranks within-gap. Proven <1% *everywhere* would need weighted
  typical-days (deferred build). *(verification of the hardest scenarios in progress)*
- **Validation:** energy-balance closure (**known reporting artefact — HP electricity
  mis-counted as heat; real balance ≤~5%, fix pending**), COP plausibility band,
  sweep–MILP consistency, Paper-1 consistency (with a price-harmonisation disclosure).

---

## 6. FIGURES — full descriptions

**F2 — Two networks (§3).** Node-link maps of Memmingen (radial tree, 15 nodes) and
Stadtbach (meshed, 33 nodes), side by side; producer / WP / TES-candidate nodes marked.
Establishes the topology that §5 siting refers to. *(user is replacing the current draft.)*

**F-ELEC — Electrification spine (§4, NEW CENTREPIECE).** 2 rows (networks) × 3 cols:
**LCOH [€/MWh], CO₂ [t/a], annual COP** vs **heat-pump penetration [% of peak]**. Both
LCOH panels rise monotonically; CO₂ flat/elevated; COP declines as the HP is oversized.
*Data:* Study A (5–6 optimal levels/network; SB high-HP tail re-solved). *Claim:*
electrification is not cost-effective at current prices. *Reviewer attack surface:*
price-dependence (a higher CO₂ or lower elec price could flip it — see F7); fixed S2
siting; two SB points were maxTimeLimit before re-solve.

**F4 — Heat-curve → COP → cost (§4).** 2 panels: (left) COP vs HK stage, both networks
rising (~5%/5 °C); (right) TAC indexed to HK0 vs COP — Memmingen drops to ~95.6%,
Stadtbach ≈flat. *Claim:* the heat-curve benefit is electrification-dependent. *Note:*
the earlier "2×3 TES-volume coupling" figure was discarded — that panel was **solver
noise** (MM TES negligible, SB capped). *Attack surface:* uses one fixed family per net.

**F5 — Cost & emissions vs baseline (§4).** Stacked bars (CAPEX / energy-OPEX / CO₂,
Paper-1 navy/teal/amber) for the best scenario vs the gray baseline, per network. *Claim:*
where savings exist they are storage/heat-curve driven. *Attack surface:* "best" scenario
selection; CHP CO₂ gross-vs-net convention affects the CO₂ split.

**F6 — Siting landscape (§5).** Per network, a heatmap of TAC (% above the best node)
over every candidate **HP × TES** node, optimum starred; titles give "worst siting N×
best" (SB 77×, MM 4×). *Claim:* siting is decisive and non-obvious. *Attack surface:*
enumeration is at HK2 only; the MM-S4 enum predates the 07-22 ladder fix (footnoted).

**F7 — Sensitivity tornado (§6).** Per network, diverging horizontal bars (teal = cost
decrease, amber = increase) of ΔTAC for ±30% prices, ±50% CO₂, ±2 pp discount, sorted by
span. SB is gas-dominated (±22%); the elec bar flips sign (SB net exporter). *Current
build is tier-1 (analytical, fixed design);* tier-2 (re-dispatch) is the intended final.
*Attack surface:* tier-1 approximates operational response for elec/gas.

**F8 — Spatial temperature & pressure profile (supplement).** 2 rows (T_supply in **red**,
p_supply in blue) along the main trunk of each network, secondary stations shaded. *Attack
surface (disclosed in caption):* pressure **saturates at 20 bar = a known j_12/j_pss
ceiling artefact**; Memmingen T is near-isothermal (axis zoom exaggerates a 0.4 °C drop).

**F9 — Storage cycling: fixed vs endogenous (supplement).** Per network, TES state-of-
charge over a winter week for best-fixed (dashed) vs best-endogenous (solid) siting.
Memmingen endogenous cycles more; Stadtbach fixed cycles hard while endogenous is flat.

**F3 — Capacity–cost surface (supplement).** Per network, LCOH heatmap over the Q̇_WP ×
V_TES grid with the MILP optimum starred — doubles as a sweep-vs-MILP cross-validation.
*(sweep re-run at the grid-fixed settings pending.)*

**F1 — DROPPED.** The former model-architecture schematic (cluttered) → its heat/mass
balance + McCormick relaxation become numbered equations in §2.

## 7. TABLES — full descriptions

**T1a — Network characteristics.** Nodes, pipes, route length, topology, demand zones,
peak load (MM 4.9 / SB 200.7 MW), annual heat (9.5 / 640 GWh), design supply temp.

**T1b — Generator portfolio.** Existing units per network (CHP, biomass, boilers, waste-
heat/AVA) with efficiencies — the real plants that make electrification uneconomic.

**T2 — Experimental design / scenario matrix.** *To be rebuilt* as factors × levels
(electrification × HK × TES-location × charging × siting freedom), defined identically per
network, replacing the ad-hoc S0–S7 list; each block mapped to Study A–E.

**T3 / T4 — Scenario KPIs (Stadtbach / Memmingen).** Per scenario: TAC [M€/a], LCOH,
Δcost vs baseline, CO₂, Q_WP, **V_TES [m³]** (added) + E_TES, COP. *Planned addition: a
`MIP gap [%]` column on every row* (the gap-reporting discipline). Full 46-row versions →
supplement; headline subset in main.

**T3b/T4b — Endogenous-siting KPIs.** The enumeration winners (HP/TES node, TAC) per
network — the data behind F6's optima.

**T5 — Validation.** Campaign population; **energy-balance closure** (currently shows the
reporting-artefact numbers — to be replaced by the ≤~2% heat-output-corrected values);
COP plausibility band; solver status/gaps; sweep–MILP consistency; Paper-1 OPEX
consistency (117%, with the price-harmonisation note); single-year disclosure.
**T5-supplement** lists excluded/diagnostic runs.

**T-GAP — MIP-gap & method table (NEW, pending).** Per study: solver settings, grid cap,
final gaps (median/max), solve time — the evidence for the tight-gap claim.

---

## 8. Limitations & anticipated reviewer challenges (the attack surface)
1. **n=2, no generalisation** — the honest framing must hold throughout; any "size/topology
   drives X" sentence is a valid rejection point.
2. **Electrification finding is price-specific** — must be stated as "at 2026 prices";
   a price × electrification sweep would strengthen it materially (recommended, not yet run).
3. **Energy-balance closure is not yet clean** (reporting artefact) — a reviewer seeing
   T5 as-is would object; the heat-output fix must land before submission.
4. **MIP gaps** — full-investment scenarios may still be ~1–3% (MM now optimal); every
   gap must be reported and no within-gap ranking made. 0.1% everywhere is not achieved.
5. **Reproducibility** — the paper's numbers come from `e8e445e`, not current `main`
   (which adds physics and doesn't reproduce them); this must be archived/tagged.
6. **P1↔P2 OPEX gap (117%)** — must be disclosed and mechanistically closed.
7. **Single weather/price year**; **CHP CO₂ gross-vs-net convention** affects CO₂ claims.
8. **Pressure results** carry the 20-bar ceiling artefact (supplement caveat).

## 9. Open decisions (author)
- **Framing:** "electrification framework" vs pivot to a **price-threshold study** (add
  Study F: elec/CO₂ price × electrification → the carbon price at which HP flips economic).
  *Recommended: the latter — it directly answers the finding.*
- Whether to build **weighted typical-days** for proven <1% gaps.
- Whether to add **multi-year** robustness.
