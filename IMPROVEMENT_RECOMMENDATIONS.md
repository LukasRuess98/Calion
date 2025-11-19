# Framework Verbesserungsvorschläge

**Datum:** 2025-11-18
**Basierend auf:** Umfassende Framework-Review nach Netzwerk-Änderungen

---

## 🔴 Kritische Verbesserungen (Sofort umsetzen)

### 1. ✅ CLI-Interface funktionsfähig machen

**Problem:** `python -m energis.run` funktioniert nicht
**Status:** ✅ BEHOBEN - `energis/run/__main__.py` erstellt

**Vorher:**
```bash
$ python -m energis.run configs/base.yaml
# Error: No module named energis.run.__main__
```

**Nachher:**
```bash
$ python -m energis.run configs/base.yaml configs/systems/baseline.system.yaml
# ✓ Funktioniert!
```

---

### 2. ⚠️ Stratified Storage in system_builder integrieren

**Problem:** `StratifiedStorageBlock` existiert (728 Zeilen), wird aber NICHT in `system_builder.py` verwendet

**Aktueller Zustand:**
- ✅ `energis/models/blocks/stratified_storage.py` - vollständig implementiert
- ❌ Nicht importiert in `system_builder.py`
- ❌ Keine Config-Option in YAML-Dateien
- ❌ Benutzer kann es nicht nutzen (nur über custom code)

**Empfehlung:**
```python
# energis/models/system_builder.py
from .blocks.stratified_storage import StratifiedStorageBlock  # HINZUFÜGEN

# In build_model(), nach storage_block:
if sto_cfg.get("type") == "stratified":
    # Use StratifiedStorageBlock instead of StorageBlock
    block = StratifiedStorageBlock(
        "TES",
        T_hot_C=sto_cfg.get("T_hot_C", 90.0),
        T_cold_C=sto_cfg.get("T_cold_C", 40.0),
        T_ambient_C=sto_cfg.get("T_ambient_C", 15.0),
        # ... weitere Parameter
    )
else:
    # Standard StorageBlock (bestehender Code)
    block = StorageBlock(...)
```

**YAML Config:**
```yaml
system:
  storage:
    enabled: true
    type: stratified  # NEW: "simple" oder "stratified"
    T_hot_C: 90.0
    T_cold_C: 40.0
    T_ambient_C: 15.0
    U_top: 0.3
    U_side: 0.2
    U_bottom: 0.15
```

**Impact:** Hoch - Nutzer können advanced storage nicht nutzen

---

### 3. ⚠️ Bus-System konsequent nutzen

**Problem:** Bus-Abstraktion existiert, wird aber nicht im `system_builder` verwendet

**Aktueller Zustand:**
```python
# system_builder.py - HARDCODED Lists
el_in: List = []
el_out: List = []
ht_out: List = []
ht_in: List = []
gas_in: List = []
bio_in: List = []
waste_in: List = []

# Dann manuell:
m.el_balance = pyo.Constraint(
    m.t,
    rule=lambda mm, t: mm.P_buy[t] + sum(el_out) == sum(el_in) + mm.P_sell[t]
)
```

**Besser wäre:**
```python
# Bus-basierte Architektur nutzen
from .bus import Bus, create_default_buses

buses = create_default_buses()
# buses = {'electricity': Bus(...), 'heat': Bus(...), ...}

# Komponenten registrieren sich selbst bei Bussen
hp_block.attach(m, m.t, cfg, buses)  # registriert flows

# Bus erstellt Balance-Constraint automatisch
for bus_name, bus in buses.items():
    bus.attach(m, m.t, cfg, buses)  # erstellt balance constraint
```

**Vorteile:**
- ✅ Weniger boilerplate code
- ✅ Einfacher erweiterbar (neue bus types)
- ✅ Konsistente Architektur
- ✅ Bessere Wartbarkeit

**Impact:** Mittel - Architektur wird sauberer

---

### 4. ⚠️ Component Registry nutzen

**Problem:** Registry existiert (299 Zeilen), wird aber NICHT genutzt

**Aktuell:**
```python
# system_builder.py - HARDCODED component creation
from .blocks.heat_pump import HeatPumpBlock
from .blocks.storage import StorageBlock
from .blocks.thermal_gen import ThermalGeneratorBlock
from .blocks.p2h import P2HBlock

# Dann:
block = HeatPumpBlock(...)
block = StorageBlock(...)
# etc.
```

