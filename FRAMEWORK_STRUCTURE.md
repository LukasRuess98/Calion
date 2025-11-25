# EnerGIS Framework - Struktur & Architektur

## 🏗️ Haupt-Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│                    EnerGIS Framework v2.0                        │
│                                                                   │
│  ┌──────────────────┐    ┌──────────────────┐                  │
│  │  User Interface  │    │   Configuration   │                  │
│  ├──────────────────┤    ├──────────────────┤                  │
│  │ • runner.ipynb   │    │ • base.yaml       │                  │
│  │ • scenario_studio│    │ • tech_catalog    │                  │
│  │ • CLI (__main__) │    │ • scenarios/      │                  │
│  └────────┬─────────┘    └────────┬─────────┘                  │
│           │                       │                              │
│           v                       v                              │
│  ┌─────────────────────────────────────────┐                   │
│  │         Workflow Orchestration           │                   │
│  ├─────────────────────────────────────────┤                   │
│  │ rolling_horizon.py (v2.0) ✅ PRIMARY    │                   │
│  │ orchestrator.py (v1.0)    ⚠️  DEPRECATED│                   │
│  │ mpc.py                                   │                   │
│  └─────────────┬───────────────────────────┘                   │
│                │                                                 │
│                v                                                 │
│  ┌─────────────────────────────────────────┐                   │
│  │         Model Building Layer             │                   │
│  ├─────────────────────────────────────────┤                   │
│  │ system_builder.py (822 lines)           │                   │
│  │  ├─ Build Pyomo model                   │                   │
│  │  ├─ Component instantiation              │                   │
│  │  └─ Constraint setup                     │                   │
│  └─────────────┬───────────────────────────┘                   │
│                │                                                 │
│                v                                                 │
│  ┌─────────────────────────────────────────┐                   │
│  │         Component Blocks                 │                   │
│  ├─────────────────────────────────────────┤                   │
│  │ blocks/                                  │                   │
│  │  ├─ heat_pump.py                         │                   │
│  │  ├─ storage.py                           │                   │
│  │  ├─ stratified_storage.py                │                   │
│  │  ├─ thermal_gen.py                       │                   │
│  │  └─ p2h.py                               │                   │
│  └─────────────┬───────────────────────────┘                   │
│                │                                                 │
│                v                                                 │
│  ┌─────────────────────────────────────────┐                   │
│  │         I/O & Export Layer               │                   │
│  ├─────────────────────────────────────────┤                   │
│  │ io/                                      │                   │
│  │  ├─ loader.py (data input)               │                   │
│  │  ├─ exporter.py (basic exports)          │                   │
│  │  ├─ plotter.py (simple plots)    ⚠️ DUP │                   │
│  │  ├─ publication_plotter.py       ⚠️ DUP │                   │
│  │  ├─ publication_exporter.py              │                   │
│  │  └─ applied_energies_exporter.py         │                   │
│  └─────────────────────────────────────────┘                   │
│                                                                   │
└───────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory-Abhängigkeiten

### Core Dependencies Flow

```
configs/*.yaml
    │
    ├──> config/merge.py (load_and_merge)
    │        │
    │        v
    │    run/rolling_horizon.py
    │        │
    │        ├──> models/system_builder.py
    │        │        │
    │        │        ├──> models/blocks/*.py
    │        │        │        │
    │        │        │        └──> models/bus.py
    │        │        │
    │        │        └──> models/component.py (protocols)
    │        │
    │        ├──> io/loader.py
    │        │        │
    │        │        └──> utils/timeseries.py
    │        │
    │        └──> io/exporter.py
    │                 │
    │                 ├──> io/plotter.py
    │                 └──> utils/xlsx.py
    │
    └──> forecasting/*.py (for MPC)
```

### Critical Path (Hot Path)

```
User → Notebook
    → rolling_horizon.run_workflow()
        → load_and_merge(configs)
        → load_input_excel()
        → build_model()
            → Component blocks instantiation
            → Pyomo model construction
        → Solver execution
        → export_workflow_results()
            → write CSV/Excel/JSON
            → generate plots
```

---

## 🔴 **PROBLEM AREAS** (Code Smells)

### 1. Code Duplication Hotspots

