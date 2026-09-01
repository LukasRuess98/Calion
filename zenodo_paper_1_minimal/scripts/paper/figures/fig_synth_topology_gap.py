"""F10 — Synthetic: L1->L2 topology gap vs pipe length. Needs Gurobi runs."""
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
    l1p = RUNS / config_id / "L1" / "economics.csv"
    l2p = RUNS / config_id / "L2" / "economics.csv"
    if not l1p.exists() or not l2p.exists():
        return None
    c1 = pd.read_csv(l1p).iloc[0]["cost_total_eur"]
    c2 = pd.read_csv(l2p).iloc[0]["cost_total_eur"]
    return float((c2 - c1) / c1 * 100)


def _load_meta(config_id: str) -> dict | None:
    import json
    p = RUNS / config_id / "meta.yaml"
    if not p.exists():
        # try synth_configs directory for params
        q = ROOT / "synth_configs" / f"{config_id}.yaml"
        if not q.exists():
            return None
        import yaml
        with open(q) as f:
            return yaml.safe_load(f)
    return None


def main() -> None:
    apply_style()

    config_dirs = sorted(RUNS.glob("synth_*")) if RUNS.exists() else []
    lengths, gaps = [], []

    for cd in config_dirs:
        cid = cd.name
        gap = _load_gap(cid)
        if gap is None:
            continue
        meta = _load_meta(cid)
        if meta is None:
            continue
        total_len = sum(e.get("length_km", 0) for e in meta.get("network", {}).get("pipes", []))
        lengths.append(total_len)
        gaps.append(gap)

    placeholder = len(lengths) == 0
    if placeholder:
        rng = np.random.default_rng(10)
        lengths = rng.uniform(1, 50, 36).tolist()
        gaps    = [0.5 + 0.12 * l + rng.normal(0, 1.5) for l in lengths]

    fig, ax = plt.subplots(figsize=(5.5, 4.0))
    ax.scatter(lengths, gaps, s=30, color="#2166AC", alpha=0.7, edgecolors="white", lw=0.5)

    if len(lengths) >= 4:
        z = np.polyfit(lengths, gaps, 1)
        xfit = np.linspace(min(lengths), max(lengths), 100)
        ax.plot(xfit, np.polyval(z, xfit), color="#2166AC", lw=1.2,
                linestyle="--", label=f"Linear fit (R2={np.corrcoef(lengths, gaps)[0,1]**2:.2f})")
        ax.legend(fontsize=7)

    ax.axhline(0, color="black", lw=0.7, linestyle=":")
    ax.set_xlabel("Total network length [km]")
    ax.set_ylabel("L1 -> L2 cost gap [%]")
    ax.set_title("Topology gap vs network length (36 synthetic networks)")

    if placeholder:
        ax.text(0.05, 0.95, "[PLACEHOLDER — Gurobi synthetic runs needed]",
                transform=ax.transAxes, fontsize=7, color="gray",
                style="italic", va="top")

    out = ROOT / "output" / "paper_runs" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"length_km": lengths, "gap_pct": gaps}).to_csv(
        out / "fig_synth_topology_gap.csv", index=False)

    save_fig(fig, "fig_synth_topology_gap")


if __name__ == "__main__":
    main()
