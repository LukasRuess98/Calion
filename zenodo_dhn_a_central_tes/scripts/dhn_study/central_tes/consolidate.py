"""Phase 6: collect all runs into results/central_tes/scenario_comparison.csv and print the numbers of the sanity check.

    python -m scripts.dhn_study.central_tes.consolidate
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config as C


def _flat(code: str, mode: str, variant: str, m: dict, h: dict | None, extra: dict | None = None) -> dict:
    a, b, t, d = m["partner_A"], m["partner_B"], m["TES"], m["dimensionless"]
    row = {"run": code, "mode": mode, "variant": variant, "cost_EUR": m["cost_total_EUR"],
           "U_A": a["U"], "A_unused_GWh": a["unused_GWh"], "HP_heat_GWh": a["HP_heat_GWh"], "HP_FLH": a["HP_full_load_h"],
           "A_chain_eff": a["chain_efficiency"], "cascade_share": a["cascade_share"],
           "HP_heat_share_lift_gt_limit": a["HP_heat_share_lift_above_limit"],
           "B_heat_GWh": b["heat_GWh"], "B_FLH": b["full_load_h"], "B_price_weighted": b["price_weighted_EUR_MWh"],
           "TES_charge_GWh": t["charge_GWh"], "TES_discharge_GWh": t["discharge_GWh"], "TES_charge_grid_GWh": t["charge_from_grid_GWh"],
           "TES_EFC": t["equivalent_full_cycles"], "masked_dis_h": t["hours_discharge_masked"],
           "masked_ch_grid_h": t["hours_charge_from_grid_masked"], "tau_h": d["tau_h"], "kappa_link": d["kappa_link"],
           "sigma_A": d["sigma_A"], "psi_central": d["psi_central"], "CO2_net_t": m["CO2_t"]["net"]}
    if h:
        row |= {"viol_h": h["violating_hours"], "attributable_h": h["attributable_to_central_h"],
                "dp_KWK_p95": h["dp_KWK_required"]["p95"], "soft_KWK_h": h["soft_hours"]["KWK"], "soft_MVA_h": h["soft_hours"]["MVA"],
                "min_sat_margin_bar": h["min_saturation_margin_bar"], "pump_el_MWh": sum(h["pump_el_MWh"].values()),
                "max_link_v_m_s": h["max_link_velocity_m_s"]}
    return row | (extra or {})


def collect(cfg: dict) -> pd.DataFrame:
    r = C.root() / cfg["paths"]["results"]
    rows = []
    sr = r / "scenario_runs"
    for d in sorted(sr.glob("F*-E")):
        j = json.loads((d / "annual_metrics.json").read_text())
        for v, h in j["hydraulics"].items():
            rows.append(_flat(d.name, "E", v, j["metrics"], h, {"group": "factorial"}))
    for d in sorted(sr.glob("F*-H")):
        for vd in sorted(p for p in d.iterdir() if p.is_dir()):
            j = json.loads((vd / "annual_metrics.json").read_text())
            rows.append(_flat(d.name, "H", vd.name, j["metrics"], j["hydraulics"], {"group": "factorial", "dC_hyd": j["dC_hyd_EUR"]}))
    for sd in sorted((r / "sensitivities").glob("A*")):
        for case in sorted(p for p in sd.iterdir() if p.is_dir()):
            for d in sorted(case.glob("F*-E")):
                j = json.loads((d / "annual_metrics.json").read_text())
                rows.append(_flat(d.name, "E", "A", j["metrics"], j["hydraulics"].get("A"), {"group": sd.name, "case": case.name}))
            for d in sorted(case.glob("F*-H")):
                vd = d / "A"
                if (vd / "annual_metrics.json").exists():
                    j = json.loads((vd / "annual_metrics.json").read_text())
                    rows.append(_flat(d.name, "H", "A", j["metrics"], j["hydraulics"], {"group": sd.name, "case": case.name,
                                                                                         "dC_hyd": j["dC_hyd_EUR"]}))
    for d in sorted((r / "rolling_horizon").glob("*")) if (r / "rolling_horizon").exists() else []:
        p = d / "annual_metrics.json"
        if p.exists():
            rows.append(_flat(d.name, "RH", "-", json.loads(p.read_text()), None, {"group": "rolling_horizon"}))
    for d in sorted((r / "exploratory").glob("*/F*-H/A")) if (r / "exploratory").exists() else []:
        j = json.loads((d / "annual_metrics.json").read_text())
        rows.append(_flat(d.parent.name, "H", "A", j["metrics"], j["hydraulics"], {"group": f"exploratory/{d.parent.parent.name}",
                                                                                    "dC_hyd": j["dC_hyd_EUR"]}))
    df = pd.DataFrame(rows)
    df.to_csv(r / "scenario_comparison.csv", index=False)
    return df


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    d = collect(C.load())
    print(d.groupby(["group", "mode"]).size())
