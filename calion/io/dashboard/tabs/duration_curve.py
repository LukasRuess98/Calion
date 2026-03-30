"""
Duration curve (Jahresdauerlinie) tab for the CALION Dashboard.
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


def create_duration_curve_tab(data: 'DashboardData') -> 'pn.Column':
    """
    Create load duration curve tab.

    Parameters
    ----------
    data : DashboardData
        Prepared dashboard data

    Returns
    -------
    pn.Column
        Duration curve tab content
    """
    from ..utils import get_component_color

    df = data.df

    if len(df) == 0:
        return pn.Column(pn.pane.Markdown("## WARNUNG: Keine Daten verfügbar"))

    # Calculate duration curves
    demand_sorted = sorted(df['demand_MW'].values, reverse=True)
    hours = list(range(len(demand_sorted)))

    # Heat production per component
    heat_production = {}
    for comp in data.heat_components:
        if comp in df.columns:
            values = sorted(df[comp].values, reverse=True)
            heat_production[comp] = values

    # Create plot
    fig = go.Figure()

    # Heat demand
    fig.add_trace(go.Scatter(
        x=hours,
        y=demand_sorted,
        mode='lines',
        name='Wärmebedarf',
        line=dict(color='red', width=3),
    ))

    # Generators
    for comp, values in heat_production.items():
        comp_name = comp.replace('_Q_th_MW', '')
        fig.add_trace(go.Scatter(
            x=hours,
            y=values,
            mode='lines',
            name=comp_name,
            line=dict(color=get_component_color(comp), width=2),
        ))

    fig.update_layout(
        title='Jahresdauerlinie - Wärmeerzeugung',
        xaxis_title='Betriebsstunden [h]',
        yaxis_title='Leistung [MW]',
        height=600,
        hovermode='x unified',
        legend=dict(x=0.7, y=0.98)
    )

    # Statistics with ORIGINAL data
    total_hours = data.original_timesteps
    peak_demand = data.original_peak_demand_MW
    avg_demand = data.original_total_demand_MWh / total_hours if total_hours > 0 else 0

    # Full load hours (>80% of peak load)
    full_load_threshold = peak_demand * 0.8
    full_load_hours = sum(1 for d in demand_sorted if d >= full_load_threshold)
    if data.downsampled:
        full_load_hours = full_load_hours * data.downsample_factor

    stats_md = f"""
### ■ Statistiken

| Kennzahl | Wert |
|----------|------|
| **Spitzenlast** | {peak_demand:.2f} MW |
| **Durchschnittslast** | {avg_demand:.2f} MW |
| **Auslastungsfaktor** | {(avg_demand/peak_demand*100) if peak_demand > 0 else 0:.1f} % |
| **Volllast-Stunden (>80%)** | {full_load_hours:,} h |
| **Gesamt-Betriebsstunden** | {total_hours:,} h |

**Interpretation:**
- Volllast-Stunden zeigen, wie oft Spitzenlast-Erzeuger benötigt werden
- Niedriger Auslastungsfaktor deutet auf hohe Lastspitzen hin
- Jahresdauerlinie hilft bei der Dimensionierung von Grund- vs. Spitzenlast
"""

    return pn.Column(
        pn.pane.Markdown("## Jahresdauerlinie (Load Duration Curve)"),
        pn.pane.Markdown(
            "*Die Jahresdauerlinie zeigt die sortierte Häufigkeitsverteilung der Lasten. "
            "Sie ist essentiell für die Dimensionierung und zeigt, wie oft bestimmte Lastbereiche auftreten.*"
        ),
        pn.pane.Plotly(fig, sizing_mode='stretch_width'),
        pn.layout.Divider(),
        pn.pane.Markdown(stats_md),
        sizing_mode='stretch_width'
    )
