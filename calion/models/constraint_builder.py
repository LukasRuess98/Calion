"""Constraint builders for optimization models.

This module provides functions to add common constraints to Pyomo models.
Extracted from system_builder.py for better modularity and reusability.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover
    HAVE_PYOMO = False
    pyo = None

from calion.logging_config import get_logger

logger = get_logger(__name__)


def _add_electricity_balance(model, el_in, el_out):
    """Add electricity bus balance constraint only (used in multi-node mode)."""
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for constraint building")

    model.el_balance = pyo.Constraint(
        model.t,
        rule=lambda m, t: (
            m.P_buy[t] + sum((f[t] for f in el_out), start=0) ==
            sum((f[t] for f in el_in), start=0) + m.P_sell[t]
        ),
    )


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
    _add_electricity_balance(model, el_in, el_out)

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


def add_per_node_heat_balance(model, system_buses, unified_config):
    """Add per-node heat balance constraints for multi-node networks.

    For each node:
    - Producer nodes: sum(ht_out[t]) feeds into outgoing pipe flows
    - Consumer nodes: incoming pipe delivers heat to meet demand + local assets
    - Junction nodes: flow balance handled by NetworkManager

    The per-node heat balances interact with pipe flow variables created by
    NetworkManager.  In this implementation we create per-node dump variables
    and per-node supply-demand constraints.

    For the global heat balance (needed for objective dump cost), we create
    a global Q_dump that is the sum of per-node dumps.

    Args:
        model: Pyomo ConcreteModel (must have network attached)
        system_buses: SystemBusConnections with per-node bus connections
        unified_config: UnifiedSystemConfig with node definitions
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for constraint building")

    # Create per-node dump variables
    for node_id in unified_config.nodes:
        dump_name = f"Q_dump_{node_id}"
        setattr(model, dump_name, pyo.Var(model.t, domain=pyo.NonNegativeReals))

    # Global Q_dump = sum of per-node dumps
    node_ids = list(unified_config.nodes.keys())

    def global_dump_rule(m, t):
        return m.Q_dump[t] == sum(
            getattr(m, f"Q_dump_{nid}")[t] for nid in node_ids
        )

    model.global_dump_balance = pyo.Constraint(model.t, rule=global_dump_rule)

    # Identify the primary producer (first in iteration order) to avoid double-counting
    # network losses and consumer demands when multiple producers exist.
    producer_node_ids = [
        nid for nid, nc in unified_config.nodes.items() if nc.type == "producer"
    ]
    primary_producer_id = producer_node_ids[0] if producer_node_ids else None

    # Pre-collect consumer demand params once (used by producer_no_demand logic)
    _all_consumer_demand_params = []
    if unified_config is not None:
        for cnid, cnode in unified_config.nodes.items():
            if cnode.type == 'consumer':
                attr = f'{cnid.upper().replace("-", "_")}_Q_demand'
                q = getattr(model, attr, None)
                if q is not None:
                    _all_consumer_demand_params.append(q)

    # Per-node heat balance constraints
    for node_id, node_cfg in unified_config.nodes.items():
        node_buses = system_buses.nodes.get(node_id)
        if node_buses is None:
            continue

        ht_out = node_buses.ht_out
        ht_in = node_buses.ht_in
        dump_var = getattr(model, f"Q_dump_{node_id}")
        # Only the primary producer carries the full network loss; secondary producers carry zero
        _is_primary = (node_id == primary_producer_id)

        if node_cfg.type == "producer":
            # Producer: sum(ht_out) == demand_at_node (if any) + dump + storage_charge + pipe_outflow
            # Pipe outflow is handled by NetworkManager constraints
            # If producer has demand, include it
            if node_cfg.demand is not None and hasattr(model, f"heatd_{node_id}"):
                demand_param = getattr(model, f"heatd_{node_id}")

                def producer_balance(m, t, _out=ht_out, _in=ht_in, _d=dump_var, _dem=demand_param,
                                     _primary=_is_primary):
                    supply = sum((f[t] for f in _out), start=0)
                    charge = sum((f[t] for f in _in), start=0)
                    network_loss = 0
                    if _primary and hasattr(m, 'network_Q_loss_per_timestep'):
                        network_loss = m.network_Q_loss_per_timestep[t]
                    return supply == _dem[t] + _d[t] + charge + network_loss

                setattr(model, f"ht_balance_{node_id}",
                        pyo.Constraint(model.t, rule=producer_balance))
            else:
                # Producer without demand: the primary producer also accounts for all consumer
                # demand delivered via the network; secondary producers only balance their own assets.
                consumer_demand_params = _all_consumer_demand_params if _is_primary else []

                def producer_no_demand(
                    m, t, _out=ht_out, _in=ht_in, _d=dump_var, _qc=consumer_demand_params,
                    _primary=_is_primary
                ):
                    supply = sum((f[t] for f in _out), start=0)
                    charge = sum((f[t] for f in _in), start=0)
                    network_loss = 0
                    if _primary and hasattr(m, 'network_Q_loss_per_timestep'):
                        network_loss = m.network_Q_loss_per_timestep[t]
                    consumer_demand = sum(q[t] for q in _qc)
                    return supply == _d[t] + charge + network_loss + consumer_demand

                setattr(model, f"ht_balance_{node_id}",
                        pyo.Constraint(model.t, rule=producer_no_demand))

            logger.info("[CONSTRAINT] Producer %s: heat balance with %d sources, %d sinks",
                        node_id, len(ht_out), len(ht_in))

        elif node_cfg.type == "consumer":
            # Consumer nodes: demand is satisfied by incoming pipe flow
            # Local assets (if any) contribute to the pipe flow balance
            # Consumer heat balance is handled by NetworkManager's
            # _link_consumer_demands() which connects pipe Q_consumer to Q_demand
            if ht_out:
                # Consumer has local assets — add their output to node demand satisfaction
                # The balance is: pipe_delivered + local_ht_out = demand + dump + local_storage_charge
                if hasattr(model, f"heatd_{node_id}"):
                    logger.info("[CONSTRAINT] Consumer %s: %d local assets contribute to demand",
                                node_id, len(ht_out))

        elif node_cfg.type == "junction":
            # Junction: flow balance handled by NetworkManager
            pass

    # Global heat balance for copperplate fallback or single-node special case
    # This ensures m.heatd is always satisfied at system level
    if not getattr(model, '_network_enabled', False):
        # No network: fall back to global balance
        all_ht_out = system_buses.all_ht_out
        all_ht_in = system_buses.all_ht_in

        def global_heat_rule(m, t):
            supply = sum((f[t] for f in all_ht_out), start=0)
            charge = sum((f[t] for f in all_ht_in), start=0)
            return supply == m.heatd[t] + m.Q_dump[t] + charge

        model.ht_balance = pyo.Constraint(model.t, rule=global_heat_rule)


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
    demand_slack_cost=0,
):
    """Create the cost minimization objective function."""
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for objective creation")

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
            + demand_slack_cost
        ),
        sense=pyo.minimize,
    )
