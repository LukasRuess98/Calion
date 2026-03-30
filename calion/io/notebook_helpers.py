"""
Helper functions for Jupyter notebooks to streamline workflow management.

This module provides common functionality used across multiple notebooks:
- Workflow persistence (save/load)
- Dashboard creation
- KPI display
- Notebook environment setup

Usage in notebooks:
    from calion.io.notebook_helpers import (
        setup_notebook_environment,
        save_workflow_run,
        create_and_display_dashboard
    )
"""

from __future__ import annotations

import json
import pickle
import sys
import warnings
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from calion.logging_config import get_logger

__all__ = [
    "setup_notebook_environment",
    "save_workflow_run",
    "load_workflow_from_saved",
    "list_saved_workflows",
    "display_workflow_summary",
    "display_kpi_summary",
    "create_and_display_dashboard",
    "diagnose_dashboard_data",
]

logger = get_logger(__name__)


def setup_notebook_environment(
    project_name: str = "Planing-Framework-for-Heat",
    configure_matplotlib: bool = True,
    configure_pandas: bool = True,
    suppress_warnings: bool = True,
    server_mode: bool = False,
) -> Path:
    """
    Setup notebook environment automatically.

    - Finds project root directory
    - Adds project to sys.path
    - Configures matplotlib and pandas (optional)
    - Suppresses warnings (optional)
    - Server-mode for headless environments (optional)

    Parameters
    ----------
    project_name : str
        Name of the project directory (default: Planing-Framework-for-Heat)
    configure_matplotlib : bool
        Configure matplotlib style and inline mode
    configure_pandas : bool
        Configure pandas display options
    suppress_warnings : bool
        Suppress warnings
    server_mode : bool
        Enable server mode for headless environments (sets 'Agg' backend)
        Use this when running on a server without display/GUI

    Returns
    -------
    Path
        Project root path

    Examples
    --------
    >>> from calion.io.notebook_helpers import setup_notebook_environment
    >>> PROJECT_ROOT = setup_notebook_environment()
    ✅ Projekt-Root: /path/to/Planing-Framework-for-Heat

    On a server:
    >>> PROJECT_ROOT = setup_notebook_environment(server_mode=True)
    ✅ Projekt-Root: /path/to/Planing-Framework-for-Heat
    ✅ Server-Modus aktiviert (Matplotlib: Agg backend)
    """

    # Find project root
    def find_project_root(start: Path) -> Path:
        """Find project root by looking for .git and calion directories."""
        for candidate in [start] + list(start.parents):
            if (candidate / '.git').exists() and (candidate / 'calion').exists():
                return candidate
        # Fallback: look for project name in path
        for candidate in [start] + list(start.parents):
            if candidate.name == project_name:
                return candidate
        return start

    project_root = find_project_root(Path.cwd())

    # Add to sys.path
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    logger.info(f"✅ Projekt-Root: {project_root}")

    # Configure matplotlib
    if configure_matplotlib:
        try:
            import matplotlib
            import matplotlib.pyplot as plt

            # Server mode: use Agg backend (no display required)
            if server_mode:
                matplotlib.use('Agg')
                logger.info("✅ Matplotlib konfiguriert (Agg backend für Server)")
            else:
                # Try to detect if we're in a headless environment
                import os
                if not os.environ.get('DISPLAY') and sys.platform != 'win32':
                    matplotlib.use('Agg')
                    logger.info("✅ Matplotlib konfiguriert (Agg backend - kein Display erkannt)")
                else:
                    logger.info("✅ Matplotlib konfiguriert (Standard backend)")

            plt.style.use('seaborn-v0_8-darkgrid')
        except ImportError:
            pass

    # Configure pandas
    if configure_pandas:
        pd.set_option('display.max_columns', None)
        pd.set_option('display.max_rows', 100)
        pd.set_option('display.float_format', '{:.2f}'.format)
        logger.info("✅ Pandas konfiguriert")

    # Suppress warnings
    if suppress_warnings:
        warnings.filterwarnings('ignore')
        logger.info("✅ Warnings unterdrückt")

    return project_root


