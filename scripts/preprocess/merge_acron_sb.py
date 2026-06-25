"""Stadtbach ACRON data merger.

Reads consumer Waermeleistung files + producer + pump station data from
  data/Stadtbach/11_Messwerte_Acron/{STATION}/

plus ancillary columns (outdoor temp, WRG, price, CO2) from the main import file
  data/Stadtbach/2025_04_14_Import_Data_stadtbach.xlsx

Outputs a single hourly Excel for 2025 (8760 rows):
  data/Stadtbach/stadtbach_acron_combined.xlsx

DEMAND APPROACH:
  - 7 stations with direct Waermeleistung measurements: use directly.
  - 17 stations without: distribute zone residual demand proportionally by ΔT.
    Zone totals are computed from pump station (PSW/PPS) flow measurements:
      Netz-West: PSW_Durchfluss_RL_nach_West × cp × ΔT_PSW
      Netz-Süd: BMHKW + HWS_computed + PPS_flow
      Netz-Mitte: HKW + GT-Ost - Q_west - Q_süd_from_hkw

Column structure (30 columns):
  Datum, outdoor_temp_C, strompreis_EUR_MWh, grid_co2_kg_MWh, WRG_1_Celsius, WRG1Q_MW,
  [7 measured consumers]_MW, [17 estimated consumers]_MW
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).resolve().parents[2]
ACRON_DIR = ROOT / "data" / "Stadtbach" / "11_Messwerte_Acron"
IMPORT_FILE = ROOT / "data" / "Stadtbach" / "2025_04_14_Import_Data_stadtbach.xlsx"
OUTPUT_FILE = ROOT / "data" / "Stadtbach" / "stadtbach_acron_combined.xlsx"

CP = 1.163e-3  # MW / (m³/h · K)

# Network zone assignment for the 17 unmeasured stations
# Format: (station_name, zone, tv_file, tr_file)
# zone: 'mitte', 'west', 'sued'
UNMEASURED_STATIONS = [
    # Netz-Mitte
    ("Fraunhofer",               "mitte", "Fraunhofer_Temp_VL.xlsx",         None),
    ("Josefinum",                "mitte", "Josefinum_Temp_VL.xlsx",           "Josefinum_Temp_RL.xlsx"),
    ("Kreissparkasse",           "mitte", "Kreissparkasse_Temp_VL.xlsx",      None),
    # Netz-Süd
    ("Hoher_Weg",                "sued",  None,                               None),
    ("Schlettererstr",           "sued",  "Schlettererstr_Temp_VL.xlsx",      "Schlettererstr_Temp_RL.xlsx"),
    ("Theodor-Heuss-Platz",      "sued",  "Theodor-Heuss-Platz_Temp_VL.xlsx","Theodor-Heuss-Platz_Temp_RL.xlsx"),
    ("Lise-Meitner-Str",         "sued",  None,                               None),
    ("Kurt-Schumacher-Str",      "sued",  "Kurt-Schumacher-Str_Temp_VL.xlsx","Kurt-Schumacher-Str_Temp_RL.xlsx"),
    # Netz-West
    ("Am_Mittleren_Moos",        "west",  "Am_MIttleren_Moos_Temp_VL.xlsx",  "Am_MIttleren_Moos_Temp_RL.xlsx"),
    ("Beethovenpark",            "west",  "Beethovenpark_Temp_VL.xlsx",       "Beethovenpark_Temp_RL.xlsx"),
    ("Don_Bosco",                "west",  None,                               None),
    ("Fuggerstr",                "west",  "Fuggerstr_Temp_VL.xlsx",           "Fuggerstr_Temp_RL.xlsx"),
    ("Grasiger_Weg",             "west",  "Grasiger_Weg_Temp_VL.xlsx",        "Grasiger_Weg_Temp_RL.xlsx"),
    ("Hans-Boeckler-Str",        "west",  "Hans-Boeckler-Str_Temp_VL.xlsx",  "Hans-Boeckler-Str_Temp_RL.xlsx"),
    ("Hooverstr",                "west",  "Hooverstr_Temp_VL.xlsx",           "Hooverstr_Temp_RL.xlsx"),
    ("Hunoldsgraben",            "west",  None,                               None),
    ("Siegfried-Aufhaeuser-Str", "west",  "Siegfried_Aufhaeuser-Str_Temp_VL.xlsx",
                                          "Siegfried_Aufhaeuser-Str_Temp_RL.xlsx"),
]

IDX_2025 = pd.date_range("2025-01-01", periods=8760, freq="h", name="Datum")


def _read_acron(station: str, filename: str) -> pd.Series:
    """Read ACRON file (skiprows=2, Wert column) and return as 8760-h series."""
    fp = ACRON_DIR / station / filename
    df = pd.read_excel(fp, skiprows=2, header=0, engine="openpyxl")
    dates = pd.to_datetime(df["Datum"]).dt.normalize()
    hours = df["Zeit"].str.strip().str.split("-").str[0].str.split(":").str[0].astype(int)
    idx = dates + pd.to_timedelta(hours, unit="h")
    s = pd.Series(pd.to_numeric(df["Wert"], errors="coerce").values, index=idx, dtype=float)
    s = s[~s.index.duplicated(keep="first")]
    if len(s) > 9000:
        s = s.resample("h").mean()
    s_2025 = s.reindex(IDX_2025).ffill().bfill().fillna(0.0)
    return s_2025


def _read_waermeleistung(station: str, filename: str) -> pd.Series:
    """Read consumer Waermeleistung file with gap-fill logging."""
    fp = ACRON_DIR / station / filename
    if not fp.exists():
        print(f"  [MISS] {station}: {filename} not found")
        return pd.Series(np.zeros(8760), index=IDX_2025)
    df = pd.read_excel(fp, skiprows=2, header=0, engine="openpyxl")
    dates = pd.to_datetime(df["Datum"]).dt.normalize()
    hours = df["Zeit"].str.strip().str.split("-").str[0].str.split(":").str[0].astype(int)
    idx = dates + pd.to_timedelta(hours, unit="h")
    s = pd.Series(pd.to_numeric(df["Wert"], errors="coerce").values, index=idx, dtype=float)
    s = s[~s.index.duplicated(keep="first")]
    if len(s) > 9000:
        s = s.resample("h").mean()
    s_2025 = s.reindex(IDX_2025)
    n_miss = int(s_2025.isna().sum())
    if n_miss > 0:
        s_2025 = s_2025.ffill().bfill().fillna(0.0)
        if n_miss > 100:
            print(f"  [FILL] {station}: {n_miss} gaps forward-filled")
    return s_2025


def _read_ancillary() -> pd.DataFrame:
    """Load ancillary columns from main import file (15-min → hourly)."""
    print(f"\nLoading ancillary columns from {IMPORT_FILE.name} ...")
    df = pd.read_excel(IMPORT_FILE, engine="openpyxl")
    df.index = pd.to_datetime(df["Datum"])
    df = df[~df.index.duplicated(keep="first")]
    df_h = df.resample("h").mean(numeric_only=True)

    wrg_temp_col = next((c for c in df.columns if c.startswith("WRG_1") and "MW" not in c), None)
    out = pd.DataFrame(index=IDX_2025)
    col_map = {
        "outdoor_temp_C":     "outdoor_temp_C",
        "strompreis_EUR_MWh": "strompreis_EUR_MWh",
        "grid_co2_kg_MWh":    "grid_co2_kg_MWh",
        "WRG1Q MW":           "WRG1Q_MW",
    }
    if wrg_temp_col:
        col_map[wrg_temp_col] = "WRG_1_Celsius"

    for src, dst in col_map.items():
        if src in df_h.columns:
            s = df_h[src].reindex(IDX_2025).ffill().bfill()
            out[dst] = s.values
            print(f"  [OK] {dst}: mean={float(s.mean()):.2f}")
        else:
            print(f"  [WARN] '{src}' missing -- using 0.0 for {dst}")
            out[dst] = 0.0
    if wrg_temp_col is None:
        out["WRG_1_Celsius"] = 0.0

    return out


def _compute_zone_demands() -> dict[str, pd.Series]:
    """Compute hourly zone-level demand from pump station and producer measurements.

    Returns dict with keys 'mitte', 'west', 'sued' — each an 8760-h Series in MW.
    """
    print("\nComputing zone demands from pump station flow measurements ...")

    # --- Netz-West via PSW ---
    psw_flow = _read_acron("PSW", "PSW_Durchfluss_RL_nach_West.xlsx")
    psw_tvl  = _read_acron("PSW", "PSW_Temp_VL.xlsx")
    psw_trl  = _read_acron("PSW", "PSW_Temp_RL.xlsx")
    Q_west = (CP * psw_flow * (psw_tvl - psw_trl)).clip(lower=0.0)
    print(f"  Netz-West: mean={Q_west.mean():.1f} MW  max={Q_west.max():.1f} MW")

    # --- Netz-Süd: BMHKW (measured) + Heizwerk_Sued (computed) + PPS flow ---
    Q_bmhkw = _read_acron("BMHKW", "BMHKW_Waermeleistung.xlsx")
    hws_flow = _read_acron("Heizwerk_Sued", "Heizwerk_Sued_Durchfluss.xlsx")
    hws_tvl  = _read_acron("Heizwerk_Sued", "Heizwerk_Sued_Temp_VL.xlsx")
    hws_trl  = _read_acron("Heizwerk_Sued", "Heizwerk_Sued_Temp_RL.xlsx")
    Q_hws = (CP * hws_flow * (hws_tvl - hws_trl)).clip(lower=0.0)
    pps_flow_sued = _read_acron("PSS", "PPS_Durchfluss_RL_nach_Sued.xlsx")
    pps_tvl  = _read_acron("PSS", "PPS_Temp_VL.xlsx")
    pps_trl  = _read_acron("PSS", "PPS_Temp_RL.xlsx")
    Q_pps_sued = (CP * pps_flow_sued * (pps_tvl - pps_trl)).clip(lower=0.0)
    Q_sued = Q_bmhkw + Q_hws + Q_pps_sued
    print(f"  Netz-Sued: mean={Q_sued.mean():.1f} MW  max={Q_sued.max():.1f} MW")
    print(f"    BMHKW={Q_bmhkw.mean():.1f}  HWS={Q_hws.mean():.1f}  PPS_add={Q_pps_sued.mean():.1f}")

    # --- Netz-Mitte: HKW + GT-Ost - Q_west - Q_pps_to_sued ---
    Q_hkw  = _read_acron("HKW",   "HKW_Waermeleistung.xlsx")
    Q_gtost = _read_acron("GT-Ost", "GT-Ost_Waermeleistung.xlsx")
    Q_mitte = (Q_hkw + Q_gtost - Q_west - Q_pps_sued).clip(lower=0.0)
    print(f"  Netz-Mitte: mean={Q_mitte.mean():.1f} MW  max={Q_mitte.max():.1f} MW")
    print(f"    HKW={Q_hkw.mean():.1f}  GT-Ost={Q_gtost.mean():.1f}")

    return {"mitte": Q_mitte, "west": Q_west, "sued": Q_sued}


def _get_delta_t(station: str, tv_file: str | None, tr_file: str | None,
                 fallback_dt: float = 35.0) -> pd.Series:
    """Read TV-TR for a station; return a 8760-h ΔT series clipped ≥0."""
    if tv_file and tr_file:
        try:
            tv = _read_acron(station, tv_file)
            tr = _read_acron(station, tr_file)
            dt = (tv - tr).clip(lower=0.0)
            return dt
        except Exception:
            pass
    # Fallback: constant typical ΔT
    return pd.Series(np.full(8760, fallback_dt), index=IDX_2025)


def _distribute_zone_demand(
    zone_total: pd.Series,
    zone_measured_sum: pd.Series,
    stations: list[tuple[str, str, str | None, str | None]],
) -> dict[str, pd.Series]:
    """Distribute (zone_total - zone_measured_sum) among unmeasured stations by ΔT weight.

    stations: list of (station, zone, tv_file, tr_file) tuples for this zone.
    Returns dict: station -> Series in MW.
    """
    residual = (zone_total - zone_measured_sum).clip(lower=0.0)

    # Get ΔT series for each unmeasured station
    dts = {}
    for station, _zone, tv_file, tr_file in stations:
        dts[station] = _get_delta_t(station, tv_file, tr_file)

    # Normalised weights (time-varying)
    dt_sum = sum(dts.values())
    dt_sum = dt_sum.replace(0.0, np.nan)

    result = {}
    for station, dt_series in dts.items():
        weight = dt_series.div(dt_sum).fillna(1.0 / len(dts))
        demand = (residual * weight).clip(lower=0.0)
        result[station] = demand

    return result


def build_combined() -> None:
    print("=" * 60)
    print("Stadtbach ACRON Merge -- 2025 hourly")
    print(f"  Output: {OUTPUT_FILE}")
    print("=" * 60)

    # 1. Ancillary columns
    ancillary = _read_ancillary()

    # 2. Zone totals from pump station/producer measurements
    zone_q = _compute_zone_demands()

    # 3. Direct Waermeleistung measurements (7 stations)
    print("\nLoading directly measured consumer stations (7) ...")
    DIRECT = {
        "August-Wessels-Str":   ("August-Wessels-Str",  "August-Wessels-Str_Waermeleistung.xlsx",  "west"),
        "Klinikum":             ("Klinikum",             "Klinikum_Waermeleistung.xlsx",              "mitte"),
        "KUKA":                 ("KUKA",                 "KUKA_Waermeleistung.xlsx",                  "mitte"),
        "Lechhauser_Str":       ("Lechhauser_Str",       "Lechhauser_Str_HA_Waermeleistung.xlsx",     "sued"),
        "MAN":                  ("MAN",                  "MAN_Waermeleistung_Station.xlsx",            "mitte"),
        "SIGMA_Technopark":     ("SIGMA_Technopark",     "SIGMA_Technopark_Waermeleistung.xlsx",       "mitte"),
        "UNI":                  ("UNI",                  "UNI_Waermeleistung.xlsx",                    "mitte"),
    }
    measured: dict[str, pd.Series] = {}
    zone_measured_sum = {"mitte": None, "west": None, "sued": None}

    for name, (station, fn, zone) in DIRECT.items():
        s = _read_waermeleistung(station, fn)
        measured[name] = s
        if zone_measured_sum[zone] is None:
            zone_measured_sum[zone] = s.copy()
        else:
            zone_measured_sum[zone] = zone_measured_sum[zone] + s
        print(f"  [OK]  {name:<35} mean={float(s.mean()):.2f} MW  max={float(s.max()):.2f} MW")

    # Ensure all zones have a measured-sum series
    for zone in zone_measured_sum:
        if zone_measured_sum[zone] is None:
            zone_measured_sum[zone] = pd.Series(np.zeros(8760), index=IDX_2025)

    # 4. Distribute unmeasured demand by zone
    print("\nEstimating demand for 17 unmeasured stations via zone dT distribution ...")
    by_zone: dict[str, list] = {"mitte": [], "west": [], "sued": []}
    for entry in UNMEASURED_STATIONS:
        by_zone[entry[1]].append(entry)

    estimated: dict[str, pd.Series] = {}
    for zone, entries in by_zone.items():
        if not entries:
            continue
        est = _distribute_zone_demand(zone_q[zone], zone_measured_sum[zone], entries)
        for station, s in est.items():
            estimated[station] = s
            print(f"  [EST] {station:<35} zone={zone}  mean={float(s.mean()):.2f} MW  max={float(s.max()):.2f} MW")

    # 5. Combine into output DataFrame
    combined = ancillary.copy()
    # Add all 24 consumer columns in ACRON-station order
    all_order = [
        "Am_Mittleren_Moos", "August-Wessels-Str", "Beethovenpark", "Don_Bosco",
        "Fraunhofer", "Fuggerstr", "Grasiger_Weg", "Hans-Boeckler-Str",
        "Hoher_Weg", "Hooverstr", "Hunoldsgraben", "Josefinum",
        "Klinikum", "Kreissparkasse", "KUKA", "Kurt-Schumacher-Str",
        "Lechhauser_Str", "Lise-Meitner-Str", "MAN", "Schlettererstr",
        "Siegfried-Aufhaeuser-Str", "SIGMA_Technopark", "Theodor-Heuss-Platz", "UNI",
    ]
    for station in all_order:
        col = f"{station}_MW"
        if station in measured:
            combined[col] = measured[station].values
        elif station in estimated:
            combined[col] = estimated[station].values
        else:
            combined[col] = np.zeros(8760)

    combined = combined.reset_index()

    # 6. Summary and total demand column (required by calion.io.loader heat_candidates)
    demand_cols = [f"{s}_MW" for s in all_order]
    total = combined[demand_cols].sum(axis=1)
    combined["Wärmebedarf MW"] = total.values
    print(f"\nTotal modelled demand: mean={total.mean():.1f} MW  max={total.max():.1f} MW  min={total.min():.1f} MW")

    # 7. Save
    combined.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")
    print(f"\nSaved {OUTPUT_FILE}")
    print(f"Shape: {combined.shape[0]} rows x {combined.shape[1]} columns")


if __name__ == "__main__":
    build_combined()
