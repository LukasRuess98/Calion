"""
smard_download.py
=================
Paper 3 — CO2-Bilanzierung in elektrifizierten Wärmenetzen
Datenpipeline: SMARD → Emissionsfaktoren G1–G6 + MEFS + EPEX-Preise

Autor:  Lukas Ruess / CALION Framework
Stand:  Juni 2026
Daten:  Bilanzjahr 2025, Deutschland

Outputs (alle im Ordner ./data/):
  generation_15min_2025.parquet   — Erzeugung je Energieträger, 15-min [MW]
  generation_1h_2025.parquet      — Erzeugung je Energieträger, stündlich [MW]
  load_1h_2025.parquet            — Netzlast, stündlich [MW]
  prices_1h_2025.parquet          — Day-Ahead Preise EPEX Spot, stündlich [EUR/MWh]
  ef_all_granularities_2025.parquet  — EF G1..G6 + MEFS, stündlich [gCO2/kWh]
  co2_summary.csv                 — Jahres-/Monatswerte für Quick-Check
"""

import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

import requests
import numpy as np
import pandas as pd

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL   = "https://www.smard.de/app/chart_data"
DATA_DIR   = Path("./data")
YEAR       = 2025
SLEEP_S    = 0.4          # politeness delay between API calls
RETRY_MAX  = 3
UBA_EF_ANNUAL = 344.0    # g CO2/kWh — UBA Jahreswert 2025

# ── SMARD Filter-IDs ──────────────────────────────────────────────────────────
# Erzeugung (Nettoeinspeisung in öffentliches Netz)
FILTERS_GENERATION = {
    "biomasse":        1223,
    "wasserkraft":     1224,
    "wind_offshore":   1225,
    "wind_onshore":    1226,
    "photovoltaik":    1227,
    "sonstige_ee":     1228,
    "kernenergie":     1229,
    "braunkohle":      1230,
    "steinkohle":      1231,
    "erdgas":          1232,
    "pumpspeicher":    1233,
    "sonstige_konv":   1234,
}
FILTER_LOAD      = 4066   # Netzlast (Verbrauch)
FILTER_PRICE     = 4169   # Day-Ahead Preis DE-LU (EUR/MWh)

# EE-Quellen für EE-Anteil-Berechnung
EE_SOURCES = ["biomasse", "wasserkraft", "wind_offshore", "wind_onshore",
              "photovoltaik", "sonstige_ee"]

# Konventionelle Quellen für Emissionsberechnung
CONV_SOURCES = ["braunkohle", "steinkohle", "erdgas", "kernenergie",
                "pumpspeicher", "sonstige_konv"]

# Spezifische CO2-Emissionsfaktoren [g CO2/kWh_el] — attributional, Direktemissionen
# Quellen: UBA, IPCC AR6, Fritsche et al.
EF_DIRECT = {
    "braunkohle":    980.0,   # Braunkohle IGCC/Dampf, Durchschnitt DE
    "steinkohle":    750.0,   # Steinkohle Dampf, Durchschnitt DE
    "erdgas":        400.0,   # GuD, eta~55%; OCGT höher (~550), vereinfacht
    "kernenergie":     0.0,   # Direkte CO2-Emissionen = 0 (Scope 1)
    "pumpspeicher":    0.0,   # Speicher — CO2 im Einspeis-Strom erfasst
    "sonstige_konv":  500.0,  # Öl, Abfall etc. — konservativer Mittelwert
    "biomasse":       25.0,   # Biogene CO2, netto gering (Nachhaltigkeitsannahme)
    "wasserkraft":     0.0,
    "wind_offshore":   0.0,
    "wind_onshore":    0.0,
    "photovoltaik":    0.0,
    "sonstige_ee":     0.0,
}

# Marginale EF für MEFS-Approximation [g CO2/kWh]
EF_MARGINAL = {
    "gas_dominant":   400.0,   # GuD als Grenzkraftwerk
    "kohle_dominant": 850.0,   # Steinkohle/Braunkohle als Grenzkraftwerk (Mischung)
    "ee_dominant":     50.0,   # Pumpspeicher / Demand Response marginal
}


# ── API Helpers ───────────────────────────────────────────────────────────────

