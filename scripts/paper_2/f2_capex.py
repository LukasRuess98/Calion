"""F2 sizing curve: add post-hoc annualized degressive TES CAPEX to the fixed-rung
OPEX-TAC sweep (2026-09-12).

The fixed-rung TES-sweep runs carry NO TES capital cost in the model (non-investable
tank = no CAPEX by design). The paper's F2 curve is therefore reconstructed post-hoc:

    TAC_full(R) = OPEX_TAC(R) + ANF * C_degressive(V(R))         [rung R > 0]
    TAC_full(0) = S0 incumbent                                    [no storage]

with the SAME degressive per-tank cost the investable model would charge:
    V(R)  = R / (eta_strat * rho * cp * dT / 3.6e6)              physical volume [m3]
    N     = ceil(V / unit_tank)                                   identical tanks
    C     = N * c0 * ((V/N) / v0)^b                               per-tank degressive
    ANF   = i(1+i)^n / ((1+i)^n - 1)                              annuity factor

This is exact for the discrete ladder: argmin_R TAC_full(R) == the co-optimized MILP
over the same ladder (OPEX/dispatch is identical whether TES is 'fixed at R' or
'investable chosen to R'; only the CAPEX accounting is added here).

Usage:
  PYTHONPATH=. python scripts/paper_2/f2_capex.py MM --sweep-dir output/mm_s4_reconcile \
      --tag-prefix atmo_mm_ --s0 298691 [--out output/paper2_sweeps/f2_MM.csv]
"""
from __future__ import annotations
import argparse
import csv
import glob
import json
import math
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# Physical constants (match calion.constants / geometric_storage.py)
_RHO, _CP = 971.8, 4.189            # hot-water density [kg/m3], cp [kJ/kgK]


def _load_geom():
    import yaml
    g = (yaml.safe_load(open(_ROOT / "configs/paper_2/storage_geometry.yaml", encoding="utf-8"))
         or {}).get("storage_geometry", {})
    return g


def _anf(i: float, n: float) -> float:
    return i * (1 + i) ** n / ((1 + i) ** n - 1) if i > 0 else 1.0 / n


def _capex_from_V(V: float, *, c0: float, v0: float, b: float, unit: float,
                  anf: float) -> tuple[float, int]:
    """Return (annualized_capex_eur, N_tanks) for a tank of physical volume V [m3]."""
    if V <= 0:
        return 0.0, 0
    N = max(1, math.ceil(V / unit))
    C = N * c0 * ((V / N) / v0) ** b
    return anf * C, N


def _read_V_from_geometry(tag_dir: Path) -> float | None:
    """Read the MODEL-computed tank volume V_TES_m3 from a rung's geometry.csv
    (V embeds the correct scenario delta_T -- hot-charge scenarios have ~half the
    volume of normal-charge, so we must NOT re-derive V from a hardcoded dT)."""
    for g in tag_dir.glob("**/geometry.csv"):
        try:
            import csv as _csv
            for row in _csv.DictReader(open(g, encoding="utf-8")):
                v = row.get("V_TES_m3") or row.get("V_m3")
                if v not in (None, "", "0", "0.0"):
                    return float(v)
        except Exception:
            pass
    return None


