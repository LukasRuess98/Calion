"""Solver-parameter guard: did the config's Gurobi options actually reach the solver?

Motivation (2026-09-05): the frozen paper-2 campaign ran at MIPFocus=1 / no-Cuts even
though Memmingen_P2_base.yaml specifies Cuts=2 / MIPFocus=2 (the documented weak-LP-bound
fix). A hardcoded override in solver.py (_solve_milp_stage) silently replaced the config's
solver_options. The methods section therefore described settings that were never used.

This module turns "did the settings take?" into a question every run answers itself:
parse the Gurobi log's "Set parameter X to value Y" echo, compare against the config's
requested solver_options, and FAIL LOUD on any mismatch of the bound-tightening knobs —
the same guard class as the V_max<=unit_tank warning in geometric_storage.py.

Usage (programmatic):
    from scripts.paper_2.verify_solver_params import verify_solver_params
    rep = verify_solver_params(gurobi_log_path, requested_solver_options)
    # rep = {"actual": {...}, "requested": {...}, "mismatches": {...}, "ok": bool}
    # raises SolverParamMismatch if a CRITICAL knob differs (unless strict=False)
"""
from __future__ import annotations
import re
from pathlib import Path

# Knobs whose silent loss corrupts the reported method (must match config exactly).
_CRITICAL = ("Cuts", "MIPFocus", "Heuristics", "NumericFocus")
_SET_RE = re.compile(r"Set parameter (\w+) to value ([-\d.eE+]+)")


class SolverParamMismatch(RuntimeError):
    """Raised when the solver ran with different bound-knobs than the config asked for."""


def parse_actual_params(gurobi_log: str | Path) -> dict[str, float]:
    """Extract the LAST 'Set parameter X to value Y' per key from a Gurobi log."""
    text = Path(gurobi_log).read_text(encoding="utf-8", errors="ignore")
    out: dict[str, float] = {}
    for name, val in _SET_RE.findall(text):
        try:
            out[name] = float(val)
        except ValueError:
            continue
    return out


def mip_start_status(gurobi_log: str | Path) -> dict:
    """Report whether a user MIP start was ACCEPTED or silently discarded.

    Gurobi announces a processed start with 'Processing user MIP start' but only an
    ACCEPTED one with 'Loaded user MIP start with objective X'. A partial/infeasible
    start is dropped with no error. This surfaces that into the manifest so a failed
    MIP start is never invisible (2026-09-05).
    """
    text = Path(gurobi_log).read_text(encoding="utf-8", errors="ignore")
    processed = "user MIP start" in text.lower()
    m = re.search(r"Loaded user MIP start with objective ([-\d.eE+]+)", text)
    if not processed:
        return {"mip_start": "none"}
    if m:
        return {"mip_start": "accepted", "objective": float(m.group(1))}
    return {"mip_start": "rejected_or_partial"}


def verify_solver_params(gurobi_log: str | Path, requested: dict,
                         *, strict: bool = True, logger=None) -> dict:
    """Compare requested (config) vs actual (Gurobi log) bound-knobs.

    Returns a report dict; raises SolverParamMismatch on a critical mismatch when
    strict=True. Non-critical differences are reported but never raise.
    """
    actual = parse_actual_params(gurobi_log)
    mism: dict[str, dict] = {}
    for k in _CRITICAL:
        if k in requested:
            want = float(requested[k])
            got = actual.get(k)
            if got is None or abs(got - want) > 1e-9:
                mism[k] = {"requested": want, "actual": got}
    report = {"actual": {k: actual.get(k) for k in _CRITICAL},
              "requested": {k: requested.get(k) for k in _CRITICAL if k in requested},
              "mismatches": mism, "ok": not mism}
    if mism:
        msg = ("[SOLVER-PARAM GUARD] config solver_options did NOT reach the solver: "
               + "; ".join(f"{k}: config={v['requested']} but Gurobi={v['actual']}"
                           for k, v in mism.items()))
        if logger:
            logger.error(msg)
        if strict:
            raise SolverParamMismatch(msg)
    elif logger:
        logger.info("[SOLVER-PARAM GUARD] OK — bound-knobs match config: %s",
                    report["requested"])
    return report


if __name__ == "__main__":
    import sys, json
    log = sys.argv[1]
    req = {"Cuts": 2, "MIPFocus": 2, "Heuristics": 0.1, "NumericFocus": 2}
    try:
        print(json.dumps(verify_solver_params(log, req, strict=False), indent=2))
    except Exception as e:
        print("ERROR:", e)
