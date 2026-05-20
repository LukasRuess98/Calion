from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from scripts.paper import extract_artefacts as ea


def _mock_to_parquet(monkeypatch):
    def _fake_to_parquet(self, path, index=False, **kwargs):
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.to_csv(index=index), encoding="utf-8")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _fake_to_parquet)


def _make_workflow(export_dir: Path):
    pf_result = SimpleNamespace(solver={"export_dir": str(export_dir)})
    return SimpleNamespace(pf_result=pf_result)


def test_season_mapping_boundary_months():
    assert ea._season_of_timestamp("2025-03-01 00:00:00") == "transition"
    assert ea._season_of_timestamp("2025-06-01 00:00:00") == "summer"
    assert ea._season_of_timestamp("2025-09-01 00:00:00") == "transition"
    assert ea._season_of_timestamp("2025-12-01 00:00:00") == "winter"


def test_write_nodes_data_computes_delta_and_seasonal(tmp_path, monkeypatch):
    _mock_to_parquet(monkeypatch)

    export_dir = tmp_path / "export"
    nodes_dir = export_dir / "thermal_network" / "nodes"
    nodes_dir.mkdir(parents=True)

    summary_payload = [
        {"node_id": "j_1", "type": "source"},
        {"node_id": "j_2", "type": "consumer"},
    ]
    (nodes_dir / "nodes_summary.json").write_text(json.dumps(summary_payload), encoding="utf-8")

    wide = pd.DataFrame(
        {
            "j_1_T_supply": [80.0, 82.0, 84.0, 86.0],
            "j_1_T_return": [60.0, 61.0, 62.0, 63.0],
            "j_1_P": [5.0, 5.0, 5.0, 5.0],
            "j_1_Q_demand": [1.0, 2.0, 3.0, 4.0],
            "j_2_T_supply": [78.0, 79.0, 80.0, 81.0],
            "j_2_T_return": [58.0, 59.0, 60.0, 61.0],
            "j_2_P": [4.8, 4.9, 5.0, 5.1],
            "j_2_Q_demand": [0.8, 0.9, 1.0, 1.1],
        },
        index=[
            "2025-03-01 00:00:00",
            "2025-06-01 00:00:00",
            "2025-09-01 00:00:00",
            "2025-12-01 00:00:00",
        ],
    )
    wide.to_csv(nodes_dir / "nodes_timeseries.csv", sep=";")

    outdir = tmp_path / "out"
    outdir.mkdir(parents=True)
    workflow = _make_workflow(export_dir)

    nodes_summary, nodes_seasonal, nodes_state = ea.write_nodes_data(
        outdir=outdir,
        run_id="L3plus",
        workflow=workflow,
        dt_h=1.0,
    )

    assert not nodes_state.empty
    assert set(nodes_state.columns) == {
        "timestamp",
        "node_id",
        "T_supply_c",
        "T_return_c",
        "delta_t_c",
        "P_bar",
        "Q_demand_mw",
    }

    s_j1 = nodes_summary.set_index("node_id").loc["j_1"]
    assert abs(float(s_j1["T_supply_avg_c"]) - 83.0) < 1e-9
    assert abs(float(s_j1["T_return_avg_c"]) - 61.5) < 1e-9
    assert abs(float(s_j1["delta_t_avg_c"]) - 21.5) < 1e-9
    assert abs(float(s_j1["Q_demand_total_mwh"]) - 10.0) < 1e-9

    transition_j1 = nodes_seasonal[
        (nodes_seasonal["node_id"] == "j_1") & (nodes_seasonal["season"].astype(str) == "transition")
    ].iloc[0]
    assert abs(float(transition_j1["T_supply_avg_c"]) - 82.0) < 1e-9
    assert abs(float(transition_j1["T_return_avg_c"]) - 61.0) < 1e-9
    assert abs(float(transition_j1["delta_t_avg_c"]) - 21.0) < 1e-9
    assert abs(float(transition_j1["Q_demand_total_mwh"]) - 4.0) < 1e-9

    assert (outdir / "nodes_summary.csv").exists()
    assert (outdir / "nodes_seasonal.csv").exists()
    assert (outdir / "nodes_state_hourly.parquet").exists()


def test_write_nodes_data_missing_input_writes_empty_artefacts(tmp_path, monkeypatch, capsys):
    _mock_to_parquet(monkeypatch)

    export_dir = tmp_path / "export"
    export_dir.mkdir(parents=True)
    outdir = tmp_path / "out"
    outdir.mkdir(parents=True)
    workflow = _make_workflow(export_dir)

    nodes_summary, nodes_seasonal, nodes_state = ea.write_nodes_data(
        outdir=outdir,
        run_id="L3plus",
        workflow=workflow,
        dt_h=1.0,
    )

    captured = capsys.readouterr()
    assert "node exports missing" in captured.out
    assert nodes_summary.empty
    assert nodes_seasonal.empty
    assert nodes_state.empty

    summary_csv = pd.read_csv(outdir / "nodes_summary.csv")
    seasonal_csv = pd.read_csv(outdir / "nodes_seasonal.csv")

    assert list(summary_csv.columns) == [
        "node_id",
        "node_type",
        "T_supply_avg_c",
        "T_return_avg_c",
        "delta_t_avg_c",
        "Q_demand_total_mwh",
        "P_avg_bar",
    ]
    assert list(seasonal_csv.columns) == [
        "season",
        "node_id",
        "node_type",
        "T_supply_avg_c",
        "T_return_avg_c",
        "delta_t_avg_c",
        "Q_demand_total_mwh",
        "P_avg_bar",
    ]
