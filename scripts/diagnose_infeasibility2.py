"""Diagnose which binary group causes infeasibility."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers.highs import Highs
from scripts.run_network_scenarios_programmatic import build_star
from calion.models.system_builder import build_model

net = build_star()
cfg = net._build_config()
table = net._build_table()
model = build_model(table, cfg, net.dt_h)

opt = Highs()
opt.config.load_solution = False

# Full MIP
r = opt.solve(model)
print(f"Full MIP: {r.termination_condition}")

# Relax only PWL binaries (keep delay binaries integer)
print("\n=== Relax only PWL binaries ===")
pwl_relaxed = []
for v in model.component_objects(pyo.Var, active=True):
    if 'pwl_segment' in v.name.lower():
        for idx in v:
            if v[idx].domain == pyo.Binary:
                pwl_relaxed.append((v, idx))
                v[idx].domain = pyo.NonNegativeReals
                v[idx].setub(1.0)

print(f"Relaxed {len(pwl_relaxed)} PWL segment binaries")
r = opt.solve(model)
print(f"MIP (PWL relaxed): {r.termination_condition}")

# Restore PWL
for v, idx in pwl_relaxed:
    v[idx].domain = pyo.Binary
    v[idx].setub(None)

# Relax only delay binaries (keep PWL binaries integer)
print("\n=== Relax only delay binaries ===")
delay_relaxed = []
for v in model.component_objects(pyo.Var, active=True):
    if 'z_delay' in v.name.lower():
        for idx in v:
            if v[idx].domain == pyo.Binary:
                delay_relaxed.append((v, idx))
                v[idx].domain = pyo.NonNegativeReals
                v[idx].setub(1.0)

print(f"Relaxed {len(delay_relaxed)} delay binaries")
r = opt.solve(model)
print(f"MIP (delay relaxed): {r.termination_condition}")

# Restore delay
for v, idx in delay_relaxed:
    v[idx].domain = pyo.Binary
    v[idx].setub(None)

# Relax both PWL + delay (keep other binaries integer)
print("\n=== Relax PWL + delay binaries ===")
for v, idx in pwl_relaxed:
    v[idx].domain = pyo.NonNegativeReals
    v[idx].setub(1.0)
for v, idx in delay_relaxed:
    v[idx].domain = pyo.NonNegativeReals
    v[idx].setub(1.0)

r = opt.solve(model)
print(f"MIP (PWL+delay relaxed): {r.termination_condition}")

# Restore all
for v, idx in pwl_relaxed:
    v[idx].domain = pyo.Binary
    v[idx].setub(None)
for v, idx in delay_relaxed:
    v[idx].domain = pyo.Binary
    v[idx].setub(None)

# Relax only system binaries (on/off etc)
print("\n=== Relax only system binaries (not PWL/delay) ===")
sys_relaxed = []
for v in model.component_objects(pyo.Var, active=True):
    if 'pwl' in v.name.lower() or 'delay' in v.name.lower():
        continue
    for idx in v:
        if v[idx].domain == pyo.Binary:
            sys_relaxed.append((v, idx))
            v[idx].domain = pyo.NonNegativeReals
            v[idx].setub(1.0)

print(f"Relaxed {len(sys_relaxed)} system binaries")
r = opt.solve(model)
print(f"MIP (system relaxed, PWL+delay integer): {r.termination_condition}")

for v, idx in sys_relaxed:
    v[idx].domain = pyo.Binary
    v[idx].setub(None)
