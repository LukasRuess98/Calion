"""
Fill the synthetic factorial to a BALANCED 135-cell grid (Paper 1 R2.5 / R-synth).

Design: N{5,15,30} x L{1,5,15,30,50}km x HI{0.1,0.4,0.8} x S{2,6,12} = 135 cells.
The n30_L1km cells (avg edge 34.5 m) are INCLUDED here as legitimate dense micro-grids
(the committed gen_synth 50 m edge floor is only a realism guard, not a physics limit;
34.5 m spacing is realistic for a dense urban block and the MILP solves fine -- low
per-pipe flow, no velocity issue).

SAFETY -- why this does not contaminate the existing 42 cells:
  The committed `gen_synth.build_config()` has DRIFTED from the configs that produced the
  paper's synth runs: it now emits costs.co2_price=1000 (real: 100), site.input_xlsx=
  2025_04_14_... (real: Import_Data_Memmingen_epronet.xlsx), and a different HP/TES asset
  schema. BUT its TOPOLOGY generation (nodes, pipes, DN sizing, demand fractions,
  network envelope: velocity/PWL/ground_temp) is byte-faithful to the stored configs
  (verified). So we generate topology with build_config, then OVERRIDE exactly the three
  drifted sections {costs, site, assets} from an existing stored config used as template
  (TES energy/soc re-sized by storage_h). Result: new cells are structurally identical to
  the existing 42 except their (independent, per-cell-seeded) demand-fraction draws -- which
  is correct: each factorial cell is one i.i.d. network instance at its design point.

  Existing {net}.yaml / {net}_L1cp.yaml are NEVER overwritten (skip-if-exists).

After running this, run  tools/gen_synth_copperplate.py  to emit _L1cp for the new bases,
then  scripts/paper/_run_synth_factorial.py  (in the worktree) which auto-discovers all
_L1cp nets and solves the 3 cells each, skipping existing.

Usage:
    python tools/fill_synth_grid.py --verify        # reproduce an existing cell, prove parity
    python tools/fill_synth_grid.py --dry-run       # list missing cells, write nothing
    python tools/fill_synth_grid.py                 # write missing base configs
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import gen_synth as G  # noqa: E402

# The factorial solver (scripts/paper/_run_synth_factorial.py) reads the WORKTREE's
# synth_configs/, so we generate there. (Topology helpers from main's gen_synth are
# byte-faithful to the worktree configs -- verified; templates are content-identical.)
WORKTREE = (ROOT / ".." / "paper1_faithful_c19d690").resolve()
SYNTH = WORKTREE / "synth_configs"
TEMPLATE_STEM = "synth_n05_L15p0km_hi0p1_s6h"  # an existing, real-lineage base config

N_NODES = [5, 15, 30]
LENGTHS_KM = [1.0, 5.0, 15.0, 30.0, 50.0]
HI_LEVELS = [0.1, 0.4, 0.8]
STORAGE_H = [2, 6, 12]
PEAK_MW = G.PEAK_DEMAND_MW
MIN_EDGE_M = 30.0  # relaxed from gen_synth's 50 m so n30_L1 (34.5 m) is admitted


def _name(n, L, hi, s):
    return (f"synth_n{n:02d}_L{str(L).replace('.', 'p')}km"
            f"_hi{str(hi).replace('.', 'p')}_s{s}h")


def _feasible(n, L):
    n_pipes = n - 1
    return not (n_pipes > 0 and (L * 1000 / n_pipes) < MIN_EDGE_M)


def _cell_seed(name):
    return int(hashlib.sha1(name.encode()).hexdigest(), 16) % (2 ** 31)


def _load_template():
    return yaml.safe_load((SYNTH / f"{TEMPLATE_STEM}.yaml").read_text(encoding="utf-8"))


def _build(n, L, hi, s, template):
    """Faithful topology via build_config, drifted envelope overridden from template."""
    name = _name(n, L, hi, s)
    seed = _cell_seed(name)
    fracs = G._gini_allocations(n, hi, seed)
    pipes = G._balanced_tree_pipes(n, L, fracs, PEAK_MW, seed)
    cfg = G.build_config({"n_nodes": n, "length_km": L, "hi": hi, "storage_h": s}, fracs, pipes)

    # --- override the three drifted sections from the real-lineage template ---
    cfg["costs"] = copy.deepcopy(template["costs"])
    cfg["site"] = copy.deepcopy(template["site"])
    cfg["assets"] = copy.deepcopy(template["assets"])
    # re-size TES to this cell's storage_h (template is s6h)
    energy = float(round(PEAK_MW * s, 0))
    cfg["assets"]["tes_main"]["energy_mwh"] = energy
    cfg["assets"]["tes_main"]["soc0_mwh"] = float(round(energy / 2, 0))
    # grid / fuels / run envelope also from template (co2/price lineage lives partly here)
    for k in ("grid", "fuels", "run"):
        if k in template:
            cfg[k] = copy.deepcopy(template[k])
    cfg["scenario"]["name"] = f"Synth n{n}_L{L}km_hi{hi}_s{s}h"
    return name, cfg


def _dump(cfg):
    return yaml.dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False)


def verify(template):
    """Regenerate an EXISTING cell and confirm parity (all but demand fracs)."""
    n, L, hi, s = 5, 15.0, 0.1, 6
    stored = yaml.safe_load((SYNTH / f"{TEMPLATE_STEM}.yaml").read_text(encoding="utf-8"))
    _, regen = _build(n, L, hi, s, template)

    def strip_random(d):
        d = copy.deepcopy(d)
        for p in d.get("network", {}).get("pipes", {}).values():
            p.pop("length_m", None); p.pop("diameter_mm", None)
            p.pop("u_value_supply_w_per_m_k", None); p.pop("u_value_return_w_per_m_k", None)
        for nd in d.get("network", {}).get("nodes", {}).values():
            for c in nd.get("consumers", []):
                c.pop("demand_fraction", None)
        return d

    import json
    a = json.dumps(strip_random(stored), sort_keys=True)
    b = json.dumps(strip_random(regen), sort_keys=True)
    ok = a == b
    print(f"[VERIFY] template cell {TEMPLATE_STEM}: structural parity (excl. demand fracs) = {ok}")
    if not ok:
        sa, sb = strip_random(stored), strip_random(regen)
        for k in sorted(set(sa) | set(sb)):
            if json.dumps(sa.get(k), sort_keys=True) != json.dumps(sb.get(k), sort_keys=True):
                print("   DIFFERS in section:", k)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    template = _load_template()
    if a.verify:
        verify(template)
        return

    grid = list(itertools.product(N_NODES, LENGTHS_KM, HI_LEVELS, STORAGE_H))
    fein = [(n, L, hi, s) for (n, L, hi, s) in grid if _feasible(n, L)]
    infeasible = [(n, L, hi, s) for (n, L, hi, s) in grid if not _feasible(n, L)]
    missing = [(n, L, hi, s) for (n, L, hi, s) in fein
               if not (SYNTH / f"{_name(n, L, hi, s)}.yaml").exists()]

    print(f"balanced grid = {len(grid)} | feasible (edge>={MIN_EDGE_M:.0f}m) = {len(fein)} "
          f"| infeasible = {len(infeasible)} | already present = {len(fein) - len(missing)} "
          f"| MISSING to write = {len(missing)}")
    if infeasible:
        print("  infeasible cells:", [_name(*c) for c in infeasible])
    if a.dry_run:
        for c in missing:
            print("   +", _name(*c))
        return

    if not verify(template):
        print("[ABORT] template parity failed; not writing anything.")
        return

    written = 0
    for (n, L, hi, s) in missing:
        name, cfg = _build(n, L, hi, s, template)
        dst = SYNTH / f"{name}.yaml"
        if dst.exists():
            continue
        dst.write_text(_dump(cfg), encoding="utf-8")
        written += 1
    print(f"[FILL] wrote {written} new base configs to {SYNTH}/")
    print("Next: python tools/gen_synth_copperplate.py   (emits _L1cp for the new bases)")


if __name__ == "__main__":
    main()
