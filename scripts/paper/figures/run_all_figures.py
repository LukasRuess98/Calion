"""Generate all paper figures. Run after paper_runner.py."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

FIGURE_SCRIPTS = [
    "scripts.paper.figures.fig_cost_topology",
    "scripts.paper.figures.fig_cost_extended",
    "scripts.paper.figures.fig_storage_winterweek",
    "scripts.paper.figures.fig_dispatch_heatmap",
    "scripts.paper.figures.fig_solve_time",
    "scripts.paper.figures.fig_tornado_sensitivity",
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
