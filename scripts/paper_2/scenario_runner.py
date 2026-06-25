"""Paper 2 scenario runner.

Iterates over all 20 scenarios from configs/paper_2/scenarios.yaml and:
1. Loads the base YAML config for the relevant network
2. Computes T_VL(t) from the heat curve stage parameters
3. Precomputes COP(t) from T_VL(t) + T_source(t) (waste heat priority)
4. Applies per-scenario overrides (TES node, investable flags)
5. Solves the MILP via run_workflow()
6. Extracts artefacts and saves to output/paper2_runs/{scenario_id}/

Follows the same pattern as scripts/paper/run_paper_full.py phase 1.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# Project root
_ROOT = Path(__file__).resolve().parents[2]

logger = logging.getLogger(__name__)

OUT_BASE = _ROOT / "output" / "paper2_runs"
SCENARIOS_YAML = _ROOT / "configs" / "paper_2" / "scenarios.yaml"


def load_scenarios_config() -> dict:
    with open(SCENARIOS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins on conflicts)."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class _IndentedDumper(yaml.Dumper):
    """Dump sequences indented under their parent key.

    PyYAML's default style puts '-' at the same indent as the key:
        consumers:
        - column: X
    simple_yaml (CALION's parser) requires the '-' to be indented:
        consumers:
          - column: X
    Setting indentless=False in increase_indent() achieves this.
    """
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow=flow, indentless=False)


def _dump_yaml_tmp(cfg: dict) -> Path:
    """Write config to a temp file in simple_yaml-compatible format."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w", encoding="utf-8")
    yaml.dump(cfg, tmp, Dumper=_IndentedDumper, allow_unicode=True,
              default_flow_style=False, indent=2)
    tmp.flush()
    return Path(tmp.name)


def _load_outdoor_temps(table, cfg: dict) -> np.ndarray | None:
    """Extract outdoor temperature column from the timeseries table."""
    # Try common column names
    for col_name in ["T_Aussentemperatur_C", "T_außen_C", "t_aus", "T_außen", "outdoor_temp_C"]:
        if hasattr(table, "columns") and col_name in table.columns:
            return np.array([float(table[col_name][i]) for i in range(len(table))])
        if isinstance(table, dict) and col_name in table:
            return np.array([float(v) for v in table[col_name]])
    logger.warning("No outdoor temperature column found; heating curve uses fixed T_VL")
    return None


