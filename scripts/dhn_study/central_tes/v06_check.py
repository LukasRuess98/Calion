"""Check of the low correlation at V06 in the holdout validation (reviewer question).

Hypothesis: V06 is the controlled worst point (the GCHP pumps hold V06 at ≈ 1.2 bar), so its measured Δp varies little
and a low correlation is expected; RMSE and bias are the meaningful metrics.

    python -m scripts.dhn_study.central_tes.v06_check
Output: results/central_tes/v06_check/{v06_stats.csv, v06_metrics.csv}
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import daten
from .. import netzmodell as nm
from ..run_netzmodell import KALIBRIERUNG_REPO, aufteilung, lade_kalibrierung
from . import config as C

STATIONS = ["V06", "V22", "V15", "V03"]


def main(variant: str = "A"):
    cfg = C.load()
    out = C.root() / cfg["paths"]["results"] / "v06_check"
    out.mkdir(parents=True, exist_ok=True)
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    ta = daten.lade_aussentemperatur()[0].reindex(m.index)
    nz = nm.netz()
    f = nm.randbedingungen(m, e, nz)
    kal = lade_kalibrierung(KALIBRIERUNG_REPO / variant, nz)
    sim = nm.simuliere(nz, f, kal["K"], kal["versatz"].to_dict(), kal["gewichte"], kal["grundlast"])
    hold, _ = aufteilung(f, ta)
    last = e["verbund"].reindex(f.index).to_numpy()
    hoch = hold & (last >= np.nanquantile(last[hold], 0.9))
    sets = {"holdout top load decile": hoch, "all hours 2025": np.ones(len(f.index), bool)}
    stats, mets = [], []
    for name, mask in sets.items():
        for st in STATIONS:
            y, s = f.ziele[st].to_numpy(), sim[st].to_numpy()
            ok = mask & np.isfinite(y) & np.isfinite(s)
            yy, ss = y[ok], s[ok]
            err = ss - yy
            row = {"set": name, "station": st, "n": int(ok.sum()),
                   "meas_mean": yy.mean(), "meas_sd": yy.std(ddof=1), "meas_p5": np.quantile(yy, 0.05),
                   "meas_p95": np.quantile(yy, 0.95), "meas_min": yy.min(), "meas_max": yy.max(),
                   "model_mean": ss.mean(), "model_sd": ss.std(ddof=1)}
            if st == "V06":
                row["share_within_0.1_of_1.2"] = float(np.mean(np.abs(yy - 1.2) <= 0.1))
            stats.append(row)
            mets.append({"set": name, "station": st, "n": int(ok.sum()), "r": float(np.corrcoef(ss, yy)[0, 1]),
                         "RMSE": float(np.sqrt(np.mean(err**2))), "bias": float(err.mean()), "SD_err": float(err.std(ddof=1)),
                         "meas_sd": float(yy.std(ddof=1)), "model_sd": float(ss.std(ddof=1)),
                         "SD_meas_lt_RMSE": bool(yy.std(ddof=1) < np.sqrt(np.mean(err**2)))})
    st_df, me_df = pd.DataFrame(stats), pd.DataFrame(mets)
    st_df.to_csv(out / "v06_stats.csv", index=False)
    me_df.to_csv(out / "v06_metrics.csv", index=False)
    pd.set_option("display.width", 220)
    print(st_df.round(3).to_string(index=False))
    print(me_df.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
