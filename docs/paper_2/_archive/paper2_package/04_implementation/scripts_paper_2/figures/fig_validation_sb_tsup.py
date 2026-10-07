"""fig_validation_sb_tsup.py
===========================
Illustrates the L3-MILP constant-supply-temperature limitation for the
Stadtbach BC-SB scenario.

Three panels:
  (a) Histogram of measured T_VL across all 7 stations (2025, hourly)
      with a vertical line at the constant model T_supply.
  (b) Time-series (January 2025) for Klinikum: measured T_VL (blue) vs.
      constant model T_supply (dashed red), outdoor temperature below.
  (c) Scatter (all 7 stations combined): measured T_VL vs. constant model
      T_supply = constant horizontal band, annotated with MAE.

Output: output/paper2_runs/figures/fig_validation_sb_tsup.{pdf,png}
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from scripts.paper.mpl_export import AE_DOUBLE_COLUMN_IN, AE_RCPARAMS, save_figure_bundle
from tools.validation_stadtbach import (
    IDX_2025,
    MEASURED_CONSUMERS,
    STATION_TO_NODE,
    load_measured_tsup,
    load_simulation_tsup_constant,
    RUN_DIR,
)

# Load outdoor temperature from preprocessed Excel
DATA_COMBINED = ROOT / "data" / "Stadtbach" / "stadtbach_acron_combined.xlsx"

OUT_DIR = ROOT / "output" / "paper2_runs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

C_MEAS    = "#003f88"
C_SIM     = "#c0392b"
C_AMB     = "#4d4d4d"
C_HIST    = "#3a7ebf"
C_SCATTER = "#1a6faf"
C_DIAG    = "#333333"


def _load_outdoor() -> pd.Series | None:
    if not DATA_COMBINED.exists():
        return None
    try:
        df = pd.read_excel(DATA_COMBINED, engine="openpyxl", usecols=["Datum", "outdoor_temp_C"])
        df.index = pd.to_datetime(df["Datum"])
        return df["outdoor_temp_C"].reindex(IDX_2025).ffill().bfill()
    except Exception:
        return None


def main() -> None:
    plt.rcParams.update(AE_RCPARAMS)

    # Load constant sim T_supply per node
    sim_tsup = load_simulation_tsup_constant(RUN_DIR)

    # Load measured T_VL for all 7 stations
    all_tvl: list[pd.Series] = []
    station_tvl: dict[str, pd.Series] = {}
    for station in STATION_TO_NODE:
        tvl = load_measured_tsup(station)
        if tvl is not None and len(tvl) == 8760:
            s = tvl.dropna()
            s = s[s > 50.0]
            all_tvl.append(s)
            station_tvl[station] = tvl

    if not all_tvl:
        print("[fig_validation_sb_tsup] No T_VL data found — aborting")
        return

    all_tvl_concat = pd.concat(all_tvl)

    # Use Klinikum node as the representative constant T
    sim_const = sim_tsup.get("j_klinikum", 94.762329)

    outdoor = _load_outdoor()

    # --- Figure layout ---
    fig_w = AE_DOUBLE_COLUMN_IN
    fig_h = 4.2
    has_amb = outdoor is not None
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = fig.add_gridspec(
        2 if has_amb else 1, 3,
        height_ratios=[3, 1] if has_amb else [1],
        hspace=0.10, wspace=0.38,
        left=0.07, right=0.97, top=0.94, bottom=0.11,
    )

    ax_hist  = fig.add_subplot(gs[0, 0])
    ax_ts    = fig.add_subplot(gs[0, 1])
    ax_scat  = fig.add_subplot(gs[0, 2])
    if has_amb:
        ax_amb = fig.add_subplot(gs[1, 1], sharex=ax_ts)

    # ── Panel (a): Histogram ─────────────────────────────────────────────────
    ax_hist.hist(all_tvl_concat, bins=40, color=C_HIST, alpha=0.8, edgecolor="none",
                 density=True, orientation="vertical")
    ax_hist.axvline(sim_const, color=C_SIM, lw=1.2, ls="--",
                    label=f"Model BC = {sim_const:.1f}°C")
    ax_hist.set_xlabel(r"Measured $T_\mathrm{sup}$ [°C]", fontsize=7)
    ax_hist.set_ylabel("Density", fontsize=7)
    ax_hist.legend(fontsize=6, frameon=True, framealpha=0.85, edgecolor="#cccccc",
                   borderpad=0.3, handlelength=1.2)
    ax_hist.text(0.04, 0.97, "(a)", transform=ax_hist.transAxes,
                 va="top", ha="left", fontsize=7, fontweight="bold")

    mae_all = float(np.mean(np.abs(all_tvl_concat - sim_const)))
    ax_hist.text(
        0.97, 0.97,
        f"MAE = {mae_all:.1f}°C\n(all 7 stations)",
        transform=ax_hist.transAxes,
        va="top", ha="right", fontsize=6,
        family="monospace",
        bbox=dict(boxstyle="square,pad=0.25", fc="white", ec="#cccccc", alpha=0.90, lw=0.4),
    )

    # ── Panel (b): January time-series for Klinikum ─────────────────────────
    kl_tvl = station_tvl.get("Klinikum")
    if kl_tvl is not None:
        jan = kl_tvl[(kl_tvl.index.year == 2025) & (kl_tvl.index.month == 1)]
        jan = jan[jan > 50.0]
        ax_ts.plot(jan.index, jan, color=C_MEAS, lw=0.7,
                   label=r"Meas. $T_\mathrm{sup}$ (Klinikum)")
        ax_ts.axhline(sim_const, color=C_SIM, lw=0.8, ls="--",
                      label=f"Model = {sim_const:.1f}°C")
        ax_ts.set_ylabel(r"$T_\mathrm{sup}$ [°C]", fontsize=7)
        ax_ts.legend(fontsize=6, frameon=True, framealpha=0.85, edgecolor="#cccccc",
                     ncol=1, borderpad=0.3, handlelength=1.0, loc="upper right")
        ax_ts.text(0.04, 0.97, "(b)", transform=ax_ts.transAxes,
                   va="top", ha="left", fontsize=7, fontweight="bold")

        if has_amb:
            amb_jan = outdoor[(outdoor.index.year == 2025) & (outdoor.index.month == 1)]
            ax_amb.plot(amb_jan.index, amb_jan, color=C_AMB, lw=0.6)
            ax_amb.axhline(0, color="#aaaaaa", lw=0.4, ls="--")
            ax_amb.set_ylabel(r"$T_\mathrm{amb}$ [°C]", fontsize=7)
            ax_amb.text(0.04, 0.93, "(d)", transform=ax_amb.transAxes,
                        va="top", ha="left", fontsize=7, fontweight="bold")
            ax_amb.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
            ax_amb.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
            plt.setp(ax_amb.xaxis.get_majorticklabels(), rotation=0, ha="center")
            plt.setp(ax_ts.get_xticklabels(), visible=False)
        else:
            ax_ts.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
            ax_ts.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
            plt.setp(ax_ts.xaxis.get_majorticklabels(), rotation=0, ha="center")

    # ── Panel (c): Scatter (all stations combined) ───────────────────────────
    for station, tvl in station_tvl.items():
        s_clean = tvl[tvl > 50.0]
        if len(s_clean) > 10:
            ax_scat.scatter(
                s_clean.values,
                np.full(len(s_clean), sim_const),
                s=0.5, alpha=0.15, color=C_SCATTER if station == "Klinikum" else "#888888",
                linewidths=0, rasterized=True,
            )

    vmin = float(all_tvl_concat.min()) - 2
    vmax = float(all_tvl_concat.max()) + 2
    # Reference diagonal (ideal)
    ax_scat.plot([vmin, vmax], [vmin, vmax], color=C_DIAG, lw=0.6, ls="--", zorder=4)
    ax_scat.set_xlim(vmin, vmax)
    ax_scat.set_ylim(vmin, vmax)
    ax_scat.set_xlabel(r"Measured $T_\mathrm{sup}$ [°C]", fontsize=7)
    ax_scat.set_ylabel(r"Model $T_\mathrm{sup}$ [°C]", fontsize=7)
    ax_scat.text(0.04, 0.97, "(c)", transform=ax_scat.transAxes,
                 va="top", ha="left", fontsize=7, fontweight="bold")
    ax_scat.text(
        0.97, 0.05,
        f"MAE = {mae_all:.1f}°C\nn = {len(all_tvl_concat)}\nL3-MILP: constant BC",
        transform=ax_scat.transAxes,
        va="bottom", ha="right", fontsize=6,
        family="monospace",
        bbox=dict(boxstyle="square,pad=0.25", fc="white", ec="#cccccc", alpha=0.90, lw=0.4),
    )

    # ---
    saved = save_figure_bundle(fig, OUT_DIR / "fig_validation_sb_tsup", formats=("png", "pdf"))
    for p in saved:
        print(f"Saved: {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