def _load_waste_heat(cfg: dict, table) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Load waste heat time series (Q_AW, T_AW, T_amb) from config or data table.

    Returns (Q_AW_ts, T_AW_ts, T_amb_ts) or None if no waste heat configured.
    """
    wh_cfg = cfg.get("waste_heat", {})
    if not wh_cfg:
        return None

    q_col = wh_cfg.get("Q_AW_max_column")
    t_aw_col = wh_cfg.get("T_AW_column")
    t_amb_col = wh_cfg.get("T_amb_column")

    def _col(name):
        if name and hasattr(table, "columns") and name in table.columns:
            return np.array([float(table[name][i]) for i in range(len(table))])
        if name and isinstance(table, dict) and name in table:
            return np.array([float(v) for v in table[name]])
        return None

    Q_AW = _col(q_col)
    T_AW = _col(t_aw_col)
    T_amb = _col(t_amb_col)

    if Q_AW is None:
        return None

    n = len(Q_AW)
    if T_AW is None:
        T_AW = np.full(n, 30.0)  # Default 30°C waste heat temp
        logger.warning("No T_AW column found; using default 30°C waste heat temperature")
    if T_amb is None:
        T_amb = np.full(n, 10.0)  # Default 10°C ambient
        logger.warning("No T_amb column found; using default 10°C ambient temperature")

    return Q_AW, T_AW, T_amb


def run_single_scenario(
    scen: dict,
    scen_cfg: dict,
    *,
    dry_run: bool = False,
    force_rerun: bool = False,
) -> dict:
    """Run a single Paper 2 MILP scenario and extract results.

    Args:
        scen: Scenario dict from scenarios.yaml (id, network, heat_curve_stage, etc.)
        scen_cfg: Full scenarios config (heat_curve_stages, tes_nodes, etc.)
        dry_run: If True, skip solver and return stub result.
        force_rerun: If True, re-run even if output already exists.

    Returns:
        Result dict with keys: id, status, solve_s, obj_eur, outdir.
    """
    scen_id = scen["id"]
    outdir = OUT_BASE / scen_id

    # Skip if already done (restart safety)
    if (outdir / "meta.json").exists() and not force_rerun:
        logger.info("[SKIP] %s — already complete (meta.json exists)", scen_id)
        return {"id": scen_id, "status": "skipped", "outdir": str(outdir)}

    logger.info("=" * 60)
    logger.info("Starting scenario: %s", scen_id)
    logger.info("  Network: %s | HK: %s | TES: %s",
                scen["network"], scen["heat_curve_stage"], scen.get("tes_node"))

    # 1. Load base YAML config
    cfg_path = _ROOT / scen["config"]
    if not cfg_path.exists():
        if "SB" in scen_id:
            logger.warning("[SKIP] %s — Stadtbach config not yet available: %s", scen_id, cfg_path)
            return {"id": scen_id, "status": "skipped_no_config", "outdir": str(outdir)}
        raise FileNotFoundError(f"Config not found: {cfg_path}")

    cfg = _load_yaml(cfg_path)

    # 2. Apply per-scenario overrides from scenarios.yaml
    if scen.get("overrides"):
        cfg = _deep_merge(cfg, scen["overrides"])

    # 3. Apply TES node location (move tes asset to the scenario node)
    if scen.get("tes_node") and not scen.get("baseline"):
        _apply_tes_location(cfg, scen, scen_cfg)

    # 4. Apply DSM consumers (if any configured)
    _apply_dsm(cfg, scen, scen_cfg)

    if dry_run:
        logger.info("[DRY-RUN] Would solve %s", scen_id)
        return {"id": scen_id, "status": "dry_run", "outdir": str(outdir)}

    # 5. Load data table (needed for outdoor temps and waste heat)
    from calion.run.workflow import _build_workflow_inputs
    try:
        inputs = _build_workflow_inputs([str(_dump_yaml_tmp(cfg))], overrides=None)
        table = inputs.table
    except Exception as exc:
        logger.error("[%s] Failed to load data table: %s", scen_id, exc)
        return {"id": scen_id, "status": "error_data", "error": str(exc)}

    # 6. Compute T_VL(t) from heat curve stage
    # heat_curve_stages may be network-keyed (stadtbach/memmingen) or flat (legacy)
    hk_stages = scen_cfg["heat_curve_stages"]
    network = scen.get("network", "memmingen")
    _first_val = next(iter(hk_stages.values())) if hk_stages else {}
    if isinstance(_first_val, dict) and network in hk_stages:
        hk_stage = hk_stages[network][scen["heat_curve_stage"]]
    else:
        hk_stage = hk_stages[scen["heat_curve_stage"]]
    T_aus = _load_outdoor_temps(table, cfg)

    if T_aus is not None:
        from calion.utils.heizkurve import compute_heizkurve
        T_VL_ts = compute_heizkurve(
            k=hk_stage["k"],
            T_VL_min_c=hk_stage["T_VL_min_c"],
            T_VL_max_c=hk_stage["T_VL_max_c"],
            T_aus_ts=T_aus,
        )
        # Ensure T_supply > T_return; +2°C physical minimum.
        # Pipe capacity constraints are disabled (max_velocity_m_s=100) for both networks,
        # so only the physical floor (T_supply > T_return) is enforced.
        return_temp_c = float(cfg.get("network", {}).get("return_temp_c", 60.0))
        T_VL_min_effective = max(float(hk_stage["T_VL_min_c"]), return_temp_c + 2.0)
        T_VL_ts = np.maximum(T_VL_ts, T_VL_min_effective)
        logger.info(
            "[%s] T_supply_min clipped: scenario %.0f°C -> effective %.1f°C (T_return=%.1f°C)",
            scen_id, hk_stage["T_VL_min_c"], T_VL_min_effective, return_temp_c,
        )
        # Inject effective T_VL_min into config for heating_curve block
        cfg.setdefault("network", {}).setdefault("heating_curve", {})
        cfg["network"]["heating_curve"]["T_supply_min_c"] = T_VL_min_effective
        cfg["network"]["heating_curve"]["T_supply_max_c"] = hk_stage["T_VL_max_c"]
        # Also inject to heat_pumps.cop so the assembler's _compute_heating_curve_sink_temps()
        # uses scenario-specific temperatures (reads from heat_pumps.cop.supply_temp_min/max_c)
        cfg.setdefault("heat_pumps", {}).setdefault("cop", {})
        cfg["heat_pumps"]["cop"]["supply_temp_min_c"] = T_VL_min_effective
        cfg["heat_pumps"]["cop"]["supply_temp_max_c"] = hk_stage["T_VL_max_c"]
    else:
        T_VL_ts = None
        logger.warning("[%s] No outdoor temps -> heating curve not applied", scen_id)

    # 7. Precompute COP(t) with waste heat priority
    waste_heat_data = _load_waste_heat(cfg, table)
    if waste_heat_data is not None and T_VL_ts is not None:
        from calion.utils.cop_wrapper import build_source_temperature_series, precompute_cop
        Q_AW, T_AW, T_amb = waste_heat_data
        T_source_ts = build_source_temperature_series(Q_AW, T_AW, T_amb)
        cop_ts = precompute_cop(
            T_VL_ts=T_VL_ts,
            T_source_ts=T_source_ts,
            table=table,
            cfg=cfg,
            hp_type="standard",
        )
        logger.info("[%s] Precomputed COP: mean=%.2f, min=%.2f, max=%.2f",
                    scen_id, float(np.mean(cop_ts)), float(np.min(cop_ts)), float(np.max(cop_ts)))
        # Inject COP series into config for the heat pump block
        _inject_cop_series(cfg, cop_ts)

    # 8. Write final config to temp file and solve
    # Inject per-scenario Gurobi log path
    log_path = (OUT_BASE.parent / "logs" / f"gurobi_{scen_id}.log").as_posix()
    (OUT_BASE.parent / "logs").mkdir(parents=True, exist_ok=True)
    cfg.setdefault("run", {}).setdefault("solver_options", {})["LogFile"] = log_path
    cfg["run"]["solver_options"]["LogToConsole"] = 0  # file-only to keep terminal clean

    tmp_cfg_path = _dump_yaml_tmp(cfg)
    t0 = time.perf_counter()
    try:
        from calion.run.workflow import run_workflow
        wf = run_workflow([str(tmp_cfg_path)])
        elapsed = time.perf_counter() - t0
        logger.info("[%s] Solved in %.1f s", scen_id, elapsed)
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        logger.error("[%s] Solve failed after %.1f s: %s", scen_id, elapsed, exc)
        return {"id": scen_id, "status": "error_solve", "error": str(exc), "solve_s": elapsed}
    finally:
        try:
            tmp_cfg_path.unlink()
        except OSError:
            pass

    # 9. Extract artefacts
    try:
        from scripts.paper_2.extract_artefacts_p2 import extract_all_p2
        outdir.mkdir(parents=True, exist_ok=True)
        extract_all_p2(scen_id, cfg, wf, elapsed, outdir, scen)
    except Exception as exc:
        logger.error("[%s] Artefact extraction failed: %s", scen_id, exc)

    obj_val = None
    try:
        pf = wf.pf_result
        if pf and hasattr(pf, "obj_value"):
            obj_val = float(pf.obj_value)
    except Exception:
        pass

    return {
        "id": scen_id,
        "status": "ok",
        "solve_s": round(elapsed, 1),
        "obj_eur": obj_val,
        "outdir": str(outdir),
    }


def _apply_tes_location(cfg: dict, scen: dict, scen_cfg: dict) -> None:
    """Move the TES asset to the scenario-specific node in the network config."""
    network = scen["network"]
    tes_node_key = scen["tes_node"]
    tes_nodes_map = scen_cfg.get("tes_nodes", {}).get(network, {})
    node_id = tes_nodes_map.get(tes_node_key)

    if node_id is None or node_id.startswith("TODO"):
        logger.warning(
            "[%s] TES node ID for %s-%s not configured yet (placeholder). "
            "Update configs/paper_2/scenarios.yaml -> tes_nodes.%s.%s",
            scen["id"], network, tes_node_key, network, tes_node_key,
        )
        return

    # Find which node currently has the TES asset
    tes_asset_key = "tes_main" if network == "memmingen" else "tes_sb"
    nodes = cfg.get("network", {}).get("nodes", {})

    # Remove TES from current node
    for nid, ncfg in nodes.items():
        assets = ncfg.get("assets", [])
        if tes_asset_key in assets:
            assets.remove(tes_asset_key)
            logger.info("[%s] Removed %s from node %s", scen["id"], tes_asset_key, nid)

    # Add TES to target node
    if node_id in nodes:
        nodes[node_id].setdefault("assets", []).append(tes_asset_key)
        logger.info("[%s] Placed %s at node %s (%s)", scen["id"], tes_asset_key, node_id, tes_node_key)
    else:
        logger.warning("[%s] Target TES node %s not found in network config", scen["id"], node_id)


def _apply_dsm(cfg: dict, scen: dict, scen_cfg: dict) -> None:
    """Add DSM consumers if configured for this network."""
    network = scen["network"]
    dsm_list = scen_cfg.get("dsm_consumers", {}).get(network, [])
    if not dsm_list:
        return
    cfg.setdefault("dsm", {})["consumers"] = dsm_list
    logger.info("[%s] Applied %d DSM consumers", scen["id"], len(dsm_list))


def _inject_cop_series(cfg: dict, cop_ts: np.ndarray) -> None:
    """Inject precomputed COP series into config for the heat pump asset."""
    cop_list = [round(float(c), 4) for c in cop_ts]
    # Inject into first heat pump asset found
    for asset_key, asset_cfg in cfg.get("assets", {}).items():
        if asset_cfg.get("type") == "heat_pump":
            asset_cfg["cop_series_override"] = cop_list
            logger.debug("Injected COP series (%d values) into asset %s", len(cop_list), asset_key)
            break


def run_all_scenarios(
    scenario_ids: list[str] | None = None,
    *,
    dry_run: bool = False,
    force_rerun: bool = False,
) -> list[dict]:
    """Run all (or a subset of) Paper 2 scenarios.

    Args:
        scenario_ids: If given, run only these scenario IDs. Else run all 20.
        dry_run: Preview without solving.
        force_rerun: Re-run even if output exists.

    Returns:
        List of result dicts from run_single_scenario().
    """
    scen_cfg = load_scenarios_config()
    all_scenarios = scen_cfg["scenarios"]

    if scenario_ids:
        scenarios = [s for s in all_scenarios if s["id"] in scenario_ids]
        not_found = set(scenario_ids) - {s["id"] for s in scenarios}
        if not_found:
            logger.warning("Unknown scenario IDs: %s", not_found)
    else:
        scenarios = all_scenarios

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    results = []
    for scen in scenarios:
        result = run_single_scenario(scen, scen_cfg, dry_run=dry_run, force_rerun=force_rerun)
        results.append(result)
        status = result.get("status", "?")
        logger.info("[%s] -> %s", scen["id"], status)

    return results
