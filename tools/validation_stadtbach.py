"""Stadtbach validation tool (Paper 2 – BC-SB baseline).

Compares BC-SB simulation output against ACRON measurement data.

Five tiers:
  Tier 1 — Consumer demand: Q_demand_mw (Parquet) vs. measured Waermeleistung (7 stations)
  Tier 2 — Consumer T_supply: all 20 stations with measured Temp_VL (L3-MILP constant BC)
  Tier 3 — Energy balance: annual closure from dispatch_hourly.csv
  Tier 4 — Producer dispatch: HKW / GT-Ost / BMHKW / AVA / HWW / HWS (computed)
            (requires dispatch_per_asset.csv — written by extract_artefacts.py after re-run)
  Tier 5 — Zone boundary temperatures: measured PSS/PSW Temp_VL vs. model j_pss/j_psw

Run:
    python tools/validation_stadtbach.py

Outputs (written to output/paper2_runs/BC-SB/):
    validation_stadtbach_kpis.json
    validation_stadtbach_report.md
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

ROOT       = Path(__file__).resolve().parents[1]
DATA_ACRON = ROOT / "data" / "Stadtbach" / "11_Messwerte_Acron"
RUN_DIR    = ROOT / "output" / "paper2_runs" / "BC-SB"
OUT_DIR    = RUN_DIR

IDX_2025 = pd.date_range("2025-01-01", periods=8760, freq="h")

# ---------------------------------------------------------------------------
# Station / node mappings
# ---------------------------------------------------------------------------

# Tier 1: consumer stations with measured Waermeleistung
# (folder, filename, node_id)
MEASURED_CONSUMERS: dict[str, tuple[str, str]] = {
    "Klinikum":           ("Klinikum",           "Klinikum_Waermeleistung.xlsx"),
    "UNI":                ("UNI",                "UNI_Waermeleistung.xlsx"),
    "KUKA":               ("KUKA",               "KUKA_Waermeleistung.xlsx"),
    "MAN":                ("MAN",                "MAN_Waermeleistung_Station.xlsx"),
    "SIGMA_Technopark":   ("SIGMA_Technopark",   "SIGMA_Technopark_Waermeleistung.xlsx"),
    "Lechhauser_Str":     ("Lechhauser_Str",     "Lechhauser_Str_HA_Waermeleistung.xlsx"),
    "August-Wessels-Str": ("August-Wessels-Str", "August-Wessels-Str_Waermeleistung.xlsx"),
}

STATION_TO_NODE: dict[str, str] = {
    "Klinikum":           "j_klinikum",
    "UNI":                "j_uni",
    "KUKA":               "j_kuka",
    "MAN":                "j_man",
    "SIGMA_Technopark":   "j_sigma_technopark",
    "Lechhauser_Str":     "j_lechhauser_str",
    "August-Wessels-Str": "j_august_wessels_str",
}

# Tier 2: all 20 consumer nodes with measured Temp_VL (folder, node_id)
# File is discovered by glob (*Temp_VL*.xlsx) inside the folder.
TVL_ALL_STATIONS: dict[str, tuple[str, str]] = {
    # 7 measured stations
    "Klinikum":                  ("Klinikum",                  "j_klinikum"),
    "UNI":                       ("UNI",                       "j_uni"),
    "KUKA":                      ("KUKA",                      "j_kuka"),
    "MAN":                       ("MAN",                       "j_man"),
    "SIGMA_Technopark":          ("SIGMA_Technopark",          "j_sigma_technopark"),
    "Lechhauser_Str":            ("Lechhauser_Str",            "j_lechhauser_str"),
    "August-Wessels-Str":        ("August-Wessels-Str",        "j_august_wessels_str"),
    # 13 zone-estimated with T_VL only
    "Am_Mittleren_Moos":         ("Am_Mittleren_Moos",         "j_am_mittleren_moos"),
    "Beethovenpark":             ("Beethovenpark",             "j_beethovenpark"),
    "Fraunhofer":                ("Fraunhofer",                "j_fraunhofer"),
    "Fuggerstr":                 ("Fuggerstr",                 "j_fuggerstr"),
    "Grasiger_Weg":              ("Grasiger_Weg",              "j_grasiger_weg"),
    "Hans-Boeckler-Str":         ("Hans-Boeckler-Str",         "j_hans_boeckler_str"),
    "Hooverstr":                 ("Hooverstr",                 "j_hooverstr"),
    "Josefinum":                 ("Josefinum",                 "j_josefinum"),
    "Kreissparkasse":            ("Kreissparkasse",            "j_kreissparkasse"),
    "Kurt-Schumacher-Str":       ("Kurt-Schumacher-Str",       "j_kurt_schumacher_str"),
    "Schlettererstr":            ("Schlettererstr",            "j_schlettererstr"),
    "Siegfried-Aufhaeuser-Str":  ("Siegfried-Aufhaeuser-Str",  "j_siegfried_aufhaeuser_str"),
    "Theodor-Heuss-Platz":       ("Theodor-Heuss-Platz",       "j_theodor_heuss_platz"),
}

# Tier 4: producer stations with Waermeleistung
# (folder, filename, sim_asset_key in dispatch_per_asset.csv column "{key}_MW")
MEASURED_PRODUCERS: dict[str, tuple[str, str, str]] = {
    "HKW":    ("HKW",            "HKW_Waermeleistung.xlsx",              "HKW"),
    "GT-Ost": ("GT-Ost",         "GT-Ost_Waermeleistung.xlsx",           "GTOST"),
    "BMHKW":  ("BMHKW",         "BMHKW_Waermeleistung.xlsx",            "BMHKW"),
    "AVA":    ("AVA",            "AVA_Waermeleistung.xlsx",              "AVA_FEED"),
    "HWW":    ("HWW_prim_Einsp", "HWW_Waermeleistung_Primeinsp.xlsx",   "HWW_BOILER"),
}

# HWS has no Waermeleistung file — computed from Durchfluss + ΔT
HWS_FILES = {
    "folder": "Heizwerk_Sued",
    "tvl":    "Heizwerk_Sued_Temp_VL.xlsx",
    "trl":    "Heizwerk_Sued_Temp_RL.xlsx",
    "flow":   "Heizwerk_Sued_Durchfluss.xlsx",  # m³/h
    "asset":  "HWS_BOILER",
}

# Tier 5: zone boundary pump stations
# (folder, tvl_file, node_id_in_sim)
ZONE_BOUNDARIES: dict[str, tuple[str, str, str]] = {
    "PSS": ("PSS", "PPS_Temp_VL.xlsx", "j_pss"),
    "PSW": ("PSW", "PSW_Temp_VL.xlsx", "j_psw"),
}


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _read_acron_file(station_dir: str, filename: str) -> pd.Series:
    """Read an ACRON Excel (skiprows=2, Datum+Zeit+Wert) → hourly 2025 Series."""
    fp = DATA_ACRON / station_dir / filename
    if not fp.exists():
        return pd.Series(dtype=float)
    df = pd.read_excel(fp, skiprows=2, header=0, engine="openpyxl")
    dates = pd.to_datetime(df["Datum"]).dt.normalize()
    hours = (
        df["Zeit"].astype(str).str.strip()
        .str.split("-").str[0]
        .str.split(":").str[0]
        .astype(int)
    )
    idx = dates + pd.to_timedelta(hours, unit="h")
    s = pd.Series(pd.to_numeric(df["Wert"], errors="coerce").values, index=idx, dtype=float)
    s = s[~s.index.duplicated(keep="first")]
    if len(s) > 9000:
        s = s.resample("h").mean()
    return s.reindex(IDX_2025).ffill().bfill().fillna(0.0)


def _find_tvl_file(station_folder: str) -> str | None:
    """Glob for *Temp_VL*.xlsx inside a station folder."""
    folder = DATA_ACRON / station_folder
    matches = sorted(folder.glob("*Temp_VL*.xlsx"))
    return matches[0].name if matches else None


def load_measured_demand(station: str) -> pd.Series:
    subfolder, filename = MEASURED_CONSUMERS[station]
    return _read_acron_file(subfolder, filename)


def load_measured_tsup(station: str) -> pd.Series | None:
    """Load measured Temp_VL for any station that has one (glob-based)."""
    if station in TVL_ALL_STATIONS:
        folder = TVL_ALL_STATIONS[station][0]
    elif station in ZONE_BOUNDARIES:
        folder = ZONE_BOUNDARIES[station][0]
    else:
        return None
    filename = _find_tvl_file(folder)
    if filename is None:
        return None
    s = _read_acron_file(folder, filename)
    return s if len(s) == 8760 else None


def load_measured_producer(name: str) -> pd.Series:
    """Load measured Waermeleistung for a named producer station."""
    folder, filename, _ = MEASURED_PRODUCERS[name]
    return _read_acron_file(folder, filename)


def load_measured_hws_q() -> pd.Series:
    """Compute HWS heat output from Durchfluss [m³/h] and ΔT [K].

    Q [MW] = Durchfluss [m³/h] × cp × ΔT / 3600
    cp ≈ 4.18 kJ/(kg·K),  ρ ≈ 1000 kg/m³
    """
    f  = HWS_FILES
    s_tvl  = _read_acron_file(f["folder"], f["tvl"])
    s_trl  = _read_acron_file(f["folder"], f["trl"])
    s_flow = _read_acron_file(f["folder"], f["flow"])
    delta_t = (s_tvl - s_trl).clip(lower=0.0)
    q_mw = s_flow * 4.18 * delta_t / 3600.0
    return q_mw.clip(lower=0.0)


def load_simulation_demand(run_dir: Path) -> pd.DataFrame:
    """Load per-node hourly demand from nodes_state_hourly.parquet."""
    pq_path = run_dir / "nodes_state_hourly.parquet"
    if not pq_path.exists():
        raise FileNotFoundError(f"Parquet not found: {pq_path}")
    pq = pd.read_parquet(pq_path, columns=["timestamp", "node_id", "Q_demand_mw"])
    pq["ts_int"] = pd.to_numeric(pq["timestamp"], errors="coerce").astype("Int64")
    pq = pq.dropna(subset=["ts_int"])
    pq["datetime"] = IDX_2025[pq["ts_int"].values - 1]
    return pq.pivot_table(index="datetime", columns="node_id",
                          values="Q_demand_mw", aggfunc="first")


def load_simulation_tsup_constant(run_dir: Path) -> dict[str, float]:
    """Read per-node supply temperatures from node_temperatures.csv (constant for L3-MILP)."""
    csv_path = run_dir / "node_temperatures.csv"
    if not csv_path.exists():
        return {}
    df = pd.read_csv(csv_path, nrows=1)
    return {col[len("T_node_"):]: float(df[col].iloc[0])
            for col in df.columns if col.startswith("T_node_")}


def load_dispatch(run_dir: Path) -> pd.DataFrame:
    return pd.read_csv(run_dir / "dispatch_hourly.csv")


def load_per_asset(run_dir: Path) -> pd.DataFrame | None:
    """Load dispatch_per_asset.csv if available (written after corrected-topology re-run)."""
    p = run_dir / "dispatch_per_asset.csv"
    if not p.exists():
        return None
    return pd.read_csv(p)


# ---------------------------------------------------------------------------
# KPI computation
# ---------------------------------------------------------------------------

def _kpis_demand(meas: pd.Series, sim: pd.Series) -> dict:
    df = pd.DataFrame({"meas": meas, "sim": sim}).dropna()
    df = df[df["meas"] >= 0.0]
    if len(df) < 10:
        return {"n": len(df), "error": "too few samples"}

    err  = df["sim"] - df["meas"]
    mae  = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    bias = float(np.mean(err))

    meas_pos = df["meas"][df["meas"] > 0.01]
    mape = float(np.mean(np.abs((df["sim"][meas_pos.index] - meas_pos) / meas_pos)) * 100) \
           if len(meas_pos) > 0 else None

    r2 = float(np.corrcoef(df["meas"], df["sim"])[0, 1] ** 2) if len(df) > 1 else None

    annual_meas = float(df["meas"].sum())
    annual_sim  = float(df["sim"].sum())
    annual_err  = (annual_sim - annual_meas) / annual_meas * 100 if annual_meas > 0 else None

    return {
        "n":              len(df),
        "MAE_MW":         round(mae,  4),
        "RMSE_MW":        round(rmse, 4),
        "bias_MW":        round(bias, 4),
        "MAPE_pct":       round(mape, 2) if mape is not None else None,
        "R2":             round(r2,   4) if r2 is not None else None,
        "annual_meas_MWh": round(annual_meas, 1),
        "annual_sim_MWh":  round(annual_sim,  1),
        "annual_err_pct":  round(annual_err,  3) if annual_err is not None else None,
    }


def _kpis_tsup(meas: pd.Series, sim_const: float, gate_c: float = 2.0) -> dict:
    s = meas.dropna()
    s = s[s > 50.0]
    if len(s) < 10:
        return {"n": len(s), "error": "too few samples"}

    err  = sim_const - s
    mae  = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    bias = float(np.mean(err))
    gate = float(100.0 * np.mean(np.abs(err) <= gate_c))

    return {
        "n":             len(s),
        "sim_const_C":   round(sim_const, 3),
        "meas_mean_C":   round(float(s.mean()), 3),
        "meas_std_C":    round(float(s.std()),  3),
        "MAE_C":         round(mae,  3),
        "RMSE_C":        round(rmse, 3),
        "bias_C":        round(bias, 3),
        f"gate_{gate_c:.0f}C_pct": round(gate, 1),
        "note": "L3-MILP constant T_supply BC — temporal variation not modelled",
    }


def _kpis_producer(meas: pd.Series, sim: pd.Series) -> dict:
    """KPIs for producer dispatch (same formula as demand but with producer note)."""
    df = pd.DataFrame({"meas": meas, "sim": sim}).dropna()
    df = df[(df["meas"] >= 0.0) & (df["sim"] >= 0.0)]
    if len(df) < 10:
        return {"n": len(df), "error": "too few samples"}

    err  = df["sim"] - df["meas"]
    mae  = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    bias = float(np.mean(err))

    meas_pos = df["meas"][df["meas"] > 0.1]
    mape = float(np.mean(np.abs((df["sim"][meas_pos.index] - meas_pos) / meas_pos)) * 100) \
           if len(meas_pos) > 0 else None

    r2 = float(np.corrcoef(df["meas"], df["sim"])[0, 1] ** 2) if len(df) > 1 else None

    annual_meas = float(df["meas"].sum())
    annual_sim  = float(df["sim"].sum())
    annual_err  = (annual_sim - annual_meas) / annual_meas * 100 if annual_meas > 0 else None

    return {
        "n":              len(df),
        "MAE_MW":         round(mae,  3),
        "RMSE_MW":        round(rmse, 3),
        "bias_MW":        round(bias, 3),
        "MAPE_pct":       round(mape, 2) if mape is not None else None,
        "R2":             round(r2,   4) if r2 is not None else None,
        "annual_meas_MWh": round(annual_meas, 1),
        "annual_sim_MWh":  round(annual_sim,  1),
        "annual_err_pct":  round(annual_err,  3) if annual_err is not None else None,
    }


def _energy_balance(dispatch: pd.DataFrame) -> dict:
    gen_cols = ["Q_chp_MW", "Q_gasboiler_MW", "Q_biomass_MW", "Q_hp_total_MW", "Q_ek_MW"]
    gen_total  = sum(dispatch[c].fillna(0).sum() for c in gen_cols if c in dispatch.columns)
    discharge  = dispatch["Q_storage_discharge_MW"].fillna(0).sum() \
                 if "Q_storage_discharge_MW" in dispatch.columns else 0.0
    charge     = dispatch["Q_storage_charge_MW"].fillna(0).sum() \
                 if "Q_storage_charge_MW" in dispatch.columns else 0.0
    demand     = dispatch["Q_demand_total_MW"].fillna(0).sum() \
                 if "Q_demand_total_MW" in dispatch.columns else 0.0
    losses     = dispatch["Q_loss_total_MW"].fillna(0).sum() \
                 if "Q_loss_total_MW" in dispatch.columns else 0.0

    supply  = gen_total + discharge - charge
    closure = abs(supply - losses - demand) / demand * 100 if demand > 0 else None
    flag    = "ok" if (closure is not None and closure <= 2.0) else (
              "ZERO_GENERATION" if gen_total == 0 else "HIGH_IMBALANCE")

    return {
        "generation_MWh":    round(gen_total, 1),
        "discharge_MWh":     round(discharge, 1),
        "charge_MWh":        round(charge,    1),
        "demand_MWh":        round(demand,    1),
        "losses_MWh":        round(losses,    1),
        "closure_error_pct": round(closure, 3) if closure is not None else None,
        "flag":  flag,
        "note": (
            "Generation = 0 in dispatch_hourly.csv — multi-node dispatch not exported. "
            "Re-run BC-SB with corrected 32-node topology + updated extract_artefacts.py."
            if gen_total == 0 else ""
        ),
    }


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

def _write_json(report: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)


def _write_md(report: dict, path: Path) -> None:
    lines = [
        "# Stadtbach Validation Report (BC-SB)\n\n",

        "## Tier 1 — Consumer Heat Demand (7 measured stations)\n\n",
        "| Station | n | MAE [MW] | MAPE [%] | R² | Annual err [%] |\n",
        "|---------|---|----------|----------|----|----------------|\n",
    ]
    for st, kpi in report.get("tier1_demand", {}).items():
        if "error" in kpi:
            lines.append(f"| {st} | — | {kpi['error']} | | | |\n")
        else:
            lines.append(
                f"| {st} | {kpi.get('n','—')} "
                f"| {kpi.get('MAE_MW','—')} "
                f"| {kpi.get('MAPE_pct','—')} "
                f"| {kpi.get('R2','—')} "
                f"| {kpi.get('annual_err_pct','—')} |\n"
            )

    lines += [
        "\n## Tier 2 — Consumer Supply Temperature (20 stations)\n\n",
        "**Note:** L3-MILP uses constant supply temperature BC; temporal variation not modelled.\n\n",
        "| Station | n | Sim [°C] | Meas mean [°C] | MAE [°C] | Gate±2°C [%] |\n",
        "|---------|---|----------|---------------|----------|---------------|\n",
    ]
    for st, kpi in report.get("tier2_tsup", {}).items():
        if "error" in kpi:
            lines.append(f"| {st} | — | — | — | — | — |\n")
        else:
            lines.append(
                f"| {st} | {kpi.get('n','—')} "
                f"| {kpi.get('sim_const_C','—')} "
                f"| {kpi.get('meas_mean_C','—')} "
                f"| {kpi.get('MAE_C','—')} "
                f"| {kpi.get('gate_2C_pct','—')} |\n"
            )

    eb = report.get("tier3_energy_balance", {})
    lines += [
        "\n## Tier 3 — Annual Energy Balance\n\n",
        f"- Generation: {eb.get('generation_MWh','?')} MWh\n",
        f"- Demand:     {eb.get('demand_MWh','?')} MWh\n",
        f"- Losses:     {eb.get('losses_MWh','?')} MWh\n",
        f"- Closure error: {eb.get('closure_error_pct','?')} %\n",
        f"- Flag: **{eb.get('flag','?')}**\n",
    ]
    if eb.get("note"):
        lines.append(f"\n> {eb['note']}\n")

    lines += [
        "\n## Tier 4 — Producer Dispatch\n\n",
    ]
    if report.get("tier4_producers", {}).get("_status") == "AWAITING_RERUN":
        lines.append(
            "> `dispatch_per_asset.csv` not found. "
            "Re-run BC-SB with updated extract_artefacts.py to enable producer validation.\n"
        )
    else:
        lines += [
            "| Producer | n | MAE [MW] | MAPE [%] | R² | Annual meas [MWh] | Annual err [%] |\n",
            "|---------|---|----------|----------|----|-------------------|----------------|\n",
        ]
        for prod, kpi in report.get("tier4_producers", {}).items():
            if prod.startswith("_"):
                continue
            if "error" in kpi:
                lines.append(f"| {prod} | — | {kpi.get('error','')} | | | | |\n")
            else:
                lines.append(
                    f"| {prod} | {kpi.get('n','—')} "
                    f"| {kpi.get('MAE_MW','—')} "
                    f"| {kpi.get('MAPE_pct','—')} "
                    f"| {kpi.get('R2','—')} "
                    f"| {kpi.get('annual_meas_MWh','—')} "
                    f"| {kpi.get('annual_err_pct','—')} |\n"
                )

    lines += ["\n## Tier 5 — Zone Boundary Temperatures (PSS/PSW)\n\n"]
    if not report.get("tier5_zone_boundaries"):
        lines.append("> No zone boundary data available.\n")
    else:
        lines += [
            "| Station | n | Sim [°C] | Meas mean [°C] | MAE [°C] |\n",
            "|---------|---|----------|---------------|----------|\n",
        ]
        for st, kpi in report.get("tier5_zone_boundaries", {}).items():
            if "error" in kpi:
                lines.append(f"| {st} | — | — | — | — |\n")
            else:
                lines.append(
                    f"| {st} | {kpi.get('n','—')} "
                    f"| {kpi.get('sim_const_C','—')} "
                    f"| {kpi.get('meas_mean_C','—')} "
                    f"| {kpi.get('MAE_C','—')} |\n"
                )

    dq = report.get("data_quality", {})
    if dq:
        lines += ["\n## Data Quality Flags\n\n"]
        for k, v in dq.items():
            lines.append(f"- **{k}**: {v}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_validation(
    run_dir: Path = RUN_DIR,
    out_dir: Path | None = None,
) -> dict:
    if out_dir is None:
        out_dir = run_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "run_dir":              str(run_dir),
        "data_quality":         {},
        "tier1_demand":         {},
        "tier2_tsup":           {},
        "tier3_energy_balance": {},
        "tier4_producers":      {},
        "tier5_zone_boundaries": {},
    }

    # --- Load simulation data ---
    print("Loading simulation data ...")
    sim_demand_df  = load_simulation_demand(run_dir)
    sim_tsup_nodes = load_simulation_tsup_constant(run_dir)
    dispatch       = load_dispatch(run_dir)
    per_asset_df   = load_per_asset(run_dir)

    # Data quality flags
    gen_cols = ["Q_chp_MW", "Q_gasboiler_MW", "Q_biomass_MW", "Q_hp_total_MW", "Q_ek_MW"]
    if all(dispatch[c].fillna(0).max() == 0 for c in gen_cols if c in dispatch.columns):
        report["data_quality"]["generation_export"] = (
            "ZERO — all generation columns in dispatch_hourly.csv are 0. "
            "Re-run BC-SB with updated extract_artefacts.py."
        )

    consumer_ts = [sim_tsup_nodes.get(n) for n in STATION_TO_NODE.values() if n in sim_tsup_nodes]
    if consumer_ts and max(consumer_ts) - min(consumer_ts) < 0.01:
        report["data_quality"]["T_supply_temporal"] = (
            f"CONSTANT = {consumer_ts[0]:.3f}°C at all consumer nodes. "
            "L3-MILP uses mean supply temperature as fixed BC."
        )

    pq_raw = pd.read_parquet(run_dir / "nodes_state_hourly.parquet", columns=["timestamp"])
    if np.issubdtype(pq_raw["timestamp"].dtype, np.integer):
        report["data_quality"]["timestamps_parquet"] = (
            "INTEGER nanoseconds (1..8760) — remapped to 2025-01-01 00:00 + (t-1)h"
        )

    # --- Tier 1: Consumer demand (7 measured stations) ---
    print("\nTier 1 — Demand validation (7 measured consumers) ...")
    for station, node_id in STATION_TO_NODE.items():
        print(f"  {station} ({node_id}) ...")
        meas_q = load_measured_demand(station)
        if node_id in sim_demand_df.columns:
            sim_q = sim_demand_df[node_id].reindex(IDX_2025)
        else:
            report["tier1_demand"][station] = {"error": f"node {node_id} not in Parquet"}
            continue
        report["tier1_demand"][station] = _kpis_demand(meas_q, sim_q)
        k = report["tier1_demand"][station]
        print(f"    MAE={k.get('MAE_MW','?')} MW  MAPE={k.get('MAPE_pct','?')}%  "
              f"annual_err={k.get('annual_err_pct','?')}%  R²={k.get('R2','?')}")

    # --- Tier 2: Consumer T_supply (all 20 stations with T_VL) ---
    print("\nTier 2 — Supply temperature (all 20 consumer stations) ...")
    for station, (folder, node_id) in TVL_ALL_STATIONS.items():
        meas_tvl = load_measured_tsup(station)
        sim_const = sim_tsup_nodes.get(node_id)
        if meas_tvl is None or sim_const is None:
            report["tier2_tsup"][station] = {"error": "T_VL or sim data not available"}
            continue
        report["tier2_tsup"][station] = _kpis_tsup(meas_tvl, sim_const)
        k = report["tier2_tsup"][station]
        print(f"  {station}: sim={sim_const:.1f}°C  "
              f"meas_mean={k.get('meas_mean_C','?')}°C  MAE={k.get('MAE_C','?')}°C")

    # --- Tier 3: Energy balance ---
    print("\nTier 3 — Energy balance ...")
    report["tier3_energy_balance"] = _energy_balance(dispatch)
    eb = report["tier3_energy_balance"]
    print(f"  Gen={eb['generation_MWh']} MWh  Demand={eb['demand_MWh']} MWh  "
          f"Losses={eb['losses_MWh']} MWh  err={eb['closure_error_pct']}%  [{eb['flag']}]")

    # --- Tier 4: Producer dispatch ---
    print("\nTier 4 — Producer dispatch ...")
    if per_asset_df is None:
        print("  dispatch_per_asset.csv not found — AWAITING_RERUN")
        report["tier4_producers"]["_status"] = "AWAITING_RERUN"
    else:
        # Named producers with direct Waermeleistung
        for name, (folder, fname, asset_key) in MEASURED_PRODUCERS.items():
            col = f"{asset_key}_MW"
            if col not in per_asset_df.columns:
                report["tier4_producers"][name] = {"error": f"column {col} not in dispatch_per_asset.csv"}
                continue
            meas_q = load_measured_producer(name)
            sim_q  = pd.Series(per_asset_df[col].values, index=IDX_2025)
            report["tier4_producers"][name] = _kpis_producer(meas_q, sim_q)
            k = report["tier4_producers"][name]
            print(f"  {name}: MAE={k.get('MAE_MW','?')} MW  "
                  f"MAPE={k.get('MAPE_pct','?')}%  annual_err={k.get('annual_err_pct','?')}%")

        # HWS: compute from Durchfluss + ΔT
        hws_col = f"{HWS_FILES['asset']}_MW"
        meas_hws = load_measured_hws_q()
        if hws_col in per_asset_df.columns:
            sim_hws = pd.Series(per_asset_df[hws_col].values, index=IDX_2025)
            report["tier4_producers"]["HWS"] = _kpis_producer(meas_hws, sim_hws)
            k = report["tier4_producers"]["HWS"]
            print(f"  HWS (computed): MAE={k.get('MAE_MW','?')} MW  "
                  f"MAPE={k.get('MAPE_pct','?')}%  annual_err={k.get('annual_err_pct','?')}%")
        else:
            report["tier4_producers"]["HWS"] = {
                "error": f"column {hws_col} not in dispatch_per_asset.csv",
                "note": "HWS Q computed from Durchfluss × cp × ΔT",
                "annual_meas_MWh": round(float(meas_hws.sum()), 1),
            }

    # --- Tier 5: Zone boundary temperatures (PSS/PSW) ---
    print("\nTier 5 — Zone boundary temperatures (PSS/PSW) ...")
    for name, (folder, tvl_file, node_id) in ZONE_BOUNDARIES.items():
        meas_tvl = _read_acron_file(folder, tvl_file)
        sim_const = sim_tsup_nodes.get(node_id)
        if len(meas_tvl) != 8760 or sim_const is None:
            report["tier5_zone_boundaries"][name] = {
                "error": "T_VL data or sim node not available",
                "node_id": node_id,
            }
            if sim_const is None:
                print(f"  {name}: node {node_id} not found in simulation "
                      "(new topology — needs re-run)")
            continue
        report["tier5_zone_boundaries"][name] = _kpis_tsup(meas_tvl, sim_const)
        report["tier5_zone_boundaries"][name]["node_id"] = node_id
        k = report["tier5_zone_boundaries"][name]
        print(f"  {name} ({node_id}): sim={sim_const:.1f}°C  "
              f"meas_mean={k.get('meas_mean_C','?')}°C  MAE={k.get('MAE_C','?')}°C")

    # --- Write outputs ---
    json_path = out_dir / "validation_stadtbach_kpis.json"
    md_path   = out_dir / "validation_stadtbach_report.md"
    _write_json(report, json_path)
    _write_md(report, md_path)
    print(f"\nReport written:\n  {json_path}\n  {md_path}")

    return report


if __name__ == "__main__":
    run_validation()
