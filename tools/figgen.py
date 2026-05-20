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
NODE_POS = {
    "j_1":  (0.0,  0.0),   # Source / Heizwerk
    "j_2":  (1.5,  0.0),
    "j_3":  (3.0,  0.0),
    # South arm (downward)
    "j_4":  (3.0, -1.8),
    "j_5":  (3.0, -3.4),
    "j_6":  (4.0, -5.0),
    "j_7":  (2.0, -5.0),
    "j_8":  (2.0, -6.4),
    # East arm (rightward)
    "j_9":  (4.8,  0.0),
    "j_10": (6.2,  0.0),
    "j_11": (7.6,  0.0),
    "j_12": (9.0,  0.0),   # HP + EBoiler
    "j_13": (10.4, 0.0),
    "j_14": (10.4, 1.6),
    "j_15": (11.8, 0.0),
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
    2D taxonomy diagram: x-axis = topology detail, y-axis = physics fidelity.
    Five model variants as labeled points with annotation arrows.
    """
    plt, mpl = _mpl_setup()
    fig, ax = plt.subplots(figsize=(3.54, 3.0))

    # Axes: topology (0=none, 1=zone, 2=full-graph)
    #       physics  (0=none, 1=steady-state losses, 2=+pressure+delay)
    variants = {
        "L1":    (0, 0, "Copperplate\n(L1)", "#F44336"),
        "L2":    (1, 1, "Zone-aggregated\n(L2)", "#FF9800"),
        "L3":    (2, 1, "Detailed MILP\n(L3)", "#4CAF50"),
        "L3+":   (2, 2, "Extended MILP\n(L3⁺)", "#2196F3"),
        "L3NL":  (2, 2, "Quadratic ref.\n(L3ᴺᴸ)", "#9C27B0"),
    }
    # Slight offset for L3+ and L3NL to avoid overlap
    offsets = {"L3NL": (0.15, -0.1)}

    # Background shading for topology regions
    ax.axvspan(-0.2, 0.5,   alpha=0.05, color="red")
    ax.axvspan(0.5,  1.5,   alpha=0.05, color="orange")
    ax.axvspan(1.5,  2.8,   alpha=0.05, color="green")

    for name, (x, y, label, color) in variants.items():
        ox, oy = offsets.get(name, (0, 0))
        marker = "D" if "NL" in name else ("s" if "+" in name else "o")
        ax.scatter(x + ox, y + oy, s=200, c=color, zorder=5,
                   marker=marker, edgecolors="k", linewidths=0.5)
        ax.annotate(label, (x + ox, y + oy), fontsize=6.5,
                    ha="center", va="bottom",
                    xytext=(0, 8), textcoords="offset points")

    # Arrows indicating experimental comparisons
    def _arrow(x0, y0, x1, y1, label="", color="gray"):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.1,
                                   connectionstyle="arc3,rad=0.0"))
        mx, my = (x0+x1)/2, (y0+y1)/2
        ax.text(mx, my, label, fontsize=5.5, color=color, ha="center",
                va="bottom", rotation=0,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))

    _arrow(0, 0, 1, 1, "Topology\neffect", "#E65100")
    _arrow(1, 1, 2, 1, "", "#E65100")
    _arrow(2, 1, 2, 2, "Physics\nfidelity", "#1565C0")

    ax.set_xlim(-0.4, 3.0)
    ax.set_ylim(-0.5, 2.8)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["Single-bus\n(L1)", "Zone\n(L2)", "Full-graph\n(L3/L3⁺)"],
                       fontsize=7)
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(["No physics", "Steady-state\nlosses",
                         "Extended\n(Δp + delay + T-prop)"], fontsize=7)
    ax.set_xlabel("Topology abstraction level", fontsize=8)
    ax.set_ylabel("Physics fidelity level", fontsize=8)
    ax.set_title("Experimental design: three orthogonal comparisons", fontsize=9)
    ax.grid(True, alpha=0.2)

    # Linearization error annotation
    ax.annotate("Linearization\nerror (MILP↔MIQCP)",
                xy=(2.15, 2.0), xytext=(2.5, 2.5),
                fontsize=5.5, color="#9C27B0",
                arrowprops=dict(arrowstyle="-|>", color="#9C27B0", lw=0.8))

    _save_fig(fig, out_dir, "F1_experimental_design", plt)


# ---------------------------------------------------------------------------
# F2 — Network topology schematic (Hari et al. style)
# ---------------------------------------------------------------------------

def fig_F2(out_dir: Path, t_values: dict | None = None) -> None:
    """
    Network topology map with:
    - Node colors = supply temperature (viridis colormap, as in Hari 2024 Fig 2a)
    - Edge widths = pipe diameter (DN100→DN450)
    - Special markers for asset nodes (j_1 = star, j_12 = diamond)
    - Pipe length annotations on selected pipes
    - Color bar for temperature
    """
    plt, mpl = _mpl_setup()
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(figsize=(7.09, 4.5))

    # Default temperatures (nominal supply, decreasing with distance)
    if t_values is None:
        t_values = {
            "j_1": 100.0, "j_2": 98.8, "j_3": 97.4,
            "j_4": 96.2, "j_5": 95.0, "j_6": 93.5, "j_7": 94.1, "j_8": 93.2,
            "j_9": 95.8, "j_10": 94.6, "j_11": 93.4,
            "j_12": 92.1, "j_13": 91.0, "j_14": 90.3, "j_15": 89.8,
        }

    all_temps = list(t_values.values())
    t_min, t_max = min(all_temps), max(all_temps)
    norm  = mcolors.Normalize(vmin=t_min - 1, vmax=t_max + 1)
    cmap  = cm.plasma

    # Draw pipes
    dn_to_lw = {450: 5.0, 350: 4.0, 300: 3.5, 250: 2.8, 150: 2.0, 125: 1.5, 100: 1.0}
    for frm, to, length_m, dn in PIPES:
        x0, y0 = NODE_POS[frm]
        x1, y1 = NODE_POS[to]
        lw = dn_to_lw.get(dn, 1.5)
        t_avg = (t_values.get(frm, 95) + t_values.get(to, 95)) / 2
        color = cmap(norm(t_avg))
        ax.plot([x0, x1], [y0, y1], "-", color=color, lw=lw, zorder=2,
                solid_capstyle="round")
        # Length annotation on main trunk only
        if dn >= 400:
            mx, my = (x0+x1)/2, (y0+y1)/2
            ax.text(mx, my + 0.3, f"{length_m}m", fontsize=5,
                    ha="center", va="bottom", color="k", alpha=0.7)

    # Draw nodes
    for node, (x, y) in NODE_POS.items():
        t = t_values.get(node, 90.0)
        color = cmap(norm(t))
        assets = NODE_ASSETS.get(node, [])
        n_consumers = len(NODE_CONSUMERS.get(node, []))

        if node == "j_1":
            # Source: large star
            ax.scatter(x, y, s=350, c=[color], cmap=cmap,
                       marker="*", zorder=5, edgecolors="k", linewidths=0.8)
        elif assets:
            # Asset node: diamond
            ax.scatter(x, y, s=200, c=[color], cmap=cmap, vmin=t_min-1, vmax=t_max+1,
                       marker="D", zorder=5, edgecolors="k", linewidths=0.8)
        else:
            # Regular junction: circle, size proportional to consumers
            size = 80 + n_consumers * 20
            ax.scatter(x, y, s=size, c=[color], cmap=cmap, vmin=t_min-1, vmax=t_max+1,
                       marker="o", zorder=5, edgecolors="k", linewidths=0.5)

        # Node label
        label = node.replace("j_", "j$_{") + "}$" if "_" in node else node
        offset_x, offset_y = 0.0, -0.4
        if node in ("j_1", "j_12"):
            offset_y = 0.4
        ax.text(x + offset_x, y + offset_y, label,
                fontsize=6, ha="center", va="top", zorder=6)

        # Asset labels at special nodes
        if assets:
            ax.text(x, y + 0.6, "\n".join(assets),
                    fontsize=5, ha="center", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="gray",
                              alpha=0.8, lw=0.5), zorder=7)

    # Color bar for temperatures
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cb = plt.colorbar(sm, ax=ax, label="Supply temperature [°C]",
                      orientation="vertical", shrink=0.7, pad=0.02)
    cb.ax.tick_params(labelsize=6)

    # Legend for pipe diameters
    legend_elements = [
        Line2D([0], [0], color="k", lw=dn_to_lw[d], label=f"DN{d}")
        for d in [450, 350, 300, 250, 150, 100]
    ]
    legend_elements += [
        Line2D([0], [0], marker="*", color="w", markerfacecolor="gray",
               markeredgecolor="k", markersize=10, label="Production node"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="gray",
               markeredgecolor="k", markersize=8, label="HP + EBoiler (j$_{12}$)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="gray",
               markeredgecolor="k", markersize=6, label="Distribution node"),
    ]
    ax.legend(handles=legend_elements, loc="lower left", fontsize=5.5,
              ncol=2, columnspacing=0.5, handlelength=1.5)

    ax.set_xlim(-1.0, 13.5)
    ax.set_ylim(-7.8, 3.0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Memmingen district heating network — 15 nodes, 14 pipes\n"
                 "(node color = nominal supply temperature)",
                 fontsize=9)

    # Arm labels
    ax.text(0.3,  0.4, "Main trunk (DN450)", fontsize=6, color="gray", style="italic")
    ax.text(3.0, -0.5, "South arm →", fontsize=6, color="gray", style="italic",
            rotation=-90, va="top")
    ax.text(4.5,  0.5, "East arm →", fontsize=6, color="gray", style="italic")

    _save_fig(fig, out_dir, "F2_network_topology", plt)


# ---------------------------------------------------------------------------
# F3 — Annual cost decomposition stacked bars
# ---------------------------------------------------------------------------

def fig_F3(out_dir: Path) -> None:
    """Stacked bar: fuel / electricity / CO₂ / pump cost for L1, L2, L3."""
    plt, mpl = _mpl_setup()
    eco = _load_economics()

    levels  = ["L1", "L2", "L3"]
    cost_components = [
        ("cost_fuel_eur",          "Fuel",        "#FF5722"),
        ("cost_energy_buy_eur",    "Electricity", "#2196F3"),
        ("cost_co2_eur",           "CO₂",         "#9C27B0"),
        ("cost_pump_eur",          "Pumping",     "#607D8B"),
        ("cost_demand_charge_eur", "Demand charge","#795548"),
    ]

    fig, ax = plt.subplots(figsize=(3.54, 3.2))
    x = np.arange(len(levels))
    bottoms = np.zeros(len(levels))

    for col, label, color in cost_components:
        vals = []
        for rid in levels:
            v = eco.get(rid, {}).get(col, 0.0) or 0.0
            vals.append(float(v) / 1e3)  # → k€
        vals = np.array(vals)
        ax.bar(x, vals, bottom=bottoms, label=label, color=color, alpha=0.85, width=0.6)
        bottoms += vals

    # Annotate total difference vs L3
    ref_total = bottoms[2]
    for i, (rid, total) in enumerate(zip(levels, bottoms)):
        delta = total - ref_total
        ax.text(x[i], total + max(bottoms) * 0.01,
                f"{total:.0f}k€\n({delta:+.0f}k€)" if rid != "L3" else f"{total:.0f}k€",
                ha="center", va="bottom", fontsize=6)

    ax.set_xticks(x); ax.set_xticklabels(levels, fontsize=8)
    ax.set_ylabel("Annual operational cost [k€/yr]")
    ax.set_title("Topology effect on operational cost (RQ1)", fontsize=9)
    ax.legend(fontsize=6, ncol=1, loc="upper right")
    ax.grid(True, axis="y")
    ax.set_ylim(0, max(bottoms) * 1.18)

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

    # Find highest-demand week
    dem = dispatch.get("Q_demand_total_MW")
    if dem is None:
        return
    weekly = dem.resample("W").mean()
    best_week_start = weekly.idxmax() - pd.Timedelta(days=6)
    slice_d = dispatch[best_week_start: best_week_start + pd.Timedelta(days=7)]

    fig, axes = plt.subplots(2, 1, figsize=(7.09, 4.5), sharex=True)

    # Upper: stacked area — generation
    ax = axes[0]
    asset_layers = [
        ("Q_chp_MW",           "CHP",       "#B71C1C"),
        ("Q_biomass_MW",       "Biomass",   "#2E7D32"),
        ("Q_boiler_biomass_MW","Biomass",   "#2E7D32"),
        ("Q_gasboiler_MW",     "Gas boiler","#FF5722"),
        ("Q_boiler_gas_MW",    "Gas boiler","#FF5722"),
        ("Q_hp_total_MW",      "Heat pump", "#0D47A1"),
        ("Q_ek_MW",            "EBoiler",   "#F9A825"),
        ("Q_storage_discharge_MW", "TES dis.", "#00BCD4"),
    ]
    seen = set()
    bottoms = pd.Series(0.0, index=slice_d.index)
    for col, label, color in asset_layers:
        if col not in slice_d.columns or label in seen:
            continue
        vals = slice_d[col].fillna(0)
        ax.fill_between(slice_d.index, bottoms, bottoms + vals,
                        alpha=0.82, color=color, label=label, step="mid")
        bottoms = bottoms + vals
        seen.add(label)

    # Demand line
    if "Q_demand_total_MW" in slice_d:
        ax.plot(slice_d.index, slice_d["Q_demand_total_MW"], "k-",
                lw=1.2, label="Demand", zorder=10)

    ax.set_ylabel("Thermal power [MW]")
    ax.legend(fontsize=6, ncol=4, loc="upper right")
    ax.grid(True)
    ax.set_title("Winter-week dispatch — L3⁺", fontsize=9)

    # Lower: TES SOC + electricity price
    ax2 = axes[1]
    ax3 = ax2.twinx()
    if "SOC_MWh" in slice_d:
        ax2.fill_between(slice_d.index, 0, slice_d["SOC_MWh"].fillna(0),
                         alpha=0.4, color="#00BCD4", label="SOC [MWh]")
        ax2.set_ylabel("TES SOC [MWh]", color="#00BCD4")
    if "lambda_buy_eur_MWh" in slice_d:
        ax3.plot(slice_d.index, slice_d["lambda_buy_eur_MWh"],
                 color="#FF9800", lw=0.8, ls="--", label="Price [€/MWh]")
        ax3.set_ylabel("Electricity price [€/MWh]", color="#FF9800")

    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    _save_fig(fig, out_dir, "F4_dispatch_winter", plt)


# ---------------------------------------------------------------------------
# F5 — Cost waterfall: L3 → L3⁺ → L3ᴺᴸ
# ---------------------------------------------------------------------------

def fig_F5(out_dir: Path) -> None:
    """
    Waterfall chart decomposing cost gap:
    L3 → (+pump) → (−loss_reduction) → (−delay_shift) = L3⁺ → (lin_error) = L3ᴺᴸ
    """
    plt, mpl = _mpl_setup()
    eco = _load_economics()

    c3  = float(eco.get("L3",    {}).get("cost_total_eur", 0) or 0)
    c3p = float(eco.get("L3plus",{}).get("cost_total_eur", 0) or 0)
    c3nl= float(eco.get("L3NL",  {}).get("cost_total_eur", 0) or 0)

    if c3 == 0:
        print("  [SKIP] F5 — no L3 results")
        return

    pump_cost    = float(eco.get("L3plus", {}).get("cost_pump_eur", 0) or 0)
    # Estimate loss reduction as residual (pump dominates going from L3→L3+)
    total_gap    = c3p - c3
    loss_reduc   = -(pump_cost - total_gap)  # negative = cost reduction
    delay_shift  = 0.0  # small for primary case
    lin_error    = c3nl - c3p

    steps = [
        ("L3\nbaseline",   c3,         0,         "start",  "#455A64"),
        ("+Pumping\ncost", pump_cost,  c3,        "pos",    "#F44336"),
        ("Loss\nreduction",loss_reduc, c3+pump_cost, "neg", "#4CAF50"),
        ("Transport\ndelay",delay_shift,c3+pump_cost+loss_reduc,"neg","#2196F3"),
        ("L3⁺\nresult",   c3p,        0,         "end",    "#0288D1"),
        ("Lineariz.\nerror",lin_error, c3p,       "pos" if lin_error>0 else "neg","#9C27B0"),
        ("L3ᴺᴸ\nresult",  c3nl,       0,         "end",    "#6A1B9A"),
    ]

    fig, ax = plt.subplots(figsize=(7.09, 3.2))
    x = np.arange(len(steps))
    scale = 1 / 1000  # → k€

    for i, (label, val, base, kind, color) in enumerate(steps):
        if kind == "start":
            # FIX: removed positional '0' that conflicted with width kwarg
            ax.bar(i, val * scale, color=color, alpha=0.85, width=0.6, zorder=3)
            ax.text(i, val * scale * 1.01, f"{val*scale:.0f}k€", ha="center",
                    va="bottom", fontsize=6)
        elif kind == "end":
            ax.bar(i, val * scale, color=color, alpha=0.85, width=0.6, zorder=3)
            ax.text(i, val * scale * 1.01, f"{val*scale:.0f}k€", ha="center",
                    va="bottom", fontsize=6)
        else:
            bottom = base * scale
            height = val * scale
            ax.bar(i, height, bottom=bottom, color=color, alpha=0.85, width=0.6,
                   zorder=3)
            sign = "+" if val >= 0 else ""
            ax.text(i, (bottom + height / 2),
                    f"{sign}{val*scale:.0f}k€",
                    ha="center", va="center", fontsize=6, color="white",
                    fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([s[0] for s in steps], fontsize=7)
    ax.set_ylabel("Annual cost [k€/yr]")
    ax.set_title("Cost gap decomposition: L3 → L3⁺ → L3ᴺᴸ (RQ2 + RQ3)", fontsize=9)
    ax.grid(True, axis="y")

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
    """Measured vs simulated T_supply at source, winter week."""
    plt, mpl = _mpl_setup()

    # Load validation outputs
    val_dir = VALDIR
    stage1_winter = val_dir / "stage1_timeseries_winter.png"

    # If validation plots exist, use them directly
    if stage1_winter.exists():
        import shutil
        copied = []
        for fmt in FIG_FORMATS:
            src = val_dir / f"stage1_timeseries_winter.{fmt}"
            if not src.exists():
                continue
            dst = out_dir / f"FV1_validation_timeseries.{fmt}"
            shutil.copy2(src, dst)
            copied.append(dst.suffix)
        if copied:
            print(f"  [FIG] FV1_validation_timeseries (copied: {', '.join(copied)})")
            return
        # Fallback to at least PNG copy if alternate formats are missing.
        dest = out_dir / "FV1_validation_timeseries.png"
        shutil.copy2(stage1_winter, dest)
        print("  [FIG] FV1_validation_timeseries (.png copied from validation/)")
        return

    # Fallback: generate from dispatch + kpis.json if available
    kpi_path = val_dir / "kpis.json"
    if not kpi_path.exists():
        print("  [SKIP] FV1 — run validation pipeline first (Phase 0)")
        return

    kpis = json.loads(kpi_path.read_text())
    stage1 = kpis.get("stage1", {})
    mae = stage1.get("T_supply_source_MAE_C", "N/A")

    # Minimal fallback plot
    fig, ax = plt.subplots(figsize=(7.09, 2.5))
    if isinstance(mae, float):
        msg = (f"Validation time series\nRun Phase 0 (validation_runner.py) first.\n"
               f"T_supply source MAE = {mae:.3f}°C")
    else:
        msg = "Run Phase 0 first."
    ax.text(0.5, 0.5, msg,
            ha="center", va="center", transform=ax.transAxes, fontsize=9)
    ax.axis("off")
    _save_fig(fig, out_dir, "FV1_validation_timeseries", plt)


# ---------------------------------------------------------------------------
# F7 — TES SOC comparison across levels
# ---------------------------------------------------------------------------

def fig_F7(out_dir: Path) -> None:
    """Storage SOC profiles for all five model levels — winter week."""
    plt, mpl = _mpl_setup()

    levels = ["L1", "L2", "L3", "L3plus", "L3NL"]
    colors = ["#F44336", "#FF9800", "#4CAF50", "#2196F3", "#9C27B0"]
    ls_map = {"L1": "-", "L2": "--", "L3": "-.", "L3plus": "-", "L3NL": ":"}

    dispatches = {rid: _load_dispatch(rid) for rid in levels}
    available  = {rid: d for rid, d in dispatches.items()
                  if d is not None and "SOC_MWh" in d.columns}

    if not available:
        print("  [SKIP] F7 — no SOC data")
        return

    # FIX: avoid `DataFrame or DataFrame` which raises ValueError
    ref = available.get("L3")
    if ref is None:
        ref = next(iter(available.values()))

    dem_col = "Q_demand_total_MW"
    if dem_col in ref.columns:
        weekly = ref[dem_col].resample("W").mean()
        w_start = weekly.idxmax() - pd.Timedelta(days=6)
    else:
        w_start = ref.index[0]
    w_end = w_start + pd.Timedelta(days=14)

    fig, ax = plt.subplots(figsize=(7.09, 2.8))
    for rid, color in zip(levels, colors):
        d = available.get(rid)
        if d is None:
            continue
        soc = d["SOC_MWh"][w_start:w_end]
        ax.plot(soc.index, soc, ls_map.get(rid, "-"), color=color,
                lw=1.0, label=f"{rid}", alpha=0.9)

    ax.axhline(500 * 0.05, color="k", lw=0.6, ls=":", alpha=0.5, label="SOC bounds")
    ax.axhline(500 * 0.95, color="k", lw=0.6, ls=":", alpha=0.5)
    ax.set_ylabel("TES SOC [MWh]")
    ax.set_xlabel("Date")
    ax.set_ylim(0, 530)
    ax.legend(ncol=3, fontsize=7)
    ax.grid(True)
    ax.set_title("Storage dispatch as diagnostic: SOC across model levels", fontsize=9)

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

def _draw_network_map(ax, values: dict[str, float], demand: dict[str, float], title: str, cmap_name: str):
    import matplotlib.colors as mcolors
    from matplotlib import colormaps

    finite_vals = [v for v in values.values() if v is not None and np.isfinite(v)]
    if finite_vals:
        norm = mcolors.Normalize(vmin=min(finite_vals), vmax=max(finite_vals))
    else:
        norm = mcolors.Normalize(vmin=0.0, vmax=1.0)
    cmap = colormaps.get_cmap(cmap_name)

    for frm, to, _, _ in PIPES:
        x0, y0 = NODE_POS[frm]
        x1, y1 = NODE_POS[to]
        ax.plot([x0, x1], [y0, y1], color="#7f7f7f", lw=1.0, alpha=0.55, zorder=1)

    dem_vals = [v for v in demand.values() if v is not None and np.isfinite(v) and v > 0]
    d_min = min(dem_vals) if dem_vals else 0.0
    d_max = max(dem_vals) if dem_vals else 1.0

    def _size(node: str) -> float:
        val = demand.get(node)
        if val is None or not np.isfinite(val) or d_max <= d_min:
            return 90.0
        return 80.0 + 260.0 * ((val - d_min) / (d_max - d_min))

    for node, (x, y) in NODE_POS.items():
        v = values.get(node)
        color = cmap(norm(v)) if v is not None and np.isfinite(v) else "#d9d9d9"
        marker = "*" if node == "j_1" else ("D" if node == "j_12" else "o")
        ax.scatter(x, y, s=_size(node), marker=marker, color=color, edgecolors="k", linewidths=0.6, zorder=3)
        ax.text(x, y - 0.32, node, fontsize=6, ha="center", va="top", zorder=4)

    from matplotlib.cm import ScalarMappable
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = ax.figure.colorbar(sm, ax=ax, shrink=0.8, pad=0.02)
    cbar.ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.axis("off")


def fig_F10(out_dir: Path) -> None:
    plt, _ = _mpl_setup()
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

    demand = {
        str(r["node_id"]): float(r["Q_demand_total_mwh"])
        for _, r in summary.iterrows()
        if pd.notna(r.get("Q_demand_total_mwh"))
    }
    annual_supply = {
        str(r["node_id"]): float(r["T_supply_avg_c"])
        for _, r in summary.iterrows()
        if pd.notna(r.get("T_supply_avg_c"))
    }

    spread = {}
    if seasonal is not None and not seasonal.empty:
        g = seasonal.groupby("node_id")["T_supply_avg_c"]
        spread = {
            str(node): float(series.max() - series.min())
            for node, series in g
            if pd.notna(series.max()) and pd.notna(series.min())
        }

    fig, axes = plt.subplots(1, 2, figsize=(7.09, 3.8), constrained_layout=True)
    _draw_network_map(
        axes[0],
        annual_supply,
        demand,
        f"F10A Annual mean supply temperature ({run_id})",
        "plasma",
    )
    _draw_network_map(
        axes[1],
        spread,
        demand,
        "F10B Seasonal spread of supply temperature [K]",
        "viridis",
    )
    _save_fig(fig, out_dir, "F10_node_topology_heatmap", plt)


# ---------------------------------------------------------------------------
# F11 — Critical-path profile
# ---------------------------------------------------------------------------

def fig_F11(out_dir: Path) -> None:
    plt, _ = _mpl_setup()
    run_id = _pick_node_run()
    if run_id is None:
        _placeholder_figure(
            out_dir, plt, "F11_critical_path_profile",
            "Critical-path profile",
            "No node artefacts found.",
        )
        return

    summary = _load_nodes_summary(run_id)
    seasonal = _load_nodes_seasonal(run_id)
    if summary is None or summary.empty:
        _placeholder_figure(
            out_dir, plt, "F11_critical_path_profile",
            "Critical-path profile",
            f"{run_id}: nodes_summary.csv is empty.",
        )
        return

    trunk = ["j_1", "j_2", "j_3", "j_9", "j_10", "j_11", "j_12", "j_13", "j_15"]
    idx = np.arange(len(trunk))
    smap = summary.set_index("node_id")
    t_sup = [float(smap.loc[n, "T_supply_avg_c"]) if n in smap.index and pd.notna(smap.loc[n, "T_supply_avg_c"]) else np.nan for n in trunk]
    t_ret = [float(smap.loc[n, "T_return_avg_c"]) if n in smap.index and pd.notna(smap.loc[n, "T_return_avg_c"]) else np.nan for n in trunk]
    p_avg = [float(smap.loc[n, "P_avg_bar"]) if n in smap.index and pd.notna(smap.loc[n, "P_avg_bar"]) else np.nan for n in trunk]

    fig, axes = plt.subplots(2, 1, figsize=(7.09, 4.8), sharex=True, constrained_layout=True)
    axes[0].plot(idx, t_sup, marker="o", color="#1f77b4", label="Annual T_supply")
    axes[0].plot(idx, t_ret, marker="o", color="#ff7f0e", label="Annual T_return")

    if seasonal is not None and not seasonal.empty:
        sdf = seasonal.copy()
        for season, color in [("winter", "#2ca02c"), ("transition", "#9467bd"), ("summer", "#d62728")]:
            sub = sdf[sdf["season"].astype(str) == season].set_index("node_id")
            sup_vals = [float(sub.loc[n, "T_supply_avg_c"]) if n in sub.index and pd.notna(sub.loc[n, "T_supply_avg_c"]) else np.nan for n in trunk]
            axes[0].plot(idx, sup_vals, linestyle="--", linewidth=1.0, color=color, alpha=0.9, label=f"{season} T_supply")

    axes[0].set_ylabel("Temperature [°C]")
    axes[0].set_title(f"F11A Critical-path temperature profile ({run_id})")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(ncol=3, fontsize=6)

    axes[1].plot(idx, p_avg, marker="s", color="#4c4c4c", label="Annual pressure")
    if seasonal is not None and not seasonal.empty:
        sdf = seasonal.copy()
        for season, color in [("winter", "#2ca02c"), ("transition", "#9467bd"), ("summer", "#d62728")]:
            sub = sdf[sdf["season"].astype(str) == season].set_index("node_id")
            p_vals = [float(sub.loc[n, "P_avg_bar"]) if n in sub.index and pd.notna(sub.loc[n, "P_avg_bar"]) else np.nan for n in trunk]
            axes[1].plot(idx, p_vals, linestyle="--", linewidth=1.0, color=color, alpha=0.9, label=f"{season} pressure")
    axes[1].set_ylabel("Pressure [bar]")
    axes[1].set_title("F11B Critical-path pressure profile")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(ncol=2, fontsize=6)
    axes[1].set_xticks(idx)
    axes[1].set_xticklabels(trunk, rotation=25, ha="right")
    axes[1].set_xlabel("Trunk node sequence")

    _save_fig(fig, out_dir, "F11_critical_path_profile", plt)


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
