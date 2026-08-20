"""
Exact loss x topology decomposition from the LIVE defensible-U runs (incl. the newly
re-solved T0P0). The 2x2 factorial (topology on/off) x (loss on/off):

    CP  = T0P0        (1 point, no loss)
    CP+L= T0P1a       (1 point, + aggregate loss)   -> isolates LOSS
    ND0 = T2P0        (nodes,   no loss)             -> isolates TOPOLOGY
    L1  = T2P1_defU   (nodes,   + trunk loss)        -> both

Additive identity (exact by construction; interaction is the residual):
    total    = cost(L1)  - cost(CP)
    loss_main= cost(CP+L)- cost(CP)
    topo_main= cost(ND0) - cost(CP)
    interaction = total - loss_main - topo_main
Closure residual (total - [loss+topo+interaction]) MUST be 0 to machine precision;
we print it to show the identity is exact and not fitted. Economic cost basis
(calion conventions), so no penalty-scaffolding contamination.

Output: results/v2/analysis/decomposition_live.csv
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import evaluator as E  # noqa: E402

OUT = "../paper1_faithful_c19d690/output/paper1_v2"
RUNS = {"CP": f"{OUT}/T0P0", "CP+L": f"{OUT}/T0P1a",
        "ND0": f"{OUT}/T2P0", "L1": f"{OUT}/T2P1_defU"}


def econ(rundir):
    return E._econ_cost_from_run(E.load_run(rundir))["econ_cost_eur"]


def main():
    c = {k: econ(v) for k, v in RUNS.items()}
    total = c["L1"] - c["CP"]
    loss_main = c["CP+L"] - c["CP"]
    topo_main = c["ND0"] - c["CP"]
    interaction = total - loss_main - topo_main
    residual = total - (loss_main + topo_main + interaction)   # == 0 by construction

    rows = [
        {"term": "cost_CP", "eur": c["CP"], "pct_of_total": None},
        {"term": "cost_CP+L", "eur": c["CP+L"], "pct_of_total": None},
        {"term": "cost_ND0", "eur": c["ND0"], "pct_of_total": None},
        {"term": "cost_L1", "eur": c["L1"], "pct_of_total": None},
        {"term": "total", "eur": total, "pct_of_total": 100.0},
        {"term": "loss_main", "eur": loss_main, "pct_of_total": 100 * loss_main / total},
        {"term": "topo_main", "eur": topo_main, "pct_of_total": 100 * topo_main / total},
        {"term": "interaction", "eur": interaction, "pct_of_total": 100 * interaction / total},
        {"term": "closure_residual", "eur": residual,
         "pct_of_total": 100 * residual / total},
    ]
    df = pd.DataFrame(rows)
    os.makedirs("results/v2/analysis", exist_ok=True)
    df.to_csv("results/v2/analysis/decomposition_live.csv", index=False)

    print("=== EXACT decomposition (live defensible-U, economic cost) ===")
    for r in rows:
        p = "" if r["pct_of_total"] is None else f"{r['pct_of_total']:9.4f}%"
        print(f"  {r['term']:18s} {r['eur']:14.4f} EUR   {p}")
    print(f"\n  total (of L1 econ)   {100*total/c['L1']:.4f}% ")
    print(f"  CLOSURE RESIDUAL     {residual:.3e} EUR  ({100*residual/total:.2e}% of total)"
          f"  -> exact identity, not fitted")
    print("\nwrote results/v2/analysis/decomposition_live.csv")


if __name__ == "__main__":
    main()
