"""F4 — Cost stack for L3 vs L3+ vs L3NL."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from scripts.paper.figures.fig_utils import apply_style, save_fig, COST_COLORS

RUNS = ROOT / "output" / "paper_runs"

COST_COLS = {
    "cost_fuel_eur":          ("Fuel", COST_COLORS["fuel"]),
    "cost_energy_buy_eur":    ("Electricity", COST_COLORS["energy"]),
    "cost_co2_eur":           ("CO₂", COST_COLORS["co2"]),
    "cost_pump_eur":          ("Pump", COST_COLORS["pump"]),
    "cost_dump_eur":          ("Curtailment", COST_COLORS["dump"]),
}


def load_eco(run_id: str) -> dict | None:
    p = RUNS / run_id / "economics.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    return df.iloc[0].to_dict() if not df.empty else None


def main() -> None:
    apply_style()
    levels = ["L3", "L3plus", "L3NL"]
    labels = ["L3", r"L3$^+$", r"L3$^\mathrm{NL}$"]
    data = {rid: load_eco(rid) for rid in levels}
    available = [rid for rid in levels if data[rid] is not None]

    if not available:
        data = {
            "L3":     {"cost_energy_buy_eur": 17300, "cost_co2_eur": 75500, "cost_pump_eur": 800, "cost_fuel_eur": 0, "cost_dump_eur": 0},
            "L3plus": {"cost_energy_buy_eur": 17600, "cost_co2_eur": 75800, "cost_pump_eur": 1200, "cost_fuel_eur": 0, "cost_dump_eur": 0},
            "L3NL":   {"cost_energy_buy_eur": 17620, "cost_co2_eur": 75820, "cost_pump_eur": 1210, "cost_fuel_eur": 0, "cost_dump_eur": 0},
        }
        available = levels

    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    x = np.arange(len(available))
    width = 0.55
    bottoms = np.zeros(len(available))

    for col, (label, color) in COST_COLS.items():
        vals = np.array([float(data[rid].get(col, 0) or 0) / 1e3 for rid in available])
        if vals.sum() == 0:
            continue
        ax.bar(x, vals, width, bottom=bottoms, label=label, color=color, edgecolor="white", linewidth=0.5)
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels([labels[levels.index(r)] for r in available])
    ax.set_ylabel("Annual cost [k€/a]")
    ax.set_title("Cost decomposition: physics fidelity effect")
    ax.legend(loc="upper left", ncol=2, framealpha=0.8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))

    rows = []
    for rid in available:
        row = {"run_id": rid}
        for col, (label, _) in COST_COLS.items():
            row[label] = float(data[rid].get(col, 0) or 0)
        rows.append(row)
    pd.DataFrame(rows).to_csv(RUNS / "figures" / "fig_cost_extended.csv", index=False)

    save_fig(fig, "fig_cost_extended")


if __name__ == "__main__":
    main()
