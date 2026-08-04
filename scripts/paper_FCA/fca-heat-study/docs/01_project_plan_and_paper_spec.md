# Project plan & paper specification

**Working title** — *Storage-enabled full electrification of industrial heat supply: how thermal
and battery storage substitute for grid reinforcement across five sites*

**Target journal** — Renewable Energy Focus (Elsevier). Applied, methods-light-but-rigorous,
strong on case-study evidence and practitioner relevance. Typical length 6 000–9 000 words,
8–12 figures.

**Status** — data template and framework notebook exist and run end-to-end on placeholder data.
Everything below is the plan to turn that into a manuscript.

---

## 1 · The working prompt

Copy this into any new session (or hand it to a co-author) to re-establish the full context.

> We are writing a journal paper for *Renewable Energy Focus* on decarbonising industrial heat
> supply with heat pumps and electrode boilers, and on the role of thermal (TES) and battery
> (BES) storage in avoiding grid reinforcement.
>
> **Scope, fixed:**
> 1. Five industrial sites, each with a measured 15-minute electricity demand profile and a
>    15-minute heat demand profile, 2022–2026.
> 2. Decarbonisation of the heat supply is **100 %** — no residual fossil boiler. Heat is
>    supplied by a heat pump (HP) and/or an electrode boiler (EB).
> 3. The grid connection limit of each site is the **historical maximum of its existing
>    electricity demand**. It is fixed in the storage scenarios and free (at a reinforcement
>    cost) in the no-storage reference.
> 4. Scenarios: `S0_BASE` (gas, reference) · `S1_NOSTOR` (electrified, no storage, grid may
>    grow) · `S2_TES` · `S3_BES` · `S4_TES_BES` · `S5_FREE` (everything free, economic optimum).
> 5. Assets are modelled linearly and simply (no unit commitment, single temperature level).
>    Refinement comes in a later paper.
>
> **Method:** one LP per (site, scenario) that co-optimises asset sizing and 15-minute dispatch
> over the horizon, minimising total annualised cost (annuitised CAPEX + energy + grid capacity
> charge + reinforcement), with unserved heat and unserved electricity as high-penalty slacks so
> that infeasible configurations return *how much* is missing rather than "infeasible".
> Implemented in Pyomo, solved with HiGHS (interior point).
>
> **Deliverables:** an Excel workbook holding all inputs, a Jupyter notebook holding the whole
> workflow, a KPI table, ten figures, and a reproducibility record.
>
> **Everything is data-driven.** No site, asset, price or scenario value is hard-coded in the
> notebook; all of it lives in `data/input_data_template.xlsx`.

---

## 2 · Research questions

| # | Question | Answered by |
|---|---|---|
| RQ1 | How much does the grid connection have to grow if industrial heat is electrified to 100 % without storage? | `S1_NOSTOR` vs `S0_BASE`, Fig. 3 |
| RQ2 | Can storage keep the site inside its existing connection — and how much storage does that take? | `S2`–`S4`, Fig. 4 |
| RQ3 | Where the answer to RQ2 is *no*, what is the **minimum viable connection** with storage, and how much reinforcement does storage still avoid? | `find_min_connection()`, Fig. 10 |
| RQ4 | TES or BES — which does the work, and under what conditions does the other one earn a place? | `S2` vs `S3` vs `S4`, sensitivity, Fig. 9 |
| RQ5 | What does it cost per MWh of heat and per tonne of CO₂ avoided, and how does that vary across load archetypes? | LCOH / abatement cost, Fig. 7 |
| RQ6 | Which parameters actually drive the sizing decision? | OAT sensitivity + 2-way grid, Fig. 9 |

**Claimed contribution.** Not a new model — a *consistent, multi-site, 15-minute-resolution
quantification of the storage-versus-reinforcement trade-off* under a hard 100 % decarbonisation
constraint, with a load-archetype taxonomy that lets other plants place themselves. The
"minimum viable connection" metric (RQ3) is the part that has not been reported this way before.

---

## 3 · Work packages

