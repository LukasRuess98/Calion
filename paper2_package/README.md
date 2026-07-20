# Paper 2 Design Package — status snapshot 2026-07-20 (campaign COMPLETE; 3 remaining figures IN PROGRESS, not yet in this package; ⚠️ Memmingen economics now STALE, re-run in progress — see banner below)

**⚠️ 2026-07-20, later same day — BOTH networks' economics now invalidated,
DO NOT use `tab_T3_stadtbach_kpis.csv` / `tab_T4_memmingen_kpis.csv` / any
headline number below until this is cleared.** Two confounds found and
fixed this pass, both the same class of bug (an unintentional per-network
economic-assumption asymmetry that could itself explain the siting-outcome
difference the paper's core claim rests on):
1. **Heat-pump `eta`**: Memmingen `0.6` vs. Stadtbach's already-correct
   `0.75`. Fixed in `configs/paper_2/Memmingen_P2_base.yaml`. Memmingen
   re-run in progress (see "What's still running"); Stadtbach untouched by
   this one.
2. **Heat-pump investment CAPEX**: Stadtbach `400,000 EUR/MW` vs.
   Memmingen's already-correct `700,000 EUR/MW` (flagged unresolved since
   2026-07-03, never acted on until now). Literature check (Pieper, Ommen,
   Buehler, Lava Paaske, Elmegaard & Markussen, "Allocation of investment
   costs for large-scale heat pumps supplying district heating," *Energy
   Procedia* 147 (2018) 358–367 — 26 real Danish DH-HP installations,
   0.8–1.1 M EUR/MW; corroborated by IRENA/JRC ~600–900 EUR/kW) confirmed
   700k EUR/MW is the literature-supported value. Fixed in
   `configs/stadtbach/Stadtbach_topo.yaml`. **This one required a full
   Stadtbach re-run** (Memmingen needed no change) — in progress, see
   "What's still running". This also forced killing an in-progress
   Stadtbach F3 capacity-sweep at 31/49 points (63%, ~28h sunk) and the F7
   sensitivity-tornado campaign — user-confirmed, not an accident.

See `project_paper2_eta_harmonization` and `project_paper2_hp_capex_asymmetry`
session memory for the full traces. Everything else in this snapshot (F1/F2/
F4/F5/F6/F9 figures, the model/methods description) predates both findings
and is NOT invalidated by them — only the economics tables and anything
downstream of them (F3, F6, F7, F8, T3/T4/T5) are affected.

This folder is the handoff package for designing the CALION Paper 2 manuscript
(target: Energy Conversion and Management). **The full 46-scenario campaign is
done** and **the economics (T3/T4/T5, the headline numbers) are final,
trustworthy, and unchanged since the last snapshot** — nothing below affects
any TAC/LCOH/CAPEX/OPEX/CO₂ number. **(See the ⚠️ banner above — this
statement is now only true for Stadtbach; Memmingen's 20 rows are stale
pending the eta-harmonization re-run.)** **What changed since 2026-07-19: two real
bugs were found and fixed (F8's pressure export, F7's objective extraction),
one apparent bug was investigated and found to be correct model behavior
(F8's Stadtbach "non-monotone" panel, now annotated instead of flagged), and
the two previously-nonexistent analyses (F3 capacity sweep, F7 sensitivity
tornado) were launched for the first time.** All three fixes are verified;
the **campaigns applying them are still running** as background jobs at the
time of this snapshot — see "What's still running" for exactly what that
means for you. **Verdict: start writing now — the numeric backbone and 6 of
9 figures are final. F8/F3/F7 will drop in without any other change to this
package once their campaigns finish; do not fabricate placeholders for them.**

## TL;DR for the writing agent

- **⚠️ BOTH networks' economics are STALE as of 2026-07-20 (eta fix +
  CAPEX fix, re-runs in progress) — do not write ANY TAC/LCOH/siting number
  into the manuscript until "What's still running" below says both are
  done.** Memmingen: eta-harmonization re-run. Stadtbach: HP-CAPEX
  harmonization re-run (bigger blast radius — also killed a 63%-done F3
  sweep and the F7 sensitivity campaign, see the top-of-file banner).
