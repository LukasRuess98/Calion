"""
Energy flows (Sankey) tab for the EnerGIS Dashboard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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


def create_sankey_tab(data: 'DashboardData') -> 'pn.Column':
    """
    Create Sankey diagram tab for energy flows.

    Parameters
    ----------
    data : DashboardData
        Prepared dashboard data

    Returns
    -------
    pn.Column
        Energy flows tab content
    """
    df = data.df

    if len(df) == 0 or not data.heat_components:
        return pn.Column(
            pn.pane.Markdown("## WARNUNG: Keine Daten verfügbar für Energiefluss-Diagramm")
        )

    # Create heat Sankey
    heat_sankey_fig = _create_heat_sankey(data)
    heat_stats_md = _create_heat_stats(data)

    # Create electricity Sankey
    elec_sankey = _create_electricity_sankey(data)

    return pn.Column(
        pn.pane.Markdown("## Wärme-Energiefluss (Sankey)"),
        pn.pane.Markdown(
            "*Das Sankey-Diagramm visualisiert die Energieströme von den Erzeugern zum Wärmenetz. "
            "Die Breite der Flüsse entspricht der übertragenen Energiemenge.*"
        ),
        heat_sankey_fig,
        pn.layout.Divider(),
        pn.pane.Markdown(heat_stats_md),
        pn.layout.Divider(),
        elec_sankey,
        sizing_mode='stretch_width'
    )


def _create_heat_sankey(data: 'DashboardData'):
    """Create heat Sankey diagram."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    df = data.df
    nodes = []
    links = []
    node_indices = {}

    # Node 0: Heat network (target)
    nodes.append("Wärmenetz")
    node_indices["Wärmenetz"] = 0

    # Heat generators as sources
    idx = 1
    total_production = {}

    for comp in data.heat_components:
        if comp in df.columns:
            total = df[comp].sum()
            if total > 0.01:
                comp_name = comp.replace('_Q_th_MW', '')
                nodes.append(comp_name)
                node_indices[comp_name] = idx
                total_production[comp_name] = total
                idx += 1

    # Create links from generators to heat network
    for comp_name, total in total_production.items():
        links.append({
            'source': node_indices[comp_name],
            'target': 0,
            'value': total
        })

    if not links:
        return pn.pane.Markdown(
            "## WARNUNG: Keine Energieflüsse erkannt\n\n"
            "Möglicherweise sind alle Komponenten inaktiv oder die Werte zu gering."
        )

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

    return pn.pane.Plotly(fig, sizing_mode='stretch_width')


def _create_heat_stats(data: 'DashboardData') -> str:
    """Create heat statistics markdown."""
    total_demand = data.original_total_demand_MWh
    total_gen = data.original_total_heat_production

    stats_md = f"""
### Energie-Bilanz

| Kennzahl | Wert |
|----------|------|
| **Gesamt-Wärmebedarf** | {total_demand:,.0f} MWh |
| **Gesamt-Erzeugung** | {total_gen:,.0f} MWh |
| **Bilanz** | {(total_gen - total_demand):,.0f} MWh ({((total_gen/total_demand - 1)*100) if total_demand > 0 else 0:.1f}%) |

### Erzeugung nach Quelle
"""

    sorted_prod = sorted(data.original_heat_production.items(), key=lambda x: x[1], reverse=True)
    for comp_full, value in sorted_prod:
        comp = comp_full.replace('_Q_th_MW', '')
        percentage = (value / total_gen * 100) if total_gen > 0 else 0
        stats_md += f"- **{comp}**: {value:,.0f} MWh ({percentage:.1f}%)\n"

    return stats_md


