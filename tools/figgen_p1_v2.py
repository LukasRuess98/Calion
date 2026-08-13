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

TEAL, NAVY, SILVER, AMBER, RED = "#009B77", "#003E6E", "#8C9EA8", "#E8A33D", "#C1272D"
PAT = re.compile(r"synth_n(?P<n>\d+)_L(?P<L>[\dp]+?)km_hi(?P<hi>[\dp]+)_s(?P<s>\d+)h")


def _save(fig, stem):
    save_figure_bundle(fig, FIG / stem, formats=("png", "pdf"), raster_dpi=600)
    plt.close(fig)
    print("wrote", stem)


def f_decomp():
    d = pd.read_csv(A / "decomposition_live.csv").set_index("term")["pct_of_total"]
    s = pd.read_csv(A / "synth_factorial_decomposition.csv")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(AE_DOUBLE_COLUMN_IN, 2.7))
    # (a) Memmingen exact decomposition
    terms = ["loss_main", "topo_main", "interaction"]
    vals = [d[t] for t in terms]
    labels = ["Loss\n(visibility)", "Topology\n(routing)", "Interaction"]
    bars = ax1.bar(labels, vals, color=[TEAL, NAVY, SILVER], width=0.6, edgecolor="k", lw=0.4)
    ax1.axhline(0, color="k", lw=0.6)
    for b, v in zip(bars, vals):
        ax1.text(b.get_x() + b.get_width() / 2, v + (2 if v >= 0 else -4),
                 f"{v:.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
    ax1.set_ylabel("Share of cost gap (%)")
    ax1.set_title("(a) Memmingen, exact decomposition", fontsize=9)
    ax1.set_ylim(-10, 105)
    # (b) synthetic distribution
    ax2.boxplot([s["loss_pct_of_total"], s["topo_pct_of_total"]], labels=["Loss", "Topology"],
                widths=0.5, patch_artist=True,
                boxprops=dict(facecolor=SILVER, color="k", lw=0.5),
                medianprops=dict(color=RED, lw=1.2), flierprops=dict(marker=".", ms=3))
    ax2.axhline(100, color=TEAL, lw=0.8, ls="--", alpha=0.7)
    ax2.axhline(0, color=NAVY, lw=0.8, ls="--", alpha=0.7)
    ax2.set_ylabel("Share of cost gap (%)")
    ax2.set_title("(b) Synthetic factorial (135 networks)", fontsize=9)
    fig.tight_layout()
    _save(fig, "F_decomp")


def f_regret():
    r = pd.read_csv(A / "regret_decomp.csv").set_index("level")
    order = [l for l in ["CP", "CP+L", "ND0", "L1"] if l in r.index]
    disp = {"CP": "CP", "CP+L": "CP+L", "ND0": r"ND$^0$", "L1": "L1"}
    x = np.arange(len(order)); wd = 0.38
    fig, ax = plt.subplots(figsize=(AE_SINGLE_COLUMN_IN, 2.7))
    bias = [r.loc[l, "bias_pct"] for l in order]
    reg = [r.loc[l, "regret_pct"] for l in order]
    ax.bar(x - wd/2, bias, wd, label="Estimation bias", color=SILVER, edgecolor="k", lw=0.4)
    ax.bar(x + wd/2, reg, wd, label="Decision regret", color=TEAL, edgecolor="k", lw=0.4)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xticks(x); ax.set_xticklabels([disp[l] for l in order])
    ax.set_ylabel("% of baseline operating cost")
    ax.legend(frameon=False, fontsize=7.5, loc="upper left")
    # annotate the opposite-sign copperplate
    ax.annotate("opposite\nsigns", xy=(0 + wd/2, r.loc["CP", "regret_pct"]),
                xytext=(0.7, 30), fontsize=7.5, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED, lw=0.8))
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
    for n, c in zip([5, 15, 30], [TEAL, NAVY, AMBER]):
        sub = s[s["n"] == n]
        ax.scatter(sub["L_km"], sub["total_pct"], s=22, color=c, label=f"$n={n}$",
                   edgecolor="k", lw=0.3, alpha=0.85)
    ax.set_xscale("log")
    ax.set_xlabel("Trunk pipe length (km, log)")
    ax.set_ylabel("Loss burden (% of cost)")
    ax.legend(frameon=False, fontsize=7.5, title="nodes", title_fontsize=7.5)
    ax.text(0.03, 0.95, "a frozen loss adder\ncannot span this range",
            transform=ax.transAxes, fontsize=7.5, va="top", color=RED)
    fig.tight_layout()
    _save(fig, "F_drift")


def f_tsup():
    t = pd.read_csv(A / "tsup_sensitivity.csv")
    fig, ax = plt.subplots(figsize=(AE_SINGLE_COLUMN_IN, 2.7))
    ax.plot(t["offset_K"], t["loss_cost_eur"] / 1e3, "-o", color=TEAL, ms=3, label="Loss cost")
    ax.plot(t["offset_K"], t["pump_cost_eur"] / 1e3, "-s", color=NAVY, ms=3, label="Pump cost")
    ax.plot(t["offset_K"], t["tsup_cost_eur"] / 1e3, "-^", color=RED, ms=3, label="Total")
    opt = t.loc[t[t.velocity_viol_steps == 0]["tsup_cost_eur"].idxmin()]
    ax.axvline(opt["offset_K"], color=SILVER, ls="--", lw=0.8)
    ax.axvspan(20, t["offset_K"].max(), color=RED, alpha=0.08)
    ax.text(20.3, ax.get_ylim()[1]*0.55, "velocity\nlimit", fontsize=7, color=RED, va="top")
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
    # decision regions
    ax.axhspan(0, 10, color=TEAL, alpha=0.07)
    ax.axhspan(10, 30, color=AMBER, alpha=0.07)
    ax.axhspan(30, 100, color=RED, alpha=0.07)
    ax.text(df["lambda"].min(), 5, "copperplate\n/ adder ok", fontsize=6.5, va="center", color=TEAL)
    ax.text(df["lambda"].min(), 20, "adder, calibrate", fontsize=6.5, va="center", color="#9a6a00")
    ax.text(df["lambda"].min(), 45, "resolve nodes", fontsize=6.5, va="center", color=RED)
    ax.plot(lam, curve, "-", color=NAVY, lw=1.4, label=r"$b=\lambda/(1{+}\lambda)$ (physics)")
    ax.scatter(syn["lambda"], syn["b_meas_pct"], s=16, color=SILVER, edgecolor="k",
               lw=0.3, label="synthetic (135)", zorder=3)
    if len(mem):
        ax.scatter(mem["lambda"], mem["b_meas_pct"], s=55, color=RED, marker="*",
                   edgecolor="k", lw=0.5, label="Memmingen", zorder=4)
    ax.set_xscale("log")
    ax.set_xlabel(r"loss number $\lambda = $ annual loss / annual demand")
    ax.set_ylabel("cost gap a copperplate misses (%)")
    ax.set_ylim(0, 75)
    ax.legend(frameon=False, fontsize=6.8, loc="lower right")
    fig.tight_layout()
    _save(fig, "F_rule")


def main():
    f_decomp(); f_regret(); f_drift(); f_tsup(); f_rule()
    print("figures ->", FIG)


if __name__ == "__main__":
    main()
