"""Netzmodell DHN-A: Kalibrierung an den Messwerten 2025, Validierung (Holdout, Hebel, Ost-Kopplung) und Auslegungsfall.

Aufruf aus der Repository-Wurzel:
* ``python -m scripts.dhn_study.run_netzmodell --ohne-kalibrierung``: verwendet die veröffentlichte Kalibrierung
  (``scripts/dhn_study/kalibrierung/``) und rechnet Validierung und Auslegung (≈ 1 min). Damit sind alle Zahlen in
  ``docs/dhn_storage_study/Netzmodell.md`` reproduzierbar.
* ``python -m scripts.dhn_study.run_netzmodell``: kalibriert neu, ausgehend von der veröffentlichten Kalibrierung
  (≈ 30 min); ``--von-null`` startet bei den Prior-Werten. Die Optimierung kann in einem anderen lokalen Optimum enden.
Ergebnisse: ``results/dhn_study/netzmodell/`` (CSV, ``zusammenfassung.md``); Abbildungen ``docs/dhn_storage_study/abbildungen/``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import anker, daten, hydraulik
from . import netzmodell as nm
from .run_analyse import T_VL_AUSL, _md

KALIBRIERUNG_REPO = Path(__file__).resolve().parent / "kalibrierung"   # veröffentlichte Kalibrierung
SPEICHER_MW = 40.0
PAAR_GEWICHT = 1.0
HEBEL_GEWICHT = 1.0
# Der KWK-interne Verlust wächst quadratisch mit dem KWK-Durchfluss; der gemessene Hebel des KWK-Durchflusses bleibt aber über
# 130–330 kg/s konstant. Der interne Verlust wird deshalb eng an den Planwert gebunden (sonst falsche Extrapolation).
KANTEN_SIGMA = {"KWKi": 0.2}
MINDEST_MITTE = 1.0
# Temperatur-Tracer (Datenanalyse Abschnitt 8): Station -> (Temperatursignal, Modellknoten). V05 (Süd) liegt ohne
# Lageangabe entweder vor oder hinter HW1; beide Knoten werden gezeigt.
TRACER_STATIONEN = {"V22": ("V22_T_supply", "S"), "V11": ("V11_T_supply", "L5M"), "V15": ("V15_house_T_supply", "K3"),
                    "V23": ("V23_T_supply", "L1G"), "V17": ("V17_T_supply", "SEC2"), "V12": ("V12_T_supply", "SEC4"),
                    "V24": ("V24_T_supply", "SEC2"), "V05 (vor HW1)": ("V05_T_supply", "SUED_N"),
                    "V05 (hinter HW1)": ("V05_T_supply", "SUED_S")}
# KWK-Durchflussbänder der Hebelprüfung; das Band ab 180 kg/s (Kältebetrieb) verankert die Speicherentlastung
BAENDER = ((0, 180), (180, 240), (240, 600), (180, 600))
BAND_AUSLEGUNG = (180, 600)


def aufteilung(f: nm.Fall, ta: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Holdout = jede vierte Kalenderwoche + Spitzenzeit 10.–23.02.; Kalibrierung = Stundenpaare (h, h+1) aus dem Rest,
    Kältestunden dichter abgetastet. Rückgabe: Holdout-Maske, Zeilenindizes der Kalibrierpaare (geordnet)."""
    T = ta.reindex(f.index).to_numpy()
    wk = f.index.isocalendar().week.to_numpy()
    hold = (wk % 4 == 1) | ((f.index >= "2025-02-10") & (f.index < "2025-02-24"))
    idx = np.arange(len(f.index) - 1)
    ok = ~hold[:-1] & ~hold[1:] & ((f.index[1:] - f.index[:-1]) == pd.Timedelta(hours=1))
    start = np.concatenate([idx[ok & (T[:-1] < 5)][::6], idx[ok & ~(T[:-1] < 5)][::20]])
    start = np.sort(start)
    return hold, np.ravel(np.column_stack([start, start + 1]))


def kalibrier_eingaben(m: pd.DataFrame, e: pd.DataFrame, ta: pd.Series, f: nm.Fall) -> dict:
    """Eingaben der Kalibrierung: Holdout-Maske, Kalibrierpaare, Hebel-Trainingsstunden (Heizperiode), Stundengewichte."""
    hold, sel = aufteilung(f, ta)
    ft = f.teil(sel)
    hreg = nm.hebel_regressoren(m, e, f.index)
    heiz = (ta.reindex(f.index) < 8).to_numpy()
    return {"hold": hold, "sel": sel, "ft": ft, "hreg": hreg, "heiz": heiz,
            "hebel": {"fall": f.teil(~hold & heiz), "reg": hreg[~hold & heiz], "gewicht": HEBEL_GEWICHT},
            "gewichtung": np.where(ta.reindex(ft.index).to_numpy() < 5, 3.0, 1.0)}


