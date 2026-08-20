"""Memmingen network topology (native, STIX font) from Memmingen_L3_MILP.yaml.
Radial tree: 15 junctions (j_1 producer hub .. j_15), 27 consumers, DN-coloured pipes.
Output: results/v2/figures/F_network.{png,pdf}
"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.paper.mpl_export import AE_DOUBLE_COLUMN_IN, apply_ae_style, save_figure_bundle
apply_ae_style(matplotlib)
matplotlib.rcParams.update({"font.family": "serif",
                            "font.serif": ["STIXGeneral", "STIX Two Text", "Times New Roman"],
                            "mathtext.fontset": "stix"})

# topology from the config (parent -> children), and pipe diameters (mm)
children = {"j_1": ["j_2"], "j_2": ["j_3"], "j_3": ["j_4", "j_9"], "j_4": ["j_5"],
            "j_5": ["j_6", "j_7"], "j_7": ["j_8"], "j_9": ["j_10"], "j_10": ["j_11"],
            "j_11": ["j_12"], "j_12": ["j_13"], "j_13": ["j_14", "j_15"]}
dn = {("j_1", "j_2"): 250, ("j_2", "j_3"): 200, ("j_3", "j_4"): 250, ("j_3", "j_9"): 250,
      ("j_4", "j_5"): 250, ("j_5", "j_6"): 200, ("j_5", "j_7"): 65, ("j_7", "j_8"): 65,
      ("j_9", "j_10"): 300, ("j_10", "j_11"): 300, ("j_11", "j_12"): 300,
      ("j_12", "j_13"): 250, ("j_13", "j_14"): 125, ("j_13", "j_15"): 100}
consumers = {"j_1": ["V_1"], "j_2": ["V_2"], "j_3": ["V_3"], "j_4": ["V_4", "V_5", "V_6", "V_7"],
             "j_5": ["V_8", "V_9"], "j_6": ["V_10", "V_11", "V_12"], "j_7": ["V_13"],
             "j_8": ["V_14"], "j_9": ["V_15", "V_16"], "j_10": ["V_17"], "j_11": ["V_18"],
             "j_12": ["V_19", "V_20", "V_21"], "j_13": ["V_22", "V_23", "V_24"],
             "j_14": ["V_25", "V_26"], "j_15": ["V_27"]}

# tidy-tree layout: x = depth (left->right), y = leaf order
pos = {}
_leaf = [0.0]
def layout(node, depth):
    kids = children.get(node, [])
    if not kids:
        y = _leaf[0]; _leaf[0] += 1.0
    else:
        ys = [layout(k, depth + 1) for k in kids]
        y = sum(ys) / len(ys)
    pos[node] = (depth, y)
    return y
layout("j_1", 0)

DN_ORDER = [300, 250, 200, 125, 100, 65]
DN_COL = {300: "#08306B", 250: "#2171B5", 200: "#4292C6", 125: "#6BAED6", 100: "#9ECAE1", 65: "#C6DBEF"}
DN_LW = {300: 3.4, 250: 2.7, 200: 2.1, 125: 1.5, 100: 1.2, 65: 0.9}

fig, ax = plt.subplots(figsize=(AE_DOUBLE_COLUMN_IN, 3.9))
# pipes
for (u, v), d in dn.items():
    x0, y0 = pos[u]; x1, y1 = pos[v]
    ax.plot([x0, x1], [y0, y1], color=DN_COL[d], lw=DN_LW[d], solid_capstyle="round", zorder=2)
# consumers (small light dots fanned just left of / around each junction)
for j, vs in consumers.items():
    x, y = pos[j]
    n = len(vs)
    for i, vname in enumerate(vs):
        dy = (i - (n - 1) / 2) * 0.26
        cx, cy = x - 0.32, y + dy
        ax.plot([x, cx], [y, cy], color="#B8C4CE", lw=0.5, zorder=1)
        ax.scatter(cx, cy, s=26, color="#D6E4F0", edgecolors="#5B6B78", lw=0.4, zorder=3)
        ax.annotate(vname.replace("V_", "V$_{") + "}$", (cx, cy), fontsize=4.4,
                    ha="center", va="center", zorder=4)
# junctions
for j, (x, y) in pos.items():
    hub = (j == "j_1")
    ax.scatter(x, y, s=210 if hub else 150, color="white",
               edgecolors="#08306B", lw=1.6 if hub else 1.0, zorder=5)
    if hub:
        ax.scatter(x, y, s=310, facecolors="none", edgecolors="#08306B", lw=1.0, zorder=5)
    ax.annotate(j.replace("j_", "j$_{") + "}$", (x, y), fontsize=5.6, ha="center",
                va="center", zorder=6)
ax.annotate("production hub j$_1$\n(CHP, TES, gas & biomass\nboilers, HP, e-boiler)",
            pos["j_1"], textcoords="offset points", xytext=(2, 26), fontsize=5.6,
            ha="left", va="bottom")
# DN legend
handles = [Line2D([0], [0], color=DN_COL[d], lw=DN_LW[d], label=f"DN{d}") for d in DN_ORDER]
handles += [Line2D([0], [0], marker="o", color="white", markerfacecolor="white",
                   markeredgecolor="#08306B", label="junction (j)", lw=0, markersize=6),
            Line2D([0], [0], marker="o", color="white", markerfacecolor="#D6E4F0",
                   markeredgecolor="#5B6B78", label="consumer (V)", lw=0, markersize=5)]
ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.9,
          fontsize=5.8, ncol=2, handlelength=1.4, columnspacing=1.0)
ax.set_axis_off()
ax.margins(0.04)
fig.tight_layout()
save_figure_bundle(fig, ROOT / "results/v2/figures/F_network", formats=("png", "pdf"), raster_dpi=600)
print("wrote F_network")
