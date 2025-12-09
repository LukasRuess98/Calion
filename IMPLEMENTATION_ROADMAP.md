# Implementation Roadmap - Prioritized Features

## 🎯 Current Status

### ✅ Implemented (Network Designer v1.0)
- Interactive coordinate-based component placement
- YAML export/import (system_builder compatible)
- Live validation
- Runner integration
- Results viewer
- Complete workflow documentation

### ❌ Not Implemented (from original analysis)

#### High Priority Missing Features:

1. **Component Registry Integration** ⭐⭐⭐⭐⭐
   - Status: NOT implemented
   - Effort: 1-2 weeks
   - Risk: Low
   - Benefit: Plugin architecture, better maintainability

2. **Stratified Storage Integration** ⭐⭐⭐⭐⭐
   - Status: NOT implemented (code exists but not usable)
   - Effort: 1 week
   - Risk: Low
   - Benefit: Advanced storage modeling

3. **Geographic Network Visualization** ⭐⭐⭐⭐⭐
   - Status: NOT implemented
   - Effort: 2-3 weeks
   - Risk: Medium
   - Benefit: Visual network topology with real coordinates

4. **Multi-Scenario Batch Runner** ⭐⭐⭐⭐
   - Status: NOT implemented
   - Effort: 1-2 weeks
   - Risk: Low
   - Benefit: Automated parameter studies

5. **Sensitivity Analysis Dashboard** ⭐⭐⭐⭐
   - Status: NOT implemented
   - Effort: 2 weeks
   - Risk: Low
   - Benefit: Interactive what-if analysis

6. **Bus-System Refactoring** ⭐⭐⭐⭐
   - Status: NOT implemented
   - Effort: 2-3 weeks
   - Risk: Medium (refactoring)
   - Benefit: Cleaner architecture

#### Phase 4: Thermal Network Features ⚠️ HIGH RISK

**IMPORTANT: This is PLANNING ONLY - NO CODE EXISTS!**

- PipeBlock implementation
- NodeBlock implementation
- Pressure drop constraints
- Heat loss along pipes
- Mass balance per node
- Geographic optimization
- Hydraulic network optimization
- Pipe dimensioning (DN selection)

**Status:**
- ❌ Not implemented
- ✅ Only documentation (8000+ lines)
- Effort: 6-8 weeks
- Risk: HIGH (complex, breaking changes)
- Recommendation: Separate Epic, own branch

---

## 🚀 Recommended Implementation Plan

### Sprint 1: Quick Wins (1-2 weeks)

**Goal:** Immediate improvements to existing Network Designer

**Tasks:**
1. Add template library
   - Pre-defined network templates (brownfield, greenfield, etc.)
   - Load template → auto-populate canvas

2. Improve coordinate system
   - Snap-to-grid
   - Auto-layout algorithm (arrange components automatically)
   - Zoom/pan controls

3. Enhanced validation
   - Topology checks (cycles, isolated components)
   - Capacity plausibility checks
   - Warning system (yellow = warning, red = error)

4. Export improvements
   - Export to PNG/SVG (network diagram)
   - Export to Excel (component list)
   - Export comparison (multiple scenarios)

**Deliverables:**
- Template system
- Better UX
- Visual exports

---

### Sprint 2: Component Registry (1-2 weeks) ⭐⭐⭐⭐⭐

**Goal:** Plugin architecture for components

**Implementation:**

```python
# energis/models/registry.py
class ComponentRegistry:
    _instance = None
    _components = {}

    @classmethod
    def register(cls, component_type, category):
        def decorator(component_class):
            cls._components[component_type] = {
                'class': component_class,
                'category': category
            }
            return component_class
        return decorator

    @classmethod
    def create(cls, component_type, **kwargs):
        if component_type not in cls._components:
            raise ValueError(f"Unknown component: {component_type}")
        return cls._components[component_type]['class'](**kwargs)

# energis/models/blocks/heat_pump.py
from energis.models.registry import ComponentRegistry

@ComponentRegistry.register("heat_pump", category="converter")
class HeatPumpBlock(BaseComponent):
    ...

# Usage in system_builder.py
from energis.models.registry import ComponentRegistry

registry = ComponentRegistry()
hp_block = registry.create("heat_pump", id="HP1", **config)
```

