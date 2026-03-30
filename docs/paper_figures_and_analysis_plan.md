# Paper Figures, Analyses, and Gap Analysis
## Spatial Resolution Study: 1-node / 5-node / 30-node under Perfect Forecast

---

## 1. What the framework already produces (no extra work)

These are generated automatically by `export_workflow_results()` after each run.

| Output | File | Notes |
|--------|------|-------|
| Heat dispatch stack | `heat_balance.pdf` | One per level — needs combining |
| Electricity balance | `electric_balance.pdf` | One per level |
| Storage SOC | `storage_operation.pdf` | One per level |
| Cost breakdown | `cost_breakdown.pdf` | One per level |
| Full timeseries | `pf_timeseries.csv` | All variables at 1-h resolution |
| Pipe losses per pipe | `thermal_network/pipes_timeseries.csv` | L2 and L3 only |
| Node temperatures | `thermal_network/nodes_timeseries.csv` | L2 and L3 only |
| Network summary | `thermal_network/network_summary.json` | |
| Cost JSON | `costs.json` | All cost components |
| Design JSON | `design.json` | HP and storage sizing |
| Solver stats | logged to console | Need to capture explicitly |

---

## 2. Figures needed for the paper

### MUST-HAVE (paper not publishable without these)

---

#### Fig 1 — System topology diagram (3 panels)
**What:** Schematic of the 3 model levels side by side.
Left: single node with assets. Middle: 5-node topology with pipe lengths. Right: 30-node star-of-stars.

**Framework status:** ❌ Does not exist — must be drawn.
**Recommendation:** Draw in draw.io / PowerPoint / LaTeX TikZ. Simple boxes and arrows.
One diagram, 3 sub-panels (a), (b), (c). Include pipe lengths and diameters in annotations.

---

#### Fig 2 — Annual heat dispatch comparison (3 panels, 1 representative week)
**What:** Stacked area chart of heat sources (boiler, HP, storage discharge) plus demand line.
One panel per level. Show a winter week (e.g. Jan 8–14) when heat losses are largest.

**Framework status:** ⚠️ Framework generates individual `heat_balance.pdf` per run.
Need a 3-panel combined figure.
**Required data columns (from `pf_timeseries.csv`):**
- `waermebedarf_MWth` (demand)
- `boiler_main_Q_th_MW`
- `hp_main_Q_th_MW`
- `TES_discharge_MW`, `TES_charge_MW`
- `Q_dump_MWth`

**Gap:** Need a script that reads all three CSVs and produces one combined 3-panel matplotlib figure.

---

#### Fig 3 — Annual cost breakdown (grouped bar chart)
**What:** Grouped or stacked bars for L1 / L2 / L3 showing:
- Energy cost (grid electricity)
- Fuel cost (gas)
- CO₂ cost
- Demand charge
- Storage OPEX (dump cost proxy)

**Framework status:** ⚠️ Framework generates individual `cost_breakdown.pdf` per run.
Need a cross-level comparison bar chart.
**Required data:** `costs.json` from each run.

**Gap:** Need a script that reads 3 `costs.json` files and produces one grouped bar chart.

---

#### Fig 4 — Pipe heat loss profile: L2 vs L3
**What:** Line plot of total hourly pipe heat loss [MW] over the year for L2 and L3.
Show seasonal pattern (winter peaks). Optionally show loss fraction (loss / demand [%]).

**Framework status:** ✅ Data in `thermal_network/pipes_timeseries.csv` (column `{pipe_id}_Q_loss`).
Need to sum across all pipes per timestep.
**Gap:** Small post-processing script to aggregate pipe losses.

---

#### Fig 5 — Tornado chart (sensitivity indices, all 3 levels)
**What:** Horizontal bar chart showing sensitivity index $S_i$ for each of the 7 parameters,
with 3 colour-coded bars per parameter (L1, L2, L3).

**Framework status:** ❌ `calculate_sensitivity_indices()` computes the values,
but no tornado chart plotter exists in the framework.
**Gap:** Need to (a) wire up sensitivity runs, (b) write a tornado chart function.

---

#### Table 1 — Annual cost breakdown (numbers for Fig 3)
All cost components for L1 / L2 / L3. Columns: L1, L2, L3, Δ L2−L1 [%], Δ L3−L1 [%].
**Required data:** `costs.json` from each run.
**Framework status:** ✅ All fields present — just need aggregation script.

---

#### Table 2 — Key operational KPIs
| Metric | L1 | L2 | L3 |
|--------|----|----|-----|
| Total heat generated [GWh] | | | |
| HP full-load hours [h] | | | |
| Boiler utilisation [%] | | | |
| Storage cycles per year [−] | | | |
| Grid import [GWh] | | | |
| Grid export [GWh] | | | |
| CO₂ emissions [t] | | | |
| Annual pipe heat loss [GWh] | — | | |
| Loss as % of demand [%] | — | | |

**Required data:** `summary_sections` from result_collector.
**Framework status:** ✅ All fields present in `costs.json` / `design.json`.

---

