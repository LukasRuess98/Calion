"""
Synthetic parametric network study — generalises L1/L2/L3 topology comparison.

Creates idealised ring networks, varies 4 parameters across 36 combinations,
runs 108 MILP optimisations (L1 + L2 + L3 per combination), and exports a
cost-gap matrix.

Usage:
    python scripts/paper/run_synthetic_parametric.py
    python scripts/paper/run_synthetic_parametric.py --outdir outputs/paper/synthetic
    python scripts/paper/run_synthetic_parametric.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import itertools
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Repository root on sys.path so calion is importable
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from calion.run.workflow import run_workflow  # noqa: E402

# ---------------------------------------------------------------------------
# Parameter grid (36 combinations)
# ---------------------------------------------------------------------------

PIPE_LENGTHS_KM: list[float] = [3.0, 8.0, 15.0]
DEMAND_HETERO: list[str]     = ["uniform", "moderate", "concentrated"]
STORAGE_RATIOS: list[float]  = [0.1, 0.3, 0.6]
NODE_COUNTS: list[int]       = [5, 15, 30]

PEAK_DEMAND_MW = 80.0   # fixed reference — matches synthetic 1-week dataset

# Input data — use the real file that exists in the repository
SYNTHETIC_DATA_PATH = "data/stadtbach_synthetic_2023_1week_zonal.csv"

# ---------------------------------------------------------------------------
# Demand-fraction helpers
# ---------------------------------------------------------------------------


def _demand_fractions(n: int, heterogeneity: str) -> list[float]:
    """Return a list of n demand fractions that sum to 1.0."""
    if heterogeneity == "uniform":
        return [1.0 / n] * n

    if heterogeneity == "moderate":
        # Linear ramp: node 0 gets the smallest share, node n-1 the largest
        raw = [1.0 + i for i in range(n)]
        total = sum(raw)
        return [v / total for v in raw]

    if heterogeneity == "concentrated":
        # First node gets 60 %, the remainder is split equally
        if n == 1:
            return [1.0]
        first = 0.60
        rest = (1.0 - first) / (n - 1)
        return [first] + [rest] * (n - 1)

    raise ValueError(f"Unknown heterogeneity type: {heterogeneity!r}")


# ---------------------------------------------------------------------------
# YAML config builders
# ---------------------------------------------------------------------------


def _common_assets(storage_mwh: float) -> dict[str, Any]:
    """Return the asset/fuel/costs/run sub-dicts shared by all topology levels."""
    return {
        "assets": {
            "boiler_main": {
                "type": "thermal_generator",
                "fuel": "gas",
                "capacity_mw": 200.0,
                "min_load": 0.0,
                "thermal_efficiency": 0.90,
            },
            "hp_main": {
                "type": "heat_pump",
                "capacity_mw": 100.0,
                "min_load": 0.0,
                "cop_method": "analytical_lmtd",
                "sink_temp_c": 90.0,
                "source_columns": ["wrg1_temp", "wrg2_temp"],
                "carnot_efficiency": 0.50,
                "cop_default": 3.0,
            },
            "tes_main": {
                "type": "storage",
                "energy_mwh": float(storage_mwh),
                "power_mw": 50.0,
                "min_soc": 0.05,
                "max_soc": 0.95,
                "loss_type": "pwl",
                "loss_segments": 10,
                "storage_loss_mwh_per_hour": 0.25,
            },
        },
        "grid": {
            "max_import_mw": 200.0,
            "max_export_mw": 0.0,
            "gridcost_eur_mwh": 35.0,
        },
        "fuels": {
            "gas": {
                "price_eur_mwh": 45.0,
                "ef_kg_per_mwh_fuel": 200.0,
            }
        },
        "costs": {
            "co2_price_eur_per_t": 100.0,
            "dump_cost_eur_per_mwh_th": 10.0,
        },
        "run": {
            "dt_h": 1.0,
            "solver": "appsi_highs",
            "mip_gap": 0.001,
            "time_limit_s": 600,
        },
    }


def _site_block() -> dict[str, Any]:
    return {
        "site": {
            "input_xlsx": SYNTHETIC_DATA_PATH,
            "columns": {
                "datetime":  "Datum",
                "price":     "strompreis_EUR_MWh",
                "co2_grid":  "grid_co2_kg_MWh",
                "wrg1_temp": "T_WRG1_C",
                "wrg2_temp": "T_WRG2_C",
            },
        }
    }


def build_l1_config(
    combo_id: str,
    storage_mwh: float,
) -> dict[str, Any]:
    """L1 copperplate — single aggregated node, no network, no losses."""
    cfg: dict[str, Any] = {}
    cfg.update(_site_block())
    cfg["scenario"] = {
        "name": f"synthetic_L1_{combo_id}",
        "run_mode": "PF_ONLY",
    }
    cfg["network"] = {
        "physics": {
            "heat_loss": False,
            "pressure_drop": False,
            "transport_delay": False,
        },
        "supply_temp_c": 90.0,
        "return_temp_c": 55.0,
        "ground_temp_c": 10.0,
        "nodes": {
            "plant": {
                "type": "producer",
                "assets": ["boiler_main", "hp_main", "tes_main"],
                "demand": {"column": "waermebedarf_MWth"},
            }
        },
        "pipes": {},
    }
    cfg.update(_common_assets(storage_mwh))
    return cfg


def build_l2_config(
    combo_id: str,
    n_nodes: int,
    pipe_length_km: float,
    demand_fractions: list[float],
    storage_mwh: float,
) -> dict[str, Any]:
    """L2 simplified — N consumer nodes connected directly to plant (star topology)."""
    pipe_length_m = pipe_length_km * 1000.0 / n_nodes

    nodes: dict[str, Any] = {
        "plant": {
            "type": "producer",
            "assets": ["boiler_main", "hp_main", "tes_main"],
        }
    }
    pipes: dict[str, Any] = {}

    for i in range(n_nodes):
        node_name = f"node_{i}"
        # Distribute total demand via waermebedarf_MWth scaled by fraction
        # We use the aggregated demand column with a scale factor via
        # a demand block; calion supports a 'scale' multiplier on demand columns
        nodes[node_name] = {
            "type": "consumer",
            "demand": {
                "column": "waermebedarf_MWth",
                "scale": round(demand_fractions[i], 6),
            },
        }
        pipes[f"plant_to_node_{i}"] = {
            "from": "plant",
            "to": node_name,
            "length_m": round(pipe_length_m, 1),
            "diameter_mm": 300,
            "u_value_w_mk": 0.15,
        }

    cfg: dict[str, Any] = {}
    cfg.update(_site_block())
    cfg["scenario"] = {
        "name": f"synthetic_L2_{combo_id}",
        "run_mode": "PF_ONLY",
    }
    cfg["network"] = {
        "physics": {
            "heat_loss": True,
            "pressure_drop": True,
            "transport_delay": False,
        },
        "supply_temp_c": 90.0,
        "return_temp_c": 55.0,
        "ground_temp_c": 10.0,
        "nodes": nodes,
        "pipes": pipes,
    }
    cfg.update(_common_assets(storage_mwh))
    return cfg


def build_l3_config(
    combo_id: str,
    n_nodes: int,
    pipe_length_km: float,
    demand_fractions: list[float],
    storage_mwh: float,
) -> dict[str, Any]:
    """L3 detailed — N consumer nodes in a branched topology with a central junction."""
    total_length_m = pipe_length_km * 1000.0
    # Trunk: plant -> central junction consumes 20 % of total length
    trunk_length_m = round(total_length_m * 0.20, 1)
    # Remaining length split equally among branch pipes (plant -> each node via junction)
    branch_length_m = round((total_length_m - trunk_length_m) / n_nodes, 1)

    nodes: dict[str, Any] = {
        "plant": {
            "type": "producer",
            "assets": ["boiler_main", "hp_main", "tes_main"],
        },
        "j_central": {"type": "junction"},
    }
    pipes: dict[str, Any] = {
        "plant_to_central": {
            "from": "plant",
            "to": "j_central",
            "length_m": trunk_length_m,
            "diameter_mm": 500,
            "u_value_w_mk": 0.15,
        }
    }

    for i in range(n_nodes):
        node_name = f"node_{i}"
        nodes[node_name] = {
            "type": "consumer",
            "demand": {
                "column": "waermebedarf_MWth",
                "scale": round(demand_fractions[i], 6),
            },
        }
        pipes[f"central_to_node_{i}"] = {
            "from": "j_central",
            "to": node_name,
            "length_m": branch_length_m,
            "diameter_mm": 200,
            "u_value_w_mk": 0.15,
        }

    cfg: dict[str, Any] = {}
    cfg.update(_site_block())
    cfg["scenario"] = {
        "name": f"synthetic_L3_{combo_id}",
        "run_mode": "PF_ONLY",
    }
    cfg["network"] = {
        "physics": {
            "heat_loss": True,
            "pressure_drop": True,
            "transport_delay": False,
        },
        "supply_temp_c": 90.0,
        "return_temp_c": 55.0,
        "ground_temp_c": 10.0,
        "nodes": nodes,
        "pipes": pipes,
    }
    cfg.update(_common_assets(storage_mwh))
    return cfg


# ---------------------------------------------------------------------------
# YAML serialisation helper
# ---------------------------------------------------------------------------


def _write_temp_yaml(cfg: dict[str, Any]) -> Path:
    """Write *cfg* to a NamedTemporaryFile and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="synthetic_calion_",
        delete=False,
        encoding="utf-8",
    )
    yaml.dump(cfg, tmp, default_flow_style=False, allow_unicode=True, sort_keys=False)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Result extraction
