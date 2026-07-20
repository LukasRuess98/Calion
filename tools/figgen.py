"""
Paper Figure Generator (Phase 6)
=================================
Reads simulation artefacts from output/paper_runs/ and generates
all publication figures for the paper.

Figures produced
----------------
  F1   — Experimental design matrix (topology × physics 2D diagram)
  F2   — Network topology schematic (15-node, color-coded temperatures,
          inspired by Hari et al. 2024 Fig. 1 style)
  F3   — Annual cost decomposition stacked bars (L1/L2/L3)
  F4   — Dispatch time series, 2 representative weeks (winter)
  F5   — Cost waterfall: L3 → pumping → loss-reduction → delay → L3⁺ → lin.err → L3ᴺᴸ
  F6   — Hourly pumping-power scatter: L3⁺ vs L3ᴺᴸ (R² annotation)
  FV1  — Validation time series: measured vs simulated (winter week)
  F7   — Storage SOC comparison across all five levels
  F8   — Generalizability heatmap: ΔCost (L1→L3) vs pipe-length × HI
  F9   — Node averages (annual + seasonal)
  F10  — Node topology heatmap (annual + seasonal spread)
  F11  — Critical-path profile (temperature + pressure)
  F12  — Extended duration curves (L1/L2/L3/L3plus/L3NL)
  F13  — Annual energy Sankey

Output directory: output/paper_runs/figures/ (PNG + PDF + PGF)

Usage
-----
    python tools/figgen.py              # generate all figures
    python tools/figgen.py --fig F2     # single figure
    python tools/figgen.py --fig F1 F3  # subset
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT    = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.paper.mpl_export import AE_RCPARAMS, save_figure_bundle

RUNS    = ROOT / "output" / "paper_runs"
FIGDIR  = RUNS / "figures"
VALDIR  = ROOT / "output" / "validation"
FIG_FORMATS = ("png", "pdf", "pgf")
FIG_RASTER_DPI = 600

# ---------------------------------------------------------------------------
# Fraunhofer IPA brand colors
# ---------------------------------------------------------------------------
IPA = {
    "teal":       "#009B77",   # Akzent 1 — primary IPA teal-green
    "navy":       "#003E6E",   # Akzent 2 — dark navy
    "silver":     "#8C9EA8",   # Akzent 3 — steel grey
    "dark_teal":  "#006478",   # Akzent 4 — dark teal
    "cyan":       "#00B4C8",   # Akzent 5 — bright cyan
    "lime":       "#A5C84E",   # Akzent 6 — lime green
    "orange":     "#E07B39",   # custom orange
    "dark_navy":  "#1A2A4A",   # very dark navy
    "dark_green": "#1D6545",   # custom dark green
}

# ---------------------------------------------------------------------------
# Matplotlib setup
# ---------------------------------------------------------------------------

def _mpl_setup():
    """Return (plt, mpl) with journal-quality rcParams."""
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    mpl.rcParams.update(AE_RCPARAMS)
    return plt, mpl


def _save_fig(fig, out_dir: Path, stem: str, plt) -> None:
    saved = save_figure_bundle(
        fig,
        out_dir / stem,
        formats=FIG_FORMATS,
        raster_dpi=FIG_RASTER_DPI,
    )
    plt.close(fig)
    suffixes = ", ".join(path.suffix for path in saved)
    print(f"  [FIG] {stem} ({suffixes})")


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_dispatch(run_id: str) -> pd.DataFrame | None:
    p = RUNS / run_id / "dispatch_hourly.csv"
    if p.exists():
        return pd.read_csv(p, index_col=0, parse_dates=True)
    return None


def _load_economics() -> dict[str, dict]:
    eco = {}
    for rid in ["L1", "L2", "L3", "L3plus", "L3NL"]:
        p = RUNS / rid / "economics.csv"
        if p.exists():
            try:
                df = pd.read_csv(p)
                if not df.empty:
                    eco[rid] = df.iloc[0].to_dict()
            except Exception:
                pass
    return eco


def _load_synth_results() -> pd.DataFrame | None:
    """Load synthetic parametric results for F8."""
    synth_dir = RUNS / "synth"
    rows = []
    if not synth_dir.exists():
        return None
    for sub in synth_dir.iterdir():
        meta_p  = sub / "meta.json"
        econ_p  = sub / "economics.csv"
        cfg_p   = sub / "_scenario_config.yaml"
        if not (meta_p.exists() and econ_p.exists()):
            continue
        try:
            meta = json.loads(meta_p.read_text())
            econ = pd.read_csv(econ_p).iloc[0].to_dict()
            # Parse level from folder name  e.g. synth_001_L1
            parts = sub.name.rsplit("_", 1)
            level = parts[1] if len(parts) == 2 else "?"
            row = {"run_id": sub.name, "level": level,
                   **{k: v for k, v in econ.items()},
                   "pipe_length_km": None, "hi": None, "n_nodes": None}
            if cfg_p.exists():
                try:
                    import yaml
                    cfg = yaml.safe_load(cfg_p.read_text())
                    synth_p = cfg.get("synthetic", {})
                    row["pipe_length_km"] = synth_p.get("pipe_length_km")
                    row["hi"]             = synth_p.get("demand_hi")
                    row["n_nodes"]        = synth_p.get("n_nodes")
                    row["storage_ratio"]  = synth_p.get("storage_ratio_h")
                except Exception:
                    pass
            rows.append(row)
        except Exception:
            pass
    return pd.DataFrame(rows) if rows else None


def _node_sort_key(node_id: str) -> tuple[int, str]:
    parts = "".join(ch if ch.isdigit() else " " for ch in str(node_id)).split()
    if parts:
        try:
            return (int(parts[-1]), str(node_id))
        except ValueError:
            pass
    return (10**9, str(node_id))


def _season_sort_key(season: str) -> int:
    order = {"winter": 0, "transition": 1, "summer": 2}
    return order.get(str(season), 99)


def _load_nodes_summary(run_id: str) -> pd.DataFrame | None:
    p = RUNS / run_id / "nodes_summary.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
        return df if not df.empty else None
    except Exception:
        return None


def _load_nodes_seasonal(run_id: str) -> pd.DataFrame | None:
    p = RUNS / run_id / "nodes_seasonal.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
        return df if not df.empty else None
    except Exception:
        return None


def _load_nodes_state(run_id: str) -> pd.DataFrame | None:
    p = RUNS / run_id / "nodes_state_hourly.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
        if df.empty:
            return None
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df
    except Exception:
        return None


def _pick_node_run() -> str | None:
    for rid in ("L3plus", "L3", "L3NL"):
        if (RUNS / rid / "nodes_summary.csv").exists():
            return rid
    return None


def _placeholder_figure(out_dir: Path, plt, stem: str, title: str, message: str) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 2.6))
    ax.text(
        0.5,
        0.5,
        f"{title}\n{message}",
        ha="center",
        va="center",
        transform=ax.transAxes,
        fontsize=9,
    )
    ax.axis("off")
    _save_fig(fig, out_dir, stem, plt)


# ---------------------------------------------------------------------------
# Network topology layout (from Memmingen_L3_MILP.yaml)
# ---------------------------------------------------------------------------

# Node positions in schematic space (x=east/right, y=north/up)
# Derived from the real Memmingen eProNet map geometry:
#   J1 = production node (top, center-right)
#   Trunk: J1→J2→J3 (south-west then south-east)
#   South/West arm: J3→J4→J5→J6 and J5→J7→J8
#   East arm: J3→J9→J10→J11→J12→J13→J14 and J13→J15
NODE_POS = {
    "j_1":  (5.5, 11.0),   # Production node (top, center-right)
    "j_2":  (4.5,  8.8),   # Main trunk south
    "j_3":  (6.0,  6.5),   # Main junction — splits west & east arm
    # West/South arm
    "j_4":  (3.8,  6.5),   # West branch from j3
    "j_5":  (2.2,  5.2),   # South-west
    "j_6":  (1.5,  3.5),   # South terminal
    "j_7":  (0.3,  6.5),   # West terminal
    "j_8":  (1.3,  7.8),   # North-west terminal
    # East arm
    "j_9":  (7.6,  6.5),   # East branch from j3
    "j_10": (7.8,  5.2),   # East arm, south
    "j_11": (7.2,  4.2),   # East arm
    "j_12": (6.0,  5.1),   # HP + EBoiler (back towards center)
    "j_13": (5.5,  3.0),   # East arm, south
    "j_14": (8.0,  3.0),   # East terminal
    "j_15": (4.8,  1.5),   # South terminal
}

PIPES = [
    ("j_1", "j_2", 350, 450),
    ("j_2", "j_3", 300, 450),
    ("j_3", "j_4", 260, 300),
    ("j_3", "j_9", 450, 350),
    ("j_4", "j_5", 240, 250),
    ("j_5", "j_6", 150, 150),
    ("j_5", "j_7", 220, 125),
    ("j_7", "j_8",  80, 100),
    ("j_9", "j_10", 200, 300),
    ("j_10","j_11", 230, 300),
    ("j_11","j_12", 250, 300),
    ("j_12","j_13", 220, 250),
    ("j_13","j_14", 180, 125),
    ("j_13","j_15", 125, 100),
]

# Assets at nodes
NODE_ASSETS = {
    "j_1":  ["CHP", "TES", "Gas Boiler", "Biomass"],
    "j_12": ["HP", "EBoiler"],
}

NODE_CONSUMERS = {
    "j_1":  ["V_1"],
    "j_2":  ["V_2"],
    "j_3":  ["V_3"],
    "j_4":  ["V_4","V_5","V_6","V_7"],
    "j_5":  ["V_8","V_9"],
    "j_6":  ["V_10","V_11","V_12"],
    "j_7":  ["V_13"],
    "j_8":  ["V_14"],
    "j_9":  ["V_15","V_16"],
    "j_10": ["V_17"],
    "j_11": ["V_18"],
    "j_12": ["V_19","V_20","V_21"],
    "j_13": ["V_22","V_23","V_24"],
    "j_14": ["V_25","V_26"],
    "j_15": ["V_27"],
}


# ---------------------------------------------------------------------------
# F1 — Experimental design matrix
# ---------------------------------------------------------------------------

def fig_F1(out_dir: Path) -> None:
    """
    Clean horizontal flowchart: L1 → L2 → L3 → L3⁺ → L3ᴺᴸ
    with labeled comparison arrows beneath each transition.
    Double column width (170 mm).
    """
    plt, mpl = _mpl_setup()
    import matplotlib.patches as mpatches
    MM = 1 / 25.4
    fig, ax = plt.subplots(figsize=(170 * MM, 55 * MM))
    ax.set_xlim(-0.3, 4.3)
    ax.set_ylim(-1.4, 1.6)
    ax.axis("off")

    levels = ["L1", "L2", "L3", "L3+", "L3NL"]
    colors = {
        "L1":   "#C62828",   # dark red
        "L2":   "#E65100",   # dark orange
        "L3":   "#2E7D32",   # dark green
        "L3+":  "#1565C0",   # dark blue
        "L3NL": "#6A1B9A",   # dark purple
    }
    subtitles = {
        "L1":   "Copperplate\n1 node\nMILP",
        "L2":   "7-zone\naggregation\nMILP",
        "L3":   "15-node\nbasic physics\nMILP",
        "L3+":  "15-node\nextended physics\nMILP",
        "L3NL": "15-node\nextended physics\nMIQCP",
    }
    comparisons = [
        (0, 1, "Topology\neffect (RQ1)", "above", "#B71C1C"),
        (1, 2, "Topology\nrefinement (RQ1)", "above", "#BF360C"),
        (2, 3, "Physics\nfidelity (RQ2)", "below", "#1565C0"),
        (3, 4, "Linearization\nerror (RQ3)", "below", "#4A148C"),
    ]

    box_h, box_w = 0.7, 0.72
    y_box = 0.3
    for i, lvl in enumerate(levels):
        clr = colors[lvl]
        rect = mpatches.FancyBboxPatch(
            (i - box_w / 2, y_box - box_h / 2), box_w, box_h,
            boxstyle="round,pad=0.04",
            facecolor=clr, edgecolor="white", linewidth=1.2, alpha=0.92, zorder=3,
        )
        ax.add_patch(rect)
        ax.text(i, y_box, f"$\\mathbf{{{lvl}}}$\n{subtitles[lvl]}",
                ha="center", va="center", fontsize=6.2, color="white",
                linespacing=1.35, zorder=4)

    for i0, i1, label, side, clr in comparisons:
        x0 = i0 + box_w / 2 + 0.02
        x1 = i1 - box_w / 2 - 0.02
        y  = y_box + (0.52 if side == "above" else -0.52)
        yt = y + (0.20 if side == "above" else -0.22)
        ax.annotate("", xy=(x1, y), xytext=(x0, y),
                    arrowprops=dict(arrowstyle="-|>", color=clr, lw=1.1), zorder=2)
        for xi in (x0, x1):
            yb = y_box + (box_h / 2 if side == "above" else -box_h / 2)
            ax.plot([xi, xi], [yb, y], color=clr, lw=0.6, ls=":", zorder=1)
        ax.text((x0 + x1) / 2, yt, label,
                ha="center", va="center", fontsize=6.0, color=clr,
                style="italic",
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))

    ax.set_title("Experimental design: three orthogonal comparison dimensions",
                 fontsize=8, pad=4)
    _save_fig(fig, out_dir, "F1_experimental_design", plt)


# ---------------------------------------------------------------------------
# F2 — Network topology schematic (Hari et al. style)
# ---------------------------------------------------------------------------

def fig_F2(out_dir: Path) -> None:
    """
    Network topology schematic:
    - Edge widths = pipe diameter (DN100→DN450), grey
    - Node size = number of consumers, filled by arm color
    - j_1 = large circle with hatch (production), j_12 = double ring (HP node)
    - Legend placed below figure (no overlap)
    Double column width (170 mm).
    """
    plt, mpl = _mpl_setup()
    from matplotlib.lines import Line2D
    import matplotlib.patches as mpatches

    MM = 1 / 25.4
    fig, ax = plt.subplots(figsize=(85 * MM, 95 * MM))

    # Arm / branch colors for visual grouping
    TRUNK_COLOR  = IPA["navy"]       # j1–j2–j3
    SOUTH_COLOR  = IPA["orange"]     # j4–j8
    EAST_COLOR   = IPA["dark_teal"]  # j9–j15

    def _arm_color(node: str) -> str:
        if node in ("j_1", "j_2", "j_3"):
            return TRUNK_COLOR
        if node in ("j_4", "j_5", "j_6", "j_7", "j_8"):
            return SOUTH_COLOR
        return EAST_COLOR

    dn_to_lw = {450: 5.0, 350: 4.0, 300: 3.5, 250: 2.8, 150: 2.0, 125: 1.5, 100: 1.0}

    # Draw pipes
    for frm, to, length_m, dn in PIPES:
        x0, y0 = NODE_POS[frm]
        x1, y1 = NODE_POS[to]
        lw = dn_to_lw.get(dn, 1.5)
        ax.plot([x0, x1], [y0, y1], "-", color="#90A4AE", lw=lw, zorder=2,
                solid_capstyle="round")

    # Draw nodes
    for node, (x, y) in NODE_POS.items():
        color = _arm_color(node)
        n_consumers = len(NODE_CONSUMERS.get(node, []))
        size = max(100, 80 + n_consumers * 28)

        if node == "j_1":
            # Production node: large filled circle with thick edge
            ax.scatter(x, y, s=size + 120, marker="o", color=color,
                       edgecolors="k", linewidths=1.8, zorder=5)
            ax.scatter(x, y, s=size + 40, marker="o", color="white",
                       edgecolors="none", zorder=6, alpha=0.35)
        elif node == "j_12":
            # HP/EBoiler node: double ring
            ax.scatter(x, y, s=size + 60, marker="o", color=color,
                       edgecolors="k", linewidths=1.6, zorder=5)
            ax.scatter(x, y, s=size - 20, marker="o", color="white",
                       edgecolors=color, linewidths=1.0, zorder=6)
        else:
            ax.scatter(x, y, s=size, marker="o", color=color,
                       edgecolors="#37474F", linewidths=0.6, zorder=5, alpha=0.88)

        # Node label — offset to avoid overlap
        lbl = node.replace("j_", "j")
        offsets = {
            "j_1": (0.0, 0.55), "j_2": (-0.55, 0.0), "j_3": (0.55, 0.0),
            "j_4": (-0.55, 0.0), "j_5": (-0.55, 0.0), "j_6": (-0.55, 0.0),
            "j_7": (-0.55, 0.0), "j_8": (-0.55, 0.0),
            "j_9": (0.55, 0.0), "j_10": (0.55, 0.0), "j_11": (0.55, 0.0),
            "j_12": (0.55, 0.0), "j_13": (0.0, -0.5), "j_14": (0.55, 0.0),
            "j_15": (0.0, -0.5),
        }
        ox, oy = offsets.get(node, (0.0, -0.45))
        ax.text(x + ox, y + oy, lbl, fontsize=6, ha="center", va="center", zorder=7,
                color="#212121")

    # Asset annotation boxes
    for node, asset_list in NODE_ASSETS.items():
        x, y = NODE_POS[node]
        label_text = ", ".join(asset_list)
        oy = 0.75 if node == "j_1" else -0.75
        ax.text(x, y + oy, label_text, fontsize=5.5, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#90A4AE",
                          lw=0.7, alpha=0.92), zorder=8, color="#37474F")

    # Arm labels
    ax.text(4.8, 10.2, "Trunk", fontsize=7, color=TRUNK_COLOR, fontweight="bold", ha="center")
    ax.text(1.5,  7.2, "South/West arm", fontsize=7, color=SOUTH_COLOR,
            fontweight="bold", ha="center", rotation=0)
    ax.text(8.5,  6.8, "East arm", fontsize=7, color=EAST_COLOR,
            fontweight="bold", ha="center")

    ax.set_xlim(-1.2, 10.5)
    ax.set_ylim(0.0, 12.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Network topology\n(15 nodes · 14 pipes · 27 consumers)", fontsize=7, pad=3)

    # Legend — placed below the axes, no overlap
    legend_elements = [
        Line2D([0], [0], color="#90A4AE", lw=dn_to_lw[d], label=f"DN{d}")
        for d in [450, 350, 300, 250, 150, 100]
    ]
    legend_elements += [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=TRUNK_COLOR,
               markeredgecolor="k", markersize=9, linewidth=1.8, label="Production (j1)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=EAST_COLOR,
               markeredgecolor=EAST_COLOR, markersize=7, label="HP+EBoiler (j12)"),
        mpatches.Patch(facecolor=SOUTH_COLOR, label="South/West arm"),
        mpatches.Patch(facecolor=EAST_COLOR,  label="East arm"),
    ]
    ax.legend(handles=legend_elements, loc="lower center",
              bbox_to_anchor=(0.5, -0.06), ncol=5, fontsize=5.5,
              columnspacing=0.6, handlelength=1.6, frameon=True,
              framealpha=0.9, edgecolor="#BDBDBD")

    _save_fig(fig, out_dir, "F2_network_topology", plt)


# ---------------------------------------------------------------------------
# F3 — Annual cost decomposition stacked bars
# ---------------------------------------------------------------------------

def fig_F3(out_dir: Path) -> None:
    """Stacked bar: fuel / electricity / CO₂ cost for L1, L2, L3 (single column)."""
    plt, mpl = _mpl_setup()
    MM = 1 / 25.4
    eco = _load_economics()

    levels = ["L1", "L2", "L3"]
    cost_components = [
        ("cost_fuel_eur",       "Fuel",         IPA["navy"]),
        ("cost_energy_buy_eur", "Electricity",  IPA["dark_teal"]),
        ("cost_co2_eur",        "CO₂",          IPA["teal"]),
        ("cost_dump_eur",       "Dump penalty", IPA["silver"]),
    ]

    fig, ax = plt.subplots(figsize=(85 * MM, 70 * MM), constrained_layout=True)
    x = np.arange(len(levels))
    bottoms = np.zeros(len(levels))

    for col, label, color in cost_components:
        vals = np.array([float(eco.get(rid, {}).get(col, 0.0) or 0.0) / 1e3 for rid in levels])
        if vals.sum() == 0:
            continue
        ax.bar(x, vals, bottom=bottoms, label=label, color=color, alpha=0.88, width=0.55)
        bottoms += vals

    ref_total = bottoms[levels.index("L3")]
    for i, (rid, total) in enumerate(zip(levels, bottoms)):
        delta = total - ref_total
        ann = f"{total:.0f}\n({delta:+.0f})" if rid != "L3" else f"{total:.0f}"
        ax.text(x[i], total + max(bottoms) * 0.012, ann,
                ha="center", va="bottom", fontsize=5.5)

    ax.set_xticks(x)
    ax.set_xticklabels(levels, fontsize=7)
    ax.set_ylabel("Annual cost [k€/yr]", fontsize=7)
    ax.set_title("Topology effect on cost (RQ1)", fontsize=7, pad=3)
    ax.legend(fontsize=6, ncol=1, loc="upper right", framealpha=0.9,
              handlelength=1.2, labelspacing=0.3)
    ax.grid(True, axis="y", alpha=0.4)
    ax.set_ylim(0, max(bottoms) * 1.22)
    ax.tick_params(labelsize=6)

    _save_fig(fig, out_dir, "F3_cost_topology", plt)


# ---------------------------------------------------------------------------
# F4 — Dispatch time series (representative winter week)
# ---------------------------------------------------------------------------

def fig_F4(out_dir: Path) -> None:
    """Stacked area chart of asset dispatch for a representative winter week."""
    plt, mpl = _mpl_setup()

    # FIX: avoid `DataFrame or DataFrame` which raises ValueError
    dispatch = _load_dispatch("L3plus")
    if dispatch is None:
        dispatch = _load_dispatch("L3")
    if dispatch is None:
        print("  [SKIP] F4 — no dispatch data")
        return

    # Find highest-demand week using rolling mean to avoid edge artefacts
    dem = dispatch.get("Q_demand_total_MW")
    if dem is None:
        return
    rolling7 = dem.rolling("7D").mean()
    peak_end  = rolling7.idxmax()
    best_week_start = max(peak_end - pd.Timedelta(days=6), dispatch.index[0])
    slice_d = dispatch[best_week_start: best_week_start + pd.Timedelta(hours=167)]

    import matplotlib.dates as mdates
    MM = 1 / 25.4
    fig, axes = plt.subplots(2, 1, figsize=(170 * MM, 90 * MM),
                             sharex=True, constrained_layout=True)

    # Upper: stacked area — generation (IPA colors)
    ax = axes[0]
    asset_layers = [
        ("Q_chp_MW",               "CHP",        IPA["dark_navy"]),
        ("Q_biomass_MW",           "Biomass",    IPA["teal"]),
        ("Q_boiler_biomass_MW",    "Biomass",    IPA["teal"]),
        ("Q_gasboiler_MW",         "Gas boiler", IPA["navy"]),
        ("Q_boiler_gas_MW",        "Gas boiler", IPA["navy"]),
        ("Q_hp_total_MW",          "Heat pump",  IPA["cyan"]),
        ("Q_ek_MW",                "E-Boiler",   IPA["lime"]),
        ("Q_storage_discharge_MW", "TES dis.",   IPA["silver"]),
    ]
    seen: set = set()
    bottoms = pd.Series(0.0, index=slice_d.index)
    for col, label, color in asset_layers:
        if col not in slice_d.columns or label in seen:
            continue
        vals = slice_d[col].fillna(0)
        ax.fill_between(slice_d.index, bottoms, bottoms + vals,
                        alpha=0.88, color=color, label=label, step="mid")
        bottoms = bottoms + vals
        seen.add(label)
    if "Q_demand_total_MW" in slice_d:
        ax.plot(slice_d.index, slice_d["Q_demand_total_MW"],
                color=IPA["dark_navy"], lw=1.1, label="Demand", zorder=10)
    ax.set_ylabel("Power [MW]", fontsize=7)
    ax.legend(fontsize=5.5, ncol=4, loc="upper right",
              framealpha=0.9, handlelength=1.0, columnspacing=0.5)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_title("Winter-week dispatch — L3", fontsize=7, pad=3)
    ax.tick_params(labelsize=6)

    # Lower: TES SOC + electricity price
    ax2 = axes[1]
    ax3 = ax2.twinx()
    if "SOC_MWh" in slice_d:
        ax2.fill_between(slice_d.index, 0, slice_d["SOC_MWh"].fillna(0),
                         alpha=0.55, color=IPA["teal"])
        ax2.set_ylabel("SOC [MWh]", fontsize=7, color=IPA["teal"])
        ax2.tick_params(axis="y", colors=IPA["teal"], labelsize=6)
    if "lambda_buy_eur_MWh" in slice_d:
        ax3.plot(slice_d.index, slice_d["lambda_buy_eur_MWh"],
                 color=IPA["orange"], lw=0.9, ls="--", label="Price")
        ax3.set_ylabel("Price [€/MWh]", fontsize=7, color=IPA["orange"])
        ax3.tick_params(axis="y", colors=IPA["orange"], labelsize=6)
    ax2.grid(True, axis="y", alpha=0.25)
    ax2.tick_params(axis="x", labelsize=6)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax2.xaxis.set_major_locator(mdates.DayLocator())

    _save_fig(fig, out_dir, "F4_dispatch_winter", plt)


# ---------------------------------------------------------------------------
# F5 — Cost waterfall: L3 → L3⁺ → L3ᴺᴸ
# ---------------------------------------------------------------------------

def fig_F5(out_dir: Path) -> None:
    """
    Grouped cost comparison bars: L1, L2, L3, L3⁺ — fuel, electricity, CO₂.
    Double column width (170 mm).
    """
    plt, mpl = _mpl_setup()
    MM = 1 / 25.4
    eco = _load_economics()

    # Include L3NL if week data is available (annualise from 1-week run)
    week_eco_path = RUNS / "_week_linearization" / "L3NL" / "economics.csv"
    l3nl_eco: dict = {}
    if week_eco_path.exists():
        try:
            wdf = pd.read_csv(week_eco_path)
            row = wdf.iloc[0] if len(wdf) else pd.Series(dtype=float)
            scale_52 = 52.18  # 1 week → annual
            for col in ["cost_fuel_eur", "cost_energy_buy_eur", "cost_co2_eur",
                        "cost_dump_eur", "cost_total_eur"]:
                v = row.get(col)
                if v is not None and pd.notna(v):
                    l3nl_eco[col] = float(v) * scale_52
        except Exception:
            pass

    levels  = ["L1", "L2", "L3", "L3plus"]
    labels  = ["L1", "L2", "L3", "L3+"]
    # Only include L3NL if annualised cost is plausible (≤3× L3, run converged)
    l3_ref = float(eco.get("L3", {}).get("cost_total_eur", 0) or 0) / 1e3
    l3nl_total = l3nl_eco.get("cost_total_eur", 0) / 1e3 if l3nl_eco else 0
    if l3nl_eco and l3_ref > 0 and l3nl_total <= l3_ref * 3:
        levels.append("L3NL"); labels.append("L3NL*")

    components = [
        ("cost_fuel_eur",       "Fuel",         IPA["navy"]),
        ("cost_energy_buy_eur", "Electricity",  IPA["dark_teal"]),
        ("cost_co2_eur",        "CO₂",          IPA["teal"]),
        ("cost_dump_eur",       "Dump penalty", IPA["silver"]),
    ]

    def _get(rid: str, col: str) -> float:
        if rid == "L3NL":
            return l3nl_eco.get(col, 0.0) / 1e3
        return float(eco.get(rid, {}).get(col, 0.0) or 0.0) / 1e3

    x = np.arange(len(levels))
    fig, ax = plt.subplots(figsize=(85 * MM, 70 * MM), constrained_layout=True)

    bottoms = np.zeros(len(levels))
    for col, lbl, color in components:
        vals = np.array([_get(rid, col) for rid in levels])
        if vals.sum() == 0:
            continue
        ax.bar(x, vals, bottom=bottoms, label=lbl, color=color, alpha=0.88, width=0.52)
        bottoms += vals

    # Annotate total above each bar; show delta vs L3
    ref_idx = levels.index("L3") if "L3" in levels else -1
    ref_total = bottoms[ref_idx] if ref_idx >= 0 else 0.0
    for i, (rid, tot) in enumerate(zip(levels, bottoms)):
        if tot <= 0:
            continue
        delta = tot - ref_total
        show_delta = rid != "L3" and abs(delta) >= 0.5
        ann = f"{tot:.0f}" if not show_delta else f"{tot:.0f}\n({delta:+.0f})"
        ax.text(x[i], tot + max(bottoms) * 0.012, ann,
                ha="center", va="bottom", fontsize=5.5, color="#212121")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("Annual cost [k€/yr]", fontsize=7)
    ax.set_title("Operational cost comparison across model levels (RQ1–RQ3)", fontsize=7, pad=3)
    ax.legend(fontsize=6, ncol=4, loc="upper right", framealpha=0.9,
              handlelength=1.2, columnspacing=0.6)
    ax.grid(True, axis="y", alpha=0.4)
    ax.set_ylim(0, max(bottoms) * 1.22 if bottoms.max() > 0 else 1)
    ax.tick_params(labelsize=6)
    if "L3NL" in levels:
        ax.text(0.99, 0.01, "* L3NL annualised from 1-week run",
                transform=ax.transAxes, fontsize=5, ha="right", va="bottom",
                color="#757575")

    _save_fig(fig, out_dir, "F5_cost_waterfall", plt)


# ---------------------------------------------------------------------------
# F6 — Pumping scatter: L3⁺ vs L3ᴺᴸ
# ---------------------------------------------------------------------------

def fig_F6(out_dir: Path) -> None:
    """Hourly P_pump scatter with R² annotation."""
    plt, mpl = _mpl_setup()
    d3p  = _load_dispatch("L3plus")
    d3nl = _load_dispatch("L3NL")

    if d3p is None or d3nl is None:
        print("  [SKIP] F6 — missing L3plus or L3NL dispatch")
        return

    col = "P_pump_MW"
    if col not in d3p.columns or col not in d3nl.columns:
        print("  [SKIP] F6 — P_pump_MW column not found")
        return

    idx = d3p.dropna(subset=[col]).index.intersection(
          d3nl.dropna(subset=[col]).index)
    if len(idx) < 100:
        print("  [SKIP] F6 — insufficient aligned timesteps")
        return

    p3p  = d3p.loc[idx, col]
    p3nl = d3nl.loc[idx, col]

    corr = np.corrcoef(p3p, p3nl)[0, 1] if len(p3p) > 1 else 0
    r2   = corr ** 2
    rmse = float(np.sqrt(((p3p - p3nl) ** 2).mean()))

    fig, ax = plt.subplots(figsize=(3.54, 3.0))
    ax.scatter(p3nl, p3p, s=4, alpha=0.4, c="#2196F3", linewidths=0)
    lo = min(p3p.min(), p3nl.min())
    hi = max(p3p.max(), p3nl.max())
    ax.plot([lo, hi], [lo, hi], "k-", lw=0.8, label="1:1")
    ax.text(0.05, 0.95,
            f"$R^2={r2:.4f}$\nRMSE={rmse:.3f} MW",
            transform=ax.transAxes, va="top", fontsize=7)
    ax.set_xlabel("$P^{\\rm pump}$ — L3ᴺᴸ [MW]")
    ax.set_ylabel("$P^{\\rm pump}$ — L3⁺ (PWL) [MW]")
    ax.set_title("Linearization error: pumping power (RQ3)", fontsize=9)
    ax.legend(fontsize=7)
    ax.grid(True)

    _save_fig(fig, out_dir, "F6_pump_scatter", plt)


# ---------------------------------------------------------------------------
# FV1 — Validation time series
# ---------------------------------------------------------------------------

def fig_FV1(out_dir: Path) -> None:
    """Representative winter-week: dispatch, supply temperature, TES SOC."""
    plt, mpl = _mpl_setup()
    import matplotlib.dates as mdates
    MM = 1 / 25.4

    dispatch = _load_dispatch("L3")
    if dispatch is None:
        _placeholder_figure(out_dir, plt, "FV1_validation_timeseries",
                            "Model overview", "No L3 dispatch data found.")
        return

    # Find coldest/highest-demand week (representative winter)
    dem_col = "Q_demand_total_MW"
    data_start = dispatch.index[0]
    data_end   = dispatch.index[-1]
    if dem_col in dispatch.columns:
        # Use 7-day rolling mean; index is the RIGHT edge of each window
        rolling7 = dispatch[dem_col].rolling("7D").mean()
        peak_end  = rolling7.idxmax()
        w_start   = peak_end - pd.Timedelta(days=6)
    else:
        w_start = data_start
    # Clamp to data range
    w_start = max(w_start, data_start)
    w_end   = min(w_start + pd.Timedelta(hours=167), data_end)
    sl = dispatch[w_start:w_end]

    fig, axes = plt.subplots(3, 1, figsize=(170 * MM, 110 * MM),
                             sharex=True, constrained_layout=True)

    # Panel 1 — Stacked asset dispatch
    ax0 = axes[0]
    asset_layers = [
        ("Q_gasboiler_MW",         "Gas boiler", IPA["navy"]),
        ("Q_biomass_MW",           "Biomass",    IPA["teal"]),
        ("Q_hp_total_MW",          "Heat pump",  IPA["cyan"]),
        ("Q_ek_MW",                "E-Boiler",   IPA["lime"]),
        ("Q_storage_discharge_MW", "TES dis.",   IPA["silver"]),
        ("Q_chp_MW",               "CHP",        IPA["dark_teal"]),
    ]
    bottoms = pd.Series(0.0, index=sl.index)
    seen: set = set()
    for col, label, color in asset_layers:
        if col not in sl.columns or label in seen:
            continue
        vals = sl[col].fillna(0)
        ax0.fill_between(sl.index, bottoms, bottoms + vals,
                         alpha=0.88, color=color, label=label, step="mid")
        bottoms = bottoms + vals
        seen.add(label)
    if dem_col in sl.columns:
        ax0.plot(sl.index, sl[dem_col], color=IPA["dark_navy"],
                 lw=1.1, label="Demand", zorder=10)
    ax0.set_ylabel("Power [MW]", fontsize=7)
    ax0.legend(fontsize=5.5, ncol=4, loc="upper right",
               framealpha=0.9, handlelength=1.0, columnspacing=0.5)
    ax0.grid(True, axis="y", alpha=0.3)
    ax0.tick_params(labelsize=6)

    # Panel 2 — Supply temperature
    ax1 = axes[1]
    if "T_supply_C" in sl.columns:
        ax1.plot(sl.index, sl["T_supply_C"].fillna(method="ffill"),
                 color=IPA["navy"], lw=1.0, label="T$_{sup}$ source")
    if "T_supply_farend_C" in sl.columns:
        ax1.plot(sl.index, sl["T_supply_farend_C"].fillna(method="ffill"),
                 color=IPA["cyan"], lw=1.0, ls="--", label="T$_{sup}$ far-end")
    ax1.set_ylabel("T$_{supply}$ [°C]", fontsize=7)
    ax1.legend(fontsize=6, loc="lower right", framealpha=0.9)
    ax1.grid(True, axis="y", alpha=0.3)
    ax1.tick_params(labelsize=6)

    # Panel 3 — TES SOC
    ax2 = axes[2]
    if "SOC_MWh" in sl.columns:
        ax2.fill_between(sl.index, sl["SOC_MWh"].fillna(0),
                         color=IPA["teal"], alpha=0.65, lw=0.0)
        ax2.plot(sl.index, sl["SOC_MWh"].fillna(0),
                 color=IPA["teal"], lw=0.8)
        ax2.axhline(500 * 0.05, color="k", lw=0.6, ls=":", alpha=0.4)
        ax2.axhline(500 * 0.95, color="k", lw=0.6, ls=":", alpha=0.4)
    ax2.set_ylabel("TES SOC [MWh]", fontsize=7)
    ax2.set_ylim(0, 530)
    ax2.grid(True, axis="y", alpha=0.3)
    ax2.tick_params(labelsize=6)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax2.xaxis.set_major_locator(mdates.DayLocator())

    # Stage-1 validation KPI box — paper Table 6 certified values (hardcoded)
    _kpi_vals = {"T_supply_source_MAE_C": 0.99,
                 "T_supply_farend_MAE_C": 1.19,
                 "T_return_source_MAE_C": 0.55}
    lines = [
        f"MAE T$_{{sup,src}}$ = {_kpi_vals['T_supply_source_MAE_C']:.2f}°C",
        f"MAE T$_{{sup,far}}$ = {_kpi_vals['T_supply_farend_MAE_C']:.2f}°C",
        f"MAE T$_{{ret}}$      = {_kpi_vals['T_return_source_MAE_C']:.2f}°C",
    ]
    ax1.text(0.01, 0.97, "\n".join(lines), transform=ax1.transAxes,
             fontsize=6, va="top", ha="left",
             bbox=dict(boxstyle="round,pad=0.28", fc="white",
                       ec=IPA["silver"], lw=0.7, alpha=0.92))

    axes[0].set_title("Dispatch — representative winter week (L3)", fontsize=7, pad=3)
    _save_fig(fig, out_dir, "FV1_validation_timeseries", plt)


# ---------------------------------------------------------------------------
# F7 — TES SOC comparison across levels
# ---------------------------------------------------------------------------

def fig_F7(out_dir: Path) -> None:
    """Storage SOC profiles for L1, L2, L3, L3⁺ — full simulation year."""
    plt, mpl = _mpl_setup()
    import matplotlib.dates as mdates
    MM = 1 / 25.4

    levels = ["L1", "L2", "L3", "L3plus"]
    labels = {"L1": "L1", "L2": "L2", "L3": "L3", "L3plus": "L3+"}
    colors = {"L1": "#C62828", "L2": "#E65100", "L3": "#2E7D32", "L3plus": "#1565C0"}
    ls_map = {"L1": "-", "L2": "--", "L3": "-.", "L3plus": "-"}

    dispatches = {rid: _load_dispatch(rid) for rid in levels}
    available  = {rid: d for rid, d in dispatches.items()
                  if d is not None and "SOC_MWh" in d.columns}

    if not available:
        print("  [SKIP] F7 — no SOC data")
        return

    fig, ax = plt.subplots(figsize=(170 * MM, 60 * MM), constrained_layout=True)

    for rid in levels:
        d = available.get(rid)
        if d is None:
            continue
        # Resample to daily mean for a clean full-year plot
        soc = d["SOC_MWh"].resample("D").mean()
        ax.plot(soc.index, soc, ls_map.get(rid, "-"),
                color=colors[rid], lw=0.9, label=labels[rid], alpha=0.9)

    ax.axhline(500 * 0.05, color="k", lw=0.6, ls=":", alpha=0.45)
    ax.axhline(500 * 0.95, color="k", lw=0.6, ls=":", alpha=0.45)
    ax.set_ylabel("TES SOC [MWh]", fontsize=7)
    ax.set_ylim(0, 530)
    ax.legend(ncol=4, fontsize=6, loc="upper right", framealpha=0.9)
    ax.grid(True, alpha=0.35)
    ax.set_title("TES state of charge — full simulation year", fontsize=7, pad=3)
    ax.tick_params(labelsize=6)

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    _save_fig(fig, out_dir, "F7_TES_SOC_comparison", plt)


# ---------------------------------------------------------------------------
# F8 — Generalizability heatmap
# ---------------------------------------------------------------------------

def fig_F8(out_dir: Path) -> None:
    """ΔCost (L1→L3) heatmap vs pipe_length × demand_HI from synthetic runs."""
    plt, mpl = _mpl_setup()
    synth = _load_synth_results()

    if synth is None or synth.empty:
        print("  [SKIP] F8 — no synthetic results (run Phase 3 first)")
        _fig_F8_placeholder(out_dir, plt)
        return

    # Compute ΔCost = (Cost_L1 - Cost_L3) / Cost_L3 × 100
    l1 = synth[synth["level"] == "L1"][["cost_total_eur","pipe_length_km","hi","n_nodes"]]
    l3 = synth[synth["level"] == "L3"][["cost_total_eur","pipe_length_km","hi","n_nodes"]]

    if l1.empty or l3.empty:
        _fig_F8_placeholder(out_dir, plt)
        return

    merged = l1.merge(l3, on=["pipe_length_km","hi","n_nodes"],
                      suffixes=("_L1","_L3"))
    merged = merged.dropna(subset=["cost_total_eur_L1","cost_total_eur_L3"])
    merged["delta_cost_pct"] = ((merged["cost_total_eur_L3"] - merged["cost_total_eur_L1"])
                                 / merged["cost_total_eur_L1"].replace(0, np.nan) * 100)

    # 2D pivot: pipe_length vs HI
    pivot = merged.pivot_table(index="pipe_length_km", columns="hi",
                                values="delta_cost_pct", aggfunc="mean")

    fig, ax = plt.subplots(figsize=(3.54, 2.8))
    if not pivot.empty:
        im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn_r",
                       origin="lower")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"{x:.1f}" for x in pivot.columns], fontsize=7)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"{x:.0f}" for x in pivot.index], fontsize=7)
        plt.colorbar(im, ax=ax, label="ΔCost L1→L3 [%]", shrink=0.8)

        # Annotate cells
        for i in range(pivot.shape[0]):
            # FIX: was `for j in pivot.shape[1]` → int is not iterable
            for j in range(pivot.shape[1]):
                v = pivot.values[i, j]
                if np.isfinite(v):
                    ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                            fontsize=6, color="k")

    ax.set_xlabel("Demand heterogeneity index (HI)")
    ax.set_ylabel("Total pipe length [km]")
    ax.set_title("Topology gap ΔCost (L1→L3) across\nsynthetic network configurations",
                 fontsize=9)

    _save_fig(fig, out_dir, "F8_generalizability_heatmap", plt)


def _fig_F8_placeholder(out_dir: Path, plt) -> None:
    fig, ax = plt.subplots(figsize=(3.54, 2.8))
    ax.text(0.5, 0.5,
            "F8: Generalizability heatmap\nRun Phase 3 (synthetic) first.",
            ha="center", va="center", transform=ax.transAxes, fontsize=9)
    ax.axis("off")
    _save_fig(fig, out_dir, "F8_generalizability_heatmap", plt)
    print("  [FIG] F8_generalizability_heatmap (placeholder)")


# ---------------------------------------------------------------------------
# F9 — Node averages (annual + seasonal)
# ---------------------------------------------------------------------------

def fig_F9(out_dir: Path) -> None:
    plt, _ = _mpl_setup()
    run_id = _pick_node_run()
    if run_id is None:
        _placeholder_figure(
            out_dir, plt, "F9_node_averages",
            "Node averages",
            "No nodes_summary.csv found (run Phase 1 first).",
        )
        return

    summary = _load_nodes_summary(run_id)
    seasonal = _load_nodes_seasonal(run_id)
    if summary is None or summary.empty:
        _placeholder_figure(
            out_dir, plt, "F9_node_averages",
            "Node averages",
            f"{run_id}: nodes_summary.csv is empty.",
        )
        return

    summary = summary.copy().sort_values("node_id", key=lambda c: c.map(_node_sort_key))
    nodes = summary["node_id"].astype(str).tolist()
    x = np.arange(len(nodes))

    ts = summary.get("T_supply_avg_c", pd.Series(np.nan, index=summary.index)).astype(float)
    tr = summary.get("T_return_avg_c", pd.Series(np.nan, index=summary.index)).astype(float)
    dt = summary.get("delta_t_avg_c", pd.Series(np.nan, index=summary.index)).astype(float)

    fig = plt.figure(figsize=(7.09, 5.2), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.5, 1.0])
    ax_main = fig.add_subplot(gs[0, :])
    season_axes = [fig.add_subplot(gs[1, i]) for i in range(3)]

    w = 0.26
    ax_main.bar(x - w, ts, width=w, label="T_supply avg [°C]", color="#1f77b4", alpha=0.85)
    ax_main.bar(x, tr, width=w, label="T_return avg [°C]", color="#ff7f0e", alpha=0.85)
    ax_main.bar(x + w, dt, width=w, label="delta T avg [K]", color="#2ca02c", alpha=0.85)
    ax_main.set_xticks(x)
    ax_main.set_xticklabels(nodes, rotation=55, ha="right")
    ax_main.set_ylabel("Annual mean")
    ax_main.set_title(f"F9 Node averages ({run_id}) — annual + seasonal")
    ax_main.grid(True, axis="y", alpha=0.3)
    ax_main.legend(ncol=3, fontsize=6, loc="upper right")

    season_names = ["winter", "transition", "summer"]
    if seasonal is None or seasonal.empty:
        for ax, season in zip(season_axes, season_names):
            ax.text(
                0.5,
                0.5,
                f"{season}\nno seasonal data",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=7,
            )
            ax.axis("off")
    else:
        sdf = seasonal.copy()
        sdf["node_id"] = sdf["node_id"].astype(str)
        for ax, season in zip(season_axes, season_names):
            sub = sdf[sdf["season"].astype(str) == season]
            if sub.empty:
                ax.text(
                    0.5,
                    0.5,
                    f"{season}\nno data",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                    fontsize=7,
                )
                ax.axis("off")
                continue
            sub = sub.sort_values("node_id", key=lambda c: c.map(_node_sort_key))
            vals = sub.get("delta_t_avg_c", pd.Series(np.nan, index=sub.index)).astype(float).values
            lbls = sub["node_id"].tolist()
            xx = np.arange(len(lbls))
            ax.bar(xx, vals, color="#2ca02c", alpha=0.85)
            ax.set_xticks(xx)
            ax.set_xticklabels(lbls, rotation=55, ha="right", fontsize=6)
            ax.set_title(season, fontsize=8)
            ax.set_ylabel("delta T [K]", fontsize=7)
            ax.grid(True, axis="y", alpha=0.3)

    _save_fig(fig, out_dir, "F9_node_averages", plt)


# ---------------------------------------------------------------------------
# F10 — Node topology heatmap (annual + seasonal spread)
# ---------------------------------------------------------------------------

def _draw_network_map(ax, values: dict[str, float], cbar_label: str, title: str, cmap_name: str):
    """Draw the Memmingen network with nodes colored by `values` dict."""
    import matplotlib.colors as mcolors
    from matplotlib import colormaps
    from matplotlib.cm import ScalarMappable

    finite_vals = [v for v in values.values() if v is not None and np.isfinite(v)]
    if finite_vals:
        norm = mcolors.Normalize(vmin=min(finite_vals), vmax=max(finite_vals))
    else:
        norm = mcolors.Normalize(vmin=0.0, vmax=1.0)
    cmap = colormaps.get_cmap(cmap_name)

    dn_to_lw = {450: 4.0, 350: 3.2, 300: 2.6, 250: 2.0, 150: 1.4, 125: 1.1, 100: 0.8}
    for frm, to, _, dn in PIPES:
        x0, y0 = NODE_POS[frm]
        x1, y1 = NODE_POS[to]
        ax.plot([x0, x1], [y0, y1], color="#90A4AE", lw=dn_to_lw.get(dn, 1.2),
                alpha=0.65, zorder=1)

    for node, (x, y) in NODE_POS.items():
        v = values.get(node)
        color = cmap(norm(v)) if v is not None and np.isfinite(v) else "#d9d9d9"
        # Use circle for all nodes — no star
        size = 160 if node in ("j_1", "j_12") else 90
        edgew = 1.4 if node in ("j_1", "j_12") else 0.6
        ax.scatter(x, y, s=size, marker="o", color=color, edgecolors="k",
                   linewidths=edgew, zorder=3)
        lbl = node.replace("j_", "j")
        ax.text(x, y - 0.38, lbl, fontsize=5.5, ha="center", va="top", zorder=4)

    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = ax.figure.colorbar(sm, ax=ax, shrink=0.75, pad=0.02)
    cbar.set_label(cbar_label, fontsize=6)
    cbar.ax.tick_params(labelsize=5.5)
    ax.set_title(title, fontsize=7, pad=3)
    ax.set_aspect("equal")
    ax.axis("off")


def fig_F10(out_dir: Path) -> None:
    """Network heatmap: node color by annual heat demand and seasonal T spread."""
    plt, _ = _mpl_setup()
    MM = 1 / 25.4
    run_id = _pick_node_run()
    if run_id is None:
        _placeholder_figure(
            out_dir, plt, "F10_node_topology_heatmap",
            "Node topology heatmap",
            "No node artefacts found.",
        )
        return

    summary = _load_nodes_summary(run_id)
    seasonal = _load_nodes_seasonal(run_id)
    if summary is None or summary.empty:
        _placeholder_figure(
            out_dir, plt, "F10_node_topology_heatmap",
            "Node topology heatmap",
            f"{run_id}: nodes_summary.csv is empty.",
        )
        return

    # Color by annual heat demand (spatially varying), not supply temp (uniform)
    demand_col = "Q_demand_total_mwh"
    demand_values = {
        str(r["node_id"]): float(r[demand_col])
        for _, r in summary.iterrows()
        if pd.notna(r.get(demand_col))
    }

    # Seasonal T_supply spread (also spatially varying if seasonal data exists)
    spread: dict[str, float] = {}
    if seasonal is not None and not seasonal.empty:
        g = seasonal.groupby("node_id")["T_supply_avg_c"]
        spread = {
            str(node): float(series.max() - series.min())
            for node, series in g
            if pd.notna(series.max()) and pd.notna(series.min())
        }
    # Fall back to demand if no seasonal spread data
    right_values = spread if spread else demand_values
    right_label  = "Seasonal T spread [K]" if spread else "Annual demand [GWh]"
    right_cmap   = "viridis" if spread else "YlOrRd"

    fig, axes = plt.subplots(1, 2, figsize=(170 * MM, 95 * MM), constrained_layout=True)
    _draw_network_map(
        axes[0],
        demand_values,
        "Annual heat demand [GWh]",
        f"Annual demand per node ({run_id})",
        "YlOrRd",
    )
    _draw_network_map(
        axes[1],
        right_values,
        right_label,
        "Seasonal temperature spread per node",
        right_cmap,
    )
    _save_fig(fig, out_dir, "F10_node_topology_heatmap", plt)


# ---------------------------------------------------------------------------
# F11 — Critical-path profile
# ---------------------------------------------------------------------------

def fig_F11(out_dir: Path) -> None:
    """F11 removed — critical-path data discussed in text (Section 5.6)."""
    plt, _ = _mpl_setup()
    # This figure has been removed from the paper.
    # Pressure and temperature profiles along the critical path are
    # discussed in the text of Section 5.6 instead.
    _placeholder_figure(
        out_dir, plt, "F11_critical_path_profile",
        "Figure removed",
        "Critical-path pressure and temperature profiles\nare discussed in Section 5.6 (text).",
    )


# ---------------------------------------------------------------------------
# F12 — Extended duration curves
# ---------------------------------------------------------------------------

def fig_F12(out_dir: Path) -> None:
    plt, _ = _mpl_setup()
    levels = ["L1", "L2", "L3", "L3plus", "L3NL"]
    colors = {
        "L1": "#d62728",
        "L2": "#ff7f0e",
        "L3": "#2ca02c",
        "L3plus": "#1f77b4",
        "L3NL": "#9467bd",
    }
    dispatch = {rid: _load_dispatch(rid) for rid in levels}
    available = {rid: df for rid, df in dispatch.items() if df is not None and not df.empty}
    if not available:
        _placeholder_figure(
            out_dir, plt, "F12_duration_curves_extended",
            "Extended duration curves",
            "No dispatch_hourly.csv found.",
        )
        return

    metrics = [
        ("Q_demand_total_MW", "Heat demand duration"),
        ("P_pump_MW", "Pump power duration"),
        ("Q_loss_total_MW", "Heat loss duration"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(7.09, 2.6), constrained_layout=True)
    for ax, (col, title) in zip(axes, metrics):
        plotted = 0
        for rid in levels:
            df = available.get(rid)
            if df is None or col not in df.columns:
                continue
            vals = pd.to_numeric(df[col], errors="coerce").fillna(0.0).values
            if len(vals) == 0:
                continue
            vals = np.sort(vals)[::-1]
            x = np.linspace(0, 100, len(vals))
            ax.plot(x, vals, label=rid, color=colors[rid], linewidth=1.0)
            plotted += 1
        if plotted == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes, fontsize=7)
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("Percentile [%]")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("Power [MW]")
    axes[-1].legend(fontsize=6, loc="upper right")
    if "L3NL" not in available:
        fig.text(
            0.5,
            0.01,
            "L3NL missing: curve omitted.",
            ha="center",
            va="bottom",
            fontsize=7,
            color="#555555",
        )
    fig.suptitle("F12 Extended duration curves across model levels", fontsize=9)
    _save_fig(fig, out_dir, "F12_duration_curves_extended", plt)


# ---------------------------------------------------------------------------
# F13 — Annual energy Sankey
# ---------------------------------------------------------------------------

def fig_F13(out_dir: Path) -> None:
    plt, _ = _mpl_setup()
    run_id = "L3plus" if (RUNS / "L3plus" / "dispatch_hourly.csv").exists() else "L3"
    df = _load_dispatch(run_id)
    if df is None or df.empty:
        _placeholder_figure(
            out_dir, plt, "F13_energy_sankey",
            "Annual energy Sankey",
            "No dispatch data for L3plus/L3.",
        )
        return

    def _sum_col(col: str) -> float:
        if col not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).sum())

    q_chp = _sum_col("Q_chp_MW")
    q_bio = _sum_col("Q_biomass_MW") if "Q_biomass_MW" in df.columns else _sum_col("Q_boiler_biomass_MW")
    q_gas = _sum_col("Q_gasboiler_MW") if "Q_gasboiler_MW" in df.columns else _sum_col("Q_boiler_gas_MW")
    q_hp = _sum_col("Q_hp_total_MW")
    q_ek = _sum_col("Q_ek_MW")
    charge = _sum_col("Q_storage_charge_MW")
    discharge = _sum_col("Q_storage_discharge_MW")
    demand = _sum_col("Q_demand_total_MW")
    losses = _sum_col("Q_loss_total_MW")

    supply_tech = q_chp + q_bio + q_gas + q_hp + q_ek
    storage_net = discharge - charge
    imbalance = supply_tech + storage_net - demand - losses

    fig, ax = plt.subplots(figsize=(7.09, 3.2))
    try:
        from matplotlib.sankey import Sankey

        flows = [supply_tech, storage_net, -demand, -losses, -imbalance]
        labels = ["Generation", "Storage net", "Demand", "Network losses", "Residual"]
        orientations = [0, 1, -1, -1, -1]
        scale = 1.0 / max(abs(supply_tech), abs(demand), 1.0)

        sankey = Sankey(ax=ax, scale=scale, offset=0.2, unit=" MWh", format="%.0f")
        sankey.add(
            flows=flows,
            labels=labels,
            orientations=orientations,
            pathlengths=[0.35, 0.25, 0.30, 0.30, 0.20],
            facecolor="#4C72B0",
            alpha=0.8,
        )
        sankey.finish()
        ax.set_title(f"F13 Annual energy Sankey ({run_id})")
        txt = (
            f"CHP={q_chp:.0f}, Biomass={q_bio:.0f}, Gas={q_gas:.0f}, "
            f"HP={q_hp:.0f}, EBoiler={q_ek:.0f} MWh"
        )
        ax.text(0.02, -0.08, txt, transform=ax.transAxes, fontsize=7)
    except Exception as exc:
        ax.axis("off")
        ax.text(
            0.5, 0.5,
            f"Sankey not available.\n{run_id} annual balance:\n"
            f"Generation={supply_tech:.0f} MWh, Storage net={storage_net:.0f} MWh,\n"
            f"Demand={demand:.0f} MWh, Losses={losses:.0f} MWh\nError: {exc}",
            ha="center", va="center", transform=ax.transAxes, fontsize=8
        )
    _save_fig(fig, out_dir, "F13_energy_sankey", plt)


# ---------------------------------------------------------------------------
# Registry and dispatch
# ---------------------------------------------------------------------------

FIGURES = {
    "F1":  fig_F1,
    "F2":  fig_F2,
    "F3":  fig_F3,
    "F4":  fig_F4,
    "F5":  fig_F5,
    "F6":  fig_F6,
    "FV1": fig_FV1,
    "F7":  fig_F7,
    "F8":  fig_F8,
    "F9":  fig_F9,
    "F10": fig_F10,
    "F11": fig_F11,
    "F12": fig_F12,
    "F13": fig_F13,
}


def generate_all(subset: list[str] | None = None) -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    targets = subset if subset else list(FIGURES.keys())
    print(f"\n[FIGGEN] Generating {len(targets)} figures → {FIGDIR}")
    for name in targets:
        fn = FIGURES.get(name)
        if fn is None:
            print(f"  [SKIP] Unknown figure: {name}")
            continue
        try:
            fn(FIGDIR)
        except Exception as e:
            import traceback
            print(f"  [ERR] {name}: {e}")
            traceback.print_exc()

    print(f"[FIGGEN] Done. {len(targets)} figures in {FIGDIR}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Paper figure generator")
    parser.add_argument("--fig", nargs="*",
                        choices=list(FIGURES.keys()),
                        help="Specific figure(s) to generate")
    args = parser.parse_args(argv)
    generate_all(args.fig)


if __name__ == "__main__":
    main()
