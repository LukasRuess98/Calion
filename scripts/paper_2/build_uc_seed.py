"""Build a full-year UC seed by rolling-horizon monthly decomposition + COMPLETE dump.

The full-year investment MILP is heuristic-limited (Gurobi finds a poor incumbent it
can't improve; the frozen campaign hit maxTimeLimit on it). Each CALENDAR MONTH with
min_load solves in minutes, so: solve the 12 months SEQUENTIALLY (end-SoC -> next
month's start-SoC, so the seed's storage state is physically continuous, not 12
independent cycles), dump the FULL Pyomo solution of each month, and stitch them into a
complete full-year assignment used as a COMPLETE MIP start (all decision vars set ->
Gurobi accepts it as the incumbent instead of completing a fixed-commitment LP that goes
infeasible, which is why partial commitment-only hints were rejected 4x).

Time index is positional (RangeSet 1..T per month), so each month's indices are remapped
to the absolute year index by the cumulative hour offset. One seed per (network x HK).
TES fixed at v_seed for the seed months (constant E_max for the SoC hand-off); the
full-year run optimises TES freely from the seeded start. December uses the year model's
terminal (soc0=terminal=0.5) so the concat satisfies the cyclic boundary.

Usage:
    PYTHONPATH=. python scripts/paper_2/build_uc_seed.py MM-S1-HK0 [v_seed_MWh=2.2] [year=2025]
Output:
    output/uc_seed/<scenario_id>/vars_seed.json   ({component: {abs_index: value}}) -> CALION_WARMSTART_DUMP
"""
from __future__ import annotations
import calendar
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
from scripts.paper_2 import scenario_runner as sr  # noqa: E402


def _is_int_key(k: str) -> bool:
    try:
        int(k); return True
    except ValueError:
        return False


def build_seed(scen_id: str, v_seed: float = 2.2, year: int = 2025) -> Path:
    seed_root = _ROOT / "output" / "uc_seed" / scen_id
    (seed_root / "runs").mkdir(parents=True, exist_ok=True)
    full_vars: dict[str, dict[str, float]] = {}
    offset = 0          # cumulative hours before the current month
    soc0 = 0.5          # year model's soc0_fraction (Jan starts here)
    orig_out = sr.OUT_BASE
    print(f"[seed] {scen_id}: v_seed={v_seed} MWh, {year}, 12 months, SoC hand-off + full dump")
    try:
        for m in range(1, 13):
            ld = calendar.monthrange(year, m)[1]
            mrun = seed_root / "runs" / f"m{m:02d}"
            dump_path = mrun / "vars_dump.json"
            env = {
                "CALION_HORIZON_START": f"{year}-{m:02d}-01 00:00",
                "CALION_HORIZON_END": f"{year}-{m:02d}-{ld:02d} 23:00",
                "CALION_TES_FIX_MWH": str(v_seed),
                "CALION_SOC0_FRAC": f"{soc0:.4f}",
                "CALION_DUMP_VARS": str(dump_path),
            }
            # Last month: match the year model's cyclic terminal so the concat is feasible.
            if m == 12:
                env["CALION_SOC_TERMINAL"] = "0.5"
            os.environ.update(env)
            sr.OUT_BASE = mrun
            res = sr.run_all_scenarios(scenario_ids=[scen_id], dry_run=False,
                                       force_rerun=True, gurobi_threads=4)
            st = (res[0].get("status") if res else "?")
            if not dump_path.exists():
                raise RuntimeError(f"month {m:02d} produced no var dump ({st}) — see log")
            dump = json.loads(dump_path.read_text(encoding="utf-8"))
            mvars = dump["vars"]
            T_month = ld * 24  # REAL hours this month (dump['T']=max tuple-var count, wrong)
            # accumulate: time-indexed vars (all-int keys, ~T_month entries) -> remap by
            # offset; non-time / non-tuple vars (investment, scalar) -> write once; tuple-
            # indexed (derived pipe/temp vars) -> skip (Gurobi completes them linearly).
            n_t = n_o = 0
            for comp, d in mvars.items():
                keys = list(d.keys())
                time_like = keys and all(_is_int_key(k) for k in keys) and len(d) >= 0.9 * T_month
                if time_like:
                    tgt = full_vars.setdefault(comp, {})
                    for k, val in d.items():
                        tgt[str(offset + int(k))] = val
                    n_t += 1
                elif keys and all(not (k.startswith("(") ) for k in keys):
                    full_vars.setdefault(comp, {}).update(d)  # investment/scalar (overwrite ok)
                    n_o += 1
            # SoC hand-off: read final SoC from the dumped E var (…_E) if present
            _e = next((c for c in mvars if c.endswith("_E")), None)
            final_soc = 0.0
            if _e:
                _last = str(max(int(k) for k in mvars[_e] if _is_int_key(k)))
                final_soc = float(mvars[_e].get(_last, 0.0))
            soc0 = min(max(final_soc / v_seed, 0.0), 1.0)
            offset += T_month
            print(f"  m{m:02d}: T={T_month:3d} status={st} time-vars={n_t} inv-vars={n_o} "
                  f"final_SOC={final_soc:.2f} -> next soc0={soc0:.3f}")
    finally:
        sr.OUT_BASE = orig_out
        for k in ("CALION_HORIZON_START", "CALION_HORIZON_END", "CALION_TES_FIX_MWH",
                  "CALION_SOC0_FRAC", "CALION_DUMP_VARS", "CALION_SOC_TERMINAL"):
            os.environ.pop(k, None)

    out = seed_root / "vars_seed.json"
    out.write_text(json.dumps({"total_h": offset, "vars": full_vars}), encoding="utf-8")
    n_vals = sum(len(v) for v in full_vars.values())
    print(f"[seed] wrote {out}: {len(full_vars)} components, {n_vals} values, {offset} h "
          f"— use CALION_WARMSTART_DUMP={out}")
    return out


