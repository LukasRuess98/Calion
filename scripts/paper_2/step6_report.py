"""Step-6 report: table Szenario | Kosten | dKosten vs S0 | CO2 | V_TES | HP-Leistung | Gap | Gate + break-even.

Reads ONLY model output of the s6_* result dirs (meta.json, economics.csv, geometry.csv,
dispatch_hourly.csv) -- no own physics. Tank CAPEX of FIXED-size (regret) runs is not in the model
objective (non-investable tank = no CAPEX); it is added post hoc with the SAME degressive per-tank
cost as scripts/paper_2/f2_capex.py (regret cost = objective + annualised CAPEX of the model's V).

Gate: S0 is a restriction of S_k  =>  incumbent(S_k) <= incumbent(S0) * (1 + gap(S_k)); else FAIL.
Suspect: gap > 1 % (SB) or > 0.5 % (MM), or failed integrity / gate.

Usage: python scripts/paper_2/step6_report.py [--out output/paper2_sweeps/step6]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "output" / "mm_s4_reconcile"
GAP_LIMIT = {"SB": 0.01, "MM": 0.005}


def _load(tag: str, scen: str):
    d = RECON / f"s6_{tag}" / "runs" / scen
    if not (d / "meta.json").exists():
        return None
    try:
        m = json.load(open(d / "meta.json"))
        e = pd.read_csv(d / "economics.csv").iloc[0]
        g = pd.read_csv(d / "geometry.csv").iloc[0]
        h = pd.read_csv(d / "dispatch_hourly.csv")
    except Exception:  # noqa: BLE001
        return None
    obj = m.get("obj_eur", m.get("objective"))
    if obj is None:
        return None
    return dict(obj=float(obj), gap=m.get("mip_gap"), co2=float(e.co2_total_t), V=float(g.V_TES_m3),
                E=float(g.E_TES_max_MWh), built=int(g.build),
                hp_max=float(h.Q_hp_total_MW.max()), hp_gwh=float(h.Q_hp_total_MW.sum() / 1000.0),
                integrity=not (d / "FAILED_INTEGRITY.txt").exists())


def _capex_annual(V: float) -> float:
    from scripts.paper_2.f2_capex import _anf, _capex_from_V, _load_geom
    g = _load_geom()
    return _capex_from_V(V, c0=float(g["c0_eur"]), v0=float(g["v0_m3"]), b=float(g["exponent_b"]),
                         unit=float(g.get("unit_tank_m3", 10000.0)), anf=_anf(0.05, 30.0))[0]


# (label, tag, scenario, network, kind, s0_ref_tag)  kind: s0 | core | regret | be | inter
SPEC = [
    ("MM-S0-HK0", "seed_MM_S0HK0", "MM-S0-HK0", "MM", "s0", None),
    ("MM-S1-HK0", "mm_S1HK0", "MM-S1-HK0", "MM", "core", "seed_MM_S0HK0"),
    ("MM-S2-HK0", "mm_S2HK0", "MM-S2-HK0", "MM", "core", "seed_MM_S0HK0"),
    ("MM-S3-HK0", "mm_S3HK0", "MM-S3-HK0", "MM", "core", "seed_MM_S0HK0"),
    ("MM-S2-HK0 fix 1.1 MWh (regret)", "mm_S2HK0_fix1.1", "MM-S2-HK0", "MM", "regret", "seed_MM_S0HK0"),
    ("MM-S2-HK0 c0 x0.7", "mm_S2HK0_c70", "MM-S2-HK0", "MM", "be", "seed_MM_S0HK0"),
    ("MM-S2-HK0 c0 x0.5", "mm_S2HK0_c50", "MM-S2-HK0", "MM", "be", "seed_MM_S0HK0"),
    ("MM-S2-HK0 c0 x0.3", "mm_S2HK0_c30", "MM-S2-HK0", "MM", "be", "seed_MM_S0HK0"),
    ("MM-S0-HK2", "seed_MM_S0HK2", "MM-S0-HK2", "MM", "s0", None),
    ("MM-S2-HK2 (interaction)", "mm_S2HK2", "MM-S2-HK2", "MM", "inter", "seed_MM_S0HK2"),
    ("SB-S0-HK0", "seed_SB_S0HK0", "SB-S0-HK0", "SB", "s0", None),
    ("SB-S1-HK0", "sb_S1HK0", "SB-S1-HK0", "SB", "core", "seed_SB_S0HK0"),
    ("SB-S2-HK0", "sb_S2HK0", "SB-S2-HK0", "SB", "core", "seed_SB_S0HK0"),
    ("SB-S3-HK0", "sb_S3HK0", "SB-S3-HK0", "SB", "core", "seed_SB_S0HK0"),
    ("SB-S2-HK0 fix 219 MWh (regret)", "sb_S2HK0_fix219", "SB-S2-HK0", "SB", "regret", "seed_SB_S0HK0"),
    ("SB-S2-HK0 c0 x0.7", "sb_S2HK0_c70", "SB-S2-HK0", "SB", "be", "seed_SB_S0HK0"),
    ("SB-S2-HK0 c0 x0.5", "sb_S2HK0_c50", "SB-S2-HK0", "SB", "be", "seed_SB_S0HK0"),
    ("SB-S2-HK0 c0 x0.3", "sb_S2HK0_c30", "SB-S2-HK0", "SB", "be", "seed_SB_S0HK0"),
    ("BC-SB (FIX) rerun", "sb_BC-SB", "BC-SB", "SB", "base", None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "output" / "paper2_sweeps" / "step6"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    scen_of = {t: s for _, t, s, _, _, _ in SPEC}
    data = {t: _load(t, s) for _, t, s, _, _, _ in SPEC}
    rows = []
    for label, tag, scen, net, kind, ref in SPEC:
        r = data[tag]
        if r is None:
            rows.append(dict(Szenario=label, Netz=net, Status="nicht fertig"))
            continue
        cost = r["obj"] + (_capex_annual(r["V"]) if kind == "regret" else 0.0)
        s0 = data.get(ref) if ref else None
        d_pct = 100.0 * (cost - s0["obj"]) / s0["obj"] if s0 else None
        gap = r["gap"]
        gate = "n/a"
        if kind in ("core", "be", "inter") and s0 and gap is not None:
            gate = "PASS" if cost <= s0["obj"] * (1.0 + gap) else "FAIL"
        suspect = []
        if gap is not None and gap > GAP_LIMIT[net]:
            suspect.append(f"Gap>{100*GAP_LIMIT[net]:.1f}%")
        if not r["integrity"]:
            suspect.append("Integritaet")
        if gate == "FAIL":
            suspect.append("Dominanz")
        rows.append({"Szenario": label, "Netz": net, "Kosten_EUR": round(cost), "dKosten_vs_S0_%": None if d_pct is None else round(d_pct, 2),
                     "CO2_t": round(r["co2"], 1), "V_TES_m3": round(r["V"]), "E_TES_MWh": round(r["E"], 2),
                     "HP_max_Betrieb_MW": round(r["hp_max"], 2), "HP_Waerme_GWh": round(r["hp_gwh"], 2),
                     "Gap_%": None if gap is None else round(100 * gap, 2), "Gate": gate,
                     "Status": "SUSPECT: " + ", ".join(suspect) if suspect else "ok"})
    df = pd.DataFrame(rows)
    df.to_csv(out / "step6_table.csv", index=False, encoding="utf-8")
    # break-even curve V_TES(c0) per network: 100 % = core S2 run
    be = []
    for net, core, sc in (("MM", "mm_S2HK0", "MM-S2-HK0"), ("SB", "sb_S2HK0", "SB-S2-HK0")):
        s0 = data.get("seed_MM_S0HK0" if net == "MM" else "seed_SB_S0HK0")
        for pct, tag in ((100, core), (70, core + "_c70"), (50, core + "_c50"), (30, core + "_c30")):
            r = data.get(tag) if tag in data else _load(tag, sc)
            if r is None:
                be.append(dict(Netz=net, c0_pct=pct, Status="nicht fertig")); continue
            be.append(dict(Netz=net, c0_pct=pct, gebaut=r["built"], V_TES_m3=round(r["V"]), E_TES_MWh=round(r["E"], 2),
                           Kosten_EUR=round(r["obj"]), dKosten_vs_S0_pct=None if s0 is None else round(100 * (r["obj"] - s0["obj"]) / s0["obj"], 2),
                           CO2_t=round(r["co2"], 1), Gap_pct=None if r["gap"] is None else round(100 * r["gap"], 2)))
    dfb = pd.DataFrame(be)
    dfb.to_csv(out / "step6_breakeven.csv", index=False, encoding="utf-8")
    md = ["# Schritt 6 — Modelloutput (keine Nachrechnung)\n", df.to_markdown(index=False), "\n\n## Break-even V_TES(c0)\n", dfb.to_markdown(index=False), "\n"]
    (out / "step6_report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
