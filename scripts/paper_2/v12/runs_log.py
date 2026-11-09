"""v12 B7: run log docs/paper_2/agent_reports/v12/runs_v12.csv -- one row per finished v12 run (Teil E columns).

Scans output/v12/<run_id>/ (any dir with meta.json). Every value is read from the run's own files:
  meta.json (UB = obj_eur, Gurobi gap -> LB = UB - gap*|UB|), fixed_design.yaml (design; PIN0 runs: 0/0/none),
  validation.json (system_balance, objective_residual), cost_breakdown.json (cost lines + residual),
  full_solution_dump.json (HP/TES/CHP/boiler/dump/grid), geometry.csv (TES m3), run_export.json (dT_TES),
  node_temperatures.csv (TES-node supply temperature -> discharge mode).
Discharge mode per hour: direct if the TES node's supply temperature <= t_store_max_c, else preheat (v9 E3b).
Column `interval_source`: "gurobi_bound" (Weg A) -- Weg B rows will carry "decomposition".
usage: python scripts/paper_2/v12/runs_log.py [--out-base output/v12] [--csv docs/.../runs_v12.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
CHP = {"stadtbach": ["HKW", "GTOST", "BMHKW"], "memmingen": ["CHP_MAIN"]}
BOILER = {"stadtbach": ["HWS_BOILER", "HWW_BOILER"], "memmingen": ["GASBOILER_MAIN", "BIOMASS_MAIN"]}
HP = {"stadtbach": "hp_sb", "memmingen": "hp_main"}
TES = {"stadtbach": "tes_sb", "memmingen": "tes_main"}
TES_NODE = {("stadtbach", "hub"): "j_hkw", ("stadtbach", "source"): "j_man",
            ("memmingen", "hub"): "j_9", ("memmingen", "source"): "j_12"}


def _s(v, name):
    d = v.get(name)
    return np.array(list(d.values()), dtype=float) if isinstance(d, dict) else np.zeros(0)


def _sum(v, name):
    a = _s(v, name)
    return float(a.sum()) if a.size else 0.0


def row(run: Path) -> dict:
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    smeta = json.loads((run / "scenario_meta.json").read_text(encoding="utf-8"))
    net = smeta.get("network", "")
    fd = yaml.safe_load((run / "fixed_design.yaml").read_text(encoding="utf-8")) if (run / "fixed_design.yaml").exists() \
        else {"hp_mw": 0.0, "ek_mw": 0.0, "tes_mwh": 0.0, "tes_site": "none"}
    val = json.loads((run / "validation.json").read_text(encoding="utf-8")) if (run / "validation.json").exists() else {}
    sb = val.get("system_balance", {})
    cb = json.loads((run / "cost_breakdown.json").read_text(encoding="utf-8")) if (run / "cost_breakdown.json").exists() else {}
    v = json.loads((run / "full_solution_dump.json").read_text(encoding="utf-8"))["vars"]
    ub = float(meta.get("obj_eur") or np.nan)
    gap = float(meta.get("mip_gap") or np.nan)
    lb = ub - gap * abs(ub)
    hp, tes = HP.get(net, ""), TES.get(net, "")
    q_hp = _sum(v, f"{hp}_Q") + _sum(v, f"{hp}_Q_hot")
    disp = pd.read_csv(run / "dispatch_hourly.csv")
    q_el = float(disp["P_hp_el_MW"].sum()) if "P_hp_el_MW" in disp else np.nan
    qd = _s(v, f"{tes}_Qd")
    e_tes = float(fd.get("tes_mwh") or 0.0)
    geo = pd.read_csv(run / "geometry.csv") if (run / "geometry.csv").exists() else None
    tes_m3 = float(geo["V_TES_m3"].iloc[0]) if geo is not None and len(geo) else 0.0
    rexp = json.loads((run / "run_export.json").read_text(encoding="utf-8")) if (run / "run_export.json").exists() else {}
    tcfg = (rexp.get("tank_config") or {}).get(tes, {})
    direct_share = np.nan
    if qd.size and qd.sum() > 1e-6 and fd.get("tes_site") in ("hub", "source"):
        tn = pd.read_csv(run / "node_temperatures.csv")
        col = f"T_node_{TES_NODE[(net, fd['tes_site'])]}"
        tmax = float(tcfg.get("t_store_max_c", 95.0))
        if col in tn:
            direct = tn[col].to_numpy()[: qd.size] <= tmax + 1e-9
            direct_share = float(qd[direct].sum() / qd.sum())
    real = {k: d["value"] for k, d in (cb.get("real_costs_EUR") or {}).items()}
    aux = {k: d["value"] for k, d in (cb.get("model_aux_terms_EUR") or {}).items()}
    out = {
        "scenario_id": run.name, "network": net, "HK": smeta.get("heat_curve_stage"),
        "WP_MW": fd.get("hp_mw"), "EK_MW": fd.get("ek_mw"), "TES_MWh": e_tes, "TES_m3": round(tes_m3, 1),
        "TES_site": fd.get("tes_site"), "status": meta.get("status"), "balance_status": sb.get("status"),
        "UB_EUR": ub, "LB_EUR": lb, "width_EUR": ub - lb, "width_pct": 100 * gap, "interval_source": "gurobi_bound",
        "runtime_s": meta.get("solve_s"),
        "R_min_MW": sb.get("R_min_MW"), "R_absmax_MW": sb.get("R_abs_max_MW"), "R_sum_MWh": sb.get("R_sum_MWh"),
        "residual_EUR": cb.get("residual_EUR"),
        "HP_Qth_MWh": q_hp, "HP_Qel_MWh": q_el, "HP_SCOP": (q_hp / q_el) if q_el and q_el > 0 else np.nan,
        "HP_full_load_h": (q_hp / fd["hp_mw"]) if fd.get("hp_mw") else 0.0,
        "TES_cycles": (float(qd.sum()) / e_tes) if e_tes > 0 and qd.size else 0.0,
        "TES_direct_share": direct_share, "TES_dT_K": tcfg.get("delta_T_scenario_k"),
        "CHP_el_MWh": sum(_sum(v, f"{a}_Pel") for a in CHP.get(net, [])),
        "CHP_th_MWh": sum(_sum(v, f"{a}_Qth") for a in CHP.get(net, [])),
        "boiler_th_MWh": sum(_sum(v, f"{a}_Qth") for a in BOILER.get(net, [])),
        "dump_MWh": sum(float(np.sum(list(d.values()))) for k, d in v.items()
                        if k.startswith("Q_dump_") and not k.startswith("Q_dump_chp_") and isinstance(d, dict)),
        "grid_import_peak_MW": float(disp["P_buy_MW"].max()) if "P_buy_MW" in disp else np.nan,
    }
    out.update({f"cost_{k}": val_ for k, val_ in {**real, **aux}.items()})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-base", default=str(ROOT / "output" / "v12"))
    ap.add_argument("--csv", default=str(ROOT / "docs" / "paper_2" / "agent_reports" / "v12" / "runs_v12.csv"))
    a = ap.parse_args()
    rows = [row(d) for d in sorted(Path(a.out_base).iterdir()) if (d / "meta.json").exists()]
    cols = list(dict.fromkeys(k for r in rows for k in r))
    Path(a.csv).parent.mkdir(parents=True, exist_ok=True)
    with open(a.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} run(s) -> {a.csv}")


if __name__ == "__main__":
    main()