def kalibrier_problem(nz: nm.Netz, ein: dict) -> dict:
    """Residuenfunktion der Kalibrierung mit den Einstellungen dieses Laufs (``nm.kalibrier_problem``)."""
    return nm.kalibrier_problem(nz, ein["ft"], gewichtung=ein["gewichtung"], paar_gewicht=PAAR_GEWICHT, hebel=ein["hebel"],
                                kanten_sigma=KANTEN_SIGMA)


def auslegung_eingaben(m: pd.DataFrame, e: pd.DataFrame, ta: pd.Series, nz: nm.Netz) -> dict:
    """Randbedingungen des Auslegungsfalls (−14 °C, n−1, West aus eigenen Kesseln): Spreizung aus dem gemessenen
    Rücklauf bei Kälte, Ost nach Plan A und wie 2025, HW1, Pumpengewinne, Mindest-Δp, Lastfälle, Pumpengrenze KWK."""
    anl = daten.lade_anlagen()["plants"]
    t_rl = float(m.gas_CHP_T_return[ta < -5].median())
    kalt = ta < -2
    ps1 = m.pump_station_1_p_supply_after_pump - m.pump_station_1_p_supply_before_pump
    gewinn = np.zeros((1, len(nz.kanten)))
    gewinn[0, nz.kanten_ids.index("L4c")] = float(ps1.quantile(0.99))
    gewinn[0, nz.kanten_ids.index("W1")] = float((m.pump_station_2_dp_supply_after_pump
                                                  - m.pump_station_2_dp_supply_before_pump)[kalt].median())
    gt_an = e["gas_turbine"] > 2
    return {"T_RL": t_rl, "dT": T_VL_AUSL - t_rl, "dh": float(daten.dh(T_VL_AUSL, t_rl)),
            "ost": {"Ost Plan A": {"MVA": anl["waste_incineration"]["P_max_MW"]["design_minus14C"],
                                   "GT": anl["gas_turbine"]["P_max_MW"]["design_minus14C"],
                                   "BIO": anl["biomass_CHP"]["P_max_MW"]["design_minus14C"]},
                    "Ost wie 2025": {"MVA": float(e["waste_incineration"][kalt].median()),
                                     "GT": float(e["gas_turbine"][kalt & gt_an].median()),
                                     "BIO": float(e["biomass_CHP"][kalt].median())}},
            "hw1_mw": anl["boiler_plant_1"]["P_max_MW"]["design_minus14C"], "hw1_m": anl["boiler_plant_1"]["m_max_t_h"] / 3.6,
            "gewinn": gewinn, "ps1_quantile": {"P95": float(ps1.quantile(0.95)), "P99": float(ps1.quantile(0.99))},
            "mindest": {"V06": 1.2, **{s: MINDEST_MITTE for s in nm.MITTE_ZIELE}},
            "faelle": {"P50": (235.0, 1.0), "P90": (252.0, 3.7)},   # Verbund-Stundenlast, West-Bezug [MW] (Datenanalyse 6)
            "pumpe": hydraulik.dp_aus_pumpe(anl["gas_CHP"]["pumps"]["head_m"], T_VL_AUSL, anl["gas_CHP"]["dp_internal_bar"])}


def speichere_kalibrierung(kal: dict, nz: nm.Netz, ordner: Path) -> None:
    """Kalibrierung als CSV: Widerstände je Kante sowie Lastgewichte, Grundlast und Stationsversatz."""
    ordner.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"Multiplikator": kal["multiplikator"], "K [bar/(kg/s)²]": kal["K"],
                  "K_prior": nz.k0}).rename_axis("Kante").to_csv(ordner / "kalibrierung_kanten.csv")
    pd.Series({**{f"Gewicht {k}": v for k, v in kal["gewichte"].items()},
               **{f"Grundlast {k} [kg/s]": v for k, v in kal["grundlast"].items()},
               **{f"Versatz {k} [bar]": v for k, v in kal["versatz"].items()}}).to_csv(ordner / "kalibrierung_last_versatz.csv")


def kalibriervarianten() -> tuple[list[str], str]:
    """Gleich gute Kalibriervarianten (``mehrfachstart``) und die Referenz (niedrigste Kosten). Ohne Übersicht nur „A“."""
    datei = KALIBRIERUNG_REPO / "uebersicht.csv"
    if not datei.exists():
        return ["A"], "A"
    u = pd.read_csv(datei, index_col=0)
    gut = u[u["gleich gut"].astype(str).str.lower() == "true"]
    return list(gut.index), str(u["Kosten"].idxmin())


