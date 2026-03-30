"""Diagnose infeasibility in star topology with PWL + SOS2 delay."""
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

n_constraints = sum(1 for c in model.component_objects(pyo.Constraint, active=True) for _ in c)
n_vars = sum(1 for v in model.component_objects(pyo.Var, active=True) for _ in v)
n_binary = sum(1 for v in model.component_objects(pyo.Var, active=True) for idx in v if v[idx].domain == pyo.Binary)
print(f"Variables: {n_vars} ({n_binary} binary), Constraints: {n_constraints}")

# LP Relaxation test
print("\n=== LP Relaxation ===")
binary_vars = []
for v in model.component_objects(pyo.Var, active=True):
    for idx in v:
        if v[idx].domain == pyo.Binary:
            binary_vars.append((v, idx))
            v[idx].domain = pyo.NonNegativeReals
            if v[idx].ub is None:
                v[idx].setub(1.0)

opt = Highs()
opt.config.load_solution = False
results = opt.solve(model)
tc = str(results.termination_condition)
print(f"LP relaxation: {tc}")

def is_infeasible(tc_str):
    return 'infeasible' in tc_str.lower() or 'Infeasible' in tc_str

if not is_infeasible(tc):
    print("LP relaxation is feasible - infeasibility from integrality only")
    sys.exit(0)

print("\nLP relaxation infeasible. Testing constraint groups...")

# Collect constraint groups
groups = {}
for c in model.component_objects(pyo.Constraint, active=True):
    name = c.name.lower()
    matched = False
    for kw in ['pwl', 'w_ub', 'w_lb', 'sos2', 'delayed_delivery',
                'delay_flow', 'pressure_drop', 'pressure_supply_prop',
                'pressure_return_prop', 'velocity', 'heat_loss',
                'heat_delivered', 'link_heat_demand', 'passthrough',
                'mass_balance', 'producer', 'junction', 'network_q_loss']:
        if kw in name:
            groups.setdefault(kw, []).append(c)
            matched = True
            break
    if not matched:
        groups.setdefault('other', []).append(c)

for gname in sorted(groups):
    n = sum(1 for c in groups[gname] for _ in c)
    print(f"  Group '{gname}': {len(groups[gname])} objects, {n} constraints")

# Disable groups one at a time
print("\n=== Single group removal ===")
for gname, constrs in sorted(groups.items()):
    for c in constrs:
        c.deactivate()
    try:
        r = opt.solve(model)
        status = str(r.termination_condition)
    except Exception as e:
        status = f"error: {e}"
    for c in constrs:
        c.activate()
    if not is_infeasible(status):
        print(f"  ** FEASIBLE without '{gname}' (status: {status})")
    else:
        print(f"     Still infeasible without '{gname}'")

# Try disabling pairs
print("\n=== Pair removal ===")
gnames = sorted(groups.keys())
for i, g1 in enumerate(gnames):
    for g2 in gnames[i+1:]:
        for c in groups[g1]:
            c.deactivate()
        for c in groups[g2]:
            c.deactivate()
        try:
            r = opt.solve(model)
            status = str(r.termination_condition)
        except Exception as e:
            status = f"error: {e}"
        for c in groups[g1]:
            c.activate()
        for c in groups[g2]:
            c.activate()
        if not is_infeasible(status):
            print(f"  ** FEASIBLE without '{g1}' + '{g2}'")
