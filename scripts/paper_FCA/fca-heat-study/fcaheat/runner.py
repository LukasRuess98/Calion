"""Batch execution, derived KPIs, contract-space and sensitivity studies."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CFG, ECON, OUT_DIR, get_solver
from .data import Inputs
from .model import Case, solve_case


def run_batch(inp: Inputs, sites=None, scenarios=None, fcas=None, years=None,
              resolution=None, overrides=None, tag="main", store_ts=True, verbose=True,
              intensive=False):
    sites = sites or list(inp.sites["site_id"])
    scenarios = scenarios or CFG["scenarios"]
    fcas = fcas or CFG["fcas"]
    years = tuple(years or CFG["years"])
    resolution = resolution or CFG["resolution"]
    opt = get_solver()
    rows, store = [], {}
    for s in sites:
        for sc in scenarios:
            # the gas baseline does not depend on the connection regime -> run it once
            regimes = ["FCA_FIRM"] if sc == "S0_BASE" else fcas
            for fc in regimes:
                case = Case(site=s, scenario=sc, fca=fc, years=years, resolution=resolution,
                            overrides=overrides or {})
                out = (solve_intensive_two_pass(inp, case, opt) if intensive
                       else solve_case(inp, case, opt))
                rows.append(out["kpi"])
                if store_ts:
                    store[(s, sc, fc)] = out["ts"]
                if verbose:
                    k = out["kpi"]
                    print(f"  {s:8s} {sc:11s} {fc:16s} peak={k['peak_grid_MW']:6.2f} "
                          f"TES={k['Etes_MWh']:6.1f} BES={k['Ebes_MWh']:6.1f} "
                          f"unserved={k['unserved_MWh']+k['unserved_el_MWh']:8.1f} "
                          f"({k['runtime_s']:.1f}s)")
    kpi = pd.DataFrame(rows)
    kpi.to_csv(OUT_DIR / f"kpi_{tag}.csv", index=False)
    if store_ts:
        pd.to_pickle(store, OUT_DIR / f"ts_{tag}.pkl")
    return kpi, store


def solve_intensive_two_pass(inp: Inputs, case: Case, opt=None):
    """§ 19 Abs. 2 S. 2 StromNEV as a two-pass fixed point, not an LP binary (rule 6).

    Pass 1 sizes the plant at the standard capacity charge and checks whether the resulting draw
    qualifies as intensive network use (≥ 7,000 utilisation hours and ≥ 10 GWh/a). If it does,
    pass 2 re-solves with the individual-charge discount applied — which, by making capacity
    cheaper, can only weaken the incentive to peak-shave, so an eligible pass-1 solution stays
    eligible; the second check confirms it rather than iterating further. Returns the final `out`
    dict with `kpi['intensive_applied']` and `kpi['intensive_two_pass']` set."""
    opt = opt or get_solver()
    out = solve_case(inp, case, opt)
    out["kpi"]["intensive_two_pass"] = False
    out["kpi"]["intensive_applied"] = False
    if not out["kpi"].get("intensive_eligible"):
        return out
    disc = ECON["intensive_discount_max"]
    case2 = Case(site=case.site, scenario=case.scenario, fca=case.fca, years=case.years,
                 resolution=case.resolution, seed=case.seed, fixed_sizes=case.fixed_sizes,
                 overrides={**case.overrides, "ECON.intensive_discount": disc})
    out2 = solve_case(inp, case2, opt)
    out2["kpi"]["intensive_two_pass"] = True
    out2["kpi"]["intensive_applied"] = bool(out2["kpi"].get("intensive_eligible"))
    return out2


def add_relative_kpis(kpi: pd.DataFrame) -> pd.DataFrame:
    k = kpi.copy()
    base = k[k["scenario"] == "S0_BASE"].drop_duplicates("site").set_index("site")
    for src, dst in [("CO2_cert_t", "CO2_cert_base_t"), ("CO2_phys_t", "CO2_phys_base_t"),
                     ("cost_total_EUR", "cost_base_EUR"), ("peak_grid_MW", "peak_base_MW")]:
        k[dst] = k["site"].map(base[src])
    k["dCO2_cert_t"] = k["CO2_cert_base_t"] - k["CO2_cert_t"]
    k["dCO2_phys_t"] = k["CO2_phys_base_t"] - k["CO2_phys_t"]
    k["CO2_red_pct"] = 100 * k["dCO2_phys_t"] / k["CO2_phys_base_t"]
    k["dcost_EUR"] = k["cost_total_EUR"] - k["cost_base_EUR"]
    k["LCOH_EUR_MWh"] = k["dcost_EUR"] / k["E_heat_MWh"].replace(0, np.nan)
    k["abatement_EUR_t"] = k["dcost_EUR"] / k["dCO2_phys_t"].replace(0, np.nan)
    k["uplift_pct"] = 100 * (k["peak_grid_MW"] / k["P_grid_exist_MW"] - 1)
    k["unserved_total_MWh"] = k["unserved_MWh"] + k["unserved_el_MWh"]
    k["feasible"] = k["unserved_total_MWh"] < 1e-3
    k["unserved_share_pct"] = 100 * k["unserved_MWh"] / k["E_heat_MWh"].replace(0, np.nan)
    k["price_advantage_pct"] = 100 * (1 - k["avg_price_EUR_MWh"] / k["mean_price_EUR_MWh"])
    # storage needed per MW of avoided firm capacity, relative to the upgrade case
    up = k[k["fca"] == "FCA_UPGRADE"].set_index(["site", "scenario"])["peak_grid_MW"]
    k["peak_upgrade_MW"] = k.set_index(["site", "scenario"]).index.map(up)
    k["avoided_firm_MW"] = k["peak_upgrade_MW"] - k["P_grid_exist_MW"]
    k["TES_per_avoided_MW"] = k["Etes_MWh"] / k["avoided_firm_MW"].replace(0, np.nan)
    return k


def _unserved(inp, site, scenario, fca, overrides, opt, years=None, resolution=None):
    c = Case(site=site, scenario=scenario, fca=fca, overrides=overrides,
             years=tuple(years or CFG["years"]), resolution=resolution or CFG["resolution"])
    k = solve_case(inp, c, opt)["kpi"]
    return k["unserved_MWh"] + k["unserved_el_MWh"], k


def find_min_flex(inp: Inputs, site: str, scenario: str, fca: str = "FCA_WINDOW",
                  lo=1.0, hi=2.5, tol=0.02, years=None, resolution=None):
    """Smallest P_flex_rel scaling at which the configuration supplies 100 % of the heat."""
    opt = get_solver()
    f = lambda x: _unserved(inp, site, scenario, fca, {"fca.P_flex_rel": float(x)}, opt,
                            years, resolution)[0]
    if f(hi) > 1e-3:
        return np.nan
    if f(lo) <= 1e-3:
        return lo
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if f(mid) > 1e-3:
            lo = mid
        else:
            hi = mid
    return hi


def find_max_restriction(inp: Inputs, site: str, scenario: str, fca: str = "FCA_WINDOW",
                         lo=0.0, hi=16.0, tol=0.5, years=None, resolution=None):
    """Widest restriction block [h per working day] the configuration can still absorb."""
    opt = get_solver()
    f = lambda x: _unserved(inp, site, scenario, fca, {"fca.window_width": float(x)}, opt,
                            years, resolution)[0]
    if f(lo) > 1e-3:
        return np.nan
    if f(hi) <= 1e-3:
        return hi
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if f(mid) > 1e-3:
            hi = mid
        else:
            lo = mid
    return lo


def run_contract_space(inp: Inputs, sites=None, scenarios=("S2_TES", "S3_BES", "S4_TES_BES"),
                       fca: str = "FCA_WINDOW"):
    rows = []
    for s in (sites or list(inp.sites["site_id"])):
        for sc in scenarios:
            mf = find_min_flex(inp, s, sc, fca=fca)
            mr = find_max_restriction(inp, s, sc, fca=fca)
            rows.append(dict(site=s, scenario=sc, min_P_flex_rel=mf, max_restriction_h=mr))
            print(f"  {s:8s} {sc:11s} min P_flex = {mf if mf==mf else float('nan'):.2f} x P_exist"
                  f"   max restriction = {mr if mr==mr else float('nan'):.1f} h/working day")
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "contract_space.csv", index=False)
    return df


def run_seed_robustness(inp: Inputs, sites=None, scenario: str = "S4_TES_BES",
                        fcas=("FCA_DYNAMIC", "FCA_TDTR"), n_seeds: int = 12, base_seed: int = 0,
                        years=None, resolution=None, tag="seed_robustness", verbose=True):
    """F19: re-solve the operator-called (dynamic) regimes over many call seeds.

    The dynamic results rest on a price-percentile proxy for when the operator curtails; this
    sweep shows the required storage is a property of the regime, not of one lucky call pattern.
    Only `dynamic`-type regimes consume the seed — `window`/`firm` ignore it — so pass only those."""
    sites = sites or list(inp.sites["site_id"])
    years = tuple(years or CFG["years"])
    resolution = resolution or CFG["resolution"]
    opt = get_solver()
    rows = []
    for s in sites:
        for fc in fcas:
            for j in range(n_seeds):
                seed = base_seed + j
                case = Case(site=s, scenario=scenario, fca=fc, years=years,
                            resolution=resolution, seed=seed)
                k = solve_case(inp, case, opt)["kpi"]
                rows.append(dict(site=s, scenario=scenario, fca=fc, seed=seed,
                                 Etes_MWh=k["Etes_MWh"], Ebes_MWh=k["Ebes_MWh"],
                                 unserved_MWh=k["unserved_MWh"] + k["unserved_el_MWh"],
                                 restricted_share=k["restricted_share"],
                                 restriction_bite_share=k["restriction_bite_share"]))
            if verbose:
                d = [r["Etes_MWh"] for r in rows if r["site"] == s and r["fca"] == fc]
                print(f"  {s:8s} {fc:12s} TES over {n_seeds} seeds: "
                      f"{np.min(d):.1f}–{np.max(d):.1f} MWh (median {np.median(d):.1f})")
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / f"{tag}_{scenario}.csv", index=False)
    return df


def run_contract_grid(inp: Inputs, sites=None, scenario: str = "S4_TES_BES",
                      fca: str = "FCA_WINDOW", n_width: int = 8, n_beta: int = 6,
                      width_range=(0.0, 16.0), beta_range=(1.0, 2.0),
                      years=None, resolution=None, tag="contract_grid", verbose=True):
    """2-D sweep for F11: restriction width per working day × granted uplift β.

    For each cell it solves the sizing LP and records whether the design supplies 100 % of the
    heat (feasibility) and how much thermal storage it needs. β is the *effective* flex level
    b/P_exist, obtained by scaling the sheet's `P_flex_rel` — so the y-axis reads as a contract
    term regardless of the workbook's base value. ~n_width×n_beta solves per site."""
    sites = sites or list(inp.sites["site_id"])
    years = tuple(years or CFG["years"])
    resolution = resolution or CFG["resolution"]
    base_flex = float(inp.fca.set_index("fca_id").loc[fca, "P_flex_rel"])
    widths = np.linspace(*width_range, n_width)
    betas = np.linspace(*beta_range, n_beta)
    opt = get_solver()
    rows = []
    for s in sites:
        for w in widths:
            for b in betas:
                ov = {"fca.window_width": float(w), "fca.P_flex_rel": float(b / base_flex)}
                case = Case(site=s, scenario=scenario, fca=fca, years=years,
                            resolution=resolution, overrides=ov)
                k = solve_case(inp, case, opt)["kpi"]
                unserved = k["unserved_MWh"] + k["unserved_el_MWh"]
                rows.append(dict(site=s, scenario=scenario, fca=fca,
                                 window_width_h=float(w), beta=float(b),
                                 unserved_MWh=unserved, feasible=unserved < 1e-3,
                                 Etes_MWh=k["Etes_MWh"], Ebes_MWh=k["Ebes_MWh"]))
        if verbose:
            nf = sum(r["feasible"] for r in rows if r["site"] == s)
            print(f"  {s:8s} {scenario:11s} {fca:12s} {nf}/{n_width*n_beta} cells feasible")
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / f"{tag}_{scenario}_{fca}.csv", index=False)
    return df


