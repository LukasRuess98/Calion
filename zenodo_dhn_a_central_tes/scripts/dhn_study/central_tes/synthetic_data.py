"""SYNTHETIC example data set in the schema of ``data/dhn_a`` (for running the pipeline without the NDA data).

Everything written here is generated from simple parametric formulas and a fixed random seed. Nothing is derived from
measured data, operator plans or partner data: the outdoor temperature is a sine + AR(1) noise, demand a heating-degree
model, the dispatch a fixed merit order, pressures smooth functions of the flows, prices a daily/seasonal pattern with
noise, partner A a weekday/shift profile. Numbers are only roughly in the range of a city network of the paper's size;
the results of a synthetic run must not be compared with the paper.

    python -m scripts.dhn_study.central_tes.synthetic_data [--out data/synthetic] [--seed 2025]

Files (same names and columns as the real data set; see ``docs/input_data_schema.md``):
``measurements_2025_hourly.parquet``, ``ambient_temperature_hourly.parquet``, ``ambient_temperature_daily.csv``,
``plants.yaml``, ``sectors.csv``, ``consumers.csv``, ``prices/raw_2025.json``, ``partner_a_2023.csv``, ``grid_co2_2025.csv``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .. import daten
from .. import netzmodell as nm

TZ = "Europe/Berlin"
YEAR = 2025
LABEL = "SYNTHETIC EXAMPLE DATA - not measured, not derived from measurements; for testing the pipeline only"


def local_index(year: int) -> pd.DatetimeIndex:
    """Naive local hourly index like the measurement set: spring DST hour missing, October double hour merged."""
    utc = pd.date_range(f"{year - 1}-12-31 22:00", f"{year}-12-31 23:00", freq="h", tz="UTC")
    loc = utc.tz_convert(TZ).tz_localize(None)
    loc = loc[(loc.year == year)]
    return pd.DatetimeIndex(loc.unique(), name="time_local")


def _ar1(rng, n: int, phi: float, sd: float) -> np.ndarray:
    e = rng.normal(0.0, sd * np.sqrt(1 - phi**2), n)
    out = np.empty(n)
    out[0] = rng.normal(0.0, sd)
    for i in range(1, n):
        out[i] = phi * out[i - 1] + e[i]
    return out


def ambient(rng, idx: pd.DatetimeIndex) -> pd.Series:
    doy = idx.dayofyear.to_numpy()
    h = idx.hour.to_numpy()
    t = 9.5 - 10.5 * np.cos(2 * np.pi * (doy - 20) / 365.25) + 3.5 * np.sin(2 * np.pi * (h - 9) / 24)
    return pd.Series(t + _ar1(rng, len(idx), 0.985, 3.0), index=idx, name="T_ambient")


def dh(tv, tr):
    return daten.dh(tv, tr)                      # kJ/kg


def measurements(rng, idx: pd.DatetimeIndex, ta: pd.Series) -> pd.DataFrame:
    n = len(idx)
    tad = ta.groupby(idx.date).transform("mean").to_numpy()
    h = idx.hour.to_numpy()
    # network temperatures (heating curve + noise)
    tvl = np.clip(np.interp(tad, [-15, 30], [122, 70]), 88, 118) + _ar1(rng, n, 0.9, 1.5)
    trl = 58.0 + 0.08 * (tvl - 95) + rng.normal(0, 0.8, n)
    # demand incl. losses [MW]
    prof = 1 + 0.10 * np.sin(2 * np.pi * (h - 4) / 24) + 0.06 * np.sin(4 * np.pi * (h - 5) / 24)
    D = (22 + 5.6 * np.maximum(16 - tad, 0) * prof + rng.normal(0, 2.0, n)).clip(12)
    # today's dispatch (fixed merit order)
    maint = (idx.month == 5) & (idx.day <= 14)
    bio = np.minimum(13.5, 0.3 * D)
    mva = np.where(maint, 0.0, np.clip(D - bio - 8.0, 0.0, 38.0))       # must-run, the CHP keeps at least 8 MW
    gt = np.clip(D - 95, 0, 30)
    hw1 = np.clip(D - 165, 0, 35)
    kwk = D - mva - bio - gt - hw1
    d = dh(tvl, trl)                                   # kJ/kg
    m = lambda q: q * 1e3 / d                          # noqa: E731  kg/s per MW
    th = lambda q: m(q) * 3.6                          # noqa: E731  t/h
    m_tot, m_east = m(D), m(mva + gt + bio)
    load = m_tot / np.quantile(m_tot, 0.999)
    le = m_east / max(np.quantile(m_east, 0.999), 1e-6)
    lk = m(kwk) / np.quantile(m(kwk), 0.999)
    noise = lambda sd: rng.normal(0, sd, n)            # noqa: E731

    c: dict[str, np.ndarray] = {}
    p_ret_k = 8.4 + noise(0.04)
    dp_k = 1.3 + 1.7 * load**2 + noise(0.05)
    c |= {"gas_CHP_T_supply": tvl, "gas_CHP_T_return": trl, "gas_CHP_heat": kwk, "gas_CHP_p_return": p_ret_k,
          "gas_CHP_p_supply": p_ret_k + dp_k, "gas_CHP_flow_total_out": th(kwk)}
    for i, sh in enumerate((0.33, 0.22, 0.17, 0.28), start=1):
        c[f"gas_CHP_flow_line_{i}"] = th(kwk) * sh * (1 + noise(0.02))
    dp_e = dp_k + 0.6 + 2.2 * le**2 - 0.5 * lk**2 + noise(0.05)
    for key, q in (("waste_incineration", mva), ("gas_turbine", gt), ("biomass_CHP", bio)):
        on = q > 0.5
        pr = p_ret_k - 0.3 - (dp_e - dp_k) / 2 + noise(0.03)
        c[f"{key}_T_supply"] = np.where(on, tvl + 0.5, 45.0)
        c[f"{key}_T_return"] = trl + noise(0.3)
        c[f"{key}_p_return"] = pr
        c[f"{key}_p_supply"] = pr + dp_e
        c[f"{key}_dp"] = dp_e + noise(0.02)
        c[f"{key}_heat"] = q
    c["gas_turbine_flow"] = th(gt)
    c["biomass_CHP_flow"] = m(bio) / daten.rho_w(tvl) * 3600            # m³/h in the supply line
    c["gas_turbine_heat"] = gt                                           # (real export: unusable copy; not used)
    hw_on = hw1 > 0.5
    dp_h = np.clip(dp_k - 0.9 * load**2 + 0.4 + noise(0.04), 0.4, None)
    c |= {"boiler_plant_1_T_supply": np.where(hw_on, tvl, 50.0), "boiler_plant_1_T_return": trl,
          "boiler_plant_1_flow": th(hw1), "boiler_plant_1_dp": dp_h, "boiler_plant_1_p_return": p_ret_k - 1.6 + noise(0.03),
          "boiler_plant_1_p_supply": p_ret_k - 1.6 + dp_h}
    # west transfer (heat exchanger) and its secondary network
    q_hx = np.clip(0.085 * D + noise(0.8), 2, 35)
    c |= {"boiler_plant_2_hx_flow": th(q_hx), "boiler_plant_2_hx_heat": q_hx, "boiler_plant_2_hx_T_supply": tvl - 1,
          "boiler_plant_2_hx_T_return": trl + 1, "boiler_plant_2_hx_dp": np.clip(dp_k - 1.0 * load**2, 0.3, None),
          "boiler_plant_2_hx_p_supply": 7.0 - 0.8 * load**2, "boiler_plant_2_hx_p_return": 4.2 + noise(0.03),
          "boiler_plant_2_heat_boilers": np.clip(0.2 * D - 30, 0, None)}
    c["boiler_plant_2_secondary_heat"] = q_hx + c["boiler_plant_2_heat_boilers"]
    c |= {"boiler_plant_2_secondary_T_supply": tvl - 6, "boiler_plant_2_secondary_T_return": trl - 2,
          "boiler_plant_2_secondary_p_supply": 6.0 + noise(0.05), "boiler_plant_2_secondary_p_return": 3.5 + noise(0.05)}
    for i in (1, 2, 3):
        c[f"boiler_plant_2_secondary_flow_{i}"] = th(c["boiler_plant_2_secondary_heat"]) / 3
    # pump stations (supply line): head gain grows with the load
    for k, (g0, g1) in {"pump_station_1": (1.0, 1.6), "pump_station_2": (0.6, 1.0)}.items():
        before = np.clip(dp_k - 1.1 * load**2 - 0.2, 0.3, None) + noise(0.03)
        c |= {f"{k}_dp_supply_before_pump": before, f"{k}_dp_supply_after_pump": before + g0 + g1 * load**2 + noise(0.03),
              f"{k}_p_supply_before_pump": 6.0 + before / 2, f"{k}_p_supply_after_pump": 6.0 + before / 2 + g0 + g1 * load**2,
              f"{k}_T_supply": tvl - 1, f"{k}_T_return": trl}
    c |= {"pump_station_1_flow_return_to_center": th(0.18 * D), "pump_station_1_flow_return_to_south": th(0.12 * D),
          "pump_station_2_flow_return_to_center": th(0.10 * D), "pump_station_2_flow_return_to_west": th(0.05 * D)}
    for i in (1, 2, 3):
        c[f"pump_station_1_speed_{i}"] = np.clip(55 + 40 * load + noise(2), 0, 100)
    # stations V01..V24 (signals as in the real export; values generic)
    rs = np.random.default_rng(7)
    for i in range(1, 25):
        v = f"V{i:02d}"
        f = rs.uniform(0.35, 0.9)
        dpv = np.clip(0.3 + (dp_k - 0.3) * f - 0.6 * f * load**2 + noise(0.03), 0.15, None)
        q = rs.uniform(0.002, 0.012) * D if v != "V22" else 0.06 * D
        c |= {f"{v}_dp": dpv, f"{v}_p_supply": 4.0 + dpv / 2 + 2.0, f"{v}_p_return": 6.0 - dpv / 2,
              f"{v}_T_supply": tvl - rs.uniform(0.5, 4) + noise(0.3), f"{v}_T_return": trl + rs.uniform(-3, 3) + noise(0.5),
              f"{v}_flow": th(q), f"{v}_heat": q}
    c["V15_house_T_supply"], c["V15_house_T_return"] = c["V15_T_supply"], c["V15_T_return"]
    c["V15_house_flow"], c["V15_house_heat"] = c["V15_flow"], c["V15_heat"]
    df = pd.DataFrame(c, index=idx)
    real_cols = SCHEMA_COLUMNS
    df = df.reindex(columns=real_cols)
    return df.astype("float64")


# column schema of the measurement export (169 signals, see docs/input_data_schema.md)
SCHEMA_COLUMNS = [
    "V01_T_return", "V01_T_supply", "V01_dp", "V01_p_return", "V01_p_supply", "V02_T_return", "V02_T_supply",
    "V02_dp", "V02_p_return", "V02_p_supply", "V03_dp", "V03_p_supply", "V04_T_return", "V04_T_supply", "V04_dp",
    "V04_p_supply", "V05_T_return", "V05_T_supply", "V05_flow", "V05_heat", "V05_p_supply", "V06_T_supply", "V06_dp",
    "V06_p_supply", "V07_T_return", "V07_T_supply", "V07_dp", "V07_flow", "V07_heat", "V07_p_supply", "V08_T_return",
    "V08_T_supply", "V08_p_return", "V08_p_supply", "V09_T_return", "V09_T_supply", "V09_dp", "V09_p_supply",
    "V10_dp", "V10_p_supply", "V11_T_return", "V11_T_supply", "V11_p_return", "V11_p_supply", "V12_T_return",
    "V12_T_supply", "V12_dp", "V12_p_return", "V12_p_supply", "V13_T_return", "V13_T_supply", "V13_dp", "V13_flow",
    "V13_heat", "V13_p_return", "V13_p_supply", "V14_T_return", "V14_T_supply", "V14_flow", "V14_heat",
    "V14_p_supply", "V15_dp", "V15_house_T_return", "V15_house_T_supply", "V15_house_flow", "V15_house_heat",
    "V15_p_return", "V15_p_supply", "V16_dp", "V17_T_supply", "V18_T_return", "V18_T_supply", "V18_p_return",
    "V18_p_supply", "V19_dp", "V19_p_supply", "V20_T_return", "V20_T_supply", "V20_flow", "V20_heat", "V21_T_return",
    "V21_T_supply", "V21_dp", "V21_p_supply", "V22_T_return", "V22_T_supply", "V22_dp", "V22_flow", "V22_heat",
    "V22_p_supply", "V23_T_return", "V23_T_supply", "V23_dp", "V23_p_return", "V23_p_supply", "V24_T_return",
    "V24_T_supply", "V24_p_return", "V24_p_supply", "biomass_CHP_T_return", "biomass_CHP_T_supply", "biomass_CHP_dp",
    "biomass_CHP_flow", "biomass_CHP_heat", "biomass_CHP_p_return", "biomass_CHP_p_supply",
    "boiler_plant_1_T_return", "boiler_plant_1_T_supply", "boiler_plant_1_dp", "boiler_plant_1_flow",
    "boiler_plant_1_p_return", "boiler_plant_1_p_supply", "boiler_plant_2_heat_boilers",
    "boiler_plant_2_hx_T_return", "boiler_plant_2_hx_T_supply", "boiler_plant_2_hx_dp", "boiler_plant_2_hx_flow",
    "boiler_plant_2_hx_heat", "boiler_plant_2_hx_p_return", "boiler_plant_2_hx_p_supply",
    "boiler_plant_2_secondary_T_return", "boiler_plant_2_secondary_T_supply", "boiler_plant_2_secondary_flow_1",
    "boiler_plant_2_secondary_flow_2", "boiler_plant_2_secondary_flow_3", "boiler_plant_2_secondary_heat",
    "boiler_plant_2_secondary_p_return", "boiler_plant_2_secondary_p_supply", "gas_CHP_T_return", "gas_CHP_T_supply",
    "gas_CHP_flow_line_1", "gas_CHP_flow_line_2", "gas_CHP_flow_line_3", "gas_CHP_flow_line_4",
    "gas_CHP_flow_total_out", "gas_CHP_heat", "gas_CHP_p_return", "gas_CHP_p_supply", "gas_turbine_T_return",
    "gas_turbine_T_supply", "gas_turbine_dp", "gas_turbine_flow", "gas_turbine_heat", "gas_turbine_p_return",
    "gas_turbine_p_supply", "pump_station_1_T_return", "pump_station_1_T_supply",
    "pump_station_1_dp_supply_after_pump", "pump_station_1_dp_supply_before_pump",
    "pump_station_1_flow_return_to_center", "pump_station_1_flow_return_to_south",
    "pump_station_1_p_supply_after_pump", "pump_station_1_p_supply_before_pump", "pump_station_1_speed_1",
    "pump_station_1_speed_2", "pump_station_1_speed_3", "pump_station_2_T_return", "pump_station_2_T_supply",
    "pump_station_2_dp_supply_after_pump", "pump_station_2_dp_supply_before_pump",
    "pump_station_2_flow_return_to_center", "pump_station_2_flow_return_to_west",
    "pump_station_2_p_supply_after_pump", "waste_incineration_T_return", "waste_incineration_T_supply",
    "waste_incineration_dp", "waste_incineration_heat", "waste_incineration_p_return", "waste_incineration_p_supply",
]


def plants() -> dict:
    """Generic plant and pump data (round example values, not the operator's plan data)."""
    return {"network": {"name": "SYNTHETIC", "pressure_class": "PN25", "note": LABEL},
            "plants": {
                "gas_CHP": {"dz_m": 0.0, "P_max_MW": {"design_minus14C": 125}, "m_max_t_h": 2400,
                            "pumps": {"arrangement": "supply", "installed": "4x700 t/h", "head_m": 70.0},
                            "dp_internal_bar": 1.0, "dp_max_outlet_bar": 4.0, "static_pressure_bar": {"normal": 8.4}},
                "waste_incineration": {"dz_m": 0.0, "P_max_MW": {"transition": 45}, "m_max_t_h": {"transition": 1000},
                                       "pumps": {"arrangement": "return", "installed": "2x550 t/h", "head_m": 85.0},
                                       "dp_internal_bar": 0.8, "dp_max_outlet_bar": 7.5,
                                       "shutdown_bar": {"p_return_below": 4.5, "p_supply_above": 20.0}},
                "gas_turbine": {"dz_m": 0.0, "P_max_MW": {"transition": 35}, "m_max_t_h": {"transition": 700},
                                "pumps": {"arrangement": "return", "installed": "2x700 t/h", "head_m": 85.0},
                                "dp_internal_bar": 1.2, "dp_max_outlet_bar": 7.5,
                                "shutdown_bar": {"p_return_below": 4.0, "p_supply_above": 20.0}},
                "biomass_CHP": {"dz_m": 0.0, "P_max_MW": {"transition": 14.5}, "m_max_t_h": {"transition": 400},
                                "pumps": {"arrangement": "return", "installed": "2x220 t/h", "head_m": 100.0},
                                "dp_internal_bar": 0.9, "dp_max_outlet_bar": 7.5,
                                "shutdown_bar": {"p_return_below": 4.5, "p_supply_above": 21.0}},
                "boiler_plant_1": {"dz_m": 0.0, "P_max_MW": {"design_minus14C": 40}, "m_max_t_h": 600,
                                   "pumps": {"arrangement": "return", "installed": "3x300 m3/h", "head_m": 60.0},
                                   "dp_internal_bar": 0.7}}}


def node_loads() -> dict[str, float]:
    """Generic connected load per load node [MW]: city centre 120, large customer at S 32, south branch 30 in total,
    every other load node 35 (round example values)."""
    south = nm.LASTGRUPPEN["Süd"]
    out = {n: 35.0 for n in dict.fromkeys(nm.SEKTOR_KNOTEN.values())}
    out[nm.STATIONEN["V03"]] = 120.0
    out[nm.GROSSKUNDE[1]] = 32.0
    out.update({n: 30.0 / len(south) for n in south})
    return out


def sectors(rng) -> pd.DataFrame:
    """One synthetic sub-area per load-node prefix of the network model; the node load is split equally."""
    rows = []
    load = node_loads()
    n_keys = pd.Series(list(nm.SEKTOR_KNOTEN.values())).value_counts()
    for key, node in nm.SEKTOR_KNOTEN.items():
        rows.append({"sub_area": key + ("A" if key.endswith("-") else ""), "section": "L", "region": node,
                     "network_volume_m3": round(float(rng.uniform(100, 500))), "customers": int(rng.integers(5, 60)),
                     "connected_MW": round(load[node] / n_keys[node], 2), "note": "synthetic"})
    rows.append({"sub_area": "W-A", "section": "W1", "region": "west", "network_volume_m3": 300, "customers": 20,
                 "connected_MW": 20.0, "note": "synthetic (secondary network, excluded)"})
    return pd.DataFrame(rows)


def prices_json(rng, year: int) -> dict:
    utc = pd.date_range(f"{year}-01-01 00:00", f"{year}-12-31 23:00", freq="h", tz=TZ).tz_convert("UTC")
    loc = utc.tz_convert(TZ)
    h, doy = loc.hour.to_numpy(), loc.dayofyear.to_numpy()
    solar = np.clip(np.sin(np.pi * (h - 6) / 14), 0, None) * (0.5 + 0.5 * np.sin(2 * np.pi * (doy - 80) / 365.25))
    p = 95 + 18 * np.cos(2 * np.pi * (doy - 15) / 365.25) + 25 * np.sin(2 * np.pi * (h - 13) / 24) ** 2 - 110 * solar
    wind = _ar1(rng, len(p), 0.98, 1.0)                                 # windy spells push prices down (some < 0)
    p = p + _ar1(rng, len(p), 0.95, 15.0) + 15 * (loc.dayofweek < 5) - 60 * np.clip(wind - 0.3, 0, None)
    return {"_note": LABEL, "unix_seconds": (utc.asi8 // 10**9).tolist(), "price": np.round(p, 2).tolist()}


def partner_a(rng) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01 00:00", "2023-12-31 23:00", freq="h", name="time")
    shift = np.isin(idx.hour, range(6, 22)) & (idx.dayofweek < 5)
    q = np.where(shift, 6.5, 2.0) * (1 + 0.15 * np.sin(2 * np.pi * idx.dayofyear / 365.25)) + rng.normal(0, 0.6, len(idx))
    q = np.where((idx.month == 8) & (idx.day <= 14), 0.5, q).clip(0)
    tw = 18 + 4 * np.sin(2 * np.pi * (idx.dayofyear - 110) / 365.25) + rng.normal(0, 1.0, len(idx))
    return pd.DataFrame({"time": idx, "Q_avail_MW": q.round(3), "T_warm_C": tw.round(2), "T_intake_C": (tw - 7).round(2)})


def grid_co2(rng, idx: pd.DatetimeIndex) -> pd.DataFrame:
    h = idx.hour.to_numpy()
    ef = 0.38 - 0.12 * np.clip(np.sin(np.pi * (h - 6) / 14), 0, None) + _ar1(rng, len(idx), 0.97, 0.05)
    return pd.DataFrame({"time": idx, "ef_grid_t_MWh": ef.clip(0.05).round(4)})


def write(out: Path, seed: int = 2025, start: str | None = None, end: str | None = None) -> Path:
    """Generate the data set; ``start``/``end`` cut the hourly files to a period (the full year is generated first, so
    a cut is identical to the corresponding part of the full-year set)."""
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)
    idx_amb = pd.DatetimeIndex(local_index(YEAR - 1).append(local_index(YEAR)), name="time_local")
    ta_all = ambient(rng, idx_amb)
    idx = local_index(YEAR)
    m = measurements(rng, idx, ta_all.reindex(idx))
    cut = lambda d: d.loc[start or d.index[0]:end or d.index[-1]]   # noqa: E731
    m = cut(m).round(4)
    ta = ta_all.loc[m.index[0] - pd.Timedelta(days=7):m.index[-1] + pd.Timedelta(days=7)]
    ta.to_frame().to_parquet(out / daten.TEMP_STUNDE)
    ta.groupby(ta.index.normalize()).mean().rename("T_ambient_daily_mean").rename_axis("date").to_csv(out / daten.TEMP_TAG)
    m.to_parquet(out / daten.MESSDATEN)
    (out / "plants.yaml").write_text(f"# {LABEL}\n" + yaml.safe_dump(plants(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    sectors(rng).to_csv(out / "sectors.csv", index=False)
    pd.DataFrame({"id": [f"V{i:02d}" for i in range(1, 25)], "region": "synthetic", "note": ""}).to_csv(out / "consumers.csv", index=False)
    (out / "prices").mkdir(exist_ok=True)
    (out / "prices" / f"raw_{YEAR}.json").write_text(json.dumps(prices_json(rng, YEAR)))
    partner_a(rng).to_csv(out / "partner_a_2023.csv", index=False)
    grid_co2(rng, m.index).to_csv(out / "grid_co2_2025.csv", index=False)
    (out / "README.md").write_text(
        f"# {LABEL}\n\nGenerated by `python -m scripts.dhn_study.central_tes.synthetic_data` (seed {seed}; period "
        f"{m.index[0]:%Y-%m-%d %H:%M} to {m.index[-1]:%Y-%m-%d %H:%M}, {len(m)} h). Same file names, "
        "columns, units and time conventions as the (non-public) data set of the study; see `docs/input_data_schema.md`.\n"
        "Results obtained with these data have no meaning for the network studied in the paper.\n", encoding="utf-8")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--seed", type=int, default=2025)
    ap.add_argument("--start", default="2025-01-01 00:00", help="first hour (default: shipped example, Jan-Feb)")
    ap.add_argument("--end", default="2025-02-28 23:00", help="last hour; use --full for the whole year")
    ap.add_argument("--full", action="store_true", help="whole year 2025 (8 759 h)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    st, en = (None, None) if a.full else (a.start, a.end)
    print(write(out if out.is_absolute() else daten.repo_root() / out, a.seed, st, en))


if __name__ == "__main__":
    main()
