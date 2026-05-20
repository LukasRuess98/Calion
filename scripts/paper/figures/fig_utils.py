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
FIG_DIR.mkdir(parents=True, exist_ok=True)
FIG_FORMATS = ("png", "pdf", "pgf")
FIG_RASTER_DPI = 600

# Applied Energy style
STYLE = dict(AE_RCPARAMS)
STYLE.update({
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
})

LEVEL_COLORS = {
    "L1":    "#2166AC",
    "L2":    "#4DAC26",
    "L3":    "#D01C8B",
    "L3plus": "#F1A340",
    "L3NL":  "#A50026",
}

LEVEL_LABELS = {
    "L1":    "L1 (copperplate)",
    "L2":    "L2 (regional)",
    "L3":    "L3 (basic physics)",
    "L3plus": r"L3$^+$ (full physics)",
    "L3NL":  r"L3$^\mathrm{NL}$ (nonlinear)",
}

COST_COLORS = {
    "fuel":   "#D9534F",
    "energy": "#F0AD4E",
    "co2":    "#5BC0DE",
    "pump":   "#777777",
    "dump":   "#999999",
    "demand": "#5CB85C",
}


def apply_style() -> None:
    plt.rcParams.update(STYLE)


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
