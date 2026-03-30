from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import List, Dict, Any

from calion.utils import simple_yaml
from calion.config.schema import validate_config_schema

import logging as _logging

_logger = _logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config key normalisation
# ---------------------------------------------------------------------------

# Maps (section_path, legacy_key) → canonical_key.
# Applied once at load time so downstream code only needs to check one name.
_KEY_ALIASES: List[tuple] = [
    # SOC initial value: canonical = soc_init_mwh
    ("system.storage", "SOC_init", "soc_init_mwh"),
    ("system.storage", "soc0_mwh", "soc_init_mwh"),
    # Rolling horizon: canonical = lowercase
    ("scenario.rolling_horizon", "HEAT_HORIZON_HOURS", "heat_horizon_hours"),
    ("scenario.rolling_horizon", "STEP_HOURS", "step_hours"),
    ("scenario.rolling_horizon", "OVERLAP_HOURS", "overlap_hours"),
    ("scenario.rolling_horizon", "TERMINAL_POLICY", "terminal_policy"),
    ("scenario.rolling_horizon", "window_hours", "heat_horizon_hours"),
]


def _navigate(cfg: dict, dotpath: str) -> dict | None:
    """Traverse nested dicts by dot-separated path, returning the leaf dict."""
    node = cfg
    for key in dotpath.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node if isinstance(node, dict) else None


def normalise_config_keys(cfg: dict) -> dict:
    """Copy legacy alias values to their canonical keys.

    This runs **in-place** on *cfg* after merge but before consumption.
    Both legacy and canonical keys are kept so that code which still reads
    the old name continues to work during the migration period.
    """
    for dotpath, legacy, canonical in _KEY_ALIASES:
        section = _navigate(cfg, dotpath)
        if section is None:
            continue
        if legacy in section and canonical not in section:
            section[canonical] = section[legacy]
            _logger.debug(
                "Config alias: %s.%s → %s.%s",
                dotpath, legacy, dotpath, canonical,
            )

    # Also normalise inputs.SOC_init → inputs.soc_init_mwh
    inputs = cfg.get("inputs")
    if isinstance(inputs, dict):
        if "SOC_init" in inputs and "soc_init_mwh" not in inputs:
            inputs["soc_init_mwh"] = inputs["SOC_init"]

    return cfg


def deep_merge(a: dict, b: dict) -> dict:
    """Recursively merge mapping ``b`` into ``a`` without mutating inputs."""

    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out

def load_yaml(path: str) -> dict:
    """Load YAML using the light-weight parser.

    PyYAML is not available in the execution environment.  The configuration
    files only rely on a tiny subset of the YAML specification, therefore we
    can use :mod:`calion.utils.simple_yaml` which is purposely written for this
    repository.
    """

    data = simple_yaml.load(path)
    if not isinstance(data, dict):
        raise TypeError(f"Expected mapping at document root in {path!r}.")
    return data


def load_yaml_with_inheritance(path: str, _visited: set = None) -> dict:
    """Load YAML with support for _extends: inheritance.

    If a config contains "_extends: parent.yaml", it will:
    1. Load the parent config first
    2. Merge the current config on top
    3. Remove the _extends key from the result

    Supports both single parent and list of parents:
        _extends: base.yaml
        _extends: [base.yaml, overrides.yaml]

    Prevents circular dependencies by tracking visited files.
    """

    if _visited is None:
        _visited = set()

    # Prevent circular dependencies
    abs_path = str(_resolve_config_path(path))
    if abs_path in _visited:
        raise ValueError(f"Circular dependency detected: {abs_path}")
    _visited.add(abs_path)

    # Load current config
    data = load_yaml(path)

    # Check for _extends key
    if "_extends" not in data:
        return data

    # Get parent config(s)
    extends = data.pop("_extends")  # Remove _extends from result

    # Convert single parent to list
    if isinstance(extends, str):
        extends = [extends]

    if not isinstance(extends, list):
        raise TypeError(f"_extends must be string or list, got {type(extends)}")

    # Resolve parent paths relative to current config directory
    config_dir = Path(path).parent

    # Load and merge all parents (left to right)
    result = {}
    for parent_path in extends:
        # Resolve relative to current config's directory
        if not Path(parent_path).is_absolute():
            parent_path = str(config_dir / parent_path)

        parent_data = load_yaml_with_inheritance(parent_path, _visited)
        result = deep_merge(result, parent_data)

    # Merge current config on top of parents
    result = deep_merge(result, data)

    return result

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_config_path(path: str) -> Path:
    """Resolve ``path`` to an existing configuration file.

    Relative paths are first resolved against the current working directory
    (allowing callers to keep the old behaviour).  If that fails we fall back
    to the project root so that notebooks or scripts executed from nested
    directories can continue to refer to configs using repository-relative
    paths.
    """

    candidate = Path(path)
    if candidate.is_absolute():
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Config not found: {candidate}")

    search_roots = [Path.cwd()]
    if PROJECT_ROOT not in search_roots:
        search_roots.append(PROJECT_ROOT)

    for root in search_roots:
        resolved = (root / candidate).resolve()
        if resolved.exists():
            return resolved

    raise FileNotFoundError(f"Config not found: {(Path.cwd() / candidate).resolve()}")


def load_and_merge(paths: List[str], enable_inheritance: bool = True) -> Dict[str,Any]:
    """Load and merge multiple config files.

    Args:
        paths: List of config file paths to merge (left to right)
        enable_inheritance: If True, support _extends: syntax (default: True)

    Returns:
        Merged configuration dictionary with metadata
    """
    cfg = {}
    norm = []
    load_fn = load_yaml_with_inheritance if enable_inheritance else load_yaml

    for p in paths:
        if p is None:
            continue
        resolved = _resolve_config_path(p)
        norm.append(str(resolved))
        cfg = deep_merge(cfg, load_fn(str(resolved)))

    # compute hash for provenance
    h = hashlib.sha256()
    for p in norm:
        with open(p, "rb") as f:
            h.update(f.read())

    cfg["meta"] = cfg.get("meta", {})
    cfg["meta"]["config_hash"] = h.hexdigest()[:16]
    cfg["meta"]["merged_from"] = norm
    cfg["meta"]["inheritance_enabled"] = enable_inheritance

    validate_config_schema(cfg)
    normalise_config_keys(cfg)
    return cfg
