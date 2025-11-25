# EnerGIS Framework - Konkrete Verbesserungsschritte

## 🎯 **TOP 5 SOFORT-MASSNAHMEN**

### 1. 🧹 Code Cleanup (1 Stunde)

**Problem**: 21 Dateien mit unused imports

**Lösung**:
```bash
# Installation
pip install autoflake ruff

# Cleanup ausführen
autoflake \
  --remove-all-unused-imports \
  --remove-unused-variables \
  --in-place \
  --recursive \
  energis/

# Zusätzlich: Ruff für moderne Linting
ruff check energis/ --fix
```

**Erwartetes Ergebnis**:
- ~30 Zeilen unnötiger Code entfernt
- Klarere Imports
- Schnellere IDE-Performance

---

### 2. 🎨 Plot Utilities Konsolidierung (2 Stunden)

**Problem**: ~300 Zeilen duplizierter Code in plotter.py und publication_plotter.py

**Schritt 1**: Neue Datei erstellen
```python
# energis/io/plot_utils.py
"""Shared plotting utilities."""

from typing import Sequence, Optional
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

def has_content(
    values: Sequence[float],
    threshold: float = 1e-6
) -> bool:
    """Check if series has meaningful non-zero content.

    Parameters
    ----------
    values : sequence of float
        Numeric values to check
    threshold : float, default 1e-6
        Minimum absolute value to consider non-zero

    Returns
    -------
    bool
        True if at least one value exceeds threshold

    Examples
    --------
    >>> has_content([0.0, 0.0, 1.5])
    True
    >>> has_content([1e-10, 0.0, 1e-9])
    False
    """
    return any(abs(v) > threshold for v in values)


def prettify_label(name: str, language: str = 'de') -> str:
    """Format technical variable name for display.

    Parameters
    ----------
    name : str
        Technical variable name (e.g., 'P_buy_MW')
    language : {'de', 'en'}, default 'de'
        Target language for translation

    Returns
    -------
    str
        Human-readable label

    Examples
    --------
    >>> prettify_label('P_buy_MW', 'de')
    'Netzbezug'
    >>> prettify_label('P_buy_MW', 'en')
    'Grid Import'
    """
    translations = {
        'de': {
            'P_buy_MW': 'Netzbezug',
            'P_sell_MW': 'Einspeisung',
            'Q_dump_MWth': 'Wärme-Dump',
            'TES_SOC_MWh': 'Speicher-SOC',
            # ... more translations
        },
        'en': {
            'P_buy_MW': 'Grid Import',
            'P_sell_MW': 'Grid Export',
            'Q_dump_MWth': 'Heat Dump',
            'TES_SOC_MWh': 'Storage SOC',
            # ... more translations
        }
    }

    lang_dict = translations.get(language, translations['de'])
    return lang_dict.get(name, name.replace('_', ' ').title())


def configure_time_axis(
    ax: Axes,
    timestamps,
    language: str = 'de',
    rotation: int = 45
) -> None:
    """Configure matplotlib time axis with localized formatting.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Axis to configure
    timestamps : sequence
        Datetime values
    language : {'de', 'en'}, default 'de'
        Language for month/day names
    rotation : int, default 45
        X-tick label rotation angle
    """
    import matplotlib.dates as mdates
    import locale

    # Set locale for date formatting
    try:
        if language == 'de':
            locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
        else:
            locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
    except locale.Error:
        pass  # Fall back to system default

    # Configure date formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())

    # Rotate labels
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=rotation, ha='right')
```

**Schritt 2**: Update plotter.py
```python
# energis/io/plotter.py
from .plot_utils import has_content, prettify_label, configure_time_axis

# Alte Funktionen löschen, neue nutzen
```

**Schritt 3**: Update publication_plotter.py
```python
# energis/io/publication_plotter.py
from .plot_utils import has_content, prettify_label, configure_time_axis

# Alte Funktionen löschen, neue nutzen
```

