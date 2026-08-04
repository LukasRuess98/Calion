# CLAUDE.md — working brief

Read this before touching anything. It is the contract between you and the project.

---

## 1 · What this is

A research framework and manuscript for a journal paper (target: *Renewable Energy Focus*).

**Research question.** An industrial site electrifies its heat supply to 100 % with heat pumps and
electrode boilers. It does not get a bigger firm grid connection. What it can get is a **flexible
connection agreement (FCA)** — under § 17 Abs. 2b EnWG the network operator may grant additional
withdrawal capacity subject to a static or dynamic limitation. Given a specific agreement, **how
must the energy system be built?**

Formally: minimise total annualised cost subject to

```
p_grid(t) <= P_limit(t)
```

where `P_limit(t)` is a time series built from the contract parameters the statute requires the
agreement to state — the level of the limitation and the periods of limitation. Decision
variables are the sizes of heat pump, electrode boiler, thermal storage (TES) and battery storage
(BES), plus their 15-minute dispatch.

This is not "peak shaving with a battery". The distinction matters and you should keep it in
mind: in the demand-charge literature the peak is a *tariff* signal that can be exceeded at a
price. Here the limit is **contractual** — exceeding it is a breach, and the statute requires the
agreement to settle the liability in advance. That is why the constraint is hard and shortfall is
reported as unserved energy rather than priced through. Do not "improve" this by adding a penalty
price that lets the model buy through the limit.

## 2 · Layout

```
fcaheat/            the package — canonical, edit this
  config.py         CFG dict, paths, solver factory. CFG is mutated by callers.
  data.py           Inputs dataclass, workbook loading, validation, caching
  fca.py            P_limit(t) construction, DSO call generation, HLZF mask
  model.py          Case, build_model (the LP), solve_case
  runner.py         batch runs, derived KPIs, contract space, sensitivity
  mpc.py            rolling-horizon operation with forecast error and limited notice
  figures.py        figure library
  export.py         CSV / LaTeX / reproducibility record
run_study.py        CLI driver
notebooks/study.ipynb   THIN driver that imports the package. Contains no logic.
data/input_data_template_v2.xlsx   all inputs — the single source of truth
docs/               plan, regulatory basis, literature review, manuscript draft, changelog
tests/              pytest
FIGURES.md          specification of every figure, built and unbuilt
```

Run: `pip install -r requirements.txt`, then `python run_study.py --smoke` (~1 min) or
`pytest -q` (~5 s).

## 3 · Rules

1. **The workbook is the single source of truth.** No site, asset, tariff, contract or scenario
   value may be hard-coded in Python. If you need a new parameter, add a row or column to the
   workbook and read it. `build_template_v2.py`-style regeneration must preserve every existing
   sheet name and column header.
2. **Edit the package, not the notebook.** `notebooks/study.ipynb` imports `fcaheat` and holds no
   logic. If you find yourself writing a function in the notebook, it belongs in the package.
3. **Never invent a citation.** If you cannot open the source, mark it ⚠ or ⛔ exactly as
   `docs/04_literature_review.md` does. A fabricated reference in a manuscript is unrecoverable —
   a reviewer who catches one stops trusting all of them. Same for parameter values: an unsourced
   number stays labelled `PLACEHOLDER` in the workbook's `source` column.
4. **Add a regression test with every bug fix.** Two bugs have already been found by validation
   runs rather than by tests; see §6.
5. **Do not silently change a default.** Defaults in `CFG` and in the workbook are study
   assumptions. Changing one changes results. Flag it.
6. **Keep the model an LP.** Introducing a binary (minimum load, unit commitment, threshold
   tariffs) makes the full study intractable at 15-minute resolution over three years. If a
   feature needs integrality, implement it as a post-hoc check or a two-pass fixed-point and say
   so in the docstring.

## 4 · Conventions

* Units: MW electric, MW_th thermal, MWh, EUR, EUR/MWh, tCO2/MWh, °C. Always in the name.
* Time: 15-minute intervals, left-labelled, local time, no DST gaps or duplicates. The validator
  rejects anything else.
