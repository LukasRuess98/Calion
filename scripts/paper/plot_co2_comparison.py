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
    figX_co2_comparison.pdf  (vector — use in Overleaf)
    figX_co2_comparison.png  (300 DPI preview)
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

LEVEL_LABELS = ["L1\n(1-node)", "L2\n(5-node)", "L3\n(24-node)"]


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