**Benefits:**
- Easy to add new components
- Better testability
- Plugin system for custom components

---

### Sprint 3: Stratified Storage Integration (1 week) ⭐⭐⭐⭐⭐

**Goal:** Make StratifiedStorageBlock usable in system_builder

**Implementation:**

```yaml
# Config extension
system:
  storage:
    enabled: true
    type: stratified  # NEW: "simple" or "stratified"

    # Stratified-specific params
    T_hot_C: 90.0
    T_cold_C: 40.0
    n_layers: 10
    mixing_coefficient: 0.1
```

```python
# In system_builder.py
def _add_storage(model, timesteps, cfg):
    sto_cfg = cfg['system']['storage']

    if sto_cfg.get('type') == 'stratified':
        from energis.models.blocks.stratified_storage import StratifiedStorageBlock
        block = StratifiedStorageBlock(
            n_layers=sto_cfg.get('n_layers', 10),
            T_hot=sto_cfg.get('T_hot_C', 90.0) + 273.15,
            T_cold=sto_cfg.get('T_cold_C', 40.0) + 273.15,
            # ...
        )
    else:
        # Existing simple storage
        block = StorageBlock(...)

    block.attach(model, timesteps, sto_cfg)
```

**Benefits:**
- Advanced thermal storage modeling
- Temperature stratification effects
- Better accuracy for large storage

---

### Sprint 4: Geographic Visualization (2-3 weeks) ⭐⭐⭐⭐⭐

**Goal:** Interactive map for network topology

**Implementation:**

```python
# energis/io/geographic_viewer.py
import folium
import panel as pn
from panel.pane import HTML

class GeographicNetworkViewer:
    def __init__(self, components, connections):
        self.components = components
        self.connections = connections

    def create_map(self, center_lat=48.0, center_lon=11.0):
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=13,
            tiles='OpenStreetMap'
        )

        # Add components as markers
        for comp in self.components:
            # Convert grid coordinates to lat/lon
            # (for now, mock conversion - later use real geo data)
            lat = center_lat + comp.y / 10000
            lon = center_lon + comp.x / 10000

            # Color by type
            colors = {
                'heat_pump': 'red',
                'boiler': 'orange',
                'storage': 'blue',
                'consumer': 'green'
            }

            # Icon by status
            icon_color = 'green' if comp.status == 'existing' else 'blue'

            folium.Marker(
                location=[lat, lon],
                popup=f"""
                    <b>{comp.component_id}</b><br>
                    Type: {comp.component_type}<br>
                    Status: {comp.status}<br>
                    Capacity: {comp.properties.get('capacity_mw', 'N/A')} MW
                """,
                icon=folium.Icon(color=colors.get(comp.component_type, 'gray'))
            ).add_to(m)

        # Add connections as lines
        for conn in self.connections:
            from_comp = self._get_component(conn.from_id)
            to_comp = self._get_component(conn.to_id)

            if from_comp and to_comp:
                from_lat = center_lat + from_comp.y / 10000
                from_lon = center_lon + from_comp.x / 10000
                to_lat = center_lat + to_comp.y / 10000
                to_lon = center_lon + to_comp.x / 10000

                folium.PolyLine(
                    locations=[[from_lat, from_lon], [to_lat, to_lon]],
                    color='green',
                    weight=3,
                    opacity=0.7,
                    popup=f"{conn.from_id} → {conn.to_id}"
                ).add_to(m)

        return m

    def create_panel(self):
        """Create Panel dashboard with map"""
        m = self.create_map()

        # Convert to HTML
        map_html = m._repr_html_()

        return pn.Column(
            "## Geographic Network View",
            HTML(map_html, height=600),
            sizing_mode='stretch_both'
        )
```

**Integration in Network Designer:**

```python
# Add to network_designer.py
def create_dashboard(self):
    # ... existing code ...

    # Add Geographic View tab
    from energis.io.geographic_viewer import GeographicNetworkViewer

    geo_viewer = GeographicNetworkViewer(self.components, self.connections)
    geo_panel = geo_viewer.create_panel()

    tabs = pn.Tabs(
        ('🗺️ Designer', designer_tab),
        ('🌍 Geographic View', geo_panel),  # NEW
        ('📊 Results', results_tab),
    )
```

