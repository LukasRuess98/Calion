"""AE3 (2026-10-22): connection-cost sweep as the RESULT axis.

For every sweep point (power cost 0 / 10 / 25 / 50 / 75 / 100 / 280 kEUR/MW_th) on SB-S1 it reports
built storage volume, chosen charge/discharge power, resulting E/P, full-equivalent cycles per year and
the storage-only value (TES-free reference vs the free run, Y1 gap-aware bounds), and the break-even
statement "the storage is built as long as the connection costs less than X kEUR/MW".

Reads the run directories under output/_ac (geometry.csv, meta.json, dispatch_hourly.csv).
Reference = ac3_s0free_notes if finished, else the proxy SB-S3 (no TES built).
usage: python scripts/paper_2/ae3_sweep_table.py
"""
import csv
import json
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[2]
O = R / "output"
OUT = R / "docs/paper_2/submission_pack/02_tables/tab_AE3_connection_cost_sweep.csv"

POINTS = [  # (kEUR/MW, run dir, note)
    (0, "_ac/ac5_k000/paper2_runs/SB-S1-HK0", "new model"),
    (10, "_ac/ac5_k010/paper2_runs/SB-S1-HK0", "new model"),
    (25, "_ac/ac5_k025/paper2_runs/SB-S1-HK0", "new model"),
    (50, "_ac/ac5_k050/paper2_runs/SB-S1-HK0", "new model"),
    (75, "_ac/ac1_p3_low75k/paper2_runs/SB-S1-HK0", "started before AE1: E/P<=4 h bound, no hydraulic cap, H/D 2, no height cap"),
    (100, "_ac/ac5_k100/paper2_runs/SB-S1-HK0", "new model"),
    (280, "_ac/ac1_p1_c0x1.0/paper2_runs/SB-S1-HK0", "stress test (transmission station, outside scope); old geometry"),
]
PIN0 = "v7_final/SB-S0-HK0-PIN0"
HYD_CAP_MW = 51.8
REFS = [("ac3_s0free_notes", "_ac/ac3_s0free_notes/paper2_runs/SB-S0-HK0"),
        ("proxy SB-S3 (no TES built)", "_s2/sb_s3_resolve/paper2_runs/SB-S3-HK0")]
ANCHORS = {"bottom-up AE2 (22-34, mid 28)": (22.2, 34.2), "house-substation upper anchor (70)": (70.0, 70.0),
           "transmission station stress (280)": (280.0, 280.0)}


def load(d):
    d = O / d
    m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    ub, gap = float(m["obj_eur"]), float(m.get("mip_gap") or 0.0)
    g = list(csv.DictReader(open(d / "geometry.csv")))[0]
    disp = pd.read_csv(d / "dispatch_hourly.csv")
    qd = disp["Q_storage_discharge_MW"].fillna(0).sum() if "Q_storage_discharge_MW" in disp else 0.0
    E = float(g["E_TES_max_MWh"])
    P = float(g["cap_power_MW"])
    return dict(ub=ub, lb=ub * (1 - gap), gap=100 * gap, V=float(g["V_TES_m3"]), E=E, P=P,
                ep=(E / P if P > 0 else None), cycles=(qd / E if E > 0 else 0.0),
                peak=float(disp["Q_storage_charge_MW"].max()) if "Q_storage_charge_MW" in disp else None,
                n_tanks=g.get("n_tanks"), status=m.get("status"))


def ref():
    for lab, d in REFS:
        if (O / d / "meta.json").exists():
            return lab, load(d)
    raise SystemExit("no TES-free reference available")


def main():
    rl, Rf = ref()
    rows = []
    for k, d, note in POINTS:
        if not (O / d / "meta.json").exists():
            continue
        F = load(d)
        # AF3: P3 ran without the hydraulic cap and with H/D 2 -> keep it ONLY if the chosen power is within
        # the 51.8 MW cap (and then it is comparable only because no storage resp. <= cap was chosen);
        # otherwise DISCARD (never patched).
        if d.startswith("_ac/ac1_p3") and F["P"] > HYD_CAP_MW + 1e-6:
            print(f"P3 DISCARDED: chosen power {F['P']:.1f} MW > hydraulic cap {HYD_CAP_MW} MW (ran without cap, H/D 2)")
            continue
        lo = max(0.0, Rf["lb"] - F["ub"]); hi = Rf["ub"] - F["lb"]
        rows.append({"conn_cost_kEUR_per_MW": k, "run": d.split("/")[1], "obj_eur": round(F["ub"]), "gap_pct": round(F["gap"], 4),
                     "V_TES_m3": F["V"], "n_tanks": F["n_tanks"], "E_MWh": F["E"], "chosen_power_MW": F["P"],
                     "E_over_P_h": None if F["ep"] is None else round(F["ep"], 2),
                     "peak_charge_MW": None if F["peak"] is None else round(F["peak"], 1),
                     "full_cycles_per_a": round(F["cycles"], 1),
                     "storage_only_lo_eur_a": round(lo), "storage_only_hi_eur_a": round(hi),
                     "reference": rl, "note": note})
    if not rows:
        print("no sweep run finished yet"); return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"reference: {rl}")
    for r in rows:
        print(f"{r['conn_cost_kEUR_per_MW']:>4} kEUR/MW  V={r['V_TES_m3']:>9,.0f} m3  P={r['chosen_power_MW']:6.1f} MW  "
              f"E/P={r['E_over_P_h']}  cycles={r['full_cycles_per_a']}  storage-only [{r['storage_only_lo_eur_a']:,}; "
              f"{r['storage_only_hi_eur_a']:,}]  gap {r['gap_pct']}%  ({r['note']})")
    built = [r for r in rows if r["V_TES_m3"] > 0]
    notb = [r for r in rows if r["V_TES_m3"] == 0]
    if built and notb:
        x_lo = max(r["conn_cost_kEUR_per_MW"] for r in built)
        x_hi = min(r["conn_cost_kEUR_per_MW"] for r in notb if r["conn_cost_kEUR_per_MW"] > x_lo)
        print(f"\nBREAK-EVEN: the storage is built up to {x_lo} kEUR/MW and no longer at {x_hi} kEUR/MW "
              f"(between the two sweep points).")
        for name, (a, b) in ANCHORS.items():
            side = "below" if b < x_hi and a <= x_lo else ("above" if a >= x_hi else "straddles")
            print(f"  anchor {name}: {side} the break-even interval [{x_lo}, {x_hi}]")
    elif built and not notb:
        print("\nstorage built at every sweep point so far: break-even above", max(r["conn_cost_kEUR_per_MW"] for r in built))
    else:
        print("\nno storage built at any finished sweep point: break-even below", min(r["conn_cost_kEUR_per_MW"] for r in rows))


if __name__ == "__main__":
    main()
