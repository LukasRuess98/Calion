"""
Paper 3 — Abbildungsgenerierung (F1–F12).

Applied Energy Journal Formatierung. Alle Abbildungen als PDF + PNG.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.colors as mcolors
    from matplotlib.lines import Line2D
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

logger = logging.getLogger(__name__)

_SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = _SCRIPT_DIR / "results"

# ---------------------------------------------------------------------------
# Stil-Konstanten (verbindlich gemaess Prompt-Spezifikation)
# ---------------------------------------------------------------------------

COLORS = {
    "S1": "#1F5C99",
    "S2": "#C55A11",
    "S3": "#375623",
    "B1": "dashed",
    "B2": "solid",
    "B3": "dotted",
    "memmingen": 1.0,
    "stadtbach": 0.6,
    "M1": "o",
    "M2": "^",
    "G1": "Jährl.\n(G1)",
    "G2": "Monatl.\n(G2)",
    "G3": "Wöchentl.\n(G3)",
    "G4": "Tägl.\n(G4)",
    "G5": "Stündl.\n(G5)",
    "G6": "15-min\n(G6)",
}

# Applied Energy Spaltenbreiten [inch]
FIGSIZE_SINGLE = (8.46 / 2.54, 5.0)
FIGSIZE_DOUBLE = (17.4 / 2.54, 5.0)
FONTSIZE = 10
DPI_SCREEN = 100
DPI_PRINT = 300

_GRAN_ORDER = ["G1", "G2", "G3", "G4", "G5_M1", "G5_M2", "G6_M1"]
_GRAN_LABELS = ["G1", "G2", "G3", "G4", "G5\nM1", "G5\nM2", "G6"]


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def save_figure(fig: "plt.Figure", name: str, results_dir: Path) -> None:
    """Speichert Abbildung als PDF (Journal) und PNG (Vorschau)."""
    fig_dir = results_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_dir / f"{name}.pdf", dpi=DPI_PRINT, bbox_inches="tight")
    fig.savefig(fig_dir / f"{name}.png", dpi=DPI_SCREEN, bbox_inches="tight")
    plt.close(fig)
    logger.info("Gespeichert: %s (.pdf + .png)", name)


def _apply_style(ax: "plt.Axes") -> None:
    """Einheitliches Achsen-Styling."""
    ax.tick_params(labelsize=FONTSIZE - 1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


# ---------------------------------------------------------------------------
# F1 — Systemuebersicht (konzeptionell)
# ---------------------------------------------------------------------------

def fig_f1_system_overview(results_dir: Path) -> None:
    """Systemschema: WP, EB, TES, Wärmenetz, CO2-Post-Processing-Kette."""
    if not HAS_MPL:
        return
    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    def box(x, y, w, h, label, color="#E8F0FE", fontsize=9):
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.1",
            linewidth=1.2,
            edgecolor="#333333",
            facecolor=color,
        )
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                fontsize=fontsize, fontweight="bold")

    def arrow(x1, y1, x2, y2):
        ax.annotate(
            "",
            xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", color="#555555", lw=1.5),
        )

    # Komponenten
    box(0.3, 3.2, 1.8, 1.0, "Wärme-\npumpe\n(WP)", color="#D6E8F7")
    box(0.3, 1.8, 1.8, 1.0, "Elektroden-\nkessel\n(EB, S3)", color="#FDE9D9")
    box(0.3, 0.4, 1.8, 1.0, "Therm.\nSpeicher\n(TES, S2)", color="#E8F5E9")
    box(3.5, 2.0, 2.0, 1.5, "Kupfer-\nschiene\n(L1)", color="#FFFDE7")
    box(7.0, 2.0, 2.5, 1.5, "Wärme-\nnetz", color="#F3E5F5")

    # Pfeile
    arrow(2.1, 3.7, 3.5, 2.9)
    arrow(2.1, 2.3, 3.5, 2.6)
    arrow(1.2, 1.4, 1.2, 1.8)
    arrow(2.1, 0.9, 3.5, 2.3)
    arrow(5.5, 2.75, 7.0, 2.75)

    # CO2-Kette unten
    box(0.3, -0.3, 2.2, 0.6, "P_el(t) × EF_G1..G6(t)", color="#FCE4EC", fontsize=8)
    box(3.2, -0.3, 2.5, 0.6, "CO₂-Bilanzen\n(7 Varianten)", color="#FCE4EC", fontsize=8)
    box(6.5, -0.3, 2.5, 0.6, "KPIs\n(K1–K8)", color="#FCE4EC", fontsize=8)
    arrow(2.5, 0.0, 3.2, 0.0)
    arrow(5.7, 0.0, 6.5, 0.0)

    ax.text(5.0, 5.7, "CALION L1 — Paper 3 Systemuebersicht",
            ha="center", va="top", fontsize=12, fontweight="bold")

    save_figure(fig, "F1_system_overview", results_dir)


# ---------------------------------------------------------------------------
# F2 — EF-Zeitreihe 2025
# ---------------------------------------------------------------------------

def fig_f2_ef_timeseries(ef_df: pd.DataFrame, results_dir: Path) -> None:
    """EF-Zeitreihe: ef_g5_m1 (stündlich), ef_g2 (monatlich), ef_g1 (konstant) + EE-Anteil."""
    if not HAS_MPL or ef_df is None:
        return
    fig, ax1 = plt.subplots(figsize=FIGSIZE_DOUBLE)

    ax1.plot(ef_df.index, ef_df["ef_g5_m1"], color="#1F5C99", alpha=0.4,
             lw=0.7, label="G5 (stündl., attributional)")
    ax1.plot(ef_df.index, ef_df["ef_g2"], color="#C55A11", lw=1.5,
             label="G2 (monatl.)")
    ax1.axhline(ef_df["ef_g1"].iloc[0], color="red", lw=1.5, ls="--",
                label=f"G1 (jährl., {ef_df['ef_g1'].iloc[0]:.0f} g/kWh)")

    ax1.set_ylabel("Emissionsfaktor [g CO₂/kWh]", fontsize=FONTSIZE)
    ax1.set_xlabel("2025", fontsize=FONTSIZE)
    _apply_style(ax1)

    if "ee_share_1h" in ef_df.columns:
        ax2 = ax1.twinx()
        ax2.fill_between(ef_df.index, ef_df["ee_share_1h"] * 100,
                         alpha=0.15, color="#27AE60", label="EE-Anteil [%]")
        ax2.set_ylabel("EE-Anteil [%]", fontsize=FONTSIZE, color="#27AE60")
        ax2.tick_params(axis="y", colors="#27AE60", labelsize=FONTSIZE - 1)
        ax2.set_ylim(0, 150)
        ax2.spines["top"].set_visible(False)

    ax1.legend(fontsize=FONTSIZE - 1, loc="upper right")
    ax1.set_title("EF-Zeitreihen 2025", fontsize=FONTSIZE + 1)

    save_figure(fig, "F2_ef_timeseries", results_dir)


# ---------------------------------------------------------------------------
# F3 — EF-Heatmap
# ---------------------------------------------------------------------------

def fig_f3_ef_heatmap(ef_df: pd.DataFrame, results_dir: Path) -> None:
    """EF-Heatmap: Stunde x Monat (ef_g5_m1), RdYlGn_r."""
    if not HAS_MPL or ef_df is None:
        return
    ef = ef_df["ef_g5_m1"].copy()
    ef_pivot = pd.DataFrame({
        "hour": ef.index.hour,
        "month": ef.index.month,
        "ef": ef.values,
    }).groupby(["month", "hour"])["ef"].mean().unstack("hour")

    fig, ax = plt.subplots(figsize=FIGSIZE_DOUBLE)
    im = ax.imshow(ef_pivot.values, aspect="auto", cmap="RdYlGn_r",
                   origin="upper")
    cbar = fig.colorbar(im, ax=ax, label="Ø EF [g CO₂/kWh]")
    cbar.ax.tick_params(labelsize=FONTSIZE - 1)

    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels(range(0, 24, 2), fontsize=FONTSIZE - 1)
    ax.set_yticks(range(12))
    ax.set_yticklabels(
        ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
         "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
        fontsize=FONTSIZE - 1,
    )
    ax.set_xlabel("Stunde des Tages", fontsize=FONTSIZE)
    ax.set_ylabel("Monat", fontsize=FONTSIZE)
    ax.set_title("Mittlerer Emissionsfaktor G5 (stündl., attributional) — 2025",
                 fontsize=FONTSIZE + 1)

    save_figure(fig, "F3_ef_heatmap", results_dir)


# ---------------------------------------------------------------------------
# F4 — Dispatch-Exemplarwoche
# ---------------------------------------------------------------------------

def fig_f4_dispatch_week(
    run_data: dict[str, pd.DataFrame],
    ef_df: pd.DataFrame,
    results_dir: Path,
) -> None:
    """
    Dispatch-Vergleich fuer kälteste + wärmste Woche.

    run_data: {run_id: DataFrame} fuer alle Memmingen S2 Runs (R02, R05, R08).
    """
    if not HAS_MPL or not run_data or ef_df is None:
        return

    # R02=B1, R05=B2, R08=B3 (Memmingen S2)
    run_map = {
        "B1": run_data.get("R02"),
        "B2": run_data.get("R05"),
        "B3": run_data.get("R08"),
    }
    if any(v is None for v in run_map.values()):
        logger.warning("F4: Nicht alle Memmingen-S2-Runs verfuegbar, ueberspringe")
        return

    ref = run_map["B2"]
    t_out = ref.get("t_outside", pd.Series(dtype=float))

    # Kälteste/wärmste Woche anhand Aussentemperatur-Wochenmittel
    if t_out.empty and "ef_g5_m1" in ref.columns:
        # Fallback: Winterwoche = Jan, Sommerwoche = Jul
        weeks = {
            "Winter": (pd.Timestamp("2025-01-13"), pd.Timestamp("2025-01-19")),
            "Sommer": (pd.Timestamp("2025-07-07"), pd.Timestamp("2025-07-13")),
        }
    else:
        weekly_mean = t_out.resample("W-MON").mean()
        cold_start = weekly_mean.idxmin() - pd.Timedelta(days=6)
        warm_start = weekly_mean.idxmax() - pd.Timedelta(days=6)
        weeks = {
            "Winter (kälteste Woche)": (cold_start, cold_start + pd.Timedelta(days=7)),
            "Sommer (wärmste Woche)": (warm_start, warm_start + pd.Timedelta(days=7)),
        }

    ls_map = {"B1": "dashed", "B2": "solid", "B3": "dotted"}
    strat_colors = {"B1": "#888888", "B2": "#1F5C99", "B3": "#C55A11"}

    fig, axes = plt.subplots(4, 2, figsize=(17.4 / 2.54, 14), sharey="row")
    subplot_labels = ["Strompreis\n[EUR/MWh]", "EF\n[g/kWh]",
                      "P_el WP+EB\n[MW]", "SOC TES\n[MWh]"]

    for col_i, (week_label, (t_start, t_end)) in enumerate(weeks.items()):
        for row_i, ylabel in enumerate(subplot_labels):
            ax = axes[row_i][col_i]
            for strat, df in run_map.items():
                week_df = df.loc[str(t_start):str(t_end)]
                if week_df.empty:
                    continue
                if row_i == 0:
                    y = week_df.get("da_price", pd.Series(dtype=float))
                elif row_i == 1:
                    y = ef_df["ef_g5_m1"].reindex(week_df.index, method="nearest")
                elif row_i == 2:
                    y = week_df["p_el_total_mw"]
                else:
                    y = week_df["soc_tes_mwh"]
                ax.plot(week_df.index, y, color=strat_colors[strat],
                        ls=ls_map[strat], lw=1.2, label=strat)
            _apply_style(ax)
            if col_i == 0:
                ax.set_ylabel(ylabel, fontsize=FONTSIZE - 1)
            if row_i == 0:
                ax.set_title(week_label, fontsize=FONTSIZE)
            if row_i == 3:
                ax.tick_params(axis="x", rotation=30, labelsize=FONTSIZE - 2)
            else:
                ax.set_xticklabels([])

    handles = [Line2D([0], [0], color=strat_colors[s], ls=ls_map[s], lw=1.5, label=s)
               for s in ["B1", "B2", "B3"]]
    fig.legend(handles=handles, loc="lower center", ncol=3,
               fontsize=FONTSIZE, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Dispatch-Vergleich — Memmingen S2", fontsize=FONTSIZE + 1, y=1.01)
    fig.tight_layout()

    save_figure(fig, "F4_dispatch_week", results_dir)


# ---------------------------------------------------------------------------
# F5 — Jahreskostenvergleich
# ---------------------------------------------------------------------------

def fig_f5_annual_cost(co2_df: pd.DataFrame, results_dir: Path) -> None:
    """Grouped Bar: Jahreskosten S1/S2/S3 x B1/B2/B3, zwei Panels."""
    if not HAS_MPL or co2_df is None:
        return

    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_DOUBLE, sharey=True)
    networks = ["memmingen", "stadtbach"]
    titles = ["Memmingen", "Stadtbach"]
    strategies = ["B1", "B2", "B3"]
    systems = ["S1", "S2", "S3"]
    sys_colors = {s: COLORS[s] for s in systems}

    x = np.arange(len(strategies))
    width = 0.25

    for ax, net, title in zip(axes, networks, titles):
        net_df = co2_df[co2_df["network"] == net] if "network" in co2_df.columns else co2_df
        for i, sys_name in enumerate(systems):
            sys_df = net_df[net_df["system"] == sys_name] if "system" in net_df.columns else net_df
            vals = []
            for strat in strategies:
                row = sys_df[sys_df["strategy"] == strat] if "strategy" in sys_df.columns else pd.DataFrame()
                val = float(row["cost_eur"].iloc[0]) / 1000.0 if not row.empty else 0.0
                vals.append(val)
            bars = ax.bar(x + i * width, vals, width, label=sys_name,
                          color=sys_colors[sys_name], alpha=0.85)

            # Prozent-Annotation: Ersparnis B2 vs B1
            if len(vals) >= 2 and vals[0] > 0:
                sav = (vals[0] - vals[1]) / vals[0] * 100.0
                ax.annotate(
                    f"{sav:.0f}%↓",
                    xy=(x[1] + i * width, vals[1]),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=7, color=sys_colors[sys_name],
                )

        ax.set_xticks(x + width)
        ax.set_xticklabels(strategies, fontsize=FONTSIZE)
        ax.set_title(title, fontsize=FONTSIZE + 1)
        ax.set_xlabel("Betriebsstrategie", fontsize=FONTSIZE)
        _apply_style(ax)

    axes[0].set_ylabel("Jahreskosten [kEUR/a]", fontsize=FONTSIZE)
    axes[0].legend(title="System", fontsize=FONTSIZE - 1)
    fig.suptitle("Jahresbetriebskosten", fontsize=FONTSIZE + 1)
    fig.tight_layout()

    save_figure(fig, "F5_annual_cost", results_dir)


# ---------------------------------------------------------------------------
# F6 — CO2-Divergenzkurve (KERNFIGUR)
# ---------------------------------------------------------------------------

def fig_f6_co2_divergence(co2_df: pd.DataFrame, results_dir: Path) -> None:
    """
    CO2-Divergenzkurve: x=G1..G6, y=CO2 [t/a] + rel. Fehler [%].

    3 Panels: B1 | B2 | B3. Linien: S1, S2, S3.
    """
    if not HAS_MPL or co2_df is None:
        return

    strategies = ["B1", "B2", "B3"]
    systems = ["S1", "S2", "S3"]
    gran_cols = ["co2_g1", "co2_g2", "co2_g3", "co2_g4", "co2_g5_m1", "co2_g6_m1"]
    gran_labels = ["G1", "G2", "G3", "G4", "G5", "G6"]
    x_pos = np.arange(len(gran_labels))

    fig, axes = plt.subplots(1, 3, figsize=(17.4 / 2.54, 5.5), sharey=False)

    for ax, strat in zip(axes, strategies):
        strat_df = co2_df[co2_df["strategy"] == strat] if "strategy" in co2_df.columns else co2_df
        ax2 = ax.twinx()

        for sys_name in systems:
            sys_df = strat_df[strat_df["system"] == sys_name] if "system" in strat_df.columns else strat_df
            if sys_df.empty:
                continue

            # Mittelwert ueber beide Netzwerke
            vals = [float(sys_df[c].mean()) if c in sys_df.columns else np.nan
                    for c in gran_cols]
            ref = vals[gran_cols.index("co2_g5_m1")] if "co2_g5_m1" in gran_cols else np.nan
            errs = [(v - ref) / ref * 100.0 if ref > 0 else np.nan for v in vals]

            col = COLORS[sys_name]
            ax.plot(x_pos, vals, color=col, lw=2, marker="o", ms=5, label=sys_name)
            ax2.plot(x_pos, errs, color=col, lw=1.5, ls="--", alpha=0.6)

            # G1-Fehler annotieren
            if not np.isnan(errs[0]):
                ax2.annotate(
                    f"{errs[0]:.1f}%",
                    xy=(0, errs[0]), xytext=(5, 0), textcoords="offset points",
                    fontsize=7, color=col,
                )

        # G5-Referenzlinie
        ref_vals = [float(strat_df[strat_df["system"] == s]["co2_g5_m1"].mean())
                    for s in systems
                    if "co2_g5_m1" in strat_df.columns and not strat_df[strat_df["system"] == s].empty]
        if ref_vals:
            for rv in ref_vals:
                ax.axhline(rv, color="gray", lw=0.8, ls="--", alpha=0.5)

        ax.set_xticks(x_pos)
        ax.set_xticklabels(gran_labels, fontsize=FONTSIZE - 1)
        ax.set_title(f"Strategie {strat}", fontsize=FONTSIZE)
        ax.set_xlabel("Granularitaet", fontsize=FONTSIZE - 1)
        _apply_style(ax)
        ax2.set_ylabel("Fehler zu G5 [%]", fontsize=FONTSIZE - 1, color="gray")
        ax2.tick_params(axis="y", colors="gray", labelsize=FONTSIZE - 2)
        ax2.spines["top"].set_visible(False)

    axes[0].set_ylabel("CO₂ [t/a]", fontsize=FONTSIZE)
    handles = [Line2D([0], [0], color=COLORS[s], lw=2, marker="o", ms=5, label=s)
               for s in systems]
    fig.legend(handles=handles, loc="lower center", ncol=3,
               fontsize=FONTSIZE, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("CO₂-Divergenzkurve nach Bilanzierungsgranularitaet",
                 fontsize=FONTSIZE + 1)
    fig.tight_layout()

    save_figure(fig, "F6_co2_divergence", results_dir)


# ---------------------------------------------------------------------------
# F7 — Bilanzierungsfehler Boxplot
# ---------------------------------------------------------------------------

def fig_f7_ef_error_boxplot(co2_df: pd.DataFrame, results_dir: Path) -> None:
    """Boxplot: ef_err [%] fuer G1..G4, G6 ueber alle 18 Runs."""
    if not HAS_MPL or co2_df is None:
        return

    err_cols = ["ef_err_g1_pct", "ef_err_g2_pct", "ef_err_g3_pct",
                "ef_err_g4_pct", "ef_err_g6_m1_pct"]
    labels = ["G1", "G2", "G3", "G4", "G6"]
    data = [co2_df[c].dropna().values for c in err_cols if c in co2_df.columns]
    used_labels = [l for l, c in zip(labels, err_cols) if c in co2_df.columns]

    fig, ax = plt.subplots(figsize=FIGSIZE_SINGLE)
    bp = ax.boxplot(data, labels=used_labels, patch_artist=True, notch=False)

    for patch, label in zip(bp["boxes"], used_labels):
        patch.set_facecolor("#D6E8F7")
        patch.set_alpha(0.8)

    ax.axhline(0, color="black", lw=1.2, ls="-")
    ax.set_ylabel("Bilanzierungsfehler zu G5 [%]", fontsize=FONTSIZE)
    ax.set_xlabel("Granularitaet", fontsize=FONTSIZE)
    ax.set_title("Bilanzierungsfehler — alle 18 Runs", fontsize=FONTSIZE + 1)
    _apply_style(ax)

    save_figure(fig, "F7_ef_error_boxplot", results_dir)


# ---------------------------------------------------------------------------
# F8 — M1 vs M2 Scatter
# ---------------------------------------------------------------------------

def fig_f8_m1_m2_scatter(co2_df: pd.DataFrame, results_dir: Path) -> None:
    """Scatter: co2_g5_m1 vs co2_g5_m2, Farbe=System, Marker=Strategie."""
    if not HAS_MPL or co2_df is None:
        return
    if "co2_g5_m1" not in co2_df.columns or "co2_g5_m2" not in co2_df.columns:
        logger.warning("F8: co2_g5_m1 oder co2_g5_m2 fehlen")
        return

    fig, ax = plt.subplots(figsize=FIGSIZE_SINGLE)
    marker_map = {"B1": "o", "B2": "s", "B3": "^"}

    for _, row in co2_df.iterrows():
        sys_name = row.get("system", "S1")
        strat = row.get("strategy", "B1")
        x_val = row.get("co2_g5_m1", np.nan)
        y_val = row.get("co2_g5_m2", np.nan)
        if np.isnan(x_val) or np.isnan(y_val):
            continue
        ax.scatter(
            x_val, y_val,
            color=COLORS[sys_name],
            marker=marker_map.get(strat, "o"),
            s=60, alpha=0.85, zorder=3,
        )

    # Diagonale y=x
    lims = [
        min(ax.get_xlim()[0], ax.get_ylim()[0]),
        max(ax.get_xlim()[1], ax.get_ylim()[1]),
    ]
    ax.plot(lims, lims, "k--", lw=1, alpha=0.5, label="y = x")
    ax.set_xlim(lims)
    ax.set_ylim(lims)

    ax.set_xlabel("CO₂ G5 M1 — attributional [t/a]", fontsize=FONTSIZE)
    ax.set_ylabel("CO₂ G5 M2 — MEFS [t/a]", fontsize=FONTSIZE)
    ax.set_title("Attributionaler vs. Marginaler EF (G5)", fontsize=FONTSIZE + 1)
    _apply_style(ax)

    sys_handles = [mpatches.Patch(color=COLORS[s], label=s) for s in ["S1", "S2", "S3"]]
    strat_handles = [Line2D([0], [0], color="gray", marker=marker_map[b],
                            ls="none", ms=7, label=b) for b in ["B1", "B2", "B3"]]
    ax.legend(handles=sys_handles + strat_handles, fontsize=FONTSIZE - 1,
              ncol=2, loc="upper left")

    save_figure(fig, "F8_m1_m2_scatter", results_dir)


# ---------------------------------------------------------------------------
# F9 — Monatliche CO2-Heatmap
# ---------------------------------------------------------------------------

def fig_f9_monthly_co2_heatmap(
    monthly_df: Optional[pd.DataFrame],
    results_dir: Path,
) -> None:
    """18 Runs x 12 Monate — CO2 normiert auf Jahresmaximum je Run."""
    if not HAS_MPL or monthly_df is None or monthly_df.empty:
        return

    pivot = monthly_df.pivot_table(
        index="run_id", columns=monthly_df["month"].apply(lambda x: x.month),
        values="co2_g5m1_t", aggfunc="sum",
    )
    pivot = pivot.reindex(sorted(pivot.index))

    # Normieren je Run
    pivot_norm = pivot.div(pivot.max(axis=1), axis=0)

    fig, ax = plt.subplots(figsize=(17.4 / 2.54, 7))
    im = ax.imshow(pivot_norm.values, aspect="auto", cmap="YlOrRd",
                   vmin=0, vmax=1)
    fig.colorbar(im, ax=ax, label="CO₂ normiert [0–1 je Run]")

    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                         "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
                        fontsize=FONTSIZE - 1)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist(), fontsize=FONTSIZE - 2)
    ax.set_title("Monatliche CO₂-Emissionen — normiert je Run (G5 M1)",
                 fontsize=FONTSIZE + 1)
    ax.set_xlabel("Monat", fontsize=FONTSIZE)
    fig.tight_layout()

    save_figure(fig, "F9_monthly_co2_heatmap", results_dir)


# ---------------------------------------------------------------------------
# F10 — RH vs PF Lollipop
# ---------------------------------------------------------------------------

def fig_f10_rh_penalty(co2_df: pd.DataFrame, results_dir: Path) -> None:
    """Lollipop: RH-Penalitaet fuer 6 System×Netz-Kombinationen."""
    if not HAS_MPL or co2_df is None:
        return
    if "rh_pen_pct" not in co2_df.columns:
        logger.warning("F10: rh_pen_pct nicht berechnet, ueberspringe")
        return

    rh_df = co2_df[co2_df["strategy"] == "B3"].dropna(subset=["rh_pen_pct"])
    if rh_df.empty:
        return

    labels = [
        f"{row.get('system','')}\n{row.get('network','')}"
        for _, row in rh_df.iterrows()
    ]
    vals = rh_df["rh_pen_pct"].values

    fig, ax = plt.subplots(figsize=FIGSIZE_SINGLE)
    x = np.arange(len(labels))
    ax.stem(x, vals, linefmt="C0-", markerfmt="C0o", basefmt="k-")
    ax.axhline(0, color="black", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=FONTSIZE - 1)
    ax.set_ylabel("RH-Penalitaet (B3 vs B2) [%]", fontsize=FONTSIZE)
    ax.set_title("Rolling Horizon vs. Perfect Foresight — CO₂-Penalitaet",
                 fontsize=FONTSIZE + 1)
    _apply_style(ax)

    save_figure(fig, "F10_rh_penalty", results_dir)


# ---------------------------------------------------------------------------
# F11 — Netzvergleich normiert
# ---------------------------------------------------------------------------

def fig_f11_network_comparison(co2_df: pd.DataFrame, results_dir: Path) -> None:
    """co2_spez [kg CO2/MWh_th] fuer S1/S2/S3, Memmingen vs Stadtbach."""
    if not HAS_MPL or co2_df is None:
        return

    spez_col = "co2_spez_g5_m1"
    if spez_col not in co2_df.columns:
        logger.warning("F11: %s fehlt", spez_col)
        return

    strategies = ["B1", "B2", "B3"]
    systems = ["S1", "S2", "S3"]
    x = np.arange(len(strategies))
    width = 0.13

    fig, ax = plt.subplots(figsize=FIGSIZE_SINGLE)

    for i, sys_name in enumerate(systems):
        for net, alpha in [("memmingen", 1.0), ("stadtbach", 0.5)]:
            mask = (co2_df.get("system") == sys_name) & (co2_df.get("network") == net)
            vals = []
            for strat in strategies:
                m2 = mask & (co2_df.get("strategy") == strat)
                v = float(co2_df[m2][spez_col].iloc[0]) if co2_df[m2].shape[0] > 0 else 0.0
                vals.append(v)
            offset = i * (width * 2.2) - width
            ax.bar(x + offset, vals, width, color=COLORS[sys_name], alpha=alpha,
                   label=f"{sys_name} {'Mmg' if net == 'memmingen' else 'Stb'}")

    ax.set_xticks(x)
    ax.set_xticklabels(strategies, fontsize=FONTSIZE)
    ax.set_ylabel("Spez. CO₂ [kg CO₂/MWh_th]", fontsize=FONTSIZE)
    ax.set_title("Netzvergleich: Spezifische CO₂-Emissionen (G5 M1)",
                 fontsize=FONTSIZE + 1)
    ax.legend(fontsize=FONTSIZE - 2, ncol=3)
    _apply_style(ax)

    save_figure(fig, "F11_network_comparison", results_dir)


# ---------------------------------------------------------------------------
# F12 — Policy-Implikationsdiagramm
# ---------------------------------------------------------------------------

def fig_f12_policy_implication(co2_df: pd.DataFrame, results_dir: Path) -> None:
    """
    Policy-Implication: mittlerer |Bilanzierungsfehler| nach Granularitaet.

    Farbzonen: Rot (G1), Gelb (G2-G3), Gruen (G5+).
    """
    if not HAS_MPL or co2_df is None:
        return

    err_cols = {
        "G1": "ef_err_g1_pct",
        "G2": "ef_err_g2_pct",
        "G3": "ef_err_g3_pct",
        "G4": "ef_err_g4_pct",
        "G5": None,           # Referenz = 0%
        "G6": "ef_err_g6_m1_pct",
    }
    labels = list(err_cols.keys())
    means = []
    for lbl, col in err_cols.items():
        if col is None:
            means.append(0.0)
        elif col in co2_df.columns:
            means.append(float(co2_df[col].abs().mean()))
        else:
            means.append(float("nan"))

    fig, ax = plt.subplots(figsize=FIGSIZE_SINGLE)
    x = np.arange(len(labels))

    # Farbzonen
    ax.axvspan(-0.5, 0.5, alpha=0.15, color="red", label="GEG / jährl. Bilanz")
    ax.axvspan(0.5, 2.5, alpha=0.15, color="yellow", label="Monatl./wöchentl. Regulatorik")
    ax.axvspan(2.5, 5.5, alpha=0.15, color="green", label="Wissenschaftl. Standard")

    ax.bar(x, means, color=["#C0392B", "#E67E22", "#F39C12", "#27AE60", "#1F5C99", "#9B59B6"],
           alpha=0.85, zorder=2)
    ax.plot(x, means, "ko-", ms=5, lw=1.5, zorder=3)

    # Empfehlungspfeil
    ax.annotate(
        "Mindestanforderung\npreisoptimierter Netze: G4",
        xy=(3, means[3] if not np.isnan(means[3]) else 0),
        xytext=(3.5, max(m for m in means if not np.isnan(m)) * 0.85),
        fontsize=7,
        arrowprops=dict(arrowstyle="->", color="black", lw=1.2),
    )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=FONTSIZE)
    ax.set_ylabel("Ø |Bilanzierungsfehler| [%]", fontsize=FONTSIZE)
    ax.set_xlabel("Granularitaet", fontsize=FONTSIZE)
    ax.set_title("Policy-Implikation: Mindestgranularitaet der CO₂-Bilanzierung",
                 fontsize=FONTSIZE + 1)
    ax.legend(fontsize=FONTSIZE - 2, loc="upper right")
    _apply_style(ax)

    save_figure(fig, "F12_policy_implication", results_dir)


# ---------------------------------------------------------------------------
# Alle Abbildungen generieren
# ---------------------------------------------------------------------------

def generate_all(
    ef_df: Optional[pd.DataFrame] = None,
    co2_df: Optional[pd.DataFrame] = None,
    run_data: Optional[dict[str, pd.DataFrame]] = None,
    monthly_df: Optional[pd.DataFrame] = None,
    results_dir: Optional[Path] = None,
) -> None:
    """
    Generiert alle 12 Abbildungen.

    Fehlende Eingangsdaten werden mit Warnung uebersprungen.
    """
    if not HAS_MPL:
        logger.error("Matplotlib nicht installiert — keine Abbildungen generiert")
        return

    rd = results_dir or RESULTS_DIR
    plt.rcParams.update({"font.size": FONTSIZE})

    logger.info("Generiere Abbildungen in %s ...", rd / "figures")

    fig_f1_system_overview(rd)
    fig_f2_ef_timeseries(ef_df, rd)
    fig_f3_ef_heatmap(ef_df, rd)
    fig_f4_dispatch_week(run_data or {}, ef_df, rd)
    fig_f5_annual_cost(co2_df, rd)
    fig_f6_co2_divergence(co2_df, rd)
    fig_f7_ef_error_boxplot(co2_df, rd)
    fig_f8_m1_m2_scatter(co2_df, rd)
    fig_f9_monthly_co2_heatmap(monthly_df, rd)
    fig_f10_rh_penalty(co2_df, rd)
    fig_f11_network_comparison(co2_df, rd)
    fig_f12_policy_implication(co2_df, rd)

    logger.info("Alle Abbildungen generiert.")
