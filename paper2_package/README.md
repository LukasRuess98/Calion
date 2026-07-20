# Paper 2 Design Package — status snapshot 2026-07-19 (campaign COMPLETE, NOT fully paper-ready)

This folder is the handoff package for designing the CALION Paper 2 manuscript
(target: Energy Conversion and Management). **The full 46-scenario campaign is
done** (both networks, including the F3 endogenous-siting scenarios via an
enumeration decomposition) and the economics (T3/T4/T5, the headline numbers)
are final and trustworthy. **However, a full visual re-check of every figure
(done in this pass) found one rendering bug (fixed) and one still-open,
unresolved physical/data issue in F8** — see "What changed this pass" and
"Still open" below. **Verdict: the numeric/economic backbone is ready to
write from now; F8 is not, and F3/F7 don't exist yet.** Read this whole file
before writing anything.

## TL;DR for the writing agent

- **Economics (TAC, LCOH, CAPEX/OPEX, CO₂) are final and trustworthy** for all
  46 scenarios. Use `02_figures_tables/tab_T3_stadtbach_kpis.csv` (26 rows) and
  `tab_T4_memmingen_kpis.csv` (20 rows).
- **Figures ready to use as-is**: F1 (model architecture), F2 (network maps),
  F4 (k↔COP↔V_TES coupling), F5 (cost split), F6 (endogenous vs. fixed
  siting — a text-overlap rendering bug was found and fixed this pass, see
  below), F9 (TES SOC time series).
- **F8 (spatial T/p profile) is NOT ready — do not use as-is.** A visual
  check this pass found two real problems, neither fixed: (1) the pressure
  sub-panels are completely empty for both networks ("no pressure data") —
  a pre-existing export gap, not something wired up this session; (2) the
  Stadtbach temperature panel is **not monotone** (dips at `j_pss` then rises
  again at `j_hws`) despite the figure's own title claiming a "monotone fall"
  check — traced to `j_pss` having a local generator (`HWS_BOILER`) injected
  into what the figure treats as a simple linear trunk, which may be a real
  L3+ per-node temperature-parameter artifact rather than a plotting bug.
  Needs its own investigation before this figure (or any "monotone
  propagation" claim about Stadtbach) can be used. See "Still open" below.
- **Figures NOT ready — do not fabricate placeholders**: F3 (capacity-sweep
  heatmap) and F7 (sensitivity tornado) each need a separate analysis module
  that hasn't been run (see "Still open" below). If the manuscript structure
  needs a placeholder for these, say so explicitly rather than estimating.
- **One correction made in this pass, worth knowing about**: the F3
  endogenous-siting scenarios' auxiliary `_summary.json` files (produced by a
  parallel work session, not part of this package) reported the wrong
  "best" site pair for the three Stadtbach `SB-S6` stages — they pointed at
  an early screening-stage leader that a later, more-converged run
  (`(j_man, j_man)`) beat by ~49 %. This package's tables use the **verified
  true winner** (see `tab_T3b_T4b_f3_endogenous_siting_FINAL.csv` and the
  Implementation Statement Part G.8 for the full trace). If you see the older
  number (`j_hkw`/`j_pss`, ≈8.80 M€) anywhere else in the repo, it is stale.

## Headline results (for quick reference — verify against the CSVs before quoting)

**Stadtbach** (BC-SB baseline TAC = 11.033 M€/a):
- Best fixed-siting result: `SB-S2-HK2` (TES at a pre-selected node), TAC =
  4.420 M€/a, −59.9 % vs. baseline.
- Best endogenous-siting result: `SB-S6-HK2` (free HP+TES placement,
  `hp=j_man, tes=j_man`), TAC = 4.437 M€/a, −59.8 % — essentially tied with
  the best fixed case, marginally worse (~0.4 %). Free siting does **not**
  beat a well-chosen fixed node here.
- All three `SB-S6` stages independently converge on the same site pair
  (`j_man`/`j_man`), a strong, reproducible result — see
  `tab_T3b_T4b_f3_endogenous_siting_FINAL.csv`.

**Memmingen** (BC-MM baseline TAC = 0.507 M€/a):
- Best fixed-siting result: `MM-S3-HK2`, TAC = 0.335 M€/a, −33.9 %.
- Best endogenous result overall: `MM-S5-HK2` (**colocated** HP+TES, not the
  free-siting `S4` family), TAC = 0.299 M€/a, −41.0 % — colocation beats free
  siting for Memmingen, the opposite pattern from Stadtbach. `MM-S4`
  (free siting, `hp=j_3, tes=j_1`) reaches TAC = 0.312 M€/a at best (HK2),
  still better than any fixed-node scenario but not as good as colocating.
- This Stadtbach-vs-Memmingen asymmetry (free siting helps in one network,
  colocation helps in the other) is a genuine, topology-dependent finding
  worth a sentence in the discussion — it is not an artifact.

