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

# ── Configuration ─────────────────────────────────────────────────────────
from calion.config import load_and_merge as load_config
from calion.config import validate_config_schema, CALIONConfig

# ── Workflow execution ────────────────────────────────────────────────────
from calion.run import (
    run_workflow,
    ScenarioResult,
    RollingHorizonResult,
    WorkflowResult,
    WorkflowPlan,
)

# ── Structured results ────────────────────────────────────────────────────
from calion.models.results import InvestmentDecisions

# ── Component system ──────────────────────────────────────────────────────
from calion.models import (
    Component,
    BaseComponent,
    Bus,
    Flow,
    register_component,
    ComponentRegistry,
    build_model,
)

__all__ = [
    # Config
    "load_config",
    "validate_config_schema",
    "CALIONConfig",
    # Workflow
    "run_workflow",
    "ScenarioResult",
    "RollingHorizonResult",
    "WorkflowResult",
    "WorkflowPlan",
    # Results
    "InvestmentDecisions",
    # Components
    "Component",
    "BaseComponent",
    "Bus",
    "Flow",
    "register_component",
    "ComponentRegistry",
    "build_model",
]
