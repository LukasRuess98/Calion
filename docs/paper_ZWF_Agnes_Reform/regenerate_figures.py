# -*- coding: utf-8 -*-
"""Baut Abb. 2-5 (Blautöne, Legenden außerhalb) NEU aus den bereits
berechneten Ergebnissen eines Laufs (outputs/<run_ts>/), ohne die
Solver-Kampagne erneut auszuführen. Nur für reine Stil-Änderungen an
bereits korrekten Daten gedacht.

Aufruf: python regenerate_figures.py [run_ts]
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent


def latest_run_dir() -> Path:
    runs = sorted((BASE_DIR / "outputs").iterdir(), key=lambda p: p.name)
    return runs[-1]


run_ts = sys.argv[1] if len(sys.argv) > 1 else None
RUN_DIR = (BASE_DIR / "outputs" / run_ts) if run_ts else latest_run_dir()
FIG_DIR = RUN_DIR / "figures"
if not RUN_DIR.exists():
    raise SystemExit(f"Run-Ordner nicht gefunden: {RUN_DIR}")
print(f"Quelle: {RUN_DIR}")

with open(BASE_DIR / "config.yaml", "r", encoding="utf-8") as fh:
    CONFIG = yaml.safe_load(fh)

DT_H = CONFIG["study"]["timestep_min"] / 60.0
SITE_IDS = list(CONFIG["sites"].keys())
SITE_LABEL_DE = {sid: CONFIG["sites"][sid]["label_de"].split(" (")[0] for sid in SITE_IDS}
SITE_ORDER = [s for s in ("food", "chemistry", "metal", "paper") if s in SITE_IDS]

# --- Palette (identisch zu agnes_p2h.py) -----------------------------------
OKABE_ITO = {"schwarz": "#000000", "blau": "#0072B2"}
BLUE_SHADES = ["#08306B", "#2171B5", "#4292C6", "#9ECAE1"]
BLUE_DARK, BLUE_MED, BLUE_MED2, BLUE_LIGHT = BLUE_SHADES
SITE_COLOR = dict(zip(("food", "chemistry", "metal", "paper"), BLUE_SHADES))
TECH_COLOR = dict(zip(("hp", "ek", "gb", "tes"), BLUE_SHADES))
TECH_LABEL = {"hp": "Wärmepumpe", "ek": "Elektrodenkessel", "gb": "Gaskessel", "tes": "Wärmespeicher"}
REGIME_COLOR = {"stromnev": BLUE_MED2, "agnes": BLUE_DARK}
REGIME_LS = {"stromnev": "--", "agnes": "-"}

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "figure.dpi": 150, "savefig.dpi": 300, "axes.spines.top": False, "axes.spines.right": False,
})


def save_fig(fig, name: str):
    fig.savefig(FIG_DIR / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{name}.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {name}.pdf / .png")


# --- Analytik neu berechnen (billig, kein Solve) ----------------------------
def cfg_value(node):
    return node["value"]


def annuity_factor(wacc, lifetime_a):
    if wacc <= 1e-9:
        return 1.0 / lifetime_a
    return wacc / (1.0 - (1.0 + wacc) ** (-lifetime_a))


class ResolvedTariff:
    pass


def resolve_tariffs(voltage_level: str):
    sn = CONFIG["stromnev"]["by_level"][voltage_level]
    tar = CONFIG["tariffs"]
    alpha = cfg_value(tar["alpha"])
    f = cfg_value(tar["f"])
    beta = cfg_value(tar["beta_min_order"])
    t_B = cfg_value(tar["t_B_h"])
    k = cfg_value(tar["k_by_level"][voltage_level])
    KP = (1 - alpha) * k
    AP1 = 1000.0 * alpha * k / t_B
    AP2 = f * AP1
    h_star = 1000.0 * KP / (AP2 - AP1)
    rt = ResolvedTariff()
    rt.voltage_level = voltage_level
    rt.KP_eur_kw_a, rt.AP1_eur_mwh, rt.AP2_eur_mwh = KP, AP1, AP2
    rt.h_star_h = h_star
    rt.t_B_h = t_B
    rt.beta_min_order = beta
    rt.stromnev_ge2500h_lp = sn["pair_ge2500h"]["lp_eur_kw_a"]
    return rt


TARIFFS = {lvl: resolve_tariffs(lvl) for lvl in ("ms", "ns", "hs_ms")}

# --- Standort -> Ebene (aus table02_cases.csv) ------------------------------
table02 = pd.read_csv(RUN_DIR / "tables" / "table02_cases.csv")
label_to_id = {v: k for k, v in SITE_LABEL_DE.items()}
site_level = {}
for _, row in table02.iterrows():
    sid = label_to_id.get(row["Standort"].split(" (")[0], None)
    if sid:
        site_level[sid] = row["Spannungsebene"]

# %% ==========================================================================
# Abbildung 2
# ==============================================================================
def sigma_stromnev(h, lp):
    with np.errstate(divide="ignore"):
        return 1000.0 * lp / h


def sigma_agnes(h, KP, AP2_minus_AP1):
    with np.errstate(divide="ignore"):
        return np.minimum(1000.0 * KP / h, AP2_minus_AP1)


def fig02_analytics():
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
    ax = axes[0]
    lvl = "ms"
    rt = TARIFFS[lvl]
    h_grid = np.geomspace(10, 8760, 400)
    s_nev = sigma_stromnev(h_grid, rt.stromnev_ge2500h_lp)
    s_agn = sigma_agnes(h_grid, rt.KP_eur_kw_a, rt.AP2_eur_mwh - rt.AP1_eur_mwh)
    ax.plot(h_grid, s_nev, color=REGIME_COLOR["stromnev"], ls=REGIME_LS["stromnev"], lw=1.8,
            label="StromNEV (>=2500h-Paar)")
    ax.plot(h_grid, s_agn, color=REGIME_COLOR["agnes"], ls=REGIME_LS["agnes"], lw=1.8, label="AgNes")
    ax.axvline(rt.h_star_h, color=OKABE_ITO["schwarz"], lw=0.9, ls=":")
    ax.text(rt.h_star_h, ax.get_ylim()[1] * 0.9 if ax.get_ylim()[1] else 1,
            f"  h*={rt.h_star_h:.0f} h", fontsize=7.5, rotation=90, va="top")
    ax.set_xscale("log")
    ax.set_xlabel("Bedarfsdauer h [h/a]")
    ax.set_ylabel("$\\sigma$ [EUR/MWh]")
    ax.set_title(f"(a) $\\sigma_{{NEV}}$ vs. $\\sigma_{{AgNes}}$ (Ebene {lvl.upper()})")
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2)

    ax2 = axes[1]
    alpha_fine = np.linspace(0.30, 0.60, 61)
    f_fine = np.linspace(2.0, 3.5, 61)
    theta_rows = [{"alpha": a, "f": f_, "theta": (1 - a) / ((f_ - 1) * a)}
                  for a in alpha_fine for f_ in f_fine]
    fig02_theta = pd.DataFrame(theta_rows)
    piv = fig02_theta.pivot(index="f", columns="alpha", values="theta")
    cmap = plt.get_cmap("Blues")
    im = ax2.pcolormesh(piv.columns, piv.index, piv.values, cmap=cmap, shading="auto")
    cs = ax2.contour(piv.columns, piv.index, piv.values, levels=[1.0], colors=BLUE_DARK, linewidths=1.6)
    ax2.clabel(cs, fmt={1.0: "theta=1"}, fontsize=7.5)
    fig.colorbar(im, ax=ax2, label="theta = h*/t_B")
    ax2.set_xlabel("alpha (Kapazitätspreis-Erlösanteil)")
    ax2.set_ylabel("f = AP2/AP1")
    ax2.set_title("(b) theta(alpha, f)")

    fig.suptitle("Zusatzabbildung: Analytik – Aufschlagsvergleich und dimensionslose Kennzahl "
                 "(nicht Teil der Haupttext-Abbildungen)", y=1.03)
    fig.tight_layout()
    save_fig(fig, "fig02_analytics")


# %% ==========================================================================
# Abbildung 3
# ==============================================================================
def fig03_core_results():
    df_lcoh = pd.read_csv(RUN_DIR / "lcoh_inc.csv", dtype={"kennung": str})
    df_lcoh["kennung"] = df_lcoh["kennung"].str.zfill(2)  # CSV-Rundreise verliert führende Null (0 statt "00")
    caps_df = pd.read_csv(RUN_DIR / "fig03_core_results.csv").set_index("site_id")

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0))

    ax = axes[0]
    kenn_order = ["00", "01", "10", "11"]
    kenn_label = {"00": "StromNEV\nFixpreis", "01": "StromNEV\nDay-Ahead",
                  "10": "AgNes\nFixpreis", "11": "AgNes\nDay-Ahead"}
    width = 0.2
    xpos = np.arange(len(kenn_order))
    for i, site in enumerate(SITE_ORDER):
        vals = [df_lcoh[(df_lcoh["site"] == site) & (df_lcoh["kennung"] == k)]["LCOH_inc_eur_mwh"].iloc[0]
                for k in kenn_order]
        ax.bar(xpos + (i - 1.5) * width, vals, width=width, color=SITE_COLOR[site], label=SITE_LABEL_DE[site])
    ax.set_xticks(xpos)
    ax.set_xticklabels([kenn_label[k] for k in kenn_order], fontsize=7.5)
    ax.set_ylabel("$LCOH^{inc}$ [EUR/MWh$_{th}$]")
    ax.set_title("(a) Inkrementelle Wärmekosten je Regime")
    ax.legend(frameon=False, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, 1.08), ncol=2)

    ax = axes[1]
    bottom = np.zeros(len(SITE_ORDER))
    for tech in ("hp", "ek", "gb"):
        vals = np.array([caps_df.loc[s, f"x_{tech}_kw"] / 1000.0 for s in SITE_ORDER])
        ax.bar(SITE_ORDER, vals, bottom=bottom, color=TECH_COLOR[tech], label=TECH_LABEL[tech])
        bottom += vals
    ax.set_xticklabels([SITE_LABEL_DE[s] for s in SITE_ORDER], rotation=20, ha="right", fontsize=7.5)
    ax.set_ylabel("Erzeugerkapazität [MW$_{th}$]")
    ax.set_title("(b) Anlagenauslegung (AgNes, Day-Ahead)")
    ax.legend(frameon=False, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, 1.08), ncol=3)

    ax = axes[2]
    vals_tes = np.array([caps_df.loc[s, "x_tes_kwh"] / 1000.0 for s in SITE_ORDER])
    ax.bar(SITE_ORDER, vals_tes, color=TECH_COLOR["tes"])
    ax.set_xticklabels([SITE_LABEL_DE[s] for s in SITE_ORDER], rotation=20, ha="right", fontsize=7.5)
    ax.set_ylabel("Speicherkapazität [MWh$_{th}$]")
    ax.set_title("(c) Wärmespeicher (1 Band, AgNes/Day-Ahead)")

    fig.tight_layout()
    fig.subplots_adjust(top=0.78)
    fig.suptitle("Abb. 2: Kernergebnisse – Kosten, Auslegung, Speicher", y=1.08)
    save_fig(fig, "fig03_core_results")


# %% ==========================================================================
# Abbildung 4
# ==============================================================================
def fig04_load_duration():
    ldc = pd.read_csv(RUN_DIR / "fig04_load_duration.csv")
    kpi = pd.read_parquet(RUN_DIR / "kpi_s1_s4.parquet")

    def make_run_id(site):
        return f"{site}__ELEC__agnes__dayahead__optimize__1h"

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 8.5))
    legend_handles = None
    for ax, site in zip(axes.flat, SITE_ORDER):
        sub = ldc[ldc["site"] == site].sort_values("rank_h")
        if sub.empty:
            ax.set_visible(False)
            continue
        run_id = make_run_id(site)
        row = kpi[kpi["run_id"] == run_id]
        if row.empty:
            ax.set_visible(False)
            continue
        kpi_row = row.iloc[0]
        C = kpi_row["C_kw"]
        p_sorted = sub["P_kw"].to_numpy()
        hours = sub["rank_h"].to_numpy()
        ax.plot(hours, p_sorted / 1000.0, color=OKABE_ITO["schwarz"], lw=1.4, label="Jahresdauerlinie $P_t$")
        ax.axhline(C / 1000.0, color=BLUE_DARK, lw=1.4, ls="-", label="C (bestellt)")
        ax.axhline(kpi_row["P_max_kw"] / 1000.0, color=BLUE_MED2, lw=1.2, ls="--", label="$P_{max}$")
        rt = TARIFFS[site_level[site]]
        ax.axvline(rt.h_star_h, color=BLUE_MED, lw=1.0, ls=":", label="h*")
        above = p_sorted > C
        ax.fill_between(hours, C / 1000.0, p_sorted / 1000.0, where=above,
                         color=BLUE_LIGHT, alpha=0.5, label="$E_2$-Fläche")
        ax.set_title(SITE_LABEL_DE[site])
        ax.set_xlabel("Dauer [h/a]")
        ax.set_ylabel("Leistung [MW]")
        if legend_handles is None:
            legend_handles, legend_labels = ax.get_legend_handles_labels()
    fig.suptitle("Abb. 3: Jahresdauerlinien (ELEC, AgNes, Day-Ahead) – C, $P_{max}$, $E_2$, h*", y=1.02)
    fig.tight_layout()
    fig.legend(legend_handles, legend_labels, loc="lower center", ncol=5,
               bbox_to_anchor=(0.5, -0.04), frameon=False, fontsize=9)
    save_fig(fig, "fig04_load_duration")


# %% ==========================================================================
# Abbildung 5
# ==============================================================================
def fig05_breakeven():
    from matplotlib.patches import Patch

    df_breakeven = pd.read_csv(RUN_DIR / "breakeven.csv")
    GAS_PRICE = cfg_value(CONFIG["energy"]["gas_eur_mwh_hu"])
    CO2_PRICE = cfg_value(CONFIG["energy"]["co2_eur_t"])

    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.8))
    regimes = CONFIG["design"]["netz_regimes"]
    xpos = np.arange(len(SITE_ORDER))
    regime_hatch = {"stromnev": "//", "agnes": None}
    regime_label = {"stromnev": "StromNEV", "agnes": "AgNes"}
    bar_w, gap = 0.30, 0.04
    single_w = 0.42

    for ax, kind, label, ref, unit in (
        (axes[0], "gas", "Gaspreis-Break-even", GAS_PRICE, "EUR/MWh$_{Hu}$"),
        (axes[1], "co2", "CO$_2$-Preis-Break-even", CO2_PRICE, "EUR/t"),
    ):
        sub = df_breakeven[df_breakeven["kind"] == kind]
        for si, site in enumerate(SITE_ORDER):
            avail = []
            for regime in regimes:
                row = sub[(sub["site"] == site) & (sub["netz_regime"] == regime)]
                if len(row) and bool(row.iloc[0]["found"]):
                    avail.append((regime, float(row.iloc[0]["breakeven"])))
            n = len(avail)
            if n == 0:
                continue
            if n == 1:
                regime, val = avail[0]
                ax.bar(si, val, width=single_w, color=SITE_COLOR[site],
                       hatch=regime_hatch[regime], edgecolor=OKABE_ITO["schwarz"], linewidth=0.6)
            else:
                for j, (regime, val) in enumerate(avail):
                    offset = (j - (n - 1) / 2) * (bar_w + gap)
                    ax.bar(si + offset, val, width=bar_w, color=SITE_COLOR[site],
                           hatch=regime_hatch[regime], edgecolor=OKABE_ITO["schwarz"], linewidth=0.6)
        ax.axhline(ref, color=OKABE_ITO["schwarz"], lw=1.0, ls=":")
        ax.set_xticks(xpos)
        ax.set_xticklabels([SITE_LABEL_DE[s] for s in SITE_ORDER], rotation=20, ha="right")
        ax.set_xlim(-0.6, len(SITE_ORDER) - 0.4)
        ax.set_ylabel(f"Break-even [{unit}]")
        ax.set_title(label)
        legend_elems = [
            Patch(facecolor="#D9D9D9", edgecolor=OKABE_ITO["schwarz"], hatch=regime_hatch["stromnev"],
                  label=regime_label["stromnev"]),
            Patch(facecolor="#D9D9D9", edgecolor=OKABE_ITO["schwarz"], label=regime_label["agnes"]),
            plt.Line2D([0], [0], color=OKABE_ITO["schwarz"], lw=1.0, ls=":",
                       label=f"Referenz-Szenariowert ({ref:.0f})"),
        ]
        ax.legend(handles=legend_elems, frameon=False, fontsize=7, loc="lower center",
                  bbox_to_anchor=(0.5, 1.12), ncol=3)
    fig.tight_layout()
    fig.subplots_adjust(top=0.72)
    fig.suptitle("Abb. 4: Fossiler Break-even je Standort x Netzregime (Hybrid-ELEC vs. GAS, Day-Ahead)", y=1.1)
    save_fig(fig, "fig05_breakeven")


if __name__ == "__main__":
    print("Baue Zusatzabbildung (Analytik, nicht im Haupttext)...")
    fig02_analytics()
    print("Baue Abb. 2...")
    fig03_core_results()
    print("Baue Abb. 3...")
    fig04_load_duration()
    print("Baue Abb. 4...")
    fig05_breakeven()
    print("Fertig.")
