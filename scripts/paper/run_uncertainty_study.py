"""
Paper-oriented uncertainty study runner.

This script packages the current deterministic uncertainty workflow into a
single paper-facing entry point:

- one-at-a-time sensitivity analysis,
- named scenario matrix,
- optional CO2 resolution analysis,
- compact summary export for publication tables.

Usage examples:
    python scripts/paper/run_uncertainty_study.py
    python scripts/paper/run_uncertainty_study.py --config configs/paper/L2_costs_example_2_zonal_static.yaml
    python scripts/paper/run_uncertainty_study.py --skip-sensitivity
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from calion.analysis.co2_resolution_analysis import (  # noqa: E402
    analyze_from_result,
    create_comparison_report,
)
from calion.analysis.sensitivity import ParameterVariation  # noqa: E402
from calion.analysis.sensitivity_runner import run_full_sensitivity_study  # noqa: E402
from calion.run.workflow import run_workflow  # noqa: E402


DEFAULT_CONFIG = "configs/paper/L2_simplified_dispatch.yaml"
DEFAULT_OUTPUT = ROOT / "outputs" / "paper_uncertainty"


@dataclass
class ScenarioSpec:
    """Named combined-uncertainty scenario."""

    name: str
    description: str
    overrides: dict[str, Any]


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dictionaries without modifying inputs."""
    result = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _extract_active_result(workflow) -> Any | None:
    return workflow.mpc_result or workflow.rh_result or workflow.pf_result


def _extract_metrics(active_result: Any) -> dict[str, float]:
    """Extract a stable KPI subset for scenario comparison."""
    costs = active_result.costs or {}
    summary = active_result.summary or {}
    objective_section = summary.get("objective", {}) if isinstance(summary.get("objective"), dict) else {}
    grid_section = summary.get("grid", {}) if isinstance(summary.get("grid"), dict) else {}

    objective = costs.get("objective.OBJ_value_EUR")
    if objective is None:
        objective = objective_section.get("OBJ_value_EUR")
    if objective is None:
        objective = (
            float(costs.get("objective.Grid_net_cost_EUR", 0.0))
            + float(costs.get("objective.Fuel_cost_EUR", 0.0))
            + float(costs.get("objective.Dump_cost_EUR", 0.0))
            + float(costs.get("objective.CO2_cost_EUR", 0.0))
            + float(costs.get("objective.Demand_charge_cost_EUR", 0.0))
            + float(costs.get("objective.Capex_cost_EUR", 0.0))
            + float(costs.get("objective.Activation_cost_EUR", 0.0))
            + float(costs.get("objective.Tie_breaker_cost_EUR", 0.0))
            + float(costs.get("objective.Storage_installation_cost_EUR", 0.0))
        )

    return {
        "objective_eur": float(objective or 0.0),
        "grid_cost_eur": float(costs.get("objective.Grid_net_cost_EUR", objective_section.get("Grid_net_cost_EUR", 0.0))),
        "fuel_cost_eur": float(costs.get("objective.Fuel_cost_EUR", objective_section.get("Fuel_cost_EUR", 0.0))),
        "co2_cost_eur": float(costs.get("objective.CO2_cost_EUR", objective_section.get("CO2_cost_EUR", 0.0))),
        "demand_charge_cost_eur": float(costs.get("objective.Demand_charge_cost_EUR", objective_section.get("Demand_charge_cost_EUR", 0.0))),
        "capex_cost_eur": float(costs.get("objective.Capex_cost_EUR", objective_section.get("Capex_cost_EUR", 0.0))),
        "activation_cost_eur": float(costs.get("objective.Activation_cost_EUR", objective_section.get("Activation_cost_EUR", 0.0))),
        "storage_installation_cost_eur": float(costs.get("objective.Storage_installation_cost_EUR", objective_section.get("Storage_installation_cost_EUR", 0.0))),
        "grid_import_mwh": float(grid_section.get("Energy_from_grid_MWh", summary.get("Energy_from_grid_MWh", 0.0))),
        "grid_peak_mw": float(objective_section.get("P_buy_peak_MW", summary.get("P_buy_peak_MW", 0.0))),
        "co2_total_t": float(grid_section.get("Total_CO2_emissions_t", summary.get("Total_CO2_emissions_t", 0.0))),
        "heat_demand_mwh": float(grid_section.get("Heat_demand_MWh", summary.get("Heat_demand_MWh", 0.0))),
    }


