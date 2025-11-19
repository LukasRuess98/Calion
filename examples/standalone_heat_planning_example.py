#!/usr/bin/env python3
"""
Standalone Heat Planning Example
=================================

Ein vollständiges, eigenständiges Beispiel für Heat Planning mit:
- Umfangreicher ENV-basierter Konfiguration
- Excel-Datenlader mit Zeitreihenverarbeitung
- COP-Lookup-Tabellen für Wärmepumpen
- Planning Framework (PF) für Design-Optimierung
- Rolling Horizon (RH) für Betriebsoptimierung
- Multi-Komponenten-System (HP1-4, HKW, GTOST, P2H, BMHKW, HWS, HWW, AVA, Storage)

Usage:
    # Basic run (Planning Framework only)
    python standalone_heat_planning_example.py

    # With environment variables
    RUN_MODE=PF_THEN_RH SCENARIO_TITLE=HP_v3_CO2_100 python standalone_heat_planning_example.py

    # Customize solver and settings
    SOLVER_NAME=cbc YEAR_TARGET=2023 DT_H=1.0 python standalone_heat_planning_example.py
"""

# ==============================
# Einheitlicher Konfig-Block
# ==============================

from __future__ import annotations

import os
import re
import json
import bisect
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from collections import defaultdict

import numpy as np
import pandas as pd
import pyomo.environ as pyo
from pyomo.environ import (
    ConcreteModel, Var, Param, RangeSet, Constraint, Objective, Expression,
    NonNegativeReals, PositiveReals, Binary, minimize, value as pyo_val
)
from pyomo.opt import SolverFactory


# --- Szenario-Titel früh setzen (optional) ---
os.environ.setdefault("SCENARIO_TITLE", "HP_v3_CO2_100")


def _getenv(key: str, default, cast=str):
    """ENV lesen, auf Typ casten. Bei leeren Strings auf Default zurückfallen."""
    raw = os.environ.get(key, None)
    val = default if (raw is None or str(raw).strip() == "") else raw
    try:
        return cast(val)
    except Exception:
        return cast(default)


def _getbool(key: str, default="0"):
    return bool(int(_getenv(key, default, str)))


# --- Allgemein / Timing ---
YEAR_TARGET = _getenv("YEAR_TARGET", 2023, int)
DT_H        = _getenv("DT_H", 1.0, float)  # Stunden

# --- Laufmodus & Szenario-Titel ---
RUN_MODE = _getenv("RUN_MODE", "PF_ONLY", str).upper()    # PF_ONLY | RH_ONLY | PF_THEN_RH
assert RUN_MODE in {"PF_ONLY", "RH_ONLY", "PF_THEN_RH"}, f"Ungültiger RUN_MODE: {RUN_MODE}"
SCENARIO_TITLE = _getenv("SCENARIO_TITLE", "Baseline", str)  # eindeutiger, einmaliger Titel

# --- Dateien & Exportpfade ---
EXPORT_BASE_DIR = _getenv("EXPORT_BASE_DIR", "exports", str)
INPUT_XLSX      = _getenv("INPUT_XLSX", "Import_Data.xlsx", str)
INPUT_SHEET     = None  # None → erstes Blatt

# Zentrales Workbook
SCENARIO_XLSX   = str(Path(EXPORT_BASE_DIR) / "scenario.xlsx")

# PF-Design-Export (JSON bleibt für RH_ONLY)
PF_DESIGN_JSON = _getenv("PF_DESIGN_JSON", str(Path(EXPORT_BASE_DIR) / "pf_design.json"), str)

# --- Solver ---
SOLVER_NAME = _getenv("SOLVER_NAME", "cbc", str)  # "gurobi","cbc","glpk"
SOLVER_TEE  = _getbool("SOLVER_TEE", "1")

# --- Rolling Horizon ---
HEAT_HORIZON_HOURS = _getenv("HEAT_HORIZON_HOURS", 7*24, int)
STEP_HOURS         = _getenv("STEP_HOURS", 24, int)
RH_TERMINAL_POLICY = _getenv("RH_TERMINAL_POLICY", "geq", str)  # "equal"|"geq"|"free"

# --- Kosten-Schalter ---
FLAGS = {
    "gridcost_in_energy": _getbool("INCLUDE_GRIDCOST_IN_ENERGY", "0"),
    "demand_in_rh":       _getbool("INCLUDE_DEMAND_CHARGE_IN_RH", "0"),
    "capex_in_rh":        _getbool("INCLUDE_INVEST_COSTS_IN_RH", "0"),
    "install_in_rh":      _getbool("INCLUDE_INSTALL_COSTS_IN_RH", "0"),
    "co2_in_obj":         _getbool("INCLUDE_CO2_COST_IN_OBJECTIVE", "1"),
}

# --- Preise ---
LEISTUNGSPREIS_EUR_PER_MW    = _getenv("LEISTUNGSPREIS_EUR_PER_MW", 127240.0, float)
GRIDCOST_EUR_PER_MWh         = _getenv("GRIDCOST_EUR_PER_MWh", 61.6, float)
GASPREIS_EUR_PER_MWh_th      = _getenv("GASPREIS_EUR_PER_MWh_th", 58.6, float)
BIOMASSEPREIS_EUR_PER_MWh_th = _getenv("BIOMASSEPREIS_EUR_PER_MWh_th", 20.0, float)
ABFALLPREIS_EUR_PER_MWh_th   = _getenv("ABFALLPREIS_EUR_PER_MWh_th", 10.0, float)
CO2_PRICE_EUR_PER_T          = _getenv("CO2_PRICE_EUR_PER_T", 100.0, float)

# --- Einspeise-Mechanik ---
EINSPEISE_FLOOR_EUR_PER_MWh = _getenv("EINSPEISE_FLOOR_EUR_PER_MWh", 0.0, float)
SELL_HAIRCUT = _getenv("SELL_HAIRCUT", 0.05, float)
SELL_SPREAD  = _getenv("SELL_SPREAD", 5.0, float)
SELL_FEE     = _getenv("SELL_FEE", 5.0, float)
SELL_PREMIUM = _getenv("SELL_PREMIUM", 0.0, float)

