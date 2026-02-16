"""Cost calculation utilities for optimization models.

This module provides functions to calculate various cost components:
- Energy costs (grid purchase/sales with dynamic pricing)
- CO2 emission costs (with heat/electricity breakdown)
- Fuel costs (gas, biomass, waste, oil)
- CAPEX (capital expenditure, annualized)
- Demand charges (peak demand pricing)

Extracted from system_builder.py for better modularity and testability.
"""

from __future__ import annotations

from typing import Dict, List, Any, Tuple

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover
    HAVE_PYOMO = False
    pyo = None


def calculate_energy_costs(
    model,
    time_steps,
    base_prices: List[float],
    dt_h: float = 1.0,
    include_grid_cost: bool = True,
) -> Any:
    """Calculate grid electricity purchase and sales costs.

    Args:
        model: Pyomo model with P_buy, P_sell variables and price parameters
        time_steps: List of timestep indices
        base_prices: Base electricity prices (EUR/MWh) for each timestep
        dt_h: Timestep duration in hours
        include_grid_cost: Whether to add grid fees to buy price

    Returns:
        Pyomo expression for total energy costs
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for cost calculation")

    # Calculate buy and sell prices
    buy_price = base_prices.copy()
    if include_grid_cost:
        energy_fee = float(model.energy_fee.value) if hasattr(model, 'energy_fee') else 0.0
        grid_cost = float(model.grid_cost.value) if hasattr(model, 'grid_cost') else 0.0
        addition = energy_fee + grid_cost
        buy_price = [bp + addition for bp in base_prices]

    # Sell price calculation (with haircut and spread)
    def _sell_price(bp: float) -> float:
        sell_floor = float(model.sell_floor.value) if hasattr(model, 'sell_floor') else 0.0
        sell_haircut = float(model.sell_haircut.value) if hasattr(model, 'sell_haircut') else 0.0
        sell_spread = float(model.sell_spread.value) if hasattr(model, 'sell_spread') else 0.0
        sell_fee = float(model.sell_fee.value) if hasattr(model, 'sell_fee') else 0.0

        price = bp * (1 - sell_haircut) - sell_spread - sell_fee
        return max(price, sell_floor)

    sell_price = [_sell_price(bp) for bp in base_prices]

    # Total energy cost = purchase - sales revenue
    energy_cost = sum(
        dt_h * (model.P_buy[t] * buy_price[idx] - model.P_sell[t] * sell_price[idx])
        for idx, t in enumerate(time_steps)
    )

    return energy_cost


def calculate_co2_costs(
    component_co2_terms: Dict[str, Dict[str, Any]],
    co2_price_eur_per_t: float,
) -> Tuple[Any, Any, Any]:
    """Calculate CO2 emission costs with heat/electricity breakdown.

    Args:
        component_co2_terms: Dict mapping component name to CO2 data:
            {'heat_kg': ..., 'elec_kg': ..., 'heat_eur': ..., 'elec_eur': ...}
        co2_price_eur_per_t: CO2 price in EUR/tonne

    Returns:
        Tuple of (total_cost, heat_cost, elec_cost) as Pyomo expressions
    """
    heat_cost_terms = []
    elec_cost_terms = []

    for comp_name, co2_data in component_co2_terms.items():
        heat_cost_terms.append(co2_data.get('heat_eur', 0))
        elec_cost_terms.append(co2_data.get('elec_eur', 0))

    heat_cost = sum(heat_cost_terms) if heat_cost_terms else 0
    elec_cost = sum(elec_cost_terms) if elec_cost_terms else 0
    total_cost = heat_cost + elec_cost

    return total_cost, heat_cost, elec_cost


def calculate_demand_charge(
    model,
    include_demand: bool = True,
) -> Any:
    """Calculate peak demand charge.

    Args:
        model: Pyomo model with P_buy_peak variable
        include_demand: Whether to include demand charges

    Returns:
        Pyomo expression for demand charge costs
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for cost calculation")

    if not include_demand:
        return 0

    if not hasattr(model, 'P_buy_peak'):
        return 0

    return model.demand_charge_y * model.year_frac * model.P_buy_peak


def calculate_investment_costs(
    capex_terms: List[Any],
    activation_terms: List[Any],
    tie_breaker_terms: List[Any],
    storage_install_terms: List[Any],
    include_capex: bool = True,
    include_activation: bool = True,
    include_tie_breaker: bool = True,
) -> Tuple[Any, Any, Any, Any]:
    """Calculate total investment costs.

    Args:
        capex_terms: List of CAPEX cost expressions
        activation_terms: List of activation cost expressions
        tie_breaker_terms: List of tie-breaker cost expressions
        storage_install_terms: List of storage installation cost expressions
        include_capex: Include CAPEX in total
        include_activation: Include activation costs in total
        include_tie_breaker: Include tie-breaker costs in total

    Returns:
        Tuple of (capex_total, activation_total, tie_break_total, storage_install_total)
    """
    capex = sum(capex_terms) if (capex_terms and include_capex) else 0
    activation = sum(activation_terms) if (activation_terms and include_activation) else 0
    tie_break = sum(tie_breaker_terms) if (tie_breaker_terms and include_tie_breaker) else 0
    storage_install = sum(storage_install_terms) if storage_install_terms else 0

    return capex, activation, tie_break, storage_install


