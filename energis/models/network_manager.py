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

        for pipe_id, pipe_config in self.pipes.items():
            # Enrich pipe config with global parameters
            enriched_config = {
                **pipe_config,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_nominal_c': return_temp,
                'use_outdoor_temperature': use_outdoor_temp,
                'pipe_catalog': self.pipe_catalog,
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
                    # Multiple pipes feed this consumer - need flow balance
                    logger.warning(f"  ⚠ {node_id} has {len(incoming_pipes)} incoming pipes - "
                                  f"complex flow balance needed (Phase 2 feature)")
                else:
                    logger.warning(f"  ⚠ {node_id} has no incoming pipes!")

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

        results['summary'] = {
            'total_heat_delivered_mwh': total_heat_delivered,
            'total_heat_loss_mwh': total_heat_loss,
            'loss_percentage': loss_percentage,
            'total_pipe_length_m': sum(p['length_m'] for p in self.pipes.values()),
        }

        logger.info(f"  Total heat delivered: {total_heat_delivered:.1f} MWh")
        logger.info(f"  Total heat losses: {total_heat_loss:.1f} MWh ({loss_percentage:.2f}%)")

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
            dashboard_data['time_series']['heat_losses'][pipe_id] = pipe_result['Q_loss_supply_mw']

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
