"""
Heat Exchanger Component for Multi-Temperature District Heating Networks
=========================================================================

Models heat transfer between two temperature levels (networks):
- Primary side: High-temperature network (typically return flow)
- Secondary side: Low-temperature network (typically supply flow)

Key Features:
- MILP-compatible linearized heat transfer model
- Configurable effectiveness and capacity limits
- Supports cascading heat use (waste heat recovery)

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

from ..component import BaseComponent
from ..registry import register_component

logger = logging.getLogger(__name__)


@register_component("heat_exchanger")
class HeatExchangerBlock(BaseComponent):
    """
    Heat exchanger coupling two temperature networks.

    Models counter-flow heat exchanger with effectiveness method:
        Q_transfer = ε × C_min × (T_prim_in - T_sec_in)

    For MILP compatibility, temperatures are parameters (from connected networks)
    and heat transfer is the decision variable.

    Variables (per timestep t):
        - Q_transfer[t]: Heat transferred [MW]
        - active[t]: Binary, whether HX is operating

    Parameters:
        - effectiveness: Heat exchanger effectiveness (0-1)
        - max_power_mw: Maximum heat transfer capacity [MW]
        - min_power_mw: Minimum operating power [MW]
        - primary_network: ID of high-temp network (source)
        - secondary_network: ID of low-temp network (sink)
    """

    @staticmethod
    def validate_config(config: dict[str, Any]) -> None:
        """Validate heat exchanger configuration."""
        required = ['id', 'primary_network', 'secondary_network']
        for field in required:
            if field not in config:
                raise ValueError(f"HeatExchanger config missing required field: {field}")

        effectiveness = config.get('effectiveness', 0.85)
        if not 0 < effectiveness <= 1:
            raise ValueError(f"HeatExchanger effectiveness must be in (0, 1], got {effectiveness}")

    @staticmethod
    def attach(model, time_set, config: dict[str, Any], buses: dict | None = None) -> dict[str, Any]:
        """
        Attach heat exchanger component to Pyomo model.

        Args:
            model: Pyomo ConcreteModel
            time_set: Set of timesteps
            config: Heat exchanger configuration dict
            buses: Dict of bus components (optional)

        Returns:
            Dict with variable references and metadata
        """
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach blocks")

        hx_id = config.get('id', 'HX_1')
        prefix = hx_id.upper().replace('-', '_')

        logger.info(f"Attaching heat exchanger: {hx_id}")

        # ============================================================
        # PARAMETERS
        # ============================================================

        effectiveness = config.get('effectiveness', 0.85)
        max_power_mw = config.get('max_power_mw', 10.0)
        min_power_mw = config.get('min_power_mw', 0.0)
        config.get('min_load_fraction', 0.1)

        # Temperature parameters (will be linked to networks)
        T_prim_in_nominal = config.get('T_primary_in_c', 60.0)  # Return from high-temp
        config.get('T_primary_out_c', 40.0)
        T_sec_in_nominal = config.get('T_secondary_in_c', 30.0)  # Return to low-temp
        config.get('T_secondary_out_c', 55.0)  # Supply to low-temp

        # Fluid properties
        cp_water = 4.186  # kJ/(kg·K)

        # Network references
        primary_network = config.get('primary_network')
        secondary_network = config.get('secondary_network')
        primary_side = config.get('primary_side', 'return')  # 'supply' or 'return'
        secondary_side = config.get('secondary_side', 'supply')  # 'supply' or 'return'

        # Investment parameters
        investable = config.get('investable', False)
        capex_eur_per_mw = config.get('capex_eur_per_mw', 50000)

        logger.info(f"  Effectiveness: {effectiveness}")
        logger.info(f"  Capacity: {min_power_mw}-{max_power_mw} MW")
        logger.info(f"  Primary: {primary_network} ({primary_side})")
        logger.info(f"  Secondary: {secondary_network} ({secondary_side})")

        # ============================================================
        # VARIABLES
        # ============================================================

        # Heat transfer [MW]
        Q_transfer = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                             bounds=(0, max_power_mw * 1.1))
        setattr(model, f'{prefix}_Q_transfer', Q_transfer)

        # Operating binary
        active = pyo.Var(time_set, domain=pyo.Binary)
        setattr(model, f'{prefix}_active', active)

        # Build decision (for investment)
        if investable:
            build = pyo.Var(domain=pyo.Binary)
            setattr(model, f'{prefix}_build', build)

            # Capacity variable
            capacity = pyo.Var(domain=pyo.NonNegativeReals,
                              bounds=(0, max_power_mw))
            setattr(model, f'{prefix}_capacity', capacity)
        else:
            build = None
            capacity = None

        # Temperature variables (linked to networks or fixed)
        T_prim_in = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(20, 150))
        T_prim_out = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                            bounds=(20, 150))
        T_sec_in = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                          bounds=(20, 100))
        T_sec_out = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(20, 100))

        setattr(model, f'{prefix}_T_prim_in', T_prim_in)
        setattr(model, f'{prefix}_T_prim_out', T_prim_out)
        setattr(model, f'{prefix}_T_sec_in', T_sec_in)
        setattr(model, f'{prefix}_T_sec_out', T_sec_out)

        # Mass flow rates [kg/s]
        m_dot_prim = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                            bounds=(0, 500))
        m_dot_sec = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(0, 500))

        setattr(model, f'{prefix}_m_dot_prim', m_dot_prim)
        setattr(model, f'{prefix}_m_dot_sec', m_dot_sec)

        # ============================================================
        # PARAMETERS (fixed values or from config)
        # ============================================================

        # Store effectiveness as parameter
        setattr(model, f'{prefix}_effectiveness',
                pyo.Param(initialize=effectiveness))

        # Maximum capacity parameter
        setattr(model, f'{prefix}_max_power',
                pyo.Param(initialize=max_power_mw))

        # ============================================================
        # CONSTRAINTS
        # ============================================================

        # (1) Capacity limit
        def capacity_limit_rule(m, t):
            if investable and capacity is not None:
                return Q_transfer[t] <= capacity
            else:
                return Q_transfer[t] <= max_power_mw * active[t]

        setattr(model, f'{prefix}_capacity_limit',
                pyo.Constraint(time_set, rule=capacity_limit_rule))

        # (2) Minimum load when active
        def min_load_rule(m, t):
            return Q_transfer[t] >= min_power_mw * active[t]

        setattr(model, f'{prefix}_min_load',
                pyo.Constraint(time_set, rule=min_load_rule))

        # (3) Energy balance - Primary side
        # Q_transfer = m_dot_prim × c_p × (T_prim_in - T_prim_out)
        def energy_balance_primary_rule(m, t):
            # Q [MW] = m_dot [kg/s] × c_p [kJ/(kg·K)] × ΔT [K] / 1000
            return Q_transfer[t] * 1000 == m_dot_prim[t] * cp_water * (T_prim_in[t] - T_prim_out[t])

        setattr(model, f'{prefix}_energy_balance_prim',
                pyo.Constraint(time_set, rule=energy_balance_primary_rule))

        # (4) Energy balance - Secondary side
        # Q_transfer = m_dot_sec × c_p × (T_sec_out - T_sec_in)
        def energy_balance_secondary_rule(m, t):
            return Q_transfer[t] * 1000 == m_dot_sec[t] * cp_water * (T_sec_out[t] - T_sec_in[t])

        setattr(model, f'{prefix}_energy_balance_sec',
                pyo.Constraint(time_set, rule=energy_balance_secondary_rule))

        # (5) Effectiveness constraint (linearized)
        # For counter-flow HX: Q_actual ≤ ε × Q_max_possible
        # Q_max = C_min × (T_prim_in - T_sec_in)
        # Simplified linear constraint:
        # T_sec_out ≤ T_prim_in - (1-ε) × (T_prim_in - T_sec_in)
        # Which simplifies to: T_sec_out ≤ ε × T_prim_in + (1-ε) × T_sec_in

        def effectiveness_constraint_rule(m, t):
            # Approach temperature constraint
            # T_sec_out cannot exceed T_prim_in (2nd law)
            # With effectiveness: T_sec_out ≤ T_sec_in + ε × (T_prim_in - T_sec_in)
            return T_sec_out[t] <= T_sec_in[t] + effectiveness * (T_prim_in[t] - T_sec_in[t])

        setattr(model, f'{prefix}_effectiveness_constraint',
                pyo.Constraint(time_set, rule=effectiveness_constraint_rule))

        # (6) Minimum approach temperature (pinch point)
        min_approach_temp = config.get('min_approach_temp_c', 3.0)

        def pinch_constraint_rule(m, t):
            # T_prim_out must be higher than T_sec_in by at least approach temp
            return T_prim_out[t] >= T_sec_in[t] + min_approach_temp - 100 * (1 - active[t])

        setattr(model, f'{prefix}_pinch_constraint',
                pyo.Constraint(time_set, rule=pinch_constraint_rule))

        # (7) Investment constraints (if investable)
        if investable and build is not None and capacity is not None:
            def build_capacity_rule(m):
                return capacity <= max_power_mw * build

            setattr(model, f'{prefix}_build_capacity',
                    pyo.Constraint(rule=build_capacity_rule))

            def active_build_rule(m, t):
                return active[t] <= build

            setattr(model, f'{prefix}_active_build',
                    pyo.Constraint(time_set, rule=active_build_rule))

        # ============================================================
        # FIX NOMINAL TEMPERATURES (initial values for network coupling)
        # ============================================================
        # Temperatures are fixed to nominal values here as initial starting
        # points.  The network_manager will overwrite these with constraint-
        # based links once all components are attached.

        for t in time_set:
            T_prim_in[t].fix(T_prim_in_nominal)
            T_sec_in[t].fix(T_sec_in_nominal)

        logger.info(f"  T_prim_in={T_prim_in_nominal}°C, T_sec_in={T_sec_in_nominal}°C (initial, network will link)")

        # ============================================================
        # RETURN REFERENCES
        # ============================================================

        result = {
            'id': hx_id,
            'type': 'heat_exchanger',
            'Q_transfer': Q_transfer,
            'active': active,
            'T_prim_in': T_prim_in,
            'T_prim_out': T_prim_out,
            'T_sec_in': T_sec_in,
            'T_sec_out': T_sec_out,
            'm_dot_prim': m_dot_prim,
            'm_dot_sec': m_dot_sec,
            'effectiveness': effectiveness,
            'max_power_mw': max_power_mw,
            'primary_network': primary_network,
            'secondary_network': secondary_network,
            'primary_side': primary_side,
            'secondary_side': secondary_side,
        }

        if investable:
            result['build'] = build
            result['capacity'] = capacity
            result['capex_eur_per_mw'] = capex_eur_per_mw

        # Flows for integration
        result['flows'] = {
            'heat_in': {'var': Q_transfer, 'bus': f'{primary_network}_thermal'},
            'heat_out': {'var': Q_transfer, 'bus': f'{secondary_network}_thermal'},
        }

        return result

    @staticmethod
    def get_results(model, time_set, config: dict[str, Any]) -> dict[str, Any]:
        """Extract results from solved model."""
        hx_id = config.get('id', 'HX_1')
        prefix = hx_id.upper().replace('-', '_')

        Q_transfer = getattr(model, f'{prefix}_Q_transfer', None)
        active = getattr(model, f'{prefix}_active', None)
        T_prim_in = getattr(model, f'{prefix}_T_prim_in', None)
        T_prim_out = getattr(model, f'{prefix}_T_prim_out', None)
        T_sec_in = getattr(model, f'{prefix}_T_sec_in', None)
        T_sec_out = getattr(model, f'{prefix}_T_sec_out', None)

        results = {
            'id': hx_id,
            'type': 'heat_exchanger',
        }

        if Q_transfer is not None:
            results['Q_transfer_mw'] = [pyo.value(Q_transfer[t]) for t in time_set]
            results['total_heat_transferred_mwh'] = sum(results['Q_transfer_mw'])

        if active is not None:
            results['active'] = [pyo.value(active[t]) for t in time_set]
            results['operating_hours'] = sum(results['active'])

        if T_prim_in is not None:
            results['T_prim_in_c'] = [pyo.value(T_prim_in[t]) for t in time_set]

        if T_prim_out is not None:
            results['T_prim_out_c'] = [pyo.value(T_prim_out[t]) for t in time_set]

        if T_sec_in is not None:
            results['T_sec_in_c'] = [pyo.value(T_sec_in[t]) for t in time_set]

        if T_sec_out is not None:
            results['T_sec_out_c'] = [pyo.value(T_sec_out[t]) for t in time_set]

        # Calculate average temperatures
        if 'T_prim_in_c' in results and 'T_sec_out_c' in results:
            results['avg_T_prim_in_c'] = sum(results['T_prim_in_c']) / len(results['T_prim_in_c'])
            results['avg_T_sec_out_c'] = sum(results['T_sec_out_c']) / len(results['T_sec_out_c'])

        # Investment results
        build = getattr(model, f'{prefix}_build', None)
        capacity = getattr(model, f'{prefix}_capacity', None)

        if build is not None:
            results['build'] = pyo.value(build)

        if capacity is not None:
            results['capacity_mw'] = pyo.value(capacity)

        return results
