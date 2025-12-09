"""Extended features for Network Designer.

Adds templates, auto-layout, and enhanced export functionality.
"""

from __future__ import annotations

import io
import base64
from pathlib import Path
from typing import List, Optional

import panel as pn

from energis.io.network_designer import ThermalNetworkDesigner, NetworkComponent, NetworkConnection
from energis.io.network_templates import (
    get_template,
    list_templates,
    optimize_layout,
    snap_to_grid,
)

try:
    import plotly.graph_objects as go
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False


class ThermalNetworkDesignerExtended(ThermalNetworkDesigner):
    """Extended Network Designer with templates and auto-layout."""

    def __init__(self, **params):
        super().__init__(**params)
        self._add_extended_ui()

    def _add_extended_ui(self):
        """Add template and layout UI elements."""

        # Template selector
        templates = list_templates()
        template_options = {t['name']: t['id'] for t in templates}

        self.template_select = pn.widgets.Select(
            name='📋 Template wählen',
            options=['Leer'] + list(template_options.keys()),
            value='Leer',
            width=200,
        )

        self.load_template_button = pn.widgets.Button(
            name='✨ Template laden',
            button_type='success',
            width=150,
        )
        self.load_template_button.on_click(self._load_template)

        # Layout selector
        self.layout_select = pn.widgets.Select(
            name='🎨 Auto-Layout',
            options=['Hierarchisch', 'Grid', 'Circular', 'Force-Directed'],
            value='Hierarchisch',
            width=150,
        )

        self.apply_layout_button = pn.widgets.Button(
            name='🎯 Layout anwenden',
            button_type='primary',
            width=150,
        )
        self.apply_layout_button.on_click(self._apply_layout)

        # Snap to grid button
        self.snap_grid_button = pn.widgets.Button(
            name='⊞ Snap to Grid',
            button_type='default',
            width=150,
        )
        self.snap_grid_button.on_click(self._snap_to_grid)

        # Export options
        self.export_png_button = pn.widgets.Button(
            name='🖼️ PNG exportieren',
            button_type='info',
            width=150,
        )
        self.export_png_button.on_click(self._export_png)

        self.export_svg_button = pn.widgets.Button(
            name='📐 SVG exportieren',
            button_type='info',
            width=150,
        )
        self.export_svg_button.on_click(self._export_svg)

    def _load_template(self, event):
        """Load selected template."""
        selected = self.template_select.value

        if selected == 'Leer':
            return

        # Find template ID
        templates = list_templates()
        template_id = None
        for t in templates:
            if t['name'] == selected:
                template_id = t['id']
                break

        if not template_id:
            print(f"❌ Template nicht gefunden: {selected}")
            return

        # Load template
        try:
            template = get_template(template_id)

            # Clear current network
            self.components = []
            self.connections = []

            # Load components
            for comp_data in template['components']:
                comp = NetworkComponent(
                    component_id=comp_data['id'],
                    component_type=comp_data['type'],
                    x=comp_data['x'],
                    y=comp_data['y'],
                    status=comp_data['status'],
                    properties=comp_data['properties'],
                )
                self.components.append(comp)

            # Load connections
            for conn_data in template['connections']:
                conn = NetworkConnection(
                    from_id=conn_data['from'],
                    to_id=conn_data['to'],
                )
                self.connections.append(conn)

            self._update_canvas()
            print(f"✅ Template geladen: {template['name']}")
            print(f"   {len(self.components)} Komponenten, {len(self.connections)} Verbindungen")

        except Exception as e:
            print(f"❌ Fehler beim Laden: {e}")

    def _apply_layout(self, event):
        """Apply selected auto-layout."""
        if not self.components:
            print("⚠️ Keine Komponenten vorhanden")
            return

        selected = self.layout_select.value
        method_map = {
            'Hierarchisch': 'hierarchical',
            'Grid': 'grid',
            'Circular': 'circular',
            'Force-Directed': 'force',
        }

        method = method_map.get(selected, 'hierarchical')

        try:
            optimize_layout(
                self.components,
                self.connections,
                method=method,
                canvas_width=self.canvas_width,
                canvas_height=self.canvas_height,
            )

            self._update_canvas()
            print(f"✅ Layout angewendet: {selected}")

        except Exception as e:
            print(f"❌ Fehler beim Layout: {e}")

    def _snap_to_grid(self, event):
        """Snap all components to grid."""
        if not self.components:
            print("⚠️ Keine Komponenten vorhanden")
            return

        snap_to_grid(self.components, grid_size=50)
        self._update_canvas()
        print("✅ Komponenten am Raster ausgerichtet")

    def _export_png(self, event):
        """Export network diagram as PNG."""
        if not HAVE_PLOTLY:
            print("❌ Plotly nicht verfügbar")
            return

        try:
            # Get current figure
            fig = self.canvas.object

            # Export to PNG
            output_path = Path('exports/network_diagram.png')
            output_path.parent.mkdir(parents=True, exist_ok=True)

            fig.write_image(str(output_path), width=1200, height=800, scale=2)

            print(f"✅ PNG exportiert: {output_path}")

        except Exception as e:
            print(f"❌ PNG Export fehlgeschlagen: {e}")
            print("   Tipp: pip install kaleido")

    def _export_svg(self, event):
        """Export network diagram as SVG."""
        if not HAVE_PLOTLY:
            print("❌ Plotly nicht verfügbar")
            return

        try:
            # Get current figure
            fig = self.canvas.object

            # Export to SVG
            output_path = Path('exports/network_diagram.svg')
            output_path.parent.mkdir(parents=True, exist_ok=True)

            fig.write_image(str(output_path), format='svg')

            print(f"✅ SVG exportiert: {output_path}")

        except Exception as e:
            print(f"❌ SVG Export fehlgeschlagen: {e}")
            print("   Tipp: pip install kaleido")

    def create_dashboard(self) -> pn.Column:
        """Create complete dashboard layout with extended features."""
        if not HAVE_PLOTLY:
            return pn.Column(
                "# ❌ Error: Plotly not installed",
                "Please install Plotly to use Network Designer:",
                "```bash\npip install plotly\n```",
            )

        # Tool palette row
        tool_palette = pn.Row(
            pn.pane.Markdown("**Werkzeuge:**"),
            *self.tool_buttons.values(),
            sizing_mode='stretch_width',
        )

        # Template and layout row
        template_layout_row = pn.Row(
            self.template_select,
            self.load_template_button,
            pn.layout.HSpacer(),
            self.layout_select,
            self.apply_layout_button,
            self.snap_grid_button,
            sizing_mode='stretch_width',
        )

        # Export row
        export_row = pn.Row(
            *self.action_buttons,
            pn.layout.HSpacer(),
            self.export_png_button,
            self.export_svg_button,
            sizing_mode='stretch_width',
        )

        # Main content: Canvas + Properties
        main_content = pn.Row(
            pn.Column(
                self.canvas,
                self.validation_pane,
                sizing_mode='stretch_both',
            ),
            pn.Column(
                self.properties_panel,
                width=300,
                sizing_mode='stretch_height',
            ),
            sizing_mode='stretch_both',
        )

        # Complete layout
        return pn.Column(
            "# 🗺️ Thermal Network Designer (Extended)",
            template_layout_row,
            tool_palette,
            main_content,
            export_row,
            sizing_mode='stretch_both',
        )


def create_network_designer_extended() -> ThermalNetworkDesignerExtended:
    """Factory function to create extended network designer instance."""
    return ThermalNetworkDesignerExtended()


if __name__ == '__main__':
    # Standalone execution
    import panel as pn
    pn.extension('plotly')

    designer = create_network_designer_extended()
    dashboard = designer.create_dashboard()
    dashboard.servable(title="EnerGIS Network Designer Extended")
