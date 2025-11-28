#!/usr/bin/env python3
"""
Load and compare multiple saved workflow results with interactive selection.

This provides a multi-workflow dashboard where you can:
- Select from all saved simulations via dropdown
- View metadata (scenario, technologies, costs, etc.)
- Analyze results interactively

Usage:
    panel serve load_dashboard.py --show

Requirements:
    saved_workflows/ directory with saved simulations
    (created by save_workflow_results.py)
"""

import sys
import pickle
import json
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("🎛️ EnerGIS Multi-Workflow Dashboard")
print("="*70)

import panel as pn
from energis.io.dashboard import create_dashboard

# Initialize Panel
pn.extension('plotly', 'tabulator')

# Check for saved workflows
saved_workflows_dir = project_root / 'saved_workflows'

if not saved_workflows_dir.exists():
    print(f"\n❌ FEHLER: Keine gespeicherten Workflows gefunden!")
    print(f"   Erwartet: {saved_workflows_dir}")
    print(f"\n💡 Lösung:")
    print("   1. Führe zuerst aus: python save_workflow_results.py")
    print("   2. Dann starte Dashboard: panel serve load_dashboard.py --show")
    sys.exit(1)

# Scan for saved workflows
workflow_dirs = sorted(
    [d for d in saved_workflows_dir.iterdir() if d.is_dir()],
    reverse=True  # Most recent first
)

if not workflow_dirs:
    print(f"\n❌ FEHLER: Keine gespeicherten Workflows gefunden in {saved_workflows_dir}")
    print(f"\n💡 Lösung:")
    print("   1. Führe zuerst aus: python save_workflow_results.py")
    print("   2. Dann starte Dashboard: panel serve load_dashboard.py --show")
    sys.exit(1)

print(f"\n✅ {len(workflow_dirs)} gespeicherte Workflow(s) gefunden")

# Load all metadata
workflows_info = []
for wf_dir in workflow_dirs:
    metadata_file = wf_dir / 'metadata.json'
    workflow_file = wf_dir / 'workflow.pkl'

    if metadata_file.exists() and workflow_file.exists():
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            workflows_info.append({
                'dir': wf_dir,
                'dir_name': wf_dir.name,
                'metadata': metadata,
                'workflow_file': workflow_file,
            })
            print(f"   • {wf_dir.name}: {metadata.get('name', 'Unknown')}")
        except Exception as e:
            print(f"   ⚠️  Fehler beim Laden von {wf_dir.name}: {e}")

if not workflows_info:
    print(f"\n❌ FEHLER: Keine gültigen Workflows gefunden")
    sys.exit(1)

print(f"\n✅ Dashboard wird erstellt...")


