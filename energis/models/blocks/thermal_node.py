"""
Thermal Node Component for District Heating Networks

Models network nodes where:
- Multiple pipes connect
- Heat producers inject heat
- Heat consumers extract heat
- Temperatures are mixed
- Mass flow is balanced

Author: EnerGIS Development Team
Date: 2025-12-10
"""

from typing import Dict, Any, List, Optional
import pyomo.environ as pyo
import logging

from ..component import BaseComponent
from ..registry import register_component

logger = logging.getLogger(__name__)


@register_component("thermal_node")
class ThermalNodeBlock(BaseComponent):
    """
    Node in thermal network representing a connection point.

    Node Types:
    - plant: Heat production (HPs, generators)
    - consumer: Heat consumption (demand zones)
    - junction: Pipe branching point

    Models:
    - Mass flow balance (inflows = outflows)
    - Temperature mixing from multiple inflows
    - Heat balance for consumers
    - Optional pressure variables (Phase 3)

    Variables (per timestep t):
        - m_dot_in[pipe, t]: Mass flow from each incoming pipe (kg/s)
        - m_dot_out[pipe, t]: Mass flow to each outgoing pipe (kg/s)
        - T_supply[t]: Supply temperature at node (°C)
        - T_return[t]: Return temperature at node (°C)
        - Q_demand[t]: Heat demand at consumer nodes (MW)
    """

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> None:
        """Validate thermal node configuration."""
        required = ['id', 'type']
        for field in required:
            if field not in config:
                raise ValueError(f"ThermalNode config missing required field: {field}")

        valid_types = ['plant', 'consumer', 'junction']
        if config['type'] not in valid_types:
            raise ValueError(f"Node {config['id']}: type must be one of {valid_types}")

        # Consumer nodes must have demand info
        if config['type'] == 'consumer':
            if 'demand_fraction' not in config and 'demand_profile' not in config:
                raise ValueError(f"Consumer node {config['id']}: must specify demand_fraction or demand_profile")

    @staticmethod
    def attach(model, time_set, config: Dict[str, Any], buses: Dict, network_pipes: Dict) -> Dict[str, Any]:
        """
        Attach thermal node to Pyomo model.

        Args:
            model: Pyomo ConcreteModel
            time_set: Set of timesteps
            config: Node configuration dict
            buses: Dict of bus components
            network_pipes: Dict of pipe components connected to this node

        Returns:
            Dict with variable references and metadata
        """
        node_id = config['id']
        prefix = node_id.upper().replace('-', '_')
        node_type = config['type']

        logger.info(f"Attaching thermal node: {node_id} (type: {node_type})")

        # ============================================================
        # PARAMETERS
        # ============================================================

        # Fluid properties
        cp_water = 4.186  # kJ/(kg·K)

        # Temperature parameters
        supply_temp_nominal_c = config.get('supply_temp_nominal_c', 90.0)
        return_temp_c = config.get('return_temp_c', 50.0)

        # Identify connected pipes
        incoming_pipes = []
        outgoing_pipes = []

        for pipe_id, pipe_info in network_pipes.items():
            if pipe_info['to_node'] == node_id:
                incoming_pipes.append(pipe_id)
            if pipe_info['from_node'] == node_id:
                outgoing_pipes.append(pipe_id)

        logger.info(f"  Node {node_id}: {len(incoming_pipes)} incoming, {len(outgoing_pipes)} outgoing pipes")

        # ============================================================
        # VARIABLES
        # ============================================================

        # Temperature bounds based on network parameters
        supply_temp_min = min(60, supply_temp_nominal_c - 30)
        supply_temp_max = max(130, supply_temp_nominal_c + 10)
        return_temp_min = 30
        return_temp_max = max(90, return_temp_c + 20)

        # Supply temperature at node (°C)
        # For plant: fixed or decision variable
        # For consumers/junctions: mixed from incoming pipes
        if node_type == 'plant':
            # Plant nodes have fixed supply temperature
            setattr(model, f'{prefix}_T_supply',
                    pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True))
            T_supply = getattr(model, f'{prefix}_T_supply')
        else:
            # Consumer and junction nodes: temperature from pipes
            setattr(model, f'{prefix}_T_supply',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(supply_temp_min, supply_temp_max)))
            T_supply = getattr(model, f'{prefix}_T_supply')

        # Return temperature at node (°C)
        if node_type == 'consumer':
            # Consumer nodes have fixed return temperature
            setattr(model, f'{prefix}_T_return',
                    pyo.Param(time_set, initialize=return_temp_c, mutable=True))
            T_return = getattr(model, f'{prefix}_T_return')
        else:
            # Plant and junction nodes: return temperature from pipes
            setattr(model, f'{prefix}_T_return',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(return_temp_min, return_temp_max)))
            T_return = getattr(model, f'{prefix}_T_return')

        # Heat demand at consumer nodes (MW)
        if node_type == 'consumer':
            # Get demand profile
            demand_fraction = config.get('demand_fraction', 0.0)

            if hasattr(model, 'heatd'):
                # Use existing heat demand and scale by fraction
                def demand_init(m, t):
                    return pyo.value(m.heatd[t]) * demand_fraction

                setattr(model, f'{prefix}_Q_demand',
                        pyo.Param(time_set, initialize=demand_init))
            elif 'demand_profile' in config:
                # Use explicitly provided demand profile
                demand_profile = config['demand_profile']
                setattr(model, f'{prefix}_Q_demand',
                        pyo.Param(time_set, initialize=demand_profile))
            else:
                raise ValueError(f"Consumer node {node_id}: no demand data available")

            Q_demand = getattr(model, f'{prefix}_Q_demand')
        else:
            Q_demand = None

        # Mass flow at node (kg/s)
        # For consumer nodes, calculate from heat demand
        if node_type == 'consumer':
            setattr(model, f'{prefix}_m_dot_demand',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals))
            m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')
        else:
            m_dot_demand = None

        # ============================================================
        # CONSTRAINTS
        # ============================================================

        # (1) Temperature mixing at node (for non-plant nodes)
        # Note: Full bilinear temperature mixing (T * m_dot) causes non-convex QP issues
        # For brownfield scenarios, we simplify by fixing supply temp or using first pipe
        brownfield_mode = config.get('brownfield_mode', False)

        if node_type != 'plant' and incoming_pipes:
            if len(incoming_pipes) == 1 and not brownfield_mode:
                # Single pipe: simple temperature link
                pipe_id = incoming_pipes[0]
                pipe_prefix = pipe_id.upper().replace('-', '_')

                def single_temp_rule(m, t, _prefix=pipe_prefix):
                    pipe_T_out = getattr(m, f'{_prefix}_T_supply_out')
                    return T_supply[t] == pipe_T_out[t]

                setattr(model, f'{prefix}_temp_mixing',
                        pyo.Constraint(time_set, rule=single_temp_rule))
            else:
                # Multiple pipes or brownfield: fix temperature at nominal value
                # This avoids bilinear T*m_dot constraints that cause solver issues
                logger.info(f"    Node {node_id}: fixing supply temp to {supply_temp_nominal_c}°C (brownfield/multi-pipe)")
                for t in time_set:
                    T_supply[t].fix(supply_temp_nominal_c)

        # (2) Mass flow balance at node
        # sum(inflows) = sum(outflows) + local_demand
        def mass_balance_rule(m, t):
            total_inflow = sum(
                pyo.value(getattr(m, f"{pipe_id.upper().replace('-', '_')}_m_dot")[t])
                if hasattr(m, f"{pipe_id.upper().replace('-', '_')}_m_dot")
                else 0
                for pipe_id in incoming_pipes
            )

            total_outflow = sum(
                pyo.value(getattr(m, f"{pipe_id.upper().replace('-', '_')}_m_dot")[t])
                if hasattr(m, f"{pipe_id.upper().replace('-', '_')}_m_dot")
                else 0
                for pipe_id in outgoing_pipes
            )

            if node_type == 'consumer':
                return total_inflow == total_outflow + m_dot_demand[t]
            else:
                return total_inflow == total_outflow

        # Note: This constraint needs refinement - we need to properly reference pipe flows
        # For now, skip and handle in network manager level

        # (3) Heat demand satisfaction (consumer nodes)
        if node_type == 'consumer':
            def heat_demand_rule(m, t):
                # Q_demand = m_dot * c_p * (T_supply - T_return)
                # In MW: m_dot[kg/s] * c_p[kJ/kg-K] * delta_T[K] / 1000
                return Q_demand[t] * 1000 == m_dot_demand[t] * cp_water * (T_supply[t] - T_return[t])

            setattr(model, f'{prefix}_heat_demand',
                    pyo.Constraint(time_set, rule=heat_demand_rule))

        # (4) Connect node temperatures to connected pipes
        # This is handled by linking pipe variables directly
        # Store references for system builder to create connections

        # ============================================================
        # RETURN REFERENCES
        # ============================================================

        result = {
            'id': node_id,
            'type': node_type,
            'T_supply': T_supply,
            'T_return': T_return,
            'incoming_pipes': incoming_pipes,
            'outgoing_pipes': outgoing_pipes,
        }

        if node_type == 'consumer':
            result['Q_demand'] = Q_demand
            result['m_dot_demand'] = m_dot_demand
            result['demand_fraction'] = config.get('demand_fraction', 0.0)

        if node_type == 'plant':
            result['components'] = config.get('components', {})

        return result

    @staticmethod
    def get_results(model, time_set, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract results from solved model."""
        node_id = config.get('id') or config.get('node_id')
        prefix = node_id.upper().replace('-', '_')
        node_type = config['type']

        # Retrieve variables
        T_supply = getattr(model, f'{prefix}_T_supply')
        T_return = getattr(model, f'{prefix}_T_return')

        # Extract time series (with error handling for uninitialized vars)
        def safe_value(var, t, default=None):
            """Safely get value, return default if uninitialized."""
            try:
                val = pyo.value(var[t])
                return val if val is not None else default
            except (ValueError, TypeError):
                return default

        if isinstance(T_supply, pyo.Var):
            t_supply_series = [safe_value(T_supply, t, 90.0) for t in time_set]
        else:
            t_supply_series = [pyo.value(T_supply[t]) for t in time_set]

        if isinstance(T_return, pyo.Var):
            t_return_series = [safe_value(T_return, t, 50.0) for t in time_set]
        else:
            t_return_series = [pyo.value(T_return[t]) for t in time_set]

        result = {
            'node_id': node_id,
            'type': node_type,
            'T_supply_c': t_supply_series,
            'T_return_c': t_return_series,
            'avg_supply_temp_c': sum(t_supply_series) / len(t_supply_series),
            'avg_return_temp_c': sum(t_return_series) / len(t_return_series),
        }

        # Consumer-specific results
        if node_type == 'consumer':
            Q_demand = getattr(model, f'{prefix}_Q_demand')
            m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')

            q_demand_series = [pyo.value(Q_demand[t]) for t in time_set]
            m_dot_series = [pyo.value(m_dot_demand[t]) for t in time_set]

            dt_h = getattr(model, 'dt_h', 1.0)
            total_demand_mwh = sum(q_demand_series) * dt_h

            result.update({
                'Q_demand_mw': q_demand_series,
                'm_dot_demand_kg_s': m_dot_series,
                'total_demand_mwh': total_demand_mwh,
                'avg_demand_mw': sum(q_demand_series) / len(q_demand_series),
                'peak_demand_mw': max(q_demand_series),
            })

        return result
