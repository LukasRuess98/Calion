"""
Full paper run orchestrator — executes all phases in order.

Phases:
  0.  Validation Stage 1 (§4.2): legacy model + network validation (quality gate)
  1.  Primary runs        (§2):  L1, L2, L3, L3+, L3NL
  1b. Cross-level check   (§2):  auto-injected after Phase 1 — verifies model
      hierarchy (L1≤L2≤L3 costs, L1 losses=0, pump cost L3+≥L3) and computes
      the linearization error KPI (L3NL vs L3).
      → output/paper_runs/level_consistency.json
  2.  Validation Stage 2  (§4.2): asset plausibility checks (needs Phase 1 results)
  3.  Sensitivity runs    (§4):  11 scenarios x 4 levels
  4.  Synthetic runs      (§5):  N configs x 5 levels
  5.  Tables              (§7):  tools/tablegen.py
  6.  Figures             (§8):  tools/figgen.py
  7.  Fill paper          (§9):  tools/fill_paper.py --auto

Pipeline logic:
  Phase 0 (Stage 1) is a QUALITY GATE: validates the network model against
  historical measurements BEFORE running any optimization. If T_supply MAE
  exceeds thresholds, the user is warned to recalibrate.
  Note: with MILP only 1/5 Stage 1 KPIs are evaluable (annual energy balance).
  Temperature KPIs require the MIQP run (Gurobi NonConvex=2).

  Phase 1b runs automatically after Phase 1 (use --skip-consistency to disable).
  It verifies that the model hierarchy holds and writes the linearization error
  (core paper result: how much does MILP approximation distort cost vs NLP?).

  Phase 2 (Stage 2) runs AFTER optimization (Phase 1) because it checks
  asset dispatch plausibility (COP, SOC, eboiler) from dispatch_hourly.csv.

Usage:
    python scripts/paper/run_paper_full.py                   # all phases
    python scripts/paper/run_paper_full.py --phases 0        # validation Stage 1 only
    python scripts/paper/run_paper_full.py --phases 1 2      # primary + consistency + asset validation
    python scripts/paper/run_paper_full.py --phases 1 --skip-consistency  # primary only, no check
    python scripts/paper/run_paper_full.py --phases 3        # sensitivity only
    python scripts/paper/run_paper_full.py --phases 4        # synthetic only
    python scripts/paper/run_paper_full.py --phases 5 6 7    # tables + figures + fill
    python scripts/paper/run_paper_full.py --skip-nl         # skip all L3NL runs (no Gurobi)
    python scripts/paper/run_paper_full.py --dry-run         # print plan, do not run
    python scripts/paper/run_paper_full.py --phases 0 --skip-model  # validation, reuse legacy run
    python scripts/paper/run_paper_full.py --phases 6 --figs F2 FV1  # specific figures only

Notes:
  - Phase 0 (Stage 1) is a quality gate: if T_supply MAE > threshold, consider
    recalibrating before proceeding.
  - Phase 1b (level_consistency.json) is the paper's core sanity check — always review it.
  - Phase 2 (Stage 2) requires Phase 1 dispatch results (L3/dispatch_hourly.csv).
  - L1/L2/L3/L3+ fall back to HiGHS if Gurobi is unavailable.
  - L3NL is skipped automatically if Gurobi is not installed (unless --fail-on-skip).
  - Results go to output/paper_runs/<run_id>/.
  - Sensitivity to output/paper_runs/sensitivity/<level>_<scenario>/.
  - Synthetic  to output/paper_runs/synth/<synth_id>_<level>/.
  - Validation to output/validation/.
  - Figures    to output/paper_runs/figures/.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# In the standalone zenodo package, pre-computed results live in results/.
# In the full development repo they live in output/paper_runs/.
# New runs always write to output/paper_runs/ so they don't overwrite the
# pre-computed artefacts shipped in results/.
OUT_BASE   = ROOT / "output" / "paper_runs"
RESULTS_BASE = ROOT / "results" if (ROOT / "results").exists() else OUT_BASE
SYNTH_DIR  = ROOT / "synth_configs"
CONFIGS    = ROOT / "configs" / "memmingen"

# ──────────────────────────────────────────────────────────────────────────────
# Gurobi detection
# ──────────────────────────────────────────────────────────────────────────────

def _gurobi_ok() -> bool:
    try:
        import gurobipy  # noqa: F401
        return True
    except ImportError:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Primary run definitions
# ──────────────────────────────────────────────────────────────────────────────

PRIMARY_RUNS = [
    {
        "run_id": "L1",
        "config": CONFIGS / "Memmingen_L1.yaml",
        "overrides": None,
        "needs_gurobi": False,
    },
    {
        "run_id": "L2",
        "config": CONFIGS / "Memmingen_L2.yaml",
        "overrides": None,
        "needs_gurobi": False,
    },
    {
        "run_id": "L3",
        "config": CONFIGS / "Memmingen_L3_MILP.yaml",
        "overrides": {
            "network": {"physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False}}
        },
        "needs_gurobi": False,
    },
    {
        "run_id": "L3plus",
        "config": CONFIGS / "Memmingen_L3_MILP.yaml",
        "overrides": {
            "network": {"physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": True}}
        },
        "needs_gurobi": False,
    },
    # In PRIMARY_RUNS, ersetze den L3NL-Eintrag:
    {
        "run_id": "L3NL",
        "config": CONFIGS / "Memmingen_L3_NLP.yaml",
        "overrides": None,   # fix_binaries_from ist bereits in der YAML
        "needs_gurobi": True,
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Sensitivity scenarios (§4)
# ──────────────────────────────────────────────────────────────────────────────

SENSITIVITY_SCENARIOS = {
    "baseline":   {},                                          # 100 EUR/t aus YAML
    "gas_high":   {"fuels": {"gas": {"price_eur_mwh": 60.0}}},
    "gas_low":    {"fuels": {"gas": {"price_eur_mwh": 35.0}}},
    "elec_low":   {"grid": {"gridcost_eur_mwh": 15.0},
                   "costs": {"include_gridcost_in_energy": True}},   # +15 EUR/MWh adder
    "elec_high":  {"grid": {"gridcost_eur_mwh": 45.0},
                   "costs": {"include_gridcost_in_energy": True}},   # +45 EUR/MWh adder
    "co2_high":   {"costs": {"co2_price_eur_per_t": 200.0}},
    "co2_low":    {"costs": {"co2_price_eur_per_t": 50.0}},
    "cold":       {"_demand_scale": 1.10,                             # +10% demand
                   "run": {"solver_options": {"NumericFocus": 3}}},
    "warm":       {"_demand_scale": 0.90},                           # -10% demand
    "cop_low":    {"heat_pumps": {"types": {"standard": {"eta": 0.45}}}},
    "biomass_expensive": {"fuels": {"biomass": {"price_eur_mwh": 55.0}}},
}

SENSITIVITY_LEVELS = ["L1", "L2", "L3", "L3plus"]

LEVEL_TO_PRIMARY = {r["run_id"]: r for r in PRIMARY_RUNS}


# ──────────────────────────────────────────────────────────────────────────────
# Physics override presets
# ──────────────────────────────────────────────────────────────────────────────

SYNTH_PHYSICS = {
    "L1": {
        "network": {"physics": {"heat_loss": False, "pressure_drop": False, "transport_delay": False}}
    },
    "L2": {
        "network": {"physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False}}
    },
    "L3": {
        "network": {"physics": {"heat_loss": True, "pressure_drop": False, "transport_delay": False}}
    },
    "L3plus": {
        "network": {"physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": True}}
    },
    "L3NL": {
        "scenario": {"milp_linearize": False},
        "network":  {"milp_linearize": False,
                     "physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": True}},
        "run": {"solver": "gurobi", "solver_options": {
            "NonConvex": 2, "MIPGap": 0.005, "TimeLimit": 86400,
            "NumericFocus": 2, "Heuristics": 0.8, "OutputFlag": 1, "LogToConsole": 1,
        }},
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict."""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_yaml(path: Path) -> dict:
    """Load YAML with encoding fallback for Windows files."""
    try:
        import yaml
    except ImportError:
        raise RuntimeError("PyYAML required: pip install pyyaml")

    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return yaml.safe_load(path.read_text(encoding=enc)) or {}
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Cannot decode {path} with any known encoding")


