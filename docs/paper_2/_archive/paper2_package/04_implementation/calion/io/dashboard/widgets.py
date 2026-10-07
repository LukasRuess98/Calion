"""
Reusable widget components for the CALION Dashboard.

Contains interactive controls, filters, and other reusable UI elements.
"""

from __future__ import annotations

import pandas as pd

try:
    import panel as pn
    HAVE_PANEL = True
except ImportError:
    HAVE_PANEL = False
    pn = None


def create_time_range_slider(
    total_hours: int,
    default_range: tuple[int, int] | None = None,
    step: int = 24,
    name: str = 'Zeitbereich (Stunden)'
) -> pn.widgets.IntRangeSlider:
    """
    Create a time range slider widget.

    Parameters
    ----------
    total_hours : int
        Total number of hours in the dataset
    default_range : tuple, optional
        (start, end) default range, defaults to first week
    step : int
        Step size in hours (default: 24)
    name : str
        Widget name/label

    Returns
    -------
    pn.widgets.IntRangeSlider
        Configured time range slider
    """
    if not HAVE_PANEL:
        raise ImportError("Panel is required for widgets")

    if default_range is None:
        default_range = (0, min(168, total_hours))

    return pn.widgets.IntRangeSlider(
        name=name,
        start=0,
        end=total_hours,
        value=default_range,
        step=step,
        sizing_mode='stretch_width'
    )


def create_quick_filter_buttons(
    time_slider: pn.widgets.IntRangeSlider,
    df: pd.DataFrame,
    demand_col: str = 'demand_MW'
) -> pn.Row:
    """
    Create quick filter buttons for time range selection.

    Parameters
    ----------
    time_slider : pn.widgets.IntRangeSlider
        Time slider widget to control
    df : pd.DataFrame
        DataFrame with timestamp and demand data
    demand_col : str
        Name of the demand column

    Returns
    -------
    pn.Row
        Row of quick filter buttons
    """
    if not HAVE_PANEL:
        raise ImportError("Panel is required for widgets")

    total_hours = len(df)

    def set_erste_woche():
        time_slider.value = (0, min(168, total_hours))

    def set_winter_tag():
        if demand_col in df.columns:
            winter_idx = df[demand_col].idxmax()
            start = max(0, winter_idx - 12)
            end = min(total_hours, winter_idx + 36)
            time_slider.value = (start, end)

    def set_sommer_tag():
        if demand_col in df.columns:
            summer_idx = df[demand_col].idxmin()
            start = max(0, summer_idx - 12)
            end = min(total_hours, summer_idx + 36)
            time_slider.value = (start, end)

    def set_komplettes_jahr():
        time_slider.value = (0, total_hours)

    btn_erste_woche = pn.widgets.Button(name='Erste Woche', button_type='primary', width=120)
    btn_winter = pn.widgets.Button(name='Winter-Tag', button_type='default', width=120)
    btn_sommer = pn.widgets.Button(name='Sommer-Tag', button_type='default', width=120)
    btn_jahr = pn.widgets.Button(name='Ganzes Jahr', button_type='success', width=120)

    btn_erste_woche.on_click(lambda event: set_erste_woche())
    btn_winter.on_click(lambda event: set_winter_tag())
    btn_sommer.on_click(lambda event: set_sommer_tag())
    btn_jahr.on_click(lambda event: set_komplettes_jahr())

    return pn.Row(
        pn.pane.Markdown("**Schnellfilter:**"),
        btn_erste_woche,
        btn_winter,
        btn_sommer,
        btn_jahr,
        sizing_mode='stretch_width'
    )


def create_component_selector(
    components: list[str],
    name: str = 'Komponenten',
    default_count: int = 3
) -> pn.widgets.MultiChoice:
    """
    Create a multi-choice selector for components.

    Parameters
    ----------
    components : list
        List of component names
    name : str
        Widget name/label
    default_count : int
        Number of components to select by default

    Returns
    -------
    pn.widgets.MultiChoice
        Configured component selector
    """
    if not HAVE_PANEL:
        raise ImportError("Panel is required for widgets")

    return pn.widgets.MultiChoice(
        name=name,
        options=components,
        value=components[:default_count] if len(components) > 0 else [],
        sizing_mode='stretch_width'
    )


def create_plot_type_selector(
    name: str = 'Plot-Typ',
    options: list[str] | None = None,
    default: str = 'Stacked Area'
) -> pn.widgets.Select:
    """
    Create a plot type selector.

    Parameters
    ----------
    name : str
        Widget name/label
    options : list, optional
        List of plot type options
    default : str
        Default selection

    Returns
    -------
    pn.widgets.Select
        Configured plot type selector
    """
    if not HAVE_PANEL:
        raise ImportError("Panel is required for widgets")

    if options is None:
        options = ['Stacked Area', 'Lines', 'Stacked Bar']

    return pn.widgets.Select(
        name=name,
        options=options,
        value=default
    )


def create_aggregation_selector(
    name: str = 'Aggregation',
    default: str = 'Stündlich'
) -> pn.widgets.Select:
    """
    Create an aggregation level selector.

    Parameters
    ----------
    name : str
        Widget name/label
    default : str
        Default selection

    Returns
    -------
    pn.widgets.Select
        Configured aggregation selector
    """
    if not HAVE_PANEL:
        raise ImportError("Panel is required for widgets")

    return pn.widgets.Select(
        name=name,
        options=['Stündlich', 'Täglich', 'Wöchentlich', 'Monatlich'],
        value=default
    )


def create_control_card(
    *widgets,
    title: str = "Steuerung",
    collapsed: bool = False
) -> pn.Card:
    """
    Create a collapsible card containing control widgets.

    Parameters
    ----------
    *widgets
        Widget elements to include in the card
    title : str
        Card title
    collapsed : bool
        Whether card starts collapsed

    Returns
    -------
    pn.Card
        Card containing the widgets
    """
    if not HAVE_PANEL:
        raise ImportError("Panel is required for widgets")

    return pn.Card(
        *widgets,
        title=title,
        collapsed=collapsed,
        sizing_mode='stretch_width'
    )


def create_warning_message(
    title: str,
    message: str,
    troubleshooting: str | None = None,
    solutions: list[str] | None = None
) -> pn.Column:
    """
    Create a formatted warning message panel.

    Parameters
    ----------
    title : str
        Warning title
    message : str
        Main warning message
    troubleshooting : str, optional
        Troubleshooting code/instructions
    solutions : list, optional
        List of possible solutions

    Returns
    -------
    pn.Column
        Formatted warning panel
    """
    if not HAVE_PANEL:
        raise ImportError("Panel is required for widgets")

    md_content = f"## WARNUNG: {title}\n\n{message}\n\n"

    if troubleshooting:
        md_content += f"**Troubleshooting:**\n```python\n{troubleshooting}\n```\n\n"

    if solutions:
        md_content += "**Mögliche Lösungen:**\n"
        for solution in solutions:
            md_content += f"- {solution}\n"

    return pn.Column(pn.pane.Markdown(md_content))
