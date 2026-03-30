"""High-level convenience API for the EnerGIS framework.

This module re-exports the most commonly used classes and functions so
that users can write::

    from energis.api import load_config, run_workflow, EnerGISConfig

instead of reaching into sub-packages.

Typical usage::

    from energis.api import load_config, run_workflow

    cfg = load_config(["configs/base.yaml", "configs/scenario.yaml"])
    result = run_workflow(["configs/base.yaml", "configs/scenario.yaml"])

    print(result.pf_result.costs)
"""

from __future__ import annotations

# ── Configuration ─────────────────────────────────────────────────────────
from energis.config import load_and_merge as load_config
from energis.config import validate_config_schema, EnerGISConfig

# ── Workflow execution ────────────────────────────────────────────────────
from energis.run import (
    run_workflow,
    ScenarioResult,
    RollingHorizonResult,
    WorkflowResult,
    WorkflowPlan,
)

# ── Structured results ────────────────────────────────────────────────────
from energis.models.results import InvestmentDecisions

# ── Component system ──────────────────────────────────────────────────────
from energis.models import (
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
    "EnerGISConfig",
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
