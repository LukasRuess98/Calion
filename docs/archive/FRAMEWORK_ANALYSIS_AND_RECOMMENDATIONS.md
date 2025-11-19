# EnerGIS Framework: Strukturanalyse und Verbesserungsvorschläge

**Datum:** 2025-11-18
**Vergleichsbasis:** Oemof.solph und PyPSA Designpatterns

---

## Zusammenfassung

Das EnerGIS-Framework ist ein solides, auf Pyomo basierendes MILP-Framework für Wärmenetzoptimierung mit ~6.500 Zeilen Python-Code. Die Analyse zeigt jedoch erhebliches Verbesserungspotenzial in den Bereichen **Modularität**, **Erweiterbarkeit** und **Architektur** im Vergleich zu etablierten Frameworks wie Oemof und PyPSA.

### Haupterkenntnisse

✅ **Stärken:**
- Minimale Abhängigkeiten (kein pandas erforderlich)
- Spezialisierung auf Wärmenetze
- Eingebaute Rolling-Horizon-Orchestrierung
- YAML-basierte Konfiguration

❌ **Schwächen:**
- **Keine Komponentenhierarchie** - Fehlende Abstraktion
- **Hardcodierte Komponentenintegration** - Schwer erweiterbar
- **Fehlende Bus-Abstraktion** - Listen statt dedizierte Objekte
- **Implizite Konventionen** - Keine expliziten Schnittstellen
- **Manuelle Orchestrierung** - Keine automatische Komponentenerkennung

---

## 1. Aktuelle Architektur

### 1.1 Komponenten-Struktur

```
energis/models/
├── system_builder.py         # 670 Zeilen - Monolithischer Builder
├── blocks/
│   ├── heat_pump.py          # 138 Zeilen - Duck-typed Block
│   ├── storage.py            # 246 Zeilen - Duck-typed Block
│   ├── thermal_gen.py        # 42 Zeilen  - Duck-typed Block
│   └── p2h.py                # 27 Zeilen  - Duck-typed Block
```

**Problem:** Alle Komponenten verwenden Duck-Typing mit `.attach(m, Tset, cfg, buses)` Interface, aber:
- Keine gemeinsame Basisklasse
- Keine expliziten Schnittstellen/Protokolle
- Inkonsistente Rückgabewerte
- Keine Typsicherheit

### 1.2 Bus-Modellierung

**Aktuell:** Flow-Listen in `system_builder.py`

```python
el_in: List = []    # Elektrische Eingänge
el_out: List = []   # Elektrische Ausgänge
ht_out: List = []   # Wärme-Ausgänge
ht_in: List = []    # Wärme-Eingänge
gas_in: List = []   # Gas-Eingänge
bio_in: List = []   # Biomasse-Eingänge
waste_in: List = [] # Abfall-Eingänge
```

**Problem:**
- Buses sind keine eigenständigen Objekte
- Manuelle Zuweisung in system_builder.py (Zeilen 270-277, 340-341, etc.)
- Schwer erweiterbar (neue Bus-Typen erfordern Code-Änderungen)
- Keine Kapazitätsgrenzen oder Transport-Verluste möglich

### 1.3 Komponenten-Integration

**Aktueller Ablauf im system_builder.py:**

```python
# Zeile 288-360: Heat Pumps (hardcodiert)
for hp in apply_heat_pump_defaults(syscfg):
    if not hp.get("enabled", True):
        continue
    block = HeatPumpBlock(...)
    fs = block.attach(m, m.t, cfg, {})
    ht_out.append(fs["Q_th_out"])
    el_in.append(fs["P_el_in"])

# Zeile 361-544: Storage (hardcodiert)
if sto_cfg.get("enabled", False):
    block = StorageBlock(...)
    fs = block.attach(m, m.t, cfg, {})
    ht_out.append(fs["Q_th_out"])
    ht_in.append(fs["Q_th_in"])

# Zeile 546-589: Generators (hardcodiert)
for key, par in gens.items():
    if not par.get("enabled", False):
        continue
    if key == "p2h":  # Spezialbehandlung!
        block = P2HBlock(...)
    else:
        block = ThermalGeneratorBlock(...)
    fs = block.attach(m, m.t, cfg, {})
    ht_out.append(fs["Q_th_out"])
```

**Problem:**
- Jeder Komponententyp ist explizit hardcodiert
- Spezielle if/else-Logik für verschiedene Typen
- Neue Komponenten erfordern Änderungen im system_builder.py
- Keine Registry oder Plugin-Architektur

---

## 2. Vergleich: Oemof.solph

### 2.1 Oemof Architektur-Prinzipien

**Komponentenhierarchie:**
```
oemof.network.Node (Basis)
├── Bus
├── Converter (früher Transformer)
│   ├── OffsetConverter
│   └── ExtractionTurbineCHPBlock
├── Source
├── Sink
└── GenericStorage
```

**Vorteile:**
- Klare Vererbungshierarchie
- Gemeinsame Schnittstellen durch Basisklasse
- Graph-basierte Modellierung (NetworkX)
- Automatische Constraint-Gruppierung

