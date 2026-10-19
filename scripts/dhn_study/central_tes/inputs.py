"""Hourly inputs on the 2025 measurement index (naive local time, 8 759 hours; DST gap/double hour as in the data set).

* Demand: measured feed-in into the interconnected network (KWK + MVA + GT + Bio-KWK + HW1). It contains the network
  losses and the heat-exchanger export to the west network. Short gaps per plant are interpolated (≤ 6 h); the
  remaining hours are filled from a demand model (outdoor temperature + hour-of-week) and flagged.
* Temperatures: measured supply/return at the main plant (default) or the linear heating curve of the existing energy
  configuration.
* Prices: DE-LU day-ahead (energy-charts.info, source BNetzA | SMARD.de, CC BY 4.0). From 2025-10-01 the SDAC uses a
  15-min MTU; quarter-hours are averaged to hourly means. Converted to naive local time; the double hour in October is
  averaged, the missing spring hour does not exist in the index either.
* Partner A: four measured water-based waste-heat streams merged into one (local file only), 2023, mapped
  weekday-preserving to 2025 (calendar shift 728 d; set PS ± 7 d).
* Grid CO2 (secondary metric): local file, hourly mean.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .. import daten
from . import config as C

INPUTS_VERSION = 4                 # bump when the input pipeline changes (invalidates the cache)
PLANT_COLS = {"KWK": "gas_CHP", "MVA": "waste_incineration", "GT": "gas_turbine", "BIO": "biomass_CHP", "HW1": "boiler_plant_1"}


# ----------------------------------------------------------------------------------------------------------- demand
def _demand_model(d: pd.Series, ta: pd.Series) -> pd.Series:
    """Piecewise-linear demand in the daily mean outdoor temperature + hour-of-week profile (least squares)."""
    tam = ta.groupby(ta.index.date).transform("mean")
    knots = [-10, 0, 5, 10, 15, 20]
    X = [np.ones(len(d))] + [np.maximum(knots[i] - tam.to_numpy(), 0.0) for i in range(len(knots))]
    how = (d.index.dayofweek * 24 + d.index.hour).to_numpy()
    for h in range(1, 168):
        X.append((how == h).astype(float))
    X = np.c_[tuple(X)]
    ok = d.notna().to_numpy() & np.isfinite(X).all(axis=1)
    coef = np.linalg.lstsq(X[ok], d.to_numpy()[ok], rcond=None)[0]
    return pd.Series(X @ coef, index=d.index)


def measured(cfg: dict) -> pd.DataFrame:
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    e.attrs = {}
    lim = cfg["inputs"]["demand"]["max_interp_gap_h"]
    parts = pd.DataFrame({k: e[v] for k, v in PLANT_COLS.items()})
    parts["HW1"] = parts["HW1"].fillna(0.0)
    parts["BIO"] = parts["BIO"].fillna(parts["BIO"].median())          # flat must-run profile (median 14.6 MW)
    parts = parts.interpolate(limit=lim, limit_area="inside")
    d = parts.sum(axis=1, min_count=5)
    ta, _ = daten.lade_aussentemperatur()
    ta = ta.reindex(m.index).interpolate(limit_direction="both")
    model = _demand_model(d, ta)
    imputed = d.isna()
    d = d.fillna(model).clip(lower=0.0)
    t_vl = m.gas_CHP_T_supply.interpolate(limit_direction="both")
    t_rl = m.gas_CHP_T_return.interpolate(limit_direction="both")
    hc = cfg["inputs"]["temperatures"]["heating_curve"]
    t_hc = pd.Series(np.interp(ta, hc["T_amb_C"], hc["T_supply_C"]), index=m.index)
    if cfg["inputs"]["temperatures"]["supply"] == "heating_curve":
        t_vl = t_hc
    out = pd.DataFrame({"D": d, "D_imputed": imputed, "T_VL": t_vl, "T_RL": t_rl, "T_amb": ta, "T_VL_hc": t_hc},
                       index=m.index)
    out["dh"] = daten.dh(out["T_VL"], out["T_RL"])                  # kJ/kg, network enthalpy difference
    ex = cfg["inputs"].get("expansion", {}) or {}
    share = float(ex.get("share", 0.0))
    out["D_base"] = out["D"]
    out["D_extra"] = share * out["D"]          # new customers in the expansion area, same hourly shape as today's demand
    out["D"] = out["D"] + out["D_extra"]
    for k in PLANT_COLS:
        out[f"Q_meas_{k}"] = parts[k]
    return out


# ----------------------------------------------------------------------------------------------------------- prices
def _raw_prices(path: Path) -> pd.Series:
    j = json.loads(path.read_text())
    s = pd.Series(j["price"], index=pd.to_datetime(j["unix_seconds"], unit="s", utc=True), dtype=float)
    h = s.groupby(s.index.floor("h")).mean()           # 15-min MTU -> hourly mean (floored in UTC: DST-safe)
    naive = h.tz_convert("Europe/Berlin").tz_localize(None)
    return naive.groupby(naive.index).mean()            # October double hour -> mean


def prices(cfg: dict, index: pd.DatetimeIndex, year: int | None = None) -> pd.Series:
    year = int(year or cfg["inputs"]["prices"]["year"])
    p = _raw_prices(C.root() / cfg["paths"]["prices_dir"] / f"raw_{year}.json")
    if year == index[0].year:
        out = p.reindex(index)
    else:   # weekday-preserving mapping onto the 2025 calendar (52-week multiples)
        shift = pd.Timedelta(days=364 * (index[0].year - year))
        src = index - shift
        out = pd.Series(p.reindex(src).to_numpy(), index=index)
    return out.interpolate(limit_direction="both").rename("price")


# ----------------------------------------------------------------------------------------------------------- partner A
def _read_stream(xlsx: Path, sheet: str, header: int) -> pd.DataFrame:
    d = pd.read_excel(xlsx, sheet_name=sheet, header=header, usecols=range(5))
    d.columns = ["t", "V", "T_in", "T_out", "P_kW"]
    d["t"] = pd.to_datetime(d["t"], errors="coerce")
    d = d.dropna(subset=["t"]).set_index("t").apply(pd.to_numeric, errors="coerce")
    # interval-ending time stamps -> hourly mean of the interval [h, h+1)
    d.index = d.index - pd.Timedelta(minutes=1)
    return d.resample("h").mean()


def partner_a_csv(path: Path) -> pd.DataFrame:
    """Partner-A table (schema: time, Q_avail_MW, T_warm_C, T_intake_C; hourly, naive local time)."""
    d = pd.read_csv(path, parse_dates=["time"]).set_index("time")
    return d.rename(columns={"Q_avail_MW": "Q_avail", "T_warm_C": "T_warm", "T_intake_C": "T_intake"})[["Q_avail", "T_warm", "T_intake"]]


def partner_a_raw(cfg: dict) -> pd.DataFrame | None:
    if cfg["paths"].get("partner_a_csv"):            # schema-based input (synthetic example or own data)
        return partner_a_csv(C.root() / cfg["paths"]["partner_a_csv"])
    loc = C.local(cfg).get("partner_a")
    if not loc:
        return None
    cache = C.root() / loc["cache"].replace(".parquet", f"_{len(cfg['inputs']['partner_a']['streams'])}s.parquet")
    if cache.exists():
        return pd.read_parquet(cache)
    xlsx = C.root() / loc["file"]
    q, vt, tin, v = 0.0, 0.0, 0.0, 0.0
    idx = pd.date_range("2023-01-01 00:00", "2023-12-31 23:00", freq="h")
    for name in cfg["inputs"]["partner_a"]["streams"]:
        s = loc["streams"][name]
        d = _read_stream(xlsx, s["sheet"], s["header_row"])
        if s.get("daily"):                       # daily values: constant over the 24 h of the day
            d.index = d.index + pd.Timedelta(minutes=1)
            d = d.resample("D").mean().reindex(idx, method="ffill")
            d["P_kW"] = d["P_kW"] / 24.0          # the daily sheet holds kWh per day (sum matches its annual total)
        d = d.reindex(idx).interpolate(limit=6, limit_area="inside")
        d["P_kW"] = d["P_kW"].clip(lower=0.0)
        q = q + d["P_kW"].fillna(0.0) / 1e3
        w = d["V"].fillna(0.0)
        vt = vt + w * d["T_out"].fillna(d["T_out"].mean())
        tin = tin + w * d["T_in"].fillna(d["T_in"].mean())
        v = v + w
    out = pd.DataFrame({"Q_avail": q, "T_warm": vt / v.where(v > 0), "T_intake": tin / v.where(v > 0)}, index=idx)
    mon = out.groupby(out.index.month)[["T_warm", "T_intake"]].transform("mean")
    out[["T_warm", "T_intake"]] = out[["T_warm", "T_intake"]].fillna(mon)
    cache.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache)
    return out


def partner_a(cfg: dict, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Q_avail [MW] (scaled) and source temperature [°C] on the 2025 index. Zeros if the local file is missing."""
    pa = cfg["inputs"]["partner_a"]
    raw = partner_a_raw(cfg)
    if raw is None:
        return pd.DataFrame({"Q_A_avail": 0.0, "T_source": 15.0, "A_data": False}, index=index)
    src = index - pd.Timedelta(days=pa["calendar_shift_days"])
    out_of_range = (src < raw.index[0]) | (src > raw.index[-1])
    src = src.where(~out_of_range, src - pd.Timedelta(days=364))
    r = raw.reindex(src)
    t = r["T_warm"].to_numpy() if pa["source_temperature"] == "warm" else 0.5 * (r["T_warm"] + r["T_intake"]).to_numpy()
    out = pd.DataFrame({"Q_A_avail": r["Q_avail"].fillna(0.0).to_numpy() * float(pa.get("scale", 1.0)),
                        "T_source": t, "A_data": True}, index=index)
    out["T_source"] = out["T_source"].interpolate(limit_direction="both") + float(pa.get("T_source_offset_K", 0.0))   # what-if
    return out