def run_sensitivity_grid(inp: Inputs, site: str, scenario: str = "S4_TES_BES",
                         fca: str = "FCA_WINDOW",
                         target_a: str = "TES.capex_EUR_per_MWh",
                         target_b: str = "market.da_price_spread",
                         values_a=None, values_b=None, n=6,
                         years=None, resolution=None, tag="sensgrid", verbose=True):
    """Two-way sensitivity for F15. Solves the sizing LP on a `target_a` × `target_b` grid of
    overrides and records the storage split, so the figure can show where BES stops losing to TES.
    Defaults to the interacting pair called out in FIGURES.md: TES CAPEX × day-ahead price spread."""
    values_a = np.linspace(0.5, 2.0, n) if values_a is None else np.asarray(values_a)
    values_b = np.linspace(0.5, 1.75, n) if values_b is None else np.asarray(values_b)
    years = tuple(years or CFG["years"])
    resolution = resolution or CFG["resolution"]
    opt = get_solver()
    rows = []
    for va in values_a:
        for vb in values_b:
            ov = {target_a: float(va), target_b: float(vb)}
            case = Case(site=site, scenario=scenario, fca=fca, years=years,
                        resolution=resolution, overrides=ov)
            k = solve_case(inp, case, opt)["kpi"]
            tot = k["Etes_MWh"] + k["Ebes_MWh"]
            rows.append(dict(site=site, scenario=scenario, fca=fca,
                             a=float(va), b=float(vb), target_a=target_a, target_b=target_b,
                             Etes_MWh=k["Etes_MWh"], Ebes_MWh=k["Ebes_MWh"],
                             bes_share=(k["Ebes_MWh"] / tot if tot > 1e-9 else 0.0),
                             cost_total_EUR=k["cost_total_EUR"]))
        if verbose:
            print(f"  {target_a}={va:.2f} row done ({len(values_b)} cols)")
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / f"{tag}_{site}_{scenario}.csv", index=False)
    return df


