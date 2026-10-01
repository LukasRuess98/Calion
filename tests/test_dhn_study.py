"""Tests der Datenanalysen DHN-A (scripts/dhn_study) mit synthetischen Daten."""

import numpy as np
import pandas as pd
import pytest

from scripts.dhn_study import anker, auslegung, daten, hydraulik, wetter
from scripts.dhn_study import netzmodell as nm

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


def test_unbegrenzter_fit_und_ungedeckte_last():
    idx = pd.date_range("2021-10-01", periods=500, freq="D")
    t = pd.Series(RNG.uniform(-12, 11, 500), index=idx)
    bedarf = 130.0 - 7.0 * t + RNG.normal(0, 0.5, 500)
    p = bedarf.where(t >= -3, bedarf - 0.1 * (bedarf - (130 + 21)))         # Kappung unter −3 °C
    begrenzt = auslegung.fit_last_temperatur(p, t)
    frei = auslegung.fit_last_temperatur(p, t, t_min=0.0, ferien=True)
    assert frei["koeff"][1] == pytest.approx(-7.0, abs=0.1)
    assert begrenzt["koeff"][1] > frei["koeff"][1] + 0.2                    # Gerade über alle Tage zu flach
    assert auslegung.last_bei(frei, -14.0)[0] == pytest.approx(130 + 7 * 14, abs=2.0)
    u = auslegung.ungedeckte_last(p, t, frei)
    assert (u["Differenz_MW"] < 0).all() and u["Differenz_MW"].is_monotonic_increasing
    assert u.loc["(-20, -8]", "Differenz_MW"] < -3.0


def test_dp_aus_pumpe():
    assert hydraulik.dp_aus_pumpe(73.5, 120.0, 1.1) == pytest.approx(943.1 * 9.81 * 73.5 / 1e5 - 1.1, abs=0.01)


def test_ost_kopplung_und_grenze():
    n = 3000
    dp_k = pd.Series(RNG.uniform(1.5, 3.5, n))
    m_o, m_k = pd.Series(RNG.uniform(150, 450, n)), pd.Series(RNG.uniform(20, 300, n))
    dp_o = dp_k + 0.5 + 0.3 * (m_o / 100) ** 2 - 0.2 * (m_k / 100) ** 2
    f = hydraulik.fit_ost_kopplung(dp_o, dp_k, m_o, m_k)
    assert (f["c"], f["d"], f["f"]) == pytest.approx((0.5, 0.3, 0.2), abs=1e-6)
    g = hydraulik.kwk_grenze_ost(f, 400.0, 200.0, dp_ost_max=7.5)
    assert hydraulik.ost_dp(f, g, 400.0, 200.0) == pytest.approx(7.5, abs=1e-9)
    assert hydraulik.m_ost_max(f, g, 200.0, dp_ost_max=7.5) == pytest.approx(400.0, abs=1e-6)
    # Entlastung durch ṁ_KWK wird konservativ nicht über das P99 hinaus extrapoliert
    assert hydraulik.kwk_grenze_ost(f, 400.0, 900.0) == pytest.approx(hydraulik.kwk_grenze_ost(f, 400.0, f["m_kwk_p99"]))
    assert hydraulik.kwk_grenze_ost(f, 400.0, 900.0, konservativ=False) > hydraulik.kwk_grenze_ost(f, 400.0, 900.0)


def test_regelgesetz_sued_und_ausbaureserve():
    n = 3000
    F, h, ps = pd.Series(RNG.uniform(1, 3.5, n)), pd.Series(RNG.uniform(0, 150, n)), pd.Series(RNG.uniform(0, 1.8, n))
    dp_k = 2.0 + 0.2 * F**2 - 1.0 * h / 100 - 0.4 * ps
    f = hydraulik.fit_regelgesetz_sued(dp_k, F, h, ps)
    assert (f["a"], f["b"], f["g"], f["h"]) == pytest.approx((2.0, 0.2, 1.0, 0.4), abs=1e-6)
    mitte = {"a": 0.12, "b": 0.14}
    r = hydraulik.ausbaureserve(mitte, f, 250.0, 61.0, 4.0, 150.0, 1.7)
    assert r["gesamt"] == min(r["Mitte"], r["Süd"])
    P_s = 250.0 * (1 + r["Süd"])
    assert hydraulik.erforderliche_dp_sued(f, P_s, 61.0, 150.0, 1.7) == pytest.approx(4.0, abs=1e-9)


def test_aktive_grenzen():
    idx = pd.date_range("2025-01-01", periods=2000, freq="h")
    ta = pd.Series(RNG.uniform(-8, 10, 2000), index=idx)
    x = pd.DataFrame({"dp_ost": 7.6, "dp_kwk": 3.0, "dp_sued": 1.1, "dp_mitte": 1.8, "gt_an": True}, index=idx)
    g = hydraulik.aktive_grenzen(x, ta)
    assert g["Stunden"].sum() == 2000 and (g["Ost-Δp ≥ 7.5 bar [%]"] == 100).all() and (g["Süd ≤ 1.1 bar [%]"] == 100).all()
    assert (g["Mitte ≤ 1,2 bar [%]"] == 0).all()


