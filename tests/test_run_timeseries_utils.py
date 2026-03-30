"""Tests for calion.run.utilities.timeseries_utils."""

from datetime import datetime, timedelta

import pytest

from calion.run.utilities.timeseries_utils import (
    _apply_horizon,
    _hours_to_steps,
    _parse_ts,
    _slice_table,
    _slugify,
)
from calion.utils.timeseries import TimeSeriesTable


# ---------------------------------------------------------------------------
# _hours_to_steps
# ---------------------------------------------------------------------------

class TestHoursToSteps:
    def test_exact_division(self):
        assert _hours_to_steps(24, 1.0) == 24

    def test_fractional_dt(self):
        assert _hours_to_steps(6, 0.25) == 24

    def test_minimum_one(self):
        assert _hours_to_steps(0.25, 0.25) >= 1

    def test_non_multiple_raises(self):
        with pytest.raises(ValueError, match="multiple of dt_h"):
            _hours_to_steps(7, 3.0)

    def test_zero_hours_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            _hours_to_steps(0, 1.0)

    def test_negative_hours_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            _hours_to_steps(-1, 1.0)

    def test_custom_name_in_error(self):
        with pytest.raises(ValueError, match="MY_PARAM"):
            _hours_to_steps(-1, 1.0, name="MY_PARAM")


# ---------------------------------------------------------------------------
# _parse_ts
# ---------------------------------------------------------------------------

class TestParseTs:
    def test_passthrough_datetime(self):
        dt = datetime(2024, 1, 1, 12, 0)
        assert _parse_ts(dt) is dt

    def test_iso_format(self):
        assert _parse_ts("2024-01-15T10:30:00") == datetime(2024, 1, 15, 10, 30)

    def test_iso_date_only(self):
        assert _parse_ts("2024-06-01") == datetime(2024, 6, 1)

    def test_german_date_format(self):
        assert _parse_ts("15.01.2024 10:30") == datetime(2024, 1, 15, 10, 30)

    def test_german_date_only(self):
        assert _parse_ts("15.01.2024") == datetime(2024, 1, 15)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _parse_ts("")

    def test_garbage_raises(self):
        with pytest.raises(ValueError, match="Kann Datum"):
            _parse_ts("not-a-date")


# ---------------------------------------------------------------------------
# _slice_table
# ---------------------------------------------------------------------------

def _make_table(n=5):
    index = [datetime(2024, 1, 1, i) for i in range(n)]
    cols = ["temp", "load"]
    data = {"temp": list(range(n)), "load": [10.0 * i for i in range(n)]}
    return TimeSeriesTable(index, cols, data)


class TestSliceTable:
    def test_subset_rows(self):
        t = _make_table(5)
        sliced = _slice_table(t, [1, 3])
        assert len(sliced) == 2
        assert sliced["temp"] == [1, 3]

    def test_single_row(self):
        t = _make_table(5)
        sliced = _slice_table(t, [0])
        assert len(sliced) == 1

    def test_preserves_columns(self):
        t = _make_table(5)
        sliced = _slice_table(t, [0, 1])
        assert sliced.columns == t.columns

    def test_preserves_index(self):
        t = _make_table(5)
        sliced = _slice_table(t, [2, 4])
        assert sliced.index[0] == datetime(2024, 1, 1, 2)
        assert sliced.index[1] == datetime(2024, 1, 1, 4)


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_simple_string(self):
        assert _slugify("hello world") == "hello-world"

    def test_special_chars(self):
        assert _slugify("Test (1) / 2") == "Test-1-2"

    def test_empty_returns_default(self):
        assert _slugify("") == "scenario"

    def test_none_returns_default(self):
        assert _slugify(None) == "scenario"

    def test_already_clean(self):
        assert _slugify("my-scenario") == "my-scenario"


# ---------------------------------------------------------------------------
# _apply_horizon
# ---------------------------------------------------------------------------

def _make_year_table(year=2023, dt_h=1.0):
    """Create a full-year table at hourly resolution."""
    start = datetime(year, 1, 1)
    n = 8760  # non-leap year
    index = [start + timedelta(hours=i) for i in range(n)]
    data = {"load": [1.0] * n}
    return TimeSeriesTable(index, ["load"], data)


class TestApplyHorizon:
    def test_no_horizon(self):
        t = _make_table(10)
        result = _apply_horizon(t, {}, 1.0)
        assert len(result) == 10  # unchanged

    def test_non_dict_horizon(self):
        t = _make_table(10)
        result = _apply_horizon(t, {"horizon": "not_dict"}, 1.0)
        assert len(result) == 10

    def test_full_year(self):
        t = _make_year_table(2023)
        result = _apply_horizon(t, {"horizon": {"type": "full_year", "year": 2023}}, 1.0)
        assert len(result) == 8760

    def test_full_year_auto_year(self):
        t = _make_year_table(2023)
        result = _apply_horizon(t, {"horizon": {"type": "full_year"}}, 1.0)
        assert len(result) == 8760

    def test_full_year_wrong_year(self):
        t = _make_year_table(2023)
        with pytest.raises(RuntimeError, match="keine Zeitschritte"):
            _apply_horizon(t, {"horizon": {"type": "full_year", "year": 2025}}, 1.0)

    def test_date_range(self):
        t = _make_year_table(2023)
        result = _apply_horizon(
            t,
            {"horizon": {"start": "2023-01-01", "end": "2023-01-02 23:00"}},
            1.0,
        )
        assert len(result) == 48

    def test_start_after_end_raises(self):
        t = _make_year_table(2023)
        with pytest.raises(RuntimeError, match="Start liegt nach"):
            _apply_horizon(
                t,
                {"horizon": {"start": "2023-02-01", "end": "2023-01-01"}},
                1.0,
            )

    def test_empty_range_raises(self):
        t = _make_year_table(2023)
        with pytest.raises(RuntimeError, match="keine Zeitschritte"):
            _apply_horizon(
                t,
                {"horizon": {"start": "2025-01-01", "end": "2025-12-31"}},
                1.0,
            )

    def test_start_only(self):
        t = _make_year_table(2023)
        result = _apply_horizon(
            t, {"horizon": {"start": "2023-12-30"}}, 1.0
        )
        assert len(result) == 48  # Dec 30 + Dec 31

    def test_end_only(self):
        t = _make_year_table(2023)
        result = _apply_horizon(
            t, {"horizon": {"end": "2023-01-01 04:00"}}, 1.0
        )
        assert len(result) == 5  # 00:00 through 04:00

    def test_full_year_enforce_false(self):
        # Partial year with enforce=false should warn, not raise
        start = datetime(2024, 1, 1)
        n = 48
        index = [start + timedelta(hours=i) for i in range(n)]
        data = {"temp": list(range(n)), "load": [10.0 * i for i in range(n)]}
        t = TimeSeriesTable(index, ["temp", "load"], data)
        result = _apply_horizon(
            t,
            {"horizon": {"type": "full_year", "year": 2024, "enforce": False}},
            1.0,
        )
        assert len(result) == 48
