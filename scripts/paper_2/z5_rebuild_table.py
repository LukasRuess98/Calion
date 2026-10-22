"""Z5 table rebuild (AC3, 2026-10-19).

The original tab_Z5_sb_mm_s1_sweep_and_sensitivities.csv (docs SS4cn) and its generating
script were not found in the workspace on 2026-10-19; this rebuilds the table directly from the
solved run directories (meta.json / geometry.csv / run_export.json) -- nothing typed by hand.

Two columns (AC, 2026-10-21): "package" = PIN0 vs free (HP+EK+TES together, the old Z5 definition) and
"storage_only" = TES-free reference (HP/EK free, no storage) vs free, i.e. the value of the storage alone.
Output: tab_Z5b_package_vs_storage_only.csv (the committed tab_Z5_... stays untouched).

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

# TES-free reference runs (HP/EK free, no storage built) for the PURE storage value.
# Preferred: the dedicated clean reference run; fallback PROXY: runs whose siting allowed TES but built none.
REFS = {
    "SB": [("ac3_s0free_notes", "_ac/ac3_s0free_notes/paper2_runs/SB-S0-HK0"),
           ("proxy SB-S3 (no TES built)", "_s2/sb_s3_resolve/paper2_runs/SB-S3-HK0")],
    "MM": [("proxy MM-S2 (no TES built)", "v7_final/MM-S2-HK0")],
}
# AC rows (new model): only listed if the run exists on disk
AC_ROWS = [   # (net, label, pin0_dir, free_dir[, own TES-free reference dir])
    ("SB", "AC1 stress: power 280,274 EUR/MW (scope-mismatched, withdrawn as base)", SB_PIN0, "_ac/ac1_p1_c0x1.0/paper2_runs/SB-S1-HK0"),
    ("SB", "AC1 high: power 75,185 EUR/MW, c0x1.0", SB_PIN0, "_ac/ac1_p3_low75k/paper2_runs/SB-S1-HK0"),
    ("SB", "AD1 mid: power 22,100 EUR/MW, c0x1.0, H/D 1.5, h<=45 m", SB_PIN0, "_ac/ac4_mid22k/paper2_runs/SB-S1-HK0"),
    ("SB", "AD1 low: power 8,800 EUR/MW, c0x1.0, H/D 1.5, h<=45 m", SB_PIN0, "_ac/ac4_low9k/paper2_runs/SB-S1-HK0"),
    ("SB", "AD1 mid, c0x1.5", SB_PIN0, "_ac/ac4_mid22k_c1.5/paper2_runs/SB-S1-HK0"),
    ("SB", "AD2 mid, E/P >= 8 h", SB_PIN0, "_ac/ac4_mid22k_ep8/paper2_runs/SB-S1-HK0"),
    ("SB", "AD2 mid, E/P >= 12 h", SB_PIN0, "_ac/ac4_mid22k_ep12/paper2_runs/SB-S1-HK0"),
    ("SB", "AD5 mid, H/D 2.0 (geometry sensitivity)", SB_PIN0, "_ac/ac4_mid22k_hd2/paper2_runs/SB-S1-HK0"),
    ("SB", "AD4 mid, price amplitude x1.5", "_z3b/sb_pin0_spreiz15/paper2_runs/SB-S1-HK0-PIN0-SPREIZ15",
     "_ac/ac4_spreiz15_mid/paper2_runs/SB-S1-HK0-SPREIZ15", "_ac/ac4_ref_spreiz15/paper2_runs/SB-S0-HK0-SPREIZ15"),
    ("SB", "AD4 mid, price amplitude x2.0", "_z3b/sb_pin0_spreiz20/paper2_runs/SB-S1-HK0-PIN0-SPREIZ20",
     "_ac/ac4_spreiz20_mid/paper2_runs/SB-S1-HK0-SPREIZ20", "_ac/ac4_ref_spreiz20/paper2_runs/SB-S0-HK0-SPREIZ20"),
]
BASE_ROWS = {"base c0x1.0", "c0x1.3", "c0x1.5", "c0x2.0", "base"}  # rows with a valid TES-free reference


def pick_ref(net):
    for lab, d in REFS[net]:
        if (O / d / "meta.json").exists():
            return lab, load(d)
    return None, None


def main(out):
    rows = []
    all_pairs = list(PAIRS) + [r for r in AC_ROWS if (O / r[3] / "meta.json").exists()]
    for row in all_pairs:
        net, lab, p, f = row[:4]
        own_ref = row[4] if len(row) > 4 else None
        P, F = load(p), load(f)
        lo = max(0.0, P["lb"] - F["ub"]); hi = P["ub"] - F["lb"]
        # PURE storage value = TES-free reference vs the free run (valid only where the case has its own
        # TES-free reference, i.e. the cost/price/geometry cases of the base tariff -- not the tariff
        # sensitivities, which would need a TES-free run each).
        if own_ref is not None:
            rl, R = (("own: " + own_ref.split("/")[1]), load(own_ref)) if (O / own_ref / "meta.json").exists() else (None, None)
        else:
            has_ref = (lab in BASE_ROWS) or lab.startswith(("AC", "AD"))
            rl, R = pick_ref(net) if has_ref else (None, None)
        if R is not None:
            s_lo = max(0.0, R["lb"] - F["ub"]); s_hi = R["ub"] - F["lb"]
        elif F["V"] == 0:
            # AD4: no storage built in the free run -> the storage-only value is 0 by construction
            s_lo = s_hi = 0.0
            rl, R = "no storage built (V_TES = 0): value = 0", True
        else:
            s_lo = s_hi = None
        rows.append({
            "network": net, "case": lab,
            "pin0_dir": P["rel"], "free_dir": F["rel"],
            "pin0_obj_eur": round(P["ub"], 2), "pin0_gap_pct": round(100 * P["gap"], 4),
            "free_obj_eur": round(F["ub"], 2), "free_gap_pct": round(100 * F["gap"], 4),
            "free_status": F["status"], "free_solution_count": F["sc"],
            "V_TES_m3": F["V"], "E_TES_MWh": F["E"],
            "value_lo_eur_a": round(lo, 0), "value_hi_eur_a": round(hi, 0),
            "value_hi_pct_of_pin0_tac": round(100 * hi / P["ub"], 3),
            "package_value_lo_eur_a": round(lo, 0), "package_value_hi_eur_a": round(hi, 0),
            "storage_only_lo_eur_a": None if s_lo is None else round(s_lo, 0),
            "storage_only_hi_eur_a": None if s_hi is None else round(s_hi, 0),
            "storage_only_reference": rl if R is not None else "n/a (TES-free reference for this tariff case not run)",
            "free_export_hash": F["hash"],
            "caveat": ("solution_count==1: size never left the warm start -> obj is an upper bound "
                       "(valid for the interval's lower end, may overstate the optimum)") if F["sc"] == 1 and F["V"] else ("" if F["sc"] else "solution count not recoverable from a run-local Gurobi log"),
        })
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for r in rows:
        so = "n/a" if r["storage_only_lo_eur_a"] is None else f"[{r['storage_only_lo_eur_a']:,.0f}; {r['storage_only_hi_eur_a']:,.0f}]"
        print(f"{r['network']} {r['case']:42s} package [{r['value_lo_eur_a']:>9,.0f}; {r['value_hi_eur_a']:>9,.0f}]  "
              f"storage-only {so:>20s}  V={r['V_TES_m3']} sc={r['free_solution_count']} gap={r['free_gap_pct']}%")

if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else R / "docs/paper_2/submission_pack/02_tables/tab_Z5b_package_vs_storage_only.csv")
