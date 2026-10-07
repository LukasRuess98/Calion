"""Read-only integrity check of finished Paper-2 result directories (2026-09-21).

Why: concurrent runs all export into the SAME directory (output/paper2_runs/thermal_network/...,
solver/...), and the per-run extraction copies from there. If two runs finish extraction at the
same moment, one result dir can receive files of the OTHER run (found 2026-09-21: d3yr_BC-SB had
pipes.csv/dispatch_hourly.csv of a Memmingen run, dispatch_per_asset.csv/node_heat_audit.json of
Stadtbach; 20 older atmo*/atmo2*/fillr/valgeo sweep dirs show the same pattern).

Checks per run dir (network inferred from the scenario id, horizon from the row count):
  * pipes.csv          -> Stadtbach pipe ids (hkw_to_*, ost_to_*, pss_to_*) vs Memmingen (jN_to_jM)
  * dispatch_per_asset -> AVA_FEED_MW column exists only for Stadtbach
  * dispatch_hourly    -> total demand ~ expected (SB 640 GWh/yr, MM 9.43 GWh/yr, scaled by hours)
  * node_heat_audit    -> SB nodes (j_hkw, j_ava, ...) vs MM nodes (j_9, j_12)
  * economics.csv (model-derived) vs dispatch_hourly P_buy/P_sell sums (same-network mixing, e.g.
    two MM runs ending together, is invisible to the network checks but shows up here).
    NOTE: dispatch_hourly is assembled column-wise from model AND thermal-export files; the demand /
    temperature / loss columns can be foreign while the electricity columns are correct.
Exit code 1 if any directory is inconsistent.

Usage:  python scripts/paper_2/check_run_integrity.py <run_dir> [<run_dir> ...]
        python scripts/paper_2/check_run_integrity.py "output/mm_s4_reconcile/d3yr_*/runs/*"
"""
import csv
import glob
import json
import sys

import pandas as pd

SB_PER_H, MM_PER_H = 639970.0 / 8760.0, 9430.0 / 8760.0   # MWh of demand per hour of horizon


def _network(scen: str) -> str:
    return "SB" if "SB" in scen else "MM"


def check(run_dir: str) -> list[str]:
    run_dir = run_dir.replace("\\", "/").rstrip("/")
    scen = run_dir.split("/")[-1]
    exp = _network(scen)
    problems = []
    try:
        ids = [r["pipe_id"] for r in csv.DictReader(open(run_dir + "/pipes.csv"))]
        got = "SB" if any(i.startswith(("hkw_to", "ost_to", "pss_to")) for i in ids) else "MM"
        if got != exp:
            problems.append(f"pipes.csv is {got}")
    except Exception as e:  # noqa: BLE001
        problems.append(f"pipes.csv unreadable ({e.__class__.__name__})")
    try:
        cols = pd.read_csv(run_dir + "/dispatch_per_asset.csv", nrows=1).columns
        got = "SB" if "AVA_FEED_MW" in cols else "MM"
        if got != exp:
            problems.append(f"dispatch_per_asset.csv is {got}")
    except Exception as e:  # noqa: BLE001
        problems.append(f"dispatch_per_asset.csv unreadable ({e.__class__.__name__})")
    try:
        h = pd.read_csv(run_dir + "/dispatch_hourly.csv", usecols=["Q_demand_total_MW"])
        per_h = h.Q_demand_total_MW.sum() / max(len(h), 1)
        got = "SB" if abs(per_h - SB_PER_H) < abs(per_h - MM_PER_H) else "MM"
        if got != exp:
            problems.append(f"dispatch_hourly.csv looks {got} (mean demand {per_h:.1f} MW)")
    except Exception as e:  # noqa: BLE001
        problems.append(f"dispatch_hourly.csv unreadable ({e.__class__.__name__})")
    try:  # dispatch_hourly (model + thermal-export columns) must agree with economics.csv (model)
        e = pd.read_csv(run_dir + "/economics.csv").iloc[0]
        h2 = pd.read_csv(run_dir + "/dispatch_hourly.csv", usecols=["P_buy_MW", "P_sell_MW"])
        for col, ec in (("P_buy_MW", "energy_buy_MWh"), ("P_sell_MW", "energy_sell_MWh")):
            a, b = float(h2[col].sum()), float(e[ec])
            if abs(a - b) > 0.02 * max(b, 1.0):
                problems.append(f"dispatch_hourly {col} sum {a:.0f} != economics {ec} {b:.0f}")
    except Exception as ex:  # noqa: BLE001
        problems.append(f"economics/dispatch cross-check unreadable ({ex.__class__.__name__})")
    try:
        nodes = json.load(open(run_dir + "/node_heat_audit.json"))["per_node"]
        got = "SB" if any(k in nodes for k in ("j_hkw", "j_ava", "j_pss")) else "MM"
        if got != exp:
            problems.append(f"node_heat_audit.json is {got}")
    except Exception as e:  # noqa: BLE001
        problems.append(f"node_heat_audit.json unreadable ({e.__class__.__name__})")
    return problems


if __name__ == "__main__":
    dirs = []
    for a in sys.argv[1:]:
        dirs += sorted(glob.glob(a)) or [a]
    bad = 0
    for d in dirs:
        p = check(d)
        print(("MIXED  " if p else "ok     ") + d + ("  :: " + "; ".join(p) if p else ""))
        bad += bool(p)
    sys.exit(1 if bad else 0)