def reaccumulate(scen_id: str, year: int = 2025) -> Path:
    """Rebuild vars_seed.json from EXISTING monthly vars_dump.json (no solving).

    Uses the KNOWN month hour count (not dump['T']) to classify time-indexed vars.
    """
    seed_root = _ROOT / "output" / "uc_seed" / scen_id
    full_vars: dict[str, dict[str, float]] = {}
    offset = 0
    for m in range(1, 13):
        ld = calendar.monthrange(year, m)[1]
        T_month = ld * 24
        dpath = seed_root / "runs" / f"m{m:02d}" / "vars_dump.json"
        if not dpath.exists():
            raise RuntimeError(f"missing dump for month {m:02d}: {dpath}")
        mvars = json.loads(dpath.read_text(encoding="utf-8"))["vars"]
        n_t = 0
        for comp, d in mvars.items():
            keys = list(d.keys())
            if keys and all(_is_int_key(k) for k in keys) and len(d) >= 0.9 * T_month:
                tgt = full_vars.setdefault(comp, {})
                for k, val in d.items():
                    tgt[str(offset + int(k))] = val
                n_t += 1
            elif keys and all(not k.startswith("(") for k in keys):
                full_vars.setdefault(comp, {}).update(d)
        print(f"  m{m:02d}: T={T_month} time-vars={n_t}")
        offset += T_month
    out = seed_root / "vars_seed.json"
    out.write_text(json.dumps({"total_h": offset, "vars": full_vars}), encoding="utf-8")
    n_vals = sum(len(v) for v in full_vars.values())
    print(f"[reaccumulate] {out}: {len(full_vars)} components, {n_vals} values, {offset} h")
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reaccumulate":
        reaccumulate(sys.argv[2] if len(sys.argv) > 2 else "MM-S1-HK0")
        sys.exit(0)
    scen = sys.argv[1] if len(sys.argv) > 1 else "MM-S1-HK0"
    v = float(sys.argv[2]) if len(sys.argv) > 2 else 2.2
    yr = int(sys.argv[3]) if len(sys.argv) > 3 else 2025
    build_seed(scen, v, yr)