def create_paper_sensitivity_study() -> list[ParameterVariation]:
    """Create a paper-specific uncertainty set."""
    return [
        ParameterVariation(
            param_path="costs.co2_price_eur_per_t",
            base_value=100.0,
            variations=[0.5, 0.75, 1.0, 1.25, 1.5],
            variation_type="multiplicative",
            description="CO2 price",
            units="EUR/t",
        ),
        ParameterVariation(
            param_path="fuels.gas.price_eur_mwh",
            base_value=45.0,
            variations=[0.8, 0.9, 1.0, 1.1, 1.2],
            variation_type="multiplicative",
            description="Natural gas price",
            units="EUR/MWh",
        ),
        ParameterVariation(
            param_path="grid.demand_charge_eur_per_mw_y",
            base_value=50000.0,
            variations=[0.75, 1.0, 1.25],
            variation_type="multiplicative",
            description="Demand charge",
            units="EUR/MW/year",
        ),
    ]


def create_paper_scenarios() -> list[ScenarioSpec]:
    """Create a compact publication-ready scenario matrix."""
    return [
        ScenarioSpec(
            name="baseline",
            description="Reference configuration",
            overrides={},
        ),
        ScenarioSpec(
            name="market_low",
            description="Low energy and carbon price environment",
            overrides={
                "fuels": {"gas": {"price_eur_mwh": 36.0}},
                "costs": {"co2_price_eur_per_t": 50.0},
            },
        ),
        ScenarioSpec(
            name="market_high",
            description="High energy and carbon price environment",
            overrides={
                "fuels": {"gas": {"price_eur_mwh": 54.0}},
                "costs": {"co2_price_eur_per_t": 150.0},
            },
        ),
        ScenarioSpec(
            name="grid_favorable",
            description="Favorable electrification economics",
            overrides={
                "grid": {"demand_charge_eur_per_mw_y": 37500.0},
            },
        ),
        ScenarioSpec(
            name="grid_unfavorable",
            description="Unfavorable electrification economics",
            overrides={
                "grid": {"demand_charge_eur_per_mw_y": 62500.0},
            },
        ),
        ScenarioSpec(
            name="co2_relaxed",
            description="Reduced carbon price pressure",
            overrides={
                "costs": {"co2_price_eur_per_t": 60.0},
            },
        ),
        ScenarioSpec(
            name="co2_stringent",
            description="Stringent carbon price pressure",
            overrides={
                "costs": {"co2_price_eur_per_t": 180.0},
            },
        ),
    ]


def run_named_scenarios(
    config_paths: list[str],
    output_dir: Path,
    scenarios: list[ScenarioSpec] | None = None,
) -> dict[str, Any]:
    """Run named combined-uncertainty scenarios and export summaries."""
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios = scenarios or create_paper_scenarios()

    rows: list[dict[str, Any]] = []
    baseline_obj: float | None = None
    baseline_co2: float | None = None

    for spec in scenarios:
        workflow = run_workflow(config_paths, overrides=spec.overrides or None)
        active_result = _extract_active_result(workflow)
        if active_result is None:
            rows.append({
                "scenario": spec.name,
                "description": spec.description,
                "status": "no_result",
            })
            continue

        metrics = _extract_metrics(active_result)
        status = str((active_result.solver or {}).get("termination_condition", "unknown"))
        row = {
            "scenario": spec.name,
            "description": spec.description,
            "status": status,
            **metrics,
        }

        if spec.name == "baseline":
            baseline_obj = metrics["objective_eur"]
            baseline_co2 = metrics["co2_total_t"]

        rows.append(row)

    for row in rows:
        if baseline_obj and isinstance(row.get("objective_eur"), (int, float)):
            row["delta_objective_pct_vs_baseline"] = (
                (float(row["objective_eur"]) - baseline_obj) / baseline_obj * 100.0
            )
        else:
            row["delta_objective_pct_vs_baseline"] = None

        if baseline_co2 and isinstance(row.get("co2_total_t"), (int, float)):
            row["delta_co2_pct_vs_baseline"] = (
                (float(row["co2_total_t"]) - baseline_co2) / baseline_co2 * 100.0
            )
        else:
            row["delta_co2_pct_vs_baseline"] = None

    json_path = output_dir / "scenario_summary.json"
    csv_path = output_dir / "scenario_summary.csv"
    md_path = output_dir / "scenario_summary.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now().isoformat(),
                "config_paths": config_paths,
                "rows": rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    fieldnames = [
        "scenario",
        "description",
        "status",
        "objective_eur",
        "delta_objective_pct_vs_baseline",
        "co2_total_t",
        "delta_co2_pct_vs_baseline",
        "grid_peak_mw",
        "grid_import_mwh",
        "grid_cost_eur",
        "fuel_cost_eur",
        "co2_cost_eur",
        "demand_charge_cost_eur",
        "capex_cost_eur",
        "activation_cost_eur",
        "storage_installation_cost_eur",
        "heat_demand_mwh",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Scenario Summary",
        "",
        "| Scenario | Status | Objective [EUR] | Delta vs baseline [%] | CO2 [t] | Delta CO2 [%] | Peak import [MW] |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {scenario} | {status} | {objective:.0f} | {delta_obj} | {co2:.1f} | {delta_co2} | {peak:.2f} |".format(
                scenario=row.get("scenario", ""),
                status=row.get("status", ""),
                objective=float(row.get("objective_eur", 0.0) or 0.0),
                delta_obj=(
                    f"{row['delta_objective_pct_vs_baseline']:+.2f}"
                    if isinstance(row.get("delta_objective_pct_vs_baseline"), (int, float))
                    else "n/a"
                ),
                co2=float(row.get("co2_total_t", 0.0) or 0.0),
                delta_co2=(
                    f"{row['delta_co2_pct_vs_baseline']:+.2f}"
                    if isinstance(row.get("delta_co2_pct_vs_baseline"), (int, float))
                    else "n/a"
                ),
                peak=float(row.get("grid_peak_mw", 0.0) or 0.0),
            )
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "rows": rows,
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(md_path),
    }


