"""Tests for calion.utils.timeseries — TimeSeriesTable and fill utilities."""

import math
import pytest
from datetime import datetime, timedelta

from calion.utils.timeseries import (
    TimeSeriesTable,
    forward_fill,
    backward_fill,
    fill_gaps,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_table(n=4):
    """Create a small test table with n rows."""
    start = datetime(2023, 1, 1)
    index = [start + timedelta(hours=i) for i in range(n)]
    columns = ["demand", "price"]
    data = {
        "demand": [10.0 + i for i in range(n)],
        "price": [50.0 - i for i in range(n)],
    }
    return TimeSeriesTable(index=index, columns=columns, data=data)


# ---------------------------------------------------------------------------
# TimeSeriesTable
# ---------------------------------------------------------------------------

class TestTimeSeriesTable:
    def test_basic_creation(self):
        t = _make_table()
        assert len(t) == 4
        assert list(t) == ["demand", "price"]

    def test_missing_column_data(self):
        with pytest.raises(KeyError, match="Missing column"):
            TimeSeriesTable(
                index=[datetime(2023, 1, 1)],
                columns=["a", "b"],
                data={"a": [1.0]},
            )

    def test_wrong_length(self):
        with pytest.raises(ValueError, match="wrong length"):
            TimeSeriesTable(
                index=[datetime(2023, 1, 1), datetime(2023, 1, 2)],
                columns=["a"],
                data={"a": [1.0]},
            )

    def test_getitem(self):
        t = _make_table()
        assert t["demand"] == [10.0, 11.0, 12.0, 13.0]

    def test_contains(self):
        t = _make_table()
        assert "demand" in t
        assert "missing" not in t

    def test_as_rows(self):
        t = _make_table(2)
        rows = list(t.as_rows())
        assert len(rows) == 2
        assert rows[0]["demand"] == 10.0
        assert rows[1]["price"] == 49.0

    def test_copy(self):
        t = _make_table()
        c = t.copy()
        c.data["demand"][0] = 999.0
        assert t["demand"][0] == 10.0  # original not mutated

    def test_to_dict(self):
        t = _make_table()
        d = t.to_dict()
        assert "demand" in d
        d["demand"][0] = 999.0
        assert t["demand"][0] == 10.0

    def test_subset(self):
        t = _make_table()
        s = t.subset(["demand"])
        assert s.columns == ["demand"]
        assert "price" not in s.data

    def test_ensure_frequency_ok(self):
        t = _make_table()
        t.ensure_frequency(1.0)  # 1-hour steps — should pass

    def test_ensure_frequency_fail(self):
        t = _make_table()
        with pytest.raises(ValueError, match="not evenly spaced"):
            t.ensure_frequency(2.0)

    def test_ensure_frequency_short(self):
        # < 2 rows — no check
        t = _make_table(1)
        t.ensure_frequency(999.0)

    def test_column_stats(self):
        t = _make_table(4)
        stats = t.column_stats("demand")
        assert stats["n"] == 4
        assert stats["min"] == 10.0
        assert stats["max"] == 13.0
        assert abs(stats["mean"] - 11.5) < 1e-10

    def test_column_stats_empty(self):
        t = TimeSeriesTable(index=[], columns=["a"], data={"a": []})
        stats = t.column_stats("a")
        assert stats["n"] == 0


# ---------------------------------------------------------------------------
# Fill functions
# ---------------------------------------------------------------------------

class TestFillFunctions:
    def test_forward_fill_basic(self):
        assert forward_fill([1.0, None, None, 4.0]) == [1.0, 1.0, 1.0, 4.0]

    def test_forward_fill_leading_none(self):
        result = forward_fill([None, None, 3.0])
        assert result[0] is None
        assert result[1] is None
        assert result[2] == 3.0

    def test_forward_fill_nan(self):
        result = forward_fill([1.0, float("nan"), 3.0])
        assert result[1] == 1.0

    def test_backward_fill_basic(self):
        assert backward_fill([None, None, 3.0, 4.0]) == [3.0, 3.0, 3.0, 4.0]

    def test_backward_fill_trailing_none(self):
        result = backward_fill([1.0, None, None])
        assert result[0] == 1.0
        assert result[1] is None
        assert result[2] is None

    def test_fill_gaps(self):
        result = fill_gaps([None, 2.0, None, None, 5.0, None])
        # forward_fill: [None, 2.0, 2.0, 2.0, 5.0, 5.0]
        # backward_fill: [2.0, 2.0, 2.0, 2.0, 5.0, 5.0]
        assert result[0] == 2.0
        assert result[2] == 2.0
        assert result[5] == 5.0
