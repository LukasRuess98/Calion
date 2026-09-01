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
# Ceteris-paribus fixed-siting family per network (vary heat-curve stage only).
# MM-S1 = TES at central node (j_9); SB-S2 = TES at WP node (j_man). Both invest
# TES across all three HK stages, so the coupling is visible. (Design 2026-08-30.)
_F4_FAMILY = {"MM": "S1", "SB": "S2"}
_STAGES = ["HK0", "HK1", "HK2"]
# Network identity colour, fixed across the whole figure set (dataviz: colour
# follows the entity). Memmingen = Fraunhofer blue, Stadtbach = Fraunhofer green.
NET_COLOR = {"MM": _style.FHG_BLUE, "SB": _style.FHG_GREEN}
# Three coupled measures, own y-scale each (no dual axis). m³ is the primary
# storage quantity (user decision 2026-08-30); TAC in k€/a; COP dimensionless.
_F4_COLS = [
    ("V_TES_m3", "TES volume [m$^3$]", 1.0),
    ("COP_annual_mean", "COP [–]", 1.0),
    ("TAC_eur_per_a", "TAC [k€/a]", 1e-3),
]


def build_f4() -> None:
    print("F4 - heat-curve -> COP -> cost trajectory (electrification-dependent):")
    df = _kpis()
    if df is None:
        return
    df = _annotate_net(df)
    _style.apply_rcparams()
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(_style.COL_DOUBLE_IN, 3.6))
    any_data = False
    for net in ["MM", "SB"]:
        fam = _F4_FAMILY[net]
        color = NET_COLOR[net]
        sub = df[(df.net == net) & (df.fam == fam) & (df.stage.isin(_STAGES))]
        sub = sub.set_index("stage").reindex(_STAGES)
        cop = pd.to_numeric(sub["COP_annual_mean"], errors="coerce").to_numpy(float)
        tac = pd.to_numeric(sub["TAC_eur_per_a"], errors="coerce").to_numpy(float)
        elec = pd.to_numeric(sub["electrification_pct"], errors="coerce").mean()
        if np.all(np.isnan(cop)):
            continue
        any_data = True
        tac_idx = tac / tac[0] * 100.0            # index to HK0 = 100 %
        # LEFT: the universal physics — COP rises as the curve is lowered
        axL.plot(_STAGES, cop, "-o", ms=8, lw=2, color=color, label=NET_LABEL[net])
        # RIGHT: the economic consequence — trajectory in (COP, indexed-TAC) space
        axR.plot(cop, tac_idx, "-o", ms=8, lw=2, color=color,
                 label=f"{NET_LABEL[net]}  ({elec:.0f}% electrified)")
        for k, st in enumerate(_STAGES):
            axR.annotate(st, (cop[k], tac_idx[k]), textcoords="offset points",
                         xytext=(5, 5), fontsize=6.8, color=_style.INK_SOFT)
    axL.set_xlabel("Heat-curve stage  (HK0 → HK2 = lower supply temp.)", fontsize=8.5)
    axL.set_ylabel("Annual mean COP [–]")
    axL.set_title("Physics: lower curve → higher COP", fontsize=9)
    axL.grid(axis="y"); axL.legend(fontsize=7.5, loc="upper left")
    axR.axhline(100, color=_style.INK_MUTED, lw=0.8, ls=(0, (4, 3)))
    axR.set_xlabel("Annual mean COP [–]")
    axR.set_ylabel("Total annual cost  [% of HK0]")
    axR.set_title("Economics: the benefit scales with electrification", fontsize=9)
    axR.grid(axis="y"); axR.legend(fontsize=7.5, loc="lower left")
    fig.suptitle("Lowering the heat curve always raises COP, but only pays off "
                 "where the heat pump carries real load", fontsize=9.5, y=1.01)
    fig.subplots_adjust(wspace=0.3, bottom=0.16)
    if not any_data:
        print("  [PARTIAL] F4: reference families lack COP/TAC data")
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
    # Cost components use the Paper 1 palette (navy/teal/amber) for cross-paper
    # visual consistency (user request 2026-08-30) — distinct from the network hues.
    cats = [("CAPEX (annualised)", _style.P1_NAVY),
            ("Energy OPEX", _style.P1_TEAL),
            ("CO$_2$ cost", _style.P1_AMBER)]
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


_F6_ENUM = {"MM": "MM-S4-HK2", "SB": "SB-S6-HK2"}   # HK2 free-siting enumeration
# candidate node order per network (trunk / distance-ish order for readability)
_F6_NODES = {"MM": ["j_9", "j_12", "j_13", "j_1", "j_3", "j_5"],
             "SB": ["j_hkw", "j_man", "j_ost", "j_pss", "j_psw"]}