# ---------------------------------------------------------------------------


def _extract_cost(workflow) -> float | None:
    """Pull the total objective cost [EUR] from a finished workflow object."""
    result = workflow.mpc_result or workflow.rh_result or workflow.pf_result
    if result is None:
        return None

    costs   = result.costs   or {}
    summary = result.summary or {}
    obj_section = summary.get("objective", {}) if isinstance(summary.get("objective"), dict) else {}

    # Try the flat dotted-key format first, then nested summary dict
    for key in ("objective.OBJ_value_EUR", "OBJ_value_EUR"):
        val = costs.get(key)
        if val is not None:
            return float(val)

    val = obj_section.get("OBJ_value_EUR")
    if val is not None:
        return float(val)

    # Fall back to sum of individual cost components
    components = [
        "objective.Grid_net_cost_EUR",
        "objective.Fuel_cost_EUR",
        "objective.Dump_cost_EUR",
        "objective.CO2_cost_EUR",
        "objective.Demand_charge_cost_EUR",
        "objective.Capex_cost_EUR",
        "objective.Activation_cost_EUR",
        "objective.Tie_breaker_cost_EUR",
        "objective.Storage_installation_cost_EUR",
    ]
    total = sum(float(costs.get(c, 0.0)) for c in components)
    return total if total != 0.0 else None