# --- Enable-Flags ---
ENABLE_CONFIG = {
    "HP1": True, "HP2": True, "HP3": True, "HP4": True,
    "HKW": True, "GTOST": True, "P2H": True,
    "BMHKW": True, "HWS": True, "HWW": True, "AVA": True,
    "STORAGE": True,
}


def print_config():
    """Print current configuration."""
    print(f"{'='*70}")
    print(f"RUN_MODE       = {RUN_MODE}")
    print(f"SCENARIO_TITLE = {SCENARIO_TITLE}")
    print(f"INPUT          = {INPUT_XLSX}")
    print(f"EXPORTS        = {EXPORT_BASE_DIR}")
    print(f"SOLVER         = {SOLVER_NAME}")
    print(f"YEAR_TARGET    = {YEAR_TARGET}")
    print(f"DT_H           = {DT_H}")
    print(f"{'='*70}\n")


print_config()


# ==============================
# 1) Utils & Loader
# ==============================

def _slug(s: str, maxlen: int = 60) -> str:
    """Convert string to filesystem-safe slug."""
    s = str(s).strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^A-Za-z0-9._-]+", "", s)
    return (s or "Baseline")[:maxlen]


def _require(condition: bool, msg: str):
    """Assertion helper with custom message."""
    if not condition:
        raise RuntimeError(msg)


def _excel_safe_df(df: pd.DataFrame, tz: str = "Europe/Berlin") -> pd.DataFrame:
    """Entfernt Zeitzonen für Excel-Writer (Index & datetime-Spalten)."""
    df2 = df.copy()
    if isinstance(df2.index, pd.DatetimeIndex) and df2.index.tz is not None:
        df2.index = df2.index.tz_convert(tz).tz_localize(None)

    for c in df2.columns:
        if np.issubdtype(df2[c].dtype, np.datetime64):
            s = pd.to_datetime(df2[c], errors="coerce")
            try:
                if getattr(s.dt, "tz", None) is not None:
                    s = s.dt.tz_convert(tz).dt.tz_localize(None)
            except Exception:
                pass
            df2[c] = s
    return df2


_norm = lambda s: re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _get_col(df: pd.DataFrame, *candidates: str) -> str:
    """Find column by fuzzy name matching."""
    norm_map = {_norm(c): c for c in df.columns}

    for cand in candidates:
        key = _norm(cand)
        if key in norm_map:
            return norm_map[key]

    for cand in candidates:
        key = _norm(cand)
        for k, orig in norm_map.items():
            if k == key or k.startswith(key) or key in k:
                return orig

    raise RuntimeError("Fehlende Spalte. Gesucht eine von: " + " | ".join(candidates))


def _parse_and_localize_datetime(
    sr: pd.Series,
    tz: str = "Europe/Berlin",
    input_time_is_local: bool = True,
    ambiguous_policy: str = "infer_then_first"
) -> pd.DatetimeIndex:
    """Parse datetime series and localize to timezone."""
    ts = pd.to_datetime(sr, errors="raise", utc=False)

    if getattr(ts.dt, "tz", None) is None:
        if input_time_is_local:
            if ambiguous_policy == "infer_then_first":
                try:
                    ts = ts.dt.tz_localize(tz, nonexistent="shift_forward", ambiguous="infer")
                except Exception:
                    ts = ts.dt.tz_localize(tz, nonexistent="shift_forward", ambiguous=True)
            else:
                ambiguous_arg = {"first": True, "last": False, "NaT": "NaT", "infer": "infer"}.get(ambiguous_policy, "infer")
                ts = ts.dt.tz_localize(tz, nonexistent="shift_forward", ambiguous=ambiguous_arg)
        else:
            ts = ts.dt.tz_localize("UTC")

    ts_utc_naive = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    return pd.DatetimeIndex(ts_utc_naive)


def _enforce_monotonic_unique_index(
    df: pd.DataFrame,
    duplicate_strategy: str = "drop_first"
) -> pd.DataFrame:
    """Ensure DataFrame has monotonic, unique datetime index."""
    if not isinstance(df.index, pd.DatetimeIndex):
        raise RuntimeError("Index ist kein Datumsindex.")

    df = df.sort_index()
    dup_mask = df.index.duplicated(keep="first")
    n_dup = int(dup_mask.sum())

    if n_dup:
        if duplicate_strategy == "drop_first":
            print(f"[Loader] Entferne {n_dup} doppelte Zeitstempel (behalte erste Vorkommen).")
            df = df[~dup_mask]
        else:
            raise RuntimeError(f"Doppelte Zeitstempel gefunden: {n_dup}.")

    _require(df.index.is_monotonic_increasing, "Zeitindex nicht monoton steigend.")
    _require(df.index.is_unique, "Zeitindex enthält weiterhin Duplikate.")
    return df


def _reindex_hourly_and_fill(
    df: pd.DataFrame,
    dt_hours: float = 1.0,
    gap_strategy: str = "error"
) -> pd.DataFrame:
    """Reindex to regular hourly intervals and fill gaps."""
    if df.empty:
        return df

    freq = pd.to_timedelta(dt_hours, unit="h")
    target_index = pd.date_range(df.index.min(), df.index.max(), freq=freq)

    if len(target_index) != len(df):
        missing = len(target_index) - len(df)
        msg = f"[Loader] Es fehlen {missing} Zeitschritte (soll: {len(target_index)}, ist: {len(df)})."

        if gap_strategy == "error":
            raise RuntimeError(msg + " gap_strategy='error' → abbrechen.")

        print(msg + f" gap_strategy='{gap_strategy}' → fülle Lücken.")

    df2 = df.reindex(target_index)

    if gap_strategy == "ffill":
        df2 = df2.ffill().bfill()
    elif gap_strategy == "bfill":
        df2 = df2.bfill().ffill()
    elif gap_strategy == "interp":
        num_cols = df2.select_dtypes(include=[np.number]).columns
        non_num  = [c for c in df2.columns if c not in num_cols]
        df2[num_cols] = df2[num_cols].interpolate(method="time", limit_direction="both")
        if non_num:
            df2[non_num] = df2[non_num].ffill().bfill()

    steps = df2.index.to_series().diff().dropna().unique()
    _require(len(steps) == 1 and steps[0] == freq, f"Schrittweite ist nicht {freq}.")

    return df2


