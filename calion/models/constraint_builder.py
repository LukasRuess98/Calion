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

        # Pipe thermal mass buffer (positive = charging pipes, negative = discharging)
        buf_term = m.Q_net_buf[t] if hasattr(m, 'Q_net_buf') else 0

        # Balance: supply = demand + dump + storage_charge + network_losses + pipe_buffer
        return supply == demand + dump + storage_charge + network_loss + buf_term

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
        nid for nid, nc in unified_config.nodes.items() if nc.type in ("producer", "mixed")
    ]
    _cfg_primary = getattr(unified_config, 'primary_producer', None)
    if _cfg_primary and _cfg_primary in producer_node_ids:
        primary_producer_id = _cfg_primary
        logger.info("[CONSTRAINT] Primary producer set from config: %s", primary_producer_id)
    elif _cfg_primary:
        logger.warning(
            "[CONSTRAINT] primary_producer '%s' not found in producer nodes %s, falling back to first",
            _cfg_primary, producer_node_ids,
        )
        primary_producer_id = producer_node_ids[0] if producer_node_ids else None
    else:
        primary_producer_id = producer_node_ids[0] if producer_node_ids else None

    # Pre-collect consumer demand params for the primary producer balance.
    # Rules:
    #   - Pure consumer nodes: always included (their demand is served by pipes from j_1;
    #     demand_heat_rule in network_manager forces Q_pipe == Q_demand, so we can use
    #     Q_demand as a proxy for the pipe delivery in j_1's balance)
    #   - Primary mixed producer: included (e.g. single-node L1 where j_1 IS the only
    #     node — its Q_demand is also its local consumption)
    #   - Secondary mixed nodes (non-primary producers with local generators + demand):
    #     EXCLUDED from demand params.  For these nodes the pipe from j_1 carries a
    #     variable amount of supplemental heat (Q_consumer, not = Q_demand), so we add
    #     the pipe's Q_consumer variable directly to j_1's balance instead (see
    #     _secondary_mixed_q_pipes below).  This keeps the global energy balance closed:
    #       j_1: supply == Σ_consumer_D + Σ_secondary_Q_pipe + losses + dump + charge
    #       j_5: Q_gen_j5 + Q_pipe_j5 == D_j5 + dump_j5
    #       Sum: total_gen == total_D + losses + total_dump + charge  ✓
    # Precompute which nodes have outgoing pipes (needed to distinguish terminal vs passthrough)
    _nodes_with_outgoing = set()
    if unified_config is not None:
        for pipe_cfg in unified_config.pipes.values():
            _nodes_with_outgoing.add(pipe_cfg.from_node)

    _all_consumer_demand_nodes = []
    _secondary_mixed_q_pipes = []   # Q_consumer vars for pipes into TERMINAL secondary mixed nodes

    def _node_effective_demand(m, node_id, t):
        """Return node demand net of optional feasibility slack."""
        pfx = node_id.upper().replace('-', '_')
        q = getattr(m, f'{pfx}_Q_demand', None)
        if q is None:
            q = getattr(m, f'heatd_{node_id}', None)
        if q is None:
            return 0
        slack = getattr(m, f'{pfx}_Q_demand_slack', None)
        if slack is None:
            return q[t]
        return q[t] - slack[t]

    if unified_config is not None:
        for cnid, cnode in unified_config.nodes.items():
            is_consumer = cnode.type == 'consumer'
            is_primary_mixed = cnode.type == 'mixed' and cnid == primary_producer_id
            if is_consumer or is_primary_mixed:
                _all_consumer_demand_nodes.append(cnid)
            elif cnode.type == 'mixed' and cnid != primary_producer_id:
                is_terminal = cnid not in _nodes_with_outgoing
                if is_terminal:
                    # Terminal secondary mixed node (e.g. j_5 in L2):
                    # Its demand is handled by its own combined balance
                    # (local_gen + Q_pipe_in = demand + dump), so we use the pipe's
                    # Q_consumer variable in j_1's balance instead of Q_demand.
                    # This avoids double-counting while keeping the global energy balance:
                    #   j_1: supply = Σ_consumer_D + Q_consumer_j5 + losses + dump + C
                    #   j_5: Q_gen_j5 + Q_consumer_j5 = D_j5 + dump_j5
                    #   Sum: total_gen = total_D + losses + total_dump + C  ✓
                    for pipe_id, pipe_cfg in unified_config.pipes.items():
                        if pipe_cfg.to_node == cnid:
                            pipe_pfx = pipe_id.upper().replace('-', '_')
                            qp = getattr(model, f'{pipe_pfx}_Q_consumer',
                                         getattr(model, f'{pipe_pfx}_Q_delivered', None))
                            if qp is not None:
                                _secondary_mixed_q_pipes.append(qp)
                else:
                    # Non-terminal secondary mixed node (e.g. j_12 in L3):
                    # It passes heat downstream — keep its demand in the primary balance.
                    # Adding Q_consumer for its incoming pipe would double-count the
                    # downstream demands (j_13+j_14+j_15) that flow through it.
                    _all_consumer_demand_nodes.append(cnid)

    # ── Nodal balance for primary producer ───────────────────────────────────
    # Multi-producer networks (Stadtbach) require a nodal balance at j_hkw.
    # The old demand proxy (sum all consumer Q_demands) assumed j_hkw is the
    # sole producer and breaks when secondary producers (j_hws, j_hww, east arm)
    # serve part of the load — including backward flow through the bidirectional
    # hkw_to_ost pipe when east arm excess exceeds east demand.
    #
    # Fix: use Q_delivered (supply side) for every outgoing pipe from j_hkw.
    # Since Q_delivered = Q_consumer + pipe_loss, pipe losses are already embedded
    # and no separate network_loss term is needed.  For single-producer networks
    # (Memmingen) this is algebraically equivalent to the old approach.
    _bidi_signed_q_terms = []   # list of callables t → Pyomo expression [MW]

    if unified_config is not None and primary_producer_id is not None:
        # Nodal balance for primary producer: collect Q_delivered (supply side) for
        # every outgoing pipe.  Using supply-side quantities means pipe losses are
        # already included, so neither a demand proxy nor a network_loss term is needed.
        # For single-producer networks (Memmingen) this is equivalent to the old approach:
        #   sum(Q_del_all) = sum(Q_consumer + loss) = sum(D) + total_losses.
        _CP = 4.186  # kJ/(kg·K), same constant as pipe_pair.py

        def _make_signed_q_fn(m_dot_v, T_sup_p, T_ret_p, cp=_CP):
            def _signed_q(t):
                coeff = cp * (pyo.value(T_sup_p[t]) - pyo.value(T_ret_p[t])) / 1000
                return m_dot_v[t] * coeff
            return _signed_q

        for _out_pipe_id, _out_pipe_cfg in unified_config.pipes.items():
            if _out_pipe_cfg.from_node != primary_producer_id:
                continue
            _out_pfx = _out_pipe_id.upper().replace('-', '_')
            if _out_pipe_cfg.bidirectional:
                # Signed Q: positive = j_hkw sends forward; negative = receives backward
                _bidi_m_dot = getattr(model, f'{_out_pfx}_m_dot', None)
                _bidi_T_sup = getattr(model, f'{_out_pfx}_T_supply_in', None)
                _bidi_T_ret = getattr(model, f'{_out_pfx}_T_return_in', None)
                if _bidi_m_dot is None or _bidi_T_sup is None or _bidi_T_ret is None:
                    logger.warning(
                        "[CONSTRAINT] Bidi pipe %s: m_dot or T params not found — skipped",
                        _out_pipe_id,
                    )
                    continue
                _bidi_signed_q_terms.append(
                    _make_signed_q_fn(_bidi_m_dot, _bidi_T_sup, _bidi_T_ret)
                )
                logger.info("[CONSTRAINT] Nodal balance: bidi pipe %s signed-Q added", _out_pipe_id)
            else:
                _q_del = getattr(model, f'{_out_pfx}_Q_delivered', None)
                if _q_del is None:
                    logger.warning(
                        "[CONSTRAINT] Pipe %s: Q_delivered not found — skipped from nodal balance",
                        _out_pipe_id,
                    )
                    continue
                _bidi_signed_q_terms.append(lambda t, _qd=_q_del: _qd[t])
                logger.info("[CONSTRAINT] Nodal balance: pipe %s Q_delivered added", _out_pipe_id)

        if _bidi_signed_q_terms:
            # Nodal approach covers all outgoing pipes — demand proxy and secondary
            # mixed pipe lists are no longer needed in primary balance.
            _all_consumer_demand_nodes = []
            _secondary_mixed_q_pipes = []
            logger.info(
                "[CONSTRAINT] Primary producer %s: nodal balance with %d outgoing pipe terms",
                primary_producer_id, len(_bidi_signed_q_terms),
            )
        else:
            logger.warning(
                "[CONSTRAINT] Primary producer %s: no outgoing pipe Q_delivered found — "
                "falling back to demand proxy", primary_producer_id,
            )

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

        if node_cfg.type in ("producer", "mixed"):
            # Primary producer accounts for ALL consumer demands + network losses.
            # Secondary producers (e.g. heat pump at a junction) only balance their
            # own local demand (if any) — the pipe network propagates their output.
            if _is_primary:
                consumer_demand_nodes = _all_consumer_demand_nodes
                secondary_q_pipes = _secondary_mixed_q_pipes

                def primary_producer_balance(
                    m, t, _out=ht_out, _in=ht_in, _d=dump_var,
                    _qc=consumer_demand_nodes, _qp=secondary_q_pipes,
                    _bidi=_bidi_signed_q_terms
                ):
                    supply = sum((f[t] for f in _out), start=0)
                    charge = sum((f[t] for f in _in), start=0)
                    # Nodal balance: _bidi contains Q_delivered (supply side) for all
                    # outgoing pipes, so losses are already embedded — no network_loss term.
                    # _qc and _qp are empty when nodal balance is active (multi-producer).
                    # Legacy fallback: if nodal balance failed, _qc/_qp remain populated
                    # and network_loss is still required.
                    network_loss = 0
                    if _qc or _qp:
                        if hasattr(m, 'network_Q_loss_per_timestep'):
                            network_loss = m.network_Q_loss_per_timestep[t]
                    return supply == (_d[t] + charge + network_loss
                                      + sum(_node_effective_demand(m, nid, t) for nid in _qc)
                                      + sum(qp[t] for qp in _qp)
                                      + sum(f(t) for f in _bidi))

                setattr(model, f"ht_balance_{node_id}",
                        pyo.Constraint(model.t, rule=primary_producer_balance))
            else:
                # Secondary producer: balance against own local demand (if any).
                # For mixed nodes that also receive network heat via an incoming pipe,
                # the pipe delivery supplements local generation:
                #   local_gen + Q_pipe_in == demand + dump + charge
                # This replaces the old "supply == demand + dump" which double-counted
                # demand when the primary balance already required j_1 to cover it.
                has_local_demand = (
                    (node_cfg.demand is not None or node_cfg.demands)
                    and hasattr(model, f"heatd_{node_id}")
                )

                # Find incoming pipe's Q_consumer variable (first incoming pipe in tree)
                q_pipe_in = None
                if unified_config is not None:
                    for pipe_id, pipe_cfg in unified_config.pipes.items():
                        if pipe_cfg.to_node == node_id:
                            pipe_pfx = pipe_id.upper().replace('-', '_')
                            q_pipe_in = getattr(
                                model, f'{pipe_pfx}_Q_consumer',
                                getattr(model, f'{pipe_pfx}_Q_delivered', None)
                            )
                            break  # use first (typically only) incoming pipe

                # Collect outgoing pipes' Q_delivered variables.
                # For non-terminal nodes (e.g. j_12 in L3) the heat balance must include
                # the supply-side heat leaving into downstream pipes:
                #   Q_gen + Q_consumer_in = D_node + Q_delivered_out + dump + charge
                # For terminal nodes there are no outgoing pipes, so the sum is empty and
                # the constraint reduces to the standard combined balance.
                q_pipes_out: list = []
                if unified_config is not None:
                    for pipe_id, pipe_cfg in unified_config.pipes.items():
                        if pipe_cfg.from_node == node_id:
                            pipe_pfx = pipe_id.upper().replace('-', '_')
                            qd = getattr(model, f'{pipe_pfx}_Q_delivered', None)
                            if qd is not None:
                                q_pipes_out.append(qd)

                if has_local_demand:
                    demand_param = getattr(model, f"heatd_{node_id}")
                    demand_slack = getattr(
                        model, f"{node_id.upper().replace('-', '_')}_Q_demand_slack", None
                    )

                    if q_pipe_in is not None:
                        # Combined balance (works for both terminal and non-terminal):
                        #   local_gen + pipe_in = demand + Σ_out_delivered + dump + charge
                        # Terminal nodes: q_pipes_out is empty → reduces to the simple form.
                        # Non-terminal nodes: q_pipes_out accounts for downstream heat so
                        # the pass-through flow no longer inflates the dump term.
                        def secondary_combined_balance(
                            m, t, _out=ht_out, _in=ht_in, _d=dump_var,
                            _dem=demand_param, _dem_slack=demand_slack,
                            _qp=q_pipe_in, _qpo=q_pipes_out
                        ):
                            supply = sum((f[t] for f in _out), start=0)
                            charge = sum((f[t] for f in _in), start=0)
                            dem_t = _dem[t] - _dem_slack[t] if _dem_slack is not None else _dem[t]
                            return (supply + _qp[t]
                                    == dem_t + sum(qo[t] for qo in _qpo) + _d[t] + charge)

                        setattr(model, f"ht_balance_{node_id}",
                                pyo.Constraint(model.t, rule=secondary_combined_balance))
                        logger.info(
                            "[CONSTRAINT] Secondary mixed %s: combined balance "
                            "(local_gen + pipe_in = demand + %d downstream pipes + dump)",
                            node_id, len(q_pipes_out)
                        )
                    else:
                        # No incoming pipe (satellite plant): generators alone cover demand
                        def secondary_producer_balance(
                            m, t, _out=ht_out, _in=ht_in, _d=dump_var, _dem=demand_param
                        ):
                            supply = sum((f[t] for f in _out), start=0)
                            charge = sum((f[t] for f in _in), start=0)
                            if demand_slack is not None:
                                return supply == (_dem[t] - demand_slack[t]) + _d[t] + charge
                            return supply == _dem[t] + _d[t] + charge

                        setattr(model, f"ht_balance_{node_id}",
                                pyo.Constraint(model.t, rule=secondary_producer_balance))
                else:
                    if q_pipe_in is not None:
                        # No local demand but has incoming pipe:
                        #   gen + pipe_in = Σ_out_delivered + dump + charge
                        def secondary_no_demand_with_pipe(
                            m, t, _out=ht_out, _in=ht_in, _d=dump_var,
                            _qp=q_pipe_in, _qpo=q_pipes_out
                        ):
                            supply = sum((f[t] for f in _out), start=0)
                            charge = sum((f[t] for f in _in), start=0)
                            return (supply + _qp[t]
                                    == sum(qo[t] for qo in _qpo) + _d[t] + charge)

                        setattr(model, f"ht_balance_{node_id}",
                                pyo.Constraint(model.t, rule=secondary_no_demand_with_pipe))
                    else:
                        def secondary_producer_no_demand(
                            m, t, _out=ht_out, _in=ht_in, _d=dump_var,
                            _qpo=q_pipes_out
                        ):
                            supply = sum((f[t] for f in _out), start=0)
                            charge = sum((f[t] for f in _in), start=0)
                            return supply == sum(qo[t] for qo in _qpo) + _d[t] + charge

                        setattr(model, f"ht_balance_{node_id}",
                                pyo.Constraint(model.t, rule=secondary_producer_no_demand))

            logger.info("[CONSTRAINT] Producer/mixed %s: heat balance with %d sources, %d sinks",
                        node_id, len(ht_out), len(ht_in))

        elif node_cfg.type == "consumer":
            # Consumer nodes: demand is satisfied by incoming pipe flow + local assets
            if ht_out and hasattr(model, f"heatd_{node_id}"):
                # Consumer has local generation assets — create a combined balance:
                #   local_gen + pipe_in == demand + dump + storage_charge
                demand_param = getattr(model, f"heatd_{node_id}")
                demand_slack = getattr(
                    model, f"{node_id.upper().replace('-', '_')}_Q_demand_slack", None
                )

                # Find incoming pipe's Q_consumer variable
                q_pipe_in = None
                if unified_config is not None:
                    for pipe_id, pipe_cfg in unified_config.pipes.items():
                        if pipe_cfg.to_node == node_id:
                            pipe_pfx = pipe_id.upper().replace('-', '_')
                            q_pipe_in = getattr(
                                model, f'{pipe_pfx}_Q_consumer',
                                getattr(model, f'{pipe_pfx}_Q_delivered', None)
                            )
                            break

                def consumer_with_assets_balance(
                    m, t, _out=ht_out, _in=ht_in, _d=dump_var,
                    _dem=demand_param, _dem_slack=demand_slack, _qp=q_pipe_in
                ):
                    local_supply = sum((f[t] for f in _out), start=0)
                    charge = sum((f[t] for f in _in), start=0)
                    pipe_in = _qp[t] if _qp is not None else 0
                    dem_t = _dem[t] - _dem_slack[t] if _dem_slack is not None else _dem[t]
                    return local_supply + pipe_in == dem_t + _d[t] + charge

                setattr(model, f"ht_balance_{node_id}",
                        pyo.Constraint(model.t, rule=consumer_with_assets_balance))
                logger.info(
                    "[CONSTRAINT] Consumer %s: combined balance with %d local assets",
                    node_id, len(ht_out),
                )
            # else: pure consumer without local assets — demand handled by NetworkManager

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

    # Zonal peak demand tracking: all zones share the single grid connection's
    # peak (P_buy_peak), which is already constrained above. No per-zone Vars
    # needed until multi-node load flow is implemented.
    if hasattr(model, 'zone_demand_charge') and model.zone_demand_charge:
        logger.debug(
            "[CONSTRAINT-BUILDER] Zonal demand charges active: %s zones, using P_buy_peak",
            len(model.zone_demand_charge)
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
    return_anchor_cost=0,
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
            + return_anchor_cost
        ),
        sense=pyo.minimize,
    )
