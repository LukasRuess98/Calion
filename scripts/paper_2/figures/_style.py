"""Shared style + output conventions for the Paper 2 publication figure set.

This is the single source of truth for the *canonical* Paper 2 figure system
(user decision 2026-07-08): Fraunhofer-IPA palette, English labels, vector +
raster export to ``results/paper2_figures/``. All new T1–T5 / F1–F9 generators
import from here; the older ``fig_p2_paperset.py`` (F-P2-11…14) is to be folded
into this system.

Palette provenance
------------------
All six colours below are read directly from a real Fraunhofer PPTX template's
OOXML theme (``ppt/theme/theme1.xml``/``theme4.xml``, ``<a:srgbClr val="...">``),
not invented: green/blue/orange/lime were already right by earlier guess, teal
and cyan replace two earlier guessed hues that were NOT in the actual theme.
No red/bordeaux/purple/yellow exists in that theme, so those three earlier
placeholders are removed rather than kept as unverified extras — see the
diverging-pole note below for how the "negative" pole is now sourced.

Perceptual spacing (plain CIE76 ΔE76 in Lab space, computed from the hex values
above — NOT a CVD simulation): the four CATEGORICAL_CORE colours are mutually
≥51 ΔE apart (green-blue is the closest pair). Teal and cyan sit close to both
blue and each other (ΔE 22-23 blue-teal, teal-cyan) and moderately close to
green (ΔE 29-32) — they are real brand colours but hue-adjacent to blue/green,
so they are ADJACENT-safe only (bar/line/stacked with direct labels), never for
scatter/maps/anything requiring all-pairs discrimination. This has not been run
through a dedicated CVD simulator (Machado/Viénot); if that matters for the
final manuscript figures, re-validate before print, especially for the
teal/cyan/blue cluster (deuteranopia confuses blue-green family hues).

Font
----
The real corporate faces (found in the same theme file) are
"Frutiger LT Com 45 Light" (body) and "Frutiger LT Com 65 Bold" (headings) —
not the earlier guessed "Frutiger LT Std". Licensed, not bundled: FONT_STACK
requests the real name first and falls back to Arial → DejaVu Sans so figures
still render on a machine without the font installed.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Output location (spec B.1, user-confirmed) ───────────────────────────────
_ROOT = Path(__file__).resolve().parents[3]
FIG_DIR = _ROOT / "results" / "paper2_figures"

# ── Fraunhofer IPA palette (verified from the real PPTX theme, see docstring) ──
FHG_GREEN = "#179C7D"   # Fraunhofer primary green
FHG_BLUE = "#005B7F"    # Fraunhofer dark blue
FHG_ORANGE = "#F58220"  # theme accent — only warm hue in the real palette
FHG_TEAL = "#008598"    # theme accent — hue-adjacent to blue, use with care
FHG_CYAN = "#39C1CD"    # theme accent — hue-adjacent to teal/blue, use with care
FHG_LIME = "#B2D235"    # theme accent

# Fixed categorical order — assigned by slot, never cycled (dataviz rule).
#
# CATEGORICAL_CORE (slots 1-4): the four mutually-most-distinct real theme
# colours, min pairwise CIE76 ΔE76 = 51.0 (green-blue) — all-pairs safe for
# maps/scatter/bubble. Slots 5-6 (teal, cyan) are ADJACENT-safe only (bar/line/
# stacked with direct labels): they sit only 22-23 ΔE from blue and each other.
# No 5th/6th all-pairs-distinct hue exists in the real theme (orange and lime
# are the only other candidates and both already used in CORE).
CATEGORICAL_CORE = [FHG_GREEN, FHG_BLUE, FHG_ORANGE, FHG_LIME]
CATEGORICAL = CATEGORICAL_CORE + [FHG_TEAL, FHG_CYAN]

# Sequential ramp (magnitude) — single Fraunhofer-green hue, light → dark.
SEQ_GREEN = ["#e8f4f0", "#a8dccd", "#5cbfa3", "#179C7D", "#0e6853", "#083a2e"]

# Diverging pair (polarity, e.g. cost reduction vs. baseline): warm <-> neutral <-> cool.
# The real theme has no red/bordeaux; orange is its only warm hue, so it takes
# the "worse than baseline" pole (ΔE 99.6 from green — very safe separation).
DIV_NEG = FHG_ORANGE      # worse than baseline
DIV_MID = "#f2f1ee"       # neutral
DIV_POS = FHG_GREEN       # better than baseline

# ── Ink / structural tokens (text wears these, never a series colour) ─────────
INK = "#1a1a19"
INK_SOFT = "#52514e"
INK_MUTED = "#86847f"
GRID = "#d8d7d2"
SURFACE = "#ffffff"

FONT_STACK = ["Frutiger LT Com 45 Light", "Frutiger LT Com", "Frutiger",
             "Arial", "Helvetica", "DejaVu Sans"]


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
