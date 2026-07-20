"""
Configuration schemas for CALION v2.0.

Type-safe dataclass-based configuration schemas that replace Dict[str, Any].
"""

from .asset_schema import (
    AssetCapacity,
    ComponentAsset,
    ExpansionPotential,
    GeneratorAsset,
    GridConnection,
    HeatPumpAsset,
    P2HAsset,
    StorageAsset,
)
from .network_schema import (
    HeatingCurve,
    NetworkNode,
    NetworkTopology,
    Pipe,
    PipeCapacity,
    PipeExpansion,
    Pump,
    ThermalNetwork,
)
from .scenario_schema import (
    AssetPaths,
    ConstraintsConfig,
    CostConfig,
    EconomicsConfig,
    InitialState,
    OptimizationConfig,
    OutputConfig,
    ReportingConfig,
    RepresentativePeriods,
    Scenario,
    SensitivityConfig,
    SolverConfig,
    Subsidies,
    TerminalConditions,
    TimeConfig,
)
from .tech_library_schema import (
    COPModel,
    FuelProperties,
    GeneratorTechnology,
    HeatPumpTechnology,
    P2HTechnology,
    PipeTechnology,
    StorageTechnology,
)

__all__ = [
    # Asset schemas
    'AssetCapacity',
    'AssetPaths',
    # Tech library schemas
    'COPModel',
    'ComponentAsset',
    'ConstraintsConfig',
    'CostConfig',
    'EconomicsConfig',
    'ExpansionPotential',
    'FuelProperties',
    'GeneratorAsset',
    'GeneratorTechnology',
    'GridConnection',
    'HeatPumpAsset',
    'HeatPumpTechnology',
    'HeatingCurve',
    'InitialState',
    # Network schemas
    'NetworkNode',
    'NetworkTopology',
    'OptimizationConfig',
    'OutputConfig',
    'P2HAsset',
    'P2HTechnology',
    'Pipe',
    'PipeCapacity',
    'PipeExpansion',
    'PipeTechnology',
    'Pump',
    'ReportingConfig',
    # Scenario schemas
    'RepresentativePeriods',
    'Scenario',
    'SensitivityConfig',
    'SolverConfig',
    'StorageAsset',
    'StorageTechnology',
    'Subsidies',
    'TerminalConditions',
    'ThermalNetwork',
    'TimeConfig',
]