* A **run** is a triple *(site, storage configuration, connection regime)* — `Case(site=...,
  scenario=..., fca=...)`. `scenario` means the storage configuration only; the grid regime lives
  in `fca`.
* `P_grid_exist` is the historical maximum of the site's measured electricity demand. This is a
  scope rule, not an estimate.
* Existing KPI names are load-bearing (figures and exports read them). Add, don't rename.

## 5 · Key concepts you will need

**Connection regimes** (`data/…xlsx`, sheet `fca`): `firm` · `firm_upgrade` · `static` · `window`
(deterministic schedule — the original study case, restricted 07–11 and 13–18 on working days) ·
`dynamic` (operator-called, budget in h/a) · and `FCA_TDTR`, an 85/15 dynamic regime with
day-ahead notice calibrated to the Dutch time-dependent transport right as an international
benchmark.

**Two regulatory layers.** The FCA restriction windows (`restricted` mask) and the high-load
windows used to assess individual network charges under § 19 Abs. 2 StromNEV (`hlzf` sheet,
billing mask) are set by different mechanisms and need not coincide. Shifting heat production out
of one can push it into the other. Modelling both is a novel element of the paper — do not
simplify it away.

**Restriction bite.** `restricted_share` is what the operator reserves; `binding_restricted_share`
is the fraction of those intervals where the limit actually binds; `restriction_bite_share` is
their product. The gap between reserved and binding is capacity the operator never needs, and it
is the plant's negotiating argument.

**Notice.** `fca.notice_h` is how far ahead a restriction becomes visible. Used only by the MPC.
0.25 = response time only, 24 = day-ahead, ≥ horizon = fully known. Sweeping it with identical
hardware turns the foresight caveat into a contract-design result.

## 6 · Traps — read before debugging

* **Sub-year horizons.** `_dynamic_calls` pro-rates the annual curtailment budget by horizon
  length. It previously used `index.year.nunique()`, so a one-month screening run got a full
  year's curtailment. Guarded by `test_tdtr_restricts_about_15_percent`. Any new time-based
  budget must be pro-rated the same way.
* **Solver.** HiGHS dual simplex takes ~150 s on a site-year that interior point does in ~7 s.
  Default is `{"solver": "ipm", "run_crossover": "off"}` with an automatic simplex fallback
  (`solve_with_fallback`) because IPM occasionally returns no loadable solution. Do not remove
  the fallback.
* **Peak billing is 15-minute.** Sizing at 1 h resolution and reporting a peak is inconsistent.
  Screening at 1 h is fine; every number that goes in the manuscript comes from a 15-min run.
* **Feasibility is a result.** Unserved heat is not a failure to be tuned away. For high-load-
  factor sites it is the finding — no storage size makes an unenlarged firm connection work.
* **`CFG` is global and mutable.** `Case` resolves `resolution` and `years` from it at
  construction. If you change `CFG` mid-run, existing `Case` objects keep their old values.

## 7 · Backlog

Ordered. Items 1–3 are not blocked by the user's data; items 4+ are.

**1 · Figures.** DONE — every coded figure (F1–F20 incl. F2b) exists and runs; only F0, a
hand-drawn system schematic, remains (draw.io/Inkscape, not code). Built across this work: F2b
`fig_archetype_scatter`, F11 `fig_contract_space`, F13 `fig_restriction_bite`,
F14 `fig_block_length_vs_storage`, F15 `fig_sensitivity_grid`, F16 `fig_shadow_price`,
F17 `fig_hp_eb_split`, F18 `fig_co2_accounting`, F19 `fig_seed_robustness`, F20 `fig_year_validation`.
F16 required wiring `m.dual` into `build_model`/`solve_case` (guarded by
`test_connection_shadow_price_extracted`). New runner drivers: `run_contract_grid` (F11),
`run_seed_robustness` (F19), `run_sensitivity_grid` (F15), `run_year_validation` (F20). Note: all
verified on placeholder data — figures must be regenerated once the real profiles land.

