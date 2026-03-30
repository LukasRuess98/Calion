"""Configuration loading, merging, and validation.

Public API:

- :func:`load_and_merge` — load one or more YAML files and deep-merge them.
- :func:`validate_config_schema` — lightweight schema checks.
- :class:`CALIONConfig` — TypedDict describing the merged config shape.
"""

from calion.config.merge import load_and_merge, deep_merge, load_yaml
from calion.config.schema import validate_config_schema
from calion.config.typed_config import CALIONConfig

__all__ = [
    "load_and_merge",
    "deep_merge",
    "load_yaml",
    "validate_config_schema",
    "CALIONConfig",
]
