"""
Pipe Pair Component for District Heating Networks

Models supply and return pipes with:
- Temperature-dependent heat losses
- Outdoor temperature coupling
- Discrete diameter selection
- Investment optimization

Author: EnerGIS Development Team
Date: 2025-12-10
"""

from typing import Dict, Any, Optional, List
import logging

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

from ..component import BaseComponent
from ..registry import register_component

logger = logging.getLogger(__name__)


@register_component("pipe_pair")
class PipePairBlock(BaseComponent):
    """
    Pair of pipes (supply + return) for district heating network.

    Models:
    - Heat losses dependent on pipe temperature and ground temperature
    - Temperature propagation along pipes
    - Mass flow balance
    - Optional diameter selection and insulation upgrade
    - Investment decisions

    Variables (per timestep t):
        - m_dot[t]: Mass flow through pipes (kg/s)
        - T_supply_in[t], T_supply_out[t]: Supply temperatures (°C)
        - T_return_in[t], T_return_out[t]: Return temperatures (°C)
        - Q_loss_supply[t], Q_loss_return[t]: Heat losses (MW)
        - Q_delivered[t]: Net heat delivered (MW)
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

        # Check diameter configuration
        if 'current_diameter_supply_mm' not in config and 'diameter_options' not in config:
            raise ValueError(f"Pipe {config['id']}: must specify either current_diameter or diameter_options")

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
        cp_water = 4.186  # kJ/(kg·K)
        density_water = 1000  # kg/m³

        # Temperature parameters
        supply_temp_nominal_c = config.get('supply_temp_nominal_c', 90.0)
        return_temp_nominal_c = config.get('return_temp_nominal_c', 50.0)
        network_delta_t_k = supply_temp_nominal_c - return_temp_nominal_c

        # Ground/ambient temperature
        use_outdoor_temp = config.get('use_outdoor_temperature', False)
        if use_outdoor_temp and hasattr(model, 'outdoor_temp'):
            # Use time-varying outdoor temperature from model
            T_ground = model.outdoor_temp
        else:
            # Fixed ground temperature
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
        diameter_options = upgrade_config.get('diameter_options', [current_diam_supply] if current_diam_supply else [200])
        insulation_options = upgrade_config.get('insulation_options', ['standard'])

        # Pipe catalog for costs
        pipe_catalog = config.get('pipe_catalog', {})

        # ============================================================
        # SETS
        # ============================================================

        if upgrade_enabled:
            setattr(model, f'{prefix}_diameter_options',
                    pyo.Set(initialize=diameter_options))
            setattr(model, f'{prefix}_insulation_options',
                    pyo.Set(initialize=insulation_options))

        # ============================================================
        # VARIABLES
        # ============================================================

        # Mass flow (kg/s) - same for supply and return
        setattr(model, f'{prefix}_m_dot',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(0, 500)))  # Max 500 kg/s = 180 m³/h

        # Temperature bounds based on network parameters
        # Supply: from (nominal - 30) to (nominal + 10), at least 60-130°C range
        supply_temp_min = min(60, supply_temp_nominal_c - 30)
        supply_temp_max = max(130, supply_temp_nominal_c + 10)
        # Return: from 30°C to (nominal + 20), at least 30-90°C range
        return_temp_min = 30
        return_temp_max = max(90, return_temp_nominal_c + 20)

        # Supply pipe temperatures (°C)
        setattr(model, f'{prefix}_T_supply_in',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(supply_temp_min, supply_temp_max)))
        setattr(model, f'{prefix}_T_supply_out',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(supply_temp_min, supply_temp_max)))

        # Return pipe temperatures (°C)
        setattr(model, f'{prefix}_T_return_in',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(return_temp_min, return_temp_max)))
        setattr(model, f'{prefix}_T_return_out',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(return_temp_min, return_temp_max)))

        # Heat losses (MW) - bounded to prevent unbounded solutions
        # Max heat loss estimate: U × L × ΔT_max / 1e6
        # Conservative bound: 5 MW per pipe (even for longest pipes)
        max_heat_loss_mw = 5.0
        setattr(model, f'{prefix}_Q_loss_supply',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(0, max_heat_loss_mw)))
        setattr(model, f'{prefix}_Q_loss_return',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(0, max_heat_loss_mw)))

        # Heat delivered (MW) - bounded by max pipe capacity
        # Max heat: max_flow × cp × ΔT / 1000
        # Use conservative upper bound (500 kg/s max flow * 40K delta_T)
        delta_t_max = supply_temp_nominal_c - return_temp_nominal_c
        max_flow_estimate = 500.0  # kg/s - will be refined later based on diameter
        max_heat_delivered_mw = max_flow_estimate * cp_water * delta_t_max / 1000 * 1.2  # 20% margin
        max_heat_delivered_mw = max(max_heat_delivered_mw, 100.0)  # At least 100 MW
        setattr(model, f'{prefix}_Q_delivered',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(0, max_heat_delivered_mw)))

        # Investment variables (if upgrade enabled)
        if upgrade_enabled:
            setattr(model, f'{prefix}_diameter_choice',
                    pyo.Var(getattr(model, f'{prefix}_diameter_options'),
                           domain=pyo.Binary))
            setattr(model, f'{prefix}_insulation_choice',
                    pyo.Var(getattr(model, f'{prefix}_insulation_options'),
                           domain=pyo.Binary))

        # Retrieve variables for constraint definition
        m_dot = getattr(model, f'{prefix}_m_dot')
        T_supply_in = getattr(model, f'{prefix}_T_supply_in')
        T_supply_out = getattr(model, f'{prefix}_T_supply_out')
        T_return_in = getattr(model, f'{prefix}_T_return_in')
        T_return_out = getattr(model, f'{prefix}_T_return_out')
        Q_loss_supply = getattr(model, f'{prefix}_Q_loss_supply')
        Q_loss_return = getattr(model, f'{prefix}_Q_loss_return')
        Q_delivered = getattr(model, f'{prefix}_Q_delivered')

        # ============================================================
        # BROWNFIELD MODE: Temperature fixing moved to network_manager.py
        # ============================================================
        # In brownfield mode, temperatures are fixed by network_manager AFTER
        # all pipes and nodes are attached. This ensures consistent temperatures
        # based on the actual network topology (plant nodes vs consumer nodes).
        #
        # NOTE: Do NOT fix temperatures here! network_manager.py handles this
        # in PHASE 3b to avoid conflicts between pipe inlet temps and node temps.

        brownfield_mode = config.get('brownfield_mode', False)
        if brownfield_mode:
            logger.info(f"    {pipe_id}: Brownfield mode - temps will be fixed by network_manager")

        # ============================================================
        # CONSTRAINTS
        # ============================================================

        # (1) Diameter selection constraint (if upgrade enabled)
        if upgrade_enabled:
            diameter_choice = getattr(model, f'{prefix}_diameter_choice')
            insulation_choice = getattr(model, f'{prefix}_insulation_choice')

            def one_diameter_rule(m):
                return sum(diameter_choice[d] for d in diameter_options) == 1

            setattr(model, f'{prefix}_one_diameter',
                    pyo.Constraint(rule=one_diameter_rule))

            def one_insulation_rule(m):
                return sum(insulation_choice[i] for i in insulation_options) == 1

            setattr(model, f'{prefix}_one_insulation',
                    pyo.Constraint(rule=one_insulation_rule))

        # (2) Heat loss calculation (supply pipe)
        # Q_loss = U * Length * (T_avg - T_ground)
        # where T_avg = (T_in + T_out) / 2
        #
        # NOTE: In brownfield mode, we SKIP these constraints!
        # Reason: With fixed temperatures, both heat_loss and temp_drop constraints
        # would overdetermine the system (inconsistent m_dot values).
        # Instead, we let Q_loss be determined by the temp_drop constraints alone.

        if not brownfield_mode:
            def heat_loss_supply_rule(m, t):
                # Get effective U-value
                if upgrade_enabled:
                    insulation_choice = getattr(m, f'{prefix}_insulation_choice')
                    u_eff = 0
                    for insul_type in insulation_options:
                        if insul_type == 'standard':
                            u_val = u_value_supply
                        elif insul_type == 'enhanced':
                            u_val = upgrade_config.get('enhanced_u_value', 0.18)
                        else:
                            u_val = u_value_supply
                        u_eff += insulation_choice[insul_type] * u_val
                else:
                    u_eff = u_value_supply

                # Average temperature in pipe
                T_avg = (T_supply_in[t] + T_supply_out[t]) / 2.0

                # Temperature difference to ground
                delta_T = T_avg - T_ground[t]

                # Heat loss in MW: (W/(m·K)) * m * K / 1e6
                q_loss_mw = (u_eff * length_m * delta_T) / 1e6

                return Q_loss_supply[t] == q_loss_mw

            setattr(model, f'{prefix}_heat_loss_supply',
                    pyo.Constraint(time_set, rule=heat_loss_supply_rule))

            # (3) Heat loss calculation (return pipe)
            def heat_loss_return_rule(m, t):
                # Get effective U-value
                if upgrade_enabled:
                    insulation_choice = getattr(m, f'{prefix}_insulation_choice')
                    u_eff = 0
                    for insul_type in insulation_options:
                        if insul_type == 'standard':
                            u_val = u_value_return
                        elif insul_type == 'enhanced':
                            u_val = upgrade_config.get('enhanced_u_value', 0.20)
                        else:
                            u_val = u_value_return
                        u_eff += insulation_choice[insul_type] * u_val
                else:
                    u_eff = u_value_return

                # Average temperature in return pipe
                T_avg = (T_return_in[t] + T_return_out[t]) / 2.0

                # Temperature difference (can be negative if return < ground)
                delta_T = T_avg - T_ground[t]

                # Heat loss/gain in MW
                # Note: If delta_T < 0, this becomes negative (heat gain)
                # For simplicity in Phase 1, we assume T_return > T_ground always
                q_loss_mw = (u_eff * length_m * delta_T) / 1e6

                return Q_loss_return[t] == q_loss_mw

            setattr(model, f'{prefix}_heat_loss_return',
                    pyo.Constraint(time_set, rule=heat_loss_return_rule))
        else:
            logger.info(f"    {pipe_id}: Brownfield mode - skipping heat loss calc constraints (using temp drop only)")

        # (4) Temperature drop in supply pipe
        # Energy balance: m_dot * c_p * (T_in - T_out) = Q_loss
        # T_out = T_in - Q_loss / (m_dot * c_p)

        def temp_drop_supply_rule(m, t):
            # Avoid division by zero: use small epsilon or conditional
            # For MILP, we use: m_dot * c_p * (T_in - T_out) = Q_loss * 1000 (MW to kW)
            return m_dot[t] * cp_water * (T_supply_in[t] - T_supply_out[t]) == Q_loss_supply[t] * 1000

        setattr(model, f'{prefix}_temp_drop_supply',
                pyo.Constraint(time_set, rule=temp_drop_supply_rule))

        # (5) Temperature rise in return pipe (heat loss means temp drops)
        # T_out = T_in - Q_loss / (m_dot * c_p)
        # But for return: we're going backwards, so T_out (at plant) < T_in (from consumer)

        def temp_drop_return_rule(m, t):
            # Return pipe loses heat as it goes back to plant
            # T_return_out (at plant) = T_return_in (at consumer) - loss
            return m_dot[t] * cp_water * (T_return_in[t] - T_return_out[t]) == Q_loss_return[t] * 1000

        setattr(model, f'{prefix}_temp_drop_return',
                pyo.Constraint(time_set, rule=temp_drop_return_rule))

        # (6) Heat delivered to consumer
        # Q = m_dot * c_p * (T_supply_out - T_return_in)
        # This is the heat extracted by the consumer

        def heat_delivered_rule(m, t):
            # Heat delivered in MW
            return Q_delivered[t] * 1000 == m_dot[t] * cp_water * (T_supply_out[t] - T_return_in[t])

        setattr(model, f'{prefix}_heat_delivered',
                pyo.Constraint(time_set, rule=heat_delivered_rule))

        # (7) Minimum flow constraint (avoid division by zero in temp calculations)
        # When there's demand, ensure minimum flow

        def min_flow_rule(m, t):
            # If Q_delivered > 0, then m_dot >= 0.1 kg/s
            # This is a soft constraint to avoid numerical issues
            # Can be refined with indicator constraints in Phase 2
            return m_dot[t] >= 0.0  # Placeholder

        # Skip for now - handle in Phase 2 with better logic

        # ============================================================
        # HYDRAULIC CONSTRAINTS - PRESSURE DROP MODELING
        # ============================================================
        # Implements Darcy-Weisbach pressure drop calculation for
        # realistic hydraulic analysis required by grid operators

        # Get hydraulic parameters
        max_velocity = config.get('max_velocity_m_s', 2.5)  # Default 2.5 m/s
        max_pressure_drop = config.get('max_pressure_drop_bar', 2.0)  # Max ΔP per pipe
        pipe_roughness = config.get('pipe_roughness_mm', 0.05)  # Surface roughness (steel: 0.05mm)

        # Fluid properties
        mu_water = 0.0004  # Dynamic viscosity at 80°C [Pa·s]

        # Pipe-specific max flow limit (if defined)
        pipe_max_flow = config.get('max_flow_kg_s', None)

        import math
        pi = math.pi

        # Calculate pipe geometry
        if current_diam_supply:
            # Inner diameter (DN pipes: inner ≈ 94% of nominal)
            d_inner_m = current_diam_supply / 1000.0 * 0.94  # Convert mm to m
            d_inner_mm = current_diam_supply * 0.94

            # Cross-sectional area
            area_m2 = pi * (d_inner_m / 2.0) ** 2

            # Max flow for given velocity
            v_max_calculated = area_m2 * max_velocity * density_water  # kg/s

            # Use either calculated or specified limit
            if pipe_max_flow:
                effective_max_flow = min(pipe_max_flow, v_max_calculated)
            else:
                effective_max_flow = v_max_calculated
        else:
            # No diameter specified
            d_inner_m = 0.2  # Default 200mm
            d_inner_mm = 200.0
            area_m2 = pi * (d_inner_m / 2.0) ** 2
            effective_max_flow = pipe_max_flow if pipe_max_flow else 500.0

        # Update variable bounds with pipe-specific limit
        for t in time_set:
            m_dot[t].setub(effective_max_flow)

        logger.info(f"Pipe {pipe_id}: max flow = {effective_max_flow:.2f} kg/s "
                   f"(v_max={max_velocity} m/s, D={current_diam_supply or 'unspec'} mm)")

        # ============================================================
        # PRESSURE DROP VARIABLES
        # ============================================================

        # Velocity in pipe [m/s]
        velocity = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, max_velocity * 1.5))
        setattr(model, f'{prefix}_velocity', velocity)

        # Pressure drop in supply pipe [bar]
        delta_p_supply = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, max_pressure_drop * 2))
        setattr(model, f'{prefix}_delta_p_supply', delta_p_supply)

        # Pressure drop in return pipe [bar]
        delta_p_return = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, max_pressure_drop * 2))
        setattr(model, f'{prefix}_delta_p_return', delta_p_return)

        # Total pressure drop for this pipe pair [bar]
        delta_p_total = pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, max_pressure_drop * 4))
        setattr(model, f'{prefix}_delta_p_total', delta_p_total)

        # ============================================================
        # PRESSURE DROP CONSTRAINTS
        # ============================================================

        # (8) Velocity calculation: v = m_dot / (ρ * A)
        def velocity_rule(m, t):
            # v = m_dot / (density * area)
            # To avoid division, use: v * density * area = m_dot
            return velocity[t] * density_water * area_m2 == m_dot[t]

        setattr(model, f'{prefix}_velocity_calc',
                pyo.Constraint(time_set, rule=velocity_rule))

        # (9) Pressure drop calculation (Darcy-Weisbach with linearized friction)
        # ΔP = f * (L/D) * (ρ * v² / 2)
        #
        # For district heating (turbulent flow, Re > 4000):
        # Using Swamee-Jain approximation for friction factor:
        # f ≈ 0.25 / [log10(ε/3.7D + 5.74/Re^0.9)]²
        #
        # For typical DH conditions (Re ≈ 50000-500000), f ≈ 0.015-0.025
        # We use a linearized approximation for MILP compatibility:
        # ΔP ≈ k * L * v^1.85  (empirical Hazen-Williams style)
        #
        # For pure quadratic (more accurate but requires QP solver):
        # ΔP = f * (L/D) * (ρ/2) * v² / 100000 [bar]

        # Friction coefficient (typical for DH steel pipes)
        f_friction = config.get('friction_factor', 0.02)

        # Pressure drop coefficient: k = f * (L/D) * (ρ/2) / 100000
        # Units: [bar] when v in [m/s]
        k_pressure = f_friction * (length_m / d_inner_m) * (density_water / 2.0) / 100000.0

        # Linearized pressure drop (piecewise or conservative linear bound)
        # For MILP, we use: ΔP ≤ k * v_max * v (linear upper bound)
        # This is conservative but MILP-compatible

        brownfield_mode = config.get('brownfield_mode', False)
        use_pwl_pressure = config.get('use_pwl_pressure', True)  # Piecewise-linear by default

        if brownfield_mode:
            if use_pwl_pressure and effective_max_flow > 0:
                # ============================================================
                # PIECEWISE-LINEAR PRESSURE DROP (MILP-Compatible, More Accurate)
                # ============================================================
                # Real: ΔP = k * v² ∝ m_dot²
                # PWL approximation with 3 segments for better accuracy:
                #   Segment 1: 0-30% flow (low flow regime)
                #   Segment 2: 30-70% flow (typical operation)
                #   Segment 3: 70-100% flow (high flow regime)
                #
                # Each segment linearized at its midpoint:
                #   ΔP_segment = k_i * (m_dot - m_dot_i_start) + ΔP_i_start
                #
                # This reduces error from ~50% (single linear) to ~10% (PWL)
                # ============================================================

                # Flow breakpoints (fraction of max flow)
                bp_fractions = [0.0, 0.3, 0.7, 1.0]
                bp_flows = [f * effective_max_flow for f in bp_fractions]

                # Calculate quadratic ΔP at each breakpoint
                # ΔP = k_pressure * v², where v = m_dot / (density * area)
                v_at_max = effective_max_flow / (density_water * area_m2) if area_m2 > 0 else max_velocity
                k_flow_to_dp = k_pressure / ((density_water * area_m2) ** 2) if area_m2 > 0 else 0

                bp_dp = [k_flow_to_dp * (f * effective_max_flow) ** 2 for f in bp_fractions]

                # Linear slopes for each segment (dΔP/dm_dot at segment midpoint)
                # Derivative of ΔP = k * m_dot² is dΔP/dm_dot = 2 * k * m_dot
                slopes = []
                for i in range(3):
                    mid_flow = (bp_flows[i] + bp_flows[i + 1]) / 2
                    slope = 2 * k_flow_to_dp * mid_flow  # Tangent at midpoint
                    slopes.append(slope)

                # Store for logging
                pipe_pwl_info = {
                    'breakpoints': bp_flows,
                    'dp_at_bp': bp_dp,
                    'slopes': slopes,
                }

                logger.debug(f"Pipe {pipe_id} PWL pressure drop:")
                logger.debug(f"  Breakpoints (kg/s): {[f'{x:.2f}' for x in bp_flows]}")
                logger.debug(f"  ΔP at breakpoints (bar): {[f'{x:.4f}' for x in bp_dp]}")
                logger.debug(f"  Segment slopes: {[f'{x:.6f}' for x in slopes]}")

                # Binary variables for segment selection (exactly one active)
                pwl_seg = pyo.Var(time_set, range(3), domain=pyo.Binary)
                setattr(model, f'{prefix}_pwl_segment', pwl_seg)

                # Continuous auxiliary for flow within segment
                pwl_flow = pyo.Var(time_set, range(3), domain=pyo.NonNegativeReals)
                setattr(model, f'{prefix}_pwl_flow', pwl_flow)

                # Constraint: Exactly one segment active per timestep
                def one_segment_rule(m, t):
                    return sum(pwl_seg[t, s] for s in range(3)) == 1
                setattr(model, f'{prefix}_pwl_one_segment',
                        pyo.Constraint(time_set, rule=one_segment_rule))

                # Constraint: Flow equals sum of segment flows
                def flow_sum_rule(m, t):
                    return m_dot[t] == sum(pwl_flow[t, s] for s in range(3))
                setattr(model, f'{prefix}_pwl_flow_sum',
                        pyo.Constraint(time_set, rule=flow_sum_rule))

                # Constraint: Segment flow bounds (big-M formulation)
                M_flow = effective_max_flow * 1.1

                def seg_flow_lb_rule(m, t, s):
                    return pwl_flow[t, s] >= bp_flows[s] * pwl_seg[t, s]
                setattr(model, f'{prefix}_pwl_seg_lb',
                        pyo.Constraint(time_set, range(3), rule=seg_flow_lb_rule))

                def seg_flow_ub_rule(m, t, s):
                    return pwl_flow[t, s] <= bp_flows[s + 1] * pwl_seg[t, s] + M_flow * (1 - pwl_seg[t, s])
                setattr(model, f'{prefix}_pwl_seg_ub',
                        pyo.Constraint(time_set, range(3), rule=seg_flow_ub_rule))

                # PWL pressure drop constraint
                # ΔP = Σ_s [ΔP_at_start_s + slope_s * (flow_s - bp_start_s)] * seg_s
                # Simplified: ΔP = Σ_s [slope_s * flow_s + (ΔP_start_s - slope_s * bp_start_s) * seg_s]
                intercepts = [bp_dp[s] - slopes[s] * bp_flows[s] for s in range(3)]

                def pwl_pressure_drop_supply_rule(m, t):
                    return delta_p_supply[t] == sum(
                        slopes[s] * pwl_flow[t, s] + intercepts[s] * pwl_seg[t, s]
                        for s in range(3)
                    )

                def pwl_pressure_drop_return_rule(m, t):
                    return delta_p_return[t] == sum(
                        slopes[s] * pwl_flow[t, s] + intercepts[s] * pwl_seg[t, s]
                        for s in range(3)
                    )

                setattr(model, f'{prefix}_pressure_drop_supply',
                        pyo.Constraint(time_set, rule=pwl_pressure_drop_supply_rule))
                setattr(model, f'{prefix}_pressure_drop_return',
                        pyo.Constraint(time_set, rule=pwl_pressure_drop_return_rule))

            else:
                # Simple linear approximation (original brownfield behavior)
                # ΔP ≈ k_linear * m_dot
                # Calibrated at max flow: k_linear = k_pressure * v_max² / m_dot_max
                k_linear = k_pressure * max_velocity * max_velocity / effective_max_flow if effective_max_flow > 0 else 0

                def pressure_drop_supply_rule(m, t):
                    return delta_p_supply[t] == k_linear * m_dot[t]

                def pressure_drop_return_rule(m, t):
                    return delta_p_return[t] == k_linear * m_dot[t]

                setattr(model, f'{prefix}_pressure_drop_supply',
                        pyo.Constraint(time_set, rule=pressure_drop_supply_rule))
                setattr(model, f'{prefix}_pressure_drop_return',
                        pyo.Constraint(time_set, rule=pressure_drop_return_rule))
        else:
            # Quadratic pressure drop (requires QP/MIQP solver like Gurobi)
            def pressure_drop_supply_rule(m, t):
                # Darcy-Weisbach: ΔP = k * v²
                return delta_p_supply[t] == k_pressure * velocity[t] * velocity[t]

            def pressure_drop_return_rule(m, t):
                return delta_p_return[t] == k_pressure * velocity[t] * velocity[t]

        setattr(model, f'{prefix}_pressure_drop_supply',
                pyo.Constraint(time_set, rule=pressure_drop_supply_rule))

        setattr(model, f'{prefix}_pressure_drop_return',
                pyo.Constraint(time_set, rule=pressure_drop_return_rule))

        # (10) Total pressure drop = supply + return
        def total_pressure_drop_rule(m, t):
            return delta_p_total[t] == delta_p_supply[t] + delta_p_return[t]

        setattr(model, f'{prefix}_pressure_drop_total',
                pyo.Constraint(time_set, rule=total_pressure_drop_rule))

        # Store pressure parameters for reporting
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

        # Store for results extraction
        setattr(model, f'{prefix}_pressure_params', pressure_params)

        # ============================================================
        # COST CALCULATION
        # ============================================================

        capex_expr = 0

        if upgrade_enabled:
            diameter_choice = getattr(model, f'{prefix}_diameter_choice')
            insulation_choice = getattr(model, f'{prefix}_insulation_choice')

            # CAPEX depends on diameter and insulation choices
            # Base cost: existing pipe
            # Upgrade cost: additional cost if changing

            if existing_pipe:
                # Cost only if upgrading
                upgrade_cost_per_m = upgrade_config.get('upgrade_cost_eur_per_m', 200)

                # If changing diameter or insulation, pay upgrade cost
                # For simplicity: pay full upgrade cost for any change
                # More sophisticated: only charge if actually changing

                # Define upgrade indicator
                setattr(model, f'{prefix}_upgrade_indicator',
                        pyo.Var(domain=pyo.Binary))
                upgrade_ind = getattr(model, f'{prefix}_upgrade_indicator')

                # Upgrade indicator = 1 if NOT choosing current config
                current_diam_mm = config.get('current_diameter_supply_mm')
                current_insul = config.get('insulation_type', 'standard')

                # If current choice, upgrade_ind = 0; else = 1
                # This requires constraints to link choices to indicator
                # For Phase 1 simplification: assume upgrade cost applies to all choices

                capex_expr = upgrade_ind * upgrade_cost_per_m * length_m

                # Link upgrade indicator to choices (simplified)
                # upgrade_ind >= 1 - diameter_choice[current_diam_mm] (if current in options)
                if current_diam_mm in diameter_options:
                    def upgrade_link_rule(m):
                        return upgrade_ind >= 1 - diameter_choice[current_diam_mm]

                    setattr(model, f'{prefix}_upgrade_link',
                            pyo.Constraint(rule=upgrade_link_rule))
                else:
                    # Always upgrading (current not in options)
                    upgrade_ind.fix(1)

            else:
                # New pipe: pay full construction cost
                for d_mm in diameter_options:
                    dn_label = f"DN{d_mm}"
                    if dn_label in pipe_catalog:
                        cost_per_m = pipe_catalog[dn_label].get('capex_eur_per_m', 1000)
                        capex_expr += diameter_choice[d_mm] * cost_per_m * length_m
                    else:
                        # Default cost estimate
                        cost_per_m = 500 + d_mm * 3  # Rough estimate
                        capex_expr += diameter_choice[d_mm] * cost_per_m * length_m

        # Annualize CAPEX
        lifetime_years = config.get('lifetime_years', 40)
        period_years = getattr(model, 'period_years', 1.0)
        annualization = period_years / lifetime_years

        annual_capex = capex_expr * annualization

        # Store in model
        if not hasattr(model, 'pipe_capex_costs'):
            model.pipe_capex_costs = {}
        model.pipe_capex_costs[pipe_id] = annual_capex

        # Store heat loss penalty in objective (OPEX)
        # Heat losses valued at marginal generation cost
        # Will be added to objective in system_builder

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
            'capex': annual_capex,
            'existing': existing_pipe,
            'upgrade_enabled': upgrade_enabled
        }

    @staticmethod
    def get_results(model, time_set, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract results from solved model."""
        pipe_id = config.get('id') or config.get('pipe_id')
        prefix = pipe_id.upper().replace('-', '_')

        # Retrieve variables
        m_dot = getattr(model, f'{prefix}_m_dot')
        T_supply_in = getattr(model, f'{prefix}_T_supply_in')
        T_supply_out = getattr(model, f'{prefix}_T_supply_out')
        T_return_in = getattr(model, f'{prefix}_T_return_in')
        T_return_out = getattr(model, f'{prefix}_T_return_out')
        Q_loss_supply = getattr(model, f'{prefix}_Q_loss_supply')
        Q_loss_return = getattr(model, f'{prefix}_Q_loss_return')
        Q_delivered = getattr(model, f'{prefix}_Q_delivered')

        # Extract time series (with error handling)
        def safe_value(var, t, default=0.0):
            """Safely get value, return default if uninitialized."""
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
        # Q_loss is stored in MW internally, convert to kW for dashboard/export
        q_loss_supply_series_kw = [safe_value(Q_loss_supply, t, 0.0) * 1000 for t in time_set]
        q_loss_return_series_kw = [safe_value(Q_loss_return, t, 0.0) * 1000 for t in time_set]
        q_delivered_series = [safe_value(Q_delivered, t, 0.0) for t in time_set]

        # Extract hydraulic results (pressure drop, velocity)
        velocity_var = getattr(model, f'{prefix}_velocity', None)
        delta_p_supply_var = getattr(model, f'{prefix}_delta_p_supply', None)
        delta_p_return_var = getattr(model, f'{prefix}_delta_p_return', None)
        delta_p_total_var = getattr(model, f'{prefix}_delta_p_total', None)

        velocity_series = [safe_value(velocity_var, t, 0.0) for t in time_set] if velocity_var else []
        delta_p_supply_series = [safe_value(delta_p_supply_var, t, 0.0) for t in time_set] if delta_p_supply_var else []
        delta_p_return_series = [safe_value(delta_p_return_var, t, 0.0) for t in time_set] if delta_p_return_var else []
        delta_p_total_series = [safe_value(delta_p_total_var, t, 0.0) for t in time_set] if delta_p_total_var else []

        # Get pressure parameters
        pressure_params = getattr(model, f'{prefix}_pressure_params', {})

        # Calculate totals
        dt_h = getattr(model, 'dt_h', 1.0)
        total_heat_delivered_mwh = sum(q_delivered_series) * dt_h
        # Convert kW to MWh: kW * h / 1000 = MWh
        total_heat_loss_supply_mwh = sum(q_loss_supply_series_kw) * dt_h / 1000
        total_heat_loss_return_mwh = sum(q_loss_return_series_kw) * dt_h / 1000
        total_heat_loss_mwh = total_heat_loss_supply_mwh + total_heat_loss_return_mwh

        # Loss percentage
        if total_heat_delivered_mwh > 0:
            loss_percentage = (total_heat_loss_mwh / total_heat_delivered_mwh) * 100
        else:
            loss_percentage = 0.0

        # Investment results (if applicable)
        upgrade_config = config.get('upgrade_options', {})
        upgrade_enabled = upgrade_config.get('enabled', False)

        selected_diameter = None
        selected_insulation = None

        if upgrade_enabled:
            diameter_choice = getattr(model, f'{prefix}_diameter_choice')
            insulation_choice = getattr(model, f'{prefix}_insulation_choice')

            diameter_options = upgrade_config.get('diameter_options', [])
            insulation_options = upgrade_config.get('insulation_options', ['standard'])

            for d in diameter_options:
                if pyo.value(diameter_choice[d]) > 0.5:
                    selected_diameter = d
                    break

            for i in insulation_options:
                if pyo.value(insulation_choice[i]) > 0.5:
                    selected_insulation = i
                    break

        return {
            'pipe_id': pipe_id,
            'from_node': config['from_node'],
            'to_node': config['to_node'],
            'length_m': config['length_m'],

            # Time series - thermal
            'flow_kg_s': flow_series,
            'T_supply_in_c': t_supply_in_series,
            'T_supply_out_c': t_supply_out_series,
            'T_return_in_c': t_return_in_series,
            'T_return_out_c': t_return_out_series,
            'Q_loss_supply_kw': q_loss_supply_series_kw,  # kW for dashboard
            'Q_loss_return_kw': q_loss_return_series_kw,  # kW for dashboard
            'Q_delivered_mw': q_delivered_series,

            # Time series - hydraulic
            'velocity_m_s': velocity_series,
            'delta_p_supply_bar': delta_p_supply_series,
            'delta_p_return_bar': delta_p_return_series,
            'delta_p_total_bar': delta_p_total_series,

            # Aggregates - thermal
            'total_heat_delivered_mwh': total_heat_delivered_mwh,
            'total_heat_loss_mwh': total_heat_loss_mwh,
            'total_heat_loss_supply_mwh': total_heat_loss_supply_mwh,
            'total_heat_loss_return_mwh': total_heat_loss_return_mwh,
            'loss_percentage': loss_percentage,

            # Aggregates - hydraulic
            'max_velocity_m_s': max(velocity_series) if velocity_series else 0,
            'avg_velocity_m_s': sum(velocity_series) / len(velocity_series) if velocity_series else 0,
            'max_delta_p_total_bar': max(delta_p_total_series) if delta_p_total_series else 0,
            'avg_delta_p_total_bar': sum(delta_p_total_series) / len(delta_p_total_series) if delta_p_total_series else 0,

            # Averages - thermal
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
            'upgrade_recommended': selected_diameter != config.get('current_diameter_supply_mm') if selected_diameter else False,
        }
