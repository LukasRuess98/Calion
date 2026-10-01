"""Hydraulische Begrenzung bei Kälte: Kopplung der Erzeuger, Schlechtpunktregelung Süd und Grenzband der Hauptanlage.

Befund 2025 (siehe ``docs/dhn_storage_study/Datenanalyse_Auslegung.md``, Abschnitte 5 und 6):

* Der Süd-Schlechtpunkt wird auf ≈ 1,2 bar geregelt. Die KWK-Δp folgt dieser Regelung (``fit_regelgesetz_sued``).
* Die Ost-Erzeuger speisen gegen die KWK-Δp: Δp_MVA − Δp_KWK = c + d·(ṁ_Ost/100)² − f·(ṁ_KWK/100)²
  (``fit_ost_kopplung``). Jede zusätzliche bar KWK-Δp hebt die MVA-Δp um ≈ 1 bar; an deren Pumpengrenze (7,5 bar)
  ist die KWK-Δp deshalb nicht frei erhöhbar.
* Die 4,0 bar am KWK-Austritt sind ein Planwert; als Band werden Planwert, gemessenes Maximum und die aus der
  Pumpenförderhöhe ableitbare Δp geführt (``dp_aus_pumpe``).

Alle Gesetze sind Ersatzmodelle aus dem Betriebsbereich 2025. Außerhalb davon (``extrapolation``) sind sie nur
Anhaltswerte, die das Netzmodell bestätigen muss.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import daten

G = 9.81


def dp_aus_pumpe(foerderhoehe_m: float, t_c: float, dp_intern_bar: float) -> float:
    """Austritts-Δp [bar] aus Förderhöhe bei Mediumtemperatur ``t_c`` abzüglich anlageninterner Verluste."""
    return float(daten.rho_w(t_c) * G * foerderhoehe_m / 1e5 - dp_intern_bar)


def massenstrom(q_mw, t_vl, t_rl):
    """Massenstrom [kg/s] aus Wärmeleistung und Spreizung."""
    return np.asarray(q_mw, float) * 1e3 / daten.dh(t_vl, t_rl)


def massenstroeme(m: pd.DataFrame, e: pd.DataFrame) -> pd.DataFrame:
    """Massenströme [kg/s] der Erzeuger: MVA (aus Wärme/Δh), GT (Durchfluss, sonst aus Wärme), Bio (m³/h im VL), KWK, HW1."""
    mva = pd.Series(massenstrom(m.waste_incineration_heat, m.waste_incineration_T_supply, m.waste_incineration_T_return), index=m.index)
    gt_q = pd.Series(massenstrom(e["gas_turbine"], m.gas_turbine_T_supply, m.gas_turbine_T_return), index=m.index)
    gt = (m.gas_turbine_flow / 3.6).fillna(gt_q).where(e["gas_turbine"] > 0, 0.0)
    bio = m.biomass_CHP_flow * daten.rho_w(m.biomass_CHP_T_supply) / 3600
    out = pd.DataFrame({"MVA": mva, "GT": gt, "Bio": bio}, index=m.index)
    out["Ost"] = out[["MVA", "GT", "Bio"]].sum(axis=1, min_count=3)
    out["KWK"] = m.gas_CHP_flow_total_out / 3.6
    out["HW1"] = (m.boiler_plant_1_flow / 3.6).fillna(0.0)
    return out


def _lstsq(y: np.ndarray, A: np.ndarray) -> tuple[np.ndarray, float, float]:
    c = np.linalg.lstsq(A, y, rcond=None)[0]
    e = y - A @ c
    return c, float(1 - (e**2).sum() / ((y - y.mean()) ** 2).sum()), float(np.quantile(np.abs(e), 0.9))


def fit_ost_kopplung(dp_ost: pd.Series, dp_kwk: pd.Series, m_ost: pd.Series, m_kwk: pd.Series, m_ost_min: float = 50.0) -> dict:
    """Δp_Ost − Δp_KWK = c + d·(ṁ_Ost/100)² − f·(ṁ_KWK/100)²  (ṁ in kg/s, Δp in bar).

    ``d`` beschreibt den Transportverlust Ost → Verbund, ``f`` den Verlust der KWK bis zum Treffpunkt der Ströme.
    """
    x = pd.concat([dp_ost - dp_kwk, m_ost / 100, m_kwk / 100], axis=1, keys=["d", "o", "k"]).replace([np.inf, -np.inf], np.nan).dropna()
    x = x[x.o > m_ost_min / 100]
    c, r2, r90 = _lstsq(x.d.to_numpy(), np.c_[np.ones(len(x)), x.o**2, x.k**2])
    return {"c": float(c[0]), "d": float(c[1]), "f": float(-c[2]), "r2": r2, "residuum_p90": r90, "n": len(x),
            "m_ost_p99": float(x.o.quantile(0.99) * 100), "m_kwk_p99": float(x.k.quantile(0.99) * 100)}


def ost_dp(fit: dict, dp_kwk: float, m_ost: float, m_kwk: float) -> float:
    """Δp der Ost-Hauptanlage (MVA) [bar] bei gegebener KWK-Δp und Massenströmen [kg/s]."""
    return dp_kwk + fit["c"] + fit["d"] * (m_ost / 100) ** 2 - fit["f"] * (m_kwk / 100) ** 2


def kwk_grenze_ost(fit: dict, m_ost: float, m_kwk: float, dp_ost_max: float = 7.5, konservativ: bool = True) -> float:
    """Größte KWK-Δp [bar], bei der die Ost-Hauptanlage ihre Austritts-Δp-Grenze ``dp_ost_max`` noch einhält.

    ``konservativ``: Die Entlastung durch den KWK-Massenstrom wird nicht über das P99 der Messungen hinaus
    extrapoliert (sie wächst physikalisch mit ṁ_KWK, ist aber nur im Messbereich belegt).
    """
    m_k = min(m_kwk, fit["m_kwk_p99"]) if konservativ else m_kwk
    return dp_ost_max - fit["c"] - fit["d"] * (m_ost / 100) ** 2 + fit["f"] * (m_k / 100) ** 2


def m_ost_max(fit: dict, dp_kwk: float, m_kwk: float, dp_ost_max: float = 7.5) -> float:
    """Größter Ost-Massenstrom [kg/s], den die Ost-Pumpen bei gegebener KWK-Δp noch einspeisen können."""
    rest = dp_ost_max - dp_kwk - fit["c"] + fit["f"] * (m_kwk / 100) ** 2
    return float(100 * np.sqrt(rest / fit["d"])) if rest > 0 else 0.0


def fit_regelgesetz_sued(dp_kwk: pd.Series, F: pd.Series, m_hw1: pd.Series, ps1_gewinn: pd.Series,
                         maske: pd.Series | None = None) -> dict:
    """Empirisches Regelgesetz der Schlechtpunktregelung Süd: Δp_KWK = a + b·F² − g·ṁ_HW1/100 − h·Δp_PS1.

    F = P/ΔT [MW/K] ∝ Verbund-Massenstrom. ``g`` und ``h`` sind die Entlastung der KWK durch die lokale
    Süd-Einspeisung (HW1) und die Pumpstation PS1.
    """
    x = pd.concat([dp_kwk, F, m_hw1 / 100, ps1_gewinn], axis=1, keys=["y", "F", "h", "p"]).replace([np.inf, -np.inf], np.nan).dropna()
    if maske is not None:
        x = x[maske.reindex(x.index).fillna(False).to_numpy(bool)]
    x = x[(x.F > 0.5) & (x.y > 0.5)]
    c, r2, r90 = _lstsq(x.y.to_numpy(), np.c_[np.ones(len(x)), x.F**2, x.h, x.p])
    return {"a": float(c[0]), "b": float(c[1]), "g": float(-c[2]), "h": float(-c[3]), "r2": r2, "residuum_p90": r90,
            "n": len(x), "F_p99": float(x.F.quantile(0.99))}


def erforderliche_dp_sued(fit: dict, P: float, dT: float, m_hw1: float, ps1_gewinn: float) -> float:
    """KWK-Δp [bar], die die heutige Schlechtpunktregelung Süd bei Last P, Spreizung dT, HW1-Massenstrom [kg/s] und PS1 einstellt."""
    return fit["a"] + fit["b"] * (P / dT) ** 2 - fit["g"] * m_hw1 / 100 - fit["h"] * ps1_gewinn


def ausbaureserve(fit_mitte: dict, fit_sued: dict, P: float, dT: float, dp_grenze: float, m_hw1: float, ps1_gewinn: float,
                  dp_min_mitte: float = 1.0) -> dict[str, float]:
    """Relativer Lastzuwachs, bis die nach Mitte- bzw. Süd-Gesetz erforderliche KWK-Δp die Grenze erreicht.

    ``Mitte``: Verlustgesetz ``anker.fit_verlustgesetz``; ``Süd``: ``fit_regelgesetz_sued`` mit gegebener HW1- und
    PS1-Unterstützung; ``gesamt`` = Minimum. Negativ: Grenze schon überschritten.
    """
    def _res(rest, b):
        return float(np.sqrt(rest / b) * dT / P - 1.0) if rest > 0 else -1.0
    mitte = _res(dp_grenze - dp_min_mitte - fit_mitte["a"], fit_mitte["b"])
    sued = _res(dp_grenze - fit_sued["a"] + fit_sued["g"] * m_hw1 / 100 + fit_sued["h"] * ps1_gewinn, fit_sued["b"])
    return {"Mitte": mitte, "Süd": sued, "gesamt": min(mitte, sued)}


def aktive_grenzen(x: pd.DataFrame, ta: pd.Series, klassen=(-15, -2, 2, 8, 30),
                   ost_grenze: float = 7.5, kwk_grenze: float = 4.0, sued_min: float = 1.1) -> pd.DataFrame:
    """Anteil der Stunden je Außentemperaturklasse, in denen eine Grenze erreicht oder fast erreicht ist.

    ``x`` braucht die Spalten ``dp_ost`` (max. Ost-Δp), ``dp_kwk``, ``dp_sued`` (min. Süd-Δp), ``dp_mitte`` und
    ``gt_an`` (bool).
    """
    k = x.assign(Ta=ta.reindex(x.index)).dropna(subset=["Ta"])
    g = pd.cut(k.Ta, list(klassen))
    out = pd.DataFrame({
        "Stunden": k.groupby(g, observed=True).size(),
        f"Ost-Δp ≥ {ost_grenze - 0.5:g} bar [%]": 100 * (k.dp_ost >= ost_grenze - 0.5).groupby(g, observed=True).mean(),
        f"Ost-Δp ≥ {ost_grenze:g} bar [%]": 100 * (k.dp_ost >= ost_grenze).groupby(g, observed=True).mean(),
        f"KWK-Δp ≥ {kwk_grenze - 0.5:g} bar [%]": 100 * (k.dp_kwk >= kwk_grenze - 0.5).groupby(g, observed=True).mean(),
        f"Süd ≤ {sued_min:g} bar [%]": 100 * (k.dp_sued <= sued_min).groupby(g, observed=True).mean(),
        "Mitte ≤ 1,2 bar [%]": 100 * (k.dp_mitte <= 1.2).groupby(g, observed=True).mean(),
        "GT in Betrieb [%]": 100 * k.gt_an.astype(float).groupby(g, observed=True).mean(),
        "Ost-Δp P95 [bar]": k.dp_ost.groupby(g, observed=True).quantile(0.95),
        "KWK-Δp P95 [bar]": k.dp_kwk.groupby(g, observed=True).quantile(0.95),
        "Süd-Δp Median [bar]": k.dp_sued.groupby(g, observed=True).median(),
    })
    out.index = out.index.astype(str)
    return out
