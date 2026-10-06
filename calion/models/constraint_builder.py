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
from .utils.mccormick import add_mccormick_constraints as _mccormick

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
    # 2026-09-22 (C3, "Notkuehler nach Ansatz B", author decision): the generic per-node valve
    # let ANY excess heat at ANY node (CHP, biomass, gas boiler, ...) dump for the flat
    # dump_cost_eur_per_mwh_th price, with no unit attribution. CALION_DUMP_MODE=chp_only fixes
    # every per-node dump Var to 0 here (structure kept, capability removed): the ONLY dump
    # outlet becomes the new per-CHP-asset Q_dump_chp_{ASSET} Var (component_assembler.py's
    # _attach_thermal_generator_from_unified), bounded by that unit's own thermal output/rated
    # capacity and netted OUT of its heat contribution before it ever reaches this node balance.
    # Biomass/gas-boiler/other assets must modulate or shut down via their existing UC (on/off)
    # instead -- if that is not sufficient, the model goes INFEASIBLE, which is the intended,
    # reportable signal (no silent slack, no reintroduced node-level dump).
    import os as _os_dm
    _dump_mode = _os_dm.environ.get('CALION_DUMP_MODE', 'legacy').strip().lower()
    _n_dump_vars_fixed = 0
    _closure_vars = []  # (node_id, Var) pairs eligible for the data-closure mechanism (M1: demand-bearing nodes only)
    for node_id in unified_config.nodes:
        dump_name = f"Q_dump_{node_id}"
        setattr(model, dump_name, pyo.Var(model.t, domain=pyo.NonNegativeReals))
    # 2026-09-27 (M1, author decision, docs SS4bh): the generic per-node closure valve
    # (introduced G3 to absorb a genuine passthrough-node residual, e.g. MM j_12) was
    # ALSO left open at CHP-hosting nodes -- since it is epsilon-priced (0.01 EUR/MWh, I1)
    # while the dedicated per-CHP emergency-cooler Q_dump_chp_{asset} (C3, "Ansatz B") is
    # priced at the real dump_cost (~5 EUR/MWh), the solver silently routed CHP curtailment
    # through the cheap valve instead of the real one -- SB's three CHP nodes alone show
    # 504+259+110 = 874 MWh this way (BC-SB-HK0), the same order of magnitude as the
    # already-documented D2 min-load pattern (784 MWh).
    #
    # 2026-09-27 CORRECTION (N1/N2, author decision, docs SS4bi): M1's first cut (a hard
    # "no node may have both mechanisms" assertion, and a flat 0.05%-of-own-demand per-node
    # cap for everything else) broke on two counts, both caught by a build-only test before
    # any solve: (a) Memmingen's j_9 genuinely hosts BOTH a CHP asset (chp_main) AND local
    # demand (V_15/V_16) -- a real, not a bug -- so "no node has both" is simply wrong; (b)
    # the flat 0.05%-of-own-demand cap was 6.5x-42x too tight even at cleanly-categorised,
    # non-controversial nodes (MM j_12, SB j_man) based on their OWN already-solved
    # dispatch, i.e. it would have made the established baselines themselves infeasible.
    # Final rule (replaces both): every node gets EXACTLY the mechanisms it has evidence
    # for, and the closure cap (where allowed) is DATA-DERIVED, not an arbitrary fraction:
    #   - Pure-KWK node (CHP asset present, NO local demand, e.g. SB j_bmhkw/j_gtost/j_hkw):
    #     closure Var hard-fixed to 0, unchanged from M1 -- curtailment MUST go through
    #     Q_dump_chp_{asset} (priced, capacity-bounded by that unit's own thermal rating).
    #   - Every other node (local demand with or without a CHP asset, e.g. MM j_9/j_12, SB
    #     j_man; OR a pure generator/passthrough node with neither, e.g. SB j_pss/j_psw):
    #     closure Var stays free, epsilon-priced (I1), capped per-node at
    #     cap(n) = max(1.5 x that node's OWN historical closure usage in the network's
    #     BASE-HK0 reference solve (B4, docs SS4bb), 1.0 MWh) -- analogous to how the E3
    #     pressure-slack widening was data-derived, not picked arbitrarily. This keeps every
    #     baseline feasible by construction (the cap is always >= what that node already
    #     needed) while still preventing the whole network's 0.25% budget from concentrating
    #     on one node (SB j_man: ~475 MWh derived vs. the old flat-fraction formula, which
    #     would have let it absorb up to the full 1,600 MWh network-wide cap alone).
    # SB's j_man shows ZERO closure usage in ITS OWN BASE-HK0 (BC-SB-HK0) -- HP/EK are not
    # placed there until S0-HK0, so BASE-HK0 gives no signal for it there; substituted with
    # its own usage in the original S0-HK0 solve (B4, docs SS4bb, 316.71 MWh) as the
    # next-best authoritative reference for what this node genuinely needs.
    _BASELINE_CLOSURE_MWH = {
        # Memmingen -- BC-MM-HK0 (B4), docs SS4bb
        "j_9": 5.29052209949666,
        "j_12": 6.281481086231974,
        # Stadtbach -- BC-SB-HK0 (B4), docs SS4bb
        "j_bmhkw": 504.13861899150936,
        "j_gtost": 259.34819674675987,
        "j_hkw": 110.00012352183458,
        "j_pss": 0.7319359407029244,
        # Stadtbach j_man -- SUBSTITUTE reference: BC-SB-HK0 shows 0 (no HP/EK there yet);
        # using SB-S0-HK0's own original usage (B4, docs SS4bb) instead.
        "j_man": 316.71,
    }
    _CAP_MULTIPLIER = 1.5
    _CAP_FLOOR_MWH = 1.0

    if _dump_mode == 'chp_only':
        _kwk_only_nodes = []
        _closure_eligible_nodes = []  # demand-bearing (with/without CHP) + pure-gen/passthrough
        for node_id, node_cfg in unified_config.nodes.items():
            _node_assets = list(getattr(node_cfg, 'assets', None) or [])
            # component_assembler.py's _attach_thermal_generator_from_unified uppercases the
            # asset id for the Pyomo attribute name (name = asset.id.upper()) -- match that
            # exactly, not the raw lowercase config key, or every CHP asset is invisible here.
            _has_chp = any(
                hasattr(model, f"Q_dump_chp_{a.upper()}") for a in _node_assets
            )
            _has_local_demand = hasattr(model, f"heatd_{node_id}")
            if _has_chp and not _has_local_demand:
                _kwk_only_nodes.append(node_id)
            else:
                _closure_eligible_nodes.append((node_id, _has_chp, _has_local_demand))

        for _nid in _kwk_only_nodes:
            _dv = getattr(model, f"Q_dump_{_nid}")
            for _t in model.t:
                _dv[_t].fix(0.0)
            _n_dump_vars_fixed += len(model.t)
            # N2 sanity check: every pure-KWK node must actually have a Notkuehler outlet --
            # trivially true by the _has_chp test above, asserted explicitly for redundancy.
            _node_assets = list(getattr(unified_config.nodes[_nid], 'assets', None) or [])
            assert any(hasattr(model, f"Q_dump_chp_{a.upper()}") for a in _node_assets), (
                f"[DATA-CLOSURE N2] {_nid} classified pure-KWK but no Q_dump_chp_* found -- "
                "internal inconsistency, investigate before trusting results.")

        _node_cap_mwh = {}
        for _nid, _has_chp, _has_local_demand in _closure_eligible_nodes:
            _closure_vars.append((_nid, getattr(model, f"Q_dump_{_nid}")))
            _baseline = _BASELINE_CLOSURE_MWH.get(_nid, 0.0)
            _cap = max(_CAP_MULTIPLIER * _baseline, _CAP_FLOOR_MWH)
            _node_cap_mwh[_nid] = _cap
            # N2: at every node that also carries a CHP asset, the derived cap must not
            # exceed 1.5x its own baseline usage (true by construction of the formula above,
            # asserted for redundancy against a future refactor breaking that invariant).
            if _has_chp:
                assert _cap <= _CAP_MULTIPLIER * _baseline + 1e-9, (
                    f"[DATA-CLOSURE N2] {_nid} (KWK+demand) cap {_cap:.4f} MWh exceeds "
                    f"1.5x baseline {_baseline:.4f} MWh -- invariant violated.")

        logger.info(
            "[DATA-CLOSURE N1/N2] node categorisation: %d pure-KWK (fixed 0, Q_dump_chp "
            "only), %d closure-eligible (demand-bearing and/or pure-generator/passthrough, "
            "data-derived per-node cap) -- pure-KWK=%s, closure-eligible=%s",
            len(_kwk_only_nodes), len(_closure_eligible_nodes),
            _kwk_only_nodes, [n for n, _, _ in _closure_eligible_nodes],
        )
        assert len(_closure_vars) > 0, (
            "[DUMP-MODE] chp_only requested but 0 node-level dump variables were made closure-"
            "eligible -- the per-node mechanism is a no-op, investigate before trusting results.")

        _total_annual_demand_mwh = 0.0
        for _nid in unified_config.nodes:
            _hd = getattr(model, f"heatd_{_nid}", None)
            if _hd is not None:
                _total_annual_demand_mwh += sum(pyo.value(_hd[_t]) for _t in model.t)
        _closure_cap_frac = 0.0025  # H1: 0.25% network-wide guard (unchanged, stays active)
        _closure_cap_mwh = _closure_cap_frac * _total_annual_demand_mwh
        model._data_closure_total_demand_mwh = _total_annual_demand_mwh
        model._data_closure_cap_mwh = _closure_cap_mwh
        model._data_closure_cap_frac = _closure_cap_frac
        model._data_closure_baseline_mwh = dict(_BASELINE_CLOSURE_MWH)
        model._data_closure_node_cap_mwh = dict(_node_cap_mwh)
        # 2026-09-25 (I1, docs SS4bc): expose the closure Vars so model_finalizer.py can price
        # them at the epsilon tie-break rate (0.01 EUR/MWh) -- built here, consumed there, same
        # pattern as model.pressure_slack_terms/model.lateral_tiebreak_terms.
        model.data_closure_terms = list(_closure_vars)

        # NOTE: no default-arg closure capture here -- Pyomo's scalar-constraint calling
        # convention can invoke rule(model, None), which would silently clobber a default
        # argument positionally (found via a live TypeError: 'NoneType' object is not
        # iterable). Plain closure over _closure_vars/_closure_cap_mwh is safe: this rule is
        # defined and used exactly once, immediately, no loop-variable late-binding risk.
        def _data_closure_cap_rule(m):
            return sum(v[t] for _nid, v in _closure_vars for t in m.t) <= _closure_cap_mwh

        model.data_closure_cap = pyo.Constraint(rule=_data_closure_cap_rule)
        logger.info(
            "[DATA-CLOSURE] network-wide guard (H1, unchanged): %.4f MWh (0.25%% of %.2f MWh "
            "total annual demand) -- run becomes INFEASIBLE if the true requirement exceeds "
            "this; a WARNING fires above %.4f MWh (0.125%%)",
            _closure_cap_mwh, _total_annual_demand_mwh, 0.5 * _closure_cap_mwh)
        assert _closure_cap_mwh > 0.0, (
            "[DATA-CLOSURE] computed 0.25% cap is <= 0 -- total annual demand could not be "
            "determined, investigate before trusting results.")

        # N1: per-node cap, data-derived from that node's own BASE-HK0 (or, for j_man,
        # S0-HK0) reference usage, additional to the network-wide guard above.
        for _nid, _has_chp, _has_local_demand in _closure_eligible_nodes:
            _dv = getattr(model, f"Q_dump_{_nid}")
            _cap = _node_cap_mwh[_nid]

            def _make_node_cap_rule(_var, _cap_val):
                def _rule(m):
                    return sum(_var[t] for t in m.t) <= _cap_val
                return _rule

            setattr(model, f"data_closure_cap_node_{_nid}",
                    pyo.Constraint(rule=_make_node_cap_rule(_dv, _cap)))
            logger.info(
                "[DATA-CLOSURE N1] per-node cap %s: %.4f MWh (max(1.5 x %.4f MWh baseline, "
                "%.1f MWh floor)) -- chp=%s, local_demand=%s",
                _nid, _cap, _BASELINE_CLOSURE_MWH.get(_nid, 0.0), _CAP_FLOOR_MWH,
                _has_chp, _has_local_demand)

    # Global Q_dump = sum of per-node dumps (real, priced dump). Under chp_only every per-node
    # dump Var is now a free-but-capped-and-unpriced G3 closure Var (see above), NOT priced
    # dump -- so the priced global aggregate stays identically 0 there, matching the original
    # (pre-G3) fixed-to-0 behaviour for objective/reporting purposes.
    node_ids = list(unified_config.nodes.keys())

    def global_dump_rule(m, t):
        if _dump_mode == 'chp_only':
            return m.Q_dump[t] == 0
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
            # 2026-07-08: this freezes T_sup_p/T_ret_p to Python floats via
            # pyo.value() at build time -- only valid if they're Params, not
            # Vars. Today this holds by construction: this function is only
            # ever called for bidirectional pipes off the primary producer,
            # and L3+ node classification (network_manager.py
            # _classify_node_temperature_mode) deliberately excludes every
            # node adjacent to a bidirectional pipe from getting a Var
            # T_supply/T_return, specifically so this stays valid. Assert
            # rather than silently freezing a Var if that invariant ever
            # breaks (same bug class as the pre-2026-07-07 mass-balance bugs).
            assert isinstance(T_sup_p, pyo.Param), (
                f"_make_signed_q_fn: T_sup_p is a {type(T_sup_p).__name__}, not a Param -- "
                f"freezing it via pyo.value() would silently bake in a stale ΔT. "
                f"This should only be reachable for bidirectional-pipe-adjacent nodes, "
                f"which L3+ classification excludes from ever getting a Var T_supply."
            )
            assert isinstance(T_ret_p, pyo.Param), (
                f"_make_signed_q_fn: T_ret_p is a {type(T_ret_p).__name__}, not a Param -- "
                f"same concern as T_sup_p above."
            )

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
                # 2026-09-20 FIX (F1): the term is Q_delivered ONLY. Q_delivered is already NET
                # of every downstream local generation, because the node mass balance
                # (`m_in + m_gen == m_out + m_dem [+ m_chg]`, rewritten below for every node
                # with ht_out) removes local generation from the pipe mass flow, and
                # Q_delivered = m_dot*cp*dT is linked to that flow. The previous
                # (2026-07-07) BFS that subtracted ht_out of the whole downstream subtree
                # from Q_delivered pre-dated that mass-balance rewrite and therefore counted
                # local generation TWICE (and, for storage nodes, credited the discharge
                # without ever charging the primary for the charge). Symptom: primary supply
                # far below the physical pipe outflow (BC-SB: 104 GWh of a 115 GWh gap).
                # Energy conservation now follows from the exact linear node balances alone:
                #   sum(ht_out) = sum(demand) + sum(dump) + sum(ht_in) + supply_loss + return_loss.
                # See MODEL_AND_DOE_CONTROL.md §4x/§4y and scripts/paper_2/diag_primary_balance.py.
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

    # ── Return-side pipe loss (L3+ correctness fix, 2026-09-03) ──────────────
    # In L3+ mode the return temperature is a fixed Param, so the nodal balance's
    # Q_delivered (supply side) embeds ONLY the supply-pipe loss; each pipe's
    # Q_loss_return is computed but never forces generation. That under-counts
    # network loss by the entire return side (~45% at Memmingen) — the flattering
    # direction (less loss → less generation/fuel/CO2/TAC). Since T_return is a
    # Param, every Q_loss_return[t] is a constant, so we add their sum as an extra
    # producer heat demand: a correctness fix, one term, no new variable, no gap
    # risk. True return-temperature propagation would be a model extension → Future
    # Work. Applied ONLY on the nodal path (guarded by _bidi below); the legacy
    # network_Q_loss_per_timestep fallback already sums supply+return, so adding it
    # there too would double-count.
    import os as _os_rl
    _return_loss_terms = []
    if unified_config is not None and not _os_rl.environ.get("CALION_DISABLE_RETURN_LOSS"):
        for _pid in unified_config.pipes:
            _rl = getattr(model, f"{_pid.upper().replace('-', '_')}_Q_loss_return", None)
            if _rl is not None:
                _return_loss_terms.append(_rl)
    if _os_rl.environ.get("CALION_DISABLE_RETURN_LOSS"):
        logger.warning("[CONSTRAINT] Return-loss correction DISABLED (CALION_DISABLE_RETURN_LOSS) "
                       "— objective-validation A/B only, do NOT use for results.")
    if _return_loss_terms:
        logger.info(
            "[CONSTRAINT] Return-loss correction: %d pipe Q_loss_return terms added to "
            "primary producer balance (nodal path only)", len(_return_loss_terms),
        )

    # ── Supply-side pipe loss (2026-09-21 FIX, defect 3) ─────────────────────────
    # The 2026-09-03 correction above assumed Q_delivered already embeds the SUPPLY-pipe loss.
    # That holds only in the McCormick enthalpy-propagation path (W_sup_in - W_sup_out =
    # Q_loss_supply*1000, constraint `<PIPE>_enthalpy_prop_sup`). In the standard MILP mode
    # (Param temperatures) the built model has `1000*Q_delivered = m_dot*cp*dT` (lossless),
    # `Q_consumer = Q_delivered` (no_delay) and `Q_loss_supply = const`: the supply loss then
    # sits in NO heat balance and asks for no generation (BC-SB 56%, BC-MM 60% of the pipe loss
    # uncovered; found 2026-09-20 from the exported LP, see MODEL_AND_DOE_CONTROL §4z).
    # Add Q_loss_supply of exactly those pipes as an extra primary heat demand. Guarded by the
    # presence of `enthalpy_prop_sup`, so a pipe whose Q_delivered already carries the loss is
    # never counted twice. Self-test (author): BC-MM / BC-SB closure must go to ~0, NOT to a
    # negative surplus of the same size (= double count). Nodal path only, like the return loss.
    _supply_loss_terms = []
    if unified_config is not None and not _os_rl.environ.get("CALION_DISABLE_SUPPLY_LOSS"):
        for _pid in unified_config.pipes:
            _pfx_sl = _pid.upper().replace('-', '_')
            _sl = getattr(model, f"{_pfx_sl}_Q_loss_supply", None)
            if _sl is None:
                continue
            if getattr(model, f"{_pfx_sl}_enthalpy_prop_sup", None) is not None:
                continue  # McCormick path: loss already embedded in Q_delivered
            _supply_loss_terms.append(_sl)
    if _os_rl.environ.get("CALION_DISABLE_SUPPLY_LOSS"):
        logger.warning("[CONSTRAINT] Supply-loss correction DISABLED (CALION_DISABLE_SUPPLY_LOSS) "
                       "— A/B / legacy-reproduction only, do NOT use for results.")
    if _supply_loss_terms:
        logger.info(
            "[CONSTRAINT] Supply-loss correction: %d pipe Q_loss_supply terms added to "
            "primary producer balance (nodal path only; pipes without enthalpy_prop_sup)",
            len(_supply_loss_terms),
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
                    _bidi=_bidi_signed_q_terms, _rl=_return_loss_terms,
                    _sl=_supply_loss_terms,
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
                    # Return-side loss correction: Q_delivered (supply side) misses it in
                    # L3+; add it ONLY on the nodal path (_bidi active) so the legacy
                    # network_Q_loss_per_timestep branch above is not double-counted.
                    return_loss = sum(rl[t] for rl in _rl) if (_rl and _bidi) else 0
                    # Supply-side loss of pipes whose Q_delivered does not embed it (defect 3).
                    supply_loss = sum(sl[t] for sl in _sl) if (_sl and _bidi) else 0
                    return supply == (_d[t] + charge + network_loss + return_loss + supply_loss
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
                #   local_gen + pipe_in == demand + Σ(downstream pipes out) + dump + charge
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

                # BUGFIX (2026-07-07): collect outgoing pipes' Q_delivered, mirroring the
                # producer/mixed branch above (lines ~377-390). Before this fix, a
                # 'consumer'-type node's balance only ever needed to satisfy its OWN local
                # demand, because pre-F3 no consumer node ever had local generation
                # (ht_out was always empty here, so this whole branch was skipped and
                # NetworkManager handled pass-through separately). F3 endogenous siting
                # breaks that assumption — it injects ht_out at consumer candidate nodes
                # that are NOT terminal (e.g. Memmingen's j_5, which feeds j_6 onward).
                # Without q_pipes_out, the balance silently dropped the requirement to
                # keep feeding everything downstream, which is exactly what an IIS traced
                # to infeasibility at j_5→j_6, j_7→j_8 for MM-S4/MM-S5.
                q_pipes_out: list = []
                if unified_config is not None:
                    for pipe_id, pipe_cfg in unified_config.pipes.items():
                        if pipe_cfg.from_node == node_id:
                            pipe_pfx = pipe_id.upper().replace('-', '_')
                            qd = getattr(model, f'{pipe_pfx}_Q_delivered', None)
                            if qd is not None:
                                q_pipes_out.append(qd)

                def consumer_with_assets_balance(
                    m, t, _out=ht_out, _in=ht_in, _d=dump_var,
                    _dem=demand_param, _dem_slack=demand_slack, _qp=q_pipe_in,
                    _qpo=q_pipes_out
                ):
                    local_supply = sum((f[t] for f in _out), start=0)
                    charge = sum((f[t] for f in _in), start=0)
                    pipe_in = _qp[t] if _qp is not None else 0
                    dem_t = _dem[t] - _dem_slack[t] if _dem_slack is not None else _dem[t]
                    return (local_supply + pipe_in
                            == dem_t + sum(qo[t] for qo in _qpo) + _d[t] + charge)

                setattr(model, f"ht_balance_{node_id}",
                        pyo.Constraint(model.t, rule=consumer_with_assets_balance))
                logger.info(
                    "[CONSTRAINT] Consumer %s: combined balance with %d local assets, "
                    "%d downstream pipes",
                    node_id, len(ht_out), len(q_pipes_out),
                )
            # else: pure consumer without local assets — demand handled by NetworkManager

        elif node_cfg.type == "junction":
            # Junction: flow balance handled by NetworkManager
            pass

    # ── Mass-balance correction for nodes with local heat generation ────────
    # BUGFIX (2026-07-07): thermal_node.py's `{prefix}_mass_balance` constraint
    # (Sigma m_dot_in == Sigma m_dot_out [+ m_dot_demand]) is built while nodes
    # are attached, BEFORE any asset/F3 flow is wired up -- ht_out is always
    # empty at that point, so it has no way to account for heat injected
    # locally at that node (static secondary producers, or F3 endogenous-siting
    # candidates). In MILP-linearized mode every pipe's own m_dot is a fixed
    # linear function of its Q_delivered (Q = m_dot * cp * dT with dT a Param),
    # so a local Q_gen with no matching m_dot term makes the (already-fixed)
    # heat balance above and this untouched mass balance mutually exclusive
    # whenever Q_gen != 0. This is exactly what made MM-S4/MM-S5
    # infeasibleOrUnbounded (confirmed via IIS).
    #
    # BUGFIX (2026-07-08): T_supply is now a real per-node Var at L3+-classified
    # nodes (spatial temperature propagation), including generation-bearing/F3
    # candidate nodes -- so the original fix's `pyo.value(T_supply[t])` (frozen
    # to a float at build time) would silently produce a WRONG constant instead
    # of tracking the Var, and dividing by it isn't linear anyway. Fix: promote
    # `m_dot_gen[t]` to a genuine decision Var with its own McCormick-relaxed
    # enthalpy-flux block (_attach_local_generation_mdot below), built ONCE per
    # node and consumed by BOTH the mass_balance and passthrough_flow rewrites
    # -- deliberately shared so the two constraints can never independently
    # diverge on "what m_dot_gen means here" the way the pre-2026-07-07 bug did.
    _cp_water = 4.186  # kJ/(kg*K), same constant as thermal_node.py / pipe_pair.py

    def _attach_local_generation_mdot(model, node_id, prefix, gens, T_supply_n, T_return_n):
        """Create (or return the already-created) m_dot_gen[t] Var for a node's
        local heat generation: Q_gen*1000 == m_dot_gen*cp*(T_supply - T_return).

        T_supply and T_return are classified INDEPENDENTLY here (each can be a
        Var or a Param for reasons unrelated to each other -- e.g. a junction
        node excluded from L3+ propagation still has a free Var T_return
        purely because it's non-consumer type, regardless of T_supply being a
        Param). Each side of the product is built as a plain linear term when
        its own T is a Param, or McCormick-relaxed against a shared m_dot_gen
        Var when its own T is a Var -- single source of truth for both
        mass-balance rewrite sites below.
        """
        existing = getattr(model, f'{prefix}_m_dot_gen', None)
        if existing is not None:
            return existing

        _supply_is_var = isinstance(T_supply_n, pyo.Var)
        _return_is_var = isinstance(T_return_n, pyo.Var)

        if not _supply_is_var and not _return_is_var:
            # Legacy path: both Params -- plain linear expression, identical
            # in spirit to the pre-2026-07-08 fix (no new Var needed at all).
            def _m_dot_gen_expr(m, t, _gens=gens, _Tsup=T_supply_n, _Tret=T_return_n):
                dT_t = pyo.value(_Tsup[t]) - pyo.value(_Tret[t])
                return sum(f[t] for f in _gens) * 1000 / (_cp_water * dT_t)
            expr = pyo.Expression(model.t, rule=_m_dot_gen_expr)
            setattr(model, f'{prefix}_m_dot_gen', expr)
            return expr

        # At least one side is a Var -> m_dot_gen must be a genuine decision
        # Var so each bilinear side can be McCormick-relaxed against it.
        #
        # Bound: sum of a generous per-term fallback (40 MW -- above any single
        # asset's real capacity in these networks, e.g. hp_main caps at 30MW,
        # eboiler_main at 20MW) unless a tighter numeric .ub is already present
        # on the term itself. Per McCormick, a LOOSER bound only widens the
        # relaxation (never causes infeasibility); an OVER-TIGHT one can -- so
        # err generous, matching thermal_node.py's own _mdot_ub philosophy.
        _q_gen_cap = 0.0
        for term in gens:
            try:
                _ub = next(iter(term.values())).ub
            except Exception:
                _ub = None
            _q_gen_cap += float(_ub) if _ub is not None else 40.0

        def _bounds_of(T_n):
            if isinstance(T_n, pyo.Var):
                sample = next(iter(T_n.values()))
                lo, hi = sample.lb, sample.ub
            else:
                v = float(pyo.value(T_n[next(iter(T_n))]))
                lo = hi = v
            if lo is None or hi is None:
                lo, hi = 40.0, 140.0  # safe generic fallback
            return lo, hi

        _T_sup_lo, _T_sup_hi = _bounds_of(T_supply_n)
        _T_ret_lo, _T_ret_hi = _bounds_of(T_return_n)
        _dT_min = max(_T_sup_lo - _T_ret_hi, 5.0)
        _m_dot_gen_max = _q_gen_cap * 1000 / (_cp_water * _dT_min) * 1.5

        m_dot_gen = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(0, _m_dot_gen_max))
        setattr(model, f'{prefix}_m_dot_gen', m_dot_gen)

        if _supply_is_var:
            W_sup_gen = pyo.Var(model.t, domain=pyo.NonNegativeReals,
                                 bounds=(0, _m_dot_gen_max * _cp_water * _T_sup_hi))
            setattr(model, f'{prefix}_W_sup_gen', W_sup_gen)
            _mccormick(model, f'{prefix}_W_sup_gen_mix', W_sup_gen, m_dot_gen, T_supply_n,
                       0, _m_dot_gen_max, _T_sup_lo, _T_sup_hi, model.t, scale=_cp_water)
            sup_term_at = lambda t: W_sup_gen[t]
        else:
            sup_term_at = lambda t: m_dot_gen[t] * _cp_water * T_supply_n[t]

        if _return_is_var:
            W_ret_gen = pyo.Var(model.t, domain=pyo.NonNegativeReals,
                                 bounds=(0, _m_dot_gen_max * _cp_water * _T_ret_hi))
            setattr(model, f'{prefix}_W_ret_gen', W_ret_gen)
            _mccormick(model, f'{prefix}_W_ret_gen_mix', W_ret_gen, m_dot_gen, T_return_n,
                       0, _m_dot_gen_max, _T_ret_lo, _T_ret_hi, model.t, scale=_cp_water)
            ret_term_at = lambda t: W_ret_gen[t]
        else:
            ret_term_at = lambda t: m_dot_gen[t] * _cp_water * T_return_n[t]

        def _close_rule(m, t, _gens=gens, _sup=sup_term_at, _ret=ret_term_at):
            return _sup(t) - _ret(t) == sum(f[t] for f in _gens) * 1000

        setattr(model, f'{prefix}_m_dot_gen_close', pyo.Constraint(model.t, rule=_close_rule))
        logger.info(
            "[CONSTRAINT] Node %s: m_dot_gen McCormick-relaxed (T_supply_is_var=%s, "
            "T_return_is_var=%s, %d gen term(s), bound=%.1f kg/s)",
            node_id, _supply_is_var, _return_is_var, len(gens), _m_dot_gen_max,
        )
        return m_dot_gen

    for node_id, node_buses in system_buses.nodes.items():
        if not node_buses.ht_out:
            continue
        prefix = node_id.upper().replace('-', '_')
        old_mb = getattr(model, f'{prefix}_mass_balance', None)
        if old_mb is None:
            continue  # root/producer node with no incoming pipes -- unconstrained, fine

        T_supply_n = getattr(model, f'{prefix}_T_supply', None)
        T_return_n = getattr(model, f'{prefix}_T_return', None)
        if T_supply_n is None or T_return_n is None:
            # Should be structurally impossible once WP1-2 classification is
            # consistent (every node with a mass_balance constraint has both
            # attributes) -- hard-fail instead of silently reproducing the
            # 2026-07-07 bug, per the 2026-07-08 design review.
            raise ValueError(
                f"Node {node_id} has local generation (ht_out non-empty) but is "
                f"missing T_supply/T_return -- cannot build a correct mass balance. "
                f"This should not be reachable; check node classification."
            )

        _incoming_m_dot = []
        _outgoing_m_dot = []
        for pipe_id, pipe_cfg in unified_config.pipes.items():
            pfx = pipe_id.upper().replace('-', '_')
            md = getattr(model, f'{pfx}_m_dot', None)
            if md is None:
                continue
            if pipe_cfg.to_node == node_id:
                _incoming_m_dot.append(md)
            if pipe_cfg.from_node == node_id:
                _outgoing_m_dot.append(md)

        _m_dot_demand_n = getattr(model, f'{prefix}_m_dot_demand', None)
        _gens = list(node_buses.ht_out)
        _m_dot_gen = _attach_local_generation_mdot(model, node_id, prefix, _gens, T_supply_n, T_return_n)
        # 2026-09-20 FIX (F2): storage CHARGE (ht_in) withdraws heat/mass at this node exactly as
        # generation injects it. Before, the mass balance knew only ht_out, so at a storage node
        # it was inconsistent with the (correct) heat balance `gen + Q_in == dem + out + dump +
        # charge` (Param T: forces charge+dump=0; Var T: only "satisfiable" via McCormick slack
        # on m_gen). Same helper / same (T_supply, T_return) pair -> m_chg means the same thing
        # as m_gen. Attribute prefix `<NODE>_CH` keeps it separate from `<NODE>_m_dot_gen`.
        import os as _os_f2
        # CALION_DISABLE_MASS_CHARGE: bisection switch for the 2026-09-20 acceptance tests ONLY
        # (F2 off = old mass balance without charge term). Never set for results.
        _chg_terms = ([] if _os_f2.environ.get("CALION_DISABLE_MASS_CHARGE")
                      else list(node_buses.ht_in))
        _m_dot_chg = (_attach_local_generation_mdot(model, node_id, f'{prefix}_CH', _chg_terms,
                                                    T_supply_n, T_return_n)
                      if _chg_terms else None)

        model.del_component(old_mb)

        def _corrected_mass_balance(
            m, t, _in=_incoming_m_dot, _out=_outgoing_m_dot,
            _dem=_m_dot_demand_n, _gen=_m_dot_gen, _chg=_m_dot_chg,
        ):
            total_in = sum(md[t] for md in _in)
            total_out = sum(md[t] for md in _out)
            dem_t = _dem[t] if _dem is not None else 0
            chg_t = _chg[t] if _chg is not None else 0
            return total_in + _gen[t] == total_out + dem_t + chg_t

        setattr(model, f'{prefix}_mass_balance',
                pyo.Constraint(model.t, rule=_corrected_mass_balance))
        logger.info(
            "[CONSTRAINT] Node %s: mass_balance corrected for %d local generation "
            "term(s) (shared m_dot_gen Var)", node_id, len(_gens),
        )

        # network_manager.py's `_link_consumer_demands()` independently builds a
        # SECOND, redundant Kirchhoff constraint on the exact same pipe m_dot
        # variables (`link_demand_{node_id}_passthrough_flow` for a single
        # incoming pipe, `link_demand_{node_id}_multi_passthrough_flow` for
        # several) -- also built before assets/F3 flows exist, so it has the
        # identical missing-generation-term gap as thermal_node.py's mass
        # balance above. Deliberately reuses the SAME `_m_dot_gen` Var created
        # above rather than an independent computation.
        for _pf_name in (f'link_demand_{node_id}_passthrough_flow',
                         f'link_demand_{node_id}_multi_passthrough_flow'):
            old_pf = getattr(model, _pf_name, None)
            if old_pf is None:
                continue
            model.del_component(old_pf)

            def _corrected_passthrough(
                m, t, _in=_incoming_m_dot, _out=_outgoing_m_dot,
                _dem=_m_dot_demand_n, _gen=_m_dot_gen, _chg=_m_dot_chg,
            ):
                total_in = sum(md[t] for md in _in)
                total_out = sum(md[t] for md in _out)
                dem_t = _dem[t] if _dem is not None else 0
                chg_t = _chg[t] if _chg is not None else 0
                return total_in + _gen[t] == total_out + dem_t + chg_t

            setattr(model, _pf_name, pyo.Constraint(model.t, rule=_corrected_passthrough))
            logger.info(
                "[CONSTRAINT] Node %s: %s corrected for %d local generation term(s)",
                node_id, _pf_name, len(_gens),
            )

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


def add_grid_market_constraints(model, month_groups: dict[int, list[int]] | None = None):
    """Add grid buy/sell and peak demand constraints.

    Args:
        model: Pyomo ConcreteModel with grid variables (P_buy, P_sell, grid_mode, etc.)
        month_groups: Y3 (2026-10-01, docs SS4cb): optional {calendar_month: [t,...]}
            mapping (1-12, using the real input timestamps -- NOT a generic 30-day
            assumption) derived by the caller from the TimeSeriesTable index. When
            given, ALSO builds per-month peak-tracking Vars/Constraints (P_buy_peak_month),
            alongside the existing single ANNUAL P_buy_peak (never removed -- needed
            for the annual-vs-monthly diagnostic comparison regardless of which one
            drives the objective, see model_finalizer.py's demand_charge_mode switch).

    Constraints added:
        - model.buy_gate: Buy only when grid_mode = 1
        - model.sell_gate: Sell only when grid_mode = 0
        - model.buy_limit: Limit import to max_import
        - model.sell_limit: Limit export to max_export
        - model.peak_con: Track peak demand
        - model.peak_con_month[m] (if month_groups given): track per-month peak demand
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

    # Y3 (2026-10-01, docs SS4cb): per-month peak tracking, built ALONGSIDE the
    # annual one above (not replacing it) so both are always available for the
    # annual-vs-monthly diagnostic regardless of which drives the objective.
    if month_groups:
        model.months = pyo.Set(initialize=sorted(month_groups.keys()))
        model.P_buy_peak_month = pyo.Var(model.months, domain=pyo.NonNegativeReals)

        def _peak_con_month_rule(m, mo, t):
            return m.P_buy_peak_month[mo] >= m.P_buy[t]

        _month_t_pairs = [(mo, t) for mo, ts in month_groups.items() for t in ts]
        model.peak_con_month = pyo.Constraint(_month_t_pairs, rule=_peak_con_month_rule)
        logger.info("[CONSTRAINT-BUILDER] Monthly peak tracking active: %d months, %d (month,t) pairs",
                    len(month_groups), len(_month_t_pairs))

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
    om_cost=0,
    var_om_cost=0,
    terminal_value=0,
    demand_slack_cost=0,
    return_anchor_cost=0,
    pressure_reg_cost=0,
    lateral_tiebreak_cost=0,
    pressure_slack_cost=0,
    data_closure_cost=0,
):
    """Create the cost minimization objective function."""
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for objective creation")

    model.capex_cost_expr = pyo.Expression(expr=capex_cost)
    model.activation_cost_expr = pyo.Expression(expr=activation_cost)
    model.tie_break_cost_expr = pyo.Expression(expr=tie_break_cost)
    model.storage_install_cost_expr = pyo.Expression(expr=storage_install_cost)
    # V3 (docs SS4bw): fixed O&M, a REAL cost (goes in real_costs_EUR, not aux terms).
    model.om_cost_expr = pyo.Expression(expr=om_cost)
    # W2 (docs SS4bw-W): variable O&M, also a REAL cost.
    model.var_om_cost_expr = pyo.Expression(expr=var_om_cost)
    # Remaining objective terms as named Expressions too (diagnostic/audit only —
    # does not change model.obj, just makes each cost bucket individually
    # queryable post-solve via pyo.value(model.<name>_expr)).
    model.energy_cost_expr = pyo.Expression(expr=energy_cost)
    model.dump_cost_expr = pyo.Expression(expr=dump_cost)
    model.fuel_cost_expr = pyo.Expression(expr=fuel_costs)
    model.co2_cost_expr = pyo.Expression(expr=co2_cost)
    model.demand_cost_expr = pyo.Expression(expr=demand_cost)
    model.terminal_value_expr = pyo.Expression(expr=terminal_value)
    model.demand_slack_cost_expr = pyo.Expression(expr=demand_slack_cost)
    model.return_anchor_cost_expr = pyo.Expression(expr=return_anchor_cost)
    model.pressure_reg_cost_expr = pyo.Expression(expr=pressure_reg_cost)
    model.lateral_tiebreak_cost_expr = pyo.Expression(expr=lateral_tiebreak_cost)
    # Penalty only (data-artifact pressure relief) -- net out of TAC/LCOH in KPIs.
    model.pressure_slack_cost_expr = pyo.Expression(expr=pressure_slack_cost)
    # 2026-09-25 (I1, author decision, docs SS4bc): epsilon tie-break price (0.01 EUR/MWh) on
    # the G3/H1 data-closure quantity -- NOT a real cost (excluded from real_costs_EUR/positive
    # list, same treatment as pressure_slack_cost), only large enough to make the solver prefer
    # minimizing the residual when otherwise indifferent; far too small (SB: <=16 EUR at the full
    # 1,599.93 MWh cap) to ever justify a different investment decision.
    model.data_closure_cost_expr = pyo.Expression(expr=data_closure_cost)

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
            + om_cost
            + var_om_cost
            + terminal_value
            + demand_slack_cost
            + return_anchor_cost
            + pressure_reg_cost
            + lateral_tiebreak_cost
            + pressure_slack_cost
            + data_closure_cost
        ),
        sense=pyo.minimize,
    )