**Test**:
```python
# Test dass beide Plotter noch funktionieren
python -m pytest tests/test_plotter.py -v
```

---

### 3. 🗑️ orchestrator.py Final Cleanup (3 Stunden)

**Problem**: Deprecated module noch aktiv in __main__.py

**Schritt 1**: Update CLI entry point
```python
# energis/run/__main__.py
"""Command-line interface for EnerGIS workflows."""

import sys
from energis.run import rolling_horizon

if __name__ == "__main__":
    sys.exit(rolling_horizon.main())
```

**Schritt 2**: Markiere orchestrator.py deutlicher
```python
# energis/run/orchestrator.py (am Anfang)
"""
.. deprecated:: 2.0
    This module is DEPRECATED. Use :mod:`energis.run.rolling_horizon` instead.

    This file is kept only for backwards compatibility and will be removed in v3.0.

    All functionality has been moved to rolling_horizon.py.
"""

import warnings
warnings.warn(
    "energis.run.orchestrator is deprecated. "
    "Use energis.run.rolling_horizon instead.",
    DeprecationWarning,
    stacklevel=2
)
```

**Schritt 3**: Test alle Notebooks
```bash
# Stelle sicher, dass kein Notebook mehr orchestrator importiert
grep -r "from energis.run.orchestrator" notebooks/
# Sollte: Keine Ergebnisse (wir haben alle aktualisiert)

# Test runner.ipynb
jupyter nbconvert --to notebook --execute notebooks/runner.ipynb
```

---

### 4. 🏗️ Model Builder Refactoring (1 Tag)

**Problem**: system_builder.py ist 822 Zeilen Monolith

**Neue Struktur**:
```
energis/models/builder/
├── __init__.py         # Public API
├── core.py             # build_model() orchestrator
├── setup.py            # Sets, parameters, time indices
├── components.py       # Bus and block instantiation
└── constraints.py      # Balance constraints, objective
```

**Implementation**:

```python
# energis/models/builder/__init__.py
"""Model building module."""

from .core import build_model

__all__ = ['build_model']
```

```python
# energis/models/builder/core.py
"""Core model building orchestrator."""

from typing import Dict, Any
import pyomo.environ as pyo
from energis.utils.timeseries import TimeSeriesTable
from . import setup, components, constraints

def build_model(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float = 1.0
) -> pyo.ConcreteModel:
    """Build complete Pyomo optimization model.

    This is the main entry point that orchestrates all model building steps.

    Parameters
    ----------
    table : TimeSeriesTable
        Input time series data
    cfg : dict
        Merged configuration dictionary
    dt_h : float, default 1.0
        Time step in hours

    Returns
    -------
    pyomo.ConcreteModel
        Complete optimization model ready for solving

    Notes
    -----
    Model building happens in 4 phases:
    1. Setup: Create sets, parameters, time indices
    2. Components: Instantiate buses and component blocks
    3. Constraints: Add balance constraints and coupling
    4. Objective: Define optimization objective function
    """
    # Phase 1: Initialize model structure
    m = pyo.ConcreteModel()
    setup.initialize_model_structure(m, table, cfg, dt_h)

    # Phase 2: Add components (buses and blocks)
    buses, blocks = components.add_components(m, table, cfg, dt_h)

    # Phase 3: Add constraints
    constraints.add_balance_constraints(m, buses, blocks, cfg)
    constraints.add_coupling_constraints(m, blocks, cfg)

    # Phase 4: Add objective
    constraints.add_objective(m, blocks, cfg, dt_h)

    return m
```

