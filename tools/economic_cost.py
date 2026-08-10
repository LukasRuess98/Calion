"""
Economic-cost reporting for the Paper-1 revision.

Motivation (see revision/audit/P11_status.md): the Gurobi objective
(`OBJ_value_EUR`, = calion's reported "cost") contains a large non-economic
residual — `terminal_value + demand_slack_cost + return_anchor_cost`, ~38-41 % of
the objective on Memmingen, dominated by the return-temperature regularizer. All
v1 bias percentages were normalised to this penalty-laden objective, which damps
them. The revision reports bias/regret on ECONOMIC cost instead:

    economic_cost = energy_buy - revenue_sell + fuel + co2 + dump + demand_charge

This tool reads a set of solved run directories (each with economics.csv + meta.json),
computes economic cost and the residual per level, and reports level-to-level gaps on
BOTH bases (objective and economic) side by side. Pure post-processing: it never
touches the model, the configs, or Paper 2.

Usage:
    python tools/economic_cost.py --runs L1=path L2=path L3=path L3plus=path \
        --ref L3 --out results/v2/analysis/economic_gaps.csv
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

ECON_COMPONENTS = [
    ("cost_energy_buy_eur", +1),
    ("revenue_sell_eur", -1),
    ("cost_fuel_eur", +1),
    ("cost_co2_eur", +1),
    ("cost_dump_eur", +1),
    ("cost_demand_charge_eur", +1),
]


def economic_cost(econ_row: pd.Series) -> float:
    """Sum the economic components (matches result_collector.components_sum minus
    the ~0 capex/activation/tie_break/storage_install for a dispatch run)."""
    total = 0.0
    for col, sign in ECON_COMPONENTS:
        total += sign * float(econ_row.get(col, 0.0) or 0.0)
    return total


def load_level(run_dir: str) -> dict:
    ec = pd.read_csv(os.path.join(run_dir, "economics.csv")).iloc[0]
    obj = float(ec["cost_total_eur"])          # = OBJ_value_EUR
    econ = economic_cost(ec)
    return {
        "run_dir": run_dir,
        "OBJ_eur": obj,
        "econ_eur": econ,
        "residual_eur": obj - econ,
        "residual_pct": 100.0 * (obj - econ) / obj if obj else float("nan"),
        "cost_fuel_eur": float(ec.get("cost_fuel_eur", 0.0)),
        "cost_co2_eur": float(ec.get("cost_co2_eur", 0.0)),
        "cost_pump_eur": float(ec.get("cost_pump_eur", 0.0)),
        "co2_total_t": float(ec.get("co2_total_t", 0.0)),
    }


def build_table(runs: dict, ref: str) -> pd.DataFrame:
    rows = {lvl: load_level(d) for lvl, d in runs.items()}
    df = pd.DataFrame(rows).T
    df.index.name = "level"
    return df


def gaps_both_bases(df: pd.DataFrame, ref: str) -> pd.DataFrame:
    """Level-vs-ref gap on objective and on economic cost (percent of ref)."""
    ref_obj = df.loc[ref, "OBJ_eur"]
    ref_econ = df.loc[ref, "econ_eur"]
    out = []
    for lvl, r in df.iterrows():
        out.append({
            "level": lvl,
            "gap_OBJ_pct": 100.0 * (r["OBJ_eur"] - ref_obj) / ref_obj,
            "gap_econ_pct": 100.0 * (r["econ_eur"] - ref_econ) / ref_econ,
            "OBJ_eur": r["OBJ_eur"],
            "econ_eur": r["econ_eur"],
            "residual_pct": r["residual_pct"],
        })
    return pd.DataFrame(out).set_index("level")


def _parse_runs(items):
    runs = {}
    for it in items:
        lvl, path = it.split("=", 1)
        runs[lvl] = path
    return runs


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Economic-cost gap reporting (Paper 1)")
    ap.add_argument("--runs", nargs="+", required=True,
                    help="level=run_dir pairs, e.g. L1=output/.../L1")
    ap.add_argument("--ref", default="L3", help="reference level (default L3 = T2P1)")
    ap.add_argument("--out", default=None, help="optional CSV path for the gap table")
    a = ap.parse_args()
    runs = _parse_runs(a.runs)
    df = build_table(runs, a.ref)
    gaps = gaps_both_bases(df, a.ref)
    pd.set_option("display.width", 200, "display.float_format", lambda x: f"{x:,.3f}")
    print("Per-level economic vs objective cost:")
    print(df[["OBJ_eur", "econ_eur", "residual_eur", "residual_pct"]].to_string())
    print("\nLevel-vs-%s gaps on both bases:" % a.ref)
    print(gaps[["gap_OBJ_pct", "gap_econ_pct"]].to_string())
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        gaps.to_csv(a.out)
        print(f"\nwrote {a.out}")
