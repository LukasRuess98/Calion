"""
Thermal Network Results tab for the EnerGIS Dashboard.

Displays detailed thermal network simulation results including:
- Node temperatures and pressures
- Pipe flows, velocities, and pressure drops
- Heat losses
- Network topology visualization
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

try:
    import panel as pn
    HAVE_PANEL = True
except ImportError:
    HAVE_PANEL = False
    pn = None

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False
    go = None

if TYPE_CHECKING:
    from ..data_preparation import DashboardData


def create_thermal_network_tab(
    data: 'DashboardData',
    network_data: Optional[Dict[str, Any]] = None,
    workflow: Any = None,
) -> 'pn.Column':
    """
    Create thermal network results visualization tab.

    Parameters
    ----------
    data : DashboardData
        Prepared dashboard data
    network_data : dict, optional
        Network data from thermal_network_exporter
    workflow : Any, optional
        Workflow result for extracting additional data

    Returns
    -------
    pn.Column
        Thermal network tab content
    """
    if not HAVE_PANEL:
        raise ImportError("Panel required for dashboard")

    # Try to extract network data from various sources
    if network_data is None and workflow is not None:
        network_data = _extract_network_data_from_workflow(workflow)

    if network_data is None or not network_data:
        return pn.Column(
            pn.pane.Markdown("## Thermal Network Ergebnisse"),
            pn.pane.Alert(
                "Keine Thermal Network Daten verfügbar. "
                "Stellen Sie sicher, dass 'export_thermal_network: true' in der Config aktiviert ist.",
                alert_type="warning"
            ),
            sizing_mode='stretch_width'
        )

    # Build tab content
    components = [
        pn.pane.Markdown("## Thermal Network Ergebnisse"),
        pn.pane.Markdown("Detaillierte Analyse der Wärmenetz-Simulation"),
        pn.layout.Divider(),
    ]

    # 1. Summary KPIs
    summary_section = _create_summary_section(network_data)
    components.append(summary_section)
    components.append(pn.layout.Divider())

    # 2. Node Results
    node_section = _create_node_section(network_data, data)
    components.append(node_section)
    components.append(pn.layout.Divider())

    # 3. Pipe Results
    pipe_section = _create_pipe_section(network_data, data)
    components.append(pipe_section)
    components.append(pn.layout.Divider())

    # 4. Timeseries Plots
    timeseries_section = _create_timeseries_section(network_data, data)
    components.append(timeseries_section)

    return pn.Column(*components, sizing_mode='stretch_width')


def _extract_network_data_from_workflow(workflow: Any) -> Optional[Dict[str, Any]]:
    """Try to extract network data from workflow result."""
    # Check for exported network data attached to workflow
    if hasattr(workflow, 'network_export_data') and workflow.network_export_data:
        return workflow.network_export_data

    # Check primary result's solver_meta
    result = None
    if hasattr(workflow, 'rh_result') and workflow.rh_result:
        result = workflow.rh_result
    elif hasattr(workflow, 'mpc_result') and workflow.mpc_result:
        result = workflow.mpc_result
    elif hasattr(workflow, 'pf_result') and workflow.pf_result:
        result = workflow.pf_result

    if result and hasattr(result, 'solver_meta'):
        meta = result.solver_meta
        if isinstance(meta, dict):
            network_data = meta.get('network_data')
            if network_data and (network_data.get('nodes') or network_data.get('pipes')):
                return network_data

    return None


def _create_summary_section(network_data: Dict[str, Any]) -> 'pn.Column':
    """Create summary KPI section."""
    from ..utils import create_kpi_card

    summary = network_data.get('summary', {})
    nodes = network_data.get('nodes', {})
    pipes = network_data.get('pipes', {})

    cards = []

    # Network size
    cards.append(create_kpi_card(
        "Knoten",
        f"{summary.get('num_nodes', len(nodes))}",
        "primary"
    ))

    cards.append(create_kpi_card(
        "Rohrleitungen",
        f"{summary.get('num_pipes', len(pipes))}",
        "primary"
    ))

    # Total pipe length
    total_length = summary.get('total_pipe_length_m', 0)
    cards.append(create_kpi_card(
        "Trassenlänge",
        f"{total_length/1000:.1f} km",
        "info"
    ))

    # Network heat loss
    total_loss = summary.get('total_network_loss_mwh', 0)
    cards.append(create_kpi_card(
        "Netzverluste",
        f"{total_loss:,.0f} MWh",
        "warning"
    ))

    avg_loss = summary.get('avg_network_loss_mw', 0)
    cards.append(create_kpi_card(
        "Ø Verlustleistung",
        f"{avg_loss:.2f} MW",
        "warning"
    ))

    # Calculate max velocity across all pipes
    max_velocity = 0
    for pipe_data in pipes.values():
        v = pipe_data.get('velocity_max', 0)
        if v > max_velocity:
            max_velocity = v

    cards.append(create_kpi_card(
        "Max. Geschwindigkeit",
        f"{max_velocity:.2f} m/s",
        "danger" if max_velocity > 2.5 else "success"
    ))

    return pn.Column(
        pn.pane.Markdown("### Netzwerk-Übersicht"),
        pn.GridBox(*cards, ncols=6, sizing_mode='stretch_width'),
    )


def _create_node_section(
    network_data: Dict[str, Any],
    data: 'DashboardData'
) -> 'pn.Column':
    """Create node results section with table."""
    nodes = network_data.get('nodes', {})

    if not nodes:
        return pn.pane.Markdown("*Keine Knotendaten verfügbar*")

    # Build node table
    rows = []
    for node_id, node_info in nodes.items():
        row = {
            'Knoten-ID': node_id,
            'Typ': node_info.get('type', '-'),
            'Name': node_info.get('name', node_id)[:20],
            'T_Vorlauf [°C]': f"{node_info.get('T_supply_avg', 0):.1f}",
            'T_Rücklauf [°C]': f"{node_info.get('T_return_avg', 0):.1f}",
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Sort by type (plants first, then consumers, then junctions)
    type_order = {'plant': 0, 'consumer': 1, 'junction': 2, 'pump': 3}
    df['_sort'] = df['Typ'].map(lambda x: type_order.get(x, 99))
    df = df.sort_values('_sort').drop('_sort', axis=1)

    return pn.Column(
        pn.pane.Markdown("### Knoten-Ergebnisse"),
        pn.widgets.Tabulator(
            df,
            layout='fit_columns',
            sizing_mode='stretch_width',
            height=300,
            show_index=False,
        ),
    )


def _create_pipe_section(
    network_data: Dict[str, Any],
    data: 'DashboardData'
) -> 'pn.Column':
    """Create pipe results section with table and visualization."""
    pipes = network_data.get('pipes', {})

    if not pipes:
        return pn.pane.Markdown("*Keine Rohrleitungsdaten verfügbar*")

    # Build pipe table
    rows = []
    for pipe_id, pipe_info in pipes.items():
        row = {
            'Rohr-ID': pipe_id,
            'Von → Nach': f"{pipe_info.get('from_node', '?')} → {pipe_info.get('to_node', '?')}",
            'Länge [m]': f"{pipe_info.get('length_m', 0):.0f}",
            'Ø Massenstrom [kg/s]': f"{pipe_info.get('m_dot_avg', 0):.1f}",
            'Max. Geschw. [m/s]': f"{pipe_info.get('velocity_max', 0):.2f}",
            'Max. ΔP [bar]': f"{pipe_info.get('delta_p_max', 0):.3f}",
            'Verlust [MWh]': f"{pipe_info.get('total_heat_loss_mwh', 0):.1f}",
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Create velocity bar chart
    velocity_plot = _create_velocity_bar_chart(pipes)

    return pn.Column(
        pn.pane.Markdown("### Rohrleitungs-Ergebnisse"),
        pn.Row(
            pn.Column(
                pn.widgets.Tabulator(
                    df,
                    layout='fit_columns',
                    sizing_mode='stretch_width',
                    height=300,
                    show_index=False,
                ),
                width=700,
            ),
            pn.Column(
                velocity_plot,
                width=400,
            ),
        ),
    )


def _create_velocity_bar_chart(pipes: Dict[str, Any]):
    """Create bar chart showing max velocities per pipe."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    pipe_ids = list(pipes.keys())[:15]  # Limit to 15 pipes
    velocities = [pipes[p].get('velocity_max', 0) for p in pipe_ids]

    # Color based on velocity limit (2.5 m/s typical limit)
    colors = ['red' if v > 2.5 else 'orange' if v > 2.0 else 'green' for v in velocities]

    fig = go.Figure(data=[
        go.Bar(
            x=pipe_ids,
            y=velocities,
            marker_color=colors,
            text=[f'{v:.2f}' for v in velocities],
            textposition='outside',
        )
    ])

    fig.add_hline(y=2.5, line_dash="dash", line_color="red",
                  annotation_text="Grenzwert 2.5 m/s")

    fig.update_layout(
        title="Max. Fließgeschwindigkeit pro Rohr",
        xaxis_title="Rohrleitung",
        yaxis_title="Geschwindigkeit [m/s]",
        height=300,
        margin=dict(l=40, r=20, t=40, b=80),
        xaxis_tickangle=-45,
    )

    return pn.pane.Plotly(fig)


