"""Workflow result export to files (Excel, CSV, plots, JSON).

Provides :func:`export_workflow_results` – the unified export entry point –
and the thermal-network CSV writer ``_write_network_data_to_dir``.
"""

from __future__ import annotations

import json
import os
import time
from collections import OrderedDict
from typing import Any

import pandas as pd

from calion.io.exporter import export_scenario_bundle, write_timeseries_csv
from calion.io.plotter import export_plots
from calion.logging_config import get_logger

from .types import WorkflowResult
from .utilities.timeseries_utils import _slugify

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    HAVE_PYOMO = True
except Exception:  # pragma: no cover
    HAVE_PYOMO = False


def _write_network_data_to_dir(network_data: dict[str, Any], outdir: str) -> dict[str, str]:
    """Write thermal network results from solver_meta['network_data'] to outdir."""
    if not network_data:
        return {}

    net_dir = os.path.join(outdir, "thermal_network")
    os.makedirs(net_dir, exist_ok=True)
    written: dict[str, str] = {}

    # Node timeseries
    node_ts: dict[str, list] = {}
    node_summary: dict[str, dict] = {}
    for node_id, node_info in network_data.get('nodes', {}).items():
        for key in ('T_supply_series', 'T_return_series'):
            col = f"{node_id}_{key.replace('_series', '')}"
            if key in node_info:
                node_ts[col] = node_info[key]
        node_summary[node_id] = {
            k: v for k, v in node_info.items()
            if not k.endswith('_series') and k not in ('id',)
        }

    if node_ts:
        node_csv = os.path.join(net_dir, "nodes_timeseries.csv")
        pd.DataFrame(node_ts).to_csv(node_csv, sep=';', index=True)
        written['nodes_timeseries'] = node_csv
        logger.info("[EXPORT] Thermal network nodes -> %s", node_csv)

    # Pipe timeseries
    pipe_ts: dict[str, list] = {}
    pipe_summary: dict[str, dict] = {}
    for pipe_id, pipe_info in network_data.get('pipes', {}).items():
        for key in ('m_dot_series', 'velocity_series', 'delta_p_series',
                    'Q_loss_series', 'T_supply_out_series', 'T_return_out_series'):
            col = f"{pipe_id}_{key.replace('_series', '')}"
            if key in pipe_info:
                pipe_ts[col] = pipe_info[key]
        pipe_summary[pipe_id] = {
            k: v for k, v in pipe_info.items()
            if not k.endswith('_series') and k not in ('id',)
        }

    if pipe_ts:
        pipe_csv = os.path.join(net_dir, "pipes_timeseries.csv")
        pd.DataFrame(pipe_ts).to_csv(pipe_csv, sep=';', index=True)
        written['pipes_timeseries'] = pipe_csv
        logger.info("[EXPORT] Thermal network pipes  -> %s", pipe_csv)

    # Summary JSON
    summary = {
        'nodes': node_summary,
        'pipes': pipe_summary,
        'network': network_data.get('summary', {}),
    }
    summary_path = os.path.join(net_dir, "network_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, default=str)
    written['network_summary'] = summary_path
    logger.info("[EXPORT] Thermal network summary -> %s", summary_path)

    return written


def export_workflow_results(
    workflow: WorkflowResult,
    outdir: str | None = None,
    save_lp: bool = False,
) -> dict[str, Any]:
    """Export workflow results to files (Excel, CSV, plots, JSON).

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow result from run_workflow()
    outdir : str, optional
        Output directory path. If None, creates timestamped directory in exports/
    save_lp : bool, optional
        Copy the MILP model LP file into {outdir}/solver/model.lp. Default: False.

    Returns
    -------
    dict
        Dictionary with export paths and metadata
    """

    if outdir is None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        scenario_cfg = workflow.config.get("scenario", {})
        title = str(scenario_cfg.get("title", "Workflow"))
        run_mode = str(scenario_cfg.get("run_mode", "UNKNOWN"))
        tag = scenario_cfg.get("tag") or f"{run_mode}-{title}"
        slug = _slugify(tag)
        outdir = os.path.join("exports", f"{stamp}_{slug}")

    os.makedirs(outdir, exist_ok=True)

    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None
    has_mpc = workflow.mpc_result is not None

    timeseries_sections = []
    cost_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()

    if has_pf and workflow.pf_result:
        pf_input_series: OrderedDict[str, list[float]] = OrderedDict(
            (col, list(workflow.pf_result.table[col])) for col in workflow.pf_result.table.columns
        )
        pf_result_series: OrderedDict[str, list[float]] = OrderedDict(
            (name, list(values)) for name, values in workflow.pf_result.series.items()
        )

        timeseries_sections.append({
            "label": "PF_input",
            "timestamps": list(workflow.pf_result.table.index),
            "series": pf_input_series,
        })
        timeseries_sections.append({
            "label": "PF_result",
            "timestamps": list(workflow.pf_result.table.index),
            "series": pf_result_series,
        })

        if workflow.pf_result.costs:
            cost_sections["PF"] = OrderedDict(
                (str(key), value) for key, value in workflow.pf_result.costs.items()
            )

        pf_csv = os.path.join(outdir, "pf_timeseries.csv")
        write_timeseries_csv(pf_csv, workflow.pf_result.table, workflow.pf_result.series)

    if has_rh and workflow.rh_result:
        rh_result_series: OrderedDict[str, list[float]] = OrderedDict(
            (name, list(values)) for name, values in workflow.rh_result.series.items()
        )

        timeseries_sections.append({
            "label": "RH_result",
            "timestamps": list(workflow.rh_result.table.index),
            "series": rh_result_series,
        })

        if workflow.rh_result.costs:
            cost_sections["RH"] = OrderedDict(
                (str(key), value) for key, value in workflow.rh_result.costs.items()
            )

        rh_csv = os.path.join(outdir, "rh_timeseries.csv")
        write_timeseries_csv(rh_csv, workflow.rh_result.table, workflow.rh_result.series)

    if has_mpc and workflow.mpc_result:
        mpc_result_series: OrderedDict[str, list[float]] = OrderedDict(
            (name, list(values)) for name, values in workflow.mpc_result.series.items()
        )

        timeseries_sections.append({
            "label": "MPC_result",
            "timestamps": list(workflow.mpc_result.table.index),
            "series": mpc_result_series,
        })

        if workflow.mpc_result.costs:
            cost_sections["MPC"] = OrderedDict(
                (str(key), value) for key, value in workflow.mpc_result.costs.items()
            )

        mpc_csv = os.path.join(outdir, "mpc_timeseries.csv")
        write_timeseries_csv(mpc_csv, workflow.mpc_result.table, workflow.mpc_result.series)

    design_export: dict[str, Any] = {}
    design_json_path: str | None = None
    if workflow.design:
        design_export["heat_pumps"] = workflow.design.heat_pumps
        if workflow.design.storage:
            design_export["storage"] = workflow.design.storage

        design_json_path = os.path.join(outdir, "design.json")
        with open(design_json_path, "w", encoding="utf-8") as f:
            json.dump(design_export, f, indent=2, default=str)

    scenario_cfg = workflow.config.get("scenario", {})
    site_cfg = workflow.config.get("site", {})
    run_cfg = workflow.config.get("run", {})

    stamp = time.strftime("%Y%m%d_%H%M%S")
    dt_h = float(run_cfg.get("dt_h", 1.0))

    metadata_sections: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    metadata_sections["run"] = OrderedDict([
        ("timestamp", stamp),
        ("output_directory", outdir),
        ("dt_h", dt_h),
        ("workflow_steps", list(workflow.plan.steps)),
        ("pyomo_available", HAVE_PYOMO),
    ])

    if isinstance(scenario_cfg, dict):
        metadata_sections["scenario"] = OrderedDict((key, value) for key, value in scenario_cfg.items())

    if isinstance(site_cfg, dict):
        metadata_sections["site"] = OrderedDict((key, value) for key, value in site_cfg.items())

    title = str(scenario_cfg.get("title", "Workflow"))
    run_mode = str(scenario_cfg.get("run_mode", "UNKNOWN"))
    tag = scenario_cfg.get("tag") or f"{run_mode}-{title}"

    flags = OrderedDict([
        ("has_pf", has_pf),
        ("has_rh", has_rh),
        ("has_mpc", has_mpc),
        ("has_design", bool(design_export)),
    ])

    manifest_data = OrderedDict([
        ("scenario_title", title),
        ("run_mode", run_mode),
        ("workflow_steps", list(workflow.plan.steps)),
        ("flags", flags),
        ("export_timestamp", stamp),
        ("slug", _slugify(tag)),
        ("output_directory", outdir),
    ])

    bundle_paths = dict(
        export_scenario_bundle(
            outdir,
            meta_sections=metadata_sections,
            timeseries_sections=timeseries_sections,
            cost_sections=cost_sections,
            design=design_export,
            manifest=manifest_data,
        )
    )

    plot_files = []
    try:
        if has_pf and workflow.pf_result:
            pf_summary = workflow.pf_result.summary if hasattr(workflow.pf_result, 'summary') else {}
            pf_plots = export_plots(
                outdir,
                workflow.pf_result.table,
                workflow.pf_result.series,
                pf_summary,
            )
            plot_files.extend(pf_plots)
    except Exception as exc:
        logger.info(f"[EXPORT] Plot export skipped: {exc}")

    # Thermal network CSV
    network_files: dict[str, str] = {}
    active_result = workflow.mpc_result or workflow.rh_result or workflow.pf_result
    # RollingHorizonResult has no solver field; fall back to the last window's solver dict
    if active_result is not None:
        _active_solver: dict[str, Any] = getattr(active_result, 'solver', None) or {}
        if not _active_solver:
            from .types import RollingHorizonResult as _RHR
            if isinstance(active_result, _RHR) and active_result.windows:
                _active_solver = active_result.windows[-1].solver or {}
        network_data = _active_solver.get('network_data', {})
        if network_data:
            try:
                network_files = _write_network_data_to_dir(network_data, outdir)
                logger.info(
                    "[EXPORT] Thermal network: %d files written to %s/thermal_network/",
                    len(network_files), outdir,
                )
            except Exception as exc:
                logger.warning("[EXPORT] Thermal network CSV export failed: %s", exc)

    # Optional LP file copy
    lp_path_in_result: str | None = None
    if save_lp and active_result is not None:
        src_lp = _active_solver.get('export_files', {}).get('solver_lp_file')
        if src_lp and os.path.isfile(src_lp):
            import shutil as _shutil
            solver_dir = os.path.join(outdir, "solver")
            os.makedirs(solver_dir, exist_ok=True)
            dest_lp = os.path.join(solver_dir, "model.lp")
            try:
                _shutil.copy2(src_lp, dest_lp)
                lp_path_in_result = dest_lp
                logger.info("[EXPORT] LP model copied → %s", dest_lp)
            except Exception as exc:
                logger.warning("[EXPORT] Could not copy LP file: %s", exc)
        else:
            logger.warning(
                "[EXPORT] --save-lp requested but no LP file found in solver results. "
                "Set output.export_solver_solution: true in config to generate it."
            )

    # Write costs.json — flat dict keyed without section prefix (for comparison scripts)
    costs_json_path = os.path.join(outdir, "costs.json")
    flat_costs: dict = {}
    for _section, section_costs in cost_sections.items():
        for key, val in section_costs.items():
            # Strip "objective." / "grid." prefixes so keys are plain names
            clean_key = key.split(".", 1)[-1] if "." in key else key
            flat_costs[clean_key] = val
    if flat_costs:
        with open(costs_json_path, "w", encoding="utf-8") as f:
            json.dump({"PF": flat_costs}, f, indent=2, default=str)
    else:
        costs_json_path = None

    result_dict = {
        "outdir": outdir,
        "scenario_xlsx": bundle_paths.get("scenario_xlsx"),
        "costs_json": costs_json_path or bundle_paths.get("costs_json"),
        "design_json": design_json_path or bundle_paths.get("design_json") or bundle_paths.get("pf_design_json"),
        "meta_json": bundle_paths.get("meta_json"),
        "manifest_json": bundle_paths.get("manifest_json"),
        "plots": plot_files,
        "network_files": network_files,
        "lp_file": lp_path_in_result,
        "costs": {},
    }

    if has_mpc and workflow.mpc_result and workflow.mpc_result.costs:
        result_dict["costs"] = workflow.mpc_result.costs
    elif has_rh and workflow.rh_result and workflow.rh_result.costs:
        result_dict["costs"] = workflow.rh_result.costs
    elif has_pf and workflow.pf_result and workflow.pf_result.costs:
        result_dict["costs"] = workflow.pf_result.costs

    return result_dict
