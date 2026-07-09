"""Shared style + output conventions for the Paper 2 publication figure set.

This is the single source of truth for the *canonical* Paper 2 figure system
(user decision 2026-07-08): Fraunhofer-IPA palette, English labels, vector +
raster export to ``results/paper2_figures/``. All new T1–T5 / F1–F9 generators
import from here; the older ``fig_p2_paperset.py`` (F-P2-11…14) is to be folded
into this system.

Palette provenance / open item
-------------------------------
Primary two colours are confirmed from the spec:
    Fraunhofer green  #179C7D   (primary)
    Fraunhofer blue   #005B7F   (secondary)
The additional categorical hues below are a *proposed* extension derived to sit
in the Fraunhofer CI family AND to pass the dataviz CVD/contrast validator
(``dataviz/scripts/validate_palette.js``). They are flagged for user approval
before final use (spec B.1: "Zusatzfarben … mir zur Freigabe vorlegen").

Font
----
The Fraunhofer corporate face is Frutiger (licensed, not bundled). We request it
first and fall back to Arial → DejaVu Sans, so the figures render everywhere and
upgrade automatically on a machine that has Frutiger installed. Swap FONT_STACK
once the exact face is extracted from the PowerPoint template.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Output location (spec B.1, user-confirmed) ───────────────────────────────
_ROOT = Path(__file__).resolve().parents[3]
FIG_DIR = _ROOT / "results" / "paper2_figures"

# ── Fraunhofer IPA palette ───────────────────────────────────────────────────
# Confirmed brand anchors
FHG_GREEN = "#179C7D"   # Fraunhofer primary green
FHG_BLUE = "#005B7F"    # Fraunhofer dark blue

# Proposed CI-family accents (pending approval) — used only when >2 categories.
FHG_BORDEAUX = "#A6093D"
FHG_ORANGE = "#F58220"
FHG_PURPLE = "#6C4A9C"
FHG_CYAN = "#37A9DE"
FHG_LIME = "#B2D235"
FHG_YELLOW = "#FDB913"

# Fixed categorical order — assigned by slot, never cycled (dataviz rule).
#
# CATEGORICAL_CORE (slots 1–4) is validated CVD-safe for the strict ALL-PAIRS
# case (maps, scatter, bubble): worst Machado-2009 ΔE = 24.7 (target ≥12), all
# inside the light-mode L band. Caveats, both documented brand/relief conditions:
#   · #005B7F chroma 0.093 is a hair below the 0.10 "reads-gray" floor — it is a
#     brand anchor, kept deliberately; it still separates cleanly under CVD.
#   · #F58220 contrast 2.53:1 vs white is in the relief band — always ships with
#     a direct label (which every Paper 2 figure uses), never colour-alone.
# A 5th all-pairs-distinct hue inside the Fraunhofer family is not achievable
# (pink collides with green ΔE 5.4, violet with navy 10.9), so slots 5–8 are
# ADJACENT-safe only (worst adjacent ΔE 24.2): legal for bar/line/stacked series
# with direct labels, NOT for scatter/maps. Beyond 8, fold into "Other".
CATEGORICAL_CORE = [FHG_GREEN, FHG_BLUE, FHG_BORDEAUX, FHG_ORANGE]
CATEGORICAL = CATEGORICAL_CORE + [FHG_PURPLE, FHG_CYAN, FHG_LIME, FHG_YELLOW]

# Sequential ramp (magnitude) — single Fraunhofer-green hue, light → dark.
SEQ_GREEN = ["#e8f4f0", "#a8dccd", "#5cbfa3", "#179C7D", "#0e6853", "#083a2e"]

# Diverging pair (polarity, e.g. cost reduction vs. baseline): warm ↔ neutral ↔ cool.
# Cool/good pole = Fraunhofer green, warm/bad pole = bordeaux, neutral mid = warm grey.
DIV_NEG = FHG_BORDEAUX    # worse than baseline
DIV_MID = "#f2f1ee"       # neutral
DIV_POS = FHG_GREEN       # better than baseline

# ── Ink / structural tokens (text wears these, never a series colour) ─────────
INK = "#1a1a19"
INK_SOFT = "#52514e"
INK_MUTED = "#86847f"
GRID = "#d8d7d2"
SURFACE = "#ffffff"

FONT_STACK = ["Frutiger", "Frutiger LT Std", "Arial", "Helvetica", "DejaVu Sans"]


def apply_rcparams() -> None:
    """Install the shared Matplotlib rcParams for the figure set."""
    plt.rcParams.update({
        "font.size": 8.5,
        "font.family": "sans-serif",
        "font.sans-serif": FONT_STACK,
        "axes.edgecolor": INK_SOFT,
        "axes.labelcolor": INK,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlecolor": INK,
        "xtick.color": INK_SOFT,
        "ytick.color": INK_SOFT,
        "text.color": INK,
        "grid.color": GRID,
        "grid.linewidth": 0.5,
        "legend.frameon": False,
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "pdf.fonttype": 42,   # embed TrueType, keep text selectable/editable
        "ps.fonttype": 42,
        "svg.fonttype": "none",  # keep text as text in SVG
    })


# ── ECM column widths (spec B.1 open item Q3 — default; adjust if needed) ─────
# Elsevier / ECM single column ≈ 9 cm, double column ≈ 19 cm.
CM = 1 / 2.54
COL_SINGLE_IN = 9.0 * CM
COL_DOUBLE_IN = 19.0 * CM


def save(fig, name: str, *, formats: tuple[str, ...] = ("svg", "pdf", "png")) -> None:
    """Save *fig* to results/paper2_figures/ as vector (SVG, PDF) + PNG@300dpi."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in formats:
        fig.savefig(FIG_DIR / f"{name}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {name}: {', '.join(formats)} -> {FIG_DIR}")
