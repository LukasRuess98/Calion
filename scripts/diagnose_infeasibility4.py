"""Check which constraints remain after the fix."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers.highs import Highs
from scripts.run_network_scenarios_programmatic import build_star
from energis.models.system_builder import build_model

net = build_star()
cfg = net._build_config()
table = net._build_table()
model = build_model(table, cfg, net.dt_h)

# List all constraints related to consumers
print("=== Consumer-related constraints ===")
for c in model.component_objects(pyo.Constraint, active=True):
    name = c.name
    if any(kw in name.lower() for kw in ['north', 'south', 'east', 'demand', 'mass_balance', 'heat_demand']):
        n = sum(1 for _ in c)
        print(f"  {name}: {n} constraints")

# Check if delay binaries are still the issue
opt = Highs()
opt.config.load_solution = False

# Test: relax delay
delay_relaxed = []
for v in model.component_objects(pyo.Var, active=True):
    if 'z_delay' in v.name.lower():
        for idx in v:
            if v[idx].domain == pyo.Binary:
                delay_relaxed.append((v, idx))
                v[idx].domain = pyo.NonNegativeReals
                v[idx].setub(1.0)

r = opt.solve(model)
print(f"\nDelay relaxed: {r.termination_condition}")

# Restore
for v, idx in delay_relaxed:
    v[idx].domain = pyo.Binary
    v[idx].setub(None)

# Test: deactivate passthrough constraints from _link_consumer_demands
print("\n=== Test: disable demand linkage constraints ===")
deactivated = []
for c in model.component_objects(pyo.Constraint, active=True):
    if 'link_heat_demand' in c.name or 'link_demand' in c.name:
        c.deactivate()
        deactivated.append(c.name)
        print(f"  Deactivated: {c.name}")

r = opt.solve(model)
print(f"Without demand linkage: {r.termination_condition}")

# Restore
for c in model.component_objects(pyo.Constraint, active=False):
    if c.name in deactivated:
        c.activate()

# Check what constraints link m_dot to demand
print("\n=== All active constraints on NORTH node ===")
for c in model.component_objects(pyo.Constraint, active=True):
    name = c.name
    if 'NORTH' in name or 'north' in name:
        n = sum(1 for _ in c)
        # Print one example constraint body
        for idx in c:
            body = str(c[idx].expr)
            if len(body) > 200:
                body = body[:200] + "..."
            print(f"  {name}[{idx}]: {body}")
            break
