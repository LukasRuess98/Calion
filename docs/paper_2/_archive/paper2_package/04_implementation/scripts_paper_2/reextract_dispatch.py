"""Re-extract dispatch_hourly.csv for specified scenarios using config dispatch_series_map.

Reads dispatch_per_asset.csv (raw asset series) + existing dispatch_hourly.csv
(temperatures, demand, losses, prices) and rebuilds the generation columns
(Q_chp_MW, Q_biomass_MW, Q_gasboiler_MW, Q_hp_total_MW) using the explicit
dispatch_series_map from the network config YAML.

Does NOT re-solve the MILP. Use after updating configs/stadtbach/Stadtbach_topo.yaml
with dispatch_series_map to correct misrouted BMHKW/AVA_FEED columns.

Usage:
    python scripts/paper_2/reextract_dispatch.py [--scenarios SB-S1-HK0 SB-S2-HK0 ...]
    python scripts/paper_2/reextract_dispatch.py --all-sb
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_BASE = REPO_ROOT / "output" / "paper2_runs"

SB_SCENARIOS = [
    "BC-SB",
    "SB-S1-HK0", "SB-S1-HK1", "SB-S1-HK2",
    "SB-S2-HK0", "SB-S2-HK1", "SB-S2-HK2",
    "SB-S3-HK0", "SB-S3-HK1", "SB-S3-HK2",
]

# Primary series keys already captured in the primary rows of write_dispatch_hourly.
# These appear in dispatch_per_asset.csv as {KEY[:-len("_Q_th_MW")]}_MW.
# P2H_Q_th_MW = p2h_existing + ek_sb summed by result_collector; already in Q_ek_MW.
_PRIMARY_KEYS = {
    "CHP_MAIN_Q_th_MW", "GASBOILER_MAIN_Q_th_MW", "BIOMASS_MAIN_Q_th_MW",
    "hp_main_Q_th_MW", "EBOILER_MAIN_Q_th_MW", "P2H_Q_th_MW",
}

# Columns rebuilt from dispatch_series_map; all others are kept from existing CSV.
_GEN_COLS = ["Q_chp_MW", "Q_biomass_MW", "Q_gasboiler_MW", "Q_hp_total_MW"]


def _load_dispatch_map(config_path: Path) -> dict[str, str]:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    dm = cfg.get("dispatch_series_map", {})
    if not dm:
        logger.warning("No dispatch_series_map found in %s", config_path)
    return dm


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def reextract_scenario(scen_dir: Path, dispatch_map: dict[str, str]) -> bool:
    per_asset_path = scen_dir / "dispatch_per_asset.csv"
    dispatch_path = scen_dir / "dispatch_hourly.csv"

    if not per_asset_path.exists():
        logger.warning("[%s] dispatch_per_asset.csv missing — skipping", scen_dir.name)
        return False
    if not dispatch_path.exists():
        logger.warning("[%s] dispatch_hourly.csv missing — skipping", scen_dir.name)
        return False

    per_asset_rows = _read_csv(per_asset_path)
    dispatch_rows = _read_csv(dispatch_path)
    T = len(dispatch_rows)

    if len(per_asset_rows) != T:
        logger.warning(
            "[%s] Row count mismatch: per_asset=%d dispatch=%d — skipping",
            scen_dir.name, len(per_asset_rows), T,
        )
        return False

    # Initialise gen columns to 0.0
    gen: dict[str, list[float]] = {col: [0.0] * T for col in _GEN_COLS}

    # Per-asset columns are "{series_key[:-len('_Q_th_MW')]}_MW"
    # Reconstruct series key and apply dispatch_map
    pa_cols = [c for c in per_asset_rows[0] if c != "timestamp"]
    for col in pa_cols:
        series_key = col[:-len("_MW")] + "_Q_th_MW"
        if series_key in _PRIMARY_KEYS:
            continue  # already captured in primary Q_ek or other primary
        dest = dispatch_map.get(series_key)
        if dest and dest in gen:
            for i, row in enumerate(per_asset_rows):
                gen[dest][i] += float(row.get(col) or 0.0)
        else:
            # Heuristic for unmapped keys (backward compat)
            kl = series_key.lower()
            if kl.split("_")[0].startswith("hp"):
                dest = "Q_hp_total_MW"
            elif "ek_" in kl or kl.startswith("ek") or "eboiler" in kl:
                dest = "Q_ek_MW"  # not in _GEN_COLS — skip (handled by primary)
                continue
            else:
                dest = "Q_chp_MW"
            if dest in gen:
                for i, row in enumerate(per_asset_rows):
                    gen[dest][i] += float(row.get(col) or 0.0)

    # Merge rebuilt gen columns back into dispatch_rows
    fieldnames = list(dispatch_rows[0].keys())
    for col in _GEN_COLS:
        if col not in fieldnames:
            fieldnames.append(col)

    for i, row in enumerate(dispatch_rows):
        for col in _GEN_COLS:
            row[col] = f"{gen[col][i]:.6f}"

    _write_csv(dispatch_path, dispatch_rows, fieldnames)

    # Log summary
    totals = {col: sum(gen[col]) for col in _GEN_COLS}
    q_ek = sum(float(r.get("Q_ek_MW") or 0) for r in dispatch_rows)
    logger.info(
        "[%s] -> chp=%.0f bio=%.0f gb=%.0f hp=%.0f ek=%.0f MWh",
        scen_dir.name,
        totals["Q_chp_MW"], totals["Q_biomass_MW"],
        totals["Q_gasboiler_MW"], totals["Q_hp_total_MW"],
        q_ek,
    )
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenarios", nargs="+", metavar="ID", help="Scenario IDs to process")
    ap.add_argument("--all-sb", action="store_true", help="Process all SB scenarios")
    ap.add_argument(
        "--config",
        default=str(REPO_ROOT / "configs" / "stadtbach" / "Stadtbach_topo.yaml"),
        help="Network config YAML with dispatch_series_map",
    )
    args = ap.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error("Config not found: %s", config_path)
        sys.exit(1)

    dispatch_map = _load_dispatch_map(config_path)
    logger.info("Loaded dispatch_series_map (%d entries) from %s", len(dispatch_map), config_path)
    for k, v in dispatch_map.items():
        logger.info("  %s -> %s", k, v)

    if args.all_sb:
        scenario_ids = SB_SCENARIOS
    elif args.scenarios:
        scenario_ids = args.scenarios
    else:
        logger.error("Specify --scenarios or --all-sb")
        sys.exit(1)

    ok = failed = 0
    for sid in scenario_ids:
        scen_dir = OUT_BASE / sid
        if not scen_dir.exists():
            logger.warning("[%s] output dir missing — skipping", sid)
            failed += 1
            continue
        if reextract_scenario(scen_dir, dispatch_map):
            ok += 1
        else:
            failed += 1

    logger.info("Done: %d OK, %d failed/skipped", ok, failed)


if __name__ == "__main__":
    main()
