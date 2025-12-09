# EnerGIS Framework - Comprehensive Test Plan

## 🎯 Overview

This test plan covers all features implemented in Sprints 1-4:

1. **Sprint 1**: Templates, Auto-Layout, PNG/SVG Exports
2. **Sprint 2**: Component Registry
3. **Sprint 3**: Stratified Storage
4. **Sprint 4**: Geographic Visualization

---

## 📋 Test Scope

### In Scope
- ✅ Network Designer Templates
- ✅ Auto-Layout Algorithms
- ✅ PNG/SVG Export
- ✅ Component Registry API
- ✅ Registry CLI Tools
- ✅ Stratified Storage Configuration
- ✅ Storage Type Selection in UI
- ✅ Geographic Map Visualization
- ✅ Coordinate Conversion
- ✅ Integration with existing workflow

### Out of Scope
- ⚠️ Phase 4 Thermal Network features (not implemented)
- ⚠️ Performance/load testing (future)
- ⚠️ Multi-user/concurrent access (future)

---

## 🧪 Test Strategy

### Test Levels

1. **Unit Tests**: Individual functions and methods
2. **Integration Tests**: Component interactions
3. **System Tests**: End-to-end workflows
4. **Manual Tests**: UI and visual verification

### Test Environment

```bash
# Python version
Python >= 3.8

# Required dependencies
pip install -r requirements.txt
pip install folium  # For geographic visualization
pip install kaleido  # For PNG/SVG export (optional)

# Framework installation
pip install -e .
```

---

## 📝 Test Cases

### Sprint 1: Templates, Auto-Layout, Exports

#### TC-S1-001: Load Network Template

**Objective**: Verify template loading functionality

**Preconditions**:
- Network Designer dashboard running
- Templates defined in `network_templates.py`

**Steps**:
1. Start dashboard: `python start_network_designer.py`
2. Select template from dropdown (e.g., "Simple HP + Storage")
3. Click "✨ Template laden" button

**Expected Result**:
- Template loads successfully
- Components appear on canvas
- Connections are established
- Component properties set correctly
- Console shows: "✅ Template geladen: [template name]"

**Status**: ⏸️ Pending

---

#### TC-S1-002: Apply Hierarchical Auto-Layout

**Objective**: Verify hierarchical layout algorithm

**Preconditions**:
- Network with 3+ components created
- Components not yet arranged

**Steps**:
1. Create network with: 1 producer, 1 storage, 1 consumer
2. Select "Hierarchisch" from layout dropdown
3. Click "🎯 Layout anwenden" button

**Expected Result**:
- Components arranged left-to-right: Producer → Storage → Consumer
- Vertical centering
- No overlapping components
- Console shows: "✅ Layout angewendet: Hierarchisch"

**Status**: ⏸️ Pending

---

#### TC-S1-003: Apply Grid Auto-Layout

**Objective**: Verify grid layout algorithm

**Steps**:
1. Create network with 6+ components
2. Select "Grid" from layout dropdown
3. Click "🎯 Layout anwenden"

**Expected Result**:
- Components arranged in grid (3 columns)
- Equal spacing
- No overlapping
- Console shows success message

**Status**: ⏸️ Pending

---

#### TC-S1-004: Apply Force-Directed Layout

**Objective**: Verify force-directed layout algorithm

**Steps**:
1. Create complex network (5+ components, multiple connections)
2. Select "Force-Directed" from layout dropdown
3. Click "🎯 Layout anwenden"

**Expected Result**:
- Components arranged to minimize connection length
- Connected components closer together
- No overlapping
- Aesthetically pleasing arrangement

**Status**: ⏸️ Pending

---

#### TC-S1-005: Snap to Grid

**Objective**: Verify snap-to-grid functionality

**Steps**:
1. Place components at arbitrary positions (e.g., x=173, y=247)
2. Click "⊞ Snap to Grid" button

