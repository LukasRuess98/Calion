"""Diagnose delay bucket infeasibility - check specific constraints."""
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

opt = Highs()

# Relax delay binaries and solve to see what fractional values they take
delay_vars = {}
for v in model.component_objects(pyo.Var, active=True):
    if 'z_delay' in v.name.lower():
        delay_vars[v.name] = v
        for idx in v:
            if v[idx].domain == pyo.Binary:
                v[idx].domain = pyo.NonNegativeReals
                v[idx].setub(1.0)

opt.config.load_solution = True
r = opt.solve(model)
print(f"Relaxed delay solve: {r.termination_condition}")

# Check delay binary values - are they fractional?
print("\n=== Delay binary values (first 5 timesteps) ===")
for vname, v in sorted(delay_vars.items()):
    pipe = vname.split('_z_delay')[0]
    print(f"\n{pipe}:")
    for t in range(1, 6):  # first 5 timesteps
        vals = []
        for n in range(3):
            try:
                val = pyo.value(v[n, t])
                vals.append(f"z[{n}]={val:.3f}")
            except:
                vals.append(f"z[{n}]=???")
        print(f"  t={t}: {', '.join(vals)}")

# Also check m_dot values to see what flow rates the solver picks
print("\n=== Flow values (first 5 timesteps) ===")
for v in model.component_objects(pyo.Var, active=True):
    if v.name.endswith('_m_dot') and 'PLANT' in v.name:
        pipe = v.name
        print(f"\n{pipe}:")
        for t in range(1, 6):
            try:
                val = pyo.value(v[t])
                print(f"  t={t}: m_dot={val:.2f} kg/s")
            except:
                print(f"  t={t}: ???")

# Check demand values
print("\n=== Q_demand at consumers (first 5 timesteps) ===")
for v in model.component_objects(pyo.Var, active=True):
    if 'q_demand' in v.name.lower():
        print(f"\n{v.name}:")
        for t in range(1, 6):
            try:
                val = pyo.value(v[t])
                print(f"  t={t}: Q_demand={val:.3f} MW")
            except:
                print(f"  t={t}: ???")

# Check delay bucket flow bounds vs actual flow
print("\n=== Delay bucket bounds vs actual flow ===")
for v in model.component_objects(pyo.Var, active=True):
    if v.name.endswith('_m_dot') and any(p in v.name for p in ['PLANT_NORTH', 'PLANT_SOUTH', 'PLANT_EAST']):
        pipe = v.name.replace('_m_dot', '')
        m_dot_vals = [pyo.value(v[t]) for t in range(1, 6)]

        # Get delay flow bounds from the constraint
        lb_con = getattr(model, f'{pipe}_delay_flow_lb', None)
        ub_con = getattr(model, f'{pipe}_delay_flow_ub', None)

        print(f"\n{pipe}:")
        print(f"  Max flow bound: {v[1].ub}")
        for t in range(1, min(4, len(m_dot_vals)+1)):
            print(f"  t={t}: m_dot={m_dot_vals[t-1]:.2f}")

# Now try: what if we widen the delay flow bounds?
print("\n\n=== Test: Deactivate delay_flow_lb and delay_flow_ub ===")
# Restore delay binaries
for vname, v in delay_vars.items():
    for idx in v:
        v[idx].domain = pyo.Binary
        v[idx].setub(None)

# Deactivate delay flow bounds
deactivated = []
for c in model.component_objects(pyo.Constraint, active=True):
    if 'delay_flow_lb' in c.name or 'delay_flow_ub' in c.name:
        c.deactivate()
        deactivated.append(c.name)

print(f"Deactivated {len(deactivated)} delay flow bound constraints")
opt.config.load_solution = False
r = opt.solve(model)
print(f"Without delay flow bounds: {r.termination_condition}")

# Reactivate
for c in model.component_objects(pyo.Constraint, active=False):
    if c.name in deactivated:
        c.activate()

# Try deactivating just delay_flow_lb
print("\n=== Test: Deactivate only delay_flow_lb ===")
deactivated_lb = []
for c in model.component_objects(pyo.Constraint, active=True):
    if 'delay_flow_lb' in c.name:
        c.deactivate()
        deactivated_lb.append(c.name)

print(f"Deactivated {len(deactivated_lb)} delay_flow_lb constraints")
r = opt.solve(model)
print(f"Without delay_flow_lb: {r.termination_condition}")

for c in model.component_objects(pyo.Constraint, active=False):
    if c.name in deactivated_lb:
        c.activate()

# Try deactivating just delay_flow_ub
print("\n=== Test: Deactivate only delay_flow_ub ===")
deactivated_ub = []
for c in model.component_objects(pyo.Constraint, active=True):
    if 'delay_flow_ub' in c.name:
        c.deactivate()
        deactivated_ub.append(c.name)

print(f"Deactivated {len(deactivated_ub)} delay_flow_ub constraints")
r = opt.solve(model)
print(f"Without delay_flow_ub: {r.termination_condition}")