**Oemof Flow-Konzept:**
```python
from oemof import solph

# Buses sind First-Class-Citizens
heat_bus = solph.Bus(label="heat")
elec_bus = solph.Bus(label="electricity")

# Komponenten verbinden sich über Flows
heat_pump = solph.components.Converter(
    label="heat_pump",
    inputs={elec_bus: solph.Flow()},
    outputs={heat_bus: solph.Flow(nominal_value=10)}
)

# Automatische Registrierung im EnergySystem
energy_system = solph.EnergySystem()
energy_system.add(heat_bus, elec_bus, heat_pump)
```

### 2.2 Oemof Erweiterbarkeits-Pattern

**Facades (oemof.tabular):**
```python
# Vereinfachte Komponenten-Definitionen
from oemof.tabular.facades import HeatPump

hp = HeatPump(
    bus_elec=elec_bus,
    bus_heat=heat_bus,
    cop=3.5,
    capacity=10
)
```

**Sub-Networks (oemof 2025.02):**
- Verschachtelte Energiesysteme
- Wiederverwendbare Komponenten-Gruppen
- Funktional seit 2025.02 Developer Meeting

---

## 3. Vergleich: PyPSA

### 3.1 PyPSA Architektur-Prinzipien

**Komponenten-Modell:**
```python
import pypsa

# Network ist Container
n = pypsa.Network()

# Buses als DataFrame-Zeilen
n.add("Bus", "heat_bus", carrier="heat")
n.add("Bus", "elec_bus", carrier="electricity")

# Komponenten mit standardisierten Attributen
n.add("HeatPump",
      "hp1",
      bus0="elec_bus",
      bus1="heat_bus",
      efficiency=3.5,
      p_nom=10)

n.add("Store",
      "tes1",
      bus="heat_bus",
      e_nom=100,
      e_cyclic=True)
```

**Vorteile:**
- **DataFrame-basiert** - Einfache Datenmanipulation
- **Standardisierte Attribute** - Konsistente Schnittstelle
- **Override-Mechanismus** - Eigene Komponenten via `override_components`
- **pypsa.Components Class** (v1.0.0) - Zusätzliche Funktionalität

### 3.2 PyPSA Extensibility

**Custom Components:**
```python
# Override existierender Komponenten
override_components = {
    "Generator": {
        "attrs": {
            "custom_param": {"type": "float", "default": 0.0}
        }
    }
}

n = pypsa.Network(override_components=override_components)

# Neue Komponententypen
override_components["MyHeatPump"] = {
    "type": "branch",  # oder "one_port"
    "attrs": {"cop": {"type": "float"}, ...}
}
```

**Components Class (v1.0.0+):**
- Wrapper um pandas DataFrames
- Reduziert Boilerplate-Code
- Behält Kompatibilität mit direktem DataFrame-Zugriff

---

## 4. Identifizierte Schwachstellen

### 4.1 Fehlende Abstraktion

**Problem:** Keine gemeinsame Basisklasse/Interface

**Auswirkung:**
- Inkonsistente Implementierungen
- Schwer zu testen (keine Mock-Komponenten)
- Keine Garantien für .attach() Signatur
- Keine Typsicherheit

**Beispiel:**
```python
# HeatPumpBlock.attach() -> Dict mit "Q_th_out", "P_el_in", "capacity", "build"
# StorageBlock.attach() -> Dict mit "Q_th_out", "Q_th_in", "SOC", "cap_energy", ...
# ThermalGeneratorBlock.attach() -> Dict mit "Q_th_out", "fuel_in", "P_el_out"
```

Inkonsistente Keys, keine Dokumentation der Rückgabewerte.

### 4.2 Hardcodierte Integration

**Problem:** system_builder.py kennt alle Komponententypen explizit

**Zeilen 288-589:** Explizite Loops für:
- Heat Pumps (Zeile 288)
- Storage (Zeile 361)
- Generators (Zeile 546)
  - Mit Spezialfall für "p2h" (Zeile 554)

**Auswirkung:**
- Neue Komponenten = Code-Änderungen in system_builder.py
- Schwer für externe Erweiterungen
- Keine Plugin-Architektur
- Vendor Lock-In

### 4.3 Bus-Listen statt Bus-Objekte

**Problem:** Buses sind Python-Listen, keine dedizierten Klassen

**Auswirkung:**
- Keine Bus-spezifischen Eigenschaften (Kapazität, Verluste, Preise)
- Keine Transport-Kosten oder -Grenzen
- Schwer erweiterbar (z.B. District Heating Networks mit Temperaturstufen)
- Keine geografische Modellierung möglich

**Vergleich:**
| Feature | EnerGIS | Oemof | PyPSA |
|---------|---------|-------|-------|
| Bus als Objekt | ❌ | ✅ | ✅ |
| Bus-Kapazität | ❌ | ✅ | ✅ |
| Transport-Verluste | ❌ | ✅ | ✅ |
| Bus-Typen | ❌ | ✅ | ✅ |

### 4.4 Konfiguration vs. Code