**Validation (T5)**: 46/46 scenarios solved successfully; median MIP gap
1.84 %; annual COP range 2.43–3.67 (physically plausible). The MW-closure
statistic (22.98 % mean error, 12/41 passing ≤2 %) looks alarming at first
glance — **it is a known methodology limitation of that specific check, not
evidence of an energy-balance violation.** See "Known caveats" below before
citing it as a problem in the manuscript; do not present it as unexplained.

## What's in here

- `01_specification/` — the governing documents:
  - `CALION_Paper2_Implementation_Statement.md` — full model/spec
    traceability, current as of 2026-07-19. Parts G.10–G.12 (new this pass)
    document the reporting-pipeline audit, the TES dispatch-export bug and
    fix, and the resolution of the Memmingen P1↔P2 consistency check. **This
    is the primary methods-section source and the place to check before
    trusting any specific number's provenance.**
  - `CALION_Paper2_Sweep_und_Grafiken_Prompt_v2_final.md` — the figure/table
    spec (F1–F9, T1–T5) and capacity-sweep module spec. Still the
    authoritative to-do list for the two open figures.
  - `CALION_Paper2_Sweep_und_Grafiken_Prompt.md` — v1, history only.
  - `CALION_Paper2_Spezifikation.docx` — the original Version 1.0 spec.
- `02_figures_tables/` — current state of `results/paper2_figures/`:
  - `tab_T1a/T1b` — network characteristics / generator portfolio (static,
    config-derived, unaffected by the campaign).
  - `tab_T2` — scenario matrix (46 rows, static).
  - `tab_T3_stadtbach_kpis` (26 rows), `tab_T4_memmingen_kpis` (20 rows) —
    **final economics**, see headline numbers above.
  - `tab_T3b_T4b_f3_endogenous_siting_FINAL` — the corrected F3
    (`SB-S6`/`MM-S4`) results, with HP/TES site, MIP gap, and full KPI set;
    supersedes what you'd otherwise read out of T3/T4's own `SB-S6-HK0` /
    `MM-S4-HK0` rows if this package's fix had not been applied.
  - `tab_T5_validation` — solver-status census, MW-closure stat (see caveat
    above), COP plausibility range, P1↔P2 consistency (see caveat below).
  - `fig_F1/F2/F4/F5/F6/F8/F9` (svg+pdf+png) — ready to use.
  - `fig_F8_trunk_candidates_DRAFT`, `fig_palette_preview_DRAFT` — approval
    artefacts (trunk-path decision, color palette), not manuscript figures.
  - **Missing on purpose**: F3, F7 (see "Still open").
- `03_configs/` — full config trees (`paper_2/`, `stadtbach/`) — unchanged
  this pass, still current.
- `04_implementation/` — source code snapshot (`calion/`, `scripts_paper_2/`),
  refreshed this pass to include every file touched by the fixes described
  below (`calion/run/result_collector.py`, `calion/run/solver.py`,
  `scripts/paper_2/figures/gen_tables.py`,
  `scripts/paper_2/extract_artefacts_p2.py`).
- `05_paper1_reference/` — Paper 1 materials for consistency (submitted
  manuscript, Elsevier template, equations/methodology docs, published
  figures). Unchanged this pass.

## What changed this pass (2026-07-16 to -19) — read this before trusting old caveats

A reviewer-style critique of the earlier campaign surfaced four apparent
blockers. All four are now resolved; three were reporting-pipeline bugs, one
was a real (now-fixed) data-export bug that never touched the economics:

1. **Stale aggregation file + a dict-key typo** made T3/T4/T5 look like most
   runs hadn't converged and showed impossible values (e.g. constant
   `E_TES=500 MWh` even for no-TES baselines). Both fixed; every number in
   T3/T4/T5 is now read from live, current per-scenario data.
2. **A real bug found and fixed**: TES charge/discharge/SOC data was silently
   dropped from the dispatch export for every TES-active scenario, on both
   networks (a type-matching gate never recognized the investable TES's
   `geometric_storage` asset type, and a variable-name mismatch broke the
   SOC read even when the gate was fixed). This made the MW-closure
   validation check look far worse than reality. **Verified: `economics.csv`
   — and therefore every TAC/LCOH/CO₂ number in T3/T4 — was never on this
   broken code path.** All 27 TES-active scenarios were re-solved after the
   fix to get correct TES-utilization data (`TES_cycles_per_a`,
   `TES_utilization_pct`) and clean validation numbers; the economic
   conclusions did not change (verified byte-for-byte identical TAC values
   before/after re-solve).
3. **The Memmingen P1↔P2 OPEX consistency check** (T5, still shows "FAIL,
   124 %") is not a bug: it compares Paper 2's `BC-MM` (a genuine
   zero-investment "Bestand" baseline) against Paper 1's `L3` reference
   (which assumed a small pre-existing 5 MW HP+EK). These are two
   deliberately different scenarios; a large deviation is the *expected*
   outcome, not evidence of a defect. Recommend retiring this specific check
   or repointing it at a new explicitly-5 MW-fixed scenario if a
   like-for-like cross-check is still wanted for the manuscript — not done
   in this pass, awaiting a decision on whether it's still needed.
