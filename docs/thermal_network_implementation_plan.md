# Implementierungsplan: Thermische Netzwerk-Erweiterung

## Executive Summary

**Ziel:** Erweiterung des EnerGIS-Frameworks um detaillierte thermisch-hydraulische Netzwerkmodellierung

**Umfang:**
- 12 neue Komponenten-Klassen (inkl. Cooling & Seasonal Storage)
- 20 neue Constraint-Typen
- 4 neue Konfigurationsmodule
- ~5250 Zeilen Python-Code
- ~75 Unit-Tests

**Zeitrahmen:** 10-12 Wochen (1 Entwickler)

**Dependencies:**
- Keine neuen externen Libraries erforderlich
- Alles auf Basis von Pyomo + Gurobi

---

## Inhaltsverzeichnis

1. [Projektstruktur](#1-projektstruktur)
2. [Phase 1: Infrastruktur & Datenmodelle](#2-phase-1-infrastruktur--datenmodelle)
3. [Phase 2: Kern-Komponenten](#3-phase-2-kern-komponenten)
4. [Phase 3: Erweiterte Features](#4-phase-3-erweiterte-features)
5. [Phase 4: Integration & Testing](#5-phase-4-integration--testing)
6. [Phase 5: Dokumentation & Beispiele](#6-phase-5-dokumentation--beispiele)
7. [Code-Templates](#7-code-templates)
8. [Testing-Strategie](#8-testing-strategie)
9. [Migration von bestehenden Systemen](#9-migration-von-bestehenden-systemen)

---

## 1. Projektstruktur

### 1.1 Neue Verzeichnisstruktur

```
energis/
├── models/
│   ├── blocks/
│   │   ├── network/                      # NEU: Netzwerk-Komponenten
│   │   │   ├── __init__.py
│   │   │   ├── pipe.py                   # Rohr-Komponente
│   │   │   ├── pump.py                   # Pumpen-Komponente
│   │   │   ├── thermal_node.py           # Thermischer Knoten
│   │   │   ├── heat_exchanger.py         # Wärmeübertrager
│   │   │   └── valve.py                  # Ventil (Optional Phase 3)
│   │   │
│   │   ├── consumers/                    # NEU: Verbraucher
│   │   │   ├── __init__.py
│   │   │   ├── point_load.py             # Punktlast
│   │   │   └── distributed_load.py       # Verteilte Last
│   │   │
│   │   ├── steam/                        # NEU: Dampf-Komponenten (Phase 3)
│   │   │   ├── __init__.py
│   │   │   ├── steam_turbine.py
│   │   │   ├── steam_generator.py
│   │   │   └── condenser.py
│   │   │
│   │   ├── cooling/                      # NEU: Kälte-Komponenten (Phase 4)
│   │   │   ├── __init__.py
│   │   │   ├── chiller.py                # Kältemaschine
│   │   │   ├── cooling_tower.py          # Rückkühler
│   │   │   └── free_cooling.py           # Free Cooling
│   │   │
│   │   ├── heat_recovery/                # NEU: Wärmerückgewinnung (Phase 4)
│   │   │   ├── __init__.py
│   │   │   └── heat_recovery_unit.py     # Abwärme-Integration
│   │   │
│   │   ├── seasonal_storage/             # NEU: Saisonale Speicher (Phase 5)
│   │   │   ├── __init__.py
│   │   │   ├── ptes.py                   # Erdbeckenspeicher
│   │   │   └── ates.py                   # Aquifer-Speicher
│   │   │
│   │   ├── heat_pump.py                  # EXISTIERT → ERWEITERN (Kältenetz)
│   │   ├── storage.py                    # EXISTIERT
│   │   └── ...
│   │
│   ├── network/                          # NEU: Netzwerk-Logik
│   │   ├── __init__.py
│   │   ├── topology.py                   # Graph-basierte Topologie
│   │   ├── multi_network.py              # Multi-Netzwerk-Manager
│   │   └── geographic.py                 # Geografische Berechnungen
│   │
│   ├── linearization/                    # NEU: Linearisierungs-Utilities
│   │   ├── __init__.py
│   │   ├── pwl.py                        # PWL + SOS2 Helpers
│   │   ├── mccormick.py                  # McCormick Envelopes
│   │   └── steam_tables.py               # Dampftafel-Approximationen
│   │
│   ├── seasonal_storage/                 # NEU: Saisonale Speicher Utils
│   │   ├── __init__.py
│   │   └── time_aggregation.py           # Monatlich ↔ Stündlich
│   │
│   ├── component.py                      # EXISTIERT: Basis-Klassen
│   ├── bus.py                            # ERWEITERN: Multi-Netz
│   └── system_builder.py                 # ERWEITERN: Netzwerk-Support
│
├── config/
│   ├── catalogs/                         # NEU: Technologie-Kataloge
│   │   ├── pipes.yaml
│   │   ├── pumps.yaml
│   │   ├── insulation.yaml
│   │   ├── chillers.yaml
│   │   └── seasonal_storage.yaml
│   │
│   ├── networks/                         # NEU: Netzwerk-Konfigurationen
│   │   ├── network_definition.yaml       # Netzwerk-Parameter (T, p, etc.)
│   │   └── topology_example.yaml         # Beispiel-Topologie
│   │
│   ├── base.yaml                         # EXISTIERT
│   └── tech_catalog.yaml                 # EXISTIERT
│
├── tests/
│   ├── unit/
│   │   ├── network/                      # NEU: Netzwerk-Tests
│   │   │   ├── test_pipe.py
│   │   │   ├── test_pump.py
│   │   │   └── test_thermal_node.py
│   │   │
│   │   ├── cooling/                      # NEU: Cooling-Tests
│   │   │   ├── test_chiller.py
│   │   │   ├── test_cooling_tower.py
│   │   │   └── test_free_cooling.py
│   │   │
│   │   ├── seasonal_storage/             # NEU: Seasonal Storage Tests
│   │   │   ├── test_ptes.py
│   │   │   ├── test_ates.py
│   │   │   └── test_time_aggregation.py
│   │   │
│   │   └── linearization/                # NEU: Linearisierungs-Tests
│   │       ├── test_pwl.py
│   │       └── test_mccormick.py
│   │
│   ├── integration/                      # NEU: Integrationstests
│   │   ├── test_simple_network.py        # Einfaches 2-Knoten-Netz
│   │   ├── test_multi_network.py         # Multi-Temperatur
│   │   └── test_vs_tespy.py              # TESpy-Vergleich (optional)
│   │
│   └── fixtures/                         # NEU: Test-Daten
│       ├── simple_network.yaml
│       └── multi_temperature.yaml
│
└── examples/
    ├── notebooks/
    │   ├── 01_simple_district_heating.ipynb    # NEU
    │   ├── 02_multi_temperature_cascade.ipynb  # NEU
    │   └── 03_investment_optimization.ipynb    # NEU
    │
    └── configs/
        ├── district_heating_baseline.yaml      # NEU
        └── industrial_steam_network.yaml       # NEU
```

### 1.2 Dateien-Übersicht

| **Datei** | **Zeilen** | **Zweck** | **Status** |
|-----------|------------|-----------|------------|
| `network/pipe.py` | ~400 | Rohr-Komponente (Vorlauf/Rücklauf) | NEU |
| `network/pump.py` | ~350 | Pumpen-Komponente mit PWL | NEU |
| `network/thermal_node.py` | ~250 | Knoten mit Mischung | NEU |
| `network/heat_exchanger.py` | ~300 | Wärmeübertrager | NEU |
| `consumers/point_load.py` | ~200 | Punktuelle Last | NEU |
| `consumers/distributed_load.py` | ~350 | Verteilte Last | NEU |
| `linearization/pwl.py` | ~250 | PWL+SOS2 Utilities | NEU |
| `linearization/mccormick.py` | ~150 | McCormick Utilities | NEU |
| `network/topology.py` | ~300 | NetworkX Integration | NEU |
| `network/multi_network.py` | ~200 | Multi-Netz Manager | NEU |
| `cooling/chiller.py` | ~350 | Kältemaschine | NEU (Phase 4) |
| `cooling/cooling_tower.py` | ~250 | Rückkühler | NEU (Phase 4) |
| `cooling/free_cooling.py` | ~300 | Free Cooling | NEU (Phase 4) |
| `heat_recovery/heat_recovery_unit.py` | ~400 | Wärmerückgewinnung | NEU (Phase 4) |
| `heat_pump.py` (extend) | ~100 | Kältenetz-Anbindung | ERWEITERT (Phase 4) |
| `seasonal_storage/ptes.py` | ~400 | Erdbeckenspeicher | NEU (Phase 5) |
| `seasonal_storage/ates.py` | ~450 | Aquifer-Speicher | NEU (Phase 5) |
| `seasonal_storage/time_aggregation.py` | ~150 | Monatlich ↔ Stündlich | NEU (Phase 5) |
| **SUMME Basis** | **~2750** | | |
| **SUMME + Cooling/HR** | **~4150** | | |
| **SUMME + Seasonal Storage** | **~5250** | | |

---

## 2. Phase 1: Infrastruktur & Datenmodelle

**Dauer:** 1 Woche
**Ziel:** Grundlagen schaffen für Netzwerk-Modellierung

### 2.1 Task 1.1: Linearisierungs-Utilities erstellen

#### `energis/models/linearization/pwl.py`

**Zweck:** Wiederverwendbare PWL + SOS2 Implementierung

**Funktionen:**
```python
def create_pwl_sos2(
    model: pyo.ConcreteModel,
    name: str,
    x_var: pyo.Var,
    y_var: pyo.Var,
    x_points: List[float],
    y_points: List[float],
    index_set: Optional[pyo.Set] = None
) -> Tuple[pyo.Var, List[pyo.Constraint]]:
    """
    Erstellt PWL-Approximation mit SOS2-Constraints

    Returns:
        (lambda_vars, constraints_list)
    """

def piecewise_linear_curve(
    x_values: np.ndarray,
    curve_function: Callable,
    num_points: int = 10
) -> Tuple[List[float], List[float]]:
    """
    Generiert Stützstellen für PWL-Approximation

    Args:
        x_values: X-Bereich [x_min, x_max]
        curve_function: f(x) → y
        num_points: Anzahl Stützstellen

    Returns:
        (x_points, y_points)
    """

def validate_pwl_accuracy(
    x_test: np.ndarray,
    y_exact: np.ndarray,
    x_points: List[float],
    y_points: List[float],
    max_relative_error: float = 0.02
) -> Dict[str, float]:
    """
    Validiert PWL-Genauigkeit

    Returns:
        {"max_abs_error": ..., "max_rel_error": ..., "mean_error": ...}
    """
```

**Test:** `tests/unit/linearization/test_pwl.py`
```python
def test_pwl_quadratic():
    """Test PWL für y = x²"""
    x_pts = [0, 2, 4, 6, 8, 10]
    y_pts = [x**2 for x in x_pts]

    # Teste Genauigkeit
    x_test = np.linspace(0, 10, 100)
    y_exact = x_test**2

    metrics = validate_pwl_accuracy(x_test, y_exact, x_pts, y_pts)
    assert metrics["max_rel_error"] < 0.05  # < 5%

def test_pwl_pyomo_integration():
    """Test PWL mit Pyomo-Modell"""
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(0, 10))
    model.y = pyo.Var()

    x_pts = [0, 5, 10]
    y_pts = [0, 25, 100]

    lambda_vars, constraints = create_pwl_sos2(model, "pwl_test", model.x, model.y, x_pts, y_pts)

    # Setze x = 7 und löse
    model.x.fix(7)
    solver = pyo.SolverFactory('gurobi')
    solver.solve(model)

    # Erwarte y ≈ 49
    assert abs(pyo.value(model.y) - 49) < 0.1
```

---

#### `energis/models/linearization/mccormick.py`

**Zweck:** McCormick Envelopes für bilineare Terme

**Funktionen:**
```python
def create_mccormick_envelope(
    model: pyo.ConcreteModel,
    name: str,
    x_var: pyo.Var,
    y_var: pyo.Var,
    w_var: pyo.Var,
    x_bounds: Tuple[float, float],
    y_bounds: Tuple[float, float],
    index_set: Optional[pyo.Set] = None
) -> List[pyo.Constraint]:
    """
    Erstellt McCormick-Constraints für w = x · y

    Args:
        w_var: Produkt-Variable w = x · y
        x_bounds: (x_min, x_max)
        y_bounds: (y_min, y_max)

    Returns:
        Liste der 4 McCormick-Constraints
    """

def adaptive_bounds_from_solution(
    solution: Dict,
    var_name: str,
    percentile: float = 0.05
) -> Tuple[float, float]:
    """
    Berechnet engere Bounds aus vorheriger Lösung

    Args:
        solution: Lösungs-Dict mit Werten
        var_name: Variablenname
        percentile: Untere/obere Quantile für Bounds

    Returns:
        (tighter_min, tighter_max)
    """
```

**Test:** `tests/unit/linearization/test_mccormick.py`
```python
def test_mccormick_basic():
    """Test McCormick für w = x · y"""
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(1, 10))
    model.y = pyo.Var(bounds=(2, 20))
    model.w = pyo.Var()

    x_bounds = (1, 10)
    y_bounds = (2, 20)

    constraints = create_mccormick_envelope(
        model, "mc_test", model.x, model.y, model.w, x_bounds, y_bounds
    )

    # Setze x=5, y=10
    model.x.fix(5)
    model.y.fix(10)

    solver = pyo.SolverFactory('gurobi')
    solver.solve(model)

    # Erwarte w = 50
    assert abs(pyo.value(model.w) - 50) < 0.01

def test_mccormick_tightness():
    """Test dass enge Bounds bessere Approximation geben"""
    # ... (Vergleich weite vs. enge Bounds)
```

---

### 2.2 Task 1.2: Geografisches Modul

#### `energis/models/network/geographic.py`

**Zweck:** Koordinaten-basierte Berechnungen

**Funktionen:**
```python
@dataclass
class GeoCoordinate:
    """Geografische Koordinate"""
    x: float  # Ost-West [m]
    y: float  # Nord-Süd [m]
    z: float = 0.0  # Höhe [m ü. NN]

def euclidean_distance(
    coord1: GeoCoordinate,
    coord2: GeoCoordinate
) -> float:
    """Euklidische Distanz zwischen zwei Punkten [m]"""
    return np.sqrt(
        (coord1.x - coord2.x)**2 +
        (coord1.y - coord2.y)**2
    )

def manhattan_distance(
    coord1: GeoCoordinate,
    coord2: GeoCoordinate
) -> float:
    """Manhattan-Distanz (für städtische Netze) [m]"""
    return abs(coord1.x - coord2.x) + abs(coord1.y - coord2.y)

def calculate_pipe_lengths(
    nodes: Dict[str, GeoCoordinate],
    pipes: List[Dict],
    method: str = "euclidean"
) -> Dict[str, float]:
    """
    Berechnet Rohrlängen aus Koordinaten

    Args:
        nodes: {node_id: GeoCoordinate}
        pipes: [{"id": ..., "from": ..., "to": ...}, ...]
        method: "euclidean" | "manhattan"

    Returns:
        {pipe_id: length_m}
    """

def geodetic_pressure_change(
    z1: float,
    z2: float,
    rho: float = 971.8,
    g: float = 9.81
) -> float:
    """
    Geodätische Druckänderung [bar]

    Δp = ρ · g · Δz / 10^5
    """
    return -rho * g * (z2 - z1) / 1e5
```

**Test:** `tests/unit/network/test_geographic.py`
```python
def test_euclidean_distance():
    c1 = GeoCoordinate(x=0, y=0, z=0)
    c2 = GeoCoordinate(x=300, y=400, z=0)

    dist = euclidean_distance(c1, c2)
    assert abs(dist - 500.0) < 0.01  # 3-4-5 Dreieck

def test_geodetic_pressure():
    # 10m Höhenunterschied
    dp = geodetic_pressure_change(z1=0, z2=10)
    # Erwarte ca. -0.095 bar (Druckverlust bergauf)
    assert abs(dp - (-0.095)) < 0.01
```

---

### 2.3 Task 1.3: Netzwerk-Topologie Modul

#### `energis/models/network/topology.py`

**Zweck:** Graph-basierte Netzwerk-Struktur mit NetworkX

**Klassen & Funktionen:**
```python
import networkx as nx
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set

class NodeType(Enum):
    PRODUCER = "producer"
    CONSUMER = "consumer"
    JUNCTION = "junction"
    INTERFACE = "interface"  # Zwischen Netzen

class PipeDirection(Enum):
    UNIDIRECTIONAL = "unidirectional"
    BIDIRECTIONAL = "bidirectional"

@dataclass
class NetworkNode:
    """Netzwerk-Knoten"""
    id: str
    node_type: NodeType
    network_id: str
    coordinates: GeoCoordinate

    # Parameter (je nach Typ)
    T_supply: Optional[float] = None  # Erzeuger
    T_return: Optional[float] = None
    Q_demand_profile: Optional[str] = None  # Verbraucher (Pfad zu CSV)

@dataclass
class NetworkPipe:
    """Netzwerk-Rohr"""
    id: str
    from_node: str
    to_node: str
    network_id: str
    pipe_type: str  # "supply" | "return"

    # Optional: Überschreibe Auto-Berechnung
    length: Optional[float] = None  # Wenn None → aus Koordinaten

    # Investment
    is_investment: bool = False
    DN_options: Optional[List[str]] = None

class NetworkTopology:
    """
    Verwaltet Netzwerk-Topologie als gerichteter Graph
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, NetworkNode] = {}
        self.pipes: Dict[str, NetworkPipe] = {}

    def add_node(self, node: NetworkNode):
        """Füge Knoten hinzu"""
        self.nodes[node.id] = node
        self.graph.add_node(
            node.id,
            node_type=node.node_type,
            network_id=node.network_id,
            coordinates=node.coordinates
        )

    def add_pipe(self, pipe: NetworkPipe):
        """Füge Rohr hinzu"""
        self.pipes[pipe.id] = pipe

        # Berechne Länge falls nicht gegeben
        if pipe.length is None:
            pipe.length = euclidean_distance(
                self.nodes[pipe.from_node].coordinates,
                self.nodes[pipe.to_node].coordinates
            )

        self.graph.add_edge(
            pipe.from_node,
            pipe.to_node,
            pipe_id=pipe.id,
            length=pipe.length,
            pipe_type=pipe.pipe_type
        )

    def get_incoming_pipes(self, node_id: str) -> List[str]:
        """Rohre die in Knoten enden"""
        return [
            self.graph.edges[edge]["pipe_id"]
            for edge in self.graph.in_edges(node_id)
        ]

    def get_outgoing_pipes(self, node_id: str) -> List[str]:
        """Rohre die von Knoten starten"""
        return [
            self.graph.edges[edge]["pipe_id"]
            for edge in self.graph.out_edges(node_id)
        ]

    def validate_topology(self) -> List[str]:
        """
        Validiere Netzwerk-Topologie

        Returns:
            Liste von Fehlern (leer wenn OK)
        """
        errors = []

        # Check 1: Zusammenhängend?
        if not nx.is_weakly_connected(self.graph):
            errors.append("Netzwerk ist nicht zusammenhängend")

        # Check 2: Jedes Vorlauf-Rohr hat Rücklauf?
        supply_pipes = [p for p in self.pipes.values() if p.pipe_type == "supply"]
        for sp in supply_pipes:
            # Suche matching return pipe
            matching = [
                p for p in self.pipes.values()
                if p.pipe_type == "return"
                and p.from_node == sp.to_node
                and p.to_node == sp.from_node
            ]
            if not matching:
                errors.append(f"Vorlauf-Rohr {sp.id} hat kein Rücklauf-Pendant")

        # Check 3: Erzeuger haben Ausgang, Verbraucher Eingang
        for node in self.nodes.values():
            if node.node_type == NodeType.PRODUCER:
                if not self.get_outgoing_pipes(node.id):
                    errors.append(f"Erzeuger {node.id} hat keinen Ausgang")
            elif node.node_type == NodeType.CONSUMER:
                if not self.get_incoming_pipes(node.id):
                    errors.append(f"Verbraucher {node.id} hat keinen Eingang")

        return errors

    def visualize(self, output_path: Optional[str] = None):
        """Visualisiere Netzwerk (matplotlib)"""
        import matplotlib.pyplot as plt

        pos = {
            node_id: (node.coordinates.x, node.coordinates.y)
            for node_id, node in self.nodes.items()
        }

        # Farben nach Typ
        colors = {
            NodeType.PRODUCER: "red",
            NodeType.CONSUMER: "blue",
            NodeType.JUNCTION: "gray",
            NodeType.INTERFACE: "green"
        }

        node_colors = [colors[self.nodes[n].node_type] for n in self.graph.nodes()]

        nx.draw(
            self.graph,
            pos=pos,
            node_color=node_colors,
            with_labels=True,
            node_size=500,
            font_size=8
        )

        if output_path:
            plt.savefig(output_path)
        else:
            plt.show()

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "NetworkTopology":
        """Lade Topologie aus YAML-Datei"""
        import yaml

        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        topology = cls()

        # Nodes
        for node_data in data.get("nodes", []):
            node = NetworkNode(
                id=node_data["id"],
                node_type=NodeType(node_data["type"]),
                network_id=node_data["network"],
                coordinates=GeoCoordinate(**node_data["coordinates"]),
                T_supply=node_data.get("T_supply"),
                T_return=node_data.get("T_return"),
                Q_demand_profile=node_data.get("demand_profile")
            )
            topology.add_node(node)

        # Pipes
        for pipe_data in data.get("pipes", []):
            pipe = NetworkPipe(
                id=pipe_data["id"],
                from_node=pipe_data["from"],
                to_node=pipe_data["to"],
                network_id=pipe_data["network"],
                pipe_type=pipe_data["pipe_type"],
                length=pipe_data.get("length"),
                is_investment=pipe_data.get("invest", False),
                DN_options=pipe_data.get("DN_options")
            )
            topology.add_pipe(pipe)

        return topology
```

**Test:** `tests/unit/network/test_topology.py`
```python
def test_simple_topology():
    """Test einfaches 2-Knoten-Netz"""
    topo = NetworkTopology()

    # Producer
    topo.add_node(NetworkNode(
        id="chp_1",
        node_type=NodeType.PRODUCER,
        network_id="dh_ht",
        coordinates=GeoCoordinate(0, 0)
    ))

    # Consumer
    topo.add_node(NetworkNode(
        id="consumer_1",
        node_type=NodeType.CONSUMER,
        network_id="dh_ht",
        coordinates=GeoCoordinate(1000, 0)
    ))

    # Supply pipe
    topo.add_pipe(NetworkPipe(
        id="pipe_supply",
        from_node="chp_1",
        to_node="consumer_1",
        network_id="dh_ht",
        pipe_type="supply"
    ))

    # Return pipe
    topo.add_pipe(NetworkPipe(
        id="pipe_return",
        from_node="consumer_1",
        to_node="chp_1",
        network_id="dh_ht",
        pipe_type="return"
    ))

    # Validate
    errors = topo.validate_topology()
    assert len(errors) == 0

    # Check lengths
    assert topo.pipes["pipe_supply"].length == 1000.0
```

---

### 2.4 Task 1.4: Multi-Netzwerk Manager

#### `energis/models/network/multi_network.py`

**Zweck:** Verwaltet mehrere Netze mit verschiedenen Temperaturniveaus

**Klasse:**
```python
@dataclass
class NetworkDefinition:
    """Definition eines thermischen Netzes"""
    id: str
    name: str
    medium: str  # "water_liquid" | "water_steam"
    T_supply: float  # °C
    T_return: float  # °C
    p_nominal: float  # bar
    p_min: float  # bar
    p_max: float  # bar
    temperature_level: str  # "high" | "medium" | "low"

class MultiNetworkManager:
    """Verwaltet mehrere thermische Netze"""

    def __init__(self):
        self.networks: Dict[str, NetworkDefinition] = {}
        self.topologies: Dict[str, NetworkTopology] = {}
        self.interface_nodes: List[Tuple[str, str]] = []  # (net1, net2) Paare

    def add_network(self, network: NetworkDefinition):
        """Füge Netz hinzu"""
        self.networks[network.id] = network
        self.topologies[network.id] = NetworkTopology()

    def add_interface(self, network1_id: str, network2_id: str):
        """
        Füge Interface zwischen zwei Netzen hinzu
        (→ Wärmeübertrager erforderlich)
        """
        self.interface_nodes.append((network1_id, network2_id))

    def get_temperature_hierarchy(self) -> List[str]:
        """
        Sortiere Netze nach Temperatur (absteigend)

        Returns:
            [net_id_1, net_id_2, ...] mit T_1 > T_2 > ...
        """
        sorted_nets = sorted(
            self.networks.values(),
            key=lambda n: n.T_supply,
            reverse=True
        )
        return [n.id for n in sorted_nets]

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "MultiNetworkManager":
        """Lade Multi-Netz-Konfiguration aus YAML"""
        import yaml

        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        manager = cls()

        for net_data in data.get("networks", []):
            net = NetworkDefinition(**net_data)
            manager.add_network(net)

        for interface in data.get("interfaces", []):
            manager.add_interface(interface["network1"], interface["network2"])

        return manager
```

**Konfigurationsbeispiel:** `config/networks/multi_temperature_example.yaml`
```yaml
networks:
  - id: "steam_hp"
    name: "Hochdruck-Dampfnetz"
    medium: "water_steam"
    T_supply: 250
    T_return: 180
    p_nominal: 40
    p_min: 30
    p_max: 50
    temperature_level: "high"

  - id: "dh_ht"
    name: "Fernwärme Hochtemperatur"
    medium: "water_liquid"
    T_supply: 90
    T_return: 50
    p_nominal: 6
    p_min: 3
    p_max: 10
    temperature_level: "medium"

  - id: "dh_lt"
    name: "Fernwärme Niedertemperatur"
    medium: "water_liquid"
    T_supply: 55
    T_return: 35
    p_nominal: 3
    p_min: 2
    p_max: 6
    temperature_level: "low"

interfaces:
  - network1: "steam_hp"
    network2: "dh_ht"
  - network1: "dh_ht"
    network2: "dh_lt"
```

---

## 3. Phase 2: Kern-Komponenten

**Dauer:** 3 Wochen
**Ziel:** Implementierung der 6 Haupt-Komponenten

### 3.1 Task 2.1: Pipe Component

#### `energis/models/blocks/network/pipe.py`

**Struktur:**
```python
from energis.models.component import BaseComponent, Flow, register_component
from energis.models.linearization.pwl import create_pwl_sos2
import pyomo.environ as pyo
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class PipeConfig:
    """Konfiguration für Rohr-Komponente"""
    name: str
    from_node: str
    to_node: str
    network: str
    pipe_type: str  # "supply" | "return"

    # Geometrie
    length: float  # m (aus Topology)

    # NEU: Brownfield-Support
    existing: bool = False           # Rohr existiert bereits?
    invest: bool = False             # Investment möglich?

    # Für Brownfield (wenn existing=True):
    DN_fixed: Optional[str] = None   # z.B. "DN150"
    insulation_fixed: Optional[str] = None  # z.B. "standard"
    installation_year: Optional[int] = None
    condition: str = "good"          # "good" | "fair" | "poor"

    # Für Greenfield (wenn invest=True):
    DN_options: Optional[List[str]] = None  # ["DN100", "DN150", ...]
    insulation_options: Optional[List[str]] = None  # ["standard", "good", ...]

    # Grenzen
    m_flow_max: float = 100.0  # kg/s
    T_min: float = 20.0  # °C
    T_max: float = 120.0  # °C

@register_component("pipe", category="network")
class PipeBlock(BaseComponent):
    """
    Thermisches Rohr mit:
    - Druckverlust (Darcy-Weisbach, PWL)
    - Wärmeverlust (erdreichbasiert)
    - Temperaturabfall
    - Optional: Investment in DN und Isolierung
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.pipe_cfg = PipeConfig(**config)

        # Lade Katalog-Daten
        self.catalog = self._load_pipe_catalog()

    def attach(self, model: pyo.ConcreteModel, time_set: pyo.Set,
               config: Dict, buses: Dict) -> Dict[str, Any]:
        """
        Erstelle Pyomo-Variablen und Constraints
        """
        name = self.pipe_cfg.name
        T = time_set

        # ==================== Variablen ====================

        # Hydraulik
        model.add_component(
            f"{name}_m_flow",
            pyo.Var(T, domain=pyo.NonNegativeReals, bounds=(0, self.pipe_cfg.m_flow_max))
        )
        model.add_component(
            f"{name}_p_in",
            pyo.Var(T, bounds=(config["networks"][self.pipe_cfg.network]["p_min"],
                                config["networks"][self.pipe_cfg.network]["p_max"]))
        )
        model.add_component(
            f"{name}_p_out",
            pyo.Var(T, bounds=(config["networks"][self.pipe_cfg.network]["p_min"],
                                config["networks"][self.pipe_cfg.network]["p_max"]))
        )
        model.add_component(
            f"{name}_Δp",
            pyo.Var(T, domain=pyo.NonNegativeReals)
        )

        # Thermisch
        model.add_component(
            f"{name}_T_in",
            pyo.Var(T, bounds=(self.pipe_cfg.T_min, self.pipe_cfg.T_max))
        )
        model.add_component(
            f"{name}_T_out",
            pyo.Var(T, bounds=(self.pipe_cfg.T_min, self.pipe_cfg.T_max))
        )
        model.add_component(
            f"{name}_Q_loss",
            pyo.Var(T, domain=pyo.NonNegativeReals)
        )

        # Investment
        if self.pipe_cfg.invest:
            model.add_component(
                f"{name}_build",
                pyo.Var(domain=pyo.Binary)
            )

            # DN Auswahl
            DN_set = pyo.Set(initialize=self.pipe_cfg.DN_options)
            model.add_component(f"{name}_DN_set", DN_set)
            model.add_component(
                f"{name}_select_DN",
                pyo.Var(DN_set, domain=pyo.Binary)
            )

            # Isolierung Auswahl
            if self.pipe_cfg.insulation_options:
                ins_set = pyo.Set(initialize=self.pipe_cfg.insulation_options)
                model.add_component(f"{name}_insul_set", ins_set)
                model.add_component(
                    f"{name}_select_insul",
                    pyo.Var(ins_set, domain=pyo.Binary)
                )

        # Abgeleitete Parameter
        model.add_component(
            f"{name}_D",
            pyo.Var(domain=pyo.NonNegativeReals)  # Effektiver Durchmesser
        )
        model.add_component(
            f"{name}_U",
            pyo.Var(domain=pyo.NonNegativeReals)  # Effektiver U-Wert
        )

        # ==================== Constraints ====================

        # (1) Druckverlust
        self._add_pressure_drop_constraints(model, name, T)

        # (2) Wärmeverlust
        self._add_heat_loss_constraints(model, name, T, config)

        # (3) Energiebilanz
        self._add_energy_balance_constraints(model, name, T)

        # (4) Investment Logik
        if self.pipe_cfg.invest:
            self._add_investment_constraints(model, name)
        else:
            self._add_fixed_design_constraints(model, name)

        # ==================== Flows registrieren ====================

        m_flow_var = getattr(model, f"{name}_m_flow")

        # Flow zu Bus (je nach Netzwerk)
        # Wird von ThermalNode verwaltet, hier nur Variable bereitstellen

        return {
            "m_flow": m_flow_var,
            "p_in": getattr(model, f"{name}_p_in"),
            "p_out": getattr(model, f"{name}_p_out"),
            "T_in": getattr(model, f"{name}_T_in"),
            "T_out": getattr(model, f"{name}_T_out"),
        }

    def _add_pressure_drop_constraints(self, model, name, T):
        """
        Druckverlust: Δp = f(m²) mit PWL
        """
        m_flow = getattr(model, f"{name}_m_flow")
        p_in = getattr(model, f"{name}_p_in")
        p_out = getattr(model, f"{name}_p_out")
        Δp = getattr(model, f"{name}_Δp")
        D = getattr(model, f"{name}_D")

        # Druckverlust-Koeffizient berechnen
        # a = λ · L / (2·ρ·g·π²·D⁵) · 8
        # Für jetzt: Vereinfachung mit λ = 0.02 (turbulent)

        λ = 0.02  # Rohrreibungszahl
        L = self.pipe_cfg.length
        ρ = 971.8  # kg/m³ (Wasser bei 90°C)

        # PWL-Stützstellen für verschiedene DN
        # Wird dynamisch basierend auf gewähltem DN erstellt

        # Constraint: p_in - p_out = Δp + Δp_geo

        # Geodätischer Druck (aus Topologie)
        Δz = 0.0  # TODO: Aus Topologie holen
        Δp_geo = -ρ * 9.81 * Δz / 1e5  # bar

        def pressure_balance_rule(model, t):
            return p_in[t] - p_out[t] == Δp[t] + Δp_geo

        model.add_component(
            f"{name}_pressure_balance",
            pyo.Constraint(T, rule=pressure_balance_rule)
        )

        # PWL für Δp(m²)
        # Für jetzt: Vereinfachung mit fixem D
        # TODO: Erweitern für Investment mit mehreren DN

        D_fixed = 0.15  # m (DN150)
        a = λ * L * 8 / (2 * ρ * 9.81 * (3.14159**2) * (D_fixed**5))

        # Stützstellen
        m_pts = [0, 10, 20, 50, self.pipe_cfg.m_flow_max]
        Δp_pts = [a * m**2 / 1e5 for m in m_pts]  # in bar

        # PWL + SOS2
        for t in T:
            lambda_vars, constraints = create_pwl_sos2(
                model,
                f"{name}_pwl_dp_t{t}",
                m_flow[t],
                Δp[t],
                m_pts,
                Δp_pts
            )
            # Constraints werden automatisch hinzugefügt

    def _add_heat_loss_constraints(self, model, name, T, config):
        """
        Wärmeverlust: Q_loss = U · π · D · L · (T_avg - T_soil)
        """
        T_in = getattr(model, f"{name}_T_in")
        T_out = getattr(model, f"{name}_T_out")
        Q_loss = getattr(model, f"{name}_Q_loss")
        U = getattr(model, f"{name}_U")
        D = getattr(model, f"{name}_D")

        L = self.pipe_cfg.length

        # Erdreichtemperatur (zeitabhängig)
        T_soil_mean = config.get("T_soil_mean", 10.0)
        T_soil_amp = config.get("T_soil_amplitude", 5.0)

        def T_soil(t_hour):
            return T_soil_mean + T_soil_amp * np.sin(2*np.pi*(t_hour - 2190)/8760)

        # Approximation: T_avg ≈ T_in (konservativ)

        def heat_loss_rule(model, t):
            T_soil_t = T_soil(t)
            # Q_loss = U · π · D · L · (T_in - T_soil) / 1e6  # MW
            # Linearisierung: D und U sind Variablen → Produkt!
            # Vereinfachung: U·D als eine Variable "UD"
            return Q_loss[t] == U * 3.14159 * D * L * (T_in[t] - T_soil_t) / 1e6

        model.add_component(
            f"{name}_heat_loss",
            pyo.Constraint(T, rule=heat_loss_rule)
        )

    def _add_energy_balance_constraints(self, model, name, T):
        """
        Energiebilanz: m · cp · (T_in - T_out) = Q_loss
        """
        m_flow = getattr(model, f"{name}_m_flow")
        T_in = getattr(model, f"{name}_T_in")
        T_out = getattr(model, f"{name}_T_out")
        Q_loss = getattr(model, f"{name}_Q_loss")

        cp = 4.19  # kJ/(kg·K)

        def energy_balance_rule(model, t):
            # Q_loss = m · cp · ΔT
            # ΔT = Q_loss / (m · cp)
            #
            # Problem: Q_loss / m ist bilinear!
            #
            # Linearisierung: PWL über m-Bereiche
            # Oder: McCormick für m · ΔT
            #
            # Für jetzt: Vereinfachung
            return m_flow[t] * cp * (T_in[t] - T_out[t]) / 1000 == Q_loss[t]

        model.add_component(
            f"{name}_energy_balance",
            pyo.Constraint(T, rule=energy_balance_rule)
        )

    def _add_investment_constraints(self, model, name):
        """Investment-Logik für DN und Isolierung"""
        build = getattr(model, f"{name}_build")
        select_DN = getattr(model, f"{name}_select_DN")
        DN_set = getattr(model, f"{name}_DN_set")
        D = getattr(model, f"{name}_D")
        U = getattr(model, f"{name}_U")

        # (1) Genau eine DN wenn gebaut
        def dn_selection_rule(model):
            return sum(select_DN[dn] for dn in DN_set) == build

        model.add_component(
            f"{name}_dn_selection",
            pyo.Constraint(rule=dn_selection_rule)
        )

        # (2) D aus Auswahl
        def diameter_rule(model):
            return D == sum(
                select_DN[dn] * self.catalog["pipes"][dn]["diameter_inner"]
                for dn in DN_set
            )

        model.add_component(
            f"{name}_diameter",
            pyo.Constraint(rule=diameter_rule)
        )

        # (3) Isolierung (ähnlich)
        if self.pipe_cfg.insulation_options:
            select_insul = getattr(model, f"{name}_select_insul")
            ins_set = getattr(model, f"{name}_insul_set")

            def insul_selection_rule(model):
                return sum(select_insul[ins] for ins in ins_set) == build

            model.add_component(
                f"{name}_insul_selection",
                pyo.Constraint(rule=insul_selection_rule)
            )

            def u_value_rule(model):
                return U == sum(
                    select_insul[ins] * self.catalog["insulation"][ins]["U_value"]
                    for ins in ins_set
                )

            model.add_component(
                f"{name}_u_value",
                pyo.Constraint(rule=u_value_rule)
            )

    def _add_fixed_design_constraints(self, model, name):
        """Fixe DN und Isolierung"""
        D = getattr(model, f"{name}_D")
        U = getattr(model, f"{name}_U")

        DN_fixed = self.pipe_cfg.DN_fixed
        ins_fixed = self.pipe_cfg.insulation_fixed

        D_value = self.catalog["pipes"][DN_fixed]["diameter_inner"]
        U_value = self.catalog["insulation"][ins_fixed]["U_value"]

        D.fix(D_value)
        U.fix(U_value)

    def _load_pipe_catalog(self) -> Dict:
        """Lade Rohr- und Isolierungs-Katalog"""
        import yaml

        # TODO: Pfad aus Config
        catalog_path = "config/catalogs/pipes.yaml"

        with open(catalog_path, 'r') as f:
            return yaml.safe_load(f)

    def get_results(self, model, time_set) -> Dict[str, Any]:
        """Extrahiere Ergebnisse"""
        name = self.pipe_cfg.name

        results = {
            "m_flow": [pyo.value(getattr(model, f"{name}_m_flow")[t]) for t in time_set],
            "p_in": [pyo.value(getattr(model, f"{name}_p_in")[t]) for t in time_set],
            "p_out": [pyo.value(getattr(model, f"{name}_p_out")[t]) for t in time_set],
            "T_in": [pyo.value(getattr(model, f"{name}_T_in")[t]) for t in time_set],
            "T_out": [pyo.value(getattr(model, f"{name}_T_out")[t]) for t in time_set],
            "Q_loss": [pyo.value(getattr(model, f"{name}_Q_loss")[t]) for t in time_set],
        }

        if self.pipe_cfg.invest:
            DN_set = getattr(model, f"{name}_DN_set")
            select_DN = getattr(model, f"{name}_select_DN")

            selected_DN = [dn for dn in DN_set if pyo.value(select_DN[dn]) > 0.5]
            results["selected_DN"] = selected_DN[0] if selected_DN else None

        return results
```

**Hinweis:** Dieses Code-Template zeigt die Struktur. Die vollständige Implementierung erfordert weitere Verfeinerung der Linearisierungen.

**Test:** `tests/unit/network/test_pipe.py`
```python
def test_pipe_fixed_design():
    """Test Rohr mit fixem Design (kein Investment)"""
    # ... (Ähnlich wie existierende Component-Tests)

def test_pipe_investment():
    """Test Rohr mit DN-Investment"""
    # ...

def test_pipe_heat_loss():
    """Test Wärmeverlust-Berechnung"""
    # ...
```

---

#### Task 2.1.5: Brownfield Support für PipeBlock

**Zweck:** Implementiere Logik für bestehende Rohre (Brownfield-Szenarien)

**Erweiterte `_add_investment_constraints()` Methode:**
```python
def _add_investment_constraints(self, model, name):
    """Investment-Logik für DN und Isolierung"""

    # NEU: Brownfield-Check
    if self.pipe_cfg.existing:
        # Bestehendes Rohr: Geometrie ist FEST
        D = getattr(model, f"{name}_D")
        U = getattr(model, f"{name}_U")

        # Fixe Werte aus Katalog
        DN_fixed = self.pipe_cfg.DN_fixed
        ins_fixed = self.pipe_cfg.insulation_fixed

        if DN_fixed is None:
            raise ValueError(f"Pipe {name}: existing=True benötigt DN_fixed")

        D_value = self.catalog["pipes"][DN_fixed]["diameter_inner"]
        U_value = self.catalog["insulation"][ins_fixed]["U_value"]

        # Optional: Zustandsabhängige Anpassung
        if self.pipe_cfg.condition == "fair":
            U_value *= 1.1  # 10% mehr Verluste
        elif self.pipe_cfg.condition == "poor":
            U_value *= 1.2  # 20% mehr Verluste

        D.fix(D_value)
        U.fix(U_value)

        # Kein build_pipe Variable nötig (existiert bereits)
        # Falls Variable erstellt wurde, fixiere sie auf 1
        if hasattr(model, f"{name}_build"):
            getattr(model, f"{name}_build").fix(1)

        return  # Keine weiteren Investment-Constraints

    elif self.pipe_cfg.invest:
        # GREENFIELD: Investment-Optimierung (wie bisher)
        build = getattr(model, f"{name}_build")
        select_DN = getattr(model, f"{name}_select_DN")
        DN_set = getattr(model, f"{name}_DN_set")
        D = getattr(model, f"{name}_D")
        U = getattr(model, f"{name}_U")

        # (1) Genau eine DN wenn gebaut
        def dn_selection_rule(model):
            return sum(select_DN[dn] for dn in DN_set) == build

        model.add_component(
            f"{name}_dn_selection",
            pyo.Constraint(rule=dn_selection_rule)
        )

        # (2) D aus Auswahl
        def diameter_rule(model):
            return D == sum(
                select_DN[dn] * self.catalog["pipes"][dn]["diameter_inner"]
                for dn in DN_set
            )

        model.add_component(
            f"{name}_diameter",
            pyo.Constraint(rule=diameter_rule)
        )

        # (3) Isolierung (ähnlich)
        if self.pipe_cfg.insulation_options:
            select_insul = getattr(model, f"{name}_select_insul")
            ins_set = getattr(model, f"{name}_insul_set")

            def insul_selection_rule(model):
                return sum(select_insul[ins] for ins in ins_set) == build

            model.add_component(
                f"{name}_insul_selection",
                pyo.Constraint(rule=insul_selection_rule)
            )

            def u_value_rule(model):
                return U == sum(
                    select_insul[ins] * self.catalog["insulation"][ins]["U_value"]
                    for ins in ins_set
                )

            model.add_component(
                f"{name}_u_value",
                pyo.Constraint(rule=u_value_rule)
            )

    else:
        # Fixe Komponente ohne Investment (wie bisher)
        D = getattr(model, f"{name}_D")
        U = getattr(model, f"{name}_U")

        DN_fixed = self.pipe_cfg.DN_fixed
        ins_fixed = self.pipe_cfg.insulation_fixed

        D_value = self.catalog["pipes"][DN_fixed]["diameter_inner"]
        U_value = self.catalog["insulation"][ins_fixed]["U_value"]

        D.fix(D_value)
        U.fix(U_value)
```

**Erweiterte Kosten-Berechnung:**
```python
def get_capex(self, model) -> float:
    """Berechne CAPEX für Rohr"""
    name = self.pipe_cfg.name

    # BROWNFIELD: Kein CAPEX
    if self.pipe_cfg.existing:
        return 0.0

    # GREENFIELD: Investment-Kosten
    if self.pipe_cfg.invest:
        build = getattr(model, f"{name}_build")
        DN_set = getattr(model, f"{name}_DN_set")
        select_DN = getattr(model, f"{name}_select_DN")

        # CAPEX = build * (Σ select_DN[dn] * cost[dn])
        capex = 0.0
        for dn in DN_set:
            if pyo.value(select_DN[dn]) > 0.5:  # Gewählt
                pipe_catalog = self.catalog["pipes"][dn]
                capex = (
                    pipe_catalog.get("fixed_cost", 0) +
                    self.pipe_cfg.length * pipe_catalog["cost_per_m"]
                )
                break

        # Isolierungs-Kosten
        if self.pipe_cfg.insulation_options:
            ins_set = getattr(model, f"{name}_insul_set")
            select_insul = getattr(model, f"{name}_select_insul")

            for ins in ins_set:
                if pyo.value(select_insul[ins]) > 0.5:  # Gewählt
                    insul_catalog = self.catalog["insulation"][ins]
                    capex += self.pipe_cfg.length * insul_catalog["cost_per_m"]
                    break

        return capex * pyo.value(build)

    else:
        # Fixiert, kein Investment
        return 0.0

def get_opex(self, model, time_set, config) -> float:
    """Berechne OPEX für Rohr"""
    name = self.pipe_cfg.name
    Q_loss = getattr(model, f"{name}_Q_loss")

    # OPEX = Wärmeverluste * Wärmekosten
    # Gilt für ALLE Rohre (bestehend + neu)
    heat_cost = config.get("heat_cost", 50)  # EUR/MWh

    total_opex = 0.0
    for t in time_set:
        total_opex += pyo.value(Q_loss[t]) * heat_cost

    return total_opex
```

**Erweiterte Tests:**
```python
# tests/unit/network/test_pipe_brownfield.py

def test_pipe_existing_brownfield():
    """Test bestehendes Rohr (Brownfield)"""
    config = {
        "name": "pipe_existing_1",
        "from_node": "node_a",
        "to_node": "node_b",
        "network": "dh_ht",
        "pipe_type": "supply",
        "length": 1000.0,

        # Brownfield-Config
        "existing": True,
        "invest": False,
        "DN_fixed": "DN150",
        "insulation_fixed": "standard",
        "installation_year": 2010,
        "condition": "good"
    }

    model = pyo.ConcreteModel()
    model.T = pyo.RangeSet(1, 24)

    pipe = PipeBlock(config)
    vars_dict = pipe.attach(model, model.T, test_config, {})

    # Check: D und U sind fixiert
    D = getattr(model, "pipe_existing_1_D")
    U = getattr(model, "pipe_existing_1_U")

    assert D.fixed
    assert U.fixed
    assert abs(pyo.value(D) - 0.15) < 0.001  # DN150 → 0.15m

    # Check: Betriebsvariablen sind NICHT fixiert
    m_flow = getattr(model, "pipe_existing_1_m_flow")
    assert not m_flow[1].fixed  # Variable!

    # Check: CAPEX = 0
    capex = pipe.get_capex(model)
    assert capex == 0.0

def test_pipe_brownfield_poor_condition():
    """Test bestehendes Rohr mit schlechtem Zustand"""
    config = {
        "name": "pipe_old",
        "existing": True,
        "DN_fixed": "DN150",
        "insulation_fixed": "standard",
        "condition": "poor",  # Schlechter Zustand
        # ... (rest of config)
    }

    model = pyo.ConcreteModel()
    model.T = pyo.RangeSet(1, 24)

    pipe = PipeBlock(config)
    pipe.attach(model, model.T, test_config, {})

    # Check: U-Wert erhöht (schlechtere Isolierung)
    U = getattr(model, "pipe_old_U")
    U_catalog = 0.4  # Standard U-Wert
    U_expected = U_catalog * 1.2  # 20% Erhöhung

    assert abs(pyo.value(U) - U_expected) < 0.01

def test_pipe_mixed_greenfield_brownfield():
    """Test gemischtes Szenario: Bestehende + neue Rohre"""
    # Topologie: existing_pipe → new_pipe

    # 1. Bestehendes Rohr
    config_existing = {
        "name": "pipe_existing",
        "existing": True,
        "DN_fixed": "DN150",
        # ...
    }

    # 2. Neues Rohr (Investment)
    config_new = {
        "name": "pipe_new",
        "existing": False,
        "invest": True,
        "DN_options": ["DN100", "DN150", "DN200"],
        # ...
    }

    model = pyo.ConcreteModel()
    model.T = pyo.RangeSet(1, 24)

    pipe_existing = PipeBlock(config_existing)
    pipe_new = PipeBlock(config_new)

    pipe_existing.attach(model, model.T, test_config, {})
    pipe_new.attach(model, model.T, test_config, {})

    # ... (Setze Randbedingungen, löse)

    solver = pyo.SolverFactory('gurobi')
    results = solver.solve(model)

    # Check: Bestehendes Rohr hat D=0.15 (fix)
    assert pyo.value(getattr(model, "pipe_existing_D")) == 0.15

    # Check: Neues Rohr hat optimiertes D
    D_new = pyo.value(getattr(model, "pipe_new_D"))
    assert D_new in [0.1, 0.15, 0.2]  # DN100, DN150, DN200

    # Check: CAPEX nur für neues Rohr
    capex_existing = pipe_existing.get_capex(model)
    capex_new = pipe_new.get_capex(model)

    assert capex_existing == 0.0
    assert capex_new > 0.0

def test_brownfield_validation():
    """Test Validierung: existing UND invest nicht erlaubt"""
    config_invalid = {
        "name": "pipe_invalid",
        "existing": True,   # ❌
        "invest": True,     # ❌ Konflikt!
        # ...
    }

    with pytest.raises(ValueError, match="existing=True und invest=True"):
        pipe = PipeBlock(config_invalid)
        # Validierung sollte fehlschlagen

def test_brownfield_missing_DN_fixed():
    """Test Validierung: existing=True benötigt DN_fixed"""
    config_invalid = {
        "name": "pipe_invalid",
        "existing": True,
        "DN_fixed": None,  # ❌ Fehlt!
        # ...
    }

    model = pyo.ConcreteModel()
    model.T = pyo.RangeSet(1, 24)

    pipe = PipeBlock(config_invalid)

    with pytest.raises(ValueError, match="benötigt DN_fixed"):
        pipe.attach(model, model.T, test_config, {})
```

**Aufwand:** +1 Tag (zusätzlich zu Basis-Pipe-Implementierung)

---

### 3.2 Task 2.2 - 2.6: Weitere Komponenten

**Analog zu Pipe implementieren:**

1. **PumpBlock** (`pump.py`) - ~350 Zeilen
2. **ThermalNodeBlock** (`thermal_node.py`) - ~250 Zeilen
3. **HeatExchangerBlock** (`heat_exchanger.py`) - ~300 Zeilen
4. **PointLoadBlock** (`point_load.py`) - ~200 Zeilen
5. **DistributedLoadBlock** (`distributed_load.py`) - ~350 Zeilen

**Jede Komponente folgt dem gleichen Muster:**
- Config-Dataclass
- `@register_component` Decorator
- `attach()` Methode mit Variablen + Constraints
- Linearisierungs-Hilfsmethoden
- `get_results()`
- Unit-Tests

**Zeitplanung:**
- Pipe: 5 Tage (komplex)
- Pump: 4 Tage
- ThermalNode: 3 Tage
- HeatExchanger: 4 Tage
- PointLoad: 2 Tage
- DistributedLoad: 4 Tage

= **22 Tage ≈ 3 Wochen** (mit Puffer)

---

## 4. Phase 3: Erweiterte Features

**Dauer:** 1-2 Wochen (optional)

### Task 3.1: Dampf-Komponenten

**Falls erforderlich, später implementieren:**
- `steam_turbine.py`
- `steam_generator.py`
- `condenser.py`

### Task 3.2: Multi-Period Investment

**Erweitere Investment-Logik:**
- Investitionen in verschiedenen Jahren
- NPV-Berechnung
- Discount-Faktoren

---

## 5. Phase 4: Kältenetze & Wärmerückgewinnung

**Dauer:** 3 Wochen
**Ziel:** Integration von Cooling Networks und Heat Recovery

### Task 4.1: Chiller Component

**`energis/models/blocks/cooling/chiller.py`** (~350 Zeilen)

**Features:**
- Kompressionskältemaschine (elektrisch)
- Absorptionskältemaschine (thermisch)
- COP temperaturabhängig: COP = f(T_evap, T_cond)
- 2D-PWL für COP-Kurve
- Investment in Größe
- Anbindung an Kältenetz + Kondensator (Rückkühlung)

**Variablen:**
```python
Q_cold[t]              # Kälteleistung [MW]
Q_cond[t]              # Kondensatorwärme [MW]
P_el[t]                # Elektrische Leistung [MW]
COP[t]                 # Coefficient of Performance
T_evap[t]              # Verdampfertemperatur [°C]
T_cond[t]              # Kondensatortemperatur [°C]
```

**Test:** `tests/unit/cooling/test_chiller.py`

---

### Task 4.2: Cooling Tower Component

**`energis/models/blocks/cooling/cooling_tower.py`** (~250 Zeilen)

**Features:**
- Wet vs. Dry Cooling
- Kühlgrenze T_wetbulb vs. T_ambient
- Lüfterleistung P_fan = α · Q_reject
- Vereinfachung: Konstante T_out (Design-Temperatur)

**Variablen:**
```python
Q_reject[t]            # Abgeführte Wärme [MW]
m_water[t]             # Wassermassenstrom [kg/s]
T_water_in[t]          # Eintrittstemperatur [°C]
T_water_out[t]         # Austrittstemperatur [°C]
P_fan[t]               # Lüfterleistung [MW]
```

**Test:** `tests/unit/cooling/test_cooling_tower.py`

---

### Task 4.3: Free Cooling Component

**`energis/models/blocks/cooling/free_cooling.py`** (~300 Zeilen)

**Features:**
- Grundwasser, Fluss/See, Außenluft als Quelle
- Binary is_active[t] (abhängig von T_source)
- Wärmeübertrager mit ε_HEX
- Pinch-Point Constraint
- Minimale Betriebskosten (nur Pumpen)

**Variablen:**
```python
Q_cool[t]              # Bereitgestellte Kälte [MW]
is_active[t]           # Binary: Verfügbar?
T_source_in[t]         # Temperatur Quelle [°C] (exogen)
m_source[t]            # Massenstrom Quelle [kg/s]
P_pump[t]              # Pumpenleistung [MW]
```

**Test:** `tests/unit/cooling/test_free_cooling.py`

---

### Task 4.4: Heat Recovery Unit

**`energis/models/blocks/heat_recovery/heat_recovery_unit.py`** (~400 Zeilen)

**Features:**
- Abwärmequellen: Industrie, Rechenzentren, Abwasser
- Fall A: Direkte Einspeisung (T_waste hoch)
- Fall B: Mit Wärmepumpe (T_waste niedrig)
- Binary use_heatpump[t]
- COP-Berechnung für Wärmepumpe

**Variablen:**
```python
Q_waste_available[t]   # Verfügbare Abwärme [MW] (exogen)
Q_recovered[t]         # Rückgewonnene Wärme [MW]
T_waste_in[t]          # Temperatur Abwärme [°C]
use_heatpump[t]        # Binary: WP nutzen?
COP_hp[t]              # COP Wärmepumpe
P_el_hp[t]             # Elektrische Leistung WP [MW]
```

**Test:** `tests/unit/heat_recovery/test_heat_recovery_unit.py`

---

### Task 4.5: Erweiterte HeatPump-Modellierung

**Erweitere `energis/models/blocks/heat_pump.py`** (+~100 Zeilen)

**Neue Features:**
- Anbindung an Kältenetz (`cold_network` Parameter)
- Bidirektionaler Betrieb (optional): mode[t] ∈ {0, 1}
- Heizmodus: Kälte-Quelle → Wärme-Senke
- Kühlmodus: Wärme-Quelle → Kälte-Senke

**Config-Erweiterung:**
```python
@dataclass
class HeatPumpConfig:
    # ... (existing)
    cold_network: Optional[str] = None
    supports_cooling: bool = False
```

**Test:** `tests/unit/test_heat_pump_extended.py`

---

### Task 4.6: Multi-Network Manager Update

**Erweitere `energis/models/network/multi_network.py`**

**Änderungen:**
```python
@dataclass
class NetworkDefinition:
    # ... (existing)
    network_type: str  # "heating" | "cooling"  # NEU
```

**Neue Methoden:**
```python
def get_cooling_networks(self) -> List[str]:
    """Gibt alle Kältenetze zurück"""

def get_heating_networks(self) -> List[str]:
    """Gibt alle Wärmenetze zurück"""
```

---

### Task 4.7: Kataloge & Konfiguration

**Neue Dateien:**

**`config/catalogs/chillers.yaml`:**
```yaml
chiller_catalog:
  compression_small:
    Q_cold_nominal: 1  # MW
    COP_nominal: 5
    COP_curve:
      T_evap: [4, 6, 8, 10]
      T_cond: [25, 30, 35, 40]
      COP_values: [[5.5, 5.0, 4.5, 4.0], ...]
    cost_fixed: 200000  # EUR
    cost_variable: 150000  # EUR/MW
```

**`config/networks/heating_cooling_system.yaml`:**
```yaml
networks:
  - id: "heat_net"
    network_type: "heating"
    T_supply: 55
    T_return: 35

  - id: "cold_net"
    network_type: "cooling"
    T_supply: 8
    T_return: 12
```

---

### Zeitplan Phase 4

| **Task** | **Aufwand** | **Kumulativ** |
|----------|-------------|---------------|
| 4.1 Chiller | 4 Tage | 4 Tage |
| 4.2 Cooling Tower | 2 Tage | 6 Tage |
| 4.3 Free Cooling | 3 Tage | 9 Tage |
| 4.4 Heat Recovery | 4 Tage | 13 Tage |
| 4.5 HeatPump Extend | 2 Tage | 15 Tage |
| 4.6 Multi-Network | 1 Tag | 16 Tage |
| 4.7 Kataloge | 1 Tag | 17 Tage |
| Tests | 2 Tage | 19 Tage |
| **SUMME** | **19 Tage** | **≈ 3 Wochen** |

---

## 6. Phase 5: Saisonale Wärmespeicher

**Dauer:** 2 Wochen
**Ziel:** Integration saisonaler Wärmespeicher (PTES/ATES)

### Task 5.1: PTES Component

**`energis/models/blocks/seasonal_storage/ptes.py`** (~400 Zeilen)

**Features:**
- Erdbeckenspeicher (Pit Thermal Energy Storage)
- Monatliche Zeitauflösung (statt stündlich)
- Energiebilanz mit Wärmeverlusten
- Investment in Speichergröße (diskret: 50k, 100k, 200k m³)
- Kopplung mit stündlichem Netzwerkmodell

**Variablen:**
```python
# Monatliche Zeitschritte
M = pyo.RangeSet(1, 12)  # Monate

SOC[month]               # State of Charge [m³]
E_stored[month]          # Energieinhalt [MWh]
T_storage[month]         # Durchschnittstemperatur [°C]
Q_charge[month]          # Ladeleistung [MWh/Monat]
Q_discharge[month]       # Entladeleistung [MWh/Monat]
Q_loss[month]            # Wärmeverlust [MWh/Monat]

# Investment
build_ptes               # Binary: Baue PTES?
V_max                    # Maximales Volumen [m³] - diskret
```

**Constraints:**
```python
# 1. Energiebilanz (monatlich)
E_stored[month+1] = E_stored[month] + Q_charge[month]
                    - Q_discharge[month] - Q_loss[month]

# 2. Zyklische Randbedingung
E_stored[1] = E_stored[12]

# 3. Wärmeverluste (temperaturabhängig)
Q_loss[month] = U_ptes · A_surface · (T_storage[month] - T_soil[month])
                · hours_per_month / 1000

# 4. Kapazitätsgrenzen
0 ≤ SOC[month] ≤ V_max
T_min ≤ T_storage[month] ≤ T_max

# 5. Investment-Logik
V_max ∈ {0, 50000, 100000, 200000}  # m³
SOC[month] ≤ V_max · build_ptes
```

**Linearisierung:**
```python
# Bilinearer Term: SOC · T_storage
# → McCormick Envelopes

# ODER: PWL-Vereinfachung
# T_storage ≈ f(SOC/V_max)
T_storage[month] = PWL_SOS2(SOC[month]/V_max, SOC_frac_pts, T_storage_pts)
```

**Test:** `tests/unit/seasonal_storage/test_ptes.py`
```python
def test_ptes_seasonal_cycle():
    """Test saisonaler Zyklus: Sommer laden, Winter entladen"""
    # Sommer (Monat 5-9): Q_charge > 0
    # Winter (Monat 11-2): Q_discharge > 0
    # Validiere: SOC erreicht Maximum im September
    # Validiere: SOC erreicht Minimum im Februar

def test_ptes_investment():
    """Test Investment-Optimierung"""
    # Gegeben: Hoher solarer Überschuss im Sommer
    # Erwarte: Optimierer wählt große PTES (100k-200k m³)

def test_ptes_heat_loss():
    """Test Wärmeverluste"""
    # Validiere: Q_loss höher bei hoher T_storage
    # Validiere: Q_loss höher im Winter (niedriger T_soil)
```

---

### Task 5.2: ATES Component

**`energis/models/blocks/seasonal_storage/ates.py`** (~450 Zeilen)

**Features:**
- Aquifer Thermal Energy Storage
- Warm- und Kaltbohrloch
- Monatliche Zeitauflösung
- Recovery Efficiency (geologieabhängig)
- Investment in Anzahl Bohrlochpaare

**Variablen:**
```python
T_warm_well[month]       # Temperatur warmes Bohrloch [°C]
T_cold_well[month]       # Temperatur kaltes Bohrloch [°C]
E_stored_warm[month]     # Energie im warmen Bereich [MWh]
Q_charge[month]          # Wärme ins warme Bohrloch [MWh/Monat]
Q_discharge[month]       # Wärme aus warmem Bohrloch [MWh/Monat]

# Investment
build_ates               # Binary: Baue ATES?
num_well_pairs           # Anzahl Bohrlochpaare [1-5]
```

**Constraints:**
```python
# 1. Energiebilanz Warm-Seite
E_stored_warm[month+1] = E_stored_warm[month] + Q_charge[month]
                         - Q_discharge[month] / η_recovery
                         - Q_loss_underground[month]

# 2. Temperatur-Grenzen
T_warm_min ≤ T_warm_well[month] ≤ T_warm_max
T_warm_well[month] - T_cold_well[month] ≥ ΔT_min  # z.B. 5K

# 3. Kapazität abhängig von Anzahl Bohrungen
E_max = num_well_pairs · E_per_well_pair

# 4. Investment
num_well_pairs ∈ {1, 2, 3, 4, 5}
```

**Test:** `tests/unit/seasonal_storage/test_ates.py`

---

### Task 5.3: Monatliche Aggregation (Hybrid-Modell)

**`energis/models/seasonal_storage/time_aggregation.py`** (~150 Zeilen)

**Problem:** Netzwerkmodell ist stündlich (8760 h), aber saisonale Speicher monatlich (12 Monate).

**Lösung: Hybrid-Modell**

```python
# Stündliche Variablen (Netzwerk)
T_hourly = pyo.RangeSet(1, 8760)  # Stunden

# Monatliche Variablen (Saisonalspeicher)
M = pyo.RangeSet(1, 12)  # Monate

# Mapping hour → month
def month_of_hour(h):
    """Gibt Monat für Stunde h zurück"""
    cumulative_hours = [0, 744, 1416, 2160, 2880, 3624, 4344, 5088,
                        5832, 6552, 7296, 8016, 8760]
    for m in range(1, 13):
        if cumulative_hours[m-1] < h <= cumulative_hours[m]:
            return m
    return 12

# Kopplung: Monatliche Aggregation
def monthly_aggregation_constraint(model, month):
    """Summiere stündliche Flows zu monatlichem Flow"""
    hours_in_month = [h for h in T_hourly if month_of_hour(h) == month]

    return (model.Q_charge_monthly[month] ==
            sum(model.Q_to_storage_hourly[h] for h in hours_in_month))

model.charge_aggregation = pyo.Constraint(M, rule=monthly_aggregation_constraint)
```

**Alternative: Representative Days**
```python
# Statt 8760h: 12 Monate × 3 repräsentative Tage × 24h = 864h
# → Faktor 10 schneller, aber weniger genau

def select_representative_days(hourly_data, month, num_days=3):
    """
    Wähle repräsentative Tage für Monat

    Kriterien:
    - 1 Tag mit max. Solarproduktion
    - 1 Tag mit max. Nachfrage
    - 1 Durchschnittstag
    """
    # ...
```

**Test:** `tests/unit/seasonal_storage/test_time_aggregation.py`

---

### Task 5.4: Integration mit System Builder

**Erweitere `energis/models/system_builder.py`:**

```python
def build_seasonal_storage_components(
    model: pyo.ConcreteModel,
    seasonal_storage_config: Dict,
    hourly_time_set: pyo.Set,
    monthly_time_set: pyo.Set,
    buses: Dict
) -> None:
    """
    Integriere saisonale Speicher in System Builder
    """

    for storage_cfg in seasonal_storage_config:
        if storage_cfg["type"] == "PTES":
            ptes_component = PTESBlock(storage_cfg)
            ptes_component.attach(
                model,
                hourly_time_set,
                monthly_time_set,
                config,
                buses
            )

        elif storage_cfg["type"] == "ATES":
            ates_component = ATESBlock(storage_cfg)
            ates_component.attach(
                model,
                hourly_time_set,
                monthly_time_set,
                config,
                buses
            )
```

---

### Task 5.5: Kataloge & Konfiguration

**Neue Dateien:**

**`config/catalogs/seasonal_storage.yaml`:**
```yaml
ptes_catalog:
  standard_50k:
    V_nominal: 50000  # m³
    T_min: 40
    T_max: 95
    U_value: 0.3  # W/(m²·K)
    depth: 10  # m
    cost_fixed: 500000  # EUR
    cost_per_m3: 75  # EUR/m³
    cost_lining_per_m2: 50  # EUR/m²

  standard_100k:
    V_nominal: 100000
    T_min: 40
    T_max: 95
    U_value: 0.25  # Bessere Isolierung bei größerem Volumen
    depth: 12
    cost_fixed: 750000
    cost_per_m3: 65  # Economies of scale
    cost_lining_per_m2: 45

  standard_200k:
    V_nominal: 200000
    T_min: 40
    T_max: 95
    U_value: 0.2
    depth: 15
    cost_fixed: 1000000
    cost_per_m3: 55
    cost_lining_per_m2: 40

ates_catalog:
  shallow_aquifer:
    depth_range: [50, 150]  # m
    aquifer_thickness: 50  # m
    porosity: 0.3
    η_recovery: 0.7
    cost_per_borehole: 150000  # EUR
    cost_pumps: 50000  # EUR
    cost_heat_exchanger: 30000  # EUR

  deep_aquifer:
    depth_range: [150, 300]
    aquifer_thickness: 80
    porosity: 0.35
    η_recovery: 0.75  # Bessere Isolation
    cost_per_borehole: 300000
    cost_pumps: 75000
    cost_heat_exchanger: 50000
```

**`config/networks/solar_district_heating_with_ptes.yaml`:**
```yaml
networks:
  - id: "dh_ht"
    network_type: "heating"
    T_supply: 90
    T_return: 50

components:
  solar_thermal:
    - id: "solar_1"
      type: "SolarThermalCollector"
      network: "dh_ht"
      A_collector: 10000  # m² (investment variable)

  seasonal_storage:
    - id: "ptes_solar_1"
      type: "PTES"
      network: "dh_ht"
      invest: true
      V_options: [50000, 100000, 200000]  # m³
      catalog: "standard_100k"

  backup:
    - id: "gas_boiler"
      type: "Boiler"
      network: "dh_ht"
      Q_max: 20  # MW
```

---

### Zeitplan Phase 5

| **Task** | **Aufwand** | **Kumulativ** |
|----------|-------------|---------------|
| 5.1 PTES Component | 4 Tage | 4 Tage |
| 5.2 ATES Component | 5 Tage | 9 Tage |
| 5.3 Monatliche Aggregation | 2 Tage | 11 Tage |
| 5.4 System Builder Integration | 1 Tag | 12 Tage |
| 5.5 Kataloge | 1 Tag | 13 Tage |
| Tests | 2 Tage | 15 Tage |
| **SUMME** | **15 Tage** | **≈ 2 Wochen** |

---

## 7. Phase 6: Integration & Testing

**Dauer:** 1 Woche

### Task 6.1: System Builder Integration

**Erweitere** `energis/models/system_builder.py`:

```python
def build_network_model(
    model: pyo.ConcreteModel,
    topology: NetworkTopology,
    multi_net: MultiNetworkManager,
    config: Dict
) -> None:
    """
    Integriere Netzwerk-Komponenten in System Builder
    """
    # Erstelle alle Rohre
    for pipe_id, pipe in topology.pipes.items():
        pipe_component = PipeBlock(pipe_cfg)
        pipe_component.attach(model, model.T, config, buses)

    # Erstelle alle Knoten
    for node_id, node in topology.nodes.items():
        node_component = ThermalNodeBlock(node_cfg)
        node_component.attach(model, model.T, config, buses)

    # ... (Pumpen, Verbraucher, etc.)
```

### Task 6.2: Integrationstests

**`tests/integration/test_simple_network.py`:**
```python
def test_two_node_network():
    """
    Test einfachstes Netz:
    Producer ──pipe──► Consumer
            ◄──pipe──
    """
    # Setup
    topology = NetworkTopology.from_yaml("tests/fixtures/simple_network.yaml")

    # Build model
    model = build_energis_model(topology, config)

    # Solve
    solver = pyo.SolverFactory('gurobi')
    results = solver.solve(model)

    # Validate
    assert results.solver.termination_condition == pyo.TerminationCondition.optimal

    # Check mass balance
    m_supply = pyo.value(model.pipe_supply_m_flow[1])
    m_return = pyo.value(model.pipe_return_m_flow[1])
    assert abs(m_supply - m_return) < 1e-6

    # Check energy balance
    Q_produced = pyo.value(model.producer_Q[1])
    Q_consumed = pyo.value(model.consumer_Q[1])
    Q_loss_supply = pyo.value(model.pipe_supply_Q_loss[1])
    Q_loss_return = pyo.value(model.pipe_return_Q_loss[1])

    assert abs(Q_produced - Q_consumed - Q_loss_supply - Q_loss_return) < 1e-3
```

**`tests/integration/test_multi_network.py`:**
```python
def test_two_network_cascade():
    """
    Test Kaskadierung:
    HT-Netz (90°C) ─HEX─► NT-Netz (55°C)
    """
    # ...
```

### Task 6.3: Validierung gegen TESpy (optional)

**`tests/integration/test_vs_tespy.py`:**
```python
def test_energis_vs_tespy_simple_network():
    """
    Vergleiche EnerGIS (MILP) mit TESpy (nichtlinear)
    für einfaches Netz
    """
    # 1. Löse mit EnerGIS
    energis_solution = solve_energis(config)

    # 2. Konvertiere zu TESpy
    tespy_network = convert_energis_to_tespy(energis_solution)

    # 3. Simuliere mit TESpy
    tespy_solution = tespy_network.solve('design')

    # 4. Vergleiche
    for pipe_id in pipes:
        m_energis = energis_solution[f"{pipe_id}_m_flow"]
        m_tespy = tespy_solution[pipe_id]["m"]

        rel_error = abs(m_energis - m_tespy) / m_tespy
        assert rel_error < 0.05  # < 5%
```

---

## 8. Phase 7: Dokumentation & Beispiele

**Dauer:** 3-4 Tage

### Task 7.1: User Guide

**`docs/user_guide_thermal_networks.md`:**
```markdown
# User Guide: Thermische Netzwerk-Modellierung

## Quickstart

### 1. Definiere Netzwerk-Topologie

...yaml example...

### 2. Konfiguriere Komponenten

...

### 3. Löse Optimierung

...

## Beispiele

### Beispiel 1: Einfaches Fernwärmenetz

...
```

### Task 7.2: Jupyter Notebooks

**`examples/notebooks/01_simple_district_heating.ipynb`:**
- Schritt-für-Schritt Tutorial
- Visualisierungen
- Ergebnisanalyse

**`examples/notebooks/02_multi_temperature_cascade.ipynb`:**
- Multi-Netz-Beispiel
- HT → MT → NT Kaskadierung

**`examples/notebooks/03_investment_optimization.ipynb`:**
- DN-Optimierung
- Kostenanalyse
- Sensitivitätsanalyse

### Task 7.3: API-Dokumentation

**Generiere mit Sphinx:**
```bash
cd docs
sphinx-apidoc -o source ../energis/models/blocks/network
make html
```

---

## 9. Code-Templates

### 9.1 Component Template

**Für neue Komponenten:**
```python
# energis/models/blocks/network/new_component.py

from energis.models.component import BaseComponent, register_component
from dataclasses import dataclass
import pyomo.environ as pyo

@dataclass
class NewComponentConfig:
    """Konfiguration für NewComponent"""
    name: str
    # ... weitere Parameter

@register_component("new_component", category="network")
class NewComponentBlock(BaseComponent):
    """
    Beschreibung der Komponente

    Variablen:
        - var1: Beschreibung
        - var2: Beschreibung

    Constraints:
        - constraint1: Beschreibung
        - constraint2: Beschreibung
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.cfg = NewComponentConfig(**config)

    def attach(self, model, time_set, config, buses):
        """Erstelle Variablen und Constraints"""
        name = self.cfg.name
        T = time_set

        # Variables
        model.add_component(f"{name}_var1", pyo.Var(T, ...))

        # Constraints
        def constraint1_rule(model, t):
            # ...
            return ...

        model.add_component(f"{name}_constraint1", pyo.Constraint(T, rule=constraint1_rule))

        # Register flows
        # self.add_flow(...)

        return {...}

    def get_results(self, model, time_set):
        """Extrahiere Ergebnisse"""
        name = self.cfg.name
        return {
            "var1": [pyo.value(getattr(model, f"{name}_var1")[t]) for t in time_set],
        }
```

### 9.2 Test Template

**Für Component-Tests:**
```python
# tests/unit/network/test_new_component.py

import pytest
import pyomo.environ as pyo
from energis.models.blocks.network.new_component import NewComponentBlock

@pytest.fixture
def model():
    """Erstelle Test-Modell"""
    m = pyo.ConcreteModel()
    m.T = pyo.RangeSet(1, 24)
    return m

def test_new_component_basic(model):
    """Test Basisfunktionalität"""
    config = {
        "name": "test_comp",
        # ...
    }

    component = NewComponentBlock(config)
    component.attach(model, model.T, {}, {})

    # Setze Randbedingungen
    # ...

    # Löse
    solver = pyo.SolverFactory('gurobi')
    results = solver.solve(model)

    # Assertions
    assert results.solver.termination_condition == pyo.TerminationCondition.optimal
    # ...

def test_new_component_edge_cases(model):
    """Test Grenzfälle"""
    # ...
```

---

## 10. Testing-Strategie

### 10.1 Test-Pyramide

```
                      ╱╲
                     ╱  ╲
                    ╱ E2E╲         1-2 Tests
                   ╱______╲        - Vollständige Workflows
                  ╱        ╲
                 ╱Integration╲     5-10 Tests
                ╱____________╲     - Multi-Komponenten
               ╱              ╲
              ╱  Unit Tests    ╲   30-50 Tests
             ╱__________________╲  - Einzelne Komponenten
```

### 10.2 Coverage-Ziel

**Minimum: 80% Code Coverage**

```bash
pytest --cov=energis/models/blocks/network --cov-report=html
```

### 10.3 Continuous Integration

**GitHub Actions:** `.github/workflows/test_network.yml`
```yaml
name: Network Components Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      run: |
        pytest tests/unit/network/ -v --cov

    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## 11. Migration von bestehenden Systemen

### 11.1 Für Nutzer des v1.0 Frameworks

**Migrations-Guide:**

**Alt (v1.0):**
```yaml
# Nur abstrakte Buses, keine Rohre
system:
  buses:
    - heat_bus
```

**Neu (v2.0 + Network):**
```yaml
# Explizite Topologie
topology:
  nodes:
    - id: "chp_1"
      type: "producer"
      coordinates: {x: 0, y: 0}

  pipes:
    - id: "pipe_1"
      from: "chp_1"
      to: "consumer_1"
```

**Migration-Script:** `scripts/migrate_to_network.py`
```python
def migrate_config_v1_to_v2(old_config_path: str, output_path: str):
    """
    Konvertiere alte Konfiguration zu neuer mit Netzwerk

    Erstellt Standard-Topologie:
    - Ein Producer-Node
    - Ein Consumer-Node
    - Direkte Verbindung (Supply + Return)
    """
    # ...
```

---

## 12. Zeitplan & Meilensteine

### 12.1 Gantt-Chart

```
Woche   Aufgaben
───────────────────────────────────────────────────────────
1       [████████████] Phase 1: Infrastruktur
2       [████████    ] Phase 2.1: Pipe
3       [    ████████] Phase 2.2-3: Pump, Node
4       [    ████████] Phase 2.4-5: HEX, Loads
5       [████        ] Phase 2.6: Distributed Load
6       [████████    ] Phase 4.1-2: Chiller, Cooling Tower
7       [    ████████] Phase 4.3-4: Free Cooling, Heat Recovery
8       [████        ] Phase 4.5-7: HeatPump, Kataloge
9       [████████    ] Phase 5.1-3: PTES, ATES, Aggregation
10      [    ████████] Phase 5.4-5: Integration, Kataloge
11      [    ████████] Phase 6: Integration & Tests
12      [████████    ] Phase 7: Dokumentation
```

### 12.2 Meilensteine

**M1 (Ende Woche 1):** Infrastruktur fertig
- ✓ PWL/McCormick Utilities
- ✓ Geographic/Topology Module
- ✓ Multi-Network Manager

**M2 (Ende Woche 3):** Pipe + Pump fertig
- ✓ PipeBlock implementiert & getestet
- ✓ PumpBlock implementiert & getestet

**M3 (Ende Woche 5):** Basis-Komponenten fertig
- ✓ 6 Basis-Komponenten implementiert (Pipe, Pump, Node, HEX, Loads)
- ✓ Unit-Tests 100%

**M4 (Ende Woche 8):** Cooling & Heat Recovery fertig
- ✓ 4 Cooling-Komponenten (Chiller, Cooling Tower, Free Cooling, Heat Recovery)
- ✓ HeatPump erweitert
- ✓ Multi-Network Update
- ✓ Kataloge

**M5 (Ende Woche 10):** Seasonal Storage fertig
- ✓ PTES Component implementiert & getestet
- ✓ ATES Component implementiert & getestet
- ✓ Monatliche Zeitauflösung (Hybrid-Modell)
- ✓ Aggregation stündlich → monatlich
- ✓ Kataloge für saisonale Speicher

**M6 (Ende Woche 11):** Integration fertig
- ✓ System Builder erweitert
- ✓ Integrationstests bestehen
- ✓ Optional: TESpy-Validierung

**M7 (Ende Woche 12):** Release-Ready
- ✓ Dokumentation vollständig
- ✓ Beispiel-Notebooks (Heating + Cooling + Seasonal Storage)
- ✓ User Guide

---

## 13. Risiken & Mitigation

| **Risiko** | **Wahrscheinlichkeit** | **Impact** | **Mitigation** |
|------------|------------------------|------------|----------------|
| Linearisierung zu ungenau | Mittel | Hoch | Frühe Validierung mit TESpy, mehr Stützstellen |
| Gurobi-Performance bei großen Netzen | Mittel | Mittel | Warm Start, Gap-Toleranz, Modell-Tuning |
| Komplexität McCormick-Bounds | Hoch | Mittel | Adaptive Bounds, gutes Debugging |
| Zeitüberschreitung | Mittel | Niedrig | 2 Wochen Puffer, Phase 3 optional |

---

## 14. Deliverables

**Code:**
- ✅ 6 Basis-Komponenten (Pipe, Pump, ThermalNode, HeatExchanger, PointLoad, DistributedLoad)
- ✅ 4 Cooling-Komponenten (Chiller, CoolingTower, FreeCooling, HeatRecoveryUnit)
- ✅ 2 Seasonal Storage-Komponenten (PTES, ATES)
- ✅ HeatPump erweitert (Kältenetz-Anbindung)
- ✅ 3 Linearisierungs-Module (PWL, McCormick, SteamTables)
- ✅ 3 Netzwerk-Management-Module (Topology, Geographic, MultiNetwork)
- ✅ 1 Time Aggregation-Modul (monatlich ↔ stündlich)
- ✅ System Builder erweitert
- ✅ ~75 Unit Tests
- ✅ ~20 Integrationstests

**Konfiguration:**
- ✅ 5 Technologie-Kataloge (pipes, pumps, insulation, chillers, seasonal_storage)
- ✅ 4 Beispiel-Netzwerk-Konfigurationen (heating, cooling, integrated, solar_with_ptes)
- ✅ Multi-Netz Definition Template (heating + cooling)

**Dokumentation:**
- ✅ Requirements-Dokument (FERTIG, mit Cooling + Seasonal Storage)
- ✅ Mathematisches Design-Dokument (FERTIG)
- ✅ Implementierungsplan (DIESES DOKUMENT)
- ✅ Cooling & Heat Recovery Extension Document (FERTIG)
- ✅ Future Extensions Document (FERTIG)
- ✅ User Guide
- ✅ 5 Tutorial-Notebooks (Heating, Cooling, Multi-Temperature, Investment, Seasonal Storage)
- ✅ API-Dokumentation (Sphinx)

**Tests & Validierung:**
- ✅ 80%+ Code Coverage
- ✅ CI/CD Pipeline
- ✅ TESpy-Vergleich (optional)

---

**Status:** Ready to implement
**Zeitrahmen:** 10-12 Wochen (inkl. Cooling, Heat Recovery & Seasonal Storage)
**Nächster Schritt:** Start Phase 1 - Task 1.1 (PWL Utilities)
