"""Dominance gate: assert UB(S0) <= UB(BASE) + 1e-6 per network/heat-curve stage.

2026-09-25 (I2, author decision, docs SS4bc): S0 scenarios are BASE scenarios with an
ADDED investment option (HP/EK become investable) -- S0 can always replicate BASE's
dispatch by building nothing, so its true optimum can NEVER cost more than BASE's. A
reported incumbent that violates this is not "a wide interval", it is a FAILED run
(the solver's best-known solution is provably suboptimal) and must be reported as
such, not silently accepted.

Usage:
    python scripts/paper_2/check_dominance_gate.py <out_base_1> [<out_base_2> ...]

Each <out_base> is a CALION_OUT_BASE directory (e.g. output/mm_s4_reconcile/b4_mm)
containing per-scenario subdirectories with meta.json (obj_eur, mip_gap, status).
Pairs are matched by (network, heat_curve_stage) inferred from scenario IDs:
  BASE:  BC-MM, BC-MM-HK0, BC-SB, BC-SB-HK0        (BASE-FIX / BASE-HK0)
  S0:    MM-S0-HK0, SB-S0-HK0                       (S0-HK0 only, per the campaign so far)
"""
import json
import sys
from pathlib import Path

# (network, heat_curve_stage) -> scenario id, for both BASE and S0
_PAIRS = [
    ("MM", "HK0", "BC-MM-HK0", "MM-S0-HK0"),
    ("SB", "HK0", "BC-SB-HK0", "SB-S0-HK0"),
]

TOL = 1e-6


def _load_meta(out_base: Path, scen_id: str) -> dict | None:
    p = out_base / scen_id / "meta.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main(out_bases: list[str]) -> int:
    paths = [Path(p) for p in out_bases]
    rows = []
    any_fail = False
    for net, hk, base_id, s0_id in _PAIRS:
        base_meta = s0_meta = None
        base_src = s0_src = None
        for p in paths:
            m = _load_meta(p, base_id)
            if m is not None:
                base_meta, base_src = m, p
            m = _load_meta(p, s0_id)
            if m is not None:
                s0_meta, s0_src = m, p
        if base_meta is None or s0_meta is None:
            rows.append((net, hk, "SKIP (missing meta.json)", None, None, None, None))
            continue
        ub_base = float(base_meta["obj_eur"])
        ub_s0 = float(s0_meta["obj_eur"])
        violation = ub_s0 - ub_base
        passed = violation <= TOL
        any_fail = any_fail or not passed
        rows.append((net, hk, "PASS" if passed else "FAIL", ub_base, ub_s0, violation, (base_src, s0_src)))

    print(f"{'Net':4s} {'HK':4s} {'Gate':6s} {'UB(BASE)':>16s} {'UB(S0)':>16s} {'UB(S0)-UB(BASE)':>18s}")
    for net, hk, status, ub_base, ub_s0, violation, srcs in rows:
        if ub_base is None:
            print(f"{net:4s} {hk:4s} {status}")
            continue
        print(f"{net:4s} {hk:4s} {status:6s} {ub_base:16,.2f} {ub_s0:16,.2f} {violation:18,.2f}")
        if status == "FAIL":
            print(f"     ^ DOMINANCE VIOLATION: S0 ({srcs[1]}) costs {violation:,.2f} EUR MORE than "
                  f"BASE ({srcs[0]}) despite being a strict relaxation. This is a FAILED run, not a "
                  f"wide interval -- the reported S0 incumbent is not usable.")

    if any_fail:
        print("\nRESULT: at least one dominance gate FAILED.")
        return 1
    print("\nRESULT: all dominance gates PASS.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