- ~~Economics (TAC, LCOH, CAPEX/OPEX, CO₂) are final and trustworthy for all
  46 scenarios, unchanged since 2026-07-19.~~ **No longer true for either
  network as of the same-day CAPEX finding — both `tab_T3_stadtbach_kpis.csv`
  and `tab_T4_memmingen_kpis.csv` are STALE, see the ⚠️ bullet above.** This was independently re-confirmed
  this pass: the F8 re-solve of `SB-S1-HK0` under the corrected pressure
  export produced the exact same objective (`9,978,017.60 €`) as the original
  campaign value — proof the pressure-export bug never touched the economics.
- **Figures ready to use as-is, no change this pass**: F1 (model
  architecture), F2 (network maps), F4 (k↔COP↔V_TES coupling), F5 (cost
  split), F9 (TES SOC time series).
- **F6 (endogenous vs. fixed siting)**: ready — a text-overlap rendering bug
  (long negative-bar label running off the axes) was found and fixed in the
  2026-07-19 pass, unchanged since.
- **F8 (spatial T/p profile) — NOT in this package yet, but both of its
  blocking problems are now resolved:**
  1. The pressure sub-panels being empty was a real, one-line export bug
     (wrong Pyomo attribute name) — **fixed and verified** (100 % of nodes
     now populated on both networks, physically plausible producer→consumer
     decay).
  2. Stadtbach's "non-monotone" temperature dip at `j_pss` is **not a bug** —
     `j_pss` (Stadtbach) / `j_12` (Memmingen) are secondary pump/generator
     stations with a deliberately free, locally-boosted setpoint (real
     equipment behavior, documented design decision from 2026-07-09). The
     figure now shades these nodes and its title no longer claims a
     network-wide "monotone fall".
  A full-year re-solve of the real `SB-S1-HK0`/`MM-S1-HK0` reference
  scenarios with the pressure fix is running now so the final figure uses
  clean, non-diagnostic data — see "What's still running". Once it finishes,
  the figure regenerates and drops into `02_figures_tables/` with no further
  investigation needed.
- **F3 (capacity-sweep heatmap) and F7 (sensitivity tornado) — NOT in this
  package yet, campaigns running for the first time.** Neither had ever been
  executed before this pass (F3's own prerequisite — "pick a representative
  scenario" — could only be decided after the main campaign finished; F7's
  prior runs all had a broken objective-extraction bug, now fixed). Both are
  mid-run — see "What's still running".
- **What you can write now**: introduction, model/methods (Part A/B of the
  Implementation Statement), Stadtbach and Memmingen case-study description,
  all economics-driven results text (siting comparison, cost breakdown, TES
  behavior), validation section (with the T5 caveat below), and the F1/F2/F4/
  F5/F6/F9 figure discussions. Leave placeholders only for the specific
  paragraphs that need F8's spatial profile, F3's heatmap, or F7's tornado —
  everything else is final.

## What's still running (check before you need F8/F3/F7 specifically)

**⚠️ Memmingen eta-harmonization re-run (launched 2026-07-20, later same
day) — THIS ONE DOES affect headline economics, unlike the three below.**
Two chained background campaigns, both using the corrected
`configs/paper_2/Memmingen_P2_base.yaml` (`eta=0.75`):
- **Wave 1** (`python -m scripts.paper_2.scenario_runner --scenarios BC-MM
  MM-S0-TVLFIX MM-S0-HK0 MM-S0-HK1 MM-S0-HK2 MM-S1-HK0 MM-S1-HK1 MM-S1-HK2
  MM-S2-HK0 MM-S2-HK1 MM-S2-HK2 MM-S3-HK0 MM-S3-HK1 MM-S3-HK2 MM-S5-HK0
  MM-S5-HK1 MM-S5-HK2 --force-rerun`): the 17 non-endogenous-siting Memmingen
  scenarios, sequential single MILP solves each.
