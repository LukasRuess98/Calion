"""
Scenario configuration schemas.

Defines dataclasses for optimization scenario configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class RepresentativePeriods:
    """Representative period configuration for reducing problem size."""

    method: str = "kmeans_clustering"  # kmeans_clustering, manual_selection
    num_periods: int = 8
    include_extreme_days: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RepresentativePeriods:
        """Create from dictionary."""
        return cls(
            method=str(data.get('method', 'kmeans_clustering')),
            num_periods=int(data.get('num_periods', 8)),
            include_extreme_days=bool(data.get('include_extreme_days', True)),
        )


@dataclass
class TimeConfig:
    """Time horizon configuration."""

    # Data source
    data_file: str
    data_source_config: str

    # Time range
    start: str = "2023-01-01 00:00:00"
    end: str = "2023-12-31 23:00:00"
    resolution_h: float = 1.0

    # Representative periods (optional)
    use_representative_periods: bool = False
    representative_periods: Optional[RepresentativePeriods] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimeConfig:
        """Create from dictionary."""
        rep_periods = None
        if data.get('use_representative_periods', False):
            rep_periods_data = data.get('representative_periods', {})
            rep_periods = RepresentativePeriods.from_dict(rep_periods_data)

        return cls(
            data_file=str(data['data_file']),
            data_source_config=str(data['data_source_config']),
            start=str(data.get('start', '2023-01-01 00:00:00')),
            end=str(data.get('end', '2023-12-31 23:00:00')),
            resolution_h=float(data.get('resolution_h', 1.0)),
            use_representative_periods=bool(data.get('use_representative_periods', False)),
            representative_periods=rep_periods,
        )


@dataclass
class CostConfig:
    """Cost components configuration."""

    # Which costs to include
    include_capex: bool = False
    include_activation_costs: bool = False
    include_opex_fixed: bool = False
    include_opex_variable: bool = True
    include_fuel: bool = True
    include_electricity_purchase: bool = True
    include_electricity_sales: bool = True
    include_co2: bool = True
    include_demand_charge: bool = True
    include_heat_dump_penalty: bool = True

    # Economic parameters (for investment)
    discount_rate: float = 0.05
    planning_horizon_yr: float = 15.0
    annualization_method: str = "simplified"  # simplified, npv, annuity

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CostConfig:
        """Create from dictionary."""
        return cls(
            include_capex=bool(data.get('include_capex', False)),
            include_activation_costs=bool(data.get('include_activation_costs', False)),
            include_opex_fixed=bool(data.get('include_opex_fixed', False)),
            include_opex_variable=bool(data.get('include_opex_variable', True)),
            include_fuel=bool(data.get('include_fuel', True)),
            include_electricity_purchase=bool(data.get('include_electricity_purchase', True)),
            include_electricity_sales=bool(data.get('include_electricity_sales', True)),
            include_co2=bool(data.get('include_co2', True)),
            include_demand_charge=bool(data.get('include_demand_charge', True)),
            include_heat_dump_penalty=bool(data.get('include_heat_dump_penalty', True)),
            discount_rate=float(data.get('discount_rate', 0.05)),
            planning_horizon_yr=float(data.get('planning_horizon_yr', 15.0)),
            annualization_method=str(data.get('annualization_method', 'simplified')),
        )


@dataclass
class ConstraintsConfig:
    """Optimization constraints configuration."""

    # Energy balances
    enforce_heat_balance: bool = True
    enforce_power_balance: bool = True

    # Component limits
    respect_capacity_limits: bool = True
    respect_min_load: bool = True
    respect_ramp_rates: bool = True

    # Network constraints
    enforce_network_losses: bool = True
    use_simplified_network_model: bool = True

    # Emissions constraint (optional)
    max_annual_co2_emissions_t: Optional[float] = None

    # Reliability
    n_minus_1_criterion: bool = False

    # Investment constraints
    max_total_investment_eur: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConstraintsConfig:
        """Create from dictionary."""
        return cls(
            enforce_heat_balance=bool(data.get('enforce_heat_balance', True)),
            enforce_power_balance=bool(data.get('enforce_power_balance', True)),
            respect_capacity_limits=bool(data.get('respect_capacity_limits', True)),
            respect_min_load=bool(data.get('respect_min_load', True)),
            respect_ramp_rates=bool(data.get('respect_ramp_rates', True)),
            enforce_network_losses=bool(data.get('enforce_network_losses', True)),
            use_simplified_network_model=bool(data.get('use_simplified_network_model', True)),
            max_annual_co2_emissions_t=float(data['max_annual_co2_emissions_t']) if data.get('max_annual_co2_emissions_t') is not None else None,
            n_minus_1_criterion=bool(data.get('n_minus_1_criterion', False)),
            max_total_investment_eur=float(data['max_total_investment_eur']) if data.get('max_total_investment_eur') is not None else None,
        )


@dataclass
class OptimizationConfig:
    """Optimization configuration."""

    # Optimization mode
    mode: str  # dispatch, capacity_expansion, network_design

    # Decision variables
    decision_variables: List[str] = field(default_factory=list)

    # Objective function
    objective: str = "minimize_total_cost"

    # Cost configuration
    costs: CostConfig = field(default_factory=CostConfig)

    # Constraints
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OptimizationConfig:
        """Create from dictionary."""
        costs_data = data.get('costs', {})
        constraints_data = data.get('constraints', {})

        return cls(
            mode=str(data.get('mode', 'dispatch')),
            decision_variables=data.get('decision_variables', []),
            objective=str(data.get('objective', 'minimize_total_cost')),
            costs=CostConfig.from_dict(costs_data),
            constraints=ConstraintsConfig.from_dict(constraints_data),
        )


@dataclass
class StorageInitialState:
    """Storage initial state."""

    soc_mwh: float = 0.0
    hot_zone_fraction: float = 0.5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StorageInitialState:
        """Create from dictionary."""
        return cls(
            soc_mwh=float(data.get('soc_mwh', 0.0)),
            hot_zone_fraction=float(data.get('hot_zone_fraction', 0.5)),
        )


@dataclass
class NetworkInitialState:
    """Network initial state."""

    supply_temp_c: float = 100.0
    return_temp_c: float = 55.0
    pressure_bar: float = 10.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NetworkInitialState:
        """Create from dictionary."""
        return cls(
            supply_temp_c=float(data.get('supply_temp_c', 100.0)),
            return_temp_c=float(data.get('return_temp_c', 55.0)),
            pressure_bar=float(data.get('pressure_bar', 10.0)),
        )


@dataclass
class InitialState:
    """Initial conditions for optimization."""

    storage: Dict[str, StorageInitialState] = field(default_factory=dict)
    network: NetworkInitialState = field(default_factory=NetworkInitialState)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InitialState:
        """Create from dictionary."""
        storage_data = data.get('storage', {})
        storage = {sid: StorageInitialState.from_dict(sdata) for sid, sdata in storage_data.items()}

        network_data = data.get('network', {})
        network = NetworkInitialState.from_dict(network_data)

        return cls(
            storage=storage,
            network=network,
        )


@dataclass
class StorageTerminalConditions:
    """Storage terminal conditions."""

    state: str = "cyclic"  # free, cyclic, target
    policy: str = "equal"  # equal, geq, soft, value

    # For target state
    target_mwh: Optional[float] = None

    # For value function
    value_function_type: str = "constant"  # constant, diminishing
    salvage_price_eur_per_mwh: float = 50.0
    diminishing_decay: float = 0.3

    # For soft constraint
    soft_penalty_eur_per_mwh: float = 100.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StorageTerminalConditions:
        """Create from dictionary."""
        return cls(
            state=str(data.get('state', 'cyclic')),
            policy=str(data.get('policy', 'equal')),
            target_mwh=float(data['target_mwh']) if data.get('target_mwh') is not None else None,
            value_function_type=str(data.get('value_function_type', 'constant')),
            salvage_price_eur_per_mwh=float(data.get('salvage_price_eur_per_mwh', 50.0)),
            diminishing_decay=float(data.get('diminishing_decay', 0.3)),
            soft_penalty_eur_per_mwh=float(data.get('soft_penalty_eur_per_mwh', 100.0)),
        )


@dataclass
class TerminalConditions:
    """Terminal conditions for optimization."""

    storage: StorageTerminalConditions = field(default_factory=StorageTerminalConditions)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TerminalConditions:
        """Create from dictionary."""
        storage_data = data.get('storage', {})
        storage = StorageTerminalConditions.from_dict(storage_data)

        return cls(storage=storage)


@dataclass
class Subsidies:
    """Investment subsidies configuration."""

    heat_pump_subsidy_fraction: float = 0.0
    storage_subsidy_fraction: float = 0.0
    p2h_subsidy_fraction: float = 0.0
    chp_subsidy_fraction: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Subsidies:
        """Create from dictionary."""
        return cls(
            heat_pump_subsidy_fraction=float(data.get('heat_pump_subsidy_fraction', 0.0)),
            storage_subsidy_fraction=float(data.get('storage_subsidy_fraction', 0.0)),
            p2h_subsidy_fraction=float(data.get('p2h_subsidy_fraction', 0.0)),
            chp_subsidy_fraction=float(data.get('chp_subsidy_fraction', 0.0)),
        )


@dataclass
class EconomicsConfig:
    """Economics configuration."""

    # Fuel prices (overrides tech_library defaults)
    fuel_prices: Dict[str, float] = field(default_factory=dict)

    # Carbon pricing
    co2_price_eur_per_tonne: float = 100.0

    # Other costs
    heat_dump_penalty_eur_per_mwh: float = 10.0

    # Investment incentives
    subsidies: Subsidies = field(default_factory=Subsidies)

    # Discount rate (for NPV calculations)
    discount_rate: float = 0.05

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EconomicsConfig:
        """Create from dictionary."""
        subsidies_data = data.get('subsidies', {})
        subsidies = Subsidies.from_dict(subsidies_data)

        return cls(
            fuel_prices=data.get('fuel_prices', {}),
            co2_price_eur_per_tonne=float(data.get('co2_price_eur_per_tonne', 100.0)),
            heat_dump_penalty_eur_per_mwh=float(data.get('heat_dump_penalty_eur_per_mwh', 10.0)),
            subsidies=subsidies,
            discount_rate=float(data.get('discount_rate', 0.05)),
        )


@dataclass
class SensitivityParameter:
    """Sensitivity analysis parameter."""

    name: str
    base: float
    range: List[float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SensitivityParameter:
        """Create from dictionary."""
        return cls(
            name=str(data['name']),
            base=float(data['base']),
            range=data.get('range', []),
        )


@dataclass
class SensitivityConfig:
    """Sensitivity analysis configuration."""

    enabled: bool = False
    parameters: List[SensitivityParameter] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SensitivityConfig:
        """Create from dictionary."""
        params_data = data.get('parameters', [])
        parameters = [SensitivityParameter.from_dict(p) for p in params_data]

        return cls(
            enabled=bool(data.get('enabled', False)),
            parameters=parameters,
        )


@dataclass
class SolverConfig:
    """Solver configuration."""

    name: str = "gurobi"  # gurobi, cplex, glpk, cbc
    timelimit_s: int = 7200
    mip_gap: float = 0.01
    threads: int = 8

    # Solver-specific options
    options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SolverConfig:
        """Create from dictionary."""
        return cls(
            name=str(data.get('name', 'gurobi')),
            timelimit_s=int(data.get('timelimit_s', 7200)),
            mip_gap=float(data.get('mip_gap', 0.01)),
            threads=int(data.get('threads', 8)),
            options=data.get('options', {}),
        )


@dataclass
class OutputConfig:
    """Output configuration."""

    results_dir: str = "../../results"

    # Output files
    save_hourly_results: bool = True
    save_summary_statistics: bool = True
    save_cost_breakdown: bool = True
    save_emissions_breakdown: bool = True
    save_investment_summary: bool = False

    # Visualization
    create_plots: bool = True
    plot_formats: List[str] = field(default_factory=lambda: ["png", "pdf"])

    # Export formats
    export_formats: List[str] = field(default_factory=lambda: ["excel", "csv", "json"])

    # Dashboard data
    export_dashboard_data: bool = True
    dashboard_format: str = "json"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OutputConfig:
        """Create from dictionary."""
        return cls(
            results_dir=str(data.get('results_dir', '../../results')),
            save_hourly_results=bool(data.get('save_hourly_results', True)),
            save_summary_statistics=bool(data.get('save_summary_statistics', True)),
            save_cost_breakdown=bool(data.get('save_cost_breakdown', True)),
            save_emissions_breakdown=bool(data.get('save_emissions_breakdown', True)),
            save_investment_summary=bool(data.get('save_investment_summary', False)),
            create_plots=bool(data.get('create_plots', True)),
            plot_formats=data.get('plot_formats', ["png", "pdf"]),
            export_formats=data.get('export_formats', ["excel", "csv", "json"]),
            export_dashboard_data=bool(data.get('export_dashboard_data', True)),
            dashboard_format=str(data.get('dashboard_format', 'json')),
        )


@dataclass
class ReportingConfig:
    """Reporting configuration."""

    # KPIs to calculate
    kpis: List[str] = field(default_factory=list)

    # Time aggregations
    aggregations: List[str] = field(default_factory=lambda: ["hourly", "daily", "monthly", "annual"])

    # Investment summary (for capacity expansion)
    investment_summary: Dict[str, bool] = field(default_factory=dict)

    # Comparison to baseline
    compare_to_baseline: bool = False
    baseline_scenario: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReportingConfig:
        """Create from dictionary."""
        return cls(
            kpis=data.get('kpis', []),
            aggregations=data.get('aggregations', ["hourly", "daily", "monthly", "annual"]),
            investment_summary=data.get('investment_summary', {}),
            compare_to_baseline=bool(data.get('compare_to_baseline', False)),
            baseline_scenario=data.get('baseline_scenario'),
        )


@dataclass
class AssetPaths:
    """Asset configuration file paths."""

    components: str
    grid: str
    network: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AssetPaths:
        """Create from dictionary."""
        return cls(
            components=str(data['components']),
            grid=str(data['grid']),
            network=str(data['network']),
        )


@dataclass
class Scenario:
    """Complete scenario configuration."""

    # Required fields (no defaults)
    name: str
    description: str
    time: TimeConfig
    assets: AssetPaths
    optimization: OptimizationConfig
    initial_state: InitialState
    terminal_conditions: TerminalConditions
    economics: EconomicsConfig
    sensitivity: SensitivityConfig
    solver: SolverConfig
    output: OutputConfig
    reporting: ReportingConfig

    # Optional metadata fields (with defaults)
    version: str = "1.0"
    author: str = ""
    date: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Scenario:
        """Create from dictionary."""
        scenario_data = data.get('scenario', {})

        time_data = scenario_data.get('time', {})
        time = TimeConfig.from_dict(time_data)

        assets_data = scenario_data.get('assets', {})
        assets = AssetPaths.from_dict(assets_data)

        optimization_data = scenario_data.get('optimization', {})
        optimization = OptimizationConfig.from_dict(optimization_data)

        initial_state_data = scenario_data.get('initial_state', {})
        initial_state = InitialState.from_dict(initial_state_data)

        terminal_conditions_data = scenario_data.get('terminal_conditions', {})
        terminal_conditions = TerminalConditions.from_dict(terminal_conditions_data)

        economics_data = scenario_data.get('economics', {})
        economics = EconomicsConfig.from_dict(economics_data)

        sensitivity_data = scenario_data.get('sensitivity', {})
        sensitivity = SensitivityConfig.from_dict(sensitivity_data)

        solver_data = scenario_data.get('solver', {})
        solver = SolverConfig.from_dict(solver_data)

        output_data = scenario_data.get('output', {})
        output = OutputConfig.from_dict(output_data)

        reporting_data = scenario_data.get('reporting', {})
        reporting = ReportingConfig.from_dict(reporting_data)

        return cls(
            name=str(scenario_data.get('name', '')),
            description=str(scenario_data.get('description', '')),
            version=str(scenario_data.get('version', '1.0')),
            author=str(scenario_data.get('author', '')),
            date=str(scenario_data.get('date', '')),
            time=time,
            assets=assets,
            optimization=optimization,
            initial_state=initial_state,
            terminal_conditions=terminal_conditions,
            economics=economics,
            sensitivity=sensitivity,
            solver=solver,
            output=output,
            reporting=reporting,
        )
