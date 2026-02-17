"""
Network Manager for Thermal District Heating Networks
======================================================

This module coordinates pipe and node components for district heating network
optimization, managing both greenfield (new network design) and brownfield
(existing network optimization) modes.

Key Concepts:
-------------
1. **Brownfield Mode** (default):
   - Network topology is fixed (no pipe investment)
   - Temperatures are fixed at design values
   - Heat losses calculated using physics: Q_loss = U × L × ΔT
   - Simplified linear constraints for fast solving

2. **Greenfield Mode** (advanced):
   - Pipe diameters can be optimized
   - Requires nonlinear solver (Gurobi, CPLEX)
   - Full hydraulic constraints (flow, pressure, temperature)

Network Components:
-------------------
- **Nodes**: Plants (heat sources), Consumers (heat sinks), Junctions
- **Pipes**: Supply and return pipes connecting nodes, characterized by:
  - length_m: Pipe length [m]
  - diameter_mm: Pipe diameter [mm]
  - u_value_w_per_m_k: Heat loss coefficient [W/(m·K)]

Heat Loss Calculation (Brownfield):
-----------------------------------
Physical heat loss per pipe (constant, independent of flow):

    Q_loss = U × L × (T_fluid - T_ground) / 1e6  [MW]

where:
    U = Heat transfer coefficient [W/(m·K)]
    L = Pipe length [m]
    T_fluid = Fluid temperature [°C]
    T_ground = Ground temperature [°C]

Configuration (brownfield.yaml):
--------------------------------
```yaml
parameters:
  supply_temp_nominal_c: 120    # Supply temperature [°C]
  return_temp_nominal_c: 55     # Return temperature [°C]
  ground_temp_default_c: 10     # Ground temperature [°C]

pipes:
  - id: main_pipe
    from_node: plant
    to_node: consumer
    length_m: 1000
    u_value_supply_w_per_m_k: 0.28
    u_value_return_w_per_m_k: 0.30
```

Usage:
------
    >>> from energis.models.network_manager import NetworkManager
    >>> nm = NetworkManager(config, config_dir=Path('.'))
    >>> nm.attach_to_model(model, config, time_set)
    >>> results = nm.get_results(model, config, time_set)

Author: EnerGIS Development Team
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

from .blocks.pipe_pair import PipePairBlock
from .blocks.thermal_node import ThermalNodeBlock
from .network_physics import (
    heat_kw_to_mdot_kg_s,
    mdot_to_velocity_m_s,
    pipe_total_heat_loss_mw,
    pipe_temperature_drop_c,
    calculate_pipe_temp_drops,
    calculate_supply_temperature,
    calculate_supply_temperature_series,
    get_heating_curve_parameters,
)
from ..utils.config_utils import resolve_heating_curve_profile

logger = logging.getLogger(__name__)


class NetworkManager:
    """
    Manages thermal network components and topology.

    Responsibilities:
    - Parse network YAML configuration
    - Create and attach pipe and node components
    - Connect network to heat sources and demands
    - Coordinate constraints between components
    - Export results for dashboard
    """

    def __init__(self, config: Dict[str, Any], config_dir: Path = None):
        """
        Initialize network manager.

        Args:
            config: Full configuration dict containing 'thermal_network' section
            config_dir: Base directory for resolving relative topology file paths

        The network manager handles:
        - Loading network topology from YAML or Excel files
        - Parsing nodes (plants, consumers, junctions) and pipes
        - Creating Pyomo constraints for the thermal network
        - Calculating heat losses using physical formulas (Q = U × L × ΔT)
        """
        self.config = config
        self.config_dir = config_dir or Path.cwd()

        # Initialize all attributes to safe defaults (prevents AttributeError)
        self.nodes = {}           # Dict[str, dict] - node configurations
        self.pipes = {}           # Dict[str, dict] - pipe configurations
        self.pipe_catalog = {}    # Dict[str, dict] - available pipe types
        self.topology = {}        # Dict - raw topology data from file
        self.parameters = {}      # Dict - network parameters (temps, pressures)
        self.brownfield_mode = False  # bool - True = fixed topology, simplified constraints

        self.network_enabled = config.get('thermal_network', {}).get('enabled', False)

        if self.network_enabled:
            self._load_network_topology()

    def _find_repo_root(self, start_path: Path = None) -> Path:
        """
        Find repository root by searching for .git directory.

        Args:
            start_path: Starting directory (default: current working directory)

        Returns:
            Path to repository root, or start_path if not found
        """
        if start_path is None:
            start_path = Path.cwd()

        current = start_path.resolve()

        # Search up to 10 levels
        for _ in range(10):
            if (current / '.git').exists():
                return current

            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent

        # If not found, return the original path
        return start_path

    def _resolve_path(self, path_str: str) -> Path:
        """
        Intelligently resolve a path that could be:
        - Absolute
        - Relative to config_dir
        - Relative to repository root

        Args:
            path_str: Path string to resolve

        Returns:
            Resolved absolute Path
        """
        path = Path(path_str)

        # If already absolute, use as-is
        if path.is_absolute():
            logger.debug(f"Path is absolute: {path}")
            return path

        # Try relative to repository root FIRST (most common case)
        repo_root = self._find_repo_root()
        repo_relative = repo_root / path
        logger.debug(f"Trying repo_relative: {repo_relative}")
        if repo_relative.exists():
            logger.debug(f"Found at repo root: {repo_relative}")
            return repo_relative

        # Try relative to config_dir
        config_relative = self.config_dir / path
        logger.debug(f"Trying config_relative: {config_relative}")
        if config_relative.exists():
            logger.debug(f"Found at config_dir: {config_relative}")
            return config_relative

        # Not found - return repo_relative as best guess (will fail later with clear error)
        logger.warning(f"Path not found. Tried:\n  - {repo_relative}\n  - {config_relative}")
        return repo_relative

    def _load_network_topology(self):
        """
        Load network topology from YAML file, Excel file, or inline config.

        Topology sources (checked in order):
        1. topology_excel: Path to Excel file with Network_Nodes/Pipes/Parameters sheets
        2. topology_file: Path to YAML file with network definition
        3. Inline: thermal_network section contains topology directly

        Raises:
            FileNotFoundError: If specified topology file doesn't exist
            yaml.YAMLError: If YAML file is malformed
        """
        network_config = self.config.get('thermal_network', {})

        # Check for external topology file (YAML)
        topology_file = network_config.get('topology_file')

        # Check for Excel-based topology
        topology_excel = network_config.get('topology_excel')

        if topology_excel:
            # Load from Excel file
            excel_path = self._resolve_path(topology_excel)
            logger.info(f"Loading network topology from Excel: {excel_path}")

            try:
                from energis.io.network_loader import load_network_from_excel
                topology_data = load_network_from_excel(
                    str(excel_path),
                    nodes_sheet=network_config.get('nodes_sheet', 'Network_Nodes'),
                    pipes_sheet=network_config.get('pipes_sheet', 'Network_Pipes'),
                    params_sheet=network_config.get('params_sheet', 'Network_Parameters'),
                )
            except FileNotFoundError:
                logger.error(f"Network Excel file not found: {excel_path}")
                self.network_enabled = False
                return
            except Exception as e:
                logger.error(f"Error loading network from Excel: {e}")
                self.network_enabled = False
                return

            if topology_data is None:
                logger.warning("No network data found in Excel, disabling network")
                self.network_enabled = False
                return

        elif topology_file:
            topology_path = self._resolve_path(topology_file)
            logger.info(f"Loading network topology from YAML: {topology_path}")

            try:
                with open(topology_path, 'r') as f:
                    topology_data = yaml.safe_load(f)
            except FileNotFoundError:
                logger.error(f"=" * 70)
                logger.error(f"THERMAL NETWORK ERROR: Topology file not found!")
                logger.error(f"  Expected: {topology_path}")
                logger.error(f"  Config value: {topology_file}")
                logger.error(f"  Config dir: {self.config_dir}")
                logger.error(f"  Repo root: {self._find_repo_root()}")
                logger.error(f"=" * 70)
                self.network_enabled = False
                return
            except yaml.YAMLError as e:
                logger.error(f"Error parsing network YAML file: {e}")
                self.network_enabled = False
                return
        else:
            # Inline network definition
            topology_data = network_config

        # Store topology data
        self.topology = topology_data
        self.parameters = topology_data.get('parameters', {})
        self.pipe_catalog = topology_data.get('pipe_catalog', {})

        # Parse nodes
        self._parse_nodes(topology_data)

        # Parse pipes
        self._parse_pipes(topology_data)

        logger.info(f"Loaded network: {len(self.nodes)} nodes, {len(self.pipes)} pipes")

    def _parse_nodes(self, topology_data: Dict):
        """Parse node definitions from topology."""
        # Production plants
        for plant_config in topology_data.get('production_plants', []):
            node_id = plant_config['node_id']
            self.nodes[node_id] = {
                **plant_config,
                'type': 'plant',
                'node_category': 'plant'
            }

        # Pump stations
        for pump_config in topology_data.get('pump_stations', []):
            node_id = pump_config['node_id']
            self.nodes[node_id] = {
                **pump_config,
                'type': 'junction',
                'node_category': 'pump_station'
            }

        # Consumer zones
        for consumer_config in topology_data.get('consumer_zones', []):
            node_id = consumer_config['node_id']
            self.nodes[node_id] = {
                **consumer_config,
                'type': 'consumer',
                'node_category': 'consumer'
            }

    def _parse_pipes(self, topology_data: Dict):
        """Parse pipe definitions from topology."""
        for pipe_config in topology_data.get('pipes', []):
            pipe_id = pipe_config['id']
            self.pipes[pipe_id] = pipe_config

    def attach_to_model(self, model, time_set, buses: Dict) -> Dict[str, Any]:
        """
        Attach network components to Pyomo model.

        Args:
            model: Pyomo ConcreteModel
            time_set: Set of timesteps
            buses: Dict of bus components

        Returns:
            Dict with network results and references
        """
        if not self.network_enabled:
            logger.info("Thermal network disabled, skipping")
            return {}

        logger.info("=" * 60)
        logger.info("ATTACHING THERMAL NETWORK")
        logger.info("=" * 60)

        temp_setup = self._setup_temperatures(model, time_set)
        pipe_components = self._attach_all_pipes(model, time_set, buses, temp_setup)
        node_components = self._attach_all_nodes(model, time_set, buses, temp_setup, pipe_components)

        self._link_greenfield_temperatures(model, time_set, pipe_components, node_components)
        self._fix_brownfield_temperatures(model, time_set, temp_setup, pipe_components, node_components)
        self._link_consumer_demands(model, time_set, temp_setup, pipe_components, node_components)
        self._link_junction_flows(model, time_set, pipe_components, node_components)
        self._link_plant_return_temps(model, time_set, temp_setup, pipe_components, node_components)
        self._setup_network_losses(model, time_set, temp_setup, pipe_components)

        logger.info(f"\n" + "=" * 60)
        logger.info(f"THERMAL NETWORK ATTACHED SUCCESSFULLY")
        logger.info(f"  Pipes: {len(pipe_components)}")
        logger.info(f"  Nodes: {len(node_components)}")
        logger.info("=" * 60)

        return {
            'pipes': pipe_components,
            'nodes': node_components,
            'parameters': self.parameters,
            'brownfield_mode': temp_setup['brownfield_mode'],
            'supply_temp': temp_setup['supply_temp'],
            'return_temp': temp_setup['return_temp'],
            'ground_temp': temp_setup['ground_temp'],
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    def _setup_temperatures(self, model, time_set) -> Dict[str, Any]:
        """Setup temperature profiles and brownfield mode flag.

        Returns a dict with keys: supply_temp, return_temp, ground_temp,
        use_heating_curve, use_outdoor_temp, supply_temp_dict, brownfield_mode.
        Also sets model.outdoor_temp and model.supply_temp_series.
        """
        supply_temp_nominal = self.parameters.get('supply_temp_nominal_c', 90.0)
        return_temp = self.parameters.get('return_temp_nominal_c', 50.0)
        ground_temp = self.parameters.get('ground_temp_default_c', 10.0)

        use_outdoor_temp = self.config.get('thermal_network', {}).get('use_outdoor_temperature', False)
        if use_outdoor_temp and hasattr(model, 'outdoor_temp'):
            logger.info("Using time-varying outdoor temperature from model")
            outdoor_temp_series = [model.outdoor_temp[t] for t in time_set]
        else:
            model.outdoor_temp = {t: ground_temp for t in time_set}
            outdoor_temp_series = [ground_temp for _ in time_set]
            logger.info(f"Using fixed ground temperature: {ground_temp}°C")

        heating_curve_config_raw = self.parameters.get('heating_curve', {})
        heating_curve_config = resolve_heating_curve_profile(
            heating_curve_config_raw,
            config_dir=self.config_dir,
        )
        use_heating_curve = heating_curve_config.get('enabled', False)

        if use_heating_curve and use_outdoor_temp:
            T_supply_min = heating_curve_config.get('T_supply_min_c', 80.0)
            T_supply_max = heating_curve_config.get('T_supply_max_c', 120.0)
            T_outdoor_high = heating_curve_config.get('T_outdoor_high_c', 20.0)
            T_outdoor_low = heating_curve_config.get('T_outdoor_low_c', -10.0)

            supply_temp_series = calculate_supply_temperature_series(
                T_outdoor_series=outdoor_temp_series,
                T_supply_min_c=T_supply_min,
                T_supply_max_c=T_supply_max,
                T_outdoor_high_c=T_outdoor_high,
                T_outdoor_low_c=T_outdoor_low,
            )
            model.supply_temp_series = {t: supply_temp_series[i] for i, t in enumerate(time_set)}

            curve_params = get_heating_curve_parameters(
                T_supply_min_c=T_supply_min,
                T_supply_max_c=T_supply_max,
                T_outdoor_high_c=T_outdoor_high,
                T_outdoor_low_c=T_outdoor_low,
            )
            logger.info(f"\n  HEATING CURVE (Heizkurve) enabled:")
            logger.info(f"    Formula: {curve_params['formula']}")
            logger.info(f"    Range: {T_supply_min}°C (at {T_outdoor_high}°C outdoor) "
                       f"to {T_supply_max}°C (at {T_outdoor_low}°C outdoor)")
            logger.info(f"    Supply temp range in data: "
                       f"{min(supply_temp_series):.1f}°C - {max(supply_temp_series):.1f}°C")

            supply_temp = sum(supply_temp_series) / len(supply_temp_series)
            logger.info(f"    Average supply temp: {supply_temp:.1f}°C")
        else:
            supply_temp = supply_temp_nominal
            model.supply_temp_series = {t: supply_temp for t in time_set}
            if use_heating_curve and not use_outdoor_temp:
                logger.warning("  Heating curve enabled but outdoor temperature not available!")
                logger.warning("  Set 'use_outdoor_temperature: true' in config to enable heating curve.")

        brownfield_mode = self.config.get('thermal_network', {}).get('brownfield_mode', True)
        self.brownfield_mode = brownfield_mode

        return {
            'supply_temp': supply_temp,
            'return_temp': return_temp,
            'ground_temp': ground_temp,
            'use_heating_curve': use_heating_curve,
            'use_outdoor_temp': use_outdoor_temp,
            'supply_temp_dict': {t: model.supply_temp_series[t] for t in time_set},
            'brownfield_mode': brownfield_mode,
        }

    def _attach_all_pipes(self, model, time_set, buses, temp_setup) -> Dict:
        """Phase 1: Validate and attach all pipe pair blocks to the model."""
        supply_temp = temp_setup['supply_temp']
        return_temp = temp_setup['return_temp']
        use_outdoor_temp = temp_setup['use_outdoor_temp']
        brownfield_mode = temp_setup['brownfield_mode']

        pipe_components: Dict = {}
        logger.info(f"\nAttaching {len(self.pipes)} pipe pairs...")

        if brownfield_mode:
            logger.info("  [Brownfield mode: fixed topology with physical losses (Q = U×L×ΔT)]")

        for pipe_id, pipe_config in self.pipes.items():
            enriched_config = {
                **pipe_config,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_nominal_c': return_temp,
                'use_outdoor_temperature': use_outdoor_temp,
                'pipe_catalog': self.pipe_catalog,
                'brownfield_mode': brownfield_mode,
                **self.parameters
            }
            PipePairBlock.validate_config(enriched_config)
            pipe_result = PipePairBlock.attach(model, time_set, enriched_config, buses)
            pipe_components[pipe_id] = pipe_result
            logger.info(
                f"  ✓ {pipe_id}: {pipe_config['from_node']} → {pipe_config['to_node']} "
                f"({pipe_config['length_m']}m)"
            )

        return pipe_components

    def _attach_all_nodes(self, model, time_set, buses, temp_setup, pipe_components) -> Dict:
        """Phase 2: Validate and attach all thermal node blocks to the model."""
        supply_temp = temp_setup['supply_temp']
        return_temp = temp_setup['return_temp']
        brownfield_mode = temp_setup['brownfield_mode']

        node_components: Dict = {}
        logger.info(f"\nAttaching {len(self.nodes)} thermal nodes...")

        for node_id, node_config in self.nodes.items():
            enriched_config = {
                **node_config,
                'id': node_id,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_c': return_temp,
                'brownfield_mode': brownfield_mode,
            }
            ThermalNodeBlock.validate_config(enriched_config)
            node_result = ThermalNodeBlock.attach(
                model, time_set, enriched_config, buses, pipe_components
            )
            node_components[node_id] = node_result
            node_type = node_config.get('type', 'unknown')
            logger.info(f"  ✓ {node_id} ({node_type})")

        return node_components

    def _link_greenfield_temperatures(self, model, time_set, pipe_components, node_components) -> None:
        """Phase 3: Link pipe temperature variables to node temperatures (greenfield only).

        In brownfield mode this is skipped – temperatures are fixed in _fix_brownfield_temperatures.
        Also tracks return pipes for each plant node (used by _link_plant_return_temps).
        """
        logger.info(f"\nConnecting pipes to nodes...")

        for pipe_id, pipe_comp in pipe_components.items():
            from_node = pipe_comp['from_node']
            to_node = pipe_comp['to_node']

            if not self.brownfield_mode:
                if from_node in node_components:
                    from_node_comp = node_components[from_node]
                    pipe_T_supply_in = pipe_comp['T_supply_in']
                    node_T_supply = from_node_comp['T_supply']
                    constraint_name = f"link_pipe_{pipe_id}_inlet_to_node_{from_node}"

                    def link_rule(m, t, _pipe=pipe_T_supply_in, _node=node_T_supply):
                        if isinstance(_node, pyo.Param):
                            return _pipe[t] == pyo.value(_node[t])
                        else:
                            return _pipe[t] == _node[t]

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=link_rule))
                    logger.info(f"    Linked {pipe_id} inlet ← {from_node} supply temp")

                if to_node in node_components:
                    to_node_comp = node_components[to_node]
                    if to_node_comp['type'] in ['consumer', 'junction']:
                        pass  # Handled by node's temperature mixing constraint

                if to_node in node_components:
                    to_node_comp = node_components[to_node]
                    pipe_T_return_in = pipe_comp['T_return_in']
                    node_T_return = to_node_comp['T_return']
                    constraint_name = f"link_pipe_{pipe_id}_return_to_node_{to_node}"

                    def return_link_rule(m, t, _pipe=pipe_T_return_in, _node=node_T_return):
                        if isinstance(_node, pyo.Param):
                            return _pipe[t] == pyo.value(_node[t])
                        else:
                            return _pipe[t] == _node[t]

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=return_link_rule))
                    logger.info(f"    Linked {pipe_id} return ← {to_node} return temp")
            else:
                logger.info(f"    {pipe_id}: skipping temp links (brownfield - handled in Phase 3b)")

            # Track return pipes for each plant node
            if from_node in node_components:
                from_node_comp = node_components[from_node]
                if from_node_comp['type'] == 'plant':
                    if 'return_pipes' not in from_node_comp:
                        from_node_comp['return_pipes'] = []
                    from_node_comp['return_pipes'].append(pipe_id)

    def _fix_brownfield_temperatures(self, model, time_set, temp_setup, pipe_components, node_components) -> None:
        """Phase 3b: Fix pipe and node temperatures using physics in brownfield mode."""
        if not temp_setup['brownfield_mode']:
            return

        supply_temp = temp_setup['supply_temp']
        return_temp = temp_setup['return_temp']
        ground_temp = temp_setup['ground_temp']
        use_heating_curve = temp_setup['use_heating_curve']
        supply_temp_dict = temp_setup['supply_temp_dict']

        logger.info(f"\nFixing temperatures for brownfield mode...")

        use_physics_temp_drop = self.parameters.get('use_physics_temp_drop', True)
        default_temp_drop = self.parameters.get('brownfield_temp_drop_per_pipe_c', 1.0)

        if use_physics_temp_drop and hasattr(model, 'heatd'):
            first_t = list(time_set)[0]
            total_demand_mw = pyo.value(model.heatd[first_t]) if hasattr(model, 'heatd') else 10.0
            total_demand_kw = total_demand_mw * 1000

            pipes_for_calc = {}
            for pipe_id in self.pipes:
                pipe_cfg = self.pipes[pipe_id]
                pipes_for_calc[pipe_id] = {
                    'length_m': pipe_cfg.get('length_m', 100),
                    'u_value_w_per_m_k': pipe_cfg.get('u_value_w_per_m_k', 0.5),
                }

            pipe_temp_drops = calculate_pipe_temp_drops(
                pipes_config=pipes_for_calc,
                supply_temp_c=supply_temp,
                return_temp_c=return_temp,
                ground_temp_c=ground_temp,
                total_heat_demand_kw=total_demand_kw,
            )
            logger.info(f"  Using physics-based temperature drops (demand={total_demand_mw:.1f} MW)")
            for pipe_id, drops in pipe_temp_drops.items():
                logger.debug(f"    {pipe_id}: supply_drop={drops['supply_drop_c']:.2f}°C, "
                           f"return_drop={drops['return_drop_c']:.2f}°C")
        else:
            pipe_temp_drops = None
            logger.info(f"  Using constant temperature drop: {default_temp_drop}°C/pipe")

        pipe_hop_counts = {}
        for pipe_id, pipe_comp in pipe_components.items():
            from_node = pipe_comp['from_node']
            from_node_comp = node_components.get(from_node, {})
            from_node_type = from_node_comp.get('type', 'unknown')

            if from_node_type == 'plant':
                pipe_hop_counts[pipe_id] = 0
            else:
                incoming_to_from = from_node_comp.get('incoming_pipes', [])
                pipe_hop_counts[pipe_id] = len(incoming_to_from) if incoming_to_from else 1

        for pipe_id, pipe_comp in pipe_components.items():
            from_node = pipe_comp['from_node']
            to_node = pipe_comp['to_node']
            from_node_comp = node_components.get(from_node, {})
            to_node_comp = node_components.get(to_node, {})
            from_node_type = from_node_comp.get('type', 'unknown')
            to_node_type = to_node_comp.get('type', 'unknown')

            pipe_prefix = pipe_id.upper().replace('-', '_')
            T_supply_in = getattr(model, f'{pipe_prefix}_T_supply_in')
            T_supply_out = getattr(model, f'{pipe_prefix}_T_supply_out')
            T_return_in = getattr(model, f'{pipe_prefix}_T_return_in')
            T_return_out = getattr(model, f'{pipe_prefix}_T_return_out')

            hop_count = pipe_hop_counts[pipe_id]

            if pipe_temp_drops and pipe_id in pipe_temp_drops:
                supply_drop = pipe_temp_drops[pipe_id]['supply_drop_c']
                return_drop = pipe_temp_drops[pipe_id]['return_drop_c']
            else:
                supply_drop = default_temp_drop
                return_drop = default_temp_drop

            cumulative_supply_drop = 0.0
            if hop_count > 0 and pipe_temp_drops:
                upstream_drops = [d['supply_drop_c'] for d in pipe_temp_drops.values()]
                avg_upstream_drop = sum(upstream_drops) / len(upstream_drops) if upstream_drops else default_temp_drop
                cumulative_supply_drop = avg_upstream_drop * hop_count
            else:
                cumulative_supply_drop = default_temp_drop * hop_count

            for t in time_set:
                base_supply_temp = supply_temp_dict[t]

                if from_node_type == 'plant':
                    inlet_temp_t = base_supply_temp
                    outlet_temp_t = base_supply_temp - supply_drop
                else:
                    inlet_temp_t = base_supply_temp - cumulative_supply_drop
                    outlet_temp_t = inlet_temp_t - supply_drop

                T_supply_in[t].fix(inlet_temp_t)
                T_supply_out[t].fix(outlet_temp_t)

            if use_heating_curve:
                avg_inlet = sum(supply_temp_dict[t] - cumulative_supply_drop for t in time_set) / len(list(time_set))
                logger.info(
                    f"    {pipe_id}: {'plant' if from_node_type == 'plant' else 'cascade'} pipe, "
                    f"T_supply_in=heating_curve (avg {avg_inlet:.1f}°C), ΔT_supply={supply_drop:.2f}°C"
                )
            else:
                inlet_temp = supply_temp - cumulative_supply_drop
                outlet_temp = inlet_temp - supply_drop
                logger.info(
                    f"    {pipe_id}: {'plant' if from_node_type == 'plant' else 'cascade'} pipe, "
                    f"T_supply_in={inlet_temp:.1f}°C, T_supply_out={outlet_temp:.1f}°C (ΔT={supply_drop:.2f}°C)"
                )

            if to_node_type == 'consumer':
                to_node_cfg = self.nodes.get(to_node, {})
                consumer_return_temp = to_node_cfg.get('return_temp_c', return_temp)
                pipe_return_in_temp = consumer_return_temp
                pipe_return_out_temp = consumer_return_temp - return_drop
                logger.info(
                    f"      T_return_in={pipe_return_in_temp}°C (from consumer), "
                    f"T_return_out={pipe_return_out_temp}°C"
                )
            else:
                pipe_return_in_temp = return_temp
                pipe_return_out_temp = return_temp - return_drop

            for t in time_set:
                T_return_in[t].fix(pipe_return_in_temp)
                T_return_out[t].fix(pipe_return_out_temp)

        logger.info(f"  ✓ Fixed temperatures for {len(pipe_components)} pipes")
        if use_heating_curve:
            logger.info(f"    (Using time-varying supply temperatures from heating curve)")

        logger.info(f"\nFixing node temperatures for brownfield mode...")

        for node_id, node_comp in node_components.items():
            node_type = node_comp['type']

            if node_type == 'plant':
                T_return = node_comp['T_return']
                if isinstance(T_return, pyo.Var):
                    for t in time_set:
                        T_return[t].fix(return_temp)
                    logger.info(f"    {node_id}: Fixed return temp to {return_temp}°C")

            elif node_type == 'consumer':
                T_supply = node_comp['T_supply']
                incoming_pipes = node_comp.get('incoming_pipes', [])

                if incoming_pipes and isinstance(T_supply, pyo.Var):
                    first_pipe = incoming_pipes[0]
                    pipe_prefix = first_pipe.upper().replace('-', '_')
                    pipe_T_supply_out = getattr(model, f'{pipe_prefix}_T_supply_out')

                    first_t = next(iter(time_set))
                    consumer_supply_temp = pyo.value(pipe_T_supply_out[first_t])

                    for t in time_set:
                        T_supply[t].fix(consumer_supply_temp)
                    logger.info(
                        f"    {node_id}: Fixed supply temp to "
                        f"{consumer_supply_temp}°C (from pipe {first_pipe})"
                    )

            elif node_type == 'junction':
                T_supply = node_comp['T_supply']
                T_return = node_comp['T_return']

                incoming_pipes = node_comp.get('incoming_pipes', [])
                if incoming_pipes:
                    first_pipe = incoming_pipes[0]
                    pipe_prefix = first_pipe.upper().replace('-', '_')
                    pipe_T_supply_out = getattr(model, f'{pipe_prefix}_T_supply_out')

                    first_t = next(iter(time_set))
                    junction_supply_temp = pyo.value(pipe_T_supply_out[first_t])

                    if isinstance(T_supply, pyo.Var):
                        for t in time_set:
                            T_supply[t].fix(junction_supply_temp)
                        logger.info(
                            f"    {node_id}: Fixed supply temp to "
                            f"{junction_supply_temp}°C"
                        )

                if isinstance(T_return, pyo.Var):
                    for t in time_set:
                        T_return[t].fix(return_temp)
                    logger.info(f"    {node_id}: Fixed return temp to {return_temp}°C")

        logger.info(f"  ✓ Fixed temperatures for {len(node_components)} nodes")

    def _link_consumer_demands(self, model, time_set, temp_setup, pipe_components, node_components) -> None:
        """Phase 4: Connect consumer heat demands to incoming pipe flow variables."""
        brownfield_mode = temp_setup['brownfield_mode']
        supply_temp = temp_setup['supply_temp']
        return_temp = temp_setup['return_temp']
        ground_temp = temp_setup['ground_temp']

        logger.info(f"\nConnecting consumer demands to pipes...")

        if brownfield_mode:
            logger.info("  [Brownfield mode: using simplified demand-based flow linking]")

            consumer_info = {}
            for node_id, node_comp in node_components.items():
                if node_comp['type'] == 'consumer':
                    incoming = node_comp.get('incoming_pipes', [])
                    consumer_info[node_id] = {
                        'demand_fraction': node_comp.get('demand_fraction', 0.0),
                        'num_sources': max(1, len(incoming)),
                        'incoming_pipes': incoming
                    }

            def get_downstream_demand(pipe_id, visited=None):
                if visited is None:
                    visited = set()
                if pipe_id in visited:
                    return 0.0
                visited.add(pipe_id)

                pipe_info = pipe_components.get(pipe_id, {})
                to_node = pipe_info.get('to_node')
                if not to_node:
                    return 0.0

                node_comp = node_components.get(to_node, {})
                incoming_count = len(node_comp.get('incoming_pipes', [pipe_id]))
                split_factor = 1.0 / max(1, incoming_count)

                if to_node in consumer_info:
                    info = consumer_info[to_node]
                    local_demand = info['demand_fraction'] * split_factor
                else:
                    local_demand = 0.0

                outgoing = node_comp.get('outgoing_pipes', [])
                downstream_demand = sum(
                    get_downstream_demand(out_pipe, visited.copy())
                    for out_pipe in outgoing
                ) * split_factor

                return local_demand + downstream_demand

            pipe_service_fractions = {}
            for pipe_id in pipe_components.keys():
                pipe_service_fractions[pipe_id] = get_downstream_demand(pipe_id)
                logger.info(
                    f"    {pipe_id}: serves {pipe_service_fractions[pipe_id]*100:.1f}% of demand"
                )

            plant_pipe_total = sum(
                pipe_service_fractions.get(pid, 0)
                for pid, pc in pipe_components.items()
                if node_components.get(pc.get('from_node'), {}).get('type') == 'plant'
            )
            logger.info(
                f"  Total from plant pipes: {plant_pipe_total*100:.1f}% (should be ~100%)"
            )

            cp_water = self.parameters.get('cp_water_kj_per_kg_k', 4.186)
            delta_T = supply_temp - return_temp
            logger.info(f"  Creating brownfield flow constraints (delta_T = {delta_T}K)...")
            logger.info(f"  Calculating physical network losses (Q = U × L × ΔT)...")

            total_network_loss_mw = 0.0
            pipe_losses = {}

            for pipe_id, pipe_config in self.pipes.items():
                length_m = pipe_config.get('length_m', 0.0)
                u_supply = pipe_config.get('u_value_supply_w_per_m_k', 0.28)
                u_return = pipe_config.get('u_value_return_w_per_m_k', 0.30)

                loss_data = pipe_total_heat_loss_mw(
                    length_m=length_m,
                    u_supply_w_per_m_k=u_supply,
                    u_return_w_per_m_k=u_return,
                    T_supply_c=supply_temp,
                    T_return_c=return_temp,
                    T_ground_c=ground_temp,
                )

                pipe_losses[pipe_id] = {
                    'supply_mw': loss_data['supply_mw'],
                    'return_mw': loss_data['return_mw'],
                    'total_mw': loss_data['total_mw'],
                    'length_m': length_m,
                }
                total_network_loss_mw += loss_data['total_mw']
                logger.info(
                    f"    {pipe_id}: L={length_m:.0f}m, "
                    f"U_s={u_supply:.2f}, U_r={u_return:.2f} → "
                    f"Q_loss={loss_data['total_mw']*1000:.1f} kW"
                )

            logger.info(f"  Ground temperature: {ground_temp}°C")
            logger.info(f"  Supply/Return temps: {supply_temp}°C / {return_temp}°C")
            logger.info(
                f"  Total network heat loss: {total_network_loss_mw:.3f} MW (constant)"
            )

            model._brownfield_total_loss_mw = total_network_loss_mw
            model._brownfield_pipe_losses = pipe_losses
            model._brownfield_pipe_service_fractions = pipe_service_fractions
            model._brownfield_delta_T = delta_T
            model._brownfield_cp_water = cp_water
            model._brownfield_ground_temp = ground_temp
            return

        # Greenfield: full coupling between pipes and demand
        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'consumer':
                continue
            incoming_pipes = node_comp.get('incoming_pipes', [])
            outgoing_pipes = node_comp.get('outgoing_pipes', [])
            has_outgoing = len(outgoing_pipes) > 0

            if len(incoming_pipes) == 1 and not has_outgoing:
                pipe_id = incoming_pipes[0]
                pipe_comp = pipe_components[pipe_id]
                pipe_m_dot = pipe_comp['m_dot']
                node_m_dot = node_comp['m_dot_demand']

                setattr(model, f"link_demand_{node_id}_to_pipe_{pipe_id}",
                        pyo.Constraint(time_set, rule=lambda m, t, _p=pipe_m_dot, _n=node_m_dot: _p[t] == _n[t]))

                pipe_Q_delivered = pipe_comp['Q_delivered']
                node_Q_demand = node_comp['Q_demand']

                def demand_heat_rule(m, t, _Q_del=pipe_Q_delivered, _Q_dem=node_Q_demand):
                    if isinstance(_Q_dem, pyo.Param):
                        return _Q_del[t] == pyo.value(_Q_dem[t])
                    else:
                        return _Q_del[t] == _Q_dem[t]

                setattr(model, f"link_heat_demand_{node_id}_to_pipe_{pipe_id}",
                        pyo.Constraint(time_set, rule=demand_heat_rule))
                logger.info(f"  ✓ {node_id} demand ← pipe {pipe_id}")

            elif len(incoming_pipes) == 1 and has_outgoing:
                pipe_id = incoming_pipes[0]
                pipe_comp = pipe_components[pipe_id]
                pipe_m_dot = pipe_comp['m_dot']
                node_m_dot = node_comp['m_dot_demand']

                def passthrough_flow_rule(m, t, _pipe=pipe_m_dot, _node=node_m_dot, _out=outgoing_pipes):
                    outgoing_flow = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                    return _pipe[t] == _node[t] + outgoing_flow

                setattr(model, f"link_demand_{node_id}_passthrough_flow",
                        pyo.Constraint(time_set, rule=passthrough_flow_rule))
                logger.info(
                    f"  ✓ {node_id} passthrough: incoming={pipe_id}, "
                    f"outgoing={len(outgoing_pipes)} pipes"
                )

            elif len(incoming_pipes) > 1:
                node_m_dot = node_comp['m_dot_demand']
                node_Q_demand = node_comp['Q_demand']

                if has_outgoing:
                    logger.info(
                        f"  ✓ {node_id} has {len(incoming_pipes)} incoming, "
                        f"{len(outgoing_pipes)} outgoing pipes - passthrough hub"
                    )

                    def multi_passthrough_flow_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes, _node=node_m_dot):
                        total_inflow = sum(pipe_components[pid]['m_dot'][t] for pid in _in)
                        total_outflow = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                        return total_inflow == _node[t] + total_outflow

                    setattr(model, f"link_demand_{node_id}_multi_passthrough_flow",
                            pyo.Constraint(time_set, rule=multi_passthrough_flow_rule))
                    logger.info(f"    ← incoming: {', '.join(incoming_pipes)}")
                    logger.info(f"    → outgoing: {', '.join(outgoing_pipes)}")

                else:
                    logger.info(
                        f"  ✓ {node_id} has {len(incoming_pipes)} incoming pipes - "
                        f"creating multi-pipe flow balance"
                    )

                    def multi_pipe_flow_rule(m, t, _incoming=incoming_pipes, _node=node_m_dot):
                        total_inflow = sum(pipe_components[pid]['m_dot'][t] for pid in _incoming)
                        return total_inflow == _node[t]

                    setattr(model, f"link_demand_{node_id}_multi_pipe_flow",
                            pyo.Constraint(time_set, rule=multi_pipe_flow_rule))

                    def multi_pipe_heat_rule(m, t, _incoming=incoming_pipes, _Q=node_Q_demand):
                        total_heat = sum(pipe_components[pid]['Q_delivered'][t] for pid in _incoming)
                        if isinstance(_Q, pyo.Param):
                            return total_heat >= pyo.value(_Q[t]) * 0.99
                        else:
                            return total_heat >= _Q[t] * 0.99

                    setattr(model, f"link_demand_{node_id}_multi_pipe_heat",
                            pyo.Constraint(time_set, rule=multi_pipe_heat_rule))
                    logger.info(f"    ← pipes: {', '.join(incoming_pipes)}")

            else:
                logger.warning(f"  ⚠ {node_id} has no incoming pipes!")

    def _link_junction_flows(self, model, time_set, pipe_components, node_components) -> None:
        """Phase 4b: Setup flow balance constraints for junction nodes (greenfield only)."""
        logger.info(f"\nSetting up junction flow balance constraints...")

        if self.brownfield_mode:
            logger.info("  [Brownfield mode: junction flows determined by brownfield_flow_rule]")
            return

        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'junction':
                continue
            incoming_pipes = node_comp.get('incoming_pipes', [])
            outgoing_pipes = node_comp.get('outgoing_pipes', [])

            if not incoming_pipes or not outgoing_pipes:
                logger.warning(
                    f"  ⚠ Junction {node_id} incomplete: "
                    f"{len(incoming_pipes)} in, {len(outgoing_pipes)} out"
                )
                continue

            def junction_flow_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes):
                total_in = sum(pipe_components[pid]['m_dot'][t] for pid in _in)
                total_out = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                return total_in == total_out

            setattr(model, f"junction_{node_id}_flow_balance",
                    pyo.Constraint(time_set, rule=junction_flow_rule))
            logger.info(
                f"  ✓ {node_id}: {len(incoming_pipes)} in = {len(outgoing_pipes)} out"
            )

    def _link_plant_return_temps(self, model, time_set, temp_setup, pipe_components, node_components) -> None:
        """Phase 5+5b: Setup plant return temperature constraints and plant-to-network heat linkage."""
        return_temp = temp_setup['return_temp']
        supply_temp = temp_setup['supply_temp']
        brownfield_mode = temp_setup['brownfield_mode']

        logger.info(f"\nSetting up plant return temperature constraints...")

        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'plant':
                continue
            return_pipes = node_comp.get('return_pipes', [])
            node_T_return = node_comp['T_return']

            if len(return_pipes) == 0:
                logger.warning(f"  ⚠ Plant {node_id} has no return pipes!")
            elif len(return_pipes) == 1:
                pipe_id = return_pipes[0]
                pipe_comp = pipe_components[pipe_id]
                pipe_T_return_out = pipe_comp['T_return_out']

                if brownfield_mode:
                    logger.info(
                        f"  ✓ {node_id} return temp fixed (brownfield - skipping link to pipe {pipe_id})"
                    )
                else:
                    def single_return_rule(m, t, _node=node_T_return, _pipe=pipe_T_return_out):
                        return _node[t] == _pipe[t]

                    setattr(model, f"plant_{node_id}_return_temp_single",
                            pyo.Constraint(time_set, rule=single_return_rule))
                    logger.info(f"  ✓ {node_id} return temp ← pipe {pipe_id}")

            else:
                if brownfield_mode:
                    logger.info(
                        f"  ✓ {node_id} return temp fixed to {return_temp}°C (brownfield mode)"
                    )
                    for t in time_set:
                        node_T_return[t].fix(return_temp)
                else:
                    def multi_return_rule(m, t, _pipes=return_pipes, _node=node_T_return):
                        total_return_flow = 0
                        weighted_temp = 0
                        for p_id in _pipes:
                            pc = pipe_components[p_id]
                            total_return_flow += pc['m_dot'][t]
                            weighted_temp += pc['T_return_out'][t] * pc['m_dot'][t]
                        return _node[t] * total_return_flow == weighted_temp

                    setattr(model, f"plant_{node_id}_return_temp_mixing",
                            pyo.Constraint(time_set, rule=multi_return_rule))
                    logger.info(
                        f"  ✓ {node_id} return temp mixing ← {len(return_pipes)} pipes "
                        f"(BILINEAR - needs QP solver)"
                    )

        logger.info(f"\nSetting up plant-to-network heat linkage...")

        plant_outgoing_pipes = []
        for node_id, node_comp in node_components.items():
            if node_comp['type'] == 'plant':
                outgoing = node_comp.get('outgoing_pipes', [])
                plant_outgoing_pipes.extend(outgoing)
                logger.info(f"  Plant {node_id}: {len(outgoing)} outgoing pipes")

        if plant_outgoing_pipes and hasattr(model, 'heatd'):
            network_delta_t = supply_temp - return_temp
            logger.info(
                f"  Network ΔT: {network_delta_t}K, {len(plant_outgoing_pipes)} plant pipes total"
            )
            logger.info(
                "  ℹ Network heat linkage: relying on system-level heat balance (no redundant constraint)"
            )
        else:
            logger.warning("  ⚠ No plant outgoing pipes or heatd not found - skipping linkage")

    def _setup_network_losses(self, model, time_set, temp_setup, pipe_components) -> None:
        """Phase 6: Create per-timestep network heat loss variable and binding constraint."""
        brownfield_mode = temp_setup['brownfield_mode']

        logger.info(f"\nCalculating network costs...")

        if hasattr(model, 'pipe_capex_costs'):
            total_pipe_capex = sum(model.pipe_capex_costs.values())
            logger.info(f"  Total pipe CAPEX (annualized): {total_pipe_capex}")

        logger.info(f"\nCreating per-timestep network heat losses...")

        loss_bounds = self.parameters.get('network_Q_loss_bounds_mw', (0, 50))
        try:
            loss_min, loss_max = loss_bounds
        except Exception:
            loss_min, loss_max = 0, 50

        model.network_Q_loss_per_timestep = pyo.Var(
            time_set,
            domain=pyo.NonNegativeReals,
            bounds=(loss_min, loss_max),
        )

        if brownfield_mode and hasattr(model, '_brownfield_total_loss_mw'):
            total_loss_mw = model._brownfield_total_loss_mw
            loss_model = self.parameters.get('brownfield_loss_model', 'constant')
            ref_heat_mw = self.parameters.get('brownfield_loss_ref_heat_mw', None)

            if (
                loss_model == 'demand_proportional'
                and hasattr(model, 'heatd')
                and ref_heat_mw is not None
                and ref_heat_mw > 0
            ):
                def brownfield_network_loss_rule(m, t):
                    return m.network_Q_loss_per_timestep[t] == total_loss_mw * (m.heatd[t] / 1000.0) / ref_heat_mw

                model.brownfield_network_loss = pyo.Constraint(
                    time_set, rule=brownfield_network_loss_rule
                )
                logger.info(
                    f"  ✓ Brownfield (demand_proportional): "
                    f"network_Q_loss_per_timestep scaled with heatd / {ref_heat_mw} MW"
                )
            else:
                def brownfield_network_loss_rule(m, t):
                    return m.network_Q_loss_per_timestep[t] == total_loss_mw

                model.brownfield_network_loss = pyo.Constraint(
                    time_set, rule=brownfield_network_loss_rule
                )
                logger.info(
                    f"  ✓ Brownfield: network_Q_loss_per_timestep = {total_loss_mw:.3f} MW (constant)"
                )
                if loss_model == 'demand_proportional':
                    logger.warning(
                        "brownfield_loss_model='demand_proportional' gesetzt, "
                        "aber 'heatd' oder 'brownfield_loss_ref_heat_mw' fehlen/ungültig. "
                        "Falle auf konstantes Verlustmodell zurück."
                    )
        else:
            def network_loss_per_timestep_rule(m, t):
                total_loss = sum(
                    pipe_comp['Q_loss_supply'][t] + pipe_comp['Q_loss_return'][t]
                    for pipe_comp in pipe_components.values()
                )
                return m.network_Q_loss_per_timestep[t] == total_loss

            model.network_loss_per_timestep_calc = pyo.Constraint(
                time_set,
                rule=network_loss_per_timestep_rule
            )
            logger.info(f"  ✓ Greenfield: network_Q_loss_per_timestep from pipe losses")


    def get_results(self, model, time_set) -> Dict[str, Any]:
        """
        Extract network results from solved model.

        Args:
            model: Solved Pyomo model
            time_set: Set of timesteps

        Returns:
            Dict with network results for all components
        """
        if not self.network_enabled:
            return {}

        logger.info("Extracting network results...")

        results = {
            'metadata': {
                'network_name': self.topology.get('metadata', {}).get('name', 'Unknown'),
                'total_nodes': len(self.nodes),
                'total_pipes': len(self.pipes),
            },
            'pipes': {},
            'nodes': {},
            'summary': {}
        }

        # Extract pipe results
        for pipe_id, pipe_config in self.pipes.items():
            pipe_results = PipePairBlock.get_results(model, time_set, pipe_config)
            results['pipes'][pipe_id] = pipe_results

        # Extract node results
        for node_id, node_config in self.nodes.items():
            node_results = ThermalNodeBlock.get_results(model, time_set, node_config)
            results['nodes'][node_id] = node_results

        # dt_h for MWh conversion
        dt_h = getattr(model, 'dt_h', 1.0)

        brownfield_mode = getattr(self, 'brownfield_mode', False)

        # BROWNFIELD MODE: pipe-level Hydraulik aus Demand + Service-Fractions
        if brownfield_mode and hasattr(model, '_brownfield_pipe_service_fractions'):
            logger.info("  [Brownfield mode: Calculating pipe-level hydraulics from demand]")

            pipe_fractions = model._brownfield_pipe_service_fractions
            delta_T = getattr(model, '_brownfield_delta_T', 65.0)  # K
            cp_water = getattr(model, '_brownfield_cp_water', 4.186)  # kJ/(kg·K)
            pipe_losses = getattr(model, '_brownfield_pipe_losses', {})

            # Last-skalierung wie im Modell
            loss_model = self.parameters.get('brownfield_loss_model', 'constant')
            ref_heat_mw = self.parameters.get('brownfield_loss_ref_heat_mw', None)

            # heatd_series liegt bereits (kW) vor
            n_timesteps = len(heatd_series)

            if loss_model == 'demand_proportional' and ref_heat_mw and ref_heat_mw > 0:
                # Skalenfaktor pro Zeitschritt: heatd(t)/Q_ref
                loss_scale = [
                    (heatd_kw / 1000.0) / ref_heat_mw
                    for heatd_kw in heatd_series
                ]
            else:
                loss_scale = [1.0] * n_timesteps

            for pipe_id, service_frac in pipe_fractions.items():
                if pipe_id not in results['pipes']:
                    continue

                pipe_config = self.pipes.get(pipe_id, {})
                pipe_res = results['pipes'][pipe_id]

                # m_dot Serie (wie bisher)
                flow_series = [
                    heat_kw_to_mdot_kg_s(heatd * service_frac, cp_water, delta_T)
                    for heatd in heatd_series
                ]

                pipe_loss_data = pipe_losses.get(pipe_id, {})
                q_loss_supply_mw = pipe_loss_data.get('supply_mw', 0.0)
                q_loss_return_mw = pipe_loss_data.get('return_mw', 0.0)

                # Zeitvariable Verluste (kW), skaliert mit loss_scale[t]
                q_loss_supply_kw_series = [
                    q_loss_supply_mw * 1000 * loss_scale[i]
                    for i in range(n_timesteps)
                ]
                q_loss_return_kw_series = [
                    q_loss_return_mw * 1000 * loss_scale[i]
                    for i in range(n_timesteps)
                ]
                q_loss_series_kw = [
                    (q_loss_supply_mw + q_loss_return_mw) * 1000 * loss_scale[i]
                    for i in range(n_timesteps)
                ]

                # ... (Geschwindigkeit, Druck usw. wie bisher)
                diameter_mm = pipe_config.get(
                    'current_diameter_supply_mm',
                    pipe_config.get('diameter_mm', 200)
                )
                velocity_series = [
                    mdot_to_velocity_m_s(m_dot, diameter_mm, rho_water)
                    for m_dot in flow_series
                ]
                diameter_m = diameter_mm / 1000.0
                pipe_length = pipe_config.get('length_m', 100)
                pressure_series = [
                    0.001 * pipe_length * (v ** 2) / diameter_m if diameter_m > 0 else 0
                    for v in velocity_series
                ]

                avg_flow = sum(flow_series) / n_timesteps if n_timesteps > 0 else 0
                max_velocity = max(velocity_series) if velocity_series else 0
                avg_velocity = sum(velocity_series) / n_timesteps if n_timesteps > 0 else 0
                max_pressure = max(pressure_series) if pressure_series else 0
                total_loss_mwh = sum(q_loss_series_kw) * dt_h / 1000  # kW*h -> MWh

                q_delivered_series_kw = [
                    heatd * service_frac  # kW
                    for heatd in heatd_series
                ]
                total_delivered_mwh = sum(q_delivered_series_kw) * dt_h / 1000

                pipe_res['flow_kg_s'] = flow_series
                pipe_res['Q_loss_supply_kw'] = q_loss_supply_kw_series
                pipe_res['Q_loss_return_kw'] = q_loss_return_kw_series
                pipe_res['velocity_m_s'] = velocity_series
                pipe_res['delta_p_total_bar'] = pressure_series
                pipe_res['avg_flow_kg_s'] = avg_flow
                pipe_res['max_velocity_m_s'] = max_velocity
                pipe_res['avg_velocity_m_s'] = avg_velocity
                pipe_res['max_delta_p_total_bar'] = max_pressure
                pipe_res['total_heat_loss_mwh'] = total_loss_mwh
                pipe_res['total_heat_delivered_mwh'] = total_delivered_mwh
                pipe_res['service_fraction'] = service_frac

                logger.info(
                    f"    {pipe_id}: m_dot_avg={avg_flow:.3f} kg/s, "
                    f"v_max={max_velocity:.4f} m/s, ΔP_max={max_pressure:.4f} bar, "
                    f"Q_loss={total_loss_mwh:.3f} MWh"
                )

        # Netzwerk-Gesamtverluste
        if brownfield_mode and hasattr(model, 'network_Q_loss_per_timestep'):
            total_heat_loss = sum(
                pyo.value(model.network_Q_loss_per_timestep[t]) * dt_h / 1000  # kW*h -> MWh
                for t in time_set
            )
            logger.info("  [Brownfield mode: Using network_Q_loss_per_timestep for losses]")

            total_heat_delivered = sum(
                pyo.value(model.heatd[t]) * dt_h / 1000
                for t in time_set
            )
        else:
            total_heat_delivered = sum(
                pipe_res['total_heat_delivered_mwh']
                for pipe_res in results['pipes'].values()
            )

            total_heat_loss = sum(
                pipe_res['total_heat_loss_mwh']
                for pipe_res in results['pipes'].values()
            )

        loss_percentage = (total_heat_loss / total_heat_delivered * 100) if total_heat_delivered > 0 else 0

        max_velocity = max(
            (pipe_res.get('max_velocity_m_s', 0) for pipe_res in results['pipes'].values()),
            default=0
        )

        total_pressure_drop = sum(
            pipe_res.get('max_delta_p_total_bar', 0)
            for pipe_res in results['pipes'].values()
        )

        avg_total_flow = sum(
            pipe_res.get('avg_flow_kg_s', 0)
            for pipe_res in results['pipes'].values()
        ) / max(len(results['pipes']), 1)

        pump_efficiency = 0.75
        density_water = 1000  # kg/m³

        pump_power_kw = (
            avg_total_flow * total_pressure_drop * 100000
        ) / (density_water * pump_efficiency * 1000)

        n_timesteps = len(list(time_set))
        operating_hours = n_timesteps * dt_h
        pump_energy_mwh = pump_power_kw * operating_hours / 1000

        results['summary'] = {
            'total_heat_delivered_mwh': total_heat_delivered,
            'total_heat_loss_mwh': total_heat_loss,
            'loss_percentage': loss_percentage,
            'total_pipe_length_m': sum(p['length_m'] for p in self.pipes.values()),
            'max_velocity_m_s': max_velocity,
            'total_pressure_drop_bar': total_pressure_drop,
            'pump_power_kw': pump_power_kw,
            'pump_energy_mwh': pump_energy_mwh,
            'pump_efficiency': pump_efficiency,
        }

        logger.info(f"  Total heat delivered: {total_heat_delivered:.1f} MWh")
        logger.info(f"  Total heat losses: {total_heat_loss:.1f} MWh ({loss_percentage:.2f}%)")
        logger.info(f"  Max velocity: {max_velocity:.2f} m/s")
        logger.info(f"  Total pressure drop: {total_pressure_drop:.2f} bar")
        logger.info(f"  Pump power: {pump_power_kw:.1f} kW ({pump_energy_mwh:.1f} MWh/period)")

        return results
    def export_for_dashboard(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format network results for dashboard visualization.

        Args:
            results: Network results from get_results()

        Returns:
            Dashboard-ready JSON structure
        """
        dashboard_data = {
            'metadata': results.get('metadata', {}),
            'network_topology': {
                'nodes': [],
                'pipes': []
            },
            'time_series': {
                'pipe_flows': {},
                'temperatures': {},
                'heat_losses': {}
            },
            'investment_results': {
                'pipe_upgrades': [],
                'total_investment_eur': 0,
                'annual_savings_eur': 0
            },
            'summary': results.get('summary', {})
        }

        # Format nodes for visualization
        for node_id, node_config in self.nodes.items():
            node_result = results['nodes'].get(node_id, {})

            dashboard_data['network_topology']['nodes'].append({
                'id': node_id,
                'name': node_config.get('name', node_id),
                'type': node_config.get('type'),
                'coordinates': node_config.get('coordinates', {}),
                'elevation_m': node_config.get('elevation_nn_m'),
                'avg_supply_temp_c': node_result.get('avg_supply_temp_c'),
                'avg_return_temp_c': node_result.get('avg_return_temp_c'),
                'total_demand_mwh': node_result.get('total_demand_mwh', 0),
                'network': node_config.get('network'),
            })

        # Format pipes for visualization
        for pipe_id, pipe_result in results['pipes'].items():
            pipe_config = self.pipes[pipe_id]

            dashboard_data['network_topology']['pipes'].append({
                'id': pipe_id,
                'from': pipe_result['from_node'],
                'to': pipe_result['to_node'],
                'length_m': pipe_result['length_m'],
                'diameter_current_mm': pipe_result['current_diameter_mm'],
                'diameter_optimized_mm': pipe_result['selected_diameter_mm'],
                'upgrade_recommended': pipe_result['upgrade_recommended'],
                'total_heat_loss_mwh': pipe_result['total_heat_loss_mwh'],
                'loss_percentage': pipe_result['loss_percentage'],
                'avg_flow_kg_s': pipe_result['avg_flow_kg_s'],
            })

            # Add time series
            dashboard_data['time_series']['pipe_flows'][pipe_id] = pipe_result['flow_kg_s']
            dashboard_data['time_series']['heat_losses'][pipe_id] = pipe_result['Q_loss_supply_kw']

        # Format node temperatures
        for node_id, node_result in results['nodes'].items():
            dashboard_data['time_series']['temperatures'][f'{node_id}_supply'] = node_result['T_supply_c']
            dashboard_data['time_series']['temperatures'][f'{node_id}_return'] = node_result['T_return_c']

        # Investment results
        for pipe_id, pipe_result in results['pipes'].items():
            if pipe_result.get('upgrade_recommended'):
                dashboard_data['investment_results']['pipe_upgrades'].append({
                    'pipe_id': pipe_id,
                    'current_diameter': pipe_result['current_diameter_mm'],
                    'recommended_diameter': pipe_result['selected_diameter_mm'],
                    'action': 'upgrade_diameter',
                    'cost_eur': 0  # Calculate from CAPEX if available
                })

        return dashboard_data

    def validate_hydraulics_post_optimization(
        self,
        heat_series: List[float],
        dt_h: float = 1.0
    ) -> Dict[str, Any]:
        """
        Post-optimization validation of hydraulic constraints.

        Args:
            heat_series: Time series of total heat demand (MW) from optimization
            dt_h: Time step duration in hours

        Returns:
            Dict with validation results.
        """
        if not self.network_enabled:
            return {'is_valid': True, 'violations': [], 'max_utilization': {}, 'recommendations': []}

        logger.info("=" * 60)
        logger.info("POST-OPTIMIZATION HYDRAULIC VALIDATION")
        logger.info("=" * 60)

        # Network parameters
        network_config = self.topology.get('network_parameters', {})
        parameters = self.parameters or {}

        supply_temp = network_config.get(
            'supply_temp_nominal_c',
            parameters.get('supply_temp_nominal_c', 120.0)
        )
        return_temp = network_config.get(
            'return_temp_nominal_c',
            parameters.get('return_temp_nominal_c', 55.0)
        )
        delta_t = supply_temp - return_temp  # K

        cp_water = network_config.get(
            'cp_water_kj_per_kg_k',
            parameters.get('cp_water_kj_per_kg_k', 4.186)
        )
        rho_water = network_config.get(
            'rho_water_kg_per_m3',
            parameters.get('rho_water_kg_per_m3', 983.0)
        )

        max_velocity_m_s = network_config.get(
            'max_velocity_m_s',
            parameters.get('max_velocity_m_s', 2.5)
        )

        default_pipe_fraction = parameters.get('default_pipe_demand_fraction', 0.2)

        violations = []
        max_utilization = {}
        recommendations = []

        for pipe_id, pipe_config in self.pipes.items():
            diameter_m = pipe_config.get('diameter_mm', 200) / 1000.0
            max_flow_m3_s = (3.14159 * (diameter_m / 2) ** 2) * max_velocity_m_s
            max_flow_kg_s = max_flow_m3_s * rho_water

            # Brownfield: vereinfachte Annahme über demand_fraction
            demand_fraction = pipe_config.get('demand_fraction', default_pipe_fraction)

            pipe_violations = []
            pipe_max_util = 0.0

            for t, heat_mw in enumerate(heat_series):
                # Q [MW] → m_dot [kg/s]
                # m_dot = Q[MW] * 1000 [kW/MW] / (cp[kJ/kg/K] * ΔT[K])
                if cp_water <= 0 or delta_t <= 0:
                    total_flow_kg_s = 0.0
                else:
                    total_flow_kg_s = heat_mw * 1000 / (cp_water * delta_t)

                pipe_flow_kg_s = total_flow_kg_s * demand_fraction

                utilization = pipe_flow_kg_s / max_flow_kg_s if max_flow_kg_s > 0 else 0
                pipe_max_util = max(pipe_max_util, utilization)

                if utilization > 1.0:
                    pipe_violations.append({
                        'timestep': t,
                        'heat_mw': heat_mw,
                        'required_flow_kg_s': pipe_flow_kg_s,
                        'max_flow_kg_s': max_flow_kg_s,
                        'utilization': utilization,
                        'excess_percent': (utilization - 1.0) * 100
                    })

            max_utilization[pipe_id] = {
                'max_utilization': pipe_max_util,
                'diameter_mm': pipe_config.get('diameter_mm', 200),
                'max_flow_kg_s': max_flow_kg_s,
                'is_overloaded': pipe_max_util > 1.0
            }

            if pipe_violations:
                violations.extend([{'pipe_id': pipe_id, **v} for v in pipe_violations])
                recommended_diameter = self._calculate_required_diameter(
                    max(v['required_flow_kg_s'] for v in pipe_violations),
                    max_velocity_m_s,
                    rho_water
                )
                recommendations.append({
                    'pipe_id': pipe_id,
                    'current_diameter_mm': pipe_config.get('diameter_mm', 200),
                    'recommended_diameter_mm': recommended_diameter,
                    'max_overload_percent': (pipe_max_util - 1.0) * 100,
                    'violation_hours': len(pipe_violations)
                })

        overloaded_pipes = sum(1 for m in max_utilization.values() if m['is_overloaded'])
        logger.info(f"  Analyzed {len(self.pipes)} pipes")
        logger.info(f"  Overloaded pipes: {overloaded_pipes}")
        logger.info(f"  Total violation hours: {len(violations)}")

        if overloaded_pipes > 0:
            logger.warning(f"  ⚠ {overloaded_pipes} pipes exceed hydraulic limits!")
            for rec in recommendations:
                logger.warning(
                    f"    - {rec['pipe_id']}: {rec['current_diameter_mm']}mm → "
                    f"{rec['recommended_diameter_mm']}mm "
                    f"(overload: {rec['max_overload_percent']:.1f}%)"
                )
        else:
            logger.info("  ✓ All pipes within hydraulic limits")

        is_valid = len(violations) == 0

        return {
            'is_valid': is_valid,
            'violations': violations,
            'max_utilization': max_utilization,
            'recommendations': recommendations,
            'summary': {
                'total_pipes': len(self.pipes),
                'overloaded_pipes': overloaded_pipes,
                'total_violation_hours': len(violations),
                'network_delta_t_k': delta_t,
                'max_velocity_m_s': max_velocity_m_s
            }
        }
    def _calculate_required_diameter(
        self,
        required_flow_kg_s: float,
        max_velocity_m_s: float,
        rho_water: float
    ) -> int:
        """Calculate minimum diameter (mm) for given flow and max velocity."""
        import math

        # m_dot = rho * A * v = rho * pi * (d/2)^2 * v
        # d = 2 * sqrt(m_dot / (rho * pi * v))
        area_m2 = required_flow_kg_s / (rho_water * max_velocity_m_s)
        diameter_m = 2 * math.sqrt(area_m2 / 3.14159)
        diameter_mm = diameter_m * 1000

        # Round up to standard pipe sizes
        standard_sizes = [50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800]
        for size in standard_sizes:
            if size >= diameter_mm:
                return size

        # If larger than standard, return calculated value rounded up
        return int(math.ceil(diameter_mm / 50) * 50)
