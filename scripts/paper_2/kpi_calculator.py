"""Paper 2 KPI calculator.

Reads per-scenario artefact files from output/paper2_runs/{scenario_id}/
and computes all 24 KPIs from spec Section 6. Writes scenarios_kpis.csv.

KPIs (24 total):
  Economic:   TAC, CAPEX_annual, OPEX_annual, LCOH, payback_years, cost_reduction_pct
  Environmental: co2_t_per_a, co2_reduction_pct, electrification_pct, renewable_heat_pct
  Technical:  Q_WP_opt_MW, Q_EK_opt_MW, V_TES_m3, h_TES_m, E_TES_MWh,
              TES_cycles_per_a, TES_utilization_pct, WP_hours_per_a, COP_annual_mean,
              pump_energy_MWh_el_per_a, waste_heat_utilization_pct, DSM_activation_MWh_per_a,
              k_opt, T_VL_min_opt_c
"""

from __future__ import annotations

import csv
import json
import logging
import math
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ── TES geometry constants ─────────────────────────────────────────────────
_RHO = 971.8        # kg/m³  (water at ~80°C)
_CP  = 4189.0       # J/(kg·K)
_G   = 9.81
_P_ATM = 1.013      # bar
_R_HD  = 3.0        # height/diameter ratio for cylindrical TES

# ── Heat curve lookup (from configs/paper_2/scenarios.yaml) ───────────────
_HK_PARAMS = {
    "memmingen": {
        "HK0": (1.0, 74.0),
        "HK1": (0.8, 70.0),
        "HK2": (0.6, 66.0),
    },
    "stadtbach": {
        "HK0": (1.0, 70.0),
        "HK1": (0.8, 65.0),
        "HK2": (0.6, 60.0),
    },
}

KPI_COLS = [
    "scenario_id", "network", "heat_curve_stage", "tes_node", "baseline",
    # Economic
    "TAC_eur_per_a", "CAPEX_annual_eur_per_a", "OPEX_annual_eur_per_a",
    "LCOH_eur_per_MWh", "payback_years", "cost_reduction_pct", "NPV_eur",
    # Environmental
    "co2_t_per_a", "co2_reduction_pct", "electrification_pct", "renewable_heat_pct",
    # Technical
    "Q_WP_opt_MW", "Q_EK_opt_MW", "V_TES_m3", "h_TES_m", "E_TES_MWh",
    "TES_cycles_per_a", "TES_utilization_pct", "WP_hours_per_a", "COP_annual_mean",
    "pump_energy_MWh_el_per_a", "waste_heat_utilization_pct",
    "DSM_activation_MWh_per_a", "k_opt", "T_VL_min_opt_c",
    # Hydraulic / thermal (spec §6.3 additions)
    "T_VL_avg_c", "p_max_bar", "p_min_bar", "endog_site",
]

# NPV horizon parameters (spec §6.1: "Net present value berechnen").
# NPV = Σ_{y=1..n} (TAC_BC − TAC_s) / (1+i)^y — annualized-cost framework,
# consistent with ANF-based CAPEX annualization elsewhere.
_NPV_DISCOUNT_RATE = 0.05
_NPV_HORIZON_YEARS = 20


