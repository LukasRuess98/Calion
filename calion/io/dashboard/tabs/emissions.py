"""
CO2 emissions analysis tab for the CALION Dashboard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Tuple

import pandas as pd

try:
    import panel as pn
    HAVE_PANEL = True
except ImportError:
    HAVE_PANEL = False
    pn = None

try:
    import plotly.graph_objects as go
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False
    go = None

if TYPE_CHECKING:
    from ..data_preparation import DashboardData


def create_emissions_tab(data: 'DashboardData', result: Any) -> 'pn.Column':
    """
    Create CO2 emissions analysis tab with interactive time filtering.

    Parameters
    ----------
    data : DashboardData
        Prepared dashboard data
    result : Any
        Primary workflow result

    Returns
    -------
    pn.Column
        Emissions tab content
    """
    from ..utils import create_kpi_card
    from ..widgets import create_time_range_slider, create_quick_filter_buttons

    # Check if we have any CO2 data
    if data.total_co2_t == 0 and data.co2_cost_eur == 0:
        return pn.Column(
            pn.pane.Markdown(
                "## WARNUNG: Keine CO2-Emissionsdaten verfügbar\n\n"
                "Das Workflow-Ergebnis enthält keine CO2-Daten.\n\n"
                "**Um CO2-Tracking zu aktivieren:**\n"
                "```yaml\n"
                "costs:\n"
                "  include_co2_cost_in_objective: true\n"
                "  co2_price_eur_per_t: 100.0\n"
                "```"
            )
        )

    df = data.df

    # Extract CO2 costs
    co2_heat_cost = result.costs.get('CO2_heat_total_cost_EUR', 0) if hasattr(result, 'costs') else 0
    co2_elec_cost = result.costs.get('CO2_elec_total_cost_EUR', 0) if hasattr(result, 'costs') else 0
    co2_total_cost = result.costs.get('CO2_total_cost_EUR', data.co2_cost_eur) if hasattr(result, 'costs') else data.co2_cost_eur

    # Calculate grid export
    p_sell_mwh = df['P_sell_MW'].sum() * data.dt_h if 'P_sell_MW' in df.columns else 0
    co2_grid_export_t = _calculate_grid_export_co2(data, result, p_sell_mwh)

    # KPI cards
    co2_kpis = pn.GridBox(
        create_kpi_card("Gesamt-CO2-Äquivalente", f"{data.total_co2_t:,.1f} t", "warning"),
        create_kpi_card("CO2-Äq. Wärmeerzeugung", f"{data.fuel_co2_heat_t:,.1f} t", "danger"),
        create_kpi_card("CO2-Äq. Strom-Eigenverbrauch", f"{data.fuel_co2_elec_t:,.1f} t", "success"),
        create_kpi_card("Stromeinspeisung", f"{p_sell_mwh:,.0f} MWh ({co2_grid_export_t:,.1f} t*)", "light"),
        create_kpi_card("CO2-Äq. Strombezug (Netz)", f"{data.grid_co2_elec_t:,.1f} t", "info"),
        create_kpi_card("CO2-Kosten Wärme", f"{co2_heat_cost:,.0f} €", "danger"),
        create_kpi_card("CO2-Kosten Strom", f"{co2_elec_cost:,.0f} €", "info"),
        create_kpi_card("CO2-Kosten Gesamt", f"{co2_total_cost:,.0f} €", "primary"),
        ncols=5,
        sizing_mode='stretch_width'
    )

    # Summary markdown
    summary_md = _create_summary_markdown(data, result, co2_total_cost, p_sell_mwh)

    # Breakdown plot
    breakdown_plot = _create_co2_breakdown_plot(data)

    # Emissions table
    emissions_table = _create_emissions_table(data)

    # Find CO2 source columns for timeseries
    co2_source_columns = _find_co2_source_columns(df)

    # Create interactive controls
    co2_source_selector = pn.widgets.MultiChoice(
        name='CO2-Quellen',
        options=[label for label, _ in co2_source_columns],
        value=[label for label, _ in co2_source_columns[:5]] if len(co2_source_columns) > 0 else [],
        sizing_mode='stretch_width'
    )

    time_slider = create_time_range_slider(len(df))
    quick_filters = create_quick_filter_buttons(time_slider, df)

    # Reactive CO2 timeseries plot
    @pn.depends(time_slider, co2_source_selector)
    def create_co2_timeseries(time_range, selected_sources):
        return _create_co2_timeseries_plot(data, time_range, selected_sources, co2_source_columns)

    controls = pn.Card(
        co2_source_selector,
        time_slider,
        quick_filters,
        title="Filter & Auswahl",
        collapsed=False,
        sizing_mode='stretch_width'
    )

    # Grid export note
    grid_export_note = ""
    if co2_grid_export_t > 0.01:
        grid_export_note = f"""
