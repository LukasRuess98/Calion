# Component Registry - Plugin Architecture

## 🎯 Overview

The EnerGIS Component Registry provides a **plugin architecture** for discovering, registering, and creating components dynamically. This enables:

- **Decoupled Design**: Components register themselves without modifying core code
- **Dynamic Discovery**: List and inspect components at runtime
- **Extensibility**: Users can add custom component types easily
- **Type Safety**: Protocol-based validation ensures components implement required methods

---

## 📦 Architecture

### Core Components

```
energis/models/
├── component.py           # Component protocol and base classes
├── registry.py            # ComponentRegistry and decorators
├── component_utils.py     # Helper functions and CLI tools
└── blocks/                # Built-in component implementations
    ├── heat_pump.py       # @register_component("heat_pump")
    ├── storage.py         # @register_component("storage")
    ├── stratified_storage.py
    ├── thermal_gen.py
    └── p2h.py
```

### Component Protocol

All components must implement the `Component` protocol:

```python
class Component(Protocol):
    name: str

    def attach(self, model, time_set, config, buses) -> Dict[str, Any]:
        """Attach component to Pyomo model."""
        ...

    def get_results(self, model, time_set) -> Dict[str, Any]:
        """Extract results from solved model."""
        ...

    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validate component configuration."""
        ...
```

---

## 🚀 Usage

### 1. List Registered Components

```python
from energis.models.component_utils import print_component_registry

print_component_registry(detailed=True)
```

**Output:**
```
================================================================================
  EnerGIS Component Registry
================================================================================

📂 CONVERTER
--------------------------------------------------------------------------------

  • heat_pump
    Class: HeatPumpBlock
    Module: energis.models.blocks.heat_pump

  • thermal_generator
    Class: ThermalGeneratorBlock
    Module: energis.models.blocks.thermal_gen

📂 STORAGE
--------------------------------------------------------------------------------

  • storage
    Class: StorageBlock
    Module: energis.models.blocks.storage

  • stratified_storage
    Class: StratifiedStorageBlock
    Module: energis.models.blocks.stratified_storage

================================================================================
Total: 5 components registered
================================================================================
```

### 2. Inspect Component Details

```python
from energis.models.component_utils import print_component_info

print_component_info('heat_pump')
```

**Output:**
```
================================================================================
  Component: heat_pump
================================================================================

Class:       HeatPumpBlock
Module:      energis.models.blocks.heat_pump
Category:    converter
Version:     1.0.0
Description: Heat pump with COP series and waste heat recovery

Parameters:
--------------------------------------------------------------------------------

  Required:
    • name: str
    • min_load: float
    • cop_series: List[float]
    • capacity_min_mw: float
    • capacity_max_mw: float
    • capacity_init_mw: float
    • investable: bool

  Optional:
    • wrg_cap_series: Optional[Dict[int, float]] = None
    • cop_default: float = 3.5
    • label: str = None
```

### 3. Create Components Dynamically

```python
from energis.models.registry import get_registry

registry = get_registry()

# Get component class
HeatPumpBlock = registry.get('heat_pump')

# Create instance
hp = registry.create(
    'heat_pump',
    name='HP_1',
    min_load=0.3,
    cop_series=[3.5, 3.6, 3.7, ...],
    capacity_min_mw=5.0,
    capacity_max_mw=20.0,
    capacity_init_mw=0.0,
    investable=True
)

# Attach to model
result = hp.attach(model, time_set, config, buses)
```

### 4. Discover Components by Category

```python
from energis.models.component_utils import discover_components_by_category

converters = discover_components_by_category('converter')
# ['heat_pump', 'thermal_generator', 'p2h']

storage_types = discover_components_by_category('storage')
# ['storage', 'stratified_storage']
```

---

## 🔧 Creating Custom Components

### Method 1: Using Decorator (Recommended)

```python
from energis.models.component import BaseComponent
from energis.models.registry import register_component

@register_component(
    "my_custom_chp",
    category="converter",
    description="Custom CHP with advanced controls",
    version="1.0.0"
)
class MyCustomCHP(BaseComponent):
    def __init__(self, name: str, capacity_mw: float, efficiency: float):
        super().__init__(name)
        self.capacity_mw = capacity_mw
        self.efficiency = efficiency

    def attach(self, model, time_set, config, buses):
        # Create Pyomo variables and constraints
        # ...
        return {
            'flows': {...},
            'investment': None,
            'metadata': {...}
        }

    def validate_config(self, config):
        if self.efficiency < 0 or self.efficiency > 1:
            raise ValueError(f"Invalid efficiency: {self.efficiency}")
```

### Method 2: Manual Registration

```python
from energis.models.registry import ComponentRegistry

ComponentRegistry.register(
    component_type='my_component',
    component_class=MyComponentClass,
    description='My custom component',
    category='converter'
)
```

---

## 🛠️ CLI Tools

The component registry includes command-line tools:

### List All Components

```bash
python -m energis.models.component_utils list
```

### Show Detailed Info

```bash
python -m energis.models.component_utils list --detailed
```

### Filter by Category

```bash
python -m energis.models.component_utils list --category converter
```

### Inspect Component

```bash
python -m energis.models.component_utils info heat_pump
```

### Export Documentation

```bash
python -m energis.models.component_utils export docs/registry.json
```

### Validate Configuration

```bash
python -m energis.models.component_utils validate heat_pump config.json
```

---

## 📝 Integration with Existing Code

### Current Status

