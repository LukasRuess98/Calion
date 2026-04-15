"""
Thermal Node Component for District Heating Networks

Models network nodes where:
- Multiple pipes connect
- Heat producers inject heat
- Heat consumers extract heat
- Temperatures are mixed via enthalpy balance
- Mass flow is balanced at every node

Unified physics — no brownfield/greenfield distinction:
- T_supply and T_return are always Var (calculated, never fixed params)
- pressure_supply and pressure_return are Var (propagated from upstream)
- All node types (producer, consumer, junction) use the same constraint structure
- Node type only controls which component variables are linked

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
from ..state_constraints import (
    enforce_supply_ge_return_temperature,
    enforce_minimum_pressure,
)

logger = logging.getLogger(__name__)


@register_component("thermal_node")
class ThermalNodeBlock(BaseComponent):
    """
    Node in thermal network representing a connection point.

    Node Types:
    - producer (or plant): Heat production (HPs, generators) — no incoming pipes
    - consumer: Heat consumption (demand zones) — linked to Q_demand timeseries
    - junction: Pipe branching point — no demand, only mass balance

    Unified Physics (identical for all node types):
    - Mass balance:     Σ m_dot_in[t] = Σ m_dot_out[t] + m_dot_demand[t]
    - Enthalpy balance: T_supply[t] × Σ m_dot_in[t] = Σ (m_dot_in[t] × T_supply_out_pipe[t])
      (linearised mixing law — valid for constant cp)
    - Pressure: pressure_supply and pressure_return are Var, linked by network_manager

    Variables (per timestep t):
        - T_supply[t]:        Supply temperature at node (°C) — always a Var
        - T_return[t]:        Return temperature at node (°C) — always a Var (or Param for consumer)
        - pressure_supply[t]: Supply pressure at node (bar) — Var
        - pressure_return[t]: Return pressure at node (bar) — Var
        - m_dot_demand[t]:    Consumer mass flow demand (kg/s) — consumer nodes only
        - Q_demand[t]:        Consumer heat demand (MW) — consumer nodes only (Param)
    """

    @staticmethod
    def validate_config(config: dict[str, Any]) -> None:
        """Validate thermal node configuration."""
        required = ['id', 'type']
        for field in required:
            if field not in config:
                raise ValueError(f"ThermalNode config missing required field: {field}")

        # Accept 'plant' as an alias for 'producer' (backward compatibility)
        valid_types = ['producer', 'plant', 'consumer', 'junction']
        if config['type'] not in valid_types:
            raise ValueError(f"Node {config['id']}: type must be one of {valid_types}")

        if config['type'] == 'consumer':
            if 'demand_column' not in config and 'demand_profile' not in config:
                raise ValueError(
                    f"Consumer node {config['id']}: must specify demand_column or demand_profile"
                )

    @staticmethod
    def attach(model, time_set, config: dict[str, Any], buses: dict, network_pipes: dict) -> dict[str, Any]:
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
        # Normalise 'plant' → 'producer' for unified handling
        node_type = config['type']
        if node_type == 'plant':
            node_type = 'producer'

        logger.info(f"Attaching thermal node: {node_id} (type: {node_type})")

        # ============================================================
        # PARAMETERS
        # ============================================================

        cp_water = 4.186  # kJ/(kg·K)
        supply_temp_nominal_c = config.get('supply_temp_nominal_c', 90.0)
        return_temp_c = config.get('return_temp_c', 50.0)
        pressure_nominal_bar = config.get('pressure_nominal_supply_bar', 10.0)

        # ============================================================
        # IDENTIFY CONNECTED PIPES
        # ============================================================

        incoming_pipes = []
        outgoing_pipes = []

        for pipe_id, pipe_info in network_pipes.items():
            if pipe_info['to_node'] == node_id:
                incoming_pipes.append(pipe_id)
            if pipe_info['from_node'] == node_id:
                outgoing_pipes.append(pipe_id)

        logger.info(
            f"  Node {node_id}: {len(incoming_pipes)} incoming, {len(outgoing_pipes)} outgoing pipes"
        )

        # ============================================================
        # VARIABLES
        # ============================================================

        # Temperature bounds
        supply_temp_min = min(60, supply_temp_nominal_c - 30)
        supply_temp_max = max(130, supply_temp_nominal_c + 10)
        return_temp_min = 30
        return_temp_max = max(90, return_temp_c + 20)

        milp_linearize_temp = config.get('milp_linearize', False)
        _node_milp_temps = None  # populated below if MILP mode; used by heat_demand later

        if milp_linearize_temp:
            # MILP mode: both T_supply and T_return are load-dependent Params
            from .temperature_linearization import build_temperatures
            _lin_cfg = config.get('linearization', {})
            _demand_series = config.get('demand_series', {t: 0.0 for t in time_set})
            _peak_demand_mw = config.get('peak_demand_mw', 1.0)
            if _peak_demand_mw <= 0:
                _peak_demand_mw = 1.0
            _node_milp_temps = build_temperatures(
                _lin_cfg.get('method', 'fixed'),
                _lin_cfg,
                _demand_series,
                _peak_demand_mw,
                supply_temp_nominal_c,
                return_temp_c,
                time_set,
            )
            setattr(model, f'{prefix}_T_supply',
                    pyo.Param(time_set, initialize=lambda m, t: _node_milp_temps[t][0], mutable=True))
            setattr(model, f'{prefix}_T_return',
                    pyo.Param(time_set, initialize=lambda m, t: _node_milp_temps[t][1], mutable=True))
        else:
            # Non-MILP: T_supply is Var; T_return is Param or Var depending on config
            setattr(model, f'{prefix}_T_supply',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(supply_temp_min, supply_temp_max)))

            return_temp_profile = config.get('return_temp_profile', None)
            return_temp_range = config.get('return_temp_range', None)
            return_temp_load_factor = config.get('return_temp_load_factor', 0.0)

            if node_type == 'consumer' and return_temp_profile is not None:
                # Explicit time-varying profile → Param
                def return_temp_init(m, t):
                    return return_temp_profile.get(t, return_temp_c)
                setattr(model, f'{prefix}_T_return',
                        pyo.Param(time_set, initialize=return_temp_init, mutable=True))
                logger.info(
                    f"    Node {node_id}: using return temp profile "
                    f"(range: {min(return_temp_profile.values()):.1f}-"
                    f"{max(return_temp_profile.values()):.1f}°C)"
                )
            elif node_type == 'consumer' and return_temp_range is None and return_temp_load_factor == 0:
                # Constant return temperature → Param
                setattr(model, f'{prefix}_T_return',
                        pyo.Param(time_set, initialize=return_temp_c, mutable=True))
            else:
                # Variable return temperature (load-dependent or all non-consumer nodes)
                T_ret_min = return_temp_range[0] if return_temp_range else return_temp_min
                T_ret_max = return_temp_range[1] if return_temp_range else return_temp_max
                setattr(model, f'{prefix}_T_return',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals,
                               bounds=(T_ret_min, T_ret_max)))

        T_supply = getattr(model, f'{prefix}_T_supply')
        T_return = getattr(model, f'{prefix}_T_return')

        # Pressure variables — always Var, values propagated by network_manager
        setattr(model, f'{prefix}_pressure_supply',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(0, pressure_nominal_bar * 2.0)))
        setattr(model, f'{prefix}_pressure_return',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(0, pressure_nominal_bar * 2.0)))
        pressure_supply = getattr(model, f'{prefix}_pressure_supply')
        pressure_return = getattr(model, f'{prefix}_pressure_return')

        # Demand variables (consumer nodes only)
        Q_demand = None
        m_dot_demand = None
        delta_p_valve_var = None
        delta_p_min_station = 0.5

        if node_type == 'consumer':
            _node_heatd_attr = f'heatd_{node_id}'
            if hasattr(model, _node_heatd_attr):
                # Node-specific demand param created by system_builder from demand_column
                _node_heatd = getattr(model, _node_heatd_attr)
                def demand_init(m, t, _h=_node_heatd):
                    return pyo.value(_h[t])
                setattr(model, f'{prefix}_Q_demand',
                        pyo.Param(time_set, initialize=demand_init))
            elif 'demand_profile' in config:
                demand_profile = config['demand_profile']
                setattr(model, f'{prefix}_Q_demand',
                        pyo.Param(time_set, initialize=demand_profile))
            else:
                raise ValueError(
                    f"Consumer node {node_id}: no demand data available. "
                    f"Set demand_column in the node config so a heatd_{node_id} param is created."
                )

            Q_demand = getattr(model, f'{prefix}_Q_demand')

            setattr(model, f'{prefix}_m_dot_demand',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals))
            m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')

            # Valve differential pressure — absorbs excess pump head at consumer stations.
            # delta_p_valve[t] = P_supply[t] - P_return[t] - delta_p_min_station >= 0
            # This replaces the per-pipe pump-head constraint: the pump head only needs
            # to cover the critical path; shorter paths shed excess pressure via valves.
            delta_p_min_station = config.get('delta_p_min_consumer_bar', 0.5)
            setattr(model, f'{prefix}_delta_p_valve',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, 20.0)))
            delta_p_valve_var = getattr(model, f'{prefix}_delta_p_valve')

        # ============================================================
        # CONSTRAINTS
        # ============================================================

        # (1) Enthalpy balance (temperature mixing) for nodes with incoming pipes.
        #
        # Linearised mixing law (valid for constant cp):
        #   T_supply[t] × Σ_in m_dot_in[t] = Σ_in (m_dot_in[t] × T_supply_out_pipe[t])
        #
        # This sets node supply temperature as the flow-weighted average of all
        # incoming pipe supply outlet temperatures.  For a single pipe the
        # constraint reduces to a simple equality (T_node = T_pipe_out).
        if incoming_pipes and not milp_linearize_temp:
            if len(incoming_pipes) == 1:
                pipe_id = incoming_pipes[0]
                pipe_prefix = pipe_id.upper().replace('-', '_')

                def single_temp_rule(m, t, _pp=pipe_prefix):
                    pipe_T_out = getattr(m, f'{_pp}_T_supply_out')
                    return T_supply[t] == pipe_T_out[t]

                setattr(model, f'{prefix}_temp_mixing',
                        pyo.Constraint(time_set, rule=single_temp_rule))
                logger.info(f"    Node {node_id}: single-pipe temperature link")

            else:
                # Multi-pipe enthalpy balance: bilinear mixing (handled by QP/MIQP solver)
                def multi_temp_rule(m, t, _pipes=incoming_pipes):
                    total_m = sum(
                        getattr(m, f'{p.upper().replace("-", "_")}_m_dot')[t]
                        for p in _pipes
                    )
                    weighted_T = sum(
                        getattr(m, f'{p.upper().replace("-", "_")}_m_dot')[t] *
                        getattr(m, f'{p.upper().replace("-", "_")}_T_supply_out')[t]
                        for p in _pipes
                    )
                    return T_supply[t] * total_m == weighted_T

                setattr(model, f'{prefix}_temp_mixing',
                        pyo.Constraint(time_set, rule=multi_temp_rule))
                logger.info(
                    f"    Node {node_id}: multi-pipe enthalpy balance "
                    f"({len(incoming_pipes)} pipes, bilinear — needs QP solver)"
                )

        # MILP Mode: Fix T_supply to nominal (linear approximation for multi-pipe)
        # Only add constraint if T_supply is a Var (for producers); when T_supply
        # is already a Param (consumer/junction in MILP mode), it's already fixed.
        elif incoming_pipes and milp_linearize_temp and len(incoming_pipes) > 1:
            if isinstance(T_supply, pyo.Var):
                def multi_temp_milp_rule(m, t):
                    return T_supply[t] == supply_temp_nominal_c

                setattr(model, f'{prefix}_temp_mixing_milp',
                        pyo.Constraint(time_set, rule=multi_temp_milp_rule))
                logger.info(
                    f"    Node {node_id}: multi-pipe MILP mode — T_supply fixed to {supply_temp_nominal_c}°C"
                )
            else:
                logger.info(
                    f"    Node {node_id}: multi-pipe MILP mode — T_supply already a Param"
                )

        # (2) Mass balance: Σ m_dot_in[t] = Σ m_dot_out[t] + m_dot_demand[t]
        #
        # For producer nodes: incoming=[], outgoing=[...], m_dot_demand=0
        #   → trivial 0 == Σ m_dot_out (not a useful constraint; skip for producers)
        # For junction nodes: m_dot_demand=0
        #   → Σ m_dot_in == Σ m_dot_out
        # For consumer nodes: m_dot_demand >= 0
        #   → Σ m_dot_in == Σ m_dot_out + m_dot_demand
        #
        # In MILP mode, skip producer mass balance — the global heat balance already
        # handles energy conservation, and forcing pipe flow conservation at the plant
        # can over-constrain ring/loop topologies.
        #
        # In MILP mode, also skip consumer mass balance for terminal nodes (no outgoing
        # pipes).  Transport delay means Q_consumer[t] = Q_delivered[t−τ], so the pipe
        # flow m_dot[t] must be free to serve *future* demand rather than being pinned
        # to the *instantaneous* demand.  Demand is enforced via the Q_consumer linkage
        # in network_manager._link_consumer_demands instead.
        skip_producer_mass_balance = milp_linearize_temp and node_type == 'producer'
        skip_consumer_mass_balance = (
            milp_linearize_temp
            and node_type == 'consumer'
            and not outgoing_pipes
        )
        skip_mass_balance = skip_producer_mass_balance or skip_consumer_mass_balance
        if not skip_mass_balance and (incoming_pipes or (node_type != 'producer' and outgoing_pipes)):
            def mass_balance_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes):
                total_in = sum(
                    getattr(m, f'{p.upper().replace("-", "_")}_m_dot')[t]
                    for p in _in
                )
                total_out = sum(
                    getattr(m, f'{p.upper().replace("-", "_")}_m_dot')[t]
                    for p in _out
                )
                if node_type == 'consumer':
                    demand_var = getattr(m, f'{prefix}_m_dot_demand')
                    return total_in == total_out + demand_var[t]
                return total_in == total_out

            setattr(model, f'{prefix}_mass_balance',
                    pyo.Constraint(time_set, rule=mass_balance_rule))

        # (3) Heat demand satisfaction (consumer nodes only)
        # Q_demand [MW] = m_dot [kg/s] × c_p [kJ/(kg·K)] × (T_supply - T_return) [K] / 1000
        milp_linearize = config.get('milp_linearize', False)

        if node_type == 'consumer':
            if milp_linearize and not outgoing_pipes:
                # Terminal consumer in MILP mode: demand is enforced through
                # Q_consumer == Q_demand in the network manager.  The heat_demand
                # constraint (m_dot_demand ↔ Q_demand) is skipped because transport
                # delay decouples instantaneous flow from instantaneous demand.
                logger.info(
                    f"    Node {node_id}: MILP terminal consumer — "
                    f"heat_demand constraint skipped (enforced via Q_consumer)"
                )
            elif milp_linearize:
                # MILP passthrough consumer: use load-specific ΔT from build_temperatures
                def heat_demand_rule_milp(m, t, _temps=_node_milp_temps):
                    dT = _temps[t][0] - _temps[t][1]
                    if dT <= 0:
                        dT = 35.0  # safe fallback (should never happen after build-time validation)
                    return m_dot_demand[t] == Q_demand[t] * 1000 / (cp_water * dT)

                setattr(model, f'{prefix}_heat_demand',
                        pyo.Constraint(time_set, rule=heat_demand_rule_milp))
            else:
                # Full nonlinear mode (bilinear — requires QP/NLP solver)
                def heat_demand_rule(m, t):
                    return Q_demand[t] * 1000 == m_dot_demand[t] * cp_water * (T_supply[t] - T_return[t])

                setattr(model, f'{prefix}_heat_demand',
                        pyo.Constraint(time_set, rule=heat_demand_rule))

            # (3b) Consumer station differential pressure constraint.
            # delta_p_valve[t] = P_supply[t] - P_return[t] - delta_p_min_station
            # Since delta_p_valve >= 0, this enforces P_supply - P_return >= delta_p_min_station.
            # Correct pump-head model: pump overcomes critical-path resistance; excess
            # pressure at shorter paths is absorbed here by the control valve.
            def valve_dp_rule(m, t,
                              _ps=pressure_supply, _pr=pressure_return,
                              _dv=delta_p_valve_var, _dm=delta_p_min_station):
                return _ps[t] - _pr[t] == _dv[t] + _dm

            setattr(model, f'{prefix}_valve_dp',
                    pyo.Constraint(time_set, rule=valve_dp_rule))

            # (3c) Optional load-dependent return temperature
            if return_temp_range is not None and return_temp_load_factor > 0:
                T_ret_min_v, T_ret_max_v = return_temp_range
                T_ret_base = (T_ret_min_v + T_ret_max_v) / 2
                delta_T_range = T_ret_max_v - T_ret_min_v

                peak_demand_mw = config.get('peak_demand_mw', None)
                if peak_demand_mw is None:
                    _node_heatd_attr = f'heatd_{node_id}'
                    if hasattr(model, _node_heatd_attr):
                        _nh = getattr(model, _node_heatd_attr)
                        peak_demand_mw = max(pyo.value(_nh[t]) for t in time_set)
                    elif hasattr(model, 'heatd'):
                        peak_demand_mw = max(pyo.value(model.heatd[t]) for t in time_set)

                if peak_demand_mw and peak_demand_mw > 0:
                    k_ret_temp = return_temp_load_factor * delta_T_range / peak_demand_mw

                    def return_temp_load_rule(m, t):
                        return T_return[t] == T_ret_base + k_ret_temp * (
                            Q_demand[t] - 0.5 * peak_demand_mw
                        )

                    setattr(model, f'{prefix}_return_temp_load',
                            pyo.Constraint(time_set, rule=return_temp_load_rule))
                    logger.info(
                        f"    Node {node_id}: load-dependent T_return constraint "
                        f"(k={k_ret_temp:.4f} °C/MW, Q_max={peak_demand_mw:.2f} MW)"
                    )

        # ============================================================
        # PHASE 1: STATE CONSTRAINTS
        # ============================================================
        # Enforce physical validity of network states (temperatures, pressures)
        logger.info(f"  Attaching Phase 1 state constraints for node {node_id}")

        # 1. Supply >= Return temperature (prevent unphysical reversals)
        if isinstance(T_supply, pyo.Var):
            enforce_supply_ge_return_temperature(
                model, time_set, prefix, T_supply, T_return,
                node_id, config
            )

        # 2. Minimum pressure bound (cavitation + pump protection)
        enforce_minimum_pressure(
            model, time_set, prefix, pressure_supply, pressure_return,
            node_id, config
        )

        # ============================================================
        # RETURN REFERENCES
        # ============================================================

        result = {
            'id': node_id,
            'type': node_type,
            'T_supply': T_supply,
            'T_return': T_return,
            'pressure_supply': pressure_supply,
            'pressure_return': pressure_return,
            'incoming_pipes': incoming_pipes,
            'outgoing_pipes': outgoing_pipes,
        }

        if node_type == 'consumer':
            result['Q_demand'] = Q_demand
            result['m_dot_demand'] = m_dot_demand
            result['delta_p_valve'] = getattr(model, f'{prefix}_delta_p_valve')

        if node_type == 'producer':
            result['components'] = config.get('components', {})

        return result

    @staticmethod
    def get_results(model, time_set, config: dict[str, Any]) -> dict[str, Any]:
        """Extract results from solved model."""
        node_id = config.get('id') or config.get('node_id')
        prefix = node_id.upper().replace('-', '_')
        node_type = config['type']
        # Normalise alias
        if node_type == 'plant':
            node_type = 'producer'

        T_supply = getattr(model, f'{prefix}_T_supply')
        T_return = getattr(model, f'{prefix}_T_return')

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

        if node_type == 'consumer':
            Q_demand = getattr(model, f'{prefix}_Q_demand')
            m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')

            q_demand_series = [pyo.value(Q_demand[t]) for t in time_set]
            m_dot_series = [safe_value(m_dot_demand, t, 0.0) for t in time_set]

            dt_h = getattr(model, 'dt_h', 1.0)
            total_demand_mwh = sum(q_demand_series) * dt_h

            dp_valve_var = getattr(model, f'{prefix}_delta_p_valve', None)
            dp_valve_series = (
                [safe_value(dp_valve_var, t, 0.0) for t in time_set]
                if dp_valve_var is not None else [0.0] * len(time_set)
            )

            result.update({
                'Q_demand_mw': q_demand_series,
                'm_dot_demand_kg_s': m_dot_series,
                'total_demand_mwh': total_demand_mwh,
                'avg_demand_mw': sum(q_demand_series) / len(q_demand_series),
                'peak_demand_mw': max(q_demand_series),
                'delta_p_valve_bar': dp_valve_series,
                'min_delta_p_valve_bar': min(dp_valve_series),
            })

        return result
