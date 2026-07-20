"""One-shot re-run of BC-SB with corrected 32-node topology."""
import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from scripts.paper_2.scenario_runner import load_scenarios_config, run_single_scenario

scen_cfg = load_scenarios_config()
scen = next(s for s in scen_cfg["scenarios"] if s["id"] == "BC-SB")
res = run_single_scenario(scen, scen_cfg, force_rerun=True)
print("\n=== RESULT ===")
print(res)