#### Table 3 — Network characteristics (L2 and L3)
| Property | L2 (5-node) | L3 (30-node) |
|----------|-------------|-------------|
| Number of nodes | 5 | 29 |
| Number of pipes | 4 | 28 |
| Total pipe length [m] | 6 300 | 14 250 |
| Min / max pipe diameter [mm] | 350 / 500 | 150 / 600 |
| Annual supply loss [GWh] | | |
| Annual return loss [GWh] | | |
| Total loss [GWh] | | |
| Loss / annual demand [%] | | |
| Peak hourly loss [MW] | | |

**Framework status:** ✅ Topology known from configs. Losses from pipe timeseries.

---

#### Table 4 — Solver statistics
| Metric | L1 | L2 | L3 |
|--------|----|----|-----|
| Continuous variables | | | |
| Binary variables | | | |
| Constraints | | | |
| Solve time [s] | | | |
| MIP gap achieved [%] | | | |

**Framework status:** ⚠️ Solve time can be captured from HiGHS output / timing.
Variable/constraint counts need `--save-lp` flag or Pyomo model inspection.
**Gap:** Add timing wrapper around solver call; inspect model size.

---

### NICE-TO-HAVE (strengthen the paper significantly)

---

#### Fig 6 — Load duration curve (heat) — 3 lines in one plot
**What:** Sorted annual demand met by source. X-axis = hours/year (0–8760).
Y-axis = heat output [MW]. Three lines (L1/L2/L3) nearly identical in total,
but L2/L3 curves sit slightly higher (losses force more generation).

**Framework status:** ❌ Not implemented.
**Effort:** Small — sort `pf_timeseries.csv` data and plot.
**Scientific value:** Shows *when* the copperplate model underestimates most (cold winter hours).

---

#### Fig 7 — Seasonal dispatch heatmap (calendar view)
**What:** 365×24 grid heatmap. Colour = HP share of total heat output [%].
One panel per level. Shows dispatch pattern shifts when network losses are present.

**Framework status:** ❌ Not implemented.
**Effort:** Medium — reshape timeseries to (365, 24) matrix and plot with matplotlib `imshow`.
**Scientific value:** Reveals structural differences in how the optimizer responds to losses.

---

#### Fig 8 — Storage state-of-charge comparison (3 lines, 1 year)
**What:** Daily average SOC [MWh] for all three levels in one plot.
Shows whether the optimizer uses storage differently when network losses are present.

**Framework status:** ⚠️ `storage_operation.pdf` exists per run. Need combined single figure.
**Effort:** Trivial — read `TES_SOC_MWh` from 3 CSVs and overlay.

---

#### Fig 9 — Pipe loss spatial map (L3 only)
**What:** Network diagram with pipes coloured by annual heat loss [MWh/yr].
Node size proportional to zone demand. Qualitative illustration of where losses concentrate.

**Framework status:** ❌ Not implemented (no geographic coordinates in current configs).
**Effort:** Medium — use networkx + matplotlib. Assign representative x/y positions to nodes
(no real coordinates needed — schematic layout is sufficient).
**Scientific value:** High — visual proof that a lumped model misses spatial heterogeneity.

---

#### Fig 10 — Sensitivity: cost range bars (waterfall style)
**What:** For each of the 7 sensitivity parameters, show [min cost, base cost, max cost]
as a floating bar, grouped by level (L1/L2/L3). Colour gradient from green (low) to red (high).

**Framework status:** ⚠️ `format_sensitivity_table()` produces the data. No waterfall plotter.
**Effort:** Medium.

---

#### Fig 11 — HP operating hours vs. COP (scatter)
**What:** Scatter plot: x = COP value at each timestep, y = HP output [MW].
Shows operating envelope. One panel per level — does the spatial model change when the HP runs?

**Framework status:** ✅ Data in `HP1_COP` and `HP1_Q_th_MW` columns.
**Effort:** Trivial — scatter from timeseries CSV.

---

## 3. Sensitivity analysis design

### Standard 7-parameter OAT study (mandatory for paper)

| Parameter | Config path | Base | Low | High | Justification |
|-----------|-------------|------|-----|------|---------------|
| Gas price | `fuels.gas.price_eur_mwh` | 45 EUR/MWh | 36 (−20%) | 54 (+20%) | Eurostat price range 2020–2024 |
| Electricity grid cost | `grid.gridcost_eur_mwh` | 20 EUR/MWh | 15 (−25%) | 30 (+50%) | German grid surcharge variation |
| HP COP factor | `assets.hp_main.cop_default` | 3.5 | 3.0 (−14%) | 4.0 (+14%) | Season / source temperature range |
| CO₂ price | `costs.co2_price_eur_per_t` | 100 EUR/t | 65 (−35%) | 150 (+50%) | EU ETS 2023–2024 range |
| Storage energy capacity | `assets.tes_main.energy_mwh` | 500 MWh | 250 (−50%) | 750 (+50%) | Sizing uncertainty |
| Boiler efficiency | `assets.boiler_main.thermal_efficiency` | 0.90 | 0.85 (−6%) | 0.95 (+6%) | Technology range |
| HP min load | `assets.hp_main.min_load` | 0.20 | 0.10 (−50%) | 0.30 (+50%) | Operating constraint range |