✅ **Component Protocol Defined**: `energis/models/component.py`
✅ **Registry Implemented**: `energis/models/registry.py`
✅ **All Blocks Registered**: Heat pump, storage, generators, etc.
✅ **Utility Functions**: Discovery, inspection, validation
✅ **CLI Tools**: Command-line interface for registry

### Backward Compatibility

The registry is **fully backward compatible**. Existing code continues to work:

```python
# Existing code (still works)
from energis.models.blocks.heat_pump import HeatPumpBlock

hp = HeatPumpBlock(name='HP_1', ...)
```

```python
# New registry-based approach (optional)
from energis.models.registry import get_registry

hp = get_registry().create('heat_pump', name='HP_1', ...)
```

### Future Integration Opportunities

**Dashboard Integration**:
```python
# Network Designer could list available components from registry
registry = get_registry()
available_types = registry.list_components()

for comp_type in available_types:
    metadata = registry.get_metadata(comp_type)
    add_component_button(comp_type, metadata['description'])
```

**Dynamic System Builder**:
```python
# system_builder.py could use registry for dynamic creation
registry = get_registry()

for hp_config in config['system']['heat_pumps']:
    hp = registry.create('heat_pump', **hp_config)
    hp.attach(model, time_set, config, buses)
```

**Plugin Packages**:
```python
# Third-party packages can provide components
# my_custom_package/components.py

@register_component("advanced_storage", category="storage")
class AdvancedStorage(BaseComponent):
    ...

# User just imports the package
import my_custom_package
# Components automatically registered!
```

---

## 📚 Examples

### Run Demo Script

```bash
python examples/component_registry_demo.py
```

The demo script shows:
1. Listing all registered components
2. Inspecting component details
3. Discovering components by category
4. Getting metadata programmatically
5. Registering custom components
6. Creating components dynamically
7. Plugin architecture concepts
8. Integration examples

---

## 🎓 Best Practices

### 1. Always Use Protocol

Ensure custom components implement the `Component` protocol:

```python
from energis.models.component import BaseComponent  # Provides defaults

class MyComponent(BaseComponent):
    # Inherit from BaseComponent for default implementations
    pass
```

### 2. Validate in `__init__` and `validate_config`

```python
def __init__(self, name: str, capacity: float):
    super().__init__(name)
    if capacity <= 0:
        raise ValueError("Capacity must be positive")
    self.capacity = capacity

def validate_config(self, config: Dict[str, Any]):
    # Additional configuration validation
    pass
```

### 3. Use Descriptive Metadata

```python
@register_component(
    "my_component",
    category="converter",
    description="Clear, concise description of what this component does",
    version="1.0.0",
    author="Your Name"
)
```

### 4. Return Standardized Format from `attach()`

```python
def attach(self, model, time_set, config, buses):
    # ... create variables ...

    return {
        'flows': {
            'heat': {'output': Q_out},
            'electricity': {'input': P_in}
        },
        'investment': InvestmentResult(capacity=cap, build=build),
        'metadata': {...}
    }
```

---

## 🔍 Troubleshooting

### Component Not Found

```python
KeyError: Component type 'my_component' not found in registry
```

**Solution**: Ensure the module with `@register_component` is imported:

```python
import energis.models.blocks.heat_pump  # Import triggers registration
```

### Protocol Violation

```python
TypeError: Component class must implement method 'attach'
```

**Solution**: Inherit from `BaseComponent` or implement all required methods.

### Duplicate Registration

```python
ValueError: Component 'heat_pump' is already registered
```

**Solution**: Use `ComponentRegistry.unregister('heat_pump')` first, or choose different name.

---

## 📊 API Reference

### `ComponentRegistry`

```python
class ComponentRegistry:
    @classmethod
    def register(cls, component_type: str, component_class: Type[Component], ...) -> None
        """Register a component class."""

    @classmethod
    def get(cls, component_type: str) -> Type[Component]
        """Get component class by type."""

    @classmethod
    def create(cls, component_type: str, **kwargs) -> Component
        """Factory method to create component instance."""

    @classmethod
    def list_components(cls) -> List[str]
        """List all registered component types."""

    @classmethod
    def get_metadata(cls, component_type: str) -> Dict[str, Any]
        """Get metadata for a component type."""

    @classmethod
    def list_by_category(cls, category: str) -> List[str]
        """List components in a specific category."""
```

### Helper Functions

```python
# From energis.models.component_utils

def list_all_components() -> List[Dict[str, Any]]
    """List all registered components with metadata."""

def print_component_registry(detailed: bool = False)
    """Print formatted list of all components."""

def get_component_info(component_type: str) -> Optional[Dict[str, Any]]
    """Get detailed information about a component."""

def validate_component_config(component_type: str, config: Dict[str, Any]) -> List[str]
    """Validate a configuration dictionary."""

def discover_components_by_category(category: str) -> List[str]
    """Find all components in a category."""

def create_component_from_config(component_type: str, config: Dict[str, Any]) -> Component
    """Factory function to create component from config."""
```

---

## ✅ Summary

The Component Registry provides a **robust plugin architecture** that:

- ✅ Enables **dynamic component discovery** at runtime
- ✅ Supports **custom components** without modifying core code
- ✅ Provides **type safety** via Protocol validation
- ✅ Includes **CLI tools** for inspection and validation
- ✅ Is **fully backward compatible** with existing code
- ✅ Facilitates **third-party extensions** and plugins

**All existing blocks are already registered and ready to use!**

For questions or issues, see: `examples/component_registry_demo.py`
