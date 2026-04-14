"""
OAT sensitivity analysis across all three topology levels (L1, L2, L3).

Runs a one-at-a-time (OAT) parameter sweep for each topology level and
computes normalised sensitivity indices.  Results are saved as:

    outputs/paper/sensitivity/sensitivity_indices_by_level.csv
    outputs/paper/sensitivity/sensitivity_run_log.json

The CSV is consumed directly by ``scripts/paper/plot_sensitivity_heatmap.py``.

Usage
-----
    python scripts/paper/run_sensitivity_all_levels.py
    python scripts/paper/run_sensitivity_all_levels.py --outdir outputs/paper/sensitivity
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repo root on path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from calion.analysis.sensitivity import (  # noqa: E402
    ParameterVariation,
    SensitivityResult,
    apply_parameter_variation,
    calculate_sensitivity_indices,
    run_sensitivity_analysis,
)
from calion.config.merge import load_and_merge  # noqa: E402
from calion.logging_config import get_logger  # noqa: E402
from calion.run.workflow import run_workflow  # noqa: E402

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Level configurations
# ---------------------------------------------------------------------------
LEVELS: list[tuple[str, str]] = [
    ("L1", "configs/paper/L1_copperplate_dispatch.yaml"),
    ("L2", "configs/paper/L2_simplified_dispatch.yaml"),
    ("L3", "configs/paper/L3_detailed_dispatch.yaml"),
]

# ---------------------------------------------------------------------------
# Parameter variations with literature-justified ranges
# ---------------------------------------------------------------------------
VARIATIONS: list[ParameterVariation] = [
    ParameterVariation(
        param_path="fuels.gas.price_eur_mwh",
        base_value=45.0,
        variations=[0.8, 1.0, 1.2],
        variation_type="multiplicative",
        description="Natural gas price",
        units="EUR/MWh",
    ),
    ParameterVariation(
        # Special key — top-level scalar multiplier; applied via override key.
        # apply_parameter_variation will raise KeyError if the path is absent;
        # that is caught gracefully and the cell is recorded as NaN.
        param_path="electricity_price_scale",
        base_value=1.0,
        variations=[0.8, 1.0, 1.2],
        variation_type="multiplicative",
        description="Electricity price",
        units="scale factor",
    ),
    ParameterVariation(
        param_path="costs.co2_price_eur_per_t",
        base_value=100.0,
        variations=[0.5, 1.0, 1.5],
        variation_type="multiplicative",
        description="CO2 price",
        units="EUR/t",
    ),
    ParameterVariation(
        param_path="heat_pumps.hp_main.eta_relative",
        base_value=0.50,
        variations=[0.9, 1.0, 1.1],
        variation_type="multiplicative",
        description="HP Carnot factor",
        units="-",
    ),
    ParameterVariation(
        param_path="storage.tes_main.hourly_loss",
        base_value=0.0005,
        variations=[0.5, 1.0, 1.5],
        variation_type="multiplicative",
        description="Storage loss rate",
        units="1/h",
    ),
    ParameterVariation(
        param_path="storage.tes_main.eff_charge",
        base_value=0.98,
        variations=[0.97, 1.0, 1.03],
        variation_type="multiplicative",
        description="Storage charge efficiency",
        units="-",
    ),
    ParameterVariation(
        # Special key — top-level scalar multiplier; same graceful-skip logic.
        param_path="demand_scale",
        base_value=1.0,
        variations=[0.9, 1.0, 1.1],
        variation_type="multiplicative",
        description="Annual heat demand",
        units="scale factor",
    ),
]

# Number of variations expected per parameter (low / base / high)
_N_VARIATIONS = 3


# ---------------------------------------------------------------------------
# Single-run helper
# ---------------------------------------------------------------------------

def _extract_objective(workflow_result: Any) -> float:
    """Pull the scalar objective value from a finished workflow."""
    result = (
        workflow_result.pf_result
        or workflow_result.mpc_result
        or workflow_result.rh_result
    )
    if result is None:
        return math.nan

    # Primary: explicit key
    costs = result.costs or {}
    obj = costs.get("objective.OBJ_value_EUR")
    if obj is not None:
        return float(obj)

    # Fallback: sum of cost components
    components = [
        "objective.Grid_net_cost_EUR",
        "objective.Fuel_cost_EUR",
        "objective.Dump_cost_EUR",
        "objective.CO2_cost_EUR",
        "objective.Demand_charge_cost_EUR",
        "objective.Capex_cost_EUR",
        "objective.Activation_cost_EUR",
        "objective.Tie_breaker_cost_EUR",
        "objective.Storage_installation_cost_EUR",
    ]
    total = sum(float(costs.get(k, 0.0) or 0.0) for k in components)
    return total if total != 0.0 else math.nan


def _make_run_func(config_path: str) -> Any:
    """Return an optimization callable for use with run_sensitivity_analysis.

    The returned function accepts a modified config dict, writes it to a
    temporary YAML file, and calls run_workflow.  On any error the
    objective is set to NaN so the sweep continues.
    """
    import yaml  # local import — optional dependency check deferred

    def _run(config_dict: dict[str, Any]) -> SensitivityResult:
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False, encoding="utf-8"
            ) as fh:
                yaml.dump(config_dict, fh, allow_unicode=True)
                tmp_path = fh.name

            workflow = run_workflow([tmp_path])
            obj = _extract_objective(workflow)

        except Exception as exc:
            logger.warning("  run failed: %s", exc)
            obj = math.nan
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return SensitivityResult(
            param_path="",           # overwritten by run_sensitivity_analysis
            param_value=0.0,         # overwritten by run_sensitivity_analysis
            variation_label="",      # overwritten by run_sensitivity_analysis
            objective_value=obj if not math.isnan(obj) else None,
            key_metrics={"total_cost": obj if not math.isnan(obj) else 0.0},
            solve_status="ok" if not math.isnan(obj) else "failed",
        )

    return _run


# ---------------------------------------------------------------------------
# Per-level sensitivity run
# ---------------------------------------------------------------------------

def run_level_sensitivity(
    tag: str,
    config_path: str,
) -> tuple[dict[str, list[SensitivityResult]], dict[str, float]]:
    """Run OAT sensitivity for one topology level.

    Returns
    -------
    results_by_param : dict[param_path, list[SensitivityResult]]
    indices          : dict[param_path, float]
    """
    abs_cfg = str(ROOT / config_path)
    logger.info("=" * 65)
    logger.info("Level %s — loading base config: %s", tag, config_path)

    try:
        base_config = load_and_merge([abs_cfg])
    except Exception as exc:
        logger.error("Cannot load config for %s: %s", tag, exc)
        return {}, {}

    run_func = _make_run_func(abs_cfg)
    total_runs = sum(len(v.variations) for v in VARIATIONS)
    completed = 0

    results_by_param: dict[str, list[SensitivityResult]] = {}

    for var in VARIATIONS:
        param_values = var.get_values()
        param_labels = var.get_labels()
        param_results: list[SensitivityResult] = []

        for value, label in zip(param_values, param_labels):
            completed += 1
            logger.info(
                "  [%s] %d/%d  %s = %.4g  (%s)",
                tag, completed, total_runs, var.param_path, value, label,
            )
            t0 = time.perf_counter()

            # Attempt to apply the variation; skip gracefully for special keys
            try:
                modified = apply_parameter_variation(base_config, var.param_path, value)
            except KeyError as exc:
                logger.warning(
                    "  Skipping %s for %s (path absent): %s", var.param_path, tag, exc
                )
                param_results.append(
                    SensitivityResult(
                        param_path=var.param_path,
                        param_value=value,
                        variation_label=label,
                        objective_value=None,
                        solve_status="skipped: path absent",
                    )
                )
                continue

            result = run_func(modified)
            result.param_path = var.param_path
            result.param_value = value
            result.variation_label = label

            elapsed = time.perf_counter() - t0
            status_str = (
                f"{result.objective_value:,.0f} EUR"
                if result.objective_value is not None
                else "NaN"
            )
            logger.info("  -> %s  (%.1f s)", status_str, elapsed)
            param_results.append(result)

        results_by_param[var.param_path] = param_results

    indices = calculate_sensitivity_indices(results_by_param)
    return results_by_param, indices


# ---------------------------------------------------------------------------
# CSV / JSON export helpers
# ---------------------------------------------------------------------------

def _objective_triple(
    results: list[SensitivityResult],
) -> tuple[float | None, float | None, float | None]:
    """Return (low, base, high) objective values from a 3-point result list.

    Positions correspond to index 0 (low), 1 (base), 2 (high) in the list
    as defined by VARIATIONS.  Missing or failed runs yield None.
    """
    def _get(idx: int) -> float | None:
        if idx >= len(results):
            return None
        v = results[idx].objective_value
        return None if v is None else float(v)

    return _get(0), _get(1), _get(2)


def _nan_str(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "NaN"
    return str(v)


def write_csv(
    outdir: Path,
    all_results: dict[str, dict[str, list[SensitivityResult]]],
    all_indices: dict[str, dict[str, float]],
    variations: list[ParameterVariation],
) -> Path:
    """Write the comparison CSV consumed by plot_sensitivity_heatmap.py."""
    import csv

    csv_path = outdir / "sensitivity_indices_by_level.csv"
    levels = [tag for tag, _ in LEVELS]

    # Build description / units lookup from VARIATIONS
    desc_map = {v.param_path: v.description for v in variations}
    units_map = {v.param_path: v.units for v in variations}

    fieldnames = (
        ["param_path", "description", "units"]
        + [f"{lvl}_index" for lvl in levels]
        + [f"{lvl}_{pos}" for lvl in levels for pos in ("low", "base", "high")]
    )

    rows = []
    for var in variations:
        pp = var.param_path
        row: dict[str, Any] = {
            "param_path": pp,
            "description": desc_map.get(pp, ""),
            "units": units_map.get(pp, ""),
        }
        for lvl in levels:
            idx_val = all_indices.get(lvl, {}).get(pp)
            row[f"{lvl}_index"] = _nan_str(idx_val)
            results_list = all_results.get(lvl, {}).get(pp, [])
            low, base, high = _objective_triple(results_list)
            row[f"{lvl}_low"] = _nan_str(low)
            row[f"{lvl}_base"] = _nan_str(base)
            row[f"{lvl}_high"] = _nan_str(high)
        rows.append(row)

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("CSV written: %s", csv_path)
    return csv_path


def write_run_log(
    outdir: Path,
    all_results: dict[str, dict[str, list[SensitivityResult]]],
    all_indices: dict[str, dict[str, float]],
) -> Path:
    """Write the full run log JSON for debugging and archiving."""
    log_path = outdir / "sensitivity_run_log.json"

    serialisable: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "levels": {},
    }

    for lvl in [tag for tag, _ in LEVELS]:
        level_data: dict[str, Any] = {
            "sensitivity_indices": all_indices.get(lvl, {}),
            "params": {},
        }
        for pp, res_list in all_results.get(lvl, {}).items():
            level_data["params"][pp] = [
                {
                    "param_value": r.param_value,
                    "variation_label": r.variation_label,
                    "objective_value": r.objective_value,
                    "key_metrics": r.key_metrics,
                    "solve_status": r.solve_status,
                }
                for r in res_list
            ]
        serialisable["levels"][lvl] = level_data

    with log_path.open("w", encoding="utf-8") as fh:
        json.dump(serialisable, fh, indent=2, ensure_ascii=False, default=str)

    logger.info("Run log written: %s", log_path)
    return log_path


# ---------------------------------------------------------------------------
# Progress summary
# ---------------------------------------------------------------------------

def print_summary(
    all_indices: dict[str, dict[str, float]],
    variations: list[ParameterVariation],
    total_s: float,
) -> None:
    levels = [tag for tag, _ in LEVELS]
    col_w = 14

    header = f"{'Parameter':<35}" + "".join(f"{lvl:>{col_w}}" for lvl in levels)
    print("\n" + "=" * len(header))
    print("SENSITIVITY INDICES (|Δobj_range| / obj_base)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for var in variations:
        pp = var.param_path
        short = var.description or pp.split(".")[-1]
        line = f"  {short:<33}"
        for lvl in levels:
            idx = all_indices.get(lvl, {}).get(pp)
            if idx is None:
                cell = "n/a"
            else:
                cell = f"{idx:.4f}"
            line += f"{cell:>{col_w}}"
        print(line)

    print("-" * len(header))
    print(f"  Total wall time: {total_s:.1f} s")
    print("=" * len(header))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OAT sensitivity analysis at L1/L2/L3 topology levels.",
    )
    parser.add_argument(
        "--outdir",
        default="outputs/paper/sensitivity",
        help="Output directory (default: outputs/paper/sensitivity)",
    )
    parser.add_argument(
        "--levels",
        nargs="+",
        choices=["L1", "L2", "L3"],
        default=None,
        help="Subset of levels to run (default: all three).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    selected_levels = set(args.levels) if args.levels else {"L1", "L2", "L3"}
    active_levels = [(tag, cfg) for tag, cfg in LEVELS if tag in selected_levels]

    logger.info("=" * 65)
    logger.info("OAT SENSITIVITY ANALYSIS — all topology levels")
    logger.info("Output directory: %s", outdir)
    logger.info("Parameters: %d", len(VARIATIONS))
    logger.info("Levels: %s", [t for t, _ in active_levels])
    logger.info("=" * 65)

    all_results: dict[str, dict[str, list[SensitivityResult]]] = {}
    all_indices: dict[str, dict[str, float]] = {}

    wall_t0 = time.perf_counter()

    for tag, cfg_path in active_levels:
        logger.info("\nStarting level %s ...", tag)
        lvl_t0 = time.perf_counter()

        results_by_param, indices = run_level_sensitivity(tag, cfg_path)

        lvl_elapsed = time.perf_counter() - lvl_t0
        logger.info("Level %s finished in %.1f s", tag, lvl_elapsed)

        all_results[tag] = results_by_param
        all_indices[tag] = indices

    total_s = time.perf_counter() - wall_t0

    # Export
    csv_path = write_csv(outdir, all_results, all_indices, VARIATIONS)
    log_path = write_run_log(outdir, all_results, all_indices)

    # Console summary
    print_summary(all_indices, VARIATIONS, total_s)
    print(f"\nCSV : {csv_path}")
    print(f"Log : {log_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
