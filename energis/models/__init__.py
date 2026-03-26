"""
EnerGIS Models Package - Component-based energy system modeling.

This package provides the core abstractions for building modular, extensible
energy system optimization models using Pyomo.

New Architecture (v2.0):
- Component Protocol and BaseComponent for type-safe component development
- Bus abstraction for explicit flow management
- ComponentRegistry for plugin architecture
- Standardized Flow objects for explicit flow declarations

The package maintains backward compatibility with the v1.0 system_builder
while providing a cleaner, more extensible architecture for future development.
"""

# Core abstractions
from .component import (
    Component,
    BaseComponent,
    Flow,
    InvestmentResult,
    BusType
)

from .bus import (
    Bus,
    create_default_buses,
    create_buses_from_config
)

from .registry import (
    ComponentRegistry,
    register_component,
    get_component,
    create_component,
    list_components
)

# Import all block classes to trigger @register_component decorators
# This ensures all components are registered when the package is imported
from .blocks.heat_pump import HeatPumpBlock
from .blocks.storage import StorageBlock
from .blocks.thermal_gen import ThermalGeneratorBlock
from .blocks.p2h import P2HBlock

# Legacy builder (v1.0) - still supported
from .system_builder import build_model

__all__ = [
    # Core abstractions
    'Component',
    'BaseComponent',
    'Flow',
    'InvestmentResult',
    'BusType',
    'Bus',
    'create_default_buses',
    'create_buses_from_config',

    # Registry
    'ComponentRegistry',
    'register_component',
    'get_component',
    'create_component',
    'list_components',

    # Component blocks
    'HeatPumpBlock',
    'StorageBlock',
    'ThermalGeneratorBlock',
    'P2HBlock',

    # Builder
    'build_model',
]


def list_registered_components():
    """
    List all registered component types with metadata.

    Returns:
        dict: Component types mapped to their metadata

    Example:
        >>> from energis.models import list_registered_components
        >>> components = list_registered_components()
        >>> for comp_type, meta in components.items():
        ...     print(f"{comp_type}: {meta['description']}")
    """
    return ComponentRegistry.get_all_metadata()


def get_component_info(component_type: str) -> dict:
    """
    Get detailed information about a component type.

    Args:
        component_type: Type identifier (e.g., "heat_pump", "storage")

    Returns:
        dict: Component metadata including description, category, etc.

    Example:
        >>> from energis.models import get_component_info
        >>> info = get_component_info("heat_pump")
        >>> print(info['description'])
    """
    return ComponentRegistry.get_metadata(component_type)


# Forward-compatible alias: ``from energis.models import components``
# maps to ``energis.models.blocks`` so new code can use the cleaner name
# while the physical directory keeps working.
import energis.models.blocks as components  # noqa: F401

__version__ = "2.0.0-alpha"
