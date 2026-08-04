"""Workbook loading, validation and caching. The workbook is the single source of truth."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CACHE_DIR, CFG, DATA_XLSX, ECON

REQUIRED_SHEETS = ["sites", "fca", "hlzf", "assets", "scenarios", "sensitivity",
                   "el_demand_MW", "heat_demand_MW_th", "market_15min"]

ECON_KEYS = ["wacc", "grid_capacity_price_EUR_per_MW_a", "grid_energy_price_EUR_per_MWh",
             "grid_reinforcement_EUR_per_MW", "co2_price_EUR_per_t", "atypical_discount_max",
             "electricity_tax_EUR_per_MWh", "project_lifetime_a", "voll_EUR_per_MWh",
             "intensive_min_util_h", "intensive_min_energy_GWh", "intensive_discount_max"]

@dataclass
class Inputs:
    sites: pd.DataFrame
    fca: pd.DataFrame
    hlzf: pd.DataFrame
    assets: pd.DataFrame
    scenarios: pd.DataFrame
    sensitivity: pd.DataFrame
    el: pd.DataFrame
    heat: pd.DataFrame
    market: pd.DataFrame

    def par(self, asset: str, param: str, default=None):
        m = (self.assets["asset_id"] == asset) & (self.assets["parameter"] == param)
        if not m.any():
            if default is None:
                raise KeyError(f"assets: missing {asset}.{param}")
            return default
        return self.assets.loc[m, "value"].iloc[0]


def parse_int_list(v) -> list[int]:
    if v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() in ("", "nan"):
        return []
    return [int(float(x)) for x in str(v).replace(" ", "").split(",") if x != ""]


def annuity(capex: float, lifetime: float, wacc: float) -> float:
    if wacc <= 0:
        return capex / lifetime
    return capex * wacc / (1 - (1 + wacc) ** (-lifetime))


def _validate(inp: Inputs) -> list[str]:
    msg = []
    for nm, df in [("el", inp.el), ("heat", inp.heat), ("market", inp.market)]:
        if df.index.has_duplicates:
            msg.append(f"{nm}: duplicated timestamps")
        if not df.index.is_monotonic_increasing:
            msg.append(f"{nm}: timestamps not sorted")
        d = pd.Series(df.index).diff().dropna().unique()
        if len(d) != 1 or pd.Timedelta(d[0]) != pd.Timedelta("15min"):
            msg.append(f"{nm}: not a gap-free 15-min series ({d[:3]})")
        if df.isna().any().any():
            msg.append(f"{nm}: contains NaN")
    for nm, df in [("el", inp.el), ("heat", inp.heat)]:
        if (df < 0).any().any():
            msg.append(f"{nm}: negative values")
    for nm, df in [("el_demand_MW", inp.el), ("heat_demand_MW_th", inp.heat)]:
        miss = set(inp.sites["site_id"]) - set(df.columns)
        if miss:
            msg.append(f"{nm}: missing columns for {sorted(miss)}")
    for col in ["da_price_EUR_per_MWh", "grid_EF_tCO2_per_MWh", "T_ambient_C"]:
        if col not in inp.market.columns:
            msg.append(f"market_15min: missing column {col}")
    valid_types = {"firm", "firm_upgrade", "static", "window", "dynamic"}
    bad = set(inp.fca["type"].str.strip().str.lower()) - valid_types
    if bad:
        msg.append(f"fca: unknown type(s) {sorted(bad)} — allowed: {sorted(valid_types)}")
    for _, f in inp.fca.iterrows():
        if str(f["type"]).strip().lower() in ("window", "dynamic") \
                and float(f["P_flex_rel"]) < float(f["P_static_rel"]):
            msg.append(f"fca {f['fca_id']}: P_flex_rel < P_static_rel")
    return msg


def load_inputs(xlsx: Path = DATA_XLSX, use_cache: bool = True) -> Inputs:
    cache = CACHE_DIR / (xlsx.stem + ".pkl")
    if use_cache and cache.exists() and cache.stat().st_mtime > xlsx.stat().st_mtime:
        inp = Inputs(**pd.read_pickle(cache))
    else:
        t0 = time.time()
        xl = pd.ExcelFile(xlsx)
        missing = [s for s in REQUIRED_SHEETS if s not in xl.sheet_names]
        assert not missing, f"workbook is missing sheets: {missing}"
        ts = lambda s: xl.parse(s).set_index("timestamp").sort_index()
        fca = xl.parse("fca")
        fca = fca[fca["fca_id"].notna() & fca["type"].notna()]   # sheet carries notes below
        inp = Inputs(sites=xl.parse("sites"), fca=fca,
                     hlzf=xl.parse("hlzf").dropna(subset=["season"]),
                     assets=xl.parse("assets"), scenarios=xl.parse("scenarios"),
                     sensitivity=xl.parse("sensitivity"),
                     el=ts("el_demand_MW"), heat=ts("heat_demand_MW_th"),
                     market=ts("market_15min"))
        pd.to_pickle(inp.__dict__, cache)
        print(f"workbook read in {time.time()-t0:.1f} s -> cached")

    problems = _validate(inp)
    if problems:
        raise ValueError("input validation failed:\n  - " + "\n  - ".join(problems))

    # grid connection = historical maximum of the existing electricity demand (scope rule)
    auto = inp.sites["P_grid_exist_MW"].isna()
    inp.sites["P_grid_hist_max_MW"] = [inp.el[s].max() for s in inp.sites["site_id"]]
    inp.sites["P_grid_exist_MW"] = np.where(auto, inp.sites["P_grid_hist_max_MW"],
                                            inp.sites["P_grid_exist_MW"])
    # two descriptors that predict most of the results
    inp.sites["load_factor"] = [inp.el[s].mean() / inp.el[s].max() for s in inp.sites["site_id"]]
    inp.sites["heat_to_power"] = [inp.heat[s].sum() / inp.el[s].sum() for s in inp.sites["site_id"]]

    ECON.clear()
    ECON.update({k: float(inp.par("ECON", k)) for k in ECON_KEYS})
    return inp
