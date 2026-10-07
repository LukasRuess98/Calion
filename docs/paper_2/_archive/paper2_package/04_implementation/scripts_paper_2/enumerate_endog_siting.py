"""Explicit enumeration decomposition for F3 endogenous siting (SB-S6/MM-S4-style
scenarios: TES and HP/EK sited independently among N candidate nodes).

BACKGROUND (see docs/paper_2/CALION_Paper2_Implementation_Statement.md Part G.7):
the monolithic free-siting MILP has a structurally weak LP relaxation -- a
fractional site-selection binary `y` lets the LP draw on every candidate's
McCormick-relaxed local-generation headroom SIMULTANEOUSLY, which no linear
reformulation (four were tried and verified ineffective) can fix, and which
even a mathematically-correct SOS1 branching declaration can't exploit within
a practical time budget because Gurobi's own root-node processing (LP +
cutting planes) on this model's scale (~7M rows) consumes the entire budget
before real branching starts.

A rigorously diagnosed control experiment showed that FIXING the site
selection (removing y's fractionality) makes the subproblem dramatically
easier: root LP ~6x tighter, gap closing to ~12% within minutes instead of
staying frozen near 97%. Since there are only N_hp x N_tes candidate PAIRS
(25 for the 5x5 Stadtbach S6 case), the scientifically correct technique is
classical explicit-enumeration decomposition: solve each of the N_hp x N_tes
site-pair subproblems as an independent, individually-tractable MILP (same
model, same code path, y fixed instead of free), and take the best. The
overall solution's optimality gap to the TRUE free-siting optimum is bounded
by the WORST subproblem's own MIP gap -- a far stronger, and now practically
achievable, guarantee than the monolithic formulation's ~97% gap.

Usage (single pair, called by the orchestrator below):
    python enumerate_endog_siting.py --scenario SB-S6-HK0 \
        --hp-site j_hkw --tes-site j_ost --time-limit 3600 \
        --outdir output/paper2_runs/_endog_enum/SB-S6-HK0

Usage (orchestrator -- runs all N_hp x N_tes pairs with bounded concurrency):
    python enumerate_endog_siting.py --scenario SB-S6-HK0 --enumerate-all \
        --time-limit 3600 --concurrency 2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))


def _run_single_pair(scenario_id: str, hp_site: str, tes_site: str,
                      time_limit: int, outdir: Path, gurobi_threads: int = 4) -> dict:
    """Solve ONE (hp_site, tes_site) subproblem in-process (used by --pair mode,
    invoked as a subprocess by the orchestrator for isolation/parallelism).

    CRITICAL: run_single_scenario() writes to a FIXED path keyed only by
    scen["id"] -- output/paper2_runs/{id}/ for artefacts AND
    output/logs/gurobi_{id}.log for the solver log. Since every pair shares
    the same base scenario_id, concurrent pairs sharing that id would
    silently clobber each other's output files mid-solve. Each pair is
    therefore given its OWN synthetic id (base + site suffix) so its
    artefacts/log land in a unique location; the underlying scenario
    config (network, heat_curve_stage, overrides, ...) is otherwise
    untouched, only the id changes.
    """
    import copy
    import logging
    import calion.models.component_assembler as ca

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("enumerate_endog_siting")

    _orig_get_site_y = ca.ComponentAssembler._get_site_y
    _fixed_site = {"hp": hp_site, "tes": tes_site}

    def _patched_get_site_y(self, group):
        already_built = group in self._endog_y_vars
        y = _orig_get_site_y(self, group)
        if not already_built:
            target = _fixed_site.get(group)
            for c in self._endog_candidates:
                y[c].fix(1.0 if c == target else 0.0)
            logger.info("[ENUM] group '%s' fixed to site '%s'", group, target)
        return y

    ca.ComponentAssembler._get_site_y = _patched_get_site_y

    from scripts.paper_2.scenario_runner import load_scenarios_config, run_single_scenario

    scen_cfg = load_scenarios_config()
    base_scen = next(s for s in scen_cfg["scenarios"] if s["id"] == scenario_id)
    pair_scen = copy.deepcopy(base_scen)
    pair_id = f"{scenario_id}__hp_{hp_site}__tes_{tes_site}"
    pair_scen["id"] = pair_id
    # BUGFIX: calion/run/solver.py's export_all_results() writes to
    # cfg["output"]["export_dir"], which defaults to a FIXED shared path
    # (resolve_runs_dir()/thermal_network_results) -- NOT parameterized by
    # scenario id, unlike meta.json/gurobi log (which the pair_id already
    # fixes). Concurrent pairs sharing that base scenario config would
    # clobber each other's LP/SOL/thermal-network export files mid-solve.
    # This export is also expensive (~8-10 min/pair just for LP+SOL dump)
    # and not needed here -- the enumeration driver only reads obj/bound/gap
    # from run_single_scenario()'s return dict, never from these files.
    # Disabling it removes both the clobbering risk and ~10 min/pair of
    # pure overhead across the 25-pair campaign.
    pair_scen.setdefault("overrides", {})
    pair_scen["overrides"].setdefault("output", {})
    pair_scen["overrides"]["output"]["export_thermal_network"] = False
    pair_scen["overrides"]["output"]["export_solver_solution"] = False

    t0 = time.perf_counter()
    result = run_single_scenario(
        pair_scen, scen_cfg,
        force_rerun=True,
        # 2026-07-20: capped Threads (previously unset -> Gurobi default of using
        # up to every logical processor per solve) -- with several enumeration
        # pairs + main-campaign scenarios running concurrently across networks,
        # uncapped threads oversubscribed the host's CPU well past target.
        extra_solver_options={"TimeLimit": time_limit, "Threads": gurobi_threads},
    )
    elapsed = time.perf_counter() - t0
    result["hp_site"] = hp_site
    result["tes_site"] = tes_site
    result["elapsed_s"] = round(elapsed, 1)
    result["pair_id"] = pair_id

    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"pair_{hp_site}__{tes_site}.json"
    out_path.write_text(json.dumps(result, indent=2))
    logger.info("[ENUM] Pair (%s, %s) done: %s", hp_site, tes_site, result)
    return result


def _load_candidates(scenario_id: str) -> tuple[list[str], list[str], bool]:
    """Return (hp_candidates, tes_candidates, colocate) for the scenario's network."""
    from scripts.paper_2.scenario_runner import load_scenarios_config

    scen_cfg = load_scenarios_config()
    scen = next(s for s in scen_cfg["scenarios"] if s["id"] == scenario_id)
    network = scen["network"]
    cands = scen_cfg.get("endogenous_candidates", {}).get(network, [])
    colocate = bool(scen.get("colocate", False))
    return list(cands), list(cands), colocate


