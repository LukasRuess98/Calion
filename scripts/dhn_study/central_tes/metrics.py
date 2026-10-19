"""Annual metrics, Shapley attribution, break-even values (spec section 8)."""

from __future__ import annotations

from itertools import combinations
from math import factorial

import numpy as np
import pandas as pd

from .milp import HP_MODES, PLANTS


def _ebk_cost(sched: pd.DataFrame, x: pd.DataFrame, cfg: dict) -> float:
    """Cost of the optional electric boiler at the KWK (same price law as in milp.build)."""
    ek = cfg["plants"].get("existing_eb_at_kwk", {})
    if "Q_EBK" not in sched or not ek.get("enabled", False):
        return 0.0
    return float(((x["price"] + ek.get("c_el_var_eur_MWh", 61.6)) / ek["eta"] * sched["Q_EBK"]).sum())


def annual(sched: pd.DataFrame, x: pd.DataFrame, s: pd.DataFrame, cfg: dict, info: dict) -> dict:
    dt = cfg["meta"]["dt_h"]
    eb, tes, hp = cfg["electrode_boiler"], cfg["tes"], cfg["heat_pump"]
    gwh = lambda v: float(np.sum(v) * dt / 1e3)  # noqa: E731
    out: dict = {"cost_total_EUR": info["objective"], "solver": {k: info.get(k) for k in ("status", "bound", "gap", "runtime_s")}}
    out["cost_components_EUR"] = {g: float(sched[f"C_{g}"].sum() * dt) for g in PLANTS} | {
        "HP": float(sched["C_HP"].sum() * dt), "EB_partner_B": float(sched["C_EB"].sum() * dt),
        "NEW_capacity": float(sched["C_NEW_cap"].sum() * dt) if "C_NEW_cap" in sched else 0.0,
        "EB_at_KWK": _ebk_cost(sched, x, cfg) * dt}
    out["new_boiler"] = {"capacity_MW": float(sched["C_new_MW"].iloc[0]) if "C_new_MW" in sched else 0.0,
                         "heat_GWh": float(sched["Q_NEW"].sum() * dt / 1e3) if "Q_NEW" in sched else 0.0,
                         "peak_MW": float(sched["Q_NEW"].max()) if "Q_NEW" in sched else 0.0,
                         "hours": int((sched["Q_NEW"] > 1e-3).sum()) if "Q_NEW" in sched else 0}
    out["heat_GWh"] = {g: gwh(sched[f"Q_{g}"]) for g in PLANTS} | {"demand": gwh(x["D"]), "central_net": gwh(sched["Q_central"]),
                                                                   "central_pos": gwh(sched["Q_central"].clip(lower=0))}
    for c, k in (("Q_tes_ext", "tes_ext_net"), ("Q_EBK", "EB_at_KWK")):        # balance: Σ plants + central + these = demand
        out["heat_GWh"][k] = gwh(sched[c]) if c in sched else 0.0
    # partner A
    avail, used = sched["Q_A_avail"].sum() * dt, sched["Q_src_used"].sum() * dt
    q_route = {md: float(sched[f"Q_HP_{md}"].sum() * dt / 1e3) for md in HP_MODES}
    boost = sched["Q_EB_boost_grid"] + sched["Q_EB_boost_tes"]
    el_hp = sched["P_HP"].sum() * dt
    el_boost = boost.sum() * dt / eb["eta"]
    a_heat = sched["Q_HP"].sum() * dt + boost.sum() * dt
    hp_on = sched["Q_HP"] > 1e-3
    lift_h = {md: int((sched[f"Q_HP_{md}"] > 1e-3)[s[f"lift_flag_{'mid' if md.startswith('casc') else md}"]].sum()) for md in HP_MODES}
    out["partner_A"] = {"available_GWh": float(avail / 1e3), "source_used_GWh": float(used / 1e3),
                        "U": float(used / avail) if avail > 0 else np.nan, "unused_GWh": float((avail - used) / 1e3),
                        "HP_heat_GWh_by_mode": q_route, "HP_heat_GWh": float(sched["Q_HP"].sum() * dt / 1e3),
                        "HP_el_GWh": float(el_hp / 1e3), "HP_full_load_h": float(sched["Q_HP"].sum() * dt / hp["Q_max_MW"]),
                        "chain_efficiency": float(a_heat / (el_hp + el_boost)) if el_hp + el_boost > 0 else np.nan,
                        "cascade_share": float((q_route["casc_grid"] + q_route["casc_tes"]) / max(sum(q_route.values()), 1e-9)),
                        "hours_on": int(hp_on.sum()), "hours_on_lift_above_limit_by_mode": lift_h,
                        "HP_heat_share_lift_above_limit": float(sum(sched.loc[s[f"lift_flag_{'mid' if md.startswith('casc') else md}"], f"Q_HP_{md}"].sum()
                                                                    for md in HP_MODES) / max(sched["Q_HP"].sum(), 1e-9)),
                        "cascade_masked_h": {"grid": int(s["r_grid"].isna().sum()), "tes": int(s["r_tes"].isna().sum())}}
    # partner B
    p = sched["P_EB"]
    pw = float((p * x["price"]).sum() / p.sum()) if p.sum() > 0 else np.nan
    out["partner_B"] = {"heat_GWh": float(p.sum() * dt * eb["eta"] / 1e3), "el_GWh": float(p.sum() * dt / 1e3),
                        "full_load_h": float(p.sum() * dt / eb["P_max_MW"]), "price_weighted_EUR_MWh": pw,
                        "annual_mean_price_EUR_MWh": float(x["price"].mean()), "boost_GWh": float(boost.sum() * dt / 1e3)}
    # TES
    emax_mean = float(s["E_max"].mean())
    out["TES"] = {"external_net_GWh": gwh(sched["Q_tes_ext"]) if "Q_tes_ext" in sched else 0.0,
                  "max_volume_used_m3": float(sched["V_used_m3"].max()) if "V_used_m3" in sched else np.nan,
                  "charge_GWh": gwh(sched["Q_ch"]), "discharge_GWh": gwh(sched["Q_dis"]), "charge_from_grid_GWh": gwh(sched["Q_ch_grid"]),
                  "E_max_mean_MWh": emax_mean, "equivalent_full_cycles": float(sched["Q_dis"].sum() * dt / emax_mean) if emax_mean > 0 else 0.0,
                  "hours_discharge_masked": int((~s["mask_dis"].astype(bool)).sum()),
                  "hours_charge_from_grid_masked": int((~s["mask_ch_grid"].astype(bool)).sum())}
    # dimensionless
    q_max = tes["Q_dis_max_MW"] if tes.get("enabled", True) else np.nan
    dpk = float(x["D"].max())
    design = s["link_cap"].quantile(0.99)
    out["dimensionless"] = {"tau_h": emax_mean / q_max if q_max and q_max > 0 else np.nan,
                            "kappa_link": float(design / dpk), "sigma_A": float(avail / 1e3 / (x["D"].sum() * dt / 1e3)),
                            "psi_central": float(sched["Q_central"].clip(lower=0).sum() / x["D"].sum())}
    # CO2 (secondary): fuel emissions of the plants + grid electricity of HP and EB − CHP electricity at the grid factor
    ef = x["ef_grid"].fillna(x["ef_grid"].mean()) / 1e3
    pc = lambda g: cfg["plants"][g] if g != "NEW" else cfg["new_boiler"]  # noqa: E731
    fuel = sum(sched[f"Q_{g}"] / pc(g)["eta_th"] * cfg["fuels"][pc(g)["fuel"]]["ef"] / 1e3 for g in PLANTS)
    chp_el = sum(sched[f"Q_{g}"] * pc(g).get("eta_el", 0.0) / pc(g)["eta_th"] for g in PLANTS)
    p_ebk = sched["Q_EBK"] / cfg["plants"].get("existing_eb_at_kwk", {}).get("eta", 1.0) if "Q_EBK" in sched else 0.0
    grid = (sched["P_HP"] + sched["P_EB"] + p_ebk) * ef
    out["CO2_t"] = {"fuel": float(fuel.sum() * dt), "grid_electricity": float(grid.sum() * dt),
                    "chp_power_credit": float(-(chp_el * ef).sum() * dt),
                    "net": float((fuel + grid - chp_el * ef).sum() * dt)}
    return out


