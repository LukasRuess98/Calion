"""
Comparison tab for the EnerGIS Dashboard.

Compares PF vs RH vs MPC results.
"""

from __future__ import annotations

from typing import Any, List, Tuple

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
    Create PF vs RH vs MPC comparison tab.

    Supports comparison of all available workflow results:
    - PF vs RH (if both available)
    - PF vs MPC (if both available)
    - PF vs RH vs MPC (if all three available)

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

    # Collect all available results
    results: List[Tuple[str, Any, str]] = []  # (label, result, color)

    if has_pf:
        results.append(("PF", workflow.pf_result, "#4477AA"))

    if has_rh:
        results.append(("RH", workflow.rh_result, "#EE6677"))

    if has_mpc:
        results.append(("MPC", workflow.mpc_result, "#228833"))

    # Extract costs
    costs = {}
    for label, result, _ in results:
        costs[label] = result.costs.get('objective.OBJ_value_EUR', 0)

    pf_cost = costs.get("PF", 0)

    # Build comparison data
    metrics = ['Gesamtkosten', 'Optimality Gap vs PF']
    data = {'Metrik': metrics}

    for label, _, _ in results:
        cost = costs[label]
        gap = ((cost - pf_cost) / pf_cost * 100) if pf_cost > 0 else 0
        data[label] = [
            f"{cost:,.0f} €",
            "-" if label == "PF" else f"{gap:.2f} %"
        ]

    comparison_data = pd.DataFrame(data)

    # Comparison plot
    comp_plot = _create_multi_comparison_plot(results, costs)

    # Table
    comp_table = pn.widgets.Tabulator(
        comparison_data,
        sizing_mode='stretch_width',
        theme='modern',
        show_index=False
    )

    # Interpretation for each non-PF result
    interpretations = []
    for label, _, _ in results:
        if label == "PF":
            continue
        gap = ((costs[label] - pf_cost) / pf_cost * 100) if pf_cost > 0 else 0
        interpretation = _get_gap_interpretation(label, gap)
        interpretations.append(interpretation)

    # Build title based on available results
    labels = [label for label, _, _ in results]
    title = " vs ".join(labels)

    return pn.Column(
        pn.pane.Markdown(f"## {title} Vergleich"),
        comp_plot,
        pn.layout.Divider(),
        pn.pane.Markdown("## Kennzahlen"),
        comp_table,
        pn.layout.Divider(),
        pn.pane.Markdown("## Interpretation"),
        *[pn.pane.Markdown(interp) for interp in interpretations],
        sizing_mode='stretch_width'
    )


def _get_gap_interpretation(label: str, gap: float) -> str:
    """Get interpretation text for a given gap percentage."""
    if gap < 1:
        return f"**{label} - Exzellent:** Gap < 1% - sehr gute operative Planung"
    elif gap < 5:
        return f"**{label} - Gut:** Gap < 5% - akzeptable operative Planung"
    elif gap < 10:
        return f"**{label} - Akzeptabel:** Gap < 10% - Horizont könnte verlängert werden"
    else:
        return f"**{label} - WARNUNG:** Gap > 10% - Horizont zu kurz oder zu viel Unsicherheit"


def _create_multi_comparison_plot(
    results: List[Tuple[str, Any, str]],
    costs: dict
):
    """Create cost comparison plot for multiple methods."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    labels = [label for label, _, _ in results]
    colors = [color for _, _, color in results]
    values = [costs[label] for label in labels]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels,
        y=values,
        marker=dict(color=colors),
        text=[f"{v:,.0f} €" for v in values],
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


# Keep old function for backwards compatibility
def _create_comparison_plot(pf_cost: float, comp_cost: float, comp_label: str):
    """Create cost comparison plot (legacy, 2 methods only)."""
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
