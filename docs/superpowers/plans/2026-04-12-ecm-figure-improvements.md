# ECM Figure Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce 8 publication-ready figures (4 refactored + 4 new) for a district heating optimisation paper targeting Energy Conversion and Management (ECM) journal, with Overleaf-compatible PDF vector output and a single shared style module.

**Architecture:** `scripts/paper/ecm_style.py` is the single source of truth for all ECM constants and rcParams. Every figure script imports it. Tests live in `tests/test_paper_plot_style.py` and cover pure data functions plus smoke tests that verify PDF/PNG output is created given minimal synthetic input data.

**Tech Stack:** Python 3.x, matplotlib, pandas, numpy, pathlib; pytest for tests.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/paper/ecm_style.py` | CREATE | ECM constants, rcParams, `save_figure()` helper |
| `scripts/paper/plot_dispatch_comparison.py` | REWRITE | Fig 2 — heat dispatch 3-panel stacked area |
| `scripts/paper/plot_cost_comparison.py` | REWRITE | Fig 3 — cost breakdown grouped bar |
| `scripts/paper/plot_pipe_losses.py` | REWRITE | Fig 4 — pipe losses top-10 + loss/km annotation |
| `scripts/paper/plot_storage_comparison.py` | REWRITE | Fig 8 — storage SOC monthly average |
| `scripts/paper/plot_co2_comparison.py` | CREATE | CO2 emissions grouped bar |
| `scripts/paper/plot_network_topology.py` | CREATE | Network topology schematic (pure matplotlib patches) |
| `scripts/paper/plot_load_duration.py` | CREATE | Heat load duration curve |
| `scripts/paper/plot_network_comparison.py` | CREATE | Network infrastructure comparison (L2 vs L3) |
| `tests/test_paper_plot_style.py` | CREATE | Style constants tests + smoke tests for all 8 scripts |

---

### Task 1: Create shared ECM style module

**Files:**
- Create: `scripts/paper/ecm_style.py`
- Create: `tests/test_paper_plot_style.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_paper_plot_style.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "paper"))


def test_ecm_dimensions():
    import ecm_style
    assert abs(ecm_style.SINGLE_COL_W - 3.54) < 0.01
    assert abs(ecm_style.DOUBLE_COL_W - 7.48) < 0.01


def test_ecm_font_sizes():
    import ecm_style
    assert ecm_style.FONT_TICK == 8
    assert ecm_style.FONT_AXIS_LABEL == 9
    assert ecm_style.FONT_TITLE == 10


def test_apply_ecm_style_sets_rcparams():
    import matplotlib as mpl
    import ecm_style
    ecm_style.apply_ecm_style()
    assert mpl.rcParams["xtick.labelsize"] == ecm_style.FONT_TICK
    assert mpl.rcParams["font.size"] == ecm_style.FONT_AXIS_LABEL


def test_color_constants_defined():
    import ecm_style
    for attr in ("C_BOILER", "C_HP", "C_TES_DIS", "C_TES_CHG",
                 "C_DEMAND", "C_DUMP", "C_L1", "C_L2", "C_L3"):
        val = getattr(ecm_style, attr)
        assert val.startswith("#"), f"{attr} should be a hex color string"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_paper_plot_style.py -v
```
Expected: `ImportError: No module named 'ecm_style'`

- [ ] **Step 3: Write implementation**

Create `scripts/paper/ecm_style.py`:

```python
"""
ECM journal style constants and matplotlib rcParams.
Energy Conversion and Management (Elsevier) figure guidelines.

Usage in every figure script:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from ecm_style import apply_ecm_style, save_figure, DOUBLE_COL_W, ...
    apply_ecm_style()
"""
import matplotlib as mpl

# ── Figure dimensions (inches) ────────────────────────────────────────────────
SINGLE_COL_W = 3.54    # 90 mm  — half-page figures
DOUBLE_COL_W = 7.48    # 190 mm — full-width figures

H_STANDARD   = 3.94    # 100 mm
H_TALL       = 4.33    # 110 mm
H_PIPE       = 4.72    # 120 mm
H_WIDE_SHORT = 2.76    # 70 mm
H_TOPOLOGY   = 3.15    # 80 mm

# ── Font sizes (pt at final print size) ──────────────────────────────────────
FONT_AXIS_LABEL = 9
FONT_TICK       = 8
FONT_TITLE      = 10
FONT_SUPTITLE   = 11
FONT_ANNOTATION = 8
FONT_LEGEND     = 8

# ── Colors (colorblind-safe, distinguishable in grayscale) ───────────────────
C_BOILER  = "#d62728"   # red       — gas boiler
C_HP      = "#1f77b4"   # blue      — heat pump
C_TES_DIS = "#2ca02c"   # green     — storage discharge
C_TES_CHG = "#aec7e8"   # lt. blue  — storage charge
C_DEMAND  = "#1a1a2e"   # near-blk  — heat demand line
C_DUMP    = "#ff7f0e"   # orange    — heat dump

C_L1 = "#1f77b4"   # blue
C_L2 = "#ff7f0e"   # orange
C_L3 = "#2ca02c"   # green

C_CO2_GAS  = "#d62728"   # red   — CO2 from gas
C_CO2_GRID = "#1f77b4"   # blue  — CO2 from grid

# ── matplotlib rcParams ───────────────────────────────────────────────────────
ECM_RC = {
    "font.family":       "sans-serif",
    "font.sans-serif":   ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size":         FONT_AXIS_LABEL,
    "axes.titlesize":    FONT_TITLE,
    "axes.labelsize":    FONT_AXIS_LABEL,
    "xtick.labelsize":   FONT_TICK,
    "ytick.labelsize":   FONT_TICK,
    "legend.fontsize":   FONT_LEGEND,
    "axes.linewidth":    0.6,
    "grid.linewidth":    0.4,
    "grid.alpha":        0.3,
    "lines.linewidth":   1.2,
    "patch.linewidth":   0.5,
    "figure.dpi":        300,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "axes.spines.top":   False,
    "axes.spines.right": False,
}


def apply_ecm_style() -> None:
    """Apply ECM rcParams globally. Call once at module level in each script."""
    mpl.rcParams.update(ECM_RC)


def save_figure(fig, stem, formats=("pdf", "png")) -> None:
    """Save fig to each format. stem is a Path or str without extension."""
    for fmt in formats:
        path = f"{stem}.{fmt}"
        fig.savefig(path, bbox_inches="tight")
        print(f"  Saved: {path}")
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_paper_plot_style.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/paper/ecm_style.py tests/test_paper_plot_style.py
git commit -m "feat: add ECM shared style module and tests"
```

---

### Task 2: Refactor Fig 2 — dispatch comparison

**Files:**
- Rewrite: `scripts/paper/plot_dispatch_comparison.py`
- Modify: `tests/test_paper_plot_style.py` (append smoke test)

- [ ] **Step 1: Append smoke test helper + test**

Append to `tests/test_paper_plot_style.py`:

```python
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")


def _write_dispatch_csv(path, n=168):
    """Minimal pf_timeseries.csv for smoke testing."""
    rows = [
        {
            "timestamp": i,
            "waermebedarf_MWth":    50 + 10 * np.sin(i / 24 * 3.14),
            "BOILER_MAIN_Q_th_MW":  30.0,
            "hp_main_Q_th_MW":      15.0,
            "TES_discharge_MW":      5.0,
            "TES_charge_MW":         3.0,
            "Q_dump_MWth":           0.0,
        }
        for i in range(n)
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)