- **Wave 2** (`python scripts/paper_2/enumerate_endog_siting.py --scenario
  MM-S4-H{K0,K1,K2} --enumerate-all --time-limit 1800 --concurrency 1
  --outdir output/paper2_runs/_endog_enum/MM-S4-H{K0,K1,K2}`, chained
  HK0→HK1→HK2): re-solves all 36 `(hp_site, tes_site)` pairs per HK stage —
  the same enumeration-decomposition method already used for the existing
  `SB-S6`/`MM-S4` results (see G.8), because the monolithic free-siting MILP
  is known-intractable. This is the expensive part, up to ~18h/stage,
  multi-day total.

Once both waves finish: (1) regenerate `scenarios_kpis.csv` via
`kpi_calculator.compute_all_kpis()`, (2) re-run `gen_tables.py` for T3/T4/T5
and `tab_T3b_T4b_f3_endogenous_siting_FINAL`, (3) **re-verify T5's exclusion
filter still keeps the new MM-S4 enumeration sub-pairs and the superseded
monolithic `MM-S4-*` dirs out of the headline gap/status statistics** —
the mechanism already exists (`gen_tables.py::build_t5`'s
`endogenous_superseded` set for `SB-S6-*`/`MM-S4-*` canonical ids, plus
`_load_kpis()`'s `__hp_.*__tes_` regex for the sub-pair dirs) and should
still work unchanged, but confirm rather than assume — this is exactly the
kind of regression the 2026-07-15/16 T5 fix (G.10-G.12) was built to prevent,
and it would be easy to silently reintroduce if that code path gets touched
before then. (4) Update every Memmingen number in this README (headline
results, TL;DR) and clear this banner and the one at the top of the file.

**⚠️ Stadtbach HP-CAPEX harmonization re-run (launched 2026-07-20, ~21:07) —
bigger deal than it looks, read this before touching Stadtbach numbers.**
`configs/stadtbach/Stadtbach_topo.yaml`'s `hp_sb.investment.capex_eur_per_mw`
changed `400,000 → 700,000 EUR/MW` (see top-of-file banner for the
literature citation). Two chained campaigns, mirroring the Memmingen
pattern:
- **Wave A** (`python -m scripts.paper_2.scenario_runner --scenarios BC-SB
  SB-S0-TVLFIX SB-S0-HK0 SB-S0-HK1 SB-S0-HK2 SB-S1-HK0 SB-S1-HK1 SB-S1-HK2
  SB-S2-HK0 SB-S2-HK1 SB-S2-HK2 SB-S3-HK0 SB-S3-HK1 SB-S3-HK2 SB-S4-HK0
  SB-S4-HK1 SB-S4-HK2 SB-S5-HK0 SB-S5-HK1 SB-S5-HK2 SB-S7-HK0 SB-S7-HK1
  SB-S7-HK2 --force-rerun`): 23 non-endogenous-siting scenarios (`SB-S7` is
  colocate-only, handled directly, not enumerated).
- **Wave B** (`enumerate_endog_siting.py --scenario SB-S6-H{K0,K1,K2}
  --enumerate-all --time-limit 1800 --concurrency 1`, chained
  HK0→HK1→HK2): re-solves all 25 `(hp_site, tes_site)` pairs per HK stage.

**This forced killing three in-flight campaigns that used the stale 400k
rate** (`Stop-Process` on the real Windows PIDs — MSYS bash's own `ps`
reports different, wrong PIDs on this host for anything not launched by the
current bash session; use `Get-CimInstance Win32_Process` to find the real
one before killing anything found this way): the F7 sensitivity-tornado
orchestrator + its 3 live Stadtbach variant children, and the Stadtbach F3
capacity-sweep — **which was at 31/49 points (63%), ~28h into its run**.
User was shown this exact number and explicitly confirmed proceeding anyway
— this was not an accidental loss. Both need relaunching (commands below)
once Wave A/B finish and there's RAM headroom to spare (killing them freed
~48GB of RAM that the sweep + F7 variants had been holding, most of it now
going to Wave A/B instead).

