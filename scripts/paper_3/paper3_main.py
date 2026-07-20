"""
Paper 3 — Einstiegspunkt.

Fuehrt die vollstaendige Pipeline in Sequenz aus:
  1. SMARD-Datenpruefung
  2. 18 Solver-Runs (run_simulations)
  3. CO2-Post-Processing (co2_postprocessing)
  4. 12 Abbildungen (figures)
  5. CSV-Export fuer Paper

Verwendung:
  python paper3_main.py --step all
  python paper3_main.py --step simulate
  python paper3_main.py --step co2
  python paper3_main.py --step figures
  python paper3_main.py --runs R01 R02 R03
  python paper3_main.py --force
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
# CALION-Framework auf Python-Pfad setzen
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR.parent.parent))  # Repo-Root

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("paper3")

DATA_DIR = _SCRIPT_DIR / "data"
RESULTS_DIR = _SCRIPT_DIR / "results"


# ---------------------------------------------------------------------------
# SMARD-Datenpruefung
# ---------------------------------------------------------------------------

def check_smard_data() -> bool:
    """
    Prueft ob die SMARD-Parquet-Dateien vorhanden sind.

    Returns False und druckt Hinweis falls Daten fehlen.
    """
    ef_path = DATA_DIR / "ef_all_granularities_2025.parquet"
    prices_path = DATA_DIR / "prices_1h_2025.parquet"

    missing = [p for p in [ef_path, prices_path] if not p.exists()]
    if missing:
        logger.error(
            "SMARD-Daten fehlen:\n%s\n\n"
            "Bitte zuerst ausfuehren:\n"
            "  python docs/paper_3/Prompt/smard_download.py\n"
            "Ausgabeverzeichnis: scripts/paper_3/data/",
            "\n".join(f"  {p}" for p in missing),
        )
        return False

    logger.info("SMARD-Daten gefunden: %s", DATA_DIR)
    ef_df = pd.read_parquet(ef_path)
    logger.info(
        "EF-Daten: %d Stunden (%s bis %s)",
        len(ef_df), ef_df.index[0], ef_df.index[-1],
    )
    return True


# ---------------------------------------------------------------------------
# Pipeline-Schritte
# ---------------------------------------------------------------------------

def step_simulate(run_ids: list[str] | None, force: bool) -> list[dict]:
    """Schritt 1: 18 Solver-Runs."""
    from run_simulations import run_all
    t0 = time.perf_counter()
    logger.info("=== SCHRITT 1: Solver-Runs ===")
    results = run_all(force=force, run_ids=run_ids or None)
    logger.info(
        "Solver-Runs abgeschlossen in %.1f min.",
        (time.perf_counter() - t0) / 60.0,
    )
    return results


def step_co2() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Schritt 2: CO2-Post-Processing."""
    from co2_postprocessing import compute_co2_all_runs, compute_kpis
    from run_simulations import load_smard_data

    t0 = time.perf_counter()
    logger.info("=== SCHRITT 2: CO2-Post-Processing ===")

    ef_df, ef_g6_15min, _ = load_smard_data()
    runs_dir = RESULTS_DIR / "runs"

    co2_df = compute_co2_all_runs(runs_dir, ef_df, ef_g6_15min)
    kpi_df = compute_kpis(co2_df)

    logger.info(
        "CO2-Post-Processing abgeschlossen in %.1f s. %d Runs verarbeitet.",
        time.perf_counter() - t0, len(co2_df),
    )
    return co2_df, kpi_df