**Mit Registry:**
```python
from .registry import ComponentRegistry, register_component

# In blocks/heat_pump.py
@register_component("heat_pump", category="converter")
class HeatPumpBlock(BaseComponent):
    ...

# In system_builder.py
for hp in syscfg.get("heat_pumps", []):
    block = ComponentRegistry.create("heat_pump", **hp_params)
    block.attach(m, m.t, cfg, buses)
```

**Vorteile:**
- ✅ Plugin-Architektur (Benutzer können eigene Komponenten hinzufügen)
- ✅ Weniger imports
- ✅ Dynamische Komponentenerstellung
- ✅ Introspection (list alle verfügbaren Komponenten)

**Impact:** Mittel - Erweiterbarkeit wird stark verbessert

---

## 🟡 Wichtige Verbesserungen (Mittelfristig)

### 5. Unit Tests fehlen

**Problem:** Nur Integration-Tests, keine Unit-Tests

**Aktueller Zustand:**
```
tests/
├── (leer oder nur integration tests)
```

**Empfehlung:**
```
tests/
├── unit/
│   ├── test_bus.py                    # Bus-Klasse testen
│   ├── test_component.py              # Component-Protokoll
│   ├── test_registry.py               # Registry-Funktionen
│   ├── test_heat_pump_block.py        # HeatPump isoliert
│   ├── test_storage_block.py          # Storage isoliert
│   ├── test_stratified_storage.py     # Stratified Storage
│   ├── test_config_merge.py           # Config deep-merge
│   ├── test_timeseries.py             # TimeSeriesTable
│   └── test_cop_calculation.py        # COP-Lookup und LMTD
├── integration/
│   ├── test_orchestrator.py           # Full workflow
│   ├── test_system_builder.py         # Model building
│   └── test_exports.py                # Export-Formate
└── fixtures/
    ├── sample_config.yaml
    └── sample_data.xlsx
```

**Befehle:**
```bash
pytest tests/unit/                   # Schnell (< 1s)
pytest tests/integration/            # Langsam (mit Solver)
pytest tests/ --cov=energis          # Mit Coverage
```

**Impact:** Hoch - Qualitätssicherung und Regressionstests

---

### 6. Type Hints inkonsistent

**Problem:** Manche Files haben Type Hints, andere nicht

**Beispiele:**

✅ **Gut** (system_builder.py):
```python
def build_model(
    table: TimeSeriesTable,
    cfg: Dict[str, Any],
    dt_h: float = 1.0
) -> pyo.ConcreteModel | None:
```

❌ **Fehlt** (viele Helper-Funktionen):
```python
def _cop_series_from_table(table, wrg_col, cfg, hp_type):  # Keine Types!
    ...
```

**Empfehlung:**
- Konsistente Type Hints in allen Public APIs
- `mypy` im CI/CD pipeline
- Schrittweise Migration bestehender Funktionen

```python
# Vorher
def _cop_series_from_table(table, wrg_col, cfg, hp_type):

# Nachher
def _cop_series_from_table(
    table: TimeSeriesTable,
    wrg_col: str | None,
    cfg: Dict[str, Any],
    hp_type: str
) -> List[float]:
```

**Impact:** Mittel - Bessere IDE-Unterstützung, weniger Bugs

---

### 7. Progress Bars für lange Optimierungen

**Problem:** Bei 8760 Zeitschritten keine Fortschrittsanzeige

**Empfehlung:**
```python
from tqdm import tqdm  # oder rich.progress

# In orchestrator.py
def run_all(config_paths: List[str], ...):
    with Progress() as progress:
        task = progress.add_task("[cyan]Loading config...", total=5)

        cfg = load_and_merge(config_paths)
        progress.update(task, advance=1)

        table = load_input_excel(...)
        progress.update(task, advance=1)

        m = build_model(table, cfg, dt_h)
        progress.update(task, advance=1)

        result = solver.solve(m, tee=False)  # Mit progress callback
        progress.update(task, advance=1)

        # ...
```

**Impact:** Niedrig - UX-Verbesserung

---

### 8. Bessere Fehlervalidierung

**Problem:** Fehlermeldungen sind generisch

**Beispiel aktuell:**
```python
# Wenn COP-Tabelle fehlerhaft ist:
ValueError: COP table axis 'x' is empty
# → Benutzer weiß nicht, WO das Problem ist
```

**Besser:**
```python
ValueError: COP table axis 'x' is empty in configuration:
  File: configs/base.yaml
  Path: heat_pumps.cop.tables.default.x
  Expected: List of temperature values (e.g., [273.15, 283.15, ...])
  Got: []
```

