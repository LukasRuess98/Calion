# EnerGIS – Modular MILP Framework (Fuel Buses enabled)

This package contains a minimal, runnable skeleton to model industrial energy systems with **explicit fuel buses**.
It keeps the structure close to oemof/pypsa (configs, components, buses, orchestrator) and your previous monolithic code.

## Motivation & Forschungsfragen
- EnerGIS digitalisiert eine bestehende Stadtbach-Referenz, um Wartbarkeit, Transparenz und CI-basierte Validierung für Fern- und Nahwärmenetze sicherzustellen.
- Forschungsfragen und Paper-Skopierung sind in [`docs/paper_outline.md`](docs/paper_outline.md) skizziert: Wie nah kommt die modulare PF→RH-Architektur an die Legacy-Ergebnisse, welche Modellierungsentscheidungen treiben Abweichungen, und wie wird die Validierung automatisiert?

## Highlights
- YAML config-layer with merge order (base → tech_catalog → site → system → scenario → overrides.local)
- Explicit **buses**: `electricity`, `heat`, `gas`, `biomass`, `waste`
- Modular components (blocks): HeatPump, Storage, ThermalGenerator, P2H
- PF + RH orchestration and single Excel export
- Tests that build a tiny model and check bus balances (skipped if Pyomo missing)
- Kurzgefasste Formulierungsdetails: siehe [`docs/methodology.md`](docs/methodology.md)

## Quickstart
1. Put your `Import_Data.xlsx` in the repo root or change the path in `configs/sites/default.site.yaml`.
2. Install deps:
   ```bash
   pip install pyomo openpyxl pandas numpy pyyaml pytest
   # Optional solvers: gurobi / highs / glpk (fallback to glpk if available)
   ```
3. Run quick test:
   ```bash
   python quickstart_test.py
   ```
4. Execute a configurable PF/RH workflow without writing exports:
   ```bash
   python -m energis.run.rolling_horizon \
       configs/base.yaml \
       configs/tech_catalog.yaml \
       configs/sites/default.site.yaml \
       configs/systems/baseline.system.yaml \
       configs/scenarios/pf_then_rh.workflow.scenario.yaml \
       --print-design \
       --run-mode PF_THEN_RH \
       --heat-horizon-hours 168 \
       --step-hours 24 \
       --terminal-policy free
   ```
   All CLI flags have matching environment variables (`RUN_MODE`, `HEAT_HORIZON_HOURS`, `STEP_HOURS`,
   `TERMINAL_POLICY`, `FIX_DESIGN`, `PF_DESIGN_JSON`, `INCLUDE_GRIDCOST_IN_ENERGY`,
   `INCLUDE_DEMAND_CHARGE_IN_RH`, `INCLUDE_CO2_COST_IN_OBJECTIVE`) so the workflow can be steered by
   CI pipelines or notebooks without modifying YAML files. Additional helpers:
   - `--rh-window-hours`/`--heat-horizon-hours` and `--rh-overlap-hours` allow explicit control of window length and overlap.
   - Sensitivity sweeps for RH settings use comma-separated lists: e.g. `--sensitivity-horizon-hours 72,168 --sensitivity-overlap-hours 0,6` runs multiple PF→RH combinations sequentially.
5. Interaktive Notebooks (siehe `notebooks/`):
   - **`runner.ipynb`** - Haupteinstiegspunkt für Optimierungsläufe (PF/RH)
   - **`scenario_studio.ipynb`** - Interaktives Dashboard mit detaillierten Visualisierungen
   - **`synthetic_example.ipynb`** - Beispiel mit synthetischen Daten
   - **`validation.ipynb`** - Validierung gegen Legacy-Referenz

### Case study exports

Use the convenience wrapper to run the PF→RH workflow, export Excel/JSON bundles and plot images into `artifacts/`:

```bash
./scripts/run_case_study.sh
```

Optional overrides:
- Pass an alternative config list as arguments to the script.
- `CASE_TAG=mytag` adjusts the folder suffix, `ARTIFACT_ROOT=/tmp/out` changes the export root.

### Validierung (Stadtbach-Referenz)

- Der Test [`tests/test_stadtbach_validation.py`](tests/test_stadtbach_validation.py) führt einen 24h-Stadtbach-Lauf gegen die Legacy-Referenz aus, erstellt eine Kennzahlentabelle EnerGIS vs. Legacy und exportiert sie (CSV) für Artefakte.
- Notebook [`notebooks/validation.ipynb`](notebooks/validation.ipynb) repliziert den Lauf interaktiv; die Ergebnis-Tabelle landet in `notebooks/exports/stadtbach_validation.csv`.

### Configuration quick reference

The default `configs/base.yaml` now ships sane defaults for the rolling horizon settings and cost flags:

```yaml
scenario:
  run_mode: PF_ONLY
  fix_design: false
  rolling_horizon:
    heat_horizon_hours: 168.0
    step_hours: 24.0
    terminal_policy: free

costs:
  include_gridcost_in_energy: true
  include_demand_charge_in_rh: true
  include_co2_cost_in_objective: true
```

Individual scenarios can override these entries (see `configs/scenarios/`).  When `PF_THEN_RH` is used
without executing a PF step, point `scenario.pf_design_json` to a previously exported `pf_design.json` so
that the design fixation step can reuse those capacities. Missing design files are detected and reported
gracefully.

Exports go to `exports/<timestamp>_<tag>/scenario.xlsx`.

## Architecture & Documentation

EnerGIS uses a **v2.0 component-based architecture** inspired by Oemof and PyPSA:

- **[ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)** - Technical architecture reference (Component Protocol, BaseComponent, Bus abstraction, Registry pattern)
- **[MIGRATION_GUIDE_V2.md](MIGRATION_GUIDE_V2.md)** - Migration guide for v1.0 → v2.0 (100% backward compatible)
- **[docs/archive/](docs/archive/)** - Historical analysis and implementation reports

### Key Features (v2.0)

- ✅ **Plugin Architecture** - Add custom components via `@register_component` decorator
- ✅ **Type Safety** - Full type hints with `typing.Protocol` for IDE support
- ✅ **Explicit Flows** - Flow objects replace implicit dictionary returns
- ✅ **Bus Abstraction** - Buses as first-class objects with capacity limits and loss factors
- ✅ **Backward Compatible** - All v1.0 code works unchanged

See `examples/custom_component_example.py` for a complete guide on adding new components.