def _get_index(filter_id: int, resolution: str = "quarterhour") -> list[int]:
    """Fetch available weekly timestamps for a given filter and resolution."""
    url = f"{BASE_URL}/{filter_id}/DE/index_{resolution}.json"
    for attempt in range(RETRY_MAX):
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            return r.json()["timestamps"]
        except Exception as e:
            log.warning(f"Index fetch attempt {attempt+1} failed for filter {filter_id}: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch index for filter {filter_id}")


def _get_chunk(filter_id: int, timestamp: int, resolution: str = "quarterhour") -> list:
    """Fetch one weekly data chunk from SMARD."""
    url = f"{BASE_URL}/{filter_id}/DE/{filter_id}_DE_{resolution}_{timestamp}.json"
    for attempt in range(RETRY_MAX):
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            return r.json().get("series", [])
        except Exception as e:
            log.warning(f"Chunk fetch attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch chunk {timestamp} for filter {filter_id}")


def _fetch_full_year(
    filter_id: int,
    name: str,
    year: int = YEAR,
    resolution: str = "quarterhour",
) -> pd.Series:
    """
    Download all weekly chunks for a given year and return a
    timezone-aware pd.Series indexed in Europe/Berlin time.
    """
    log.info(f"  Downloading: {name} (filter={filter_id}, res={resolution})")
    timestamps = _get_index(filter_id, resolution)

    # Filter to chunks that overlap with target year
    year_ts = [
        t for t in timestamps
        if datetime.fromtimestamp(t / 1000, tz=timezone.utc).year in (year - 1, year, year + 1)
    ]

    all_series = []
    for ts in year_ts:
        chunk = _get_chunk(filter_id, ts, resolution)
        all_series.extend(chunk)
        time.sleep(SLEEP_S)

    if not all_series:
        raise ValueError(f"No data fetched for {name} / {year}")

    # Build Series
    idx = pd.to_datetime([row[0] for row in all_series], unit="ms", utc=True)
    vals = pd.array([row[1] for row in all_series], dtype="Float64")
    s = pd.Series(vals, index=idx, name=name)

    # Convert to local time (CET/CEST) and filter to exact year
    s.index = s.index.tz_convert("Europe/Berlin")
    s = s[s.index.year == year]
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="first")]

    log.info(f"    → {len(s)} data points, nulls: {s.isna().sum()}")
    return s


# ── Download Functions ────────────────────────────────────────────────────────

def download_generation(year: int = YEAR) -> pd.DataFrame:
    """Download all generation sources at 15-min resolution → [MW]."""
    log.info("=" * 60)
    log.info("STEP 1: Downloading generation mix (15-min)")
    log.info("=" * 60)

    series = {}
    for name, fid in FILTERS_GENERATION.items():
        s = _fetch_full_year(fid, name, year, resolution="quarterhour")
        # Fill small gaps (≤ 2 steps = 30 min) with linear interpolation
        s = s.interpolate(method="linear", limit=2)
        s = s.clip(lower=0)  # no negative generation
        series[name] = s

    df = pd.DataFrame(series)

    # Reindex to complete 15-min grid (handles DST gaps/overlaps)
    full_idx = pd.date_range(
        start=f"{year}-01-01 00:00",
        end=f"{year}-12-31 23:45",
        freq="15min",
        tz="Europe/Berlin",
    )
    df = df.reindex(full_idx)
    df = df.interpolate(method="linear", limit=4)  # fill DST gaps

    log.info(f"Generation DataFrame: {df.shape}, NaN total: {df.isna().sum().sum()}")
    return df


def download_load(year: int = YEAR) -> pd.Series:
    """Download grid load at 15-min resolution → [MW]."""
    log.info("=" * 60)
    log.info("STEP 2: Downloading grid load (15-min)")
    log.info("=" * 60)
    s = _fetch_full_year(FILTER_LOAD, "netzlast", year, resolution="quarterhour")
    s = s.interpolate(method="linear", limit=4).clip(lower=0)
    return s


def download_prices(year: int = YEAR) -> pd.Series:
    """Download Day-Ahead spot prices at hourly resolution → [EUR/MWh]."""
    log.info("=" * 60)
    log.info("STEP 3: Downloading Day-Ahead prices (hourly)")
    log.info("=" * 60)
    s = _fetch_full_year(FILTER_PRICE, "da_price", year, resolution="hour")
    # Prices can be negative — do NOT clip
    s = s.interpolate(method="linear", limit=2)
    return s


