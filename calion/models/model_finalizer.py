"""
Model finalization for the CALION optimization model.

Extracts the three post-assembly steps from build_model() into a focused
ModelFinalizer class:

1. integrate_network()         - attach optional thermal district network
2. add_balance_constraints()   - bus balance + grid market constraints
3. build_and_set_objective()   - calculate all costs and set objective

Supports both legacy (global BusConnections) and unified (per-node
SystemBusConnections) configurations.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from calion.logging_config import get_logger

logger = get_logger(__name__)

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_PYOMO = False
    pyo = None

from calion.utils.config_utils import normalize_thermal_network_config

from .component_assembler import BusConnections, SystemBusConnections
from .constraint_builder import (
    add_bus_balance_constraints,
    add_grid_market_constraints,
    add_per_node_heat_balance,
    create_objective,
)
from .cost_calculator import (
    aggregate_co2_emissions,
    calculate_co2_costs,
    calculate_demand_charge,
    calculate_dump_costs,
    calculate_energy_costs,
    calculate_fuel_costs,
    calculate_investment_costs,
    store_cost_expressions_on_model,
)
from .cost_calculator_zonal import (
    calculate_demand_charge_zonal,
    calculate_demand_charge_zonal_dynamic,
)
from .network_manager import NetworkManager

# ─── Cost Flags ───────────────────────────────────────────────────────────────

@dataclass
class CostFlags:
    """Boolean flags controlling which cost terms enter the objective."""

    include_gridcost: bool = False
    include_demand: bool = True
    include_co2: bool = True
    include_capex: bool = True
    include_activation: bool = True
    include_tie_breaker: bool = True
    include_storage_install: bool = True

    @staticmethod
    def from_config(cfg: dict[str, Any]) -> CostFlags:
        """Parse cost flags from the merged configuration dict."""
        costs = cfg.get("costs", {})
        grid = cfg.get("grid", {})
        return CostFlags(
            include_gridcost=bool(costs.get("include_gridcost_in_energy", False)),
            include_demand=bool(
                grid.get(
                    "include_demand_charge_in_rh",
                    costs.get("include_demand_charge_in_rh", True),
                )
            ),
            include_co2=bool(costs.get("include_co2_cost_in_objective", True)),
            include_capex=bool(costs.get("include_capex_costs", True)),
            include_activation=bool(costs.get("include_activation_costs", True)),
            include_tie_breaker=bool(costs.get("include_tie_breaker_costs", True)),
            include_storage_install=bool(costs.get("include_storage_installation_costs", True)),
        )


# ─── Pre-flight Check ─────────────────────────────────────────────────────────

def _preflight_network_check(network_mgr) -> None:
    """B3 - Raise ValueError with descriptive message if network is fundamentally infeasible."""
    issues = []
    nodes = network_mgr.nodes
    pipes = network_mgr.pipes

    producer_ids = [nid for nid, n in nodes.items() if n.get('type') in ('producer', 'mixed')]
    if not producer_ids:
        issues.append("No producer node found in topology (need at least one)")

    for pipe_id, pipe_cfg in pipes.items():
        fn = pipe_cfg.get('from_node')
        tn = pipe_cfg.get('to_node')
        if fn and fn not in nodes:
            issues.append(f"Pipe '{pipe_id}': from_node '{fn}' not in node list")
        if tn and tn not in nodes:
            issues.append(f"Pipe '{pipe_id}': to_node '{tn}' not in node list")

        diam = pipe_cfg.get('current_diameter_supply_mm') or pipe_cfg.get('diameter_mm', 0)
        if float(diam or 0) <= 0:
            issues.append(f"Pipe '{pipe_id}': diameter is {diam!r} (must be > 0)")

    for node_id, node_cfg in nodes.items():
        if node_cfg.get('type') != 'consumer':
            continue
        has_demand = (
            node_cfg.get('demand_column')
            or node_cfg.get('demand_fraction') is not None
            or node_cfg.get('Q_demand') is not None
        )
        if not has_demand:
            issues.append(
                f"Consumer node '{node_id}': missing demand_column, demand_fraction, or Q_demand"
            )

    if issues:
        raise ValueError(
            f"Network preflight failed ({len(issues)} issue(s)):\n"
            + "\n".join(f"  - {i}" for i in issues)
        )

    logger.info("[PREFLIGHT] Network OK: %d nodes, %d pipes", len(nodes), len(pipes))


# ─── Model Finalizer ──────────────────────────────────────────────────────────

class ModelFinalizer:
    """Finalizes a Pyomo model after component assembly.

    Supports both legacy mode (flat BusConnections) and unified mode
    (per-node SystemBusConnections with optional multi-node network).
    """

    def __init__(
        self,
        model: Any,
        cfg: dict[str, Any],
        table: Any,
        buses: BusConnections,
        dt_h: float,
        flags: CostFlags,
        *,
        unified_config: Any | None = None,
        system_buses: SystemBusConnections | None = None,
    ) -> None:
        self.m = model
        self.cfg = cfg
        self.table = table
        self.buses = buses
        self.dt_h = dt_h
        self.flags = flags
        self.T = len(table)
        self.unified_config = unified_config
        self.system_buses = system_buses

    @property
    def _is_unified(self) -> bool:
        return self.unified_config is not None

    @property
    def _is_multinode(self) -> bool:
        return self._is_unified and not self.unified_config.is_copperplate

    # ── Network Integration ────────────────────────────────────────────────────

    def integrate_network(self) -> None:
        """Attach an optional thermal district network to the model.

        For unified multi-node configs: builds NetworkManager from the unified
        config's pipes/nodes and attaches per-node bus connections.

        For unified copperplate: skips network integration entirely (no pipes).

        For legacy configs: uses the thermal_network config section as before.
        """
        if self._is_unified:
            self._integrate_network_unified()
        else:
            self._integrate_network_legacy()

    def _integrate_network_unified(self) -> None:
        """Network integration for unified config."""
        ucfg = self.unified_config

        if ucfg.is_copperplate:
            self.m._network_enabled = False
            logger.info("[FINALIZE] Copperplate mode — no network physics")
            return

        # Multi-node: build NetworkManager from unified config pipes/nodes
        logger.info("[FINALIZE] Integrating multi-node network from unified config...")

        # Convert unified config to thermal_network format for NetworkManager
        network_cfg = self._unified_to_network_cfg(ucfg)
        cfg_with_network = dict(self.cfg)
        cfg_with_network["thermal_network"] = network_cfg

        config_dir = self.cfg.get("_config_dir", Path.cwd())
        if not isinstance(config_dir, Path):
            config_dir = Path(config_dir) if config_dir else Path.cwd()

        has_outdoor_temp = hasattr(self.m, "outdoor_temp") and self.m.outdoor_temp is not None
        if has_outdoor_temp:
            network_cfg.setdefault("use_outdoor_temperature", True)

        try:
            network_mgr = NetworkManager(cfg_with_network, config_dir=config_dir)

            if not network_mgr.network_enabled:
                logger.info("[FINALIZE] Network failed to initialize, continuing without")
                self.m._network_enabled = False
                return

            _preflight_network_check(network_mgr)

            # Build buses dict for NetworkManager from per-node connections
            buses_dict = {
                "heat": {"in": self.buses.ht_in, "out": self.buses.ht_out},
                "electricity": {"in": self.buses.el_in, "out": self.buses.el_out},
            }
            self.m.dt_h = self.dt_h

            network_results = network_mgr.attach_to_model(self.m, self.m.t, buses_dict)

            # Add pump power flows to electricity bus
            pump_el_flows = network_results.get('pump_el_flows', [])
            if pump_el_flows:
                self.buses.el_in.extend(pump_el_flows)
                logger.info(
                    "[FINALIZE] Added %d aggregated producer pump load(s) to electricity bus (el_in)",
                    len(pump_el_flows)
                )

            has_nodes = len(network_results.get("nodes", {})) > 0
            if network_results and has_nodes:
                self.m._network_manager = network_mgr
                self.m._network_enabled = True
                logger.info(
                    "[FINALIZE] Multi-node network integrated: %d pipes, %d nodes",
                    len(network_results.get("pipes", {})),
                    len(network_results.get("nodes", {})),
                )
            else:
                self.m._network_enabled = False

        except Exception as exc:
            logger.error("[FINALIZE] Failed to integrate network: %s", exc)
            self.m._network_enabled = False
            logger.debug(traceback.format_exc())

    def _unified_to_network_cfg(self, ucfg) -> dict[str, Any]:
        """Convert unified config to thermal_network dict for NetworkManager."""
        nodes_list = []
        raw_nodes = self.cfg.get("network", {}).get("nodes", {})
        if not isinstance(raw_nodes, dict):
            raw_nodes = {}
        for nid, node in ucfg.nodes.items():
            node_dict: dict[str, Any] = {
                "id": nid,
                "type": node.type,
            }
            # Forward multi-consumer demand list (consumers: [...] in YAML)
            if node.demands:
                node_dict["consumers"] = [
                    {
                        "column": d.column,
                        **(
                            {"demand_fraction": d.demand_fraction}
                            if d.demand_fraction is not None else {}
                        ),
                    }
                    for d in node.demands
                ]
            elif node.demand is not None:
                node_dict["demand_column"] = node.demand.column
            if node.demand_fraction is not None:
                node_dict["demand_fraction"] = node.demand_fraction
            if node.assets:
                node_dict["components"] = {aid: {} for aid in node.assets}

            # Preserve node-level thermal tuning fields from raw unified config.
            # These keys are optional and used by thermal node constraints.
            raw_node = raw_nodes.get(nid, {})
            if isinstance(raw_node, dict):
                for key in (
                    "return_temp_c",
                    "return_temp_profile",
                    "return_temp_range",
                    "return_temp_load_factor",
                    "return_temp_load_mode",
                    "return_temp_load_relax_c",
                    "return_temp_apply_on_passthrough",
                    "return_temp_frame_on_passthrough",
                    "return_temp_ref_shift_c",
                    "return_temp_peak_floor_mw",
                    "return_temp_ref_profile",
                    "return_temp_band_c",
                    "return_temp_band_profile",
                    "peak_demand_mw",
                    # Return model V2 / soft-anchor / identification fields
                    "return_model_mode",
                    "return_v2_params",
                    "return_state_init_c",
                    "return_v2_outdoor_profile",
                    "return_state_penalty_eur_per_c",
                    "return_link_penalty_eur_per_c",
                    "flow_anchor_profile_kg_s",
                    "flow_anchor_penalty_eur_per_kg_s",
                    "return_temp_soft_anchor_enabled",
                    "return_temp_soft_anchor_weight_frame",
                    "return_temp_soft_anchor_weight_load",
                    # Summer feasibility + diagnostics fields
                    "allow_heat_demand_slack",
                    "max_heat_demand_slack_frac",
                    "max_heat_demand_slack_abs_mw",
                    "demand_slack_penalty_eur_per_mwh",
                    "min_demand_mw",
                    "min_demand_only_when_positive",
                    # Node-level Phase-1/state-constraint overrides
                    "state_validation",
                    # Per-node supply temperature offset for L3-MILP degeneracy breaking
                    "T_supply_offset_c",
                    # Per-node pressure setpoint (primary/secondary producer) and
                    # minimum-required pressure (consumer) -- network_manager.py::
                    # _link_pressure_propagation reads `pressure.setpoint_bar` /
                    # `pressure.min_required_bar`. Was missing from this whitelist
                    # entirely, so BOTH silently fell back to network_manager.py's
                    # hardcoded defaults (10.0 bar / "no constraint") regardless of
                    # what any YAML configured -- affects every network, not just
                    # this one (e.g. Stadtbach_topo.yaml's explicit 16.0 bar j_hkw
                    # setpoint never actually took effect either).
                    "pressure",
                    # Real DXF-derived count of physical Uebergabestationen this
                    # node's lumped demand represents -- read by thermal_node.py's
                    # opt-in lateral-pipe-loss term (`pressure.lateral_length_m`,
                    # both added together 2026-07-29, see memory
                    # project_memmingen_pump_pressure_study). Also missing from
                    # this whitelist by default; add lateral_length_m INSIDE the
                    # `pressure` dict above instead of a new top-level key, since
                    # that key is already forwarded whole.
                    "n_transfer_stations",
                ):
                    if key in raw_node:
                        node_dict[key] = raw_node[key]
            # Also propagate from NodeConfig attribute (belt-and-suspenders)
            if getattr(node, 'T_supply_offset_c', 0.0) != 0.0 and 'T_supply_offset_c' not in node_dict:
                node_dict['T_supply_offset_c'] = node.T_supply_offset_c
            nodes_list.append(node_dict)

        pipes_list = []
        raw_pipes = self.cfg.get("network", {}).get("pipes", {})
        if not isinstance(raw_pipes, dict):
            raw_pipes = {}
        for pid, pipe in ucfg.pipes.items():
            pipe_dict = {
                "id": pid,
                "from_node": pipe.from_node,
                "to_node": pipe.to_node,
                "length_m": pipe.length_m,
                "current_diameter_supply_mm": pipe.diameter_mm,
                "diameter_mm": pipe.diameter_mm,
                "u_value_supply_w_per_m_k": pipe.u_value_supply_w_per_m_k,
                "u_value_return_w_per_m_k": pipe.u_value_return_w_per_m_k,
                "bidirectional": pipe.bidirectional,
            }
            raw_pipe = raw_pipes.get(pid, {})
            if isinstance(raw_pipe, dict):
                for key in (
                    # Existing runtime tuning fields
                    "heat_loss_flow_guard_kg_s",
                    "stagnation_mode",
                    "stagnation_flow_threshold_kg_s",
                    # Summer warmup relax fields
                    "summer_warmup_hours",
                    "summer_warmup_penalty_eur_per_mwh",
                    "summer_warmup_flow_relax_kg_s",
                    "summer_warmup_flow_penalty_eur_per_kg_s",
                    # Optional per-pipe overrides that should survive unified conversion
                    "max_velocity_m_s",
                    "state_validation",
                ):
                    if key in raw_pipe:
                        pipe_dict[key] = raw_pipe[key]
            pipes_list.append(pipe_dict)

        net_cfg = self.cfg.get('network', {})
        tn_cfg = self.cfg.get('thermal_network', {})
        physics_cfg = net_cfg.get('physics', tn_cfg.get('physics', {}))
        lin_cfg = (
            net_cfg.get('linearization')
            or tn_cfg.get('linearization')
            or {}
        )
        temperature_frame_cfg = (
            net_cfg.get("temperature_frame")
            or tn_cfg.get("temperature_frame")
            or {}
        )
        # Pass heating curve from network section into thermal_network.parameters
        # so NetworkManager._setup_temperatures() picks it up.
        heating_curve_cfg = net_cfg.get('heating_curve', tn_cfg.get('heating_curve', {}))
        parameters: dict = {
            "supply_temp_nominal_c": ucfg.physics.supply_temp_c,
            "return_temp_nominal_c": ucfg.physics.return_temp_c,
            "ground_temp_default_c": ucfg.physics.ground_temp_c,
        }
        if heating_curve_cfg:
            parameters["heating_curve"] = heating_curve_cfg
        raw_parameters = net_cfg.get("parameters", tn_cfg.get("parameters", {}))
        if isinstance(raw_parameters, dict):
            parameters.update(raw_parameters)
        return {
            "enabled": True,
            "nodes": nodes_list,
            "pipes": pipes_list,
            "parameters": parameters,
            "milp_linearize": (
                tn_cfg.get('milp_linearize', False)
                or net_cfg.get('milp_linearize', False)
                or self.cfg.get('scenario', {}).get('milp_linearize', False)
            ),
            "temperature_linearize": (
                tn_cfg.get('temperature_linearize',
                net_cfg.get('temperature_linearize',
                self.cfg.get('scenario', {}).get('temperature_linearize', None)))
            ),
            # L3+ spatial temperature propagation (2026-07-08) -- was never
            # forwarded here at all, so 'network.temperature_propagation: true'
            # in the YAML was silently dropped before NetworkManager ever saw
            # it (NetworkManager._net_cfg resolves 'thermal_network' over
            # 'network', and this function builds 'thermal_network' fresh).
            "temperature_propagation": (
                tn_cfg.get('temperature_propagation', False)
                or net_cfg.get('temperature_propagation', False)
            ),
            "linearization": lin_cfg,
            "temperature_frame": temperature_frame_cfg,
            "physics": physics_cfg,
            "state_validation": (
                net_cfg.get('state_validation') or tn_cfg.get('state_validation') or {}
            ),
            # primary_producer: designates which producer node gets a fixed P_supply setpoint.
            # Other producers in multi-source networks (e.g. Stadtbach) get floating pressure.
            "primary_producer": (
                net_cfg.get('primary_producer') or tn_cfg.get('primary_producer') or None
            ),
            # Paper 2 F4: TES↔network pressure coupling (spec §4.1.3 edit).
            # Only populated when physics.tes_pressure_coupling is enabled.
            "tes_pressure_coupling": self._build_tes_pressure_coupling(ucfg, physics_cfg),
        }

    def _build_tes_pressure_coupling(self, ucfg, physics_cfg: dict) -> list[dict]:
        """Collect geometric-TES pressure-coupling specs (spec §4.1.3 edit).

        Two modes (physics.tes_pressure_mode), selected once for the whole network:

        - "hydrostatic_support" (legacy elevated-tower model): precompute the h(V)
          PWL breakpoints (h = (4·r²·V/π)^(1/3), concave) so NetworkManager adds
            P_supply[n,t] ≥ p_atm + ρg·h/1e5 + k·Qc(t) − k·Qd(t) − M(1−build)
            P_supply[n,t] ≤ p_max_bar + M(1−build)
        - "same_circuit_buffer" (2026-07-13 default): TES is an in-line buffer on
          the SAME pressurized loop as the network (no HX, no elevated column) ->
          no hydrostatic push term; NetworkManager adds only the vessel rating cap
            P_supply[n,t] ≤ p_max_bar + M(1−build)
          Breakpoints are still returned (cheap) but NetworkManager ignores them
          in this mode.
        """
        import math as _math

        from ..constants import G_ACCEL_M_S2, P_ATM_BAR, RHO_WATER_HOT_KG_M3
        if not physics_cfg.get('tes_pressure_coupling', False):
            return []
        mode = physics_cfg.get('tes_pressure_mode', 'hydrostatic_support')
        if mode not in ('hydrostatic_support', 'same_circuit_buffer'):
            raise ValueError(
                f"physics.tes_pressure_mode must be 'hydrostatic_support' or "
                f"'same_circuit_buffer', got {mode!r}"
            )
        specs = []
        _RHO, _G, _P_ATM = RHO_WATER_HOT_KG_M3, G_ACCEL_M_S2, P_ATM_BAR
        for node_id, node_cfg in ucfg.nodes.items():
            for asset_id in node_cfg.assets:
                asset = ucfg.assets.get(asset_id)
                if asset is None or asset.type != 'geometric_storage':
                    continue
                p = dict(asset.params)
                r_hd = float(p.get('r_hd', 3.0))
                p_max_bar = float(p.get('p_max_bar', 10.0))
                V_max = float(p.get('V_max_m3', 5000.0))
                h_max_p = (p_max_bar - _P_ATM) * 1e5 / (_RHO * _G)
                V_max_p = _math.pi * h_max_p ** 3 / (4.0 * r_hd ** 2)
                V_eff = min(V_max, V_max_p)
                fracs = [0.0, 0.05, 0.2, 0.5, 1.0]
                V_breaks = [f * V_eff for f in fracs]
                h_breaks = [
                    (v * 4.0 * r_hd ** 2 / _math.pi) ** (1.0 / 3.0) if v > 0 else 0.0
                    for v in V_breaks
                ]
                specs.append({
                    'node_id': node_id,
                    'asset_id': asset_id,
                    'mode': mode,
                    'p_max_bar': p_max_bar,
                    'conn_dp_bar_per_mw': float(p.get('conn_dp_bar_per_mw', 0.01)),
                    'V_breaks': V_breaks,
                    'h_breaks': h_breaks,
                })
        return specs

    def _integrate_network_legacy(self) -> None:
        """Network integration for legacy config (unchanged from original)."""
        network_cfg = normalize_thermal_network_config(self.cfg)
        if not network_cfg.get("enabled", False):
            self.m._network_enabled = False
            logger.info("[FINALIZE] Thermal network disabled")
            return

        logger.info("[FINALIZE] Integrating thermal network...")

        config_dir = self.cfg.get("_config_dir", Path.cwd())
        if not isinstance(config_dir, Path):
            config_dir = Path(config_dir) if config_dir else Path.cwd()

        has_outdoor_temp = hasattr(self.m, "outdoor_temp") and self.m.outdoor_temp is not None
        if has_outdoor_temp:
            network_cfg.setdefault("use_outdoor_temperature", True)
            logger.info("[FINALIZE] Outdoor temperature available - heating curve enabled")
        else:
            logger.info("[FINALIZE] No outdoor temperature data - using fixed supply temperature")

        cfg_with_network = dict(self.cfg)
        cfg_with_network["thermal_network"] = network_cfg

        try:
            network_mgr = NetworkManager(cfg_with_network, config_dir=config_dir)

            if not network_mgr.network_enabled:
                logger.warning("[FINALIZE] Thermal network failed to load (check topology file)")
                logger.warning("[FINALIZE] Continuing without thermal network...")
                self.m._network_enabled = False
                return

            _preflight_network_check(network_mgr)

            buses_dict = {
                "heat": {"in": self.buses.ht_in, "out": self.buses.ht_out},
                "electricity": {"in": self.buses.el_in, "out": self.buses.el_out},
            }
            self.m.dt_h = self.dt_h

            network_results = network_mgr.attach_to_model(self.m, self.m.t, buses_dict)

            # Add pump power flows to electricity bus
            pump_el_flows = network_results.get('pump_el_flows', [])
            if pump_el_flows:
                self.buses.el_in.extend(pump_el_flows)
                logger.info(
                    "[FINALIZE] Added %d aggregated producer pump load(s) to electricity bus (el_in)",
                    len(pump_el_flows)
                )

            has_nodes = len(network_results.get("nodes", {})) > 0
            if network_results and has_nodes:
                self.m._network_manager = network_mgr
                self.m._network_enabled = True
                logger.info(
                    "[FINALIZE] Thermal network integrated: %d pipes, %d nodes",
                    len(network_results.get("pipes", {})),
                    len(network_results.get("nodes", {})),
                )
            else:
                logger.info("[FINALIZE] WARNING: Thermal network returned no nodes")
                logger.info("[FINALIZE] Continuing without thermal network...")
                self.m._network_enabled = False

        except Exception as exc:
            logger.error("[FINALIZE] Failed to integrate thermal network: %s", exc)
            logger.warning("[FINALIZE] Continuing without thermal network...")
            self.m._network_enabled = False
            logger.debug(traceback.format_exc())

    # ── Balance Constraints ────────────────────────────────────────────────────

    def add_balance_constraints(self) -> None:
        """Add electricity/heat bus balance and grid market constraints.

        For multi-node unified configs: adds per-node heat balance constraints
        instead of a single global heat balance.

        Electricity balance is always global (single grid connection).
        """
        if self._is_multinode and self.system_buses is not None:
            # Per-node heat balance for multi-node networks
            add_per_node_heat_balance(
                self.m,
                self.system_buses,
                self.unified_config,
            )
            # Global electricity balance (unchanged)
            from .constraint_builder import _add_electricity_balance
            _add_electricity_balance(self.m, self.buses.el_in, self.buses.el_out)
        else:
            # Copperplate or legacy: global heat + electricity balance
            add_bus_balance_constraints(
                self.m,
                self.buses.el_in,
                self.buses.el_out,
                self.buses.ht_in,
                self.buses.ht_out,
            )
        add_grid_market_constraints(self.m)

    # ── Objective ──────────────────────────────────────────────────────────────

    def build_and_set_objective(self) -> None:
        """Calculate all cost terms and set the minimization objective."""
        m = self.m
        flags = self.flags
        buses = self.buses
        table = self.table
        dt_h = self.dt_h
        T = self.T

        base_prices = [float(table["strompreis_EUR_MWh"][i]) for i in range(T)]
        time_steps = list(m.t)

        energy_cost = calculate_energy_costs(
            m, time_steps, base_prices, dt_h=dt_h, include_grid_cost=flags.include_gridcost
        )
        dump_cost = calculate_dump_costs(
            m, time_steps, dt_h=dt_h, dump_cost_eur_per_mwh=float(m.dump_cost.value)
        )
        fuel_costs = calculate_fuel_costs(buses.fuel_cost_terms)

        co2_cost_total, co2_cost_heat_total, co2_cost_elec_total = calculate_co2_costs(
            m.co2_component_costs, co2_price_eur_per_t=float(m.co2_price.value)
        )
        co2_kg_heat_total, co2_kg_elec_total, co2_kg_fuel_heat, co2_kg_fuel_elec, co2_kg_grid_elec = (
            aggregate_co2_emissions(m.co2_component_costs)
        )
        store_cost_expressions_on_model(
            m,
            co2_cost_total=co2_cost_total,
            co2_cost_heat=co2_cost_heat_total,
            co2_cost_elec=co2_cost_elec_total,
            co2_kg_heat=co2_kg_heat_total,
            co2_kg_elec=co2_kg_elec_total,
            co2_kg_fuel_to_heat=co2_kg_fuel_heat,
            co2_kg_fuel_to_elec=co2_kg_fuel_elec,
            co2_kg_grid_to_elec=co2_kg_grid_elec,
        )

        # Legacy compatibility: total CO2 scalars for old reports
        m._co2_grid_expr = sum(m.P_buy[t] * table["grid_co2_kg_MWh"][t - 1] * dt_h for t in m.t)
        m._co2_fuel_expr = sum(buses.fuel_co2_terms) if buses.fuel_co2_terms else 0

        # Zonal-aware demand charge: Use zone-specific tariffs if available
        has_dynamic_costs = hasattr(m, 'zone_demand_charge_ts') and m.zone_demand_charge_ts
        has_zonal_costs = hasattr(m, 'zone_demand_charge') and m.zone_demand_charge
        
        if has_dynamic_costs:
            # Dynamic zonal costs (hourly tariffs from CSV)
            demand_term = calculate_demand_charge_zonal_dynamic(m, include_demand=flags.include_demand)
            logger.debug("Using dynamic zonal demand charges (hourly from CSV)")
        elif has_zonal_costs:
            # Static zonal costs (from YAML configuration)
            demand_term = calculate_demand_charge_zonal(m, include_demand=flags.include_demand)
            logger.debug("Using static zonal demand charges (%d zones)", len(m.zone_demand_charge))
        else:
            # Fallback: Global cost (backward compatibility)
            demand_term = calculate_demand_charge(m, include_demand=flags.include_demand)
            logger.debug("Using global demand charge (no zones defined)")

        capex_total, activation_total, tie_break_total, storage_install_total = calculate_investment_costs(
            capex_terms=buses.capex_terms,
            activation_terms=buses.activation_terms,
            tie_breaker_terms=buses.tie_breaker_terms,
            storage_install_terms=buses.storage_install_terms,
            include_capex=flags.include_capex,
            include_activation=flags.include_activation,
            include_tie_breaker=flags.include_tie_breaker,
            include_storage_install=flags.include_storage_install,
        )

        if not flags.include_storage_install:
            storage_install_total = 0

        co2_term = co2_cost_total if flags.include_co2 else 0
        terminal_value = getattr(m, "terminal_value_term", None) or 0

        # Pipe CAPEX (computed in pipe_pair.py but previously not wired into objective)
        pipe_capex_costs = getattr(m, 'pipe_capex_costs', {})
        if pipe_capex_costs and flags.include_capex:
            pipe_capex_total = sum(pipe_capex_costs.values())
            capex_total = capex_total + pipe_capex_total

        # Demand slack penalties (created by network_manager but previously missing from objective)
        demand_slack_cost = 0
        demand_slack_terms = getattr(m, 'demand_slack_penalty_terms', [])
        if demand_slack_terms:
            T_set = list(m.t)
            for slack_var, penalty in demand_slack_terms:
                demand_slack_cost = demand_slack_cost + sum(
                    slack_var[t] * penalty for t in T_set
                )

        # Soft return-temperature anchors (created in thermal_node).
        return_anchor_cost = 0
        return_anchor_terms = getattr(m, 'return_temp_anchor_penalty_terms', [])
        if return_anchor_terms:
            T_set = list(m.t)
            for slack_var, penalty in return_anchor_terms:
                return_anchor_cost = return_anchor_cost + sum(
                    slack_var[t] * penalty for t in T_set
                )

        # Pressure tie-breaking regularization (created in network_manager's
        # _link_pressure_propagation, opt-in via network.physics.
        # pressure_regularization -- see that function's comment for the
        # rationale). Off by default: empty list, term is 0.
        pressure_reg_cost = 0
        pressure_reg_terms = getattr(m, 'pressure_regularization_terms', [])
        if pressure_reg_terms:
            T_set = list(m.t)
            for p_var, coeff in pressure_reg_terms:
                pressure_reg_cost = pressure_reg_cost + sum(
                    p_var[t] * coeff for t in T_set
                )

        # Lateral-loss PWL tie-break (created in thermal_node.py, 2026-07-30
        # bugfix -- see that module's comment for the "why": without this,
        # a routine MIP gap can leave the weighted-breakpoint interpolation
        # spread across non-adjacent points, reporting values up to ~20x too
        # high despite the flow-link constraint being satisfied).
        lateral_tiebreak_cost = 0
        lateral_tiebreak_terms = getattr(m, 'lateral_tiebreak_terms', [])
        if lateral_tiebreak_terms:
            T_set = list(m.t)
            for dp_var, coeff in lateral_tiebreak_terms:
                lateral_tiebreak_cost = lateral_tiebreak_cost + sum(
                    dp_var[t] * coeff for t in T_set
                )

        create_objective(
            m,
            energy_cost=energy_cost,
            dump_cost=dump_cost,
            fuel_costs=fuel_costs,
            co2_cost=co2_term,
            demand_cost=demand_term,
            capex_cost=capex_total,
            activation_cost=activation_total,
            tie_break_cost=tie_break_total,
            storage_install_cost=storage_install_total,
            terminal_value=terminal_value,
            demand_slack_cost=demand_slack_cost,
            return_anchor_cost=return_anchor_cost,
            pressure_reg_cost=pressure_reg_cost,
            lateral_tiebreak_cost=lateral_tiebreak_cost,
        )
