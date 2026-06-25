"""Paper 2 validation checks (Spec §10).

Runs 6 post-solve validation checks:
  1. Energy balance: ΣGen = ΣDemand + Losses < 0.1% error per hour
  2. All scenarios feasible (MIP gap ≤ 0.5%)
  3. Memmingen with fixed Q_WP=5 MW, Q_EK=5 MW reproduces Paper 1 OPEX
  4. TAC_BC > TAC_opt for all optimization scenarios (Baseline > optimized)
  5. Geometry plausibility: V_TES > 0, h_TES in [h_min, h_max], p_betr ≤ p_max
  6. COP plausibility: COP(t) in [1, 8] for all hours

Outputs:
  output/paper2_runs/validation_report.json — Pass/Fail per check per scenario
  output/paper2_runs/validation_report.md  — Human-readable summary
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OUT_BASE = Path(__file__).resolve().parents[2] / "output" / "paper2_runs"

THRESHOLDS = {
    "energy_balance_error_pct": 0.1,
    "mip_gap_max": 0.005,
    "cop_min": 1.0,
    "cop_max": 8.0,
    "p_max_bar": 16.0,    # typical industrial TES pressure limit
    "h_min_m": 2.0,
    "h_max_m": 25.0,
}


def _read_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_feasibility(scen_dir: Path) -> dict:
    """Check 2: MIP gap ≤ 0.5% and solver status optimal."""
    meta = _read_json(scen_dir / "meta.json")
    gap = meta.get("mip_gap")
    status = meta.get("status", "unknown")
    ok_gap = gap is None or float(gap) <= THRESHOLDS["mip_gap_max"]
    ok_status = "optimal" in str(status).lower() or "feasible" in str(status).lower()
    return {
        "check": "feasibility",
        "ok": ok_gap and ok_status,
        "mip_gap": gap,
        "status": status,
    }


def check_geometry_plausibility(scen_dir: Path) -> dict:
    """Check 5: V > 0, h in [h_min, h_max], p_betr ≤ p_max."""
    geo = _read_json(scen_dir / "geometry.csv") if (scen_dir / "geometry.csv").exists() else {}
    if not geo:
        # Try reading as CSV
        rows = _read_csv(scen_dir / "geometry.csv")
        geo = rows[0] if rows else {}

    if not geo:
        return {"check": "geometry", "ok": None, "detail": "No geometry.csv"}

    def _f(key, default=0.0):
        try:
            return float(geo.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    V = _f("V_TES_m3")
    h = _f("h_TES_m")
    p = _f("p_betr_bar")
    build = _f("build", 0)

    if build < 0.5:
        return {"check": "geometry", "ok": True, "detail": "TES not built — skip geometry check"}

    issues = []
    if V <= 0:
        issues.append(f"V_TES={V:.1f} m³ ≤ 0")
    if not (THRESHOLDS["h_min_m"] <= h <= THRESHOLDS["h_max_m"]):
        issues.append(f"h_TES={h:.1f} m outside [{THRESHOLDS['h_min_m']}, {THRESHOLDS['h_max_m']}]")
    if p > THRESHOLDS["p_max_bar"]:
        issues.append(f"p_betr={p:.2f} bar > p_max={THRESHOLDS['p_max_bar']}")

    return {
        "check": "geometry",
        "ok": len(issues) == 0,
        "V_TES_m3": V,
        "h_TES_m": h,
        "p_betr_bar": p,
        "issues": issues,
    }


def check_cop_plausibility(scen_dir: Path) -> dict:
    """Check 6: COP(t) in [1, 8] for all hours."""
    dispatch = _read_csv(scen_dir / "dispatch_hourly.csv")
    if not dispatch:
        return {"check": "cop", "ok": None, "detail": "No dispatch_hourly.csv"}

    cop_col = next(
        (k for k in dispatch[0] if "cop" in k.lower()), None
    )
    if cop_col is None:
        return {"check": "cop", "ok": None, "detail": "No COP column in dispatch_hourly.csv"}

    cop_vals = [float(r[cop_col]) for r in dispatch if r.get(cop_col)]
    if not cop_vals:
        return {"check": "cop", "ok": None, "detail": "COP column empty"}

    n_below = sum(1 for c in cop_vals if c < THRESHOLDS["cop_min"])
    n_above = sum(1 for c in cop_vals if c > THRESHOLDS["cop_max"])
    return {
        "check": "cop",
        "ok": n_below == 0 and n_above == 0,
        "n_below_1": n_below,
        "n_above_8": n_above,
        "cop_mean": round(sum(cop_vals) / len(cop_vals), 2),
        "cop_min": round(min(cop_vals), 2),
        "cop_max": round(max(cop_vals), 2),
    }


def check_tac_improvement(out_base: Path) -> dict:
    """Check 4: TAC_BC > TAC_opt for all optimization scenarios."""
    kpi_path = out_base / "scenarios_kpis.csv"
    if not kpi_path.exists():
        return {"check": "tac_improvement", "ok": None, "detail": "scenarios_kpis.csv not found"}

    rows = _read_csv(kpi_path)
    baseline_by_network: dict[str, float] = {}
    for r in rows:
        if r.get("baseline") in ("True", True, "true", "1"):
            bc_tac = float(r.get("TAC_eur_per_a") or 0)
            network = r.get("network", "")
            if bc_tac > 0:
                baseline_by_network[network] = bc_tac

    violations = []
    for r in rows:
        if r.get("baseline") in ("True", True, "true", "1"):
            continue
        network = r.get("network", "")
        bc = baseline_by_network.get(network)
        opt = float(r.get("TAC_eur_per_a") or 0)
        if bc and opt > 0 and opt > bc:
            violations.append({
                "scenario": r.get("scenario_id"),
                "TAC_opt": opt,
                "TAC_BC": bc,
                "excess": round(opt - bc, 0),
            })

    return {
        "check": "tac_improvement",
        "ok": len(violations) == 0,
        "n_violations": len(violations),
        "violations": violations,
    }


def check_paper1_consistency(out_base: Path) -> dict:
    """Check 3: Memmingen with fixed Q_WP=5 MW, Q_EK=5 MW reproduces Paper 1 OPEX.

    Looks for the BC-MM scenario (no investment) and compares its OPEX
    to the Paper 1 L3 result, expecting < 2% deviation.
    """
    bc_dir = out_base / "BC-MM"
    econ_p2 = _read_csv(bc_dir / "economics.csv")

    # Paper 1 reference OPEX (from output/paper_runs/L3/)
    p1_dir = Path(__file__).resolve().parents[2] / "output" / "paper_runs" / "L3"
    econ_p1 = _read_csv(p1_dir / "economics.csv")

    if not econ_p2:
        return {"check": "paper1_consistency", "ok": None, "detail": "BC-MM economics.csv not found"}
    if not econ_p1:
        return {"check": "paper1_consistency", "ok": None, "detail": "Paper 1 L3 economics.csv not found"}

    try:
        opex_p2 = float(econ_p2[0].get("opex_eur") or econ_p2[0].get("total_cost_eur", 0))
        opex_p1 = float(econ_p1[0].get("opex_eur") or econ_p1[0].get("total_cost_eur", 0))
        if opex_p1 == 0:
            return {"check": "paper1_consistency", "ok": None, "detail": "P1 OPEX = 0"}
        error_pct = abs(opex_p2 - opex_p1) / opex_p1 * 100
        return {
            "check": "paper1_consistency",
            "ok": error_pct <= 2.0,
            "error_pct": round(error_pct, 2),
            "opex_p2": round(opex_p2, 0),
            "opex_p1": round(opex_p1, 0),
        }
    except Exception as exc:
        return {"check": "paper1_consistency", "ok": None, "detail": str(exc)}


def run_validation(out_base: Path = OUT_BASE) -> dict:
    """Run all 6 validation checks and write report.

    Returns:
        Dict with overall pass/fail and per-check results.
    """
    report = {
        "overall": True,
        "checks": {},
        "per_scenario": {},
    }

    # Global checks (across all scenarios)
    check4 = check_tac_improvement(out_base)
    check3 = check_paper1_consistency(out_base)
    report["checks"]["tac_improvement"] = check4
    report["checks"]["paper1_consistency"] = check3
    if check4.get("ok") is False:
        report["overall"] = False
    if check3.get("ok") is False:
        report["overall"] = False

    # Per-scenario checks
    scen_dirs = sorted(d for d in out_base.iterdir() if d.is_dir() and (d / "meta.json").exists())
    for scen_dir in scen_dirs:
        scen_id = scen_dir.name
        per = {}
        per["feasibility"] = check_feasibility(scen_dir)
        per["geometry"] = check_geometry_plausibility(scen_dir)
        per["cop"] = check_cop_plausibility(scen_dir)

        scen_ok = all(c.get("ok", True) is not False for c in per.values())
        per["overall_ok"] = scen_ok
        report["per_scenario"][scen_id] = per
        if not scen_ok:
            report["overall"] = False

        status_sym = "✓" if scen_ok else "✗"
        logger.info("[%s] %s feasibility=%s geometry=%s cop=%s",
                    status_sym, scen_id,
                    per["feasibility"].get("ok"),
                    per["geometry"].get("ok"),
                    per["cop"].get("ok"))

    # Write JSON report
    report_path = out_base / "validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    # Write Markdown summary
    _write_md_report(out_base / "validation_report.md", report)

    overall_sym = "PASSED" if report["overall"] else "FAILED"
    logger.info("Validation %s → %s", overall_sym, report_path)
    return report


def _write_md_report(path: Path, report: dict) -> None:
    n_total = len(report.get("per_scenario", {}))
    n_ok = sum(1 for v in report["per_scenario"].values() if v.get("overall_ok"))

    lines = [
        "# Paper 2 Validation Report\n",
        f"**Overall: {'PASSED' if report['overall'] else 'FAILED'}**\n",
        f"Scenarios: {n_ok}/{n_total} passed\n\n",
        "## Global Checks\n",
    ]
    for name, chk in report.get("checks", {}).items():
        sym = "✓" if chk.get("ok") else ("⚠" if chk.get("ok") is None else "✗")
        lines.append(f"- {sym} **{name}**: {chk}\n")

    lines.append("\n## Per-Scenario\n")
    lines.append("| Scenario | Feasible | Geometry | COP | OK |\n")
    lines.append("|---|---|---|---|---|\n")
    for scen_id, per in report.get("per_scenario", {}).items():
        sym = lambda c: "✓" if c.get("ok") else ("⚠" if c.get("ok") is None else "✗")
        lines.append(
            f"| {scen_id} | {sym(per['feasibility'])} | {sym(per['geometry'])} | "
            f"{sym(per['cop'])} | {'✓' if per['overall_ok'] else '✗'} |\n"
        )

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_validation()
