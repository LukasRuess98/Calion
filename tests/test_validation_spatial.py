from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import tools.validation_spatial as vs

from tools.validation_spatial import (
    BC_NODE,
    CALIBRATION_NODES,
    EDGE_TO_PIPE,
    NODE_CONSUMERS,
    PIPE_CATALOG,
    compute_kpi_with_uncertainty,
    compute_path_lengths,
    compute_pipe_flows_measured,
    extract_optimization_node_temps,
    generate_validation_table_latex,
    get_downstream_nodes,
    get_measured_node_temperatures,
    get_measured_return_temperatures,
    reconstruct_node_temperatures_L3,
    calibrate_u_values_independent,
    validate_spatial_temperature_profile,
    run_spatial_validation,
)


def _hist_base(n: int = 96, start: str = "2025-01-01 00:00:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="h")
    df = pd.DataFrame(index=idx)
    for v in range(1, 28):
        df[f"V_{v}_demand_MWth"] = 0.05 + 0.002 * v
        df[f"V_{v}_flow_temp"] = 84.0 - 0.03 * v
        df[f"V_{v}_return_temp"] = 56.0 - 0.02 * v
        df[f"V_{v}_flow_rate"] = 4.0 + 0.1 * v
    return df


def test_compute_path_lengths_j15_and_count():
    lengths = compute_path_lengths()
    assert lengths["j_15"] == 2125.0
    assert len(lengths) == 15


def test_get_downstream_nodes_j3_contains_all_expected():
    ds = get_downstream_nodes("j_3")
    expected = {
        "j_3", "j_4", "j_5", "j_6", "j_7", "j_8",
        "j_9", "j_10", "j_11", "j_12", "j_13", "j_14", "j_15",
    }
    assert expected.issubset(ds)
    assert BC_NODE not in ds


def test_get_measured_node_temperatures_uses_max_and_spread():
    hist = _hist_base()
    # Node j_4 has V_4..V_7; force high spread and known max channel
    hist["V_4_flow_temp"] = 78.0
    hist["V_5_flow_temp"] = 80.0
    hist["V_6_flow_temp"] = 83.0
    hist["V_7_flow_temp"] = 81.0

    node_t, node_spread = get_measured_node_temperatures(hist, min_valid_hours=24)
    assert "j_4" in node_t
    assert np.allclose(node_t["j_4"].to_numpy(), hist["V_6_flow_temp"].to_numpy())
    assert node_spread["j_4"] > 2.0


def test_compute_pipe_flows_measured_bounds_and_count():
    hist = _hist_base()
    node_t, _ = get_measured_node_temperatures(hist, min_valid_hours=24)
    node_r = get_measured_return_temperatures(hist, min_valid_hours=24)
    flows = compute_pipe_flows_measured(hist, node_t, node_r, bc_temp=86.0)

    assert set(flows.keys()) == set(PIPE_CATALOG.keys())
    for series in flows.values():
        assert float(series.min()) >= 0.01 - 1e-9
        assert float(series.max()) <= 100.0 + 1e-9


def test_reconstruct_node_temperatures_monotonic_by_edge_mean():
    hist = _hist_base()
    node_t, _ = get_measured_node_temperatures(hist, min_valid_hours=24)
    node_r = get_measured_return_temperatures(hist, min_valid_hours=24)
    recon = reconstruct_node_temperatures_L3(
        hist=hist,
        bc_temp=86.0,
        u_multipliers={k: 1.0 for k in PIPE_CATALOG},
        node_temps_meas=node_t,
        node_ret_temps=node_r,
    )
    for (parent, child), _pipe in EDGE_TO_PIPE.items():
        p_mean = float(recon[parent].mean())
        c_mean = float(recon[child].mean())
        assert c_mean <= p_mean + 1e-6


def test_calibration_independent_only_updates_calibration_branch_pipes():
    hist = _hist_base(n=240)
    node_t, _ = get_measured_node_temperatures(hist, min_valid_hours=24)
    node_r = get_measured_return_temperatures(hist, min_valid_hours=24)

    # Inject bias at calibration nodes to trigger updates
    node_t_mod = dict(node_t)
    for n in CALIBRATION_NODES:
        if n in node_t_mod:
            node_t_mod[n] = node_t_mod[n] - 2.0

    u = calibrate_u_values_independent(
        hist_train=hist,
        node_temps_meas=node_t_mod,
        node_ret_temps=node_r,
        bc_temp=86.0,
        max_iterations=3,
    )
    changed = {k for k, v in u.items() if abs(v - 1.0) > 1e-6}
    assert changed.issubset({"j5_to_j6", "j5_to_j7", "j7_to_j8", "j13_to_j14"})


def test_compute_kpi_with_uncertainty_deterministic():
    idx = pd.date_range("2025-01-01", periods=120, freq="h")
    t_meas = pd.Series(80.0 + 0.2 * np.sin(np.arange(120) / 5.0), index=idx)
    t_sim = t_meas + 1.0
    k = compute_kpi_with_uncertainty(t_meas, t_sim, n_bootstrap=300, seed=42)
    assert abs(k["MAE_C"] - 1.0) < 1e-9
    assert k["MAE_CI95_lower_C"] <= k["MAE_C"] <= k["MAE_CI95_upper_C"]
    # strict rule is MAE > 2*unc; here MAE == 1.0 and unc=0.5 -> not significant
    assert k["significant"] is False


def test_extract_optimization_node_temps_nodes_timeseries_integer_timestamp_mapping(tmp_path: Path):
    run_dir = tmp_path / "run_l3plus"
    run_dir.mkdir(parents=True)

    # Integer timestep index in node export
    df_nodes = pd.DataFrame(
        {
            "j_1_T_supply": [86.0, 86.1, 86.2],
            "j_2_T_supply": [85.5, 85.6, 85.7],
        },
        index=[1, 2, 3],
    )
    df_nodes.to_csv(run_dir / "nodes_timeseries.csv", sep=";")

    df_dispatch = pd.DataFrame(
        {
            "timestamp": [
                "2025-01-01 00:00:00",
                "2025-01-01 01:00:00",
                "2025-01-01 02:00:00",
            ],
            "Q_demand_total_MW": [1.0, 1.0, 1.0],
        }
    )
    df_dispatch.to_csv(run_dir / "dispatch_hourly.csv", index=False)

    out = extract_optimization_node_temps(run_dir, "L3+")
    assert out is not None
    assert "j_2" in out
    assert isinstance(out["j_2"].index, pd.DatetimeIndex)
    assert str(out["j_2"].index[0]) == "2025-01-01 00:00:00"


def test_validate_spatial_temperature_profile_summary_contains_val_stats():
    hist = _hist_base(n=240)
    node_t, node_spreads = get_measured_node_temperatures(hist, min_valid_hours=24)

    # Build synthetic simulated level from measured + constant offset
    sim_l3 = {n: s + 0.4 for n, s in node_t.items()}
    report = validate_spatial_temperature_profile(
        hist=hist,
        bc_info={"mode": "constant", "mean_C": 86.0, "median_C": 86.0},
        u_multipliers={k: 1.0 for k in PIPE_CATALOG},
        model_levels={"L3": sim_l3},
        node_temps_meas=node_t,
        node_spreads=node_spreads,
        period="full",
        period_months=None,
    )
    assert report.node_results
    assert "L3" in report.summary
    assert abs(report.summary["L3"]["mean_MAE_all_C"] - 0.4) < 1e-3
    assert "mean_MAE_VAL_C" in report.summary["L3"]


def test_generate_validation_table_latex_contains_cal_mean_row(tmp_path: Path):
    hist = _hist_base(n=240)
    node_t, node_spreads = get_measured_node_temperatures(hist, min_valid_hours=24)
    sim_l3 = {n: s + 0.4 for n, s in node_t.items()}
    report = validate_spatial_temperature_profile(
        hist=hist,
        bc_info={"mode": "constant", "mean_C": 86.0, "median_C": 86.0},
        u_multipliers={k: 1.0 for k in PIPE_CATALOG},
        model_levels={"L3": sim_l3},
        node_temps_meas=node_t,
        node_spreads=node_spreads,
        period="test",
        period_months=None,
    )
    tex = generate_validation_table_latex(report, tmp_path, "spatial_validation_table.tex")
    assert "Mean (VAL nodes)" in tex
    assert "Mean (CAL nodes)" in tex
    assert "Mean (all nodes)" in tex


def test_run_spatial_validation_excludes_missing_extended_levels(monkeypatch, tmp_path: Path):
    hist = _hist_base(n=96)
    hist["V_1_flow_temp"] = 86.0

    monkeypatch.setattr(vs, "OUT_DIR", tmp_path)
    monkeypatch.setattr(vs, "load_historical", lambda *args, **kwargs: hist)
    monkeypatch.setattr(
        vs,
        "extract_supply_temperature_bc",
        lambda _h: {"mode": "constant", "mean_C": 86.0, "median_C": 86.0, "std_C": 1.0},
    )
    monkeypatch.setattr(vs, "extract_optimization_node_temps", lambda *_a, **_k: None)
    monkeypatch.setattr(vs, "plot_spatial_profile", lambda *args, **kwargs: None)
    monkeypatch.setattr(vs, "plot_node_error_heatmap", lambda *args, **kwargs: None)
    monkeypatch.setattr(vs, "plot_level_comparison_scatter", lambda *args, **kwargs: None)
    monkeypatch.setattr(vs, "plot_validation_timeseries", lambda *args, **kwargs: None)

    result = run_spatial_validation(skip_calibration=True)
    assert result["model_levels_available"] == ["L3"]
