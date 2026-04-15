"""Quick diagnostic: verify scenario.horizon parsing and table slicing."""
import sys
sys.path.insert(0, ".")

from calion.utils import simple_yaml
from calion.config.merge import load_and_merge
from calion.run.utilities.timeseries_utils import _apply_horizon

CONFIG = "configs/memmingen/Memmingen_L3.yaml"

# 1. Raw YAML parse
raw = simple_yaml.load(CONFIG)
scenario = raw.get("scenario", {})
horizon = scenario.get("horizon")
print(f"[RAW YAML] scenario.horizon = {horizon!r}  (type: {type(horizon).__name__})")

# 2. After load_and_merge (schema + normalisation)
cfg = load_and_merge([CONFIG])
scenario_cfg = cfg.get("scenario", {})
horizon2 = scenario_cfg.get("horizon")
print(f"[MERGED CFG] scenario.horizon = {horizon2!r}  (type: {type(horizon2).__name__})")

# 3. Check _apply_horizon branch
if isinstance(horizon2, dict):
    print("[OK] horizon is dict → _apply_horizon will filter")
else:
    print("[FAIL] horizon is NOT dict → _apply_horizon returns full table!")

# 4. Load the table and check T
from calion.io.loader import load_input_excel
site_cfg = cfg.get("site", {})
run_cfg = cfg.get("run", {})
dt_h = float(run_cfg.get("dt_h", 1.0))
print(f"\ndt_h = {dt_h}")

table = load_input_excel(site_cfg.get("input_xlsx", "Import_Data.xlsx"), site_cfg, dt_hours=dt_h)
print(f"[BEFORE horizon] T = {len(table)}  ({table.index[0]} → {table.index[-1]})")

table2 = _apply_horizon(table, scenario_cfg, dt_h)
print(f"[AFTER  horizon] T = {len(table2)}  ({table2.index[0]} → {table2.index[-1]})")
