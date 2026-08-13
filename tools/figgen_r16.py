"""
R1.6 zone-clustering sensitivity figure (Applied Energy house style, 600 dpi PNG+PDF).

Reads results/v2/analysis/r16_clustering_costs.csv (from scripts/paper/_run_r16_clustering.py):
the hand-made L2 clustering vs 20 random contiguous 7-zone partitions (null) + 3 deliberate
alternative granularities (coarse-4 / fine-10 / shifted-7 zones). Shows the L2 economic cost
is insensitive to the clustering choice.

Usage: python tools/figgen_r16.py
Output: results/v2/figures/F_r16_clustering.{png,pdf}
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.paper.mpl_export import AE_SINGLE_COLUMN_IN, apply_ae_style, save_figure_bundle

A = ROOT / "results" / "v2" / "analysis"
FIG = ROOT / "results" / "v2" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
apply_ae_style(matplotlib)
TEAL, NAVY, SILVER, AMBER, RED = "#009B77", "#003E6E", "#8C9EA8", "#E8A33D", "#C1272D"


def main():
    d = pd.read_csv(A / "r16_clustering_costs.csv", keep_default_na=False)
    d["econ_cost_eur"] = d["econ_cost_eur"].astype(float)
    orig = d[d.name == "orig"]["econ_cost_eur"].iloc[0]
    nulls = d[d.name.str.startswith("L2_null")]["econ_cost_eur"].to_numpy() / 1e3
    alts = d[d.name.str.startswith("L2_alt")].set_index("name")["econ_cost_eur"].to_dict()
    o = orig / 1e3
    m, sd = nulls.mean(), nulls.std()

    fig, ax = plt.subplots(figsize=(AE_SINGLE_COLUMN_IN, 2.7))
    # null distribution (random 7-zone partitions)
    ax.hist(nulls, bins=8, color=SILVER, edgecolor="k", lw=0.4, alpha=0.85,
            label=f"Null: 20 random 7-zone\npartitions (sd {100*sd/m:.1f}%)")
    ax.axvspan(m - sd, m + sd, color=SILVER, alpha=0.25, zorder=0)
    # hand-made L2
    ax.axvline(o, color=NAVY, lw=1.6, label=f"Reported L2 (7 zones)")
    # alternative granularities
    style = {"L2_alt_coarse4": (TEAL, "4 zones"),
             "L2_alt_fine10": (AMBER, "10 zones"),
             "L2_alt_shift7": (RED, "shifted 7")}
    for k, (c, lab) in style.items():
        if k in alts:
            ax.axvline(alts[k] / 1e3, color=c, lw=1.2, ls="--",
                       label=f"Alt {lab} ({100*(alts[k]-orig)/orig:+.1f}%)")
    ax.set_xlabel("L2 economic cost (k€ / yr)")
    ax.set_ylabel("count (null partitions)")
    ax.set_title("R1.6: L2 cost is insensitive to zone clustering", fontsize=9)
    ax.legend(frameon=False, fontsize=6.3, loc="upper left")
    fig.tight_layout()
    save_figure_bundle(fig, FIG / "F_r16_clustering", formats=("png", "pdf"), raster_dpi=600)
    plt.close(fig)
    print("wrote F_r16_clustering  (orig z=%.2f vs null; alt spread %.1f%% to %.1f%%)"
          % ((o - m) / sd,
             100 * (min(alts.values()) - orig) / orig,
             100 * (max(alts.values()) - orig) / orig))


if __name__ == "__main__":
    main()
