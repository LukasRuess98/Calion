"""
§3 Output Artefact Extraction
Converts a WorkflowResult into the paper's canonical output files.

Output layout (all under outdir/):
  meta.json
  economics.csv
  dispatch_hourly.csv
  pipes.csv
  pipe_state_hourly.parquet
  validation.json
  linearization_diagnostics.csv  (L3+, L3NL only)
"""
from __future__ import annotations

import datetime
import json
import math
import platform
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _gurobi_version() -> str | None:
    try:
        import gurobipy
        v = gurobipy.gurobi.version()
        return ".".join(str(x) for x in v)
    except Exception:
        return None


def _peak_ram_gb() -> float | None:
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1e9, 3)
    except Exception:
        return None


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _summary_val(summary: dict, section: str, key: str, default: float = 0.0) -> float:
    return _safe(summary.get(section, {}).get(key, default), default)


# ---------------------------------------------------------------------------
# §3.1 meta.json
# ---------------------------------------------------------------------------

def write_meta(
    outdir: Path,
    run_id: str,
    config_path: str,
    workflow,
    solve_time_s: float,
) -> dict:
    result = workflow.pf_result
    solver_info = result.solver if result else {}
    summary = result.summary if result else {}

    obj_val = _summary_val(summary, "objective", "OBJ_value_EUR")
    mip_gap = solver_info.get("mip_gap") or solver_info.get("gap")

    milp_linearize = workflow.config.get("scenario", {}).get("milp_linearize", True)
    model_class = "MILP" if milp_linearize else "MIQCP"

    meta = {
        "run_id": run_id,
        "config_path": config_path,
        "git_sha": _git_sha(),
        "gurobi_version": _gurobi_version(),
        "solve_time_s": round(solve_time_s, 2),
        "mip_gap": _safe(mip_gap) if mip_gap is not None else None,
        "objective": obj_val,
        "num_vars": None,
        "num_bin": None,
        "num_constr": None,
        "num_quad_constr": None,
        "model_class": model_class,
        "wall_clock": datetime.datetime.now().isoformat(),
        "peak_RAM_GB": _peak_ram_gb(),
        "solver_status": solver_info.get("termination_condition", "unknown"),
        "python_version": platform.python_version(),
    }

    (outdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


# ---------------------------------------------------------------------------
# §3.2 economics.csv
# ---------------------------------------------------------------------------

def write_economics(outdir: Path, run_id: str, workflow) -> pd.DataFrame:
    result = workflow.pf_result
    if result is None:
        return pd.DataFrame()

    summary = result.summary
    series = result.series

    obj = summary.get("objective", {})
    grid = summary.get("grid", {})
    hp = summary.get("heat_pump_hp_main", {})

    heat_demand_MWh = _safe(grid.get("Heat_demand_MWh"))
    cost_total = _safe(obj.get("OBJ_value_EUR"))
    cost_energy_buy = _safe(obj.get("Grid_energy_cost_EUR") or obj.get("Electricity_base_cost_EUR"))
    revenue_sell = _safe(obj.get("Grid_sell_revenue_EUR"))
    cost_fuel = _safe(obj.get("Fuel_cost_EUR"))
    cost_co2 = _safe(obj.get("CO2_cost_EUR"))
    cost_dump = _safe(obj.get("Dump_cost_EUR"))
    cost_demand = _safe(obj.get("Demand_charge_cost_EUR"))

    # Pump cost: not directly in summary — compute from series if available
    p_pump_series = series.get("P_pump_total_MW") or series.get("pump_P_MW") or []
    cost_pump = sum(p_pump_series) * 35.0 if p_pump_series else 0.0  # approx grid price

    energy_buy = _safe(grid.get("Energy_from_grid_MWh"))
    energy_sell = _safe(grid.get("Energy_to_grid_MWh"))

    # Gas consumption: from fuel summary
    gas_mwh = 0.0
    for sec, vals in summary.items():
        if "chp" in sec.lower() or "boiler" in sec.lower():
            gas_mwh += _safe(vals.get("Gas_consumption_MWh") or vals.get("Fuel_input_MWh"))

    co2_total = _safe(grid.get("Total_CO2_emissions_t"))
    co2_grid = _safe(grid.get("Grid_CO2_emissions_t"))
    co2_fuel = _safe(obj.get("CO2_fuel_to_heat_kg", 0.0)) / 1000.0

    peak_import = _safe(obj.get("P_buy_peak_MW"))
    p_sell_series = series.get("P_sell_MW") or []
    peak_export = max(p_sell_series) if p_sell_series else 0.0

    lcoh = (cost_total / heat_demand_MWh) if heat_demand_MWh > 0 else float("nan")

    hp_total = _safe(hp.get("Heat_output_MWh"))
    share_HP = (hp_total / heat_demand_MWh * 100) if heat_demand_MWh > 0 else 0.0
    share_CHP = 0.0  # TODO: add CHP section when CHP summary available
    share_EK = 0.0   # No electrode boiler

    row = {
        "run_id": run_id,
        "cost_total_eur": cost_total,
        "cost_energy_buy_eur": cost_energy_buy,
        "revenue_sell_eur": revenue_sell,
        "cost_fuel_eur": cost_fuel,
        "cost_co2_eur": cost_co2,
        "cost_dump_eur": cost_dump,
        "cost_demand_charge_eur": cost_demand,
        "cost_pump_eur": cost_pump,
        "energy_buy_MWh": energy_buy,
        "energy_sell_MWh": energy_sell,
        "gas_consumption_MWh": gas_mwh,
        "co2_total_t": co2_total,
        "co2_grid_t": co2_grid,
        "co2_fuel_t": co2_fuel,
        "peak_import_MW": peak_import,
        "peak_export_MW": peak_export,
        "lcoh_eur_per_MWh_th": round(lcoh, 4) if math.isfinite(lcoh) else None,
        "share_HP_pct": round(share_HP, 2),
        "share_CHP_pct": round(share_CHP, 2),
        "share_EK_pct": round(share_EK, 2),
    }

    df = pd.DataFrame([row])
    df.to_csv(outdir / "economics.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# §3.3 dispatch_hourly.csv
# ---------------------------------------------------------------------------

def write_dispatch_hourly(outdir: Path, run_id: str, workflow, dt_h: float = 1.0) -> pd.DataFrame:
    result = workflow.pf_result
    if result is None:
        return pd.DataFrame()

    series = result.series
    table = result.table

    T = len(next(iter(series.values()))) if series else 0
    if T == 0:
        return pd.DataFrame()

    # Build timestamp index from table if available — always clip to T
    try:
        timestamps = list(table.index)[:T]
        if len(timestamps) < T:
            timestamps += [f"t{i}" for i in range(len(timestamps), T)]
    except Exception:
        timestamps = [f"t{i}" for i in range(T)]

    def s(key: str) -> list:
        raw = series.get(key)
        if not raw:
            return [0.0] * T
        # Clip or pad to exactly T to guard against length mismatches
        if len(raw) > T:
            return list(raw[:T])
        if len(raw) < T:
            return list(raw) + [0.0] * (T - len(raw))
        return list(raw)

    # Map series keys to §3.3 schema columns
    # Network pipe data: read from framework export if available
    net_export = Path(workflow.pf_result.solver.get("export_dir", ""))
    pipe_ts = net_export / "thermal_network" / "pipes" / "pipes_timeseries.csv"

    q_loss_total = [0.0] * T
    p_pump = [0.0] * T
    t_supply = [100.0] * T
    t_return = [40.0] * T

    if pipe_ts.exists():
        try:
            pdf = pd.read_csv(pipe_ts, sep=";", index_col=0)
            loss_cols_sup = [c for c in pdf.columns if c.endswith("_Q_loss_supply")]
            loss_cols_ret = [c for c in pdf.columns if c.endswith("_Q_loss_return")]
            raw_loss = (pdf[loss_cols_sup].sum(axis=1) + pdf[loss_cols_ret].sum(axis=1)).tolist()
            # Clip/pad to T
            q_loss_total = (raw_loss[:T] if len(raw_loss) >= T
                            else raw_loss + [0.0] * (T - len(raw_loss)))
        except Exception:
            pass

    rows = {
        "timestamp": timestamps,
        "Q_demand_total_MW": s("Q_demand_total_MW") or [0.0] * T,
        # --- CHP (uppercase in result_collector) ---
        "Q_chp_MW": s("CHP_MAIN_Q_th_MW"),
        "P_chp_el_MW": s("CHP_MAIN_Pel_MW"),
        "F_chp_gas_MW": s("CHP_MAIN_fuel_MW"),
        # --- Gas Boiler (NEU - fehlte komplett!) ---
        "Q_gasboiler_MW": s("GASBOILER_MAIN_Q_th_MW"),
        "F_gasboiler_MW": s("GASBOILER_MAIN_fuel_MW"),
        # --- Biomass Boiler (NEU - fehlte komplett!) ---
        "Q_biomass_MW": s("BIOMASS_MAIN_Q_th_MW"),
        "F_biomass_MW": s("BIOMASS_MAIN_fuel_MW"),
        # --- Heat Pump (lowercase - HP uses asset.id directly) ---
        "Q_hp_total_MW": s("hp_main_Q_th_MW"),
        "Q_hp_wrg_MW": s("hp_main_Q_wrg_MW"),
        "Q_hp_def_MW": s("hp_main_Q_def_MW"),
        "P_hp_el_MW": s("hp_main_Pel_MW"),
        "COP_hp_wrg": s("hp_main_COP"),
        # --- E-Boiler (uppercase after P2H fix in result_collector) ---
        "Q_ek_MW": s("EBOILER_MAIN_Q_th_MW"),
        "P_ek_el_MW": s("EBOILER_MAIN_Pel_MW"),
        # --- Storage ---
        "Q_storage_charge_MW": s("TES_charge_MW"),
        "Q_storage_discharge_MW": s("TES_discharge_MW"),
        "SOC_MWh": s("TES_SOC_MWh"),
        # --- Grid ---
        "P_buy_MW": s("P_buy_MW"),
        "P_sell_MW": s("P_sell_MW"),
        "lambda_buy_eur_MWh": [0.0] * T,
        "lambda_sell_eur_MWh": [0.0] * T,
        "ef_grid_kg_MWh": s("grid_co2_kg_MWh")
    }

    # Try to fill lambda_buy from table
    try:
        price_col = [c for c in table.columns if "strompreis" in c.lower() or "price" in c.lower()]
        if price_col:
            rows["lambda_buy_eur_MWh"] = list(table[price_col[0]])[:T]
    except Exception:
        pass

    # Final guard: truncate any array that ended up longer than T
    for k, v in rows.items():
        if isinstance(v, list) and len(v) != T:
            rows[k] = (v[:T] if len(v) > T else v + [0.0] * (T - len(v)))

    df = pd.DataFrame(rows)
    df.to_csv(outdir / "dispatch_hourly.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# §3.4 pipes.csv
# ---------------------------------------------------------------------------

def write_pipes(outdir: Path, run_id: str, workflow) -> pd.DataFrame:
    result = workflow.pf_result
    if result is None:
        return pd.DataFrame()

    net_export = Path(result.solver.get("export_dir", ""))
    pipes_json = net_export / "thermal_network" / "pipes" / "pipes_summary.json"

    if not pipes_json.exists():
        pd.DataFrame().to_csv(outdir / "pipes.csv", index=False)
        return pd.DataFrame()

    raw = json.loads(pipes_json.read_text())
    rows = []
    for p in raw:
        pp = p.get("pressure_params", {})
        rows.append({
            "pipe_id": p.get("pipe_id"),
            "from": p.get("from_node"),
            "to": p.get("to_node"),
            "length_m": p.get("length_m"),
            "diameter_mm": p.get("diameter_mm"),
            "U_value_W_mK": p.get("u_value_w_per_m_k", 0),
            "R_resistance": None,
            "m_dot_max_kg_s": pp.get("effective_max_flow_kg_s"),
            "v_max_m_s": pp.get("max_velocity_m_s"),
            "dp_max_Pa": (p.get("delta_p_supply_max_bar", 0) * 1e5),
            "transport_delay_min": None,
            "k_p_steps": 3,
            "annual_loss_MWh": (
                _safe(p.get("Q_loss_supply_total_mwh"))
                + _safe(p.get("Q_loss_return_total_mwh"))
            ),
            "annual_loss_share_pct": None,
            "peak_velocity_m_s": p.get("velocity_max_m_s"),
            "peak_dp_bar": p.get("delta_p_supply_max_bar"),
            "annual_pump_energy_MWh": None,
        })

    df = pd.DataFrame(rows)
    # Compute annual_loss_share_pct relative to total demand
    net_summary_path = net_export / "thermal_network" / "network_summary.json"
    if net_summary_path.exists():
        ns = json.loads(net_summary_path.read_text())
        total_demand = _safe(ns.get("energy", {}).get("total_heat_delivered_mwh") or
                             ns.get("energy", {}).get("Q_consumer_total_mwh"), 1.0)
        if total_demand > 0:
            df["annual_loss_share_pct"] = df["annual_loss_MWh"] / total_demand * 100

    df.to_csv(outdir / "pipes.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# §3.5 pipe_state_hourly.parquet
# ---------------------------------------------------------------------------

def write_pipe_state(outdir: Path, run_id: str, workflow) -> pd.DataFrame:
    result = workflow.pf_result
    if result is None:
        return pd.DataFrame()

    net_export = Path(result.solver.get("export_dir", ""))
    pipe_ts_path = net_export / "thermal_network" / "pipes" / "pipes_timeseries.csv"

    if not pipe_ts_path.exists():
        return pd.DataFrame()

    wide = pd.read_csv(pipe_ts_path, sep=";", index_col=0)
    # Wide → long
    pipe_ids = sorted(set(c.rsplit("_", 1)[0] for c in wide.columns if "_" in c))
    records = []
    for ts in wide.index:
        row = wide.loc[ts]
        for pid in pipe_ids:
            records.append({
                "timestamp": ts,
                "pipe_id": pid,
                "Q_pipe_MW": _safe(row.get(f"{pid}_Q_consumer")),
                "m_dot_kg_s": _safe(row.get(f"{pid}_m_dot")),
                "dp_Pa": _safe(row.get(f"{pid}_delta_p_supply")) * 1e5,
                "T_in_C": _safe(row.get(f"{pid}_T_supply_in")),
                "T_out_C": _safe(row.get(f"{pid}_T_supply_out")),
                "P_pump_pipe_MW": 0.0,
                "Q_loss_pipe_MW": (
                    _safe(row.get(f"{pid}_Q_loss_supply"))
                    + _safe(row.get(f"{pid}_Q_loss_return"))
                ),
            })

    df = pd.DataFrame(records)
    df.to_parquet(outdir / "pipe_state_hourly.parquet", index=False)
    return df


# ---------------------------------------------------------------------------
# §3.7 validation.json
# ---------------------------------------------------------------------------

def write_validation(outdir: Path, measured_data_path: str | None = None) -> None:
    if measured_data_path is None:
        (outdir / "validation.json").write_text(
            json.dumps({"status": "no_measured_data"}, indent=2), encoding="utf-8"
        )
    # TODO: implement once measured data is provided


# ---------------------------------------------------------------------------
# Main extraction entry point
# ---------------------------------------------------------------------------

def extract_all(
    run_id: str,
    config_path: str,
    workflow,
    solve_time_s: float,
    outdir: Path | None = None,
    measured_data_path: str | None = None,
    is_l3nl: bool = False,
) -> Path:
    if outdir is None:
        outdir = ROOT / "output" / "paper_runs" / run_id
    outdir.mkdir(parents=True, exist_ok=True)

    write_meta(outdir, run_id, config_path, workflow, solve_time_s)
    write_economics(outdir, run_id, workflow)
    write_dispatch_hourly(outdir, run_id, workflow)
    write_pipes(outdir, run_id, workflow)
    try:
        write_pipe_state(outdir, run_id, workflow)
    except Exception as e:
        print(f"  [WARN] pipe_state_hourly.parquet skipped: {e}")
    write_validation(outdir, measured_data_path)

    print(f"  [EXTRACT] {run_id} → {outdir}")
    return outdir
