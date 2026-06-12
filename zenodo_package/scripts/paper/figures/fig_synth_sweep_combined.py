"""Combined synthetic sweep figure for paper Figure F10.

Panels:
(a) Distribution of L1cp -> L3 cost gap [%]
(b) Additive decomposition per config [kEUR]
(c) Gap scaling versus total pipe length [km]

By default this script uses the core sweep CSV and merges the large-scale
extension CSV when present.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.paper.figures.fig_utils import apply_style, polish_axes, save_fig

CORE_CSV = ROOT / "output" / "paper_runs" / "synth_sweep_results.csv"
LARGE_CSV = ROOT / "output" / "paper_runs" / "synth_large_scale_results.csv"

C_TOPO = "#2C7BB6"
C_LOSS = "#D7191C"
C_PRES = "#F1A340"
C_NET = "black"
C_POINT = "#4D4D4D"


def _jitter(n: int, spread: float) -> np.ndarray:
    if n <= 1 or spread <= 0:
        return np.zeros(n)
    return np.linspace(-spread, spread, n)


def _load_df(core_csv: Path, large_csv: Path | None, include_large: bool) -> pd.DataFrame:
    if not core_csv.exists():
        raise FileNotFoundError(f"Missing core CSV: {core_csv}")

    parts = [pd.read_csv(core_csv)]

    if include_large and large_csv is not None and large_csv.exists():
        parts.append(pd.read_csv(large_csv))

    df = pd.concat(parts, ignore_index=True)

    # Keep one row per config_id (large extension uses new IDs, so this is safe).
    df = df.drop_duplicates(subset=["config_id"], keep="last").copy()

    # Derived metrics.
    df["gap_pct"] = 100.0 * (df["cost_L3"] - df["cost_L1cp"]) / df["cost_L3"]
    df["topology_keur"] = df["decomp_topology_eur"] / 1000.0
    df["heatloss_keur"] = df["decomp_heatloss_eur"] / 1000.0
    df["pressure_keur"] = df["decomp_pressure_eur"] / 1000.0
    df["net_keur"] = df["decomp_combined_eur"] / 1000.0

    return df


def _panel_a(ax: plt.Axes, df: pd.DataFrame) -> None:
    vals = df["gap_pct"].to_numpy(dtype=float)

    ax.boxplot(
        vals,
        positions=[0],
        widths=0.35,
        patch_artist=True,
        medianprops=dict(color="black", lw=1.8),
        boxprops=dict(facecolor="#AEC6E8", alpha=0.65),
        whiskerprops=dict(lw=1.0),
        capprops=dict(lw=1.0),
        flierprops=dict(marker="", lw=0),
    )

    jx = _jitter(len(vals), 0.11)
    ax.scatter(
        jx,
        vals,
        s=16,
        color=C_POINT,
        alpha=0.65,
        edgecolors="white",
        lw=0.3,
        zorder=3,
    )

    med = float(np.median(vals))
    lo = float(np.min(vals))
    hi = float(np.max(vals))
    n_pos = int((vals > 0.0).sum())

    ax.text(
        0.04,
        0.97,
        f"median: {med:.1f}%\\nrange: {lo:.1f}% - {hi:.1f}%\\n{n_pos}/{len(vals)} positive",
        transform=ax.transAxes,
        fontsize=6.8,
        va="top",
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#B7B7B7", alpha=0.9, lw=0.5),
    )

    ymax = max(float(np.max(vals)) * 1.12, 10.0)
    ax.set_ylim(0.0, ymax)
    ax.set_xticks([0])
    ax.set_xticklabels(["L1cp -> L3"])
    ax.set_ylabel("Cost gap [%]")
    ax.set_title("(a) Gap distribution", loc="left")
    polish_axes(ax, grid_axis="y")


def _panel_b(ax: plt.Axes, df: pd.DataFrame) -> None:
    ds = df.sort_values("net_keur").reset_index(drop=True)
    y = np.arange(len(ds))

    topo_pos = ds["topology_keur"].clip(lower=0)
    topo_neg = ds["topology_keur"].clip(upper=0)
    loss_pos = ds["heatloss_keur"].clip(lower=0)
    loss_neg = ds["heatloss_keur"].clip(upper=0)
    pres_pos = ds["pressure_keur"].clip(lower=0)
    pres_neg = ds["pressure_keur"].clip(upper=0)

    left_topo = ds["topology_keur"].to_numpy()
    left_loss = (ds["topology_keur"] + ds["heatloss_keur"]).to_numpy()

    ax.barh(y, topo_neg, color=C_TOPO, alpha=0.82, height=0.72, label="Topology")
    ax.barh(y, topo_pos, color=C_TOPO, alpha=0.38, height=0.72)
    ax.barh(y, loss_pos, left=left_topo, color=C_LOSS, alpha=0.82, height=0.72, label="Heat loss")
    ax.barh(y, loss_neg, left=left_topo, color=C_LOSS, alpha=0.38, height=0.72)
    ax.barh(y, pres_pos, left=left_loss, color=C_PRES, alpha=0.88, height=0.72, label="Pressure")
    ax.barh(y, pres_neg, left=left_loss, color=C_PRES, alpha=0.48, height=0.72)

    ax.scatter(ds["net_keur"], y, color=C_NET, s=9, zorder=5, label="Net")

    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Cost difference [kEUR/yr]")
    ax.set_yticks([])
    ax.set_title(f"(b) Additive decomposition (n={len(ds)}, sorted)", loc="left")
    ax.legend(loc="lower right", frameon=True, framealpha=0.9,
              ncol=2, columnspacing=0.8, handlelength=1.1,
              borderpad=0.35, handletextpad=0.35)
    polish_axes(ax, grid_axis="x")


def _panel_c(ax: plt.Axes, df: pd.DataFrame) -> None:
    x = df["pipe_length_km"].to_numpy(dtype=float)
    y = df["gap_pct"].to_numpy(dtype=float)

    spread = max(0.15, 0.015 * float(np.max(x)))
    jx = _jitter(len(x), spread)

    ax.scatter(
        x + jx,
        y,
        s=18,
        color=C_POINT,
        alpha=0.68,
        edgecolors="white",
        lw=0.3,
        zorder=3,
    )

    z = np.polyfit(x, y, 1)
    xfit = np.linspace(float(np.min(x)) - 0.5, float(np.max(x)) + 0.5, 200)
    ax.plot(xfit, np.polyval(z, xfit), color="#707070", lw=0.9, ls="--", zorder=2)

    ymax = max(float(np.max(y)) * 1.12, 10.0)
    ax.set_ylim(0.0, ymax)

    # Auto-scale to full available length range (up to 50 km in extension).
    xmin = max(0.0, float(np.min(x)) - 0.8)
    xmax = float(np.max(x)) + 1.2
    ax.set_xlim(xmin, xmax)

    xt = sorted(df["pipe_length_km"].unique().tolist())
    ax.set_xticks(xt)

    ax.set_xlabel("Total pipe length [km]")
    ax.set_ylabel("L1cp -> L3 cost gap [%]")
    ax.set_title("(c) Gap scaling with pipe length", loc="left")
    polish_axes(ax, grid_axis="both")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create F10 combined synthetic sweep figure")
    parser.add_argument("--core", type=Path, default=CORE_CSV)
    parser.add_argument("--large", type=Path, default=LARGE_CSV)
    parser.add_argument("--no-large", action="store_true", help="Use only core CSV")
    args = parser.parse_args()

    apply_style()
    df = _load_df(args.core, args.large, include_large=not args.no_large)

    fig, axes = plt.subplots(
        1, 3,
        figsize=(7.6, 3.1),
        gridspec_kw={"width_ratios": [0.72, 1.58, 0.95]},
    )

    _panel_a(axes[0], df)
    _panel_b(axes[1], df)
    _panel_c(axes[2], df)

    fig.tight_layout(pad=0.55, w_pad=1.0)
    save_fig(fig, "F10_synth_sweep_combined")


if __name__ == "__main__":
    main()
