"""WP0 value-saturation probe (Rework v3, 2026-09-01).

Question this answers: does the marginal value of thermal storage SATURATE at a
finite number of storage-hours, or does it keep paying out past any buildable
size? That determines whether Paper 2's central figure (F2, an *inner* storage
optimum) can exist at all, or whether the honest result is "storage is only as
large as the building site" (see WP0_BEFUND.md, Zusatzbefund B).

Method (cost- and ΔT-independent, by construction):
  * HP capacity is PINNED at the scenario's solved MILP optimum (investment
    min=max), so the only thing that varies across points is stored energy.
  * TES runs in NON-INVESTABLE fixed-tank mode at a grid of ENERGY levels
    [MWh]. A non-investable tank contributes NO CAPEX to the objective
    (investable=False -> InvestmentResult=None in geometric_storage.py), so the
    resulting OPEX(E) curve is the pure storage *value* curve. Overlay any cost
    assumption offline: the optimum is where marginal value crosses marginal
    cost.
  * soc0_fraction=0 and terminal_soc_fraction=0 kill the initial-SOC free-energy
    artifact (a large tank with the default soc0=0.5 would inject 0.5*E_max of
    free heat and fake a value ∝ E).
  * p_max_bar and V_max_m3 are lifted FOR THE PROBE ONLY so the fixed tank can
    exceed the pressurized-vessel 5,000 m³ cap that the atmospheric-technology
    decision is replacing anyway — the probe must see past it.

Everything else (load, prices, COP, L3+ temperature/pressure, network) is
inherited unchanged from the seed scenario.

Usage:
    python scripts/paper_2/value_saturation_probe.py MM-S1-HK0
    python scripts/paper_2/value_saturation_probe.py SB-S1-HK0
    python scripts/paper_2/value_saturation_probe.py MM-S1-HK0 --energies 0,5,10,20,40,80,160,320 --dry-run
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(_ROOT))

from scripts.paper_2 import scenario_runner as sr  # noqa: E402
from scripts.paper_2.kpi_calculator import compute_opex_split, compute_scenario_kpis  # noqa: E402
from scripts.paper_2.main_result_loader import HP_ASSET, TES_ASSET, load_main_result  # noqa: E402

logger = logging.getLogger("value_probe")

PROBE_OUT = _ROOT / "output" / "paper2_value_probe"   # isolated per-point artefacts
RESULTS = _ROOT / "results"
CO2_PRICE = 100.0                                     # €/t (spec / configs)

# Per-network default ENERGY grids [MWh], spanning 0 -> well past the 5,000 m³
# pressurized cap (at ΔT≈15 K, 5,000 m³ ≈ 85 MWh). Chosen to bracket where the
# value plausibly saturates in storage-hours for each network's load scale.
DEFAULT_ENERGIES = {
    "memmingen": [0, 5, 10, 20, 40, 80, 160, 320],        # mean ~1.4 MW, peak ~5.3 MW
    "stadtbach": [0, 20, 50, 100, 200, 400, 800, 1600],   # much larger load
}

_PROBE_SOLVER_OPTIONS = {
    "TimeLimit": 1800,
    "MIPGap": 0.01,
    "Threads": 4,
    "Cuts": 2,
    "MIPFocus": 1,       # find incumbents fast (MIPFocus=2 chases the bound -> no incumbent)
    "Heuristics": 0.5,
}

# Investable electrode-boiler (EK) key per network — disabled in the probe (its
# build binary is pure cost here, and its optimal share is 0% in both seeds).
EK_ASSET = {"memmingen": "eboiler_main", "stadtbach": "ek_sb"}


def _probe_override(network: str, q_fix: float, e_mwh: float,
                    relax_gen_keys: list[str] | None = None) -> dict:
    """Pin HP at q_fix; set TES to a non-investable fixed tank at e_mwh (or off).

    relax_gen_keys: generator/p2h assets whose min_load is set to 0 so their
    unit-commitment on/off binary drops out -> the year-long dispatch becomes an
    LP. Needed for the large Stadtbach model, which otherwise finds no incumbent.
    """
    hp, tes = HP_ASSET[network], TES_ASSET[network]
    ov: dict = {
        "assets": {
            hp: {"investment": {"enabled": True,
                                "capacity_min_mw": float(q_fix),
                                "capacity_max_mw": float(q_fix)}},
            # Disable the investable EK (share 0% in both seeds; removes a binary).
            EK_ASSET[network]: {"investment": {"enabled": False, "capacity_max_mw": 0.0},
                                "min_load": 0.0},
        }
    }
    for gk in (relax_gen_keys or []):
        ov["assets"].setdefault(gk, {})["min_load"] = 0.0
    if e_mwh <= 0:
        # No storage reference point: investable tank pinned to zero volume.
        ov["assets"][tes] = {"V_min_m3": 0.0, "V_max_m3": 0.0}
    else:
        ov["assets"][tes] = {
            "investable": False,
            "energy_mwh_fixed": float(e_mwh),
            "power_mw_fixed": round(0.25 * float(e_mwh), 4),  # standard 4 h C-rate
            "p_max_bar": 100.0,        # probe-only: lift pressurized-vessel height limit
            "V_max_m3": 300000.0,      # probe-only: lift volume cap
            "soc0_fraction": 0.0,      # no free initial energy
            "terminal_soc_fraction": 0.0,
        }
    return ov


def _detect_commitment_gens(config_path: str) -> list[str]:
    """Return generator/p2h asset keys carrying a min_load>0 (i.e. a UC binary)."""
    import yaml
    cfg = yaml.safe_load(open(_ROOT / config_path, encoding="utf-8"))
    keys = []
    for k, v in (cfg.get("assets") or {}).items():
        if isinstance(v, dict) and v.get("type") in ("thermal_generator", "p2h", "heat_pump") \
                and float(v.get("min_load", 0) or 0) > 0:
            keys.append(k)
    return keys


def run_probe(scenario_id: str, energies: list[float] | None = None,
              dry_run: bool = False, relax_commitment: bool = False,
              solver_opts: dict | None = None, out_tag: str = "") -> Path | None:
    res = load_main_result(scenario_id)
    network = res["network"]
    q_opt = res["Q_WP_opt_MW"]
    if not q_opt:
        raise ValueError(
            f"{scenario_id}: solved MILP optimum has Q_WP={q_opt} MW — the probe "
            "needs a scenario where the heat pump was built (pick an S1 scenario).")
    energies = energies if energies is not None else DEFAULT_ENERGIES[network]
    energies = sorted({round(float(e), 3) for e in energies})

    relax_keys: list[str] = []
    if relax_commitment:
        relax_keys = _detect_commitment_gens(res["scenario"]["config"])
        logger.info("  Commitment relaxed (min_load->0) on %d gens: %s",
                    len(relax_keys), ", ".join(relax_keys))

    logger.info("Value probe %s (%s): HP pinned at Q*=%.2f MW; TES energies [MWh]: %s",
                scenario_id, network, q_opt, ", ".join(f"{e:g}" for e in energies))
    logger.info("  %d dispatch solves (HP fixed, TES non-investable fixed tank)", len(energies))
    if dry_run:
        logger.info("[DRY-RUN] grid built; no solves performed")
        return None

    base_scen = res["scenario"]
    scen_cfg = sr.load_scenarios_config()
    orig_out = sr.OUT_BASE
    sr.OUT_BASE = PROBE_OUT
    PROBE_OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    try:
        for i, e in enumerate(energies):
            scen = copy.deepcopy(base_scen)
            scen["id"] = f"VPROBE_{scenario_id}_e{e:g}"
            scen["baseline"] = False
            scen["overrides"] = sr._deep_merge(scen.get("overrides") or {},
                                               _probe_override(network, q_opt, e, relax_keys))
            opts = {**_PROBE_SOLVER_OPTIONS, **(solver_opts or {})}
            r = sr.run_single_scenario(scen, scen_cfg, dry_run=False, force_rerun=True,
                                       extra_solver_options=opts)
            row = {"E_mwh": e, "Q_WP_MW": q_opt, "status": r.get("status")}
            if r.get("status") == "ok" and r.get("outdir"):
                k = compute_scenario_kpis(Path(r["outdir"]))
                opex_split = compute_opex_split(Path(r["outdir"]))
                opex = float(k.get("OPEX_annual_eur_per_a") or 0)
                co2 = float(k.get("co2_t_per_a") or 0) * CO2_PRICE
                row.update(
                    TAC_eur_per_a=k.get("TAC_eur_per_a"),
                    LCOH_eur_per_MWh=k.get("LCOH_eur_per_MWh"),
                    CAPEX_annual_eur_per_a=k.get("CAPEX_annual_eur_per_a"),
                    OPEX_annual_eur_per_a=opex,
                    OPEX_el_eur_per_a=opex_split["OPEX_el_eur_per_a"],
                    OPEX_gas_eur_per_a=opex_split["OPEX_gas_eur_per_a"],
                    OPEX_CO2_eur_per_a=round(co2, 1),
                    OPEX_energy_eur_per_a=round(max(opex - co2, 0.0), 1),
                    co2_t_per_a=k.get("co2_t_per_a"),
                    mip_gap_pct=k.get("mip_gap_pct"),
                    feasible=True,
                )
            else:
                row["feasible"] = False
            rows.append(row)
            logger.info("  [%d/%d] E=%g MWh -> %s  OPEX=%s  TAC=%s",
                        i + 1, len(energies), e, row["status"],
                        f"{row.get('OPEX_annual_eur_per_a'):,.0f}" if row.get("feasible") else "—",
                        f"{row.get('TAC_eur_per_a'):,.0f}" if row.get("feasible") else "—")
    finally:
        sr.OUT_BASE = orig_out

    # Marginal value m(E) = -d(OPEX)/dE between consecutive points [€/a per MWh].
    df = pd.DataFrame(rows)
    if "OPEX_annual_eur_per_a" in df.columns:
        df = df.sort_values("E_mwh").reset_index(drop=True)
        opex = df["OPEX_annual_eur_per_a"]
        de = df["E_mwh"].diff()
        df["marginal_value_eur_per_a_per_mwh"] = (-opex.diff() / de).round(1)

    RESULTS.mkdir(parents=True, exist_ok=True)
    _sfx = f"__{out_tag}" if out_tag else ""
    out = RESULTS / f"value_probe_{network}_{scenario_id}{_sfx}.csv"
    df.to_csv(out, index=False)
    (RESULTS / f"value_probe_{network}_{scenario_id}{_sfx}_meta.json").write_text(json.dumps({
        "scenario_id": scenario_id, "network": network, "Q_WP_pinned_MW": q_opt,
        "energies_mwh": energies, "co2_price_eur_per_t": CO2_PRICE,
        "note": "OPEX(E) is the pure storage value curve (non-investable TES, no CAPEX). "
                "Optimum = where marginal_value crosses marginal annualized cost.",
    }, indent=2), encoding="utf-8")
    logger.info("Value probe written -> %s", out)
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser(description="WP0 value-saturation probe (Paper 2 v3)")
    ap.add_argument("scenario_id", help="seed scenario with a built HP, e.g. MM-S1-HK0")
    ap.add_argument("--energies", type=str, default=None,
                    help="comma-separated ENERGY grid [MWh]; default is per-network")
    ap.add_argument("--dry-run", action="store_true", help="build+print grid only")
    ap.add_argument("--relax-commitment", action="store_true",
                    help="set generator min_load=0 (drops UC binaries -> LP); needed for Stadtbach")
    ap.add_argument("--out-tag", type=str, default="",
                    help="suffix for the output CSV, so parallel single-point runs don't clobber")
    ap.add_argument("--time-limit", type=int, default=None, help="Gurobi TimeLimit [s] override")
    ap.add_argument("--threads", type=int, default=None, help="Gurobi Threads override")
    ap.add_argument("--mip-gap", type=float, default=None, help="Gurobi MIPGap override")
    args = ap.parse_args()
    energies = ([float(x) for x in args.energies.split(",")] if args.energies else None)
    solver_opts = {}
    if args.time_limit is not None: solver_opts["TimeLimit"] = args.time_limit
    if args.threads is not None: solver_opts["Threads"] = args.threads
    if args.mip_gap is not None: solver_opts["MIPGap"] = args.mip_gap
    run_probe(args.scenario_id, energies=energies, dry_run=args.dry_run,
              relax_commitment=args.relax_commitment, solver_opts=solver_opts or None,
              out_tag=args.out_tag)


if __name__ == "__main__":
    main()
