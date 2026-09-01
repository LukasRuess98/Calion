# Paper 2 — Figure/Table Provenance & Build Status

Generated 2026-08-30. All elements below derive from the **frozen campaign**
`output/_prefix_backup_2026-07-26/paper2_runs/` (produced by code commit
`e8e445e`, 2026-07-22), aggregated to `03_data/scenarios_kpis.csv` +
`baseline_kpis.csv` via `04_scripts/kpi_calculator.py`.

> ⚠ **Reproducibility caveat (see QC_REVIEW.md #1):** current `main` has drifted
> from `e8e445e` (lateral-pipe losses + pressure physics added 2026-07-26+) and
> does **not** reproduce these numbers (MM-S4 gives 493k on current code vs 299k
> frozen). Treat `e8e445e` + the current `configs/paper_2/` as the canonical
> reproduction state, or re-run the whole campaign on current code.

## Data source of truth
| File | Built by | From |
|---|---|---|
| `03_data/scenarios_kpis.csv` | `kpi_calculator.compute_all_kpis` | frozen 07-26 run dirs |
| `03_data/baseline_kpis.csv` | same | frozen BC-MM / BC-SB |

**KPI bug fixed 2026-08-30:** the Memmingen baseline was being overwritten by a
January-only diagnostic (`BC-MM-DIAGJAN`), corrupting every Memmingen
`cost_reduction_pct` (−289% → correct **+44.8%**). Fix = `_is_diagnostic()` skip
in `kpi_calculator.compute_all_kpis`.

## Figures
| Fig | What | Generator | Status |
|---|---|---|---|
| ~~F1~~ | ~~Model architecture~~ | — | ❌ **DROPPED** (2026-08-30, user) — cluttered; the L3+ heat/mass balance + McCormick move to §2 as numbered equations. Files archived in `_dropped/`. |
| F2 | Network maps (both) | `fig_f2_network_maps.py` | ⚠ user is **replacing** it. (Confirmed: S2 & S3 are the *same* node — j_12 / j_man — differing only by hot charging.) |
| F3 | Capacity–cost surface | `fig_p2_campaign.build_f3` | 🔄 **sweep re-running** in the campaign-era worktree (MM-S1-HK0 + SB-S2-HK0, 500 s/point ≈6% gap surface); figure builds when it lands |
| F4 | Heat-curve → COP → cost trajectory | `fig_p2_campaign.build_f4` | ✅ **REDESIGNED** (2026-08-30) — old 2×3 TES-volume "pyramid" was solver noise (MM TES negligible, SB capped). New 2-panel: (L) COP vs HK both nets rise; (R) TAC indexed to HK0 vs COP → MM −4.4%, SB flat. Finding: heat-curve benefit is **electrification-dependent**. |
| F5 | Cost & emissions vs baseline (stacked) | `fig_p2_campaign.build_f5` | ✅ rebuilt (corrected KPIs); components recoloured to **Paper 1 palette** (navy/teal/amber) per user |
| F6 | Siting landscape (TAC over HP×TES nodes) | `fig_p2_campaign.build_f6` | ✅ **REDESIGNED** (2026-08-30) — replaced delta bars with an enumeration **heatmap** (% above best siting, star=optimum). Shows siting is decisive: SB worst 77× best, MM 4×. |
| F7 | Sensitivity tornado | `fig_p2_campaign.build_f7` | ✅ **built (tier-1)** + professionalised (split teal/amber = decrease/increase, value labels, net-coloured titles). Fixed-design analytical (CO₂/discount exact, elec via net position, gas first-order). SB gas-dominated (±22%). Data: `03_data/sensitivity_tier1.csv`. Tier-2 re-dispatch (~1–3 h worktree) if wanted. |
| F8 | Spatial temp/pressure profile (supplement) | `fig_p2_campaign.build_f8` | ✅ temperature recoloured **red** per user. ⚠ CAVEATS: MM T near-flat (0.4 °C, axis-zoom exaggerates); **pressure saturates at 20 bar = j_12/j_pss ceiling artifact** (needs caption caveat). |
| F9 | Storage SoC — fixed vs endogenous (supplement) | `fig_p2_campaign.build_f9` | ✅ **REDESIGNED** (2026-08-30) — best-fixed (dashed) vs best-endogenous (solid) per network. MM endog cycles more; SB fixed cycles hard while endog is flat. |

Network identity colour is fixed across the set: **Memmingen = FHG blue, Stadtbach = FHG green.**  Cost components & Paper-1-aligned elements use `P1_NAVY/P1_TEAL/P1_AMBER/P1_RED` (added to `_style.py`).

## Tables
| Tab | What | Generator | Status |
|---|---|---|---|
| T1a/T1b | Network characteristics / generator portfolio | `gen_tables.build_t1` | ✅ current |
| T2 | Scenario matrix | `gen_tables.build_t2` | ✅ current |
| T3 | Stadtbach KPIs | `gen_tables.build_t3` | ✅ rebuilt + `V_TES [m³]` column |
| T4 | Memmingen KPIs | `gen_tables.build_t4` | ✅ rebuilt (corrected) + `V_TES [m³]` |
| T5 | Validation | `gen_tables.build_t5` | ⚠ built; closure metric bugged (see QC #2), MIP gaps not extracted |

## Corrected headline numbers (HK2, TAC €/a)
- Memmingen best: **MM-S5-HK2** 278,868 (+44.8% cost, +20.8% CO₂)
- Stadtbach best fixed: **SB-S4-HK2** 9.577 M (+13.2%) — moved from old SB-S2
- Stadtbach endogenous: **SB-S6-HK2** (j_pss/j_pss) 9.275 M (+15.9%) — beats best fixed
