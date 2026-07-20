"""
Synthetic gap analysis — computes cost and CO2 gaps between all level pairs
across the 36 synthetic configurations.

Usage:
    python scripts/paper/synth_gap_analysis.py

Output:
    output/paper_runs/synth_gap_summary.csv    (full table)
    output/paper_runs/synth_gap_statistics.json (per-gap statistics for paper)
    Printed summary report
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SYNTH_DIR = ROOT / "output" / "paper_runs" / "synth"
OUT_DIR   = ROOT / "output" / "paper_runs"

LEVELS = ["L1cp", "L1", "L2", "L3", "L3plus"]
COMPARISONS = [
    ("L1cp", "L3",     "topology gap (L1cp->L3, copperplate->full)"),
    ("L1cp", "L1",     "topology abstraction (L1cp->L1, no heat loss)"),
    ("L1",   "L2",     "heat loss effect (L1->L2)"),
    ("L2",   "L3",     "pressure drop effect (L2->L3)"),
    ("L1cp", "L2",     "topology+heat-loss (L1cp->L2)"),
    ("L3",   "L3plus", "physics fidelity (L3->L3+)"),
]


def _load_synth() -> pd.DataFrame:
    rows = []
    for d in sorted(SYNTH_DIR.iterdir()):
        eco = d / "economics.csv"
        if not eco.exists():
            continue
        m = re.match(r"^(.+)_(L1cp|L1|L2|L3|L3plus)$", d.name)
        if not m:
            continue
        config, level = m.group(1), m.group(2)

        # Only include base synth configs (skip _L1cp-variant config names)
        # Base configs: synth_n05_L15p0km_hi0p1_s12h
        # L1cp variants: synth_n05_L15p0km_hi0p1_s12h_L1cp  ← excluded
        if "_L1cp" in config or not re.match(r"synth_n\d+_L[\dp]+km_", config):
            continue

        p = re.match(
            r"synth_n(\d+)_L([\dp]+)km_hi([\dp]+)_s(\d+)h", config
        )
        n_nodes    = int(p.group(1)) if p else None
        pipe_km    = float(p.group(2).replace("p", ".")) if p else None
        hi         = float(p.group(3).replace("p", ".")) if p else None
        storage_h  = int(p.group(4)) if p else None

        df_eco = pd.read_csv(eco).iloc[0]

        # Annual demand and heat losses from dispatch
        disp = d / "dispatch_hourly.csv"
        qloss = 0.0
        demand_mwh = 0.0
        if disp.exists():
            dp = pd.read_csv(disp, parse_dates=["timestamp"])
            dt_h = (
                (dp["timestamp"].iloc[1] - dp["timestamp"].iloc[0]).total_seconds() / 3600
                if len(dp) > 1 else 1.0
            )
            qloss = float(dp["Q_loss_total_MW"].sum()) * dt_h if "Q_loss_total_MW" in dp.columns else 0.0
            demand_mwh = float(dp["Q_demand_total_MW"].sum()) * dt_h if "Q_demand_total_MW" in dp.columns else 0.0

        rows.append({
            "config":      config,
            "level":       level,
            "n_nodes":     n_nodes,
            "pipe_km":     pipe_km,
            "hi":          hi,
            "storage_h":   storage_h,
            "cost_eur":    float(df_eco["cost_total_eur"]),
            "co2_t":       float(df_eco["co2_total_t"]),
            "lcoh":        float(df_eco.get("lcoh_eur_per_MWh_th", 0)),
            "demand_mwh":  demand_mwh,
            "qloss_mwh":   qloss,
        })
    return pd.DataFrame(rows)


def _gap_stats(series: pd.Series, label: str) -> dict:
    s = series.dropna()
    return {
        "label":   label,
        "n":       int(len(s)),
        "min":     round(float(s.min()),   3),
        "p10":     round(float(np.percentile(s, 10)), 3),
        "p25":     round(float(np.percentile(s, 25)), 3),
        "median":  round(float(s.median()), 3),
        "p75":     round(float(np.percentile(s, 75)), 3),
        "p90":     round(float(np.percentile(s, 90)), 3),
        "max":     round(float(s.max()),   3),
        "mean":    round(float(s.mean()),  3),
        "std":     round(float(s.std()),   3),
    }


def main() -> None:
    print("Loading synthetic run economics...")
    df = _load_synth()
    if df.empty:
        print("[ERROR] No economics.csv files found in", SYNTH_DIR)
        return

    n_configs = df["config"].nunique()
    n_levels  = df["level"].nunique()
    print(f"  {n_configs} configs × {n_levels} levels = {len(df)} rows loaded")

    # --- Pivot ---
    cost   = df.pivot(index="config", columns="level", values="cost_eur")
    co2    = df.pivot(index="config", columns="level", values="co2_t")
    loss   = df.pivot(index="config", columns="level", values="qloss_mwh")
    demand = df.pivot(index="config", columns="level", values="demand_mwh")

    # --- Physics override sanity check ---
    # L1: heat_loss=False → Q_loss must be 0
    # L2: heat_loss=True, pressure_drop=False → Q_loss > 0, pump cost = 0
    # L3: heat_loss=True, pressure_drop=True → Q_loss > 0, pump cost > 0
    print("\n-- Physics override sanity check --")
    if "L1" in loss.columns and "L2" in loss.columns:
        n_equal_loss = (loss["L1"] == loss["L2"]).sum()
        flag = "[WARN] heat_loss override NOT applied" if n_equal_loss > 0 else "[OK]"
        print(f"  Q_loss(L1) == Q_loss(L2): {n_equal_loss}/{len(loss)}  {flag}  (expected 0)")
    if "L2" in loss.columns and "L3" in loss.columns:
        n_l2_l3 = (loss["L2"] == loss["L3"]).sum()
        note = "[OK] losses match (pipe losses independent of pressure_drop model)" if n_l2_l3 == len(loss) else "[CHECK] some differences"
        print(f"  Q_loss(L2) == Q_loss(L3): {n_l2_l3}/{len(loss)}  {note}")
    if "L1" in loss.columns and "L3" in loss.columns:
        n_equal = (loss["L1"] == loss["L3"]).sum()
        flag = "[WARN] L1 and L3 have same losses — heat_loss not applied?" if n_equal > 0 else "[OK]"
        print(f"  Q_loss(L1) == Q_loss(L3): {n_equal}/{len(loss)}  {flag}")
    else:
        print("  L1/L3 network results not yet available (still running)")

    # --- Gap tables ---
    gap_rows = []
    stats = {}

    for lo, hi_lvl, label in COMPARISONS:
        if lo not in cost.columns or hi_lvl not in cost.columns:
            print(f"  [SKIP] {label} - level missing")
            continue

        gap_cost_pct = (cost[hi_lvl] - cost[lo]) / cost[hi_lvl].abs() * 100
        gap_cost_eur = cost[hi_lvl] - cost[lo]
        gap_co2_t    = co2[hi_lvl] - co2[lo]
        n_zero       = (gap_cost_pct.abs() < 0.001).sum()

        # Absolute gap: EUR per MWh of annual demand (reference = hi_lvl demand)
        ref_demand = demand[hi_lvl] if hi_lvl in demand.columns else demand.get(lo)
        if ref_demand is not None:
            gap_cost_eur_per_mwh = gap_cost_eur / ref_demand.replace(0, np.nan)
        else:
            gap_cost_eur_per_mwh = pd.Series(np.nan, index=cost.index)

        stats[f"{lo}_vs_{hi_lvl}"] = {
            "cost_gap_pct":        _gap_stats(gap_cost_pct, label),
            "cost_gap_eur_per_mwh": _gap_stats(gap_cost_eur_per_mwh, label),
            "co2_gap_t":           _gap_stats(gap_co2_t, label),
            "n_zero_gap":          int(n_zero),
            "note": (
                "[WARN] many zero gaps — check if L3 has pressure_drop=True (may be using old physics preset)"
                if lo == "L2" and hi_lvl == "L3" and n_zero > len(gap_cost_pct) * 0.8
                else "[WARN] unexpectedly many zero gaps - check physics override"
                if n_zero > len(gap_cost_pct) * 0.8 else "ok"
            ),
        }

        for config in cost.index:
            gap_rows.append({
                "comparison":          f"{lo}->{hi_lvl}",
                "config":              config,
                "gap_cost_pct":        round(float(gap_cost_pct.get(config, np.nan)), 4),
                "gap_cost_eur":        round(float(gap_cost_eur.get(config, np.nan)), 2),
                "gap_cost_eur_per_mwh": round(float(gap_cost_eur_per_mwh.get(config, np.nan)), 4),
                "gap_co2_t":           round(float(gap_co2_t.get(config, np.nan)), 2),
            })

    # --- Print summary ---
    print("\n-- Gap statistics across synthetic configurations --")
    for key, s in stats.items():
        cp  = s["cost_gap_pct"]
        ca  = s["cost_gap_eur_per_mwh"]
        print(f"\n  {cp['label']}  [n={cp['n']}]")
        print(f"    Cost gap [%]:        min={cp['min']:.2f}  p10={cp['p10']:.2f}  "
              f"median={cp['median']:.2f}  p90={cp['p90']:.2f}  max={cp['max']:.2f}")
        print(f"    Cost gap [EUR/MWh]:  min={ca['min']:.2f}  p10={ca['p10']:.2f}  "
              f"median={ca['median']:.2f}  p90={ca['p90']:.2f}  max={ca['max']:.2f}")
        print(f"    Zero gaps: {s['n_zero_gap']}/{cp['n']}")
        if s["note"] != "ok":
            print(f"    NOTE: {s['note']}")

    # --- Key paper results ---
    print("\n-- PAPER-READY RESULTS --")

    key_topo = "L1cp_vs_L3"
    if key_topo in stats:
        cp = stats[key_topo]["cost_gap_pct"]
        ca = stats[key_topo]["cost_gap_eur_per_mwh"]
        print(f"\n  [TOPOLOGY GAP L1cp->L3, n={cp['n']}]")
        print(f"  Cost gap [%]:       min={cp['min']:.2f}  p10={cp['p10']:.2f}  "
              f"median={cp['median']:.2f}  p90={cp['p90']:.2f}  max={cp['max']:.2f}")
        print(f"  Cost gap [EUR/MWh]: min={ca['min']:.2f}  p10={ca['p10']:.2f}  "
              f"median={ca['median']:.2f}  p90={ca['p90']:.2f}  max={ca['max']:.2f}")
        cc = stats[key_topo]["co2_gap_t"]
        print(f"  CO2  gap [t/yr]: min={cc['min']:.1f}  median={cc['median']:.1f}  "
              f"max={cc['max']:.1f}")
        print(f"\n  Paper sentence: \"Across all {cp['n']} synthetic instances, the "
              f"topology gap (L1cp->L3) ranged from {ca['min']:.1f} to {ca['max']:.1f} "
              f"EUR/MWh_demand (median {ca['median']:.1f} EUR/MWh), confirming that network topology "
              f"abstraction has a material effect on dispatch cost.\"")

    key_hl = "L1_vs_L2"
    if key_hl in stats:
        cp = stats[key_hl]["cost_gap_pct"]
        ca = stats[key_hl]["cost_gap_eur_per_mwh"]
        print(f"\n  [HEAT LOSS EFFECT L1->L2, n={cp['n']}]")
        print(f"  Cost gap [%]:       min={cp['min']:.2f}  p10={cp['p10']:.2f}  "
              f"median={cp['median']:.2f}  p90={cp['p90']:.2f}  max={cp['max']:.2f}")
        print(f"  Cost gap [EUR/MWh]: min={ca['min']:.2f}  p10={ca['p10']:.2f}  "
              f"median={ca['median']:.2f}  p90={ca['p90']:.2f}  max={ca['max']:.2f}")

    key_pd = "L2_vs_L3"
    if key_pd in stats:
        cp = stats[key_pd]["cost_gap_pct"]
        ca = stats[key_pd]["cost_gap_eur_per_mwh"]
        print(f"\n  [PRESSURE DROP EFFECT L2->L3, n={cp['n']}]")
        print(f"  Cost gap [%]:       min={cp['min']:.2f}  p10={cp['p10']:.2f}  "
              f"median={cp['median']:.2f}  p90={cp['p90']:.2f}  max={cp['max']:.2f}")
        print(f"  Cost gap [EUR/MWh]: min={ca['min']:.2f}  p10={ca['p10']:.2f}  "
              f"median={ca['median']:.2f}  p90={ca['p90']:.2f}  max={ca['max']:.2f}")
        if cp['n'] > 0 and ca['max'] < 0.5:
            print(f"  NOTE: pressure drop effect is small (<0.5 EUR/MWh) — "
                  f"consider if L3 adds meaningful insight over L2 for this network size.")

    key_phys = "L3_vs_L3plus"
    if key_phys in stats:
        cp = stats[key_phys]["cost_gap_pct"]
        ca = stats[key_phys]["cost_gap_eur_per_mwh"]
        print(f"\n  [PHYSICS GAP L3->L3+, n={cp['n']}]")
        print(f"  Cost gap [%]:       min={cp['min']:.3f}  p10={cp['p10']:.3f}  "
              f"median={cp['median']:.3f}  p90={cp['p90']:.3f}  max={cp['max']:.3f}")
        print(f"  Cost gap [EUR/MWh]: min={ca['min']:.4f}  median={ca['median']:.4f}  "
              f"p90={ca['p90']:.4f}  max={ca['max']:.4f}")
        print(f"\n  Paper sentence: \"Across all {cp['n']} synthetic instances, the "
              f"physics fidelity gap (L3->L3+) remained below {ca['max']:.2f} EUR/MWh_demand "
              f"(median {ca['median']:.4f} EUR/MWh), confirming near-equivalence of "
              f"the linearized and full-physics models.\"")

    # ── Save outputs ──────────────────────────────────────────────────────────
    gap_df = pd.DataFrame(gap_rows)
    gap_df.to_csv(OUT_DIR / "synth_gap_summary.csv", index=False)
    (OUT_DIR / "synth_gap_statistics.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False)
    )
    print(f"\n  Saved: synth_gap_summary.csv  synth_gap_statistics.json")


if __name__ == "__main__":
    main()