```
HIGH SEVERITY:
├─ io/plotter.py (335 lines)
│  └─ vs publication_plotter.py (1,216 lines)
│     └─ OVERLAP: ~300 lines (~25%)
│        ├─ _has_content() - EXACT DUPLICATE
│        ├─ _prettify_label() - NEAR DUPLICATE
│        ├─ _configure_time_axis() - NEAR DUPLICATE
│        └─ Plot functions - PATTERN DUPLICATE
│
├─ models/blocks/*.py
│  └─ setattr/getattr pattern: 117 occurrences
│     └─ Component variable creation
│        ├─ heat_pump.py: 23 occurrences
│        ├─ storage.py: 31 occurrences
│        ├─ stratified_storage.py: 28 occurrences
│        └─ thermal_gen.py: 19 occurrences
│
└─ io/exporter*.py
   └─ Three export modules with overlapping logic
      ├─ exporter.py (684 lines)
      ├─ publication_exporter.py (851 lines)
      └─ applied_energies_exporter.py (906 lines)
         └─ CSV/Excel writing repeated
```

### 2. Deprecated Code

```
⚠️  TECHNICAL DEBT:
├─ run/orchestrator.py (1,260 lines)
│  ├─ Status: DEPRECATED since v2.0
│  ├─ Still imported by: __main__.py
│  ├─ Wrapper: run_all() → rolling_horizon.run_workflow()
│  └─ Risk: Confusion about which to use
│
└─ Unused imports (21 files)
   ├─ collections (7 files)
   ├─ pathlib (4 files)
   ├─ datetime (3 files)
   └─ Others (7 files)
```

### 3. Missing Abstractions

```
ARCHITECTURAL GAPS:
├─ No unified plotting framework
│  └─ Two separate implementations
│
├─ No export strategy pattern
│  └─ Three export modules with duplication
│
├─ Weak config validation
│  └─ config/schema.py is minimal
│
├─ No model building abstraction
│  └─ system_builder.py is 822 lines monolith
│
└─ No batch processing API
   └─ Manual loops in notebooks
```

### 4. Inconsistent Naming

```
STYLE INCONSISTENCIES:
├─ Config keys:
│  ├─ dt_h (abbreviation)
│  ├─ Tsink_out_K (mixed case)
│  └─ eur_mwh (lowercase)
│
├─ Variables:
│  ├─ self.cop_series vs self.COP_series (SAME THING!)
│  ├─ self.e_min (cryptic)
│  └─ self.capacity_min_mw (verbose)
│
└─ Functions:
   ├─ _has_content (underscore)
   ├─ get_results (no underscore)
   └─ validate_config (inconsistent)
```

---

## ✅ **STÄRKEN DES FRAMEWORKS**

### Positive Architectural Aspects

```
WELL DESIGNED:
✅ Modular component system (blocks)
✅ Plugin-based architecture (registry.py)
✅ Clear separation: models vs. run vs. io
✅ Config-driven approach (YAML-based)
✅ Comprehensive test coverage (14 test files)
✅ Optional dependencies handled gracefully
✅ TimeSeriesTable abstraction (minimal pandas)
✅ Forecasting abstraction (base.py)
✅ v2.0 workflow unification completed
✅ Good documentation (README, ARCHITECTURE_V2, etc.)
```

### Code Quality Metrics

```
METRICS:
├─ Total lines: ~13,066
├─ Test coverage: 14 test files
├─ Modularization: 11 core modules
├─ Documentation: 5 major docs
├─ Config examples: 21 YAML files
└─ Example notebooks: 5
```

---

## 🎯 **GENERICITY & AUSTAUSCHBARKEIT**

### Ist das Framework generisch?

| Aspekt | Status | Bewertung |
|--------|--------|-----------|
| **Komponenten** | ✅ Gut | Blocks sind Plugin-basiert, neue hinzufügbar |
| **Solver** | ✅ Gut | Gurobi/CBC/GLPK austauschbar via config |
| **Config** | ✅ Gut | YAML-basiert, erweiterbar |
| **Forecasting** | ✅ Gut | Abstract base class, neue Methoden hinzufügbar |
| **Export** | ⚠️ Mittel | Drei separate Module, schwer zu erweitern |
| **Plotting** | ⚠️ Mittel | Zwei Implementierungen, nicht pluggable |
| **Data Input** | ✅ Gut | Excel/CSV/TimeSeriesTable abstrahiert |
| **Zeitauflösung** | ✅ Gut | Über dt_h konfigurierbar |

### Was ist NICHT austauschbar?