def save_workflow_run(
    workflow: Any,
    name: Optional[str] = None,
    description: Optional[str] = None,
    config_paths: Optional[List[str]] = None,
    save_dir: Optional[str] = None,
    export_first: bool = True,
) -> Path:
    """
    Save workflow with metadata and exports.

    This function:
    1. Exports results (CSV, PDF, SVG) via export_workflow_results()
    2. Saves workflow object as pickle
    3. Creates comprehensive metadata.json
    4. Optionally moves everything to outputs/workflows/

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow result from run_workflow()
    name : str, optional
        Human-readable name for this simulation run
        If None, auto-generates from timestamp
    description : str, optional
        Description of the simulation
    config_paths : list of str, optional
        List of config files used for this run
    save_dir : str, optional
        Target directory (default: outputs/workflows)
        Can be absolute or relative to project root
    export_first : bool
        Whether to run export_workflow_results first (default: True)

    Returns
    -------
    Path
        Path to the saved workflow directory

    Examples
    --------
    >>> workflow = rh.run_workflow(CONFIG_PATHS)
    >>> workflow_dir = save_workflow_run(
    ...     workflow,
    ...     name="Baseline Simulation",
    ...     description="Standard configuration with air/ground HP",
    ...     config_paths=CONFIG_PATHS
    ... )
    """

    from calion.run import rolling_horizon as rh
    from calion.io._output_paths import resolve_workflows_dir

    # Resolve save_dir (supports legacy path detection)
    save_path = Path(resolve_workflows_dir(save_dir))
    if not save_path.is_absolute():
        # Find project root
        project_root = Path.cwd()
        for candidate in [project_root] + list(project_root.parents):
            if (candidate / 'calion').exists():
                project_root = candidate
                break
        save_path = project_root / save_dir

    # Ensure directory exists
    save_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Export results (this creates the export directory)
    if export_first:
        logger.info("📦 Exportiere Ergebnisse (CSV, PDF, SVG)...")
        export_meta = rh.export_workflow_results(workflow)
        export_dir = Path(export_meta['outdir'])
    else:
        # Create directory manually
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        auto_name = (name or f"workflow_{timestamp}").replace(" ", "_")
        base_export_dir = save_path / f"{timestamp}_{auto_name}"
        export_dir = base_export_dir
        counter = 1
        while export_dir.exists():
            export_dir = save_path / f"{timestamp}_{auto_name}_{counter}"
            counter += 1
        export_dir.mkdir(parents=True, exist_ok=False)
        export_meta = {'outdir': str(export_dir)}

    logger.info(f"📁 Speicherverzeichnis: {export_dir}")

    # Step 2: Save workflow object as pickle
    workflow_pkl = export_dir / 'workflow.pkl'
    logger.info("💾 Speichere Workflow-Objekt...")
    with open(workflow_pkl, 'wb') as f:
        pickle.dump(workflow, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info(f"✅ Workflow gespeichert: {workflow_pkl.name}")

    # Step 3: Create comprehensive metadata
    metadata = _build_metadata(
        workflow=workflow,
        name=name,
        description=description,
        config_paths=config_paths,
        export_dir=export_dir,
    )

    metadata_json = export_dir / 'metadata.json'
    logger.info("📝 Erstelle Metadaten...")
    with open(metadata_json, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"✅ Metadaten gespeichert: {metadata_json.name}")

    # Step 4: Move to saved_workflows if export was in exports/
    if export_first and 'exports' in str(export_dir):
        # Move from exports/ to saved_workflows/
        target_dir = save_path / export_dir.name
        if not target_dir.exists():
            logger.info(f"🔄 Verschiebe nach {save_path.name}/...")
            import shutil
            shutil.move(str(export_dir), str(target_dir))
            export_dir = target_dir
            logger.info(f"✅ Verschoben nach: {export_dir}")

    logger.info("✅ WORKFLOW ERFOLGREICH GESPEICHERT")
    logger.info("="*70)
    logger.info(f"📂 Verzeichnis: {export_dir}")
    logger.info(f"📊 Dateien:")
    logger.info(f"   • workflow.pkl    - Workflow-Objekt")
    logger.info(f"   • metadata.json   - Metadaten")
    logger.info(f"   • *.csv           - Zeitreihen")
    logger.info(f"   • *.pdf, *.svg    - Plots")
    if (export_dir / 'design.json').exists():
        logger.info(f"   • design.json     - Anlagen-Design")
    logger.info("="*70)

    return export_dir


def _build_metadata(
    workflow: Any,
    name: Optional[str],
    description: Optional[str],
    config_paths: Optional[List[str]],
    export_dir: Path,
) -> Dict[str, Any]:
    """Build comprehensive metadata dictionary."""

    # Auto-generate name if not provided
    if name is None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        name = f"Workflow {timestamp}"

    # Extract workflow information
    has_pf = getattr(workflow, 'pf_result', None) is not None
    has_rh = getattr(workflow, 'rh_result', None) is not None
    has_mpc = getattr(workflow, 'mpc_result', None) is not None

    # Get scenario info from config (defensive: WorkflowResult has .config, legacy objects may not)
    cfg_dict = getattr(workflow, 'config', None) or {}
    scenario_cfg = cfg_dict.get('scenario', {})
    system_cfg = cfg_dict.get('system', {})
    site_cfg = cfg_dict.get('site', {})
    run_cfg = cfg_dict.get('run', {})

    plan = getattr(workflow, 'plan', None)

    # Build metadata
    metadata = {
        'saved_at': datetime.now().isoformat(),
        'name': name,
        'description': description or "",
        'scenario': {
            'name': scenario_cfg.get('name', 'unknown'),
            'system': system_cfg.get('name', 'unknown'),
            'site': site_cfg.get('name', 'default'),
            'run_mode': scenario_cfg.get('run_mode', 'UNKNOWN'),
            'title': scenario_cfg.get('title', ''),
        },
        'config_files': config_paths or [],
        'workflow': {
            'steps': list(plan.steps) if plan else [],
            'fix_design': getattr(plan, 'fix_design', False) if plan else False,
        },
        'results_available': {
            'pf': has_pf,
            'rh': has_rh,
            'mpc': has_mpc,
        },
        'solver': run_cfg.get('solver', 'unknown'),
        'dt_h': run_cfg.get('dt_h', 1.0),
    }

    # Add technologies from design
    if workflow.design:
        metadata['technologies'] = {
            'heat_pumps': {
                hp_id: {'capacity_mw': hp_data.get('capacity_mw', 0.0), 'type': 'heat_pump'}
                for hp_id, hp_data in workflow.design.heat_pumps.items()
            } if workflow.design.heat_pumps else {},
            'storage': {
                'capacity_mwh': workflow.design.storage.get('capacity_mwh', 0.0) if workflow.design.storage else 0.0,
                'type': 'thermal_storage'
            } if workflow.design.storage else None,
        }

    # Add statistics
    primary_result = getattr(workflow, 'rh_result', None) or getattr(workflow, 'mpc_result', None) or getattr(workflow, 'pf_result', None)
    if primary_result:
        _table = getattr(primary_result, 'table', None)
        _table_len = len(_table) if (_table is not None and hasattr(_table, '__len__')) else len(getattr(_table, 'index', []))
        metadata['statistics'] = {
            'timesteps': _table_len,
            'duration_hours': _table_len * metadata['dt_h'],
            'start_date': str(_table.index[0]) if _table is not None and getattr(_table, 'index', None) else None,
            'end_date': str(_table.index[-1]) if _table is not None and getattr(_table, 'index', None) else None,
        }

        # Add costs
        if primary_result.costs:
            total_cost = primary_result.costs.get('objective.OBJ_value_EUR', 0.0)
            capex = primary_result.costs.get('objective.Capex_cost_EUR', 0.0)
            fuel = primary_result.costs.get('objective.Fuel_cost_EUR', 0.0)
            elec = primary_result.costs.get('objective.Grid_energy_cost_EUR', 0.0)

            metadata['costs'] = {
                'total_eur': total_cost,
                'capex_eur': capex,
                'opex_eur': total_cost - capex,
                'fuel_eur': fuel,
                'electricity_eur': elec,
            }

    # Backward-compatibility aliases
    metadata['created'] = metadata['saved_at']
    metadata['workflow_plan'] = metadata['workflow']

    return metadata


def list_saved_workflows(
    save_dir: Optional[str] = None,
    sort_by: str = "date",
) -> List[Dict[str, Any]]:
    """
    List all saved workflows with metadata.

    Parameters
    ----------
    save_dir : str, optional
        Directory to search (default: outputs/workflows)
    sort_by : str
        Sort by: "date", "name", "cost" (default: date)

    Returns
    -------
    list of dict
        List of workflow metadata dictionaries

    Examples
    --------
    >>> workflows = list_saved_workflows()
    >>> for wf in workflows:
    ...     logger.info(f"{wf['name']}: {wf['costs']:.0f} EUR")
    """

    # Resolve directory (supports legacy path detection)
    from calion.io._output_paths import resolve_workflows_dir
    resolved = resolve_workflows_dir(save_dir)
    save_path = Path(resolved)
    if not save_path.is_absolute():
        # Find project root
        project_root = Path.cwd()
        for candidate in [project_root] + list(project_root.parents):
            if (candidate / 'calion').exists():
                project_root = candidate
                break
        save_path = project_root / resolved
    if not save_path.exists():
        logger.info(f"⚠️  Verzeichnis {resolved} existiert nicht")
        return []

    workflows = []

    # Scan all subdirectories
    for workflow_dir in save_path.iterdir():
        if not workflow_dir.is_dir():
            continue

        metadata_file = workflow_dir / 'metadata.json'

        # Load metadata if available
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                # Extract key information
                workflows.append({
                    'path': workflow_dir,
                    'name': metadata.get('name', workflow_dir.name),
                    'description': metadata.get('description', ''),
                    'date': datetime.fromisoformat(metadata['saved_at']) if 'saved_at' in metadata else None,
                    'date_str': metadata.get('saved_at', ''),
                    'created': metadata.get('saved_at', ''),
                    'costs': metadata.get('costs', {}).get('total_eur', 0.0),
                    'steps': metadata.get('workflow', {}).get('steps', []),
                    'timesteps': metadata.get('statistics', {}).get('timesteps', 0),
                    'scenario': metadata.get('scenario', {}).get('name', 'unknown'),
                })
            except Exception as e:
                logger.info(f"⚠️  Fehler beim Laden von {metadata_file}: {e}")

    # Sort workflows
    if sort_by == "date":
        workflows.sort(key=lambda w: w['date'] or datetime.min, reverse=True)
    elif sort_by == "name":
        workflows.sort(key=lambda w: w['name'])
    elif sort_by == "cost":
        workflows.sort(key=lambda w: w['costs'], reverse=True)

    return workflows


def load_workflow_from_saved(
    workflow_path: str | Path,
    verbose: bool = True,
) -> Any:
    """
    Load a saved workflow from disk.

    Parameters
    ----------
    workflow_path : str or Path
        Path to workflow directory
    verbose : bool
        Print loading information

    Returns
    -------
    WorkflowResult
        The loaded workflow object

    Examples
    --------
    >>> workflow = load_workflow_from_saved("saved_workflows/2025-11-28_...")
    📂 Lade Workflow: saved_workflows/2025-11-28_...
    ✅ Workflow geladen!
    """

    workflow_dir = Path(workflow_path)

    if not workflow_dir.exists():
        raise FileNotFoundError(f"Workflow-Verzeichnis nicht gefunden: {workflow_dir}")

    workflow_pkl = workflow_dir / 'workflow.pkl'

    if not workflow_pkl.exists():
        raise FileNotFoundError(f"workflow.pkl nicht gefunden in {workflow_dir}")

    if verbose:
        logger.info(f"📂 Lade Workflow: {workflow_dir.name}")

    # Load workflow
    with open(workflow_pkl, 'rb') as f:
        workflow = pickle.load(f)

    if verbose:
        logger.info("✅ Workflow geladen!")
        logger.info(f"   Steps: {' → '.join(workflow.plan.steps)}")

        # Show timesteps
        primary_result = workflow.rh_result or workflow.mpc_result or workflow.pf_result
        if primary_result:
            logger.info(f"   Zeitschritte: {len(primary_result.table):,}")

    return workflow


def display_workflow_summary(
    workflow: Any,
    show_costs: bool = True,
    show_design: bool = True,
) -> None:
    """
    Display formatted workflow summary.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow to summarize
    show_costs : bool
        Show detailed cost breakdown
    show_design : bool
        Show design/capacities

    Examples
    --------
    >>> display_workflow_summary(workflow)
    """

    logger.info("📊 WORKFLOW-ZUSAMMENFASSUNG")
    logger.info("="*70)

    logger.info(f"🔄 Workflow: {' → '.join(workflow.plan.steps)}")

    # Show which results are available
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None
    has_mpc = workflow.mpc_result is not None

    logger.info("📦 Verfügbare Ergebnisse:")
    logger.info(f"   {'✅' if has_pf else '❌'} Perfect Forecast (PF)")
    logger.info(f"   {'✅' if has_rh else '❌'} Rolling Horizon (RH)")
    logger.info(f"   {'✅' if has_mpc else '❌'} Model Predictive Control (MPC)")

    # Show costs
    if show_costs:
        primary_result = workflow.rh_result or workflow.mpc_result or workflow.pf_result
        if primary_result and primary_result.costs:
            logger.info("💰 Kosten:")

            total_cost = primary_result.costs.get('objective.OBJ_value_EUR', 0.0)
            logger.info(f"   Gesamtkosten:  {total_cost:>15,.0f} EUR")

            # Breakdown
            elec = primary_result.costs.get('objective.Grid_energy_cost_EUR', 0.0)
            fuel = primary_result.costs.get('objective.Fuel_cost_EUR', 0.0)
            capex = primary_result.costs.get('objective.Capex_cost_EUR', 0.0)

            if elec > 1e-3:
                logger.info(f"   • Strom:       {elec:>15,.0f} EUR  ({elec/total_cost*100:>5.1f}%)")
            if fuel > 1e-3:
                logger.info(f"   • Brennstoff:  {fuel:>15,.0f} EUR  ({fuel/total_cost*100:>5.1f}%)")
            if capex > 1e-3:
                logger.info(f"   • CAPEX:       {capex:>15,.0f} EUR  ({capex/total_cost*100:>5.1f}%)")

    # Show design
    if show_design and workflow.design:
        logger.info("🏭 Anlagen-Design:")

        if workflow.design.heat_pumps:
            logger.info(f"   Wärmepumpen:")
            for hp_id, hp_data in sorted(workflow.design.heat_pumps.items()):
                capacity = hp_data.get('capacity_mw', 0.0)
                logger.info(f"      {hp_id}: {capacity:>6.2f} MW")

        if workflow.design.storage:
            storage_cap = workflow.design.storage.get('capacity_mwh', 0.0)
            logger.info(f"   Speicher:   {storage_cap:>6.2f} MWh")

    logger.info("="*70)


def display_kpi_summary(
    workflow: Any,
    timeseries_df: Optional[pd.DataFrame] = None,
) -> None:
    """
    Display detailed KPI summary with component analysis.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow to analyze
    timeseries_df : DataFrame, optional
        Timeseries dataframe (will be created from workflow if not provided)

    Examples
    --------
    >>> display_kpi_summary(workflow)
    """

    logger.info("📊 KEY PERFORMANCE INDICATORS")
    logger.info("="*70)

    primary_result = workflow.rh_result or workflow.mpc_result or workflow.pf_result

    if not primary_result:
        logger.info("⚠️  Keine Ergebnisse verfügbar")
        return

    # Create dataframe if not provided
    if timeseries_df is None:
        timeseries_df = pd.DataFrame({
            'timestamp': primary_result.table.index,
            **{col: primary_result.table.data[col] for col in primary_result.table.columns},
            **primary_result.series,
        })

    ts = timeseries_df

    # Costs
    if primary_result.costs:
        logger.info("💰 Wirtschaftlichkeit:")

        total_cost = primary_result.costs.get('objective.OBJ_value_EUR', 0.0)
        peak_power = primary_result.costs.get('objective.P_buy_peak_MW', 0.0)

        logger.info(f"   Gesamtkosten:  {total_cost:>15,.0f} EUR")
        if peak_power > 0:
            logger.info(f"   Peak-Leistung: {peak_power:>15,.2f} MW")

        # Detailed breakdown (same as in scenario_studio)
        _display_detailed_cost_breakdown(primary_result.costs)

    # Energy balance
    logger.info("⚡ Elektrische Energie:")

    p_buy_col = next((c for c in ['P_buy_MW', 'P_buy'] if c in ts.columns), None)
    p_sell_col = next((c for c in ['P_sell_MW', 'P_sell'] if c in ts.columns), None)

    if p_buy_col:
        e_buy = ts[p_buy_col].sum()
        logger.info(f"   Netzbezug:     {e_buy:>15,.0f} MWh")

    if p_sell_col:
        e_sell = ts[p_sell_col].sum()
        logger.info(f"   Einspeisung:   {e_sell:>15,.0f} MWh")

    # Component utilization
    logger.info("🏭 Komponenten-Auslastung:")

    # Heat pumps
    hp_cols = [c for c in ts.columns if c.startswith('HP') and c.endswith('_Q_th_MW')]
    if hp_cols:
        logger.info("   Wärmepumpen:")
        for col in sorted(hp_cols):
            hp_id = col.replace('_Q_th_MW', '')
            avg = ts[col].mean()
            max_val = ts[col].max()
            hours_on = (ts[col] > 0.01).sum()
            logger.info(f"      {hp_id:8s}: Ø {avg:6.2f} MW | Max {max_val:6.2f} MW | {hours_on:5d} h aktiv")

    # Storage
    tes_soc_col = next((c for c in ['TES_SOC_MWh', 'TES_SOC'] if c in ts.columns), None)
    if tes_soc_col:
        logger.info("   Speicher:")
        logger.info(f"      Max SOC:       {ts[tes_soc_col].max():>10.2f} MWh")
        logger.info(f"      Ø SOC:         {ts[tes_soc_col].mean():>10.2f} MWh")

    logger.info("="*70)


def _display_detailed_cost_breakdown(costs: Dict[str, Any]) -> None:
    """Display detailed cost breakdown (helper for display_kpi_summary)."""
    logger = get_logger(__name__)

    logger.info("   💶 Detaillierte Aufschlüsselung:")

    # Electricity costs
    elec_total = costs.get('objective.Grid_energy_cost_EUR', 0.0)
    elec_base = costs.get('objective.Electricity_base_cost_EUR', 0.0)
    elec_fee = costs.get('objective.Electricity_energy_fee_EUR', 0.0)
    elec_grid = costs.get('objective.Electricity_grid_fee_EUR', 0.0)
    demand_charge = costs.get('objective.Demand_charge_cost_EUR', 0.0)

    if elec_total > 1e-3:
        logger.info(f"      Stromkosten:           {elec_total:>15,.0f} EUR")
        if elec_base > 1e-3:
            logger.info(f"         • Spotpreis:        {elec_base:>15,.0f} EUR  ({elec_base/elec_total*100:>5.1f}%)")
        if elec_fee > 1e-3:
            logger.info(f"         • Energy Fee:       {elec_fee:>15,.0f} EUR  ({elec_fee/elec_total*100:>5.1f}%)")
        if elec_grid > 1e-3:
            logger.info(f"         • Netzentgelte:     {elec_grid:>15,.0f} EUR  ({elec_grid/elec_total*100:>5.1f}%)")
        if demand_charge > 1e-3:
            logger.info(f"         • Leistungspreis:   {demand_charge:>15,.0f} EUR")

    # Fuel costs
    fuel_total = costs.get('objective.Fuel_cost_EUR', 0.0)
    if fuel_total > 1e-3:
        logger.info(f"      Brennstoffkosten:      {fuel_total:>15,.0f} EUR")

    # Investment costs
    capex_total = costs.get('objective.Capex_cost_EUR', 0.0)
    capex_hp = costs.get('objective.Capex_heat_pumps_EUR', 0.0)
    capex_sto = costs.get('objective.Capex_storage_EUR', 0.0)

    if capex_total > 1e-3:
        logger.info(f"      Investitionskosten:    {capex_total:>15,.0f} EUR")
        if capex_hp > 1e-3:
            logger.info(f"         • Wärmepumpen:      {capex_hp:>15,.0f} EUR  ({capex_hp/capex_total*100:>5.1f}%)")
        if capex_sto > 1e-3:
            logger.info(f"         • Speicher:         {capex_sto:>15,.0f} EUR  ({capex_sto/capex_total*100:>5.1f}%)")


def diagnose_dashboard_data(workflow: Any) -> None:
    """
    Diagnose workflow data for dashboard display issues.

    This is a convenience wrapper around diagnose_workflow() that
    prints a formatted report to help troubleshoot dashboard issues.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow to diagnose

    Examples
    --------
    >>> from calion.io.notebook_helpers import diagnose_dashboard_data
    >>> diagnose_dashboard_data(workflow)
    🔍 Dashboard Data Diagnosis
    ====================================
    ✓ Primary result: RH
    ✓ Timeseries: 150 series
    ✓ Costs: 12 entries
    ✗ Design: No data
    ...
    """
    from calion.io.dashboard import diagnose_workflow

    logger.info("🔍 DASHBOARD DATA DIAGNOSIS")
    logger.info("="*70)

    diagnosis = diagnose_workflow(workflow)

    # Status overview
    logger.info("📊 Status:")
    logger.info(f"  Primary Result: {diagnosis['primary_result_type']}")
    logger.info(f"  {'✓' if diagnosis['has_timeseries'] else '✗'} Timeseries: {diagnosis.get('series_count', 0)} series")
    logger.info(f"  {'✓' if diagnosis['has_costs'] else '✗'} Costs: {diagnosis.get('cost_entries', 0)} entries")
    logger.info(f"  {'✓' if diagnosis['has_design'] else '✗'} Design: {diagnosis.get('design_components', 0)} components")

    # Issues
    if diagnosis['issues']:
        logger.info(f"⚠️  Issues Found ({len(diagnosis['issues'])}):")
        for i, issue in enumerate(diagnosis['issues'], 1):
            logger.info(f"  {i}. {issue}")

    # Recommendations
    if diagnosis['recommendations']:
        logger.info(f"💡 Recommendations ({len(diagnosis['recommendations'])}):")
        for i, rec in enumerate(diagnosis['recommendations'], 1):
            logger.info(f"  {i}. {rec}")
    else:
        logger.info("✅ No issues detected - dashboard should display correctly!")

    logger.info("="*70)

    return diagnosis


def create_and_display_dashboard(
    workflow: Any,
    title: Optional[str] = None,
    auto_display: bool = False,
    diagnose: bool = True,
) -> Any:
    """
    Create interactive Panel dashboard for workflow results.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow to visualize
    title : str, optional
        Dashboard title (auto-generated if None)
    auto_display : bool
        Whether to automatically display the dashboard in Jupyter
        (default: False, user must evaluate dashboard object)
    diagnose : bool, optional
        Run diagnostic check before creating dashboard (default: True)

    Returns
    -------
    Panel dashboard object

    Examples
    --------
    >>> dashboard = create_and_display_dashboard(workflow)
    >>> dashboard  # Display in Jupyter

    Or serve as webapp:
    >>> dashboard.servable()

    If dashboard is not displaying data:
    >>> diagnose_dashboard_data(workflow)
    """

    from calion.io.dashboard import create_dashboard, HAVE_PANEL

    if not HAVE_PANEL:
        logger.info("❌ Panel nicht installiert!")
        logger.info("   Installation: pip install panel holoviews bokeh plotly")
        return None

    # Auto-generate title
    if title is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = f"CALION Dashboard - {timestamp}"

    logger.info("🎛️ Erstelle interaktives Dashboard...")

    dashboard = create_dashboard(workflow, title=title, diagnose=diagnose)

    logger.info("✅ Dashboard erfolgreich erstellt!")
    logger.info("💡 Verwendung:")
    logger.info("   • Im Notebook: Evaluiere 'dashboard' in einer Zelle")
    logger.info("   • Als Webapp: panel serve notebook.ipynb --show")
    logger.info("   • Features: Tabs, interaktive Plots, Zoom/Pan/Hover")
    logger.info("💡 Troubleshooting:")
    logger.info("   • Wenn Daten nicht angezeigt werden: diagnose_dashboard_data(workflow)")
    logger.info("   • VS-Code: Panel funktioniert am besten im Browser")

    if auto_display:
        return dashboard
    else:
        return dashboard
