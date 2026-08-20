"""
§5 Synthetic Generalizability Network Generator

Generates 36 YAML configs in synth_configs/ from a 3⁴=81 grid,
retaining only the 36 feasible parameter combinations.

Parameter grid:
    LENGTHS_KM = [1.0, 5.0, 15.0]       # total trunk length
    HI_LEVELS  = [0.1, 0.4, 0.8]        # demand heterogeneity index
    N_NODES    = [5, 15, 30]
    STORAGE_H  = [2, 6, 12]             # storage hours at peak demand

Usage:
    python tools/gen_synth.py --seed 42
    python tools/gen_synth.py --seed 42 --dry-run  # print but don't write
"""
from __future__ import annotations

import argparse
import itertools
import math
import random
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
SYNTH_DIR = ROOT / "synth_configs"
TEMPLATE_BASE = ROOT / "configs" / "memmingen" / "Memmingen_L1.yaml"

# Parameter grid
LENGTHS_KM = [1.0, 5.0, 15.0]
HI_LEVELS  = [0.1, 0.4, 0.8]
N_NODES    = [5, 15, 30]
STORAGE_H  = [2, 6, 12]

# Network constants
PEAK_DEMAND_MW = 76.0
CP_WATER = 4182.0        # J/(kg·K)
DT_NOMINAL = 60.0        # K (100°C - 40°C)
V_MAX = 2.5              # m/s
RHO_WATER = 1000.0       # kg/m³
PI = math.pi

# DN lookup [mm inner diameter → nominal DN]
DN_TABLE = [
    (20,  25), (26, 32), (35, 40), (41, 50), (53, 65),
    (67, 80), (79, 100), (103, 125), (128, 150), (154, 200),
    (202, 250), (253, 300), (304, 350), (355, 400), (407, 450),
    (456, 500), (508, 600),
]


def _peak_flow_kg_s(q_mw: float) -> float:
    return q_mw * 1e6 / (CP_WATER * DT_NOMINAL)


def _min_diameter_m(q_mw: float) -> float:
    flow = _peak_flow_kg_s(q_mw)
    area = flow / (RHO_WATER * V_MAX)
    return math.sqrt(4 * area / PI)


def _select_dn(d_inner_m: float) -> int:
    d_mm = d_inner_m * 1000
    for inner, dn in DN_TABLE:
        if inner >= d_mm:
            return dn
    return 600


def _gini_allocations(n_leaves: int, hi: float, seed: int) -> list[float]:
    """Allocate demand fractions with target Gini = hi."""
    rng = random.Random(seed)
    if hi <= 0.05:
        return [1.0 / n_leaves] * n_leaves
    if hi >= 0.95:
        fracs = [0.0] * n_leaves
        fracs[0] = 1.0
        return fracs
    # Draw from exponential, scale by hi
    raw = [rng.expovariate(1.0) for _ in range(n_leaves)]
    total = sum(raw)
    fracs = [r / total for r in raw]
    # Blend towards uniform to hit target HI
    uniform = 1.0 / n_leaves
    blend = hi
    fracs = [blend * f + (1 - blend) * uniform for f in fracs]
    total = sum(fracs)
    return [f / total for f in fracs]


def _balanced_tree_pipes(n_nodes: int, length_km: float, demand_fracs: list[float],
                          peak_mw: float, seed: int) -> list[dict]:
    """Generate balanced binary tree pipes."""
    depth = math.ceil(math.log2(max(n_nodes, 2)))
    # Assign demand to leaves
    n_leaves = min(n_nodes, 2 ** depth)
    fracs = demand_fracs[:n_leaves]

    # Total trunk length divided equally among edges
    n_edges = n_nodes - 1
    if n_edges <= 0:
        return []
    edge_length_m = (length_km * 1000) / n_edges

    pipes = []
    for i in range(1, n_nodes):
        parent = (i - 1) // 2 if i > 0 else 0
        from_node = f"j_{parent + 1}"
        to_node = f"j_{i + 1}"
        # Downstream demand = sum of fracs in subtree rooted at i
        downstream_frac = sum(fracs[j] for j in range(i, n_nodes) if j < len(fracs))
        q_downstream_mw = downstream_frac * peak_mw
        d_inner = _min_diameter_m(q_downstream_mw) if q_downstream_mw > 0 else 0.05
        dn = _select_dn(d_inner)
        u = 0.32 if dn >= 250 else 0.28
        pipes.append({
            "id": f"j{parent+1}_to_j{i+1}",
            "from": from_node,
            "to": to_node,
            "length_m": round(edge_length_m, 0),
            "diameter_mm": dn,
            "u_value_supply_w_per_m_k": u,
            "u_value_return_w_per_m_k": round(u + 0.02, 2),
        })
    return pipes


