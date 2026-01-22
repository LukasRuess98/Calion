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

        # Store references
        pipe_components = {}
        node_components = {}

        # Global network parameters
        supply_temp_nominal = self.parameters.get('supply_temp_nominal_c', 90.0)
        return_temp = self.parameters.get('return_temp_nominal_c', 50.0)

        # Setup outdoor temperature (if available)
        use_outdoor_temp = self.config.get('thermal_network', {}).get('use_outdoor_temperature', False)
        if use_outdoor_temp and hasattr(model, 'outdoor_temp'):
            logger.info("Using time-varying outdoor temperature from model")
            outdoor_temp_series = [model.outdoor_temp[t] for t in time_set]
        else:
            # Create fixed ground temperature
            default_ground_temp = self.parameters.get('ground_temp_default_c', 10.0)
            model.outdoor_temp = {t: default_ground_temp for t in time_set}
            outdoor_temp_series = [default_ground_temp for _ in time_set]
            logger.info(f"Using fixed ground temperature: {default_ground_temp}°C")

        # ========================================
        # HEATING CURVE (Heizkurve) - Time-varying supply temperature
        # ========================================
        heating_curve_config_raw = self.parameters.get('heating_curve', {})
        # Resolve profile reference (e.g., "profile: standard_dh" -> full parameters)
        heating_curve_config = resolve_heating_curve_profile(
            heating_curve_config_raw,
            config_dir=self.config_dir,
        )
        use_heating_curve = heating_curve_config.get('enabled', False)

        if use_heating_curve and use_outdoor_temp:
            # Extract heating curve parameters
            T_supply_min = heating_curve_config.get('T_supply_min_c', 80.0)
            T_supply_max = heating_curve_config.get('T_supply_max_c', 120.0)
            T_outdoor_high = heating_curve_config.get('T_outdoor_high_c', 20.0)
            T_outdoor_low = heating_curve_config.get('T_outdoor_low_c', -10.0)

            # Calculate time-varying supply temperatures
            supply_temp_series = calculate_supply_temperature_series(
                T_outdoor_series=outdoor_temp_series,
                T_supply_min_c=T_supply_min,
                T_supply_max_c=T_supply_max,
                T_outdoor_high_c=T_outdoor_high,
                T_outdoor_low_c=T_outdoor_low,
            )

            # Store as model attribute for later use
            model.supply_temp_series = {t: supply_temp_series[i] for i, t in enumerate(time_set)}

            # Log heating curve info
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

            # Use nominal for static calculations (average or design point)
            supply_temp = sum(supply_temp_series) / len(supply_temp_series)
            logger.info(f"    Average supply temp: {supply_temp:.1f}°C")
        else:
            # Fixed supply temperature (original behavior)
            supply_temp = supply_temp_nominal
            model.supply_temp_series = {t: supply_temp for t in time_set}
            if use_heating_curve and not use_outdoor_temp:
                logger.warning("  Heating curve enabled but outdoor temperature not available!")
                logger.warning("  Set 'use_outdoor_temperature: true' in config to enable heating curve.")

        # ========================================
        # PHASE 1: Attach all pipes
        # ========================================

        logger.info(f"\nAttaching {len(self.pipes)} pipe pairs...")

        # Check brownfield mode - defaults to True (simplified fixed-topology mode)
        brownfield_mode = self.config.get('thermal_network', {}).get('brownfield_mode', True)
        self.brownfield_mode = brownfield_mode  # Store as instance variable for get_results
        if brownfield_mode:
            logger.info("  [Brownfield mode: fixed topology with physical losses (Q = U×L×ΔT)]")

        for pipe_id, pipe_config in self.pipes.items():
            # Enrich pipe config with global parameters
            enriched_config = {
                **pipe_config,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_nominal_c': return_temp,
                'use_outdoor_temperature': use_outdoor_temp,
                'pipe_catalog': self.pipe_catalog,
                'brownfield_mode': brownfield_mode,
                **self.parameters
            }

            # Validate and attach
            PipePairBlock.validate_config(enriched_config)
            pipe_result = PipePairBlock.attach(model, time_set, enriched_config, buses)

            pipe_components[pipe_id] = pipe_result

            logger.info(
                f"  ✓ {pipe_id}: {pipe_config['from_node']} → {pipe_config['to_node']} "
                f"({pipe_config['length_m']}m)"
            )

        # ========================================
        # PHASE 2: Attach all nodes
        # ========================================

        logger.info(f"\nAttaching {len(self.nodes)} thermal nodes...")

        for node_id, node_config in self.nodes.items():
            # Enrich node config
            enriched_config = {
                **node_config,
                'id': node_id,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_c': return_temp,
                'brownfield_mode': brownfield_mode,
            }

            # Validate and attach
            ThermalNodeBlock.validate_config(enriched_config)
            node_result = ThermalNodeBlock.attach(
                model, time_set, enriched_config, buses, pipe_components
            )

            node_components[node_id] = node_result

            node_type = node_config.get('type', 'unknown')
            logger.info(f"  ✓ {node_id} ({node_type})")

        # ========================================
        # PHASE 3: Connect pipes to nodes
        # ========================================

        logger.info(f"\nConnecting pipes to nodes...")

        for pipe_id, pipe_comp in pipe_components.items():
            from_node = pipe_comp['from_node']
            to_node = pipe_comp['to_node']

            # In BROWNFIELD mode: Skip temperature linking constraints!
            # PHASE 3b will fix all temperatures directly to avoid conflicts.
            # In greenfield mode: Create linking constraints for temperature propagation.

            if not brownfield_mode:
                # Link pipe inlet temperature to from_node supply temperature
                if from_node in node_components:
                    from_node_comp = node_components[from_node]
                    pipe_T_supply_in = pipe_comp['T_supply_in']
                    node_T_supply = from_node_comp['T_supply']

                    # Create equality constraint
                    constraint_name = f"link_pipe_{pipe_id}_inlet_to_node_{from_node}"

                    def link_rule(m, t):
                        if isinstance(node_T_supply, pyo.Param):
                            return pipe_T_supply_in[t] == pyo.value(node_T_supply[t])
                        else:
                            return pipe_T_supply_in[t] == node_T_supply[t]

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=link_rule))
                    logger.info(f"    Linked {pipe_id} inlet ← {from_node} supply temp")

                # Link pipe outlet to_node supply temperature (for consumer/junction nodes)
                if to_node in node_components:
                    to_node_comp = node_components[to_node]
                    if to_node_comp['type'] in ['consumer', 'junction']:
                        # The node's supply temp is set by pipe(s) feeding into it
                        # This is handled by node's temperature mixing constraint
                        pass

                # Link return temperatures
                # Pipe return inlet gets temperature from to_node
                if to_node in node_components:
                    to_node_comp = node_components[to_node]
                    pipe_T_return_in = pipe_comp['T_return_in']
                    node_T_return = to_node_comp['T_return']

                    constraint_name = f"link_pipe_{pipe_id}_return_to_node_{to_node}"

                    def return_link_rule(m, t):
                        if isinstance(node_T_return, pyo.Param):
                            return pipe_T_return_in[t] == pyo.value(node_T_return[t])
                        else:
                            return pipe_T_return_in[t] == node_T_return[t]

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=return_link_rule))
                    logger.info(f"    Linked {pipe_id} return ← {to_node} return temp")
            else:
                logger.info(f"    {pipe_id}: skipping temp links (brownfield - handled in PHASE 3b)")

            # Track return pipes for each plant node (for later mixing constraint)
            if from_node in node_components:
                from_node_comp = node_components[from_node]
                if from_node_comp['type'] == 'plant':
                    if 'return_pipes' not in from_node_comp:
                        from_node_comp['return_pipes'] = []
                    from_node_comp['return_pipes'].append(pipe_id)

        # ========================================
        # PHASE 3b: BROWNFIELD Temperature Fixing
        # ========================================
        # In brownfield mode, fix temperatures based on network topology:
        # - Plant nodes: T_supply = supply_temp (from heating curve if enabled)
        # - Pipes from plants: T_supply_in = supply_temp (time-varying if heating curve)
        # - Pipes between consumers: T_supply_in = T_supply_out of upstream pipe
        # This avoids the conflict where all pipes had same inlet temp

        if brownfield_mode:
            logger.info(f"\nFixing temperatures for brownfield mode...")

            # ============================================================
            # PIPE-SPECIFIC TEMPERATURE DROPS (Physics-based calculation)
            # ============================================================
            # Options:
            # 1. use_physics_temp_drop: True (default) - calculate from U, L, m_dot
            # 2. brownfield_temp_drop_per_pipe_c: fallback constant [°C]
            # ============================================================
            use_physics_temp_drop = self.parameters.get('use_physics_temp_drop', True)
            default_temp_drop = self.parameters.get('brownfield_temp_drop_per_pipe_c', 1.0)

            # Calculate pipe-specific temperature drops if enabled
            if use_physics_temp_drop and hasattr(model, 'heatd'):
                # Estimate total heat demand from first timestep
                first_t = list(time_set)[0]
                total_demand_mw = pyo.value(model.heatd[first_t]) if hasattr(model, 'heatd') else 10.0
                total_demand_kw = total_demand_mw * 1000

                # Build pipes config for calculation
                pipes_for_calc = {}
                for pipe_id in self.pipes:
                    pipe_cfg = self.pipes[pipe_id]
                    pipes_for_calc[pipe_id] = {
                        'length_m': pipe_cfg.get('length_m', 100),
                        'u_value_w_per_m_k': pipe_cfg.get('u_value_w_per_m_k', 0.5),
                    }

                # Calculate physics-based temperature drops
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

            # Check if using time-varying supply temperatures (heating curve)
            supply_temp_dict = getattr(model, 'supply_temp_series', None)
            if supply_temp_dict is None:
                supply_temp_dict = {t: supply_temp for t in time_set}

            # Pre-calculate pipe hop counts for temperature cascade
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

                # Get pipe-specific temperature drop (physics-based or constant fallback)
                if pipe_temp_drops and pipe_id in pipe_temp_drops:
                    supply_drop = pipe_temp_drops[pipe_id]['supply_drop_c']
                    return_drop = pipe_temp_drops[pipe_id]['return_drop_c']
                else:
                    supply_drop = default_temp_drop
                    return_drop = default_temp_drop

                # Cumulative supply drop for cascaded pipes (sum of upstream drops)
                cumulative_supply_drop = 0.0
                if hop_count > 0 and pipe_temp_drops:
                    # Sum up drops from upstream pipes (simplified: use average)
                    upstream_drops = [d['supply_drop_c'] for d in pipe_temp_drops.values()]
                    avg_upstream_drop = sum(upstream_drops) / len(upstream_drops) if upstream_drops else default_temp_drop
                    cumulative_supply_drop = avg_upstream_drop * hop_count
                else:
                    cumulative_supply_drop = default_temp_drop * hop_count

                # === SUPPLY TEMPERATURE (time-varying with heating curve) ===
                for t in time_set:
                    base_supply_temp = supply_temp_dict[t]

                    if from_node_type == 'plant':
                        # Pipe from plant: inlet at supply temp (from heating curve)
                        inlet_temp_t = base_supply_temp
                        outlet_temp_t = base_supply_temp - supply_drop
                    else:
                        # Pipe from consumer/junction: cascade temperature drop
                        inlet_temp_t = base_supply_temp - cumulative_supply_drop
                        outlet_temp_t = inlet_temp_t - supply_drop

                    T_supply_in[t].fix(inlet_temp_t)
                    T_supply_out[t].fix(outlet_temp_t)

                # Log summary (using average if time-varying)
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

                # === RETURN TEMPERATURE (fixed, not affected by heating curve) ===
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

                # Fix return temperatures (constant over time)
                for t in time_set:
                    T_return_in[t].fix(pipe_return_in_temp)
                    T_return_out[t].fix(pipe_return_out_temp)

            logger.info(f"  ✓ Fixed temperatures for {len(pipe_components)} pipes")
            if use_heating_curve:
                logger.info(f"    (Using time-varying supply temperatures from heating curve)")

            # Also fix NODE temperatures in brownfield mode!
            logger.info(f"\nFixing node temperatures for brownfield mode...")

            for node_id, node_comp in node_components.items():
                node_type = node_comp['type']
                node_prefix = node_id.upper().replace('-', '_')

                if node_type == 'plant':
                    # Plant return needs fixing
                    T_return = node_comp['T_return']
                    if isinstance(T_return, pyo.Var):
                        for t in time_set:
                            T_return[t].fix(return_temp)
                        logger.info(f"    {node_id}: Fixed return temp to {return_temp}°C")

                elif node_type == 'consumer':
                    # Consumer: T_supply from incoming pipe
                    T_supply = node_comp['T_supply']
                    incoming_pipes = node_comp.get('incoming_pipes', [])

                    if incoming_pipes and isinstance(T_supply, pyo.Var):
                        # Use the outlet temperature of the first incoming pipe
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
                    # Junction: fix both temps
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

        # ========================================
        # PHASE 4: Connect demands to pipes
        # ========================================

        logger.info(f"\nConnecting consumer demands to pipes...")

        # In brownfield mode: Use simplified flow linking based on demand fractions
        if brownfield_mode:
            logger.info("  [Brownfield mode: using simplified demand-based flow linking]")

            # Calculate service fraction for each pipe, accounting for multi-source consumers
            pipe_service_fractions = {}

            # First, get consumer info (demand fraction, number of incoming pipes)
            consumer_info = {}
            for node_id, node_comp in node_components.items():
                if node_comp['type'] == 'consumer':
                    incoming = node_comp.get('incoming_pipes', [])
                    consumer_info[node_id] = {
                        'demand_fraction': node_comp.get('demand_fraction', 0.0),
                        'num_sources': max(1, len(incoming)),
                        'incoming_pipes': incoming
                    }

            # For each pipe, calculate total downstream demand fraction
            def get_downstream_demand(pipe_id, visited=None):
                """Recursively calculate total demand fraction served by this pipe."""
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

                # Demand at destination node (split among incoming pipes)
                if to_node in consumer_info:
                    info = consumer_info[to_node]
                    local_demand = info['demand_fraction'] * split_factor
                else:
                    local_demand = 0.0

                # Demand from outgoing pipes (downstream), auch gesplittet
                outgoing = node_comp.get('outgoing_pipes', [])
                downstream_demand = sum(
                    get_downstream_demand(out_pipe, visited.copy())
                    for out_pipe in outgoing
                ) * split_factor

                return local_demand + downstream_demand

            for pipe_id in pipe_components.keys():
                pipe_service_fractions[pipe_id] = get_downstream_demand(pipe_id)
                logger.info(
                    f"    {pipe_id}: serves {pipe_service_fractions[pipe_id]*100:.1f}% of demand"
                )

            # Verify total adds up (sollte ~100% über alle Plant-Outgoing-Pipes sein)
            plant_pipe_total = sum(
                pipe_service_fractions.get(pid, 0)
                for pid, pc in pipe_components.items()
                if node_components.get(pc.get('from_node'), {}).get('type') == 'plant'
            )
            logger.info(
                f"  Total from plant pipes: {plant_pipe_total*100:.1f}% (should be ~100%)"
            )

            # Flow-Parameter für Brownfield
            cp_water = self.parameters.get('cp_water_kj_per_kg_k', 4.186)  # kJ/(kg·K)
            delta_T = supply_temp - return_temp  # K

            logger.info(f"  Creating brownfield flow constraints (delta_T = {delta_T}K)...")
            logger.info(f"  Calculating physical network losses (Q = U × L × ΔT)...")

            ground_temp = self.parameters.get('ground_temp_default_c', 10.0)  # °C

            total_network_loss_mw = 0.0
            pipe_losses = {}

            # Physikalische Verluste pro Leitung berechnen (Vorlauf + Rücklauf)
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

            # Store data for later use in PHASE 6 and get_results()
            model._brownfield_total_loss_mw = total_network_loss_mw  # Constant loss [MW]
            model._brownfield_pipe_losses = pipe_losses  # Per-pipe breakdown
            model._brownfield_pipe_service_fractions = pipe_service_fractions  # For flow calc
            model._brownfield_delta_T = delta_T  # Temperature difference for flow calc
            model._brownfield_cp_water = cp_water  # Specific heat capacity
            model._brownfield_ground_temp = ground_temp

        # Greenfield: vollständige Kopplung zwischen Pipes und Demand
        for node_id, node_comp in node_components.items():
            if node_comp['type'] == 'consumer' and not brownfield_mode:
                incoming_pipes = node_comp.get('incoming_pipes', [])
                outgoing_pipes = node_comp.get('outgoing_pipes', [])

                has_outgoing = len(outgoing_pipes) > 0

                if len(incoming_pipes) == 1 and not has_outgoing:
                    pipe_id = incoming_pipes[0]
                    pipe_comp = pipe_components[pipe_id]

                    pipe_m_dot = pipe_comp['m_dot']
                    node_m_dot = node_comp['m_dot_demand']

                    constraint_name = f"link_demand_{node_id}_to_pipe_{pipe_id}"

                    def demand_flow_rule(m, t):
                        return pipe_m_dot[t] == node_m_dot[t]

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=demand_flow_rule))

                    pipe_Q_delivered = pipe_comp['Q_delivered']
                    node_Q_demand = node_comp['Q_demand']

                    constraint_name_q = f"link_heat_demand_{node_id}_to_pipe_{pipe_id}"

                    def demand_heat_rule(m, t):
                        if isinstance(node_Q_demand, pyo.Param):
                            return pipe_Q_delivered[t] == pyo.value(node_Q_demand[t])
                        else:
                            return pipe_Q_delivered[t] == node_Q_demand[t]

                    setattr(model, constraint_name_q, pyo.Constraint(time_set, rule=demand_heat_rule))

                    logger.info(f"  ✓ {node_id} demand ← pipe {pipe_id}")

                elif len(incoming_pipes) == 1 and has_outgoing:
                    pipe_id = incoming_pipes[0]
                    pipe_comp = pipe_components[pipe_id]
                    pipe_m_dot = pipe_comp['m_dot']
                    node_m_dot = node_comp['m_dot_demand']

                    constraint_name = f"link_demand_{node_id}_passthrough_flow"

                    def passthrough_flow_rule(m, t, _pipe=pipe_m_dot, _node=node_m_dot, _out=outgoing_pipes):
                        outgoing_flow = sum(
                            pipe_components[pid]['m_dot'][t]
                            for pid in _out
                        )
                        return _pipe[t] == _node[t] + outgoing_flow

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=passthrough_flow_rule))

                    node_Q_demand = node_comp['Q_demand']
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

                        constraint_name_flow = f"link_demand_{node_id}_multi_passthrough_flow"

                        def multi_passthrough_flow_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes, _node=node_m_dot):
                            total_inflow = sum(
                                pipe_components[pid]['m_dot'][t]
                                for pid in _in
                            )
                            total_outflow = sum(
                                pipe_components[pid]['m_dot'][t]
                                for pid in _out
                            )
                            return total_inflow == _node[t] + total_outflow

                        setattr(model, constraint_name_flow, pyo.Constraint(time_set, rule=multi_passthrough_flow_rule))

                        logger.info(f"    ← incoming: {', '.join(incoming_pipes)}")
                        logger.info(f"    → outgoing: {', '.join(outgoing_pipes)}")

                    else:
                        logger.info(
                            f"  ✓ {node_id} has {len(incoming_pipes)} incoming pipes - "
                            f"creating multi-pipe flow balance"
                        )

                        constraint_name_flow = f"link_demand_{node_id}_multi_pipe_flow"

                        def multi_pipe_flow_rule(m, t, _incoming=incoming_pipes, _node=node_m_dot):
                            total_inflow = sum(
                                pipe_components[pid]['m_dot'][t]
                                for pid in _incoming
                            )
                            return total_inflow == _node[t]

                        setattr(model, constraint_name_flow, pyo.Constraint(time_set, rule=multi_pipe_flow_rule))

                        constraint_name_heat = f"link_demand_{node_id}_multi_pipe_heat"

                        def multi_pipe_heat_rule(m, t, _incoming=incoming_pipes, _Q=node_Q_demand):
                            total_heat = sum(
                                pipe_components[pid]['Q_delivered'][t]
                                for pid in _incoming
                            )
                            if isinstance(_Q, pyo.Param):
                                return total_heat >= pyo.value(_Q[t]) * 0.99
                            else:
                                return total_heat >= _Q[t] * 0.99

                        setattr(model, constraint_name_heat, pyo.Constraint(time_set, rule=multi_pipe_heat_rule))

                        logger.info(f"    ← pipes: {', '.join(incoming_pipes)}")

                else:
                    logger.warning(f"  ⚠ {node_id} has no incoming pipes!")

        # ========================================
        # PHASE 4b: Junction flow balance
        # ========================================

        logger.info(f"\nSetting up junction flow balance constraints...")

        if brownfield_mode:
            logger.info("  [Brownfield mode: junction flows determined by brownfield_flow_rule]")
        else:
            for node_id, node_comp in node_components.items():
                if node_comp['type'] == 'junction':
                    incoming_pipes = node_comp.get('incoming_pipes', [])
                    outgoing_pipes = node_comp.get('outgoing_pipes', [])

                    if not incoming_pipes or not outgoing_pipes:
                        logger.warning(
                            f"  ⚠ Junction {node_id} incomplete: "
                            f"{len(incoming_pipes)} in, {len(outgoing_pipes)} out"
                        )
                        continue

                    constraint_name = f"junction_{node_id}_flow_balance"

                    def junction_flow_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes):
                        total_in = sum(
                            pipe_components[pid]['m_dot'][t]
                            for pid in _in
                        )
                        total_out = sum(
                            pipe_components[pid]['m_dot'][t]
                            for pid in _out
                        )
                        return total_in == total_out

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=junction_flow_rule))
                    logger.info(
                        f"  ✓ {node_id}: {len(incoming_pipes)} in = {len(outgoing_pipes)} out"
                    )

        # ========================================
        # PHASE 5: Plant return temperature mixing
        # ========================================

        logger.info(f"\nSetting up plant return temperature constraints...")

        for node_id, node_comp in node_components.items():
            if node_comp['type'] == 'plant':
                return_pipes = node_comp.get('return_pipes', [])
                node_T_return = node_comp['T_return']

                if len(return_pipes) == 0:
                    logger.warning(f"  ⚠ Plant {node_id} has no return pipes!")
                elif len(return_pipes) == 1:
                    pipe_id = return_pipes[0]
                    pipe_comp = pipe_components[pipe_id]
                    pipe_T_return_out = pipe_comp['T_return_out']
                    pipe_m_dot = pipe_comp['m_dot']

                    if brownfield_mode:
                        logger.info(
                            f"  ✓ {node_id} return temp fixed (brownfield - skipping link to pipe {pipe_id})"
                        )
                    else:
                        constraint_name = f"plant_{node_id}_return_temp_single"

                        def single_return_rule(m, t):
                            return node_T_return[t] == pipe_T_return_out[t]

                        setattr(model, constraint_name, pyo.Constraint(time_set, rule=single_return_rule))
                        logger.info(f"  ✓ {node_id} return temp ← pipe {pipe_id}")

                else:
                    if brownfield_mode:
                        logger.info(
                            f"  ✓ {node_id} return temp fixed to {return_temp}°C (brownfield mode)"
                        )
                        for t in time_set:
                            node_T_return[t].fix(return_temp)
                    else:
                        constraint_name = f"plant_{node_id}_return_temp_mixing"

                        def multi_return_rule(m, t):
                            total_return_flow = 0
                            weighted_temp = 0

                            for p_id in return_pipes:
                                pipe_comp = pipe_components[p_id]
                                pipe_m_dot = pipe_comp['m_dot']
                                pipe_T_return_out = pipe_comp['T_return_out']

                                total_return_flow += pipe_m_dot[t]
                                weighted_temp += pipe_T_return_out[t] * pipe_m_dot[t]

                            return node_T_return[t] * total_return_flow == weighted_temp

                        setattr(model, constraint_name, pyo.Constraint(time_set, rule=multi_return_rule))
                        logger.info(
                            f"  ✓ {node_id} return temp mixing ← {len(return_pipes)} pipes "
                            f"(BILINEAR - needs QP solver)"
                        )

        # ========================================
        # PHASE 5b: Plant-to-Network Heat Linkage
        # ========================================

        logger.info(f"\nSetting up plant-to-network heat linkage...")

        plant_outgoing_pipes = []
        for node_id, node_comp in node_components.items():
            if node_comp['type'] == 'plant':
                outgoing = node_comp.get('outgoing_pipes', [])
                plant_outgoing_pipes.extend(outgoing)
                logger.info(f"  Plant {node_id}: {len(outgoing)} outgoing pipes")

        if plant_outgoing_pipes and hasattr(model, 'heatd'):
            network_delta_t = supply_temp - return_temp  # K
            cp_water = 4.186  # kJ/(kg·K)

            logger.info(
                f"  Network ΔT: {network_delta_t}K, {len(plant_outgoing_pipes)} plant pipes total"
            )

            logger.info(
                "  ℹ Network heat linkage: relying on system-level heat balance (no redundant constraint)"
            )
        else:
            logger.warning("  ⚠ No plant outgoing pipes or heatd not found - skipping linkage")

        # ========================================
        # PHASE 6: Calculate network costs
        # ========================================

        logger.info(f"\nCalculating network costs...")

        if hasattr(model, 'pipe_capex_costs'):
            total_pipe_capex = sum(model.pipe_capex_costs.values())
            logger.info(f"  Total pipe CAPEX (annualized): {total_pipe_capex}")
        else:
            total_pipe_capex = 0

        total_heat_loss_expr = sum(
            sum(pipe_comp['Q_loss_supply'][t] + pipe_comp['Q_loss_return'][t] for t in time_set)
            for pipe_comp in pipe_components.values()
        )

        # ========================================
        # CRITICAL: Create per-timestep network heat losses
        # ========================================

        logger.info(f"\nCreating per-timestep network heat losses...")

        # Bounds für network_Q_loss_per_timestep aus Parametern
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

        # In brownfield mode, nutze physikalische Referenzverluste und skaliere mit der Last
        if brownfield_mode and hasattr(model, '_brownfield_total_loss_mw'):
            total_loss_mw = model._brownfield_total_loss_mw  # Referenzverlust bei Q_ref
            loss_model = self.parameters.get('brownfield_loss_model', 'constant')
            ref_heat_mw = self.parameters.get('brownfield_loss_ref_heat_mw', None)

            # heatd[t] ist im Modell in kW
            if (
                loss_model == 'demand_proportional'
                and hasattr(model, 'heatd')
                and ref_heat_mw is not None
                and ref_heat_mw > 0
            ):
                def brownfield_network_loss_rule(m, t):
                    # heatd[t] [kW] → [MW] und Skalierung mit Referenzlast
                    return m.network_Q_loss_per_timestep[t] == total_loss_mw * (m.heatd[t] / 1000.0) / ref_heat_mw

                model.brownfield_network_loss = pyo.Constraint(
                    time_set, rule=brownfield_network_loss_rule
                )
                logger.info(
                    f"  ✓ Brownfield (demand_proportional): "
                    f"network_Q_loss_per_timestep scaled with heatd / {ref_heat_mw} MW"
                )
            else:
                # Fallback: konstante Verluste wie bisher
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
            # Greenfield: network_Q_loss_per_timestep[t] = Summe aus Pipe-Verlustvariablen
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
