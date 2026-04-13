"""
ECM journal style constants and matplotlib rcParams.
Energy Conversion and Management (Elsevier) figure guidelines.

Usage in every figure script:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from ecm_style import apply_ecm_style, save_figure, DOUBLE_COL_W, ...
    apply_ecm_style()
"""
import matplotlib as mpl

# ── Figure dimensions (inches) ────────────────────────────────────────────────
SINGLE_COL_W = 3.54    # 90 mm  — half-page figures
DOUBLE_COL_W = 7.48    # 190 mm — full-width figures

H_STANDARD   = 3.94    # 100 mm
H_TALL       = 4.33    # 110 mm
H_PIPE       = 4.72    # 120 mm
H_WIDE_SHORT = 2.76    # 70 mm
H_TOPOLOGY   = 3.15    # 80 mm

# ── Font sizes (pt at final print size) ──────────────────────────────────────
FONT_AXIS_LABEL = 9
FONT_TICK       = 8
FONT_TITLE      = 10
FONT_SUPTITLE   = 11
FONT_ANNOTATION = 8
FONT_LEGEND     = 8

# ── Colors (colorblind-safe, distinguishable in grayscale) ───────────────────
C_BOILER  = "#d62728"   # red       — gas boiler
C_HP      = "#1f77b4"   # blue      — heat pump
C_TES_DIS = "#2ca02c"   # green     — storage discharge
C_TES_CHG = "#aec7e8"   # lt. blue  — storage charge
C_DEMAND  = "#1a1a2e"   # near-blk  — heat demand line
C_DUMP    = "#ff7f0e"   # orange    — heat dump

C_L1 = "#1f77b4"   # blue
C_L2 = "#ff7f0e"   # orange
C_L3 = "#2ca02c"   # green

C_CO2_GAS  = "#d62728"   # red   — CO2 from gas
C_CO2_GRID = "#1f77b4"   # blue  — CO2 from grid

# ── matplotlib rcParams ───────────────────────────────────────────────────────
ECM_RC = {
    "font.family":       "sans-serif",
    "font.sans-serif":   ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size":         FONT_AXIS_LABEL,
    "axes.titlesize":    FONT_TITLE,
    "axes.labelsize":    FONT_AXIS_LABEL,
    "xtick.labelsize":   FONT_TICK,
    "ytick.labelsize":   FONT_TICK,
    "legend.fontsize":   FONT_LEGEND,
    "axes.linewidth":    0.6,
    "grid.linewidth":    0.4,
    "grid.alpha":        0.3,
    "lines.linewidth":   1.2,
    "patch.linewidth":   0.5,
    "figure.dpi":        300,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "axes.spines.top":   False,
    "axes.spines.right": False,
}


def apply_ecm_style() -> None:
    """Apply ECM rcParams globally. Call once at module level in each script."""
    mpl.rcParams.update(ECM_RC)


def save_figure(fig, stem, formats=("pdf", "png")) -> None:
    """Save fig to each format. stem is a Path or str without extension."""
    for fmt in formats:
        path = f"{stem}.{fmt}"
        fig.savefig(path, bbox_inches="tight")
        print(f"  Saved: {path}")