_F6_CLIP = 25.0   # colour-scale cap: % above the best siting (bad cells saturate)


def build_f6() -> None:
    print("F6 — siting landscape (TAC over candidate HP x TES nodes):")
    df = _kpis_with_enum()
    if df is None:
        return
    _style.apply_rcparams()
    fig, axes = plt.subplots(1, 2, figsize=(_style.COL_DOUBLE_IN, 3.9), squeeze=False)
    cmap = plt.get_cmap("YlGnBu")
    im = None
    for ax, net in zip(axes[0], ["MM", "SB"]):
        base = _F6_ENUM[net]
        e = df[df.scenario_id.str.startswith(base + "__hp_")].copy()
        m = e["scenario_id"].str.extract(rf'{base}__hp_(?P<hp>.+?)__tes_(?P<tes>.+)')
        e = pd.concat([e, m], axis=1)
        e["TAC"] = pd.to_numeric(e["TAC_eur_per_a"], errors="coerce")
        e = e[e["TAC"] > 1.0]
        nodes = _F6_NODES[net]
        tmin = e["TAC"].min()
        e["pct"] = (e["TAC"] / tmin - 1.0) * 100.0
        grid = e.pivot_table(index="tes", columns="hp", values="pct").reindex(
            index=nodes, columns=nodes)
        im = ax.imshow(grid.values, origin="lower", cmap=cmap, vmin=0, vmax=_F6_CLIP,
                       aspect="equal")
        # star the optimum (0% cell)
        opt = e.loc[e["pct"].idxmin()]
        oi, oj = nodes.index(opt["tes"]), nodes.index(opt["hp"])
        ax.scatter([oj], [oi], marker="*", s=240, color="white",
                   edgecolor=_style.INK, linewidth=0.8, zorder=5)
        ax.set_xticks(range(len(nodes)), nodes, rotation=45, ha="right", fontsize=7)
        ax.set_yticks(range(len(nodes)), nodes, fontsize=7)
        ax.set_xlabel("heat-pump node")
        if net == "MM":
            ax.set_ylabel("TES node")
        worst = e["TAC"].max() / tmin
        ax.set_title(f"{NET_LABEL[net]}  (worst siting {worst:.0f}× best)",
                     fontsize=9, color=NET_COLOR[net])
    cbar = fig.colorbar(im, ax=axes[0], shrink=0.82, pad=0.02,
                        label="TAC above best siting [%]  (capped at 25)")
    fig.suptitle("Siting is decisive: total annual cost over every candidate "
                 "heat-pump × storage node  (star = optimum)", fontsize=9.5, y=1.02)
    _style.save(fig, "fig_F6_siting")


