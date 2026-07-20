"""
Paper 3 — CO2-Post-Processing Pipeline.

Liest alle 18 Run-Outputs, multipliziert mit EF-Zeitreihen, berechnet KPIs.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = _SCRIPT_DIR / "results"

# EF-Spaltennamen im ef_all_granularities_2025.parquet
EF_COLS = {
    "G1": "ef_g1",
    "G2": "ef_g2",
    "G3": "ef_g3",
    "G4": "ef_g4",
    "G5_M1": "ef_g5_m1",
    "G5_M2": "ef_g5_m2",
    "G6_M1": "ef_g6_m1",
}


# ---------------------------------------------------------------------------
# Einzel-Run CO2-Berechnung
# ---------------------------------------------------------------------------

def compute_co2_run(
    run_df: pd.DataFrame,
    ef_df: pd.DataFrame,
    run_id: str,
) -> dict:
    """
    Berechnet CO2-Emissionen fuer einen einzelnen Run x alle 7 EF-Varianten.

    Formel: CO2 [t/a] = Σ_t ( P_el[t] [MW] * EF[t] [g/kWh] * 1h ) / 1e6
    Erklärung: 1 MW * 1h = 1 MWh; 1 MWh * g/kWh = 1000 g = 0.001 kg → / 1e6 → t

    Ausserdem: ef_err_g{x}_pct = (CO2_Gx - CO2_G5_M1) / CO2_G5_M1 * 100
    """
    p_el = run_df["p_el_total_mw"]

    # EF-Zeitreihen auf Run-Index ausrichten
    ef_aligned = ef_df.reindex(p_el.index, method="nearest")

    result: dict = {"run_id": run_id}

    # CO2-Emissionen je Granularitaet
    for key, col in EF_COLS.items():
        if col not in ef_aligned.columns:
            logger.warning("EF-Spalte '%s' nicht in ef_df — setze auf NaN", col)
            result[f"co2_{key.lower()}"] = float("nan")
        else:
            co2_t_a = float((p_el * ef_aligned[col]).sum() / 1e6)
            result[f"co2_{key.lower()}"] = co2_t_a

    # Referenz: G5_M1 (stündlich, attributional)
    co2_ref = result.get("co2_g5_m1", float("nan"))

    # Relativer Fehler gegenueber G5_M1
    for key in EF_COLS:
        if key == "G5_M1":
            continue
        co2_gx = result.get(f"co2_{key.lower()}", float("nan"))
        if co2_ref > 0:
            err_pct = (co2_gx - co2_ref) / co2_ref * 100.0
        else:
            err_pct = float("nan")
        result[f"ef_err_{key.lower()}_pct"] = err_pct

    return result


# ---------------------------------------------------------------------------
# Alle 18 Runs
# ---------------------------------------------------------------------------

def compute_co2_all_runs(
    runs_dir: Path,
    ef_df: pd.DataFrame,
    ef_g6_15min: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Berechnet CO2-Emissionen fuer alle 18 Runs x 7 EF-Varianten.

    Gibt DataFrame mit Index=run_id zurueck.
    Speichert: results/co2/co2_summary.parquet + co2_summary.csv
    """
    co2_dir = RESULTS_DIR / "co2"
    co2_dir.mkdir(parents=True, exist_ok=True)

    # 15-min EF als eigene Spalte ergaenzen falls vorhanden
    if ef_g6_15min is not None:
        ef_work = ef_df.copy()
        # ef_g6_m1 aus 15-min auf Stunden-Index neu berechnen (falls separater Input)
        ef_g6_resampled = ef_g6_15min.resample("1h").mean()
        ef_work["ef_g6_m1"] = ef_g6_resampled.reindex(ef_df.index, method="nearest")
    else:
        ef_work = ef_df

    rows = []
    run_parquets = sorted(runs_dir.glob("R*.parquet"))

    if not run_parquets:
        raise FileNotFoundError(
            f"Keine Run-Parquet-Dateien in {runs_dir}. "
            "Bitte zuerst run_simulations.run_all() ausfuehren."
        )

    for parquet_path in run_parquets:
        run_id = parquet_path.stem  # z.B. "R01"
        meta_path = runs_dir / f"{run_id}_meta.json"

        logger.info("Verarbeite %s ...", run_id)
        run_df = pd.read_parquet(parquet_path)

        co2_row = compute_co2_run(run_df, ef_work, run_id)

        # Metadaten ergaenzen
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            co2_row.update({
                "network": meta.get("network", ""),
                "system": meta.get("system", ""),
                "strategy": meta.get("strategy", ""),
                "cost_eur": meta.get("cost_eur", float("nan")),
                "cop_mean": meta.get("cop_annual_mean", float("nan")),
                "q_demand_total_mwh": meta.get("q_demand_total_mwh", float("nan")),
                "solver_status": meta.get("solver_status", "unknown"),
            })
        else:
            logger.warning("Keine meta.json fuer %s", run_id)

        # Monatliche CO2-Zeitreihe (G5_M1)
        p_el = run_df["p_el_total_mw"]
        ef_g5 = ef_work["ef_g5_m1"].reindex(p_el.index, method="nearest")
        monthly = (p_el * ef_g5 / 1e6).resample("ME").sum()
        co2_row["co2_monthly_g5m1"] = monthly.to_dict()

        rows.append(co2_row)

    co2_df = pd.DataFrame(rows).set_index("run_id")

    # Speichern
    co2_df.drop(columns=["co2_monthly_g5m1"], errors="ignore").to_parquet(
        co2_dir / "co2_summary.parquet"
    )
    co2_df.drop(columns=["co2_monthly_g5m1"], errors="ignore").to_csv(
        co2_dir / "co2_summary.csv"
    )
    logger.info("CO2-Zusammenfassung gespeichert: %s", co2_dir / "co2_summary.csv")

    # Monatliche CO2 separat speichern
    _save_monthly_co2(rows, co2_dir)

    return co2_df


