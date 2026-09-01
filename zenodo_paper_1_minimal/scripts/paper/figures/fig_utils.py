"""Shared matplotlib style for all paper figures."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path

from scripts.paper.mpl_export import AE_RCPARAMS, save_figure_bundle

ROOT = Path(__file__).resolve().parents[3]
FIG_DIR = ROOT / "output" / "paper_runs" / "figures"
FIG_DIR = FIG_DIR / "polished"
FIG_DIR.mkdir(parents=True, exist_ok=True)
FIG_FORMATS = ("pdf", "svg", "png", "tiff")
FIG_RASTER_DPI = 900

# Applied Energy style
STYLE = dict(AE_RCPARAMS)
STYLE.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "legend.title_fontsize": 7,
    "lines.markersize": 4,
    "patch.linewidth": 0.45,
    "grid.linewidth": 0.35,
    "grid.alpha": 0.32,
    "grid.color": "#BFC6CC",
    "savefig.dpi": FIG_RASTER_DPI,
    "savefig.facecolor": "white",
})

LEVEL_COLORS = {
    "L1cp":   "#888888",   # copperplate baseline — gray
    "L1":     "#2166AC",   # topology, no physics — blue
    "L2":     "#4DAC26",   # + heat loss — green
    "L3":     "#D01C8B",   # + pressure drop — magenta
    "L3plus": "#F1A340",   # + transport delay — orange
    "L3NL":   "#A50026",   # nonlinear reference — dark red
}

# Paper-facing display labels (paper convention: L1 / L1_topo / L2 / L3 / L+).
LEVEL_LABELS = {
    "L1cp":   r"$\mathrm{L1}$",
    "L1":     r"$\mathrm{L1}_{\mathrm{topo}}$",
    "L2":     r"$\mathrm{L2}$",
    "L3":     r"$\mathrm{L3}$",
    "L3plus": r"$\mathrm{L}^{+}$",
    "L3NL":   r"$\mathrm{L}^{\mathrm{NL}}$",
}

# Short tick labels for compact axes
LEVEL_SHORT = {
    "L1cp":   "L1",
    "L1":     "L1_topo",
    "L2":     "L2",
    "L3":     "L3",
    "L3plus": "L+",
    "L3NL":   "L^NL",
}

COST_COLORS = {
    "fuel":   "#D9534F",
    "energy": "#F0AD4E",
    "co2":    "#5BC0DE",
    "pump":   "#777777",
    "dump":   "#999999",
    "demand": "#5CB85C",
}

DIRECTION_COLORS = {
    "positive": "#B94E48",
    "negative": "#3F7CAC",
    "neutral":  "#4D4D4D",
}


def apply_style() -> None:
    plt.rcParams.update(STYLE)


def polish_axes(ax: plt.Axes, *, grid_axis: str = "both") -> None:
    """Apply journal-style axes cleanup without touching plotted data."""
    if grid_axis == "none":
        ax.grid(False)
    else:
        ax.grid(True, axis=grid_axis, color=STYLE["grid.color"],
                linewidth=STYLE["grid.linewidth"], alpha=STYLE["grid.alpha"])
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(width=0.6, length=3, pad=2)


def save_fig(fig: plt.Figure, stem: str) -> None:
    apply_style()
    saved = save_figure_bundle(
        fig,
        FIG_DIR / stem,
        formats=FIG_FORMATS,
        raster_dpi=FIG_RASTER_DPI,
    )
    suffixes = ", ".join(path.suffix for path in saved)
    print(f"[FIG] {stem} ({suffixes}) saved to {FIG_DIR}")
    plt.close(fig)