# ---------------------------------------------------------------------------
# Single-solve runner
# ---------------------------------------------------------------------------


def run_single(
    cfg: dict[str, Any],
    label: str,
) -> tuple[float | None, float, str]:
    """
    Write *cfg* to a temp file, run it, return (cost_eur, solve_seconds, status).

    On any exception returns (None, elapsed, error_message).
    """
    tmp_path = _write_temp_yaml(cfg)
    t0 = time.perf_counter()
    try:
        workflow = run_workflow([str(tmp_path)])
        elapsed = time.perf_counter() - t0
        cost = _extract_cost(workflow)
        status = "OK" if cost is not None else "no_result"
        return cost, round(elapsed, 2), status
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - t0
        return None, round(elapsed, 2), f"ERROR: {exc}"
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Combo description helpers
# ---------------------------------------------------------------------------


def _combo_id(pipe_km: float, hetero: str, stor_ratio: float, n_nodes: int) -> str:
    return f"pl{pipe_km:.0f}_{hetero[:3]}_sr{stor_ratio:.1f}_n{n_nodes}"


def _all_combos() -> list[tuple[float, str, float, int]]:
    return list(itertools.product(PIPE_LENGTHS_KM, DEMAND_HETERO, STORAGE_RATIOS, NODE_COUNTS))


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------


