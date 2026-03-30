"""Workflow execution: single-shot, rolling horizon, and MPC.

Public API:

- :func:`run_workflow` — high-level entry point for all run modes.
- :class:`WorkflowResult` — typed result container returned by ``run_workflow``.
- :class:`ScenarioResult` — result for a single optimisation window.
"""

from calion.run.types import (
    RollingHorizonResult,
    ScenarioResult,
    WorkflowPlan,
    WorkflowResult,
)
from calion.run.workflow import run_workflow

__all__ = [
    "RollingHorizonResult",
    "ScenarioResult",
    "WorkflowPlan",
    "WorkflowResult",
    "run_workflow",
]
