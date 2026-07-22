"""
Component assembly for the CALION optimization model.

Extracts the three component-attachment loops from build_model() into a
focused ComponentAssembler class.  Each public method attaches one
technology class (heat pumps, storage, thermal generators / P2H) and
accumulates the resulting bus flow variables and cost terms so that
build_model() becomes a thin orchestrator.

Extracted from system_builder.py to reduce build_model() from ~943 lines
to ~100 lines and to give each component type a single place to live.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from calion.logging_config import get_logger

logger = get_logger(__name__)

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_PYOMO = False
    pyo = None

from calion.constants import COP_DEFAULT, DEFAULT_STORAGE_ENERGY_MWH, DEFAULT_STORAGE_POWER_MW
from calion.utils.config_utils import apply_heat_pump_defaults, normalize_storage_config

from .blocks.geometric_storage import GeometricStorageBlock
from .blocks.heat_pump import HeatPumpBlock
from .blocks.p2h import P2HBlock
from .blocks.storage import StorageBlock
from .blocks.thermal_gen import ThermalGeneratorBlock
from .cop_calculator import calculate_cop_series
from .emissions_calculator import EmissionsCalculator
from .investment_calculator import InvestmentCalculator
from .network_physics import calculate_supply_temperature_series

# ─── Bus Connections Containers ────────────────────────────────────────────────

@dataclass
class BusConnections:
    """Accumulates bus flow variable lists during component assembly.

    All lists are extended by assemble_* methods.  The lists are passed
    directly to add_bus_balance_constraints() and the objective builder.

    Also used as NodeBusConnections for per-node heat flows in multi-node mode.
    """

    el_in: list = field(default_factory=list)
    el_out: list = field(default_factory=list)
    ht_in: list = field(default_factory=list)
    ht_out: list = field(default_factory=list)
    gas_in: list = field(default_factory=list)
    bio_in: list = field(default_factory=list)
    waste_in: list = field(default_factory=list)

    # Investment cost accumulation
    capex_terms: list = field(default_factory=list)
    activation_terms: list = field(default_factory=list)
    tie_breaker_terms: list = field(default_factory=list)
    storage_install_terms: list = field(default_factory=list)

    # Fuel cost / CO2 accumulation for generators
    fuel_cost_terms: list = field(default_factory=list)
    fuel_co2_terms: list = field(default_factory=list)

    # Terminal value expression for storage (value/soft policy)
    terminal_value_term: Any = None


# Alias for clarity in multi-node context
NodeBusConnections = BusConnections


@dataclass
class SystemBusConnections:
    """Aggregates per-node bus connections for the entire system.

    In copperplate mode, there is a single node whose BusConnections is also
    the system-level aggregation.  In multi-node mode, each node has its own
    BusConnections for heat flows, while electricity and cost terms are global.
    """

    nodes: dict[str, BusConnections] = field(default_factory=dict)

    # Global electricity bus (single grid connection for all nodes)
    el_in: list = field(default_factory=list)
    el_out: list = field(default_factory=list)

    # System-wide cost accumulators
    capex_terms: list = field(default_factory=list)
    activation_terms: list = field(default_factory=list)
    tie_breaker_terms: list = field(default_factory=list)
    storage_install_terms: list = field(default_factory=list)

    # Fuel cost / CO2 accumulation for generators
    fuel_cost_terms: list = field(default_factory=list)
    fuel_co2_terms: list = field(default_factory=list)

    # Terminal value expression for storage
    terminal_value_term: Any = None

    def get_or_create_node(self, node_id: str) -> BusConnections:
        """Get or create per-node bus connections."""
        if node_id not in self.nodes:
            self.nodes[node_id] = BusConnections()
        return self.nodes[node_id]

    @property
    def all_ht_out(self) -> list:
        """Flatten all per-node heat output lists."""
        result = []
        for nb in self.nodes.values():
            result.extend(nb.ht_out)
        return result

    @property
    def all_ht_in(self) -> list:
        """Flatten all per-node heat input lists."""
        result = []
        for nb in self.nodes.values():
            result.extend(nb.ht_in)
        return result

    def to_flat_bus_connections(self) -> BusConnections:
        """Collapse to a single flat BusConnections (for copperplate compatibility).

        Merges all per-node heat flows into one global BusConnections while
        preserving the system-level electricity and cost terms.
        """
        flat = BusConnections(
            el_in=list(self.el_in),
            el_out=list(self.el_out),
            ht_in=list(self.all_ht_in),
            ht_out=list(self.all_ht_out),
            capex_terms=list(self.capex_terms),
            activation_terms=list(self.activation_terms),
            tie_breaker_terms=list(self.tie_breaker_terms),
            storage_install_terms=list(self.storage_install_terms),
            fuel_cost_terms=list(self.fuel_cost_terms),
            fuel_co2_terms=list(self.fuel_co2_terms),
            terminal_value_term=self.terminal_value_term,
        )
        # Also merge per-node fuel bus lists
        for nb in self.nodes.values():
            flat.gas_in.extend(nb.gas_in)
            flat.bio_in.extend(nb.bio_in)
            flat.waste_in.extend(nb.waste_in)
        return flat


# ─── Component Assembler ───────────────────────────────────────────────────────

class ComponentAssembler:
    """Attaches technology blocks to a Pyomo model and accumulates bus flows.

    Usage::

        assembler = ComponentAssembler(m, m.t, table, cfg, dt_h, inv_calc, co2_calc)
        assembler.assemble_heat_pumps()
        assembler.assemble_storage(soc_init_override, terminal_target_override)
        assembler.assemble_thermal_generators()
        buses = assembler.buses
    """

    def __init__(
        self,
        model: Any,
        time_set: Any,
        table: Any,
        cfg: dict[str, Any],
        dt_h: float,
        inv_calc: InvestmentCalculator,
        co2_calc: EmissionsCalculator,
    ) -> None:
        self.m = model
        self.t = time_set
        self.T = len(table)
        self.table = table
        self.cfg = cfg
        self.dt_h = dt_h
        self.inv_calc = inv_calc
        self.co2_calc = co2_calc

        self.buses = BusConnections()

        fuels = cfg.get("fuels", {})
        self._pfuel = lambda key, default=0.0: float(fuels.get(key, {}).get("price_eur_mwh", default))
        self._efuel = lambda key, default=0.0: float(fuels.get(key, {}).get("ef_kg_per_mwh_fuel", default))

        # ── Paper 2 feature wiring ────────────────────────────────────────────
        # Attached-block result handles, keyed by asset id (for cross-asset
        # couplings added after the main assembly loop).
        self._component_fs: dict[str, dict] = {}

        # Hot charging (F2): {"hp": asset_id, "tes": asset_id} — enforces
        # Qc_tes(t) == Q_hot_hp(t) so the TES charges exclusively from the HP's
        # hot channel; the pair bypasses the node heat bus (closed HP→TES pipe).
        self._hot_coupling: dict | None = cfg.get("hot_charging_coupling")

        # Endogenous siting (F3): one site binary set per group ("hp", "tes");
        # heat flows of member assets are split across candidate nodes and
        # gated by the group's site binaries (Σ_c y_c = 1).
        _endog_cfg = cfg.get("endogenous_siting") or {}
        self._endog_candidates: list[str] = list(_endog_cfg.get("candidates", []))
        self._endog_group_of: dict[str, str] = {}
        if self._endog_candidates:
            for a in _endog_cfg.get("hp_group", []):
                self._endog_group_of[a] = "hp"
            tes_group_key = "hp" if _endog_cfg.get("colocate") else "tes"
            for a in _endog_cfg.get("tes_group", []):
                self._endog_group_of[a] = tes_group_key
        self._endog_y_vars: dict[str, Any] = {}

    # ── public helpers ─────────────────────────────────────────────────────────

    def column_series(self, name: str) -> list[float] | None:
        """Return a table column as a list, or None if absent."""
        if name in self.table.columns:
            return [float(self.table[name][i]) for i in range(self.T)]
        return None

    # ── Unified Assembly (new config) ──────────────────────────────────────────

    def assemble_all(
        self,
        ucfg,
        *,
        soc_init_override: float | None = None,
        terminal_target_override: float | None = None,
    ) -> SystemBusConnections:
        """Assemble all components from a UnifiedSystemConfig.

        Iterates over nodes and their assets, attaching each component to the
        correct per-node bus.  Returns a SystemBusConnections with per-node
        heat flows and global electricity / cost terms.

        Args:
            ucfg: A UnifiedSystemConfig instance.
            soc_init_override: Override for initial storage SOC (from RH handover).
            terminal_target_override: Override for terminal SOC target.

        Returns:
            SystemBusConnections with per-node and system-level bus connections.
        """
        from calion.config.unified_config import unified_generators_defaults

        sys_buses = SystemBusConnections()

        # Store overrides for use by _attach_storage_from_unified
        self._soc_init_override = soc_init_override
        self._terminal_target_override = terminal_target_override

        # Build generator defaults lookup for config compatibility
        gen_defaults = unified_generators_defaults(ucfg)

        for node_id, node_cfg in ucfg.nodes.items():
            node_buses = sys_buses.get_or_create_node(node_id)

            for asset_id in node_cfg.assets:
                asset = ucfg.assets.get(asset_id)
                if asset is None:
                    logger.warning("Node '%s': asset '%s' not found, skipping", node_id, asset_id)
                    continue
                if isinstance(asset.params, dict) and asset.params.get("enabled") is False:
                    logger.info(
                        "Node '%s': asset '%s' disabled via config (enabled=false), skipping",
                        node_id, asset_id,
                    )
                    continue

                if asset.type == "heat_pump":
                    self._attach_hp_from_unified(asset, node_buses, sys_buses)
                elif asset.type == "storage":
                    self._attach_storage_from_unified(asset, node_buses, sys_buses)
                elif asset.type == "geometric_storage":
                    self._attach_geometric_storage_from_unified(asset, node_buses, sys_buses)
                elif asset.type == "thermal_generator":
                    self._attach_generator_from_unified(asset, node_buses, sys_buses, gen_defaults)
                elif asset.type == "p2h":
                    self._attach_p2h_from_unified(asset, node_buses, sys_buses, gen_defaults)
                else:
                    logger.warning("Unknown asset type '%s' for '%s'", asset.type, asset_id)

        self._finalize_couplings(sys_buses)
        return sys_buses

    # ── Paper 2 cross-asset wiring (hot charging, endogenous siting) ──────────

    def _get_site_y(self, group: str):
        """Get or create the site-selection binary set for a group ('hp'/'tes').

        Creates y_c ∈ {0,1} per candidate node with Σ_c y_c == 1 (a site is
        always designated; it only matters once something is built there).

        Also declares y as a type-1 Special Ordered Set (SOS1). ROOT-CAUSE
        DIAGNOSIS (2026-07-14, SB-S6/MM-S4 free-siting intractability): a
        decisive control test -- pin y to a single candidate right after
        creation, going through the EXACT SAME candidate-replicated model
        code as the free-siting run (so every candidate still carries its
        own McCormick-relaxed local-generation structure, just fixed to
        zero at the unselected ones) -- solved its root LP to 1.0958e7 in
        282s, vs. 1.799264e6 (~6x looser) taking 400-900s in FOUR separate
        formulation fixes (disaggregated capacity gates, per-candidate
        shared-port cut, explicit Var bounds correcting a McCormick sizing
        bug -- see the other DIAGNOSTIC FINDING comments in this file -- and
        a colocate-only attribution test that ruled out the 25-vs-5
        combinatorics theory). None of those linear-constraint fixes moved
        the bound at all; only removing y's FRACTIONALITY did. This proves
        the weak bound is not a tightness-of-a-single-constraint problem --
        it is that a fractional y lets the LP draw on EVERY candidate's
        McCormick-relaxed generation headroom SIMULTANEOUSLY, and only
        integrality (branching) resolves that.
        The fix: instead of leaving Gurobi to branch on these 87k+ binaries
        in whatever order its generic pseudocost heuristic picks, declare
        each group's y as an SOS1 set. SOS1 branching (Beale & Tomlin 1970;
        standard in every major MILP solver, native to Gurobi and to
        Pyomo's LP writer/persistent interfaces alike -- no solver-specific
        plumbing required) splits the candidate set in two and forces the
        "choose exactly one of these near-symmetric candidates" structure to
        be resolved early and directly, instead of being buried among
        generic binaries. This is a standard exact technique for facility-
        location-style one-hot selection, not a generic performance knob.
        """
        if group in self._endog_y_vars:
            return self._endog_y_vars[group]
        m = self.m
        cand = self._endog_candidates
        set_name = f"endog_{group}_sites"
        setattr(m, set_name, pyo.Set(initialize=cand, ordered=True))
        y = pyo.Var(getattr(m, set_name), domain=pyo.Binary)
        setattr(m, f"endog_{group}_site_y", y)
        setattr(m, f"endog_{group}_one_site",
                pyo.Constraint(expr=sum(y[c] for c in cand) == 1))
        setattr(m, f"endog_{group}_sos1",
                pyo.SOSConstraint(var=y, index=getattr(m, set_name), sos=1))
        self._endog_y_vars[group] = y
        logger.info("[ENDOG] Site binaries for group '%s': %s (SOS1)", group, cand)
        return y

    def _distribute_flows(self, name: str, out_var, in_var, sys_buses,
                          power_bound: float, capacity_var=None) -> None:
        """Split an asset's heat flows across candidate nodes (F3 siting).

        Creates per-candidate flow vars gated by the group's site binaries and
        pushes them into the candidate nodes' heat buses.

        Two formulations:
        - **Strong (disaggregated), when `capacity_var` is given**: each
          candidate gets its own capacity share `cap_c`, with
          `Σ_c cap_c == capacity_var` and `cap_c ≤ M·y_c`; flows are then
          bounded by `cap_c` directly (`out_c(t) ≤ cap_c`), not by a flat
          `M`. DIAGNOSTIC FINDING (2026-07-14, SB-S6/MM-S4 free-siting
          combinatorics): the flat `out_c(t) ≤ M·y_c` gate is the classic
          *weak/aggregated* big-M facility-location formulation — every
          candidate gets the full `M` of headroom whenever `y_c` is even
          slightly fractional, independent of the other candidates, so the
          LP relaxation can "smear" flow across all candidates at once with
          no shared capacity budget. Tying the gates to a disaggregated
          `cap_c` whose sum is pinned to the asset's real (CAPEX-priced)
          capacity is the standard *strong*/VUB reformulation (Balinski 1965;
          Cornuéjols/Fisher/Nemhauser 1977) — same integer-feasible set,
          provably at least as tight LP relaxation, and empirically the
          dominant fix for the frozen-bound pathology seen in the B&B log
          (best bound flat for 1000+ nodes / ~4800s despite active search).
        - **Weak (flat M·y_c), when `capacity_var` is None**: fallback for
          assets with no capacity handle (fixed/non-investable, no Var to
          disaggregate). Kept for robustness; not expected to be hit by any
          current F3 group member (hp_sb, ek_sb, tes_sb, hp_main,
          eboiler_main, tes_main are all investable).

            Σ_c out_c(t) == out(t)   (same for in_var)
        """
        m = self.m
        group = self._endog_group_of[name]
        y = self._get_site_y(group)
        M = float(power_bound)

        cap_c_by_c: dict[str, Any] = {}
        if capacity_var is not None:
            for c in self._endog_candidates:
                cap_c = pyo.Var(domain=pyo.NonNegativeReals, bounds=(0.0, M))
                setattr(m, f"{name}_cap_at_{c}", cap_c)
                setattr(m, f"{name}_cap_gate_{c}", pyo.Constraint(
                    expr=cap_c <= M * y[c]))
                cap_c_by_c[c] = cap_c
            setattr(m, f"{name}_cap_split", pyo.Constraint(
                expr=sum(cap_c_by_c[c] for c in self._endog_candidates) == capacity_var))

        for c in self._endog_candidates:
            node_bus = sys_buses.get_or_create_node(c)
            # DIAGNOSTIC FINDING (2026-07-14): qo/qi previously had NO
            # declared .ub (unbounded domain=NonNegativeReals) -- the linear
            # gates below (M*y_c or cap_c) constrain them, but
            # constraint_builder.py::_attach_local_generation_mdot's
            # McCormick relaxation for each node's bilinear m_dot_gen*T term
            # reads each local-generation term's Pyomo Var .ub attribute
            # DIRECTLY at Python model-build time -- before Gurobi/presolve
            # ever sees the linear gate constraints -- so an unbounded qo/qi
            # silently fell back to that code's generic 40 MW/term default,
            # producing a hugely inflated McCormick envelope (observed:
            # 11466.8 kg/s, ~2400 MW-equivalent) at EVERY candidate node.
            # This was the actual dominant weak-bound driver: three prior
            # fixes (disaggregated capacity gate, colocate-only attribution
            # test, per-candidate shared-port cut) all left the root LP bound
            # completely unchanged (1.799264e6 in all three) because none of
            # them touched the Var's own declared bound, which is the only
            # thing this McCormick sizing code looks at. Declaring the true
            # bound here directly fixes it at the source.
            qo = pyo.Var(self.t, domain=pyo.NonNegativeReals, bounds=(0.0, M))
            setattr(m, f"{name}_out_at_{c}", qo)
            if capacity_var is not None:
                _cap_c = cap_c_by_c[c]
                setattr(m, f"{name}_out_gate_{c}", pyo.Constraint(
                    self.t, rule=lambda mm, t, _q=qo, _cap=_cap_c: _q[t] <= _cap))
            else:
                setattr(m, f"{name}_out_gate_{c}", pyo.Constraint(
                    self.t, rule=lambda mm, t, _q=qo, _c=c: _q[t] <= M * y[_c]))
            node_bus.ht_out.append(qo)
            if in_var is not None:
                qi = pyo.Var(self.t, domain=pyo.NonNegativeReals, bounds=(0.0, M))
                setattr(m, f"{name}_in_at_{c}", qi)
                if capacity_var is not None:
                    _cap_c = cap_c_by_c[c]
                    setattr(m, f"{name}_in_gate_{c}", pyo.Constraint(
                        self.t, rule=lambda mm, t, _q=qi, _cap=_cap_c: _q[t] <= _cap))
                    # Per-candidate shared-port cut. DIAGNOSTIC FINDING
                    # (2026-07-14): the two gates above bound qi_c and qo_c
                    # INDEPENDENTLY by cap_c, so the LP relaxation can run
                    # BOTH at cap_c simultaneously at the SAME candidate --
                    # 2x cap_c of throughput at one node -- with only the
                    # aggregate Qc[t]+Qd[t]<=cap_p (geometric_storage.py's
                    # shared-port constraint, added 2026-07-13 for the
                    # SB-S2 consumer-node TES fix) catching the total across
                    # ALL candidates combined. An attribution test (SB-S6
                    # +colocate, no hot_charging) showed this candidate is
                    # NOT fixed by reducing the site-binary combinatorics
                    # (25->5): it tracked the fully independent-siting run
                    # almost exactly (frozen at node 0, ~96.9% gap, matched
                    # elapsed time) -- ruling out colocate as the lever. The
                    # one variant that DOES converge fast (SB-S7) also
                    # happens to bypass this exact per-candidate charge
                    # gate entirely (hot_charging routes Qc via a direct
                    # Qc==Q_hot equality, never through _distribute_flows).
                    # This cut closes the same loophole per-candidate that
                    # the aggregate shared-port constraint already closes
                    # in total, without requiring the hot-charging shortcut.
                    setattr(m, f"{name}_shared_port_at_{c}", pyo.Constraint(
                        self.t, rule=lambda mm, t, _qi=qi, _qo=qo, _cap=_cap_c:
                            _qi[t] + _qo[t] <= _cap))
                else:
                    setattr(m, f"{name}_in_gate_{c}", pyo.Constraint(
                        self.t, rule=lambda mm, t, _q=qi, _c=c: _q[t] <= M * y[_c]))
                node_bus.ht_in.append(qi)

        def out_sum(mm, t):
            return sum(getattr(mm, f"{name}_out_at_{c}")[t]
                       for c in self._endog_candidates) == out_var[t]
        setattr(m, f"{name}_out_split", pyo.Constraint(self.t, rule=out_sum))

        if in_var is not None:
            def in_sum(mm, t):
                return sum(getattr(mm, f"{name}_in_at_{c}")[t]
                           for c in self._endog_candidates) == in_var[t]
            setattr(m, f"{name}_in_split", pyo.Constraint(self.t, rule=in_sum))

        logger.info("[ENDOG] %s: heat flows distributed over %d candidate nodes "
                    "(group '%s', M=%.1f MW, disaggregated=%s)", name,
                    len(self._endog_candidates), group, M, capacity_var is not None)

    def _finalize_couplings(self, sys_buses) -> None:
        """Add cross-asset constraints after all blocks are attached."""
        # Hot charging: TES charges exactly from the HP hot channel.
        if self._hot_coupling:
            hp_id = self._hot_coupling.get("hp")
            tes_id = self._hot_coupling.get("tes")
            hp_fs = self._component_fs.get(hp_id, {})
            tes_fs = self._component_fs.get(tes_id, {})
            q_hot = hp_fs.get("Q_hot")
            qc = tes_fs.get("Q_th_in")
            if q_hot is None or qc is None:
                logger.warning(
                    "[HOT-CHARGE] Coupling %s→%s requested but Q_hot=%s / Qc=%s "
                    "— constraint NOT added", hp_id, tes_id,
                    q_hot is not None, qc is not None)
                # Safety: the TES Qc was kept OFF the node bus in anticipation
                # of this coupling — without it, charging would be free energy.
                if qc is not None:
                    setattr(self.m, f"{tes_id}_hot_charge_blocked",
                            pyo.Constraint(self.t, rule=lambda mm, t: qc[t] == 0.0))
            else:
                def hot_eq(mm, t):
                    return qc[t] == q_hot[t]
                setattr(self.m, f"{tes_id}_hot_charge_eq",
                        pyo.Constraint(self.t, rule=hot_eq))
                logger.info("[HOT-CHARGE] %s_Qc(t) == %s_Q_hot(t) coupled "
                            "(closed HP→TES charging pipe)", tes_id, hp_id)

        # Endogenous co-location: with colocate=true the TES group shares the
        # HP group's site binaries, so no extra constraint is needed here.

    def _attach_hp_from_unified(self, asset, node_buses, sys_buses):
        """Attach a heat pump from unified config to per-node buses."""
        p = dict(asset.params)
        name = asset.id
        hp_type = p.get("hp_type", "standard")

        capacity_mw = float(p.get("capacity_mw", 0.0))
        min_load = float(p.get("min_load", 0.3))

        wrg_col = p.get("wrg_source_column")
        wrg_sources = p.get("wrg_sources")
        if wrg_col is None and wrg_sources and isinstance(wrg_sources, list):
            wrg_col = wrg_sources[0] + "_T"
        if wrg_col and wrg_col not in self.table.columns and f"{wrg_col}_K" in self.table.columns:
            wrg_col = f"{wrg_col}_K"

        # Scenario-injected COP series takes priority (Paper 2 §4.3.1: waste-heat
        # priority with ambient fallback, precomputed by scenario_runner).
        # Previously this key was injected but never read — the model silently
        # used the WRG-column temperature for all hours.
        cop_override = p.get("cop_series_override")
        if cop_override is not None:
            cop_series = [float(c) for c in cop_override]
            logger.info("[ASSEMBLE] %s: using scenario-injected COP series "
                        "(len=%d, waste-heat priority)", name, len(cop_series))
        else:
            sink_temp_series_k = self._compute_heating_curve_sink_temps()
            cop_series = calculate_cop_series(self.table, wrg_col, self.cfg, hp_type,
                                              sink_temp_series=sink_temp_series_k)

        cop_charge_override = p.get("cop_charge_series_override")
        cop_charge_series = ([float(c) for c in cop_charge_override]
                             if cop_charge_override is not None else None)

        wrg_cap_col = p.get("wrg_capacity_column")
        if wrg_cap_col is None and wrg_col:
            prefix = str(wrg_col).split("_T")[0]
            candidate = f"{prefix}_Q_cap"
            if candidate in self.table.columns:
                wrg_cap_col = candidate
        wrg_caps = None
        if wrg_cap_col and wrg_cap_col in self.table.columns:
            wrg_caps = {i + 1: float(self.table[wrg_cap_col][i]) for i in range(self.T)}

        cop_default = float(p.get("cop_default", COP_DEFAULT))
        if not math.isfinite(cop_default) or cop_default <= 0:
            cop_default = COP_DEFAULT

        inv_cfg = p.get("investment", {})
        invest_enabled = bool(inv_cfg.get("enabled", False))
        cap_min = float(inv_cfg.get("capacity_min_mw", 0.0))
        cap_max = float(inv_cfg.get("capacity_max_mw", capacity_mw))
        cap_init = float(inv_cfg.get("initial_capacity_mw", capacity_mw))

        block = HeatPumpBlock(
            name,
            min_load=min_load,
            cop_series=cop_series,
            capacity_min_mw=cap_min,
            capacity_max_mw=cap_max,
            capacity_init_mw=cap_init,
            investable=invest_enabled,
            wrg_cap_series=wrg_caps,
            cop_default=cop_default,
            cop_charge_series=cop_charge_series,
        )
        fs = block.attach(self.m, self.t, self.cfg, {})
        self._component_fs[name] = fs

        # Per-node heat output (or distributed over candidates in F3 siting).
        # Note: Q_hot is never bus-connected — it feeds the TES exclusively via
        # the Qc == Q_hot coupling in _finalize_couplings().
        if name in self._endog_group_of:
            self._distribute_flows(name, fs["Q_th_out"], None, sys_buses,
                                   power_bound=max(cap_max, cap_init, 1.0),
                                   capacity_var=fs.get("capacity"))
        else:
            node_buses.ht_out.append(fs["Q_th_out"])
        # Global electricity input
        sys_buses.el_in.append(fs["P_el_in"])

        # Investment costs → system level.
        # BUGFIX (2026-07-21): same class of bug as _attach_single_heat_pump's fix
        # below -- CAPEX was charged unconditionally, even for a fixed
        # (non-investable) pre-existing HP. THIS is the function actually used for
        # Paper 2's unified `assets: {type: heat_pump}` config (routed from
        # assemble_all() at line ~279); _attach_single_heat_pump is a separate,
        # legacy `system.heat_pumps:`-list path not exercised by Paper 2 networks
        # -- fixing it alone (first pass) had zero effect on the real objective.
        # Found via MM-P1REF's Capex_cost_EUR staying nonzero (~24,194 EUR for a
        # January window) after the first fix; confirmed by objective-term dump
        # (`CALION_DEBUG_COSTS=1`) showing Capex_heat_pumps_EUR=0 (the now-fixed,
        # inactive path) while the true Capex_cost_EUR objective term was untouched.
        # Never exercised by any of the 46 campaign scenarios for the same reason
        # as the other fix (BC-MM/BC-SB are the only non-investable HP cases, both
        # capacity_mw=0, where the bug is invisible).
        cap_var = fs.get("capacity")
        build_var = fs.get("build")
        if invest_enabled and cap_var is not None and build_var is not None:
            hp_inv_defaults = self.cfg.get("heat_pumps", {}).get("investment_defaults", {})
            hp_inv_config = InvestmentCalculator.extract_component_config(inv_cfg, hp_inv_defaults)
            hp_inv_terms = self.inv_calc.calculate_component_costs(cap_var, build_var, hp_inv_config)
            sys_buses.capex_terms.extend(hp_inv_terms.capex)
            sys_buses.activation_terms.extend(hp_inv_terms.activation)
            sys_buses.tie_breaker_terms.extend(hp_inv_terms.tie_breaker)

        hp_co2 = self.co2_calc.calculate_grid_electricity_emissions(fs["P_el_in"], "heat_pump")
        self.m.co2_component_costs[name] = hp_co2.to_dict()

    def _attach_storage_from_unified(self, asset, node_buses, sys_buses):
        """Attach storage from unified config to per-node buses."""
        p = dict(asset.params)

        base_energy_mwh = p.pop("energy_mwh", DEFAULT_STORAGE_ENERGY_MWH)
        base_power_mw = p.pop("power_mw", DEFAULT_STORAGE_POWER_MW)

        # When investment is enabled, the StorageBlock's hard e_max bound must be at least
        # e_cap_max so that  E[t] <= e_max * active[t]  never undercuts the invested capacity.
        # Without this fix:  energy_mwh=0 → e_max=0 → E[t]≤0 always (tes_sb bug);
        # or energy_mwh=500, e_cap_max=5000 → SOC capped at 500 even when 5000 MW invested.
        invest_cfg = p.get("investment", {})
        invest_enabled = bool(invest_cfg.get("enabled", False))
        if invest_enabled:
            e_cap_max_inv = float(invest_cfg.get("energy_capacity_max_mwh", DEFAULT_STORAGE_ENERGY_MWH))
            effective_energy_mwh = max(base_energy_mwh, e_cap_max_inv)
        else:
            effective_energy_mwh = base_energy_mwh

        sto_cfg = {
            "enabled": True,
            "type": p.pop("storage_type", "simple"),
            "max_energy_mwh": effective_energy_mwh,
            "max_power_mw": base_power_mw,
        }
        for key in (
            "eff_charge", "eff_discharge", "loss_hour",
            "soc0_mwh", "terminal", "investment",
            "min_energy_mwh", "min_power_mw",
        ):
            if key in p:
                sto_cfg[key] = p.pop(key)
        sto_cfg.update(p)

        # Temporarily set system config for standard assembly path
        old_sys = self.cfg.get("system")
        self.cfg.setdefault("system", {})["storage"] = sto_cfg
        try:
            self.assemble_storage(
                soc_init_override=getattr(self, '_soc_init_override', None),
                terminal_target_override=getattr(self, '_terminal_target_override', None),
                name=asset.id,
            )
        finally:
            if old_sys is None:
                self.cfg.pop("system", None)
            else:
                self.cfg["system"] = old_sys

        # Move storage flows from self.buses to per-node / system level
        if self.buses.ht_out:
            node_buses.ht_out.extend(self.buses.ht_out)
            self.buses.ht_out.clear()
        if self.buses.ht_in:
            node_buses.ht_in.extend(self.buses.ht_in)
            self.buses.ht_in.clear()
        # Transfer cost terms to system level
        sys_buses.capex_terms.extend(self.buses.capex_terms)
        sys_buses.activation_terms.extend(self.buses.activation_terms)
        sys_buses.tie_breaker_terms.extend(self.buses.tie_breaker_terms)
        sys_buses.storage_install_terms.extend(self.buses.storage_install_terms)
        sys_buses.fuel_cost_terms.extend(self.buses.fuel_cost_terms)
        sys_buses.terminal_value_term = self.buses.terminal_value_term
        self.buses.capex_terms.clear()
        self.buses.activation_terms.clear()
        self.buses.tie_breaker_terms.clear()
        self.buses.storage_install_terms.clear()
        self.buses.fuel_cost_terms.clear()

    def _attach_generator_from_unified(self, asset, node_buses, sys_buses, gen_defaults):
        """Attach a thermal generator from unified config to per-node buses."""
        p = dict(asset.params)
        name = asset.id.upper()

        th_eff = float(p.get("thermal_efficiency", p.get("th_eff", 0.9)))
        el_eff = p.get("el_eff")
        cap_th = float(p.get("capacity_mw", p.get("cap_th_mw", 10.0)))

        block = ThermalGeneratorBlock(
            name,
            th_eff=th_eff,
            el_eff=el_eff,
            cap_th_mw=cap_th,
            min_load_fraction=float(p.get("min_load", 0.0)),
            min_uptime_h=float(p.get("min_uptime_h", 0.0)),
            min_downtime_h=float(p.get("min_downtime_h", 0.0)),
            max_ramp_up_mw_per_h=p.get("max_ramp_up_mw_per_h"),
            max_ramp_down_mw_per_h=p.get("max_ramp_down_mw_per_h"),
            startup_cost_eur=float(p.get("startup_cost_eur", 0.0)),
        )
        fs = block.attach(self.m, self.t, self.cfg, {})

        if fs.get("startup_var") is not None and fs.get("startup_cost_eur", 0) > 0:
            startup_expr = fs["startup_cost_eur"] * sum(fs["startup_var"][t] for t in self.t)
            sys_buses.fuel_cost_terms.append(startup_expr)

        # Per-node heat output
        node_buses.ht_out.append(fs["Q_th_out"])
        # Global electricity output (if CHP)
        if fs.get("P_el_out") is not None:
            sys_buses.el_out.append(fs["P_el_out"])

        fuel_bus = p.get("fuel", "gas")
        price = self._pfuel(fuel_bus, 0.0)
        ef = self._efuel(fuel_bus, 0.0)

        bus_map = {
            "gas": node_buses.gas_in,
            "biomass": node_buses.bio_in,
            "waste": node_buses.waste_in,
        }
        bus_map.get(fuel_bus, node_buses.gas_in).append(fs["fuel_in"])

        fuel_cost_expr = sum(fs["fuel_in"][t] * price * self.dt_h for t in self.t)
        sys_buses.fuel_cost_terms.append(fuel_cost_expr)

        is_chp = fs.get("P_el_out") is not None
        el_eff_val = float(el_eff) if el_eff is not None and is_chp else 0.0

        gen_co2 = self.co2_calc.calculate_fuel_emissions(
            fuel_var=fs["fuel_in"],
            fuel_ef_kg_per_mwh=ef,
            is_chp=is_chp,
            th_eff=th_eff,
            el_eff=el_eff_val,
            fuel_bus=fuel_bus,
        )
        gen_co2_dict = gen_co2.to_dict()
        gen_co2_dict.update({"th_eff": th_eff, "el_eff": el_eff_val if is_chp else None, "fuel_bus": fuel_bus})
        self.m.co2_component_costs[name] = gen_co2_dict
        sys_buses.fuel_co2_terms.append(gen_co2.total_kg)

    def _attach_p2h_from_unified(self, asset, node_buses, sys_buses, gen_defaults):
        """Attach a P2H converter from unified config to per-node buses.

        Supports Paper 2 EK investment (spec §2.2 CAPEX_EK = α_EK·Q̇_EK + β_EK·y_EK).
        Previously the investment section was silently ignored: the EK was a
        fixed-capacity asset (capacity_mw) with zero CAPEX in the objective.
        """
        p = dict(asset.params)
        eff = float(p.get("efficiency", 0.99))
        cap_th = float(p.get("capacity_mw", 10.0))
        min_load = float(p.get("min_load", 0.0))

        inv_cfg = p.get("investment", {}) or {}
        invest_enabled = bool(inv_cfg.get("enabled", False))
        cap_min = float(inv_cfg.get("capacity_min_mw", 0.0))
        cap_max = float(inv_cfg.get("capacity_max_mw", cap_th))

        p2h_name = asset.id.upper()
        block = P2HBlock(
            p2h_name, eff=eff, cap_th_mw=cap_th, min_load=min_load,
            investable=invest_enabled,
            capacity_min_mw=cap_min,
            capacity_max_mw=cap_max if invest_enabled else None,
        )
        fs = block.attach(self.m, self.t, self.cfg, {})
        self._component_fs[asset.id] = fs

        # Per-node heat output (or distributed over candidates in F3 siting)
        if asset.id in self._endog_group_of:
            self._distribute_flows(asset.id, fs["Q_th_out"], None, sys_buses,
                                   power_bound=max(cap_max, cap_th, 1.0),
                                   capacity_var=fs.get("capacity"))
        else:
            node_buses.ht_out.append(fs["Q_th_out"])
        # Global electricity input
        sys_buses.el_in.append(fs["P_el_in"])

        # Investment costs → system level (ANF via InvestmentCalculator)
        cap_var = fs.get("capacity")
        build_var = fs.get("build")
        if invest_enabled and cap_var is not None and build_var is not None:
            p2h_inv_config = InvestmentCalculator.extract_component_config(inv_cfg, {})
            p2h_inv_terms = self.inv_calc.calculate_component_costs(
                cap_var, build_var, p2h_inv_config)
            sys_buses.capex_terms.extend(p2h_inv_terms.capex)
            sys_buses.activation_terms.extend(p2h_inv_terms.activation)
            sys_buses.tie_breaker_terms.extend(p2h_inv_terms.tie_breaker)
            logger.info("[ASSEMBLE] %s: investable EK cap∈[%.1f, %.1f] MW, "
                        "capex=%.0f €/MW", p2h_name, cap_min, cap_max,
                        float(inv_cfg.get("capex_eur_per_mw", 0.0)))

        p2h_co2 = self.co2_calc.calculate_grid_electricity_emissions(fs["P_el_in"], "p2h")
        self.m.co2_component_costs[p2h_name] = p2h_co2.to_dict()

    # ── Heat Pump Assembly ─────────────────────────────────────────────────────

    def assemble_heat_pumps(self) -> None:
        """Attach all enabled heat pumps to the model."""
        syscfg = self.cfg.get("system", {})
        hp_defaults = self.cfg.get("heat_pumps", {})
        hp_inv_defaults = hp_defaults.get("investment_defaults", {})

        logger.debug("Raw HP config from syscfg:")
        for hp_raw in syscfg.get("heat_pumps", []):
            logger.debug(
                "  %s: enabled=%s, max_th_mw=%s, inv.enabled=%s",
                hp_raw.get("id"), hp_raw.get("enabled"),
                hp_raw.get("max_th_mw"),
                hp_raw.get("investment", {}).get("enabled"),
            )

        logger.debug("After apply_heat_pump_defaults:")
        for hp_check in apply_heat_pump_defaults(syscfg):
            logger.debug(
                "  %s: enabled=%s, max_th_mw=%s",
                hp_check.get("id"), hp_check.get("enabled"), hp_check.get("max_th_mw"),
            )

        for hp in apply_heat_pump_defaults(syscfg):
            if not hp.get("enabled", True):
                continue
            self._attach_single_heat_pump(hp, hp_inv_defaults)

    def _compute_heating_curve_sink_temps(self) -> list[float] | None:
        """Compute per-timestep sink temperature [K] from outdoor-temp heating curve.

        Returns None if no outdoor temperature column is configured, so callers
        fall back to the fixed Tsink_out_K from config.
        """
        hp_cop_cfg = self.cfg.get('heat_pumps', {}).get('cop', {})
        outdoor_col = hp_cop_cfg.get('outdoor_temp_column', 'outdoor_temp_C')
        if outdoor_col not in self.table.columns:
            return None

        outdoor_c = [float(self.table[outdoor_col][i]) for i in range(self.T)]
        supply_c = calculate_supply_temperature_series(
            outdoor_c,
            T_supply_min_c=float(hp_cop_cfg.get('supply_temp_min_c', 80.0)),
            T_supply_max_c=float(hp_cop_cfg.get('supply_temp_max_c', 120.0)),
            T_outdoor_high_c=float(hp_cop_cfg.get('t_outdoor_high_c', 20.0)),
            T_outdoor_low_c=float(hp_cop_cfg.get('t_outdoor_low_c', -10.0)),
        )
        # Convert °C → K for cop_calculator
        return [t + 273.15 for t in supply_c]

    def _attach_single_heat_pump(self, hp: dict[str, Any], hp_inv_defaults: dict[str, Any]) -> None:
        """Attach one heat pump block and accumulate its bus flows and costs."""
        name = hp.get("id", "HP")
        hp_type = hp.get("type", "standard")

        wrg_col = None
        if hp.get("wrg_source_column"):
            wrg_col = hp.get("wrg_source_column")
            if wrg_col not in self.table.columns and f"{wrg_col}_K" in self.table.columns:
                wrg_col = f"{wrg_col}_K"

        sink_temp_series_k = self._compute_heating_curve_sink_temps()
        cop_series = calculate_cop_series(self.table, wrg_col, self.cfg, hp_type,
                                          sink_temp_series=sink_temp_series_k)

        wrg_cap_col: str | None = hp.get("wrg_capacity_column")
        if wrg_cap_col is None and hp.get("wrg_source_column"):
            prefix = str(hp.get("wrg_source_column")).split("_T")[0]
            candidate = f"{prefix}_Q_cap"
            if candidate in self.table.columns:
                wrg_cap_col = candidate
        wrg_caps = None
        if wrg_cap_col and wrg_cap_col in self.table.columns:
            wrg_caps = {i + 1: float(self.table[wrg_cap_col][i]) for i in range(self.T)}

        inv_cfg = dict(hp_inv_defaults)
        inv_cfg.update(hp.get("investment", {}))
        invest_enabled = bool(inv_cfg.get("enabled", False))
        cap_min = float(inv_cfg.get("capacity_min_mw", hp.get("min_th_mw", 0.0)))
        cap_max = float(inv_cfg.get("capacity_max_mw", hp.get("max_th_mw", 0.0)))
        existing_cap = float(hp.get("max_th_mw", cap_max))
        cap_init = float(
            inv_cfg.get(
                "initial_capacity_mw",
                existing_cap if not invest_enabled else max(cap_min, min(existing_cap, cap_max)),
            )
        )

        type_cfg = self.cfg.get("heat_pumps", {}).get("types", {})
        type_par = type_cfg.get(hp_type, {})
        min_load = float(type_par.get("min_load", 0.3))
        cop_default = float(
            type_par.get(
                "COPdefault",
                self.cfg.get("heat_pumps", {}).get("cop", {}).get("cop_fallback", COP_DEFAULT),
            )
        )
        if not math.isfinite(cop_default) or cop_default <= 0:
            cop_default = COP_DEFAULT

        block = HeatPumpBlock(
            name,
            min_load=min_load,
            cop_series=cop_series,
            capacity_min_mw=cap_min,
            capacity_max_mw=cap_max,
            capacity_init_mw=cap_init,
            investable=invest_enabled,
            wrg_cap_series=wrg_caps,
            cop_default=cop_default,
        )
        fs = block.attach(self.m, self.t, self.cfg, {})
        self.buses.ht_out.append(fs["Q_th_out"])
        self.buses.el_in.append(fs["P_el_in"])

        if name == "HP1":
            logger.debug("HP1 parameters:")
            logger.info("  - capacity: %.1f - %.1f MW (init: %.1f)", cap_min, cap_max, cap_init)
            logger.info("  - investable: %s", invest_enabled)
            logger.info("  - min_load: %s", min_load)
            logger.info(
                "  - COP series: min=%.2f, max=%.2f, avg=%.2f",
                min(cop_series), max(cop_series), sum(cop_series) / len(cop_series),
            )
            logger.info("  - WRG caps: %s", "None" if wrg_caps is None else f"provided ({len(wrg_caps)} values)")

        # BUGFIX (2026-07-21): CAPEX was charged unconditionally, even for a fixed
        # (non-investable) pre-existing HP -- unlike every other asset type in this
        # module (thermal generators never charge CAPEX; _attach_p2h_from_unified's
        # EK path already gates on invest_enabled, see its own docstring for the
        # identical bug found and fixed there previously). Never exercised by any
        # of the 46 campaign scenarios (BC-MM/BC-SB are the only non-investable HP
        # cases, and both use capacity_mw=0, where the bug is invisible since the
        # fixed capacity_var is 0 either way) -- surfaced building MM-P1REF, the
        # first scenario with a nonzero fixed non-investable HP capacity.
        cap_var = fs.get("capacity")
        build_var = fs.get("build")
        if invest_enabled and cap_var is not None and build_var is not None:
            hp_inv_config = InvestmentCalculator.extract_component_config(inv_cfg, hp_inv_defaults)
            hp_inv_terms = self.inv_calc.calculate_component_costs(cap_var, build_var, hp_inv_config)
            self.buses.capex_terms.extend(hp_inv_terms.capex)
            self.buses.activation_terms.extend(hp_inv_terms.activation)
            self.buses.tie_breaker_terms.extend(hp_inv_terms.tie_breaker)

        hp_co2 = self.co2_calc.calculate_grid_electricity_emissions(fs["P_el_in"], "heat_pump")
        self.m.co2_component_costs[name] = hp_co2.to_dict()

    # ── Storage Assembly ───────────────────────────────────────────────────────

    def assemble_storage(
        self,
        soc_init_override: float | None = None,
        terminal_target_override: float | None = None,
        name: str = "TES",
    ) -> None:
        """Attach thermal energy storage if enabled."""
        syscfg = self.cfg.get("system", {})
        sto_cfg = syscfg.get("storage", {"enabled": False})
        if isinstance(sto_cfg, dict):
            sto_cfg = normalize_storage_config(sto_cfg)

        logger.info("[ASSEMBLE] Storage config: enabled=%s", sto_cfg.get("enabled", False))
        if not sto_cfg.get("enabled", False):
            return

        logger.info("[ASSEMBLE] Building storage component...")
        storage_defaults = self.cfg.get("storage", {})
        sto_inv, invest_enabled, caps = self._resolve_storage_investment(sto_cfg, storage_defaults)
        e_cap_min, e_cap_max, p_cap_min, p_cap_max, e_cap_init, p_cap_init = caps

        soc_init = self._resolve_soc_init(sto_cfg, storage_defaults)
        if soc_init_override is not None:
            soc_init = float(soc_init_override)

        eff_charge = float(sto_cfg.get("eff_charge", storage_defaults.get("eff_charge", 0.95)))
        eff_discharge = float(sto_cfg.get("eff_discharge", storage_defaults.get("eff_discharge", 0.95)))
        loss = float(sto_cfg.get("loss_hour", storage_defaults.get("loss_hour", 0.9999)))

        loss_series = sto_cfg.get("loss_hour_series") or storage_defaults.get("loss_hour_series") or self.column_series("storage_loss_hour")
        eff_charge_series = sto_cfg.get("eff_charge_series") or storage_defaults.get("eff_charge_series") or self.column_series("storage_eff_charge")
        eff_discharge_series = sto_cfg.get("eff_discharge_series") or storage_defaults.get("eff_discharge_series") or self.column_series("storage_eff_discharge")
        capacity_active_series = sto_cfg.get("capacity_active_series") or storage_defaults.get("capacity_active_series") or self.column_series("storage_capacity_active")

        terminal_policy, terminal_target_val = self._resolve_terminal_policy(
            sto_cfg, storage_defaults, soc_init, terminal_target_override
        )

        power_energy_coupling = self._resolve_power_energy_coupling(sto_cfg, storage_defaults)

        logger.info("[ASSEMBLE] Using simple storage (single-zone model)")
        block = StorageBlock(
            name,
            e_min=sto_cfg.get("min_energy_mwh", 0.0),
            e_max=sto_cfg.get("max_energy_mwh", 50000.0),
            p_max=sto_cfg.get("max_power_mw", DEFAULT_STORAGE_POWER_MW),
            eff_c=eff_charge,
            eff_d=eff_discharge,
            hourly_loss=loss,
            dt_h=self.dt_h,
            soc0=soc_init,
            investable=invest_enabled,
            e_cap_min=e_cap_min,
            e_cap_max=e_cap_max,
            p_cap_min=p_cap_min,
            p_cap_max=p_cap_max,
            e_cap_init=e_cap_init,
            p_cap_init=p_cap_init,
            terminal_target=terminal_target_val,
            loss_series=loss_series,
            eff_charge_series=eff_charge_series,
            eff_discharge_series=eff_discharge_series,
            capacity_active_series=capacity_active_series,
            power_energy_coupling=power_energy_coupling,
        )

        fs = block.attach(self.m, self.t, self.cfg, {})
        self.buses.ht_out.append(fs["Q_th_out"])
        self.buses.ht_in.append(fs["Q_th_in"])

        self._register_storage_references(fs, terminal_policy, name=name)
        self.buses.terminal_value_term = self._build_terminal_value_term(
            fs, sto_cfg, storage_defaults, terminal_policy, terminal_target_val,
            invest_enabled, e_cap_init, e_cap_max, soc_init, name=name,
        )
        self.m.terminal_value_term = self.buses.terminal_value_term

        cap_var = fs.get("cap_energy")
        pow_var = fs.get("cap_power")
        build_var = fs.get("build")
        sto_inv_config = InvestmentCalculator.extract_storage_config(sto_inv, storage_defaults.get("investment_defaults", {}))
        sto_inv_terms = self.inv_calc.calculate_storage_costs(cap_var, pow_var, build_var, sto_inv_config)
        self.buses.capex_terms.extend(sto_inv_terms.capex)
        self.buses.activation_terms.extend(sto_inv_terms.activation)
        self.buses.tie_breaker_terms.extend(sto_inv_terms.tie_breaker)
        self.buses.storage_install_terms.extend(sto_inv_terms.storage_install)

        # ── Cycling cost (wear + spurious-arbitrage deterrent) ─────────────
        # Charged per MWh flowing through the storage (charge + discharge).
        # Keeps arbitrage honest: only genuine price spreads > 2×cycling_cost
        # are exploited. Set via storage.cycling_cost_eur_per_mwh in the YAML.
        cycling_cost_eur = float(
            sto_cfg.get("cycling_cost_eur_per_mwh",
                        storage_defaults.get("cycling_cost_eur_per_mwh", 0.0))
        )
        if cycling_cost_eur > 0.0:
            Qc = fs["Q_th_in"]
            Qd = fs["Q_th_out"]
            cycling_expr = sum(
                cycling_cost_eur * (Qc[t] + Qd[t]) * self.dt_h for t in self.t
            )
            self.buses.fuel_cost_terms.append(cycling_expr)
            logger.info(
                "[STORAGE] Cycling cost %.2f €/MWh added to objective "
                "(arbitrage requires spread > %.2f €/MWh_th round-trip).",
                cycling_cost_eur, 2.0 * cycling_cost_eur,
            )

    def _attach_geometric_storage_from_unified(self, asset, node_buses, sys_buses) -> None:
        """Attach GeometricStorageBlock from unified config to per-node buses.

        CAPEX is α_tes × V_m3 + β_tes × build, annualized via ANF(i, n).
        δT is a scenario parameter passed by scenario_runner; option_b adds
        explicit h_TES and d_TES Vars for MIQCP geometry (Gurobi-compatible).
        """
        p = dict(asset.params)
        name = asset.id

        alpha_tes = float(p.get("alpha_tes_eur_per_m3", 500.0))
        beta_tes = float(p.get("beta_tes_eur", 50000.0))
        lifetime_years = float(p.get("lifetime_years", 30.0))
        delta_T_k = float(p.get("delta_T_scenario_k", 20.0))
        r_hd = float(p.get("r_hd", 3.0))
        p_max_bar = float(p.get("p_max_bar", 10.0))
        V_min_m3 = float(p.get("V_min_m3", 5.0))
        V_max_m3 = float(p.get("V_max_m3", 60000.0))
        option_b = bool(p.get("option_b", False))
        eff_c = float(p.get("eff_charge", 0.98))
        eff_d = float(p.get("eff_discharge", 0.98))
        hourly_loss = float(p.get("loss_hour", 0.9999))
        soc0_fraction = float(p.get("soc0_fraction", 0.5))
        ptr = p.get("power_to_energy_ratio")
        power_to_energy_ratio = float(ptr) if ptr is not None else None
        tsf = p.get("terminal_soc_fraction")
        terminal_soc_fraction = float(tsf) if tsf is not None else None
        cycling_cost_eur = float(p.get("cycling_cost_eur_per_mwh", 0.0))

        # Non-investable mode: a real, already-built tank sized by its known
        # energy/power rating (e.g. tes_existing) rather than an optimizer
        # decision. Volume/height are still derived geometrically so it can
        # participate in F4 pressure coupling like an investable tank.
        investable = bool(p.get("investable", True))
        energy_mwh_fixed = p.get("energy_mwh_fixed")
        power_mw_fixed = p.get("power_mw_fixed")
        e_min_fraction = float(p.get("e_min_fraction", 0.0))
        # Discrete storage sizing (multi-tank): explicit energy ladder [MWh] and the
        # realistic single-tank unit volume; large sizes -> N=ceil(V/unit) tanks,
        # beta_tes charged per tank. Tight LP relaxation vs the continuous V + big-M.
        discrete_energies_mwh = p.get("discrete_energies_mwh")
        unit_tank_m3 = p.get("unit_tank_m3")

        block = GeometricStorageBlock(
            name=name,
            alpha_tes_eur_per_m3=alpha_tes,
            beta_tes_eur=beta_tes,
            lifetime_years=lifetime_years,
            delta_T_scenario_k=delta_T_k,
            r_hd=r_hd,
            p_max_bar=p_max_bar,
            V_min_m3=V_min_m3,
            V_max_m3=V_max_m3,
            eff_c=eff_c,
            eff_d=eff_d,
            hourly_loss=hourly_loss,
            dt_h=self.dt_h,
            soc0_fraction=soc0_fraction,
            power_to_energy_ratio=power_to_energy_ratio,
            terminal_soc_fraction=terminal_soc_fraction,
            option_b=option_b,
            investable=investable,
            energy_mwh_fixed=float(energy_mwh_fixed) if energy_mwh_fixed is not None else None,
            power_mw_fixed=float(power_mw_fixed) if power_mw_fixed is not None else None,
            e_min_fraction=e_min_fraction,
            discrete_energies_mwh=discrete_energies_mwh,
            unit_tank_m3=float(unit_tank_m3) if unit_tank_m3 else None,
        )

        fs = block.attach(self.m, self.t, self.cfg, {})
        self._component_fs[name] = fs

        # BUGFIX (2026-07-03): flows and CAPEX previously went to self.buses
        # (legacy accumulator), which the unified path NEVER merges — the
        # geometric TES was disconnected from every heat balance and its CAPEX
        # was missing from the objective (phantom storage: siting had no effect,
        # investment was free). Route to node_buses / sys_buses like all other
        # unified assets.
        hot_tes = bool(self._hot_coupling and self._hot_coupling.get("tes") == name)
        # ≥ cap_power bound [MW], used as the big-M in F3 endogenous-siting flow
        # gates (_distribute_flows). BUGFIX (2026-07-14): both branches previously
        # used the max ENERGY figure [MWh] directly as a POWER bound [MW] (units
        # mismatch) -- for tes_sb that's 845 vs the true max cap_power of
        # 0.25*845=211.25 MW, a 4x looser-than-necessary M. Multiplying by the same
        # power/energy ratio GeometricStorageBlock itself uses (power_to_energy_ratio,
        # default 0.25 -- see geometric_storage.py's default_ratio) gives the tight,
        # still-exact bound: the true cap_power can never exceed it, so y_c=1 never
        # binds against it, but the LP relaxation can no longer "smear" flow using
        # 4x more headroom than physically buildable.
        _p2e_ratio = power_to_energy_ratio if power_to_energy_ratio is not None else 0.25
        if discrete_energies_mwh:
            power_bound = _p2e_ratio * max(float(e) for e in discrete_energies_mwh)
        else:
            power_bound = _p2e_ratio * block.V_max_effective * block.energy_coeff

        if name in self._endog_group_of:
            # F3 siting: discharge distributed over candidates; charge likewise
            # unless hot-coupled (then Qc == Q_hot is a closed HP→TES pipe that
            # bypasses the bus entirely).
            self._distribute_flows(name, fs["Q_th_out"],
                                   None if hot_tes else fs["Q_th_in"],
                                   sys_buses, power_bound=power_bound,
                                   capacity_var=fs.get("cap_power"))
        else:
            node_buses.ht_out.append(fs["Q_th_out"])
            if not hot_tes:
                node_buses.ht_in.append(fs["Q_th_in"])
        if hot_tes:
            logger.info("[HOT-CHARGE] %s: Qc bypasses node bus (charged only "
                        "via HP hot channel)", name)

        # CAPEX: ANF(i, n) × (α × V + β × build), scaled to optimization period.
        # Skipped for non-investable (existing/fixed) tanks — already built, no new spend.
        V = fs["V_m3"]
        build = fs["build"]
        # beta_tes is charged PER TANK: n_tanks = ceil(V_size / unit_tank) for multi-
        # tank sizes (falls back to the binary build for continuous / even-spacing).
        n_tanks_cost = fs.get("n_tanks", build)
        annual_factor = self.inv_calc.annual_factor(lifetime_years)
        if investable and annual_factor > 0:
            sys_buses.capex_terms.append(annual_factor * (alpha_tes * V + beta_tes * n_tanks_cost))

        if cycling_cost_eur > 0:
            Qc = fs["Q_th_in"]
            Qd = fs["Q_th_out"]
            cycling_expr = sum(
                cycling_cost_eur * (Qc[t] + Qd[t]) * self.dt_h for t in self.t
            )
            sys_buses.fuel_cost_terms.append(cycling_expr)

        if investable:
            logger.info(
                "[GEOMETRIC_STORAGE] %s: V=[%.0f, %.0f] m³, alpha=%.0f €/m³, "
                "beta=%.0f €, dT=%.1fK, option_b=%s, annual_factor=%.4f",
                name, V_min_m3, V_max_m3, alpha_tes, beta_tes, delta_T_k,
                option_b, annual_factor,
            )
        else:
            logger.info(
                "[GEOMETRIC_STORAGE] %s: FIXED (non-investable) tank, "
                "E=%.0f MWh, P=%.0f MW → V=%.0f m³ at dT=%.1fK, no CAPEX.",
                name, block.energy_mwh_fixed, block.power_mw_fixed,
                block.V_fixed_m3, delta_T_k,
            )

    # ── Thermal Generator / P2H Assembly ──────────────────────────────────────

    def assemble_thermal_generators(self) -> None:
        """Attach all enabled thermal generators and P2H converters."""
        syscfg = self.cfg.get("system", {})
        gens = syscfg.get("generators", {})
        for key, par in gens.items():
            if not par.get("enabled", False):
                continue
            gpar = self.cfg.get("generators", {}).get(key, {})
            if key == "p2h":
                self._attach_p2h(par, gpar)
            else:
                self._attach_thermal_generator(key, par, gpar)

    def _attach_p2h(self, par: dict[str, Any], gpar: dict[str, Any]) -> None:
        """Attach a Power-to-Heat converter block."""
        eff = float(gpar.get("el_to_th_eff", 0.99))
        cap_th = float(par.get("cap_th_mw", 10.0))
        min_load = float(gpar.get("min_load", 0.0))
        eff_series = gpar.get("eff_series", None)
        part_load_penalty = float(gpar.get("part_load_penalty", 0.0))

        block = P2HBlock("P2H", eff=eff, cap_th_mw=cap_th, min_load=min_load,
                         eff_series=eff_series, part_load_penalty=part_load_penalty)
        fs = block.attach(self.m, self.t, self.cfg, {})
        self.buses.el_in.append(fs["P_el_in"])
        self.buses.ht_out.append(fs["Q_th_out"])

        p2h_co2 = self.co2_calc.calculate_grid_electricity_emissions(fs["P_el_in"], "p2h")
        self.m.co2_component_costs["P2H"] = p2h_co2.to_dict()

    def _attach_thermal_generator(
        self, key: str, par: dict[str, Any], gpar: dict[str, Any]
    ) -> None:
        """Attach a fuel-fired thermal generator or CHP block."""
        block = ThermalGeneratorBlock(
            key.upper(),
            th_eff=float(gpar.get("th_eff", 0.9)),
            el_eff=gpar.get("el_eff", None),
            cap_th_mw=float(par.get("cap_th_mw", 10.0)),
            min_load_fraction=float(gpar.get("min_load", 0.0)),
            min_uptime_h=float(gpar.get("min_uptime_h", 0.0)),
            min_downtime_h=float(gpar.get("min_downtime_h", 0.0)),
            max_ramp_up_mw_per_h=gpar.get("max_ramp_up_mw_per_h"),
            max_ramp_down_mw_per_h=gpar.get("max_ramp_down_mw_per_h"),
            startup_cost_eur=float(gpar.get("startup_cost_eur", 0.0)),
        )
        fs = block.attach(self.m, self.t, self.cfg, {})
        self.buses.ht_out.append(fs["Q_th_out"])
        if fs.get("P_el_out") is not None:
            self.buses.el_out.append(fs["P_el_out"])

        fuel_bus = gpar.get("fuel_bus", "gas")
        price = self._pfuel(fuel_bus, 0.0)
        ef = self._efuel(fuel_bus, 0.0)

        bus_map = {
            "gas": self.buses.gas_in,
            "biomass": self.buses.bio_in,
            "waste": self.buses.waste_in,
        }
        bus_map.get(fuel_bus, self.buses.gas_in).append(fs["fuel_in"])

        fuel_cost_expr = sum(fs["fuel_in"][t] * price * self.dt_h for t in self.t)
        self.buses.fuel_cost_terms.append(fuel_cost_expr)

        if fs.get("startup_var") is not None and fs.get("startup_cost_eur", 0.0) > 0:
            startup_expr = fs["startup_cost_eur"] * sum(fs["startup_var"][t] for t in self.t)
            self.buses.fuel_cost_terms.append(startup_expr)
            logger.info(
                "[ASSEMBLE] %s: startup cost %.0f EUR/start added to objective.",
                key.upper(), fs["startup_cost_eur"],
            )

        comp_name = key.upper()
        is_chp = fs.get("P_el_out") is not None
        th_eff = float(gpar.get("th_eff", 0.9))
        el_eff = float(gpar.get("el_eff", 0.0)) if is_chp else 0.0

        gen_co2 = self.co2_calc.calculate_fuel_emissions(
            fuel_var=fs["fuel_in"],
            fuel_ef_kg_per_mwh=ef,
            is_chp=is_chp,
            th_eff=th_eff,
            el_eff=el_eff,
            fuel_bus=fuel_bus,
        )
        gen_co2_dict = gen_co2.to_dict()
        gen_co2_dict.update({"th_eff": th_eff, "el_eff": el_eff if is_chp else None, "fuel_bus": fuel_bus})
        self.m.co2_component_costs[comp_name] = gen_co2_dict
        self.buses.fuel_co2_terms.append(gen_co2.total_kg)

    # ── Storage helpers ────────────────────────────────────────────────────────

    def _resolve_storage_investment(self, sto_cfg, storage_defaults):
        """Merge investment config and resolve capacity bounds."""
        sto_defaults = storage_defaults.get("investment_defaults", {})
        sto_inv = dict(sto_defaults)
        sto_inv.update(sto_cfg.get("investment", {}))
        invest_enabled = bool(sto_inv.get("enabled", False))

        e_cap_min = float(sto_inv.get("energy_capacity_min_mwh", sto_cfg.get("min_energy_mwh", 0.0)))
        e_cap_max = float(sto_inv.get("energy_capacity_max_mwh", sto_cfg.get("max_energy_mwh", 50000.0)))
        p_cap_min = float(sto_inv.get("power_capacity_min_mw", sto_cfg.get("min_power_mw", 0.0)))
        p_cap_max = float(sto_inv.get("power_capacity_max_mw", sto_cfg.get("max_power_mw", DEFAULT_STORAGE_POWER_MW)))
        e_cap_init = float(
            sto_inv.get(
                "initial_energy_capacity_mwh",
                sto_cfg.get("max_energy_mwh", e_cap_max)
                if not invest_enabled
                else max(e_cap_min, min(e_cap_max, sto_cfg.get("max_energy_mwh", e_cap_max))),
            )
        )
        p_cap_init = float(
            sto_inv.get(
                "initial_power_capacity_mw",
                sto_cfg.get("max_power_mw", p_cap_max)
                if not invest_enabled
                else max(p_cap_min, min(p_cap_max, sto_cfg.get("max_power_mw", p_cap_max))),
            )
        )
        return sto_inv, invest_enabled, (e_cap_min, e_cap_max, p_cap_min, p_cap_max, e_cap_init, p_cap_init)

    def _resolve_soc_init(self, sto_cfg, storage_defaults) -> float:
        """Determine initial state-of-charge from config or time series."""
        inputs_cfg = self.cfg.get("inputs", {})
        soc_init = sto_cfg.get("soc0_mwh")
        if soc_init is None and "soc0_mwh" in storage_defaults:
            soc_init = storage_defaults.get("soc0_mwh")
        if "SOC_init" in inputs_cfg:
            soc_init = inputs_cfg["SOC_init"]
        elif "SOC_init" in sto_cfg:
            soc_init = sto_cfg["SOC_init"]
        else:
            soc_init_series = self.column_series("SOC_init")
            if soc_init_series:
                soc_init = soc_init_series[0]
        return float(soc_init if soc_init is not None else 0.0)

    def _resolve_terminal_policy(self, sto_cfg, storage_defaults, soc_init, terminal_target_override):
        """Determine terminal SOC policy and target from config."""
        horizon_cfg = self.cfg.get("scenario", {}).get("horizon", {})
        enforce_terminal = bool(horizon_cfg.get("enforce", True))
        terminal_cfg = sto_cfg.get("terminal", {})
        terminal_policy_raw = str(terminal_cfg.get("policy", "")).lower()
        terminal_state = str(terminal_cfg.get("state", sto_cfg.get("terminal_state", ""))).strip().lower()
        terminal_target_cfg = terminal_cfg.get("target_mwh", terminal_cfg.get("target"))
        if terminal_target_cfg is None and "terminal_soc_mwh" in sto_cfg:
            terminal_target_cfg = float(sto_cfg["terminal_soc_mwh"])
        if not terminal_state:
            # If policy is explicitly "free", always respect it
            if terminal_policy_raw == "free":
                terminal_state = "free"
            # If an explicit binding policy and target are given, treat as "target"
            elif terminal_policy_raw in {"equal", "geq", "soft"} and terminal_target_cfg is not None:
                terminal_state = "target"
            else:
                terminal_state = "free" if not enforce_terminal else "cyclic"
        # Also override: if policy is explicitly "free" and state wasn't set to target/cyclic, force free
        elif terminal_policy_raw == "free" and terminal_state in {"cyclic"}:
            terminal_state = "free"
        if terminal_state not in {"free", "cyclic", "target"}:
            raise ValueError("storage.terminal.state/terminal_state must be one of: free, cyclic, target")
        if terminal_policy_raw and terminal_policy_raw not in {"equal", "geq", "free", "value", "soft"}:
            raise ValueError("storage.terminal.policy must be one of: equal, geq, free, value, soft")

        terminal_policy = "free" if terminal_state == "free" else (terminal_policy_raw or "equal")
        if terminal_state == "free":
            terminal_target_val: float | None = None
        elif terminal_state == "cyclic":
            if not terminal_policy_raw:
                terminal_policy = "equal"
            terminal_target_val = None if terminal_policy == "value" else (
                float(terminal_target_cfg) if terminal_target_cfg is not None else float(soc_init)
            )
        else:
            if terminal_target_cfg is None:
                terminal_target_cfg = soc_init
            terminal_target_val = float(terminal_target_cfg)
            if terminal_policy not in {"equal", "geq", "value", "soft"}:
                terminal_policy = "equal"

        if terminal_target_override is not None:
            terminal_target_val = float(terminal_target_override)

        logger.info("[ASSEMBLE] Storage terminal configuration:")
        logger.info("  - terminal_state: %s", terminal_state)
        logger.info("  - terminal_policy: %s", terminal_policy)
        logger.info("  - soc_init: %s", soc_init)
        logger.info("  - terminal_target_val: %s", terminal_target_val)
        return terminal_policy, terminal_target_val

    def _resolve_power_energy_coupling(self, sto_cfg, storage_defaults) -> float | None:
        """Resolve optional power/energy coupling constraint."""
        coupling_factor = storage_defaults.get("power_energy_coupling")
        if "power_energy_coupling" in sto_cfg:
            coupling_factor = sto_cfg.get("power_energy_coupling")
        if coupling_factor is None:
            return None
        result = float(coupling_factor)
        if result <= 0:
            raise ValueError("storage.power_energy_coupling must be positive when provided")
        return result

    def _register_storage_references(self, fs: dict[str, Any], terminal_policy: str, name: str = "TES") -> None:
        """Register Pyomo References for storage variables on the model."""
        for attr in [
            f"{name}_SOC", f"{name}_charge_mode", f"{name}_discharge_mode", f"{name}_active",
            f"{name}_soc_low", f"{name}_soc_high", f"{name}_soc_split",
            f"{name}_terminal_slack_pos", f"{name}_terminal_slack_neg", f"{name}_terminal_soft",
        ]:
            if hasattr(self.m, attr):
                self.m.del_component(getattr(self.m, attr))

        setattr(self.m, f"{name}_SOC", pyo.Reference(fs["SOC"]))
        setattr(self.m, f"{name}_charge_mode", pyo.Reference(fs["charge_mode"]))
        setattr(self.m, f"{name}_discharge_mode", pyo.Reference(fs["discharge_mode"]))
        setattr(self.m, f"{name}_active", pyo.Reference(fs["active"]))
        setattr(self.m, f"{name}_terminal_policy", terminal_policy)

    def _build_terminal_value_term(
        self, fs, sto_cfg, storage_defaults, terminal_policy, terminal_target_val,
        invest_enabled, e_cap_init, e_cap_max, soc_init, name: str = "TES",
    ):
        """Build the terminal value expression and attach hard constraints to model."""
        terminal_cfg = sto_cfg.get("terminal", {})
        terminal_defs = storage_defaults.get("terminal_defaults", {})
        last_t = self.t.last()

        avg_price = sum(self.table["strompreis_EUR_MWh"]) / len(self.table) if len(self.table) > 0 else 50.0
        salvage_cfg = terminal_cfg.get("salvage_price_eur_mwh") or terminal_defs.get("salvage_price_eur_mwh")
        salvage_price = float(salvage_cfg) if salvage_cfg is not None else avg_price
        penalty_cfg = terminal_cfg.get("soft_penalty_eur_mwh") or terminal_defs.get("soft_penalty_eur_mwh")
        soft_penalty = float(penalty_cfg) if penalty_cfg is not None else (salvage_price * 2)

        terminal_value_term = None

        if terminal_target_val is not None:
            setattr(self.m, f"{name}_terminal_target", pyo.Param(initialize=terminal_target_val))
            target_param = getattr(self.m, f"{name}_terminal_target")

            if terminal_policy == "geq":
                setattr(self.m, f"{name}_terminal", pyo.Constraint(expr=fs["SOC"][last_t] >= target_param))
                logger.info("[ASSEMBLE] Terminal constraint: SOC[%s] >= %.1f MWh (geq)", last_t, terminal_target_val)

            elif terminal_policy == "equal":
                setattr(self.m, f"{name}_terminal", pyo.Constraint(expr=fs["SOC"][last_t] == target_param))
                logger.info("[ASSEMBLE] Terminal constraint: SOC[%s] == %.1f MWh (equal)", last_t, terminal_target_val)

            elif terminal_policy == "value":
                terminal_value_term = self._build_value_function(
                    fs, terminal_defs, salvage_price, last_t, invest_enabled, e_cap_init, e_cap_max, soc_init,
                    name=name,
                )

            elif terminal_policy == "soft":
                setattr(self.m, f"{name}_terminal_slack_pos", pyo.Var(domain=pyo.NonNegativeReals))
                setattr(self.m, f"{name}_terminal_slack_neg", pyo.Var(domain=pyo.NonNegativeReals))
                setattr(self.m, f"{name}_terminal_soft", pyo.Constraint(
                    expr=fs["SOC"][last_t] + getattr(self.m, f"{name}_terminal_slack_neg") - getattr(self.m, f"{name}_terminal_slack_pos") == target_param
                ))
                terminal_value_term = (
                    soft_penalty * getattr(self.m, f"{name}_terminal_slack_neg")
                    + (soft_penalty * 0.5) * getattr(self.m, f"{name}_terminal_slack_pos")
                )
                logger.info("[ASSEMBLE] Soft terminal constraint: target=%.1f, penalty=%.2f", terminal_target_val, soft_penalty)
        else:
            for attr in (f"{name}_terminal", f"{name}_terminal_target"):
                if hasattr(self.m, attr):
                    delattr(self.m, attr)

            if terminal_policy == "value":
                terminal_value_term = self._build_value_function(
                    fs, terminal_defs, salvage_price, last_t, invest_enabled, e_cap_init, e_cap_max, soc_init
                )
            else:
                logger.info("[ASSEMBLE] No terminal constraint (policy: free)")

        return terminal_value_term

    def _build_value_function(self, fs, terminal_defs, salvage_price, last_t,
                               invest_enabled, e_cap_init, e_cap_max, soc_init, name: str = "TES"):
        """Create the salvage value expression for the 'value' terminal policy."""
        value_func_type = str(terminal_defs.get("value_function_type", "constant")).lower()
        decay = float(terminal_defs.get("diminishing_decay", 0.3))

        if value_func_type == "diminishing" and decay > 0:
            soc_max = float(e_cap_init if not invest_enabled else e_cap_max)
            threshold = 0.5 * soc_max

            if soc_init > soc_max:
                logger.info("[ASSEMBLE] soc_init (%.1f) > soc_max (%.1f); adjusting.", soc_init, soc_max)
                soc_max = max(soc_max, soc_init * 1.1)
                threshold = 0.5 * soc_max

            setattr(self.m, f"{name}_soc_low", pyo.Var(domain=pyo.NonNegativeReals, bounds=(0, threshold)))
            setattr(self.m, f"{name}_soc_high", pyo.Var(domain=pyo.NonNegativeReals, bounds=(0, soc_max - threshold)))
            setattr(self.m, f"{name}_soc_split", pyo.Constraint(
                expr=fs["SOC"][last_t] == getattr(self.m, f"{name}_soc_low") + getattr(self.m, f"{name}_soc_high")
            ))

            price_low = salvage_price
            price_high = salvage_price * (1 - decay)
            logger.info("[ASSEMBLE] Diminishing terminal value: price_low=%.2f, price_high=%.2f", price_low, price_high)
            return -(price_low * getattr(self.m, f"{name}_soc_low") + price_high * getattr(self.m, f"{name}_soc_high"))

        logger.info("[ASSEMBLE] Constant terminal value: salvage_price=%.2f EUR/MWh", salvage_price)
        return -salvage_price * fs["SOC"][last_t]
