# Detailed plan v2 — FCA-centred study

Supersedes `01_project_plan_and_paper_spec.md`. That document assumed a constant grid limit;
this one is built on the flexible connection agreement as the research object.

---

## 1 · Research question, as now implemented

> **Given a flexible connection agreement with a specific restriction structure, how must the
> electrified heat supply be designed?**

Formally: minimise total annualised cost subject to $p_g(t)\le P_\mathrm{limit}(t)$, where
$P_\mathrm{limit}(t)$ is generated from the contract parameters that § 17 Abs. 2b EnWG obliges
the parties to write down. Decision variables: HP, EB, TES and BES capacities plus dispatch.

Three sub-questions, all answered by the code as it stands:

* **RQ1 — sizing.** How do HP/EB/TES/BES sizes change across connection regimes, from a firm
  connection with no uplift to a fully upgraded one?
* **RQ2 — feasibility boundary.** For which load archetypes can storage bridge the restriction
  windows at all, and where does the network operator's own caveat bite — that FCAs only cover
  *temporary* congestion?
* **RQ3 — contract space.** Inverted: what is the minimum uplift, and the maximum restriction
  width, a given design can live with? This is the number a plant takes into the negotiation.

## 2 · Your seven points — what was done

| # | Your decision | Implementation |
|---|---|---|
| 1 | FCA is the core, restricted 07–11 and 13–18 | `fca` sheet; `FCA_WINDOW` defaults reproduce your case (`restricted_hours = 7,8,9,10,13,14,15,16,17`, working days). Constraint III is now $p_g(t)\le P_\mathrm{limit}(t)$. Six regimes: firm / firm_upgrade / static / window / window_wide / dynamic. |
| 2 | Baseline = gas + biomethane certificates | `sites.biomethane_share` and `biomethane_premium_EUR_per_MWh_th`. Two CO₂ figures reported: `CO2_cert_t` (certificate accounting) and `CO2_phys_t` (physical). |
| 3 | Perfect foresight for sizing, MPC into sensitivity, all sites | §6 of the notebook: `run_mpc()` and `run_mpc_all_sites()`. Forecast error on demand and price, DSO calls visible only within the response time, SOC safety margin. Reports the foresight gap and the number of limit violations. |
| 4 | 2023–2025 | Workbook regenerated for that horizon (105,216 rows). `CFG["years"]` defaults to `[2024]` for screening. |
| 5 | Heat-pump model later | COP stays Carnot-based, but a **maximum sink temperature** (`HP.T_sink_max_C`) now gates HP admissibility per site — above it the electrode boiler must carry the load. `cop_series()` is the single swap-in point for your detailed model. |
| 6 | More detailed plan | this document |
| 7 | You replace the dummy values | every parameter carries a `source` cell; §4 below is the status list |

**Additional changes made without being asked, because the FCA framing forced them**

* Billed peak is now measured over a **billing mask**: the HLZF windows where a site is an
  atypical network user under § 19 Abs. 2 S. 1 StromNEV, otherwise all steps. New `hlzf` sheet.
* Unserved **electricity** as well as unserved heat, so that a regime which cannot even cover the
  existing load returns a number instead of failing.
* `binding_share` KPI: the fraction of time the connection limit is active — the single best
  diagnostic for whether a design is limit-driven or price-driven.
* `run_contract_space()`: bisection on `P_flex_rel` and on the restriction width.

## 3 · What the placeholder run already shows

One site, one month, screening resolution. Placeholder data, so the numbers are illustrative —
but the *pattern* is the paper.

| Regime | TES for `S2_TES` | BES for `S3_BES` |
|---|---|---|
| `FCA_FIRM` (no uplift ever) | 406 MWh | 198 MWh |
| `FCA_WINDOW` (your 07–11 / 13–18) | 203 MWh | 39 MWh |
| `FCA_DYNAMIC` (300 h/a called) | 71 MWh | 18 MWh |
| `FCA_UPGRADE` (firm, enlarged) | 57 MWh | 3.5 MWh |

Read across a row and the paper writes itself: **the restriction structure, not the technology
cost, sets the storage size.** A time-window FCA halves the storage a firm-but-unenlarged
connection would need; a dynamic agreement with a few hundred called hours gets you most of the
way to an upgrade at a fraction of the storage. And on the continuous, high-load-factor site the
firm regime is simply infeasible — 5,300 MWh of unserved heat regardless of storage — which is
the model reproducing the network operators' own statement that FCAs, and by extension storage,
bridge temporary congestion only.

That contrast between a site an FCA can rescue and a site it cannot is the result the paper
should be built around.

## 4 · Parameter sourcing status

The `assets` sheet has 50 rows. Status after this pass:

**Sourced or pointed at a citable catalogue**

* HP / EB / TES cost, efficiency and lifetime → Danish Energy Agency Technology Data catalogues,
  <https://ens.dk/en/analyses-and-statistics/technology-catalogues>. The catalogue explicitly
  states that its values are generic representative techno-economic data and should not be the
  basis for a final investment decision — quote that caveat in the methods section, it is exactly
  the right hedge for a multi-site study. The 20-year investment horizon for industry and
  district heating is consistent with IEA HPT Annex 48 practice.
* HP maximum sink temperature ~160 °C, electrode/resistance heating above → Fleiter et al., cited
  in arXiv:2506.14664. ⚠ Secondary citation, get the primary.
* Packed-bed TES round-trip efficiency 90 % → Profaiser et al., cited in the same paper.
  ⚠ Secondary citation, get the primary.
* § 19 Abs. 2 StromNEV reduction to ~20 % of the standard charge → trade sources. ⚠ Verify.

**Still `PLACEHOLDER`, and blocking**