**Problem:** Komponenten-Logik teils in YAML, teils in Code

**Beispiel:**
```yaml
# configs/systems/baseline.system.yaml
system:
  heat_pumps:
    - id: HP1
      wrg_source_column: WRG1_T_K
```

vs.

```python
# system_builder.py Zeile 292-297
wrg_col = None
if hp.get("wrg_source_column"):
    wrg_col = hp.get("wrg_source_column")
    if wrg_col not in table.columns and f"{wrg_col}_K" in table.columns:
        wrg_col = f"{wrg_col}_K"  # Implizite Konvention!
```

**Auswirkung:**
- Unklare Trennung zwischen Konfiguration und Logik
- Implizite Namenskonventionen ("_K" Suffix)
- Schwer zu dokumentieren

### 4.5 Fehlende Komponentenregistrierung

**Problem:** Keine zentrale Registry für verfügbare Komponenten

**Auswirkung:**
- Nutzer müssen source code lesen, um verfügbare Komponenten zu finden
- Keine programmatische Auflistung von Komponenten
- Schwer für UI/Tool-Integration
- Keine Versionierung von Komponenten

---

## 5. Empfohlene Verbesserungen

### 5.1 Komponentenhierarchie einführen

**Vorschlag:** Abstract Base Class mit typing.Protocol

```python
# energis/models/component.py
from __future__ import annotations
from typing import Protocol, Dict, Any, runtime_checkable
from abc import ABC, abstractmethod
import pyomo.environ as pyo

@runtime_checkable
class Component(Protocol):
    """Protocol für alle Komponenten im EnerGIS Framework."""

    name: str

    def attach(
        self,
        model: pyo.ConcreteModel,
        time_set: pyo.Set,
        config: Dict[str, Any],
        buses: Dict[str, 'Bus']
    ) -> Dict[str, Any]:
        """
        Fügt Komponente dem Pyomo-Modell hinzu.

        Returns:
            Dict mit standardisierten Keys:
            - 'flows': Dict[str, Dict[str, pyo.Var]] - Bus-Flow-Zuweisungen
            - 'investment': Optional[InvestmentResult] - Investment-Variablen
            - 'state': Optional[pyo.Var] - Zustandsvariablen (z.B. SOC)
        """
        ...

    def get_results(
        self,
        model: pyo.ConcreteModel,
        time_set: pyo.Set
    ) -> Dict[str, Any]:
        """Extrahiert Ergebnisse aus gelöstem Modell."""
        ...


class BaseComponent(ABC):
    """Basisklasse für alle Komponenten mit gemeinsamer Funktionalität."""

    def __init__(self, name: str, label: str = None):
        self.name = name
        self.label = label or name
        self._attached = False

    @abstractmethod
    def attach(self, model, time_set, config, buses):
        """Subklassen müssen attach() implementieren."""
        pass

    def get_results(self, model, time_set):
        """Default-Implementierung für Ergebnis-Extraktion."""
        return {}

    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validiert Konfigurationsparameter."""
        pass
```

**Vorteile:**
- Typsicherheit durch Protocol
- Gemeinsame Funktionalität in BaseComponent
- Klare Schnittstellen-Definition
- Bessere IDE-Unterstützung

### 5.2 Bus-Abstraktion einführen

**Vorschlag:** Dedizierte Bus-Klasse

```python
# energis/models/bus.py
from typing import Dict, List, Optional
from enum import Enum

class BusType(Enum):
    ELECTRICITY = "electricity"
    HEAT = "heat"
    FUEL_GAS = "fuel_gas"
    FUEL_BIOMASS = "fuel_biomass"
    FUEL_WASTE = "fuel_waste"
    HYDROGEN = "hydrogen"
    COOLING = "cooling"

class Bus(BaseComponent):
    """
    Bus-Klasse für Energie-/Stoffströme.

    Inspiriert von Oemof.solph und PyPSA.
    """

    def __init__(
        self,
        name: str,
        bus_type: BusType,
        *,
        capacity: Optional[float] = None,
        loss_factor: float = 0.0,
        price: Optional[List[float]] = None,
        co2_factor: Optional[List[float]] = None
    ):
        super().__init__(name)
        self.bus_type = bus_type
        self.capacity = capacity
        self.loss_factor = loss_factor
        self.price = price
        self.co2_factor = co2_factor
        self._inputs: List[pyo.Var] = []
        self._outputs: List[pyo.Var] = []

    def add_input(self, flow: pyo.Var) -> None:
        """Registriert Input-Flow."""
        self._inputs.append(flow)

    def add_output(self, flow: pyo.Var) -> None:
        """Registriert Output-Flow."""
        self._outputs.append(flow)

    def attach(self, model, time_set, config, buses):
        """Erstellt Bus-Balance-Constraint."""

        def balance_rule(m, t):
            inputs = sum(f[t] for f in self._inputs)
            outputs = sum(f[t] for f in self._outputs)
            return inputs * (1 - self.loss_factor) == outputs

        setattr(
            model,
            f"{self.name}_balance",
            pyo.Constraint(time_set, rule=balance_rule)
        )

        # Optional: Kapazitätsgrenze
        if self.capacity:
            def capacity_rule(m, t):
                return sum(f[t] for f in self._outputs) <= self.capacity

            setattr(
                model,
                f"{self.name}_capacity",
                pyo.Constraint(time_set, rule=capacity_rule)
            )

        return {'flows': {}}
```

