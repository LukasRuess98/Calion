"""Part A — dispatch-only capacity sweep (spec §A).

For ONE representative scenario per network, solve the operation over a fixed
Q̇_WP × V_TES grid — no investment optimisation. Capacity is pinned per grid
point by collapsing the WP capacity bounds and the TES volume bounds to a single
value (capacity_min = capacity_max = x_fix); every operating constraint (energy
balance, SOC, COP, L3+ temperature/pressure, waste-heat) is inherited unchanged
from the main model. The build binaries are forced to 1 (x_fix > 0), so Gurobi
presolves them away and each point is effectively a dispatch LP — much faster
than the investment MILP, exactly as the spec intends.

Per point: TAC / LCOH / OPEX split are computed with the *same* KPI definitions
as the main campaign (kpi_calculator.compute_scenario_kpis → spec §6.1), so the
sweep surface is directly comparable to the MILP optimum, which is written out as
a marker for the F3 heatmap and the §A.5 sweep↔MILP consistency check.

Per-point solve artefacts are isolated in output/paper2_sweep/ so they never
enter the main campaign's KPI aggregation. The aggregated grid lands in
results/sweep_{network}_{scenario_id}.csv (+ _optimum.json).

Usage:
    python scripts/paper_2/capacity_sweep.py SB-S1-HK0                 # 7×7 default
    python scripts/paper_2/capacity_sweep.py MM-S2-HK0 --n 5 --lo 0.5 --hi 1.5
    python scripts/paper_2/capacity_sweep.py SB-S1-HK0 --dry-run       # grid only
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(_ROOT))

from scripts.paper_2 import scenario_runner as sr  # noqa: E402
from scripts.paper_2.kpi_calculator import compute_opex_split, compute_scenario_kpis  # noqa: E402
from scripts.paper_2.main_result_loader import load_main_result  # noqa: E402
from scripts.paper_2.validation_p2 import check_sweep_consistency  # noqa: E402

logger = logging.getLogger("capacity_sweep")

SWEEP_OUT = _ROOT / "output" / "paper2_sweep"     # isolated per-point artefacts
RESULTS = _ROOT / "results"
CO2_PRICE = 100.0                                  # €/t (spec / configs)


def _pin_override(network: str, q_mw: float, v_m3: float) -> dict:
    """Override that fixes WP capacity and TES volume to a single grid point."""
    from scripts.paper_2.main_result_loader import HP_ASSET, TES_ASSET
    return {
        "assets": {
            HP_ASSET[network]: {"investment": {"enabled": True,
                                               "capacity_min_mw": float(q_mw),
                                               "capacity_max_mw": float(q_mw)}},
            TES_ASSET[network]: {"V_min_m3": float(v_m3), "V_max_m3": float(v_m3)},
        }
    }


def _grid(opt: float, lo: float, hi: float, n: int, vmin: float, vmax: float) -> list[float]:
    g = np.clip(np.linspace(lo * opt, hi * opt, n), vmin, vmax)
    # de-dupe after clipping (endpoints may collapse onto a bound)
    return sorted({round(float(x), 6) for x in g if x > 0})


_SWEEP_SOLVER_OPTIONS = {
    # Dispatch-only points (capacities pinned, build binaries presolved away)
    # converge to a good gap within minutes in practice (observed ~4.7% at
    # ~9 min on a Stadtbach-scale point) -- they don't need the investment
    # MILP's 24h/1% budget. A tighter budget here is what makes a 7x7=49-point
    # sweep per network tractable (2026-07-19).
    "TimeLimit": 1800,
    "MIPGap": 0.02,
    "Threads": 4,
    "Cuts": 2,
    "MIPFocus": 2,
    "Heuristics": 0.1,
}


def run_sweep(scenario_id: str, n: int = 7, lo: float = 0.4, hi: float = 1.6,
              dry_run: bool = False) -> Path | None:
    res = load_main_result(scenario_id)
    network = res["network"]
    q_opt, v_opt = res["Q_WP_opt_MW"], res["V_TES_opt_m3"]
    if not q_opt or not v_opt:
        raise ValueError(
            f"{scenario_id}: MILP optimum has Q_WP={q_opt} MW, V_TES={v_opt} m³ — "
            "the sweep needs a scenario where BOTH the WP and the TES were built.")

    q_grid = _grid(q_opt, lo, hi, n, res["q_min_mw"], res["q_max_mw"])
    v_grid = _grid(v_opt, lo, hi, n, res["v_min_m3"], res["v_max_m3"])
    logger.info("Sweep %s (%s): Q_WP*=%.2f MW, V_TES*=%.0f m³ — fixed at HK1 "
                "(spec A.3, regardless of the seed scenario's own HK stage)",
                scenario_id, network, q_opt, v_opt)
    logger.info("  Q_WP grid [MW]: %s", ", ".join(f"{x:.2f}" for x in q_grid))
    logger.info("  V_TES grid [m³]: %s", ", ".join(f"{x:.0f}" for x in v_grid))
    logger.info("  %d × %d = %d dispatch solves", len(q_grid), len(v_grid),
                len(q_grid) * len(v_grid))

    if dry_run:
        logger.info("[DRY-RUN] grid built; no solves performed")
        return None

    base_scen = res["scenario"]
    scen_cfg = sr.load_scenarios_config()
    orig_out = sr.OUT_BASE
    sr.OUT_BASE = SWEEP_OUT
    SWEEP_OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    try:
        for iq, q in enumerate(q_grid):
            for iv, v in enumerate(v_grid):
                scen = copy.deepcopy(base_scen)
                scen["id"] = f"SWEEP_{scenario_id}_q{q:.3f}_v{v:.0f}"
                scen["baseline"] = False
                # Spec A.3 (finalised): the sweep always runs at HK1, regardless of
                # which HK stage the seed scenario_id (used for Q*/V*/node) carries.
                scen["heat_curve_stage"] = "HK1"
                scen["tvl_fix"] = False
                scen["overrides"] = sr._deep_merge(scen.get("overrides") or {},
                                                   _pin_override(network, q, v))
                r = sr.run_single_scenario(scen, scen_cfg, dry_run=False, force_rerun=True,
                                            extra_solver_options=_SWEEP_SOLVER_OPTIONS)
                row = {"Q_WP_MW": q, "V_TES_m3": v, "status": r.get("status")}
                if r.get("status") == "ok" and r.get("outdir"):
                    k = compute_scenario_kpis(Path(r["outdir"]))
                    opex_split = compute_opex_split(Path(r["outdir"]))
                    opex = float(k.get("OPEX_annual_eur_per_a") or 0)
                    co2 = float(k.get("co2_t_per_a") or 0) * CO2_PRICE
                    row.update(
                        TAC_eur_per_a=k.get("TAC_eur_per_a"),
                        LCOH_eur_per_MWh=k.get("LCOH_eur_per_MWh"),
                        CAPEX_annual_eur_per_a=k.get("CAPEX_annual_eur_per_a"),
                        OPEX_annual_eur_per_a=opex,
                        OPEX_el_eur_per_a=opex_split["OPEX_el_eur_per_a"],
                        OPEX_gas_eur_per_a=opex_split["OPEX_gas_eur_per_a"],
                        OPEX_CO2_eur_per_a=round(co2, 1),
                        OPEX_energy_eur_per_a=round(max(opex - co2, 0.0), 1),
                        co2_t_per_a=k.get("co2_t_per_a"),
                        feasible=True,
                    )
                else:
                    row["feasible"] = False
                rows.append(row)
                logger.info("  [%2d/%2d] Q=%.2f V=%.0f -> %s  TAC=%s",
                            iq * len(v_grid) + iv + 1, len(q_grid) * len(v_grid),
                            q, v, row["status"],
                            f"{row.get('TAC_eur_per_a'):,.0f}" if row.get("feasible") else "—")
    finally:
        sr.OUT_BASE = orig_out

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"sweep_{network}_{scenario_id}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    optimum_path = RESULTS / f"sweep_{network}_{scenario_id}_optimum.json"
    optimum_path.write_text(json.dumps({
        "scenario_id": scenario_id, "network": network,
        "Q_WP_opt_MW": q_opt, "V_TES_opt_m3": v_opt,
        "TAC_opt_eur_per_a": res.get("TAC_opt_eur_per_a"),
        "LCOH_opt_eur_per_MWh": res.get("LCOH_opt_eur_per_MWh"),
    }, indent=2), encoding="utf-8")

    # §A.5 consistency: dual-criterion check (TAC +/-10% AND grid distance +/-1 step)
    consistency = check_sweep_consistency(out, optimum_path)
    if consistency.get("verdict") not in (None, "not_run"):
        optimum_path.write_text(json.dumps({
            "scenario_id": scenario_id, "network": network,
            "Q_WP_opt_MW": q_opt, "V_TES_opt_m3": v_opt,
            "TAC_opt_eur_per_a": res.get("TAC_opt_eur_per_a"),
            "LCOH_opt_eur_per_MWh": res.get("LCOH_opt_eur_per_MWh"),
            "sweep_consistency": consistency,
        }, indent=2), encoding="utf-8")
        logger.info("Sweep<->MILP consistency: %s (TAC dev %+.1f%%, grid dist Q=%d V=%d steps)",
                    consistency["verdict"], consistency["tac_dev_pct"],
                    consistency["grid_steps_q"], consistency["grid_steps_v"])
        if consistency["verdict"] != "passed":
            logger.warning("Sweep<->MILP consistency is '%s' — report explicitly in T5, "
                            "do not treat silently as passed (spec A.5).",
                            consistency["verdict"])
    else:
        logger.info("Sweep<->MILP consistency: not_run (%s)", consistency.get("detail"))
    logger.info("Sweep written -> %s", out)
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser(description="Dispatch-only capacity sweep (Paper 2 Part A)")
    ap.add_argument("scenario_id", help="representative scenario, e.g. SB-S1-HK0")
    ap.add_argument("--n", type=int, default=7, help="grid points per axis (default 7)")
    ap.add_argument("--lo", type=float, default=0.4, help="lower factor of optimum")
    ap.add_argument("--hi", type=float, default=1.6, help="upper factor of optimum")
    ap.add_argument("--dry-run", action="store_true", help="build+print grid only")
    args = ap.parse_args()
    run_sweep(args.scenario_id, n=args.n, lo=args.lo, hi=args.hi, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
