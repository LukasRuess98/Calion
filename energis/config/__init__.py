"""Configuration loading, merging, and validation.

Public API:

- :func:`load_and_merge` — load one or more YAML files and deep-merge them.
- :func:`validate_config_schema` — lightweight schema checks.
- :class:`EnerGISConfig` — TypedDict describing the merged config shape.
"""

from energis.config.merge import load_and_merge, deep_merge, load_yaml
from energis.config.schema import validate_config_schema
from energis.config.typed_config import EnerGISConfig

__all__ = [
    "load_and_merge",
    "deep_merge",
    "load_yaml",
    "validate_config_schema",
    "EnerGISConfig",
]
