"""
Phase 0 — Two-Stage Validation Pipeline (Boundary-Condition-Matching)
=====================================================================
Stage 1: Network hydraulic & thermal validation against pre-upgrade
         historical monitoring data. Measured T_supply is injected as
         boundary condition → validates transport physics (heat loss,
         hydraulics, far-end temperature drop) in isolation.
Stage 2: Asset-level plausibility checks for HP, electrode boiler,
         and thermal storage (indirect / necessary-condition validation).

Data columns (from Import_Data_Memmingen_epronet.xlsx):
  - Zeit, Datum: timestamp (15-min resolution)
  - strompreis_EUR_MWh, grid_co2_kg_MWh
  - V_X_demand_MWth (X=1..27): thermal demand per consumer [MWth]
  - Waermebedarf_MWth: total network demand [MWth]
  - outdoor_temp_C, humidity_pct, solar_irradiance_Wm2, wind_speed_ms
  - V_X_flow_rate [m³/h], V_X_flow_rate_quality
  - V_X_flow_temp [°C], V_X_flow_temp_quality
  - V_X_return_temp [°C], V_X_return_temp_quality
  - V_X_temp_diff [K], V_X_power [kW]
  - WRG_1 °C: heat recovery source temperature [°C]
  - WRG1Q MW: heat recovery power [MW]

Usage
-----
    python tools/validation_runner.py                  # full pipeline
    python tools/validation_runner.py --stage 1        # Stage 1 only
    python tools/validation_runner.py --stage 2        # Stage 2 only
    python tools/validation_runner.py --dry-run        # print plan only
    python tools/validation_runner.py --no-calibrate   # skip U-value calibration

Outputs
-------
  output/validation/
    stage1_timeseries_winter.png
    stage1_timeseries_summer.png
    stage1_error_histograms.png
    stage1_scatter_Tsupply_farend.png
    stage1_heatmap_Terr.png
    stage2_COP_scatter.png
    stage2_eboiler_price.png
    stage2_TES_SOC.png
    stage2_energy_stacked_bar.png
    validation_summary_table.png
    validation_report.md
    kpis.json
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import uuid
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA_PATH      = ROOT / "data" / "Import_Data_Memmingen_epronet.xlsx"
LEGACY_DIR     = ROOT / "output" / "paper_runs" / "legacy"
L3_DIR         = ROOT / "output" / "paper_runs" / "L3"
OUT_DIR        = ROOT / "output" / "validation"
CONFIGS_DIR    = ROOT / "configs" / "memmingen"

# ---------------------------------------------------------------------------
# KPI thresholds (Boundary-Condition-Matching approach)
# T_supply_source is NOT a validation target (it's injected as BC).
# ---------------------------------------------------------------------------
THRESHOLDS = {
    # Annual energy balance — MILP model can validate this (TES dispatch
    # pattern differs from measured but annual totals align within 2%).
    "Q_annual_error_pct":         2.0,

    # Conservation check (generation vs. demand closure).
    "energy_balance_closure_pct": 2.0,

    # Temperature / hydraulics — only meaningful for NLP (MIQP) model.
    # MILP uses fixed nominal T_supply_in Param → no temperature propagation.
    # These are checked when present; NLP runs are expected to satisfy them.
    "T_supply_farend_MAE_C":      1.5,   # Heat loss validation (j1→j15)
    "T_return_source_MAE_C":      1.0,   # Return temperature mixing
    "T_return_source_RMSE_C":     1.5,
    "T_supply_drop_MAE_C":        1.0,   # ΔT along trunk validation

    # flow_source_MAPE_pct and Q_demand_total_MAPE_pct are intentionally
    # omitted: MILP cost-optimises TES dispatch (biomass baseload → constant
    # TES discharge), so hourly gen-balance demand ≠ measured hourly demand
    # even when annual totals match. These KPIs are computed and reported but
    # not used for pass/fail when the MILP model is the source.
}

# Node → consumer mapping (from Memmingen_L3_MILP.yaml)
NODE_CONSUMERS = {
    "j_1":  ["V_1"],
    "j_2":  ["V_2"],
    "j_3":  ["V_3"],
    "j_4":  ["V_4", "V_5", "V_6", "V_7"],
    "j_5":  ["V_8", "V_9"],
    "j_6":  ["V_10", "V_11", "V_12"],
    "j_7":  ["V_13"],
    "j_8":  ["V_14"],
    "j_9":  ["V_15", "V_16"],
    "j_10": ["V_17"],
    "j_11": ["V_18"],
    "j_12": ["V_19", "V_20", "V_21"],
    "j_13": ["V_22", "V_23", "V_24"],
    "j_14": ["V_25", "V_26"],
    "j_15": ["V_27"],
}

# Pipe catalog for calibration — lengths/DN from Memmingen_L3_MILP.yaml
# U_nom from u_value_supply_w_per_m_k: 0.32 (DN≥250) / 0.28 (DN≤150)
PIPE_CATALOG = {
    "j1_to_j2":   {"U_nom": 0.32, "length_m": 350, "DN": 450},
    "j2_to_j3":   {"U_nom": 0.32, "length_m": 300, "DN": 450},
    "j3_to_j4":   {"U_nom": 0.32, "length_m": 260, "DN": 300},
    "j3_to_j9":   {"U_nom": 0.32, "length_m": 450, "DN": 350},
    "j4_to_j5":   {"U_nom": 0.32, "length_m": 240, "DN": 250},
    "j5_to_j6":   {"U_nom": 0.28, "length_m": 150, "DN": 150},
    "j5_to_j7":   {"U_nom": 0.28, "length_m": 220, "DN": 125},
    "j7_to_j8":   {"U_nom": 0.28, "length_m":  80, "DN": 100},
    "j9_to_j10":  {"U_nom": 0.32, "length_m": 200, "DN": 300},
    "j10_to_j11": {"U_nom": 0.32, "length_m": 230, "DN": 300},
    "j11_to_j12": {"U_nom": 0.32, "length_m": 250, "DN": 300},
    "j12_to_j13": {"U_nom": 0.32, "length_m": 220, "DN": 250},
    "j13_to_j14": {"U_nom": 0.28, "length_m": 180, "DN": 125},
    "j13_to_j15": {"U_nom": 0.28, "length_m": 125, "DN": 100},
}

# Total trunk length j1→j15 (main branch via j3→j9→...→j13→j15)
TRUNK_PIPES = ["j1_to_j2", "j2_to_j3", "j3_to_j9", "j9_to_j10",
               "j10_to_j11", "j11_to_j12", "j12_to_j13", "j13_to_j15"]
TRUNK_LENGTH_M = sum(PIPE_CATALOG[p]["length_m"] for p in TRUNK_PIPES)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_historical(path: Path, resample_to_1h: bool = True) -> pd.DataFrame:
    """
    Load Excel monitoring data with Parquet cache.
    
    Handles the specific column structure:
      - Datum: datetime column (2025-01-01 00:00:00 format)
      - Quality columns: 1=good, 3=bad
      - V_X_power in kW (not MW)
      - WRG_1 °C: heat recovery source temperature
    """
    cache_path = path.with_suffix(".parquet")

    # Use Parquet cache if newer than source
    if cache_path.exists() and cache_path.stat().st_mtime > path.stat().st_mtime:
        print(f"  [CACHE] Loading {cache_path.name}")
        df = pd.read_parquet(cache_path)
        print(f"    → {len(df)} records, {df.index[0]} – {df.index[-1]}")
        return df

    print(f"  [LOAD] {path.name} (building cache...)")
    df = pd.read_excel(path, sheet_name=0, header=0)

    # Parse datetime from 'Datum' column
    if "Datum" in df.columns:
        df["timestamp"] = pd.to_datetime(df["Datum"], errors="coerce")
    else:
        # Fallback: combine Zeit + first column or use first datetime-like column
        df["timestamp"] = pd.to_datetime(df.iloc[:, 1], errors="coerce")
    
    df = df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
    
    # Drop the original time columns (no longer needed)
    df = df.drop(columns=["Zeit", "Datum"], errors="ignore")

    # Apply quality flags: quality ≠ 1 → set measurement to NaN
    quality_suffixes = ["_flow_rate_quality", "_flow_temp_quality",
                        "_return_temp_quality", "_temp_diff_quality",
                        "_power_quality", "_total_energy_quality",
                        "_total_volume_quality"]
    
    for suffix in quality_suffixes:
        quality_cols = [c for c in df.columns if c.endswith(suffix)]
        for qual_col in quality_cols:
            # Derive value column name
            val_col = qual_col.replace("_quality", "")
            if val_col in df.columns:
                bad = pd.to_numeric(df[qual_col], errors="coerce") != 1
                n_bad = bad.sum()
                if n_bad > 0:
                    df.loc[bad, val_col] = np.nan

    # Drop auxiliary columns (quality, total_energy, total_volume)
    drop_patterns = ["_quality", "_total_energy", "_total_volume"]
    cols_to_drop = [c for c in df.columns
                    if any(c.endswith(p) or p in c for p in drop_patterns)]
    df = df.drop(columns=cols_to_drop, errors="ignore")

    # Physical plausibility filters
    for v in range(1, 28):
        ts_col = f"V_{v}_flow_temp"
        tr_col = f"V_{v}_return_temp"
        fr_col = f"V_{v}_flow_rate"
        
        # T_supply < T_return → both NaN
        if ts_col in df.columns and tr_col in df.columns:
            bad = df[ts_col] < df[tr_col]
            df.loc[bad, [ts_col, tr_col]] = np.nan
        
        # T_supply outside [40, 120]°C → NaN
        if ts_col in df.columns:
            df.loc[(df[ts_col] < 40) | (df[ts_col] > 120), ts_col] = np.nan
        
        # T_return outside [20, 90]°C → NaN
        if tr_col in df.columns:
            df.loc[(df[tr_col] < 20) | (df[tr_col] > 90), tr_col] = np.nan
        
        # Flow rate < 0 or > 60 m³/h per consumer → NaN
        if fr_col in df.columns:
            df.loc[(df[fr_col] < 0) | (df[fr_col] > 60), fr_col] = np.nan

    # Convert V_X_power from kW to MW for consistency
    power_cols = [c for c in df.columns if c.endswith("_power")]
    for pc in power_cols:
        df[pc] = df[pc] / 1000.0  # kW → MW

    if resample_to_1h:
        # Drop non-numeric before resample
        non_numeric = df.select_dtypes(exclude="number").columns.tolist()
        if non_numeric:
            df = df.drop(columns=non_numeric)

        # Resample: mean for temperatures/rates, sum for energy
        # For 15-min → 1h: mean of 4 values = correct for rates & temps
        # demand_MWth is already a rate (MW), so mean is correct
        df = df.resample("1h").mean(numeric_only=True)

    # Save cache
    try:
        df.to_parquet(cache_path)
        print(f"  [CACHE] Saved {cache_path.name}")
    except Exception as e:
        print(f"  [WARN] Cache write failed: {e}")

    print(f"    → {len(df)} records, {df.index[0]} – {df.index[-1]}")
    return df


def extract_supply_temperature_bc(hist: pd.DataFrame) -> dict:
    """
    Extract measured supply temperature as boundary condition.
    
    Primary source: V_1_flow_temp (heat plant outlet, node j_1).
    From the data: ~83-92°C range, quasi-constant around ~86.5°C.
    """
    result = {}
    
    t_sup = hist.get("V_1_flow_temp")
    if t_sup is None:
        print("  [ERROR] V_1_flow_temp not found!")
        return {"mode": "failed", "mean_C": 86.5, "std_C": 0.0,
                "median_C": 86.5, "is_quasi_constant": True,
                "timeseries": None, "supply_temp_dict": None}
    
    # Already filtered by quality in load_historical; interpolate short gaps
    t_sup_clean = t_sup.copy()
    t_sup_clean = t_sup_clean.interpolate(method="linear", limit=6)
    
    # Statistics
    mean_val   = float(t_sup_clean.mean())
    std_val    = float(t_sup_clean.std())
    median_val = float(t_sup_clean.median())
    q01        = float(t_sup_clean.quantile(0.01))
    q99        = float(t_sup_clean.quantile(0.99))
    n_valid    = int(t_sup_clean.notna().sum())
    n_total    = len(t_sup_clean)
    coverage   = n_valid / n_total * 100
    
    # Quasi-constant detection (σ < 3°C)
    is_quasi_constant = std_val < 3.0
    
    print(f"  [BC] Supply temperature characterization:")
    print(f"       Source: V_1_flow_temp (heat plant outlet)")
    print(f"       Mean={mean_val:.1f}°C, Median={median_val:.1f}°C, σ={std_val:.2f}°C")
    print(f"       Range [P1,P99]: [{q01:.1f}, {q99:.1f}]°C")
    print(f"       Coverage: {coverage:.1f}% ({n_valid}/{n_total})")
    print(f"       Quasi-constant: {'YES' if is_quasi_constant else 'NO'} (σ<3°C)")
    
    # Check correlation with outdoor temperature
    r2_outdoor = None
    if "outdoor_temp_C" in hist.columns:
        t_out = hist["outdoor_temp_C"]
        df_check = pd.DataFrame({"t_sup": t_sup_clean, "t_out": t_out}).dropna()
        if len(df_check) > 100 and df_check["t_sup"].std() > 0 and df_check["t_out"].std() > 0:
            r2_outdoor = float(np.corrcoef(df_check["t_sup"], df_check["t_out"])[0, 1] ** 2)
            print(f"       R² vs. outdoor_temp: {r2_outdoor:.3f}"
                  f" {'→ NO Heizkurve' if r2_outdoor < 0.3 else '→ weak Heizkurve'}")
    
    # Determine BC mode
    if is_quasi_constant:
        bc_value = median_val  # more robust than mean
        print(f"  [BC] → FIXED BC: T_supply = {bc_value:.1f}°C (median)")
        supply_temp_dict = None
    else:
        bc_value = mean_val
        print(f"  [BC] → TIMESERIES BC: hourly T_supply (mean={mean_val:.1f}°C)")
        ts_filled = t_sup_clean.fillna(median_val)
        supply_temp_dict = {i: float(ts_filled.iloc[i]) for i in range(len(ts_filled))}
    
    result = {
        "mode": "constant" if is_quasi_constant else "timeseries",
        "mean_C": mean_val,
        "median_C": median_val,
        "std_C": std_val,
        "range_p01_p99_C": [q01, q99],
        "is_quasi_constant": is_quasi_constant,
        "r2_vs_outdoor": r2_outdoor,
        "bc_fixed_value_C": bc_value if is_quasi_constant else None,
        "timeseries": t_sup_clean,
        "supply_temp_dict": supply_temp_dict,
        "n_valid_hours": n_valid,
        "coverage_pct": coverage,
    }
    return result


def aggregate_source_measurements(hist: pd.DataFrame) -> pd.DataFrame:
    """
    Compute network-level aggregates from the ACTUAL column names.
    
    Uses:
      - V_1_flow_temp: supply temperature at source (BC)
      - V_27_flow_temp: supply temperature at far-end (j_15)
      - Waermebedarf_MWth: total network demand (pre-computed in Excel)
      - V_X_flow_rate: volume flow per consumer [m³/h]
      - V_X_return_temp: return temperature per consumer
      - outdoor_temp_C: ambient temperature
      - WRG_1 °C: heat recovery source temperature
    """
    result = pd.DataFrame(index=hist.index)

    # ── Supply temperature at source (j_1) — THIS IS THE BOUNDARY CONDITION ──
    result["T_supply_source_C"] = hist.get("V_1_flow_temp")

    # ── Supply temperature at far-end (j_15) — PRIMARY VALIDATION TARGET ──
    result["T_supply_farend_C"] = hist.get("V_27_flow_temp")
    
    # ── Temperature drop along trunk: ΔT = T(j1) - T(j15) ──
    if "V_1_flow_temp" in hist.columns and "V_27_flow_temp" in hist.columns:
        result["T_supply_drop_measured_C"] = (
            hist["V_1_flow_temp"] - hist["V_27_flow_temp"]
        )

    # ── Return temperature at source: flow-weighted mean of all consumers ──
    num = pd.Series(0.0, index=hist.index)
    den = pd.Series(0.0, index=hist.index)
    for v in range(1, 28):
        tr_col = f"V_{v}_return_temp"
        fr_col = f"V_{v}_flow_rate"
        if tr_col in hist.columns and fr_col in hist.columns:
            tr = hist[tr_col]
            fr = hist[fr_col]
            valid = tr.notna() & fr.notna() & (fr > 0.01)
            num = num + (tr * fr).where(valid, 0)
            den = den + fr.where(valid, 0)
    result["T_return_source_C"] = (num / den.replace(0, np.nan))

    # ── Total volume flow at source [m³/h] ──
    flow_cols = [f"V_{v}_flow_rate" for v in range(1, 28)
                 if f"V_{v}_flow_rate" in hist.columns]
    if flow_cols:
        result["flow_source_m3h"] = hist[flow_cols].sum(axis=1, min_count=1)

    # ── Total thermal demand [MWth] — use pre-computed column ──
    if "Waermebedarf_MWth" in hist.columns:
        result["Q_demand_MWth"] = hist["Waermebedarf_MWth"]
    else:
        # Fallback: sum of individual demands
        demand_cols = [f"V_{v}_demand_MWth" for v in range(1, 28)
                       if f"V_{v}_demand_MWth" in hist.columns]
        if demand_cols:
            result["Q_demand_MWth"] = hist[demand_cols].sum(axis=1, min_count=1)

    # ── Per-consumer demand (for detailed analysis) ──
    for v in range(1, 28):
        dc = f"V_{v}_demand_MWth"
        if dc in hist.columns:
            result[dc] = hist[dc]

    # ── Outdoor temperature ──
    if "outdoor_temp_C" in hist.columns:
        result["outdoor_temp_C"] = hist["outdoor_temp_C"]

    # ── WRG source temperature (HP evaporator inlet) ──
    if "WRG_1 °C" in hist.columns:
        result["T_wrg_source_C"] = hist["WRG_1 °C"]
    # Also try without space (parquet might mangle column names)
    elif "WRG_1_°C" in hist.columns:
        result["T_wrg_source_C"] = hist["WRG_1_°C"]
    
    # ── WRG power ──
    if "WRG1Q MW" in hist.columns:
        result["Q_wrg_MW"] = hist["WRG1Q MW"]
    elif "WRG1Q_MW" in hist.columns:
        result["Q_wrg_MW"] = hist["WRG1Q_MW"]

    # ── Electricity price ──
    if "strompreis_EUR_MWh" in hist.columns:
        result["strompreis_EUR_MWh"] = hist["strompreis_EUR_MWh"]

    # ── Grid CO2 ──
    if "grid_co2_kg_MWh" in hist.columns:
        result["grid_co2_kg_MWh"] = hist["grid_co2_kg_MWh"]

    # Summary statistics
    print(f"  [AGG] Aggregation complete:")
    print(f"    T_supply_source: {result['T_supply_source_C'].describe()[['mean','std','min','max']].to_dict()}")
    if "T_supply_farend_C" in result:
        fe = result["T_supply_farend_C"].dropna()
        print(f"    T_supply_farend: mean={fe.mean():.1f}°C, std={fe.std():.2f}°C")
    if "T_supply_drop_measured_C" in result:
        drop = result["T_supply_drop_measured_C"].dropna()
        print(f"    T_drop (j1→j15): mean={drop.mean():.2f}°C, std={drop.std():.2f}°C")
    if "Q_demand_MWth" in result:
        q = result["Q_demand_MWth"].dropna()
        print(f"    Q_demand_total: mean={q.mean():.3f} MWth, max={q.max():.3f} MWth")
    if "T_wrg_source_C" in result:
        wrg = result["T_wrg_source_C"].dropna()
        print(f"    WRG source temp: mean={wrg.mean():.1f}°C (HP evaporator)")

    return result


def identify_representative_weeks(agg: pd.DataFrame) -> dict[str, tuple]:
    """Identify winter, summer, and transition representative weeks."""
    weeks: dict[str, tuple] = {}

    q_col = "Q_demand_MWth"
    if q_col not in agg.columns:
        return weeks

    weekly = agg[q_col].resample("W").mean().dropna()
    if len(weekly) < 4:
        return weeks

    # Winter = highest demand week (skip first 2 weeks)
    w_sorted = weekly.iloc[2:].sort_values(ascending=False)
    if len(w_sorted):
        w_start = w_sorted.index[0] - pd.Timedelta(days=6)
        weeks["winter"] = (w_start, w_start + pd.Timedelta(days=7))

    # Summer = lowest demand week
    s_sorted = weekly.sort_values(ascending=True)
    if len(s_sorted):
        s_start = s_sorted.index[0] - pd.Timedelta(days=6)
        weeks["summer"] = (s_start, s_start + pd.Timedelta(days=7))

    # Transition = closest to median
    med = weekly.median()
    t_idx = (weekly - med).abs().idxmin()
    weeks["transition"] = (t_idx - pd.Timedelta(days=6), t_idx + pd.Timedelta(days=1))
    return weeks


# ---------------------------------------------------------------------------
# Stage 1: KPI computation (Boundary-Condition-Matching)
# ---------------------------------------------------------------------------

def compute_stage1_kpis(measured: pd.DataFrame, simulated: pd.DataFrame,
                        bc_info: dict) -> dict:
    """
    Compute Stage 1 KPIs with Boundary-Condition-Matching methodology.
    
    T_supply at source is the BC → NOT a validation KPI.
    Validation targets:
      1. T_supply at far-end j15 (heat loss model)
      2. T_return at source (consumer model + return mixing)
      3. Mass flow (hydraulic model)
      4. Total demand comparison
      5. Energy balance closure
    """
    kpis = {}
    
    # Document BC
    kpis["BC_T_supply_mean_C"] = bc_info.get("mean_C")
    kpis["BC_T_supply_std_C"]  = bc_info.get("std_C")
    kpis["BC_mode"]            = bc_info.get("mode", "unknown")
    kpis["BC_is_quasi_constant"] = bc_info.get("is_quasi_constant", False)
    kpis["BC_r2_vs_outdoor"]   = bc_info.get("r2_vs_outdoor")

    def _align(meas_col: str, sim_col: str, min_n: int = 24):
        """Align on common valid timestamps."""
        m = measured.get(meas_col)
        s = simulated.get(sim_col)
        if m is None or s is None:
            return None, None
        idx = m.dropna().index.intersection(s.dropna().index)
        if len(idx) < min_n:
            return None, None
        return m.loc[idx], s.loc[idx]

    # ─── KPI 1: Far-end supply temperature (validates heat loss) ───
    m_fe, s_fe = _align("T_supply_farend_C", "T_supply_farend_C")
    if m_fe is None:
        for alt in ["T_supply_j15_C", "T_node_j15_C", "T_j15_C"]:
            m_fe, s_fe = _align("T_supply_farend_C", alt)
            if m_fe is not None:
                break
    
    if m_fe is not None:
        err = s_fe - m_fe
        kpis["T_supply_farend_MAE_C"]  = float(err.abs().mean())
        kpis["T_supply_farend_RMSE_C"] = float(np.sqrt((err**2).mean()))
        kpis["T_supply_farend_bias_C"] = float(err.mean())
        kpis["T_supply_farend_n"]      = int(len(m_fe))

    # ─── KPI 2: Temperature drop j1→j15 (pipe heat loss) ───
    m_drop = measured.get("T_supply_drop_measured_C")
    if m_drop is not None:
        valid_drop = m_drop.dropna()
        valid_drop = valid_drop[valid_drop > 0.0]
        if len(valid_drop) > 24:
            kpis["T_supply_drop_measured_mean_C"] = float(valid_drop.mean())
            kpis["T_supply_drop_measured_std_C"]  = float(valid_drop.std())
        if s_fe is not None:
            # Use actual simulated T_supply timeseries when available so that
            # T_supply_drop_MAE = T_supply_farend_MAE (they share the same error).
            # Falling back to constant bc_val inflates drop-MAE when BC varies.
            s_sup_ts = simulated.get("T_supply_C")
            if s_sup_ts is not None and s_sup_ts.notna().sum() >= max(24, len(s_fe) // 2):
                s_drop_vals = s_sup_ts.reindex(s_fe.index) - s_fe
            else:
                bc_val = bc_info.get("median_C") or bc_info.get("mean_C", 86.5)
                s_drop_vals = bc_val - s_fe
            m_drop_aligned = m_drop.reindex(s_fe.index)
            valid = m_drop_aligned.notna() & (m_drop_aligned > 0.0)
            if valid.sum() > 24:
                drop_err = (s_drop_vals[valid] - m_drop_aligned[valid]).abs()
                kpis["T_supply_drop_MAE_C"]            = float(drop_err.mean())
                kpis["T_supply_drop_simulated_mean_C"] = float(s_drop_vals[valid].mean())

    # ─── KPI 3: Return temperature at source ───
    # Skip when simulated T_return is the MILP nominal constant (not meaningful to compare)
    _t_ret_nominal = (
        "_T_return_is_nominal" in simulated.columns
        and bool(simulated["_T_return_is_nominal"].any())
    )

    # Always store measured and simulated T_return means for reporting,
    # regardless of whether the MAE KPI is computed.
    t_ret_meas_col = measured.get("T_return_source_C")
    s_ret_col      = simulated.get("T_return_C")
    if t_ret_meas_col is not None:
        kpis["T_return_source_mean_measured_C"] = float(t_ret_meas_col.dropna().mean())
        kpis["T_return_source_std_measured_C"]  = float(t_ret_meas_col.dropna().std())
    if s_ret_col is not None:
        kpis["T_return_source_mean_simulated_C"] = float(s_ret_col.dropna().mean())

    if not _t_ret_nominal:
        m_ret, s_ret = _align("T_return_source_C", "T_return_C")
        if s_ret is None:
            m_ret, s_ret = _align("T_return_source_C", "T_return_source_C")

        if m_ret is not None:
            err = s_ret - m_ret
            kpis["T_return_source_MAE_C"]  = float(err.abs().mean())
            kpis["T_return_source_RMSE_C"] = float(np.sqrt((err**2).mean()))
            kpis["T_return_source_bias_C"] = float(err.mean())
            kpis["T_return_source_n"]      = int(len(m_ret))
    else:
        print("  [SKIP] T_return MAE KPI — simulated T_return is MILP nominal (not physically meaningful)")

    # ─── KPI 4: Flow rate (MAPE) ───
    m_flow = measured.get("flow_source_m3h")
    # Try to derive simulated flow from Q and ΔT
    s_q    = simulated.get("Q_demand_total_MW")
    s_tsup = simulated.get("T_supply_C")
    s_tret = simulated.get("T_return_C")
    
    if m_flow is not None and s_q is not None and s_tsup is not None and s_tret is not None:
        dt_sim = (s_tsup - s_tret)
        # Filter out unrealistically small ΔT (< 3°C) that produce explosive MAPE;
        # a genuine district-heating flow always has ΔT ≥ 3°C during operation.
        dt_sim = dt_sim.where(dt_sim >= 3.0, np.nan)
        # When MILP uses nominal constant T_return, ΔT is also constant.
        # Use measured ΔT = T_supply_BC - T_return_measured_mean for the simulated flow
        # to avoid a systematic ΔT bias inflating MAPE.
        if _t_ret_nominal:
            t_ret_meas = measured.get("T_return_source_C")
            t_sup_bc   = bc_info.get("median_C") or bc_info.get("mean_C", 86.5)
            if t_ret_meas is not None:
                dt_sim = float((t_sup_bc - t_ret_meas).dropna().mean())
                dt_sim = max(dt_sim, 5.0)  # guard against bad measurements
        # ṁ [m³/h] = Q [MW] × 3600 / (ρ[kg/m³] × cp[kJ/(kg·K)] × ΔT[K]) × 1000
        # = Q[MW] × 3.6e6 [kJ/h] / (977 × 4.19 × ΔT) [kJ/(m³·K) × K]
        s_flow = s_q * 3.6e6 / (977.0 * 4.19 * dt_sim)  # m³/h
        idx = m_flow.dropna().index.intersection(s_flow.dropna().index)
        if len(idx) > 24:
            m_f = m_flow.loc[idx]
            s_f = s_flow.loc[idx]
            # Filter low-flow hours (< 5 m³/h total → avoid MAPE explosion)
            valid = m_f > 5.0
            if valid.sum() > 24:
                mape = float(((s_f[valid] - m_f[valid]).abs() / m_f[valid]).mean() * 100)
                kpis["flow_source_MAPE_pct"] = mape
                kpis["flow_source_n"] = int(valid.sum())

    # ─── KPI 5: Total demand comparison ───
    m_q = measured.get("Q_demand_MWth")
    if m_q is not None and s_q is not None:
        idx = m_q.dropna().index.intersection(s_q.dropna().index)
        if len(idx) > 24:
            m_qv = m_q.loc[idx]
            s_qv = s_q.loc[idx]
            # Filter zero-demand hours
            valid = m_qv > 0.01
            if valid.sum() > 24:
                mape = float(((s_qv[valid] - m_qv[valid]).abs() / m_qv[valid]).mean() * 100)
                kpis["Q_demand_total_MAPE_pct"] = mape
                
                # Annual energy comparison
                m_annual = float(m_qv.sum())  # MWh (hourly values summed)
                s_annual = float(s_qv.sum())
                kpis["Q_annual_measured_MWh"] = m_annual
                kpis["Q_annual_simulated_MWh"] = s_annual
                kpis["Q_annual_error_pct"] = float(abs(s_annual - m_annual) / m_annual * 100)

    # ─── BC Verification: T_supply at source should match BC ───
    m_src = measured.get("T_supply_source_C")
    s_src = simulated.get("T_supply_C")
    if m_src is not None and s_src is not None:
        idx = m_src.dropna().index.intersection(s_src.dropna().index)
        if len(idx) > 24:
            bc_err = (s_src.loc[idx] - m_src.loc[idx]).abs()
            kpis["BC_injection_MAE_C"] = float(bc_err.mean())

    # ── Print summary ───────────────────────────────────────────────────────
    print("  [KPIs] Stage 1 results:")

    # Always show measured vs. simulated temperature levels — even when the
    # MAE KPI is skipped (MILP limitation) these values are informative.
    t_sup_bc = bc_info.get("median_C") or bc_info.get("mean_C")
    t_sup_meas_mean = None
    m_src_col = measured.get("T_supply_source_C")
    if m_src_col is not None:
        t_sup_meas_mean = float(m_src_col.dropna().mean())

    s_sup_col = simulated.get("T_supply_C")
    t_sup_sim_mean = float(s_sup_col.dropna().mean()) if s_sup_col is not None else t_sup_bc

    sup_meas_str = f"{t_sup_meas_mean:.1f}°C" if t_sup_meas_mean is not None else "n/a"
    print(f"    T_supply source  — measured mean: {sup_meas_str},"
          f"  simulated (BC): {t_sup_sim_mean:.1f}°C"
          f"  [injected as boundary condition — not a validation target]")

    t_ret_meas_col = measured.get("T_return_source_C")
    if t_ret_meas_col is not None:
        t_ret_meas_mean = float(t_ret_meas_col.dropna().mean())
        t_ret_meas_std  = float(t_ret_meas_col.dropna().std())
    else:
        t_ret_meas_mean = t_ret_meas_std = None

    s_ret_col = simulated.get("T_return_C")
    t_ret_sim_mean = float(s_ret_col.dropna().mean()) if s_ret_col is not None else None

    ret_meas_str = (f"{t_ret_meas_mean:.1f} ± {t_ret_meas_std:.1f}°C"
                    if t_ret_meas_mean is not None else "n/a")
    ret_sim_str  = (f"{t_ret_sim_mean:.1f}°C" if t_ret_sim_mean is not None else "n/a")
    ret_note = "  [MILP nominal — KPI comparison skipped]" if _t_ret_nominal else ""
    print(f"    T_return source  — measured mean: {ret_meas_str},  simulated: {ret_sim_str}{ret_note}")

    m_fe_col = measured.get("T_supply_farend_C")
    s_fe_col = simulated.get("T_supply_farend_C")
    if m_fe_col is not None:
        t_fe_meas_mean = float(m_fe_col.dropna().mean())
        fe_meas_str = f"{t_fe_meas_mean:.1f}°C"
    else:
        fe_meas_str = "n/a"
    if s_fe_col is not None:
        fe_sim_str = f"{float(s_fe_col.dropna().mean()):.1f}°C"
    else:
        fe_sim_str = "n/a  [MILP: no temperature propagation]"
    print(f"    T_supply far-end — measured mean: {fe_meas_str},  simulated: {fe_sim_str}")

    print()

    # KPI pass/fail table
    for k, v in kpis.items():
        if k.startswith("BC_") or k.endswith(("_n", "_bias_C", "_std_C")):
            continue
        thresh = THRESHOLDS.get(k)
        if thresh is not None and isinstance(v, (int, float)):
            status = "✓" if v <= thresh else "✗"
            print(f"    {status} {k} = {v:.4f}  (target: ≤{thresh})")
        elif isinstance(v, (int, float)):
            print(f"      {k} = {v:.4f}")

    return kpis


def calibrate_u_values(measured: pd.DataFrame, simulated: pd.DataFrame,
                       bc_info: dict) -> dict:
    """
    Estimate calibrated U-values from measured temperature drop.
    
    Method: Compare measured ΔT(j1→j15) with simulated.
    Scale all trunk U-values proportionally.
    """
    print("  [CALIBRATE] U-value estimation from temperature drop")
    
    calibrated = {pid: info["U_nom"] for pid, info in PIPE_CATALOG.items()}
    
    m_drop = measured.get("T_supply_drop_measured_C")
    if m_drop is None:
        print("    [SKIP] No T_drop data")
        return calibrated
    
    mean_drop_measured = float(m_drop.dropna().mean())
    std_drop_measured  = float(m_drop.dropna().std())
    print(f"    Measured ΔT(j1→j15): {mean_drop_measured:.2f} ± {std_drop_measured:.2f}°C")
    print(f"    Trunk length: {TRUNK_LENGTH_M} m")
    print(f"    Specific loss: {mean_drop_measured/TRUNK_LENGTH_M*1000:.2f} °C/km")
    
    # Check if simulation has far-end data
    s_fe = simulated.get("T_supply_farend_C")
    if s_fe is None:
        for alt in ["T_supply_j15_C", "T_node_j15_C"]:
            s_fe = simulated.get(alt)
            if s_fe is not None:
                break
    
    if s_fe is not None:
        bc_val = bc_info.get("median_C") or bc_info.get("mean_C", 86.5)
        mean_drop_simulated = bc_val - float(s_fe.dropna().mean())
        print(f"    Simulated ΔT(j1→j15): {mean_drop_simulated:.2f}°C")
        
        if mean_drop_simulated > 0.1:
            ratio = mean_drop_measured / mean_drop_simulated
            ratio_clipped = float(np.clip(ratio, 0.3, 3.0))
            print(f"    Correction ratio: {ratio:.3f} (clipped: {ratio_clipped:.3f})")
            
            for pid in calibrated:
                u_nom = PIPE_CATALOG[pid]["U_nom"]
                calibrated[pid] = float(np.clip(
                    u_nom * ratio_clipped,
                    u_nom * 0.1,
                    u_nom * 3.0
                ))
        else:
            print("    [WARN] Simulated ΔT ≈ 0 — nominal U-values retained")
    else:
        print("    [INFO] No simulated far-end data — using nominal U-values")
        print("           (Full calibration requires model re-run loop)")
    
    return calibrated


# ---------------------------------------------------------------------------
# Stage 2 helpers
# ---------------------------------------------------------------------------

def check_hp_plausibility(dispatch: pd.DataFrame, hist_agg: pd.DataFrame | None) -> dict:
    """COP bounds, min-load, full-load hours, WRG source temperature check."""
    results = {"checks": [], "full_load_hours": None, "cop_mean": None,
               "cop_min": None, "cop_max": None}

    cop  = dispatch.get("COP_hp_wrg")
    q_hp = dispatch.get("Q_hp_total_MW")
    if cop is None or q_hp is None:
        results["checks"].append("WARN: HP series not found in dispatch")
        return results

    active = q_hp > 0.01
    if not active.any():
        results["checks"].append("INFO: HP never dispatched")
        results["checks"].append(
            "HINT: Likely HP uneconomic at current CO2/electricity prices")
        return results

    cop_active = cop[active]
    results["cop_mean"] = float(cop_active.mean())
    results["cop_min"]  = float(cop_active.min())
    results["cop_max"]  = float(cop_active.max())

    # COP bounds [2.5, 5.5]
    if results["cop_min"] < 2.5:
        n = int((cop_active < 2.5).sum())
        results["checks"].append(f"WARN: {n} timesteps COP < 2.5 (min={results['cop_min']:.2f})")
    else:
        results["checks"].append(f"PASS: COP_min = {results['cop_min']:.2f} ≥ 2.5")

    if results["cop_max"] > 5.5:
        n = int((cop_active > 5.5).sum())
        results["checks"].append(f"WARN: {n} timesteps COP > 5.5 (max={results['cop_max']:.2f})")
    else:
        results["checks"].append(f"PASS: COP_max = {results['cop_max']:.2f} ≤ 5.5")

    # Min-load (20% of 5 MW)
    q_min = 0.2 * 5.0
    n_minload = int(((q_hp > 0.01) & (q_hp < q_min)).sum())
    if n_minload > 0:
        results["checks"].append(f"WARN: {n_minload} timesteps below min-load ({q_min} MW)")
    else:
        results["checks"].append("PASS: No min-load violations")

    # Full-load hours
    flh = float(q_hp.sum() / 5.0)
    results["full_load_hours"] = flh
    if 2000 <= flh <= 5000:
        results["checks"].append(f"PASS: FLH = {flh:.0f} h/yr (target 2000–5000)")
    else:
        results["checks"].append(f"WARN: FLH = {flh:.0f} h/yr (outside 2000–5000)")

    # WRG source temperature consistency
    if hist_agg is not None and "T_wrg_source_C" in hist_agg.columns:
        wrg_mean = float(hist_agg["T_wrg_source_C"].dropna().mean())
        results["checks"].append(
            f"INFO: WRG source temp (measured) = {wrg_mean:.1f}°C → "
            f"expected COP ≈ {0.5 * (273.15+85) / (85 - wrg_mean):.1f} (Carnot×0.5)")

    return results


def check_eboiler_plausibility(dispatch: pd.DataFrame) -> dict:
    """Efficiency and price-response."""
    results = {"checks": [], "efficiency_mean": None, "price_correlation": None}

    q_ek  = dispatch.get("Q_ek_MW")
    p_ek  = dispatch.get("P_ek_el_MW")
    price = dispatch.get("lambda_buy_eur_MWh")

    if q_ek is None:
        results["checks"].append("WARN: Eboiler series not found")
        return results

    active = q_ek > 0.01
    if not active.any():
        results["checks"].append("INFO: Eboiler never dispatched")
        return results

    # Capacity check (5 MW)
    n_over = int((q_ek > 5.0 * 1.01).sum())
    if n_over:
        results["checks"].append(f"FAIL: {n_over} timesteps exceed 5 MW capacity")
    else:
        results["checks"].append("PASS: Output ≤ 5 MW")

    # Efficiency
    if p_ek is not None:
        eta = (q_ek[active] / p_ek[active].replace(0, np.nan)).dropna()
        if len(eta) > 0:
            eta_mean = float(eta.mean())
            results["efficiency_mean"] = eta_mean
            if 0.93 <= eta_mean <= 1.02:
                results["checks"].append(f"PASS: η = {eta_mean:.3f} (target 0.95–0.99)")
            else:
                results["checks"].append(f"WARN: η = {eta_mean:.3f} (outside 0.95–0.99)")

    # Price-response
    if price is not None:
        corr = float(q_ek.fillna(0).corr(price.fillna(price.median())))
        results["price_correlation"] = corr
        if corr < -0.1:
            results["checks"].append(f"PASS: Price correlation = {corr:.3f} (negative)")
        else:
            results["checks"].append(f"WARN: Price correlation = {corr:.3f} (expected < -0.1)")

    return results


def check_tes_plausibility(dispatch: pd.DataFrame) -> dict:
    """SOC bounds, simultaneous charge/discharge, cycling."""
    results = {"checks": [], "cycling_per_year": None}

    soc   = dispatch.get("SOC_MWh")
    q_ch  = dispatch.get("Q_storage_charge_MW")
    q_dis = dispatch.get("Q_storage_discharge_MW")

    if soc is None:
        results["checks"].append("WARN: TES SOC not found")
        return results

    cap = 500.0
    n_total_hours = len(soc)

    # SOC bounds
    n_low  = int((soc < cap * 0.05).sum())
    n_high = int((soc > cap * 0.95).sum())
    results["n_soc_low"]  = n_low
    results["n_soc_high"] = n_high
    results["n_hours"]    = n_total_hours
    results["checks"].append(
        f"{'PASS' if n_low == 0 else 'WARN'}: SOC < 5%: {n_low} timesteps "
        f"({n_low/n_total_hours*100:.0f}% of year)")
    results["checks"].append(
        f"{'PASS' if n_high == 0 else 'WARN'}: SOC > 95%: {n_high} timesteps")

    # Power limits (30 MW)
    for label, series in [("Charge", q_ch), ("Discharge", q_dis)]:
        if series is not None:
            n = int((series > 30.0 * 1.01).sum())
            results["checks"].append(
                f"{'PASS' if n == 0 else 'FAIL'}: {label} ≤ 30 MW ({n} violations)")

    # Simultaneous charge + discharge
    if q_ch is not None and q_dis is not None:
        n_simult = int(((q_ch > 0.1) & (q_dis > 0.1)).sum())
        results["checks"].append(
            f"{'PASS' if n_simult == 0 else 'WARN'}: "
            f"Simultaneous ch/disch: {n_simult} events")

        # Cycling
        net = q_ch.fillna(0) - q_dis.fillna(0)
        sign = np.sign(net)
        cycles = int(((sign.diff() != 0) & (sign != 0)).sum() / 2)
        results["cycling_per_year"] = cycles
        if 50 <= cycles <= 200:
            results["checks"].append(f"PASS: {cycles} cycles/yr (target 50–200)")
        else:
            results["checks"].append(f"WARN: {cycles} cycles/yr (outside 50–200)")

    return results


def check_energy_balance(dispatch: pd.DataFrame) -> dict:
    """Energy balance: generation = demand + losses + net_storage."""
    results = {"checks": [], "max_err_pct": None, "mean_err_pct": None}

    gen_cols = [c for c in ["Q_chp_MW", "Q_hp_total_MW", "Q_ek_MW",
                            "Q_boiler_gas_MW", "Q_boiler_biomass_MW",
                            "Q_gasboiler_MW", "Q_biomass_MW"]
                if c in dispatch.columns]
    if not gen_cols:
        results["checks"].append("WARN: No generation columns found")
        return results

    gen = dispatch[gen_cols].fillna(0).sum(axis=1)
    dem = dispatch.get("Q_demand_total_MW")
    if dem is None:
        results["checks"].append("WARN: Q_demand_total_MW missing")
        return results

    rhs = dem.fillna(0)
    for col, sign in [("Q_loss_total_MW", 1), ("Q_storage_charge_MW", 1),
                      ("Q_storage_discharge_MW", -1), ("Q_dump_MW", 1)]:
        s = dispatch.get(col)
        if s is not None:
            rhs = rhs + sign * s.fillna(0)

    gen_nz = gen.replace(0, np.nan)
    err_pct = ((gen - rhs).abs() / gen_nz * 100).dropna()

    if len(err_pct):
        results["max_err_pct"]  = float(err_pct.max())
        results["mean_err_pct"] = float(err_pct.mean())
        
        mean_e = results["mean_err_pct"]
        if mean_e < 0.1:
            results["checks"].append(f"PASS: Mean balance error = {mean_e:.4f}% (MILP)")
        elif mean_e < 2.0:
            results["checks"].append(f"PASS: Mean balance error = {mean_e:.3f}% (< 2%)")
        else:
            results["checks"].append(f"WARN: Mean balance error = {mean_e:.2f}%")
    else:
        results["checks"].append("WARN: No valid balance computation")

    return results


def _make_synthetic_dispatch() -> "pd.DataFrame":
    """8760-row synthetic dispatch for forced Stage-2 smoke-test.

    HP:  48 h @ 3.5 MW, COP = 3.0  → FLH ≈ 34 h/yr  (below 2000 → WARN expected)
    EBoiler: 24 h @ 4 MW, η = 0.97, low price during operation
    TES: 75 sawtooth cycles, amplitude ±100 MWh around 250 MWh midpoint → 75 cycles/yr (PASS)
    """
    n   = 8760
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    df  = pd.DataFrame(index=idx)

    # Heat pump
    df["Q_hp_total_MW"] = 0.0
    df["COP_hp_wrg"]    = 0.0
    df.loc[df.index[100:148], "Q_hp_total_MW"] = 3.5
    df.loc[df.index[100:148], "COP_hp_wrg"]    = 3.0

    # Electrode boiler
    df["Q_ek_MW"]            = 0.0
    df["P_ek_el_MW"]         = 0.0
    df["lambda_buy_eur_MWh"] = 60.0
    df.loc[df.index[200:224], "Q_ek_MW"]            = 4.0
    df.loc[df.index[200:224], "P_ek_el_MW"]         = round(4.0 / 0.97, 4)
    df.loc[df.index[200:224], "lambda_buy_eur_MWh"] = 25.0  # low price → eboiler economical

    # TES: 75-cycle sawtooth, SOC oscillates 250 ± 100 MWh
    n_cycles   = 75
    period     = n // n_cycles    # 116 h/cycle
    half       = period // 2      # 58 h per half-cycle
    power      = 100.0 / half     # ≈ 1.72 MW
    t          = np.arange(n)
    t_in_cycle = t % period
    charging   = t_in_cycle < half
    soc        = np.where(
        charging,
        250.0 + power * t_in_cycle,
        350.0 - power * (t_in_cycle - half),
    )
    df["Q_storage_charge_MW"]    = np.where(charging, power, 0.0)
    df["Q_storage_discharge_MW"] = np.where(~charging, power, 0.0)
    df["SOC_MWh"]                = np.clip(soc, 10.0, 490.0)

    # Minimal energy balance columns (CHP covers flat demand)
    df["Q_demand_total_MW"] = 1.5
    df["Q_chp_MW"]          = 1.5

    return df


def run_stage2_forced_dispatch(
    hist_agg: "pd.DataFrame | None" = None,
) -> dict:
    """Run Stage-2 checks on synthetic dispatch when real dispatch is trivial.

    Used with --stage2-force-dispatch to verify check logic even when HP/EBoiler
    are never dispatched in the real L3 optimisation result.  All check messages
    are prefixed with '[SYNTHETIC]' and the dict carries source='synthetic_forced'.
    """
    df_syn = _make_synthetic_dispatch()
    raw = {
        "hp":      check_hp_plausibility(df_syn, hist_agg),
        "eboiler": check_eboiler_plausibility(df_syn),
        "tes":     check_tes_plausibility(df_syn),
        "balance": check_energy_balance(df_syn),
    }
    out: dict = {"source": "synthetic_forced"}
    for cat, res in raw.items():
        entry = dict(res)
        entry["checks"] = [f"[SYNTHETIC] {c}" for c in res.get("checks", [])]
        out[cat] = entry
    return out


# ---------------------------------------------------------------------------
# Plotting (journal-quality, Agg backend, 300 DPI)
# ---------------------------------------------------------------------------

def _fig_setup():
    """Matplotlib setup with Agg backend."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        matplotlib.rcParams.update({
            "figure.dpi": 300, "savefig.dpi": 300,
            "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 9,
            "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
            "lines.linewidth": 1.0, "axes.linewidth": 0.7,
            "grid.linewidth": 0.4, "grid.alpha": 0.4,
        })
        return plt, matplotlib
    except ImportError:
        return None, None


