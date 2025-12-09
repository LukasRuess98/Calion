"""Geographic Network Viewer for EnerGIS.

Provides map-based visualization of thermal networks using real geographic coordinates.
Uses Folium (Leaflet) for interactive maps.
"""

from __future__ import annotations

from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

import panel as pn

try:
    import folium
    from folium import plugins
    HAVE_FOLIUM = True
except ImportError:
    HAVE_FOLIUM = False
    folium = None

from .network_designer import NetworkComponent, NetworkConnection


# Component styling for map markers
COMPONENT_STYLES = {
    'heat_pump': {
        'icon': 'fire',
        'color': 'red',
        'prefix': 'fa',
        'label': 'Wärmepumpe'
    },
    'boiler': {
        'icon': 'fire-burner',
        'color': 'orange',
        'prefix': 'fa',
        'label': 'Kessel'
    },
    'chp': {
        'icon': 'bolt',
        'color': 'purple',
        'prefix': 'fa',
        'label': 'BHKW'
    },
    'storage': {
        'icon': 'database',
        'color': 'blue',
        'prefix': 'fa',
        'label': 'Speicher'
    },
    'consumer': {
        'icon': 'home',
        'color': 'green',
        'prefix': 'fa',
        'label': 'Verbraucher'
    },
}


def canvas_to_geographic(
    x: float,
    y: float,
    canvas_bounds: Tuple[float, float, float, float],
    geo_bounds: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Convert canvas coordinates to geographic coordinates.

    Args:
        x: Canvas x coordinate
        y: Canvas y coordinate
        canvas_bounds: (x_min, y_min, x_max, y_max) of canvas
        geo_bounds: (lat_min, lon_min, lat_max, lon_max) geographic bounds

    Returns:
        (latitude, longitude) tuple
    """
    cx_min, cy_min, cx_max, cy_max = canvas_bounds
    lat_min, lon_min, lat_max, lon_max = geo_bounds

    # Normalize canvas coordinates to [0, 1]
    x_norm = (x - cx_min) / (cx_max - cx_min) if cx_max > cx_min else 0.5
    y_norm = (y - cy_min) / (cy_max - cy_min) if cy_max > cy_min else 0.5

    # Map to geographic coordinates
    # Note: Y axis is inverted (canvas y increases downward, latitude increases upward)
    lon = lon_min + x_norm * (lon_max - lon_min)
    lat = lat_max - y_norm * (lat_max - lat_min)

    return lat, lon


def geographic_to_canvas(
    lat: float,
    lon: float,
    canvas_bounds: Tuple[float, float, float, float],
    geo_bounds: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Convert geographic coordinates to canvas coordinates.

    Args:
        lat: Latitude
        lon: Longitude
        canvas_bounds: (x_min, y_min, x_max, y_max) of canvas
        geo_bounds: (lat_min, lon_min, lat_max, lon_max) geographic bounds

    Returns:
        (x, y) canvas coordinates
    """
    cx_min, cy_min, cx_max, cy_max = canvas_bounds
    lat_min, lon_min, lat_max, lon_max = geo_bounds

    # Normalize geographic coordinates
    lon_norm = (lon - lon_min) / (lon_max - lon_min) if lon_max > lon_min else 0.5
    lat_norm = (lat_max - lat) / (lat_max - lat_min) if lat_max > lat_min else 0.5

    # Map to canvas coordinates
    x = cx_min + lon_norm * (cx_max - cx_min)
    y = cy_min + lat_norm * (cy_max - cy_min)

    return x, y


class GeographicNetworkViewer:
    """Geographic visualization of thermal networks on interactive maps."""

    def __init__(
        self,
        components: List[NetworkComponent],
        connections: List[NetworkConnection],
        geo_bounds: Optional[Tuple[float, float, float, float]] = None,
        canvas_bounds: Optional[Tuple[float, float, float, float]] = None,
    ):
        """Initialize geographic viewer.

        Args:
            components: List of network components
            connections: List of network connections
            geo_bounds: (lat_min, lon_min, lat_max, lon_max) - geographic bounds for mapping
                        Default: Munich area (48.0, 11.4, 48.3, 11.8)
            canvas_bounds: (x_min, y_min, x_max, y_max) - canvas coordinate bounds
                           Default: (0, 0, 1000, 800)
        """
        if not HAVE_FOLIUM:
            raise ImportError("Folium is required for geographic visualization. Install: pip install folium")

        self.components = components
        self.connections = connections

        # Default bounds (Munich area)
        self.geo_bounds = geo_bounds or (48.0, 11.4, 48.3, 11.8)
        self.canvas_bounds = canvas_bounds or (0, 0, 1000, 800)

        self._map = None

    def create_map(
        self,
        center: Optional[Tuple[float, float]] = None,
        zoom_start: int = 12,
        tiles: str = 'OpenStreetMap',
    ) -> folium.Map:
        """Create Folium map with network components.

        Args:
            center: (lat, lon) map center. If None, uses center of geo_bounds
            zoom_start: Initial zoom level
            tiles: Map tiles style ('OpenStreetMap', 'CartoDB positron', etc.)

        Returns:
            Folium Map object
        """
        # Calculate center from bounds if not provided
        if center is None:
            lat_min, lon_min, lat_max, lon_max = self.geo_bounds
            center = ((lat_min + lat_max) / 2, (lon_min + lon_max) / 2)

        # Create base map
        m = folium.Map(
            location=center,
            zoom_start=zoom_start,
            tiles=tiles,
        )

        # Add components as markers
        for comp in self.components:
            self._add_component_marker(m, comp)

        # Add connections as lines
        for conn in self.connections:
            self._add_connection_line(m, conn)

        # Add legend
        self._add_legend(m)

        # Add fullscreen button
        plugins.Fullscreen().add_to(m)

        # Add measure control
        plugins.MeasureControl().add_to(m)

        self._map = m
        return m

    def _add_component_marker(self, m: folium.Map, comp: NetworkComponent):
        """Add component as marker on map."""
        # Convert canvas coordinates to geographic
        lat, lon = canvas_to_geographic(
            comp.x, comp.y,
            self.canvas_bounds,
            self.geo_bounds
        )

        # Get component style
        style = COMPONENT_STYLES.get(comp.component_type, {
            'icon': 'question',
            'color': 'gray',
            'prefix': 'fa',
            'label': comp.component_type.title()
        })

        # Create popup content
        popup_html = self._create_popup_html(comp)

        # Determine marker color based on status
        if comp.status == 'existing':
            marker_color = 'darkblue'
        elif comp.status == 'investment':
            marker_color = 'lightred'
        else:
            marker_color = style['color']

        # Create marker
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{style['label']}: {comp.component_id}",
            icon=folium.Icon(
                color=marker_color,
                icon=style['icon'],
                prefix=style['prefix']
            )
        ).add_to(m)

    def _create_popup_html(self, comp: NetworkComponent) -> str:
        """Create HTML content for component popup."""
        style = COMPONENT_STYLES.get(comp.component_type, {})
        label = style.get('label', comp.component_type.title())

        html = f"""
        <div style="font-family: Arial, sans-serif; min-width: 200px;">
            <h4 style="margin: 0 0 10px 0;">{label}</h4>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 3px;"><strong>ID:</strong></td>
                    <td style="padding: 3px;">{comp.component_id}</td>
                </tr>
                <tr>
                    <td style="padding: 3px;"><strong>Status:</strong></td>
                    <td style="padding: 3px;">{comp.status}</td>
                </tr>
        """

        # Add component-specific properties
        if comp.component_type in ['heat_pump', 'boiler', 'chp']:
            capacity = comp.properties.get('capacity_mw', 'N/A')
            html += f"""
                <tr>
                    <td style="padding: 3px;"><strong>Leistung:</strong></td>
                    <td style="padding: 3px;">{capacity} MW</td>
                </tr>
            """

            if comp.component_type == 'heat_pump':
                cop = comp.properties.get('cop', 'N/A')
                html += f"""
                <tr>
                    <td style="padding: 3px;"><strong>COP:</strong></td>
                    <td style="padding: 3px;">{cop}</td>
                </tr>
                """

        elif comp.component_type == 'storage':
            capacity = comp.properties.get('capacity_mwh', 'N/A')
            storage_type = comp.properties.get('storage_type', 'simple')
            html += f"""
                <tr>
                    <td style="padding: 3px;"><strong>Kapazität:</strong></td>
                    <td style="padding: 3px;">{capacity} MWh</td>
                </tr>
                <tr>
                    <td style="padding: 3px;"><strong>Typ:</strong></td>
                    <td style="padding: 3px;">{storage_type}</td>
                </tr>
            """

        elif comp.component_type == 'consumer':
            demand = comp.properties.get('demand_mw', 'N/A')
            html += f"""
                <tr>
                    <td style="padding: 3px;"><strong>Bedarf:</strong></td>
                    <td style="padding: 3px;">{demand} MW</td>
                </tr>
            """

        html += """
            </table>
        </div>
        """

        return html

    def _add_connection_line(self, m: folium.Map, conn: NetworkConnection):
        """Add connection as line on map."""
        # Find source and target components
        source = next((c for c in self.components if c.component_id == conn.from_id), None)
        target = next((c for c in self.components if c.component_id == conn.to_id), None)

        if not source or not target:
            return

        # Convert coordinates
        lat1, lon1 = canvas_to_geographic(source.x, source.y, self.canvas_bounds, self.geo_bounds)
        lat2, lon2 = canvas_to_geographic(target.x, target.y, self.canvas_bounds, self.geo_bounds)

        # Create line
        folium.PolyLine(
            locations=[[lat1, lon1], [lat2, lon2]],
            color='#3388ff',
            weight=3,
            opacity=0.7,
            popup=f"{conn.from_id} → {conn.to_id}"
        ).add_to(m)

        # Add arrow in the middle
        mid_lat = (lat1 + lat2) / 2
        mid_lon = (lon1 + lon2) / 2

        folium.Marker(
            location=[mid_lat, mid_lon],
            icon=folium.DivIcon(html='<div style="font-size: 20px;">→</div>')
        ).add_to(m)

    def _add_legend(self, m: folium.Map):
        """Add legend to map."""
        legend_html = '''
        <div style="position: fixed;
                    bottom: 50px; right: 50px; width: 200px; height: auto;
                    background-color: white; z-index:9999; font-size:14px;
                    border:2px solid grey; padding: 10px;
                    border-radius: 5px;">
            <p style="margin: 0 0 10px 0;"><strong>Legende</strong></p>
            <p style="margin: 5px 0;"><span style="color: darkblue;">●</span> Bestehend</p>
            <p style="margin: 5px 0;"><span style="color: lightcoral;">●</span> Investition</p>
            <hr style="margin: 10px 0;">
            <p style="margin: 5px 0;"><i class="fa fa-fire" style="color: red;"></i> Wärmepumpe</p>
            <p style="margin: 5px 0;"><i class="fa fa-fire-burner" style="color: orange;"></i> Kessel</p>
            <p style="margin: 5px 0;"><i class="fa fa-database" style="color: blue;"></i> Speicher</p>
            <p style="margin: 5px 0;"><i class="fa fa-home" style="color: green;"></i> Verbraucher</p>
        </div>
        '''

        m.get_root().html.add_child(folium.Element(legend_html))

    def save_html(self, output_path: Path):
        """Save map as HTML file.

        Args:
            output_path: Path to save HTML file
        """
        if self._map is None:
            self.create_map()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._map.save(str(output_path))

    def create_dashboard_panel(self) -> pn.Column:
        """Create Panel dashboard with embedded map.

        Returns:
            Panel Column with map and controls
        """
        if self._map is None:
            self.create_map()

        # Save to temp HTML
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            self._map.save(f.name)
            html_path = f.name

        # Create HTML pane
        map_pane = pn.pane.HTML(
            open(html_path).read(),
            height=600,
            sizing_mode='stretch_width'
        )

        # Create controls
        info_md = pn.pane.Markdown(f"""
        ## 🗺️ Geografische Netzwerk-Ansicht

        **Komponenten:** {len(self.components)}
        **Verbindungen:** {len(self.connections)}

        **Koordinaten-Bereich:**
        - Breitengrad: {self.geo_bounds[0]:.4f} - {self.geo_bounds[2]:.4f}
        - Längengrad: {self.geo_bounds[1]:.4f} - {self.geo_bounds[3]:.4f}

        **Funktionen:**
        - 🖱️ Klicken Sie auf Marker für Details
        - 📏 Nutzen Sie das Messwerkzeug
        - 🔍 Zoom und Navigation mit Maus
        """)

        export_button = pn.widgets.Button(name='🗺️ Karte exportieren (HTML)', button_type='primary')

        def export_map(event):
            output_path = Path('exports/network_map.html')
            self.save_html(output_path)
            print(f"✅ Karte exportiert: {output_path}")

        export_button.on_click(export_map)

        return pn.Column(
            info_md,
            map_pane,
            export_button,
            sizing_mode='stretch_width'
        )