**Hinweis zur Stromeinspeisung (*)**:
- {co2_grid_export_t:,.1f} t CO2 entstanden durch eingespeisten Strom
- Diese werden **NICHT** in der Bilanz angerechnet (neutraler Ansatz)
"""

    return pn.Column(
        pn.pane.Markdown("## Emissionsanalyse in CO2-Äquivalenten"),
        pn.pane.Markdown(
            "*Dieses Tab zeigt die Treibhausgasemissionen des Energiesystems in CO2-Äquivalenten.*"
        ),
        co2_kpis,
        pn.pane.Markdown(grid_export_note) if grid_export_note else pn.Spacer(height=0),
        pn.layout.Divider(),
        pn.Row(
            pn.Column(pn.pane.Markdown(summary_md), width=500),
            pn.Column(
                pn.pane.Markdown("### Emissionsquellen"),
                breakdown_plot,
            ),
        ),
        pn.layout.Divider(),
        pn.pane.Markdown("### Emissionen nach Quelle (Gesamtzeitraum)"),
        emissions_table,
        pn.layout.Divider(),
        pn.pane.Markdown("### CO2-Äquivalente Zeitverlauf"),
        controls,
        create_co2_timeseries,
        sizing_mode='stretch_width'
    )


def _calculate_grid_export_co2(data: 'DashboardData', result: Any, p_sell_mwh: float) -> float:
    """Calculate CO2 for grid export."""
    if p_sell_mwh <= 0.01:
        return 0.0

    if hasattr(result, 'costs'):
        co2_fuel_elec_gross = result.costs.get('CO2_fuel_to_elec_kg_gross', 0) / 1000.0
        selfuse_fraction = result.costs.get('CO2_fuel_to_elec_selfuse_fraction', 1.0)

        if co2_fuel_elec_gross > 0.01:
            return co2_fuel_elec_gross * (1 - selfuse_fraction)

    return 0.0


def _create_summary_markdown(data: 'DashboardData', result: Any, co2_total_cost: float, p_sell_mwh: float) -> str:
    """Create summary markdown."""
    # Calculate CO2 intensity
    co2_intensity = (data.total_co2_t * 1000 / data.original_total_demand_MWh) if data.original_total_demand_MWh > 0 else 0

    total_cost = result.costs.get('objective.OBJ_value_EUR', 0) if hasattr(result, 'costs') else 0
    co2_cost_percentage = (data.co2_cost_eur / total_cost * 100) if total_cost > 0 else 0

    summary_md = f"""
### CO2-Äquivalente Bilanz

| Kennzahl | Wert |
|----------|------|
| **Gesamt-CO2-Äquivalente** | {data.total_co2_t:,.1f} t CO2eq |
| **CO2-Äq. Wärmeerzeugung** | {data.fuel_co2_heat_t:,.1f} t ({(data.fuel_co2_heat_t/data.total_co2_t*100) if data.total_co2_t > 0 else 0:.1f}%) |
| **CO2-Äq. Strom-Eigenverbrauch (CHP)** | {data.fuel_co2_elec_t:,.1f} t ({(data.fuel_co2_elec_t/data.total_co2_t*100) if data.total_co2_t > 0 else 0:.1f}%) |
| **CO2-Äq. Strombezug (Netz)** | {data.grid_co2_elec_t:,.1f} t ({(data.grid_co2_elec_t/data.total_co2_t*100) if data.total_co2_t > 0 else 0:.1f}%) |
| **CO2-Intensität** | {co2_intensity:.1f} kg CO2eq/MWh_th |
| **CO2-Kosten Gesamt** | {co2_total_cost:,.0f} € ({co2_cost_percentage:.1f}% der Gesamtkosten) |
| **Wärmebereitstellung (gesamt)** | {data.original_total_demand_MWh:,.0f} MWh |

