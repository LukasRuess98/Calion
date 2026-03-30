"""Diagnose ring topology infeasibility."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pyomo.environ as pyo
from pyomo.contrib.appsi.solvers.highs import Highs
from scripts.run_network_scenarios_programmatic import build_ring
from calion.models.system_builder import build_model

net = build_ring()
cfg = net._build_config()
table = net._build_table()
model = build_model(table, cfg, net.dt_h)

opt = Highs()
opt.config.load_solution = False

# Test: relax delay binaries
delay_relaxed = []
for v in model.component_objects(pyo.Var, active=True):
    if 'z_delay' in v.name.lower():
        for idx in v:
            if v[idx].domain == pyo.Binary:
                delay_relaxed.append((v, idx))
                v[idx].domain = pyo.NonNegativeReals
                v[idx].setub(1.0)

r = opt.solve(model)
print(f"Delay relaxed: {r.termination_condition}")

# Restore
for v, idx in delay_relaxed:
    v[idx].domain = pyo.Binary
    v[idx].setub(None)

# Test: deactivate all delay constraints
print("\n=== Deactivate all delay constraints ===")
deactivated = []
for c in model.component_objects(pyo.Constraint, active=True):
    name = c.name.lower()
    if any(kw in name for kw in ['delay', 'sos2', 'w_ub', 'w_lb', 'delayed_delivery']):
        c.deactivate()
        deactivated.append(c.name)

# Also set Q_consumer = Q_delivered directly
print(f"Deactivated {len(deactivated)} delay constraint objects")
r = opt.solve(model)
print(f"Without all delay: {r.termination_condition}")

# Restore
for c in model.component_objects(pyo.Constraint, active=False):
    if c.name in deactivated:
        c.activate()

# Check: deactivate mass_balance for passthrough consumers
print("\n=== Deactivate consumer mass_balance ===")
mb_deactivated = []
for c in model.component_objects(pyo.Constraint, active=True):
    if 'mass_balance' in c.name.lower():
        c.deactivate()
        mb_deactivated.append(c.name)
        n = sum(1 for _ in c)
        print(f"  Deactivated: {c.name} ({n} constraints)")

r = opt.solve(model)
print(f"Without consumer mass_balance: {r.termination_condition}")

# Restore
for c in model.component_objects(pyo.Constraint, active=False):
    if c.name in mb_deactivated:
        c.activate()

# Check: deactivate heat_demand for passthrough consumers
print("\n=== Deactivate consumer heat_demand ===")
hd_deactivated = []
for c in model.component_objects(pyo.Constraint, active=True):
    if 'heat_demand' in c.name.lower():
        c.deactivate()
        hd_deactivated.append(c.name)
        n = sum(1 for _ in c)
        print(f"  Deactivated: {c.name} ({n} constraints)")

r = opt.solve(model)
print(f"Without heat_demand: {r.termination_condition}")

for c in model.component_objects(pyo.Constraint, active=False):
    if c.name in hd_deactivated:
        c.activate()

# Check: deactivate BOTH mass_balance + heat_demand
print("\n=== Deactivate mass_balance + heat_demand ===")
for c in model.component_objects(pyo.Constraint, active=True):
    if 'mass_balance' in c.name.lower() or 'heat_demand' in c.name.lower():
        c.deactivate()

r = opt.solve(model)
print(f"Without mass_balance + heat_demand: {r.termination_condition}")