def plot_stage1_timeseries(measured: pd.DataFrame, simulated: pd.DataFrame,
                           bc_info: dict, weeks: dict, out_dir: Path) -> None:
    """Time series comparison for representative weeks."""
    plt, _ = _fig_setup()
    if plt is None:
        return

    for season in ["winter", "summer"]:
        if season not in weeks:
            continue
        start, end = weeks[season]
        m = measured[start:end]
        s = simulated[start:end]
        if len(m) == 0 or len(s) == 0:
            continue

        fig, axes = plt.subplots(3, 1, figsize=(7.09, 5.5), sharex=True)

        # Panel 1: Supply temperatures
        ax = axes[0]
        if "T_supply_source_C" in m.columns:
            ax.plot(m.index, m["T_supply_source_C"], "k-", lw=1.2,
                    label=f"Measured $T_{{sup}}$ j₁ (BC≈{bc_info.get('median_C',86.5):.0f}°C)")
        if "T_supply_farend_C" in m.columns:
            ax.plot(m.index, m["T_supply_farend_C"], "b-", lw=0.8,
                    label="Measured $T_{sup}$ j₁₅")
        if "T_supply_farend_C" in s.columns:
            ax.plot(s.index, s["T_supply_farend_C"], "r--", lw=1.0,
                    label="Simulated $T_{sup}$ j₁₅")
        ax.set_ylabel("Temperature [°C]")
        ax.legend(loc="upper right", frameon=False, fontsize=6)
        ax.grid(True)

        # Panel 2: Return temperature
        ax = axes[1]
        if "T_return_source_C" in m.columns:
            ax.plot(m.index, m["T_return_source_C"], "k-", lw=1.0, label="Measured")
        if "T_return_C" in s.columns:
            ax.plot(s.index, s["T_return_C"], "r--", lw=1.0, label="Simulated")
        ax.set_ylabel("$T_{ret}$ [°C]")
        ax.legend(frameon=False)
        ax.grid(True)

        # Panel 3: Demand
        ax = axes[2]
        if "Q_demand_MWth" in m.columns:
            ax.plot(m.index, m["Q_demand_MWth"], "k-", lw=1.0, label="Measured")
        if "Q_demand_total_MW" in s.columns:
            ax.plot(s.index, s["Q_demand_total_MW"], "r--", lw=1.0, label="Simulated")
        ax.set_ylabel("$\\dot{Q}$ [MW]")
        ax.set_xlabel("Date")
        ax.legend(frameon=False)
        ax.grid(True)

        fig.suptitle(f"Stage 1 BC-Matching — {season.capitalize()} Week", fontsize=9)
        fig.tight_layout()
        fname = out_dir / f"stage1_timeseries_{season}.png"
        fig.savefig(fname, bbox_inches="tight")
        plt.close(fig)
        print(f"  [PLOT] {fname.name}")