def _is_feasible(params: dict) -> tuple[bool, str]:
    """Check if a parameter combo is physically feasible."""
    n = params["n_nodes"]
    length_km = params["length_km"]
    hi = params["hi"]

    # Min pipe length: at least 50m per pipe
    n_pipes = n - 1
    if n_pipes > 0 and (length_km * 1000 / n_pipes) < 50:
        return False, f"Edge length < 50m (n={n}, L={length_km}km)"

    # Storage hours must be positive
    if params["storage_h"] <= 0:
        return False, "storage_h <= 0"

    return True, ""


def build_config(params: dict, demand_fracs: list[float], pipes: list[dict]) -> dict:
    n = params["n_nodes"]
    peak_mw = PEAK_DEMAND_MW
    storage_mwh = round(peak_mw * params["storage_h"], 0)

    nodes: dict[str, Any] = {}
    for i in range(n):
        node_id = f"j_{i + 1}"
        frac = demand_fracs[i] if i < len(demand_fracs) else 0.0
        node: dict[str, Any] = {
            "consumers": [{"column": "waermebedarf_MWth", "demand_fraction": round(frac, 4)}]
        }
        if i == 0:
            node["assets"] = ["hp_main", "tes_main"]
        nodes[node_id] = node

    pipes_cfg: dict[str, Any] = {}
    for p in pipes:
        pipes_cfg[p["id"]] = {
            "from": p["from"],
            "to": p["to"],
            "length_m": int(p["length_m"]),
            "diameter_mm": p["diameter_mm"],
            "u_value_supply_w_per_m_k": p["u_value_supply_w_per_m_k"],
            "u_value_return_w_per_m_k": p["u_value_return_w_per_m_k"],
        }

    cfg = {
        "site": {
            "input_xlsx": "data/2025_04_14_Import_Data_Memmingen.xlsx",
            "columns": {"datetime": "Datum", "price": "strompreis_EUR_MWh", "co2_grid": "grid_co2_kg_MWh"},
        },
        "scenario": {
            "name": f"Synth n{n}_L{params['length_km']}km_hi{params['hi']}_s{params['storage_h']}h",
            "run_mode": "PF_ONLY",
            "milp_linearize": True,
            "horizon": {"start": "2025-01-01 00:00", "end": "2025-12-31 23:00"},
        },
        "network": {
            "milp_linearize": True,
            "physics": {"heat_loss": True, "pressure_drop": True, "transport_delay": True},
            "supply_temp_c": 100,
            "return_temp_c": 40,
            "ground_temp_c": 10,
            "max_velocity_m_s": 2.5,
            "pump_efficiency": 0.75,
            "pipe_roughness_mm": 0.5,
            "max_pressure_drop_bar": 2.0,
            "linearization": {
                "method": "pwl",
                "temperature_profile": {
                    "load_fractions": [0.0, 0.3, 0.6, 1.0],
                    "T_supply_c": [70.0, 80.0, 90.0, 100.0],
                    "T_return_c": [55.0, 50.0, 45.0, 40.0],
                },
            },
            "nodes": nodes,
            "pipes": pipes_cfg,
        },
        "assets": {
            "hp_main": {
                "type": "heat_pump",
                "capacity_mw": float(peak_mw),
                "min_load": 0.1,
                "cop_method": "analytical_lmtd",
                "sink_temp_c": 90.0,
                "source_columns": ["wrg1_temp", "wrg2_temp"],
                "carnot_efficiency": 0.6,
                "cop_default": 3.0,
            },
            "tes_main": {
                "type": "storage",
                "energy_capacity_mwh": float(storage_mwh),
                "power_capacity_mw": float(round(peak_mw * 0.5, 0)),
                "charge_efficiency": 0.95,
                "discharge_efficiency": 0.95,
                "min_load_mw": 0.0,
                "round_trip_efficiency": 0.90,
                "soc_min": 0.0,
                "soc_max": 1.0,
                "soc0_mwh": float(storage_mwh / 2),
                "terminal": {"state": "cyclic", "policy": "equal"},
            },
        },
        "grid": {"max_import_mw": 5000.0, "max_export_mw": 5000.0, "gridcost_eur_mwh": 35.0},
        "fuels": {"gas": {"price_eur_mwh": 45.0, "ef_kg_per_mwh_fuel": 200.0}},
        "costs": {"co2_price_eur_per_t": 1000.0, "dump_cost_eur_per_mwh_th": 1000.0},
        "run": {
            "dt_h": 1.0,
            "solver": "gurobi",
            "solver_options": {"MIPGap": 0.01, "TimeLimit": 7200, "OutputFlag": 0, "LogToConsole": 0},
        },
    }
    return cfg