def run_year_validation(inp: Inputs, sites=None, scenario: str = "S4_TES_BES",
                        fca: str = "FCA_WINDOW", design_year=None, operation_years=None,
                        resolution=None, tag="year_validation", verbose=True):
    """F20: size on one design year, then operate the fixed design over the other years.

    Answers the reviewer question "what if you had sized on a different year?". Sizes are frozen
    from the design-year solve via `Case.fixed_sizes`; each year is then re-solved with the sizes
    fixed, so unserved energy and peak are the operation outcome of that one design."""
    sites = sites or list(inp.sites["site_id"])
    all_years = sorted(inp.el.index.year.unique().tolist())
    design_year = design_year or all_years[len(all_years) // 2]
    operation_years = operation_years or all_years
    resolution = resolution or CFG["resolution"]
    opt = get_solver()
    rows = []
    for s in sites:
        design = solve_case(inp, Case(site=s, scenario=scenario, fca=fca,
                                      years=(design_year,), resolution=resolution), opt)["kpi"]
        sizes = {"Qhp": design["Qhp_MW"], "Peb": design["Peb_MW"],
                 "Etes": design["Etes_MWh"], "Ebes": design["Ebes_MWh"]}
        for y in operation_years:
            k = solve_case(inp, Case(site=s, scenario=scenario, fca=fca, years=(y,),
                                     resolution=resolution, fixed_sizes=sizes), opt)["kpi"]
            rows.append(dict(site=s, scenario=scenario, fca=fca, year=y,
                             role="design" if y == design_year else "operation",
                             design_year=design_year,
                             unserved_MWh=k["unserved_MWh"] + k["unserved_el_MWh"],
                             unserved_share_pct=100 * k["unserved_MWh"]
                             / max(k["E_heat_MWh"], 1e-9),
                             peak_grid_MW=k["peak_grid_MW"]))
        if verbose:
            u = [r["unserved_MWh"] for r in rows if r["site"] == s]
            print(f"  {s:8s} design {design_year} -> operate {operation_years}: "
                  f"unserved {min(u):.1f}-{max(u):.1f} MWh")
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / f"{tag}_{scenario}_{fca}.csv", index=False)
    return df


