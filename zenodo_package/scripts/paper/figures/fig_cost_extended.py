"""F4 - Stacked cost decomposition for L3, L3+, and L3NL."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.paper.figures.fig_utils import (
    COST_COLORS,
    LEVEL_LABELS,
    apply_style,
    polish_axes,
    save_fig,
)

RUNS = ROOT / "output" / "paper_runs"

COST_COLS = {
    "cost_fuel_eur": ("Fuel", COST_COLORS["fuel"]),
    "cost_energy_buy_eur": ("Electricity", COST_COLORS["energy"]),
    "cost_co2_eur": ("CO2", COST_COLORS["co2"]),
    "cost_pump_eur": ("Pump", COST_COLORS["pump"]),
    "cost_dump_eur": ("Curtailment", COST_COLORS["dump"]),
}


def load_eco(run_id: str) -> dict | None:
    path = RUNS / run_id / "economics.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    return df.iloc[0].to_dict() if not df.empty else None


def main() -> None:
    apply_style()
    levels = ["L3", "L3plus", "L3NL"]
    data = {rid: load_eco(rid) for rid in levels}
    missing = [rid for rid in levels if data[rid] is None]
    if missing:
        print(f"[fig_cost_extended] Missing economics.csv for {', '.join(missing)} - skipping")
        return

    fig, ax = plt.subplots(figsize=(3.65, 2.6))
    x = np.arange(len(levels))
    width = 0.58
    bottoms = np.zeros(len(levels))

    for col, (label, color) in COST_COLS.items():
        vals = np.array([float(data[rid].get(col, 0) or 0) / 1e3 for rid in levels])
        if vals.sum() == 0:
            continue
        ax.bar(
            x, vals, width, bottom=bottoms, label=label, color=color,
            edgecolor="white", linewidth=0.45,
        )
        bottoms += vals

    for xi, total in zip(x, bottoms):
        ax.text(xi, total + max(bottoms) * 0.015, f"{total:,.0f}",
                ha="center", va="bottom", fontsize=6.4)

    ax.set_xticks(x)
    ax.set_xticklabels([LEVEL_LABELS[rid] for rid in levels])
    ax.set_ylabel("Annual cost [kEUR/yr]")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylim(0, max(bottoms) * 1.13)
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, 1.03), ncol=3,
        frameon=True, framealpha=0.92, columnspacing=0.8,
        handlelength=1.1, handletextpad=0.35, borderpad=0.35,
    )
    polish_axes(ax, grid_axis="y")

    fig.tight_layout(pad=0.45)
    save_fig(fig, "fig_cost_extended")


if __name__ == "__main__":
    main()
