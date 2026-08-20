"""
Paper-1 revision figures (v2, hardened lineage). Built from results/v2/analysis/*.csv in
the Applied Energy house style (scripts/paper/mpl_export.AE_RCPARAMS, 85/170 mm columns,
600 dpi, PNG+PDF+PGF). Reproducible: re-run after any results change.

  F_decomp  loss/topology/interaction (Memmingen) + 135-net synthetic distribution
  F_regret  estimation bias vs decision regret per level (opposite signs) + pricing
  F_drift   loss burden vs pipe length across the factorial (frozen-adder non-transfer)
  F_tsup    supply-temperature forward sensitivity (loss vs pumping; velocity binds)

Usage: python tools/figgen_p1_v2.py
"""
import os
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.paper.mpl_export import (AE_DOUBLE_COLUMN_IN, AE_SINGLE_COLUMN_IN,  # noqa: E402
                                      apply_ae_style, save_figure_bundle)

A = ROOT / "results" / "v2" / "analysis"
FIG = ROOT / "results" / "v2" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
apply_ae_style(matplotlib)
# match the manuscript font (cas-sc uses the STIX family)
matplotlib.rcParams.update({"font.family": "serif",
                            "font.serif": ["STIXGeneral", "STIX Two Text", "Times New Roman"],
                            "mathtext.fontset": "stix"})

# unified blue palette (dark -> pale) + neutral grey
BLUE_D, BLUE_M, BLUE_L, BLUE_P = "#08306B", "#2171B5", "#6BAED6", "#C6DBEF"
GREY = "#9AA7B0"
TEAL, NAVY, SILVER, AMBER, RED = BLUE_M, BLUE_D, GREY, BLUE_L, BLUE_D  # back-compat aliases
PAT = re.compile(r"synth_n(?P<n>\d+)_L(?P<L>[\dp]+?)km_hi(?P<hi>[\dp]+)_s(?P<s>\d+)h")


def _save(fig, stem):
    save_figure_bundle(fig, FIG / stem, formats=("png", "pdf"), raster_dpi=600)
    plt.close(fig)
    print("wrote", stem)


def f_decomp():
    d = pd.read_csv(A / "decomposition_live.csv").set_index("term")["pct_of_total"]
    s = pd.read_csv(A / "synth_factorial_decomposition.csv")
    loss, topo, inter = d["loss_main"], d["topo_main"], d["interaction"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(AE_DOUBLE_COLUMN_IN, 2.7),
                                   gridspec_kw={"width_ratios": [1.4, 1.0]})
    # (a) waterfall: CP -> +loss -> +topology -> +interaction -> L1
    cats = ["Loss\n(visibility)", "Topology\n(routing)", "Interaction", "Total\nL1$-$CP"]
    bottoms = [0.0, loss, loss + topo, 0.0]
    heights = [loss, topo, inter, loss + topo + inter]
    cols = [BLUE_M, BLUE_D, BLUE_L, GREY]
    for i, (bot, h, col) in enumerate(zip(bottoms, heights, cols)):
        ax1.bar(i, h, bottom=bot, width=0.64, color=col, edgecolor="k", lw=0.4)
        lab = f"{h:+.1f}" if i < 3 else f"{h:.0f}"
        ax1.text(i, bot + h + 2.0, lab, ha="center", va="bottom", fontsize=7.5)
    for i, t in enumerate([loss, loss + topo]):           # step connectors
        ax1.plot([i + 0.32, i + 1 - 0.32], [t, t], color="k", lw=0.5, ls=":")
    ax1.axhline(0, color="k", lw=0.6)
    ax1.set_xticks(range(4)); ax1.set_xticklabels(cats)
    ax1.set_ylabel(r"Share of the CP$\to$L1 cost gap (%)")
    ax1.set_title("(a) Memmingen, exact decomposition", fontsize=9)
    ax1.set_ylim(-8, 114)
    # (b) synthetic loss-share distribution
    ax2.hist(s["loss_pct_of_total"], bins=18, color=TEAL, edgecolor="k", lw=0.3, alpha=0.9)
    ax2.axvline(100, color=NAVY, lw=1.0, ls="--")
    ax2.set_xlabel(r"Loss share of cost gap (%)")
    ax2.set_ylabel("Networks")
    ax2.set_title("(b) Synthetic factorial (135)", fontsize=9)
    fig.tight_layout()
    _save(fig, "F_decomp")


