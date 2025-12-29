# EnerGIS v2.0 Architecture

**Version:** 2.0.0-alpha
**Status:** Implementation in progress
**Based on:** Oemof.solph and PyPSA design patterns

---

## Architecture Overview

```
energis/models/
├── component.py          # Core abstractions (Protocol, BaseComponent, Flow)
├── bus.py               # Bus abstraction for flow management
├── registry.py          # ComponentRegistry for plugin architecture
├── system_builder.py    # Legacy builder (v1.0 - still supported)
├── __init__.py         # Package exports
└── blocks/
    ├── heat_pump.py    # @register_component("heat_pump")
    ├── storage.py      # @register_component("storage")
    ├── thermal_gen.py  # @register_component("thermal_generator")
    └── p2h.py          # @register_component("p2h")
```

---

## Core Abstractions

### 1. Component Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Component(Protocol):
    """Interface that all components must implement."""

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

**Purpose:** Defines the contract all components must follow, enabling type checking and duck typing.

### 2. BaseComponent Class

```python
class BaseComponent(ABC):
    """Base class with common functionality."""

    def __init__(self, name: str, label: str = None):
        self.name = name
        self.label = label or name
        self.flows: List[Flow] = []

    def add_flow(self, flow: Flow) -> None:
        """Register a flow."""
        self.flows.append(flow)

    def get_flows_for_bus(self, bus_name: str) -> List[Flow]:
        """Get flows for specific bus."""
        return [f for f in self.flows if f.bus == bus_name]

    # Helper validation methods
    def _validate_positive(self, value, name, allow_zero=False): ...
    def _validate_range(self, value, name, min_val, max_val): ...
```

**Purpose:** Provides common functionality, reducing code duplication across components.

### 3. Flow Object

```python
@dataclass
class Flow:
    """Explicit flow declaration."""

    bus: str
    direction: Literal["input", "output"]
    variable: Optional[pyo.Var] = None
    nominal_value: Optional[float] = None
    investment: bool = False
    variable_costs: Optional[float] = None
```

**Purpose:** Explicit declaration of flows between components and buses, replacing implicit dict returns.

### 4. Bus Class

```python
class Bus(BaseComponent):
    """Bus for energy/commodity flows."""

    def __init__(self, name, bus_type, capacity=None, loss_factor=0.0):
        self.bus_type = bus_type
        self.capacity = capacity
        self.loss_factor = loss_factor
        self._inputs = []
        self._outputs = []

    def add_input(self, flow): ...
    def add_output(self, flow): ...

    def attach(self, model, time_set, config, buses):
        """Creates balance constraint: inputs * (1-loss) == outputs"""
        ...
```

**Purpose:** Buses as first-class objects, enabling capacity limits, losses, and network modeling.

### 5. ComponentRegistry

```python
class ComponentRegistry:
    """Central registry for component discovery."""

    @classmethod
    def register(cls, component_type, component_class, **metadata): ...

    @classmethod
    def get(cls, component_type) -> Type[Component]: ...

    @classmethod
    def create(cls, component_type, **kwargs) -> Component: ...

    @classmethod
    def list_components(cls) -> List[str]: ...
```

**Purpose:** Plugin architecture - components self-register via decorator, no hardcoding needed.

---

## Design Patterns

### 1. Protocol Pattern (Type Safety)

```python
@runtime_checkable
class Component(Protocol):
    def attach(self, ...): ...
```

**Benefits:**
- Duck typing with type checking
- IDE autocomplete support
- Runtime validation

### 2. Registry Pattern (Plugin Architecture)

```python
@register_component("my_component")
class MyComponent(BaseComponent):
    pass

# Automatically registered!
ComponentRegistry.get("my_component")
```

**Benefits:**
- No manual registration
- No framework modifications needed
- Discoverable components

### 3. Template Method Pattern (BaseComponent)

```python
class BaseComponent(ABC):
    def get_results(self, model, time_set):
        """Default implementation - can be overridden"""
        results = {}
        for flow in self.flows:
            results[...] = pyo.value(flow.variable[t])
        return results
```

**Benefits:**
- Code reuse
- Consistent behavior
- Easy to extend

### 4. Data Transfer Object (Flow, InvestmentResult)

```python
@dataclass
class Flow:
    bus: str
    direction: Literal["input", "output"]
    variable: Optional[pyo.Var] = None
```

**Benefits:**
- Explicit data structures
- Type hints
- Immutable (frozen=True optional)

---

## Component Lifecycle

```
1. Registration (Import time)
   ├─ @register_component decorator
   └─ ComponentRegistry.register()

2. Creation (Runtime)
   ├─ ComponentRegistry.create()  OR
   └─ Direct instantiation: MyComponent(...)

3. Configuration Validation
   └─ component.validate_config(config)

4. Attachment to Model
   ├─ component.attach(model, time_set, config, buses)
   ├─ Creates Pyomo variables/constraints
   ├─ Declares flows via add_flow()
   └─ Registers with buses

5. Optimization
   └─ Solver.solve(model)

6. Result Extraction
   └─ component.get_results(model, time_set)
```

---

## Standardized Return Format

All components return:

```python
{
    "flows": {
        "bus_name": {
            "input": pyo.Var,
            "output": pyo.Var
        }
    },
    "investment": InvestmentResult(
        capacity=pyo.Var,
        build=pyo.Var
    ),
    "state": pyo.Var,  # e.g., SOC for storage
    "metadata": {
        # Component-specific data
    },

    # Legacy compatibility (kept for backward compat)
    "Q_th_out": pyo.Var,
    "P_el_in": pyo.Var,
    ...
}
```