def kalibrierung_ordner(out: Path) -> Path:
    """Ordner der zu verwendenden Kalibrierung: die des letzten Laufs in ``out``, sonst die veröffentlichte."""
    return out if (out / "kalibrierung_kanten.csv").exists() else KALIBRIERUNG_REPO / kalibriervarianten()[1]


def lade_kalibrierung(out, nz: nm.Netz) -> dict:
    """Kalibrierung aus den CSV-Dateien eines Laufs (bzw. der veröffentlichten Kalibrierung) wiederherstellen."""
    k = pd.read_csv(out / "kalibrierung_kanten.csv", index_col=0)
    lv = pd.read_csv(out / "kalibrierung_last_versatz.csv", index_col=0).iloc[:, 0]
    sub = lambda pre, suf="": {i[len(pre):].replace(suf, ""): float(v) for i, v in lv.items() if i.startswith(pre)}  # noqa: E731
    return {"K": k.loc[nz.kanten_ids, "K [bar/(kg/s)²]"].to_numpy(), "multiplikator": k.loc[nz.kanten_ids, "Multiplikator"],
            "gewichte": sub("Gewicht "), "grundlast": sub("Grundlast ", " [kg/s]"),
            "versatz": pd.Series(sub("Versatz ", " [bar]")), "erfolg": True, "kosten": float("nan")}


