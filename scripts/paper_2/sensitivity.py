"""Paper 2 sensitivity analysis (tornado diagram).

Runs parametric ±variation for the best scenario per network
and computes relative TAC change [%] per parameter.

Parameters (from spec §7):
  - c_el (electricity price): ±30%
  - c_CO2 (CO2 price): ±50%
  - alpha_WP (WP CAPEX): ±25%
  - Q_AW_max (waste heat availability): -50%, -100%
  - delta_max (DSM potential): 0%, +50%
  - i (discount rate): ±2 percentage points

Follows the same pattern as scripts/paper/sensitivity_runner.py from Paper 1.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)

OUT_BASE = _ROOT / "output" / "paper2_runs"

# Sensitivity parameters: {param_key: [(label, override_dict), ...]}
SENSITIVITY_PARAMS = {
    "c_el": [
        ("c_el_low", {"site": {"price_scale_factor": 0.7}}),    # -30%
        ("c_el_high", {"site": {"price_scale_factor": 1.3}}),   # +30%
    ],
    "c_co2": [
        ("c_co2_low", {"costs": {"co2_price_eur_per_t": 50.0}}),   # -50%
        ("c_co2_high", {"costs": {"co2_price_eur_per_t": 150.0}}), # +50%
    ],
    "alpha_wp": [
        ("alpha_wp_low", {
            "assets": {"hp_main": {"investment": {"capex_eur_per_mw": 525000.0}}},  # -25%
        }),
        ("alpha_wp_high", {
            "assets": {"hp_main": {"investment": {"capex_eur_per_mw": 875000.0}}},  # +25%
        }),
    ],
    "Q_AW_max": [
        ("q_aw_minus50", {"site": {"wrg_scale_factor": 0.5}}),   # -50%
        ("q_aw_zero", {"site": {"wrg_scale_factor": 0.0}}),       # -100%
    ],
    # delta_max excluded: DSM not integrated in current CALION assembler
    "discount_rate": [
        ("i_low", {"investment": {"discount_rate": 0.03}}),   # -2pp
        ("i_high", {"investment": {"discount_rate": 0.07}}),  # +2pp
    ],
}


def _find_best_scenario(network: str) -> str | None:
    """Find the scenario with lowest TAC for a given network."""
    kpi_path = OUT_BASE / "scenarios_kpis.csv"
    if not kpi_path.exists():
        return None
    with open(kpi_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    candidates = [
        r for r in rows
        if r.get("network") == network and not (r.get("baseline") in ("True", True, "true"))
    ]
    if not candidates:
        return None
    best = min(candidates, key=lambda r: float(r.get("TAC_eur_per_a") or 1e18))
    return best["scenario_id"]


def run_sensitivity_scenario(
    base_scen_id: str,
    param_key: str,
    variant_label: str,
    override: dict,
) -> dict:
    """Run a single sensitivity scenario (one parameter variation).

    Args:
        base_scen_id: Base scenario to perturb (e.g., "MM-S1-HK1")
        param_key: Parameter being varied
        variant_label: Unique label for this variant
        override: Config override dict for this parameter value

    Returns:
        Result dict with TAC and metadata.
    """
    from scripts.paper_2.scenario_runner import (
        load_scenarios_config, _load_yaml, _deep_merge, _dump_yaml_tmp
    )

    scen_cfg = load_scenarios_config()
    all_scenarios = scen_cfg["scenarios"]

    # Find base scenario
    base = next((s for s in all_scenarios if s["id"] == base_scen_id), None)
    if base is None:
        logger.error("Base scenario %s not found", base_scen_id)
        return {"id": f"{base_scen_id}_{variant_label}", "status": "error_not_found"}

    sens_id = f"{base_scen_id}_SENS_{param_key}_{variant_label}"
    outdir = OUT_BASE / "sensitivity" / sens_id

    if (outdir / "meta.json").exists():
        logger.info("[SKIP] %s already done", sens_id)
        return {"id": sens_id, "status": "skipped"}

    # Load and merge config
    cfg_path = _ROOT / base["config"]
    if not cfg_path.exists():
        return {"id": sens_id, "status": "skipped_no_config"}

    cfg = _load_yaml(cfg_path)
    if base.get("overrides"):
        cfg = _deep_merge(cfg, base["overrides"])
    cfg = _deep_merge(cfg, override)

    # Inject heating curve parameters from the base scenario's HK stage.
    # scenario_runner.py does this dynamically via compute_heizkurve(); here we use
    # the static min/max bounds so CALION's internal heating curve stays feasible
    # (T_supply_min >= T_return + 2°C is enforced at scenario level, not YAML level).
    hk_stages = scen_cfg.get("heat_curve_stages", {})
    hk_stage_key = base.get("heat_curve_stage", "HK0")
    network_key = base.get("network", "memmingen")
    first_val = next(iter(hk_stages.values()), None) if hk_stages else None
    if isinstance(first_val, dict) and network_key in hk_stages:
        hk_stage = hk_stages[network_key][hk_stage_key]
    else:
        hk_stage = hk_stages.get(hk_stage_key, {})
    if hk_stage:
        return_temp_c = float(cfg.get("network", {}).get("return_temp_c", 60.0))
        t_vl_min_c = float(hk_stage.get("T_VL_min_c", 74.0))
        t_vl_max_c = float(hk_stage.get("T_VL_max_c", 100.0))
        t_vl_min_effective = max(t_vl_min_c, return_temp_c + 2.0)
        cfg.setdefault("network", {}).setdefault("heating_curve", {})
        cfg["network"]["heating_curve"]["T_supply_min_c"] = t_vl_min_effective
        cfg["network"]["heating_curve"]["T_supply_max_c"] = t_vl_max_c
        cfg.setdefault("heat_pumps", {}).setdefault("cop", {})
        cfg["heat_pumps"]["cop"]["supply_temp_min_c"] = t_vl_min_effective
        cfg["heat_pumps"]["cop"]["supply_temp_max_c"] = t_vl_max_c

    tmp_path = _dump_yaml_tmp(cfg)
    t0 = time.perf_counter()
    try:
        from calion.run.workflow import run_workflow
        wf = run_workflow([str(tmp_path)])
        elapsed = time.perf_counter() - t0
        obj = None
        try:
            obj = float(wf.pf_result.obj_value)
        except Exception:
            pass
        outdir.mkdir(parents=True, exist_ok=True)
        with open(outdir / "meta.json", "w", encoding="utf-8") as f:
            json.dump({
                "id": sens_id, "base": base_scen_id, "param": param_key,
                "variant": variant_label, "obj_eur": obj, "solve_s": elapsed,
            }, f, indent=2)
        return {"id": sens_id, "status": "ok", "TAC_eur_per_a": obj, "solve_s": elapsed}
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        logger.error("[%s] Failed: %s", sens_id, exc)
        return {"id": sens_id, "status": "error", "error": str(exc)}
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def run_sensitivity(out_base: Path) -> dict:
    """Run full tornado sensitivity for best scenario per network.

    Returns:
        Dict with results and path to sensitivity.csv.
    """
    all_results = []

    for network in ["memmingen", "stadtbach"]:
        best_id = _find_best_scenario(network)
        if best_id is None:
            logger.warning("No best scenario found for %s — run phase 1 first", network)
            continue

        # Get baseline TAC for this network
        bc_id = "BC-MM" if network == "memmingen" else "BC-SB"
        bc_meta = _read_json(out_base / bc_id / "meta.json")
        base_obj = bc_meta.get("obj_eur")

        logger.info("Sensitivity for %s (best: %s)", network, best_id)

        for param_key, variants in SENSITIVITY_PARAMS.items():
            for variant_label, override in variants:
                # Adapt alpha_wp key for Stadtbach (hp_sb vs hp_main)
                if network == "stadtbach":
                    override = _adapt_override_for_stadtbach(override)
                res = run_sensitivity_scenario(best_id, param_key, variant_label, override)
                res["network"] = network
                res["base_scenario"] = best_id
                res["base_TAC"] = base_obj
                all_results.append(res)

    # Write sensitivity.csv
    csv_path = out_base / "sensitivity.csv"
    if all_results:
        fieldnames = ["id", "network", "base_scenario", "param", "variant",
                      "TAC_eur_per_a", "base_TAC", "delta_pct", "solve_s", "status"]
        for r in all_results:
            if r.get("TAC_eur_per_a") and r.get("base_TAC") and float(r["base_TAC"] or 0) > 0:
                r["delta_pct"] = round(
                    (float(r["TAC_eur_per_a"]) - float(r["base_TAC"])) / float(r["base_TAC"]) * 100, 2
                )
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(all_results)

    logger.info("Sensitivity complete: %d variants → %s", len(all_results), csv_path)
    return {"status": "ok", "n_variants": len(all_results), "csv": str(csv_path)}


def _adapt_override_for_stadtbach(override: dict) -> dict:
    """Rename memmingen-specific asset keys (hp_main→hp_sb, etc.) for Stadtbach."""
    result = {}
    for k, v in override.items():
        if k == "assets" and isinstance(v, dict):
            new_assets = {}
            for ak, av in v.items():
                new_key = ak.replace("hp_main", "hp_sb").replace("tes_main", "tes_sb")
                new_assets[new_key] = av
            result["assets"] = new_assets
        else:
            result[k] = v
    return result


def _read_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    run_sensitivity(OUT_BASE)
