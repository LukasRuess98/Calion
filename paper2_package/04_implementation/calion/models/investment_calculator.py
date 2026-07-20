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
        discount_rate: float = 0.0,
        include_capex: bool = True,
        include_activation: bool = True,
        include_tie_breaker: bool = True,
        include_storage_install: bool = True,
    ):
        self.period_frac = period_frac
        self.discount_rate = discount_rate
        self.include_capex = include_capex
        self.include_activation = include_activation
        self.include_tie_breaker = include_tie_breaker
        self.include_storage_install = include_storage_install

    def annual_factor(self, lifetime_years: float) -> float:
        """
        Compute the annualization factor for a given lifetime.

        When discount_rate > 0, uses the ANF formula: i*(1+i)^n / ((1+i)^n - 1) * period_frac.
        When discount_rate == 0, falls back to period_frac / lifetime_years (linear depreciation).

        Returns 0.0 for zero or negative lifetimes (safe default).
        """
        if lifetime_years <= 0:
            return 0.0
        if self.discount_rate > 0:
            i, n = self.discount_rate, lifetime_years
            anf = i * (1 + i) ** n / ((1 + i) ** n - 1)
            return anf * self.period_frac
        return self.period_frac / lifetime_years

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


def annuity_factor(i: float, n: float) -> float:
    """Compute the annuity factor ANF(i, n) for investment cost annualization.

    ANF(i, n) = i * (1 + i)^n / ((1 + i)^n - 1)

    Converts a one-time CAPEX into an equivalent annual payment stream.
    Used in Paper 2 objective function:
        CAPEX_annual = ANF(i, n) * CAPEX_total

    Args:
        i: Discount rate as a decimal fraction (e.g., 0.05 for 5%).
        n: Economic lifetime [years].

    Returns:
        Annuity factor [1/year]. For i=0, returns 1/n (straight-line).
    """
    if n <= 0:
        raise ValueError(f"Lifetime n must be positive, got {n}")
    if i <= 0:
        return 1.0 / n
    factor = (1.0 + i) ** n
    return i * factor / (factor - 1.0)


@dataclass
class P2InvestmentConfig:
    """Paper 2 investment configuration using proper ANF annualization.

    Unlike ComponentInvestmentConfig (which uses period_frac/lifetime),
    this uses the full ANF formula and explicit α/β cost coefficients
    from the Paper 2 spec.
    """
    alpha_eur_per_mw_or_m3: float
    beta_eur: float
    discount_rate: float
    lifetime_years: float

    def capex_annual_per_unit(self) -> float:
        """Annualized CAPEX per unit capacity [€/year per MW or m³]."""
        return annuity_factor(self.discount_rate, self.lifetime_years) * self.alpha_eur_per_mw_or_m3

    def capex_annual_fixed(self) -> float:
        """Annualized fixed (activation) CAPEX [€/year]."""
        return annuity_factor(self.discount_rate, self.lifetime_years) * self.beta_eur


class P2InvestmentCalculator:
    """Investment cost calculator for Paper 2 using ANF annualization.

    Computes CAPEX cost expressions for WP, EK, and TES components
    following the spec linear cost model:
        CAPEX_WP = alpha_WP * Q_WP + beta_WP * y_WP
        CAPEX_EK = alpha_EK * Q_EK + beta_EK * y_EK
        CAPEX_TES = alpha_TES * V_TES + beta_TES * y_TES

    The annualized cost in the objective is:
        ANF * CAPEX * period_frac
    """

    def __init__(self, discount_rate: float, period_frac: float = 1.0):
        self.discount_rate = discount_rate
        self.period_frac = period_frac

    def calculate_annualized_cost(
        self,
        capacity_var: Any,
        build_var: Any,
        config: P2InvestmentConfig,
    ) -> Any:
        """Build a Pyomo expression for the annualized CAPEX contribution.

        Returns:
            Pyomo expression: ANF * period_frac * (alpha * cap + beta * build)
        """
        af = annuity_factor(config.discount_rate, config.lifetime_years)
        scale = af * self.period_frac
        return scale * (config.alpha_eur_per_mw_or_m3 * capacity_var + config.beta_eur * build_var)


__all__ = [
    "ComponentInvestmentConfig",
    "InvestmentCalculator",
    "InvestmentTerms",
    "P2InvestmentCalculator",
    "P2InvestmentConfig",
    "StorageInvestmentConfig",
    "annuity_factor",
]
