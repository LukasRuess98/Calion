"""Draft figures (spec section 9) from the result files. Draft quality, no manuscript styling.

    python -m scripts.dhn_study.central_tes.figures

Output: results/central_tes/figures/*.png (gitignored with results/). Figure 1 (system concept) is a drawing and is
left to the writing phase.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import config as C  # noqa: E402
from . import inputs  # noqa: E402
from .milp import PLANTS  # noqa: E402

SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.6,
                     "legend.frameon": False, "figure.dpi": 130})
WEEKS = {"winter": ("2025-01-13", "2025-01-20"), "transition": ("2025-04-07", "2025-04-14"), "summer": ("2025-07-07", "2025-07-14")}
CODES = ["F000", "F001", "F100", "F010", "F110", "F101", "F011", "F111"]


def _r(cfg):
    return C.root() / cfg["paths"]["results"]


def fig2_data(cfg, x, out):
    fig, ax = plt.subplots(4, 3, figsize=(11, 7.5), sharex="col")
    rows = [("D", "Demand incl. losses [MW]"), ("T_VL", "Supply temperature [°C]"), ("Q_A_avail", "Partner A heat available [MW]"),
            ("price", "Day-ahead price [EUR/MWh]")]
    for j, (name, (a, b)) in enumerate(WEEKS.items()):
        w = x.loc[a:b]
        for i, (c, lab) in enumerate(rows):
            ax[i, j].plot(w.index, w[c], color=SLOTS[0])
            if j == 0:
                ax[i, j].set_ylabel(lab)
        ax[0, j].set_title(f"{name} week ({a})", color=INK)
        ax[-1, j].tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out / "fig2_data_context.png")
    plt.close(fig)


def fig3_factorial(cfg, out):
    r = _r(cfg) / "scenario_runs"
    sh = json.loads((r / "shapley.json").read_text())
    keys = [k for k in sh if k == "E" or k.startswith("H_")]
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    codes = [c for c in CODES if c != "F000"]
    w = 0.8 / len(keys)
    for i, k in enumerate(keys):
        v = [sh[k]["v"][c] / 1e3 for c in codes]
        ax[0].bar(np.arange(len(codes)) + i * w, v, w * 0.92, color=SLOTS[i], label="Mode E" if k == "E" else f"Mode H ({k[2:]})")
    ax[0].set_xticks(np.arange(len(codes)) + w * (len(keys) - 1) / 2, codes)
    ax[0].set_ylabel("v(S) = C(F000) − C(S) [kEUR/a]")
    ax[0].legend()
    players = ["A", "B", "TES"]
    for i, k in enumerate(keys):
        ax[1].bar(np.arange(3) + i * w, [sh[k]["phi"][p] / 1e3 for p in players], w * 0.92, color=SLOTS[i])
    ax[1].set_xticks(np.arange(3) + w * (len(keys) - 1) / 2, ["partner A + HP", "partner B EB", "TES"])
    ax[1].set_ylabel("Shapley value [kEUR/a]")
    fig.tight_layout()
    fig.savefig(out / "fig3_factorial_shapley.png")
    plt.close(fig)


def fig4_week(cfg, out, code="F111-E", week="winter"):
    p = _r(cfg) / "scenario_runs" / code / "milp_timeseries.parquet"
    s = pd.read_parquet(p).loc[slice(*WEEKS[week])]
    fig, ax = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
    stack = [s[f"Q_{g}"] for g in PLANTS] + [s["Q_central"].clip(lower=0)]
    ax[0].stackplot(s.index, *stack, labels=[*PLANTS, "central (S)"], colors=SLOTS[:6], edgecolor="white", linewidth=0.3)
    ax[0].plot(s.index, s["D"], color=INK, lw=1.0, label="demand")
    ax[0].set_ylabel("Heat [MW]")
    ax[0].legend(ncol=7, fontsize=7, loc="upper left")
    for i, md in enumerate(["grid", "tes", "casc_grid", "casc_tes"]):
        ax[1].plot(s.index, s[f"Q_HP_{md}"], color=SLOTS[i], label=f"HP {md}")
    ax[1].plot(s.index, s["P_EB"], color=SLOTS[4], label="EB power")
    ax[1].set_ylabel("HP heat / EB power [MW]")
    ax[1].legend(ncol=5, fontsize=7)
    ax[2].plot(s.index, s["E"], color=SLOTS[0], label="SOC")
    ax[2].plot(s.index, s["E_max"], color=INK2, lw=0.8, ls="--", label="E_max")
    ax[2].set_ylabel("TES [MWh]")
    ax[2].legend(fontsize=7)
    ax[3].plot(s.index, s["price"], color=SLOTS[1])
    ax[3].set_ylabel("Price [EUR/MWh]")
    fig.tight_layout()
    fig.savefig(out / f"fig4_operation_{code}_{week}.png")
    plt.close(fig)


def fig5_hydraulic(cfg, out, v="A"):
    r = _r(cfg) / "scenario_runs"
    cases = {"F000-E": r / "F000-E" / f"hydraulic_timeseries_{v}.parquet", "F111-E": r / "F111-E" / f"hydraulic_timeseries_{v}.parquet",
             "F111-H": r / "F111-H" / v / "hydraulic_timeseries.parquet"}
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.6))
    for i, (k, p) in enumerate(cases.items()):
        if not p.exists():
            continue
        e = pd.read_parquet(p)
        n = np.arange(len(e)) / len(e) * 100
        ax[0].plot(n, np.sort(e["dp_KWK"])[::-1], color=SLOTS[i], label=k)
        dm = np.sort(e["dp_MVA"].dropna().to_numpy())[::-1]
        ax[1].plot(np.arange(len(dm)) / len(dm) * 100, dm, color=SLOTS[i], label=k)
        ax[2].plot(n, np.sort(e["m_S"])[::-1], color=SLOTS[i], label=k)
    ax[0].axhline(4.0, color=INK2, ls=":", lw=1)
    ax[0].set(ylabel="required KWK Δp [bar]", xlabel="hours [% of year]")
    ax[1].axhline(7.5, color=INK2, ls=":", lw=1)
    ax[1].set(ylabel="MVA Δp [bar] (anchored)", xlabel="hours [% of year, MVA on]")
    ax[2].set(ylabel="net injection at S [kg/s]", xlabel="hours [% of year]")
    ax[0].legend()
    fig.tight_layout()
    fig.savefig(out / f"fig5_hydraulic_duration_{v}.png")
    plt.close(fig)
    # flow reversals per edge vs F000
    m = json.loads((r / "F111-E" / "annual_metrics.json").read_text())
    rev = {vv: m["hydraulics"][vv].get("flow_reversals_vs_F000_h", {}) for vv in m["hydraulics"]}
    df = pd.DataFrame(rev).fillna(0)
    if len(df):
        fig, ax = plt.subplots(figsize=(8, 3.2))
        w = 0.8 / df.shape[1]
        for i, c in enumerate(df.columns):
            ax.bar(np.arange(len(df)) + i * w, df[c], w * 0.92, color=SLOTS[i], label=f"calibration {c}")
        ax.set_xticks(np.arange(len(df)) + w * (df.shape[1] - 1) / 2, df.index, rotation=45)
        ax.set_ylabel("hours with reversed flow vs F000")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / "fig5b_flow_reversals_F111.png")
        plt.close(fig)


def fig6_feasibility(cfg, out, v="A"):
    r = _r(cfg) / "scenario_runs"
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    viol = pd.read_csv(r / "F111-E" / f"violations_{v}.csv", index_col=0, parse_dates=True)
    if len(viol):
        t = viol.groupby([viol.index.month, "violated_limit"]).size().unstack(fill_value=0).reindex(range(1, 13), fill_value=0)
        bottom = np.zeros(12)
        for i, c in enumerate(t.columns):
            ax[0].bar(range(1, 13), t[c], bottom=bottom, color=SLOTS[i], label=c, edgecolor="white", linewidth=1)
            bottom += t[c].to_numpy()
        ax[0].legend()
    ax[0].set(xlabel="month", ylabel="violating hours (F111-E)")
    for i, code in enumerate(["F000", "F101", "F111"]):
        p = r / f"{code}-H" / v / "iterations.csv"
        if p.exists():
            it = pd.read_csv(p)
            ax[1].plot(it["iteration"], it["violations"], marker="o", color=SLOTS[i], label=code)
    ax[1].set(xlabel="Mode-H iteration", ylabel="violating hours")
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(out / f"fig6_feasibility_{v}.png")
    plt.close(fig)


def fig7_design(cfg, out):
    p = _r(cfg) / "sensitivities" / "A1" / "summary.csv"
    if not p.exists():
        return
    d = pd.read_csv(p)
    fs = pd.read_csv(_r(cfg) / "scenario_runs" / "factorial_summary.csv").set_index("scenario")
    ref = fs.at["F110", "C_E"]            # A+B without TES (the A1 'V0' case is not a no-TES case in the class model)
    g = d[d["case"] != "V0"].copy()
    g["V"] = g["case"].str.extract(r"V(\d+)_").astype(float)
    g["Q"] = g["case"].str.extract(r"_Q(\d+)").astype(float)
    g["value"] = (ref - g["C_E"]) / 1e3
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for i, (q, gg) in enumerate(g.groupby("Q")):
        ax[0].plot(gg["tau_h"], gg["value"], marker="o", color=SLOTS[i], label=f"Q_max {q:.0f} MW")
    ax[0].set(xlabel="τ = E_max / Q_max [h]", ylabel="TES value vs F110 [kEUR/a]", xscale="log")
    ax[0].legend()
    if "dC_hyd" in g and g["dC_hyd"].notna().any():
        for i, (q, gg) in enumerate(g.groupby("Q")):
            ax[1].plot(gg["tau_h"], gg["dC_hyd"] / 1e3, marker="o", color=SLOTS[i], label=f"Q_max {q:.0f} MW")
        ax[1].set(xlabel="τ [h]", ylabel="ΔC_hyd [kEUR/a]", xscale="log", ylim=(0, 1.2 * g["dC_hyd"].max() / 1e3))
    fig.tight_layout()
    fig.savefig(out / "fig7_design_map.png")
    plt.close(fig)


def main():
    cfg = C.load()
    out = _r(cfg) / "figures"
    out.mkdir(parents=True, exist_ok=True)
    x = inputs.build(cfg)
    for f in (lambda: fig2_data(cfg, x, out), lambda: fig3_factorial(cfg, out), lambda: fig4_week(cfg, out),
              lambda: fig4_week(cfg, out, week="transition"), lambda: fig5_hydraulic(cfg, out), lambda: fig6_feasibility(cfg, out),
              lambda: fig7_design(cfg, out)):
        try:
            f()
        except FileNotFoundError as e:
            print("skipped:", e)
    print("figures in", out)


if __name__ == "__main__":
    main()
