"""
Bilanzraum-Emissionen Paper — alle Figuren generieren.

Erwartet:
  outputs/bilanz_emissionen/ergebnisse/dispatch_zeitreihen.csv
  outputs/bilanz_emissionen/ergebnisse/bilanzraum_vergleich.xlsx

Erzeugt 8 Figuren (PDF + PNG) in:
  outputs/bilanz_emissionen/figures/

Figuren:
  fig1_hauptergebnis       Hauptvergleich CO2 [t] aller Bilanzräume × Szenarien
  fig2_rel_abweichung      Relative Abweichung [%] von stündlicher Referenz
  fig3_dispatch_winter     Dispatch-Beispiel Winterwoche (S1 / S2 / S3)
  fig4_dispatch_sommer     Dispatch-Beispiel Sommerwoche (S1 / S2 / S3)
  fig5_co2_faktor          Stündlicher CO2-Faktor + Monatsmittel + Wochenmittel
  fig6_hp_co2_scatter      Korrelation HP-Strom vs CO2-Faktor (je Szenario)
  fig7_monatliche_co2      Monatliche CO2-Emissionen je Bilanzraum × Szenario
  fig8_dauerlinie          Geordnete Jahresdauerlinie HP-Strombezug je Szenario

Usage:
    python scripts/paper/run_bilanz_emissionen.py  # erst Ergebnisse erzeugen
    python scripts/paper/plot_bilanz_emissionen.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from ecm_style import (
    apply_ecm_style, save_figure,
    SINGLE_COL_W, DOUBLE_COL_W, H_STANDARD, H_TALL,
    C_HP, C_TES_DIS, C_TES_CHG, C_DEMAND,
    FONT_LEGEND, FONT_TICK, FONT_AXIS_LABEL,
)

apply_ecm_style()

# ── Paths ─────────────────────────────────────────────────────────────────────
RES_DIR  = ROOT / "outputs" / "bilanz_emissionen" / "ergebnisse"
FIG_DIR  = ROOT / "outputs" / "bilanz_emissionen" / "figures"
DATA_CSV = ROOT / "data" / "memmingen_bilanz_emissionen_2025_1h.csv"

DISPATCH_CSV = RES_DIR / "dispatch_zeitreihen.csv"
EXCEL_FILE   = RES_DIR / "bilanzraum_vergleich.xlsx"

# ── Colors & labels ───────────────────────────────────────────────────────────
C_S1 = "#1f77b4"   # blue    — Lastfolge
C_S2 = "#ff7f0e"   # orange  — Kosten
C_S3 = "#2ca02c"   # green   — Kosten+CO2

C_ANNUAL  = "#d62728"   # red
C_MONTHLY = "#ff7f0e"   # orange
C_WEEKLY  = "#9467bd"   # purple
C_HOURLY  = "#1f77b4"   # blue (reference)

C_CO2_FACTOR = "#7f7f7f"  # grey

SCENARIO_COLORS = {"S1_Lastfolge": C_S1, "S2_Kosten": C_S2, "S3_Kosten_Emissionen": C_S3}
SCENARIO_LABELS = {
    "S1_Lastfolge":         "S1: Lastfolge",
    "S2_Kosten":            "S2: Kostenpoptimiert",
    "S3_Kosten_Emissionen": "S3: Kosten + CO$_2$",
}
C_15MIN   = "#17becf"   # cyan — 15-min reference

BILANZRAUM_COLORS = {
    "CO2_jaehrlich_t":    C_ANNUAL,
    "CO2_monatlich_t":    C_MONTHLY,
    "CO2_woechentlich_t": C_WEEKLY,
    "CO2_stuendlich_t":   C_HOURLY,
    "CO2_15min_t":        C_15MIN,
}
BILANZRAUM_LABELS = {
    "CO2_jaehrlich_t":    "Jahres-Ø",
    "CO2_monatlich_t":    "Monats-Ø",
    "CO2_woechentlich_t": "Wochen-Ø",
    "CO2_stuendlich_t":   "Stündlich",
    "CO2_15min_t":        "15-Minuten",
}

DATA_15M = ROOT / "data" / "memmingen_bilanz_emissionen_2025_15min.csv"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_data() -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame,
                          pd.Series | None]:
    """Returns (dispatch_df, summary_df, base_1h, co2_15m)."""
    base = pd.read_csv(DATA_CSV, index_col="Datum", parse_dates=True).sort_index()

    co2_15m = None
    if DATA_15M.exists():
        df15 = pd.read_csv(DATA_15M, index_col="Datum", parse_dates=True).sort_index()
        co2_15m = df15["grid_co2_kg_MWh"]

    dispatch = None
    if DISPATCH_CSV.exists():
        dispatch = pd.read_csv(DISPATCH_CSV, index_col="Datum", parse_dates=True).sort_index()
    else:
        print(f"[WARN] Dispatch CSV not found: {DISPATCH_CSV}")
        print("       Generating analytical S1 only (run run_bilanz_emissionen.py first)")

    summary = None
    if EXCEL_FILE.exists():
        summary = pd.read_excel(EXCEL_FILE, sheet_name="Vergleich")

    return dispatch, summary, base, co2_15m


def _co2_bilanzraeume(
    hp_el_mw: pd.Series,
    co2_factor: pd.Series,
    co2_15m: pd.Series | None = None,
) -> dict[str, float]:
    """Compute annual CO2 totals [t] for 5 Bilanzräume (incl. 15-min)."""
    elec = hp_el_mw * 1.0  # MWh (dt=1h)
    ef_annual  = co2_factor.mean()
    ef_monthly = co2_factor.resample("ME").mean()
    ef_weekly  = co2_factor.resample("W-MON").mean()

    def _apply(ef_series: pd.Series, freq: str) -> float:
        ef_mapped = pd.Series(ef_annual, index=elec.index, dtype=float)
        for ts, val in ef_series.items():
            period = pd.Period(ts, freq=freq)
            mask = elec.index.to_period(freq) == period
            ef_mapped[mask] = val
        return float((elec * ef_mapped).sum() / 1000)

    annual  = float((elec * ef_annual).sum() / 1000)
    monthly = _apply(ef_monthly, "M")
    weekly  = _apply(ef_weekly,  "W-MON")
    hourly  = float((elec * co2_factor).sum() / 1000)

    # 15-min: expand dispatch to 15-min then apply 15-min CO2 factors
    if co2_15m is not None:
        el_15m = hp_el_mw.resample("15min").ffill() * 0.25  # MWh per 15-min slot
        idx_c  = el_15m.index.intersection(co2_15m.index)
        qh     = float((el_15m.loc[idx_c] * co2_15m.loc[idx_c]).sum() / 1000)
    else:
        qh = hourly

    return {
        "CO2_jaehrlich_t":    annual,
        "CO2_monatlich_t":    monthly,
        "CO2_woechentlich_t": weekly,
        "CO2_stuendlich_t":   hourly,
        "CO2_15min_t":        qh,
    }


# ── Fig 1: Hauptergebnis ──────────────────────────────────────────────────────

def fig1_hauptergebnis(dispatch: pd.DataFrame, base: pd.DataFrame,
                       co2_15m: pd.Series | None = None) -> None:
    """Grouped bars: CO2 [t/a] per scenario and Bilanzraum."""
    scenarios = [c for c in dispatch.columns if c in SCENARIO_LABELS]
    if not scenarios:
        print("[SKIP] fig1: no scenarios in dispatch")
        return

    br_cols = ["CO2_jaehrlich_t", "CO2_monatlich_t", "CO2_woechentlich_t",
               "CO2_stuendlich_t", "CO2_15min_t"]
    data: dict[str, dict] = {}
    for sc in scenarios:
        data[sc] = _co2_bilanzraeume(dispatch[sc], base["grid_co2_kg_MWh"], co2_15m)

    n_sc = len(scenarios)
    n_br = len(br_cols)
    x    = np.arange(n_sc)
    # Adaptive bar width: wider when few scenarios, narrower with more
    w    = min(0.18, 0.7 / (n_sc * n_br) * n_sc)
    offsets = np.linspace(-(n_br - 1) / 2 * w, (n_br - 1) / 2 * w, n_br)

    fig, ax = plt.subplots(figsize=(DOUBLE_COL_W, H_STANDARD))

    for j, (col, offset) in enumerate(zip(br_cols, offsets)):
        vals  = [data[sc].get(col, 0.0) for sc in scenarios]
        bars  = ax.bar(x + offset, vals, width=w, color=BILANZRAUM_COLORS[col],
                       label=BILANZRAUM_LABELS[col], zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_LABELS.get(s, s) for s in scenarios])
    ax.set_ylabel("CO$_2$-Emissionen [t CO$_2$/a]")
    ax.set_xlabel("Betriebsszenario")
    ax.legend(title="Bilanzraum", fontsize=FONT_LEGEND, title_fontsize=FONT_LEGEND,
              loc="upper right")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=6, integer=True))
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()
    save_figure(fig, FIG_DIR / "fig1_hauptergebnis")
    plt.close(fig)
    print("fig1 saved")


# ── Fig 2: Relative Abweichung ────────────────────────────────────────────────

def fig2_rel_abweichung(dispatch: pd.DataFrame, base: pd.DataFrame,
                        co2_15m: pd.Series | None = None) -> None:
    """% deviation of annual/monthly/weekly/hourly from 15-min reference."""
    scenarios = [c for c in dispatch.columns if c in SCENARIO_LABELS]
    if not scenarios:
        return

    br_comp = ["CO2_jaehrlich_t", "CO2_monatlich_t",
               "CO2_woechentlich_t", "CO2_stuendlich_t"]
    n_sc  = len(scenarios)
    x     = np.arange(len(br_comp))
    w     = 0.22
    offsets = np.linspace(-(n_sc - 1) / 2 * w, (n_sc - 1) / 2 * w, n_sc)

    fig, ax = plt.subplots(figsize=(DOUBLE_COL_W, H_STANDARD))

    for i, sc in enumerate(scenarios):
        vals = _co2_bilanzraeume(dispatch[sc], base["grid_co2_kg_MWh"], co2_15m)
        ref  = vals["CO2_15min_t"]   # 15-min is now the reference
        devs = [(vals[c] - ref) / ref * 100 for c in br_comp]
        color = SCENARIO_COLORS.get(sc, f"C{i}")
        ax.bar(x + offsets[i], devs, width=w, color=color,
               label=SCENARIO_LABELS.get(sc, sc), zorder=3)

    ax.axhline(0, color="k", linewidth=0.8, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels([BILANZRAUM_LABELS.get(c, c) for c in br_comp])
    ax.set_ylabel("Abweichung von 15-min-Referenz [%]")
    ax.set_xlabel("Bilanzraum")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)
    # Ensure sensible y-limits even when all deviations are near zero
    ylim = ax.get_ylim()
    span = ylim[1] - ylim[0]
    if span < 1.0:
        mid = (ylim[0] + ylim[1]) / 2
        ax.set_ylim(mid - 0.5, mid + 0.5)

    fig.tight_layout()
    save_figure(fig, FIG_DIR / "fig2_rel_abweichung")
    plt.close(fig)
    print("fig2 saved")


# ── Helper: example week dispatch ─────────────────────────────────────────────

def _plot_dispatch_week(
    dispatch: pd.DataFrame,
    base: pd.DataFrame,
    week_start: str,
    fig_stem: str,
    title_prefix: str,
) -> None:
    scenarios = [c for c in dispatch.columns if c in SCENARIO_LABELS]
    if not scenarios:
        return

    ws  = pd.Timestamp(week_start)
    we  = ws + pd.Timedelta(days=7) - pd.Timedelta(hours=1)
    hrs = dispatch.loc[ws:we].index

    # Each scenario: upper panel (HP+demand+price) + lower panel (TES SOC) if available
    n_sc = len(scenarios)
    # 2 rows per scenario if TES data present, else 1
    has_tes = any(f"{sc}_TES_SOC_MWh" in dispatch.columns for sc in scenarios)
    n_rows  = 2 if has_tes else 1
    row_h   = H_TALL * 0.6

    fig, all_axes = plt.subplots(
        n_rows, n_sc,
        figsize=(DOUBLE_COL_W, row_h * n_rows),
        sharex=True, squeeze=False,
    )

    day_ticks  = [i * 24 for i in range(8)]
    day_labels = [(ws + pd.Timedelta(days=i)).strftime("%a\n%d.%m") for i in range(8)]

    for col_i, sc in enumerate(scenarios):
        ax_top = all_axes[0][col_i]
        hp_el = dispatch[sc].loc[hrs]
        dem   = base["total_demand_MWth"].loc[hrs]
        price = base["strompreis_EUR_MWh"].loc[hrs]
        co2   = base["grid_co2_kg_MWh"].loc[hrs]

        x = np.arange(len(hrs))
        sc_color = SCENARIO_COLORS.get(sc, C_HP)

        ax_top.fill_between(x, 0, hp_el.values, color=sc_color, alpha=0.7,
                            label="WP Strom [MW]")
        ax_top.plot(x, dem.values / 3.5, color=C_DEMAND, linewidth=1.0,
                    linestyle="--", label="Bedarf/3,5")

        ax_p = ax_top.twinx()
        ax_p.plot(x, price.values, color="#d62728", linewidth=0.6, alpha=0.55,
                  label="Preis [€/MWh]")
        ax_p.set_ylabel("€/MWh", fontsize=FONT_TICK - 1, color="#d62728")
        ax_p.tick_params(axis="y", labelcolor="#d62728", labelsize=FONT_TICK - 1)
        ax_p.spines["right"].set_visible(True)

        ax_top.set_title(SCENARIO_LABELS.get(sc, sc), fontsize=FONT_TICK + 1)
        if col_i == 0:
            ax_top.set_ylabel("Leistung [MW]", fontsize=FONT_TICK)

        l1, lb1 = ax_top.get_legend_handles_labels()
        l2, lb2 = ax_p.get_legend_handles_labels()
        ax_top.legend(l1 + l2, lb1 + lb2, fontsize=FONT_LEGEND - 1,
                      loc="upper right", ncol=3)

        # TES SOC panel
        if has_tes:
            ax_tes = all_axes[1][col_i]
            soc_col   = f"{sc}_TES_SOC_MWh"
            chg_col   = f"{sc}_TES_charge_MW"
            dchg_col  = f"{sc}_TES_discharge_MW"

            if soc_col in dispatch.columns:
                soc = dispatch[soc_col].loc[hrs]
                ax_tes.fill_between(x, 0, soc.values, color=C_TES_DIS, alpha=0.5,
                                    label="Speicher SOC [MWh]")
                ax_tes.set_ylabel("SOC [MWh]", fontsize=FONT_TICK)
                if chg_col in dispatch.columns:
                    chg  = dispatch[chg_col].loc[hrs]
                    dchg = dispatch[dchg_col].loc[hrs] if dchg_col in dispatch.columns else None
                    ax_tes2 = ax_tes.twinx()
                    ax_tes2.bar(x, chg.values,  color=C_TES_CHG, alpha=0.5,
                                width=0.4, align="edge", label="Laden")
                    if dchg is not None:
                        ax_tes2.bar(x, -dchg.values, color=C_TES_DIS, alpha=0.5,
                                    width=0.4, align="edge", label="Entladen")
                    ax_tes2.axhline(0, color="k", linewidth=0.5)
                    ax_tes2.set_ylabel("MW", fontsize=FONT_TICK - 1)
                    ax_tes2.spines["right"].set_visible(True)
            else:
                ax_tes.text(0.5, 0.5, "kein Speicher (S1)",
                            ha="center", va="center", transform=ax_tes.transAxes,
                            fontsize=FONT_TICK, color="grey")
                ax_tes.set_ylabel("SOC [MWh]", fontsize=FONT_TICK)

            ax_tes.set_xticks(day_ticks)
            ax_tes.set_xticklabels(day_labels, fontsize=FONT_TICK)
            ax_tes.set_xlabel("Tag")
        else:
            ax_top.set_xticks(day_ticks)
            ax_top.set_xticklabels(day_labels, fontsize=FONT_TICK)
            ax_top.set_xlabel("Tag")

    # Supertitle
    fig.suptitle(title_prefix, fontsize=FONT_TICK + 2, y=1.01)
    fig.tight_layout()
    save_figure(fig, FIG_DIR / fig_stem)
    plt.close(fig)
    print(f"{fig_stem} saved")


def fig3_dispatch_winter(dispatch: pd.DataFrame, base: pd.DataFrame) -> None:
    _plot_dispatch_week(dispatch, base, "2025-01-13", "fig3_dispatch_winter",
                        "Winterwoche 13.–19. Jan.")


def fig4_dispatch_sommer(dispatch: pd.DataFrame, base: pd.DataFrame) -> None:
    _plot_dispatch_week(dispatch, base, "2025-07-07", "fig4_dispatch_sommer",
                        "Sommerwoche 7.–13. Jul.")


# ── Fig 5: CO2-Faktor Zeitreihe ───────────────────────────────────────────────

def fig5_co2_faktor(base: pd.DataFrame) -> None:
    """Annual CO2 factor: hourly + monthly/weekly averages."""
    co2 = base["grid_co2_kg_MWh"]
    idx = co2.index

    monthly = co2.resample("ME").mean()
    weekly  = co2.resample("W-MON").mean()

    fig, ax = plt.subplots(figsize=(DOUBLE_COL_W, H_STANDARD))

    # Hourly as light fill
    ax.fill_between(idx, co2.values, alpha=0.15, color=C_CO2_FACTOR,
                    label="Stündlich")

    # Weekly as step
    weekly_reindexed = weekly.reindex(idx, method="ffill")
    ax.step(idx, weekly_reindexed.values, color=C_WEEKLY, linewidth=0.8,
            alpha=0.85, label="Wochen-Ø")

    # Monthly as bold step
    monthly_reindexed = monthly.reindex(idx, method="ffill")
    ax.step(idx, monthly_reindexed.values, color=C_MONTHLY, linewidth=1.4,
            label="Monats-Ø")

    # Annual line
    ax.axhline(co2.mean(), color=C_ANNUAL, linewidth=1.4, linestyle="--",
               label=f"Jahres-Ø ({co2.mean():.0f} g/kWh)")

    ax.set_ylabel("CO$_2$-Emissionsfaktor [kg/MWh]")
    ax.set_xlabel("Monat 2025")
    ax.xaxis.set_major_locator(mdates_locator())
    ax.xaxis.set_major_formatter(mdates_formatter())
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.legend(fontsize=FONT_LEGEND, ncol=2)
    ax.grid(axis="y")

    fig.tight_layout()
    save_figure(fig, FIG_DIR / "fig5_co2_faktor")
    plt.close(fig)
    print("fig5 saved")


def mdates_locator():
    import matplotlib.dates as mdates
    return mdates.MonthLocator()


def mdates_formatter():
    import matplotlib.dates as mdates
    return mdates.DateFormatter("%b")


# ── Fig 6: HP-Strom vs CO2-Faktor Korrelation ─────────────────────────────────

def fig6_hp_co2_scatter(dispatch: pd.DataFrame, base: pd.DataFrame) -> None:
    """Scatter: HP electricity vs CO2 factor (monthly aggregates per scenario)."""
    scenarios = [c for c in dispatch.columns if c in SCENARIO_LABELS]
    if not scenarios:
        return

    n_sc = len(scenarios)
    fig, axes = plt.subplots(1, n_sc, figsize=(DOUBLE_COL_W, H_STANDARD),
                             sharey=True)
    if n_sc == 1:
        axes = [axes]

    for ax, sc in zip(axes, scenarios):
        hp_el = dispatch[sc]
        co2   = base["grid_co2_kg_MWh"]

        # Monthly aggregates
        monthly = pd.DataFrame({
            "hp_el_mwh": hp_el.resample("ME").sum(),
            "co2_mean":  co2.resample("ME").mean(),
        }).dropna()

        color = SCENARIO_COLORS.get(sc, "C0")
        ax.scatter(monthly["hp_el_mwh"], monthly["co2_mean"],
                   c=color, s=50, zorder=5, alpha=0.85)

        # Regression line
        x = monthly["hp_el_mwh"].values
        y = monthly["co2_mean"].values
        if len(x) >= 2:
            m, b = np.polyfit(x, y, 1)
            xr = np.linspace(x.min(), x.max(), 50)
            ax.plot(xr, m * xr + b, color=color, linewidth=1.2,
                    linestyle="--", alpha=0.7)
            r = np.corrcoef(x, y)[0, 1]
            ax.text(0.05, 0.92, f"r = {r:.2f}", transform=ax.transAxes,
                    fontsize=FONT_TICK, color=color)

        ax.set_xlabel("WP-Strombezug\n[MWh/Monat]")
        ax.set_title(SCENARIO_LABELS.get(sc, sc), fontsize=FONT_TICK + 1)

    axes[0].set_ylabel("Ø CO$_2$-Faktor\n[kg CO$_2$/MWh]")
    fig.tight_layout()
    save_figure(fig, FIG_DIR / "fig6_hp_co2_scatter")
    plt.close(fig)
    print("fig6 saved")


# ── Fig 7: Monatliche CO2-Emissionen ─────────────────────────────────────────

def fig7_monatliche_co2(dispatch: pd.DataFrame, base: pd.DataFrame) -> None:
    """Monthly CO2 per Bilanzraum for each scenario (3 subplots)."""
    scenarios = [c for c in dispatch.columns if c in SCENARIO_LABELS]
    if not scenarios:
        return

    n_sc = len(scenarios)
    fig, axes = plt.subplots(1, n_sc, figsize=(DOUBLE_COL_W, H_STANDARD),
                             sharey=True)
    if n_sc == 1:
        axes = [axes]

    br_cols  = ["CO2_jaehrlich_t", "CO2_monatlich_t",
                 "CO2_woechentlich_t", "CO2_stuendlich_t"]
    months   = range(1, 13)
    month_labels = ["Jan","Feb","Mär","Apr","Mai","Jun",
                    "Jul","Aug","Sep","Okt","Nov","Dez"]
    x = np.arange(12)
    w = 0.18
    offsets = np.linspace(-(len(br_cols) - 1) / 2 * w,
                           (len(br_cols) - 1) / 2 * w, len(br_cols))

    co2 = base["grid_co2_kg_MWh"]

    for ax, sc in zip(axes, scenarios):
        hp_el = dispatch[sc]
        ef_a  = co2.mean()
        ef_mo = co2.resample("ME").mean()
        ef_wk = co2.resample("W-MON").mean()

        # Monthly HP electricity
        el_mo = hp_el.resample("ME").sum()  # MWh

        co2_annual  = [float(el_mo.iloc[m - 1]) * ef_a / 1000 for m in months]

        co2_monthly = []
        for m in months:
            key = pd.Timestamp(f"2025-{m:02d}-01") + pd.offsets.MonthEnd(0)
            ef  = float(ef_mo.get(key, ef_a))
            co2_monthly.append(float(el_mo.iloc[m - 1]) * ef / 1000)

        co2_weekly  = []
        for m in months:
            mask  = (hp_el.index.month == m)
            el_h  = hp_el[mask] * 1.0          # MWh per hour
            co2_h = []
            for ts, e in el_h.items():
                key = ts.to_period("W-MON").to_timestamp("W-MON")
                ef  = float(ef_wk.get(key, ef_a))
                co2_h.append(e * ef / 1000)
            co2_weekly.append(sum(co2_h))

        co2_hourly = []
        for m in months:
            mask = (hp_el.index.month == m) & (co2.index.month == m)
            el   = hp_el[hp_el.index.month == m]
            ef   = co2[co2.index.month == m].reindex(el.index, method="ffill").fillna(ef_a)
            co2_hourly.append(float((el * ef / 1000).sum()))

        all_vals = [co2_annual, co2_monthly, co2_weekly, co2_hourly]

        for j, (col, vals, offset) in enumerate(zip(br_cols, all_vals, offsets)):
            ax.bar(x + offset, vals, width=w, color=BILANZRAUM_COLORS[col],
                   label=BILANZRAUM_LABELS[col] if ax is axes[0] else None,
                   zorder=3)

        ax.set_xticks(x)
        ax.set_xticklabels(month_labels, fontsize=FONT_TICK - 1, rotation=45, ha="right")
        ax.set_title(SCENARIO_LABELS.get(sc, sc), fontsize=FONT_TICK + 1)
        ax.grid(axis="y", zorder=0)

    axes[0].set_ylabel("CO$_2$-Emissionen [t CO$_2$/Monat]")

    # Shared legend
    handles = [mpatches.Patch(color=BILANZRAUM_COLORS[c], label=BILANZRAUM_LABELS[c])
               for c in br_cols]
    fig.legend(handles=handles, title="Bilanzraum", fontsize=FONT_LEGEND,
               title_fontsize=FONT_LEGEND, loc="upper center",
               bbox_to_anchor=(0.5, 1.02), ncol=4)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save_figure(fig, FIG_DIR / "fig7_monatliche_co2")
    plt.close(fig)
    print("fig7 saved")


# ── Fig 8: Geordnete Dauerlinie ───────────────────────────────────────────────

def fig8_dauerlinie(dispatch: pd.DataFrame, base: pd.DataFrame) -> None:
    """Load duration curve: sorted HP electricity [MW] per scenario."""
    scenarios = [c for c in dispatch.columns if c in SCENARIO_LABELS]
    if not scenarios:
        return

    fig, ax = plt.subplots(figsize=(SINGLE_COL_W, H_STANDARD))

    for sc in scenarios:
        sorted_vals = np.sort(dispatch[sc].values)[::-1]
        hours = np.arange(1, len(sorted_vals) + 1)
        ax.plot(hours, sorted_vals, color=SCENARIO_COLORS.get(sc, "C0"),
                linewidth=1.2, label=SCENARIO_LABELS.get(sc, sc))

    ax.set_xlabel("Stunden [h/a]")
    ax.set_ylabel("WP-Strombezug [MW]")
    ax.legend(fontsize=FONT_LEGEND)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, len(dispatch))

    fig.tight_layout()
    save_figure(fig, FIG_DIR / "fig8_dauerlinie")
    plt.close(fig)
    print("fig8 saved")


# ── Bonus Fig 9: Monatlicher CO2-Faktor + WP-Strombezug ──────────────────────

def fig9_co2_faktor_und_hp(dispatch: pd.DataFrame, base: pd.DataFrame) -> None:
    """Dual-axis: monthly avg CO2 factor (bar) + HP electricity per scenario (lines)."""
    scenarios = [c for c in dispatch.columns if c in SCENARIO_LABELS]
    if not scenarios:
        return

    co2 = base["grid_co2_kg_MWh"]
    ef_mo = co2.resample("ME").mean()

    months = range(1, 13)
    x = np.arange(12)
    month_labels = ["Jan","Feb","Mär","Apr","Mai","Jun",
                    "Jul","Aug","Sep","Okt","Nov","Dez"]

    ef_vals = [float(ef_mo.iloc[m - 1]) for m in months]

    fig, ax1 = plt.subplots(figsize=(DOUBLE_COL_W, H_STANDARD))
    ax2 = ax1.twinx()

    ax1.bar(x, ef_vals, color=C_CO2_FACTOR, alpha=0.35, zorder=2,
            label="CO$_2$-Faktor Ø [kg/MWh]")
    ax1.set_ylabel("Ø CO$_2$-Emissionsfaktor [kg/MWh]", color=C_CO2_FACTOR)
    ax1.tick_params(axis="y", labelcolor=C_CO2_FACTOR)

    for sc in scenarios:
        el_mo = dispatch[sc].resample("ME").sum()
        vals = [float(el_mo.iloc[m - 1]) for m in months]
        ax2.plot(x, vals, color=SCENARIO_COLORS.get(sc, "C0"), linewidth=1.4,
                 marker="o", markersize=3, label=SCENARIO_LABELS.get(sc, sc), zorder=5)

    ax2.set_ylabel("WP-Strombezug [MWh/Monat]")

    ax1.set_xticks(x)
    ax1.set_xticklabels(month_labels, fontsize=FONT_TICK)
    ax1.set_xlabel("Monat 2025")

    lines1, lab1 = ax1.get_legend_handles_labels()
    lines2, lab2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lab1 + lab2, fontsize=FONT_LEGEND, loc="upper right")
    ax1.set_axisbelow(True)

    fig.tight_layout()
    save_figure(fig, FIG_DIR / "fig9_co2_hp_monatlich")
    plt.close(fig)
    print("fig9 saved")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    dispatch, summary, base, co2_15m = load_data()

    if dispatch is None:
        print("[INFO] Generating S1 analytically (no optimizer results)")
        s1 = (base["total_demand_MWth"] / 3.5).rename("S1_Lastfolge")
        dispatch = pd.DataFrame({"S1_Lastfolge": s1})

    # Only keep scenario HP columns for scenario-level analysis
    sc_cols = [c for c in dispatch.columns if c in SCENARIO_LABELS]

    common_idx = dispatch.index.intersection(base.index)
    dispatch_full = dispatch.loc[common_idx]          # includes TES columns
    dispatch_sc   = dispatch_full[sc_cols]            # HP-only for CO2 plots
    base          = base.loc[common_idx]

    print(f"\nGenerating figures in: {FIG_DIR}")
    print(f"Scenarios: {sc_cols}")
    print(f"15-min CO2: {'yes' if co2_15m is not None else 'no'}")
    print(f"Period: {dispatch_full.index[0]} — {dispatch_full.index[-1]}")
    print("-" * 50)

    fig1_hauptergebnis(dispatch_sc, base, co2_15m)
    fig2_rel_abweichung(dispatch_sc, base, co2_15m)

    if len(dispatch_full) >= 7 * 24:
        fig3_dispatch_winter(dispatch_full, base)
        fig4_dispatch_sommer(dispatch_full, base)
    else:
        print("[SKIP] Dispatch week plots: insufficient data")

    fig5_co2_faktor(base)
    fig6_hp_co2_scatter(dispatch_sc, base)
    fig7_monatliche_co2(dispatch_sc, base)
    fig8_dauerlinie(dispatch_sc, base)
    fig9_co2_faktor_und_hp(dispatch_sc, base)

    print("\nDone. All figures saved as PDF + PNG.")


if __name__ == "__main__":
    sys.exit(main())
