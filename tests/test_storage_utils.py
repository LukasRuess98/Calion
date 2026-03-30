"""Tests for calion.utils.storage_utils — storage modeling utilities."""

import math
import pytest
from calion.utils.storage_utils import (
    calculate_temp_dependent_loss_series,
    calculate_stratification_efficiency_bonus,
    recommend_storage_parameters,
)


# ---------------------------------------------------------------------------
# calculate_temp_dependent_loss_series
# ---------------------------------------------------------------------------

class TestTempDependentLoss:
    def test_simple_scaling(self):
        # 0°C ambient, 90°C storage → ΔT = 90K
        # reference at ΔT=50K, so scaling = 90/50 = 1.8
        ambient = [273.15]  # 0°C in K
        result = calculate_temp_dependent_loss_series(
            ambient, storage_temp_K=363.15, reference_loss_rate=0.0005, reference_delta_T_K=50.0
        )
        assert len(result) == 1
        expected = 0.0005 * (90.0 / 50.0)
        assert abs(result[0] - expected) < 1e-10

    def test_multiple_temps(self):
        ambient = [273.15, 283.15, 293.15]  # 0, 10, 20°C
        result = calculate_temp_dependent_loss_series(ambient, storage_temp_K=363.15)
        # Higher ambient → smaller ΔT → lower loss
        assert result[0] > result[1] > result[2]

    def test_zero_delta_t(self):
        # Ambient equal to storage → zero loss
        ambient = [363.15]
        result = calculate_temp_dependent_loss_series(ambient, storage_temp_K=363.15)
        assert result[0] == 0.0

    def test_negative_delta_t_clamped(self):
        # Ambient hotter than storage → ΔT clamped to 0
        ambient = [400.0]
        result = calculate_temp_dependent_loss_series(ambient, storage_temp_K=363.15)
        assert result[0] == 0.0

    def test_physical_params(self):
        ambient = [273.15]
        result = calculate_temp_dependent_loss_series(
            ambient,
            storage_temp_K=363.15,
            heat_transfer_coeff_W_m2K=0.5,
            surface_area_m2=1000.0,
            storage_capacity_mwh=100.0,
        )
        # Q_loss = 0.5 * 1000 * 90 = 45000 W
        # hourly_loss = 45000 / (100 * 1e6) = 0.00045
        assert len(result) == 1
        assert abs(result[0] - 0.00045) < 1e-8

    def test_physical_params_capacity_zero(self):
        with pytest.raises(ValueError, match="capacity must be positive"):
            calculate_temp_dependent_loss_series(
                [273.15],
                heat_transfer_coeff_W_m2K=0.5,
                surface_area_m2=1000.0,
                storage_capacity_mwh=0.0,
            )

    def test_negative_storage_temp(self):
        with pytest.raises(ValueError, match="positive"):
            calculate_temp_dependent_loss_series([273.15], storage_temp_K=-10.0)

    def test_loss_clamped_at_5_percent(self):
        # Extremely large ΔT should be clamped
        ambient = [0.0]  # 0K = unrealistic but tests clamping
        result = calculate_temp_dependent_loss_series(
            ambient, storage_temp_K=363.15, reference_loss_rate=0.1, reference_delta_T_K=1.0
        )
        assert result[0] <= 0.05


# ---------------------------------------------------------------------------
# calculate_stratification_efficiency_bonus
# ---------------------------------------------------------------------------

class TestStratification:
    def test_tall_tank(self):
        # Aspect ratio 3:1 → excellent
        c, d = calculate_stratification_efficiency_bonus(30.0, 10.0)
        assert c == 0.10
        assert d == 0.10

    def test_moderate_tank(self):
        c, d = calculate_stratification_efficiency_bonus(20.0, 10.0)
        assert c == 0.07
        assert d == 0.07

    def test_equal_dims(self):
        c, d = calculate_stratification_efficiency_bonus(10.0, 10.0)
        assert c == 0.05
        assert d == 0.05

    def test_short_tank(self):
        c, d = calculate_stratification_efficiency_bonus(5.0, 10.0)
        assert c == 0.03
        assert d == 0.03

    def test_very_flat_tank(self):
        c, d = calculate_stratification_efficiency_bonus(2.0, 10.0)
        assert c == 0.01
        assert d == 0.01

    def test_negative_dims(self):
        with pytest.raises(ValueError, match="positive"):
            calculate_stratification_efficiency_bonus(-1.0, 10.0)
        with pytest.raises(ValueError, match="positive"):
            calculate_stratification_efficiency_bonus(10.0, 0.0)

    def test_flow_rate_penalty(self):
        # High flow rate should reduce bonus
        c_no_flow, d_no_flow = calculate_stratification_efficiency_bonus(30.0, 10.0)
        c_flow, d_flow = calculate_stratification_efficiency_bonus(
            30.0, 10.0, charge_flow_rate_m3_h=5000.0
        )
        assert c_flow < c_no_flow
        assert d_flow == d_no_flow  # discharge not penalized

    def test_discharge_flow_penalty(self):
        c, d = calculate_stratification_efficiency_bonus(
            30.0, 10.0, discharge_flow_rate_m3_h=5000.0
        )
        assert d < 0.10  # reduced from base


# ---------------------------------------------------------------------------
# recommend_storage_parameters
# ---------------------------------------------------------------------------

class TestRecommendStorageParams:
    def test_hot_water_tank(self):
        params = recommend_storage_parameters("hot_water_tank")
        assert params["charge_efficiency"] == 0.98
        assert params["discharge_efficiency"] == 0.98
        assert "description" in params

    def test_pcm(self):
        params = recommend_storage_parameters("pcm")
        assert params["charge_efficiency"] == 0.96
        assert params["reference_temp_K"] == 333.15

    def test_pit_storage(self):
        params = recommend_storage_parameters("pit_storage")
        assert params["charge_efficiency"] == 0.93
        assert params["power_to_energy_ratio"] == 0.1

    def test_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown storage type"):
            recommend_storage_parameters("magic_box")
