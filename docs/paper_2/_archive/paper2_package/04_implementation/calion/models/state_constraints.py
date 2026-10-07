"""
State Constraint Helpers for Thermal Network Components

This module provides reusable functions to enforce physical state constraints
on network nodes and pipes, ensuring valid thermal states.

Phase 1: Essential constraints
  - Temperature: Supply >= Return at every node
  - Pressure: Minimum operating pressure (cavitation prevention)
  - Flow: Velocity bounds (stagnation + max velocity enforcement)

Author: CALION Development Team
"""

import logging
from typing import Any

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

logger = logging.getLogger(__name__)


def enforce_supply_ge_return_temperature(model, time_set, prefix: str, T_supply, T_return,
                                          node_id: str, config: dict[str, Any]) -> None:
    """
    Enforce supply temperature >= return temperature (supply/return reversal prevention).
    
    Physical rationale:
    - In a heating system, supply always carries hotter fluid than return
    - T_supply < T_return indicates either:
      a) Unphysical optimizer artifact (rare in well-constrained models)
      b) Numerical instability in bilinear mixing constraints
      c) Cooling mode (not applicable in heating networks)
    - Adding this constraint improves model credibility and catches edge cases
    
    Args:
        model: Pyomo ConcreteModel
        time_set: Set of timesteps
        prefix: Variable name prefix (e.g., "CONSUMER_A")
        T_supply: Supply temperature variable/param
        T_return: Return temperature variable/param
        node_id: Node identifier (for logging)
        config: Component configuration dict with state_validation flags
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for constraint building")
    
    # Check if constraint should be applied
    state_cfg = config.get('state_validation', {})
    temp_cfg = state_cfg.get('temperature_constraints', {})
    enabled = temp_cfg.get('enforce_supply_ge_return', True)
    
    if not enabled:
        logger.debug(f"  Node {node_id}: supply_ge_return constraint disabled in config")
        return
    
    # Skip if T_supply or T_return is a Param (fixed) — constraint unnecessary
    if not isinstance(T_supply, pyo.Var):
        logger.debug(f"  Node {node_id}: T_supply is Param (fixed), skipping supply_ge_return")
        return
    
    if not isinstance(T_return, pyo.Var):
        logger.debug(f"  Node {node_id}: T_return is Param (fixed), skipping supply_ge_return")
        return
    
    # Add constraint with numerical tolerance for stability
    tolerance_c = temp_cfg.get('temperature_tolerance_c', 0.1)
    
    def supply_ge_return_rule(m, t):
        return T_supply[t] >= T_return[t] - tolerance_c
    
    constraint_name = f'{prefix}_SUPPLY_GE_RETURN'
    setattr(model, constraint_name,
            pyo.Constraint(time_set, rule=supply_ge_return_rule))
    
    logger.info(
        f"  Node {node_id}: Added supply_ge_return constraint (tolerance: {tolerance_c}°C)"
    )


def enforce_demand_based_return_temperature(model, time_set, prefix: str, T_supply, T_return,
                                            m_dot_demand, Q_demand, node_id: str,
                                            config: dict[str, Any]) -> None:
    """
    Link consumer return temperature to heat demand via mass flow (advanced constraint).
    
    Physical relationship (for consumers):
    - Q_demand = m_dot × cp × (T_supply - T_return)
    - Therefore: T_return = T_supply - Q_demand / (m_dot × cp)
    
    This constraint ensures:
    - When Q_demand increases, T_return must decrease (wider ΔT)
    - When Q_demand decreases, T_return can increase (narrower ΔT)
    - Prevents unrealistic scenarios (e.g., high ΔT at low flow)
    
    Args:
        model: Pyomo ConcreteModel
        time_set: Set of timesteps
        prefix: Variable name prefix
        T_supply, T_return: Temperature variables
        m_dot_demand: Consumer mass flow demand [kg/s]
        Q_demand: Consumer heat demand [MW]
        node_id: Node identifier
        config: Configuration dict
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for constraint building")
    
    state_cfg = config.get('state_validation', {})
    temp_cfg = state_cfg.get('temperature_constraints', {})
    enabled = temp_cfg.get('enforce_demand_based_return_temp', False)
    
    if not enabled:
        logger.debug(f"  Node {node_id}: demand_based_return_temp constraint disabled")
        return
    
    if not isinstance(T_return, pyo.Var) or not isinstance(m_dot_demand, pyo.Var):
        logger.debug(f"  Node {node_id}: T_return or m_dot_demand not Var, skipping")
        return
    
    cp_water = 4.186  # kJ/(kg·K)
    m_dot_min_kg_s = 0.01  # Min 10 g/s to avoid division by zero

    # Auxiliary variable for safe mass flow: max(m_dot_demand, m_dot_min)
    safe_mdot_name = f'{prefix}_safe_mdot'
    setattr(model, safe_mdot_name,
            pyo.Var(time_set, domain=pyo.NonNegativeReals))
    safe_mdot = getattr(model, safe_mdot_name)

    def safe_mdot_ge_demand(m, t):
        return safe_mdot[t] >= m_dot_demand[t]

    def safe_mdot_ge_min(m, t):
        return safe_mdot[t] >= m_dot_min_kg_s

    setattr(model, f'{prefix}_safe_mdot_ge_demand',
            pyo.Constraint(time_set, rule=safe_mdot_ge_demand))
    setattr(model, f'{prefix}_safe_mdot_ge_min',
            pyo.Constraint(time_set, rule=safe_mdot_ge_min))

    def demand_return_temp_rule(m, t):
        # T_return = T_supply - Q_demand / (m_dot * cp)
        # Rearranged: T_return * safe_mdot * cp = T_supply * safe_mdot * cp - Q_demand * 1000
        # (multiply by 1000 to convert MW to kW)
        return T_return[t] * safe_mdot[t] * cp_water == T_supply[t] * safe_mdot[t] * cp_water - Q_demand[t] * 1000

    constraint_name = f'{prefix}_DEMAND_RETURN_TEMP'
    setattr(model, constraint_name,
            pyo.Constraint(time_set, rule=demand_return_temp_rule))
    
    logger.info(
        f"  Node {node_id}: Added demand_based_return_temp constraint"
    )


