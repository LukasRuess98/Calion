"""
Timeseries tab for the EnerGIS Dashboard.

Provides interactive timeseries visualization with filtering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from energis.logging_config import get_logger

logger = get_logger(__name__)

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


def create_timeseries_tab(data: 'DashboardData') -> 'pn.Column':
    """
    Create interactive timeseries tab.

    Parameters
    ----------
    data : DashboardData
        Prepared dashboard data

    Returns
    -------
    pn.Column
        Timeseries tab content
    """
    from ..utils import get_component_color
    from ..widgets import (
        create_time_range_slider,
        create_quick_filter_buttons,
        create_component_selector,
        create_plot_type_selector,
        create_aggregation_selector,
        create_control_card,
        create_warning_message,
    )

    df = data.df

    # Check if we have any data
    if len(df) == 0:
        return create_warning_message(
            "Keine Zeitreihendaten verfügbar",
            "Das Workflow-Ergebnis enthält keine Zeitreihendaten.",
            troubleshooting=(
                "from energis.io.dashboard import diagnose_workflow\n"
                "diagnosis = diagnose_workflow(workflow)\n"
                "print(diagnosis)"
            ),
            solutions=[
                "Prüfe ob die Optimierung ohne Fehler durchgelaufen ist",
                "Stelle sicher dass Solver korrekt konfiguriert ist",
                "Prüfe ob result.series im Workflow-Result populiert ist"
            ]
        )

    if not data.heat_components and not data.elec_components:
        return create_warning_message(
            "Keine Komponenten erkannt",
            f"Es wurden keine Wärme- oder Elektro-Komponenten in den Ergebnissen gefunden.\n\n"
            f"**Verfügbare Spalten ({len(df.columns)}):**\n"
            f"```\n{', '.join(list(df.columns)[:20])}{'...' if len(df.columns) > 20 else ''}\n```",
            solutions=[
                "Thermische Komponenten: Spalten mit Endung '_Q_th_MW'",
                "Elektrische Komponenten: Spalten mit Endung '_Pel_MW'"
            ]
        )

    # Component selection
    heat_selector = create_component_selector(
        data.heat_components,
        name='Thermische Komponenten',
        default_count=3
    )

    # Time range slider
    time_slider = create_time_range_slider(len(df))

    # Quick-Filter Buttons
    quick_filters = create_quick_filter_buttons(time_slider, df)

    # Aggregation selector
    aggregation = create_aggregation_selector()

    # Plot type selector
    plot_type = create_plot_type_selector()

    # Create reactive plot
    @pn.depends(heat_selector, time_slider, plot_type)
    def create_heat_plot(components, time_range, ptype):
        return _create_heat_balance_plot(data, components, time_range, ptype)

    # Electric balance plot
    elec_plot = _create_electric_balance_plot(data)

    # Storage plot (if available)
    storage_plot = _create_storage_plot(data) if data.storage_cols else None

    # Layout
    controls = create_control_card(
        heat_selector,
        time_slider,
        quick_filters,
        pn.layout.Divider(),
        pn.Row(aggregation, plot_type),
        title="Steuerung"
    )

    plots = pn.Column(
        pn.pane.Markdown("### Wärmebilanz"),
        create_heat_plot,
        pn.layout.Divider(),
        pn.pane.Markdown("### Elektrische Bilanz"),
        elec_plot,
    )

    if storage_plot:
        plots.append(pn.layout.Divider())
        plots.append(pn.pane.Markdown("### Thermischer Speicher"))
        plots.append(storage_plot)

    return pn.Column(
        controls,
        plots,
        sizing_mode='stretch_width'
    )


def _create_heat_balance_plot(
    data: 'DashboardData',
    components: List[str],
    time_range: tuple,
    plot_type: str
):
    """Create heat balance plot based on selections."""
    from ..utils import get_component_color

    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    if not components:
        return pn.pane.Markdown("*Bitte Komponenten auswählen*")

    start, end = time_range
    df_subset = data.df.iloc[start:end]

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
                fillcolor=get_component_color(comp),
                line=dict(width=0.5)
            ))
    elif plot_type == 'Lines':
        for comp in components:
            fig.add_trace(go.Scatter(
                x=df_subset['timestamp'],
                y=df_subset[comp],
                mode='lines',
                name=comp.replace('_Q_th_MW', '').replace('_', ' '),
                line=dict(color=get_component_color(comp), width=2)
            ))
    else:  # Stacked Bar
        for comp in components:
            fig.add_trace(go.Bar(
                x=df_subset['timestamp'],
                y=df_subset[comp],
                name=comp.replace('_Q_th_MW', '').replace('_', ' '),
                marker_color=get_component_color(comp)
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


def _create_electric_balance_plot(data: 'DashboardData'):
    """Create electric balance plot."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    df = data.df
    fig = go.Figure()

    # Add electric components
    for comp in data.elec_components:
        if comp in df.columns and df[comp].sum() > 1:
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df[comp],
                mode='lines',
                name=comp.replace('_Pel_MW', '').replace('_', ' '),
                stackgroup='one'
            ))

    # Add grid flows
    if 'P_buy_MW' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['P_buy_MW'],
            mode='lines',
            name='Netzbezug',
            line=dict(color='red', width=2)
        ))

    if 'P_sell_MW' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['P_sell_MW'],
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


def _create_storage_plot(data: 'DashboardData'):
    """Create storage SOC plot."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    df = data.df
    soc_col = next((col for col in data.storage_cols if 'SOC' in col), None)
    if not soc_col:
        return pn.pane.Markdown("*Kein Speicher-SOC verfügbar*")

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # SOC
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df[soc_col],
            mode='lines',
            name='Speicherfüllstand',
            line=dict(color='blue', width=2)
        ),
        secondary_y=False
    )

    # Charge/Discharge
    charge_col = next((col for col in data.storage_cols if 'charge' in col.lower()), None)
    discharge_col = next((col for col in data.storage_cols if 'discharge' in col.lower()), None)

    if charge_col:
        fig.add_trace(
            go.Scatter(
                x=df['timestamp'],
                y=df[charge_col],
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
                x=df['timestamp'],
                y=-df[discharge_col],
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