| WP | Content | Status | Depends on |
|---|---|---|---|
| WP0 | Data template, validation, caching | **done** | — |
| WP1 | LP formulation, sizing + dispatch, slacks | **done** | WP0 |
| WP2 | Scenario runner, KPI layer | **done** | WP1 |
| WP3 | Figure library (F1–F10) | **done (draft quality)** | WP2 |
| WP4 | Sensitivity: OAT + 2-way grid | OAT done, 2-way open | WP2 |
| WP5 | **Replace placeholder data with measured data** | **open — you** | — |
| WP6 | Parameter sourcing: replace every `PLACEHOLDER` in `assets` with a citable value | **open — you** | — |
| WP7 | Production runs at 15 min, all years, all sites | open | WP5, WP6 |
| WP8 | Manuscript writing, figure polish, literature review | open | WP7 |

WP5 and WP6 are the critical path. Everything else is ready to consume them.

---

## 4 · Code deliverables → paper artefacts

Each row is a function in the notebook and the thing it produces in the manuscript.

| Code object | Produces | Paper artefact |
|---|---|---|
| `load_inputs()` + `_validate()` | validated `Inputs` object, pickle cache | Methods §"Data" + the reproducibility statement |
| `INP.sites` (auto `P_grid_exist_MW`) | site table incl. derived connection limit | **Table 2** — site characterisation |
| `cop_series()` | time-varying Carnot COP per site | Methods, Eq. (COP); Fig. A1 (appendix) |
| `build_model()` | the LP | Methods §"Model", Eqs. I–VIII, objective |
| `solve_case()` | dispatch time series + KPI dict | all results |
| `run_batch()` | `kpi_main.csv`, `ts_main.pkl` | raw material for every figure |
| `add_relative_kpis()` | ΔCO₂, LCOH, abatement cost, uplift | **Table 3** — main results |
| `fig_demand_overview()` | monthly mean el + heat, 5 sites | **Fig. 1** — the five archetypes |
| `fig_duration_curves()` | load duration curves | **Fig. 2** — why load factor matters |
| `fig_peak_problem()` | existing connection vs naive electrified peak | **Fig. 3** — the motivation, the paper's opening figure |
| `fig_storage_sizes()` | TES/BES sizes per site and scenario | **Fig. 4** — the price of staying inside the connection |
| `fig_dispatch()` | one representative winter week, 3 panels | **Fig. 5** — how it actually operates |
| `fig_grid_duration()` | grid draw duration curve per scenario | **Fig. 6** — the peak-shaving evidence |
| `fig_kpi_comparison()` | uplift / LCOH / CO₂ / abatement, 4 panels | **Fig. 7** — scenario comparison |
| `fig_cost_stack()` | CAPEX vs energy vs capacity charge | **Fig. 8** — where the money goes |
| `find_min_connection()` / `fig_min_connection()` | minimum viable connection per scenario | **Fig. 10** — RQ3, the headline result |
| `run_sensitivity_oat()` / `fig_tornado()` | tornado charts | **Fig. 9** — robustness |
| `export_tables()` | CSV + LaTeX | Tables 2 and 3, paste-ready |
| `export_metadata()` | config, versions, workbook hash, timestamp | Data availability statement |

**Still to write (WP4/WP8):**

* `run_sensitivity_grid(param_a, param_b)` → 2-way heat map. The one that matters:
  **TES CAPEX × electricity-price spread**, because it is where BES stops losing to TES.
* `fig_pareto()` → storage size vs peak reduction, one line per site. Shows diminishing returns
  and gives practitioners a sizing rule of thumb.
* `run_operation_validation()` → sizes fixed from the design year (`Case.fixed_sizes`), operated
  over the other four years. Produces the *design-year robustness* KPI: how much unserved heat
  appears when the weather/price year differs from the one you sized on. Reviewers ask this.

---

## 5 · Paper outline

1. **Introduction** — industrial heat is ~2/3 of industrial final energy; electrification is the
   only scalable route below 200 °C; the binding constraint in practice is not technology but the
   grid connection and its multi-year queue. Gap: studies size HP/EB against energy and cost, few
   against a *hard* connection limit, and almost none compare TES and BES on the same footing at
   15-minute resolution across several load archetypes.
