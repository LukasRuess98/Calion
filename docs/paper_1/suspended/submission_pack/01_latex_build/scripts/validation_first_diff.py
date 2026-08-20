"""
First-difference validation metric (R2.4 robustness). A level MAPE can be inflated by small
low-load denominators (see flow_mape_by_band.py) while the model still tracks the DYNAMICS. The
first-difference metric tests exactly that: does the simulated series reproduce the hour-to-hour
CHANGES of the measurement? We report the Pearson correlation of Δx(t)=x(t)-x(t-1) between measured
and simulated source flow (and, as a sanity check, demand). High first-difference correlation with a
large level MAPE means the disagreement is a slow offset, not a failure to track operation.

Pure post-processing (no solve). Output: results/v2/analysis/validation_first_diff.csv (NDA-safe).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import validation_runner as V  # noqa: E402

DATA = ROOT / "data" / "Import_Data_Memmingen_epronet.xlsx"
SIM = ROOT / "output" / "paper_runs" / "legacy" / "dispatch_hourly.csv"
A = ROOT / "results" / "v2" / "analysis"


def _corrs(m, s):
    """Level correlation, and first-difference correlation at hourly and daily resolution.
    Hourly Δ is dominated by 15-min metering noise (report daily for the dynamics)."""
    idx = m.dropna().index.intersection(s.dropna().index)
    m, s = m.loc[idx], s.loc[idx]
    lvl = float(np.corrcoef(m, s)[0, 1])
    fdh = float(np.corrcoef(m.diff().dropna(), s.diff().dropna())[0, 1])
    md, sd = m.resample("D").mean(), s.resample("D").mean()
    j = md.dropna().index.intersection(sd.dropna().index)
    fdd = float(np.corrcoef(md.loc[j].diff().dropna(), sd.loc[j].diff().dropna())[0, 1])
    return lvl, fdd, fdh, len(idx)


def main():
    hist = V.load_historical(DATA)
    meas = V.aggregate_source_measurements(hist)
    sim = pd.read_csv(SIM, parse_dates=[0], index_col=0)

    t_ret = meas.get("T_return_source_C")
    dt = max(float((86.5 - t_ret).dropna().mean()), 5.0) if t_ret is not None else 22.0
    s_flow = sim["Q_demand_total_MW"] * 3.6e6 / (977.0 * 4.19 * dt)

    rows = []
    for label, m, s in [("total demand (MW)", meas.get("Q_demand_MWth"), sim["Q_demand_total_MW"]),
                        ("source flow (m3/h)", meas["flow_source_m3h"], s_flow)]:
        if m is None:
            continue
        lvl, fdd, fdh, n = _corrs(m, s)
        rows.append({"quantity": label, "level_corr": round(lvl, 3),
                     "first_diff_daily_corr": round(fdd, 3),
                     "first_diff_hourly_corr": round(fdh, 3), "n": n})
    df = pd.DataFrame(rows)
    A.mkdir(parents=True, exist_ok=True)
    df.to_csv(A / "validation_first_diff.csv", index=False)
    print(df.to_string(index=False))
    print(f"\nwrote {A / 'validation_first_diff.csv'}")


if __name__ == "__main__":
    main()
