from __future__ import annotations

import csv
import math
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from calion.utils.xlsx import read_xlsx
from calion.utils.timeseries import TimeSeriesTable, fill_gaps

from calion.logging_config import get_logger
from calion.io._utils import _is_empty  # noqa: F401 – re-exported for callers

logger = get_logger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _resolve_input_path(path: str, site_cfg: Dict[str, Any]) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        if candidate.exists():
            return candidate
        raise RuntimeError(f"Datei nicht gefunden: {candidate}")

    search_roots = []

    for key in ("input_base_dir", "input_dir", "data_root"):
        base = site_cfg.get(key)
        if isinstance(base, str) and base:
            search_roots.append(Path(base))

    env_root = os.getenv("ENERGIS_INPUT_ROOT")
    if env_root:
        search_roots.append(Path(env_root))

    search_roots.extend([Path.cwd(), PROJECT_ROOT])

    seen = set()
    for root in search_roots:
        if root in seen:
            continue
        seen.add(root)
        resolved = (root / candidate).expanduser()
        if resolved.exists():
            return resolved.resolve()

    raise RuntimeError(f"Datei nicht gefunden: {path}")


def _read_tabular(path: Path, sheet_name: str | None) -> tuple[list[str], list[list[Any]]]:
    """Return ``(header, rows)`` from CSV or XLSX input.

    CSV keeps diffs text-only for synthetic examples; XLSX remains supported for
    backwards compatibility.
    """

    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            reader = list(csv.reader(handle))
        if not reader:
            return [], []
        header = [col.strip() for col in reader[0]]
        data_rows: List[List[Any]] = []
        for row in reader[1:]:
            if not any(str(cell).strip() for cell in row):
                continue
            cells = list(row)
            if len(cells) < len(header):
                cells.extend([""] * (len(header) - len(cells)))
            elif len(cells) > len(header):
                cells = cells[: len(header)]
            data_rows.append(cells)
        return header, data_rows

    return read_xlsx(str(path), sheet_name=sheet_name)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # Excel serial date numbers are already converted by the XLSX helper.
        base = datetime(1899, 12, 30)
        return base + timedelta(days=float(value))
    text = str(value).strip()
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M",
        "%Y/%m/%d %H:%M",
    ]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    # last resort: ISO parser
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise RuntimeError(f"Cannot parse datetime value: {value!r}") from exc


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError as exc:
        raise RuntimeError(f"Expected numeric value, got {value!r}") from exc


def _find_time_column(header: List[str]) -> str:
    candidates = ["datum", "date", "datetime", "zeit", "timestamp", "time"]
    norm = {_normalise(col): col for col in header}
    for cand in candidates:
        if cand in norm:
            return norm[cand]
    raise RuntimeError("Time column not found (e.g., 'Datum', 'Date', 'Time').")


def _map_column(header: List[str], candidates: List[str]) -> Optional[str]:
    norm = {_normalise(col): col for col in header}
    for cand in candidates:
        key = _normalise(cand)
        if key in norm:
            return norm[key]
        for norm_key, original in norm.items():
            if norm_key.startswith(key) or key in norm_key:
                return original
    return None


def _build_records(header: List[str], rows: List[List[Any]]) -> List[Dict[str, Any]]:
    records = []
    for row in rows:
        if all(_is_empty(value) for value in row):
            continue
        record = {}
        for col, value in zip(header, row):
            record[col] = value
        records.append(record)
    return records


