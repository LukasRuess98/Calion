from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools import figgen


def _mock_save(monkeypatch):
    saved: list[str] = []

    def _fake_save(fig, out_dir: Path, stem: str, plt):
        saved.append(stem)
        plt.close(fig)

    monkeypatch.setattr(figgen, "_save_fig", _fake_save)
    return saved


def test_extended_figures_registered():
    for fid in ("F9", "F10", "F11", "F12", "F13"):
        assert fid in figgen.FIGURES


def test_extended_figures_smoke(monkeypatch, tmp_path):
    saved = _mock_save(monkeypatch)

    summary = pd.DataFrame(
        [
            {
                "node_id": "j_1",
                "node_type": "source",
                "T_supply_avg_c": 86.0,
                "T_return_avg_c": 62.0,
                "delta_t_avg_c": 24.0,
                "Q_demand_total_mwh": 200.0,
                "P_avg_bar": 5.2,
            },
            {
                "node_id": "j_12",
                "node_type": "junction",
                "T_supply_avg_c": 83.0,
                "T_return_avg_c": 60.0,
                "delta_t_avg_c": 23.0,
                "Q_demand_total_mwh": 150.0,
                "P_avg_bar": 4.9,
            },
            {
                "node_id": "j_15",
                "node_type": "consumer",
                "T_supply_avg_c": 79.0,
                "T_return_avg_c": 57.0,
                "delta_t_avg_c": 22.0,
                "Q_demand_total_mwh": 120.0,
                "P_avg_bar": 4.5,
            },
        ]
    )

    seasonal = pd.DataFrame(
        [
            {"season": "winter", "node_id": "j_1", "node_type": "source", "T_supply_avg_c": 87.0, "T_return_avg_c": 62.0, "delta_t_avg_c": 25.0, "Q_demand_total_mwh": 90.0, "P_avg_bar": 5.3},
            {"season": "transition", "node_id": "j_1", "node_type": "source", "T_supply_avg_c": 85.0, "T_return_avg_c": 61.0, "delta_t_avg_c": 24.0, "Q_demand_total_mwh": 70.0, "P_avg_bar": 5.2},
            {"season": "summer", "node_id": "j_1", "node_type": "source", "T_supply_avg_c": 82.0, "T_return_avg_c": 60.0, "delta_t_avg_c": 22.0, "Q_demand_total_mwh": 40.0, "P_avg_bar": 5.0},
            {"season": "winter", "node_id": "j_12", "node_type": "junction", "T_supply_avg_c": 84.0, "T_return_avg_c": 60.0, "delta_t_avg_c": 24.0, "Q_demand_total_mwh": 70.0, "P_avg_bar": 5.0},
            {"season": "transition", "node_id": "j_12", "node_type": "junction", "T_supply_avg_c": 82.0, "T_return_avg_c": 59.0, "delta_t_avg_c": 23.0, "Q_demand_total_mwh": 50.0, "P_avg_bar": 4.9},
            {"season": "summer", "node_id": "j_12", "node_type": "junction", "T_supply_avg_c": 80.0, "T_return_avg_c": 58.0, "delta_t_avg_c": 22.0, "Q_demand_total_mwh": 30.0, "P_avg_bar": 4.8},
            {"season": "winter", "node_id": "j_15", "node_type": "consumer", "T_supply_avg_c": 80.0, "T_return_avg_c": 57.0, "delta_t_avg_c": 23.0, "Q_demand_total_mwh": 55.0, "P_avg_bar": 4.6},
            {"season": "transition", "node_id": "j_15", "node_type": "consumer", "T_supply_avg_c": 78.0, "T_return_avg_c": 56.0, "delta_t_avg_c": 22.0, "Q_demand_total_mwh": 40.0, "P_avg_bar": 4.5},
            {"season": "summer", "node_id": "j_15", "node_type": "consumer", "T_supply_avg_c": 76.0, "T_return_avg_c": 55.0, "delta_t_avg_c": 21.0, "Q_demand_total_mwh": 25.0, "P_avg_bar": 4.4},
        ]
    )

    idx = pd.date_range("2025-01-01", periods=48, freq="h")
    dispatch = pd.DataFrame(
        {
            "Q_demand_total_MW": [20.0 + (i % 8) for i in range(len(idx))],
            "P_pump_MW": [0.8 + 0.05 * (i % 6) for i in range(len(idx))],
            "Q_loss_total_MW": [1.2 + 0.03 * (i % 7) for i in range(len(idx))],
            "Q_chp_MW": [12.0 for _ in idx],
            "Q_biomass_MW": [4.0 for _ in idx],
            "Q_gasboiler_MW": [2.5 for _ in idx],
            "Q_hp_total_MW": [5.0 for _ in idx],
            "Q_ek_MW": [1.0 for _ in idx],
            "Q_storage_charge_MW": [0.5 for _ in idx],
            "Q_storage_discharge_MW": [0.7 for _ in idx],
        },
        index=idx,
    )

    runs = tmp_path / "paper_runs"
    (runs / "L3plus").mkdir(parents=True)
    (runs / "L3plus" / "dispatch_hourly.csv").write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(figgen, "RUNS", runs)

    monkeypatch.setattr(figgen, "_pick_node_run", lambda: "L3plus")
    monkeypatch.setattr(figgen, "_load_nodes_summary", lambda rid: summary.copy())
    monkeypatch.setattr(figgen, "_load_nodes_seasonal", lambda rid: seasonal.copy())

    def _load_dispatch(rid: str):
        if rid in {"L1", "L2", "L3", "L3plus"}:
            return dispatch.copy()
        return None

    monkeypatch.setattr(figgen, "_load_dispatch", _load_dispatch)

    outdir = tmp_path / "figures"
    outdir.mkdir(parents=True)

    figgen.fig_F9(outdir)
    figgen.fig_F10(outdir)
    figgen.fig_F11(outdir)
    figgen.fig_F12(outdir)
    figgen.fig_F13(outdir)

    assert "F9_node_averages" in saved
    assert "F10_node_topology_heatmap" in saved
    assert "F11_critical_path_profile" in saved
    assert "F12_duration_curves_extended" in saved
    assert "F13_energy_sankey" in saved
