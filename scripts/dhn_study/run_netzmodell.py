"""Netzmodell DHN-A: Kalibrierung an den Messwerten 2025, Validierung (Holdout, Hebel, Ost-Kopplung) und Auslegungsfall.

Aufruf aus der Repository-Wurzel:  ``python -m scripts.dhn_study.run_netzmodell``
Ergebnisse: ``results/dhn_study/netzmodell/`` (CSV, ``zusammenfassung.md``); Abbildungen ``docs/dhn_storage_study/abbildungen/``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import daten, hydraulik
from . import netzmodell as nm
from .run_analyse import T_VL_AUSL, _md

SPEICHER_MW = 40.0
PAAR_GEWICHT = 1.0
HEBEL_GEWICHT = 1.0
MINDEST_MITTE = 1.0


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


def main() -> dict:
    out = daten.repo_root() / "results" / "dhn_study" / "netzmodell"
    out.mkdir(parents=True, exist_ok=True)
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    ta = daten.lade_aussentemperatur()[0].reindex(m.index)
    nz = nm.netz()
    f = nm.randbedingungen(m, e, nz)
    hold, sel = aufteilung(f, ta)
    ft = f.teil(sel)
    erg = {"stunden": {"gesamt": len(f.index), "Kalibrierung": len(sel), "Holdout": int(hold.sum())}}

    # 1) Kalibrierung auf Pegel, stündliche Änderungen und gemessene Hebel (Heizperiode, nur Trainingswochen)
    hreg = nm.hebel_regressoren(m, e, f.index)
    heiz = (ta.reindex(f.index) < 8).to_numpy()
    hebel_train = {"fall": f.teil(~hold & heiz), "reg": hreg[~hold & heiz], "gewicht": HEBEL_GEWICHT}
    kal = nm.kalibriere(nz, ft, gewichtung=np.where(ta.reindex(ft.index).to_numpy() < 5, 3.0, 1.0), paar_gewicht=PAAR_GEWICHT,
                        hebel=hebel_train)
    erg["kal"] = kal
    par = pd.DataFrame({"Multiplikator": kal["multiplikator"], "K [bar/(kg/s)²]": kal["K"],
                        "K_prior": nz.k0}).rename_axis("Kante")
    par.to_csv(out / "kalibrierung_kanten.csv")
    pd.Series({**{f"Gewicht {k}": v for k, v in kal["gewichte"].items()},
               **{f"Grundlast {k} [kg/s]": v for k, v in kal["grundlast"].items()},
               **{f"Versatz {k} [bar]": v for k, v in kal["versatz"].items()}}).to_csv(out / "kalibrierung_last_versatz.csv")

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
    # Strukturelle Hebel im Modell (Störung +10 kg/s anstelle von KWK-Wasser, KWK-Δp fest), Hochlast-Holdout
    fh = f.teil(hoch)
    erg["hebel_struktur"] = pd.DataFrame({k: nm.hebel_modell(nz, fh, kal["K"], kn, gw, gl) for k, kn in
                                          (("Süd (HW1)", "HW1"), ("Ost (MVA)", "MVA"), ("Standort S", "S"), ("Südende", "SUED_E"))})
    erg["hebel_struktur"] = erg["hebel_struktur"].loc[[nm.STATIONEN[s] for s in ["V06", "V03", "V22", "V15"]]]
    erg["hebel_struktur"].index = ["V06", "V03/V10/V24", "V22", "V15"]
    erg["hebel_struktur"].to_csv(out / "hebel_struktur.csv")

    # 4) Ost-Kopplung im Modell gegen Messung (gleiche Regression auf Modellwerten)
    ms = hydraulik.massenstroeme(m, e)
    ps1 = m.pump_station_1_p_supply_after_pump - m.pump_station_1_p_supply_before_pump
    msf = ms.reindex(f.index)
    kop_mess = hydraulik.fit_ost_kopplung(f.ziele["MVA"], pd.Series(f.dp_kwk, f.index), msf.Ost, msf.KWK)
    kop_mod = hydraulik.fit_ost_kopplung(sim["MVA"], pd.Series(f.dp_kwk, f.index), msf.Ost, msf.KWK)
    erg["kopplung"] = pd.DataFrame({"Messung": kop_mess, "Modell": kop_mod}).loc[["c", "d", "f", "r2"]]

    # 5) Auslegungsfall mit dem kalibrierten Modell (Referenz: −14 °C, n−1, West aus eigenen Kesseln)
    anl = daten.lade_anlagen()["plants"]
    dTd = T_VL_AUSL - float(m.gas_CHP_T_return[ta < -5].median())       # gemessener Rücklauf bei Kälte
    dh = float(daten.dh(T_VL_AUSL, T_VL_AUSL - dTd))
    ost = {"MVA": anl["waste_incineration"]["P_max_MW"]["design_minus14C"], "GT": anl["gas_turbine"]["P_max_MW"]["design_minus14C"],
           "BIO": anl["biomass_CHP"]["P_max_MW"]["design_minus14C"]}
    hw1_mw, hw1_m = anl["boiler_plant_1"]["P_max_MW"]["design_minus14C"], anl["boiler_plant_1"]["m_max_t_h"] / 3.6
    kalt = ta < -2
    gewinn = np.zeros((1, len(nz.kanten)))
    gewinn[0, nz.kanten_ids.index("L4c")] = float(ps1.quantile(0.99))
    gewinn[0, nz.kanten_ids.index("W1")] = float((m.pump_station_2_dp_supply_after_pump - m.pump_station_2_dp_supply_before_pump)[kalt].median())
    mindest = {"V06": 1.2, **{s: MINDEST_MITTE for s in nm.MITTE_ZIELE}}
    faelle = {"P50": (235.0, 1.0), "P90": (252.0, 3.7)}       # Verbund-Stundenlast [MW], West-Bezug [MW] (Datenanalyse Abschnitt 6)
    zeilen = []

    def rechne(P, west, speicher=None, mind=mindest):
        b = nm.auslegungs_einspeisung(nz, P, dh, ost, hw1_mw, hw1_m, west, speicher, gw, gl)
        req, need = nm.erforderliche_kwk_dp(nz, kal["K"], b, gewinn, mind, vs)
        mfl = nz.loese(b, kal["K"], gewinn)
        dpn = nz.dp_knoten(mfl, kal["K"], req, gewinn)[0]
        return float(req[0]), need.iloc[0].idxmax(), dpn, b

    for name, (P, west) in faelle.items():
        req, bind, dpn, _ = rechne(P, west)
        req10, *_ = rechne(P, west, mind={"V06": 1.0, **{s: MINDEST_MITTE for s in nm.MITTE_ZIELE}})
        res = {}
        for lab, grenze in (("4,0 bar", 4.0), ("Pumpe", hydraulik.dp_aus_pumpe(anl["gas_CHP"]["pumps"]["head_m"], T_VL_AUSL, anl["gas_CHP"]["dp_internal_bar"]))):
            lo, hi = 0.5, 2.5
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                (lo, hi) = (mid, hi) if rechne(P * mid, west)[0] < grenze else (lo, mid)
            res[lab] = lo - 1.0
        sp_s = rechne(P, west, {"S": SPEICHER_MW})[0]
        sp_e = rechne(P, west, {"SUED_E": SPEICHER_MW})[0]
        zeilen.append({"Fall": name, "P Verbund [MW]": P, "erf. KWK-Δp (V06 ≥ 1,2) [bar]": req, "maßgebend": bind,
                       "erf. KWK-Δp (V06 ≥ 1,0) [bar]": req10, "MVA-Δp [bar]": dpn[nz.idx["MVA"]],
                       "GT-Δp [bar]": dpn[nz.idx["GT"]], "Bio-Δp [bar]": dpn[nz.idx["BIO"]],
                       "Reserve bis 4,0 bar": res["4,0 bar"], "Reserve bis Pumpe": res["Pumpe"],
                       "Entlastung Speicher S [bar]": req - sp_s, "Entlastung Speicher Südende [bar]": req - sp_e,
                       "V06-Bias Hochlast (Modell − Messung) [bar]": erg["guete"].loc["V06", ("Holdout Hochlast", "Bias")]})
    erg["auslegung"] = pd.DataFrame(zeilen).set_index("Fall")
    erg["auslegung"].to_csv(out / "auslegung_netzmodell.csv")
    erg["auslegung_annahmen"] = {"ΔT [K]": dTd, "Ost [MW]": ost, "HW1 [MW]": hw1_mw, "PS1-Gewinn [bar]": float(gewinn[0, nz.kanten_ids.index("L4c")]),
                                 "PS2-Gewinn [bar]": float(gewinn[0, nz.kanten_ids.index("W1")]), "Mindest-Δp": mindest}
    _bericht(erg, out)
    return erg


def _bericht(erg: dict, out) -> None:
    k = erg["kal"]
    teile = ["# Netzmodell DHN-A – Zusammenfassung (automatisch erzeugt)", "", f"Stunden: {erg['stunden']}", "",
             "## Kalibrierung", f"Lastgewichte: { {g: round(v, 2) for g, v in k['gewichte'].items()} }",
             f"Grundlast [kg/s]: { {g: round(v, 1) for g, v in k['grundlast'].items()} }",
             f"Versatz [bar]: {k['versatz'].round(2).to_dict()}", "", _md(k["multiplikator"].round(2).to_frame("Multiplikator")), "",
             "## Güte", _md(erg["guete"].round(3)), "",
             "## Hebel Holdout-Heizperiode (Differenzenregression, gleiche Stunden; je 100 kg/s bzw. je bar)", _md(erg["hebel"].round(3)), "",
             "## Strukturelle Hebel im Modell (Δp je 100 kg/s anstelle von KWK-Wasser, KWK-Δp fest)", _md(erg["hebel_struktur"].round(3)), "",
             "## Ost-Kopplung (Δp_MVA − Δp_KWK = c + d·(ṁ_Ost/100)² − f·(ṁ_KWK/100)²)", _md(erg["kopplung"].round(3)), "",
             "## Auslegungsfall", f"Annahmen: {erg['auslegung_annahmen']}", "", _md(erg["auslegung"].round(3))]
    (out / "zusammenfassung.md").write_text("\n".join(teile), encoding="utf-8")


if __name__ == "__main__":
    main()