**Interpretation:**
- CO2-Intensität: Emissionen pro MWh bereitgestellter Wärme
- Vergleichswerte: Gaskessel ~200 kg/MWh, Wärmepumpe ~50-150 kg/MWh
"""
    return summary_md


def _create_co2_breakdown_plot(data: 'DashboardData'):
    """Create CO2 breakdown pie chart."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    labels = []
    values = []
    colors = []

    if data.fuel_co2_heat_t > 0.01:
        labels.append('Wärmeerzeugung')
        values.append(data.fuel_co2_heat_t)
        colors.append('#dc3545')

    if data.fuel_co2_elec_t > 0.01:
        labels.append('Strom-Eigenverbrauch (CHP)')
        values.append(data.fuel_co2_elec_t)
        colors.append('#198754')

    if data.grid_co2_elec_t > 0.01:
        labels.append('Strombezug (Netz)')
        values.append(data.grid_co2_elec_t)
        colors.append('#0dcaf0')

    if not values:
        return pn.pane.Markdown("*Keine CO2-Äquivalent-Daten für Breakdown verfügbar*")

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(colors=colors),
        textinfo='label+percent',
        textfont_size=14,
        hovertemplate='<b>%{label}</b><br>%{value:.1f} t CO2eq<br>%{percent}<extra></extra>'
    )])

    fig.update_layout(
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
        title=dict(
            text=f'CO2-Aufteilung: {len(values)} Kategorien | Gesamt: {sum(values):.1f} t',
            font=dict(size=12),
            x=0.5,
            xanchor='center'
        )
    )

    return pn.pane.Plotly(fig, sizing_mode='stretch_width')


def _create_emissions_table(data: 'DashboardData'):
    """Create emissions table."""
    emissions_data = []

    if data.fuel_co2_heat_t > 0.001:
        emissions_data.append({
            'Quelle': 'Wärmeerzeugung (Brennstoff)',
            'CO2eq_t': data.fuel_co2_heat_t,
            'Anteil_%': (data.fuel_co2_heat_t / data.total_co2_t * 100) if data.total_co2_t > 0 else 0,
            'Kategorie': 'Direkt - Wärme'
        })

    if data.fuel_co2_elec_t > 0.001:
        emissions_data.append({
            'Quelle': 'Strom-Eigenverbrauch (CHP)',
            'CO2eq_t': data.fuel_co2_elec_t,
            'Anteil_%': (data.fuel_co2_elec_t / data.total_co2_t * 100) if data.total_co2_t > 0 else 0,
            'Kategorie': 'Direkt - Strom'
        })

    if data.grid_co2_elec_t > 0.001:
        emissions_data.append({
            'Quelle': 'Strombezug (Netz für WP/P2H)',
            'CO2eq_t': data.grid_co2_elec_t,
            'Anteil_%': (data.grid_co2_elec_t / data.total_co2_t * 100) if data.total_co2_t > 0 else 0,
            'Kategorie': 'Indirekt - Grid'
        })

    emissions_data = sorted(emissions_data, key=lambda x: x['CO2eq_t'], reverse=True)

    sum_co2 = sum(e['CO2eq_t'] for e in emissions_data)
    emissions_data.append({
        'Quelle': '═══ GESAMT ═══',
        'CO2eq_t': sum_co2,
        'Anteil_%': 100.0,
        'Kategorie': 'Summe'
    })

    if not emissions_data:
        return pn.pane.Markdown("*Keine Emissionsdaten verfügbar*")

    emissions_df = pd.DataFrame(emissions_data)

    table = pn.widgets.Tabulator(
        emissions_df,
        sizing_mode='stretch_width',
        theme='modern',
        show_index=False,
        formatters={
            'CO2eq_t': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 1, 'symbol': ' t'},
            'Anteil_%': {'type': 'progress', 'max': 100, 'legend': True}
        }
    )

    return table


