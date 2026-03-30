"""Tests for calion.config.model_settings — reference documentation dicts."""

from calion.config.model_settings import ROLLING_HORIZON, GRID_LIMITS, STORAGE_POLICIES


class TestModelSettings:
    def test_rolling_horizon_keys(self):
        assert "heat_horizon_hours" in ROLLING_HORIZON
        assert "step_hours" in ROLLING_HORIZON
        assert "overlap_hours" in ROLLING_HORIZON
        assert "terminal_policy" in ROLLING_HORIZON

    def test_grid_limits_keys(self):
        assert "max_import_mw" in GRID_LIMITS
        assert "max_export_mw" in GRID_LIMITS
        assert "big_m_grid_mw" in GRID_LIMITS

    def test_storage_policies_keys(self):
        assert "terminal.policy" in STORAGE_POLICIES
        assert "max_energy_mwh" in STORAGE_POLICIES

    def test_all_values_are_strings(self):
        for d in (ROLLING_HORIZON, GRID_LIMITS, STORAGE_POLICIES):
            for k, v in d.items():
                assert isinstance(k, str)
                assert isinstance(v, str)