Once Wave A/B (Stadtbach) and Wave 1/2 (Memmingen, above) all finish: same
four steps as listed for Memmingen (regenerate `scenarios_kpis.csv`, re-run
`gen_tables.py`, re-verify T5's exclusion filter now against BOTH networks'
fresh enumeration sub-pairs, update every number in this README) — do this
once, after both networks are done, not twice.

Two more background campaigns were running BEFORE either of today's fixes
and were left alone rather than also killed — they predate the eta fix too,
so they're independently stale for that reason, but are close enough to
their own time budgets that killing them saves little. **Both need
re-queuing later, after Memmingen's re-run lands, with the corrected eta —
this is a real follow-up, not resolved by anything above:**

- **F8 real re-solve**: `SB-S1-HK0` (done — see confirmation above, and
  unaffected by anything today) then `MM-S1-HK0` (full-year, 24h/1% budget
  — ~20.5h in as of this snapshot, so likely finishes on its own soon, but
  its result predates today's Memmingen eta fix and will need re-running).
  Once genuinely done with the corrected eta: regenerate via
  `python -c "from scripts.paper_2.figures.fig_p2_campaign import build_f8; build_f8()"`.
- **F3 capacity sweep, Memmingen side only** (`MM-S1-HK0`, 37/49 points as
  of this snapshot, still running): also predates the eta fix, will need
  re-running once it finishes. The Stadtbach side of this sweep was the one
  killed above (different reason — CAPEX, not eta) and needs a fresh launch
  from scratch anyway.
- **F7 sensitivity tornado**: Memmingen-side results (in
  `output/paper2_runs/sensitivity/MM-*`) also predate the eta fix and are
  stale for that reason. The orchestrator that ran all of F7 (both
  networks) was the one killed above — so F7 needs a full fresh launch for
  BOTH networks once Wave A/B/1/2 all land, at 26 variants (13 parameters ×
  2 networks), each up to a 6h solve.
  until the campaign completes.

Full technical detail on all three (root causes, fixes, verification) is in
`01_specification/CALION_Paper2_Implementation_Statement.md`, **Part G.13**.

## Headline results (for quick reference — verify against the CSVs before quoting)

**Stadtbach** — **⚠️ STALE, HP-CAPEX-harmonization re-run in progress
(400k→700k EUR/MW), do not quote any number below until "What's still
running" says it's done** (BC-SB baseline TAC = 11.033 M€/a, solved at the
too-low 400k rate):
- Best fixed-siting result: `SB-S2-HK2` (TES at a pre-selected node), TAC =
  4.420 M€/a, −59.9 % vs. baseline.
- Best endogenous-siting result: `SB-S6-HK2` (free HP+TES placement,
  `hp=j_man, tes=j_man`), TAC = 4.437 M€/a, −59.8 % — essentially tied with
  the best fixed case, marginally worse (~0.4 %). Free siting does **not**
  beat a well-chosen fixed node here.
- All three `SB-S6` stages independently converge on the same site pair
  (`j_man`/`j_man`), a strong, reproducible result — see
  `tab_T3b_T4b_f3_endogenous_siting_FINAL.csv`. **Re-verify this holds under
  the corrected 700k CAPEX** — same caveat as Memmingen's `(j_3, j_1)` pair
  above: a 75% CAPEX change alters HP investment economics and could
  plausibly shift the winning site, which is exactly why this was worth
  fixing rather than leaving as an undocumented asymmetry.

**Memmingen** — **⚠️ STALE, eta-harmonization re-run in progress, do not
quote any number below until "What's still running" says it's done** (BC-MM
baseline TAC = 0.507 M€/a, solved at the wrong `eta=0.6`):
- Best fixed-siting result: `MM-S3-HK2`, TAC = 0.335 M€/a, −33.9 %.
- Best endogenous result overall: `MM-S5-HK2` (**colocated** HP+TES, not the
  free-siting `S4` family), TAC = 0.299 M€/a, −41.0 % — colocation beats free
  siting for Memmingen, the opposite pattern from Stadtbach. `MM-S4`
  (free siting, `hp=j_3, tes=j_1`) reaches TAC = 0.312 M€/a at best (HK2),
  still better than any fixed-node scenario but not as good as colocating.
