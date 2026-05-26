"""
Investment Calculator Service for CALION Framework.

Centralizes all investment cost calculation logic that was previously duplicated
across system_builder.py. Provides a consistent interface for:
- Standard component investment (heat pumps, converters)
- Storage investment with separate energy/power capacities

Replaces duplicated patterns from:
- system_builder.py lines 314-328 (Heat Pump investment)
- system_builder.py lines 748-776 (Storage investment)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from calion.constants import DEFAULT_LIFETIME_YEARS


@dataclass
class ComponentInvestmentConfig:
    """
    Configuration for a standard single-capacity component investment.

    Used for heat pumps, P2H converters, and other single-variable components.
    """
    capex_eur_per_mw: float
    activation_cost_eur: float
    tie_breaker_eur_per_mw: float
    lifetime_years: float = DEFAULT_LIFETIME_YEARS


@dataclass
class StorageInvestmentConfig:
    """
    Configuration for storage investment with separate energy/power capacities.

    Used for thermal storage with independent energy (MWh) and power (MW) sizing.
    """
    energy_capex_eur_per_mwh: float
    power_capex_eur_per_mw: float
    activation_cost_eur: float
    tie_breaker_eur_per_mwh: float
    installation_cost_share: float = 0.0
    lifetime_years: float = DEFAULT_LIFETIME_YEARS


@dataclass
class InvestmentTerms:
    """
    Container for investment cost expressions returned by the calculator.

    Organizes investment terms into separate lists for capex, activation,
    tie-breaker, and storage installation costs. Callers append these to
    the global cost lists in system_builder.

    Attributes:
        capex: Annualized capital cost expressions
        activation: Annualized build decision cost expressions
        tie_breaker: Non-annualized small costs to break optimization ties
        storage_install: Installation cost expressions (storage only)
    """
    capex: list[Any] = field(default_factory=list)
    activation: list[Any] = field(default_factory=list)
    tie_breaker: list[Any] = field(default_factory=list)
    storage_install: list[Any] = field(default_factory=list)


class InvestmentCalculator:
    """
    Service class for calculating investment cost expressions.

    Encapsulates the annualization factor and cost flag logic that was
    previously repeated for each component type. The caller (system_builder)
    passes the Pyomo capacity/build variables; this service returns the
    cost expressions to be appended to the objective function.

    Args:
        period_frac: Fraction of year covered by the optimization horizon.
                     = (T * dt_h) / 8760. Used for annualization.
        include_capex: Whether to include CAPEX in objective.
        include_activation: Whether to include activation costs in objective.
        include_tie_breaker: Whether to include tie-breaker costs in objective.
        include_storage_install: Whether to include storage installation costs.
    """

    def __init__(
        self,
        period_frac: float,
        include_capex: bool = True,
        include_activation: bool = True,
        include_tie_breaker: bool = True,
        include_storage_install: bool = True,
    ):
        self.period_frac = period_frac
        self.include_capex = include_capex
        self.include_activation = include_activation
        self.include_tie_breaker = include_tie_breaker
        self.include_storage_install = include_storage_install

    def annual_factor(self, lifetime_years: float) -> float:
        """
        Compute the annualization factor for a given lifetime.

        factor = period_frac / lifetime_years

        Returns 0.0 for zero or negative lifetimes (safe default).
        """
        if lifetime_years > 0:
            return self.period_frac / lifetime_years
        return 0.0

    def calculate_component_costs(
        self,
        capacity_var: Any,  # pyo.Var
        build_var: Any,  # pyo.Var (binary)
        config: ComponentInvestmentConfig,
    ) -> InvestmentTerms:
        """
        Calculate investment cost terms for a standard single-capacity component.

        Replaces the duplicated pattern from heat pump investment calculation
        (system_builder.py lines 314-328).

        Args:
            capacity_var: Pyomo continuous variable for capacity [MW]
            build_var: Pyomo binary variable for build decision
            config: Investment configuration parameters

        Returns:
            InvestmentTerms with cost expressions ready to append to objective lists
        """
        terms = InvestmentTerms()
        af = self.annual_factor(config.lifetime_years)

        if self.include_capex and config.capex_eur_per_mw > 0:
            terms.capex.append(capacity_var * config.capex_eur_per_mw * af)

        if self.include_activation and config.activation_cost_eur > 0:
            terms.activation.append(build_var * config.activation_cost_eur * af)

        if self.include_tie_breaker and config.tie_breaker_eur_per_mw > 0:
            terms.tie_breaker.append(capacity_var * config.tie_breaker_eur_per_mw)

        return terms

    def calculate_storage_costs(
        self,
        energy_cap_var: Any | None,  # pyo.Var for energy capacity
        power_cap_var: Any | None,  # pyo.Var for power capacity
        build_var: Any | None,  # pyo.Var (binary)
        config: StorageInvestmentConfig,
    ) -> InvestmentTerms:
        """
        Calculate investment cost terms for thermal storage with energy/power split.

        Replaces the duplicated pattern from storage investment calculation
        (system_builder.py lines 748-776).

        Args:
            energy_cap_var: Pyomo variable for energy capacity [MWh]
            power_cap_var: Pyomo variable for power capacity [MW]
            build_var: Pyomo binary variable for build decision
            config: Storage investment configuration

        Returns:
            InvestmentTerms with cost expressions ready to append to objective lists
        """
        terms = InvestmentTerms()
        af = self.annual_factor(config.lifetime_years)

        install_components: list[Any] = []

        if energy_cap_var is not None:
            if self.include_capex and config.energy_capex_eur_per_mwh > 0:
                terms.capex.append(energy_cap_var * config.energy_capex_eur_per_mwh * af)
            install_components.append(energy_cap_var * config.energy_capex_eur_per_mwh)
            if self.include_tie_breaker and config.tie_breaker_eur_per_mwh > 0:
                terms.tie_breaker.append(energy_cap_var * config.tie_breaker_eur_per_mwh)

        if power_cap_var is not None:
            if self.include_capex and config.power_capex_eur_per_mw > 0:
                terms.capex.append(power_cap_var * config.power_capex_eur_per_mw * af)
            install_components.append(power_cap_var * config.power_capex_eur_per_mw)

        if build_var is not None:
            if self.include_activation and config.activation_cost_eur > 0:
                terms.activation.append(build_var * config.activation_cost_eur * af)

        if (
            config.installation_cost_share > 0
            and install_components
            and self.include_storage_install
        ):
            terms.storage_install.append(
                sum(install_components) * config.installation_cost_share * af
            )

        return terms

    @staticmethod
    def from_config_dicts(
        inv_cfg: dict,
        inv_defaults: dict,
        period_frac: float,
        cost_flags: dict,
    ) -> InvestmentCalculator:
        """
        Factory method to create InvestmentCalculator from config dictionaries.

        Extracts cost inclusion flags from the nested config structure used
        in system_builder.py.

        Args:
            inv_cfg: Component-specific investment config
            inv_defaults: Global investment defaults
            period_frac: Period fraction for annualization
            cost_flags: Dict with include_* boolean flags

        Returns:
            Configured InvestmentCalculator instance
        """
        return InvestmentCalculator(
            period_frac=period_frac,
            include_capex=cost_flags.get("include_capex_costs", True),
            include_activation=cost_flags.get("include_activation_costs", True),
            include_tie_breaker=cost_flags.get("include_tie_breaker_costs", True),
            include_storage_install=cost_flags.get("include_storage_install_costs", True),
        )

    @staticmethod
    def extract_component_config(
        inv_cfg: dict,
        inv_defaults: dict,
    ) -> ComponentInvestmentConfig:
        """
        Extract ComponentInvestmentConfig from merged config dicts.

        Args:
            inv_cfg: Component-specific investment config
            inv_defaults: Global defaults to fall back to

        Returns:
            ComponentInvestmentConfig with merged values
        """
        def get(key: str, default: float = 0.0) -> float:
            return float(inv_cfg.get(key, inv_defaults.get(key, default)))

        return ComponentInvestmentConfig(
            capex_eur_per_mw=get("capex_eur_per_mw"),
            activation_cost_eur=get("activation_cost_eur"),
            tie_breaker_eur_per_mw=get("tie_breaker_eur_per_mw"),
            lifetime_years=get("lifetime_years", DEFAULT_LIFETIME_YEARS),
        )

    @staticmethod
    def extract_storage_config(
        inv_cfg: dict,
        inv_defaults: dict,
    ) -> StorageInvestmentConfig:
        """
        Extract StorageInvestmentConfig from merged config dicts.

        Args:
            inv_cfg: Storage-specific investment config
            inv_defaults: Global storage defaults to fall back to

        Returns:
            StorageInvestmentConfig with merged values
        """
        def get(key: str, default: float = 0.0) -> float:
            return float(inv_cfg.get(key, inv_defaults.get(key, default)))

        return StorageInvestmentConfig(
            energy_capex_eur_per_mwh=get("energy_capex_eur_per_mwh"),
            power_capex_eur_per_mw=get("power_capex_eur_per_mw"),
            activation_cost_eur=get("activation_cost_eur"),
            tie_breaker_eur_per_mwh=get("tie_breaker_eur_per_mwh"),
            installation_cost_share=get("installation_cost_share"),
            lifetime_years=get("lifetime_years", DEFAULT_LIFETIME_YEARS),
        )


__all__ = [
    "ComponentInvestmentConfig",
    "InvestmentCalculator",
    "InvestmentTerms",
    "StorageInvestmentConfig",
]