4. **This session's own correction**: the F3 (`SB-S6`/`MM-S4`) enumeration
   campaign's `_summary.json` files (built by a separate, parallel session)
   were stale for the three Stadtbach stages, still pointing at a
   screening-stage leader that a later Stage-2 re-verification had already
   beaten by ~49 %. Traced by directly comparing every individual
   `pair_*.json` result file rather than trusting the summary — see
   `tab_T3b_T4b_f3_endogenous_siting_FINAL.csv` for the corrected numbers,
   folded into T3/T4 and figures F5/F6.
5. **F6 rendering bug found and fixed in a full visual re-check of every
   figure**: the "Value of free TES/WP siting" bar chart placed each data
   label past the bar's tip (away from zero); for a long negative bar
   (Memmingen, −10.7 %) this pushed the label text off the left edge of the
   axes, where it overlapped the "Memmingen" category tick label —
   unreadable. Fixed by widening the axes' x-margins to fit the longest
   label (`scripts/paper_2/figures/fig_p2_campaign.py::build_f6`).
   Regenerated and visually re-verified clean.
6. **F8 checked, NOT fixed — two real problems found**, see the TL;DR above
   and "Still open" below. This figure should not be used until both are
   resolved.

## Known caveats to state explicitly in the manuscript

From Implementation Statement Part D (O-1…O-10) and Part G:
- O-1: WP/EK/TES cost coefficients are literature/VDI-2067 assumptions, not
  vendor quotes.
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
- G.8: the `(hp_site, tes_site)` pairs quoted anywhere for `SB-S6`/`MM-S4`
  must be the ones in `tab_T3b_T4b_f3_endogenous_siting_FINAL.csv`
  (`j_man`/`j_man` for all three Stadtbach stages, `j_3`/`j_1` for all three
  Memmingen stages) — not any earlier screening-stage number that might
  still be floating around other output files in the repo.

## Still open — genuinely not done, needs its own session

- **F8, problem 1 — pressure data never populated.** Traced to
  `scripts/paper/extract_artefacts.py`'s `nodes_state_hourly.parquet` writer:
  it reads per-node pressure from a wide-format `{node}_P` column in
  `output/paper2_runs/thermal_network/nodes/nodes_timeseries.csv`, but that
  file (confirmed for both networks) has zero `_P`-suffixed columns at
  all — only `_T_supply`/`_T_return`/`_Q_demand`. Pipe-level pressure drop
  and pump power ARE modeled and solved (confirmed elsewhere in the
  Implementation Statement), so this is a real, separate export gap: no
  per-*node* pressure was ever wired into this specific timeseries export,
  on either network, for the whole campaign. Also note: this file lives at
  a **shared, non-scenario-specific path** (same class of issue as the
  `unified_timeseries.csv` finding in Part G.10) — worth checking whether it
  reflects the right scenario at all once pressure export is fixed.
- **F8, problem 2 — Stadtbach's temperature panel is not monotone.** The
  trunk `j_hkw → j_pss → j_hws → j_don_bosco` is a genuine simple linear
  pipe chain (confirmed against `Stadtbach_topo.yaml`, no mesh mixing at
  either node), yet `T_supply` drops sharply at `j_pss` (~70 °C) then rises
  again at `j_hws` (~98 °C) before easing off toward `j_don_bosco`. `j_pss`
  is the site of a local generator (`HWS_BOILER`), which is the likely
  cause, but a local generator alone shouldn't make a *downstream* node's
  temperature exceed its *upstream* neighbor's in a simple chain — suspect
  the L3+ per-node temperature-classification mechanism (some nodes carry a
  solved, propagated `T_supply` Var; others may carry a Param driven
  independently by the heating-curve setpoint, per
  `network_manager.py::_classify_node_temperature_mode` referenced elsewhere
  in this package's code) rather than a real physical reheat. Not resolved
  this pass — needs someone to trace which of the two mechanisms each of
  these four nodes actually uses before this figure (or any claim of
  "monotone propagation" for Stadtbach) can be presented as validated.
  Memmingen's own panel (radial tree, single mechanism throughout) IS
  monotone and did not show this problem — the issue looks specific to
  nodes whose local generation type triggers the alternate temperature mode.
- **F3 (capacity-sweep heatmap, LCOH over Q_WP × V_TES)**: needs
  `capacity_sweep.py` (Part A of the prompt spec) run for a representative
  scenario per network, producing `results/sweep_{network}_{scenario_id}.csv`.
  Not started. The prompt spec explicitly says the representative-scenario
  choice ("A.6 decision") can't be made before the campaign finishes — the
  campaign is now finished, so this can proceed; it just hasn't yet.
- **F7 (sensitivity tornado)**: `sensitivity.py`'s existing run only recorded
  solve time/status, not the TAC deltas the figure needs. Needs a re-run with
  TAC capture wired in.
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
