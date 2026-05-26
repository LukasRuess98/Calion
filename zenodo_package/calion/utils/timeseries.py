"""Small helper classes that mimic the subset of pandas used in the project."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd


def _ensure_length(values: dict[str, list[float]]) -> int:
    lengths = {len(v) for v in values.values()}
    if len(lengths) != 1:
        raise ValueError("Column lengths mismatch in time series table")
    return lengths.pop() if lengths else 0


@dataclass
class TimeSeriesTable:
    """Simple table structure storing equally spaced time series data."""

    index: list[datetime]
    columns: list[str]
    data: dict[str, list[float]]

    def __post_init__(self) -> None:
        n_rows = len(self.index)
        for col in self.columns:
            if col not in self.data:
                raise KeyError(f"Missing column data for {col!r}")
            if len(self.data[col]) != n_rows:
                raise ValueError(f"Column {col!r} has wrong length")

    def __len__(self) -> int:
        return len(self.index)

    def __iter__(self) -> Iterator[str]:
        return iter(self.columns)

    def __getitem__(self, key: str) -> list[float]:
        return self.data[key]

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def as_rows(self) -> Iterator[dict[str, float]]:
        for i in range(len(self.index)):
            yield {col: self.data[col][i] for col in self.columns}

    def copy(self) -> TimeSeriesTable:
        return TimeSeriesTable(self.index[:], self.columns[:], {k: v[:] for k, v in self.data.items()})

    def to_dict(self) -> dict[str, list[float]]:
        return {k: v[:] for k, v in self.data.items()}

    def subset(self, cols: Sequence[str]) -> TimeSeriesTable:
        return TimeSeriesTable(self.index[:], list(cols), {c: self.data[c][:] for c in cols})

    def ensure_frequency(self, dt_hours: float) -> None:
        if len(self.index) < 2:
            return
        expected = timedelta(hours=dt_hours)
        for prev, curr in zip(self.index, self.index[1:], strict=False):
            if curr - prev != expected:
                raise ValueError("Time index is not evenly spaced")

    def column_stats(self, name: str) -> dict[str, float]:
        series = self.data[name]
        if not series:
            return {"name": name, "n": 0, "min": 0.0, "max": 0.0, "mean": 0.0}
        s = pd.Series(series)
        return {
            "name": name,
            "n": len(series),
            "min": float(s.min()),
            "max": float(s.max()),
            "mean": float(s.mean()),
        }


def forward_fill(values: list[float]) -> list[float]:
    """Forward fill missing values (None or NaN) with the last valid value.

    If the first value(s) are missing, they remain None until a valid value is found.
    """
    out = []
    last = None
    for v in values:
        if v is None or v != v:  # NaN check
            # Only fill if we have a valid last value
            out.append(last if last is not None else v)
        else:
            out.append(v)
            last = v
    return out


def backward_fill(values: list[float]) -> list[float]:
    """Backward fill missing values (None or NaN) with the next valid value.

    If the last value(s) are missing, they remain None until a valid value is found.
    """
    out = values[:]
    next_val = None
    for i in range(len(out) - 1, -1, -1):
        v = out[i]
        if v is None or v != v:
            # Only fill if we have a valid next value
            out[i] = next_val if next_val is not None else v
        else:
            next_val = v
    return out


def fill_gaps(values: list[float]) -> list[float]:
    return backward_fill(forward_fill(values))

