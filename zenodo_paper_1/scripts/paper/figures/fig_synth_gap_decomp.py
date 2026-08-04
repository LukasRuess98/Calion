"""
fig_synth_gap_decomp.py
=======================
Topology gap decomposition into additive cost components.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.paper.figures.fig_utils import (
    DIRECTION_COLORS,
    apply_style,
    polish_axes,
    save_fig,
)

SYNTH = ROOT / "output" / "paper_runs" / "synth"
KEUR = 1000.0
C_TOPO = "#2C7BB6"
C_LOSS = "#B94E48"
C_PRESS = "#E2A448"


def _load() -> pd.DataFrame:
    if not SYNTH.exists():
        raise FileNotFoundError(f"Missing synthetic run directory: {SYNTH}")

    rows = []
    for d in sorted(SYNTH.iterdir()):
        eco = d / "economics.csv"
        if not eco.exists():
            continue
        m = re.match(r"^(.+)_(L1cp|L1|L2|L3)$", d.name)
        if not m:
            continue
        config, level = m.group(1), m.group(2)
        if not re.match(r"synth_n\d+_L", config):
            continue
        p = re.match(r"synth_n(\d+)_L([\dp]+)km_hi([\dp]+)_s(\d+)h", config)
        rows.append({
            "config": config,
            "level": level,
            "cost": float(pd.read_csv(eco).iloc[0]["cost_total_eur"]),
            "pipe_km": float(p.group(2).replace("p", ".")) if p else None,
            "n_nodes": int(p.group(1)) if p else None,
            "hi": float(p.group(3).replace("p", ".")) if p else None,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    piv = df.pivot(index="config", columns="level", values="cost")
    meta = df[df["level"] == "L1cp"][["config", "pipe_km", "n_nodes", "hi"]].set_index("config")
    piv = piv.join(meta).dropna(subset=["L1cp", "L1", "L2", "L3"])
    piv["delta_topology"] = (piv["L1"] - piv["L1cp"]) / KEUR
    piv["delta_heatloss"] = (piv["L2"] - piv["L1"]) / KEUR
    piv["delta_pressure"] = (piv["L3"] - piv["L2"]) / KEUR
    piv["delta_combined"] = (piv["L3"] - piv["L1cp"]) / KEUR
    return piv.reset_index()


def main() -> None:
    apply_style()
    df = _load()

    if df.empty:
        print("[fig_synth_gap_decomp] No complete L1cp/L1/L2/L3 data yet - skipping")
        return

    fig, axes = plt.subplots(
        1, 2, figsize=(7.0, 3.25),
        gridspec_kw={"width_ratios": [1.0, 1.18]},
    )

    ax = axes[0]
    pos = df["delta_combined"] >= 0
    ax.scatter(
        df.loc[pos, "delta_topology"], df.loc[pos, "delta_heatloss"],
        s=22, color=DIRECTION_COLORS["positive"], alpha=0.68,
        edgecolors="white", lw=0.3, zorder=3,
        label="net positive",
    )
    ax.scatter(
        df.loc[~pos, "delta_topology"], df.loc[~pos, "delta_heatloss"],
        s=22, color=DIRECTION_COLORS["negative"], alpha=0.68,
        edgecolors="white", lw=0.3, zorder=3,
        label="net negative",
    )

    lim = max(abs(df["delta_topology"].min()), abs(df["delta_heatloss"].max())) * 1.05
    diag_x = np.linspace(-lim, 0, 100)
    ax.plot(diag_x, -diag_x, color="#777777", lw=0.8, ls="--", zorder=1, label="net gap = 0")
    ax.axhline(0, color="black", lw=0.55, ls=":")
    ax.axvline(0, color="black", lw=0.55, ls=":")
    ax.set_xlabel("Topology routing component [kEUR/yr]")
    ax.set_ylabel("Heat-loss component [kEUR/yr]")
    ax.set_title("(a) Component interaction", loc="left")
    ax.legend(
        loc="upper left", frameon=True, framealpha=0.9,
        borderpad=0.35, labelspacing=0.25, handlelength=1.1,
    )
    polish_axes(ax, grid_axis="both")

    ax2 = axes[1]
    df_s = df.sort_values("delta_combined")
    y = np.arange(len(df_s))

    topo_pos = df_s["delta_topology"].clip(lower=0)
    topo_neg = df_s["delta_topology"].clip(upper=0)
    loss_pos = df_s["delta_heatloss"].clip(lower=0)
    loss_neg = df_s["delta_heatloss"].clip(upper=0)
    pres_pos = df_s["delta_pressure"].clip(lower=0)
    pres_neg = df_s["delta_pressure"].clip(upper=0)

    left_after_topo = df_s["delta_topology"].values
    left_after_loss = (df_s["delta_topology"] + df_s["delta_heatloss"]).values

    ax2.barh(y, topo_neg, color=C_TOPO, alpha=0.82, height=0.72, label="Topology")
    ax2.barh(y, topo_pos, color=C_TOPO, alpha=0.38, height=0.72)
    ax2.barh(y, loss_pos, left=left_after_topo, color=C_LOSS, alpha=0.82, height=0.72, label="Heat loss")
    ax2.barh(y, loss_neg, left=left_after_topo, color=C_LOSS, alpha=0.38, height=0.72)
    ax2.barh(y, pres_pos, left=left_after_loss, color=C_PRESS, alpha=0.90, height=0.72, label="Pressure")
    ax2.barh(y, pres_neg, left=left_after_loss, color=C_PRESS, alpha=0.50, height=0.72)
    ax2.scatter(df_s["delta_combined"], y, color="black", s=8, zorder=5, label="Net")

    ax2.axvline(0, color="black", lw=0.75)
    ax2.set_xlabel("Cost difference vs L1 copperplate [kEUR/yr]")
    ax2.set_yticks([])
    ax2.set_title(f"(b) Per-config decomposition (n={len(df_s)})", loc="left")
    ax2.legend(
        loc="lower right", frameon=True, framealpha=0.9, ncol=2,
        borderpad=0.35, labelspacing=0.25, columnspacing=0.8,
        handlelength=1.1, handletextpad=0.35,
    )
    polish_axes(ax2, grid_axis="x")

    fig.tight_layout(pad=0.55, w_pad=1.0)
    save_fig(fig, "fig_synth_gap_decomp")


if __name__ == "__main__":
    main()
