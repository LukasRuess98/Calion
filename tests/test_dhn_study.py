"""Tests der Datenanalysen DHN-A (scripts/dhn_study) mit synthetischen Daten."""

import numpy as np
import pandas as pd
import pytest

from scripts.dhn_study import anker, auslegung, daten, wetter

RNG = np.random.default_rng(1)


def test_identische_signale_findet_kopie():
    idx = pd.date_range("2025-01-01", periods=1000, freq="h")
    a = RNG.normal(size=1000)
    df = pd.DataFrame({"gt_heat": a, "hx_heat": a.copy(), "X": a + 1e-3}, index=idx)
    assert daten.identische_signale(df) == [("gt_heat", "hx_heat", 1000)]


def test_einheitentest_erkennt_t_pro_h():
    n = 500
    tv, tr = RNG.uniform(90, 120, n), RNG.uniform(50, 60, n)
    v = RNG.uniform(50, 300, n)                                   # t/h
    q = v / 3.6 * daten.dh(tv, tr) / 1e3                          # MW
    r = daten.einheitentest(pd.Series(q), pd.Series(v), pd.Series(tv), pd.Series(tr))
    assert r["t/h"] == pytest.approx(1.0, abs=1e-9)
    assert r["m3/h@VL"] > 1.03


def test_parse_produkt_zeitbezug():
    text = ("STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU;eor\n"
            "232;1990010110;5;-1.0;80;eor\n"                     # MEZ, Winter → Ortszeit 10:00
            "232;2025070110;5;20.0;50;eor\n"                     # UTC, Sommer → Ortszeit 12:00
            "232;2025010110;5;-999;50;eor\n")                    # Fehlwert
    s = wetter.parse_produkt(text)
    assert s.loc["1990-01-01 10:00"] == -1.0
    assert s.loc["2025-07-01 12:00"] == 20.0
    assert np.isnan(s.loc["2025-01-01 11:00"])


def test_lastregression_und_band():
    t = pd.Series(RNG.uniform(-10, 11, 400), index=pd.date_range("2021-01-01", periods=400, freq="D"))
    p = 130.0 - 6.5 * t + RNG.normal(0, 1.0, 400)
    f = auslegung.fit_last_temperatur(p, t)
    assert f["koeff"][1] == pytest.approx(-6.5, abs=0.1)
    p50, p90 = auslegung.last_bei(f, -14.0)
    assert p50 == pytest.approx(130 + 6.5 * 14, abs=2.0)
    assert p90 > p50


def test_ausrichtung_schaltjahr():
    idx = pd.date_range("2020-01-01", periods=8760, freq="h")
    tt = pd.Series(10 * np.sin(np.arange(366) / 9.0), index=pd.date_range("2020-01-01", periods=366, freq="D"))
    werte = (150 - 6 * tt.reindex(idx.floor("D")).to_numpy())
    r = auslegung.pruefe_ausrichtung(werte, 2020, tt)
    assert r["fortlaufend"] < r["ohne 29.02."]


def test_verlustgesetz_und_reserve_konsistent():
    n = 3000
    P, dT = RNG.uniform(30, 180, n), RNG.uniform(40, 60, n)
    kunde = pd.Series(RNG.uniform(1.2, 2.0, n))
    dp = kunde + 0.12 + 0.14 * (P / dT) ** 2
    f = anker.fit_verlustgesetz(pd.Series(dp), kunde, pd.Series(P), pd.Series(dT))
    assert f["a"] == pytest.approx(0.12, abs=1e-6) and f["b"] == pytest.approx(0.14, abs=1e-6)
    g = anker.ausbaureserve(f, 250.0, 61.0, dp_grenze=4.0)
    assert anker.erforderliche_dp(f, 250.0 * (1 + g), 61.0) == pytest.approx(4.0, abs=1e-9)


def test_netzhebel_findet_koeffizient():
    n = 2000
    x = pd.DataFrame({"inj": np.cumsum(RNG.normal(0, 1, n)), "dp": np.cumsum(RNG.normal(0, 0.1, n))})
    y = 0.3 * x.inj + 0.8 * x.dp + RNG.normal(0, 0.01, n)
    t = anker.netzhebel({"st": y}, x, max_sprung=10)
    assert t.loc[0, "inj"] == pytest.approx(0.3, abs=0.01)
    assert t.loc[0, "dp"] == pytest.approx(0.8, abs=0.05)


def test_tracer_anteil_und_lag():
    n = 1500
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    ta = pd.Series(110 + RNG.normal(0, 1, n), index=idx)
    tb = pd.Series(110 + 8 * np.sign(np.sin(np.arange(n) / 7)), index=idx)
    ts = (ta + 0.6 * (tb - ta) - 1.0).shift(1)
    r = anker.tracer_anteil(ts, ta, tb)
    assert r["lag_h"] == 1 and r["anteil"] == pytest.approx(0.6, abs=0.02)


def test_erzeugung_gt_quellen_und_summen():
    n = 600
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    dp = RNG.uniform(3, 7, n)
    tv = RNG.uniform(90, 120, n)
    tr = np.full(n, 60.0)
    q_gt = -5 + 2.0 * dp + 0.3 * (tv - tr)
    v_gt = q_gt / (daten.dh(tv, tr) / 1e3) * 3.6
    v_gt[400:500] = np.nan                                          # läuft, nicht gemessen → imputiert
    tv_gt = tv.copy()
    tv_gt[500:] = 40.0                                              # Stillstand
    v_gt[500:] = np.nan
    m = pd.DataFrame({"gas_turbine_flow": v_gt, "gas_turbine_T_supply": tv_gt, "gas_turbine_T_return": tr,
                      "gas_turbine_p_supply": 8 + dp, "gas_turbine_p_return": np.full(n, 8.0),
                      "gas_CHP_heat": 50.0, "waste_incineration_heat": 40.0, "biomass_CHP_heat": 14.0,
                      "boiler_plant_1_flow": 100.0, "boiler_plant_1_T_supply": 110.0, "boiler_plant_1_T_return": 60.0,
                      "boiler_plant_2_hx_heat": 10.0, "boiler_plant_2_secondary_heat": 25.0}, index=idx)
    e = daten.erzeugung(m)
    assert set(e.gt_quelle[400:500]) == {"imputiert"} and set(e.gt_quelle[500:]) == {"stillstand"}
    assert e["gas_turbine"][500:].eq(0).all()
    assert np.allclose(e["gas_turbine"][400:500], q_gt[400:500], atol=1e-6)
    hw1 = 100 / 3.6 * daten.dh(110, 60) / 1e3
    assert np.allclose(e["verbund"], 104 + e["gas_turbine"] + hw1) and np.allclose(e["gesamt"] - e["verbund"], 15.0)


def test_kunden_dp_aus_diffdruck_und_vl_rl():
    idx = pd.date_range("2025-01-01", periods=3, freq="h")
    m = pd.DataFrame({"V06_dp": [1.0, 1.1, 0.0], "V24_p_supply": [9.4, 9.5, 9.6], "V24_p_return": [7.6, 7.6, 7.6],
                      "waste_incineration_dp": [4.0, 4.0, 4.0], "boiler_plant_2_hx_dp": [1.4, 1.5, 1.6]}, index=idx)
    k = daten.kunden_dp(m)
    assert set(k.columns) == {"V06", "V24", "HX_West"} and np.isnan(k.V06.iloc[2])
    assert k.V24.round(2).tolist() == [1.8, 1.9, 2.0]
