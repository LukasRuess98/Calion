"""v12 B9 (Weg B): certified lower bound of the annual operating problem of ONE fixed design by monthly decomposition.

Lower bound (valid for any peak grid and any water values lambda):
    The annual demand charge r * P_peak is the only non-separable cost term besides the SOC link (A6). For a cap grid
    c_1 < ... < c_n (plus c_{n+1} = inf) every feasible annual schedule has its peak in some [c_i, c_{i+1}] and costs
        >= r * c_i + sum_k LB_k(cap = c_{i+1})          (interval [0, c_1]: 0 + sum_k LB_k(c_1))
    where LB_k(cap) is the Gurobi BOUND of month block k with P_buy <= cap and the demand charge switched off
    (CALION_PEAK_CAP_MW, CALION_DEMAND_CHARGE_OFF). LB = min over intervals; an interval whose blocks are infeasible
    is excluded. With storage, the SOC link is dualised: block k gets + lambda_k * E0 - lambda_{k+1} * E_end
    (CALION_SOC_MODE=free, lambda_13 = lambda_1 for the cyclic year) -- valid for any lambda.
    Annualised CAPEX/O&M are period-scaled per block and sum to the annual value over the 12 months.
Upper bound: any feasible annual schedule; by default the Weg-A incumbent of the same design (--ub-run).
Every block uses the full-year temperature basis (CALION_REF_TRL_C / CALION_REF_TVL_AVG_C, v12 B9 refs).

usage:
  python scripts/paper_2/v12/decompose.py --scenario SB-S0-HK0-PIN0 [--design <yaml>] --work output/v12/_b9/<tag>
         --ref-trl 61.528991 --ref-tvl 99.876927 --caps 0.25,0.29,0.30 [--ub-run output/v12/<run>] [--workers 16]
         [--cpus 16-31] [--lambdas l1,...,l12] [--timelimit 3600] [--gap 0.0001]
Writes <work>/decomposition.json (all blocks, every interval, LB, UB, width).
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
YEAR = 2025


def months():
    for m in range(1, 13):
        last = calendar.monthrange(YEAR, m)[1]
        yield m, f"{YEAR}-{m:02d}-01 00:00", f"{YEAR}-{m:02d}-{last:02d} 23:00"


def _cpu_list(spec: str | None, threads: int = 1):
    """CPU range 'a-b' -> list of CPU groups of size `threads` (one group per concurrently running block)."""
    if not spec:
        return None
    a, b = spec.split("-")
    cpus = list(range(int(a), int(b) + 1))
    return [cpus[i:i + threads] for i in range(0, len(cpus) - threads + 1, threads)]


def run_block(job, args, cpu_pool):
    """One month block -> dict(status, obj, bound, gap, solve_s). Re-uses a finished block (meta.json) on restart."""
    out = Path(job["out"])
    scen_id = job["run_id"]
    meta = out / scen_id / "meta.json"
    if not meta.exists():
        env = dict(os.environ, PYTHONIOENCODING="utf-8", CALION_OUT_BASE=str(out),
                   CALION_HORIZON_START=job["start"], CALION_HORIZON_END=job["end"],
                   CALION_MIPGAP=str(args.gap), CALION_TIMELIMIT=str(args.timelimit), CALION_MIPFOCUS="3",
                   CALION_HP_DEFAULT_CHANNEL="off", CALION_DEMAND_CHARGE_OFF="1",
                   CALION_REF_TRL_C=str(args.ref_trl), CALION_REF_TVL_AVG_C=str(args.ref_tvl),
                   CALION_NODEFILE_DIR=str(ROOT / "output" / "v12" / "_nodefiles"))
        env.pop("CALION_RUN_TAG", None)
        env.pop("CALION_WARMSTART_DUMP", None)
        if job["cap"] is not None:
            env["CALION_PEAK_CAP_MW"] = repr(job["cap"])
        if job.get("design"):
            env["CALION_FIXED_DESIGN"] = job["design"]
        if job.get("soc"):
            env.update(job["soc"])
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "block.out", "w", encoding="utf-8") as fh:
            p = subprocess.Popen([sys.executable, "-m", "scripts.paper_2.scenario_runner", "-s", args.scenario,
                                  "-g", str(args.threads)],
                                 cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
            grp = cpu_pool.pop() if cpu_pool else None
            try:
                if grp is not None:
                    import psutil
                    psutil.Process(p.pid).cpu_affinity(list(grp))
                p.wait()
            finally:
                if grp is not None:
                    cpu_pool.append(grp)
    if not meta.exists():
        txt = (out / "block.out").read_text(encoding="utf-8", errors="replace") if (out / "block.out").exists() else ""
        status = "infeasible" if "infeasible" in txt.lower() else "error"
        return dict(job, status=status, obj=None, bound=None, gap=None, solve_s=None)
    m = json.loads(meta.read_text(encoding="utf-8"))
    # final P2 meta (obj_eur/status) or, if the extractor was interrupted, the P1 meta (objective/solver_status)
    obj = float(m["obj_eur"] if "obj_eur" in m else m["objective"])
    gap = float(m.get("mip_gap") or 0.0)
    status = m.get("status", m.get("solver_status"))
    return dict(job, status=status, obj=obj, bound=obj - gap * abs(obj), gap=gap,
                solve_s=m.get("solve_s", m.get("solve_time_s")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--design")
    ap.add_argument("--work", required=True)
    ap.add_argument("--ref-trl", type=float, required=True)
    ap.add_argument("--ref-tvl", type=float, required=True)
    ap.add_argument("--caps", required=True, help="comma-separated peak caps [MW]; 'inf' is always added")
    ap.add_argument("--ub-run")
    ap.add_argument("--lambdas", help="12 water values EUR/MWh at the START of months 1..12 (lambda_13 = lambda_1)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--threads", type=int, default=1, help="Gurobi threads per block (CPU group size)")
    ap.add_argument("--cpus")
    ap.add_argument("--timelimit", type=int, default=3600)
    ap.add_argument("--gap", type=float, default=1e-4)
    ap.add_argument("--rate", type=float, help="demand charge EUR/MW/a (default: from the scenario config)")
    ap.add_argument("--lambda0", type=float, default=0.0, help="initial constant water value EUR/MWh (storage)")
    ap.add_argument("--lb-iters", type=int, default=0, help="subgradient iterations on the water values (storage)")
    ap.add_argument("--lambda-step", type=float, default=0.2, help="subgradient step EUR/MWh per MWh, divided by iter+1")
    ap.add_argument("--anchor-cap", help="peak cap [MW] for the water-value iterations (default: largest cap)")
    ap.add_argument("--ub-seq", help="storage: caps for the sequential hand-off UB pass, comma list or auto")
    args = ap.parse_args()

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    scen_all = yaml.safe_load((ROOT / "configs" / "paper_2" / "scenarios.yaml").read_text(encoding="utf-8"))
    scen = next(s for s in scen_all["scenarios"] if s["id"] == args.scenario)
    cfg = yaml.safe_load((ROOT / scen["config"]).read_text(encoding="utf-8"))
    rate = args.rate if args.rate is not None else float(cfg["grid"]["demand_charge_eur_per_mw_y"])
    design = yaml.safe_load(Path(args.design).read_text(encoding="utf-8")) if args.design else None
    has_tes = bool(design and float(design.get("tes_mwh", 0)) > 0)
    lambdas = ([float(x) for x in args.lambdas.split(",")] if args.lambdas
               else [float(args.lambda0)] * 12)
    assert len(lambdas) == 12
    caps = sorted({float(c) for c in args.caps.split(",")})
    cap_list = caps + [None]   # None = uncapped
    cpu_pool = _cpu_list(args.cpus, args.threads)

    def make_jobs(base, caps_, lam):
        jobs = []
        for cap in caps_:
            ctag = "inf" if cap is None else f"{cap:.4f}"
            for m, start, end in months():
                j = dict(cap=cap, month=m, start=start, end=end, out=str(base / f"cap_{ctag}" / f"m{m:02d}"))
                j["run_id"] = args.scenario
                if design:
                    d = dict(design, run_id=f"B9-{ctag}-m{m:02d}")
                    dp = base / "_designs" / f"{d['run_id']}.yaml"
                    dp.parent.mkdir(parents=True, exist_ok=True)
                    dp.write_text(yaml.safe_dump(d), encoding="utf-8")
                    j["design"], j["run_id"] = str(dp), d["run_id"]
                if has_tes:
                    j["soc"] = {"CALION_SOC_MODE": "free", "CALION_SOC_START_VALUE": repr(lam[m - 1]),
                                "CALION_SOC_END_VALUE": repr(lam[m % 12])}
                jobs.append(j)
        return jobs

    def run_all(jobs):
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            res_ = list(ex.map(lambda j: run_block(j, args, cpu_pool), jobs))
        print(f"{len(res_)} blocks in {time.time() - t0:.0f} s", flush=True)
        return res_

    def soc_state(r):
        """(E0, E_end) of a block from its solution dump (storage designs only)."""
        v = json.loads((Path(r["out"]) / r["run_id"] / "full_solution_dump.json").read_text(encoding="utf-8"))["vars"]
        e0k = next(k for k in v if k.endswith("_E0"))
        e = v[e0k[:-1]]   # <tes>_E
        return float(v[e0k]["None"]), float(e[str(max(int(k) for k in e))])

    def boundary_value(r):
        cb = json.loads((Path(r["out"]) / r["run_id"] / "cost_breakdown.json").read_text(encoding="utf-8"))
        return float(cb["model_aux_terms_EUR"].get("SOC_boundary_value_EUR", {}).get("value", 0.0))

    # water values (storage designs): projected subgradient on the Lagrangian dual at the anchor cap
    lam_trace = []
    if has_tes and args.lb_iters > 0:
        anchor = float(args.anchor_cap) if args.anchor_cap else caps[-1]
        best = (None, list(lambdas))
        lam = list(lambdas)
        for it in range(args.lb_iters):
            res_it = run_all(make_jobs(work / f"lam{it:02d}", [anchor], lam))
            if any(r["bound"] is None for r in res_it):
                lam_trace.append({"iter": it, "lambdas": lam, "L_EUR": None})
                break
            L = sum(r["bound"] for r in res_it)
            st = {r["month"]: soc_state(r) for r in res_it}
            g = [st[k][0] - st[(k - 2) % 12 + 1][1] for k in range(1, 13)]   # E0_k - E_end_{k-1}, cyclic
            lam_trace.append({"iter": it, "lambdas": lam, "L_EUR": L, "subgradient_MWh": g})
            print(f"lambda iter {it}: L = {L:.0f} EUR, max|g| = {max(abs(x) for x in g):.1f} MWh", flush=True)
            if best[0] is None or L > best[0]:
                best = (L, list(lam))
            step = args.lambda_step / (it + 1)
            lam = [lam[k] + step * g[k] for k in range(12)]
        lambdas = best[1]

    res = run_all(make_jobs(work / "final" if has_tes else work, cap_list, lambdas))

    def block_sum(cap):
        rows = [r for r in res if r["cap"] == cap]
        if any(r["status"] in ("infeasible", "error") or r["bound"] is None for r in rows):
            return None, rows
        return sum(r["bound"] for r in rows), rows

    intervals = []
    lo_edges = [0.0] + caps
    for i, hi in enumerate(cap_list):
        s_, rows = block_sum(hi)
        lo = lo_edges[i]
        intervals.append({"P_lo_MW": lo, "P_hi_MW": hi, "sum_block_bounds_EUR": s_,
                          "LB_EUR": None if s_ is None else rate * lo + s_,
                          "blocks": [{k: r[k] for k in ("month", "status", "obj", "bound", "gap", "solve_s")} for r in rows]})
    feas = [iv for iv in intervals if iv["LB_EUR"] is not None]
    lb = min(iv["LB_EUR"] for iv in feas) if feas else None
    binding = min(feas, key=lambda iv: iv["LB_EUR"]) if feas else None

    # upper bounds
    # (a) Weg-A incumbent of the same design (--ub-run).
    # (b) no storage: the blocks of one cap are independent; their incumbents form a feasible annual schedule,
    #     UB_c = r * (its real annual peak) + sum_k obj_k.
    # (c) storage: sequential hand-off pass at cap c: month k starts at the end state of month k-1, its end state is
    #     valued with lambda_{k+1} (no draining), December ends on the January start state (annual cycle closed).
    #     Feasible annual schedule -> UB = r * peak + sum_k (obj_k - boundary term_k).
    import pandas as pd
    ub_candidates = []
    if args.ub_run and (Path(args.ub_run) / "meta.json").exists():
        ub_candidates.append({"source": f"weg_a:{args.ub_run}",
                              "UB_EUR": float(json.loads((Path(args.ub_run) / "meta.json").read_text(encoding="utf-8"))["obj_eur"])})
    elif args.ub_run:
        print(f"WARNING: --ub-run {args.ub_run} has no meta.json (yet) -- Weg-A UB not used")

    def peak(r):
        return float(pd.read_csv(Path(r["out"]) / r["run_id"] / "dispatch_hourly.csv")["P_buy_MW"].max())

    if not has_tes:
        for cap in cap_list:
            rows = [r for r in res if r["cap"] == cap]
            if any(r["obj"] is None for r in rows):
                continue
            pk = max(peak(r) for r in rows)
            ub_candidates.append({"source": f"blocks:cap={cap}", "annual_peak_MW": pk,
                                  "UB_EUR": rate * pk + sum(r["obj"] for r in rows)})
    elif args.ub_seq:
        if args.ub_seq != "auto":
            seq_caps = [float(c) for c in args.ub_seq.split(",")]
        else:
            seq_caps = [binding["P_hi_MW"]] if binding and binding["P_hi_MW"] is not None else [caps[-1]]
        for cap in seq_caps:
            jan = next((r for r in res if r["cap"] == cap and r["month"] == 1 and r["obj"] is not None), None)
            e_start = soc_state(jan)[0] if jan else 0.5 * float(design["tes_mwh"])
            e_prev, rows, ok = e_start, [], True
            base = work / "ubseq"
            ctag = f"{cap:.4f}"
            for m, start, end in months():
                d = dict(design, run_id=f"B9U-{ctag}-m{m:02d}")
                dp = base / "_designs" / f"{d['run_id']}.yaml"
                dp.parent.mkdir(parents=True, exist_ok=True)
                dp.write_text(yaml.safe_dump(d), encoding="utf-8")
                soc = {"CALION_SOC_MODE": "handoff", "CALION_SOC_START_MWH": repr(e_prev),
                       "CALION_SOC_START_VALUE": "0", "CALION_SOC_END_VALUE": repr(lambdas[m % 12])}
                if m == 12:
                    soc["CALION_SOC_END_MWH"] = repr(e_start)
                    soc["CALION_SOC_END_VALUE"] = "0"
                j = dict(cap=cap, month=m, start=start, end=end, out=str(base / f"cap_{ctag}" / f"m{m:02d}"),
                         run_id=d["run_id"], design=str(dp), soc=soc)
                r = run_block(j, args, cpu_pool)
                if r["obj"] is None:
                    ok = False
                    break
                rows.append(r)
                e_prev = soc_state(r)[1]
            if ok:
                pk = max(peak(r) for r in rows)
                ub_candidates.append({"source": f"seq_handoff:cap={cap}", "annual_peak_MW": pk, "E_start_MWh": e_start,
                                      "UB_EUR": rate * pk + sum(r["obj"] - boundary_value(r) for r in rows)})
    ub = min((c["UB_EUR"] for c in ub_candidates), default=None)
    out = {"scenario": args.scenario, "design": design, "rate_EUR_per_MW_a": rate, "caps_MW": caps,
           "lambdas_EUR_per_MWh": lambdas if has_tes else None, "lambda_trace": lam_trace,
           "refs": {"T_RL_ref_C": args.ref_trl, "T_avg_C": args.ref_tvl},
           "LB_EUR": lb, "UB_EUR": ub, "UB_candidates": ub_candidates,
           "UB_source": min(ub_candidates, key=lambda c: c["UB_EUR"])["source"] if ub_candidates else None,
           "width_EUR": (ub - lb) if (ub is not None and lb is not None) else None,
           "width_pct": (100 * (ub - lb) / ub) if (ub is not None and lb is not None) else None,
           "binding_interval": [binding["P_lo_MW"], binding["P_hi_MW"]] if binding else None,
           "intervals": intervals}
    (work / "decomposition.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("LB_EUR", "UB_EUR", "width_EUR", "width_pct", "binding_interval", "UB_source")},
                     indent=1))

if __name__ == "__main__":
    main()
