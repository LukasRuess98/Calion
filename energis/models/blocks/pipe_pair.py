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
import pyomo.environ as pyo
import logging

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

        # Supply pipe temperatures (°C)
        setattr(model, f'{prefix}_T_supply_in',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(70, 100)))
        setattr(model, f'{prefix}_T_supply_out',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(70, 100)))

        # Return pipe temperatures (°C)
        setattr(model, f'{prefix}_T_return_in',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(30, 70)))
        setattr(model, f'{prefix}_T_return_out',
                pyo.Var(time_set, domain=pyo.NonNegativeReals,
                       bounds=(30, 70)))

        # Heat losses (MW)
        setattr(model, f'{prefix}_Q_loss_supply',
                pyo.Var(time_set, domain=pyo.NonNegativeReals))
        setattr(model, f'{prefix}_Q_loss_return',
                pyo.Var(time_set, domain=pyo.NonNegativeReals))

        # Heat delivered (MW)
        setattr(model, f'{prefix}_Q_delivered',
                pyo.Var(time_set, domain=pyo.NonNegativeReals))

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
        # BROWNFIELD MODE: Fix temperatures to design values
        # ============================================================
        # This converts bilinear constraints (m_dot * T) to linear ones

        brownfield_mode = config.get('brownfield_mode', False)
        if brownfield_mode:
            logger.info(f"    {pipe_id}: Brownfield mode - fixing temperatures")
            # Assume small temperature drop in pipes (1°C supply, 1°C return)
            supply_temp_out = supply_temp_nominal_c - 1.0
            return_temp_out = return_temp_nominal_c - 1.0

            for t in time_set:
                T_supply_in[t].fix(supply_temp_nominal_c)
                T_supply_out[t].fix(supply_temp_out)
                T_return_in[t].fix(return_temp_nominal_c)
                T_return_out[t].fix(return_temp_out)

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
        # HYDRAULIC CONSTRAINTS
        # ============================================================

        # Get hydraulic parameters
        max_velocity = config.get('max_velocity_m_s', 2.5)  # Default 2.5 m/s
        max_pressure = config.get('max_pressure_bar', 16.0)  # Default PN16

        # Pipe-specific max flow limit (if defined)
        pipe_max_flow = config.get('max_flow_kg_s', None)

        # (8) Maximum flow constraint based on pipe diameter and velocity
        # V_dot_max = A * v_max = π * (D/2)² * v_max
        # m_dot_max = V_dot_max * ρ = π * (D/2)² * v_max * ρ

        import math
        pi = math.pi

        # Calculate max flow based on current diameter
        if current_diam_supply:
            # Inner diameter (assuming outer diameter given, subtract wall thickness)
            # For DN pipes, inner diameter is typically ~94% of nominal
            d_inner_m = current_diam_supply / 1000.0 * 0.94  # Convert mm to m

            # Max flow for given velocity
            area_m2 = pi * (d_inner_m / 2.0) ** 2
            v_max_calculated = area_m2 * max_velocity * density_water  # kg/s

            # Use either calculated or specified limit
            if pipe_max_flow:
                effective_max_flow = min(pipe_max_flow, v_max_calculated)
            else:
                effective_max_flow = v_max_calculated
        else:
            # No diameter specified, use pipe-specific or global limit
            effective_max_flow = pipe_max_flow if pipe_max_flow else 500.0

        # Update variable bounds with pipe-specific limit
        for t in time_set:
            m_dot[t].setub(effective_max_flow)

        logger.info(f"Pipe {pipe_id}: max flow = {effective_max_flow:.2f} kg/s (v_max={max_velocity} m/s, D={current_diam_supply or 'unspec'} mm)")

        # (9) Pressure drop constraint (simplified Darcy-Weisbach)
        # Δp = λ * (L/D) * (ρ * v²/2)
        # where λ is the friction factor (typically 0.02-0.03 for district heating)

        # For now, we store pressure parameters but don't add hard constraints
        # (pressure optimization requires pump modeling which is more complex)

        # Store pressure parameters for reporting
        pressure_params = {
            'max_pressure_bar': max_pressure,
            'max_velocity_m_s': max_velocity,
            'effective_max_flow_kg_s': effective_max_flow,
            'pipe_diameter_mm': current_diam_supply,
        }

        # (10) Optional: Explicit pressure drop calculation for reporting
        # This can be used for post-optimization analysis

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
        q_loss_supply_series = [safe_value(Q_loss_supply, t, 0.0) for t in time_set]
        q_loss_return_series = [safe_value(Q_loss_return, t, 0.0) for t in time_set]
        q_delivered_series = [safe_value(Q_delivered, t, 0.0) for t in time_set]

        # Calculate totals
        dt_h = getattr(model, 'dt_h', 1.0)
        total_heat_delivered_mwh = sum(q_delivered_series) * dt_h
        total_heat_loss_supply_mwh = sum(q_loss_supply_series) * dt_h
        total_heat_loss_return_mwh = sum(q_loss_return_series) * dt_h
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

            # Time series
            'flow_kg_s': flow_series,
            'T_supply_in_c': t_supply_in_series,
            'T_supply_out_c': t_supply_out_series,
            'T_return_in_c': t_return_in_series,
            'T_return_out_c': t_return_out_series,
            'Q_loss_supply_mw': q_loss_supply_series,
            'Q_loss_return_mw': q_loss_return_series,
            'Q_delivered_mw': q_delivered_series,

            # Aggregates
            'total_heat_delivered_mwh': total_heat_delivered_mwh,
            'total_heat_loss_mwh': total_heat_loss_mwh,
            'total_heat_loss_supply_mwh': total_heat_loss_supply_mwh,
            'total_heat_loss_return_mwh': total_heat_loss_return_mwh,
            'loss_percentage': loss_percentage,

            # Averages
            'avg_flow_kg_s': sum(flow_series) / len(flow_series) if flow_series else 0,
            'avg_supply_temp_in_c': sum(t_supply_in_series) / len(t_supply_in_series) if t_supply_in_series else 0,
            'avg_return_temp_out_c': sum(t_return_out_series) / len(t_return_out_series) if t_return_out_series else 0,

            # Investment results
            'selected_diameter_mm': selected_diameter,
            'selected_insulation': selected_insulation,
            'current_diameter_mm': config.get('current_diameter_supply_mm'),
            'upgrade_recommended': selected_diameter != config.get('current_diameter_supply_mm') if selected_diameter else False,
        }