- This Stadtbach-vs-Memmingen asymmetry (free siting helps in one network,
  colocation helps in the other) is a genuine, topology-dependent finding
  worth a sentence in the discussion — it is not an artifact. **However,
  with the eta confound now fixed, re-verify after the re-run that the
  `MM-S4`-vs-`MM-S5` ranking and the `(j_3, j_1)` winning pair still hold —
  a 25% better COP changes HP dispatch economics and could plausibly shift
  which site wins, which is exactly why the fix matters.**

**Validation (T5)**: 46/46 scenarios solved successfully; median MIP gap
1.84 %; annual COP range 2.43–3.67 (physically plausible). The MW-closure
statistic (22.98 % mean error, 12/41 passing ≤2 %) looks alarming at first
glance — **it is a known methodology limitation of that specific check, not
evidence of an energy-balance violation.** See "Known caveats" below before
citing it as a problem in the manuscript; do not present it as unexplained.

## What's in here

- `01_specification/` — the governing documents:
  - `CALION_Paper2_Implementation_Statement.md` — full model/spec
    traceability, current as of 2026-07-20. **Part G.13** (new this pass)
    documents the F8 pressure-export fix, the F8 Stadtbach-monotonicity
    resolution, the F7 objective-extraction fix, the F3 capacity-sweep
    launch, and the in-progress campaign status. **This is the primary
    methods-section source and the place to check before trusting any
    specific number's provenance.**
  - `CALION_Paper2_Sweep_und_Grafiken_Prompt_v2_final.md` — the figure/table
    spec (F1–F9, T1–T5) and capacity-sweep module spec.
  - `CALION_Paper2_Sweep_und_Grafiken_Prompt.md` — v1, history only.
  - `CALION_Paper2_Spezifikation.docx` — the original Version 1.0 spec.
- `02_figures_tables/` — current state of `results/paper2_figures/`:
  - `tab_T1a/T1b` — network characteristics / generator portfolio (static,
    config-derived, unaffected by the campaign). **⚠️ tab_T1a fixed
    2026-07-20 (later pass)**: Memmingen's "Peak heat load"/"Annual heat
    supplied" cells were internally impossible (implied mean load 6.5 MW
    exceeded the stated 5.3 MW peak). Root cause: `_peak_and_energy()` in
    `gen_tables.py` summed the ENTIRE raw demand xlsx as if it were exactly
    one hourly calendar year; Memmingen's raw file is actually ~1.24 years of
    15-minute-resolution data (Stadtbach's happens to genuinely be one hourly
    year, so it was never wrong there). Fixed to infer the true row interval
    and restrict to the same `scenario.horizon` calendar window the real
    MILP solves use. Corrected Memmingen values: peak 4.9 MW, annual 9.5 GWh
    (mean ≈1.1 MW — now consistent with the ≈1.4 MW mean load used in the
    Part-A storage-sizing chapter, not a third contradictory number as it
    first appeared). Stadtbach's cells (200.7 MW / 640.4 GWh) are unchanged.
  - `tab_T2` — scenario matrix (46 rows, static).
  - `tab_T3_stadtbach_kpis` (26 rows), `tab_T4_memmingen_kpis` (20 rows) —
    **final economics**, see headline numbers above.
  - `tab_T3b_T4b_f3_endogenous_siting_FINAL` — the corrected `SB-S6`/`MM-S4`
    results, with HP/TES site, MIP gap, and full KPI set.
  - `tab_T5_validation` — solver-status census, MW-closure stat (see caveat
    above), COP plausibility range, P1↔P2 consistency (see caveat below).
  - `fig_F1/F2/F4/F5/F6/F9` (svg+pdf+png) — ready to use.
  - `fig_F8_trunk_candidates_DRAFT`, `fig_palette_preview_DRAFT` — approval
    artefacts (trunk-path decision, color palette), not manuscript figures.
  - **Missing on purpose, campaigns in progress**: F8 (new pressure-fixed
    version), F3, F7 — see "What's still running".
