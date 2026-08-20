"""Solver-time / fidelity trade-off figure (Applied Energy style).
Values from tab_computation (run meta.json): solve time and model size per solved level.
Output: results/v2/figures/F_solvetime.{png,pdf}
"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.paper.mpl_export import AE_SINGLE_COLUMN_IN, apply_ae_style, save_figure_bundle
apply_ae_style(matplotlib)
matplotlib.rcParams.update({"font.family": "serif",
                            "font.serif": ["STIXGeneral", "STIX Two Text", "Times New Roman"],
                            "mathtext.fontset": "stix"})
BLUE_D, BLUE_M, BLUE_L, GREY = "#08306B", "#2171B5", "#6BAED6", "#9AA7B0"

levels = [r"$\mathrm{CP}$", r"$\mathrm{CP{+}L}$", r"$\mathrm{ND^0}$",
          r"$\mathrm{L1}$", r"$\mathrm{L3}$", r"$\mathrm{L6}$"]
solve_min = [3, 3, 4, 5, 9, 9]
nvars_M = [0.21, 0.21, 2.27, 2.27, 3.15, 3.15]
# colour: the loss step (up to the L1 baseline) vs the inert extras beyond it
cols = [BLUE_L, BLUE_L, BLUE_M, BLUE_M, BLUE_D, BLUE_D]

fig, ax = plt.subplots(figsize=(AE_SINGLE_COLUMN_IN, 2.6))
x = np.arange(len(levels))
ax.bar(x, solve_min, width=0.66, color=cols, edgecolor="k", lw=0.4)
for xi, v, nv in zip(x, solve_min, nvars_M):
    ax.text(xi, v + 0.15, f"{nv:.2f}M", ha="center", va="bottom", fontsize=6.2, color="#33475b")
ax.axvline(3.5, color=GREY, ls="--", lw=0.8)
ax.text(3.35, 9.8, "decision-relevant\nstep reached (L1)", fontsize=6.4, ha="right",
        va="top", color="#33475b")
ax.set_xticks(x); ax.set_xticklabels(levels)
ax.set_ylabel("Solve time (min)")
ax.set_ylim(0, 10.5)
ax.set_title("", fontsize=1)
fig.tight_layout()
save_figure_bundle(fig, ROOT / "results/v2/figures/F_solvetime", formats=("png", "pdf"), raster_dpi=600)
print("wrote F_solvetime")