def create_metadata_panel(metadata):
    """Create a Panel component showing workflow metadata."""

    # Build HTML for metadata display
    html_parts = [
        "<div style='background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;'>",
        "<h2 style='margin-top: 0; color: #2c3e50;'>📋 Workflow Informationen</h2>",
    ]

    # Basic info
    html_parts.append("<div style='margin-bottom: 15px;'>")
    html_parts.append(f"<h3 style='color: #34495e; margin-bottom: 10px;'>🎯 {metadata['name']}</h3>")
    html_parts.append(f"<p style='color: #7f8c8d; margin: 5px 0;'><i>{metadata.get('description', '')}</i></p>")
    html_parts.append(f"<p style='color: #95a5a6; margin: 5px 0; font-size: 0.9em;'>Gespeichert: {metadata['saved_at']}</p>")
    html_parts.append("</div>")

    # Scenario info
    scenario = metadata.get('scenario', {})
    html_parts.append("<div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 15px;'>")

    html_parts.append("<div style='background: white; padding: 12px; border-radius: 6px; border-left: 4px solid #3498db;'>")
    html_parts.append(f"<div style='font-size: 0.85em; color: #7f8c8d; margin-bottom: 4px;'>SCENARIO</div>")
    html_parts.append(f"<div style='font-weight: bold; color: #2c3e50;'>{scenario.get('name', 'N/A')}</div>")
    html_parts.append("</div>")

    html_parts.append("<div style='background: white; padding: 12px; border-radius: 6px; border-left: 4px solid #9b59b6;'>")
    html_parts.append(f"<div style='font-size: 0.85em; color: #7f8c8d; margin-bottom: 4px;'>SYSTEM</div>")
    html_parts.append(f"<div style='font-weight: bold; color: #2c3e50;'>{scenario.get('system', 'N/A')}</div>")
    html_parts.append("</div>")

    html_parts.append("<div style='background: white; padding: 12px; border-radius: 6px; border-left: 4px solid #1abc9c;'>")
    html_parts.append(f"<div style='font-size: 0.85em; color: #7f8c8d; margin-bottom: 4px;'>SITE</div>")
    html_parts.append(f"<div style='font-weight: bold; color: #2c3e50;'>{scenario.get('site', 'N/A')}</div>")
    html_parts.append("</div>")

    html_parts.append("</div>")

    # Workflow info
    workflow_info = metadata.get('workflow', {})
    steps = workflow_info.get('steps', [])
    html_parts.append("<div style='background: white; padding: 12px; border-radius: 6px; margin-bottom: 15px;'>")
    html_parts.append(f"<div style='font-size: 0.85em; color: #7f8c8d; margin-bottom: 6px;'>WORKFLOW</div>")
    html_parts.append(f"<div style='font-weight: bold; color: #2c3e50;'>{' → '.join(steps)}</div>")
    html_parts.append(f"<div style='font-size: 0.9em; color: #95a5a6; margin-top: 4px;'>Solver: {metadata.get('solver', 'N/A')}</div>")
    html_parts.append("</div>")

    # Technologies
    technologies = metadata.get('technologies', {})
    if technologies:
        html_parts.append("<div style='background: white; padding: 12px; border-radius: 6px; margin-bottom: 15px;'>")
        html_parts.append("<div style='font-size: 0.85em; color: #7f8c8d; margin-bottom: 8px;'>TECHNOLOGIEN</div>")

        heat_pumps = technologies.get('heat_pumps', {})
        if heat_pumps:
            html_parts.append("<div style='margin-bottom: 8px;'>")
            html_parts.append("<div style='font-weight: bold; color: #e74c3c; margin-bottom: 4px;'>🔥 Wärmepumpen:</div>")
            for name, data in heat_pumps.items():
                capacity = data.get('capacity_mw', 0)
                html_parts.append(f"<div style='margin-left: 20px; color: #34495e;'>• {name}: {capacity:.2f} MW</div>")
            html_parts.append("</div>")

        storage = technologies.get('storage', {})
        if storage:
            capacity = storage.get('capacity_mwh', 0)
            html_parts.append(f"<div style='font-weight: bold; color: #f39c12;'>🔋 Speicher: {capacity:.2f} MWh</div>")

        html_parts.append("</div>")

    # Statistics
    stats = metadata.get('statistics', {})
    costs = metadata.get('costs', {})

    html_parts.append("<div style='display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 15px;'>")

    html_parts.append("<div style='background: white; padding: 12px; border-radius: 6px;'>")
    html_parts.append("<div style='font-size: 0.85em; color: #7f8c8d; margin-bottom: 6px;'>ZEITRAUM</div>")
    html_parts.append(f"<div style='font-weight: bold; color: #2c3e50;'>{stats.get('timesteps', 0):,} Zeitschritte</div>")
    html_parts.append(f"<div style='font-size: 0.9em; color: #95a5a6; margin-top: 4px;'>{stats.get('duration_hours', 0):.1f} Stunden</div>")
    html_parts.append("</div>")

    if costs.get('total_eur'):
        html_parts.append("<div style='background: white; padding: 12px; border-radius: 6px;'>")
        html_parts.append("<div style='font-size: 0.85em; color: #7f8c8d; margin-bottom: 6px;'>KOSTEN</div>")
        html_parts.append(f"<div style='font-weight: bold; color: #27ae60; font-size: 1.1em;'>{costs['total_eur']:,.0f} EUR</div>")
        if costs.get('capex_eur'):
            html_parts.append(f"<div style='font-size: 0.85em; color: #95a5a6; margin-top: 4px;'>CAPEX: {costs['capex_eur']:,.0f} EUR</div>")
        if costs.get('opex_eur'):
            html_parts.append(f"<div style='font-size: 0.85em; color: #95a5a6;'>OPEX: {costs['opex_eur']:,.0f} EUR</div>")
        html_parts.append("</div>")

    html_parts.append("</div>")

    # Config files (collapsible)
    config_files = metadata.get('config_files', [])
    if config_files:
        html_parts.append("<details style='background: white; padding: 12px; border-radius: 6px;'>")
        html_parts.append("<summary style='cursor: pointer; color: #7f8c8d; font-size: 0.85em;'>📁 Konfigurationsdateien anzeigen</summary>")
        html_parts.append("<ul style='margin-top: 8px; padding-left: 20px;'>")
        for config_file in config_files:
            html_parts.append(f"<li style='color: #34495e; font-size: 0.9em;'>{config_file}</li>")
        html_parts.append("</ul>")
        html_parts.append("</details>")

    html_parts.append("</div>")

    return pn.pane.HTML(''.join(html_parts))