def _save_monthly_co2(rows: list[dict], co2_dir: Path) -> None:
    """Speichert monatliche CO2-Emissionen (G5_M1) als separates Parquet."""
    monthly_rows = []
    for row in rows:
        if "co2_monthly_g5m1" not in row:
            continue
        run_id = row.get("run_id", row.get("index", "?"))
        for ts_str, val in row["co2_monthly_g5m1"].items():
            monthly_rows.append({
                "run_id": run_id,
                "network": row.get("network", ""),
                "system": row.get("system", ""),
                "strategy": row.get("strategy", ""),
                "month": pd.Timestamp(ts_str),
                "co2_g5m1_t": val,
            })

    if monthly_rows:
        monthly_df = pd.DataFrame(monthly_rows)
        monthly_df.to_parquet(co2_dir / "co2_monthly.parquet", index=False)
        logger.info("Monatliche CO2-Zeitreihen gespeichert: co2_monthly.parquet")


# ---------------------------------------------------------------------------
# KPI-Berechnung
# ---------------------------------------------------------------------------

def compute_kpis(co2_df: pd.DataFrame) -> pd.DataFrame:
    """
    Berechnet alle Paper-3-KPIs aus der CO2-Bilanz-Tabelle.

    K1: co2_abs_g{x}     [t/a]  — absolute Emissionen je Granularitaet
    K2: co2_spez_g{x}    [kg/MWh_th] — normiert auf Waermeproduktion
    K3: ef_err_g{x}_pct  [%]   — (CO2_Gx - CO2_G5_M1) / CO2_G5_M1 * 100
    K4: rh_pen_pct       [%]   — (CO2_B3 - CO2_B2) / CO2_B2 * 100
    K5: stor_ben_pct     [%]   — (CO2_S1 - CO2_S2) / CO2_S1 * 100
    K6: m1_m2_delta_pct  [%]   — (CO2_M2 - CO2_M1) / CO2_M1 * 100
    K7: cost_eur_a       [EUR/a]
    """
    kpi = co2_df.copy()

    # K1: Absolute Emissionen (bereits als co2_g1, co2_g2, ... vorhanden)

    # K2: Spezifische Emissionen [kg/MWh_th]
    q_demand = kpi["q_demand_total_mwh"]
    for key in EF_COLS:
        col = f"co2_{key.lower()}"
        if col in kpi.columns:
            kpi[f"co2_spez_{key.lower()}"] = kpi[col] * 1000.0 / q_demand

    # K3: Bilanzierungsfehler (bereits als ef_err_* berechnet)

    # K4: RH-Penalitaet (CO2_B3 - CO2_B2) / CO2_B2 * 100
    # Pivot: eine Zeile je (network, system), Spalten = Strategien
    if "strategy" in kpi.columns:
        _add_rh_penalty(kpi)

    # K5: Speichervorteil (CO2_S1 - CO2_S2) / CO2_S1 * 100
    if "system" in kpi.columns:
        _add_storage_benefit(kpi)

    # K6: M1 vs M2 Delta
    if "co2_g5_m1" in kpi.columns and "co2_g5_m2" in kpi.columns:
        kpi["m1_m2_delta_pct"] = (
            (kpi["co2_g5_m2"] - kpi["co2_g5_m1"]) / kpi["co2_g5_m1"] * 100.0
        )

    # K7: Jahresbetriebskosten (bereits in cost_eur)
    kpi["cost_eur_a"] = kpi["cost_eur"]

    co2_dir = RESULTS_DIR / "co2"
    co2_dir.mkdir(parents=True, exist_ok=True)
    kpi.to_csv(co2_dir / "kpi_summary.csv")
    logger.info("KPI-Zusammenfassung gespeichert: kpi_summary.csv")

    return kpi


def _add_rh_penalty(kpi: pd.DataFrame) -> None:
    """Ergaenzt K4 rh_pen_pct in-place."""
    for run_b3_id, row_b3 in kpi[kpi["strategy"] == "B3"].iterrows():
        # Entsprechenden B2-Run finden (gleiches Netz und System)
        mask_b2 = (
            (kpi["network"] == row_b3["network"])
            & (kpi["system"] == row_b3["system"])
            & (kpi["strategy"] == "B2")
        )
        b2_rows = kpi[mask_b2]
        if b2_rows.empty:
            continue
        co2_b2 = b2_rows["co2_g5_m1"].iloc[0]
        co2_b3 = row_b3["co2_g5_m1"]
        if co2_b2 > 0:
            kpi.at[run_b3_id, "rh_pen_pct"] = (co2_b3 - co2_b2) / co2_b2 * 100.0


def _add_storage_benefit(kpi: pd.DataFrame) -> None:
    """Ergaenzt K5 stor_ben_pct in-place."""
    for run_s2_id, row_s2 in kpi[kpi["system"] == "S2"].iterrows():
        mask_s1 = (
            (kpi["network"] == row_s2["network"])
            & (kpi["system"] == "S1")
            & (kpi["strategy"] == row_s2["strategy"])
        )
        s1_rows = kpi[mask_s1]
        if s1_rows.empty:
            continue
        co2_s1 = s1_rows["co2_g5_m1"].iloc[0]
        co2_s2 = row_s2["co2_g5_m1"]
        if co2_s1 > 0:
            kpi.at[run_s2_id, "stor_ben_pct"] = (co2_s1 - co2_s2) / co2_s1 * 100.0