def load_input_excel(
    path: str,
    site_cfg: Dict[str, Any],
    *,
    dt_hours: Optional[float] = None,
    tz: Optional[str] = None,
    input_time_is_local: Optional[bool] = None,
    duplicate_strategy: str = "drop_first",
    gap_strategy: str = "ffill",
    ambiguous_policy: str = "first",
) -> TimeSeriesTable:
    resolved_path = _resolve_input_path(path, site_cfg)
    header, rows = _read_tabular(resolved_path, site_cfg.get("sheet_name"))
    _require(header, f"Input file {resolved_path} contains no data")
    records = _build_records(header, rows)

    time_col = _find_time_column(header)
    records = [rec for rec in records if not _is_empty(rec.get(time_col))]
    _require(records, f"Time column '{time_col}' contains no valid values.")
    timestamps = [_parse_datetime(rec[time_col]) for rec in records]

    year_target = site_cfg.get("year_target")
    if year_target is not None:
        year_target = int(year_target)
        filtered = [(ts, rec) for ts, rec in zip(timestamps, records) if ts.year == year_target]
        _require(filtered, f"Im Zieljahr {year_target} keine Daten.")
        timestamps = [ts for ts, _ in filtered]
        records = [rec for _, rec in filtered]

    combined = sorted(zip(timestamps, records), key=lambda item: item[0])
    unique_ts: List[datetime] = []
    unique_records: List[Dict[str, Any]] = []
    seen = set()
    for ts, rec in combined:
        if ts in seen:
            continue
        seen.add(ts)
        unique_ts.append(ts)
        unique_records.append(rec)
    timestamps = unique_ts
    records = unique_records

    cols_cfg = site_cfg.get("columns", {})
    def pick(name: str, fallbacks: List[str]) -> str:
        if name in cols_cfg and cols_cfg[name]:
            value = cols_cfg[name]
            if isinstance(value, str):
                col = _map_column(header, [value])
            else:
                col = _map_column(header, [str(v) for v in value])
            if col:
                return col
        col = _map_column(header, fallbacks)
        _require(col is not None, f"Missing column for {name}")
        return col

    price_col = pick("price_candidates", ["Day_Ahead_Price €/MWh", "strompreis"])
    heat_col = pick("heat_candidates", ["Wärmebedarf MW", "waermebedarf"])
    co2_col = pick("co2_candidates", ["CO2_consumption_based kgCO2/MWh", "co2"])

    # Outdoor temperature for heating curve (optional)
    outdoor_temp_col = _map_column(header, [
        "Außentemperatur °C",
        "Außentemperatur",
        "aussentemperatur",
        "outdoor_temp",
        "T_outdoor",
        "T_amb",
        "Ambient_Temp",
        "ambient_temperature",
        "temperature_c",
    ])
    if "outdoor_temp_candidates" in cols_cfg:
        custom_col = cols_cfg["outdoor_temp_candidates"]
        if isinstance(custom_col, str):
            outdoor_temp_col = _map_column(header, [custom_col]) or outdoor_temp_col
        elif isinstance(custom_col, list):
            outdoor_temp_col = _map_column(header, custom_col) or outdoor_temp_col

    wrg_cols: Dict[int, Dict[str, Optional[str]]] = {}
    for i in range(1, 5):
        q_key = f"wrg{i}_q_candidates"
        t_key = f"wrg{i}_t_candidates"
        wrg_cols[i] = {
            "q": pick(q_key, []) if q_key in cols_cfg else _map_column(header, [
                f"WRG{i}Q MW",
                f"WRG{i} Q MW",
                f"WRG{i}_Q MW",
                f"WRG{i}_Q MW_th",
                f"wrg{i}qmw",
            ]),
            "t": pick(t_key, []) if t_key in cols_cfg else _map_column(header, [
                f"WRG{i}_T °C",
                f"WRG{i} T °C",
                f"wrg{i} temp c",
            ]),
        }

    price = [_to_float(rec.get(price_col)) for rec in records]
    heat = [_to_float(rec.get(heat_col)) for rec in records]
    co2 = [_to_float(rec.get(co2_col)) for rec in records]

    # Outdoor temperature (optional, for heating curve)
    outdoor_temp: List[float] = []
    if outdoor_temp_col:
        outdoor_temp = [_to_float(rec.get(outdoor_temp_col)) for rec in records]
        logger.info(f"[LOAD] Outdoor temperature found: column '{outdoor_temp_col}'")
    else:
        logger.info("[LOAD] No outdoor temperature column found (heating curve disabled)")

    data: Dict[str, List[float]] = {
        "strompreis_EUR_MWh": price,
        "waermebedarf_MWth": heat,
        "grid_co2_kg_MWh": co2,
    }

    # Add outdoor temperature if available
    if outdoor_temp and any(t == t for t in outdoor_temp):  # Check for non-NaN values
        data["outdoor_temp_C"] = outdoor_temp

    for i in range(1, 5):
        q_col = wrg_cols[i]["q"]
        t_col = wrg_cols[i]["t"]
        if q_col:
            data[f"WRG{i}_Q_cap"] = [_to_float(rec.get(q_col)) for rec in records]
        if t_col:
            temps = [_to_float(rec.get(t_col)) for rec in records]
            data[f"WRG{i}_T_K"] = [temp + 273.15 if temp == temp else temp for temp in temps]

    # fill missing numbers using simple forward/backward fill
    for key, values in data.items():
        data[key] = fill_gaps(values)
        _require(all(v == v for v in data[key]), f"NaN in column {key}")

    dt_hours = float(dt_hours if dt_hours is not None else site_cfg.get("dt_h", 1.0))

    def _resample_regular(ts: List[datetime], values: Dict[str, List[float]], step_hours: float) -> TimeSeriesTable:
        step = timedelta(hours=step_hours)
        target: List[datetime] = []
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

    table = _resample_regular(timestamps, data, dt_hours)

    if table.data["waermebedarf_MWth"] and max(table.data["waermebedarf_MWth"]) == 0:
        raise RuntimeError("Heat demand is zero everywhere. Please check column mapping.")

    logger.info(
        "[LOAD] %s -> %d steps from %s to %s",
        os.path.basename(path), len(table), table.index[0], table.index[-1],
    )

    return table