def run_parametric(outdir: Path, dry_run: bool = False) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    combos = _all_combos()
    n_combos = len(combos)
    n_total  = n_combos * 3   # L1 + L2 + L3

    print("=" * 72)
    print(f"SYNTHETIC PARAMETRIC STUDY — {n_combos} combinations × 3 levels = {n_total} solves")
    print(f"Output directory: {outdir}")
    if dry_run:
        print("DRY-RUN MODE — configs printed, no solves")
    print("=" * 72)

    gap_rows: list[dict[str, Any]]  = []
    log_rows: list[dict[str, Any]]  = []

    for idx, (pipe_km, hetero, stor_ratio, n_nodes) in enumerate(combos, start=1):
        storage_mwh = stor_ratio * PEAK_DEMAND_MW
        fractions   = _demand_fractions(n_nodes, hetero)
        combo_id    = _combo_id(pipe_km, hetero, stor_ratio, n_nodes)

        print(f"\n[{idx:>3}/{n_combos}] {combo_id}")
        print(f"         pipe_km={pipe_km}  hetero={hetero}  "
              f"stor_ratio={stor_ratio}  n_nodes={n_nodes}  "
              f"storage_mwh={storage_mwh:.1f}")

        # Build all three configs
        cfg_l1 = build_l1_config(combo_id, storage_mwh)
        cfg_l2 = build_l2_config(combo_id, n_nodes, pipe_km, fractions, storage_mwh)
        cfg_l3 = build_l3_config(combo_id, n_nodes, pipe_km, fractions, storage_mwh)

        if dry_run:
            for level, cfg in [("L1", cfg_l1), ("L2", cfg_l2), ("L3", cfg_l3)]:
                print(f"\n  --- {level} config ---")
                print(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
            continue

        costs: dict[str, float | None] = {}

        for level, cfg in [("L1", cfg_l1), ("L2", cfg_l2), ("L3", cfg_l3)]:
            print(f"    Solving {level} ...", end="", flush=True)
            cost, elapsed, status = run_single(cfg, label=f"{combo_id}_{level}")
            costs[level] = cost
            print(f" {status}  ({elapsed:.1f} s)"
                  + (f"  cost={cost:,.0f} EUR" if cost is not None else ""))

            log_rows.append({
                "timestamp":         datetime.now().isoformat(timespec="seconds"),
                "combo_id":          combo_id,
                "level":             level,
                "pipe_length_km":    pipe_km,
                "demand_heterogeneity": hetero,
                "storage_ratio":     stor_ratio,
                "node_count":        n_nodes,
                "storage_mwh":       storage_mwh,
                "cost_eur":          cost if cost is not None else "",
                "solve_s":           elapsed,
                "status":            status,
            })

        # Compute gap metrics
        c1 = costs.get("L1")
        c2 = costs.get("L2")
        c3 = costs.get("L3")

        def _gap(higher: float | None, lower: float | None) -> float | None:
            if higher is not None and lower is not None and lower > 0:
                return round((higher - lower) / lower * 100.0, 4)
            return None

        gap_rows.append({
            "pipe_length_km":       pipe_km,
            "demand_heterogeneity": hetero,
            "storage_ratio":        stor_ratio,
            "node_count":           n_nodes,
            "L1_cost_eur":          c1 if c1 is not None else float("nan"),
            "L2_cost_eur":          c2 if c2 is not None else float("nan"),
            "L3_cost_eur":          c3 if c3 is not None else float("nan"),
            "L1_L3_gap_pct":        _gap(c3, c1) if _gap(c3, c1) is not None else float("nan"),
            "L2_L3_gap_pct":        _gap(c3, c2) if _gap(c3, c2) is not None else float("nan"),
        })

    if dry_run:
        return

    # ------------------------------------------------------------------
    # Export gap_matrix.csv
    # ------------------------------------------------------------------
    gap_csv = outdir / "gap_matrix.csv"
    gap_fields = [
        "pipe_length_km", "demand_heterogeneity", "storage_ratio", "node_count",
        "L1_cost_eur", "L2_cost_eur", "L3_cost_eur",
        "L1_L3_gap_pct", "L2_L3_gap_pct",
    ]
    with gap_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=gap_fields)
        writer.writeheader()
        writer.writerows(gap_rows)
    print(f"\nGap matrix   -> {gap_csv}")

    # ------------------------------------------------------------------
    # Export run_log.csv
    # ------------------------------------------------------------------
    log_csv = outdir / "run_log.csv"
    log_fields = [
        "timestamp", "combo_id", "level",
        "pipe_length_km", "demand_heterogeneity", "storage_ratio",
        "node_count", "storage_mwh", "cost_eur", "solve_s", "status",
    ]
    with log_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log_fields)
        writer.writeheader()
        writer.writerows(log_rows)
    print(f"Run log      -> {log_csv}")

    # ------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------
    ok_rows      = [r for r in gap_rows if r["L1_cost_eur"] == r["L1_cost_eur"]]  # not NaN
    failed_count = n_combos * 3 - sum(
        1 for r in log_rows if r["status"] == "OK"
    )

    print("\n" + "=" * 72)
    print("PARAMETRIC STUDY COMPLETE")
    print("=" * 72)
    print(f"  Combinations run:  {n_combos}")
    print(f"  Total solves:      {n_total}")
    print(f"  Failed solves:     {failed_count}")

    if ok_rows:
        l1l3_gaps = [r["L1_L3_gap_pct"] for r in ok_rows
                     if r["L1_L3_gap_pct"] == r["L1_L3_gap_pct"]]
        l2l3_gaps = [r["L2_L3_gap_pct"] for r in ok_rows
                     if r["L2_L3_gap_pct"] == r["L2_L3_gap_pct"]]
        if l1l3_gaps:
            print(f"  L1-L3 gap [%]:     min={min(l1l3_gaps):.2f}  "
                  f"mean={sum(l1l3_gaps)/len(l1l3_gaps):.2f}  max={max(l1l3_gaps):.2f}")
        if l2l3_gaps:
            print(f"  L2-L3 gap [%]:     min={min(l2l3_gaps):.2f}  "
                  f"mean={sum(l2l3_gaps)/len(l2l3_gaps):.2f}  max={max(l2l3_gaps):.2f}")

    print("=" * 72)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run synthetic parametric network study (L1/L2/L3 topology comparison). "
            "Generates 108 MILP optimisations across 36 parameter combinations and "
            "exports a cost-gap matrix."
        )
    )
    parser.add_argument(
        "--outdir",
        default="outputs/paper/synthetic",
        help="Output directory for gap_matrix.csv and run_log.csv "
             "(default: outputs/paper/synthetic)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the 36 generated configs to stdout without running any solves.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    outdir = ROOT / args.outdir if not Path(args.outdir).is_absolute() else Path(args.outdir)

    try:
        run_parametric(outdir=outdir, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
