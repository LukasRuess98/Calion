from __future__ import annotations

from pathlib import Path

import pytest

from energis.validation.stadtbach import run_stadtbach_reference

REFERENCE_PATH = Path(__file__).parent / "data/stadtbach_legacy_reference.json"


def test_stadtbach_reference_matches_legacy(tmp_path) -> None:
    output_csv = tmp_path / "stadtbach_table.csv"
    table, run, reference = run_stadtbach_reference(
        reference_path=REFERENCE_PATH, output_table=output_csv
    )

    assert reference["horizon"]["start"] == run.start.isoformat()
    assert reference["horizon"]["end"] == run.end.isoformat()

    # EnerGIS PF and RH runs should satisfy demand over the sampled horizon
    assert run.pf_metrics["grid.Heat_demand_MWh"] == pytest.approx(
        reference["legacy"]["grid.Heat_demand_MWh"]
    )
    assert run.rh_metrics["grid.Heat_demand_MWh"] == pytest.approx(
        reference["legacy"]["grid.Heat_demand_MWh"]
    )

    # The automated comparison table mirrors the legacy keys
    assert all(row.get("relative_error_pct") in (None, 0.0) for row in table)
    assert all(abs(row.get("delta", 0.0)) < 1e-6 for row in table)

    with output_csv.open() as f:
        header = f.readline().strip().split(",")
        rows = [dict(zip(header, line.strip().split(","))) for line in f if line.strip()]
    assert len(rows) == len(table)
    for csv_row, row in zip(rows, table):
        assert csv_row["metric"] == row["metric"]
