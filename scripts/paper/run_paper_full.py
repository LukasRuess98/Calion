"""
Full paper run orchestrator — executes all phases in order.

Phases:
  0. Validation Stage 1 (§4.2): legacy model + network validation (quality gate)
  1. Primary runs       (§2):   L1, L2, L3, L3+, L3NL
  2. Validation Stage 2 (§4.2): asset plausibility checks (needs Phase 1 results)
  3. Sensitivity runs   (§4):   8 scenarios x L1/L2/L3/L3+
  4. Synthetic runs     (§5):   36 configs x 5 levels = 180 runs
  5. Tables             (§7):   tools/tablegen.py
  6. Figures            (§8):   tools/figgen.py
  7. Fill paper         (§9):   tools/fill_paper.py --auto

Pipeline logic:
  Phase 0 (Stage 1) is a QUALITY GATE: validates the network model against
  historical measurements BEFORE running any optimization. If T_supply MAE
  exceeds thresholds, the user is warned to recalibrate.

  Phase 2 (Stage 2) runs AFTER optimization (Phase 1) because it checks
  asset dispatch plausibility (COP, SOC, eboiler) from dispatch_hourly.csv.

Usage:
    python scripts/paper/run_paper_full.py                   # all phases
    python scripts/paper/run_paper_full.py --phases 0        # validation Stage 1 only
    python scripts/paper/run_paper_full.py --phases 1 2      # primary + asset validation
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
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT_BASE   = ROOT / "output" / "paper_runs"
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
        "config": CONFIGS / "Memmingen_L3_MIQP.yaml",
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
    "elec_low":   {"grid": {"gridcost_eur_mwh": 15.0}},       # günstiger HP-Strom
    "elec_high":  {"grid": {"gridcost_eur_mwh": 45.0}},       # teurer Strom
    "co2_high":   {"costs": {"co2_price_eur_per_t": 200.0}},   # jetzt wirklich höher
    "co2_low":    {"costs": {"co2_price_eur_per_t": 50.0}},    # niedriger
    "cold":       {"_demand_scale": 1.15},                      # +15% statt +5%
    "warm":       {"_demand_scale": 0.85},                      # -15% statt -5%
    "cop_low":    {"heat_pumps": {"cop": {"types": {"standard": {"eta": 0.45}}}}},
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


def _run_workflow_with_overrides(config_path: Path, overrides: dict | None):
    """Load config, apply overrides, run workflow, return workflow object."""
    from calion.run.workflow import run_workflow
    if not overrides:
        return run_workflow([str(config_path)])
    cfg = _load_yaml(config_path)
    cfg = _deep_merge(cfg, overrides)
    tmp = config_path.parent / f"_tmp_{config_path.stem}.yaml"
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

def phase0_validation_stage1(skip_model: bool, dry_run: bool, log: list) -> None:
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

def phase1_primary(gurobi: bool, skip_nl: bool, dry_run: bool, log: list) -> None:
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

        if (needs_g and not gurobi) or (skip_nl and run_id == "L3NL"):
            print(f"\n[SKIP] {run_id} — {'no Gurobi' if needs_g else 'skip-nl flag'}")
            _record(log, {"phase": 1, "run_id": run_id, "status": "skipped"})
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
        scenario_delta   = SENSITIVITY_SCENARIOS[scenario]
        clean_delta      = {k: v for k, v in scenario_delta.items() if not k.startswith("_")}
        overrides        = _deep_merge(physics_override, clean_delta) if clean_delta else physics_override

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
        target_str = ", ".join(figs) if figs else "F1 F2 F3 F4 F5 F6 FV1 F7 F8"
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
        n_figs  = len(list(fig_dir.glob("*.png"))) if fig_dir.exists() else 0
        print(f"  [OK] {n_figs} figures in {fig_dir} ({_elapsed_str(elapsed)})")
        _record(log, {"phase": 6, "status": "ok",
                      "n_figures": n_figs, "solve_s": round(elapsed, 1)})


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
            "0=val-stage1(pre)  1=primary  2=val-stage2(post)  "
            "3=sensitivity  4=synth  5=tables  6=figures  7=fill"
        ),
    )
    parser.add_argument("--skip-nl", action="store_true",
                        help="Skip all L3NL (Gurobi NonConvex) runs unconditionally")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan only — do not run any solver")
    parser.add_argument("--fail-on-skip", action="store_true",
                        help="Exit non-zero if any run is skipped due to missing Gurobi")
    parser.add_argument("--skip-model", action="store_true",
                        help="(Phase 0) Skip re-running the legacy model; reuse existing output")
    parser.add_argument("--figs", nargs="*",
                        metavar="FIG",
                        help="(Phase 6) Specific figure IDs, e.g. --figs F2 FV1 F5")
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
    print(f"  Dry run:    {args.dry_run}")
    print(f"  Output:     {OUT_BASE}")

    if args.dry_run:
        print("\n  [DRY RUN MODE] No solver calls will be made.\n")

    # ── Phase execution order ──
    # The order is important:
    #   0: Validate network (quality gate) → BEFORE optimization
    #   1: Run optimization (L1, L2, L3, L3+, L3NL)
    #   2: Validate assets (plausibility) → AFTER optimization
    #   3-7: Post-processing

    t_total = time.perf_counter()

    phase_map = {
        0: lambda: phase0_validation_stage1(args.skip_model, args.dry_run, log),
        1: lambda: phase1_primary(gurobi, args.skip_nl, args.dry_run, log),
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
    warns   = sum(1 for e in log if e.get("status") == "warn_threshold")

    print(f"\n{'='*70}")
    print(f"DONE  total={_elapsed_str(elapsed)}  ok={ok}  warns={warns}  "
          f"errors={errors}  skipped={skipped}")
    print(f"  log → {OUT_BASE / 'run_log.json'}")
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