"""Run only the L3NL (fix-and-relax NLP) and update level_consistency.json."""
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.paper.run_paper_full import (
    CONFIGS, OUT_BASE,
    _run_workflow_with_overrides, _extract,
    phase1b_level_consistency,
)

NLP_CONFIG = CONFIGS / "Memmingen_L3_NLP.yaml"
OUT_L3NL   = OUT_BASE / "L3NL"
OUT_L3NL.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("L3NL Fix-and-Relax NLP run")
print(f"  Config : {NLP_CONFIG}")
print(f"  Output : {OUT_L3NL}")
print("=" * 60)

t0 = time.perf_counter()
try:
    wf = _run_workflow_with_overrides(NLP_CONFIG, None)
    elapsed = time.perf_counter() - t0
    print(f"\n  [OK] Solved in {elapsed:.1f}s")
except Exception as exc:
    elapsed = time.perf_counter() - t0
    print(f"\n  [ERROR] after {elapsed:.1f}s: {exc}")
    import traceback; traceback.print_exc()
    sys.exit(1)

print("\nExtracting artefacts...")
try:
    outdir = _extract("L3NL", NLP_CONFIG, wf, elapsed, outdir=OUT_L3NL)
    print(f"  [OK] artefacts → {outdir}")
except Exception as exc:
    print(f"  [WARN] extract failed: {exc}")
    import traceback; traceback.print_exc()

print("\nUpdating level_consistency.json...")
log = []
phase1b_level_consistency(dry_run=False, log=log)
print("Done.")
