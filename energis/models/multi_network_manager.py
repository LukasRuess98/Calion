"""
Multi-Network Manager for Multi-Temperature District Heating
============================================================

Manages multiple thermal networks with different temperature levels
and their interconnections via heat exchangers.

Key Features:
- Multiple independent networks with different temperature levels
- Heat exchanger coupling between networks (cascading)
- Unified optimization across all networks
- MILP-compatible formulation

Example Use Cases:
- High-temperature industrial network + Low-temperature residential network
- Cascading waste heat from industry to residential areas
- 4th Generation District Heating (4GDH) with multiple temperature levels

Author: EnerGIS Development Team
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

from .network_manager import NetworkManager
from .blocks.heat_exchanger import HeatExchangerBlock

logger = logging.getLogger(__name__)


class MultiNetworkManager:
    """
    Manages multiple thermal networks with interconnections.

    Responsibilities:
    1. Create and manage multiple NetworkManager instances
    2. Create heat exchanger couplings between networks
    3. Add coupling constraints to the optimization model
    4. Collect results from all networks

    Architecture:
    ```
    MultiNetworkManager
    ├── networks: Dict[str, NetworkManager]
    │   ├── "hochtemp": NetworkManager (90-120°C)
    │   └── "niedertemp": NetworkManager (50-70°C)
    ├── heat_exchangers: Dict[str, HeatExchangerBlock]
    │   └── "hx_cascade": HeatExchangerBlock
    └── couplings: List[CouplingConfig]
    ```
    """

    def __init__(
        self,
        config: Dict[str, Any],
        config_dir: Optional[Path] = None,
    ):
        """
        Initialize Multi-Network Manager.

        Args:
            config: Configuration dict with:
                - networks: List of network configurations
                - heat_exchangers: List of HX configurations
                - couplings: List of network coupling definitions
            config_dir: Path to config directory for file references
        """
        self.config = config
        self.config_dir = config_dir or Path('.')

        # Network instances
        self.networks: Dict[str, NetworkManager] = {}

        # Heat exchanger instances
        self.heat_exchangers: Dict[str, Dict[str, Any]] = {}

        # Coupling definitions
        self.couplings: List[Dict[str, Any]] = []

        # Global parameters
        self.parameters = config.get('parameters', {})

        # Parse configuration
        self._parse_config()

        logger.info(f"MultiNetworkManager initialized with {len(self.networks)} networks")

    def _parse_config(self):
        """Parse multi-network configuration."""
        # Parse individual networks
        networks_config = self.config.get('networks', [])

        for net_cfg in networks_config:
            net_id = net_cfg.get('id')
            if not net_id:
                raise ValueError("Each network must have an 'id' field")

            # Create NetworkManager for this network
            self.networks[net_id] = NetworkManager(
                config=net_cfg,
                config_dir=self.config_dir,
            )

            logger.info(f"  Added network: {net_id} "
                       f"(T_supply={net_cfg.get('parameters', {}).get('supply_temp_nominal_c', 'N/A')}°C)")

        # Parse heat exchangers
        hx_config = self.config.get('heat_exchangers', [])

        for hx_cfg in hx_config:
            hx_id = hx_cfg.get('id')
            if not hx_id:
                raise ValueError("Each heat exchanger must have an 'id' field")

            self.heat_exchangers[hx_id] = hx_cfg

            logger.info(f"  Added heat exchanger: {hx_id} "
                       f"({hx_cfg.get('primary_network')} → {hx_cfg.get('secondary_network')})")

        # Parse couplings (explicit network connections)
        self.couplings = self.config.get('couplings', [])

    def attach_to_model(
        self,
        model,
        config: Dict[str, Any],
        time_set,
        outdoor_temp_series: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Attach all networks and couplings to Pyomo model.

        Args:
            model: Pyomo ConcreteModel
            config: Full system configuration
            time_set: Set of timesteps
            outdoor_temp_series: Outdoor temperature time series

        Returns:
            Dict with all network and coupling components
        """
        if pyo is None:
            raise RuntimeError("Pyomo is required")

        logger.info("\n" + "="*70)
        logger.info("MULTI-NETWORK MANAGER: Attaching networks to model")
        logger.info("="*70)

        result = {
            'networks': {},
            'heat_exchangers': {},
            'total_heat_loss_mw': {},
        }

        # ========================================
        # PHASE 1: Attach individual networks
        # ========================================

        for net_id, network_manager in self.networks.items():
            logger.info(f"\n--- Network: {net_id} ---")

            # Get network-specific config
            net_cfg = None
            for nc in self.config.get('networks', []):
                if nc.get('id') == net_id:
                    net_cfg = nc
                    break

            if net_cfg is None:
                net_cfg = {}

            # Attach network to model
            net_result = network_manager.attach_to_model(
                model=model,
                config=net_cfg,
                time_set=time_set,
                outdoor_temp_series=outdoor_temp_series,
            )

            result['networks'][net_id] = net_result

            # Store network prefix for coupling
            model.__setattr__(f'_network_{net_id}', net_result)

        # ========================================
        # PHASE 2: Attach heat exchangers
        # ========================================

        for hx_id, hx_cfg in self.heat_exchangers.items():
            logger.info(f"\n--- Heat Exchanger: {hx_id} ---")

            # Attach HX component
            hx_result = HeatExchangerBlock.attach(
                model=model,
                time_set=time_set,
                config=hx_cfg,
                buses={},
            )

            result['heat_exchangers'][hx_id] = hx_result

        # ========================================
        # PHASE 3: Create coupling constraints
        # ========================================

        logger.info(f"\n--- Creating coupling constraints ---")

        self._create_coupling_constraints(model, time_set, result)

        # ========================================
        # PHASE 4: Create aggregated variables
        # ========================================

        self._create_aggregated_variables(model, time_set, result)

        logger.info("\n" + "="*70)
        logger.info(f"Multi-network attachment complete: "
                   f"{len(self.networks)} networks, {len(self.heat_exchangers)} heat exchangers")
        logger.info("="*70)

        return result

    def _create_coupling_constraints(
        self,
        model,
        time_set,
        result: Dict[str, Any],
    ):
        """Create constraints coupling networks via heat exchangers."""

        for hx_id, hx_cfg in self.heat_exchangers.items():
            hx_result = result['heat_exchangers'].get(hx_id, {})

            primary_net_id = hx_cfg.get('primary_network')
            secondary_net_id = hx_cfg.get('secondary_network')
            primary_side = hx_cfg.get('primary_side', 'return')
            secondary_side = hx_cfg.get('secondary_side', 'supply')

            if primary_net_id not in self.networks:
                logger.warning(f"HX {hx_id}: Primary network '{primary_net_id}' not found")
                continue

            if secondary_net_id not in self.networks:
                logger.warning(f"HX {hx_id}: Secondary network '{secondary_net_id}' not found")
                continue

            primary_net = result['networks'].get(primary_net_id, {})
            secondary_net = result['networks'].get(secondary_net_id, {})

            hx_prefix = hx_id.upper().replace('-', '_')

            # Get HX temperature variables
            T_prim_in = hx_result.get('T_prim_in')
            T_sec_out = hx_result.get('T_sec_out')
            Q_transfer = hx_result.get('Q_transfer')

            if T_prim_in is None or Q_transfer is None:
                logger.warning(f"HX {hx_id}: Missing variables")
                continue

            # ========================================
            # Coupling: Primary network → HX primary inlet
            # ========================================

            # Get return temperature from primary network
            # This is simplified - in full implementation, would link to specific node
            primary_params = self.networks[primary_net_id].parameters
            if primary_side == 'return':
                T_link_primary = primary_params.get('return_temp_nominal_c', 60.0)
            else:
                T_link_primary = primary_params.get('supply_temp_nominal_c', 90.0)

            # Fix primary inlet temperature (brownfield)
            for t in time_set:
                if hasattr(T_prim_in[t], 'fix'):
                    T_prim_in[t].fix(T_link_primary)

            logger.info(f"  {hx_id}: Primary ({primary_net_id}.{primary_side}) → T_prim_in = {T_link_primary}°C")

            # ========================================
            # Coupling: HX secondary outlet → Secondary network
            # ========================================

            # The heat transferred adds to secondary network's supply
            # Create constraint linking Q_transfer to secondary network heat balance

            # For now, we track the coupling for post-processing
            # Full implementation would add constraints to secondary network's plant node

            secondary_params = self.networks[secondary_net_id].parameters
            if secondary_side == 'supply':
                T_link_secondary = secondary_params.get('supply_temp_nominal_c', 55.0)
            else:
                T_link_secondary = secondary_params.get('return_temp_nominal_c', 35.0)

            logger.info(f"  {hx_id}: T_sec_out → Secondary ({secondary_net_id}.{secondary_side}) ~ {T_link_secondary}°C")

            # Store coupling info
            hx_result['coupling'] = {
                'primary_network': primary_net_id,
                'primary_side': primary_side,
                'primary_temp_c': T_link_primary,
                'secondary_network': secondary_net_id,
                'secondary_side': secondary_side,
                'secondary_temp_c': T_link_secondary,
            }

    def _create_aggregated_variables(
        self,
        model,
        time_set,
        result: Dict[str, Any],
    ):
        """Create aggregated variables across all networks."""

        # Total heat loss across all networks
        def total_multi_network_loss_rule(m, t):
            total = 0
            for net_id, net_result in result['networks'].items():
                loss_var = net_result.get('network_Q_loss_per_timestep', {})
                if loss_var and t in loss_var:
                    total += loss_var[t]
            return total

        # Store per-timestep losses
        result['total_heat_loss_mw'] = {
            t: total_multi_network_loss_rule(model, t)
            for t in time_set
        }

        # Total heat transferred via HX
        result['total_hx_transfer_mw'] = {}
        for t in time_set:
            total_hx = 0
            for hx_id, hx_result in result['heat_exchangers'].items():
                Q_transfer = hx_result.get('Q_transfer')
                if Q_transfer:
                    total_hx += Q_transfer[t]
            result['total_hx_transfer_mw'][t] = total_hx

    def get_results(
        self,
        model,
        config: Dict[str, Any],
        time_set,
    ) -> Dict[str, Any]:
        """
        Extract results from all networks and heat exchangers.

        Returns:
            Dict with comprehensive results from all components
        """
        results = {
            'networks': {},
            'heat_exchangers': {},
            'summary': {},
        }

        # ========================================
        # Network results
        # ========================================

        for net_id, network_manager in self.networks.items():
            net_cfg = None
            for nc in self.config.get('networks', []):
                if nc.get('id') == net_id:
                    net_cfg = nc
                    break

            net_results = network_manager.get_results(
                model=model,
                config=net_cfg or {},
                time_set=time_set,
            )

            results['networks'][net_id] = net_results

        # ========================================
        # Heat exchanger results
        # ========================================

        for hx_id, hx_cfg in self.heat_exchangers.items():
            hx_results = HeatExchangerBlock.get_results(
                model=model,
                time_set=time_set,
                config=hx_cfg,
            )

            results['heat_exchangers'][hx_id] = hx_results

        # ========================================
        # Summary statistics
        # ========================================

        total_heat_loss = 0
        total_heat_transferred = 0

        for net_id, net_res in results['networks'].items():
            total_heat_loss += net_res.get('total_network_heat_loss_mwh', 0)

        for hx_id, hx_res in results['heat_exchangers'].items():
            total_heat_transferred += hx_res.get('total_heat_transferred_mwh', 0)

        results['summary'] = {
            'num_networks': len(self.networks),
            'num_heat_exchangers': len(self.heat_exchangers),
            'total_network_heat_loss_mwh': total_heat_loss,
            'total_hx_heat_transferred_mwh': total_heat_transferred,
        }

        return results

    def get_network(self, network_id: str) -> Optional[NetworkManager]:
        """Get a specific network manager by ID."""
        return self.networks.get(network_id)

    def get_network_ids(self) -> List[str]:
        """Get list of all network IDs."""
        return list(self.networks.keys())

    def get_heat_exchanger_ids(self) -> List[str]:
        """Get list of all heat exchanger IDs."""
        return list(self.heat_exchangers.keys())

    def get_temperature_levels(self) -> Dict[str, Dict[str, float]]:
        """
        Get temperature levels for all networks.

        Returns:
            Dict mapping network_id to {supply_temp, return_temp}
        """
        levels = {}

        for net_id, network_manager in self.networks.items():
            params = network_manager.parameters
            levels[net_id] = {
                'supply_temp_c': params.get('supply_temp_nominal_c', 90.0),
                'return_temp_c': params.get('return_temp_nominal_c', 50.0),
                'temperature_level': params.get('temperature_level', 'medium'),
            }

        return levels


def create_multi_network_from_config(
    config_path: Path,
) -> MultiNetworkManager:
    """
    Factory function to create MultiNetworkManager from YAML config.

    Args:
        config_path: Path to multi-network YAML configuration

    Returns:
        Configured MultiNetworkManager instance
    """
    import yaml

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    config_dir = config_path.parent

    return MultiNetworkManager(config=config, config_dir=config_dir)
