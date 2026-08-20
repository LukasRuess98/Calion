"""
Fit statistics for the a-priori fidelity design rule  b = lambda/(1+lambda).

fidelity_rule.py computes R2/MAE/calibrated-R2 but only PRINTS them, leaving the
headline claim with no stored provenance. This tool recomputes them from the stored
results/v2/analysis/fidelity_rule.csv (current balanced-135 values: zero-param R2=0.87,
MAE 6.7 pts, calibrated R2=0.96, n=136)
-- using the IDENTICAL math as fidelity_rule.py (same dropna, same SST reference incl.
Memmingen, same lstsq calibration) -- and writes them to a CSV.

Pure post-processing. NO solve.

Output: results/v2/analysis/fidelity_rule_fit.csv
"""
import os

import numpy as np
import pandas as pd

A = "results/v2/analysis"


def main():
    df = pd.read_csv(f"{A}/fidelity_rule.csv")
    v = df.dropna(subset=["b_pred_pct", "b_meas_pct"]).copy()

    # zero-parameter (pure physics): b_pred vs b_meas, R2 wrt b_meas variance
    err = v["b_pred_pct"] - v["b_meas_pct"]
    ss = ((v["b_meas_pct"] - v["b_meas_pct"].mean()) ** 2).sum()
    r2 = 1 - (err ** 2).sum() / ss if ss else np.nan
    mae = float(err.abs().mean())
    rmse = float(np.sqrt((err ** 2).mean()))

    # calibrated: b = a * lambda/(1+lambda) + c   (c absorbs the ~const topology term)
    x = (v["lambda"] / (1 + v["lambda"])).to_numpy()
    Amat = np.column_stack([x, np.ones(len(x))])
    (a, c), *_ = np.linalg.lstsq(Amat, v["b_meas_pct"].to_numpy(), rcond=None)
    fit = Amat @ np.array([a, c])
    r2c = 1 - ((v["b_meas_pct"] - fit) ** 2).sum() / ss if ss else np.nan
    mae_c = float(np.abs(v["b_meas_pct"].to_numpy() - fit).mean())

    n_synth = int((v["net"] != "Memmingen").sum())
    mem = df[df.net == "Memmingen"]

    rows = [
        ("n_points_total", len(v)),
        ("n_synth", n_synth),
        ("includes_memmingen", int(len(mem) > 0)),
        ("r2_zero_param", round(float(r2), 4)),
        ("mae_pts_zero_param", round(mae, 3)),
        ("rmse_pts_zero_param", round(rmse, 3)),
        ("r2_calibrated", round(float(r2c), 4)),
        ("mae_pts_calibrated", round(mae_c, 3)),
        ("cal_slope_a", round(float(a), 4)),
        ("cal_intercept_c_pts", round(float(c), 4)),
        ("lambda_min", round(float(v["lambda"].min()), 4)),
        ("lambda_max", round(float(v["lambda"].max()), 4)),
    ]
    if len(mem):
        rows += [
            ("memmingen_lambda", round(float(mem["lambda"].iloc[0]), 4)),
            ("memmingen_b_pred_pct", round(float(mem["b_pred_pct"].iloc[0]), 3)),
            ("memmingen_b_meas_pct", round(float(mem["b_meas_pct"].iloc[0]), 3)),
        ]

    out = pd.DataFrame(rows, columns=["stat", "value"])
    os.makedirs(A, exist_ok=True)
    dst = f"{A}/fidelity_rule_fit.csv"
    out.to_csv(dst, index=False)
    print(out.to_string(index=False))
    print(f"\nwrote {dst}")


if __name__ == "__main__":
    main()
