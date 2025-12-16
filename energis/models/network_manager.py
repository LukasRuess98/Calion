"""
Network Manager for Thermal District Heating Networks

Coordinates pipe and node components, parses network topology,
and integrates with the main optimization model.

Author: EnerGIS Development Team
Date: 2025-12-10
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import pyomo.environ as pyo

from .blocks.pipe_pair import PipePairBlock
from .blocks.thermal_node import ThermalNodeBlock

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
            config: Network configuration dict
            config_dir: Base directory for resolving relative paths
        """
        self.config = config
        self.config_dir = config_dir or Path.cwd()

        self.nodes = {}
        self.pipes = {}
        self.pipe_catalog = {}

        self.network_enabled = config.get('thermal_network', {}).get('enabled', False)

        if self.network_enabled:
            self._load_network_topology()

    def _load_network_topology(self):
        """Load network topology from YAML file, Excel file, or inline config."""
        network_config = self.config.get('thermal_network', {})

        # Check for external topology file (YAML)
        topology_file = network_config.get('topology_file')

        # Check for Excel-based topology
        topology_excel = network_config.get('topology_excel')

        if topology_excel:
            # Load from Excel file
            excel_path = Path(topology_excel)
            if not excel_path.is_absolute():
                excel_path = self.config_dir / topology_excel

            logger.info(f"Loading network topology from Excel: {excel_path}")

            from energis.io.network_loader import load_network_from_excel
            topology_data = load_network_from_excel(
                str(excel_path),
                nodes_sheet=network_config.get('nodes_sheet', 'Network_Nodes'),
                pipes_sheet=network_config.get('pipes_sheet', 'Network_Pipes'),
                params_sheet=network_config.get('params_sheet', 'Network_Parameters'),
            )

            if topology_data is None:
                logger.warning("No network data found in Excel, disabling network")
                self.network_enabled = False
                return

        elif topology_file:
            topology_path = Path(topology_file)
            if not topology_path.is_absolute():
                topology_path = self.config_dir / topology_path

            logger.info(f"Loading network topology from YAML: {topology_path}")

            with open(topology_path, 'r') as f:
                topology_data = yaml.safe_load(f)
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
        supply_temp = self.parameters.get('supply_temp_nominal_c', 90.0)
        return_temp = self.parameters.get('return_temp_nominal_c', 50.0)

        # Setup outdoor temperature (if available)
        use_outdoor_temp = self.config.get('thermal_network', {}).get('use_outdoor_temperature', False)
        if use_outdoor_temp and hasattr(model, 'outdoor_temp'):
            logger.info("Using time-varying outdoor temperature from model")
        else:
            # Create fixed ground temperature
            default_ground_temp = self.parameters.get('ground_temp_default_c', 10.0)
            model.outdoor_temp = {t: default_ground_temp for t in time_set}
            logger.info(f"Using fixed ground temperature: {default_ground_temp}°C")

        # ========================================
        # PHASE 1: Attach all pipes
        # ========================================

        logger.info(f"\nAttaching {len(self.pipes)} pipe pairs...")

        # Check brownfield mode (moved earlier for pipe config)
        brownfield_mode = self.config.get('thermal_network', {}).get('brownfield_mode', False)
        if brownfield_mode:
            logger.info("  [Brownfield mode: temperatures fixed at design values]")

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

            logger.info(f"  ✓ {pipe_id}: {pipe_config['from_node']} → {pipe_config['to_node']} "
                       f"({pipe_config['length_m']}m)")

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

            # Track return pipes for each plant node (for later mixing constraint)
            if from_node in node_components:
                from_node_comp = node_components[from_node]
                if from_node_comp['type'] == 'plant':
                    if 'return_pipes' not in from_node_comp:
                        from_node_comp['return_pipes'] = []
                    from_node_comp['return_pipes'].append(pipe_id)

        # ========================================
        # PHASE 4: Connect demands to pipes
        # ========================================

        logger.info(f"\nConnecting consumer demands to pipes...")

        for node_id, node_comp in node_components.items():
            if node_comp['type'] == 'consumer':
                # Find pipe(s) supplying this consumer
                incoming_pipes = node_comp.get('incoming_pipes', [])

                if len(incoming_pipes) == 1:
                    # Simple case: one pipe feeds this consumer
                    pipe_id = incoming_pipes[0]
                    pipe_comp = pipe_components[pipe_id]

                    # Link flow: pipe delivers what consumer needs
                    pipe_m_dot = pipe_comp['m_dot']
                    node_m_dot = node_comp['m_dot_demand']

                    constraint_name = f"link_demand_{node_id}_to_pipe_{pipe_id}"

                    def demand_flow_rule(m, t):
                        return pipe_m_dot[t] == node_m_dot[t]

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=demand_flow_rule))

                    # Link heat delivered
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

                elif len(incoming_pipes) > 1:
                    # Multiple pipes feed this consumer - sum of flows = demand
                    logger.info(f"  ✓ {node_id} has {len(incoming_pipes)} incoming pipes - "
                               f"creating multi-pipe flow balance")

                    node_m_dot = node_comp['m_dot_demand']
                    node_Q_demand = node_comp['Q_demand']

                    # Flow balance: sum of pipe flows = consumer demand flow
                    constraint_name_flow = f"link_demand_{node_id}_multi_pipe_flow"

                    def multi_pipe_flow_rule(m, t, _incoming=incoming_pipes):
                        total_inflow = sum(
                            pipe_components[pid]['m_dot'][t]
                            for pid in _incoming
                        )
                        return total_inflow == node_m_dot[t]

                    setattr(model, constraint_name_flow, pyo.Constraint(time_set, rule=multi_pipe_flow_rule))

                    # Heat balance: sum of heat delivered = consumer heat demand
                    # Note: This constraint ensures thermal consistency at multi-pipe junctions
                    constraint_name_heat = f"link_demand_{node_id}_multi_pipe_heat"

                    def multi_pipe_heat_rule(m, t, _incoming=incoming_pipes, _Q=node_Q_demand):
                        total_heat = sum(
                            pipe_components[pid]['Q_delivered'][t]
                            for pid in _incoming
                        )
                        if isinstance(_Q, pyo.Param):
                            return total_heat >= pyo.value(_Q[t]) * 0.99  # Allow 1% tolerance
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

        for node_id, node_comp in node_components.items():
            if node_comp['type'] == 'junction':
                incoming_pipes = node_comp.get('incoming_pipes', [])
                outgoing_pipes = node_comp.get('outgoing_pipes', [])

                if not incoming_pipes or not outgoing_pipes:
                    logger.warning(f"  ⚠ Junction {node_id} incomplete: "
                                  f"{len(incoming_pipes)} in, {len(outgoing_pipes)} out")
                    continue

                # Flow balance: sum(incoming) = sum(outgoing)
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
                logger.info(f"  ✓ {node_id}: {len(incoming_pipes)} in = {len(outgoing_pipes)} out")

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
                    # Simple case: single return stream
                    pipe_id = return_pipes[0]
                    pipe_comp = pipe_components[pipe_id]
                    pipe_T_return_out = pipe_comp['T_return_out']
                    pipe_m_dot = pipe_comp['m_dot']

                    constraint_name = f"plant_{node_id}_return_temp_single"

                    def single_return_rule(m, t):
                        return node_T_return[t] == pipe_T_return_out[t]

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=single_return_rule))
                    logger.info(f"  ✓ {node_id} return temp ← pipe {pipe_id}")

                else:
                    # Multiple return streams: weighted average by mass flow
                    # T_return * sum(m_dot_i) = sum(T_return_out_i * m_dot_i)
                    constraint_name = f"plant_{node_id}_return_temp_mixing"

                    def multi_return_rule(m, t):
                        total_return_flow = 0
                        weighted_temp = 0

                        for pipe_id in return_pipes:
                            pipe_comp = pipe_components[pipe_id]
                            pipe_m_dot = pipe_comp['m_dot']
                            pipe_T_return_out = pipe_comp['T_return_out']

                            total_return_flow += pipe_m_dot[t]
                            weighted_temp += pipe_T_return_out[t] * pipe_m_dot[t]

                        # Weighted average: T_node * sum(m_dot) = sum(T_pipe * m_dot)
                        return node_T_return[t] * total_return_flow == weighted_temp

                    setattr(model, constraint_name, pyo.Constraint(time_set, rule=multi_return_rule))
                    logger.info(f"  ✓ {node_id} return temp mixing ← {len(return_pipes)} pipes")

        # ========================================
        # PHASE 5b: Plant-to-Network Heat Linkage
        # ========================================
        # This is the critical constraint connecting heat production to network distribution
        # Total heat entering network from plants = total heat demand (heatd)

        logger.info(f"\nSetting up plant-to-network heat linkage...")

        # Collect all pipes leaving plant nodes
        plant_outgoing_pipes = []
        for node_id, node_comp in node_components.items():
            if node_comp['type'] == 'plant':
                outgoing = node_comp.get('outgoing_pipes', [])
                plant_outgoing_pipes.extend(outgoing)
                logger.info(f"  Plant {node_id}: {len(outgoing)} outgoing pipes")

        if plant_outgoing_pipes and hasattr(model, 'heatd'):
            # Network temperature differential (for heat-to-flow conversion)
            network_delta_t = supply_temp - return_temp  # K
            cp_water = 4.186  # kJ/(kg·K)

            logger.info(f"  Network ΔT: {network_delta_t}K, {len(plant_outgoing_pipes)} plant pipes total")

            # Constraint: Total heat entering network = total demand
            # sum(m_dot * cp * delta_T) / 1000 = heatd (converting kW to MW)
            def plant_network_balance_rule(m, t):
                total_heat_input = sum(
                    pipe_components[pid]['m_dot'][t] * cp_water * network_delta_t / 1000
                    for pid in plant_outgoing_pipes
                )
                # Allow for network heat losses (up to 15% tolerance)
                return total_heat_input >= m.heatd[t] * 1.0

            setattr(model, 'plant_network_heat_balance',
                    pyo.Constraint(time_set, rule=plant_network_balance_rule))

            # Also add upper bound to prevent unbounded flows
            def plant_network_upper_rule(m, t):
                total_heat_input = sum(
                    pipe_components[pid]['m_dot'][t] * cp_water * network_delta_t / 1000
                    for pid in plant_outgoing_pipes
                )
                # Allow 20% extra for losses and operational margin
                return total_heat_input <= m.heatd[t] * 1.20

            setattr(model, 'plant_network_heat_upper',
                    pyo.Constraint(time_set, rule=plant_network_upper_rule))

            logger.info(f"  ✓ Plant-network balance constraint added")
        else:
            logger.warning("  ⚠ No plant outgoing pipes or heatd not found - skipping linkage")

        # ========================================
        # PHASE 6: Calculate total network costs
        # ========================================

        logger.info(f"\nCalculating network costs...")

        # Sum all pipe CAPEX
        if hasattr(model, 'pipe_capex_costs'):
            total_pipe_capex = sum(model.pipe_capex_costs.values())
            logger.info(f"  Total pipe CAPEX (annualized): {total_pipe_capex}")
        else:
            total_pipe_capex = 0

        # Heat loss penalty (OPEX)
        # Heat losses valued at marginal generation cost
        # This should be added to objective in system_builder

        total_heat_loss_expr = sum(
            sum(pipe_comp['Q_loss_supply'][t] + pipe_comp['Q_loss_return'][t] for t in time_set)
            for pipe_comp in pipe_components.values()
        )

        # Store for objective function
        model.network_total_pipe_capex = total_pipe_capex
        model.network_heat_loss_expr = total_heat_loss_expr

        logger.info("=" * 60)
        logger.info("THERMAL NETWORK ATTACHED SUCCESSFULLY")
        logger.info("=" * 60)

        return {
            'pipes': pipe_components,
            'nodes': node_components,
            'total_capex': total_pipe_capex,
            'heat_loss_expr': total_heat_loss_expr
        }

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

        # Calculate summary statistics
        total_heat_delivered = sum(
            pipe_res['total_heat_delivered_mwh']
            for pipe_res in results['pipes'].values()
        )

        total_heat_loss = sum(
            pipe_res['total_heat_loss_mwh']
            for pipe_res in results['pipes'].values()
        )

        loss_percentage = (total_heat_loss / total_heat_delivered * 100) if total_heat_delivered > 0 else 0

        # Hydraulic summary - aggregate from pipe results
        max_velocity = max(
            (pipe_res.get('max_velocity_m_s', 0) for pipe_res in results['pipes'].values()),
            default=0
        )

        # Critical path pressure drop (sum of max pressure drops per pipe)
        # In a real network, you'd trace the actual critical path
        total_pressure_drop = sum(
            pipe_res.get('max_delta_p_total_bar', 0)
            for pipe_res in results['pipes'].values()
        )

        # Pump power estimation
        # P_pump = (V_dot * ΔP) / η = (m_dot / ρ) * ΔP * 100000 / η [W]
        # For simplicity, use average flow and total pressure drop
        avg_total_flow = sum(
            pipe_res.get('avg_flow_kg_s', 0)
            for pipe_res in results['pipes'].values()
        ) / max(len(results['pipes']), 1)

        # Pump efficiency (typical for variable speed pumps)
        pump_efficiency = 0.75
        density_water = 1000  # kg/m³

        # P_pump [kW] = (m_dot [kg/s] / ρ [kg/m³]) * ΔP [bar] * 100000 [Pa/bar] / (η * 1000 [W/kW])
        # Simplified: P_pump [kW] = m_dot * ΔP * 100 / (ρ * η)
        pump_power_kw = (avg_total_flow * total_pressure_drop * 100000) / (density_water * pump_efficiency * 1000)

        # Annual pump energy [MWh] = P_pump [kW] * hours / 1000
        dt_h = getattr(model, 'dt_h', 1.0)
        n_timesteps = len(list(time_set))
        operating_hours = n_timesteps * dt_h
        pump_energy_mwh = pump_power_kw * operating_hours / 1000

        results['summary'] = {
            # Thermal
            'total_heat_delivered_mwh': total_heat_delivered,
            'total_heat_loss_mwh': total_heat_loss,
            'loss_percentage': loss_percentage,
            'total_pipe_length_m': sum(p['length_m'] for p in self.pipes.values()),

            # Hydraulic
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

        This method calculates the required pipe flows based on the heat
        production/consumption results and validates them against pipe
        hydraulic limits (max velocity, max pressure drop, max flow).

        This approach keeps the main optimization linear/convex while still
        providing hydraulic validation feedback.

        Args:
            heat_series: Time series of total heat demand (MW) from optimization
            dt_h: Time step duration in hours

        Returns:
            Dict with validation results:
            - 'is_valid': bool - overall validation result
            - 'violations': list of pipe/timestep violations
            - 'max_utilization': dict of max flow utilization per pipe
            - 'recommendations': list of upgrade recommendations
        """
        if not self.network_enabled:
            return {'is_valid': True, 'violations': [], 'max_utilization': {}, 'recommendations': []}

        logger.info("=" * 60)
        logger.info("POST-OPTIMIZATION HYDRAULIC VALIDATION")
        logger.info("=" * 60)

        # Network parameters
        network_config = self.topology.get('network_parameters', {})
        supply_temp = network_config.get('supply_temp_nominal_c', 120.0)
        return_temp = network_config.get('return_temp_nominal_c', 55.0)
        delta_t = supply_temp - return_temp  # K
        cp_water = 4.186  # kJ/(kg·K)
        rho_water = 983.0  # kg/m³ at ~60°C average

        # Hydraulic limits
        max_velocity_m_s = network_config.get('max_velocity_m_s', 2.5)

        violations = []
        max_utilization = {}
        recommendations = []

        # For each pipe, calculate required flow and validate
        for pipe_id, pipe_config in self.pipes.items():
            diameter_m = pipe_config.get('diameter_mm', 200) / 1000.0
            max_flow_m3_s = (3.14159 * (diameter_m / 2) ** 2) * max_velocity_m_s
            max_flow_kg_s = max_flow_m3_s * rho_water

            # For brownfield networks, assume proportional flow distribution
            # based on demand served by this pipe segment
            # (This is a simplification - real flow depends on network topology)
            demand_fraction = pipe_config.get('demand_fraction', 0.2)  # Default 20% of total flow

            pipe_violations = []
            pipe_max_util = 0.0

            for t, heat_mw in enumerate(heat_series):
                # Calculate required mass flow for this timestep
                # Q = m_dot * cp * delta_T / 1000 (kW to MW)
                # m_dot = Q * 1000 / (cp * delta_T)
                total_flow_kg_s = heat_mw * 1000 / (cp_water * delta_t)

                # This pipe's share of the flow
                pipe_flow_kg_s = total_flow_kg_s * demand_fraction

                # Calculate utilization
                utilization = pipe_flow_kg_s / max_flow_kg_s if max_flow_kg_s > 0 else 0
                pipe_max_util = max(pipe_max_util, utilization)

                # Check for violation
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
                # Add upgrade recommendation
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

        # Summary logging
        overloaded_pipes = sum(1 for m in max_utilization.values() if m['is_overloaded'])
        logger.info(f"  Analyzed {len(self.pipes)} pipes")
        logger.info(f"  Overloaded pipes: {overloaded_pipes}")
        logger.info(f"  Total violation hours: {len(violations)}")

        if overloaded_pipes > 0:
            logger.warning(f"  ⚠ {overloaded_pipes} pipes exceed hydraulic limits!")
            for rec in recommendations:
                logger.warning(f"    - {rec['pipe_id']}: {rec['current_diameter_mm']}mm → "
                              f"{rec['recommended_diameter_mm']}mm (overload: {rec['max_overload_percent']:.1f}%)")
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