**Expected Result**:
- All component coordinates become multiples of 50
- Components visually aligned to grid
- Console shows: "✅ Komponenten am Raster ausgerichtet"

**Status**: ⏸️ Pending

---

#### TC-S1-006: Export Network as PNG

**Objective**: Verify PNG export functionality

**Preconditions**:
- `pip install kaleido` (required for image export)

**Steps**:
1. Create network with 3+ components
2. Click "🖼️ PNG exportieren" button

**Expected Result**:
- PNG file created at `exports/network_diagram.png`
- Image shows network diagram
- Resolution: 1200x800, scale=2 (high quality)
- Console shows: "✅ PNG exportiert: exports/network_diagram.png"

**Fallback**: If kaleido not installed, shows error with install instruction

**Status**: ⏸️ Pending

---

#### TC-S1-007: Export Network as SVG

**Objective**: Verify SVG export functionality

**Preconditions**:
- `pip install kaleido`

**Steps**:
1. Create network with 3+ components
2. Click "📐 SVG exportieren" button

**Expected Result**:
- SVG file created at `exports/network_diagram.svg`
- Scalable vector graphic (can zoom without quality loss)
- Console shows success message

**Status**: ⏸️ Pending

---

### Sprint 2: Component Registry

#### TC-S2-001: List All Registered Components

**Objective**: Verify component discovery

**Steps**:
1. Run CLI command:
   ```bash
   python -m energis.models.component_utils list
   ```

**Expected Result**:
```
================================================================================
  EnerGIS Component Registry
================================================================================

📂 CONVERTER
--------------------------------------------------------------------------------

  • heat_pump
    Class: HeatPumpBlock
    Module: energis.models.blocks.heat_pump

  • thermal_generator
    ...

📂 STORAGE
--------------------------------------------------------------------------------

  • storage
    Class: StorageBlock
    ...

  • stratified_storage
    Class: StratifiedStorageBlock
    ...

Total: 5 components registered
```

**Status**: ⏸️ Pending

---

#### TC-S2-002: Get Component Info via CLI

**Objective**: Verify component inspection

**Steps**:
```bash
python -m energis.models.component_utils info heat_pump
```

**Expected Result**:
- Shows component metadata
- Lists required parameters (name, min_load, cop_series, etc.)
- Lists optional parameters with defaults
- Shows description

**Status**: ⏸️ Pending

---

#### TC-S2-003: List Components by Category

**Objective**: Verify category filtering

**Steps**:
```bash
python -m energis.models.component_utils list --category converter
```

**Expected Result**:
- Shows only converter components
- Includes: heat_pump, thermal_generator, p2h

**Status**: ⏸️ Pending

---

#### TC-S2-004: Export Registry Documentation

**Objective**: Verify registry export

**Steps**:
```bash
python -m energis.models.component_utils export exports/registry_docs.json
```

**Expected Result**:
- JSON file created
- Contains all component metadata
- Valid JSON structure
- Console shows: "✅ Exported registry documentation to: exports/registry_docs.json"

**Status**: ⏸️ Pending

---

#### TC-S2-005: Register Custom Component

**Objective**: Verify custom component registration

**Steps**:
1. Create custom component:
   ```python
   from energis.models.component import BaseComponent
   from energis.models.registry import register_component

   @register_component(
       "test_component",
       category="converter",
       description="Test component for registry"
   )
   class TestComponent(BaseComponent):
       def __init__(self, name: str):
           super().__init__(name)

       def attach(self, model, time_set, config, buses):
           return {'flows': {}}

       def validate_config(self, config):
           pass
   ```

2. Check registration:
   ```python
   from energis.models.registry import get_registry
   registry = get_registry()
   assert registry.is_registered('test_component')
   ```

**Expected Result**:
- Component registered successfully
- Appears in registry listing
- Can be retrieved via `registry.get('test_component')`

**Status**: ⏸️ Pending

---