- `03_configs/` — full config trees (`paper_2/`, `stadtbach/`) — unchanged
  this pass, still current.
- `04_implementation/` — source code snapshot (`calion/`, `scripts_paper_2/`),
  refreshed this pass to include every file touched by the fixes described
  above: `calion/io/thermal_network_exporter.py` (F8 pressure fix),
  `scripts_paper_2/figures/fig_p2_campaign.py` (F8/F6 figure fixes),
  `scripts_paper_2/sensitivity.py` (F7 extraction fix), `scripts_paper_2/
  capacity_sweep.py` (F3, new tractable solver budget).
- `05_paper1_reference/` — Paper 1 materials for consistency (submitted
  manuscript, Elsevier template, equations/methodology docs, published
  figures). Unchanged this pass.

## What changed this pass (2026-07-19 evening to 2026-07-20) — read this before trusting old caveats

1. **F8, problem 1 (pressure data always empty) — real bug, fixed.** Wrong
   Pyomo attribute name in the node-pressure export
   (`calion/io/thermal_network_exporter.py`); pressure was fully modeled and
   solved the whole time, just never read out. Fixed, verified 100 %
   populated with physically plausible producer→consumer decay on both
   networks. Full-year re-solve of the real reference scenarios in progress
   to get clean data for the final figure (see "What's still running").
2. **F8, problem 2 (Stadtbach "non-monotone" panel) — investigated, not a
   bug.** `j_pss`/`j_12` are secondary pump/generator stations with a
   deliberately free, locally-boosted setpoint — real equipment behavior,
   not an L3+ artifact or plotting bug. Figure now shades these nodes and
   its title states this explicitly instead of claiming an incorrect
   network-wide monotonicity guarantee.
3. **F7's objective extraction — real bug, fixed.** Every prior sensitivity
   run recorded `obj_eur: null` despite solving successfully; the tornado
   diagram's one required number was silently missing for all 26 variants,
   every prior attempt. Root cause: an independent, broken hand-rolled
   extraction helper instead of the main campaign's proven extraction path.
   Fixed by routing through the same `run_single_scenario()` pipeline the
   46-scenario campaign itself uses. Verified on one variant before
   launching the full campaign.
4. **F3's capacity sweep — never run before, now launched.** Not a bug: the
   module existed but had never actually been executed. Added a dedicated,
   tractable dispatch-only solver budget (the main campaign's 24h/1%
   investment-MILP budget would have made a 98-point sweep impractical) and
   launched both networks' 49-point grids.
5. **Operational: F7 campaign concurrency raised mid-run.** Confirmed spare
   RAM/CPU headroom on the host and safely increased F7's parallelism
   (3→8 concurrent solves) without touching or restarting F8/F3's live
   processes. No formulation or budget-cap change — see Implementation
   Statement Part G.13.5 for exactly how the handover between the old and
   new scheduler was made collision-safe.

See the 2026-07-19 pass's changes (stale-aggregation fix, TES dispatch-export
bug, F6 rendering fix, F3 `_summary.json` staleness correction) in the
Implementation Statement Parts G.10–G.12 — all still valid and unchanged.

## Known caveats to state explicitly in the manuscript

