"""
Figure 3 — Annual cost breakdown: stacked bar (L1 / L2 / L3).

Usage:
    python scripts/paper/plot_cost_comparison.py \
        --l1 outputs/paper/L1/costs.json \
        --l2 outputs/paper/L2/costs.json \
        --l3 outputs/paper/L3/costs.json \
        --outdir outputs/paper/figures/

Produces:
    fig3_cost_comparison.pdf  (vector — use in Overleaf)
    fig3_cost_comparison.png  (300 DPI preview)
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

    # €/MWh specific cost
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

    # Console summary
    print("\n-- Cost summary ---------------------------------------------------")
    for k, (label, _) in COST_COMPONENTS.items():
        vals = [_get(c, k) for c in all_costs]
        if any(v > 0 for v in vals):
            d2 = (vals[1]-vals[0])/vals[0]*100 if vals[0] else float("nan")
            d3 = (vals[2]-vals[0])/vals[0]*100 if vals[0] else float("nan")
            print(f"  {label:<26} {vals[0]:>14,.0f}  {vals[1]:>14,.0f}  "
                  f"{vals[2]:>14,.0f}  {d2:>+8.1f}%  {d3:>+8.1f}%")


if __name__ == "__main__":
    main()
