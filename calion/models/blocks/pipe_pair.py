"""
Pipe Pair Component for District Heating Networks

Models supply and return pipes with:
- Temperature-dependent heat losses (Darcy-Weisbach)
- Piecewise-linear pressure drop (MILP-compatible, 3-segment PWL)
- Transport time delay (linearised with 3-bucket SOS2 binary selection)
- Investment optimization (optional diameter/insulation upgrade)

Unified physics — no brownfield/greenfield distinction.

Author: CALION Development Team
"""

from typing import Dict, Any, Optional, List
import logging
import math

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

from ..component import BaseComponent
from ..registry import register_component
from ..network_physics import compute_delay_buckets

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
        - T_supply_in[t], T_supply_out[t]: Supply temperatures (°C)
        - T_return_in[t], T_return_out[t]: Return temperatures (°C)
        - Q_loss_supply[t], Q_loss_return[t]: Heat losses (MW)
        - Q_delivered[t]: Heat entering supply pipe at source side (MW)
        - Q_consumer[t]: Heat delivered to consumer (delayed) (MW)
        - z_delay[n, t]: Binary bucket selector for transport delay
        - w_delay[n, t]: Linearisation auxiliary for z_delay × Q_delivered
        - diameter_choice[d]: Binary for diameter selection (if investable)
        - insulation_choice[i]: Binary for insulation type (if upgradeable)
    """

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> None:
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
    def attach(model, time_set, config: Dict[str, Any], buses: Dict) -> Dict[str, Any]:
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
        cp_water = 4.186       # kJ/(kg·K)
        density_water = 1000   # kg/m³
        mu_water = 0.0004      # Dynamic viscosity at 80°C [Pa·s]

        # Temperature parameters
        supply_temp_nominal_c = config.get('supply_temp_nominal_c', 90.0)
        return_temp_nominal_c = config.get('return_temp_nominal_c', 50.0)

        # Ground/ambient temperature
        use_outdoor_temp = config.get('use_outdoor_temperature', False)
        if use_outdoor_temp and hasattr(model, 'outdoor_temp'):
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

        m_dot = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, effective_max_flow))
        setattr(model, f'{prefix}_m_dot', m_dot)

        logger.info(
            f"Pipe {pipe_id}: max flow = {effective_max_flow:.2f} kg/s "
            f"(v_max={max_velocity} m/s, D={current_diam_supply or 'unspec'} mm)"
        )

        # ============================================================
        # TEMPERATURE VARIABLES (or PARAMS in MILP-linearized mode)
        # ============================================================

        milp_linearize = config.get('milp_linearize', False)

        if milp_linearize:
            # Fix temperatures at nominal values → all T×m_dot products become linear
            T_supply_in = pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True)
            T_supply_out = pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True)
            T_return_in = pyo.Param(time_set, initialize=return_temp_nominal_c, mutable=True)
            T_return_out = pyo.Param(time_set, initialize=return_temp_nominal_c, mutable=True)
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
        # CONSTRAINTS — INVESTMENT
        # ============================================================

        if upgrade_enabled:
            diameter_choice = getattr(model, f'{prefix}_diameter_choice')
            insulation_choice = getattr(model, f'{prefix}_insulation_choice')

            setattr(model, f'{prefix}_one_diameter',
                    pyo.Constraint(rule=lambda m: sum(diameter_choice[d] for d in diameter_options) == 1))
            setattr(model, f'{prefix}_one_insulation',
                    pyo.Constraint(rule=lambda m: sum(insulation_choice[i] for i in insulation_options) == 1))

        # ============================================================
        # CONSTRAINTS — HEAT LOSSES
        # Q_loss = U × L × (T_avg - T_ground) / 1e6  [MW]
        # ============================================================

        if milp_linearize:
            # MILP mode: heat losses computed from fixed nominal temperatures
            # Q_loss is fully determined (no bilinear products)
            def heat_loss_supply_rule_milp(m, t):
                T_avg = supply_temp_nominal_c  # fixed nominal
                return Q_loss_supply[t] == (u_value_supply * length_m * (T_avg - T_ground[t])) / 1e6

            setattr(model, f'{prefix}_heat_loss_supply',
                    pyo.Constraint(time_set, rule=heat_loss_supply_rule_milp))

            def heat_loss_return_rule_milp(m, t):
                T_avg = return_temp_nominal_c  # fixed nominal
                return Q_loss_return[t] == (u_value_return * length_m * (T_avg - T_ground[t])) / 1e6

            setattr(model, f'{prefix}_heat_loss_return',
                    pyo.Constraint(time_set, rule=heat_loss_return_rule_milp))

            # MILP mode: Q_delivered linked to m_dot via fixed ΔT (linear)
            def heat_delivered_rule_milp(m, t):
                dT = supply_temp_nominal_c - return_temp_nominal_c
                return Q_delivered[t] * 1000 == m_dot[t] * cp_water * dT

            setattr(model, f'{prefix}_heat_delivered',
                    pyo.Constraint(time_set, rule=heat_delivered_rule_milp))

            # No temp_drop constraints needed — temperatures are fixed Params

        else:
            # Full nonlinear mode (requires QP/NLP solver)
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
                return Q_loss_supply[t] == (u_eff * length_m * (T_avg - T_ground[t])) / 1e6

            setattr(model, f'{prefix}_heat_loss_supply',
                    pyo.Constraint(time_set, rule=heat_loss_supply_rule))

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
                return Q_loss_return[t] == (u_eff * length_m * (T_avg - T_ground[t])) / 1e6

            setattr(model, f'{prefix}_heat_loss_return',
                    pyo.Constraint(time_set, rule=heat_loss_return_rule))

            # ============================================================
            # CONSTRAINTS — TEMPERATURE DROP (energy balance)
            # m_dot × c_p × (T_in − T_out) = Q_loss × 1000  (MW→kW)
            # ============================================================

            def temp_drop_supply_rule(m, t):
                return m_dot[t] * cp_water * (T_supply_in[t] - T_supply_out[t]) == Q_loss_supply[t] * 1000

            setattr(model, f'{prefix}_temp_drop_supply',
                    pyo.Constraint(time_set, rule=temp_drop_supply_rule))

            def temp_drop_return_rule(m, t):
                return m_dot[t] * cp_water * (T_return_in[t] - T_return_out[t]) == Q_loss_return[t] * 1000

            setattr(model, f'{prefix}_temp_drop_return',
                    pyo.Constraint(time_set, rule=temp_drop_return_rule))

            # ============================================================
            # CONSTRAINTS — HEAT DELIVERED (source side)
            # Q_delivered × 1000 = m_dot × c_p × (T_supply_in − T_return_out)
            # ============================================================

            def heat_delivered_rule(m, t):
                return Q_delivered[t] * 1000 == m_dot[t] * cp_water * (T_supply_in[t] - T_return_out[t])

            setattr(model, f'{prefix}_heat_delivered',
                    pyo.Constraint(time_set, rule=heat_delivered_rule))

        # ============================================================
        # PRESSURE DROP VARIABLES
        # ============================================================

        velocity = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, max_velocity * 1.5))
        delta_p_supply = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                 bounds=(0, max_pressure_drop * 2))
        delta_p_return = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                 bounds=(0, max_pressure_drop * 2))
        delta_p_total = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                bounds=(0, max_pressure_drop * 4))

        setattr(model, f'{prefix}_velocity', velocity)
        setattr(model, f'{prefix}_delta_p_supply', delta_p_supply)
        setattr(model, f'{prefix}_delta_p_return', delta_p_return)
        setattr(model, f'{prefix}_delta_p_total', delta_p_total)

        f_friction = config.get('friction_factor', 0.02)
        k_pressure = f_friction * (length_m / d_inner_m) * (density_water / 2.0) / 100000.0

        # Velocity: v × ρ × A = m_dot
        setattr(model, f'{prefix}_velocity_calc',
                pyo.Constraint(time_set,
                               rule=lambda m, t: velocity[t] * density_water * area_m2 == m_dot[t]))

        # PWL pressure drop (Darcy-Weisbach, 3-segment) — MILP-compatible
        # ΔP = f × (L/D) × (ρ/2) × v²  approximated as piecewise-linear in m_dot
        k_flow = k_pressure / ((density_water * area_m2) ** 2) if area_m2 > 0 else 0

        if effective_max_flow > 0:
            bp_fracs = [0.0, 0.3, 0.7, 1.0]
            bp_flows = [f * effective_max_flow for f in bp_fracs]
            bp_dp = [k_flow * (f * effective_max_flow) ** 2 for f in bp_fracs]

            slopes = [2 * k_flow * (bp_flows[s] + bp_flows[s + 1]) / 2 for s in range(3)]
            intercepts = [bp_dp[s] - slopes[s] * bp_flows[s] for s in range(3)]

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
                                   rule=lambda m, t: m_dot[t] == sum(pwl_flow[t, s] for s in range(3))))

            def seg_flow_lb_rule(m, t, s):
                return pwl_flow[t, s] >= bp_flows[s] * pwl_seg[t, s]

            def seg_flow_ub_rule(m, t, s):
                return pwl_flow[t, s] <= bp_flows[s + 1] * pwl_seg[t, s] + M_flow * (1 - pwl_seg[t, s])

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
            setattr(model, f'{prefix}_pressure_drop_supply',
                    pyo.Constraint(time_set, rule=lambda m, t: delta_p_supply[t] == 0))
            setattr(model, f'{prefix}_pressure_drop_return',
                    pyo.Constraint(time_set, rule=lambda m, t: delta_p_return[t] == 0))

        setattr(model, f'{prefix}_pressure_drop_total',
                pyo.Constraint(time_set,
                               rule=lambda m, t: delta_p_total[t] == delta_p_supply[t] + delta_p_return[t]))

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
        }
        setattr(model, f'{prefix}_pressure_params', pressure_params)

        # ── Transport Delay ────────────────────────────────────────────────────────

        # Delayed delivery variable: Q_consumer[t] = heat arriving at consumer at time t
        Q_consumer = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                             bounds=(0, max_heat_delivered_mw))
        setattr(model, f'{prefix}_Q_consumer', Q_consumer)

        # ── Transport Delay ─────────────────────────────────────────────────────────
        #
        # In MILP-linearise mode temperatures are fixed → no bilinear products, and
        # adding binary z_delay selectors on top makes the already-linear model
        # unnecessarily hard and can cause presolve infeasibility.  Skip the delay
        # entirely in that mode and link Q_consumer directly to Q_delivered.
        #
        # In full nonlinear mode: 3-Bucket SOS2 piecewise-linear approximation.
        #   Bucket 0 (high flow):   m_dot ∈ [m_mid, m_max] → τ₁ timesteps (shortest)
        #   Bucket 1 (medium flow): m_dot ∈ [m_low, m_mid] → τ₂ timesteps
        #   Bucket 2 (low flow):    m_dot ∈ [0,     m_low] → τ₃ timesteps (longest)
        # ─────────────────────────────────────────────────────────────────────────

        if milp_linearize:
            # MILP-linearise mode: no transport delay — Q_consumer == Q_delivered
            setattr(model, f'{prefix}_no_delay',
                    pyo.Constraint(time_set,
                                   rule=lambda m, t: Q_consumer[t] == Q_delivered[t]))
            logger.info("  Pipe %s: transport delay skipped (milp_linearize mode)", pipe_id)
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
                f"τ={tau_steps} timesteps, "
                f"flow bounds={[(f'{lo:.1f}', f'{hi:.1f}') for lo, hi in m_bounds]} kg/s"
            )

            time_list = sorted(list(time_set))
            t_idx = {t: i for i, t in enumerate(time_list)}

            z_delay = pyo.Var(range(N_BUCKETS), time_set, domain=pyo.Binary)
            setattr(model, f'{prefix}_z_delay', z_delay)

            setattr(model, f'{prefix}_sos2_delay',
                    pyo.Constraint(time_set,
                                   rule=lambda m, t: sum(z_delay[n, t] for n in range(N_BUCKETS)) == 1))

            M_FLOW_BIG = effective_max_flow * 1.1

            def delay_flow_lb_rule(m, n, t):
                m_lower, _ = m_bounds[n]
                return m_dot[t] >= m_lower * z_delay[n, t]

            def delay_flow_ub_rule(m, n, t):
                _, m_upper = m_bounds[n]
                return m_dot[t] <= m_upper + M_FLOW_BIG * (1 - z_delay[n, t])

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
                    # Warm-up period: delay reaches before horizon start.
                    # Let w_delay be free (bounded only by M_Q via w_ub_z).
                    return pyo.Constraint.Skip
                delayed_t = _tlist[i - tau_steps[n]]
                return w_delay[n, t] <= Q_delivered[delayed_t]

            def w_ub_z_rule(m, n, t):
                return w_delay[n, t] <= M_Q * z_delay[n, t]

            def w_lb_rule(m, n, t, _tlist=time_list, _tidx=t_idx):
                i = _tidx[t]
                if i < tau_steps[n]:
                    # Warm-up period: no lower bound from Q_delivered.
                    return pyo.Constraint.Skip
                delayed_t = _tlist[i - tau_steps[n]]
                return w_delay[n, t] >= Q_delivered[delayed_t] - M_Q * (1 - z_delay[n, t])

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
        # RETURN REFERENCES
        # ============================================================

        return {
            'id': pipe_id,
            'from_node': from_node,
            'to_node': to_node,
            'length_m': length_m,
            'm_dot': m_dot,
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
        }

    @staticmethod
    def get_results(model, time_set, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract results from solved model."""
        pipe_id = config.get('id') or config.get('pipe_id')
        prefix = pipe_id.upper().replace('-', '_')

        m_dot = getattr(model, f'{prefix}_m_dot')
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

        velocity_var = getattr(model, f'{prefix}_velocity', None)
        delta_p_supply_var = getattr(model, f'{prefix}_delta_p_supply', None)
        delta_p_return_var = getattr(model, f'{prefix}_delta_p_return', None)
        delta_p_total_var = getattr(model, f'{prefix}_delta_p_total', None)

        velocity_series = [safe_value(velocity_var, t, 0.0) for t in time_set] if velocity_var else []
        delta_p_supply_series = [safe_value(delta_p_supply_var, t, 0.0) for t in time_set] if delta_p_supply_var else []
        delta_p_return_series = [safe_value(delta_p_return_var, t, 0.0) for t in time_set] if delta_p_return_var else []
        delta_p_total_series = [safe_value(delta_p_total_var, t, 0.0) for t in time_set] if delta_p_total_var else []

        pressure_params = getattr(model, f'{prefix}_pressure_params', {})

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

            # Time series — thermal
            'flow_kg_s': flow_series,
            'T_supply_in_c': t_supply_in_series,
            'T_supply_out_c': t_supply_out_series,
            'T_return_in_c': t_return_in_series,
            'T_return_out_c': t_return_out_series,
            'Q_loss_supply_kw': q_loss_supply_kw,
            'Q_loss_return_kw': q_loss_return_kw,
            'Q_delivered_mw': q_delivered_series,
            'Q_consumer_mw': q_consumer_series,

            # Time series — hydraulic
            'velocity_m_s': velocity_series,
            'delta_p_supply_bar': delta_p_supply_series,
            'delta_p_return_bar': delta_p_return_series,
            'delta_p_total_bar': delta_p_total_series,

            # Aggregates — thermal
            'total_heat_delivered_mwh': total_heat_delivered_mwh,
            'total_heat_loss_mwh': total_heat_loss_mwh,
            'total_heat_loss_supply_mwh': total_heat_loss_supply_mwh,
            'total_heat_loss_return_mwh': total_heat_loss_return_mwh,
            'loss_percentage': loss_percentage,

            # Aggregates — hydraulic
            'max_velocity_m_s': max(velocity_series) if velocity_series else 0,
            'avg_velocity_m_s': sum(velocity_series) / len(velocity_series) if velocity_series else 0,
            'max_delta_p_total_bar': max(delta_p_total_series) if delta_p_total_series else 0,
            'avg_delta_p_total_bar': (
                sum(delta_p_total_series) / len(delta_p_total_series) if delta_p_total_series else 0
            ),

            # Averages — thermal
            'avg_flow_kg_s': sum(flow_series) / len(flow_series) if flow_series else 0,
            'avg_supply_temp_in_c': sum(t_supply_in_series) / len(t_supply_in_series) if t_supply_in_series else 0,
            'avg_return_temp_out_c': sum(t_return_out_series) / len(t_return_out_series) if t_return_out_series else 0,

            # Pipe parameters
            'pipe_diameter_mm': pressure_params.get('pipe_diameter_mm'),
            'pipe_diameter_inner_mm': pressure_params.get('pipe_diameter_inner_mm'),
            'friction_factor': pressure_params.get('friction_factor'),

            # Investment results
            'selected_diameter_mm': selected_diameter,
            'selected_insulation': selected_insulation,
            'current_diameter_mm': config.get('current_diameter_supply_mm'),
            'upgrade_recommended': (
                selected_diameter != config.get('current_diameter_supply_mm')
                if selected_diameter else False
            ),
        }