2. **Method** — §2.1 sites and data, §2.2 asset models, §2.3 optimisation problem (Eqs. I–VIII +
   objective), §2.4 scenarios, §2.5 KPI definitions, §2.6 sensitivity design.
3. **Case studies** — Table 2, Figs. 1–2. Introduce the five archetypes and, crucially, the
   **load factor** and **heat-to-power ratio** as the two variables that predict everything later.
4. **Results** — §4.1 the peak problem (Fig. 3) · §4.2 storage sizing (Figs. 4, 6) · §4.3
   operation (Fig. 5) · §4.4 economics (Figs. 7, 8) · §4.5 minimum viable connection (Fig. 10) ·
   §4.6 sensitivity (Fig. 9).
5. **Discussion** — when storage substitutes for copper and when it cannot; the energy-limited
   versus power-limited distinction; what a plant needs to know to place itself in the taxonomy;
   policy implication for connection-queue and tariff design.
6. **Limitations** — the table in §7 of the notebook, verbatim.
7. **Conclusion.**

**The one-sentence finding the paper has to land:** *for power-limited sites, thermal storage
substitutes for grid reinforcement almost completely and at a fraction of the cost; for
energy-limited sites it only reduces the reinforcement, and the load factor tells you which one
you are before you model anything.*

---

## 6 · Data you need to deliver (WP5/WP6)

Paste into the existing sheets — keep sheet names, column headers and the timestamp column.

**Time series** (`el_demand_MW`, `heat_demand_MW_th`)

- [ ] 15-minute mean power, MW and MW_th, left-labelled intervals.
- [ ] Gap-free 2022-01-01 00:00 → 2026-12-31 23:45, local time, no DST duplicates or holes.
      If your export has DST artefacts, fix them before pasting — the validator will reject them.
- [ ] Electricity demand **without** any existing electric heat generation. If a site already has
      an electric boiler, subtract it and tell me.
- [ ] Heat demand at the network feed-in point, **including** distribution losses.
- [ ] For 2025/2026: if these are forecasts rather than measurements, say so — it changes the
      reproducibility statement and probably means we size on a measured year.

**Market data** (`market_15min`)

- [ ] Day-ahead price, EUR/MWh, same 15-min grid (quarter-hourly product if you have it, else
      hourly forward-filled — tell me which).
- [ ] Grid emission factor, tCO₂/MWh. **Say whether it is average or marginal** — it changes the
      CO₂ claim materially and a reviewer will ask.
- [ ] Ambient temperature °C per site if the sites are geographically separated (currently one
      shared series; the workbook would then need one column per site).

**Parameters** (`assets`, `sites`)

- [ ] Every `PLACEHOLDER` in the `source` column replaced by a citation or a vendor quotation.
      These 43 rows become the paper's parameter table; unsourced numbers are the fastest route
      to a reviewer rejection.
- [ ] Real supply/return/source temperatures per site — they drive the COP and therefore
      everything downstream.
- [ ] Actual grid tariff structure: Leistungspreis, Arbeitspreis, and whether any site qualifies
      for reduced network charges (§19 StromNEV atypical use, Bandlastprivileg). **If atypical
      network use applies, the peak-shaving value changes by an order of magnitude** and it
      deserves its own scenario.
- [ ] TES volume limits per site (m³ actually available on the ground) — currently guessed. In
      the placeholder runs TES sizes reach ~400 MWh, which is a large tank; a real footprint
      constraint may bind first.

---

## 7 · Open decisions

I would rather you settle these than have me pick a default.

