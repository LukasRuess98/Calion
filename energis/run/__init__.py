"""Workflow execution: single-shot, rolling horizon, and MPC.

Public API:

- :func:`run_workflow` — high-level entry point for all run modes.
- :class:`WorkflowResult` — typed result container returned by ``run_workflow``.
- :class:`ScenarioResult` — result for a single optimisation window.
"""

from energis.run.workflow import run_workflow
from energis.run.types import (
    ScenarioResult,
    RollingHorizonResult,
    WorkflowResult,
    WorkflowPlan,
)

__all__ = [
    "run_workflow",
    "ScenarioResult",
    "RollingHorizonResult",
    "WorkflowResult",
    "WorkflowPlan",
]
