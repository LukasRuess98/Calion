"""TypedDict definitions for the top-level configuration structure.

These types describe the *expected* shape of the merged config dict that
flows through the framework.  They are not enforced at runtime — the dict
remains ``Dict[str, Any]`` — but they serve three purposes:

1. **Documentation** — a single place to see which keys each section uses.
2. **IDE support** — auto-complete and type-narrowing for editors that
   understand ``TypedDict``.
3. **Migration target** — downstream code can gradually adopt these types
   in function signatures, eliminating the defensive ``isinstance`` checks
   that currently guard every dict access.

Usage::

    from calion.config.typed_config import CALIONConfig

    def my_function(cfg: CALIONConfig) -> None:
        dt_h = cfg["run"]["dt_h"]  # IDE knows this is float
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from typing_extensions import NotRequired, TypedDict


# ---------------------------------------------------------------------------
# Leaf-level sections
# ---------------------------------------------------------------------------

class GridConfig(TypedDict, total=False):
    """Grid connection parameters."""

    enabled: bool
    max_import_mw: float
    max_export_mw: float
    big_m_grid_mw: float
    year_fraction: float
    demand_charge_eur_per_mw_y: float
    buy_price_eur_per_mwh: float
    sell_price_eur_per_mwh: float


class CostsConfig(TypedDict, total=False):
    """Cost configuration."""

    co2_price_eur_per_t: float
    dump_cost_eur_per_mwh_th: float
    include_gridcost_in_energy: bool
    include_demand_charge_in_rh: bool
    include_co2_cost_in_objective: bool
    include_investment_in_rh: bool
    amortise_investment_once_in_rh: bool


class StorageTerminalConfig(TypedDict, total=False):
    """Storage terminal constraint configuration."""

    policy: str  # "free", "equal", "geq", "soft", "value"
    state: str  # "free", "cyclic"
    target_mwh: float


class StorageInvestmentConfig(TypedDict, total=False):
    """Storage investment optimisation bounds."""

    enabled: bool
    energy_capacity_min_mwh: float
    energy_capacity_max_mwh: float
    power_capacity_min_mw: float
    power_capacity_max_mw: float


class StorageConfig(TypedDict, total=False):
    """Thermal energy storage parameters."""

    enabled: bool
    id: str
    energy_mwh: float
    power_mw: float
    max_energy_mwh: float
    max_power_mw: float
    soc0_mwh: float
    SOC_init: float  # legacy alias for soc0_mwh
    eta_charge: float
    eta_discharge: float
    self_discharge_rate: float
    terminal: StorageTerminalConfig
    terminal_soc_mwh: float
    terminal_state: str
    investment: StorageInvestmentConfig


class HeatPumpInvestmentConfig(TypedDict, total=False):
    """Heat pump investment optimisation bounds."""

    enabled: bool
    capacity_min_mw: float
    capacity_max_mw: float


class HeatPumpConfig(TypedDict, total=False):
    """Single heat pump configuration."""

    enabled: bool
    id: str
    capacity_mw: float
    cop_series: str
    cop_default: float
    investment: HeatPumpInvestmentConfig


class GeneratorConfig(TypedDict, total=False):
    """Thermal generator configuration."""

    enabled: bool
    cap_th_mw: float
    fuel_bus: str
    el_eff: Optional[float]
    th_eff: Optional[float]


class SystemConfig(TypedDict, total=False):
    """System section — component definitions and topology."""

    storage: StorageConfig
    heat_pumps: Dict[str, HeatPumpConfig]
    generators: Dict[str, GeneratorConfig]


class RollingHorizonConfig(TypedDict, total=False):
    """Rolling horizon parameters."""

    heat_horizon_hours: float
    window_hours: float  # alias
    step_hours: float
    overlap_hours: float
    terminal_policy: str

    # Legacy aliases (uppercase)
    HEAT_HORIZON_HOURS: float
    STEP_HOURS: float
    OVERLAP_HOURS: float
    TERMINAL_POLICY: str


class DesignSectionConfig(TypedDict, total=False):
    """Design fixation configuration within scenario."""

    mode: str  # "none", "optimize", "file", "inline"
    apply_from_window: int
    save_to: str
    load_from: str


class ScenarioConfig(TypedDict, total=False):
    """Scenario section."""

    name: str
    run_mode: str
    workflow: Any  # str | List[str]
    fix_design: bool
    fix_design_in_rh: bool  # legacy alias
    rolling_horizon: RollingHorizonConfig
    design: DesignSectionConfig
    pf_design_json: str


class RunConfig(TypedDict, total=False):
    """Run section — execution parameters."""

    dt_h: float
    solver: str
    solver_options: Dict[str, Any]


class InputsConfig(TypedDict, total=False):
    """Inputs section — initial conditions."""

    SOC_init: float


class SiteConfig(TypedDict, total=False):
    """Site section — location and data files."""

    input_xlsx: str


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

class CALIONConfig(TypedDict, total=False):
    """Top-level configuration dictionary.

    This is the type of the merged config dict that flows through the
    entire framework after ``load_and_merge()`` returns.
    """

    system: SystemConfig
    grid: GridConfig
    costs: CostsConfig
    run: RunConfig
    scenario: ScenarioConfig
    inputs: InputsConfig
    site: SiteConfig
    fuels: Dict[str, Any]
    generators: Dict[str, Any]
    storage: Dict[str, Any]  # root-level legacy alias
    output: Dict[str, Any]
