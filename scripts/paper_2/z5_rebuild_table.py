"""Z5 table rebuild (AC3, 2026-10-19).

The original tab_Z5_sb_mm_s1_sweep_and_sensitivities.csv (docs SS4cn) and its generating
script were not found in the workspace on 2026-10-19; this rebuilds the table directly from the
solved run directories (meta.json / geometry.csv / run_export.json) -- nothing typed by hand.

Value interval per pair (Y1 structural-bound method, docs SS4cb):
    LB(run) = obj*(1-gap)           (Gurobi MIPGap is relative to the incumbent)
    value in [ max(0, LB(PIN0) - UB(free)) , UB(PIN0) - LB(free) ]   [EUR/yr]
PIN0 is a restriction of the free problem, so Free_true <= PIN0_true holds structurally.
"""
import csv, json
from pathlib import Path

R = Path(__file__).resolve().parents[2]
O = R / "output"

def load(d):
    d = O / d
    m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    g = list(csv.DictReader(open(d / "geometry.csv"))) if (d / "geometry.csv").exists() else []
    re = json.loads((d / "run_export.json").read_text(encoding="utf-8")) if (d / "run_export.json").exists() else {}
    ub = float(m["obj_eur"]); gap = float(m.get("mip_gap") or 0.0)
    # meta.json 'solution_count' is UNRELIABLE (always 1) -> read the Gurobi log's 'Solution count' line.
    sc = None
    for lg in (d.parent.parent / "logs").glob("gurobi_*.log") if (d.parent.parent / "logs").exists() else []:
        if lg.stem.replace("gurobi_", "") == d.name:
            for line in lg.read_text(errors="ignore").splitlines():
                if line.startswith("Solution count"):
                    sc = int(line.split()[2].rstrip(":"))
    return dict(ub=ub, gap=gap, lb=ub * (1 - gap), status=m.get("status"), sc=sc,
                V=float(g[0]["V_TES_m3"]) if g else None, E=float(g[0]["E_TES_max_MWh"]) if g else None,
                hash=Path(re.get("export_dir", "")).name or None, rel=str(d.relative_to(O)).replace("\\", "/"))

SB_PIN0, MM_PIN0 = "v7_final/SB-S0-HK0-PIN0", "v7_final/MM-S0-HK0-PIN0"
PAIRS = [  # (net, label, pin0_dir, free_dir, cost spec EUR/m3 note)
    ("SB", "base c0x1.0", SB_PIN0, "v7_final/SB-S1-HK0"),
    ("SB", "c0x1.3", SB_PIN0, "_parallel_aa3/c0x1.3/paper2_runs/SB-S1-HK0"),
    ("SB", "c0x1.5", SB_PIN0, "_parallel_aa3/c0x1.5/paper2_runs/SB-S1-HK0"),
    ("SB", "c0x2.0", SB_PIN0, "_parallel_aa3/c0x2.0/paper2_runs/SB-S1-HK0"),
    ("SB", "grid fee -50%", "_z3/sb_pin0_netz50/paper2_runs/SB-S1-HK0-PIN0-NETZ50", "_z3/sb_free_netz50/paper2_runs/SB-S1-HK0-NETZ50"),
    ("SB", "monthly billing", "_z3/sb_pin0_monthly/paper2_runs/SB-S1-HK0-PIN0-MONTHLY", "_z3/sb_free_monthly/paper2_runs/SB-S1-HK0-MONTHLY"),
    ("SB", "marketing -2 EUR/MWh", "_z3b/sb_pin0_vermarkt2/paper2_runs/SB-S1-HK0-PIN0-VERMARKT2", "_z3b/sb_free_vermarkt2/paper2_runs/SB-S1-HK0-VERMARKT2"),
    ("SB", "price amplitude x1.5", "_z3b/sb_pin0_spreiz15/paper2_runs/SB-S1-HK0-PIN0-SPREIZ15", "_z3b/sb_free_spreiz15/paper2_runs/SB-S1-HK0-SPREIZ15"),
    ("SB", "price amplitude x2.0", "_z3b/sb_pin0_spreiz20/paper2_runs/SB-S1-HK0-PIN0-SPREIZ20", "_z3b/sb_free_spreiz20/paper2_runs/SB-S1-HK0-SPREIZ20"),
    ("MM", "base", MM_PIN0, "v7_final/MM-S1-HK0"),
    ("MM", "grid fee -50%", "_z3/mm_pin0_netz50/paper2_runs/MM-S1-HK0-PIN0-NETZ50", "_z3/mm_free_netz50/paper2_runs/MM-S1-HK0-NETZ50"),
    ("MM", "monthly billing", "_z3/mm_pin0_monthly/paper2_runs/MM-S1-HK0-PIN0-MONTHLY", "_z3/mm_free_monthly/paper2_runs/MM-S1-HK0-MONTHLY"),
    ("MM", "marketing -2 EUR/MWh", "_z3b/mm_pin0_vermarkt2/paper2_runs/MM-S1-HK0-PIN0-VERMARKT2", "_z3b/mm_free_vermarkt2/paper2_runs/MM-S1-HK0-VERMARKT2"),
    ("MM", "price amplitude x1.5", "_z3b/mm_pin0_spreiz15/paper2_runs/MM-S1-HK0-PIN0-SPREIZ15", "_z3b/mm_free_spreiz15/paper2_runs/MM-S1-HK0-SPREIZ15"),
    ("MM", "price amplitude x2.0", "_z3b/mm_pin0_spreiz20/paper2_runs/MM-S1-HK0-PIN0-SPREIZ20", "_z3b/mm_free_spreiz20/paper2_runs/MM-S1-HK0-SPREIZ20"),
]

def main(out):
    rows = []
    for net, lab, p, f in PAIRS:
        P, F = load(p), load(f)
        lo = max(0.0, P["lb"] - F["ub"]); hi = P["ub"] - F["lb"]
        rows.append({
            "network": net, "case": lab,
            "pin0_dir": P["rel"], "free_dir": F["rel"],
            "pin0_obj_eur": round(P["ub"], 2), "pin0_gap_pct": round(100 * P["gap"], 4),
            "free_obj_eur": round(F["ub"], 2), "free_gap_pct": round(100 * F["gap"], 4),
            "free_status": F["status"], "free_solution_count": F["sc"],
            "V_TES_m3": F["V"], "E_TES_MWh": F["E"],
            "value_lo_eur_a": round(lo, 0), "value_hi_eur_a": round(hi, 0),
            "value_hi_pct_of_pin0_tac": round(100 * hi / P["ub"], 3),
            "free_export_hash": F["hash"],
            "caveat": ("solution_count==1: size never left the warm start -> obj is an upper bound "
                       "(valid for the interval's lower end, may overstate the optimum)") if F["sc"] == 1 and F["V"] else ("" if F["sc"] else "solution count not recoverable from a run-local Gurobi log"),
        })
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for r in rows:
        print(f"{r['network']} {r['case']:24s} [{r['value_lo_eur_a']:>10,.0f}; {r['value_hi_eur_a']:>10,.0f}] "
              f"V={r['V_TES_m3']} sc={r['free_solution_count']} gap={r['free_gap_pct']}%")

if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else R / "docs/paper_2/submission_pack/02_tables/tab_Z5_sb_mm_s1_sweep_and_sensitivities.csv")