**Vorteile:**
- Buses als First-Class-Citizens
- Kapazitätsgrenzen und Verluste möglich
- Erweiterbar für komplexere Netzwerke
- Konsistent mit Oemof/PyPSA

### 5.3 Komponenten-Registry

**Vorschlag:** Registry-Pattern für automatische Erkennung

```python
# energis/models/registry.py
from typing import Dict, Type, List
from .component import Component

class ComponentRegistry:
    """
    Zentrale Registry für alle verfügbaren Komponenten.

    Inspiriert von Oemof.tabular Facades.
    """

    _components: Dict[str, Type[Component]] = {}

    @classmethod
    def register(cls, name: str, component_class: Type[Component]):
        """Registriert neue Komponente."""
        if name in cls._components:
            raise ValueError(f"Component '{name}' already registered")
        cls._components[name] = component_class

    @classmethod
    def get(cls, name: str) -> Type[Component]:
        """Gibt Komponenten-Klasse zurück."""
        if name not in cls._components:
            raise KeyError(f"Component '{name}' not found in registry")
        return cls._components[name]

    @classmethod
    def list_components(cls) -> List[str]:
        """Liste aller registrierten Komponenten."""
        return list(cls._components.keys())

    @classmethod
    def create(cls, name: str, **kwargs) -> Component:
        """Factory-Methode für Komponenten-Erstellung."""
        component_class = cls.get(name)
        return component_class(**kwargs)


# Decorator für automatische Registrierung
def register_component(name: str):
    """Decorator für automatische Komponenten-Registrierung."""
    def decorator(cls):
        ComponentRegistry.register(name, cls)
        return cls
    return decorator
```

**Verwendung:**

```python
# energis/models/blocks/heat_pump.py
from energis.models.registry import register_component
from energis.models.component import BaseComponent

@register_component("heat_pump")
class HeatPumpBlock(BaseComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name)
        # ... existing code ...
```

**Vorteile:**
- Keine Code-Änderungen in system_builder.py für neue Komponenten
- Programmatische Auflistung verfügbarer Komponenten
- Plugin-Architektur ermöglicht externe Erweiterungen
- Bessere Testbarkeit

### 5.4 Generischer System Builder

**Vorschlag:** Builder nutzt Registry statt hardcodierte Logik

```python
# energis/models/system_builder_v2.py
from typing import Dict, Any, List
from energis.models.registry import ComponentRegistry
from energis.models.bus import Bus, BusType

def build_model_v2(table: TimeSeriesTable, cfg: Dict[str, Any], dt_h: float = 1.0):
    """
    Generischer Model-Builder mit automatischer Komponenten-Erkennung.

    Ersetzt hardcodierte Logik durch Registry-basierte Orchestrierung.
    """
    m = pyo.ConcreteModel(name="EnerGIS")
    T = len(table)
    m.t = pyo.RangeSet(1, T)

    # 1. Erstelle Buses
    buses = create_buses(cfg, m, m.t)

    # 2. Erstelle Komponenten aus Config
    components = create_components_from_config(cfg, table, buses)

    # 3. Attach alle Komponenten
    for component in components:
        flows = component.attach(m, m.t, cfg, buses)
        register_flows_with_buses(flows, buses)

    # 4. Erstelle Bus-Balancen (automatisch durch Bus.attach())
    for bus in buses.values():
        bus.attach(m, m.t, cfg, buses)

    # 5. Objective (generisch)
    m.obj = pyo.Objective(
        expr=build_objective(m, m.t, components, buses, cfg),
        sense=pyo.minimize
    )

    return m


def create_buses(cfg: Dict[str, Any], model, time_set) -> Dict[str, Bus]:
    """Erstellt Buses basierend auf Konfiguration."""
    buses_cfg = cfg.get("buses", {})
    buses = {}

    # Default-Buses
    buses["electricity"] = Bus("electricity", BusType.ELECTRICITY)
    buses["heat"] = Bus("heat", BusType.HEAT)

    # Custom Buses aus Config
    for bus_name, bus_cfg in buses_cfg.items():
        bus_type_str = bus_cfg.get("type", "generic")
        bus_type = BusType(bus_type_str)

        buses[bus_name] = Bus(
            bus_name,
            bus_type,
            capacity=bus_cfg.get("capacity"),
            loss_factor=bus_cfg.get("loss_factor", 0.0)
        )

    return buses


def create_components_from_config(
    cfg: Dict[str, Any],
    table: TimeSeriesTable,
    buses: Dict[str, Bus]
) -> List[Component]:
    """
    Erstellt Komponenten basierend auf Config und Registry.

    Keine hardcodierten if/else für Komponententypen!
    """
    components = []
    system_cfg = cfg.get("system", {})

    # Heat Pumps
    heat_pump_defaults = system_cfg.get("heat_pump_defaults", {})
    for hp_cfg in system_cfg.get("heat_pumps", []):
        if not hp_cfg.get("enabled", True):
            continue

        # Merge defaults
        hp_cfg_merged = {**heat_pump_defaults, **hp_cfg}

        # Registry-basierte Erstellung
        hp = ComponentRegistry.create(
            "heat_pump",
            name=hp_cfg_merged.get("id", "HP"),
            **build_heat_pump_params(hp_cfg_merged, table, cfg)
        )
        components.append(hp)

    # Storage
    storage_cfg = system_cfg.get("storage", {})
    if storage_cfg.get("enabled", False):
        storage = ComponentRegistry.create(
            "storage",
            name="TES",
            **build_storage_params(storage_cfg, cfg)
        )
        components.append(storage)

    # Generators (generisch!)
    for gen_name, gen_cfg in system_cfg.get("generators", {}).items():
        if not gen_cfg.get("enabled", False):
            continue

        # Bestimme Komponententyp aus Config oder defaults
        component_type = gen_cfg.get("component_type", "thermal_generator")
        if gen_name == "p2h":
            component_type = "p2h"

        gen = ComponentRegistry.create(
            component_type,
            name=gen_name.upper(),
            **build_generator_params(gen_name, gen_cfg, cfg)
        )
        components.append(gen)

    return components
```

