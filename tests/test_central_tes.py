"""Tests for the central-TES study model (spec section 12). Run: python -m pytest -o addopts="" tests/test_central_tes.py

The tests use a 96-hour winter window of the 2025 inputs. Partner-A availability is replaced by a synthetic profile so
that the tests do not depend on the local (confidential) partner file.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.dhn_study.central_tes import config as C
from scripts.dhn_study.central_tes import cop, coupling, inputs, metrics, milp
from scripts.dhn_study.central_tes.hydraulics import Hydro

TOL = 1e-5


@pytest.fixture(scope="module")
def setup():
    cfg = C.load(overrides={"solver.mip_rel_gap": 1e-6, "tes.T_set_strategy": "daily"})
    x_full = inputs.build(cfg)
    x = x_full.loc["2025-01-13":"2025-01-16"].copy()
    rng = np.random.default_rng(0)
    x["Q_A_avail"] = np.clip(3 + 3 * rng.standard_normal(len(x)), 0, None)
    x["T_source"] = 18.0
    x["price"] = x["price"] - 200 * (x.index.hour.isin([12, 13, 14]))           # cheap hours to trigger the EB
    s = cop.series(x, cfg)
    fl = milp.Flags(True, True, True)
    m = milp.build(x, s, cfg, fl, cyclic=True)
    info = milp.solve(m, cfg)
    sched = milp.extract(m, x, s, cfg)
    return cfg, x_full, x, s, fl, m, info, sched


def test_solved(setup):
    *_, info, sched = setup
    assert "optimal" in info["status"]
    assert sched["Q_HP"].sum() > 0 and sched["P_EB"].sum() > 0 and sched["Q_dis"].sum() > 0


def test_heat_balance(setup):
    cfg, _, x, s, fl, m, info, sched = setup
    supply = sched[[f"Q_{g}" for g in milp.PLANTS]].sum(axis=1) + sched["Q_central"]
    assert np.allclose(supply, x["D"], atol=1e-4)
    central = (sched["Q_HP_grid"] + sched["Q_HP_casc_grid"] + sched["Q_EB_boost_grid"] + sched["Q_EB_grid"]
               + sched["Q_dis"] - sched["Q_ch_grid"])
    assert np.allclose(central, sched["Q_central"], atol=1e-4)


def test_storage_bounds_and_exclusivity(setup):
    cfg, _, x, s, fl, m, info, sched = setup
    assert (sched["E"] >= -TOL).all() and (sched["E"] <= sched["E_max"] + TOL).all()
    assert not ((sched["Q_ch"] > 1e-4) & (sched["Q_dis"] > 1e-4)).any()
    lo = cfg["tes"]["loss_per_h"]
    assert np.allclose(sched["E_end"], sched["E"] * (1 - lo) + sched["Q_ch"] - sched["Q_dis"], atol=1e-4)
    assert abs(sched["E_end"].iloc[-1] - sched["E"].iloc[0]) < 1e-4        # cyclic


def test_source_limit(setup):
    *_, sched = setup
    assert (sched["Q_src_used"] <= sched["Q_A_avail"] + TOL).all()


def test_hp_modes_and_cascade(setup):
    cfg, _, x, s, fl, m, info, sched = setup
    cops = {"grid": s["COP_grid"], "tes": s["COP_tes"], "casc_grid": s["COP_mid"], "casc_tes": s["COP_mid"]}
    for md in milp.HP_MODES:
        assert np.allclose(sched[f"Q_HP_{md}"], cops[md] * sched[f"P_HP_{md}"], atol=1e-6)
    on = (sched[[f"Q_HP_{md}" for md in milp.HP_MODES]] > 1e-4).sum(axis=1)
    assert (on <= 1).all()
    assert (sched["Q_HP"] <= cfg["heat_pump"]["Q_max_MW"] + TOL).all()
    assert np.allclose(sched["Q_EB_boost_grid"], s["r_grid"].fillna(0) * sched["Q_HP_casc_grid"], atol=1e-6)
    assert np.allclose(sched["Q_EB_boost_tes"], s["r_tes"].fillna(0) * sched["Q_HP_casc_tes"], atol=1e-6)
    t_mid = cfg["heat_pump"]["cascade"]["T_mid_C"]
    assert (sched.loc[x["T_VL"] <= t_mid, "Q_HP_casc_grid"] < 1e-6).all()
    assert (sched.loc[s["T_set"] <= t_mid, "Q_HP_casc_tes"] < 1e-6).all()


def test_electrode_boiler(setup):
    cfg, _, x, s, fl, m, info, sched = setup
    eb = cfg["electrode_boiler"]
    assert (sched["P_EB"] <= eb["P_max_MW"] + TOL).all()
    heat = sched["Q_EB_grid"] + sched["Q_EB_tes"] + sched["Q_EB_boost_grid"] + sched["Q_EB_boost_tes"]
    assert np.allclose(heat, eb["eta"] * sched["P_EB"], atol=1e-5)


def test_masks_and_link(setup):
    cfg, _, x, s, fl, m, info, sched = setup
    assert (sched.loc[~s["mask_dis"], "Q_dis"] < 1e-6).all()
    assert (sched.loc[~s["mask_ch_grid"], "Q_ch_grid"] < 1e-6).all()
    assert (sched["Q_central"].abs() <= s["link_cap"] + TOL).all()


def test_inputs_alignment(setup):
    cfg, x_full, *_ = setup
    assert x_full.index.is_unique and x_full.index.is_monotonic_increasing
    for c in ("D", "T_VL", "T_RL", "price", "Q_A_avail", "T_source", "dh"):
        assert x_full[c].notna().all(), c
    if x_full.index[0] <= pd.Timestamp("2025-01-01") and x_full.index[-1] >= pd.Timestamp("2025-12-31 23:00"):
        assert len(x_full) == 8759                                         # DST: 30.03 02:00 missing, 26.10 double hour merged
    else:                                                                  # shorter data set (e.g. the synthetic example)
        assert len(x_full) == int((x_full.index[-1] - x_full.index[0]) / pd.Timedelta(hours=1)) + 1 \
            - int((x_full.index[0] < pd.Timestamp("2025-03-30 02:00")) & (x_full.index[-1] > pd.Timestamp("2025-03-30 02:00")))
    assert pd.Timestamp("2025-03-30 02:00") not in x_full.index


def test_temperature_order(setup):
    cfg, x_full, x, s, *_ = setup
    assert (x_full["T_RL"] < x_full["T_VL"]).all()
    assert (x_full["T_source"] < x_full["T_RL"]).all()
    assert (s["T_set"] > cfg["tes"]["T_low_C"]).all()


def test_cop_formula():
    c = cop.cop_carnot_fraction(100.0, 20.0, 0.5, 5.0, 7.0)
    ts, tq = 373.15 + 5, 293.15 - 5
    assert np.isclose(c, 0.5 * ts / (ts - tq))
    assert cop.cop_carnot_fraction(30.0, 29.0, 0.9, 0.0, 7.0) == 7.0


def test_hydraulics_mass_balance_and_mapping(setup):
    from scripts.dhn_study import netzmodell as nm
    cfg, x_full, *_ = setup
    hy = Hydro(cfg, x_full, "A")
    sched = hy._sched_measured()
    b = hy.injections(sched)
    r = hy._model(sched)
    # node balance A·m = −b for every non-root node, root balances the rest
    resid = hy.nz.A @ r["m"].T + b.T
    nr = [i for i, k in enumerate(hy.nz.knoten) if k != hy.nz.wurzel]
    assert np.abs(resid[nr]).max() < 1e-6
    # loop equations converged
    h, _ = nm.verlust(r["m"], hy.K)
    assert np.abs((h - hy.gain) @ hy.nz.C.T).max() < 1e-5
    # the measured dispatch is feasible with the envelope-anchored pump curves
    ev = hy.evaluate(sched)
    assert ev["violation"].sum() == 0
    assert set(hy.nz.knoten) >= {"S", "MVA", "GT", "BIO", "HW1", "HW2", "KWK"}


def test_mode_h_cuts_respected(setup):
    cfg, x_full, x, s, fl, m, info, sched = setup
    # a synthetic violation: demand a cut that lowers the east output in the first hour
    cut = {"t": 0, "a": {"MVA": 1.0, "GT": 1.0, "BIO": 1.0}, "rhs": float(sched[["Q_MVA", "Q_GT", "Q_BIO"]].iloc[0].sum() - 5.0)}
    m2 = milp.build(x, s, cfg, fl, cyclic=True, cuts=[cut])
    milp.solve(m2, cfg)
    s2 = milp.extract(m2, x, s, cfg)
    assert s2[["Q_MVA", "Q_GT", "Q_BIO"]].iloc[0].sum() <= cut["rhs"] + 1e-5


def test_redispatch_keeps_balance(setup):
    cfg, x_full, x, s, fl, m, info, sched = setup
    lo, hi = milp.plant_bounds(x, cfg)
    cols = coupling._sched_cols(sched)
    rows = np.arange(len(cols))
    r = coupling.redispatch(cols, rows, 0.5 * cols["Q_central"].to_numpy(), hi, lo)
    assert np.allclose(r.sum(axis=1), cols.sum(axis=1), atol=1e-6)


def test_shapley_efficiency():
    costs = {"F000": 100.0, "F001": 98.0, "F100": 95.0, "F010": 99.0, "F110": 93.0, "F101": 92.0, "F011": 96.0, "F111": 88.0}
    sh = metrics.shapley(costs)
    assert np.isclose(sh["sum_phi"], 12.0)
    assert np.isclose(sh["tes_interaction"], 12.0 - 7.0 - 2.0)


def test_temperature_classes(setup):
    """Volume limit of the class model and the class rules (charge only with hotter network water, discharge only from
    classes at least as hot as the network supply)."""
    cfg, _, x, s, fl, m, info, sched = setup
    assert cfg["tes"]["model"] == "classes"
    assert (sched["V_used_m3"] <= cfg["tes"]["volume_m3"] + 1e-4).all()
    import pyomo.environ as pyo
    tb = cfg["tes"]["classes_C"]
    for k, t_k in enumerate(tb):
        ch = np.array([pyo.value(m.chb[k, t]) for t in range(len(x))])
        dis = np.array([pyo.value(m.disb[k, t]) for t in range(len(x))])
        assert (ch[x["T_VL"].to_numpy() < t_k] < 1e-6).all()
        assert (dis[x["T_VL"].to_numpy() > t_k] < 1e-6).all()


def test_node_of_station_alias():
    from scripts.dhn_study import netzmodell as nm
    from scripts.dhn_study.central_tes.hydraulics import node_of
    assert node_of("S") == "S"
    assert node_of("station:V06") == nm.STATIONEN["V06"]


def test_rh_price_forecast_no_lookahead():
    """Price forecast of the rolling horizon uses only prices known at the decision hour (day-ahead auction at 12:00)."""
    import numpy as np
    import pandas as pd
    from scripts.dhn_study.central_tes.rolling import _price_forecast
    x = pd.DataFrame({"price": np.arange(240.0)})
    for i0 in (0, 5, 13, 23, 48):
        known_end = (i0 // 24 + 1) * 24 + (24 if i0 % 24 >= 13 else 0)      # first hour not yet auctioned
        f = _price_forecast(x, i0, 72, "da_repeat")
        assert f.max() < known_end                                         # never a price from an unknown hour
        assert np.allclose(f[: known_end - i0], x["price"].to_numpy()[i0:known_end])
    assert np.allclose(_price_forecast(x, 0, 72, "perfect"), np.arange(72.0))


def test_unserved_mode_hosting():
    """Hosting-capacity mode: no new capacity; NEW is unserved heat ≤ the new customers' demand, priced with the
    penalty, without a capacity variable, and it reduces the withdrawal at the south nodes in the hydraulics."""
    cfg = C.load(overrides={"inputs.expansion": {"share": 0.3, "region": "south"}, "new_boiler.enabled": True,
                            "new_boiler.mode": "unserved", "new_boiler.unserved_penalty_eur_MWh": 1000.0})
    assert milp.unserved_mode(cfg)
    full = inputs.build(cfg)
    x = full.loc["2025-01-13":"2025-01-14"].copy()
    lo, hi = milp.plant_bounds(x, cfg)
    assert np.allclose(hi["NEW"].to_numpy(), x["D_extra"].to_numpy())
    assert np.allclose(milp.plant_costs(x, cfg)["NEW"].to_numpy(), 1000.0)
    s = cop.series(x, cfg)
    m = milp.build(x, s, cfg, milp.Flags(False, False, False))
    assert not hasattr(m, "Cnew")
    milp.solve(m, cfg)
    sched = milp.extract(m, x, s, cfg)
    assert (sched["Q_NEW"] <= x["D_extra"] + 1e-6).all()
    hy = Hydro(cfg, full, "A")
    base = pd.DataFrame(0.0, index=full.index, columns=[f"Q_{g}" for g in milp.PLANTS] + ["Q_central", "Q_tes_ext"])
    base["Q_KWK"] = full["D"]
    b0 = hy.injections(base)
    b1s = base.copy()
    b1s["Q_NEW"] = 5.0
    b1s["Q_KWK"] -= 5.0
    b1 = hy.injections(b1s)
    idx = [hy.nz.idx[k] for k in hy.south_w]
    mf = 1e3 / hy.dh
    assert np.allclose((b1 - b0)[:, idx].sum(axis=1), 5.0 * mf, rtol=1e-6)     # south withdrawal shrinks by 5 MW


def test_dispatch_comparison_gleiche_bewertung_regel_uc():
    """Kraftwerkseinsatz-Vergleich: ein MILP-Fahrplan, als „IST“ bewertet, ergibt exakt die MILP-Zielfunktion (eine
    Kostenlogik); die Regel deckt die Last in den Modellgrenzen; die Zerlegung ist additiv; UC hält Mindestlasten."""
    from scripts.dhn_study.central_tes import dispatch_comparison as dc

    cfg = C.load(overrides={"solver.mip_rel_gap": 1e-6})
    x = inputs.build(cfg).loc["2025-01-13":"2025-01-16"].copy()
    s = cop.series(x, cfg)
    sched, info, _ = dc.milp_f000(x, s, cfg)
    k = dc.kosten(sched, x, cfg)
    assert k["gesamt"].sum() == pytest.approx(info["objective"], rel=1e-9)
    teile = [f"{g}_{c}" for g in milp.EXISTING for c in ("brennstoff", "co2", "steuer", "stromerloes")]
    assert k[teile].to_numpy().sum() == pytest.approx(info["objective"], rel=1e-9)
    r = dc.regel(x, cfg)
    lo, hi = milp.plant_bounds(x, cfg)
    assert np.allclose(r[[f"Q_{g}" for g in milp.EXISTING]].sum(axis=1), x["D"], atol=1e-6)
    for g in milp.EXISTING:
        assert (r[f"Q_{g}"] <= hi[g] + 1e-6).all() and (r[f"Q_{g}"] >= lo[g] - 1e-6).all()
    kr = dc.kosten(r, x, cfg)
    assert kr["gesamt"].sum() >= info["objective"] - 1e-6                  # das LP-Optimum ist nie teurer als die Regel
    z = dc.zerlegung(r, sched, kr, k)
    assert z["Wert [M€/a]"].sum() * 1e6 == pytest.approx(k["gesamt"].sum() - kr["gesamt"].sum(), abs=1.0)
    ml = {"KWK": 20.0, "GT": 5.0, "HW1": 2.0}
    su, iu = dc.milp_uc(x, s, cfg, ml, dc.ANFAHRKOSTEN_EUR, {g: False for g in ml})
    for g, pm in ml.items():
        q = su[f"Q_{g}"]
        assert ((q < 1e-6) | (q >= pm - 1e-6)).all()
    assert iu["objective"] >= info["objective"] - 1e-6
    ku = dc.kosten(su, x, cfg)                    # Zielfunktion = Betrieb + Anfahrkosten + Notkühlungsstrafe
    assert (ku["gesamt"] + ku["anfahrkosten"] + ku["notkuehlung_strafe"]).sum() == pytest.approx(iu["objective"], rel=1e-6)
    assert ku["anfahrkosten"].sum() == pytest.approx(sum(dc.ANFAHRKOSTEN_EUR[g] * su[f"start_{g}"].sum() for g in ml), rel=1e-9)
