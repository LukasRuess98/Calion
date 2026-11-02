"""Rolling-horizon operation of F111 (spec 7.3).

Each day at 00:00 the MILP is solved over a 72-h window with forecasts; the first 24 h of the central decisions
(HP output per mode, electrode-boiler power, TES charge from the network and discharge) are committed. Realisation:
the committed central decisions meet the actual data (the HP is curtailed if the actual partner-A heat is lower than
planned; TES charging from the HP is reduced accordingly) and the existing plants cover the actual residual demand in
merit order (single-hour LP, solved greedily: individual bounds, must-run, east-group limit). The SOC is propagated with
the realised flows **per temperature class** (class model) and handed to the next window per class, so that network
water charged into a lower class is not relabelled as top-class energy. Discharge is limited by the realised class
energy. The tank starts empty and energy left at the end of the year is not credited (conservative; reported as
``rh_soc_end_MWh``), so the rolling-horizon year gets no stored energy for free. (A hand-back condition on the top
class is infeasible when lower classes are full in winter, where they cannot be discharged.)

Forecasts (flagged assumptions):
* demand: actual × (1 + ε_t), ε_t ~ N(0, σ_D) i.i.d. per hour (multiplicative noise; a simplification of the
  parametric approach of ``calion.forecasting.PerfectNoiseForecast``), σ_D = 5 %, drawn per window from
  (solver.random_seed, window start); robustness over seeds and σ = 10 / 15 % in ``run_robustness``;
* prices: day-ahead prices known up to the end of the delivery day (and of the next day for decisions at or after
  13:00, after the auction); beyond, the last known day is repeated (``da_repeat``). The version of 2026-10-10 used the
  same hour of the previous day (``lag24``), which for hours 48–71 used not-yet-known prices (results archived in
  ``rolling_horizon_v1_lag24``);
* partner A: ``schedule_known_day_ahead`` (actual for 24 h, same hour one week earlier beyond) or ``persistence``
  (same hour one week earlier for the whole window);
* supply/return temperature: actual (weather-driven, flagged).
Variants for the foresight decomposition (``run_foresight``): window length, commitment (24 h or hourly re-planning),
perfect prices / demand / partner A, terminal value of the stored energy, perfect-foresight guide curve.
Mode H in RH: the converged cuts of PF Mode H (same hours) are added to every window (approximation, documented).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from . import cop, inputs, metrics, milp

WINDOW_H, COMMIT_H = 72, 24


def _price_forecast(x: pd.DataFrame, i0: int, n: int, price_fc: str) -> np.ndarray:
    """Price forecast for hours i0 … i0+n−1 decided at i0. ``perfect``: actual prices; ``da_repeat``: day-ahead known
    for 24 h, then the known day repeated (no information beyond the first day); ``lag24`` (version of 2026-10-10):
    same hour of the previous day, which for hours 48–71 uses prices of day 2 that are not yet known (slight look-ahead)."""
    act = x["price"].to_numpy()[i0:i0 + n]
    if price_fc == "perfect":
        return act.copy()
    if price_fc == "da_repeat":   # known: rest of today, plus tomorrow after the day-ahead auction (decision hour ≥ 13)
        hod = i0 % 24
        known = min((24 - hod) + (24 if hod >= 13 else 0), n)
        return np.array([x["price"].iat[i0 + k] if k < known else x["price"].iat[i0 + known - 24 + ((k - known) % 24)]
                         for k in range(n)])
    day = min(COMMIT_H, n)
    lag = np.array([x["price"].iat[max(i0 + k - 24, 0)] for k in range(n)])
    return np.r_[act[:day], lag[day:]]


KNOTS = (-10.0, 0.0, 5.0, 10.0, 15.0, 20.0)       # as inputs._demand_model (imputation model of the 335 h)
WX_SD_K = (1.0, 2.0, 3.0)                       # weather-forecast error of the daily mean temperature, lead day 1/2/3
DEMAND_FC = ("iid", "model", "model_wx", "ar1", "model_res", "model_res_damped")
RES_DAMP = 0.7                                     # A4b: residual correction × 0.7^lead day (lead day 1, 2, 3)


def _design(tam: np.ndarray, how: np.ndarray) -> np.ndarray:
    X = np.zeros((len(tam), 1 + len(KNOTS) + 167))
    X[:, 0] = 1.0
    for j, k in enumerate(KNOTS):
        X[:, 1 + j] = np.maximum(k - tam, 0.0)
    m = how > 0
    X[np.arange(len(tam))[m], 1 + len(KNOTS) + how[m] - 1] = 1.0
    return X


class DemandModel:
    """Demand forecast from the imputation model (piecewise linear in the daily mean outdoor temperature + hour-of-week
    profile), fitted leave-one-month-out on the measured (not imputed) hours: the coefficients used for a month never
    saw that month. Outdoor temperature: measured daily mean (perfect weather forecast) or with a lead-time error."""

    def __init__(self, x: pd.DataFrame):
        self.tam = x["T_amb"].groupby(x.index.date).transform("mean").to_numpy(float)
        self.how = (x.index.dayofweek * 24 + x.index.hour).to_numpy()
        self.month = x.index.month.to_numpy()
        base = x["D_base"].to_numpy(float) if "D_base" in x else x["D"].to_numpy(float)
        self.scale = np.where(base > 0, x["D"].to_numpy(float) / np.maximum(base, 1e-9), 1.0)   # expansion share
        X = _design(self.tam, self.how)
        ok = np.isfinite(base) & ~x["D_imputed"].to_numpy(bool) & np.isfinite(X).all(axis=1)
        self.coef = {mo: np.linalg.lstsq(X[ok & (self.month != mo)], base[ok & (self.month != mo)], rcond=None)[0]
                     for mo in np.unique(self.month)}

    def predict(self, i0: int, i1: int, dtam: np.ndarray | None = None) -> np.ndarray:
        tam = self.tam[i0:i1] + (0.0 if dtam is None else dtam)
        X = _design(tam, self.how[i0:i1])
        mo = self.month[i0:i1]
        y = np.array([X[k] @ self.coef[mo[k]] for k in range(i1 - i0)])
        return np.maximum(y * self.scale[i0:i1], 0.0)


def demand_forecast(x: pd.DataFrame, i0: int, i1: int, demand_fc: str, sigma: float, rng, dm: DemandModel | None = None,
                    rho: float = 0.9) -> np.ndarray:
    """Demand forecast for hours i0 … i1−1 decided at i0. ``iid`` (reference): actual × (1 + ε), ε i.i.d. N(0, σ);
    ``model``: LOMO demand model with measured temperature; ``model_wx``: same with a daily-temperature error
    N(0, 1 / 2 / 3 K) for lead day 1 / 2 / 3 (drawn per window from (seed, window start)); ``ar1``: actual × (1 + ε)
    with ε AR(1), ρ per hour, stationary SD σ."""
    act = x["D"].to_numpy(float)[i0:i1]
    n = len(act)
    if demand_fc == "iid":
        if isinstance(rng, int):     # noise drawn per window from (seed, window start): identical errors for the first
            eps = np.random.default_rng([rng, i0]).normal(0.0, sigma, max(n, 336))[:n]   # hours whatever the window length
        else:                        # one stream over all windows (version of 2026-10-10)
            eps = rng.normal(0.0, sigma, n)
        return np.maximum(act * (1 + eps), 0.0)
    seed = rng if isinstance(rng, int) else 0
    if demand_fc == "ar1":
        z = np.random.default_rng([seed, i0, 1]).normal(0.0, 1.0, max(n, 336))[:n]
        eps = np.empty(n)
        eps[0] = sigma * z[0]
        for k in range(1, n):
            eps[k] = rho * eps[k - 1] + sigma * np.sqrt(1 - rho**2) * z[k]
        return np.maximum(act * (1 + eps), 0.0)
    if demand_fc == "model":
        return dm.predict(i0, i1)
    if demand_fc in ("model_res", "model_res_damped"):
        # A4: model + residual of the same hour on the last day with measurements (the 24 h before the decision),
        # A4b: the same correction damped by RES_DAMP per lead day
        base = dm.predict(i0, i1)
        if i0 < 24:
            return base
        res = x["D"].to_numpy(float)[i0 - 24:i0] - dm.predict(i0 - 24, i0)
        k = np.arange(n)
        corr = res[k % 24]
        if demand_fc == "model_res_damped":
            corr = corr * RES_DAMP ** (k // 24 + 1)
        return np.maximum(base + corr, 0.0)
    if demand_fc == "model_wx":
        lead = np.minimum(np.arange(n) // 24, len(WX_SD_K) - 1)
        e = np.random.default_rng([seed, i0, 2]).normal(0.0, 1.0, len(WX_SD_K)) * np.asarray(WX_SD_K)
        return dm.predict(i0, i1, dtam=e[lead])
    raise ValueError(demand_fc)


def _forecast(x: pd.DataFrame, i0: int, i1: int, mode: str, sigma: float, rng, price_fc: str = "lag24",
              demand_fc: str = "iid", dm: DemandModel | None = None) -> pd.DataFrame:
    f = x.iloc[i0:i1].copy()
    n = len(f)
    f["D"] = demand_forecast(x, i0, i1, demand_fc, sigma, rng, dm)
    for c in [c for c in f.columns if c.startswith("lo_")]:      # must-run bound follows the forecast demand
        f[c] = np.minimum(f[c], f["D"])
    day = min(COMMIT_H, n)
    lag = lambda col, h: np.array([x[col].iat[max(i0 + k - h, 0)] for k in range(n)])  # noqa: E731
    f["price"] = _price_forecast(x, i0, n, price_fc)
    week = lag("Q_A_avail", 168)
    if mode == "persistence":
        f["Q_A_avail"] = week
    elif mode == "perfect":
        pass
    else:
        f["Q_A_avail"] = np.r_[f["Q_A_avail"].to_numpy()[:day], week[day:]]
    return f


def _marginal_cost(xs: pd.DataFrame, cfg: dict) -> np.ndarray:
    """Marginal heat cost per hour [EUR/MWh]: cost of the most expensive plant dispatched above its lower bound when
    the existing plants cover the demand in merit order (no central units)."""
    q = _merit_order(xs, cfg, xs["D"].to_numpy())
    lo, _ = milp.plant_bounds(xs, cfg)
    c = milp.plant_costs(xs, cfg)[milp.PLANTS].to_numpy()
    above = q > lo[milp.PLANTS].to_numpy() + 1e-6
    mc = np.where(above, c, -np.inf).max(axis=1)
    return np.where(np.isfinite(mc), mc, np.where(q > 1e-6, c, np.inf).min(axis=1))


def _terminal_value(x: pd.DataFrame, cfg: dict, i0: int, i1: int, price_fc: str, lookahead_h: int) -> np.ndarray | float:
    """Terminal value of stored energy per class: mean marginal heat cost over the ``lookahead_h`` hours after the
    window end, counted only in hours where the class can discharge (T_k ≥ T_VL); 0 if it cannot discharge there.
    Prices in the look-ahead follow the price forecast decided at i0 (actual demand = expected value of the forecast)."""
    j1 = min(i1 + lookahead_h, len(x))
    if j1 <= i1:
        return 0.0
    xs = x.iloc[i1:j1].copy()
    pf = _price_forecast(x, i0, j1 - i0, price_fc)
    xs["price"] = pf[i1 - i0:]
    mc = _marginal_cost(xs, cfg)
    tvl = xs["T_VL"].to_numpy()
    if cfg["tes"].get("model") != "classes":
        return float(np.mean(mc))
    tb = np.asarray(cfg["tes"]["classes_C"], float)
    return np.array([float(np.mean(mc[tk >= tvl])) if (tk >= tvl).any() else 0.0 for tk in tb])


def _merit_order(x: pd.DataFrame, cfg: dict, resid: np.ndarray) -> np.ndarray:
    """Greedy single-hour dispatch of the existing plants (cost order, bounds, must-run, east-group limit)."""
    lo, hi = milp.plant_bounds(x, cfg)
    cost = milp.plant_costs(x, cfg)
    em = cfg["plants"].get("east_parallel_max_kg_s")
    east_cap = em * x["dh"].to_numpy() / 1e3 if em else np.full(len(x), np.inf)
    P = milp.PLANTS
    q = np.zeros((len(x), len(P)))
    for t in range(len(x)):
        need = resid[t]
        q[t] = lo.iloc[t][P].to_numpy()
        need -= q[t].sum()
        east_used = sum(q[t][P.index(g)] for g in ("MVA", "GT", "BIO"))
        for j in np.argsort(cost.iloc[t][P].to_numpy()):
            if need <= 1e-9:
                break
            room = hi.iat[t, hi.columns.get_loc(P[j])] - q[t, j]
            if P[j] in ("MVA", "GT", "BIO"):
                room = min(room, east_cap[t] - east_used)
            d = max(0.0, min(room, need))
            q[t, j] += d
            need -= d
            if P[j] in ("MVA", "GT", "BIO"):
                east_used += d
        if need > 1e-6:                      # residual (should not occur): KWK beyond its bound, flagged
            q[t, P.index("KWK")] += need
        if need < -1e-6:                     # over-supply by must-run/central: reduce must-run plants
            q[t, P.index("BIO")] = max(0.0, q[t, P.index("BIO")] + need)
    return q


def run(cfg: dict, out: Path, a_mode: str | None = None, sigma: float = 0.05, cuts: list | None = None, tag: str = "E",
        code: str = "F111", window_h: int = WINDOW_H, price_fc: str = "da_repeat", terminal: str | None = None,
        lookahead_h: int = 168, guide: pd.DataFrame | None = None, noise: str = "window", commit_h: int = COMMIT_H,
        demand_fc: str = "iid") -> dict:
    """``window_h`` optimisation window; ``price_fc`` see ``_price_forecast``; ``a_mode`` also ``perfect``;
    ``terminal``: None (reference), ``mc`` (terminal value per class, ``_terminal_value``) or ``guide`` (soft
    end-of-window target per class from the perfect-foresight trajectory ``guide``, an upper-bound experiment)."""
    out.mkdir(parents=True, exist_ok=True)
    x = inputs.build(cfg)
    s = cop.series(x, cfg)
    lo, hi = milp.plant_bounds(x, cfg)             # availability statistics need the full year, not the window
    for g in milp.PLANTS:
        x[f"lo_{g}"], x[f"hi_{g}"] = lo[g], hi[g]
    f = C.parse_code(code)
    fl = milp.Flags(f["A"], f["B"], f["TES"])
    rng = (np.random.default_rng(cfg["solver"]["random_seed"]) if noise == "stream" else int(cfg["solver"]["random_seed"]))
    dm = DemandModel(x) if demand_fc.startswith("model") else None
    modes = [a_mode] if a_mode else ["schedule_known_day_ahead", "persistence"]
    res = {}
    for md in modes:
        t0 = time.time()
        T = len(x)
        e = 0.0
        classes = cfg["tes"].get("model") == "classes"
        tbs = [int(t) for t in cfg["tes"].get("classes_C", [])]
        ek = np.zeros(len(tbs))
        if classes and tbs:
            ek[-1] = e
        e_init_top = e
        rows, wins = [], []
        for i0 in range(0, T, commit_h):
            i1 = min(i0 + window_h, T)
            xf = _forecast(x, i0, i1, md, sigma, rng, price_fc, demand_fc, dm)
            sf = s.iloc[i0:i1]
            cw = None
            if cuts:
                cw = [{**c, "t": c["t"] - i0} for c in cuts if i0 <= c["t"] < i1]
            e0 = (ek.copy() if classes else e) if fl.TES else None
            ev = et = None
            if fl.TES and terminal == "mc":
                ev = _terminal_value(x, cfg, i0, i1, price_fc, lookahead_h)
            if fl.TES and terminal == "guide" and guide is not None and i1 < T:
                et = (guide[[f"E_class_{tk}" for tk in tbs]].iloc[i1].to_numpy() if classes else float(guide["E"].iat[i1]))
            m = milp.build(xf, sf, cfg, fl, e0=e0, cyclic=False, cuts=cw, end_value=ev, end_target=et)
            info = milp.solve(m, cfg)
            wins.append({"i0": i0, "hours": i1 - i0, **{k: info[k] for k in ("status", "objective", "bound", "gap", "runtime_s")}})
            plan = milp.extract(m, xf, sf, cfg).iloc[:commit_h]
            xa, sa = x.iloc[i0:i0 + len(plan)], s.iloc[i0:i0 + len(plan)]
            # --- realisation of the committed central decisions
            r = plan.copy()
            cops = {"grid": sa["COP_grid"], "tes": sa["COP_tes"], "casc_grid": sa["COP_mid"], "casc_tes": sa["COP_mid"]}
            need_src = plan[[f"Q_src_{k}" for k in milp.HP_MODES]].sum(axis=1).to_numpy()
            fac = np.where(need_src > 1e-9, np.minimum(1.0, xa["Q_A_avail"].to_numpy() / np.maximum(need_src, 1e-9)), 1.0)
            for k in milp.HP_MODES:
                r[f"Q_HP_{k}"] = plan[f"Q_HP_{k}"].to_numpy() * fac
                r[f"P_HP_{k}"] = r[f"Q_HP_{k}"] / cops[k]
                r[f"Q_src_{k}"] = r[f"Q_HP_{k}"] * (1 - 1 / cops[k])
            r["Q_EB_boost_grid"] = sa["r_grid"].fillna(0).to_numpy() * r["Q_HP_casc_grid"]
            r["Q_EB_boost_tes"] = sa["r_tes"].fillna(0).to_numpy() * r["Q_HP_casc_tes"]
            eb_eta = cfg["electrode_boiler"]["eta"]
            r["P_EB"] = (plan["Q_EB_grid"] + plan["Q_EB_tes"] + r["Q_EB_boost_grid"] + r["Q_EB_boost_tes"]) / eb_eta
            E = np.zeros(len(r))
            qdis = plan["Q_dis"].to_numpy().copy()
            lo_h = cfg["tes"]["loss_per_h"]
            if classes and fl.TES:                   # per-class realisation
                qsrc = (r["Q_HP_tes"] + r["Q_HP_casc_tes"] + r["Q_EB_boost_tes"] + plan["Q_EB_tes"]).to_numpy()
                for h in range(len(r)):
                    E[h] = ek.sum()
                    for j, tk in enumerate(tbs):
                        r.iat[h, r.columns.get_loc(f"E_class_{tk}")] = ek[j]
                        inflow = plan[f"ch_class_{tk}"].iat[h] + (qsrc[h] if j == len(tbs) - 1 else 0.0)
                        avail = ek[j] * (1 - lo_h) + inflow
                        d = min(plan[f"dis_class_{tk}"].iat[h], max(avail, 0.0))
                        r.iat[h, r.columns.get_loc(f"dis_class_{tk}")] = d
                        ek[j] = max(avail - d, 0.0)
                qdis = r[[f"dis_class_{tk}" for tk in tbs]].sum(axis=1).to_numpy()
                e = float(ek.sum())
            for k in range(len(r) if not (classes and fl.TES) else 0):
                E[k] = e
                qch = (plan["Q_ch_grid"].iat[k] + r["Q_HP_tes"].iat[k] + r["Q_HP_casc_tes"].iat[k] + r["Q_EB_boost_tes"].iat[k]
                       + plan["Q_EB_tes"].iat[k])
                emax = float(sa["E_max"].iat[k]) if fl.TES else 0.0
                qdis[k] = min(qdis[k], max(e * (1 - lo_h) + qch, 0.0))
                e = min(max(e * (1 - lo_h) + qch - qdis[k], 0.0), emax)
            r["Q_dis"], r["E"] = qdis, E
            r["Q_ch"] = (r["Q_ch_grid"] + r["Q_HP_tes"] + r["Q_HP_casc_tes"] + r["Q_EB_boost_tes"] + r["Q_EB_tes"])
            r["Q_central"] = (r["Q_HP_grid"] + (1 + sa["r_grid"].fillna(0).to_numpy()) * r["Q_HP_casc_grid"] + r["Q_EB_grid"]
                              + r["Q_dis"] - r["Q_ch_grid"])
            q = _merit_order(xa, cfg, xa["D"].to_numpy() - r["Q_central"].to_numpy())
            for j, g in enumerate(milp.PLANTS):
                r[f"Q_{g}"] = q[:, j]
            rows.append(r)
        sched = pd.concat(rows)
        # recompute cost columns with actual data
        cost = milp.plant_costs(x, cfg)
        for g in milp.PLANTS:
            sched[f"C_{g}"] = cost[g] * sched[f"Q_{g}"]
        hp, eb = cfg["heat_pump"], cfg["electrode_boiler"]
        sched["P_HP"] = sched[[f"P_HP_{k}" for k in milp.HP_MODES]].sum(axis=1)
        sched["Q_HP"] = sched[[f"Q_HP_{k}" for k in milp.HP_MODES]].sum(axis=1)
        sched["Q_src_used"] = sched[[f"Q_src_{k}" for k in milp.HP_MODES]].sum(axis=1)
        sched["Q_A_avail"] = x["Q_A_avail"]
        sched["C_HP"] = (x["price"] + hp["c_el_var_eur_MWh"]) * sched["P_HP"] + hp["pi_source_eur_MWh"] * sched["Q_src_used"]
        sched["C_EB"] = milp.eb_heat_price(x, cfg) * eb["eta"] * sched["P_EB"]
        c_tot = float(sched[[f"C_{g}" for g in milp.PLANTS] + ["C_HP", "C_EB"]].sum().sum())
        if eb["demand_charge"] == "full":
            c_tot += eb["demand_charge_eur_per_MW_a"] * sched["P_EB"].max() * len(x) / 8760
        info = {"objective": c_tot, "status": "rolling_horizon", "runtime_s": time.time() - t0, "bound": np.nan, "gap": np.nan}
        met = metrics.annual(sched, x, s, cfg, info)
        met["TES"]["rh_soc_start_MWh"] = float(e_init_top) if fl.TES else 0.0
        met["TES"]["rh_soc_end_MWh"] = float(ek.sum() if classes else e) if fl.TES else 0.0
        met["TES"]["rh_soc_end_top_MWh"] = float(ek[-1]) if (fl.TES and classes) else None
        d = out / f"{code}-{tag}_{md}"
        d.mkdir(parents=True, exist_ok=True)
        sched.to_parquet(d / "milp_timeseries.parquet")
        pd.DataFrame(wins).to_csv(d / "window_solver.csv", index=False)       # achieved MIP gap per window
        (d / "annual_metrics.json").write_text(json.dumps(met, indent=1, default=float))
        res[md] = met
        print(f"RH {code}-{tag} {md}: cost {c_tot:.0f} EUR, {time.time() - t0:.0f} s, SOC {met['TES']['rh_soc_start_MWh']:.1f} -> "
              f"{met['TES']['rh_soc_end_MWh']:.1f} MWh", flush=True)
    return res


def load_cuts(path: Path) -> list[dict]:
    from .coupling import VARS
    if not path.exists() or path.stat().st_size < 2:      # converged without cuts (no hydraulic violation)
        return []
    c = pd.read_csv(path)
    return [{"t": int(r["t"]), "a": {v: float(r[f"a_{v}"]) for v in VARS}, "rhs": float(r["rhs"])} for _, r in c.iterrows()]


def run_all(cfg: dict, out: Path) -> dict:
    """RH Mode E for both partner-A forecast modes; RH Mode H (day-ahead schedule known) with the converged PF cuts."""
    res = {"E": run(cfg, out)}
    cuts_file = C.root() / cfg["paths"]["results"] / "scenario_runs" / "F111-H" / cfg["hydraulics"]["reference_variant"] / "cuts.csv"
    if cuts_file.exists():
        res["H"] = run(cfg, out, a_mode="schedule_known_day_ahead", cuts=load_cuts(cuts_file), tag="H")
    return res


def run_tes_values(cfg: dict, out: Path) -> pd.DataFrame:
    """TES value under rolling horizon (partner-A schedule known): F110 and F001 references and the A1 size grid
    for F111. V_TES,RH = C_RH(F110) − C_RH(F111, size). Results: <out>/tes_values_rh.csv."""
    from . import sensitivity
    mode = "schedule_known_day_ahead"
    ref = {}
    for code in ("F110", "F001", "F000"):
        d = out / f"{code}-E_{mode}" / "annual_metrics.json"
        ref[code] = (json.loads(d.read_text()) if d.exists() else run(cfg, out, a_mode=mode, code=code)[mode])["cost_total_EUR"]
    rows = []
    for name, ov, _scen, _h in sensitivity.cases(cfg, "A1"):
        if name == "V0":
            continue
        o = out / "A1" / name
        d = o / f"F111-E_{mode}" / "annual_metrics.json"
        c = json.loads(d.read_text())["cost_total_EUR"] if d.exists() else run(C.merge(cfg, ov), o, a_mode=mode)[mode]["cost_total_EUR"]
        rows.append({"case": name, "V_m3": ov["tes.volume_m3"], "Q_MW": ov["tes.Q_dis_max_MW"], "C_RH_F111": c,
                     "V_TES_RH_EUR": ref["F110"] - c})
    t = pd.DataFrame(rows)
    t.attrs = {}
    t["C_RH_F110"], t["C_RH_F001"], t["C_RH_F000"] = ref["F110"], ref["F001"], ref["F000"]
    t.to_csv(out / "tes_values_rh.csv", index=False)
    return t


def run_factorial_rh(cfg: dict, out: Path) -> dict:
    """All eight factorial scenarios under RH (partner-A schedule known day-ahead) and the Shapley values under RH."""
    from .metrics import shapley
    mode = "schedule_known_day_ahead"
    cost = {}
    for code in ("F000", "F001", "F100", "F010", "F110", "F101", "F011", "F111"):
        d = out / f"{code}-E_{mode}" / "annual_metrics.json"
        cost[code] = (json.loads(d.read_text()) if d.exists() else run(cfg, out, a_mode=mode, code=code)[mode])["cost_total_EUR"]
    res = shapley(cost)
    (out / "shapley_rh.json").write_text(json.dumps({"cost": cost, **res}, indent=1, default=float))
    return res


def run_robustness(cfg: dict, out: Path) -> pd.DataFrame:
    """RH robustness of the TES value: noise seeds 1/2/3 at σ = 5 % and σ = 10 / 15 % (seed 1234), F110 and F111,
    partner-A schedule known. Results: <out>/robustness_rh.csv."""
    mode = "schedule_known_day_ahead"
    rows = []
    for sigma, seed in ((0.05, 1), (0.05, 2), (0.05, 3), (0.10, 1234), (0.15, 1234)):
        c = C.merge(cfg, {"solver.random_seed": seed})
        o = out / "robustness" / f"s{sigma:g}_seed{seed}"
        cost = {}
        for code in ("F000", "F110", "F111"):
            d = o / f"{code}-E_{mode}" / "annual_metrics.json"
            cost[code] = (json.loads(d.read_text()) if d.exists() else run(c, o, a_mode=mode, sigma=sigma, code=code)[mode])["cost_total_EUR"]
        rows.append({"sigma": sigma, "seed": seed, "C_F000": cost["F000"], "C_F110": cost["F110"], "C_F111": cost["F111"],
                     "v_F111": cost["F000"] - cost["F111"], "V_TES": cost["F110"] - cost["F111"]})
    t = pd.DataFrame(rows)
    t.to_csv(out / "robustness_rh.csv", index=False)
    return t


def run_at_values(cfg: dict, out: Path) -> pd.DataFrame:
    """Atmospheric-tank set AT under RH (partner-A schedule known): V_TES,RH = C_RH(F110) − C_RH(F111, AT case).
    Results: <out>/at_values_rh.csv."""
    from . import sensitivity
    mode = "schedule_known_day_ahead"
    d = out / f"F110-E_{mode}" / "annual_metrics.json"
    c110 = (json.loads(d.read_text()) if d.exists() else run(cfg, out, a_mode=mode, code="F110")[mode])["cost_total_EUR"]
    rows = []
    for name, ov, _scen, _h in sensitivity.cases(cfg, "AT"):
        o = out / "AT" / name
        f = o / f"F111-E_{mode}" / "annual_metrics.json"
        c = json.loads(f.read_text())["cost_total_EUR"] if f.exists() else run(C.merge(cfg, ov), o, a_mode=mode)[mode]["cost_total_EUR"]
        rows.append({"case": name, "V_m3": ov["tes.volume_m3"], "Q_MW": ov["tes.Q_dis_max_MW"], "C_RH_F111": c, "C_RH_F110": c110,
                     "V_TES_RH_EUR": c110 - c})
    t = pd.DataFrame(rows)
    t.to_csv(out / "at_values_rh.csv", index=False)
    return t


FORESIGHT_CASES = {
    # name: (window_h, price_fc, a_mode, sigma, terminal)
    "ref": (72, "da_repeat", "schedule_known_day_ahead", 0.05, None),
    "ref_w120": (120, "da_repeat", "schedule_known_day_ahead", 0.05, None),
    "ref_w168": (168, "da_repeat", "schedule_known_day_ahead", 0.05, None),
    "ref_tv": (72, "da_repeat", "schedule_known_day_ahead", 0.05, "mc"),
    "ref_w120_tv": (120, "da_repeat", "schedule_known_day_ahead", 0.05, "mc"),
    "ref_guide": (72, "da_repeat", "schedule_known_day_ahead", 0.05, "guide"),
    "sigma0": (72, "da_repeat", "schedule_known_day_ahead", 0.0, None),
    "pprice": (72, "perfect", "schedule_known_day_ahead", 0.05, None),
    "pi": (72, "perfect", "perfect", 0.0, None),
    "pi_w120": (120, "perfect", "perfect", 0.0, None),
    "pi_w168": (168, "perfect", "perfect", 0.0, None),
    "pi_w336": (336, "perfect", "perfect", 0.0, None),
    "pi_tv": (72, "perfect", "perfect", 0.0, "mc"),
    "pi_guide": (72, "perfect", "perfect", 0.0, "guide"),
    "ref_gap": (72, "da_repeat", "schedule_known_day_ahead", 0.05, None),       # MIP gap 1e-5 per window
    "pi_gap": (72, "perfect", "perfect", 0.0, None),
    "ref_c1": (72, "da_repeat", "schedule_known_day_ahead", 0.05, None, 1),     # hourly re-planning (MPC)
    "ref_w336": (336, "da_repeat", "schedule_known_day_ahead", 0.05, None),
    "pi_w720": (720, "perfect", "perfect", 0.0, None),
}


def run_foresight(cfg: dict, out: Path, only: list[str] | None = None) -> pd.DataFrame:
    """Decomposition of the foresight loss of the TES (F110 vs F111): window length, price forecast, demand noise,
    partner-A forecast, terminal value and a perfect-foresight guide curve. Noise per window (seed, window start).
    V_TES = C(F110) − C(F111) under the same forecast settings. Results: <out>/foresight/foresight_rh.csv."""
    root = out / "foresight"
    pf_dir = C.root() / cfg["paths"]["results"] / "scenario_runs"
    guide = pd.read_parquet(pf_dir / "F111-E" / "milp_timeseries.parquet").reset_index(drop=True)
    pf = {c: json.loads((pf_dir / f"{c}-E" / "annual_metrics.json").read_text())["metrics"]["cost_total_EUR"]
          for c in ("F110", "F111")}
    rows = []
    for name, spec in FORESIGHT_CASES.items():
        w, pfc, am, sg, term = spec[:5]
        ch = spec[5] if len(spec) > 5 else COMMIT_H
        if only and name not in only:
            continue
        cost = {}
        c_run = C.merge(cfg, {"solver.mip_rel_gap": 1e-5}) if name.endswith("_gap") else cfg
        for code in ("F110", "F111"):
            key = (f"w{w}_{pfc}_{am}_s{sg:g}" + (f"_{term}" if (term and code == "F111") else "")
                   + ("_gap" if name.endswith("_gap") else "") + (f"_c{ch}" if ch != COMMIT_H else ""))
            d = root / key
            f = d / f"{code}-E_{am}" / "annual_metrics.json"
            if not f.exists():
                run(c_run, d, a_mode=am, sigma=sg, code=code, window_h=w, price_fc=pfc, terminal=term, guide=guide,
                    noise="window", commit_h=ch)
            met = json.loads(f.read_text())
            cost[code] = met["cost_total_EUR"]
            if code == "F111":
                soc_end = met["TES"]["rh_soc_end_MWh"]
                dis = met["TES"]["discharge_GWh"]
        v = cost["F110"] - cost["F111"]
        rows.append({"case": name, "window_h": w, "commit_h": ch, "price_fc": pfc, "a_mode": am, "sigma": sg, "terminal": term or "none",
                     "C_F110": cost["F110"], "C_F111": cost["F111"], "V_TES_RH": v, "V_TES_PF": pf["F110"] - pf["F111"],
                     "share_of_PF": v / (pf["F110"] - pf["F111"]), "TES_dis_GWh": dis, "soc_end_MWh": soc_end})
        pd.DataFrame(rows).to_csv(root / ("foresight_rh.csv" if not only else "foresight_rh_partial.csv"), index=False)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------- realistic demand forecasts
FORECAST_VARIANTS = {"iid_ref": "iid", "A1_model_lomo": "model", "A2_model_wx": "model_wx", "A3_ar1": "ar1",
                     "A4_model_residual": "model_res", "A4b_model_residual_damped": "model_res_damped"}


def forecast_quality(cfg: dict, demand_fc: str, sigma: float = 0.05, window_h: int = WINDOW_H,
                     commit_h: int = COMMIT_H) -> pd.DataFrame:
    """MAPE and nRMSE of the demand forecasts actually used (every window, lead 1–window_h h) by lead day."""
    x = inputs.build(cfg)
    dm = DemandModel(x) if demand_fc.startswith("model") else None
    seed = int(cfg["solver"]["random_seed"])
    D = x["D"].to_numpy(float)
    err, act, lead = [], [], []
    for i0 in range(0, len(x), commit_h):
        i1 = min(i0 + window_h, len(x))
        f = demand_forecast(x, i0, i1, demand_fc, sigma, seed, dm)
        err.append(f - D[i0:i1])
        act.append(D[i0:i1])
        lead.append(np.arange(i1 - i0) // 24 + 1)
    e, a, ld = np.concatenate(err), np.concatenate(act), np.concatenate(lead)
    rows = []
    for name, m in [("day 1", ld == 1), ("day 2", ld == 2), ("day 3", ld == 3), ("all", ld >= 1)]:
        ok = m & (a > 1.0)
        rows.append({"lead": name, "n": int(ok.sum()), "MAPE_pct": float(np.mean(np.abs(e[ok]) / a[ok]) * 100),
                     "nRMSE_pct": float(np.sqrt(np.mean(e[ok] ** 2)) / np.mean(a[ok]) * 100),
                     "bias_pct": float(np.mean(e[ok]) / np.mean(a[ok]) * 100)})
    return pd.DataFrame(rows)


def run_forecast_variants(cfg: dict, out: Path, only: list[str] | None = None,
                          codes: tuple = ("F000", "F110", "F111")) -> pd.DataFrame:
    """RH reference settings with realistic demand forecasts (new result folder; reference results untouched)."""
    mode = "schedule_known_day_ahead"
    rows, q = [], []
    for name, dfc in FORECAST_VARIANTS.items():
        if only and name not in only:
            continue
        o = out / name
        cost, met = {}, {}
        for code in codes:
            d = o / f"{code}-E_{mode}" / "annual_metrics.json"
            m = json.loads(d.read_text()) if d.exists() else run(cfg, o, a_mode=mode, code=code, demand_fc=dfc)[mode]
            cost[code], met[code] = m["cost_total_EUR"], m
        fq = forecast_quality(cfg, dfc)
        fq.insert(0, "variant", name)
        q.append(fq)
        rows.append({"variant": name, "demand_fc": dfc, **{f"C_{c}": cost[c] for c in codes},
                     "V_TES_kEUR": (cost["F110"] - cost["F111"]) / 1e3, "v_F111_kEUR": (cost["F000"] - cost["F111"]) / 1e3,
                     "TES_dis_GWh": met["F111"]["TES"]["discharge_GWh"],
                     "runtime_F111_s": met["F111"].get("solver", {}).get("runtime_s", np.nan)})
    t = pd.DataFrame(rows)
    out.mkdir(parents=True, exist_ok=True)
    t.to_csv(out / ("forecast_variants.csv" if not only else f"forecast_variants_{'_'.join(only)}.csv"), index=False)
    pd.concat(q).to_csv(out / ("forecast_quality.csv" if not only else f"forecast_quality_{'_'.join(only)}.csv"), index=False)
    return t
