"""
R1.6 zone-clustering sensitivity (Paper 1).

Reviewer R1.6 asks how sensitive the results are to the L2 zone aggregation. The paper's
L2 is ONE hand-tuned 7-zone partition of the 15-node L3 tree. This tool:

  1. Builds a faithful L3->L2 aggregator (verified to reproduce the hand-made Memmingen_L2.yaml).
  2. Emits ALTERNATIVE clusterings (coarser / finer / shifted 7-zone) + a NULL distribution of
     random contiguous partitions, as solvable L2 configs.
  3. (Downstream) each is solved at L2 physics; the spread of the L2 cost / L2->L1 gap across
     clusterings vs the null band answers R1.6 with data.

Aggregation rule (conserves total sum(U*L), preserves the tree):
  Root the L3 tree at j_1. Each L3 pipe (u->v, v = child/downstream node) is assigned to the
  zone of v. The aggregated pipe FEEDING zone Z carries sum(U*L) and sum(L) of every L3 pipe
  whose downstream node is in Z; U_rep = sum(U*L)/sum(L); DN_rep = max DN of those pipes; the
  parent zone is the zone of the upstream node of Z's entry edge(s) (must be unique -> tree-valid).
  Demand(Z) = union of member nodes' consumer columns; assets(Z) = union of member assets.

NOTE (data flag): L3 pipe j13->j15 has u_value_supply=1.31 (vs the hand L2's 0.28 assumption).
This tool uses the ACTUAL L3 value, so the regenerated zF_to_zG differs from the stored L2 on
that one pipe. All clusterings use the same consistent aggregator, so the sensitivity comparison
is valid; the stored-L2 parity check therefore matches 6/7 pipes exactly and flags this one.

Usage:
    python tools/r16_zone_clustering.py --verify           # parity vs hand-made L2
    python tools/r16_zone_clustering.py --emit --null 20   # write alt + null configs
"""
from __future__ import annotations

import argparse
import copy
import random
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WT = (ROOT / ".." / "paper1_faithful_c19d690").resolve()
CFG = WT / "configs" / "memmingen"
L3 = CFG / "Memmingen_L3_MILP.yaml"
L2 = CFG / "Memmingen_L2.yaml"
OUTDIR = CFG / "r16_clusterings"

# Original hand-made L2 partition (node index -> zone), for the parity check.
ORIG = {
    1: "A", 2: "B", 3: "B", 4: "C", 5: "C", 6: "D", 7: "D", 8: "D",
    9: "E", 10: "E", 11: "E", 12: "F", 13: "F", 14: "G", 15: "G",
}


def _load(p):
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _tree(l3):
    """Return (parent_edge_by_child, pipes) where pipes[(u,v)] = dict(U_s,U_r,L,DN)."""
    net = l3["network"]
    pipes = {}
    parent = {}  # child_node -> (parent_node, pipe_key)
    for pid, p in net["pipes"].items():
        u = int(p["from"].split("_")[1]); v = int(p["to"].split("_")[1])
        pipes[(u, v)] = {
            "U_s": float(p["u_value_supply_w_per_m_k"]),
            "U_r": float(p["u_value_return_w_per_m_k"]),
            "L": float(p["length_m"]),
            "DN": int(p["diameter_mm"]),
        }
        parent[v] = (u, (u, v))  # tree: v's parent is u
    return parent, pipes


def _node_consumers_assets(l3):
    net = l3["network"]
    cons, assets = {}, {}
    for nid, nd in net["nodes"].items():
        i = int(nid.split("_")[1])
        cons[i] = [c.get("column") for c in nd.get("consumers", [])]
        assets[i] = list(nd.get("assets", []))
    return cons, assets


