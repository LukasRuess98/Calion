#!/usr/bin/env python3
"""
Quick integration test script for Phase 1 constraints.
Tests that all components work together without running a full optimization.

Usage:
    python verify_phase1_integration.py
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_imports():
    """Verify all Phase 1 modules import correctly."""
    print("✓ Checking module imports...")
    try:
        from calion.models.state_constraints import (
            enforce_supply_ge_return_temperature,
            enforce_minimum_pressure,
            enforce_velocity_bounds,
            add_network_state_validation_config
        )
        print("  ✓ state_constraints module imported")
        
        from calion.models.network_validator import NetworkValidator, StateValidationIssue
        print("  ✓ network_validator module imported")
        
        return True
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False


def check_config():
    """Verify base.yaml has state_validation section."""
    print("✓ Checking configuration...")
    try:
        import yaml
        config_path = project_root / "configs" / "base.yaml"
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        if 'state_validation' not in config:
            print(f"  ✗ state_validation section not found in base.yaml")
            return False
        
        sv = config['state_validation']
        required_keys = ['temperature_constraints', 'pressure_constraints', 'flow_constraints']
        for key in required_keys:
            if key not in sv:
                print(f"  ✗ Missing {key} in state_validation")
                return False
        
        print(f"  ✓ state_validation config found with {len(required_keys)} sections")
        return True
        
    except Exception as e:
        print(f"  ✗ Config check failed: {e}")
        return False


def check_files_exist():
    """Verify all Phase 1 files exist."""
    print("✓ Checking file existence...")
    
    files_to_check = [
        "calion/models/state_constraints.py",
        "calion/models/network_validator.py",
        "configs/scenarios/phase1_state_constraints_test.yaml",
        "docs/USER_GUIDE.md",
    ]
    
    all_exist = True
    for file_path in files_to_check:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} NOT FOUND")
            all_exist = False
    
    return all_exist


def check_export_integration():
    """Verify export.py has NetworkValidator integration."""
    print("✓ Checking export.py integration...")
    
    try:
        export_path = project_root / "calion" / "run" / "export.py"
        content = export_path.read_text(encoding='utf-8', errors='ignore')
        
        checks = {
            "NetworkValidator import": "from calion.models.network_validator import NetworkValidator",
            "Validator instantiation": "validator = NetworkValidator(",
            "Report export": "validator.export_report(",
            "Validation logging": "[EXPORT] Network state validation",
            "validation_files in result": '"validation_files": validation_files',
        }
        
        all_found = True
        for check_name, pattern in checks.items():
            if pattern.lower() in content.lower() or pattern in content:
                print(f"  ✓ {check_name}")
            else:
                print(f"  ✗ {check_name} not found")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"  ✗ Export check failed: {e}")
        return False


def check_documentation():
    """Verify USER_GUIDE.md has Phase 1 section."""
    print("✓ Checking documentation...")
    
    try:
        user_guide_path = project_root / "docs" / "USER_GUIDE.md"
        content = user_guide_path.read_text(encoding='utf-8', errors='ignore')
        
        checks = {
            "Section 5.4 header": "5.4 Phase 1",
            "Configuration example": "state_validation:",
            "Validation report": "state_validation_report.json",
            "Programmatic usage": "NetworkValidator",
        }
        
        all_found = True
        for check_name, pattern in checks.items():
            if pattern in content:
                print(f"  ✓ {check_name}")
            else:
                print(f"  ✗ {check_name} not found")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"  ✗ Documentation check failed: {e}")
        return False


def main():
    """Run all checks."""
    print("\n" + "="*60)
    print("Phase 1 Integration Verification")
    print("="*60 + "\n")
    
    results = {
        "Module Imports": check_imports(),
        "Configuration": check_config(),
        "Files Exist": check_files_exist(),
        "Export Integration": check_export_integration(),
        "Documentation": check_documentation(),
    }
    
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    
    for check_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All Phase 1 integration checks passed!")
        print("\nNext step: Run test scenario")
        print("  python -m calion.run configs/scenarios/phase1_state_constraints_test.yaml")
        return 0
    else:
        print("\n✗ Some checks failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
