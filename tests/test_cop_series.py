from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from calion.models.cop_calculator import calculate_cop_series as _cop_series_from_table
from calion.utils.timeseries import TimeSeriesTable


def _base_table(hours: int, extra: dict[str, list[float]]) -> TimeSeriesTable:
    base = datetime(2023, 1, 1)
    index = [base + timedelta(hours=i) for i in range(hours)]
    data = {
        "strompreis_EUR_MWh": [0.0] * hours,
        "waermebedarf_MWth": [0.0] * hours,
        "grid_co2_kg_MWh": [0.0] * hours,
    }
    columns = list(data.keys())
    for key, values in extra.items():
        columns.append(key)
        data[key] = values
    return TimeSeriesTable(index=index, columns=columns, data=data)


def test_cop_series_bilinear_interpolation_with_clamping():
    table = _base_table(
        3,
        {
            "WRG1_T_K": [305.0, 315.0, 330.0],
            "sink_temp_K": [330.0, 335.0, 345.0],
        },
    )
    cfg = {
        "heat_pumps": {
            "cop": {
                "tables": {
                    "standard": {
                        "x": [300.0, 310.0, 320.0],
                        "y": [330.0, 340.0],
                        "values": [
                            [4.0, 4.5, 5.0],
                            [3.0, 3.5, 4.0],
                        ],
                        "x_column": "WRG1_T_K",
                        "y_column": "sink_temp_K",
                        "clamp": True,
                    }
                }
            }
        }
    }

    result = _cop_series_from_table(table, "WRG1_T_K", cfg, "standard")
    assert result == pytest.approx([4.25, 4.25, 4.0])


def test_cop_series_out_of_range_without_clamp_raises():
    table = _base_table(
        1,
        {
            "WRG1_T_K": [330.0],
            "sink_temp_K": [330.0],
        },
    )
    cfg = {
        "heat_pumps": {
            "cop": {
                "tables": {
                    "standard": {
                        "x": [300.0, 310.0, 320.0],
                        "y": [330.0, 340.0],
                        "values": [
                            [4.0, 4.5, 5.0],
                            [3.0, 3.5, 4.0],
                        ],
                        "x_column": "WRG1_T_K",
                        "y_column": "sink_temp_K",
                        "clamp": False,
                    }
                }
            }
        }
    }

    with pytest.raises(ValueError):
        _cop_series_from_table(table, "WRG1_T_K", cfg, "standard")


def test_cop_series_uses_sink_temp_series_override():
    """When sink_temp_series is provided, it overrides Tsink_out_K in analytical mode."""
    hours = 4
    table = _base_table(hours, {"WRG_T_K": [283.0, 288.0, 293.0, 298.0]})

    cfg_fixed_sink = {
        "heat_pumps": {
            "cop": {"sink_defaults": {"Tsink_out_K": 363.15, "Tsink_in_K": 343.15}},
            "types": {"default": {"eta": 0.75, "FQ": 0.10}},
        }
    }

    # COP with fixed sink temp (90 °C = 363.15 K)
    cop_fixed = _cop_series_from_table(table, "WRG_T_K", cfg_fixed_sink, "default")

    # COP with lower sink temp (70 °C = 343.15 K) → should give higher COP
    sink_series = [343.15, 343.15, 343.15, 343.15]
    cop_variable = _cop_series_from_table(
        table, "WRG_T_K", cfg_fixed_sink, "default",
        sink_temp_series=sink_series,
    )

    assert all(cv >= cf for cv, cf in zip(cop_variable, cop_fixed)), (
        "Lower sink temperature must yield higher or equal COP"
    )


def test_cop_series_sink_temp_series_table_mode():
    """sink_temp_series override works in table-based COP mode too."""
    hours = 3
    table = _base_table(hours, {"WRG_T_K": [300.0, 310.0, 315.0]})
    cfg = {
        "heat_pumps": {
            "cop": {
                "tables": {
                    "standard": {
                        "x": [290.0, 300.0, 315.0],
                        "y": [340.0, 360.0],
                        "values": [[5.0, 4.5, 4.0], [4.0, 3.5, 3.0]],
                        "x_column": "WRG_T_K",
                        "clamp": True,
                    }
                }
            }
        }
    }
    # Without sink_temp_series: uses y default (clamp to first row, y=340 K)
    cop_no_series = _cop_series_from_table(table, "WRG_T_K", cfg, "standard")

    # With sink_temp_series at upper y value (360 K): should give lower COP
    cop_high_sink = _cop_series_from_table(
        table, "WRG_T_K", cfg, "standard",
        sink_temp_series=[360.0, 360.0, 360.0],
    )
    assert all(ch <= cn for ch, cn in zip(cop_high_sink, cop_no_series)), (
        "Higher sink temp (360K) must give lower or equal COP than default"
    )