def main(neu_kalibrieren: bool = True, von_null: bool = False) -> dict:
    out = daten.repo_root() / "results" / "dhn_study" / "netzmodell"
    out.mkdir(parents=True, exist_ok=True)
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    ta = daten.lade_aussentemperatur()[0].reindex(m.index)
    nz = nm.netz()
    f = nm.randbedingungen(m, e, nz)
    ein = kalibrier_eingaben(m, e, ta, f)
    hold, sel, ft, hreg, heiz = ein["hold"], ein["sel"], ein["ft"], ein["hreg"], ein["heiz"]
    erg = {"stunden": {"gesamt": len(f.index), "Kalibrierung": len(sel), "Holdout": int(hold.sum())}}

    # 1) Kalibrierung auf Pegel, stündliche Änderungen und gemessene Hebel (Heizperiode, nur Trainingswochen)
    if neu_kalibrieren:
        start = None if von_null else lade_kalibrierung(KALIBRIERUNG_REPO / kalibriervarianten()[1], nz)
        kal = nm.kalibriere(nz, ft, gewichtung=ein["gewichtung"], paar_gewicht=PAAR_GEWICHT, hebel=ein["hebel"],
                            kanten_sigma=KANTEN_SIGMA, start=start)
    else:
        kal = lade_kalibrierung(KALIBRIERUNG_REPO / kalibriervarianten()[1], nz)
    erg["kal"] = kal
    speichere_kalibrierung(kal, nz, out)

    # 2) Validierung: Güte Holdout / Hochlast, Prior-Modell zum Vergleich
    vs, gw, gl = kal["versatz"].to_dict(), kal["gewichte"], kal["grundlast"]
    sim = nm.simuliere(nz, f, kal["K"], vs, gw, gl)
    sim0 = nm.simuliere(nz, f, nz.k0)
    last = e["verbund"].reindex(f.index).to_numpy()
    hoch = hold & (last >= np.nanquantile(last[hold], 0.9))
    erg["guete"] = pd.concat({"Holdout": nm.guete(sim[hold], f.ziele[hold]),
                              "Holdout Hochlast": nm.guete(sim[hoch], f.ziele[hoch]),
                              "ohne Kalibrierung, Holdout Hochlast": nm.guete(sim0[hoch], f.ziele[hoch])}, axis=1)
    erg["guete"].to_csv(out / "guete.csv")
    sim.to_parquet(out / "simulation.parquet")

    # 3) Hebel: gleiche Differenzenregression auf Messung und Modell, Holdout-Wochen der Heizperiode
    hm_, hs_, hse = nm.hebel_vergleich(f.teil(hold & heiz), hreg[hold & heiz], sim[hold & heiz])
    erg["hebel"] = pd.concat({"Messung": hm_, "Modell": hs_, "SE Messung": hse}, axis=1)
    erg["hebel"].to_csv(out / "hebel_holdout.csv")
    # Hebel „Ost statt KWK“ je KWK-Durchflussband (Heizperiode, alle Stunden). Der West-Übergabestrom ist zusätzlicher
    # Regressor, damit der KWK-Koeffizient reiner Ost-Ersatz ist. Bleibt der Hebel konstant, wachsen die Verluste nicht
    # quadratisch mit dem KWK-Durchfluss – entscheidend für die Extrapolation auf den Auslegungsfall.
    hreg_w = nm.hebel_regressoren(m, e, f.index, mit_west=True)
    kwk_f = (hreg["KWK-Fluss"] * 100).to_numpy()
    zeilen_b, ost_hebel = [], {}
    for lo, hi in BAENDER:
        band = heiz & (kwk_f >= lo) & (kwk_f < hi)
        hm_b, hs_b, se_b = nm.hebel_vergleich(f.teil(band), hreg_w[band], sim[band])
        hm_f, hs_f, _ = nm.hebel_vergleich_fest(f.teil(band), hreg_w[band], sim[band])   # Gegenprobe: KWK-Δp-Koeff. = 1
        zeilen_b += [{"Band": f"{lo}–{hi} kg/s", "Stunden": int(band.sum()), "Station": st,
                      "Messung": -hm_b.loc[st, "KWK-Fluss"], "SE": se_b.loc[st, "KWK-Fluss"],
                      "Modell": -hs_b.loc[st, "KWK-Fluss"],
                      "Messung, KWK-Δp-Koeff. 1": -hm_f.loc[st, "KWK-Fluss"],
                      "Modell, KWK-Δp-Koeff. 1": -hs_f.loc[st, "KWK-Fluss"]} for st in nm.HEBEL_ZIELE]
        if (lo, hi) == BAND_AUSLEGUNG:
            ost_hebel = {st: (-hm_b.loc[st, "KWK-Fluss"], se_b.loc[st, "KWK-Fluss"]) for st in nm.HEBEL_ZIELE}
    erg["hebel_band"] = pd.DataFrame(zeilen_b).set_index(["Station", "Band"]).sort_index()
    erg["hebel_band"].to_csv(out / "hebel_kwk_baender.csv")
    # Strukturelle Hebel im Modell (Störung +10 kg/s anstelle von KWK-Wasser, KWK-Δp fest), Hochlast-Holdout
    fh = f.teil(hoch)
    struk = {k: nm.hebel_modell(nz, fh, kal["K"], kn, gw, gl) for k, kn in
             (("Süd (HW1)", "HW1"), ("Ost (MVA)", "MVA"), ("Standort S", "S"), ("Südende", "SUED_E"))}
    erg["hebel_struktur"] = pd.DataFrame(struk).loc[[nm.STATIONEN[s] for s in ["V06", "V03", "V22", "V15"]]]
    erg["hebel_struktur"].index = ["V06", "V03/V10/V24", "V22", "V15"]
    erg["hebel_struktur"].to_csv(out / "hebel_struktur.csv")
    # 4) Ost-Kopplung im Modell gegen Messung (gleiche Regression auf Modellwerten)
    ms = hydraulik.massenstroeme(m, e)
    ps1 = m.pump_station_1_p_supply_after_pump - m.pump_station_1_p_supply_before_pump
    msf = ms.reindex(f.index)
    kop_mess = hydraulik.fit_ost_kopplung(f.ziele["MVA"], pd.Series(f.dp_kwk, f.index), msf.Ost, msf.KWK)
    kop_mod = hydraulik.fit_ost_kopplung(sim["MVA"], pd.Series(f.dp_kwk, f.index), msf.Ost, msf.KWK)
    erg["kopplung"] = pd.DataFrame({"Messung": kop_mess, "Modell": kop_mod}).loc[["c", "d", "f", "r2"]]

    # 3.5 Temperatur-Tracer: Mischungsanteile aus den Modellflüssen (Aufwind, Quellmarkierung); daraus eine synthetische
    # Stationstemperatur aus den gemessenen Quelltemperaturen und darauf dieselbe Regression wie in der Datenanalyse
    b_all = f.b(nz, gw, gl)
    phi = nm.quellanteile(nz, nz.loese(b_all, kal["K"], f.gewinn), b_all)
    mm = m.reindex(f.index)
    t_q = {"KWK": mm.gas_CHP_T_supply, "MVA": mm.waste_incineration_T_supply,
           "GT": mm.gas_turbine_T_supply.fillna(mm.waste_incineration_T_supply), "BIO": mm.biomass_CHP_T_supply,
           "HW1": mm.boiler_plant_1_T_supply.fillna(mm.gas_CHP_T_supply)}
    Tq = np.stack([t_q[q].to_numpy() for q in nm.QUELLEN], axis=1)
    t_ost = mm[["waste_incineration_T_supply", "biomass_CHP_T_supply"]].mean(axis=1)
    winter = pd.Series(f.index.month.isin([1, 2, 11, 12]), index=f.index)
    sel_t = (winter & ((t_ost - mm.gas_CHP_T_supply).abs() > 3)).to_numpy()
    zeilen_t = {}
    for st, (spalte, kn) in TRACER_STATIONEN.items():
        mess = anker.tracer_anteil(mm[spalte], mm.gas_CHP_T_supply, t_ost, maske=winter)
        t_mod = pd.Series((phi[:, nz.idx[kn], :] * Tq).sum(axis=1), index=f.index)
        mod = anker.tracer_anteil(t_mod, mm.gas_CHP_T_supply, t_ost, lags=(0,), maske=winter)
        zeilen_t[st] = {"Knoten": kn, "Messung": mess["anteil"], "R² Messung": mess["r2"], "Stunden": mess["n"],
                        "Modell (gleiche Regression)": mod["anteil"], "Abweichung [Pp]": 100 * (mod["anteil"] - mess["anteil"]),
                        "Modell Ost-Anteil (Mittel)": float(phi[sel_t, nz.idx[kn], 1:4].sum(axis=1).mean()),
                        "Modell HW1-Anteil (Mittel)": float(phi[sel_t, nz.idx[kn], 4].mean()),
                        "aussagekräftig (R² ≥ 0,3)": mess["r2"] >= 0.3,
                        "erfüllt (±15 Pp)": abs(mod["anteil"] - mess["anteil"]) <= 0.15}
    erg["tracer"] = pd.DataFrame(zeilen_t).T.infer_objects()
    erg["tracer"].to_csv(out / "kriterium_3_5_tracer.csv")

    # Plan-Kriterien: 3.1 Zustand (Hochlast-Holdout, kritische Stationen), 3.2 Hebel (Vorzeichen richtig, Betrag ±30 %
    # bzw. ±0,05 bar), 3.4 Ost-Kopplung (Modellgesetz gegen gemessenes Gesetz im Bereich 2025, ±0,3 bar)
    gh = erg["guete"]["Holdout Hochlast"].loc[["V06", *nm.MITTE_ZIELE]]
    k31 = gh.assign(**{"erfüllt": (gh["RMSE"] <= 0.2) & (gh["Bias"].abs() <= 0.1)})
    d32 = (hs_ - hm_).abs()
    k32 = (np.sign(hs_) == np.sign(hm_)) & ((d32 <= 0.05) | (d32 <= 0.3 * hm_.abs()))
    sel_o = msf.Ost > 50
    gesetz = lambda k: k["c"] + k["d"] * (msf.Ost[sel_o] / 100) ** 2 - k["f"] * (msf.KWK[sel_o] / 100) ** 2  # noqa: E731
    dk = gesetz(kop_mod) - gesetz(kop_mess)
    k34 = pd.Series({"Abweichung P5 [bar]": dk.quantile(0.05), "Abweichung P50 [bar]": dk.median(),
                     "Abweichung P95 [bar]": dk.quantile(0.95), "Anteil Stunden mit Abweichung ≤ 0,3 bar": (dk.abs() <= 0.3).mean()})
    # 3.6 Plausibilitätsanker: Mitte-Verlustgesetz (±0,2 bar) und Süd-Regelgesetz (±0,3 bar) auf Messung und Modell
    # gefittet, verglichen an denselben Stunden. Modell-Süd: KWK-Δp, die V06 im Modell auf dem gemessenen Wert hielte.
    dT = (m.gas_CHP_T_supply - m.gas_CHP_T_return).reindex(f.index)
    P_v = e["verbund"].reindex(f.index)
    dpk = pd.Series(f.dp_kwk, f.index)
    mitte = list(daten.MITTE_STATIONEN)
    fm = {q: anker.fit_verlustgesetz(dpk, z[mitte].min(axis=1), P_v, dT) for q, z in (("Messung", f.ziele), ("Modell", sim))}
    F = P_v / dT
    F_ber = F[(F > 0) & np.isfinite(F)].quantile([0.05, 0.99]).to_numpy()
    F_gitter = np.linspace(*F_ber, 50)
    d_mitte = (fm["Modell"]["a"] - fm["Messung"]["a"]) + (fm["Modell"]["b"] - fm["Messung"]["b"]) * F_gitter**2
    ps1_s = ps1.reindex(f.index)
    kalt8 = ta.reindex(f.index) < 8
    fs = {q: hydraulik.fit_regelgesetz_sued(y, F, msf.HW1, ps1_s, maske=kalt8) for q, y in
          (("Messung", dpk), ("Modell", dpk + f.ziele["V06"] - sim["V06"]))}
    X = pd.concat([F**2, msf.HW1 / 100, ps1_s], axis=1)[kalt8].dropna()
    gs = lambda k: k["a"] + k["b"] * X.iloc[:, 0] - k["g"] * X.iloc[:, 1] - k["h"] * X.iloc[:, 2]  # noqa: E731
    d_sued = gs(fs["Modell"]) - gs(fs["Messung"])
    k36 = pd.DataFrame({"Mitte-Verlustgesetz": {"Abweichung min [bar]": d_mitte.min(), "Abweichung max [bar]": d_mitte.max(),
                                                "Kriterium [bar]": 0.2},
                        "Süd-Regelgesetz": {"Abweichung min [bar]": d_sued.quantile(0.05), "Abweichung max [bar]": d_sued.quantile(0.95),
                                            "Kriterium [bar]": 0.3}}).T
    k36_par = pd.DataFrame({f"Mitte {q}": {k: fm[q][k] for k in ("a", "b", "r2")} for q in fm} |
                           {f"Süd {q}": {k: fs[q][k] for k in ("a", "b", "g", "h", "r2")} for q in fs})
    erg["kriterien"] = {"3.1": k31, "3.2": k32, "3.4": k34, "3.6": k36, "3.6 Parameter": k36_par}
    k31.to_csv(out / "kriterium_3_1.csv")
    k32.to_csv(out / "kriterium_3_2.csv")
    k34.to_csv(out / "kriterium_3_4.csv")
    k36.to_csv(out / "kriterium_3_6.csv")
    k36_par.to_csv(out / "kriterium_3_6_parameter.csv")

    # 5) Auslegungsfall mit dem kalibrierten Modell (Referenz: −14 °C, n−1, West aus eigenen Kesseln), dazu alle gleich
    # guten Kalibriervarianten (Mehrfachstart)
    ae = auslegung_eingaben(m, e, ta, nz)
    bias_v06 = float(erg["guete"].loc["V06", ("Holdout Hochlast", "Bias")])
    erg["auslegung"], hebel_s = auslegung_tabelle(nz, kal, ae, fh, ost_hebel, bias_v06)
    pd.DataFrame({"Hebel [bar je 100 kg/s]": {z: hebel_s(z) for z in ae["mindest"]},
                  "SE": {z: hebel_s(z, 1.0) - hebel_s(z) for z in ae["mindest"]}}).to_csv(out / "hebel_speicher_s_gemessen.csv")
    erg["auslegung"].to_csv(out / "auslegung_netzmodell.csv")
    namen, referenz = kalibriervarianten()
    tab, gue = {}, {}
    for v in namen:
        kal_v = lade_kalibrierung(KALIBRIERUNG_REPO / v, nz)
        tab[v], hebel_v = auslegung_tabelle(nz, kal_v, ae, fh, ost_hebel, bias_v06)
        pd.DataFrame({"Hebel [bar je 100 kg/s]": {z: hebel_v(z) for z in ae["mindest"]},
                      "SE": {z: hebel_v(z, 1.0) - hebel_v(z) for z in ae["mindest"]}}).to_csv(
            out / f"hebel_speicher_s_gemessen_{v}.csv")
        sim_v = nm.simuliere(nz, f.teil(hoch), kal_v["K"], kal_v["versatz"].to_dict(), kal_v["gewichte"], kal_v["grundlast"])
        gue[v] = nm.guete(sim_v, f.ziele[hoch])["RMSE"]
    erg["auslegung_varianten"] = pd.concat(tab, names=["Kalibrierung"])
    erg["auslegung_varianten"].to_csv(out / "auslegung_kalibriervarianten.csv")
    erg["guete_varianten"] = pd.DataFrame(gue)
    erg["guete_varianten"].to_csv(out / "guete_kalibriervarianten.csv")
    erg["referenz"] = referenz
    dTd, dh, gewinn, mindest, hw1_mw = ae["dT"], ae["dh"], ae["gewinn"], ae["mindest"], ae["hw1_mw"]
    ost, ost_2025 = ae["ost"]["Ost Plan A"], ae["ost"]["Ost wie 2025"]
    dm_s = SPEICHER_MW * 1e3 / dh
    erg["auslegung_annahmen"] = {"ΔT [K]": dTd, "Ost Plan A [MW]": ost, "Ost wie 2025 [MW]": ost_2025, "V06-Bias [bar]": bias_v06,
                                 "HW1 [MW]": hw1_mw, "PS1-Gewinn [bar]": float(gewinn[0, nz.kanten_ids.index("L4c")]),
                                 "PS2-Gewinn [bar]": float(gewinn[0, nz.kanten_ids.index("W1")]), "Mindest-Δp": mindest,
                                 "Speicher S [kg/s]": dm_s, "Band gemessener Hebel [kg/s]": BAND_AUSLEGUNG,
                                 "Hebel Speicher S, gemessen [bar je 100 kg/s]": {z: round(hebel_s(z), 3) for z in mindest}}
    _bericht(erg, out)
    return erg