def _find_co2_source_columns(df: pd.DataFrame) -> List[Tuple[str, str]]:
    """Find CO2 source columns in DataFrame."""
    co2_source_columns = []

    if 'Grid_CO2_emissions_t_per_step' in df.columns:
        co2_source_columns.append(('Strombezug (Grid)', 'Grid_CO2_emissions_t_per_step'))

    for col in df.columns:
        if col.startswith('CO2_') and col.endswith('_t_per_step'):
            gen_name = col.replace('CO2_', '').replace('_t_per_step', '')
            co2_source_columns.append((gen_name, col))

    return co2_source_columns


def _create_co2_timeseries_plot(
    data: 'DashboardData',
    time_range: tuple,
    selected_sources: list,
    co2_source_columns: List[Tuple[str, str]]
):
    """Create CO2 emissions time series plot."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    df = data.df

    # Apply time filter
    if time_range:
        start, end = time_range
        df_subset = df.iloc[start:end]
    else:
        df_subset = df

    co2_series = []

    if co2_source_columns and selected_sources:
        source_map = {label: col for label, col in co2_source_columns}

        for source_label in selected_sources:
            if source_label in source_map:
                col_name = source_map[source_label]
                if col_name in df_subset.columns:
                    series = df_subset[col_name]
                    if series.sum() > 0.001:
                        display_name = source_label if source_label != 'Strombezug (Grid)' else 'Strombezug'
                        co2_series.append((display_name, series))

    # Fallback
    if not co2_series:
        if 'Grid_CO2_emissions_t_per_step' in df_subset.columns:
            co2_series.append(('CO2-Äq. aus Strombezug', df_subset['Grid_CO2_emissions_t_per_step']))

        if 'Fuel_CO2_emissions_t_per_step' in df_subset.columns:
            fuel_co2 = df_subset['Fuel_CO2_emissions_t_per_step']
            if fuel_co2.sum() > 0.001:
                co2_series.append(('CO2-Äq. aus Wärmeerzeugung', fuel_co2))

    if not co2_series:
        return pn.pane.Markdown(
            "*Keine zeitaufgelösten CO2-Äquivalent-Daten verfügbar.*"
        )

    fig = go.Figure()

    total_series = sum(series for _, series in co2_series)

    for name, series in co2_series:
        fig.add_trace(go.Scatter(
            x=df_subset['timestamp'],
            y=series,
            mode='lines',
            name=name,
            stackgroup='one' if len(co2_series) > 1 else None,
            line=dict(width=1),
            hovertemplate='<b>%{fullData.name}</b>: %{y:.4f} t CO2eq<extra></extra>'
        ))

    if len(co2_series) > 1:
        fig.add_trace(go.Scatter(
            x=df_subset['timestamp'],
            y=total_series,
            mode='lines',
            name='═══ GESAMT ═══',
            line=dict(color='black', width=2, dash='dash'),
            hovertemplate='<b>Gesamt-CO2</b>: %{y:.4f} t CO2eq<extra></extra>'
        ))

    total_co2_filtered = sum(series.sum() for _, series in co2_series)
    time_span_h = len(df_subset) * data.dt_h

    fig.update_layout(
        height=400,
        xaxis_title='Zeit',
        yaxis_title=f'CO2-Äquivalente [t / {data.dt_h}h]',
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        title=dict(
            text=f'Zeitraum: {time_span_h:.0f}h | Summe: {total_co2_filtered:.2f} t CO2eq',
            font=dict(size=12),
            x=0.5,
            xanchor='center'
        )
    )

    return pn.pane.Plotly(fig, sizing_mode='stretch_width')