From Implementation Statement Part D (O-1…O-10) and Part G:
- O-1: WP/EK/TES cost coefficients are literature/VDI-2067 assumptions, not
  vendor quotes. **HP CAPEX specifically was harmonized 2026-07-20 to
  700,000 EUR/MW for both networks** (Stadtbach was 400k, undocumented,
  below the literature band; Memmingen's 700k was already correct) — see
  `configs/stadtbach/Stadtbach_topo.yaml`'s inline comment for the citation:
  Pieper, Ommen, Buehler, Lava Paaske, Elmegaard & Markussen, "Allocation of
  investment costs for large-scale heat pumps supplying district heating,"
  *Energy Procedia* 147 (2018) 358–367 (0.8–1.1 M EUR/MW, 26 real Danish
  DH-HP installations). **Cite it as Energy Procedia, not Energy Conversion
  and Management** — an earlier web-search pass momentarily misattributed
  it; don't let that wrong journal name reach the manuscript's bibliography.
- **T1's Memmingen "Annual heat supplied" cell was wrong (57.3→9.5 GWh),
  fixed 2026-07-20**: `gen_tables.py::_peak_and_energy()` summed Memmingen's
  entire raw demand file (which spans ~1.24 years at 15-minute resolution)
  as if it were one hourly calendar year — the implied mean load exceeded
  the stated peak, which is how this was caught. Now infers the true
  sampling interval and restricts to the same `scenario.horizon` window the
  real MILP solves use. Stadtbach's cell was never wrong (its file already
  is exactly one clean hourly year). Not a modeling bug — confirmed the
  actual solves already used the correct 2025-only window; only this
  standalone descriptive table was affected.
- O-2: the heating-curve formula is a defensible variant of the spec's
  literal form, not an exact reproduction.
- O-5: endogenous siting (`S4`–`S7`) is an extension beyond spec §3.3 —
  present it as such, not as literally specified.
- **`SB-S2` (and any TES sited directly at a consumer node) shows
  near-constant bidirectional charge/discharge cycling** — confirmed to be
  the genuine MILP optimum given current cost coefficients (not a bug — see
  Part G.1–G.4), but an unusual operating pattern that deserves a
  plausibility sentence if quoted (e.g., correlate against local HP dispatch)
  rather than presenting it as obviously realistic.
- **T5's MW-closure statistic** (22.98 % mean, 12/41 passing) is a real
  number but measures the wrong thing for a multi-producer/TES-heavy network:
  the check's formula (`generation + discharge − charge` vs. demand) nets a
  wash-cycling TES's contribution to ~zero, while the model's *true*
  constraint-level balance is verified correct to <0.1 % via a purpose-built
  audit (Part G.12). If T5 is included in the manuscript's validation
  section, caption it as "aggregate solver/dispatch-balance census" and do
  **not** describe it as an energy-conservation check — or note the
  known formula limitation explicitly. Do not present 22.98 %/12/41 as if it
  suggests the model doesn't conserve energy; it doesn't mean that.
- **F8's station-node temperature/pressure jumps** (`j_pss` Stadtbach,
  `j_12` Memmingen): if F8 is discussed, note explicitly that these are
  secondary pump/generator stations with an independently-boosted setpoint,
  not evidence against monotone propagation elsewhere on the trunk (Part
  G.13.2).
- G.8: the `(hp_site, tes_site)` pairs quoted anywhere for `SB-S6`/`MM-S4`
  must be the ones in `tab_T3b_T4b_f3_endogenous_siting_FINAL.csv`
  (`j_man`/`j_man` for all three Stadtbach stages, `j_3`/`j_1` for all three
  Memmingen stages, **pre-eta-fix AND pre-CAPEX-fix as of 2026-07-20 morning
  — re-verify against the post-re-run file, do not assume these hold**) —
  not any earlier screening-stage number that might still be floating
  around other output files in the repo.
- **`scripts/paper_2/scenario_runner.py` reproducibility gotcha (found
  2026-07-20, fixed same day)**: unlike its siblings (`run_paper2_full.py`,
  `enumerate_endog_siting.py`), this module was missing the
  `sys.path.insert(0, str(_ROOT))` line that makes `calion` importable when
  the script is run directly. On a clean clone, `python
  scripts/paper_2/scenario_runner.py ...` failed with `ModuleNotFoundError:
  No module named 'calion'`; only `python -m scripts.paper_2.scenario_runner
  ...` worked (it adds the repo root to `sys.path` via cwd, masking the
  missing insert). Fixed by adding the same insert its siblings already have
  — direct script invocation works now too, but if you're on a checkout from
  before this fix, use the `-m` form or update the file.

