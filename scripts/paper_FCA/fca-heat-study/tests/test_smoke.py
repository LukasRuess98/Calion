"""Fast tests. Run with `pytest -q`. The full-solve test takes ~20 s."""
import numpy as np
import pandas as pd
import pytest

from fcaheat import CFG, Case, build_grid_limit, load_inputs, solve_case
from fcaheat.config import ECON
from fcaheat.data import annuity, parse_int_list
from fcaheat.runner import solve_intensive_two_pass


@pytest.fixture(scope="session")
def inp():
    return load_inputs()


def test_workbook_loads_and_validates(inp):
    assert len(inp.sites) >= 1
    assert {"FCA_FIRM", "FCA_WINDOW", "FCA_DYNAMIC", "FCA_TDTR"} <= set(inp.fca["fca_id"])
    assert inp.el.index.equals(inp.heat.index)


def test_grid_connection_is_historical_max(inp):
    for s in inp.sites["site_id"]:
        row = inp.sites.set_index("site_id").loc[s]
        assert np.isclose(row["P_grid_exist_MW"], inp.el[s].max())


def test_parse_int_list():
    assert parse_int_list("7,8,9") == [7, 8, 9]
    assert parse_int_list("") == []
    assert parse_int_list(np.nan) == []


def test_annuity():
    assert annuity(1000, 10, 0.0) == pytest.approx(100.0)
    assert annuity(1000, 20, 0.06) == pytest.approx(87.18, abs=0.5)


@pytest.mark.parametrize("fca_id", ["FCA_FIRM", "FCA_STATIC", "FCA_WINDOW", "FCA_DYNAMIC",
                                    "FCA_TDTR"])
def test_limit_shape(inp, fca_id):
    idx = inp.el.index[inp.el.index.year == 2024]
    price = inp.market.loc[idx, "da_price_EUR_per_MWh"].to_numpy()
    lim, free, restr, row = build_grid_limit(inp, fca_id, idx, 10.0, price, 0.25)
    assert len(lim) == len(idx) and lim.min() > 0
    assert not free


def test_tdtr_restricts_about_15_percent(inp):
    """Regression guard for the call-budget bug: the annual budget must be pro-rated by the
    horizon, not by the number of calendar years."""
    idx = inp.el.index[inp.el.index.year == 2024]
    price = inp.market.loc[idx, "da_price_EUR_per_MWh"].to_numpy()
    _, _, restr, _ = build_grid_limit(inp, "FCA_TDTR", idx, 10.0, price, 0.25)
    assert 0.13 < restr.mean() < 0.17

    one_month = idx[idx.month == 1]                      # sub-year horizon
    p2 = inp.market.loc[one_month, "da_price_EUR_per_MWh"].to_numpy()
    _, _, restr2, _ = build_grid_limit(inp, "FCA_TDTR", one_month, 10.0, p2, 0.25)
    assert 0.10 < restr2.mean() < 0.20, "call budget not pro-rated by horizon length"


def test_window_matches_contract(inp):
    idx = inp.el.index[inp.el.index.year == 2024]
    price = inp.market.loc[idx, "da_price_EUR_per_MWh"].to_numpy()
    _, _, restr, _ = build_grid_limit(inp, "FCA_WINDOW", idx, 10.0, price, 0.25)
    r = pd.Series(restr, index=idx)
    work = idx.dayofweek < 5
    assert r[work & (idx.hour == 8)].all()          # inside the morning block, working days
    assert r[work & (idx.hour == 15)].all()         # inside the afternoon block
    assert not r[idx.hour == 3].any()               # night is free
    assert not r[work & (idx.hour == 11)].any()     # the gap between the two blocks is free
    assert not r[idx.dayofweek == 6].any()          # sunday is free


def test_solve_runs_and_respects_the_limit(inp):
    CFG.update(years=[2024], months=[1], resolution="1h")
    out = solve_case(inp, Case(site=inp.sites["site_id"].iloc[0], scenario="S2_TES",
                               fca="FCA_WINDOW"))
    ts, k = out["ts"], out["kpi"]
    assert (ts["grid"] <= ts["P_limit"] + 1e-6).all(), "FCA limit violated"
    assert k["Etes_MWh"] > 0
    assert k["unserved_MWh"] >= 0


def test_connection_shadow_price_extracted(inp):
    """F16 guard: the connection-constraint dual must load through the IPM/no-crossover solver
    and be non-negative where the limit binds. A regime that binds must have a positive total."""
    CFG.update(years=[2024], months=[1], resolution="1h")
    out = solve_case(inp, Case(site=inp.sites["site_id"].iloc[0], scenario="S4_TES_BES",
                               fca="FCA_WINDOW"))
    sp = out["ts"]["shadow_conn_EUR_MW"]
    assert np.isfinite(sp.to_numpy()).any(), "no connection duals were loaded"
    assert (sp.dropna() >= -1e-6).all(), "shadow price should be reported as a magnitude"
    assert out["kpi"]["shadow_conn_EUR_MW"] > 0, "the window limit binds, so capacity has value"


def test_intensive_network_use_post_hoc(inp):
    """§ 19 Abs. 2 S. 2: eligibility is reported every solve, the discount floors the capacity
    charge to (1 - discount) of standard, and the two-pass driver reports its flags. The check
    must never turn the LP into a MILP (rule 6) — so it is pure post-processing + a re-solve."""
    CFG.update(years=[2024], months=[1], resolution="1h")
    site = inp.sites["site_id"].iloc[0]
    base = solve_case(inp, Case(site=site, scenario="S4_TES_BES", fca="FCA_WINDOW"))["kpi"]
    for key in ("util_hours_h", "annual_energy_GWh", "intensive_eligible"):
        assert key in base, f"post-hoc KPI {key} missing"
    assert base["util_hours_h"] > 0

    disc = ECON["intensive_discount_max"]
    d = solve_case(inp, Case(site=site, scenario="S4_TES_BES", fca="FCA_WINDOW",
                             overrides={"ECON.intensive_discount": disc}))["kpi"]
    assert d["cost_capacity_EUR"] == pytest.approx((1 - disc) * base["cost_capacity_EUR"], rel=1e-6)

    out = solve_intensive_two_pass(inp, Case(site=site, scenario="S4_TES_BES", fca="FCA_WINDOW"))
    assert "intensive_two_pass" in out["kpi"] and "intensive_applied" in out["kpi"]
