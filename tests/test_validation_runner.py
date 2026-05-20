"""
Unit tests for tools/validation_runner.py

All tests are purely synthetic — no Gurobi, no Excel, no file I/O.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from validation_runner import (
    apply_return_v2_source_bias_correction,
    assess_miqp_usability,
    build_effective_stage1_kpis,
    calibrate_u_values,
    check_eboiler_plausibility,
    check_hp_plausibility,
    check_tes_plausibility,
    compute_stage1_kpis,
    fit_return_v2_params_by_node,
    _select_miqp_windows,
    _fix_sim_legacy,
    _fix_sim_miqp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_index(n: int = 100) -> pd.DatetimeIndex:
    return pd.date_range("2025-01-01", periods=n, freq="h")


def _make_measured(
    n: int = 100,
    t_supply_farend: float | None = 82.0,
    t_return: float | None = 55.0,
    flow: float | None = 300.0,
    q_demand: float | None = 10.0,
) -> pd.DataFrame:
    idx = _make_index(n)
    d: dict = {}
    if t_supply_farend is not None:
        d["T_supply_farend_C"] = t_supply_farend
    if t_return is not None:
        d["T_return_source_C"] = t_return
    if flow is not None:
        d["flow_source_m3h"] = flow
    if q_demand is not None:
        d["Q_demand_MWth"] = q_demand
    return pd.DataFrame(d, index=idx)


def _make_simulated(
    n: int = 100,
    t_supply: float = 86.0,
    t_supply_farend: float | None = 84.0,
    t_return: float | None = 57.0,
    q_demand: float | None = 10.0,
    t_return_is_nominal: bool = False,
) -> pd.DataFrame:
    idx = _make_index(n)
    d: dict = {
        "T_supply_C": t_supply,
        "Q_demand_total_MW": q_demand if q_demand is not None else 10.0,
    }
    if t_supply_farend is not None:
        d["T_supply_farend_C"] = t_supply_farend
    if t_return is not None:
        d["T_return_C"] = t_return
    if t_return_is_nominal:
        d["_T_return_is_nominal"] = True
    return pd.DataFrame(d, index=idx)


def _bc(mean: float = 86.0) -> dict:
    return {"mean_C": mean, "median_C": mean, "std_C": 2.0, "mode": "series"}


# ===========================================================================
# TestComputeStage1KpisFormulas
# ===========================================================================

class TestComputeStage1KpisFormulas:

    def test_mae_formula_exact(self):
        """MAE formula: mean of absolute differences."""
        n = 50
        meas = _make_measured(n, t_supply_farend=80.0, t_return=None, flow=None, q_demand=None)
        # Simulated is 2.0 °C above measured every hour → MAE == 2.0
        sim = _make_simulated(n, t_supply_farend=82.0, t_return=None, q_demand=10.0)
        bc = _bc()
        kpis = compute_stage1_kpis(meas, sim, bc)
        assert "T_supply_farend_MAE_C" in kpis
        assert abs(kpis["T_supply_farend_MAE_C"] - 2.0) < 1e-6

    def test_rmse_formula_exact(self):
        """RMSE formula: sqrt(mean(errors^2))."""
        n = 50
        meas = _make_measured(n, t_supply_farend=80.0, t_return=None, flow=None, q_demand=None)
        sim = _make_simulated(n, t_supply_farend=83.0, t_return=None, q_demand=10.0)
        bc = _bc()
        kpis = compute_stage1_kpis(meas, sim, bc)
        assert "T_supply_farend_RMSE_C" in kpis
        assert abs(kpis["T_supply_farend_RMSE_C"] - 3.0) < 1e-6

    def test_q_annual_error_pct(self):
        """Q_annual_error_pct = abs(sim - meas) / meas * 100."""
        n = 100
        meas_q = 10.0
        sim_q = 11.0  # 10% more
        meas = _make_measured(n, t_supply_farend=None, t_return=None, flow=None, q_demand=meas_q)
        sim = _make_simulated(n, t_supply_farend=None, t_return=None, q_demand=sim_q)
        bc = _bc()
        kpis = compute_stage1_kpis(meas, sim, bc)
        assert "Q_annual_error_pct" in kpis
        expected = abs(sim_q * n - meas_q * n) / (meas_q * n) * 100
        assert abs(kpis["Q_annual_error_pct"] - expected) < 1e-3

    def test_dt_sim_low_dt_filters_flow_kpi(self):
        """dt_sim < 3°C must be filtered — MAPE would explode otherwise."""
        n = 100
        idx = _make_index(n)
        meas = pd.DataFrame({
            "flow_source_m3h": 300.0,
            "Q_demand_MWth": 10.0,
        }, index=idx)
        # ΔT = 1.0°C → below 3°C guard → flow_source_MAPE_pct should NOT be computed
        sim = pd.DataFrame({
            "T_supply_C": 87.0,
            "T_return_C": 86.0,   # ΔT = 1.0°C — below guard
            "Q_demand_total_MW": 10.0,
        }, index=idx)
        bc = _bc(87.0)
        kpis = compute_stage1_kpis(meas, sim, bc)
        # flow_source_MAPE_pct should not be present (or None) because ΔT < 3°C
        assert "flow_source_MAPE_pct" not in kpis or kpis.get("flow_source_MAPE_pct") is None


# ===========================================================================
# TestCalibrateUValues
# ===========================================================================

class TestCalibrateUValues:

    def test_calibration_increases_u_when_sim_underpredicts_drop(self):
        """Measured drop > simulated drop → U should increase."""
        n = 100
        bc = _bc(86.0)
        # Measured: 10°C drop (farend = 76°C)
        meas = pd.DataFrame({"T_supply_drop_measured_C": 10.0}, index=_make_index(n))
        # Simulated: 2°C drop (farend = 84°C) → underpredicts heat loss
        sim = _make_simulated(n, t_supply_farend=84.0)
        result = calibrate_u_values(meas, sim, bc, previous_u=None)
        # U must increase for trunk pipes
        from validation_runner import TRUNK_PIPES, PIPE_CATALOG
        for pid in TRUNK_PIPES:
            u_nom = PIPE_CATALOG[pid]["U_nom"]
            assert result[pid] > u_nom, f"{pid}: expected U increase, got {result[pid]:.4f} <= {u_nom}"

    def test_calibration_result_within_clip_bounds(self):
        """Calibrated U-values must stay within [0.05×, 20×] nominal."""
        from validation_runner import PIPE_CATALOG
        n = 100
        bc = _bc(86.0)
        meas = pd.DataFrame({"T_supply_drop_measured_C": 50.0}, index=_make_index(n))
        sim = _make_simulated(n, t_supply_farend=85.9)  # extreme mismatch
        result = calibrate_u_values(meas, sim, bc, previous_u=None)
        for pid, u_val in result.items():
            u_nom = PIPE_CATALOG[pid]["U_nom"]
            assert u_val >= u_nom * 0.05 - 1e-9
            assert u_val <= u_nom * 20.0 + 1e-9

    def test_calibration_no_change_when_no_measured_drop(self):
        """Without T_supply_drop_measured_C, result equals nominal U-values."""
        from validation_runner import PIPE_CATALOG
        n = 100
        bc = _bc()
        meas = pd.DataFrame({"some_other_col": 1.0}, index=_make_index(n))
        sim = _make_simulated(n)
        result = calibrate_u_values(meas, sim, bc, previous_u=None)
        for pid, u_val in result.items():
            u_nom = PIPE_CATALOG[pid]["U_nom"]
            assert abs(u_val - u_nom) < 1e-9, f"{pid}: expected nominal {u_nom}, got {u_val}"


# ===========================================================================
# TestBuildEffectiveStage1Kpis
# ===========================================================================

class TestBuildEffectiveStage1Kpis:

    def test_miqp_overrides_milp_temperature_kpis_when_usable(self):
        """When MIQP is usable, temperature KPIs from MIQP replace MILP values."""
        milp = {"Q_annual_error_pct": 1.5, "T_supply_farend_MAE_C": 5.0}
        miqp = {"T_supply_farend_MAE_C": 0.8, "T_return_source_MAE_C": 0.6}
        result = build_effective_stage1_kpis(milp, miqp, miqp_usable=True)
        # MIQP temperature value should win
        assert result["T_supply_farend_MAE_C"] == 0.8
        # Energy KPI from MILP preserved
        assert result["Q_annual_error_pct"] == 1.5


# ===========================================================================
# TestReturnV2SourceBiasCorrection
# ===========================================================================

class TestReturnV2SourceBiasCorrection:

    def test_applies_global_bias_to_a0_when_source_channel_available(self):
        n = 120
        idx = _make_index(n)
        hist = pd.DataFrame({
            "V_2_demand_MWth": 2.0,
            "V_2_flow_rate": 20.0,   # m3/h
            "V_2_return_temp": 50.0,
            "V_2_flow_temp": 85.0,
            "outdoor_temp_C": 10.0,
        }, index=idx)
        measured_agg = pd.DataFrame({
            "T_return_source_C": 55.0,
        }, index=idx)
        params = {
            "j_2": {
                "a0": 50.0,
                "a_q": 0.0,
                "a_out": 0.0,
                "a_sup": 0.0,
                "alpha": 0.5,
                "q_ref": 2.0,
                "t_outdoor_ref": 10.0,
                "t_supply_ref": 85.0,
                "state_init_c": 50.0,
            }
        }
        corrected, meta = apply_return_v2_source_bias_correction(
            hist=hist,
            measured_agg=measured_agg,
            params_by_node=params,
            months_filter=None,
            bias_clip_c=3.0,
            max_surrogate_mae_c=10.0,
        )
        assert meta.get("status") == "applied"
        assert abs(float(meta.get("bias_applied_c", 0.0)) - 3.0) < 0.2
        assert abs(float(corrected["j_2"]["a0"]) - 53.0) < 0.2

    def test_milp_unchanged_when_miqp_not_usable(self):
        """When MIQP is not usable, MILP KPIs are returned unchanged."""
        milp = {"Q_annual_error_pct": 1.5, "T_supply_farend_MAE_C": 5.0}
        miqp = {"T_supply_farend_MAE_C": 0.8}
        result = build_effective_stage1_kpis(milp, miqp, miqp_usable=False)
        assert result["T_supply_farend_MAE_C"] == 5.0
        assert result["Q_annual_error_pct"] == 1.5


# ===========================================================================
# TestFixSimLegacy
# ===========================================================================

class TestFixSimLegacy:

    def test_q_demand_reconstructed_when_zero(self):
        """Q_demand_total_MW = 0 → reconstructed from generation balance."""
        n = 10
        idx = _make_index(n)
        sim = pd.DataFrame({
            "Q_demand_total_MW": 0.0,
            "Q_gasboiler_MW": 5.0,
            "Q_biomass_MW": 2.0,
            "Q_storage_discharge_MW": 1.0,
            "Q_storage_charge_MW": 0.5,
            "Q_loss_total_MW": 0.3,
        }, index=idx)
        fixed = _fix_sim_legacy(sim)
        # Expected: 5 + 2 + 1 - 0.5 - 0.3 = 7.2 MW
        expected = 5.0 + 2.0 + 1.0 - 0.5 - 0.3
        assert (fixed["Q_demand_total_MW"] - expected).abs().max() < 1e-6

    def test_q_demand_not_changed_when_nonzero(self):
        """Non-zero Q_demand_total_MW must not be overwritten."""
        n = 10
        idx = _make_index(n)
        sim = pd.DataFrame({
            "Q_demand_total_MW": 8.0,
            "Q_gasboiler_MW": 5.0,
        }, index=idx)
        fixed = _fix_sim_legacy(sim)
        assert (fixed["Q_demand_total_MW"] == 8.0).all()

    def test_t_return_nominal_flag_set(self):
        """_T_return_is_nominal must be True after fix when T_return_C present."""
        n = 10
        idx = _make_index(n)
        sim = pd.DataFrame({
            "Q_demand_total_MW": 8.0,
            "T_return_C": 56.9,   # constant → MILP nominal
        }, index=idx)
        fixed = _fix_sim_legacy(sim)
        assert "_T_return_is_nominal" in fixed.columns
        assert bool(fixed["_T_return_is_nominal"].any())


# ===========================================================================
# TestAssessMiqpUsability
# ===========================================================================

class TestAssessMiqpUsability:

    def test_none_input_not_usable(self):
        result = assess_miqp_usability(None)
        assert result["usable"] is False
        assert result["reason"] == "no_dispatch_file"

    def test_insufficient_farend_hours_not_usable(self):
        """< 24 valid far-end hours → not usable."""
        n = 100
        idx = _make_index(n)
        sim = pd.DataFrame({
            "T_supply_farend_C": [84.0] * 10 + [np.nan] * 90,  # only 10 valid
            "Q_demand_total_MW": 10.0,
        }, index=idx)
        result = assess_miqp_usability(sim)
        assert result["usable"] is False
        assert result["reason"] == "missing_farend_temperature"

    def test_sufficient_data_is_usable(self):
        """≥ 24 farend hours + non-trivial dispatch → usable."""
        n = 100
        idx = _make_index(n)
        sim = pd.DataFrame({
            "T_supply_farend_C": 82.0,
            "Q_demand_total_MW": 10.0,
            "T_supply_C": 86.0,
        }, index=idx)
        result = assess_miqp_usability(sim)
        assert result["usable"] is True
        assert result["reason"] == "ok"


# ===========================================================================
# TestStage2PlausibilityChecks
# ===========================================================================

class TestStage2PlausibilityChecks:

    def _hp_dispatch(self, cop: float, q: float, n: int = 200) -> pd.DataFrame:
        idx = _make_index(n)
        return pd.DataFrame({
            "COP_hp_wrg": cop,
            "Q_hp_total_MW": q,
        }, index=idx)

    def test_hp_cop_pass(self):
        dispatch = self._hp_dispatch(cop=3.5, q=3.0)
        result = check_hp_plausibility(dispatch, None)
        checks = result["checks"]
        assert any("PASS" in c and "COP_min" in c for c in checks)

    def test_hp_cop_fail_low(self):
        dispatch = self._hp_dispatch(cop=1.5, q=3.0)
        result = check_hp_plausibility(dispatch, None)
        checks = result["checks"]
        assert any("WARN" in c and "COP < 2.5" in c for c in checks)

    def test_hp_never_dispatched(self):
        idx = _make_index(50)
        dispatch = pd.DataFrame({
            "COP_hp_wrg": 3.0,
            "Q_hp_total_MW": 0.0,
        }, index=idx)
        result = check_hp_plausibility(dispatch, None)
        assert any("never dispatched" in c.lower() for c in result["checks"])

    def test_eboiler_eta_pass(self):
        n = 100
        idx = _make_index(n)
        q_ek = 4.0
        p_ek = q_ek / 0.95   # η = 0.95
        dispatch = pd.DataFrame({
            "Q_ek_MW": q_ek,
            "P_ek_el_MW": p_ek,
        }, index=idx)
        result = check_eboiler_plausibility(dispatch)
        assert result["efficiency_mean"] is not None
        assert abs(result["efficiency_mean"] - 0.95) < 0.01
        # message uses Greek η, fallback to checking for "PASS" + efficiency value
        assert any("PASS" in c for c in result["checks"])

    def test_tes_soc_bounds(self):
        """TES SOC must pass when within 5–95% of 500 MWh capacity."""
        n = 100
        idx = _make_index(n)
        dispatch = pd.DataFrame({
            "SOC_MWh": 250.0,     # exactly 50% → always OK
            "Q_storage_charge_MW": 5.0,
            "Q_storage_discharge_MW": 5.0,
        }, index=idx)
        result = check_tes_plausibility(dispatch)
        assert result["n_soc_low"] == 0
        assert result["n_soc_high"] == 0
        assert any("PASS" in c and "SOC < 5%" in c for c in result["checks"])


# ===========================================================================
# TestFixSimMiqp
# ===========================================================================

class TestFixSimMiqp:

    def test_t_return_is_nominal_flag_constant(self):
        """Constant T_return_C → _T_return_is_nominal = True."""
        n = 50
        idx = _make_index(n)
        sim = pd.DataFrame({
            "T_supply_C": 86.0,
            "T_return_C": 56.9,   # constant
            "Q_demand_total_MW": 10.0,
        }, index=idx)
        result = _fix_sim_miqp(sim)
        assert bool(result["_T_return_is_nominal"].any())

    def test_t_return_is_not_nominal_when_variable(self):
        """Variable T_return_C (std > 0.01) → _T_return_is_nominal = False."""
        n = 50
        idx = _make_index(n)
        t_ret = np.linspace(50.0, 65.0, n)   # large variation
        sim = pd.DataFrame({
            "T_supply_C": 86.0,
            "T_return_C": t_ret,
            "Q_demand_total_MW": 10.0,
        }, index=idx)
        result = _fix_sim_miqp(sim)
        assert not bool(result["_T_return_is_nominal"].all())

    def test_q_demand_reconstructed_when_zero_miqp(self):
        """Q_demand_total_MW = 0 in MIQP output is reconstructed from gen balance."""
        n = 10
        idx = _make_index(n)
        sim = pd.DataFrame({
            "T_supply_C": 86.0,
            "T_return_C": np.linspace(50.0, 65.0, n),
            "Q_demand_total_MW": 0.0,
            "Q_gasboiler_MW": 6.0,
            "Q_loss_total_MW": 0.5,
        }, index=idx)
        result = _fix_sim_miqp(sim)
        expected = 6.0 - 0.5
        assert (result["Q_demand_total_MW"] - expected).abs().max() < 1e-6


# ===========================================================================
# TestReturnV2Fit
# ===========================================================================

class TestReturnV2Fit:

    def test_fit_falls_back_to_defaults_without_hist(self):
        params, quality, source = fit_return_v2_params_by_node(
            hist=None,
            windows=None,
            cluster_assignment={"node_cluster": {}},
            ridge_weight=0.25,
        )
        assert "j_15" in params
        assert params["j_15"]["alpha"] >= 0.15
        assert params["j_15"]["alpha"] <= 0.85
        assert all(v == "safe_defaults" for v in source.values())
        assert all(isinstance(v, dict) for v in quality.values())

    def test_fit_produces_clamped_params_on_synthetic_node_data(self):
        idx = pd.date_range("2025-07-01", periods=96, freq="h")
        q = np.linspace(0.5, 6.0, len(idx))
        hist = pd.DataFrame(index=idx)
        hist["V_27_demand_MWth"] = q
        hist["V_27_flow_rate"] = 12.0 + 0.8 * q
        hist["V_27_flow_temp"] = 84.0 + 0.1 * np.sin(np.linspace(0, 2 * np.pi, len(idx)))
        hist["V_27_return_temp"] = 54.0 + 0.45 * q + 0.08 * (15.0 - 10.0)
        hist["V_1_flow_temp"] = 86.0
        hist["outdoor_temp_C"] = 10.0 + 5.0 * np.sin(np.linspace(0, 2 * np.pi, len(idx)))

        params, _quality, source = fit_return_v2_params_by_node(
            hist=hist,
            windows=None,
            cluster_assignment={"node_cluster": {"j_15": "medium"}},
            ridge_weight=0.25,
        )
        p = params["j_15"]
        assert source["j_15"] in {"node_fit", "cluster_fit", "global_fit"}
        assert 0.15 <= float(p["alpha"]) <= 0.85
        assert -8.0 <= float(p["a_q"]) <= 8.0
        assert -0.4 <= float(p["a_out"]) <= 0.4
        assert 0.0 <= float(p["a_sup"]) <= 0.5


# ===========================================================================
# TestSelectMiqpWindows
# ===========================================================================

class TestSelectMiqpWindows:

    def test_window_days_default_duration(self):
        """Default day-based windows should have expected duration."""
        windows = _select_miqp_windows(None, None, window_days=2, window_hours=None)
        assert len(windows) == 3
        for w in windows:
            assert w["name"] in {"winter", "summer", "transition"}
            assert (w["end"] - w["start"]) == pd.Timedelta(days=2)

    def test_window_hours_overrides_days(self):
        """window_hours must override window_days for representative windows."""
        weeks = {
            "winter": (pd.Timestamp("2025-01-10 00:00"), pd.Timestamp("2025-01-17 00:00")),
            "summer": (pd.Timestamp("2025-07-10 00:00"), pd.Timestamp("2025-07-17 00:00")),
            "transition": (pd.Timestamp("2025-04-10 00:00"), pd.Timestamp("2025-04-17 00:00")),
        }
        windows = _select_miqp_windows(None, weeks, window_days=7, window_hours=12)
        assert len(windows) == 3
        for w in windows:
            assert (w["end"] - w["start"]) == pd.Timedelta(hours=12)

    def test_window_hours_invalid_falls_back_to_days(self):
        """Invalid window_hours should fall back to 24 * window_days."""
        windows = _select_miqp_windows(None, None, window_days=3, window_hours="bad")  # type: ignore[arg-type]
        assert len(windows) == 3
        for w in windows:
            assert (w["end"] - w["start"]) == pd.Timedelta(days=3)