```
HARDCODED ANNAHMEN:
├─ Bus-Typen (electricity, heat, gas, biomass, waste)
│  └─ Fest in system_builder.py codiert
│
├─ Pyomo als Solver-Interface
│  └─ Kein Adapter für andere Frameworks (Gurobi Direct, Julia/JuMP)
│
├─ Excel als primäres Input-Format
│  └─ Alternativen (CSV, Parquet, DB) nicht integriert
│
└─ Deutsche Sprache in Labels
   └─ Internalisierung fehlt (nur teilweise in publication_plotter)
```

---

## 🔧 **KONKRETE VERBESSERUNGEN**

### Priorität 1: Quick Wins (1-2 Tage) 🟢

#### 1.1 Cleanup: Unused Imports entfernen
```bash
# Tool: autoflake
pip install autoflake
autoflake --remove-all-unused-imports --in-place energis/**/*.py
```
**Nutzen**: Code-Qualität, weniger Clutter
**Aufwand**: 1 Stunde

#### 1.2 Konsolidierung: Plotting Utilities
**Datei erstellen**: `energis/io/plot_utils.py`
```python
"""Shared plotting utilities."""

def has_content(values: Sequence[float], threshold: float = 1e-6) -> bool:
    """Check if series has non-zero content."""
    return any(abs(v) > threshold for v in values)

def prettify_label(name: str, language: str = 'de') -> str:
    """Format variable name for display."""
    # Unified implementation with language support
    ...

def configure_time_axis(ax, timestamps, language='de') -> None:
    """Configure matplotlib time axis formatting."""
    ...
```
**Nutzen**: DRY-Prinzip, 300 Zeilen Duplikation eliminiert
**Aufwand**: 2 Stunden

#### 1.3 orchestrator.py vollständig deprecaten
**Action**: Entferne alle direkten Referenzen
```python
# In __main__.py - ERSETZE:
from energis.run import orchestrator
result = orchestrator.run_all(configs)

# MIT:
from energis.run import rolling_horizon as rh
workflow = rh.run_workflow(configs)
result = rh.export_workflow_results(workflow)
```
**Nutzen**: Klare Codebasis, keine Verwirrung
**Aufwand**: 3 Stunden

---

### Priorität 2: Mittelfristige Verbesserungen (3-5 Tage) 🟡

#### 2.1 Unified Plotting Framework
**Struktur**:
```python
# energis/io/plotting/
├── __init__.py
├── base.py              # PlotRenderer protocol
├── styles.py            # PlotConfig, themes
├── simple.py            # SimplePlotter(PlotRenderer)
├── publication.py       # PublicationPlotter(PlotRenderer)
└── utils.py             # Shared utilities (moved from plot_utils.py)

# Usage:
from energis.io.plotting import get_plotter

plotter = get_plotter(style='publication', language='de')
fig = plotter.render_heat_balance(data)
```
**Nutzen**: Einheitliche API, einfache Erweiterung, DRY
**Aufwand**: 1 Tag

#### 2.2 Config Schema mit Pydantic
**Implementation**:
```python
# energis/config/schemas.py
from pydantic import BaseModel, Field, validator

class SolverConfig(BaseModel):
    name: str = Field(..., regex='^(gurobi|cbc|glpk)$')
    options: Dict[str, Any] = Field(default_factory=dict)

    @validator('options')
    def validate_solver_options(cls, v, values):
        # Validate per-solver options
        ...

class RunConfig(BaseModel):
    dt_h: float = Field(1.0, gt=0, description="Timestep in hours")
    solver: SolverConfig
    export_model_structure: bool = True

class BaseConfig(BaseModel):
    run: RunConfig
    costs: CostConfig
    grid: GridConfig

    class Config:
        extra = 'forbid'  # Strict validation
```
**Nutzen**: Frühe Fehlererkennung, bessere IDE-Unterstützung
**Aufwand**: 2 Tage

#### 2.3 Model Builder Refactoring
**Aufteilen von system_builder.py** (822 Zeilen → 4 Module):
```python
# energis/models/builder/
├── __init__.py
├── core.py          # build_model() orchestrator
├── setup.py         # _setup_sets, _setup_parameters
├── components.py    # _add_buses, _add_blocks
└── constraints.py   # _add_balance_constraints, _add_objective

# Usage bleibt gleich:
from energis.models import build_model
model = build_model(table, config, dt_h)
```
**Nutzen**: Testbarkeit, Lesbarkeit, Wartbarkeit
**Aufwand**: 1 Tag

