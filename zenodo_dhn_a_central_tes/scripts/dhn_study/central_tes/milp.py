"""Energy-layer MILP (operator perspective), Pyomo model solved with HiGHS.

Spec sections 4.2–4.7: HP of partner A with direct modes (grid, TES) and HP→EB cascade (grid, TES) with exogenous COPs,
mode exclusivity per hour (binary); electrode boiler of partner B under a heat-purchase contract; TES as temperature
classes sharing one volume (reference, D10) or as a single state with temperature strategy and masks (spec variant),
charge/discharge exclusivity (binary); explicit central feed-in Q_central with link capacity; optional TES at another
node (Q_tes_ext), optional electric boiler at the KWK (Q_EBK) and optional new south boiler with its capacity as a
decision; heat balance Σ plants + Q_central + Q_tes_ext + Q_EBK = measured network feed-in (losses embedded, see docs).
Cost minimisation without artificial penalties; the only capital cost is the annualised new-boiler capacity
(expansion study); the partner-A waste-heat fee π_A·Q_src is an operating cost.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pyomo.environ as pyo

EXISTING = ["KWK", "MVA", "GT", "BIO", "HW1"]
PLANTS = EXISTING + ["NEW"]          # NEW: new peak boiler in the expansion area (capacity is a decision, see new_boiler)
HP_MODES = ["grid", "tes", "casc_grid", "casc_tes"]


@dataclass
class Flags:
    A: bool       # partner A + HP
    B: bool       # partner B electrode boiler
    TES: bool

    @property
    def link(self) -> bool:
        return self.A or self.B or self.TES


def plant_bounds(x: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hourly (lower, upper) bounds per plant: nominal capacity, revealed availability (monthly P95 of the measured
    output) and must-run (lower bound min(cap, demand))."""
    lo, hi = {}, {}
    if all(f"hi_{g}" in x for g in PLANTS):            # precomputed on the full year (rolling horizon windows)
        return (pd.DataFrame({g: x[f"lo_{g}"] for g in PLANTS}, index=x.index),
                pd.DataFrame({g: x[f"hi_{g}"] for g in PLANTS}, index=x.index))
    nb = cfg.get("new_boiler", {})
    lo["NEW"] = pd.Series(0.0, index=x.index)
    hi["NEW"] = pd.Series(float(nb.get("cap_max_MW", 500.0)) if nb.get("enabled") else 0.0, index=x.index)
    if unserved_mode(cfg):
        hi["NEW"] = x["D_extra"] if "D_extra" in x else 0.0 * hi["NEW"]
    for g in EXISTING:
        p = cfg["plants"][g]
        cap = pd.Series(float(p["cap_MW"]), index=x.index)
        if p.get("availability") == "monthly_p95_measured":
            q = x[f"Q_meas_{g}"]
            cap = np.minimum(cap, q.groupby(q.index.month).transform(lambda s: s.quantile(0.95)).fillna(cap))
        mm = cfg["plants"].get("m_max_kg_s", {}).get(g)
        if mm:
            cap = np.minimum(cap, mm * x["dh"] / 1e3)
        hi[g] = cap
        lo[g] = np.minimum(cap, x["D"]) if p.get("must_run") else 0.0 * cap
    return pd.DataFrame(lo, index=x.index)[PLANTS], pd.DataFrame(hi, index=x.index)[PLANTS]


