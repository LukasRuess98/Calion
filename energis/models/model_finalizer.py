"""
Model finalization for the EnerGIS optimization model.

Extracts the three post-assembly steps from build_model() into a focused
ModelFinalizer class:

1. integrate_network()         – attach optional thermal district network
2. add_balance_constraints()   – bus balance + grid market constraints
3. build_and_set_objective()   – calculate all costs and set objective

Extracted from system_builder.py to give build_model() a clean
Setup → Assembly → Finalization structure.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from energis.logging_config import get_logger

logger = get_logger(__name__)

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_PYOMO = False
    pyo = None

from energis.utils.config_utils import normalize_thermal_network_config
from .component_assembler import BusConnections
from .constraint_builder import add_bus_balance_constraints, add_grid_market_constraints, create_objective
from .cost_calculator import (
    calculate_energy_costs,
    calculate_co2_costs,
    calculate_demand_charge,
    calculate_investment_costs,
    calculate_fuel_costs,
    calculate_dump_costs,
    aggregate_co2_emissions,
    store_cost_expressions_on_model,
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
    def from_config(cfg: Dict[str, Any]) -> "CostFlags":
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
    """B3 — Raise ValueError with descriptive message if network is fundamentally infeasible.

    Checks performed (all use already-loaded data — no file I/O):
    - At least one producer node exists
    - All pipe endpoints reference existing nodes
    - All pipe diameters are positive
    - Consumer nodes have demand_column or demand_fraction specified
    """
    issues = []
    nodes = network_mgr.nodes
    pipes = network_mgr.pipes

    # 1. At least one producer node
    producer_ids = [nid for nid, n in nodes.items() if n.get('type') == 'producer']
    if not producer_ids:
        issues.append("No producer node found in topology (need at least one)")

    # 2. Pipe endpoints reference existing nodes
    for pipe_id, pipe_cfg in pipes.items():
        fn = pipe_cfg.get('from_node')
        tn = pipe_cfg.get('to_node')
        if fn and fn not in nodes:
            issues.append(f"Pipe '{pipe_id}': from_node '{fn}' not in node list")
        if tn and tn not in nodes:
            issues.append(f"Pipe '{pipe_id}': to_node '{tn}' not in node list")

        # 3. Positive diameters
        diam = pipe_cfg.get('current_diameter_supply_mm') or pipe_cfg.get('diameter_mm', 0)
        if float(diam or 0) <= 0:
            issues.append(
                f"Pipe '{pipe_id}': diameter is {diam!r} (must be > 0)"
            )

    # 4. Consumer demand info
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

    logger.info(
        "[PREFLIGHT] Network OK: %d nodes, %d pipes",
        len(nodes),
        len(pipes),
    )


# ─── Model Finalizer ──────────────────────────────────────────────────────────

class ModelFinalizer:
    """Finalizes a Pyomo model after component assembly.

    Usage::

        flags = CostFlags.from_config(cfg)
        finalizer = ModelFinalizer(m, cfg, table, buses, dt_h, flags)
        finalizer.integrate_network()
        finalizer.add_balance_constraints()
        finalizer.build_and_set_objective()
    """

    def __init__(
        self,
        model: Any,
        cfg: Dict[str, Any],
        table: Any,
        buses: BusConnections,
        dt_h: float,
        flags: CostFlags,
    ) -> None:
        self.m = model
        self.cfg = cfg
        self.table = table
        self.buses = buses
        self.dt_h = dt_h
        self.flags = flags
        self.T = len(table)

    # ── Network Integration ────────────────────────────────────────────────────

    def integrate_network(self) -> None:
        """Attach an optional thermal district network to the model.

        Reads the thermal_network config section, loads the topology if
        enabled, calls NetworkManager.attach_to_model(), and stores a
        reference to the manager on the model for later result extraction.
        Sets m._network_enabled to True/False accordingly.
        """
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
                logger.info("[FINALIZE] WARNING: Thermal network failed to load (check topology file)")
                logger.info("[FINALIZE] Continuing without thermal network...")
                self.m._network_enabled = False
                return

            # B3: Pre-flight feasibility check before building / solving
            _preflight_network_check(network_mgr)

            buses_dict = {
                "heat": {"in": self.buses.ht_in, "out": self.buses.ht_out},
                "electricity": {"in": self.buses.el_in, "out": self.buses.el_out},
            }
            # Store dt_h on model so get_results() can compute correct MWh totals
            self.m.dt_h = self.dt_h

            network_results = network_mgr.attach_to_model(self.m, self.m.t, buses_dict)

            # Accept single-node fallback (pipes=0) as well as multi-pipe topologies
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
            logger.info("[FINALIZE] ERROR: Failed to integrate thermal network: %s", exc)
            logger.info("[FINALIZE] Continuing without thermal network...")
            self.m._network_enabled = False
            traceback.print_exc()

    # ── Balance Constraints ────────────────────────────────────────────────────

    def add_balance_constraints(self) -> None:
        """Add electricity/heat bus balance and grid market constraints."""
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

        demand_term = calculate_demand_charge(m, include_demand=flags.include_demand)

        capex_total, activation_total, tie_break_total, storage_install_total = calculate_investment_costs(
            capex_terms=buses.capex_terms,
            activation_terms=buses.activation_terms,
            tie_breaker_terms=buses.tie_breaker_terms,
            storage_install_terms=buses.storage_install_terms,
            include_capex=flags.include_capex,
            include_activation=flags.include_activation,
            include_tie_breaker=flags.include_tie_breaker,
        )

        co2_term = co2_cost_total if flags.include_co2 else 0
        terminal_value = getattr(m, "terminal_value_term", None) or 0

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
        )
