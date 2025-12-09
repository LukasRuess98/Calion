# Geographic Network Visualization

## 🎯 Overview

EnerGIS now supports **geographic visualization** of thermal networks on interactive maps using real-world coordinates.

**Key Features:**
- 🗺️ Interactive maps powered by Folium (Leaflet)
- 📍 Real geographic coordinates (latitude/longitude)
- 🔄 Automatic conversion from canvas to geographic coordinates
- 📊 Component details in map popups
- 📏 Built-in measurement tools
- 💾 Export as standalone HTML

---

## 🚀 Quick Start

### Installation

```bash
pip install folium
```

### Basic Usage

```python
from energis.io.network_designer import create_network_designer
from energis.io.geographic_viewer import create_geographic_viewer

# Create network
designer = create_network_designer()
designer.add_component(x=200, y=200, comp_type='heat_pump')
designer.add_component(x=500, y=200, comp_type='storage')
designer.add_component(x=800, y=200, comp_type='consumer')

# Create geographic viewer
viewer = create_geographic_viewer(
    components=designer.components,
    connections=designer.connections,
    geo_bounds=(48.0, 11.4, 48.3, 11.8)  # Munich area
)

# Create interactive map
m = viewer.create_map()

# Save as HTML
viewer.save_html('exports/network_map.html')
```

---

## 📐 Coordinate System

### Canvas to Geographic Mapping

The system automatically maps canvas coordinates (x, y) to geographic coordinates (lat, lon):

```
Canvas Space              Geographic Space
┌───────────────┐        ┌──────────────┐
│ (0, 0)        │   →    │ (lat_max,    │
│               │        │  lon_min)    │
│               │        │              │
│      (1000,   │   →    │     (lat_min,│
│        800)   │        │      lon_max)│
└───────────────┘        └──────────────┘
```

**Default Bounds:**
- **Canvas**: (0, 0) to (1000, 800)
- **Geographic**: Munich area (48.0°N - 48.3°N, 11.4°E - 11.8°E)

### Custom Geographic Bounds

```python
# Berlin area
geo_bounds = (52.4, 13.3, 52.6, 13.5)

# Hamburg area
geo_bounds = (53.5, 9.9, 53.6, 10.1)

# Frankfurt area
geo_bounds = (50.0, 8.6, 50.2, 8.8)

viewer = create_geographic_viewer(
    components=components,
    connections=connections,
    geo_bounds=geo_bounds
)
```

### Coordinate Conversion Functions

```python
from energis.io.geographic_viewer import canvas_to_geographic, geographic_to_canvas

# Convert canvas to geographic
lat, lon = canvas_to_geographic(
    x=500, y=400,
    canvas_bounds=(0, 0, 1000, 800),
    geo_bounds=(48.0, 11.4, 48.3, 11.8)
)

# Convert geographic to canvas
x, y = geographic_to_canvas(
    lat=48.15, lon=11.6,
    canvas_bounds=(0, 0, 1000, 800),
    geo_bounds=(48.0, 11.4, 48.3, 11.8)
)
```

---

## 🎨 Map Customization

### Map Tiles

Choose from various map styles:

```python
# OpenStreetMap (default)
m = viewer.create_map(tiles='OpenStreetMap')

# CartoDB Positron (light theme)
m = viewer.create_map(tiles='CartoDB positron')

# CartoDB Dark Matter (dark theme)
m = viewer.create_map(tiles='CartoDB dark_matter')

# Stamen Terrain (topographic)
m = viewer.create_map(tiles='Stamen Terrain')

# Stamen Toner (high contrast)
m = viewer.create_map(tiles='Stamen Toner')
```

### Map Center and Zoom

```python
# Center on specific location with zoom
m = viewer.create_map(
    center=(48.137154, 11.576124),  # Munich center
    zoom_start=13  # Higher = more zoomed in
)
```

### Component Styling

Components are automatically styled based on type and status:

| Component Type | Icon | Color (Existing) | Color (Investment) |
|----------------|------|------------------|-------------------|
| Heat Pump | 🔥 fire | Dark Blue | Light Red |
| Boiler | 🔥 fire-burner | Dark Blue | Light Red |
| CHP | ⚡ bolt | Dark Blue | Light Red |
| Storage | 📦 database | Dark Blue | Light Red |
| Consumer | 🏠 home | Dark Blue | Light Red |

---

## 📊 Interactive Features

### Map Controls

**Built-in controls:**
- 🔍 **Zoom**: Mouse wheel or +/- buttons
- 🖱️ **Pan**: Click and drag
- 📏 **Measure**: Distance and area measurement tool
- 🔲 **Fullscreen**: Fullscreen mode button

### Component Popups

Click on any component marker to see details:

```
┌─────────────────────────┐
│ Wärmepumpe              │
├─────────────────────────┤
│ ID:        HP_1         │
│ Status:    existing     │
│ Leistung:  10.0 MW      │
│ COP:       3.5          │
└─────────────────────────┘
```