**Vorteile:**
- **Generisch:** Keine hardcodierten Komponententypen
- **Erweiterbar:** Neue Komponenten via Registry
- **Übersichtlich:** Klare Struktur statt 670 Zeilen
- **Testbar:** Einfaches Mocking von Komponenten

### 5.5 Standardisierte Flow-Deklaration

**Vorschlag:** Explizite Flow-Definitionen in Komponenten

```python
# energis/models/component.py (Erweiterung)
from dataclasses import dataclass
from typing import Literal

@dataclass
class Flow:
    """
    Flow-Definition für Verbindungen zwischen Komponenten und Buses.

    Inspiriert von Oemof.solph Flow-Konzept.
    """
    bus: str
    direction: Literal["input", "output"]
    variable: Optional[pyo.Var] = None
    nominal_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    investment: bool = False


class BaseComponent(ABC):
    """Erweiterte Basisklasse mit Flow-Deklaration."""

    def __init__(self, name: str):
        self.name = name
        self.flows: List[Flow] = []

    def add_flow(self, flow: Flow) -> None:
        """Registriert Flow für diese Komponente."""
        self.flows.append(flow)

    def get_flows_for_bus(self, bus_name: str) -> List[Flow]:
        """Gibt alle Flows für einen bestimmten Bus zurück."""
        return [f for f in self.flows if f.bus == bus_name]
```

**Verwendung:**

```python
# energis/models/blocks/heat_pump.py (refactored)
@register_component("heat_pump")
class HeatPumpBlock(BaseComponent):
    def attach(self, model, time_set, config, buses):
        # Erstelle Variablen
        Q_th_out = pyo.Var(time_set, domain=pyo.NonNegativeReals)
        P_el_in = pyo.Var(time_set, domain=pyo.NonNegativeReals)

        # Deklariere Flows
        self.add_flow(Flow(
            bus="heat",
            direction="output",
            variable=Q_th_out,
            investment=self.investable
        ))

        self.add_flow(Flow(
            bus="electricity",
            direction="input",
            variable=P_el_in
        ))

        # Registriere bei Buses
        buses["heat"].add_output(Q_th_out)
        buses["electricity"].add_input(P_el_in)

        # ... rest of constraints ...

        return {
            'flows': {
                'heat': {'output': Q_th_out},
                'electricity': {'input': P_el_in}
            }
        }
```

**Vorteile:**
- Explizite Deklaration statt impliziter Rückgabe-Dicts
- Typsicherheit
- Einfachere Validierung
- Bessere Dokumentation

### 5.6 Konfiguration-Schema-Validierung

**Vorschlag:** Pydantic-basierte Config-Validierung

