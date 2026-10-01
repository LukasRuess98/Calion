"""Abbildungen zu den Regelpunkten der Schlechtpunktregelung (anonymisiert, ohne Geografie).

Aufruf aus der Repository-Wurzel:  ``python -m scripts.dhn_study.abbildungen``
Ausgabe: ``docs/dhn_storage_study/abbildungen/*.png``

* ``regelpunkte_signatur.png``: Streuung des Stations-Δp gegen den Durchgriff der Quellen-Δp; Regelpunkte liegen unten links.
* ``regelpunkte_kaeltewoche.png``: Quellen-Δp und Regelpunkte in einer kalten Woche 2025.
* ``regelpunkte_schema.png``: Netzschema mit Erzeugern, Stammleitungen und Lage der Regelpunkte.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import daten, hydraulik

# Referenzpalette (hell): drei kategoriale Slots, Tinte, Raster
SERIE = ["#2a78d6", "#eb6834", "#1baf7a"]
FLAECHE, TINTE, TINTE2, GEDAEMPFT, RASTER, ACHSE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
REGIONEN = {"Süd": "Süd", "City": "Mitte/City", "Mitte-L3": "Mitte/City", "Mitte-L4": "Mitte/City", "L1": "Mitte/City",
            "Ost-L5": "Ost", "Ost-L7": "Ost"}
FARBE_REGION = {"Süd": SERIE[0], "Mitte/City": SERIE[1], "Ost": SERIE[2]}


def _stil(ax):
    ax.set_facecolor(FLAECHE)
    ax.grid(True, color=RASTER, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(ACHSE)
    ax.tick_params(colors=TINTE2, labelsize=9)


def _daten():
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    ta = daten.lade_aussentemperatur()[0].reindex(m.index)
    kd = daten.kunden_dp(m)
    vb = daten.lade_verbraucher()
    return m, e, ta, kd, vb


def _gruppen(s, dx=0.06, dy=0.06):
    """Punkte, die im Diagramm fast zusammenfallen, für eine gemeinsame Beschriftung bündeln."""
    gruppen = []
    for st, r in s.sort_values("Std [bar]").iterrows():
        for g in gruppen:
            if abs(g[1][0] - r["Durchgriff"]) < dx and abs(g[1][1] - r["Std [bar]"]) < dy:
                g[0].append(st)
                break
        else:
            gruppen.append(([st], (r["Durchgriff"], r["Std [bar]"])))
    return [(sorted(n), xy) for n, xy in gruppen]


def signatur(m, e, ta, kd, vb, pfad):
    west = [s for s in kd.columns if vb.region.get(s, "") == "Sekundärnetz West"]
    verbund = [s for s in kd.columns if s not in west and s != "HX_West"]
    dp_kwk = m.gas_CHP_p_supply - m.gas_CHP_p_return
    dp_west = m.boiler_plant_2_secondary_p_supply - m.boiler_plant_2_secondary_p_return
    sv = hydraulik.regelpunkt_signatur(kd[verbund], dp_kwk, e["verbund"] / 10, maske=ta < 8)
    sw = hydraulik.regelpunkt_signatur(kd[west], dp_west, (e["hx_west"] + e["boilers_west"]) / 10, maske=ta < 8)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6), facecolor=FLAECHE, sharey=True)
    for ax, s, titel, regel in ((axs[0], sv, "Verbund – Quelle KWK-Δp", daten.SUED_SCHLECHTPUNKTE),
                                (axs[1], sw, "Westnetz – Quelle Heizwerk-West-Δp", daten.WEST_SCHLECHTPUNKTE)):
        _stil(ax)
        for st, r in s.iterrows():
            reg = REGIONEN.get(vb.region.get(st, "").split(" (")[0], None)
            ist_regel = st in regel
            ax.scatter(r["Durchgriff"], r["Std [bar]"], s=120 if ist_regel else 64, color=FARBE_REGION.get(reg, GEDAEMPFT),
                       zorder=3, edgecolors=TINTE if ist_regel else FLAECHE, linewidths=1.8 if ist_regel else 1.0)
        for namen, (x, y) in _gruppen(s):
            fett = any(n in regel for n in namen)
            ax.annotate("/".join(namen) + ("  Regelpunkt" if fett else ""), (x, y), xytext=(8, 5), textcoords="offset points",
                        fontsize=9, color=TINTE if fett else TINTE2, fontweight="bold" if fett else "normal")
        ax.set_title(titel, fontsize=11, color=TINTE, loc="left")
        ax.set_xlabel("Durchgriff der Quellen-Δp auf die Station [bar/bar]", fontsize=9, color=TINTE2)
        ax.set_xlim(-0.1, 1.1)
        ax.set_ylim(0, None)
    axs[0].set_ylabel("Streuung des Stations-Δp, Heizperiode [bar]", fontsize=9, color=TINTE2)
    handles = [plt.Line2D([], [], marker="o", linestyle="", color=c, markersize=8, label=k)
               for k, c in [*FARBE_REGION.items(), ("Westnetz", GEDAEMPFT)]]
    axs[0].legend(handles=handles, frameon=False, fontsize=9, loc="upper left", labelcolor=TINTE2)
    axs[1].annotate("V09/V16: konstant 1,5 bar,\nvermutlich lokal geregelt", (0.10, 0.045), xytext=(0.55, 0.07),
                    fontsize=8.5, color=GEDAEMPFT, arrowprops={"arrowstyle": "-", "color": GEDAEMPFT, "lw": 0.8})
    fig.suptitle("Regelpunkte: konstant gehalten und unabhängig von der Quellen-Δp (unten links)", fontsize=12,
                 color=TINTE, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(pfad, dpi=150, facecolor=FLAECHE)
    plt.close(fig)
    return sv, sw


def kaeltewoche(m, e, ta, kd, pfad, start="2025-01-13", ende="2025-01-23"):
    w = slice(start, ende)
    dp_kwk = (m.gas_CHP_p_supply - m.gas_CHP_p_return)[w]
    dp_west = (m.boiler_plant_2_secondary_p_supply - m.boiler_plant_2_secondary_p_return)[w]
    mitte = kd[daten.MITTE_STATIONEN].min(axis=1)[w]
    fig, axs = plt.subplots(2, 1, figsize=(11, 6.4), facecolor=FLAECHE, sharex=True)
    for ax, reihen, titel in (
            (axs[0], [("KWK-Δp", dp_kwk), ("V06 (Regelpunkt)", kd.V06[w]), ("Minimum Mitte/City", mitte)], "Verbund"),
            (axs[1], [("Heizwerk-West-Δp", dp_west), ("V01 (Regelpunkt)", kd.V01[w]), ("V13 (Regelpunkt)", kd.V13[w])],
             "Westnetz")):
        _stil(ax)
        enden = []
        for (lab, s), c in zip(reihen, SERIE, strict=True):
            ax.plot(s.index, s.values, color=c, linewidth=1.6, label=lab)
            enden.append([float(s.dropna().iloc[-1]), lab, s.index[-1]])
        enden.sort()
        for i in range(1, len(enden)):                                   # Mindestabstand 0,25 bar
            enden[i][0] = max(enden[i][0], enden[i - 1][0] + 0.25)
        for y, lab, x in enden:
            ax.annotate(lab, (x, y), xytext=(6, 0), textcoords="offset points", fontsize=9, color=TINTE2, va="center")
        ax.set_title(titel, fontsize=11, color=TINTE, loc="left")
        ax.set_ylabel("Δp [bar]", fontsize=9, color=TINTE2)
        ax.set_ylim(0, None)
        ax.legend(frameon=False, fontsize=9, loc="upper left", ncol=3, labelcolor=TINTE2)
    t = ta[w].resample("D").mean()
    axs[1].set_xlabel("Tagesmittel Außentemperatur: " + ", ".join(f"{v:.0f} °C" for v in t.values), fontsize=9, color=TINTE2)
    fig.suptitle(f"Kalte Tage {pd.Timestamp(start):%d.%m.}–{pd.Timestamp(ende):%d.%m.%Y}: Quellen-Δp schwankt, Regelpunkte bleiben bei ≈ 1,2 bar",
                 fontsize=12, color=TINTE, x=0.01, ha="left")
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 0.9, 1))
    fig.savefig(pfad, dpi=150, facecolor=FLAECHE)
    plt.close(fig)


def schema(kd, ta, vb, pfad):
    """Netzschema ohne Geografie: Stammleitungen ab KWK, Ost-Transport, Süd mit PS1/HW1, Westnetz über WÜ."""
    kalt = kd[ta.reindex(kd.index) < -2].median()
    knoten = {"KWK": (0, 0), "Ost": (6.2, 4.6), "S/V22": (3.4, 3.2), "V08/V11/V18": (5.2, 3.0), "V07": (5.0, 1.0),
              "V15/V19": (3.0, 1.2), "City": (0.9, 1.7), "V23": (-1.6, 1.8), "V12": (0.6, -1.4), "PS1": (0.6, -3.0),
              "V05/V14": (0.9, -4.4), "HW1": (1.0, -5.3), "V06": (1.3, -6.4), "PS2": (-2.2, -0.5), "HW2": (-4.2, -0.9),
              "V02/V04/V21": (-5.6, -2.4), "V13": (-6.6, 1.6), "V01": (-5.2, 3.4), "V09/V16": (-6.4, -0.2)}
    leitungen_verbund = [("KWK", "S/V22"), ("S/V22", "V08/V11/V18"), ("V08/V11/V18", "Ost"), ("KWK", "V15/V19"),
                         ("V15/V19", "V07"), ("V07", "Ost"), ("KWK", "City"), ("KWK", "V23"), ("KWK", "V12"),
                         ("V12", "PS1"), ("PS1", "V05/V14"), ("V05/V14", "HW1"), ("HW1", "V06"), ("KWK", "PS2"), ("PS2", "HW2")]
    leitungen_west = [("HW2", "V02/V04/V21"), ("HW2", "V09/V16"), ("V09/V16", "V13"), ("V09/V16", "V01")]
    fig, ax = plt.subplots(figsize=(11, 8.2), facecolor=FLAECHE)
    ax.set_facecolor(FLAECHE)
    ax.axis("off")
    for a, b in leitungen_verbund:
        (x1, y1), (x2, y2) = knoten[a], knoten[b]
        ax.plot([x1, x2], [y1, y2], color=ACHSE, linewidth=3.0, zorder=1, solid_capstyle="round")
    for a, b in leitungen_west:
        (x1, y1), (x2, y2) = knoten[a], knoten[b]
        ax.plot([x1, x2], [y1, y2], color=GEDAEMPFT, linewidth=1.8, zorder=1, linestyle=(0, (4, 2)))
    erzeuger = {"KWK": "KWK\n(Druckhalter)", "Ost": "MVA · GT · Bio-KWK\n(Ost-Transport L5–L7)", "HW1": "HW1", "HW2": "Heizwerk West\n(HW2, WÜ)",
                "PS1": "PS1", "PS2": "PS2"}
    versatz = {"HW2": (-20, -34), "PS2": (6, 10), "KWK": (12, 8), "Ost": (-60, 14)}
    for k, lab in erzeuger.items():
        x, y = knoten[k]
        ax.scatter(x, y, marker="s", s=170, color=TINTE, zorder=3)
        ax.annotate(lab, (x, y), xytext=versatz.get(k, (10, 6)), textcoords="offset points", fontsize=9.5, color=TINTE,
                    fontweight="bold")
    regel = set(daten.SUED_SCHLECHTPUNKTE + daten.WEST_SCHLECHTPUNKTE)
    for k in knoten:
        if k in erzeuger:
            continue
        x, y = knoten[k]
        ids = [i for i in k.replace("S/", "").split("/") if i.startswith("V")] or (["V03", "V10", "V24"] if k == "City" else [])
        werte = [kalt.get(i) for i in ids if i in kalt.index and pd.notna(kalt.get(i))]
        if len(werte) > 1 and round(min(werte), 1) != round(max(werte), 1):
            dp_txt = f"Δp {min(werte):.1f}–{max(werte):.1f} bar"
        else:
            dp_txt = f"Δp {werte[0]:.2f} bar" if werte else ""
        ist_regel = k in regel
        ax.scatter(x, y, s=150 if ist_regel else 70, color=SERIE[1] if ist_regel else SERIE[0], zorder=4,
                   edgecolors=TINTE if ist_regel else FLAECHE, linewidths=1.8 if ist_regel else 1.0)
        name = {"City": "City (V03/V10/V24)", "S/V22": "Standort S (V22)"}.get(k, k)
        ax.annotate(name + ("  · Regelpunkt" if ist_regel else "") + (f"\n{dp_txt}" if dp_txt else ""), (x, y),
                    xytext=(10, -14), textcoords="offset points", fontsize=9, color=TINTE if ist_regel else TINTE2,
                    fontweight="bold" if ist_regel else "normal")
    ax.annotate("Stammleitung L4 (Süd)", (0.1, -2.8), fontsize=8.5, color=GEDAEMPFT, rotation=90)
    ax.annotate("Westnetz (PN16, über WÜ getrennt)", (-6.9, 4.3), fontsize=9, color=GEDAEMPFT)
    ax.plot([], [], color=ACHSE, linewidth=3, label="Verbund (PN25)")
    ax.plot([], [], color=GEDAEMPFT, linewidth=1.8, linestyle=(0, (4, 2)), label="Westnetz")
    ax.scatter([], [], s=150, color=SERIE[1], edgecolors=TINTE, linewidths=1.8, label="Regelpunkt der Schlechtpunktregelung")
    ax.scatter([], [], s=70, color=SERIE[0], label="Messstelle (Δp-Median bei Ta < −2 °C)")
    ax.scatter([], [], marker="s", s=120, color=TINTE, label="Erzeuger / Pumpstation")
    ax.legend(frameon=False, fontsize=9, loc="lower right", labelcolor=TINTE2)
    ax.set_title("Netzschema DHN-A (ohne Geografie): Lage der Regelpunkte", fontsize=12, color=TINTE, loc="left")
    ax.set_xlim(-7.6, 8.2)
    ax.set_ylim(-7.2, 5.4)
    fig.tight_layout()
    fig.savefig(pfad, dpi=150, facecolor=FLAECHE)
    plt.close(fig)


def netzmodell_abbildungen(out):
    """Abgleich Netzmodell–Messung (benötigt ``python -m scripts.dhn_study.run_netzmodell``)."""
    res = daten.repo_root() / "results" / "dhn_study" / "netzmodell"
    if not (res / "simulation.parquet").exists():
        return
    from . import netzmodell as nm
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    nz = nm.netz()
    f = nm.randbedingungen(m, e, nz)
    sim = pd.read_parquet(res / "simulation.parquet")
    # 1) Zeitreihen Spitzenzeit (Holdout)
    w = slice("2025-02-10", "2025-02-23")
    fig, axs = plt.subplots(2, 2, figsize=(11, 6.2), facecolor=FLAECHE, sharex=True)
    for ax, (z, titel) in zip(axs.ravel(), (("V06", "V06 – Regelpunkt Süd"), ("V03", "V03 – City"),
                                             ("V22", "V22 – Standort S"), ("MVA", "MVA – Ost-Erzeuger")), strict=True):
        _stil(ax)
        ax.plot(f.ziele[z][w].index, f.ziele[z][w].values, color=SERIE[0], linewidth=1.4, label="Messung")
        ax.plot(sim[z][w].index, sim[z][w].values, color=SERIE[1], linewidth=1.4, label="Modell")
        ax.set_title(titel, fontsize=10.5, color=TINTE, loc="left")
        ax.set_ylabel("Δp [bar]", fontsize=9, color=TINTE2)
    axs[0, 0].legend(frameon=False, fontsize=9, loc="upper left", labelcolor=TINTE2, ncol=2)
    fig.suptitle("Netzmodell gegen Messung, Spitzenzeit 10.–23.02.2025 (Holdout, nicht in der Kalibrierung)", fontsize=12,
                 color=TINTE, x=0.01, ha="left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out / "netzmodell_zeitreihen.png", dpi=150, facecolor=FLAECHE)
    plt.close(fig)
    # 2) Güte je Messziel (Holdout, Hochlast)
    g = pd.read_csv(res / "guete.csv", header=[0, 1], index_col=0)
    gh = g["Holdout Hochlast"].drop([c for c in g.index if c.startswith("Fluss")])
    g0 = g["ohne Kalibrierung, Holdout Hochlast"].reindex(gh.index)
    fig, ax = plt.subplots(figsize=(11, 4.4), facecolor=FLAECHE)
    _stil(ax)
    x = range(len(gh))
    ax.scatter(x, g0["RMSE"], s=40, color=GEDAEMPFT, label="ohne Kalibrierung", zorder=3)
    ax.scatter(x, gh["RMSE"], s=64, color=SERIE[0], label="kalibriert (RMSE)", zorder=4)
    ax.scatter(x, gh["Bias"].abs(), s=40, color=SERIE[1], marker="D", label="kalibriert (|Bias|)", zorder=4)
    ax.axhline(0.2, color=TINTE2, linewidth=0.9, linestyle=(0, (4, 2)))
    ax.annotate("gestrichelt: Kriterium Plan 3.1, RMSE ≤ 0,2 bar", (len(gh) - 0.5, 0.012), fontsize=8.5, color=TINTE2,
                ha="right")
    ax.set_xticks(list(x))
    ax.set_xticklabels(gh.index, rotation=0, fontsize=8.5)
    ax.set_ylabel("Abweichung [bar]", fontsize=9, color=TINTE2)
    ax.set_yscale("log")
    ax.legend(frameon=False, fontsize=9, loc="upper right", labelcolor=TINTE2)
    ax.set_title("Güte im Holdout bei Hochlast (oberes Lastzehntel, 241 h)", fontsize=11, color=TINTE, loc="left")
    fig.tight_layout()
    fig.savefig(out / "netzmodell_guete.png", dpi=150, facecolor=FLAECHE)
    plt.close(fig)
    # 3) Hebel Messung gegen Modell
    h = pd.read_csv(res / "hebel_holdout.csv", header=[0, 1], index_col=0)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4), facecolor=FLAECHE)
    for ax, (reg, titel) in zip(axs, (("KWK-Fluss", "je 100 kg/s KWK-Durchfluss (Ersatz durch Ost)"),
                                      ("HW1", "je 100 kg/s HW1 (Süd statt Ost)")), strict=True):
        _stil(ax)
        y = range(len(h))
        ax.errorbar(h[("Messung", reg)], y, xerr=2 * h[("SE Messung", reg)], fmt="o", color=SERIE[0], markersize=7,
                    capsize=3, label="Messung ± 2 SE")
        ax.scatter(h[("Modell", reg)], y, s=60, marker="D", color=SERIE[1], label="Modell", zorder=4)
        ax.axvline(0, color=ACHSE, linewidth=0.8)
        ax.set_yticks(list(y))
        ax.set_yticklabels(h.index, fontsize=9)
        ax.set_title(titel, fontsize=10.5, color=TINTE, loc="left")
        ax.set_xlabel("Δp-Änderung [bar]", fontsize=9, color=TINTE2)
    axs[0].legend(frameon=False, fontsize=9, loc="lower left", labelcolor=TINTE2)
    fig.suptitle("Hebel aus natürlichen Experimenten (Holdout, Heizperiode): gleiche Regression auf Messung und Modell",
                 fontsize=12, color=TINTE, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out / "netzmodell_hebel.png", dpi=150, facecolor=FLAECHE)
    plt.close(fig)
    # 4) Hebel „Ost statt KWK“ je KWK-Durchflussband: Grenze der Extrapolation
    hb = pd.read_csv(res / "hebel_kwk_baender.csv", index_col=[0, 1])
    baender = ["0–180 kg/s", "180–240 kg/s", "240–600 kg/s"]
    fig, axs = plt.subplots(1, 4, figsize=(11, 3.9), facecolor=FLAECHE, sharey=False)
    for ax, (st, titel) in zip(axs, (("V03", "V03 – City"), ("V06", "V06 – Regelpunkt Süd"), ("V22", "V22 – Standort S"),
                                     ("PS1", "PS1 – Pumpstation Süd")), strict=True):
        _stil(ax)
        d = hb.loc[st].reindex(baender)
        x = np.arange(len(baender))
        ax.errorbar(x - 0.08, d["Messung"], yerr=2 * d["SE"], fmt="o", color=SERIE[0], markersize=7, capsize=3,
                    label="Messung ± 2 SE")
        ax.scatter(x + 0.08, d["Modell"], s=56, marker="D", color=SERIE[1], label="Modell", zorder=4)
        ax.set_xticks(x)
        ax.set_xticklabels(["< 180", "180–240", "> 240"], fontsize=8.5)
        ax.set_xlabel("KWK-Durchfluss [kg/s]", fontsize=8.5, color=TINTE2)
        ax.set_ylim(0, None)
        ax.set_title(titel, fontsize=10, color=TINTE, loc="left")
    axs[0].set_ylabel("bar je 100 kg/s", fontsize=9, color=TINTE2)
    axs[0].legend(frameon=False, fontsize=8.5, loc="lower left", labelcolor=TINTE2)
    fig.suptitle("Hebel „Ost statt KWK“ je Durchflussband (Heizperiode): Modell bis 240 kg/s passend, darüber zu steil",
                 fontsize=12, color=TINTE, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out / "netzmodell_hebel_baender.png", dpi=150, facecolor=FLAECHE)
    plt.close(fig)


def main():
    out = daten.repo_root() / "docs" / "dhn_storage_study" / "abbildungen"
    out.mkdir(parents=True, exist_ok=True)
    m, e, ta, kd, vb = _daten()
    signatur(m, e, ta, kd, vb, out / "regelpunkte_signatur.png")
    kaeltewoche(m, e, ta, kd, out / "regelpunkte_kaeltewoche.png")
    schema(kd, ta, vb, out / "regelpunkte_schema.png")
    netzmodell_abbildungen(out)
    return out


if __name__ == "__main__":
    print(main())
