"""Solve MM-P1REF: a Memmingen P1<->P2 like-for-like OPEX comparison scenario.

Not part of the 46-run campaign matrix (deliberately not added to
configs/paper_2/scenarios.yaml, so it never inflates the canonical population
counted by T2/T3/T4/T5 — see gen_tables.py::build_t5's canonical_ids filter).

Context (Implementation Statement G.11/G.14): T5's Memmingen P1<->P2 OPEX
consistency check compared BC-MM (P2's zero-investment baseline, hp_main/
eboiler_main capacity_mw=0) against Paper 1's L3 reference (hp_main/
eboiler_main capacity_mw=5.0, pre-existing and dispatched) and failed at
124.49% -- expected, since the two scenarios are not the same physical
configuration. This scenario isolates that single variable: same P2 base
config, network topology and demand as BC-MM, but hp_main/eboiler_main fixed
at 5.0 MW (matching Paper 1's L3) with investment disabled, so it is a true
apples-to-apples P1<->P2 comparison point.

Usage:
    python scripts/paper_2/run_mm_p1ref.py
"""
from __future__ import annotations

import logging

from scripts.paper_2.scenario_runner import load_scenarios_config, run_single_scenario

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SCEN = {
    "id": "MM-P1REF",
    "network": "memmingen",
    "config": "configs/paper_2/Memmingen_P2_base.yaml",
    "heat_curve_stage": "TVLFIX",
    "tvl_fix": True,
    "tes_node": None,
    "baseline": False,
    "description": (
        "Memmingen P1-equivalent reference: hp_main/eboiler_main fixed at 5 MW "
        "(matching Paper 1 L3's pre-existing capacity), investment disabled, no TES -- "
        "isolates the single variable (HP/EK capacity) behind the P1<->P2 OPEX check "
        "(G.11/G.14). Not part of the 46-scenario campaign matrix."
    ),
    "overrides": {
        "assets": {
            "hp_main": {
                "capacity_mw": 5.0,
                "investment": {"enabled": False, "capacity_max_mw": 5.0},
            },
            "eboiler_main": {
                "capacity_mw": 5.0,
                "investment": {"enabled": False, "capacity_max_mw": 5.0},
            },
            "tes_main": {
                "V_min_m3": 0.0,
                "V_max_m3": 0.0,
            },
        },
    },
}

if __name__ == "__main__":
    scen_cfg = load_scenarios_config()
    result = run_single_scenario(SCEN, scen_cfg, force_rerun=True)
    print(result)
