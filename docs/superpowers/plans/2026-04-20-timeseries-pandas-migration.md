# TimeSeriesTable pandas Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove manual fill-function reimplementations from `calion/utils/timeseries.py`, replace with pandas equivalents in-place, and add `to_frame()`/`from_frame()` for downstream analysis code.

**Architecture:** Keep `TimeSeriesTable` dataclass structure unchanged (internal `dict[str, list[float]]`). Delete `forward_fill`, `backward_fill`, `fill_gaps` standalone functions and update the single caller (`loader.py`) to use `pd.Series.ffill().bfill()` inline. Add `to_frame()`/`from_frame()` methods. Rewrite `_resample_regular` in `loader.py` with `pd.DataFrame.reindex().ffill()`.

**Tech Stack:** Python, pandas (already a project dependency), pytest

---

## File Map

| File | Change |
|---|---|
| `calion/utils/timeseries.py` | Delete 3 fill functions, add `to_frame()` + `from_frame()` |
| `calion/io/loader.py` | Remove `fill_gaps` import/usage, rewrite `_resample_regular` |
| `tests/test_timeseries.py` | Remove `TestFillFunctions`, add `to_frame`/`from_frame` tests |

---

## Task 1: Add `to_frame()` and `from_frame()` to `TimeSeriesTable`

**Files:**
- Modify: `calion/utils/timeseries.py`
- Test: `tests/test_timeseries.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_timeseries.py`:

```python
import pandas as pd

class TestTimeSeriesTablePandas:
    def test_to_frame_shape(self):
        t = _make_table(4)
        df = t.to_frame()
        assert isinstance(df, pd.DataFrame)
        assert df.shape == (4, 2)
        assert list(df.columns) == ["demand", "price"]

    def test_to_frame_values(self):
        t = _make_table(4)
        df = t.to_frame()
        assert list(df["demand"]) == [10.0, 11.0, 12.0, 13.0]

    def test_to_frame_index_is_datetime(self):
        t = _make_table(4)
        df = t.to_frame()
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index[0] == pd.Timestamp("2023-01-01 00:00:00")

    def test_to_frame_is_copy(self):
        t = _make_table(4)
        df = t.to_frame()
        df["demand"].iloc[0] = 999.0
        assert t["demand"][0] == 10.0  # original unaffected

    def test_from_frame_roundtrip(self):
        t = _make_table(4)
        df = t.to_frame()
        t2 = TimeSeriesTable.from_frame(df)
        assert t2.columns == t.columns
        assert t2["demand"] == t["demand"]
        assert t2["price"] == t["price"]
        assert t2.index == t.index

    def test_from_frame_index_type(self):
        t = _make_table(4)
        df = t.to_frame()
        t2 = TimeSeriesTable.from_frame(df)
        assert all(isinstance(ts, datetime) for ts in t2.index)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_timeseries.py::TestTimeSeriesTablePandas -v
```

Expected: `AttributeError: 'TimeSeriesTable' object has no attribute 'to_frame'`

- [ ] **Step 3: Implement `to_frame()` and `from_frame()`**

In `calion/utils/timeseries.py`, add these two methods inside the `TimeSeriesTable` dataclass (after `column_stats`):

```python
def to_frame(self) -> pd.DataFrame:
    """Return a copy of this table as a pandas DataFrame with DatetimeIndex."""
    return pd.DataFrame(self.data, index=pd.DatetimeIndex(self.index))

@classmethod
def from_frame(cls, df: pd.DataFrame) -> "TimeSeriesTable":
    """Construct a TimeSeriesTable from a pandas DataFrame with DatetimeIndex."""
    index = [ts.to_pydatetime() for ts in df.index]
    columns = list(df.columns)
    data = {col: df[col].tolist() for col in columns}
    return cls(index=index, columns=columns, data=data)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_timeseries.py::TestTimeSeriesTablePandas -v
```

Expected: 6 tests PASSED

- [ ] **Step 5: Run full timeseries test suite to check no regressions**

```
pytest tests/test_timeseries.py -v
```

Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git add calion/utils/timeseries.py tests/test_timeseries.py
git commit -m "feat(timeseries): add to_frame() and from_frame() to TimeSeriesTable"
```

---

## Task 2: Remove `forward_fill`, `backward_fill`, `fill_gaps` from `timeseries.py`

**Files:**
- Modify: `calion/utils/timeseries.py`
- Modify: `calion/io/loader.py`
- Modify: `tests/test_timeseries.py`

- [ ] **Step 1: Delete `TestFillFunctions` from `tests/test_timeseries.py`**

Remove the entire `TestFillFunctions` class (lines 124–154) and remove the imports:

```python
# Remove from the import at top of file:
from calion.utils.timeseries import (
    TimeSeriesTable,
    forward_fill,   # <-- remove this
    backward_fill,  # <-- remove this
    fill_gaps,      # <-- remove this
)

# Replace with:
from calion.utils.timeseries import TimeSeriesTable
```

- [ ] **Step 2: Verify the deleted tests are gone**

```
pytest tests/test_timeseries.py -v
```

Expected: `TestFillFunctions` no longer appears in output. All remaining tests PASSED.

- [ ] **Step 3: Update `loader.py` import**

In `calion/io/loader.py`, line 12:

```python
# Remove:
from calion.utils.timeseries import TimeSeriesTable, fill_gaps