#### TC-S2-006: Programmatic Component Discovery

**Objective**: Verify registry API usage

**Steps**:
```python
from energis.models.component_utils import (
    list_all_components,
    get_component_info,
    discover_components_by_category
)

# List all
components = list_all_components()
assert len(components) >= 5

# Get info
info = get_component_info('heat_pump')
assert info is not None
assert info['category'] == 'converter'

# Discover by category
storage_comps = discover_components_by_category('storage')
assert 'storage' in storage_comps
assert 'stratified_storage' in storage_comps
```

**Expected Result**:
- All API functions work correctly
- Return expected data structures

**Status**: ⏸️ Pending

---

### Sprint 3: Stratified Storage

#### TC-S3-001: Select Storage Type in UI

**Objective**: Verify storage type selector in Network Designer

**Steps**:
1. Start dashboard: `python start_network_designer.py`
2. Add storage component to canvas
3. Click on storage to open properties panel
4. Observe "Speicher-Typ" dropdown

**Expected Result**:
- Dropdown shows two options: "simple", "stratified"
- Default value: "simple"
- Help text shows below:
  - simple: "⚡ Einfacher Speicher (single-zone)"
  - stratified: "🌡️ Geschichteter Speicher (2-zone thermocline)"

**Status**: ⏸️ Pending

---

#### TC-S3-002: Configure Simple Storage

**Objective**: Verify simple storage configuration

**Steps**:
1. Add storage component
2. Set storage type: "simple"
3. Set capacity: 100 MWh
4. Set efficiency: 0.98
5. Export to YAML

**Expected Result**:
- YAML contains:
  ```yaml
  system:
    storage:
      type: simple
      eff_charge: 0.98
      eff_discharge: 0.98
      loss_hour: 0.9999
  ```

**Status**: ⏸️ Pending

---

#### TC-S3-003: Configure Stratified Storage

**Objective**: Verify stratified storage configuration

**Steps**:
1. Add storage component
2. Set storage type: "stratified"
3. Set capacity: 100 MWh
4. Set efficiency: 0.98
5. Export to YAML

**Expected Result**:
- YAML contains:
  ```yaml
  system:
    storage:
      type: stratified
      T_hot_C: 90.0
      T_cold_C: 40.0
      T_ambient_C: 15.0
      T_ground_C: 10.0
      aspect_ratio: 1.5
      geometry_type: tank
      U_top: 0.3
      U_side: 0.2
      U_bottom: 0.15
      V_hot_init_fraction: 0.5
  ```

**Status**: ⏸️ Pending

---

#### TC-S3-004: Stratified Storage Additional Parameters Display

**Objective**: Verify UI shows stratified-specific info

**Steps**:
1. Add storage component
2. Select "stratified" from type dropdown

**Expected Result**:
- Additional info box appears in properties panel
- Shows:
  - Heiße Zone: 90°C (oben)
  - Kalte Zone: 40°C (unten)
  - Geometrie: Automatisch berechnet
  - Verluste: Geometrie-basiert

**Status**: ⏸️ Pending

---

#### TC-S3-005: Run Simulation with Simple Storage

**Objective**: Verify simple storage simulation works

**Steps**:
1. Create network: HP → Simple Storage → Consumer
2. Export YAML (with `type: simple`)
3. Run simulation:
   ```bash
   python -m energis.run.rolling_horizon exports/network_config.yaml
   ```

**Expected Result**:
- Simulation completes successfully
- Console shows: "[BUILD] Using simple storage (single-zone model)"
- Results include storage SOC, charge/discharge

**Status**: ⏸️ Pending

---

#### TC-S3-006: Run Simulation with Stratified Storage

**Objective**: Verify stratified storage simulation works

**Steps**:
1. Create network: HP → Stratified Storage → Consumer
2. Export YAML (with `type: stratified`)
3. Run simulation

