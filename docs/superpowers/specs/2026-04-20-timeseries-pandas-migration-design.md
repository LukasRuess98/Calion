# TimeSeriesTable → pandas Migration Design

**Date:** 2026-04-20  
**Status:** Approved

## Goal

Replace manual reimplementations (`forward_fill`, `backward_fill`, `fill_gaps`, `column_stats`) with pandas internally, while keeping the external `TimeSeriesTable` API intact. Add `.to_frame()` for analysis code that benefits from the full pandas API.

## Approach: Two-Phase

### Phase 1 — Internal cleanup (zero breaking changes)

**`calion/utils/timeseries.py`**

- Store data internally as `pd.DataFrame` instead of `dict[str, list[float]]`
- Keep `__getitem__`, `__len__`, `__iter__`, `__contains__`, `as_rows()`, `copy()`, `to_dict()`, `subset()`, `ensure_frequency()` with identical external signatures
- Delete `forward_fill`, `backward_fill`, `fill_gaps` as standalone functions — replace with `df.ffill()`, `df.bfill()` internally
- Replace `column_stats()` body with `df[name].describe()`
- Add `to_frame() -> pd.DataFrame` — returns a copy of the internal DataFrame with DatetimeIndex
- Add `from_frame(df: pd.DataFrame) -> TimeSeriesTable` classmethod

**`calion/io/loader.py`**

- `_resample_regular`: replace manual loop with `pd.DataFrame.resample()` + `ffill()`
- `fill_gaps` import → remove, use `df.ffill().bfill()` directly

**Consumers unchanged:** `system_builder.py`, `component_assembler.py`, `model_finalizer.py`, `cost_resolver.py` — all use `table[col][i]` which still returns `list[float]` via `__getitem__`.

### Phase 2 — Selective pandas usage in IO/analysis (optional, future)

Where `resample`, `rolling`, `describe`, or `merge` would add real value:
- `calion/io/publication_plotter.py` — use `.to_frame()` for plotting
- `calion/analysis/` — use `.to_frame()` for sensitivity / CO2 analysis
- `calion/forecasting/` — use `.to_frame()` for persistence forecaster

Phase 2 is opportunistic — apply when touching those files for other reasons.

## API Compatibility

| Old | New | Change |
|---|---|---|
| `table[col]` | `table[col]` | None — returns `list[float]` |
| `table.data[col]` | `table.data[col]` | None — `.data` property returns internal dict view |
| `table.index` | `table.index` | None — returns `list[datetime]` |
| `table.columns` | `table.columns` | None — returns `list[str]` |
| `forward_fill(values)` | removed | callers in `loader.py` updated |
| `backward_fill(values)` | removed | callers in `loader.py` updated |
| `fill_gaps(values)` | removed | callers in `loader.py` updated |
| — | `table.to_frame()` | New — `pd.DataFrame` with DatetimeIndex |
| — | `TimeSeriesTable.from_frame(df)` | New — constructor from DataFrame |

## Files Changed (Phase 1)

1. `calion/utils/timeseries.py` — core rewrite (internal only)
2. `calion/io/loader.py` — remove `fill_gaps` usage, simplify `_resample_regular`
3. `tests/test_timeseries.py` — remove tests for deleted functions, add `to_frame`/`from_frame` tests

## Risk

Low. External API unchanged. Pyomo model-building code untouched. Existing test suite covers all consumers.

## Success Criteria

- All existing tests pass
- `forward_fill`, `backward_fill`, `fill_gaps` deleted from module
- `TimeSeriesTable.to_frame()` returns correct `pd.DataFrame`
- `loader.py` `_resample_regular` uses pandas resample
