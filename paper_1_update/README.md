# Paper 1 — update package (everything to revise the manuscript)

Corrected results after four model fixes (pump-attribution BFS, demand_fraction²,
fine-PWL friction, 0.6 bar transfer-station Δp). Generated from an isolated faithful
worktree at the paper's commit **c19d690** (reproduces the submitted numbers to the
cent before the fixes). Your Paper-2 working tree was not disturbed.

## What's here
| File / folder | Use |
|---|---|
| **`MANUSCRIPT_UPDATE_PROMPT.md`** | The authoritative, line-by-line edit checklist (old→new for every number, exact §/table/line targets). START HERE. |
| **`L3NL_LINEARIZATION_ANALYSIS.md`** | Why the L3NL re-solve is intractable + the exact-decomposition linearisation-error result (feeds prompt §2). |
| `Paper1_draft_MainEingereicht.tex` | Copy of the submitted manuscript to edit. |
| `figures_corrected/` | All 14 figures regenerated from the corrected data (pdf + png + the plotted csv). |
| `impact_analysis.json` | Machine-readable alt→new for every reported number. |
| `corrected_data/` | `synth_gap_summary.csv` (36-config gaps) + `level_consistency.json`. |
| `patches/` | The three code diffs vs c19d690 (apply to reproduce). |

## The corrected numbers (summary)
**Primary:** L1→L3 **13.03 %** (paper 13.0), L2→L3 **2.54 %** (2.6), **L3→L3⁺ +0.33 %**
(+735 EUR; paper +0.11 %/+255), pump electricity **10.6 MWh (0.11 % of heat)**.
**Sensitivity** L3–L3⁺: −0.14 % … +0.54 % across 11 scenarios (full table in the prompt).
**Synth (n=36):** topology **+20.2 %** and heat-loss **+20.0 %** reproduce; **pressure-drop
L2→L3 +0.02 % → +0.165 %**; delay L3→L3⁺ **≈0** reproduces.
→ Topology dominates pumping ~40×; the "pumping marginal" conclusion holds.

## Figures — mapping and which changed
Script → paper F-number (from `run_all_figures.py`). **Bold = changed by the fixes; regenerate/replace these.** The rest reproduce the submitted version.

| script (in `figures_corrected/`) | F# | changed? |
|---|---|---|
| fig_comparison_design | F1 | no |
| fig_topology | F2 | no |
| fig_cost_topology | F3 | no (topology reproduces) |
| **fig_cost_extended** | **F4** | **yes** (L3→L3⁺) |
| **fig_cost_waterfall** | **F5** | **yes** (cost decomposition) |
| **fig_pump_pwl_vs_quad** | **F6** | **yes — but see caveat** |
| fig_storage_winterweek | F7 | no |
| fig_storage_charge_hour | F8 | no |
| fig_dispatch_heatmap | F9 | no |
| fig_synth_topology_gap | F10 | no (topology reproduces) |
| **fig_synth_physics_gap** | **F11** | **yes** (L2→L3 pressure drop) |
| fig_synth_lin_error | F12 | **see caveat** |
| **fig_tornado_sensitivity** | **F13** | **yes** (gap-stability) |
| fig_solve_time | F14 | no |

> Map F-number → your manuscript `Figure_N` yourself (the submission curated 9 of them);
> the content names above make it unambiguous.

## Two caveats (read before using F4 / F6 / F12)
1. **`cost_pump_eur` is not wired at c19d690** (a separate reporting bug we did NOT
   port — only the objective was corrected). So in **F4** the "Pump" bar reads 0; the
   pump cost is real but sits inside the Electricity + CO₂ bars. If you want an explicit
   pump bar, say so and I'll port the reporting fix and re-plot.
2. **F6 (pump PWL-vs-quad) and F12 (synth linearisation error) depend on a full L3NL solve**,
   which is now **intractable** with the corrected pump physics (BFS attribution → ~14× more
   bilinear constraints → 58,774; 24 h/window found no incumbent). So F6/F12 stay as submitted.
   The *number* that mattered — the L3⁺→L3NL linearisation error — was instead obtained by
   **exact decomposition** on the L3⁺ dispatch (`L3NL_LINEARIZATION_ANALYSIS.md`): pump-friction
   error +0.031 %/+0.027 %, station Δp cancels ⇒ submitted +0.35 %/+0.50 % gap stands. Table
   `tab:cost_extended` gets a footnote, not new numbers (see prompt §2).

## Reproduce
Apply the three patches in `patches/` to a clean checkout at commit `c19d690`, then run
the primary/sensitivity/synth as in the Zenodo package (`zenodo_paper_1/`).
