"""
Thermal Node Component for District Heating Networks

Models network nodes where:
- Multiple pipes connect
- Heat producers inject heat
- Heat consumers extract heat
- Temperatures are mixed via enthalpy balance
- Mass flow is balanced at every node

Unified physics â€” no brownfield/greenfield distinction:
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
    - producer (or plant): Heat production (HPs, generators) â€” no incoming pipes
    - consumer: Heat consumption (demand zones) â€” linked to Q_demand timeseries
    - junction: Pipe branching point â€” no demand, only mass balance

    Unified Physics (identical for all node types):
    - Mass balance:     Î£ m_dot_in[t] = Î£ m_dot_out[t] + m_dot_demand[t]
    - Enthalpy balance: T_supply[t] Ã— Î£ m_dot_in[t] = Î£ (m_dot_in[t] Ã— T_supply_out_pipe[t])
      (linearised mixing law â€” valid for constant cp)
    - Pressure: pressure_supply and pressure_return are Var, linked by network_manager

    Variables (per timestep t):
        - T_supply[t]:        Supply temperature at node (Â°C) â€” always a Var
        - T_return[t]:        Return temperature at node (Â°C) â€” always a Var (or Param for consumer)
        - pressure_supply[t]: Supply pressure at node (bar) â€” Var
        - pressure_return[t]: Return pressure at node (bar) â€” Var
        - m_dot_demand[t]:    Consumer mass flow demand (kg/s) â€” consumer nodes only
        - Q_demand[t]:        Consumer heat demand (MW) â€” consumer nodes only (Param)
    """

    @staticmethod
    def validate_config(config: dict[str, Any]) -> None:
        """Validate thermal node configuration."""
        required = ['id', 'type']
        for field in required:
            if field not in config:
                raise ValueError(f"ThermalNode config missing required field: {field}")

        # Accept 'plant' as alias for 'producer', 'mixed' for producer+consumer
        valid_types = ['producer', 'plant', 'consumer', 'junction', 'mixed']
        if config['type'] not in valid_types:
            raise ValueError(f"Node {config['id']}: type must be one of {valid_types}")

        if config['type'] in ('consumer', 'mixed'):
            if 'demand_fraction' not in config and 'demand_profile' not in config and 'consumers' not in config:
                raise ValueError(
                    f"Consumer node {config['id']}: must specify demand_fraction, demand_profile, or consumers"
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
        # Normalise 'plant' â†’ 'producer' for unified handling
        node_type = config['type']
        if node_type == 'plant':
            node_type = 'producer'

        logger.info(f"Attaching thermal node: {node_id} (type: {node_type})")

        # ============================================================
        # PARAMETERS
        # ============================================================

        cp_water = 4.186  # kJ/(kgÂ·K)
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

        # T_supply: Var by default, but fixed Param in MILP-linearized mode
        milp_linearize_temp = config.get('temperature_linearize')
        if milp_linearize_temp is None:
            milp_linearize_temp = config.get('milp_linearize', False)

        if milp_linearize_temp and node_type in ('consumer', 'junction', 'mixed'):
            # MILP mode: fix supply temperature to nominal value â†’ eliminates bilinear products
            setattr(model, f'{prefix}_T_supply',
                    pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True))
        else:
            setattr(model, f'{prefix}_T_supply',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(supply_temp_min, supply_temp_max)))
        T_supply = getattr(model, f'{prefix}_T_supply')

        # T_return: Param for constant consumer return temps, Var otherwise
        return_model_mode = str(config.get('return_model_mode', 'legacy')).strip().lower()
        if return_model_mode not in ('legacy', 'stateful_v2'):
            return_model_mode = 'legacy'
        stateful_return_v2 = bool(
            return_model_mode == 'stateful_v2' and node_type in ('consumer', 'mixed')
        )
        return_temp_profile = config.get('return_temp_profile', None)
        return_temp_range = config.get('return_temp_range', None)
        return_temp_load_factor = config.get('return_temp_load_factor', 0.0)
        return_temp_ref_profile = config.get('return_temp_ref_profile', None)
        return_temp_band_profile = config.get('return_temp_band_profile', None)
        return_temp_band_c = float(config.get('return_temp_band_c', 0.0) or 0.0)
        return_temp_ref_shift_c = float(config.get('return_temp_ref_shift_c', 0.0) or 0.0)
        return_temp_max_step_c = float(config.get('return_temp_max_step_c', 0.0) or 0.0)
        return_temp_soft_anchor_enabled = bool(config.get('return_temp_soft_anchor_enabled', False))
        return_temp_soft_anchor_weight_frame = float(
            config.get('return_temp_soft_anchor_weight_frame', 1200.0) or 1200.0
        )
        return_temp_soft_anchor_weight_load = float(
            config.get('return_temp_soft_anchor_weight_load', 400.0) or 400.0
        )
        return_temp_soft_anchor_weight_frame = max(0.0, return_temp_soft_anchor_weight_frame)
        return_temp_soft_anchor_weight_load = max(0.0, return_temp_soft_anchor_weight_load)
        return_state_penalty = float(config.get('return_state_penalty_eur_per_c', 2500.0) or 2500.0)
        return_link_penalty = float(config.get('return_link_penalty_eur_per_c', 5000.0) or 5000.0)
        flow_anchor_penalty = float(config.get('flow_anchor_penalty_eur_per_kg_s', 0.0) or 0.0)
        return_state_penalty = max(0.0, return_state_penalty)
        return_link_penalty = max(0.0, return_link_penalty)
        flow_anchor_penalty = max(0.0, flow_anchor_penalty)
        if node_id == 'j_1':
            return_temp_ref_shift_c = float(max(-6.0, min(6.0, return_temp_ref_shift_c)))

        if stateful_return_v2:
            t_ret_min = 30.0
            t_ret_max = 80.0
            if isinstance(return_temp_range, (list, tuple)) and len(return_temp_range) >= 2:
                try:
                    t_ret_min = float(max(30.0, min(80.0, float(return_temp_range[0]))))
                    t_ret_max = float(max(t_ret_min + 0.1, min(80.0, float(return_temp_range[1]))))
                except Exception:
                    t_ret_min, t_ret_max = 30.0, 80.0
            setattr(
                model,
                f'{prefix}_T_return',
                pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(t_ret_min, t_ret_max)),
            )
            logger.info(
                f"    Node {node_id}: stateful_v2 return model active "
                f"(T_return in [{t_ret_min:.1f}, {t_ret_max:.1f}] C)"
            )
        elif node_type in ('consumer', 'mixed') and return_temp_profile is not None:
            # Explicit time-varying profile â†’ Param
            def return_temp_init(m, t):
                return return_temp_profile.get(t, return_temp_profile.get(str(t), return_temp_c))
            setattr(model, f'{prefix}_T_return',
                    pyo.Param(time_set, initialize=return_temp_init, mutable=True))
            logger.info(
                f"    Node {node_id}: using return temp profile "
                f"(range: {min(return_temp_profile.values()):.1f}-"
                f"{max(return_temp_profile.values()):.1f}Â°C)"
            )
        elif node_type in ('consumer', 'mixed') and return_temp_range is None and return_temp_load_factor == 0:
            # Constant return temperature â†’ Param
            setattr(model, f'{prefix}_T_return',
                    pyo.Param(time_set, initialize=return_temp_c, mutable=True))
        else:
            # Variable return temperature (load-dependent or all non-consumer nodes)
            T_ret_min = return_temp_range[0] if return_temp_range else return_temp_min
            T_ret_max = return_temp_range[1] if return_temp_range else return_temp_max
            setattr(model, f'{prefix}_T_return',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(T_ret_min, T_ret_max)))
        T_return = getattr(model, f'{prefix}_T_return')

        # Pressure variables â€” always Var, values propagated by network_manager
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
        Q_demand_slack = None

        if node_type in ('consumer', 'mixed'):
            allow_heat_demand_slack = bool(config.get('allow_heat_demand_slack', False))
            max_heat_demand_slack_frac = float(config.get('max_heat_demand_slack_frac', 0.0) or 0.0)
            max_heat_demand_slack_frac = max(0.0, min(max_heat_demand_slack_frac, 1.0))
            max_heat_demand_slack_abs_mw = float(config.get('max_heat_demand_slack_abs_mw', 0.0) or 0.0)
            max_heat_demand_slack_abs_mw = max(0.0, max_heat_demand_slack_abs_mw)
            demand_slack_penalty = float(config.get('demand_slack_penalty_eur_per_mwh', 1e6) or 1e6)
            consumers_list = config.get('consumers') or []
            n_consumers = len(consumers_list)

            if n_consumers > 1:
                # Multi-consumer: create per-consumer Q_demand_{i} Params and m_dot_demand_{i} Vars
                for i in range(n_consumers):
                    _heatd_attr = f'heatd_{node_id}_{i}'
                    if hasattr(model, _heatd_attr):
                        _h = getattr(model, _heatd_attr)
                        def _demand_init(m, t, _hh=_h):
                            return pyo.value(_hh[t])
                        setattr(model, f'{prefix}_Q_demand_{i}',
                                pyo.Param(time_set, initialize=_demand_init))
                    else:
                        raise ValueError(
                            f"Consumer node {node_id}: no heatd_{node_id}_{i} param found on model"
                        )
                    setattr(model, f'{prefix}_m_dot_demand_{i}',
                            pyo.Var(time_set, domain=pyo.NonNegativeReals))

                # Aggregate Q_demand Param = sum of per-consumer demands.
                # network_manager constraint rules expect a subscriptable Q_demand[t].
                # Must be created before m_dot_demand so _mdot_ub can use Q_demand.
                def _q_agg_init(m, t, _pfx=prefix, _n=n_consumers):
                    return sum(pyo.value(getattr(m, f'{_pfx}_Q_demand_{ii}')[t])
                               for ii in range(_n))
                setattr(model, f'{prefix}_Q_demand',
                        pyo.Param(time_set, initialize=_q_agg_init))
                Q_demand = getattr(model, f'{prefix}_Q_demand')

                # Compute UB for aggregate m_dot_demand (same logic as single-consumer)
                _dT_min = max(supply_temp_min - return_temp_c, 5.0)
                _cp_mw = cp_water / 1000
                _q_peak = max(
                    (pyo.value(Q_demand[t]) for t in time_set),
                    default=10.0
                )
                _mdot_ub = _q_peak / (_cp_mw * _dT_min) * 1.5

                # Aggregate m_dot_demand = sum of per-consumer flows
                setattr(model, f'{prefix}_m_dot_demand',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, _mdot_ub)))
                m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')

                def _m_dot_sum_rule(m, t, _n=n_consumers, _pfx=prefix):
                    return getattr(m, f'{_pfx}_m_dot_demand')[t] == sum(
                        getattr(m, f'{_pfx}_m_dot_demand_{ii}')[t] for ii in range(_n)
                    )
                setattr(model, f'{prefix}_m_dot_demand_sum',
                        pyo.Constraint(time_set, rule=_m_dot_sum_rule))

            else:
                # Single-consumer: explicit demand_profile overrides heatd params when provided.
                _node_heatd_attr = f'heatd_{node_id}'
                _demand_fraction = float(config.get('demand_fraction', 1.0) or 1.0)
                _min_demand_mw = float(config.get('min_demand_mw', 0.0) or 0.0)
                _min_demand_only_when_positive = bool(
                    config.get('min_demand_only_when_positive', False)
                )

                def _apply_demand_floor(q_raw, _q_min=_min_demand_mw, _only_pos=_min_demand_only_when_positive):
                    q_val = max(0.0, float(q_raw))
                    if _q_min <= 0.0:
                        return q_val
                    if _only_pos and q_val <= 0.0:
                        return 0.0
                    return max(q_val, _q_min)

                if 'demand_profile' in config:
                    demand_profile = config['demand_profile']

                    def demand_init(m, t, _prof=demand_profile, _frac=_demand_fraction):
                        q_raw = _prof.get(t, _prof.get(str(t), 0.0))
                        return _apply_demand_floor(q_raw * _frac)

                    setattr(model, f'{prefix}_Q_demand',
                            pyo.Param(time_set, initialize=demand_init))
                elif hasattr(model, _node_heatd_attr):
                    # Prefer node-specific demand param (avoids triple-counting when multiple
                    # consumer nodes reference the same demand column -- m.heatd is their sum).
                    # 2026-07-27 demand_fraction^2 fix (faithful Paper-1 synth correction):
                    # system_builder.py already builds heatd_{node} as (demand_column * frac),
                    # so it IS the node's demand. Multiplying by _frac AGAIN here yielded
                    # (column * frac * frac) = column * frac^2 -- for the synth configs
                    # (single fractional consumer per node, frac ~0.19) this served only
                    # SUM(frac^2) ~ 0.20x of the true demand, under-generating by ~5x. The
                    # primary case was unaffected because its consumers have demand_fraction
                    # removed (frac = 1.0 -> 1^2 = 1). Use the node param directly.
                    _node_heatd = getattr(model, _node_heatd_attr)
                    def demand_init(m, t, _h=_node_heatd):
                        return _apply_demand_floor(pyo.value(_h[t]))
                    setattr(model, f'{prefix}_Q_demand',
                            pyo.Param(time_set, initialize=demand_init))
                elif hasattr(model, 'heatd'):
                    def demand_init(m, t, _frac=_demand_fraction):
                        return _apply_demand_floor(pyo.value(m.heatd[t]) * _frac)
                    setattr(model, f'{prefix}_Q_demand',
                            pyo.Param(time_set, initialize=demand_init))
                else:
                    raise ValueError(f"Consumer node {node_id}: no demand data available")

                Q_demand = getattr(model, f'{prefix}_Q_demand')

                # Compute upper bound on m_dot_demand for McCormick relaxation quality.
                # Without an explicit UB the bilinear product m_dot_demand Ã— T_supply has
                # only a one-sided McCormick envelope, making BQP cuts ineffective.
                # UB = peak_Q / (cp/1000 Ã— Î”T_min) where Î”T_min = T_supply_min - T_return.
                _dT_min = max(supply_temp_min - return_temp_c, 5.0)  # at least 5Â°C
                _cp_mw = cp_water / 1000
                _q_peak = max(
                    (pyo.value(Q_demand[t]) for t in time_set),
                    default=10.0
                )
                _mdot_ub = _q_peak / (_cp_mw * _dT_min) * 1.5  # 50% safety margin

                setattr(model, f'{prefix}_m_dot_demand',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, _mdot_ub)))
                m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')

            if (
                allow_heat_demand_slack
                and Q_demand is not None
                and (max_heat_demand_slack_frac > 0.0 or max_heat_demand_slack_abs_mw > 0.0)
            ):
                def _demand_slack_bounds(
                    m, t, _Q=Q_demand, _frac=max_heat_demand_slack_frac, _abs=max_heat_demand_slack_abs_mw
                ):
                    q_t = 0.0
                    try:
                        q_t = max(0.0, float(pyo.value(_Q[t])))
                    except Exception:
                        q_t = 0.0
                    return (0.0, max(_frac * q_t, _abs))

                setattr(
                    model,
                    f'{prefix}_Q_demand_slack',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=_demand_slack_bounds),
                )
                Q_demand_slack = getattr(model, f'{prefix}_Q_demand_slack')
                if not hasattr(model, 'demand_slack_penalty_terms'):
                    model.demand_slack_penalty_terms = []
                model.demand_slack_penalty_terms.append((Q_demand_slack, demand_slack_penalty))
                logger.info(
                    f"    Node {node_id}: demand slack enabled "
                    f"(max {max_heat_demand_slack_frac:.1%} or {max_heat_demand_slack_abs_mw:.4f} MW, "
                    f"penalty={demand_slack_penalty:.0e} â‚¬/MWh)"
                )

            # Valve differential pressure â€” absorbs excess pump head at consumer stations.
            delta_p_min_station = config.get('delta_p_min_consumer_bar', 0.7)
            setattr(model, f'{prefix}_delta_p_valve',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, 20.0)))
            delta_p_valve_var = getattr(model, f'{prefix}_delta_p_valve')

            # Minimum differential pressure at consumer station (Ãœbergabestation):
            # P_supply - P_return >= delta_p_min_station (e.g. 0.7 bar = 70 kPa)
            if config.get('pressure_drop_enabled', False):
                def _station_dp_rule(m, t, _ps=pressure_supply, _pr=pressure_return, _dp=delta_p_min_station):
                    return _ps[t] - _pr[t] >= _dp
                setattr(model, f'{prefix}_station_dp',
                        pyo.Constraint(time_set, rule=_station_dp_rule))

        # ============================================================
        # CONSTRAINTS
        # ============================================================

        # (1) Enthalpy balance (temperature mixing) for nodes with incoming pipes.
        #
        # Linearised mixing law (valid for constant cp):
        #   T_supply[t] Ã— Î£_in m_dot_in[t] = Î£_in (m_dot_in[t] Ã— T_supply_out_pipe[t])
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
                    f"({len(incoming_pipes)} pipes, bilinear â€” needs QP solver)"
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
                    f"    Node {node_id}: multi-pipe MILP mode â€” T_supply fixed to {supply_temp_nominal_c}Â°C"
                )
            else:
                logger.info(
                    f"    Node {node_id}: multi-pipe MILP mode â€” T_supply already a Param"
                )

        # (2) Mass balance: Î£ m_dot_in[t] = Î£ m_dot_out[t] + m_dot_demand[t]
        #
        # For producer nodes: incoming=[], outgoing=[...], m_dot_demand=0
        #   â†’ trivial 0 == Î£ m_dot_out (not a useful constraint; skip for producers)
        # For junction nodes: m_dot_demand=0
        #   â†’ Î£ m_dot_in == Î£ m_dot_out
        # For consumer nodes: m_dot_demand >= 0
        #   â†’ Î£ m_dot_in == Î£ m_dot_out + m_dot_demand
        #
        # Keep Kirchhoff active whenever this node participates in supply flow
        # balance. Demand-delay decoupling is handled by dedicated demand-link
        # constraints in network_manager, not by disabling mass balance here.
        if incoming_pipes or (node_type not in ('producer', 'mixed') and outgoing_pipes):
            def mass_balance_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes):
                total_in = sum(
                    getattr(m, f'{p.upper().replace("-", "_")}_m_dot')[t]
                    for p in _in
                )
                total_out = sum(
                    getattr(m, f'{p.upper().replace("-", "_")}_m_dot')[t]
                    for p in _out
                )
                if node_type in ('consumer', 'mixed'):
                    demand_var = getattr(m, f'{prefix}_m_dot_demand')
                    return total_in == total_out + demand_var[t]
                return total_in == total_out

            setattr(model, f'{prefix}_mass_balance',
                    pyo.Constraint(time_set, rule=mass_balance_rule))

        # (3) Heat demand satisfaction (consumer nodes only)
        # Q_demand [MW] = m_dot [kg/s] Ã— c_p [kJ/(kgÂ·K)] Ã— (T_supply - T_return) [K] / 1000
        milp_linearize = config.get('milp_linearize', False)

        if node_type in ('consumer', 'mixed'):
            is_terminal_consumer = (len(outgoing_pipes) == 0)
            apply_tuning_on_passthrough = bool(
                config.get('return_temp_apply_on_passthrough', False)
            )
            apply_frame_on_passthrough = bool(
                config.get('return_temp_frame_on_passthrough', False)
            )
            if milp_linearize and not outgoing_pipes:
                # Terminal consumer in MILP mode: demand is enforced through
                # Q_consumer == Q_demand in the network manager.  The heat_demand
                # constraint (m_dot_demand â†” Q_demand) is skipped because transport
                # delay decouples instantaneous flow from instantaneous demand.
                logger.info(
                    f"    Node {node_id}: MILP terminal consumer â€” "
                    f"heat_demand constraint skipped (enforced via Q_consumer)"
                )
            elif milp_linearize:
                # MILP passthrough consumer: still needs m_dot_demand for mass balance
                dT_nominal = supply_temp_nominal_c - return_temp_c
                if dT_nominal <= 0:
                    dT_nominal = 35.0  # safe fallback

                def heat_demand_rule_milp(m, t):
                    q_req = Q_demand[t]
                    if Q_demand_slack is not None:
                        q_req = q_req - Q_demand_slack[t]
                    return m_dot_demand[t] == q_req * 1000 / (cp_water * dT_nominal)

                setattr(model, f'{prefix}_heat_demand',
                        pyo.Constraint(time_set, rule=heat_demand_rule_milp))
            else:
                # Full nonlinear mode (bilinear â€” requires QP/NLP solver)
                # Use cp/1000 to keep coefficients O(1) in MW units â€” avoids
                # a Ã—1000 factor in Gurobi's QLMatrix that causes BQP/RLT cuts
                # to be numerically unreliable (false infeasibility).
                cp_mw = cp_water / 1000  # MWÂ·s/(kgÂ·K)

                def heat_demand_rule(m, t):
                    if Q_demand_slack is not None:
                        return Q_demand[t] - Q_demand_slack[t] == (
                            m_dot_demand[t] * cp_mw * (T_supply[t] - T_return[t])
                        )
                    return Q_demand[t] == m_dot_demand[t] * cp_mw * (T_supply[t] - T_return[t])

                setattr(model, f'{prefix}_heat_demand',
                        pyo.Constraint(time_set, rule=heat_demand_rule))

            # (3b) Optional load-dependent return temperature
            def _register_return_anchor_penalty(slack_var, weight_eur_per_c):
                if weight_eur_per_c <= 0.0:
                    return
                if not hasattr(model, 'return_temp_anchor_penalty_terms'):
                    model.return_temp_anchor_penalty_terms = []
                model.return_temp_anchor_penalty_terms.append((slack_var, float(weight_eur_per_c)))

            if stateful_return_v2 and isinstance(T_return, pyo.Var):
                rv2_params = config.get('return_v2_params', {})
                if not isinstance(rv2_params, dict):
                    rv2_params = {}
                a0 = float(rv2_params.get('a0', return_temp_c))
                a_q = float(rv2_params.get('a_q', 0.5))
                a_out = float(rv2_params.get('a_out', 0.0))
                a_sup = float(rv2_params.get('a_sup', 0.05))
                alpha = float(rv2_params.get('alpha', 0.35))
                q_ref = float(rv2_params.get('q_ref', 0.0))
                t_outdoor_ref = float(rv2_params.get('t_outdoor_ref', 10.0))
                t_supply_ref = float(rv2_params.get('t_supply_ref', supply_temp_nominal_c))
                state_init_c = float(config.get('return_state_init_c', 56.9) or 56.9)
                allow_negative_a_q = bool(config.get('return_v2_allow_negative_a_q', False))
                if allow_negative_a_q:
                    a_q = float(max(-8.0, min(8.0, a_q)))
                else:
                    a_q = float(max(0.2, min(8.0, a_q)))
                a_out = float(max(-0.4, min(0.4, a_out)))
                a_sup = float(max(0.0, min(0.5, a_sup)))
                alpha = float(max(0.15, min(0.85, alpha)))
                state_init_c = float(max(30.0, min(80.0, state_init_c)))

                outdoor_profile = config.get('return_v2_outdoor_profile', {})
                if not isinstance(outdoor_profile, dict):
                    outdoor_profile = {}

                setattr(
                    model,
                    f'{prefix}_T_return_state',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(30.0, 80.0)),
                )
                setattr(
                    model,
                    f'{prefix}_return_state_slack_pos',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals),
                )
                setattr(
                    model,
                    f'{prefix}_return_state_slack_neg',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals),
                )
                setattr(
                    model,
                    f'{prefix}_return_link_slack_pos',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals),
                )
                setattr(
                    model,
                    f'{prefix}_return_link_slack_neg',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals),
                )
                T_return_state = getattr(model, f'{prefix}_T_return_state')
                s_dyn_pos = getattr(model, f'{prefix}_return_state_slack_pos')
                s_dyn_neg = getattr(model, f'{prefix}_return_state_slack_neg')
                s_link_pos = getattr(model, f'{prefix}_return_link_slack_pos')
                s_link_neg = getattr(model, f'{prefix}_return_link_slack_neg')

                def _target_temp_expr(t):
                    t_outdoor = float(
                        outdoor_profile.get(
                            t,
                            outdoor_profile.get(str(t), t_outdoor_ref),
                        )
                    )
                    return (
                        a0
                        + a_q * (Q_demand[t] - q_ref)
                        + a_out * (t_outdoor_ref - t_outdoor)
                        + a_sup * (T_supply[t] - t_supply_ref)
                    )

                t_list = list(time_set)
                if t_list:
                    t0 = t_list[0]

                    setattr(
                        model,
                        f'{prefix}_return_state_init',
                        pyo.Constraint(
                            expr=T_return_state[t0] == state_init_c + s_dyn_pos[t0] - s_dyn_neg[t0]
                        ),
                    )

                    if len(t_list) > 1:
                        setattr(model, f'{prefix}_return_state_idx', pyo.RangeSet(1, len(t_list) - 1))
                        state_idx = getattr(model, f'{prefix}_return_state_idx')

                        def _state_dyn_rule(m, k):
                            t_prev = t_list[k - 1]
                            t_now = t_list[k]
                            return (
                                T_return_state[t_now]
                                == (1.0 - alpha) * T_return_state[t_prev]
                                + alpha * _target_temp_expr(t_now)
                                + s_dyn_pos[t_now]
                                - s_dyn_neg[t_now]
                            )

                        setattr(
                            model,
                            f'{prefix}_return_state_dyn',
                            pyo.Constraint(state_idx, rule=_state_dyn_rule),
                        )

                    setattr(
                        model,
                        f'{prefix}_return_state_link',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t: T_return[t] == T_return_state[t] + s_link_pos[t] - s_link_neg[t],
                        ),
                    )

                _register_return_anchor_penalty(s_dyn_pos, return_state_penalty)
                _register_return_anchor_penalty(s_dyn_neg, return_state_penalty)
                _register_return_anchor_penalty(s_link_pos, return_link_penalty)
                _register_return_anchor_penalty(s_link_neg, return_link_penalty)

                flow_anchor_profile = config.get('flow_anchor_profile_kg_s', {})
                if (
                    isinstance(flow_anchor_profile, dict)
                    and flow_anchor_profile
                    and isinstance(m_dot_demand, pyo.Var)
                    and flow_anchor_penalty > 0.0
                ):
                    setattr(
                        model,
                        f'{prefix}_flow_anchor_slack_pos',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals),
                    )
                    setattr(
                        model,
                        f'{prefix}_flow_anchor_slack_neg',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals),
                    )
                    flow_slack_pos = getattr(model, f'{prefix}_flow_anchor_slack_pos')
                    flow_slack_neg = getattr(model, f'{prefix}_flow_anchor_slack_neg')

                    def _flow_ref(t):
                        raw = flow_anchor_profile.get(t, flow_anchor_profile.get(str(t), None))
                        if raw is None:
                            return None
                        try:
                            return max(0.0, float(raw))
                        except Exception:
                            return None

                    def _flow_anchor_lb_rule(m, t):
                        ref = _flow_ref(t)
                        if ref is None:
                            return pyo.Constraint.Skip
                        return m_dot_demand[t] >= ref - flow_slack_neg[t]

                    def _flow_anchor_ub_rule(m, t):
                        ref = _flow_ref(t)
                        if ref is None:
                            return pyo.Constraint.Skip
                        return m_dot_demand[t] <= ref + flow_slack_pos[t]

                    setattr(
                        model,
                        f'{prefix}_flow_anchor_lb',
                        pyo.Constraint(time_set, rule=_flow_anchor_lb_rule),
                    )
                    setattr(
                        model,
                        f'{prefix}_flow_anchor_ub',
                        pyo.Constraint(time_set, rule=_flow_anchor_ub_rule),
                    )
                    _register_return_anchor_penalty(flow_slack_pos, flow_anchor_penalty)
                    _register_return_anchor_penalty(flow_slack_neg, flow_anchor_penalty)

                # Prevent legacy return-load constraints from being generated in v2 mode.
                return_temp_load_factor = 0.0
                return_temp_ref_profile = None
                return_temp_band_profile = None
                return_temp_max_step_c = 0.0

            load_dep_active = False
            load_dep_half_swing_c = 0.0
            return_temp_load_mode = str(
                config.get('return_temp_load_mode', 'equal')
            ).strip().lower()
            if return_temp_load_mode not in ('equal', 'upper', 'band'):
                return_temp_load_mode = 'equal'
            load_relax_c = float(config.get('return_temp_load_relax_c', 0.0) or 0.0)
            load_relax_c = max(0.0, load_relax_c)
            if (
                isinstance(T_return, pyo.Var)
                and (is_terminal_consumer or apply_tuning_on_passthrough)
                and return_temp_range is not None
                and return_temp_load_factor > 0
            ):
                T_ret_min_v, T_ret_max_v = return_temp_range
                T_ret_base = (T_ret_min_v + T_ret_max_v) / 2
                delta_T_range = T_ret_max_v - T_ret_min_v

                peak_demand_mw = config.get('peak_demand_mw', None)
                if peak_demand_mw is None and hasattr(model, 'heatd'):
                    demand_frac = config.get('demand_fraction', 0.0)
                    peak_demand_mw = max(pyo.value(model.heatd[t]) for t in time_set) * demand_frac

                if peak_demand_mw and peak_demand_mw > 0:
                    # Guard very small node peaks to avoid extreme return-temperature
                    # slopes (k) on low-demand nodes during calibration windows.
                    peak_floor_mw = float(config.get('return_temp_peak_floor_mw', 0.75) or 0.75)
                    peak_floor_mw = max(0.05, peak_floor_mw)
                    peak_eff_mw = max(float(peak_demand_mw), peak_floor_mw)
                    k_ret_temp = return_temp_load_factor * delta_T_range / peak_eff_mw
                    load_dep_half_swing_c = abs(k_ret_temp) * 0.5 * peak_demand_mw
                    load_dep_active = True

                    has_ref_profile = (
                        isinstance(return_temp_ref_profile, dict)
                        and bool(return_temp_ref_profile)
                    )

                    def _target_temp(t):
                        if has_ref_profile:
                            _t_ref = float(
                                return_temp_ref_profile.get(
                                    t,
                                    return_temp_ref_profile.get(str(t), T_ret_base),
                                )
                            )
                        else:
                            _t_ref = T_ret_base
                        _t_ref = _t_ref + return_temp_ref_shift_c
                        return _t_ref + k_ret_temp * (
                            Q_demand[t] - 0.5 * peak_demand_mw
                        )

                    if return_temp_soft_anchor_enabled:
                        if return_temp_load_mode == 'upper':
                            setattr(
                                model,
                                f'{prefix}_return_temp_load_slack_ub',
                                pyo.Var(time_set, domain=pyo.NonNegativeReals),
                            )
                            load_slack_ub = getattr(model, f'{prefix}_return_temp_load_slack_ub')

                            def return_temp_load_ub_rule(m, t, _sl=load_slack_ub):
                                return T_return[t] <= _target_temp(t) + _sl[t]

                            setattr(
                                model,
                                f'{prefix}_return_temp_load_ub',
                                pyo.Constraint(time_set, rule=return_temp_load_ub_rule),
                            )
                            _register_return_anchor_penalty(
                                load_slack_ub, return_temp_soft_anchor_weight_load
                            )
                        else:
                            relax_band = load_relax_c if return_temp_load_mode == 'band' else 0.0
                            setattr(
                                model,
                                f'{prefix}_return_temp_load_slack_lb',
                                pyo.Var(time_set, domain=pyo.NonNegativeReals),
                            )
                            setattr(
                                model,
                                f'{prefix}_return_temp_load_slack_ub',
                                pyo.Var(time_set, domain=pyo.NonNegativeReals),
                            )
                            load_slack_lb = getattr(model, f'{prefix}_return_temp_load_slack_lb')
                            load_slack_ub = getattr(model, f'{prefix}_return_temp_load_slack_ub')

                            def return_temp_load_lb_rule(m, t, _sl=load_slack_lb, _rel=relax_band):
                                return T_return[t] >= _target_temp(t) - _rel - _sl[t]

                            def return_temp_load_ub_rule(m, t, _sl=load_slack_ub, _rel=relax_band):
                                return T_return[t] <= _target_temp(t) + _rel + _sl[t]

                            setattr(
                                model,
                                f'{prefix}_return_temp_load_lb',
                                pyo.Constraint(time_set, rule=return_temp_load_lb_rule),
                            )
                            setattr(
                                model,
                                f'{prefix}_return_temp_load_ub',
                                pyo.Constraint(time_set, rule=return_temp_load_ub_rule),
                            )
                            _register_return_anchor_penalty(
                                load_slack_lb, return_temp_soft_anchor_weight_load
                            )
                            _register_return_anchor_penalty(
                                load_slack_ub, return_temp_soft_anchor_weight_load
                            )
                    else:
                        if return_temp_load_mode == 'equal':
                            def return_temp_load_rule(m, t):
                                return T_return[t] == _target_temp(t)
                            setattr(model, f'{prefix}_return_temp_load',
                                    pyo.Constraint(time_set, rule=return_temp_load_rule))
                        elif return_temp_load_mode == 'upper':
                            def return_temp_load_ub_rule(m, t):
                                return T_return[t] <= _target_temp(t)
                            setattr(model, f'{prefix}_return_temp_load_ub',
                                    pyo.Constraint(time_set, rule=return_temp_load_ub_rule))
                        else:  # band
                            def return_temp_load_lb_rule(m, t, _rel=load_relax_c):
                                return T_return[t] >= _target_temp(t) - _rel
                            def return_temp_load_ub_rule(m, t, _rel=load_relax_c):
                                return T_return[t] <= _target_temp(t) + _rel
                            setattr(model, f'{prefix}_return_temp_load_lb',
                                    pyo.Constraint(time_set, rule=return_temp_load_lb_rule))
                            setattr(model, f'{prefix}_return_temp_load_ub',
                                    pyo.Constraint(time_set, rule=return_temp_load_ub_rule))

                    logger.info(
                        f"    Node {node_id}: load-dependent T_return constraint "
                        f"(mode={return_temp_load_mode}, k={k_ret_temp:.4f} Â°C/MW, "
                        f"Q_max={peak_demand_mw:.2f} MW)"
                    )

            # (3c) Optional dynamic return-temperature frame around a reference profile.
            # Keeps T_return variable but within a physically plausible corridor.
            if (
                isinstance(T_return, pyo.Var)
                and (is_terminal_consumer or apply_frame_on_passthrough)
                and isinstance(return_temp_ref_profile, dict)
                and return_temp_ref_profile
            ):
                # If load-dependent return temperature is active, ensure the frame
                # can contain the induced swing around the reference trajectory.
                auto_band_floor_c = (
                    load_dep_half_swing_c + 0.25 if load_dep_active else 0.0
                )

                def _ref_temp(t):
                    return float(
                        return_temp_ref_profile.get(
                            t,
                            return_temp_ref_profile.get(str(t), return_temp_c),
                        )
                    )

                def _band_temp(t):
                    if isinstance(return_temp_band_profile, dict) and return_temp_band_profile:
                        if t in return_temp_band_profile:
                            return max(
                                auto_band_floor_c,
                                max(0.0, float(return_temp_band_profile[t])),
                            )
                        if str(t) in return_temp_band_profile:
                            return max(
                                auto_band_floor_c,
                                max(0.0, float(return_temp_band_profile[str(t)])),
                            )
                    return max(auto_band_floor_c, max(0.0, return_temp_band_c))

                def _ret_frame_lb_rule(m, t):
                    return T_return[t] >= _ref_temp(t) - _band_temp(t)

                def _ret_frame_ub_rule(m, t):
                    return T_return[t] <= _ref_temp(t) + _band_temp(t)

                if return_temp_soft_anchor_enabled:
                    setattr(
                        model,
                        f'{prefix}_return_frame_slack_lb',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals),
                    )
                    setattr(
                        model,
                        f'{prefix}_return_frame_slack_ub',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals),
                    )
                    frame_slack_lb = getattr(model, f'{prefix}_return_frame_slack_lb')
                    frame_slack_ub = getattr(model, f'{prefix}_return_frame_slack_ub')

                    def _ret_frame_lb_soft_rule(m, t, _sl=frame_slack_lb):
                        return T_return[t] >= _ref_temp(t) - _band_temp(t) - _sl[t]

                    def _ret_frame_ub_soft_rule(m, t, _sl=frame_slack_ub):
                        return T_return[t] <= _ref_temp(t) + _band_temp(t) + _sl[t]

                    setattr(
                        model,
                        f'{prefix}_return_frame_lb',
                        pyo.Constraint(time_set, rule=_ret_frame_lb_soft_rule),
                    )
                    setattr(
                        model,
                        f'{prefix}_return_frame_ub',
                        pyo.Constraint(time_set, rule=_ret_frame_ub_soft_rule),
                    )
                    _register_return_anchor_penalty(
                        frame_slack_lb, return_temp_soft_anchor_weight_frame
                    )
                    _register_return_anchor_penalty(
                        frame_slack_ub, return_temp_soft_anchor_weight_frame
                    )
                else:
                    setattr(model, f'{prefix}_return_frame_lb',
                            pyo.Constraint(time_set, rule=_ret_frame_lb_rule))
                    setattr(model, f'{prefix}_return_frame_ub',
                            pyo.Constraint(time_set, rule=_ret_frame_ub_rule))
                if auto_band_floor_c > 0.0:
                    logger.info(
                        f"    Node {node_id}: dynamic T_return frame activated "
                        f"(auto band floor {auto_band_floor_c:.2f}Â°C)"
                    )
                else:
                    logger.info(f"    Node {node_id}: dynamic T_return frame activated")

            # (3d) Optional anti-oscillation guard for low-demand nodes:
            # bound timestep-to-timestep return-temperature jumps.
            if isinstance(T_return, pyo.Var) and return_temp_max_step_c > 0:
                t_list = list(time_set)
                if len(t_list) > 1:
                    step_set_name = f'{prefix}_ret_step_idx'
                    setattr(model, step_set_name, pyo.RangeSet(1, len(t_list) - 1))
                    step_idx_set = getattr(model, step_set_name)

                    def _ret_step_up_rule(m, k):
                        t_prev = t_list[k - 1]
                        t_now = t_list[k]
                        return T_return[t_now] - T_return[t_prev] <= return_temp_max_step_c

                    def _ret_step_dn_rule(m, k):
                        t_prev = t_list[k - 1]
                        t_now = t_list[k]
                        return T_return[t_prev] - T_return[t_now] <= return_temp_max_step_c

                    setattr(
                        model,
                        f'{prefix}_return_step_up',
                        pyo.Constraint(step_idx_set, rule=_ret_step_up_rule),
                    )
                    setattr(
                        model,
                        f'{prefix}_return_step_dn',
                        pyo.Constraint(step_idx_set, rule=_ret_step_dn_rule),
                    )
                    logger.info(
                        f"    Node {node_id}: T_return anti-oscillation guard "
                        f"(max step {return_temp_max_step_c:.2f}Ã‚Â°C per timestep)"
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
            'return_model_mode': return_model_mode,
            'T_supply': T_supply,
            'T_return': T_return,
            'pressure_supply': pressure_supply,
            'pressure_return': pressure_return,
            'incoming_pipes': incoming_pipes,
            'outgoing_pipes': outgoing_pipes,
            # Direction semantics:
            # - supply incoming at node: pipes with to_node == node
            # - return incoming at node: pipes with from_node == node
            'supply_incoming_pipes': list(incoming_pipes),
            'supply_outgoing_pipes': list(outgoing_pipes),
            'return_incoming_pipes': list(outgoing_pipes),
            'return_outgoing_pipes': list(incoming_pipes),
            'return_temperature_role': 'temperature_at_node_of_incoming_return_streams',
            'pressure_coupling_owner': 'network_manager',
            'interface': {
                'temperature_coupling_owner': 'network_manager',
                'pressure_coupling_owner': 'network_manager',
                'supply_incoming_pipes': list(incoming_pipes),
                'supply_outgoing_pipes': list(outgoing_pipes),
                'return_incoming_pipes': list(outgoing_pipes),
                'return_outgoing_pipes': list(incoming_pipes),
            },
        }

        if hasattr(model, f'{prefix}_T_return_state'):
            result['T_return_state'] = getattr(model, f'{prefix}_T_return_state')

        if node_type in ('consumer', 'mixed'):
            result['Q_demand'] = Q_demand  # Param for single- and multi-consumer nodes
            result['m_dot_demand'] = m_dot_demand
            result['Q_demand_slack'] = Q_demand_slack
            result['demand_fraction'] = config.get('demand_fraction', 0.0)

        if node_type in ('producer', 'mixed'):
            result['components'] = config.get('components', {})
            if not incoming_pipes:
                result['requires_supply_temp_from'] = 'profile_or_generator'

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
        T_return_state = getattr(model, f'{prefix}_T_return_state', None)

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

        if isinstance(T_return_state, pyo.Var):
            result['T_return_state_c'] = [safe_value(T_return_state, t, 50.0) for t in time_set]

        if node_type in ('consumer', 'mixed'):
            Q_demand = getattr(model, f'{prefix}_Q_demand')
            m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')

            q_demand_series = [pyo.value(Q_demand[t]) for t in time_set]
            m_dot_series = [safe_value(m_dot_demand, t, 0.0) for t in time_set]

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

