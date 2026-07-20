"""
Phase 1 State Constraints: Test Suite

Quick test to verify Phase 1 constraints are properly integrated and functioning.

Run with: python test_phase1_constraints.py
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_state_constraints_import():
    """Test that state_constraints module imports correctly."""
    logger.info("Test 1: Import state_constraints module")
    try:
        from calion.models.state_constraints import (
            enforce_supply_ge_return_temperature,
            enforce_minimum_pressure,
            enforce_velocity_bounds,
            add_network_state_validation_config,
        )
        logger.info("✓ All functions imported successfully")
        return True
    except ImportError as e:
        logger.error(f"✗ Failed to import: {e}")
        return False


def test_network_validator_import():
    """Test that network_validator module imports correctly."""
    logger.info("\nTest 2: Import network_validator module")
    try:
        from calion.models.network_validator import NetworkValidator, StateValidationIssue
        logger.info("✓ Network validator imported successfully")
        return True
    except ImportError as e:
        logger.error(f"✗ Failed to import: {e}")
        return False


def test_thermal_node_constraints():
    """Test that thermal_node.py includes state constraints."""
    logger.info("\nTest 3: Check thermal_node.py for state constraint integration")
    try:
        thermal_node_path = project_root / 'calion' / 'models' / 'blocks' / 'thermal_node.py'
        content = thermal_node_path.read_text(encoding='utf-8', errors='ignore')
        
        checks = [
            ('enforce_supply_ge_return_temperature import', 'enforce_supply_ge_return_temperature'),
            ('enforce_minimum_pressure import', 'enforce_minimum_pressure'),
            ('Phase 1 state constraints section', 'PHASE 1: STATE CONSTRAINTS'),
        ]
        
        all_passed = True
        for check_name, keyword in checks:
            if keyword in content:
                logger.info(f"  ✓ {check_name}")
            else:
                logger.error(f"  ✗ {check_name} not found")
                all_passed = False
        
        return all_passed
    except Exception as e:
        logger.error(f"✗ Error reading thermal_node.py: {e}")
        return False


def test_pipe_pair_constraints():
    """Test that pipe_pair.py includes state constraints."""
    logger.info("\nTest 4: Check pipe_pair.py for state constraint integration")
    try:
        pipe_pair_path = project_root / 'calion' / 'models' / 'blocks' / 'pipe_pair.py'
        content = pipe_pair_path.read_text(encoding='utf-8', errors='ignore')
        
        checks = [
            ('enforce_velocity_bounds import', 'enforce_velocity_bounds'),
            ('enforce_minimum_pressure import', 'enforce_minimum_pressure'),
            ('Phase 1 state constraints section', 'PHASE 1: STATE CONSTRAINTS'),
        ]
        
        all_passed = True
        for check_name, keyword in checks:
            if keyword in content:
                logger.info(f"  ✓ {check_name}")
            else:
                logger.error(f"  ✗ {check_name} not found")
                all_passed = False
        
        return all_passed
    except Exception as e:
        logger.error(f"✗ Error reading pipe_pair.py: {e}")
        return False


def test_base_yaml_config():
    """Test that base.yaml includes state_validation config."""
    logger.info("\nTest 5: Check base.yaml for state_validation configuration")
    try:
        base_yaml_path = project_root / 'configs' / 'base.yaml'
        content = base_yaml_path.read_text(encoding='utf-8', errors='ignore')
        
        checks = [
            ('state_validation section', 'state_validation:'),
            ('temperature_constraints', 'temperature_constraints:'),
            ('pressure_constraints', 'pressure_constraints:'),
            ('flow_constraints', 'flow_constraints:'),
            ('min_pressure_bar', 'min_pressure_bar:'),
            ('min_velocity_m_s', 'min_velocity_m_s:'),
            ('max_velocity_m_s', 'max_velocity_m_s:'),
        ]
        
        all_passed = True
        for check_name, keyword in checks:
            if keyword in content:
                logger.info(f"  ✓ {check_name}")
            else:
                logger.error(f"  ✗ {check_name} not found")
                all_passed = False
        
        return all_passed
    except Exception as e:
        logger.error(f"✗ Error reading base.yaml: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("=" * 70)
    logger.info("CALION Phase 1 State Constraints — Integration Tests")
    logger.info("=" * 70)
    
    tests = [
        test_state_constraints_import,
        test_network_validator_import,
        test_thermal_node_constraints,
        test_pipe_pair_constraints,
        test_base_yaml_config,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            logger.error(f"✗ Test {test_func.__name__} failed: {e}")
            results.append((test_func.__name__, False))
    
    logger.info("\n" + "=" * 70)
    logger.info("Test Results Summary")
    logger.info("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status:8} — {test_name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n✓ All Phase 1 integration tests passed!")
        return 0
    else:
        logger.error(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
