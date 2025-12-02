"""
Interactive browser for saved workflow simulations.

This module provides a Panel-based dashboard that allows browsing and
visualizing previously saved workflow results from saved_workflows/.

Usage:
    from energis.io.workflow_browser import create_workflow_browser

    browser = create_workflow_browser(saved_workflows_dir="saved_workflows")
    browser.show()  # Or use: panel serve notebook.ipynb --show
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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

__all__ = ["create_workflow_browser", "HAVE_PANEL", "HAVE_PLOTLY"]

logger = logging.getLogger(__name__)


def create_workflow_browser(
    saved_workflows_dir: str = "saved_workflows",
    title: str = "EnerGIS Workflow Browser"
) -> Any:
    """
    Create an interactive browser for saved workflow simulations.

    This creates a Panel dashboard with:
    - Dropdown to select saved simulations
    - All standard dashboard tabs (Overview, Zeitreihen, Kosten, Anlagen)
    - Access to CSV timeseries and exported plots
    - Comparison between multiple simulations

    Parameters
    ----------
    saved_workflows_dir : str
        Directory containing saved workflows (default: "saved_workflows")
    title : str
        Browser title

    Returns
    -------
    pn.Column
        Panel browser dashboard

    Examples
    --------
    >>> from energis.io.workflow_browser import create_workflow_browser
    >>> browser = create_workflow_browser()
    >>> browser  # Display in Jupyter

    Or serve as webapp:
    >>> import panel as pn
    >>> browser = create_workflow_browser()
    >>> pn.serve(browser, port=5007, show=True)
    """

    if not HAVE_PANEL:
        raise ImportError(
            "Panel is required for workflow browser. Install with: pip install panel holoviews bokeh"
        )

    # Initialize Panel
    pn.extension('plotly', 'tabulator', sizing_mode='stretch_width')

    # Create browser instance
    browser = WorkflowBrowser(saved_workflows_dir, title)

    return browser.create()


class WorkflowBrowser:
    """Interactive browser for saved workflows."""

    def __init__(self, saved_workflows_dir: str, title: str):
        self.saved_workflows_dir = Path(saved_workflows_dir)
        self.title = title

        # Scan for available workflows
        self.available_workflows = self._scan_workflows()

        if not self.available_workflows:
            logger.warning(f"No workflows found in {saved_workflows_dir}")

        # Current selection
        self.current_workflow = None
        self.current_workflow_data = None

    def _scan_workflows(self) -> List[Dict[str, Any]]:
        """Scan saved_workflows directory for available simulations."""

        if not self.saved_workflows_dir.exists():
            logger.warning(f"Directory {self.saved_workflows_dir} does not exist")
            return []

        workflows = []

        for workflow_dir in self.saved_workflows_dir.iterdir():
            if not workflow_dir.is_dir():
                continue

            # Check for metadata.json
            metadata_file = workflow_dir / 'metadata.json'

            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)

                    # Extrahiere Daten mit Fallbacks
                    name = metadata.get('name', workflow_dir.name)
                    saved_at = metadata.get('saved_at', '')

                    # Szenario-Name aus verschachtelter Struktur
                    scenario_data = metadata.get('scenario', {})
                    if isinstance(scenario_data, dict):
                        scenario = scenario_data.get('name', scenario_data.get('title', 'unknown'))
                    else:
                        scenario = 'unknown'

                    # Kosten aus costs-Dictionary
                    costs_data = metadata.get('costs', {})
                    if isinstance(costs_data, dict):
                        costs = costs_data.get('total_eur', 0.0)
                    else:
                        costs = 0.0

                    # Steps aus workflow-Dictionary
                    workflow_data = metadata.get('workflow', {})
                    if isinstance(workflow_data, dict):
                        steps = workflow_data.get('steps', [])
                    else:
                        steps = []

                    workflows.append({
                        'path': workflow_dir,
                        'name': name,
                        'date': saved_at,
                        'scenario': scenario,
                        'costs': costs,
                        'steps': steps,
                        'metadata': metadata
                    })
                except Exception as e:
                    logger.warning(f"Failed to load metadata from {metadata_file}: {e}")
            else:
                # Fallback: use directory name
                workflows.append({
                    'path': workflow_dir,
                    'name': workflow_dir.name,
                    'date': '',
                    'scenario': 'unknown',
                    'costs': 0.0,
                    'steps': [],
                    'metadata': {}
                })

        # Sort by date (newest first)
        workflows.sort(key=lambda w: w['date'], reverse=True)

        return workflows

    def _load_workflow(self, workflow_info: Dict[str, Any]) -> Optional[Any]:
        """Load workflow from saved_workflows directory."""

        from energis.io.notebook_helpers import load_workflow_from_saved

        try:
            workflow = load_workflow_from_saved(workflow_info['path'], verbose=False)
            logger.info(f"Loaded workflow: {workflow_info['name']}")
            return workflow
        except Exception as e:
            logger.error(f"Failed to load workflow {workflow_info['name']}: {e}")
            return None

    def _load_timeseries_csv(self, workflow_info: Dict[str, Any], result_type: str = 'rh') -> Optional[pd.DataFrame]:
        """Load timeseries CSV for a workflow."""

        csv_file = workflow_info['path'] / f'{result_type}_timeseries.csv'

        if not csv_file.exists():
            logger.warning(f"CSV not found: {csv_file}")
            return None

        try:
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            logger.info(f"Loaded {result_type} timeseries: {len(df)} rows, {len(df.columns)} columns")
            return df
        except Exception as e:
            logger.error(f"Failed to load CSV {csv_file}: {e}")
            return None

    def create(self) -> pn.Column:
        """Create the browser dashboard."""

        if not self.available_workflows:
            return pn.Column(
                pn.pane.Markdown(f"# {self.title}"),
                pn.pane.Markdown(
                    f"## ⚠️ Keine gespeicherten Workflows gefunden\n\n"
                    f"Verzeichnis: `{self.saved_workflows_dir}`\n\n"
                    f"**Erstelle Workflows mit:**\n"
                    f"- `notebooks/scenario_studio.ipynb`\n"
                    f"- `notebooks/runner.ipynb`\n\n"
                    f"Workflows werden automatisch in `saved_workflows/` gespeichert."
                )
            )

        # Header - kompakter
        header = pn.pane.Markdown(
            f"# {self.title}\n"
            f"📦 **{len(self.available_workflows)} gespeicherte Simulationen gefunden**"
        )

        # Workflow selector dropdown
        workflow_options = {
            f"{wf['name']} ({wf['date'][:10] if wf['date'] else 'no date'})": i
            for i, wf in enumerate(self.available_workflows)
        }

        workflow_selector = pn.widgets.Select(
            name='🔍 Simulation auswählen',
            options=workflow_options,
            width=600
        )

        # Refresh button
        refresh_button = pn.widgets.Button(
            name='🔄 Aktualisieren',
            button_type='success',
            width=150
        )

        # Status indicator for refresh
        refresh_status = pn.pane.Markdown("", width=200)

        # Refresh callback
        def on_refresh(event):
            """Rescan workflows and update dropdown."""
            refresh_status.object = "🔄 Aktualisiere..."

            # Rescan workflows
            self.available_workflows = self._scan_workflows()

            # Update dropdown options
            new_options = {
                f"{wf['name']} ({wf['date'][:10] if wf['date'] else 'no date'})": i
                for i, wf in enumerate(self.available_workflows)
            }
            workflow_selector.options = new_options

            # Update status
            refresh_status.object = f"✅ {len(self.available_workflows)} Simulationen gefunden"

            # Clear status after 3 seconds
            import time
            import threading
            def clear_status():
                time.sleep(3)
                refresh_status.object = ""
            threading.Thread(target=clear_status, daemon=True).start()

        refresh_button.on_click(on_refresh)

        # Info panel (reactive)
        @pn.depends(workflow_selector.param.value)
        def info_panel(selected_idx):
            if selected_idx is None:
                return pn.pane.Markdown("*Wähle eine Simulation aus*")

            wf = self.available_workflows[selected_idx]

            info_md = f"""
