"""Read-only diagnostic (2026-09-20): reproduce the primary-producer heat-balance
constraint of ``constraint_builder.add_per_node_heat_balance`` from exported results.

    supply(primary) == dump + charge + return_loss
                       + sum_out [ Q_delivered - sum(ht_out of every node downstream) ]

and compare it with the PHYSICAL net pipe outflow of the primary node.  No solve, no
model change: it only reads pipes.csv, pipe_state_hourly.parquet, node_heat_audit.json,
dispatch_per_asset.csv, dispatch_hourly.csv of a finished run directory.

Finding: Q_delivered on a pipe feeding a node with local generation is already NET of that
generation (node mass balance ``m_in + m_gen == m_out + m_dem``), so subtracting the
downstream ht_out again double-counts it (and for storage nodes only the discharge is
subtracted, never the charge).

Usage:  PYTHONIOENCODING=utf-8 python scripts/paper_2/diag_primary_balance.py <run_dir> [primary_node] [bidi_pipe ...]
        e.g. ... output/paper2_runs/BC-SB j_hkw hkw_to_ost
"""
import csv
import json
import sys

import pandas as pd


def annual_reproduction(run_dir, primary, bidi=()):
    pipes = {r["pipe_id"]: (r["from"], r["to"]) for r in csv.DictReader(open(run_dir + "/pipes.csv"))}
    p = pd.read_parquet(run_dir + "/pipe_state_hourly.parquet")
    p = p[~p.pipe_id.str.endswith(("_P", "_Q"))]
    Q = p.groupby("pipe_id").Q_pipe_MW.sum() / 1000.0          # |Q| in GWh (sign lost in export)
    aud = json.load(open(run_dir + "/node_heat_audit.json"))["per_node"]
    gen = {k: v["ht_out_MWh"] / 1000.0 for k, v in aud.items()}
    chg = {k: v["ht_in_MWh"] / 1000.0 for k, v in aud.items()}

    def signed(pid):
        o = p[p.pipe_id == pid]
        return float((o.Q_pipe_MW * o.m_dot_kg_s.apply(lambda x: 1 if x >= 0 else -1)).sum()) / 1000.0

    def subtree(n, seen):
        if n in seen:
            return 0.0
        seen.add(n)
        s = gen.get(n, 0.0)
        for pid, (f, t) in pipes.items():
            if f == n and t not in seen:
                s += subtree(t, seen)
        return s

    print(f"=== {run_dir}  primary={primary}  supply(ht_out)={gen.get(primary, 0.0):.1f} GWh")
    rhs, sub_total, phys = 0.0, 0.0, 0.0
    for pid, (f, t) in pipes.items():
        if f != primary:
            continue
        if pid in bidi:
            q = signed(pid)
            rhs += q
            phys += q
            print(f"  {pid:26s} bidirectional signed Q = {q:8.1f}")
            continue
        g = subtree(t, {primary})
        rhs += Q[pid] - g
        sub_total += g
        phys += Q[pid]
        print(f"  {pid:26s} Q_delivered = {Q[pid]:8.1f}  - downstream ht_out {g:8.1f}  = {Q[pid] - g:8.1f}")
    print(f"  constraint RHS (before dump/return_loss) = {rhs:.1f}  -> implied dump+return_loss = {gen.get(primary, 0.0) - rhs:.1f}")
    print(f"  PHYSICAL net pipe outflow at primary     = {phys:.1f}  vs asset injection {gen.get(primary, 0.0):.1f}"
          f"  -> unexplained {phys - gen.get(primary, 0.0):.1f} GWh")
    print(f"  downstream ht_out subtracted a 2nd time  = {sub_total:.1f} GWh;  charge (ht_in) by node: "
          f"{ {k: round(v, 1) for k, v in chg.items() if v} }")


if __name__ == "__main__":
    run = sys.argv[1]
    prim = sys.argv[2] if len(sys.argv) > 2 else "j_hkw"
    annual_reproduction(run, prim, tuple(sys.argv[3:]))