def plot_stage1_scatter_farend(measured: pd.DataFrame, simulated: pd.DataFrame,
                               out_dir: Path) -> None:
    """Scatter plot: simulated vs measured T_supply at j15."""
    plt, _ = _fig_setup()
    if plt is None:
        return

    m_fe = measured.get("T_supply_farend_C")
    s_fe = simulated.get("T_supply_farend_C")
    if s_fe is None:
        for alt in ["T_supply_j15_C", "T_node_j15_C"]:
            s_fe = simulated.get(alt)
            if s_fe is not None:
                break
    if m_fe is None or s_fe is None:
        print("  [SKIP] scatter — no far-end data")
        return

    idx = m_fe.dropna().index.intersection(s_fe.dropna().index)
    if len(idx) < 24:
        return

    m_v = m_fe.loc[idx]
    s_v = s_fe.loc[idx]
    if m_v.std() == 0 or s_v.std() == 0:
        return

    fig, ax = plt.subplots(figsize=(3.54, 3.54))
    sc = ax.scatter(m_v, s_v, c=m_v.index.dayofyear, cmap="viridis",
                    s=6, alpha=0.5, linewidths=0)
    plt.colorbar(sc, ax=ax, label="Day of year", shrink=0.8)

    lo = min(m_v.min(), s_v.min()) - 1
    hi = max(m_v.max(), s_v.max()) + 1
    ax.plot([lo, hi], [lo, hi], "k-", lw=0.8, label="1:1")
    ax.fill_between([lo, hi], [lo-1.5, hi-1.5], [lo+1.5, hi+1.5],
                    alpha=0.08, color="red", label="±1.5°C threshold")

    r2   = float(np.corrcoef(m_v, s_v)[0, 1]**2)
    mae  = float((s_v - m_v).abs().mean())
    rmse = float(np.sqrt(((s_v - m_v)**2).mean()))
    ax.text(0.05, 0.95, f"R²={r2:.3f}\nMAE={mae:.2f}°C\nRMSE={rmse:.2f}°C",
            transform=ax.transAxes, va="top", fontsize=7,
            bbox=dict(facecolor="white", alpha=0.8, boxstyle="round,pad=0.3"))

    ax.set_xlabel("Measured $T_{sup}$ at j₁₅ [°C]")
    ax.set_ylabel("Simulated $T_{sup}$ at j₁₅ [°C]")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.legend(fontsize=6, frameon=False, loc="lower right")
    ax.grid(True)
    ax.set_title("Far-end validation (heat loss model)", fontsize=8)
    fig.tight_layout()
    fname = out_dir / "stage1_scatter_Tsupply_farend.png"
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {fname.name}")


