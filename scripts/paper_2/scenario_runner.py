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
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# Project root
_ROOT = Path(__file__).resolve().parents[2]
# Unlike its siblings (run_paper2_full.py, enumerate_endog_siting.py), this
# module used to skip this insert, which only worked when Python's own
# script-mode sys.path[0] (this file's directory) happened to make `calion`
# importable some other way (e.g. an editable install). On a clean clone,
# `python scripts/paper_2/scenario_runner.py` fails with
# `ModuleNotFoundError: No module named 'calion'`; `python -m
# scripts.paper_2.scenario_runner` masked it by adding the repo root via cwd.
# This makes direct script invocation work too, matching the siblings.
sys.path.insert(0, str(_ROOT))

logger = logging.getLogger(__name__)

OUT_BASE = _ROOT / "output" / "paper2_runs"
SCENARIOS_YAML = _ROOT / "configs" / "paper_2" / "scenarios.yaml"
STORAGE_GEOMETRY_YAML = _ROOT / "configs" / "paper_2" / "storage_geometry.yaml"

_STORAGE_GEOM_CACHE: dict | None = None


def _load_storage_geometry(cfg: dict | None = None) -> dict:
    """Atmospheric TES geometry/cost params — OPT-IN via env CALION_ATMOSPHERIC_TES=1.

    Returns {} when disabled, so every existing campaign scenario is bit-for-bit
    unchanged (the v3 atmospheric model must not silently alter the frozen v1/v2
    results). When enabled, returns the `storage_geometry:` block of
    configs/paper_2/storage_geometry.yaml (surface loss, degressive cost,
    eta_strat, atmospheric ceiling).
    """
    global _STORAGE_GEOM_CACHE
    import os
    if not os.environ.get("CALION_ATMOSPHERIC_TES"):
        return {}
    if _STORAGE_GEOM_CACHE is None:
        try:
            _STORAGE_GEOM_CACHE = (yaml.safe_load(
                open(STORAGE_GEOMETRY_YAML, encoding="utf-8")) or {}).get("storage_geometry", {})
        except FileNotFoundError:
            _STORAGE_GEOM_CACHE = {}
    return _STORAGE_GEOM_CACHE


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


