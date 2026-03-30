"""Shared data types for the workflow orchestration layer.

All dataclasses that were previously defined inside ``rolling_horizon.py`` now
live here so that every sub-module can import them without pulling in the whole
monolith.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from calion.design import OptimizationConfig, DesignSpec
from calion.models.results import InvestmentDecisions
from calion.utils.timeseries import TimeSeriesTable


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    """Container for a single optimisation run."""

    table: TimeSeriesTable
    series: OrderedDict[str, List[float]]
    summary: Mapping[str, Mapping[str, Any]]
    costs: Dict[str, Any]
    solver: Dict[str, Any]
    investments: Optional[InvestmentDecisions] = None


@dataclass
class WindowResult(ScenarioResult):
    """Specialised result carrying metadata for RH windows."""

    start_index: int = 0
    commit_steps: int = 0


@dataclass
class DesignData:
    """Design figures extracted from a PF optimisation.

    DEPRECATED: Use :class:`~calion.models.results.InvestmentDecisions` instead.
    Kept temporarily for backward compatibility during migration.
    """

    heat_pumps: Dict[str, Dict[str, float]]
    storage: Optional[Dict[str, float]]


@dataclass
class RollingHorizonResult:
    """Aggregated result for a complete RH simulation."""

    table: TimeSeriesTable
    series: OrderedDict[str, List[float]]
    costs: Dict[str, Any]
    windows: List[WindowResult]
    design: Optional[DesignData] = None
    investments: Optional[InvestmentDecisions] = None


# ---------------------------------------------------------------------------
# Workflow planning / context
# ---------------------------------------------------------------------------

@dataclass
class WorkflowPlan:
    """Parsed representation of the requested workflow sequence."""

    steps: Sequence[str]
    fix_design: bool
    design_config: Optional[OptimizationConfig] = None


@dataclass
class WorkflowInputs:
    """Prepared artefacts required to execute a workflow."""

    cfg: Dict[str, Any]
    table: TimeSeriesTable
    dt_h: float
    solver_name: str
    plan: WorkflowPlan


@dataclass
class WorkflowContext:
    """Mutable state shared between workflow steps."""

    cfg: Dict[str, Any]
    table: TimeSeriesTable
    dt_h: float
    solver_name: str
    plan: WorkflowPlan
    pf_result: Optional[ScenarioResult] = None
    rh_result: Optional[RollingHorizonResult] = None
    mpc_result: Optional[RollingHorizonResult] = None
    design: Optional[DesignData] = None  # Legacy (deprecated)
    design_spec: Optional[DesignSpec] = None  # Legacy (deprecated)
    investments: Optional[InvestmentDecisions] = None  # Structured investment results


@dataclass
class WorkflowResult:
    """Return value for :func:`run_workflow`."""

    config: Dict[str, Any]
    pf_result: Optional[ScenarioResult]
    rh_result: Optional[RollingHorizonResult]
    mpc_result: Optional[RollingHorizonResult]
    design: Optional[DesignData]
    plan: WorkflowPlan
    investments: Optional[InvestmentDecisions] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@dataclass
class _RollingParams:
    """Internal helper capturing rolling horizon parameters."""

    horizon_hours: float
    step_hours: float
    overlap_hours: float
    terminal_policy: str

    def as_steps(self, dt_h: float) -> tuple[int, int, int]:
        """Return window, commit and overlap lengths measured in simulation steps."""
        from .utilities.timeseries_utils import _hours_to_steps

        if dt_h <= 0:
            raise ValueError("dt_h must be positive")
        horizon_steps = _hours_to_steps(self.horizon_hours, dt_h, "HEAT_HORIZON_HOURS")
        step_steps = _hours_to_steps(self.step_hours, dt_h, "STEP_HOURS")
        overlap_steps = _hours_to_steps(self.overlap_hours, dt_h, "OVERLAP_HOURS") if self.overlap_hours else 0
        if step_steps > horizon_steps:
            raise ValueError("STEP_HOURS must not exceed HEAT_HORIZON_HOURS")
        if overlap_steps >= step_steps:
            raise ValueError("OVERLAP_HOURS must be smaller than STEP_HOURS")
        return horizon_steps, step_steps, overlap_steps


@dataclass
class _CostAggregationPlan:
    """Configuration for rolling-horizon cost handling."""

    include_investment: bool
    amortise_once: bool
    include_tie_breaker: bool
    include_installation: bool
    include_activation: bool

    def investment_active(self, window_idx: int) -> bool:
        if not self.include_investment:
            return False
        if self.amortise_once and window_idx > 0:
            return False
        return True


StepHandler = Callable[[WorkflowContext], None]


__all__ = [
    "ScenarioResult",
    "WindowResult",
    "DesignData",
    "RollingHorizonResult",
    "WorkflowPlan",
    "WorkflowInputs",
    "WorkflowContext",
    "WorkflowResult",
    "_RollingParams",
    "_CostAggregationPlan",
    "StepHandler",
]
