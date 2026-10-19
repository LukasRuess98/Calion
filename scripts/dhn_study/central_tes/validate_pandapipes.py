"""Cross-check of the Mode-E / Mode-H hydraulic states with pandapipes (closed loop, separate supply/return).

For selected hours of a schedule, the injections, pump-station gains (incl. the PS1 head used by the control) and the
required KWK Δp from the Ersatznetz evaluation are applied to the pandapipes model of
``scripts/dhn_study/gegenrechnung_pandapipes.py``. Compared: Δp at the stations and plant nodes, edge flows.
Two friction laws: ``nikuradse`` (same quadratic law → checks solver/structure) and ``swamee-jain`` (Reynolds-dependent).
Hours without KWK flow are skipped (a circulation pump cannot run at zero/negative flow).

    python -m scripts.dhn_study.central_tes.validate_pandapipes
Output: results/central_tes/pandapipes/
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .. import gegenrechnung_pandapipes as gp
from .. import netzmodell as nm
from . import config as C
from . import coupling, inputs
from .hydraulics import Hydro

NODES = [nm.STATIONEN[v] for v in ("V06", "V03", "V12")] + ["L1G", "S", "K3", "MVA", "GT", "BIO", "HW1"]


def select_hours(ev: pd.DataFrame, sched: pd.DataFrame, n: int = 25) -> np.ndarray:
    ok = ev["m_KWK"].to_numpy() > 10.0
    idx = np.arange(len(ev))
    pick = set()
    for key in (sched["D"].to_numpy(), np.abs(sched["Q_central"].to_numpy()), ev["dp_KWK"].to_numpy()):
        order = idx[ok][np.argsort(-key[ok])]
        pick |= set(order[:n].tolist())
    viol = idx[ok & ev["violation"].to_numpy()]
    pick |= set(viol[:n].tolist())
    rng = np.random.default_rng(0)
    pick |= set(rng.choice(idx[ok], size=min(n, ok.sum()), replace=False).tolist())
    return np.array(sorted(pick))


def run(cfg: dict, cases: dict[str, tuple[dict, Path]], out: Path) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    rows, summ = [], []
    for name, (ov, sched_path) in cases.items():
        c = C.merge(cfg, ov)
        x = inputs.build(c)
        hy = Hydro(c, x, c["hydraulics"]["reference_variant"])
        sched = pd.read_parquet(sched_path)
        sc = coupling._sched_cols(sched)
        ev = hy.evaluate(sc)
        hours = select_hours(ev, sched)
        r = hy._model(sc, hours)
        hi = nm.verlust  # noqa: F841  (quadratic law used by the Ersatznetz)
        high = np.argsort(-sched["D"].to_numpy())[:200]
        m_ref = np.median(np.abs(hy._model(sc, high)["m"]), axis=0)
        for model in ("nikuradse", "swamee-jain"):
            ppn = gp.baue_netz(hy.nz, hy.K, m_ref, modell=model)
            for i, t in enumerate(hours):
                dp_pp, m_vl, m_rl = gp.rechne(hy.nz, ppn, r["b"][i], r["gain"][i], float(r["req"][i]))
                for n in NODES:
                    j = hy.nz.idx[n]
                    rows.append({"case": name, "model": model, "hour": str(x.index[t]), "node": n,
                                 "dp_ersatznetz": float(r["dp"][i, j]), "dp_pandapipes": float(dp_pp[j]),
                                 "dm_max_vl": float(np.nanmax(np.abs(m_vl - r["m"][i]))),
                                 "dm_vl_rl": float(np.nanmax(np.abs(m_vl - m_rl)))})
        d = pd.DataFrame([w for w in rows if w["case"] == name])
        d["diff"] = d["dp_pandapipes"] - d["dp_ersatznetz"]
        for model, g in d.groupby("model"):
            summ.append({"case": name, "model": model, "hours": int(g["hour"].nunique()),
                         "converged_share": float(g["dp_pandapipes"].notna().groupby(g["hour"]).all().mean()),
                         "max_abs_dp_diff_bar": float(g["diff"].abs().max()), "p95_abs_dp_diff_bar": float(g["diff"].abs().quantile(0.95)),
                         "V06_max_abs_diff_bar": float(g.loc[g.node == nm.STATIONEN["V06"], "diff"].abs().max()),
                         "max_dm_vl_kg_s": float(g["dm_max_vl"].max()), "max_dm_vl_rl_kg_s": float(g["dm_vl_rl"].max())})
    df = pd.DataFrame(rows)
    df.to_csv(out / "pandapipes_hours.csv", index=False)
    s = pd.DataFrame(summ)
    s.to_csv(out / "pandapipes_summary.csv", index=False)
    (out / "pandapipes_summary.json").write_text(json.dumps(summ, indent=1))
    return s


def main():
    cfg = C.load()
    r = C.root() / cfg["paths"]["results"]
    cases = {"F000-E": ({}, r / "scenario_runs/F000-E/milp_timeseries.parquet"),
             "F111-E": ({}, r / "scenario_runs/F111-E/milp_timeseries.parquet"),
             "F111-H": ({}, r / "scenario_runs/F111-H/A/milp_timeseries.parquet")}
    xs = r / "sensitivities/X/L20"
    if (xs / "F111-H/A/milp_timeseries.parquet").exists():
        ov = {"inputs.expansion": {"share": 0.2, "region": "south"}, "new_boiler.enabled": True}
        cases["L20 F111-E"] = (ov, xs / "F111-E/milp_timeseries.parquet")
        cases["L20 F111-H"] = (ov, xs / "F111-H/A/milp_timeseries.parquet")
    cases = {k: v for k, v in cases.items() if v[1].exists()}
    s = run(cfg, cases, r / "pandapipes")
    print(s.round(3).to_string())


if __name__ == "__main__":
    main()
