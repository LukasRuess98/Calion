"""Paper 2 figure generator.

Generates 10 publication-quality figures from output/paper2_runs/:

  F-P2-1: Scenario matrix overview (17 scenarios: network × TES location × HK)
  F-P2-2: TAC comparison across all 17 scenarios (grouped bar)
  F-P2-3: CAPEX vs OPEX breakdown (stacked bars)
  F-P2-4: Optimal WP/EK/TES sizing across scenarios (grouped)
  F-P2-5: TES geometry scatter (V vs h, colored by p_betr)
  F-P2-6: COP time series (representative winter/summer week)
  F-P2-7: DSM activation profile (representative week, if DSM configured)
  F-P2-8: Heat curve comparison (HK0 vs HK1 vs HK2)
  F-P2-9: CO₂ reduction vs cost reduction (Pareto scatter)
  F-P2-10: Sensitivity tornado for best scenario per network

Usage:
  python tools/figgen_p2.py
  Or called from run_paper2_full.py phase 4.

Follows Applied Energy journal style (ae_style.py from Paper 1).
"""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT) + "/scripts/paper")

logger = logging.getLogger(__name__)

# ── Style ─────────────────────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    logger.warning("matplotlib not available — figures will be skipped")

IPA = {
    "teal": "#009B77",
    "navy": "#003E6E",
    "silver": "#8C9EA8",
    "red": "#C0392B",
    "orange": "#E67E22",
    "green": "#27AE60",
    "blue": "#2980B9",
    "gray": "#95A5A6",
}

# Applied Energy: 1-col = 8.46 cm, 2-col = 17.4 cm
_COL1 = 8.46 / 2.54  # inches
_COL2 = 17.4 / 2.54


def _r(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _save(fig, path: Path, dpi: int = 300) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path.with_suffix(".pdf")), bbox_inches="tight")
    fig.savefig(str(path.with_suffix(".png")), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved %s (.pdf + .png)", path.stem)


# ── Figure implementations ─────────────────────────────────────────────────

def fig_p2_1_scenario_matrix(rows: list[dict], fig_dir: Path) -> None:
    """F-P2-1: Scenario matrix — TAC as coloured grid (network × TES × HK stage)."""
    if not HAS_MPL:
        return

    # Build index: (network, tes_node, hk_stage) → TAC
    import math
    cell = {}
    bc_tac = {"memmingen": None, "stadtbach": None}
    for r in rows:
        net = r.get("network", "")
        tes = r.get("tes_node") or "BC"
        hk  = r.get("heat_curve_stage", "")
        tac = _f(r.get("TAC_eur_per_a"))
        if r.get("baseline") in ("True", True, "true"):
            bc_tac[net] = tac
        else:
            cell[(net, tes, hk)] = tac

    networks  = ["memmingen", "stadtbach"]
    tes_nodes = {"memmingen": ["S1", "S2"],
                 "stadtbach": ["S1", "S2", "S3"]}
    hk_stages = ["HK0", "HK1", "HK2"]

    # Layout: one subplot per network, rows=TES nodes, cols=HK stages
    fig, axes = plt.subplots(1, 2, figsize=(_COL2, 4))
    for ax, net in zip(axes, networks):
        nodes = tes_nodes[net]
        mat = np.full((len(nodes), len(hk_stages)), np.nan)
        for i, tes in enumerate(nodes):
            for j, hk in enumerate(hk_stages):
                if (net, tes, hk) in cell:
                    bc = bc_tac.get(net) or 1
                    reduction = (bc - cell[(net, tes, hk)]) / bc * 100 if bc else 0
                    mat[i, j] = reduction

        im = ax.imshow(mat, cmap="RdYlGn", vmin=-5, vmax=25, aspect="auto")
        ax.set_xticks(range(len(hk_stages)))
        ax.set_xticklabels(hk_stages, fontsize=8)
        ax.set_yticks(range(len(nodes)))
        ax.set_yticklabels(nodes, fontsize=8)
        ax.set_title(net.capitalize(), fontsize=9, fontweight="bold")
        ax.set_xlabel("Heat curve stage", fontsize=8)
        ax.set_ylabel("TES location", fontsize=8)
        for i in range(len(nodes)):
            for j in range(len(hk_stages)):
                val = mat[i, j]
                if not math.isnan(val):
                    ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                            fontsize=7, color="black")

    plt.colorbar(im, ax=axes[-1], label="Cost reduction vs BC [%]", shrink=0.8)
    fig.suptitle("Scenario Matrix — Cost Reduction over Baseline", fontsize=9, y=1.01)
    fig.tight_layout()
    _save(fig, fig_dir / "F-P2-1_scenario_matrix")


