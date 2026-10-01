"""Auslegungslast aus der Beziehung Tageslast ↔ Außentemperatur.

Lineare und quadratische Regression der Tagesmittelleistung auf das Tagesmittel der Außentemperatur
(bzw. das trägheitsgewichtete ``ta_eff``) unterhalb der Heizgrenze, mit Wochenend-Term. Ergebnis als
Band (P50 = Regression, P90 = + 1,28 σ der Tagesresiduen) bei der Auslegungstemperatur.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

Z90 = 1.2816


def fit_last_temperatur(p_tag: pd.Series, t_tag: pd.Series, t_grenze: float = 12.0, quadratisch: bool = False) -> dict:
    x = pd.concat([p_tag, t_tag], axis=1, keys=["P", "T"]).dropna()
    x = x[x["T"] < t_grenze]
    we = (x.index.dayofweek >= 5).astype(float)
    spalten = [np.ones(len(x)), x["T"].to_numpy(), we]
    if quadratisch:
        spalten.append(x["T"].to_numpy() ** 2)
    A = np.column_stack(spalten)
    c = np.linalg.lstsq(A, x["P"].to_numpy(), rcond=None)[0]
    e = x["P"].to_numpy() - A @ c
    return {"koeff": c, "sigma": float(e.std()), "n": len(x), "quadratisch": quadratisch,
            "residuum_kalt": float(e[x["T"].to_numpy() < -3].mean()) if (x["T"] < -3).any() else np.nan}


def last_bei(fit: dict, t: float, wochenende: bool = False) -> tuple[float, float]:
    """(P50, P90) der Tagesmittelleistung bei Außentemperatur ``t``."""
    c = fit["koeff"]
    p = c[0] + c[1] * t + c[2] * float(wochenende) + (c[3] * t * t if fit["quadratisch"] else 0.0)
    return float(p), float(p + Z90 * fit["sigma"])


def auslegungsband(reihen: dict[str, pd.Series], t_tag: pd.Series, t_ausl: float = -14.0, t_eff: pd.Series | None = None) -> pd.DataFrame:
    """Tabelle der Auslegungs-Tagesleistung je Datenreihe und Modellvariante."""
    rows = []
    for name, p in reihen.items():
        pt = p.resample("D").mean()
        for tlab, T in (("Ta", t_tag), ("Ta_eff", t_eff)):
            if T is None:
                continue
            for quad in (False, True):
                f = fit_last_temperatur(pt, T, quadratisch=quad)
                p50, p90 = last_bei(f, t_ausl)
                rows.append({"Reihe": name, "Temperatur": tlab, "Modell": "quadratisch" if quad else "linear", "n Tage": f["n"],
                             "Steigung [MW/K]": f["koeff"][1], "σ [MW]": f["sigma"], "Residuum kalte Tage [MW]": f["residuum_kalt"],
                             f"P50 bei {t_ausl:g} °C [MW]": p50, f"P90 bei {t_ausl:g} °C [MW]": p90})
    return pd.DataFrame(rows)


def spitzenfaktor(p_h: pd.Series, t_tag: pd.Series, t_max: float = 0.0) -> dict[str, float]:
    """Verhältnis Stundenmaximum / Tagesmittel an Tagen mit Tagesmittel unter ``t_max``."""
    x = pd.concat([p_h.resample("D").mean(), p_h.resample("D").max(), t_tag], axis=1, keys=["m", "x", "T"]).dropna()
    r = (x.x / x.m)[x["T"] < t_max]
    return {"n": len(r), "median": float(r.median()), "p90": float(r.quantile(0.9))}


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