def auslegung_tabelle(nz: nm.Netz, kal: dict, ae: dict, fh: nm.Fall, ost_hebel: dict, bias_v06: float = 0.0):
    """Auslegungsfall für eine Kalibrierung: erforderliche KWK-Δp, Reserven und Speicherwirkung je Ost-Variante und
    Lastfall. ``fh``: Hochlast-Stunden für die strukturellen Hebel; ``ost_hebel``: gemessener Hebel „Ost statt KWK“
    (Station -> (Wert, SE)). Rückgabe: Tabelle und Funktion ``hebel_s(z, k_se)`` (datenverankerter Speicherhebel)."""
    vs, gw, gl, K = kal["versatz"].to_dict(), kal["gewichte"], kal["grundlast"], kal["K"]
    dh, gewinn, mindest, pumpe = ae["dh"], ae["gewinn"], ae["mindest"], ae["pumpe"]
    struk = {k: nm.hebel_modell(nz, fh, K, kn, gw, gl) for k, kn in (("Standort S", "S"), ("Ost (MVA)", "MVA"))}

    def hebel_s(z, k_se=0.0):
        """Gemessener Ost-Hebel (ohne Anstieg mit dem Durchfluss), mit dem Modellverhältnis S/Ost auf den Standort S
        umgerechnet; Stationen ohne eigenes Hebelziel über ihren Knoten."""
        q = next(s for s in nm.HEBEL_ZIELE if nm.STATIONEN.get(s) == nm.STATIONEN[z])
        kn = nm.STATIONEN[z]
        return (ost_hebel[q][0] + k_se * ost_hebel[q][1]) * struk["Standort S"][kn] / struk["Ost (MVA)"][kn]

    def rechne(P, west, ost_v, speicher=None, mind=mindest):
        b = nm.auslegungs_einspeisung(nz, P, dh, ost_v, ae["hw1_mw"], ae["hw1_m"], west, speicher, gw, gl)
        req, need = nm.erforderliche_kwk_dp(nz, K, b, gewinn, mind, vs)
        mfl = nz.loese(b, K, gewinn)
        dpn = nz.dp_knoten(mfl, K, req, gewinn)[0]
        return float(req[0]), need.iloc[0], dpn, mfl[0]

    dm_s = SPEICHER_MW * 1e3 / dh

    def reserve(P, west, ost_v, grenze, speicher=None, gemessener_hebel=False):
        """Lastzuwachs (Faktor − 1), bis die erforderliche KWK-Δp die Grenze erreicht (Bisektion)."""
        def erf(x):
            req, need, *_ = rechne(P * x, west, ost_v, speicher)
            if gemessener_hebel:
                req -= nm.entlastung_aus_hebeln(need, {z: hebel_s(z) for z in need.index}, dm_s)
            return req

        lo, hi = 0.5, 2.5
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            (lo, hi) = (mid, hi) if erf(mid) < grenze else (lo, mid)
        return lo - 1.0

    zeilen = []
    for var, ost_v in ae["ost"].items():
        for name, (P, west) in ae["faelle"].items():
            req, need, dpn, mfl = rechne(P, west, ost_v)
            req10, *_ = rechne(P, west, ost_v, mind={**mindest, "V06": 1.0})
            bind = need.idxmax()
            ent_daten = {k: nm.entlastung_aus_hebeln(need, {z: hebel_s(z, k) for z in need.index}, dm_s) for k in (-2, 0, 2)}
            zeilen.append({"Ost": var, "Fall": name, "P Verbund [MW]": P, "erf. KWK-Δp [bar]": req, "maßgebend": bind,
                           "erf. KWK-Δp, V06-Bias korrigiert [bar]": req + bias_v06 if bind == "V06" else req,
                           "erf. KWK-Δp bei V06 ≥ 1,0 [bar]": req10, "MVA-Δp [bar]": dpn[nz.idx["MVA"]],
                           "KWK-Durchfluss [kg/s]": mfl[nz.kanten_ids.index("KWKi")],
                           "Reserve bis 4,0 bar": reserve(P, west, ost_v, 4.0),
                           "Reserve bis Pumpe": reserve(P, west, ost_v, pumpe),
                           "Entlastung Speicher S, Modell [bar]": req - rechne(P, west, ost_v, {"S": SPEICHER_MW})[0],
                           "Entlastung Speicher S, gemessener Hebel [bar]": ent_daten[0],
                           "Entlastung Speicher S, gemessener Hebel ±2 SE [bar]": f"{ent_daten[-2]:.2f}–{ent_daten[2]:.2f}",
                           "Reserve bis 4,0 bar mit Speicher S, Modell": reserve(P, west, ost_v, 4.0, {"S": SPEICHER_MW}),
                           "Reserve bis 4,0 bar mit Speicher S, gemessener Hebel": reserve(P, west, ost_v, 4.0,
                                                                                            gemessener_hebel=True),
                           "Entlastung Speicher Südende, Modell [bar]": req - rechne(P, west, ost_v, {"SUED_E": SPEICHER_MW})[0],
                           "Reserve bis 4,0 bar mit Speicher Südende, Modell": reserve(P, west, ost_v, 4.0, {"SUED_E": SPEICHER_MW})})
    return pd.DataFrame(zeilen).set_index(["Ost", "Fall"]), hebel_s