**Expected Result**:
- Simulation completes successfully
- Console shows: "[BUILD] Using stratified storage (2-zone thermocline model)"
- Results include:
  - Storage SOC
  - Hot zone volume (V_hot_m3)
  - Cold zone volume (V_cold_m3)
  - Geometry-based heat losses

**Status**: ⏸️ Pending

---

#### TC-S3-007: Compare Simple vs Stratified Results

**Objective**: Verify different storage models give different results

**Steps**:
1. Run same network with simple storage → save results
2. Run same network with stratified storage → save results
3. Compare:
   - Total costs
   - Storage capacity
   - Energy losses

**Expected Result**:
- Stratified storage should show:
  - 2-5% more accurate loss modeling
  - Potentially different optimal capacity
  - More detailed state variables

**Status**: ⏸️ Pending

---

### Sprint 4: Geographic Visualization

#### TC-S4-001: Create Geographic Map

**Objective**: Verify map creation from network

**Preconditions**:
- `pip install folium`

**Steps**:
```python
from energis.io.network_designer import create_network_designer
from energis.io.geographic_viewer import create_geographic_viewer

designer = create_network_designer()
designer.add_component(x=200, y=200, comp_type='heat_pump')
designer.add_component(x=500, y=400, comp_type='storage')
designer.add_component(x=800, y=600, comp_type='consumer')

viewer = create_geographic_viewer(
    components=designer.components,
    connections=designer.connections,
    geo_bounds=(48.0, 11.4, 48.3, 11.8)  # Munich
)

m = viewer.create_map()
viewer.save_html('exports/test_map.html')
```

**Expected Result**:
- HTML file created at `exports/test_map.html`
- Opening in browser shows:
  - Interactive map centered on Munich
  - 3 markers (heat pump, storage, consumer)
  - 2 connection lines
  - Legend
  - Map controls (zoom, pan, fullscreen, measure)

**Status**: ⏸️ Pending

---

#### TC-S4-002: Verify Component Popups

**Objective**: Verify map markers show component details

**Steps**:
1. Create map (as in TC-S4-001)
2. Open HTML in browser
3. Click on heat pump marker

**Expected Result**:
- Popup appears with:
  - Title: "Wärmepumpe"
  - ID: [component_id]
  - Status: [existing/investment]
  - Leistung: [capacity] MW
  - COP: [cop value]

**Status**: ⏸️ Pending

---

#### TC-S4-003: Verify Coordinate Conversion

**Objective**: Verify canvas-to-geographic conversion accuracy

**Steps**:
```python
from energis.io.geographic_viewer import canvas_to_geographic, geographic_to_canvas

canvas_bounds = (0, 0, 1000, 800)
geo_bounds = (48.0, 11.4, 48.3, 11.8)

# Test corner points
lat1, lon1 = canvas_to_geographic(0, 0, canvas_bounds, geo_bounds)
assert abs(lat1 - 48.3) < 0.01  # Top-left
assert abs(lon1 - 11.4) < 0.01

lat2, lon2 = canvas_to_geographic(1000, 800, canvas_bounds, geo_bounds)
assert abs(lat2 - 48.0) < 0.01  # Bottom-right
assert abs(lon2 - 11.8) < 0.01

# Test round-trip
x, y = 500, 400
lat, lon = canvas_to_geographic(x, y, canvas_bounds, geo_bounds)
x2, y2 = geographic_to_canvas(lat, lon, canvas_bounds, geo_bounds)
assert abs(x - x2) < 1.0
assert abs(y - y2) < 1.0
```

**Expected Result**:
- All assertions pass
- Round-trip conversion accurate to < 1 pixel

**Status**: ⏸️ Pending

---

#### TC-S4-004: Test Multiple Map Tiles

**Objective**: Verify different map styles work