#### 2.4 Variable Management Helper
**Ersetzt setattr/getattr Pattern**:
```python
# energis/models/variables.py
class ModelVariables:
    """Structured variable management for Pyomo models."""

    def __init__(self, component_name: str, model: pyo.ConcreteModel):
        self.prefix = component_name
        self.model = model
        self._vars = {}

    def add_var(self, name: str, *args, **kwargs) -> pyo.Var:
        full_name = f"{self.prefix}_{name}"
        var = pyo.Var(*args, **kwargs)
        setattr(self.model, full_name, var)
        self._vars[name] = var
        return var

    def get(self, name: str) -> pyo.Var:
        return self._vars[name]

# Usage in blocks:
vars = ModelVariables("HP1", m)
Q = vars.add_var("Q", m.t, domain=pyo.NonNegativeReals)
# Instead of: setattr(m, "HP1_Q", pyo.Var(...))
```
**Nutzen**: Type safety, autocomplete, weniger Fehler
**Aufwand**: 1 Tag

---

### Priorität 3: Langfristige Architektur (1-2 Wochen) 🔵

#### 3.1 Unified Export Strategy Pattern
```python
# energis/io/export/
├── __init__.py
├── base.py           # ExportStrategy protocol
├── csv.py            # CSVExporter
├── excel.py          # ExcelExporter
├── latex.py          # LaTeXExporter
├── journal.py        # JournalExporter (Applied Energies)
└── manager.py        # ExportManager

class ExportManager:
    def __init__(self, exporters: List[ExportStrategy]):
        self.exporters = exporters

    def export_all(self, results, config) -> List[Path]:
        paths = []
        for exporter in self.exporters:
            paths.extend(exporter.export(results, config))
        return paths

# Usage:
from energis.io.export import ExportManager, CSVExporter, LaTeXExporter

manager = ExportManager([
    CSVExporter(),
    LaTeXExporter(style='publication'),
])
files = manager.export_all(workflow, config)
```
**Nutzen**: Flexible Exports, Plugin-System, DRY
**Aufwand**: 3 Tage

#### 3.2 Public API Layer
**Erstelle**: `energis/api.py`
```python
"""High-level public API for EnerGIS framework."""

from typing import Union, List
from pathlib import Path

def run_scenario(
    configs: Union[List[str], List[Path]],
    overrides: dict = None,
    output_dir: str = "exports"
) -> WorkflowResult:
    """Run a single scenario optimization.

    Examples
    --------
    >>> result = energis.run_scenario([
    ...     "configs/base.yaml",
    ...     "configs/scenarios/pf_only.scenario.yaml"
    ... ])
    >>> print(result.costs['objective.OBJ_value_EUR'])
    """
    from energis.run import rolling_horizon as rh
    workflow = rh.run_workflow(configs, overrides)
    export = rh.export_workflow_results(workflow, outdir=output_dir)
    return WorkflowResult(workflow, export)

def run_batch(
    base_config: List[str],
    scenarios: List[dict],
    output_base: str = "exports"
) -> List[WorkflowResult]:
    """Run multiple scenarios with parameter variations."""
    ...

def run_sensitivity(
    base_config: List[str],
    parameter_ranges: dict,
    num_parallel: int = 1
) -> SensitivityResult:
    """Run sensitivity analysis."""
    ...

# Public exports
__all__ = [
    'run_scenario',
    'run_batch',
    'run_sensitivity',
    'WorkflowResult',
    'SensitivityResult'
]
```
**Nutzen**: Klare Schnittstelle, einfache Integration, versionierbar
**Aufwand**: 2 Tage

#### 3.3 Type Checking & Validation
**Setup**:
```toml
# pyproject.toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
files = ["energis/**/*.py"]

[[tool.mypy.overrides]]
module = ["pyomo.*", "matplotlib.*"]
ignore_missing_imports = true
```

**CI/CD Integration**:
```yaml
# .github/workflows/ci.yml
- name: Type checking
  run: |
    pip install mypy
    mypy energis/
```
**Nutzen**: Frühe Fehlererkennung, bessere IDE-Unterstützung
**Aufwand**: 3 Tage (Hinzufügen + Fixing)

#### 3.4 Batch Processing Framework
```python
# energis/batch/
├── __init__.py
├── processor.py      # BatchProcessor
├── parallel.py       # ParallelExecutor
└── results.py        # ResultAggregator

class BatchProcessor:
    """Process multiple scenarios efficiently."""

    def sweep(
        self,
        base_config: List[str],
        parameter_grid: Dict[str, List[Any]]
    ) -> pd.DataFrame:
        """Run parameter sweep."""
        results = []
        for params in self._generate_combinations(parameter_grid):
            overrides = self._build_overrides(params)
            result = run_scenario(base_config, overrides)
            results.append(result.to_dict())
        return pd.DataFrame(results)

    def parallel_sweep(
        self,
        base_config: List[str],
        parameter_grid: Dict[str, List[Any]],
        num_workers: int = 4
    ) -> pd.DataFrame:
        """Run parameter sweep in parallel."""
        ...
```
**Nutzen**: Automatisierte Studien, Zeitersparnis
**Aufwand**: 2 Tage