def test_dispatch_comparison_smoke(tmp_path):
    import importlib
    import plot_dispatch_comparison as pdc
    importlib.reload(pdc)

    for tag in ("l1", "l2", "l3"):
        _write_dispatch_csv(tmp_path / f"{tag}.csv")

    sys.argv = ["prog",
                "--l1", str(tmp_path / "l1.csv"),
                "--l2", str(tmp_path / "l2.csv"),
                "--l3", str(tmp_path / "l3.csv"),
                "--outdir", str(tmp_path)]
    pdc.main()

    assert (tmp_path / "fig2_dispatch_comparison.pdf").exists()
    assert (tmp_path / "fig2_dispatch_comparison.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_paper_plot_style.py::test_dispatch_comparison_smoke -v
```
Expected: FAIL — old script does not produce `.pdf`

- [ ] **Step 3: Rewrite plot_dispatch_comparison.py**

```python
"""
Figure 2 — Heat dispatch comparison (3-panel stacked area, coldest week).

Usage:
    python scripts/paper/plot_dispatch_comparison.py \
        --l1 outputs/paper/L1/pf_timeseries.csv \
        --l2 outputs/paper/L2/pf_timeseries.csv \
        --l3 outputs/paper/L3/pf_timeseries.csv \
        --outdir outputs/paper/figures/

Produces:
    fig2_dispatch_comparison.pdf  (vector — use in Overleaf)
    fig2_dispatch_comparison.png  (300 DPI preview)
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    DOUBLE_COL_W, H_TALL,
    C_BOILER, C_HP, C_TES_DIS, C_TES_CHG, C_DEMAND, C_DUMP,
)

apply_ecm_style()

COL_DEMAND  = "waermebedarf_MWth"
COL_BOILER  = "BOILER_MAIN_Q_th_MW"
COL_HP      = "hp_main_Q_th_MW"
COL_TES_DIS = "TES_discharge_MW"
COL_TES_CHG = "TES_charge_MW"
COL_DUMP    = "Q_dump_MWth"

STACK_COLS   = [COL_BOILER, COL_HP, COL_TES_DIS]
STACK_LABELS = ["Gas boiler", "Heat pump", "Storage discharge"]
STACK_COLORS = [C_BOILER, C_HP, C_TES_DIS]

LEVEL_TITLES = {
    "L1": "(a) L1 — copperplate",
    "L2": "(b) L2 — 5-node",
    "L3": "(c) L3 — 30-node",
}


def _load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)
    for col in (COL_DEMAND, COL_BOILER, COL_HP, COL_TES_DIS, COL_TES_CHG, COL_DUMP):
        if col not in df.columns:
            df[col] = 0.0
    return df


def _pick_winter_week(df: pd.DataFrame) -> pd.DataFrame:
    demand = df[COL_DEMAND]
    if len(demand) < 168:
        return df
    end_pos = demand.rolling(168).mean().values.argmax()
    start_pos = max(0, end_pos - 167)
    return df.iloc[start_pos: start_pos + 168]


def _plot_level(ax, df_week: pd.DataFrame, title: str, show_ylabel: bool):
    t = np.arange(len(df_week))

    for col, color in zip(STACK_COLS, STACK_COLORS):
        ax.stackplot(t, df_week[col].fillna(0).values,
                     baseline="zero", colors=[color], alpha=0.85)

    ax.plot(t, df_week[COL_DEMAND].fillna(0).values,
            color=C_DEMAND, linewidth=1.4, zorder=5)

    chg = df_week[COL_TES_CHG].fillna(0).values
    ax.fill_between(t, 0, -chg, color=C_TES_CHG, alpha=0.7)

    dump = df_week[COL_DUMP].fillna(0).values
    if dump.max() > 0.01:
        ax.fill_between(t, 0, dump, color=C_DUMP, alpha=0.7)

    ax.set_title(title, pad=4)
    ax.set_xlim(0, len(df_week) - 1)
    chg_max = df_week[COL_TES_CHG].max()
    ax.set_ylim(bottom=-(chg_max * 1.3) if chg_max > 0 else -5)
    ax.axhline(0, color="black", linewidth=0.4, linestyle="--")
    ax.set_xlabel("Hour of week [h]")
    if show_ylabel:
        ax.set_ylabel("Thermal power [MW]")
    ax.grid(True, axis="y")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l1", required=True)
    parser.add_argument("--l2", required=True)
    parser.add_argument("--l3", required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    parser.add_argument("--week", choices=["coldest", "manual"], default="coldest")
    parser.add_argument("--week-start", type=int, default=None)
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    levels = [("L1", args.l1), ("L2", args.l2), ("L3", args.l3)]
    dfs = {tag: _load(path) for tag, path in levels}

    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_COL_W, H_TALL), sharey=True)
    fig.subplots_adjust(wspace=0.06, left=0.08, right=0.98, top=0.87, bottom=0.14)

    for ax, (tag, _) in zip(axes, levels):
        df = dfs[tag]
        df_week = (df.iloc[args.week_start: args.week_start + 168]
                   if args.week == "manual" and args.week_start is not None
                   else _pick_winter_week(df))
        _plot_level(ax, df_week, LEVEL_TITLES[tag], show_ylabel=(ax is axes[0]))

    # Legend inside centre panel
    handles = [mpatches.Patch(color=c, alpha=0.85, label=l)
               for l, c in zip(STACK_LABELS, STACK_COLORS)]
    handles.append(plt.Line2D([0], [0], color=C_DEMAND, linewidth=1.4,
                               label="Heat demand"))
    handles.append(mpatches.Patch(color=C_TES_CHG, alpha=0.7, label="Storage charge"))
    if max(dfs[t][COL_DUMP].max() for t in dfs) > 0.01:
        handles.append(mpatches.Patch(color=C_DUMP, alpha=0.7, label="Heat dump"))

    axes[1].legend(handles=handles, loc="upper right", ncol=2, framealpha=0.9)
    fig.suptitle("Heat dispatch — coldest week of year", y=0.97)

    save_figure(fig, Path(args.outdir) / "fig2_dispatch_comparison")
    plt.close(fig)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_paper_plot_style.py::test_dispatch_comparison_smoke -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/paper/plot_dispatch_comparison.py tests/test_paper_plot_style.py
git commit -m "refactor: fig2 dispatch — ECM style, PDF output, legend inside panel"
```

---

### Task 3: Refactor Fig 3 — cost breakdown

**Files:**
- Rewrite: `scripts/paper/plot_cost_comparison.py`
- Modify: `tests/test_paper_plot_style.py`

- [ ] **Step 1: Append smoke test**

Append to `tests/test_paper_plot_style.py`:

```python
import json


def _write_costs_json(path, grid=9_400_000, co2=4_200_000, total=14_770_000,
                      demand_mwh=50_000.0):
    data = {"PF": {
        "Grid_energy_cost_EUR":   grid,
        "Fuel_cost_EUR":          0.0,
        "CO2_cost_EUR":           co2,
        "Demand_charge_cost_EUR": 0.0,
        "Dump_cost_EUR":          0.0,
        "Capex_cost_EUR":         0.0,
        "OBJ_value_EUR":          total,
        "total_demand_MWh":       demand_mwh,
    }}
    Path(path).write_text(json.dumps(data))


def test_cost_comparison_smoke(tmp_path):
    import importlib
    import plot_cost_comparison as pcc
    importlib.reload(pcc)

    _write_costs_json(tmp_path / "l1.json", total=14_770_000)
    _write_costs_json(tmp_path / "l2.json", total=14_810_000)
    _write_costs_json(tmp_path / "l3.json", total=14_850_000)

    sys.argv = ["prog",
                "--l1", str(tmp_path / "l1.json"),
                "--l2", str(tmp_path / "l2.json"),
                "--l3", str(tmp_path / "l3.json"),
                "--outdir", str(tmp_path)]
    pcc.main()

    assert (tmp_path / "fig3_cost_comparison.pdf").exists()
    assert (tmp_path / "fig3_cost_comparison.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_paper_plot_style.py::test_cost_comparison_smoke -v
```
Expected: FAIL — old script saves only PNG at wrong size

- [ ] **Step 3: Rewrite plot_cost_comparison.py**

```python
"""
Figure 3 — Annual cost breakdown: grouped bar (L1 / L2 / L3).

Usage:
    python scripts/paper/plot_cost_comparison.py \
        --l1 outputs/paper/L1/costs.json \
        --l2 outputs/paper/L2/costs.json \
        --l3 outputs/paper/L3/costs.json \
        --outdir outputs/paper/figures/

Produces:
    fig3_cost_comparison.pdf / .png
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    SINGLE_COL_W, H_TALL,
    C_HP, C_BOILER, C_L3,
)