**Implementierung:**
```python
class ConfigValidationError(Exception):
    def __init__(self, message: str, config_path: str, yaml_path: str):
        self.config_path = config_path
        self.yaml_path = yaml_path
        super().__init__(f"{message}\n  File: {config_path}\n  Path: {yaml_path}")
```

**Impact:** Mittel - Viel bessere Developer Experience

---

### 9. COP-Berechnung cachen

**Problem:** COP wird für jeden HP und jeden Timestep neu berechnet

**Aktuell:**
```python
# Bei 4 Heat Pumps × 8760 Stunden = 35.040 Interpolationen
for hp in heat_pumps:
    COP_series = _cop_series_from_table(table, wrg_col, cfg, hp_type)
    # → Lookup-Table-Interpolation 8760× pro HP
```

**Mit Caching:**
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def _get_cop_interpolator(table_spec_hash: str):
    # Erstelle Interpolator einmal
    return BilinearInterpolator(x_points, y_points, matrix)

# Dann:
interpolator = _get_cop_interpolator(hash(table_spec))
COP_series = [interpolator(x[i], y[i]) for i in range(T)]
```

**Performance-Gewinn:** ~20-30% bei großen Modellen

**Impact:** Mittel - Performance bei großen Modellen

---

## 🟢 Nice-to-Have (Längerfristig)

### 10. Dokumentation mit Sphinx

**Empfehlung:**
```bash
docs/
├── conf.py                  # Sphinx config
├── index.rst                # Homepage
├── api/
│   ├── models.rst           # API docs für models
│   ├── blocks.rst           # API docs für blocks
│   └── utils.rst            # API docs für utils
├── tutorials/
│   ├── getting_started.rst
│   ├── heat_pump_config.rst
│   └── custom_components.rst
└── examples/
    ├── baseline_system.rst
    └── stratified_storage.rst
```

**Build:**
```bash
cd docs/
sphinx-apidoc -o api/ ../energis/
make html
# → docs/_build/html/index.html
```

**Hosting:** GitHub Pages oder Read the Docs

**Impact:** Niedrig - Langfristige Wartbarkeit

---

### 11. Logging statt Print

**Aktuell:**
```python
print(f"[LOAD] Import_Data.xlsx → {n} Schritte")
print(f"[BUILD] #el_in={len(el_in)}, #el_out={len(el_out)}")
```

**Besser:**
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Loaded {n} timesteps from Import_Data.xlsx")
logger.debug(f"Building model: {len(el_in)} el_in, {len(el_out)} el_out")
logger.warning("Storage capacity below demand peak")
logger.error("Solver failed to find optimal solution")
```

**Config:**
```python
# Benutzer kann Logging-Level setzen
logging.basicConfig(level=logging.INFO)  # oder DEBUG, WARNING, ERROR
```

**Impact:** Niedrig - Bessere Steuerung von Ausgaben

---

### 12. Pyomo-Model-Inspektor erweitern

**Aktuell:**
```python
# energis/io/model_inspector.py existiert
export_model_structure(m, outdir, prefix="pyomo_model")
```

**Erweiterungen:**
```python
# 1. Variable bounds prüfen
def check_infeasible_bounds(model):
    """Findet Variablen mit lb > ub"""
    for var in model.component_data_objects(pyo.Var):
        if var.lb and var.ub and var.lb > var.ub:
            logger.error(f"Infeasible bounds: {var} [{var.lb}, {var.ub}]")

# 2. Constraint slack analysieren
def analyze_constraint_slack(model):
    """Zeigt welche Constraints tight/slack sind"""
    for con in model.component_data_objects(pyo.Constraint):
        slack = pyo.value(con.body) - pyo.value(con.upper)
        if abs(slack) < 1e-6:
            logger.info(f"Tight constraint: {con}")

# 3. Modell-Statistiken
def get_model_stats(model):
    return {
        'n_variables': len(list(model.component_data_objects(pyo.Var))),
        'n_binary': len([v for v in model.component_data_objects(pyo.Var) if v.is_binary()]),
        'n_constraints': len(list(model.component_data_objects(pyo.Constraint))),
        'n_objectives': len(list(model.component_data_objects(pyo.Objective))),
    }
```

**Impact:** Niedrig - Debugging-Hilfe

---

### 13. Parallelisierung für Rolling Horizon

**Empfehlung:**
```python
# rolling_horizon.py
from concurrent.futures import ProcessPoolExecutor

def solve_window(window_data):
    """Solve one RH window (can be parallelized)"""
    m = build_model(window_data.table, window_data.cfg, ...)
    result = solver.solve(m)
    return extract_results(m)

# In run_rolling_horizon():
with ProcessPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(solve_window, window)
        for window in rolling_windows
    ]
    results = [f.result() for f in futures]
```

