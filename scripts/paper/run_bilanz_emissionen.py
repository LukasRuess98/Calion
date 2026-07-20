"""
Bilanzraum-Emissionen Paper — Szenarien ausführen und Ergebnisse generieren.

Szenarien:
  S1  HP Lastfolgebetrieb (kein Speicher, kein Optimierungsanreiz)
  S2  HP optimiert auf Strombezugskosten (mit Speicher 50 MWh/10 MW)
  S3  HP optimiert auf Kosten + CO2-Emissionen (mit Speicher 50 MWh/10 MW)

Bilanzräume für CO2-Berechnung (Referenz = 15-Minuten):
  1. Jahresdurchschnitt      (1 Faktor)
  2. Monatsdurchschnitt      (12 Faktoren)
  3. Wochendurchschnitt      (52 Faktoren)
  4. Stündliche Auflösung    (8760 Faktoren)
  5. 15-Minuten-Auflösung    (35040 Faktoren) — feinste Referenz

Speicher-Dispatch (S2/S3): SOC, Laden, Entladen werden ebenfalls exportiert.

Ausgabe: outputs/bilanz_emissionen/ergebnisse/
  bilanzraum_vergleich.xlsx    Hauptergebnistabelle + Pivots
  dispatch_zeitreihen.csv      Stündlicher HP-Strom + Speicher-SOC aller Szenarien
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from calion.run.workflow import run_workflow
from calion.logging_config import get_logger

logger = get_logger(__name__)

DATA_1H  = ROOT / "data" / "memmingen_bilanz_emissionen_2025_1h.csv"
DATA_15M = ROOT / "data" / "memmingen_bilanz_emissionen_2025_15min.csv"
OUTDIR   = ROOT / "outputs" / "bilanz_emissionen" / "ergebnisse"

CONFIGS = {
    "S2_Kosten":            ROOT / "configs/Paper_bilanz_emissionen/S2_kosten.yaml",
    "S3_Kosten_Emissionen": ROOT / "configs/Paper_bilanz_emissionen/S3_kosten_emissionen.yaml",
}

COP_S1 = 3.5   # fixed COP für Lastfolge-Szenario


# ─── Bilanzraum-Analyse ───────────────────────────────────────────────────────

def compute_bilanzraeume(
    hp_el_mw_1h: pd.Series,
    co2_1h: pd.Series,
    co2_15m: pd.Series | None,
    label: str,
) -> pd.DataFrame:
    """
    CO2-Emissionen der WP unter 5 Bilanzräumen.

    hp_el_mw_1h : hourly HP electricity [MW] (optimizer output)
    co2_1h      : hourly CO2 factor [kg/MWh]
    co2_15m     : 15-min CO2 factor [kg/MWh] (optional, for finest Bilanzraum)
    """
    elec_mwh = hp_el_mw_1h * 1.0   # dt = 1h → MWh

    ef_annual = co2_1h.mean()
    ef_monthly = co2_1h.resample("ME").mean()
    ef_weekly  = co2_1h.resample("W-MON").mean()

    # Build lookup maps for speed
    def _make_monthly_map() -> pd.Series:
        return co2_1h.resample("ME").mean()

    def _monthly_ef(ts: pd.Timestamp) -> float:
        key = ts.to_period("M").to_timestamp() + pd.offsets.MonthEnd(0)
        return float(ef_monthly.get(key, ef_annual))

    def _weekly_ef(ts: pd.Timestamp) -> float:
        key = ts.to_period("W-MON").to_timestamp("W-MON")
        return float(ef_weekly.get(key, ef_annual))

    rows = []
    for ts, e_mwh, ef_h in zip(elec_mwh.index, elec_mwh, co2_1h):
        rows.append({
            "timestamp":      ts,
            "hp_el_mwh":      float(e_mwh),
            "ef_hourly":      float(ef_h),
            "co2_annual_kg":  float(e_mwh) * ef_annual,
            "co2_monthly_kg": float(e_mwh) * _monthly_ef(ts),
            "co2_weekly_kg":  float(e_mwh) * _weekly_ef(ts),
            "co2_hourly_kg":  float(e_mwh) * float(ef_h),
        })

    df = pd.DataFrame(rows).set_index("timestamp")

    # 15-min Bilanzraum: repeat each hourly dispatch value × 4 (constant within hour)
    # then use 15-min CO2 factors
    if co2_15m is not None:
        # Expand hourly dispatch to 15-min (each hour = 4 equal 15-min slots of 0.25 MWh)
        elec_15m = hp_el_mw_1h.resample("15min").ffill() * 0.25  # MW × 0.25h = MWh

        # Align 15-min CO2 with the expanded dispatch
        idx_common = elec_15m.index.intersection(co2_15m.index)
        co2_15_aligned = co2_15m.loc[idx_common]
        el_15_aligned  = elec_15m.loc[idx_common]
        co2_15m_total_by_hour = (el_15_aligned * co2_15_aligned).resample("1h").sum()

        co2_15m_series = co2_15m_total_by_hour.reindex(df.index, fill_value=0.0)
        df["co2_15min_kg"] = co2_15m_series.values
    else:
        df["co2_15min_kg"] = df["co2_hourly_kg"]   # fallback

    df.attrs["scenario"] = label
    return df


def bilanzraum_summary(df: pd.DataFrame, label: str) -> dict:
    e    = df["hp_el_mwh"].sum()
    ann  = df["co2_annual_kg"].sum()  / 1000.0
    mo   = df["co2_monthly_kg"].sum() / 1000.0
    wk   = df["co2_weekly_kg"].sum()  / 1000.0
    h    = df["co2_hourly_kg"].sum()  / 1000.0
    qh   = df["co2_15min_kg"].sum()   / 1000.0
    ref  = qh if qh > 0 else 1.0
    return {
        "Szenario":                     label,
        "WP-Strom [MWh/a]":             round(e,   1),
        "CO2 Jahres-Ø [t]":             round(ann, 1),
        "CO2 Monats-Ø [t]":             round(mo,  1),
        "CO2 Wochen-Ø [t]":             round(wk,  1),
        "CO2 Stündlich [t]":            round(h,   1),
        "CO2 15-Minuten [t]":           round(qh,  1),
        "Abw. Jahres [%]":              round((ann - ref) / ref * 100, 2),
        "Abw. Monats [%]":              round((mo  - ref) / ref * 100, 2),
        "Abw. Wochen [%]":              round((wk  - ref) / ref * 100, 2),
        "Abw. Stündlich [%]":           round((h   - ref) / ref * 100, 2),
    }


def monthly_breakdown(df: pd.DataFrame, label: str) -> pd.DataFrame:
    agg = df.resample("ME").agg({
        "hp_el_mwh":      "sum",
        "co2_annual_kg":  "sum",
        "co2_monthly_kg": "sum",
        "co2_weekly_kg":  "sum",
        "co2_hourly_kg":  "sum",
        "co2_15min_kg":   "sum",
    }) / 1000.0  # → Tonnen
    agg.columns = [
        "Strom_MWh",
        "CO2_jaehrlich_t", "CO2_monatlich_t", "CO2_woechentlich_t",
        "CO2_stuendlich_t", "CO2_15min_t",
    ]
    agg.index = agg.index.strftime("%Y-%m")
    agg.index.name = "Monat"
    agg["Szenario"] = label
    return agg


# ─── S1 Lastfolge (analytisch, kein Speicher) ────────────────────────────────

def compute_s1_lastfolge(data: pd.DataFrame) -> pd.Series:
    """P_el(t) = Q_demand(t) / COP — WP deckt Bedarf direkt, kein Speicher."""
    return (data["total_demand_MWth"] / COP_S1).rename("S1_Lastfolge")


# ─── Optimizer-Szenarien ─────────────────────────────────────────────────────

class ScenarioResult:
    def __init__(
        self,
        hp_el: pd.Series,
        tes_soc: pd.Series | None = None,
        tes_charge: pd.Series | None = None,
        tes_discharge: pd.Series | None = None,
    ):
        self.hp_el        = hp_el
        self.tes_soc      = tes_soc
        self.tes_charge   = tes_charge
        self.tes_discharge = tes_discharge


def run_scenario(name: str, cfg_path: Path) -> ScenarioResult | None:
    logger.info("=" * 60)
    logger.info("Running %s", name)
    t0 = time.perf_counter()
    try:
        workflow = run_workflow([str(cfg_path)])
    except Exception as exc:
        logger.error("%s FAILED: %s", name, exc)
        return None
    elapsed = time.perf_counter() - t0
    logger.info("%s solved in %.1f s", name, elapsed)

    result = workflow.pf_result
    if result is None or not result.series:
        logger.warning("%s: no PF result", name)
        return None

    s = result.series
    timestamps = pd.DatetimeIndex([pd.Timestamp(t) for t in result.table.index])
    if len(timestamps) == 0:
        logger.error("%s: no timestamps in result", name)
        return None

    def _get(keys: list[str]) -> pd.Series | None:
        for k in keys:
            if k in s:
                return pd.Series(list(s[k]), index=timestamps)
        return None

    hp_el = _get(["hp_main_Pel_MW", "hp_main_P_el_MW", "HP_P_el_MW", "P_buy_MW"])
    if hp_el is None:
        logger.error("%s: HP electricity series not found. Keys: %s",
                     name, list(s.keys())[:20])
        return None
    hp_el.name = name

    tes_soc       = _get(["TES_SOC_MWh", "tes_main_SOC_MWh"])
    tes_charge    = _get(["TES_charge_MW", "tes_main_charge_MW"])
    tes_discharge = _get(["TES_discharge_MW", "tes_main_discharge_MW"])

    return ScenarioResult(hp_el, tes_soc, tes_charge, tes_discharge)


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)

    data_1h = pd.read_csv(DATA_1H, index_col="Datum", parse_dates=True).sort_index()
    co2_1h  = data_1h["grid_co2_kg_MWh"]

    co2_15m = None
    if DATA_15M.exists():
        df15 = pd.read_csv(DATA_15M, index_col="Datum", parse_dates=True).sort_index()
        co2_15m = df15["grid_co2_kg_MWh"]
        logger.info("15-min CO2 data loaded: %d rows", len(co2_15m))
    else:
        logger.warning("15-min CSV not found — run preprocess_bilanz_memmingen.py first")

    # ── S1: analytisch ──
    hp_el_s1 = compute_s1_lastfolge(data_1h)
    optimizer_results: dict[str, ScenarioResult] = {}

    # ── S2, S3: Optimizer ──
    for name, cfg_path in CONFIGS.items():
        res = run_scenario(name, cfg_path)
        if res is not None:
            optimizer_results[name] = res

    # ── Bilanzraum-Analyse ──
    all_hp: dict[str, pd.Series] = {"S1_Lastfolge": hp_el_s1}
    for n, r in optimizer_results.items():
        all_hp[n] = r.hp_el

    summaries, monthly_dfs = [], []
    dispatch_cols: dict[str, pd.Series] = {}

    for label, hp_mw in all_hp.items():
        idx = hp_mw.index.intersection(co2_1h.index)
        if not len(idx):
            logger.warning("%s: no overlapping timestamps", label)
            continue
        hp_aligned  = hp_mw.loc[idx]
        co2_aligned = co2_1h.loc[idx]
        co2_15_aligned = co2_15m.loc[co2_15m.index.intersection(
            co2_15m.index)] if co2_15m is not None else None

        df_br = compute_bilanzraeume(hp_aligned, co2_aligned, co2_15m, label)
        summaries.append(bilanzraum_summary(df_br, label))
        monthly_dfs.append(monthly_breakdown(df_br, label))

        dispatch_cols[label] = hp_aligned
        # Add storage columns for S2/S3
        if label in optimizer_results:
            r = optimizer_results[label]
            if r.tes_soc is not None:
                dispatch_cols[f"{label}_TES_SOC_MWh"] = r.tes_soc
            if r.tes_charge is not None:
                dispatch_cols[f"{label}_TES_charge_MW"] = r.tes_charge
            if r.tes_discharge is not None:
                dispatch_cols[f"{label}_TES_discharge_MW"] = r.tes_discharge

    # ── Export ──
    if summaries:
        df_sum = pd.DataFrame(summaries)
        print("\n" + "=" * 80)
        print("BILANZRAUM-VERGLEICH — WP CO2-Emissionen (Referenz: 15-Minuten)")
        print("=" * 80)
        print(df_sum.to_string(index=False))
        print("=" * 80)

        with pd.ExcelWriter(OUTDIR / "bilanzraum_vergleich.xlsx", engine="openpyxl") as xl:
            df_sum.to_excel(xl, sheet_name="Vergleich", index=False)
            if monthly_dfs:
                df_mo = pd.concat(monthly_dfs)
                df_mo.to_excel(xl, sheet_name="Monatlich")
                for col in ["CO2_stuendlich_t", "CO2_15min_t", "CO2_monatlich_t",
                             "CO2_woechentlich_t", "CO2_jaehrlich_t"]:
                    if col in df_mo.columns:
                        piv = df_mo.pivot_table(index="Monat", columns="Szenario", values=col)
                        piv.to_excel(xl, sheet_name=f"Pivot_{col.replace('CO2_','').replace('_t','')}")
        print(f"Excel: {OUTDIR / 'bilanzraum_vergleich.xlsx'}")

    if dispatch_cols:
        df_disp = pd.DataFrame(dispatch_cols)
        df_disp.index.name = "Datum"
        df_disp.to_csv(OUTDIR / "dispatch_zeitreihen.csv")
        print(f"Dispatch CSV: {OUTDIR / 'dispatch_zeitreihen.csv'}")
        print(f"  Columns: {list(df_disp.columns)}")


if __name__ == "__main__":
    sys.exit(main())