def build(network: str, sweep_dir: Path, tag_prefix: str, s0: float, dT: float,
          out: Path) -> Path:
    g = _load_geom()
    asset = "tes_main" if network.upper().startswith("MM") else "tes_sb"
    pa = (g.get("per_asset") or {}).get(asset, {})
    eta = float(g.get("eta_strat", 0.85))
    c0 = float(g.get("c0_eur", 2_500_000.0))
    v0 = float(g.get("v0_m3", 10_000.0))
    b = float(g.get("exponent_b", 0.70))
    unit = float(pa.get("unit_tank_m3", g.get("unit_tank_m3", 10_000.0)))
    v_min = float(pa.get("v_min_realistic_m3", g.get("v_min_realistic_m3", 50.0)))
    ladder = list(pa.get("discrete_energies_mwh", []))
    anf = _anf(0.05, 30.0)

    rows = [{"rung_mwh": 0.0, "opex_tac": s0, "capex_annual": 0.0, "tac_full": s0,
             "V_m3": 0.0, "N_tanks": 0, "gap": "", "status": "S0_anchor"}]
    for R in ladder:
        if R <= 0:
            continue
        tag = f"{tag_prefix}{R:g}"
        tag_dir = sweep_dir / tag
        cand = glob.glob(str(tag_dir / "**" / "meta.json"), recursive=True)
        opex = gap = status = None
        if cand:
            d = json.loads(Path(cand[0]).read_text(encoding="utf-8"))
            opex = d.get("obj_eur") or d.get("incumbent")
            gap = d.get("mip_gap"); status = d.get("status")
        # V from the MODEL (geometry.csv) -- embeds the correct scenario dT. Fallback to
        # the dT-based estimate only if no geometry.csv (with a warning-worthy status).
        V = _read_V_from_geometry(tag_dir)
        v_src = "geometry.csv"
        if V is None:
            V = R / (eta * _RHO * _CP * dT / 3.6e6); v_src = f"est@dT={dT}"
        # v_min ENFORCEMENT: a physical tank below v_min is not buildable -> not a valid rung.
        if V < v_min:
            status = f"sub_v_min({V:.0f}<{v_min:.0f}m3)"
            rows.append({"rung_mwh": R, "opex_tac": opex, "capex_annual": "", "tac_full": "",
                         "V_m3": round(V), "N_tanks": 0, "gap": "", "status": status})
            continue
        cap, N = _capex_from_V(V, c0=c0, v0=v0, b=b, unit=unit, anf=anf)
        tac_full = (opex + cap) if isinstance(opex, (int, float)) else None
        rows.append({"rung_mwh": R, "opex_tac": opex, "capex_annual": round(cap),
                     "tac_full": round(tac_full) if tac_full else None,
                     "V_m3": round(V), "N_tanks": N,
                     "gap": round(gap * 100, 2) if isinstance(gap, (int, float)) else "",
                     "status": status})
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["rung_mwh", "opex_tac", "capex_annual", "tac_full",
                                          "V_m3", "N_tanks", "gap", "status"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    # report
    valid = [r for r in rows if isinstance(r["tac_full"], (int, float))]
    print(f"F2 curve [{network}] (ANF={anf:.4f}, eta={eta}, c0={c0:.0f}, b={b}, unit={unit:.0f}):")
    print(f"  {'R[MWh]':>7} {'OPEX':>11} {'+CAPEXann':>10} {'=TAC_full':>11} {'V[m3]':>8} N {'gap%':>6} status")
    for r in rows:
        o = r["opex_tac"]; tf = r["tac_full"]; ca = r["capex_annual"]
        os_ = f"{o:,.0f}" if isinstance(o, (int, float)) else "MISSING"
        cs_ = f"{ca:,.0f}" if isinstance(ca, (int, float)) else "-"
        ts_ = f"{tf:,.0f}" if isinstance(tf, (int, float)) else "--"
        print(f"  {r['rung_mwh']:>7g} {os_:>11} {cs_:>10} {ts_:>11} "
              f"{r['V_m3']:>8,} {r['N_tanks']} {str(r['gap']):>6} {r['status']}")
    best = min(valid, key=lambda r: r["tac_full"], default=None)
    if best:
        sav = 100.0 * (s0 - best["tac_full"]) / s0
        print(f"\n  ARGMIN TAC_full = {best['tac_full']:,.0f} EUR @ {best['rung_mwh']:g} MWh "
              f"| saving vs S0({s0:,.0f}) = {sav:.1f}%")
    print(f"  written -> {out}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("network", help="MM or SB")
    ap.add_argument("--sweep-dir", default="output/mm_s4_reconcile")
    ap.add_argument("--tag-prefix", required=True, help="e.g. atmo_mm_ or atmo_sb_")
    ap.add_argument("--s0", type=float, required=True, help="S0 (no-TES) incumbent [EUR]")
    ap.add_argument("--dt", type=float, default=15.0, help="scenario delta_T [K]")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = Path(a.out) if a.out else _ROOT / "output" / "paper2_sweeps" / f"f2_{a.network}.csv"
    build(a.network, _ROOT / a.sweep_dir, a.tag_prefix, a.s0, a.dt, out)