| Parameter | Why it blocks | Where to get it |
|---|---|---|
| `fca.netzentgelt_discount` | the entire economic case for accepting an FCA | actual DSO offer — no public substitute |
| `ECON.grid_capacity_price…` / `…energy_price` | scales every cost result | your DSO's price sheet for the site's voltage level |
| `ECON.grid_reinforcement_EUR_per_MW` | the counterfactual to storage | Baukostenzuschuss calculation + works estimate |
| `BES.capex_EUR_per_MWh`, `capex_EUR_per_MW` | drives the whole TES-vs-BES conclusion | 2025/26 market survey; a single citable source is essential because this is a headline comparison |
| `TES.capex_EUR_per_MW`, losses, C-rate | second half of the same comparison | vendor quotation or DEA storage catalogue |
| `sites.biomethane_premium…` | sets the baseline cost, hence every LCOH | your procurement, plus a market index for the sensitivity range |
| supply/return/source temperatures per site | drive the COP and the HP/EB split | your measurement data |
| HLZF windows | change which peak is billed | your DSO's published windows |
| DSO call series for `FCA_DYNAMIC` | currently proxied by price percentile | ask the DSO; otherwise state the proxy plainly |

**Recommendation.** Do not chase perfect literature values for the technology costs. Two of them
— the FCA discount and the network tariff — dominate the result, and neither exists in the
literature. Spend the effort on getting those from a real offer and treat the technology costs as
DEA catalogue values with a sensitivity range.

## 5 · Runtime

Measured, one core, HiGHS interior point:

| Configuration | Per case | Full grid (5 sites × 5 configurations × 6 regimes ≈ 130 runs) |
|---|---|---|
| 1 h, one month | 1–4 s | ~8 min |
| 1 h, one year | 5–30 s | 25–60 min |
| 15 min, one year | 1–5 min | 3–10 h |
| 15 min, three years | 5–20 min | 12–40 h |

Recommended production setup: size at 15 min on one design year, then re-run the other two years
with `Case.fixed_sizes` for the operation check, and run all sensitivities at 1 h. The MPC chapter
adds roughly 2–5 min per site per seed.

## 6 · Figures as they now stand

| Fig. | Function | Content |
|---|---|---|
| F1 | `fig_demand_overview` | five archetypes, electricity and heat |
| F2 | `fig_duration_curves` | load duration curves — introduces load factor |
| **F3** | `fig_limit_profile` | $P_\mathrm{limit}(t)$ for each regime over one week. **The explanatory figure of the paper** — it shows the reader what an FCA *is* |
| **F4** | `fig_feasibility_matrix` | unserved heat by configuration × regime. The feasibility boundary |
| **F5** | `fig_storage_vs_regime` | storage size by regime. The headline result |
| F6 | `fig_dispatch` | one week, three panels, restriction windows shaded |
| F7 | `fig_grid_duration` | grid draw duration curve per regime |
| F8 | `fig_kpi_comparison` | TES / LCOH / peak / unserved across sites |
| F9 | `fig_cost_structure` | CAPEX vs energy vs capacity charge |
| F10 | `fig_tornado` | sensitivity |
| **F11** | *to build* | **contract-space map**: restriction width × uplift, shaded by feasibility, one panel per site. If one figure ends up on the first page, it should be this one |

## 7 · What is not done, and why

You asked for the parameter values, then a broad literature review of about 70 references, then a
draft. The regulatory half of the review is in `02_regulatory_basis_and_model_mapping.md` with
sixteen verified sources. The rest is not here, and I would rather say so than pad it.

A 70-reference review needs roughly forty to sixty literature searches, each screened for
relevance and checked for correct attribution. Produced quickly, the failure mode is not a thin
review — it is confident, plausible, wrong citations: real authors attached to papers they did not
write, page numbers that do not exist. In a manuscript that is unrecoverable, because a reviewer
who catches one stops trusting all of them.

**Proposed next pass**, in this order:

1. **Literature review, part 2 — the technical field** (~25 refs): industrial heat
   electrification, HTHP and electrode boilers, power-to-heat with TES, industrial demand-side
   flexibility, storage sizing under grid constraints. Two anchors already located: a 2026
   Applied Energy review comparing electrical and thermal storage for electrified process heat,
   and a MILP sizing study linking electricity-price variability to HP/EB/TES sizing.
2. **Literature review, part 3 — flexible and non-firm connections** (~15 refs). The UK has a
   decade of operational experience with non-firm and actively managed connections; that
   literature is the closest existing analogue to this paper and must be engaged with.
3. **Complete bibliographic data** for parts 1–3 and assemble the reference list.
4. **Draft** — title, abstract, introduction, method, data. Case studies, results, discussion and
   conclusion left as scaffolds until the real data are in, as you asked.

Steps 1–3 are one working session. Step 4 is another. Neither is blocked by your data.

## 8 · Open decisions still on the table

| # | Decision | Note |
|---|---|---|
| D1 | Does BES get a revenue stream beyond arbitrage and peak shaving? | With the FCA framing this matters *less* — under a window regime BES sizes drop to a few MWh and TES dominates. The finding is now clean enough to state as a result rather than a modelling artefact. |
| D2 | Model intensive network use (7,000 h / 10 GWh) as well? | Recommend yes — electrification pushes sites *towards* the threshold, an effect that works against peak shaving |
| D3 | Site anonymity | archetype labels recommended |
| D4 | Is the price-percentile proxy for DSO calls acceptable, or can you get a real call series? | affects the credibility of the `FCA_DYNAMIC` results specifically |
| D5 | Include the § 19 reform as a policy scenario? | recommend yes; it converts a shelf-life risk into a result |
