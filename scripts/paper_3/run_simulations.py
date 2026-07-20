"""
Paper 3 — Simulationsorchestrierung.

18 Solver-Runs: 2 Netzwerke x 3 Systemkonfigurationen x 3 Betriebsstrategien.
Ergebnisse werden als Parquet + JSON-Metadaten gecacht.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from calion_l1_paper3 import (
    NetworkParams,
    OperationParams,
    SystemParams,
    solve_dispatch,
    validate_run_output,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).parent
DATA_DIR = _SCRIPT_DIR / "data"
RESULTS_DIR = _SCRIPT_DIR / "results"

# ---------------------------------------------------------------------------
# Run-Matrix
# ---------------------------------------------------------------------------

RUN_MATRIX: list[tuple[str, str, str, str]] = [
    ("R01", "memmingen", "S1", "B1"),
    ("R02", "memmingen", "S2", "B1"),
    ("R03", "memmingen", "S3", "B1"),
    ("R04", "memmingen", "S1", "B2"),
    ("R05", "memmingen", "S2", "B2"),
    ("R06", "memmingen", "S3", "B2"),
    ("R07", "memmingen", "S1", "B3"),
    ("R08", "memmingen", "S2", "B3"),
    ("R09", "memmingen", "S3", "B3"),
    ("R10", "stadtbach", "S1", "B1"),
    ("R11", "stadtbach", "S2", "B1"),
    ("R12", "stadtbach", "S3", "B1"),
    ("R13", "stadtbach", "S1", "B2"),
    ("R14", "stadtbach", "S2", "B2"),
    ("R15", "stadtbach", "S3", "B2"),
    ("R16", "stadtbach", "S1", "B3"),
    ("R17", "stadtbach", "S2", "B3"),
    ("R18", "stadtbach", "S3", "B3"),
]

# ---------------------------------------------------------------------------
# Eingangsdaten-Loader (ANPASSEN: Pfade und Formate ergaenzen)
# ---------------------------------------------------------------------------

def _load_q_demand_memmingen(horizon: pd.DatetimeIndex) -> pd.Series:
    """
    Laedt den stündlichen Waermebedarf fuer Memmingen [MWh/h].

    # ANPASSEN: Pfad und Format der Messdaten von e-con AG / ECONTEC
    # Erwartet: CSV mit Spalte 'q_demand_mwh' und DatetimeIndex (Europe/Berlin)
    # Beispiel:
    #   csv_path = DATA_DIR / "memmingen_waermebedarf_2025.csv"
    #   df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    #   df.index = df.index.tz_localize("Europe/Berlin", ambiguous="infer")
    #   return df["q_demand_mwh"].reindex(horizon, method="nearest")
    """
    raise NotImplementedError(
        "ANPASSEN: _load_q_demand_memmingen() implementieren.\n"
        f"Erwarteter Pfad: {DATA_DIR / 'memmingen_waermebedarf_2025.csv'}"
    )


def _load_q_demand_stadtbach(horizon: pd.DatetimeIndex) -> pd.Series:
    """
    Laedt den stündlichen Waermebedarf fuer Stadtbach [MWh/h].

    # ANPASSEN: Format aus Paper-1-Kalibrierung (SLP-skaliert auf Jahressumme)
    # Beispiel:
    #   csv_path = DATA_DIR / "stadtbach_waermebedarf_2025.csv"
    #   df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    #   df.index = df.index.tz_localize("Europe/Berlin", ambiguous="infer")
    #   return df["q_demand_mwh"].reindex(horizon, method="nearest")
    """
    raise NotImplementedError(
        "ANPASSEN: _load_q_demand_stadtbach() implementieren.\n"
        f"Erwarteter Pfad: {DATA_DIR / 'stadtbach_waermebedarf_2025.csv'}"
    )


def _load_t_outside_memmingen(horizon: pd.DatetimeIndex) -> pd.Series:
    """
    Laedt die stündliche Aussentemperatur fuer Memmingen [°C].

    # ANPASSEN: DWD CDC Download oder eigene Messdaten
    # DWD Station: Memmingen (ID 3257)
    # Spalte: TT_TU_MN009 (Lufttemperatur 2m) -> umbenennen in 't_outside_c'
    # Beispiel:
    #   csv_path = DATA_DIR / "dwd_memmingen_2025.csv"
    #   df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    #   df.index = df.index.tz_localize("Europe/Berlin", ambiguous="infer")
    #   return df["t_outside_c"].reindex(horizon, method="nearest")
    """
    raise NotImplementedError(
        "ANPASSEN: _load_t_outside_memmingen() implementieren.\n"
        f"Erwarteter Pfad: {DATA_DIR / 'dwd_memmingen_2025.csv'}"
    )


def _load_t_outside_stadtbach(horizon: pd.DatetimeIndex) -> pd.Series:
    """
    Laedt die stündliche Aussentemperatur fuer Stuttgart/Stadtbach [°C].

    # ANPASSEN: DWD CDC Download oder eigene Messdaten
    # DWD Station: Stuttgart-Echterdingen (ID 4931) oder Stuttgart (ID 4928)
    # Beispiel:
    #   csv_path = DATA_DIR / "dwd_stuttgart_2025.csv"
    #   df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    #   df.index = df.index.tz_localize("Europe/Berlin", ambiguous="infer")
    #   return df["t_outside_c"].reindex(horizon, method="nearest")
    """
    raise NotImplementedError(
        "ANPASSEN: _load_t_outside_stadtbach() implementieren.\n"
        f"Erwarteter Pfad: {DATA_DIR / 'dwd_stuttgart_2025.csv'}"
    )


# ---------------------------------------------------------------------------
# Systemkonfigurationen
# ---------------------------------------------------------------------------

def _build_systems() -> dict[str, SystemParams]:
    """
    Systemkonfigurationen S1 / S2 / S3.

    # ANPASSEN: Echte Anlagenparameter aus Paper-2-Auslegung und Hersteller-Datenblaettern.
    # Memmingen: hp_cap_mw aus optimierter P2-Auslegung, tes_cap_mwh aus P2-Auslegungswert.
    # Stadtbach: Entsprechend Paper-1-Netzparametrierung.
    """
    return {
        # S1: Nur Waermepumpe, kein Speicher, kein Elektrodenkessel
        "S1": SystemParams(
            config="S1",
            hp_cap_mw=12.0,       # ANPASSEN: Herstellerdatenblatt / P2-Auslegung [MW_th]
            hp_cop_rated=3.5,     # ANPASSEN: COP bei Normbedingungen (EN 14511)
            hp_t_ref_c=-7.0,
            hp_cop_min=1.5,
            eb_cap_mw=0.0,
            tes_cap_mwh=0.0,
        ),
        # S2: Waermepumpe + thermischer Speicher
        "S2": SystemParams(
            config="S2",
            hp_cap_mw=12.0,       # ANPASSEN
            hp_cop_rated=3.5,     # ANPASSEN
            hp_t_ref_c=-7.0,
            hp_cop_min=1.5,
            eb_cap_mw=0.0,
            tes_cap_mwh=50.0,     # ANPASSEN: P2-Auslegungswert [MWh_th]
        ),
        # S3: Waermepumpe + Elektrodenkessel (kein Speicher)
        "S3": SystemParams(
            config="S3",
            hp_cap_mw=12.0,       # ANPASSEN
            hp_cop_rated=3.5,     # ANPASSEN
            hp_t_ref_c=-7.0,
            hp_cop_min=1.5,
            eb_cap_mw=5.0,        # ANPASSEN: EK-Leistung [MW_el]
            eb_eta=0.99,
            tes_cap_mwh=0.0,
        ),
    }


# ---------------------------------------------------------------------------
# Betriebsstrategien
# ---------------------------------------------------------------------------

def _build_strategies(da_prices: pd.Series) -> dict[str, OperationParams]:
    """Betriebsstrategien B1 / B2 / B3."""
    return {
        # B1: Fixpreis-Betrieb (kein Preissignal)
        "B1": OperationParams(
            strategy="B1",
            prices_eur_mwh=da_prices,    # wird intern durch price_fixed ersetzt
            price_fixed=120.0,           # ANPASSEN: Representativer Fixpreis 2025 [EUR/MWh]
            mip_gap=0.001,
            time_limit_s=3600,
        ),
        # B2: Day-Ahead-Preise, Perfect Foresight
        "B2": OperationParams(
            strategy="B2",
            prices_eur_mwh=da_prices,
            mip_gap=0.001,
            time_limit_s=3600,
        ),
        # B3: Day-Ahead-Preise, Rolling Horizon 24h
        "B3": OperationParams(
            strategy="B3",
            prices_eur_mwh=da_prices,
            rh_horizon_h=24,
            rh_step_h=1,
            mip_gap=0.005,              # lockerer fuer 8760 Solver-Calls
            time_limit_s=60,
        ),
    }


# ---------------------------------------------------------------------------
# Eingangsdaten laden
# ---------------------------------------------------------------------------

def load_smard_data() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Laedt SMARD-Daten aus data/.

    Returns:
        ef_df: DataFrame mit ef_g1..ef_g6_m1, stündlich, Europe/Berlin
        ef_g6_15min: 15-min EF-Zeitreihe (ef_g6_m1 aus ef_all_granularities)
        da_prices: stündliche DA-Preise [EUR/MWh]
    """
    ef_path = DATA_DIR / "ef_all_granularities_2025.parquet"
    prices_path = DATA_DIR / "prices_1h_2025.parquet"

    if not ef_path.exists():
        raise FileNotFoundError(
            f"SMARD-Daten fehlen: {ef_path}\n"
            "Bitte zuerst ausfuehren:\n"
            "  python docs/paper_3/Prompt/smard_download.py"
        )
    if not prices_path.exists():
        raise FileNotFoundError(f"Preise fehlen: {prices_path}")

    ef_df = pd.read_parquet(ef_path)
    prices = pd.read_parquet(prices_path)["da_price"]

    # 15-min EF ist in ef_all_granularities als ef_g6_m1 (bereits auf stündlich gemittelt)
    # Fuer echte 15-min Granularitaet: ef_g6_15min_2025.parquet lesen falls vorhanden
    g6_15min_path = DATA_DIR / "ef_g6_15min_2025.parquet"
    if g6_15min_path.exists():
        ef_g6_15min = pd.read_parquet(g6_15min_path)["ef_g6_m1"]
    else:
        logger.warning("ef_g6_15min_2025.parquet nicht gefunden — verwende ef_g6_m1 aus ef_all_granularities")
        ef_g6_15min = ef_df["ef_g6_m1"]

    return ef_df, ef_g6_15min, prices


