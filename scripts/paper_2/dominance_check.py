"""Dominance acceptance gate for the Paper-2 matched-effort campaign (2026-09-09).

A scenario may NEVER report a better (lower) TAC bound than a scenario whose feasible
set it CONTAINS is allowed to — equivalently, a scenario may never report WORSE than a
scenario it contains as a restriction. The DoE nesting is exact:

  BC              no investment
  S0   ⊇ BC       HP/EK investment, NO TES              (TES-scenarios can set TES=0 → S0)
  S1/S2/S3 ⊇ S0   HP/EK + TES at a FIXED node           (rung 0 reproduces S0)
  S4/S5    ⊇ S1..S3, ⊇ S0   HP/EK + TES ENDOGENOUS siting (can pick any node, or none)
  S4CO     ⊇ S0   endogenous but co-located (a restriction of S4; still can set TES=0)

So per (network, HK): obj(any TES scenario) ≤ obj(S0) ≤ obj(BC). An incumbent that
violates this is a DEMONSTRABLY BROKEN run (it failed to find a solution trivially
available in its own model) → mark FAILED, do not report the number.

Usage:  PYTHONPATH=. python scripts/paper_2/dominance_check.py [run_dir ...]
        (defaults to output/paper2_runs_v3b + output/paper2_runs_v3)
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# Scenarios whose feasible set CONTAINS S0 (same net+HK): TES-enabled with the same
# HP/EK investment freedom → can set TES=0 and reproduce S0. TESONLY excluded (its HP
# freedom differs). Endogenous (S4/S5/S4CO) included: they can also decline to build.
_TES_ENABLED_PREFIX = ("S1", "S2", "S3", "S4", "S5", "S4CO", "S6", "S7", "S6CO")


def _load(run_dirs: list[Path]) -> dict[str, dict]:
    """scenario_id -> {obj, gap, status, run_dir}. Later dirs override earlier."""
    out: dict[str, dict] = {}
    for rd in run_dirs:
        for mf in sorted(rd.glob("*/meta.json")):
            sid = mf.parent.name
            try:
                d = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            out[sid] = {
                "obj": d.get("obj_eur") or d.get("incumbent") or d.get("objective"),
                "gap": d.get("mip_gap"),
                "status": d.get("status"),
                "run_dir": rd.name,
            }
    return out


def _parse(sid: str) -> tuple[str, str, str]:
    """(network, row, hk) from e.g. 'MM-S1-HK0' -> ('MM','S1','HK0'); 'BC-MM'->('MM','BC','')."""
    parts = sid.split("-")
    if sid.startswith("BC"):
        net = parts[1] if len(parts) > 1 else "?"
        hk = parts[2] if len(parts) > 2 else ""
        return net, "BC", hk
    net = parts[0]
    row = parts[1] if len(parts) > 1 else "?"
    hk = parts[2] if len(parts) > 2 else ""
    return net, row, hk


def check(run_dirs: list[Path], fail_tol: float = 0.01, suspect_tol: float = 0.0) -> list[dict]:
    """Tiered dominance gate (2026-09-09, author correction). Excess over the inheritable
    restriction is classified: > fail_tol (1%) -> 'failed' (do NOT report the number);
    (suspect_tol, fail_tol] -> 'suspect' (report but flag, don't rank against its inheritor
    — a +0.5% excess is numerical noise / an unclosed gap, not a broken run). The exact
    threshold is provisional: re-derive fail_tol from the incumbent-stability drift once
    measured, so it is justified rather than picked.
    """
    res = _load(run_dirs)
    s0 = {}
    for sid, r in res.items():
        net, row, hk = _parse(sid)
        if row == "S0" and r["obj"] is not None:
            s0[(net, hk)] = (sid, r["obj"])
    violations = []
    for sid, r in res.items():
        net, row, hk = _parse(sid)
        obj = r["obj"]
        if obj is None:
            continue
        if any(row == p or row.startswith(p) for p in _TES_ENABLED_PREFIX):
            ref = s0.get((net, hk))
            if ref is None:
                continue
            ref_sid, ref_obj = ref
            excess = (obj - ref_obj) / ref_obj
            if excess <= suspect_tol:
                continue
            violations.append({
                "scenario": sid, "obj": obj, "restriction": ref_sid,
                "restriction_obj": ref_obj, "excess_pct": 100.0 * excess,
                "tier": "failed" if excess > fail_tol else "suspect",
                "gap": r["gap"], "status": r["status"],
            })
    violations.sort(key=lambda v: -v["excess_pct"])
    return violations


def main() -> None:
    args = sys.argv[1:]
    run_dirs = [Path(a) for a in args] if args else [
        _ROOT / "output" / "paper2_runs_v3", _ROOT / "output" / "paper2_runs_v3b"]
    run_dirs = [d for d in run_dirs if d.exists()]
    v = check(run_dirs)
    print(f"Dominance gate over {[d.name for d in run_dirs]}")
    if not v:
        print("  PASS - no scenario reports worse than its own restriction.")
        return
    failed = [r for r in v if r["tier"] == "failed"]
    suspect = [r for r in v if r["tier"] == "suspect"]
    print(f"  {len(failed)} FAILED (>1%, not reported) | {len(suspect)} SUSPECT (0-1%, reported+flagged)")
    print(f"  {'scenario':16} {'obj_eur':>12} {'>':>3} {'restriction':16} {'restr_obj':>11} {'excess':>8}  tier")
    for r in v:
        print(f"  {r['scenario']:16} {r['obj']:12,.0f}  >  {r['restriction']:16} "
              f"{r['restriction_obj']:11,.0f} {r['excess_pct']:7.1f}%  {r['tier'].upper()}")


if __name__ == "__main__":
    main()
