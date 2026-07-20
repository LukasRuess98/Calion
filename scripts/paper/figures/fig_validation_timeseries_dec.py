"""
fig_validation_timeseries_dec.py
=================================
Time-series validation for December: measured vs. BCM-simulated T_supply
at the network far-end (j_15, corridor j_1->j_15, 2125 m), together with
outdoor temperature on a secondary panel.

Reuses the same BCM reconstruction logic as fig_validation_scatter_tsup.py.
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

from scripts.paper.figures.fig_utils import apply_style, save_fig

TRUNK_MULT = 1.330
GATE_C     = 1.5
TARGET_MONTH = 12
MONTH_NAME   = "December"


def _load_data() -> dict | None:
    try:
        from tools.validation_runner import DATA_PATH, PIPE_CATALOG, TRUNK_PIPES, load_historical
        from tools.validation_spatial import reconstruct_node_temperatures
    except ImportError as exc:
        print(f"[fig_validation_timeseries_dec] Import failed: {exc}")
        return None

    if not DATA_PATH.exists():
        print(f"[fig_validation_timeseries_dec] Data file not found: {DATA_PATH}")
        return None

    hist = load_historical(DATA_PATH)

    for col in ("V_1_flow_temp", "V_27_flow_temp"):
        if col not in hist.columns:
            print(f"[fig_validation_timeseries_dec] Missing column: {col}")
            return None

    bc_temp = hist["V_1_flow_temp"].astype(float).fillna(float(hist["V_1_flow_temp"].median()))

    u_cal = {pid: 1.0 for pid in PIPE_CATALOG}
    for pid in TRUNK_PIPES:
        u_cal[pid] = TRUNK_MULT

    node_temps = reconstruct_node_temperatures(hist, bc_temp, u_cal)
    t_sim = node_temps.get("j_15")
    if t_sim is None:
        print("[fig_validation_timeseries_dec] BCM reconstruction failed")
        return None

    df = pd.DataFrame({
        "t_meas": hist["V_27_flow_temp"].astype(float),
        "t_sim":  t_sim,
        "t_amb":  hist["outdoor_temp_C"].astype(float) if "outdoor_temp_C" in hist.columns else np.nan,
    }).dropna(subset=["t_meas", "t_sim"])

    df = df[df.index.month == TARGET_MONTH]
    df = df[(df["t_meas"] >= 70.0) & (df["t_sim"] >= 70.0)]

    if len(df) < 24:
        print(f"[fig_validation_timeseries_dec] Too few December points: {len(df)}")
        return None

    err  = df["t_sim"] - df["t_meas"]
    mae  = float(np.mean(np.abs(err)))
    bias = float(np.mean(err))
    pct  = float(100.0 * np.mean(np.abs(err) <= GATE_C))

    return dict(df=df, mae=mae, bias=bias, pct=pct)


def _plot(data: dict) -> None:
    apply_style()
    df   = data["df"]
    mae  = data["mae"]
    bias = data["bias"]
    pct  = data["pct"]

    has_amb = df["t_amb"].notna().any()
    n_panels = 2 if has_amb else 1
    height   = 4.5 if has_amb else 3.0

    fig, axes = plt.subplots(
        n_panels, 1,
        figsize=(7.0, height),
        sharex=True,
        gridspec_kw={"height_ratios": [2, 1]} if has_amb else {},
        constrained_layout=True,
    )
    if n_panels == 1:
        axes = [axes]

    ax_t = axes[0]
    ax_a = axes[1] if has_amb else None

    # ── Panel 1: T_sup measured + simulated ──────────────────────────────────
    ax_t.plot(
        df.index, df["t_meas"],
        color="#2166AC", lw=1.0, label=r"$T_{\mathrm{sup}}$ measured (j$_{15}$)",
        zorder=3,
    )
    ax_t.plot(
        df.index, df["t_sim"],
        color="#D01C8B", lw=1.0, ls="--",
        label=r"$T_{\mathrm{sup}}$ simulated BCM (j$_{15}$)",
        zorder=3,
    )

    # error band: shade region between measured and simulated
    ax_t.fill_between(
        df.index, df["t_meas"], df["t_sim"],
        alpha=0.18, color="#D01C8B", linewidth=0, label="_nolegend_",
    )

    ax_t.set_ylabel(r"$T_{\mathrm{sup}}$ [°C]")
    ax_t.grid(True, axis="y", alpha=0.25, lw=0.5)
    ax_t.grid(True, axis="x", alpha=0.15, lw=0.5)

    kpi_txt = (
        rf"MAE = {mae:.2f} °C   Bias = {bias:+.2f} °C"
        "\n"
        rf"Within $\pm${GATE_C:.1f} °C gate: {pct:.0f} %   $n$ = {len(df)} h"
    )
    ax_t.text(
        0.01, 0.97, kpi_txt,
        transform=ax_t.transAxes,
        va="top", ha="left", fontsize=7.5,
        bbox=dict(boxstyle="round,pad=0.28", fc="white", ec="#C8C8C8", alpha=0.92, lw=0.6),
    )
    ax_t.legend(fontsize=7.5, loc="upper right", framealpha=0.9,
                handlelength=1.8, labelspacing=0.3)
    ax_t.set_title(
        rf"BCM forward validation — {MONTH_NAME} "
        rf"(j$_1\to$j$_{{15}}$, 2125 m,  $U_{{trunk}}\times{TRUNK_MULT:.3f}$)",
        fontsize=8,
    )

    # ── Panel 2: outdoor temperature ─────────────────────────────────────────
    if ax_a is not None:
        ax_a.plot(
            df.index, df["t_amb"],
            color="#5e5e5e", lw=0.9, label="Outdoor temp.",
        )
        ax_a.fill_between(
            df.index, df["t_amb"], df["t_amb"].min() - 1,
            alpha=0.15, color="#5e5e5e", linewidth=0,
        )
        ax_a.set_ylabel(r"$T_{\mathrm{amb}}$ [°C]")
        ax_a.grid(True, axis="y", alpha=0.25, lw=0.5)
        ax_a.legend(fontsize=7.5, loc="upper right", framealpha=0.9)
        ax_a.invert_yaxis()   # colder at top → visually mirrors heating demand

    # ── x-axis formatting ────────────────────────────────────────────────────
    bottom_ax = axes[-1]
    bottom_ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    bottom_ax.xaxis.set_minor_locator(mdates.DayLocator())
    bottom_ax.xaxis.set_major_formatter(mdates.DateFormatter("%d. %b"))
    plt.setp(bottom_ax.xaxis.get_majorticklabels(), rotation=0, ha="center")

    save_fig(fig, "F_validation_timeseries_dec")


def main() -> None:
    data = _load_data()
    if data is None:
        print("[fig_validation_timeseries_dec] Skipping — data unavailable")
        return
    _plot(data)


if __name__ == "__main__":
    main()