# ── Emission Factor Computation ───────────────────────────────────────────────

def compute_emission_factors(
    gen_15min: pd.DataFrame,
    load_15min: pd.Series,
    uba_annual: float = UBA_EF_ANNUAL,
) -> pd.DataFrame:
    """
    Compute all emission factor time series on hourly resolution.

    Returns DataFrame with columns:
      ef_g5_m1    — Stündlich, attributional [g CO2/kWh]
      ef_g6_m1    — Viertelstündlich, attributional [g CO2/kWh]
      ef_g5_m2    — Stündlich, MEFS-approximiert [g CO2/kWh]
      ef_g4       — Täglich gemittelt, attributional [g CO2/kWh]
      ef_g3       — Wöchentlich gemittelt, attributional [g CO2/kWh]
      ef_g2       — Monatlich gemittelt, attributional [g CO2/kWh]
      ef_g1       — Jahreswert (UBA), konstant [g CO2/kWh]
      ee_share    — EE-Anteil stündlich [0..1]
      residual_load_gw — Residuallast stündlich [GW]
    """
    log.info("=" * 60)
    log.info("STEP 4: Computing emission factors G1–G6 + MEFS")
    log.info("=" * 60)

    # ── G6: Attributional EF, 15-min ─────────────────────────────────────
    log.info("  Computing G6 (15-min attributional)...")
    total_gen_15min = gen_15min.sum(axis=1).replace(0, np.nan)

    # Weighted average EF from generation mix
    weighted_ef_15min = pd.Series(0.0, index=gen_15min.index)
    for source, ef in EF_DIRECT.items():
        if source in gen_15min.columns and ef > 0:
            weighted_ef_15min += gen_15min[source] * ef
    ef_g6 = (weighted_ef_15min / total_gen_15min).fillna(uba_annual)
    ef_g6.name = "ef_g6_m1"

    # ── G5: Attributional EF, hourly ─────────────────────────────────────
    log.info("  Computing G5 (hourly attributional)...")
    # Resample: energy-weighted mean (sum numerator + sum denominator, then divide)
    num_1h = weighted_ef_15min.resample("1h").sum()
    den_1h = total_gen_15min.resample("1h").sum()
    ef_g5 = (num_1h / den_1h).fillna(uba_annual)
    ef_g5.name = "ef_g5_m1"

    # ── G4: Daily mean ────────────────────────────────────────────────────
    log.info("  Computing G4 (daily mean)...")
    ef_g4_daily = ef_g5.resample("1D").mean()
    # Expand back to hourly (each hour gets the day's mean)
    ef_g4 = ef_g5.resample("1D").transform("mean")
    ef_g4.name = "ef_g4"

    # ── G3: Weekly mean ───────────────────────────────────────────────────
    log.info("  Computing G3 (weekly mean, ISO week Mon–Sun)...")
    ef_g3 = ef_g5.resample("W-MON", closed="left", label="left").transform("mean")
    ef_g3.name = "ef_g3"

    # ── G2: Monthly mean ──────────────────────────────────────────────────
    log.info("  Computing G2 (monthly mean)...")
    ef_g2 = ef_g5.resample("ME").transform("mean")
    ef_g2.name = "ef_g2"

    # ── G1: Annual constant (UBA) ─────────────────────────────────────────
    log.info(f"  G1 = constant {uba_annual} g CO2/kWh (UBA 2025)")
    ef_g1 = pd.Series(uba_annual, index=ef_g5.index, name="ef_g1")

    # ── MEFS: Marginal EF, hourly (M2) ───────────────────────────────────
    log.info("  Computing MEFS (Merit-Order approximation, M2)...")

    # Hourly generation mix
    gen_1h = gen_15min.resample("1h").mean()
    load_1h = load_15min.resample("1h").mean()

    total_gen_1h = gen_1h.sum(axis=1).replace(0, np.nan)

    ee_1h = gen_1h[EE_SOURCES].sum(axis=1)
    ee_share_1h = (ee_1h / total_gen_1h).fillna(0).clip(0, 1)

    gas_1h   = gen_1h["erdgas"]
    kohle_1h = gen_1h["braunkohle"] + gen_1h["steinkohle"]

    # Residual load: load minus volatile renewables (wind + PV)
    volatile_ee = gen_1h[["wind_offshore", "wind_onshore", "photovoltaik"]].sum(axis=1)
    residual_load = (load_1h - volatile_ee).clip(lower=0)

    # Merit-Order assignment
    #   If EE share > 95% → storage / DR marginal (very low EF)
    #   Else if Gas > Coal → Gas is marginal
    #   Else → Coal is marginal
    mefs = pd.Series(index=ef_g5.index, dtype=float)
    mask_ee   = ee_share_1h >= 0.95
    mask_gas  = (~mask_ee) & (gas_1h >= kohle_1h)
    mask_coal = (~mask_ee) & (gas_1h < kohle_1h)

    mefs[mask_ee]   = EF_MARGINAL["ee_dominant"]
    mefs[mask_gas]  = EF_MARGINAL["gas_dominant"]
    mefs[mask_coal] = EF_MARGINAL["kohle_dominant"]
    mefs.name = "ef_g5_m2"

    # ── Assemble output DataFrame ─────────────────────────────────────────
    out = pd.DataFrame({
        "ef_g1":            ef_g1,
        "ef_g2":            ef_g2,
        "ef_g3":            ef_g3,
        "ef_g4":            ef_g4,
        "ef_g5_m1":         ef_g5,
        "ef_g5_m2":         mefs,
        "ef_g6_m1":         ef_g6.resample("1h").mean(),  # 15-min stored separately
        "ee_share_1h":      ee_share_1h,
        "residual_load_gw": residual_load / 1000,
    })

    # ── Validation ────────────────────────────────────────────────────────
    log.info("  Validation:")
    annual_mean_g5 = ef_g5.mean()
    log.info(f"    G5 annual mean:  {annual_mean_g5:.1f} g/kWh  (UBA: {uba_annual:.1f})")
    log.info(f"    MEFS annual mean: {mefs.mean():.1f} g/kWh")
    log.info(f"    EE-share annual:  {ee_share_1h.mean()*100:.1f}%")
    log.info(f"    EE-dominant hours (>95%): {mask_ee.sum()} h")
    log.info(f"    Gas-marginal hours:       {mask_gas.sum()} h")
    log.info(f"    Coal-marginal hours:      {mask_coal.sum()} h")

    deviation = abs(annual_mean_g5 - uba_annual) / uba_annual * 100
    if deviation > 15:
        log.warning(
            f"  G5 annual mean deviates {deviation:.1f}% from UBA value — "
            "check EF_DIRECT values or generation mix data!"
        )
    else:
        log.info(f"    Deviation from UBA: {deviation:.1f}%  ✓")

    return out, ef_g6  # return 15-min G6 separately