def hydraulic_summary(ev: pd.DataFrame, flows_ref: np.ndarray | None, nz, cfg: dict) -> dict:
    v = ev["violation"]
    out = {"violating_hours": int(v.sum()), "by_limit": ev.loc[v, "violated_limit"].value_counts().to_dict(),
           "attributable_to_central_h": int(ev.get("attributable", pd.Series(False, index=ev.index)).sum()),
           "max_violation_bar": float(ev["violation_bar"].max()),
           "dp_KWK_required": {"p50": float(ev["dp_KWK"].median()), "p95": float(ev["dp_KWK"].quantile(0.95)), "max": float(ev["dp_KWK"].max())},
           "soft_hours": {k: int(ev[f"soft_{k}"].sum()) for k in ("KWK", "MVA", "GT", "BIO")},
           "binding_station_share": ev["bind"].value_counts(normalize=True).round(4).to_dict(),
           "min_saturation_margin_bar": float(ev["sat_margin_bar"].min()),
           "min_return_pressure_bar": {g: float(np.nanmin(ev[f"p_ret_{g}"])) for g in ("MVA", "GT", "BIO", "HW1")},
           "pump_el_MWh": {c[7:]: float(ev[c].sum()) for c in ev if c.startswith("P_pump_")}}
    d = cfg["link"]["DN_inner_m"][int(cfg["link"]["DN"])]
    vel = np.abs(ev["m_central"] if "m_central" in ev else ev["m_S"]) / 960.0 / (np.pi * d**2 / 4)   # link flow only
    out["max_link_velocity_m_s"] = float(vel.max())
    if flows_ref is not None and "flows" in ev.attrs:
        from .hydraulics import flow_reversals
        rev = flow_reversals(nz, ev.attrs["flows"], flows_ref)
        out["flow_reversals_vs_F000_h"] = {k: int(n) for k, n in rev.items() if n > 0}
    return out