```python
# energis/models/config_schema.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal

class HeatPumpConfig(BaseModel):
    """Typsichere Konfiguration für Wärmepumpen."""
    id: str
    enabled: bool = True
    type: Literal["standard", "high_temp", "low_temp"] = "standard"
    wrg_source_column: Optional[str] = None
    wrg_capacity_column: Optional[str] = None
    max_th_mw: float = Field(gt=0)
    min_th_mw: float = Field(ge=0)

    investment: Optional[InvestmentConfig] = None

    @validator("min_th_mw")
    def min_less_than_max(cls, v, values):
        if "max_th_mw" in values and v > values["max_th_mw"]:
            raise ValueError("min_th_mw must be <= max_th_mw")
        return v


class StorageConfig(BaseModel):
    """Typsichere Konfiguration für Speicher."""
    enabled: bool = False
    min_energy_mwh: float = Field(ge=0, default=0.0)
    max_energy_mwh: float = Field(gt=0, default=100.0)
    max_power_mw: float = Field(gt=0, default=30.0)
    soc0_mwh: float = Field(ge=0, default=0.0)
    eff_charge: float = Field(gt=0, le=1.0, default=0.95)
    eff_discharge: float = Field(gt=0, le=1.0, default=0.95)

    terminal: TerminalConfig = Field(default_factory=TerminalConfig)
    investment: Optional[InvestmentConfig] = None


class SystemConfig(BaseModel):
    """Gesamte System-Konfiguration."""
    heat_pump_defaults: HeatPumpConfig = Field(default_factory=HeatPumpConfig)
    heat_pumps: List[HeatPumpConfig] = []
    storage: StorageConfig = Field(default_factory=StorageConfig)
    generators: Dict[str, GeneratorConfig] = {}


# Verwendung
def load_and_validate_config(config_dict: Dict[str, Any]) -> SystemConfig:
    """Lädt und validiert Konfiguration mit Pydantic."""
    try:
        return SystemConfig(**config_dict["system"])
    except ValidationError as e:
        # Detaillierte Fehlermeldungen
        raise ValueError(f"Invalid configuration: {e}")
```

**Vorteile:**
- Typsicherheit für Konfigurationen
- Automatische Validierung
- Bessere Fehlermeldungen
- IDE-Autovervollständigung

---

## 6. Implementierungsplan

### Phase 1: Grundlagen (2-3 Wochen)

**Ziel:** Basis-Abstraktion ohne Breaking Changes

1. **Component Protocol & BaseClass erstellen**
   - `energis/models/component.py`
   - Protocol-Definition
   - BaseComponent mit gemeinsamer Funktionalität

2. **Bestehende Komponenten refactoren**
   - HeatPumpBlock, StorageBlock, etc. erben von BaseComponent
   - Konsistente .attach() Rückgabewerte
   - Keine funktionalen Änderungen

3. **Tests anpassen**
   - Sicherstellen, dass alle Tests weiter laufen
   - Neue Tests für BaseComponent

**Deliverables:**
- ✅ Component-Abstraktion
- ✅ Refactored blocks
- ✅ Passing tests

---

### Phase 2: Bus-Abstraktion (2-3 Wochen)

**Ziel:** Dedizierte Bus-Klasse

1. **Bus-Klasse implementieren**
   - `energis/models/bus.py`
   - BusType Enum
   - Bus mit add_input/add_output

2. **system_builder.py refactoren**
   - Listen durch Bus-Objekte ersetzen
   - `create_buses()` Funktion
   - Bus-Balance durch Bus.attach()

3. **Rückwärtskompatibilität sicherstellen**
   - Alte API weiterhin unterstützen (deprecation warnings)
   - Migration-Guide

**Deliverables:**
- ✅ Bus-Klasse
- ✅ Refactored system_builder
- ✅ Migration guide

---

### Phase 3: Component Registry (3-4 Wochen)

**Ziel:** Generische Komponenten-Integration

1. **Registry implementieren**
   - `energis/models/registry.py`
   - ComponentRegistry-Klasse
   - @register_component Decorator

2. **Alle Komponenten registrieren**
   - Decorator zu allen Block-Klassen hinzufügen
   - Automatische Registrierung beim Import

3. **Generischen Builder erstellen**
   - `build_model_v2()` parallel zu `build_model()`
   - Config-basierte Komponenten-Erstellung
   - Feature-Flag für neuen Builder

4. **Tests & Benchmarks**
   - Vergleich alte vs. neue Builder
   - Performance-Tests
   - Integrationstests

**Deliverables:**
- ✅ ComponentRegistry
- ✅ build_model_v2()
- ✅ A/B Testing

---

### Phase 4: Flow-Abstraktion (2-3 Wochen)

**Ziel:** Explizite Flow-Definitionen

1. **Flow-Dataclass**
   - `Flow` mit standardisierten Attributen
   - Integration in BaseComponent

2. **Komponenten refactoren**
   - Alle Komponenten verwenden Flow-Deklaration
   - Konsistente Bus-Registrierung

3. **Validierung**
   - Flow-Validierung bei attach()
   - Fehler bei ungültigen Bus-Verbindungen

**Deliverables:**
- ✅ Flow-Abstraktion
- ✅ Refactored components
- ✅ Validation

---

### Phase 5: Config-Validierung (1-2 Wochen)

**Ziel:** Typsichere Konfigurationen

1. **Pydantic-Schemas**
   - `energis/models/config_schema.py`
   - Schemas für alle Komponenten

2. **Config-Loader**
   - Validierung beim Laden
   - Detaillierte Fehlermeldungen

3. **Dokumentation**
   - Schema-Dokumentation
   - Beispiel-Configs

**Deliverables:**
- ✅ Config-Schemas
- ✅ Validierung
- ✅ Dokumentation

---

### Phase 6: Migration & Cleanup (1-2 Wochen)

**Ziel:** Alte Implementierung entfernen

1. **Deprecation Cycle**
   - Alte APIs als deprecated markieren
   - Warnings für 1-2 Versionen

2. **Cleanup**
   - Alte Implementierungen entfernen
   - Code-Deduplizierung

