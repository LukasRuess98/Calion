"""South hosting capacity: how much additional south demand can the existing network serve, and does the TES help?

No new capacity is built. New customers are added at the south nodes (share of today's annual demand, today's hourly
shape). Heat that the network cannot deliver to them within the hydraulic limits becomes *unserved heat* (variable
``NEW`` in ``new_boiler.mode: unserved``: penalty cost, ≤ the new customers' demand, withdrawn from the south nodes
like their load). Mode H enforces the hydraulic limits with the existing plants, pumps and PS1 head control.

Metrics per growth level and variant (Mode H, calibration A):
* unserved heat [MWh/a] and its peak [MW] — hosting capacity = largest growth with no unserved heat;
* cost of hydraulic feasibility ΔC_hyd = C_H − C_E without the unserved-heat penalty (redispatch cost);
* value of the variant against F000 at the same growth: Mode H cost without penalty, unserved heat charged at the heat
  cost of the existing south peak boiler HW1 (comparison at equal delivered heat).

    python -m scripts.dhn_study.central_tes.hosting [--only F000 F111 ...] [--shares 0.15 0.2 ...]
Output: results/central_tes/hosting/summary.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from . import config as C
from .run import Study

SOUTH = {"hydraulics.anticipate_tes_ext_bar": 0.5, "hydraulics.k_max": 20}   # TES charging through the bottleneck
VARIANTS = {
    # name: (scenario code, overrides)
    "F000": ("F000", {}),
    "F110": ("F110", {}),
    "F001_S": ("F001", {}),
    "F111_S": ("F111", {}),
    "F001_south": ("F001", {"tes.node": "station:V06", **SOUTH}),
    "F111_south": ("F111", {"tes.node": "station:V06", **SOUTH}),
    "F001_south_V20000_Q80": ("F001", {"tes.node": "station:V06", "tes.volume_m3": 20000, "tes.Q_ch_max_MW": 80,
                                       "tes.Q_dis_max_MW": 80, **SOUTH}),
    # KWK Δp ≤ 4 bar (operator experience value) as hard limit
    "F000_kwk4": ("F000", {"hydraulics.kwk_experience_value_hard": True}),
    "F001_S_kwk4": ("F001", {"hydraulics.kwk_experience_value_hard": True}),
    "F001_south_kwk4": ("F001", {"tes.node": "station:V06", "hydraulics.kwk_experience_value_hard": True, **SOUTH}),
}
SHARES = (0.15, 0.175, 0.20, 0.225, 0.25, 0.30)


TOL_BAR = 0.05      # remaining hydraulic violation accepted as converged (cut margin 0.02 bar; model accuracy ≫ this)


def _maxviol(p: Path) -> float:
    if not p.exists():
        return 0.0
    v = pd.read_csv(p)
    return float(v["violation_bar"].max()) if len(v) else 0.0


def run_one(cfg: dict, out: Path, name: str, share: float) -> dict:
    code, ov = VARIANTS[name]
    c = C.merge(cfg, {**ov, "inputs.expansion": {"share": share, "region": "south"}, "new_boiler.enabled": True,
                      "new_boiler.mode": "unserved"})
    d = out / name / f"L{100 * share:g}"
    f = d / f"{code}-H" / "A" / "annual_metrics.json"
    if not f.exists():
        st = Study(c, d, ["A"], out / "run.log")
        st.log(f"hosting {name} share {share}")
        st.run(code, mode_h=True, h_variants=["A"])
    e = json.loads((d / f"{code}-E" / "annual_metrics.json").read_text())["metrics"]
    h = json.loads(f.read_text())
    pen = float(c["new_boiler"].get("unserved_penalty_eur_MWh", 1000.0))
    ue, uh = e["new_boiler"]["heat_GWh"] * 1e3, h["metrics"]["new_boiler"]["heat_GWh"] * 1e3
    ce = e["cost_total_EUR"] - pen * ue
    ch = h["metrics"]["cost_total_EUR"] - pen * uh
    return {"variant": name, "scenario": code, "share": share, "unserved_E_MWh": ue, "unserved_H_MWh": uh,
            "unserved_peak_H_MW": h["metrics"]["new_boiler"]["peak_MW"], "unserved_hours_H": h["metrics"]["new_boiler"].get("hours", None),
            "C_E_excl": ce, "C_H_excl": ch, "dC_hyd_excl": ch - ce, "converged_H": h["info"]["converged"],
            "iterations_H": h["info"]["iterations"], "max_violation_H_bar": _maxviol(d / f"{code}-H" / "A" / "violations.csv"), "dpKWK_p95_H": h["hydraulics"]["dp_KWK_required"]["p95"],
            "TES_dis_GWh_H": h["metrics"]["TES"]["discharge_GWh"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--shares", nargs="*", type=float)
    ap.add_argument("--set", nargs="*", default=[])
    ap.add_argument("--collect", action="store_true", help="only collect all finished runs into hosting/summary.csv")
    a = ap.parse_args(argv)
    if a.collect:
        print(collect().round(3).to_string(index=False))
        return
    import yaml
    cfg = C.load(None, {k: yaml.safe_load(v) for k, v in (kv.split("=", 1) for kv in a.set)})
    out = C.root() / cfg["paths"]["results"] / "hosting"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in (a.only or VARIANTS):
        for share in (a.shares or SHARES):
            rows.append(run_one(cfg, out, name, share))
            print(rows[-1], flush=True)
    tag = "_".join(a.only) if a.only else "all"
    pd.DataFrame(rows).to_csv(out / f"summary_{tag}.csv", index=False)


def collect(out: Path | None = None) -> pd.DataFrame:
    """All finished runs → summary.csv with the value of each variant against F000 at the same growth."""
    cfg = C.load()
    out = out or C.root() / cfg["paths"]["results"] / "hosting"
    rows = []
    for name in VARIANTS:
        for d in sorted((out / name).glob("L*")) if (out / name).exists() else []:
            share = round(float(d.name[1:]) / 100, 4)
            if (d / f"{VARIANTS[name][0]}-H" / "A" / "annual_metrics.json").exists():
                rows.append(run_one(cfg, out, name, share))
    s = pd.DataFrame(rows).sort_values(["variant", "share"])
    s["share"] = s["share"].round(4)
    s["feasible_H"] = s["max_violation_H_bar"] <= TOL_BAR
    # value at equal delivered heat: unserved heat is charged at the heat cost of the existing south peak boiler (HW1)
    hw = cfg["plants"]["HW1"]
    c_heat = (cfg["fuels"]["gas"]["price"] + hw.get("energy_tax_eur_MWh", 0.0) + cfg["fuels"]["gas"]["ef"] / 1e3 * cfg["co2_price_eur_t"]) / hw["eta_th"]
    s["C_H_adj"] = s["C_H_excl"] + c_heat * s["unserved_H_MWh"]
    s["heat_value_unserved_EUR_MWh"] = c_heat
    s["value_vs_F000_H"] = float("nan")
    for ref, kw in (("F000", False), ("F000_kwk4", True)):
        base = s[s["variant"] == ref].set_index("share")["C_H_adj"]
        m = s["variant"].str.endswith("_kwk4") == kw
        s.loc[m, "value_vs_F000_H"] = s[m].apply(lambda r: base.get(r["share"], float("nan")) - r["C_H_adj"], axis=1)
    s.to_csv(out / "summary.csv", index=False)
    return s


if __name__ == "__main__":
    main()