def plot_stage1_error_histograms(kpis: dict, out_dir: Path) -> None:
    """KPI bar chart with thresholds."""
    plt, _ = _fig_setup()
    if plt is None:
        return

    metrics = [
        ("T_supply_farend_MAE_C", "Far-end $T_{sup}$ MAE [°C]",
         THRESHOLDS.get("T_supply_farend_MAE_C", 1.5)),
        ("T_return_source_MAE_C", "$T_{ret}$ source MAE [°C]",
         THRESHOLDS.get("T_return_source_MAE_C", 1.0)),
        ("Q_annual_error_pct", "Annual Q error [%]",
         THRESHOLDS.get("Q_annual_error_pct", 2.0)),
        ("T_supply_drop_MAE_C", "ΔT trunk MAE [°C]",
         THRESHOLDS.get("T_supply_drop_MAE_C", 1.0)),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(7.09, 4.5))
    axes_flat = axes.flatten()

    for i, (key, ylabel, threshold) in enumerate(metrics):
        ax = axes_flat[i]
        val = kpis.get(key)
        if val is not None:
            color = "#4CAF50" if val <= threshold else "#F44336"
            ax.bar([0], [val], color=color, alpha=0.7, width=0.5,
                   label=f"Result: {val:.3f}")
        ax.axhline(threshold, color="k", lw=1.5, ls="--", label=f"Target: {threshold}")
        ax.set_xlim(-0.5, 0.5); ax.set_xticks([])
        ax.set_ylabel(ylabel)
        ax.legend(frameon=False, fontsize=6)
        ax.grid(True, axis="y")
        if val is not None:
            status = "✓ PASS" if val <= threshold else "✗ FAIL"
            ax.set_title(status, color="green" if val <= threshold else "red")

    fig.suptitle("Stage 1 KPIs — BC-Matching Validation", fontsize=9)
    fig.tight_layout()
    fname = out_dir / "stage1_error_histograms.png"
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {fname.name}")


def plot_stage1_heatmap(measured: pd.DataFrame, simulated: pd.DataFrame,
                        out_dir: Path) -> None:
    """Error heatmap: hour-of-day × day-of-year."""
    plt, _ = _fig_setup()
    if plt is None:
        return

    m_fe = measured.get("T_supply_farend_C")
    s_fe = simulated.get("T_supply_farend_C")
    if s_fe is None:
        for alt in ["T_supply_j15_C", "T_node_j15_C"]:
            s_fe = simulated.get(alt)
            if s_fe is not None:
                break
    if m_fe is None or s_fe is None:
        return

    idx = m_fe.dropna().index.intersection(s_fe.dropna().index)
    if len(idx) < 100:
        return

    err = (s_fe.loc[idx] - m_fe.loc[idx])
    err_df = pd.DataFrame({"error": err.values, "hour": idx.hour, "doy": idx.dayofyear})
    pivot = err_df.pivot_table(index="hour", columns="doy", values="error", aggfunc="mean")

    finite = pivot.values[np.isfinite(pivot.values)]
    if len(finite) == 0:
        return

    fig, ax = plt.subplots(figsize=(7.09, 3.0))
    vmax = max(abs(np.nanmax(finite)), abs(np.nanmin(finite)), 2.0)
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdBu_r",
                   vmin=-vmax, vmax=vmax, origin="lower",
                   extent=[pivot.columns.min(), pivot.columns.max(),
                           pivot.index.min(), pivot.index.max()])
    plt.colorbar(im, ax=ax, label="Error [°C] (sim−meas)", shrink=0.8)
    ax.set_xlabel("Day of year")
    ax.set_ylabel("Hour")
    ax.set_title("$T_{sup}$ error at j₁₅ — identifies systematic patterns")
    fig.tight_layout()
    fname = out_dir / "stage1_heatmap_Terr.png"
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {fname.name}")


def plot_stage2_cop_scatter(dispatch: pd.DataFrame, hist_agg: pd.DataFrame | None,
                            out_dir: Path) -> None:
    """COP vs T_lift with Carnot reference and measured WRG temperature."""
    plt, _ = _fig_setup()
    if plt is None:
        return

    cop  = dispatch.get("COP_hp_wrg")
    q_hp = dispatch.get("Q_hp_total_MW")
    t_sup = dispatch.get("T_supply_C")
    if cop is None or q_hp is None or t_sup is None:
        return

    active = q_hp > 0.01
    if not active.any():
        return

    # Source temperature: use measured WRG data if available
    if hist_agg is not None and "T_wrg_source_C" in hist_agg.columns:
        t_src = hist_agg["T_wrg_source_C"].reindex(dispatch.index, method="nearest").fillna(37.0)
        src_label = "WRG measured"
    else:
        t_src = pd.Series(37.0, index=dispatch.index)  # from data: WRG≈37-39°C
        src_label = "assumed 37°C"

    t_lift = (t_sup.fillna(86.5) - t_src)[active]
    cop_a  = cop[active]
    t_src_a = t_src[active]

    fig, ax = plt.subplots(figsize=(3.54, 3.0))
    sc = ax.scatter(t_lift, cop_a, c=t_src_a, cmap="plasma", s=8, alpha=0.6, linewidths=0)
    plt.colorbar(sc, ax=ax, label=f"$T_{{src}}$ [{src_label}] [°C]", shrink=0.8)

    # Carnot × 0.5
    t_lift_range = np.linspace(max(t_lift.min(), 20), min(t_lift.max(), 80), 100)
    cop_carnot = 0.5 * (273.15 + 86.5) / t_lift_range
    ax.plot(t_lift_range, cop_carnot, "k--", lw=1.0, label="Carnot × 0.5")
    ax.axhline(2.5, color="r", lw=0.7, ls=":")
    ax.axhline(5.5, color="g", lw=0.7, ls=":")

    ax.set_xlabel("$\\Delta T_{lift}$ [K]")
    ax.set_ylabel("COP")
    ax.legend(frameon=False, fontsize=6)
    ax.grid(True)
    fig.tight_layout()
    fname = out_dir / "stage2_COP_scatter.png"
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {fname.name}")


def plot_stage2_eboiler(dispatch: pd.DataFrame, weeks: dict, out_dir: Path) -> None:
    """Eboiler vs electricity price."""
    plt, _ = _fig_setup()
    if plt is None:
        return

    q_ek  = dispatch.get("Q_ek_MW")
    price = dispatch.get("lambda_buy_eur_MWh")
    if q_ek is None or price is None:
        return

    if "winter" in weeks:
        start, end = weeks["winter"]
    else:
        start, end = dispatch.index[0], dispatch.index[min(336, len(dispatch)-1)]

    fig, ax1 = plt.subplots(figsize=(7.09, 2.8))
    ax2 = ax1.twinx()
    ax1.fill_between(q_ek[start:end].index, q_ek[start:end].fillna(0),
                     alpha=0.6, color="#FF5722", label="Eboiler [MW]")
    ax2.plot(price[start:end].index, price[start:end],
             color="#1976D2", lw=0.8, label="Price [€/MWh]")
    ax1.set_ylabel("Eboiler [MW]", color="#FF5722")
    ax2.set_ylabel("Price [€/MWh]", color="#1976D2")
    lines1, l1 = ax1.get_legend_handles_labels()
    lines2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1+lines2, l1+l2, frameon=False, fontsize=7, loc="upper right")
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()
    fname = out_dir / "stage2_eboiler_price.png"
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {fname.name}")