def load_input_excel(
    path: str,
    sheet_name=None,
    year_target: int | None = None,
    *,
    tz: str = "Europe/Berlin",
    input_time_is_local: bool = True,
    dt_hours: float | None = None,
    duplicate_strategy: str = "drop_first",
    gap_strategy: str = "error",
    ambiguous_policy: str = "infer_then_first",
) -> pd.DataFrame:
    """Load and process Excel input data with time series."""
    _require(os.path.exists(path), f"Datei nicht gefunden: {path}")

    xls = pd.ExcelFile(path)
    sh  = sheet_name if sheet_name is not None else xls.sheet_names[0]
    df_raw = pd.read_excel(path, sheet_name=sh)
    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    # Parse datetime index
    _require("Datum" in df_raw.columns, "Spalte 'Datum' fehlt in Import_Data.xlsx")
    idx = _parse_and_localize_datetime(
        df_raw["Datum"],
        tz=tz,
        input_time_is_local=input_time_is_local,
        ambiguous_policy=ambiguous_policy,
    )

    df = df_raw.set_index(idx).drop(columns=["Datum"])

    if year_target is not None:
        df = df[df.index.year == int(year_target)]
        _require(len(df) > 0, f"Im Zieljahr {year_target} keine Daten.")

    df = _enforce_monotonic_unique_index(df, duplicate_strategy=duplicate_strategy)

    # Find required columns
    col_price = _get_col(df, "Day_Ahead_Price €/MWh", "Day Ahead Price €/MWh", "strompreis", "price_eur_mwh")
    col_heat  = _get_col(df, "Wärmebedarf MW", "Waermebedarf MW", "waermebedarf", "heat_demand_mw")
    col_co2   = _get_col(df, "CO2_consumption_based kgCO2/MWh", "co2_intensity_kgco2_mwh", "co2 kgco2/mwh")

    col_wrgq = {i: _get_col(df,
                            f"WRG{i}Q MW", f"WRG{i} Q MW", f"WRG{i}_Q MW", f"WRG{i}_Q MW_th", f"wrg{i}qmw")
                for i in [1,2,3,4]}
    col_wrgt = {i: _get_col(df,
                            f"WRG{i}_T °C", f"WRG{i} T °C", f"wrg{i} temp c")
                for i in [1,2,3,4]}

    # Create output dataframe
    out = pd.DataFrame(index=df.index)
    _to_num = lambda s: pd.to_numeric(s.astype(str).str.replace(",", ".", regex=False), errors="raise")

    out["strompreis_EUR_MWh"] = _to_num(df[col_price])
    out["waermebedarf_MWth"]  = _to_num(df[col_heat])
    out["grid_co2_kg_MWh"]    = _to_num(df[col_co2])

    for i in [1,2,3,4]:
        out[f"WRG{i}_Q_cap"] = _to_num(df[col_wrgq[i]])
        out[f"WRG{i}_T_K"]   = _to_num(df[col_wrgt[i]]) + 273.15

    _require(not out.isna().any().any(), "NaN in Import_Data – bitte fehlende Werte schließen.")

    if dt_hours is None:
        dt_hours = float(globals().get("DT_H", 1.0))

    out = _reindex_hourly_and_fill(out, dt_hours=dt_hours, gap_strategy=gap_strategy)

    print(f"[LOAD] {os.path.basename(path)} → {len(out)} Std (UTC-naiv) "
          f"von {out.index.min()} bis {out.index.max()}, dt={dt_hours}h")

    return out


# ==============================
# 2) COP-Logik
# ==============================

# Sink/source temperatures and parameters
Tsink_out = 363.15
Tsink_in = 343.15
deltaTpp  = 5.0
eta       = 0.75
FQ        = 0.10


def lmtd(Th, Tc):
    """Calculate logarithmic mean temperature difference."""
    return (Th - Tc) / np.log(Th / Tc)


LMTD_sink = lmtd(Tsink_out, Tsink_in)

# Build COP lookup table
Tsourcein_vals = np.linspace(303.15, 353.15, 6)
deltaT_vals    = np.array([10, 20, 30, 40, 50])

_records = []
for Tsourcein in Tsourcein_vals:
    for dT in deltaT_vals:
        Tsourceout = Tsourcein - dT
        if Tsourceout <= 0 or Tsourceout >= Tsourcein:
            continue

        LMTD_source = lmtd(Tsourcein, Tsourceout)
        mdts = 0.2*(Tsink_out - Tsourceout + 2*deltaTpp) + 0.2*(Tsink_out - Tsink_in) + 0.016
        qww  = 0.0014*(Tsink_out - Tsourceout + 2*deltaTpp) - 0.0015*(Tsink_out - Tsink_in) + 0.039

        A = LMTD_sink / (LMTD_sink - LMTD_source + 1e-9)
        B = (1 + (mdts + deltaTpp)/LMTD_sink) / (1 + (mdts + 0.5*dT + 2*deltaTpp)/(LMTD_sink - LMTD_source + 1e-9))
        COP = A * B * eta * (1 - qww) + 1 - eta - FQ
        COP = float(np.clip(COP if np.isfinite(COP) else 3.0, 0.5, 12.0))

        _records.append({"Tsourcein": round(Tsourcein,2), "Tsourceout": round(Tsourceout,2), "COP": round(COP,4)})

cop_lookup_df = pd.DataFrame(_records).sort_values(["Tsourcein","Tsourceout"])

# Build piecewise rules
cop_piecewise_rules = defaultdict(list)
for _, r in cop_lookup_df.iterrows():
    cop_piecewise_rules[r["Tsourcein"]].append((r["Tsourceout"], r["COP"]))

