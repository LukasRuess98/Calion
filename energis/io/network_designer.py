"""Interactive Network Designer Dashboard with Coordinate System.

This module provides a visual, coordinate-based interface for designing
thermal network scenarios with drag-and-drop component placement.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import panel as pn
import param
import yaml

logger = logging.getLogger(__name__)

# Try importing plotting libraries
try:
    import plotly.graph_objects as go
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False
    go = None

try:
    import pandas as pd
    HAVE_PANDAS = True
except ImportError:
    HAVE_PANDAS = False
    pd = None


# Component type definitions
COMPONENT_TYPES = {
    'heat_pump': {
        'icon': '🔥',
        'label': 'Wärmepumpe',
        'color': '#FF6B6B',
        'default_props': {
            'cop': 3.5,
            'capacity_mw': 10.0,
        }
    },
    'boiler': {
        'icon': '⚡',
        'label': 'Kessel',
        'color': '#FFA500',
        'default_props': {
            'efficiency': 0.95,
            'capacity_mw': 15.0,
        }
    },
    'storage': {
        'icon': '🔋',
        'label': 'Speicher',
        'color': '#4ECDC4',
        'default_props': {
            'capacity_mwh': 50.0,
            'efficiency': 0.98,
        }
    },
    'consumer': {
        'icon': '🏠',
        'label': 'Verbraucher',
        'color': '#95E1D3',
        'default_props': {
            'demand_mw': 25.0,
        }
    },
    'node': {
        'icon': '⊕',
        'label': 'Knoten',
        'color': '#CCCCCC',
        'default_props': {}
    },
}

STATUS_COLORS = {
    'existing': '#4CAF50',  # Green - Bestand
    'investment': '#2196F3',  # Blue - Investition
    'pending': '#FFC107',  # Yellow - Noch nicht konfiguriert
    'error': '#F44336',  # Red - Fehler
}


class NetworkComponent(param.Parameterized):
    """Represents a single component in the thermal network."""

    component_id = param.String(default='')
    component_type = param.String(default='heat_pump')
    x = param.Number(default=0.0)
    y = param.Number(default=0.0)
    status = param.Selector(default='pending', objects=['pending', 'existing', 'investment', 'error'])
    properties = param.Dict(default={})
    validation_errors = param.List(default=[])

    def __init__(self, **params):
        super().__init__(**params)
        if not self.component_id:
            self.component_id = self._generate_id()
        if not self.properties:
            self.properties = COMPONENT_TYPES[self.component_type]['default_props'].copy()

    def _generate_id(self) -> str:
        """Generate unique component ID."""
        type_prefix = self.component_type[:3].upper()
        return f"{type_prefix}_{uuid.uuid4().hex[:8]}"

    def validate(self) -> List[str]:
        """Validate component configuration."""
        errors = []

        # Type-specific validation
        if self.component_type in ['heat_pump', 'boiler']:
            capacity = self.properties.get('capacity_mw', 0)
            if capacity <= 0:
                errors.append(f"❌ {self.component_id}: Leistung muss > 0 sein")

        elif self.component_type == 'storage':
            capacity = self.properties.get('capacity_mwh', 0)
            if capacity <= 0:
                errors.append(f"❌ {self.component_id}: Speicherkapazität muss > 0 sein")

        # Status validation
        if self.status == 'existing':
            if self.component_type in ['heat_pump', 'boiler']:
                if 'capacity_mw' not in self.properties:
                    errors.append(f"❌ {self.component_id}: Bestandsanlagen brauchen feste Leistung")

        self.validation_errors = errors
        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Export component as dictionary."""
        return {
            'id': self.component_id,
            'type': self.component_type,
            'x': self.x,
            'y': self.y,
            'status': self.status,
            'properties': self.properties,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkComponent':
        """Create component from dictionary."""
        return cls(
            component_id=data['id'],
            component_type=data['type'],
            x=data['x'],
            y=data['y'],
            status=data.get('status', 'pending'),
            properties=data.get('properties', {}),
        )


class NetworkConnection(param.Parameterized):
    """Represents a connection (pipe) between components."""

    connection_id = param.String(default='')
    from_id = param.String(default='')
    to_id = param.String(default='')
    connection_type = param.String(default='pipe')
    properties = param.Dict(default={})

    def __init__(self, **params):
        super().__init__(**params)
        if not self.connection_id:
            self.connection_id = f"CONN_{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        """Export connection as dictionary."""
        return {
            'id': self.connection_id,
            'from': self.from_id,
            'to': self.to_id,
            'type': self.connection_type,
            'properties': self.properties,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkConnection':
        """Create connection from dictionary."""
        return cls(
            connection_id=data.get('id', ''),
            from_id=data['from'],
            to_id=data['to'],
            connection_type=data.get('type', 'pipe'),
            properties=data.get('properties', {}),
        )


class ThermalNetworkDesigner(param.Parameterized):
    """Main dashboard class for visual network design."""

    # State
    components = param.List(default=[], item_type=NetworkComponent)
    connections = param.List(default=[], item_type=NetworkConnection)
    selected_component = param.Parameter(default=None)
    selected_tool = param.String(default='select')
    validation_status = param.String(default='')

    # UI Elements
    canvas_width = param.Integer(default=800)
    canvas_height = param.Integer(default=600)

    def __init__(self, **params):
        super().__init__(**params)
        self._setup_ui()

    def _setup_ui(self):
        """Setup Panel UI components."""
        if not HAVE_PLOTLY:
            logger.error("Plotly not available. Install with: pip install plotly")
            return

        # Tool palette
        self.tool_buttons = {
            'select': pn.widgets.Button(name='👆 Auswählen', button_type='primary', width=120),
            'heat_pump': pn.widgets.Button(name='🔥 Wärmepumpe', button_type='default', width=120),
            'boiler': pn.widgets.Button(name='⚡ Kessel', button_type='default', width=120),
            'storage': pn.widgets.Button(name='🔋 Speicher', button_type='default', width=120),
            'consumer': pn.widgets.Button(name='🏠 Verbraucher', button_type='default', width=120),
            'connect': pn.widgets.Button(name='─ Verbinden', button_type='default', width=120),
            'delete': pn.widgets.Button(name='🗑️ Löschen', button_type='danger', width=120),
        }

        # Wire button callbacks
        for tool, button in self.tool_buttons.items():
            button.on_click(lambda event, t=tool: self.select_tool(t))

        # Canvas (Plotly figure)
        self.canvas = pn.pane.Plotly(
            self._create_empty_canvas(),
            config={'displayModeBar': True, 'displaylogo': False},
            sizing_mode='stretch_both',
        )

        # Properties panel (will be updated dynamically)
        self.properties_panel = pn.Column(
            "### Eigenschaften",
            pn.pane.Markdown("_Keine Komponente ausgewählt_"),
            sizing_mode='stretch_width',
        )

        # Connection state for connect tool
        self.connection_start_id = None

        # Action buttons
        self.action_buttons = pn.Row(
            pn.widgets.Button(name='💾 YAML exportieren', button_type='success', width=150),
            pn.widgets.Button(name='📂 YAML importieren', button_type='primary', width=150),
            pn.widgets.Button(name='▶ Simulation starten', button_type='primary', width=150),
            pn.widgets.Button(name='🔄 Zurücksetzen', button_type='warning', width=150),
        )

        # Wire action callbacks
        self.action_buttons[0].on_click(self._export_yaml)
        self.action_buttons[1].on_click(self._import_yaml)
        self.action_buttons[2].on_click(self._run_simulation)
        self.action_buttons[3].on_click(self._reset_canvas)

        # Validation status
        self.validation_pane = pn.pane.Markdown("", sizing_mode='stretch_width')

    def _create_empty_canvas(self) -> go.Figure:
        """Create empty Plotly canvas."""
        fig = go.Figure()

        # Set up grid background
        fig.update_layout(
            title="🗺️ Thermisches Netzwerk Designer",
            xaxis=dict(
                title="X-Koordinate (m)",
                range=[0, 1000],
                showgrid=True,
                gridcolor='lightgray',
                zeroline=True,
            ),
            yaxis=dict(
                title="Y-Koordinate (m)",
                range=[0, 800],
                showgrid=True,
                gridcolor='lightgray',
                zeroline=True,
            ),
            width=self.canvas_width,
            height=self.canvas_height,
            hovermode='closest',
            plot_bgcolor='white',
            dragmode='pan',
        )

        return fig

    def _update_canvas(self):
        """Redraw canvas with all components and connections."""
        fig = self._create_empty_canvas()

        # Draw connections first (so they appear behind components)
        for conn in self.connections:
            from_comp = self._get_component_by_id(conn.from_id)
            to_comp = self._get_component_by_id(conn.to_id)

            if from_comp and to_comp:
                fig.add_trace(go.Scatter(
                    x=[from_comp.x, to_comp.x],
                    y=[from_comp.y, to_comp.y],
                    mode='lines',
                    line=dict(color='gray', width=2),
                    hoverinfo='skip',
                    showlegend=False,
                ))

        # Draw components
        for comp in self.components:
            comp_type = COMPONENT_TYPES.get(comp.component_type, {})
            color = STATUS_COLORS.get(comp.status, '#CCCCCC')

            # Validate to update status
            errors = comp.validate()
            if errors:
                color = STATUS_COLORS['error']

            # Icon + label
            icon = comp_type.get('icon', '●')
            label = f"{icon} {comp.component_id}"

            fig.add_trace(go.Scatter(
                x=[comp.x],
                y=[comp.y],
                mode='markers+text',
                marker=dict(size=20, color=color, line=dict(color='black', width=2)),
                text=label,
                textposition='top center',
                hoverinfo='text',
                hovertext=self._component_hover_text(comp),
                showlegend=False,
                customdata=[comp.component_id],
            ))

        # Update canvas
        self.canvas.object = fig

    def _component_hover_text(self, comp: NetworkComponent) -> str:
        """Generate hover text for component."""
        lines = [
            f"<b>{comp.component_id}</b>",
            f"Typ: {COMPONENT_TYPES[comp.component_type]['label']}",
            f"Status: {comp.status}",
            f"Position: ({comp.x:.0f}, {comp.y:.0f})",
        ]

        # Add properties
        for key, value in comp.properties.items():
            lines.append(f"{key}: {value}")

        # Add validation errors
        if comp.validation_errors:
            lines.append("<br><b style='color:red;'>Fehler:</b>")
            lines.extend([f"• {err}" for err in comp.validation_errors])

        return "<br>".join(lines)

    def _get_component_by_id(self, component_id: str) -> Optional[NetworkComponent]:
        """Find component by ID."""
        for comp in self.components:
            if comp.component_id == component_id:
                return comp
        return None

    def select_tool(self, tool: str):
        """Select active tool."""
        self.selected_tool = tool

        # Update button styles
        for t, button in self.tool_buttons.items():
            if t == tool:
                button.button_type = 'primary'
            else:
                button.button_type = 'default'

        # Reset connection state when switching tools
        if tool != 'connect':
            self.connection_start_id = None

        logger.info(f"Tool selected: {tool}")

    def handle_canvas_click(self, x: float, y: float, clicked_id: Optional[str] = None):
        """Handle click events on canvas."""
        if self.selected_tool == 'select':
            if clicked_id:
                self.select_component(clicked_id)
            else:
                self.selected_component = None
                self._update_properties_panel()

        elif self.selected_tool in ['heat_pump', 'boiler', 'storage', 'consumer', 'node']:
            # Place new component
            self.add_component(x, y, self.selected_tool)

        elif self.selected_tool == 'connect':
            if clicked_id:
                self._handle_connect_click(clicked_id)

        elif self.selected_tool == 'delete':
            if clicked_id:
                self.delete_component(clicked_id)

    def _handle_connect_click(self, component_id: str):
        """Handle clicks in connect mode."""
        if self.connection_start_id is None:
            # First click - start connection
            self.connection_start_id = component_id
            logger.info(f"Connection started from: {component_id}")
        else:
            # Second click - complete connection
            if self.connection_start_id != component_id:
                self.add_connection(self.connection_start_id, component_id)
            self.connection_start_id = None

    def select_component(self, component_id: str):
        """Select component and update properties panel."""
        comp = self._get_component_by_id(component_id)
        if comp:
            self.selected_component = comp
            self._update_properties_panel()
            logger.info(f"Selected component: {component_id}")

    def _update_properties_panel(self):
        """Update properties panel based on selected component."""
        if self.selected_component is None:
            self.properties_panel.objects = [
                "### Eigenschaften",
                pn.pane.Markdown("_Keine Komponente ausgewählt_"),
            ]
            return

        comp = self.selected_component
        comp_type_info = COMPONENT_TYPES.get(comp.component_type, {})

        # Component header
        header = pn.pane.Markdown(
            f"### {comp_type_info.get('icon', '●')} {comp.component_id}"
        )

        # Basic info
        info = pn.pane.Markdown(
            f"**Typ:** {comp_type_info.get('label', comp.component_type)}  \n"
            f"**Position:** ({comp.x:.0f}, {comp.y:.0f})"
        )

        # Status selector
        status_selector = pn.widgets.RadioButtonGroup(
            name='Status',
            options=['Bestand', 'Investition'],
            value='Bestand' if comp.status == 'existing' else 'Investition',
            button_type='success' if comp.status == 'existing' else 'primary',
        )

        def update_status(event):
            comp.status = 'existing' if event.new == 'Bestand' else 'investment'
            self._update_canvas()

        status_selector.param.watch(update_status, 'value')

        # Property editors
        property_widgets = []

        if comp.component_type in ['heat_pump', 'boiler']:
            capacity_input = pn.widgets.FloatInput(
                name='Leistung (MW)',
                value=comp.properties.get('capacity_mw', 10.0),
                start=0.0,
                step=1.0,
                width=200,
            )

            def update_capacity(event):
                comp.properties['capacity_mw'] = event.new
                comp.validate()
                self._update_canvas()

            capacity_input.param.watch(update_capacity, 'value')
            property_widgets.append(capacity_input)

            if comp.component_type == 'heat_pump':
                cop_input = pn.widgets.FloatInput(
                    name='COP',
                    value=comp.properties.get('cop', 3.5),
                    start=1.0,
                    step=0.1,
                    width=200,
                )

                def update_cop(event):
                    comp.properties['cop'] = event.new
                    self._update_canvas()

                cop_input.param.watch(update_cop, 'value')
                property_widgets.append(cop_input)

            elif comp.component_type == 'boiler':
                efficiency_input = pn.widgets.FloatInput(
                    name='Wirkungsgrad',
                    value=comp.properties.get('efficiency', 0.95),
                    start=0.0,
                    end=1.0,
                    step=0.01,
                    width=200,
                )

                def update_efficiency(event):
                    comp.properties['efficiency'] = event.new
                    self._update_canvas()

                efficiency_input.param.watch(update_efficiency, 'value')
                property_widgets.append(efficiency_input)

        elif comp.component_type == 'storage':
            # Storage type selector
            storage_type_select = pn.widgets.Select(
                name='Speicher-Typ',
                options=['simple', 'stratified'],
                value=comp.properties.get('storage_type', 'simple'),
                width=200,
            )

            def update_storage_type(event):
                comp.properties['storage_type'] = event.new
                self._update_canvas()

            storage_type_select.param.watch(update_storage_type, 'value')
            property_widgets.append(storage_type_select)

            # Type info
            type_info = {
                'simple': '⚡ Einfacher Speicher (single-zone)',
                'stratified': '🌡️ Geschichteter Speicher (2-zone thermocline)'
            }
            type_desc = pn.pane.Markdown(
                f"_{type_info.get(storage_type_select.value, '')}_",
                width=200,
                styles={'font-size': '0.9em', 'color': '#666'}
            )
            property_widgets.append(type_desc)

            capacity_input = pn.widgets.FloatInput(
                name='Kapazität (MWh)',
                value=comp.properties.get('capacity_mwh', 50.0),
                start=0.0,
                step=5.0,
                width=200,
            )

            def update_storage_capacity(event):
                comp.properties['capacity_mwh'] = event.new
                comp.validate()
                self._update_canvas()

            capacity_input.param.watch(update_storage_capacity, 'value')
            property_widgets.append(capacity_input)

            efficiency_input = pn.widgets.FloatInput(
                name='Wirkungsgrad',
                value=comp.properties.get('efficiency', 0.98),
                start=0.0,
                end=1.0,
                step=0.01,
                width=200,
            )

            def update_storage_efficiency(event):
                comp.properties['efficiency'] = event.new
                self._update_canvas()

            efficiency_input.param.watch(update_storage_efficiency, 'value')
            property_widgets.append(efficiency_input)

            # Show additional parameters for stratified storage
            if comp.properties.get('storage_type', 'simple') == 'stratified':
                stratified_params = pn.pane.Markdown(
                    """**Geschichteter Speicher Parameter:**
                    - Heiße Zone: 90°C (oben)
                    - Kalte Zone: 40°C (unten)
                    - Geometrie: Automatisch berechnet
                    - Verluste: Geometrie-basiert""",
                    width=200,
                    styles={'font-size': '0.85em', 'background': '#f0f8ff', 'padding': '10px', 'border-radius': '5px'}
                )
                property_widgets.append(stratified_params)

        elif comp.component_type == 'consumer':
            demand_input = pn.widgets.FloatInput(
                name='Wärmebedarf (MW)',
                value=comp.properties.get('demand_mw', 25.0),
                start=0.0,
                step=1.0,
                width=200,
            )

            def update_demand(event):
                comp.properties['demand_mw'] = event.new
                self._update_canvas()

            demand_input.param.watch(update_demand, 'value')
            property_widgets.append(demand_input)

        # Validation status
        errors = comp.validate()
        if errors:
            validation_md = pn.pane.Markdown(
                "**Validierung:**\n\n" + "\n".join([f"- {err}" for err in errors]),
                styles={'color': 'red'},
            )
        else:
            validation_md = pn.pane.Markdown(
                "✅ **Validierung:** OK",
                styles={'color': 'green'},
            )

        # Delete button
        delete_button = pn.widgets.Button(
            name='🗑️ Komponente löschen',
            button_type='danger',
            width=200,
        )

        def delete_handler(event):
            self.delete_component(comp.component_id)
            self.selected_component = None
            self._update_properties_panel()

        delete_button.on_click(delete_handler)

        # Update panel
        self.properties_panel.objects = [
            header,
            info,
            "---",
            status_selector,
            "---",
            "**Eigenschaften:**",
            *property_widgets,
            "---",
            validation_md,
            "---",
            delete_button,
        ]

    def add_component(self, x: float, y: float, comp_type: str):
        """Add component at coordinates."""
        comp = NetworkComponent(
            component_type=comp_type,
            x=x,
            y=y,
            status='pending',
        )
        self.components.append(comp)
        self._update_canvas()
        logger.info(f"Added component: {comp.component_id} at ({x}, {y})")

    def add_connection(self, from_id: str, to_id: str):
        """Add connection between components."""
        conn = NetworkConnection(
            from_id=from_id,
            to_id=to_id,
        )
        self.connections.append(conn)
        self._update_canvas()
        logger.info(f"Added connection: {from_id} -> {to_id}")

    def delete_component(self, component_id: str):
        """Delete component and all connected connections."""
        # Remove component
        self.components = [c for c in self.components if c.component_id != component_id]

        # Remove connections
        self.connections = [
            c for c in self.connections
            if c.from_id != component_id and c.to_id != component_id
        ]

        self._update_canvas()
        logger.info(f"Deleted component: {component_id}")

    def validate_network(self) -> Tuple[bool, List[str]]:
        """Validate entire network."""
        all_errors = []

        # Validate components
        for comp in self.components:
            errors = comp.validate()
            all_errors.extend(errors)

        # Validate topology
        isolated = self._find_isolated_components()
        if isolated:
            all_errors.append(f"⚠️ Isolierte Komponenten: {', '.join(isolated)}")

        # Update validation status
        if all_errors:
            self.validation_status = "❌ **Validierung fehlgeschlagen:**\n" + "\n".join(all_errors)
            self.validation_pane.object = self.validation_status
            return False, all_errors
        else:
            self.validation_status = "✅ **Validierung erfolgreich** - Alle Komponenten korrekt konfiguriert"
            self.validation_pane.object = self.validation_status
            return True, []

    def _find_isolated_components(self) -> List[str]:
        """Find components with no connections."""
        if not self.components:
            return []

        connected_ids = set()
        for conn in self.connections:
            connected_ids.add(conn.from_id)
            connected_ids.add(conn.to_id)

        isolated = [
            comp.component_id for comp in self.components
            if comp.component_id not in connected_ids and comp.component_type != 'node'
        ]

        return isolated

    def export_to_yaml(self, output_path: str | Path) -> Dict[str, Any]:
        """Export network to YAML configuration.

        Exports in format compatible with system_builder.py and rolling_horizon.py.
        Creates a complete, self-contained configuration with sensible defaults.
        """
        # Generate system config in format expected by system_builder
        system_config = self._generate_system_config()

        # Complete config structure with all required sections
        config = {
            # Metadata (for Network Designer only)
            '_network_designer': {
                'version': '1.0',
                'created': 'Network Designer',
                'components': [comp.to_dict() for comp in self.components],
                'connections': [conn.to_dict() for conn in self.connections],
            },

            # Run configuration
            'run': {
                'dt_h': 1.0,
                'solver': 'gurobi',
                'solver_options': {
                    'MIPGap': 0.02,
                    'TimeLimit': 3600,
                    'Threads': 0,
                },
            },

            # Cost parameters
            'costs': {
                'include_gridcost_in_energy': True,
                'include_demand_charge_in_rh': True,
                'include_co2_cost_in_objective': True,
                'co2_price_eur_per_t': 100.0,
                'dump_cost_eur_per_mwh_th': 1.0,
            },

            # Grid parameters
            'grid': {
                'energy_fee_eur_mwh': 0.0,
                'demand_charge_eur_per_mw_y': 120000.0,
                'gridcost_eur_mwh': 0.0,
                'year_fraction': 1.0,
                'big_m_grid_mw': 200.0,
                'max_import_mw': 200.0,
                'max_export_mw': 100.0,
            },

            # Fuel prices (defaults)
            'fuels': {
                'gas': {
                    'price_eur_mwh': 50.0,
                    'ef_kg_per_mwh_fuel': 200.0,
                },
                'biomass': {
                    'price_eur_mwh': 40.0,
                    'ef_kg_per_mwh_fuel': 0.0,
                },
            },

            # Heat pump configuration
            'heat_pumps': {
                'cop': {
                    'cop_fallback': 3.5,
                    'T_feed_K': 353.15,  # 80°C
                    'dT_pinch_K': 5.0,
                },
                'types': {
                    'standard': {
                        'COPdefault': 3.5,
                    },
                },
            },

            # Storage configuration defaults
            'storage': {
                'eff_charge': 0.98,
                'eff_discharge': 0.98,
                'loss_hour': 0.9999,
            },

            # Scenario metadata
            'scenario': {
                'name': 'network_designer_scenario',
                'description': 'Created with Network Designer',
                'run_mode': 'PF_ONLY',  # Default to Perfect Forecast
            },

            # System configuration (required by system_builder.py)
            'system': system_config,
        }

        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"✅ Exported network to {output_path}")
        return config

    def _generate_system_config(self) -> Dict[str, Any]:
        """Generate system configuration compatible with system_builder.py.

        Creates config structure matching baseline.system.yaml format:
        - system.heat_pumps: list of heat pump definitions
        - system.storage: single storage config with enabled flag
        - system.generators: dict of generator configs (for boilers)
        """
        system_config = {}

        # Extract heat pumps
        heat_pumps = [comp for comp in self.components if comp.component_type == 'heat_pump']
        if heat_pumps:
            # Add heat pump defaults
            system_config['heat_pump_defaults'] = {
                'enabled': True,
                'type': 'standard',
                'max_th_mw': 100.0,
                'min_th_mw': 0.0,
            }

            # Check if any heat pump is investment (not existing)
            has_investment = any(comp.status != 'existing' for comp in heat_pumps)
            if has_investment:
                system_config['heat_pump_defaults']['investment'] = {
                    'enabled': True,
                    'capacity_min_mw': 1.0,
                    'capacity_max_mw': 100.0,
                }

            # Add individual heat pumps
            system_config['heat_pumps'] = []
            for comp in heat_pumps:
                hp_config = {
                    'id': comp.component_id,
                }

                # Add capacity if existing
                if comp.status == 'existing':
                    capacity = comp.properties.get('capacity_mw', 10.0)
                    hp_config['max_th_mw'] = capacity
                    hp_config['min_th_mw'] = 0.0

                # Add COP if specified
                if 'cop' in comp.properties:
                    hp_config['cop_override'] = comp.properties['cop']

                # Add coordinates (for future use)
                hp_config['_x'] = comp.x
                hp_config['_y'] = comp.y

                system_config['heat_pumps'].append(hp_config)

        # Extract storage
        storage_comps = [comp for comp in self.components if comp.component_type == 'storage']
        if storage_comps:
            # For now, support only single storage
            # TODO: Multiple storage support in future
            storage_comp = storage_comps[0]

            storage_config = {
                'enabled': True,
                'type': storage_comp.properties.get('storage_type', 'simple'),  # 'simple' or 'stratified'
                'soc0_mwh': 0.0,
                'eff_charge': storage_comp.properties.get('efficiency', 0.98),
                'eff_discharge': storage_comp.properties.get('efficiency', 0.98),
                'loss_hour': 0.9999,  # Default: minimal losses
                '_x': storage_comp.x,
                '_y': storage_comp.y,
            }

            # Add stratified-specific parameters if needed
            if storage_config['type'] == 'stratified':
                storage_config.update({
                    'T_hot_C': 90.0,
                    'T_cold_C': 40.0,
                    'T_ambient_C': 15.0,
                    'T_ground_C': 10.0,
                    'aspect_ratio': 1.5,
                    'geometry_type': 'tank',
                    'U_top': 0.3,
                    'U_side': 0.2,
                    'U_bottom': 0.15,
                    'V_hot_init_fraction': 0.5,
                })

            if storage_comp.status == 'existing':
                # Fixed capacity
                capacity = storage_comp.properties.get('capacity_mwh', 50.0)
                storage_config['min_energy_mwh'] = capacity
                storage_config['max_energy_mwh'] = capacity
                storage_config['max_power_mw'] = capacity * 0.5  # Default: 2h discharge
                storage_config['investment'] = {'enabled': False}
            else:
                # Investment
                capacity = storage_comp.properties.get('capacity_mwh', 50.0)
                storage_config['min_energy_mwh'] = 0.0
                storage_config['max_energy_mwh'] = capacity * 2  # Allow optimization up to 2x
                storage_config['max_power_mw'] = capacity
                storage_config['investment'] = {
                    'enabled': True,
                    'energy_capacity_min_mwh': 10.0,
                    'energy_capacity_max_mwh': capacity * 2,
                    'power_capacity_min_mw': 5.0,
                    'power_capacity_max_mw': capacity,
                }

            system_config['storage'] = storage_config

            if len(storage_comps) > 1:
                logger.warning(
                    f"Multiple storage components found ({len(storage_comps)}). "
                    f"Only first storage '{storage_comp.component_id}' will be used. "
                    f"Multiple storage support coming in future version."
                )

        # Extract boilers and map to generators
        boilers = [comp for comp in self.components if comp.component_type == 'boiler']
        if boilers:
            system_config['generators'] = {}

            for comp in boilers:
                capacity = comp.properties.get('capacity_mw', 15.0)
                efficiency = comp.properties.get('efficiency', 0.95)

                # Map to generic generator (HKW = Heizkraftwerk)
                gen_id = comp.component_id.lower().replace('boi_', 'hkw_')

                system_config['generators'][gen_id] = {
                    'enabled': True,
                    'cap_th_mw': capacity,
                    'efficiency': efficiency,
                    '_x': comp.x,
                    '_y': comp.y,
                    '_original_id': comp.component_id,
                }

        # Consumers are handled via demand time series, not in system config
        # Store consumer info in metadata for reference
        consumers = [comp for comp in self.components if comp.component_type == 'consumer']
        if consumers:
            system_config['_consumers'] = [
                {
                    'id': comp.component_id,
                    'x': comp.x,
                    'y': comp.y,
                    **comp.properties,
                }
                for comp in consumers
            ]

        return system_config

    def import_from_yaml(self, yaml_path: str | Path):
        """Import network from YAML configuration.

        Supports two formats:
        1. Network Designer format (with _network_designer metadata)
        2. Standard system config (converts to components)
        """
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        # Check if this is a Network Designer export
        if '_network_designer' in config:
            # Import from Network Designer format
            network = config['_network_designer']

            # Import components
            self.components = []
            for comp_data in network.get('components', []):
                comp = NetworkComponent.from_dict(comp_data)
                self.components.append(comp)

            # Import connections
            self.connections = []
            for conn_data in network.get('connections', []):
                conn = NetworkConnection.from_dict(conn_data)
                self.connections.append(conn)

        else:
            # Import from standard system config
            self._import_from_system_config(config)

        self._update_canvas()
        logger.info(f"✅ Imported network from {yaml_path}")

    def _import_from_system_config(self, config: Dict[str, Any]):
        """Import components from standard system config format."""
        self.components = []
        self.connections = []

        system = config.get('system', {})

        # Import heat pumps
        heat_pumps = system.get('heat_pumps', [])
        for i, hp in enumerate(heat_pumps):
            comp = NetworkComponent(
                component_id=hp.get('id', f'HP{i+1}'),
                component_type='heat_pump',
                x=hp.get('_x', 100 + i * 150),  # Auto-position if no coords
                y=hp.get('_y', 300),
                status='existing' if hp.get('max_th_mw') else 'investment',
                properties={
                    'capacity_mw': hp.get('max_th_mw', 10.0),
                    'cop': hp.get('cop_override', 3.5),
                }
            )
            self.components.append(comp)

        # Import storage
        storage = system.get('storage', {})
        if storage.get('enabled'):
            capacity = storage.get('max_energy_mwh', 50.0)
            is_investment = storage.get('investment', {}).get('enabled', False)

            comp = NetworkComponent(
                component_id='STORAGE1',
                component_type='storage',
                x=storage.get('_x', 400),
                y=storage.get('_y', 300),
                status='investment' if is_investment else 'existing',
                properties={
                    'capacity_mwh': capacity,
                    'efficiency': storage.get('eff_charge', 0.98),
                }
            )
            self.components.append(comp)

        # Import generators (boilers)
        generators = system.get('generators', {})
        for i, (gen_id, gen_cfg) in enumerate(generators.items()):
            if gen_cfg.get('enabled'):
                comp = NetworkComponent(
                    component_id=gen_cfg.get('_original_id', gen_id.upper()),
                    component_type='boiler',
                    x=gen_cfg.get('_x', 100 + i * 150),
                    y=gen_cfg.get('_y', 500),
                    status='existing',
                    properties={
                        'capacity_mw': gen_cfg.get('cap_th_mw', 15.0),
                        'efficiency': gen_cfg.get('efficiency', 0.95),
                    }
                )
                self.components.append(comp)

        logger.info(f"Imported {len(self.components)} components from system config")

    def _export_yaml(self, event):
        """Callback for export button."""
        output_path = Path('exports/network_designer_export.yaml')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.export_to_yaml(output_path)
        print(f"✅ Exported to {output_path}")

    def _import_yaml(self, event):
        """Callback for import button."""
        # TODO: Add file selector dialog
        print("⚠️ Import: Please implement file selector")

    def _run_simulation(self, event):
        """Callback for simulation button."""
        valid, errors = self.validate_network()
        if not valid:
            print("❌ Cannot run simulation - validation errors:")
            for err in errors:
                print(f"  {err}")
            return

        print("▶ Starting simulation...")

        # Create temporary YAML config
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_path = Path(f.name)
            self.export_to_yaml(config_path)

        print(f"  Created config: {config_path}")

        try:
            # Import runner
            from energis.run.rolling_horizon import run_workflow

            # Run workflow
            print("  Running workflow...")
            result = run_workflow([str(config_path)])

            print("✅ Simulation completed successfully!")

            # Show results viewer
            self._show_results(result)

        except Exception as e:
            print(f"❌ Simulation failed: {e}")
            logger.exception("Simulation error")
        finally:
            # Cleanup temp file
            if config_path.exists():
                config_path.unlink()

    def _show_results(self, workflow_result):
        """Show results in new window/tab."""
        from energis.io.network_results_viewer import create_results_viewer

        # Create results viewer
        viewer = create_results_viewer(
            workflow_result=workflow_result,
            components=self.components,
            connections=self.connections,
        )

        # Display in new tab
        results_layout = viewer.create_viewer()

        # Create new window
        print("\n" + "="*60)
        print("📊 Ergebnisse werden angezeigt...")
        print("="*60)

        # Open in popup or new tab
        pn.state.notifications.success("Simulation erfolgreich abgeschlossen!", duration=5000)

        # TODO: Open results in separate browser tab
        # For now, we integrate it into the main dashboard
        self._results_viewer = viewer
        print("✅ Ergebnisse verfügbar - siehe Results Tab")

    def _reset_canvas(self, event):
        """Callback for reset button."""
        self.components = []
        self.connections = []
        self.selected_component = None
        self._update_canvas()
        print("🔄 Canvas reset")

    def create_dashboard(self) -> pn.Column:
        """Create complete dashboard layout."""
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
            "# 🗺️ Thermal Network Designer",
            tool_palette,
            main_content,
            self.action_buttons,
            sizing_mode='stretch_both',
        )


def create_network_designer() -> ThermalNetworkDesigner:
    """Factory function to create network designer instance."""
    return ThermalNetworkDesigner()


if __name__ == '__main__':
    # Standalone execution
    pn.extension('plotly')
    designer = create_network_designer()
    dashboard = designer.create_dashboard()
    dashboard.servable(title="EnerGIS Network Designer")
