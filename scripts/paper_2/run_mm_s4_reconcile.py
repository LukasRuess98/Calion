"""MM-S4 two-run reconciliation (299k vs 493k) — isolated output + pinned manifest.

Runs MM-S4-HK0 into a SEPARATE output dir (NOT the canonical paper2_runs/MM-S4-HK0,
to avoid clobbering a converged campaign result — see memory feedback_scenario_id_
clobbering) and writes a run_manifest.json pinning the year cut, git commit, and the
hashes of the temperature-critical configs, so the main-vs-e8e445e comparison differs
only by what we intend (code state), never by weather year or config drift.

Usage:
    PYTHONPATH=. python scripts/paper_2/run_mm_s4_reconcile.py <tag>
      <tag> = subdir under output/mm_s4_reconcile/ (e.g. "main" or "e8e445e")
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
from scripts.paper_2 import scenario_runner as sr  # noqa: E402

SCEN = "MM-S4-HK0"  # overridable via argv[2]
CFGS = [
    "configs/paper_2/Memmingen_P2_base.yaml",
    "configs/paper_2/scenarios.yaml",
    "configs/paper_2/storage_geometry.yaml",
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else "MISSING"


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=_ROOT, text=True).strip()
    except Exception as e:
        return f"ERR:{e}"


def main() -> None:
    tag = sys.argv[1] if len(sys.argv) > 1 else "main"
    scen = sys.argv[2] if len(sys.argv) > 2 else SCEN
    out = _ROOT / "output" / "mm_s4_reconcile" / tag
    (out / "runs").mkdir(parents=True, exist_ok=True)
    # Nest per-tag so parallel tags don't collide on the shared Gurobi-log dir
    # (scenario_runner derives logs from OUT_BASE.parent/logs).
    sr.OUT_BASE = out / "runs"

    manifest = {
        "tag": tag,
        "scenario": scen,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_short": _git("rev-parse", "--short", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "year_pin": "2025-01-01 00:00 .. 2025-12-31 23:00 (Memmingen_P2_base.yaml horizon)",
        "note": "load/price/CO2 are columns of one xlsx -> auto year-aligned",
        "config_sha256_16": {c: _sha(_ROOT / c) for c in CFGS},
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[reconcile:{tag}] manifest written -> {out/'run_manifest.json'}")
    print(json.dumps(manifest, indent=2))

    res = sr.run_all_scenarios(scenario_ids=[scen], dry_run=False,
                               force_rerun=True, gurobi_threads=4)
    (out / "result_summary.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")

    # Solver-parameter guard: confirm the config's bound-knobs actually reached Gurobi.
    from scripts.paper_2.verify_solver_params import (
        verify_solver_params, SolverParamMismatch, mip_start_status)
    import yaml
    _mmcfg = yaml.safe_load(open(_ROOT / "configs/paper_2/Memmingen_P2_base.yaml", encoding="utf-8"))
    _req = (_mmcfg.get("run", {}) or {}).get("solver_options", {})
    # scenario_runner derives the Gurobi log from OUT_BASE.parent/logs, and we
    # redirected OUT_BASE to `out`, so the live log is here (NOT output/logs, which
    # would be a stale pre-fix log and trip a false mismatch).
    _glog = out / "logs" / f"gurobi_{scen}.log"
    # MIP-start acceptance -> manifest (never let a silently-dropped start be invisible).
    manifest["mip_start"] = mip_start_status(_glog) if _glog.exists() else {"mip_start": "no_log"}
    print(f"[reconcile:{tag}] MIP-start status: {manifest['mip_start']}")
    # The guard compares the config's solver_options to Gurobi's echoed params. When we
    # intentionally override via env (CALION_MIPFOCUS / CUTS / TIMELIMIT / MIPGAP / PRESOLVE /
    # FEASTOL), a "mismatch" is expected and NOT an error — so it must not abort the run
    # (results/meta are already written by this point). Non-fatal: record and continue.
    import os as _os_g
    _overridden = any(_os_g.environ.get(k) for k in (
        "CALION_MIPFOCUS", "CALION_CUTS", "CALION_TIMELIMIT", "CALION_MIPGAP",
        "CALION_PRESOLVE", "CALION_FEASTOL", "CALION_HEURISTICS"))
    try:
        rep = verify_solver_params(_glog, _req, strict=not _overridden)
        manifest["solver_param_check"] = rep
        print(f"[reconcile:{tag}] solver-param guard OK: {rep['requested']}")
    except SolverParamMismatch as e:
        manifest["solver_param_check"] = {"ok": False, "error": str(e), "expected_env_override": _overridden}
        (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if _overridden:
            print(f"[reconcile:{tag}] solver-param mismatch EXPECTED (env override) — continuing")
        else:
            raise
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[reconcile:{tag}] done -> {out}")


if __name__ == "__main__":
    main()
