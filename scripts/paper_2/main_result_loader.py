"""Part A step 1 — load the MILP optimum for a chosen scenario (spec A.4).

Reads Q_WP*, V_TES*, TES node, heat-curve stage and the technical capacity
bounds for a completed main-campaign scenario, so capacity_sweep.py can build a
grid *around* the optimum (never below cap_min / above cap_max).

Usage:
    from scripts.paper_2.main_result_loader import load_main_result
    r = load_main_result("SB-S1-HK0")
"""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
OUT_BASE = _ROOT / "output" / "paper2_runs"
SCENARIOS_YAML = _ROOT / "configs" / "paper_2" / "scenarios.yaml"

HP_ASSET = {"memmingen": "hp_main", "stadtbach": "hp_sb"}
TES_ASSET = {"memmingen": "tes_main", "stadtbach": "tes_sb"}


def _kpi_row(scenario_id: str) -> dict:
    p = OUT_BASE / "scenarios_kpis.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} not found — run the campaign + KPI phase first")
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("scenario_id") == scenario_id:
                return r
    raise KeyError(f"scenario {scenario_id} not in scenarios_kpis.csv")


def _scenario_def(scenario_id: str) -> tuple[dict, dict]:
    with open(SCENARIOS_YAML, encoding="utf-8") as f:
        scen_cfg = yaml.safe_load(f)
    scen = next((s for s in scen_cfg["scenarios"] if s["id"] == scenario_id), None)
    if scen is None:
        raise KeyError(f"scenario {scenario_id} not in scenarios.yaml")
    return scen, scen_cfg


def _f(row: dict, key: str) -> float | None:
    try:
        v = float(row.get(key))
        return v
    except (TypeError, ValueError):
        return None


def load_main_result(scenario_id: str) -> dict:
    """Return the optimum + bounds needed to seed a capacity sweep."""
    row = _kpi_row(scenario_id)
    scen, scen_cfg = _scenario_def(scenario_id)
    network = row.get("network") or scen.get("network")

    cfg_path = _ROOT / scen["config"]
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assets = cfg.get("assets", {}) or {}
    hp = assets.get(HP_ASSET.get(network, ""), {}) or {}
    tes = assets.get(TES_ASSET.get(network, ""), {}) or {}
    hp_inv = hp.get("investment", {}) or {}

    return {
        "scenario_id": scenario_id,
        "network": network,
        "scenario": scen,               # full scenarios.yaml dict (overrides, nodes, HK)
        "heat_curve_stage": row.get("heat_curve_stage") or scen.get("heat_curve_stage"),
        "tes_node": row.get("tes_node") or scen.get("tes_node"),
        "Q_WP_opt_MW": _f(row, "Q_WP_opt_MW"),
        "V_TES_opt_m3": _f(row, "V_TES_m3"),
        "TAC_opt_eur_per_a": _f(row, "TAC_eur_per_a"),
        "LCOH_opt_eur_per_MWh": _f(row, "LCOH_eur_per_MWh"),
        # technical bounds (never sweep outside these)
        "q_min_mw": float(hp_inv.get("capacity_min_mw", 0.0)),
        "q_max_mw": float(hp_inv.get("capacity_max_mw", 1e9)),
        "v_min_m3": float(tes.get("V_min_m3", 0.0)),
        "v_max_m3": float(tes.get("V_max_m3", 1e9)),
        "hp_asset": HP_ASSET.get(network),
        "tes_asset": TES_ASSET.get(network),
    }


if __name__ == "__main__":
    import json
    import sys
    sid = sys.argv[1] if len(sys.argv) > 1 else "SB-S1-HK0"
    print(json.dumps({k: v for k, v in load_main_result(sid).items()
                      if k != "scenario"}, indent=2, default=str))
