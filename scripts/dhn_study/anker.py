"""Datenbasierte Netzkenngrößen als Plausibilitätsanker und Validierungsziele.

* Verlustgesetz Hauptanlage → ungünstigste Mitte-Station: Δp_Haupt − min Δp_Kunde = a + b·(P/ΔT)²
  (P/ΔT ∝ Massenstrom). Daraus erforderliche Δp der Hauptanlage und Ausbaureserve bis zu einer Δp-Grenze.
* Netzhebel: Regression der stündlichen Differenzen der Kunden-Δp auf Differenzen von Einspeisung,
  Erzeuger-Δp, Last und Pumpengewinn.
* Temperatur-Tracer: Mischungsanteil von Ost-Wasser an einer Station.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def fit_verlustgesetz(dp_haupt: pd.Series, dp_kunde_min: pd.Series, last_mw: pd.Series, dT: pd.Series,
                      dp_kunde_unten: float = 0.3, dT_min: float = 20.0) -> dict:
    x = pd.concat([dp_haupt - dp_kunde_min, last_mw, dT, dp_kunde_min], axis=1, keys=["v", "P", "dT", "k"]).dropna()
    x = x[(x.k > dp_kunde_unten) & (x.dT > dT_min)]
    F = (x.P / x.dT).to_numpy()
    A = np.c_[np.ones(len(x)), F**2]
    c = np.linalg.lstsq(A, x.v.to_numpy(), rcond=None)[0]
    e = x.v.to_numpy() - A @ c
    r2 = 1 - (e**2).sum() / ((x.v - x.v.mean()) ** 2).sum()
    return {"a": float(c[0]), "b": float(c[1]), "r2": float(r2), "n": len(x), "F_max": float(F.max()),
            "residuum_p90": float(np.quantile(np.abs(e), 0.9))}


def erforderliche_dp(fit: dict, P: float, dT: float, dp_min: float = 1.0) -> float:
    """Erforderliche Δp der Hauptanlage [bar], damit die ungünstigste Mitte-Station ``dp_min`` erhält."""
    return dp_min + fit["a"] + fit["b"] * (P / dT) ** 2


def ausbaureserve(fit: dict, P: float, dT: float, dp_grenze: float = 4.0, dp_min: float = 1.0) -> float:
    """Relativer Lastzuwachs, bis die erforderliche Δp der Hauptanlage die Grenze erreicht (negativ: Grenze schon überschritten)."""
    rest = dp_grenze - dp_min - fit["a"]
    if rest <= 0:
        return -1.0
    return float(np.sqrt(rest / fit["b"]) * dT / P - 1.0)


def netzhebel(ziele: dict[str, pd.Series], regressoren: pd.DataFrame, max_sprung: float = 1.0) -> pd.DataFrame:
    """Regression auf stündliche Differenzen: Δy = c0 + Σ c_k·Δx_k. Gibt Koeffizienten und Standardfehler je Ziel."""
    dX = regressoren.diff()
    rows = []
    for name, y in ziele.items():
        z = pd.concat([y.diff().rename("y"), dX], axis=1).dropna()
        z = z[z.y.abs() < max_sprung]
        A = np.c_[np.ones(len(z)), z[regressoren.columns].to_numpy()]
        c = np.linalg.lstsq(A, z.y.to_numpy(), rcond=None)[0]
        e = z.y.to_numpy() - A @ c
        se = np.sqrt(np.diag(np.linalg.inv(A.T @ A)) * e.var())
        row = {"Ziel": name, "n": len(z)}
        for k, col in enumerate(regressoren.columns, start=1):
            row[col] = float(c[k])
            row[f"SE {col}"] = float(se[k])
        rows.append(row)
    return pd.DataFrame(rows)


def tracer_anteil(t_station: pd.Series, t_a: pd.Series, t_b: pd.Series, lags=(0, 1, 2), min_diff: float = 3.0,
                  maske: pd.Series | None = None) -> dict:
    """Anteil der Quelle b am Wasser einer Station: T_s − T_a = α·(T_b − T_a) + c, bestes Lag nach R²."""
    best = None
    for lag in lags:
        x = pd.concat([t_station, t_a.shift(lag), t_b.shift(lag)], axis=1, keys=["s", "a", "b"])
        if maske is not None:
            x = x[maske.reindex(x.index).fillna(False).to_numpy(bool)]
        x = x.dropna()
        x = x[(x.b - x.a).abs() > min_diff]
        if len(x) < 50:
            continue
        A = np.c_[(x.b - x.a).to_numpy(), np.ones(len(x))]
        y = (x.s - x.a).to_numpy()
        c = np.linalg.lstsq(A, y, rcond=None)[0]
        r2 = 1 - ((y - A @ c) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        if best is None or r2 > best["r2"]:
            best = {"lag_h": lag, "anteil": float(c[0]), "verlust_K": float(c[1]), "r2": float(r2), "n": len(x)}
    return best or {"lag_h": np.nan, "anteil": np.nan, "verlust_K": np.nan, "r2": np.nan, "n": 0}
