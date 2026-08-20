"""
R1.6 zone-clustering figure (Applied Energy house style, 600 dpi PNG+PDF).

With total sum(U*L) conserved across all clusterings (producer j_1 held as its own zone), the
residual cost spread from zone aggregation is a PURE ROUTING effect. This figure places that
routing effect against the decomposition's own spatial term (the topology main effect,
decomposition_live.csv) and the loss main effect, on a log scale -- showing that clustering
choice is ~2 orders of magnitude below even the (already small) topology effect, and ~3 below
loss. R1.6 thus independently corroborates the central decomposition: loss dominates; geometry
(topology, and a fortiori zone routing) is negligible.

Reads results/v2/analysis/{r16_clustering_costs.csv, decomposition_live.csv}.
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
matplotlib.rcParams.update({"font.family": "serif",
                            "font.serif": ["STIXGeneral", "STIX Two Text", "Times New Roman"],
                            "mathtext.fontset": "stix"})
BLUE_D, BLUE_M, BLUE_L, GREY = "#08306B", "#2171B5", "#6BAED6", "#9AA7B0"


def main():
    d = pd.read_csv(A / "r16_clustering_costs.csv", keep_default_na=False)
    d["econ_cost_eur"] = d["econ_cost_eur"].astype(float)
    orig = d[d.name == "L2_orig"]["econ_cost_eur"].iloc[0]
    spread = float(d["econ_cost_eur"].max() - d["econ_cost_eur"].min())   # full routing spread, EUR
    nsd = float(d[d.kind == "null"]["econ_cost_eur"].std())

    dec = pd.read_csv(A / "decomposition_live.csv").set_index("term")["eur"]
    loss_eur = abs(float(dec["loss_main"]))
    topo_eur = abs(float(dec["topo_main"]))
    total_gap = float(dec["total"])

    # |cost effect| in EUR, log scale
    labels = ["Loss\n(visibility)", "Topology\n(routing, resolved)", "Zone clustering\n(routing choice)"]
    vals = [loss_eur, topo_eur, max(spread, 1.0)]
    pcts = [100 * v / total_gap for v in (loss_eur, topo_eur, spread)]
    colors = [BLUE_M, BLUE_D, BLUE_L]

    fig, ax = plt.subplots(figsize=(AE_SINGLE_COLUMN_IN, 2.1))
    y = np.arange(len(labels))[::-1]
    ax.barh(y, vals, color=colors, edgecolor="k", lw=0.4, height=0.58, log=True)
    for yi, v, p in zip(y, vals, pcts):
        txt = f"{v:,.0f} EUR ({p:.2g}%)" if p >= 0.01 else f"{v:,.0f} EUR (<0.01%)"
        ax.text(v * 1.5, yi, txt, va="center", fontsize=7.2)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlabel("Cost effect on the copperplate-to-baseline gap (EUR/yr, log scale)")
    ax.set_xlim(1, loss_eur * 12)
    fig.tight_layout()
    save_figure_bundle(fig, FIG / "F_r16_clustering", formats=("png", "pdf"), raster_dpi=600)
    plt.close(fig)
    print(f"wrote F_r16_clustering: loss {loss_eur:,.0f}€ / topo {topo_eur:,.0f}€ / "
          f"routing {spread:,.0f}€ (null sd {nsd:,.1f}€)")


if __name__ == "__main__":
    main()