| # | Decision | Options | My recommendation |
|---|---|---|---|
| D1 | Objective | (a) min cost, 100 % decarb as hard constraint · (b) ε-constraint cost/CO₂ Pareto | **(a)** as the main study, one Pareto figure for a single site in the discussion. (b) everywhere doubles runtime for modest payoff. |
| D2 | Meaning of "100 % decarbonised" | (a) no fossil boiler, grid CO₂ counted at the hourly EF · (b) green PPA, zero by definition | **(a)**. Option (b) makes the CO₂ KPI trivially zero and the paper loses RQ5. |
| D3 | Does BES get a fair shot? | (a) arbitrage + peak shaving only · (b) add ancillary-service revenue or option value | Decide now. Under (a) BES loses to TES at every site — a legitimate finding, but then the paper's title should say so. If BES is meant to be part of the answer, you need (b). |
| D4 | Sizing horizon | (a) one design year · (b) all five years jointly | **(a)** + operation validation on the other four years. (b) is 5× the runtime for a result nobody asks for. |
| D5 | Foresight | perfect foresight only, or add rolling-horizon MPC | Perfect foresight for the main results; add MPC for **one** site as a "foresight gap" number. Cheap insurance against a reviewer. |
| D6 | Storage cost scaling | linear · piecewise-linear economies of scale | Linear now. Revisit if TES sizes stay near 400 MWh, where linear cost is optimistic. |
| D7 | Site anonymity | real names · archetype labels | Archetype labels ("continuous chemicals, load factor 0.87") — better for generalisation and avoids an NDA problem. |

---

## 8 · Runtime & reproducibility

Measured on one core with HiGHS:

| Configuration | Per case | Full study (5 sites × 5 scenarios) |
|---|---|---|
| 1 h, one year | 1–7 s | ~3 min |
| 15 min, one year | ~30–120 s | 30–90 min |
| 15 min, five years | 10–30 min | 4–12 h |

Model *construction* is ~1 s; solving dominates. Two settings matter:

* `solver_options={"solver": "ipm", "run_crossover": "off"}` — interior point, ~20× faster than
  the dual simplex on these LPs. A simplex fallback catches the occasional case where IPM returns
  no loadable solution.
* Design-year sizing + fixed-size operation runs (`Case.fixed_sizes`) instead of a single
  five-year LP. Same answer, a fraction of the cost, and it produces the robustness KPI for free.

**Reproducibility plan.** `export_metadata()` writes config, package versions, workbook path and
mtime to `results/run_metadata.json` on every run. Before submission: freeze the workbook, record
its SHA-256, tag the notebook, and state in the data-availability section that the manuscript can
be regenerated with `CFG["resolution"]="15min"` and `CFG["years"]=[2022,…,2026]`.

---

## 9 · Risks

| Risk | Mitigation |
|---|---|
| Real profiles turn out highly correlated (all five sites behave the same) → no archetype story | Check load factor and heat/power ratio the moment data arrives; if they cluster, recruit a sixth site or reframe around one axis |
| TES wins everywhere and BES contributes nothing | Either accept it and retitle, or implement D3(b). Decide before writing |
| Storage sizes hit the `size_max` bounds | Bounds are inputs, not physics. Raise them, or introduce the real footprint constraint and report it as binding |
| Reviewer asks for perfect-foresight justification | D5 |
| 2025/2026 data are forecasts | Size on a measured year, disclose |

---

## 10 · Immediate next steps

1. **You:** answer D1–D3, deliver the measured profiles (WP5) and at least the HP/TES/BES cost
   sources (WP6).
2. **Me, in parallel and not blocked by the above:** `run_sensitivity_grid()`, `fig_pareto()`,
   `run_operation_validation()`, and figure polish to journal quality (fonts, sizes, SVG export,
   colour-blind-safe palette).
3. **Then:** production runs (WP7) → Tables 2–3 and Figs. 1–10 → first full draft.

---

### File map

```
01_project_plan_and_paper_spec.md          this document
data/input_data_template.xlsx              all inputs (8 sheets, placeholder data)
notebooks/dhn_decarbonization_framework.ipynb   the framework
  ├─ results/kpi_main_extended.csv         written on run
  ├─ results/table2_sites.{csv,tex}
  ├─ results/table3_results.{csv,tex}
  ├─ results/min_connection.csv
  ├─ results/run_metadata.json
  └─ results/figures/F1…F10.{html,svg}
```

Put the notebook one level above `data/`, or set `DHN_ROOT` / `DHN_XLSX` as environment
variables. First run reads the workbook in ~25 s and caches it; later runs start in under a
second.
