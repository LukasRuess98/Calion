"""F5 - Waterfall decomposition from L3 to L3+."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.paper.figures.fig_utils import LEVEL_COLORS, apply_style, polish_axes, save_fig

RUNS = ROOT / "output" / "paper_runs"

COST_COLS = [
    "cost_fuel_eur",
    "cost_co2_eur",
    "cost_energy_buy_eur",
    "cost_pump_eur",
    "cost_dump_eur",
    "cost_demand_charge_eur",
]
LABELS = {
    "cost_fuel_eur": "Fuel",
    "cost_co2_eur": "CO2",
    "cost_energy_buy_eur": "Grid energy",
    "cost_pump_eur": "Pumping",
    "cost_dump_eur": "Curtailment",
    "cost_demand_charge_eur": "Demand charge",
}
COLOR_POS = "#B94E48"
COLOR_NEG = "#3F7CAC"


def _load(run_id: str) -> dict | None:
    path = RUNS / run_id / "economics.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    return df.iloc[0].to_dict() if not df.empty else None


def _total(row: dict) -> float:
    return float(row.get("cost_total_eur", sum(float(row.get(c, 0) or 0) for c in COST_COLS)))


def main() -> None:
    apply_style()

    r_l3 = _load("L3")
    r_l3p = _load("L3plus")
    if r_l3 is None or r_l3p is None:
        missing = [rid for rid, row in [("L3", r_l3), ("L3plus", r_l3p)] if row is None]
        print(f"[fig_cost_waterfall] Missing economics.csv for {', '.join(missing)} - skipping")
        return

    deltas = {c: float(r_l3p[c]) - float(r_l3[c]) for c in COST_COLS if c in r_l3 and c in r_l3p}
    base_total = _total(r_l3) / 1e3
    final_total = _total(r_l3p) / 1e3
    delta_vals = [v / 1e3 for v in deltas.values()]

    labels = ["L3 baseline"] + [LABELS.get(k, k) for k in deltas] + ["L3+ total"]
    x = np.arange(len(labels))
    width = 0.58

    fig, ax = plt.subplots(figsize=(5.35, 2.9))
    ax.bar(
        x[0], base_total, width,
        color=LEVEL_COLORS["L3"], edgecolor="white", linewidth=0.45,
        label="Baseline / total",
    )

    running = base_total
    connector_y = base_total
    for i, delta in enumerate(delta_vals, start=1):
        bottom = running if delta >= 0 else running + delta
        ax.bar(
            x[i], abs(delta), width, bottom=bottom,
            color=COLOR_POS if delta >= 0 else COLOR_NEG,
            edgecolor="white", linewidth=0.45,
        )
        ax.plot(
            [x[i - 1] + width / 2, x[i] - width / 2],
            [connector_y, connector_y],
            color="#777777", lw=0.55, ls=(0, (2, 2)), zorder=2,
        )
        sign = "+" if delta >= 0 else ""
        va = "bottom" if delta >= 0 else "top"
        offset = 1.2 if delta >= 0 else -1.2
        ax.text(
            x[i], bottom + abs(delta) + offset if delta >= 0 else bottom + offset,
            f"{sign}{delta:.1f}",
            ha="center", va=va, fontsize=6.4,
        )
        running += delta
        connector_y = running

    ax.plot(
        [x[-2] + width / 2, x[-1] - width / 2],
        [connector_y, connector_y],
        color="#777777", lw=0.55, ls=(0, (2, 2)), zorder=2,
    )
    ax.bar(
        x[-1], final_total, width,
        color=LEVEL_COLORS["L3plus"], edgecolor="white", linewidth=0.45,
    )
    ax.axhline(base_total, color=LEVEL_COLORS["L3"], lw=0.7, ls="--", alpha=0.75)

    ax.text(x[0], base_total + max(base_total, final_total) * 0.015, f"{base_total:,.0f}",
            ha="center", va="bottom", fontsize=6.4)
    ax.text(x[-1], final_total + max(base_total, final_total) * 0.015, f"{final_total:,.0f}",
            ha="center", va="bottom", fontsize=6.4)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("Annual cost [kEUR/yr]")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    upper = max(base_total, final_total, running) * 1.10
    lower = min(base_total, final_total, base_total + min(0, min(delta_vals, default=0))) * 0.96
    ax.set_ylim(lower, upper)

    legend_items = [
        mpatches.Patch(color=LEVEL_COLORS["L3"], label="L3 baseline"),
        mpatches.Patch(color=LEVEL_COLORS["L3plus"], label="L3+ total"),
        mpatches.Patch(color=COLOR_POS, label="Increase"),
        mpatches.Patch(color=COLOR_NEG, label="Reduction"),
    ]
    ax.legend(
        handles=legend_items, loc="upper left", ncol=2,
        frameon=True, framealpha=0.92, columnspacing=0.8,
        handlelength=1.1, handletextpad=0.35, borderpad=0.35,
    )
    polish_axes(ax, grid_axis="y")

    fig.tight_layout(pad=0.5)
    save_fig(fig, "fig_cost_waterfall")


if __name__ == "__main__":
    main()
