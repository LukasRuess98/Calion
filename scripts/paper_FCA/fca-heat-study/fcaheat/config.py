"""Global configuration, paths and solver factory.

CFG is a plain dict and is meant to be mutated by the caller before a run:

    from fcaheat.config import CFG
    CFG.update(years=[2023, 2024, 2025], resolution="15min")

ECON is filled in by `fcaheat.data.load_inputs()` from the workbook's `assets` sheet. It is a
module-level dict so that model code can read economics without threading it through every call.
"""
from __future__ import annotations

import os
from pathlib import Path

import pyomo.environ as pyo

ROOT = Path(os.environ.get("FCA_ROOT", Path(__file__).resolve().parent.parent))
DATA_XLSX = Path(os.environ.get("FCA_XLSX", ROOT / "data" / "input_data_template_v2.xlsx"))
CACHE_DIR = ROOT / "cache"
OUT_DIR = ROOT / "results"
FIG_DIR = OUT_DIR / "figures"
for _d in (CACHE_DIR, OUT_DIR, FIG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CFG = dict(
    # --- horizon -----------------------------------------------------------
    years=[2024],            # [2023, 2024, 2025] for the full set
    months=None,             # None = whole year; e.g. [1, 2] for a smoke test
    resolution="1h",         # "15min" for final results, "1h" for screening
    # --- what to run -------------------------------------------------------
    sites=None,              # None = all sites in the workbook
    scenarios=["S0_BASE", "S1_NOSTOR", "S2_TES", "S3_BES", "S4_TES_BES"],
    fcas=["FCA_FIRM", "FCA_WINDOW", "FCA_DYNAMIC", "FCA_TDTR", "FCA_UPGRADE"],
    # --- model options -----------------------------------------------------
    cyclic_storage=True,
    limit_bes_cycles=False,
    apply_hlzf=True,
    dynamic_seed=2026,
    # --- solver ------------------------------------------------------------
    solver="appsi_highs",
    solver_options={"solver": "ipm", "run_crossover": "off"},
    tee=False,
)

ECON: dict = {}


def res_step() -> float:
    """Timestep in hours implied by CFG['resolution']. Always call this; never cache it."""
    return {"15min": 0.25, "1h": 1.0}[CFG["resolution"]]


def get_solver():
    name = CFG["solver"]
    opt = pyo.SolverFactory(name)
    if name.startswith("appsi"):
        assert opt.available(), f"solver {name} not available"
        if CFG.get("solver_options"):
            opt.highs_options = dict(CFG["solver_options"])
    else:
        assert opt.available(exception_flag=False), f"solver {name} not available"
        for k, v in (CFG.get("solver_options") or {}).items():
            opt.options[k] = v
    return opt