---

## 📊 **AUFWAND-NUTZEN-MATRIX**

| Verbesserung | Aufwand | Nutzen | Priorität |
|-------------|---------|--------|-----------|
| Unused imports entfernen | 1h | Mittel | 🟢 P1 |
| Plot utilities konsolidieren | 2h | Hoch | 🟢 P1 |
| orchestrator.py entfernen | 3h | Hoch | 🟢 P1 |
| Unified plotting framework | 1d | Sehr hoch | 🟡 P2 |
| Pydantic config schema | 2d | Hoch | 🟡 P2 |
| Model builder refactoring | 1d | Hoch | 🟡 P2 |
| Variable management helper | 1d | Mittel | 🟡 P2 |
| Export strategy pattern | 3d | Hoch | 🔵 P3 |
| Public API layer | 2d | Sehr hoch | 🔵 P3 |
| Type checking setup | 3d | Mittel | 🔵 P3 |
| Batch processing | 2d | Mittel | 🔵 P3 |

---

## 🎯 **IMPLEMENTATION ROADMAP**

### Woche 1: Fundamentals
```
Tag 1-2: Quick Wins (P1)
  ├─ Unused imports cleanup
  ├─ Plot utilities konsolidieren
  └─ orchestrator.py final cleanup

Tag 3-5: Core Refactoring (P2)
  ├─ Unified plotting framework
  ├─ Model builder refactoring
  └─ Variable management helper
```

### Woche 2: Quality & Architecture
```
Tag 1-3: Config & Validation (P2)
  ├─ Pydantic schemas
  ├─ Config validation tests
  └─ Error handling improvements

Tag 4-5: Export Unification (P3)
  └─ Export strategy pattern
```

### Woche 3-4: API & Tooling
```
Tag 1-2: Public API (P3)
  └─ api.py with clean interface

Tag 3-4: Advanced Features (P3)
  ├─ Batch processing
  └─ Type checking setup

Tag 5: Documentation & Testing
  ├─ Update docs
  └─ Integration tests
```

---

## 📝 **FAZIT**

### Ist das Framework sauber und nachvollziehbar?

**JA, weitgehend:**
- ✅ Klare Modul-Trennung
- ✅ Gute Dokumentation
- ✅ Test-Coverage vorhanden
- ⚠️  Aber: Code-Duplikation (Plotting)
- ⚠️  Aber: Deprecated orchestrator.py
- ⚠️  Aber: Inkonsistente Namenskonventionen

**Note: 7/10** - Gut, aber mit Verbesserungspotenzial

### Passt der Aufbau?

**JA, grundsätzlich solide:**
- ✅ Gute Layer-Separation (models, run, io, config)
- ✅ Plugin-Architektur (blocks, forecasting)
- ✅ Config-driven Design
- ⚠️  Aber: Fehlende Abstractions (Plotting, Export)
- ⚠️  Aber: Monolithische Funktionen (system_builder)
- ⚠️  Aber: Schwache Config-Validierung

**Note: 8/10** - Sehr gut mit kleinen Schwächen

### Ist alles generisch und austauschbar?

**TEILWEISE:**
- ✅ Komponenten (Blocks) sind pluggable
- ✅ Solver austauschbar
- ✅ Config-basiert
- ✅ Forecasting-Methoden erweiterbar
- ⚠️  Bus-Typen sind hardcoded
- ⚠️  Pyomo als einziges Interface
- ⚠️  Plotting nicht pluggable
- ⚠️  Export-Formate nicht pluggable

**Note: 7/10** - Gut, aber ausbaufähig

### Gesamtbewertung: **7.5/10**

**Stärken:**
- Sehr gute Modularität
- Klare Architektur
- Gute Dokumentation
- Aktive Weiterentwicklung (v2.0)

**Schwächen:**
- Code-Duplikation (Plotting)
- Fehlende Abstractions
- Inkonsistente Conventions
- Deprecated Code noch aktiv

**Empfehlung**: Framework ist production-ready, aber die vorgeschlagenen Verbesserungen würden Wartbarkeit und Erweiterbarkeit signifikant verbessern.
