"""
Configuration schemas for EnerGIS v2.0.

Type-safe dataclass-based configuration schemas that replace Dict[str, Any].
"""

from .asset_schema import (
    AssetCapacity,
    ExpansionPotential,
    ComponentAsset,
    HeatPumpAsset,
    StorageAsset,
    GeneratorAsset,
    P2HAsset,
    GridConnection,
)

from .network_schema import (
    NetworkNode,
    PipeCapacity,
    PipeExpansion,
    Pipe,
    Pump,
    HeatingCurve,
    ThermalNetwork,
    NetworkTopology,
)

from .tech_library_schema import (
    COPModel,
    HeatPumpTechnology,
    StorageTechnology,
    GeneratorTechnology,
    P2HTechnology,
    PipeTechnology,
    FuelProperties,
)

from .scenario_schema import (
    RepresentativePeriods,
    TimeConfig,
    CostConfig,
    ConstraintsConfig,
    OptimizationConfig,
    InitialState,
    TerminalConditions,
    Subsidies,
    EconomicsConfig,
    SensitivityConfig,
    SolverConfig,
    OutputConfig,
    ReportingConfig,
    AssetPaths,
    Scenario,
)

__all__ = [
    # Asset schemas
    'AssetCapacity',
    'ExpansionPotential',
    'ComponentAsset',
    'HeatPumpAsset',
    'StorageAsset',
    'GeneratorAsset',
    'P2HAsset',
    'GridConnection',

    # Network schemas
    'NetworkNode',
    'PipeCapacity',
    'PipeExpansion',
    'Pipe',
    'Pump',
    'HeatingCurve',
    'ThermalNetwork',
    'NetworkTopology',

    # Tech library schemas
    'COPModel',
    'HeatPumpTechnology',
    'StorageTechnology',
    'GeneratorTechnology',
    'P2HTechnology',
    'PipeTechnology',
    'FuelProperties',

    # Scenario schemas
    'RepresentativePeriods',
    'TimeConfig',
    'CostConfig',
    'ConstraintsConfig',
    'OptimizationConfig',
    'InitialState',
    'TerminalConditions',
    'Subsidies',
    'EconomicsConfig',
    'SensitivityConfig',
    'SolverConfig',
    'OutputConfig',
    'ReportingConfig',
    'AssetPaths',
    'Scenario',
]