def compute_co2_summary(
    ef_df: pd.DataFrame,
    p_el_profiles: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """
    Quick-check: compute annual CO2 [t/a] for each EF variant
    applied to a flat 1 MW reference load.
    If p_el_profiles dict is provided, compute for each profile too.
    """
    log.info("  Computing CO2 summary (reference load = 1 MW flat)...")
    results = []

    ref_load = pd.Series(1.0, index=ef_df.index)  # 1 MW constant

    for col in [c for c in ef_df.columns if c.startswith("ef_")]:
        ef = ef_df[col]
        co2_annual = (ref_load * ef / 1e6).sum()  # MW * g/kWh * 1h = MWh * g/kWh / 1e6 = t
        results.append({
            "ef_variant": col,
            "annual_mean_g_kwh": ef.mean(),
            "co2_ref_1mw_t_per_a": co2_annual,
        })

    df_summary = pd.DataFrame(results).set_index("ef_variant")
    log.info("\n" + df_summary.to_string())
    return df_summary


# ── I/O Helpers ───────────────────────────────────────────────────────────────

def save_parquet(df: pd.DataFrame | pd.Series, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(df, pd.Series):
        df = df.to_frame()
    df.to_parquet(path, engine="pyarrow", compression="snappy")
    size_kb = path.stat().st_size / 1024
    log.info(f"  Saved → {path}  ({size_kb:.0f} KB)")


def load_parquet(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path, engine="pyarrow")
    log.info(f"  Loaded ← {path}  ({df.shape})")
    return df


# ── Main Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    year: int = YEAR,
    force_download: bool = False,
    data_dir: Path = DATA_DIR,
) -> dict:
    """
    Full data pipeline. Skips download steps if cached files exist
    (unless force_download=True).

    Returns dict with all DataFrames.
    """
    data_dir.mkdir(parents=True, exist_ok=True)

    # ── Paths ──────────────────────────────────────────────────────────────
    p_gen15  = data_dir / f"generation_15min_{year}.parquet"
    p_load15 = data_dir / f"load_15min_{year}.parquet"
    p_price1 = data_dir / f"prices_1h_{year}.parquet"
    p_ef     = data_dir / f"ef_all_granularities_{year}.parquet"
    p_ef_g6  = data_dir / f"ef_g6_15min_{year}.parquet"
    p_sum    = data_dir / f"co2_summary_{year}.csv"

    # ── Step 1: Generation ─────────────────────────────────────────────────
    if not p_gen15.exists() or force_download:
        gen_15min = download_generation(year)
        save_parquet(gen_15min, p_gen15)
    else:
        log.info(f"Cache hit: {p_gen15.name}")
        gen_15min = load_parquet(p_gen15)

    # ── Step 2: Load ───────────────────────────────────────────────────────
    if not p_load15.exists() or force_download:
        load_15min = download_load(year)
        save_parquet(load_15min, p_load15)
    else:
        log.info(f"Cache hit: {p_load15.name}")
        load_15min = load_parquet(p_load15)["netzlast"]

    # ── Step 3: Prices ─────────────────────────────────────────────────────
    if not p_price1.exists() or force_download:
        prices_1h = download_prices(year)
        save_parquet(prices_1h, p_price1)
    else:
        log.info(f"Cache hit: {p_price1.name}")
        prices_1h = load_parquet(p_price1)["da_price"]

    # ── Step 4: Emission Factors ───────────────────────────────────────────
    if not p_ef.exists() or force_download:
        ef_df, ef_g6_15min = compute_emission_factors(gen_15min, load_15min)
        save_parquet(ef_df, p_ef)
        save_parquet(ef_g6_15min, p_ef_g6)
    else:
        log.info(f"Cache hit: {p_ef.name}")
        ef_df        = load_parquet(p_ef)
        ef_g6_15min  = load_parquet(p_ef_g6).iloc[:, 0]

    # ── Step 5: Summary ────────────────────────────────────────────────────
    summary = compute_co2_summary(ef_df)
    summary.to_csv(p_sum)
    log.info(f"  Saved → {p_sum}")

    log.info("=" * 60)
    log.info("Pipeline complete.")
    log.info(f"  Files in {data_dir}:")
    for f in sorted(data_dir.iterdir()):
        log.info(f"    {f.name:45s}  {f.stat().st_size/1024:8.1f} KB")

    return {
        "generation_15min": gen_15min,
        "load_15min":       load_15min,
        "prices_1h":        prices_1h,
        "ef_df":            ef_df,
        "ef_g6_15min":      ef_g6_15min,
        "summary":          summary,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download SMARD data and compute CO2 emission factors for Paper 3."
    )
    parser.add_argument("--year",  type=int, default=YEAR,  help="Bilanzjahr (default: 2025)")
    parser.add_argument("--force", action="store_true",     help="Redownload even if cached")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()

    result = run_pipeline(year=args.year, force_download=args.force, data_dir=args.data_dir)

    # Quick sanity print
    print("\n── Quick Sanity Check ──────────────────────────────────")
    ef = result["ef_df"]
    print(f"EF G1 (const):     {ef['ef_g1'].mean():.1f} g/kWh")
    print(f"EF G5 M1 (hourly): {ef['ef_g5_m1'].mean():.1f} g/kWh  (min={ef['ef_g5_m1'].min():.0f}, max={ef['ef_g5_m1'].max():.0f})")
    print(f"EF G5 M2 (MEFS):   {ef['ef_g5_m2'].mean():.1f} g/kWh")
    print(f"EE-share annual:   {ef['ee_share_1h'].mean()*100:.1f}%")
    print(f"Price range:       {result['prices_1h'].min():.1f} .. {result['prices_1h'].max():.1f} EUR/MWh")
    print(f"Data points:       {len(ef)} hours  (expected 8760)")
