"""Convert epronet long-format CSV → Memmingen wide-format Excel.

Source: data/epronet_full_20260427.csv  (15-min, UTC, long: one row per endpoint×timestamp)
Target: data/Import_Data_Memmingen_epronet.xlsx  (15-min, CET/CEST, wide: one row per timestamp)

CONS_001 → V_1, ..., CONS_027 → V_27
All metrics kept per consumer. Shared columns (price, weather) kept once.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC  = ROOT / "data" / "epronet_full_20260427.csv"
DST  = ROOT / "data" / "Import_Data_Memmingen_epronet.xlsx"

# ── Per-consumer metric columns in source ─────────────────────────────────────
METRIC_COLS = [
    "flow_rate", "flow_rate_quality",
    "flow_temp", "flow_temp_quality",
    "return_temp", "return_temp_quality",
    "temp_diff", "temp_diff_quality",
    "power", "power_quality",
    "total_energy", "total_energy_quality",
    "total_volume", "total_volume_quality",
]

# ── Shared (weather + price) ───────────────────────────────────────────────────
SHARED_COLS = [
    "ambient_temp", "humidity", "solar_irradiance", "wind_speed",
    "da_price_eur_mwh",
]


def main() -> None:
    print(f"[1/5] Loading {SRC.name} …", flush=True)
    df = pd.read_csv(SRC, parse_dates=["time"])

    # UTC → Europe/Berlin (handles CET/CEST), then strip tzinfo for Excel compat
    df["time"] = (
        pd.to_datetime(df["time"], utc=True)
        .dt.tz_convert("Europe/Berlin")
        .dt.tz_localize(None)
    )

    # Consumer number: CONS_001 → 1, CONS_027 → 27
    df["v_num"] = df["endpoint_anon"].str.extract(r"(\d+)$").astype(int)

    n_endpoints = df["v_num"].nunique()
    n_timesteps = df["time"].nunique()
    print(f"      {n_endpoints} endpoints × {n_timesteps} timesteps "
          f"= {len(df):,} rows", flush=True)

    # ── Shared data: one row per timestamp (first non-null across endpoints) ──
    print("[2/5] Extracting shared columns ...", flush=True)
    shared = (
        df[["time"] + SHARED_COLS]
        .groupby("time", sort=True)
        .first()
        .ffill()   # price/weather are hourly → forward-fill to 15-min slots
    )

    # ── Pivot per-consumer metrics ─────────────────────────────────────────────
    print("[3/5] Pivoting consumer metrics …", flush=True)
    pivoted = df.pivot(index="time", columns="v_num", values=METRIC_COLS)

    # MultiIndex ('metric', v_num) → 'V_{n}_{metric}'
    pivoted.columns = [f"V_{v}_{m}" for m, v in pivoted.columns]
    pivoted = pivoted.sort_index()

    # ── Derived columns ────────────────────────────────────────────────────────
    print("[4/5] Computing demand + Waermebedarf …", flush=True)
    v_nums = sorted(df["v_num"].unique())  # [1..27]
    for n in v_nums:
        src_col = f"V_{n}_power"
        if src_col in pivoted.columns:
            pivoted[f"V_{n}_demand_MWth"] = pivoted[src_col] / 1000.0

    demand_cols = [f"V_{n}_demand_MWth" for n in v_nums
                   if f"V_{n}_demand_MWth" in pivoted.columns]

    # ── Combine ────────────────────────────────────────────────────────────────
    result = shared.join(pivoted, how="outer").reset_index()
    result["Waermebedarf"] = result[demand_cols].sum(axis=1, min_count=1)

    # ── Time columns (Tag / Zeit / Datum) ──────────────────────────────────────
    result.insert(0, "Datum", result["time"])
    result.insert(0, "Zeit", result["time"].dt.time)
    result.insert(0, "Tag", result["time"].dt.date)
    result = result.drop(columns=["time"])

    # ── Column order: Tag Zeit Datum price [V_N_demand …] Waermebedarf weather rest ──
    front = ["Tag", "Zeit", "Datum", "da_price_eur_mwh"]
    demand_block = demand_cols
    mid   = ["Waermebedarf", "ambient_temp", "humidity",
             "solar_irradiance", "wind_speed"]
    rest  = [c for c in result.columns
             if c not in front + demand_block + mid]

    result = result.reindex(columns=front + demand_block + mid + rest)

    # Rename to match target format
    result = result.rename(columns={
        "da_price_eur_mwh": "strompreis_EUR_MWh",
        "ambient_temp":     "outdoor_temp_C",
        "humidity":         "humidity_pct",
        "solar_irradiance": "solar_irradiance_Wm2",
        "wind_speed":       "wind_speed_ms",
    })

    # ── Write ──────────────────────────────────────────────────────────────────
    print(f"[5/5] Writing {DST.name}  ({len(result):,} rows × {len(result.columns)} cols) …",
          flush=True)
    result.to_excel(DST, index=False, sheet_name="Data", engine="openpyxl")
    print(f"Done -> {DST}", flush=True)

    # ── Quick sanity print ─────────────────────────────────────────────────────
    print("\nColumn overview:")
    print("  Front:  ", front[:4])
    print("  Demand: ", demand_block[:3], "…", demand_block[-1])
    print("  Weather:", mid)
    print("  Total cols:", len(result.columns))
    print("  Date range:",
          result["Tag"].iloc[0], "→", result["Tag"].iloc[-1])


if __name__ == "__main__":
    main()
