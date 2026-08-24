"""
Decompose the total-demand MAPE by LOAD BAND (demand-side analogue of flow_mape_by_band.py).

validation kpis.json reports a single aggregate Q_demand_total_MAPE_pct = 29.07 %. As with the
flow side, a bare aggregate invites reading a large number in isolation; the decomposition shows
the error is concentrated at low load (small denominators), while the high-load hours that drive
cost are matched far better. The annual delivered-energy match (1.23 %) is the measure the cost
conclusions rest on.

Mirrors validation_runner KPI 5 exactly (measured Q_demand_MWth vs simulated Q_demand_total_MW,
filter m_q > 0.01, MAPE = mean(|s-m|/m)*100) so the aggregate reproduces the shipped 29.07 %.
Pure post-processing (no solve). Output aggregated per band (NDA-safe).

Output: results/v2/analysis/demand_mape_by_band.csv  (+ prints, and asserts aggregate ~= 29.07 %)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import validation_runner as V  # noqa: E402

DATA = ROOT / "data" / "Import_Data_Memmingen_epronet.xlsx"
SIM = ROOT / "output" / "paper_runs" / "legacy" / "dispatch_hourly.csv"   # validation baseline
A = ROOT / "results" / "v2" / "analysis"


def main():
    hist = V.load_historical(DATA)
    meas = V.aggregate_source_measurements(hist)
    m_q = meas.get("Q_demand_MWth")

    sim = pd.read_csv(SIM, parse_dates=[0], index_col=0)
    s_q = sim["Q_demand_total_MW"]

    # replicate validation_runner KPI 5 exactly
    idx = m_q.dropna().index.intersection(s_q.dropna().index)
    m_qv, s_qv = m_q.loc[idx], s_q.loc[idx]
    valid = m_qv > 0.01
    m_qv, s_qv = m_qv[valid], s_qv[valid]
    ape = (s_qv - m_qv).abs() / m_qv * 100.0

    agg = float(ape.mean())
    print(f"aggregate demand MAPE = {agg:.2f} %  (shipped 29.07 %), n={len(ape)}")
    assert abs(agg - 29.07) < 0.5, f"aggregate {agg} does not reproduce shipped 29.07 %"

    # --- load bands by fraction of peak measured demand ---
    peak = float(m_qv.max())
    edges = [0.0, 0.25, 0.50, 0.75, 1.01]
    labels = ["<25 % peak", "25-50 %", "50-75 %", ">75 % peak"]
    frac = m_qv / peak
    rows = []
    for lab, lo, hi in zip(labels, edges[:-1], edges[1:]):
        mask = (frac >= lo) & (frac < hi)
        if mask.sum() == 0:
            continue
        # small absolute error at low load is why the annual energy still closes to 1.2 %.
        abs_err = (s_qv[mask] - m_qv[mask]).abs()
        rows.append({"load_band": lab, "n_hours": int(mask.sum()),
                     "share_of_hours_pct": round(100 * mask.mean(), 1),
                     "demand_MAPE_pct": round(float(ape[mask].mean()), 1),
                     "mean_abs_err_MW": round(float(abs_err.mean()), 3),
                     "mean_measured_MW": round(float(m_qv[mask].mean()), 3)})
    df = pd.DataFrame(rows)
    A.mkdir(parents=True, exist_ok=True)
    df.to_csv(A / "demand_mape_by_band.csv", index=False)
    print(df.to_string(index=False))
    print(f"\nwrote {A / 'demand_mape_by_band.csv'}")


if __name__ == "__main__":
    main()