def _yaml_dump(cfg: dict) -> str:
    if yaml is not None:
        return yaml.dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False)
    # Fallback: JSON
    import json
    return json.dumps(cfg, indent=2, ensure_ascii=False)


def generate(seed: int = 42, dry_run: bool = False) -> list[dict]:
    rng = random.Random(seed)
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)

    all_combos = list(itertools.product(LENGTHS_KM, HI_LEVELS, N_NODES, STORAGE_H))
    feasible = []
    dropped = []

    for length_km, hi, n, storage_h in all_combos:
        params = {"length_km": length_km, "hi": hi, "n_nodes": n, "storage_h": storage_h}
        ok, reason = _is_feasible(params)
        if ok:
            feasible.append(params)
        else:
            dropped.append((params, reason))

    # Keep at most 36
    rng.shuffle(feasible)
    selected = feasible[:36]
    selected.sort(key=lambda p: (p["n_nodes"], p["length_km"], p["hi"], p["storage_h"]))

    configs_written = []
    for i, params in enumerate(selected):
        local_seed = seed + i
        fracs = _gini_allocations(params["n_nodes"], params["hi"], local_seed)
        pipes = _balanced_tree_pipes(
            params["n_nodes"], params["length_km"], fracs, PEAK_DEMAND_MW, local_seed
        )
        cfg = build_config(params, fracs, pipes)
        name = (
            f"synth_n{params['n_nodes']:02d}"
            f"_L{str(params['length_km']).replace('.','p')}km"
            f"_hi{str(params['hi']).replace('.','p')}"
            f"_s{params['storage_h']}h"
        )
        out_path = SYNTH_DIR / f"{name}.yaml"
        if not dry_run:
            out_path.write_text(_yaml_dump(cfg), encoding="utf-8")
        configs_written.append({"name": name, "params": params, "path": str(out_path)})

    # Write README
    readme_lines = [
        "# Synthetic Network Configs — §5\n\n",
        f"Generated with `python tools/gen_synth.py --seed {seed}`\n\n",
        f"Total combinations: {len(all_combos)} (3⁴=81 grid)\n",
        f"Feasible: {len(feasible)}\n",
        f"Selected: {len(selected)}\n\n",
        "## Parameter Table\n\n",
        "| # | n_nodes | length_km | HI | storage_h |\n",
        "|---|---------|-----------|----|-----------|\n",
    ]
    for i, c in enumerate(configs_written):
        p = c["params"]
        readme_lines.append(f"| {i+1} | {p['n_nodes']} | {p['length_km']} | {p['hi']} | {p['storage_h']} |\n")

    readme_lines.append("\n## Feasibility Filter Log\n\n")
    readme_lines.append(f"Dropped {len(dropped)} of {len(all_combos)} combinations:\n\n")
    for params, reason in dropped[:20]:
        readme_lines.append(f"- n={params['n_nodes']}, L={params['length_km']}km, HI={params['hi']}, s={params['storage_h']}h → {reason}\n")
    if len(dropped) > 20:
        readme_lines.append(f"- ... and {len(dropped) - 20} more\n")

    if not dry_run:
        (SYNTH_DIR / "_README.md").write_text("".join(readme_lines), encoding="utf-8")

    print(f"[GEN] {len(selected)} synthetic configs written to {SYNTH_DIR}/")
    return configs_written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    generate(seed=args.seed, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
