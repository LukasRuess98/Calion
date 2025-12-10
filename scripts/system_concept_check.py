#!/usr/bin/env python3
"""
Umfassender System-Konzept-Check für thermische Netzwerk-Integration.

Prüft:
- Dateikonsistenz und Imports
- Konfigurationsstrukturen
- Integration Points
- Vollständigkeit
- Kompatibilität mit Runners
"""

import os
import sys
from pathlib import Path
import yaml
import logging
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def check_mark(passed: bool) -> str:
    return f"{Colors.GREEN}✓{Colors.END}" if passed else f"{Colors.RED}✗{Colors.END}"


class SystemConceptChecker:
    """Comprehensive system check for thermal network integration."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.issues = []
        self.warnings = []
        self.passed_checks = 0
        self.total_checks = 0

    def check(self, name: str, condition: bool, error_msg: str = "", warning: bool = False):
        """Record a check result."""
        self.total_checks += 1
        if condition:
            self.passed_checks += 1
            logger.info(f"{check_mark(True)} {name}")
        else:
            logger.warning(f"{check_mark(False)} {name}")
            if warning:
                self.warnings.append(f"{name}: {error_msg}")
            else:
                self.issues.append(f"{name}: {error_msg}")

    # ============================================================
    # 1. FILE STRUCTURE CHECKS
    # ============================================================

    def check_file_structure(self):
        """Check that all required files exist."""
        logger.info(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        logger.info(f"{Colors.BOLD}1. FILE STRUCTURE CHECK{Colors.END}")
        logger.info(f"{Colors.BOLD}{'='*60}{Colors.END}")

        required_files = {
            # Core components
            'energis/models/blocks/pipe_pair.py': 'PipePairComponent',
            'energis/models/blocks/thermal_node.py': 'ThermalNodeComponent',
            'energis/models/network_manager.py': 'NetworkManager',
            'energis/models/system_builder.py': 'System builder integration',

            # Configurations
            'configs/networks/stadtbach_network.yaml': 'Stadtbach network topology',
            'configs/networks/test_simple_network.yaml': 'Test network topology',
            'configs/systems/test_simple_with_network.system.yaml': 'Test system config',
            'configs/tech_catalog.yaml': 'Technology catalog',

            # Documentation
            'docs/IMPLEMENTATION_PLAN_THERMAL_NETWORKS.md': 'Implementation plan',
            'docs/SYSTEM_ANALYSIS_THERMAL_NETWORKS.md': 'System analysis',
            'docs/THERMAL_NETWORK_SOLVER_REQUIREMENTS.md': 'Solver requirements',
            'docs/PERFORMANCE_OPTIMIZATION_THERMAL_NETWORKS.md': 'Performance optimization',

            # Tests
            'scripts/test_thermal_network.py': 'Test script',
        }

        for file_path, description in required_files.items():
            full_path = self.base_path / file_path
            self.check(
                f"File exists: {file_path}",
                full_path.exists(),
                f"{description} missing at {full_path}"
            )

    # ============================================================
    # 2. IMPORT CHECKS
    # ============================================================

    def check_imports(self):
        """Check that Python imports work."""
        logger.info(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        logger.info(f"{Colors.BOLD}2. IMPORT CHECKS{Colors.END}")
        logger.info(f"{Colors.BOLD}{'='*60}{Colors.END}")

        # Add project to path
        sys.path.insert(0, str(self.base_path))

        imports_to_check = [
            ('energis.models.blocks.pipe_pair', 'PipePairBlock'),
            ('energis.models.blocks.thermal_node', 'ThermalNodeBlock'),
            ('energis.models.network_manager', 'NetworkManager'),
            ('energis.models.system_builder', 'build_model'),
            ('energis.models.blocks.stratified_storage', 'StratifiedStorageBlock'),
        ]

        for module_name, obj_name in imports_to_check:
            try:
                module = __import__(module_name, fromlist=[obj_name])
                obj = getattr(module, obj_name, None)
                self.check(
                    f"Import: {module_name}.{obj_name}",
                    obj is not None,
                    f"Cannot import {obj_name} from {module_name}"
                )
            except Exception as e:
                self.check(
                    f"Import: {module_name}.{obj_name}",
                    False,
                    f"Import error: {e}"
                )

    # ============================================================
    # 3. CONFIGURATION CHECKS
    # ============================================================

    def check_configurations(self):
        """Check YAML configuration consistency."""
        logger.info(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        logger.info(f"{Colors.BOLD}3. CONFIGURATION CHECKS{Colors.END}")
        logger.info(f"{Colors.BOLD}{'='*60}{Colors.END}")

        # Check tech_catalog.yaml
        tech_catalog_path = self.base_path / 'configs/tech_catalog.yaml'
        if tech_catalog_path.exists():
            with open(tech_catalog_path, encoding='utf-8') as f:
                tech_catalog = yaml.safe_load(f)

            # Check cop_fallback exists
            cop_fallback = tech_catalog.get('heat_pumps', {}).get('cop', {}).get('cop_fallback')
            self.check(
                "tech_catalog.yaml has cop_fallback",
                cop_fallback is not None,
                "Missing heat_pumps.cop.cop_fallback in tech_catalog.yaml"
            )

            # Check cop_fallback value
            if cop_fallback:
                self.check(
                    f"cop_fallback value reasonable ({cop_fallback})",
                    1.5 <= cop_fallback <= 6.0,
                    f"cop_fallback={cop_fallback} outside reasonable range [1.5, 6.0]",
                    warning=True
                )

        # Check test system config
        test_system_path = self.base_path / 'configs/systems/test_simple_with_network.system.yaml'
        if test_system_path.exists():
            with open(test_system_path, encoding='utf-8') as f:
                test_system = yaml.safe_load(f)

            # Check structure
            self.check(
                "Test system has 'system' key",
                'system' in test_system,
                "Missing 'system:' wrapper in test config"
            )

            # Check thermal_network config
            self.check(
                "Test system has thermal_network config",
                'thermal_network' in test_system,
                "Missing thermal_network configuration"
            )

            if 'thermal_network' in test_system:
                tn_cfg = test_system['thermal_network']
                self.check(
                    "thermal_network.enabled is set",
                    'enabled' in tn_cfg,
                    "Missing thermal_network.enabled"
                )
                self.check(
                    "thermal_network.topology_file is set",
                    'topology_file' in tn_cfg,
                    "Missing thermal_network.topology_file"
                )

        # Check Stadtbach network
        stadtbach_path = self.base_path / 'configs/networks/stadtbach_network.yaml'
        if stadtbach_path.exists():
            with open(stadtbach_path, encoding='utf-8') as f:
                stadtbach = yaml.safe_load(f)

            # Check structure
            required_sections = ['parameters', 'production_plants', 'consumer_zones', 'pipes', 'pipe_catalog']
            for section in required_sections:
                self.check(
                    f"Stadtbach network has '{section}' section",
                    section in stadtbach,
                    f"Missing section '{section}' in stadtbach_network.yaml"
                )

            # Check demand fractions sum to 1.0
            if 'consumer_zones' in stadtbach:
                consumers = stadtbach['consumer_zones']
                total_fraction = sum(c.get('demand_fraction', 0) for c in consumers)
                self.check(
                    f"Demand fractions sum to 1.0 (actual: {total_fraction:.3f})",
                    0.99 <= total_fraction <= 1.01,
                    f"Demand fractions sum to {total_fraction}, should be 1.0",
                    warning=True
                )

                # Check 60/40 split as requested by user
                süd_fraction = sum(
                    c.get('demand_fraction', 0)
                    for c in consumers
                    if 'Süd' in c.get('id', '') or 'Sued' in c.get('id', '')
                )
                nord_fraction = sum(
                    c.get('demand_fraction', 0)
                    for c in consumers
                    if 'Nord' in c.get('id', '')
                )

                logger.info(f"  Süd: {süd_fraction*100:.1f}%, Nord: {nord_fraction*100:.1f}%")
                self.check(
                    f"Süd/Nord split approximately 60/40",
                    0.55 <= süd_fraction <= 0.65 and 0.35 <= nord_fraction <= 0.45,
                    f"Süd={süd_fraction*100:.0f}% Nord={nord_fraction*100:.0f}%, requested was 60%/40%",
                    warning=True
                )

    # ============================================================
    # 4. INTEGRATION CHECKS
    # ============================================================

    def check_integration(self):
        """Check integration with system_builder and runners."""
        logger.info(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        logger.info(f"{Colors.BOLD}4. INTEGRATION CHECKS{Colors.END}")
        logger.info(f"{Colors.BOLD}{'='*60}{Colors.END}")

        # Check system_builder.py integration
        system_builder_path = self.base_path / 'energis/models/system_builder.py'
        if system_builder_path.exists():
            with open(system_builder_path, encoding='utf-8') as f:
                content = f.read()

            # Check imports
            self.check(
                "system_builder imports NetworkManager",
                'from .network_manager import NetworkManager' in content,
                "NetworkManager not imported in system_builder.py"
            )

            # Check outdoor temperature loading
            self.check(
                "system_builder loads outdoor temperature",
                'outdoor_temp' in content and 'T_outdoor' in content,
                "Outdoor temperature not loaded in system_builder.py",
                warning=True
            )

            # Check network manager instantiation
            self.check(
                "system_builder creates NetworkManager",
                'NetworkManager(cfg' in content,
                "NetworkManager not instantiated in system_builder.py"
            )

            # Check network attachment
            self.check(
                "system_builder attaches network to model",
                'attach_to_model' in content and 'network' in content.lower(),
                "Network not attached to model in system_builder.py"
            )

            # Check objective integration
            self.check(
                "Network costs in objective",
                'network_total_pipe_capex' in content or 'network_heat_loss' in content,
                "Network costs might not be in objective function",
                warning=True
            )

        # Check runner compatibility
        runner_files = [
            'energis/run/__main__.py',
            'energis/run/rolling_horizon.py',
            'energis/run/mpc.py',
        ]

        for runner_file in runner_files:
            runner_path = self.base_path / runner_file
            if runner_path.exists():
                with open(runner_path, encoding='utf-8') as f:
                    content = f.read()

                # Runners should use build_model, which handles network automatically
                self.check(
                    f"{runner_file} uses build_model",
                    'build_model' in content,
                    f"{runner_file} might not use build_model",
                    warning=True
                )

    # ============================================================
    # 5. COMPONENT CHECKS
    # ============================================================

    def check_components(self):
        """Check individual components for completeness."""
        logger.info(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        logger.info(f"{Colors.BOLD}5. COMPONENT CHECKS{Colors.END}")
        logger.info(f"{Colors.BOLD}{'='*60}{Colors.END}")

        # Check PipePairBlock
        pipe_pair_path = self.base_path / 'energis/models/blocks/pipe_pair.py'
        if pipe_pair_path.exists():
            with open(pipe_pair_path, encoding='utf-8') as f:
                content = f.read()

            self.check(
                "PipePairBlock has @register_component decorator",
                '@register_component' in content,
                "PipePairBlock missing @register_component"
            )

            self.check(
                "PipePairBlock has attach method",
                'def attach(' in content,
                "PipePairBlock missing attach method"
            )

            # Check key variables
            key_vars = ['m_dot', 'T_supply_in', 'T_supply_out', 'Q_loss', 'Q_delivered']
            for var in key_vars:
                self.check(
                    f"PipePairBlock defines {var}",
                    f'{var}' in content and 'pyo.Var' in content,
                    f"PipePairBlock missing variable {var}",
                    warning=True
                )

            # Check constraints
            key_constraints = ['heat_loss', 'temp_drop', 'heat_balance']
            for constraint in key_constraints:
                self.check(
                    f"PipePairBlock has {constraint} constraint",
                    constraint in content.lower(),
                    f"PipePairBlock might be missing {constraint} constraint",
                    warning=True
                )

        # Check ThermalNodeBlock
        thermal_node_path = self.base_path / 'energis/models/blocks/thermal_node.py'
        if thermal_node_path.exists():
            with open(thermal_node_path, encoding='utf-8') as f:
                content = f.read()

            self.check(
                "ThermalNodeBlock has @register_component decorator",
                '@register_component' in content,
                "ThermalNodeBlock missing @register_component"
            )

            # Check node types
            node_types = ['plant', 'consumer', 'junction']
            for node_type in node_types:
                self.check(
                    f"ThermalNodeBlock handles '{node_type}' type",
                    node_type in content,
                    f"ThermalNodeBlock might not handle {node_type} nodes",
                    warning=True
                )

        # Check NetworkManager
        network_mgr_path = self.base_path / 'energis/models/network_manager.py'
        if network_mgr_path.exists():
            with open(network_mgr_path, encoding='utf-8') as f:
                content = f.read()

            key_methods = [
                '_load_network_topology',
                'attach_to_model',
                'get_results',
                'export_for_dashboard'
            ]

            for method in key_methods:
                self.check(
                    f"NetworkManager has {method} method",
                    f'def {method}' in content,
                    f"NetworkManager missing method {method}",
                    warning=True
                )

    # ============================================================
    # 6. CONSISTENCY CHECKS
    # ============================================================

    def check_consistency(self):
        """Check consistency across components."""
        logger.info(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        logger.info(f"{Colors.BOLD}6. CONSISTENCY CHECKS{Colors.END}")
        logger.info(f"{Colors.BOLD}{'='*60}{Colors.END}")

        # Check temperature ranges are consistent
        stadtbach_path = self.base_path / 'configs/networks/stadtbach_network.yaml'
        if stadtbach_path.exists():
            with open(stadtbach_path, encoding='utf-8') as f:
                stadtbach = yaml.safe_load(f)

            params = stadtbach.get('parameters', {})
            T_supply = params.get('supply_temp_nominal_c', 90)
            T_return = params.get('return_temp_nominal_c', 50)

            self.check(
                f"Supply temp ({T_supply}°C) > Return temp ({T_return}°C)",
                T_supply > T_return,
                f"Supply temp must be > return temp"
            )

            self.check(
                f"Temperature range reasonable",
                40 <= T_return <= 70 and 70 <= T_supply <= 130,
                f"Temperatures outside typical DH range",
                warning=True
            )

        # Check pipe catalog consistency
        test_network_path = self.base_path / 'configs/networks/test_simple_network.yaml'
        if test_network_path.exists():
            with open(test_network_path, encoding='utf-8') as f:
                test_network = yaml.safe_load(f)

            pipe_catalog = test_network.get('pipe_catalog', {})
            pipes = test_network.get('pipes', [])

            for pipe in pipes:
                pipe_id = pipe.get('id')
                current_diameter = pipe.get('current_diameter')

                if current_diameter:
                    diameter_key = f"DN{current_diameter}"
                    self.check(
                        f"Pipe {pipe_id}: {diameter_key} in catalog",
                        diameter_key in pipe_catalog,
                        f"Diameter {diameter_key} not in pipe_catalog for pipe {pipe_id}",
                        warning=True
                    )

    # ============================================================
    # 7. COMPLETENESS CHECKS
    # ============================================================

    def check_completeness(self):
        """Check for missing features or TODO items."""
        logger.info(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        logger.info(f"{Colors.BOLD}7. COMPLETENESS CHECKS{Colors.END}")
        logger.info(f"{Colors.BOLD}{'='*60}{Colors.END}")

        # Features that should be implemented
        features = {
            'Temperature-dependent heat loss': (
                self.base_path / 'energis/models/blocks/pipe_pair.py',
                'T_ground'
            ),
            'Diameter selection': (
                self.base_path / 'energis/models/blocks/pipe_pair.py',
                'diameter_choice'
            ),
            'Insulation options': (
                self.base_path / 'energis/models/blocks/pipe_pair.py',
                'insulation_choice'
            ),
            'Mass flow balance': (
                self.base_path / 'energis/models/blocks/thermal_node.py',
                'mass_balance'
            ),
            'Temperature mixing': (
                self.base_path / 'energis/models/blocks/thermal_node.py',
                'temperature_mixing'
            ),
        }

        for feature, (file_path, keyword) in features.items():
            if file_path.exists():
                with open(file_path, encoding='utf-8') as f:
                    content = f.read()
                self.check(
                    f"Feature implemented: {feature}",
                    keyword in content or keyword.replace('_', ' ') in content.lower(),
                    f"Feature '{feature}' might not be implemented",
                    warning=True
                )

    # ============================================================
    # MAIN RUN METHOD
    # ============================================================

    def run_all_checks(self):
        """Run all checks and print summary."""
        logger.info(f"\n{Colors.BLUE}{Colors.BOLD}")
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║   THERMAL NETWORK SYSTEM CONCEPT CHECK                   ║")
        logger.info("╚══════════════════════════════════════════════════════════╝")
        logger.info(f"{Colors.END}")

        # Run all check groups
        self.check_file_structure()
        self.check_imports()
        self.check_configurations()
        self.check_integration()
        self.check_components()
        self.check_consistency()
        self.check_completeness()

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print final summary."""
        logger.info(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        logger.info(f"{Colors.BOLD}SUMMARY{Colors.END}")
        logger.info(f"{Colors.BOLD}{'='*60}{Colors.END}")

        passed_pct = (self.passed_checks / self.total_checks * 100) if self.total_checks > 0 else 0

        logger.info(f"Total checks: {self.total_checks}")
        logger.info(f"{Colors.GREEN}Passed: {self.passed_checks} ({passed_pct:.1f}%){Colors.END}")

        if self.warnings:
            logger.info(f"{Colors.YELLOW}Warnings: {len(self.warnings)}{Colors.END}")
            for warning in self.warnings:
                logger.info(f"  {Colors.YELLOW}⚠{Colors.END}  {warning}")

        if self.issues:
            logger.info(f"{Colors.RED}Issues: {len(self.issues)}{Colors.END}")
            for issue in self.issues:
                logger.info(f"  {Colors.RED}✗{Colors.END}  {issue}")

        # Overall status
        logger.info(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        if not self.issues:
            logger.info(f"{Colors.GREEN}{Colors.BOLD}✓ SYSTEM READY FOR DEPLOYMENT{Colors.END}")
        elif len(self.issues) <= 3:
            logger.info(f"{Colors.YELLOW}{Colors.BOLD}⚠ SYSTEM MOSTLY READY - FEW ISSUES TO FIX{Colors.END}")
        else:
            logger.info(f"{Colors.RED}{Colors.BOLD}✗ SYSTEM NEEDS WORK - MULTIPLE ISSUES{Colors.END}")
        logger.info(f"{Colors.BOLD}{'='*60}{Colors.END}\n")


if __name__ == '__main__':
    # Get base path
    base_path = Path(__file__).parent.parent

    # Run checks
    checker = SystemConceptChecker(base_path)
    checker.run_all_checks()

    # Exit with appropriate code
    sys.exit(0 if not checker.issues else 1)
