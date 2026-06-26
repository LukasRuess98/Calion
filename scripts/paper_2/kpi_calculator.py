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
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

KPI_COLS = [
    "scenario_id", "network", "heat_curve_stage", "tes_node", "baseline",
    # Economic
    "TAC_eur_per_a", "CAPEX_annual_eur_per_a", "OPEX_annual_eur_per_a",
    "LCOH_eur_per_MWh", "payback_years", "cost_reduction_pct",
    # Environmental
    "co2_t_per_a", "co2_reduction_pct", "electrification_pct", "renewable_heat_pct",
    # Technical
    "Q_WP_opt_MW", "Q_EK_opt_MW", "V_TES_m3", "h_TES_m", "E_TES_MWh",
    "TES_cycles_per_a", "TES_utilization_pct", "WP_hours_per_a", "COP_annual_mean",
    "pump_energy_MWh_el_per_a", "waste_heat_utilization_pct",
    "DSM_activation_MWh_per_a", "k_opt", "T_VL_min_opt_c",
]


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


def compute_scenario_kpis(scen_dir: Path, baseline_kpis: dict | None = None) -> dict:
    """Compute all 24 KPIs for one scenario directory.

    Args:
        scen_dir: Path to output/paper2_runs/{scenario_id}/
        baseline_kpis: BC KPIs for same network (for cost_reduction_pct, co2_reduction_pct).

    Returns:
        Dict with all KPI values (or None for missing).
    """
    scen_meta = _read_json(scen_dir / "scenario_meta.json")
    meta = _read_json(scen_dir / "meta.json")
    economics = _read_csv_first_row(scen_dir / "economics.csv")
    geometry = _read_csv_first_row(scen_dir / "geometry.csv")
    dispatch_rows = _read_csv_all_rows(scen_dir / "dispatch_hourly.csv")
    dsm_rows = _read_csv_all_rows(scen_dir / "dsm_hourly.csv")

    kpis = {col: None for col in KPI_COLS}
    kpis["scenario_id"] = scen_meta.get("id", scen_dir.name)
    kpis["network"] = scen_meta.get("network")
    kpis["heat_curve_stage"] = scen_meta.get("heat_curve_stage")
    kpis["tes_node"] = scen_meta.get("tes_node")
    kpis["baseline"] = scen_meta.get("baseline", False)

    # ── Economic KPIs ──────────────────────────────────────────────────────
    # economics.csv columns: cost_total_eur, co2_total_t, lcoh_eur_per_MWh_th, ...
    TAC = economics.get("cost_total_eur")
    if TAC is not None:
        kpis["TAC_eur_per_a"] = round(TAC, 0)

    # CAPEX and OPEX are not yet split in economics.csv — leave as None
    capex = economics.get("capex_annual_eur")  # future: extractor will add this
    kpis["CAPEX_annual_eur_per_a"] = round(capex, 0) if capex is not None else None

    opex = economics.get("opex_eur")  # future: TAC - CAPEX
    kpis["OPEX_annual_eur_per_a"] = round(opex, 0) if opex is not None else None

    # LCOH: use pre-computed value from extractor (already correct) or recompute from dispatch
    lcoh_from_eco = economics.get("lcoh_eur_per_MWh_th")
    Q_total = sum(row.get("Q_demand_total_MW", 0) or 0 for row in dispatch_rows)
    if lcoh_from_eco is not None and lcoh_from_eco > 0:
        kpis["LCOH_eur_per_MWh"] = round(float(lcoh_from_eco), 2)
    elif TAC is not None and Q_total > 0:
        kpis["LCOH_eur_per_MWh"] = round(TAC / Q_total, 2)

    # Cost reduction vs baseline
    if baseline_kpis and TAC is not None:
        tac_bc = baseline_kpis.get("TAC_eur_per_a")
        if tac_bc and tac_bc > 0:
            kpis["cost_reduction_pct"] = round((tac_bc - TAC) / tac_bc * 100, 2)
            # Payback: only computable when CAPEX and OPEX splits are available
            if capex and capex > 0 and opex is not None:
                opex_bc = baseline_kpis.get("OPEX_annual_eur_per_a")
                if opex_bc and opex_bc > opex:
                    kpis["payback_years"] = round(capex / (opex_bc - opex), 1)

    # ── Environmental KPIs ─────────────────────────────────────────────────
    # co2_total_t is already in tonnes in economics.csv
    co2_t = economics.get("co2_total_t")
    if co2_t is not None:
        kpis["co2_t_per_a"] = round(float(co2_t), 1)
    if baseline_kpis and co2_t is not None:
        co2_bc_t = baseline_kpis.get("co2_t_per_a") or 0
        if co2_bc_t > 0:
            kpis["co2_reduction_pct"] = round((co2_bc_t - float(co2_t)) / co2_bc_t * 100, 2)

    # Use share_HP_pct from economics (reliable across single- and multi-node topologies).
    # Dispatch Q_hp_total_MW can include WRG passthrough (not true HP compression) and
    # should not be used to compute these shares.
    share_hp_eco = economics.get("share_HP_pct")
    if share_hp_eco is not None:
        kpis["electrification_pct"] = round(float(share_hp_eco), 2)
        kpis["renewable_heat_pct"] = round(float(share_hp_eco), 2)

    # ── Technical KPIs ─────────────────────────────────────────────────────
    # Capacity values not directly in economics.csv; use share_HP_pct × total demand as proxy
    share_hp = economics.get("share_HP_pct")
    share_ek = economics.get("share_EK_pct")
    if share_hp is not None and Q_total > 0:
        # Rough capacity estimate: average power = share × total_demand / 8760
        kpis["Q_WP_opt_MW"] = round(float(share_hp) / 100.0 * Q_total / 8760.0, 2)
    if share_ek is not None and Q_total > 0:
        kpis["Q_EK_opt_MW"] = round(float(share_ek) / 100.0 * Q_total / 8760.0, 2)

    # TES geometry
    if geometry:
        kpis["V_TES_m3"] = geometry.get("V_TES_m3")
        kpis["h_TES_m"] = geometry.get("h_TES_m")
        kpis["E_TES_MWh"] = geometry.get("E_TES_max_MWh")

    # TES cycles: sum(charge) / E_TES_max
    if dispatch_rows and kpis.get("E_TES_MWh"):
        qc_col = _find_col(dispatch_rows[0], "Q_storage_charge_MW", "tes_charge", "q_charge")
        if qc_col:
            total_charge = sum(row.get(qc_col, 0) or 0 for row in dispatch_rows)
            E_max = kpis["E_TES_MWh"]
            if E_max and E_max > 0:
                kpis["TES_cycles_per_a"] = round(total_charge / E_max, 1)
        # TES utilization: mean SOC / E_max
        soc_col = _find_col(dispatch_rows[0], "SOC_MWh", "tes_soc", "E_tes")
        if soc_col and kpis.get("E_TES_MWh", 0) > 0:
            soc_vals = [row.get(soc_col) for row in dispatch_rows if row.get(soc_col) is not None]
            if soc_vals:
                kpis["TES_utilization_pct"] = round(
                    float(np.mean(soc_vals)) / kpis["E_TES_MWh"] * 100, 2
                )

    # WP operating hours: use P_hp_el_MW > 0.01 threshold to detect true HP compression
    # (avoids counting WRG-passthrough hours where HP runs with zero electricity input).
    if dispatch_rows:
        pel_col = _find_col(dispatch_rows[0], "P_hp_el_MW", "P_el", "pel_wp")
        hp_col = _find_col(dispatch_rows[0], "Q_hp_total_MW", "hp_", "q_wp")
        if pel_col:
            P_el_ts = [row.get(pel_col, 0) or 0 for row in dispatch_rows]
            P_el_sum = sum(P_el_ts)
            kpis["WP_hours_per_a"] = sum(1 for p in P_el_ts if p > 0.01)
            if P_el_sum > 0 and hp_col:
                Q_WP_ts = [row.get(hp_col, 0) or 0 for row in dispatch_rows]
                Q_WP_sum_local = sum(Q_WP_ts)
                kpis["COP_annual_mean"] = round(Q_WP_sum_local / P_el_sum, 2)
        elif hp_col:
            Q_WP_ts = [row.get(hp_col, 0) or 0 for row in dispatch_rows]
            kpis["WP_hours_per_a"] = sum(1 for q in Q_WP_ts if q > 0.01)

    # Pump energy
    pump_col = _find_col(dispatch_rows[0] if dispatch_rows else {}, "pump", "P_pump")
    if pump_col and dispatch_rows:
        kpis["pump_energy_MWh_el_per_a"] = round(
            sum(row.get(pump_col, 0) or 0 for row in dispatch_rows), 1
        )

    # Waste heat utilization: Σ Q_WP_AW / Σ Q_AW_max
    wh_used = economics.get("waste_heat_used_MWh")
    wh_avail = economics.get("waste_heat_available_MWh")
    if wh_used is not None and wh_avail and wh_avail > 0:
        kpis["waste_heat_utilization_pct"] = round(wh_used / wh_avail * 100, 2)

    # DSM activation
    if dsm_rows:
        total_abs = sum(
            (row.get("delta_abs") or abs(row.get("delta", 0) or 0))
            for row in dsm_rows
        )
        kpis["DSM_activation_MWh_per_a"] = round(total_abs, 1)

    # Heat curve params (from scenario_meta.json → HK stage)
    hk_stage = scen_meta.get("heat_curve_stage", "HK0")
    # k and T_VL_min would be in the scenarios.yaml — stored at solve time
    # For now we leave these as None unless injected into scenario_meta
    kpis["k_opt"] = scen_meta.get("k")
    kpis["T_VL_min_opt_c"] = scen_meta.get("T_VL_min_c")

    return kpis


def _find_col(row: dict, *patterns: str) -> str | None:
    """Find first column name matching any of the given substrings."""
    keys = list(row.keys())
    for pat in patterns:
        pat_lower = pat.lower()
        for k in keys:
            if pat_lower in k.lower():
                return k
    return None


def compute_all_kpis(out_base: Path) -> Path:
    """Compute KPIs for all scenarios and write scenarios_kpis.csv.

    Args:
        out_base: Path to output/paper2_runs/

    Returns:
        Path to the written scenarios_kpis.csv.
    """
    # Collect all scenario dirs
    scen_dirs = sorted(
        d for d in out_base.iterdir()
        if d.is_dir() and (d / "meta.json").exists()
    )

    if not scen_dirs:
        logger.warning("No scenario outputs found in %s", out_base)
        return out_base / "scenarios_kpis.csv"

    # First pass: collect baseline KPIs for cost/co2 comparison
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

    # Second pass: compute all KPIs with baseline reference
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

    # Write CSV
    out_path = out_base / "scenarios_kpis.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=KPI_COLS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_kpis)

    logger.info("Wrote %d scenario KPIs to %s", len(all_kpis), out_path)
    return out_path
