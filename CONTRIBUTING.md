# Contributing to EnerGIS

Thank you for considering a contribution to EnerGIS! This document explains
how to set up a development environment, run tests, and submit changes.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/LukasRuess98/Planing-Framework-for-Heat.git
cd Planing-Framework-for-Heat

# Create a virtual environment (Python 3.10+)
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows

# Install in editable mode with all dev dependencies
pip install -e ".[all]"
```

## Running Tests

```bash
# Run the full test suite with coverage
python -m pytest tests/

# Run a specific test file
python -m pytest tests/test_results.py -v

# Run with coverage report
python -m pytest tests/ --cov=energis --cov-report=html
```

The CI pipeline requires a minimum of 30 % line coverage.

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting:

```bash
ruff check energis/
ruff format energis/   # auto-format
```

Key conventions:
- Line length: 100 characters
- Python 3.10+ type annotations (`X | None` instead of `Optional[X]`)
- No unused imports or variables
- Docstrings follow NumPy style

## Project Structure

```
energis/
├── api.py                  # High-level convenience API
├── network.py              # Programmatic Network builder (PyPSA-style)
├── constants.py            # Centralised physical constants
├── config/                 # YAML loading, merging, validation
│   ├── merge.py            # load_and_merge(), deep_merge()
│   ├── schema.py           # Lightweight schema validation
│   └── typed_config.py     # TypedDict definitions
├── models/                 # Pyomo optimisation model
│   ├── blocks/             # Component implementations (heat pump, storage, …)
│   ├── system_builder.py   # Model construction pipeline
│   ├── results.py          # Structured result containers
│   └── component.py        # Component protocol & base class
├── run/                    # Workflow execution
│   ├── workflow.py         # run_workflow() orchestrator
│   ├── rh_engine.py        # Rolling horizon engine
│   ├── solver.py           # Solver invocation wrapper
│   └── types.py            # Shared dataclasses
├── io/                     # Import / export / plotting
├── utils/                  # Timeseries, YAML parser, helpers
└── validation/             # Analytical benchmarks for publications
```

## Adding a New Component

1. Create a file in `energis/models/blocks/` (e.g. `my_component.py`).
2. Subclass `BaseComponent` and implement the `Component` protocol.
3. Decorate with `@register_component("my_component")`.
4. Import the class in `energis/models/__init__.py` so the decorator fires.
5. Add tests in `tests/test_my_component.py`.

See `energis/models/blocks/heat_pump.py` for a reference implementation.

## Submitting Changes

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Write tests for new functionality.
3. Ensure `pytest` passes and coverage does not decrease.
4. Run `ruff check energis/` — no errors allowed.
5. Open a Pull Request against `main`.

## Reporting Issues

Please use [GitHub Issues](https://github.com/LukasRuess98/Planing-Framework-for-Heat/issues)
with one of the following labels:
- **bug** — something broken
- **enhancement** — feature request
- **documentation** — docs improvement

## Citation

If you use EnerGIS in academic work, please cite:

```bibtex
@software{energis2026,
  author  = {Ruess, Lukas},
  title   = {EnerGIS: Modular MILP Framework for Industrial Heat Network Planning},
  year    = {2026},
  url     = {https://github.com/LukasRuess98/Planing-Framework-for-Heat}
}
```

See also `CITATION.cff` in the repository root.
