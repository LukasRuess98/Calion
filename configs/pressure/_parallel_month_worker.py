# -*- coding: utf-8 -*-
"""Worker for parallelizing Teil 2's 12-month MILP solve loop across OS processes.

Runs in a freshly spawned interpreter (Windows requires spawn, not fork, for
multiprocessing). Loads the notebook's OWN Cell 1 / Cell 2 / Cell 16 source and
execs it here, so there is exactly one implementation of build_and_solve() /
extract_all_hours() -- never a hand-ported duplicate that can silently drift
from the notebook (this happened twice already in this notebook's history).

Must be an importable top-level module (not defined inline in the notebook):
ProcessPoolExecutor on Windows pickles the target function by module+qualname
and re-imports it in the child process, which fails for anything defined in a
live Jupyter/IPython namespace.
"""
import json
import pickle
from pathlib import Path

NB_PATH = Path(__file__).parent / "Memmingen_pandapipes_crosscheck.ipynb"


def _load_helper_source():
    with open(NB_PATH, encoding="utf-8") as f:
        nb = json.load(f)
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    cell1_src = "".join(code_cells[0]["source"])
    cell2_src = "".join(code_cells[1]["source"])
    # Cell 2 ends with a real WINTER-week solve call -- keep only the function
    # definitions above it, so a worker doesn't waste ~90s on an unused solve.
    marker = '\nmodel, cfg, inputs = build_and_solve('
    assert marker in cell2_src, "Cell 2 source shape changed -- update the split marker"
    cell2_defs_only = cell2_src.split(marker)[0]
    cell16_src = next("".join(c["source"]) for c in code_cells if "Cell 16 --" in "".join(c["source"]))
    return cell1_src, cell2_defs_only, cell16_src


def solve_month(start, end, label, time_limit_s, mip_gap, n_threads, out_pickle):
    """Builds+solves one month-window's MILP in this process, extracts all
    hours, and pickles the result. Returns (label, n_hours, elapsed_s)."""
    import time as _time
    t0 = _time.time()
    ns = {}
    cell1_src, cell2_defs, cell16_src = _load_helper_source()
    exec(cell1_src, ns)
    exec(cell2_defs, ns)
    exec(cell16_src, ns)
    model, cfg, inputs = ns["build_and_solve"](
        start, end, label, time_limit_s=time_limit_s, mip_gap=mip_gap, n_threads=n_threads,
    )
    node_data, pipe_data, ts, pump_MW = ns["extract_all_hours"](model, cfg)

    import numpy as _np
    n_hours = len(ts)
    total_demand_MW = _np.zeros(n_hours)
    for _pdata in pipe_data.values():
        if _pdata.get("Q_consumer_MW") is not None:
            total_demand_MW += _pdata["Q_consumer_MW"]

    payload = {
        "label": label,
        "node_data": node_data,
        "pipe_data": pipe_data,
        "n_hours": n_hours,
        "node_ids": list(cfg["network"]["nodes"].keys()),
        "pipe_ids": list(cfg["network"]["pipes"].keys()),
        "total_demand_MW": total_demand_MW,
        "total_pump_MW": pump_MW["total"],
        "producer_pump_MW": pump_MW["producer"],
        "station_pump_MW": pump_MW["station"],
        "lateral_pump_MW": pump_MW["lateral"],
    }
    with open(out_pickle, "wb") as f:
        pickle.dump(payload, f)
    return label, len(ts), _time.time() - t0