def _load_hp_source_temps(cfg: dict, table) -> np.ndarray | None:
    """Fallback source-temperature series from the first HP's WRG column."""
    for a in cfg.get("assets", {}).values():
        if a.get("type") == "heat_pump":
            col = a.get("wrg_source_column")
            if col and hasattr(table, "columns") and col in table.columns:
                return np.array([float(table[col][i]) for i in range(len(table))])
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
    extra_solver_options: dict | None = None,
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

    # Feature-gated scenarios (hot charging, endogenous siting) are defined in
    # the matrix but skipped until the corresponding model feature lands.
    if scen.get("requires_feature"):
        feats = scen["requires_feature"]
        feats = feats if isinstance(feats, list) else [feats]
        logger.warning("[SKIP] %s — requires unimplemented feature(s): %s",
                       scen_id, ", ".join(feats))
        return {"id": scen_id, "status": "skipped_pending_feature",
                "features": feats, "outdir": str(outdir)}

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

    # 3b. Apply HP/EK node location (spec §3.3: HP/EK fixed at the waste-heat
    # node — SB "J4", MM j_12). Mapped via scenarios.yaml hp_nodes/hp_assets.
    if scen.get("hp_node"):
        _apply_hp_location(cfg, scen, scen_cfg)

    # 4. Apply DSM consumers (if any configured)
    _apply_dsm(cfg, scen, scen_cfg)

    # 4b. Endogenous siting (F3): MILP chooses TES (and HP/EK) node freely.
    # Assets stay attached where the base config lists them; the assembler
    # splits their heat flows across candidate nodes gated by site binaries.
    if scen.get("endogenous"):
        _network = scen["network"]
        _cands = scen_cfg.get("endogenous_candidates", {}).get(_network, [])
        if not _cands:
            logger.warning(
                "[%s] endogenous scenario but no endogenous_candidates for %s "
                "in scenarios.yaml — flows stay at base-config nodes",
                scen_id, _network,
            )
        else:
            cfg["endogenous_siting"] = {
                "candidates": list(_cands),
                "hp_group": list(scen_cfg.get("hp_assets", {}).get(_network, [])),
                "tes_group": ["tes_main" if _network == "memmingen" else "tes_sb"],
                "colocate": bool(scen.get("colocate", False)),
            }
            logger.info(
                "[%s] ENDOGENOUS SITING: candidates=%s, colocate=%s",
                scen_id, _cands, bool(scen.get("colocate", False)),
            )

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
    # TVL-fix mode (BC + S0-TVLFIX): constant Paper-1 setpoint, no heating curve.
    # Modeled as a degenerate stage with k=0 and T_min=T_max=setpoint, so the
    # entire downstream path (floor check, COP precompute, delta_T injection)
    # is reused unchanged.
    tvl_fix = bool(scen.get("tvl_fix", False))
    network = scen.get("network", "memmingen")
    if tvl_fix:
        _setpoint = float(cfg.get("network", {}).get("supply_temp_c", 99.0))
        hk_stage = {"k": 0.0, "T_VL_min_c": _setpoint, "T_VL_max_c": _setpoint,
                    "description": f"TVL fix: constant {_setpoint:.1f} degC (Paper-1 setpoint)"}
        logger.info("[%s] TVL-fix mode: constant T_VL = %.1f degC", scen_id, _setpoint)
    else:
        # heat_curve_stages may be network-keyed (stadtbach/memmingen) or flat (legacy)
        hk_stages = scen_cfg["heat_curve_stages"]
        _first_val = next(iter(hk_stages.values())) if hk_stages else {}
        if isinstance(_first_val, dict) and network in hk_stages:
            hk_stage = hk_stages[network][scen["heat_curve_stage"]]
        else:
            hk_stage = hk_stages[scen["heat_curve_stage"]]
    # Retrofit heat curves (HK1/HK2) model a substation retrofit that lowers the
    # RETURN temperature along with supply (better heat exchangers extract more →
    # colder return, which is the retrofit's actual benefit). Without this, supply
    # drops but return stays put, collapsing ΔT to the min-ΔT floor at mild hours
    # and overshooting pipe velocity/pressure limits network-wide (~50 h/yr). A
    # per-stage T_RL_c overrides the network return so ΔT stays healthy (~15 K).
    _stage_return = hk_stage.get("T_RL_c")
    if _stage_return is not None:
        cfg.setdefault("network", {})["return_temp_c"] = float(_stage_return)
        logger.info("[%s] Retrofit return temp: T_return=%.1f°C (per heat-curve stage)",
                    scen_id, float(_stage_return))
    T_aus = _load_outdoor_temps(table, cfg)
    if T_aus is None and tvl_fix:
        # Outdoor temps are irrelevant for the k=0 constant curve
        T_aus = np.zeros(len(table))

    if T_aus is not None:
        from calion.utils.heizkurve import compute_heizkurve
        T_VL_ts = compute_heizkurve(
            k=hk_stage["k"],
            T_VL_min_c=hk_stage["T_VL_min_c"],
            T_VL_max_c=hk_stage["T_VL_max_c"],
            T_aus_ts=T_aus,
        )
        # Physical floor: T_VL_min ≥ T_return + 10 K (VDI 6002 minimum ΔT for
        # consumer substation operation). The +2°C bare minimum was too low —
        # below +10K no real DH substation delivers rated heat transfer.
        return_temp_c = float(cfg.get("network", {}).get("return_temp_c", 60.0))
        min_delta_T = float(cfg.get("network", {}).get("min_supply_delta_T_k", 10.0))
        T_VL_min_effective = max(float(hk_stage["T_VL_min_c"]), return_temp_c + min_delta_T)
        T_VL_ts = np.maximum(T_VL_ts, T_VL_min_effective)
        if T_VL_min_effective > float(hk_stage["T_VL_min_c"]) + 0.1:
            logger.warning(
                "[%s] T_VL_min raised: config %.1f°C -> %.1f°C "
                "(T_return=%.1f°C + min_delta_T=%.0fK). "
                "Original value is below consumer substation minimum.",
                scen_id, hk_stage["T_VL_min_c"], T_VL_min_effective,
                return_temp_c, min_delta_T,
            )
        else:
            logger.info(
                "[%s] T_supply_min: %.1f°C (T_return=%.1f°C, delta_T=%.1fK)",
                scen_id, T_VL_min_effective, return_temp_c,
                T_VL_min_effective - return_temp_c,
            )

        # Consumer minimum temperature check: warn if T_VL(t) drops below
        # the per-network substation minimum at any timestep.
        _consumer_min_c = float(cfg.get("network", {}).get("consumer_min_temp_c",
                                                             return_temp_c + min_delta_T))
        from calion.utils.heizkurve import check_consumer_min_temps
        _violations = check_consumer_min_temps(
            T_VL_ts,
            consumer_min_temps_c={"network": _consumer_min_c},
        )
        if _violations:
            v = _violations["network"]
            logger.warning(
                "[%s] CONSUMER TEMP VIOLATION: T_supply < %.1f°C in %d hours (%.1f%% of year). "
                "Max deficit: %.2f K. Consumers may receive insufficient heat.",
                scen_id, _consumer_min_c, v["violations"],
                v["hours_below_pct"], v["max_deficit_c"],
            )
        else:
            logger.info(
                "[%s] Consumer temperature check passed: T_supply ≥ %.1f°C in all timesteps.",
                scen_id, _consumer_min_c,
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

        # Inject per-scenario delta_T into every geometric_storage TES asset
        # (tes_main/tes_sb, and tes_existing where present).
        # delta_T = T_VL_min_effective - T_return (worst case, not the mean).
        # PHYSICS FIX (2026-07-08): the mean-ΔT formula (T_VL_min+T_VL_max)/2 -
        # T_return credited the tank with an average energy density that isn't
        # actually available at the coldest point of the heating curve, where
        # T_VL sits at T_VL_min and the real usable spread is only T_VL_min -
        # T_return. Since the tank's geometry (V, h) is sized once from this
        # scalar ΔT and the network's real T_supply[t]/T_return[t] are solved
        # independently (thermal_node.py), using the mean systematically
        # understated V_TES for a given energy_mwh — i.e. overstated the
        # tank's deliverable energy at low-ΔT winter conditions. Using the
        # worst-case ΔT instead makes the geometry conservative: the tank
        # can always deliver its rated energy, even at T_VL_min.
        # Previously only one hardcoded asset (tes_main/tes_sb) was updated
        # per HK stage; tes_existing was left at its static config ΔT across
        # all stages. Now every geometric_storage asset is updated so fixed
        # and investable tanks stay consistent within a scenario.
        delta_T_scenario_k = round(T_VL_min_effective - return_temp_c, 2)
        _geom = _load_storage_geometry(cfg)
        for _asset_key, _asset_cfg in cfg.get("assets", {}).items():
            if _asset_cfg.get("type") == "geometric_storage":
                _asset_cfg["delta_T_scenario_k"] = delta_T_scenario_k
                # v3: inject atmospheric geometry/cost params (storage_geometry.yaml)
                # + the scenario return temp, so the loss ΔT and store ceiling work.
                # setdefault -> a per-asset config value overrides the global default.
                if _geom:
                    # Global params: setdefault (asset config value wins).
                    for _gk, _gv in _geom.items():
                        if _gk == "per_asset":
                            continue
                        _asset_cfg.setdefault(_gk, _gv)
                    _asset_cfg.setdefault("t_return_c", round(return_temp_c, 2))
                    # Per-asset atmospheric envelope: OVERRIDE the frozen
                    # pressurized caps/ladder (V_max, p_max, r_hd, ladder).
                    _pa = (_geom.get("per_asset") or {}).get(_asset_key)
                    if _pa:
                        _asset_cfg.update(_pa)
                logger.info(
                    "[%s] geometric_storage %s: delta_T_scenario_k=%.2f K (worst-case; "
                    "T_VL_min=%.1f°C, T_return=%.1f°C)%s",
                    scen_id, _asset_key, delta_T_scenario_k,
                    T_VL_min_effective, return_temp_c,
                    f", loss={_asset_cfg.get('loss_model')}/cost={_asset_cfg.get('cost_model')}" if _geom else "",
                )
    else:
        T_VL_ts = None
        logger.warning("[%s] No outdoor temps -> heating curve not applied", scen_id)

    # 7. Precompute COP(t) with waste heat priority (spec §4.3.1)
    T_source_ts = None
    waste_heat_data = _load_waste_heat(cfg, table)
    if waste_heat_data is not None:
        from calion.utils.cop_wrapper import build_source_temperature_series
        Q_AW, T_AW, T_amb = waste_heat_data
        T_source_ts = build_source_temperature_series(Q_AW, T_AW, T_amb)
    else:
        # Fallback (e.g. Memmingen: no waste_heat section): use the HP's
        # WRG source-temperature column directly.
        T_source_ts = _load_hp_source_temps(cfg, table)

    if T_source_ts is not None and T_VL_ts is not None:
        from calion.utils.cop_wrapper import precompute_cop
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

        # F2: hot charging — HP charges the TES at T_charge = T_VL,max via a
        # second (lower-COP) channel. TES energy density uses the hot ΔT.
        if scen.get("hot_charging"):
            T_charge_c = float(hk_stage["T_VL_max_c"])
            cop_hot_ts = np.clip(
                precompute_cop(
                    T_VL_ts=np.full(len(T_VL_ts), T_charge_c),
                    T_source_ts=T_source_ts,
                    table=table,
                    cfg=cfg,
                    hp_type="standard",
                ),
                1.01, 8.0,
            )
            _tes_key = "tes_main" if network == "memmingen" else "tes_sb"
            _hp_key = None
            for _ak, _acfg in cfg.get("assets", {}).items():
                if _acfg.get("type") == "heat_pump":
                    _acfg["cop_charge_series_override"] = [
                        round(float(c), 4) for c in cop_hot_ts
                    ]
                    _hp_key = _ak
                    break
            _rt = float(cfg.get("network", {}).get("return_temp_c", 60.0))
            _tes_asset = cfg.get("assets", {}).get(_tes_key, {})
            if _tes_asset.get("type") == "geometric_storage":
                _tes_asset["delta_T_scenario_k"] = round(T_charge_c - _rt, 2)
            if _hp_key is not None:
                cfg["hot_charging_coupling"] = {"hp": _hp_key, "tes": _tes_key}
                logger.info(
                    "[%s] HOT CHARGING: T_charge=%.1f degC, TES dT=%.1f K, "
                    "COP_hot mean=%.2f (vs net %.2f)",
                    scen_id, T_charge_c, T_charge_c - _rt,
                    float(np.mean(cop_hot_ts)), float(np.mean(cop_ts)),
                )
            else:
                logger.warning("[%s] hot_charging set but no heat_pump asset found", scen_id)

    # 7b. Lightweight spatial supply-temperature drop (2026-07-08).
    # Instead of the McCormick L3+ temperature propagation (which makes the
    # 8760-h model ~6M rows and intractable -- see plan greedy-wandering-alpaca /
    # report Part E.1), give each node a per-node supply-temperature OFFSET equal
    # to the cumulative heat-loss temperature drop from the plant to that node.
    # T stays a Param (no bilinear, no McCormick), but supply temperature now
    # DROPS spatially node-to-node. Physically motivated, keeps the model at the
    # solvable L3 size, and applies identically to both networks.
    if T_VL_ts is not None:
        _apply_spatial_temperature_offsets(cfg, T_VL_ts, scen_id)

    # 8. Write final config to temp file and solve
    # Inject per-scenario Gurobi log path and any parallel-runner solver overrides
    if extra_solver_options:
        cfg.setdefault("run", {}).setdefault("solver_options", {}).update(extra_solver_options)
    log_path = (OUT_BASE.parent / "logs" / f"gurobi_{scen_id}.log").as_posix()
    (OUT_BASE.parent / "logs").mkdir(parents=True, exist_ok=True)
    cfg.setdefault("run", {}).setdefault("solver_options", {})["LogFile"] = log_path
    cfg["run"]["solver_options"]["LogToConsole"] = 0  # file-only to keep terminal clean

    tmp_cfg_path = _dump_yaml_tmp(cfg)
    t0 = time.perf_counter()
    try:
        from calion.run.workflow import run_workflow
        wf = run_workflow([str(tmp_cfg_path)])
        import os
        if os.environ.get("CALION_DEBUG_COSTS"):
            print("DEBUG_COSTS", scen_id, dict(wf.pf_result.costs) if wf.pf_result else None)
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

    # ── Incumbent / status check (2026-07-08, fixes O-7) ─────────────────────
    # run_workflow() only RAISES on infeasible/unbounded; a maxTimeLimit or
    # aborted run that found ZERO incumbents returns normally with empty/zero
    # values, and this function used to blindly report status="ok" with obj=0.
    # That silently poisons the results table with zero-cost artefacts (exactly
    # the reviewer's O-7 concern). Gate "ok" on a real incumbent existing
    # (solver_meta.solution_count > 0). A maxTimeLimit run that DID find an
    # incumbent is still "ok" (valid solution, gap possibly > MIPGap target),
    # but is tagged with its termination_condition so downstream can filter.
    solver_meta: dict = {}
    obj_val = None
    try:
        pf = wf.pf_result
        if pf is not None:
            solver_meta = getattr(pf, "solver", {}) or {}
            # Objective: prefer the model objective recorded in the summary,
            # fall back to summed cost terms; never fabricate a 0.
            summ = getattr(pf, "summary", {}) or {}
            obj_section = summ.get("objective", {}) if hasattr(summ, "get") else {}
            for _k in ("OBJ_value_EUR", "Model_OBJ_value_EUR"):
                if isinstance(obj_section, dict) and obj_section.get(_k) is not None:
                    obj_val = float(obj_section[_k])
                    break
    except Exception:
        pass

    term_cond = str(solver_meta.get("termination_condition", "")).lower()
    sol_count = solver_meta.get("solution_count", None)

    if sol_count is not None and sol_count <= 0:
        # No incumbent -> NOT a usable result. Do not let it pass as "ok".
        logger.error(
            "[%s] No incumbent solution found (termination=%s, solve_s=%.1f). "
            "Reporting status=no_incumbent so it is NOT counted as a valid run.",
            scen_id, term_cond or "?", elapsed,
        )
        return {
            "id": scen_id,
            "status": "no_incumbent",
            "solve_s": round(elapsed, 1),
            "obj_eur": None,
            "termination": term_cond or None,
            "outdir": str(outdir),
        }

    if term_cond and ("maxtimelimit" in term_cond or "aborted" in term_cond):
        logger.warning(
            "[%s] Solved to an incumbent but hit the time limit (termination=%s, "
            "obj=%s EUR) -- valid but MIP gap may exceed the 0.5%% target.",
            scen_id, term_cond, f"{obj_val:.0f}" if obj_val is not None else "?",
        )

    return {
        "id": scen_id,
        "status": "ok",
        "solve_s": round(elapsed, 1),
        "obj_eur": obj_val,
        "termination": term_cond or None,
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
        # If the node has consumers but no explicit type, unified_config.py would infer
        # 'mixed' (assets + demands → mixed) and fix its P_supply=10 bar, creating a
        # pressure loop with the actual source node. Preserve 'consumer' classification —
        # but ONLY for a node that had no OTHER assets before this move (the case this
        # was written for: a pure downstream consumer gaining TES as its sole asset).
        # BUGFIX (2026-07-04): the blanket "no type + has consumers -> consumer" rule
        # also fired for nodes that already host generation (e.g. Memmingen's j_1:
        # chp_main+biomass_main+gasboiler_main+consumers, no explicit type) — silently
        # reclassifying the network's primary producer as a plain consumer. That drops
        # it from `all_producer_node_ids` in NetworkManager._link_pressure_propagation,
        # so it never gets a fixed P_supply setpoint -> proven infeasible (IIS pointed
        # at J_1/J_2/J_3 heat_demand + mass_balance + pipe PWL-flow-sum constraints on
        # every MM-S1-HK* run; confirmed independent of TES volume, i.e. the TES itself
        # wasn't the trigger — this node-type side effect was).
        target = nodes[node_id]
        existing_assets = [a for a in target.get('assets', []) if a != tes_asset_key]
        if 'type' not in target and target.get('consumers') and not existing_assets:
            target['type'] = 'consumer'
        target.setdefault("assets", []).append(tes_asset_key)
        logger.info("[%s] Placed %s at node %s (%s)", scen["id"], tes_asset_key, node_id, tes_node_key)
    else:
        logger.warning("[%s] Target TES node %s not found in network config", scen["id"], node_id)


def _apply_hp_location(cfg: dict, scen: dict, scen_cfg: dict) -> None:
    """Move the HP/EK assets to the scenario-specified node.

    scen["hp_node"] is a spec-level key (e.g. "J4") resolved via
    scen_cfg["hp_nodes"][network]. The asset keys moved are listed in
    scen_cfg["hp_assets"][network] (e.g. [hp_sb, ek_sb]).

    The target node is NOT forced to type 'consumer' (unlike the TES helper):
    a generator at a consumer node must be classified 'mixed' so the primary
    heat balance subtracts its local generation (constraint_builder fix
    2026-06-30). Pressure conflicts are handled by network.primary_producer.
    """
    network = scen["network"]
    key = scen["hp_node"]
    node_id = scen_cfg.get("hp_nodes", {}).get(network, {}).get(key)
    if node_id is None:
        logger.warning(
            "[%s] hp_node %s not mapped for %s — HP stays at base-config node. "
            "Update configs/paper_2/scenarios.yaml -> hp_nodes.%s.%s",
            scen["id"], key, network, network, key,
        )
        return

    asset_keys = scen_cfg.get("hp_assets", {}).get(network, [])
    nodes = cfg.get("network", {}).get("nodes", {})
    if node_id not in nodes:
        logger.warning("[%s] Target HP node %s not found in network config", scen["id"], node_id)
        return

    for akey in asset_keys:
        for nid, ncfg in nodes.items():
            assets = ncfg.get("assets", [])
            if akey in assets:
                assets.remove(akey)
                logger.info("[%s] Removed %s from node %s", scen["id"], akey, nid)
        nodes[node_id].setdefault("assets", []).append(akey)
    logger.info("[%s] Placed %s at node %s (%s)", scen["id"], asset_keys, node_id, key)


def _apply_spatial_temperature_offsets(cfg: dict, T_VL_ts, scen_id: str) -> None:
    """Compute each node's cumulative supply-temperature drop from the plant
    (heat loss along the trunk) and inject it as `T_supply_offset_c` per node.

    This is the lightweight alternative to McCormick L3+ temperature
    propagation: it keeps supply temperature a Param (no bilinear terms, no
    ~6M-row explosion), while making the supply temperature DROP spatially,
    node by node, by the physically-correct heat-loss amount.

    Per pipe (i->j):
        dT_pipe = U * L * (T_avg - T_ground) / (m_dot_design * cp)   [K]
    with T_avg the mean supply temperature over the horizon, m_dot_design a
    representative design flow from the pipe diameter at ~1 m/s, cp in J/(kg K).
    The offset at node j is the sum of dT_pipe over the plant->j path (negative,
    i.e. cooler downstream). Skips if temperature_propagation (McCormick L3+) is
    still active, since that models the drop endogenously.
    """
    import numpy as _np
    net = cfg.get("network", {})
    if net.get("temperature_propagation"):
        return  # McCormick L3+ handles the drop endogenously; don't double-count
    pipes = net.get("nodes") is not None and net.get("pipes") or {}
    nodes = net.get("nodes", {})
    if not pipes or not nodes:
        return

    _CP = 4186.0        # J/(kg K)
    _RHO = 971.8        # kg/m3 (~75 C)
    _V_DESIGN = 1.0     # m/s representative design velocity for the flow estimate
    T_ground = float(net.get("ground_temp_c", 10.0))
    try:
        T_avg = float(_np.mean(T_VL_ts))
    except Exception:
        T_avg = float(net.get("supply_temp_c", 90.0))

    # adjacency from -> [(to, pipe_cfg)]; identify the root (plant)
    adj: dict[str, list] = {}
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for pid, p in pipes.items():
        fr = p.get("from") or p.get("from_node")
        to = p.get("to") or p.get("to_node")
        if fr is None or to is None:
            continue
        adj.setdefault(fr, []).append((to, p))
        indeg[to] = indeg.get(to, 0) + 1
    primary = net.get("primary_producer")
    roots = [primary] if primary and primary in nodes else [n for n in nodes if indeg.get(n, 0) == 0]
    if not roots:
        return

    def _pipe_drop(p: dict) -> float:
        L = float(p.get("length_m", 0.0) or 0.0)
        d_mm = float(p.get("diameter_mm", 0.0) or 0.0)
        U = float(p.get("u_value_supply_w_per_m_k", 0.32) or 0.32)
        if L <= 0 or d_mm <= 0:
            return 0.0
        A = _np.pi / 4.0 * (d_mm / 1000.0) ** 2         # m2
        m_dot = max(_RHO * A * _V_DESIGN, 0.5)           # kg/s (floor)
        q_loss_w = U * L * max(T_avg - T_ground, 0.0)    # W
        return q_loss_w / (m_dot * _CP)                  # K

    # BFS from each root accumulating drop; guard against cycles (meshed nets)
    cum: dict[str, float] = {r: 0.0 for r in roots}
    from collections import deque
    dq = deque(roots)
    visited = set(roots)
    while dq:
        u = dq.popleft()
        for (v, p) in adj.get(u, []):
            cand = cum[u] + _pipe_drop(p)
            # for meshed nodes keep the SMALLEST drop (shortest/least-loss path)
            if v not in cum or cand < cum[v]:
                cum[v] = cand
            if v not in visited:
                visited.add(v)
                dq.append(v)

    applied = 0
    max_drop = 0.0
    for nid, ncfg in nodes.items():
        drop = cum.get(nid, 0.0)
        if drop > 0.01 and isinstance(ncfg, dict):
            # existing manually-set offset takes precedence (e.g. secondary
            # producers with a measured trunk-loss offset)
            if "T_supply_offset_c" not in ncfg:
                ncfg["T_supply_offset_c"] = -round(drop, 3)
                applied += 1
                max_drop = max(max_drop, drop)
    if applied:
        logger.info(
            "[%s] Spatial temperature drop applied to %d node(s); max cumulative "
            "drop from plant = %.2f K (T_supply Param, no McCormick)",
            scen_id, applied, max_drop,
        )


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
    gurobi_threads: int | None = None,
) -> list[dict]:
    """Run all (or a subset of) Paper 2 scenarios sequentially.

    Args:
        scenario_ids: If given, run only these scenario IDs. Else run all.
        dry_run: Preview without solving.
        force_rerun: Re-run even if output exists.
        gurobi_threads: If set, caps each solve's Gurobi Threads parameter
            (2026-07-20: this path previously left Threads unset, so Gurobi
            defaulted to using every logical processor per solve -- fine
            alone, but oversubscribes the host when multiple scenario_runner/
            enumerate_endog_siting invocations run concurrently, as they do
            during the Paper 2 campaign).

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

    extra_solver_options = {"Threads": gurobi_threads} if gurobi_threads else None

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    results = []
    for scen in scenarios:
        result = run_single_scenario(scen, scen_cfg, dry_run=dry_run, force_rerun=force_rerun,
                                      extra_solver_options=extra_solver_options)
        results.append(result)
        status = result.get("status", "?")
        logger.info("[%s] -> %s", scen["id"], status)

    return results


def run_all_scenarios_parallel(
    scenario_ids: list[str] | None = None,
    *,
    max_workers: int | None = None,
    gurobi_threads: int | None = None,
    dry_run: bool = False,
    force_rerun: bool = False,
) -> list[dict]:
    """Run Paper 2 scenarios in parallel using separate processes.

    Each scenario runs in its own process so Gurobi instances are fully
    isolated (no shared memory, no GIL contention). Gurobi thread counts
    are divided evenly across workers to avoid CPU oversubscription.

    Args:
        scenario_ids: Subset of scenario IDs to run (default: all).
        max_workers: Number of parallel solver processes.
            Default: cpu_count // gurobi_threads (auto-balanced).
        gurobi_threads: Threads per Gurobi process.
            Default: 4 (leaves room for OS + Python overhead).
        dry_run: Preview without solving.
        force_rerun: Re-run even if output exists.

    Returns:
        List of result dicts (order matches scenario definition order).
    """
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

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

    cpu_count = os.cpu_count() or 8
    if gurobi_threads is None:
        gurobi_threads = 4
    if max_workers is None:
        max_workers = max(1, cpu_count // gurobi_threads)

    logger.info(
        "Parallel run: %d scenarios | %d workers | %d Gurobi threads each | %d CPUs total",
        len(scenarios), max_workers, gurobi_threads, cpu_count,
    )

    extra_solver_opts = {"Threads": gurobi_threads}

    id_order = {s["id"]: i for i, s in enumerate(scenarios)}
    results: list[dict] = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                run_single_scenario,
                scen,
                scen_cfg,
                dry_run=dry_run,
                force_rerun=force_rerun,
                extra_solver_options=extra_solver_opts,
            ): scen["id"]
            for scen in scenarios
        }
        for fut in as_completed(futures):
            scen_id = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:
                logger.error("[%s] Worker raised: %s", scen_id, exc, exc_info=True)
                result = {"id": scen_id, "status": "error_worker", "error": str(exc)}
            results.append(result)
            logger.info("[%s] -> %s", scen_id, result.get("status", "?"))

    results.sort(key=lambda r: id_order.get(r["id"], 9999))
    return results


if __name__ == "__main__":
    import argparse
    import sys

    # Required for multiprocessing on Windows (spawn start method)
    from multiprocessing import freeze_support
    freeze_support()

    (OUT_BASE.parent / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                str(OUT_BASE.parent / "logs" / "scenario_runner.log"),
                encoding="utf-8",
            ),
        ],
    )

    parser = argparse.ArgumentParser(
        description="Paper 2 scenario runner — runs all 17 MILP scenarios",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--scenarios", "-s", nargs="*", metavar="ID",
        help="Scenario IDs to run (default: all). E.g. BC-MM MM-S1-HK0",
    )
    parser.add_argument(
        "--parallel", "-p", action="store_true",
        help="Run scenarios in parallel (ProcessPoolExecutor)",
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=None,
        help="Number of parallel worker processes (default: cpu_count // gurobi-threads)",
    )
    parser.add_argument(
        "--gurobi-threads", "-g", type=int, default=4,
        help="Gurobi Threads per solver process (avoids CPU oversubscription)",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Preview scenario list without solving",
    )
    parser.add_argument(
        "--force-rerun", "-f", action="store_true",
        help="Re-run even if output/meta.json already exists",
    )
    args = parser.parse_args()

    if args.parallel:
        results = run_all_scenarios_parallel(
            scenario_ids=args.scenarios,
            max_workers=args.workers,
            gurobi_threads=args.gurobi_threads,
            dry_run=args.dry_run,
            force_rerun=args.force_rerun,
        )
    else:
        results = run_all_scenarios(
            scenario_ids=args.scenarios,
            dry_run=args.dry_run,
            force_rerun=args.force_rerun,
            gurobi_threads=args.gurobi_threads,
        )

    # Summary table
    _skip_statuses = ("skipped", "dry_run", "skipped_no_config", "skipped_pending_feature")
    ok      = [r for r in results if r.get("status") == "ok"]
    skipped = [r for r in results if r.get("status") in _skip_statuses]
    errors  = [r for r in results if r.get("status") not in ("ok",) + _skip_statuses]

    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(ok)} OK | {len(skipped)} skipped | {len(errors)} errors")
    print(f"{'='*60}")
    for r in ok:
        obj_str = f"  obj={r['obj_eur']:,.0f}€" if r.get("obj_eur") else ""
        print(f"  OK      [{r['id']:20s}] {r.get('solve_s', '?'):>7.1f}s{obj_str}")
    for r in skipped:
        print(f"  SKIPPED [{r['id']:20s}]")
    for r in errors:
        print(f"  ERROR   [{r['id']:20s}] {r.get('error', '?')}")
    print(f"{'='*60}")
