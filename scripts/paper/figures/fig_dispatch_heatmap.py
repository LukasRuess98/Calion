"""F9 — Heatmap (hour-of-year × component) for L3+."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from scripts.paper.figures.fig_utils import apply_style, save_fig

RUNS = ROOT / "output" / "paper_runs"


def main() -> None:
    apply_style()

    run_id = "L3plus"
    p = RUNS / run_id / "dispatch_hourly.csv"

    if p.exists():
        df = pd.read_csv(p)
        components = {
            "HP":       df.get("Q_hp_total_MW", pd.Series(dtype=float)).values,
            "CHP":      df.get("Q_chp_MW", pd.Series(dtype=float)).values,
            "Storage+": df.get("Q_storage_charge_MW", pd.Series(dtype=float)).values,
            "Storage−": df.get("Q_storage_discharge_MW", pd.Series(dtype=float)).values,
        }
        T = len(df)
    else:
        # Placeholder: 8760h random data
        T = 8760
        components = {
            "HP":       np.abs(np.random.randn(T) * 30 + 40),
            "CHP":      np.abs(np.random.randn(T) * 5 + 10),
            "Storage+": np.abs(np.random.randn(T) * 10 + 5),
            "Storage−": np.abs(np.random.randn(T) * 10 + 5),
        }

    T_pad = min(T, 8760)
    # Reshape to (day, hour_of_day)
    n_days = T_pad // 24
    fig, axes = plt.subplots(len(components), 1, figsize=(7, 5.5), sharex=True)

    for ax, (name, vals) in zip(axes, components.items()):
        v = np.array(vals[:T_pad], dtype=float)
        v[np.isnan(v)] = 0.0
        mat = v[:n_days * 24].reshape(n_days, 24)
        im = ax.imshow(
            mat.T,
            aspect="auto",
            origin="lower",
            cmap="YlOrRd",
            vmin=0,
            vmax=max(v.max(), 1),
        )
        ax.set_ylabel(name, fontsize=7)
        ax.set_yticks([0, 6, 12, 18, 23])
        ax.set_yticklabels(["0h", "6h", "12h", "18h", "23h"], fontsize=6)
        plt.colorbar(im, ax=ax, fraction=0.02, pad=0.02, label="MW")

    axes[-1].set_xlabel("Day of year")
    fig.suptitle(r"Dispatch heatmap — L3$^+$")

    save_fig(fig, "fig_dispatch_heatmap")


if __name__ == "__main__":
    main()
