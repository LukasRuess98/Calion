"""
§3 Output Artefact Extraction
Converts a WorkflowResult into the paper's canonical output files.

Output layout (all under outdir/):
  meta.json
  economics.csv
  dispatch_hourly.csv
  pipes.csv
  pipe_state_hourly.parquet
  nodes_summary.csv
  nodes_seasonal.csv
  nodes_state_hourly.parquet
  node_temperatures.csv
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
SEASON_BY_MONTH = {
    12: "winter", 1: "winter", 2: "winter",
    3: "transition", 4: "transition", 5: "transition",
    6: "summer", 7: "summer", 8: "summer",
    9: "transition", 10: "transition", 11: "transition",
}
SEASON_ORDER = ["winter", "transition", "summer"]


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


def _node_sort_key(node_id: str) -> tuple[int, str]:
    """Sort node ids naturally, e.g. j_2 before j_10."""
    parts = "".join(ch if ch.isdigit() else " " for ch in str(node_id)).split()
    if parts:
        try:
            return (int(parts[-1]), str(node_id))
        except ValueError:
            pass
    return (10**9, str(node_id))


def _season_of_timestamp(ts: pd.Timestamp | str) -> str | None:
    try:
        dt = pd.to_datetime(ts, errors="coerce")
    except Exception:
        return None
    if pd.isna(dt):
        return None
    return SEASON_BY_MONTH.get(int(dt.month))


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
        "num_vars": solver_info.get("num_vars"),
        "num_bin": solver_info.get("num_bin"),
        "num_constr": solver_info.get("num_constr"),
        "num_quad_constr": solver_info.get("num_quad_constr"),
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

    # Pump cost: use actual time-varying electricity price where available.
    # Falls back to the summary buy cost if the price series is missing.
    p_pump_series = series.get("P_pump_total_MW") or series.get("pump_P_MW") or []
    price_series = series.get("strompreis_EUR_MWh") or series.get("lambda_buy_EUR_MWh") or []
    if p_pump_series and price_series and len(price_series) == len(p_pump_series):
        cost_pump = float(sum(p * lam for p, lam in zip(p_pump_series, price_series)))
    elif p_pump_series:
        # Fallback: use mean buy price from summary if price series unavailable
        mean_price = (cost_energy_buy / energy_buy) if energy_buy > 0 else 35.0
        cost_pump = sum(p_pump_series) * mean_price
    else:
        cost_pump = 0.0

    energy_buy = _safe(grid.get("Energy_from_grid_MWh"))
    energy_sell = _safe(grid.get("Energy_to_grid_MWh"))

    # Gas consumption: from fuel summary (CHP + all boiler types)
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

    # CHP heat share: sum Q_th from all CHP assets in summary
    chp_total = 0.0
    for sec, vals in summary.items():
        if "chp" in sec.lower():
            chp_total += _safe(vals.get("Heat_output_MWh") or vals.get("Q_th_MWh"))
    share_CHP = (chp_total / heat_demand_MWh * 100) if heat_demand_MWh > 0 else 0.0

    # EBoiler / P2H heat share
    ek_total = 0.0
    for sec, vals in summary.items():
        if "eboiler" in sec.lower() or "p2h" in sec.lower() or "electrode" in sec.lower():
            ek_total += _safe(vals.get("Heat_output_MWh") or vals.get("Q_th_MWh"))
    share_EK = (ek_total / heat_demand_MWh * 100) if heat_demand_MWh > 0 else 0.0

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
    unified_ts = net_export / "unified_timeseries.csv"

    q_loss_total = [0.0] * T
    p_pump = [0.0] * T
    t_supply = [None] * T
    t_return = [None] * T
    t_supply_farend = [None] * T
    q_demand_from_model: list[float] | None = None

    # Read total heat demand directly from the model's unified timeseries export.
    # This is the consumer-side demand the optimizer solved for — more reliable than
    # back-computing from the generation/storage balance.
    if unified_ts.exists():
        try:
            udf = pd.read_csv(unified_ts, sep=";")
            if "heat_demand_MW" in udf.columns:
                raw_dem = udf["heat_demand_MW"].tolist()
                q_demand_from_model = (raw_dem[:T] if len(raw_dem) >= T
                                       else raw_dem + [0.0] * (T - len(raw_dem)))
        except Exception:
            pass

    if pipe_ts.exists():
        try:
            pdf = pd.read_csv(pipe_ts, sep=";", index_col=0)

            # Total heat losses across all pipes
            loss_cols_sup = [c for c in pdf.columns if c.endswith("_Q_loss_supply")]
            loss_cols_ret = [c for c in pdf.columns if c.endswith("_Q_loss_return")]
            raw_loss = (pdf[loss_cols_sup].sum(axis=1) + pdf[loss_cols_ret].sum(axis=1)).tolist()
            q_loss_total = (raw_loss[:T] if len(raw_loss) >= T
                            else raw_loss + [0.0] * (T - len(raw_loss)))

            # Source supply temperature: T_supply_in of the first pipe leaving j_1.
            # Column format: "{pipe_id}_T_supply_in" (e.g. "j1_to_j2_T_supply_in").
            # We prefer pipes whose name starts with "j1_to" or "j_1_to",
            # falling back to the first available T_supply_in column.
            sup_in_cols = [c for c in pdf.columns if c.endswith("_T_supply_in")]
            src_col = next(
                (c for c in sup_in_cols
                 if c.startswith("j1_to") or c.startswith("j_1_to")),
                sup_in_cols[0] if sup_in_cols else None,
            )
            if src_col is not None:
                raw_tsup = pdf[src_col].tolist()
                t_supply = (raw_tsup[:T] if len(raw_tsup) >= T
                            else raw_tsup + [None] * (T - len(raw_tsup)))

            # Source return temperature: use source-side return (T_return_out)
            # of the first pipe leaving j_1. This aligns with measured source
            # return temperature and avoids accidentally using consumer-side
            # return (T_return_in).
            ret_out_cols = [c for c in pdf.columns if c.endswith("_T_return_out")]
            src_ret_col = next(
                (c for c in ret_out_cols
                 if c.startswith("j1_to") or c.startswith("j_1_to")),
                ret_out_cols[0] if ret_out_cols else None,
            )
            if src_ret_col is not None:
                raw_tret = pdf[src_ret_col].tolist()
                t_return = (raw_tret[:T] if len(raw_tret) >= T
                            else raw_tret + [None] * (T - len(raw_tret)))

            # Far-end supply temperature: T_supply_out of the last trunk pipe (j13→j15).
            # This is the supply temperature arriving at the far end of the network (j15),
            # which is the primary validation KPI for heat-loss physics (BCM methodology).
            # Trunk path: j1→j2→j3→j9→j10→j11→j12→j13→j15; last segment is j13_to_j15.
            sup_out_cols = [c for c in pdf.columns if c.endswith("_T_supply_out")]
            farend_candidates = ["j13_to_j15", "j13-to-j15", "j_13_to_j_15"]
            farend_col = next(
                (c for c in sup_out_cols
                 if any(c.startswith(cand) for cand in farend_candidates)),
                None,
            )
            if farend_col is None and sup_out_cols:
                # Fallback: last pipe in sorted order (heuristic for trunk end)
                farend_col = sorted(sup_out_cols)[-1]
            if farend_col is not None:
                raw_fe = pdf[farend_col].tolist()
                t_supply_farend = (raw_fe[:T] if len(raw_fe) >= T
                                   else raw_fe + [None] * (T - len(raw_fe)))
        except Exception:
            pass

    rows = {
        "timestamp": timestamps,
        "Q_demand_total_MW": [0.0] * T,  # filled from energy balance below
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
        "ef_grid_kg_MWh": s("grid_co2_kg_MWh"),
        # --- Network temperatures (from pipes_timeseries.csv) ---
        "T_supply_C": t_supply,
        "T_return_C": t_return,
        "T_supply_farend_C": t_supply_farend,
        "Q_loss_total_MW": q_loss_total,
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

    # Q_demand: use model's own heat_demand_MW series (from unified_timeseries.csv) if
    # available — this is the consumer-side demand the optimizer solved for.
    # Fallback: energy balance (gen + net_storage - losses), but losses are post-processed
    # and can cause negative values at individual timesteps when storage cycles deeply.
    gen_keys = ["Q_chp_MW", "Q_gasboiler_MW", "Q_biomass_MW", "Q_hp_total_MW", "Q_ek_MW"]
    if q_demand_from_model is not None:
        rows["Q_demand_total_MW"] = q_demand_from_model
    else:
        rows["Q_demand_total_MW"] = [
            max(0.0,
                sum(rows[k][i] for k in gen_keys)
                + rows["Q_storage_discharge_MW"][i]
                - rows["Q_storage_charge_MW"][i]
                - rows["Q_loss_total_MW"][i]
                )
            for i in range(T)
        ]

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
# §3.6 node_state / node_summary exports
# ---------------------------------------------------------------------------

def _to_float_or_none(val: Any) -> float | None:
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _write_empty_node_artefacts(outdir: Path) -> None:
    summary_cols = [
        "node_id", "node_type", "T_supply_avg_c", "T_return_avg_c",
        "delta_t_avg_c", "Q_demand_total_mwh", "P_avg_bar",
    ]
    seasonal_cols = ["season"] + summary_cols
    state_cols = [
        "timestamp", "node_id", "T_supply_c", "T_return_c",
        "delta_t_c", "P_bar", "Q_demand_mw",
    ]
    pd.DataFrame(columns=summary_cols).to_csv(outdir / "nodes_summary.csv", index=False)
    pd.DataFrame(columns=seasonal_cols).to_csv(outdir / "nodes_seasonal.csv", index=False)
    pd.DataFrame(columns=state_cols).to_parquet(outdir / "nodes_state_hourly.parquet", index=False)
    pd.DataFrame().to_csv(outdir / "node_temperatures.csv", index_label="timestamp")


def _write_node_temperatures_csv(outdir: Path, nodes_state: pd.DataFrame) -> None:
    """Write wide node temperature CSV (timestamp x T_node_j_x columns)."""
    out_path = outdir / "node_temperatures.csv"
    if nodes_state.empty:
        pd.DataFrame().to_csv(out_path, index_label="timestamp")
        return

    needed = {"timestamp", "node_id", "T_supply_c"}
    if not needed.issubset(set(nodes_state.columns)):
        pd.DataFrame().to_csv(out_path, index_label="timestamp")
        return

    df = nodes_state[["timestamp", "node_id", "T_supply_c"]].copy()
    # Keep timestamp as-is when datetime parsing fails (e.g., integer timesteps).
    ts_dt = pd.to_datetime(df["timestamp"], errors="coerce")
    if ts_dt.notna().sum() >= max(1, int(0.8 * len(df))):
        df["timestamp"] = ts_dt

    wide = (
        df.pivot_table(index="timestamp", columns="node_id", values="T_supply_c", aggfunc="mean")
        .sort_index()
    )
    wide.columns = [f"T_node_{str(c)}" for c in wide.columns]
    wide.index.name = "timestamp"
    wide.to_csv(out_path)


def write_nodes_data(
    outdir: Path,
    run_id: str,
    workflow,
    dt_h: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Export node-level summary, seasonal and hourly state artefacts."""
    result = workflow.pf_result
    if result is None:
        _write_empty_node_artefacts(outdir)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    net_export = Path(result.solver.get("export_dir", ""))
    nodes_dir = net_export / "thermal_network" / "nodes"
    summary_json = nodes_dir / "nodes_summary.json"
    ts_csv = nodes_dir / "nodes_timeseries.csv"

    if not summary_json.exists() and not ts_csv.exists():
        print(f"  [WARN] node exports missing for {run_id} ({nodes_dir})")
        _write_empty_node_artefacts(outdir)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # ---- summary source (json) ----
    raw_summary: list[dict] = []
    if summary_json.exists():
        try:
            payload = json.loads(summary_json.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                raw_summary = payload
        except Exception as exc:
            print(f"  [WARN] Could not read nodes_summary.json: {exc}")

    summary_map: dict[str, dict] = {}
    for row in raw_summary:
        node_id = str(row.get("node_id") or row.get("id") or "").strip()
        if not node_id:
            continue
        summary_map[node_id] = {
            "node_id": node_id,
            "node_type": row.get("type") or "unknown",
            "T_supply_avg_c": _to_float_or_none(row.get("T_supply_avg_c")),
            "T_return_avg_c": _to_float_or_none(row.get("T_return_avg_c")),
            "Q_demand_total_mwh": _to_float_or_none(row.get("Q_demand_total_mwh")),
            "P_avg_bar": _to_float_or_none(row.get("P_avg_bar")),
        }

    # ---- hourly source (wide csv -> long parquet) ----
    long_cols = [
        "timestamp", "node_id", "T_supply_c", "T_return_c",
        "delta_t_c", "P_bar", "Q_demand_mw",
    ]
    wide = pd.DataFrame()
    if ts_csv.exists():
        try:
            wide = pd.read_csv(ts_csv, sep=";", index_col=0)
        except Exception as exc:
            print(f"  [WARN] Could not read nodes_timeseries.csv: {exc}")
            wide = pd.DataFrame()

    records: list[dict] = []
    if not wide.empty:
        node_ids: set[str] = set()
        suffixes = ("_T_supply", "_T_return", "_P", "_Q_demand")
        for col in wide.columns:
            for suffix in suffixes:
                if col.endswith(suffix):
                    node_ids.add(col[:-len(suffix)])
                    break
        for node_id in sorted(node_ids, key=_node_sort_key):
            c_sup = f"{node_id}_T_supply"
            c_ret = f"{node_id}_T_return"
            c_p = f"{node_id}_P"
            c_q = f"{node_id}_Q_demand"
            for ts, row in wide.iterrows():
                t_supply = _to_float_or_none(row.get(c_sup)) if c_sup in wide.columns else None
                t_return = _to_float_or_none(row.get(c_ret)) if c_ret in wide.columns else None
                p_bar = _to_float_or_none(row.get(c_p)) if c_p in wide.columns else None
                q_dem = _to_float_or_none(row.get(c_q)) if c_q in wide.columns else None
                delta_t = (t_supply - t_return) if (t_supply is not None and t_return is not None) else None
                records.append({
                    "timestamp": ts,
                    "node_id": node_id,
                    "T_supply_c": t_supply,
                    "T_return_c": t_return,
                    "delta_t_c": delta_t,
                    "P_bar": p_bar,
                    "Q_demand_mw": q_dem,
                })

    nodes_state = pd.DataFrame(records, columns=long_cols)
    nodes_state.to_parquet(outdir / "nodes_state_hourly.parquet", index=False)

    # ---- annual summary ----
    annual_from_state = pd.DataFrame()
    if not nodes_state.empty:
        annual_from_state = (
            nodes_state.groupby("node_id", as_index=False)
            .agg(
                T_supply_avg_c=("T_supply_c", "mean"),
                T_return_avg_c=("T_return_c", "mean"),
                delta_t_avg_c=("delta_t_c", "mean"),
                Q_demand_total_mwh=("Q_demand_mw", lambda x: float(x.fillna(0).sum()) * dt_h),
                P_avg_bar=("P_bar", "mean"),
            )
        )

    annual_rows: list[dict] = []
    all_nodes = set(summary_map.keys())
    if not annual_from_state.empty:
        all_nodes.update(annual_from_state["node_id"].astype(str).tolist())

    state_map = {}
    if not annual_from_state.empty:
        state_map = {
            str(row["node_id"]): row
            for _, row in annual_from_state.iterrows()
        }

    for node_id in sorted(all_nodes, key=_node_sort_key):
        srow = summary_map.get(node_id, {})
        arow = state_map.get(node_id, {})
        t_sup = srow.get("T_supply_avg_c")
        t_ret = srow.get("T_return_avg_c")
        q_mwh = srow.get("Q_demand_total_mwh")
        p_avg = srow.get("P_avg_bar")
        if t_sup is None and arow is not None:
            t_sup = _to_float_or_none(arow.get("T_supply_avg_c"))
        if t_ret is None and arow is not None:
            t_ret = _to_float_or_none(arow.get("T_return_avg_c"))
        if q_mwh is None and arow is not None:
            q_mwh = _to_float_or_none(arow.get("Q_demand_total_mwh"))
        if p_avg is None and arow is not None:
            p_avg = _to_float_or_none(arow.get("P_avg_bar"))
        delta = (t_sup - t_ret) if (t_sup is not None and t_ret is not None) else _to_float_or_none(arow.get("delta_t_avg_c"))
        annual_rows.append({
            "node_id": node_id,
            "node_type": srow.get("node_type", "unknown"),
            "T_supply_avg_c": t_sup,
            "T_return_avg_c": t_ret,
            "delta_t_avg_c": delta,
            "Q_demand_total_mwh": q_mwh,
            "P_avg_bar": p_avg,
        })

    nodes_summary = pd.DataFrame(annual_rows, columns=[
        "node_id", "node_type", "T_supply_avg_c", "T_return_avg_c",
        "delta_t_avg_c", "Q_demand_total_mwh", "P_avg_bar",
    ])
    nodes_summary.to_csv(outdir / "nodes_summary.csv", index=False)

    # ---- seasonal summary ----
    seasonal_cols = [
        "season", "node_id", "node_type", "T_supply_avg_c",
        "T_return_avg_c", "delta_t_avg_c", "Q_demand_total_mwh", "P_avg_bar",
    ]
    if nodes_state.empty:
        nodes_seasonal = pd.DataFrame(columns=seasonal_cols)
    else:
        seasonal_df = nodes_state.copy()
        seasonal_df["season"] = seasonal_df["timestamp"].map(_season_of_timestamp)
        seasonal_df = seasonal_df[seasonal_df["season"].notna()].copy()
        if seasonal_df.empty:
            nodes_seasonal = pd.DataFrame(columns=seasonal_cols)
        else:
            grouped = (
                seasonal_df.groupby(["node_id", "season"], as_index=False)
                .agg(
                    T_supply_avg_c=("T_supply_c", "mean"),
                    T_return_avg_c=("T_return_c", "mean"),
                    delta_t_avg_c=("delta_t_c", "mean"),
                    Q_demand_total_mwh=("Q_demand_mw", lambda x: float(x.fillna(0).sum()) * dt_h),
                    P_avg_bar=("P_bar", "mean"),
                )
            )
            grouped["node_type"] = grouped["node_id"].map(
                lambda nid: summary_map.get(str(nid), {}).get("node_type", "unknown")
            )
            grouped["season"] = pd.Categorical(grouped["season"], categories=SEASON_ORDER, ordered=True)
            grouped = grouped.sort_values(["node_id", "season"], key=lambda col: col.map(_node_sort_key) if col.name == "node_id" else col)
            nodes_seasonal = grouped[seasonal_cols].copy()

    nodes_seasonal.to_csv(outdir / "nodes_seasonal.csv", index=False)
    _write_node_temperatures_csv(outdir, nodes_state)
    return nodes_summary, nodes_seasonal, nodes_state


# ---------------------------------------------------------------------------
# §3.7 validation.json
# ---------------------------------------------------------------------------

def write_validation(outdir: Path, measured_data_path: str | None = None) -> None:
    """Write per-run validation.json.

    Links to the shared validation runner kpis.json when it exists (the
    validation_runner produces a single network-level result used by all runs).
    Includes a run-level energy-balance closure check derived from
    dispatch_hourly.csv if that artefact is already written.
    """
    shared_kpis_path = ROOT / "output" / "validation" / "kpis.json"

    payload: dict = {
        "status": "linked",
        "note": (
            "Per-run validation.json. Network-level Stage 1/2 KPIs are in "
            "output/validation/kpis.json (produced by tools/validation_runner.py). "
            "This file contains the run-level energy-balance closure check."
        ),
        "shared_kpis": str(shared_kpis_path.relative_to(ROOT))
        if shared_kpis_path.exists()
        else None,
    }

    # Pull the overall pass/fail summary from the shared kpis.json if available.
    if shared_kpis_path.exists():
        try:
            shared = json.loads(shared_kpis_path.read_text(encoding="utf-8"))
            effective = shared.get("stage1_kpis_effective", {})
            thresholds = shared.get("thresholds", {})
            gate_results = {}
            for kpi, thresh in thresholds.items():
                val = effective.get(kpi)
                if val is not None:
                    gate_results[kpi] = {
                        "value": val,
                        "threshold": thresh,
                        "pass": float(val) <= float(thresh),
                    }
            payload["stage1_gate"] = gate_results
            payload["status"] = "ok" if all(
                r["pass"] for r in gate_results.values()
            ) else "warn_threshold"
        except Exception as exc:
            payload["shared_kpis_read_error"] = str(exc)

    # Run-level energy-balance closure from dispatch_hourly.csv.
    dispatch_path = outdir / "dispatch_hourly.csv"
    if dispatch_path.exists():
        try:
            disp = pd.read_csv(dispatch_path)
            gen_cols = [
                "Q_chp_MW", "Q_gasboiler_MW", "Q_biomass_MW",
                "Q_hp_total_MW", "Q_ek_MW",
            ]
            discharge_cols = ["Q_storage_discharge_MW"]
            charge_cols = ["Q_storage_charge_MW"]
            loss_col = "Q_loss_total_MW"
            demand_col = "Q_demand_total_MW"

            gen_total = sum(
                disp[c].fillna(0).sum() for c in gen_cols if c in disp.columns
            )
            discharge = sum(
                disp[c].fillna(0).sum() for c in discharge_cols if c in disp.columns
            )
            charge = sum(
                disp[c].fillna(0).sum() for c in charge_cols if c in disp.columns
            )
            losses = disp[loss_col].fillna(0).sum() if loss_col in disp.columns else 0.0
            demand = disp[demand_col].fillna(0).sum() if demand_col in disp.columns else 0.0

            supply = gen_total + discharge - charge
            closure_err_pct = (
                abs(supply - losses - demand) / demand * 100 if demand > 0 else None
            )
            payload["energy_balance"] = {
                "generation_MWh": round(gen_total, 1),
                "net_storage_MWh": round(discharge - charge, 1),
                "losses_MWh": round(losses, 1),
                "demand_MWh": round(demand, 1),
                "closure_error_pct": round(closure_err_pct, 3) if closure_err_pct is not None else None,
                "closure_pass": bool(closure_err_pct is not None and closure_err_pct <= 2.0),
            }
        except Exception as exc:
            payload["energy_balance_error"] = str(exc)

    (outdir / "validation.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )


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
    try:
        write_nodes_data(outdir, run_id, workflow)
    except Exception as e:
        print(f"  [WARN] node artefacts skipped: {e}")
        _write_empty_node_artefacts(outdir)
    write_validation(outdir, measured_data_path)

    print(f"  [EXTRACT] {run_id} → {outdir}")
    return outdir
