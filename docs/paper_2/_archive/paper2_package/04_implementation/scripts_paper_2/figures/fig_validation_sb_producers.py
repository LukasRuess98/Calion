"""fig_validation_sb_producers.py
================================
Monthly producer dispatch: measured (ACRON) vs. BC-SB simulation (dispatch_per_asset.csv)
for HKW (gas CHP), BMHKW (biomass CHP), and Heizwerk Süd (gas boiler).

Three-panel bar chart, all 12 months of 2025. The large deviations at individual
producer level illustrate that BC-SB optimises total system cost, not individual
asset dispatch matching — the key modelling limitation narrative.

Output: output/paper2_runs/figures/fig_validation_sb_producers.{pdf,png}
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.paper.mpl_export import AE_DOUBLE_COLUMN_IN, AE_RCPARAMS, save_figure_bundle
from tools.validation_stadtbach import (
    IDX_2025,
    MEASURED_PRODUCERS,
    RUN_DIR,
    load_measured_producer,
    load_measured_hws_q,
)

OUT_DIR = ROOT / "output" / "paper2_runs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PER_ASSET_CSV = RUN_DIR / "dispatch_per_asset.csv"

C_MEAS = "#003f88"
C_SIM  = "#c0392b"
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

PANELS = [
    ("HKW",   "HKW_MW",       "HKW\n(Gas CHP, 75 MW)"),
    ("BMHKW", "BMHKW_MW",     "BMHKW\n(Biomass CHP, 14.5 MW)"),
    ("HWS",   "HWS_BOILER_MW","Heizwerk Süd\n(Gas boiler, 40 MW)"),
]


def _monthly_mwh(s: pd.Series) -> pd.Series:
    """Resample hourly MW to monthly MWh."""
    return s.resample("MS").sum()


def _load_per_asset() -> pd.DataFrame | None:
    if not PER_ASSET_CSV.exists():
        print(f"[fig_validation_sb_producers] {PER_ASSET_CSV} not found")
        return None
    df = pd.read_csv(PER_ASSET_CSV, parse_dates=["timestamp"])
    df = df.set_index("timestamp")
    df.index = IDX_2025
    return df


def _annual_err_pct(meas: pd.Series, sim: pd.Series) -> float:
    m = meas.sum()
    s = sim.sum()
    return 100.0 * (s - m) / m if m > 0 else float("nan")


def main() -> None:
    plt.rcParams.update(AE_RCPARAMS)

    per_asset = _load_per_asset()
    if per_asset is None:
        return

    fig, axes = plt.subplots(1, 3, figsize=(AE_DOUBLE_COLUMN_IN, 2.8),
                              sharey=False)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.18, wspace=0.38)

    x = np.arange(12)
    bw = 0.38

    for ax, (name, asset_col, title) in zip(axes, PANELS):
        # Load measured
        if name == "HWS":
            meas_h = load_measured_hws_q()
        else:
            meas_h = load_measured_producer(name)

        meas_h = meas_h.reindex(IDX_2025).fillna(0.0)
        meas_monthly = _monthly_mwh(meas_h)

        # Load simulated
        if asset_col not in per_asset.columns:
            print(f"[fig_validation_sb_producers] column {asset_col} missing")
            ax.set_title(title, fontsize=7)
            ax.text(0.5, 0.5, "data missing", transform=ax.transAxes,
                    ha="center", va="center", fontsize=7, color="grey")
            continue

        sim_h = per_asset[asset_col].reindex(IDX_2025).fillna(0.0)
        sim_monthly = _monthly_mwh(sim_h)

        # Align to 12 months
        m_vals = meas_monthly.values[:12]
        s_vals = sim_monthly.values[:12]
        if len(m_vals) < 12:
            m_vals = np.pad(m_vals, (0, 12 - len(m_vals)))
        if len(s_vals) < 12:
            s_vals = np.pad(s_vals, (0, 12 - len(s_vals)))

        ax.bar(x - bw / 2, m_vals / 1e3, bw, color=C_MEAS, alpha=0.85,
               label="Measured", zorder=3)
        ax.bar(x + bw / 2, s_vals / 1e3, bw, color=C_SIM, alpha=0.70,
               label="Simulated", zorder=3)

        ax.set_xticks(x)
        ax.set_xticklabels(MONTH_LABELS, fontsize=6, rotation=45, ha="right")
        ax.set_ylabel("Heat output [GWh/month]", fontsize=7)
        ax.set_title(title, fontsize=7, pad=3)
        ax.tick_params(axis="y", labelsize=6)
        ax.yaxis.grid(True, lw=0.4, alpha=0.5)
        ax.set_axisbelow(True)

        ann_err = _annual_err_pct(
            pd.Series(m_vals), pd.Series(s_vals)
        )
        ann_meas = m_vals.sum() / 1e3
        ann_sim  = s_vals.sum() / 1e3
        ax.text(
            0.97, 0.97,
            f"Annual meas: {ann_meas:.0f} GWh\n"
            f"Annual sim:  {ann_sim:.0f} GWh\n"
            f"Annual err:  {ann_err:+.1f}%",
            transform=ax.transAxes,
            va="top", ha="right", fontsize=6,
            family="monospace",
            bbox=dict(boxstyle="square,pad=0.25", fc="white",
                      ec="#cccccc", alpha=0.90, lw=0.4),
        )

    # Shared legend on first axis
    axes[0].legend(fontsize=6, frameon=True, framealpha=0.85,
                   edgecolor="#cccccc", borderpad=0.3, handlelength=1.2,
                   loc="upper left")

    # Panel labels
    for ax, lbl in zip(axes, ["(a)", "(b)", "(c)"]):
        ax.text(0.04, 0.97, lbl, transform=ax.transAxes,
                va="top", ha="left", fontsize=7, fontweight="bold")

    saved = save_figure_bundle(fig, OUT_DIR / "fig_validation_sb_producers",
                               formats=("png", "pdf"))
    for p in saved:
        print(f"Saved: {p}")
    plt.close(fig)


if __name__ == "__main__":
    main()