3. **Final Testing**
   - Full Regression Suite
   - Performance Benchmarks

**Deliverables:**
- ✅ Clean codebase
- ✅ Updated docs
- ✅ Release notes

---

## 7. Beispiel: Neue Komponente hinzufügen

### 7.1 Aktueller Prozess (❌ Komplex)

**Neue "Solarthermie"-Komponente:**

1. **Block-Klasse erstellen:**
   ```python
   # energis/models/blocks/solar_thermal.py
   class SolarThermalBlock:
       def __init__(self, name, area, ...):
           self.name = name
           # ...

       def attach(self, m, Tset, cfg, buses):
           # Manuell Pyomo-Variablen erstellen
           # Manuell Constraints definieren
           # Rückgabe-Dict (welche Keys?)
           return {"Q_th_out": Q, ...}
   ```

2. **system_builder.py ändern:**
   ```python
   # Zeile ~590: Neuer Block hinzufügen
   from .blocks.solar_thermal import SolarThermalBlock

   # Zeile ~650: Hardcodierte Integration
   solar_cfg = syscfg.get("solar_thermal", {})
   if solar_cfg.get("enabled", False):
       block = SolarThermalBlock(...)
       fs = block.attach(m, m.t, cfg, {})
       ht_out.append(fs["Q_th_out"])  # Welcher Key?
   ```

3. **Config-Support:**
   ```yaml
   # configs/systems/baseline.system.yaml
   system:
     solar_thermal:  # Wie heißt das Feld? Keine Schema-Validierung!
       enabled: true
       area: 100
   ```

4. **Tech-Catalog:**
   ```yaml
   # configs/tech_catalog.yaml
   solar_thermal:  # Konsistent mit system config?
     efficiency: 0.7
   ```

**Probleme:**
- 4 Dateien ändern
- Keine Typsicherheit
- Implizite Konventionen
- Fehleranfällig

---

### 7.2 Neuer Prozess (✅ Einfach)

**Neue "Solarthermie"-Komponente:**

1. **Block-Klasse mit Decorator:**
   ```python
   # energis/models/blocks/solar_thermal.py
   from energis.models.component import BaseComponent
   from energis.models.registry import register_component
   from energis.models.bus import Flow

   @register_component("solar_thermal")  # Automatische Registrierung!
   class SolarThermalBlock(BaseComponent):
       def __init__(
           self,
           name: str,
           area: float,
           efficiency: float = 0.7
       ):
           super().__init__(name)
           self.area = area
           self.efficiency = efficiency

       def attach(self, model, time_set, config, buses):
           # Erstelle Variablen
           Q_th_out = pyo.Var(time_set, domain=pyo.NonNegativeReals)

           # Deklariere Flow (explizit!)
           self.add_flow(Flow(
               bus="heat",
               direction="output",
               variable=Q_th_out
           ))

           # Registriere bei Bus (automatisch durch Flow)
           buses["heat"].add_output(Q_th_out)

           # Constraints
           # ... (solar-spezifische Logik)

           # Standardisierter Return
           return {
               'flows': {
                   'heat': {'output': Q_th_out}
               }
           }
   ```

2. **Config-Schema (optional, aber empfohlen):**
   ```python
   # energis/models/config_schema.py
   class SolarThermalConfig(BaseModel):
       enabled: bool = False
       area: float = Field(gt=0, description="Collector area in m²")
       efficiency: float = Field(gt=0, le=1.0, default=0.7)
   ```

3. **Config verwenden:**
   ```yaml
   # configs/systems/baseline.system.yaml
   system:
     solar_thermal:
       enabled: true
       area: 100
       efficiency: 0.75
   ```

**Fertig!** Keine Änderungen in system_builder.py nötig!

**Vorteile:**
- Nur 1-2 Dateien ändern
- Automatische Registrierung
- Explizite Flow-Deklaration
- Optional: Schema-Validierung

---

## 8. Vergleichstabelle: Alt vs. Neu

| Aspekt | Aktuell (Alt) | Vorgeschlagen (Neu) |
|--------|--------------|---------------------|
| **Komponenten-Abstraktion** | ❌ Duck-Typing | ✅ Protocol + BaseClass |
| **Bus-Modellierung** | ❌ Python-Listen | ✅ Dedizierte Bus-Klasse |
| **Komponenten-Integration** | ❌ Hardcodiert in builder | ✅ Registry-basiert |
| **Neue Komponente hinzufügen** | ❌ 4+ Dateien ändern | ✅ 1 Datei + Decorator |
| **Flow-Deklaration** | ❌ Implizite Dict-Keys | ✅ Explizite Flow-Objekte |
| **Config-Validierung** | ❌ Manuell / Runtime Errors | ✅ Pydantic-Schemas |
| **Typsicherheit** | ❌ Keine | ✅ typing.Protocol + Pydantic |
| **Extensibility** | ⚠️ Schwierig | ✅ Plugin-Architektur |
| **Testbarkeit** | ⚠️ Integration-Tests only | ✅ Unit + Integration |
| **Dokumentation** | ⚠️ Implizite Konventionen | ✅ Explizite Schemas |
| **IDE-Support** | ⚠️ Begrenzt | ✅ Autocomplete + Type hints |

