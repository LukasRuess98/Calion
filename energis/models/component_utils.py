"""Utility functions for working with the component registry.

This module provides helper functions and CLI tools for discovering,
inspecting, and working with registered components.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import json
from pathlib import Path

from .registry import ComponentRegistry, get_registry
from .component import Component


def list_all_components() -> List[Dict[str, Any]]:
    """List all registered components with their metadata.

    Returns:
        List of dictionaries with component information
    """
    registry = get_registry()
    components = []

    for comp_type in registry.list_components():
        metadata = registry.get_metadata(comp_type)
        components.append({
            'type': comp_type,
            'class': metadata['class_name'],
            'module': metadata['module'],
            'category': metadata['category'],
            'description': metadata['description'],
            'version': metadata['version'],
        })

    return components


def print_component_registry(detailed: bool = False):
    """Print a formatted list of all registered components.

    Args:
        detailed: If True, show detailed information for each component
    """
    registry = get_registry()
    components = list_all_components()

    # Group by category
    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for comp in components:
        category = comp['category']
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(comp)

    print("\n" + "="*80)
    print("  EnerGIS Component Registry")
    print("="*80)

    for category, comps in sorted(by_category.items()):
        print(f"\n📂 {category.upper()}")
        print("-" * 80)

        for comp in comps:
            print(f"\n  • {comp['type']}")
            print(f"    Class: {comp['class']}")
            print(f"    Module: {comp['module']}")

            if detailed:
                print(f"    Description: {comp['description']}")
                print(f"    Version: {comp['version']}")

    print("\n" + "="*80)
    print(f"Total: {len(components)} components registered")
    print("="*80 + "\n")


def get_component_info(component_type: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific component.

    Args:
        component_type: Type identifier of the component

    Returns:
        Dictionary with component information, or None if not found
    """
    registry = get_registry()

    if not registry.is_registered(component_type):
        return None

    metadata = registry.get_metadata(component_type)
    component_class = registry.get(component_type)

    # Get __init__ signature
    import inspect
    sig = inspect.signature(component_class.__init__)
    params = {}
    for name, param in sig.parameters.items():
        if name == 'self':
            continue
        params[name] = {
            'required': param.default == inspect.Parameter.empty,
            'default': None if param.default == inspect.Parameter.empty else param.default,
            'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
        }

    return {
        'type': component_type,
        'class_name': metadata['class_name'],
        'module': metadata['module'],
        'category': metadata['category'],
        'description': metadata['description'],
        'version': metadata['version'],
        'author': metadata['author'],
        'parameters': params,
    }


def print_component_info(component_type: str):
    """Print detailed information about a component.

    Args:
        component_type: Type identifier of the component
    """
    info = get_component_info(component_type)

    if not info:
        print(f"❌ Component '{component_type}' not found in registry")
        return

    print("\n" + "="*80)
    print(f"  Component: {info['type']}")
    print("="*80)

    print(f"\nClass:       {info['class_name']}")
    print(f"Module:      {info['module']}")
    print(f"Category:    {info['category']}")
    print(f"Version:     {info['version']}")
    print(f"Author:      {info['author']}")

    if info['description']:
        print(f"\nDescription:\n  {info['description']}")

    print("\nParameters:")
    print("-" * 80)

    required = [p for p, v in info['parameters'].items() if v['required']]
    optional = [p for p, v in info['parameters'].items() if not v['required']]

    if required:
        print("\n  Required:")
        for param in required:
            pinfo = info['parameters'][param]
            print(f"    • {param}: {pinfo['annotation']}")

    if optional:
        print("\n  Optional:")
        for param in optional:
            pinfo = info['parameters'][param]
            default = pinfo['default']
            print(f"    • {param}: {pinfo['annotation']} = {default}")

    print("\n" + "="*80 + "\n")


def validate_component_config(component_type: str, config: Dict[str, Any]) -> List[str]:
    """Validate a configuration dictionary for a component.

    Args:
        component_type: Type identifier of the component
        config: Configuration dictionary to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    registry = get_registry()

    if not registry.is_registered(component_type):
        return [f"Component type '{component_type}' not registered"]

    errors = []

    # Get component class and check required parameters
    component_class = registry.get(component_type)
    import inspect
    sig = inspect.signature(component_class.__init__)

    for name, param in sig.parameters.items():
        if name == 'self':
            continue

        # Check required parameters
        if param.default == inspect.Parameter.empty:
            if name not in config:
                errors.append(f"Missing required parameter: {name}")

    return errors


def export_registry_docs(output_path: Path):
    """Export component registry documentation to JSON.

    Args:
        output_path: Path to write JSON documentation
    """
    components = []

    for comp_type in get_registry().list_components():
        info = get_component_info(comp_type)
        if info:
            components.append(info)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump({
            'version': '1.0',
            'components': components,
        }, f, indent=2, default=str)

    print(f"✅ Exported registry documentation to: {output_path}")


def discover_components_by_category(category: str) -> List[str]:
    """Find all components in a specific category.

    Args:
        category: Category name (e.g., 'converter', 'storage')

    Returns:
        List of component type identifiers in that category
    """
    return get_registry().list_by_category(category)


def create_component_from_config(
    component_type: str,
    config: Dict[str, Any]
) -> Component:
    """Factory function to create a component from configuration.

    Args:
        component_type: Type of component to create
        config: Configuration dictionary with component parameters

    Returns:
        Component instance

    Raises:
        KeyError: If component type not registered
        ValueError: If configuration is invalid
        TypeError: If required parameters missing
    """
    registry = get_registry()

    # Validate config
    errors = validate_component_config(component_type, config)
    if errors:
        raise ValueError(f"Invalid configuration for {component_type}:\n" + "\n".join(f"  - {e}" for e in errors))

    # Create component
    return registry.create(component_type, **config)


# ============================================================================
# CLI Interface
# ============================================================================

def cli_main():
    """Command-line interface for component registry tools."""
    import argparse

    parser = argparse.ArgumentParser(
        description="EnerGIS Component Registry Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List command
    list_parser = subparsers.add_parser('list', help='List all registered components')
    list_parser.add_argument('--detailed', '-d', action='store_true', help='Show detailed information')
    list_parser.add_argument('--category', '-c', help='Filter by category')

    # Info command
    info_parser = subparsers.add_parser('info', help='Show detailed info for a component')
    info_parser.add_argument('component_type', help='Component type identifier')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export registry docs to JSON')
    export_parser.add_argument('output', help='Output file path')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate component configuration')
    validate_parser.add_argument('component_type', help='Component type identifier')
    validate_parser.add_argument('config_file', help='JSON configuration file')

    args = parser.parse_args()

    if args.command == 'list':
        if args.category:
            components = discover_components_by_category(args.category)
            print(f"\nComponents in category '{args.category}':")
            for comp in components:
                print(f"  • {comp}")
        else:
            print_component_registry(detailed=args.detailed)

    elif args.command == 'info':
        print_component_info(args.component_type)

    elif args.command == 'export':
        export_registry_docs(Path(args.output))

    elif args.command == 'validate':
        with open(args.config_file) as f:
            config = json.load(f)

        errors = validate_component_config(args.component_type, config)

        if errors:
            print(f"❌ Validation failed for {args.component_type}:")
            for err in errors:
                print(f"  • {err}")
            return 1
        else:
            print(f"✅ Configuration valid for {args.component_type}")
            return 0

    else:
        parser.print_help()

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(cli_main())
