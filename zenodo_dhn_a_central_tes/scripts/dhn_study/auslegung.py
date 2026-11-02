"""Auslegungslast aus der Beziehung Tageslast ↔ Außentemperatur.

Lineare und quadratische Regression der Tagesmittelleistung auf das Tagesmittel der Außentemperatur
(bzw. das trägheitsgewichtete ``ta_eff``) unterhalb der Heizgrenze, mit Wochenend-Term. Ergebnis als
Band (P50 = Regression, P90 = + 1,28 σ der Tagesresiduen) bei der Auslegungstemperatur.

An Kältetagen ist die Lieferung 2021, 2022 und 2025 hydraulisch begrenzt (Last unter der Geraden, auch ohne
Ferienzeit). Der unbegrenzte Bedarf wird deshalb zusätzlich nur auf milden Tagen (≥ 0 °C) angepasst.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

Z90 = 1.2816


def ferienzeit(idx: pd.DatetimeIndex) -> np.ndarray:
    """Weihnachts-/Neujahrszeit 23.12.–06.01. (Gewerbe ruht, Lastniveau verschoben)."""
    md = idx.month * 100 + idx.day
    return ((md >= 1223) | (md <= 106)).astype(float)


def fit_last_temperatur(p_tag: pd.Series, t_tag: pd.Series, t_grenze: float = 12.0, quadratisch: bool = False,
                        t_min: float | None = None, ferien: bool = False) -> dict:
    """Regression Tagesleistung ~ 1 + T + Wochenende [+ T²] [+ Ferienzeit].

    ``t_min``: nur Tage ab dieser Temperatur anpassen (z. B. 0 °C), um hydraulisch begrenzte Kältetage auszuschließen;
    das Ergebnis ist dann der **unbegrenzte** Bedarf. ``residuum_kalt`` ist immer über alle Tage < −3 °C gebildet
    (ohne Ferienzeit, falls ``ferien``).
    """
    x = pd.concat([p_tag, t_tag], axis=1, keys=["P", "T"]).dropna()
    x = x[x["T"] < t_grenze]
    T = x["T"].to_numpy()
    spalten = [np.ones(len(x)), T, (x.index.dayofweek >= 5).astype(float)]
    if quadratisch:
        spalten.append(T**2)
    if ferien:
        spalten.append(ferienzeit(x.index))
    A = np.column_stack(spalten)
    fit_maske = T >= t_min if t_min is not None else np.ones(len(x), bool)
    c = np.linalg.lstsq(A[fit_maske], x["P"].to_numpy()[fit_maske], rcond=None)[0]
    e = x["P"].to_numpy() - A @ c
    kalt = (T < -3) & ((A[:, -1] == 0) if ferien else True)
    return {"koeff": c, "sigma": float(e[fit_maske].std()), "n": int(fit_maske.sum()), "quadratisch": quadratisch,
            "ferien": ferien, "t_min": t_min, "residuum_kalt": float(e[kalt].mean()) if kalt.any() else np.nan}


def last_bei(fit: dict, t: float, wochenende: bool = False) -> tuple[float, float]:
    """(P50, P90) der Tagesmittelleistung bei Außentemperatur ``t`` (Werktag außerhalb der Ferienzeit)."""
    c = fit["koeff"]
    p = c[0] + c[1] * t + c[2] * float(wochenende) + (c[3] * t * t if fit["quadratisch"] else 0.0)
    return float(p), float(p + Z90 * fit["sigma"])


def ungedeckte_last(p_tag: pd.Series, t_tag: pd.Series, fit: dict, klassen=(-20, -8, -5, -2)) -> pd.DataFrame:
    """Gemessene minus unbegrenzt erwartete Tagesleistung an kalten Werktagen außerhalb der Ferienzeit, je Temperaturklasse.

    Negativ heißt: weniger geliefert als der Bedarf nach dem auf milde Tage angepassten Modell (``fit`` mit ``t_min``).
    """
    x = pd.concat([p_tag, t_tag], axis=1, keys=["P", "T"]).dropna()
    x = x[(x.index.dayofweek < 5) & (ferienzeit(x.index) == 0)]
    x["erwartet"] = [last_bei(fit, t)[0] for t in x["T"]]
    x["diff"] = x.P - x.erwartet
    g = pd.cut(x["T"], list(klassen))
    out = x.groupby(g, observed=True).agg(Tage=("diff", "size"), Differenz_MW=("diff", "mean"), Erwartet_MW=("erwartet", "mean"))
    out["Differenz [%]"] = 100 * out.Differenz_MW / out.Erwartet_MW
    out.index = out.index.astype(str)
    return out


MODELLE = {"linear": {"quadratisch": False}, "quadratisch": {"quadratisch": True},
           "linear unbegrenzt (Fit ≥ 0 °C)": {"t_min": 0.0, "ferien": True}}


def auslegungsband(reihen: dict[str, pd.Series], t_tag: pd.Series, t_ausl: float = -14.0, t_eff: pd.Series | None = None) -> pd.DataFrame:
    """Tabelle der Auslegungs-Tagesleistung je Datenreihe und Modellvariante.

    ``quadratisch`` bildet die heutige (an Kältetagen begrenzte) Lieferung ab, ``linear unbegrenzt`` den Bedarf ohne
    hydraulische Begrenzung; ``linear`` (alle Tage < 12 °C) liegt dazwischen.
    """
    rows = []
    for name, p in reihen.items():
        pt = p.resample("D").mean()
        for tlab, T in (("Ta", t_tag), ("Ta_eff", t_eff)):
            if T is None:
                continue
            for modell, kw in MODELLE.items():
                f = fit_last_temperatur(pt, T, **kw)
                p50, p90 = last_bei(f, t_ausl)
                rows.append({"Reihe": name, "Temperatur": tlab, "Modell": modell, "n Tage": f["n"],
                             "Steigung [MW/K]": f["koeff"][1], "σ [MW]": f["sigma"], "Residuum kalte Tage [MW]": f["residuum_kalt"],
                             f"P50 bei {t_ausl:g} °C [MW]": p50, f"P90 bei {t_ausl:g} °C [MW]": p90})
    return pd.DataFrame(rows)


def spitzenfaktor(p_h: pd.Series, t_tag: pd.Series, t_max: float = 0.0) -> dict[str, float]:
    """Verhältnis Stundenmaximum / Tagesmittel an Tagen mit Tagesmittel unter ``t_max``."""
    x = pd.concat([p_h.resample("D").mean(), p_h.resample("D").max(), t_tag], axis=1, keys=["m", "x", "T"]).dropna()
    r = (x.x / x.m)[x["T"] < t_max]
    return {"n": len(r), "median": float(r.median()), "p90": float(r.quantile(0.9))}


def verbundlast_west_eigen(p_ohne_west: float, p_west: float, kessel_west_mw: float, spitzenfaktor: float) -> float:
    """Verbund-Tagesmittel [MW], wenn das Sekundärnetz West aus seinen Kesseln versorgt wird (Fahrweise Plan A bei −14 °C).

    Bezug aus dem Verbund nur für den Teil der West-Stundenspitze, der die Kesselleistung übersteigt; zurückgerechnet
    auf ein Tagesmittel, damit es mit dem Spitzenfaktor wieder die Stundenlast ergibt.
    """
    bezug_stunde = max(0.0, spitzenfaktor * p_west - kessel_west_mw)
    return p_ohne_west + bezug_stunde / spitzenfaktor


def tagesprofile(p_h: pd.Series, t_tag: pd.Series, t_max: float = -2.0) -> np.ndarray:
    """Normierte 24-h-Profile (Stunde / Tagesmittel) aller vollständigen Werktage mit Tagesmittel unter ``t_max``."""
    d = p_h.resample("D").mean()
    t = t_tag.reindex(d.index)
    tage = d.index[(t < t_max) & (d.index.dayofweek < 5) & (ferienzeit(d.index) == 0)]
    profile = [p_h[str(tg.date())].to_numpy(float) / d[tg] for tg in tage]
    return np.array([x for x in profile if len(x) == 24 and np.isfinite(x).all()])


def ueberschuss(profile: np.ndarray, p_mittel: float, leistung: float) -> dict[str, float]:
    """Leistung und Energie oberhalb der verfügbaren Erzeugungsleistung, wenn ein Tag mit Mittel ``p_mittel`` [MW]
    die gemessenen Kältetagsprofile hat. Median und P90 über die Profile (Spitzendeckung, z. B. durch einen Speicher)."""
    ex = np.clip(profile * p_mittel - leistung, 0.0, None)
    e, h, mx = ex.sum(axis=1), (ex > 0).sum(axis=1), ex.max(axis=1)
    return {"Profile": len(profile), "Energie Median [MWh]": float(np.median(e)), "Energie P90 [MWh]": float(np.quantile(e, 0.9)),
            "Stunden Median": float(np.median(h)), "Leistung Median [MW]": float(np.median(mx)), "Leistung P90 [MW]": float(np.quantile(mx, 0.9))}


def pruefe_ausrichtung(werte: np.ndarray, jahr: int, t_tag: pd.Series) -> dict[str, float]:
    """Korrelation Tageslast ↔ Ta für zwei Lesarten eines Jahres-Lastgangs (fortlaufend gegen ohne 29.02.)."""
    werte = np.asarray(werte, float)
    fortl = pd.Series(werte, index=pd.date_range(f"{jahr}-01-01", periods=len(werte), freq="h"))
    idx = pd.date_range(f"{jahr}-01-01", f"{jahr}-12-31 23:00", freq="h")
    idx = idx[~((idx.month == 2) & (idx.day == 29))][: len(werte)]
    ohne = pd.Series(werte[: len(idx)], index=idx)
    out = {}
    for name, s in (("fortlaufend", fortl), ("ohne 29.02.", ohne)):
        x = pd.concat([s.resample("D").mean(), t_tag], axis=1, keys=["P", "T"]).dropna()
        out[name] = float(x.P.corr(x["T"]))
    return out