def aggregate(partition, l3, template):
    """Build an L2-style config from a node->zone partition. Returns (cfg, diagnostics)."""
    parent, pipes = _tree(l3)
    cons, assets = _node_consumers_assets(l3)
    zones = sorted(set(partition.values()), key=lambda z: (len(z), z))
    znodes = {z: sorted(n for n, zz in partition.items() if zz == z) for z in zones}

    # feed pipe per zone: sum over pipes whose downstream node in Z
    feed = {}  # zone -> dict
    parent_zone = {}
    for (u, v), pd in pipes.items():
        zv = partition[v]
        zu = partition[u]
        f = feed.setdefault(zv, {"ULs": 0.0, "ULr": 0.0, "L": 0.0, "DN": 0, "parents": set()})
        f["ULs"] += pd["U_s"] * pd["L"]; f["ULr"] += pd["U_r"] * pd["L"]
        f["L"] += pd["L"]; f["DN"] = max(f["DN"], pd["DN"])
        if zu != zv:
            f["parents"].add(zu)      # this pipe is an entry edge into Z
    root_zone = partition[1]

    cfg = copy.deepcopy(template)
    net = cfg["network"]
    # --- nodes ---
    net["nodes"] = {}
    for z in zones:
        node = {}
        za = []
        for n in znodes[z]:
            za += [a for a in assets[n] if a not in za]
        if za:
            node["assets"] = za
        node["consumers"] = [{"column": col} for n in znodes[z] for col in cons[n]]
        net["nodes"][f"zone_{z}"] = node
    # --- pipes ---
    net["pipes"] = {}
    valid = True
    for z in zones:
        if z == root_zone:
            continue
        f = feed[z]
        if len(f["parents"]) != 1:
            valid = False
            parent_zone[z] = sorted(f["parents"])
            continue
        pz = next(iter(f["parents"]))
        parent_zone[z] = pz
        net["pipes"][f"z{pz}_to_z{z}"] = {
            "from": f"zone_{pz}", "to": f"zone_{z}",
            "length_m": round(f["L"]),
            "diameter_mm": f["DN"],
            "u_value_supply_w_per_m_k": round(f["ULs"] / f["L"], 4),
            "u_value_return_w_per_m_k": round(f["ULr"] / f["L"], 4),
        }
    cfg["scenario"]["name"] = "Memmingen L2 (clustering)"
    # total-U*L conservation: every L3 pipe's U*L must land on an aggregated feed pipe.
    # It is dropped only for pipes internal to the ROOT zone (no feed pipe), so conservation
    # holds iff the producer zone carries no internal pipes -> keep j_1 its own zone.
    ul_l3 = sum(pd["U_s"] * pd["L"] for pd in pipes.values())
    ul_agg = sum(p["u_value_supply_w_per_m_k"] * p["length_m"] for p in net["pipes"].values())
    conserves = abs(ul_agg - ul_l3) < 1.0
    diag = {"valid_tree": valid, "n_zones": len(zones), "parent_zone": parent_zone,
            "conserves_UL": conserves, "ul_l3": round(ul_l3, 1), "ul_agg": round(ul_agg, 1),
            "feed": {z: {"ULs": round(feed[z]["ULs"], 1), "L": feed[z]["L"]} for z in feed}}
    return cfg, diag


def verify():
    l3 = _load(L3); l2 = _load(L2)
    cfg, diag = aggregate(ORIG, l3, l2)
    print(f"[VERIFY] tree-valid={diag['valid_tree']}  n_zones={diag['n_zones']}")
    got = cfg["network"]["pipes"]; exp = l2["network"]["pipes"]
    # match by (from,to) zone pair regardless of key name
    def by_pair(pp):
        return {(v["from"], v["to"]): v for v in pp.values()}
    g, e = by_pair(got), by_pair(exp)
    print(f"[VERIFY] regenerated {len(g)} pipes vs stored {len(e)}")
    for pair in sorted(e):
        ge = g.get(pair)
        if not ge:
            print(f"   MISSING {pair}"); continue
        uls_g = ge["u_value_supply_w_per_m_k"] * ge["length_m"]
        uls_e = e[pair]["u_value_supply_w_per_m_k"] * e[pair]["length_m"]
        ok = abs(uls_g - uls_e) < 1.0 and ge["length_m"] == e[pair]["length_m"]
        flag = "OK " if ok else "DIFF"
        print(f"   {flag} {pair[0]}->{pair[1]}: L {ge['length_m']}/{e[pair]['length_m']} "
              f"sumUL_s {uls_g:.1f}/{uls_e:.1f} DN {ge['diameter_mm']}/{e[pair]['diameter_mm']}")