### Connection Lines

- Connections shown as blue lines
- Click on line to see source → target
- Arrows indicate flow direction

---

## 💾 Export Options

### Export as HTML

```python
# Standalone HTML file
viewer.save_html('exports/network_map.html')
```

**Features of exported HTML:**
- Fully interactive (no Python needed)
- Shareable (just open in browser)
- All map features included
- Self-contained file

### Embed in Dashboard

```python
import panel as pn

# Create Panel dashboard with embedded map
dashboard = viewer.create_dashboard_panel()
dashboard.servable()
```

### Export as PNG/PDF

Use browser print function:
1. Open HTML in browser
2. Press Ctrl+P (Windows/Linux) or Cmd+P (Mac)
3. Select "Save as PDF" or print

---

## 🗺️ Use Cases

### 1. District Heating Network Planning

```python
# Munich district heating network
geo_bounds = (48.1, 11.5, 48.2, 11.65)  # Central Munich

# Add multiple heat sources and consumers
for building in buildings_df.itertuples():
    x, y = geographic_to_canvas(
        building.lat, building.lon,
        canvas_bounds=(0, 0, 1000, 800),
        geo_bounds=geo_bounds
    )
    designer.add_component(x=x, y=y, comp_type='consumer')
    consumer = designer.components[-1]
    consumer.properties['demand_mw'] = building.heat_demand
```

### 2. Industrial Site Layout

```python
# Industrial park in Frankfurt
geo_bounds = (50.05, 8.65, 50.08, 8.68)

# Map real building positions
buildings = {
    'Production Hall A': (50.06, 8.66),
    'Central Boiler': (50.065, 8.665),
    'Storage Tank': (50.07, 8.67),
}

for name, (lat, lon) in buildings.items():
    x, y = geographic_to_canvas(lat, lon, canvas_bounds, geo_bounds)
    # Add component at real position...
```

### 3. Regional Energy System

```python
# Hamburg region
geo_bounds = (53.45, 9.85, 53.65, 10.15)

# Multiple municipalities
cities = [
    ('Hamburg', 53.55, 10.0),
    ('Norderstedt', 53.7, 10.0),
    ('Pinneberg', 53.65, 9.8),
]

for city, lat, lon in cities:
    x, y = geographic_to_canvas(lat, lon, canvas_bounds, geo_bounds)
    # Add city consumer...
```

---

## 🔧 Advanced Configuration

### Custom Component Icons

Extend component styles:

```python
from energis.io.geographic_viewer import COMPONENT_STYLES

# Add custom component type
COMPONENT_STYLES['solar_thermal'] = {
    'icon': 'sun',
    'color': 'yellow',
    'prefix': 'fa',
    'label': 'Solarthermie'
}
```

### Custom Popup HTML

```python
class CustomGeographicViewer(GeographicNetworkViewer):
    def _create_popup_html(self, comp):
        # Custom popup with additional info
        html = f"""
        <div>
            <h3>{comp.component_id}</h3>
            <img src="component_images/{comp.component_type}.png" width="100">
            <p>Capacity: {comp.properties.get('capacity_mw', 'N/A')} MW</p>
            <p>Efficiency: {comp.properties.get('efficiency', 'N/A')}%</p>
        </div>
        """
        return html
```

### Multiple Layers

```python
# Create feature groups for different component types
import folium

m = folium.Map(location=[48.15, 11.6])

producers = folium.FeatureGroup(name='Producers')
consumers = folium.FeatureGroup(name='Consumers')
storage = folium.FeatureGroup(name='Storage')

# Add components to respective layers
for comp in components:
    if comp.component_type in ['heat_pump', 'boiler']:
        # Add to producers layer
        pass
    elif comp.component_type == 'consumer':
        # Add to consumers layer
        pass
    elif comp.component_type == 'storage':
        # Add to storage layer
        pass

producers.add_to(m)
consumers.add_to(m)
storage.add_to(m)

# Add layer control
folium.LayerControl().add_to(m)
```

---

## 🌐 Real-World Coordinates

### Finding Geographic Coordinates

**Option 1: Google Maps**
1. Right-click on location
2. Select "What's here?"
3. Copy coordinates (latitude, longitude)

**Option 2: OpenStreetMap**
1. Navigate to location
2. Right-click on map
3. Select "Show address"
4. Coordinates shown in URL

**Option 3: GIS Software**
- QGIS (free, open-source)
- ArcGIS
- Excel with geocoding plugins

### Coordinate Formats

EnerGIS uses decimal degrees:
```python
# Correct format
lat, lon = 48.137154, 11.576124

# NOT supported (DMS format)
# 48°08'13.8"N, 11°34'34.0"E
```

**Conversion from DMS to Decimal:**
```python
def dms_to_decimal(degrees, minutes, seconds):
    return degrees + minutes/60 + seconds/3600

# Example: 48°08'13.8"N
lat = dms_to_decimal(48, 8, 13.8)  # = 48.137166°
```

---

## 📚 API Reference

