"""
Efficiency and COP analysis tab for the EnerGIS Dashboard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

try:
    import panel as pn
    from panel.widgets import Tabulator
    HAVE_PANEL = True
except ImportError:
    HAVE_PANEL = False
    pn = None
    Tabulator = None

try:
    import plotly.graph_objects as go
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False
    go = None

if TYPE_CHECKING:
    from ..data_preparation import DashboardData


def create_efficiency_tab(data: 'DashboardData') -> 'pn.Column':
    """
    Create efficiency and COP analysis tab with input/output comparison.

    Parameters
    ----------
    data : DashboardData
        Prepared dashboard data

    Returns
    -------
    pn.Column
        Efficiency tab content
    """
    df = data.df

    if len(df) == 0:
        return pn.Column(pn.pane.Markdown("## WARNUNG: Keine Daten verfügbar"))

    # Find COP columns
    cop_cols = [col for col in df.columns if col.endswith('_COP')]
    cop_input_cols = [col for col in df.columns if col.endswith('_COP_input')]
    wrg_ratio_cols = [col for col in df.columns if col.endswith('_WRG_ratio')]

    if not cop_cols:
        return pn.Column(
            pn.pane.Markdown(
                "## WARNUNG: Keine COP-Daten verfügbar\n\n"
                "Es wurden keine COP (Coefficient of Performance) Daten in den Ergebnissen gefunden.\n\n"
                f"**Verfügbare Spalten:**\n"
                f"```\n{', '.join(list(df.columns)[:20])}...\n```\n\n"
                "**Hinweis:** COP-Daten werden möglicherweise nicht in den series exportiert."
            )
        )

    elements = [pn.pane.Markdown("## η Effizienz & COP Analyse")]

    # === COP Comparison: Input vs Calculated ===
    if cop_input_cols:
        fig_cop_comparison, warnings = _create_cop_comparison_plot(df, cop_cols)

        comparison_md = """
### COP Vergleich: Input vs Berechnet

- **Input COP**: Der COP-Wert, der als Parameter in die Optimierung eingeht (basierend auf Temperatur)
- **Berechneter COP**: Der tatsächliche COP aus den Optimierungsergebnissen (Q_th / P_el)

Bei reiner WRG-Nutzung (ohne Fallback) sollten beide Werte übereinstimmen.
Abweichungen entstehen, wenn der Optimizer Fallback-Wärme (Q_def) mit COP_default nutzt.
"""
        elements.append(pn.pane.Markdown(comparison_md))

        if warnings:
            warning_md = "### ⚠️ COP-Abweichungen erkannt\n\n" + "\n".join(f"- {w}" for w in warnings)
            warning_md += "\n\n**Ursache:** Der Optimizer nutzt teilweise Fallback-Wärme (Q_def) mit konstantem COP_default."
            elements.append(pn.pane.Markdown(warning_md))

        elements.append(pn.pane.Plotly(fig_cop_comparison, sizing_mode='stretch_width'))
        elements.append(pn.layout.Divider())

    # === WRG Ratio Analysis ===
    if wrg_ratio_cols:
        fig_wrg = _create_wrg_ratio_plot(df, wrg_ratio_cols)

        wrg_md = """
### WRG-Verhältnis (Waste Recovery Ratio)

Zeigt den Anteil der Wärme, die über Waste Recovery (WRG) mit variablem COP bereitgestellt wird.
- **100%**: Gesamte Wärme kommt aus WRG (COP = COP_input)
- **< 100%**: Teil der Wärme kommt aus Fallback (Q_def) mit COP_default
"""
        elements.append(pn.pane.Markdown(wrg_md))
        elements.append(pn.pane.Plotly(fig_wrg, sizing_mode='stretch_width'))
        elements.append(pn.layout.Divider())

    # === COP Statistics Table ===
    cop_stats_df, fig_cop_box = _create_cop_statistics(df, cop_cols)

    if cop_stats_df is not None:
        stats_md = """
### COP Statistiken

Die folgende Tabelle zeigt die statistischen Kennwerte für die Wärmepumpen-Performance.