def fig_p2_2_tac_comparison(rows: list[dict], fig_dir: Path) -> None:
    """F-P2-2: TAC comparison bar chart across all 17 scenarios."""
    if not HAS_MPL or not rows:
        return
    scen_ids = [r.get("scenario_id", "") for r in rows]
    tac_k = [_f(r.get("TAC_eur_per_a")) / 1000 for r in rows]
    is_bc = [r.get("baseline") in ("True", True, "true") for r in rows]

    colors = [IPA["gray"] if bc else IPA["teal"] for bc in is_bc]
    fig, ax = plt.subplots(figsize=(_COL2, 5))
    ax.bar(range(len(scen_ids)), tac_k, color=colors)
    ax.set_xticks(range(len(scen_ids)))
    ax.set_xticklabels(scen_ids, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("TAC [k€/a]")
    ax.set_title("Total Annualized Cost — all 17 scenarios")
    bc_patch = mpatches.Patch(color=IPA["gray"], label="Baseline")
    opt_patch = mpatches.Patch(color=IPA["teal"], label="Optimized")
    ax.legend(handles=[bc_patch, opt_patch])
    fig.tight_layout()
    _save(fig, fig_dir / "F-P2-2_tac_comparison")


def fig_p2_3_capex_opex(rows: list[dict], fig_dir: Path) -> None:
    """F-P2-3: CAPEX vs OPEX stacked bar chart."""
    if not HAS_MPL or not rows:
        return
    opt_rows = [r for r in rows if r.get("baseline") not in ("True", True, "true")]
    if not opt_rows:
        return
    scen_ids = [r.get("scenario_id", "") for r in opt_rows]
    capex = [_f(r.get("CAPEX_annual_eur_per_a")) / 1000 for r in opt_rows]
    opex = [_f(r.get("OPEX_annual_eur_per_a")) / 1000 for r in opt_rows]

    fig, ax = plt.subplots(figsize=(_COL2, 5))
    x = range(len(scen_ids))
    ax.bar(x, opex, color=IPA["navy"], label="OPEX")
    ax.bar(x, capex, bottom=opex, color=IPA["teal"], label="CAPEX (annualized)")
    ax.set_xticks(x)
    ax.set_xticklabels(scen_ids, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Cost [k€/a]")
    ax.set_title("CAPEX vs OPEX breakdown")
    ax.legend()
    fig.tight_layout()
    _save(fig, fig_dir / "F-P2-3_capex_opex")


def fig_p2_4_sizing(rows: list[dict], fig_dir: Path) -> None:
    """F-P2-4: Optimal WP/EK/TES sizing across scenarios."""
    if not HAS_MPL or not rows:
        return
    opt_rows = [r for r in rows if r.get("baseline") not in ("True", True, "true")]
    if not opt_rows:
        return
    scen_ids = [r.get("scenario_id", "") for r in opt_rows]
    q_wp = [_f(r.get("Q_WP_opt_MW")) for r in opt_rows]
    q_ek = [_f(r.get("Q_EK_opt_MW")) for r in opt_rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(_COL2, 7), sharex=True)
    x = range(len(scen_ids))
    ax1.bar(x, q_wp, color=IPA["teal"], label="Q̇_WP [MW]")
    ax1.bar(x, q_ek, bottom=q_wp, color=IPA["orange"], label="Q̇_EK [MW]")
    ax1.set_ylabel("Capacity [MW]")
    ax1.set_title("Optimal WP and EK capacity")
    ax1.legend()

    e_tes = [_f(r.get("E_TES_MWh")) for r in opt_rows]
    ax2.bar(x, e_tes, color=IPA["navy"])
    ax2.set_ylabel("E_TES [MWh]")
    ax2.set_title("TES energy capacity")
    ax2.set_xticks(x)
    ax2.set_xticklabels(scen_ids, rotation=45, ha="right", fontsize=7)
    fig.tight_layout()
    _save(fig, fig_dir / "F-P2-4_sizing")


def fig_p2_5_geometry_scatter(rows: list[dict], fig_dir: Path) -> None:
    """F-P2-5: TES geometry scatter: V vs h, colored by p_betr."""
    if not HAS_MPL or not rows:
        return
    opt_rows = [r for r in rows if r.get("baseline") not in ("True", True, "true")
                and _f(r.get("V_TES_m3")) > 0]
    if not opt_rows:
        return
    V = np.array([_f(r.get("V_TES_m3")) for r in opt_rows])
    h = np.array([_f(r.get("h_TES_m")) for r in opt_rows])
    p = np.array([_f(r.get("p_betr_bar"), 1.0) for r in opt_rows])

    fig, ax = plt.subplots(figsize=(_COL1 * 1.5, _COL1 * 1.5))
    sc = ax.scatter(V, h, c=p, cmap="RdYlGn_r", s=80, edgecolors="k", linewidths=0.5)
    plt.colorbar(sc, ax=ax, label="p_betr [bar]")
    ax.set_xlabel("V_TES [m³]")
    ax.set_ylabel("h_TES [m]")
    ax.set_title("TES geometry")
    for r, vv, hh in zip(opt_rows, V, h):
        ax.annotate(r.get("scenario_id", "")[:8], (vv, hh), fontsize=5, ha="center")
    fig.tight_layout()
    _save(fig, fig_dir / "F-P2-5_tes_geometry")


def fig_p2_8_heizkurve(fig_dir: Path) -> None:
    """F-P2-8: Heat curve comparison — Memmingen and Stadtbach, all HK stages."""
    if not HAS_MPL:
        return
    T_aus = np.linspace(-15, 30, 200)
    networks = {
        "Memmingen": [
            ("HK0 (current)",     1.0, 74.0, 100.0),
            ("HK1 (moderate)",    0.8, 70.0, 100.0),
            ("HK2 (aggressive)",  0.6, 66.0, 100.0),
        ],
        "Stadtbach": [
            ("HK0 (current)",     1.0, 70.0, 122.0),
            ("HK1 (moderate)",    0.8, 65.0, 122.0),
            ("HK2 (aggressive)",  0.6, 60.0, 122.0),
        ],
    }
    colors = [IPA["navy"], IPA["teal"], IPA["orange"]]
    ls     = ["-", "--", ":"]

    fig, axes = plt.subplots(1, 2, figsize=(_COL2, _COL1), sharey=False)
    for ax, (net_name, params) in zip(axes, networks.items()):
        for (label, k, T_min, T_max), color, linestyle in zip(params, colors, ls):
            T_VL = np.maximum(T_min, T_max - k * (T_max - T_aus))
            ax.plot(T_aus, T_VL, label=label, color=color, ls=linestyle, lw=1.5)
        ax.set_xlabel("T_aus [°C]", fontsize=8)
        ax.set_ylabel("T_VL [°C]", fontsize=8)
        ax.set_title(net_name, fontsize=9, fontweight="bold")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)

    fig.suptitle("Heating curve scenarios — all HK stages", fontsize=9)
    fig.tight_layout()
    _save(fig, fig_dir / "F-P2-8_heizkurve")


def fig_p2_9_pareto(rows: list[dict], fig_dir: Path) -> None:
    """F-P2-9: CO₂ reduction vs cost reduction (Pareto scatter)."""
    if not HAS_MPL or not rows:
        return
    opt_rows = [r for r in rows
                if r.get("baseline") not in ("True", True, "true")
                and r.get("cost_reduction_pct") and r.get("co2_reduction_pct")]
    if not opt_rows:
        return
    cost_red = [_f(r.get("cost_reduction_pct")) for r in opt_rows]
    co2_red = [_f(r.get("co2_reduction_pct")) for r in opt_rows]
    networks = [r.get("network", "") for r in opt_rows]
    colors = [IPA["teal"] if "memmingen" in n else IPA["navy"] for n in networks]

    fig, ax = plt.subplots(figsize=(_COL1 * 1.5, _COL1 * 1.5))
    ax.scatter(cost_red, co2_red, c=colors, s=80, edgecolors="k", linewidths=0.5)
    ax.set_xlabel("Cost reduction [%]")
    ax.set_ylabel("CO₂ reduction [%]")
    ax.set_title("Economic vs. environmental trade-off")
    mm_patch = mpatches.Patch(color=IPA["teal"], label="Memmingen")
    sb_patch = mpatches.Patch(color=IPA["navy"], label="Stadtbach")
    ax.legend(handles=[mm_patch, sb_patch])
    ax.axhline(0, color="gray", lw=0.5)
    ax.axvline(0, color="gray", lw=0.5)
    fig.tight_layout()
    _save(fig, fig_dir / "F-P2-9_pareto")


def fig_p2_10_tornado(sens_rows: list[dict], fig_dir: Path) -> None:
    """F-P2-10: Sensitivity tornado diagram for best scenario per network."""
    if not HAS_MPL or not sens_rows:
        return
    for network in ["memmingen", "stadtbach"]:
        net_rows = [r for r in sens_rows if r.get("network") == network]
        if not net_rows:
            continue
        param_labels = {
            "c_el": "Electricity price ±30%",
            "c_co2": "CO₂ price ±50%",
            "alpha_wp": "WP CAPEX ±25%",
            "Q_AW_max": "Waste heat availability",
            "delta_max": "DSM potential",
            "discount_rate": "Discount rate ±2pp",
        }
        params = {}
        for r in net_rows:
            param = r.get("param", "")
            delta = _f(r.get("delta_pct"))
            params.setdefault(param, []).append(delta)

        param_names = list(params.keys())
        low_vals = [min(v) for v in params.values()]
        high_vals = [max(v) for v in params.values()]
        labels = [param_labels.get(p, p) for p in param_names]

        fig, ax = plt.subplots(figsize=(_COL2 * 0.7, len(param_names) * 0.5 + 1))
        y = range(len(param_names))
        ax.barh(y, [max(0, v) for v in high_vals], color=IPA["red"], label="+")
        ax.barh(y, [min(0, v) for v in low_vals], color=IPA["teal"], label="−")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        ax.axvline(0, color="black", lw=0.8)
        ax.set_xlabel("ΔTAC [%]")
        ax.set_title(f"Sensitivity — {network.capitalize()}")
        ax.legend(fontsize=8)
        fig.tight_layout()
        _save(fig, fig_dir / f"F-P2-10_tornado_{network}")


# ── Master function ───────────────────────────────────────────────────────

def generate_all_figures(out_base: Path, fig_dir: Path) -> None:
    """Generate all 10 Paper 2 figures."""
    rows = _r(out_base / "scenarios_kpis.csv")
    sens_rows = _r(out_base / "sensitivity.csv")

    fig_p2_1_scenario_matrix(rows, fig_dir)
    fig_p2_2_tac_comparison(rows, fig_dir)
    fig_p2_3_capex_opex(rows, fig_dir)
    fig_p2_4_sizing(rows, fig_dir)
    fig_p2_5_geometry_scatter(rows, fig_dir)
    fig_p2_8_heizkurve(fig_dir)
    fig_p2_9_pareto(rows, fig_dir)
    fig_p2_10_tornado(sens_rows, fig_dir)

    # F-P2-6 (COP time series) and F-P2-7 (DSM) require dispatch data
    # — generated from best scenario's dispatch_hourly.csv when available
    _fig_p2_6_cop_timeseries(out_base, fig_dir)
    _fig_p2_7_dsm_profile(out_base, fig_dir)

    print(f"All Paper 2 figures written to {fig_dir}")


def _fig_p2_6_cop_timeseries(out_base: Path, fig_dir: Path) -> None:
    """F-P2-6: COP time series for best MM scenario (representative week)."""
    if not HAS_MPL:
        return
    # Find a dispatch_hourly.csv from any completed MM scenario
    for scen_id in ["MM-S1-HK1", "MM-S1-HK0", "MM-S2-HK1"]:
        dispatch_path = out_base / scen_id / "dispatch_hourly.csv"
        if dispatch_path.exists():
            rows = _r(dispatch_path)
            cop_col = next((k for k in (rows[0] if rows else {}) if "cop" in k.lower()), None)
            if cop_col and rows:
                # Plot first 336 hours (2 weeks)
                T = min(336, len(rows))
                cop_vals = [_f(r.get(cop_col), 3.0) for r in rows[:T]]
                fig, ax = plt.subplots(figsize=(_COL2, 3))
                ax.plot(range(T), cop_vals, color=IPA["teal"], lw=0.8)
                ax.set_xlabel("Hour")
                ax.set_ylabel("COP [—]")
                ax.set_title(f"COP time series — {scen_id} (first 2 weeks)")
                ax.set_ylim(0, 8)
                ax.axhline(1, color="red", lw=0.5, ls="--", label="COP=1")
                ax.legend(fontsize=8)
                fig.tight_layout()
                _save(fig, fig_dir / "F-P2-6_cop_timeseries")
                return
    logger.info("F-P2-6: No dispatch data found — skipping COP time series")


def _fig_p2_7_dsm_profile(out_base: Path, fig_dir: Path) -> None:
    """F-P2-7: DSM activation profile (if DSM data available)."""
    if not HAS_MPL:
        return
    for scen_id in out_base.iterdir():
        dsm_path = scen_id / "dsm_hourly.csv"
        if dsm_path.exists():
            rows = _r(dsm_path)
            if not rows:
                continue
            delta_col = next((k for k in rows[0] if "delta" in k.lower()), None)
            if delta_col:
                T = min(168, len(rows))  # 1 week
                delta = [_f(r.get(delta_col)) for r in rows[:T]]
                fig, ax = plt.subplots(figsize=(_COL2, 3))
                ax.bar(range(T), [max(0, d) for d in delta], color=IPA["teal"], label="δ_pos")
                ax.bar(range(T), [min(0, d) for d in delta], color=IPA["navy"], label="δ_neg")
                ax.set_xlabel("Hour")
                ax.set_ylabel("Load shift δ [MW]")
                ax.set_title(f"DSM activation — {scen_id.name} (first week)")
                ax.legend(fontsize=8)
                fig.tight_layout()
                _save(fig, fig_dir / "F-P2-7_dsm_profile")
                return
    logger.info("F-P2-7: No DSM data found — skipping")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out_base = _ROOT / "output" / "paper2_runs"
    fig_dir = out_base / "figures"
    generate_all_figures(out_base, fig_dir)