def annualize_capex(
    capacity_mw: float,
    capex_eur_per_mw: float,
    lifetime_years: float,
    year_fraction: float = 1.0,
) -> float:
    """Annualize capital expenditure.

    Uses simplified annualization: CAPEX / lifetime * year_fraction

    Args:
        capacity_mw: Installed capacity (MW)
        capex_eur_per_mw: Capital cost per MW
        lifetime_years: Economic lifetime
        year_fraction: Fraction of year being optimized (e.g., 0.5 for 6 months)

    Returns:
        Annualized CAPEX for the optimization period
    """
    if lifetime_years <= 0:
        return 0.0

    annual_capex = (capacity_mw * capex_eur_per_mw) / lifetime_years
    return annual_capex * year_fraction


def calculate_fuel_costs(
    fuel_consumption_terms: List[Any],
) -> Any:
    """Calculate total fuel costs.

    Args:
        fuel_consumption_terms: List of fuel cost expressions (MWh * price/MWh)

    Returns:
        Total fuel costs
    """
    return sum(fuel_consumption_terms) if fuel_consumption_terms else 0


def calculate_dump_costs(
    model,
    time_steps,
    dt_h: float,
    dump_cost_eur_per_mwh: float,
) -> Any:
    """Calculate cost for dumping excess heat.

    Args:
        model: Pyomo model with Q_dump variable
        time_steps: List of timestep indices
        dt_h: Timestep duration in hours
        dump_cost_eur_per_mwh: Cost per MWh of dumped heat

    Returns:
        Total dump costs
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for cost calculation")

    return dump_cost_eur_per_mwh * sum(model.Q_dump[t] * dt_h for t in time_steps)


def store_cost_expressions_on_model(
    model,
    co2_cost_total,
    co2_cost_heat,
    co2_cost_elec,
    co2_kg_heat,
    co2_kg_elec,
    co2_kg_fuel_to_heat,
    co2_kg_fuel_to_elec,
    co2_kg_grid_to_elec,
):
    """Store cost and emission expressions on model for later extraction.

    Args:
        model: Pyomo model
        co2_cost_total: Total CO2 costs
        co2_cost_heat: CO2 costs from heat production
        co2_cost_elec: CO2 costs from electricity use
        co2_kg_heat: CO2 emissions from heat production (kg)
        co2_kg_elec: CO2 emissions from electricity use (kg)
        co2_kg_fuel_to_heat: Fuel → heat emissions (kg)
        co2_kg_fuel_to_elec: Fuel → electricity emissions (kg)
        co2_kg_grid_to_elec: Grid → electricity emissions (kg)
    """
    # Store cost expressions
    model.co2_cost_heat_expr = co2_cost_heat
    model.co2_cost_elec_expr = co2_cost_elec
    model.co2_cost_total_expr = co2_cost_total

    # Store emission quantities (kg)
    model.co2_kg_heat_expr = co2_kg_heat
    model.co2_kg_elec_expr = co2_kg_elec

    # Store dashboard categories
    model.co2_kg_fuel_to_heat_expr = co2_kg_fuel_to_heat
    model.co2_kg_fuel_to_elec_expr = co2_kg_fuel_to_elec
    model.co2_kg_grid_to_elec_expr = co2_kg_grid_to_elec


def aggregate_co2_emissions(
    component_co2_data: Dict[str, Dict[str, Any]]
) -> Tuple[Any, Any, Any, Any, Any]:
    """Aggregate CO2 emissions from all components.

    Args:
        component_co2_data: Dict mapping component name to CO2 data

    Returns:
        Tuple of (heat_kg, elec_kg, fuel_to_heat_kg, fuel_to_elec_kg, grid_to_elec_kg)
    """
    heat_terms = []
    elec_terms = []
    fuel_to_heat_terms = []
    fuel_to_elec_terms = []
    grid_to_elec_terms = []

    for comp_name, co2_data in component_co2_data.items():
        heat_terms.append(co2_data.get('heat_kg', 0))
        elec_terms.append(co2_data.get('elec_kg', 0))

        # Categorize by source
        comp_type = co2_data.get('type', 'unknown')
        if comp_type in ('heat_pump', 'p2h'):
            # Electric components: grid → electricity
            grid_to_elec_terms.append(co2_data.get('total_kg', 0))
        elif comp_type == 'thermal_generator':
            # Pure heat: fuel → heat
            fuel_to_heat_terms.append(co2_data.get('heat_kg', 0))
        elif comp_type == 'chp':
            # Combined: fuel → heat + electricity
            fuel_to_heat_terms.append(co2_data.get('heat_kg', 0))
            fuel_to_elec_terms.append(co2_data.get('elec_kg', 0))

    heat_kg = sum(heat_terms) if heat_terms else 0
    elec_kg = sum(elec_terms) if elec_terms else 0
    fuel_to_heat_kg = sum(fuel_to_heat_terms) if fuel_to_heat_terms else 0
    fuel_to_elec_kg = sum(fuel_to_elec_terms) if fuel_to_elec_terms else 0
    grid_to_elec_kg = sum(grid_to_elec_terms) if grid_to_elec_terms else 0

    return heat_kg, elec_kg, fuel_to_heat_kg, fuel_to_elec_kg, grid_to_elec_kg
