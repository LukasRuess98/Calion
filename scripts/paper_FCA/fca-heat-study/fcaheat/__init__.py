"""Sizing an electrified industrial heat supply behind a flexible connection agreement."""
__version__ = "0.3.0"

from .config import CFG, ECON, OUT_DIR, FIG_DIR, get_solver, res_step
from .data import Inputs, load_inputs, annuity, parse_int_list
from .fca import build_grid_limit, hlzf_mask
from .model import Case, build_model, solve_case, cop_series, slice_horizon
from .runner import (run_batch, add_relative_kpis, run_contract_space,
                     run_sensitivity_oat, find_min_flex, find_max_restriction)
from .mpc import run_mpc, run_mpc_all_sites
from .export import export_tables, export_metadata
