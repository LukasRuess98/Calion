"""
Synthetic-factorial decomposition reader (rebuilds the previously-missing producer of
synth_factorial_decomposition.csv). For each synth net with all three cells solved
(T0P0 copperplate-no-loss, T2P0 nodes-no-loss, T2P1 nodes+loss), compute the economic-cost
2-way decomposition:

    total      = z(T2P1) - z(T0P0)
    topo_main  = z(T2P0) - z(T0P0)
    loss(+int) = total - topo_main
    total_pct        = 100 * total / z(T2P1)          # loss burden as % of full cost
    topo_pct_of_total= 100 * topo_main / total
    loss_pct_of_total= 100 - topo_pct_of_total

(There is no CP+L cell on the synth nets, so loss and interaction are lumped; loss ~100%
of the gap in every net, so this is fine.) Economic-cost basis (calion conventions).

Verified to reproduce the legacy synth_factorial_decomposition.csv exactly on the loose runs.

Output: results/v2/analysis/synth_factorial_decomposition.csv
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import evaluator as E  # noqa: E402

SYNTH = "../paper1_faithful_c19d690/output/paper1_v2/synth_decomp"


def econ(rundir):
    return E._econ_cost_from_run(E.load_run(rundir))["econ_cost_eur"]


def main():
    nets = sorted({os.path.basename(d).rsplit("_", 1)[0]
                   for d in os.listdir(SYNTH)
                   if os.path.isdir(os.path.join(SYNTH, d)) and d.endswith("_T2P1")})
    rows, skipped = [], []
    for net in nets:
        try:
            z = {c: econ(f"{SYNTH}/{net}_{c}") for c in ("T0P0", "T2P0", "T2P1")}
        except Exception as e:  # noqa: BLE001
            skipped.append((net, str(e)))
            continue
        total = z["T2P1"] - z["T0P0"]
        topo = z["T2P0"] - z["T0P0"]
        if abs(total) < 1e-9:
            skipped.append((net, "total~0"))
            continue
        rows.append({"net": net,
                     "total_pct": 100 * total / z["T2P1"],
                     "topo_pct_of_total": 100 * topo / total,
                     "loss_pct_of_total": 100 * (total - topo) / total})
    df = pd.DataFrame(rows).sort_values("net")
    os.makedirs("results/v2/analysis", exist_ok=True)
    df.to_csv("results/v2/analysis/synth_factorial_decomposition.csv", index=False)
    print(f"nets={len(df)}  skipped={len(skipped)}")
    for n, e in skipped:
        print(f"  SKIP {n}: {e}")
    print(f"loss_pct_of_total: min={df.loss_pct_of_total.min():.2f}  "
          f"median={df.loss_pct_of_total.median():.2f}  max={df.loss_pct_of_total.max():.2f}")
    print(f"topo_pct_of_total: min={df.topo_pct_of_total.min():.3f}  "
          f"max={df.topo_pct_of_total.max():.3f}  |max|={df.topo_pct_of_total.abs().max():.3f}")
    print(f"total_pct (loss burden): min={df.total_pct.min():.2f}  max={df.total_pct.max():.2f}")
    print("wrote results/v2/analysis/synth_factorial_decomposition.csv")


if __name__ == "__main__":
    main()