**Benefits:**
- Consistent structure
- Easy to parse
- Backward compatible
- Extensible

---

## Comparison with Oemof/PyPSA

| Feature | EnerGIS v1.0 | EnerGIS v2.0 | Oemof.solph | PyPSA |
|---------|-------------|-------------|-------------|-------|
| **Component Abstraction** | ❌ Duck typing | ✅ Protocol + Base | ✅ Node hierarchy | ✅ DataFrame-based |
| **Bus Modeling** | ❌ Lists | ✅ Objects | ✅ Bus class | ✅ Bus DataFrame |
| **Component Registration** | ❌ Hardcoded | ✅ Registry | ⚠️ Manual | ✅ Override mechanism |
| **Flow Declaration** | ❌ Implicit | ✅ Explicit | ✅ Flow objects | ✅ DataFrame columns |
| **Extensibility** | ⚠️ Difficult | ✅ Plugin arch | ✅ Subclassing | ✅ override_components |
| **Type Safety** | ❌ None | ✅ Protocol | ❌ None | ⚠️ Partial |
| **Backward Compat** | N/A | ✅ Full | ⚠️ Partial | ⚠️ Partial |

---

## Key Improvements

### 1. Extensibility

**Before (v1.0):**
```python
# Need to modify system_builder.py (50+ lines)
# Hardcode component type handling
if component_type == "new_component":
    block = NewComponentBlock(...)
    fs = block.attach(...)
    ht_out.append(fs["Q_th_out"])
```

**After (v2.0):**
```python
# Just create component with decorator
@register_component("new_component")
class NewComponent(BaseComponent):
    pass

# Auto-registered! No other changes needed.
```

### 2. Type Safety

**Before (v1.0):**
```python
# No type hints, no IDE support
def attach(self, m, Tset, cfg, buses):
    return {"Q_th_out": Q}  # What keys are valid?
```

**After (v2.0):**
```python
# Full type hints, IDE autocomplete
def attach(
    self,
    model: pyo.ConcreteModel,
    time_set: pyo.Set,
    config: Dict[str, Any],
    buses: Dict[str, Bus]
) -> Dict[str, Any]:
    return {"flows": {...}}  # Standardized structure
```

### 3. Explicit Flows

**Before (v1.0):**
```python
# Implicit - just return variables
return {"Q_th_out": Q, "P_el_in": P}
```

**After (v2.0):**
```python
# Explicit - declare flows
self.add_flow(Flow(bus="heat", direction="output", variable=Q))
self.add_flow(Flow(bus="electricity", direction="input", variable=P))
```

### 4. Bus Abstraction

**Before (v1.0):**
```python
# Lists - no capacity, no losses
ht_out = []
ht_out.append(Q)
```

**After (v2.0):**
```python
# Objects - capacity, losses, balance
heat_bus = Bus("heat", BusType.HEAT, capacity=100, loss_factor=0.05)
heat_bus.add_output(Q)
```

---

## Migration Strategy

### Phase 1 (DONE) ✅
- Component Protocol & BaseComponent
- Bus abstraction
- ComponentRegistry
- Refactor existing components

### Phase 2 (TODO) 🔲
- system_builder_v2.py (generic builder)
- Config schema validation (Pydantic)
- Extended test suite

### Phase 3 (TODO) 🔲
- Deprecation warnings for v1.0
- Migration tools
- Documentation

### Phase 4 (TODO) 🔲
- Remove v1.0 code (v3.0+)
- Advanced features
- Plugin marketplace

---

## Design Decisions

### Why Protocol instead of ABC only?

**Decision:** Use both Protocol (interface) and ABC (base class)

**Rationale:**
- Protocol: Type checking, duck typing compatibility
- ABC: Shared implementation, template methods
- Best of both worlds

### Why keep legacy return keys?

**Decision:** Include both new standardized format AND legacy keys

**Rationale:**
- Backward compatibility
- Gradual migration
- No breaking changes

### Why not use pandas like PyPSA?

**Decision:** Keep minimal dependencies

**Rationale:**
- EnerGIS goal: lightweight framework
- Pandas adds ~100MB dependency
- Custom TimeSeriesTable is sufficient

### Why ComponentRegistry instead of metaclass magic?

**Decision:** Explicit registration via decorator

**Rationale:**
- Explicit > implicit (Zen of Python)
- Easy to understand
- No metaclass complexity

---

## Future Enhancements

### v2.1: Network Topology
- Line/Link components
- Geographic bus connections
- Transport losses

### v2.2: Multi-Carrier
- Sector coupling
- Power-to-X
- Hydrogen networks

### v2.3: Uncertainty
- Stochastic optimization
- Scenario trees
- Robust optimization

### v3.0: Ecosystem
- Plugin marketplace
- Community components
- Oemof/PyPSA interop

---

## References

### Design Patterns
- Martin Fowler: https://martinfowler.com/eaaCatalog/
- Gang of Four: Design Patterns book

### Similar Frameworks
- Oemof.solph: https://github.com/oemof/oemof-solph
- PyPSA: https://github.com/PyPSA/PyPSA
- Calliope: https://github.com/calliope-project/calliope

### Python Protocols
- PEP 544: https://peps.python.org/pep-0544/

---

**Last Updated:** 2025-11-18
**Status:** Alpha - implementation in progress
**Feedback:** lukas.ruess@example.com
