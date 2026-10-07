"""SB-S2 wash-cycling plausibility counter-test (Implementation Statement G.4/G.14).

Part G.4's "Open item" flagged SB-S2's near-constant full-power bidirectional
TES cycling (at j_man, a consumer node) as an extreme dispatch pattern and
recommended, before quoting SB-S2 as a paper finding, either (a) correlating
TES charge/discharge against HP dispatch, or (b) re-solving with a
cycling_cost_eur_per_mwh penalty to see whether the pattern (and its TAC
advantage) survives a modest wear/degradation cost.

(a) was already done directly against the existing campaign dispatch data
(no re-solve needed): corr(Q_storage_charge, Q_hp_total) = 0.23 on SB-S2-HK2
-- weak, meaning the wash-cycling is NOT primarily "the HP charging the tank";
throughput (Qc+Qd ~= 830 GWh/yr) is ~25x the HP's own mean output.

This script does (b): three January-2025-only (744h) diagnostic re-solves of
SB-S2-HK0 (fast turnaround, same window G.12 used for its own TES-export
diagnostic) --
  SB-S2-HK0-DIAGJAN-BASE   : no cycling cost (replicates current behaviour)
  SB-S2-HK0-DIAGJAN-CYCLO  : cycling_cost_eur_per_mwh = 0.5 EUR/MWh_th
  SB-S2-HK0-DIAGJAN-CYCHI  : cycling_cost_eur_per_mwh = 2.0 EUR/MWh_th

All three use distinct DIAG-suffixed ids (never the canonical SB-S2-HK0) so
they cannot clobber the real campaign result and are automatically excluded
from T3/T4/T5's canonical-scenario population (gen_tables.py's TEST|DIAG|ZZ
filter / build_t5's canonical_ids check).

Usage:
    python -m scripts.paper_2.run_sb_s2_cycling_counter_test
"""
from __future__ import annotations

import logging

from scripts.paper_2.scenario_runner import load_scenarios_config, run_single_scenario

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

JAN_HORIZON = {"start": "2025-01-01T00:00:00", "end": "2025-01-31T23:00:00"}

_BASE_SCEN = {
    "network": "stadtbach",
    "config": "configs/stadtbach/Stadtbach_topo.yaml",
    "heat_curve_stage": "HK0",
    "tes_node": "S2",
    "hp_node": "J4",
    "baseline": False,
}


def _variant(suffix: str, cycling_cost: float | None, desc: str) -> dict:
    scen = dict(_BASE_SCEN)
    scen["id"] = f"SB-S2-HK0-DIAGJAN-{suffix}"
    scen["description"] = desc
    overrides: dict = {"scenario": {"horizon": JAN_HORIZON}}
    if cycling_cost is not None:
        overrides["assets"] = {"tes_sb": {"cycling_cost_eur_per_mwh": cycling_cost}}
    scen["overrides"] = overrides
    return scen


VARIANTS = [
    _variant("BASE", None, "SB-S2-HK0 January-2025 diagnostic, no cycling cost (baseline for counter-test)"),
    _variant("CYCLO", 0.5, "SB-S2-HK0 January-2025 diagnostic, cycling_cost=0.5 EUR/MWh_th"),
    _variant("CYCHI", 2.0, "SB-S2-HK0 January-2025 diagnostic, cycling_cost=2.0 EUR/MWh_th"),
]

if __name__ == "__main__":
    scen_cfg = load_scenarios_config()
    for scen in VARIANTS:
        result = run_single_scenario(scen, scen_cfg, force_rerun=True)
        print(result)