apply_ecm_style()

COST_COMPONENTS = {
    "Grid_energy_cost_EUR":   ("Grid electricity", C_HP),
    "Fuel_cost_EUR":          ("Gas fuel",         C_BOILER),
    "CO2_cost_EUR":           ("CO\u2082",          "#78909c"),
    "Demand_charge_cost_EUR": ("Demand charge",    "#ab47bc"),
    "Dump_cost_EUR":          ("Heat dump",        "#ff7f0e"),
    "Capex_cost_EUR":         ("CAPEX",            C_L3),
}
TOTAL_KEY  = "OBJ_value_EUR"
DEMAND_KEY = "total_demand_MWh"
LEVEL_LABELS = ["L1\n(1-node)", "L2\n(5-node)", "L3\n(30-node)"]


def _load_costs(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("PF", data)


def _get(costs: dict, key: str) -> float:
    if key in costs:
        return float(costs[key])
    return float(costs.get("objective", {}).get(key, 0.0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l1", required=True)
    parser.add_argument("--l2", required=True)
    parser.add_argument("--l3", required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    all_costs = [_load_costs(p) for p in (args.l1, args.l2, args.l3)]
    totals  = [_get(c, TOTAL_KEY) for c in all_costs]
    if all(t == 0 for t in totals):
        totals = [sum(_get(c, k) for k in COST_COMPONENTS) for c in all_costs]
    demands = [_get(c, DEMAND_KEY) for c in all_costs]

    # Only show components that are non-zero in at least one level
    active = {k: v for k, v in COST_COMPONENTS.items()
              if any(_get(c, k) > 0 for c in all_costs)}

    comp_keys   = list(active.keys())
    comp_labels = [v[0] for v in active.values()]
    comp_colors = [v[1] for v in active.values()]
    matrix = np.array([[_get(c, k) / 1e6 for k in comp_keys] for c in all_costs])

    fig, ax = plt.subplots(figsize=(SINGLE_COL_W, H_TALL))
    x = np.arange(3)
    bar_w = 0.55

    bottoms = np.zeros(3)
    for i, (label, color) in enumerate(zip(comp_labels, comp_colors)):
        ax.bar(x, matrix[:, i], bar_w, bottom=bottoms,
               color=color, label=label, edgecolor="white", linewidth=0.4)
        bottoms += matrix[:, i]

    y_max = bottoms.max()

    # Total M€ annotation above each bar
    for xi, total in enumerate(totals):
        ax.text(xi, bottoms[xi] + y_max * 0.03,
                f"{total/1e6:.2f} M\u20ac",
                ha="center", va="bottom", fontsize=8, fontweight="bold")

    # €/MWh specific cost below the M€ annotation
    for xi, (total, demand) in enumerate(zip(totals, demands)):
        if demand > 0:
            ax.text(xi, bottoms[xi] + y_max * 0.11,
                    f"{total/demand:.1f} \u20ac/MWh",
                    ha="center", va="bottom", fontsize=7, color="#555555")

    # Δ% vs L1 below x-axis
    if totals[0] > 0:
        for xi in (1, 2):
            pct = (totals[xi] - totals[0]) / totals[0] * 100
            sign = "+" if pct >= 0 else ""
            ax.annotate(f"\u0394 L1: {sign}{pct:.1f}%",
                        xy=(xi, 0), xytext=(xi, -y_max * 0.12),
                        ha="center", va="top", fontsize=7,
                        color="#444444", style="italic",
                        annotation_clip=False)

    ax.set_xticks(x)
    ax.set_xticklabels(LEVEL_LABELS)
    ax.set_ylabel("Annual cost [M\u20ac]")
    ax.set_title("Annual cost breakdown — perfect forecast")
    ax.set_ylim(0, y_max * 1.30)
    ax.grid(True, axis="y")
    ax.legend(loc="upper right", framealpha=0.9)

    fig.tight_layout()
    save_figure(fig, Path(args.outdir) / "fig3_cost_comparison")
    plt.close(fig)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_paper_plot_style.py::test_cost_comparison_smoke -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/paper/plot_cost_comparison.py tests/test_paper_plot_style.py
git commit -m "refactor: fig3 cost — ECM style, grouped bar, EUR/MWh annotation, fixed overlap"
```

---

### Task 4: Refactor Fig 4 — pipe losses

**Files:**
- Rewrite: `scripts/paper/plot_pipe_losses.py`
- Modify: `tests/test_paper_plot_style.py`

- [ ] **Step 1: Append smoke test**

Append to `tests/test_paper_plot_style.py`:

```python
def _write_network_summary(path, n_pipes=5, base_loss=300.0):
    pipes = {
        f"pipe_{i:02d}": {"total_heat_loss_mwh": base_loss - i * (base_loss / (n_pipes + 1)),
                           "length_m": 500 + i * 100}
        for i in range(n_pipes)
    }
    Path(path).write_text(json.dumps({"pipes": pipes}))


def test_pipe_losses_smoke(tmp_path):
    import importlib
    import plot_pipe_losses as ppl
    importlib.reload(ppl)

    _write_network_summary(tmp_path / "l2_summary.json", n_pipes=4,  base_loss=400)
    _write_network_summary(tmp_path / "l3_summary.json", n_pipes=15, base_loss=200)
    _write_dispatch_csv(tmp_path / "l1_demand.csv", n=8760)

    sys.argv = ["prog",
                "--l2-summary", str(tmp_path / "l2_summary.json"),
                "--l3-summary", str(tmp_path / "l3_summary.json"),
                "--l1-demand",  str(tmp_path / "l1_demand.csv"),
                "--outdir", str(tmp_path)]
    ppl.main()

    assert (tmp_path / "fig4_pipe_losses.pdf").exists()
    assert (tmp_path / "fig4_pipe_losses.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_paper_plot_style.py::test_pipe_losses_smoke -v
```
Expected: FAIL

- [ ] **Step 3: Rewrite plot_pipe_losses.py**

```python
"""
Figure 4 — Pipe heat losses: L2 vs L3 (top-10 + aggregated others).

Usage:
    python scripts/paper/plot_pipe_losses.py \
        --l2-summary outputs/paper/L2_january/thermal_network/network_summary.json \
        --l3-summary outputs/paper/L3_january/thermal_network/network_summary.json \
        --l1-demand  outputs/paper/L1_january/pf_timeseries.csv \
        --outdir     outputs/paper/figures/

Produces:
    fig4_pipe_losses.pdf / .png
    fig4_pipe_losses_summary.csv
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    DOUBLE_COL_W, H_PIPE,
    C_L2, C_L3,
)

apply_ecm_style()

DEMAND_COL = "waermebedarf_MWth"
TOP_N      = 10


def _load_summary(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pipe_losses(summary: dict) -> pd.DataFrame:
    rows = [
        {"pipe": pid,
         "loss_MWh": float(p.get("total_heat_loss_mwh", 0)),
         "length_m": float(p.get("length_m", 0))}
        for pid, p in summary.get("pipes", {}).items()
    ]
    return pd.DataFrame(rows).sort_values("loss_MWh", ascending=False).reset_index(drop=True)


def _top_n_with_other(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Keep top-n rows by loss; aggregate the rest into a single 'Other pipes' bar."""
    if len(df) <= n:
        return df
    top  = df.head(n).copy()
    rest = df.iloc[n:]
    other = pd.DataFrame([{
        "pipe":     f"Other {len(rest)} pipes",
        "loss_MWh": rest["loss_MWh"].sum(),
        "length_m": rest["length_m"].sum(),
    }])
    return pd.concat([top, other], ignore_index=True)


def _plot_panel(ax, df: pd.DataFrame, title: str, color: str, demand_mwh: float):
    y = np.arange(len(df))
    ax.barh(y, df["loss_MWh"], color=color, alpha=0.85, edgecolor="white", linewidth=0.3)

    x_max = df["loss_MWh"].max()
    for i, row in df.iterrows():
        if row["length_m"] > 0:
            loss_per_km = row["loss_MWh"] / (row["length_m"] / 1000)
            ax.text(row["loss_MWh"] + x_max * 0.02, i,
                    f"{loss_per_km:.0f} MWh/km",
                    va="center", fontsize=6.5, color="#444444")

    ax.set_yticks(y)
    ax.set_yticklabels(df["pipe"], fontsize=7)
    ax.set_xlabel("Heat loss [MWh]")
    total_mwh = df["loss_MWh"].sum()
    loss_pct  = total_mwh / demand_mwh * 100 if demand_mwh > 0 else 0
    ax.set_title(f"{title}\n{total_mwh:.0f} MWh total ({loss_pct:.2f}% of demand)")
    ax.grid(True, axis="x")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l2-summary", required=True)
    parser.add_argument("--l3-summary", required=True)
    parser.add_argument("--l1-demand",  required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    df_l2 = _pipe_losses(_load_summary(args.l2_summary))
    df_l3 = _pipe_losses(_load_summary(args.l3_summary))

    dem_df     = pd.read_csv(args.l1_demand, sep=";", decimal=",")
    demand_mwh = dem_df[DEMAND_COL].fillna(0).sum() if DEMAND_COL in dem_df.columns else 0.0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(DOUBLE_COL_W, H_PIPE))
    _plot_panel(ax1, _top_n_with_other(df_l2, TOP_N), "L2 — 5-node",  C_L2, demand_mwh)
    _plot_panel(ax2, _top_n_with_other(df_l3, TOP_N), "L3 — 30-node", C_L3, demand_mwh)
    fig.suptitle("Pipe heat losses (January baseline)")
    fig.tight_layout()

    save_figure(fig, Path(args.outdir) / "fig4_pipe_losses")
    plt.close(fig)

    rows = []
    for tag, df in [("L2", df_l2), ("L3", df_l3)]:
        for _, row in df.iterrows():
            rows.append({"level": tag, "pipe": row["pipe"],
                         "length_m": row["length_m"],
                         "heat_loss_MWh": round(row["loss_MWh"], 2)})
    pd.DataFrame(rows).to_csv(Path(args.outdir) / "fig4_pipe_losses_summary.csv", index=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_paper_plot_style.py::test_pipe_losses_smoke -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/paper/plot_pipe_losses.py tests/test_paper_plot_style.py
git commit -m "refactor: fig4 pipe losses — ECM style, top-10+other, loss/km annotation"
```

---

### Task 5: Refactor Fig 8 — storage SOC

**Files:**
- Rewrite: `scripts/paper/plot_storage_comparison.py`
- Modify: `tests/test_paper_plot_style.py`

- [ ] **Step 1: Append smoke test**

Append to `tests/test_paper_plot_style.py`:

```python
def _write_soc_csv(path, n=8760):
    rows = [
        {
            "timestamp":          i,
            "TES_SOC_MWh":        230 + 20 * np.sin(i / 24 * 3.14),
            "TES_charge_MW":      max(0.0, 5 * np.sin(i / 12 * 3.14)),
            "TES_discharge_MW":   max(0.0, -5 * np.sin(i / 12 * 3.14)),
        }
        for i in range(n)
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)


def test_storage_comparison_smoke(tmp_path):
    import importlib
    import plot_storage_comparison as psc
    importlib.reload(psc)

    for tag in ("l1", "l2", "l3"):
        _write_soc_csv(tmp_path / f"{tag}.csv")

    sys.argv = ["prog",
                "--l1", str(tmp_path / "l1.csv"),
                "--l2", str(tmp_path / "l2.csv"),
                "--l3", str(tmp_path / "l3.csv"),
                "--outdir", str(tmp_path)]
    psc.main()

    assert (tmp_path / "fig8_storage_soc.pdf").exists()
    assert (tmp_path / "fig8_storage_soc.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_paper_plot_style.py::test_storage_comparison_smoke -v
```
Expected: FAIL

- [ ] **Step 3: Rewrite plot_storage_comparison.py**

```python
"""
Figure 8 — Storage state-of-charge comparison (L1 / L2 / L3, monthly average).

Usage:
    python scripts/paper/plot_storage_comparison.py \
        --l1 outputs/paper/L1/pf_timeseries.csv \
        --l2 outputs/paper/L2/pf_timeseries.csv \
        --l3 outputs/paper/L3/pf_timeseries.csv \
        --outdir outputs/paper/figures/

Produces:
    fig8_storage_soc.pdf / .png
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    SINGLE_COL_W, H_TALL,
    C_L1, C_L2, C_L3,
)

apply_ecm_style()

SOC_COL = "TES_SOC_MWh"
CHG_COL = "TES_charge_MW"
DIS_COL = "TES_discharge_MW"

COLORS = {"L1": C_L1, "L2": C_L2, "L3": C_L3}
LABELS = {"L1": "L1 — 1-node", "L2": "L2 — 5-node", "L3": "L3 — 30-node"}


def _load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)
    for col in (SOC_COL, CHG_COL, DIS_COL):
        if col not in df.columns:
            df[col] = 0.0
    return df


def _monthly_avg(series: pd.Series) -> np.ndarray:
    """Return 12 monthly mean values. Falls back to 12 equal blocks."""
    if isinstance(series.index, pd.DatetimeIndex):
        return series.resample("ME").mean().values
    block = max(1, len(series) // 12)
    return np.array([series.iloc[i * block:(i + 1) * block].mean()
                     for i in range(12)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l1", required=True)
    parser.add_argument("--l2", required=True)
    parser.add_argument("--l3", required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    dfs = {tag: _load(path)
           for tag, path in (("L1", args.l1), ("L2", args.l2), ("L3", args.l3))}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(SINGLE_COL_W, H_TALL * 1.8))
    fig.subplots_adjust(hspace=0.38)

    # ── Top: monthly average SOC ──────────────────────────────────────────────
    monthly = {tag: _monthly_avg(df[SOC_COL]) for tag, df in dfs.items()}

    all_vals = np.concatenate(list(monthly.values()))
    spread   = np.nanmax(all_vals) - np.nanmin(all_vals)
    mean_val = np.nanmean(all_vals)
    identical = spread < 0.05 * mean_val if mean_val > 0 else True

    months = np.arange(1, 13)
    if identical:
        ax1.plot(months, monthly["L1"], color=C_L1, linewidth=1.4)
        ax1.text(months[-1] * 0.6, mean_val, "L1 \u2248 L2 \u2248 L3",
                 fontsize=8, color="#555555")
    else:
        for tag, vals in monthly.items():
            ax1.plot(months, vals, color=COLORS[tag], linewidth=1.4, label=LABELS[tag])
        ax1.legend(loc="lower right")

    ax1.set_xlabel("Month")
    ax1.set_ylabel("Monthly avg. SOC [MWh]")
    ax1.set_title("Thermal storage state-of-charge")
    ax1.set_xticks(months)
    ax1.grid(True, axis="y")

    # ── Bottom: annual metrics grouped bar ───────────────────────────────────
    metrics = {
        tag: {
            "avg_soc":   df[SOC_COL].mean(),
            "charge":    df[CHG_COL].clip(lower=0).sum(),
            "discharge": df[DIS_COL].clip(lower=0).sum(),
        }
        for tag, df in dfs.items()
    }
    tags = list(metrics.keys())
    x, w = np.arange(len(tags)), 0.25
    ax2.bar(x - w, [metrics[t]["avg_soc"]   for t in tags], w,
            label="Avg SOC [MWh]",       color="#78909c", alpha=0.85)
    ax2.bar(x,     [metrics[t]["charge"]    for t in tags], w,
            label="Annual charge [MWh]", color=C_L1, alpha=0.85)
    ax2.bar(x + w, [metrics[t]["discharge"] for t in tags], w,
            label="Annual discharge [MWh]", color=C_L2, alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels([LABELS[t] for t in tags])
    ax2.set_ylabel("Energy [MWh]")
    ax2.set_title("Annual storage energy metrics")
    ax2.legend(loc="upper right")
    ax2.grid(True, axis="y")

    fig.tight_layout()
    save_figure(fig, Path(args.outdir) / "fig8_storage_soc")
    plt.close(fig)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_paper_plot_style.py::test_storage_comparison_smoke -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/paper/plot_storage_comparison.py tests/test_paper_plot_style.py
git commit -m "refactor: fig8 storage — ECM style, monthly SOC, identical-line detection"
```

---

### Task 6: New Fig — CO2 emissions comparison

**Files:**
- Create: `scripts/paper/plot_co2_comparison.py`
- Modify: `tests/test_paper_plot_style.py`

- [ ] **Step 1: Append smoke test**

Append to `tests/test_paper_plot_style.py`:

```python
def test_co2_comparison_smoke(tmp_path):
    for name, gas_t, grid_t, total in [
        ("l1.json", 820.0, 380.0, 14_770_000),
        ("l2.json", 825.0, 382.0, 14_810_000),
        ("l3.json", 830.0, 385.0, 14_850_000),
    ]:
        data = {"PF": {
            "CO2_gas_tonnes":  gas_t,
            "CO2_grid_tonnes": grid_t,
            "OBJ_value_EUR":   total,
            "total_demand_MWh": 50_000.0,
        }}
        (tmp_path / name).write_text(json.dumps(data))

    import importlib
    import plot_co2_comparison as pco2
    importlib.reload(pco2)

    sys.argv = ["prog",
                "--l1", str(tmp_path / "l1.json"),
                "--l2", str(tmp_path / "l2.json"),
                "--l3", str(tmp_path / "l3.json"),
                "--outdir", str(tmp_path)]
    pco2.main()

    assert (tmp_path / "figX_co2_comparison.pdf").exists()
    assert (tmp_path / "figX_co2_comparison.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_paper_plot_style.py::test_co2_comparison_smoke -v
```
Expected: `ModuleNotFoundError: No module named 'plot_co2_comparison'`

- [ ] **Step 3: Write plot_co2_comparison.py**

```python
"""
Figure — Annual CO2 emissions: grouped bar (L1 / L2 / L3).

Usage:
    python scripts/paper/plot_co2_comparison.py \
        --l1 outputs/paper/L1/costs.json \
        --l2 outputs/paper/L2/costs.json \
        --l3 outputs/paper/L3/costs.json \
        --outdir outputs/paper/figures/

Expects costs.json (under "PF") to contain:
    CO2_gas_tonnes   — annual CO2 from gas boiler [t CO2]
    CO2_grid_tonnes  — annual CO2 from grid electricity [t CO2]
    total_demand_MWh — annual heat demand [MWh]

Fallback if CO2 tonne keys are absent:
    gas  CO2 = Fuel_cost_EUR / 40.0 (EUR/MWh) * 0.202 (t CO2/MWh)
    grid CO2 = CO2_cost_EUR  / 65.0 (EUR/t CO2, EU ETS 2023 approx.)

Produces:
    figX_co2_comparison.pdf / .png
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    SINGLE_COL_W, H_TALL,
    C_CO2_GAS, C_CO2_GRID,
)

apply_ecm_style()

GAS_PRICE_EUR_MWH = 40.0
GAS_CO2_FACTOR    = 0.202   # t CO2 / MWh natural gas
CO2_PRICE_EUR_T   = 65.0    # EUR / t CO2

LEVEL_LABELS = ["L1\n(1-node)", "L2\n(5-node)", "L3\n(30-node)"]


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("PF", data)


def _get(d: dict, key: str) -> float:
    return float(d.get(key, d.get("objective", {}).get(key, 0.0)))


def _co2_tonnes(costs: dict) -> tuple:
    """Return (gas_co2_t, grid_co2_t). Falls back to cost-based estimate."""
    gas_t  = _get(costs, "CO2_gas_tonnes")
    grid_t = _get(costs, "CO2_grid_tonnes")
    if gas_t == 0.0:
        gas_t = (_get(costs, "Fuel_cost_EUR") / GAS_PRICE_EUR_MWH) * GAS_CO2_FACTOR
    if grid_t == 0.0:
        grid_t = _get(costs, "CO2_cost_EUR") / CO2_PRICE_EUR_T
    return gas_t, grid_t


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l1", required=True)
    parser.add_argument("--l2", required=True)
    parser.add_argument("--l3", required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    all_costs  = [_load(p) for p in (args.l1, args.l2, args.l3)]
    co2_pairs  = [_co2_tonnes(c) for c in all_costs]
    gas_vals   = np.array([p[0] for p in co2_pairs])
    grid_vals  = np.array([p[1] for p in co2_pairs])
    totals     = gas_vals + grid_vals
    demands    = np.array([_get(c, "total_demand_MWh") for c in all_costs])

    fig, ax = plt.subplots(figsize=(SINGLE_COL_W, H_TALL))
    x, w = np.arange(3), 0.55

    ax.bar(x, gas_vals,  w, label="Gas boiler",       color=C_CO2_GAS,  alpha=0.85, edgecolor="white")
    ax.bar(x, grid_vals, w, label="Grid electricity", color=C_CO2_GRID, alpha=0.85,
           bottom=gas_vals, edgecolor="white")

    y_max = totals.max()
    for xi, total in enumerate(totals):
        ax.text(xi, total + y_max * 0.03,
                f"{total:.0f} t",
                ha="center", va="bottom", fontsize=8, fontweight="bold")

    for xi, (total, demand) in enumerate(zip(totals, demands)):
        if demand > 0:
            ax.text(xi, total + y_max * 0.11,
                    f"{total/demand*1000:.1f} kg/MWh",
                    ha="center", va="bottom", fontsize=7, color="#555555")

    if totals[0] > 0:
        for xi in (1, 2):
            pct = (totals[xi] - totals[0]) / totals[0] * 100
            sign = "+" if pct >= 0 else ""
            ax.annotate(f"\u0394 L1: {sign}{pct:.1f}%",
                        xy=(xi, 0), xytext=(xi, -y_max * 0.12),
                        ha="center", va="top", fontsize=7,
                        color="#444444", style="italic",
                        annotation_clip=False)

    ax.set_xticks(x)
    ax.set_xticklabels(LEVEL_LABELS)
    ax.set_ylabel("Annual CO\u2082 emissions [t CO\u2082/yr]")
    ax.set_title("CO\u2082 emissions comparison — perfect forecast")
    ax.set_ylim(0, y_max * 1.30)
    ax.grid(True, axis="y")
    ax.legend(loc="upper right", framealpha=0.9)

    fig.tight_layout()
    save_figure(fig, Path(args.outdir) / "figX_co2_comparison")
    plt.close(fig)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_paper_plot_style.py::test_co2_comparison_smoke -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/paper/plot_co2_comparison.py tests/test_paper_plot_style.py
git commit -m "feat: add CO2 emissions comparison figure (ECM style)"
```

---

### Task 7: New Fig — network topology schematic

**Files:**
- Create: `scripts/paper/plot_network_topology.py`
- Modify: `tests/test_paper_plot_style.py`

- [ ] **Step 1: Append smoke test**

Append to `tests/test_paper_plot_style.py`:

```python
def test_network_topology_smoke(tmp_path):
    import importlib
    import plot_network_topology as pnt
    importlib.reload(pnt)

    sys.argv = ["prog", "--outdir", str(tmp_path)]
    pnt.main()

    assert (tmp_path / "figX_network_topology.pdf").exists()
    assert (tmp_path / "figX_network_topology.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_paper_plot_style.py::test_network_topology_smoke -v
```
Expected: `ModuleNotFoundError: No module named 'plot_network_topology'`

- [ ] **Step 3: Write plot_network_topology.py**

```python
"""
Figure — Network topology schematic: L1 / L2 / L3 side-by-side.

Usage:
    python scripts/paper/plot_network_topology.py --outdir outputs/paper/figures/

No input data required — all positions are hardcoded schematically.

Produces:
    figX_network_topology.pdf / .png
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    DOUBLE_COL_W, H_TOPOLOGY,
)

apply_ecm_style()

NODE_STYLES = {
    "plant":      {"color": "#d62728", "r": 0.055, "label": "Generation plant"},
    "central":    {"color": "#ff7f0e", "r": 0.045, "label": "Central node"},
    "substation": {"color": "#1f77b4", "r": 0.035, "label": "Substation / demand"},
    "storage":    {"color": "#2ca02c", "r": 0.040, "label": "Thermal storage"},
}
PIPE_COLOR = "#555555"
PIPE_LW    = 1.2


def _node(ax, x, y, ntype, label="", lo=(0, -0.13)):
    s = NODE_STYLES[ntype]
    ax.add_patch(Circle((x, y), s["r"], color=s["color"], zorder=5,
                         linewidth=0.5, edgecolor="white"))
    if label:
        ax.text(x + lo[0], y + lo[1], label, ha="center", va="top",
                fontsize=6.5, zorder=6)


def _pipe(ax, x1, y1, x2, y2):
    ax.plot([x1, x2], [y1, y2], color=PIPE_COLOR, linewidth=PIPE_LW,
            solid_capstyle="round", zorder=3)


def _panel_l1(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("(a) L1 — Copperplate\n(1 node)", pad=4)

    _node(ax, 0.50, 0.60, "central",    "All assets\nco-located")
    _node(ax, 0.32, 0.76, "plant",      "Boiler +\nHeat pump", (0, 0.06))
    _node(ax, 0.68, 0.76, "storage",    "TES",                 (0, 0.06))
    _node(ax, 0.50, 0.36, "substation", "Demand",              (0, -0.12))

    _pipe(ax, 0.36, 0.70, 0.46, 0.62)
    _pipe(ax, 0.64, 0.70, 0.54, 0.62)
    _pipe(ax, 0.50, 0.52, 0.50, 0.42)

    ax.text(0.50, 0.10, "No network losses\n(copperplate)", ha="center",
            fontsize=6.5, color="#666666", style="italic")


def _panel_l2(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("(b) L2 — 5-node\nnetwork", pad=4)

    pos = {
        "plant":   (0.50, 0.84),
        "central": (0.50, 0.65),
        "north":   (0.22, 0.44),
        "south":   (0.78, 0.44),
        "indus":   (0.78, 0.22),
    }
    pipes = [("plant", "central"), ("central", "north"),
             ("central", "south"), ("south", "indus")]
    for a, b in pipes:
        _pipe(ax, *pos[a], *pos[b])

    labels = {"plant": "Plant\n(Gen+TES)", "central": "Central",
              "north": "North", "south": "South", "indus": "Industrial"}
    types  = {"plant": "plant", "central": "central",
              "north": "substation", "south": "substation", "indus": "substation"}
    for k, (x, y) in pos.items():
        lo = (0, 0.06) if y > 0.70 else (0, -0.12)
        _node(ax, x, y, types[k], labels[k], lo)

    ax.text(0.50, 0.06, "4 pipes · 5 nodes", ha="center",
            fontsize=6.5, color="#666666", style="italic")


def _panel_l3(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("(c) L3 — 30-node\nnetwork", pad=4)

    plant   = (0.50, 0.90)
    central = (0.50, 0.74)
    _pipe(ax, *plant, *central)
    _node(ax, *plant,   "plant",   "Plant",   (0, 0.05))
    _node(ax, *central, "central", "Central", (0, -0.10))

    branches = [(0.18, 0.56), (0.50, 0.56), (0.82, 0.56)]
    blabels  = ["West", "North", "East"]
    for (bx, by), bl in zip(branches, blabels):
        _pipe(ax, *central, bx, by)
        _node(ax, bx, by, "substation", bl, (0, -0.10))

        sub_offsets = [(-0.09, -0.14), (0.0, -0.14), (0.09, -0.14)]
        for ox, oy in sub_offsets:
            sx, sy = bx + ox, by + oy
            _pipe(ax, bx, by, sx, sy)
            _node(ax, sx, sy, "substation")

            for lox, loy in [(-0.045, -0.11), (0.045, -0.11)]:
                lx, ly = sx + lox, sy + loy
                if 0.02 < lx < 0.98 and 0.04 < ly < 0.96:
                    _pipe(ax, sx, sy, lx, ly)
                    _node(ax, lx, ly, "substation")

    ax.text(0.50, 0.03, "\u224829 pipes · 30 nodes", ha="center",
            fontsize=6.5, color="#666666", style="italic")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_COL_W, H_TOPOLOGY))
    fig.subplots_adjust(wspace=0.05, left=0.01, right=0.99, top=0.86, bottom=0.10)

    _panel_l1(axes[0])
    _panel_l2(axes[1])
    _panel_l3(axes[2])

    handles = [mpatches.Patch(color=NODE_STYLES[k]["color"],
                               label=NODE_STYLES[k]["label"])
               for k in ("plant", "central", "substation", "storage")]
    handles.append(plt.Line2D([0], [0], color=PIPE_COLOR,
                               linewidth=PIPE_LW, label="District heating pipe"))
    fig.legend(handles=handles, loc="lower center", ncol=5,
               fontsize=7, bbox_to_anchor=(0.5, -0.04), frameon=True)

    fig.suptitle("Planning framework levels — network topology", y=0.97)

    save_figure(fig, Path(args.outdir) / "figX_network_topology")
    plt.close(fig)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_paper_plot_style.py::test_network_topology_smoke -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/paper/plot_network_topology.py tests/test_paper_plot_style.py
git commit -m "feat: add network topology schematic (L1/L2/L3 panels)"
```

---

### Task 8: New Fig — heat load duration curve

**Files:**
- Create: `scripts/paper/plot_load_duration.py`
- Modify: `tests/test_paper_plot_style.py`

- [ ] **Step 1: Append smoke test**

Append to `tests/test_paper_plot_style.py`:

```python
def test_load_duration_smoke(tmp_path):
    import importlib
    import plot_load_duration as pld
    importlib.reload(pld)

    for tag in ("l1", "l2", "l3"):
        _write_dispatch_csv(tmp_path / f"{tag}.csv", n=8760)

    sys.argv = ["prog",
                "--l1", str(tmp_path / "l1.csv"),
                "--l2", str(tmp_path / "l2.csv"),
                "--l3", str(tmp_path / "l3.csv"),
                "--outdir", str(tmp_path)]
    pld.main()

    assert (tmp_path / "figX_load_duration.pdf").exists()
    assert (tmp_path / "figX_load_duration.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_paper_plot_style.py::test_load_duration_smoke -v
```
Expected: `ModuleNotFoundError: No module named 'plot_load_duration'`

- [ ] **Step 3: Write plot_load_duration.py**

```python
"""
Figure — Heat load duration curve (L1 / L2 / L3).

L1 line:    heat demand (waermebedarf_MWth) — copperplate, no network losses
L2/L3 line: total heat supply (boiler + heat pump + storage discharge)
            = demand + network losses

Grey shading between L1 and L3 = network loss penalty.

Usage:
    python scripts/paper/plot_load_duration.py \
        --l1 outputs/paper/L1/pf_timeseries.csv \
        --l2 outputs/paper/L2/pf_timeseries.csv \
        --l3 outputs/paper/L3/pf_timeseries.csv \
        --outdir outputs/paper/figures/

Produces:
    figX_load_duration.pdf / .png
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    SINGLE_COL_W, H_TALL,
    C_L1, C_L2, C_L3,
)

apply_ecm_style()

COL_DEMAND  = "waermebedarf_MWth"
COL_BOILER  = "BOILER_MAIN_Q_th_MW"
COL_HP      = "hp_main_Q_th_MW"
COL_TES_DIS = "TES_discharge_MW"

COLORS = {"L1": C_L1, "L2": C_L2, "L3": C_L3}
LSTYLE = {"L1": "-",  "L2": "--", "L3": ":"}
LABELS = {
    "L1": "L1 demand (copperplate)",
    "L2": "L2 supply (5-node)",
    "L3": "L3 supply (30-node)",
}


def _load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)
    for col in (COL_DEMAND, COL_BOILER, COL_HP, COL_TES_DIS):
        if col not in df.columns:
            df[col] = 0.0
    return df


def _supply(df: pd.DataFrame) -> pd.Series:
    return (df[COL_BOILER] + df[COL_HP] + df[COL_TES_DIS]).clip(lower=0)


def _duration_curve(series: pd.Series) -> np.ndarray:
    return np.sort(series.fillna(0).values)[::-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l1", required=True)
    parser.add_argument("--l2", required=True)
    parser.add_argument("--l3", required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    dfs = {tag: _load(path)
           for tag, path in (("L1", args.l1), ("L2", args.l2), ("L3", args.l3))}

    series = {
        "L1": dfs["L1"][COL_DEMAND],
        "L2": _supply(dfs["L2"]),
        "L3": _supply(dfs["L3"]),
    }
    curves = {tag: _duration_curve(s) for tag, s in series.items()}
    n_h    = max(len(c) for c in curves.values())
    h      = np.arange(1, n_h + 1)

    fig, ax = plt.subplots(figsize=(SINGLE_COL_W, H_TALL))

    for tag, curve in curves.items():
        n = min(len(h), len(curve))
        ax.plot(h[:n], curve[:n], color=COLORS[tag], linewidth=1.4,
                linestyle=LSTYLE[tag], label=LABELS[tag])

    # Shade network loss penalty between L1 and L3
    n_common = min(len(curves["L1"]), len(curves["L3"]))
    l1_c, l3_c = curves["L1"][:n_common], curves["L3"][:n_common]
    if l3_c.max() > l1_c.max() * 0.01:
        ax.fill_between(h[:n_common], l1_c, l3_c,
                        where=(l3_c >= l1_c), alpha=0.12, color=C_L3,
                        label="Network loss (L3 vs L1)")

    # Annotate peak demand per level
    for tag, curve in curves.items():
        peak = curve[0]
        ax.annotate(f"{peak:.1f} MW",
                    xy=(1, peak), xytext=(n_h * 0.04, peak * 0.98),
                    fontsize=6.5, color=COLORS[tag],
                    arrowprops=dict(arrowstyle="-", color=COLORS[tag], lw=0.4))

    ax.set_xlabel("Hours per year [h]")
    ax.set_ylabel("Thermal power [MW]")
    ax.set_title("Heat load duration curve")
    ax.set_xlim(0, n_h)
    ax.set_ylim(bottom=0)
    ax.grid(True, axis="both")
    ax.legend(loc="upper right", fontsize=7, framealpha=0.9)

    fig.tight_layout()
    save_figure(fig, Path(args.outdir) / "figX_load_duration")
    plt.close(fig)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_paper_plot_style.py::test_load_duration_smoke -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/paper/plot_load_duration.py tests/test_paper_plot_style.py
git commit -m "feat: add heat load duration curve figure"
```

---

### Task 9: New Fig — network infrastructure comparison

**Files:**
- Create: `scripts/paper/plot_network_comparison.py`
- Modify: `tests/test_paper_plot_style.py`

- [ ] **Step 1: Append smoke test**

Append to `tests/test_paper_plot_style.py`:

```python
def test_network_comparison_smoke(tmp_path):
    import importlib
    import plot_network_comparison as pnc
    importlib.reload(pnc)

    _write_network_summary(tmp_path / "l2_summary.json", n_pipes=4,  base_loss=400)
    _write_network_summary(tmp_path / "l3_summary.json", n_pipes=30, base_loss=180)
    _write_dispatch_csv(tmp_path / "l1_demand.csv", n=8760)

    sys.argv = ["prog",
                "--l2-summary", str(tmp_path / "l2_summary.json"),
                "--l3-summary", str(tmp_path / "l3_summary.json"),
                "--l1-demand",  str(tmp_path / "l1_demand.csv"),
                "--outdir", str(tmp_path)]
    pnc.main()

    assert (tmp_path / "figX_network_comparison.pdf").exists()
    assert (tmp_path / "figX_network_comparison.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_paper_plot_style.py::test_network_comparison_smoke -v
```
Expected: `ModuleNotFoundError: No module named 'plot_network_comparison'`

- [ ] **Step 3: Write plot_network_comparison.py**

```python
"""
Figure — Network infrastructure comparison: L2 vs L3.

Usage:
    python scripts/paper/plot_network_comparison.py \
        --l2-summary outputs/paper/L2_january/thermal_network/network_summary.json \
        --l3-summary outputs/paper/L3_january/thermal_network/network_summary.json \
        --l1-demand  outputs/paper/L1_january/pf_timeseries.csv \
        --outdir     outputs/paper/figures/

Produces:
    figX_network_comparison.pdf / .png
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style, save_figure,
    DOUBLE_COL_W, H_WIDE_SHORT,
    C_L2, C_L3,
)

apply_ecm_style()

DEMAND_COL = "waermebedarf_MWth"

METRICS = [
    ("n_pipes",         "Number of pipes"),
    ("total_length_km", "Total pipe length [km]"),
    ("total_loss_mwh",  "Annual heat loss [MWh]"),
    ("loss_pct",        "Heat loss [% of demand]"),
]


def _load_summary(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _compute_metrics(summary: dict, demand_mwh: float) -> dict:
    pipes          = summary.get("pipes", {})
    total_len_m    = sum(float(p.get("length_m", 0)) for p in pipes.values())
    total_loss_mwh = sum(float(p.get("total_heat_loss_mwh", 0)) for p in pipes.values())
    return {
        "n_pipes":         len(pipes),
        "total_length_km": total_len_m / 1000,
        "total_loss_mwh":  total_loss_mwh,
        "loss_pct":        total_loss_mwh / demand_mwh * 100 if demand_mwh > 0 else 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--l2-summary", required=True)
    parser.add_argument("--l3-summary", required=True)
    parser.add_argument("--l1-demand",  required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    dem_df     = pd.read_csv(args.l1_demand, sep=";", decimal=",")
    demand_mwh = dem_df[DEMAND_COL].fillna(0).sum() if DEMAND_COL in dem_df.columns else 1.0

    m_l2 = _compute_metrics(_load_summary(args.l2_summary), demand_mwh)
    m_l3 = _compute_metrics(_load_summary(args.l3_summary), demand_mwh)

    colors = [C_L2, C_L3]
    labels = ["L2 (5-node)", "L3 (30-node)"]

    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL_W, H_WIDE_SHORT))
    fig.subplots_adjust(wspace=0.50, left=0.06, right=0.98, top=0.78, bottom=0.22)

    for ax, (key, ylabel) in zip(axes, METRICS):
        vals = [m_l2[key], m_l3[key]]
        ax.bar([0, 1], vals, 0.5, color=colors, alpha=0.85, edgecolor="white")

        for xi, val in enumerate(vals):
            fmt = f"{val:.1f}" if val < 1000 else f"{val:,.0f}"
            ax.text(xi, val * 1.05, fmt, ha="center", va="bottom", fontsize=7)

        ax.set_xticks([0, 1])
        ax.set_xticklabels(["L2", "L3"])
        ax.set_ylabel(ylabel, fontsize=7)
        ax.set_ylim(0, max(vals) * 1.30 if max(vals) > 0 else 1)
        ax.grid(True, axis="y")

    fig.suptitle("Network infrastructure comparison — L2 vs L3", y=0.94)

    handles = [mpatches.Patch(color=c, label=l, alpha=0.85)
               for c, l in zip(colors, labels)]
    fig.legend(handles=handles, loc="lower center", ncol=2,
               fontsize=8, bbox_to_anchor=(0.5, -0.02), frameon=True)

    save_figure(fig, Path(args.outdir) / "figX_network_comparison")
    plt.close(fig)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_paper_plot_style.py::test_network_comparison_smoke -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/paper/plot_network_comparison.py tests/test_paper_plot_style.py
git commit -m "feat: add network infrastructure comparison figure (L2 vs L3)"
```

---

### Task 10: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run full test suite**

```
pytest tests/test_paper_plot_style.py -v
```
Expected: All 9 tests PASS (`test_ecm_dimensions`, `test_ecm_font_sizes`,
`test_apply_ecm_style_sets_rcparams`, `test_color_constants_defined`,
`test_dispatch_comparison_smoke`, `test_cost_comparison_smoke`,
`test_pipe_losses_smoke`, `test_storage_comparison_smoke`,
`test_co2_comparison_smoke`, `test_network_topology_smoke`,
`test_load_duration_smoke`, `test_network_comparison_smoke`)

- [ ] **Step 2: Regenerate all figures with real output data**

```bash
python scripts/paper/plot_dispatch_comparison.py \
    --l1 outputs/paper/L1/pf_timeseries.csv \
    --l2 outputs/paper/L2/pf_timeseries.csv \
    --l3 outputs/paper/L3/pf_timeseries.csv \
    --outdir outputs/paper/figures/

python scripts/paper/plot_cost_comparison.py \
    --l1 outputs/paper/L1/costs.json \
    --l2 outputs/paper/L2/costs.json \
    --l3 outputs/paper/L3/costs.json \
    --outdir outputs/paper/figures/

python scripts/paper/plot_pipe_losses.py \
    --l2-summary outputs/paper/L2_january/thermal_network/network_summary.json \
    --l3-summary outputs/paper/L3_january/thermal_network/network_summary.json \
    --l1-demand  outputs/paper/L1_january/pf_timeseries.csv \
    --outdir outputs/paper/figures/

python scripts/paper/plot_storage_comparison.py \
    --l1 outputs/paper/L1/pf_timeseries.csv \
    --l2 outputs/paper/L2/pf_timeseries.csv \
    --l3 outputs/paper/L3/pf_timeseries.csv \
    --outdir outputs/paper/figures/

python scripts/paper/plot_co2_comparison.py \
    --l1 outputs/paper/L1/costs.json \
    --l2 outputs/paper/L2/costs.json \
    --l3 outputs/paper/L3/costs.json \
    --outdir outputs/paper/figures/

python scripts/paper/plot_network_topology.py \
    --outdir outputs/paper/figures/

python scripts/paper/plot_load_duration.py \
    --l1 outputs/paper/L1/pf_timeseries.csv \
    --l2 outputs/paper/L2/pf_timeseries.csv \
    --l3 outputs/paper/L3/pf_timeseries.csv \
    --outdir outputs/paper/figures/

python scripts/paper/plot_network_comparison.py \
    --l2-summary outputs/paper/L2_january/thermal_network/network_summary.json \
    --l3-summary outputs/paper/L3_january/thermal_network/network_summary.json \
    --l1-demand  outputs/paper/L1_january/pf_timeseries.csv \
    --outdir outputs/paper/figures/
```

Expected: 8 × 2 files created in `outputs/paper/figures/` (PDF + PNG each)

- [ ] **Step 3: Final commit**

```bash
git add outputs/paper/figures/
git commit -m "chore: regenerate all paper figures in ECM journal style"
```

---

## Overleaf integration notes

Include figures in your LaTeX document as follows:

```latex
% Double-column figure (190 mm wide)
\begin{figure*}
  \centering
  \includegraphics[width=\textwidth]{figures/fig2_dispatch_comparison.pdf}
  \caption{Heat dispatch during the coldest week. (a) L1 copperplate,
           (b) L2 5-node, (c) L3 30-node.}
  \label{fig:dispatch}
\end{figure*}

% Single-column figure (90 mm wide)
\begin{figure}
  \centering
  \includegraphics[width=\columnwidth]{figures/fig3_cost_comparison.pdf}
  \caption{Annual cost breakdown across planning levels.}
  \label{fig:cost}
\end{figure}
```

Place all PDF files in a `figures/` subdirectory of your Overleaf project.