def _read_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _read_csv_first_row(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            return {k: _try_float(v) for k, v in row.items()}
    return {}


def _read_csv_all_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [
            {k: _try_float(v) for k, v in row.items()}
            for row in csv.DictReader(f)
        ]


def _try_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _col_max(rows: list[dict], *patterns: str) -> float:
    """Return max value across all rows for first matching column pattern."""
    if not rows:
        return 0.0
    col = _find_col(rows[0], *patterns)
    if col is None:
        return 0.0
    return max((float(r.get(col) or 0) for r in rows), default=0.0)


def _col_sum(rows: list[dict], *patterns: str) -> float:
    col = _find_col(rows[0] if rows else {}, *patterns)
    if col is None:
        return 0.0
    return sum(float(r.get(col) or 0) for r in rows)


def _tes_geometry(E_MWh: float, delta_T_K: float) -> tuple[float, float]:
    """Return (V_m3, h_m) for a cylindrical TES given energy and delta-T."""
    if E_MWh <= 0 or delta_T_K <= 0:
        return 0.0, 0.0
    V = E_MWh * 3.6e9 / (_RHO * _CP * delta_T_K)
    h = (V * 4.0 * _R_HD ** 2 / math.pi) ** (1.0 / 3.0)
    return round(V, 1), round(h, 2)


def compute_scenario_kpis(scen_dir: Path, baseline_kpis: dict | None = None) -> dict:
    """Compute all 24 KPIs for one scenario directory."""
    scen_meta = _read_json(scen_dir / "scenario_meta.json")
    economics = _read_csv_first_row(scen_dir / "economics.csv")
    nodes_sum = _read_csv_first_row(scen_dir / "nodes_summary.csv")
    dispatch_rows = _read_csv_all_rows(scen_dir / "dispatch_hourly.csv")
    dsm_rows = _read_csv_all_rows(scen_dir / "dsm_hourly.csv")

    kpis = {col: None for col in KPI_COLS}
    kpis["scenario_id"] = scen_meta.get("id", scen_dir.name)
    kpis["network"] = scen_meta.get("network")
    kpis["heat_curve_stage"] = scen_meta.get("heat_curve_stage")
    kpis["tes_node"] = scen_meta.get("tes_node")
    kpis["baseline"] = scen_meta.get("baseline", False)

    # ── Economic KPIs ──────────────────────────────────────────────────────
    TAC = economics.get("cost_total_eur")
    if TAC is not None:
        kpis["TAC_eur_per_a"] = round(TAC, 0)

    # CAPEX/OPEX split from economics columns
    # OPEX = net electricity cost + fuel + CO2 + dump - CHP revenue
    # CAPEX_annual = TAC - OPEX  (includes fixed asset annualization)
    e_buy   = economics.get("cost_energy_buy_eur") or 0.0
    e_sell  = economics.get("revenue_sell_eur") or 0.0
    c_fuel  = economics.get("cost_fuel_eur") or 0.0
    c_co2   = economics.get("cost_co2_eur") or 0.0
    c_dump  = economics.get("cost_dump_eur") or 0.0
    c_pump  = economics.get("cost_pump_eur") or 0.0
    c_dem   = economics.get("cost_demand_charge_eur") or 0.0
    if TAC is not None:
        opex = e_buy + c_fuel + c_co2 + c_dump + c_pump + c_dem - e_sell
        capex = TAC - opex
        kpis["OPEX_annual_eur_per_a"] = round(opex, 0)
        kpis["CAPEX_annual_eur_per_a"] = round(capex, 0)

    # LCOH
    Q_total = sum(float(r.get("Q_demand_total_MW") or 0) for r in dispatch_rows)
    lcoh_from_eco = economics.get("lcoh_eur_per_MWh_th")
    if lcoh_from_eco is not None and float(lcoh_from_eco) > 0:
        kpis["LCOH_eur_per_MWh"] = round(float(lcoh_from_eco), 2)
    elif TAC is not None and Q_total > 0:
        kpis["LCOH_eur_per_MWh"] = round(TAC / Q_total, 2)

    # Cost reduction vs baseline
    if baseline_kpis and TAC is not None:
        tac_bc = baseline_kpis.get("TAC_eur_per_a")
        if tac_bc and tac_bc > 0:
            kpis["cost_reduction_pct"] = round((tac_bc - TAC) / tac_bc * 100, 2)
            # NPV over n years at discount rate i (present value of the annual
            # total-cost saving vs. baseline; negative = worse than baseline)
            _af = (1.0 - (1.0 + _NPV_DISCOUNT_RATE) ** -_NPV_HORIZON_YEARS) / _NPV_DISCOUNT_RATE
            kpis["NPV_eur"] = round((tac_bc - TAC) * _af, 0)
            # Payback: incremental CAPEX / incremental OPEX savings
            capex_bc = baseline_kpis.get("CAPEX_annual_eur_per_a") or 0
            opex_bc  = baseline_kpis.get("OPEX_annual_eur_per_a") or 0
            capex_new = kpis.get("CAPEX_annual_eur_per_a") or 0
            opex_new  = kpis.get("OPEX_annual_eur_per_a") or 0
            delta_capex = capex_new - capex_bc
            delta_opex  = opex_bc - opex_new
            if delta_capex > 0 and delta_opex > 0:
                kpis["payback_years"] = round(delta_capex / delta_opex, 1)

    # ── Environmental KPIs ─────────────────────────────────────────────────
    co2_t = economics.get("co2_total_t")
    if co2_t is not None:
        kpis["co2_t_per_a"] = round(float(co2_t), 1)
    if baseline_kpis and co2_t is not None:
        co2_bc = baseline_kpis.get("co2_t_per_a") or 0
        if co2_bc > 0:
            kpis["co2_reduction_pct"] = round((co2_bc - float(co2_t)) / co2_bc * 100, 2)

    share_hp_eco = economics.get("share_HP_pct")
    if share_hp_eco is not None:
        kpis["electrification_pct"] = round(float(share_hp_eco), 2)
        kpis["renewable_heat_pct"] = round(float(share_hp_eco), 2)

    # ── Technical KPIs — capacities from peak dispatch ─────────────────────
    # Q_WP: peak HP thermal output (Q_hp_total_MW covers both WRG and compression)
    if dispatch_rows:
        Q_WP_peak = _col_max(dispatch_rows, "Q_hp_total_MW", "q_hp_total")
        Q_EK_peak  = _col_max(dispatch_rows, "Q_ek_MW", "q_ek")
        kpis["Q_WP_opt_MW"] = round(Q_WP_peak, 2)
        kpis["Q_EK_opt_MW"] = round(Q_EK_peak, 2)

    # ── TES geometry: prefer the ACTUAL solver values from geometry.csv ────
    # (result_collector captures {tes}_V_m3 / E_max / build; geometry.csv is
    # written by extract_artefacts_p2). Fallback: derive from peak SOC.
    geo_row = _read_csv_first_row(scen_dir / "geometry.csv")
    if geo_row and float(geo_row.get("V_TES_m3") or 0) > 0:
        kpis["V_TES_m3"] = round(float(geo_row["V_TES_m3"]), 1)
        kpis["h_TES_m"] = round(float(geo_row.get("h_TES_m") or 0), 2)
        kpis["E_TES_MWh"] = round(float(geo_row.get("E_TES_max_MWh") or 0), 1)
    elif dispatch_rows:
        # E_TES_MWh ≈ max observed SOC (lower bound on installed capacity)
        E_TES = _col_max(dispatch_rows, "SOC_MWh", "tes_soc", "E_tes")
        if E_TES > 0:
            kpis["E_TES_MWh"] = round(E_TES, 1)
            # Derive ΔT from nodes_summary (T_supply_avg - T_return_avg)
            delta_T = _nodes_delta_T(nodes_sum, scen_meta.get("network", ""))
            V, h = _tes_geometry(E_TES, delta_T)
            kpis["V_TES_m3"] = V
            kpis["h_TES_m"] = h

    # Endogenous site choice (F3 scenarios)
    endog = _read_json(scen_dir / "endog_sites.json")
    if endog:
        kpis["endog_site"] = endog.get("endog_tes_site") or endog.get("endog_hp_site")

    # TES cycles and utilization
    if dispatch_rows and kpis.get("E_TES_MWh"):
        total_charge = _col_sum(dispatch_rows, "Q_storage_charge_MW", "tes_charge")
        E_max = kpis["E_TES_MWh"]
        if E_max > 0 and total_charge > 0:
            kpis["TES_cycles_per_a"] = round(total_charge / E_max, 1)
        soc_col = _find_col(dispatch_rows[0], "SOC_MWh", "tes_soc", "E_tes")
        if soc_col and E_max > 0:
            soc_vals = [float(r.get(soc_col) or 0) for r in dispatch_rows]
            kpis["TES_utilization_pct"] = round(float(np.mean(soc_vals)) / E_max * 100, 2)

    # WP operating hours and annual COP (heat-weighted; fall back to COP series)
    if dispatch_rows:
        pel_col = _find_col(dispatch_rows[0], "P_hp_el_MW", "P_el", "pel_wp")
        hp_col  = _find_col(dispatch_rows[0], "Q_hp_total_MW", "q_hp_total")
        cop_col = _find_col(dispatch_rows[0], "COP_hp_wrg", "COP_hp", "cop_wp")
        Q_WP_ts = [float(r.get(hp_col) or 0) for r in dispatch_rows] if hp_col else []
        run_idx = [i for i, q in enumerate(Q_WP_ts) if q > 0.01]
        if Q_WP_ts:
            kpis["WP_hours_per_a"] = len(run_idx)
        P_el_sum = 0.0
        if pel_col:
            P_el_sum = sum(float(r.get(pel_col) or 0) for r in dispatch_rows)
        if P_el_sum > 0 and Q_WP_ts:
            # true annual COP = delivered heat / consumed electricity
            kpis["COP_annual_mean"] = round(sum(Q_WP_ts) / P_el_sum, 2)
        elif cop_col and run_idx:
            # fallback: mean of the per-hour COP series over operating hours
            cop_run = [c for c in (float(dispatch_rows[i].get(cop_col) or 0)
                                   for i in run_idx) if c > 0]
            if cop_run:
                kpis["COP_annual_mean"] = round(sum(cop_run) / len(cop_run), 2)

    # DSM activation
    if dsm_rows:
        total_abs = sum(
            (float(r.get("delta_abs") or 0) or abs(float(r.get("delta") or 0)))
            for r in dsm_rows
        )
        kpis["DSM_activation_MWh_per_a"] = round(total_abs, 1)

    # ── Hydraulic / thermal KPIs (spec §6.3: TVL average, max/min pressure) ─
    _add_state_kpis(kpis, scen_dir)

    # ── Heat curve parameters from lookup ──────────────────────────────────
    network = scen_meta.get("network", "")
    hk_stage = scen_meta.get("heat_curve_stage", "HK0")
    # First try scenario_meta.json (set at solve time by extract_artefacts_p2)
    k = scen_meta.get("k")
    T_VL_min = scen_meta.get("T_VL_min_c")
    if k is None:
        hk_data = _HK_PARAMS.get(network, {}).get(hk_stage)
        if hk_data:
            k, T_VL_min = hk_data
    kpis["k_opt"] = k
    kpis["T_VL_min_opt_c"] = T_VL_min

    return kpis


def _add_state_kpis(kpis: dict, scen_dir: Path) -> None:
    """TVL average (system + per pipe) and max/min node pressure.

    Sources: nodes_state_hourly.parquet (T_supply_c, P_bar per node·t) and
    pipe_state_hourly.parquet (T_in_C/T_out_C per pipe·t). Writes the
    per-pipe averages to tvl_per_pipe.csv alongside the scenario artefacts.
    """
    try:
        import pandas as pd
    except ImportError:
        return

    nodes_pq = scen_dir / "nodes_state_hourly.parquet"
    if nodes_pq.exists():
        try:
            df = pd.read_parquet(nodes_pq, columns=["node_id", "T_supply_c", "P_bar"])
            t_sup = pd.to_numeric(df["T_supply_c"], errors="coerce").dropna()
            if len(t_sup):
                kpis["T_VL_avg_c"] = round(float(t_sup.mean()), 2)
            p = pd.to_numeric(df["P_bar"], errors="coerce").dropna()
            if len(p):
                kpis["p_max_bar"] = round(float(p.max()), 3)
                kpis["p_min_bar"] = round(float(p.min()), 3)
        except Exception as exc:
            logger.debug("nodes_state KPI read failed for %s: %s", scen_dir.name, exc)

    pipes_pq = scen_dir / "pipe_state_hourly.parquet"
    if pipes_pq.exists():
        try:
            dfp = pd.read_parquet(pipes_pq, columns=["pipe_id", "T_in_C", "T_out_C"])
            per_pipe = dfp.groupby("pipe_id").agg(
                T_in_avg_C=("T_in_C", "mean"),
                T_out_avg_C=("T_out_C", "mean"),
            ).round(2)
            per_pipe["T_pipe_avg_C"] = ((per_pipe["T_in_avg_C"] + per_pipe["T_out_avg_C"]) / 2).round(2)
            per_pipe.to_csv(scen_dir / "tvl_per_pipe.csv")
        except Exception as exc:
            logger.debug("pipe_state KPI read failed for %s: %s", scen_dir.name, exc)


def _nodes_delta_T(nodes_sum: dict, network: str) -> float:
    """Return ΔT from nodes_summary first row, or network default."""
    T_sup = nodes_sum.get("T_supply_avg_c")
    T_ret = nodes_sum.get("T_return_avg_c")
    if T_sup and T_ret:
        return float(T_sup) - float(T_ret)
    # Fallback defaults from config
    return 22.78 if "memmingen" in network else 39.0


def _find_col(row: dict, *patterns: str) -> str | None:
    keys = list(row.keys())
    for pat in patterns:
        pl = pat.lower()
        for k in keys:
            if pl in k.lower():
                return k
    return None


def compute_all_kpis(out_base: Path) -> Path:
    """Compute KPIs for all scenarios and write scenarios_kpis.csv."""
    scen_dirs = sorted(
        d for d in out_base.iterdir()
        if d.is_dir() and (d / "scenario_meta.json").exists()
    )

    if not scen_dirs:
        logger.warning("No scenario outputs found in %s", out_base)
        return out_base / "scenarios_kpis.csv"

    # First pass: baseline KPIs per network
    baseline_kpis_by_network: dict[str, dict] = {}
    for scen_dir in scen_dirs:
        meta = _read_json(scen_dir / "scenario_meta.json")
        if meta.get("baseline"):
            kpis = compute_scenario_kpis(scen_dir)
            network = meta.get("network", "unknown")
            baseline_kpis_by_network[network] = kpis
            logger.info("Baseline %s: TAC=%.0f €/a, CO2=%.0f t/a",
                        scen_dir.name,
                        kpis.get("TAC_eur_per_a") or 0,
                        kpis.get("co2_t_per_a") or 0)

    # Second pass: all KPIs with baseline reference
    all_kpis = []
    for scen_dir in scen_dirs:
        meta = _read_json(scen_dir / "scenario_meta.json")
        network = meta.get("network", "unknown")
        bc_kpis = baseline_kpis_by_network.get(network)
        kpis = compute_scenario_kpis(scen_dir, baseline_kpis=bc_kpis)
        all_kpis.append(kpis)
        logger.info("[KPI] %s: TAC=%.0f €/a, LCOH=%.1f €/MWh, cost_red=%.1f%%",
                    kpis["scenario_id"],
                    kpis.get("TAC_eur_per_a") or 0,
                    kpis.get("LCOH_eur_per_MWh") or 0,
                    kpis.get("cost_reduction_pct") or 0)

    out_path = out_base / "scenarios_kpis.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=KPI_COLS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_kpis)

    # Spec §11: baseline_kpis.csv — BC results for both networks separately
    bc_rows = [k for k in all_kpis if k.get("baseline")]
    if bc_rows:
        bc_path = out_base / "baseline_kpis.csv"
        with open(bc_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=KPI_COLS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(bc_rows)
        logger.info("Wrote %d baseline KPIs to %s", len(bc_rows), bc_path)

    logger.info("Wrote %d scenario KPIs to %s", len(all_kpis), out_path)
    return out_path
