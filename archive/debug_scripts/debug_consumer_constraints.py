#!/usr/bin/env python3
"""Debug: inspect model constraints for consumer nodes"""

import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from calion.io.loader import load_input_excel  
from calion.models.system_builder import build_model
from calion.config.merge import load_and_merge
import pyomo.environ as pyo

cfg = load_and_merge(["configs/templates/level2_minimal.yaml"])
excel_file = Path(cfg.get("site", {}).get("input_xlsx"))
time_series = load_input_excel(excel_file, cfg)
dt_h = cfg["run"]["dt_h"]

model = build_model(time_series, cfg, dt_h=dt_h)

print("\n" + "=" * 70)
print("CONSTRAINT INSPECTION: Consumer node constraints")
print("=" * 70)

# Find consumer-related constraints
consumer_constraints = []
for name, comp in model.component_map(pyo.Constraint).items():
    if 'consumer' in str(name).lower():
        consumer_constraints.append(name)

print(f"\nConsumer-related constraints: {len(consumer_constraints)}")
for name in sorted(consumer_constraints):
    constr = getattr(model, name)
    print(f"\n  {name}:")
    try:
        # Get first time-step to show structure
        first_time = list(model.time)[0]
        if hasattr(constr, '__getitem__'):
            expr = constr[first_time]
            print(f"    t={first_time}: {expr.expr}")
            if hasattr(expr, 'get_value'):
                print(f"    Value: {pyo.value(expr)}")
        else:
            print(f"    {constr.expr}")
    except Exception as e:
        print(f"    Error reading: {e}")

# Check Q_demand and Q_consumer
print("\n" + "=" * 70)
print("DEMAND VARIABLES")
print("=" * 70)

q_demand = getattr(model, 'consumer_1_Q_demand', None)
q_consumer = None

# Search for Q_consumer in pipe components
for name, comp in model.component_map(pyo.Var).items():
    if 'Q_consumer' in str(name):
        print(f"\nFound Q_consumer: {name}")
        q_consumer = comp
        break

if q_demand:
    print(f"\nQ_demand (consumer_1):")
    first_t = list(model.time)[0]
    print(f"  Type: {type(q_demand)}")
    print(f"  t={first_t}: {pyo.value(q_demand) if isinstance(q_demand, pyo.Param) else 'Var'}")
    
if q_consumer:
    first_t = list(model.time)[0]
    print(f"\nQ_consumer_pipe:")
    print(f"  Type: {type(q_consumer)}")
    print(f"  Bounds: {q_consumer.bounds()}")
    print(f"  t={first_t}: {q_consumer[first_t].value if hasattr(q_consumer[first_t], 'value') else pyo.value(q_consumer[first_t])}")