def _bericht(erg: dict, out) -> None:
    k = erg["kal"]
    teile = ["# Netzmodell DHN-A – Zusammenfassung (automatisch erzeugt)", "", f"Stunden: {erg['stunden']}", "",
             "## Kalibrierung", f"Lastgewichte: { {g: round(v, 2) for g, v in k['gewichte'].items()} }",
             f"Grundlast [kg/s]: { {g: round(v, 1) for g, v in k['grundlast'].items()} }",
             f"Versatz [bar]: {k['versatz'].round(2).to_dict()}", "", _md(k["multiplikator"].round(2).to_frame("Multiplikator")), "",
             "## Güte", _md(erg["guete"].round(3)), "",
             "## Hebel Holdout-Heizperiode (Differenzenregression, gleiche Stunden; je 100 kg/s bzw. je bar)", _md(erg["hebel"].round(3)), "",
             "## Hebel „Ost statt KWK“ je KWK-Durchflussband (bar je 100 kg/s; West-Übergabe als Regressor)", _md(erg["hebel_band"].round(3)), "",
             "## Strukturelle Hebel im Modell (Δp je 100 kg/s anstelle von KWK-Wasser, KWK-Δp fest)", _md(erg["hebel_struktur"].round(3)), "",
             "## Ost-Kopplung (Δp_MVA − Δp_KWK = c + d·(ṁ_Ost/100)² − f·(ṁ_KWK/100)²)", _md(erg["kopplung"].round(3)), "",
             "## Plan-Kriterien", "3.1 (Hochlast-Holdout, RMSE ≤ 0,2 bar, |Bias| ≤ 0,1 bar)", _md(erg["kriterien"]["3.1"].round(3)), "",
             "3.2 (Hebel Holdout-Heizperiode: Vorzeichen, Betrag ±30 % bzw. ±0,05 bar)", _md(erg["kriterien"]["3.2"]), "",
             "3.4 (Ost-Kopplung, Modellgesetz − gemessenes Gesetz)", _md(erg["kriterien"]["3.4"].round(3).to_frame("Wert")), "",
             "3.5 (Temperatur-Tracer: Ost-Wasseranteil, Winter; Modell mit derselben Regression auf synthetischer Temperatur)",
             _md(erg["tracer"].drop(columns="Knoten").round(2)), "",
             "3.6 (Plausibilitätsanker, Modellgesetz − gemessenes Gesetz; Mitte über den Lastbereich P5–P99, Süd P5–P95 der Stunden)",
             _md(erg["kriterien"]["3.6"].round(3)), "", _md(erg["kriterien"]["3.6 Parameter"].round(4)), "",
             "## Auslegungsfall", f"Annahmen: {erg['auslegung_annahmen']}", "", _md(erg["auslegung"].round(3)), "",
             f"## Kalibriervarianten (Mehrfachstart; Referenz {erg['referenz']})", "RMSE Holdout Hochlast:",
             _md(erg["guete_varianten"].round(3)), "",
             _md(erg["auslegung_varianten"][["erf. KWK-Δp [bar]", "maßgebend", "Reserve bis 4,0 bar", "Reserve bis Pumpe",
                                            "Entlastung Speicher S, Modell [bar]", "Entlastung Speicher S, gemessener Hebel [bar]",
                                            "Reserve bis 4,0 bar mit Speicher S, Modell",
                                            "Reserve bis 4,0 bar mit Speicher S, gemessener Hebel",
                                            "Reserve bis 4,0 bar mit Speicher Südende, Modell"]].round(3))]
    (out / "zusammenfassung.md").write_text("\n".join(teile), encoding="utf-8")


if __name__ == "__main__":
    import sys

    main(neu_kalibrieren="--ohne-kalibrierung" not in sys.argv, von_null="--von-null" in sys.argv)