**Benefits:**
- Visual network overview
- Real-world context
- Better planning for brownfield

---

### Sprint 5: Batch Runner (1-2 weeks) ⭐⭐⭐⭐

**Goal:** Automated multi-scenario simulations

**Implementation:**

```python
# energis/run/batch_runner.py
from pathlib import Path
from typing import List, Dict
from energis.run.rolling_horizon import run_workflow
import yaml

class BatchRunner:
    def __init__(self, base_config: str):
        self.base_config = base_config
        self.results = {}

    def run_scenarios(self, scenario_configs: List[str], parallel=False):
        """Run multiple scenarios"""
        for scenario in scenario_configs:
            print(f"Running scenario: {scenario}")

            result = run_workflow([self.base_config, scenario])
            self.results[scenario] = result

        return self.results

    def run_parameter_sweep(
        self,
        parameter: str,
        values: List[float],
        config_path: str = 'run'
    ):
        """Parameter sweep (e.g., CO2 price from 50 to 200)"""
        results = {}

        for value in values:
            print(f"Running with {parameter} = {value}")

            overrides = {config_path: {parameter: value}}
            result = run_workflow([self.base_config], overrides=overrides)

            results[value] = result

        return results

    def export_comparison(self, output_path: str):
        """Export comparison table"""
        comparison_data = []

        for scenario_name, result in self.results.items():
            primary = result.pf_result or result.rh_result

            if primary:
                total_cost = sum(primary.costs.values())

                comparison_data.append({
                    'Scenario': scenario_name,
                    'Total_Cost_EUR': total_cost,
                    'CAPEX_EUR': sum(v for k, v in primary.costs.items() if 'investment' in k.lower()),
                    'OPEX_EUR': sum(v for k, v in primary.costs.items() if 'investment' not in k.lower()),
                })

        import pandas as pd
        df = pd.DataFrame(comparison_data)
        df.to_csv(output_path, index=False)

        return df
```

**Usage:**

```python
# Script or notebook
from energis.run.batch_runner import BatchRunner

runner = BatchRunner('configs/base.yaml')

# Scenario comparison
scenarios = [
    'configs/scenarios/baseline.yaml',
    'configs/scenarios/hp_expansion.yaml',
    'configs/scenarios/storage_upgrade.yaml'
]

results = runner.run_scenarios(scenarios)
df = runner.export_comparison('exports/scenario_comparison.csv')

print(df)
```

**Benefits:**
- Automated what-if analysis
- Easy parameter studies
- Reproducible comparisons

---

### Sprint 6: Sensitivity Analysis (2 weeks) ⭐⭐⭐⭐

**Goal:** Interactive sensitivity analysis dashboard

**Implementation:**

```python
# energis/analysis/sensitivity.py
import numpy as np
from energis.run.rolling_horizon import run_workflow

class SensitivityAnalyzer:
    def __init__(self, base_config: str):
        self.base_config = base_config

    def run_sensitivity(
        self,
        parameter_path: str,  # e.g., "costs.co2_price_eur_per_t"
        min_value: float,
        max_value: float,
        steps: int = 10,
        output_metric: str = 'total_cost'
    ):
        """Run sensitivity analysis"""

        values = np.linspace(min_value, max_value, steps)
        results = []

        for value in values:
            print(f"Running with {parameter_path} = {value}")

            # Parse path
            keys = parameter_path.split('.')
            overrides = self._build_nested_dict(keys, value)

            # Run
            result = run_workflow([self.base_config], overrides=overrides)

            # Extract metric
            primary = result.pf_result or result.rh_result
            metric_value = self._extract_metric(primary, output_metric)

            results.append({
                'parameter_value': value,
                'metric_value': metric_value
            })

        return pd.DataFrame(results)

    def _build_nested_dict(self, keys, value):
        """Build nested dict from keys"""
        if len(keys) == 1:
            return {keys[0]: value}
        return {keys[0]: self._build_nested_dict(keys[1:], value)}

    def _extract_metric(self, result, metric: str):
        """Extract metric from result"""
        if metric == 'total_cost':
            return sum(result.costs.values())
        # ... more metrics
```

**Panel Dashboard:**

