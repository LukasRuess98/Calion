"""F11 — Synthetic: L3->L3+ physics gap vs transport delay. Needs Gurobi."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scripts.paper.figures.fig_utils import apply_style, save_fig

RUNS = ROOT / "output" / "paper_runs" / "synthetic"


def _load_gap(config_id: str) -> float | None:
    l3p  = RUNS / config_id / "L3"     / "economics.csv"
    l3pp = RUNS / config_id / "L3plus" / "economics.csv"
    if not l3p.exists() or not l3pp.exists():
        return None
    c3  = pd.read_csv(l3p).iloc[0]["cost_total_eur"]
    c3p = pd.read_csv(l3pp).iloc[0]["cost_total_eur"]
    return float((c3p - c3) / c3 * 100)


def _max_delay(config_id: str) -> float | None:
    fig_topo = ROOT / "output" / "paper_runs" / "figures" / "fig_topology.csv"
    if fig_topo.exists():
        df = pd.read_csv(fig_topo)
        return float(df["delay_h"].max())
    return None


def main() -> None:
    apply_style()

    config_dirs = sorted(RUNS.glob("synth_*")) if RUNS.exists() else []
    delays, gaps = [], []

    for cd in config_dirs:
        cid = cd.name
        gap = _load_gap(cid)
        if gap is None:
            continue
        d = _max_delay(cid)
        if d is None:
            continue
        delays.append(d)
        gaps.append(gap)

    placeholder = len(delays) == 0
    if placeholder:
        rng = np.random.default_rng(11)
        delays = rng.uniform(0.1, 4.0, 36).tolist()
        gaps   = [-0.3 + 0.8 * d + rng.normal(0, 0.5) for d in delays]

    fig, ax = plt.subplots(figsize=(5.5, 4.0))
    ax.scatter(delays, gaps, s=30, color="#4DAC26", alpha=0.7,
               edgecolors="white", lw=0.5)

    if len(delays) >= 4:
        z = np.polyfit(delays, gaps, 1)
        xfit = np.linspace(min(delays), max(delays), 100)
        r2 = np.corrcoef(delays, gaps)[0, 1] ** 2
        ax.plot(xfit, np.polyval(z, xfit), color="#4DAC26", lw=1.2,
                linestyle="--", label=f"Linear fit (R2={r2:.2f})")
        ax.legend(fontsize=7)

    ax.axhline(0, color="black", lw=0.7, linestyle=":")
    ax.set_xlabel("Max transport delay [h]")
    ax.set_ylabel(r"L3 $\to$ L3$^+$ cost gap [%]")
    ax.set_title(r"Physics gap vs transport delay (36 synthetic networks)")

    if placeholder:
        ax.text(0.05, 0.95, "[PLACEHOLDER — Gurobi synthetic runs needed]",
                transform=ax.transAxes, fontsize=7, color="gray",
                style="italic", va="top")

    out = ROOT / "output" / "paper_runs" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"delay_h": delays, "gap_pct": gaps}).to_csv(
        out / "fig_synth_physics_gap.csv", index=False)

    save_fig(fig, "fig_synth_physics_gap")


if __name__ == "__main__":
    main()