---

## 9. Risiken und Mitigations

### 9.1 Breaking Changes

**Risiko:** Bestehende Nutzer-Code bricht

**Mitigation:**
- **Deprecation Cycle:** Alte API 1-2 Versionen parallel unterstützen
- **Feature Flags:** Neue Implementierung opt-in
- **Migration Guide:** Schritt-für-Schritt Anleitung
- **Automated Migration:** Script für automatische Config-Migration

### 9.2 Performance

**Risiko:** Abstraktion reduziert Performance

**Mitigation:**
- **Benchmarking:** Alt vs. Neu Vergleich
- **Profiling:** Hotspots identifizieren
- **Optimierung:** Lazy evaluation, Caching
- **Target:** Max. 5% Performance-Overhead

### 9.3 Komplexität

**Risiko:** Framework wird zu abstrakt/komplex

**Mitigation:**
- **Einfache Defaults:** BaseComponent erledigt meiste Arbeit
- **Facades:** Vereinfachte High-Level API (wie oemof.tabular)
- **Dokumentation:** Klare Beispiele für gängige Use Cases
- **Progressive Enhancement:** Basis-Features einfach, Advanced opt-in

### 9.4 Maintenance Burden

**Risiko:** Mehr Code = Mehr Wartungsaufwand

**Mitigation:**
- **Code Cleanup:** Alte Implementierung entfernen nach Deprecation
- **Tests:** Umfassende Test-Suite
- **CI/CD:** Automatische Tests und Linting
- **Documentation:** Code-Comments und Type hints

---

## 10. Zusammenfassung und Empfehlungen

### 10.1 Kritische Verbesserungen (Must-Have)

1. **Component-Abstraktion** (Phase 1)
   - Ohne diese ist keine weitere Verbesserung sinnvoll
   - Basis für alle anderen Änderungen
   - Relativ geringer Aufwand (2-3 Wochen)

2. **Component Registry** (Phase 3)
   - Größter Impact auf Extensibility
   - Ermöglicht Plugin-Architektur
   - Reduziert Wartungsaufwand langfristig

3. **Bus-Abstraktion** (Phase 2)
   - Wichtig für komplexere Netzwerke
   - Konsistenz mit Oemof/PyPSA
   - Foundation für zukünftige Features

### 10.2 Nice-to-Have

4. **Flow-Abstraktion** (Phase 4)
   - Verbessert Code-Qualität
   - Nicht kritisch für Funktionalität

5. **Config-Validierung** (Phase 5)
   - Bessere User Experience
   - Verhindert Config-Fehler
   - Relativ geringer Aufwand

### 10.3 Langfristige Vision

**EnerGIS als modulares Framework:**
- Plugin-Ecosystem für Komponenten
- PyPI-Packages für spezialisierte Komponenten
- Community-Contributions einfach möglich
- Konsistent mit etablierten Frameworks (Oemof/PyPSA)

**Beispiel:**
```bash
pip install energis-core
pip install energis-heat-pumps-advanced  # Community-Plugin
pip install energis-hydrogen-systems     # Community-Plugin
```

---

## 11. Nächste Schritte

### Sofort (nächste Woche)

1. **Team-Review:** Dieses Dokument besprechen
2. **Priorisierung:** Welche Phasen sind kritisch?
3. **Proof of Concept:** Phase 1 in separatem Branch

### Kurzfristig (nächster Monat)

4. **Phase 1 implementieren:** Component-Abstraktion
5. **Test-Suite erweitern:** Sicherstellen, dass Refactoring safe ist
6. **Documentation:** Architecture Decision Records (ADRs)

### Mittelfristig (Q1 2026)

7. **Phasen 2-3:** Bus-Abstraktion + Registry
8. **Migration Guide:** Für bestehende Nutzer
9. **Release:** v2.0.0 mit neuer Architektur

### Langfristig (2026+)

10. **Plugin-Ecosystem:** Community-Komponenten
11. **Integration:** Oemof/PyPSA Interoperability
12. **Advanced Features:** Netzwerk-Topologie, geografische Modellierung

---

## 12. Referenzen

### Frameworks

- **Oemof.solph:** https://github.com/oemof/oemof-solph
- **PyPSA:** https://github.com/PyPSA/PyPSA
- **Oemof.tabular:** https://github.com/oemof/oemof-tabular

### Design Patterns

- **Component Pattern:** https://refactoring.guru/design-patterns/composite
- **Registry Pattern:** https://martinfowler.com/eaaCatalog/registry.html
- **Plugin Architecture:** https://martinfowler.com/articles/plugins.html

### Python Best Practices

- **typing.Protocol:** https://peps.python.org/pep-0544/
- **Pydantic:** https://docs.pydantic.dev/
- **ABC (Abstract Base Classes):** https://docs.python.org/3/library/abc.html

---

**Autor:** Claude (Anthropic)
**Erstellt:** 2025-11-18
**Version:** 1.0
