"""v12 B2/B2b test helper: 2-node sub-network cut from the real Stadtbach config.

j_hkw (primary): gas CHP `hkw` + own local demand (column Hoher_Weg_MW)   -> exercises B2b (primary own demand)
j_man (secondary, bidirectional feeder hkw_to_man): cheap waste-heat source `wh_man` (cap_mw) + demand MAN_MW
   -> MAN demand < cap  => surplus flows j_man -> j_hkw (reverse);  MAN demand > cap => forward flow.  (B2)
Builds the model with the production code path (calion.run.workflow._build_workflow_inputs + calion.run.solver.build_model),
solves with Gurobi and returns the hourly system residual
  R(t) = sum gen - sum demand - sum pipe losses - sum dump - (charge - discharge)
read from the solved Pyomo model.
"""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pyomo.environ as pyo
import yaml

ROOT = Path(__file__).resolve().parents[2]
TOPO = ROOT / "configs" / "paper_2" / "Stadtbach_topo.yaml"


def make_cfg(cap_mw: float = 6.0, start="2025-01-01 00:00", end="2025-01-02 23:00", primary_demand=True,
             bidirectional=True) -> dict:
    full = yaml.safe_load(TOPO.read_text(encoding="utf-8"))
    cfg = copy.deepcopy(full)
    cfg["site"]["input_xlsx"] = str(ROOT / full["site"]["input_xlsx"])
    cfg["scenario"]["horizon"] = {"start": start, "end": end}
    net = cfg["network"]
    net["physics"] = {"heat_loss": True, "pressure_drop": False, "transport_delay": False}
    hkw_node = {"assets": ["hkw"]}
    if primary_demand:
        hkw_node["consumers"] = [{"column": "Hoher_Weg_MW"}]
    net["nodes"] = {"j_hkw": hkw_node,
                    "j_man": {"assets": ["wh_man"], "consumers": [{"column": "MAN_MW"}]}}
    pipe = copy.deepcopy(full["network"]["pipes"]["hkw_to_man"])
    pipe["bidirectional"] = bool(bidirectional)
    net["pipes"] = {"hkw_to_man": pipe}
    cfg["assets"] = {"hkw": copy.deepcopy(full["assets"]["hkw"]),
                     "wh_man": {"type": "thermal_generator", "fuel": "waste_heat", "capacity_mw": float(cap_mw),
                                "thermal_efficiency": 1.0, "min_load": 0.0}}
    cfg["assets"]["hkw"]["min_load"] = 0.0
    cfg["assets"]["hkw"]["capacity_mw"] = 400.0   # pre-check compares capacity with the site-wide demand column
    cfg.setdefault("run", {})["solver"] = "gurobi"
    return cfg


def build(cfg: dict):
    from calion.run.workflow import _build_workflow_inputs
    from calion.run.solver import build_model
    from scripts.paper_2.scenario_runner import _dump_yaml_tmp   # simple_yaml-compatible writer
    inp = _build_workflow_inputs([str(_dump_yaml_tmp(cfg))], overrides=None)
    return build_model(inp.table, inp.cfg, dt_h=inp.dt_h), inp


def solve(model):
    opt = pyo.SolverFactory("gurobi_direct")
    opt.options["MIPGap"] = 1e-6
    opt.options["OutputFlag"] = 0
    res = opt.solve(model, tee=False)
    return str(res.solver.termination_condition)


def _val(x):
    v = pyo.value(x, exception=False)
    return 0.0 if v is None else float(v)


def residual(model) -> dict:
    T = list(model.t)
    gen = np.array([sum(_val(getattr(model, n)[t]) for n in ("HKW_Qth", "WH_MAN_Qth") if hasattr(model, n)) for t in T])
    dem = np.zeros(len(T))
    for comp in model.component_objects(pyo.Param, active=True):
        if comp.name.startswith("heatd_"):   # J_*_Q_demand is the same series (alias)
            dem += np.array([_val(comp[t]) for t in T])
    loss = np.array([_val(model.HKW_TO_MAN_Q_loss_supply[t]) + _val(model.HKW_TO_MAN_Q_loss_return[t]) for t in T])
    dump = np.zeros(len(T))
    for comp in model.component_objects(pyo.Var, active=True):
        if comp.name.startswith("Q_dump_"):
            dump += np.array([_val(comp[t]) for t in T])
    mdot = np.array([_val(model.HKW_TO_MAN_m_dot[t]) for t in T])
    R = gen - dem - loss - dump
    return {"R": R, "gen": gen, "dem": dem, "loss": loss, "dump": dump, "mdot": mdot}
