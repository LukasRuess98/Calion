"""
Applied Energy publication style constants and helpers.

Column widths:  single = 85 mm,  double = 170 mm,  max height = 225 mm
Resolution:     1000 DPI (line art), 500 DPI (combination)
Font:           8–10 pt body, 6 pt minimum for secondary labels
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from scripts.paper.mpl_export import save_figure_bundle

# ── Dimensions ────────────────────────────────────────────────────────────────
MM = 1 / 25.4          # mm → inch conversion
W1 = 85  * MM          # single column
W2 = 170 * MM          # double column
HMAX = 225 * MM        # maximum figure height

# ── 4-level colour palette (print-safe, colourblind-safe) ─────────────────────
LEVEL_COLORS = {
    "L1": "#2166ac",   # blue
    "L2": "#f4a582",   # salmon-orange
    "L3": "#4dac26",   # green
    "L3_NLP": "#d01c8b",  # magenta
}
LEVEL_LABELS = {
    "L1":     "L1 – Copperplate",
    "L2":     "L2 – 5-node (MILP)",
    "L3":     "L3 – 24-node (MILP)",
    "L3_NLP": "L3 – 24-node (QCQP)",
}
LEVELS = ["L1", "L2", "L3", "L3_NLP"]

# ── Cost component colours ────────────────────────────────────────────────────
COST_COLORS = {
    "Grid electricity": "#2166ac",
    "Gas fuel":         "#fdae61",
    "CO₂ cost":         "#d73027",
    "Demand charge":    "#fee090",
    "Heat dump":        "#abd9e9",
    "CAPEX":            "#878787",
}

# ── Dispatch stack colours ────────────────────────────────────────────────────
DISPATCH_COLORS = {
    "boiler":   "#e08214",
    "hp":       "#4575b4",
    "tes_dch":  "#74add1",
    "tes_ch":   "#d73027",
    "demand":   "#000000",
    "dump":     "#969696",
}

# ── rcParams ──────────────────────────────────────────────────────────────────
RC = {
    # font
    "font.family":        "sans-serif",
    "font.sans-serif":    ["Arial", "Helvetica Neue", "DejaVu Sans"],
    "font.size":          8,
    "axes.titlesize":     8,
    "axes.labelsize":     8,
    "xtick.labelsize":    7,
    "ytick.labelsize":    7,
    "legend.fontsize":    7,
    "legend.title_fontsize": 7,
    # lines
    "lines.linewidth":    1.0,
    "axes.linewidth":     0.6,
    "xtick.major.width":  0.6,
    "ytick.major.width":  0.6,
    "xtick.minor.width":  0.4,
    "ytick.minor.width":  0.4,
    "xtick.major.size":   3,
    "ytick.major.size":   3,
    "xtick.minor.size":   1.5,
    "ytick.minor.size":   1.5,
    # layout
    "figure.dpi":         150,
    "savefig.dpi":        600,
    "savefig.bbox":       "tight",
    "savefig.pad_inches": 0.02,
    # grid
    "axes.grid":          True,
    "grid.linewidth":     0.4,
    "grid.alpha":         0.5,
    "grid.color":         "#cccccc",
    "axes.axisbelow":     True,
    # spines
    "axes.spines.top":    False,
    "axes.spines.right":  False,
}


def apply():
    """Apply Applied Energy rcParams globally."""
    mpl.rcParams.update(RC)


def fig(ncols=1, nrows=1, width=None, height=None, **kwargs):
    """Return (fig, axes) pre-styled for Applied Energy."""
    apply()
    w = width or (W1 if ncols == 1 else W2)
    h = height or min(w * 0.75 * nrows / max(ncols, 1), HMAX)
    return plt.subplots(nrows, ncols, figsize=(w, h), **kwargs)


def save(fig, path_stem, formats=("pdf", "png", "pgf")):
    """Save figure to one or more formats."""
    import pathlib
    p = pathlib.Path(path_stem)
    save_figure_bundle(fig, p, formats=formats, raster_dpi=600)
    plt.close(fig)


def label_bars(ax, bars, fmt="{:.0f}", fontsize=6, pad=2):
    """Annotate bar tops with values."""
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + pad,
                fmt.format(h),
                ha="center", va="bottom", fontsize=fontsize,
            )


def delta_annotation(ax, x_ref, x_other, y, delta_pct, fontsize=6, color="k"):
    """Draw Δ% annotation between two bar positions."""
    ax.annotate(
        f"Δ {delta_pct:+.1f}%",
        xy=(x_other, y), xytext=(x_other, y * 1.05),
        fontsize=fontsize, color=color, ha="center", va="bottom",
    )