cop_piecewise_rules = {k: sorted(v, key=lambda x: x[0]) for k, v in cop_piecewise_rules.items()}

_all_x = sorted({x for pts in cop_piecewise_rules.values() for (x, _) in pts})
x_min, x_max = (_all_x[0], _all_x[-1]) if _all_x else (0.0, 1.0)
T_grid = sorted(cop_piecewise_rules.keys())


def _interp_on_curve(pts, x):
    """Interpolate on a single curve."""
    if x <= pts[0][0]:  return pts[0][1]
    if x >= pts[-1][0]: return pts[-1][1]
    for (x0,y0),(x1,y1) in zip(pts[:-1], pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1-y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def bilinear_interp_from_lookup(Tsrc_in, x, clamp_x=True):
    """Bilinear interpolation from COP lookup table."""
    if not T_grid: return 3.0
    if clamp_x: x = max(x_min, min(x_max, x))

    j = bisect.bisect_left(T_grid, Tsrc_in)
    if j == 0: return _interp_on_curve(cop_piecewise_rules[T_grid[0]], x)
    if j == len(T_grid): return _interp_on_curve(cop_piecewise_rules[T_grid[-1]], x)

    t0, t1 = T_grid[j-1], T_grid[j]
    y0 = _interp_on_curve(cop_piecewise_rules[t0], x)
    y1 = _interp_on_curve(cop_piecewise_rules[t1], x)

    y0 = 3.0 if (not np.isfinite(y0)) else y0
    y1 = 3.0 if (not np.isfinite(y1)) else y1

    w  = (Tsrc_in - t0) / (t1 - t0)
    val = y0*(1-w) + y1*w
    return float(np.clip(val if np.isfinite(val) else 3.0, 0.5, 12.0))


def safe_cop(Tin, Tout, COP_MIN=1.01, COP_MAX=12.0, COP_FALLBACK=3.0):
    """Safe COP calculation with bounds checking."""
    Tin_v, Tout_v = float(Tin), float(Tout)
    x = max(x_min, min(x_max, float(Tout_v))) if x_min < x_max else float(Tout_v)
    val = bilinear_interp_from_lookup(Tin_v, x) if T_grid else COP_FALLBACK

    if (not np.isfinite(val)) or (val <= 0):
        raise RuntimeError(f"COP-Berechnung fehlgeschlagen (Tin={Tin}, Tout={Tout}).")

    return float(np.clip(val, COP_MIN, COP_MAX))


print(f"[COP] Lookup-Tabelle erstellt mit {len(cop_lookup_df)} Einträgen\n")


# ==============================
# 3) Modell-Builder (PF & RH)
# ==============================

HP_IDS = [1, 2, 3, 4]


def _apply_terminal_policy(m: pyo.ConcreteModel, policy: str):
    """Apply terminal policy for storage SOC constraint."""
    # Basis: >=
    m.soc_terminal_geq = pyo.Constraint(expr = m.storage_level[m.t.last()] >= m.SOC_init)

    if policy == "equal":
        m.soc_terminal_eq = pyo.Constraint(expr = m.storage_level[m.t.last()] <= m.SOC_init)
    elif policy == "geq":
        pass
    elif policy == "free":
        m.soc_terminal_geq.deactivate()
    else:
        raise ValueError(f"Unbekannte RH_TERMINAL_POLICY: {policy}")


def _build_common_blocks(m: pyo.ConcreteModel, T: int, dfW: pd.DataFrame):
    """Build common model blocks (parameters, variables, constraints)."""

    # Grundreihen
    prices = dfW["strompreis_EUR_MWh"].astype(float).tolist()
    heat   = dfW["waermebedarf_MWth"].astype(float).tolist()
    co2    = dfW["grid_co2_kg_MWh"].astype(float).tolist()

    def _cop_series(T_K: pd.Series, dT=20.0):
        Tin = T_K.astype(float).values
        Tout = np.maximum(1.0, Tin - dT)
        return [safe_cop(Tin[i], Tout[i]) for i in range(T)]

    # Mengen
    m.t = RangeSet(1, T)
    m.HP = pyo.Set(initialize=HP_IDS)

    # Parameter
    m.strompreis   = Param(m.t, initialize={i: prices[i-1] for i in range(1, T+1)})
    m.waermebedarf = Param(m.t, initialize={i: heat[i-1]   for i in range(1, T+1)})
    m.grid_co2_kg_per_MWh = Param(m.t, initialize={i: co2[i-1] for i in range(1, T+1)},
                                   within=NonNegativeReals, mutable=True)

    # Kosten-Parameter
    m.Leistungspreis      = Param(initialize=LEISTUNGSPREIS_EUR_PER_MW, mutable=True)
    m.Gridcost            = Param(initialize=GRIDCOST_EUR_PER_MWh, mutable=True)
    m.Installationskosten = Param(initialize=20000.0, mutable=True)
    m.Gaspreis            = Param(initialize=GASPREIS_EUR_PER_MWh_th, mutable=True)
    m.Abfallpreis         = Param(initialize=ABFALLPREIS_EUR_PER_MWh_th, mutable=True)
    m.Biomassepreis       = Param(initialize=BIOMASSEPREIS_EUR_PER_MWh_th, mutable=True)

    # Einspeise-Mechanik
    m.einspeisepreis = Param(initialize=EINSPEISE_FLOOR_EUR_PER_MWh, within=NonNegativeReals, mutable=True)
    m.SELL_HAIRCUT = Param(initialize=SELL_HAIRCUT,  mutable=True)
    m.SELL_SPREAD  = Param(initialize=SELL_SPREAD,   mutable=True)
    m.SELL_FEE     = Param(initialize=SELL_FEE,      mutable=True)
    m.SELL_PREMIUM = Param(initialize=SELL_PREMIUM,  mutable=True)

    m.sell_base = Expression(m.t, rule=lambda mm, t: (1.0 - mm.SELL_HAIRCUT) * mm.strompreis[t]
                                               + mm.SELL_PREMIUM - mm.SELL_FEE - mm.SELL_SPREAD)
    m.sell_price_eff = Param(m.t, initialize=lambda mm, t: max(float(pyo_val(mm.sell_base[t])),
                                                               float(pyo_val(mm.einspeisepreis))), mutable=True)

    # CO2
    m.CO2_price_EUR_per_t = Param(initialize=float(CO2_PRICE_EUR_PER_T), mutable=True)
    m.CO2_cost_switch     = Param(initialize=int(bool(FLAGS["co2_in_obj"])), mutable=True, within=NonNegativeReals)

    # Enable-Flags (indexiert für HPs)
    m.EN_HP = Param(m.HP, initialize={i: int(ENABLE_CONFIG[f"HP{i}"]) for i in HP_IDS},
                    within=NonNegativeReals, mutable=True)
    m.EN_HKW     = Param(initialize=int(ENABLE_CONFIG["HKW"]),     within=NonNegativeReals, mutable=True)
    m.EN_GTOST   = Param(initialize=int(ENABLE_CONFIG["GTOST"]),   within=NonNegativeReals, mutable=True)
    m.EN_P2H     = Param(initialize=int(ENABLE_CONFIG["P2H"]),     within=NonNegativeReals, mutable=True)
    m.EN_BMHKW   = Param(initialize=int(ENABLE_CONFIG["BMHKW"]),   within=NonNegativeReals, mutable=True)
    m.EN_HWS     = Param(initialize=int(ENABLE_CONFIG["HWS"]),     within=NonNegativeReals, mutable=True)
    m.EN_HWW     = Param(initialize=int(ENABLE_CONFIG["HWW"]),     within=NonNegativeReals, mutable=True)
    m.EN_AVA     = Param(initialize=int(ENABLE_CONFIG["AVA"]),     within=NonNegativeReals, mutable=True)
    m.EN_STORAGE = Param(initialize=int(ENABLE_CONFIG["STORAGE"]), within=NonNegativeReals, mutable=True)

    # Speicher
    m.storage_eff_charge    = Param(initialize=0.95)
    m.storage_eff_discharge = Param(initialize=0.95)
    m.storage_c_rate        = Param(initialize=0.25)
    m.CAPEXspeicher       = Param(initialize=5160.0, within=PositiveReals, mutable=True)
    m.Lebensdauerspeicher = Param(initialize=20)

    STO_E_MAX = 50000.0
    STO_E_MIN = 10.0
    STO_P_MAX = 50.0

    m.storage_capacity        = Var(bounds=(0, STO_E_MAX))
    m.storage_power           = Var(bounds=(0, STO_P_MAX))
    m.storage_capacity_active = Var(domain=Binary)
    m.storage_level     = Var(m.t, domain=NonNegativeReals)
    m.storage_charge    = Var(m.t, domain=NonNegativeReals)
    m.storage_discharge = Var(m.t, domain=NonNegativeReals)

    # Initial SOC
    m.SOC_init = Param(initialize=0.0, mutable=True)

    # Heat pumps (indexiert)
    m.HP_Q_th = Var(m.HP, m.t, domain=NonNegativeReals)
    m.HP_P_el = Var(m.HP, m.t, domain=NonNegativeReals)
    m.HP_cap  = Var(m.HP, domain=NonNegativeReals, bounds=(0, 100))
    m.HP_active = Var(m.HP, domain=Binary)

    # COP parameters (per HP, per timestep - hier vereinfacht mit festen Werten)
    m.HP_COP = Param(m.HP, m.t, initialize=3.5, mutable=True)

    # Weitere Komponenten (vereinfacht)
    m.HKW_Q    = Var(m.t, domain=NonNegativeReals, bounds=(0, 50))
    m.GTOST_Q  = Var(m.t, domain=NonNegativeReals, bounds=(0, 30))
    m.P2H_Q    = Var(m.t, domain=NonNegativeReals, bounds=(0, 20))
    m.BMHKW_Q  = Var(m.t, domain=NonNegativeReals, bounds=(0, 25))
    m.HWS_Q    = Var(m.t, domain=NonNegativeReals, bounds=(0, 15))
    m.HWW_Q    = Var(m.t, domain=NonNegativeReals, bounds=(0, 15))
    m.AVA_Q    = Var(m.t, domain=NonNegativeReals, bounds=(0, 20))

    # Grid purchases and sales
    m.grid_buy  = Var(m.t, domain=NonNegativeReals)
    m.grid_sell = Var(m.t, domain=NonNegativeReals)
    m.peak_demand = Var(domain=NonNegativeReals)


def build_pf_model(dfW: pd.DataFrame) -> pyo.ConcreteModel:
    """Build Planning Framework (PF) model for design optimization."""
    T = len(dfW)
    m = ConcreteModel(name="PF_Model")

    _build_common_blocks(m, T, dfW)

    # === Constraints ===

    # Heat balance
    def heat_balance_rule(mm, t):
        hp_total = sum(mm.HP_Q_th[i, t] for i in mm.HP)
        other = (mm.HKW_Q[t] + mm.GTOST_Q[t] + mm.P2H_Q[t] + mm.BMHKW_Q[t] +
                 mm.HWS_Q[t] + mm.HWW_Q[t] + mm.AVA_Q[t])
        supply = hp_total + other + mm.storage_discharge[t]
        demand = mm.waermebedarf[t] + mm.storage_charge[t]
        return supply == demand

    m.heat_balance = Constraint(m.t, rule=heat_balance_rule)

    # HP capacity constraints
    def hp_cap_rule(mm, i, t):
        return mm.HP_Q_th[i, t] <= mm.HP_cap[i] * mm.EN_HP[i]
    m.hp_cap_con = Constraint(m.HP, m.t, rule=hp_cap_rule)

    # HP power consumption (simplified COP)
    def hp_power_rule(mm, i, t):
        return mm.HP_P_el[i, t] * mm.HP_COP[i, t] == mm.HP_Q_th[i, t]
    m.hp_power = Constraint(m.HP, m.t, rule=hp_power_rule)

    # Storage dynamics
    def storage_dynamics_rule(mm, t):
        if t == 1:
            prev_level = mm.SOC_init
        else:
            prev_level = mm.storage_level[t-1]

        return mm.storage_level[t] == (prev_level +
                                        mm.storage_eff_charge * mm.storage_charge[t] -
                                        mm.storage_discharge[t] / mm.storage_eff_discharge)
    m.storage_dyn = Constraint(m.t, rule=storage_dynamics_rule)

    # Storage capacity constraints
    def storage_level_max_rule(mm, t):
        return mm.storage_level[t] <= mm.storage_capacity * mm.EN_STORAGE
    m.storage_level_max = Constraint(m.t, rule=storage_level_max_rule)

    def storage_charge_max_rule(mm, t):
        return mm.storage_charge[t] <= mm.storage_power * mm.EN_STORAGE
    m.storage_charge_max = Constraint(m.t, rule=storage_charge_max_rule)

    def storage_discharge_max_rule(mm, t):
        return mm.storage_discharge[t] <= mm.storage_power * mm.EN_STORAGE
    m.storage_discharge_max = Constraint(m.t, rule=storage_discharge_max_rule)

    # Grid balance
    def grid_balance_rule(mm, t):
        hp_el = sum(mm.HP_P_el[i, t] for i in mm.HP)
        p2h_el = mm.P2H_Q[t] / 0.98  # Simple efficiency
        consumption = hp_el + p2h_el
        return mm.grid_buy[t] - mm.grid_sell[t] == consumption
    m.grid_balance = Constraint(m.t, rule=grid_balance_rule)

    # Peak demand tracking
    def peak_demand_rule(mm, t):
        return mm.peak_demand >= mm.grid_buy[t]
    m.peak_demand_con = Constraint(m.t, rule=peak_demand_rule)

    # Terminal policy
    _apply_terminal_policy(m, RH_TERMINAL_POLICY)

    # === Objective ===
    def objective_rule(mm):
        # Energy costs
        energy_cost = sum(
            mm.strompreis[t] * mm.grid_buy[t] -
            mm.sell_price_eff[t] * mm.grid_sell[t]
            for t in mm.t
        ) * DT_H

        # Demand charge
        demand_cost = mm.Leistungspreis * mm.peak_demand

        # Fuel costs
        fuel_cost = sum(
            mm.HKW_Q[t] * mm.Gaspreis +
            mm.GTOST_Q[t] * mm.Gaspreis +
            mm.BMHKW_Q[t] * mm.Biomassepreis +
            mm.AVA_Q[t] * mm.Abfallpreis
            for t in mm.t
        ) * DT_H

        # CAPEX costs (annualized)
        hp_capex = sum(mm.HP_cap[i] * 800.0 / 15.0 for i in mm.HP)  # EUR/MW/year
        storage_capex = mm.storage_capacity * mm.CAPEXspeicher / mm.Lebensdauerspeicher

        # CO2 costs
        co2_cost = mm.CO2_cost_switch * sum(
            mm.grid_buy[t] * mm.grid_co2_kg_per_MWh[t] / 1000.0 * mm.CO2_price_EUR_per_t
            for t in mm.t
        ) * DT_H

        total = energy_cost + demand_cost + fuel_cost + hp_capex + storage_capex + co2_cost
        return total

    m.obj = Objective(rule=objective_rule, sense=minimize)

    print(f"[PF] Modell erstellt: {T} Zeitschritte, {len(list(m.HP))} Wärmepumpen")
    return m


def build_rh_model(dfW: pd.DataFrame, design: Dict[str, Any]) -> pyo.ConcreteModel:
    """Build Rolling Horizon (RH) model for operational optimization."""
    T = len(dfW)
    m = ConcreteModel(name="RH_Model")

    _build_common_blocks(m, T, dfW)

    # Fix design variables from PF
    if "HP_cap" in design:
        for i in m.HP:
            m.HP_cap[i].fix(design["HP_cap"].get(i, 0.0))

    if "storage_capacity" in design:
        m.storage_capacity.fix(design["storage_capacity"])
        m.storage_power.fix(design["storage_power"])

    # Same constraints as PF (operational mode)
    # Heat balance
    def heat_balance_rule(mm, t):
        hp_total = sum(mm.HP_Q_th[i, t] for i in mm.HP)
        other = (mm.HKW_Q[t] + mm.GTOST_Q[t] + mm.P2H_Q[t] + mm.BMHKW_Q[t] +
                 mm.HWS_Q[t] + mm.HWW_Q[t] + mm.AVA_Q[t])
        supply = hp_total + other + mm.storage_discharge[t]
        demand = mm.waermebedarf[t] + mm.storage_charge[t]
        return supply == demand
    m.heat_balance = Constraint(m.t, rule=heat_balance_rule)

    # HP capacity constraints
    def hp_cap_rule(mm, i, t):
        return mm.HP_Q_th[i, t] <= mm.HP_cap[i] * mm.EN_HP[i]
    m.hp_cap_con = Constraint(m.HP, m.t, rule=hp_cap_rule)

    # HP power consumption
    def hp_power_rule(mm, i, t):
        return mm.HP_P_el[i, t] * mm.HP_COP[i, t] == mm.HP_Q_th[i, t]
    m.hp_power = Constraint(m.HP, m.t, rule=hp_power_rule)

    # Storage dynamics
    def storage_dynamics_rule(mm, t):
        if t == 1:
            prev_level = mm.SOC_init
        else:
            prev_level = mm.storage_level[t-1]
        return mm.storage_level[t] == (prev_level +
                                        mm.storage_eff_charge * mm.storage_charge[t] -
                                        mm.storage_discharge[t] / mm.storage_eff_discharge)
    m.storage_dyn = Constraint(m.t, rule=storage_dynamics_rule)

    # Storage capacity constraints
    def storage_level_max_rule(mm, t):
        return mm.storage_level[t] <= mm.storage_capacity * mm.EN_STORAGE
    m.storage_level_max = Constraint(m.t, rule=storage_level_max_rule)

    def storage_charge_max_rule(mm, t):
        return mm.storage_charge[t] <= mm.storage_power * mm.EN_STORAGE
    m.storage_charge_max = Constraint(m.t, rule=storage_charge_max_rule)

    def storage_discharge_max_rule(mm, t):
        return mm.storage_discharge[t] <= mm.storage_power * mm.EN_STORAGE
    m.storage_discharge_max = Constraint(m.t, rule=storage_discharge_max_rule)

    # Grid balance
    def grid_balance_rule(mm, t):
        hp_el = sum(mm.HP_P_el[i, t] for i in mm.HP)
        p2h_el = mm.P2H_Q[t] / 0.98
        consumption = hp_el + p2h_el
        return mm.grid_buy[t] - mm.grid_sell[t] == consumption
    m.grid_balance = Constraint(m.t, rule=grid_balance_rule)

    # Terminal policy
    _apply_terminal_policy(m, RH_TERMINAL_POLICY)

    # === Objective (operational costs only) ===
    def objective_rule(mm):
        # Energy costs
        energy_cost = sum(
            mm.strompreis[t] * mm.grid_buy[t] -
            mm.sell_price_eff[t] * mm.grid_sell[t]
            for t in mm.t
        ) * DT_H

        # Fuel costs
        fuel_cost = sum(
            mm.HKW_Q[t] * mm.Gaspreis +
            mm.GTOST_Q[t] * mm.Gaspreis +
            mm.BMHKW_Q[t] * mm.Biomassepreis +
            mm.AVA_Q[t] * mm.Abfallpreis
            for t in mm.t
        ) * DT_H

        # CO2 costs
        co2_cost = mm.CO2_cost_switch * sum(
            mm.grid_buy[t] * mm.grid_co2_kg_per_MWh[t] / 1000.0 * mm.CO2_price_EUR_per_t
            for t in mm.t
        ) * DT_H

        # Optional: demand charge in RH
        demand_cost = 0.0
        if FLAGS["demand_in_rh"]:
            mm.peak_demand = Var(domain=NonNegativeReals)
            mm.peak_demand_con = Constraint(mm.t, rule=lambda m, t: m.peak_demand >= m.grid_buy[t])
            demand_cost = mm.Leistungspreis * mm.peak_demand

        return energy_cost + fuel_cost + co2_cost + demand_cost

    m.obj = Objective(rule=objective_rule, sense=minimize)

    print(f"[RH] Modell erstellt: {T} Zeitschritte (operational mode)")
    return m


def solve_model(m: pyo.ConcreteModel, solver_name: str = SOLVER_NAME, tee: bool = SOLVER_TEE) -> Dict[str, Any]:
    """Solve Pyomo model and return results."""
    solver = SolverFactory(solver_name)

    print(f"[SOLVE] Starte Solver: {solver_name}")
    start_time = time.time()

    results = solver.solve(m, tee=tee)

    solve_time = time.time() - start_time
    print(f"[SOLVE] Fertig in {solve_time:.2f}s")

    if results.solver.termination_condition != pyo.TerminationCondition.optimal:
        print(f"[WARN] Solver nicht optimal: {results.solver.termination_condition}")

    return {
        "status": str(results.solver.termination_condition),
        "solve_time": solve_time,
        "objective": pyo_val(m.obj) if hasattr(m, "obj") else None,
    }


def extract_results(m: pyo.ConcreteModel) -> Dict[str, pd.DataFrame]:
    """Extract results from solved model."""
    T = len(m.t)

    results = {}

    # Heat production
    hp_data = {f"HP{i}_Q_th": [pyo_val(m.HP_Q_th[i, t]) for t in m.t] for i in m.HP}
    hp_data["HKW_Q"] = [pyo_val(m.HKW_Q[t]) for t in m.t]
    hp_data["GTOST_Q"] = [pyo_val(m.GTOST_Q[t]) for t in m.t]
    hp_data["P2H_Q"] = [pyo_val(m.P2H_Q[t]) for t in m.t]
    hp_data["BMHKW_Q"] = [pyo_val(m.BMHKW_Q[t]) for t in m.t]
    hp_data["HWS_Q"] = [pyo_val(m.HWS_Q[t]) for t in m.t]
    hp_data["HWW_Q"] = [pyo_val(m.HWW_Q[t]) for t in m.t]
    hp_data["AVA_Q"] = [pyo_val(m.AVA_Q[t]) for t in m.t]

    results["heat_production"] = pd.DataFrame(hp_data)

    # Storage
    storage_data = {
        "level": [pyo_val(m.storage_level[t]) for t in m.t],
        "charge": [pyo_val(m.storage_charge[t]) for t in m.t],
        "discharge": [pyo_val(m.storage_discharge[t]) for t in m.t],
    }
    results["storage"] = pd.DataFrame(storage_data)

    # Grid
    grid_data = {
        "buy": [pyo_val(m.grid_buy[t]) for t in m.t],
        "sell": [pyo_val(m.grid_sell[t]) for t in m.t],
    }
    results["grid"] = pd.DataFrame(grid_data)

    # Design (if variables not fixed)
    design = {}
    if not m.storage_capacity.is_fixed():
        design["storage_capacity"] = pyo_val(m.storage_capacity)
        design["storage_power"] = pyo_val(m.storage_power)

    hp_caps = {}
    for i in m.HP:
        if not m.HP_cap[i].is_fixed():
            hp_caps[i] = pyo_val(m.HP_cap[i])
    if hp_caps:
        design["HP_cap"] = hp_caps

    results["design"] = design

    return results


# ==============================
# 4) Export-Funktionen
# ==============================

def export_results_to_excel(
    results: Dict[str, Any],
    filepath: str,
    input_df: pd.DataFrame = None
):
    """Export results to Excel file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # Input data
        if input_df is not None:
            _excel_safe_df(input_df).to_excel(writer, sheet_name="Input_Data")

        # Results
        for sheet_name, df in results.items():
            if isinstance(df, pd.DataFrame):
                _excel_safe_df(df).to_excel(writer, sheet_name=sheet_name)
            elif isinstance(df, dict):
                # Convert dict to DataFrame
                pd.DataFrame([df]).to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"[EXPORT] Ergebnisse exportiert nach: {filepath}")


def export_design_to_json(design: Dict[str, Any], filepath: str):
    """Export design parameters to JSON."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w") as f:
        json.dump(design, f, indent=2)

    print(f"[EXPORT] Design exportiert nach: {filepath}")


