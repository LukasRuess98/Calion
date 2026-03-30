"""
Network Manager for Thermal District Heating Networks
======================================================

This module coordinates pipe and node components for district heating network
optimization using a single unified physics model.

Key Concepts:
-------------
- **Always network-based**: even "no network" is just one node with all components attached
- **No special cases**: every topology goes through the same code path
- **Nodes** handle: mass balance, enthalpy balance, pressure variables (T and P are
  *calculated*, not fixed parameters)
- **Pipes** handle: temperature loss, pressure loss (Darcy-Weisbach), and transport
  time delay (linearised with 3-bucket SOS2 binary selection)
- **Single-node fallback**: when no pipes are configured, a virtual `_network_root`
  node is auto-created so calling code never needs to check `network_enabled`

Network Components:
-------------------
- **Nodes**: Producers (heat sources), Consumers (heat sinks), Junctions
- **Pipes**: Supply and return pipes connecting nodes, characterised by:
  - length_m: Pipe length [m]
  - current_diameter_supply_mm: Pipe diameter [mm]
  - u_value_supply/return_w_per_m_k: Heat loss coefficients [W/(m·K)]

Configuration (topology.yaml):
--------------------------------
```yaml
nodes:
  - id: plant_node
    type: producer
    components: [HKW, HP1]
  - id: consumer_A
    type: consumer
    demand_fraction: 0.6
  - id: junction_1
    type: junction

pipes:
  - id: pipe_1
    from_node: plant_node
    to_node: consumer_A
    length_m: 500
    current_diameter_supply_mm: 200
```

Single-node fallback (no `pipes:` key):
  All components → one implicit "_network_root" node.

Usage:
------
    >>> nm = NetworkManager(config, config_dir=Path('.'))
    >>> nm.attach_to_model(model, config, time_set)
    >>> results = nm.get_results(model, config, time_set)

Author: CALION Development Team
"""

import logging
from pathlib import Path
from typing import Any

import yaml

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

from ..utils.config_utils import resolve_heating_curve_profile
from .blocks.pipe_pair import PipePairBlock
from .blocks.thermal_node import ThermalNodeBlock
from .network_physics import (
    calculate_supply_temperature_series,
    get_heating_curve_parameters,
)

logger = logging.getLogger(__name__)


