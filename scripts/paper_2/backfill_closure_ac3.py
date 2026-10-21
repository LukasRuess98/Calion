"""AC3 (2026-10-19): apply the Z4 loss-inclusive closure formula to validation.json files that
still carry the stale lossless value. Old value is preserved in closure_fix_note; nothing else touched.
usage: python scripts/paper_2/backfill_closure_ac3.py <run_dir> [<run_dir> ...]"""
import json, sys
from pathlib import Path
import pandas as pd

for d in map(Path, sys.argv[1:]):
    vj = d / "validation.json"
    disp = pd.read_csv(d / "dispatch_hourly.csv")
    v = json.loads(vj.read_text(encoding="utf-8"))
    eb = v["energy_balance"]
    if "closure_fix_note" in eb:
        print(f"{d.name}: already fixed ({eb['closure_error_pct']} %) - skipped"); continue
    s = lambda c: disp[c].fillna(0).sum() if c in disp.columns else 0.0
    gen = sum(s(c) for c in ["Q_chp_MW", "Q_gasboiler_MW", "Q_biomass_MW", "Q_hp_total_MW", "Q_ek_MW"])
    supply = gen + s("Q_storage_discharge_MW") - s("Q_storage_charge_MW")
    dump = sum(s(c) for c in ["Q_dump_MW", "Q_dump_total_MW", "Q_curtail_MW", "Q_curtailment_MW"])
    losses, demand = s("Q_loss_total_MW"), s("Q_demand_total_MW")
    err = abs(supply - dump - losses - demand) / demand * 100
    old = (eb.get("closure_error_pct"), eb.get("closure_pass"))
    eb["closure_error_pct"] = round(err, 3); eb["closure_pass"] = bool(err <= 2.0)
    eb["closure_fix_note"] = (f"AC3 2026-10-19: losses now included (Z4 formula); was closure_error_pct={old[0]}, "
                              f"closure_pass={old[1]} under the stale lossless formula")
    vj.write_text(json.dumps(v, indent=2, default=str), encoding="utf-8")
    print(f"{d.name}: {old} -> ({eb['closure_error_pct']}, {eb['closure_pass']})")
