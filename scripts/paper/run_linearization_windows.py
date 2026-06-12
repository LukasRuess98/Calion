"""
Run multi-window L3+ vs L3NL linearization validation.

Default workflow:
  - Reuse the existing January 2025 744 h validation artefacts.
  - Solve May and August 2025 windows in parallel.
  - For each new window, solve L3plus MILP first, then L3NL MIQCP on the
    identical horizon, warm-started from that window's L3plus dispatch.
  - Write CSV/JSON summaries and update level_consistency.json.

Examples
--------
    python scripts/paper/run_linearization_windows.py --dry-run
    python scripts/paper/run_linearization_windows.py
    python scripts/paper/run_linearization_windows.py --windows aug_2025 --workers 1
    python scripts/paper/run_linearization_windows.py --annual-only --dry-run
    python scripts/paper/run_linearization_windows.py --annual-only --threads 56 --time-limit 86400
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import re
import shutil
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.paper.extract_artefacts import extract_all
from scripts.paper.run_paper_full import CONFIGS, OUT_BASE, _deep_merge, _dump_yaml, _load_yaml

MILP_CONFIG = CONFIGS / "Memmingen_L3_MILP.yaml"
MIQCP_CONFIG = CONFIGS / "Memmingen_L3_NLP.yaml"

OUT_WINDOWS_EXACT = OUT_BASE / "linearization_windows"
OUT_WINDOWS_STAGNATION = OUT_BASE / "linearization_windows_stagnation"
OUT_WINDOWS = OUT_WINDOWS_EXACT
RUNTIME_RESULTS_SUBDIR = "linearization_windows"
TMP_CONFIG_DIR = OUT_WINDOWS / "_tmp_configs"
SUMMARY_CSV = OUT_WINDOWS / "linearization_windows_summary.csv"
SUMMARY_JSON = OUT_WINDOWS / "linearization_windows_summary.json"
LEVEL_CONSISTENCY = OUT_BASE / "level_consistency.json"

REUSE_JAN_SOURCE = OUT_BASE / "_week_linearization"
REUSE_ANNUAL_L3PLUS_SOURCE = OUT_BASE / "L3plus"
REUSED_JAN_MIQCP_GAP_PCT = 1.99


@dataclass(frozen=True)
class WindowSpec:
    name: str
    label: str
    start: str
    end: str
    in_headline: bool = True

    @property
    def hours(self) -> int:
        import pandas as pd

        start_dt = pd.Timestamp(self.start)
        end_dt = pd.Timestamp(self.end)
        return int((end_dt - start_dt).total_seconds() // 3600) + 1


WINDOWS: dict[str, WindowSpec] = {
    "jan_2025": WindowSpec(
        name="jan_2025",
        label="Jan. 2025",
        start="2025-01-01 00:00",
        end="2025-01-31 23:00",
    ),
    "feb_2025": WindowSpec(
        name="feb_2025",
        label="Feb. 2025",
        start="2025-02-01 00:00",
        end="2025-02-28 23:00",
    ),
    "may_2025": WindowSpec(
        name="may_2025",
        label="May 2025",
        start="2025-05-01 00:00",
        end="2025-05-31 23:00",
    ),
    "aug_2025": WindowSpec(
        name="aug_2025",
        label="Aug. 2025",
        start="2025-08-01 00:00",
        end="2025-08-31 23:00",
    ),
    "may_2025_168h": WindowSpec(
        name="may_2025_168h",
        label="May 2025 (168 h)",
        start="2025-05-01 00:00",
        end="2025-05-07 23:00",
        in_headline=False,
    ),
    "may_2025_mid_168h": WindowSpec(
        name="may_2025_mid_168h",
        label="May 2025 mid-month (168 h)",
        start="2025-05-15 00:00",
        end="2025-05-21 23:00",
        in_headline=False,
    ),
    "aug_2025_168h": WindowSpec(
        name="aug_2025_168h",
        label="Aug. 2025 (168 h)",
        start="2025-08-01 00:00",
        end="2025-08-07 23:00",
        in_headline=False,
    ),
    "aug_2025_mid_168h": WindowSpec(
        name="aug_2025_mid_168h",
        label="Aug. 2025 mid-month (168 h)",
        start="2025-08-15 00:00",
        end="2025-08-21 23:00",
        in_headline=False,
    ),
}
DEFAULT_WINDOW_NAMES = ["jan_2025", "may_2025", "aug_2025"]

ANNUAL_PROBE = WindowSpec(
    name="annual_2025_probe",
    label="Annual 2025 probe",
    start="2025-01-01 00:00",
    end="2025-12-31 23:00",
    in_headline=False,
)

SUMMARY_FIELDS = [
    "window",
    "label",
    "start",
    "end",
    "hours",
    "in_headline",
    "miqcp_variant",
    "fixed_regime_warmstart",
    "milp_status",
    "miqcp_status",
    "milp_cost_eur",
    "miqcp_cost_eur",
    "signed_error_pct",
    "abs_error_pct",
    "abs_diff_eur",
    "miqcp_gap_pct",
    "miqcp_best_bound_eur",
    "miqcp_abs_gap_eur",
    "milp_solve_s",
    "miqcp_solve_s",
    "stagnation_threshold_frac",
    "stagnation_hours",
    "stagnation_counterfactual_loss_mwh",
    "stagnation_counterfactual_loss_pct_demand",
    "usable",
    "source",
    "note",
]


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}min"
    return f"{seconds / 3600:.1f}h"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_first_csv_row(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return next(reader, {})
    except Exception:
        return {}


def _read_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _sum_csv_column(path: Path, column: str) -> float | None:
    if not path.exists():
        return None
    total = 0.0
    seen = False
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                value = _safe_float(row.get(column))
                if value is None:
                    continue
                total += value
                seen = True
    except Exception:
        return None
    return total if seen else None


def _extract_gap_from_log(log_path: Path) -> dict[str, float | None]:
    """Return the last Gurobi objective/bound/gap triple found in a log."""
    if not log_path.exists():
        return {"objective": None, "bound": None, "gap_pct": None}

    pattern = re.compile(
        r"Best objective\s+([+\-\deE.]+|-),\s+best bound\s+([+\-\deE.]+|-),\s+gap\s+([+\-\deE.]+)%"
    )
    last: dict[str, float | None] = {"objective": None, "bound": None, "gap_pct": None}
    try:
        for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = pattern.search(line)
            if not match:
                continue
            obj, bound, gap = match.groups()
            last = {
                "objective": _safe_float(obj),
                "bound": _safe_float(bound),
                "gap_pct": _safe_float(gap),
            }
    except Exception:
        return last
    return last


def _stagnation_diagnostics(
    spec: WindowSpec,
    miqcp_level: str,
    threshold_frac: float | None,
) -> dict[str, float | None]:
    if not miqcp_level.startswith("L3NL-S"):
        return {
            "stagnation_threshold_frac": None,
            "stagnation_hours": None,
            "stagnation_counterfactual_loss_mwh": None,
            "stagnation_counterfactual_loss_pct_demand": None,
        }

    candidates = [
        _runtime_export_dir(spec.name, miqcp_level) / "thermal_network" / "pipes" / "pipes_summary.json",
        _window_dir(spec.name, miqcp_level) / "thermal_network" / "pipes" / "pipes_summary.json",
    ]
    pipe_rows: list[dict] = []
    for path in candidates:
        pipe_rows = _read_json_list(path)
        if pipe_rows:
            break

    stagnation_hours = 0.0
    stagnation_loss_mwh = 0.0
    for row in pipe_rows:
        stagnation_hours += _safe_float(row.get("stagnation_hours")) or 0.0
        stagnation_loss_mwh += _safe_float(row.get("stagnation_counterfactual_loss_mwh")) or 0.0

    demand_mwh = _sum_csv_column(_window_dir(spec.name, "L3plus") / "dispatch_hourly.csv", "Q_demand_total_MW")
    loss_pct_demand = (
        stagnation_loss_mwh / demand_mwh * 100.0
        if demand_mwh and demand_mwh > 0 else None
    )
    return {
        "stagnation_threshold_frac": threshold_frac,
        "stagnation_hours": round(stagnation_hours, 2) if pipe_rows else None,
        "stagnation_counterfactual_loss_mwh": (
            round(stagnation_loss_mwh, 4) if pipe_rows else None
        ),
        "stagnation_counterfactual_loss_pct_demand": (
            round(loss_pct_demand, 4) if loss_pct_demand is not None else None
        ),
    }


def _existing_january_gap_pct() -> float | None:
    payload = _read_json(LEVEL_CONSISTENCY)
    lin = payload.get("linearization_error") or {}
    note = str(lin.get("note") or "")
    match = re.search(r"gap[^:]*:\s*([0-9]+(?:\.[0-9]+)?)\s*%", note, re.IGNORECASE)
    if match:
        return _safe_float(match.group(1))
    return None


def _sanitize_output_suffix(output_suffix: str | None) -> str:
    if not output_suffix:
        return ""
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "_", output_suffix.strip())
    suffix = suffix.strip("._-")
    if not suffix:
        raise ValueError(f"Invalid empty output suffix derived from {output_suffix!r}")
    return suffix


def _configure_output_profile(low_load_stagnation: bool, output_suffix: str | None = None) -> None:
    """Switch generated artefacts between exact/L3NL-S trees, optionally suffixed."""
    global OUT_WINDOWS, RUNTIME_RESULTS_SUBDIR, TMP_CONFIG_DIR, SUMMARY_CSV, SUMMARY_JSON
    suffix = _sanitize_output_suffix(output_suffix)
    profile_name = "linearization_windows_stagnation" if low_load_stagnation else "linearization_windows"
    if suffix:
        profile_name = f"{profile_name}_{suffix}"
    OUT_WINDOWS = OUT_BASE / profile_name
    RUNTIME_RESULTS_SUBDIR = profile_name
    TMP_CONFIG_DIR = OUT_WINDOWS / "_tmp_configs"
    SUMMARY_CSV = OUT_WINDOWS / "linearization_windows_summary.csv"
    SUMMARY_JSON = OUT_WINDOWS / "linearization_windows_summary.json"


def _miqcp_level_name(
    spec: WindowSpec,
    low_load_stagnation: bool,
    fix_l3nl_s_regimes: bool = False,
    relax_l3nl_s_active: bool = False,
) -> str:
    if low_load_stagnation and spec.name != "jan_2025":
        if fix_l3nl_s_regimes and relax_l3nl_s_active:
            return "L3NL-S-FR-ACTREL"
        return "L3NL-S-FR" if fix_l3nl_s_regimes else "L3NL-S"
    return "L3NL"


def _window_dir(window: str, level: str | None = None) -> Path:
    base = OUT_WINDOWS / window
    return base / level if level else base


def _runtime_export_dir(window: str, level: str) -> Path:
    return ROOT / "output" / "results" / RUNTIME_RESULTS_SUBDIR / window / level


def _log_path(window: str, level: str) -> Path:
    return _window_dir(window) / "logs" / f"{window}_{level}.log"


def _assert_under_output(path: Path) -> None:
    resolved = path.resolve()
    root = OUT_WINDOWS.resolve()
    if root not in [resolved, *resolved.parents]:
        raise RuntimeError(f"Refusing to remove path outside {OUT_WINDOWS}: {path}")


def _copy_reused_january(force: bool = False) -> None:
    """Copy existing January artefacts into the new multi-window layout."""
    mappings = {
        "L3plus": REUSE_JAN_SOURCE / "L3plus",
        "L3NL": REUSE_JAN_SOURCE / "L3NL",
    }
    for level, src in mappings.items():
        dst = _window_dir("jan_2025", level)
        if not src.exists():
            raise RuntimeError(f"Cannot reuse January artefacts, missing {src}")
        if dst.exists():
            if not force:
                continue
            _assert_under_output(dst)
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)


def _copy_reused_annual_l3plus(force: bool = False) -> None:
    """Copy the existing annual L3plus MILP result for the annual MIQCP probe."""
    src = REUSE_ANNUAL_L3PLUS_SOURCE
    dst = _window_dir(ANNUAL_PROBE.name, "L3plus")
    if not src.exists():
        raise RuntimeError(f"Cannot reuse annual L3plus artefacts, missing {src}")
    if dst.exists():
        if not force:
            return
        _assert_under_output(dst)
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def _base_horizon_override(spec: WindowSpec) -> dict:
    return {
        "scenario": {
            "horizon": {
                "start": spec.start,
                "end": spec.end,
            }
        }
    }


def _parity_overrides_from_milp() -> dict:
    """Keep L3NL economically identical to L3plus, changing only physics/form."""
    milp_cfg = _load_yaml(MILP_CONFIG)
    shared: dict[str, Any] = {}
    for key in ["assets", "heat_pumps", "grid", "fuels", "costs"]:
        if key in milp_cfg:
            shared[key] = copy.deepcopy(milp_cfg[key])

    network_src = milp_cfg.get("network", {}) or {}
    network_shared: dict[str, Any] = {}
    for key in [
        "supply_temp_c",
        "return_temp_c",
        "ground_temp_c",
        "temperature_frame",
        "heating_curve",
        "max_velocity_m_s",
        "pump_efficiency",
        "pipe_roughness_mm",
        "max_pressure_drop_bar",
        "delta_p_min_consumer_bar",
        "pipes",
    ]:
        if key in network_src:
            network_shared[key] = copy.deepcopy(network_src[key])
    if network_shared:
        shared["network"] = network_shared
    return shared


def _milp_overrides(spec: WindowSpec, threads: int) -> dict:
    log_path = _log_path(spec.name, "L3plus").resolve()
    export_dir = _runtime_export_dir(spec.name, "L3plus").resolve()
    base = {
        "scenario": {"milp_linearize": True},
        "network": {
            "milp_linearize": True,
            "physics": {
                "heat_loss": True,
                "pressure_drop": True,
                "transport_delay": True,
            },
        },
        "run": {
            "solver": "gurobi",
            "solver_options": {
                "Threads": int(threads),
                "LogFile": str(log_path),
                "OutputFlag": 1,
                "LogToConsole": 0,
            },
        },
        "output": {
            "export_dir": str(export_dir),
            "export_thermal_network": True,
            "export_solver_solution": False,
        },
    }
    return _deep_merge(base, _base_horizon_override(spec))


def _solver_option_tuning(args: dict) -> dict:
    options: dict[str, Any] = {
        "MIPFocus": int(args["mip_focus"]),
        "Heuristics": float(args["heuristics"]),
        "NumericFocus": int(args["numeric_focus"]),
    }
    if args.get("nodefile_start") is not None:
        nodefile_dir = Path(args["nodefile_dir"]).resolve()
        nodefile_dir.mkdir(parents=True, exist_ok=True)
        options["NodefileStart"] = float(args["nodefile_start"])
        options["NodefileDir"] = str(nodefile_dir)
    if args.get("no_rel_heur_time") is not None:
        options["NoRelHeurTime"] = int(args["no_rel_heur_time"])
    if args.get("improve_start_time") is not None:
        options["ImproveStartTime"] = int(args["improve_start_time"])
    if args.get("diagnose_inf_unbd"):
        # Makes Gurobi disambiguate INF_OR_UNBD into infeasible vs unbounded.
        options["DualReductions"] = 0
        options["InfUnbdInfo"] = 1
    options.update(args.get("custom_solver_options") or {})
    return options


def _parse_solver_option_value(raw: str) -> Any:
    value = raw.strip()
    lower = value.lower()
    if lower in {"true", "yes", "on"}:
        return 1
    if lower in {"false", "no", "off"}:
        return 0
    try:
        if re.fullmatch(r"[+-]?\d+", value):
            return int(value)
        return float(value)
    except ValueError:
        return value


def _parse_solver_options(items: list[str] | None) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"Expected --solver-option KEY=VALUE, got {item!r}")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Empty Gurobi parameter name in {item!r}")
        parsed[key] = _parse_solver_option_value(raw_value)
    return parsed


def _warmstart_mode_options(mode: str) -> dict[str, bool]:
    """Map a named experiment mode to the warmstart hint classes."""
    modes: dict[str, dict[str, bool]] = {
        "full": {
            "warmstart_pipe_binaries": True,
            "warmstart_dispatch_binaries": True,
            "warmstart_pipe_continuous": True,
            "warmstart_dispatch_continuous": True,
            "warmstart_model_defaults": True,
            "warmstart_clear_unset_continuous": False,
        },
        # Keeps all operational dispatch hints, but lets L3NL-S rebuild the
        # temperature/loss pipe state that differs from the MILP approximation.
        "no-pipe-state": {
            "warmstart_pipe_binaries": True,
            "warmstart_dispatch_binaries": True,
            "warmstart_pipe_continuous": False,
            "warmstart_dispatch_continuous": True,
            "warmstart_model_defaults": True,
            "warmstart_clear_unset_continuous": True,
        },
        # Gives Gurobi only the integer structure and lets it complete all
        # continuous values. This is often better when the source solution is
        # physically close but not exactly feasible for the MIQCP equations.
        "binary-only": {
            "warmstart_pipe_binaries": True,
            "warmstart_dispatch_binaries": True,
            "warmstart_pipe_continuous": False,
            "warmstart_dispatch_continuous": False,
            "warmstart_model_defaults": False,
            "warmstart_clear_unset_continuous": True,
        },
        "dispatch-only": {
            "warmstart_pipe_binaries": False,
            "warmstart_dispatch_binaries": True,
            "warmstart_pipe_continuous": False,
            "warmstart_dispatch_continuous": True,
            "warmstart_model_defaults": True,
            "warmstart_clear_unset_continuous": True,
        },
        "pipe-regime-only": {
            "warmstart_pipe_binaries": True,
            "warmstart_dispatch_binaries": False,
            "warmstart_pipe_continuous": False,
            "warmstart_dispatch_continuous": False,
            "warmstart_model_defaults": False,
            "warmstart_clear_unset_continuous": True,
        },
    }
    try:
        return modes[mode]
    except KeyError as exc:
        raise ValueError(f"Unknown warmstart mode: {mode}") from exc


def _miqcp_overrides(spec: WindowSpec, args: dict) -> dict:
    threads = int(args["threads"])
    time_limit = int(args["time_limit"])
    low_load_stagnation = bool(args.get("low_load_stagnation", False))
    fix_l3nl_s_regimes = bool(args.get("fix_l3nl_s_regimes", False))
    relax_l3nl_s_active = bool(args.get("relax_l3nl_s_active", False))
    fixed_regime_run = low_load_stagnation and fix_l3nl_s_regimes and spec.name != "jan_2025"
    miqcp_level = _miqcp_level_name(
        spec,
        low_load_stagnation,
        fixed_regime_run,
        relax_l3nl_s_active,
    )
    log_path = _log_path(spec.name, miqcp_level).resolve()
    export_dir = _runtime_export_dir(spec.name, miqcp_level).resolve()
    warmstart_dir = _window_dir(spec.name, "L3plus").resolve()
    warmstart_mode = str(args.get("warmstart_mode", "full"))
    network_override: dict[str, Any] = {
        "milp_linearize": False,
        "physics": {
            "heat_loss": True,
            "pressure_drop": True,
            "transport_delay": True,
        },
    }
    if low_load_stagnation and miqcp_level.startswith("L3NL-S"):
        network_override["physics"]["stagnation_mode"] = "binary"
        network_override["parameters"] = {
            "stagnation_flow_threshold_rel_maxflow_frac": float(
                args.get("stagnation_threshold_frac", 0.01)
            ),
            "stagnation_flow_threshold_abs_min_kg_s": float(
                args.get("stagnation_threshold_abs_min_kg_s", 0.25)
            ),
            "stagnation_flow_threshold_abs_max_kg_s": float(
                args.get("stagnation_threshold_abs_max_kg_s", 5.0)
            ),
        }
    base = _deep_merge(_parity_overrides_from_milp(), {
        "scenario": {"milp_linearize": False},
        "network": network_override,
        "run": {
            "solver": "gurobi",
            "warmstart_from": str(warmstart_dir),
            "fix_binaries_from_warmstart": fixed_regime_run,
            "relax_pipe_active_in_warmstart_fix": fixed_regime_run and relax_l3nl_s_active,
            **_warmstart_mode_options(warmstart_mode),
            "solver_options": {
                "NonConvex": 2,
                "MIPGap": 0.005,
                "TimeLimit": int(time_limit),
                "Threads": int(threads),
                "LogFile": str(log_path),
                "OutputFlag": 1,
                "LogToConsole": 0,
                **_solver_option_tuning(args),
            },
        },
        "output": {
            "export_dir": str(export_dir),
            "export_thermal_network": True,
            "export_solver_solution": False,
        },
    })
    return _deep_merge(base, _base_horizon_override(spec))


def _run_with_overrides(
    config_path: Path,
    overrides: dict,
    run_id: str,
    outdir: Path,
) -> dict:
    """Run one workflow from a temporary config and extract paper artefacts."""
    from calion.run.workflow import run_workflow

    TMP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg = _load_yaml(config_path)
    cfg = _deep_merge(cfg, copy.deepcopy(overrides))
    tmp = TMP_CONFIG_DIR / f"_tmp_{run_id}_{uuid.uuid4().hex[:8]}.yaml"
    _dump_yaml(cfg, tmp)

    t0 = time.perf_counter()
    try:
        workflow = run_workflow([str(tmp)])
        elapsed = time.perf_counter() - t0
        extract_all(
            run_id=run_id,
            config_path=str(config_path),
            workflow=workflow,
            solve_time_s=elapsed,
            outdir=outdir,
        )
        return {"status": "ok", "elapsed_s": elapsed}
    finally:
        tmp.unlink(missing_ok=True)


def _is_completed(outdir: Path) -> bool:
    return (outdir / "meta.json").exists() and (outdir / "economics.csv").exists()


def _run_window_worker(job: dict) -> dict:
    _configure_output_profile(
        bool(job.get("low_load_stagnation", False)),
        job.get("output_suffix"),
    )
    spec = WindowSpec(**job["spec"])
    threads = int(job["threads"])
    force = bool(job["force"])
    force_miqcp = bool(job.get("force_miqcp", False))
    reuse_l3plus = bool(job.get("reuse_l3plus", False))
    miqcp_args = job["miqcp_args"]
    low_load_stagnation = bool(miqcp_args.get("low_load_stagnation", False))
    fix_l3nl_s_regimes = bool(miqcp_args.get("fix_l3nl_s_regimes", False))
    relax_l3nl_s_active = bool(miqcp_args.get("relax_l3nl_s_active", False))
    miqcp_level = _miqcp_level_name(
        spec,
        low_load_stagnation,
        fix_l3nl_s_regimes,
        relax_l3nl_s_active,
    )

    window_base = _window_dir(spec.name)
    (window_base / "logs").mkdir(parents=True, exist_ok=True)

    milp_dir = _window_dir(spec.name, "L3plus")
    miqcp_dir = _window_dir(spec.name, miqcp_level)

    result: dict[str, Any] = {
        "window": spec.name,
        "milp": {"status": "skipped_existing"},
        "miqcp": {"status": "skipped_existing"},
    }

    if force and milp_dir.exists() and not reuse_l3plus:
        _assert_under_output(milp_dir)
        shutil.rmtree(milp_dir)
    if (force or force_miqcp) and miqcp_dir.exists():
        _assert_under_output(miqcp_dir)
        shutil.rmtree(miqcp_dir)

    if reuse_l3plus and not _is_completed(milp_dir):
        raise RuntimeError(f"Requested L3plus reuse for {spec.name}, but artefacts are incomplete in {milp_dir}")

    if not reuse_l3plus and not _is_completed(milp_dir):
        result["milp"] = _run_with_overrides(
            MILP_CONFIG,
            _milp_overrides(spec, threads),
            f"{spec.name}_L3plus",
            milp_dir,
        )

    if not _is_completed(miqcp_dir):
        result["miqcp"] = _run_with_overrides(
            MIQCP_CONFIG,
            _miqcp_overrides(spec, miqcp_args),
            f"{spec.name}_{miqcp_level}",
            miqcp_dir,
        )

    return result


def _summarize_window(
    spec: WindowSpec,
    source: str = "computed",
    low_load_stagnation: bool = False,
    stagnation_threshold_frac: float | None = None,
    fix_l3nl_s_regimes: bool = False,
    relax_l3nl_s_active: bool = False,
) -> dict:
    milp_dir = _window_dir(spec.name, "L3plus")
    miqcp_level = _miqcp_level_name(
        spec,
        low_load_stagnation,
        fix_l3nl_s_regimes,
        relax_l3nl_s_active,
    )
    miqcp_dir = _window_dir(spec.name, miqcp_level)

    milp_meta = _read_json(milp_dir / "meta.json")
    miqcp_meta = _read_json(miqcp_dir / "meta.json")
    milp_eco = _read_first_csv_row(milp_dir / "economics.csv")
    miqcp_eco = _read_first_csv_row(miqcp_dir / "economics.csv")

    milp_cost = _safe_float(milp_eco.get("cost_total_eur"))
    miqcp_cost = _safe_float(miqcp_eco.get("cost_total_eur"))
    gap_data = _extract_gap_from_log(_log_path(spec.name, miqcp_level))
    miqcp_gap_pct = gap_data.get("gap_pct")
    miqcp_best_bound = gap_data.get("bound")
    miqcp_abs_gap = None
    if gap_data.get("objective") is not None and miqcp_best_bound is not None:
        miqcp_abs_gap = abs(float(gap_data["objective"]) - float(miqcp_best_bound))
    if miqcp_gap_pct is None and spec.name == "jan_2025":
        miqcp_gap_pct = _existing_january_gap_pct()
    if miqcp_gap_pct is None and spec.name == "jan_2025" and source == "reused_existing":
        miqcp_gap_pct = REUSED_JAN_MIQCP_GAP_PCT

    signed_error = None
    abs_error = None
    abs_diff = None
    usable = False
    note = ""
    if milp_cost is not None and miqcp_cost is not None and abs(miqcp_cost) > 1e-9:
        signed_error = (milp_cost - miqcp_cost) / abs(miqcp_cost) * 100
        abs_error = abs(signed_error)
        abs_diff = abs(milp_cost - miqcp_cost)
        usable = True
    else:
        note = "Missing or zero-cost MIQCP incumbent; not usable for headline KPI."

    stagnation_diag = _stagnation_diagnostics(
        spec,
        miqcp_level,
        stagnation_threshold_frac if miqcp_level.startswith("L3NL-S") else None,
    )
    if miqcp_level == "L3NL-S-FR-ACTREL":
        miqcp_variant = "L3NL-S fixed-regime active-relaxed"
    elif miqcp_level == "L3NL-S-FR":
        miqcp_variant = "L3NL-S fixed-regime"
    elif miqcp_level == "L3NL-S":
        miqcp_variant = "L3NL-S"
    else:
        miqcp_variant = "exact L3NL"

    return {
        "window": spec.name,
        "label": spec.label,
        "start": spec.start,
        "end": spec.end,
        "hours": spec.hours,
        "in_headline": spec.in_headline,
        "miqcp_variant": miqcp_variant,
        "fixed_regime_warmstart": miqcp_level.startswith("L3NL-S-FR"),
        "milp_status": milp_meta.get("solver_status"),
        "miqcp_status": miqcp_meta.get("solver_status"),
        "milp_cost_eur": round(milp_cost, 2) if milp_cost is not None else None,
        "miqcp_cost_eur": round(miqcp_cost, 2) if miqcp_cost is not None else None,
        "signed_error_pct": round(signed_error, 3) if signed_error is not None else None,
        "abs_error_pct": round(abs_error, 3) if abs_error is not None else None,
        "abs_diff_eur": round(abs_diff, 2) if abs_diff is not None else None,
        "miqcp_gap_pct": round(miqcp_gap_pct, 4) if miqcp_gap_pct is not None else None,
        "miqcp_best_bound_eur": (
            round(miqcp_best_bound, 2) if miqcp_best_bound is not None else None
        ),
        "miqcp_abs_gap_eur": round(miqcp_abs_gap, 2) if miqcp_abs_gap is not None else None,
        "milp_solve_s": _safe_float(milp_meta.get("solve_time_s")),
        "miqcp_solve_s": _safe_float(miqcp_meta.get("solve_time_s")),
        **stagnation_diag,
        "usable": usable,
        "source": source,
        "note": note,
    }


def _write_summary(rows: list[dict]) -> None:
    OUT_WINDOWS.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in SUMMARY_FIELDS})

    usable_headline = [
        row for row in rows
        if row.get("in_headline") and row.get("usable")
    ]
    payload = {
        "windows": rows,
        "summary": {
            "n_windows": len(rows),
            "n_headline_windows": sum(1 for row in rows if row.get("in_headline")),
            "n_usable_headline_windows": len(usable_headline),
            "max_abs_error_pct": (
                max(row["abs_error_pct"] for row in usable_headline if row.get("abs_error_pct") is not None)
                if usable_headline else None
            ),
            "min_signed_error_pct": (
                min(row["signed_error_pct"] for row in usable_headline if row.get("signed_error_pct") is not None)
                if usable_headline else None
            ),
            "max_signed_error_pct": (
                max(row["signed_error_pct"] for row in usable_headline if row.get("signed_error_pct") is not None)
                if usable_headline else None
            ),
            "passes_minimum_evidence": len(usable_headline) >= 2,
        },
    }
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _update_level_consistency(rows: list[dict], low_load_stagnation: bool = False) -> None:
    payload = _read_json(LEVEL_CONSISTENCY)
    if not payload:
        payload = {"checks": [], "summary": {}, "costs_eur": {}}

    if low_load_stagnation:
        payload["linearization_windows_low_load_stagnation"] = rows
        LEVEL_CONSISTENCY.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return

    payload["linearization_windows"] = rows

    usable = [
        row for row in rows
        if row.get("in_headline") and row.get("usable") and row.get("abs_error_pct") is not None
    ]
    if usable:
        worst = max(usable, key=lambda row: row["abs_error_pct"])
        payload["linearization_error"] = {
            "method": "multi_window_744h",
            "n_windows": len(rows),
            "n_usable_headline_windows": len(usable),
            "max_abs_error_pct": worst.get("abs_error_pct"),
            "signed_error_pct": worst.get("signed_error_pct"),
            "abs_error_pct": worst.get("abs_error_pct"),
            "abs_diff_eur": worst.get("abs_diff_eur"),
            "window": worst.get("window"),
            "window_start": worst.get("start"),
            "window_end": worst.get("end"),
            "note": (
                "Multi-window 744 h L3plus MILP vs L3NL MIQCP validation. "
                "Full-year MIQCP is treated as probe-only because prior annual "
                "runs did not produce a usable incumbent within 24 h."
            ),
        }

    replaced_checks = {
        "linearization_error_L3_vs_L3NL",
        "linearization_error_L3plus_vs_L3NL_windows",
    }
    checks = [
        check for check in payload.get("checks", [])
        if check.get("check") not in replaced_checks
    ]
    checks.append({
        "check": "linearization_error_L3plus_vs_L3NL_windows",
        "pass": len(usable) >= 2,
        "detail": (
            f"{len(usable)} usable 744 h L3plus/L3NL window(s); "
            f"minimum reviewer-response target is 2."
        ),
        "usable_windows": [row.get("window") for row in usable],
    })
    payload["checks"] = checks
    payload.setdefault("summary", {}).update({
        "n_checks": len(checks),
        "n_pass": sum(1 for check in checks if check.get("pass", True)),
        "n_fail": sum(1 for check in checks if not check.get("pass", True)),
    })

    LEVEL_CONSISTENCY.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _selected_windows(names: list[str] | None, annual_probe: bool, annual_only: bool) -> list[WindowSpec]:
    if annual_only:
        return [ANNUAL_PROBE]
    selected = [WINDOWS[name] for name in (names or DEFAULT_WINDOW_NAMES)]
    if annual_probe:
        selected.append(ANNUAL_PROBE)
    return selected


def _print_dry_run(windows: list[WindowSpec], args: argparse.Namespace) -> None:
    print("=" * 72)
    print("Linearization window validation dry run")
    print("=" * 72)
    print(f"Output:              {OUT_WINDOWS}")
    print(f"Workers:             {args.workers}")
    print(f"Gurobi threads/run:  {args.threads}")
    print(f"MIQCP TimeLimit:     {args.time_limit}s")
    print(f"Warmstart mode:      {args.warmstart_mode}")
    if args.output_suffix:
        print(f"Output suffix:       {_sanitize_output_suffix(args.output_suffix)}")
    if args.low_load_stagnation and args.fix_l3nl_s_regimes and args.relax_l3nl_s_active:
        variant_label = "L3NL-S-FR-ACTREL active-relaxed sensitivity"
    elif args.low_load_stagnation and args.fix_l3nl_s_regimes:
        variant_label = "L3NL-S-FR fixed-regime sensitivity"
    elif args.low_load_stagnation:
        variant_label = "L3NL-S low-load stagnation"
    else:
        variant_label = "exact L3NL"
    print(f"MIQCP variant:       {variant_label}")
    if args.low_load_stagnation:
        print(
            "Stagnation threshold:"
            f" frac={args.stagnation_threshold_frac},"
            f" min={args.stagnation_threshold_abs_min_kg_s} kg/s,"
            f" max={args.stagnation_threshold_abs_max_kg_s} kg/s"
        )
    print(f"Reuse January:       {not args.no_reuse_jan}")
    print(f"Reuse annual L3plus: {args.reuse_annual_l3plus}")
    print(f"MIPFocus/Heuristics: {args.mip_focus}/{args.heuristics}")
    if args.nodefile_start is not None:
        print(f"Nodefile:            start={args.nodefile_start} GB, dir={Path(args.nodefile_dir).resolve()}")
    if getattr(args, "custom_solver_options", None):
        print(f"Custom Gurobi opts:  {args.custom_solver_options}")
    print()
    for spec in windows:
        if spec.name == "jan_2025" and not args.no_reuse_jan:
            action = "reuse existing"
        elif spec.name == ANNUAL_PROBE.name and args.reuse_annual_l3plus:
            action = "reuse annual L3plus, solve L3NL"
        else:
            action = "solve"
        headline = "headline" if spec.in_headline else "probe-only"
        print(
            f"{spec.name:<18} {spec.start} -> {spec.end} "
            f"({spec.hours} h, {headline}, {action})"
        )
        print(f"  L3plus out: {_window_dir(spec.name, 'L3plus')}")
        miqcp_level = _miqcp_level_name(
            spec,
            args.low_load_stagnation,
            args.fix_l3nl_s_regimes,
            args.relax_l3nl_s_active,
        )
        print(f"  {miqcp_level:<6} out: {_window_dir(spec.name, miqcp_level)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run 744 h L3plus vs L3NL validation windows.",
    )
    parser.add_argument(
        "--windows",
        nargs="+",
        choices=sorted(WINDOWS.keys()),
        default=None,
        help="Windows to include. Default: jan_2025 feb_2025 may_2025.",
    )
    parser.add_argument("--workers", type=int, default=2, help="Parallel window workers.")
    parser.add_argument("--threads", type=int, default=24, help="Gurobi threads per solve.")
    parser.add_argument("--time-limit", type=int, default=14400, help="MIQCP TimeLimit per window in seconds.")
    parser.add_argument("--annual-probe", action="store_true", help="Also plan/run a probe-only full-year MIQCP.")
    parser.add_argument("--annual-only", action="store_true", help="Run only the probe-only full-year MIQCP.")
    parser.add_argument(
        "--reuse-annual-l3plus",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse output/paper_runs/L3plus as annual MIQCP warmstart/output baseline.",
    )
    parser.add_argument("--no-reuse-jan", action="store_true", help="Recompute January instead of reusing existing artefacts.")
    parser.add_argument("--force", action="store_true", help="Recompute selected windows even if artefacts exist.")
    parser.add_argument("--force-miqcp", action="store_true", help="Recompute only selected L3NL/MIQCP artefacts.")
    parser.add_argument("--dry-run", action="store_true", help="Print jobs only; do not solve or write artefacts.")
    parser.add_argument("--summary-only", action="store_true", help="Only rebuild summary files from existing artefacts.")
    parser.add_argument(
        "--output-suffix",
        default=None,
        help=(
            "Append a sanitized suffix to the output profile, e.g. "
            "linearization_windows_stagnation_<suffix>. Useful for threshold sweeps."
        ),
    )
    parser.add_argument(
        "--no-level-consistency-update",
        action="store_true",
        help="Do not write this run into output/paper_runs/level_consistency.json.",
    )
    parser.add_argument("--mip-focus", type=int, default=1, choices=[0, 1, 2, 3], help="Gurobi MIPFocus for MIQCP.")
    parser.add_argument("--heuristics", type=float, default=0.8, help="Gurobi Heuristics for MIQCP.")
    parser.add_argument("--numeric-focus", type=int, default=2, choices=[0, 1, 2, 3], help="Gurobi NumericFocus for MIQCP.")
    parser.add_argument("--nodefile-start", type=float, default=None, help="Gurobi NodefileStart in GB.")
    parser.add_argument(
        "--nodefile-dir",
        default=str(OUT_WINDOWS / "_nodefiles"),
        help="Directory for Gurobi node files when --nodefile-start is set.",
    )
    parser.add_argument("--no-rel-heur-time", type=int, default=None, help="Gurobi NoRelHeurTime in seconds.")
    parser.add_argument("--improve-start-time", type=int, default=None, help="Gurobi ImproveStartTime in seconds.")
    parser.add_argument(
        "--warmstart-mode",
        choices=["full", "no-pipe-state", "binary-only", "dispatch-only", "pipe-regime-only"],
        default="full",
        help=(
            "Select which L3plus solution values are passed as MIQCP warmstart. "
            "Use no-pipe-state or binary-only when full starts violate L3NL-S equalities."
        ),
    )
    parser.add_argument(
        "--solver-option",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional raw Gurobi parameter. Can be passed multiple times.",
    )
    parser.add_argument(
        "--diagnose-inf-unbd",
        action="store_true",
        help="Set DualReductions=0 and InfUnbdInfo=1 for short infeasible/unbounded diagnosis runs.",
    )
    parser.add_argument(
        "--low-load-stagnation",
        action="store_true",
        help="Run L3NL-S with binary low-flow pipe stagnation for non-January windows.",
    )
    parser.add_argument(
        "--fix-l3nl-s-regimes",
        action="store_true",
        help=(
            "For L3NL-S only, fix warmstarted binary regimes and relax unknown "
            "binaries. This is a fixed-regime sensitivity, not an exact MIQCP reference."
        ),
    )
    parser.add_argument(
        "--relax-l3nl-s-active",
        action="store_true",
        help=(
            "With --fix-l3nl-s-regimes, relax the low-flow active/stagnation "
            "variables to [0,1]. This is a feasibility sensitivity only."
        ),
    )
    parser.add_argument(
        "--stagnation-threshold-frac",
        type=float,
        default=0.01,
        help="Low-flow stagnation threshold as fraction of each pipe's effective max flow.",
    )
    parser.add_argument(
        "--stagnation-threshold-abs-min-kg-s",
        type=float,
        default=0.25,
        help="Minimum absolute stagnation threshold per pipe.",
    )
    parser.add_argument(
        "--stagnation-threshold-abs-max-kg-s",
        type=float,
        default=5.0,
        help="Maximum absolute stagnation threshold per pipe.",
    )
    args = parser.parse_args(argv)
    args.custom_solver_options = _parse_solver_options(args.solver_option)
    _configure_output_profile(args.low_load_stagnation, args.output_suffix)
    if args.nodefile_dir == str(OUT_WINDOWS_EXACT / "_nodefiles"):
        args.nodefile_dir = str(OUT_WINDOWS / "_nodefiles")

    windows = _selected_windows(args.windows, args.annual_probe, args.annual_only)
    if args.dry_run:
        _print_dry_run(windows, args)
        return 0

    OUT_WINDOWS.mkdir(parents=True, exist_ok=True)

    if not args.no_reuse_jan and any(spec.name == "jan_2025" for spec in windows):
        print("[reuse] Copying January artefacts into linearization_windows/jan_2025")
        _copy_reused_january(force=args.force)

    if args.reuse_annual_l3plus and any(spec.name == ANNUAL_PROBE.name for spec in windows):
        print("[reuse] Copying annual L3plus artefacts into linearization_windows/annual_2025_probe/L3plus")
        _copy_reused_annual_l3plus(force=args.force)

    if not args.summary_only:
        jobs = []
        for spec in windows:
            if spec.name == "jan_2025" and not args.no_reuse_jan:
                continue
            jobs.append({
                "spec": spec.__dict__,
                "threads": args.threads,
                "reuse_l3plus": spec.name == ANNUAL_PROBE.name and args.reuse_annual_l3plus,
                "force_miqcp": args.force_miqcp,
                "low_load_stagnation": args.low_load_stagnation,
                "output_suffix": args.output_suffix,
                "miqcp_args": {
                    "threads": args.threads,
                    "time_limit": args.time_limit,
                    "mip_focus": args.mip_focus,
                    "heuristics": args.heuristics,
                    "numeric_focus": args.numeric_focus,
                    "warmstart_mode": args.warmstart_mode,
                    "nodefile_start": args.nodefile_start,
                    "nodefile_dir": args.nodefile_dir,
                    "no_rel_heur_time": args.no_rel_heur_time,
                    "improve_start_time": args.improve_start_time,
                    "custom_solver_options": args.custom_solver_options,
                    "diagnose_inf_unbd": args.diagnose_inf_unbd,
                    "low_load_stagnation": args.low_load_stagnation,
                    "fix_l3nl_s_regimes": args.fix_l3nl_s_regimes,
                    "relax_l3nl_s_active": args.relax_l3nl_s_active,
                    "stagnation_threshold_frac": args.stagnation_threshold_frac,
                    "stagnation_threshold_abs_min_kg_s": args.stagnation_threshold_abs_min_kg_s,
                    "stagnation_threshold_abs_max_kg_s": args.stagnation_threshold_abs_max_kg_s,
                },
                "force": args.force,
            })

        if jobs:
            print(f"[run] Starting {len(jobs)} window job(s) with {args.workers} worker(s)")
            with ProcessPoolExecutor(max_workers=max(1, int(args.workers))) as pool:
                futures = {pool.submit(_run_window_worker, job): job for job in jobs}
                done = 0
                for future in as_completed(futures):
                    done += 1
                    spec_name = futures[future]["spec"]["name"]
                    try:
                        result = future.result()
                        milp_s = result.get("milp", {}).get("elapsed_s")
                        miqcp_s = result.get("miqcp", {}).get("elapsed_s")
                        print(
                            f"[ok] {done}/{len(jobs)} {spec_name} "
                            f"MILP={_format_seconds(milp_s)} MIQCP={_format_seconds(miqcp_s)}"
                        )
                    except Exception as exc:
                        print(f"[error] {done}/{len(jobs)} {spec_name}: {exc}")
        else:
            print("[run] No solve jobs needed; rebuilding summary from existing artefacts.")

    rows = []
    for spec in windows:
        source = "reused_existing" if spec.name == "jan_2025" and not args.no_reuse_jan else "computed"
        rows.append(
            _summarize_window(
                spec,
                source=source,
                low_load_stagnation=args.low_load_stagnation,
                stagnation_threshold_frac=args.stagnation_threshold_frac,
                fix_l3nl_s_regimes=args.fix_l3nl_s_regimes,
                relax_l3nl_s_active=args.relax_l3nl_s_active,
            )
        )

    _write_summary(rows)
    if not args.no_level_consistency_update:
        _update_level_consistency(rows, low_load_stagnation=args.low_load_stagnation)

    usable = [row for row in rows if row.get("in_headline") and row.get("usable")]
    print(f"[summary] wrote {SUMMARY_CSV}")
    print(f"[summary] wrote {SUMMARY_JSON}")
    n_headline = sum(1 for row in rows if row.get("in_headline"))
    print(f"[summary] usable headline windows: {len(usable)}/{n_headline}")
    if n_headline == 0:
        print("[summary] probe-only run; headline-window evidence check skipped.")
        return 0
    if len(usable) < 2:
        print("[warn] Fewer than two usable MIQCP windows; soften paper claim accordingly.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