**Vorsicht:** Nur für unabhängige Windows (nicht bei terminal_policy="cyclic")

**Impact:** Niedrig - Speedup bei langen RH-Läufen

---

### 14. Scenario-Vergleichs-Tool

**Empfehlung:**
```python
# energis/utils/compare_scenarios.py

def compare_scenarios(scenario_dirs: List[str]) -> pd.DataFrame:
    """
    Vergleicht mehrere Szenarien.

    Args:
        scenario_dirs: Liste von Export-Verzeichnissen

    Returns:
        DataFrame mit Vergleichsmetrik
    """
    results = []
    for sdir in scenario_dirs:
        summary = json.load(open(f"{sdir}/summary.json"))
        results.append({
            'scenario': sdir,
            'total_cost': summary['objective']['OBJ_value_EUR'],
            'co2_emissions': summary['grid']['Total_CO2_emissions_t'],
            'hp_capacity': sum(hp['Thermal_capacity_MW']
                              for k, hp in summary.items()
                              if k.startswith('heat_pump_')),
            # ...
        })
    return pd.DataFrame(results)
```

**CLI:**
```bash
python -m energis.compare exports/scenario1/ exports/scenario2/ exports/scenario3/
```

**Impact:** Niedrig - Nützlich für Parameterstudien

---

## 📊 Prioritätsübersicht

| Verbesserung | Priorität | Aufwand | Impact | Status |
|--------------|-----------|---------|--------|--------|
| 1. CLI-Interface | 🔴 Hoch | 1h | Hoch | ✅ Erledigt |
| 2. Stratified Storage Integration | 🔴 Hoch | 4h | Hoch | ⏸️ Offen |
| 3. Bus-System konsequent nutzen | 🔴 Hoch | 8h | Mittel | ⏸️ Offen |
| 4. Component Registry nutzen | 🔴 Hoch | 4h | Mittel | ⏸️ Offen |
| 5. Unit Tests | 🟡 Mittel | 16h | Hoch | ⏸️ Offen |
| 6. Type Hints | 🟡 Mittel | 8h | Mittel | ⏸️ Offen |
| 7. Progress Bars | 🟡 Mittel | 2h | Niedrig | ⏸️ Offen |
| 8. Fehlervalidierung | 🟡 Mittel | 4h | Mittel | ⏸️ Offen |
| 9. COP Caching | 🟡 Mittel | 4h | Mittel | ⏸️ Offen |
| 10. Sphinx Docs | 🟢 Niedrig | 16h | Niedrig | ⏸️ Offen |
| 11. Logging | 🟢 Niedrig | 4h | Niedrig | ⏸️ Offen |
| 12. Model Inspector | 🟢 Niedrig | 4h | Niedrig | ⏸️ Offen |
| 13. Parallelisierung | 🟢 Niedrig | 8h | Niedrig | ⏸️ Offen |
| 14. Scenario-Vergleich | 🟢 Niedrig | 4h | Niedrig | ⏸️ Offen |

---

## 🚀 Empfohlene Roadmap

### Phase 1: Quick Wins (1-2 Wochen)
✅ CLI-Interface (erledigt)
☐ Stratified Storage Integration
☐ Bessere Fehlervalidierung

### Phase 2: Architektur (3-4 Wochen)
☐ Bus-System konsequent nutzen
☐ Component Registry aktivieren
☐ Unit Tests aufbauen

### Phase 3: Qualität (4-6 Wochen)
☐ Type Hints vervollständigen
☐ COP Caching
☐ Progress Bars

### Phase 4: Dokumentation (2-3 Wochen)
☐ Sphinx Dokumentation
☐ Tutorial-Videos
☐ Beispiel-Galerie

---

## 💡 Zusammenfassung

**Stärken des Frameworks:**
- ✅ Solide Architektur-Grundlagen
- ✅ Modularer Aufbau
- ✅ Gute Abstraktionen (Bus, Component, Registry)
- ✅ Umfangreiche Komponenten-Bibliothek

**Verbesserungspotenzial:**
- ⚠️ Bestehende Abstraktionen werden nicht voll genutzt
- ⚠️ Testing-Coverage niedrig
- ⚠️ Dokumentation könnte umfangreicher sein
- ⚠️ Performance-Optimierungen möglich

**Empfehlung:**
Fokus auf **Phase 1** (Quick Wins) und **Phase 2** (Architektur), um die bestehenden guten Abstraktionen konsequent zu nutzen. Das würde die Erweiterbarkeit und Wartbarkeit deutlich verbessern.
