"""
fig_trunk_profile.py
====================
Three-panel figure showing the supply-temperature, mass-flow, and specific
heat-loss profile along the main trunk j1 -> j15 (Jan 2025, L3^NL mean).

Panel (a): Supply temperature at each trunk node (mean ± p10/p90 band)
Panel (b): Mass flow and cumulative heat loss per segment (dual-axis bar)
Panel (c): Specific heat loss [W/m] per segment — highlights j13->j15 anomaly
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from scripts.paper.figures.fig_utils import save_fig
from scripts.paper.mpl_export import AE_RCPARAMS, AE_DOUBLE_COLUMN_IN

BASE = ROOT / "output/paper_runs/linearization_windows/jan_2025/L3NL"

# ── trunk definition ────────────────────────────────────────────────────────
# (pipe_id, length_m, upstream_node, downstream_node)
TRUNK = [
    ("j1_to_j2",   100, "j_1",  "j_2"),
    ("j2_to_j3",   100, "j_2",  "j_3"),
    ("j3_to_j9",   250, "j_3",  "j_9"),
    ("j9_to_j10",  200, "j_9",  "j_10"),
    ("j10_to_j11", 200, "j_10", "j_11"),
    ("j11_to_j12", 200, "j_11", "j_12"),
    ("j12_to_j13", 350, "j_12", "j_13"),
    ("j13_to_j15", 125, "j_13", "j_15"),
]

TRUNK_NODES = ["j_1","j_2","j_3","j_9","j_10","j_11","j_12","j_13","j_15"]
NODE_LABELS = ["j₁","j₂","j₃","j₉","j₁₀","j₁₁","j₁₂","j₁₃","j₁₅"]

# cumulative distance at each node [m]
CUM_DIST = [0]
for _, L, _, _ in TRUNK:
    CUM_DIST.append(CUM_DIST[-1] + L)

# pipe mid-points for bar charts
PIPE_MID  = [(CUM_DIST[i] + CUM_DIST[i+1]) / 2 for i in range(len(TRUNK))]
PIPE_WIDTHS = [t[1] * 0.72 for t in TRUNK]

C_TEMP    = "#1f4e79"   # dark blue — temperature
C_BAND    = "#bdd7ee"   # light blue — T band
C_FLOW    = "#2e75b6"   # mid blue  — mass flow bars
C_LOSS    = "#c55a11"   # burnt orange — heat loss / W/m
C_DEMAND  = "#70ad47"   # green — demand markers
C_ALERT   = "#ff0000"   # red — alert for j13->j15


def _load() -> tuple[dict, dict, dict]:
    ps  = pq.read_table(BASE / "pipe_state_hourly.parquet").to_pandas()
    ns  = pq.read_table(BASE / "nodes_state_hourly.parquet").to_pandas()

    real = ps[~ps["pipe_id"].str.contains("_Q|_loss|return|_ret", case=False, na=False)]

    # Node temperature stats
    node_T = {
        "mean": ns.groupby("node_id")["T_supply_c"].mean(),
        "p10":  ns.groupby("node_id")["T_supply_c"].quantile(0.10),
        "p90":  ns.groupby("node_id")["T_supply_c"].quantile(0.90),
    }
    node_Q = ns.groupby("node_id")["Q_demand_mw"].mean()

    # Per-pipe stats
    pipe_stats = {}
    for pipe_id, length, _, _ in TRUNK:
        d = real[real["pipe_id"] == pipe_id]
        if d.empty:
            pipe_stats[pipe_id] = {}
            continue
        pipe_stats[pipe_id] = {
            "length":        length,
            "m_dot_mean":    d["m_dot_kg_s"].mean(),
            "m_dot_p10":     d["m_dot_kg_s"].quantile(0.10),
            "m_dot_p90":     d["m_dot_kg_s"].quantile(0.90),
            "Q_loss_kW":     d["Q_loss_pipe_MW"].mean() * 1000,
            "Q_loss_Wpm":    d["Q_loss_pipe_MW"].mean() * 1e6 / length,
            "dp_mbar":       d["dp_Pa"].mean() / 100,
        }

    return node_T, node_Q, pipe_stats


def main() -> None:
    plt.rcParams.update(AE_RCPARAMS)

    node_T, node_Q, pipe_stats = _load()

    T_mean = [node_T["mean"][n] for n in TRUNK_NODES]
    T_p10  = [node_T["p10"][n]  for n in TRUNK_NODES]
    T_p90  = [node_T["p90"][n]  for n in TRUNK_NODES]
    demand = [node_Q.get(n, 0.0) for n in TRUNK_NODES]

    pipes       = [p for p, *_ in TRUNK]
    m_dot       = [pipe_stats[p].get("m_dot_mean", 0) for p in pipes]
    Q_loss_kW   = [pipe_stats[p].get("Q_loss_kW",  0) for p in pipes]
    Q_loss_Wpm  = [pipe_stats[p].get("Q_loss_Wpm", 0) for p in pipes]
    dp_mbar     = [pipe_stats[p].get("dp_mbar",    0) for p in pipes]

    # colour each bar: red for j13->j15, else normal
    bar_colors_flow = [C_ALERT if p == "j13_to_j15" else C_FLOW for p in pipes]
    bar_colors_wpm  = [C_ALERT if p == "j13_to_j15" else C_LOSS for p in pipes]

    # ── figure layout ──────────────────────────────────────────────────────
    fig_w = AE_DOUBLE_COLUMN_IN
    fig_h = fig_w * 0.88
    fig, axes = plt.subplots(
        3, 1,
        figsize=(fig_w, fig_h),
        gridspec_kw={"height_ratios": [1.6, 1.0, 1.0], "hspace": 0.45},
    )
    fig.subplots_adjust(left=0.10, right=0.94, top=0.96, bottom=0.08)

    ax_T, ax_m, ax_q = axes

    # ── Panel (a): Supply temperature ──────────────────────────────────────
    ax_T.fill_between(CUM_DIST, T_p10, T_p90,
                      color=C_BAND, alpha=0.55, linewidth=0, label="p10–p90")
    ax_T.plot(CUM_DIST, T_mean, color=C_TEMP, lw=1.2, marker="o",
              markersize=4.5, markeredgewidth=0.5,
              markeredgecolor="white", zorder=5, label="Mean $T_{\\mathrm{sup}}$")

    # Demand markers (size ∝ demand)
    for x, T, q in zip(CUM_DIST, T_mean, demand):
        if q > 0.01:
            ax_T.scatter(x, T, s=q * 280, color=C_DEMAND, zorder=6,
                         edgecolors=C_TEMP, linewidths=0.5)

    # Annotate j13->j15 drop
    ax_T.annotate(
        f"−{T_mean[-2]-T_mean[-1]:.1f} K\n(125 m, 0.9 kg/s)",
        xy=(CUM_DIST[-1], T_mean[-1]),
        xytext=(CUM_DIST[-2] - 120, T_mean[-1] + 1.2),
        fontsize=6.5, color=C_ALERT,
        arrowprops=dict(arrowstyle="->", color=C_ALERT, lw=0.8),
        ha="right",
    )

    ax_T.set_xlim(-30, CUM_DIST[-1] + 30)
    ax_T.set_ylim(81.5, 90.5)
    ax_T.set_ylabel("$T_{\\mathrm{sup}}$ [°C]", fontsize=8)
    ax_T.set_xticks(CUM_DIST)
    ax_T.set_xticklabels(NODE_LABELS, fontsize=7)
    ax_T.tick_params(which="both", length=3, width=0.6)
    ax_T.yaxis.set_major_locator(plt.MultipleLocator(2))
    ax_T.yaxis.set_minor_locator(plt.MultipleLocator(1))
    ax_T.grid(axis="y", linewidth=0.35, alpha=0.5)
    ax_T.set_title("(a) Supply temperature along trunk  j₁ → j₁₅  (Jan 2025, L3$^{\\mathrm{NL}}$ mean)",
                   loc="left", fontsize=7.5)

    # legend
    leg_handles = [
        plt.Line2D([0],[0], color=C_TEMP, lw=1.2, marker="o", ms=4, label="Mean $T_{\\mathrm{sup}}$"),
        mpatches.Patch(color=C_BAND, alpha=0.55, label="p10–p90 range"),
        plt.scatter([],[], s=60, color=C_DEMAND, edgecolors=C_TEMP, lw=0.5, label="Node demand (size $\\sim$ MW)"),
    ]
    ax_T.legend(handles=leg_handles, fontsize=6.3, loc="lower left",
                framealpha=0.9, borderpad=0.3, handletextpad=0.4, labelspacing=0.3)

    # ── Panel (b): Mass flow + cumulative pressure drop ─────────────────────
    ax_m2 = ax_m.twinx()

    bars = ax_m.bar(PIPE_MID, m_dot, width=PIPE_WIDTHS,
                    color=bar_colors_flow, alpha=0.82,
                    edgecolor="white", linewidth=0.4)
    ax_m.set_ylabel("Mass flow [kg/s]", fontsize=7.5, color=C_FLOW)
    ax_m.tick_params(axis="y", colors=C_FLOW, labelsize=7)
    ax_m.set_ylim(0, 22)

    # cumulative pressure drop line
    cum_dp = np.cumsum([0] + dp_mbar)
    ax_m2.plot(CUM_DIST, cum_dp, color=C_LOSS, lw=1.1,
               marker="s", markersize=3.5,
               markeredgewidth=0.5, markeredgecolor="white", zorder=5)
    ax_m2.set_ylabel("Cumul. Δp [mbar]", fontsize=7.5, color=C_LOSS)
    ax_m2.tick_params(axis="y", colors=C_LOSS, labelsize=7)
    ax_m2.set_ylim(0, 12)

    ax_m.set_xlim(-30, CUM_DIST[-1] + 30)
    ax_m.set_xticks(CUM_DIST)
    ax_m.set_xticklabels(NODE_LABELS, fontsize=7)
    ax_m.tick_params(which="both", length=3, width=0.6)
    ax_m.grid(axis="y", linewidth=0.35, alpha=0.4)
    ax_m.set_title("(b) Mass flow (bars) and cumulative pressure drop (line)",
                   loc="left", fontsize=7.5)

    # ── Panel (c): Specific heat loss W/m ──────────────────────────────────
    ax_q.bar(PIPE_MID, Q_loss_Wpm, width=PIPE_WIDTHS,
             color=bar_colors_wpm, alpha=0.85,
             edgecolor="white", linewidth=0.4)

    # annotate j13->j15
    idx_last = pipes.index("j13_to_j15")
    ax_q.annotate(
        f"{Q_loss_Wpm[idx_last]:.0f} W/m\n(≈ {Q_loss_Wpm[idx_last]/Q_loss_Wpm[idx_last-1]:.1f}× upstream)",
        xy=(PIPE_MID[idx_last], Q_loss_Wpm[idx_last]),
        xytext=(PIPE_MID[idx_last] - 250, Q_loss_Wpm[idx_last] * 0.82),
        fontsize=6.5, color=C_ALERT,
        arrowprops=dict(arrowstyle="->", color=C_ALERT, lw=0.8),
        ha="right",
    )

    ax_q.set_xlim(-30, CUM_DIST[-1] + 30)
    ax_q.set_ylim(0, 210)
    ax_q.set_ylabel("Spec. heat loss [W/m]", fontsize=7.5)
    ax_q.set_xlabel("Distance from source j₁ [m]", fontsize=7.5)
    ax_q.set_xticks(CUM_DIST)
    ax_q.set_xticklabels(NODE_LABELS, fontsize=7)
    ax_q.tick_params(which="both", length=3, width=0.6)
    ax_q.grid(axis="y", linewidth=0.35, alpha=0.5)
    ax_q.set_title("(c) Specific heat loss per metre — low-flow penalty at j₁₃→j₁₅",
                   loc="left", fontsize=7.5)

    # reference line: mean of other pipes
    mean_other = np.mean([v for p, v in zip(pipes, Q_loss_Wpm) if p != "j13_to_j15"])
    ax_q.axhline(mean_other, color="#888888", lw=0.7, ls=(0,(3,3)),
                 label=f"Other pipes avg: {mean_other:.0f} W/m")
    ax_q.legend(fontsize=6.3, loc="upper left",
                framealpha=0.9, borderpad=0.3)

    save_fig(fig, "F_trunk_profile")


if __name__ == "__main__":
    main()