def plant_costs(x: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Marginal heat cost per plant [EUR/MWh_th]: (fuel + CO2)/η_th − η_el/η_th · λ (CHP power credit)."""
    out = {}
    for g in PLANTS:
        p = cfg["plants"][g] if g != "NEW" else cfg["new_boiler"]
        if g == "NEW" and unserved_mode(cfg):          # hosting capacity: NEW = heat not delivered to new customers
            out[g] = pd.Series(float(p.get("unserved_penalty_eur_MWh", 1000.0)), index=x.index)
            continue
        fu = cfg["fuels"][p["fuel"]]
        fuel = (fu["price"] + p.get("energy_tax_eur_MWh", 0.0) + fu["ef"] / 1e3 * cfg["co2_price_eur_t"]) / p["eta_th"]
        credit = p.get("eta_el", 0.0) / p["eta_th"] * x["price"] if cfg.get("chp_power_credit") == "day_ahead" else 0.0
        out[g] = fuel - credit
    return pd.DataFrame(out, index=x.index)


def unserved_mode(cfg: dict) -> bool:
    """Hosting-capacity mode: the NEW variable is unserved heat of the new south customers (no investment, penalty
    cost, ≤ D_extra, withdrawn from the south nodes like the new load) instead of a new boiler."""
    nb = cfg.get("new_boiler", {})
    return bool(nb.get("enabled")) and nb.get("mode", "boiler") == "unserved"


def new_boiler_annual_cost_per_MW(cfg: dict) -> float:
    """Annualised capital + fixed O&M cost of the new peak boiler [EUR/(MW·a)]."""
    nb = cfg["new_boiler"]
    i, n = cfg["economics"]["discount_rate"], nb["lifetime_a"]
    return nb["capex_eur_per_MW"] * i * (1 + i) ** n / ((1 + i) ** n - 1) + nb["om_fix_eur_per_MW_a"]


def tes_colocated(cfg: dict) -> bool:
    return cfg["tes"].get("node", "S") == "S"


def class_density(cfg: dict) -> np.ndarray:
    """Energy density [MWh/m³] of each temperature class above T_low."""
    from .. import daten
    tes = cfg["tes"]
    tb = np.asarray(tes["classes_C"], float)
    tl = float(tes["T_low_C"])
    tm = 0.5 * (tb + tl)
    return daten.rho_w(tm) * daten.cp_w(tm) * (tb - tl) / 3600.0 / 1e3


def eb_heat_price(x: pd.DataFrame, cfg: dict) -> pd.Series:
    eb = cfg["electrode_boiler"]
    c_el = eb["c_el_var_eur_MWh"][eb["c_el_var_case"]]
    return (x["price"] + c_el) / eb["eta"] + eb["premium_eur_MWh"]


def build(x: pd.DataFrame, s: pd.DataFrame, cfg: dict, fl: Flags, bounds: pd.DataFrame | None = None,
          e0=None, cyclic: bool | None = None, cuts: list | None = None,
          e_end_top: float | None = None, end_value=None, end_target=None,
          end_penalty: float = 1000.0) -> pyo.ConcreteModel:
    """``x`` inputs, ``s`` temperature-dependent series (``cop.series``); ``bounds``: columns lo/hi for Q_central (Mode H);
    ``e0``: fixed initial SOC [MWh] (rolling horizon; scalar = top class, or one value per temperature class), otherwise
    cyclic E_T = E_0. ``e_end_top``: optional minimum top-class energy at the window end (not used in the reported runs: the RH tank
    starts empty instead, see rolling.py). ``end_value``: terminal value of the stored energy at the window end [EUR/MWh],
    one value per temperature class (class model) or a scalar (single state); subtracted from the objective (RH
    variant). ``end_target``: soft minimum energy per class at the window end (RH guide-curve variant), shortfall
    penalised with ``end_penalty`` [EUR/MWh]."""
    T = len(x)
    H = range(T)
    dt = cfg["meta"]["dt_h"]
    cost = plant_costs(x, cfg)
    lam = x["price"].to_numpy()
    D = x["D"].to_numpy()
    hp, eb, tes = cfg["heat_pump"], cfg["electrode_boiler"], cfg["tes"]
    m = pyo.ConcreteModel()
    m.H = pyo.RangeSet(0, T - 1)
    plo, phi = plant_bounds(x, cfg)
    plo_a, phi_a = {g: plo[g].to_numpy() for g in PLANTS}, {g: phi[g].to_numpy() for g in PLANTS}
    m.Q = pyo.Var(PLANTS, m.H, bounds=lambda _m, g, t: (float(plo_a[g][t]), float(phi_a[g][t])))
    central_terms = {t: [] for t in H}
    obj = [sum(float(cost[g].iat[t]) * m.Q[g, t] for g in PLANTS for t in H) * dt]

    # ---------------- partner A heat pump
    modes = []
    tes_at_s = fl.TES and tes_colocated(cfg)
    if fl.A:
        modes = ["grid", "tes"] if tes_at_s else ["grid"]
        if hp["cascade"]["enabled"] and fl.B:
            modes += ["casc_grid"] + (["casc_tes"] if tes_at_s else [])
        cop = {"grid": s["COP_grid"].to_numpy(), "tes": s["COP_tes"].to_numpy(),
               "casc_grid": s["COP_mid"].to_numpy(), "casc_tes": s["COP_mid"].to_numpy()}
        r = {"casc_grid": s["r_grid"].to_numpy(), "casc_tes": s["r_tes"].to_numpy()}
        qmax = hp["Q_max_MW"]
        m.M = pyo.Set(initialize=modes)
        m.Qhp = pyo.Var(m.M, m.H, bounds=(0.0, qmax))
        m.z = pyo.Var(m.M, m.H, domain=pyo.Binary)
        for md in modes:          # cascade masks: no cascade where r is undefined
            if md in r:
                for t in H:
                    if not np.isfinite(r[md][t]):
                        m.Qhp[md, t].fix(0.0)
                        m.z[md, t].fix(0)
        avail = x["Q_A_avail"].to_numpy()
        m.src = pyo.Constraint(m.H, rule=lambda _m, t: sum(_m.Qhp[md, t] * (1 - 1 / cop[md][t]) for md in modes) <= float(avail[t]))
        m.hpcap = pyo.Constraint(m.H, rule=lambda _m, t: sum(_m.Qhp[md, t] for md in modes) <= qmax)
        m.hpz = pyo.Constraint(m.M, m.H, rule=lambda _m, md, t: _m.Qhp[md, t] <= qmax * _m.z[md, t])
        m.hpx = pyo.Constraint(m.H, rule=lambda _m, t: sum(_m.z[md, t] for md in modes) <= 1)
        c_hp = lam + hp["c_el_var_eur_MWh"]
        obj.append(sum(float(c_hp[t] / cop[md][t]) * m.Qhp[md, t] for md in modes for t in H) * dt)
        if hp["pi_source_eur_MWh"]:
            obj.append(sum(hp["pi_source_eur_MWh"] * (1 - 1 / cop[md][t]) * m.Qhp[md, t] for md in modes for t in H) * dt)
        for t in H:
            if "grid" in modes:
                central_terms[t].append(m.Qhp["grid", t])
            if "casc_grid" in modes:
                rr = r["casc_grid"][t]
                if np.isfinite(rr):
                    central_terms[t].append((1 + rr) * m.Qhp["casc_grid", t])

    # ---------------- partner B electrode boiler
    if fl.B:
        pmax = eb["P_max_MW"]
        m.Peb = pyo.Var(m.H, bounds=(0.0, pmax))
        m.Qeb_grid = pyo.Var(m.H, bounds=(0.0, None))
        m.Qeb_tes = pyo.Var(m.H, bounds=(0.0, None))
        if not tes_at_s:
            for t in H:
                m.Qeb_tes[t].fix(0.0)

        def _boost(t):
            b = 0
            if fl.A and "casc_grid" in modes and np.isfinite(r["casc_grid"][t]):
                b = b + r["casc_grid"][t] * m.Qhp["casc_grid", t]
            if fl.A and "casc_tes" in modes and np.isfinite(r["casc_tes"][t]):
                b = b + r["casc_tes"][t] * m.Qhp["casc_tes", t]
            return b
        m.ebbal = pyo.Constraint(m.H, rule=lambda _m, t: _m.Qeb_grid[t] + _m.Qeb_tes[t] + _boost(t) == eb["eta"] * _m.Peb[t])
        c_upm = eb_heat_price(x, cfg).to_numpy()
        # heat price applies to all heat delivered by the boiler (direct + boost) = η·P
        obj.append(sum(float(c_upm[t] * eb["eta"]) * m.Peb[t] for t in H) * dt)
        if eb["demand_charge"] == "full":
            m.Ppeak = pyo.Var(bounds=(0.0, pmax))
            m.peak = pyo.Constraint(m.H, rule=lambda _m, t: _m.Ppeak >= _m.Peb[t])
            obj.append(eb["demand_charge_eur_per_MW_a"] * T * dt / 8760.0 * m.Ppeak)
        for t in H:
            central_terms[t].append(m.Qeb_grid[t])

    # ---------------- TES
    tx_terms = {t: [] for t in H}                    # TES at a node other than S: own injection Q_tes_ext
    if fl.TES:
        model = tes.get("model", "single")
        lo_l = tes["loss_per_h"]
        mdis, mchg = s["mask_dis"].to_numpy(), s["mask_ch_grid"].to_numpy()

        def _qsrc(_m, t):                            # charging by the co-located sources (top class / T_set)
            q = 0
            if fl.A and "tes" in modes:
                q = q + _m.Qhp["tes", t]
            if fl.A and "casc_tes" in modes and np.isfinite(r["casc_tes"][t]):
                q = q + (1 + r["casc_tes"][t]) * _m.Qhp["casc_tes", t]
            if fl.B and tes_at_s:
                q = q + _m.Qeb_tes[t]
            return q
        if model == "classes":
            tb = np.asarray(tes["classes_C"], float)
            dens = class_density(cfg)
            K = range(len(tb))
            top = len(tb) - 1
            tvl = x["T_VL"].to_numpy()
            vol = float(tes["volume_m3"]) if tes.get("enabled", True) else 0.0
            m.Kc = pyo.RangeSet(0, len(tb) - 1)
            m.Eb = pyo.Var(m.Kc, pyo.RangeSet(0, T), bounds=lambda _m, k, t: (0.0, float(vol * dens[k])))
            m.chb = pyo.Var(m.Kc, m.H, bounds=(0.0, tes["Q_ch_max_MW"]))
            m.disb = pyo.Var(m.Kc, m.H, bounds=(0.0, tes["Q_dis_max_MW"]))
            for k in K:
                for t in H:
                    if tvl[t] < tb[k] - tes["dT_tol_K"]:      # network water too cold for class k
                        m.chb[k, t].fix(0.0)
                    if tb[k] < tvl[t]:                        # class k too cold for the network
                        m.disb[k, t].fix(0.0)
            m.vol = pyo.Constraint(pyo.RangeSet(0, T), rule=lambda _m, t: sum(_m.Eb[k, t] / float(dens[k]) for k in K) <= vol)
            m.socb = pyo.Constraint(m.Kc, m.H, rule=lambda _m, k, t: _m.Eb[k, t + 1] == _m.Eb[k, t] * (1 - lo_l * dt)
                                    + (_m.chb[k, t] + (_qsrc(_m, t) if k == top else 0) - _m.disb[k, t]) * dt)
            m.Qdis = pyo.Expression(m.H, rule=lambda _m, t: sum(_m.disb[k, t] for k in K))
            m.Qch_grid = pyo.Expression(m.H, rule=lambda _m, t: sum(_m.chb[k, t] for k in K))
            m.E = pyo.Expression(pyo.RangeSet(0, T), rule=lambda _m, t: sum(_m.Eb[k, t] for k in K))
            if e0 is not None:                        # rolling horizon: scalar (all in the top class) or per class
                e0k = np.asarray(e0, float).ravel()
                for k in K:
                    ek0 = float(e0k[k]) if e0k.size == len(tb) else (float(e0k[0]) if k == top else 0.0)
                    m.Eb[k, 0].fix(min(max(ek0, 0.0), float(vol * dens[k])))      # clip float round-off
                if e_end_top is not None:             # last RH window: hand back at least the initial top-class energy
                    m.endb = pyo.Constraint(expr=m.Eb[top, T] >= float(e_end_top))
            elif (tes.get("cyclic", True) if cyclic is None else cyclic):
                m.cycb = pyo.Constraint(m.Kc, rule=lambda _m, k: _m.Eb[k, T] == _m.Eb[k, 0])
            if end_value is not None:                 # RH terminal value per class
                ev = np.broadcast_to(np.asarray(end_value, float), (len(tb),))
                obj.append(-sum(float(ev[k]) * m.Eb[k, T] for k in K))
            if end_target is not None:                # RH soft guide curve per class
                et = np.broadcast_to(np.asarray(end_target, float), (len(tb),))
                m.endsl = pyo.Var(m.Kc, bounds=(0.0, None))
                m.endg = pyo.Constraint(m.Kc, rule=lambda _m, k: _m.Eb[k, T] + _m.endsl[k] >= float(min(et[k], vol * dens[k])))
                obj.append(end_penalty * sum(m.endsl[k] for k in K))
        else:
            emax = s["E_max"].to_numpy()
            m.E = pyo.Var(pyo.RangeSet(0, T), bounds=lambda _m, t: (0.0, float(emax[min(t, T - 1)])))
            m.Qdis = pyo.Var(m.H, bounds=(0.0, tes["Q_dis_max_MW"]))
            m.Qch_grid = pyo.Var(m.H, bounds=(0.0, tes["Q_ch_max_MW"]))
            for t in H:
                if not mdis[t]:
                    m.Qdis[t].fix(0.0)
                if not mchg[t]:
                    m.Qch_grid[t].fix(0.0)
            m.soc = pyo.Constraint(m.H, rule=lambda _m, t: _m.E[t + 1] == _m.E[t] * (1 - lo_l * dt)
                                   + (_m.Qch_grid[t] + _qsrc(_m, t) - _m.Qdis[t]) * dt)
            cyc = tes.get("cyclic", True) if cyclic is None else cyclic
            if e0 is not None:
                m.E[0].fix(min(float(e0), float(emax[0])))
            if cyc and e0 is None:
                m.cyc = pyo.Constraint(expr=m.E[T] == m.E[0])
            if end_value is not None:
                obj.append(-float(np.asarray(end_value, float).ravel()[0]) * m.E[T])
        m.Qch = pyo.Expression(m.H, rule=lambda _m, t: _m.Qch_grid[t] + _qsrc(_m, t))
        if tes.get("exclusivity_binary", True):
            m.ych = pyo.Var(m.H, domain=pyo.Binary)
            m.ydis = pyo.Var(m.H, domain=pyo.Binary)
            m.chx = pyo.Constraint(m.H, rule=lambda _m, t: _m.Qch[t] <= tes["Q_ch_max_MW"] * _m.ych[t])
            m.disx = pyo.Constraint(m.H, rule=lambda _m, t: _m.Qdis[t] <= tes["Q_dis_max_MW"] * _m.ydis[t])
            m.x = pyo.Constraint(m.H, rule=lambda _m, t: _m.ych[t] + _m.ydis[t] <= 1)
        else:
            m.chx = pyo.Constraint(m.H, rule=lambda _m, t: _m.Qch[t] <= tes["Q_ch_max_MW"])
        for t in H:
            if tes_at_s:
                central_terms[t] += [m.Qdis[t], -m.Qch_grid[t]]
            else:
                tx_terms[t] += [m.Qdis[t], -m.Qch_grid[t]]

    # ---------------- new peak boiler (capacity decision, annualised cost)
    nb = cfg.get("new_boiler", {})
    if nb.get("enabled") and not unserved_mode(cfg):
        m.Cnew = pyo.Var(bounds=(float(nb.get("cap_min_MW", 0.0)), float(nb.get("cap_max_MW", 500.0))))
        m.newcap = pyo.Constraint(m.H, rule=lambda _m, t: _m.Q["NEW", t] <= _m.Cnew)
        obj.append(new_boiler_annual_cost_per_MW(cfg) * T * dt / 8760.0 * m.Cnew)

    # ---------------- existing electric boiler at the main plant (sensitivity; not in plan A)
    ek = cfg["plants"].get("existing_eb_at_kwk", {})
    if ek.get("enabled"):
        c_ek = (lam + ek.get("c_el_var_eur_MWh", 61.6)) / ek["eta"]
        m.Qebk = pyo.Var(m.H, bounds=(0.0, ek["cap_MW"] * ek["eta"]))
        obj.append(sum(float(c_ek[t]) * m.Qebk[t] for t in H) * dt)
    m.Qek = pyo.Expression(m.H, rule=lambda _m, t: _m.Qebk[t] if hasattr(_m, "Qebk") else 0.0)

    # ---------------- central feed-in, link, heat balance
    m.Qc = pyo.Expression(m.H, rule=lambda _m, t: sum(central_terms[t]) if central_terms[t] else 0.0)
    m.Qtx = pyo.Expression(m.H, rule=lambda _m, t: sum(tx_terms[t]) if tx_terms[t] else 0.0)
    if fl.link:
        lc = s["link_cap"].to_numpy()
        m.link_hi = pyo.Constraint(m.H, rule=lambda _m, t: _m.Qc[t] <= float(lc[t]) if central_terms[t] else pyo.Constraint.Skip)
        m.link_lo = pyo.Constraint(m.H, rule=lambda _m, t: _m.Qc[t] >= -float(lc[t]) if central_terms[t] else pyo.Constraint.Skip)
    if bounds is not None and fl.link:
        hi = bounds["hi"].to_numpy() if "hi" in bounds else np.full(T, np.nan)
        lo_ = bounds["lo"].to_numpy() if "lo" in bounds else np.full(T, np.nan)
        m.hyd_hi = pyo.Constraint(m.H, rule=lambda _m, t: _m.Qc[t] <= float(hi[t]) if np.isfinite(hi[t]) and central_terms[t] else pyo.Constraint.Skip)
        m.hyd_lo = pyo.Constraint(m.H, rule=lambda _m, t: _m.Qc[t] >= float(lo_[t]) if np.isfinite(lo_[t]) and central_terms[t] else pyo.Constraint.Skip)
    em = cfg["plants"].get("east_parallel_max_kg_s")
    if em:
        dh = x["dh"].to_numpy()
        m.east = pyo.Constraint(m.H, rule=lambda _m, t: sum(_m.Q[g, t] for g in ("MVA", "GT", "BIO")) <= float(em * dh[t] / 1e3))
    m.bal = pyo.Constraint(m.H, rule=lambda _m, t: sum(_m.Q[g, t] for g in PLANTS) + _m.Qc[t] + _m.Qtx[t] + _m.Qek[t] == float(D[t]))
    if cuts:     # linearised hydraulic cuts (Mode H): Σ_g a_g·Q_g,t + a_c·Q_central,t + a_x·Q_tes_ext,t ≤ rhs
        m.CUTS = pyo.RangeSet(0, len(cuts) - 1)

        def _cut(_m, i):
            t, a, rhs = cuts[i]["t"], cuts[i]["a"], cuts[i]["rhs"]
            e = sum(a.get(g, 0.0) * _m.Q[g, t] for g in PLANTS if g != "KWK" and abs(a.get(g, 0.0)) > 0)
            if central_terms[t] and abs(a.get("central", 0.0)) > 0:
                e = e + a["central"] * _m.Qc[t]
            if tx_terms[t] and abs(a.get("tes_ext", 0.0)) > 0:
                e = e + a["tes_ext"] * _m.Qtx[t]
            if isinstance(e, (int, float)):
                return pyo.Constraint.Skip
            return e <= rhs
        m.hcut = pyo.Constraint(m.CUTS, rule=_cut)
    m.obj = pyo.Objective(expr=sum(obj), sense=pyo.minimize)
    m._modes = modes
    m._flags = fl
    return m


def solve(m: pyo.ConcreteModel, cfg: dict, tee: bool = False) -> dict:
    sv = cfg["solver"]
    from pyomo.contrib.appsi.solvers import Highs

    opt = Highs()
    opt.config.mip_gap = sv["mip_rel_gap"]
    opt.config.time_limit = sv["time_limit_s"]
    opt.config.stream_solver = tee
    opt.config.load_solution = True
    opt.highs_options = {"threads": sv["threads"], "random_seed": sv["random_seed"], "presolve": sv["presolve"]}
    t0 = time.time()
    res = opt.solve(m)
    rt = time.time() - t0
    info = {"status": str(res.termination_condition), "objective": float(pyo.value(m.obj)),
            "bound": float(res.best_objective_bound) if res.best_objective_bound is not None else np.nan, "runtime_s": rt}
    info["gap"] = abs(info["objective"] - info["bound"]) / max(1.0, abs(info["objective"]))
    return info


def extract(m: pyo.ConcreteModel, x: pd.DataFrame, s: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Hourly schedule with all derived quantities."""
    T = len(x)
    fl: Flags = m._flags
    v = lambda var, *k: np.array([pyo.value(var[(*k, t)] if k else var[t]) for t in range(T)], float)  # noqa: E731
    out = pd.DataFrame(index=x.index)
    for g in PLANTS:
        out[f"Q_{g}"] = v(m.Q, g)
    cop = {"grid": s["COP_grid"], "tes": s["COP_tes"], "casc_grid": s["COP_mid"], "casc_tes": s["COP_mid"]}
    r = {"casc_grid": s["r_grid"].fillna(0.0), "casc_tes": s["r_tes"].fillna(0.0)}
    for md in HP_MODES:
        q = v(m.Qhp, md) if fl.A and md in m._modes else np.zeros(T)
        out[f"Q_HP_{md}"] = q
        out[f"P_HP_{md}"] = q / cop[md].to_numpy()
        out[f"Q_src_{md}"] = q * (1 - 1 / cop[md].to_numpy())
    out["Q_EB_boost_grid"] = r["casc_grid"].to_numpy() * out["Q_HP_casc_grid"]
    out["Q_EB_boost_tes"] = r["casc_tes"].to_numpy() * out["Q_HP_casc_tes"]
    out["P_EB"] = v(m.Peb) if fl.B else 0.0
    out["Q_EB_grid"] = v(m.Qeb_grid) if fl.B else 0.0
    out["Q_EB_tes"] = v(m.Qeb_tes) if fl.B else 0.0
    if fl.TES:
        out["E"] = v(m.E)
        out["E_end"] = np.array([pyo.value(m.E[t + 1]) for t in range(T)])
        out["Q_dis"] = v(m.Qdis)
        out["Q_ch_grid"] = v(m.Qch_grid)
        if cfg["tes"].get("model") == "classes":
            dens = class_density(cfg)
            vol_used = sum(np.array([pyo.value(m.Eb[k, t]) for t in range(T)]) / dens[k] for k in range(len(dens)))
            out["V_used_m3"] = vol_used
            for k, tk in enumerate(cfg["tes"]["classes_C"]):
                out[f"E_class_{int(tk)}"] = np.array([pyo.value(m.Eb[k, t]) for t in range(T)])
                out[f"ch_class_{int(tk)}"] = np.array([pyo.value(m.chb[k, t]) for t in range(T)])
                out[f"dis_class_{int(tk)}"] = np.array([pyo.value(m.disb[k, t]) for t in range(T)])
    else:
        out[["E", "E_end", "Q_dis", "Q_ch_grid"]] = 0.0
    out["Q_ch"] = (out["Q_ch_grid"] + out["Q_HP_tes"] + out["Q_HP_casc_tes"] + out["Q_EB_boost_tes"] + out["Q_EB_tes"])
    out["Q_central"] = np.array([pyo.value(m.Qc[t]) for t in range(T)], float) if fl.link else 0.0
    out["Q_tes_ext"] = np.array([pyo.value(m.Qtx[t]) for t in range(T)], float)
    out["Q_EBK"] = np.array([pyo.value(m.Qek[t]) for t in range(T)], float)
    out["C_new_MW"] = float(pyo.value(m.Cnew)) if hasattr(m, "Cnew") else 0.0
    out["Q_src_used"] = out[[f"Q_src_{md}" for md in HP_MODES]].sum(axis=1)
    out["Q_A_avail"] = x["Q_A_avail"] if fl.A else 0.0
    out["Q_A_unused"] = out["Q_A_avail"] - out["Q_src_used"]
    out["P_HP"] = out[[f"P_HP_{md}" for md in HP_MODES]].sum(axis=1)
    out["Q_HP"] = out[[f"Q_HP_{md}" for md in HP_MODES]].sum(axis=1)
    # cost components
    cost = plant_costs(x, cfg)
    for g in PLANTS:
        out[f"C_{g}"] = cost[g] * out[f"Q_{g}"]
    hp, eb = cfg["heat_pump"], cfg["electrode_boiler"]
    out["C_HP"] = (x["price"] + hp["c_el_var_eur_MWh"]) * out["P_HP"] + hp["pi_source_eur_MWh"] * out["Q_src_used"]
    out["C_EB"] = eb_heat_price(x, cfg) * eb["eta"] * out["P_EB"]
    out["C_NEW_cap"] = ((new_boiler_annual_cost_per_MW(cfg) * out["C_new_MW"] / 8760.0)
                        if cfg.get("new_boiler", {}).get("enabled") and not unserved_mode(cfg) else 0.0)
    out["D"] = x["D"]
    out["price"] = x["price"]
    out["T_VL"], out["T_RL"] = x["T_VL"], x["T_RL"]
    for c in ("E_max", "T_set", "link_cap", "mask_dis", "mask_ch_grid"):
        out[c] = s[c]
    return out