# Replace with:
from calion.utils.timeseries import TimeSeriesTable
```

- [ ] **Step 4: Replace `fill_gaps` calls in `loader.py`**

There are two `fill_gaps` call sites in `loader.py`.

**First site** — inside the pass-through column loop (~line 316):

```python
# Remove:
data[_col] = fill_gaps(_vals)

# Replace with:
_s = pd.Series(_vals)
data[_col] = _s.ffill().bfill().tolist()
```

**Second site** — the final fill loop (~line 319–321):

```python
# Remove:
for key, values in data.items():
    data[key] = fill_gaps(values)
    _require(all(v == v for v in data[key]), f"NaN in column {key}")

# Replace with:
for key, values in data.items():
    filled = pd.Series(values).ffill().bfill().tolist()
    data[key] = filled
    _require(all(v == v for v in data[key]), f"NaN in column {key}")
```

Also add `import pandas as pd` at the top of `loader.py` if not already present.

- [ ] **Step 5: Delete `forward_fill`, `backward_fill`, `fill_gaps` from `timeseries.py`**

Remove lines 82–118 of `calion/utils/timeseries.py` (the three functions and their docstrings):

```python
# DELETE these three functions entirely:
def forward_fill(values: list[float]) -> list[float]: ...
def backward_fill(values: list[float]) -> list[float]: ...
def fill_gaps(values: list[float]) -> list[float]: ...
```

- [ ] **Step 6: Run the test suite**

```
pytest tests/test_timeseries.py tests/test_rolling_workflow.py tests/test_full_system.py -v
```

Expected: all PASSED — if anything fails it means another caller of the deleted functions exists; grep for it with `rg "fill_gaps|forward_fill|backward_fill" calion/`.

- [ ] **Step 7: Commit**

```bash
git add calion/utils/timeseries.py calion/io/loader.py tests/test_timeseries.py
git commit -m "refactor(timeseries): replace manual fill functions with pandas ffill/bfill"
```

---

## Task 3: Rewrite `_resample_regular` in `loader.py` with pandas

**Files:**
- Modify: `calion/io/loader.py`

- [ ] **Step 1: Replace the `_resample_regular` inner function**

In `calion/io/loader.py`, the function `_resample_regular` is defined as an inner function inside `load_input_excel` (around line 325). Replace it entirely:

```python
# Remove:
def _resample_regular(ts: list[datetime], values: dict[str, list[float]], step_hours: float) -> TimeSeriesTable:
    step = timedelta(hours=step_hours)
    target: list[datetime] = []
    series = {k: [] for k in values}
    idx_map = {ts_val: i for i, ts_val in enumerate(ts)}
    current = ts[0]
    end = ts[-1]
    last_values = {k: values[k][0] for k in values}
    while current <= end:
        target.append(current)
        if current in idx_map:
            src_idx = idx_map[current]
            for key in values:
                val = values[key][src_idx]
                series[key].append(val)
                last_values[key] = val
        else:
            for key in values:
                series[key].append(last_values[key])
        current += step
    return TimeSeriesTable(target, list(values.keys()), series)

# Replace with:
def _resample_regular(ts: list[datetime], values: dict[str, list[float]], step_hours: float) -> TimeSeriesTable:
    freq = timedelta(hours=step_hours)
    target_index = pd.date_range(start=ts[0], end=ts[-1], freq=freq)
    df = pd.DataFrame(values, index=pd.DatetimeIndex(ts))
    df = df.reindex(df.index.union(target_index)).ffill().reindex(target_index)
    return TimeSeriesTable(
        index=df.index.to_pydatetime().tolist(),
        columns=list(df.columns),
        data={col: df[col].tolist() for col in df.columns},
    )
```

Note: `timedelta` is already imported in `loader.py`. `pd` is now imported from Task 2.

- [ ] **Step 2: Run loader-touching tests**

```
pytest tests/test_rolling_workflow.py tests/test_full_system.py tests/test_investment.py tests/test_capex_persistence.py -v
```

Expected: all PASSED. If a test fails, check if the resampled index length changed (the new version uses inclusive end, same as old version).

- [ ] **Step 3: Commit**

```bash
git add calion/io/loader.py
git commit -m "refactor(loader): rewrite _resample_regular using pandas reindex+ffill"
```

---

## Task 4: Final verification

- [ ] **Step 1: Run complete test suite**

```
pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: all PASSED, no references to `forward_fill`, `backward_fill`, or `fill_gaps` in errors.

- [ ] **Step 2: Verify deleted functions are gone**

```bash
grep -r "forward_fill\|backward_fill\|fill_gaps" calion/
```

Expected: no output (no calion source files reference these functions).

- [ ] **Step 3: Verify `to_frame` works end-to-end in a real workflow**

```python
# Quick smoke test (run in Python REPL or a scratch script):
from calion.utils.timeseries import TimeSeriesTable
from datetime import datetime, timedelta

start = datetime(2023, 1, 1)
index = [start + timedelta(hours=i) for i in range(24)]
t = TimeSeriesTable(index=index, columns=["demand"], data={"demand": [float(i) for i in range(24)]})
df = t.to_frame()
print(df.head())               # DatetimeIndex, column 'demand'
print(df.resample("6h").mean()) # pandas aggregation works
t2 = TimeSeriesTable.from_frame(df)
assert t2["demand"] == t["demand"]
print("OK")
```

Expected output: DataFrame printed with DatetimeIndex, resampled 4-row result, then `OK`.
