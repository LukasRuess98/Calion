"""Exogenous COP time series (Carnot fraction), TES set temperature, cascade ratios and lift flags."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import daten

K0 = 273.15


def cop_carnot_fraction(t_sink_c, t_source_c, eta_c: float, dt_app: float, cop_max: float) -> np.ndarray:
    """COP = min(COP_max, η_C · (T_sink + ΔT_app) / ((T_sink + ΔT_app) − (T_source − ΔT_app))), temperatures in K."""
    ts = np.asarray(t_sink_c, float) + K0 + dt_app
    tq = np.asarray(t_source_c, float) + K0 - dt_app
    with np.errstate(divide="ignore", invalid="ignore"):
        c = eta_c * ts / np.maximum(ts - tq, 1e-6)
    return np.minimum(cop_max, np.maximum(c, 1.0))


def tes_set_temperature(t_vl: pd.Series, strategy: str, t_fixed: float) -> pd.Series:
    if strategy == "fixed":
        return pd.Series(t_fixed, index=t_vl.index)
    if strategy == "monthly":
        return t_vl.groupby(t_vl.index.month).transform("max")
    if strategy == "daily":
        return t_vl.groupby(t_vl.index.date).transform("max")
    raise ValueError(strategy)


def tes_capacity_mwh(volume_m3: float, t_set: pd.Series, t_low: float) -> pd.Series:
    """E_max,t = ρ V c_p (T_set − T_low) [MWh] with ρ, c_p at the mean temperature."""
    tm = 0.5 * (t_set + t_low)
    return volume_m3 * daten.rho_w(tm) * daten.cp_w(tm) * np.maximum(t_set - t_low, 0.0) / 3600.0 / 1e3


def series(x: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """All temperature-dependent parameters per hour."""
    hp, tes = cfg["heat_pump"], cfg["tes"]
    classes = tes.get("model") == "classes"
    t_set = (pd.Series(float(max(tes["classes_C"])), index=x.index) if classes      # class model: HP/EB charge the top class
             else tes_set_temperature(x["T_VL"], tes["T_set_strategy"], tes["T_fixed_C"]))
    t_low = float(tes["T_low_C"])
    t_mid = float(hp["cascade"]["T_mid_C"])
    f = lambda ts: cop_carnot_fraction(ts, x["T_source"], hp["eta_carnot"], hp["dT_app_K"], hp["cop_max"])  # noqa: E731
    out = pd.DataFrame(index=x.index)
    out["T_set"] = t_set
    out["E_max"] = tes_capacity_mwh(tes["volume_m3"], t_set, t_low) if tes.get("enabled", True) else 0.0
    if classes and tes.get("enabled", True):          # temperature classes: masks are replaced by per-class rules
        out["E_max"] = tes_capacity_mwh(tes["volume_m3"], pd.Series(max(tes["classes_C"]), index=x.index), t_low)
    out["COP_grid"] = f(x["T_VL"])
    out["COP_tes"] = f(t_set)
    out["COP_mid"] = f(pd.Series(t_mid, index=x.index))
    # cascade boost ratios r = (T_target − T_mid) / (T_mid − T_in); allowed only if T_target > T_mid > T_in
    r_g = (x["T_VL"] - t_mid) / (t_mid - x["T_RL"])
    r_t = (t_set - t_mid) / (t_mid - t_low)
    out["r_grid"] = r_g.where((x["T_VL"] > t_mid) & (t_mid > x["T_RL"]), np.nan)
    out["r_tes"] = r_t.where((t_set > t_mid) & (t_mid > t_low), np.nan)
    lim = hp["lift_limit_single_stage_K"]
    out["lift_grid"] = x["T_VL"] - x["T_source"]
    out["lift_tes"] = t_set - x["T_source"]
    out["lift_mid"] = t_mid - x["T_source"]
    for k in ("grid", "tes", "mid"):
        out[f"lift_flag_{k}"] = out[f"lift_{k}"] > lim
    # temperature masks of the single-state TES
    out["mask_dis"] = t_set >= x["T_VL"]                                   # discharge to network allowed
    out["mask_ch_grid"] = x["T_VL"] >= t_set - tes["dT_tol_K"]             # charging from the network allowed
    if not classes and not tes.get("temperature_masks", True):   # energy-only storage (no temperature feasibility)
        out["mask_dis"] = pd.Series(True, index=x.index)
        out["mask_ch_grid"] = pd.Series(True, index=x.index)
    if classes:     # report: discharge possible from the top class; network charging possible into the lowest class
        out["mask_dis"] = max(tes["classes_C"]) >= x["T_VL"]
        out["mask_ch_grid"] = x["T_VL"] >= min(tes["classes_C"]) - tes["dT_tol_K"]
    # link capacity [MW]
    lk = cfg["link"]
    d = lk["DN_inner_m"][int(lk["DN"])]
    m_max = daten.rho_w(x["T_VL"]) * lk["v_max_m_s"] * np.pi * d**2 / 4          # kg/s (supply side)
    out["link_cap"] = m_max * daten.dh(x["T_VL"], x["T_RL"]) / 1e3
    out["m_link_max"] = m_max
    return out
