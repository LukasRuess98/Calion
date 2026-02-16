"""
Network topology configuration schemas.

Defines dataclasses for multi-node thermal network topology with physics modeling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class NetworkNode:
    """Network node (producer, consumer, or junction)."""

    id: str
    type: str  # producer, consumer, junction

    # Components attached to this node
    components: List[str] = field(default_factory=list)

    # Demand configuration (for consumer nodes)
    demand_column: Optional[str] = None
    peak_demand_mw: Optional[float] = None

    # Pressure configuration
    pressure_setpoint_bar: Optional[float] = None
    min_pressure_bar: Optional[float] = None
    max_pressure_bar: Optional[float] = None

    # Location (for visualization)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, node_id: str, data: Dict[str, Any]) -> NetworkNode:
        """Create from dictionary."""
        demand = data.get('demand', {})
        pressure = data.get('pressure', {})

        return cls(
            id=node_id,
            type=str(data.get('type', 'junction')),
            components=data.get('components', []),
            demand_column=demand.get('demand_column'),
            peak_demand_mw=float(demand['peak_demand_mw']) if 'peak_demand_mw' in demand else None,
            pressure_setpoint_bar=float(pressure['setpoint_bar']) if 'setpoint_bar' in pressure else None,
            min_pressure_bar=float(pressure['min_bar']) if 'min_bar' in pressure else None,
            max_pressure_bar=float(pressure['max_bar']) if 'max_bar' in pressure else None,
            latitude=float(data['latitude']) if 'latitude' in data else None,
            longitude=float(data['longitude']) if 'longitude' in data else None,
            metadata=data.get('metadata', {}),
        )


@dataclass
class PipeCapacity:
    """Existing or expansion pipe capacity."""

    installed: bool = False
    diameter_mm: Optional[float] = None
    commissioning_year: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PipeCapacity:
        """Create from dictionary."""
        return cls(
            installed=bool(data.get('installed', False)),
            diameter_mm=float(data['diameter_mm']) if 'diameter_mm' in data else None,
            commissioning_year=int(data['commissioning_year']) if 'commissioning_year' in data else None,
        )


@dataclass
class PipeExpansion:
    """Pipe expansion/investment potential."""

    enabled: bool = False
    diameter_options_mm: List[float] = field(default_factory=list)
    capex_eur_per_m: float = 0.0
    max_length_m: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PipeExpansion:
        """Create from dictionary."""
        return cls(
            enabled=bool(data.get('enabled', False)),
            diameter_options_mm=data.get('diameter_options_mm', []),
            capex_eur_per_m=float(data.get('capex_eur_per_m', 0.0)),
            max_length_m=float(data['max_length_m']) if 'max_length_m' in data else None,
        )


@dataclass
class Pipe:
    """Pipe connecting two nodes."""

    id: str
    from_node: str
    to_node: str

    # Geometry
    length_m: float
    diameter_mm: float

    # Technology reference
    insulation: str  # References tech_library/pipes.yaml

    # Existing/expansion
    existing: PipeCapacity
    expansion: PipeExpansion

    # Operational constraints
    max_flow_kg_per_s: Optional[float] = None
    max_velocity_m_per_s: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, pipe_id: str, data: Dict[str, Any]) -> Pipe:
        """Create from dictionary."""
        existing_data = data.get('existing', {})
        expansion_data = data.get('expansion', {})

        return cls(
            id=pipe_id,
            from_node=str(data['from_node']),
            to_node=str(data['to_node']),
            length_m=float(data['length_m']),
            diameter_mm=float(data['diameter_mm']),
            insulation=str(data.get('insulation', 'standard_insulated')),
            existing=PipeCapacity.from_dict(existing_data),
            expansion=PipeExpansion.from_dict(expansion_data),
            max_flow_kg_per_s=float(data['max_flow_kg_per_s']) if 'max_flow_kg_per_s' in data else None,
            max_velocity_m_per_s=float(data['max_velocity_m_per_s']) if 'max_velocity_m_per_s' in data else None,
            metadata=data.get('metadata', {}),
        )


@dataclass
class Pump:
    """Circulation pump."""

    id: str
    node: str  # Node where pump is located

    # Pump characteristics
    rated_pressure_bar: float
    rated_flow_m3_per_h: float
    efficiency: float = 0.75

    # Technology reference
    technology: Optional[str] = None

    # Control
    control_mode: str = "constant_pressure"  # constant_pressure, constant_flow, variable

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, pump_id: str, data: Dict[str, Any]) -> Pump:
        """Create from dictionary."""
        # Handle both YAML naming conventions
        pressure = data.get('rated_pressure_bar') or data.get('rated_pressure_rise_bar')
        flow = data.get('rated_flow_m3_per_h') or data.get('rated_flow_m3_h')

        if pressure is None:
            raise ValueError(f"Pump {pump_id} missing rated pressure (rated_pressure_bar or rated_pressure_rise_bar)")
        if flow is None:
            raise ValueError(f"Pump {pump_id} missing rated flow (rated_flow_m3_per_h or rated_flow_m3_h)")

        # Efficiency can be a float or a dict with design_point
        efficiency_data = data.get('efficiency', 0.75)
        if isinstance(efficiency_data, dict):
            efficiency = float(efficiency_data.get('design_point', 0.75))
        else:
            efficiency = float(efficiency_data)

        return cls(
            id=pump_id,
            node=str(data['node']),
            rated_pressure_bar=float(pressure),
            rated_flow_m3_per_h=float(flow),
            efficiency=efficiency,
            technology=data.get('technology'),
            control_mode=str(data.get('control_mode', 'constant_pressure')),
            metadata=data.get('metadata', {}),
        )


@dataclass
class HeatingCurve:
    """Heating curve configuration."""

    enabled: bool = False
    outdoor_temp_column: Optional[str] = None
    supply_temp_at_minus20c: Optional[float] = None
    supply_temp_at_plus20c: Optional[float] = None
    curve_exponent: float = 1.3

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HeatingCurve:
        """Create from dictionary."""
        return cls(
            enabled=bool(data.get('enabled', False)),
            outdoor_temp_column=data.get('outdoor_temp_column'),
            supply_temp_at_minus20c=float(data['supply_temp_at_minus20c']) if 'supply_temp_at_minus20c' in data else None,
            supply_temp_at_plus20c=float(data['supply_temp_at_plus20c']) if 'supply_temp_at_plus20c' in data else None,
            curve_exponent=float(data.get('curve_exponent', 1.3)),
        )


@dataclass
class ThermalNetwork:
    """Thermal network configuration."""

    id: str
    description: str

    # Temperature configuration
    supply_temp_min_c: float
    supply_temp_max_c: float
    return_temp_min_c: float
    return_temp_max_c: float

    # Heating curve (optional)
    heating_curve: HeatingCurve

    # Topology
    nodes: Dict[str, NetworkNode]
    pipes: Dict[str, Pipe]
    pumps: Dict[str, Pump]

    # Fluid properties
    fluid: str = "water"  # References tech_library/fluids.yaml

    # Physics modeling
    model_pressure_drop: bool = True
    model_temperature_loss: bool = True
    model_time_delay: bool = False  # Computationally expensive

    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, network_id: str, data: Dict[str, Any]) -> ThermalNetwork:
        """Create from dictionary."""
        temps = data.get('temperatures', {})
        supply_bounds = temps.get('supply_bounds_c', [90, 130])
        return_bounds = temps.get('return_bounds_c', [40, 70])

        heating_curve_data = data.get('heating_curve', {})
        heating_curve = HeatingCurve.from_dict(heating_curve_data)

        nodes_data = data.get('nodes', {})
        nodes = {nid: NetworkNode.from_dict(nid, ndata) for nid, ndata in nodes_data.items()}

        pipes_data = data.get('pipes', {})
        pipes = {pid: Pipe.from_dict(pid, pdata) for pid, pdata in pipes_data.items()}

        # Pumps are optional
        pumps_data = data.get('pumps', {})
        pumps = {}
        if pumps_data:
            pumps = {pumpid: Pump.from_dict(pumpid, pumpdata) for pumpid, pumpdata in pumps_data.items()}

        physics = data.get('physics', {})

        return cls(
            id=network_id,
            description=str(data.get('description', '')),
            supply_temp_min_c=float(supply_bounds[0]),
            supply_temp_max_c=float(supply_bounds[1]),
            return_temp_min_c=float(return_bounds[0]),
            return_temp_max_c=float(return_bounds[1]),
            heating_curve=heating_curve,
            nodes=nodes,
            pipes=pipes,
            pumps=pumps,
            fluid=str(data.get('fluid', 'water')),
            model_pressure_drop=bool(physics.get('model_pressure_drop', True)),
            model_temperature_loss=bool(physics.get('model_temperature_loss', True)),
            model_time_delay=bool(physics.get('model_time_delay', False)),
            metadata=data.get('metadata', {}),
        )


@dataclass
class NetworkTopology:
    """Complete network topology for the system."""

    networks: Dict[str, ThermalNetwork]

    # Inter-network connections (e.g., heat pumps between networks)
    inter_network_connections: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NetworkTopology:
        """Create from dictionary."""
        networks_data = data.get('networks', {})
        networks = {nid: ThermalNetwork.from_dict(nid, ndata) for nid, ndata in networks_data.items()}

        return cls(
            networks=networks,
            inter_network_connections=data.get('inter_network_connections', []),
        )
