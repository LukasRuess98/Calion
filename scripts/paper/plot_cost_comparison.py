"""
Figure 3 — Annual cost breakdown: grouped bar chart (L1 / L2 / L3).

Usage:
    python scripts/paper/plot_cost_comparison.py \
        --l1 outputs/paper/L1/costs.json \
        --l2 outputs/paper/L2/costs.json \
        --l3 outputs/paper/L3/costs.json \
        --outdir outputs/paper/figures/

Produces:
    fig3_cost_comparison.pdf / .svg / .png
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── Cost keys to extract from costs.json (under "PF" section) ────────────────
COST_COMPONENTS = {
    "Grid_energy_cost_EUR":    ("Grid electricity",   "#4c96d7"),
    "Fuel_cost_EUR":           ("Gas fuel",           "#e07b39"),
    "CO2_cost_EUR":            ("CO₂",                "#78909c"),
    "Demand_charge_cost_EUR":  ("Demand charge",      "#ab47bc"),
    "Dump_cost_EUR":           ("Heat dump",          "#ef5350"),
    "Capex_cost_EUR":          ("CAPEX",              "#26a69a"),
}
TOTAL_KEY = "OBJ_value_EUR"

LEVEL_LABELS = ["L1\n(1-node)", "L2\n(5-node)", "L3\n(30-node)"]
LEVEL_TAGS   = ["L1", "L2", "L3"]


def _load_costs(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # costs.json can be {"PF": {...}} or flat
    if "PF" in data:
        return data["PF"]
    return data


def _get(costs: dict, key: str) -> float:
    # search top-level and nested "objective" sub-dict
    if key in costs:
        return float(costs[key])
    obj = costs.get("objective", {})
    if key in obj:
        return float(obj[key])
    return 0.0


def main():
    parser = argparse.ArgumentParser(description="Figure 3 — cost comparison")
    parser.add_argument("--l1", required=True)
    parser.add_argument("--l2", required=True)
    parser.add_argument("--l3", required=True)
    parser.add_argument("--outdir", default="outputs/paper/figures")
    args = parser.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    paths = [args.l1, args.l2, args.l3]
    all_costs = [_load_costs(p) for p in paths]

    # ── Totals for annotations ────────────────────────────────────────────────
    totals = [_get(c, TOTAL_KEY) for c in all_costs]
    if all(t == 0 for t in totals):
        # fallback: sum components
        totals = [sum(_get(c, k) for k in COST_COMPONENTS) for c in all_costs]

    # ── Build matrix: rows = levels, cols = components ────────────────────────
    comp_keys   = list(COST_COMPONENTS.keys())
    comp_labels = [v[0] for v in COST_COMPONENTS.values()]
    comp_colors = [v[1] for v in COST_COMPONENTS.values()]

    matrix = np.array([[_get(c, k) / 1e6 for k in comp_keys] for c in all_costs])  # → M EUR

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(LEVEL_TAGS))
    bar_w = 0.55

    bottoms = np.zeros(len(LEVEL_TAGS))
    bars = []
    for i, (label, color) in enumerate(zip(comp_labels, comp_colors)):
        vals = matrix[:, i]
        b = ax.bar(x, vals, bar_w, bottom=bottoms, color=color, label=label,
                   edgecolor="white", linewidth=0.5)
        bars.append(b)
        bottoms += vals

    # Total annotations on top
    for xi, total in zip(x, totals):
        ax.text(xi, bottoms[xi] + 0.02 * max(bottoms),
                f"{total/1e6:.2f} M€",
                ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Δ annotations: show deviation of L2 and L3 from L1
    if totals[0] > 0:
        for xi in [1, 2]:
            delta_pct = (totals[xi] - totals[0]) / totals[0] * 100
            sign = "+" if delta_pct >= 0 else ""
            ax.text(xi, -0.06 * max(bottoms),
                    f"Δ vs L1: {sign}{delta_pct:.1f}%",
                    ha="center", va="top", fontsize=8, color="#333333",
                    style="italic")

    ax.set_xticks(x)
    ax.set_xticklabels(LEVEL_LABELS, fontsize=10)
    ax.set_ylabel("Annual cost [M€]", fontsize=10)
    ax.set_title("Annual system cost breakdown — L1 / L2 / L3 (perfect forecast)", fontsize=11)
    ax.set_ylim(bottom=0)
    ax.grid(True, axis="y", alpha=0.35, linewidth=0.6)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    stem = Path(args.outdir) / "fig3_cost_comparison"
    for fmt in ("pdf", "svg", "png"):
        fig.savefig(f"{stem}.{fmt}", dpi=300, bbox_inches="tight")
        print(f"Saved: {stem}.{fmt}")
    plt.close(fig)

    # ── Print summary table to console ───────────────────────────────────────
    print("\n── Cost summary (EUR) ─────────────────────────────────────")
    header = f"{'Component':<28} {'L1':>14} {'L2':>14} {'L3':>14}  {'ΔL2-L1%':>9}  {'ΔL3-L1%':>9}"
    print(header)
    print("-" * len(header))
    for k, (label, _) in COST_COMPONENTS.items():
        vals = [_get(c, k) for c in all_costs]
        delta2 = (vals[1] - vals[0]) / vals[0] * 100 if vals[0] else float("nan")
        delta3 = (vals[2] - vals[0]) / vals[0] * 100 if vals[0] else float("nan")
        print(f"  {label:<26} {vals[0]:>14,.0f} {vals[1]:>14,.0f} {vals[2]:>14,.0f}"
              f"  {delta2:>+8.1f}%  {delta3:>+8.1f}%")
    print("-" * len(header))
    t = totals
    delta2 = (t[1] - t[0]) / t[0] * 100 if t[0] else float("nan")
    delta3 = (t[2] - t[0]) / t[0] * 100 if t[0] else float("nan")
    print(f"  {'TOTAL':<26} {t[0]:>14,.0f} {t[1]:>14,.0f} {t[2]:>14,.0f}"
          f"  {delta2:>+8.1f}%  {delta3:>+8.1f}%")


if __name__ == "__main__":
    main()