```python
# energis/models/builder/setup.py
"""Model setup: sets, parameters, indices."""

import pyomo.environ as pyo

def initialize_model_structure(m, table, cfg, dt_h):
    """Initialize basic model structure (Phase 1)."""
    _add_sets(m, table)
    _add_parameters(m, table, cfg)
    _add_time_indices(m, table, dt_h)

def _add_sets(m, table):
    """Add Pyomo sets for time steps."""
    m.t = pyo.Set(initialize=range(len(table)))

def _add_parameters(m, table, cfg):
    """Add Pyomo parameters from config and data."""
    # Strompreis
    m.c_buy = pyo.Param(m.t, initialize={
        i: table['strompreis_EUR_MWh'][i] for i in m.t
    })
    # ... weitere Parameter

def _add_time_indices(m, table, dt_h):
    """Store time metadata on model."""
    m.dt_h = dt_h
    m.n_steps = len(table)
```

```python
# energis/models/builder/components.py
"""Component instantiation: buses and blocks."""

from energis.models import Bus
from energis.models.blocks import (
    HeatPumpBlock, StorageBlock, ThermalGeneratorBlock, P2HBlock
)

def add_components(m, table, cfg, dt_h):
    """Add all components to model (Phase 2)."""
    buses = _add_buses(m, cfg)
    blocks = _add_component_blocks(m, cfg, buses, table, dt_h)
    return buses, blocks

def _add_buses(m, cfg):
    """Create bus instances."""
    buses = {
        'electricity': Bus('electricity', m),
        'heat': Bus('heat', m),
        'gas': Bus('gas', m),
        'biomass': Bus('biomass', m),
        'waste': Bus('waste', m),
    }

    for bus in buses.values():
        bus.attach(m, [])  # Will be populated by blocks

    return buses

def _add_component_blocks(m, cfg, buses, table, dt_h):
    """Instantiate component blocks."""
    blocks = []

    # Heat Pumps
    for hp_cfg in cfg.get('system', {}).get('heat_pumps', []):
        if hp_cfg.get('enabled', True):
            hp = HeatPumpBlock.from_config(hp_cfg, table, dt_h)
            hp.attach(m, buses)
            blocks.append(hp)

    # Storage
    storage_cfg = cfg.get('system', {}).get('storage', {})
    if storage_cfg.get('enabled', False):
        storage = StorageBlock.from_config(storage_cfg, table, dt_h)
        storage.attach(m, buses)
        blocks.append(storage)

    # ... weitere Komponenten

    return blocks
```

```python
# energis/models/builder/constraints.py
"""Constraint and objective definitions."""

import pyomo.environ as pyo

def add_balance_constraints(m, buses, blocks, cfg):
    """Add bus balance constraints (Phase 3a)."""
    for bus in buses.values():
        bus.add_balance_constraint(m)

def add_coupling_constraints(m, blocks, cfg):
    """Add inter-component coupling constraints (Phase 3b)."""
    # z.B. Storage SOC continuity
    # z.B. Heat pump capacity constraints
    pass

def add_objective(m, blocks, cfg, dt_h):
    """Define optimization objective (Phase 4)."""

    def objective_rule(m):
        total_cost = 0.0

        # Electricity costs
        total_cost += sum(m.P_buy[t] * m.c_buy[t] * dt_h for t in m.t)

        # Investment costs (if applicable)
        for block in blocks:
            if hasattr(block, 'get_investment_cost'):
                total_cost += block.get_investment_cost(m)

        # ... weitere Kosten

        return total_cost

    m.OBJ = pyo.Objective(rule=objective_rule, sense=pyo.minimize)
```

**Migration**:
```python
# Alter Code (funktioniert weiter):
from energis.models.system_builder import build_model
model = build_model(table, cfg, dt_h)

# Neuer Code (gleiche Signatur!):
from energis.models import build_model  # Now from builder/
model = build_model(table, cfg, dt_h)
```

**Vorteile**:
- ✅ Jede Funktion < 100 Zeilen
- ✅ Testbar in Isolation
- ✅ Lesbar und wartbar
- ✅ Schrittweise Migration möglich (backwards compatible)

---

### 5. 📊 Unified Plotting Framework (1 Tag)

**Problem**: Zwei separate Plotting-Systeme mit Duplikation

