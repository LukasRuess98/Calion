"""F9 - Dispatch heatmap for L3+."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.paper.figures.fig_utils import apply_style, polish_axes, save_fig

RUNS = ROOT / "output" / "paper_runs"

COMPONENTS = {
    "HP": "Q_hp_total_MW",
    "CHP": "Q_chp_MW",
    "Storage charge": "Q_storage_charge_MW",
    "Storage discharge": "Q_storage_discharge_MW",
}


def main() -> None:
    apply_style()

    path = RUNS / "L3plus" / "dispatch_hourly.csv"
    if not path.exists():
        print(f"[fig_dispatch_heatmap] Missing dispatch data: {path} - skipping")
        return

    df = pd.read_csv(path)
    missing = [col for col in COMPONENTS.values() if col not in df.columns]
    if missing:
        print(f"[fig_dispatch_heatmap] Missing dispatch columns: {', '.join(missing)} - skipping")
        return

    T = len(df)
    T_pad = min(T, 8760)
    n_days = T_pad // 24
    if n_days == 0:
        print("[fig_dispatch_heatmap] Dispatch data shorter than 24 h - skipping")
        return

    fig, axes = plt.subplots(len(COMPONENTS), 1, figsize=(6.3, 4.1), sharex=True)
    cmap = "YlOrRd"

    for ax, (name, col) in zip(axes, COMPONENTS.items()):
        v = df[col].to_numpy(dtype=float)[:T_pad]
        v[np.isnan(v)] = 0.0
        mat = v[:n_days * 24].reshape(n_days, 24)
        im = ax.imshow(
            mat.T,
            aspect="auto",
            origin="lower",
            cmap=cmap,
            vmin=0,
            vmax=max(float(v.max()), 1.0),
            interpolation="nearest",
            rasterized=True,
        )
        ax.set_ylabel(name)
        ax.set_yticks([0, 6, 12, 18, 23])
        ax.set_yticklabels(["0", "6", "12", "18", "23"])
        ax.tick_params(axis="y", labelsize=6.4)
        cbar = fig.colorbar(im, ax=ax, fraction=0.022, pad=0.012)
        cbar.ax.tick_params(labelsize=6.2, length=2, width=0.5)
        cbar.set_label("MW", fontsize=6.4, labelpad=2)
        polish_axes(ax, grid_axis="none")

    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"].iloc[:n_days * 24], errors="coerce")
        if ts.notna().all():
            day_index = ts.iloc[::24].reset_index(drop=True)
            month_starts = day_index[day_index.dt.day.eq(1)]
            ticks = month_starts.index.to_numpy()
            labels = month_starts.dt.strftime("%b").tolist()
            axes[-1].set_xticks(ticks)
            axes[-1].set_xticklabels(labels)
        else:
            axes[-1].set_xticks(np.linspace(0, n_days - 1, 5))
    else:
        axes[-1].set_xticks(np.linspace(0, n_days - 1, 5))
    axes[-1].set_xlabel("Day of year")

    fig.tight_layout(pad=0.45, h_pad=0.35)
    save_fig(fig, "fig_dispatch_heatmap")


if __name__ == "__main__":
    main()
