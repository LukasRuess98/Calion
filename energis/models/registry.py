"""
Component registry for EnerGIS framework.

This module provides a registry pattern for component discovery and creation,
enabling a plugin architecture without hardcoded component types.

Inspired by plugin systems in Django, Flask, and other extensible frameworks.
"""
from __future__ import annotations

from typing import Dict, Type, List, Any, Callable
import inspect

from .component import Component


class ComponentRegistry:
    """
    Central registry for all available components.

    This class manages registration and discovery of component types,
    enabling a plugin architecture where new components can be added
    without modifying core framework code.

    Usage:
        # Register a component class
        ComponentRegistry.register("heat_pump", HeatPumpBlock)

        # Or use decorator
        @register_component("heat_pump")
        class HeatPumpBlock(BaseComponent):
            pass

        # Create component instance
        hp = ComponentRegistry.create("heat_pump", name="HP1", ...)

        # List available components
        components = ComponentRegistry.list_components()
    """

    _components: Dict[str, Type[Component]] = {}
    _metadata: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(
        cls,
        component_type: str,
        component_class: Type[Component],
        *,
        description: str = None,
        category: str = None,
        version: str = None,
        author: str = None
    ) -> None:
        """
        Register a component class.

        Args:
            component_type: Unique identifier for the component type
            component_class: Component class to register
            description: Human-readable description (optional)
            category: Component category (e.g., "converter", "storage")
            version: Component version (optional)
            author: Component author (optional)

        Raises:
            ValueError: If component_type is already registered
            TypeError: If component_class doesn't implement Component protocol
        """
        if component_type in cls._components:
            raise ValueError(
                f"Component type '{component_type}' is already registered. "
                f"Use unregister() first if you want to replace it."
            )

        # Validate that class implements Component protocol
        # (duck typing check - we just verify it has the required methods)
        required_methods = ['attach', 'get_results', 'validate_config']
        for method in required_methods:
            if not hasattr(component_class, method):
                raise TypeError(
                    f"Component class {component_class.__name__} must implement "
                    f"method '{method}' to satisfy Component protocol"
                )

        cls._components[component_type] = component_class

        # Store metadata
        cls._metadata[component_type] = {
            'class_name': component_class.__name__,
            'module': component_class.__module__,
            'description': description or component_class.__doc__ or '',
            'category': category or 'generic',
            'version': version or '1.0.0',
            'author': author or 'unknown',
        }

    @classmethod
    def unregister(cls, component_type: str) -> None:
        """
        Unregister a component type.

        Args:
            component_type: Component type to unregister

        Raises:
            KeyError: If component_type is not registered
        """
        if component_type not in cls._components:
            raise KeyError(f"Component type '{component_type}' is not registered")

        del cls._components[component_type]
        del cls._metadata[component_type]

    @classmethod
    def get(cls, component_type: str) -> Type[Component]:
        """
        Get component class by type.

        Args:
            component_type: Component type identifier

        Returns:
            Component class

        Raises:
            KeyError: If component type not found
        """
        if component_type not in cls._components:
            available = ', '.join(cls._components.keys())
            raise KeyError(
                f"Component type '{component_type}' not found in registry. "
                f"Available types: {available}"
            )

        return cls._components[component_type]

    @classmethod
    def create(cls, component_type: str, **kwargs) -> Component:
        """
        Factory method to create component instance.

        Args:
            component_type: Type of component to create
            **kwargs: Arguments passed to component __init__

        Returns:
            Component instance

        Raises:
            KeyError: If component type not found
            TypeError: If kwargs don't match component __init__ signature
        """
        component_class = cls.get(component_type)

        try:
            return component_class(**kwargs)
        except TypeError as e:
            # Provide helpful error message with expected parameters
            sig = inspect.signature(component_class.__init__)
            params = [
                f"{name}={param.default if param.default != inspect.Parameter.empty else '...'}"
                for name, param in sig.parameters.items()
                if name != 'self'
            ]
            expected = ', '.join(params)
            raise TypeError(
                f"Error creating {component_type}: {e}\n"
                f"Expected parameters: {expected}"
            ) from e

    @classmethod
    def list_components(cls) -> List[str]:
        """
        List all registered component types.

        Returns:
            List of component type identifiers
        """
        return list(cls._components.keys())

    @classmethod
    def get_metadata(cls, component_type: str) -> Dict[str, Any]:
        """
        Get metadata for a component type.

        Args:
            component_type: Component type identifier

        Returns:
            Dictionary with metadata

        Raises:
            KeyError: If component type not found
        """
        if component_type not in cls._metadata:
            raise KeyError(f"Component type '{component_type}' not found")

        return cls._metadata[component_type].copy()

    @classmethod
    def list_by_category(cls, category: str) -> List[str]:
        """
        List components in a specific category.

        Args:
            category: Category name

        Returns:
            List of component types in that category
        """
        return [
            comp_type
            for comp_type, metadata in cls._metadata.items()
            if metadata['category'] == category
        ]

    @classmethod
    def is_registered(cls, component_type: str) -> bool:
        """
        Check if a component type is registered.

        Args:
            component_type: Component type to check

        Returns:
            True if registered, False otherwise
        """
        return component_type in cls._components

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered components.

        WARNING: This is mainly for testing. Use with caution.
        """
        cls._components.clear()
        cls._metadata.clear()

    @classmethod
    def get_all_metadata(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for all registered components.

        Returns:
            Dictionary mapping component types to their metadata
        """
        return cls._metadata.copy()


def register_component(
    component_type: str,
    *,
    description: str = None,
    category: str = None,
    version: str = None,
    author: str = None
) -> Callable[[Type[Component]], Type[Component]]:
    """
    Decorator for automatic component registration.

    This decorator automatically registers a component class when the module
    is imported, enabling a plugin architecture.

    Usage:
        @register_component("heat_pump", category="converter")
        class HeatPumpBlock(BaseComponent):
            pass

    Args:
        component_type: Unique identifier for the component type
        description: Human-readable description (optional)
        category: Component category (optional)
        version: Component version (optional)
        author: Component author (optional)

    Returns:
        Decorator function
    """
    def decorator(cls: Type[Component]) -> Type[Component]:
        ComponentRegistry.register(
            component_type,
            cls,
            description=description,
            category=category,
            version=version,
            author=author
        )
        return cls

    return decorator


# Convenience aliases
register = register_component
get_component = ComponentRegistry.get
create_component = ComponentRegistry.create
list_components = ComponentRegistry.list_components