**Steps**:
```python
tiles_list = [
    'OpenStreetMap',
    'CartoDB positron',
    'CartoDB dark_matter',
]

for tiles in tiles_list:
    m = viewer.create_map(tiles=tiles)
    viewer.save_html(f'exports/map_{tiles.replace(" ", "_")}.html')
```

**Expected Result**:
- All 3 HTML files created
- Each shows different map style
- All display network correctly

**Status**: ⏸️ Pending

---

#### TC-S4-005: Test Map Export from Dashboard

**Objective**: Verify map export button works

**Steps**:
1. Create network in Network Designer
2. Add geographic visualization tab/button (if integrated)
3. Click "🗺️ Karte exportieren (HTML)"

**Expected Result**:
- HTML file exported to `exports/network_map.html`
- Console shows: "✅ Karte exportiert: exports/network_map.html"

**Status**: ⏸️ Pending

---

## 🔄 Integration Tests

### INT-001: End-to-End Workflow (Templates + Export + Simulation)

**Objective**: Verify complete workflow with templates

**Steps**:
1. Start Network Designer
2. Load "Brownfield Expansion" template
3. Modify storage type to "stratified"
4. Export YAML
5. Run simulation
6. View results

**Expected Result**:
- All steps complete successfully
- Simulation produces results
- Results reflect stratified storage behavior

**Status**: ⏸️ Pending

---

### INT-002: Registry + System Builder Integration

**Objective**: Verify system_builder can use registry (optional)

**Steps**:
1. Check if system_builder.py uses registry for component creation
2. If yes: Verify all component types work
3. If no: This is expected (registry is available but not mandatory)

**Expected Result**:
- Existing system_builder.py continues to work
- Registry available for future use

**Status**: ⏸️ Pending

---

### INT-003: Geographic Viewer + Network Designer Integration

**Objective**: Verify geographic viewer can display Network Designer output

**Steps**:
1. Create complex network in Network Designer (5+ components)
2. Export component/connection data
3. Pass to GeographicNetworkViewer
4. Generate map

**Expected Result**:
- All components appear on map
- All connections shown
- Coordinate conversion accurate

**Status**: ⏸️ Pending

---

## 📊 Test Results Summary

| Sprint | Total Tests | Passed | Failed | Blocked | Pending |
|--------|-------------|--------|--------|---------|---------|
| Sprint 1 | 7 | 0 | 0 | 0 | 7 |
| Sprint 2 | 6 | 0 | 0 | 0 | 6 |
| Sprint 3 | 7 | 0 | 0 | 0 | 7 |
| Sprint 4 | 5 | 0 | 0 | 0 | 5 |
| Integration | 3 | 0 | 0 | 0 | 3 |
| **TOTAL** | **28** | **0** | **0** | **0** | **28** |

---

## 🐛 Bug Tracking

### Known Issues

| ID | Sprint | Severity | Description | Status |
|----|--------|----------|-------------|--------|
| - | - | - | No known issues yet | N/A |

### Severity Levels

- **Critical**: System crash, data loss
- **High**: Major functionality broken
- **Medium**: Feature partially working
- **Low**: Minor cosmetic issues

---

## ✅ Acceptance Criteria

### Sprint 1: Templates & Auto-Layout
- ✅ At least 4 network templates available
- ✅ 4 auto-layout algorithms implemented (hierarchical, grid, circular, force)
- ✅ PNG/SVG export works (with kaleido installed)
- ✅ Snap-to-grid functionality works

### Sprint 2: Component Registry
- ✅ All existing blocks registered
- ✅ CLI tools functional (list, info, export)
- ✅ Programmatic API works
- ✅ Custom component registration supported

### Sprint 3: Stratified Storage
- ✅ Storage type selector in UI
- ✅ YAML export includes storage type
- ✅ Simple storage simulation works
- ✅ Stratified storage simulation works
- ✅ Geometry-based loss calculation

### Sprint 4: Geographic Visualization
- ✅ Interactive maps with Folium
- ✅ Coordinate conversion accurate
- ✅ Component popups with details
- ✅ Multiple tile styles supported
- ✅ HTML export works