def _orchestrate(scenario_id: str, time_limit: int, concurrency: int, outdir: Path,
                  skip_existing: bool = False, gurobi_threads: int = 4) -> None:
    hp_cands, tes_cands, colocate = _load_candidates(scenario_id)
    if colocate:
        print(f"[ENUM] {scenario_id} has colocate=true -- siting is already a single "
              f"{len(hp_cands)}-way choice, not a 2-group enumeration problem. "
              "Nothing to enumerate; run it directly instead.")
        return

    pairs = [(h, t) for h in hp_cands for t in tes_cands]
    if skip_existing:
        before = len(pairs)
        pairs = [(h, t) for h, t in pairs
                 if not (outdir / f"pair_{h}__{t}.json").exists()]
        print(f"[ENUM] --skip-existing: {before - len(pairs)}/{before} pairs already have "
              f"an output file, skipping them (use force_rerun-style cleanup if you actually "
              f"want those re-solved).")
    print(f"[ENUM] {scenario_id}: {len(hp_cands)} hp candidates x {len(tes_cands)} tes "
          f"candidates = {len(pairs)} pairs, time_limit={time_limit}s each, "
          f"concurrency={concurrency}")

    outdir.mkdir(parents=True, exist_ok=True)
    this_file = Path(__file__).resolve()
    running: list[subprocess.Popen] = []
    pending = list(pairs)
    completed = []

    def _launch(hp_site: str, tes_site: str) -> subprocess.Popen:
        log_path = outdir / f"pair_{hp_site}__{tes_site}.log"
        cmd = [
            sys.executable, str(this_file),
            "--scenario", scenario_id,
            "--hp-site", hp_site,
            "--tes-site", tes_site,
            "--time-limit", str(time_limit),
            "--gurobi-threads", str(gurobi_threads),
            "--outdir", str(outdir),
        ]
        f = open(log_path, "w")
        print(f"[ENUM] Launching pair ({hp_site}, {tes_site}) -> {log_path}")
        return subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)

    while pending or running:
        while pending and len(running) < concurrency:
            hp_site, tes_site = pending.pop(0)
            running.append(_launch(hp_site, tes_site))
        time.sleep(10)
        still_running = []
        for p in running:
            if p.poll() is None:
                still_running.append(p)
            else:
                completed.append(p)
        running = still_running

    print(f"[ENUM] All {len(pairs)} pairs finished (or crashed). Collecting results...")
    _summarize(outdir)


def _summarize(outdir: Path) -> None:
    results = []
    for f in sorted(outdir.glob("pair_*.json")):
        try:
            results.append(json.loads(f.read_text()))
        except Exception as exc:
            print(f"[ENUM] Could not read {f}: {exc}")
    if not results:
        print("[ENUM] No pair results found.")
        return
    valid = [r for r in results if r.get("status") == "ok" and r.get("obj_eur") is not None]
    if not valid:
        print("[ENUM] No pair reached a valid incumbent.")
        return
    best = min(valid, key=lambda r: r["obj_eur"])
    summary = {
        "n_pairs_total": len(results),
        "n_pairs_valid": len(valid),
        "best": best,
        "all_sorted_by_obj": sorted(valid, key=lambda r: r["obj_eur"]),
    }
    (outdir / "_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[ENUM] BEST: hp_site={best['hp_site']} tes_site={best['tes_site']} "
          f"obj={best['obj_eur']:.0f} EUR (from {len(valid)}/{len(results)} valid pairs)")
    print(f"[ENUM] Summary written to {outdir / '_summary.json'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--time-limit", type=int, default=3600)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--hp-site", default=None)
    ap.add_argument("--tes-site", default=None)
    ap.add_argument("--enumerate-all", action="store_true")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--summarize-only", action="store_true")
    ap.add_argument("--skip-existing", action="store_true",
                     help="Skip pairs that already have a pair_*.json in --outdir "
                          "(for resuming/bumping concurrency without re-solving finished pairs)")
    ap.add_argument("--gurobi-threads", type=int, default=4,
                     help="Gurobi Threads per solve (avoids CPU oversubscription when "
                          "several pairs/scenarios run concurrently)")
    args = ap.parse_args()

    if args.summarize_only:
        _summarize(args.outdir)
    elif args.enumerate_all:
        _orchestrate(args.scenario, args.time_limit, args.concurrency, args.outdir,
                     skip_existing=args.skip_existing, gurobi_threads=args.gurobi_threads)
    else:
        if not args.hp_site or not args.tes_site:
            ap.error("--hp-site and --tes-site are required unless --enumerate-all")
        _run_single_pair(args.scenario, args.hp_site, args.tes_site,
                          args.time_limit, args.outdir, gurobi_threads=args.gurobi_threads)


if __name__ == "__main__":
    main()