def step_figures(co2_df: pd.DataFrame | None = None) -> None:
    """Schritt 3: 12 Abbildungen generieren."""
    from figures import generate_all
    from run_simulations import load_smard_data

    logger.info("=== SCHRITT 3: Abbildungen ===")
    t0 = time.perf_counter()

    ef_df: pd.DataFrame | None = None
    try:
        ef_df, _, _ = load_smard_data()
    except FileNotFoundError:
        logger.warning("SMARD-Daten nicht verfuegbar — EF-Abbildungen werden uebersprungen")

    # Run-DataFrames fuer F4 laden (Memmingen S2: R02, R05, R08)
    runs_dir = RESULTS_DIR / "runs"
    run_data: dict[str, pd.DataFrame] = {}
    for run_id in ["R02", "R05", "R08"]:
        p = runs_dir / f"{run_id}.parquet"
        if p.exists():
            run_data[run_id] = pd.read_parquet(p)

    # Monatliche CO2-Daten fuer F9
    monthly_path = RESULTS_DIR / "co2" / "co2_monthly.parquet"
    monthly_df: pd.DataFrame | None = None
    if monthly_path.exists():
        monthly_df = pd.read_parquet(monthly_path)

    # Falls co2_df nicht uebergeben: aus CSV laden
    if co2_df is None:
        co2_csv = RESULTS_DIR / "co2" / "co2_summary.csv"
        if co2_csv.exists():
            co2_df = pd.read_csv(co2_csv, index_col=0)
        else:
            logger.warning("co2_summary.csv nicht gefunden — Abbildungen ohne CO2-Daten")

    generate_all(
        ef_df=ef_df,
        co2_df=co2_df,
        run_data=run_data,
        monthly_df=monthly_df,
        results_dir=RESULTS_DIR,
    )
    logger.info(
        "Abbildungen generiert in %.1f s.", time.perf_counter() - t0
    )


def step_export_tables(co2_df: pd.DataFrame, kpi_df: pd.DataFrame) -> None:
    """Schritt 4: CSV-Tabellen fuer Paper exportieren."""
    co2_dir = RESULTS_DIR / "co2"
    co2_dir.mkdir(parents=True, exist_ok=True)

    # Haupttabelle
    co2_df.to_csv(co2_dir / "Table1_co2_summary.csv")

    # KPI-Tabelle
    kpi_df.to_csv(co2_dir / "Table2_kpi_summary.csv")

    # Granularitaetsvergleich (Kerntabelle Paper 3)
    gran_cols = [c for c in co2_df.columns if c.startswith("co2_g")]
    err_cols = [c for c in co2_df.columns if c.startswith("ef_err_")]
    meta_cols = ["network", "system", "strategy", "cost_eur", "cop_mean"]
    export_cols = meta_cols + gran_cols + err_cols
    available = [c for c in export_cols if c in co2_df.columns]
    co2_df[available].to_csv(co2_dir / "Table3_granularity_comparison.csv")

    logger.info("CSV-Tabellen exportiert nach %s", co2_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Paper 3 — CO2-Bilanzierung in elektrifizierten Waermenetzen"
    )
    parser.add_argument(
        "--step",
        choices=["all", "simulate", "co2", "figures"],
        default="all",
        help="Auszufuehrender Schritt (default: all)",
    )
    parser.add_argument(
        "--runs",
        nargs="+",
        metavar="RXX",
        help="Spezifische Run-IDs (z.B. R01 R02 R03)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Gecachte Ergebnisse ueberschreiben",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logger.info(
        "=== Paper 3 Pipeline | Schritt: %s | Runs: %s | Force: %s ===",
        args.step,
        args.runs or "alle",
        args.force,
    )

    # Immer SMARD-Daten pruefen (ausser reine Figurengenerierung ohne co2_df)
    if args.step in ("all", "simulate", "co2"):
        if not check_smard_data():
            sys.exit(1)

    co2_df: pd.DataFrame | None = None
    kpi_df: pd.DataFrame | None = None

    if args.step in ("all", "simulate"):
        step_simulate(run_ids=args.runs, force=args.force)

    if args.step in ("all", "co2"):
        co2_df, kpi_df = step_co2()

    if args.step in ("all", "figures"):
        step_figures(co2_df=co2_df)

    if args.step == "all" and co2_df is not None and kpi_df is not None:
        step_export_tables(co2_df, kpi_df)

    logger.info("=== Paper 3 Pipeline abgeschlossen ===")


if __name__ == "__main__":
    main()
