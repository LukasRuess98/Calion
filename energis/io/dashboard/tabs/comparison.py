"""
Comparison tab for the EnerGIS Dashboard.

Compares PF vs RH/MPC results.
"""

from __future__ import annotations

from typing import Any

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


def create_comparison_tab(
    workflow: Any,
    has_pf: bool,
    has_rh: bool,
    has_mpc: bool
) -> 'pn.Column':
    """
    Create PF vs RH/MPC comparison tab.

    Parameters
    ----------
    workflow : Any
        Workflow object
    has_pf : bool
        Whether PF result exists
    has_rh : bool
        Whether RH result exists
    has_mpc : bool
        Whether MPC result exists

    Returns
    -------
    pn.Column
        Comparison tab content
    """
    if not (has_pf and (has_rh or has_mpc)):
        return pn.Column(
            pn.pane.Markdown("*Nicht genügend Ergebnisse für Vergleich*")
        )

    pf_result = workflow.pf_result
    comp_result = workflow.rh_result if has_rh else workflow.mpc_result
    comp_label = "RH" if has_rh else "MPC"

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
    comp_plot = _create_comparison_plot(pf_cost, comp_cost, comp_label)

    # Table
    comp_table = pn.widgets.Tabulator(
        comparison_data,
        sizing_mode='stretch_width',
        theme='modern',
        show_index=False
    )

    # Interpretation
    if gap < 1:
        interpretation = "**Exzellent:** Gap < 1% - sehr gute operative Planung"
    elif gap < 5:
        interpretation = "**Gut:** Gap < 5% - akzeptable operative Planung"
    elif gap < 10:
        interpretation = "**Akzeptabel:** Gap < 10% - Horizont könnte verlängert werden"
    else:
        interpretation = "**WARNUNG - Hoch:** Gap > 10% - Horizont zu kurz oder zu viel Unsicherheit"

    return pn.Column(
        pn.pane.Markdown(f"## PF vs {comp_label} Vergleich"),
        comp_plot,
        pn.layout.Divider(),
        pn.pane.Markdown("## Kennzahlen"),
        comp_table,
        pn.layout.Divider(),
        pn.pane.Markdown("## Interpretation"),
        pn.pane.Markdown(interpretation),
        sizing_mode='stretch_width'
    )


def _create_comparison_plot(pf_cost: float, comp_cost: float, comp_label: str):
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