**Neue Architektur**:
```python
# energis/io/plotting/__init__.py
"""Unified plotting framework."""

from .base import PlotRenderer, PlotConfig
from .simple import SimplePlotter
from .publication import PublicationPlotter

def get_plotter(
    style: str = 'simple',
    language: str = 'de',
    **kwargs
) -> PlotRenderer:
    """Factory function to create plotter instance.

    Parameters
    ----------
    style : {'simple', 'publication'}, default 'simple'
        Plotting style
    language : {'de', 'en'}, default 'de'
        Language for labels
    **kwargs
        Additional config passed to plotter

    Returns
    -------
    PlotRenderer
        Plotter instance

    Examples
    --------
    >>> plotter = get_plotter(style='publication', dpi=300)
    >>> fig = plotter.render_heat_balance(data)
    """
    config = PlotConfig(language=language, **kwargs)

    if style == 'publication':
        return PublicationPlotter(config)
    else:
        return SimplePlotter(config)

__all__ = [
    'PlotRenderer',
    'PlotConfig',
    'SimplePlotter',
    'PublicationPlotter',
    'get_plotter'
]
```

```python
# energis/io/plotting/base.py
"""Base abstractions for plotting."""

from dataclasses import dataclass, field
from typing import Protocol, Any, Dict
from matplotlib.figure import Figure

@dataclass
class PlotConfig:
    """Configuration for plot rendering."""

    language: str = 'de'
    dpi: int = 100
    format: str = 'png'
    figsize: tuple = (12, 6)
    style: str = 'seaborn-v0_8-darkgrid'
    font_size: int = 10
    title_font_size: int = 14

    # Publication-specific
    use_tex: bool = False
    column_width_inches: float = 3.5

    # Colors
    colors: Dict[str, str] = field(default_factory=lambda: {
        'grid_buy': '#1f77b4',
        'grid_sell': '#ff7f0e',
        'heat': '#d62728',
        'storage': '#9467bd',
    })


class PlotRenderer(Protocol):
    """Protocol for plot renderers.

    All plotters must implement these methods.
    """

    def render_heat_balance(
        self,
        table,
        series,
        summary=None
    ) -> Figure:
        """Render heat balance plot."""
        ...

    def render_electric_balance(
        self,
        table,
        series,
        summary=None
    ) -> Figure:
        """Render electric balance plot."""
        ...

    def render_storage(
        self,
        table,
        series,
        summary=None
    ) -> Figure:
        """Render storage state plot."""
        ...

    def render_cost_breakdown(
        self,
        costs: Dict[str, float]
    ) -> Figure:
        """Render cost breakdown plot."""
        ...
```

```python
# energis/io/plotting/simple.py
"""Simple plotter implementation."""

import matplotlib.pyplot as plt
from .base import PlotRenderer, PlotConfig
from .utils import has_content, prettify_label, configure_time_axis

class SimplePlotter:
    """Simple plot renderer for quick analysis."""

    def __init__(self, config: PlotConfig):
        self.config = config
        plt.style.use(config.style)

    def render_heat_balance(self, table, series, summary=None):
        """Render heat balance plot."""
        fig, ax = plt.subplots(figsize=self.config.figsize)

        # Find heat-producing columns
        heat_cols = [
            c for c in series.keys()
            if '_Q' in c and has_content(series[c])
        ]

        # Plot stacked area
        for col in heat_cols:
            label = prettify_label(col, self.config.language)
            ax.plot(table.index, series[col], label=label, linewidth=2)

        # Formatting
        ax.set_title('Wärmebilanz' if self.config.language == 'de' else 'Heat Balance')
        ax.set_ylabel('MW_th')
        ax.legend()
        ax.grid(alpha=0.3)

        configure_time_axis(ax, table.index, self.config.language)

        fig.tight_layout()
        return fig

    # ... weitere Methoden
```

