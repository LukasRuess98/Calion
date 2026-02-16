"""Typed configuration schemas for energy system components.

This module provides dataclass-based configuration schemas that replace
Dict[str, Any] usage throughout the codebase. Benefits:
- Type safety and IDE autocomplete
- Clear documentation of config structure
- Validation at construction time
- Easier testing and mocking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class InvestmentConfig:
    """Investment/sizing configuration for a component."""

    enabled: bool = False
    """Whether investment optimization is enabled"""

    capacity_min: float = 0.0
    """Minimum capacity (MW or MWh depending on component)"""

    capacity_max: float = 1000.0
    """Maximum capacity (MW or MWh depending on component)"""

    capacity_init: float = 0.0
    """Initial/existing capacity"""

    capex_eur_per_unit: float = 0.0
    """Capital cost per unit capacity (EUR/MW or EUR/MWh)"""

    lifetime_years: float = 20.0
    """Economic lifetime in years"""

    activation_cost_eur: float = 0.0
    """Fixed cost for activating/building the component"""

    tie_breaker_eur_per_unit: float = 0.0
    """Small cost to break optimization ties"""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InvestmentConfig:
        """Create from dictionary, handling various key naming conventions."""
        if not data:
            return cls()

        return cls(
            enabled=bool(data.get("enabled", False)),
            capacity_min=float(data.get("capacity_min", data.get("min_capacity", 0.0))),
            capacity_max=float(data.get("capacity_max", data.get("max_capacity", 1000.0))),
            capacity_init=float(data.get("capacity_init", data.get("init_capacity", 0.0))),
            capex_eur_per_unit=float(
                data.get("capex_eur_per_unit", data.get("capex_eur_per_mw", 0.0))
            ),
            lifetime_years=float(data.get("lifetime_years", 20.0)),
            activation_cost_eur=float(data.get("activation_cost_eur", 0.0)),
            tie_breaker_eur_per_unit=float(
                data.get("tie_breaker_eur_per_unit", data.get("tie_breaker_eur_per_mw", 0.0))
            ),
        )


@dataclass
class HeatPumpConfig:
    """Configuration for a heat pump component."""

    id: str
    """Unique identifier for this heat pump"""

    enabled: bool = True
    """Whether this heat pump is enabled"""

    type: str = "standard"
    """Heat pump type identifier (for COP calculation)"""

    min_load: float = 0.3
    """Minimum part-load fraction (0-1)"""

    max_th_mw: float = 0.0
    """Maximum thermal output capacity (MW)"""

    wrg_source_column: Optional[str] = None
    """Time series column name for waste heat recovery temperature"""

    cop_default: float = 3.0
    """Default COP if calculation fails"""

    investment: InvestmentConfig = field(default_factory=InvestmentConfig)
    """Investment configuration"""

    @classmethod
    def from_dict(cls, data: Dict[str, Any], defaults: Optional[Dict[str, Any]] = None) -> HeatPumpConfig:
        """Create from dictionary with optional defaults."""
        if defaults:
            merged = {**defaults, **data}
        else:
            merged = data

        inv_data = merged.get("investment", {})
        if isinstance(inv_data, dict):
            investment = InvestmentConfig.from_dict(inv_data)
        else:
            investment = InvestmentConfig()

        return cls(
            id=str(merged.get("id", "HP")),
            enabled=bool(merged.get("enabled", True)),
            type=str(merged.get("type", "standard")),
            min_load=float(merged.get("min_load", 0.3)),
            max_th_mw=float(merged.get("max_th_mw", 0.0)),
            wrg_source_column=merged.get("wrg_source_column"),
            cop_default=float(merged.get("cop_default", 3.0)),
            investment=investment,
        )


@dataclass
class StorageConfig:
    """Configuration for thermal energy storage."""

    enabled: bool = False
    """Whether storage is enabled"""

    min_energy_mwh: float = 0.0
    """Minimum energy capacity (MWh)"""

    max_energy_mwh: float = 1000.0
    """Maximum energy capacity (MWh)"""

    min_power_mw: float = 0.0
    """Minimum charge/discharge power (MW)"""

    max_power_mw: float = 100.0
    """Maximum charge/discharge power (MW)"""

    eff_charge: float = 0.95
    """Charging efficiency (0-1)"""

    eff_discharge: float = 0.95
    """Discharging efficiency (0-1)"""

    loss_hour: float = 0.9999
    """Hourly standing loss factor (0-1)"""

    soc_init: float = 0.0
    """Initial state of charge (MWh)"""

    use_stratified: bool = False
    """Use stratified (multi-zone) storage model"""

    terminal_state: str = "free"
    """Terminal constraint: 'free', 'cyclic', or 'target'"""

    terminal_policy: str = "equal"
    """Terminal policy: 'equal', 'geq', 'value', or 'soft'"""

    terminal_target: Optional[float] = None
    """Terminal target SOC (MWh), None = use soc_init"""

    power_energy_coupling: Optional[float] = None
    """Fixed ratio between power and energy capacity (MW/MWh)"""

    investment: InvestmentConfig = field(default_factory=InvestmentConfig)
    """Investment configuration for energy capacity"""

    power_investment: InvestmentConfig = field(default_factory=InvestmentConfig)
    """Investment configuration for power capacity"""

    @classmethod
    def from_dict(cls, data: Dict[str, Any], defaults: Optional[Dict[str, Any]] = None) -> StorageConfig:
        """Create from dictionary with optional defaults."""
        if defaults:
            merged = {**defaults, **data}
        else:
            merged = data

        # Extract investment configs
        inv_data = merged.get("investment", {})
        energy_inv = InvestmentConfig.from_dict(inv_data) if isinstance(inv_data, dict) else InvestmentConfig()

        # Power investment might be separate or embedded
        power_inv_data = merged.get("power_investment", inv_data)
        power_inv = InvestmentConfig.from_dict(power_inv_data) if isinstance(power_inv_data, dict) else InvestmentConfig()

        # Handle terminal config nesting
        terminal_cfg = merged.get("terminal", {})
        terminal_state = str(terminal_cfg.get("state", merged.get("terminal_state", "free")))
        terminal_policy = str(terminal_cfg.get("policy", merged.get("terminal_policy", "equal")))
        terminal_target = terminal_cfg.get("target_mwh", merged.get("terminal_target"))

        return cls(
            enabled=bool(merged.get("enabled", False)),
            min_energy_mwh=float(merged.get("min_energy_mwh", 0.0)),
            max_energy_mwh=float(merged.get("max_energy_mwh", 1000.0)),
            min_power_mw=float(merged.get("min_power_mw", 0.0)),
            max_power_mw=float(merged.get("max_power_mw", 100.0)),
            eff_charge=float(merged.get("eff_charge", 0.95)),
            eff_discharge=float(merged.get("eff_discharge", 0.95)),
            loss_hour=float(merged.get("loss_hour", 0.9999)),
            soc_init=float(merged.get("soc_init", merged.get("SOC_init", 0.0))),
            use_stratified=bool(merged.get("use_stratified", False)),
            terminal_state=terminal_state,
            terminal_policy=terminal_policy,
            terminal_target=float(terminal_target) if terminal_target is not None else None,
            power_energy_coupling=float(merged["power_energy_coupling"]) if merged.get("power_energy_coupling") is not None else None,
            investment=energy_inv,
            power_investment=power_inv,
        )


@dataclass
class ThermalGeneratorConfig:
    """Configuration for thermal generator (boiler, CHP)."""

    id: str
    """Unique identifier"""

    enabled: bool = True
    """Whether enabled"""

    cap_th_mw: float = 10.0
    """Thermal capacity (MW)"""

    th_eff: float = 0.9
    """Thermal efficiency (0-1)"""

    el_eff: Optional[float] = None
    """Electrical efficiency (0-1), None = boiler, value = CHP"""

    fuel_type: str = "gas"
    """Fuel type: 'gas', 'biomass', 'waste', 'oil'"""

    min_load: float = 0.0
    """Minimum part-load fraction (0-1)"""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ThermalGeneratorConfig:
        """Create from dictionary."""
        return cls(
            id=str(data.get("id", "GEN")),
            enabled=bool(data.get("enabled", True)),
            cap_th_mw=float(data.get("cap_th_mw", 10.0)),
            th_eff=float(data.get("th_eff", 0.9)),
            el_eff=float(data["el_eff"]) if data.get("el_eff") is not None else None,
            fuel_type=str(data.get("fuel_type", "gas")),
            min_load=float(data.get("min_load", 0.0)),
        )


@dataclass
class P2HConfig:
    """Configuration for Power-to-Heat (electric heater)."""

    enabled: bool = True
    """Whether enabled"""

    cap_th_mw: float = 10.0
    """Thermal capacity (MW)"""

    min_load: float = 0.0
    """Minimum part-load fraction (0-1)"""

    efficiency: float = 0.98
    """Conversion efficiency (0-1)"""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> P2HConfig:
        """Create from dictionary."""
        return cls(
            enabled=bool(data.get("enabled", True)),
            cap_th_mw=float(data.get("cap_th_mw", 10.0)),
            min_load=float(data.get("min_load", 0.0)),
            efficiency=float(data.get("efficiency", data.get("eff", 0.98))),
        )


@dataclass
class CostConfig:
    """Cost and pricing configuration."""

    co2_price_eur_per_t: float = 100.0
    """CO2 price (EUR/tonne)"""

    dump_cost_eur_per_mwh_th: float = 1.0
    """Cost for dumping excess heat (EUR/MWh_th)"""

    include_co2_cost_in_objective: bool = True
    """Include CO2 costs in objective"""

    include_capex_costs: bool = True
    """Include CAPEX in objective"""

    include_activation_costs: bool = True
    """Include activation costs"""

    include_tie_breaker_costs: bool = True
    """Include tie-breaker costs"""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CostConfig:
        """Create from dictionary."""
        return cls(
            co2_price_eur_per_t=float(data.get("co2_price_eur_per_t", 100.0)),
            dump_cost_eur_per_mwh_th=float(data.get("dump_cost_eur_per_mwh_th", 1.0)),
            include_co2_cost_in_objective=bool(data.get("include_co2_cost_in_objective", True)),
            include_capex_costs=bool(data.get("include_capex_costs", True)),
            include_activation_costs=bool(data.get("include_activation_costs", True)),
            include_tie_breaker_costs=bool(data.get("include_tie_breaker_costs", True)),
        )


def extract_component_configs(
    raw_cfg: Dict[str, Any]
) -> tuple[List[HeatPumpConfig], StorageConfig, List[ThermalGeneratorConfig], Optional[P2HConfig]]:
    """Extract and validate all component configurations from raw config dict.

    Args:
        raw_cfg: Raw configuration dictionary (from YAML)

    Returns:
        Tuple of (heat_pumps, storage, thermal_generators, p2h)
    """
    syscfg = raw_cfg.get("system", {})

    # Heat pumps
    hp_defaults = raw_cfg.get("heat_pumps", {})
    hp_list = syscfg.get("heat_pumps", [])
    heat_pumps = [HeatPumpConfig.from_dict(hp, hp_defaults) for hp in hp_list]

    # Storage
    sto_defaults = raw_cfg.get("storage", {})
    sto_cfg = syscfg.get("storage", {"enabled": False})
    storage = StorageConfig.from_dict(sto_cfg, sto_defaults)

    # Thermal generators (boilers, CHP)
    gen_list = syscfg.get("thermal_generators", [])
    thermal_gens = [ThermalGeneratorConfig.from_dict(gen) for gen in gen_list]

    # Power-to-Heat
    p2h_cfg = syscfg.get("p2h")
    p2h = P2HConfig.from_dict(p2h_cfg) if p2h_cfg else None

    return heat_pumps, storage, thermal_gens, p2h