# ==============================
# 5) Rolling Horizon Executor
# ==============================

def run_rolling_horizon(
    df_full: pd.DataFrame,
    design: Dict[str, Any],
    horizon_hours: int = HEAT_HORIZON_HOURS,
    step_hours: int = STEP_HOURS
) -> pd.DataFrame:
    """Execute rolling horizon optimization."""

    print(f"\n{'='*70}")
    print(f"ROLLING HORIZON")
    print(f"Horizon: {horizon_hours}h, Step: {step_hours}h")
    print(f"{'='*70}\n")

    results_list = []
    soc_current = 0.0

    t_start = 0
    while t_start < len(df_full):
        t_end = min(t_start + horizon_hours, len(df_full))
        df_window = df_full.iloc[t_start:t_end].copy()

        print(f"[RH] Fenster {t_start}-{t_end} ({len(df_window)}h)")

        # Build and solve RH model
        m = build_rh_model(df_window, design)
        m.SOC_init.set_value(soc_current)

        solve_result = solve_model(m)

        if solve_result["status"] != "optimal":
            print(f"[WARN] RH-Fenster nicht optimal gelöst: {solve_result['status']}")

        # Extract results (only first step_hours)
        n_commit = min(step_hours, len(df_window))

        window_results = extract_results(m)
        for key, df_res in window_results.items():
            if isinstance(df_res, pd.DataFrame):
                df_commit = df_res.iloc[:n_commit].copy()
                df_commit.index = df_full.index[t_start:t_start+n_commit]
                results_list.append((key, df_commit))

        # Update SOC for next window
        if n_commit > 0:
            soc_current = pyo_val(m.storage_level[n_commit])

        # Move forward
        t_start += step_hours

    # Combine all windows
    combined = {}
    for key, df_chunk in results_list:
        if key not in combined:
            combined[key] = []
        combined[key].append(df_chunk)

    final_results = {k: pd.concat(v) for k, v in combined.items() if v}

    print(f"\n[RH] Fertig: {len(final_results)} Ergebnistabellen")
    return final_results