def _dump_yaml(cfg: dict, path: Path) -> None:
    """Write YAML with indented sequences (required by calion parser)."""
    try:
        import yaml
    except ImportError:
        raise RuntimeError("PyYAML required: pip install pyyaml")

    class _IndentedDumper(yaml.Dumper):
        def increase_indent(self, flow=False, **_):
            return super().increase_indent(flow=flow, indentless=False)

    path.write_text(
        yaml.dump(cfg, Dumper=_IndentedDumper, allow_unicode=True,
                  default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _apply_demand_scale(cfg: dict, scale: float) -> dict:
    """Scale all consumer demand_fraction values in network.nodes by scale."""
    import copy
    cfg = copy.deepcopy(cfg)
    nodes = cfg.get("network", {}).get("nodes", {})
    for node_cfg in nodes.values():
        for consumer in node_cfg.get("consumers", []):
            existing = consumer.get("demand_fraction", 1.0)
            consumer["demand_fraction"] = round(float(existing) * scale, 6)
    return cfg


def _run_workflow_with_overrides(config_path: Path, overrides: dict | None):
    """Load config, apply overrides, run workflow, return workflow object."""
    from calion.run.workflow import run_workflow
    if not overrides:
        return run_workflow([str(config_path)])
    # Extract special keys before deep-merge
    demand_scale = overrides.pop("_demand_scale", None) if overrides else None
    clean = {k: v for k, v in (overrides or {}).items() if not k.startswith("_")}
    cfg = _load_yaml(config_path)
    if clean:
        cfg = _deep_merge(cfg, clean)
    if demand_scale is not None:
        cfg = _apply_demand_scale(cfg, float(demand_scale))
    tmp = config_path.parent / f"_tmp_{config_path.stem}_{uuid.uuid4().hex[:8]}.yaml"
    _dump_yaml(cfg, tmp)
    try:
        return run_workflow([str(tmp)])
    finally:
        if tmp.exists():
            tmp.unlink()


def _extract(run_id: str, config_path: Path, workflow, elapsed: float,
             outdir: Path | None = None) -> Path:
    """Extract artefacts from workflow result."""
    from scripts.paper.extract_artefacts import extract_all
    return extract_all(
        run_id=run_id,
        config_path=str(config_path),
        workflow=workflow,
        solve_time_s=elapsed,
        outdir=outdir,
    )


def _record(log: list[dict], entry: dict) -> None:
    """Append to in-memory log and write to disk."""
    log.append(entry)
    log_path = OUT_BASE / "run_log.json"
    try:
        log_path.write_text(
            json.dumps(log, indent=2, default=str), encoding="utf-8"
        )
    except Exception:
        pass  # non-critical


def _elapsed_str(seconds: float) -> str:
    """Format elapsed time nicely."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}min"
    else:
        return f"{seconds/3600:.1f}h"


# ──────────────────────────────────────────────────────────────────────────────
# Phase 0 — Validation Stage 1: Network (quality gate, BEFORE optimization)
# ──────────────────────────────────────────────────────────────────────────────

def phase0_validation_stage1(skip_model: bool, dry_run: bool, log: list,
                             miqp_seasons: str | None = None) -> None:
    """
    Stage 1 only: Runs legacy-only model (HP/TES/EBoiler capacity=0) then
    compares simulated T_supply, T_return, flow against historical Excel data.

    This is a QUALITY GATE — if MAE thresholds are not met, the network model
    needs recalibration before optimization results can be trusted.

    Outputs → output/validation/
      stage1_timeseries_{winter,summer}.png
      stage1_error_histograms.png
      stage1_scatter_Tsupply.png
      stage1_heatmap_Terr.png
      kpis.json (partial — stage1 only)
    """
    print("\n" + "="*70)
    print("PHASE 0 — Validation Stage 1: Network hydraulic & thermal (quality gate)")
    print("="*70)
    print("  Purpose: Validate network model BEFORE optimization.")
    print("           Compares legacy-only simulation against historical measurements.")

    val_script = ROOT / "tools" / "validation_runner.py"
    if not val_script.exists():
        print(f"  [WARN] {val_script} not found")
        _record(log, {"phase": 0, "status": "missing_script"})
        return

    cmd = [sys.executable, str(val_script), "--stage", "1"]
    if dry_run:
        cmd.append("--dry-run")
    if skip_model:
        cmd.append("--skip-model")
    if miqp_seasons:
        cmd += ["--miqp-seasons", miqp_seasons]

    print(f"  [CMD] {' '.join(cmd)}")
    if dry_run:
        print("  [DRY] Would run Stage 1 validation (network against measurements)")
        return

    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=ROOT, capture_output=False, text=True)
    elapsed = time.perf_counter() - t0

    status = "ok" if result.returncode == 0 else "warn_threshold"
    print(f"\n  [PHASE 0] done in {_elapsed_str(elapsed)} — status={status}")
    _record(log, {"phase": 0, "status": status, "solve_s": round(elapsed, 1)})

    # Print KPI summary and quality gate assessment
    kpi_path = ROOT / "output" / "validation" / "kpis.json"
    if kpi_path.exists():
        try:
            kpis = json.loads(kpi_path.read_text())
            s1 = kpis.get("stage1", {})
            thresholds = kpis.get("thresholds", {})
            if s1:
                print("\n  ┌─ Stage 1 KPI Summary (Quality Gate) ─────────────────────┐")
                for k, v in s1.items():
                    if isinstance(v, (int, float)):
                        t = thresholds.get(k)
                        flag = ""
                        if t and isinstance(v, float):
                            flag = "  ✓ PASS" if v <= t else "  ✗ FAIL"
                        print(f"  │  {k}: {v:.4f}{flag}")
                print("  └──────────────────────────────────────────────────────────────┘")

                fails = sum(1 for k, v in s1.items()
                            if k in thresholds and isinstance(v, float)
                            and v > thresholds[k])
                if fails > 0:
                    print(f"\n  ⚠️  QUALITY GATE: {fails} KPI(s) exceed threshold!")
                    print("     The network model may need U-value recalibration.")
                    print("     Optimization results may not reflect real-world behavior.")
                    print("     Proceeding anyway — use --phases 0 to debug standalone.")
                else:
                    print("\n  ✓ Quality gate PASSED — network model validated against measurements.")
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — Primary runs
# ──────────────────────────────────────────────────────────────────────────────

def phase1_primary(gurobi: bool, skip_nl: bool, dry_run: bool, log: list,
                   nlp_short: bool = False) -> None:
    """Run L1, L2, L3, L3+, L3NL optimization models."""
    print("\n" + "="*70)
    print("PHASE 1 — Primary runs (§2)")
    print("="*70)

    n_total  = len(PRIMARY_RUNS)
    n_skip   = sum(1 for s in PRIMARY_RUNS
                   if (s["needs_gurobi"] and not gurobi) or (skip_nl and s["run_id"] == "L3NL"))
    print(f"  {n_total} runs configured, {n_total - n_skip} will execute")

    for spec in PRIMARY_RUNS:
        run_id    = spec["run_id"]
        config    = spec["config"]
        overrides = spec.get("overrides")
        needs_g   = spec["needs_gurobi"]

        if needs_g and not gurobi:
            print(f"\n[SKIP] {run_id} — no Gurobi")
            _record(log, {"phase": 1, "run_id": run_id, "status": "skipped"})
            continue

        if skip_nl and run_id == "L3NL":
            print(f"\n[SKIP] {run_id} — skip-nl flag")
            _record(log, {"phase": 1, "run_id": run_id, "status": "skipped"})
            continue

        # Route L3NL to the short-window script when full-year NLP is intractable
        if run_id == "L3NL" and nlp_short:
            if dry_run:
                print(f"\n[DRY] {run_id} — would run _run_nlp_short.py (representative winter week)")
                continue
            print(f"\n[NLP-SHORT] {run_id} — representative winter week (full-year intractable)")
            t0 = time.perf_counter()
            try:
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "paper" / "_run_nlp_short.py")],
                    cwd=ROOT, capture_output=False, text=True,
                )
                elapsed = time.perf_counter() - t0
                status = "ok" if result.returncode == 0 else "error"
                print(f"      done in {_elapsed_str(elapsed)} — {status}")
                _record(log, {"phase": 1, "run_id": run_id, "status": status,
                              "solve_s": round(elapsed, 1), "mode": "short_window"})
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                print(f"      ERROR: {exc}")
                _record(log, {"phase": 1, "run_id": run_id, "status": "error",
                              "error": str(exc)})
            continue

        if not config.exists():
            print(f"\n[SKIP] {run_id} — config missing: {config}")
            _record(log, {"phase": 1, "run_id": run_id, "status": "missing_config"})
            continue

        if dry_run:
            phys = overrides.get("network", {}).get("physics", {}) if overrides else {}
            print(f"\n[DRY] {run_id}  config={config.name}  physics={phys or 'default'}")
            continue

        print(f"\n[RUN] {run_id} — {config.name}")
        if overrides:
            print(f"      physics: {overrides.get('network', {}).get('physics', {})}")

        t0 = time.perf_counter()
        try:
            wf = _run_workflow_with_overrides(config, overrides)
            elapsed = time.perf_counter() - t0
            outdir  = _extract(run_id, config, wf, elapsed)
            obj = 0.0
            if hasattr(wf, 'pf_result') and wf.pf_result and hasattr(wf.pf_result, 'summary'):
                obj = float(wf.pf_result.summary.get("objective", {}).get("OBJ_value_EUR", 0.0))
            print(f"      done in {_elapsed_str(elapsed)}  obj={obj:,.0f} EUR  out={outdir}")
            _record(log, {"phase": 1, "run_id": run_id, "status": "ok",
                          "solve_s": round(elapsed, 1), "obj_eur": obj})
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"      ERROR after {_elapsed_str(elapsed)}: {exc}")
            _record(log, {"phase": 1, "run_id": run_id, "status": "error",
                          "error": str(exc)})


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1b — Cross-level consistency check (runs after Phase 1)
# ──────────────────────────────────────────────────────────────────────────────

def _read_economics(run_id: str) -> dict | None:
    """Load economics.csv for a completed run, return first row as dict."""
    path = OUT_BASE / run_id / "economics.csv"
    if not path.exists():
        path = RESULTS_BASE / run_id / "economics.csv"
    if not path.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_csv(path)
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception:
        return None


def _read_pipes_summary(run_id: str) -> dict | None:
    """Return aggregated pipe statistics from pipes.csv."""
    path = OUT_BASE / run_id / "pipes.csv"
    if not path.exists():
        path = RESULTS_BASE / run_id / "pipes.csv"
    if not path.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_csv(path)
        if df.empty:
            return None
        return {
            "total_annual_loss_MWh": float(df["annual_loss_MWh"].sum()),
            "n_pipes": len(df),
        }
    except Exception:
        return None


def _read_dispatch_summary(run_id: str) -> dict | None:
    """Return aggregate dispatch statistics from dispatch_hourly.csv."""
    path = OUT_BASE / run_id / "dispatch_hourly.csv"
    if not path.exists():
        path = RESULTS_BASE / run_id / "dispatch_hourly.csv"
    if not path.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_csv(path)
        if df.empty:
            return None
        result: dict = {}
        for col in ("Q_loss_total_MW", "P_hp_el_MW", "P_ek_el_MW", "P_chp_el_MW"):
            if col in df.columns:
                result[col.replace("_MW", "_MWh")] = float(df[col].fillna(0).sum())
        if "P_buy_MW" in df.columns:
            result["P_buy_total_MWh"] = float(df["P_buy_MW"].fillna(0).sum())
        return result
    except Exception:
        return None


def phase1b_level_consistency(dry_run: bool, log: list) -> None:
    """
    Cross-level consistency checks after primary runs complete.

    Verifies:
      1. Cost hierarchy: L1 ≤ L2 ≤ L3 ≤ L3plus  (relaxed constraints → lower bound)
      2. Heat losses:    L1 = 0, L2/L3/L3plus/L3NL > 0
      3. Pressure drop:  L3plus pump energy >= L3 pump energy
      4. Linearization error: |L3NL_cost - L3_cost| / L3NL_cost × 100  (paper's core KPI)
      5. Per-run energy-balance closure from validation.json

    Outputs → output/paper_runs/level_consistency.json
    """
    print("\n" + "="*70)
    print("PHASE 1b — Cross-level consistency check")
    print("="*70)
    print("  Purpose: Verify model hierarchy and quantify linearization error.")

    if dry_run:
        print("  [DRY] Would check L1/L2/L3/L3plus/L3NL economics, losses, pump energy.")
        _record(log, {"phase": "1b", "status": "dry_run"})
        return

    run_ids = ["L1", "L2", "L3", "L3plus", "L3NL"]
    eco:   dict[str, dict] = {}
    pipes: dict[str, dict] = {}
    disp:  dict[str, dict] = {}

    for rid in run_ids:
        e = _read_economics(rid)
        if e:
            eco[rid] = e
        p = _read_pipes_summary(rid)
        if p:
            pipes[rid] = p
        d = _read_dispatch_summary(rid)
        if d:
            disp[rid] = d

    available = sorted(eco.keys())
    print(f"  Available runs: {available}")

    checks: list[dict] = []

    # ── 1. Cost table ──────────────────────────────────────────────────────────
    print("\n  ┌─ Objective costs [EUR] ──────────────────────────────────────────┐")
    costs: dict[str, float] = {}
    for rid in ["L1", "L2", "L3", "L3plus", "L3NL"]:
        if rid in eco:
            c = float(eco[rid].get("cost_total_eur", 0.0))
            costs[rid] = c
            print(f"  │  {rid:<8} {c:>15,.0f} EUR")
    print("  └──────────────────────────────────────────────────────────────────┘")

    # ── 2. Cost hierarchy check (L1 ≤ L2 ≤ L3 ≤ L3plus) ─────────────────────
    hierarchy = [("L1", "L2"), ("L2", "L3"), ("L3", "L3plus")]
    for lower, upper in hierarchy:
        if lower not in costs or upper not in costs:
            continue
        ok = costs[lower] <= costs[upper] * 1.005  # 0.5% tolerance for solver gap
        pct_diff = (costs[upper] - costs[lower]) / max(abs(costs[lower]), 1) * 100
        status = "PASS" if ok else "WARN"
        msg = (f"Cost hierarchy {lower}≤{upper}: "
               f"{costs[lower]:,.0f} ≤ {costs[upper]:,.0f} ({pct_diff:+.2f}%)")
        print(f"  [{status}] {msg}")
        checks.append({"check": f"cost_hierarchy_{lower}_le_{upper}",
                        "pass": ok, "detail": msg,
                        "pct_diff": round(pct_diff, 3)})

    # ── 3. Heat-loss check ─────────────────────────────────────────────────────
    for rid in ["L1", "L2", "L3", "L3plus", "L3NL"]:
        if rid not in disp:
            continue
        loss_mwh = disp[rid].get("Q_loss_total_MWh", 0.0)
        if rid == "L1":
            ok = loss_mwh < 1.0  # copperplate: must have no losses
            status = "PASS" if ok else "FAIL"
            msg = f"L1 heat losses = {loss_mwh:.1f} MWh (must be ~0)"
        else:
            ok = loss_mwh > 0.0
            status = "PASS" if ok else "WARN"
            msg = f"{rid} heat losses = {loss_mwh:,.0f} MWh (must be >0)"
        print(f"  [{status}] {msg}")
        checks.append({"check": f"heat_loss_{rid}", "pass": ok, "detail": msg,
                        "loss_MWh": round(loss_mwh, 1)})

    # ── 4. Pressure-drop effect: L3plus pump energy ≥ L3 ─────────────────────
    pump_key = "P_buy_total_MWh"  # proxy: L3plus buys more electricity for pumps
    # More direct: compare cost_pump_eur from economics
    pump_l3     = float(eco.get("L3",     {}).get("cost_pump_eur", 0.0))
    pump_l3plus = float(eco.get("L3plus", {}).get("cost_pump_eur", 0.0))
    if pump_l3 > 0 or pump_l3plus > 0:
        ok = pump_l3plus >= pump_l3 * 0.95  # allow 5% tolerance
        status = "PASS" if ok else "WARN"
        msg = (f"Pump cost L3={pump_l3:,.0f} EUR, L3+={pump_l3plus:,.0f} EUR "
               f"(L3+ should be ≥ L3 since pressure-drop is active)")
        print(f"  [{status}] {msg}")
        checks.append({"check": "pump_cost_L3plus_ge_L3", "pass": ok, "detail": msg,
                        "pump_L3_eur": round(pump_l3, 0),
                        "pump_L3plus_eur": round(pump_l3plus, 0)})

    # ── 5. Linearization error: L3NL vs L3 ────────────────────────────────────
    lin_err: dict | None = None
    if "L3NL" in costs and "L3" in costs:
        c_nl = costs["L3NL"]
        c_l3 = costs["L3"]
        # Linearization error = (L3_cost - L3NL_cost) / L3NL_cost
        # L3NL is nonlinear (exact), L3 is MILP (linearized).
        # L3 can be cheaper (relaxation) or more expensive (over-conservatism from
        # PWL approximation), so report signed error.
        err_pct = (c_l3 - c_nl) / max(abs(c_nl), 1.0) * 100
        abs_err = abs(c_l3 - c_nl)
        lin_err = {
            "L3NL_cost_eur": round(c_nl, 0),
            "L3_cost_eur": round(c_l3, 0),
            "abs_diff_eur": round(abs_err, 0),
            "signed_error_pct": round(err_pct, 3),
            "abs_error_pct": round(abs(err_pct), 3),
            "note": ("L3 (MILP) vs L3NL (NLP). Positive = MILP over-estimates cost "
                     "vs exact nonlinear solution."),
        }
        print(f"\n  ┌─ Linearization error (paper core KPI) ──────────────────────────┐")
        print(f"  │  L3  (MILP) : {c_l3:>15,.0f} EUR")
        print(f"  │  L3NL (NLP) : {c_nl:>15,.0f} EUR")
        print(f"  │  Δ (signed) : {err_pct:>+14.3f} %")
        print(f"  │  Δ (abs)    : {abs_err:>15,.0f} EUR")
        print(f"  └──────────────────────────────────────────────────────────────────┘")
        checks.append({"check": "linearization_error_L3_vs_L3NL",
                        "pass": True,  # informational — no pass/fail threshold
                        "detail": f"MILP linearization error = {err_pct:+.3f}%",
                        **lin_err})
    else:
        missing = [r for r in ("L3", "L3NL") if r not in costs]
        print(f"  [SKIP] Linearization error: missing {missing}")

    # ── 6. Energy-balance closure from per-run validation.json ────────────────
    print("\n  ┌─ Energy-balance closure per run ────────────────────────────────────┐")
    for rid in run_ids:
        vpath = OUT_BASE / rid / "validation.json"
        if not vpath.exists():
            continue
        try:
            vdata = json.loads(vpath.read_text())
            eb = vdata.get("energy_balance", {})
            err = eb.get("closure_error_pct")
            passed = eb.get("closure_pass")
            if err is not None:
                status = "PASS" if passed else "WARN"
                print(f"  │  [{status}] {rid:<8}  closure error = {err:.3f}%")
                checks.append({"check": f"energy_balance_closure_{rid}",
                                "pass": bool(passed),
                                "closure_error_pct": err})
        except Exception:
            pass
    print("  └──────────────────────────────────────────────────────────────────┘")

    # ── 7. Persist results ─────────────────────────────────────────────────────
    n_fail = sum(1 for c in checks if not c.get("pass", True))
    n_pass = sum(1 for c in checks if c.get("pass", True))

    result_payload = {
        "checks": checks,
        "summary": {
            "n_checks": len(checks),
            "n_pass": n_pass,
            "n_fail": n_fail,
            "available_runs": available,
        },
        "costs_eur": costs,
        "linearization_error": lin_err,
    }

    out_path = OUT_BASE / "level_consistency.json"
    out_path.write_text(json.dumps(result_payload, indent=2, default=str), encoding="utf-8")
    print(f"\n  [OK] level_consistency.json written ({n_pass} pass, {n_fail} fail/warn)")

    status_str = "ok" if n_fail == 0 else "warn"
    _record(log, {"phase": "1b", "status": status_str,
                  "n_checks": len(checks), "n_fail": n_fail,
                  "linearization_error_pct": lin_err.get("abs_error_pct") if lin_err else None})


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2 — Validation Stage 2: Asset plausibility (AFTER optimization)
# ──────────────────────────────────────────────────────────────────────────────

def phase2_validation_stage2(dry_run: bool, log: list) -> None:
    """
    Stage 2 only: Asset-level plausibility checks for HP, electrode boiler,
    and thermal storage from L3 dispatch results.

    Requires Phase 1 to have completed successfully (needs dispatch_hourly.csv).

    Outputs → output/validation/
      stage2_COP_scatter.png
      stage2_eboiler_price.png
      stage2_TES_SOC.png
      stage2_energy_stacked_bar.png
      validation_summary_table.png
      validation_report.md
      kpis.json (updated with stage2 results)
    """
    print("\n" + "="*70)
    print("PHASE 2 — Validation Stage 2: Asset plausibility (post-optimization)")
    print("="*70)
    print("  Purpose: Check optimization results for physical plausibility.")
    print("           Requires Phase 1 dispatch results.")

    # Check that Phase 1 results exist
    l3_dispatch = OUT_BASE / "L3" / "dispatch_hourly.csv"
    if not l3_dispatch.exists() and not dry_run:
        # Also check L3plus as fallback
        l3plus_dispatch = OUT_BASE / "L3plus" / "dispatch_hourly.csv"
        if not l3plus_dispatch.exists():
            print(f"  [ERROR] No dispatch results found:")
            print(f"          - {l3_dispatch}")
            print(f"          - {l3plus_dispatch}")
            print("          Run Phase 1 first: --phases 1")
            _record(log, {"phase": 2, "status": "missing_input"})
            return

    val_script = ROOT / "tools" / "validation_runner.py"
    if not val_script.exists():
        print(f"  [WARN] {val_script} not found")
        _record(log, {"phase": 2, "status": "missing_script"})
        return

    # Stage 2 does not need to re-load historical Excel data (saves ~300s)
    cmd = [sys.executable, str(val_script), "--stage", "2", "--skip-model"]
    if dry_run:
        cmd.append("--dry-run")

    print(f"  [CMD] {' '.join(cmd)}")
    if dry_run:
        print("  [DRY] Would run Stage 2 validation (HP COP, TES SOC, EBoiler price-response)")
        return

    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=ROOT, capture_output=False, text=True)
    elapsed = time.perf_counter() - t0

    status = "ok" if result.returncode == 0 else "warn_threshold"
    print(f"\n  [PHASE 2] done in {_elapsed_str(elapsed)} — status={status}")
    _record(log, {"phase": 2, "status": status, "solve_s": round(elapsed, 1)})

    # Print Stage 2 summary
    kpi_path = ROOT / "output" / "validation" / "kpis.json"
    if kpi_path.exists():
        try:
            kpis = json.loads(kpi_path.read_text())
            s2 = kpis.get("stage2", {})
            if s2:
                print("\n  ┌─ Stage 2 Summary (Asset Plausibility) ───────────────────┐")
                for k, v in s2.items():
                    if v is not None:
                        if isinstance(v, float):
                            print(f"  │  {k}: {v:.3f}")
                        else:
                            print(f"  │  {k}: {v}")
                print("  └──────────────────────────────────────────────────────────────┘")
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# Phase 3 — Sensitivity runs
# ──────────────────────────────────────────────────────────────────────────────

def phase3_sensitivity(gurobi: bool, skip_nl: bool, dry_run: bool, log: list) -> None:
    """Run 8 scenarios × 4 levels = 32 sensitivity runs."""
    print("\n" + "="*70)
    print("PHASE 3 — Sensitivity runs (§4)")
    print("="*70)

    sens_base = OUT_BASE / "sensitivity"
    sens_base.mkdir(parents=True, exist_ok=True)

    combos = [(lvl, sc) for lvl in SENSITIVITY_LEVELS for sc in SENSITIVITY_SCENARIOS]
    print(f"  {len(combos)} runs total "
          f"({len(SENSITIVITY_LEVELS)} levels × {len(SENSITIVITY_SCENARIOS)} scenarios)")

    done = 0
    for level, scenario in combos:
        run_id  = f"{level}_{scenario}"
        primary = LEVEL_TO_PRIMARY[level]
        config  = primary["config"]

        if not config.exists():
            _record(log, {"phase": 3, "run_id": run_id, "status": "missing_config"})
            continue

        physics_override = SYNTH_PHYSICS.get(level, {})
        scenario_delta   = copy.deepcopy(SENSITIVITY_SCENARIOS[scenario])
        # Keep _demand_scale (handled in _run_workflow_with_overrides); strip other _ keys
        clean_delta      = {k: v for k, v in scenario_delta.items()
                            if not k.startswith("_") or k == "_demand_scale"}
        overrides        = _deep_merge(physics_override, clean_delta) if clean_delta else copy.deepcopy(physics_override)

        outdir = sens_base / run_id
        outdir.mkdir(parents=True, exist_ok=True)

        # Skip if already completed
        if (outdir / "economics.csv").exists() and not dry_run:
            done += 1
            continue

        if dry_run:
            print(f"  [DRY] {run_id}")
            done += 1
            continue

        print(f"  [RUN] {run_id}")
        t0 = time.perf_counter()
        try:
            wf = _run_workflow_with_overrides(config, overrides or None)
            elapsed = time.perf_counter() - t0
            _extract(run_id, config, wf, elapsed, outdir=outdir)
            done += 1
            print(f"        done in {_elapsed_str(elapsed)} ({done}/{len(combos)})")
            _record(log, {"phase": 3, "run_id": run_id, "status": "ok",
                          "solve_s": round(elapsed, 1)})
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            done += 1
            print(f"        ERROR: {exc}")
            _record(log, {"phase": 3, "run_id": run_id, "status": "error",
                          "error": str(exc)})

    # Roll-up summary CSV
    if not dry_run:
        _write_sensitivity_summary(sens_base)


def _write_sensitivity_summary(sens_base: Path) -> None:
    """Collect all economics.csv from sensitivity runs into one summary.csv."""
    try:
        import pandas as pd
        rows = []
        for sub in sorted(sens_base.iterdir()):
            if not sub.is_dir():
                continue
            econ = sub / "economics.csv"
            if econ.exists():
                df = pd.read_csv(econ)
                if not df.empty:
                    row = df.iloc[0].to_dict()
                    # Parse level_scenario from folder name
                    # e.g. "L3plus_gas_high" → level="L3plus", scenario="gas_high"
                    name = sub.name
                    for lvl in SENSITIVITY_LEVELS:
                        if name.startswith(lvl + "_"):
                            row["level"]    = lvl
                            row["scenario"] = name[len(lvl) + 1:]
                            break
                    else:
                        row["level"]    = name
                        row["scenario"] = "unknown"
                    rows.append(row)
        if rows:
            pd.DataFrame(rows).to_csv(sens_base / "summary.csv", index=False)
            print(f"\n  [SUMMARY] sensitivity/summary.csv ({len(rows)} rows)")
    except Exception as e:
        print(f"\n  [WARN] sensitivity summary failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4 — Synthetic runs
# ──────────────────────────────────────────────────────────────────────────────

def phase4_synthetic(gurobi: bool, skip_nl: bool, dry_run: bool, log: list) -> None:
    """Run synthetic parametric study: N configs × 5 levels."""
    print("\n" + "="*70)
    print("PHASE 4 — Synthetic runs (§5)")
    print("="*70)

    if not SYNTH_DIR.exists():
        print(f"  [WARN] Synth config directory not found: {SYNTH_DIR}")
        print("         Run: python tools/gen_synth.py --seed 42")
        _record(log, {"phase": 4, "status": "missing_configs"})
        return

    synth_yamls = sorted(SYNTH_DIR.glob("synth_*.yaml"))
    if not synth_yamls:
        print("  [WARN] No synth_*.yaml configs found.")
        print("         Run: python tools/gen_synth.py --seed 42")
        _record(log, {"phase": 4, "status": "missing_configs"})
        return

    synth_out = OUT_BASE / "synth"
    synth_out.mkdir(parents=True, exist_ok=True)

    levels = list(SYNTH_PHYSICS.keys())
    total  = len(synth_yamls) * len(levels)
    print(f"  {len(synth_yamls)} configs × {len(levels)} levels = {total} runs")

    done = 0
    for yaml_path in synth_yamls:
        synth_id = yaml_path.stem

        for level, physics_override in SYNTH_PHYSICS.items():
            run_id = f"{synth_id}_{level}"

            if (level == "L3NL" and not gurobi) or (skip_nl and level == "L3NL"):
                _record(log, {"phase": 4, "run_id": run_id, "status": "skipped"})
                done += 1
                continue

            outdir = synth_out / run_id
            if outdir.exists() and (outdir / "meta.json").exists():
                done += 1
                continue  # already completed

            if dry_run:
                done += 1
                continue

            outdir.mkdir(parents=True, exist_ok=True)
            t0 = time.perf_counter()
            try:
                wf = _run_workflow_with_overrides(yaml_path, physics_override)
                elapsed = time.perf_counter() - t0
                _extract(run_id, yaml_path, wf, elapsed, outdir=outdir)
                done += 1
                if done % 10 == 0 or done == total:
                    print(f"  [OK] {done}/{total} ({run_id}, {_elapsed_str(elapsed)})")
                _record(log, {"phase": 4, "run_id": run_id, "status": "ok",
                              "solve_s": round(elapsed, 1)})
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                done += 1
                print(f"  [ERR] {run_id}  {_elapsed_str(elapsed)}  {exc}")
                _record(log, {"phase": 4, "run_id": run_id, "status": "error",
                              "error": str(exc)})

    if dry_run:
        print(f"  [DRY] Would run {total} synthetic configurations")


# ──────────────────────────────────────────────────────────────────────────────
# Phase 5 — Tables
# ──────────────────────────────────────────────────────────────────────────────

def phase5_tables(dry_run: bool, log: list) -> None:
    """Generate LaTeX tables from results."""
    print("\n" + "="*70)
    print("PHASE 5 — Generate LaTeX tables (§7)")
    print("="*70)

    table_script = ROOT / "tools" / "tablegen.py"
    if not table_script.exists():
        print(f"  [WARN] {table_script} not found")
        _record(log, {"phase": 5, "status": "missing_script"})
        return

    if dry_run:
        print(f"  [DRY] python {table_script.name}")
        return

    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(table_script)],
        cwd=ROOT, capture_output=True, text=True
    )
    elapsed = time.perf_counter() - t0

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"  [WARN] tablegen exited {result.returncode}: {result.stderr[:500]}")
        _record(log, {"phase": 5, "status": "error",
                      "stderr": result.stderr[:500], "solve_s": round(elapsed, 1)})
    else:
        print(f"  [OK] Tables generated in {_elapsed_str(elapsed)}")
        _record(log, {"phase": 5, "status": "ok", "solve_s": round(elapsed, 1)})


# ──────────────────────────────────────────────────────────────────────────────
# Phase 6 — Figure generation
# ──────────────────────────────────────────────────────────────────────────────

def phase6_figures(dry_run: bool, log: list,
                   figs: list[str] | None = None) -> None:
    """
    Generate all publication figures via tools/figgen.py.

      F1   Experimental design matrix
      F2   Network topology schematic
      F3   Annual cost stacked bars
      F4   Dispatch time series (winter week)
      F5   Cost waterfall: L3 → L3⁺ → L3ᴺᴸ
      F6   Pumping scatter: L3⁺ vs L3ᴺᴸ
      FV1  Validation time series
      F7   TES SOC comparison
      F8   Generalizability heatmap (requires Phase 4)
      F9   Node averages (annual + seasonal)
      F10  Node topology heatmap (annual + seasonal spread)
      F11  Critical-path profile (temperature + pressure)
      F12  Extended duration curves (L1/L2/L3/L3plus/L3NL)
      F13  Annual energy Sankey
    """
    print("\n" + "="*70)
    print("PHASE 6 — Figure generation (§8)")
    print("="*70)

    fig_script = ROOT / "tools" / "figgen.py"
    if not fig_script.exists():
        print(f"  [WARN] {fig_script} not found")
        _record(log, {"phase": 6, "status": "missing_script"})
        return

    cmd = [sys.executable, str(fig_script)]
    if figs:
        cmd += ["--fig"] + figs

    print(f"  [CMD] {' '.join(cmd)}")
    if dry_run:
        target_str = ", ".join(figs) if figs else "F1 F2 F3 F4 F5 F6 FV1 F7 F8 F9 F10 F11 F12 F13"
        print(f"  [DRY] Would generate: {target_str}")
        return

    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.perf_counter() - t0

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"  [WARN] figgen exited {result.returncode}: {result.stderr[:500]}")
        _record(log, {"phase": 6, "status": "error",
                      "stderr": result.stderr[:500], "solve_s": round(elapsed, 1)})
    else:
        fig_dir = OUT_BASE / "figures"
        fig_lines = []
        if result.stdout:
            fig_lines = [ln.strip() for ln in result.stdout.splitlines() if "[FIG]" in ln]

        n_figs = len(fig_lines)
        n_files = 0
        for ln in fig_lines:
            match = re.search(r"\(([^)]*)\)\s*$", ln)
            if not match:
                continue
            suffixes = [s.strip() for s in match.group(1).split(",") if s.strip()]
            n_files += len(suffixes)

        # Fallback: when figgen output cannot be parsed, count current directory content.
        if n_figs == 0 and fig_dir.exists():
            stems: set[str] = set()
            for ext in ("*.png", "*.pdf", "*.pgf"):
                files = list(fig_dir.glob(ext))
                n_files += len(files)
                stems.update(f.stem for f in files)
            n_figs = len(stems)

        print(f"  [OK] {n_figs} figure stems / {n_files} files in {fig_dir} ({_elapsed_str(elapsed)})")
        _record(log, {"phase": 6, "status": "ok",
                      "n_figures": n_figs, "n_files": n_files, "solve_s": round(elapsed, 1)})


# ──────────────────────────────────────────────────────────────────────────────
# Phase 7 — Fill paper placeholders
# ──────────────────────────────────────────────────────────────────────────────

def phase7_fill_paper(dry_run: bool, log: list) -> None:
    """Auto-fill LaTeX placeholders with computed results."""
    print("\n" + "="*70)
    print("PHASE 7 — Fill paper placeholders (§9)")
    print("="*70)

    fill_py = ROOT / "tools" / "fill_paper.py"
    if not fill_py.exists():
        print(f"  [WARN] {fill_py} not found")
        _record(log, {"phase": 7, "status": "missing_script"})
        return

    if dry_run:
        print(f"  [DRY] python {fill_py.name} --auto")
        return

    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(fill_py), "--auto"],
        cwd=ROOT, capture_output=True, text=True
    )
    elapsed = time.perf_counter() - t0

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"  [WARN] fill_paper exited {result.returncode}: {result.stderr[:500]}")
        _record(log, {"phase": 7, "status": "error",
                      "stderr": result.stderr[:500], "solve_s": round(elapsed, 1)})
    else:
        print(f"  [OK] Paper filled in {_elapsed_str(elapsed)}")
        _record(log, {"phase": 7, "status": "ok", "solve_s": round(elapsed, 1)})


# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Full paper orchestrator — runs all phases in order.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--phases", nargs="+", type=int, choices=[0, 1, 2, 3, 4, 5, 6, 7],
        default=[0, 1, 2, 3, 4, 5, 6, 7],
        metavar="N",
        help=(
            "Phases to run (default: all). "
            "0=val-stage1(pre)  1=primary(+1b auto)  2=val-stage2(post)  "
            "3=sensitivity  4=synth  5=tables  6=figures  7=fill"
        ),
    )
    parser.add_argument("--skip-nl", action="store_true",
                        help="Skip all L3NL (Gurobi NonConvex) runs unconditionally")
    parser.add_argument("--nlp-short", action="store_true",
                        help="Replace full-year L3NL with 1-week representative window (recommended: full-year NLP is intractable)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan only — do not run any solver")
    parser.add_argument("--fail-on-skip", action="store_true",
                        help="Exit non-zero if any run is skipped due to missing Gurobi")
    parser.add_argument("--skip-model", action="store_true",
                        help="(Phase 0) Skip re-running the legacy model; reuse existing output")
    parser.add_argument("--skip-consistency", action="store_true",
                        help="Skip Phase 1b cross-level consistency check after primary runs")
    parser.add_argument("--miqp-val-seasons", type=str, default=None,
                        dest="miqp_val_seasons",
                        help="(Phase 0) MIQP seasonal validation seasons, e.g. 'winter' or 'winter,summer'")
    parser.add_argument("--figs", nargs="*",
                        metavar="FIG",
                        help="(Phase 6) Specific figure IDs, e.g. --figs F2 FV1 F5 F10 F13")
    args = parser.parse_args(argv)

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    log: list[dict] = []

    # ── Environment check ──
    gurobi = _gurobi_ok()
    print("\n" + "="*70)
    print("PAPER RUN ORCHESTRATOR")
    print("="*70)
    print(f"  Gurobi:     {'✓ available' if gurobi else '✗ not found (L3NL will be skipped)'}")
    print(f"  Phases:     {sorted(args.phases)}")
    print(f"  Skip NL:    {args.skip_nl}")
    print(f"  NLP short:  {getattr(args, 'nlp_short', False)} (representative week instead of full-year)")
    print(f"  Dry run:    {args.dry_run}")
    print(f"  MIQP val:   {args.miqp_val_seasons or '(none — temperature KPIs skipped in Phase 0)'}")
    print(f"  Output:     {OUT_BASE}")

    if args.dry_run:
        print("\n  [DRY RUN MODE] No solver calls will be made.\n")

    # ── Phase execution order ──
    # The order is important:
    #   0:  Validate network (quality gate) → BEFORE optimization
    #   1:  Run optimization (L1, L2, L3, L3+, L3NL)
    #   1b: Cross-level consistency check → auto-injected after Phase 1
    #   2:  Validate assets (plausibility) → AFTER optimization
    #   3-7: Post-processing

    t_total = time.perf_counter()

    def _run_phase1_with_consistency():
        phase1_primary(gurobi, args.skip_nl, args.dry_run, log,
                       nlp_short=getattr(args, "nlp_short", False))
        if not getattr(args, "skip_consistency", False):
            phase1b_level_consistency(args.dry_run, log)

    phase_map = {
        0: lambda: phase0_validation_stage1(args.skip_model, args.dry_run, log,
                                            miqp_seasons=args.miqp_val_seasons),
        1: _run_phase1_with_consistency,
        2: lambda: phase2_validation_stage2(args.dry_run, log),
        3: lambda: phase3_sensitivity(gurobi, args.skip_nl, args.dry_run, log),
        4: lambda: phase4_synthetic(gurobi, args.skip_nl, args.dry_run, log),
        5: lambda: phase5_tables(args.dry_run, log),
        6: lambda: phase6_figures(args.dry_run, log, figs=args.figs),
        7: lambda: phase7_fill_paper(args.dry_run, log),
    }

    for p in sorted(args.phases):
        phase_map[p]()

    # ── Final summary ──
    elapsed = time.perf_counter() - t_total
    skipped = sum(1 for e in log if e.get("status") == "skipped")
    errors  = sum(1 for e in log if e.get("status") == "error")
    ok      = sum(1 for e in log if e.get("status") == "ok")
    warns   = sum(1 for e in log if e.get("status") in ("warn_threshold", "warn"))

    print(f"\n{'='*70}")
    print(f"DONE  total={_elapsed_str(elapsed)}  ok={ok}  warns={warns}  "
          f"errors={errors}  skipped={skipped}")
    print(f"  log → {OUT_BASE / 'run_log.json'}")

    # Show linearization error if Phase 1b ran
    consist_path = OUT_BASE / "level_consistency.json"
    if consist_path.exists():
        try:
            consist = json.loads(consist_path.read_text())
            lin = consist.get("linearization_error")
            if lin:
                print(f"  Linearization error (L3 vs L3NL): {lin.get('signed_error_pct'):+.3f}%  "
                      f"(abs: {lin.get('abs_diff_eur'):,.0f} EUR)")
            n_fail = consist.get("summary", {}).get("n_fail", 0)
            if n_fail:
                print(f"  ⚠️  {n_fail} consistency check(s) failed — review level_consistency.json")
        except Exception:
            pass

    print(f"{'='*70}")

    if errors:
        print(f"\n  ⚠️  {errors} run(s) FAILED — check run_log.json for details.")
    if warns:
        print(f"  ℹ️  {warns} validation warning(s) — thresholds exceeded.")

    if args.fail_on_skip and skipped:
        print(f"\n  [EXIT 1] {skipped} run(s) skipped (--fail-on-skip set).")
        return 1

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
