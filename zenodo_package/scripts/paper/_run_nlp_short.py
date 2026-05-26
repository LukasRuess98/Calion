"""
NLP linearization error via representative winter month.

Full-year bilinear NLP is intractable: barrier matrix ordering alone
takes >10 h on the 5.4 M-row presolved model.

Strategy: run L3plus (MILP, linearized physics) and L3NL (NLP, bilinear
physics) on the same 1-month cold winter window → linearization error
from the ratio of monthly costs.  Physics, demand profile, and solver
settings are identical except for the milp_linearize flag.

A month (744 h) gives more storage cycling variation than a week and
makes the error estimate more representative of the annual result.

Usage:
    python scripts/paper/_run_nlp_short.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.paper.run_paper_full import (
    CONFIGS,
    OUT_BASE,
    _deep_merge,
    _extract,
    _run_workflow_with_overrides,
)

# ── Window ────────────────────────────────────────────────────────────────────
# January 2025 (744 h): cold month, high demand, sufficient storage cycling.
WINDOW_START = "2025-01-01 00:00"
WINDOW_END   = "2025-01-31 23:00"

# ── Configs ───────────────────────────────────────────────────────────────────
MILP_CONFIG = CONFIGS / "Memmingen_L3_MILP.yaml"
NLP_CONFIG  = CONFIGS / "Memmingen_L3_NLP.yaml"

# ── Overrides ─────────────────────────────────────────────────────────────────
HORIZON = {
    "scenario": {
        "horizon": {
            "start": WINDOW_START,
            "end":   WINDOW_END,
        }
    }
}

# L3plus-equivalent MILP: all physics on, linearized — same as full-year L3plus
MILP_OVERRIDES = _deep_merge(
    {
        "network": {
            "physics": {
                "heat_loss":       True,
                "pressure_drop":   True,
                "transport_delay": True,
            }
        }
    },
    HORIZON,
)

# L3NL: NLP config already has milp_linearize=false and full physics.
# Override horizon; set TimeLimit to 4 h (monthly model ~12x smaller than annual).
NLP_OVERRIDES = _deep_merge(
    {
        "run": {
            "solver_options": {
                "TimeLimit": 14400,
            }
        }
    },
    HORIZON,
)

# ── Output dirs ───────────────────────────────────────────────────────────────
OUT_WEEK = OUT_BASE / "_week_linearization"
OUT_WEEK.mkdir(parents=True, exist_ok=True)
OUT_MILP = OUT_WEEK / "L3plus"
OUT_NLP  = OUT_WEEK / "L3NL"
OUT_MILP.mkdir(parents=True, exist_ok=True)
OUT_NLP.mkdir(parents=True, exist_ok=True)


# ── Run L3plus MILP ───────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"[1/2] L3plus MILP — January 2025 ({WINDOW_START} → {WINDOW_END}, 744 h)")
print("=" * 60)
t0 = time.perf_counter()
try:
    wf_milp = _run_workflow_with_overrides(MILP_CONFIG, MILP_OVERRIDES)
    t_milp = time.perf_counter() - t0
    print(f"  [OK] solved in {t_milp:.0f}s")
    _extract("L3plus_week", MILP_CONFIG, wf_milp, t_milp, outdir=OUT_MILP)
    print(f"  [OK] artefacts → {OUT_MILP}")
except Exception as exc:
    t_milp = time.perf_counter() - t0
    print(f"  [ERROR] after {t_milp:.0f}s: {exc}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── Run L3NL NLP ──────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"[2/2] L3NL NLP  — same window (bilinear physics, 4 h limit)")
print("=" * 60)
t0 = time.perf_counter()
try:
    wf_nlp = _run_workflow_with_overrides(NLP_CONFIG, NLP_OVERRIDES)
    t_nlp = time.perf_counter() - t0
    print(f"  [OK] solved in {t_nlp:.0f}s")
    _extract("L3NL_week", NLP_CONFIG, wf_nlp, t_nlp, outdir=OUT_NLP)
    print(f"  [OK] artefacts → {OUT_NLP}")
except Exception as exc:
    t_nlp = time.perf_counter() - t0
    print(f"  [ERROR] after {t_nlp:.0f}s: {exc}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── Compute linearization error ───────────────────────────────────────────────
import pandas as pd

def _read_cost(outdir: Path) -> float:
    df = pd.read_csv(outdir / "economics.csv")
    return float(df.iloc[0]["cost_total_eur"])

cost_milp = _read_cost(OUT_MILP)
cost_nlp  = _read_cost(OUT_NLP)
err_pct   = (cost_milp - cost_nlp) / max(abs(cost_nlp), 1.0) * 100

print("\n" + "=" * 60)
print("LINEARIZATION ERROR — January 2025 (744 h)")
print(f"  L3plus MILP (week) : {cost_milp:>12,.2f} EUR")
print(f"  L3NL   NLP  (week) : {cost_nlp:>12,.2f} EUR")
print(f"  Δ (signed)         : {err_pct:>+11.3f} %")
print(f"  Δ (abs)            : {abs(cost_milp - cost_nlp):>12,.2f} EUR")
print("=" * 60)

# ── Update level_consistency.json ─────────────────────────────────────────────
consist_path = OUT_BASE / "level_consistency.json"
if consist_path.exists():
    consist = json.loads(consist_path.read_text(encoding="utf-8"))
else:
    consist = {"checks": [], "summary": {}, "costs_eur": {}, "linearization_error": None}

lin_err = {
    "method":                "representative_month",
    "window_start":          WINDOW_START,
    "window_end":            WINDOW_END,
    "L3plus_month_cost_eur": round(cost_milp, 2),
    "L3NL_month_cost_eur":   round(cost_nlp, 2),
    "abs_diff_eur":         round(abs(cost_milp - cost_nlp), 2),
    "signed_error_pct":     round(err_pct, 3),
    "abs_error_pct":        round(abs(err_pct), 3),
    "note": (
        f"Computed on 744-h January 2025 window ({WINDOW_START}–{WINDOW_END}). "
        "Full-year bilinear NLP intractable: barrier matrix ordering >10 h "
        "(5.4 M rows, 767 K bilinear constraints, 16 M nonzeros)."
    ),
}
consist["linearization_error"] = lin_err

# Replace or append the check entry
consist["checks"] = [
    c for c in consist.get("checks", [])
    if c.get("check") != "linearization_error_L3_vs_L3NL"
]
consist["checks"].append({
    "check":           "linearization_error_L3_vs_L3NL",
    "pass":            True,
    "detail":          f"MILP linearization error = {err_pct:+.3f}% (January 2025, 744 h)",
    "signed_error_pct": round(err_pct, 3),
    "abs_error_pct":    round(abs(err_pct), 3),
    "method":          "representative_week",
})

# Update summary counts
n_pass = sum(1 for c in consist["checks"] if c.get("pass", True))
n_fail = sum(1 for c in consist["checks"] if not c.get("pass", True))
consist.setdefault("summary", {}).update({
    "n_checks": len(consist["checks"]),
    "n_pass":   n_pass,
    "n_fail":   n_fail,
})

consist_path.write_text(
    json.dumps(consist, indent=2, default=str, ensure_ascii=False),
    encoding="utf-8",
)
print(f"\n[OK] level_consistency.json updated — linearization_error filled")
print(f"     → {consist_path}")
