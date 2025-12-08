"""Results Viewer for Network Designer.

Visualizes simulation results with energy flows, component utilization,
costs, and network topology overlays.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import panel as pn
import param

logger = logging.getLogger(__name__)

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
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


class NetworkResultsViewer(param.Parameterized):
    """Visualizes simulation results in network context."""

    # Result data
    workflow_result = param.Parameter(default=None)
    components = param.List(default=[])
    connections = param.List(default=[])

    def __init__(self, **params):
        super().__init__(**params)
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components."""
        if not HAVE_PLOTLY:
            logger.error("Plotly not available")
            return

        # Tabs for different visualizations
        self.tabs = pn.Tabs(
            ('📊 Übersicht', self._create_overview_tab()),
            ('🗺️ Netzwerk-Flows', self._create_network_flow_tab()),
            ('📈 Zeitreihen', self._create_timeseries_tab()),
            ('💰 Kosten', self._create_costs_tab()),
            ('🔋 Komponenten-Auslastung', self._create_utilization_tab()),
            sizing_mode='stretch_both',
        )

    def _create_overview_tab(self) -> pn.Column:
        """Create overview tab with KPIs."""
        if self.workflow_result is None:
            return pn.Column("_Keine Ergebnisse verfügbar_")

        # Extract KPIs
        result = self._get_primary_result()
        if result is None:
            return pn.Column("_Kein Ergebnis gefunden_")

        kpis = self._extract_kpis(result)

        # KPI cards
        kpi_cards = pn.GridBox(
            *[self._create_kpi_card(key, value, unit) for key, value, unit in kpis],
            ncols=3,
            sizing_mode='stretch_width',
        )

        # Cost breakdown chart
        costs_chart = self._create_costs_pie_chart(result)

        return pn.Column(
            "## Ergebnis-Übersicht",
            kpi_cards,
            "---",
            "### Kosten-Verteilung",
            costs_chart,
            sizing_mode='stretch_both',
        )

    def _create_network_flow_tab(self) -> pn.Column:
        """Create network flow visualization."""
        if not self.components:
            return pn.Column("_Keine Netzwerk-Daten verfügbar_")

        # Create network diagram with flow overlays
        flow_plot = self._create_network_flow_plot()

        # Time slider for animated flows
        time_slider = pn.widgets.IntSlider(
            name='Zeitschritt',
            start=0,
            end=100,
            value=0,
            width=600,
        )

        return pn.Column(
            "## Energie-Flüsse im Netzwerk",
            pn.pane.Markdown(
                "Visualisierung der Energie-Flüsse zwischen Komponenten. "
                "Pfeildicke zeigt Flussstärke an."
            ),
            time_slider,
            flow_plot,
            sizing_mode='stretch_both',
        )

    def _create_timeseries_tab(self) -> pn.Column:
        """Create timeseries plots."""
        if self.workflow_result is None:
            return pn.Column("_Keine Ergebnisse verfügbar_")

        result = self._get_primary_result()
        if result is None:
            return pn.Column("_Kein Ergebnis gefunden_")

        # Create timeseries plots
        production_plot = self._create_production_timeseries(result)
        demand_plot = self._create_demand_timeseries(result)
        storage_plot = self._create_storage_timeseries(result)

        return pn.Column(
            "## Zeitreihen-Analyse",
            "### Wärmeerzeugung",
            production_plot,
            "### Wärmebedarf",
            demand_plot,
            "### Speicher-Füllstand",
            storage_plot,
            sizing_mode='stretch_both',
        )

    def _create_costs_tab(self) -> pn.Column:
        """Create costs analysis."""
        if self.workflow_result is None:
            return pn.Column("_Keine Ergebnisse verfügbar_")

        result = self._get_primary_result()
        if result is None:
            return pn.Column("_Kein Ergebnis gefunden_")

        # Cost breakdown table
        costs_table = self._create_costs_table(result)

        # CAPEX vs OPEX chart
        capex_opex_chart = self._create_capex_opex_chart(result)

        # Component cost breakdown
        component_costs = self._create_component_costs_chart(result)

        return pn.Column(
            "## Kosten-Analyse",
            "### Gesamtkosten",
            costs_table,
            "---",
            "### CAPEX vs OPEX",
            capex_opex_chart,
            "---",
            "### Kosten nach Komponente",
            component_costs,
            sizing_mode='stretch_both',
        )

    def _create_utilization_tab(self) -> pn.Column:
        """Create component utilization analysis."""
        if self.workflow_result is None:
            return pn.Column("_Keine Ergebnisse verfügbar_")

        result = self._get_primary_result()
        if result is None:
            return pn.Column("_Kein Ergebnis gefunden_")

        # Utilization bar chart
        utilization_chart = self._create_utilization_chart(result)

        # Full load hours table
        flh_table = self._create_full_load_hours_table(result)

        return pn.Column(
            "## Komponenten-Auslastung",
            "### Auslastungsgrad",
            utilization_chart,
            "---",
            "### Volllaststunden",
            flh_table,
            sizing_mode='stretch_both',
        )

    def _get_primary_result(self):
        """Get primary result from workflow."""
        if not self.workflow_result:
            return None

        # Priority: RH > MPC > PF
        if hasattr(self.workflow_result, 'rh_result') and self.workflow_result.rh_result:
            return self.workflow_result.rh_result
        elif hasattr(self.workflow_result, 'mpc_result') and self.workflow_result.mpc_result:
            return self.workflow_result.mpc_result
        elif hasattr(self.workflow_result, 'pf_result') and self.workflow_result.pf_result:
            return self.workflow_result.pf_result
        return None

    def _extract_kpis(self, result) -> List[tuple]:
        """Extract KPIs from result."""
        kpis = []

        if hasattr(result, 'costs') and result.costs:
            total_cost = sum(v for k, v in result.costs.items() if isinstance(v, (int, float)))
            kpis.append(('Gesamtkosten', f'{total_cost:,.0f}', '€'))

        if hasattr(result, 'table') and hasattr(result.table, 'data'):
            # Find demand column
            demand_cols = ['waermebedarf_MWth', 'heat_demand_MW', 'demand_MW']
            for col in demand_cols:
                if col in result.table.data:
                    total_demand = sum(result.table.data[col])
                    kpis.append(('Gesamt-Wärmebedarf', f'{total_demand:,.0f}', 'MWh'))
                    kpis.append(('Spitzenlast', f'{max(result.table.data[col]):.1f}', 'MW'))
                    break

        return kpis

    def _create_kpi_card(self, key: str, value: str, unit: str) -> pn.pane.Markdown:
        """Create KPI card."""
        return pn.pane.Markdown(
            f"### {key}\n\n**{value}** {unit}",
            styles={
                'background': '#f5f5f5',
                'padding': '20px',
                'border-radius': '8px',
                'border': '1px solid #ddd',
            },
        )

    def _create_costs_pie_chart(self, result) -> pn.pane.Plotly:
        """Create costs pie chart."""
        if not hasattr(result, 'costs') or not result.costs:
            return pn.pane.Markdown("_Keine Kostendaten verfügbar_")

        # Group costs
        cost_data = {}
        for key, value in result.costs.items():
            if isinstance(value, (int, float)) and value > 0:
                category = key.split('_')[0]
                cost_data[category] = cost_data.get(category, 0) + value

        if not cost_data:
            return pn.pane.Markdown("_Keine Kostendaten verfügbar_")

        fig = go.Figure(data=[go.Pie(
            labels=list(cost_data.keys()),
            values=list(cost_data.values()),
            hole=0.4,
        )])

        fig.update_layout(
            title="Kosten-Verteilung",
            height=400,
        )

        return pn.pane.Plotly(fig)

    def _create_network_flow_plot(self) -> pn.pane.Plotly:
        """Create network diagram with flow arrows."""
        fig = go.Figure()

        # Draw connections as arrows
        for conn in self.connections:
            from_comp = self._get_component_by_id(conn.from_id)
            to_comp = self._get_component_by_id(conn.to_id)

            if from_comp and to_comp:
                # Arrow from -> to
                fig.add_annotation(
                    x=to_comp.x,
                    y=to_comp.y,
                    ax=from_comp.x,
                    ay=from_comp.y,
                    xref='x',
                    yref='y',
                    axref='x',
                    ayref='y',
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=3,
                    arrowcolor='blue',
                )

        # Draw components
        for comp in self.components:
            fig.add_trace(go.Scatter(
                x=[comp.x],
                y=[comp.y],
                mode='markers+text',
                marker=dict(size=20, color='red'),
                text=comp.component_id,
                textposition='top center',
                showlegend=False,
            ))

        fig.update_layout(
            title="Netzwerk-Topologie mit Energie-Flüssen",
            xaxis=dict(title="X (m)", showgrid=True),
            yaxis=dict(title="Y (m)", showgrid=True),
            height=600,
            hovermode='closest',
        )

        return pn.pane.Plotly(fig)

    def _create_production_timeseries(self, result) -> pn.pane.Plotly:
        """Create production timeseries plot."""
        if not hasattr(result, 'table') or not result.table:
            return pn.pane.Markdown("_Keine Daten verfügbar_")

        # Find production columns
        prod_cols = [col for col in result.table.data.keys() if '_Q_th_MW' in col]

        if not prod_cols:
            return pn.pane.Markdown("_Keine Produktionsdaten gefunden_")

        fig = go.Figure()

        for col in prod_cols:
            fig.add_trace(go.Scatter(
                y=result.table.data[col],
                name=col,
                mode='lines',
                stackgroup='one',
            ))

        fig.update_layout(
            title="Wärmeerzeugung nach Komponente",
            xaxis_title="Zeitschritt",
            yaxis_title="Leistung (MW)",
            height=400,
            hovermode='x unified',
        )

        return pn.pane.Plotly(fig)

    def _create_demand_timeseries(self, result) -> pn.pane.Plotly:
        """Create demand timeseries plot."""
        if not hasattr(result, 'table') or not result.table:
            return pn.pane.Markdown("_Keine Daten verfügbar_")

        # Find demand column
        demand_cols = ['waermebedarf_MWth', 'heat_demand_MW', 'demand_MW']
        demand_data = None

        for col in demand_cols:
            if col in result.table.data:
                demand_data = result.table.data[col]
                break

        if demand_data is None:
            return pn.pane.Markdown("_Keine Bedarfsdaten gefunden_")

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            y=demand_data,
            name='Wärmebedarf',
            mode='lines',
            line=dict(color='red'),
        ))

        fig.update_layout(
            title="Wärmebedarf-Verlauf",
            xaxis_title="Zeitschritt",
            yaxis_title="Leistung (MW)",
            height=400,
        )

        return pn.pane.Plotly(fig)

    def _create_storage_timeseries(self, result) -> pn.pane.Plotly:
        """Create storage SOC timeseries."""
        if not hasattr(result, 'table') or not result.table:
            return pn.pane.Markdown("_Keine Daten verfügbar_")

        # Find storage columns
        storage_cols = [col for col in result.table.data.keys() if 'TES' in col and 'SOC' in col]

        if not storage_cols:
            return pn.pane.Markdown("_Keine Speicherdaten gefunden_")

        fig = go.Figure()

        for col in storage_cols:
            fig.add_trace(go.Scatter(
                y=result.table.data[col],
                name=col,
                mode='lines',
            ))

        fig.update_layout(
            title="Speicher-Füllstand (SOC)",
            xaxis_title="Zeitschritt",
            yaxis_title="SOC (%)",
            height=400,
        )

        return pn.pane.Plotly(fig)

    def _create_costs_table(self, result) -> pn.widgets.Tabulator:
        """Create costs table."""
        if not hasattr(result, 'costs') or not result.costs:
            return pn.pane.Markdown("_Keine Kostendaten verfügbar_")

        costs_data = []
        for key, value in result.costs.items():
            if isinstance(value, (int, float)):
                costs_data.append({
                    'Kategorie': key.replace('objective.', '').replace('_EUR', '').replace('_', ' '),
                    'Kosten (€)': f'{value:,.2f}',
                })

        if not costs_data:
            return pn.pane.Markdown("_Keine Kostendaten verfügbar_")

        df = pd.DataFrame(costs_data)
        return pn.widgets.Tabulator(df, sizing_mode='stretch_width')

    def _create_capex_opex_chart(self, result) -> pn.pane.Plotly:
        """Create CAPEX vs OPEX chart."""
        # Extract CAPEX and OPEX
        capex = 0
        opex = 0

        if hasattr(result, 'costs') and result.costs:
            for key, value in result.costs.items():
                if isinstance(value, (int, float)):
                    if 'investment' in key.lower() or 'capex' in key.lower():
                        capex += value
                    elif 'opex' in key.lower() or 'operating' in key.lower():
                        opex += value

        fig = go.Figure(data=[
            go.Bar(name='CAPEX', x=['Investition'], y=[capex], marker_color='steelblue'),
            go.Bar(name='OPEX', x=['Betrieb'], y=[opex], marker_color='lightcoral'),
        ])

        fig.update_layout(
            title="CAPEX vs OPEX",
            yaxis_title="Kosten (€)",
            height=400,
            barmode='group',
        )

        return pn.pane.Plotly(fig)

    def _create_component_costs_chart(self, result) -> pn.pane.Plotly:
        """Create component costs breakdown."""
        # Placeholder - requires detailed cost attribution
        fig = go.Figure()

        fig.update_layout(
            title="Kosten nach Komponente (in Entwicklung)",
            height=400,
        )

        return pn.pane.Plotly(fig)

    def _create_utilization_chart(self, result) -> pn.pane.Plotly:
        """Create utilization bar chart."""
        # Placeholder - requires capacity and production data
        fig = go.Figure()

        fig.update_layout(
            title="Komponenten-Auslastung (in Entwicklung)",
            height=400,
        )

        return pn.pane.Plotly(fig)

    def _create_full_load_hours_table(self, result) -> pn.widgets.Tabulator:
        """Create full load hours table."""
        # Placeholder
        df = pd.DataFrame({
            'Komponente': ['WP1', 'Kessel1', 'Speicher1'],
            'Volllaststunden': [5000, 3000, 4500],
        })

        return pn.widgets.Tabulator(df, sizing_mode='stretch_width')

    def _get_component_by_id(self, component_id: str):
        """Get component by ID."""
        for comp in self.components:
            if comp.component_id == component_id:
                return comp
        return None

    def create_viewer(self) -> pn.Column:
        """Create complete viewer layout."""
        if not HAVE_PLOTLY:
            return pn.Column("❌ Plotly nicht verfügbar")

        return pn.Column(
            "# 📊 Simulations-Ergebnisse",
            self.tabs,
            sizing_mode='stretch_both',
        )


def create_results_viewer(workflow_result, components, connections) -> NetworkResultsViewer:
    """Factory function to create results viewer."""
    return NetworkResultsViewer(
        workflow_result=workflow_result,
        components=components,
        connections=connections,
    )
