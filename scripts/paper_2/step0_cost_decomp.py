"""Step-0 analysis (2026-09-21): cost decomposition + tank operating profile + bound intervals.
READ-ONLY on existing result dirs (economics.csv, geometry.csv, dispatch_*.csv, Gurobi logs, .out).

Terms of the model objective (constraint_builder.create_objective): energy(buy-sell), dump, fuel, CO2,
demand charge, capex (HP/EK), activation (start-up), tie-break, storage install (TES capex), terminal
value, demand slack, return anchor, pressure reg, lateral tie-break, pressure slack.
economics.csv exports only: buy, sell, fuel, CO2, dump, demand charge, pump. The rest is the RESIDUAL
R = obj - sum(exported); the TES capex is computed here (degressive per-tank cost x model annual factor,
read from the run's own log) and removed, leaving 'other' = activation + tie-break + terminal + slack/regularisers
(+HP/EK capex). Runs with cost_breakdown.json (written from step 7 on) are decomposed exactly.

Savings interval (matched-effort protocol):  save_min = max(0, LB_S0 - UB_Sx),  save_max = UB_S0 - LB_Sx,
LB/UB = Gurobi best bound / best objective from the log (NOT reconstructed from meta gap).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "output" / "mm_s4_reconcile"


def log_bounds(tag: str, scen: str):
    f = RECON / tag / "logs" / f"gurobi_{scen}.log"
    ub = lb = None
    if f.exists():
        for line in f.read_text(errors="ignore").splitlines():
            m = re.search(r"Best objective\s+([0-9.eE+-]+),\s+best bound\s+([0-9.eE+-]+),\s+gap\s+([0-9.eE+-]+)%", line)
            if m:
                ub, lb = float(m.group(1)), float(m.group(2))
    return ub, lb


def annual_factor(tag: str):
    f = RECON / f"{tag}.out"
    if f.exists():
        m = re.findall(r"annual_factor=([0-9.eE+-]+)", f.read_text(errors="ignore"))
        if m:
            return float(m[-1])
    return None


def tes_capex_annual(V: float, c0_scale: float, af: float | None):
    g = yaml.safe_load(open(ROOT / "configs/paper_2/storage_geometry.yaml", encoding="utf-8"))["storage_geometry"]
    if V <= 0 or af is None:
        return 0.0
    N = max(1, int(np.ceil(V / float(g["unit_tank_m3"]))))
    raw = N * float(g["c0_eur"]) * c0_scale * ((V / N) / float(g["v0_m3"])) ** float(g["exponent_b"])
    return raw * af


def load(tag: str, scen: str, c0_scale: float = 1.0):
    d = RECON / tag / "runs" / scen
    m = json.load(open(d / "meta.json"))
    e = pd.read_csv(d / "economics.csv").iloc[0]
    g = pd.read_csv(d / "geometry.csv").iloc[0]
    h = pd.read_csv(d / "dispatch_hourly.csv")
    a = pd.read_csv(d / "dispatch_per_asset.csv")
    ub, lb = log_bounds(tag, scen)
    obj = float(m.get("obj_eur"))
    listed = dict(buy=float(e.cost_energy_buy_eur), sell=-float(e.revenue_sell_eur), fuel=float(e.cost_fuel_eur),
                  co2=float(e.cost_co2_eur), dump=float(e.cost_dump_eur), demand_charge=float(e.cost_demand_charge_eur))
    resid = obj - sum(listed.values())
    V = float(g.V_TES_m3)
    tank = tes_capex_annual(V, c0_scale, annual_factor(tag))
    exact = None
    bj = d / "cost_breakdown.json"
    if bj.exists():
        exact = json.load(open(bj))
    return dict(tag=tag, obj=obj, ub=ub, lb=lb, listed=listed, resid=resid, tank=tank, other=resid - tank, V=V,
                E=float(g.E_TES_max_MWh), h=h, a=a, exact=exact, pump=float(e.cost_pump_eur))


def profile(r):
    h, a = r["h"], r["a"]
    ch, dis = h.Q_storage_charge_MW.to_numpy(), h.Q_storage_discharge_MW.to_numpy()
    out = dict(charge_MWh=ch.sum(), discharge_MWh=dis.sum(), charge_h=int((ch > 1e-3).sum()), discharge_h=int((dis > 1e-3).sum()),
               both_h=int(((ch > 1e-3) & (dis > 1e-3)).sum()),
               cycles=(dis.sum() / r["E"]) if r["E"] > 0 else 0.0)
    cols = [c for c in a.columns if c.endswith("_MW") and c != "timestamp"]
    for c in cols:
        x = a[c].to_numpy()
        on = x > 1e-3
        out[f"on_h[{c}]"] = int(on.sum())
        out[f"starts[{c}]"] = int(((~on[:-1]) & on[1:]).sum() + (1 if on[0] else 0))
    return out


def main():
    base_tag, base_scen = "s6_seed_MM_S0HK0", "MM-S0-HK0"
    runs = [("S1 (c0 x1.0)", "s6_mm_S1HK0", "MM-S1-HK0", 1.0), ("S2 (c0 x1.0)", "s6_mm_S2HK0", "MM-S2-HK0", 1.0),
            ("S3 (c0 x1.0)", "s6_mm_S3HK0", "MM-S3-HK0", 1.0), ("S2 c0 x0.7", "s6_mm_S2HK0_c70", "MM-S2-HK0", 0.7),
            ("S2 c0 x0.5", "s6_mm_S2HK0_c50", "MM-S2-HK0", 0.5), ("S2 c0 x0.3", "s6_mm_S2HK0_c30", "MM-S2-HK0", 0.3)]
    s0 = load(base_tag, base_scen)
    print(f"S0-HK0: obj {s0['obj']:,.0f}  UB {s0['ub']:,.0f}  LB {s0['lb']:,.0f}  gap {100*(s0['ub']-s0['lb'])/s0['ub']:.2f}%")
    print(f"        listed {{{', '.join(f'{k} {v:,.0f}' for k,v in s0['listed'].items())}}}  residual {s0['resid']:,.0f} (tank capex {s0['tank']:,.0f}; other {s0['other']:,.0f})")
    rows = []
    for label, tag, scen, sc in runs:
        r = load(tag, scen, sc)
        d = {k: r["listed"][k] - s0["listed"][k] for k in r["listed"]}
        d["tank_capex"] = r["tank"] - s0["tank"]
        d["other"] = r["other"] - s0["other"]
        tot = r["obj"] - s0["obj"]
        chk = sum(d.values())
        save_min = max(0.0, s0["lb"] - r["ub"]); save_max = s0["ub"] - r["lb"]
        pen = abs(d["dump"]) + abs(d["other"])
        rows.append((label, r, d, tot, chk, save_min, save_max, pen))
        print(f"\n== {label}: obj {r['obj']:,.0f} (d {tot:+,.0f} = {100*tot/s0['obj']:+.2f}%), tank V {r['V']:.0f} m3 / {r['E']:.1f} MWh, UB {r['ub']:,.0f} LB {r['lb']:,.0f}")
        print("   d-terms EUR: " + ", ".join(f"{k} {v:+,.0f}" for k, v in d.items()) + f"   (sum {chk:+,.0f}; check vs d-obj {tot:+,.0f})")
        print(f"   saving interval (LB_S0-UB_Sx ; UB_S0-LB_Sx): min {save_min:,.0f} EUR ({100*save_min/s0['ub']:.2f}% of UB_S0), max {save_max:,.0f} EUR ({100*save_max/s0['ub']:.2f}%)")
        if tot < 0:
            print(f"   share of saving from dump + unexplained 'other' (upper bound on penalty/slack): {100*pen/abs(tot):.0f}%  (dump {100*abs(d['dump'])/abs(tot):.0f}%)")
        p0, p = profile(s0), profile(r)
        print(f"   tank: cycles/yr {p['cycles']:.0f}, charge {p['charge_MWh']:.0f} MWh in {p['charge_h']} h, discharge {p['discharge_MWh']:.0f} MWh in {p['discharge_h']} h, simultaneous h {p['both_h']}")
        for c in [c for c in r['a'].columns if c.endswith('_MW') and c != 'timestamp']:
            print(f"     {c:20s} on-h S0 {p0['on_h['+c+']']:5d} -> {p['on_h['+c+']']:5d} | starts S0 {p0['starts['+c+']']:4d} -> {p['starts['+c+']']:4d}")
        # which unit runs when the tank charges: mean change vs S0 in charge / discharge hours
        ch = r["h"].Q_storage_charge_MW.to_numpy() > 1e-3
        dis = r["h"].Q_storage_discharge_MW.to_numpy() > 1e-3
        if ch.any():
            print("     mean MW S2-S0 in CHARGE hours: " + ", ".join(f"{c[:-3]} {(r['a'][c].to_numpy()[ch]-s0['a'][c].to_numpy()[ch]).mean():+.3f}" for c in r['a'].columns if c.endswith('_MW') and c != 'timestamp'))
        if dis.any():
            print("     mean MW S2-S0 in DISCHARGE hours: " + ", ".join(f"{c[:-3]} {(r['a'][c].to_numpy()[dis]-s0['a'][c].to_numpy()[dis]).mean():+.3f}" for c in r['a'].columns if c.endswith('_MW') and c != 'timestamp'))
    print("\nSTOP rule (> 20% of the saving from penalty/slack/dump):")
    for label, r, d, tot, chk, smin, smax, pen in rows:
        if tot < 0:
            print(f"  {label:14s} dump-only share {100*abs(d['dump'])/abs(tot):5.1f}%, dump+other(upper bound) {100*pen/abs(tot):5.1f}%")


if __name__ == "__main__":
    main()
