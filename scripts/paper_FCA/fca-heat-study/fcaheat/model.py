"""The optimisation model: one LP per (site, storage configuration, connection regime)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pyomo.environ as pyo

from .config import CFG, ECON, get_solver
from .data import Inputs, annuity
from .fca import build_grid_limit, hlzf_mask


def cop_series(inp: Inputs, site_row: pd.Series, index: pd.DatetimeIndex,
               eta_scale: float = 1.0) -> pd.Series:
    mode = str(inp.par("HP", "cop_mode", "carnot")).strip().lower()
    if mode == "fixed":
        return pd.Series(float(inp.par("HP", "cop_fixed")) * eta_scale, index=index)
    eta = float(inp.par("HP", "eta_carnot")) * eta_scale
    t_sink = float(site_row["T_supply_C"]) + 273.15
    src = str(site_row.get("heat_source_type", "ambient air")).lower()
    if "ambient" in src:
        t_src = inp.market.loc[index, "T_ambient_C"].to_numpy() + 273.15
    else:
        t_src = np.full(len(index), float(site_row["T_source_C"]) + 273.15)
    cop = eta * t_sink / np.maximum(t_sink - t_src, 1.0)
    return pd.Series(np.clip(cop, float(inp.par("HP", "cop_min", 1.5)),
                             float(inp.par("HP", "cop_max", 6.0))), index=index)


def hp_admissible(inp: Inputs, site_row: pd.Series) -> bool:
    """A heat pump can only serve the site if the supply temperature is within reach."""
    return float(site_row["T_supply_C"]) <= float(inp.par("HP", "T_sink_max_C", 160))


def slice_horizon(inp: Inputs, site: str, years, resolution: str, heat_scale: float = 1.0,
                  price_scale: float = 1.0, price_spread: float = 1.0, months=None):
    mask = inp.el.index.year.isin(years)
    months = months if months is not None else CFG["months"]
    if months:
        mask = mask & inp.el.index.month.isin(months)
    df = pd.DataFrame({
        "el": inp.el.loc[mask, site],
        "heat": inp.heat.loc[mask, site] * heat_scale,
        "price": inp.market.loc[mask, "da_price_EUR_per_MWh"],
        "ef": inp.market.loc[mask, "grid_EF_tCO2_per_MWh"],
        "t_amb": inp.market.loc[mask, "T_ambient_C"],
    })
    if price_spread != 1.0:
        mu = df["price"].mean()
        df["price"] = mu + (df["price"] - mu) * price_spread
    df["price"] = df["price"] * price_scale
    if resolution == "1h":
        df = df.resample("1h").mean()
        dt = 1.0
    else:
        dt = 0.25
    return df, dt


@dataclass
class Case:
    site: str
    scenario: str
    fca: str = "FCA_FIRM"
    years: tuple = field(default_factory=lambda: tuple(CFG["years"]))
    resolution: str | None = None      # None -> CFG["resolution"] at construction time
    overrides: dict = field(default_factory=dict)
    fixed_sizes: dict | None = None
    seed: int | None = None
    label: str = ""

    def __post_init__(self):
        if self.resolution is None:
            self.resolution = CFG["resolution"]
        if not self.years:
            self.years = tuple(CFG["years"])

    def key(self):
        ov = "|".join(f"{k}={v:g}" for k, v in sorted(self.overrides.items())
                      if isinstance(v, (int, float)))
        return f"{self.site}__{self.scenario}__{self.fca}" + (f"__{ov}" if ov else "")


def _ov(case: Case, key: str, default: float = 1.0) -> float:
    return float(case.overrides.get(key, default))


def _intensive_kpis(e_grid_MWh: float, peak_MW: float, years_frac: float,
                    disc_intensive: float) -> dict:
    """§ 19 Abs. 2 S. 2 StromNEV post-hoc eligibility (rule 6: a check, never an LP binary).

    Utilisation hours = annual energy / annual peak. Electrification raises both, so a site can
    cross the 7,000 h / 10 GWh threshold *because* of the project and earn an individual network
    charge — a driver that works against peak shaving. Reported every solve; the discount is only
    *applied* by the two-pass driver once eligibility is confirmed."""
    annual_MWh = e_grid_MWh / max(years_frac, 1e-9)
    util_h = annual_MWh / max(peak_MW, 1e-9)
    annual_GWh = annual_MWh / 1000.0
    eligible = (util_h >= ECON["intensive_min_util_h"]
                and annual_GWh >= ECON["intensive_min_energy_GWh"])
    return dict(util_hours_h=util_h, annual_energy_GWh=annual_GWh,
                intensive_eligible=bool(eligible),
                intensive_discount_applied=float(disc_intensive))


def build_model(inp: Inputs, case: Case):
    srow = inp.sites.set_index("site_id").loc[case.site]
    scn = inp.scenarios.set_index("scenario_id").loc[case.scenario]

    df, dt = slice_horizon(inp, case.site, case.years, case.resolution,
                           heat_scale=_ov(case, "site.heat_demand"),
                           price_scale=_ov(case, "market.da_price"),
                           price_spread=_ov(case, "market.da_price_spread"))
    T = len(df)
    years_frac = T * dt / 8760.0
    P_exist = float(srow["P_grid_exist_MW"]) * _ov(case, "site.P_grid_exist_MW")

    # ---- connection regime -------------------------------------------------
    P_limit, free_conn, restricted, frow = build_grid_limit(
        inp, case.fca, df.index, P_exist, df["price"].to_numpy(), dt, seed=case.seed,
        flex_scale=_ov(case, "fca.P_flex_rel"),
        window_width=case.overrides.get("fca.window_width"),
        curtail_h=case.overrides.get("fca.max_curtail_h_per_a"))
    disc_fca = float(case.overrides.get("fca.netzentgelt_discount", frow["netzentgelt_discount"]))

    # ---- billing window (§ 19 Abs. 2 StromNEV) -----------------------------
    atyp = bool(int(srow.get("atypical_eligible", 0))) and CFG["apply_hlzf"]
    bill = hlzf_mask(inp, df.index) if atyp else np.ones(T, bool)
    disc_atyp = ECON["atypical_discount_max"] if atyp else 0.0

    # ---- economics ---------------------------------------------------------
    wacc = float(case.overrides.get("ECON.wacc", ECON["wacc"]))
    # § 19 Abs. 2 S. 2 StromNEV intensive-use discount: never applied on the first pass (default 0);
    # the two-pass driver (runner.solve_intensive_two_pass) sets it once eligibility is confirmed.
    disc_intensive = float(case.overrides.get("ECON.intensive_discount", 0.0))
    c_cap = (ECON["grid_capacity_price_EUR_per_MW_a"]
             * _ov(case, "ECON.grid_capacity_price_EUR_per_MW_a")
             * (1 - disc_fca) * (1 - disc_atyp) * (1 - disc_intensive))
    c_el = (df["price"].to_numpy() + ECON["grid_energy_price_EUR_per_MWh"]
            + ECON["electricity_tax_EUR_per_MWh"])

    cx = dict(hp=float(inp.par("HP", "capex_EUR_per_MW_th")),
              eb=float(inp.par("EB", "capex_EUR_per_MW_el")),
              tes_e=float(inp.par("TES", "capex_EUR_per_MWh")) * _ov(case, "TES.capex_EUR_per_MWh"),
              tes_p=float(inp.par("TES", "capex_EUR_per_MW")),
              bes_e=float(inp.par("BES", "capex_EUR_per_MWh")) * _ov(case, "BES.capex_EUR_per_MWh"),
              bes_p=float(inp.par("BES", "capex_EUR_per_MW")))
    ann = dict(
        hp=annuity(cx["hp"], inp.par("HP", "lifetime_a"), wacc)
           + cx["hp"] * float(inp.par("HP", "opex_fix_pct_capex")),
        eb=annuity(cx["eb"], inp.par("EB", "lifetime_a"), wacc)
           + cx["eb"] * float(inp.par("EB", "opex_fix_pct_capex")),
        tes_e=annuity(cx["tes_e"], inp.par("TES", "lifetime_a"), wacc),
        tes_p=annuity(cx["tes_p"], inp.par("TES", "lifetime_a"), wacc),
        bes_e=annuity(cx["bes_e"], inp.par("BES", "lifetime_a"), wacc),
        bes_p=annuity(cx["bes_p"], inp.par("BES", "lifetime_a"), wacc),
        reinf=annuity(ECON["grid_reinforcement_EUR_per_MW"], ECON["project_lifetime_a"], wacc))

    cop = cop_series(inp, srow, df.index, eta_scale=_ov(case, "HP.eta_carnot")).to_numpy()
    eta_eb = float(inp.par("EB", "efficiency"))
    on = dict(hp=int(scn["hp"]) and int(hp_admissible(inp, srow)),
              eb=int(scn["eb"]), tes=int(scn["tes"]), bes=int(scn["bes"]))

    meta = dict(df=df, dt=dt, T=T, years_frac=years_frac, cop=cop, c_el=c_el,
                ef=df["ef"].to_numpy(), P_exist=P_exist, P_limit=P_limit, restricted=restricted,
                bill=bill, atyp=atyp, on=on, ann=ann, srow=srow, c_cap=c_cap,
                disc_fca=disc_fca, disc_intensive=disc_intensive, free_conn=free_conn,
                hp_blocked=bool(int(scn["hp"])) and not hp_admissible(inp, srow))

    if not (on["hp"] or on["eb"]):
        meta["baseline"] = True
        return None, meta
    meta["baseline"] = False

    m = pyo.ConcreteModel(case.key())
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)   # F16: value of connection capacity
    m.T = pyo.RangeSet(0, T - 1)
    m.pg = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.php = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.peb = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.qu = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.pu = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.Qhp = pyo.Var(bounds=(0, float(inp.par("HP", "size_max_MW_th")) if on["hp"] else 0))
    m.Peb = pyo.Var(bounds=(0, float(inp.par("EB", "size_max_MW_el")) if on["eb"] else 0))
    m.Ppeak = pyo.Var(domain=pyo.NonNegativeReals)
    m.Pconn = pyo.Var(domain=pyo.NonNegativeReals)
    m.dP = pyo.Var(domain=pyo.NonNegativeReals)
    m.qc = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.qd = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.sth = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.Etes = pyo.Var(bounds=(0, float(inp.par("TES", "size_max_MWh")) if on["tes"] else 0))
    m.pc = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.pd = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.sel = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.Ebes = pyo.Var(bounds=(0, float(inp.par("BES", "size_max_MWh")) if on["bes"] else 0))

    heat = df["heat"].to_numpy(); elec = df["el"].to_numpy()

    m.heat_bal = pyo.Constraint(m.T, rule=lambda m, t:
        cop[t] * m.php[t] + eta_eb * m.peb[t] + m.qd[t] - m.qc[t] + m.qu[t] == heat[t])
    m.el_bal = pyo.Constraint(m.T, rule=lambda m, t:
        m.pg[t] + m.pd[t] + m.pu[t] == elec[t] + m.php[t] + m.peb[t] + m.pc[t])

    # --- III: the FCA limit -------------------------------------------------
    if free_conn:
        m.conn = pyo.Constraint(m.T, rule=lambda m, t: m.pg[t] <= m.Pconn)
        m.uplift = pyo.Constraint(expr=m.dP >= m.Pconn - P_exist)
    else:
        finite = np.isfinite(P_limit)
        m.fca_lim = pyo.Constraint(m.T, rule=lambda m, t:
            m.pg[t] <= float(P_limit[t]) if finite[t] else pyo.Constraint.Skip)
        m.Pconn.fix(float(np.nanmax(P_limit[finite])) if finite.any() else P_exist)
        m.dP.fix(0.0)

    # --- IV: billed peak ----------------------------------------------------
    m.peak = pyo.Constraint(m.T, rule=lambda m, t:
        m.Ppeak >= m.pg[t] if bill[t] else pyo.Constraint.Skip)

    m.hp_cap = pyo.Constraint(m.T, rule=lambda m, t: cop[t] * m.php[t] <= m.Qhp)
    m.eb_cap = pyo.Constraint(m.T, rule=lambda m, t: m.peb[t] <= m.Peb)

    prev = (lambda t: T - 1 if t == 0 else t - 1)
    l_t = float(inp.par("TES", "loss_pct_per_h")); e_tc = float(inp.par("TES", "eta_charge"))
    e_td = float(inp.par("TES", "eta_discharge")); c_t = float(inp.par("TES", "c_rate_max"))
    s_t = float(inp.par("TES", "soc_min_rel"))
    m.tes_dyn = pyo.Constraint(m.T, rule=lambda m, t:
        m.sth[t] == (1 - l_t * dt) * m.sth[prev(t)] + e_tc * m.qc[t] * dt - m.qd[t] * dt / e_td)
    m.tes_up = pyo.Constraint(m.T, rule=lambda m, t: m.sth[t] <= m.Etes)
    m.tes_lo = pyo.Constraint(m.T, rule=lambda m, t: m.sth[t] >= s_t * m.Etes)
    m.tes_pc = pyo.Constraint(m.T, rule=lambda m, t: m.qc[t] <= c_t * m.Etes)
    m.tes_pd = pyo.Constraint(m.T, rule=lambda m, t: m.qd[t] <= c_t * m.Etes)

    l_b = float(inp.par("BES", "loss_pct_per_h")); e_bc = float(inp.par("BES", "eta_charge"))
    e_bd = float(inp.par("BES", "eta_discharge")); c_b = float(inp.par("BES", "c_rate_max"))
    s_b = float(inp.par("BES", "soc_min_rel"))
    m.bes_dyn = pyo.Constraint(m.T, rule=lambda m, t:
        m.sel[t] == (1 - l_b * dt) * m.sel[prev(t)] + e_bc * m.pc[t] * dt - m.pd[t] * dt / e_bd)
    m.bes_up = pyo.Constraint(m.T, rule=lambda m, t: m.sel[t] <= m.Ebes)
    m.bes_lo = pyo.Constraint(m.T, rule=lambda m, t: m.sel[t] >= s_b * m.Ebes)
    m.bes_pc = pyo.Constraint(m.T, rule=lambda m, t: m.pc[t] <= c_b * m.Ebes)
    m.bes_pd = pyo.Constraint(m.T, rule=lambda m, t: m.pd[t] <= c_b * m.Ebes)
    if CFG["limit_bes_cycles"]:
        n_max = float(inp.par("BES", "cycles_max_per_a"))
        m.bes_cyc = pyo.Constraint(expr=sum(m.pd[t] for t in m.T) * dt
                                   <= n_max * years_frac * m.Ebes)

    if case.fixed_sizes:
        for nm, var in [("Qhp", m.Qhp), ("Peb", m.Peb), ("Etes", m.Etes), ("Ebes", m.Ebes)]:
            if nm in case.fixed_sizes:
                var.fix(float(case.fixed_sizes[nm]))

    m.capex = pyo.Expression(expr=(ann["hp"] * m.Qhp + ann["eb"] * m.Peb
                                   + ann["tes_e"] * m.Etes + ann["tes_p"] * c_t * m.Etes
                                   + ann["bes_e"] * m.Ebes + ann["bes_p"] * c_b * m.Ebes
                                   + ann["reinf"] * m.dP) * years_frac)
    m.energy = pyo.Expression(expr=sum(m.pg[t] * c_el[t] for t in m.T) * dt)
    m.capchg = pyo.Expression(expr=c_cap * m.Ppeak * years_frac)
    m.penalty = pyo.Expression(expr=ECON["voll_EUR_per_MWh"]
                               * sum(m.qu[t] + m.pu[t] for t in m.T) * dt)
    m.obj = pyo.Objective(expr=m.capex + m.energy + m.capchg + m.penalty, sense=pyo.minimize)
    meta.update(c_t=c_t, c_b=c_b)
    return m, meta


def solve_with_fallback(opt, m):
    def _status(r):
        return str(getattr(r, "termination_condition",
                           getattr(getattr(r, "solver", None), "termination_condition", "unknown")))
    try:
        r = opt.solve(m)
        return r, _status(r)
    except Exception as exc:
        print(f"    ! {type(exc).__name__} with {CFG.get('solver_options')} -> simplex retry")
        opt2 = pyo.SolverFactory(CFG["solver"])
        if CFG["solver"].startswith("appsi"):
            opt2.highs_options = {"solver": "simplex"}
        r = opt2.solve(m)
        return r, _status(r) + "|simplex_fallback"


def solve_case(inp: Inputs, case: Case, opt=None) -> dict:
    t0 = time.time()
    m, meta = build_model(inp, case)
    df, dt, T, yf = meta["df"], meta["dt"], meta["T"], meta["years_frac"]
    common = dict(case=case.key(), site=case.site, scenario=case.scenario, fca=case.fca,
                  years_frac=yf, dt=dt, atypical=meta["atyp"],
                  P_grid_exist_MW=meta["P_exist"],
                  P_limit_min_MW=float(np.nanmin(meta["P_limit"])),
                  P_limit_max_MW=float(np.nanmax(meta["P_limit"][np.isfinite(meta["P_limit"])]))
                  if np.isfinite(meta["P_limit"]).any() else np.nan,
                  restricted_share=float(meta["restricted"].mean()),
                  hp_blocked_by_temperature=meta["hp_blocked"])

    # ------------------------------------------------ baseline: gas + biomethane
    if meta["baseline"]:
        s = meta["srow"]
        eta_b = float(s["boiler_efficiency"])
        fuel = df["heat"].sum() * dt / eta_b
        share = float(s["biomethane_share"])
        fuel_cost = fuel * (float(s["gas_price_EUR_per_MWh_th"])
                            + share * float(case.overrides.get(
                                "site.biomethane_premium", s["biomethane_premium_EUR_per_MWh_th"])))
        co2_phys = fuel * float(s["gas_EF_tCO2_per_MWh_th"])
        co2_cert = co2_phys * (1 - share)
        peak = float(df["el"].to_numpy()[meta["bill"]].max()) if meta["bill"].any() else 0.0
        e_grid = df["el"].sum() * dt
        cost = (fuel_cost + co2_cert * ECON["co2_price_EUR_per_t"]
                + (df["el"] * meta["c_el"]).sum() * dt + meta["c_cap"] * peak * yf)
        ts = pd.DataFrame({"grid": df["el"], "heat_dem": df["heat"],
                           "P_limit": meta["P_limit"]}, index=df.index)
        kpi = dict(**common, status="baseline", runtime_s=time.time() - t0,
                   Qhp_MW=0.0, Peb_MW=0.0, Etes_MWh=0.0, Ebes_MWh=0.0, Ptes_MW=0.0, Pbes_MW=0.0,
                   peak_grid_MW=float(df["el"].max()), billed_peak_MW=peak,
                   E_grid_MWh=e_grid, E_heat_MWh=df["heat"].sum() * dt,
                   CO2_cert_t=co2_cert + (df["el"] * df["ef"]).sum() * dt,
                   CO2_phys_t=co2_phys + (df["el"] * df["ef"]).sum() * dt,
                   unserved_MWh=0.0, unserved_el_MWh=0.0,
                   cost_total_EUR=cost, cost_capex_EUR=0.0,
                   cost_energy_EUR=(df["el"] * meta["c_el"]).sum() * dt,
                   cost_capacity_EUR=meta["c_cap"] * peak * yf,
                   cost_fuel_EUR=fuel_cost, cost_co2_EUR=co2_cert * ECON["co2_price_EUR_per_t"],
                   hp_share=0.0, flh_hp_h=0.0, flh_eb_h=0.0, tes_cycles=0.0, bes_cycles=0.0,
                   avg_price_EUR_MWh=float(df["price"].mean()),
                   mean_price_EUR_MWh=float(df["price"].mean()),
                   shadow_conn_EUR_MW=np.nan,
                   **_intensive_kpis(e_grid, float(df["el"].max()), yf,
                                     meta["disc_intensive"]))
        return {"kpi": kpi, "ts": ts, "meta": meta}

    # ------------------------------------------------ optimisation
    opt = opt or get_solver()
    t1 = time.time()
    r, status = solve_with_fallback(opt, m)

    v = lambda x: np.array([pyo.value(x[t]) for t in m.T])
    ts = pd.DataFrame(index=df.index)
    ts["el_base"] = df["el"].to_numpy(); ts["heat_dem"] = df["heat"].to_numpy()
    ts["p_hp"] = v(m.php); ts["p_eb"] = v(m.peb)
    ts["q_hp"] = meta["cop"] * ts["p_hp"]
    ts["q_eb"] = float(inp.par("EB", "efficiency")) * ts["p_eb"]
    ts["tes_ch"] = v(m.qc); ts["tes_dis"] = v(m.qd); ts["tes_soc"] = v(m.sth)
    ts["bes_ch"] = v(m.pc); ts["bes_dis"] = v(m.pd); ts["bes_soc"] = v(m.sel)
    ts["grid"] = v(m.pg); ts["unserved"] = v(m.qu); ts["unserved_el"] = v(m.pu)
    ts["P_limit"] = meta["P_limit"]; ts["restricted"] = meta["restricted"]
    ts["price"] = df["price"].to_numpy(); ts["ef"] = df["ef"].to_numpy(); ts["cop"] = meta["cop"]

    # F16: shadow price of the connection constraint = EUR marginal value of 1 MW of extra
    # withdrawal capacity in each interval. The dual is on the objective, whose non-annuity terms
    # already carry the horizon fraction, so it is comparable across sub-year and full-year runs.
    # Sign: pg <= P_limit is a <= constraint, so its multiplier is non-positive; report magnitude.
    conn = getattr(m, "conn", None) if meta["free_conn"] else getattr(m, "fca_lim", None)
    shadow = np.full(T, np.nan)
    if conn is not None:
        for t in m.T:
            if t in conn:                      # skipped where the limit is +inf
                d = m.dual.get(conn[t])
                if d is not None:
                    shadow[t] = abs(float(d))
    ts["shadow_conn_EUR_MW"] = shadow

    Qhp, Peb = pyo.value(m.Qhp), pyo.value(m.Peb)
    Etes, Ebes = pyo.value(m.Etes), pyo.value(m.Ebes)
    peak = float(ts["grid"].max())
    billed = float(ts["grid"].to_numpy()[meta["bill"]].max()) if meta["bill"].any() else 0.0
    e_grid = ts["grid"].sum() * dt
    co2 = (ts["grid"] * ts["ef"]).sum() * dt

    kpi = dict(**common, status=status, runtime_s=time.time() - t0,
               runtime_solve_s=time.time() - t1,
               Qhp_MW=Qhp, Peb_MW=Peb, Etes_MWh=Etes, Ebes_MWh=Ebes,
               Ptes_MW=meta["c_t"] * Etes, Pbes_MW=meta["c_b"] * Ebes,
               peak_grid_MW=peak, billed_peak_MW=billed,
               uplift_MW=max(0.0, peak - meta["P_exist"]),
               E_grid_MWh=e_grid, E_heat_MWh=ts["heat_dem"].sum() * dt,
               CO2_cert_t=co2, CO2_phys_t=co2,
               unserved_MWh=ts["unserved"].sum() * dt,
               unserved_el_MWh=ts["unserved_el"].sum() * dt,
               cost_total_EUR=pyo.value(m.obj) - pyo.value(m.penalty),
               cost_capex_EUR=pyo.value(m.capex), cost_energy_EUR=pyo.value(m.energy),
               cost_capacity_EUR=pyo.value(m.capchg), cost_fuel_EUR=0.0, cost_co2_EUR=0.0,
               penalty_EUR=pyo.value(m.penalty),
               hp_share=float(ts["q_hp"].sum() / max(ts["q_hp"].sum() + ts["q_eb"].sum(), 1e-9)),
               flh_hp_h=float(ts["q_hp"].sum() * dt / max(Qhp, 1e-9) / yf),
               flh_eb_h=float(ts["p_eb"].sum() * dt / max(Peb, 1e-9) / yf),
               tes_cycles=float(ts["tes_dis"].sum() * dt / max(Etes, 1e-9) / yf),
               bes_cycles=float(ts["bes_dis"].sum() * dt / max(Ebes, 1e-9) / yf),
               avg_price_EUR_MWh=float((ts["grid"] * ts["price"]).sum()
                                       / max(ts["grid"].sum(), 1e-9)),
               mean_price_EUR_MWh=float(ts["price"].mean()),
               binding_share=float((ts["grid"] >= ts["P_limit"] - 1e-6).mean()),
               shadow_conn_EUR_MW=float(np.nansum(shadow)),
               shadow_conn_peak_EUR_MW=float(np.nanmax(shadow)) if np.isfinite(shadow).any()
               else np.nan,
               **_intensive_kpis(e_grid, peak, yf, meta["disc_intensive"]))

    # how much of the contractual restriction actually bites: a restricted interval in which the
    # limit never binds costs the plant nothing, and that gap is a negotiating argument
    bind = (ts["grid"] >= ts["P_limit"] - 1e-6).to_numpy()
    restr = meta["restricted"]
    kpi["binding_restricted_share"] = float(bind[restr].mean()) if restr.any() else np.nan
    kpi["binding_free_share"] = float(bind[~restr].mean()) if (~restr).any() else np.nan
    # share of ALL intervals in which the contractual restriction actually constrains the plant.
    # The gap to `restricted_share` is capacity the operator reserves but never needs — the
    # plant's strongest argument for a narrower restriction.
    kpi["restriction_bite_share"] = (kpi["binding_restricted_share"] * kpi["restricted_share"]
                                     if restr.any() else 0.0)
    return {"kpi": kpi, "ts": ts, "meta": meta}
