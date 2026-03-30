"""
Diagnostic utilities for the CALION Dashboard.

Provides functions to diagnose workflow data and identify potential issues.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from calion.logging_config import get_logger

logger = get_logger(__name__)


def diagnose_workflow(workflow: Any) -> Dict[str, Any]:
    """
    Diagnose workflow data for dashboard compatibility.

    This helper function checks if the workflow has the necessary data
    for dashboard display and provides detailed diagnostic information.

    Parameters
    ----------
    workflow : WorkflowResult
        The workflow result from run_workflow()

    Returns
    -------
    dict
        Diagnostic information with keys:
        - 'has_results': bool - at least one result available
        - 'has_timeseries': bool - timeseries data available
        - 'has_costs': bool - cost data available
        - 'has_design': bool - design data available
        - 'primary_result_type': str - which result is used (PF/RH/MPC)
        - 'issues': list of str - detected issues
        - 'recommendations': list of str - recommended actions

    Examples
    --------
    >>> from calion.io.dashboard import diagnose_workflow
    >>> diagnosis = diagnose_workflow(workflow)
    >>> if diagnosis['issues']:
    ...     print("Issues found:", diagnosis['issues'])
    """
    issues = []
    recommendations = []

    # Check which results are available
    has_pf = workflow.pf_result is not None
    has_rh = workflow.rh_result is not None
    has_mpc = workflow.mpc_result is not None
    has_any_result = has_pf or has_rh or has_mpc

    if not has_any_result:
        issues.append("No workflow results available (pf_result, rh_result, mpc_result all None)")
        recommendations.append("Run the workflow first with run_workflow()")
        return {
            'has_results': False,
            'has_timeseries': False,
            'has_costs': False,
            'has_design': False,
            'primary_result_type': None,
            'issues': issues,
            'recommendations': recommendations,
        }

    # Determine primary result (same logic as CALIONDashboard.__init__)
    if has_rh:
        primary_result = workflow.rh_result
        primary_label = "RH"
    elif has_mpc:
        primary_result = workflow.mpc_result
        primary_label = "MPC"
    elif has_pf:
        primary_result = workflow.pf_result
        primary_label = "PF"
    else:
        primary_result = None
        primary_label = None

    # Check timeseries data
    has_timeseries = False
    series_count = 0
    if primary_result and hasattr(primary_result, 'series') and primary_result.series:
        series_count = len(primary_result.series)
        has_timeseries = series_count > 0

        if not has_timeseries:
            issues.append(f"Primary result ({primary_label}) has empty series dictionary")
            recommendations.append("Check if optimization completed successfully")
            recommendations.append("Verify that result.series is populated by the solver")
    else:
        issues.append(f"Primary result ({primary_label}) has no series attribute or series is None")
        recommendations.append("Check workflow execution logs for errors")

    # Check cost data
    has_costs = False
    cost_entries = 0
    if primary_result and hasattr(primary_result, 'costs') and primary_result.costs:
        cost_entries = len([k for k, v in primary_result.costs.items()
                           if isinstance(v, (int, float)) and k.endswith('_EUR')])
        has_costs = cost_entries > 0

        if not has_costs:
            issues.append(f"Primary result ({primary_label}) has no cost entries with '_EUR' suffix")
            recommendations.append("Enable cost tracking in configuration")
            recommendations.append("Check if costs.include_* options are enabled")
    else:
        issues.append(f"Primary result ({primary_label}) has no costs attribute or costs is None")
        recommendations.append("Enable objective cost calculation in config")

    # Check design data
    has_design = False
    design_components = 0
    if workflow.design:
        if workflow.design.heat_pumps:
            design_components += len(workflow.design.heat_pumps)
        if workflow.design.storage:
            design_components += 1
        has_design = design_components > 0

        if not has_design:
            issues.append("Design exists but has no components (no heat_pumps or storage)")
            recommendations.append("Run a PF step to generate design data")
    else:
        issues.append("Workflow has no design data")
        recommendations.append("Include 'PF' in workflow steps to generate design")
        recommendations.append("Or load existing design with pf_design_json config")

    # VS-Code specific check
    try:
        import sys
        if 'debugpy' in sys.modules or 'IPython' in sys.modules:
            recommendations.append("HINWEIS: If running in VS-Code: Panel dashboards work best in browser")
            recommendations.append("         Alternative: Use 'panel serve notebook.ipynb' to view in browser")
    except Exception:
        pass

    logger.info(f"Dashboard diagnosis for {primary_label} result:")
    logger.info(f"  - Timeseries: {series_count} series")
    logger.info(f"  - Costs: {cost_entries} entries")
    logger.info(f"  - Design: {design_components} components")

    return {
        'has_results': has_any_result,
        'has_pf': has_pf,
        'has_rh': has_rh,
        'has_mpc': has_mpc,
        'has_timeseries': has_timeseries,
        'has_costs': has_costs,
        'has_design': has_design,
        'primary_result_type': primary_label,
        'series_count': series_count,
        'cost_entries': cost_entries,
        'design_components': design_components,
        'issues': issues,
        'recommendations': recommendations,
    }


def print_diagnosis(diagnosis: Dict[str, Any]) -> None:
    """
    Print formatted diagnostic results.

    Parameters
    ----------
    diagnosis : dict
        Diagnostic results from diagnose_workflow()
    """
    logger.info(f"\nDashboard Diagnosis:")
    logger.info(
        "  Available Results: PF=%s, RH=%s, MPC=%s",
        diagnosis.get("has_pf", False),
        diagnosis.get("has_rh", False),
        diagnosis.get("has_mpc", False),
    )
    logger.info(f"  Primary Result: {diagnosis['primary_result_type']}")
    logger.info(
        "  [OK] Timeseries: %d series" if diagnosis["has_timeseries"] else "  [!!] Timeseries: No data",
        *([diagnosis["series_count"]] if diagnosis["has_timeseries"] else []),
    )
    logger.info(
        "  [OK] Costs: %d entries" if diagnosis["has_costs"] else "  [!!] Costs: No data",
        *([diagnosis["cost_entries"]] if diagnosis["has_costs"] else []),
    )
    logger.info(
        "  [OK] Design: %d components" if diagnosis["has_design"] else "  [!!] Design: No data",
        *([diagnosis["design_components"]] if diagnosis["has_design"] else []),
    )

    if diagnosis['issues']:
        logger.info(f"\nWARNING: Issues found:")
        for issue in diagnosis['issues']:
            logger.info(f"         • {issue}")

    if diagnosis['recommendations']:
        logger.info(f"\nHINWEIS: Recommendations:")
        for rec in diagnosis['recommendations']:
            logger.info(f"         • {rec}")