Run: 7 parameters × 3 variations × 3 levels = **63 runs** (manageable, ~5–10 min each on HiGHS).

**Output per run:** total cost, fuel cost, CO₂, HP utilization.
**Key chart:** Tornado chart (Fig 5) — ranks which parameter most affects each level.

**Central hypothesis for paper:** The *ranking* of sensitivities should be similar across levels,
but the *magnitude* of gas-price sensitivity will be slightly higher for L2/L3 (more gas burned to cover losses).

---

### Additional scenario analysis (nice-to-have)

#### Scenario A — Low-temperature network (4GDH)
Change supply/return temps to 60°C/35°C. Compare copperplate error at lower temperatures
(losses are smaller → copperplate assumption becomes more justified).

Config change: `network.supply_temp_c: 60`, `network.return_temp_c: 35`.
**Scientific value:** High — links to 4th Generation DH literature.

#### Scenario B — High pipe loss (poor insulation)
Double U-value to 0.30 W/(m·K) for all pipes in L2 and L3.
Shows when spatial modelling becomes critical (loss > 10% of demand).

Config change: add `u_value_supply_w_per_m_k: 0.30` to all pipes.
**Scientific value:** Medium — shows sensitivity of copperplate error to insulation quality.

#### Scenario C — Carbon-neutral case
Set gas CO₂ factor to 0 (biomethane / synthetic gas).
Does the network-loss penalty change when fuel is carbon-neutral?

Config change: `fuels.gas.ef_kg_per_mwh_fuel: 0`.
**Scientific value:** Medium — relevant to 2030/2045 scenarios.

---

## 4. Full figure list for the paper

| # | Figure | Type | Status | Effort |
|---|--------|------|--------|--------|
| 1 | System topology (3 levels) | Schematic | ❌ Manual | Low |
| 2 | Heat dispatch stack (1 week) | 3-panel area chart | ⚠️ Script needed | Low |
| 3 | Annual cost breakdown | Grouped bar | ⚠️ Script needed | Low |
| 4 | Pipe heat loss profile | Line plot | ⚠️ Post-process | Low |
| 5 | Tornado chart (sensitivity) | Horizontal bar | ❌ Script needed | Medium |
| 6 | Load duration curve | Line chart | ❌ New | Low |
| 7 | Seasonal dispatch heatmap | Calendar heatmap | ❌ New | Medium |
| 8 | Storage SOC comparison | Line chart | ⚠️ Script needed | Trivial |
| 9 | Pipe loss spatial map | Network diagram | ❌ New | Medium |
| 10 | Sensitivity waterfall | Floating bar | ❌ New | Medium |
| 11 | HP operating envelope scatter | Scatter | ⚠️ Trivial | Trivial |

**For a journal paper, Figures 1–5 are required. Figures 6, 8 strengthen the paper noticeably.
Figures 7, 9 are ideal for a Q1 journal with high competition.**

---

## 5. What needs to be built (gap summary)

### High priority — needed before paper submission

1. **`scripts/paper/run_all_levels.py`** — runs L1/L2/L3 sequentially, saves outputs to `outputs/paper/`
2. **`scripts/paper/plot_dispatch_comparison.py`** — reads 3 CSVs, generates Fig 2 (3-panel dispatch)
3. **`scripts/paper/plot_cost_comparison.py`** — reads 3 `costs.json`, generates Fig 3 (grouped bar)
4. **`scripts/paper/plot_pipe_losses.py`** — aggregates pipe losses, generates Fig 4
5. **`scripts/paper/run_sensitivity.py`** — wires sensitivity runner with optimization callback for Fig 5
6. **`scripts/paper/plot_tornado.py`** — generates tornado chart from sensitivity results

### Medium priority — strengthens the paper

7. **`scripts/paper/plot_load_duration.py`** — Fig 6
8. **`scripts/paper/plot_storage_comparison.py`** — Fig 8 (trivial overlay)
9. **`scripts/paper/plot_network_map.py`** — Fig 9 (schematic networkx plot)

### Low priority — optional

10. Scenario A/B/C config variants
11. Solver statistics extraction (variable/constraint counts)

---

## 6. Recommended build order

```
Phase 2a: Run the 3 baseline models
  → outputs/paper/L1/, L2/, L3/

Phase 2b: Build comparison scripts (Figs 2, 3, 4, 8, Table 1–3)
  → These only need the 3 baseline runs

Phase 3:  Run 63 sensitivity runs
  → outputs/paper/sensitivity/L1/, L2/, L3/

Phase 4:  Build tornado chart (Fig 5) + sensitivity table
  → Needs Phase 3 complete

Phase 5:  Optional figures (6, 7, 9)

Phase 6:  Draw Fig 1 (topology schematic) — do this last, when topology is final
```

---

*Last updated: 2026-03-28*
