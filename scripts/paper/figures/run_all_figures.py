"""Generate all paper figures. Run after paper_runner.py."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

FIGURE_SCRIPTS = [
    # No external data needed
    "scripts.paper.figures.fig_comparison_design",   # F1
    "scripts.paper.figures.fig_topology",            # F2
    # Needs run data (placeholder if absent)
    "scripts.paper.figures.fig_cost_topology",       # F3
    "scripts.paper.figures.fig_cost_extended",       # F4
    "scripts.paper.figures.fig_cost_waterfall",      # F5
    "scripts.paper.figures.fig_pump_pwl_vs_quad",    # F6
    "scripts.paper.figures.fig_storage_winterweek",  # F7
    "scripts.paper.figures.fig_storage_charge_hour", # F8
    "scripts.paper.figures.fig_dispatch_heatmap",    # F9
    "scripts.paper.figures.fig_synth_topology_gap",  # F10 (Gurobi)
    "scripts.paper.figures.fig_synth_physics_gap",   # F11 (Gurobi)
    "scripts.paper.figures.fig_synth_lin_error",     # F12 (Gurobi)
    "scripts.paper.figures.fig_tornado_sensitivity", # F13
    "scripts.paper.figures.fig_solve_time",          # F14
]


def main() -> None:
    import importlib
    for mod_name in FIGURE_SCRIPTS:
        try:
            mod = importlib.import_module(mod_name)
            mod.main()
            print(f"[OK] {mod_name.split('.')[-1]}")
        except Exception as e:
            print(f"[ERR] {mod_name.split('.')[-1]}: {e}")


if __name__ == "__main__":
    main()