def run_sensitivity_oat(inp: Inputs, site: str, scenario: str, fca: str = "FCA_WINDOW",
                        params=None, years=None, resolution="1h", tag="oat", n_steps=None):
    sens = inp.sensitivity.copy()
    if params:
        sens = sens[sens["param_id"].isin(params)]
    else:
        # drop parameters that cannot act on this LP:
        #   ECON.co2*   -> only affects the gas baseline
        #   fca.notice_h-> only affects the MPC (see mpc.run_mpc_all_sites(notices=...))
        sens = sens[~sens["target"].str.startswith("ECON.co2")]
        sens = sens[sens["target"] != "fca.notice_h"]
    rows = []
    opt = get_solver()
    for _, p in sens.iterrows():
        vals = np.linspace(p["low"], p["high"], int(n_steps or p["n_steps"]))
        for val in vals:
            ov = {p["target"]: float(val if p["mode"] == "absolute" else val)}
            case = Case(site=site, scenario=scenario, fca=fca,
                        years=tuple(years or CFG["years"]), resolution=resolution, overrides=ov)
            out = solve_case(inp, case, opt)
            k = out["kpi"]; k.update(param_id=p["param_id"], value=float(val),
                                     base=float(p["base"]), mode=p["mode"])
            rows.append(k)
        print(f"  {p['param_id']:16s} done ({len(vals)} runs)")
    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / f"sensitivity_{tag}_{site}_{scenario}_{fca}.csv", index=False)
    return df
