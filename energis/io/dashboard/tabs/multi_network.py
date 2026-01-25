"""
Multi-Network tab for the EnerGIS Dashboard.

Provides visualization for multi-temperature district heating networks
with heat exchangers and cascade coupling.
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


def create_multi_network_tab(
    data: 'DashboardData',
    multi_network_results: Optional[Dict[str, Any]] = None,
) -> 'pn.Column':
    """
    Create multi-network visualization tab.

    Parameters
    ----------
    data : DashboardData
        Prepared dashboard data
    multi_network_results : dict, optional
        Results from MultiNetworkManager.get_results()

    Returns
    -------
    pn.Column
        Multi-network tab content
    """
    if not HAVE_PANEL:
        raise ImportError("Panel required for dashboard")

    # Try to extract multi-network data from various sources
    if multi_network_results is None:
        multi_network_results = _extract_multi_network_from_data(data)

    if multi_network_results is None or not multi_network_results:
        return pn.Column(
            pn.pane.Markdown("## Multi-Netzwerk Analyse"),
            pn.pane.Alert(
                "Keine Multi-Netzwerk-Daten verfügbar. "
                "Diese Ansicht erfordert eine Konfiguration mit mehreren Temperaturnetzen.",
                alert_type="warning"
            ),
            sizing_mode='stretch_width'
        )

    # Network summary cards
    network_cards = _create_network_summary_cards(multi_network_results)

    # Temperature comparison plot
    temp_plot = _create_temperature_comparison_plot(data, multi_network_results)

    # Heat exchanger operation plot
    hx_plot = _create_heat_exchanger_plot(data, multi_network_results)

    # Network coupling diagram
    coupling_diagram = _create_network_coupling_diagram(multi_network_results)

    # Summary table
    summary_table = _create_summary_table(multi_network_results)

    return pn.Column(
        pn.pane.Markdown("## Multi-Temperatur Fernwärmenetz"),
        pn.pane.Markdown(
            "Analyse der gekoppelten Wärmenetze mit unterschiedlichen Temperaturniveaus"
        ),
        pn.layout.Divider(),

        # Network KPI cards
        pn.pane.Markdown("### Netzwerk-Übersicht"),
        network_cards,

        pn.layout.Divider(),

        # Temperature plots
        pn.Row(
            pn.Column(
                pn.pane.Markdown("### Temperaturverläufe"),
                temp_plot,
                width=700
            ),
            pn.Column(
                pn.pane.Markdown("### Netzwerk-Kopplung"),
                coupling_diagram,
                width=350
            ),
        ),

        pn.layout.Divider(),

        # Heat exchanger analysis
        pn.pane.Markdown("### Wärmetauscher-Betrieb"),
        hx_plot,

        pn.layout.Divider(),

        # Summary table
        pn.pane.Markdown("### Zusammenfassung"),
        summary_table,

        sizing_mode='stretch_width'
    )


def _extract_multi_network_from_data(data: 'DashboardData') -> Optional[Dict[str, Any]]:
    """Try to extract multi-network info from dashboard data."""
    result = {'networks': {}, 'heat_exchangers': {}}

    df = data.df

    # Look for network-prefixed columns
    network_prefixes = set()
    for col in df.columns:
        if '_T_supply' in col:
            prefix = col.split('_T_supply')[0]
            if prefix:
                network_prefixes.add(prefix)

    if len(network_prefixes) <= 1:
        return None

    # Build network info from columns
    for prefix in network_prefixes:
        net_info = {'id': prefix, 'name': prefix}

        # Extract temperature info
        supply_col = f'{prefix}_T_supply'
        return_col = f'{prefix}_T_return'

        if supply_col in df.columns:
            net_info['supply_temp_c'] = df[supply_col].mean()
            net_info['supply_temp_max'] = df[supply_col].max()
            net_info['supply_temp_min'] = df[supply_col].min()

        if return_col in df.columns:
            net_info['return_temp_c'] = df[return_col].mean()

        # Look for heat loss columns
        loss_col = f'{prefix}_Q_loss'
        if loss_col in df.columns:
            net_info['total_network_heat_loss_mwh'] = df[loss_col].sum() * data.dt_h

        result['networks'][prefix] = net_info

    # Look for heat exchanger columns
    for col in df.columns:
        if '_Q_transfer' in col:
            hx_prefix = col.replace('_Q_transfer', '')
            result['heat_exchangers'][hx_prefix] = {
                'id': hx_prefix,
                'total_heat_transferred_mwh': df[col].sum() * data.dt_h,
            }

    return result if result['networks'] else None


def _create_network_summary_cards(
    multi_results: Dict[str, Any]
) -> 'pn.GridBox':
    """Create KPI cards for each network."""
    from ..utils import create_kpi_card

    cards = []
    networks = multi_results.get('networks', {})

    for net_id, net_info in networks.items():
        # Network name
        name = net_info.get('name', net_id)[:15]

        # Temperature level indicator
        t_supply = net_info.get('supply_temp_c', 0)
        if t_supply >= 90:
            level = "Hochtemperatur"
            color = "danger"
        elif t_supply >= 60:
            level = "Mitteltemperatur"
            color = "warning"
        else:
            level = "Niedertemperatur (4GDH)"
            color = "success"

        # Main card
        cards.append(create_kpi_card(
            name,
            f"{t_supply:.0f}°C / {net_info.get('return_temp_c', 0):.0f}°C",
            color
        ))

        # Heat loss card
        loss = net_info.get('total_network_heat_loss_mwh', 0)
        cards.append(create_kpi_card(
            f"{name} Verlust",
            f"{loss:,.0f} MWh",
            "secondary"
        ))

    # Heat exchanger cards
    hx_data = multi_results.get('heat_exchangers', {})
    for hx_id, hx_info in hx_data.items():
        transfer = hx_info.get('total_heat_transferred_mwh', 0)
        cards.append(create_kpi_card(
            f"WT: {hx_id[:10]}",
            f"{transfer:,.0f} MWh",
            "info"
        ))

    return pn.GridBox(*cards, ncols=4, sizing_mode='stretch_width')


def _create_temperature_comparison_plot(
    data: 'DashboardData',
    multi_results: Dict[str, Any]
):
    """Create temperature comparison plot for all networks."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    df = data.df
    networks = multi_results.get('networks', {})

    if not networks:
        return pn.pane.Markdown("*Keine Netzwerkdaten*")

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Vorlauftemperaturen', 'Rücklauftemperaturen'),
        shared_xaxes=True,
        vertical_spacing=0.1
    )

    colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00']

    for i, (net_id, net_info) in enumerate(networks.items()):
        color = colors[i % len(colors)]
        name = net_info.get('name', net_id)

        # Supply temperature
        supply_col = f'{net_id}_T_supply'
        if supply_col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['timestamp'],
                    y=df[supply_col],
                    name=f'{name} (Vorlauf)',
                    line=dict(color=color, width=2),
                    legendgroup=net_id,
                ),
                row=1, col=1
            )

        # Return temperature
        return_col = f'{net_id}_T_return'
        if return_col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['timestamp'],
                    y=df[return_col],
                    name=f'{name} (Rücklauf)',
                    line=dict(color=color, width=2, dash='dash'),
                    legendgroup=net_id,
                    showlegend=False,
                ),
                row=2, col=1
            )

    fig.update_layout(
        height=500,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        hovermode='x unified',
    )

    fig.update_yaxes(title_text='Temperatur [°C]', row=1, col=1)
    fig.update_yaxes(title_text='Temperatur [°C]', row=2, col=1)
    fig.update_xaxes(title_text='Zeit', row=2, col=1)

    return pn.pane.Plotly(fig, sizing_mode='stretch_width')