# ---- alternative clusterings (tree-valid; producer j_1 ALWAYS its own zone so total
#      U*L is conserved, matching the paper's L2 which resolves the plant) ----
ALTS = {
    "coarse4": {1: "P", 2: "1", 3: "1", 4: "1", 5: "1", 6: "1", 7: "1", 8: "1",
                9: "2", 10: "2", 11: "2", 12: "3", 13: "3", 14: "3", 15: "3"},
    "fine10":  {1: "A", 2: "B", 3: "C", 4: "D", 5: "D", 6: "E", 7: "E", 8: "E",
                9: "F", 10: "G", 11: "G", 12: "H", 13: "I", 14: "J", 15: "J"},
    "shift7":  {1: "A", 2: "B", 3: "B", 4: "C", 5: "C", 6: "C", 7: "D", 8: "D",
                9: "E", 10: "E", 11: "F", 12: "F", 13: "F", 14: "G", 15: "G"},
}


def _random_contiguous(l3, k, rng):
    """Cut k-1 tree edges -> k connected components. The producer edge (j_1->j_2) is ALWAYS
    cut so j_1 is its own zone (total-U*L conservation); the remaining k-2 cuts are random."""
    parent, pipes = _tree(l3)
    edges = list(pipes.keys())
    j1_edges = [(u, v) for (u, v) in edges if u == 1]   # producer's outgoing edge(s)
    others = [e for e in edges if e not in j1_edges]
    cut = set(j1_edges) | set(rng.sample(others, max(k - 1 - len(j1_edges), 0)))
    # union-find over nodes using non-cut edges
    par = {i: i for i in range(1, 16)}
    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for (u, v) in edges:
        if (u, v) not in cut:
            par[find(u)] = find(v)
    comp = {}
    for i in range(1, 16):
        comp.setdefault(find(i), []).append(i)
    labels = {r: chr(65 + idx) for idx, r in enumerate(comp)}
    return {i: labels[find(i)] for i in range(1, 16)}


def emit(n_null):
    l3 = _load(L3); l2 = _load(L2)
    # start clean so no stale (non-conserving) configs linger
    OUTDIR.mkdir(exist_ok=True)
    for old in OUTDIR.glob("L2_*.yaml"):
        old.unlink()
    written, skipped = [], []

    def _write(name, part, scen):
        cfg, diag = aggregate(part, l3, l2)
        if not diag["valid_tree"]:
            skipped.append(f"{name} (not tree-valid: {diag['parent_zone']})"); return False
        if not diag["conserves_UL"]:
            skipped.append(f"{name} (U*L {diag['ul_agg']}!={diag['ul_l3']})"); return False
        cfg["scenario"]["name"] = scen
        (OUTDIR / f"{name}.yaml").write_text(
            yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        written.append(f"{name} ({diag['n_zones']} zones, U*L={diag['ul_agg']})")
        return True

    # reference = the ORIGINAL partition through the SAME conserving aggregator (apples-to-apples)
    _write("L2_orig", ORIG, "Memmingen L2 orig (conserving)")
    for name, part in ALTS.items():
        _write(f"L2_alt_{name}", part, f"Memmingen L2 alt {name}")
    rng = random.Random(1234)
    made = 0
    for i in range(n_null):
        if _write(f"L2_null_{i:02d}", _random_contiguous(l3, 7, rng), f"Memmingen L2 null {i:02d}"):
            made += 1
    print(f"[EMIT] wrote {len(written)} configs (1 orig + {len(ALTS)} alt + {made} null) to {OUTDIR}/")
    for w in written:
        print("   +", w)
    for s in skipped:
        print("   [SKIP]", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--null", type=int, default=20)
    a = ap.parse_args()
    if a.verify:
        verify()
    if a.emit:
        emit(a.null)
    if not (a.verify or a.emit):
        verify()


if __name__ == "__main__":
    main()
