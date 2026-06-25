"""
fig_validation_timeseries_all.py
=================================
Generates one Applied Energy–style time-series validation figure per available
winter month (Oct/Nov/Dec/Jan/Feb) found in the historical dataset.

Design:
  - Upper panel: T_sup measured (solid blue) with ±1.5 °C gate band (light fill),
    T_sup simulated BCM (solid red) overlaid.  Cleaner than fill-between two lines.
  - Lower panel: outdoor temperature (normal orientation, 0 °C reference line).
  - No in-figure title (caption goes in LaTeX).
  - Applied Energy double-column width (170 mm), Times New Roman, 8 pt.

Output: F_validation_timeseries_YYYY_MM.{png,pdf}
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
from scripts.paper.mpl_export import AE_DOUBLE_COLUMN_IN, AE_RCPARAMS

WINTER_MONTHS = {10, 11, 12, 1, 2}
TRUNK_MULT    = 1.330
GATE_C        = 1.5
MIN_HOURS     = 24

MONTH_NAMES = {
    1: "January", 2: "February", 10: "October",
    11: "November", 12: "December",
}

# Applied Energy palette — high contrast, colour-blind safe
C_MEAS  = "#003f88"   # dark blue  — measured
C_SIM   = "#c0392b"   # dark red   — simulated
C_BAND  = "#aec6e8"   # light blue — ±gate fill around measured
C_AMB   = "#4d4d4d"   # dark grey  — outdoor temp


# ─────────────────────────────────────────────────────────────────────────────

def _load_all() -> pd.DataFrame | None:
    try:
        from tools.validation_runner import DATA_PATH, PIPE_CATALOG, TRUNK_PIPES, load_historical
        from tools.validation_spatial import reconstruct_node_temperatures
    except ImportError as exc:
        print(f"[fig_validation_timeseries_all] Import failed: {exc}")
        return None

    if not DATA_PATH.exists():
        print(f"[fig_validation_timeseries_all] Data not found: {DATA_PATH}")
        return None

    hist = load_historical(DATA_PATH)

    for col in ("V_1_flow_temp", "V_27_flow_temp"):
        if col not in hist.columns:
            print(f"[fig_validation_timeseries_all] Missing column: {col}")
            return None

    bc_temp = hist["V_1_flow_temp"].astype(float).fillna(
        float(hist["V_1_flow_temp"].median())
    )

    u_cal = {pid: 1.0 for pid in PIPE_CATALOG}
    for pid in TRUNK_PIPES:
        u_cal[pid] = TRUNK_MULT

    node_temps = reconstruct_node_temperatures(hist, bc_temp, u_cal)
    t_sim = node_temps.get("j_15")
    if t_sim is None:
        print("[fig_validation_timeseries_all] BCM reconstruction failed")
        return None

    df = pd.DataFrame({
        "t_meas": hist["V_27_flow_temp"].astype(float),
        "t_sim":  t_sim,
        "t_amb":  (
            hist["outdoor_temp_C"].astype(float)
            if "outdoor_temp_C" in hist.columns
            else pd.Series(np.nan, index=hist.index)
        ),
    })
    return df


# ─────────────────────────────────────────────────────────────────────────────

def _plot_window(df_full: pd.DataFrame, year: int, month: int) -> bool:
    sl = df_full[
        (df_full.index.year == year) &
        (df_full.index.month == month)
    ].dropna(subset=["t_meas", "t_sim"])
    sl = sl[(sl["t_meas"] >= 70.0) & (sl["t_sim"] >= 70.0)]

    if len(sl) < MIN_HOURS:
        print(f"  [{year}-{month:02d}] only {len(sl)} h after filter — skipping")
        return False

    err  = sl["t_sim"] - sl["t_meas"]
    mae  = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    bias = float(np.mean(err))
    pct  = float(100.0 * np.mean(np.abs(err) <= GATE_C))
    n    = len(sl)

    has_amb = sl["t_amb"].notna().any()

    # ── figure geometry (Applied Energy double column) ────────────────────────
    fig_w = AE_DOUBLE_COLUMN_IN          # 170 mm ≈ 6.69 in
    fig_h = 3.6 if has_amb else 2.4      # in

    plt.rcParams.update(AE_RCPARAMS)     # enforce Times New Roman, 8 pt

    fig, axes = plt.subplots(
        2 if has_amb else 1, 1,
        figsize=(fig_w, fig_h),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08} if has_amb else {},
        constrained_layout=False,
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.97, bottom=0.12,
                        hspace=0.08)

    if not has_amb:
        axes = [axes]

    ax_t = axes[0]
    ax_a = axes[1] if has_amb else None

    # ── Panel (a): supply temperature ─────────────────────────────────────────
    # ±gate band around the measured signal
    ax_t.fill_between(
        sl.index,
        sl["t_meas"] - GATE_C,
        sl["t_meas"] + GATE_C,
        color=C_BAND, alpha=0.45, linewidth=0,
        label=rf"$\pm{GATE_C:.1f}$ °C gate",
        zorder=1,
    )
    # measured — solid, slightly thicker, drawn second so it sits above band
    ax_t.plot(
        sl.index, sl["t_meas"],
        color=C_MEAS, lw=0.85,
        label=r"Measured $T_\mathrm{sup}$ (j$_{15}$)",
        zorder=3,
    )
    # simulated — solid, thinner, contrasting red, drawn on top
    ax_t.plot(
        sl.index, sl["t_sim"],
        color=C_SIM, lw=0.7,
        label=r"BCM simulated $T_\mathrm{sup}$ (j$_{15}$)",
        zorder=4,
    )

    # y-axis
    t_lo = min(sl["t_meas"].min(), sl["t_sim"].min()) - 1.5
    t_hi = max(sl["t_meas"].max(), sl["t_sim"].max()) + 1.5
    ax_t.set_ylim(t_lo, t_hi)
    ax_t.set_ylabel(r"$T_\mathrm{sup}$ [°C]")
    ax_t.yaxis.set_major_locator(plt.MultipleLocator(2))
    ax_t.yaxis.set_minor_locator(plt.MultipleLocator(1))

    # legend — compact, two columns
    leg = ax_t.legend(
        loc="upper right",
        ncol=1,
        frameon=True,
        framealpha=0.92,
        edgecolor="#cccccc",
        borderpad=0.4,
        handlelength=1.5,
        handletextpad=0.4,
        labelspacing=0.25,
        fontsize=7,
    )
    leg.get_frame().set_linewidth(0.5)

    # KPI annotation — two-column table layout, bottom-left
    kpi_lines = [
        rf"MAE  = {mae:.2f} °C",
        rf"RMSE = {rmse:.2f} °C",
        rf"Bias = {bias:+.2f} °C",
        rf"Gate = {pct:.0f} %  ($n$ = {n} h)",
    ]
    ax_t.text(
        0.01, 0.03,
        "\n".join(kpi_lines),
        transform=ax_t.transAxes,
        va="bottom", ha="left",
        fontsize=6.5,
        family="monospace",
        bbox=dict(
            boxstyle="square,pad=0.3",
            fc="white", ec="#bbbbbb",
            alpha=0.93, lw=0.5,
        ),
        zorder=5,
    )

    # panel label (a)
    ax_t.text(
        0.005, 0.97, "(a)",
        transform=ax_t.transAxes,
        va="top", ha="left", fontsize=7, fontweight="bold",
    )

    # ── Panel (b): outdoor temperature ────────────────────────────────────────
    if ax_a is not None:
        amb = sl["t_amb"].dropna()
        ax_a.plot(amb.index, amb, color=C_AMB, lw=0.75, zorder=3)
        ax_a.fill_between(
            amb.index, amb, 0,
            where=(amb < 0),
            color="#6baed6", alpha=0.25, linewidth=0,
            label="Sub-zero",
        )
        ax_a.axhline(0, color="#888888", lw=0.5, ls="--", zorder=2)
        ax_a.set_ylabel(r"$T_\mathrm{amb}$ [°C]")
        ax_a.yaxis.set_major_locator(plt.MultipleLocator(5))

        # panel label (b)
        ax_a.text(
            0.005, 0.93, "(b)",
            transform=ax_a.transAxes,
            va="top", ha="left", fontsize=7, fontweight="bold",
        )

    # ── x-axis (shared) ───────────────────────────────────────────────────────
    bottom_ax = axes[-1]
    n_days = (sl.index[-1] - sl.index[0]).days + 1
    if n_days <= 10:
        bottom_ax.xaxis.set_major_locator(mdates.DayLocator())
        bottom_ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    elif n_days <= 31:
        bottom_ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        bottom_ax.xaxis.set_minor_locator(mdates.DayLocator())
        bottom_ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    else:
        bottom_ax.xaxis.set_major_locator(mdates.MonthLocator())
        bottom_ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    plt.setp(bottom_ax.xaxis.get_majorticklabels(), rotation=0, ha="center")

    # remove top x-tick labels on upper panel
    if has_amb:
        plt.setp(ax_t.get_xticklabels(), visible=False)
        ax_t.tick_params(axis="x", which="both", bottom=True, top=False)

    stem = f"F_validation_timeseries_{year}_{month:02d}"
    save_fig(fig, stem)
    return True


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    df = _load_all()
    if df is None:
        print("[fig_validation_timeseries_all] Aborting — data unavailable")
        return

    groups = [
        (y, m)
        for (y, m), cnt in df.groupby([df.index.year, df.index.month]).size().items()
        if m in WINTER_MONTHS and cnt >= MIN_HOURS
    ]
    groups.sort()

    print(f"[fig_validation_timeseries_all] Found {len(groups)} winter windows: "
          + ", ".join(f"{y}-{m:02d}" for y, m in groups))

    success = 0
    for year, month in groups:
        print(f"  plotting {year}-{month:02d} ...")
        if _plot_window(df, year, month):
            success += 1

    print(f"[fig_validation_timeseries_all] Done — {success}/{len(groups)} figures saved.")


if __name__ == "__main__":
    main()
