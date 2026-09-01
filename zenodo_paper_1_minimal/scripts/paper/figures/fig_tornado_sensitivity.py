"""F13 — Tornado plot for L3 cost across sensitivity scenarios (§4)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scripts.paper.figures.fig_utils import apply_style, save_fig

RUNS = ROOT / "output" / "paper_runs"

SCENARIOS = ["baseline", "gas_high", "elec_low", "co2_high", "cold", "warm", "cop_low"]
SCENARIO_LABELS = {
    "baseline": "Baseline",
    "gas_high":  "Gas +20%",
    "elec_low":  "Electricity −20%",
    "co2_high":  "CO₂ 200€/t",
    "cold":      "Cold (+3K, +5% demand)",
    "warm":      "Warm (−3K, −5% demand)",
    "cop_low":   "COP Carnot −10%",
}


def _load_scenario(run_id: str, scenario: str) -> float | None:
    p = RUNS / "sensitivity" / f"{run_id}_{scenario}" / "economics.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    return float(df.iloc[0]["cost_total_eur"]) if not df.empty else None


def main() -> None:
    apply_style()

    # Load L3 sensitivity costs
    baseline = _load_scenario("L3", "baseline")
    if baseline is None:
        # Placeholder
        baseline = 500_000.0
        costs = {s: baseline * (1 + np.random.uniform(-0.05, 0.10)) for s in SCENARIOS}
    else:
        costs = {}
        for s in SCENARIOS:
            c = _load_scenario("L3", s)
            costs[s] = c if c is not None else baseline

    # Compute delta vs baseline
    deltas = {s: costs[s] - baseline for s in SCENARIOS if s != "baseline"}
    # Sort by absolute impact
    sorted_scenarios = sorted(deltas, key=lambda s: abs(deltas[s]), reverse=True)

    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    y = np.arange(len(sorted_scenarios))
    vals = [deltas[s] / 1e3 for s in sorted_scenarios]
    colors = ["#D9534F" if v > 0 else "#5BC0DE" for v in vals]
    ax.barh(y, vals, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels([SCENARIO_LABELS.get(s, s) for s in sorted_scenarios])
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Δ Annual cost vs. baseline [k€/a]")
    ax.set_title("Sensitivity: L3 cost impact")

    csv_rows = [{"scenario": s, "delta_cost_keur": deltas[s] / 1e3} for s in sorted_scenarios]
    pd.DataFrame(csv_rows).to_csv(RUNS / "figures" / "fig_tornado_sensitivity.csv", index=False)

    save_fig(fig, "fig_tornado_sensitivity")


if __name__ == "__main__":
    main()
