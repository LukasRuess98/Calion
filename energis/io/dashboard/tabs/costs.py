"""
Costs analysis tab for the EnerGIS Dashboard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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


def create_costs_tab(data: 'DashboardData') -> 'pn.Column':
    """
    Create costs analysis tab.

    Parameters
    ----------
    data : DashboardData
        Prepared dashboard data

    Returns
    -------
    pn.Column
        Costs tab content
    """
    from ..widgets import create_warning_message

    if data.costs_df.empty:
        return create_warning_message(
            "Keine Kostendaten verfügbar",
            "Das Workflow-Ergebnis enthält keine Kostendaten.",
            troubleshooting=(
                "primary_result = workflow.rh_result or workflow.pf_result\n"
                "print('Costs available:', primary_result.costs)\n"
                "print('EUR entries:', [k for k in primary_result.costs.keys() if '_EUR' in k])"
            ),
            solutions=[
                "Aktiviere Kostenberechnung in der Konfiguration",
                "Prüfe ob die Optimierung erfolgreich durchgelaufen ist"
            ]
        )

    # Cost breakdown plot
    cost_plot = _create_cost_breakdown_plot(data.costs_df)

    # Interactive cost table
    cost_table = pn.widgets.Tabulator(
        data.costs_df[['Category', 'Value_EUR', 'Percentage']],
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
    total_cost = data.costs_df['Value_EUR'].sum()
    top_3 = data.costs_df.head(3)

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
                pn.pane.Markdown("## Kostenaufteilung"),
                cost_plot,
            ),
            pn.Column(
                pn.pane.Markdown("## Zusammenfassung"),
                pn.pane.Markdown(summary),
                width=300
            ),
        ),
        pn.layout.Divider(),
        pn.pane.Markdown("## Detaillierte Kostentabelle"),
        cost_table,
        sizing_mode='stretch_width'
    )


def _create_cost_breakdown_plot(costs_df: pd.DataFrame):
    """Create cost breakdown bar chart."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    df_top = costs_df.head(10)

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
