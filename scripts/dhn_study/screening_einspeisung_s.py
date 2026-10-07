"""Screening: hydraulische Wirkung einer zusätzlichen Einspeisung am Standort S (Betriebsjahr 2025).

Frage: Erzeugt eine Einspeisung am Standort S (Speicher, Wärmepumpe, Elektrodenkessel) im heutigen Lastbereich
überhaupt hydraulische Grenzverletzungen, und wo? Das entscheidet, ob ein Vergleich „Energie-Optimum gegen hydraulisch
zulässiges Optimum“ im Betriebsjahr 2025 etwas zeigt.

Ansatz (kalibriertes Ersatznetz, alle drei Kalibriervarianten, alle Stunden mit vollständigen Randbedingungen):
* Am Knoten S wird zusätzlich P MW eingespeist (P < 0: Entnahme, z. B. Speicherladung aus dem Netz). Massenstrom aus
  P und der gemessenen KWK-Spreizung der Stunde.
* Die KWK ist Druckhalter und Ausgleich (Wurzel): Sie liefert den Rest und regelt ihre Δp wie im Betrieb so, dass der
  Regelpunkt V06 seinen Sollwert und die Mitte ihr Mindest-Δp hält (``erforderliche_kwk_dp``).
* Eine Einspeisung darf den KWK-Durchfluss höchstens bis ``KWK_MIN_KG_S`` verdrängen (die KWK-Pumpen können nicht
  rückwärts fördern); begrenzte Stunden werden gezählt.
* Erzeuger-Δp der Ost-Anlagen: gemessener Wert plus Modelländerung gegenüber P = 0 (robust gegen den Modellbias).
* Fließrichtung je Kante und Mischgrenze KWK-/Ost-Wasser entlang L5 (Mischungsrechnung mit S als eigener Quelle).

Aufruf: ``python -m scripts.dhn_study.screening_einspeisung_s``. Ergebnisse: ``results/dhn_study/screening/``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import daten
from . import netzmodell as nm
from .run_netzmodell import KALIBRIERUNG_REPO, MINDEST_MITTE, kalibriervarianten, lade_kalibrierung

LEISTUNGEN_MW = (-20.0, -10.0, 0.0, 10.0, 20.0, 40.0)
V06_SOLL_BAR = 1.2
KWK_MIN_KG_S = 10.0
KWK_GRENZEN_BAR = {"Erfahrungswert 4,0 bar": 4.0, "Pumpe ≈ 5,7 bar": 5.7}
OST_GRENZE_BAR = 7.5                     # Erfahrungswert laut Plan A (MVA, GT, Bio-KWK)
OST_ERZEUGER = ("MVA", "GT", "BIO")
L5_KETTE = ("SS", "K1", "S", "L5M", "K2", "L5O")   # von der KWK-Sammelschiene nach Osten
HEIZPERIODE = (1, 2, 3, 4, 10, 11, 12)


def einspeisung_s(b0: np.ndarray, kwk0: np.ndarray, dm: np.ndarray, nz: nm.Netz) -> tuple[np.ndarray, np.ndarray]:
    """Einspeisevektoren mit zusätzlichem Massenstrom ``dm`` [kg/s] an S; positive Einspeisung höchstens bis zum
    KWK-Mindestdurchfluss. Rückgabe: Einspeisungen und Maske der begrenzten Stunden."""
    grenze = np.maximum(kwk0 - KWK_MIN_KG_S, 0.0)
    dm_eff = np.where(dm > 0, np.minimum(dm, grenze), dm)
    b = b0.copy()
    b[:, nz.idx["S"]] += dm_eff
    return b, (dm > 0) & (dm > grenze + 1e-9)


def mischgrenze(anteil_kwk: np.ndarray, nz: nm.Netz) -> np.ndarray:
    """Erster Knoten entlang ``L5_KETTE``, an dem der KWK-Anteil unter 50 % fällt (Index in der Kette; Länge der Kette,
    wenn bis L5O überwiegend KWK-Wasser fließt)."""
    a = np.stack([anteil_kwk[:, nz.idx[k]] for k in L5_KETTE], axis=1)
    unter = a < 0.5
    return np.where(unter.any(axis=1), unter.argmax(axis=1), len(L5_KETTE))


def main() -> dict[str, pd.DataFrame]:
    out = daten.repo_root() / "results" / "dhn_study" / "screening"
    out.mkdir(parents=True, exist_ok=True)
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    nz = nm.netz()
    f = nm.randbedingungen(m, e, nz)
    t_vl = m.gas_CHP_T_supply.reindex(f.index).interpolate(limit_direction="both")
    t_rl = m.gas_CHP_T_return.reindex(f.index).interpolate(limit_direction="both")
    mf = 1e3 / np.asarray(daten.dh(t_vl, t_rl))                       # kg/s je MW
    mindest = {"V06": V06_SOLL_BAR, **{z: MINDEST_MITTE for z in nm.MITTE_ZIELE}}
    heiz = f.index.month.isin(HEIZPERIODE)
    i_kwk = nz.kanten_ids.index("KWKi")
    quellen = [*nm.QUELLEN, "S"]
    gemessen = {q: f.ziele[q].to_numpy() for q in OST_ERZEUGER}

    zeilen, kanten_wechsel, verlauf = [], {}, {}
    for v in kalibriervarianten()[0]:
        kal = lade_kalibrierung(KALIBRIERUNG_REPO / v, nz)
        K, vs = kal["K"], kal["versatz"].to_dict()
        b0 = f.b(nz, kal["gewichte"], kal["grundlast"])
        kwk0 = nz.loese(b0, K, f.gewinn)[:, i_kwk]
        basis = {}
        for P in sorted(LEISTUNGEN_MW, key=lambda p: (p != 0.0, p)):     # P = 0 zuerst (Bezug)
            b, begrenzt = einspeisung_s(b0, kwk0, P * mf, nz)
            req, need = nm.erforderliche_kwk_dp(nz, K, b, f.gewinn, mindest, vs)
            ms = nz.loese(b, K, f.gewinn)
            dp = nz.dp_knoten(ms, K, req, f.gewinn)
            anteile = nm.quellanteile(nz, ms, b, quellen=quellen)
            r = {"req": req, "bind": need.idxmax(axis=1).to_numpy(), "m": ms,
                 "grenze_l5": mischgrenze(anteile[:, :, 0], nz),
                 "s_anteil": anteile[:, :, quellen.index("S")],
                 **{q: dp[:, nz.idx[q]] for q in OST_ERZEUGER}}
            if P == 0.0:
                basis = r
            for zeitraum, sel in (("Jahr", np.ones(len(req), bool)), ("Heizperiode", heiz), ("Sommer", ~heiz)):
                z = {"Kalibrierung": v, "P [MW]": P, "Zeitraum": zeitraum, "Stunden": int(sel.sum()),
                     "Einspeisung begrenzt [h]": int(begrenzt[sel].sum()),
                     "KWK-Δp erf. Median [bar]": float(np.median(req[sel])),
                     "Δ KWK-Δp gegen P=0, Mittel [bar]": float(np.mean(req[sel] - basis["req"][sel])),
                     "Δ KWK-Δp gegen P=0, P5 [bar]": float(np.quantile(req[sel] - basis["req"][sel], 0.05)),
                     "Δ KWK-Δp gegen P=0, P95 [bar]": float(np.quantile(req[sel] - basis["req"][sel], 0.95)),
                     "V06 maßgebend [Anteil]": float(np.mean(r["bind"][sel] == "V06"))}
                for name, g in KWK_GRENZEN_BAR.items():
                    z[f"KWK-Δp erf. > {name} [h]"] = int((req[sel] > g).sum())
                for q in OST_ERZEUGER:
                    d = r[q][sel] - basis[q][sel]
                    neu = gemessen[q][sel] + d
                    ok = np.isfinite(neu)
                    z[f"Δ {q}-Δp Mittel [bar]"] = float(np.mean(d))
                    z[f"Δ {q}-Δp P95 [bar]"] = float(np.quantile(d, 0.95))
                    z[f"{q}-Δp > 7,5 bar [h]"] = int((neu[ok] > OST_GRENZE_BAR).sum())
                z["Mischgrenze L5 Median [Knoten]"] = L5_KETTE[min(int(np.median(r["grenze_l5"][sel])), len(L5_KETTE) - 1)] \
                    if np.median(r["grenze_l5"][sel]) < len(L5_KETTE) else "östlich L5O"
                z["Mischgrenze verschoben [h]"] = int((r["grenze_l5"][sel] != basis["grenze_l5"][sel]).sum())
                z["Wasser aus S erreicht K2 (≥ 10 %) [h]"] = int((r["s_anteil"][sel, nz.idx["K2"]] >= 0.1).sum())
                zeilen.append(z)
            if P != 0.0:
                wechsel = (np.sign(np.round(ms, 0)) != np.sign(np.round(basis["m"], 0))) & (np.abs(ms - basis["m"]) > 1.0)
                kanten_wechsel[(v, P)] = pd.Series(wechsel.sum(axis=0), index=nz.kanten_ids)
            if v == kalibriervarianten()[1]:
                verlauf[P] = pd.DataFrame({"KWK-Δp erf. [bar]": req, **{f"{q}-Δp Modell [bar]": r[q] for q in OST_ERZEUGER},
                                           "Mischgrenze L5 [Index]": r["grenze_l5"],
                                           "Einspeisung begrenzt": begrenzt}, index=f.index)

    erg = {"zusammenfassung": pd.DataFrame(zeilen),
           "richtungswechsel": pd.DataFrame(kanten_wechsel).T.rename_axis(["Kalibrierung", "P [MW]"])}
    erg["zusammenfassung"].to_csv(out / "screening_zusammenfassung.csv", index=False)
    erg["richtungswechsel"].to_csv(out / "screening_richtungswechsel.csv")
    pd.concat(verlauf, names=["P [MW]"]).to_parquet(out / "screening_stunden_referenz.parquet")
    gemessen_df = pd.DataFrame(gemessen, index=f.index)
    erg["gemessen"] = pd.DataFrame({q: {"Stunden mit Messwert": int(gemessen_df[q].notna().sum()),
                                         "> 7,5 bar gemessen [h]": int((gemessen_df[q] > OST_GRENZE_BAR).sum()),
                                         "Max gemessen [bar]": float(gemessen_df[q].max())} for q in OST_ERZEUGER}).T
    erg["gemessen"].to_csv(out / "screening_ost_gemessen.csv")
    return erg


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    e = main()
    print(e["gemessen"])
    print(e["zusammenfassung"].round(3).to_string())
    print(e["richtungswechsel"].loc[:, lambda d: d.max() > 0])