def _create_heat_exchanger_plot(
    data: 'DashboardData',
    multi_results: Dict[str, Any]
):
    """Create heat exchanger operation plot."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    df = data.df
    hx_data = multi_results.get('heat_exchangers', {})

    if not hx_data:
        return pn.pane.Markdown("*Keine Wärmetauscher konfiguriert*")

    fig = go.Figure()

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    for i, (hx_id, hx_info) in enumerate(hx_data.items()):
        color = colors[i % len(colors)]

        # Look for Q_transfer column (try different naming conventions)
        q_col = None
        for col_pattern in [
            f'{hx_id}_Q_transfer',
            f'{hx_id.upper()}_Q_transfer',
            f'{hx_id.upper().replace("-", "_")}_Q_transfer',
        ]:
            if col_pattern in df.columns:
                q_col = col_pattern
                break

        if q_col:
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df[q_col],
                name=hx_id,
                fill='tozeroy',
                line=dict(color=color),
                fillcolor=color.replace(')', ', 0.3)').replace('rgb', 'rgba'),
            ))

    fig.update_layout(
        height=350,
        xaxis_title='Zeit',
        yaxis_title='Wärmeübertragung [MW]',
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        hovermode='x unified',
    )

    return pn.pane.Plotly(fig, sizing_mode='stretch_width')


def _create_network_coupling_diagram(
    multi_results: Dict[str, Any]
) -> 'pn.pane.HTML':
    """Create network coupling diagram as SVG."""
    networks = multi_results.get('networks', {})
    hx_data = multi_results.get('heat_exchangers', {})

    if not networks:
        return pn.pane.Markdown("*Keine Netzwerke*")

    # Build simple SVG diagram
    svg_parts = [
        '<svg viewBox="0 0 300 250" xmlns="http://www.w3.org/2000/svg">',
        '<style>',
        '  .net-box { fill: #f0f0f0; stroke: #333; stroke-width: 2; }',
        '  .high-temp { fill: #ffcccc; }',
        '  .low-temp { fill: #cce5ff; }',
        '  .hx-box { fill: #ffffcc; stroke: #666; stroke-width: 1; }',
        '  .label { font-family: sans-serif; font-size: 12px; }',
        '  .temp { font-family: sans-serif; font-size: 10px; fill: #666; }',
        '  .arrow { stroke: #e63946; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }',
        '</style>',
        '<defs>',
        '  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
        '    <polygon points="0 0, 10 3.5, 0 7" fill="#e63946"/>',
        '  </marker>',
        '</defs>',
    ]

    y_pos = 30
    net_positions = {}

    # Draw networks
    for net_id, net_info in networks.items():
        t_supply = net_info.get('supply_temp_c', 0)
        temp_class = 'high-temp' if t_supply >= 80 else 'low-temp'

        svg_parts.append(
            f'<rect x="20" y="{y_pos}" width="120" height="50" rx="5" '
            f'class="net-box {temp_class}"/>'
        )
        svg_parts.append(
            f'<text x="80" y="{y_pos + 22}" class="label" text-anchor="middle">'
            f'{net_info.get("name", net_id)[:15]}</text>'
        )
        svg_parts.append(
            f'<text x="80" y="{y_pos + 38}" class="temp" text-anchor="middle">'
            f'{t_supply:.0f}°C / {net_info.get("return_temp_c", 0):.0f}°C</text>'
        )

        net_positions[net_id] = y_pos + 25
        y_pos += 70

    # Draw heat exchangers and arrows
    hx_y = 60
    for hx_id, hx_info in hx_data.items():
        prim = hx_info.get('primary_network', '')
        sec = hx_info.get('secondary_network', '')

        # HX box
        svg_parts.append(
            f'<rect x="180" y="{hx_y}" width="80" height="35" rx="3" class="hx-box"/>'
        )
        svg_parts.append(
            f'<text x="220" y="{hx_y + 15}" class="label" text-anchor="middle">'
            f'WT</text>'
        )
        svg_parts.append(
            f'<text x="220" y="{hx_y + 28}" class="temp" text-anchor="middle">'
            f'{hx_id[:8]}</text>'
        )

        # Arrows from primary to HX
        if prim in net_positions:
            prim_y = net_positions[prim]
            svg_parts.append(
                f'<path d="M 140 {prim_y} L 175 {hx_y + 17}" class="arrow"/>'
            )

        # Arrows from HX to secondary
        if sec in net_positions:
            sec_y = net_positions[sec]
            svg_parts.append(
                f'<path d="M 180 {hx_y + 17} L 145 {sec_y}" class="arrow"/>'
            )

        hx_y += 50

    svg_parts.append('</svg>')

    return pn.pane.HTML('\n'.join(svg_parts), width=300, height=250)


def _create_summary_table(
    multi_results: Dict[str, Any]
) -> 'pn.widgets.Tabulator':
    """Create summary table for all networks."""
    networks = multi_results.get('networks', {})
    hx_data = multi_results.get('heat_exchangers', {})

    rows = []

    # Network rows
    for net_id, net_info in networks.items():
        rows.append({
            'Typ': 'Netzwerk',
            'ID': net_id,
            'Name': net_info.get('name', net_id),
            'T_Vorlauf [°C]': f"{net_info.get('supply_temp_c', 0):.1f}",
            'T_Rücklauf [°C]': f"{net_info.get('return_temp_c', 0):.1f}",
            'Verlust [MWh]': f"{net_info.get('total_network_heat_loss_mwh', 0):,.1f}",
        })

    # Heat exchanger rows
    for hx_id, hx_info in hx_data.items():
        rows.append({
            'Typ': 'Wärmetauscher',
            'ID': hx_id,
            'Name': f"{hx_info.get('primary_network', '?')} → {hx_info.get('secondary_network', '?')}",
            'T_Vorlauf [°C]': '-',
            'T_Rücklauf [°C]': '-',
            'Verlust [MWh]': f"{hx_info.get('total_heat_transferred_mwh', 0):,.1f} (Transfer)",
        })

    df = pd.DataFrame(rows)

    return pn.widgets.Tabulator(
        df,
        layout='fit_columns',
        sizing_mode='stretch_width',
        height=200,
    )


def has_multi_network_data(data: 'DashboardData') -> bool:
    """Check if multi-network data is available."""
    df = data.df

    # Look for multiple network-prefixed temperature columns
    network_prefixes = set()
    for col in df.columns:
        if '_T_supply' in col:
            prefix = col.split('_T_supply')[0]
            if prefix:
                network_prefixes.add(prefix)

    return len(network_prefixes) > 1
