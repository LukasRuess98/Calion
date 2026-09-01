"""F12 — Synthetic: L3+ -> L3^NL linearization error on 4 axes. Needs Gurobi."""
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
AXES_LABELS = [
    ("heat_intensity", "Heat intensity [HI]"),
    ("storage_h",      "Storage size [h]"),
    ("n_nodes",        "Number of nodes"),
    ("length_km",      "Network length [km]"),
]


def _load_gap(config_id: str) -> float | None:
    l3pp = RUNS / config_id / "L3plus" / "economics.csv"
    l3nl = RUNS / config_id / "L3NL"   / "economics.csv"
    if not l3pp.exists() or not l3nl.exists():
        return None
    c3p = pd.read_csv(l3pp).iloc[0]["cost_total_eur"]
    cnl = pd.read_csv(l3nl).iloc[0]["cost_total_eur"]
    return float((cnl - c3p) / c3p * 100)


def main() -> None:
    apply_style()

    config_dirs = sorted(RUNS.glob("synth_*")) if RUNS.exists() else []
    records = []
    for cd in config_dirs:
        gap = _load_gap(cd.name)
        if gap is None:
            continue
        meta_f = ROOT / "synth_configs" / f"{cd.name}.yaml"
        if not meta_f.exists():
            continue
        import yaml
        with open(meta_f) as f:
            meta = yaml.safe_load(f)
        net = meta.get("network", {})
        records.append({
            "gap_pct":       gap,
            "heat_intensity": net.get("heat_intensity", np.nan),
            "storage_h":     meta.get("storage_hours", np.nan),
            "n_nodes":       net.get("n_nodes", np.nan),
            "length_km":     sum(e.get("length_km", 0) for e in net.get("pipes", [])),
        })

    placeholder = len(records) == 0
    if placeholder:
        rng = np.random.default_rng(12)
        n = 36
        records = [{
            "gap_pct":       rng.uniform(0.0, 3.5),
            "heat_intensity": rng.choice([0.1, 0.4, 0.8]),
            "storage_h":     rng.choice([2, 6, 12]),
            "n_nodes":       rng.choice([5, 15, 30]),
            "length_km":     rng.uniform(1, 50),
        } for _ in range(n)]

    df = pd.DataFrame(records)
    fig, axes = plt.subplots(2, 2, figsize=(7.5, 6.0))
    axes_flat = axes.flatten()

    for ax, (col, xlabel) in zip(axes_flat, AXES_LABELS):
        ax.scatter(df[col], df["gap_pct"], s=25, alpha=0.65,
                   color="#D01C8B", edgecolors="white", lw=0.4)
        if len(df) >= 4:
            z = np.polyfit(df[col].values, df["gap_pct"].values, 1)
            xfit = np.linspace(df[col].min(), df[col].max(), 80)
            ax.plot(xfit, np.polyval(z, xfit), color="#D01C8B", lw=1.0, linestyle="--")
        ax.axhline(0, color="black", lw=0.6, linestyle=":")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(r"L3$^+$ $\to$ L3$^\mathrm{NL}$ gap [%]" if ax == axes_flat[0] else "")

    fig.suptitle(r"Linearization error: L3$^+$ vs L3$^\mathrm{NL}$ across synthetic networks",
                 fontsize=9)
    plt.tight_layout()

    if placeholder:
        fig.text(0.5, -0.01, "[PLACEHOLDER — Gurobi synthetic runs needed]",
                 ha="center", fontsize=7, color="gray", style="italic")

    out = ROOT / "output" / "paper_runs" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "fig_synth_lin_error.csv", index=False)

    save_fig(fig, "fig_synth_lin_error")


if __name__ == "__main__":
    main()