## Still open — genuinely not done, needs the campaigns above to finish first

- **Memmingen eta-harmonization re-run (highest priority — blocks all
  Memmingen writing)**: Wave 1 (17 scenarios) + Wave 2 (`MM-S4` 3×36-pair
  enumeration) both running, multi-day.
- **Stadtbach HP-CAPEX-harmonization re-run (highest priority — blocks all
  Stadtbach writing)**: Wave A (23 scenarios) + Wave B (`SB-S6` 3×25-pair
  enumeration) both running, multi-day. Also killed the Stadtbach F3 sweep
  (31/49 points lost) and the whole F7 orchestrator — both need a fresh
  relaunch once Wave A/B land (see "What's still running").
- **Once BOTH of the above finish**: regenerate `scenarios_kpis.csv` +
  T3/T4/T5 + the F3-siting CSV, **re-verify T5's exclusion filter still
  keeps the enumeration sub-pairs and superseded monolithic dirs (both
  `SB-S6-*` and `MM-S4-*`) out of the headline gap statistics** (mechanism
  already built, just needs re-confirming against fresh data — see "What's
  still running"), then update every number in this README and clear both
  banners. Do this once, after both networks are done.
- **Relaunch F3 (both networks) and F7 (both networks)** after the above —
  Memmingen's copies are separately stale from the eta fix even though
  their processes weren't killed; Stadtbach's were killed outright. All
  four (F3×2, F7×2-networks-in-one-campaign) need a fresh run.
- **F8**: pressure-export fix and monotonicity annotation are done; waiting
  only on `MM-S1-HK0`'s full-year re-solve to finish before regenerating the
  final figure. No further investigation needed — this is a "wait for the
  solve" item, not an open question.
- **F3 (capacity-sweep heatmap)**: campaign running for the first time;
  `build_f3()`'s plotting logic itself has not yet been exercised against
  real sweep data and should be spot-checked once the sweep finishes.
- **F7 (sensitivity tornado)**: campaign running (extraction bug fixed);
  `build_f7()`'s plotting logic similarly unexercised against real data yet.
- **Citation library**: only Paper 1's `cas-refs.bib` is present. If a
  Paper-2-specific reference library exists (HP+TES co-sizing studies, F3
  heatmap comparators), it should be added before the related-work section is
  drafted.
- **ECM Guide for Authors**: only the two headline numbers (9,000 words,
  ≤15 figures+tables) are already encoded in the prompt spec; the full guide
  (reference style, highlights, graphical abstract, submission checklist)
  hasn't been fetched.
- **Paper 1 ↔ Paper 2 boundary**: which claims belong to which paper when
  both get cross-cited isn't written down anywhere yet — worth a short
  explicit note before drafting the introduction.

## Refreshing this snapshot

From the repo root:

```bash
# docs
cp docs/paper_2/CALION_Paper2_Implementation_Statement.md paper2_package/01_specification/

# figures/tables
rm -rf paper2_package/02_figures_tables && mkdir -p paper2_package/02_figures_tables
cp -r results/paper2_figures/* paper2_package/02_figures_tables/

# configs
rm -rf paper2_package/03_configs && mkdir -p paper2_package/03_configs
cp -r configs/paper_2 paper2_package/03_configs/
cp -r configs/stadtbach paper2_package/03_configs/

# implementation code
rm -rf paper2_package/04_implementation/calion paper2_package/04_implementation/scripts_paper_2
cp -r calion paper2_package/04_implementation/
cp -r scripts/paper_2 paper2_package/04_implementation/scripts_paper_2
find paper2_package/04_implementation -type d -name "__pycache__" -exec rm -rf {} +
```

The canonical KPI source is `output/paper2_runs/scenarios_kpis.csv`
(regenerate via `kpi_calculator.compute_all_kpis(Path('output/paper2_runs'))`
if any scenario is re-solved) — **not** `results/scenarios_kpis.csv`, which
despite being referenced in the original prompt spec was never actually the
path the real pipeline writes to; treat any reference to that path elsewhere
as aspirational/stale.