def f_regret():
    r = pd.read_csv(A / "regret_decomp.csv").set_index("level")
    order = [l for l in ["CP", "ND0", "CP+L", "CP+Lb", "L1", "L3", "L6"] if l in r.index]
    disp = {"CP": "CP", "CP+L": "CP+L", "CP+Lb": r"CP+L$_b$", "ND0": r"ND$^0$",
            "L1": "L1", "L3": "L3", "L6": "L6"}
    aware = ["CP+L", "CP+Lb", "L1", "L3", "L6"]
    fig, ax = plt.subplots(figsize=(AE_SINGLE_COLUMN_IN, 3.1))
    ax.plot([-20, 12], [-20, 12], color=GREY, lw=1.0, ls="--", zorder=1)
    ax.axhline(0, color="k", lw=0.5, zorder=1); ax.axvline(0, color="k", lw=0.5, zorder=1)
    for l in order:
        x, y = r.loc[l, "bias_pct"], r.loc[l, "regret_pct"]
        loss_blind = abs(y - x) > 5
        ax.scatter(x, y, s=70, color=BLUE_D if loss_blind else BLUE_L,
                   edgecolor="k", lw=0.6, zorder=3)
    ax.annotate(r"CP, ND$^0$", (-14.8, 46.4), textcoords="offset points", xytext=(10, -1),
                fontsize=7.6, va="center")
    ax.set_xlabel(r"Estimation bias (% of baseline cost)")
    ax.set_ylabel(r"Decision regret (% of baseline cost)")
    ax.set_xlim(-19, 11); ax.set_ylim(-7, 51)
    # inset: tight zoom on the loss-aware cluster near the origin; big translucent
    # markers with the level name printed inside (coincident pairs merged)
    clusters = [("CP+L\nCP+L$_b$", -0.66, -0.57), ("L1", 0.0, 0.0), ("L3\nL6", 1.41, 1.40)]
    axin = ax.inset_axes([0.42, 0.30, 0.54, 0.54])
    axin.plot([-2, 3], [-2, 3], color=GREY, lw=0.9, ls="--")
    axin.axhline(0, color="k", lw=0.4); axin.axvline(0, color="k", lw=0.4)
    for name, x, y in clusters:
        axin.scatter(x, y, s=720, color=BLUE_L, alpha=0.5, edgecolor=BLUE_D, lw=0.9, zorder=3)
        axin.annotate(name, (x, y), ha="center", va="center", fontsize=5.6, linespacing=0.9, zorder=5)
    axin.set_xlim(-1.05, 1.95); axin.set_ylim(-1.05, 1.95)
    axin.tick_params(labelsize=6); axin.set_title("zoom near origin", fontsize=6.6)
    ax.indicate_inset_zoom(axin, edgecolor="0.45", lw=0.6)
    fig.tight_layout()
    _save(fig, "F_regret")


def _parse_L(net):
    m = PAT.match(net)
    return float(m.group("L").replace("p", ".")) if m else np.nan


def f_drift():
    s = pd.read_csv(A / "synth_factorial_decomposition.csv")
    s["L_km"] = s["net"].map(_parse_L)
    s["n"] = s["net"].str.extract(r"_n(\d+)_").astype(int)
    fig, ax = plt.subplots(figsize=(AE_SINGLE_COLUMN_IN, 2.7))
    for n, c, m in zip([5, 15, 30], [BLUE_L, BLUE_M, BLUE_D], ["o", "s", "^"]):
        sub = s[s["n"] == n]
        ax.scatter(sub["L_km"], sub["total_pct"], s=26, facecolors="none", edgecolors=c,
                   lw=0.8, marker=m, label=f"$n={n}$")
    ax.set_xscale("log")
    ax.set_xlabel("Trunk pipe length (km, log scale)")
    ax.set_ylabel(r"Loss burden (% of cost)")
    ax.legend(frameon=False, fontsize=7.5, title="nodes", title_fontsize=7.5)
    fig.tight_layout()
    _save(fig, "F_drift")


