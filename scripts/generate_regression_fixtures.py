"""Generate regression fixtures for the EnerGIS rolling-horizon workflow.

This script is intended to be run manually to refresh the small input sample and
its reference outputs that power ``tests/test_regression.py``.  By default it
creates a 12-hour slice from ``Import_Data.xlsx`` (2023-01-01 00:00 → 2023-01-01
11:00) and stores both the fixture CSV/Excel data and the computed reference
JSON in ``tests/data``.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Sequence

from energis.io.loader import load_input_excel
from energis.run import rolling_horizon
from energis.utils.xlsx import write_simple_xlsx

DEFAULT_CONFIGS: Sequence[str] = (
    "configs/base.yaml",
    "configs/tech_catalog.yaml",
    "configs/sites/default.site.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/pf_then_rh.workflow.scenario.yaml",
)


def _build_rows(table):
    headers = [
        "Datum",
        "Day_Ahead_Price €/MWh",
        "Wärmebedarf MW",
        "CO2_consumption_based kgCO2/MWh",
        "WRG1Q MW",
        "WRG1_T °C",
        "WRG2Q MW",
        "WRG2_T °C",
        "WRG3Q MW",
        "WRG3_T °C",
        "WRG4Q MW",
        "WRG4_T °C",
    ]

    rows = []
    for idx in range(len(table.index)):
        rows.append(
            [
                table.index[idx],
                table.data["strompreis_EUR_MWh"][idx],
                table.data["waermebedarf_MWth"][idx],
                table.data["grid_co2_kg_MWh"][idx],
                table.data.get("WRG1_Q_cap", [None])[idx],
                table.data.get("WRG1_T_K", [None])[idx] - 273.15,
                table.data.get("WRG2_Q_cap", [None])[idx],
                table.data.get("WRG2_T_K", [None])[idx] - 273.15,
                table.data.get("WRG3_Q_cap", [None])[idx],
                table.data.get("WRG3_T_K", [None])[idx] - 273.15,
                table.data.get("WRG4_Q_cap", [None])[idx],
                table.data.get("WRG4_T_K", [None])[idx] - 273.15,
            ]
        )

    return headers, rows


def _write_fixture_xlsx(table, target_path: Path) -> None:
    headers, rows = _build_rows(table)
    write_simple_xlsx(str(target_path), headers, rows)


def _write_fixture_csv(table, target_path: Path) -> None:
    headers, rows = _build_rows(table)
    target_path.write_text("\n".join(
        ",".join(str(value) for value in row) for row in [headers, *rows]
    ))


def _build_overrides(input_xlsx: Path, start: str, end: str) -> Dict:
    return {
        "site": {
            "input_xlsx": str(input_xlsx),
            "year_target": None,
        },
        "scenario": {
            "horizon": {"start": start, "end": end},
            "rolling_horizon": {
                "heat_horizon_hours": 6.0,
                "step_hours": 3.0,
                "terminal_policy": "free",
            },
        },
        "run": {"solver": "glpk"},
    }


def _write_reference(result: rolling_horizon.WorkflowResult, target: Path) -> None:
    reference = {
        "plan": list(result.plan.steps),
        "pf_design": result.design.heat_pumps if result.design else {},
        "storage": result.design.storage if result.design else {},
        "pf_costs": result.pf_result.costs if result.pf_result else {},
        "rh_costs": result.rh_result.costs if result.rh_result else {},
        "series_tail": {},
    }
    if result.rh_result:
        for key in ("TES_SOC_MWh", "P_buy_MW", "P_sell_MW"):
            if key in result.rh_result.series:
                reference["series_tail"][key] = result.rh_result.series[key][-3:]

    target.write_text(json.dumps(reference, indent=2, default=float))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-xlsx",
        default="Import_Data.xlsx",
        help="Path to the original input Excel file",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("tests/data"),
        type=Path,
        help="Directory to store the fixture data",
    )
    parser.add_argument(
        "--start",
        default="2023-01-01T00:00:00",
        help="Start timestamp for the sliced horizon (ISO format)",
    )
    parser.add_argument(
        "--hours",
        default=12,
        type=int,
        help="Number of hourly steps to extract",
    )
    parser.add_argument(
        "--configs",
        nargs="*",
        default=list(DEFAULT_CONFIGS),
        help="Config files to feed into the workflow",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    site_cfg = {
        "input_xlsx": args.input_xlsx,
        "year_target": 2023,
        "columns": {},
    }
    raw_table = load_input_excel(str(args.input_xlsx), site_cfg, dt_hours=1.0)
    start_ts = datetime.fromisoformat(str(args.start))
    try:
        start_idx = raw_table.index.index(start_ts)
    except ValueError as exc:  # pragma: no cover - defensive guard for manual runs
        raise SystemExit(f"Start timestamp {start_ts} not found in input") from exc

    end_idx = min(start_idx + int(args.hours), len(raw_table.index))
    sliced = raw_table.copy()
    sliced.index = raw_table.index[start_idx:end_idx]
    sliced.data = {k: v[start_idx:end_idx] for k, v in raw_table.data.items()}

    input_fixture_xlsx = output_dir / "regression_input.xlsx"
    _write_fixture_xlsx(sliced, input_fixture_xlsx)
    input_fixture_csv = output_dir / "regression_input.csv"
    _write_fixture_csv(sliced, input_fixture_csv)

    start_iso = sliced.index[0].isoformat()
    end_iso = sliced.index[-1].isoformat()
    overrides = _build_overrides(input_fixture_xlsx, start_iso, end_iso)

    result = rolling_horizon.run_workflow(list(args.configs), overrides=overrides)

    reference_path = output_dir / "regression_reference.json"
    _write_reference(result, reference_path)

    print(f"Wrote fixture data to {input_fixture_csv}")
    print(f"Wrote fixture data to {input_fixture_xlsx}")
    print(f"Wrote reference metrics to {reference_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