def enforce_minimum_pressure(model, time_set, prefix: str, pressure_supply, pressure_return,
                            node_id: str, config: dict[str, Any]) -> None:
    """
    Enforce minimum operating pressure (cavitation and pump protection).
    
    Physical rationale:
    - Absolute pressure < ~0.3 bar causes water vaporization (cavitation)
    - Centrifugal pumps require positive head (minimum pressure drop)
    - Network must maintain >1 bar gauge (~2 bar absolute) for practical operation
    
    This sets lower bounds on pressure variables rather than adding constraints,
    so it's computationally cheap.
    
    Args:
        model: Pyomo ConcreteModel
        time_set: Set of timesteps
        prefix: Variable name prefix
        pressure_supply, pressure_return: Pressure variables [bar]
        node_id: Node identifier
        config: Configuration dict
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for constraint building")
    
    state_cfg = config.get('state_validation', {})
    press_cfg = state_cfg.get('pressure_constraints', {})
    min_pressure = press_cfg.get('min_pressure_bar', 0.5)
    
    if min_pressure <= 0:
        logger.debug(f"  Node {node_id}: min_pressure <= 0, skipping")
        return

    if not isinstance(pressure_supply, pyo.Var):
        logger.debug(f"  Node {node_id}: pressure_supply not Var, skipping")
        return

    # Use explicit Pyomo Constraints instead of setlb() so they are
    # visible in the model, deactivatable for debugging, and produce
    # clear infeasibility diagnostics instead of silent bound violations.
    min_p = min_pressure
    p_supply = pressure_supply

    def pressure_supply_min_rule(m, t):
        return p_supply[t] >= min_p

    setattr(model, f'{prefix}_pressure_supply_min',
            pyo.Constraint(time_set, rule=pressure_supply_min_rule))

    if isinstance(pressure_return, pyo.Var):
        p_return = pressure_return

        def pressure_return_min_rule(m, t):
            return p_return[t] >= min_p

        setattr(model, f'{prefix}_pressure_return_min',
                pyo.Constraint(time_set, rule=pressure_return_min_rule))

    logger.info(
        f"  Node {node_id}: Added minimum pressure constraints = {min_pressure} bar"
    )


def enforce_velocity_bounds(model, time_set, prefix: str, velocity, m_dot, node_id: str,
                           config: dict[str, Any]) -> None:
    """
    Enforce velocity bounds on pipe (max velocity as hard constraint).

    Physical rationale:
    - v_max < 2.5-3.0 m/s: limits noise, erosion, pipe wear (hard constraint)
    - v_min > 0.2-0.3 m/s: prevents stagnation, biofilm growth (post-solve check only)

    Note: Minimum velocity is NOT enforced as a hard constraint because pipes
    must allow zero flow (m_dot=0 → velocity=0). A hard v_min constraint would
    make the model infeasible whenever the optimizer reduces flow to zero.
    Minimum velocity is instead checked post-solve by NetworkValidator.

    Args:
        model: Pyomo ConcreteModel
        time_set: Set of timesteps
        prefix: Variable name prefix
        velocity: Velocity variable [m/s]
        m_dot: Mass flow variable [kg/s]
        node_id: Pipe identifier (or node if generic)
        config: Configuration dict
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for constraint building")

    state_cfg = config.get('state_validation', {})
    flow_cfg = state_cfg.get('flow_constraints', {})

    v_max = flow_cfg.get('max_velocity_m_s', 2.5)
    v_min = flow_cfg.get('min_velocity_m_s', 0.3)

    if v_max <= 0:
        logger.debug(f"  {node_id}: max velocity invalid, skipping")
        return

    if not isinstance(velocity, pyo.Var):
        logger.debug(f"  {node_id}: velocity not Var, skipping")
        return

    # Max velocity: hard constraint (always feasible since velocity >= 0)
    v_max_const = v_max
    vel_var = velocity

    def velocity_max_rule(m, t):
        return vel_var[t] <= v_max_const

    setattr(model, f'{prefix}_velocity_max',
            pyo.Constraint(time_set, rule=velocity_max_rule))

    # Min velocity: NOT a hard constraint (would conflict with zero-flow pipes).
    # Checked post-solve by NetworkValidator instead.
    logger.info(
        f"  {node_id}: Added max velocity constraint ({v_max} m/s). "
        f"Min velocity ({v_min} m/s) enforced via post-solve validation only."
    )