def test_tagesprofile_und_ueberschuss():
    idx = pd.date_range("2021-02-01", periods=24 * 10, freq="h")               # Mo 01.02. bis Mi 10.02.
    form = 1 + 0.2 * np.sin(np.arange(24) / 24 * 2 * np.pi)
    p = pd.Series(np.tile(form, 10) * 200.0, index=idx)
    t = pd.Series(-5.0, index=pd.date_range("2021-02-01", periods=10, freq="D"))
    prof = auslegung.tagesprofile(p, t)
    assert prof.shape == (8, 24) and np.allclose(prof.mean(axis=1), 1.0)       # Wochenende ausgeschlossen
    u = auslegung.ueberschuss(prof, 100.0, 110.0)
    ex = np.clip(form / form.mean() * 100 - 110, 0, None)
    assert u["Energie Median [MWh]"] == pytest.approx(ex.sum()) and u["Leistung Median [MW]"] == pytest.approx(ex.max())


def test_verbundlast_west_eigen():
    assert auslegung.verbundlast_west_eigen(200.0, 30.0, 40.0, 1.14) == 200.0                 # Kessel decken die Spitze
    p = auslegung.verbundlast_west_eigen(200.0, 40.0, 40.0, 1.15)
    assert p * 1.15 == pytest.approx(200.0 * 1.15 + (40.0 * 1.15 - 40.0))                    # nur Spitze über 40 MW


def test_sektoren_summen():
    s = daten.lade_sektoren()
    verbund, west = s[~s.section.str.startswith("W")], s[s.section.str.startswith("W")]
    assert verbund.connected_MW.sum() == pytest.approx(392.0, abs=0.15)
    assert west.connected_MW.sum() == pytest.approx(75.8, abs=0.15)
    regionen_kunden = {r.split(" (")[0] for r in daten.lade_verbraucher().region}
    assert regionen_kunden <= set(s.region)                                                  # gleiche Regionsnamen


def test_regelpunkt_signatur_erkennt_geregelten_punkt():
    rng = np.random.default_rng(7)
    n = 3000
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    last = pd.Series(10 + 3 * np.sin(np.arange(n) / 30) + rng.normal(0, 0.3, n), index=idx)
    stoer = pd.Series(np.cumsum(rng.normal(0, 0.02, n)), index=idx)          # langsame Netzstörung
    regel = 1.2 + rng.normal(0, 0.02, n)                                        # eng geregelt
    quelle = pd.Series(1.2 + 0.1 * last.to_numpy() + stoer.to_numpy(), index=idx)  # Quelle wird nachgeführt
    frei = 0.9 * quelle - 0.08 * last + 0.6 + rng.normal(0, 0.02, n)            # folgt der Quelle
    dp = pd.DataFrame({"R": regel, "F": frei}, index=idx)
    s = hydraulik.regelpunkt_signatur(dp, quelle, last)
    assert abs(s.loc["R", "Durchgriff"]) < 0.1 and s.loc["F", "Durchgriff"] > 0.7
    assert s.loc["R", "Std [bar]"] < s.loc["F", "Std [bar]"] and s.loc["R", "Anteil Minimum"] > 0.5


def test_netz_zugehoerigkeit_und_entlastung():
    rng = np.random.default_rng(8)
    n = 2000
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    a, b = pd.Series(np.cumsum(rng.normal(0, 0.1, n)), index=idx), pd.Series(np.cumsum(rng.normal(0, 0.1, n)), index=idx)
    st = {"X": a + rng.normal(0, 0.02, n), "Y": b + rng.normal(0, 0.02, n)}
    z = hydraulik.netz_zugehoerigkeit(st, {"KWK": a, "West": b})
    assert z.loc["X", "Netz"] == "KWK" and z.loc["Y", "Netz"] == "West"
    assert hydraulik.entlastung_kwk(0.5, 0.5, 200.0) == pytest.approx(2.0)


# ---------------------------------------------------------------- Netzmodell

def _klein():
    """Wurzel R, Masche über A und B, radialer Ast nach C mit Pumpe."""
    kn = ["R", "A", "B", "C"]
    ka = [("e1", "R", "A", 300, 1000), ("e2", "R", "B", 300, 1000), ("e3", "B", "A", 300, 500), ("e4", "A", "C", 200, 800)]
    return nm.Netz(kn, ka, wurzel="R")


