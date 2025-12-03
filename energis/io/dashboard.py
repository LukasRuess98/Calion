"""
Interactive Dashboard for EnerGIS using Panel.

This module provides a comprehensive, interactive dashboard for exploring
optimization results from EnerGIS workflows (PF, RH, MPC).

Features:
- Multi-tab interface with Overview, Timeseries, Emissions, Costs, Design, Comparison
- Interactive plots with Plotly/Holoviews
- Real-time component selection and filtering
- CO2 emissions tracking and visualization
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


__all__ = ["create_dashboard", "HAVE_PANEL", "HAVE_PLOTLY", "diagnose_workflow"]


def diagnose_workflow(workflow: Any) -> Dict[str, Any]:
    """
    Diagnose workflow data for dashboard compatibility.

    This helper function checks if the workflow has the necessary data
    for dashboard display and provides detailed diagnostic information.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow result from run_workflow()

    Returns
    -------
    dict
        Diagnostic information with keys:
        - 'has_results': bool - at least one result available
        - 'has_timeseries': bool - timeseries data available
        - 'has_costs': bool - cost data available
        - 'has_design': bool - design data available
        - 'primary_result_type': str - which result is used (PF/RH/MPC)
        - 'issues': list of str - detected issues
        - 'recommendations': list of str - recommended actions

    Examples
    --------
    >>> from energis.io.dashboard import diagnose_workflow
    >>> diagnosis = diagnose_workflow(workflow)
    >>> if diagnosis['issues']:
    ...     print("Issues found:", diagnosis['issues'])
    """
    import logging
    logger = logging.getLogger(__name__)

    issues = []
    recommendations = []

    # Check which results are available
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None
    has_mpc = workflow.mpc_result is not None
    has_any_result = has_pf or has_rh or has_mpc

    if not has_any_result:
        issues.append("No workflow results available (pf_result, rh_result, mpc_result all None)")
        recommendations.append("Run the workflow first with run_workflow()")
        return {
            'has_results': False,
            'has_timeseries': False,
            'has_costs': False,
            'has_design': False,
            'primary_result_type': None,
            'issues': issues,
            'recommendations': recommendations,
        }

    # Determine primary result (same logic as EnerGISDashboard.__init__)
    if has_rh:
        primary_result = workflow.rh_result
        primary_label = "RH"
    elif has_mpc:
        primary_result = workflow.mpc_result
        primary_label = "MPC"
    elif has_pf:
        primary_result = workflow.pf_result
        primary_label = "PF"
    else:
        primary_result = None
        primary_label = None

    # Check timeseries data
    has_timeseries = False
    series_count = 0
    if primary_result and hasattr(primary_result, 'series') and primary_result.series:
        series_count = len(primary_result.series)
        has_timeseries = series_count > 0

        if not has_timeseries:
            issues.append(f"Primary result ({primary_label}) has empty series dictionary")
            recommendations.append("Check if optimization completed successfully")
            recommendations.append("Verify that result.series is populated by the solver")
    else:
        issues.append(f"Primary result ({primary_label}) has no series attribute or series is None")
        recommendations.append("Check workflow execution logs for errors")

    # Check cost data
    has_costs = False
    cost_entries = 0
    if primary_result and hasattr(primary_result, 'costs') and primary_result.costs:
        cost_entries = len([k for k, v in primary_result.costs.items()
                           if isinstance(v, (int, float)) and k.endswith('_EUR')])
        has_costs = cost_entries > 0

        if not has_costs:
            issues.append(f"Primary result ({primary_label}) has no cost entries with '_EUR' suffix")
            recommendations.append("Enable cost tracking in configuration")
            recommendations.append("Check if costs.include_* options are enabled")
    else:
        issues.append(f"Primary result ({primary_label}) has no costs attribute or costs is None")
        recommendations.append("Enable objective cost calculation in config")

    # Check design data
    has_design = False
    design_components = 0
    if workflow.design:
        if workflow.design.heat_pumps:
            design_components += len(workflow.design.heat_pumps)
        if workflow.design.storage:
            design_components += 1
        has_design = design_components > 0

        if not has_design:
            issues.append("Design exists but has no components (no heat_pumps or storage)")
            recommendations.append("Run a PF step to generate design data")
    else:
        issues.append("Workflow has no design data")
        recommendations.append("Include 'PF' in workflow steps to generate design")
        recommendations.append("Or load existing design with pf_design_json config")

    # VS-Code specific check
    try:
        import sys
        if 'debugpy' in sys.modules or 'IPython' in sys.modules:
            # Running in Jupyter/VS-Code
            recommendations.append("⚠️  If running in VS-Code: Panel dashboards work best in browser")
            recommendations.append("   Alternative: Use 'panel serve notebook.ipynb' to view in browser")
    except:
        pass

    logger.info(f"Dashboard diagnosis for {primary_label} result:")
    logger.info(f"  - Timeseries: {series_count} series")
    logger.info(f"  - Costs: {cost_entries} entries")
    logger.info(f"  - Design: {design_components} components")

    return {
        'has_results': has_any_result,
        'has_timeseries': has_timeseries,
        'has_costs': has_costs,
        'has_design': has_design,
        'primary_result_type': primary_label,
        'series_count': series_count,
        'cost_entries': cost_entries,
        'design_components': design_components,
        'issues': issues,
        'recommendations': recommendations,
    }


def create_dashboard(workflow: Any, title: str = "EnerGIS Interactive Dashboard",
                     diagnose: bool = True) -> Any:
    """
    Create an interactive Panel dashboard for EnerGIS workflow results.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow result from run_workflow()
    title : str, optional
        Dashboard title
    diagnose : bool, optional
        Run diagnostic check before creating dashboard (default: True)
        Set to False to skip diagnostic warnings

    Returns
    -------
    pn.Tabs
        Panel dashboard with multiple tabs

    Notes
    -----
    **VS-Code Users:** Panel dashboards work best when viewed in a browser.
    If widgets/plots are not displaying correctly in VS-Code, try:

    1. Run: `panel serve notebook.ipynb --show`
    2. Or save and open the notebook in JupyterLab/Jupyter Notebook

    **Troubleshooting:** If data is not displaying:

    - Use `diagnose_workflow(workflow)` to check for missing data
    - Verify optimization completed successfully
    - Check that result.series and result.costs are populated
    """
    import logging
    logger = logging.getLogger(__name__)

    if not HAVE_PANEL:
        raise ImportError(
            "Panel is required for dashboards. Install with: pip install panel holoviews bokeh"
        )

    # Run diagnostic check
    if diagnose:
        diagnosis = diagnose_workflow(workflow)

        # Log diagnostic results
        if diagnosis['issues']:
            logger.warning("Dashboard creation: issues detected")
            for issue in diagnosis['issues']:
                logger.warning(f"  - {issue}")

        if diagnosis['recommendations']:
            logger.info("Dashboard recommendations:")
            for rec in diagnosis['recommendations']:
                logger.info(f"  - {rec}")

        # Print diagnostic summary
        print(f"\n🔍 Dashboard Diagnosis (Primary Result: {diagnosis['primary_result_type']}):")
        print(f"  ✓ Timeseries: {diagnosis['series_count']} series" if diagnosis['has_timeseries']
              else f"  ✗ Timeseries: No data")
        print(f"  ✓ Costs: {diagnosis['cost_entries']} entries" if diagnosis['has_costs']
              else f"  ✗ Costs: No data")
        print(f"  ✓ Design: {diagnosis['design_components']} components" if diagnosis['has_design']
              else f"  ✗ Design: No data")

        if diagnosis['issues']:
            print(f"\n⚠️  Issues found:")
            for issue in diagnosis['issues']:
                print(f"     • {issue}")

        if diagnosis['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in diagnosis['recommendations']:
                print(f"     • {rec}")
        print()

    # Initialize Panel with all required extensions
    # 'plotly' for interactive charts, 'tabulator' for interactive tables
    pn.extension('plotly', 'tabulator', sizing_mode='stretch_width')

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

        # Find demand column - try multiple common names
        demand_col_names = ['waermebedarf_MWth', 'Waermebedarf_MWth', 'heat_demand_MW', 'demand_MW', 'Q_demand_MW']
        demand_values = None
        demand_col_found = None

        for col_name in demand_col_names:
            if col_name in result.table.data:
                demand_values = result.table.data[col_name]
                demand_col_found = col_name
                break

        # ✅ FIX: Exception werfen statt Nullen bei fehlender Demand-Spalte
        if demand_values is None:
            available_cols = list(result.table.data.keys())
            raise ValueError(
                f"Dashboard: Keine Wärmebedarf-Spalte gefunden!\n"
                f"Versuchte Spalten: {demand_col_names}\n"
                f"Verfügbare Spalten: {available_cols}\n"
                f"Bitte stelle sicher, dass mindestens eine dieser Spalten in den Daten vorhanden ist."
            )

        # Main timeseries DataFrame
        self.df = pd.DataFrame({
            'timestamp': result.table.index,
            'demand_MW': demand_values,
        })

        # Add all series BEFORE downsampling
        if result.series:
            for key, values in result.series.items():
                # Ensure values list matches original length
                if len(values) == len(self.df):
                    self.df[key] = values
                else:
                    import logging
                    logging.warning(
                        f"Dashboard: Skipping series '{key}' - length mismatch "
                        f"(expected {len(self.df)}, got {len(values)})"
                    )
        else:
            import logging
            logging.warning("Dashboard: result.series is empty - no timeseries data to display")

        # Identify component types (before downsampling)
        self.heat_components = [col for col in self.df.columns if col.endswith('_Q_th_MW')]
        self.elec_components = [col for col in self.df.columns if col.endswith('_Pel_MW')]
        self.storage_cols = [col for col in self.df.columns if 'TES' in col]

        # ✅ FIX: SPEICHERE ORIGINAL-SUMMEN VOR DOWNSAMPLING
        # Diese Werte sind für KPI-Berechnungen essentiell und dürfen nicht durch Downsampling verfälscht werden
        self.original_total_demand_MWh = self.df['demand_MW'].sum()
        self.original_peak_demand_MW = self.df['demand_MW'].max()
        self.original_timesteps = len(self.df)

        # Berechne Original-Erzeugung pro Komponente
        self.original_heat_production = {}
        for comp in self.heat_components:
            if comp in self.df.columns:
                self.original_heat_production[comp] = self.df[comp].sum()

        self.original_total_heat_production = sum(self.original_heat_production.values())

        # Downsampling für sehr große Datensätze (Performance)
        self.downsampled = False
        original_length = len(self.df)
        MAX_POINTS = 20000  # Maximum Datenpunkte für interaktive Plots

        if original_length > MAX_POINTS:
            import logging
            logging.info(
                f"Dashboard: Large dataset detected ({original_length:,} points). "
                f"Downsampling to {MAX_POINTS:,} points for better performance."
            )

            # Einfaches Downsampling durch Auswahl jedes n-ten Punktes
            step = original_length // MAX_POINTS
            self.df = self.df.iloc[::step].copy()
            self.downsampled = True
            self.downsample_factor = step

            print(f"\n⚠️  Performance-Hinweis:")
            print(f"   Datensatz wurde von {original_length:,} auf {len(self.df):,} Punkte reduziert (Faktor {step})")
            print(f"   Dies verbessert die Dashboard-Performance erheblich.")
            print(f"   Für detaillierte Analysen: Verwende die CSV-Exports aus saved_workflows/\n")
            print(f"   ℹ️  KPIs werden auf Basis der Original-Daten berechnet (nicht downsampled)")
        else:
            # Keine Downsampling nötig
            pass

        # Re-identify component types nach Downsampling (für Plots)
        # Die Original-Komponenten wurden bereits vor Downsampling identifiziert
        self.heat_components = [col for col in self.df.columns if col.endswith('_Q_th_MW')]
        self.elec_components = [col for col in self.df.columns if col.endswith('_Pel_MW')]
        self.storage_cols = [col for col in self.df.columns if 'TES' in col]

        # Log component detection
        if not self.heat_components and not self.elec_components:
            import logging
            logging.warning(
                f"Dashboard: No heat or electric components detected. "
                f"Available columns: {list(self.df.columns)}"
            )

        # Costs DataFrame
        if hasattr(result, 'costs') and result.costs:
            cost_entries = []
            for key, value in result.costs.items():
                if isinstance(value, (int, float)) and key.endswith('_EUR'):
                    cost_entries.append({
                        'Category': key.replace('objective.', '').replace('_EUR', '').replace('_', ' '),
                        'Value_EUR': float(value),
                        'Original_Key': key
                    })

            if cost_entries:
                self.costs_df = pd.DataFrame(cost_entries)

                # Calculate percentages
                total = self.costs_df['Value_EUR'].sum()
                if total > 0:
                    self.costs_df['Percentage'] = (self.costs_df['Value_EUR'] / total * 100).round(2)
                else:
                    self.costs_df['Percentage'] = 0.0

                self.costs_df = self.costs_df.sort_values('Value_EUR', ascending=False)
            else:
                self.costs_df = pd.DataFrame()
                import logging
                logging.warning("Dashboard: No valid cost entries found in result.costs")
        else:
            self.costs_df = pd.DataFrame()
            import logging
            logging.warning("Dashboard: result.costs is empty or missing")

        # ✅ CO2-Daten extrahieren
        self.total_co2_t = 0
        self.grid_co2_t = 0
        self.fuel_co2_t = 0
        self.co2_cost_eur = 0

        if hasattr(result, 'summary') and result.summary:
            # Versuche CO2 aus summary.grid zu holen
            if 'grid' in result.summary:
                self.total_co2_t = result.summary['grid'].get('Total_CO2_emissions_t', 0)
                self.grid_co2_t = result.summary['grid'].get('Grid_CO2_emissions_t', 0)

        if hasattr(result, 'costs') and result.costs:
            # CO2-Kosten und Fuel-Emissionen aus costs
            self.co2_cost_eur = result.costs.get('objective.CO2_cost_EUR', 0)
            self.fuel_co2_t = result.costs.get('Fuel_emissions_t', 0)

            # Falls Total_CO2 nicht in summary gefunden wurde, versuche es aus costs
            if self.total_co2_t == 0:
                # Berechne aus Grid + Fuel falls verfügbar
                if self.grid_co2_t > 0 or self.fuel_co2_t > 0:
                    self.total_co2_t = self.grid_co2_t + self.fuel_co2_t

    def create(self) -> pn.Tabs:
        """Create the complete dashboard with all tabs."""

        tabs = pn.Tabs(
            ('■ Übersicht', self._create_overview_tab()),
            ('═ Zeitreihen', self._create_timeseries_tab()),
            ('▬ Jahresdauerlinie', self._create_duration_curve_tab()),
            ('η Effizienz & COP', self._create_efficiency_tab()),
            ('⇄ Energieflüsse', self._create_sankey_tab()),
            ('🌍 Emissionen', self._create_emissions_tab()),
            ('€ Kosten', self._create_costs_tab()),
            ('▦ Anlagen-Design', self._create_design_tab()),
            dynamic=True
        )

        # Add comparison tab if multiple results available
        if (self.has_pf and self.has_rh) or (self.has_pf and self.has_mpc):
            tabs.append(('⊞ Vergleich', self._create_comparison_tab()))

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
                    pn.pane.Markdown("## ■ Wärmebedarf (Jahresverlauf)"),
                    mini_plot,
                ),
            ),
            sizing_mode='stretch_width'
        )

    def _create_kpi_cards(self) -> pn.GridBox:
        """Create KPI indicator cards."""

        result = self.primary_result

        # ✅ FIX: Verwende ORIGINAL-SUMMEN für KPIs (nicht downsampled!)
        total_demand_MWh = self.original_total_demand_MWh
        peak_demand_MW = self.original_peak_demand_MW
        total_timesteps = self.original_timesteps

        total_cost = 0
        elec_cost = 0
        fuel_cost = 0
        capex = 0

        if hasattr(result, 'costs') and result.costs:
            total_cost = result.costs.get('objective.OBJ_value_EUR', 0)
            elec_cost = result.costs.get('objective.Grid_energy_cost_EUR', 0)
            fuel_cost = result.costs.get('objective.Fuel_cost_EUR', 0)
            capex = result.costs.get('objective.Capex_cost_EUR', 0)

            # ✅ FALLBACK: Bei fehlendem CAPEX in RH/MPC, nutze PF-CAPEX
            # Dies ist ein Fallback für den Fall, dass der Backend-Fix noch nicht angewendet wurde
            # oder bei älteren gespeicherten Workflows
            if capex == 0 and self.primary_label in ("RH", "MPC") and self.has_pf and self.workflow.pf_result:
                pf_capex = self.workflow.pf_result.costs.get('objective.Capex_cost_EUR', 0)
                if pf_capex > 0:
                    import logging
                    logging.info(
                        f"Dashboard: Using PF CAPEX ({pf_capex:,.0f} EUR) as fallback "
                        f"({self.primary_label} result has no CAPEX)"
                    )
                    capex = pf_capex
                    # Addiere zu Gesamtkosten wenn noch nicht enthalten
                    # (Prüfen ob CAPEX bereits in total_cost eingerechnet ist)
                    if 'Capex_cost_EUR' not in result.costs or result.costs['Capex_cost_EUR'] == 0:
                        total_cost += pf_capex

        # ✅ FIX: Berechne Autarkie-Metriken mit ORIGINAL-Summen
        total_heat_production = self.original_total_heat_production
        thermal_autarky = (total_heat_production / total_demand_MWh * 100) if total_demand_MWh > 0 else 0

        # ✅ FIX: Durchschnittliche Auslastung mit ORIGINAL-Daten
        avg_demand = total_demand_MWh / total_timesteps if total_timesteps > 0 else 0
        load_factor = (avg_demand / peak_demand_MW * 100) if peak_demand_MW > 0 else 0

        # Create cards - erweitert mit Autarkie und CO2
        cards = pn.GridBox(
            self._create_kpi_card("💰 Gesamtkosten", f"{total_cost:,.0f} €", "primary"),
            self._create_kpi_card("⚡ Stromkosten", f"{elec_cost:,.0f} €", "info"),
            self._create_kpi_card("🔥 Brennstoffkosten", f"{fuel_cost:,.0f} €", "warning"),
            self._create_kpi_card("🏗️ Investition (CAPEX)", f"{capex:,.0f} €", "success"),
            self._create_kpi_card("📊 Wärmebedarf (Total)", f"{total_demand_MWh:,.0f} MWh", "secondary"),
            self._create_kpi_card("🔝 Spitzenlast", f"{peak_demand_MW:.1f} MW", "danger"),
            self._create_kpi_card("🌱 Thermische Autarkie", f"{thermal_autarky:.1f} %", "success"),
            self._create_kpi_card("📈 Auslastungsfaktor", f"{load_factor:.1f} %", "info"),
            self._create_kpi_card("⏱️ Betriebsstunden", f"{total_timesteps:,} h", "secondary"),
            self._create_kpi_card("🌍 CO₂-Emissionen", f"{self.total_co2_t:,.1f} t", "warning"),
            ncols=5,
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

        # Component stats (kann mit downsampled Daten arbeiten, da es nur Filter ist)
        active_hp = len([c for c in self.heat_components if 'HP' in c and self.df[c].sum() > 1])
        active_gen = len([c for c in self.heat_components if 'HP' not in c and self.df[c].sum() > 1])
        has_storage = any('TES_SOC' in col for col in self.df.columns)

        # ✅ FIX: Energy stats mit ORIGINAL-Summen
        total_heat_generated = self.original_total_heat_production

        # Berechne grid_import aus Original-Daten falls verfügbar
        if 'P_buy_MW' in self.df.columns:
            # Hier müssen wir approximieren, da wir P_buy_MW nicht in original_* gespeichert haben
            # Bei Downsampling ist das eine Näherung
            grid_import = self.df['P_buy_MW'].sum()
            if self.downsampled:
                grid_import = grid_import * self.downsample_factor
        else:
            grid_import = 0

        summary = f"""
        **Zeitraum:** {self.df['timestamp'].min()} bis {self.df['timestamp'].max()}

        **Anzahl Zeitschritte:** {self.original_timesteps:,}

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

        # Check if we have any data
        if len(self.df) == 0:
            return pn.Column(
                pn.pane.Markdown(
                    "## ⚠️ Keine Zeitreihendaten verfügbar\n\n"
                    "Das Workflow-Ergebnis enthält keine Zeitreihendaten. Mögliche Ursachen:\n"
                    "- Die Optimierung ist fehlgeschlagen\n"
                    "- Das `result.series` Dictionary ist leer\n"
                    "- Es gibt ein Datenformat-Problem\n\n"
                    "**Troubleshooting:**\n"
                    "```python\n"
                    "# Prüfe die Ergebnisse\n"
                    "from energis.io.dashboard import diagnose_workflow\n"
                    "diagnosis = diagnose_workflow(workflow)\n"
                    "print(diagnosis)\n"
                    "```\n\n"
                    "**Häufige Lösungen:**\n"
                    "- Prüfe ob die Optimierung ohne Fehler durchgelaufen ist\n"
                    "- Stelle sicher dass Solver korrekt konfiguriert ist\n"
                    "- Prüfe ob `result.series` im Workflow-Result populiert ist\n\n"
                    "Bitte prüfe die Logs für weitere Details."
                )
            )

        if not self.heat_components and not self.elec_components:
            return pn.Column(
                pn.pane.Markdown(
                    "## ⚠️ Keine Komponenten erkannt\n\n"
                    "Es wurden keine Wärme- oder Elektro-Komponenten in den Ergebnissen gefunden.\n\n"
                    f"**Verfügbare Spalten ({len(self.df.columns)}):**\n"
                    f"```\n{', '.join(self.df.columns[:20])}{'...' if len(self.df.columns) > 20 else ''}\n```\n\n"
                    "**Was erwartet wird:**\n"
                    "- Thermische Komponenten: Spalten mit Endung `_Q_th_MW`\n"
                    "- Elektrische Komponenten: Spalten mit Endung `_Pel_MW`\n\n"
                    "**Troubleshooting:**\n"
                    "```python\n"
                    "# Prüfe welche Spalten vorhanden sind\n"
                    "primary_result = workflow.rh_result or workflow.pf_result\n"
                    "print('Available series:', list(primary_result.series.keys()))\n"
                    "```\n\n"
                    "**Mögliche Ursachen:**\n"
                    "- Komponenten sind deaktiviert in der Konfiguration\n"
                    "- Namenskonvention der Komponenten stimmt nicht überein\n"
                    "- result.series wurde nicht korrekt gefüllt"
                )
            )

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

        # Quick-Filter Buttons
        total_hours = len(self.df)

        def set_erste_woche():
            time_slider.value = (0, min(168, total_hours))

        def set_winter_tag():
            # Finde typischen Wintertag (höchster Wärmebedarf)
            if 'demand_MW' in self.df.columns:
                winter_idx = self.df['demand_MW'].idxmax()
                start = max(0, winter_idx - 12)
                end = min(total_hours, winter_idx + 36)
                time_slider.value = (start, end)

        def set_sommer_tag():
            # Finde typischen Sommertag (niedrigster Wärmebedarf)
            if 'demand_MW' in self.df.columns:
                summer_idx = self.df['demand_MW'].idxmin()
                start = max(0, summer_idx - 12)
                end = min(total_hours, summer_idx + 36)
                time_slider.value = (start, end)

        def set_komplettes_jahr():
            time_slider.value = (0, total_hours)

        btn_erste_woche = pn.widgets.Button(name='Erste Woche', button_type='primary', width=120)
        btn_winter = pn.widgets.Button(name='Winter-Tag', button_type='default', width=120)
        btn_sommer = pn.widgets.Button(name='Sommer-Tag', button_type='default', width=120)
        btn_jahr = pn.widgets.Button(name='Ganzes Jahr', button_type='success', width=120)

        btn_erste_woche.on_click(lambda event: set_erste_woche())
        btn_winter.on_click(lambda event: set_winter_tag())
        btn_sommer.on_click(lambda event: set_sommer_tag())
        btn_jahr.on_click(lambda event: set_komplettes_jahr())

        quick_filters = pn.Row(
            pn.pane.Markdown("**⚡ Schnellfilter:**"),
            btn_erste_woche,
            btn_winter,
            btn_sommer,
            btn_jahr,
            sizing_mode='stretch_width'
        )

        # Aggregation selector
        aggregation = pn.widgets.Select(
            name='📊 Aggregation',
            options=['Stündlich', 'Täglich', 'Wöchentlich', 'Monatlich'],
            value='Stündlich'
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
            quick_filters,
            pn.layout.Divider(),
            pn.Row(aggregation, plot_type),
            title="⚙️ Steuerung",
            collapsed=False,
            sizing_mode='stretch_width'
        )

        plots = pn.Column(
            pn.pane.Markdown("### 🔥 Wärmebilanz"),
            create_heat_plot,
            pn.layout.Divider(),
            pn.pane.Markdown("### η Elektrische Bilanz"),
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
            return pn.Column(
                pn.pane.Markdown(
                    "## ⚠️ Keine Kostendaten verfügbar\n\n"
                    "Das Workflow-Ergebnis enthält keine Kostendaten. Mögliche Ursachen:\n"
                    "- Die Optimierung ist fehlgeschlagen\n"
                    "- `result.costs` ist leer oder None\n"
                    "- Keine Kosteneinträge mit '_EUR' Endung gefunden\n\n"
                    "**Troubleshooting:**\n"
                    "```python\n"
                    "# Prüfe Kostendaten\n"
                    "primary_result = workflow.rh_result or workflow.pf_result\n"
                    "print('Costs available:', primary_result.costs)\n"
                    "print('EUR entries:', [k for k in primary_result.costs.keys() if '_EUR' in k])\n"
                    "```\n\n"
                    "**Häufige Lösungen:**\n"
                    "- Aktiviere Kostenberechnung in der Konfiguration:\n"
                    "  ```yaml\n"
                    "  costs:\n"
                    "    include_capex_costs: true\n"
                    "    include_gridcost_in_energy: true\n"
                    "  ```\n"
                    "- Prüfe ob die Optimierung erfolgreich durchgelaufen ist\n"
                    "- Prüfe ob Solver-Optionen korrekt konfiguriert sind"
                )
            )

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
                    pn.pane.Markdown("## ■ Kostenaufteilung"),
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
            return pn.Column(
                pn.pane.Markdown(
                    "## ⚠️ Kein Anlagen-Design verfügbar\n\n"
                    "Das Workflow enthält keine Design-Informationen. Mögliche Ursachen:\n"
                    "- Kein PF-Schritt wurde ausgeführt (Design wird in PF erstellt)\n"
                    "- Die PF-Optimierung ist fehlgeschlagen\n"
                    "- RH-Only Modus ohne vorheriges PF\n\n"
                    "**Troubleshooting:**\n"
                    "```python\n"
                    "# Prüfe Design-Verfügbarkeit\n"
                    "print('Workflow plan:', workflow.plan.steps)\n"
                    "print('Design available:', workflow.design is not None)\n"
                    "if workflow.design:\n"
                    "    print('Heat pumps:', workflow.design.heat_pumps)\n"
                    "    print('Storage:', workflow.design.storage)\n"
                    "```\n\n"
                    "**Um Design-Daten zu erhalten:**\n"
                    "- Führe einen PF-Schritt aus:\n"
                    "  ```yaml\n"
                    "  scenario:\n"
                    "    workflow: ['PF', 'RH']  # oder run_mode: PF_THEN_RH\n"
                    "  ```\n"
                    "- Oder lade ein bestehendes Design:\n"
                    "  ```yaml\n"
                    "  scenario:\n"
                    "    pf_design_json: 'path/to/design.json'\n"
                    "  ```"
                )
            )

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

        # Check if we have any design data
        if not hp_data:
            return pn.Column(
                pn.pane.Markdown(
                    "## ⚠️ Keine Komponenten im Design gefunden\n\n"
                    "Das Design-Objekt existiert, aber enthält keine Wärmepumpen oder Speicher.\n\n"
                    "Dies kann passieren wenn:\n"
                    "- Alle Komponenten in der Optimierung deaktiviert sind\n"
                    "- Die Kapazitäten auf 0 gesetzt wurden\n"
                    "- Es ein Problem beim Extrahieren des Designs gab"
                )
            )

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
            pn.pane.Markdown("## ▦ Anlagenauslegung"),
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
            pn.pane.Markdown("## ■ Kennzahlen"),
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

    def _create_duration_curve_tab(self) -> pn.Column:
        """Create load duration curve tab."""

        if len(self.df) == 0:
            return pn.Column(pn.pane.Markdown("## ⚠️ Keine Daten verfügbar"))

        # Berechne Jahresdauerlinien
        demand_sorted = sorted(self.df['demand_MW'].values, reverse=True)
        hours = list(range(len(demand_sorted)))

        # Wärmeerzeugung pro Komponente
        heat_production = {}
        for comp in self.heat_components:
            if comp in self.df.columns:
                values = sorted(self.df[comp].values, reverse=True)
                heat_production[comp] = values

        # Plot erstellen
        fig = go.Figure()

        # Wärmebedarf
        fig.add_trace(go.Scatter(
            x=hours,
            y=demand_sorted,
            mode='lines',
            name='Wärmebedarf',
            line=dict(color='red', width=3),
        ))

        # Erzeuger
        for comp, values in heat_production.items():
            comp_name = comp.replace('_Q_th_MW', '')
            fig.add_trace(go.Scatter(
                x=hours,
                y=values,
                mode='lines',
                name=comp_name,
                line=dict(color=self._get_component_color(comp), width=2),
            ))

        fig.update_layout(
            title='Jahresdauerlinie - Wärmeerzeugung',
            xaxis_title='Betriebsstunden [h]',
            yaxis_title='Leistung [MW]',
            height=600,
            hovermode='x unified',
            legend=dict(x=0.7, y=0.98)
        )

        # ✅ FIX: Statistiken mit ORIGINAL-Daten berechnen
        total_hours = self.original_timesteps
        peak_demand = self.original_peak_demand_MW
        avg_demand = self.original_total_demand_MWh / total_hours if total_hours > 0 else 0

        # Volllast-Stunden berechnen (>80% der Spitzenlast)
        # Hinweis: Dies basiert auf downsampled Daten - eine Approximation
        full_load_threshold = peak_demand * 0.8
        full_load_hours = sum(1 for d in demand_sorted if d >= full_load_threshold)
        if self.downsampled:
            full_load_hours = full_load_hours * self.downsample_factor

        stats_md = f"""
### ■ Statistiken

| Kennzahl | Wert |
|----------|------|
| **Spitzenlast** | {peak_demand:.2f} MW |
| **Durchschnittslast** | {avg_demand:.2f} MW |
| **Auslastungsfaktor** | {(avg_demand/peak_demand*100) if peak_demand > 0 else 0:.1f} % |
| **Volllast-Stunden (>80%)** | {full_load_hours:,} h |
| **Gesamt-Betriebsstunden** | {total_hours:,} h |

💡 **Interpretation:**
- Volllast-Stunden zeigen, wie oft Spitzenlast-Erzeuger benötigt werden
- Niedriger Auslastungsfaktor deutet auf hohe Lastspitzen hin
- Jahresdauerlinie hilft bei der Dimensionierung von Grund- vs. Spitzenlast
"""

        return pn.Column(
            pn.pane.Markdown("## ▬ Jahresdauerlinie (Load Duration Curve)"),
            pn.pane.Markdown(
                "*Die Jahresdauerlinie zeigt die sortierte Häufigkeitsverteilung der Lasten. "
                "Sie ist essentiell für die Dimensionierung und zeigt, wie oft bestimmte Lastbereiche auftreten.*"
            ),
            pn.pane.Plotly(fig, sizing_mode='stretch_width'),
            pn.layout.Divider(),
            pn.pane.Markdown(stats_md),
            sizing_mode='stretch_width'
        )

    def _create_efficiency_tab(self) -> pn.Column:
        """Create efficiency and COP analysis tab."""

        if len(self.df) == 0:
            return pn.Column(pn.pane.Markdown("## ⚠️ Keine Daten verfügbar"))

        # Finde COP-Spalten
        cop_cols = [col for col in self.df.columns if 'COP' in col or 'cop' in col]

        if not cop_cols:
            return pn.Column(
                pn.pane.Markdown(
                    "## ⚠️ Keine COP-Daten verfügbar\n\n"
                    "Es wurden keine COP (Coefficient of Performance) Daten in den Ergebnissen gefunden.\n\n"
                    "**Verfügbare Spalten:**\n"
                    f"```\n{', '.join(self.df.columns[:20])}...\n```\n\n"
                    "**Hinweis:** COP-Daten werden möglicherweise nicht in den series exportiert. "
                    "Diese könnten in den Notebooks berechnet und hinzugefügt werden."
                )
            )

        # COP über Zeit
        fig_cop_time = go.Figure()

        for cop_col in cop_cols:
            comp_name = cop_col.replace('_COP', '').replace('_cop', '')
            fig_cop_time.add_trace(go.Scatter(
                x=list(range(len(self.df))),
                y=self.df[cop_col],
                mode='lines',
                name=comp_name,
                line=dict(width=2)
            ))

        fig_cop_time.update_layout(
            title='COP über Zeit',
            xaxis_title='Zeitschritt',
            yaxis_title='COP [-]',
            height=400,
            hovermode='x unified'
        )

        # COP Statistiken
        cop_stats = []
        for cop_col in cop_cols:
            comp_name = cop_col.replace('_COP', '').replace('_cop', '')
            values = self.df[cop_col].dropna()
            if len(values) > 0:
                cop_stats.append({
                    'Komponente': comp_name,
                    'Durchschnitt': values.mean(),
                    'Minimum': values.min(),
                    'Maximum': values.max(),
                    'Median': values.median()
                })

        if cop_stats:
            cop_stats_df = pd.DataFrame(cop_stats)

            # Box-Plot
            fig_cop_box = go.Figure()

            for cop_col in cop_cols:
                comp_name = cop_col.replace('_COP', '').replace('_cop', '')
                values = self.df[cop_col].dropna()

                fig_cop_box.add_trace(go.Box(
                    y=values,
                    name=comp_name,
                    boxmean='sd'
                ))

            fig_cop_box.update_layout(
                title='COP Verteilung (Box-Plot)',
                yaxis_title='COP [-]',
                height=400,
                showlegend=True
            )

            stats_md = f"""
### ■ COP Statistiken

Die folgende Tabelle zeigt die statistischen Kennwerte für die Wärmepumpen-Performance:
"""

            # Tabelle
            from panel.widgets import Tabulator
            stats_table = Tabulator(
                cop_stats_df,
                formatters={
                    'Durchschnitt': {'type': 'money', 'symbol': '', 'precision': 2},
                    'Minimum': {'type': 'money', 'symbol': '', 'precision': 2},
                    'Maximum': {'type': 'money', 'symbol': '', 'precision': 2},
                    'Median': {'type': 'money', 'symbol': '', 'precision': 2},
                },
                show_index=False,
                theme='modern',
                sizing_mode='stretch_width'
            )

            return pn.Column(
                pn.pane.Markdown("## η Effizienz & COP Analyse"),
                pn.pane.Markdown(stats_md),
                stats_table,
                pn.layout.Divider(),
                pn.pane.Markdown("### COP Zeitverlauf"),
                pn.pane.Plotly(fig_cop_time, sizing_mode='stretch_width'),
                pn.layout.Divider(),
                pn.pane.Markdown("### COP Verteilung"),
                pn.pane.Plotly(fig_cop_box, sizing_mode='stretch_width'),
                sizing_mode='stretch_width'
            )

        return pn.Column(pn.pane.Markdown("## ⚠️ Keine COP-Statistiken verfügbar"))

    def _create_sankey_tab(self) -> pn.Column:
        """Create Sankey diagram for energy flows."""

        if len(self.df) == 0 or not self.heat_components:
            return pn.Column(pn.pane.Markdown("## ⚠️ Keine Daten verfügbar für Energiefluss-Diagramm"))

        # Aggregiere Energieflüsse über gesamten Zeitraum
        # Quelle: Komponenten → Ziel: Wärmenetz

        nodes = []
        links = []
        node_indices = {}

        # Node 0: Wärmenetz (Ziel)
        nodes.append("Wärmenetz")
        node_indices["Wärmenetz"] = 0

        # Wärmeerzeuger als Quellen
        idx = 1
        total_production = {}

        for comp in self.heat_components:
            if comp in self.df.columns:
                total = self.df[comp].sum()
                if total > 0.01:  # Nur relevante Beiträge
                    comp_name = comp.replace('_Q_th_MW', '')
                    nodes.append(comp_name)
                    node_indices[comp_name] = idx
                    total_production[comp_name] = total
                    idx += 1

        # Erstelle Links von Erzeugern zum Wärmenetz
        for comp_name, total in total_production.items():
            links.append({
                'source': node_indices[comp_name],
                'target': 0,  # Wärmenetz
                'value': total
            })

        if not links:
            return pn.Column(
                pn.pane.Markdown(
                    "## ⚠️ Keine Energieflüsse erkannt\n\n"
                    "Möglicherweise sind alle Komponenten inaktiv oder die Werte zu gering."
                )
            )

        # Sankey-Diagramm erstellen
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=nodes,
                color=['#EE6677'] + ['#4477AA'] * (len(nodes) - 1)
            ),
            link=dict(
                source=[l['source'] for l in links],
                target=[l['target'] for l in links],
                value=[l['value'] for l in links],
                color='rgba(68, 119, 170, 0.4)'
            )
        )])

        fig.update_layout(
            title='Energiefluss-Diagramm (Sankey)',
            font=dict(size=12),
            height=600
        )

        # ✅ FIX: Statistiken mit ORIGINAL-Summen berechnen
        total_demand = self.original_total_demand_MWh
        total_gen = self.original_total_heat_production

        stats_md = f"""
### ■ Energie-Bilanz

| Kennzahl | Wert |
|----------|------|
| **Gesamt-Wärmebedarf** | {total_demand:,.0f} MWh |
| **Gesamt-Erzeugung** | {total_gen:,.0f} MWh |
| **Bilanz** | {(total_gen - total_demand):,.0f} MWh ({((total_gen/total_demand - 1)*100) if total_demand > 0 else 0:.1f}%) |

### 🔥 Erzeugung nach Quelle
"""

        # Sortiere Erzeuger nach Beitrag (verwende original_heat_production)
        sorted_prod = sorted(self.original_heat_production.items(), key=lambda x: x[1], reverse=True)
        for comp_full, value in sorted_prod:
            comp = comp_full.replace('_Q_th_MW', '')
            percentage = (value / total_gen * 100) if total_gen > 0 else 0
            stats_md += f"- **{comp}**: {value:,.0f} MWh ({percentage:.1f}%)\n"

        return pn.Column(
            pn.pane.Markdown("## ⇄ Energiefluss-Diagramm (Sankey)"),
            pn.pane.Markdown(
                "*Das Sankey-Diagramm visualisiert die Energieströme von den Erzeugern zum Wärmenetz. "
                "Die Breite der Flüsse entspricht der übertragenen Energiemenge.*"
            ),
            pn.pane.Plotly(fig, sizing_mode='stretch_width'),
            pn.layout.Divider(),
            pn.pane.Markdown(stats_md),
            sizing_mode='stretch_width'
        )

    def _create_emissions_tab(self) -> pn.Column:
        """Create CO2 emissions analysis tab."""

        # Check if we have any CO2 data
        if self.total_co2_t == 0 and self.co2_cost_eur == 0:
            return pn.Column(
                pn.pane.Markdown(
                    "## ⚠️ Keine CO₂-Emissionsdaten verfügbar\n\n"
                    "Das Workflow-Ergebnis enthält keine CO₂-Daten. Mögliche Ursachen:\n"
                    "- CO₂-Berechnung ist in der Konfiguration deaktiviert\n"
                    "- Die Optimierung ist fehlgeschlagen\n"
                    "- CO₂-Daten wurden nicht exportiert\n\n"
                    "**Um CO₂-Tracking zu aktivieren:**\n"
                    "```yaml\n"
                    "costs:\n"
                    "  include_co2_cost_in_objective: true\n"
                    "  co2_price_eur_per_t: 100.0  # EUR pro Tonne CO₂\n"
                    "```\n\n"
                    "**Troubleshooting:**\n"
                    "```python\n"
                    "# Prüfe CO₂-Daten\n"
                    "primary_result = workflow.rh_result or workflow.pf_result\n"
                    "print('Summary:', primary_result.summary.get('grid', {}))\n"
                    "print('CO2 costs:', primary_result.costs.get('objective.CO2_cost_EUR', 0))\n"
                    "```"
                )
            )

        # KPI-Karten für CO2-Übersicht
        co2_kpis = pn.GridBox(
            self._create_kpi_card("🌍 Gesamt-CO₂", f"{self.total_co2_t:,.1f} t", "warning"),
            self._create_kpi_card("⚡ CO₂ (Strom)", f"{self.grid_co2_t:,.1f} t", "info"),
            self._create_kpi_card("🔥 CO₂ (Brennstoff)", f"{self.fuel_co2_t:,.1f} t", "danger"),
            self._create_kpi_card("💰 CO₂-Kosten", f"{self.co2_cost_eur:,.0f} €", "primary"),
            ncols=4,
            sizing_mode='stretch_width'
        )

        # Berechne CO2-Intensität (kg CO2 pro MWh Wärme)
        co2_intensity = (self.total_co2_t * 1000 / self.original_total_demand_MWh) if self.original_total_demand_MWh > 0 else 0

        # Berechne CO2-Kosten als Anteil der Gesamtkosten
        result = self.primary_result
        total_cost = result.costs.get('objective.OBJ_value_EUR', 0) if hasattr(result, 'costs') else 0
        co2_cost_percentage = (self.co2_cost_eur / total_cost * 100) if total_cost > 0 else 0

        # Zusammenfassungs-Statistiken
        summary_md = f"""
### ■ CO₂-Bilanz Zusammenfassung

| Kennzahl | Wert |
|----------|------|
| **Gesamt-CO₂-Emissionen** | {self.total_co2_t:,.1f} t CO₂eq |
| **CO₂ aus Strombezug** | {self.grid_co2_t:,.1f} t ({(self.grid_co2_t/self.total_co2_t*100) if self.total_co2_t > 0 else 0:.1f}%) |
| **CO₂ aus Brennstoffen** | {self.fuel_co2_t:,.1f} t ({(self.fuel_co2_t/self.total_co2_t*100) if self.total_co2_t > 0 else 0:.1f}%) |
| **CO₂-Intensität** | {co2_intensity:.1f} kg CO₂/MWh_th |
| **CO₂-Kosten** | {self.co2_cost_eur:,.0f} € ({co2_cost_percentage:.1f}% der Gesamtkosten) |
| **Wärmeerzeugung (gesamt)** | {self.original_total_demand_MWh:,.0f} MWh |

💡 **Interpretation:**
- CO₂-Intensität zeigt die Emissionen pro MWh bereitgestellter Wärme
- Niedrige Intensität deutet auf effiziente, CO₂-arme Wärmeerzeugung hin
- Typische Vergleichswerte: Gaskessel ~200 kg/MWh, Wärmepumpe (Strom-Mix) ~50-150 kg/MWh
"""

        # CO2-Breakdown Pie Chart
        breakdown_plot = self._create_co2_breakdown_plot()

        # Aggregierte Emissionstabelle nach Quelle
        emissions_table = self._create_emissions_table()

        # Time series plot (falls verfügbar)
        timeseries_plot = self._create_co2_timeseries_plot()

        return pn.Column(
            pn.pane.Markdown("## 🌍 CO₂-Emissionen Analyse"),
            pn.pane.Markdown(
                "*Dieses Tab zeigt die CO₂-Emissionen des Energiesystems. "
                "CO₂-Emissionen entstehen durch Strombezug (Grid-CO₂) und direkten Brennstoffeinsatz.*"
            ),
            co2_kpis,
            pn.layout.Divider(),
            pn.Row(
                pn.Column(
                    pn.pane.Markdown(summary_md),
                    width=500
                ),
                pn.Column(
                    pn.pane.Markdown("### 📊 CO₂-Quellen Breakdown"),
                    breakdown_plot,
                ),
            ),
            pn.layout.Divider(),
            pn.pane.Markdown("### 📋 Emissionen nach Quelle"),
            emissions_table,
            pn.layout.Divider(),
            pn.pane.Markdown("### ■ CO₂-Emissionen Zeitverlauf"),
            timeseries_plot,
            sizing_mode='stretch_width'
        )

    def _create_co2_breakdown_plot(self):
        """Create CO2 breakdown pie chart (Grid vs. Fuel)."""

        if not HAVE_PLOTLY:
            return pn.pane.Markdown("*Plotly nicht verfügbar*")

        # Daten vorbereiten
        labels = []
        values = []

        if self.grid_co2_t > 0.01:
            labels.append('Strombezug')
            values.append(self.grid_co2_t)

        if self.fuel_co2_t > 0.01:
            labels.append('Brennstoffe')
            values.append(self.fuel_co2_t)

        if not values:
            return pn.pane.Markdown("*Keine CO₂-Daten für Breakdown verfügbar*")

        # Pie Chart erstellen
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,  # Donut chart
            marker=dict(colors=['#0dcaf0', '#dc3545']),
            textinfo='label+percent',
            textfont_size=14,
            hovertemplate='<b>%{label}</b><br>%{value:.1f} t CO₂<br>%{percent}<extra></extra>'
        )])

        fig.update_layout(
            height=400,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
        )

        return pn.pane.Plotly(fig, sizing_mode='stretch_width')

    def _create_emissions_table(self):
        """Create aggregated emissions table by source."""

        # Erstelle Tabelle mit CO2-Quellen
        emissions_data = []

        if self.grid_co2_t > 0:
            emissions_data.append({
                'Quelle': 'Strombezug (Grid)',
                'CO2_t': self.grid_co2_t,
                'Anteil_%': (self.grid_co2_t / self.total_co2_t * 100) if self.total_co2_t > 0 else 0,
                'Typ': 'Elektrisch'
            })

        if self.fuel_co2_t > 0:
            emissions_data.append({
                'Quelle': 'Brennstoffe',
                'CO2_t': self.fuel_co2_t,
                'Anteil_%': (self.fuel_co2_t / self.total_co2_t * 100) if self.total_co2_t > 0 else 0,
                'Typ': 'Thermisch'
            })

        # Gesamt-Zeile hinzufügen
        emissions_data.append({
            'Quelle': 'GESAMT',
            'CO2_t': self.total_co2_t,
            'Anteil_%': 100.0,
            'Typ': '-'
        })

        if not emissions_data:
            return pn.pane.Markdown("*Keine Emissionsdaten verfügbar*")

        emissions_df = pd.DataFrame(emissions_data)

        # Formatierte Tabelle
        table = pn.widgets.Tabulator(
            emissions_df,
            sizing_mode='stretch_width',
            theme='modern',
            show_index=False,
            formatters={
                'CO2_t': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 1, 'symbol': ' t'},
                'Anteil_%': {'type': 'progress', 'max': 100, 'legend': True}
            }
        )

        return table

    def _create_co2_timeseries_plot(self):
        """Create CO2 emissions time series plot if data available."""

        if not HAVE_PLOTLY:
            return pn.pane.Markdown("*Plotly nicht verfügbar*")

        # Suche nach CO2-relevanten Zeitreihen in den Daten
        # Mögliche Spalten: Grid CO2, Fuel CO2, component-specific emissions
        co2_series = []

        # Grid CO2 aus P_buy berechnen falls verfügbar
        if 'P_buy_MW' in self.df.columns and 'grid_co2_kg_MWh' in self.df.columns:
            # Berechne stündliche Grid-CO2-Emissionen
            grid_co2_series = self.df['P_buy_MW'] * self.df['grid_co2_kg_MWh'] / 1000.0  # in Tonnen
            co2_series.append(('Grid CO₂', grid_co2_series))
        elif 'P_buy_MW' in self.df.columns:
            # Falls kein grid_co2_kg_MWh, aber P_buy vorhanden, verwende Durchschnittswert
            if self.grid_co2_t > 0 and self.df['P_buy_MW'].sum() > 0:
                avg_grid_intensity = self.grid_co2_t * 1000 / self.df['P_buy_MW'].sum()  # kg/MWh
                grid_co2_series = self.df['P_buy_MW'] * avg_grid_intensity / 1000.0  # in Tonnen
                co2_series.append(('Grid CO₂ (approx)', grid_co2_series))

        # Suche nach direkten CO2-Spalten in series
        for col in self.df.columns:
            if 'co2' in col.lower() or 'emission' in col.lower():
                if col not in ['grid_co2_kg_MWh']:  # Skip intensity factors
                    co2_series.append((col, self.df[col]))

        if not co2_series:
            return pn.pane.Markdown(
                "*Keine zeitaufgelösten CO₂-Daten verfügbar für Zeitreihen-Plot.*\n\n"
                "Die aggregierten Werte (Grid: {:.1f} t, Fuel: {:.1f} t) sind oben zu sehen.".format(
                    self.grid_co2_t, self.fuel_co2_t
                )
            )

        # Plot erstellen
        fig = go.Figure()

        for name, series in co2_series:
            fig.add_trace(go.Scatter(
                x=self.df['timestamp'],
                y=series,
                mode='lines',
                name=name,
                stackgroup='one' if len(co2_series) > 1 else None,
                line=dict(width=1)
            ))

        fig.update_layout(
            height=400,
            xaxis_title='Zeit',
            yaxis_title='CO₂-Emissionen [t/h]',
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
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