def add_network_state_validation_config(config_dict: dict[str, Any]) -> None:
    """
    Ensure state_validation section exists in config with sensible defaults.
    
    Called during model initialization to inject defaults if not present.
    
    Args:
        config_dict: Configuration dictionary (usually scenario or site config)
    """
    if 'state_validation' not in config_dict:
        config_dict['state_validation'] = {}
    
    state_cfg = config_dict['state_validation']
    
    # Temperature constraints
    if 'temperature_constraints' not in state_cfg:
        state_cfg['temperature_constraints'] = {
            'enforce_supply_ge_return': True,
            'enforce_demand_based_return_temp': False,  # Phase 2
            'temperature_tolerance_c': 0.1,
        }
    
    # Pressure constraints
    if 'pressure_constraints' not in state_cfg:
        state_cfg['pressure_constraints'] = {
            'min_pressure_bar': 0.5,
            'enforce_darcy_consistency': False,  # Phase 2
            'max_pressure_drop': 2.0,
        }
    
    # Flow constraints
    if 'flow_constraints' not in state_cfg:
        state_cfg['flow_constraints'] = {
            'min_velocity_m_s': 0.3,
            'max_velocity_m_s': 2.5,
            'enforce_reynolds_regime': False,  # Phase 2
        }
    
    logger.debug("Initialized state_validation config with Phase 1 defaults")