### `GeographicNetworkViewer`

```python
class GeographicNetworkViewer:
    def __init__(
        self,
        components: List[NetworkComponent],
        connections: List[NetworkConnection],
        geo_bounds: Tuple[float, float, float, float] = (48.0, 11.4, 48.3, 11.8),
        canvas_bounds: Tuple[float, float, float, float] = (0, 0, 1000, 800)
    ):
        """Initialize geographic viewer."""

    def create_map(
        self,
        center: Tuple[float, float] = None,
        zoom_start: int = 12,
        tiles: str = 'OpenStreetMap'
    ) -> folium.Map:
        """Create interactive Folium map."""

    def save_html(self, output_path: Path):
        """Save map as standalone HTML file."""

    def create_dashboard_panel(self) -> pn.Column:
        """Create Panel dashboard with embedded map."""
```

### Coordinate Conversion Functions

```python
def canvas_to_geographic(
    x: float,
    y: float,
    canvas_bounds: Tuple[float, float, float, float],
    geo_bounds: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Convert canvas (x, y) to (lat, lon)."""

def geographic_to_canvas(
    lat: float,
    lon: float,
    canvas_bounds: Tuple[float, float, float, float],
    geo_bounds: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Convert (lat, lon) to canvas (x, y)."""
```

---

## 🐛 Troubleshooting

### Issue: "ImportError: No module named 'folium'"

**Solution:**
```bash
pip install folium
```

### Issue: Map not displaying in Panel dashboard

**Solution:**
- Ensure Panel extension is loaded: `pn.extension()`
- Check browser console for JavaScript errors
- Try exporting as HTML first to verify map creation

### Issue: Components not at correct locations

**Possible Causes:**
1. Geographic bounds don't match your region
2. Canvas bounds don't match Network Designer canvas

**Solution:**
```python
# Verify bounds
print(f"Canvas bounds: {viewer.canvas_bounds}")
print(f"Geographic bounds: {viewer.geo_bounds}")

# Manually check one component
comp = components[0]
lat, lon = canvas_to_geographic(comp.x, comp.y, canvas_bounds, geo_bounds)
print(f"Component at ({comp.x}, {comp.y}) → ({lat:.4f}, {lon:.4f})")
```

### Issue: Map tiles not loading

**Possible Causes:**
- No internet connection (most tile servers require internet)
- Tile server is down

**Solution:**
- Try different tiles: `tiles='CartoDB positron'`
- Use offline tiles (advanced, requires pre-downloaded tiles)

---

## 📖 Examples

### Complete Example: Munich District Heating

```python
#!/usr/bin/env python3
from pathlib import Path
from energis.io.network_designer import create_network_designer
from energis.io.geographic_viewer import create_geographic_viewer

# Define Munich district heating network
# Geographic bounds: Central Munich
geo_bounds = (48.12, 11.54, 48.16, 11.60)
canvas_bounds = (0, 0, 1000, 800)

# Create network
designer = create_network_designer()

# Add central heat production site
designer.add_component(x=200, y=400, comp_type='boiler')
boiler = designer.components[0]
boiler.status = 'existing'
boiler.properties['capacity_mw'] = 50.0

# Add storage at central site
designer.add_component(x=350, y=400, comp_type='storage')
storage = designer.components[1]
storage.status = 'investment'
storage.properties['capacity_mwh'] = 200.0

# Add consumers in different districts
consumer_locations = [
    (500, 300, 'North District'),
    (700, 400, 'East District'),
    (600, 600, 'South District'),
]

for x, y, name in consumer_locations:
    designer.add_component(x=x, y=y, comp_type='consumer')
    consumer = designer.components[-1]
    consumer.properties['demand_mw'] = 15.0

# Connect network
designer.add_connection(boiler.component_id, storage.component_id)
for comp in designer.components:
    if comp.component_type == 'consumer':
        designer.add_connection(storage.component_id, comp.component_id)

# Create geographic visualization
viewer = create_geographic_viewer(
    components=designer.components,
    connections=designer.connections,
    geo_bounds=geo_bounds
)

# Create and save map
m = viewer.create_map(zoom_start=13)
viewer.save_html(Path('exports/munich_district_heating.html'))

print("✅ Munich district heating network map created")
print("   Open exports/munich_district_heating.html in browser")
```

---

## ✅ Summary

**Geographic Visualization is now fully integrated!**

- ✅ Interactive maps with Folium/Leaflet
- ✅ Automatic coordinate conversion
- ✅ Component popups with details
- ✅ Connection flow visualization
- ✅ Multiple map tile options
- ✅ HTML export for sharing
- ✅ Panel dashboard integration

**Use Cases:**
- 🏙️ District heating network planning
- 🏭 Industrial site layout
- 🌍 Regional energy systems
- 📊 Stakeholder presentations
- 📍 Real-world location mapping

For questions or issues, see:
- `energis/io/geographic_viewer.py` - Implementation
- `examples/geographic_viewer_demo.py` - Demo script