def f_tsup():
    t = pd.read_csv(A / "tsup_sensitivity.csv")
    fig, ax = plt.subplots(figsize=(AE_SINGLE_COLUMN_IN, 2.7))
    ax.plot(t["offset_K"], t["loss_cost_eur"] / 1e3, "-o", color=BLUE_L, ms=3, label="Loss cost")
    ax.plot(t["offset_K"], t["pump_cost_eur"] / 1e3, "-s", color=BLUE_M, ms=3, label="Pump cost")
    ax.plot(t["offset_K"], t["tsup_cost_eur"] / 1e3, "-^", color=BLUE_D, ms=3, label="Total")
    opt = t.loc[t[t.velocity_viol_steps == 0]["tsup_cost_eur"].idxmin()]
    ax.axvline(opt["offset_K"], color=GREY, ls="--", lw=0.8)
    ax.axvspan(20, t["offset_K"].max(), color=GREY, alpha=0.18)
    ax.text(20.3, ax.get_ylim()[1]*0.55, "velocity\nlimit", fontsize=7, color="#33475b", va="top")
    ax.text(opt["offset_K"], ax.get_ylim()[1]*0.9, f"optimum\n{opt['offset_K']:.1f} K",
            fontsize=7, ha="center", color="k")
    ax.set_xlabel("Supply-temperature reduction (K)")
    ax.set_ylabel("Annual cost (kEUR)")
    ax.legend(frameon=False, fontsize=7.5)
    fig.tight_layout()
    _save(fig, "F_tsup")


def f_rule():
    df = pd.read_csv(A / "fidelity_rule.csv").dropna(subset=["lambda", "b_meas_pct"])
    syn = df[df.net != "Memmingen"]; mem = df[df.net == "Memmingen"]
    lam = np.logspace(np.log10(df["lambda"].min() * 0.8), np.log10(df["lambda"].max() * 1.2), 200)
    curve = 100 * lam / (1 + lam)
    fig, ax = plt.subplots(figsize=(AE_SINGLE_COLUMN_IN, 2.8))
    # decision regions: shades of grey (technical look), boundaries drawn as thin rules
    ax.axhspan(0, 10, color="0.91", zorder=0)
    ax.axhspan(10, 30, color="0.82", zorder=0)
    ax.axhspan(30, 100, color="0.72", zorder=0)
    for yb in (10, 30):
        ax.axhline(yb, color="0.55", lw=0.5, zorder=1)
    xr = df["lambda"].max()
    ax.text(xr, 5, "copperplate ok", fontsize=6.3, va="center", ha="right", color="0.20")
    ax.text(xr, 20, "calibrate an adder", fontsize=6.3, va="center", ha="right", color="0.20")
    ax.text(xr, 45, "resolve nodes", fontsize=6.3, va="center", ha="right", color="0.20")
    ax.plot(lam, curve, "-", color="k", lw=1.4, label=r"$b=\lambda/(1{+}\lambda)$ (physics)")
    ax.scatter(syn["lambda"], syn["b_meas_pct"], s=15, facecolors="none", edgecolors="#1a3a5c",
               lw=0.6, alpha=0.8, label="synthetic (135)", zorder=3)
    if len(mem):
        ax.scatter(mem["lambda"], mem["b_meas_pct"], s=40, color="k", marker="o",
                   edgecolor="k", lw=0.5, label="Memmingen", zorder=4)
    ax.set_xscale("log")
    ax.set_xlabel(r"loss number $\lambda = $ annual loss / annual demand")
    ax.set_ylabel("cost gap a copperplate misses (%)")
    ax.set_ylim(0, 75)
    ax.legend(frameon=False, fontsize=6.6, loc="upper left")
    fig.tight_layout()
    _save(fig, "F_rule")


def main():
    f_decomp(); f_regret(); f_drift(); f_tsup(); f_rule()
    print("figures ->", FIG)


if __name__ == "__main__":
    main()