# ----------------------------------------------------------------------------------------------------------- grid CO2
def grid_co2(cfg: dict, index: pd.DatetimeIndex) -> pd.Series:
    if cfg["paths"].get("grid_co2_csv"):             # schema-based input: time, ef_grid_t_MWh
        s = pd.read_csv(C.root() / cfg["paths"]["grid_co2_csv"], parse_dates=["time"]).set_index("time")["ef_grid_t_MWh"]
        return s.reindex(index).interpolate(limit_direction="both").rename("ef_grid")
    loc = C.local(cfg).get("grid_co2")
    p = C.root() / "data/local/grid_co2_2025_raw15.parquet"
    if not loc or not p.exists():
        return pd.Series(np.nan, index=index, name="ef_grid")
    s = pd.read_parquet(p)[loc["column"]].dropna()
    h = s.groupby(s.index.floor("h")).mean()
    h = h.groupby(h.index).mean()
    return h.reindex(index).interpolate(limit_direction="both").rename("ef_grid")


# ----------------------------------------------------------------------------------------------------------- all
def build(cfg: dict, use_cache: bool = True) -> pd.DataFrame:
    """All hourly inputs (cached per input-relevant settings)."""
    key = json.dumps({"v": INPUTS_VERSION, **{k: cfg["inputs"][k] for k in ("demand", "temperatures", "prices", "partner_a", "expansion", "window") if k in cfg["inputs"]},
                      **({"paths": {k: cfg["paths"][k] for k in ("data_dir", "prices_dir", "partner_a_csv", "grid_co2_csv") if cfg["paths"].get(k)}}
                         if cfg["paths"].get("data_dir") else {})},
                     sort_keys=True)
    cache_dir = C.root() / cfg["paths"]["results"] / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / f"inputs_{hashlib.md5(key.encode()).hexdigest()[:10]}.parquet"
    if use_cache and f.exists():
        return pd.read_parquet(f)
    x = measured(cfg)
    win = cfg["inputs"].get("window")                # optional [start, end] (e.g. a short synthetic demo period)
    if win:
        x = x.loc[win[0]:win[1]].copy()
    x["price"] = prices(cfg, x.index)
    x = x.join(partner_a(cfg, x.index))
    x["ef_grid"] = grid_co2(cfg, x.index)
    x.to_parquet(f)
    return x