class NetworkManager:
    """
    Manages thermal network components and topology.

    Responsibilities:
    - Parse network YAML/Excel configuration
    - Create and attach pipe and node components
    - Connect network to heat sources and demands
    - Coordinate constraints between components
    - Export results for dashboard
    """

    def __init__(self, config: dict[str, Any], config_dir: Path | None = None):
        """
        Initialize network manager.

        Args:
            config: Full configuration dict containing 'thermal_network' section
            config_dir: Base directory for resolving relative topology file paths
        """
        self.config = config
        self.config_dir = config_dir or Path.cwd()

        self.nodes = {}        # Dict[str, dict] — node configurations
        self.pipes = {}        # Dict[str, dict] — pipe configurations
        self.pipe_catalog = {} # Dict[str, dict] — available pipe types
        self.topology = {}     # Dict — raw topology data from file
        self.parameters = {}   # Dict — network parameters (temps, pressures)

        self.network_enabled = config.get('thermal_network', {}).get('enabled', False)

        if self.network_enabled:
            self._load_network_topology()

    # ── Path helpers ───────────────────────────────────────────────────────────

    def _find_repo_root(self, start_path: Path | None = None) -> Path:
        """Find repository root by searching for .git directory."""
        if start_path is None:
            start_path = Path.cwd()
        current = start_path.resolve()
        for _ in range(10):
            if (current / '.git').exists():
                return current
            parent = current.parent
            if parent == current:
                break
            current = parent
        return start_path

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve a path relative to repo root or config_dir."""
        path = Path(path_str)
        if path.is_absolute():
            return path

        repo_relative = self._find_repo_root() / path
        if repo_relative.exists():
            return repo_relative

        config_relative = self.config_dir / path
        if config_relative.exists():
            return config_relative

        logger.warning(f"Path not found. Tried:\n  - {repo_relative}\n  - {config_relative}")
        return repo_relative

    # ── Topology loading ───────────────────────────────────────────────────────

    def _load_network_topology(self):
        """Load network topology from YAML file, Excel file, or inline config."""
        network_config = self.config.get('thermal_network', {})
        topology_file = network_config.get('topology_file')
        topology_excel = network_config.get('topology_excel')

        if topology_excel:
            excel_path = self._resolve_path(topology_excel)
            logger.info(f"Loading network topology from Excel: {excel_path}")
            try:
                from calion.io.network_loader import load_network_from_excel
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
                with open(topology_path, encoding="utf-8") as f:
                    topology_data = yaml.safe_load(f)
            except FileNotFoundError:
                logger.error("=" * 70)
                logger.error("THERMAL NETWORK ERROR: Topology file not found!")
                logger.error(f"  Expected: {topology_path}")
                logger.error(f"  Config value: {topology_file}")
                logger.error(f"  Config dir: {self.config_dir}")
                logger.error(f"  Repo root: {self._find_repo_root()}")
                logger.error("=" * 70)
                self.network_enabled = False
                return
            except yaml.YAMLError as e:
                logger.error(f"Error parsing network YAML file: {e}")
                self.network_enabled = False
                return
        else:
            topology_data = network_config

        self.topology = topology_data
        self.parameters = topology_data.get('parameters', {})
        self.pipe_catalog = topology_data.get('pipe_catalog', {})

        self._parse_nodes(topology_data)
        self._parse_pipes(topology_data)

        logger.info(f"Loaded network: {len(self.nodes)} nodes, {len(self.pipes)} pipes")

    def _parse_nodes(self, topology_data: dict):
        """Parse node definitions from topology (all supported formats).

        Supported formats:
        1. Unified list:  nodes: [{id: ..., type: ...}, ...]
        2. Nested dict:   networks.{net_id}.nodes.{node_id}: {type: ...}
           (stadtbach network_topology.yaml uses this format)
        3. Legacy lists:  production_plants / pump_stations / consumer_zones
        """
        # Format 1: flat nodes list with explicit 'id' field
        nodes_list = topology_data.get('nodes', [])
        if isinstance(nodes_list, list):
            for node_cfg in nodes_list:
                node_id = node_cfg.get('id') or node_cfg.get('node_id')
                if node_id:
                    self.nodes[node_id] = {**node_cfg, 'id': node_id}
        elif isinstance(nodes_list, dict):
            # Format 2a: nodes is itself a dict-of-dicts (key = node_id)
            for node_id, node_cfg in nodes_list.items():
                if node_cfg and isinstance(node_cfg, dict):
                    self.nodes[node_id] = {**node_cfg, 'id': node_id}

        # Format 2b: networks.{network_id}.nodes dict-of-dicts (stadtbach style)
        for net_data in topology_data.get('networks', {}).values():
            if not isinstance(net_data, dict):
                continue
            nodes_in_net = net_data.get('nodes', {})
            if isinstance(nodes_in_net, dict):
                for node_id, node_cfg in nodes_in_net.items():
                    if node_cfg and isinstance(node_cfg, dict):
                        self.nodes[node_id] = {**node_cfg, 'id': node_id}
            elif isinstance(nodes_in_net, list):
                for node_cfg in nodes_in_net:
                    node_id = node_cfg.get('id') or node_cfg.get('node_id')
                    if node_id:
                        self.nodes[node_id] = {**node_cfg, 'id': node_id}

        # Format 3: legacy separate lists per type
        for plant_cfg in topology_data.get('production_plants', []):
            node_id = plant_cfg['node_id']
            self.nodes[node_id] = {**plant_cfg, 'id': node_id, 'type': 'producer'}

        for pump_cfg in topology_data.get('pump_stations', []):
            node_id = pump_cfg['node_id']
            self.nodes[node_id] = {**pump_cfg, 'id': node_id, 'type': 'junction'}

        for consumer_cfg in topology_data.get('consumer_zones', []):
            node_id = consumer_cfg['node_id']
            self.nodes[node_id] = {**consumer_cfg, 'id': node_id, 'type': 'consumer'}

    def _parse_pipes(self, topology_data: dict):
        """Parse pipe definitions from topology.

        Supported formats:
        1. Flat list:   pipes: [{id: ..., from_node: ..., to_node: ...}, ...]
        2. Nested dict: networks.{net_id}.pipes.{pipe_id}: {from_node: ..., to_node: ...}
        3. Dict-of-dicts at top level: pipes.{pipe_id}: {from_node: ..., to_node: ...}
        """
        pipes_val = topology_data.get('pipes', [])
        if isinstance(pipes_val, list):
            for pipe_cfg in pipes_val:
                pipe_id = pipe_cfg.get('id')
                if pipe_id:
                    self.pipes[pipe_id] = pipe_cfg
        elif isinstance(pipes_val, dict):
            for pipe_id, pipe_cfg in pipes_val.items():
                if pipe_cfg and isinstance(pipe_cfg, dict):
                    self.pipes[pipe_id] = {**pipe_cfg, 'id': pipe_id}

        # Nested under 'networks' (stadtbach style)
        for net_data in topology_data.get('networks', {}).values():
            if not isinstance(net_data, dict):
                continue
            pipes_in_net = net_data.get('pipes', {})
            if isinstance(pipes_in_net, dict):
                for pipe_id, pipe_cfg in pipes_in_net.items():
                    if pipe_cfg and isinstance(pipe_cfg, dict):
                        self.pipes[pipe_id] = {**pipe_cfg, 'id': pipe_id}
            elif isinstance(pipes_in_net, list):
                for pipe_cfg in pipes_in_net:
                    pipe_id = pipe_cfg.get('id')
                    if pipe_id:
                        self.pipes[pipe_id] = pipe_cfg

    # ── Single-node fallback ──────────────────────────────────────────────────

    def _ensure_single_node_fallback(self) -> None:
        """Auto-create a virtual hub node when no pipes are configured.

        When topology has no `pipes:` key (or empty list), a single node
        `_network_root` is created and all existing node components are merged
        into it.  Calling code then proceeds through the unified network path
        without any special-case branches.
        """
        if self.pipes:
            return  # Normal multi-node topology

        virtual_node_id = '_network_root'
        if virtual_node_id not in self.nodes:
            all_components: dict = {}
            for ncfg in self.nodes.values():
                all_components.update(ncfg.get('components', {}))

            self.nodes = {
                virtual_node_id: {
                    'id': virtual_node_id,
                    'type': 'producer',
                    'components': all_components,
                    'name': 'Virtual network root (single-node fallback)',
                }
            }
            logger.info(
                "No pipes configured — created virtual single-node hub: _network_root"
            )

    # ── Main entry point ──────────────────────────────────────────────────────

    def attach_to_model(self, model, time_set, buses: dict) -> dict[str, Any]:
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

        self._ensure_single_node_fallback()

        temp_setup = self._setup_temperatures(model, time_set)
        pipe_components = self._attach_all_pipes(model, time_set, buses, temp_setup)
        node_components = self._attach_all_nodes(model, time_set, buses, temp_setup, pipe_components)

        milp_linearize = self.config.get('thermal_network', {}).get('milp_linearize', False)

        self._link_pipe_temperatures(model, time_set, pipe_components, node_components)
        self._link_consumer_demands(model, time_set, pipe_components, node_components)
        self._link_pressure_propagation(model, time_set, pipe_components, node_components)

        if not milp_linearize:
            # Full physics: junction temp mixing + plant return temp (bilinear)
            self._link_junction_flows(model, time_set, pipe_components, node_components)
            self._link_plant_return_temps(model, time_set, temp_setup, pipe_components, node_components)
        else:
            # MILP mode: junction mass balance only (no temp mixing — temps are fixed Params)
            self._link_junction_flows_simple(model, time_set, pipe_components, node_components)
            logger.info("MILP mode: skipped temperature mixing + plant return temps (temps are fixed Params)")

        self._setup_network_losses(model, time_set, pipe_components)

        logger.info("\n" + "=" * 60)
        logger.info("THERMAL NETWORK ATTACHED SUCCESSFULLY")
        logger.info(f"  Pipes: {len(pipe_components)}")
        logger.info(f"  Nodes: {len(node_components)}")
        logger.info("=" * 60)

        return {
            'pipes': pipe_components,
            'nodes': node_components,
            'parameters': self.parameters,
            'supply_temp': temp_setup['supply_temp'],
            'return_temp': temp_setup['return_temp'],
            'ground_temp': temp_setup['ground_temp'],
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    def _setup_temperatures(self, model, time_set) -> dict[str, Any]:
        """Setup temperature profiles.

        Returns a dict with keys: supply_temp, return_temp, ground_temp,
        use_heating_curve, use_outdoor_temp, supply_temp_dict.
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
            logger.info("\n  HEATING CURVE (Heizkurve) enabled:")
            logger.info(f"    Formula: {curve_params['formula']}")
            logger.info(
                f"    Range: {T_supply_min}°C (at {T_outdoor_high}°C outdoor) "
                f"to {T_supply_max}°C (at {T_outdoor_low}°C outdoor)"
            )
            logger.info(
                f"    Supply temp range in data: "
                f"{min(supply_temp_series):.1f}°C - {max(supply_temp_series):.1f}°C"
            )
            supply_temp = sum(supply_temp_series) / len(supply_temp_series)
            logger.info(f"    Average supply temp: {supply_temp:.1f}°C")
        else:
            supply_temp = supply_temp_nominal
            model.supply_temp_series = {t: supply_temp for t in time_set}
            if use_heating_curve and not use_outdoor_temp:
                logger.warning("  Heating curve enabled but outdoor temperature not available!")
                logger.warning("  Set 'use_outdoor_temperature: true' in config to enable heating curve.")

        return {
            'supply_temp': supply_temp,
            'return_temp': return_temp,
            'ground_temp': ground_temp,
            'use_heating_curve': use_heating_curve,
            'use_outdoor_temp': use_outdoor_temp,
            'supply_temp_dict': {t: model.supply_temp_series[t] for t in time_set},
        }

    def _attach_all_pipes(self, model, time_set, buses, temp_setup) -> dict:
        """Phase 1: Validate and attach all pipe pair blocks."""
        supply_temp = temp_setup['supply_temp']
        return_temp = temp_setup['return_temp']
        use_outdoor_temp = temp_setup['use_outdoor_temp']

        pipe_components: dict = {}
        logger.info(f"\nAttaching {len(self.pipes)} pipe pairs...")

        # Propagate milp_linearize flag from thermal_network config
        milp_linearize = self.config.get('thermal_network', {}).get('milp_linearize', False)

        for pipe_id, pipe_config in self.pipes.items():
            pipe_dict = pipe_config if isinstance(pipe_config, dict) else pipe_config.__dict__
            enriched_config = {
                **pipe_dict,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_nominal_c': return_temp,
                'use_outdoor_temperature': use_outdoor_temp,
                'pipe_catalog': self.pipe_catalog,
                'milp_linearize': milp_linearize,
                **self.parameters,
            }
            PipePairBlock.validate_config(enriched_config)
            pipe_result = PipePairBlock.attach(model, time_set, enriched_config, buses)
            pipe_components[pipe_id] = pipe_result
            logger.info(
                f"  ✓ {pipe_id}: {pipe_config['from_node']} → {pipe_config['to_node']} "
                f"({pipe_config['length_m']}m)"
            )

        return pipe_components

    def _attach_all_nodes(self, model, time_set, buses, temp_setup, pipe_components) -> dict:
        """Phase 2: Validate and attach all thermal node blocks."""
        supply_temp = temp_setup['supply_temp']
        return_temp = temp_setup['return_temp']

        # Propagate milp_linearize flag from thermal_network config
        milp_linearize = self.config.get('thermal_network', {}).get('milp_linearize', False)

        node_components: dict = {}
        logger.info(f"\nAttaching {len(self.nodes)} thermal nodes...")

        for node_id, node_config in self.nodes.items():
            node_dict = node_config if isinstance(node_config, dict) else node_config.__dict__
            enriched_config = {
                **node_dict,
                'id': node_id,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_c': return_temp,
                'milp_linearize': milp_linearize,
            }
            ThermalNodeBlock.validate_config(enriched_config)
            node_result = ThermalNodeBlock.attach(
                model, time_set, enriched_config, buses, pipe_components
            )
            node_components[node_id] = node_result
            node_type = node_config.get('type', 'unknown')
            logger.info(f"  ✓ {node_id} ({node_type})")

        return node_components

    def _link_pipe_temperatures(self, model, time_set, pipe_components, node_components) -> None:
        """Phase 3: Link pipe temperature inlet variables to node temperatures.

        Unified for all topologies — no brownfield/greenfield distinction.
        For each pipe:
        - T_supply_in linked to from_node.T_supply  (plant sets network supply temp)
        - T_return_in  linked to to_node.T_return   (consumer/junction sets return temp)
        Also tracks which pipes return to each producer node.
        """
        milp_linearize = self.config.get('thermal_network', {}).get('milp_linearize', False)
        logger.info("\nConnecting pipe temperatures to nodes...")

        for pipe_id, pipe_comp in pipe_components.items():
            from_node = pipe_comp['from_node']
            to_node = pipe_comp['to_node']
            pipe_T_supply_in = pipe_comp['T_supply_in']
            pipe_T_return_in = pipe_comp['T_return_in']

            # Link supply inlet to from_node supply temperature
            # Skip in MILP-linearized mode (all temps are fixed Params)
            if from_node in node_components and not milp_linearize:
                from_node_comp = node_components[from_node]
                node_T_supply = from_node_comp['T_supply']
                constraint_name = f"link_pipe_{pipe_id}_supply_in_to_node_{from_node}"

                def supply_link_rule(m, t, _pipe=pipe_T_supply_in, _node=node_T_supply):
                    return _pipe[t] == _node[t]

                setattr(model, constraint_name,
                        pyo.Constraint(time_set, rule=supply_link_rule))
                logger.info(f"    {pipe_id}.T_supply_in ← {from_node}.T_supply")

            # Link return inlet to to_node return temperature
            if to_node in node_components and not milp_linearize:
                to_node_comp = node_components[to_node]
                node_T_return = to_node_comp['T_return']
                constraint_name = f"link_pipe_{pipe_id}_return_in_to_node_{to_node}"

                def return_link_rule(m, t, _pipe=pipe_T_return_in, _node=node_T_return):
                    if isinstance(_node, pyo.Param):
                        return _pipe[t] == pyo.value(_node[t])
                    return _pipe[t] == _node[t]

                setattr(model, constraint_name,
                        pyo.Constraint(time_set, rule=return_link_rule))
                logger.info(f"    {pipe_id}.T_return_in ← {to_node}.T_return")

            # Track return pipes for producer nodes (used by _link_plant_return_temps)
            if from_node in node_components:
                from_node_comp = node_components[from_node]
                if from_node_comp['type'] == 'producer':
                    if 'return_pipes' not in from_node_comp:
                        from_node_comp['return_pipes'] = []
                    from_node_comp['return_pipes'].append(pipe_id)

    def _link_consumer_demands(self, model, time_set, pipe_components, node_components) -> None:
        """Phase 4: Connect consumer heat demands to incoming pipe Q_consumer variables.

        Uses Q_consumer (the delay-aware delivery variable) rather than Q_delivered.
        """
        logger.info("\nConnecting consumer demands to pipes...")

        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'consumer':
                continue

            incoming_pipes = node_comp.get('incoming_pipes', [])
            outgoing_pipes = node_comp.get('outgoing_pipes', [])
            has_outgoing = len(outgoing_pipes) > 0
            node_Q_demand = node_comp.get('Q_demand')

            if len(incoming_pipes) == 1 and not has_outgoing:
                # Simple terminal consumer: one pipe in, no downstream
                pipe_id = incoming_pipes[0]
                pipe_comp = pipe_components[pipe_id]
                pipe_Q_consumer = pipe_comp.get('Q_consumer', pipe_comp['Q_delivered'])

                def demand_heat_rule(m, t, _Q_pipe=pipe_Q_consumer, _Q_dem=node_Q_demand):
                    if isinstance(_Q_dem, pyo.Param):
                        return _Q_pipe[t] == pyo.value(_Q_dem[t])
                    return _Q_pipe[t] == _Q_dem[t]

                setattr(model, f"link_heat_demand_{node_id}_to_pipe_{pipe_id}",
                        pyo.Constraint(time_set, rule=demand_heat_rule))
                logger.info(f"  ✓ {node_id} demand ← pipe {pipe_id} (Q_consumer)")

            elif len(incoming_pipes) == 1 and has_outgoing:
                # Passthrough consumer: takes demand fraction, passes rest downstream
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

                if has_outgoing:
                    def multi_passthrough_flow_rule(
                        m, t, _in=incoming_pipes, _out=outgoing_pipes, _node=node_m_dot
                    ):
                        total_in = sum(pipe_components[pid]['m_dot'][t] for pid in _in)
                        total_out = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                        return total_in == _node[t] + total_out

                    setattr(model, f"link_demand_{node_id}_multi_passthrough_flow",
                            pyo.Constraint(time_set, rule=multi_passthrough_flow_rule))
                    logger.info(
                        f"  ✓ {node_id} has {len(incoming_pipes)} incoming, "
                        f"{len(outgoing_pipes)} outgoing pipes"
                    )
                else:
                    # Multiple incoming pipes, no outgoing — exact equality with feasibility slack
                    _penalty = self.parameters.get('demand_slack_penalty_eur_per_mwh', 1e6)
                    _slack_var = pyo.Var(time_set, domain=pyo.NonNegativeReals)
                    setattr(model, f"demand_slack_{node_id}", _slack_var)
                    if not hasattr(model, 'demand_slack_penalty_terms'):
                        model.demand_slack_penalty_terms = []
                    model.demand_slack_penalty_terms.append((_slack_var, _penalty))

                    def multi_pipe_heat_rule(
                        m, t, _incoming=incoming_pipes, _Q=node_Q_demand, _slack=_slack_var
                    ):
                        total_Q_consumer = sum(
                            pipe_components[pid].get('Q_consumer', pipe_components[pid]['Q_delivered'])[t]
                            for pid in _incoming
                        )
                        if isinstance(_Q, pyo.Param):
                            return total_Q_consumer + _slack[t] == pyo.value(_Q[t])
                        return total_Q_consumer + _slack[t] == _Q[t]

                    setattr(model, f"link_demand_{node_id}_multi_pipe_heat",
                            pyo.Constraint(time_set, rule=multi_pipe_heat_rule))
                    logger.info(
                        f"  ✓ {node_id}: {len(incoming_pipes)} pipes → "
                        f"Q_consumer sum + slack = Q_demand (penalty={_penalty:.0e} €/MWh)"
                    )
            else:
                logger.warning(f"  ⚠ {node_id} has no incoming pipes!")

    def _link_junction_flows(self, model, time_set, pipe_components, node_components) -> None:
        """Phase 4b: Mass flow balance constraints for junction nodes."""
        logger.info("\nSetting up junction flow balance constraints...")

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

            # A2: Return-side mass balance (same m_dot vars, reversed direction)
            # Return flow goes from outgoing-node side back to incoming-node side,
            # so outgoing pipe return flows supply the junction's return outflow.
            # For symmetric m_dot (supply == return), this mirrors the supply constraint,
            # but we add it explicitly so the return loop is closed.
            all_pipe_ids = list(set(incoming_pipes) | set(outgoing_pipes))
            if len(all_pipe_ids) > len(incoming_pipes):
                def junction_return_flow_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes):
                    # On the return side, flow comes FROM outgoing consumers BACK to junction,
                    # then continues back towards producer via incoming pipes.
                    # m_dot is symmetric: same variable for supply and return.
                    total_return_out = sum(pipe_components[pid]['m_dot'][t] for pid in _in)
                    total_return_in = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                    return total_return_in == total_return_out

                setattr(model, f"junction_{node_id}_return_flow_balance",
                        pyo.Constraint(time_set, rule=junction_return_flow_rule))

            logger.info(
                f"  ✓ {node_id}: supply {len(incoming_pipes)} in = {len(outgoing_pipes)} out "
                f"(+ return balance)"
            )

            # A3: Big-M dominant-flow temperature mixing for junctions with 2+ incoming pipes
            if len(incoming_pipes) >= 2:
                self._add_junction_temperature_mixing(
                    model, time_set, node_id, incoming_pipes, node_components, pipe_components
                )

    def _link_junction_flows_simple(self, model, time_set, pipe_components, node_components) -> None:
        """MILP-mode simplified junction flow balance: supply-side mass balance only."""
        logger.info("\nSetting up simplified junction flow balance (MILP mode)...")

        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'junction':
                continue

            incoming_pipes = node_comp.get('incoming_pipes', [])
            outgoing_pipes = node_comp.get('outgoing_pipes', [])

            if not incoming_pipes or not outgoing_pipes:
                continue

            def junction_flow_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes):
                total_in = sum(pipe_components[pid]['m_dot'][t] for pid in _in)
                total_out = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                return total_in == total_out

            setattr(model, f"junction_{node_id}_flow_balance",
                    pyo.Constraint(time_set, rule=junction_flow_rule))
            logger.info(f"  ✓ {node_id}: {len(incoming_pipes)} in = {len(outgoing_pipes)} out")

    def _link_plant_return_temps(
        self, model, time_set, temp_setup, pipe_components, node_components
    ) -> None:
        """Phase 5: Link producer node return temperature to return pipe outlet temperatures."""
        logger.info("\nSetting up plant return temperature constraints...")

        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'producer':
                continue

            return_pipes = node_comp.get('return_pipes', [])
            node_T_return = node_comp['T_return']

            if not return_pipes:
                logger.warning(f"  ⚠ Producer {node_id} has no return pipes!")
                continue

            if len(return_pipes) == 1:
                pipe_id = return_pipes[0]
                pipe_T_return_out = pipe_components[pipe_id]['T_return_out']

                def single_return_rule(m, t, _node=node_T_return, _pipe=pipe_T_return_out):
                    return _node[t] == _pipe[t]

                setattr(model, f"plant_{node_id}_return_temp",
                        pyo.Constraint(time_set, rule=single_return_rule))
                logger.info(f"  ✓ {node_id}.T_return ← pipe {pipe_id}.T_return_out")

            else:
                # Multiple return pipes: Big-M dominant-flow linearisation (MILP-compatible)
                self._add_junction_temperature_mixing(
                    model, time_set, node_id, return_pipes, node_components, pipe_components,
                    temperature_attr='T_return_out', node_temp_attr='T_return',
                    constraint_prefix=f"plant_{node_id}_return_mixing",
                )
                logger.info(
                    f"  ✓ {node_id}.T_return mixing ← {len(return_pipes)} pipes "
                    f"(Big-M dominant-flow, MILP-compatible)"
                )

        logger.info("\nChecking plant-to-network heat linkage...")
        for node_id, node_comp in node_components.items():
            if node_comp['type'] == 'producer':
                outgoing = node_comp.get('outgoing_pipes', [])
                logger.info(f"  Producer {node_id}: {len(outgoing)} outgoing pipes")

    def _add_junction_temperature_mixing(
        self,
        model,
        time_set,
        node_id: str,
        pipe_ids: list[str],
        node_components: dict,
        pipe_components: dict,
        temperature_attr: str = 'T_supply_out',
        node_temp_attr: str = 'T_supply',
        constraint_prefix: str | None = None,
    ) -> None:
        """Big-M dominant-flow temperature mixing for junctions with multiple incoming pipes.

        For N incoming pipes, introduces binary y[i, t]:
            Σ_i y[i, t] == 1                              (one dominant pipe)
            T_node >= T_pipe_out[i] - M_T * (1 - y[i])   (lower bound)
            T_node <= T_pipe_out[i] + M_T * (1 - y[i])   (upper bound)
        When y[i, t] == 1 the junction inherits pipe i's outlet temperature.

        M_T = 200°C (conservative bound covering any DHN operating range).
        MILP-compatible — no bilinear products.
        """
        if not pipe_ids:
            return

        M_T = 200.0  # Big-M for temperature (°C)
        pfx = constraint_prefix or f"junc_mix_{node_id}"
        node_T = node_components[node_id][node_temp_attr]
        n = len(pipe_ids)

        # Binary dominant-pipe selection variable
        y_name = f"{pfx}_y"
        y_var = pyo.Var(range(n), time_set, domain=pyo.Binary)
        setattr(model, y_name, y_var)

        # SOS1: exactly one dominant pipe per timestep
        setattr(
            model,
            f"{pfx}_sos1",
            pyo.Constraint(time_set, rule=lambda m, t: sum(y_var[i, t] for i in range(n)) == 1),
        )

        # Big-M bounds linking junction temperature to dominant pipe outlet
        for i, pid in enumerate(pipe_ids):
            pipe_T = pipe_components[pid][temperature_attr]

            def _lb(m, t, _i=i, _pT=pipe_T):
                return node_T[t] >= _pT[t] - M_T * (1 - y_var[_i, t])

            def _ub(m, t, _i=i, _pT=pipe_T):
                return node_T[t] <= _pT[t] + M_T * (1 - y_var[_i, t])

            setattr(model, f"{pfx}_T_lb_{i}", pyo.Constraint(time_set, rule=_lb))
            setattr(model, f"{pfx}_T_ub_{i}", pyo.Constraint(time_set, rule=_ub))

        logger.info(
            f"  ✓ {node_id}: Big-M dominant-flow mixing ({n} pipes, "
            f"attr={temperature_attr})"
        )

    def _link_pressure_propagation(
        self, model, time_set, pipe_components: dict, node_components: dict
    ) -> None:
        """A1 — Pressure propagation through the pipe network.

        For each pipe (from_node → to_node):
          Supply side:  P_supply[to_node, t]   == P_supply[from_node, t] - delta_p_supply[pipe, t]
          Return side:  P_return[from_node, t] == P_return[to_node, t]   - delta_p_return[pipe, t]

        Producer nodes have their supply pressure fixed to the configured setpoint.
        Consumer nodes get a minimum pressure constraint (min_required_bar).
        """
        logger.info("\nSetting up pressure propagation constraints...")

        # Fix producer supply pressure setpoints
        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'producer':
                continue
            node_cfg = self.nodes.get(node_id, {})
            setpoint = node_cfg.get('pressure', {}).get('setpoint_bar', 10.0)
            node_P_supply = node_comp['pressure_supply']
            node_P_return = node_comp['pressure_return']

            setattr(
                model,
                f"producer_{node_id}_P_supply_setpoint",
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _P=node_P_supply, _sp=setpoint: _P[t] == _sp,
                ),
            )
            # Return pressure at producer is setpoint minus typical loop drop (fixed lower)
            return_setpoint = setpoint * 0.5  # conservative default
            setattr(
                model,
                f"producer_{node_id}_P_return_setpoint",
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _P=node_P_return, _sp=return_setpoint: _P[t] == _sp,
                ),
            )
            logger.info(
                f"  ✓ Producer {node_id}: P_supply fixed = {setpoint} bar, "
                f"P_return fixed = {return_setpoint:.1f} bar"
            )

        # Collect producer node IDs (have fixed pressure setpoints)
        producer_nodes = {
            nid for nid, nc in node_components.items() if nc['type'] == 'producer'
        }

        # Propagate pressure through pipes
        for pipe_id, pipe_comp in pipe_components.items():
            from_node = pipe_comp['from_node']
            to_node = pipe_comp['to_node']

            if from_node not in node_components or to_node not in node_components:
                continue

            # Skip loop-closing pipes: if to_node is a producer (fixed pressure),
            # chaining the pressure drop back to it would force the total loop drop
            # to zero, making any nonzero flow infeasible.
            if to_node in producer_nodes:
                logger.info(
                    f"  ⊘ {pipe_id}: loop-closing pipe ({from_node} → producer {to_node}) "
                    f"— pressure propagation skipped"
                )
                continue

            pipe_prefix = pipe_comp.get('prefix', pipe_id.upper().replace('-', '_'))
            delta_p_supply = getattr(model, f"{pipe_prefix}_delta_p_supply", None)
            delta_p_return = getattr(model, f"{pipe_prefix}_delta_p_return", None)

            if delta_p_supply is None or delta_p_return is None:
                logger.warning(f"  ⚠ {pipe_id}: pressure drop variables not found, skipping propagation")
                continue

            from_P_supply = node_components[from_node]['pressure_supply']
            to_P_supply = node_components[to_node]['pressure_supply']
            from_P_return = node_components[from_node]['pressure_return']
            to_P_return = node_components[to_node]['pressure_return']

            # Supply: pressure drops from from_node to to_node
            setattr(
                model,
                f"pressure_supply_prop_{pipe_id}",
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _f=from_P_supply, _t=to_P_supply, _dp=delta_p_supply: (
                        _t[t] == _f[t] - _dp[t]
                    ),
                ),
            )
            # Return: pressure drops from to_node back to from_node
            setattr(
                model,
                f"pressure_return_prop_{pipe_id}",
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _f=from_P_return, _t=to_P_return, _dp=delta_p_return: (
                        _f[t] == _t[t] - _dp[t]
                    ),
                ),
            )
            logger.info(
                f"  ✓ {pipe_id}: P_supply[{to_node}] = P_supply[{from_node}] - ΔP_supply; "
                f"P_return[{from_node}] = P_return[{to_node}] - ΔP_return"
            )

        # Minimum pressure at consumer nodes
        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'consumer':
                continue
            node_cfg = self.nodes.get(node_id, {})
            min_p = node_cfg.get('pressure', {}).get('min_required_bar')
            if min_p is None:
                continue
            node_P_supply = node_comp['pressure_supply']
            setattr(
                model,
                f"consumer_{node_id}_P_min",
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _P=node_P_supply, _mp=min_p: _P[t] >= _mp,
                ),
            )
            logger.info(f"  ✓ Consumer {node_id}: P_supply >= {min_p} bar")

    def _setup_network_losses(self, model, time_set, pipe_components) -> None:
        """Phase 6: Create per-timestep network heat loss variable binding all pipe losses."""
        logger.info("\nCreating per-timestep network heat losses...")

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

        if pipe_components:
            def network_loss_rule(m, t):
                return m.network_Q_loss_per_timestep[t] == sum(
                    pipe_comp['Q_loss_supply'][t] + pipe_comp['Q_loss_return'][t]
                    for pipe_comp in pipe_components.values()
                )

            model.network_loss_per_timestep_calc = pyo.Constraint(
                time_set, rule=network_loss_rule
            )
            logger.info(f"  ✓ network_Q_loss_per_timestep = Σ pipe losses ({len(pipe_components)} pipes)")
        else:
            # Single-node fallback: no pipe losses
            def zero_loss_rule(m, t):
                return m.network_Q_loss_per_timestep[t] == 0

            model.network_loss_per_timestep_calc = pyo.Constraint(
                time_set, rule=zero_loss_rule
            )
            logger.info("  ✓ network_Q_loss_per_timestep = 0 (single-node topology)")

        if hasattr(model, 'pipe_capex_costs'):
            total_pipe_capex = sum(model.pipe_capex_costs.values())
            logger.info(f"  Total pipe CAPEX (annualized): {total_pipe_capex}")

    # ── Results extraction ─────────────────────────────────────────────────────

    def get_results(self, model, time_set) -> dict[str, Any]:
        """Extract network results from solved model."""
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
            'summary': {},
        }

        for pipe_id, pipe_config in self.pipes.items():
            results['pipes'][pipe_id] = PipePairBlock.get_results(model, time_set, pipe_config)

        for node_id, node_config in self.nodes.items():
            results['nodes'][node_id] = ThermalNodeBlock.get_results(model, time_set, node_config)

        dt_h = getattr(model, 'dt_h', 1.0)

        total_heat_delivered = sum(
            r['total_heat_delivered_mwh'] for r in results['pipes'].values()
        )
        total_heat_loss = sum(
            r['total_heat_loss_mwh'] for r in results['pipes'].values()
        )

        if total_heat_delivered <= 0 and hasattr(model, 'network_Q_loss_per_timestep'):
            # Single-node fallback: derive from network loss var
            total_heat_loss = sum(
                pyo.value(model.network_Q_loss_per_timestep[t]) * dt_h / 1000
                for t in time_set
            )
            if hasattr(model, 'heatd'):
                total_heat_delivered = sum(
                    pyo.value(model.heatd[t]) * dt_h / 1000 for t in time_set
                )

        loss_percentage = (
            (total_heat_loss / total_heat_delivered * 100)
            if total_heat_delivered > 0 else 0
        )

        max_velocity = max(
            (r.get('max_velocity_m_s', 0) for r in results['pipes'].values()),
            default=0,
        )
        total_pressure_drop = sum(
            r.get('max_delta_p_total_bar', 0) for r in results['pipes'].values()
        )
        avg_total_flow = (
            sum(r.get('avg_flow_kg_s', 0) for r in results['pipes'].values())
            / max(len(results['pipes']), 1)
        )

        pump_efficiency = 0.75
        density_water = 1000  # kg/m³
        pump_power_kw = (
            avg_total_flow * total_pressure_drop * 100000
        ) / (density_water * pump_efficiency * 1000) if total_pressure_drop > 0 else 0

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

    def export_for_dashboard(self, results: dict[str, Any]) -> dict[str, Any]:
        """Format network results for dashboard visualization."""
        dashboard_data = {
            'metadata': results.get('metadata', {}),
            'network_topology': {'nodes': [], 'pipes': []},
            'time_series': {'pipe_flows': {}, 'temperatures': {}, 'heat_losses': {}},
            'investment_results': {
                'pipe_upgrades': [],
                'total_investment_eur': 0,
                'annual_savings_eur': 0,
            },
            'summary': results.get('summary', {}),
        }

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

        for pipe_id, pipe_result in results['pipes'].items():
            self.pipes[pipe_id]
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
            dashboard_data['time_series']['pipe_flows'][pipe_id] = pipe_result['flow_kg_s']
            dashboard_data['time_series']['heat_losses'][pipe_id] = pipe_result['Q_loss_supply_kw']

        for node_id, node_result in results['nodes'].items():
            dashboard_data['time_series']['temperatures'][f'{node_id}_supply'] = node_result['T_supply_c']
            dashboard_data['time_series']['temperatures'][f'{node_id}_return'] = node_result['T_return_c']

        for pipe_id, pipe_result in results['pipes'].items():
            if pipe_result.get('upgrade_recommended'):
                dashboard_data['investment_results']['pipe_upgrades'].append({
                    'pipe_id': pipe_id,
                    'current_diameter': pipe_result['current_diameter_mm'],
                    'recommended_diameter': pipe_result['selected_diameter_mm'],
                    'action': 'upgrade_diameter',
                    'cost_eur': 0,
                })

        return dashboard_data

    def validate_hydraulics_post_optimization(
        self, heat_series: list[float], dt_h: float = 1.0
    ) -> dict[str, Any]:
        """Post-optimization validation of hydraulic constraints."""
        if not self.network_enabled:
            return {'is_valid': True, 'violations': [], 'max_utilization': {}, 'recommendations': []}

        logger.info("=" * 60)
        logger.info("POST-OPTIMIZATION HYDRAULIC VALIDATION")
        logger.info("=" * 60)

        network_config = self.topology.get('network_parameters', {})
        parameters = self.parameters or {}

        supply_temp = network_config.get(
            'supply_temp_nominal_c', parameters.get('supply_temp_nominal_c', 120.0)
        )
        return_temp = network_config.get(
            'return_temp_nominal_c', parameters.get('return_temp_nominal_c', 55.0)
        )
        delta_t = supply_temp - return_temp

        cp_water = network_config.get(
            'cp_water_kj_per_kg_k', parameters.get('cp_water_kj_per_kg_k', 4.186)
        )
        rho_water = network_config.get(
            'rho_water_kg_per_m3', parameters.get('rho_water_kg_per_m3', 983.0)
        )
        max_velocity_m_s = network_config.get(
            'max_velocity_m_s', parameters.get('max_velocity_m_s', 2.5)
        )
        default_pipe_fraction = parameters.get('default_pipe_demand_fraction', 0.2)

        violations = []
        max_utilization = {}
        recommendations = []

        for pipe_id, pipe_config in self.pipes.items():
            diameter_m = pipe_config.get('diameter_mm', 200) / 1000.0
            max_flow_m3_s = (3.14159 * (diameter_m / 2) ** 2) * max_velocity_m_s
            max_flow_kg_s = max_flow_m3_s * rho_water

            demand_fraction = pipe_config.get('demand_fraction', default_pipe_fraction)
            pipe_violations = []
            pipe_max_util = 0.0

            for t, heat_mw in enumerate(heat_series):
                total_flow_kg_s = (
                    heat_mw * 1000 / (cp_water * delta_t)
                    if cp_water > 0 and delta_t > 0 else 0.0
                )
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
                        'excess_percent': (utilization - 1.0) * 100,
                    })

            max_utilization[pipe_id] = {
                'max_utilization': pipe_max_util,
                'diameter_mm': pipe_config.get('diameter_mm', 200),
                'max_flow_kg_s': max_flow_kg_s,
                'is_overloaded': pipe_max_util > 1.0,
            }

            if pipe_violations:
                violations.extend([{'pipe_id': pipe_id, **v} for v in pipe_violations])
                recommended_diameter = self._calculate_required_diameter(
                    max(v['required_flow_kg_s'] for v in pipe_violations),
                    max_velocity_m_s,
                    rho_water,
                )
                recommendations.append({
                    'pipe_id': pipe_id,
                    'current_diameter_mm': pipe_config.get('diameter_mm', 200),
                    'recommended_diameter_mm': recommended_diameter,
                    'max_overload_percent': (pipe_max_util - 1.0) * 100,
                    'violation_hours': len(pipe_violations),
                })

        overloaded_pipes = sum(1 for m in max_utilization.values() if m['is_overloaded'])
        logger.info(f"  Analyzed {len(self.pipes)} pipes")
        logger.info(f"  Overloaded pipes: {overloaded_pipes}")

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

        return {
            'is_valid': len(violations) == 0,
            'violations': violations,
            'max_utilization': max_utilization,
            'recommendations': recommendations,
            'summary': {
                'total_pipes': len(self.pipes),
                'overloaded_pipes': overloaded_pipes,
                'total_violation_hours': len(violations),
                'network_delta_t_k': delta_t,
                'max_velocity_m_s': max_velocity_m_s,
            },
        }

    def _calculate_required_diameter(
        self, required_flow_kg_s: float, max_velocity_m_s: float, rho_water: float
    ) -> int:
        """Calculate minimum diameter (mm) for given flow and max velocity."""
        import math
        area_m2 = required_flow_kg_s / (rho_water * max_velocity_m_s)
        diameter_m = 2 * math.sqrt(area_m2 / 3.14159)
        diameter_mm = diameter_m * 1000

        standard_sizes = [50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800]
        for size in standard_sizes:
            if size >= diameter_mm:
                return size
        return int(math.ceil(diameter_mm / 50) * 50)
