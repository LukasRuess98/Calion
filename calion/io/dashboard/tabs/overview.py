"""
Overview tab for the CALION Dashboard.

Provides KPI cards and summary statistics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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


def create_overview_tab(
    data: 'DashboardData',
    result: Any,
    workflow: Any,
    primary_label: str
) -> 'pn.Column':
    """
    Create overview tab with KPIs and summary.

    Parameters
    ----------
    data : DashboardData
        Prepared dashboard data
    result : Any
        Primary workflow result
    workflow : Any
        Full workflow object
    primary_label : str
        Label of primary result type (PF/RH/MPC)

    Returns
    -------
    pn.Column
        Overview tab content
    """
    from ..utils import create_kpi_card
    from ..data_preparation import calculate_total_investment

    # KPI Cards
    kpis = _create_kpi_cards(data, result, workflow)

    # Quick stats
    stats_text = _create_stats_summary(data, primary_label)

    # Mini plot
    mini_plot = _create_mini_demand_plot(data)

    return pn.Column(
        pn.pane.Markdown("## Key Performance Indicators"),
        kpis,
        pn.layout.Divider(),
        pn.Row(
            pn.Column(
                pn.pane.Markdown("## Zusammenfassung"),
                stats_text,
                width=400
            ),
            pn.Column(
                pn.pane.Markdown("## Wärmebedarf (Jahresverlauf)"),
                mini_plot,
            ),
        ),
        sizing_mode='stretch_width'
    )


def _create_kpi_cards(
    data: 'DashboardData',
    result: Any,
    workflow: Any
) -> 'pn.GridBox':
    """Create KPI indicator cards."""
    from ..utils import create_kpi_card
    from ..data_preparation import calculate_total_investment

    # Use ORIGINAL sums for KPIs (not downsampled!)
    total_demand_MWh = data.original_total_demand_MWh
    peak_demand_MW = data.original_peak_demand_MW
    total_timesteps = data.original_timesteps

    total_cost = 0
    elec_cost = 0
    fuel_cost = 0
    capex_annualized = 0

    if hasattr(result, 'costs') and result.costs:
        total_cost = result.costs.get('objective.OBJ_value_EUR', 0)
        elec_cost = result.costs.get('objective.Grid_energy_cost_EUR', 0)
        fuel_cost = result.costs.get('objective.Fuel_cost_EUR', 0)
        capex_annualized = result.costs.get('objective.Capex_cost_EUR', 0)

    # Calculate total investment
    total_investment = calculate_total_investment(workflow)

    if total_investment == 0 and capex_annualized > 0:
        import logging
        logging.warning(
            "Dashboard: Kein Design-Objekt verfügbar für Investitionsberechnung. "
            f"Zeige annualisierte CAPEX ({capex_annualized:,.0f} EUR) als Fallback."
        )
        total_investment = capex_annualized

    # Calculate autarky metrics with original sums
    total_heat_production = data.original_total_heat_production
    thermal_autarky = (total_heat_production / total_demand_MWh * 100) if total_demand_MWh > 0 else 0

    # Average utilization with original data
    avg_demand = total_demand_MWh / total_timesteps if total_timesteps > 0 else 0
    load_factor = (avg_demand / peak_demand_MW * 100) if peak_demand_MW > 0 else 0

    # Calculate power metrics (CHP generation, grid feed-in, self-consumption)
    chp_elec_mwh = 0
    p_sell_mwh = 0

    if hasattr(result, 'summary') and result.summary:
        for key, data_dict in result.summary.items():
            if key.startswith('generator_'):
                chp_elec_mwh += data_dict.get('Power_output_MWh', 0)

    if 'P_sell_MW' in data.df.columns:
        p_sell_mwh = data.df['P_sell_MW'].sum() * data.dt_h

    chp_selfuse_mwh = max(0, chp_elec_mwh - p_sell_mwh)
    selfuse_percentage = (chp_selfuse_mwh / chp_elec_mwh * 100) if chp_elec_mwh > 0 else 0

    # Create cards
    cards = pn.GridBox(
        # Row 1: Costs (4 cards)
        create_kpi_card("Gesamtkosten", f"{total_cost:,.0f} €", "primary"),
        create_kpi_card("Stromkosten", f"{elec_cost:,.0f} €", "info"),
        create_kpi_card("Brennstoffkosten", f"{fuel_cost:,.0f} €", "warning"),
        create_kpi_card("Investition (Gesamt)", f"{total_investment:,.0f} €", "success"),

        # Row 2: Heat metrics (4 cards)
        create_kpi_card("Wärmebedarf (Total)", f"{total_demand_MWh:,.0f} MWh", "secondary"),
        create_kpi_card("Spitzenlast", f"{peak_demand_MW:.1f} MW", "danger"),
        create_kpi_card("Thermische Autarkie", f"{thermal_autarky:.1f} %", "success"),
        create_kpi_card("Betriebsstunden", f"{total_timesteps:,} h", "secondary"),

        # Row 3: Power metrics (4 cards)
        create_kpi_card("Strom-Erzeugung (CHP)", f"{chp_elec_mwh:,.0f} MWh", "info"),
        create_kpi_card("Netzeinspeisung", f"{p_sell_mwh:,.0f} MWh", "warning"),
        create_kpi_card("Strom-Eigenverbrauch", f"{chp_selfuse_mwh:,.0f} MWh ({selfuse_percentage:.1f}%)", "success"),
        create_kpi_card("CO₂-Äquivalente", f"{data.total_co2_t:,.1f} t", "danger"),

        ncols=4,
        sizing_mode='stretch_width'
    )

    return cards


def _create_stats_summary(
    data: 'DashboardData',
    primary_label: str
) -> 'pn.pane.Markdown':
    """Create statistics summary text."""
    df = data.df

    # Component stats
    active_hp = len([c for c in data.heat_components if 'HP' in c and df[c].sum() > 1])
    active_gen = len([c for c in data.heat_components if 'HP' not in c and df[c].sum() > 1])
    has_storage = any('TES_SOC' in col for col in df.columns)

    # Energy stats with original sums
    total_heat_generated = data.original_total_heat_production

    # Estimate grid import
    if 'P_buy_MW' in df.columns:
        grid_import = df['P_buy_MW'].sum()
        if data.downsampled:
            grid_import = grid_import * data.downsample_factor
    else:
        grid_import = 0

    summary = f"""
    **Zeitraum:** {df['timestamp'].min()} bis {df['timestamp'].max()}

    **Anzahl Zeitschritte:** {data.original_timesteps:,}

    **Aktive Komponenten:**
    - Wärmepumpen: {active_hp}
    - Andere Erzeuger: {active_gen}
    - Thermischer Speicher: {'Ja' if has_storage else 'Nein'}

    **Energiebilanz:**
    - Wärmeerzeugung: {total_heat_generated:,.0f} MWh
    - Netzbezug: {grid_import:,.0f} MWh

    **Workflow-Modus:** {primary_label}
    """

    return pn.pane.Markdown(summary)


def _create_mini_demand_plot(data: 'DashboardData'):
    """Create mini demand plot for overview."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=data.df['timestamp'],
        y=data.df['demand_MW'],
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
