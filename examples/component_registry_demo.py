#!/usr/bin/env python3
"""
Component Registry Demo

Demonstrates how to use the EnerGIS component registry for:
- Discovering available components
- Creating components dynamically
- Inspecting component metadata
- Extending the framework with custom components
"""

from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from energis.models.registry import get_registry, register_component
from energis.models.component import BaseComponent
from energis.models.component_utils import (
    print_component_registry,
    print_component_info,
    get_component_info,
    discover_components_by_category,
)


def demo_1_list_components():
    """Demo 1: List all registered components."""
    print("\n" + "="*80)
    print("DEMO 1: List All Registered Components")
    print("="*80)

    print_component_registry(detailed=False)


def demo_2_inspect_component():
    """Demo 2: Inspect a specific component in detail."""
    print("\n" + "="*80)
    print("DEMO 2: Inspect Heat Pump Component")
    print("="*80)

    print_component_info('heat_pump')


def demo_3_discover_by_category():
    """Demo 3: Discover components by category."""
    print("\n" + "="*80)
    print("DEMO 3: Discover Components by Category")
    print("="*80)

    categories = ['converter', 'storage', 'generic']

    for category in categories:
        components = discover_components_by_category(category)
        print(f"\n{category.upper()}: {len(components)} components")
        for comp in components:
            print(f"  • {comp}")


def demo_4_get_metadata():
    """Demo 4: Get component metadata programmatically."""
    print("\n" + "="*80)
    print("DEMO 4: Get Component Metadata Programmatically")
    print("="*80)

    registry = get_registry()

    print("\nAll registered component types:")
    for comp_type in registry.list_components():
        metadata = registry.get_metadata(comp_type)
        print(f"  • {comp_type:25s} [{metadata['category']}] - {metadata['description'][:50]}")


def demo_5_register_custom_component():
    """Demo 5: Register a custom component type."""
    print("\n" + "="*80)
    print("DEMO 5: Register Custom Component")
    print("="*80)

    # Define custom component
    @register_component(
        "custom_solar_panel",
        category="converter",
        description="Custom solar panel with degradation model",
        version="1.0.0",
        author="Demo User"
    )
    class CustomSolarPanel(BaseComponent):
        def __init__(self, name: str, area_m2: float, efficiency: float, degradation_rate: float = 0.005):
            super().__init__(name)
            self.area_m2 = area_m2
            self.efficiency = efficiency
            self.degradation_rate = degradation_rate

        def attach(self, model, time_set, config, buses):
            # Dummy implementation
            return {
                'flows': {},
                'investment': None,
                'metadata': {
                    'area': self.area_m2,
                    'efficiency': self.efficiency,
                }
            }

        def validate_config(self, config):
            if self.efficiency < 0 or self.efficiency > 1:
                raise ValueError(f"Efficiency must be in [0, 1], got {self.efficiency}")

    print("✅ Custom component 'custom_solar_panel' registered!")
    print("\nComponent info:")
    print_component_info('custom_solar_panel')


def demo_6_create_component_dynamically():
    """Demo 6: Create component instances dynamically."""
    print("\n" + "="*80)
    print("DEMO 6: Create Component Instances Dynamically")
    print("="*80)

    registry = get_registry()

    # Example: Create a storage component dynamically
    print("\nCreating storage component from registry...")

    try:
        # Get component class
        StorageClass = registry.get('storage')
        print(f"  Retrieved class: {StorageClass.__name__}")

        # Create instance (note: this is for demonstration - actual usage requires more parameters)
        # storage = registry.create('storage', name='STORAGE_1', ...)
        print(f"  ✅ Component class ready for instantiation")

    except Exception as e:
        print(f"  ℹ️  Note: {e}")
        print("  (Full instantiation requires all parameters)")


def demo_7_plugin_architecture():
    """Demo 7: Demonstrate plugin architecture concept."""
    print("\n" + "="*80)
    print("DEMO 7: Plugin Architecture Concept")
    print("="*80)

    print("""
The component registry enables a plugin architecture:

1. **Decoupled Components**: Components register themselves via decorators
   - No need to modify core framework code
   - Components can be in separate modules/packages

2. **Dynamic Discovery**: Framework can discover components at runtime
   - List available components
   - Get component metadata
   - Create instances dynamically

3. **Extensibility**: Users can add custom components
   - Implement BaseComponent or Component protocol
   - Add @register_component decorator
   - Component automatically available

4. **Type Safety**: Registry validates component protocol
   - Components must implement required methods
   - Configuration validation
   - Parameter checking

Example workflow:
  1. User creates custom_component.py with @register_component
  2. Import the module: `import custom_component`
  3. Component is automatically registered
  4. Use via registry: `registry.create('custom_type', ...)`
""")

    print("\nBenefits:")
    print("  ✓ No hardcoded component types in system_builder.py")
    print("  ✓ Easy to add new component types")
    print("  ✓ Third-party packages can provide components")
    print("  ✓ Better separation of concerns")


def demo_8_integration_example():
    """Demo 8: Show how registry integrates with existing code."""
    print("\n" + "="*80)
    print("DEMO 8: Integration with Existing Code")
    print("="*80)

    print("""
Current Integration Status:

✅ Component Base Classes:
   - energis/models/component.py defines Component protocol
   - BaseComponent provides default implementations

✅ Component Registry:
   - energis/models/registry.py provides ComponentRegistry
   - Decorator @register_component for auto-registration

✅ Existing Blocks:
   - All blocks use @register_component decorator
   - HeatPumpBlock, StorageBlock, etc. already registered
   - Located in: energis/models/blocks/

✅ Utilities:
   - energis/models/component_utils.py provides helper functions
   - CLI tools for discovery and validation

Future Integration (Optional):
   - system_builder.py could use registry for dynamic component creation
   - Dashboard could list available components from registry
   - Configuration files could reference component types by name

Example (system_builder.py could do):
    ```python
    registry = get_registry()

    # Dynamic component creation
    for hp_config in config['system']['heat_pumps']:
        hp = registry.create('heat_pump',
                            name=hp_config['id'],
                            **hp_config)
        hp.attach(model, time_set, config, buses)
    ```

This is backward-compatible - existing code works unchanged!
""")


def main():
    """Run all demos."""
    print("\n" + "#"*80)
    print("# EnerGIS Component Registry Demonstration")
    print("#"*80)

    demos = [
        demo_1_list_components,
        demo_2_inspect_component,
        demo_3_discover_by_category,
        demo_4_get_metadata,
        demo_5_register_custom_component,
        demo_6_create_component_dynamically,
        demo_7_plugin_architecture,
        demo_8_integration_example,
    ]

    for demo in demos:
        try:
            demo()
            input("\n[Press Enter to continue to next demo...]")
        except KeyboardInterrupt:
            print("\n\nDemo interrupted by user.")
            break
        except Exception as e:
            print(f"\n❌ Error in demo: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "#"*80)
    print("# End of Demonstration")
    print("#"*80)
    print("""
For more information:
  - Component Protocol: energis/models/component.py
  - Registry Implementation: energis/models/registry.py
  - Utility Functions: energis/models/component_utils.py
  - Existing Components: energis/models/blocks/

Try the CLI tools:
  python -m energis.models.component_utils list
  python -m energis.models.component_utils info heat_pump
  python -m energis.models.component_utils export registry_docs.json
""")


if __name__ == '__main__':
    main()