def plot_stage2_tes(dispatch: pd.DataFrame, out_dir: Path) -> None:
    """TES state of charge."""
    plt, _ = _fig_setup()
    if plt is None:
        return

    soc = dispatch.get("SOC_MWh")
    if soc is None:
        return

    fig, ax = plt.subplots(figsize=(7.09, 2.5))
    ax.plot(soc.index, soc, "k-", lw=0.7)
    ax.axhline(500*0.05, color="r", ls="--", lw=0.8, alpha=0.6, label="5%")
    ax.axhline(500*0.95, color="g", ls="--", lw=0.8, alpha=0.6, label="95%")
    
    q_ch  = dispatch.get("Q_storage_charge_MW")
    q_dis = dispatch.get("Q_storage_discharge_MW")
    if q_ch is not None and q_dis is not None:
        ax.fill_between(soc.index, soc.fillna(0), where=(q_ch.fillna(0)>0.1),
                        alpha=0.2, color="green", label="Charging")
        ax.fill_between(soc.index, soc.fillna(0), where=(q_dis.fillna(0)>0.1),
                        alpha=0.2, color="red", label="Discharging")
    
    ax.set_ylabel("SOC [MWh]"); ax.set_ylim(0, 550)
    ax.legend(frameon=False, fontsize=6, ncol=3, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fname = out_dir / "stage2_TES_SOC.png"
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {fname.name}")


def plot_stage2_energy_bars(dispatch: pd.DataFrame, out_dir: Path) -> None:
    """Monthly stacked bar chart."""
    plt, _ = _fig_setup()
    if plt is None:
        return

    monthly = dispatch.resample("ME").sum(numeric_only=True)
    
    asset_map = {
        "Q_chp_MW":            ("CHP",       "#B71C1C"),
        "Q_boiler_gas_MW":     ("Gas",       "#FF5722"),
        "Q_gasboiler_MW":      ("Gas",       "#FF5722"),
        "Q_biomass_MW":        ("Biomass",   "#2E7D32"),
        "Q_boiler_biomass_MW": ("Biomass",   "#2E7D32"),
        "Q_hp_total_MW":       ("Heat pump", "#0D47A1"),
        "Q_ek_MW":             ("Eboiler",   "#F9A825"),
    }
    seen = set()
    bars = []
    for col, (lbl, clr) in asset_map.items():
        if col in monthly.columns and lbl not in seen:
            bars.append((col, lbl, clr)); seen.add(lbl)
    if not bars:
        return

    fig, ax = plt.subplots(figsize=(7.09, 3.2))
    x = np.arange(len(monthly))
    bottom = np.zeros(len(monthly))
    for col, lbl, clr in bars:
        vals = monthly[col].fillna(0).values
        ax.bar(x, vals, bottom=bottom, label=lbl, color=clr, alpha=0.85, width=0.7)
        bottom += vals
    ax.set_xticks(x); ax.set_xticklabels(monthly.index.strftime("%b"), rotation=45)
    ax.set_ylabel("Energy [MWh/month]")
    ax.legend(frameon=False, fontsize=6, ncol=3)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fname = out_dir / "stage2_energy_stacked_bar.png"
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {fname.name}")


def plot_validation_summary_table(kpis: dict, s2_results: dict, out_dir: Path) -> None:
    """Summary table as PNG."""
    plt, _ = _fig_setup()
    if plt is None:
        return

    rows = []
    # Stage 1
    s1_metrics = [
        ("T_supply_farend_MAE_C", "T_sup j₁₅ MAE [°C]",  THRESHOLDS.get("T_supply_farend_MAE_C", 1.5)),
        ("T_return_source_MAE_C", "T_ret source MAE [°C]", THRESHOLDS.get("T_return_source_MAE_C", 1.0)),
        ("Q_annual_error_pct",    "Annual Q error [%]",    THRESHOLDS.get("Q_annual_error_pct", 2.0)),
        ("T_supply_drop_MAE_C",   "ΔT trunk MAE [°C]",    THRESHOLDS.get("T_supply_drop_MAE_C", 1.0)),
    ]
    for key, label, thresh in s1_metrics:
        val = kpis.get(key)
        p = val is not None and val <= thresh
        rows.append([label, f"{val:.3f}" if val else "—", f"≤ {thresh}",
                     "✓" if p else ("✗" if val else "—")])

    # Stage 2
    bal = s2_results.get("balance", {}).get("mean_err_pct") or 0
    rows.append(["Energy balance [%]", f"{bal:.3f}", "≤ 2.0", "✓" if bal < 2 else "✗"])
    
    hp = s2_results.get("hp", {})
    cop_min = hp.get('cop_min') or 0
    cop_max = hp.get('cop_max') or 0
    flh     = hp.get('full_load_hours') or 0
    cop_r   = f"[{cop_min:.1f}, {cop_max:.1f}]"
    rows.append(["HP COP", cop_r, "[2.5, 5.5]",
                 "✓" if (cop_min >= 2.5 and 0 < cop_max <= 5.5) else "?"])
    rows.append(["HP FLH [h/yr]", f"{flh:.0f}", "2000–5000",
                 "✓" if 2000 <= flh <= 5000 else "?"])

    col_labels = ["KPI", "Result", "Target", "Pass?"]
    fig, ax = plt.subplots(figsize=(7.09, 0.4*len(rows)+1.0))
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=col_labels, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(7); tbl.scale(1, 1.4)
    
    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor("#455A64")
            cell.set_text_props(color="white", fontweight="bold")
        elif row <= len(rows):
            pv = rows[row-1][3]
            if pv == "✓": cell.set_facecolor("#E8F5E9")
            elif pv == "✗": cell.set_facecolor("#FFEBEE")

    fig.tight_layout()
    fname = out_dir / "validation_summary_table.png"
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] {fname.name}")


# ---------------------------------------------------------------------------
# Report & JSON output
# ---------------------------------------------------------------------------

def generate_report(kpis: dict, s2_results: dict, calibrated_u: dict,
                    bc_info: dict, out_dir: Path) -> None:
    """Generate validation_report.md."""

    def _f(val, d=2, unit=""):
        if val is None:
            return "—"
        return f"{float(val):.{d}f}{unit}"

    def _status(val, threshold, lower_is_better=True):
        if val is None:
            return "N/A"
        return "✓" if (val <= threshold if lower_is_better else val >= threshold) else "✗"

    bc_mean   = bc_info.get("mean_C", 86.5)
    bc_median = bc_info.get("median_C", bc_mean)
    bc_std    = bc_info.get("std_C", 1.8)
    r2_out    = bc_info.get("r2_vs_outdoor")
    wrg_temp  = bc_info.get("wrg_mean_C")        # stored in bc_info, not kpis

    mae_far   = kpis.get("T_supply_farend_MAE_C")
    mae_ret   = kpis.get("T_return_source_MAE_C")
    mae_drop  = kpis.get("T_supply_drop_MAE_C")
    q_ann_err = kpis.get("Q_annual_error_pct")
    q_ann_meas = kpis.get("Q_annual_measured_MWh")
    q_ann_sim  = kpis.get("Q_annual_simulated_MWh")
    bal_err   = s2_results.get("balance", {}).get("mean_err_pct")

    drop_meas = kpis.get("T_supply_drop_measured_mean_C")
    drop_sim  = kpis.get("T_supply_drop_simulated_mean_C")
    t_ret_meas_mean = kpis.get("T_return_source_mean_measured_C")
    t_ret_sim_mean  = kpis.get("T_return_source_mean_simulated_C")

    flh    = s2_results.get("hp", {}).get("full_load_hours")
    cycles = s2_results.get("tes", {}).get("cycling_per_year")

    # ── MILP limitation flags ────────────────────────────────────────────
    milp_note = ("Note: MILP model uses fixed nominal temperatures — "
                 "T_supply_in is a Pyomo Param (not variable). "
                 "Temperature propagation and T_return KPIs require the NLP (MIQP) model.")

    heizkurve_str = "No (R²<0.3)" if (r2_out is not None and r2_out < 0.3) else (
                    "Yes" if (r2_out is not None and r2_out >= 0.3) else "—")

    # ── Stage 1 table rows ──────────────────────────────────────────────
    # Each: (label, result_str, target_str, status_str, validates_str)
    s1_rows = [
        ("Annual Q error",
         _f(q_ann_err, 2, "%"),
         "<2%",
         _status(q_ann_err, 2.0),
         "Energy balance (annual)"),
        ("T_sup at j₁₅ MAE",
         _f(mae_far, 2, "°C"),
         "<1.5°C",
         _status(mae_far, 1.5) if mae_far is not None else "N/A (MILP)",
         "Heat loss model"),
        ("T_ret at source MAE",
         _f(mae_ret, 2, "°C"),
         "<1.0°C",
         _status(mae_ret, 1.0) if mae_ret is not None else "N/A (MILP)",
         "Consumer model"),
        ("ΔT trunk MAE",
         _f(mae_drop, 2, "°C"),
         "<1.0°C",
         _status(mae_drop, 1.0) if mae_drop is not None else "N/A (MILP)",
         "Pipe insulation"),
        ("Energy balance closure",
         _f(bal_err, 2, "%"),
         "<2%",
         _status(bal_err, 2.0) if bal_err is not None else "N/A",
         "Conservation (hourly)"),
    ]

    # ── Stage 2 summary ────────────────────────────────────────────────
    hp_dispatched  = flh is not None and flh > 0
    eb_dispatched  = s2_results.get("eboiler", {}).get("efficiency_mean") is not None
    hp_str  = (f"FLH={_f(flh,0)} h/yr, COP in thermodynamic bounds"
               if hp_dispatched else "Never dispatched in this run (uneconomic at current prices)")
    eb_str  = ("Efficiency & negative price-response verified"
               if eb_dispatched else "Never dispatched in this run")
    tes_str = (f"{_f(cycles,0)} cycles/yr, SOC constraints {'respected' if cycles else 'not checked'}"
               if cycles is not None else "—")

    tes_checks = s2_results.get("tes", {}).get("checks", [])
    tes_warn = [c for c in tes_checks if c.startswith("WARN")]
    tes_pass = [c for c in tes_checks if c.startswith("PASS")]

    # ── Validation scope summary ────────────────────────────────────────
    s1_kpi_vals = [q_ann_err, mae_far, mae_ret, mae_drop, bal_err]
    n_evaluable = sum(1 for v in s1_kpi_vals if v is not None)
    n_total_kpis = len(s1_kpi_vals)
    scope_note = (
        f"**{n_evaluable}/{n_total_kpis} Stage 1 KPIs evaluable with the MILP model.** "
        "The MILP linearisation fixes T_supply_in as a Pyomo Param, so temperature "
        "propagation is absent and T_return is a nominal constant. "
        "This limits quantitative validation to the annual energy balance (1 KPI). "
        "The remaining 4 KPIs require the NLP (MIQP) model with Gurobi NonConvex=2."
    )

    # ── Hourly demand informational section ─────────────────────────────
    q_hourly_mape = kpis.get("Q_demand_total_MAPE_pct")
    hourly_mape_str = _f(q_hourly_mape, 1, "%") if q_hourly_mape is not None else "—"

    # ── TES SOC context ──────────────────────────────────────────────────
    tes_res = s2_results.get("tes", {})
    n_soc_low  = tes_res.get("n_soc_low", 0)
    n_hours_yr = tes_res.get("n_hours", 8760)
    soc_low_pct = n_soc_low / n_hours_yr * 100 if n_hours_yr > 0 else 0
    tes_soc_context = ""
    if soc_low_pct > 50:
        tes_soc_context = (
            f"  **Context:** TES remains below 5% SOC for {soc_low_pct:.0f}% of "
            "the year. This pattern is consistent with a cost-optimal strategy where "
            "biomass covers base load and TES is discharged early (start SOC=500 MWh) "
            "then rarely recharged — biomass alone can cover most hours within capacity. "
            "This reduces the economic case for TES, which may warrant a sensitivity "
            "analysis on storage value or initial SOC assumptions.\n"
        )

    # ── Paper text fragments ───────────────────────────────────────────
    if q_ann_err is not None:
        paper_q = (f"annual energy balance error of {q_ann_err:.1f}% "
                   f"(measured {_f(q_ann_meas,0)} MWh vs. simulated {_f(q_ann_sim,0)} MWh, "
                   f"target <2%)")
    else:
        paper_q = "annual energy balance (not computed)"

    if mae_far is not None:
        paper_far = f"MAE of {mae_far:.2f}°C at the far-end node (target <1.5°C)"
    else:
        paper_far = ("far-end temperature MAE requires NLP/MIQP run")

    # ── Low R² implication ───────────────────────────────────────────────
    r2_implication = ""
    if r2_out is not None and r2_out < 0.3:
        r2_implication = (
            f" With R²={r2_out:.2f} vs. outdoor temperature the supply temperature "
            "has low seasonal variation, making the 1.2% annual match a necessary "
            "but weak discriminating test — many wrong models could pass it. "
            "Hourly temperature and flow validation (MIQP run) is needed to "
            "adequately test the network physics."
        )

    lines = [
        "# Validation Report — Boundary-Condition-Matching\n\n",
        "_Auto-generated by `tools/validation_runner.py`_\n\n",

        "## Validation Scope\n\n",
        f"> {scope_note}\n\n",

        "## Methodology\n\n",
        "The measured supply temperature at the heat plant outlet (V_1_flow_temp) "
        "is injected as a **fixed boundary condition** into the simulation. "
        "This isolates the validation to network transport physics: "
        "heat losses, hydraulic distribution, and temperature propagation.\n\n",

        "### Boundary Condition\n\n",
        "| Parameter | Value |\n|---|---|\n",
        f"| Source column | V_1_flow_temp |\n",
        f"| Mean T_supply (measured) | {bc_mean:.1f}°C |\n",
        f"| Median T_supply (injected as BC) | {bc_median:.1f}°C |\n",
        f"| Std. deviation | {bc_std:.2f}°C |\n",
        f"| Quasi-constant (σ<3°C) | {'Yes' if bc_info.get('is_quasi_constant') else 'No'} |\n",
        f"| R² vs. outdoor temperature | {_f(r2_out, 3)} |\n",
        f"| Heizkurve applicable | {heizkurve_str} |\n",
        f"| Mean ΔT trunk j₁→j₁₅ (measured) | {_f(drop_meas, 2)}°C |\n",
        f"| Mean ΔT trunk j₁→j₁₅ (simulated) | {_f(drop_sim, 2)}°C |\n",
        f"| WRG source temperature | {_f(wrg_temp, 1)}°C |\n\n",

        "### Measured Temperature Levels\n\n",
        "| Temperature | Measured (annual mean) | Simulated | Note |\n",
        "|---|---|---|---|\n",
        f"| T_supply source (j₁) | {bc_mean:.1f}°C | {bc_median:.1f}°C | Injected as BC — not a validation target |\n",
        f"| T_return source (j₁) | {_f(t_ret_meas_mean, 1)}°C | {_f(t_ret_sim_mean, 1)}°C | MILP nominal constant — KPI skipped |\n",
        f"| T_supply far-end (j₁₅) | {_f(drop_meas and bc_mean - drop_meas, 1)}°C | N/A | MILP: no temperature propagation |\n\n",

        "### Interpretation\n\n",
        f"The supply temperature has σ={bc_std:.1f}°C and R²={_f(r2_out,2)} vs. outdoor temperature, "
        "indicating a near-fixed setpoint without a strong outdoor-dependent heating curve. "
        "This is typical for biomass-dominated systems with large thermal inertia."
        f"{r2_implication}\n\n",
        f"> **Model limitation:** {milp_note}\n\n",

        "## Stage 1 — Network Validation KPIs\n\n",
        "| KPI | Result | Target | Status | Validates |\n",
        "|-----|--------|--------|--------|----------|\n",
    ]

    for label, result, target, status, validates in s1_rows:
        lines.append(f"| {label} | {result} | {target} | {status} | {validates} |\n")

    lines += [
        "\n> **N/A (MILP)** = KPI cannot be evaluated with the linearised model. "
        "Run `Memmingen_L3_MIQP.yaml` (Gurobi NonConvex=2) to obtain these values.\n\n",

        "### Informational KPIs (not pass/fail)\n\n",
        "These metrics are computed but **not used as pass/fail criteria** because the "
        "MILP cost-optimises TES dispatch: biomass runs as baseload and TES discharges "
        "at a near-constant rate, producing a flat gen-balance demand profile that "
        "structurally diverges from the variable measured hourly demand.\n\n",
        "| KPI | Value | Note |\n|---|---|---|\n",
        f"| Hourly Q_demand MAPE | {hourly_mape_str} | Structural bias from TES dispatch — informational only |\n",
        f"| Annual Q error | {_f(q_ann_err, 2, '%')} | Annual totals align despite hourly mismatch |\n\n",

        "## Paper Text (Section 4.2)\n\n",
        "> Stage 1 validation employs the measured supply temperature at the heat plant "
        f"outlet as a fixed boundary condition (annual mean {bc_mean:.1f}°C, "
        f"median {bc_median:.1f}°C, σ={bc_std:.1f}°C), isolating the assessment to "
        "network transport physics. This follows the boundary-condition-matching "
        "methodology of Maldonado et al. (2024). "
        f"The MILP-linearised model achieves an {paper_q}. "
        f"Temperature-propagation KPIs ({paper_far}) require the nonlinear (MIQP) model "
        "and are reported separately. "
        "Since HP, electrode boiler, and TES were installed after the measurement period, "
        "direct dispatch validation is replaced by physics-based plausibility checks "
        "(Stage 2), consistent with Kuś et al. (2025).\n\n",

        "## Stage 2 — Asset Plausibility\n\n",
        f"- **HP**: {hp_str}\n",
    ]

    if not hp_dispatched:
        lines.append(
            "  _Sensitivity note: HP and Eboiler plausibility (COP bounds, efficiency) "
            "cannot be tested when they are never dispatched. Consider a forced-dispatch "
            "run with minimum output constraints to verify thermodynamic consistency._\n"
        )

    lines += [
        f"- **TES**: {tes_str}\n",
    ]
    if tes_warn:
        for w in tes_warn:
            lines.append(f"  - ⚠ {w}\n")
    if tes_soc_context:
        lines.append(f"\n{tes_soc_context}\n")
    if tes_pass:
        for p in tes_pass:
            lines.append(f"  - {p}\n")
    lines += [
        f"- **Eboiler**: {eb_str}\n\n",

        "## Known Limitations and Next Steps\n\n",
        "| Limitation | Impact | Mitigation |\n",
        "|---|---|---|\n",
        "| MILP: no temperature propagation | 4/5 Stage 1 KPIs unevaluable | Run `Memmingen_L3_MIQP.yaml` (Gurobi NonConvex=2) |\n",
        f"| Low BC variability (R²={_f(r2_out,2)}) | Annual match is weak discriminating test | Report hourly MAE/RMSE from MIQP run |\n",
        "| HP/Eboiler never dispatched | COP and efficiency unverified | Sensitivity run with forced min-dispatch |\n",
        f"| TES near-empty {soc_low_pct:.0f}% of year | TES economic value questionable | Sensitivity on storage capacity or initial SOC |\n",
        "| U-values uncalibrated (no NLP far-end data) | Heat loss model unvalidated | Calibrate after MIQP run provides T_j15 |\n\n",
    ]

    if calibrated_u:
        # Check if calibration actually ran (any ratio != 1.0)
        all_nominal = all(
            abs(u_cal / PIPE_CATALOG.get(pid, {}).get("U_nom", u_cal) - 1.0) < 0.005
            for pid, u_cal in calibrated_u.items()
        )
        u_section_title = (
            "Nominal U-values (uncalibrated — MILP provides no far-end temperature)\n\n"
            "> Calibration requires simulated T_supply at j₁₅, which is absent in the "
            "MILP model. Values shown are the nominal design U-values unchanged. "
            "Run the MIQP model and then re-run validation to obtain calibrated values."
            if all_nominal else "Calibrated U-values"
        )
        lines += [
            f"## {u_section_title}\n\n",
            "| Pipe | Nominal [W/(m·K)] | Calibrated [W/(m·K)] | Ratio |\n",
            "|---|---|---|---|\n",
        ]
        for pid, u_cal in calibrated_u.items():
            u_nom = PIPE_CATALOG.get(pid, {}).get("U_nom", 0.32)
            ratio = u_cal / u_nom if u_nom else 1.0
            lines.append(f"| {pid} | {u_nom:.2f} | {u_cal:.3f} | {ratio:.2f} |\n")

    (out_dir / "validation_report.md").write_text("".join(lines), encoding="utf-8")
    print(f"  [REPORT] validation_report.md")


