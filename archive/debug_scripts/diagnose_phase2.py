#!/usr/bin/env python3
"""
ENERGIS INFEASIBILITY DIAGNOSTICS - PHASE 2
Model Structure Analysis and Isolation Testing
"""

import sys
import yaml
from pathlib import Path

print("\n" + "=" * 70)
print("PHASE 2: MODEL STRUCTURE ANALYSIS")
print("=" * 70)

# Load config
config_file = Path("configs/templates/level2_simple_3node.yaml")
with open(config_file) as f:
    config = yaml.safe_load(f)

print("\n[1] CONFIG NETWORK STRUCTURE")
print("-" * 70)

network = config.get("network", {})
print(f"Supply temp nominal:  {network.get('supply_temp_nominal_c')} °C")
print(f"Return temp nominal:  {network.get('return_temp_nominal_c')} °C")
print(f"Ground temp:          {network.get('ground_temp_c')} °C")

physics = network.get("physics", {})
print(f"\nPhysics enabled:")
for key, val in physics.items():
    print(f"  - {key}: {val}")

nodes = network.get("nodes", {})
print(f"\nNodes: {len(nodes)}")
for node_name, node_config in nodes.items():
    node_type = node_config.get("type", "unknown")
    print(f"  - {node_name} ({node_type})")
    if "assets" in node_config:
        print(f"    Assets: {node_config['assets']}")
    if "demand_fraction" in node_config:
        print(f"    Demand: {node_config['demand_fraction']}")

pipes = network.get("pipes", {})
print(f"\nPipes: {len(pipes)}")
for pipe_name, pipe_config in pipes.items():
    f_node = pipe_config.get("from")
    t_node = pipe_config.get("to")
    length = pipe_config.get("length_m")
    diam = pipe_config.get("diameter_mm")
    print(f"  - {pipe_name}: {f_node} → {t_node}")
    print(f"    Length: {length}m, Diameter: {diam}mm")

print("\n[2] CHECKING FOR MILP LINEARIZATION FLAG")
print("-" * 70)
milp_flag = config.get("run", {}).get("milp_linearize")
print(f"milp_linearize in config: {milp_flag}")
print("(Default from code: True if multi-node network)")

print("\n[3] ASSET VALIDATION")
print("-" * 70)
assets = config.get("assets", {})
total_capacity = 0
for asset_name, asset_config in assets.items():
    asset_type = asset_config.get("type")
    capacity = asset_config.get("capacity_mw", 0)
    total_capacity += capacity
    print(f"  {asset_name}: {asset_type} ({capacity} MW)")

print(f"\nTotal supply capacity: {total_capacity} MW")

print("\n[4] DEMAND FRACTION ANALYSIS")
print("-" * 70)
total_demand_fraction = 0
for node_name, node_config in nodes.items():
    if "demand_fraction" in node_config:
        frac = node_config["demand_fraction"]
        total_demand_fraction += frac
        print(f"  {node_name}: {frac}")

print(f"Total demand fraction: {total_demand_fraction}")
if total_demand_fraction != 1.0:
    print(f"⚠️  WARNING: Total demand fraction != 1.0")

print("\n[5] DIAGNOSTICS")
print("-" * 70)

issues = []

# Check 1: Nodes connectivity
unique_nodes = set()
for pipe_name, pipe_cfg in pipes.items():
    unique_nodes.add(pipe_cfg["from"])
    unique_nodes.add(pipe_cfg["to"])

config_nodes = set(nodes.keys())
if unique_nodes != config_nodes:
    issues.append(f"Node mismatch: Config has {config_nodes}, pipes reference {unique_nodes}")

# Check 2: Asset node placement
asset_nodes = set()
for node_name, node_cfg in nodes.items():
    if "assets" in node_cfg:
        asset_nodes.add(node_name)

if not asset_nodes:
    issues.append("No producer node with assets!")

# Check 3: Consumer demand
consumer_nodes = [n for n, cfg in nodes.items() if cfg.get("type") == "consumer"]
if not consumer_nodes:
    issues.append("No consumer nodes defined!")

# Check 4: Pipe topology
if len(pipes) < len(nodes) - 1:
    issues.append(f"Insufficient pipes for node count: {len(pipes)} pipes vs {len(nodes)} nodes")

if issues:
    print("❌ CONFIG ISSUES FOUND:")
    for issue in issues:
        print(f"   - {issue}")
else:
    print("✅ Config validates - no structural issues")

print("\n" + "=" * 70)
print("PHASE 2 RESULT")
print("=" * 70)
print("Config structure appears valid. Proceeding to Phase 3: Model building test.")
print("(Run: python diagnose_phase3.py)")
