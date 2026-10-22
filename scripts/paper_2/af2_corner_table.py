"""AF2 (2026-10-22): the decisive corner -- German tank price (c0 x2.0, ~500 EUR/m3 at 10,000 m3 ~ KWW 530)
with a realistic connection cost (25 kEUR/MW, upper variant 50 kEUR/MW), endogenous power, hydraulic cap
51.8 MW, H/D 1.5 with 45 m cap; each against PIN0 and the TES-free reference.

Output per run: built V_TES, vessels, chosen power, E/P, full-equivalent cycles, EUR/m3 OF THE BUILT SIZE
(capex / V with the per-vessel cost curve c0 * (v/N / v0)^b), storage-only value interval (Y1 gap-aware bounds),
package value vs PIN0.   usage: python scripts/paper_2/af2_corner_table.py
"""
import csv
import json
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[2]
O = R / "output"
OUT = R / "docs/paper_2/submission_pack/02_tables/tab_AF2_decisive_corner.csv"
C0_BASE, V0, B = 2_500_000.0, 10_000.0, 0.70
PIN0 = "v7_final/SB-S0-HK0-PIN0"
RUNS = [  # (label, run dir, c0 scale, connection kEUR/MW)
    ("German tank price x2.0, connection 25 kEUR/MW", "_ac/ac6_c20_k025/paper2_runs/SB-S1-HK0", 2.0, 25),
    ("German tank price x2.0, connection 50 kEUR/MW", "_ac/ac6_c20_k050/paper2_runs/SB-S1-HK0", 2.0, 50),
]
REFS = [("ac3_s0free_notes", "_ac/ac3_s0free_notes/paper2_runs/SB-S0-HK0"),
        ("proxy SB-S3 (no TES built)", "_s2/sb_s3_resolve/paper2_runs/SB-S3-HK0")]


def load(d):
    d = O / d
    m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    ub, gap = float(m["obj_eur"]), float(m.get("mip_gap") or 0.0)
    g = list(csv.DictReader(open(d / "geometry.csv")))[0]
    disp = pd.read_csv(d / "dispatch_hourly.csv")
    qd = float(disp["Q_storage_discharge_MW"].fillna(0).sum()) if "Q_storage_discharge_MW" in disp else 0.0
    V, E, P = float(g["V_TES_m3"]), float(g["E_TES_max_MWh"]), float(g["cap_power_MW"])
    n = int(float(g.get("n_tanks") or 0))
    return dict(ub=ub, lb=ub * (1 - gap), gap=100 * gap, V=V, E=E, P=P, n=n, status=m.get("status"),
                cycles=(qd / E if E > 0 else 0.0))


def eur_per_m3(V, n, c0_scale):
    if V <= 0 or n <= 0:
        return None
    return n * C0_BASE * c0_scale * ((V / n) / V0) ** B / V


def main():
    ref = None
    for lab, d in REFS:
        if (O / d / "meta.json").exists():
            ref = (lab, load(d)); break
    P0 = load(PIN0)
    rows = []
    for lab, d, c0s, kc in RUNS:
        if not (O / d / "meta.json").exists():
            print("not finished:", d); continue
        F = load(d)
        lo = max(0.0, ref[1]["lb"] - F["ub"]); hi = ref[1]["ub"] - F["lb"]
        plo = max(0.0, P0["lb"] - F["ub"]); phi = P0["ub"] - F["lb"]
        rows.append({"case": lab, "c0_scale": c0s, "connection_kEUR_per_MW": kc, "obj_eur": round(F["ub"]),
                     "gap_pct": round(F["gap"], 4), "status": F["status"], "V_TES_m3": F["V"], "vessels": F["n"],
                     "chosen_power_MW": F["P"], "E_MWh": F["E"],
                     "E_over_P_h": None if F["P"] <= 0 else round(F["E"] / F["P"], 2),
                     "full_cycles_per_a": round(F["cycles"], 1),
                     "eur_per_m3_built": None if eur_per_m3(F["V"], F["n"], c0s) is None else round(eur_per_m3(F["V"], F["n"], c0s), 1),
                     "storage_only_lo_eur_a": round(lo), "storage_only_hi_eur_a": round(hi),
                     "package_lo_eur_a": round(plo), "package_hi_eur_a": round(phi), "reference": ref[0]})
    if not rows:
        print("no decisive run finished yet"); return
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for r in rows:
        print(f"{r['case']}: V={r['V_TES_m3']:,.0f} m3 ({r['vessels']} vessel), P={r['chosen_power_MW']} MW, E/P={r['E_over_P_h']} h, "
              f"cycles={r['full_cycles_per_a']}, {r['eur_per_m3_built']} EUR/m3 built, storage-only "
              f"[{r['storage_only_lo_eur_a']:,}; {r['storage_only_hi_eur_a']:,}] EUR/a, package [{r['package_lo_eur_a']:,}; {r['package_hi_eur_a']:,}], "
              f"gap {r['gap_pct']}%, ref = {r['reference']}")


if __name__ == "__main__":
    main()
