"""
Network State Validation and Diagnostics.

Supports two input modes:
1) Pyomo model mode (direct variable inspection)
2) Exported network-data mode (solver_meta["network_data"])
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

try:
    import pyomo.environ as pyo

    HAVE_PYOMO = True
except ImportError:  # pragma: no cover - optional dependency
    HAVE_PYOMO = False
    pyo = None

logger = logging.getLogger(__name__)


@dataclass
class StateValidationIssue:
    """Represents one validation issue."""

    severity: str  # warning, error, info
    component_type: str  # node, pipe, global
    component_id: str
    timestep: Any
    metric: str
    value: float
    bound_min: float | None = None
    bound_max: float | None = None
    message: str = ""

    def __str__(self) -> str:
        bounds = ""
        if self.bound_min is not None and self.bound_max is not None:
            bounds = f"(bounds: [{self.bound_min:.2f}, {self.bound_max:.2f}]) "
        return (
            f"[{self.severity.upper()}] {self.component_type.upper()} "
            f"{self.component_id}@t{self.timestep}: {self.metric}={self.value:.2f} "
            f"{bounds}{self.message}".strip()
        )


class NetworkValidator:
    """Post-solve network state validator."""

    def __init__(self, model_or_data: Any, config: dict[str, Any], time_set: list[Any] | None = None):
        self.model = model_or_data
        self.network_data = (
            model_or_data
            if isinstance(model_or_data, dict)
            and "nodes" in model_or_data
            and "pipes" in model_or_data
            else None
        )
        self._data_mode = self.network_data is not None
        self.config = config or {}
        self.time_set = list(time_set) if time_set is not None else self._infer_time_set()
        self.issues: list[StateValidationIssue] = []

        self.state_cfg = self._extract_state_cfg()
        self.temp_cfg = self.state_cfg.get("temperature_constraints", {})
        self.press_cfg = self.state_cfg.get("pressure_constraints", {})
        self.flow_cfg = self.state_cfg.get("flow_constraints", {})

    def _extract_state_cfg(self) -> dict[str, Any]:
        state_cfg = self.config.get("state_validation")
        if not isinstance(state_cfg, dict):
            net_cfg = self.config.get("network", {})
            if isinstance(net_cfg, dict) and isinstance(net_cfg.get("state_validation"), dict):
                state_cfg = net_cfg.get("state_validation")
            else:
                tn_cfg = self.config.get("thermal_network", {})
                if isinstance(tn_cfg, dict) and isinstance(tn_cfg.get("state_validation"), dict):
                    state_cfg = tn_cfg.get("state_validation")
                else:
                    state_cfg = {}

        out = dict(state_cfg)
        out.setdefault("temperature_constraints", {})
        out.setdefault("pressure_constraints", {})
        out.setdefault("flow_constraints", {})
        out["temperature_constraints"].setdefault("enforce_supply_ge_return", True)
        out["temperature_constraints"].setdefault("temperature_tolerance_c", 0.1)
        out["pressure_constraints"].setdefault("min_pressure_bar", 0.5)
        out["flow_constraints"].setdefault("min_velocity_m_s", 0.3)
        out["flow_constraints"].setdefault("max_velocity_m_s", 2.5)
        return out

    def _infer_time_set(self) -> list[Any]:
        if not self.network_data:
            return []
        for node in self.network_data.get("nodes", {}).values():
            if not isinstance(node, dict):
                continue
            for key in ("T_supply_series", "T_return_series"):
                series = node.get(key)
                if isinstance(series, list) and series:
                    return list(range(1, len(series) + 1))
        for pipe in self.network_data.get("pipes", {}).values():
            if not isinstance(pipe, dict):
                continue
            series = pipe.get("velocity_series")
            if isinstance(series, list) and series:
                return list(range(1, len(series) + 1))
        return []

    def _time_label(self, idx: int) -> Any:
        if idx < len(self.time_set):
            return self.time_set[idx]
        return idx + 1

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            out = float(value)
        except (TypeError, ValueError):
            return None
        if out != out:  # NaN
            return None
        return out

    def _safe_value(self, var: Any, t: Any, default: Any = None) -> Any:
        if not HAVE_PYOMO or pyo is None:
            return default
        try:
            if isinstance(var, pyo.Param):
                return pyo.value(var[t])
            if isinstance(var, pyo.Var):
                val = pyo.value(var[t])
                return val if val is not None else default
            return default
        except (ValueError, TypeError, KeyError):
            return default

    def validate_all(self) -> dict[str, Any]:
        logger.info("Starting network state validation...")
        self.issues = []
        self._validate_node_temperatures()
        self._validate_node_pressures()
        self._validate_pipe_velocities()
        self._validate_energy_balances()
        logger.info("Validation complete: %d issue(s) found", len(self.issues))
        return self._summarize_results()

    def _validate_node_temperatures(self) -> None:
        if not self.temp_cfg.get("enforce_supply_ge_return", True):
            logger.debug("Node temperature validation disabled")
            return
        if self._data_mode:
            self._validate_node_temperatures_from_data()
            return
        self._validate_node_temperatures_from_model()

    def _validate_node_temperatures_from_model(self) -> None:
        logger.info("Validating node temperatures...")
        node_vars: dict[str, dict[str, Any]] = {}
        for attr_name in dir(self.model):
            if "_T_SUPPLY" in attr_name and "_T_SUPPLY_IN" not in attr_name:
                parts = attr_name.split("_T_SUPPLY")
                if len(parts) == 2 and parts[0]:
                    node_id = parts[0].replace("_", "-").lower()
                    node_vars.setdefault(node_id, {})["T_supply"] = getattr(self.model, attr_name)
        for attr_name in dir(self.model):
            if "_T_RETURN" in attr_name and "_T_RETURN_IN" not in attr_name and "_T_RETURN_OUT" not in attr_name:
                parts = attr_name.split("_T_RETURN")
                if len(parts) == 2 and parts[0]:
                    node_id = parts[0].replace("_", "-").lower()
                    if node_id in node_vars:
                        node_vars[node_id]["T_return"] = getattr(self.model, attr_name)

        tol = float(self.temp_cfg.get("temperature_tolerance_c", 0.1))
        for node_id, temps in node_vars.items():
            if "T_supply" not in temps or "T_return" not in temps:
                continue
            t_sup_var = temps["T_supply"]
            t_ret_var = temps["T_return"]
            for t in self.time_set:
                t_sup = self._to_float(self._safe_value(t_sup_var, t, default=None))
                t_ret = self._to_float(self._safe_value(t_ret_var, t, default=None))
                if t_sup is None or t_ret is None:
                    continue
                if t_sup < t_ret - tol:
                    issue = StateValidationIssue(
                        severity="error",
                        component_type="node",
                        component_id=node_id,
                        timestep=t,
                        metric="supply_vs_return_temp",
                        value=t_sup - t_ret,
                        bound_min=-tol,
                        bound_max=float("inf"),
                        message=f"T_supply({t_sup:.1f}C) < T_return({t_ret:.1f}C) violates physics",
                    )
                    self.issues.append(issue)
                    logger.warning("  %s", issue)

    def _validate_node_temperatures_from_data(self) -> None:
        logger.info("Validating node temperatures from exported network data...")
        tol = float(self.temp_cfg.get("temperature_tolerance_c", 0.1))
        for node_id, node in (self.network_data or {}).get("nodes", {}).items():
            if not isinstance(node, dict):
                continue
            t_sup_series = node.get("T_supply_series")
            t_ret_series = node.get("T_return_series")
            if not isinstance(t_sup_series, list) or not isinstance(t_ret_series, list):
                continue
            n = min(len(t_sup_series), len(t_ret_series))
            for i in range(n):
                t_sup = self._to_float(t_sup_series[i])
                t_ret = self._to_float(t_ret_series[i])
                if t_sup is None or t_ret is None:
                    continue
                if t_sup < t_ret - tol:
                    issue = StateValidationIssue(
                        severity="error",
                        component_type="node",
                        component_id=str(node_id),
                        timestep=self._time_label(i),
                        metric="supply_vs_return_temp",
                        value=t_sup - t_ret,
                        bound_min=-tol,
                        bound_max=float("inf"),
                        message=f"T_supply({t_sup:.1f}C) < T_return({t_ret:.1f}C) violates physics",
                    )
                    self.issues.append(issue)
                    logger.warning("  %s", issue)

    def _validate_node_pressures(self) -> None:
        min_press = float(self.press_cfg.get("min_pressure_bar", 0.5))
        if min_press <= 0:
            logger.debug("Node pressure validation disabled")
            return
        if self._data_mode:
            self._validate_node_pressures_from_data(min_press)
            return
        self._validate_node_pressures_from_model(min_press)

    def _validate_node_pressures_from_model(self, min_press: float) -> None:
        logger.info("Validating node pressures (min: %.3f bar)...", min_press)
        pressure_vars: dict[str, dict[str, Any]] = {}
        for attr_name in dir(self.model):
            if "_PRESSURE_SUPPLY" in attr_name:
                parts = attr_name.split("_PRESSURE_SUPPLY")
                if len(parts) == 2 and parts[0]:
                    node_id = parts[0].replace("_", "-").lower()
                    pressure_vars.setdefault(node_id, {})["P_supply"] = getattr(self.model, attr_name)
        for attr_name in dir(self.model):
            if "_PRESSURE_RETURN" in attr_name:
                parts = attr_name.split("_PRESSURE_RETURN")
                if len(parts) == 2 and parts[0]:
                    node_id = parts[0].replace("_", "-").lower()
                    if node_id in pressure_vars:
                        pressure_vars[node_id]["P_return"] = getattr(self.model, attr_name)
        for node_id, pressures in pressure_vars.items():
            for metric in ("P_supply", "P_return"):
                if metric not in pressures:
                    continue
                p_var = pressures[metric]
                for t in self.time_set:
                    p_val = self._to_float(self._safe_value(p_var, t, default=None))
                    if p_val is not None and p_val < min_press:
                        issue = StateValidationIssue(
                            severity="warning",
                            component_type="node",
                            component_id=node_id,
                            timestep=t,
                            metric=metric,
                            value=p_val,
                            bound_min=min_press,
                            message=f"Low pressure {p_val:.2f} bar < minimum {min_press} bar",
                        )
                        self.issues.append(issue)
                        logger.warning("  %s", issue)

    def _validate_node_pressures_from_data(self, min_press: float) -> None:
        logger.info("Validating node pressures from exported network data (min: %.3f bar)...", min_press)
        for node_id, node in (self.network_data or {}).get("nodes", {}).items():
            if not isinstance(node, dict):
                continue
            for metric, keys in (
                ("P_supply", ("P_supply_series", "pressure_supply_series")),
                ("P_return", ("P_return_series", "pressure_return_series")),
            ):
                series = None
                for key in keys:
                    candidate = node.get(key)
                    if isinstance(candidate, list):
                        series = candidate
                        break
                if not isinstance(series, list):
                    continue
                for i, raw in enumerate(series):
                    p_val = self._to_float(raw)
                    if p_val is not None and p_val < min_press:
                        issue = StateValidationIssue(
                            severity="warning",
                            component_type="node",
                            component_id=str(node_id),
                            timestep=self._time_label(i),
                            metric=metric,
                            value=p_val,
                            bound_min=min_press,
                            message=f"Low pressure {p_val:.2f} bar < minimum {min_press} bar",
                        )
                        self.issues.append(issue)
                        logger.warning("  %s", issue)

    def _validate_pipe_velocities(self) -> None:
        v_min = float(self.flow_cfg.get("min_velocity_m_s", 0.3))
        v_max = float(self.flow_cfg.get("max_velocity_m_s", 2.5))
        if v_min <= 0 or v_max <= 0:
            logger.debug("Pipe velocity validation disabled")
            return
        if self._data_mode:
            self._validate_pipe_velocities_from_data(v_min, v_max)
            return
        self._validate_pipe_velocities_from_model(v_min, v_max)

    def _validate_pipe_velocities_from_model(self, v_min: float, v_max: float) -> None:
        logger.info("Validating pipe velocities (bounds: [%.3f, %.3f] m/s)...", v_min, v_max)
        velocity_vars: dict[str, Any] = {}
        for attr_name in dir(self.model):
            if "_VELOCITY" in attr_name and "_VELOCITY_" not in attr_name:
                parts = attr_name.split("_VELOCITY")
                if len(parts) == 2 and parts[0]:
                    pipe_id = parts[0].replace("_", "-").lower()
                    velocity_vars[pipe_id] = getattr(self.model, attr_name)
        for pipe_id, vel_var in velocity_vars.items():
            for t in self.time_set:
                v_val = self._to_float(self._safe_value(vel_var, t, default=None))
                if v_val is None:
                    continue
                self._check_velocity_value(pipe_id, t, v_val, v_min, v_max)

    def _validate_pipe_velocities_from_data(self, v_min: float, v_max: float) -> None:
        logger.info(
            "Validating pipe velocities from exported network data (bounds: [%.3f, %.3f] m/s)...",
            v_min,
            v_max,
        )
        for pipe_id, pipe in (self.network_data or {}).get("pipes", {}).items():
            if not isinstance(pipe, dict):
                continue
            series = pipe.get("velocity_series")
            if not isinstance(series, list):
                continue
            for i, raw in enumerate(series):
                v_val = self._to_float(raw)
                if v_val is None:
                    continue
                self._check_velocity_value(str(pipe_id), self._time_label(i), v_val, v_min, v_max)

    def _check_velocity_value(self, pipe_id: str, timestep: Any, v_val: float, v_min: float, v_max: float) -> None:
        if v_val < v_min:
            issue = StateValidationIssue(
                severity="warning",
                component_type="pipe",
                component_id=pipe_id,
                timestep=timestep,
                metric="velocity",
                value=v_val,
                bound_min=v_min,
                bound_max=v_max,
                message=f"Low velocity {v_val:.2f} m/s < min {v_min} m/s (stagnation risk)",
            )
            self.issues.append(issue)
            logger.warning("  %s", issue)
            return
        if v_val > v_max:
            issue = StateValidationIssue(
                severity="warning",
                component_type="pipe",
                component_id=pipe_id,
                timestep=timestep,
                metric="velocity",
                value=v_val,
                bound_min=v_min,
                bound_max=v_max,
                message=f"High velocity {v_val:.2f} m/s > max {v_max} m/s (noise/wear risk)",
            )
            self.issues.append(issue)
            logger.warning("  %s", issue)

    def _validate_energy_balances(self) -> None:
        logger.info("Validating global energy balance...")
        if self._data_mode:
            summary = (self.network_data or {}).get("summary", {})
            total_loss = self._to_float(summary.get("total_network_loss_mwh"))
            if total_loss is not None and total_loss < -1e-9:
                issue = StateValidationIssue(
                    severity="warning",
                    component_type="global",
                    component_id="network",
                    timestep="all",
                    metric="total_network_loss_mwh",
                    value=total_loss,
                    bound_min=0.0,
                    message="Network loss is negative; check thermal sign conventions",
                )
                self.issues.append(issue)
                logger.warning("  %s", issue)
            return
        if hasattr(self.model, "ht_balance"):
            logger.debug("  Heat balance constraint present - model is consistent")
        else:
            logger.debug("  Heat balance constraint not directly accessible")

    def _summarize_results(self) -> dict[str, Any]:
        issues_by_severity: dict[str, list[StateValidationIssue]] = {"error": [], "warning": [], "info": []}
        issues_by_component: dict[str, list[StateValidationIssue]] = {"node": [], "pipe": [], "global": []}
        for issue in self.issues:
            issues_by_severity.setdefault(issue.severity, []).append(issue)
            issues_by_component.setdefault(issue.component_type, []).append(issue)
        return {
            "total_issues": len(self.issues),
            "errors": len(issues_by_severity.get("error", [])),
            "warnings": len(issues_by_severity.get("warning", [])),
            "by_severity": {k: len(v) for k, v in issues_by_severity.items()},
            "by_component": {k: len(v) for k, v in issues_by_component.items()},
            "issues": self.issues,
            "passed": len(self.issues) == 0,
        }

    def export_report(self, filepath: str) -> None:
        report = {
            "total_issues": len(self.issues),
            "errors": sum(1 for i in self.issues if i.severity == "error"),
            "warnings": sum(1 for i in self.issues if i.severity == "warning"),
            "issues": [
                {
                    "severity": i.severity,
                    "component_type": i.component_type,
                    "component_id": i.component_id,
                    "timestep": str(i.timestep),
                    "metric": i.metric,
                    "value": float(i.value) if i.value is not None else None,
                    "bound_min": float(i.bound_min) if i.bound_min is not None else None,
                    "bound_max": float(i.bound_max) if i.bound_max is not None else None,
                    "message": i.message,
                }
                for i in self.issues
            ],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info("Validation report exported to %s", filepath)

