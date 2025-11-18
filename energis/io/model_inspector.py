"""Model inspection and export utilities for Pyomo optimization models.

This module provides functionality to export Pyomo model structure (variables,
parameters, constraints, objectives) to Excel and Markdown formats for review
before solver execution.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Mapping, Optional, Sequence
import os
import json

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:
    HAVE_PYOMO = False
    pyo = None


__all__ = [
    "export_model_structure",
    "inspect_pyomo_model",
]


def _safe_value(obj: Any, default: str = "N/A") -> Any:
    """Safely extract value from Pyomo object."""
    if not HAVE_PYOMO:
        return default

    try:
        if hasattr(obj, 'value'):
            val = pyo.value(obj)
            if val is None:
                return default
            return val
        return obj
    except Exception:
        return default


def _safe_bounds(var: Any) -> tuple[Any, Any]:
    """Safely extract bounds from Pyomo variable."""
    if not HAVE_PYOMO:
        return (None, None)

    try:
        lb = var.lb if hasattr(var, 'lb') else None
        ub = var.ub if hasattr(var, 'ub') else None
        return (lb, ub)
    except Exception:
        return (None, None)


def _format_constraint_expression(constraint: Any, max_length: int = 200) -> str:
    """Format constraint expression for display."""
    if not HAVE_PYOMO:
        return "Pyomo not available"

    try:
        expr_str = str(constraint.expr)
        if len(expr_str) > max_length:
            return expr_str[:max_length-3] + "..."
        return expr_str
    except Exception:
        return "Error formatting expression"


def inspect_pyomo_model(model: Any) -> Dict[str, Any]:
    """Inspect Pyomo model and extract structure information.

    Args:
        model: Pyomo ConcreteModel or AbstractModel

    Returns:
        Dictionary with model structure:
            - parameters: List of parameter dictionaries
            - variables: List of variable dictionaries
            - constraints: List of constraint dictionaries
            - objectives: List of objective dictionaries
            - sets: List of set dictionaries
            - summary: Model summary statistics
    """
    if not HAVE_PYOMO or model is None:
        return {
            "parameters": [],
            "variables": [],
            "constraints": [],
            "objectives": [],
            "sets": [],
            "summary": {"error": "Pyomo not available or model is None"}
        }

    inspection = {
        "parameters": [],
        "variables": [],
        "constraints": [],
        "objectives": [],
        "sets": [],
        "summary": {}
    }

    # Extract Sets
    for component in model.component_objects(pyo.Set, active=True):
        set_info = {
            "name": str(component.name),
            "size": len(component) if component.is_finite() else "infinite",
            "type": "Set",
        }

        # For small sets, show elements
        if component.is_finite() and len(component) <= 20:
            set_info["elements"] = list(component)

        inspection["sets"].append(set_info)

    # Extract Parameters
    for component in model.component_objects(pyo.Param, active=True):
        param_info = {
            "name": str(component.name),
            "type": "Parameter",
            "indexed": component.is_indexed(),
            "size": len(component) if component.is_indexed() else 1,
        }

        # Get domain info
        try:
            if hasattr(component, 'domain'):
                param_info["domain"] = str(component.domain)
        except Exception:
            pass

        # For scalar or small indexed params, get values
        if not component.is_indexed():
            param_info["value"] = _safe_value(component)
        elif len(component) <= 10:
            param_info["values"] = {str(k): _safe_value(component[k]) for k in component}
        else:
            # Sample first few values
            keys = list(component.keys())[:5]
            param_info["sample_values"] = {str(k): _safe_value(component[k]) for k in keys}
            param_info["note"] = f"Showing 5 of {len(component)} values"

        inspection["parameters"].append(param_info)

    # Extract Variables
    for component in model.component_objects(pyo.Var, active=True):
        var_info = {
            "name": str(component.name),
            "type": "Variable",
            "indexed": component.is_indexed(),
            "size": len(component) if component.is_indexed() else 1,
        }

        # Get domain info
        try:
            if hasattr(component, 'domain'):
                domain_str = str(component.domain)
                if 'NonNegativeReals' in domain_str:
                    var_info["domain"] = "NonNegativeReals"
                elif 'Binary' in domain_str:
                    var_info["domain"] = "Binary"
                elif 'Reals' in domain_str:
                    var_info["domain"] = "Reals"
                else:
                    var_info["domain"] = domain_str
        except Exception:
            pass

        # Get bounds for scalar or sample for indexed
        if not component.is_indexed():
            lb, ub = _safe_bounds(component)
            var_info["lower_bound"] = lb
            var_info["upper_bound"] = ub
        elif len(component) <= 10:
            var_info["bounds"] = {str(k): _safe_bounds(component[k]) for k in component}
        else:
            # Sample first few bounds
            keys = list(component.keys())[:5]
            var_info["sample_bounds"] = {str(k): _safe_bounds(component[k]) for k in keys}
            var_info["note"] = f"Showing 5 of {len(component)} variables"

        inspection["variables"].append(var_info)

    # Extract Constraints
    for component in model.component_objects(pyo.Constraint, active=True):
        constr_info = {
            "name": str(component.name),
            "type": "Constraint",
            "indexed": component.is_indexed(),
            "size": len(component) if component.is_indexed() else 1,
        }

        # Get expression for scalar or sample for indexed
        if not component.is_indexed():
            constr_info["expression"] = _format_constraint_expression(component)
        elif len(component) <= 5:
            constr_info["expressions"] = {
                str(k): _format_constraint_expression(component[k])
                for k in component
            }
        else:
            # Sample first few expressions
            keys = list(component.keys())[:3]
            constr_info["sample_expressions"] = {
                str(k): _format_constraint_expression(component[k])
                for k in keys
            }
            constr_info["note"] = f"Showing 3 of {len(component)} constraints"

        inspection["constraints"].append(constr_info)

    # Extract Objectives
    for component in model.component_objects(pyo.Objective, active=True):
        obj_info = {
            "name": str(component.name),
            "type": "Objective",
            "sense": str(component.sense) if hasattr(component, 'sense') else "minimize",
            "indexed": component.is_indexed(),
        }

        # Get expression
        if not component.is_indexed():
            obj_info["expression"] = _format_constraint_expression(component)

        inspection["objectives"].append(obj_info)

    # Summary statistics
    inspection["summary"] = {
        "model_name": str(model.name) if hasattr(model, 'name') else "Unknown",
        "num_sets": len(inspection["sets"]),
        "num_parameters": len(inspection["parameters"]),
        "num_variables": sum(p["size"] for p in inspection["variables"]),
        "num_constraints": sum(c["size"] for c in inspection["constraints"]),
        "num_objectives": len(inspection["objectives"]),
        "variable_types": len(inspection["variables"]),
        "constraint_types": len(inspection["constraints"]),
    }

    return inspection


def _write_markdown_report(inspection: Dict[str, Any], filepath: str) -> None:
    """Write model inspection to Markdown file."""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# Pyomo Model Structure Export\n\n")

        # Summary
        f.write("## Summary\n\n")
        summary = inspection.get("summary", {})
        f.write(f"- **Model Name**: {summary.get('model_name', 'N/A')}\n")
        f.write(f"- **Sets**: {summary.get('num_sets', 0)}\n")
        f.write(f"- **Parameters**: {summary.get('num_parameters', 0)}\n")
        f.write(f"- **Variables**: {summary.get('num_variables', 0)} ({summary.get('variable_types', 0)} types)\n")
        f.write(f"- **Constraints**: {summary.get('num_constraints', 0)} ({summary.get('constraint_types', 0)} types)\n")
        f.write(f"- **Objectives**: {summary.get('num_objectives', 0)}\n\n")

        # Sets
        if inspection.get("sets"):
            f.write("## Sets\n\n")
            f.write("| Name | Size | Elements |\n")
            f.write("|------|------|----------|\n")
            for s in inspection["sets"]:
                elements = s.get("elements", "...")
                if isinstance(elements, list):
                    elements = ", ".join(str(e) for e in elements[:10])
                f.write(f"| {s['name']} | {s.get('size', 'N/A')} | {elements} |\n")
            f.write("\n")

        # Parameters
        if inspection.get("parameters"):
            f.write("## Parameters\n\n")
            f.write("| Name | Type | Size | Domain | Value/Sample |\n")
            f.write("|------|------|------|--------|-------------|\n")
            for p in inspection["parameters"]:
                value_str = ""
                if "value" in p:
                    value_str = str(p["value"])
                elif "sample_values" in p:
                    samples = p["sample_values"]
                    value_str = ", ".join(f"{k}={v}" for k, v in list(samples.items())[:3])
                    if len(samples) > 3:
                        value_str += ", ..."

                f.write(f"| {p['name']} | {p.get('type', 'N/A')} | {p.get('size', 1)} | "
                       f"{p.get('domain', 'N/A')} | {value_str} |\n")
            f.write("\n")

        # Variables
        if inspection.get("variables"):
            f.write("## Variables\n\n")
            f.write("| Name | Type | Size | Domain | Bounds |\n")
            f.write("|------|------|------|--------|--------|\n")
            for v in inspection["variables"]:
                bounds_str = ""
                if "lower_bound" in v and "upper_bound" in v:
                    lb = v["lower_bound"] if v["lower_bound"] is not None else "-∞"
                    ub = v["upper_bound"] if v["upper_bound"] is not None else "+∞"
                    bounds_str = f"[{lb}, {ub}]"
                elif "sample_bounds" in v:
                    samples = v["sample_bounds"]
                    first_key = list(samples.keys())[0]
                    lb, ub = samples[first_key]
                    lb = lb if lb is not None else "-∞"
                    ub = ub if ub is not None else "+∞"
                    bounds_str = f"Example: [{lb}, {ub}]"

                f.write(f"| {v['name']} | {v.get('type', 'N/A')} | {v.get('size', 1)} | "
                       f"{v.get('domain', 'N/A')} | {bounds_str} |\n")
            f.write("\n")

        # Constraints
        if inspection.get("constraints"):
            f.write("## Constraints\n\n")
            for c in inspection["constraints"]:
                f.write(f"### {c['name']}\n\n")
                f.write(f"- **Type**: {c.get('type', 'N/A')}\n")
                f.write(f"- **Size**: {c.get('size', 1)}\n")

                if "expression" in c:
                    f.write(f"- **Expression**: `{c['expression']}`\n")
                elif "sample_expressions" in c:
                    f.write("- **Sample Expressions**:\n")
                    for k, expr in c["sample_expressions"].items():
                        f.write(f"  - `{k}`: {expr}\n")
                    if c.get("note"):
                        f.write(f"  - *{c['note']}*\n")
                f.write("\n")

        # Objectives
        if inspection.get("objectives"):
            f.write("## Objectives\n\n")
            for o in inspection["objectives"]:
                f.write(f"### {o['name']}\n\n")
                f.write(f"- **Sense**: {o.get('sense', 'minimize')}\n")
                if "expression" in o:
                    f.write(f"- **Expression**: `{o['expression']}`\n")
                f.write("\n")


def _write_excel_report(inspection: Dict[str, Any], filepath: str) -> None:
    """Write model inspection to Excel file."""

    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
    except ImportError:
        # Fallback to simple xlsx if openpyxl not available
        from energis.io.exporter import _write_simple_xlsx

        sheets = {}

        # Summary sheet
        summary_rows = [["Metric", "Value"]]
        for k, v in inspection.get("summary", {}).items():
            summary_rows.append([k, v])
        sheets["Summary"] = summary_rows

        # Parameters sheet
        param_rows = [["Name", "Type", "Size", "Domain", "Value/Sample"]]
        for p in inspection.get("parameters", []):
            value_str = str(p.get("value", p.get("sample_values", p.get("note", ""))))
            param_rows.append([
                p.get("name", ""),
                p.get("type", ""),
                p.get("size", ""),
                p.get("domain", ""),
                value_str
            ])
        sheets["Parameters"] = param_rows

        # Variables sheet
        var_rows = [["Name", "Type", "Size", "Domain", "Bounds"]]
        for v in inspection.get("variables", []):
            bounds_str = ""
            if "lower_bound" in v and "upper_bound" in v:
                bounds_str = f"[{v['lower_bound']}, {v['upper_bound']}]"
            elif "sample_bounds" in v:
                bounds_str = str(v["sample_bounds"])

            var_rows.append([
                v.get("name", ""),
                v.get("type", ""),
                v.get("size", ""),
                v.get("domain", ""),
                bounds_str
            ])
        sheets["Variables"] = var_rows

        # Constraints sheet
        constr_rows = [["Name", "Type", "Size", "Expression/Note"]]
        for c in inspection.get("constraints", []):
            expr_str = c.get("expression", c.get("note", ""))
            if "sample_expressions" in c:
                expr_str = str(c["sample_expressions"])

            constr_rows.append([
                c.get("name", ""),
                c.get("type", ""),
                c.get("size", ""),
                expr_str
            ])
        sheets["Constraints"] = constr_rows

        # Objectives sheet
        obj_rows = [["Name", "Sense", "Expression"]]
        for o in inspection.get("objectives", []):
            obj_rows.append([
                o.get("name", ""),
                o.get("sense", ""),
                o.get("expression", "")
            ])
        sheets["Objectives"] = obj_rows

        _write_simple_xlsx(filepath, sheets)
        return

    # Use openpyxl for better formatting
    wb = Workbook()

    # Summary sheet
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.append(["Metric", "Value"])
    for k, v in inspection.get("summary", {}).items():
        ws_summary.append([k, v])

    # Parameters sheet
    ws_params = wb.create_sheet("Parameters")
    ws_params.append(["Name", "Type", "Size", "Domain", "Value/Sample"])
    for p in inspection.get("parameters", []):
        value_str = str(p.get("value", p.get("sample_values", p.get("note", ""))))
        ws_params.append([
            p.get("name", ""),
            p.get("type", ""),
            p.get("size", ""),
            p.get("domain", ""),
            value_str
        ])

    # Variables sheet
    ws_vars = wb.create_sheet("Variables")
    ws_vars.append(["Name", "Type", "Size", "Domain", "Lower Bound", "Upper Bound", "Note"])
    for v in inspection.get("variables", []):
        lb = v.get("lower_bound", "")
        ub = v.get("upper_bound", "")
        note = v.get("note", "")

        if "sample_bounds" in v:
            samples = v["sample_bounds"]
            first_key = list(samples.keys())[0] if samples else ""
            if first_key:
                lb, ub = samples[first_key]
            note = v.get("note", "")

        ws_vars.append([
            v.get("name", ""),
            v.get("type", ""),
            v.get("size", ""),
            v.get("domain", ""),
            lb if lb is not None else "",
            ub if ub is not None else "",
            note
        ])

    # Constraints sheet
    ws_constr = wb.create_sheet("Constraints")
    ws_constr.append(["Name", "Type", "Size", "Expression", "Note"])
    for c in inspection.get("constraints", []):
        expr_str = c.get("expression", "")
        note = c.get("note", "")

        if "sample_expressions" in c:
            # Show first sample expression
            samples = c["sample_expressions"]
            first_key = list(samples.keys())[0] if samples else ""
            if first_key:
                expr_str = f"{first_key}: {samples[first_key]}"

        ws_constr.append([
            c.get("name", ""),
            c.get("type", ""),
            c.get("size", ""),
            expr_str,
            note
        ])

    # Objectives sheet
    ws_obj = wb.create_sheet("Objectives")
    ws_obj.append(["Name", "Sense", "Expression"])
    for o in inspection.get("objectives", []):
        ws_obj.append([
            o.get("name", ""),
            o.get("sense", ""),
            o.get("expression", "")
        ])

    # Auto-adjust column widths
    for ws in wb.worksheets:
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 100)
            ws.column_dimensions[column_letter].width = adjusted_width

    wb.save(filepath)


def export_model_structure(
    model: Any,
    output_dir: str,
    prefix: str = "model_structure"
) -> Dict[str, str]:
    """Export Pyomo model structure to Excel and Markdown files.

    Args:
        model: Pyomo ConcreteModel to export
        output_dir: Directory for output files
        prefix: Filename prefix for exports

    Returns:
        Dictionary with paths to created files:
            - excel_path: Path to Excel export
            - markdown_path: Path to Markdown export
            - json_path: Path to JSON export
    """
    os.makedirs(output_dir, exist_ok=True)

    # Inspect model
    print(f"[MODEL_EXPORT] Inspecting Pyomo model...")
    inspection = inspect_pyomo_model(model)

    # Create output paths
    excel_path = os.path.join(output_dir, f"{prefix}.xlsx")
    markdown_path = os.path.join(output_dir, f"{prefix}.md")
    json_path = os.path.join(output_dir, f"{prefix}.json")

    # Export to Excel
    print(f"[MODEL_EXPORT] Writing Excel report: {excel_path}")
    _write_excel_report(inspection, excel_path)

    # Export to Markdown
    print(f"[MODEL_EXPORT] Writing Markdown report: {markdown_path}")
    _write_markdown_report(inspection, markdown_path)

    # Export to JSON (full inspection data)
    print(f"[MODEL_EXPORT] Writing JSON report: {json_path}")
    # Make JSON serializable
    json_safe_inspection = json.loads(json.dumps(inspection, default=str))
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_safe_inspection, f, indent=2)

    summary = inspection.get("summary", {})
    print(f"[MODEL_EXPORT] Model exported successfully:")
    print(f"  - Variables: {summary.get('num_variables', 0)}")
    print(f"  - Constraints: {summary.get('num_constraints', 0)}")
    print(f"  - Parameters: {summary.get('num_parameters', 0)}")
    print(f"  - Objectives: {summary.get('num_objectives', 0)}")

    return {
        "excel_path": excel_path,
        "markdown_path": markdown_path,
        "json_path": json_path,
    }