# ------------------------------------------------------------------------------------------------- Shapley
PLAYERS = ("A", "B", "TES")


def code_of(subset: frozenset) -> str:
    return "F" + "".join("1" if p in subset else "0" for p in PLAYERS)


def shapley(costs: dict[str, float]) -> dict:
    """costs: {'F000': C, ..., 'F111': C}. v(S) = C(F000) − C(S)."""
    v = {frozenset(c for c, b in zip(PLAYERS, code[1:]) if b == "1"): costs["F000"] - costs[code] for code in costs}
    n = len(PLAYERS)
    phi = {}
    for i in PLAYERS:
        others = [p for p in PLAYERS if p != i]
        tot = 0.0
        for k in range(n):
            for S in combinations(others, k):
                S = frozenset(S)
                w = factorial(len(S)) * factorial(n - len(S) - 1) / factorial(n)
                tot += w * (v[S | {i}] - v[S])
        phi[i] = tot
    full = frozenset(PLAYERS)
    inter = v[full] - v[frozenset({"A", "B"})] - v[frozenset({"TES"})]
    storage_value = {"F001-F000": v[frozenset({"TES"})], "F101-F100": v[frozenset({"A", "TES"})] - v[frozenset({"A"})],
                     "F011-F010": v[frozenset({"B", "TES"})] - v[frozenset({"B"})], "F111-F110": v[full] - v[frozenset({"A", "B"})]}
    return {"v": {code_of(S): val for S, val in v.items()}, "phi": phi, "sum_phi": sum(phi.values()), "v_full": v[full],
            "tes_interaction": inter, "storage_value": storage_value}


def annuity_factor(i: float, n: int) -> float:
    return i * (1 + i) ** n / ((1 + i) ** n - 1)