def _create_timeseries_section(
    network_data: Dict[str, Any],
    data: 'DashboardData'
) -> 'pn.Column':
    """Create timeseries plots section."""
    timeseries = network_data.get('timeseries', {})

    if not timeseries or not HAVE_PLOTLY:
        return pn.pane.Markdown("*Keine Zeitreihendaten verfügbar*")

    # Find available temperature series
    temp_series = {k: v for k, v in timeseries.items() if 'T_supply' in k or 'T_return' in k}
    flow_series = {k: v for k, v in timeseries.items() if 'm_dot' in k}
    pressure_series = {k: v for k, v in timeseries.items() if 'delta_p' in k}
    loss_series = timeseries.get('network_loss', [])

    plots = []

    # Temperature plot
    if temp_series:
        fig = go.Figure()

        # Limit to first week (168 hours) and first 5 nodes
        max_points = min(168, len(list(temp_series.values())[0]))
        count = 0

        for name, values in temp_series.items():
            if count >= 10:  # Max 10 series
                break
            style = 'solid' if 'supply' in name.lower() else 'dash'
            fig.add_trace(go.Scatter(
                y=values[:max_points],
                name=name,
                line=dict(dash=style),
                mode='lines',
            ))
            count += 1

        fig.update_layout(
            title="Temperaturen (erste Woche)",
            yaxis_title="Temperatur [°C]",
            xaxis_title="Stunde",
            height=350,
            legend=dict(orientation='h', y=-0.15),
            hovermode='x unified',
        )

        plots.append(pn.pane.Plotly(fig, sizing_mode='stretch_width'))

    # Pressure drop plot
    if pressure_series:
        fig = go.Figure()

        max_points = min(168, len(list(pressure_series.values())[0]))
        count = 0

        for name, values in pressure_series.items():
            if count >= 10:
                break
            fig.add_trace(go.Scatter(
                y=values[:max_points],
                name=name.replace('_delta_p', ''),
                mode='lines',
            ))
            count += 1

        fig.update_layout(
            title="Druckverluste (erste Woche)",
            yaxis_title="Druckverlust [bar]",
            xaxis_title="Stunde",
            height=300,
            legend=dict(orientation='h', y=-0.15),
            hovermode='x unified',
        )

        plots.append(pn.pane.Plotly(fig, sizing_mode='stretch_width'))

    # Network loss plot
    if loss_series:
        max_points = min(168, len(loss_series))

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=loss_series[:max_points],
            name='Netzverlust',
            fill='tozeroy',
            line=dict(color='orange'),
        ))

        fig.update_layout(
            title="Netzverluste (erste Woche)",
            yaxis_title="Verlustleistung [MW]",
            xaxis_title="Stunde",
            height=250,
            hovermode='x unified',
        )

        plots.append(pn.pane.Plotly(fig, sizing_mode='stretch_width'))

    if not plots:
        return pn.pane.Markdown("*Keine Zeitreihendaten zum Anzeigen*")

    return pn.Column(
        pn.pane.Markdown("### Zeitreihen"),
        *plots,
    )


def has_thermal_network_data(workflow: Any) -> bool:
    """Check if thermal network data is available."""
    if workflow is None:
        return False

    # Check for network_export_data attached to workflow
    if hasattr(workflow, 'network_export_data') and workflow.network_export_data:
        return True

    # Check primary result's solver_meta for network_data
    result = None
    if hasattr(workflow, 'rh_result') and workflow.rh_result:
        result = workflow.rh_result
    elif hasattr(workflow, 'mpc_result') and workflow.mpc_result:
        result = workflow.mpc_result
    elif hasattr(workflow, 'pf_result') and workflow.pf_result:
        result = workflow.pf_result

    if result and hasattr(result, 'solver_meta'):
        meta = result.solver_meta
        if isinstance(meta, dict):
            # Check for actual network_data with content
            network_data = meta.get('network_data', {})
            if network_data and (network_data.get('nodes') or network_data.get('pipes')):
                return True
            # Fallback: check if export_files exists (network was exported)
            if 'export_files' in meta:
                return True

    return False