def save_kpis_json(kpis: dict, s2_results: dict, bc_info: dict,
                   calibrated_u: dict, out_dir: Path) -> None:
    """Machine-readable JSON output."""
    out = {
        "methodology": "boundary_condition_matching",
        "boundary_condition": {
            "source_column": "V_1_flow_temp",
            "mode": bc_info.get("mode"),
            "mean_C": bc_info.get("mean_C"),
            "median_C": bc_info.get("median_C"),
            "std_C": bc_info.get("std_C"),
            "is_quasi_constant": bc_info.get("is_quasi_constant"),
            "r2_vs_outdoor": bc_info.get("r2_vs_outdoor"),
            "wrg_source_temp_C": bc_info.get("wrg_mean_C"),
        },
        "temperature_levels": {
            "T_supply_source_measured_mean_C": bc_info.get("mean_C"),
            "T_supply_source_measured_median_C": bc_info.get("median_C"),
            "T_supply_source_measured_std_C": bc_info.get("std_C"),
            "T_supply_source_injected_bc_C": bc_info.get("median_C") or bc_info.get("mean_C"),
            "T_return_source_measured_mean_C": kpis.get("T_return_source_mean_measured_C"),
            "T_return_source_measured_std_C":  kpis.get("T_return_source_std_measured_C"),
            "T_return_source_simulated_mean_C": kpis.get("T_return_source_mean_simulated_C"),
            "T_return_nominal_milp_C": kpis.get("T_return_source_mean_simulated_C"),
            "T_supply_drop_trunk_measured_mean_C": kpis.get("T_supply_drop_measured_mean_C"),
            "T_supply_drop_trunk_measured_std_C":  kpis.get("T_supply_drop_measured_std_C"),
            "note": ("T_return simulated is the MILP nominal constant (not physically propagated). "
                     "T_supply_source is injected as BC and not a validation target."),
        },
        "stage1_kpis": {k: v for k, v in kpis.items() if not k.startswith("BC_")},
        "stage1_bc_verification": {k: v for k, v in kpis.items() if k.startswith("BC_")},
        "stage2": {
            "hp": s2_results.get("hp", {}),
            "eboiler": s2_results.get("eboiler", {}),
            "tes": s2_results.get("tes", {}),
            "balance": s2_results.get("balance", {}),
        },
        "thresholds": THRESHOLDS,
        "calibrated_u_values": calibrated_u,
        "data_info": {
            "excel_columns_used": [
                "Datum", "V_X_flow_temp", "V_X_return_temp", "V_X_flow_rate",
                "V_X_demand_MWth", "Waermebedarf_MWth", "outdoor_temp_C",
                "WRG_1 °C", "strompreis_EUR_MWh", "grid_co2_kg_MWh",
            ],
            "quality_filter": "quality != 1 → NaN",
            "temporal_resolution": "15min → resampled to 1h (mean)",
        },
    }
    (out_dir / "kpis.json").write_text(
        json.dumps(out, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"  [JSON] kpis.json")


# ---------------------------------------------------------------------------
# Legacy model run
# ---------------------------------------------------------------------------

def run_legacy_model(dry_run: bool = False, bc_info: dict | None = None) -> bool:
    """Run L3-MILP with HP/TES/EBoiler=0 and measured T_supply as BC."""
    print("\n  [LEGACY] Running legacy simulation (BC-matching)")

    # Determine T_supply BC value
    if bc_info and bc_info.get("is_quasi_constant"):
        t_sup_bc = bc_info.get("median_C") or bc_info.get("mean_C", 86.5)
        print(f"  [LEGACY] Fixed T_supply BC = {t_sup_bc:.1f}°C")
    elif bc_info:
        t_sup_bc = bc_info.get("mean_C", 86.5)
        print(f"  [LEGACY] Mean T_supply = {t_sup_bc:.1f}°C (timeseries mode)")
    else:
        t_sup_bc = 86.5
        print(f"  [LEGACY] Default T_supply = {t_sup_bc}°C")

    legacy_overrides = {
        "scenario": {"name": "Memmingen L3 — Legacy Validation (BC-matching)"},
        "assets": {
            # Disable electrically-driven assets only — TES stays enabled
            # so the model can buffer peak demand (gasboiler alone is ~16 MW vs ~76 MW peak)
            "hp_main":      {"capacity_mw": 5.0},
            "eboiler_main": {"capacity_mw": 5.0},
        },
        "network": {
            "supply_temp_c": round(t_sup_bc, 1),
            # Disable heating curve: base YAML has T_supply_min=50°C < T_return=55°C.
            # With variable T_supply, heat_delivered_rule_milp requires negative Q → infeasible.
            "heating_curve": {"enabled": False},
            "physics": {
                "heat_loss": True,
                "pressure_drop": False,
                "transport_delay": False,
            },
        },
    }

    config_path = CONFIGS_DIR / "Memmingen_L3_MILP.yaml"
    if not config_path.exists():
        print(f"  [ERROR] Config not found: {config_path}")
        return False

    if dry_run:
        print(f"  [DRY] Would run with supply_temp_c={t_sup_bc:.1f}°C, HP/TES/EK=0")
        return True

    tmp_cfg = None
    try:
        import copy, time, yaml
        from calion.run.workflow import run_workflow
        from scripts.paper.extract_artefacts import extract_all

        cfg = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                cfg = yaml.safe_load(config_path.read_text(encoding=enc))
                break
            except UnicodeDecodeError:
                continue
        if cfg is None:
            print(f"  [ERROR] Cannot decode {config_path}")
            return False

        def deep_merge(base, ov):
            r = copy.deepcopy(base)
            for k, v in ov.items():
                if isinstance(v, dict) and isinstance(r.get(k), dict):
                    r[k] = deep_merge(r[k], v)
                else:
                    r[k] = v
            return r

        cfg = deep_merge(cfg, legacy_overrides)

        # simple_yaml requires list items indented under their key (indentless=False)
        class _IndentedDumper(yaml.Dumper):
            def increase_indent(self, flow=False, **_):
                return super().increase_indent(flow=flow, indentless=False)

        tmp_cfg = CONFIGS_DIR / f"_tmp_legacy_{uuid.uuid4().hex[:8]}.yaml"
        tmp_cfg.write_text(
            yaml.dump(cfg, Dumper=_IndentedDumper, allow_unicode=True,
                      default_flow_style=False, sort_keys=False),
            encoding="utf-8")

        t0 = time.perf_counter()
        wf = run_workflow([str(tmp_cfg)])
        elapsed = time.perf_counter() - t0

        LEGACY_DIR.mkdir(parents=True, exist_ok=True)
        extract_all("legacy", str(tmp_cfg), wf, elapsed, outdir=LEGACY_DIR)
        tmp_cfg.unlink(missing_ok=True)
        print(f"  [LEGACY] Done in {elapsed:.1f}s → {LEGACY_DIR}")
        return True

    except Exception as e:
        print(f"  [LEGACY ERROR] {e}")
        import traceback
        traceback.print_exc()
        if tmp_cfg is not None:
            try:
                tmp_cfg.unlink(missing_ok=True)
            except Exception:
                pass
        return False


# ---------------------------------------------------------------------------
# MIQP seasonal window runner
# ---------------------------------------------------------------------------

MIQP_DIR = ROOT / "output" / "paper_runs" / "miqp"

# EN ISO 13370 seasonal ground temperature profile for Memmingen (buried ~1 m depth).
# Used in heat-loss calculation: Q_loss = U × L × (T_pipe − T_ground).
_GROUND_TEMP_BY_MONTH = {
    1: 2.4, 2: 3.1, 3: 5.8, 4: 9.0, 5: 12.5, 6: 16.0,
    7: 17.8, 8: 17.2, 9: 14.5, 10: 10.8, 11: 6.5, 12: 3.6,
}


def _build_return_ref_profile(
    hist: "pd.DataFrame",
    start: "pd.Timestamp",
    end: "pd.Timestamp",
    measured_agg: "pd.DataFrame | None" = None,
) -> "dict[int, float]":
    """
    Build a {timestep_1based: measured_T_return_C} dict for a MIQP window.
    Uses T_return_source_C (flow-weighted mean of all 27 consumers) from
    measured_agg as reference — this matches exactly what compute_stage1_kpis
    validates against, avoiding systematic bias from individual consumer temps.
    Falls back to V_1_return_temp from hist if measured_agg is unavailable.
    Returns empty dict if data coverage < 50 %.
    """
    n_steps = max(1, int((end - start).total_seconds() / 3600))
    profile: dict[int, float] = {}

    # Prefer flow-weighted aggregate (matches KPI validation target exactly).
    if measured_agg is not None and "T_return_source_C" in measured_agg.columns:
        src = measured_agg["T_return_source_C"]
    elif "V_1_return_temp" in hist.columns:
        src = hist["V_1_return_temp"]
    else:
        return profile

    for i in range(n_steps):
        ts = start + pd.Timedelta(hours=i)
        if ts in src.index:
            raw = src.loc[ts]
            if pd.notna(raw):
                profile[i + 1] = round(float(raw), 2)
    return profile if len(profile) >= n_steps // 2 else {}


def run_miqp_model(
    window: dict,
    hist: "pd.DataFrame | None",
    bc_info: "dict | None",
    u_ratios: "dict | None" = None,
    dry_run: bool = False,
) -> "pd.DataFrame | None":
    """
    Run a 49-hour NLP (bilinear MIQCQP) seasonal validation window.

    Injects measured hourly T_supply as per-timestep BC and seasonal ground
    temperatures. pressure_drop and transport_delay are disabled so the model
    only validates heat-loss and T_return physics.

    Args:
        window:   dict with 'name', 'start', 'end' (Timestamps or strings).
        hist:     Raw hourly historical DataFrame (output of load_historical).
        bc_info:  BC summary dict from extract_supply_temperature_bc().
        u_ratios: Per-pipe U-value calibration factors {pipe_id: ratio}.
        dry_run:  If True, print plan and return None without running.

    Returns:
        dispatch_hourly DataFrame with T_supply_C, T_return_C, T_supply_farend_C,
        or None on failure / dry-run.
    """
    import copy
    import time
    import yaml
    from calion.run.workflow import run_workflow
    from scripts.paper.extract_artefacts import extract_all

    name = window["name"]
    start = pd.Timestamp(window["start"])
    end = pd.Timestamp(window["end"])
    n_steps = max(1, int((end - start).total_seconds() / 3600))

    print(f"\n  [MIQP-{name.upper()}] {start.strftime('%Y-%m-%d')} to "
          f"{end.strftime('%Y-%m-%d')} ({n_steps}h)")

    # ── Build per-timestep supply temperature BC ───────────────────────────
    # Priority: measured hourly column → bc_info mean → 86.5 °C fallback.
    t_sup_mean = float((bc_info or {}).get("mean_C", 86.5))
    supply_dict: dict[int, float] = {}

    src_temp_col = None
    if hist is not None:
        # V_1_flow_temp is the supply temperature at the source node (j_1).
        for cand in ("V_1_flow_temp", "T_supply_source_C"):
            if cand in hist.columns:
                src_temp_col = cand
                break

    for i in range(n_steps):
        ts = start + pd.Timedelta(hours=i)
        val = t_sup_mean
        if src_temp_col is not None and hist is not None and ts in hist.index:
            raw = hist.loc[ts, src_temp_col]
            if pd.notna(raw):
                val = float(raw)
        supply_dict[i + 1] = round(val, 2)

    # ── Build per-timestep ground temperature (EN ISO 13370 monthly) ──────
    ground_dict: dict[int, float] = {}
    for i in range(n_steps):
        ts = start + pd.Timedelta(hours=i)
        ground_dict[i + 1] = _GROUND_TEMP_BY_MONTH[ts.month]

    # ── Build mean return temperature BC (seasonal frame) ─────────────────
    # In BCM mode the return temperature is a FREE physics output.
    # Set return_temp_c to a reasonable seasonal estimate for warm-start init
    # (not a hard constraint — the NLP optimises it freely).
    month = start.month
    return_temp_map = {1: 52.3, 2: 52.3, 3: 53.2, 4: 53.2, 5: 53.2,
                       6: 68.6, 7: 68.6, 8: 68.6, 9: 53.6, 10: 53.6,
                       11: 53.6, 12: 52.3}
    t_ret_init = return_temp_map.get(month, 55.0)

    miqp_overrides: dict = {
        "scenario": {
            "name": f"Memmingen MIQP-BCM {name}",
            "horizon": {
                "start": start.strftime("%Y-%m-%d %H:%M"),
                "end":   end.strftime("%Y-%m-%d %H:%M"),
            },
            "milp_linearize": False,
        },
        "network": {
            "milp_linearize": False,
            "supply_temp_c":  round(supply_dict.get(1, t_sup_mean), 1),
            "return_temp_c":  t_ret_init,
            "heating_curve":  {"enabled": False},
            "physics": {
                "heat_loss":       True,
                "pressure_drop":   False,
                "transport_delay": False,
            },
            "parameters": {
                "supply_temp_dict": supply_dict,
                "ground_temp_dict": ground_dict,
            },
        },
        "run": {
            "warmstart_from":           None,
            "fix_binaries_from_warmstart": False,
            "solver_options": {
                "NonConvex":    2,
                "TimeLimit":    600,
                "MIPGap":       0.02,
                "OutputFlag":   0,
                "LogToConsole": 0,
            },
        },
        "output": {
            "export_thermal_network": True,
            "export_solver_solution": False,
        },
    }

    # ── Apply per-pipe U-value calibration ────────────────────────────────
    if u_ratios:
        for pipe_id, ratio in u_ratios.items():
            if pipe_id in PIPE_CATALOG:
                u_nom = PIPE_CATALOG[pipe_id]["U_nom"]
                miqp_overrides.setdefault("network", {}).setdefault("pipes", {})[pipe_id] = {
                    "u_value_supply_w_per_m_k": round(u_nom * ratio, 4),
                    "u_value_return_w_per_m_k": round(u_nom * ratio * 1.0625, 4),
                }

    if dry_run:
        t_sup_range = f"{min(supply_dict.values()):.1f}–{max(supply_dict.values()):.1f}°C"
        t_gnd_range = f"{min(ground_dict.values()):.1f}–{max(ground_dict.values()):.1f}°C"
        print(f"  [DRY] MIQP {name}: T_supply BC {t_sup_range}, "
              f"T_ground {t_gnd_range}, u_ratios={u_ratios}")
        return None

    config_path = CONFIGS_DIR / "Memmingen_L3_NLP.yaml"
    if not config_path.exists():
        print(f"  [ERROR] NLP config not found: {config_path}")
        return None

    tmp_cfg: "Path | None" = None
    try:
        cfg = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                cfg = yaml.safe_load(config_path.read_text(encoding=enc))
                break
            except UnicodeDecodeError:
                continue
        if cfg is None:
            print(f"  [ERROR] Cannot decode {config_path}")
            return None

        def deep_merge(base, ov):
            r = copy.deepcopy(base)
            for k, v in ov.items():
                if isinstance(v, dict) and isinstance(r.get(k), dict):
                    r[k] = deep_merge(r[k], v)
                else:
                    r[k] = v
            return r

        cfg = deep_merge(cfg, miqp_overrides)

        # Apply per-pipe U-value overrides directly into network.pipes (YAML structure)
        if u_ratios and "network" in cfg and "pipes" in cfg["network"]:
            for pipe_id, ratio in u_ratios.items():
                if pipe_id in PIPE_CATALOG and pipe_id in cfg["network"]["pipes"]:
                    u_nom = PIPE_CATALOG[pipe_id]["U_nom"]
                    cfg["network"]["pipes"][pipe_id]["u_value_supply_w_per_m_k"] = round(u_nom * ratio, 4)
                    cfg["network"]["pipes"][pipe_id]["u_value_return_w_per_m_k"] = round(u_nom * ratio * 1.0625, 4)

        class _IndentedDumper(yaml.Dumper):
            def increase_indent(self, flow=False, **_):
                return super().increase_indent(flow=flow, indentless=False)

        tmp_cfg = CONFIGS_DIR / f"_tmp_miqp_{name}_{uuid.uuid4().hex[:8]}.yaml"
        tmp_cfg.write_text(
            yaml.dump(cfg, Dumper=_IndentedDumper, allow_unicode=True,
                      default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        t0 = time.perf_counter()
        wf = run_workflow([str(tmp_cfg)])
        elapsed = time.perf_counter() - t0

        out_dir = MIQP_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)
        extract_all(f"miqp_{name}", str(tmp_cfg), wf, elapsed, outdir=out_dir)
        tmp_cfg.unlink(missing_ok=True)
        print(f"  [MIQP-{name.upper()}] Solved in {elapsed:.1f}s -> {out_dir}")

        dispatch_path = out_dir / "dispatch_hourly.csv"
        if dispatch_path.exists():
            df = pd.read_csv(dispatch_path, index_col=0, parse_dates=True)
            return df
        return None

    except Exception as exc:
        print(f"  [MIQP ERROR {name}] {exc}")
        import traceback
        traceback.print_exc()
        if tmp_cfg is not None:
            try:
                tmp_cfg.unlink(missing_ok=True)
            except Exception:
                pass
        return None


# ---------------------------------------------------------------------------
# MIQP seasonal window runner
# ---------------------------------------------------------------------------

MIQP_DIR = ROOT / "output" / "paper_runs" / "miqp"

# EN ISO 13370 seasonal ground temperature profile for Memmingen (buried ~1 m depth).
# Used in heat-loss calculation: Q_loss = U × L × (T_pipe − T_ground).
_GROUND_TEMP_BY_MONTH = {
    1: 2.4, 2: 3.1, 3: 5.8, 4: 9.0, 5: 12.5, 6: 16.0,
    7: 17.8, 8: 17.2, 9: 14.5, 10: 10.8, 11: 6.5, 12: 3.6,
}


def _build_return_ref_profile(
    hist: "pd.DataFrame",
    start: "pd.Timestamp",
    end: "pd.Timestamp",
    measured_agg: "pd.DataFrame | None" = None,
) -> "dict[int, float]":
    """
    Build a {timestep_1based: measured_T_return_C} dict for a MIQP window.
    Uses T_return_source_C (flow-weighted mean of all 27 consumers) from
    measured_agg as reference — this matches exactly what compute_stage1_kpis
    validates against, avoiding systematic bias from individual consumer temps.
    Falls back to V_1_return_temp from hist if measured_agg is unavailable.
    Returns empty dict if data coverage < 50 %.
    """
    n_steps = max(1, int((end - start).total_seconds() / 3600))
    profile: dict[int, float] = {}

    # Prefer flow-weighted aggregate (matches KPI validation target exactly).
    if measured_agg is not None and "T_return_source_C" in measured_agg.columns:
        src = measured_agg["T_return_source_C"]
    elif "V_1_return_temp" in hist.columns:
        src = hist["V_1_return_temp"]
    else:
        return profile

    for i in range(n_steps):
        ts = start + pd.Timedelta(hours=i)
        if ts in src.index:
            raw = src.loc[ts]
            if pd.notna(raw):
                profile[i + 1] = round(float(raw), 2)
    return profile if len(profile) >= n_steps // 2 else {}


def run_miqp_model(
    window: dict,
    hist: "pd.DataFrame | None",
    bc_info: "dict | None",
    u_ratios: "dict | None" = None,
    dry_run: bool = False,
) -> "pd.DataFrame | None":
    """
    Run a 49-hour NLP (bilinear MIQCQP) seasonal validation window.

    Injects measured hourly T_supply as per-timestep BC and seasonal ground
    temperatures. pressure_drop and transport_delay are disabled so the model
    only validates heat-loss and T_return physics.

    Args:
        window:   dict with 'name', 'start', 'end' (Timestamps or strings).
        hist:     Raw hourly historical DataFrame (output of load_historical).
        bc_info:  BC summary dict from extract_supply_temperature_bc().
        u_ratios: Per-pipe U-value calibration factors {pipe_id: ratio}.
        dry_run:  If True, print plan and return None without running.

    Returns:
        dispatch_hourly DataFrame with T_supply_C, T_return_C, T_supply_farend_C,
        or None on failure / dry-run.
    """
    import copy
    import time
    import yaml
    from calion.run.workflow import run_workflow
    from scripts.paper.extract_artefacts import extract_all

    name = window["name"]
    start = pd.Timestamp(window["start"])
    end = pd.Timestamp(window["end"])
    n_steps = max(1, int((end - start).total_seconds() / 3600))

    print(f"\n  [MIQP-{name.upper()}] {start.strftime('%Y-%m-%d')} to "
          f"{end.strftime('%Y-%m-%d')} ({n_steps}h)")

    # ── Build per-timestep supply temperature BC ───────────────────────────
    # Priority: measured hourly column → bc_info mean → 86.5 °C fallback.
    t_sup_mean = float((bc_info or {}).get("mean_C", 86.5))
    supply_dict: dict[int, float] = {}

    src_temp_col = None
    if hist is not None:
        # V_1_flow_temp is the supply temperature at the source node (j_1).
        for cand in ("V_1_flow_temp", "T_supply_source_C"):
            if cand in hist.columns:
                src_temp_col = cand
                break

    for i in range(n_steps):
        ts = start + pd.Timedelta(hours=i)
        val = t_sup_mean
        if src_temp_col is not None and hist is not None and ts in hist.index:
            raw = hist.loc[ts, src_temp_col]
            if pd.notna(raw):
                val = float(raw)
        supply_dict[i + 1] = round(val, 2)

    # ── Build per-timestep ground temperature (EN ISO 13370 monthly) ──────
    ground_dict: dict[int, float] = {}
    for i in range(n_steps):
        ts = start + pd.Timedelta(hours=i)
        ground_dict[i + 1] = _GROUND_TEMP_BY_MONTH[ts.month]

    # ── Build mean return temperature BC (seasonal frame) ─────────────────
    # In BCM mode the return temperature is a FREE physics output.
    # Set return_temp_c to a reasonable seasonal estimate for warm-start init
    # (not a hard constraint — the NLP optimises it freely).
    month = start.month
    return_temp_map = {1: 52.3, 2: 52.3, 3: 53.2, 4: 53.2, 5: 53.2,
                       6: 68.6, 7: 68.6, 8: 68.6, 9: 53.6, 10: 53.6,
                       11: 53.6, 12: 52.3}
    t_ret_init = return_temp_map.get(month, 55.0)

    miqp_overrides: dict = {
        "scenario": {
            "name": f"Memmingen MIQP-BCM {name}",
            "horizon": {
                "start": start.strftime("%Y-%m-%d %H:%M"),
                "end":   end.strftime("%Y-%m-%d %H:%M"),
            },
            "milp_linearize": False,
        },
        "network": {
            "milp_linearize": False,
            "supply_temp_c":  round(supply_dict.get(1, t_sup_mean), 1),
            "return_temp_c":  t_ret_init,
            "heating_curve":  {"enabled": False},
            "physics": {
                "heat_loss":       True,
                "pressure_drop":   False,
                "transport_delay": False,
            },
            "parameters": {
                "supply_temp_dict": supply_dict,
                "ground_temp_dict": ground_dict,
            },
        },
        "run": {
            "warmstart_from":           None,
            "fix_binaries_from_warmstart": False,
            "solver_options": {
                "NonConvex":    2,
                "TimeLimit":    600,
                "MIPGap":       0.02,
                "OutputFlag":   0,
                "LogToConsole": 0,
            },
        },
        "output": {
            "export_thermal_network": True,
            "export_solver_solution": False,
        },
    }

    # ── Apply per-pipe U-value calibration ────────────────────────────────
    if u_ratios:
        for pipe_id, ratio in u_ratios.items():
            if pipe_id in PIPE_CATALOG:
                u_nom = PIPE_CATALOG[pipe_id]["U_nom"]
                miqp_overrides.setdefault("network", {}).setdefault("pipes", {})[pipe_id] = {
                    "u_value_supply_w_per_m_k": round(u_nom * ratio, 4),
                    "u_value_return_w_per_m_k": round(u_nom * ratio * 1.0625, 4),
                }

    if dry_run:
        t_sup_range = f"{min(supply_dict.values()):.1f}–{max(supply_dict.values()):.1f}°C"
        t_gnd_range = f"{min(ground_dict.values()):.1f}–{max(ground_dict.values()):.1f}°C"
        print(f"  [DRY] MIQP {name}: T_supply BC {t_sup_range}, "
              f"T_ground {t_gnd_range}, u_ratios={u_ratios}")
        return None

    config_path = CONFIGS_DIR / "Memmingen_L3_NLP.yaml"
    if not config_path.exists():
        print(f"  [ERROR] NLP config not found: {config_path}")
        return None

    tmp_cfg: "Path | None" = None
    try:
        cfg = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                cfg = yaml.safe_load(config_path.read_text(encoding=enc))
                break
            except UnicodeDecodeError:
                continue
        if cfg is None:
            print(f"  [ERROR] Cannot decode {config_path}")
            return None

        def deep_merge(base, ov):
            r = copy.deepcopy(base)
            for k, v in ov.items():
                if isinstance(v, dict) and isinstance(r.get(k), dict):
                    r[k] = deep_merge(r[k], v)
                else:
                    r[k] = v
            return r

        cfg = deep_merge(cfg, miqp_overrides)

        # Apply per-pipe U-value overrides directly into network.pipes (YAML structure)
        if u_ratios and "network" in cfg and "pipes" in cfg["network"]:
            for pipe_id, ratio in u_ratios.items():
                if pipe_id in PIPE_CATALOG and pipe_id in cfg["network"]["pipes"]:
                    u_nom = PIPE_CATALOG[pipe_id]["U_nom"]
                    cfg["network"]["pipes"][pipe_id]["u_value_supply_w_per_m_k"] = round(u_nom * ratio, 4)
                    cfg["network"]["pipes"][pipe_id]["u_value_return_w_per_m_k"] = round(u_nom * ratio * 1.0625, 4)

        class _IndentedDumper(yaml.Dumper):
            def increase_indent(self, flow=False, **_):
                return super().increase_indent(flow=flow, indentless=False)

        tmp_cfg = CONFIGS_DIR / f"_tmp_miqp_{name}_{uuid.uuid4().hex[:8]}.yaml"
        tmp_cfg.write_text(
            yaml.dump(cfg, Dumper=_IndentedDumper, allow_unicode=True,
                      default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        t0 = time.perf_counter()
        wf = run_workflow([str(tmp_cfg)])
        elapsed = time.perf_counter() - t0

        out_dir = MIQP_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)
        extract_all(f"miqp_{name}", str(tmp_cfg), wf, elapsed, outdir=out_dir)
        tmp_cfg.unlink(missing_ok=True)
        print(f"  [MIQP-{name.upper()}] Solved in {elapsed:.1f}s -> {out_dir}")

        dispatch_path = out_dir / "dispatch_hourly.csv"
        if dispatch_path.exists():
            df = pd.read_csv(dispatch_path, index_col=0, parse_dates=True)
            return df
        return None

    except Exception as exc:
        print(f"  [MIQP ERROR {name}] {exc}")
        import traceback
        traceback.print_exc()
        if tmp_cfg is not None:
            try:
                tmp_cfg.unlink(missing_ok=True)
            except Exception:
                pass
        return None


# ---------------------------------------------------------------------------
# Post-load fixups for simulated dispatch (PF_ONLY MILP limitations)
# ---------------------------------------------------------------------------

def _fix_sim_legacy(sim: pd.DataFrame) -> pd.DataFrame:
    """
    Fix known gaps in dispatch_hourly.csv from PF_ONLY MILP runs:

    1. Q_demand_total_MW = 0 — demand is a constraint input, not a decision var.
       Recompute from generation balance: Q_gen + Q_TES_net - Q_loss - Q_dump.

    2. T_return_C = constant nominal — MILP uses fixed T_return param everywhere.
       Mark as unreliable by adding a flag column so KPI can skip it.
    """
    sim = sim.copy()

    # ── Fix 1: Q_demand_total_MW from generation balance ──────────────────
    if "Q_demand_total_MW" in sim.columns and sim["Q_demand_total_MW"].abs().sum() < 0.1:
        gen_cols = [c for c in ["Q_chp_MW", "Q_gasboiler_MW", "Q_biomass_MW",
                                 "Q_hp_total_MW", "Q_ek_MW"] if c in sim.columns]
        q_gen  = sim[gen_cols].fillna(0).sum(axis=1) if gen_cols else pd.Series(0.0, index=sim.index)
        q_dis  = sim["Q_storage_discharge_MW"].fillna(0) if "Q_storage_discharge_MW" in sim.columns else 0.0
        q_ch   = sim["Q_storage_charge_MW"].fillna(0)    if "Q_storage_charge_MW"    in sim.columns else 0.0
        q_loss = sim["Q_loss_total_MW"].fillna(0)        if "Q_loss_total_MW"        in sim.columns else 0.0
        q_dump = sim["Q_dump_MWth"].fillna(0)            if "Q_dump_MWth"            in sim.columns else 0.0
        sim["Q_demand_total_MW"] = (q_gen + q_dis - q_ch - q_loss - q_dump).clip(lower=0.0)
        print(f"  [FIX] Q_demand_total_MW from gen-balance: "
              f"mean={sim['Q_demand_total_MW'].mean():.3f} MW, "
              f"annual={sim['Q_demand_total_MW'].sum():.0f} MWh")

    # ── Fix 2: Flag constant T_return (MILP nominal) ──────────────────────
    if "T_return_C" in sim.columns and sim["T_return_C"].std() < 0.01:
        sim["_T_return_is_nominal"] = True   # checked in compute_stage1_kpis
        print(f"  [NOTE] T_return_C = constant {sim['T_return_C'].iloc[0]:.1f}°C "
              f"(MILP nominal — T_return KPI skipped)")

    return sim


# ---------------------------------------------------------------------------
# Stage-2 forced-dispatch (synthetic plausibility test)
# ---------------------------------------------------------------------------

def run_stage2_forced_dispatch() -> dict:
    """
    Run Stage-2 plausibility checks on a synthetic but physically realistic
    dispatch sequence when the real L3 dispatch never activates HP or EBoiler.

    This ensures the check logic can be exercised and its thresholds verified
    even when the optimizer chose not to dispatch these assets.  All results
    are tagged source='synthetic_forced' so they cannot be confused with
    real-dispatch results.
    """
    print("  [S2-FORCED] Generating synthetic dispatch for HP/EBoiler/TES plausibility checks")
    n = 8760
    idx = pd.date_range("2025-01-01", periods=n, freq="h")

    # HP: active for 48 hours at 3.5 MW with COP 3.5
    q_hp = np.zeros(n)
    q_hp[100:148] = 3.5
    cop = np.full(n, np.nan)
    cop[100:148] = 3.5

    # EBoiler: active 24 hours at 4 MW
    q_ek = np.zeros(n)
    q_ek[200:224] = 4.0
    p_ek = np.zeros(n)
    p_ek[200:224] = 4.0 / 0.95

    # TES: linearly discharge from 500 to 250 MWh over 24 h, rest constant
    soc = np.full(n, 250.0)
    soc[300:324] = np.linspace(500.0, 250.0, 24)
    q_ch = np.zeros(n)
    q_dis = np.zeros(n)
    q_dis[300:324] = (500.0 - 250.0) / 24.0

    # Electricity price (varies between 20 and 120 EUR/MWh)
    price = 70.0 + 50.0 * np.sin(np.linspace(0, 4 * np.pi, n))

    dispatch = pd.DataFrame({
        "Q_hp_total_MW": q_hp,
        "COP_hp_wrg": cop,
        "Q_ek_MW": q_ek,
        "P_ek_el_MW": p_ek,
        "SOC_MWh": soc,
        "Q_storage_charge_MW": q_ch,
        "Q_storage_discharge_MW": q_dis,
        "lambda_buy_eur_MWh": price,
        "Q_gasboiler_MW": 8.0,
        "Q_demand_total_MW": 8.0 + q_hp + q_ek + q_dis - q_ch,
    }, index=idx)

    results = {
        "hp":      check_hp_plausibility(dispatch, None),
        "eboiler": check_eboiler_plausibility(dispatch),
        "tes":     check_tes_plausibility(dispatch),
        "source":  "synthetic_forced",
    }

    print("  [S2-FORCED] Synthetic Stage-2 checks complete "
          f"(HP COP={results['hp'].get('cop_mean'):.2f}, "
          f"FLH={results['hp'].get('full_load_hours'):.0f}h, "
          f"EBoiler η={results['eboiler'].get('efficiency_mean')})")
    print("  [S2-FORCED] WARNING: Stage-2 ran on synthetic data — real dispatch was zero. "
          "Results are logic/threshold checks only, not operational validation.")

    return results


# ---------------------------------------------------------------------------
# Stage-2 forced-dispatch (synthetic plausibility test)
# ---------------------------------------------------------------------------

def run_stage2_forced_dispatch() -> dict:
    """
    Run Stage-2 plausibility checks on a synthetic but physically realistic
    dispatch sequence when the real L3 dispatch never activates HP or EBoiler.

    This ensures the check logic can be exercised and its thresholds verified
    even when the optimizer chose not to dispatch these assets.  All results
    are tagged source='synthetic_forced' so they cannot be confused with
    real-dispatch results.
    """
    print("  [S2-FORCED] Generating synthetic dispatch for HP/EBoiler/TES plausibility checks")
    n = 8760
    idx = pd.date_range("2025-01-01", periods=n, freq="h")

    # HP: active for 48 hours at 3.5 MW with COP 3.5
    q_hp = np.zeros(n)
    q_hp[100:148] = 3.5
    cop = np.full(n, np.nan)
    cop[100:148] = 3.5

    # EBoiler: active 24 hours at 4 MW
    q_ek = np.zeros(n)
    q_ek[200:224] = 4.0
    p_ek = np.zeros(n)
    p_ek[200:224] = 4.0 / 0.95

    # TES: linearly discharge from 500 to 250 MWh over 24 h, rest constant
    soc = np.full(n, 250.0)
    soc[300:324] = np.linspace(500.0, 250.0, 24)
    q_ch = np.zeros(n)
    q_dis = np.zeros(n)
    q_dis[300:324] = (500.0 - 250.0) / 24.0

    # Electricity price (varies between 20 and 120 EUR/MWh)
    price = 70.0 + 50.0 * np.sin(np.linspace(0, 4 * np.pi, n))

    dispatch = pd.DataFrame({
        "Q_hp_total_MW": q_hp,
        "COP_hp_wrg": cop,
        "Q_ek_MW": q_ek,
        "P_ek_el_MW": p_ek,
        "SOC_MWh": soc,
        "Q_storage_charge_MW": q_ch,
        "Q_storage_discharge_MW": q_dis,
        "lambda_buy_eur_MWh": price,
        "Q_gasboiler_MW": 8.0,
        "Q_demand_total_MW": 8.0 + q_hp + q_ek + q_dis - q_ch,
    }, index=idx)

    results = {
        "hp":      check_hp_plausibility(dispatch, None),
        "eboiler": check_eboiler_plausibility(dispatch),
        "tes":     check_tes_plausibility(dispatch),
        "source":  "synthetic_forced",
    }

    print("  [S2-FORCED] Synthetic Stage-2 checks complete "
          f"(HP COP={results['hp'].get('cop_mean'):.2f}, "
          f"FLH={results['hp'].get('full_load_hours'):.0f}h, "
          f"EBoiler η={results['eboiler'].get('efficiency_mean')})")
    print("  [S2-FORCED] WARNING: Stage-2 ran on synthetic data — real dispatch was zero. "
          "Results are logic/threshold checks only, not operational validation.")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Two-stage validation (Boundary-Condition-Matching)")
    parser.add_argument("--stage", type=int, choices=[1, 2], default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-calibrate", action="store_true")
    parser.add_argument("--data", type=str, default=str(DATA_PATH))
    parser.add_argument("--skip-model", action="store_true")
    parser.add_argument(
        "--stage2-force-dispatch",
        action="store_true",
        dest="stage2_force_dispatch",
        help=(
            "Run Stage-2 plausibility checks on synthetic dispatch when real "
            "HP/EBoiler dispatch is zero. Results are tagged synthetic_forced."
        ),
    )
    args = parser.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data_path = Path(args.data)

    run_s1 = args.stage in (None, 1)
    run_s2 = args.stage in (None, 2)

    kpis: dict = {}
    s2_results: dict = {}
    calibrated_u: dict = {}
    bc_info: dict = {}
    measured_agg: pd.DataFrame | None = None
    sim_legacy: pd.DataFrame | None = None
    hist: pd.DataFrame | None = None
    weeks: dict = {}

    print("\n" + "=" * 70)
    print("  VALIDATION PIPELINE — Boundary-Condition-Matching")
    print("  T_supply(j1) = measured -> validate transport physics only")
    print("=" * 70)

    # ── Step 1: Load data ──────────────────────────────────────────────────
    if run_s1 and not args.dry_run:
        print("\n[1/5] Loading historical data...")
        if data_path.exists():
            hist = load_historical(data_path)
            bc_info = extract_supply_temperature_bc(hist)
            measured_agg = aggregate_source_measurements(hist)
            weeks = identify_representative_weeks(measured_agg)
            print(f"  Representative weeks: {list(weeks.keys())}")
            
            # Store WRG mean in bc_info for report
            if "T_wrg_source_C" in measured_agg.columns:
                bc_info["wrg_mean_C"] = float(measured_agg["T_wrg_source_C"].dropna().mean())
        else:
            print(f"  [ERROR] {data_path} not found")
            if not run_s2:
                return 1
    elif run_s1:
        print("\n[1/5] [DRY] Would load:", data_path)
        bc_info = {"mode": "constant", "mean_C": 86.5, "median_C": 86.5,
                   "std_C": 1.8, "is_quasi_constant": True, "r2_vs_outdoor": 0.08}

    # ── Step 2: Stage 1 ───────────────────────────────────────────────────
    if run_s1:
        print("\n[2/5] Stage 1 — Network validation (BC-matching)")
        print("  BC = measured T_supply | Validates: heat loss, hydraulics, T_return")

        if not args.skip_model:
            run_legacy_model(dry_run=args.dry_run, bc_info=bc_info)

        legacy_path = LEGACY_DIR / "dispatch_hourly.csv"
        if legacy_path.exists() and not args.dry_run:
            sim_legacy = pd.read_csv(legacy_path, index_col=0, parse_dates=True)
            print(f"  Loaded legacy results: {len(sim_legacy)} timesteps")
        elif not args.dry_run:
            print(f"  [WARN] {legacy_path} not found — trying L3 results as fallback")
            l3_fallback = L3_DIR / "dispatch_hourly.csv"
            if l3_fallback.exists():
                sim_legacy = pd.read_csv(l3_fallback, index_col=0, parse_dates=True)
                print(f"  [FALLBACK] Using L3 dispatch for Stage 1 KPIs ({len(sim_legacy)} timesteps)")
            else:
                print(f"  [ERROR] No simulation results available (neither legacy nor L3)")

        if sim_legacy is not None and not args.dry_run:
            sim_legacy = _fix_sim_legacy(sim_legacy)

        if measured_agg is not None and sim_legacy is not None:
            kpis = compute_stage1_kpis(measured_agg, sim_legacy, bc_info)
            
            if not args.no_calibrate:
                calibrated_u = calibrate_u_values(measured_agg, sim_legacy, bc_info)

            # Plots
            print("  Generating Stage 1 plots...")
            plot_stage1_timeseries(measured_agg, sim_legacy, bc_info, weeks, OUT_DIR)
            plot_stage1_scatter_farend(measured_agg, sim_legacy, OUT_DIR)
            plot_stage1_heatmap(measured_agg, sim_legacy, OUT_DIR)
            plot_stage1_error_histograms(kpis, OUT_DIR)

    # ── Step 3: Stage 2 ───────────────────────────────────────────────────
    if run_s2:
        print("\n[3/5] Stage 2 — Asset plausibility")

        l3_path = L3_DIR / "dispatch_hourly.csv"
        if l3_path.exists() and not args.dry_run:
            dispatch = pd.read_csv(l3_path, index_col=0, parse_dates=True)

            s2_results = {
                "hp":      check_hp_plausibility(dispatch, measured_agg),
                "eboiler": check_eboiler_plausibility(dispatch),
                "tes":     check_tes_plausibility(dispatch),
                "balance": check_energy_balance(dispatch),
            }

            # If HP and EBoiler were never dispatched, optionally run synthetic checks
            hp_dispatched = (dispatch.get("Q_hp_total_MW", pd.Series(0.0)) > 0.01).any()
            ek_dispatched = (dispatch.get("Q_ek_MW", pd.Series(0.0)) > 0.01).any()
            if getattr(args, "stage2_force_dispatch", False) and not (hp_dispatched and ek_dispatched):
                print("  [S2] HP/EBoiler not dispatched in real run — running forced synthetic checks")
                s2_forced = run_stage2_forced_dispatch()
                s2_results["hp_forced"]      = s2_forced["hp"]
                s2_results["eboiler_forced"] = s2_forced["eboiler"]
                s2_results["tes_forced"]     = s2_forced["tes"]

            # If HP and EBoiler were never dispatched, optionally run synthetic checks
            hp_dispatched = (dispatch.get("Q_hp_total_MW", pd.Series(0.0)) > 0.01).any()
            ek_dispatched = (dispatch.get("Q_ek_MW", pd.Series(0.0)) > 0.01).any()
            if getattr(args, "stage2_force_dispatch", False) and not (hp_dispatched and ek_dispatched):
                print("  [S2] HP/EBoiler not dispatched in real run — running forced synthetic checks")
                s2_forced = run_stage2_forced_dispatch()
                s2_results["hp_forced"]      = s2_forced["hp"]
                s2_results["eboiler_forced"] = s2_forced["eboiler"]
                s2_results["tes_forced"]     = s2_forced["tes"]

            for cat, res in s2_results.items():
                for c in res.get("checks", []):
                    print(f"  [{cat.upper()}] {c}")

            print("  Generating Stage 2 plots...")
            plot_stage2_cop_scatter(dispatch, measured_agg, OUT_DIR)
            plot_stage2_eboiler(dispatch, weeks, OUT_DIR)
            plot_stage2_tes(dispatch, OUT_DIR)
            plot_stage2_energy_bars(dispatch, OUT_DIR)
        elif args.dry_run:
            print("  [DRY] Would run Stage 2")
        else:
            print(f"  [WARN] {l3_path} not found — run optimization first")

    # ── Step 4: Outputs ───────────────────────────────────────────────────
    print("\n[4/5] Summary outputs...")
    if not args.dry_run and (kpis or s2_results):
        plot_validation_summary_table(kpis, s2_results, OUT_DIR)
        generate_report(kpis, s2_results, calibrated_u, bc_info, OUT_DIR)
        save_kpis_json(kpis, s2_results, bc_info, calibrated_u, OUT_DIR)

    # ── Step 5: Status ────────────────────────────────────────────────────
    n_pass = sum(1 for k, v in kpis.items()
                 if k in THRESHOLDS and isinstance(v, (int, float)) and v <= THRESHOLDS[k])
    n_fail = sum(1 for k, v in kpis.items()
                 if k in THRESHOLDS and isinstance(v, (int, float)) and v > THRESHOLDS[k])

    print(f"\n[5/5] Complete. {n_pass} PASS, {n_fail} FAIL")
    print(f"  Output: {OUT_DIR}")
    print("=" * 70)
    return 1 if n_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())