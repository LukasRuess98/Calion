"""F5 — Waterfall: L3 -> L3+ cost decomposition."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from scripts.paper.figures.fig_utils import apply_style, save_fig, LEVEL_COLORS

RUNS = ROOT / "output" / "paper_runs"

COST_COLS = ["cost_fuel_eur", "cost_co2_eur", "cost_energy_buy_eur",
             "cost_pump_eur", "cost_dump_eur", "cost_demand_charge_eur"]
LABELS = {
    "cost_fuel_eur":          "Fuel cost",
    "cost_co2_eur":           "CO2 cost",
    "cost_energy_buy_eur":    "Grid energy",
    "cost_pump_eur":          "Pumping",
    "cost_dump_eur":          "Dump heat",
    "cost_demand_charge_eur": "Demand charge",
}
COLORS_POS = "#D9534F"
COLORS_NEG = "#5BC0DE"


def _load(run_id: str) -> dict | None:
    p = RUNS / run_id / "economics.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    return df.iloc[0].to_dict() if not df.empty else None


def _make_placeholder() -> tuple[dict, dict]:
    base = 450_000.0
    l3 = {c: base * 0.12 + i * 8000 for i, c in enumerate(COST_COLS)}
    l3["cost_total_eur"] = sum(l3.values())
    l3plus = {c: v * (1 + np.random.uniform(-0.08, 0.03)) for c, v in l3.items()}
    l3plus["cost_pump_eur"] = l3["cost_pump_eur"] * 1.15
    l3plus["cost_total_eur"] = sum(l3plus[c] for c in COST_COLS)
    return l3, l3plus


def main() -> None:
    apply_style()

    r_l3   = _load("L3")
    r_l3p  = _load("L3plus")
    placeholder = r_l3 is None or r_l3p is None
    if placeholder:
        r_l3, r_l3p = _make_placeholder()

    deltas = {c: r_l3p[c] - r_l3[c] for c in COST_COLS if c in r_l3 and c in r_l3p}
    total_delta = r_l3p.get("cost_total_eur", sum(r_l3p[c] for c in COST_COLS)) - \
                  r_l3.get("cost_total_eur",  sum(r_l3[c]  for c in COST_COLS))

    items = list(deltas.items())
    items.append(("total", total_delta))

    steps = [LABELS.get(k, k) for k, _ in items[:-1]] + ["Net total"]
    vals  = [v / 1e3 for _, v in items]

    running = r_l3.get("cost_total_eur", sum(r_l3[c] for c in COST_COLS)) / 1e3
    bottoms = []
    for v in vals[:-1]:
        bottoms.append(running)
        running += v
    bottoms.append(r_l3.get("cost_total_eur", 0) / 1e3)

    colors = [COLORS_POS if v >= 0 else COLORS_NEG for v in vals]
    colors[-1] = LEVEL_COLORS["L3plus"]

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    x = np.arange(len(steps))
    bars = ax.bar(x[:-1], vals[:-1], bottom=bottoms[:-1],
                  color=colors[:-1], edgecolor="white", linewidth=0.5)
    ax.bar(x[-1:], [r_l3p.get("cost_total_eur", 0) / 1e3],
           color=LEVEL_COLORS["L3plus"], edgecolor="white", linewidth=0.5, alpha=0.85)
    ax.bar(x[:1] - 0.4, [r_l3.get("cost_total_eur", 0) / 1e3], width=0.35,
           color=LEVEL_COLORS["L3"], edgecolor="white", linewidth=0.5, alpha=0.85)

    for bar, v in zip(bars, vals[:-1]):
        sign = "+" if v >= 0 else ""
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_y() + bar.get_height() + (2 if v >= 0 else -6),
                f"{sign}{v:.1f}", ha="center", va="bottom", fontsize=6.5)

    ax.axhline(r_l3.get("cost_total_eur", 0) / 1e3, color=LEVEL_COLORS["L3"],
               lw=0.8, linestyle="--", alpha=0.7)

    ax.set_xticks(x)
    ax.set_xticklabels(["L3 baseline"] + steps[1:], rotation=20, ha="right")
    ax.set_ylabel("Annual cost [k€/a]")
    ax.set_title(r"Cost decomposition: L3 $\to$ L3$^+$ (full physics)")

    legend_items = [
        mpatches.Patch(color=COLORS_POS, label="Cost increase"),
        mpatches.Patch(color=COLORS_NEG, label="Cost reduction"),
        mpatches.Patch(color=LEVEL_COLORS["L3plus"], label=r"L3$^+$ total"),
    ]
    ax.legend(handles=legend_items, fontsize=7, frameon=False)

    if placeholder:
        ax.text(0.5, 0.97, "[PLACEHOLDER — no run data]", transform=ax.transAxes,
                ha="center", va="top", fontsize=7, color="gray", style="italic")

    rows = [{"component": k, "l3_keur": r_l3.get(k, 0) / 1e3,
             "l3plus_keur": r_l3p.get(k, 0) / 1e3,
             "delta_keur": deltas.get(k, 0) / 1e3} for k in COST_COLS]
    out = RUNS / "figures"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "fig_cost_waterfall.csv", index=False)

    save_fig(fig, "fig_cost_waterfall")


if __name__ == "__main__":
    main()