def load_workflow(workflow_file):
    """Load workflow from pickle file."""
    with open(workflow_file, 'rb') as f:
        return pickle.load(f)


# Create main dashboard layout
class MultiWorkflowDashboard:
    """Dashboard that allows selecting between multiple saved workflows."""

    def __init__(self, workflows_info):
        self.workflows_info = workflows_info
        self.current_dashboard = None

        # Create dropdown options
        dropdown_options = {
            f"{info['metadata']['saved_at'][:10]} - {info['metadata']['name']}": i
            for i, info in enumerate(workflows_info)
        }

        # Create widgets
        self.workflow_selector = pn.widgets.Select(
            name='🗂️ Gespeicherte Simulation auswählen:',
            options=dropdown_options,
            value=0,  # Select first (most recent)
            width=600,
            sizing_mode='stretch_width'
        )

        # Create layout placeholders
        self.metadata_panel = pn.Column()
        self.dashboard_panel = pn.Column()

        # Initial load
        self._update_dashboard(None)

        # Watch for changes
        self.workflow_selector.param.watch(self._update_dashboard, 'value')

    def _update_dashboard(self, event):
        """Update dashboard when selection changes."""
        idx = self.workflow_selector.value
        info = self.workflows_info[idx]

        print(f"\n📊 Lade Workflow: {info['dir_name']}")

        # Update metadata panel
        metadata_pane = create_metadata_panel(info['metadata'])
        self.metadata_panel.clear()
        self.metadata_panel.append(metadata_pane)

        # Load and create dashboard
        try:
            workflow = load_workflow(info['workflow_file'])
            dashboard = create_dashboard(
                workflow,
                title=f"EnerGIS Dashboard - {info['metadata']['name']}"
            )

            self.dashboard_panel.clear()
            self.dashboard_panel.append(dashboard)

            print(f"   ✅ Dashboard geladen")

        except Exception as e:
            error_html = f"""
            <div style='background: #fee; padding: 20px; border-radius: 8px; border-left: 4px solid #e74c3c;'>
                <h3 style='color: #c0392b; margin-top: 0;'>❌ Fehler beim Laden</h3>
                <p style='color: #7f8c8d;'>{str(e)}</p>
            </div>
            """
            self.dashboard_panel.clear()
            self.dashboard_panel.append(pn.pane.HTML(error_html))
            print(f"   ❌ Fehler: {e}")

    def panel(self):
        """Return the complete Panel layout."""
        return pn.Column(
            pn.pane.Markdown("# 🎛️ EnerGIS Multi-Workflow Dashboard", sizing_mode='stretch_width'),
            pn.pane.Markdown(
                f"**{len(self.workflows_info)} gespeicherte Simulation(en) verfügbar**",
                sizing_mode='stretch_width'
            ),
            self.workflow_selector,
            pn.layout.Divider(),
            self.metadata_panel,
            pn.layout.Divider(),
            self.dashboard_panel,
            sizing_mode='stretch_width',
        )


# Create and serve dashboard
print("\n📊 Erstelle Multi-Workflow Dashboard...")

dashboard_app = MultiWorkflowDashboard(workflows_info)

print("   ✅ Dashboard erstellt!")

print("\n" + "="*70)
print("✅ SUCCESS! Multi-Workflow Dashboard ist bereit!")
print("="*70)

print("\n📊 Dashboard Features:")
print(f"   • {len(workflows_info)} Simulation(en) verfügbar")
print("   • Dropdown-Auswahl für Workflows")
print("   • Detaillierte Metadaten-Anzeige")
print("   • Interaktive Ergebnis-Visualisierung")

print("\n🌐 Webapp läuft auf:")
print("   URL: http://localhost:5006/load_dashboard")
print("   Zum Beenden: Strg+C")

print("\n💡 Weitere Simulationen hinzufügen:")
print("   python save_workflow_results.py --name 'mein_test'")

print("\n" + "="*70)

# Make dashboard servable
dashboard_app.panel().servable()
