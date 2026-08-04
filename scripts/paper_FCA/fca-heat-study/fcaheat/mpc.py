"""Rolling-horizon operation of a fixed design, with forecast error and limited notice.

`notice_override_h` is the contract-design lever: 0.25 = response time only (pessimistic reading
of the German contract), 24 = day-ahead notification (Dutch TDTR), >= horizon = fully known.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pyomo.environ as pyo

from .config import CFG, ECON, OUT_DIR, get_solver
from .data import Inputs
from .fca import build_grid_limit
from .model import Case, cop_series, slice_horizon, solve_with_fallback


def _mpc_window_model(inp, srow, seg, dt, sizes, lim, soc0, cop, c_el, safety):
    """Small LP over one horizon with FIXED sizes and a given starting SOC."""
    T = len(seg)
    m = pyo.ConcreteModel()
    m.T = pyo.RangeSet(0, T - 1)
    for nm in ["pg", "php", "peb", "qu", "pu", "qc", "qd", "sth", "pc", "pd", "sel"]:
        setattr(m, nm, pyo.Var(m.T, domain=pyo.NonNegativeReals))
    eta_eb = float(inp.par("EB", "efficiency"))
    heat = seg["heat"].to_numpy(); elec = seg["el"].to_numpy()
    Etes, Ebes = sizes["Etes"], sizes["Ebes"]
    c_t = float(inp.par("TES", "c_rate_max")); c_b = float(inp.par("BES", "c_rate_max"))
    l_t = float(inp.par("TES", "loss_pct_per_h")); l_b = float(inp.par("BES", "loss_pct_per_h"))
    e_tc = float(inp.par("TES", "eta_charge")); e_td = float(inp.par("TES", "eta_discharge"))
    e_bc = float(inp.par("BES", "eta_charge")); e_bd = float(inp.par("BES", "eta_discharge"))
    s_t = float(inp.par("TES", "soc_min_rel")); s_b = float(inp.par("BES", "soc_min_rel"))

    m.hb = pyo.Constraint(m.T, rule=lambda m, t:
        cop[t] * m.php[t] + eta_eb * m.peb[t] + m.qd[t] - m.qc[t] + m.qu[t] == heat[t])
    m.eb_ = pyo.Constraint(m.T, rule=lambda m, t:
        m.pg[t] + m.pd[t] + m.pu[t] == elec[t] + m.php[t] + m.peb[t] + m.pc[t])
    m.lim = pyo.Constraint(m.T, rule=lambda m, t: m.pg[t] <= float(lim[t]))
    m.hpc = pyo.Constraint(m.T, rule=lambda m, t: cop[t] * m.php[t] <= sizes["Qhp"])
    m.ebc = pyo.Constraint(m.T, rule=lambda m, t: m.peb[t] <= sizes["Peb"])
    m.td = pyo.Constraint(m.T, rule=lambda m, t: m.sth[t] ==
        (1 - l_t * dt) * (soc0["tes"] if t == 0 else m.sth[t - 1])
        + e_tc * m.qc[t] * dt - m.qd[t] * dt / e_td)
    m.bd = pyo.Constraint(m.T, rule=lambda m, t: m.sel[t] ==
        (1 - l_b * dt) * (soc0["bes"] if t == 0 else m.sel[t - 1])
        + e_bc * m.pc[t] * dt - m.pd[t] * dt / e_bd)
    lo_t = (s_t + safety) * Etes if Etes > 0 else 0.0
    lo_b = (s_b + safety) * Ebes if Ebes > 0 else 0.0
    m.tu = pyo.Constraint(m.T, rule=lambda m, t: m.sth[t] <= Etes)
    m.tl = pyo.Constraint(m.T, rule=lambda m, t: m.sth[t] >= min(lo_t, soc0["tes"]))
    m.bu = pyo.Constraint(m.T, rule=lambda m, t: m.sel[t] <= Ebes)
    m.bl = pyo.Constraint(m.T, rule=lambda m, t: m.sel[t] >= min(lo_b, soc0["bes"]))
    m.tpc = pyo.Constraint(m.T, rule=lambda m, t: m.qc[t] <= c_t * Etes)
    m.tpd = pyo.Constraint(m.T, rule=lambda m, t: m.qd[t] <= c_t * Etes)
    m.bpc = pyo.Constraint(m.T, rule=lambda m, t: m.pc[t] <= c_b * Ebes)
    m.bpd = pyo.Constraint(m.T, rule=lambda m, t: m.pd[t] <= c_b * Ebes)
    m.obj = pyo.Objective(expr=sum(m.pg[t] * c_el[t] for t in m.T) * dt
                          + ECON["voll_EUR_per_MWh"] * sum(m.qu[t] + m.pu[t] for t in m.T) * dt,
                          sense=pyo.minimize)
    return m


def run_mpc(inp: Inputs, case: Case, sizes: dict, seed: int = 0, notice_override_h=None,
            verbose: bool = False) -> dict:
    """Rolling-horizon operation of a fixed design.

    `notice_override_h` overrides how far ahead a curtailment call becomes visible to the plant:
    0.25 = response time only (pessimistic reading of the German contract), 24 = day-ahead
    notification (the Dutch TDTR product), >= horizon = fully known ex ante. Passing it explicitly
    is how the notice length is turned into a contract-design variable.
    """
    srow = inp.sites.set_index("site_id").loc[case.site]
    df, dt = slice_horizon(inp, case.site, case.years, case.resolution)
    P_exist = float(srow["P_grid_exist_MW"])
    lim_act, _, restr, frow = build_grid_limit(inp, case.fca, df.index, P_exist,
                                               df["price"].to_numpy(), dt, seed=case.seed)
    cop = cop_series(inp, srow, df.index).to_numpy()
    c_el_act = df["price"].to_numpy() + ECON["grid_energy_price_EUR_per_MWh"] \
        + ECON["electricity_tax_EUR_per_MWh"]

    rng = np.random.default_rng(seed)
    e_d = float(inp.par("MPC", "forecast_err_demand"))
    e_p = float(inp.par("MPC", "forecast_err_price"))
    fc = df.copy()
    fc["heat"] = df["heat"] * (1 + rng.normal(0, e_d, len(df)))
    fc["el"] = df["el"] * (1 + rng.normal(0, e_d, len(df)))
    fc["price"] = df["price"] * (1 + rng.normal(0, e_p, len(df)))
    c_el_fc = fc["price"].to_numpy() + ECON["grid_energy_price_EUR_per_MWh"] \
        + ECON["electricity_tax_EUR_per_MWh"]

    # --- what the plant knows about future restrictions -------------------
    notice_h = float(notice_override_h if notice_override_h is not None
                     else (frow.get("notice_h", 0.0) or 0.0))
    notice = int(round(notice_h / dt))
    lim_fc = lim_act.copy()                       # deterministic regimes: fully known
    if str(frow["type"]).strip().lower() == "dynamic" and notice_h < len(df) * dt:
        lim_fc = np.full(len(df), float(frow["P_flex_rel"]) * P_exist)
        seen = np.zeros(len(df), bool)
        for i in np.where(restr)[0]:
            seen[max(0, i - notice):i + 1] = True
        lim_fc[restr & seen] = lim_act[restr & seen]

    H = int(round(float(inp.par("MPC", "horizon_h")) / dt))
    S = int(round(float(inp.par("MPC", "step_h")) / dt))
    safety = float(inp.par("MPC", "safety_margin_rel"))
    opt = get_solver()
    soc = {"tes": sizes["Etes"] * 0.5, "bes": sizes["Ebes"] * 0.5}
    real = []
    n = len(df)
    for a in range(0, n, S):
        b = min(a + H, n)
        segf = fc.iloc[a:b]
        mf = _mpc_window_model(inp, srow, segf, dt, sizes, lim_fc[a:b], soc,
                               cop[a:b], c_el_fc[a:b], safety)
        try:
            solve_with_fallback(opt, mf)
        except Exception:
            pass
        c = min(a + S, n)
        # re-solve the committed window against reality and the actual limit
        sega = df.iloc[a:c]
        ma = _mpc_window_model(inp, srow, sega, dt, sizes, lim_act[a:c], soc,
                               cop[a:c], c_el_act[a:c], 0.0)
        # anchor the end-of-window SOC to the plan so the horizon still guides the commitment
        try:
            tgt_t = pyo.value(mf.sth[min(S, b - a) - 1]); tgt_b = pyo.value(mf.sel[min(S, b - a) - 1])
            ma.anchor_t = pyo.Constraint(expr=ma.sth[c - a - 1] >= 0.9 * tgt_t)
            ma.anchor_b = pyo.Constraint(expr=ma.sel[c - a - 1] >= 0.9 * tgt_b)
        except Exception:
            pass
        try:
            solve_with_fallback(opt, ma)
        except Exception:
            ma = _mpc_window_model(inp, srow, sega, dt, sizes, lim_act[a:c], soc,
                                   cop[a:c], c_el_act[a:c], 0.0)
            solve_with_fallback(opt, ma)
        k = c - a
        blk = pd.DataFrame(index=sega.index)
        for nm in ["pg", "php", "peb", "qu", "pu", "qc", "qd", "sth", "pc", "pd", "sel"]:
            blk[nm] = [pyo.value(getattr(ma, nm)[t]) for t in range(k)]
        real.append(blk)
        soc = {"tes": float(blk["sth"].iloc[-1]), "bes": float(blk["sel"].iloc[-1])}
        if verbose and (a // S) % 30 == 0:
            print(f"    step {a//S}/{n//S}")
    R = pd.concat(real)
    R["P_limit"] = lim_act[:len(R)]
    R["grid"] = R["pg"]
    yf = len(df) * dt / 8760.0
    return dict(ts=R, kpi=dict(
        site=case.site, scenario=case.scenario, fca=case.fca, mode="mpc", seed=seed,
        notice_h=notice_h,
        unserved_MWh=float(R["qu"].sum() * dt), unserved_el_MWh=float(R["pu"].sum() * dt),
        peak_grid_MW=float(R["pg"].max()),
        violations=int((R["pg"] > R["P_limit"] + 1e-6).sum()),
        cost_energy_EUR=float((R["pg"] * c_el_act[:len(R)]).sum() * dt), years_frac=yf))


def run_mpc_all_sites(inp: Inputs, kpi: pd.DataFrame, scenario="S4_TES_BES",
                      fca="FCA_DYNAMIC", seeds=(0,), notices=(None,), tag="foresight_gap"):
    """Foresight gap for every site, using the sizes from the perfect-foresight run.

    Pass e.g. notices=(0.25, 24.0) to compare response-time-only visibility against day-ahead
    notification with identical hardware — that comparison is a contract-design result, not a
    modelling caveat.
    """
    rows = []
    for s in inp.sites["site_id"]:
        sel = kpi[(kpi["site"] == s) & (kpi["scenario"] == scenario) & (kpi["fca"] == fca)]
        if sel.empty:
            continue
        r = sel.iloc[0]
        sizes = dict(Qhp=r["Qhp_MW"], Peb=r["Peb_MW"], Etes=r["Etes_MWh"], Ebes=r["Ebes_MWh"])
        for nh in notices:
            for sd in seeds:
                out = run_mpc(inp, Case(site=s, scenario=scenario, fca=fca), sizes,
                              seed=sd, notice_override_h=nh)
                k = out["kpi"]
                k["unserved_perfect_MWh"] = r["unserved_MWh"] + r["unserved_el_MWh"]
                k["foresight_gap_MWh"] = (k["unserved_MWh"] + k["unserved_el_MWh"]
                                          - k["unserved_perfect_MWh"])
                rows.append(k)
                print(f"  {s:8s} notice={k['notice_h']:6.2f} h seed {sd}: "
                      f"unserved {k['unserved_MWh']:8.1f} MWh_th, "
                      f"gap {k['foresight_gap_MWh']:8.1f} MWh, violations {k['violations']}")
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / f"mpc_{tag}.csv", index=False)
    return df