def create_geographic_viewer(
    components: List[NetworkComponent],
    connections: List[NetworkConnection],
    geo_bounds: Optional[Tuple[float, float, float, float]] = None,
) -> GeographicNetworkViewer:
    """Factory function to create geographic viewer.

    Args:
        components: List of network components
        connections: List of network connections
        geo_bounds: Geographic bounds (lat_min, lon_min, lat_max, lon_max)

    Returns:
        GeographicNetworkViewer instance
    """
    return GeographicNetworkViewer(
        components=components,
        connections=connections,
        geo_bounds=geo_bounds
    )


if __name__ == '__main__':
    # Demo: Create example network and visualize on map
    print("Geographic Network Viewer Demo")
    print("="*70)

    from .network_designer import create_network_designer

    # Create example network
    designer = create_network_designer()
    designer.add_component(x=200, y=200, comp_type='heat_pump')
    designer.add_component(x=500, y=200, comp_type='storage')
    designer.add_component(x=800, y=200, comp_type='consumer')

    hp = designer.components[0]
    hp.properties['capacity_mw'] = 10.0
    hp.status = 'existing'

    storage = designer.components[1]
    storage.properties['capacity_mwh'] = 50.0
    storage.status = 'investment'

    designer.add_connection(hp.component_id, storage.component_id)
    designer.add_connection(storage.component_id, designer.components[2].component_id)

    # Create geographic viewer
    viewer = create_geographic_viewer(
        components=designer.components,
        connections=designer.connections,
        geo_bounds=(48.0, 11.4, 48.3, 11.8)  # Munich area
    )

    # Create map
    m = viewer.create_map()

    # Save
    output_path = Path('exports/demo_network_map.html')
    viewer.save_html(output_path)

    print(f"✅ Map created and saved to: {output_path}")
    print("   Open in browser to view interactive map")