---

## 📝 Test Execution Instructions

### Prerequisites

```bash
# Install all dependencies
pip install -r requirements.txt
pip install folium kaleido

# Install framework
pip install -e .

# Verify installation
python check_system.py
```

### Running Tests

**Manual UI Tests (Sprints 1, 3, 4):**
```bash
# Start dashboard
python start_network_designer.py

# Follow test case steps in browser
```

**CLI Tests (Sprint 2):**
```bash
# Run registry CLI commands
python -m energis.models.component_utils list
python -m energis.models.component_utils info heat_pump
# etc.
```

**Programmatic Tests (All Sprints):**
```bash
# Run demo scripts
python examples/component_registry_demo.py
python examples/stratified_storage_example.py
python -m energis.io.geographic_viewer
```

**Integration Tests:**
```bash
# Run complete workflow notebook
jupyter notebook notebooks/complete_workflow.ipynb
# Execute all cells
```

---

## 📅 Test Schedule

### Recommended Testing Order

1. **Day 1**: Sprint 2 (Component Registry)
   - Fastest to test (CLI commands)
   - No UI dependencies

2. **Day 2**: Sprint 3 (Stratified Storage)
   - Test UI selector
   - Run small simulations (< 100 timesteps)

3. **Day 3**: Sprint 1 (Templates & Auto-Layout)
   - Visual verification in dashboard
   - Export tests

4. **Day 4**: Sprint 4 (Geographic Visualization)
   - Map creation and display
   - Coordinate conversion verification

5. **Day 5**: Integration Tests
   - End-to-end workflows
   - Performance checks

---

## 🔍 Test Coverage

### Code Coverage Goals

- **Target**: > 80% line coverage
- **Critical paths**: 100% coverage
- **UI code**: Manual testing acceptable

### Automated Testing (Future)

```python
# Example pytest structure (to be implemented)

# tests/test_templates.py
def test_load_template():
    pass

def test_hierarchical_layout():
    pass

# tests/test_registry.py
def test_list_components():
    pass

def test_register_component():
    pass

# tests/test_stratified_storage.py
def test_storage_type_export():
    pass

def test_stratified_simulation():
    pass

# tests/test_geographic_viewer.py
def test_coordinate_conversion():
    pass

def test_map_creation():
    pass
```

---

## 📋 Test Deliverables

### Test Artifacts

1. **Test Execution Report**: This document (updated with results)
2. **Bug Reports**: Issues found during testing
3. **Test Data**: Sample networks, configs, outputs
4. **Screenshots**: UI verification evidence
5. **Performance Metrics**: Simulation times, memory usage

### Documentation

- ✅ TEST_PLAN.md (this file)
- ✅ WORKFLOW_GUIDE.md (user guide)
- ✅ COMPONENT_REGISTRY.md (registry docs)
- ✅ STRATIFIED_STORAGE.md (storage docs)
- ✅ GEOGRAPHIC_VISUALIZATION.md (map docs)

---

## ✅ Sign-Off Criteria

**Testing Complete When:**
- [ ] All 28 test cases executed
- [ ] Pass rate ≥ 95% (max 1-2 failures)
- [ ] All critical bugs resolved
- [ ] Documentation complete
- [ ] Integration tests pass
- [ ] User acceptance criteria met

**Approved By:**
- [ ] Developer: _________________  Date: _______
- [ ] Reviewer: _________________  Date: _______
- [ ] Product Owner: ____________  Date: _______

---

## 📞 Support

For questions or issues:
- **GitHub Issues**: https://github.com/anthropics/claude-code/issues
- **Documentation**: `docs/` directory
- **Examples**: `examples/` directory
- **Notebooks**: `notebooks/` directory

---

**Last Updated**: 2025-12-09
**Version**: 1.0
**Status**: Ready for Execution