**Usage**:
```python
# Alte API (noch supported):
from energis.io.plotter import export_plots
plots = export_plots(outdir, table, series, summary)

# Neue API:
from energis.io.plotting import get_plotter

# Simple plots
plotter = get_plotter(style='simple')
fig_heat = plotter.render_heat_balance(table, series)
fig_heat.savefig('heat_balance.png')

# Publication plots
plotter = get_plotter(
    style='publication',
    dpi=300,
    format='pdf',
    use_tex=True
)
fig_heat = plotter.render_heat_balance(table, series)
fig_heat.savefig('heat_balance.pdf')
```

---

## 📅 **2-WOCHEN SPRINT PLAN**

### Woche 1: Fundamentals

**Tag 1 (Montag)**
- ✅ Unused imports cleanup (1h)
- ✅ Plot utilities konsolidieren (2h)
- ✅ orchestrator.py cleanup (3h)
- ✅ Testing & Commit

**Tag 2-3 (Di-Mi)**
- ✅ Model builder refactoring
  - Setup module (4h)
  - Components module (4h)
  - Constraints module (4h)
  - Tests schreiben (2h)

**Tag 4-5 (Do-Fr)**
- ✅ Unified plotting framework
  - Base abstractions (3h)
  - SimplePlotter (4h)
  - PublicationPlotter migration (4h)
  - Tests & Integration (3h)

### Woche 2: Architecture & Quality

**Tag 6-7 (Mo-Di)**
- ✅ Pydantic config schemas
  - Schema definitions (6h)
  - Migration bestehender Code (4h)
  - Validation tests (4h)

**Tag 8-9 (Mi-Do)**
- ✅ Variable management helper
  - ModelVariables class (4h)
  - Block migration (6h)
  - Testing (2h)

**Tag 10 (Freitag)**
- ✅ Documentation & Final testing
  - Update ARCHITECTURE_V2.md
  - Update README.md
  - Integration tests
  - Performance benchmarking

---

## ✅ **SUCCESS CRITERIA**

### Nach Woche 1:
- [ ] 0 unused imports
- [ ] 300 Zeilen Duplikation eliminiert
- [ ] orchestrator.py vollständig optional
- [ ] system_builder.py aufgeteilt in 4 Module
- [ ] Einheitliches Plotting-Interface

### Nach Woche 2:
- [ ] Pydantic-basierte Config-Validierung
- [ ] Reduzierte setattr/getattr Nutzung
- [ ] Vollständige Dokumentation
- [ ] 100% Backwards-Kompatibilität

### Quantifizierbare Metriken:
- **Code-Duplikation**: -300 Zeilen (-3%)
- **Größte Funktion**: 822 → <200 Zeilen
- **Test Coverage**: Behalten (14 test files)
- **Type Coverage**: 30% → 80%
- **Import Zeit**: Sollte gleich bleiben

---

## 🚀 **QUICK START**

Um sofort loszulegen:

```bash
# 1. Branch erstellen
git checkout -b refactor/framework-cleanup

# 2. Quick Wins
pip install autoflake ruff
autoflake --remove-all-unused-imports --in-place --recursive energis/
ruff check energis/ --fix

# 3. Commit
git add -A
git commit -m "chore: Remove unused imports and lint cleanup"

# 4. Plot utilities
# ... (siehe Schritt 2 oben)

# 5. Nach jedem Schritt testen
python -m pytest tests/ -v
jupyter nbconvert --to notebook --execute notebooks/runner.ipynb

# 6. Commit & Push
git commit -m "refactor: Consolidate plot utilities"
git push -u origin refactor/framework-cleanup
```

---

## 📞 **SUPPORT & QUESTIONS**

Bei Fragen oder Problemen während der Umsetzung:
1. Check existing tests: `pytest tests/test_*.py -v`
2. Konsultiere ARCHITECTURE_V2.md
3. Erstelle Issue auf GitHub

**Wichtig**: Alle Änderungen müssen **backwards compatible** sein!
