"""High-level convenience API for the CALION framework.

This module re-exports the most commonly used classes and functions so
that users can write::

    from calion.api import load_config, run_workflow, CALIONConfig

instead of reaching into sub-packages.

Typical usage::

    from calion.api import load_config, run_workflow

    cfg = load_config(["configs/base.yaml", "configs/scenario.yaml"])
    result = run_workflow(["configs/base.yaml", "configs/scenario.yaml"])

    print(result.pf_result.costs)
"""

from __future__ import annotations

from calion.config import CALIONConfig, validate_config_schema

# ── Configuration ─────────────────────────────────────────────────────────
from calion.config import load_and_merge as load_config

# ── Component system ──────────────────────────────────────────────────────
from calion.models import (
    BaseComponent,
    Bus,
    Component,
    ComponentRegistry,
    Flow,
    build_model,
    register_component,
)

# ── Structured results ────────────────────────────────────────────────────
from calion.models.results import InvestmentDecisions

# ── Workflow execution ────────────────────────────────────────────────────
from calion.run import (
    RollingHorizonResult,
    ScenarioResult,
    WorkflowPlan,
    WorkflowResult,
    run_workflow,
)

__all__ = [
    "BaseComponent",
    "Bus",
    "CALIONConfig",
    # Components
    "Component",
    "ComponentRegistry",
    "Flow",
    # Results
    "InvestmentDecisions",
    "RollingHorizonResult",
    "ScenarioResult",
    "WorkflowPlan",
    "WorkflowResult",
    "build_model",
    # Config
    "load_config",
    "register_component",
    # Workflow
    "run_workflow",
    "validate_config_schema",
]
