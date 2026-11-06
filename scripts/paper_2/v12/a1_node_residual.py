"""v12 A1: per-node heat residual from model variables, to localise the system-balance offset R(t).

res_n(t) = gen_n - dump_n - (Qc-Qd)_n + sum_in Q_consumer - sum_out Q_delivered - demand_n   [primary node: also - all pipe losses]
usage: python a1_node_residual.py <run_dir> <topo_yaml> <primary_node> <asset_node_map_json>
"""
import json, sys
import numpy as np, pandas as pd, yaml

run, topo, primary, amap = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4])
v = json.load(open(f"{run}/full_solution_dump.json"))["vars"]
nodes = pd.read_parquet(f"{run}/nodes_state_hourly.parquet")
T = 8760
def s(name):
    a = np.zeros(T); d = v.get(name)
    if isinstance(d, dict):
        for k, x in d.items(): a[int(k) - 1] = float(x or 0)
    return a
pipes = yaml.safe_load(open(topo))["network"]["pipes"] if "network" in yaml.safe_load(open(topo)) else yaml.safe_load(open(topo))["pipes"]
res = {}
dem = {n: np.nan_to_num(g.sort_values("timestamp")["Q_demand_mw"].to_numpy()) for n, g in nodes.groupby("node_id")}
allnodes = set(dem) | {p["from"] for p in pipes.values()} | {p["to"] for p in pipes.values()}
loss_all = sum(s(f"{pid.upper()}_Q_loss_supply") + s(f"{pid.upper()}_Q_loss_return") for pid in pipes)
for n in sorted(allnodes):
    r = np.zeros(T)
    for a, an in amap.items():
        if an == n: r += s(a)
    r -= s(f"Q_dump_{n}")
    for pid, p in pipes.items():
        P = pid.upper()
        if p.get("bidirectional") or f"{P}_flow_dir" in v:
            # signed transfer from->to: sign(m_dot) * |Q_delivered| (same coefficient as _make_signed_q_fn)
            q = np.sign(s(f"{P}_m_dot")) * np.abs(s(f"{P}_Q_delivered"))
            if p["to"] == n: r += q
            if p["from"] == n: r -= q
            continue
        if p["to"] == n: r += s(f"{P}_Q_consumer")
        if p["from"] == n: r -= s(f"{P}_Q_delivered")
    r -= dem.get(n, np.zeros(T))
    if n == primary: r -= loss_all
    res[n] = r
tot = sum(res.values())
print(f"TOTAL sum {tot.sum():.1f} MWh  min {tot.min():.3f}  max {tot.max():.3f}")
for n, r in sorted(res.items(), key=lambda x: -abs(x[1].sum())):
    if abs(r).max() > 1e-4:
        print(f"{n:30s} sum {r.sum():10.2f} MWh  min {r.min():8.3f}  max {r.max():8.3f}  p50 {np.median(r):7.3f}")
