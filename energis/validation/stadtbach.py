from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from energis.io.loader import load_input_excel
from energis.run import rolling_horizon as rh

CONFIG_PATHS = [
    "configs/base.yaml",
    "configs/tech_catalog.yaml",
    "configs/sites/default.site.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/pf_then_rh.workflow.scenario.yaml",
]


@dataclass
class StadtbachRun:
    start: datetime
    end: datetime
    pf_metrics: Dict[str, float]
    rh_metrics: Dict[str, float]

    @property
    def horizon_hours(self) -> float:
        return (self.end - self.start) / timedelta(hours=1) + 1.0


_STADT_METRICS: Tuple[str, ...] = (
    "objective.OBJ_value_EUR",
    "grid.Energy_from_grid_MWh",
    "grid.Heat_demand_MWh",
)


def _metrics_subset(values: Dict[str, float], keys: Iterable[str]) -> Dict[str, float]:
    return {key: float(values.get(key, 0.0)) for key in keys}


def run_stadtbach_reference(
    input_xlsx: str | Path = "Import_Data.xlsx",
    reference_path: str | Path | None = None,
    output_table: str | Path | None = None,
) -> Tuple[List[Dict[str, float | None]], StadtbachRun, Dict]:
    """Run the Stadtbach reference horizon and compare to stored legacy metrics.

    Parameters
    ----------
    input_xlsx:
        Path to the Stadtbach input Excel sheet.
    reference_path:
        JSON file containing ``horizon.start``/``horizon.end`` and legacy metrics
        under ``legacy``.
    output_table:
        Optional path where the comparison table should be written as CSV.

    Returns
    -------
    table:
        Rows with ``metric``, ``legacy``, ``energis`` and ``relative_error_pct``.
    run_result:
        Captured PF/RH metrics for the EnerGIS run.
    reference:
        Parsed JSON reference content.
    """

    ref_path = Path(reference_path) if reference_path else None
    if ref_path and not ref_path.exists():
        raise FileNotFoundError(f"Missing reference file {ref_path}")

    reference = json.loads(ref_path.read_text()) if ref_path else {}
    horizon = reference.get("horizon", {})

    site_table = load_input_excel(str(input_xlsx), {"input_xlsx": str(input_xlsx)}, dt_hours=1.0)
    start_raw = horizon.get("start", site_table.index[0])
    start = datetime.fromisoformat(start_raw) if isinstance(start_raw, str) else start_raw

    end_raw = horizon.get("end")
    if end_raw is None:
        end = start + timedelta(hours=23)
    else:
        end = datetime.fromisoformat(end_raw) if isinstance(end_raw, str) else end_raw

    overrides = {
        "site": {"input_xlsx": str(input_xlsx), "year_target": None},
        "scenario": {
            "horizon": {"start": start.isoformat(), "end": end.isoformat()},
            "rolling_horizon": {
                "heat_horizon_hours": 24.0,
                "step_hours": 24.0,
                "terminal_policy": "free",
            },
        },
        "run": {"solver": "glpk"},
    }

    result = rh.run_workflow(CONFIG_PATHS, overrides=overrides)

    pf_metrics = _metrics_subset(result.pf_result.costs, _STADT_METRICS)
    rh_metrics = _metrics_subset(result.rh_result.costs, _STADT_METRICS)

    run = StadtbachRun(start=start, end=end, pf_metrics=pf_metrics, rh_metrics=rh_metrics)

    legacy_metrics = _metrics_subset(reference.get("legacy", {}), _STADT_METRICS)
    comparison_rows: List[Dict[str, float | None]] = []
    for metric in _STADT_METRICS:
        legacy_val = legacy_metrics.get(metric)
        energis_val = rh_metrics.get(metric)
        delta = energis_val - legacy_val if legacy_val is not None else energis_val
        rel_error = None
        if legacy_val not in (None, 0.0):
            rel_error = delta / legacy_val * 100.0
        comparison_rows.append(
            {
                "metric": metric,
                "legacy": legacy_val,
                "energis": energis_val,
                "delta": delta,
                "relative_error_pct": rel_error,
            }
        )

    if output_table:
        output_path = Path(output_table)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["metric", "legacy", "energis", "delta", "relative_error_pct"]
            )
            writer.writeheader()
            writer.writerows(comparison_rows)

    return comparison_rows, run, reference
