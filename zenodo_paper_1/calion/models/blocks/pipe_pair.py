"""
Pipe Pair Component for District Heating Networks

Models supply and return pipes with:
- Temperature-dependent heat losses (Darcy-Weisbach)
- Piecewise-linear pressure drop (MILP-compatible, 3-segment PWL)
- Transport time delay (linearised with 3-bucket SOS2 binary selection)
- Investment optimization (optional diameter/insulation upgrade)

Unified physics â€” no brownfield/greenfield distinction.

Author: CALION Development Team
"""

import logging
import math
from typing import Any

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

from ..component import BaseComponent
from ..network_physics import compute_delay_buckets
from ..registry import register_component
from ..state_constraints import (
    enforce_minimum_pressure,
    enforce_velocity_bounds,
)

logger = logging.getLogger(__name__)

pi = math.pi


@register_component("pipe_pair")
class PipePairBlock(BaseComponent):
    """
    Pair of pipes (supply + return) for district heating network.

    Models:
    - Heat losses dependent on pipe temperature and ground temperature
    - Temperature propagation along pipes
    - Mass flow balance
    - Piecewise-linear (PWL) pressure drop (3-segment, MILP-compatible)
    - 3-bucket SOS2 transport delay (see comment block below for details)
    - Optional diameter selection and insulation upgrade

    Variables (per timestep t):
        - m_dot[t]: Mass flow through pipes (kg/s)
        - T_supply_in[t], T_supply_out[t]: Supply temperatures (Â°C)
        - T_return_in[t], T_return_out[t]: Return temperatures (Â°C)
        - Q_loss_supply[t], Q_loss_return[t]: Heat losses (MW)
        - Q_delivered[t]: Heat entering supply pipe at source side (MW)
        - Q_consumer[t]: Heat delivered to consumer (delayed) (MW)
        - z_delay[n, t]: Binary bucket selector for transport delay
        - w_delay[n, t]: Linearisation auxiliary for z_delay Ã— Q_delivered
        - diameter_choice[d]: Binary for diameter selection (if investable)
        - insulation_choice[i]: Binary for insulation type (if upgradeable)
    """

    @staticmethod
    def validate_config(config: dict[str, Any]) -> None:
        """Validate pipe pair configuration."""
        required = ['id', 'from_node', 'to_node', 'length_m']
        for field in required:
            if field not in config:
                raise ValueError(f"PipePair config missing required field: {field}")

        if config['length_m'] <= 0:
            raise ValueError(f"Pipe {config['id']}: length must be positive")

        if 'current_diameter_supply_mm' not in config and 'diameter_options' not in config:
            raise ValueError(
                f"Pipe {config['id']}: must specify either current_diameter or diameter_options"
            )

    @staticmethod
    def attach(model, time_set, config: dict[str, Any], buses: dict) -> dict[str, Any]:
        """
        Attach pipe pair component to Pyomo model.

        Args:
            model: Pyomo ConcreteModel
            time_set: Set of timesteps
            config: Pipe configuration dict
            buses: Dict of bus components

        Returns:
            Dict with variable references and metadata
        """
        pipe_id = config['id']
        prefix = pipe_id.upper().replace('-', '_')

        logger.info(f"Attaching pipe pair: {pipe_id}")

        # ============================================================
        # PARAMETERS
        # ============================================================

        length_m = config['length_m']
        from_node = config['from_node']
        to_node = config['to_node']

        # Fluid properties (water)
        cp_water = 4.186       # kJ/(kgÂ·K)
        density_water = 1000   # kg/mÂ³

        # Temperature parameters
        supply_temp_nominal_c = config.get('supply_temp_nominal_c', 90.0)
        return_temp_nominal_c = config.get('return_temp_nominal_c', 50.0)

        # Ground/ambient temperature
        # Priority: per-timestep dict > outdoor_temp param > fixed constant.
        # ground_temp_dict uses the same 1-based time keys as the Pyomo time set.
        use_outdoor_temp = config.get('use_outdoor_temperature', False)
        ground_temp_dict = config.get('ground_temp_dict')
        if isinstance(ground_temp_dict, dict) and ground_temp_dict:
            _fallback_g = config.get('ground_temp_c', 10.0)
            T_ground = {
                t: float(ground_temp_dict.get(t, ground_temp_dict.get(str(t), _fallback_g)))
                for t in time_set
            }
        elif use_outdoor_temp and hasattr(model, 'outdoor_temp'):
            T_ground = model.outdoor_temp
        else:
            fixed_ground_temp = config.get('ground_temp_c', 10.0)
            T_ground = {t: fixed_ground_temp for t in time_set}

        # Insulation properties
        u_value_supply = config.get('u_value_supply_w_per_m_k', 0.28)
        u_value_return = config.get('u_value_return_w_per_m_k', 0.30)

        # Diameter configuration
        existing_pipe = config.get('existing', False)
        current_diam_supply = config.get('current_diameter_supply_mm')
        current_diam_return = config.get('current_diameter_return_mm', current_diam_supply)

        # Investment/upgrade options
        upgrade_config = config.get('upgrade_options', {})
        upgrade_enabled = upgrade_config.get('enabled', False)
        diameter_options = upgrade_config.get(
            'diameter_options', [current_diam_supply] if current_diam_supply else [200]
        )
        insulation_options = upgrade_config.get('insulation_options', ['standard'])

        # Pipe catalog for costs
        pipe_catalog = config.get('pipe_catalog', {})

        # ============================================================
        # SETS (investment only)
        # ============================================================

        if upgrade_enabled:
            setattr(model, f'{prefix}_diameter_options',
                    pyo.Set(initialize=diameter_options))
            setattr(model, f'{prefix}_insulation_options',
                    pyo.Set(initialize=insulation_options))

        # ============================================================
        # PIPE GEOMETRY
        # ============================================================

        pressure_drop_enabled = config.get('pressure_drop_enabled', True)
        physics_cfg = config.get('physics', {}) if isinstance(config.get('physics', {}), dict) else {}
        bidirectional = bool(physics_cfg.get('bidirectional', config.get('bidirectional', False)))
        max_velocity = config.get('max_velocity_m_s', 2.5)
        max_pressure_drop = config.get('max_pressure_drop_bar', 2.0)
        pipe_roughness = config.get('pipe_roughness_mm', 0.05)
        pipe_max_flow = config.get('max_flow_kg_s', None)

        if current_diam_supply:
            d_inner_m = current_diam_supply / 1000.0 * 0.94
            d_inner_mm = current_diam_supply * 0.94
            area_m2 = pi * (d_inner_m / 2.0) ** 2
            v_max_calc = area_m2 * max_velocity * density_water
            effective_max_flow = min(pipe_max_flow, v_max_calc) if pipe_max_flow else v_max_calc
        else:
            d_inner_m = 0.2
            d_inner_mm = 200.0
            area_m2 = pi * (d_inner_m / 2.0) ** 2
            effective_max_flow = pipe_max_flow if pipe_max_flow else 500.0

        # ============================================================
        # TEMPERATURE / HEAT BOUNDS
        # ============================================================

        supply_temp_min = min(60, supply_temp_nominal_c - 30)
        supply_temp_max = max(130, supply_temp_nominal_c + 10)
        return_temp_min = 30
        return_temp_max = max(90, return_temp_nominal_c + 20)

        delta_t_nom = supply_temp_nominal_c - return_temp_nominal_c
        max_heat_delivered_mw = max(effective_max_flow * cp_water * delta_t_nom / 1000 * 1.2, 100.0)

        # ============================================================
        # FLOW VARIABLE
        # ============================================================

        if bidirectional:
            m_dot = pyo.Var(
                time_set,
                domain=pyo.Reals,
                bounds=(-effective_max_flow, effective_max_flow),
            )
            setattr(model, f'{prefix}_m_dot', m_dot)
            m_dot_abs = pyo.Var(
                time_set,
                domain=pyo.NonNegativeReals,
                bounds=(0, effective_max_flow),
            )
            flow_dir = pyo.Var(time_set, domain=pyo.Binary)
            setattr(model, f'{prefix}_m_dot_abs', m_dot_abs)
            setattr(model, f'{prefix}_flow_dir', flow_dir)

            # Exact |m_dot| linearisation with a direction selector.
            m_big = max(float(effective_max_flow), 1e-3)
            setattr(
                model,
                f'{prefix}_m_abs_ge_pos',
                pyo.Constraint(time_set, rule=lambda m, t: m_dot_abs[t] >= m_dot[t]),
            )
            setattr(
                model,
                f'{prefix}_m_abs_ge_neg',
                pyo.Constraint(time_set, rule=lambda m, t: m_dot_abs[t] >= -m_dot[t]),
            )
            setattr(
                model,
                f'{prefix}_m_abs_le_pos',
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _M=m_big: m_dot_abs[t] <= m_dot[t] + _M * (1 - flow_dir[t]),
                ),
            )
            setattr(
                model,
                f'{prefix}_m_abs_le_neg',
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _M=m_big: m_dot_abs[t] <= -m_dot[t] + _M * flow_dir[t],
                ),
            )
            setattr(
                model,
                f'{prefix}_m_dir_pos',
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _M=m_big: m_dot[t] <= _M * flow_dir[t],
                ),
            )
            setattr(
                model,
                f'{prefix}_m_dir_neg',
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _M=m_big: m_dot[t] >= -_M * (1 - flow_dir[t]),
                ),
            )
            flow_for_hydraulics = m_dot_abs
        else:
            m_dot = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, effective_max_flow))
            m_dot_abs = None
            flow_dir = None
            flow_for_hydraulics = m_dot
        if not hasattr(model, f'{prefix}_m_dot'):
            setattr(model, f'{prefix}_m_dot', m_dot)

        logger.info(
            f"Pipe {pipe_id}: max flow = {effective_max_flow:.2f} kg/s "
            f"(v_max={max_velocity} m/s, D={current_diam_supply or 'unspec'} mm, "
            f"bidirectional={bidirectional})"
        )

        # ============================================================
        # TEMPERATURE VARIABLES (or PARAMS in MILP-linearized mode)
        # ============================================================

        # Variables that are fully assigned in NLP mode (else branch below) but are
        # also referenced outside that branch (pressure-drop, transport-delay, return
        # dict at the end of attach_pipe_pair).  Initialise safe defaults here so
        # that MILP mode never hits an UnboundLocalError.
        warmup_slack = None
        warmup_flow_slack = None
        active_flag = None
        flow_activity_threshold = 0.0
        flow_guard_kg_s = 0.0
        stagnation_mode = 'guard'
        _warmup_times: list = []
        _warmup_lookup: set = set()

        def _warmup_flow_slack_term(t):  # noqa: E306  — referenced in pressure-drop section
            if warmup_flow_slack is None:
                return 0.0
            if t in _warmup_lookup:
                return warmup_flow_slack[t]
            return 0.0

        milp_linearize = config.get('milp_linearize', False)
        temperature_linearize = config.get('temperature_linearize')
        if temperature_linearize is None:
            temperature_linearize = milp_linearize

        if temperature_linearize:
            # Fix temperatures as Params â†’ all TÃ—m_dot products become linear.
            # When a per-timestep heating curve is available (supply_temp_dict),
            # initialize T_supply with those values so the simulated supply
            # temperature tracks the Heizkurve and matches measured data.
            supply_temp_dict = config.get('supply_temp_dict')
            return_temp_dict = config.get('return_temp_dict')
            if supply_temp_dict and isinstance(supply_temp_dict, dict):
                _supply_init = supply_temp_dict
            else:
                _supply_init = supply_temp_nominal_c
            if return_temp_dict and isinstance(return_temp_dict, dict):
                _return_init = return_temp_dict
            else:
                _return_init = return_temp_nominal_c
            T_supply_in = pyo.Param(time_set, initialize=_supply_init, mutable=True)
            T_supply_out = pyo.Param(time_set, initialize=_supply_init, mutable=True)
            T_return_in = pyo.Param(time_set, initialize=_return_init, mutable=True)
            T_return_out = pyo.Param(time_set, initialize=_return_init, mutable=True)
        else:
            T_supply_in = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                  bounds=(supply_temp_min, supply_temp_max))
            T_supply_out = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                   bounds=(supply_temp_min, supply_temp_max))
            T_return_in = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                  bounds=(return_temp_min, return_temp_max))
            T_return_out = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                   bounds=(return_temp_min, return_temp_max))

        setattr(model, f'{prefix}_T_supply_in', T_supply_in)
        setattr(model, f'{prefix}_T_supply_out', T_supply_out)
        setattr(model, f'{prefix}_T_return_in', T_return_in)
        setattr(model, f'{prefix}_T_return_out', T_return_out)

        # ============================================================
        # HEAT LOSS VARIABLES
        # ============================================================

        max_heat_loss_mw = 5.0
        Q_loss_supply = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, max_heat_loss_mw))
        Q_loss_return = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, max_heat_loss_mw))
        Q_delivered = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, max_heat_delivered_mw))

        setattr(model, f'{prefix}_Q_loss_supply', Q_loss_supply)
        setattr(model, f'{prefix}_Q_loss_return', Q_loss_return)
        setattr(model, f'{prefix}_Q_delivered', Q_delivered)

        # ============================================================
        # INVESTMENT VARIABLES (optional)
        # ============================================================

        if upgrade_enabled:
            setattr(model, f'{prefix}_diameter_choice',
                    pyo.Var(getattr(model, f'{prefix}_diameter_options'), domain=pyo.Binary))
            setattr(model, f'{prefix}_insulation_choice',
                    pyo.Var(getattr(model, f'{prefix}_insulation_options'), domain=pyo.Binary))

        # ============================================================
        # CONSTRAINTS â€” INVESTMENT
        # ============================================================

        if upgrade_enabled:
            diameter_choice = getattr(model, f'{prefix}_diameter_choice')
            insulation_choice = getattr(model, f'{prefix}_insulation_choice')

            setattr(model, f'{prefix}_one_diameter',
                    pyo.Constraint(rule=lambda m: sum(diameter_choice[d] for d in diameter_options) == 1))
            setattr(model, f'{prefix}_one_insulation',
                    pyo.Constraint(rule=lambda m: sum(insulation_choice[i] for i in insulation_options) == 1))

        # ============================================================
        # CONSTRAINTS â€” HEAT LOSSES
        # MILP mode: Q_loss = U Ã— L Ã— (T_avg - T_ground) / 1e6  [MW]
        # NLP mode:  Q_loss scales with flow so m_dot=0 does not force
        # contradictory positive losses on stagnant branches.
        # ============================================================

        if temperature_linearize:
            # MILP mode: heat losses computed from Param temperatures.
            # T_supply_in[t] holds the per-timestep heating-curve value (or fixed
            # nominal when no heating curve is configured). Using T_supply_in[t]
            # directly (it is a Param, so all expressions remain linear in m_dot).
            def heat_loss_supply_rule_milp(m, t):
                return Q_loss_supply[t] == (
                    u_value_supply * length_m * (T_supply_in[t] - T_ground[t])
                ) / 1e6

            setattr(model, f'{prefix}_heat_loss_supply',
                    pyo.Constraint(time_set, rule=heat_loss_supply_rule_milp))

            def heat_loss_return_rule_milp(m, t):
                return Q_loss_return[t] == (
                    u_value_return * length_m * (T_return_in[t] - T_ground[t])
                ) / 1e6

            setattr(model, f'{prefix}_heat_loss_return',
                    pyo.Constraint(time_set, rule=heat_loss_return_rule_milp))

            # MILP mode: Q_delivered linked to m_dot via per-timestep Î”T (linear,
            # since T_supply_in and T_return_in are Params, not Variables).
            def heat_delivered_rule_milp(m, t):
                dT = T_supply_in[t] - T_return_in[t]
                return Q_delivered[t] * 1000 == flow_for_hydraulics[t] * cp_water * dT

            setattr(model, f'{prefix}_heat_delivered',
                    pyo.Constraint(time_set, rule=heat_delivered_rule_milp))

            # No temp_drop constraints needed â€” temperatures are fixed Params

        else:
            # Full nonlinear mode (requires QP/NLP solver)
            cp_mw = cp_water / 1000  # MWÂ·s/(kgÂ·K) â€” use throughout to keep coefficients O(1)
            summer_warmup_hours = int(config.get('summer_warmup_hours', 0) or 0)
            summer_warmup_penalty = float(
                config.get('summer_warmup_penalty_eur_per_mwh', 0.0) or 0.0
            )
            summer_warmup_flow_relax = float(
                config.get('summer_warmup_flow_relax_kg_s', 0.0) or 0.0
            )
            summer_warmup_flow_penalty = float(
                config.get('summer_warmup_flow_penalty_eur_per_kg_s', summer_warmup_penalty)
                or summer_warmup_penalty
            )
            summer_warmup_hours = max(0, summer_warmup_hours)
            summer_warmup_penalty = max(0.0, summer_warmup_penalty)
            summer_warmup_flow_relax = max(0.0, summer_warmup_flow_relax)
            summer_warmup_flow_penalty = max(0.0, summer_warmup_flow_penalty)
            _time_list = list(time_set)
            _warmup_times = _time_list[:summer_warmup_hours] if summer_warmup_hours > 0 else []
            _warmup_lookup = set(_warmup_times)
            warmup_slack = None
            warmup_flow_slack = None
            if _warmup_times and summer_warmup_penalty > 0.0:
                setattr(
                    model,
                    f'{prefix}_summer_warmup_slack',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals),
                )
                warmup_slack = getattr(model, f'{prefix}_summer_warmup_slack')
                for _t in time_set:
                    if _t not in _warmup_lookup:
                        warmup_slack[_t].fix(0.0)
                if not hasattr(model, 'demand_slack_penalty_terms'):
                    model.demand_slack_penalty_terms = []
                model.demand_slack_penalty_terms.append((warmup_slack, summer_warmup_penalty))
            if _warmup_times and summer_warmup_flow_relax > 0.0:
                setattr(
                    model,
                    f'{prefix}_summer_warmup_flow_slack',
                    pyo.Var(
                        time_set,
                        domain=pyo.NonNegativeReals,
                        bounds=(0.0, float(summer_warmup_flow_relax)),
                    ),
                )
                warmup_flow_slack = getattr(model, f'{prefix}_summer_warmup_flow_slack')
                for _t in time_set:
                    if _t not in _warmup_lookup:
                        warmup_flow_slack[_t].fix(0.0)
                if not hasattr(model, 'demand_slack_penalty_terms'):
                    model.demand_slack_penalty_terms = []
                model.demand_slack_penalty_terms.append((warmup_flow_slack, summer_warmup_flow_penalty))

            def _warmup_slack_term(t):
                if warmup_slack is None:
                    return 0.0
                if t in _warmup_lookup:
                    return warmup_slack[t]
                return 0.0

            def _warmup_flow_slack_term(t):
                if warmup_flow_slack is None:
                    return 0.0
                if t in _warmup_lookup:
                    return warmup_flow_slack[t]
                return 0.0

            use_heat_loss = bool(physics_cfg.get('heat_loss', True))
            flow_guard_kg_s = 0.0
            flow_activity_threshold = 0.0
            stagnation_mode = str(
                physics_cfg.get('stagnation_mode', config.get('stagnation_mode', 'guard'))
            ).strip().lower()
            if stagnation_mode not in ('guard', 'binary'):
                logger.warning(
                    "Pipe %s: unknown stagnation_mode=%s, falling back to 'guard'",
                    pipe_id,
                    stagnation_mode,
                )
                stagnation_mode = 'guard'
            active_flag = None

            if use_heat_loss:
                # Global steady heat-loss model:
                #   Q_loss ~ U * L * (T_pipe - T_ground)
                # This avoids the previous m_dot/max_flow scaling that strongly
                # suppressed dT and prevented realistic trunk temperature drops.
                #
                # Low-flow guard: use a small additive circulation term in the
                # temperature-drop balance so near-zero flow hours remain feasible
                # and numerically stable without a validation-only model fork.
                guard_frac = float(config.get('heat_loss_flow_guard_rel_maxflow_frac', 0.003) or 0.003)
                guard_vmin = float(config.get('heat_loss_flow_guard_min_velocity_m_s', 0.004) or 0.004)
                guard_abs_min = float(config.get('heat_loss_flow_guard_abs_min_kg_s', 0.01) or 0.01)
                guard_abs_max = float(config.get('heat_loss_flow_guard_abs_max_kg_s', 1.5) or 1.5)
                default_guard = max(
                    guard_frac * float(effective_max_flow),
                    density_water * area_m2 * guard_vmin,
                    guard_abs_min,
                )
                flow_guard_kg_s = float(config.get('heat_loss_flow_guard_kg_s', default_guard))
                flow_guard_kg_s = max(
                    guard_abs_min,
                    min(
                        flow_guard_kg_s,
                        min(max(float(effective_max_flow), guard_abs_min), guard_abs_max),
                    ),
                )
                logger.debug(
                    "  Pipe %s: heat_loss_flow_guard_kg_s=%.4f",
                    pipe_id, flow_guard_kg_s
                )

                if stagnation_mode == 'binary':
                    active_flag = pyo.Var(time_set, domain=pyo.Binary)
                    setattr(model, f'{prefix}_is_active', active_flag)

                    m_big = max(float(effective_max_flow), 1e-3)
                    # Near-zero-flow handling:
                    # allow a small flow band to remain "inactive" so stagnating
                    # branches do not force full heat-loss equations in summer.
                    flow_activity_threshold = float(
                        config.get('stagnation_flow_threshold_kg_s', flow_guard_kg_s)
                    )
                    flow_activity_threshold = max(
                        0.0,
                        min(flow_activity_threshold, max(0.0, m_big)),
                    )
                    dT_sup_big = max(1.0, float(supply_temp_max - supply_temp_min))
                    dT_ret_big = max(1.0, float(return_temp_max - return_temp_min))
                    q_big = max(float(max_heat_loss_mw), 1e-6)
                    q_relax_big = max(
                        q_big,
                        abs(u_value_supply) * length_m * 150.0 / 1e6,
                        abs(u_value_return) * length_m * 150.0 / 1e6,
                    )
                    h_big = max(
                        1e-3,
                        m_big * cp_mw * max(float(supply_temp_max - return_temp_min), 1.0),
                    )

                    setattr(
                        model,
                        f'{prefix}_stagnation_flow_active',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t, _mf=flow_for_hydraulics, _M=m_big, _a=active_flag, _thr=flow_activity_threshold: (
                                _mf[t] <= _thr + _M * _a[t]
                            ),
                        ),
                    )
                    setattr(
                        model,
                        f'{prefix}_stagnation_dt_supply_nonneg',
                        pyo.Constraint(time_set, rule=lambda m, t: T_supply_in[t] - T_supply_out[t] >= 0),
                    )
                    setattr(
                        model,
                        f'{prefix}_stagnation_dt_return_nonneg',
                        pyo.Constraint(time_set, rule=lambda m, t: T_return_in[t] - T_return_out[t] >= 0),
                    )
                    setattr(
                        model,
                        f'{prefix}_stagnation_dt_supply_active',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t, _a=active_flag, _M=dT_sup_big: (
                                T_supply_in[t] - T_supply_out[t] <= _M * _a[t]
                            ),
                        ),
                    )
                    setattr(
                        model,
                        f'{prefix}_stagnation_dt_return_active',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t, _a=active_flag, _M=dT_ret_big: (
                                T_return_in[t] - T_return_out[t] <= _M * _a[t]
                            ),
                        ),
                    )
                    setattr(
                        model,
                        f'{prefix}_stagnation_q_supply_active',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t, _a=active_flag, _M=q_big: Q_loss_supply[t] <= _M * _a[t],
                        ),
                    )
                    setattr(
                        model,
                        f'{prefix}_stagnation_q_return_active',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t, _a=active_flag, _M=q_big: Q_loss_return[t] <= _M * _a[t],
                        ),
                    )
                else:
                    q_relax_big = 0.0
                    h_big = 0.0

                def heat_loss_supply_rule(m, t):
                    if upgrade_enabled:
                        ins_choice = getattr(m, f'{prefix}_insulation_choice')
                        u_eff = sum(
                            ins_choice[insul] * (
                                upgrade_config.get('enhanced_u_value', 0.18)
                                if insul == 'enhanced' else u_value_supply
                            )
                            for insul in insulation_options
                        )
                    else:
                        u_eff = u_value_supply
                    T_avg = (T_supply_in[t] + T_supply_out[t]) / 2.0
                    coeff = u_eff * length_m / 1e6
                    rhs = coeff * (T_avg - T_ground[t])
                    warmup_relax = _warmup_slack_term(t)
                    if active_flag is None:
                        if warmup_slack is None:
                            return Q_loss_supply[t] == rhs
                        return Q_loss_supply[t] - rhs <= warmup_relax
                    return Q_loss_supply[t] - rhs <= q_relax_big * (1 - active_flag[t]) + warmup_relax

                setattr(model, f'{prefix}_heat_loss_supply',
                        pyo.Constraint(time_set, rule=heat_loss_supply_rule))
                if active_flag is not None or warmup_slack is not None:
                    def heat_loss_supply_rule_lb(m, t):
                        if upgrade_enabled:
                            ins_choice = getattr(m, f'{prefix}_insulation_choice')
                            u_eff = sum(
                                ins_choice[insul] * (
                                    upgrade_config.get('enhanced_u_value', 0.18)
                                    if insul == 'enhanced' else u_value_supply
                                )
                                for insul in insulation_options
                            )
                        else:
                            u_eff = u_value_supply
                        T_avg = (T_supply_in[t] + T_supply_out[t]) / 2.0
                        rhs = u_eff * length_m / 1e6 * (T_avg - T_ground[t])
                        warmup_relax = _warmup_slack_term(t)
                        if active_flag is None:
                            return rhs - Q_loss_supply[t] <= warmup_relax
                        return rhs - Q_loss_supply[t] <= q_relax_big * (1 - active_flag[t]) + warmup_relax
                    setattr(
                        model,
                        f'{prefix}_heat_loss_supply_relax_lb',
                        pyo.Constraint(time_set, rule=heat_loss_supply_rule_lb),
                    )

                def heat_loss_return_rule(m, t):
                    if upgrade_enabled:
                        ins_choice = getattr(m, f'{prefix}_insulation_choice')
                        u_eff = sum(
                            ins_choice[insul] * (
                                upgrade_config.get('enhanced_u_value', 0.20)
                                if insul == 'enhanced' else u_value_return
                            )
                            for insul in insulation_options
                        )
                    else:
                        u_eff = u_value_return
                    T_avg = (T_return_in[t] + T_return_out[t]) / 2.0
                    coeff = u_eff * length_m / 1e6
                    rhs = coeff * (T_avg - T_ground[t])
                    warmup_relax = _warmup_slack_term(t)
                    if active_flag is None:
                        if warmup_slack is None:
                            return Q_loss_return[t] == rhs
                        return Q_loss_return[t] - rhs <= warmup_relax
                    return Q_loss_return[t] - rhs <= q_relax_big * (1 - active_flag[t]) + warmup_relax

                setattr(model, f'{prefix}_heat_loss_return',
                        pyo.Constraint(time_set, rule=heat_loss_return_rule))
                if active_flag is not None or warmup_slack is not None:
                    def heat_loss_return_rule_lb(m, t):
                        if upgrade_enabled:
                            ins_choice = getattr(m, f'{prefix}_insulation_choice')
                            u_eff = sum(
                                ins_choice[insul] * (
                                    upgrade_config.get('enhanced_u_value', 0.20)
                                    if insul == 'enhanced' else u_value_return
                                )
                                for insul in insulation_options
                            )
                        else:
                            u_eff = u_value_return
                        T_avg = (T_return_in[t] + T_return_out[t]) / 2.0
                        rhs = u_eff * length_m / 1e6 * (T_avg - T_ground[t])
                        warmup_relax = _warmup_slack_term(t)
                        if active_flag is None:
                            return rhs - Q_loss_return[t] <= warmup_relax
                        return rhs - Q_loss_return[t] <= q_relax_big * (1 - active_flag[t]) + warmup_relax
                    setattr(
                        model,
                        f'{prefix}_heat_loss_return_relax_lb',
                        pyo.Constraint(time_set, rule=heat_loss_return_rule_lb),
                    )

                def temp_drop_supply_rule(m, t):
                    warmup_relax = _warmup_slack_term(t)
                    if active_flag is None:
                        m_eff = flow_for_hydraulics[t] + flow_guard_kg_s
                        if warmup_slack is None:
                            return m_eff * cp_mw * (T_supply_in[t] - T_supply_out[t]) == Q_loss_supply[t]
                        return (
                            m_eff * cp_mw * (T_supply_in[t] - T_supply_out[t]) - Q_loss_supply[t]
                            <= warmup_relax
                        )
                    m_eff = flow_for_hydraulics[t] + flow_guard_kg_s * active_flag[t]
                    lhs = m_eff * cp_mw * (T_supply_in[t] - T_supply_out[t]) - Q_loss_supply[t]
                    return lhs <= h_big * (1 - active_flag[t]) + warmup_relax

                setattr(model, f'{prefix}_temp_drop_supply',
                        pyo.Constraint(time_set, rule=temp_drop_supply_rule))
                if active_flag is not None or warmup_slack is not None:
                    def temp_drop_supply_rule_lb(m, t):
                        warmup_relax = _warmup_slack_term(t)
                        if active_flag is None:
                            m_eff = flow_for_hydraulics[t] + flow_guard_kg_s
                            return (
                                Q_loss_supply[t] - m_eff * cp_mw * (T_supply_in[t] - T_supply_out[t])
                                <= warmup_relax
                            )
                        m_eff = flow_for_hydraulics[t] + flow_guard_kg_s * active_flag[t]
                        return (
                            Q_loss_supply[t] - m_eff * cp_mw * (T_supply_in[t] - T_supply_out[t])
                            <= h_big * (1 - active_flag[t]) + warmup_relax
                        )
                    setattr(
                        model,
                        f'{prefix}_temp_drop_supply_relax_lb',
                        pyo.Constraint(time_set, rule=temp_drop_supply_rule_lb),
                    )

                def temp_drop_return_rule(m, t):
                    warmup_relax = _warmup_slack_term(t)
                    if active_flag is None:
                        m_eff = flow_for_hydraulics[t] + flow_guard_kg_s
                        if warmup_slack is None:
                            return m_eff * cp_mw * (T_return_in[t] - T_return_out[t]) == Q_loss_return[t]
                        return (
                            m_eff * cp_mw * (T_return_in[t] - T_return_out[t]) - Q_loss_return[t]
                            <= warmup_relax
                        )
                    m_eff = flow_for_hydraulics[t] + flow_guard_kg_s * active_flag[t]
                    lhs = m_eff * cp_mw * (T_return_in[t] - T_return_out[t]) - Q_loss_return[t]
                    return lhs <= h_big * (1 - active_flag[t]) + warmup_relax

                setattr(model, f'{prefix}_temp_drop_return',
                        pyo.Constraint(time_set, rule=temp_drop_return_rule))
                if active_flag is not None or warmup_slack is not None:
                    def temp_drop_return_rule_lb(m, t):
                        warmup_relax = _warmup_slack_term(t)
                        if active_flag is None:
                            m_eff = flow_for_hydraulics[t] + flow_guard_kg_s
                            return (
                                Q_loss_return[t] - m_eff * cp_mw * (T_return_in[t] - T_return_out[t])
                                <= warmup_relax
                            )
                        m_eff = flow_for_hydraulics[t] + flow_guard_kg_s * active_flag[t]
                        return (
                            Q_loss_return[t] - m_eff * cp_mw * (T_return_in[t] - T_return_out[t])
                            <= h_big * (1 - active_flag[t]) + warmup_relax
                        )
                    setattr(
                        model,
                        f'{prefix}_temp_drop_return_relax_lb',
                        pyo.Constraint(time_set, rule=temp_drop_return_rule_lb),
                    )

            else:
                # â”€â”€ No heat loss: Q_loss = 0, temperature unchanged along pipe â”€â”€
                # Physical justification: for large-diameter pipes (DNâ‰¥400) the
                # temperature drop is <0.01Â°C per 500m â€” numerically negligible.
                # Numerical benefit: eliminates QLMatrix coefficients as small as
                # 4e-9 (from u*L/(max_flow*1e6)) which cause Gurobi BQP/RLT cuts
                # to falsely prune the feasible region â†’ false infeasibility proof.
                # Without these bilinear terms QLMatrix range collapses from [4e-9,1]
                # to [~0.2, 1] â€” two orders of magnitude, within Gurobi's safe zone.
                for t in time_set:
                    Q_loss_supply[t].fix(0.0)
                    Q_loss_return[t].fix(0.0)

                # Linear temperature propagation: outlet = inlet (no heat loss)
                setattr(model, f'{prefix}_no_loss_supply',
                        pyo.Constraint(time_set,
                                       rule=lambda m, t: T_supply_out[t] == T_supply_in[t]))
                setattr(model, f'{prefix}_no_loss_return',
                        pyo.Constraint(time_set,
                                       rule=lambda m, t: T_return_out[t] == T_return_in[t]))
                logger.info(
                    f"  Pipe {pipe_id}: heat loss disabled (physics.heat_loss=false) â€” "
                    f"T_supply_out=T_supply_in (linear, no bilinear QLMatrix terms)"
                )

            # â”€â”€ Heat delivered (source side) â€” always bilinear â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Q_delivered [MW] = m_dot Ã— (cp/1000) Ã— (T_supply_in âˆ’ T_return_out)
            # With no heat loss: T_return_out = T_return_in = T_return[to_node]
            setattr(model, f'{prefix}_heat_loss_diag', {
                'flow_guard_kg_s': float(flow_guard_kg_s),
                'flow_activity_threshold_kg_s': float(flow_activity_threshold),
                'cp_mw': float(cp_mw),
                'u_value_supply': float(u_value_supply),
                'u_value_return': float(u_value_return),
                'length_m': float(length_m),
                'stagnation_mode': stagnation_mode,
                'summer_warmup_hours': int(summer_warmup_hours),
                'summer_warmup_penalty_eur_per_mwh': float(summer_warmup_penalty),
                'summer_warmup_flow_relax_kg_s': float(summer_warmup_flow_relax),
                'summer_warmup_flow_penalty_eur_per_kg_s': float(summer_warmup_flow_penalty),
            })

            def heat_delivered_rule(m, t):
                expr = flow_for_hydraulics[t] * cp_mw * (T_supply_in[t] - T_return_out[t])
                if warmup_slack is None:
                    return Q_delivered[t] == expr
                return Q_delivered[t] - expr <= _warmup_slack_term(t)

            setattr(model, f'{prefix}_heat_delivered',
                    pyo.Constraint(time_set, rule=heat_delivered_rule))
            if warmup_slack is not None:
                setattr(
                    model,
                    f'{prefix}_heat_delivered_lb',
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t: (
                            flow_for_hydraulics[t] * cp_mw * (T_supply_in[t] - T_return_out[t])
                            - Q_delivered[t]
                            <= _warmup_slack_term(t)
                        ),
                    ),
                )

        # ============================================================
        # PRESSURE DROP VARIABLES
        # ============================================================

        velocity = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, max_velocity * 1.5))

        f_friction = config.get('friction_factor', 0.02)
        k_pressure = f_friction * (length_m / d_inner_m) * (density_water / 2.0) / 100000.0

        # PWL pressure drop (Darcy-Weisbach, 3-segment) â€” MILP-compatible
        # Î”P = f Ã— (L/D) Ã— (Ï/2) Ã— vÂ²  approximated as piecewise-linear in m_dot
        k_flow = k_pressure / ((density_water * area_m2) ** 2) if area_m2 > 0 else 0

        # Physics-based pressure drop bound: actual Darcy-Weisbach Î”P at max flow Ã— 1.2 safety margin.
        # Do NOT use max_pressure_drop as a floor â€” for large-diameter pipes (DN1000) it is
        # ~10Ã— larger than the actual physics bound.  Along a chain of N pipes, the cumulative
        # floor would exceed the producer setpoint (10 bar) and make the LP relaxation infeasible
        # in Gurobi presolve even before any iterations.
        if effective_max_flow > 0 and k_flow > 0:
            dp_upper = k_flow * effective_max_flow ** 2 * 1.2
        else:
            dp_upper = max_pressure_drop

        delta_p_supply = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                 bounds=(0, dp_upper))
        delta_p_return = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                 bounds=(0, dp_upper))
        delta_p_total = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                bounds=(0, dp_upper * 2))

        setattr(model, f'{prefix}_velocity', velocity)
        setattr(model, f'{prefix}_delta_p_supply', delta_p_supply)
        setattr(model, f'{prefix}_delta_p_return', delta_p_return)
        setattr(model, f'{prefix}_delta_p_total', delta_p_total)

        # Velocity: v Ã— Ï Ã— A = m_dot
        if warmup_flow_slack is None:
            setattr(
                model,
                f'{prefix}_velocity_calc',
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t: velocity[t] * density_water * area_m2 == flow_for_hydraulics[t],
                ),
            )
        else:
            setattr(
                model,
                f'{prefix}_velocity_calc',
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t: (
                        velocity[t] * density_water * area_m2 - flow_for_hydraulics[t]
                        <= _warmup_flow_slack_term(t)
                    ),
                ),
            )
            setattr(
                model,
                f'{prefix}_velocity_calc_lb',
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t: (
                        flow_for_hydraulics[t] - velocity[t] * density_water * area_m2
                        <= _warmup_flow_slack_term(t)
                    ),
                ),
            )

        # PWL pressure drop (Darcy-Weisbach, 3-segment) â€” MILP-compatible
        # Î”P = f Ã— (L/D) Ã— (Ï/2) Ã— vÂ²  approximated as piecewise-linear in m_dot
        k_flow = k_pressure / ((density_water * area_m2) ** 2) if area_m2 > 0 else 0

        if effective_max_flow > 0:
            # 2026-07-27: breakpoints concentrated at LOW flow. The old
            # [0, 0.3, 0.7, 1.0] left a wide first segment [0, 0.3*max] whose
            # origin-chord over-estimated the convex P_pump ~ flow^3 up to ~30x,
            # since these oversized pipes run at ~10-30% of design flow most of
            # the year (objective friction pump 10.2 MWh vs 0.6 MWh physical).
            # Placing two breakpoints inside the operating band cuts the secant
            # over-estimation to ~2x while keeping 3 segments (no extra binaries)
            # and the pinned PWL equality (no negative-price P_pump inflation).
            bp_fracs = [0.0, 0.12, 0.35, 1.0]
            bp_flows = [f * effective_max_flow for f in bp_fracs]
            bp_dp = [k_flow * (f * effective_max_flow) ** 2 for f in bp_fracs]

            slopes = []
            intercepts = []
            for s in range(3):
                denom = bp_flows[s + 1] - bp_flows[s]
                slope_s = (bp_dp[s + 1] - bp_dp[s]) / denom if denom > 0 else 0.0
                intercept_s = bp_dp[s] - slope_s * bp_flows[s]
                slopes.append(slope_s)
                intercepts.append(intercept_s)

            if pressure_drop_enabled:
                pwl_seg = pyo.Var(time_set, range(3), domain=pyo.Binary)
                pwl_flow = pyo.Var(time_set, range(3), domain=pyo.NonNegativeReals)
                setattr(model, f'{prefix}_pwl_segment', pwl_seg)
                setattr(model, f'{prefix}_pwl_flow', pwl_flow)

                M_flow = effective_max_flow * 1.1

                setattr(model, f'{prefix}_pwl_one_segment',
                        pyo.Constraint(time_set,
                                       rule=lambda m, t: sum(pwl_seg[t, s] for s in range(3)) == 1))
                setattr(model, f'{prefix}_pwl_flow_sum',
                        pyo.Constraint(time_set,
                                       rule=lambda m, t: flow_for_hydraulics[t] == sum(pwl_flow[t, s] for s in range(3))))

                def seg_flow_lb_rule(m, t, s):
                    return pwl_flow[t, s] >= bp_flows[s] * pwl_seg[t, s]

                def seg_flow_ub_rule(m, t, s):
                    # BUGFIX (chat-review P0): the old formulation added
                    # `+ M_flow*(1 - pwl_seg)`, so an UNSELECTED segment (pwl_seg=0) could
                    # still carry flow up to M_flow. The optimiser then routed flow through
                    # the lowest-slope segment, massively under-stating pressure drop and
                    # pump power. Forcing the upper bound to bp_flows[s+1]*pwl_seg pins an
                    # unselected segment's flow to zero (textbook disaggregated PWL).
                    return pwl_flow[t, s] <= bp_flows[s + 1] * pwl_seg[t, s]

                setattr(model, f'{prefix}_pwl_seg_lb',
                        pyo.Constraint(time_set, range(3), rule=seg_flow_lb_rule))
                setattr(model, f'{prefix}_pwl_seg_ub',
                        pyo.Constraint(time_set, range(3), rule=seg_flow_ub_rule))

                def pwl_dp_rule(m, t):
                    return sum(
                        slopes[s] * pwl_flow[t, s] + intercepts[s] * pwl_seg[t, s]
                        for s in range(3)
                    )

                setattr(model, f'{prefix}_pressure_drop_supply',
                        pyo.Constraint(time_set, rule=lambda m, t: delta_p_supply[t] == pwl_dp_rule(m, t)))
                setattr(model, f'{prefix}_pressure_drop_return',
                        pyo.Constraint(time_set, rule=lambda m, t: delta_p_return[t] == pwl_dp_rule(m, t)))
            else:
                # Pressure drop disabled: fix delta_p to 0 without creating binary PWL vars.
                # Binary PWL segment selectors must NOT be created here — if strict_binary_fixing
                # is active in the solver warmstart, any unknown binary gets .fix(0), turning
                # pwl_one_segment into "0 = 1" which is structurally infeasible.
                for t in time_set:
                    delta_p_supply[t].fix(0.0)
                    delta_p_return[t].fix(0.0)
                    delta_p_total[t].fix(0.0)
        else:
            setattr(model, f'{prefix}_pressure_drop_supply',
                    pyo.Constraint(time_set, rule=lambda m, t: delta_p_supply[t] == 0))
            setattr(model, f'{prefix}_pressure_drop_return',
                    pyo.Constraint(time_set, rule=lambda m, t: delta_p_return[t] == 0))

        setattr(model, f'{prefix}_pressure_drop_total',
                pyo.Constraint(time_set,
                               rule=lambda m, t: delta_p_total[t] == delta_p_supply[t] + delta_p_return[t]))

        # â”€â”€ Pump Power (PWL, per pipe) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # P_pump[t] = (Î”P_supply + Î”P_return) Ã— m_dot Ã— 1e5 / (Ï Ã— Î· Ã— 1e6)  [MW]
        # Approximated as PWL using same breakpoints as pressure drop.
        pump_enabled = config.get('pump_enabled', pressure_drop_enabled)
        eta_pump = float(config.get('pump_efficiency', 0.70))

        if effective_max_flow > 0:
            # Pump power at each breakpoint: P_i = 2 Ã— k_flow Ã— m_iÂ³ Ã— 1e5 / (Ï Ã— Î· Ã— 1e6)
            p_pump_bp = [
                2.0 * k_flow * (bp_flows[i] ** 3) * 1e5 / (density_water * eta_pump * 1e6)
                for i in range(4)
            ]
            P_pump_max = max(p_pump_bp[-1] * 1.2, 1e-6)
        else:
            p_pump_bp = [0.0, 0.0, 0.0, 0.0]
            P_pump_max = 0.0

        P_pump = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, P_pump_max))
        setattr(model, f'{prefix}_P_pump', P_pump)

        if not pump_enabled or not pressure_drop_enabled or effective_max_flow <= 0:
            for t in time_set:
                P_pump[t].fix(0.0)
        else:
            # PWL EQUALITY (secant) pump power -- P_pump is pinned to the PWL of
            # the true cubic at the current flow (SOS-style segment selection via
            # pwl_flow/pwl_seg). Equality is REQUIRED: a lower-bound-only
            # formulation lets the optimiser inflate P_pump to consume
            # negative-price electricity for profit. Over-estimation of the convex
            # cubic is controlled by the low-flow-dense breakpoints (bp_fracs).
            pump_slopes = []
            pump_intercepts = []
            for s in range(3):
                m_lo = bp_flows[s]
                m_hi = bp_flows[s + 1]
                denom = m_hi - m_lo
                slope_s = (p_pump_bp[s + 1] - p_pump_bp[s]) / denom if denom > 0 else 0.0
                intercept_s = p_pump_bp[s] - slope_s * m_lo
                pump_slopes.append(slope_s)
                pump_intercepts.append(intercept_s)

            def pump_power_rule(m, t, _sl=pump_slopes, _ic=pump_intercepts):
                return P_pump[t] == sum(
                    _sl[s] * pwl_flow[t, s] + _ic[s] * pwl_seg[t, s]
                    for s in range(3)
                )

            setattr(model, f'{prefix}_pump_power',
                    pyo.Constraint(time_set, rule=pump_power_rule))

        # Store pressure parameters for results extraction
        pressure_params = {
            'max_pressure_drop_bar': max_pressure_drop,
            'max_velocity_m_s': max_velocity,
            'effective_max_flow_kg_s': effective_max_flow,
            'pipe_diameter_mm': current_diam_supply,
            'pipe_diameter_inner_mm': d_inner_mm,
            'pipe_length_m': length_m,
            'friction_factor': f_friction,
            'k_pressure': k_pressure,
            'pipe_roughness_mm': pipe_roughness,
            'bidirectional': bidirectional,
        }
        setattr(model, f'{prefix}_pressure_params', pressure_params)

        # â”€â”€ Transport Delay â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

        # Delayed delivery variable: Q_consumer[t] = heat arriving at consumer at time t
        Q_consumer = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                             bounds=(0, max_heat_delivered_mw))
        setattr(model, f'{prefix}_Q_consumer', Q_consumer)

        # â”€â”€ Transport Delay â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        #
        # In MILP-linearise mode temperatures are fixed â†’ no bilinear products, and
        # adding binary z_delay selectors on top makes the already-linear model
        # unnecessarily hard and can cause presolve infeasibility.  Skip the delay
        # entirely in that mode and link Q_consumer directly to Q_delivered.
        #
        # In full nonlinear mode: 3-Bucket SOS2 piecewise-linear approximation.
        #   Bucket 0 (high flow):   m_dot âˆˆ [m_mid, m_max] â†’ Ï„â‚ timesteps (shortest)
        #   Bucket 1 (medium flow): m_dot âˆˆ [m_low, m_mid] â†’ Ï„â‚‚ timesteps
        #   Bucket 2 (low flow):    m_dot âˆˆ [0,     m_low] â†’ Ï„â‚ƒ timesteps (longest)
        # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

        use_transport_delay = bool(physics_cfg.get('transport_delay', True))
        delay_warmup_mode = str(
            config.get('delay_warmup_mode', physics_cfg.get('delay_warmup_mode', 'cold_zero'))
        ).strip().lower()
        if delay_warmup_mode not in ('cold_zero', 'hold_first', 'skip'):
            logger.warning(
                "Pipe %s: unknown delay_warmup_mode=%s, using cold_zero",
                pipe_id,
                delay_warmup_mode,
            )
            delay_warmup_mode = 'cold_zero'
        cp_mw = cp_water / 1000
        # Useful heat at the receiving node (pipe outlet side).
        # This formulation stays feasible at m_dot=0 (useful heat = 0), while
        # preserving a physically meaningful consumer-side enthalpy expression.
        useful_heat_expr = {
            t: flow_for_hydraulics[t] * cp_mw * (T_supply_out[t] - T_return_in[t])
            for t in time_set
        }
        q_idle_max = 0.0
        if active_flag is not None:
            # When a pipe is "inactive" in binary stagnation mode, allow only a
            # tiny physically plausible delivered heat based on the configured
            # inactivity flow threshold (instead of forcing strict equality).
            q_idle_max = max(
                0.0,
                flow_activity_threshold * cp_mw
                * max(float(supply_temp_max - return_temp_min), 1.0),
            )

        if milp_linearize or not use_transport_delay:
            # Skip transport delay: Q_consumer equals useful heat arriving at
            # the receiving node (immediate delivery).
            # Reasons to skip:
            #   - milp_linearize mode: temps are fixed Params, delay adds pointless binaries
            #   - physics.transport_delay: false â€” user disabled delay (e.g., for large pipes
            #     where DNâ‰¥400 gives Ï„ < 1 timestep at any realistic flow â†’ delay is zero anyway,
            #     but the binary bucket-selectors still add 3168 binaries and interact with the
            #     bilinear temperature constraints, compounding the MIQCQP numerical difficulty)
            if active_flag is None:
                if warmup_slack is None:
                    setattr(
                        model,
                        f'{prefix}_no_delay',
                        pyo.Constraint(time_set, rule=lambda m, t: Q_consumer[t] == useful_heat_expr[t]),
                    )
                else:
                    setattr(model, f'{prefix}_no_delay',
                            pyo.Constraint(time_set,
                                           rule=lambda m, t: (
                                               Q_consumer[t] - useful_heat_expr[t] <= _warmup_slack_term(t)
                                           )))
                    setattr(
                        model,
                        f'{prefix}_no_delay_lb',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t: (
                                useful_heat_expr[t] - Q_consumer[t] <= _warmup_slack_term(t)
                            ),
                        ),
                    )
            else:
                setattr(
                    model,
                    f'{prefix}_no_delay_ub',
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _a=active_flag, _M=max_heat_delivered_mw: (
                            Q_consumer[t] - useful_heat_expr[t]
                            <= _M * (1 - _a[t]) + _warmup_slack_term(t)
                        ),
                    ),
                )
                setattr(
                    model,
                    f'{prefix}_no_delay_lb',
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _a=active_flag, _M=max_heat_delivered_mw: (
                            useful_heat_expr[t] - Q_consumer[t]
                            <= _M * (1 - _a[t]) + _warmup_slack_term(t)
                        ),
                    ),
                )
                setattr(
                    model,
                    f'{prefix}_no_delay_qcap',
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _a=active_flag, _M=max_heat_delivered_mw, _q0=q_idle_max: (
                            Q_consumer[t] <= _q0 + _M * _a[t]
                        ),
                    ),
                )
            logger.info("  Pipe %s: transport delay skipped (%s)", pipe_id,
                        "milp_linearize mode" if milp_linearize else "physics.transport_delay=false")
            tau_steps = []
            N_BUCKETS = 0
        else:
            dt_h = getattr(model, 'dt_h', 1.0)
            delay_info = compute_delay_buckets(
                length_m=length_m,
                diameter_mm=d_inner_mm,
                density_kg_per_m3=density_water,
                m_max_kg_s=max(effective_max_flow, 0.001),
                dt_h=dt_h,
            )
            tau_steps = delay_info['tau_steps']
            m_bounds = delay_info['m_bounds']
            N_BUCKETS = len(tau_steps)

            logger.info(
                f"  Pipe {pipe_id} delay buckets: "
                f"Ï„={tau_steps} timesteps, "
                f"flow bounds={[(f'{lo:.1f}', f'{hi:.1f}') for lo, hi in m_bounds]} kg/s"
            )

            if max(tau_steps, default=0) <= 0:
                if active_flag is None:
                    if warmup_slack is None:
                        setattr(
                            model,
                            f'{prefix}_no_delay',
                            pyo.Constraint(time_set, rule=lambda m, t: Q_consumer[t] == useful_heat_expr[t]),
                        )
                    else:
                        setattr(model, f'{prefix}_no_delay',
                                pyo.Constraint(time_set,
                                               rule=lambda m, t: (
                                                   Q_consumer[t] - useful_heat_expr[t] <= _warmup_slack_term(t)
                                               )))
                        setattr(
                            model,
                            f'{prefix}_no_delay_lb',
                            pyo.Constraint(
                                time_set,
                                rule=lambda m, t: (
                                    useful_heat_expr[t] - Q_consumer[t] <= _warmup_slack_term(t)
                                ),
                            ),
                        )
                else:
                    setattr(
                        model,
                        f'{prefix}_no_delay_ub',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t, _a=active_flag, _M=max_heat_delivered_mw: (
                                Q_consumer[t] - useful_heat_expr[t]
                                <= _M * (1 - _a[t]) + _warmup_slack_term(t)
                            ),
                        ),
                    )
                    setattr(
                        model,
                        f'{prefix}_no_delay_lb',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t, _a=active_flag, _M=max_heat_delivered_mw: (
                                useful_heat_expr[t] - Q_consumer[t]
                                <= _M * (1 - _a[t]) + _warmup_slack_term(t)
                            ),
                        ),
                    )
                    setattr(
                        model,
                        f'{prefix}_no_delay_qcap',
                        pyo.Constraint(
                            time_set,
                            rule=lambda m, t, _a=active_flag, _M=max_heat_delivered_mw, _q0=q_idle_max: (
                                Q_consumer[t] <= _q0 + _M * _a[t]
                            ),
                        ),
                    )
                logger.info("  Pipe %s: transport delay skipped (all delay buckets are 0)", pipe_id)
                tau_steps = []
                N_BUCKETS = 0
            else:
                time_list = sorted(list(time_set))
                t_idx = {t: i for i, t in enumerate(time_list)}

                z_delay = pyo.Var(range(N_BUCKETS), time_set, domain=pyo.Binary)
                setattr(model, f'{prefix}_z_delay', z_delay)

                setattr(model, f'{prefix}_sos2_delay',
                        pyo.Constraint(time_set,
                                       rule=lambda m, t: sum(z_delay[n, t] for n in range(N_BUCKETS)) == 1))

                M_FLOW_BIG = effective_max_flow * 1.1

                def delay_flow_lb_rule(m, n, t, _tlist=time_list, _tidx=t_idx):
                    i = _tidx[t]
                    if i < tau_steps[n]:
                        return pyo.Constraint.Skip
                    m_lower, _ = m_bounds[n]
                    delayed_source_t = _tlist[i - tau_steps[n]]
                    return flow_for_hydraulics[delayed_source_t] >= m_lower * z_delay[n, t]

                def delay_flow_ub_rule(m, n, t, _tlist=time_list, _tidx=t_idx):
                    i = _tidx[t]
                    if i < tau_steps[n]:
                        return pyo.Constraint.Skip
                    _, m_upper = m_bounds[n]
                    delayed_source_t = _tlist[i - tau_steps[n]]
                    return flow_for_hydraulics[delayed_source_t] <= m_upper + M_FLOW_BIG * (1 - z_delay[n, t])

                setattr(model, f'{prefix}_delay_flow_lb',
                        pyo.Constraint(range(N_BUCKETS), time_set, rule=delay_flow_lb_rule))
                setattr(model, f'{prefix}_delay_flow_ub',
                        pyo.Constraint(range(N_BUCKETS), time_set, rule=delay_flow_ub_rule))

                M_Q = max_heat_delivered_mw
                w_delay = pyo.Var(range(N_BUCKETS), time_set, domain=pyo.NonNegativeReals,
                                  bounds=(0, M_Q))
                setattr(model, f'{prefix}_w_delay', w_delay)

                def w_ub_q_rule(m, n, t, _tlist=time_list, _tidx=t_idx):
                    i = _tidx[t]
                    if i < tau_steps[n]:
                        if delay_warmup_mode == 'skip':
                            return pyo.Constraint.Skip
                        if delay_warmup_mode == 'hold_first':
                            return w_delay[n, t] <= useful_heat_expr[_tlist[0]]
                        # default cold start
                        Q_init = config.get('Q_pipe_initial_mw', 0.0)
                        return w_delay[n, t] <= Q_init
                    delayed_t = _tlist[i - tau_steps[n]]
                    return w_delay[n, t] <= useful_heat_expr[delayed_t]

                def w_ub_z_rule(m, n, t):
                    return w_delay[n, t] <= M_Q * z_delay[n, t]

                def w_lb_rule(m, n, t, _tlist=time_list, _tidx=t_idx):
                    i = _tidx[t]
                    if i < tau_steps[n]:
                        if delay_warmup_mode == 'hold_first':
                            return w_delay[n, t] >= useful_heat_expr[_tlist[0]] - M_Q * (1 - z_delay[n, t])
                        return pyo.Constraint.Skip
                    delayed_t = _tlist[i - tau_steps[n]]
                    return w_delay[n, t] >= useful_heat_expr[delayed_t] - M_Q * (1 - z_delay[n, t])

                setattr(model, f'{prefix}_w_ub_q',
                        pyo.Constraint(range(N_BUCKETS), time_set, rule=w_ub_q_rule))
                setattr(model, f'{prefix}_w_ub_z',
                        pyo.Constraint(range(N_BUCKETS), time_set, rule=w_ub_z_rule))
                setattr(model, f'{prefix}_w_lb',
                        pyo.Constraint(range(N_BUCKETS), time_set, rule=w_lb_rule))

                setattr(model, f'{prefix}_delayed_delivery',
                        pyo.Constraint(time_set,
                                       rule=lambda m, t: Q_consumer[t] == sum(
                                           w_delay[n, t] for n in range(N_BUCKETS)
                                       )))

        # ============================================================
        # COST CALCULATION
        # ============================================================

        capex_expr = 0

        if upgrade_enabled:
            diameter_choice = getattr(model, f'{prefix}_diameter_choice')
            insulation_choice = getattr(model, f'{prefix}_insulation_choice')

            if existing_pipe:
                upgrade_cost_per_m = upgrade_config.get('upgrade_cost_eur_per_m', 200)
                setattr(model, f'{prefix}_upgrade_indicator', pyo.Var(domain=pyo.Binary))
                upgrade_ind = getattr(model, f'{prefix}_upgrade_indicator')
                capex_expr = upgrade_ind * upgrade_cost_per_m * length_m
                current_diam_mm = config.get('current_diameter_supply_mm')
                if current_diam_mm in diameter_options:
                    setattr(model, f'{prefix}_upgrade_link',
                            pyo.Constraint(rule=lambda m: upgrade_ind >= 1 - diameter_choice[current_diam_mm]))
                else:
                    upgrade_ind.fix(1)
            else:
                for d_mm in diameter_options:
                    dn_label = f"DN{d_mm}"
                    if dn_label in pipe_catalog:
                        cost_per_m = pipe_catalog[dn_label].get('capex_eur_per_m', 1000)
                    else:
                        cost_per_m = 500 + d_mm * 3
                    capex_expr += diameter_choice[d_mm] * cost_per_m * length_m

        lifetime_years = config.get('lifetime_years', 40)
        # model.year_frac is the canonical period fraction; period_years is a legacy fallback
        period_years = getattr(model, 'year_frac', None)
        if period_years is None:
            period_years = float(getattr(model, 'period_years', 1.0))
        else:
            period_years = float(period_years)
        annual_capex = capex_expr * (period_years / lifetime_years)

        if not hasattr(model, 'pipe_capex_costs'):
            model.pipe_capex_costs = {}
        model.pipe_capex_costs[pipe_id] = annual_capex

        # ============================================================
        # PHASE 1: STATE CONSTRAINTS
        # ============================================================
        # Enforce physical validity of pipe states (pressures, velocities)
        logger.info(f"  Attaching Phase 1 state constraints for pipe {pipe_id}")

        # 1. Minimum pressure bound (cavitation + pump protection)
        # For pipes, apply to endpoints via node pressures (handled in thermal_node)
        # Here we ensure inline pressure variables stay above minimum
        # Note: Nodes handle their own pressure bounds; pipes inherit through constraints

        # 2. Velocity bounds (stagnation prevention + max velocity)
        if hasattr(model, f'{prefix}_velocity'):
            enforce_velocity_bounds(
                model, time_set, prefix, velocity, flow_for_hydraulics,
                pipe_id, config
            )

        # ============================================================
        # RETURN REFERENCES
        # ============================================================

        return {
            'id': pipe_id,
            'from_node': from_node,
            'to_node': to_node,
            'length_m': length_m,
            'm_dot': m_dot,
            'm_dot_abs': m_dot_abs,
            'flow_dir': flow_dir,
            'T_supply_in': T_supply_in,
            'T_supply_out': T_supply_out,
            'T_return_in': T_return_in,
            'T_return_out': T_return_out,
            'Q_loss_supply': Q_loss_supply,
            'Q_loss_return': Q_loss_return,
            'Q_delivered': Q_delivered,
            'Q_consumer': Q_consumer,
            'capex': annual_capex,
            'existing': existing_pipe,
            'upgrade_enabled': upgrade_enabled,
            'tau_steps': tau_steps,
            'delay_buckets': N_BUCKETS,
            'P_pump': P_pump,
            'pump_enabled': pump_enabled and pressure_drop_enabled,
            'eta_pump': eta_pump,
            'prefix': prefix,
            'heat_loss_flow_guard_kg_s': flow_guard_kg_s if not temperature_linearize else 0.0,
            'stagnation_mode': (
                stagnation_mode if not temperature_linearize else 'off'
            ),
            'bidirectional': bidirectional,
            'delay_warmup_mode': delay_warmup_mode,
        }

    @staticmethod
    def get_results(model, time_set, config: dict[str, Any]) -> dict[str, Any]:
        """Extract results from solved model."""
        pipe_id = config.get('id') or config.get('pipe_id')
        prefix = pipe_id.upper().replace('-', '_')

        m_dot = getattr(model, f'{prefix}_m_dot')
        m_dot_abs = getattr(model, f'{prefix}_m_dot_abs', None)
        flow_dir = getattr(model, f'{prefix}_flow_dir', None)
        T_supply_in = getattr(model, f'{prefix}_T_supply_in')
        T_supply_out = getattr(model, f'{prefix}_T_supply_out')
        T_return_in = getattr(model, f'{prefix}_T_return_in')
        T_return_out = getattr(model, f'{prefix}_T_return_out')
        Q_loss_supply = getattr(model, f'{prefix}_Q_loss_supply')
        Q_loss_return = getattr(model, f'{prefix}_Q_loss_return')
        Q_delivered = getattr(model, f'{prefix}_Q_delivered')
        Q_consumer = getattr(model, f'{prefix}_Q_consumer', None)

        def safe_value(var, t, default=0.0):
            try:
                val = pyo.value(var[t])
                return val if val is not None else default
            except (ValueError, TypeError):
                return default

        flow_series = [safe_value(m_dot, t, 0.0) for t in time_set]
        flow_abs_series = (
            [safe_value(m_dot_abs, t, abs(flow_series[i])) for i, t in enumerate(time_set)]
            if m_dot_abs is not None else [abs(v) for v in flow_series]
        )
        flow_dir_series = (
            [safe_value(flow_dir, t, 1.0) for t in time_set]
            if flow_dir is not None else []
        )
        t_supply_in_series = [safe_value(T_supply_in, t, 90.0) for t in time_set]
        t_supply_out_series = [safe_value(T_supply_out, t, 85.0) for t in time_set]
        t_return_in_series = [safe_value(T_return_in, t, 50.0) for t in time_set]
        t_return_out_series = [safe_value(T_return_out, t, 45.0) for t in time_set]
        q_loss_supply_kw = [safe_value(Q_loss_supply, t, 0.0) * 1000 for t in time_set]
        q_loss_return_kw = [safe_value(Q_loss_return, t, 0.0) * 1000 for t in time_set]
        q_delivered_series = [safe_value(Q_delivered, t, 0.0) for t in time_set]
        q_consumer_series = (
            [safe_value(Q_consumer, t, 0.0) for t in time_set] if Q_consumer else q_delivered_series
        )
        m_eff_series = []
        dt_supply_model_series = [
            float(ts_in) - float(ts_out) for ts_in, ts_out in zip(t_supply_in_series, t_supply_out_series)
        ]
        dt_return_model_series = [
            float(tr_in) - float(tr_out) for tr_in, tr_out in zip(t_return_in_series, t_return_out_series)
        ]
        q_loss_total_mw_series = [
            float(qs + qr) / 1000.0 for qs, qr in zip(q_loss_supply_kw, q_loss_return_kw)
        ]

        velocity_var = getattr(model, f'{prefix}_velocity', None)
        delta_p_supply_var = getattr(model, f'{prefix}_delta_p_supply', None)
        delta_p_return_var = getattr(model, f'{prefix}_delta_p_return', None)
        delta_p_total_var = getattr(model, f'{prefix}_delta_p_total', None)

        velocity_series = [safe_value(velocity_var, t, 0.0) for t in time_set] if velocity_var else []
        delta_p_supply_series = [safe_value(delta_p_supply_var, t, 0.0) for t in time_set] if delta_p_supply_var else []
        delta_p_return_series = [safe_value(delta_p_return_var, t, 0.0) for t in time_set] if delta_p_return_var else []
        delta_p_total_series = [safe_value(delta_p_total_var, t, 0.0) for t in time_set] if delta_p_total_var else []

        pressure_params = getattr(model, f'{prefix}_pressure_params', {})
        heat_loss_diag = getattr(model, f'{prefix}_heat_loss_diag', {}) or {}
        flow_guard_kg_s = float(heat_loss_diag.get('flow_guard_kg_s', 0.0) or 0.0)
        m_eff_series = [float(v) + flow_guard_kg_s for v in flow_abs_series]
        loss_share_pct_series = []
        for ql_mw, qd_mw in zip(q_loss_total_mw_series, q_delivered_series):
            if abs(float(qd_mw)) > 1e-9:
                loss_share_pct_series.append(float(100.0 * ql_mw / float(qd_mw)))
            else:
                loss_share_pct_series.append(0.0)

        dt_h = getattr(model, 'dt_h', 1.0)
        total_heat_delivered_mwh = sum(q_delivered_series) * dt_h
        total_heat_loss_supply_mwh = sum(q_loss_supply_kw) * dt_h / 1000
        total_heat_loss_return_mwh = sum(q_loss_return_kw) * dt_h / 1000
        total_heat_loss_mwh = total_heat_loss_supply_mwh + total_heat_loss_return_mwh

        loss_percentage = (
            (total_heat_loss_mwh / total_heat_delivered_mwh) * 100
            if total_heat_delivered_mwh > 0 else 0.0
        )

        upgrade_config = config.get('upgrade_options', {})
        upgrade_enabled = upgrade_config.get('enabled', False)
        selected_diameter = None
        selected_insulation = None

        if upgrade_enabled:
            diameter_choice = getattr(model, f'{prefix}_diameter_choice')
            insulation_choice = getattr(model, f'{prefix}_insulation_choice')
            for d in upgrade_config.get('diameter_options', []):
                if pyo.value(diameter_choice[d]) > 0.5:
                    selected_diameter = d
                    break
            for i in upgrade_config.get('insulation_options', ['standard']):
                if pyo.value(insulation_choice[i]) > 0.5:
                    selected_insulation = i
                    break

        return {
            'pipe_id': pipe_id,
            'from_node': config['from_node'],
            'to_node': config['to_node'],
            'length_m': config['length_m'],

            # Time series â€” thermal
            'flow_kg_s': flow_series,
            'flow_abs_kg_s': flow_abs_series,
            'flow_dir_binary': flow_dir_series,
            'T_supply_in_c': t_supply_in_series,
            'T_supply_out_c': t_supply_out_series,
            'T_return_in_c': t_return_in_series,
            'T_return_out_c': t_return_out_series,
            'Q_loss_supply_kw': q_loss_supply_kw,
            'Q_loss_return_kw': q_loss_return_kw,
            'Q_loss_total_mw': q_loss_total_mw_series,
            'Q_delivered_mw': q_delivered_series,
            'Q_consumer_mw': q_consumer_series,
            'm_eff_kg_s': m_eff_series,
            'dT_supply_model_c': dt_supply_model_series,
            'dT_return_model_c': dt_return_model_series,
            'loss_share_pct': loss_share_pct_series,

            # Time series â€” hydraulic
            'velocity_m_s': velocity_series,
            'delta_p_supply_bar': delta_p_supply_series,
            'delta_p_return_bar': delta_p_return_series,
            'delta_p_total_bar': delta_p_total_series,

            # Aggregates â€” thermal
            'total_heat_delivered_mwh': total_heat_delivered_mwh,
            'total_heat_loss_mwh': total_heat_loss_mwh,
            'total_heat_loss_supply_mwh': total_heat_loss_supply_mwh,
            'total_heat_loss_return_mwh': total_heat_loss_return_mwh,
            'loss_percentage': loss_percentage,

            # Aggregates â€” hydraulic
            'max_velocity_m_s': max(velocity_series) if velocity_series else 0,
            'avg_velocity_m_s': sum(velocity_series) / len(velocity_series) if velocity_series else 0,
            'max_delta_p_total_bar': max(delta_p_total_series) if delta_p_total_series else 0,
            'avg_delta_p_total_bar': (
                sum(delta_p_total_series) / len(delta_p_total_series) if delta_p_total_series else 0
            ),

            # Averages â€” thermal
            'avg_flow_kg_s': sum(flow_series) / len(flow_series) if flow_series else 0,
            'avg_abs_flow_kg_s': sum(flow_abs_series) / len(flow_abs_series) if flow_abs_series else 0,
            'avg_supply_temp_in_c': sum(t_supply_in_series) / len(t_supply_in_series) if t_supply_in_series else 0,
            'avg_return_temp_out_c': sum(t_return_out_series) / len(t_return_out_series) if t_return_out_series else 0,

            # Pipe parameters
            'pipe_diameter_mm': pressure_params.get('pipe_diameter_mm'),
            'pipe_diameter_inner_mm': pressure_params.get('pipe_diameter_inner_mm'),
            'friction_factor': pressure_params.get('friction_factor'),
            'heat_loss_flow_guard_kg_s': flow_guard_kg_s,
            'bidirectional': bool(pressure_params.get('bidirectional', False)),
            'stagnation_mode': heat_loss_diag.get('stagnation_mode', 'guard'),

            # Investment results
            'selected_diameter_mm': selected_diameter,
            'selected_insulation': selected_insulation,
            'current_diameter_mm': config.get('current_diameter_supply_mm'),
            'upgrade_recommended': (
                selected_diameter != config.get('current_diameter_supply_mm')
                if selected_diameter else False
            ),
        }
