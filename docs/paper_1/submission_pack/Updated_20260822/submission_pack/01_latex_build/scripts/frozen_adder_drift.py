"""
Frozen-adder DRIFT analysis (Paper 1 revision, the "DECIDER" load-bearing result).

Question the reviewer put to us: the copperplate-with-loss control (CP+L / T0P1) supplies
the copperplate with an *exogenous, calibrated* aggregate loss. If a single frozen loss
adder transferred across networks and operating regimes, then CP+L would be both low-bias
AND low-regret, and the whole node-resolved fidelity ladder would be unnecessary. The
counter-argument that makes spatial resolution NECESSARY is that the adder does NOT
transfer: a coefficient calibrated on one configuration mis-provisions loss on another.

This script quantifies that drift with ZERO new solves, from the already-computed
synthetic factorial decomposition. `total_pct` is the total cost gap z(T2P1)-z(T0P0) as a
fraction of cost, and loss is ~100 % of it (see synth_factorial_decomposition), so
`total_pct` is the loss burden b each network actually carries — precisely the quantity a
copperplate loss adder must reproduce. A frozen adder calibrated to reproduce b_ref, when
transferred to a network whose true burden is b_tgt, mis-provisions by (b_ref - b_tgt)
percentage points of cost. Under-provisioning (b_ref < b_tgt) is the dangerous direction:
the copperplate generates too little, forcing expensive real-time top-up or unmet demand.

Outputs:
  results/v2/analysis/frozen_adder_drift.csv   (per reference-choice transfer error stats)
  console: the headline drift numbers for the manuscript / response letter.
"""
import os
import re

import numpy as np
import pandas as pd

SRC = "results/v2/analysis/synth_factorial_decomposition.csv"
OUT = "results/v2/analysis/frozen_adder_drift.csv"

PAT = re.compile(r"synth_n(?P<n>\d+)_L(?P<L>[\d p]+?)km_hi(?P<hi>[\dp]+)_s(?P<s>\d+)h")


def parse(net):
    m = PAT.match(net)
    if not m:
        return None
    L = float(m.group("L").replace("p", ".").replace(" ", ""))
    hi = float(m.group("hi").replace("p", "."))
    return dict(n=int(m.group("n")), L_km=L, hi=hi, s_h=int(m.group("s")))


def main():
    df = pd.read_csv(SRC)
    meta = df["net"].map(parse).apply(pd.Series)
    df = pd.concat([df, meta], axis=1)
    df["b"] = df["total_pct"]            # loss burden [% of cost], loss ~100% of total

    print(f"n_nets={len(df)}  loss-burden b: min={df.b.min():.1f}%  "
          f"median={df.b.median():.1f}%  max={df.b.max():.1f}%  "
          f"span={df.b.max()-df.b.min():.1f} pts")

    # --- (1) GLOBAL drift: freeze the adder on each net, transfer to all others -------
    rows = []
    b = df["b"].to_numpy()
    for i, ref in df.iterrows():
        err = b[i] - b                    # signed transfer error (ref minus target)
        others = np.delete(err, i)
        rows.append({
            "ref_net": ref["net"], "ref_L_km": ref["L_km"], "ref_b_pct": ref["b"],
            "mean_abs_drift_pts": np.mean(np.abs(others)),
            "max_abs_drift_pts": np.max(np.abs(others)),
            "worst_underprov_pts": -np.min(others),   # most the ref under-provisions
        })
    drift = pd.DataFrame(rows).sort_values("mean_abs_drift_pts")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    drift.to_csv(OUT, index=False)

    best = drift.iloc[0]                   # the *most transferable* single adder
    print("\n--- GLOBAL: even the single most-transferable frozen adder ---")
    print(f"  calibrated on {best.ref_net} (b={best.ref_b_pct:.1f}%): "
          f"mean |drift|={best.mean_abs_drift_pts:.1f} pts, "
          f"max |drift|={best.max_abs_drift_pts:.1f} pts of cost")
    print(f"  (median net's adder: mean |drift|="
          f"{drift['mean_abs_drift_pts'].median():.1f} pts)")

    # --- (2) PIPE-LENGTH drift at otherwise-fixed design (the cleanest transfer) ------
    # Hold (n, hi, s) fixed, vary only L: adder calibrated at one L, applied at another.
    grp = df.groupby(["n", "hi", "s_h"])
    length_rows = []
    for key, g in grp:
        if g["L_km"].nunique() < 2:
            continue
        g = g.sort_values("L_km")
        lo, hi = g.iloc[0], g.iloc[-1]
        length_rows.append({
            "n": key[0], "hi": key[1], "s_h": key[2],
            "L_lo_km": lo["L_km"], "b_lo_pct": lo["b"],
            "L_hi_km": hi["L_km"], "b_hi_pct": hi["b"],
            "drift_pts": hi["b"] - lo["b"],
            "rel_underprov_pct": 100.0 * (hi["b"] - lo["b"]) / hi["b"],
        })
    ldf = pd.DataFrame(length_rows)
    if len(ldf):
        print("\n--- PIPE-LENGTH: adder calibrated at short L, applied at long L ---")
        for _, r in ldf.iterrows():
            print(f"  n{int(r.n)} hi{r.hi} s{int(r.s_h)}h: "
                  f"{r.L_lo_km:g}km(b={r.b_lo_pct:.1f}%) -> {r.L_hi_km:g}km(b={r.b_hi_pct:.1f}%)"
                  f"  under-provisions {r.rel_underprov_pct:.0f}% of the true loss")

    # --- (3) REGIME drift at FIXED pipe length (kills "adder transfers within a net") --
    # At a fixed L, vary storage/heterogeneity: the adder still moves.
    fixedL = df[df["L_km"] == 15.0]
    if len(fixedL) > 1:
        span = fixedL["b"].max() - fixedL["b"].min()
        print(f"\n--- REGIME (fixed L=15km, vary n/hi/storage): b in "
              f"[{fixedL['b'].min():.1f}, {fixedL['b'].max():.1f}]% -> "
              f"drift {span:.1f} pts with pipe length held constant")

    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