### 📊 Simulation Info

**Name:** {wf['name']}
**Gespeichert:** {wf['date']}
**Szenario:** {wf['scenario']}
**Kosten:** {wf['costs']:,.0f} EUR
**Steps:** {' → '.join(wf['steps']) if wf['steps'] else 'N/A'}
**Pfad:** `{wf['path']}`

---
"""
            return pn.pane.Markdown(info_md)

        # Dashboard tabs (reactive)
        @pn.depends(workflow_selector.param.value)
        def dashboard_tabs(selected_idx):
            if selected_idx is None:
                return pn.pane.Markdown("*Wähle eine Simulation aus, um das Dashboard anzuzeigen*")

            wf_info = self.available_workflows[selected_idx]

            # Load workflow
            workflow = self._load_workflow(wf_info)

            if workflow is None:
                return pn.pane.Markdown(
                    f"## ❌ Fehler beim Laden\n\n"
                    f"Workflow konnte nicht geladen werden: `{wf_info['path']}`"
                )

            # Create dashboard using existing dashboard module
            from energis.io.dashboard import create_dashboard

            try:
                dashboard = create_dashboard(workflow, title=wf_info['name'], diagnose=False)
                return dashboard
            except Exception as e:
                logger.error(f"Failed to create dashboard: {e}")
                import traceback
                return pn.pane.Markdown(
                    f"## ❌ Dashboard-Fehler\n\n"
                    f"```\n{traceback.format_exc()}\n```"
                )

        # Comparison button (shows when 2+ workflows available)
        comparison_section = pn.Column()

        if len(self.available_workflows) >= 2:
            comparison_button = pn.widgets.Button(
                name='🔀 Vergleichs-Modus aktivieren',
                button_type='primary',
                width=200
            )

            comparison_help = pn.pane.Markdown(
                "*Vergleiche 2+ Simulationen nebeneinander*"
            )

            comparison_section.append(pn.Row(comparison_button, comparison_help))

        # Layout with better spacing
        layout = pn.Column(
            header,
            pn.layout.Divider(),
            pn.layout.VSpacer(height=20),  # Extra space after header
            pn.Row(
                pn.Column(
                    workflow_selector,
                    pn.Row(refresh_button, refresh_status),  # Refresh controls
                    pn.layout.VSpacer(height=10),  # Small space
                    info_panel,
                    comparison_section,
                    width=400
                ),
                pn.Column(
                    dashboard_tabs,
                    sizing_mode='stretch_width'
                )
            ),
            sizing_mode='stretch_width'
        )

        return layout