**Hinweis:** Nur aktive Betriebsstunden werden berücksichtigt (COP > 0).
"""
        formatters = {
            'COP (berechnet)': {'type': 'money', 'symbol': '', 'precision': 2},
            'COP (Input)': {'type': 'money', 'symbol': '', 'precision': 2},
            'Min': {'type': 'money', 'symbol': '', 'precision': 2},
            'Max': {'type': 'money', 'symbol': '', 'precision': 2},
            'Betriebsstunden': {'type': 'money', 'symbol': '', 'precision': 0},
            'Abweichung [%]': {'type': 'money', 'symbol': '', 'precision': 1},
            'WRG-Anteil [%]': {'type': 'money', 'symbol': '', 'precision': 1},
        }
        stats_table = Tabulator(
            cop_stats_df,
            formatters=formatters,
            show_index=False,
            theme='modern',
            sizing_mode='stretch_width'
        )

        elements.append(pn.pane.Markdown(stats_md))
        elements.append(stats_table)
        elements.append(pn.layout.Divider())
        elements.append(pn.pane.Markdown("### COP Verteilung"))
        elements.append(pn.pane.Plotly(fig_cop_box, sizing_mode='stretch_width'))

        return pn.Column(*elements, sizing_mode='stretch_width')

    return pn.Column(pn.pane.Markdown("## WARNUNG: Keine COP-Statistiken verfügbar"))


def _create_cop_comparison_plot(df: pd.DataFrame, cop_cols: list):
    """Create COP comparison plot (input vs calculated)."""
    fig = go.Figure()
    warnings = []

    for cop_col in cop_cols:
        comp_name = cop_col.replace('_COP', '')
        cop_input_col = f"{comp_name}_COP_input"

        if cop_input_col in df.columns:
            calc_values = df[cop_col].dropna()
            calc_values = calc_values[calc_values > 0]

            input_values = df[cop_input_col].dropna()
            input_values = input_values[input_values > 0]

            if len(calc_values) > 0:
                fig.add_trace(go.Scatter(
                    x=list(range(len(df))),
                    y=df[cop_col],
                    mode='lines',
                    name=f'{comp_name} (berechnet)',
                    line=dict(width=2)
                ))

            if len(input_values) > 0:
                fig.add_trace(go.Scatter(
                    x=list(range(len(df))),
                    y=df[cop_input_col],
                    mode='lines',
                    name=f'{comp_name} (Input)',
                    line=dict(width=2, dash='dash')
                ))

            # Check for significant deviation
            if len(calc_values) > 0 and len(input_values) > 0:
                avg_calc = calc_values.mean()
                avg_input = input_values.mean()
                if avg_input > 0:
                    deviation_pct = abs(avg_calc - avg_input) / avg_input * 100
                    if deviation_pct > 5:
                        warnings.append(
                            f"**{comp_name}**: COP-Abweichung von {deviation_pct:.1f}% "
                            f"(Input: {avg_input:.2f}, Berechnet: {avg_calc:.2f})"
                        )

    fig.update_layout(
        title='COP Vergleich: Input vs Berechnet',
        xaxis_title='Zeitschritt',
        yaxis_title='COP [-]',
        height=400,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig, warnings


def _create_wrg_ratio_plot(df: pd.DataFrame, wrg_ratio_cols: list):
    """Create WRG ratio plot."""
    fig = go.Figure()

    for wrg_col in wrg_ratio_cols:
        comp_name = wrg_col.replace('_WRG_ratio', '')
        values = df[wrg_col].dropna()
        values = values[(values >= 0) & (values <= 1)]

        if len(values) > 0:
            fig.add_trace(go.Scatter(
                x=list(range(len(df))),
                y=df[wrg_col] * 100,
                mode='lines',
                name=comp_name,
                line=dict(width=2),
                fill='tozeroy'
            ))

    fig.update_layout(
        title='WRG-Anteil über Zeit (Waste Recovery Ratio)',
        xaxis_title='Zeitschritt',
        yaxis_title='WRG-Anteil [%]',
        yaxis=dict(range=[0, 105]),
        height=350,
        hovermode='x unified'
    )

    return fig


def _create_cop_statistics(df: pd.DataFrame, cop_cols: list):
    """Create COP statistics table and box plot."""
    cop_stats = []

    for cop_col in cop_cols:
        comp_name = cop_col.replace('_COP', '')
        values = df[cop_col].dropna()
        values = values[values > 0]

        if len(values) > 0:
            stat_entry = {
                'Komponente': comp_name,
                'COP (berechnet)': values.mean(),
                'Min': values.min(),
                'Max': values.max(),
                'Betriebsstunden': len(values)
            }

            cop_input_col = f"{comp_name}_COP_input"
            if cop_input_col in df.columns:
                input_values = df[cop_input_col].dropna()
                input_values = input_values[input_values > 0]
                if len(input_values) > 0:
                    stat_entry['COP (Input)'] = input_values.mean()
                    stat_entry['Abweichung [%]'] = (
                        abs(values.mean() - input_values.mean()) / input_values.mean() * 100
                        if input_values.mean() > 0 else 0
                    )

            wrg_col = f"{comp_name}_WRG_ratio"
            if wrg_col in df.columns:
                wrg_values = df[wrg_col].dropna()
                wrg_values = wrg_values[(wrg_values >= 0) & (wrg_values <= 1)]
                if len(wrg_values) > 0:
                    stat_entry['WRG-Anteil [%]'] = wrg_values.mean() * 100

            cop_stats.append(stat_entry)

    if not cop_stats:
        return None, None

    cop_stats_df = pd.DataFrame(cop_stats)

    # Box plot
    fig_cop_box = go.Figure()

    for cop_col in cop_cols:
        comp_name = cop_col.replace('_COP', '')
        values = df[cop_col].dropna()
        values = values[values > 0]

        fig_cop_box.add_trace(go.Box(
            y=values,
            name=comp_name,
            boxmean='sd'
        ))

    fig_cop_box.update_layout(
        title='COP Verteilung (Box-Plot)',
        yaxis_title='COP [-]',
        height=400,
        showlegend=True
    )

    return cop_stats_df, fig_cop_box