# ==============================
# 6) Main Execution
# ==============================

def main():
    """Main execution function."""
    print(f"\n{'='*70}")
    print(f"START: {SCENARIO_TITLE}")
    print(f"{'='*70}\n")

    # Load input data
    df_input = load_input_excel(
        INPUT_XLSX,
        sheet_name=INPUT_SHEET,
        year_target=YEAR_TARGET,
        dt_hours=DT_H,
        gap_strategy="interp"
    )

    design = {}
    pf_results = None
    rh_results = None

    # === Planning Framework ===
    if RUN_MODE in {"PF_ONLY", "PF_THEN_RH"}:
        print(f"\n{'='*70}")
        print(f"PLANNING FRAMEWORK (PF)")
        print(f"{'='*70}\n")

        m_pf = build_pf_model(df_input)
        solve_result = solve_model(m_pf)

        pf_results = extract_results(m_pf)
        design = pf_results.get("design", {})

        print(f"\n[PF] Design-Ergebnisse:")
        print(f"  Storage Capacity: {design.get('storage_capacity', 0):.2f} MWh")
        print(f"  Storage Power:    {design.get('storage_power', 0):.2f} MW")
        if "HP_cap" in design:
            for i, cap in design["HP_cap"].items():
                print(f"  HP{i} Capacity:    {cap:.2f} MW")
        print(f"  Objective:        {solve_result['objective']:.2f} EUR")

        # Export design
        export_design_to_json(design, PF_DESIGN_JSON)

    # === Rolling Horizon ===
    if RUN_MODE in {"RH_ONLY", "PF_THEN_RH"}:
        if RUN_MODE == "RH_ONLY":
            # Load design from JSON
            if os.path.exists(PF_DESIGN_JSON):
                with open(PF_DESIGN_JSON, "r") as f:
                    design = json.load(f)
                print(f"[RH] Design geladen aus: {PF_DESIGN_JSON}")
            else:
                raise RuntimeError(f"Design-Datei nicht gefunden: {PF_DESIGN_JSON}")

        rh_results = run_rolling_horizon(
            df_input,
            design,
            horizon_hours=HEAT_HORIZON_HOURS,
            step_hours=STEP_HOURS
        )

    # === Export ===
    print(f"\n{'='*70}")
    print(f"EXPORT")
    print(f"{'='*70}\n")

    if pf_results and RUN_MODE in {"PF_ONLY", "PF_THEN_RH"}:
        pf_export_path = str(Path(EXPORT_BASE_DIR) / f"{SCENARIO_TITLE}_PF.xlsx")
        export_results_to_excel(pf_results, pf_export_path, df_input)

    if rh_results and RUN_MODE in {"RH_ONLY", "PF_THEN_RH"}:
        rh_export_path = str(Path(EXPORT_BASE_DIR) / f"{SCENARIO_TITLE}_RH.xlsx")
        export_results_to_excel(rh_results, rh_export_path, df_input)

    # Combined scenario workbook
    if RUN_MODE == "PF_THEN_RH" and pf_results and rh_results:
        combined_export = str(Path(EXPORT_BASE_DIR) / f"{SCENARIO_TITLE}_Combined.xlsx")
        all_results = {**pf_results, **{f"RH_{k}": v for k, v in rh_results.items()}}
        export_results_to_excel(all_results, combined_export, df_input)

    print(f"\n{'='*70}")
    print(f"FERTIG: {SCENARIO_TITLE}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
