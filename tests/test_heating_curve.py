"""
Tests for heating curve (Heizkurve) functionality.

The heating curve calculates supply temperature based on outdoor temperature:
- At T_outdoor = 20°C → T_supply = 80°C (summer)
- At T_outdoor = -10°C → T_supply = 120°C (winter)
- Linear interpolation between these points
"""

import pytest
from energis.models.network_physics import (
    calculate_supply_temperature,
    calculate_supply_temperature_series,
    get_heating_curve_parameters,
)


class TestHeatingCurve:
    """Test heating curve calculations."""

    def test_supply_temp_at_high_outdoor(self):
        """At high outdoor temp, supply should be at minimum."""
        T_supply = calculate_supply_temperature(
            T_outdoor_c=20.0,
            T_supply_min_c=80.0,
            T_supply_max_c=120.0,
            T_outdoor_high_c=20.0,
            T_outdoor_low_c=-10.0,
        )
        assert T_supply == pytest.approx(80.0, abs=0.1)

    def test_supply_temp_at_low_outdoor(self):
        """At low outdoor temp, supply should be at maximum."""
        T_supply = calculate_supply_temperature(
            T_outdoor_c=-10.0,
            T_supply_min_c=80.0,
            T_supply_max_c=120.0,
            T_outdoor_high_c=20.0,
            T_outdoor_low_c=-10.0,
        )
        assert T_supply == pytest.approx(120.0, abs=0.1)

    def test_supply_temp_at_midpoint(self):
        """At midpoint outdoor temp (5°C), supply should be at midpoint (100°C)."""
        # Midpoint: (20 + -10) / 2 = 5°C
        # Expected: (80 + 120) / 2 = 100°C
        T_supply = calculate_supply_temperature(
            T_outdoor_c=5.0,
            T_supply_min_c=80.0,
            T_supply_max_c=120.0,
            T_outdoor_high_c=20.0,
            T_outdoor_low_c=-10.0,
        )
        assert T_supply == pytest.approx(100.0, abs=0.1)

    def test_supply_temp_interpolation(self):
        """Test linear interpolation at 10°C outdoor."""
        # At 10°C: (20-10)/(20-(-10)) = 10/30 = 1/3 of range from high
        # T_supply = 80 + (120-80) * (1/3) = 80 + 13.33 = 93.33
        T_supply = calculate_supply_temperature(
            T_outdoor_c=10.0,
            T_supply_min_c=80.0,
            T_supply_max_c=120.0,
            T_outdoor_high_c=20.0,
            T_outdoor_low_c=-10.0,
        )
        assert T_supply == pytest.approx(93.33, abs=0.1)

    def test_supply_temp_clamping_high(self):
        """Outdoor temp above threshold should return minimum supply."""
        T_supply = calculate_supply_temperature(
            T_outdoor_c=30.0,  # Above 20°C threshold
            T_supply_min_c=80.0,
            T_supply_max_c=120.0,
            T_outdoor_high_c=20.0,
            T_outdoor_low_c=-10.0,
        )
        assert T_supply == pytest.approx(80.0, abs=0.1)

    def test_supply_temp_clamping_low(self):
        """Outdoor temp below threshold should return maximum supply."""
        T_supply = calculate_supply_temperature(
            T_outdoor_c=-20.0,  # Below -10°C threshold
            T_supply_min_c=80.0,
            T_supply_max_c=120.0,
            T_outdoor_high_c=20.0,
            T_outdoor_low_c=-10.0,
        )
        assert T_supply == pytest.approx(120.0, abs=0.1)

    def test_series_calculation(self):
        """Test series calculation with multiple outdoor temps."""
        outdoor_temps = [20.0, 10.0, 0.0, -10.0]
        expected = [80.0, 93.33, 106.67, 120.0]

        result = calculate_supply_temperature_series(
            T_outdoor_series=outdoor_temps,
            T_supply_min_c=80.0,
            T_supply_max_c=120.0,
            T_outdoor_high_c=20.0,
            T_outdoor_low_c=-10.0,
        )

        assert len(result) == 4
        for i, (actual, expected_val) in enumerate(zip(result, expected)):
            assert actual == pytest.approx(expected_val, abs=0.1), f"Mismatch at index {i}"

    def test_curve_parameters(self):
        """Test extraction of curve parameters (slope-intercept form)."""
        params = get_heating_curve_parameters(
            T_supply_min_c=80.0,
            T_supply_max_c=120.0,
            T_outdoor_high_c=20.0,
            T_outdoor_low_c=-10.0,
        )

        # Slope: (120-80) / (-10-20) = 40 / -30 = -1.333
        assert params['slope'] == pytest.approx(-1.3333, abs=0.01)

        # Intercept: at T_outdoor=0, T_supply should be 106.67
        # T_supply = slope * 0 + intercept = intercept = 106.67
        assert params['intercept'] == pytest.approx(106.67, abs=0.1)

        # Verify formula string exists
        assert 'formula' in params
        assert 'T_supply' in params['formula']

    def test_invalid_temperature_range(self):
        """Test that invalid temperature range raises error."""
        with pytest.raises(ValueError):
            calculate_supply_temperature(
                T_outdoor_c=10.0,
                T_supply_min_c=80.0,
                T_supply_max_c=120.0,
                T_outdoor_high_c=-10.0,  # Invalid: high < low
                T_outdoor_low_c=20.0,
            )


class TestHeatingCurveEdgeCases:
    """Test edge cases for heating curve."""

    def test_zero_outdoor_temp(self):
        """Test at 0°C outdoor."""
        T_supply = calculate_supply_temperature(
            T_outdoor_c=0.0,
            T_supply_min_c=80.0,
            T_supply_max_c=120.0,
            T_outdoor_high_c=20.0,
            T_outdoor_low_c=-10.0,
        )
        # At 0°C: (20-0)/30 = 2/3 of range
        # T_supply = 80 + 40 * (2/3) = 80 + 26.67 = 106.67
        assert T_supply == pytest.approx(106.67, abs=0.1)

    def test_custom_temperature_range(self):
        """Test with different temperature parameters."""
        # 4GDH network: lower temperatures
        T_supply = calculate_supply_temperature(
            T_outdoor_c=10.0,
            T_supply_min_c=50.0,   # 4GDH summer
            T_supply_max_c=70.0,   # 4GDH winter
            T_outdoor_high_c=15.0,
            T_outdoor_low_c=-5.0,
        )
        # At 10°C: (15-10)/20 = 1/4 of range
        # T_supply = 50 + 20 * (1/4) = 50 + 5 = 55
        assert T_supply == pytest.approx(55.0, abs=0.1)

    def test_empty_series(self):
        """Test with empty series."""
        result = calculate_supply_temperature_series([])
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