def test_netz_massenbilanz_und_maschen():
    nz = _klein()
    assert np.abs(nz.C @ nz.A.T).max() == 0
    rng = np.random.default_rng(3)
    b = np.zeros((50, 4))
    b[:, 1:] = -rng.uniform(10, 100, (50, 3))                       # Entnahmen, Wurzel gleicht aus
    K = np.array([2e-5, 3e-5, 1e-5, 5e-5])
    g = np.zeros((50, 4))
    g[:, 3] = 0.5                                                   # Pumpe im radialen Ast
    m = nz.loese(b, K, g)
    b_voll = b.copy()
    b_voll[:, 0] = -b[:, 1:].sum(axis=1)
    assert np.abs(m @ nz.A.T + b_voll).max() < 1e-8                 # Knotenbilanz
    assert np.abs((K * m * np.abs(m) - g) @ nz.C.T).max() < 1e-6    # Maschengleichung


def test_netz_parallelzweige_und_druckpfad():
    nz = _klein()
    K = np.array([4e-5, 1e-5, 1e-5, 2e-5])                          # e1 parallel zu (e2 + e3)
    b = np.array([[0.0, -100.0, 0.0, -20.0]])
    m = nz.loese(b, K)[0]
    assert m[0] + m[2] == pytest.approx(120.0)
    assert K[0] * m[0] ** 2 == pytest.approx((K[1] + K[2]) * m[1] ** 2, rel=1e-6)
    g = np.array([[0.0, 0.0, 0.0, 0.3]])
    dp = nz.dp_knoten(nz.loese(b, K, g), K, np.array([3.0]), g)[0]
    assert dp[1] == pytest.approx(3.0 - K[0] * m[0] ** 2)
    assert dp[3] == pytest.approx(dp[1] - K[3] * 20.0**2 + 0.3)


def test_hebel_koeffizienten():
    rng = np.random.default_rng(4)
    n = 800
    X = np.cumsum(rng.normal(0, 1, (n, 2)), axis=0)
    Y = np.c_[0.4 * X[:, 0] - 0.2 * X[:, 1], 1.5 * X[:, 1]] + rng.normal(0, 0.01, (n, 2))
    zeilen = np.ones((n - 1, 2), bool)
    k = nm._hebel_koeff(Y, np.diff(X, axis=0), zeilen)
    assert k == pytest.approx(np.array([[0.4, -0.2], [0.0, 1.5]]), abs=0.02)


def test_kalibrierung_reproduziert_synthetische_messung():
    nz = nm.netz()
    rng = np.random.default_rng(5)
    B, N, E = 120, len(nz.knoten), len(nz.kanten)
    b_fix = np.zeros((B, N))
    for k, (lo, hi) in {"MVA": (100, 180), "GT": (0, 130), "BIO": (40, 60), "HW1": (0, 120), "HW2": (-60, -10)}.items():
        b_fix[:, nz.idx[k]] = rng.uniform(lo, hi, B)
    rest = rng.uniform(300, 700, B)
    idx = pd.date_range("2025-01-01", periods=B, freq="h")
    gew = np.zeros((B, E))
    gew[:, nz.kanten_ids.index("L4c")] = rng.uniform(0, 1.5, B)
    leer = pd.DataFrame(index=idx)
    f0 = nm.Fall(b_fix, rest, np.zeros(B, bool), gew, rng.uniform(2.0, 3.5, B), leer, idx)
    K_true = nz.k0 * np.exp(rng.normal(0, 0.3, E))
    ziele = nm.simuliere(nz, f0, K_true, {s: 0.05 for s in nm.STATIONEN})
    f = nm.Fall(b_fix, rest, np.zeros(B, bool), gew, f0.dp_kwk, ziele, idx)
    kal = nm.kalibriere(nz, f, max_nfev=40)
    sim = nm.simuliere(nz, f, kal["K"], kal["versatz"].to_dict(), kal["gewichte"], kal["grundlast"])
    g = nm.guete(sim, ziele)
    assert g.loc[[s for s in nm.STATIONEN], "RMSE"].max() < 0.05


def test_erforderliche_kwk_dp_haelt_mindestwerte():
    nz = nm.netz()
    b = nm.auslegungs_einspeisung(nz, 240.0, 255.0, {"MVA": 40, "GT": 31, "BIO": 13}, 40.0, 150.0)
    g = np.zeros((1, len(nz.kanten)))
    mindest = {"V06": 1.2, "V03": 1.0, "V22": 1.0}
    req, _ = nm.erforderliche_kwk_dp(nz, nz.k0, b, g, mindest)
    dp = nz.dp_knoten(nz.loese(b, nz.k0, g), nz.k0, req, g)[0]
    reserve = [dp[nz.idx[nm.ZIEL_KNOTEN[z]]] - v for z, v in mindest.items()]
    assert min(reserve) == pytest.approx(0.0, abs=1e-9) and all(r > -1e-9 for r in reserve)
