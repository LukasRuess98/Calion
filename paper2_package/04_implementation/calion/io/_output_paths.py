"""Canonical output directory helpers.

New canonical paths:
  outputs/runs/       — solver results, CSVs, PDFs per run
  outputs/workflows/  — saved notebook workflows
  outputs/dashboard/  — dashboard state / exports

Legacy paths are detected and returned with a DeprecationWarning so that
existing data is not silently ignored while users migrate.
"""

from __future__ import annotations

import os
import warnings

RUNS_DIR = "outputs/runs"
WORKFLOWS_DIR = "outputs/workflows"
DASHBOARD_DIR = "outputs/dashboard"

_LEGACY_RUNS = ["exports", "results"]
_LEGACY_WORKFLOWS = ["notebooks/saved_workflows", "saved_workflows"]


def resolve_runs_dir(requested: str | None = None) -> str:
    """Return the directory to write run outputs into.

    Priority:
    1. *requested* — explicit caller override (no warning)
    2. First legacy dir that already exists on disk — returned with DeprecationWarning
    3. ``RUNS_DIR`` — canonical new default
    """
    return _resolve(requested, RUNS_DIR, _LEGACY_RUNS, "runs")


def resolve_workflows_dir(requested: str | None = None) -> str:
    """Return the directory to read/write saved workflows from.

    Priority: same as :func:`resolve_runs_dir`.
    """
    return _resolve(requested, WORKFLOWS_DIR, _LEGACY_WORKFLOWS, "workflows")


def _resolve(requested: str | None, new_default: str, legacy: list[str], kind: str) -> str:
    if requested is not None:
        return requested
    for legacy_path in legacy:
        if os.path.isdir(legacy_path):
            warnings.warn(
                f"Output directory '{legacy_path}' is a legacy location. "
                f"Please migrate to '{new_default}' (run: python scripts/migrate_outputs.py).",
                DeprecationWarning,
                stacklevel=3,
            )
            return legacy_path
    return new_default
