# ECM Figure Improvements — Design Spec

**Date:** 2026-04-12
**Target journal:** Energy Conversion and Management (Elsevier)
**Branch:** feature/refactoring-framework-cleanup

---

## Goal

Produce publication-ready figures for the district heating optimisation paper, comparing
planning framework levels L1 (1-node copperplate), L2 (5-node), and L3 (30-node).
All figures must be Overleaf-compatible (PDF vector + PNG preview) and conform to ECM
journal style guidelines.

---

## 1. Shared Style Module

**File:** `scripts/paper/ecm_style.py`

Single source of truth for all styling. Every figure script imports this module.

### Dimensions

| Layout | Width | Usage |
|--------|-------|-------|
| Double column | 190 mm / 7.48 in | 3-panel and wide figures |
| Single column | 90 mm / 3.54 in | Simple bar/line figures |

### Typography

| Element | Size |
|---------|------|
| Axis labels | 9 pt |
| Tick labels | 8 pt |
| Subplot titles | 10 pt |
| Figure suptitle | 11 pt |
| Annotations | 8 pt |
| Font family | sans-serif (Helvetica) |

### Grid
- Line width: 0.4 pt
- Alpha: 0.3
- Axis only (no full box — top/right spines removed)

### Color palette (colorblind-safe, grayscale-distinguishable)

| Role | Hex |
|------|-----|
| Gas boiler | `#d62728` |
| Heat pump | `#1f77b4` |
| Storage discharge | `#2ca02c` |
| Storage charge | `#aec7e8` |
| L1 | `#1f77b4` |
| L2 | `#ff7f0e` |
| L3 | `#2ca02c` |
| Demand / reference | `#1a1a2e` |

### Output
- Formats: `.pdf` (vector, for Overleaf) + `.png` @ 300 DPI (preview)
- `bbox_inches="tight"` on all saves
- LaTeX usage: `\includegraphics[width=\textwidth]{fig.pdf}` (double) or
  `\includegraphics[width=0.5\textwidth]{fig.pdf}` (single)

---

## 2. Redesigned Existing Figures

### Fig 2 — Heat dispatch comparison (`plot_dispatch_comparison.py`)

- **Layout:** 1×3 panels, double column (190 mm × 110 mm)
- **Fix:** Legend moved inside figure (2-column grid, upper-right of centre panel) — saves vertical space
- **Fix:** Suppress "Heat dump" legend entry when `max(dump) < 0.01`
- **Fix:** x-axis shows datetime-derived day labels, not raw integers
- **Fix:** Shared y-axis with proper MW range
- **Style:** All ECM rcParams from `ecm_style.py`

### Fig 3 — Annual cost breakdown (`plot_cost_comparison.py`)

- **Layout:** Single column (90 mm × 110 mm)
- **Change:** Switch from stacked bar to **grouped bar** — only 2 components are non-zero; grouping is cleaner and more honest
- **Fix:** Total M€ annotations above bars with dynamic offset, no overlap
- **Fix:** Δ% labels below x-axis with `clip_on=False`, clear of tick labels
- **Add:** Specific cost per MWh delivered [€/MWh] as secondary annotation — ECM-relevant KPI

### Fig 4 — Pipe heat losses (`plot_pipe_losses.py`)

- **Layout:** Double column (190 mm × 120 mm)
- **Fix:** L3 shows top-10 pipes individually + aggregated "Other pipes" bar — eliminates 30-label clutter
- **Add:** Inset summary panel: total loss L2 vs L3, loss per km, loss as % of annual demand
- **Add:** Loss-per-km secondary metric on each bar (text annotation)

### Fig 8 — Storage state-of-charge (`plot_storage_comparison.py`)

- **Layout:** Single column (90 mm × 110 mm)
- **Fix:** Top panel resampled to **monthly average** — removes daily noise, reveals seasonal pattern
- **Fix:** If L1=L2=L3 lines overlap, collapse to single line + annotation "L1 ≈ L2 ≈ L3"
- **Fix:** Bottom panel unit consistency — all values in MWh

---

## 3. New Figures

### New Fig — CO2 emissions comparison (`plot_co2_comparison.py`)

- **Layout:** Single column (90 mm × 100 mm)
- **Type:** Grouped bar — L1 / L2 / L3, two bars per group: CO2 from gas boiler + CO2 from grid electricity
- **Annotations:** Total annual CO2 [t/yr] on top of each group; Δ% vs L1 below x-axis
- **Data source:** `costs.json` CO2 key, or computed from timeseries using:
  - Gas: `fuel_consumption_MWh × 0.202 t_CO2/MWh`
  - Grid: `grid_import_MWh × grid_emission_factor`

### New Fig — Network topology schematic (`plot_network_topology.py`)

- **Layout:** Double column (190 mm × 80 mm)
- **Type:** Three matplotlib patch panels — L1 / L2 / L3 side by side
  - L1: single circle (copperplate, all assets co-located)
  - L2: 5 nodes with 4 pipes; generation, substation, storage symbols
  - L3: 30-node radial/tree layout from central plant; node symbols sized by demand class
- **Implementation:** `matplotlib.patches` (Circle, FancyArrowPatch, Rectangle) — no coordinates required
- **Legend:** Node type symbols (generation, substation, storage) + pipe line

### New Fig — Heat load duration curve (`plot_load_duration.py`)

- **Layout:** Single column (90 mm × 100 mm)
- **Type:** Three sorted lines: L1 demand / L2 total supply / L3 total supply (demand + network losses)
- **Shading:** Area between L1 and L3 = network loss penalty (grey fill, labelled)
- **Annotations:** Peak demand [MW], base load [MW], full-load hours per level
- **Narrative support:** Directly visualises the infrastructure cost of moving from L1 → L3

### New Fig — Network infrastructure comparison (`plot_network_comparison.py`)

- **Layout:** Double column (190 mm × 70 mm)
- **Type:** Horizontal grouped bar chart, L2 vs L3
- **Metrics shown:** Total pipe length [km], number of pipes, total annual heat loss [MWh], loss as % of annual demand
- **Purpose:** Makes the L1→L3 infrastructure escalation tangible in one figure

---

## 4. File Structure

```
scripts/paper/
├── ecm_style.py                   # NEW — shared style module
├── plot_dispatch_comparison.py    # REFACTOR
├── plot_cost_comparison.py        # REFACTOR
├── plot_pipe_losses.py            # REFACTOR
├── plot_storage_comparison.py     # REFACTOR
├── plot_co2_comparison.py         # NEW
├── plot_network_topology.py       # NEW
├── plot_load_duration.py          # NEW
└── plot_network_comparison.py     # NEW

outputs/paper/figures/
├── fig2_dispatch_comparison.pdf / .png
├── fig3_cost_comparison.pdf / .png
├── fig4_pipe_losses.pdf / .png
├── fig8_storage_soc.pdf / .png
├── figX_co2_comparison.pdf / .png
├── figX_network_topology.pdf / .png
├── figX_load_duration.pdf / .png
└── figX_network_comparison.pdf / .png
```

---

## 5. Out of Scope

- Sensitivity analysis figures (separate paper section, not requested)
- MPC vs. perfect-forecast comparison (requires additional simulation runs)
- Interactive/web figures
- LaTeX table generation (handled by `scripts/paper/extract_tables.py`)