# ---------------------------------------------------------------------------
# Einzelner Run
# ---------------------------------------------------------------------------

def run_single(
    run_id: str,
    net: NetworkParams,
    sys_params: SystemParams,
    ops: OperationParams,
    horizon: pd.DatetimeIndex,
    ef_df: pd.DataFrame,
    force: bool = False,
) -> dict:
    """
    Fuehrt einen einzelnen Dispatch-Run durch und speichert Ergebnisse.

    Ueberspringt wenn {run_id}_meta.json bereits existiert (ausser force=True).
    """
    runs_dir = RESULTS_DIR / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    meta_path = runs_dir / f"{run_id}_meta.json"
    parquet_path = runs_dir / f"{run_id}.parquet"

    if meta_path.exists() and not force:
        logger.info("Ueberspringe %s (meta.json vorhanden, --force zum Ueberschreiben)", run_id)
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)

    logger.info(
        "Starte Run %s: %s / %s / %s",
        run_id, net.name, sys_params.config, ops.strategy,
    )
    t0 = time.perf_counter()

    result = solve_dispatch(net, sys_params, ops, horizon)
    result["strategy"] = ops.strategy  # fuer validate_run_output CHECK 4

    validate_run_output(result, net, sys_params)

    # DA-Preise und EF fuer Parquet-Ausgabe ausrichten
    da_price_aligned = ops.prices_eur_mwh.reindex(horizon, method="nearest")
    ef_g5_m1_aligned = ef_df["ef_g5_m1"].reindex(horizon, method="nearest")

    # Ergebnis-DataFrame zusammenbauen
    out_df = pd.DataFrame(
        {
            "p_el_total_mw": result["p_el_total_mw"],
            "p_hp_el_mw": result["p_hp_el_mw"],
            "p_eb_el_mw": result["p_eb_el_mw"],
            "q_hp_mwh": result["q_hp_mwh"],
            "q_eb_mwh": result["q_eb_mwh"],
            "soc_tes_mwh": result["soc_tes_mwh"],
            "q_demand_mwh": result["q_demand_mwh"],
            "da_price": da_price_aligned,
            "ef_g5_m1": ef_g5_m1_aligned,
        },
        index=horizon,
    )
    out_df.index.name = "timestamp"
    out_df.to_parquet(parquet_path)

    # COP-Mittelwert berechnen
    cop_annual_mean = float(
        (result["q_hp_mwh"].sum() / result["p_hp_el_mw"].sum())
        if result["p_hp_el_mw"].sum() > 0 else 0.0
    )

    meta = {
        "run_id": run_id,
        "network": net.name,
        "system": sys_params.config,
        "strategy": ops.strategy,
        "cost_eur": float(result["cost_eur"]),
        "solve_time_s": float(result["solve_time_s"]),
        "solver_status": result["solver_status"],
        "q_demand_total_mwh": float(result["q_demand_mwh"].sum()),
        "q_supply_total_mwh": float(
            (result["q_hp_mwh"] + result["q_eb_mwh"]).sum()
        ),
        "p_el_total_mwh_a": float(result["p_el_total_mw"].sum()),
        "cop_annual_mean": cop_annual_mean,
        "wall_time_s": time.perf_counter() - t0,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    logger.info(
        "Run %s abgeschlossen: Kosten=%.0f EUR, COP_a=%.2f, Status=%s",
        run_id, meta["cost_eur"], cop_annual_mean, meta["solver_status"],
    )
    return meta


# ---------------------------------------------------------------------------
# Alle 18 Runs
# ---------------------------------------------------------------------------

def run_all(
    force: bool = False,
    run_ids: Optional[list[str]] = None,
) -> list[dict]:
    """
    Orchestriert alle 18 Solver-Runs.

    force: Ueberschreibt gecachte Ergebnisse.
    run_ids: Falls angegeben, werden nur diese Run-IDs ausgefuehrt.
    """
    ef_df, ef_g6_15min, da_prices = load_smard_data()

    horizon = ef_df.index  # stündlich, tz-aware Europe/Berlin (8760h)
    logger.info("Horizont: %s bis %s (%d Stunden)", horizon[0], horizon[-1], len(horizon))

    systems = _build_systems()
    strategies = _build_strategies(da_prices)

    # Netzwerke bauen (Eingangsdaten laden)
    try:
        networks = {
            "memmingen": NetworkParams(
                name="memmingen",
                q_demand_mwh=_load_q_demand_memmingen(horizon),
                t_outside_c=_load_t_outside_memmingen(horizon),
            ),
            "stadtbach": NetworkParams(
                name="stadtbach",
                q_demand_mwh=_load_q_demand_stadtbach(horizon),
                t_outside_c=_load_t_outside_stadtbach(horizon),
            ),
        }
    except NotImplementedError as exc:
        logger.error(
            "Eingangsdaten nicht implementiert:\n%s\n"
            "Bitte die ANPASSEN-Abschnitte in run_simulations.py bearbeiten.",
            exc,
        )
        raise

    active_matrix = [
        row for row in RUN_MATRIX
        if run_ids is None or row[0] in run_ids
    ]
    logger.info("Starte %d Runs ...", len(active_matrix))

    results = []
    for run_id, net_name, sys_name, strat_name in active_matrix:
        try:
            meta = run_single(
                run_id=run_id,
                net=networks[net_name],
                sys_params=systems[sys_name],
                ops=strategies[strat_name],
                horizon=horizon,
                ef_df=ef_df,
                force=force,
            )
            results.append(meta)
        except Exception:
            logger.exception("FEHLER in Run %s — ueberspringe", run_id)
            results.append({
                "run_id": run_id,
                "network": net_name,
                "system": sys_name,
                "strategy": strat_name,
                "solver_status": "error",
            })

    n_ok = sum(1 for r in results if r.get("solver_status") in ("optimal", "feasible"))
    logger.info(
        "Alle Runs abgeschlossen: %d/%d erfolgreich.", n_ok, len(active_matrix)
    )
    return results