**2 · Intensive network use — DONE (post-hoc).** § 19 Abs. 2 S. 2 StromNEV. Eligibility
(`util_hours_h`, `annual_energy_GWh`, `intensive_eligible`) reported every solve; two-pass
`runner.solve_intensive_two_pass` applies `ECON.intensive_discount_max` to the capacity charge once
eligible (also `run_batch(..., intensive=True)`). No LP binary (rule 6). Guarded by
`test_intensive_network_use_post_hoc`. ⚠ Open: `intensive_discount_max` is a single-tier
PLACEHOLDER (0.8) — the tiered 7000/7500/8000 h floors (20/15/10 %) are unverified; treat as a
policy/sensitivity variable. Finding on placeholder data: window/dynamic sit just under 7,000 h,
static/upgrade clear it (the two § 19 layers interact).

**3 · Literature gaps.** `docs/04_literature_review.md` §9 lists five: industrial demand-side
flexibility; German connection queues and reinforcement lead times (the paper's motivation is
currently asserted, not cited); biomethane certification and additionality; MPC for industrial
energy systems; § 19 StromNEV in the academic literature. Roughly 15–20 references. Complete the
⚠ entries and replace the ⛔ ones with primaries while you are there.

**4 · Ingest the real data** (see §8) and immediately run F2b.

**5 · Production runs.** 15-minute resolution. Size on one design year, then re-run the other two
with `Case.fixed_sizes` for the operation check. Sensitivities at 1 h. Budget 3–10 h for the
sizing grid on one core.

**6 · Re-test the headline.** Placeholder data says the deterministic window regime needs ~3.3×
the thermal storage of an 85/15 dynamic regime, despite reserving less than twice as much time
(`docs/06_changelog_v3.md` §6). Confirm on real profiles over a full year and across call seeds.
If it survives, it is the paper's headline and the abstract in `docs/05_manuscript_draft.md` must
be rewritten around it — the abstract currently leads on the weaker storage-range finding.

**7 · Finish the manuscript.** Sections 3–5 and 7 of `docs/05_manuscript_draft.md` are scaffolds;
each carries the argument it must make and the figure that supports it.

## 8 · When the real data arrives

The user replaces the four data sheets themselves. Your job is to check, not to paste.

1. Run `load_inputs()` — validation covers gap-free 15-minute indexing, NaNs, negatives, missing
   site columns and unknown FCA types. Fix the *data*, never loosen the validator.
2. Run F2b (load factor × heat-to-power). Report immediately if the sites cluster.
3. Check that electricity demand excludes any existing electric heat generation.
4. Confirm whether the grid emission factor is average or marginal — it changes the CO₂ claim and
   a reviewer will ask.
5. Check whether 2025 values are measured or forecast. If forecast, size on a measured year.
6. Re-run `pytest`. `test_grid_connection_is_historical_max` and the FCA share tests are
   calibrated to the placeholder workbook; update the expected values, do not delete the tests.

## 9 · Definition of done

- [ ] Every `PLACEHOLDER` in the workbook's `source` column replaced with a citation or quotation
- [ ] No ⚠ or ⛔ references remaining in `docs/04_literature_review.md`
- [ ] All 20 figures in `FIGURES.md` built, or explicitly cut with a reason
- [ ] Production runs at 15-minute resolution over 2023–2025
- [ ] `results/run_metadata.json` written and referenced in the manuscript's §2.9
- [ ] Manuscript sections 3–5 and 7 written
- [ ] `pytest -q` green
- [ ] Code and workbook deposited; DOI in §2.9

## 10 · Two economically decisive unknowns

Neither exists in any literature and both must come from a real network operator offer:
`fca.netzentgelt_discount` (the tariff reduction granted in exchange for accepting the agreement)
and the site's actual capacity and energy charges. Every cost result scales with them. Do not
spend effort refining technology costs while these are placeholders — treat the technology costs
as Danish Energy Agency catalogue values with a sensitivity range and move on.