```python
# Add to dashboard
import panel as pn

st.title("Sensitivitätsanalyse")

parameter = st.selectbox("Parameter", [
    "costs.co2_price_eur_per_t",
    "costs.electricity_price_eur_mwh",
    "costs.gas_price_eur_mwh",
])

min_val = st.number_input("Min", value=50.0)
max_val = st.number_input("Max", value=200.0)
steps = st.slider("Steps", 5, 20, 10)

if st.button("Run"):
    analyzer = SensitivityAnalyzer('configs/base.yaml')
    df = analyzer.run_sensitivity(parameter, min_val, max_val, steps)

    # Plot
    fig = px.line(df, x='parameter_value', y='metric_value')
    st.plotly_chart(fig)

    # Table
    st.dataframe(df)
```

**Benefits:**
- Interactive what-if analysis
- Visual parameter impact
- Decision support

---

## 🚨 Phase 4: Thermal Network Features (FUTURE)

**DO NOT IMPLEMENT NOW - Too complex, too risky**

### What would be needed:

1. **PipeBlock** (hydraulic modeling)
   ```python
   class PipeBlock:
       def pressure_drop_constraint(self, model, t):
           # Darcy-Weisbach: Δp = f * (L/D) * (ρ*v²/2)
           pass

       def heat_loss_constraint(self, model, t):
           # Q_loss = U * A * (T_fluid - T_ambient)
           pass
   ```

2. **NodeBlock** (junction modeling)
   ```python
   class NodeBlock:
       def mass_balance(self, model, t):
           # Σ m_in = Σ m_out
           pass

       def energy_balance(self, model, t):
           # Σ (m * h)_in = Σ (m * h)_out
           pass
   ```

3. **Geographic optimization**
   - Pipe lengths from coordinates
   - CAPEX = f(length, diameter)
   - Heat losses = f(length, insulation)

**Effort:** 6-8 weeks
**Risk:** HIGH (breaking changes, complex validation)
**Recommendation:** Separate Epic, prototype first

---

## 📊 Priority Matrix

| Feature | Effort | Risk | Benefit | Priority |
|---------|--------|------|---------|----------|
| Quick Wins (templates, UX) | 1-2w | LOW | MEDIUM | ⭐⭐⭐⭐⭐ |
| Component Registry | 1-2w | LOW | HIGH | ⭐⭐⭐⭐⭐ |
| Stratified Storage | 1w | LOW | HIGH | ⭐⭐⭐⭐⭐ |
| Geographic Visualization | 2-3w | MEDIUM | HIGH | ⭐⭐⭐⭐⭐ |
| Batch Runner | 1-2w | LOW | HIGH | ⭐⭐⭐⭐ |
| Sensitivity Analysis | 2w | LOW | HIGH | ⭐⭐⭐⭐ |
| Bus System Refactor | 2-3w | MEDIUM | MEDIUM | ⭐⭐⭐ |
| **Thermal Network** | **6-8w** | **HIGH** | **HIGH** | **⚠️ FUTURE** |

---

## 🎯 Recommended Next Steps

### Immediate (this week):
1. Test current Network Designer implementation
2. Identify bugs/issues
3. Gather user feedback

### Short-term (1-2 months):
1. **Sprint 1:** Quick wins (templates, UX improvements)
2. **Sprint 2:** Component Registry
3. **Sprint 3:** Stratified Storage
4. **Sprint 4:** Geographic Visualization

### Medium-term (3-4 months):
5. **Sprint 5:** Batch Runner
6. **Sprint 6:** Sensitivity Analysis

### Long-term (6+ months):
7. **Phase 4:** Thermal Network (separate Epic, prototype first)

---

## ✅ Summary

**Already implemented:**
- Network Designer v1.0 (coordinate-based design tool)
- YAML export/import
- Runner integration
- Results visualization
- Complete documentation

**Missing (from your list):**
- Component Registry ⭐⭐⭐⭐⭐
- Stratified Storage ⭐⭐⭐⭐⭐
- Geographic Visualization ⭐⭐⭐⭐⭐
- Batch Runner ⭐⭐⭐⭐
- Sensitivity Analysis ⭐⭐⭐⭐
- Thermal Network Features ⚠️ (6-8 weeks, HIGH RISK)

**Recommendation:**
Start with quick wins and high-value, low-risk features.
Save Thermal Network for later (separate Epic).
