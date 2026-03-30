from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple

import pytest

from calion.io.loader import load_input_excel
from calion.run import rolling_horizon as rh
from calion.utils.xlsx import write_simple_xlsx

FIXTURE_DIR = Path(__file__).parent / "data"
INPUT_CSV = FIXTURE_DIR / "regression_input.csv"
REFERENCE_PATH = FIXTURE_DIR / "regression_reference.json"
CONFIG_PATHS = [
    "configs/base.yaml",
    "configs/tech_catalog.yaml",
    "configs/sites/default.site.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/pf_then_rh.workflow.scenario.yaml",
]

_CONFIGS_AVAILABLE = all(
    Path(p).exists() or (Path(__file__).parent.parent / p).exists()
    for p in CONFIG_PATHS
    if p != "configs/base.yaml"  # base.yaml is always created
)


@pytest.fixture(scope="module")
def reference() -> Dict:
    return json.loads(REFERENCE_PATH.read_text())


def _load_fixture_rows(csv_path: Path) -> Tuple[Sequence[str], Sequence[Sequence[object]]]:
    with csv_path.open(newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = []
        for row in reader:
            parsed = [datetime.fromisoformat(row[0])]
            parsed.extend(float(cell) if cell else None for cell in row[1:])
            rows.append(parsed)
    return headers, rows


@pytest.fixture(scope="module")
def input_xlsx(tmp_path_factory) -> Path:
    headers, rows = _load_fixture_rows(INPUT_CSV)
    path = tmp_path_factory.mktemp("regression") / "regression_input.xlsx"
    write_simple_xlsx(path, headers, rows)
    return path


@pytest.fixture(scope="module")
def overrides(input_xlsx: Path) -> Dict:
    table = load_input_excel(str(input_xlsx), {"input_xlsx": str(input_xlsx)}, dt_hours=1.0)
    start = table.index[0].isoformat()
    end = table.index[-1].isoformat()
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


def _compare_dict_subset(actual: Dict, expected: Dict, keys: Iterable[str]) -> None:
    for key in keys:
        assert key in actual, f"Missing key {key} in actual output"
        assert key in expected, f"Missing key {key} in reference for {key}"
        assert actual[key] == pytest.approx(expected[key])


@pytest.mark.skipif(not _CONFIGS_AVAILABLE, reason="Integration config files not available")
def test_regression_against_reference(reference: Dict, overrides: Dict) -> None:
    result = rh.run_workflow(CONFIG_PATHS, overrides=overrides)

    assert list(result.plan.steps) == reference["plan"]

    # Design capacities from the PF step
    assert result.design is not None
    for hp_id, hp_ref in reference["pf_design"].items():
        assert hp_id in result.design.heat_pumps
        _compare_dict_subset(result.design.heat_pumps[hp_id], hp_ref, ["capacity_mw", "build_binary"])

    storage_ref = reference.get("storage")
    if storage_ref:
        assert result.design.storage is not None
        _compare_dict_subset(result.design.storage, storage_ref, ["capacity_mwh", "power_mw", "build_binary"])

    assert result.pf_result is not None
    pf_costs = reference["pf_costs"]
    _compare_dict_subset(
        result.pf_result.costs,
        pf_costs,
        [
            "objective.OBJ_value_EUR",
            "objective.P_buy_peak_MW",
            "grid.Energy_from_grid_MWh",
            "grid.Energy_to_grid_MWh",
            "grid.Heat_demand_MWh",
        ],
    )

    assert result.rh_result is not None
    rh_costs = reference.get("rh_costs", {})
    if rh_costs:
        _compare_dict_subset(
            result.rh_result.costs,
            rh_costs,
            ["objective.OBJ_value_EUR", "objective.P_buy_peak_MW", "grid.Energy_from_grid_MWh"],
        )

    series_tail = reference.get("series_tail", {})
    for col, expected_tail in series_tail.items():
        assert col in result.rh_result.series
        actual_tail = result.rh_result.series[col][-len(expected_tail) :]
        assert actual_tail == pytest.approx(expected_tail)
