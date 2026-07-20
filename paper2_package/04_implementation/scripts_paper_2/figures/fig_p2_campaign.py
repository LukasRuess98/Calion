"""Paper 2 campaign-dependent figures F3–F9 (canonical Fraunhofer system).

Each figure reads the 46-run campaign outputs and renders itself, or prints a
clear [SKIP]/[PARTIAL] line when its inputs are not solved yet — so the whole
set can be run at any campaign completeness.

  F3  capacity_heatmap   LCOH over the Q̇_WP × V_TES grid (needs Part A sweep).
  F4  coupling           k ⇔ COP ⇔ V_TES ⇔ Q̇_WP over heat-curve stage, per net.
  F5  cost_split         CAPEX / energy-OPEX / CO₂ cost, best scenario vs baseline.
  F6  siting             endogenous vs best fixed TES/WP siting (ΔTAC + node).
  F7  tornado            sensitivity of TAC to the spec §7 parameter variations.
  F8  spatial_profile    T_supply / p_supply along a trunk (result + validation).
  F9  soc                TES state-of-charge over a winter + a transition week.

Usage:  python scripts/paper_2/figures/fig_p2_campaign.py           # all
        python scripts/paper_2/figures/fig_p2_campaign.py F4 F5     # subset
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]
OUT = _ROOT / "output" / "paper2_runs"
KPI = OUT / "scenarios_kpis.csv"
BASE = OUT / "baseline_kpis.csv"
SWEEP_DIR = _ROOT / "results"          # Part-A sweep CSVs land here
CO2_PRICE = 100.0                      # €/t (configs), used to split CO₂ out of OPEX

NET_LABEL = {"SB": "Stadtbach", "MM": "Memmingen"}


# ── shared helpers ───────────────────────────────────────────────────────────
def _kpis() -> pd.DataFrame | None:
    if not KPI.exists():
        print(f"  [SKIP] {KPI} missing"); return None
    df = pd.read_csv(KPI)
    # drop throwaway diagnostic rows
    return df[~df["scenario_id"].str.contains("TEST|DIAG|ZZ", na=False)].copy()


def _parse_id(sid: str) -> tuple[str, str, str]:
    p = sid.split("-")
    if p[0] == "BC":
        return p[1], "BC", "TVLFIX"
    return p[0], p[1], (p[2] if len(p) > 2 else "TVLFIX")


def _annotate_net(df: pd.DataFrame) -> pd.DataFrame:
    parsed = [_parse_id(s) for s in df["scenario_id"]]
    return df.assign(net=[p[0] for p in parsed], fam=[p[1] for p in parsed],
                     stage=[p[2] for p in parsed])


def _best_row(df: pd.DataFrame, net: str, *, require_tes: bool = False):
    """Best (max cost_reduction) *converged* investment scenario for a network."""
    sel = df[(df.net == net) & (~df["baseline"].astype(bool))].copy()
    sel = sel.dropna(subset=["cost_reduction_pct"])
    if require_tes and "V_TES_m3" in sel:
        sel = sel[pd.to_numeric(sel["V_TES_m3"], errors="coerce").fillna(0) > 0]
    # convergence guard (O-7): a real optimum has non-trivial TAC and CAPEX
    sel = sel[pd.to_numeric(sel["TAC_eur_per_a"], errors="coerce") > 1.0]
    if sel.empty:
        return None
    return sel.loc[sel["cost_reduction_pct"].astype(float).idxmax()]


# ═════════════════════════════════════════════════════════════════════════════
# F3 — capacity heatmap (depends on Part A sweep)
# ═════════════════════════════════════════════════════════════════════════════
def build_f3() -> None:
    print("F3 - capacity heatmap (LCOH over Q_WP x V_TES):")
    sweeps = sorted(SWEEP_DIR.glob("sweep_*.csv")) if SWEEP_DIR.exists() else []
    if not sweeps:
        print("  [SKIP] F3 needs the Part-A capacity sweep "
              "(results/sweep_{network}_{scenario}.csv) — not built yet")
        return
    _style.apply_rcparams()
    fig, axes = plt.subplots(1, len(sweeps), figsize=(_style.COL_DOUBLE_IN, 3.6),
                             squeeze=False)
    for ax, path in zip(axes[0], sweeps):
        d = pd.read_csv(path)
        piv = d.pivot_table(index="V_TES", columns="Q_WP", values="LCOH")
        im = ax.imshow(piv.values, origin="lower", aspect="auto", cmap="viridis",
                       extent=[piv.columns.min(), piv.columns.max(),
                               piv.index.min(), piv.index.max()])
        ax.set_xlabel("$\\dot{Q}_{WP}$ [MW]"); ax.set_ylabel("$V_{TES}$ [m$^3$]")
        ax.set_title(path.stem.replace("sweep_", ""), fontsize=9)
        fig.colorbar(im, ax=ax, label="LCOH [€/MWh]", shrink=0.8)
    _style.save(fig, "fig_F3_capacity_heatmap")


# ═════════════════════════════════════════════════════════════════════════════
# F4 — k ⇔ COP ⇔ V_TES ⇔ Q̇_WP coupling over heat-curve stage
# ═════════════════════════════════════════════════════════════════════════════
_F4_FAMILY = {"SB": "S1", "MM": "S1"}   # ceteris-paribus reference family per net
_STAGES = ["HK0", "HK1", "HK2"]
_F4_SERIES = [
    ("COP_annual_mean", "COP (rel.)", _style.FHG_GREEN),
    ("V_TES_m3", "TES capacity (rel.)", _style.FHG_BLUE),
    ("Q_WP_opt_MW", "WP capacity (rel.)", _style.FHG_ORANGE),
]


def build_f4() -> None:
    print("F4 - k<->COP<->V_TES coupling:")
    df = _kpis()
    if df is None:
        return
    df = _annotate_net(df)
    _style.apply_rcparams()
    fig, axes = plt.subplots(1, 2, figsize=(_style.COL_DOUBLE_IN, 3.5), sharey=True)
    any_data = False
    for ax, net in zip(axes, ["SB", "MM"]):
        fam = _F4_FAMILY[net]
        sub = df[(df.net == net) & (df.fam == fam) & (df.stage.isin(_STAGES))]
        sub = sub.set_index("stage").reindex(_STAGES)
        x = [float(v) if pd.notna(v) else np.nan for v in sub["T_VL_avg_c"]]
        drew = False
        for col, label, color in _F4_SERIES:
            y = pd.to_numeric(sub[col], errors="coerce").to_numpy(dtype=float)
            if np.all(np.isnan(y)) or np.nanmax(np.abs(y)) == 0:
                continue
            base = y[0] if (len(y) and not np.isnan(y[0]) and y[0] != 0) else np.nanmax(y)
            ax.plot(_STAGES, y / base, marker="o", ms=6, lw=2, color=color, label=label)
            drew = True
        any_data |= drew
        ax.set_title(f"{NET_LABEL[net]} — family {fam}", fontsize=9)
        ax.set_xlabel("Heat-curve stage (lower $T_{VL}$)")
        ax.grid(axis="y")
        if not drew:
            ax.text(0.5, 0.5, "no coupled data yet", transform=ax.transAxes,
                    ha="center", color=_style.INK_MUTED, fontsize=8)
    axes[0].set_ylabel("Value relative to HK0")
    h, l = axes[0].get_legend_handles_labels()
    if h:
        fig.legend(h, l, loc="lower center", ncol=3, fontsize=7.5,
                   bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Heat-curve coupling of COP, TES and WP capacity", fontsize=10.5, y=1.0)
    fig.subplots_adjust(bottom=0.2, wspace=0.08)
    if not any_data:
        print("  [PARTIAL] F4 rendered but reference families lack COP/capacity data")
    _style.save(fig, "fig_F4_coupling")


# ═════════════════════════════════════════════════════════════════════════════
# F5 — cost split: best scenario vs baseline
# ═════════════════════════════════════════════════════════════════════════════
def _cost_parts(row) -> tuple[float, float, float]:
    capex = float(row.get("CAPEX_annual_eur_per_a", 0) or 0)
    opex = float(row.get("OPEX_annual_eur_per_a", 0) or 0)
    co2 = float(row.get("co2_t_per_a", 0) or 0) * CO2_PRICE
    return capex / 1e6, max(opex - co2, 0) / 1e6, co2 / 1e6   # M€/a


def build_f5() -> None:
    print("F5 — cost split (best vs baseline):")
    df = _kpis()
    if df is None:
        return
    df = _annotate_net(df)
    _style.apply_rcparams()
    fig, axes = plt.subplots(1, 2, figsize=(_style.COL_DOUBLE_IN, 3.6))
    cats = [("CAPEX (annualised)", _style.FHG_BLUE),
            ("Energy OPEX", _style.FHG_GREEN),
            ("CO$_2$ cost", _style.FHG_ORANGE)]
    drew_any = False
    for ax, net in zip(axes, ["SB", "MM"]):
        base = df[(df.net == net) & (df["baseline"].astype(bool))]
        best = _best_row(df, net)
        if base.empty or best is None:
            ax.text(0.5, 0.5, "baseline or best scenario\nnot solved yet",
                    transform=ax.transAxes, ha="center", va="center",
                    color=_style.INK_MUTED, fontsize=8)
            ax.set_title(NET_LABEL[net], fontsize=9); ax.set_axis_off()
            continue
        drew_any = True
        cols = {"Baseline": _cost_parts(base.iloc[0]),
                f"Best: {best['scenario_id']}": _cost_parts(best)}
        labels = list(cols)
        bottoms = np.zeros(len(labels))
        for i, (cname, color) in enumerate(cats):
            vals = np.array([cols[l][i] for l in labels])
            ax.bar(labels, vals, bottom=bottoms, color=color, width=0.62,
                   label=cname, edgecolor="white", linewidth=1.2)
            bottoms += vals
        for j, l in enumerate(labels):
            ax.text(j, bottoms[j], f"{bottoms[j]:.2f}", ha="center", va="bottom",
                    fontsize=7.5, color=_style.INK)
        ax.set_title(NET_LABEL[net], fontsize=9)
        ax.set_ylabel("Total annual cost [M€/a]")
        ax.grid(axis="y")
        ax.tick_params(axis="x", labelsize=7.5)
    h, l = axes[0].get_legend_handles_labels()
    if h:
        fig.legend(h, l, loc="lower center", ncol=3, fontsize=7.5,
                   bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Annual-cost structure: best investment scenario vs. baseline",
                 fontsize=10.5, y=1.0)
    fig.subplots_adjust(bottom=0.18, wspace=0.28)
    if not drew_any:
        print("  [SKIP] F5: no network has both a baseline and a converged best scenario")
    _style.save(fig, "fig_F5_cost_split")


# ═════════════════════════════════════════════════════════════════════════════
# F6 — endogenous vs best fixed siting
# ═════════════════════════════════════════════════════════════════════════════
_ENDOG_FAMS = {"SB": ["S6", "S7"], "MM": ["S4", "S5"]}
_FIXED_FAMS = {"SB": ["S1", "S2", "S3", "S4", "S5"], "MM": ["S1", "S2", "S3"]}


def build_f6() -> None:
    print("F6 — endogenous vs best fixed siting:")
    df = _kpis()
    if df is None:
        return
    df = _annotate_net(df)
    rows = []
    for net in ["SB", "MM"]:
        fixed = df[(df.net == net) & (df.fam.isin(_FIXED_FAMS[net]))].dropna(
            subset=["TAC_eur_per_a"])
        fixed = fixed[pd.to_numeric(fixed["TAC_eur_per_a"], errors="coerce") > 1.0]
        endog = df[(df.net == net) & (df.fam.isin(_ENDOG_FAMS[net]))].dropna(
            subset=["TAC_eur_per_a"])
        endog = endog[pd.to_numeric(endog["TAC_eur_per_a"], errors="coerce") > 1.0]
        if fixed.empty or endog.empty:
            print(f"  [SKIP] F6 {net}: needs both fixed and *converged* endogenous runs "
                  f"(fixed={len(fixed)}, endog={len(endog)})")
            continue
        best_fixed = float(fixed["TAC_eur_per_a"].min())
        best_endog = endog.loc[endog["TAC_eur_per_a"].astype(float).idxmin()]
        node = str(best_endog.get("endog_site", "?"))
        rows.append((NET_LABEL[net],
                     (float(best_endog["TAC_eur_per_a"]) - best_fixed) / best_fixed * 100,
                     best_endog["scenario_id"], node))
    if not rows:
        return
    _style.apply_rcparams()
    fig, ax = plt.subplots(figsize=(_style.COL_SINGLE_IN * 1.4, 3.2))
    labels = [r[0] for r in rows]
    deltas = [r[1] for r in rows]
    colors = [_style.FHG_GREEN if d <= 0 else _style.FHG_ORANGE for d in deltas]
    ax.barh(labels, deltas, color=colors, height=0.5, edgecolor="white")
    for i, (lab, d, sid, node) in enumerate(rows):
        ax.text(d, i, f"  {d:+.1f}%  (node {node})", va="center",
                ha="left" if d >= 0 else "right", fontsize=7.5, color=_style.INK)
    ax.axvline(0, color=_style.INK_SOFT, lw=0.8)
    ax.set_xlabel("Endogenous TAC vs. best fixed siting [%]")
    ax.set_title("Value of free TES/WP siting", fontsize=9.5, pad=6)
    ax.grid(axis="x")
    # Labels sit just past each bar's tip (outside, away from zero) -- give the
    # axes enough left/right margin so a long label on the most extreme bar
    # (e.g. a large negative delta) doesn't run past the axes edge and
    # overlap the y-axis category ticks (observed for the Memmingen row when
    # margins were left at the matplotlib default).
    lo, hi = min(deltas + [0.0]), max(deltas + [0.0])
    span = max(hi - lo, 1.0)
    ax.set_xlim(lo - 0.55 * span, hi + 0.55 * span)
    _style.save(fig, "fig_F6_siting")


# ═════════════════════════════════════════════════════════════════════════════
# F7 — sensitivity tornado (spec §7)
# ═════════════════════════════════════════════════════════════════════════════
def build_f7() -> None:
    print("F7 — sensitivity tornado:")
    sp = OUT / "sensitivity.csv"
    if not sp.exists():
        print("  [SKIP] F7: sensitivity.csv missing"); return
    d = pd.read_csv(sp)
    d["delta_pct"] = pd.to_numeric(d.get("delta_pct"), errors="coerce")
    d = d.dropna(subset=["delta_pct"])
    if d.empty:
        print("  [SKIP] F7: sensitivity.csv has no delta_pct results yet "
              "(runs recorded solve time/status only — re-run sensitivity.py "
              "with TAC capture)")
        return
    _style.apply_rcparams()
    nets = d["network"].unique()
    fig, axes = plt.subplots(1, len(nets), figsize=(_style.COL_DOUBLE_IN, 3.6),
                             squeeze=False)
    for ax, net in zip(axes[0], nets):
        sub = d[d.network == net]
        g = sub.groupby("param")["delta_pct"].agg(["min", "max"])
        g["span"] = g["max"] - g["min"]
        g = g.sort_values("span")
        y = np.arange(len(g))
        ax.barh(y, g["max"] - g["min"], left=g["min"], color=_style.FHG_BLUE,
                height=0.6, edgecolor="white")
        ax.axvline(0, color=_style.INK_SOFT, lw=0.8)
        ax.set_yticks(y, g.index, fontsize=7.5)
        ax.set_xlabel("TAC change [%]")
        ax.set_title(str(net), fontsize=9)
        ax.grid(axis="x")
    fig.suptitle("Sensitivity of total annual cost (spec §7 parameter set)",
                 fontsize=10.5, y=1.0)
    _style.save(fig, "fig_F7_tornado")


# ═════════════════════════════════════════════════════════════════════════════
# F8 — spatial T/p profile along a trunk (result + L3+ monotonicity check)
# ═════════════════════════════════════════════════════════════════════════════
_TRUNK = {
    # Confirmed via scripts/paper_2/figures/trunk_path.py (algorithmic longest
    # plant->consumer path, spec F8). SB: unique candidate, 8570 m, dT_pipe
    # 1.78 K. MM: j_14 picked over the near-tied j_15 branch (3120 m vs 3065 m,
    # <2% apart) — j_14 serves 2 metered zones vs j_15's 1, and j_15's larger
    # dT_pipe (0.75 vs 0.44 K) is driven by an outlier u_value_supply_w_per_m_k
    # on pipe j13_to_j15 (1.31 W/m/K vs 0.28-0.32 on every other Memmingen
    # pipe) rather than genuine trunk length — worth a DXF/as-built sanity
    # check separately, not treated as the representative case here.
    "SB": ("SB-S1-HK0", ["j_hkw", "j_pss", "j_hws", "j_don_bosco"]),
    "MM": ("MM-S1-HK0", ["j_1", "j_2", "j_3", "j_9", "j_10", "j_11", "j_12", "j_13", "j_14"]),
}
# Secondary pump/generator stations along each trunk (network_manager.py's
# _link_pressure_propagation: these nodes carry a local asset, e.g. Stadtbach's
# HWS_BOILER at j_pss or Memmingen's hp_main/eboiler_main at j_12, and are
# deliberately modeled with a FREE, pump-boosted supply pressure/temperature
# rather than one propagated from the upstream pipe -- confirmed 2026-07-19 by
# checking configs/*/*.yaml asset attachments directly, not a plotting bug.
# A "monotone fall" is only a valid expectation WITHIN each station-to-station
# segment, not across one -- see the 2026-07-19 investigation in the
# Implementation Statement (F8 entry) for the full trace.
_TRUNK_STATIONS = {"SB": {"j_pss"}, "MM": {"j_12"}}


def _pick_col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None


def build_f8() -> None:
    print("F8 — spatial T/p profile:")
    series = []
    for net, (sid, trunk) in _TRUNK.items():
        pq = OUT / sid / "nodes_state_hourly.parquet"
        if not pq.exists():
            print(f"  [SKIP] F8 {net}: {sid}/nodes_state_hourly.parquet missing")
            continue
        df = pd.read_parquet(pq)
        tcol = _pick_col(df, "T_supply_c", "T_supply_C", "T_supply")
        pcol = _pick_col(df, "P_bar", "p_supply_bar", "P_supply_bar")
        if tcol is None or "node_id" not in df.columns:
            print(f"  [SKIP] F8 {net}: no T_supply/node_id columns")
            continue
        df[tcol] = pd.to_numeric(df[tcol], errors="coerce")
        g = df[df.node_id.isin(trunk)].groupby("node_id")[tcol].mean().reindex(trunk)
        p = None
        if pcol:
            df[pcol] = pd.to_numeric(df[pcol], errors="coerce")
            p = df[df.node_id.isin(trunk)].groupby("node_id")[pcol].mean().reindex(trunk)
        if g.isna().all():
            print(f"  [SKIP] F8 {net}: trunk nodes absent / no incumbent (O-6)")
            continue
        series.append((net, NET_LABEL[net], trunk, g, p))
    if not series:
        return
    _style.apply_rcparams()
    # two measures of different units → stacked rows sharing x, never a dual axis
    fig, axes = plt.subplots(2, len(series), figsize=(_style.COL_DOUBLE_IN, 4.4),
                             squeeze=False, sharex="col")
    for j, (net, label, trunk, tprof, pprof) in enumerate(series):
        x = np.arange(len(trunk))
        station_x = [k for k, nid in enumerate(trunk) if nid in _TRUNK_STATIONS.get(net, set())]
        ax_t, ax_p = axes[0][j], axes[1][j]
        for sx in station_x:
            ax_t.axvspan(sx - 0.4, sx + 0.4, color=_style.FHG_BLUE, alpha=0.10, lw=0)
        ax_t.plot(x, tprof.values, marker="o", ms=6, lw=2, color=_style.FHG_ORANGE)
        ax_t.set_title(label, fontsize=9)
        ax_t.grid(axis="y")
        if j == 0:
            ax_t.set_ylabel("T$_{supply}$ [°C]")
        if pprof is not None and not pprof.isna().all():
            for sx in station_x:
                ax_p.axvspan(sx - 0.4, sx + 0.4, color=_style.FHG_BLUE, alpha=0.10, lw=0)
            ax_p.plot(x, pprof.values, marker="s", ms=5, lw=2, color=_style.FHG_BLUE)
        else:
            ax_p.text(0.5, 0.5, "no pressure data", transform=ax_p.transAxes,
                      ha="center", color=_style.INK_MUTED, fontsize=7.5)
        ax_p.set_xticks(x, trunk, rotation=45, ha="right", fontsize=6.8)
        ax_p.grid(axis="y")
        if j == 0:
            ax_p.set_ylabel("p$_{supply}$ [bar]")
    fig.suptitle("Supply temperature and pressure along the main trunk\n"
                 "(shaded = secondary pump/generator station, free setpoint — "
                 "monotone fall expected only within each segment)",
                 fontsize=9.5, y=1.03)
    fig.subplots_adjust(wspace=0.22, hspace=0.32)
    _style.save(fig, "fig_F8_spatial_profile")


# ═════════════════════════════════════════════════════════════════════════════
# F9 — TES state-of-charge, winter + transition week
# ═════════════════════════════════════════════════════════════════════════════
_WEEKS = [("Winter week", "2025-01-13"), ("Transition week", "2025-04-14")]


def build_f9() -> None:
    print("F9 — TES SOC time series:")
    df = _kpis()
    if df is None:
        return
    df = _annotate_net(df)
    picks = []
    for net in ["SB", "MM"]:
        best = _best_row(df, net, require_tes=True)
        if best is None:
            print(f"  [SKIP] F9 {net}: no converged TES scenario")
            continue
        sid = best["scenario_id"]
        d = OUT / sid / "dispatch_hourly.csv"
        if not d.exists():
            print(f"  [SKIP] F9 {net}: {sid}/dispatch_hourly.csv missing")
            continue
        emax = float(best.get("E_TES_MWh", np.nan))
        picks.append((NET_LABEL[net], sid, d, emax))
    if not picks:
        return
    _style.apply_rcparams()
    fig, axes = plt.subplots(1, 2, figsize=(_style.COL_DOUBLE_IN, 3.2), sharey=True)
    colors = {"Stadtbach": _style.FHG_GREEN, "Memmingen": _style.FHG_BLUE}
    for ax, (wlabel, start) in zip(axes, _WEEKS):
        t0 = pd.Timestamp(start); t1 = t0 + pd.Timedelta(days=7)
        for label, sid, path, emax in picks:
            dd = pd.read_csv(path, parse_dates=["timestamp"])
            w = dd[(dd.timestamp >= t0) & (dd.timestamp < t1)]
            if w.empty or "SOC_MWh" not in w:
                continue
            soc = pd.to_numeric(w["SOC_MWh"], errors="coerce")
            y = soc / emax * 100 if emax and not np.isnan(emax) and emax > 0 else soc
            ax.plot(w.timestamp, y, lw=1.8, color=colors[label],
                    label=f"{label} ({sid})")
        ax.set_title(wlabel, fontsize=9)
        ax.grid(axis="y")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    axes[0].set_ylabel("TES state of charge [% of $E_{max}$]")
    h, l = axes[0].get_legend_handles_labels()
    if h:
        fig.legend(h, l, loc="lower center", ncol=2, fontsize=7.5,
                   bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("TES state of charge — best scenario per network", fontsize=10.5, y=1.0)
    fig.subplots_adjust(bottom=0.2, wspace=0.08)
    _style.save(fig, "fig_F9_soc")


_ALL = {"F3": build_f3, "F4": build_f4, "F5": build_f5, "F6": build_f6,
        "F7": build_f7, "F8": build_f8, "F9": build_f9}

if __name__ == "__main__":
    which = [a.upper() for a in sys.argv[1:] if a.upper() in _ALL] or list(_ALL)
    for key in which:
        try:
            _ALL[key]()
        except Exception as exc:  # noqa: BLE001 — one broken figure must not kill the set
            print(f"  [FAIL] {key}: {type(exc).__name__}: {exc}")
