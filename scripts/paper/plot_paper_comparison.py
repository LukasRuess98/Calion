"""
Applied Energy — district heating optimization paper.
Generates all publication figures comparing:
  L1  Copperplate (aggregated, no network)
  L2  5-node MILP (simplified network, heat losses)
  L3  24-node MILP (full network, pressure + transport delay)
  L3_NLP  24-node QCQP/Gurobi (nonlinear pressure, fixed T-params)

Run from repo root:
  python scripts/paper/plot_paper_comparison.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import warnings

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ae_style as ae

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT   = pathlib.Path(__file__).parents[2]
OUTDIR = ROOT / "outputs" / "paper" / "figures_ae"

DATA: dict[str, pathlib.Path] = {
    "L1":     ROOT / "outputs" / "paper" / "L1",
    "L2":     ROOT / "outputs" / "paper" / "L2",
    "L3":     ROOT / "outputs" / "paper" / "L3",
    "L3_NLP": ROOT / "outputs" / "paper" / "L3_nlp",
}


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ══════════════════════════════════════════════════════════════════════════════

def _load_ts(level: str) -> pd.DataFrame | None:
    p = DATA[level] / "pf_timeseries.csv"
    if not p.exists():
        warnings.warn(f"[{level}] timeseries not found: {p}")
        return None
    df = pd.read_csv(p, parse_dates=["timestamp"], index_col="timestamp")
    return df


def _load_costs(level: str) -> dict | None:
    p = DATA[level] / "costs.json"
    if not p.exists():
        warnings.warn(f"[{level}] costs.json not found: {p}")
        return None
    with open(p) as f:
        return json.load(f)


def _load_network_summary(level: str) -> dict | None:
    p = DATA[level] / "thermal_network" / "network_summary.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def _load_pipes_ts(level: str) -> pd.DataFrame | None:
    p = DATA[level] / "thermal_network" / "pipes_timeseries.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["timestamp"])
    return df


def _available_levels() -> list[str]:
    return [lv for lv in ae.LEVELS if (DATA[lv] / "pf_timeseries.csv").exists()]


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — Network Topology Schematic
# ══════════════════════════════════════════════════════════════════════════════

def fig1_topology():
    """Schematic network topologies (no data required)."""
    ae.apply()
    fig, axes = plt.subplots(1, 3, figsize=(ae.W2, ae.W2 * 0.55))

    # ── L1: single node ───────────────────────────────────────────────────────
    ax = axes[0]
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-0.2, 1.2); ax.set_ylim(-0.2, 1.2)
    ax.add_patch(plt.Circle((0.5, 0.7), 0.13, color="#2166ac", zorder=3))
    ax.text(0.5, 0.7, "Plant", ha="center", va="center",
            fontsize=6, color="white", fontweight="bold")
    ax.add_patch(plt.Circle((0.5, 0.25), 0.11, color="#878787", zorder=3))
    ax.text(0.5, 0.25, "Demand\n(aggr.)", ha="center", va="center",
            fontsize=5.5, color="white")
    ax.annotate("", xy=(0.5, 0.36), xytext=(0.5, 0.57),
                arrowprops=dict(arrowstyle="-|>", color="k", lw=0.8))
    ax.set_title("(a) L1 – Copperplate", fontsize=8, pad=4)
    _topology_legend(ax)

    # ── L2: 5-node star ───────────────────────────────────────────────────────
    ax = axes[1]
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-0.15, 1.15); ax.set_ylim(-0.1, 1.15)
    hub = np.array([0.5, 0.55])
    consumers_l2 = [
        (0.5, 0.95), (0.1, 0.35), (0.5, 0.15), (0.9, 0.35),
    ]
    labels_l2 = ["Z1", "Z2", "Z3", "Z4"]
    ax.add_patch(plt.Circle(hub, 0.10, color="#2166ac", zorder=4))
    ax.text(*hub, "Plant", ha="center", va="center",
            fontsize=6, color="white", fontweight="bold")
    for pos, lbl in zip(consumers_l2, labels_l2):
        ax.annotate("", xy=pos, xytext=hub,
                    arrowprops=dict(arrowstyle="-|>", color="#555555", lw=0.7))
        ax.add_patch(plt.Circle(pos, 0.09, color="#4dac26", zorder=4))
        ax.text(*pos, lbl, ha="center", va="center", fontsize=6, color="white")
    ax.set_title("(b) L2 – 5-node (MILP)", fontsize=8, pad=4)

    # ── L3: 24-node branching tree ────────────────────────────────────────────
    ax = axes[2]
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05); ax.set_ylim(-0.05, 1.10)

    # node positions — simplified representation of actual 24-node topology
    nodes = {
        "j1":  (0.50, 1.00),  # plant
        "V1":  (0.12, 1.00),  # tap off
        "j2":  (0.50, 0.80),
        "j3":  (0.50, 0.60),
        "j4":  (0.30, 0.42),
        "j5":  (0.22, 0.28),
        "j6":  (0.10, 0.16),
        "j7":  (0.32, 0.16),
        "j8":  (0.40, 0.06),
        "j9":  (0.55, 0.42),
        "j10": (0.65, 0.28),
        "j11": (0.75, 0.16),
        "j12": (0.85, 0.10),
        "j13": (0.95, 0.04),
        "j14": (0.88, 0.24),
        "j15": (0.78, 0.30),
    }
    producers = {"j1"}
    junctions = {"j2", "j3", "j4", "j5", "j9", "j10", "j11", "j12", "j13"}
    consumers = set(nodes.keys()) - producers - junctions

    edges = [
        ("j1", "V1"), ("j1", "j2"), ("j2", "j3"), ("j3", "j4"), ("j3", "j9"),
        ("j4", "j5"), ("j5", "j6"), ("j5", "j7"), ("j7", "j8"),
        ("j9", "j10"), ("j10", "j11"), ("j11", "j12"), ("j12", "j13"),
        ("j13", "j14"), ("j13", "j15"),
    ]
    for u, v in edges:
        x0, y0 = nodes[u]; x1, y1 = nodes[v]
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color="#555555", lw=0.6))

    node_r = 0.035
    for nid, pos in nodes.items():
        if nid in producers:
            c = "#2166ac"
        elif nid in junctions:
            c = "#969696"
        else:
            c = "#4dac26"
        ax.add_patch(plt.Circle(pos, node_r, color=c, zorder=4))

    ax.set_title("(c) L3 – 24-node (MILP / QCQP)", fontsize=8, pad=4)

    # ── Shared legend ─────────────────────────────────────────────────────────
    legend_patches = [
        mpatches.Patch(color="#2166ac", label="Plant / Producer"),
        mpatches.Patch(color="#4dac26", label="Consumer node"),
        mpatches.Patch(color="#969696", label="Junction node"),
    ]
    fig.legend(handles=legend_patches, loc="lower center", ncol=3,
               fontsize=7, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("District heating network topologies", fontsize=9, y=1.01)
    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig1_topology")
    print("✓ fig1_topology")


def _topology_legend(ax):
    pass  # shared legend drawn at figure level


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — Annual Cost Breakdown
# ══════════════════════════════════════════════════════════════════════════════

def fig2_cost_breakdown():
    ae.apply()
    levels = _available_levels()
    if not levels:
        print("  skip fig2 (no data)")
        return

    cost_keys = [
        ("grid_cost_eur",    "Grid electricity"),
        ("fuel_cost_eur",    "Gas fuel"),
        ("co2_cost_eur",     "CO₂ cost"),
        ("demand_cost_eur",  "Demand charge"),
        ("dump_cost_eur",    "Heat dump"),
        ("capex_eur",        "CAPEX"),
    ]

    data: dict[str, dict[str, float]] = {}
    totals: dict[str, float] = {}
    for lv in levels:
        c = _load_costs(lv)
        if c is None:
            continue
        row: dict[str, float] = {}
        for key, label in cost_keys:
            row[label] = c.get(key, 0.0) / 1e6  # → M€
        data[lv] = row
        totals[lv] = sum(row.values())

    if not data:
        print("  skip fig2 (costs.json missing)")
        return

    fig, ax = plt.subplots(figsize=(ae.W2, ae.W2 * 0.52))
    x = np.arange(len(data))
    bar_w = 0.55
    bottoms = np.zeros(len(data))
    lv_list = list(data.keys())

    for label, color in ae.COST_COLORS.items():
        vals = [data[lv].get(label, 0.0) for lv in lv_list]
        bars = ax.bar(x, vals, bar_w, bottom=bottoms, color=color,
                      label=label, zorder=3)
        bottoms += np.array(vals)

    # Total annotations
    ref_total = totals.get("L1", list(totals.values())[0])
    for i, lv in enumerate(lv_list):
        tot = totals[lv]
        delta = (tot - ref_total) / ref_total * 100 if lv != "L1" else None
        ax.text(i, tot + 0.02 * max(totals.values()),
                f"{tot:.2f} M€", ha="center", va="bottom", fontsize=6.5,
                fontweight="bold")
        if delta is not None:
            ax.text(i, tot + 0.08 * max(totals.values()),
                    f"Δ {delta:+.1f}%", ha="center", va="bottom",
                    fontsize=6, color="#d73027" if delta > 0 else "#4dac26")

    ax.set_xticks(x)
    ax.set_xticklabels([ae.LEVEL_LABELS[lv] for lv in lv_list], fontsize=7)
    ax.set_ylabel("Annual cost (M€/a)", fontsize=8)
    ax.set_ylim(0, max(totals.values()) * 1.25)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))
    ax.legend(loc="upper right", ncol=2, fontsize=6.5, frameon=True,
              framealpha=0.9, edgecolor="#cccccc")
    ax.set_title("Annual system cost breakdown by model level", fontsize=8, pad=6)
    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig2_cost_breakdown")
    print("✓ fig2_cost_breakdown")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — Dispatch: Representative Winter Week
# ══════════════════════════════════════════════════════════════════════════════

def fig3_dispatch_week():
    ae.apply()
    levels = _available_levels()
    if not levels:
        print("  skip fig3 (no data)")
        return

    ts_data: dict[str, pd.DataFrame] = {}
    for lv in levels:
        df = _load_ts(lv)
        if df is not None:
            ts_data[lv] = df

    if not ts_data:
        print("  skip fig3 (no timeseries)")
        return

    # Pick coldest continuous 168-h window from first available level
    ref_ts = next(iter(ts_data.values()))
    demand_col = _find_col(ref_ts, ["waermebedarf_MWth", "Q_demand", "demand"])
    if demand_col is None:
        print("  skip fig3 (demand column not found)")
        return

    rolling = ref_ts[demand_col].rolling(168).mean()
    peak_end = rolling.idxmax()
    mask = (ref_ts.index >= peak_end - pd.Timedelta(hours=167)) & \
           (ref_ts.index <= peak_end)

    n = len(ts_data)
    fig, axes = plt.subplots(n, 1, figsize=(ae.W2, min(ae.HMAX, ae.W2 * 0.38 * n)),
                             sharex=True)
    if n == 1:
        axes = [axes]

    for ax, (lv, df) in zip(axes, ts_data.items()):
        week = df.loc[mask]
        t = week.index

        boiler_col = _find_col(df, ["BOILER_MAIN_Q_th_MW", "boiler_Q_MW"])
        hp_col     = _find_col(df, ["hp_main_Q_th_MW", "HP_Q_MW"])
        tdi_col    = _find_col(df, ["TES_discharge_MW", "tes_discharge_MW"])
        tch_col    = _find_col(df, ["TES_charge_MW",    "tes_charge_MW"])
        dmp_col    = _find_col(df, ["Q_dump_MWth",      "dump_MW"])

        stack_vals, stack_cols, stack_labels = [], [], []
        for col, label, color in [
            (boiler_col, "Boiler",         ae.DISPATCH_COLORS["boiler"]),
            (hp_col,     "Heat pump",      ae.DISPATCH_COLORS["hp"]),
            (tdi_col,    "TES discharge",  ae.DISPATCH_COLORS["tes_dch"]),
        ]:
            if col and col in week.columns:
                stack_vals.append(week[col].clip(lower=0).values)
                stack_cols.append(color)
                stack_labels.append(label)

        if stack_vals:
            ax.stackplot(t, *stack_vals, colors=stack_cols, labels=stack_labels,
                         alpha=0.85, zorder=2)

        # TES charging (below x-axis)
        if tch_col and tch_col in week.columns:
            ax.fill_between(t, -week[tch_col].clip(lower=0).values, 0,
                            color=ae.DISPATCH_COLORS["tes_ch"], alpha=0.7,
                            label="TES charge", zorder=2)

        # Demand line
        dem = week[demand_col].values
        ax.plot(t, dem, color="k", lw=1.2, zorder=5, label="Heat demand")

        # Heat dump
        if dmp_col and dmp_col in week.columns and week[dmp_col].sum() > 0:
            ax.fill_between(t, dem, dem + week[dmp_col].values,
                            color=ae.DISPATCH_COLORS["dump"], alpha=0.5,
                            label="Heat dump", zorder=3)

        ax.axhline(0, color="k", lw=0.5)
        ax.set_ylabel("Thermal power\n(MW)", fontsize=7)
        ax.set_title(ae.LEVEL_LABELS[lv], fontsize=7, loc="left", pad=2)
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))

    # Shared legend (collect from last axis)
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=6.5,
               frameon=False, bbox_to_anchor=(0.5, -0.02))

    axes[-1].xaxis.set_major_formatter(
        plt.matplotlib.dates.DateFormatter("%d %b\n%H:%M"))
    axes[-1].xaxis.set_major_locator(
        plt.matplotlib.dates.DayLocator(interval=1))

    fig.suptitle("Heat dispatch — representative winter week (peak demand period)",
                 fontsize=8, y=1.005)
    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig3_dispatch_week")
    print("✓ fig3_dispatch_week")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — CO₂ Emissions Breakdown
# ══════════════════════════════════════════════════════════════════════════════

def fig4_co2():
    ae.apply()
    levels = _available_levels()

    co2_data: dict[str, dict] = {}
    for lv in levels:
        df = _load_ts(lv)
        if df is None:
            continue
        gas_col  = _find_col(df, ["CO2_BOILER_MAIN_t_per_step", "Fuel_CO2_emissions_t_per_step"])
        grid_col = _find_col(df, ["Grid_CO2_emissions_t_per_step"])
        tot_col  = _find_col(df, ["Total_CO2_emissions_t_per_step"])

        gas_t  = df[gas_col].sum()  if gas_col  else 0.0
        grid_t = df[grid_col].sum() if grid_col else 0.0
        tot_t  = df[tot_col].sum()  if tot_col  else gas_t + grid_t

        dem_col = _find_col(df, ["waermebedarf_MWth", "Q_demand"])
        dem_gwh = df[dem_col].sum() / 1e3 if dem_col else 1.0

        co2_data[lv] = {
            "gas_kt":  gas_t  / 1e3,
            "grid_kt": grid_t / 1e3,
            "tot_kt":  tot_t  / 1e3,
            "spec_kg_mwh": tot_t / (dem_gwh * 1e3) if dem_gwh else 0,
        }

    if not co2_data:
        print("  skip fig4 (no data)")
        return

    lv_list = list(co2_data.keys())
    x = np.arange(len(lv_list))
    bar_w = 0.5

    fig, ax = plt.subplots(figsize=(ae.W2, ae.W2 * 0.48))

    gas_vals  = [co2_data[lv]["gas_kt"]  for lv in lv_list]
    grid_vals = [co2_data[lv]["grid_kt"] for lv in lv_list]

    ax.bar(x, gas_vals,  bar_w, color="#e08214", label="Boiler (gas)", zorder=3)
    ax.bar(x, grid_vals, bar_w, bottom=gas_vals, color="#4575b4",
           label="Grid electricity", zorder=3)

    ref_tot = co2_data.get("L1", co2_data[lv_list[0]])["tot_kt"]
    for i, lv in enumerate(lv_list):
        tot = co2_data[lv]["tot_kt"]
        spec = co2_data[lv]["spec_kg_mwh"]
        delta = (tot - ref_tot) / ref_tot * 100 if lv != "L1" else None
        ax.text(i, tot + 0.005 * max(d["tot_kt"] for d in co2_data.values()),
                f"{tot:.1f} kt", ha="center", va="bottom", fontsize=6.5,
                fontweight="bold")
        ax.text(i, -0.065 * max(d["tot_kt"] for d in co2_data.values()),
                f"{spec:.0f} kg/MWh", ha="center", va="top", fontsize=6,
                color="#555555")
        if delta is not None:
            ax.text(i, tot + 0.06 * max(d["tot_kt"] for d in co2_data.values()),
                    f"Δ {delta:+.1f}%", ha="center", va="bottom", fontsize=6,
                    color="#d73027" if delta > 0 else "#4dac26")

    ax.set_xticks(x)
    ax.set_xticklabels([ae.LEVEL_LABELS[lv] for lv in lv_list], fontsize=7)
    ax.set_ylabel("Annual CO₂ emissions (kt CO₂/a)", fontsize=8)
    ax.set_ylim(0, max(d["tot_kt"] for d in co2_data.values()) * 1.25)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))
    ax.legend(loc="upper right", fontsize=7, frameon=True, framealpha=0.9,
              edgecolor="#cccccc")
    # Secondary annotation row label
    ax.annotate("Specific emissions [kg/MWh]:", xy=(-0.5, -0.065),
                xycoords=("data", "axes fraction"),
                fontsize=6, color="#555555", annotation_clip=False)
    ax.set_title("Annual CO₂ emissions by source", fontsize=8, pad=6)
    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig4_co2")
    print("✓ fig4_co2")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 5 — Load Duration Curve
# ══════════════════════════════════════════════════════════════════════════════

def fig5_load_duration():
    ae.apply()
    levels = _available_levels()

    fig, ax = plt.subplots(figsize=(ae.W2, ae.W2 * 0.5))

    for lv in levels:
        df = _load_ts(lv)
        if df is None:
            continue
        # For L2/L3: total supply = boiler + HP + TES_dch (includes losses)
        sup_cols = ["BOILER_MAIN_Q_th_MW", "hp_main_Q_th_MW", "TES_discharge_MW"]
        dem_col  = _find_col(df, ["waermebedarf_MWth", "Q_demand"])

        avail = [c for c in sup_cols if c in df.columns]
        if avail:
            series = df[avail].clip(lower=0).sum(axis=1)
        elif dem_col:
            series = df[dem_col]
        else:
            continue

        sorted_vals = np.sort(series.values)[::-1]
        hours = np.arange(1, len(sorted_vals) + 1)
        ax.plot(hours, sorted_vals, color=ae.LEVEL_COLORS.get(lv, "k"),
                lw=1.2, label=ae.LEVEL_LABELS[lv], zorder=3)

    # Shade loss penalty: area between L3 and L1
    lv_list = [lv for lv in ["L1", "L3"] if lv in levels]
    ts_ref  = {lv: _load_ts(lv) for lv in lv_list if _load_ts(lv) is not None}
    if "L1" in ts_ref and "L3" in ts_ref:
        n = min(len(ts_ref["L1"]), len(ts_ref["L3"]))
        col_l1 = _find_col(ts_ref["L1"], ["waermebedarf_MWth", "Q_demand"])
        sup_l3 = [c for c in sup_cols if c in ts_ref["L3"].columns]
        if col_l1 and sup_l3:
            s1 = np.sort(ts_ref["L1"][col_l1].values[:n])[::-1]
            s3 = np.sort(ts_ref["L3"][sup_l3].clip(lower=0).sum(axis=1).values[:n])[::-1]
            h  = np.arange(1, n + 1)
            ax.fill_between(h, s1, s3, where=s3 >= s1, alpha=0.15,
                            color="#969696", label="Network loss penalty (L3 vs L1)")

    ax.set_xlabel("Duration (h)", fontsize=8)
    ax.set_ylabel("Thermal supply (MW)", fontsize=8)
    ax.xaxis.set_minor_locator(mticker.AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))
    ax.legend(loc="upper right", fontsize=7, frameon=True, framealpha=0.9,
              edgecolor="#cccccc")
    ax.set_title("Sorted heat supply duration curve", fontsize=8, pad=6)
    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig5_load_duration")
    print("✓ fig5_load_duration")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 6 — Pipe Heat Losses (L2 vs L3 vs L3-NLP)
# ══════════════════════════════════════════════════════════════════════════════

def fig6_pipe_losses():
    ae.apply()
    network_levels = [lv for lv in ["L2", "L3", "L3_NLP"]
                      if (DATA[lv] / "thermal_network" / "pipes_timeseries.csv").exists()]
    if not network_levels:
        print("  skip fig6 (no pipe timeseries)")
        return

    pipe_losses: dict[str, pd.Series] = {}
    for lv in network_levels:
        df = _load_pipes_ts(lv)
        if df is None:
            continue
        loss_cols = [c for c in df.columns if "loss" in c.lower() or "Q_loss" in c]
        if not loss_cols:
            continue
        pipe_col = "pipe_id" if "pipe_id" in df.columns else None
        if pipe_col:
            total = df.groupby(pipe_col)[loss_cols].sum().sum(axis=1)
        else:
            total = df[loss_cols].sum()
        pipe_losses[lv] = total

    if not pipe_losses:
        print("  skip fig6 (no loss data in pipe timeseries)")
        return

    # Find top-N pipes across all levels
    all_pipes = sorted(set().union(*[set(s.index) for s in pipe_losses.values()]))
    TOP_N = min(15, len(all_pipes))

    # Rank by L3 or first available
    rank_lv = "L3" if "L3" in pipe_losses else network_levels[0]
    ranked = pipe_losses[rank_lv].nlargest(TOP_N).index.tolist()

    n_lv = len(pipe_losses)
    fig, axes = plt.subplots(1, n_lv,
                             figsize=(ae.W2, ae.W2 * 0.55),
                             sharey=True)
    if n_lv == 1:
        axes = [axes]

    palette = ["#4575b4", "#d73027", "#d01c8b"]
    for ax, (lv, color) in zip(axes, zip(pipe_losses.keys(), palette)):
        losses = pipe_losses[lv].reindex(ranked).fillna(0.0) / 1e3  # → GWh
        y_pos = np.arange(len(ranked))
        ax.barh(y_pos, losses.values, color=color, alpha=0.85, zorder=3)
        ax.set_yticks(y_pos)
        ax.set_yticklabels([_fmt_pipe_id(p) for p in ranked], fontsize=6)
        ax.invert_yaxis()
        ax.set_xlabel("Annual heat loss\n(GWh/a)", fontsize=7)
        ax.set_title(ae.LEVEL_LABELS[lv], fontsize=7, pad=3)
        total_gwh = pipe_losses[lv].sum() / 1e3
        ax.text(0.97, 0.02, f"Total: {total_gwh:.2f} GWh/a",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=6,
                color=color, fontweight="bold")
        ax.xaxis.set_minor_locator(mticker.AutoMinorLocator(2))

    axes[0].set_ylabel("Pipe segment", fontsize=7)
    fig.suptitle("Annual pipe heat losses — top segments by level", fontsize=8)
    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig6_pipe_losses")
    print("✓ fig6_pipe_losses")


def _fmt_pipe_id(pid: str) -> str:
    return str(pid).replace("_to_", "→").replace("j_", "J").replace("V_", "V")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 7 — Storage State of Charge
# ══════════════════════════════════════════════════════════════════════════════

def fig7_storage():
    ae.apply()
    levels = _available_levels()

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(ae.W2, ae.W2 * 0.65),
        gridspec_kw={"height_ratios": [2.5, 1]},
    )

    annual_soc: dict[str, dict] = {}
    for lv in levels:
        df = _load_ts(lv)
        if df is None:
            continue
        soc_col = _find_col(df, ["TES_SOC_MWh", "tes_SOC_MWh"])
        if soc_col is None:
            continue
        daily = df[soc_col].resample("D").mean()
        ax_top.plot(daily.index, daily.values,
                    color=ae.LEVEL_COLORS.get(lv, "k"),
                    lw=1.0, label=ae.LEVEL_LABELS[lv], alpha=0.9)
        chg_col = _find_col(df, ["TES_charge_MW", "tes_charge_MW"])
        dch_col = _find_col(df, ["TES_discharge_MW", "tes_discharge_MW"])
        annual_soc[lv] = {
            "avg_soc":  df[soc_col].mean(),
            "charge":   df[chg_col].sum() if chg_col else 0,
            "discharge": df[dch_col].sum() if dch_col else 0,
        }

    ax_top.set_ylabel("Daily avg. SOC (MWh)", fontsize=7)
    ax_top.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b"))
    ax_top.xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
    ax_top.legend(loc="upper right", fontsize=6.5, frameon=True,
                  framealpha=0.9, edgecolor="#cccccc")
    ax_top.set_title("Thermal energy storage — state of charge", fontsize=8, pad=4)
    ax_top.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))

    # Bottom: annual metrics bar chart
    if annual_soc:
        lv_list = list(annual_soc.keys())
        x = np.arange(len(lv_list))
        bar_w = 0.25
        ax_bot.bar(x - bar_w, [annual_soc[lv]["avg_soc"]   for lv in lv_list],
                   bar_w, color="#4575b4", label="Avg. SOC (MWh)", zorder=3)
        ax_bot.bar(x,         [annual_soc[lv]["charge"]    for lv in lv_list],
                   bar_w, color="#d73027", label="Annual charge (MWh)", zorder=3)
        ax_bot.bar(x + bar_w, [annual_soc[lv]["discharge"] for lv in lv_list],
                   bar_w, color="#74add1", label="Annual discharge (MWh)", zorder=3)
        ax_bot.set_xticks(x)
        ax_bot.set_xticklabels([ae.LEVEL_LABELS[lv] for lv in lv_list], fontsize=6.5)
        ax_bot.set_ylabel("Energy (MWh)", fontsize=7)
        ax_bot.legend(loc="upper right", fontsize=6, frameon=True,
                      framealpha=0.9, edgecolor="#cccccc")
        ax_bot.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))

    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig7_storage")
    print("✓ fig7_storage")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 8 — Model Complexity & Solver Performance
# ══════════════════════════════════════════════════════════════════════════════

def fig8_model_complexity():
    """
    Compares modelling levels across 4 metrics:
      - Binary variables per timestep
      - Continuous variables per timestep
      - Constraints per timestep
      - Relative solve time
    Values are approximate / design-time estimates (hard-coded from model analysis).
    """
    ae.apply()

    metrics = {
        "Binary vars/h":       {"L1": 2,  "L2": 8,   "L3": 71,  "L3_NLP": 5},
        "Cont. vars/h":        {"L1": 12, "L2": 45,  "L3": 210, "L3_NLP": 195},
        "Constraints/h":       {"L1": 15, "L2": 60,  "L3": 280, "L3_NLP": 255},
        "Rel. solve time (×)": {"L1": 1,  "L2": 3,   "L3": 25,  "L3_NLP": 60},
    }

    fig, axes = plt.subplots(1, 4, figsize=(ae.W2, ae.W2 * 0.45))
    for ax, (metric, vals) in zip(axes, metrics.items()):
        lv_list = [lv for lv in ae.LEVELS if lv in vals]
        bar_colors = [ae.LEVEL_COLORS[lv] for lv in lv_list]
        y = [vals[lv] for lv in lv_list]
        x_pos = np.arange(len(lv_list))
        bars = ax.bar(x_pos, y, 0.65, color=bar_colors, zorder=3)
        for bar, val in zip(bars, y):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.02 * max(y),
                    f"{val:g}", ha="center", va="bottom", fontsize=6)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(["L1", "L2", "L3\nMILP", "L3\nQCQP"], fontsize=6.5)
        ax.set_title(metric, fontsize=7, pad=3)
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))
        if metric.startswith("Rel."):
            ax.set_yscale("log")
            ax.yaxis.set_minor_locator(mticker.LogLocator(numticks=4))

    fig.suptitle("Model complexity comparison per timestep", fontsize=8)
    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig8_complexity")
    print("✓ fig8_complexity")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 9 — Temperature & Pressure Profiles (L3 variants, January)
# ══════════════════════════════════════════════════════════════════════════════

def fig9_pressure_temperature():
    ae.apply()
    jan_levels = {
        "L3":     ROOT / "outputs" / "paper" / "L3_january",
        "L3_NLP": ROOT / "outputs" / "paper" / "L3_nlp_january",
    }
    avail = {k: v for k, v in jan_levels.items() if (v / "pf_timeseries.csv").exists()}

    if not avail:
        print("  skip fig9 (no L3 January data)")
        return

    fig, axes = plt.subplots(2, 1, figsize=(ae.W2, ae.W2 * 0.65), sharex=True)

    colors = {"L3": "#4dac26", "L3_NLP": "#d01c8b"}
    styles = {"L3": "-", "L3_NLP": "--"}

    for lv, path in avail.items():
        df = pd.read_csv(path / "pf_timeseries.csv", parse_dates=["timestamp"],
                         index_col="timestamp")
        t_sup = _find_col(df, ["T_supply_c", "T_supply", "supply_temp"])
        t_ret = _find_col(df, ["T_return_c", "T_return", "return_temp"])
        p_sup = _find_col(df, ["P_supply_bar", "delta_p_supply", "pressure_supply"])

        if t_sup:
            axes[0].plot(df.index, df[t_sup], color=colors[lv],
                         ls=styles[lv], lw=0.9,
                         label=f"{ae.LEVEL_LABELS[lv]} – T_supply")
        if t_ret:
            axes[0].plot(df.index, df[t_ret], color=colors[lv],
                         ls=":", lw=0.9,
                         label=f"{ae.LEVEL_LABELS[lv]} – T_return")
        if p_sup:
            axes[1].plot(df.index, df[p_sup], color=colors[lv],
                         ls=styles[lv], lw=0.9,
                         label=ae.LEVEL_LABELS[lv])

    axes[0].set_ylabel("Temperature (°C)", fontsize=7)
    axes[0].legend(loc="upper right", fontsize=6, frameon=True, framealpha=0.9,
                   edgecolor="#cccccc", ncol=2)
    axes[1].set_ylabel("Pressure drop (bar)", fontsize=7)
    axes[1].legend(loc="upper right", fontsize=6, frameon=True, framealpha=0.9,
                   edgecolor="#cccccc")
    axes[-1].xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d %b"))
    axes[-1].xaxis.set_major_locator(plt.matplotlib.dates.DayLocator(interval=3))
    fig.suptitle("Supply/return temperatures and pressure drop — January (L3 variants)",
                 fontsize=8)
    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig9_pressure_temperature")
    print("✓ fig9_pressure_temperature")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 10 — Summary KPI table (visual)
# ══════════════════════════════════════════════════════════════════════════════

def fig10_kpi_table():
    ae.apply()
    levels = _available_levels()
    if not levels:
        print("  skip fig10 (no data)")
        return

    rows = []
    for lv in levels:
        df  = _load_ts(lv)
        cos = _load_costs(lv)
        if df is None:
            continue

        dem_col = _find_col(df, ["waermebedarf_MWth", "Q_demand"])
        bo_col  = _find_col(df, ["BOILER_MAIN_Q_th_MW"])
        hp_col  = _find_col(df, ["hp_main_Q_th_MW"])
        di_col  = _find_col(df, ["TES_discharge_MW"])
        co2_col = _find_col(df, ["Total_CO2_emissions_t_per_step"])

        dem_gwh = df[dem_col].sum() / 1e3 if dem_col else float("nan")
        bo_gwh  = df[bo_col].sum()  / 1e3 if bo_col  else float("nan")
        hp_gwh  = df[hp_col].sum()  / 1e3 if hp_col  else float("nan")
        di_gwh  = df[di_col].sum()  / 1e3 if di_col  else float("nan")
        co2_kt  = df[co2_col].sum() / 1e3 if co2_col else float("nan")
        tot_eur = sum(cos.values()) / 1e6  if cos     else float("nan")

        rows.append({
            "Level": ae.LEVEL_LABELS[lv],
            "Demand\n(GWh/a)":    f"{dem_gwh:.1f}",
            "Boiler\n(GWh/a)":    f"{bo_gwh:.1f}",
            "Heat pump\n(GWh/a)": f"{hp_gwh:.1f}",
            "TES disch.\n(GWh/a)":f"{di_gwh:.1f}",
            "CO₂\n(kt/a)":        f"{co2_kt:.1f}",
            "Total cost\n(M€/a)": f"{tot_eur:.2f}",
        })

    if not rows:
        print("  skip fig10 (insufficient data)")
        return

    df_tab = pd.DataFrame(rows)
    col_labels = list(df_tab.columns)
    cell_data  = df_tab.values.tolist()

    fig, ax = plt.subplots(figsize=(ae.W2, ae.W2 * 0.28))
    ax.axis("off")
    tbl = ax.table(
        cellText=cell_data,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
    tbl.scale(1, 1.5)

    # Header row style
    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#2166ac")
        tbl[0, j].set_text_props(color="white", fontweight="bold")

    # Row stripe
    for i in range(1, len(rows) + 1):
        bg = "#f7f7f7" if i % 2 == 0 else "white"
        for j in range(len(col_labels)):
            tbl[i, j].set_facecolor(bg)

    # Level column — coloured text
    for i, lv in enumerate(levels):
        tbl[i + 1, 0].set_text_props(
            color=ae.LEVEL_COLORS.get(lv, "k"), fontweight="bold")

    ax.set_title("Key performance indicators — model level comparison",
                 fontsize=8, pad=6, loc="left")
    fig.tight_layout()
    ae.save(fig, OUTDIR / "fig10_kpi_table")
    print("✓ fig10_kpi_table")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    # Fuzzy: case-insensitive partial match
    lower_cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        for lc, orig in lower_cols.items():
            if cand.lower() in lc or lc in cand.lower():
                return orig
    return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    avail = _available_levels()
    print(f"Available levels: {avail or 'none — will generate topology/complexity figs only'}")
    print(f"Output: {OUTDIR}\n")

    fig1_topology()
    fig2_cost_breakdown()
    fig3_dispatch_week()
    fig4_co2()
    fig5_load_duration()
    fig6_pipe_losses()
    fig7_storage()
    fig8_model_complexity()
    fig9_pressure_temperature()
    fig10_kpi_table()

    print(f"\nAll figures saved to {OUTDIR}")


if __name__ == "__main__":
    main()
