"""
Design/Capacity tab for the EnerGIS Dashboard.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

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
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False
    go = None


def create_design_tab(workflow: Any) -> 'pn.Column':
    """
    Create design/capacity tab.

    Parameters
    ----------
    workflow : Any
        Workflow object with design attribute

    Returns
    -------
    pn.Column
        Design tab content
    """
    from ..widgets import create_warning_message

    design = workflow.design

    if not design:
        return create_warning_message(
            "Kein Anlagen-Design verfügbar",
            "Das Workflow enthält keine Design-Informationen.",
            troubleshooting=(
                "print('Workflow plan:', workflow.plan.steps)\n"
                "print('Design available:', workflow.design is not None)\n"
                "if workflow.design:\n"
                "    print('Heat pumps:', workflow.design.heat_pumps)\n"
                "    print('Storage:', workflow.design.storage)"
            ),
            solutions=[
                "Führe einen PF-Schritt aus (workflow: ['PF', 'RH'])",
                "Oder lade ein bestehendes Design (pf_design_json: 'path/to/design.json')"
            ]
        )

    # Heat pump capacities
    hp_data = []
    if design.heat_pumps:
        for hp_id, hp_info in design.heat_pumps.items():
            capacity = hp_info.get('capacity_mw', 0.0)
            hp_data.append({
                'Komponente': hp_id,
                'Kapazität [MW]': capacity,
                'Typ': 'Wärmepumpe'
            })

    # Storage capacity
    if design.storage:
        storage_cap = design.storage.get('capacity_mwh', 0.0)
        hp_data.append({
            'Komponente': 'Thermischer Speicher',
            'Kapazität [MW]': storage_cap,
            'Typ': 'Speicher'
        })

    if not hp_data:
        return pn.Column(
            pn.pane.Markdown(
                "## WARNUNG: Keine Komponenten im Design gefunden\n\n"
                "Das Design-Objekt existiert, aber enthält keine Wärmepumpen oder Speicher."
            )
        )

    design_df = pd.DataFrame(hp_data)

    # Capacity plot
    capacity_plot = _create_capacity_plot(design_df)

    # Design table
    design_table = pn.widgets.Tabulator(
        design_df,
        sizing_mode='stretch_width',
        theme='modern',
        show_index=False,
        formatters={
            'Kapazität [MW]': {'type': 'money', 'decimal': '.', 'thousand': ',', 'precision': 2}
        }
    )

    # Export design as JSON
    design_json = json.dumps({
        'heat_pumps': design.heat_pumps,
        'storage': design.storage
    }, indent=2, default=str)

    json_pane = pn.pane.JSON(design_json, sizing_mode='stretch_width', depth=2)

    return pn.Column(
        pn.pane.Markdown("## Anlagenauslegung"),
        capacity_plot,
        pn.layout.Divider(),
        pn.pane.Markdown("## Kapazitätstabelle"),
        design_table,
        pn.layout.Divider(),
        pn.pane.Markdown("## Design-Details (JSON)"),
        json_pane,
        sizing_mode='stretch_width'
    )


def _create_capacity_plot(design_df: pd.DataFrame):
    """Create capacity bar chart."""
    if not HAVE_PLOTLY:
        return pn.pane.Markdown("*Plotly nicht verfügbar*")

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=design_df['Komponente'],
        y=design_df['Kapazität [MW]'],
        marker=dict(
            color=['#4477AA' if t == 'Wärmepumpe' else '#EE6677'
                   for t in design_df['Typ']]
        ),
        text=[f"{v:.2f} MW" for v in design_df['Kapazität [MW]']],
        textposition='auto',
    ))

    fig.update_layout(
        height=400,
        xaxis_title='',
        yaxis_title='Kapazität [MW / MWh]',
        showlegend=False
    )

    return pn.pane.Plotly(fig, sizing_mode='stretch_width')
