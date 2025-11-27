"""
Interactive Dashboard for EnerGIS using Panel.

This module provides a comprehensive, interactive dashboard for exploring
optimization results from EnerGIS workflows (PF, RH, MPC).

Features:
- Multi-tab interface with Overview, Timeseries, Costs, Design, Comparison
- Interactive plots with Plotly/Holoviews
- Real-time component selection and filtering
- Export functionality
- Responsive design

Usage:
    from energis.io.dashboard import create_dashboard

    dashboard = create_dashboard(workflow)
    dashboard.show()  # In Jupyter

    # Or serve as webapp:
    # dashboard.servable()
    # panel serve notebook.ipynb
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd
import numpy as np

try:
    import panel as pn
    import holoviews as hv
    from holoviews import opts, dim
    HAVE_PANEL = True
except ImportError:
    HAVE_PANEL = False
    pn = None
    hv = None

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False
    go = None


__all__ = ["create_dashboard", "HAVE_PANEL", "HAVE_PLOTLY"]


def create_dashboard(workflow: Any, title: str = "EnerGIS Interactive Dashboard") -> Any:
    """
    Create an interactive Panel dashboard for EnerGIS workflow results.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow result from run_workflow()
    title : str, optional
        Dashboard title

    Returns
    -------
    pn.Tabs
        Panel dashboard with multiple tabs
    """

    if not HAVE_PANEL:
        raise ImportError(
            "Panel is required for dashboards. Install with: pip install panel holoviews bokeh"
        )

    # Initialize Panel
    pn.extension('plotly', sizing_mode='stretch_width')

    # Create dashboard instance
    dashboard = EnerGISDashboard(workflow, title)

    return dashboard.create()


class EnerGISDashboard:
    """Main dashboard class for EnerGIS."""

    def __init__(self, workflow: Any, title: str):
        self.workflow = workflow
        self.title = title

        # Determine which results are available
        self.has_pf = workflow.pf_result is not None
        self.has_rh = workflow.rh_result is not None
        self.has_mpc = workflow.mpc_result is not None

        # Select primary result for display
        if self.has_rh:
            self.primary_result = workflow.rh_result
            self.primary_label = "RH"
        elif self.has_mpc:
            self.primary_result = workflow.mpc_result
            self.primary_label = "MPC"
        elif self.has_pf:
            self.primary_result = workflow.pf_result
            self.primary_label = "PF"
        else:
            raise ValueError("No results available in workflow")

        # Prepare data
        self._prepare_data()

    def _prepare_data(self):
        """Prepare DataFrames for dashboard."""

        result = self.primary_result

        # Main timeseries DataFrame
        self.df = pd.DataFrame({
            'timestamp': result.table.index,
            'demand_MW': result.table.data.get('waermebedarf_MWth', [0] * len(result.table.index)),
        })

        # Add all series
        for key, values in result.series.items():
            self.df[key] = values

        # Identify component types
        self.heat_components = [col for col in self.df.columns if col.endswith('_Q_th_MW')]
        self.elec_components = [col for col in self.df.columns if col.endswith('_Pel_MW')]
        self.storage_cols = [col for col in self.df.columns if 'TES' in col]

        # Costs DataFrame
        if hasattr(result, 'costs') and result.costs:
            self.costs_df = pd.DataFrame([
                {
                    'Category': key.replace('objective.', '').replace('_EUR', '').replace('_', ' '),
                    'Value_EUR': float(value) if isinstance(value, (int, float)) else 0.0,
                    'Original_Key': key
                }
                for key, value in result.costs.items()
                if isinstance(value, (int, float)) and key.endswith('_EUR')
            ])

            # Calculate percentages
            total = self.costs_df['Value_EUR'].sum()
            if total > 0:
                self.costs_df['Percentage'] = (self.costs_df['Value_EUR'] / total * 100).round(2)
            else:
                self.costs_df['Percentage'] = 0.0

            self.costs_df = self.costs_df.sort_values('Value_EUR', ascending=False)
        else:
            self.costs_df = pd.DataFrame()

    def create(self) -> pn.Tabs:
        """Create the complete dashboard with all tabs."""

        tabs = pn.Tabs(
            ('📊 Overview', self._create_overview_tab()),
            ('📈 Zeitreihen', self._create_timeseries_tab()),
            ('💰 Kosten', self._create_costs_tab()),
            ('🏭 Anlagen-Design', self._create_design_tab()),
            dynamic=True
        )

        # Add comparison tab if multiple results available
        if (self.has_pf and self.has_rh) or (self.has_pf and self.has_mpc):
            tabs.append(('🔀 Vergleich', self._create_comparison_tab()))

        # Header
        header = pn.pane.Markdown(
            f"# {self.title}\n"
            f"**Workflow:** {' → '.join(self.workflow.plan.steps)} | "
            f"**Zeitschritte:** {len(self.df):,}",
            sizing_mode='stretch_width'
        )

        return pn.Column(header, tabs, sizing_mode='stretch_width')

    def _create_overview_tab(self) -> pn.Column:
        """Create overview tab with KPIs and summary."""

        # KPI Cards
        kpis = self._create_kpi_cards()

        # Quick stats
        stats_text = self._create_stats_summary()

        # Mini plots
        mini_plot = self._create_mini_demand_plot()

        return pn.Column(
            pn.pane.Markdown("## 🎯 Key Performance Indicators"),
            kpis,
            pn.layout.Divider(),
            pn.Row(
                pn.Column(
                    pn.pane.Markdown("## 📋 Zusammenfassung"),
                    stats_text,
                    width=400
                ),
                pn.Column(
                    pn.pane.Markdown("## 📊 Wärmebedarf (Jahresverlauf)"),
                    mini_plot,
                ),
            ),
            sizing_mode='stretch_width'
        )

    def _create_kpi_cards(self) -> pn.GridBox:
        """Create KPI indicator cards."""

        result = self.primary_result

        # Calculate KPIs
        total_demand_MWh = self.df['demand_MW'].sum()
        peak_demand_MW = self.df['demand_MW'].max()

        total_cost = 0
        elec_cost = 0
        fuel_cost = 0
        capex = 0

        if hasattr(result, 'costs') and result.costs:
            total_cost = result.costs.get('objective.OBJ_value_EUR', 0)
            elec_cost = result.costs.get('objective.Grid_energy_cost_EUR', 0)
            fuel_cost = result.costs.get('objective.Fuel_cost_EUR', 0)
            capex = result.costs.get('objective.Capex_cost_EUR', 0)

        # Create cards
        cards = pn.GridBox(
            self._create_kpi_card("💰 Gesamtkosten", f"{total_cost:,.0f} €", "primary"),
            self._create_kpi_card("⚡ Stromkosten", f"{elec_cost:,.0f} €", "info"),
            self._create_kpi_card("🔥 Brennstoffkosten", f"{fuel_cost:,.0f} €", "warning"),
            self._create_kpi_card("🏗️ Investition (CAPEX)", f"{capex:,.0f} €", "success"),
            self._create_kpi_card("📊 Wärmebedarf (Total)", f"{total_demand_MWh:,.0f} MWh", "secondary"),
            self._create_kpi_card("🔝 Spitzenlast", f"{peak_demand_MW:.1f} MW", "danger"),
            ncols=3,
            sizing_mode='stretch_width'
        )

        return cards

    def _create_kpi_card(self, title: str, value: str, card_type: str) -> pn.Card:
        """Create a single KPI card."""

        color_map = {
            'primary': '#0d6efd',
            'secondary': '#6c757d',
            'success': '#198754',
            'danger': '#dc3545',
            'warning': '#ffc107',
            'info': '#0dcaf0'
        }

        color = color_map.get(card_type, '#6c757d')

        card_content = pn.pane.HTML(
            f"""
            <div style="padding: 20px; background: linear-gradient(135deg, {color}20 0%, {color}10 100%);
                        border-left: 4px solid {color}; border-radius: 8px;">
                <div style="font-size: 14px; color: #666; margin-bottom: 8px;">{title}</div>
                <div style="font-size: 28px; font-weight: bold; color: {color};">{value}</div>
            </div>
            """,
            sizing_mode='stretch_width'
        )

        return card_content

    def _create_stats_summary(self) -> pn.pane.Markdown:
        """Create statistics summary text."""

        result = self.primary_result

        # Component stats
        active_hp = len([c for c in self.heat_components if 'HP' in c and self.df[c].sum() > 1])
        active_gen = len([c for c in self.heat_components if 'HP' not in c and self.df[c].sum() > 1])
        has_storage = any('TES_SOC' in col for col in self.df.columns)

        # Energy stats
        total_heat_generated = sum(self.df[col].sum() for col in self.heat_components)

        grid_import = self.df.get('P_buy_MW', pd.Series([0])).sum()

        summary = f"""
        **Zeitraum:** {self.df['timestamp'].min()} bis {self.df['timestamp'].max()}

        **Anzahl Zeitschritte:** {len(self.df):,}

        **Aktive Komponenten:**
        - Wärmepumpen: {active_hp}
        - Andere Erzeuger: {active_gen}
        - Thermischer Speicher: {'Ja' if has_storage else 'Nein'}

        **Energiebilanz:**
        - Wärmeerzeugung: {total_heat_generated:,.0f} MWh
        - Netzbezug: {grid_import:,.0f} MWh

        **Workflow-Modus:** {self.primary_label}
        """

        return pn.pane.Markdown(summary)

    def _create_mini_demand_plot(self):
        """Create mini demand plot for overview."""

        if not HAVE_PLOTLY:
            return pn.pane.Markdown("*Plotly nicht verfügbar*")

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=self.df['timestamp'],
            y=self.df['demand_MW'],
            fill='tozeroy',
            mode='lines',
            line=dict(color='#0d6efd', width=1),
            name='Wärmebedarf'
        ))

        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis_title="",
            yaxis_title="MW",
            showlegend=False,
            hovermode='x'
        )

        return pn.pane.Plotly(fig, sizing_mode='stretch_width')

    def _create_timeseries_tab(self) -> pn.Column:
        """Create interactive timeseries tab."""

        # Component selection
        heat_selector = pn.widgets.MultiChoice(
            name='🔥 Thermische Komponenten',
            options=self.heat_components,
            value=self.heat_components[:3] if len(self.heat_components) > 0 else [],
            sizing_mode='stretch_width'
        )

        # Time range slider
        time_slider = pn.widgets.IntRangeSlider(
            name='📅 Zeitbereich (Stunden)',
            start=0,
            end=len(self.df),
            value=(0, min(168, len(self.df))),
            step=24,
            sizing_mode='stretch_width'
        )

        # Plot type selector
        plot_type = pn.widgets.Select(
            name='Plot-Typ',
            options=['Stacked Area', 'Lines', 'Stacked Bar'],
            value='Stacked Area'
        )

        # Create reactive plot
        @pn.depends(heat_selector, time_slider, plot_type)
        def create_heat_plot(components, time_range, ptype):
            return self._create_heat_balance_plot(components, time_range, ptype)

        # Electric balance plot
        elec_plot = self._create_electric_balance_plot()

        # Storage plot (if available)
        storage_plot = self._create_storage_plot() if self.storage_cols else None

        # Layout
        controls = pn.Card(
            heat_selector,
            time_slider,
            plot_type,
            title="⚙️ Steuerung",
            collapsed=False,
            sizing_mode='stretch_width'
        )

        plots = pn.Column(
            pn.pane.Markdown("### 🔥 Wärmebilanz"),
            create_heat_plot,
            pn.layout.Divider(),
            pn.pane.Markdown("### ⚡ Elektrische Bilanz"),
            elec_plot,
        )

        if storage_plot:
            plots.append(pn.layout.Divider())
            plots.append(pn.pane.Markdown("### 🔋 Thermischer Speicher"))
            plots.append(storage_plot)

        return pn.Column(
            controls,
            plots,
            sizing_mode='stretch_width'
        )

    def _create_heat_balance_plot(self, components: List[str], time_range: tuple, plot_type: str):
        """Create heat balance plot based on selections."""

        if not HAVE_PLOTLY:
            return pn.pane.Markdown("*Plotly nicht verfügbar*")

        if not components:
            return pn.pane.Markdown("*Bitte Komponenten auswählen*")

        start, end = time_range
        df_subset = self.df.iloc[start:end]

        fig = go.Figure()

        # Add components
        if plot_type == 'Stacked Area':
            for comp in components:
                fig.add_trace(go.Scatter(
                    x=df_subset['timestamp'],
                    y=df_subset[comp],
                    mode='lines',
                    name=comp.replace('_Q_th_MW', '').replace('_', ' '),
                    stackgroup='one',
                    fillcolor=self._get_component_color(comp),
                    line=dict(width=0.5)
                ))
        elif plot_type == 'Lines':
            for comp in components:
                fig.add_trace(go.Scatter(
                    x=df_subset['timestamp'],
                    y=df_subset[comp],
                    mode='lines',
                    name=comp.replace('_Q_th_MW', '').replace('_', ' '),
                    line=dict(color=self._get_component_color(comp), width=2)
                ))
        else:  # Stacked Bar
            for comp in components:
                fig.add_trace(go.Bar(
                    x=df_subset['timestamp'],
                    y=df_subset[comp],
                    name=comp.replace('_Q_th_MW', '').replace('_', ' '),
                    marker_color=self._get_component_color(comp)
                ))
            fig.update_layout(barmode='stack')

        # Add demand line
        fig.add_trace(go.Scatter(
            x=df_subset['timestamp'],
            y=df_subset['demand_MW'],
            mode='lines',
            name='Wärmebedarf',
            line=dict(color='black', width=2, dash='dash')
        ))

        fig.update_layout(
            height=500,
            xaxis_title='Zeit',
            yaxis_title='Thermische Leistung [MW]',
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )

        return pn.pane.Plotly(fig, sizing_mode='stretch_width')

    def _create_electric_balance_plot(self):
        """Create electric balance plot."""

        if not HAVE_PLOTLY:
            return pn.pane.Markdown("*Plotly nicht verfügbar*")

        fig = go.Figure()

        # Add electric components
        for comp in self.elec_components:
            if comp in self.df.columns and self.df[comp].sum() > 1:
                fig.add_trace(go.Scatter(
                    x=self.df['timestamp'],
                    y=self.df[comp],
                    mode='lines',
                    name=comp.replace('_Pel_MW', '').replace('_', ' '),
                    stackgroup='one'
                ))

        # Add grid flows
        if 'P_buy_MW' in self.df.columns:
            fig.add_trace(go.Scatter(
                x=self.df['timestamp'],
                y=self.df['P_buy_MW'],
                mode='lines',
                name='Netzbezug',
                line=dict(color='red', width=2)
            ))

        if 'P_sell_MW' in self.df.columns:
            fig.add_trace(go.Scatter(
                x=self.df['timestamp'],
                y=self.df['P_sell_MW'],
                mode='lines',
                name='Einspeisung',
                line=dict(color='green', width=2, dash='dot')
            ))

        fig.update_layout(
            height=400,
            xaxis_title='Zeit',
            yaxis_title='Elektrische Leistung [MW]',
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )

        return pn.pane.Plotly(fig, sizing_mode='stretch_width')

    def _create_storage_plot(self):
        """Create storage SOC plot."""

        if not HAVE_PLOTLY:
            return pn.pane.Markdown("*Plotly nicht verfügbar*")

        soc_col = next((col for col in self.storage_cols if 'SOC' in col), None)
        if not soc_col:
            return pn.pane.Markdown("*Kein Speicher-SOC verfügbar*")

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # SOC
        fig.add_trace(
            go.Scatter(
                x=self.df['timestamp'],
                y=self.df[soc_col],
                mode='lines',
                name='Speicherfüllstand',
                line=dict(color='blue', width=2)
            ),
            secondary_y=False
        )

        # Charge/Discharge
        charge_col = next((col for col in self.storage_cols if 'charge' in col.lower()), None)
        discharge_col = next((col for col in self.storage_cols if 'discharge' in col.lower()), None)

        if charge_col:
            fig.add_trace(
                go.Scatter(
                    x=self.df['timestamp'],
                    y=self.df[charge_col],
                    mode='lines',
                    name='Beladung',
                    line=dict(color='orange', width=1),
                    fill='tozeroy'
                ),
                secondary_y=True
            )

        if discharge_col:
            fig.add_trace(
                go.Scatter(
                    x=self.df['timestamp'],
                    y=-self.df[discharge_col],
                    mode='lines',
                    name='Entladung',
                    line=dict(color='green', width=1),
                    fill='tozeroy'
                ),
                secondary_y=True
            )

        fig.update_yaxes(title_text="Energieinhalt [MWh]", secondary_y=False)
        fig.update_yaxes(title_text="Leistung [MW]", secondary_y=True)
        fig.update_xaxes(title_text="Zeit")

        fig.update_layout(
            height=400,
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
        )

        return pn.pane.Plotly(fig, sizing_mode='stretch_width')

    def _create_costs_tab(self) -> pn.Column:
        """Create costs analysis tab."""

        if self.costs_df.empty:
            return pn.Column(pn.pane.Markdown("*Keine Kostendaten verfügbar*"))

        # Cost breakdown plot
        cost_plot = self._create_cost_breakdown_plot()

        # Interactive cost table
        cost_table = pn.widgets.Tabulator(
            self.costs_df[['Category', 'Value_EUR', 'Percentage']],
            page_size=20,
            sizing_mode='stretch_width',
            theme='modern',
            show_index=False,
            selectable=True,
            formatters={
                'Value_EUR': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 0},
                'Percentage': {'type': 'progress', 'max': 100, 'legend': True}
            }
        )

        # Summary stats
        total_cost = self.costs_df['Value_EUR'].sum()
        top_3 = self.costs_df.head(3)

        summary = f"""
        **Gesamtkosten:** {total_cost:,.0f} €

        **Top 3 Kostenblöcke:**
        1. {top_3.iloc[0]['Category']}: {top_3.iloc[0]['Value_EUR']:,.0f} € ({top_3.iloc[0]['Percentage']:.1f}%)
        2. {top_3.iloc[1]['Category']}: {top_3.iloc[1]['Value_EUR']:,.0f} € ({top_3.iloc[1]['Percentage']:.1f}%)
        3. {top_3.iloc[2]['Category']}: {top_3.iloc[2]['Value_EUR']:,.0f} € ({top_3.iloc[2]['Percentage']:.1f}%)
        """

        return pn.Column(
            pn.Row(
                pn.Column(
                    pn.pane.Markdown("## 📊 Kostenaufteilung"),
                    cost_plot,
                ),
                pn.Column(
                    pn.pane.Markdown("## 📋 Zusammenfassung"),
                    pn.pane.Markdown(summary),
                    width=300
                ),
            ),
            pn.layout.Divider(),
            pn.pane.Markdown("## 📄 Detaillierte Kostentabelle"),
            cost_table,
            sizing_mode='stretch_width'
        )

    def _create_cost_breakdown_plot(self):
        """Create cost breakdown bar chart."""

        if not HAVE_PLOTLY:
            return pn.pane.Markdown("*Plotly nicht verfügbar*")

        # Show top 10 costs
        df_top = self.costs_df.head(10)

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=df_top['Value_EUR'],
            y=df_top['Category'],
            orientation='h',
            marker=dict(
                color=df_top['Value_EUR'],
                colorscale='Blues',
                showscale=False
            ),
            text=[f"{v:,.0f} €" for v in df_top['Value_EUR']],
            textposition='auto',
        ))

        fig.update_layout(
            height=500,
            xaxis_title='Kosten [EUR]',
            yaxis_title='',
            showlegend=False,
            yaxis={'categoryorder': 'total ascending'}
        )

        return pn.pane.Plotly(fig, sizing_mode='stretch_width')

    def _create_design_tab(self) -> pn.Column:
        """Create design/capacity tab."""

        design = self.workflow.design

        if not design:
            return pn.Column(pn.pane.Markdown("*Kein Design verfügbar*"))

        # Heat pump capacities
        hp_data = []
        if design.heat_pumps:
            for hp_id, hp_info in design.heat_pumps.items():
                capacity = hp_info.get('capacity_mw', 0.0)
                hp_data.append({
                    'Komponente': hp_id,
                    'Kapazität [MW]': capacity,
                    'Typ': 'Wärmepumpe'
                })

        # Storage capacity
        if design.storage:
            storage_cap = design.storage.get('capacity_mwh', 0.0)
            hp_data.append({
                'Komponente': 'Thermischer Speicher',
                'Kapazität [MW]': storage_cap,
                'Typ': 'Speicher'
            })

        design_df = pd.DataFrame(hp_data)

        # Capacity plot
        capacity_plot = self._create_capacity_plot(design_df)

        # Design table
        design_table = pn.widgets.Tabulator(
            design_df,
            sizing_mode='stretch_width',
            theme='modern',
            show_index=False,
            formatters={
                'Kapazität [MW]': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 2}
            }
        )

        # Export design as JSON
        design_json = json.dumps({
            'heat_pumps': design.heat_pumps,
            'storage': design.storage
        }, indent=2, default=str)

        json_pane = pn.pane.JSON(design_json, sizing_mode='stretch_width', depth=2)

        return pn.Column(
            pn.pane.Markdown("## 🏭 Anlagenauslegung"),
            capacity_plot,
            pn.layout.Divider(),
            pn.pane.Markdown("## 📋 Kapazitätstabelle"),
            design_table,
            pn.layout.Divider(),
            pn.pane.Markdown("## 📄 Design-Details (JSON)"),
            json_pane,
            sizing_mode='stretch_width'
        )

    def _create_capacity_plot(self, design_df: pd.DataFrame):
        """Create capacity bar chart."""

        if not HAVE_PLOTLY:
            return pn.pane.Markdown("*Plotly nicht verfügbar*")

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=design_df['Komponente'],
            y=design_df['Kapazität [MW]'],
            marker=dict(
                color=['#4477AA' if t == 'Wärmepumpe' else '#EE6677'
                       for t in design_df['Typ']]
            ),
            text=[f"{v:.2f} MW" for v in design_df['Kapazität [MW]']],
            textposition='auto',
        ))

        fig.update_layout(
            height=400,
            xaxis_title='',
            yaxis_title='Kapazität [MW / MWh]',
            showlegend=False
        )

        return pn.pane.Plotly(fig, sizing_mode='stretch_width')

    def _create_comparison_tab(self) -> pn.Column:
        """Create PF vs RH comparison tab."""

        if not (self.has_pf and (self.has_rh or self.has_mpc)):
            return pn.Column(pn.pane.Markdown("*Nicht genügend Ergebnisse für Vergleich*"))

        pf_result = self.workflow.pf_result
        comp_result = self.workflow.rh_result if self.has_rh else self.workflow.mpc_result
        comp_label = "RH" if self.has_rh else "MPC"

        # Cost comparison
        pf_cost = pf_result.costs.get('objective.OBJ_value_EUR', 0)
        comp_cost = comp_result.costs.get('objective.OBJ_value_EUR', 0)

        gap = ((comp_cost - pf_cost) / pf_cost * 100) if pf_cost > 0 else 0

        comparison_data = pd.DataFrame({
            'Metrik': ['Gesamtkosten', 'Optimality Gap'],
            'PF': [f"{pf_cost:,.0f} €", '-'],
            comp_label: [f"{comp_cost:,.0f} €", f"{gap:.2f} %"]
        })

        # Comparison plot
        comp_plot = self._create_comparison_plot(pf_cost, comp_cost, comp_label)

        # Table
        comp_table = pn.widgets.Tabulator(
            comparison_data,
            sizing_mode='stretch_width',
            theme='modern',
            show_index=False
        )

        # Interpretation
        if gap < 1:
            interpretation = "✅ **Exzellent:** Gap < 1% - sehr gute operative Planung"
        elif gap < 5:
            interpretation = "✅ **Gut:** Gap < 5% - akzeptable operative Planung"
        elif gap < 10:
            interpretation = "⚠️ **Akzeptabel:** Gap < 10% - Horizont könnte verlängert werden"
        else:
            interpretation = "⚠️ **Hoch:** Gap > 10% - Horizont zu kurz oder zu viel Unsicherheit"

        return pn.Column(
            pn.pane.Markdown(f"## 🔀 PF vs {comp_label} Vergleich"),
            comp_plot,
            pn.layout.Divider(),
            pn.pane.Markdown("## 📊 Kennzahlen"),
            comp_table,
            pn.layout.Divider(),
            pn.pane.Markdown("## 💡 Interpretation"),
            pn.pane.Markdown(interpretation),
            sizing_mode='stretch_width'
        )

    def _create_comparison_plot(self, pf_cost: float, comp_cost: float, comp_label: str):
        """Create cost comparison plot."""

        if not HAVE_PLOTLY:
            return pn.pane.Markdown("*Plotly nicht verfügbar*")

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=['PF', comp_label],
            y=[pf_cost, comp_cost],
            marker=dict(color=['#4477AA', '#EE6677']),
            text=[f"{pf_cost:,.0f} €", f"{comp_cost:,.0f} €"],
            textposition='auto',
        ))

        fig.update_layout(
            height=400,
            xaxis_title='Methode',
            yaxis_title='Kosten [EUR]',
            showlegend=False,
            title='Kostenvergleich'
        )

        return pn.pane.Plotly(fig, sizing_mode='stretch_width')

    def _get_component_color(self, component: str) -> str:
        """Get color for component based on type."""

        color_map = {
            'HP1': '#4477AA',
            'HP2': '#66CCEE',
            'HP3': '#228833',
            'HP4': '#CCBB44',
            'HKW': '#EE6677',
            'GTOST': '#AA3377',
            'BMHKW': '#228833',
            'TES_discharge': '#BBBBBB',
        }

        for key, color in color_map.items():
            if key in component:
                return color

        return '#999999'
