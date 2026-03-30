# Changelog

All notable changes to EnerGIS are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0-alpha] — 2026-03-28

First tagged release. Marks the completion of a major architectural
refactoring and cleanup pass on the research prototype.

### Added
- Unified CLI entry point via `python -m energis.run` (`energis/run/__main__.py`)
- `energis/io/_output_paths.py` — canonical `outputs/{runs,workflows,dashboard}/`
  path resolution with automatic legacy-path detection and `DeprecationWarning`
- `scripts/migrate_outputs.py` — dry-run/move/copy migration tool for legacy
  `exports/`, `results/`, `saved_workflows/` directories
- `energis/io/_utils.py` — shared `_is_empty()` helper (consolidates duplicate
  implementations in `loader.py` and `network_loader.py`)
- `configs/05_networks/multi_temperature_network.yaml` — example multi-temperature
  network (90/55 °C HT + 60/40 °C LT with heat exchanger)
- `archive/` directory for development artifacts (debug scripts, validation docs,
  legacy data)

### Changed
- **Output paths**: all default export paths updated from `exports/` to
  `outputs/runs/`; saved workflows from `notebooks/saved_workflows/` to
  `outputs/workflows/`
- **Design API**: removed deprecated `DesignConfig` / `load_design_config` /
  `load_design_for_scenario` / `extract_design_from_summary` / `save_design_to_file`
  from `energis/design.py`; callers (`workflow.py`, `rh_engine.py`, `types.py`)
  migrated to `OptimizationConfig` / `load_optimization_config` /
  `extract_optimization_results` / `save_optimization_results`
- **Exception handling**: all `except Exception` blocks narrowed to specific types
  (`ImportError`, `ValueError`, `TypeError`, `AttributeError`, `OSError`, etc.)
- **Python requirement**: `>=3.8` → `>=3.10` (aligned `setup.py` with `pyproject.toml`)
- **`setup.py`** reduced to a minimal shim; `pyproject.toml` is the single source
  of truth for all packaging metadata
- **Ruff ruleset** extended with `B` (bugbear), `UP` (pyupgrade), `RUF` rules
- **Line-length** harmonised to 100 across Ruff, Black, isort, and flake8

### Removed
- `configs/examples/` directory (all templates moved to `configs/templates/`)
- Dead `unified_assets_to_legacy_system()` converter
- Root-level debug and diagnostic scripts (archived under `archive/debug_scripts/`)
- Root-level validation/analysis scripts (archived under `archive/validation_scripts/`)
- Root-level development documents (archived under `archive/dev_docs/`)
- Stale solver LP files (`debug_lp.lp`, `debug_model.lp`, `star_debug.lp`)

### Fixed
- Infeasibility in `configs/templates/level3_30node_template.yaml` (synthetic data,
  demand-fraction approach)
- `thermal_network_exporter.py` Pyomo uninitialized-variable warnings (added `_val()`)
- All `configs/examples/` path references in diagnose scripts → `configs/templates/`

---

## Earlier development (untagged)

The commits below represent the initial research prototype development.
No semantic versioning was applied during this phase.

| Commit | Summary |
|--------|---------|
| `42f40ae` | Unified config system and multi-node DHN model support |
| `c79f9d2` | Replace `rolling_horizon` monolith with modular orchestrator |
| `9179e77` | Extract run-layer foundation modules |
| `c8961e9` | Multi-node DHN physics, validation hardening, export fixes |
| `f10204d` | Dedicated multi-network export module |
| `d8b73b1` | Decompose `NetworkManager.attach_to_model()` |
| `6fef9cb` | Extract `ModelFinalizer` from `build_model()` |
| `fb718e1` | Extract `ComponentAssembler` from `build_model()` |
| `68ff53a` | Extract service layer and utility modules |
