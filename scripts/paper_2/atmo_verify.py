"""End-to-end check: does the atmospheric TES model build an inner-optimum store?

Runs ONE investment scenario to an isolated output dir (never touches the frozen
seed results) and prints the TES size the optimizer chose. Compare:
    CALION_ATMOSPHERIC_TES unset  -> legacy pressurized (expect ~0 TES, "negligible")
    CALION_ATMOSPHERIC_TES=1      -> atmospheric+degressive (expect an interior TES)

Usage:
    python scripts/paper_2/atmo_verify.py MM-S1-HK0
    CALION_ATMOSPHERIC_TES=1 python scripts/paper_2/atmo_verify.py MM-S1-HK0
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from scripts.paper_2 import scenario_runner as sr  # noqa: E402
from scripts.paper_2.value_saturation_probe import (  # noqa: E402
    HP_ASSET, EK_ASSET, _detect_commitment_gens)
from scripts.paper_2.main_result_loader import load_main_result  # noqa: E402

_SOLVER = {"TimeLimit": 5400, "MIPGap": 0.01, "Threads": 8,
           "Cuts": 2, "MIPFocus": 1, "Heuristics": 0.5}


def _fast_override(scen_id: str, network: str, config_path: str,
                   relax_commitment: bool = True) -> dict:
    """Pin HP at its solved optimum + (optionally) relax generator commitment so
    only the TES investment binaries remain. NOTE: relaxing commitment REMOVES the
    unit-commitment/cycling-smoothing value that IS storage's main value here, so
    for a faithful sizing check keep commitment ON (relax_commitment=False)."""
    q_opt = load_main_result(scen_id)["Q_WP_opt_MW"]
    ov = {"assets": {
        HP_ASSET[network]: {"investment": {"enabled": True,
                                           "capacity_min_mw": float(q_opt),
                                           "capacity_max_mw": float(q_opt)}},
        EK_ASSET[network]: {"investment": {"enabled": False, "capacity_max_mw": 0.0}},
    }}
    if relax_commitment:
        ov["assets"][EK_ASSET[network]]["min_load"] = 0.0
        for gk in _detect_commitment_gens(config_path):
            ov["assets"].setdefault(gk, {})["min_load"] = 0.0
    return ov


def main() -> None:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    scen_id = sys.argv[1] if len(sys.argv) > 1 else "MM-S1-HK0"
    mode = "ATMOSPHERIC" if os.environ.get("CALION_ATMOSPHERIC_TES") else "LEGACY"
    tag = mode.lower()
    sr.OUT_BASE = _ROOT / "output" / "atmo_verify"
    sr.OUT_BASE.mkdir(parents=True, exist_ok=True)

    scen_cfg = sr.load_scenarios_config()
    scen = next(s for s in scen_cfg["scenarios"] if s["id"] == scen_id)
    scen = dict(scen)
    scen["id"] = f"{scen_id}__{tag}"

    if "--fast" in sys.argv:
        network = scen["network"]
        relax = "--keep-commitment" not in sys.argv
        ov = _fast_override(scen_id, network, scen["config"], relax_commitment=relax)
        scen["overrides"] = sr._deep_merge(scen.get("overrides") or {}, ov)
        print(f"[FAST] HP pinned, EK off, commitment {'RELAXED' if relax else 'ON'} (TES investable)")

    print(f"=== atmo_verify {scen_id} [{mode}] ===")
    r = sr.run_single_scenario(scen, scen_cfg, dry_run=False, force_rerun=True,
                               extra_solver_options=_SOLVER)
    outdir = r.get("outdir")
    print(f"status={r.get('status')} outdir={outdir}")
    if outdir:
        import pandas as pd
        gpath = Path(outdir) / "geometry.csv"
        if gpath.exists():
            g = pd.read_csv(gpath)
            print("GEOMETRY (TES built):")
            print(g.to_string(index=False))
        from scripts.paper_2.kpi_calculator import compute_scenario_kpis
        k = compute_scenario_kpis(Path(outdir))
        print(f"TAC={k.get('TAC_eur_per_a')}  LCOH={k.get('LCOH_eur_per_MWh')}  "
              f"CAPEX={k.get('CAPEX_annual_eur_per_a')}  gap={k.get('mip_gap_pct')}")


if __name__ == "__main__":
    main()
