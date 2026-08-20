"""
Out-of-sample prediction (Paper 1, R2.5 / novelty claim 5). An a-priori estimator of the
copperplate-to-baseline cost gap (the loss burden) from observable network properties, fitted on
the shorter-pipe synthetic networks and tested on the held-out LONGER ones -- an extrapolation
beyond the fitted pipe-length range, not interpolation. If it predicts the held-out gap without
refitting, the bias is a-priori knowable from network properties; we report the outcome as given.

Target: total_pct (loss burden, % of cost). Features: pipe length (and log), node count, demand
heterogeneity, storage horizon. Ordinary least squares (numpy), no tuning.

Output: results/v2/analysis/prediction_oos.csv  + console summary.
"""
import os
import re

import numpy as np
import pandas as pd

A = "results/v2/analysis"
SRC = f"{A}/synth_factorial_decomposition.csv"


def parse(net):
    m = re.match(r"synth_n(\d+)_L([\dp]+?)km_hi([\dp]+)_s(\d+)h", net)
    if not m:
        return None
    return dict(n=int(m.group(1)), L=float(m.group(2).replace("p", ".")),
                hi=float(m.group(3).replace("p", ".")), s=int(m.group(4)))


def main():
    df = pd.read_csv(SRC)
    meta = df["net"].map(parse).apply(pd.Series)
    df = pd.concat([df, meta], axis=1).dropna(subset=["L"])
    df["y"] = df["total_pct"]

    def feats(d):
        return np.column_stack([np.ones(len(d)), d["L"], np.log1p(d["L"]),
                                d["n"], d["hi"], d["s"]])

    # split by pipe length: train on the fitted range (<=15 km), test on the longer, held-out nets
    train = df[df["L"] <= 15.0]
    test = df[df["L"] > 15.0]
    # the loss burden is bounded in (0,100), so fit on the logit scale (respects saturation)
    # and back-transform; this is the natural specification for a share.
    def logit(y):
        p = np.clip(y / 100.0, 1e-4, 1 - 1e-4)
        return np.log(p / (1 - p))
    def inv_logit(z):
        return 100.0 / (1 + np.exp(-z))
    beta, *_ = np.linalg.lstsq(feats(train), logit(train["y"].to_numpy()), rcond=None)

    def r2(y, yh):
        ss = ((y - y.mean()) ** 2).sum()
        return 1 - ((y - yh) ** 2).sum() / ss if ss else np.nan

    tr_pred = inv_logit(feats(train) @ beta)
    te_pred = inv_logit(feats(test) @ beta)
    tr_r2 = r2(train["y"].to_numpy(), tr_pred)
    te_mape = float(np.mean(np.abs(te_pred - test["y"]) / test["y"]) * 100)
    te_mae = float(np.mean(np.abs(te_pred - test["y"])))

    out = test[["net", "L", "n", "hi", "s", "y"]].copy()
    out["y_pred"] = te_pred
    out["abs_err_pts"] = np.abs(te_pred - test["y"])
    os.makedirs(A, exist_ok=True)
    out.to_csv(f"{A}/prediction_oos.csv", index=False)

    # a small summary row set the table can read (train/test split sizes + metrics)
    summ = pd.DataFrame([
        {"metric": "n_train (L<=15km)", "value": len(train)},
        {"metric": "n_test held-out (L>15km)", "value": len(test)},
        {"metric": "train R2", "value": round(tr_r2, 3)},
        {"metric": "held-out MAPE %", "value": round(te_mape, 1)},
        {"metric": "held-out MAE (pts of cost)", "value": round(te_mae, 1)},
    ])
    summ.to_csv(f"{A}/prediction_oos_summary.csv", index=False)

    print(f"train n={len(train)} (L<=15km), R2={tr_r2:.3f}")
    print(f"held-out n={len(test)} (L in {sorted(test['L'].unique())} km): "
          f"MAPE={te_mape:.1f}%, MAE={te_mae:.1f} pts")
    print(out[["net", "L", "y", "y_pred", "abs_err_pts"]].to_string(index=False))
    print("wrote prediction_oos.csv + prediction_oos_summary.csv")


if __name__ == "__main__":
    main()
