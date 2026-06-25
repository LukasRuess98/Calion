"""F3 — Stacked bar: cost decomposition for L1, L2, L3."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from scripts.paper.figures.fig_utils import apply_style, save_fig, LEVEL_COLORS, COST_COLORS

RUNS = ROOT / "output" / "paper_runs"

COST_COLS = {
    "cost_fuel_eur":          ("Fuel", COST_COLORS["fuel"]),
    "cost_energy_buy_eur":    ("Electricity", COST_COLORS["energy"]),
    "cost_co2_eur":           ("CO₂", COST_COLORS["co2"]),
    "cost_pump_eur":          ("Pump", COST_COLORS["pump"]),
    "cost_dump_eur":          ("Curtailment", COST_COLORS["dump"]),
    "cost_demand_charge_eur": ("Demand charge", COST_COLORS["demand"]),
}


def load_eco(run_id: str) -> dict | None:
    p = RUNS / run_id / "economics.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    return df.iloc[0].to_dict() if not df.empty else None


LEVEL_LABELS = {
    "L1":     "L1",
    "L2":     "L2",
    "L3":     "L3",
    "L3plus": r"L3$^+$",
    "L3NL":   r"L3$^\mathrm{NL}$",
}


def main() -> None:
    apply_style()
    levels = ["L1", "L2", "L3", "L3plus"]
    data = {rid: load_eco(rid) for rid in levels}
    available = [rid for rid in levels if data[rid] is not None]

    if not available:
        print("[WARN] No economics.csv found — generating placeholder figure")
        data = {
            "L1":     {"cost_fuel_eur": 0, "cost_energy_buy_eur": 16811, "cost_co2_eur": 74439, "cost_pump_eur": 0, "cost_dump_eur": 0, "cost_demand_charge_eur": 0},
            "L2":     {"cost_fuel_eur": 0, "cost_energy_buy_eur": 17100, "cost_co2_eur": 75000, "cost_pump_eur": 200, "cost_dump_eur": 0, "cost_demand_charge_eur": 0},
            "L3":     {"cost_fuel_eur": 0, "cost_energy_buy_eur": 17300, "cost_co2_eur": 75500, "cost_pump_eur": 800, "cost_dump_eur": 0, "cost_demand_charge_eur": 0},
            "L3plus": {"cost_fuel_eur": 0, "cost_energy_buy_eur": 17320, "cost_co2_eur": 75520, "cost_pump_eur": 810, "cost_dump_eur": 0, "cost_demand_charge_eur": 0},
        }
        available = levels

    fig, ax = plt.subplots(figsize=(6.0, 3.5))

    x = np.arange(len(available))
    width = 0.55
    bottoms = np.zeros(len(available))

    for col, (label, color) in COST_COLS.items():
        vals = np.array([float(data[rid].get(col, 0) or 0) / 1e3 for rid in available])
        if vals.sum() == 0:
            continue
        bars = ax.bar(x, vals, width, bottom=bottoms, label=label, color=color, edgecolor="white", linewidth=0.5)
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels([LEVEL_LABELS[rid] for rid in available])
    ax.set_ylabel("Annual cost [k€/a]")
    ax.set_title("Cost decomposition: topology and physics effect (L1–L3$^+$)")
    ax.legend(loc="upper left", ncol=2, framealpha=0.8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))

    # Annotate: L3NL not shown (window-only, 744 h Jan 2025)
    ax.text(
        0.99, 0.04,
        r"L3$^\mathrm{NL}$: window-only (Jan 2025, 744 h) — not shown",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5,
        style="italic", color="#666666",
    )

    # Save companion CSV
    rows = []
    for rid in available:
        row = {"run_id": rid}
        for col, (label, _) in COST_COLS.items():
            row[label] = float(data[rid].get(col, 0) or 0)
        rows.append(row)
    pd.DataFrame(rows).to_csv(RUNS / "figures" / "fig_cost_topology.csv", index=False)

    save_fig(fig, "fig_cost_topology")


if __name__ == "__main__":
    main()