def _create_electricity_sankey(data: 'DashboardData'):
    """Create Sankey diagram for electricity flows."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    df = data.df

    if len(df) == 0:
        return pn.pane.Markdown("*Keine Stromdaten verfügbar*")

    sources = {}
    consumers = {}

    # Grid import
    if 'P_buy_MW' in df.columns:
        p_buy_mwh = df['P_buy_MW'].sum() * data.dt_h
        if p_buy_mwh > 0.01:
            sources['Netz (Bezug)'] = p_buy_mwh

    # Collect all _Pel_MW columns
    for col in df.columns:
        if '_Pel_MW' in col:
            component_name = col.replace('_Pel_MW', '')
            pel_mwh = df[col].sum() * data.dt_h

            if pel_mwh < 0.01:
                continue

            if component_name.startswith('HP') or component_name == 'P2H':
                consumers[component_name] = pel_mwh
            else:
                sources[component_name] = pel_mwh

    # Grid feed-in
    if 'P_sell_MW' in df.columns:
        p_sell_mwh = df['P_sell_MW'].sum() * data.dt_h
        if p_sell_mwh > 0.01:
            consumers['Netz (Einspeisung)'] = p_sell_mwh

    if not sources and not consumers:
        return pn.pane.Markdown("*Keine relevanten Stromflüsse erkannt*")

    # Create Sankey structure
    nodes = []
    links = []
    node_indices = {}
    idx = 0

    for source_name in sources.keys():
        nodes.append(source_name)
        node_indices[source_name] = idx
        idx += 1

    for consumer_name in consumers.keys():
        nodes.append(consumer_name)
        node_indices[consumer_name] = idx
        idx += 1

    # Create links proportionally
    total_sources = sum(sources.values())
    total_consumers = sum(consumers.values())

    for source_name, source_value in sources.items():
        for consumer_name, consumer_value in consumers.items():
            if total_consumers > 0:
                flow_value = source_value * (consumer_value / total_consumers)
                if flow_value > 0.01:
                    links.append({
                        'source': node_indices[source_name],
                        'target': node_indices[consumer_name],
                        'value': flow_value
                    })

    if not links:
        return pn.pane.Markdown("*Keine Stromflüsse erkannt*")

    num_sources = len(sources)
    source_colors = ['#4477AA'] * num_sources
    consumer_colors = ['#EE6677'] * len(consumers)
    node_colors = source_colors + consumer_colors

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=nodes,
            color=node_colors
        ),
        link=dict(
            source=[l['source'] for l in links],
            target=[l['target'] for l in links],
            value=[l['value'] for l in links],
            color='rgba(68, 119, 170, 0.3)'
        )
    )])

    fig.update_layout(
        title='Strom-Energiefluss (Quellen → Verbraucher)',
        font=dict(size=12),
        height=600
    )

    # Statistics
    stats_md = f"""
### Strom-Bilanz

| Kennzahl | Wert |
|----------|------|
| **Gesamt-Strombezug** | {sum(sources.values()):,.0f} MWh |
| **Gesamt-Stromverbrauch** | {sum(consumers.values()):,.0f} MWh |
| **Bilanz** | {(sum(sources.values()) - sum(consumers.values())):,.0f} MWh |

### Stromquellen
"""
    for source, value in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        percentage = (value / sum(sources.values()) * 100) if sum(sources.values()) > 0 else 0
        stats_md += f"- **{source}**: {value:,.0f} MWh ({percentage:.1f}%)\n"

    stats_md += "\n### Stromverbraucher\n"
    for consumer, value in sorted(consumers.items(), key=lambda x: x[1], reverse=True):
        percentage = (value / sum(consumers.values()) * 100) if sum(consumers.values()) > 0 else 0
        stats_md += f"- **{consumer}**: {value:,.0f} MWh ({percentage:.1f}%)\n"

    return pn.Column(
        pn.pane.Markdown("## Strom-Energiefluss (Sankey)"),
        pn.pane.Markdown(
            "*Das Sankey-Diagramm visualisiert die Stromflüsse von den Quellen (Netz, Generatoren) "
            "zu den Verbrauchern (Wärmepumpen, P2H, Netzeinspeisung).*"
        ),
        pn.pane.Plotly(fig, sizing_mode='stretch_width'),
        pn.layout.Divider(),
        pn.pane.Markdown(stats_md),
        sizing_mode='stretch_width'
    )