def _kpis_with_enum() -> "pd.DataFrame | None":
    """KPIs INCLUDING the __hp__tes enumeration rows (which _kpis() drops)."""
    if not KPI.exists():
        print(f"  [SKIP] {KPI} missing"); return None
    df = pd.read_csv(KPI)
    return df[~df["scenario_id"].str.contains("TEST|DIAG|ZZ", na=False)].copy()


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
    nets = list(d["network"].unique())
    # symmetric x-limit so both panels share a readable scale per network
    fig, axes = plt.subplots(1, len(nets), figsize=(_style.COL_DOUBLE_IN, 3.4),
                             squeeze=False)
    C_UP, C_DOWN = _style.P1_AMBER, _style.P1_TEAL   # cost increase / decrease
    for ax, net in zip(axes[0], nets):
        sub = d[d.network == net]
        g = sub.groupby("param")["delta_pct"].agg(["min", "max"])
        g["span"] = g["max"] - g["min"]
        g = g.sort_values("span")                    # widest span at TOP (drawn last)
        y = np.arange(len(g))
        xmax = float(np.abs(g[["min", "max"]].to_numpy()).max()) * 1.28
        for i, (lo, hi) in enumerate(zip(g["min"], g["max"])):
            # split the bar at zero: cost-reduction half (teal) | cost-increase half (amber)
            ax.barh(i, min(hi, 0) - lo, left=lo, color=C_DOWN, height=0.62,
                    edgecolor="white", linewidth=0.8)
            ax.barh(i, hi - max(lo, 0), left=max(lo, 0), color=C_UP, height=0.62,
                    edgecolor="white", linewidth=0.8)
            ax.text(lo - xmax * 0.015, i, f"{lo:+.1f}", va="center", ha="right",
                    fontsize=7, color=_style.INK_SOFT)
            ax.text(hi + xmax * 0.015, i, f"{hi:+.1f}", va="center", ha="left",
                    fontsize=7, color=_style.INK_SOFT)
        ax.axvline(0, color=_style.INK, lw=0.9, zorder=1)
        ax.set_yticks(y, g.index, fontsize=8)
        ax.set_xlim(-xmax, xmax)
        ax.set_xlabel(r"$\Delta$ total annual cost  [%]")
        ax.set_title(str(net), fontsize=9.5, color=NET_COLOR.get(
            "MM" if net == "Memmingen" else "SB", _style.INK))
        ax.grid(axis="x", zorder=0)
        ax.tick_params(axis="y", length=0)
    # shared direction legend (proxy handles)
    import matplotlib.patches as mpatches
    fig.legend([mpatches.Patch(color=C_DOWN), mpatches.Patch(color=C_UP)],
               ["cost decrease", "cost increase"], loc="lower center", ncol=2,
               fontsize=7.5, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("Sensitivity of total annual cost to economic assumptions "
                 "(±30% prices, ±50% CO$_2$, ±2 pp discount rate)",
                 fontsize=9.5, y=1.01)
    fig.subplots_adjust(bottom=0.2, wspace=0.42)
    _style.save(fig, "fig_F7_tornado")


# ═════════════════════════════════════════════════════════════════════════════
# F8 — spatial T/p profile along a trunk (result + L3+ monotonicity check)
# ═════════════════════════════════════════════════════════════════════════════
_TRUNK = {
    # Confirmed via scripts/paper_2/figures/trunk_path.py (algorithmic longest
    # plant->consumer path, spec F8). SB: unique candidate, 8570 m, dT_pipe
    # 1.78 K.
    # MM (2026-08-07): re-derived on the DXF-correct topology + j_9 producer.
    # User-chosen = the algorithmic LONGEST-by-cumulative-length path,
    # j_9 -> j_3 -> j_2 -> j_1 (2535 m; the near-tied alternative
    # j_9->j_10->j_11->j_13->j_15 at 1765 m had higher cumulative dT_pipe but is
    # shorter). This trunk does NOT pass through the secondary producer j_12
    # (which sits on the parallel j_9->j_10->j_11->j_12 branch), so it is a clean
    # single-source monotone profile with no mid-trunk pump station.
    "SB": ("SB-S1-HK0", ["j_hkw", "j_pss", "j_hws", "j_don_bosco"]),
    "MM": ("MM-S1-HK0", ["j_9", "j_3", "j_2", "j_1"]),
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
_TRUNK_STATIONS = {"SB": {"j_pss"}, "MM": set()}  # MM trunk j_9->j_3->j_2->j_1 has no mid-trunk station (j_12 is off the parallel branch)


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
        ax_t.plot(x, tprof.values, marker="o", ms=6, lw=2, color=_style.P1_RED)
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


_F9_WEEK = ("2025-01-13", 7)   # representative winter week


def _f9_pick(df: pd.DataFrame, fams: list[str], net: str):
    """Lowest-TAC scenario in `fams` for `net` that built a TES and has dispatch."""
    p = [_parse_id(s) for s in df["scenario_id"]]
    sub = df.assign(net=[x[0] for x in p], fam=[x[1] for x in p])
    sub = sub[(sub.net == net) & (sub.fam.isin(fams))].copy()
    sub["TAC"] = pd.to_numeric(sub["TAC_eur_per_a"], errors="coerce")
    sub["V"] = pd.to_numeric(sub.get("V_TES_m3"), errors="coerce").fillna(0)
    sub = sub[(sub.TAC > 1.0) & (sub.V > 0)].sort_values("TAC")
    for _, r in sub.iterrows():
        if (OUT / r["scenario_id"] / "dispatch_hourly.csv").exists():
            return r
    return None


def build_f9() -> None:
    print("F9 — TES SOC: fixed vs endogenous siting:")
    df = _kpis_with_enum()
    if df is None:
        return
    _style.apply_rcparams()
    fig, axes = plt.subplots(1, 2, figsize=(_style.COL_DOUBLE_IN, 3.3), sharey=True)
    t0 = pd.Timestamp(_F9_WEEK[0]); t1 = t0 + pd.Timedelta(days=_F9_WEEK[1])
    any_data = False
    for ax, net in zip(axes, ["MM", "SB"]):
        variants = [("best fixed siting", _FIXED_FAMS[net], (0, (5, 2))),
                    ("best endogenous siting", _ENDOG_FAMS[net], "-")]
        for mode, fams, ls in variants:
            r = _f9_pick(df, fams, net)
            if r is None:
                continue
            emax = float(pd.to_numeric(r.get("E_TES_MWh"), errors="coerce") or np.nan)
            dd = pd.read_csv(OUT / r["scenario_id"] / "dispatch_hourly.csv",
                             parse_dates=["timestamp"])
            w = dd[(dd.timestamp >= t0) & (dd.timestamp < t1)]
            if w.empty or "SOC_MWh" not in w:
                continue
            soc = pd.to_numeric(w["SOC_MWh"], errors="coerce")
            y = soc / emax * 100 if emax and emax > 0 else soc
            ax.plot(w.timestamp, y, lw=1.8, color=NET_COLOR[net], ls=ls,
                    label=f"{mode}")
            any_data = True
        ax.set_title(NET_LABEL[net], fontsize=9.5, color=NET_COLOR[net])
        ax.grid(axis="y")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.legend(fontsize=7.5, loc="upper right")
    axes[0].set_ylabel("TES state of charge [% of $E_{max}$]")
    if not any_data:
        print("  [PARTIAL] F9: no fixed/endogenous TES dispatch found")
    fig.suptitle("Storage cycling — fixed vs. endogenous siting (winter week)",
                 fontsize=10, y=1.0)
    fig.subplots_adjust(bottom=0.16, wspace=0.08)
    _style.save(fig, "fig_F9_soc")


# ═════════════════════════════════════════════════════════════════════════════
# F-ELEC — electrification spine (NEW centrepiece): cost / CO2 / COP vs HP penetration
# ═════════════════════════════════════════════════════════════════════════════
_ELEC_NETS = [("memmingen", "MM"), ("stadtbach", "SB")]


def build_felec() -> None:
    print("F-ELEC - electrification sweep (cost / CO2 / COP vs HP penetration):")
    frames = []
    for net_full, net in _ELEC_NETS:
        p = _ROOT / "results" / f"elec_sweep_{net_full}.csv"
        if p.exists():
            d = pd.read_csv(p)
            # drop garbage incumbents (maxtimelimit points with absurd LCOH, e.g.
            # SB 160 MW HP came back at LCOH 393 €/MWh) — flagged, need re-solve
            lc = pd.to_numeric(d.get("LCOH_eur_per_MWh"), errors="coerce")
            bad = lc > 100.0
            if bad.any():
                print(f"  [FILTER] {net}: dropped {int(bad.sum())} garbage-incumbent "
                      f"level(s) (LCOH>100) — need re-solve")
            d = d[~bad].copy()
            d["net"] = net
            frames.append(d)
        else:
            print(f"  [PENDING] {p.name} not built yet")
    if not frames:
        print("  [SKIP] no electrification-sweep data yet")
        return
    _style.apply_rcparams()
    cols = [("LCOH_eur_per_MWh", "LCOH [€/MWh]"),
            ("co2_t_per_a", "CO$_2$ [t/a]"),
            ("COP_annual_mean", "Annual mean COP [–]")]
    nets = [f for f in frames]
    fig, axes = plt.subplots(len(nets), 3, figsize=(_style.COL_DOUBLE_IN, 2.4 * len(nets)),
                             squeeze=False)
    for i, d in enumerate(nets):
        net = d["net"].iloc[0]
        color = NET_COLOR[net]
        d = d.sort_values("level_frac")
        x = pd.to_numeric(d["level_frac"], errors="coerce") * 100.0
        for j, (col, ylab) in enumerate(cols):
            ax = axes[i][j]
            y = pd.to_numeric(d.get(col), errors="coerce")
            ax.plot(x, y, "-o", ms=7, lw=2, color=color)
            ax.set_ylabel(ylab, fontsize=8)
            ax.grid(axis="y")
            ax.set_xticklabels([] if i < len(nets) - 1 else ax.get_xticks())
            if i == 0:
                ax.set_title(["Cost", "Emissions", "Efficiency"][j], fontsize=9)
        axes[i][0].annotate(NET_LABEL[net], xy=(-0.4, 0.5), xycoords="axes fraction",
                            rotation=90, va="center", ha="center", fontsize=9.5,
                            fontweight="bold", color=color)
    axes[-1][1].set_xlabel("Heat-pump penetration  [% of peak heat demand]", fontsize=8.5)
    fig.suptitle("Electrification spine: cost, emissions and efficiency vs heat-pump "
                 "penetration (fixed siting, HK2)", fontsize=9.5, y=1.01)
    fig.subplots_adjust(hspace=0.16, wspace=0.32, left=0.11)
    _style.save(fig, "fig_Felec_electrification")


_ALL = {"F3": build_f3, "F4": build_f4, "F5": build_f5, "F6": build_f6,
        "F7": build_f7, "F8": build_f8, "F9": build_f9, "FELEC": build_felec}

if __name__ == "__main__":
    which = [a.upper() for a in sys.argv[1:] if a.upper() in _ALL] or list(_ALL)
    for key in which:
        try:
            _ALL[key]()
        except Exception as exc:  # noqa: BLE001 — one broken figure must not kill the set
            print(f"  [FAIL] {key}: {type(exc).__name__}: {exc}")
