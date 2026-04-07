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

from .blocks.heat_pump import HeatPumpBlock
from .blocks.p2h import P2HBlock
from .blocks.storage import StorageBlock
from .blocks.stratified_storage import StratifiedStorageBlock
from .blocks.thermal_gen import ThermalGeneratorBlock
from .cop_calculator import calculate_cop_series
from .emissions_calculator import EmissionsCalculator
from .investment_calculator import InvestmentCalculator

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

    # ── public helpers ─────────────────────────────────────────────────────────

    def column_series(self, name: str) -> list[float] | None:
        """Return a table column as a list, or None if absent."""
        if name in self.table.columns:
            return [float(self.table[name][i]) for i in range(self.T)]
        return None

    # ── Unified Assembly (new config) ──────────────────────────────────────────

    def assemble_all(self, ucfg) -> SystemBusConnections:
        """Assemble all components from a UnifiedSystemConfig.

        Iterates over nodes and their assets, attaching each component to the
        correct per-node bus.  Returns a SystemBusConnections with per-node
        heat flows and global electricity / cost terms.

        Args:
            ucfg: A UnifiedSystemConfig instance.

        Returns:
            SystemBusConnections with per-node and system-level bus connections.
        """
        from calion.config.unified_config import unified_generators_defaults

        sys_buses = SystemBusConnections()

        # Build generator defaults lookup for config compatibility
        gen_defaults = unified_generators_defaults(ucfg)

        for node_id, node_cfg in ucfg.nodes.items():
            node_buses = sys_buses.get_or_create_node(node_id)

            for asset_id in node_cfg.assets:
                asset = ucfg.assets.get(asset_id)
                if asset is None:
                    logger.warning("Node '%s': asset '%s' not found, skipping", node_id, asset_id)
                    continue

                if asset.type == "heat_pump":
                    self._attach_hp_from_unified(asset, node_buses, sys_buses)
                elif asset.type == "storage":
                    self._attach_storage_from_unified(asset, node_buses, sys_buses)
                elif asset.type == "thermal_generator":
                    self._attach_generator_from_unified(asset, node_buses, sys_buses, gen_defaults)
                elif asset.type == "p2h":
                    self._attach_p2h_from_unified(asset, node_buses, sys_buses, gen_defaults)
                else:
                    logger.warning("Unknown asset type '%s' for '%s'", asset.type, asset_id)

        return sys_buses

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

        cop_series = calculate_cop_series(self.table, wrg_col, self.cfg, hp_type)

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
        )
        fs = block.attach(self.m, self.t, self.cfg, {})

        # Per-node heat output
        node_buses.ht_out.append(fs["Q_th_out"])
        # Global electricity input
        sys_buses.el_in.append(fs["P_el_in"])

        # Investment costs → system level
        cap_var = fs.get("capacity")
        build_var = fs.get("build")
        if cap_var is not None and build_var is not None:
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

        sto_cfg = {
            "enabled": True,
            "type": p.pop("storage_type", "simple"),
            "max_energy_mwh": p.pop("energy_mwh", DEFAULT_STORAGE_ENERGY_MWH),
            "max_power_mw": p.pop("power_mw", DEFAULT_STORAGE_POWER_MW),
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
            self.assemble_storage()
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
        sys_buses.terminal_value_term = self.buses.terminal_value_term
        self.buses.capex_terms.clear()
        self.buses.activation_terms.clear()
        self.buses.tie_breaker_terms.clear()
        self.buses.storage_install_terms.clear()

    def _attach_generator_from_unified(self, asset, node_buses, sys_buses, gen_defaults):
        """Attach a thermal generator from unified config to per-node buses."""
        p = dict(asset.params)
        name = asset.id.upper()

        th_eff = float(p.get("thermal_efficiency", 0.9))
        el_eff = p.get("el_eff")
        cap_th = float(p.get("capacity_mw", 10.0))

        block = ThermalGeneratorBlock(
            name,
            th_eff=th_eff,
            el_eff=el_eff,
            cap_th_mw=cap_th,
        )
        fs = block.attach(self.m, self.t, self.cfg, {})

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
        """Attach a P2H converter from unified config to per-node buses."""
        p = dict(asset.params)
        eff = float(p.get("efficiency", 0.99))
        cap_th = float(p.get("capacity_mw", 10.0))
        min_load = float(p.get("min_load", 0.0))

        p2h_name = asset.id.upper()
        block = P2HBlock(p2h_name, eff=eff, cap_th_mw=cap_th, min_load=min_load)
        fs = block.attach(self.m, self.t, self.cfg, {})

        # Per-node heat output
        node_buses.ht_out.append(fs["Q_th_out"])
        # Global electricity input
        sys_buses.el_in.append(fs["P_el_in"])

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

    def _attach_single_heat_pump(self, hp: dict[str, Any], hp_inv_defaults: dict[str, Any]) -> None:
        """Attach one heat pump block and accumulate its bus flows and costs."""
        name = hp.get("id", "HP")
        hp_type = hp.get("type", "standard")

        wrg_col = None
        if hp.get("wrg_source_column"):
            wrg_col = hp.get("wrg_source_column")
            if wrg_col not in self.table.columns and f"{wrg_col}_K" in self.table.columns:
                wrg_col = f"{wrg_col}_K"

        cop_series = calculate_cop_series(self.table, wrg_col, self.cfg, hp_type)

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

        cap_var = fs.get("capacity")
        build_var = fs.get("build")
        if cap_var is not None and build_var is not None:
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

        storage_type = str(sto_cfg.get("type", "simple")).lower()
        if storage_type == "stratified":
            logger.info("[ASSEMBLE] Using stratified storage (2-zone thermocline model)")
            block = self._build_stratified_block(
                sto_cfg, eff_charge, eff_discharge, soc_init,
                invest_enabled, e_cap_min, e_cap_max, p_cap_min, p_cap_max,
                e_cap_init, p_cap_init, terminal_target_val,
            )
        else:
            logger.info("[ASSEMBLE] Using simple storage (single-zone model)")
            block = StorageBlock(
                "TES",
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

        self._register_storage_references(fs, terminal_policy)
        self.buses.terminal_value_term = self._build_terminal_value_term(
            fs, sto_cfg, storage_defaults, terminal_policy, terminal_target_val,
            invest_enabled, e_cap_init, e_cap_max, soc_init,
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

    def _build_stratified_block(
        self, sto_cfg, eff_charge, eff_discharge, soc_init,
        invest_enabled, e_cap_min, e_cap_max, p_cap_min, p_cap_max,
        e_cap_init, p_cap_init, terminal_target_val,
    ) -> StratifiedStorageBlock:
        """Create a StratifiedStorageBlock from config."""
        return StratifiedStorageBlock(
            "TES",
            T_hot_C=float(sto_cfg.get("T_hot_C", 90.0)),
            T_cold_C=float(sto_cfg.get("T_cold_C", 40.0)),
            T_ambient_C=float(sto_cfg.get("T_ambient_C", 15.0)),
            T_ground_C=float(sto_cfg.get("T_ground_C", 10.0)),
            aspect_ratio=float(sto_cfg.get("aspect_ratio", 1.5)),
            geometry_type=str(sto_cfg.get("geometry_type", "tank")),
            U_top=float(sto_cfg.get("U_top", 0.3)),
            U_side=float(sto_cfg.get("U_side", 0.2)),
            U_bottom=float(sto_cfg.get("U_bottom", 0.15)),
            eff_c=eff_charge,
            eff_d=eff_discharge,
            dt_h=self.dt_h,
            soc0=soc_init,
            V_hot_init_fraction=float(sto_cfg.get("V_hot_init_fraction", 0.5)),
            investable=invest_enabled,
            e_cap_min=e_cap_min,
            e_cap_max=e_cap_max,
            p_cap_min=p_cap_min,
            p_cap_max=p_cap_max,
            e_cap_init=e_cap_init,
            p_cap_init=p_cap_init,
            terminal_target=terminal_target_val,
        )

    def _register_storage_references(self, fs: dict[str, Any], terminal_policy: str) -> None:
        """Register Pyomo References for storage variables on the model."""
        for _name in [
            "TES_SOC", "TES_charge_mode", "TES_discharge_mode", "TES_active",
            "TES_soc_low", "TES_soc_high", "TES_soc_split",
            "TES_terminal_slack_pos", "TES_terminal_slack_neg", "TES_terminal_soft",
        ]:
            if hasattr(self.m, _name):
                self.m.del_component(getattr(self.m, _name))

        self.m.TES_SOC = pyo.Reference(fs["SOC"])
        self.m.TES_charge_mode = pyo.Reference(fs["charge_mode"])
        self.m.TES_discharge_mode = pyo.Reference(fs["discharge_mode"])
        self.m.TES_active = pyo.Reference(fs["active"])
        self.m.TES_terminal_policy = terminal_policy

    def _build_terminal_value_term(
        self, fs, sto_cfg, storage_defaults, terminal_policy, terminal_target_val,
        invest_enabled, e_cap_init, e_cap_max, soc_init,
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
            self.m.TES_terminal_target = pyo.Param(initialize=terminal_target_val)
            target_param = self.m.TES_terminal_target

            if terminal_policy == "geq":
                self.m.TES_terminal = pyo.Constraint(expr=fs["SOC"][last_t] >= target_param)
                logger.info("[ASSEMBLE] Terminal constraint: SOC[%s] >= %.1f MWh (geq)", last_t, terminal_target_val)

            elif terminal_policy == "equal":
                self.m.TES_terminal = pyo.Constraint(expr=fs["SOC"][last_t] == target_param)
                logger.info("[ASSEMBLE] Terminal constraint: SOC[%s] == %.1f MWh (equal)", last_t, terminal_target_val)

            elif terminal_policy == "value":
                terminal_value_term = self._build_value_function(
                    fs, terminal_defs, salvage_price, last_t, invest_enabled, e_cap_init, e_cap_max, soc_init
                )

            elif terminal_policy == "soft":
                self.m.TES_terminal_slack_pos = pyo.Var(domain=pyo.NonNegativeReals)
                self.m.TES_terminal_slack_neg = pyo.Var(domain=pyo.NonNegativeReals)
                self.m.TES_terminal_soft = pyo.Constraint(expr=fs["SOC"][last_t] + self.m.TES_terminal_slack_neg - self.m.TES_terminal_slack_pos == target_param)
                terminal_value_term = (
                    soft_penalty * self.m.TES_terminal_slack_neg
                    + (soft_penalty * 0.5) * self.m.TES_terminal_slack_pos
                )
                logger.info("[ASSEMBLE] Soft terminal constraint: target=%.1f, penalty=%.2f", terminal_target_val, soft_penalty)
        else:
            for attr in ("TES_terminal", "TES_terminal_target"):
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
                               invest_enabled, e_cap_init, e_cap_max, soc_init):
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

            self.m.TES_soc_low = pyo.Var(domain=pyo.NonNegativeReals, bounds=(0, threshold))
            self.m.TES_soc_high = pyo.Var(domain=pyo.NonNegativeReals, bounds=(0, soc_max - threshold))
            self.m.TES_soc_split = pyo.Constraint(
                expr=fs["SOC"][last_t] == self.m.TES_soc_low + self.m.TES_soc_high
            )

            price_low = salvage_price
            price_high = salvage_price * (1 - decay)
            logger.info("[ASSEMBLE] Diminishing terminal value: price_low=%.2f, price_high=%.2f", price_low, price_high)
            return -(price_low * self.m.TES_soc_low + price_high * self.m.TES_soc_high)

        logger.info("[ASSEMBLE] Constant terminal value: salvage_price=%.2f EUR/MWh", salvage_price)
        return -salvage_price * fs["SOC"][last_t]
