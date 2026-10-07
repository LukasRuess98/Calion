"""Palette approval swatch (spec B.1: "Liefere Hex-Liste + Vorschau-Farbstreifen
zur Freigabe, BEVOR die Palette in F2, F4 oder F7 verwendet wird").

All six colors in `_style.py` are now read from a real Fraunhofer PPTX theme
(``ppt/theme/theme1.xml``), not invented — see `_style.py`'s module docstring
for the source and the recomputed CIE76 ΔE distances. This script renders them
as one labeled color strip so approval/rejection can happen in one look before
F2/F4/F5/F6/F7 are treated as final. What is still open: the teal/cyan pair is
"adjacent-safe only" (close to blue in Lab space) and none of this has been run
through a dedicated CVD simulator — flag that explicitly, don't claim more than
was actually checked.

Usage:  python scripts/paper_2/figures/fig_palette_preview.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _style  # noqa: E402


def _row_swatch(ax, colors: list[str], labels: list[str], title: str) -> None:
    n = len(colors)
    for i, (c, lab) in enumerate(zip(colors, labels)):
        ax.add_patch(plt.Rectangle((i, 0), 0.92, 1, facecolor=c, edgecolor="white", linewidth=1.5))
        ax.text(i + 0.46, 0.62, c, ha="center", va="center", fontsize=7.5,
                color=_style.SURFACE, fontweight="bold")
        ax.text(i + 0.46, 0.28, lab, ha="center", va="center", fontsize=6.8,
                color=_style.SURFACE)
    ax.set_xlim(0, n)
    ax.set_ylim(0, 1)
    ax.set_axis_off()
    ax.set_title(title, fontsize=9, loc="left", pad=4)


def _ramp_swatch(ax, colors: list[str], title: str) -> None:
    cmap = LinearSegmentedColormap.from_list("preview", colors, N=256)
    ax.imshow([list(range(256))], cmap=cmap, aspect="auto")
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_title(title, fontsize=9, loc="left", pad=4)


def build_palette_preview() -> None:
    print("Palette preview swatch (spec B.1 approval gate):")
    _style.apply_rcparams()

    core_labels = ["real theme", "real theme", "real theme", "real theme"]
    ext_labels = ["real theme, adjacent-safe only"] * 2

    fig, axes = plt.subplots(5, 1, figsize=(_style.COL_DOUBLE_IN, 5.6),
                             gridspec_kw={"height_ratios": [1, 1, 0.4, 0.4, 0.4],
                                          "hspace": 0.95})
    _row_swatch(axes[0], _style.CATEGORICAL_CORE, core_labels,
               "Categorical - core (slots 1-4): all-pairs safe, "
               "min pairwise ΔE76 = 51.0 (green-blue)")
    _row_swatch(axes[1], _style.CATEGORICAL[4:], ext_labels,
               "Categorical - extended (slots 5-6): teal/cyan sit close to blue "
               "(ΔE ~22-23) - bar/line with direct labels only, NOT scatter/maps")
    _ramp_swatch(axes[2], _style.SEQ_GREEN, "Sequential (magnitude) - single Fraunhofer-green hue")
    _ramp_swatch(axes[3], [_style.DIV_NEG, _style.DIV_MID, _style.DIV_POS],
                "Diverging (polarity) - orange (worse, only warm hue in the real theme) "
                "<-> grey <-> green (better)")
    axes[4].axis("off")
    axes[4].text(0, 0.5,
                "Source: real Fraunhofer PPTX theme (not invented). No CVD simulator run yet - "
                "if that matters for print, re-check the teal/cyan/blue cluster before final use.",
                fontsize=7.5, color=_style.INK_SOFT, va="center")
    fig.suptitle("Fraunhofer palette (verified from real PPTX theme) - for approval",
                fontsize=10.5, y=1.0)
    _style.save(fig, "fig_palette_preview_DRAFT")


if __name__ == "__main__":
    build_palette_preview()
