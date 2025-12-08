#!/usr/bin/env python3
"""
Test script for Excel parser - Windows compatible
"""

from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser

def main():
    print("\n" + "="*80)
    print("EXCEL PARSER TEST")
    print("="*80 + "\n")

    # Test 1: Parse template
    print("Test 1: Parsing test_network.xlsx...")
    try:
        parser = ThermalNetworkExcelParser('test_network.xlsx')
        print("✓ Parser created successfully!")
    except FileNotFoundError:
        print("❌ File 'test_network.xlsx' not found!")
        print("   Run: python scripts/create_thermal_network_template.py -o test_network.xlsx")
        return
    except Exception as e:
        print(f"❌ Error creating parser: {e}")
        return

    # Test 2: Get summary
    print("\nTest 2: Getting summary...")
    try:
        summary = parser.get_summary()
        print("✓ Summary retrieved:")
        print(f"   Network name: {summary.get('network_name', 'N/A')}")
        print(f"   Producers: {summary.get('num_producers', 0)}")
        print(f"   Storage: {summary.get('num_storage', 0)}")
        print(f"   Pipes: {summary.get('num_pipes', 0)}")
        print(f"   Consumers: {summary.get('num_consumers', 0)}")
        print(f"   Timeseries columns: {summary.get('num_timeseries_columns', 0)}")
    except Exception as e:
        print(f"❌ Error getting summary: {e}")

    # Test 3: Validation
    print("\nTest 3: Validating configuration...")
    try:
        errors = parser.validate()
        if errors:
            print(f"❌ Validation failed with {len(errors)} error(s):")
            for i, error in enumerate(errors[:5], 1):  # Show first 5
                print(f"   {i}. {error}")
            if len(errors) > 5:
                print(f"   ... and {len(errors)-5} more errors")
        else:
            print("✓ Validation passed! No errors found.")
    except Exception as e:
        print(f"❌ Error during validation: {e}")

    # Test 4: Save YAML (only if valid)
    if not errors:
        print("\nTest 4: Saving YAML...")
        try:
            output_path = "test_network.scenario.yaml"
            parser.save_yaml(output_path)
            print(f"✓ YAML saved to: {output_path}")
        except Exception as e:
            print(f"❌ Error saving YAML: {e}")
    else:
        print("\nTest 4: Skipped (validation errors present)")
        print("   Fix errors in test_network.xlsx and run again")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")

if __name__ == '__main__':
    main()