def run_co2_resolution_baseline(config_paths: list[str], output_dir: Path) -> dict[str, str] | None:
    """Run CO2 resolution analysis for the baseline scenario if data are available."""
    output_dir.mkdir(parents=True, exist_ok=True)
    workflow = run_workflow(config_paths)
    active_result = _extract_active_result(workflow)
    if active_result is None:
        return None

    analysis = analyze_from_result(active_result, dt_h=float(workflow.config.get("run", {}).get("dt_h", 1.0)))
    if analysis is None:
        return None

    summary_df = analysis.summary_table()
    report = create_comparison_report(analysis)

    csv_path = output_dir / "co2_resolution_summary.csv"
    txt_path = output_dir / "co2_resolution_report.txt"
    summary_df.to_csv(csv_path, index=False)
    txt_path.write_text(report, encoding="utf-8")

    return {
        "csv": str(csv_path),
        "report": str(txt_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run paper-oriented uncertainty studies.")
    parser.add_argument(
        "--config",
        dest="configs",
        action="append",
        default=[],
        help="Config path to include. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT),
        help="Output directory for all generated artifacts.",
    )
    parser.add_argument(
        "--skip-sensitivity",
        action="store_true",
        help="Skip one-at-a-time sensitivity analysis.",
    )
    parser.add_argument(
        "--skip-scenarios",
        action="store_true",
        help="Skip named scenario matrix.",
    )
    parser.add_argument(
        "--skip-co2-resolution",
        action="store_true",
        help="Skip CO2 temporal-resolution analysis.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config_paths = args.configs or [DEFAULT_CONFIG]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "config_paths": config_paths,
        "outputs": {},
    }

    if not args.skip_sensitivity:
        sensitivity_dir = output_dir / "sensitivity"
        variations = create_paper_sensitivity_study()
        sensitivity_result = run_full_sensitivity_study(
            base_configs=config_paths,
            variations=variations,
            output_dir=str(sensitivity_dir),
            generate_plots=True,
            generate_latex=True,
            parallel=False,
        )
        manifest["outputs"]["sensitivity"] = sensitivity_result.generated_files

    if not args.skip_scenarios:
        scenario_dir = output_dir / "scenarios"
        manifest["outputs"]["scenarios"] = run_named_scenarios(
            config_paths=config_paths,
            output_dir=scenario_dir,
        )

    if not args.skip_co2_resolution:
        co2_dir = output_dir / "co2_resolution"
        co2_outputs = run_co2_resolution_baseline(config_paths=config_paths, output_dir=co2_dir)
        if co2_outputs is not None:
            manifest["outputs"]["co2_resolution"] = co2_outputs

    manifest_path = output_dir / "uncertainty_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("=" * 72)
    print("UNCERTAINTY STUDY COMPLETE")
    print("=" * 72)
    print(f"Output directory: {output_dir}")
    print(f"Manifest: {manifest_path}")
    for section, payload in manifest["outputs"].items():
        print(f"- {section}: {payload}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
