"""Paper 2 headline figures (F-P2-11 … F-P2-14).

Four publication figures computed from the 46-run scenario matrix outputs:

  F-P2-11  scenario_matrix   Cost-reduction heatmap: scenario family × heat-curve
                             stage, both networks side by side. Diverging palette
                             centred at 0 (worse than baseline = warm pole).
  F-P2-12  hot_charging_week Mechanism figure: one winter week, SB-S2 (normal
                             charging) vs SB-S3 (hot charging at 122 °C) —
                             electricity price, HP dispatch + TES charge, SOC.
  F-P2-13  pressure_path     Node-pressure envelope (min/mean/max over the year)
                             along the Memmingen trunk for the TES-site scenarios
                             — shows the F4 hydrostatic support at the TES node.
  F-P2-14  npv_co2           NPV vs. CO₂ reduction, bubble = annual CAPEX;
                             marker shape distinguishes the two networks.

Each figure is skipped with a clear message when its inputs are not solved yet.

Usage:
    python scripts/paper_2/figures/fig_p2_paperset.py           # all four
    python scripts/paper_2/figures/fig_p2_paperset.py 11 13     # subset
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

_ROOT = Path(__file__).resolve().parents[3]
OUT_BASE = _ROOT / "output" / "paper2_runs"
FIG_DIR = OUT_BASE / "figures"

# ── Palette (validated reference set: worst adjacent CVD ΔE 24.2, light mode) ──
C_BLUE = "#2a78d6"     # slot 1 — first series / cool diverging pole
C_AQUA = "#1baf7a"     # slot 2
C_YELLOW = "#eda100"   # slot 3
C_VIOLET = "#4a3aa7"   # slot 5
C_RED = "#e34948"      # slot 6 — warm diverging pole
INK = "#1a1a19"
INK_SOFT = "#52514e"
GRID = "#d8d7d2"
NEUTRAL_MID = "#f2f1ee"

DIVERGING = LinearSegmentedColormap.from_list(
    "p2_div", [C_RED, NEUTRAL_MID, C_BLUE], N=256
)

plt.rcParams.update({
    "font.size": 8.5,
    "font.family": "sans-serif",
    "axes.edgecolor": INK_SOFT,
    "axes.labelcolor": INK,
    "axes.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": INK_SOFT,
    "ytick.color": INK_SOFT,
    "text.color": INK,
    "grid.color": GRID,
    "grid.linewidth": 0.5,
    "legend.frameon": False,
    "pdf.fonttype": 42,
})


def _save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG_DIR / f"{name}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {name}.pdf/.png")


def _load_kpis() -> pd.DataFrame | None:
    p = OUT_BASE / "scenarios_kpis.csv"
    if not p.exists():
        print(f"  [SKIP] {p} missing — run kpi_calculator first")
        return None
    return pd.read_csv(p)


def _parse_id(sid: str) -> tuple[str, str, str]:
    """'SB-S3-HK0' → ('SB','S3','HK0'); 'BC-MM' → ('MM','BC','TVLFIX');
    'SB-S0-TVLFIX' → ('SB','S0','TVLFIX')."""
    parts = sid.split("-")
    if parts[0] == "BC":
        return parts[1], "BC", "TVLFIX"
    return parts[0], parts[1], parts[2]


# ═════════════════════════════════════════════════════════════════════════════
# F-P2-11 — scenario matrix heatmap
# ═════════════════════════════════════════════════════════════════════════════

_FAMILY_LABELS = {
    "BC": "BC — baseline",
    "S0": "S0 — HP+EK, no TES",
    "S1": "S1 — TES Zentrale",
    "S2": "S2 — TES at HP node",
    "S3": "S3 — hot charging",
    "S4": "S4 — TES Süd / free",
    "S5": "S5 — TES West / co-loc",
    "S6": "S6 — free siting",
    "S7": "S7 — free + hot",
}
_MM_FAMILY_LABELS = {
    "BC": "BC — baseline",
    "S0": "S0 — HP+EK, no TES",
    "S1": "S1 — TES j_1",
    "S2": "S2 — TES j_12",
    "S3": "S3 — hot charging",
    "S4": "S4 — free siting",
    "S5": "S5 — free + hot",
}
_STAGES = ["TVLFIX", "HK0", "HK1", "HK2"]


def fig_11_scenario_matrix() -> None:
    df = _load_kpis()
    if df is None:
        return
    df = df.dropna(subset=["cost_reduction_pct"], how="all")
    parsed = [_parse_id(s) for s in df["scenario_id"]]
    df = df.assign(net=[p[0] for p in parsed], fam=[p[1] for p in parsed],
                   stage=[p[2] for p in parsed])

    nets = [("SB", "Stadtbach", _FAMILY_LABELS), ("MM", "Memmingen", _MM_FAMILY_LABELS)]
    vmax = max(1.0, np.nanmax(np.abs(df["cost_reduction_pct"].values.astype(float))))
    norm = TwoSlopeNorm(vcenter=0.0, vmin=-vmax, vmax=vmax)

    fig, axes = plt.subplots(
        1, 2, figsize=(6.7, 3.4),
        gridspec_kw={"width_ratios": [1, 0.8], "wspace": 0.55},
    )
    last_im = None
    for ax, (net, title, fam_labels) in zip(axes, nets):
        fams = [f for f in fam_labels if f in set(df[df.net == net]["fam"])]
        mat = np.full((len(fams), len(_STAGES)), np.nan)
        for i, f in enumerate(fams):
            for j, st in enumerate(_STAGES):
                sel = df[(df.net == net) & (df.fam == f) & (df.stage == st)]
                if len(sel):
                    mat[i, j] = float(sel["cost_reduction_pct"].iloc[0])
        masked = np.ma.masked_invalid(mat)
        # positive reduction (good) → cool/blue pole; worse than BC → warm/red
        im = ax.imshow(masked, cmap=DIVERGING, norm=norm, aspect="auto")
        last_im = im
        ax.set_xticks(range(len(_STAGES)), ["TVL fix", "HK0", "HK1", "HK2"])
        ax.set_yticks(range(len(fams)), [fam_labels[f] for f in fams], fontsize=7.5)
        ax.set_title(title, fontsize=9, pad=6)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        # direct value labels — the heatmap is small enough to label every cell
        for i in range(len(fams)):
            for j in range(len(_STAGES)):
                if not np.isnan(mat[i, j]):
                    ax.text(j, i, f"{mat[i, j]:.1f}", ha="center", va="center",
                            fontsize=6.8, color=INK)
    if last_im is not None:
        cbar = fig.colorbar(last_im, ax=axes, shrink=0.75, pad=0.02)
        cbar.set_label("Cost reduction vs. baseline [%]", fontsize=8)
        cbar.outline.set_visible(False)
    fig.suptitle("Total-cost reduction across the scenario matrix", fontsize=10, y=1.02)
    _save(fig, "F-P2-11_scenario_matrix_heatmap")


# ═════════════════════════════════════════════════════════════════════════════
# F-P2-12 — hot-charging mechanism, one winter week
# ═════════════════════════════════════════════════════════════════════════════

def fig_12_hot_charging_week(week_start: str = "2025-01-13") -> None:
    d_norm = OUT_BASE / "SB-S2-HK0" / "dispatch_hourly.csv"
    d_hot = OUT_BASE / "SB-S3-HK0" / "dispatch_hourly.csv"
    if not (d_norm.exists() and d_hot.exists()):
        print("  [SKIP] F-P2-12 needs solved SB-S2-HK0 and SB-S3-HK0")
        return
    t0 = pd.Timestamp(week_start)
    t1 = t0 + pd.Timedelta(days=7)

    def _week(p):
        d = pd.read_csv(p, parse_dates=["timestamp"])
        return d[(d.timestamp >= t0) & (d.timestamp < t1)]

    dn, dh = _week(d_norm), _week(d_hot)
    if dn.empty or dh.empty:
        print("  [SKIP] F-P2-12: selected week not inside horizon")
        return

    fig, axes = plt.subplots(3, 1, figsize=(6.7, 5.2), sharex=True,
                             gridspec_kw={"height_ratios": [0.7, 1.1, 1.0],
                                          "hspace": 0.28})
    ax_p, ax_q, ax_soc = axes

    # (a) electricity price — context panel
    ax_p.plot(dn.timestamp, dn["lambda_buy_eur_MWh"], lw=1.2, color=INK_SOFT)
    ax_p.set_ylabel("Day-ahead price\n[€/MWh]", fontsize=7.5)
    ax_p.grid(axis="y")

    # (b) HP output and TES charging — hot vs normal
    ax_q.plot(dn.timestamp, dn["Q_hp_total_MW"], lw=1.4, color=C_BLUE,
              label="HP output — S2 (normal)")
    ax_q.plot(dh.timestamp, dh["Q_hp_total_MW"], lw=1.4, color=C_RED,
              label="HP output — S3 (hot 122 °C)")
    ax_q.fill_between(dh.timestamp, 0, dh["Q_storage_charge_MW"],
                      color=C_RED, alpha=0.22, lw=0,
                      label="TES charge — S3 (= HP hot channel)")
    ax_q.fill_between(dn.timestamp, 0, dn["Q_storage_charge_MW"],
                      color=C_BLUE, alpha=0.22, lw=0,
                      label="TES charge — S2")
    ax_q.set_ylabel("Thermal power [MW]", fontsize=7.5)
    ax_q.grid(axis="y")
    ax_q.legend(fontsize=6.8, ncol=2, loc="upper left")

    # (c) state of charge
    ax_soc.plot(dn.timestamp, dn["SOC_MWh"], lw=1.4, color=C_BLUE, label="SOC — S2")
    ax_soc.plot(dh.timestamp, dh["SOC_MWh"], lw=1.4, color=C_RED, label="SOC — S3 (ΔT 62 K)")
    ax_soc.set_ylabel("TES state of charge\n[MWh]", fontsize=7.5)
    ax_soc.grid(axis="y")
    ax_soc.legend(fontsize=6.8, loc="upper left")
    ax_soc.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

    fig.align_ylabels(axes)
    fig.suptitle("Hot charging mechanism — Stadtbach, one winter week", fontsize=10)
    _save(fig, "F-P2-12_hot_charging_week")


# ═════════════════════════════════════════════════════════════════════════════
# F-P2-13 — pressure envelope along the Memmingen trunk
# ═════════════════════════════════════════════════════════════════════════════

_MM_TRUNK = ["j_1", "j_2", "j_3", "j_9", "j_10", "j_11", "j_12", "j_13"]
_P13_SCENARIOS = [
    ("MM-S1-HK0", "S1 — TES at j_1", C_BLUE),
    ("MM-S2-HK0", "S2 — TES at j_12", C_AQUA),
    ("MM-S3-HK0", "S3 — hot charging at j_12", C_RED),
]


def fig_13_pressure_path() -> None:
    series = []
    for sid, label, color in _P13_SCENARIOS:
        pq = OUT_BASE / sid / "nodes_state_hourly.parquet"
        if not pq.exists():
            print(f"  [SKIP] F-P2-13: {sid} not solved yet")
            continue
        df = pd.read_parquet(pq, columns=["node_id", "P_bar"])
        df["P_bar"] = pd.to_numeric(df["P_bar"], errors="coerce")
        df = df.dropna(subset=["P_bar"])
        if df.empty:
            print(f"  [SKIP] F-P2-13: {sid} has no numeric pressure data")
            continue
        g = df[df.node_id.isin(_MM_TRUNK)].groupby("node_id")["P_bar"]
        stats = g.agg(["min", "mean", "max"]).reindex(_MM_TRUNK).astype(float)
        if stats["mean"].isna().all():
            print(f"  [SKIP] F-P2-13: {sid} trunk nodes not in state file")
            continue
        series.append((label, color, stats))
    if not series:
        return

    x = np.arange(len(_MM_TRUNK))
    fig, ax = plt.subplots(figsize=(6.7, 3.0))
    for label, color, st in series:
        ax.fill_between(x, st["min"], st["max"], color=color, alpha=0.15, lw=0)
        ax.plot(x, st["mean"], lw=1.6, color=color, marker="o", ms=3.5, label=label)
    ax.set_xticks(x, _MM_TRUNK, fontsize=7.5)
    ax.set_ylabel("Supply pressure [bar]")
    ax.set_xlabel("Node along main trunk")
    ax.grid(axis="y")
    ax.legend(fontsize=7.5, loc="best")
    ax.set_title("Annual node-pressure envelope by TES location — Memmingen",
                 fontsize=9.5, pad=8)
    _save(fig, "F-P2-13_pressure_path")


# ═════════════════════════════════════════════════════════════════════════════
# F-P2-14 — NPV vs CO2 reduction bubble chart
# ═════════════════════════════════════════════════════════════════════════════

def fig_14_npv_co2() -> None:
    df = _load_kpis()
    if df is None:
        return
    df = df[~df["baseline"].astype(bool)] if "baseline" in df else df
    if "NPV_eur" not in df.columns or "co2_reduction_pct" not in df.columns:
        print("  [SKIP] F-P2-14: KPI table predates NPV column — re-run kpi_calculator")
        return
    df = df.dropna(subset=["NPV_eur", "co2_reduction_pct"])
    if df.empty:
        print("  [SKIP] F-P2-14: no NPV/CO2 data yet")
        return
    parsed = [_parse_id(s) for s in df["scenario_id"]]
    df = df.assign(net=[p[0] for p in parsed], fam=[p[1] for p in parsed])

    fig, ax = plt.subplots(figsize=(5.4, 3.6))
    capex = df["CAPEX_annual_eur_per_a"].fillna(0).astype(float)
    size = 18 + 160 * (capex / max(capex.max(), 1.0))
    for net, marker, label in [("SB", "o", "Stadtbach"), ("MM", "s", "Memmingen")]:
        sel = df[df.net == net]
        ax.scatter(sel["co2_reduction_pct"], sel["NPV_eur"] / 1e6,
                   s=size[sel.index], marker=marker, facecolor=C_BLUE if net == "SB" else C_YELLOW,
                   edgecolor="white", linewidth=0.8, alpha=0.85, label=label, zorder=3)
        # direct-label the best scenario of each network
        if len(sel):
            best = sel.loc[sel["NPV_eur"].idxmax()]
            ax.annotate(best["scenario_id"],
                        (best["co2_reduction_pct"], best["NPV_eur"] / 1e6),
                        textcoords="offset points", xytext=(6, 5), fontsize=7,
                        color=INK)
    ax.axhline(0, color=INK_SOFT, lw=0.7)
    ax.set_xlabel("CO₂ reduction vs. baseline [%]")
    ax.set_ylabel("NPV over 20 a at 5 % [M€]")
    ax.grid(axis="y")
    ax.legend(fontsize=7.5, loc="lower right", title="bubble = annual CAPEX",
              title_fontsize=7)
    ax.set_title("Economic vs. climate performance of all investment scenarios",
                 fontsize=9.5, pad=8)
    _save(fig, "F-P2-14_npv_co2")


# ═════════════════════════════════════════════════════════════════════════════

_ALL = {"11": fig_11_scenario_matrix, "12": fig_12_hot_charging_week,
        "13": fig_13_pressure_path, "14": fig_14_npv_co2}

if __name__ == "__main__":
    which = [a for a in sys.argv[1:] if a in _ALL] or list(_ALL)
    for key in which:
        print(f"F-P2-{key}:")
        try:
            _ALL[key]()
        except Exception as exc:  # noqa: BLE001 — one broken figure must not kill the set
            print(f"  [FAIL] F-P2-{key}: {type(exc).__name__}: {exc}")
