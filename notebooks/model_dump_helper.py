"""Utilities to inspect Pyomo models from notebooks.

The helpers below make it easy to dump variables, parameters, constraints
and objectives either to the console (sorted) or into a JSON file so the
model structure can be reviewed before running a solve.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, IO, Iterable, Tuple

import pyomo.environ as pyo
from pyomo.core.base.component import ActiveComponent

Component = ActiveComponent


def _iter_items(component: Component) -> Iterable[Tuple[Any, Any]]:
    if component.is_indexed():
        for idx in sorted(component.keys(), key=str):
            yield idx, component[idx]
    else:
        yield None, component


def dump_model_structure(model: Any, stream: IO[str] | None = None) -> None:
    """Print a sorted, human-readable overview of a Pyomo model.

    Parameters
    ----------
    model:
        A built Pyomo model.
    stream:
        Target stream (defaults to ``sys.stdout``). Provide a file handle to
        write into a text file.
    """

    stream = stream or sys.stdout

    def _w(line: str = "") -> None:
        stream.write(f"{line}\n")

    _w("=== Parameter ===")
    for name, param in sorted(
        model.component_map(pyo.Param, active=True).items(), key=lambda kv: kv[0]
    ):
        _w(f"- {name}: index_set={param.index_set()}")
        for idx, par_data in _iter_items(param):
            _w(f"    [{idx}] value={par_data.value}")

    _w("\n=== Variablen ===")
    for name, var in sorted(
        model.component_map(pyo.Var, active=True).items(), key=lambda kv: kv[0]
    ):
        _w(f"- {name}: index_set={var.index_set()}, domain={var.domain}")
        for idx, var_data in _iter_items(var):
            lb, ub = var_data.bounds
            _w(f"    [{idx}] bounds=({lb}, {ub}) value={var_data.value}")

    _w("\n=== Nebenbedingungen ===")
    for name, cons in sorted(
        model.component_map(pyo.Constraint, active=True).items(), key=lambda kv: kv[0]
    ):
        _w(f"- {name}: index_set={cons.index_set()}")
        for idx, con_data in _iter_items(cons):
            lb = con_data.lower if con_data.has_lb() else None
            ub = con_data.upper if con_data.has_ub() else None
            expr = con_data.body
            _w(f"    [{idx}] {lb if lb is not None else ''} <= {expr} <= {ub if ub is not None else ''}")

    _w("\n=== Zielfunktionen ===")
    for name, obj in sorted(
        model.component_map(pyo.Objective, active=True).items(), key=lambda kv: kv[0]
    ):
        sense = "minimize" if obj.sense == pyo.minimize else "maximize"
        _w(f"- {name} ({sense}): {obj.expr}")


def model_to_dict(model: Any) -> Dict[str, Any]:
    """Return a JSON-friendly dictionary of the model structure."""

    data: Dict[str, Any] = {
        "parameters": {},
        "variables": {},
        "constraints": {},
        "objectives": {},
    }

    for name, param in sorted(
        model.component_map(pyo.Param, active=True).items(), key=lambda kv: kv[0]
    ):
        if param.is_indexed():
            values = {str(idx): param[idx].value for idx in param}
        else:
            values = param.value
        data["parameters"][name] = {
            "index_set": str(param.index_set()),
            "values": values,
        }

    for name, var in sorted(
        model.component_map(pyo.Var, active=True).items(), key=lambda kv: kv[0]
    ):
        if var.is_indexed():
            bounds = {str(idx): var[idx].bounds for idx in var}
        else:
            bounds = var.bounds
        data["variables"][name] = {
            "index_set": str(var.index_set()),
            "bounds": bounds,
            "domain": str(var.domain),
        }

    for name, cons in sorted(
        model.component_map(pyo.Constraint, active=True).items(), key=lambda kv: kv[0]
    ):
        if cons.is_indexed():
            expr = {str(idx): str(cons[idx].expr) for idx in cons}
        else:
            expr = str(cons.expr)
        data["constraints"][name] = {
            "index_set": str(cons.index_set()),
            "expr": expr,
        }

    for name, obj in sorted(
        model.component_map(pyo.Objective, active=True).items(), key=lambda kv: kv[0]
    ):
        data["objectives"][name] = {
            "sense": "minimize" if obj.sense == pyo.minimize else "maximize",
            "expr": str(obj.expr),
        }

    return data


def export_model_json(model: Any, path: str) -> None:
    """Write :func:`model_to_dict` output to a JSON file."""

    with open(path, "w", encoding="utf-8") as f:
        json.dump(model_to_dict(model), f, ensure_ascii=False, indent=2)


__all__ = ["dump_model_structure", "model_to_dict", "export_model_json"]
