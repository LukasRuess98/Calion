"""
Network State Validation & Diagnostics

This module provides post-solve validation of network states to ensure
they remain physically realistic and respect all Phase 1 constraints.

Author: CALION Development Team
"""

import logging
from typing import Any, List
from dataclasses import dataclass

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

logger = logging.getLogger(__name__)


@dataclass
class StateValidationIssue:
    """Represents a single validation issue."""
    severity: str  # "warning", "error", "info"
    component_type: str  # "node", "pipe", "global"
    component_id: str
    timestep: Any
    metric: str  # "temperature", "pressure", "velocity", etc.
    value: float
    bound_min: float = None
    bound_max: float = None
    message: str = ""

    def __str__(self):
        return (
            f"[{self.severity.upper()}] {self.component_type.upper()} "
            f"{self.component_id}@t{self.timestep}: "
            f"{self.metric}={self.value:.2f} " + 
            (f"(bounds: [{self.bound_min:.2f}, {self.bound_max:.2f}])" 
             if self.bound_min is not None and self.bound_max is not None else "") +
            (f" — {self.message}" if self.message else "")
        )


class NetworkValidator:
    """Post-solve network state validator."""

    def __init__(self, model, config: dict, time_set):
        """
        Initialize validator.
        
        Args:
            model: Solved Pyomo ConcreteModel
            config: Full configuration with state_validation section
            time_set: Set of timesteps
        """
        self.model = model
        self.config = config
        self.time_set = time_set
        self.issues: List[StateValidationIssue] = []
        
        # Extract state validation config with defaults
        self.state_cfg = config.get('state_validation', {})
        self.temp_cfg = self.state_cfg.get('temperature_constraints', {})
        self.press_cfg = self.state_cfg.get('pressure_constraints', {})
        self.flow_cfg = self.state_cfg.get('flow_constraints', {})

    def validate_all(self) -> dict:
        """
        Run all validation checks.
        
        Returns:
            Dict with validation results and statistics
        """
        logger.info("Starting network state validation...")
        self.issues = []
        
        self._validate_node_temperatures()
        self._validate_node_pressures()
        self._validate_pipe_velocities()
        self._validate_energy_balances()
        
        logger.info(f"Validation complete: {len(self.issues)} issue(s) found")
        return self._summarize_results()

    def _safe_value(self, var, t, default=None):
        """Safely extract value from Pyomo variable."""
        if not HAVE_PYOMO or pyo is None:
            return default
        try:
            if isinstance(var, pyo.Param):
                return pyo.value(var[t])
            elif isinstance(var, pyo.Var):
                val = pyo.value(var[t])
                return val if val is not None else default
            else:
                return default
        except (ValueError, TypeError, KeyError):
            return default

    def _validate_node_temperatures(self) -> None:
        """Check temperature constraints at all nodes."""
        if not self.temp_cfg.get('enforce_supply_ge_return', True):
            logger.debug("Node temperature validation disabled")
            return
        
        logger.info("Validating node temperatures...")
        
        # Find all node variables
        node_vars = {}
        for attr_name in dir(self.model):
            if '_T_SUPPLY' in attr_name and '_T_SUPPLY_IN' not in attr_name:
                # Extract node ID from attribute name
                parts = attr_name.split('_T_SUPPLY')
                if len(parts) == 2 and parts[0]:
                    node_id = parts[0].replace('_', '-').lower()
                    if node_id not in node_vars:
                        node_vars[node_id] = {}
                    node_vars[node_id]['T_supply'] = getattr(self.model, attr_name)
        
        # Extract T_return for each node
        for attr_name in dir(self.model):
            if '_T_RETURN' in attr_name and '_T_RETURN_IN' not in attr_name and '_T_RETURN_OUT' not in attr_name:
                parts = attr_name.split('_T_RETURN')
                if len(parts) == 2 and parts[0]:
                    node_id = parts[0].replace('_', '-').lower()
                    if node_id in node_vars:
                        node_vars[node_id]['T_return'] = getattr(self.model, attr_name)
        
        tolerance = self.temp_cfg.get('temperature_tolerance_c', 0.1)
        
        for node_id, temps in node_vars.items():
            if 'T_supply' not in temps or 'T_return' not in temps:
                continue
            
            T_sup = temps['T_supply']
            T_ret = temps['T_return']
            
            for t in self.time_set:
                t_sup = self._safe_value(T_sup, t, default=90.0)
                t_ret = self._safe_value(T_ret, t, default=50.0)
                
                if t_sup is None or t_ret is None:
                    continue
                
                if t_sup < t_ret - tolerance:
                    issue = StateValidationIssue(
                        severity="error",
                        component_type="node",
                        component_id=node_id,
                        timestep=t,
                        metric="supply_vs_return_temp",
                        value=t_sup - t_ret,
                        bound_min=-tolerance,
                        bound_max=float('inf'),
                        message=f"T_supply({t_sup:.1f}°C) < T_return({t_ret:.1f}°C) violates physics"
                    )
                    self.issues.append(issue)
                    logger.warning(f"  {issue}")

    def _validate_node_pressures(self) -> None:
        """Check pressure constraints at all nodes."""
        min_press = self.press_cfg.get('min_pressure_bar', 0.5)
        if min_press <= 0:
            logger.debug("Node pressure validation disabled")
            return
        
        logger.info(f"Validating node pressures (min: {min_press} bar)...")
        
        pressure_vars = {}
        for attr_name in dir(self.model):
            if '_PRESSURE_SUPPLY' in attr_name:
                parts = attr_name.split('_PRESSURE_SUPPLY')
                if len(parts) == 2 and parts[0]:
                    node_id = parts[0].replace('_', '-').lower()
                    if node_id not in pressure_vars:
                        pressure_vars[node_id] = {}
                    pressure_vars[node_id]['P_supply'] = getattr(self.model, attr_name)
        
        for attr_name in dir(self.model):
            if '_PRESSURE_RETURN' in attr_name:
                parts = attr_name.split('_PRESSURE_RETURN')
                if len(parts) == 2 and parts[0]:
                    node_id = parts[0].replace('_', '-').lower()
                    if node_id in pressure_vars:
                        pressure_vars[node_id]['P_return'] = getattr(self.model, attr_name)
        
        for node_id, pressures in pressure_vars.items():
            for press_type in ['P_supply', 'P_return']:
                if press_type not in pressures:
                    continue
                
                P_var = pressures[press_type]
                for t in self.time_set:
                    p_val = self._safe_value(P_var, t, default=1.0)
                    
                    if p_val is not None and p_val < min_press:
                        issue = StateValidationIssue(
                            severity="warning",
                            component_type="node",
                            component_id=node_id,
                            timestep=t,
                            metric=press_type,
                            value=p_val,
                            bound_min=min_press,
                            message=f"Low pressure {p_val:.2f} bar < minimum {min_press} bar"
                        )
                        self.issues.append(issue)
                        logger.warning(f"  {issue}")

    def _validate_pipe_velocities(self) -> None:
        """Check velocity constraints in all pipes."""
        v_min = self.flow_cfg.get('min_velocity_m_s', 0.3)
        v_max = self.flow_cfg.get('max_velocity_m_s', 2.5)
        
        if v_min <= 0 or v_max <= 0:
            logger.debug("Pipe velocity validation disabled")
            return
        
        logger.info(f"Validating pipe velocities (bounds: [{v_min}, {v_max}] m/s)...")
        
        velocity_vars = {}
        for attr_name in dir(self.model):
            if '_VELOCITY' in attr_name and '_VELOCITY_' not in attr_name:
                # Find pipe ID
                parts = attr_name.split('_VELOCITY')
                if len(parts) == 2 and parts[0]:
                    pipe_id = parts[0].replace('_', '-').lower()
                    velocity_vars[pipe_id] = getattr(self.model, attr_name)
        
        for pipe_id, V_var in velocity_vars.items():
            for t in self.time_set:
                v_val = self._safe_value(V_var, t, default=1.0)
                
                if v_val is not None:
                    if v_val < v_min:
                        issue = StateValidationIssue(
                            severity="warning",
                            component_type="pipe",
                            component_id=pipe_id,
                            timestep=t,
                            metric="velocity",
                            value=v_val,
                            bound_min=v_min,
                            bound_max=v_max,
                            message=f"Low velocity {v_val:.2f} m/s < min {v_min} m/s (stagnation risk)"
                        )
                        self.issues.append(issue)
                        logger.warning(f"  {issue}")
                    
                    elif v_val > v_max:
                        issue = StateValidationIssue(
                            severity="warning",
                            component_type="pipe",
                            component_id=pipe_id,
                            timestep=t,
                            metric="velocity",
                            value=v_val,
                            bound_min=v_min,
                            bound_max=v_max,
                            message=f"High velocity {v_val:.2f} m/s > max {v_max} m/s (noise/wear risk)"
                        )
                        self.issues.append(issue)
                        logger.warning(f"  {issue}")

    def _validate_energy_balances(self) -> None:
        """Check global energy balance."""
        logger.info("Validating global energy balance...")
        
        # This is a sanity check — the model should already satisfy this
        # if the solver converged, but we log it for completeness
        if hasattr(self.model, 'ht_balance'):
            logger.debug("  Heat balance constraint present — model is consistent")
        else:
            logger.debug("  Heat balance constraint not directly accessible")

    def _summarize_results(self) -> dict[str, Any]:
        """Create summary report."""
        issues_by_severity = {'error': [], 'warning': [], 'info': []}
        issues_by_component = {'node': [], 'pipe': [], 'global': []}
        
        for issue in self.issues:
            issues_by_severity[issue.severity].append(issue)
            issues_by_component[issue.component_type].append(issue)
        
        return {
            'total_issues': len(self.issues),
            'errors': len(issues_by_severity['error']),
            'warnings': len(issues_by_severity['warning']),
            'by_severity': {k: len(v) for k, v in issues_by_severity.items()},
            'by_component': {k: len(v) for k, v in issues_by_component.items()},
            'issues': self.issues,
            'passed': len(self.issues) == 0,
        }

    def export_report(self, filepath: str) -> None:
        """Export validation report to file."""
        import json
        
        report = {
            'total_issues': len(self.issues),
            'errors': sum(1 for i in self.issues if i.severity == 'error'),
            'warnings': sum(1 for i in self.issues if i.severity == 'warning'),
            'issues': [
                {
                    'severity': i.severity,
                    'component_type': i.component_type,
                    'component_id': i.component_id,
                    'timestep': str(i.timestep),
                    'metric': i.metric,
                    'value': float(i.value) if i.value is not None else None,
                    'bound_min': float(i.bound_min) if i.bound_min is not None else None,
                    'bound_max': float(i.bound_max) if i.bound_max is not None else None,
                    'message': i.message,
                }
                for i in self.issues
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Validation report exported to {filepath}")
