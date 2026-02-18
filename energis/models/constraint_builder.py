"""Constraint builders for optimization models.

This module provides functions to add common constraints to Pyomo models.
Extracted from system_builder.py for better modularity and reusability.
"""

from __future__ import annotations

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover
    HAVE_PYOMO = False
    pyo = None


def add_bus_balance_constraints(model, el_in, el_out, ht_in, ht_out):
    """Add electricity and heat bus balance constraints to the model.

    Args:
        model: Pyomo ConcreteModel
        el_in: List of electricity input variables (consumers)
        el_out: List of electricity output variables (generators)
        ht_in: List of heat input variables (storage charge)
        ht_out: List of heat output variables (generators)

    Constraints added:
        - model.el_balance: Electricity bus balance
        - model.ht_balance: Heat bus balance (includes network losses if present)
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for constraint building")

    # Electricity balance: Buy + Generation = Consumption + Sell
    model.el_balance = pyo.Constraint(
        model.t,
        rule=lambda m, t: (
            m.P_buy[t] + sum((f[t] for f in el_out), start=0) ==
            sum((f[t] for f in el_in), start=0) + m.P_sell[t]
        ),
    )

    # Heat balance: Supply = Demand + Dump + Storage Charge + Network Losses
    def heat_balance_rule(m, t):
        # Heat sources: generators, storage discharge
        supply = sum((f[t] for f in ht_out), start=0)

        # Heat sinks: storage charge
        storage_charge = sum((f[t] for f in ht_in), start=0)

        # Heat demand
        demand = m.heatd[t]
        dump = m.Q_dump[t]

        # Add network losses if thermal network is enabled
        if hasattr(m, 'network_Q_loss_per_timestep'):
            network_loss = m.network_Q_loss_per_timestep[t]
        else:
            network_loss = 0

        # Balance: supply = demand + dump + storage_charge + network_losses
        return supply == demand + dump + storage_charge + network_loss

    model.ht_balance = pyo.Constraint(model.t, rule=heat_balance_rule)


def add_grid_market_constraints(model):
    """Add grid buy/sell and peak demand constraints.

    Args:
        model: Pyomo ConcreteModel with grid variables (P_buy, P_sell, grid_mode, etc.)

    Constraints added:
        - model.buy_gate: Buy only when grid_mode = 1
        - model.sell_gate: Sell only when grid_mode = 0
        - model.buy_limit: Limit import to max_import
        - model.sell_limit: Limit export to max_export
        - model.peak_con: Track peak demand
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for constraint building")

    # Grid mode constraints: Can't buy and sell simultaneously
    model.buy_gate = pyo.Constraint(
        model.t,
        rule=lambda m, t: m.P_buy[t] <= m.grid_mode[t] * m.M_GRID
    )
    model.sell_gate = pyo.Constraint(
        model.t,
        rule=lambda m, t: m.P_sell[t] <= (1 - m.grid_mode[t]) * m.M_GRID
    )

    # Grid capacity limits
    model.buy_limit = pyo.Constraint(
        model.t,
        rule=lambda m, t: m.P_buy[t] <= m.max_import
    )
    model.sell_limit = pyo.Constraint(
        model.t,
        rule=lambda m, t: m.P_sell[t] <= m.max_export
    )

    # Peak demand tracking (for demand charges)
    if not hasattr(model, 'P_buy_peak'):
        model.P_buy_peak = pyo.Var(domain=pyo.NonNegativeReals)
    model.peak_con = pyo.Constraint(
        model.t,
        rule=lambda m, t: m.P_buy_peak >= m.P_buy[t]
    )


def create_objective(
    model,
    energy_cost,
    dump_cost,
    fuel_costs=0,
    co2_cost=0,
    demand_cost=0,
    capex_cost=0,
    activation_cost=0,
    tie_break_cost=0,
    storage_install_cost=0,
    terminal_value=0,
):
    """Create the cost minimization objective function.

    Args:
        model: Pyomo ConcreteModel
        energy_cost: Grid electricity purchase/sales costs
        dump_cost: Cost for dumping excess heat
        fuel_costs: Fuel consumption costs (gas, biomass, etc.)
        co2_cost: CO2 emission costs
        demand_cost: Peak demand charges
        capex_cost: Capital expenditure (annualized)
        activation_cost: Fixed costs for activating technologies
        tie_break_cost: Small costs to break ties in optimization
        storage_install_cost: Storage installation costs
        terminal_value: Terminal value for storage (can be negative = reward)

    Objective added:
        - model.obj: Total cost minimization
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for objective creation")

    # Store cost expressions on model for reporting.
    # Wrap each value in pyo.Expression so Pyomo adds a fresh component instead of
    # trying to re-register an existing variable under a different name.
    model.capex_cost_expr = pyo.Expression(expr=capex_cost)
    model.activation_cost_expr = pyo.Expression(expr=activation_cost)
    model.tie_break_cost_expr = pyo.Expression(expr=tie_break_cost)
    model.storage_install_cost_expr = pyo.Expression(expr=storage_install_cost)

    model.obj = pyo.Objective(
        expr=(
            energy_cost
            + dump_cost
            + fuel_costs
            + co2_cost
            + demand_cost
            + capex_cost
            + activation_cost
            + tie_break_cost
            + storage_install_cost
            + terminal_value
        ),
        sense=pyo.minimize,
    )
