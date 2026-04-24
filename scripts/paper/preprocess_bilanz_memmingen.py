"""
Preprocess Memmingen Excel for Bilanzraum-Emissionen paper.

Input:  data/2025_04_14_Import_Data_Memmingen_dummy.xlsx
Output:
  data/memmingen_bilanz_emissionen_2025_1h.csv    Optimizer-Input (1h)
  data/memmingen_bilanz_emissionen_2025_15min.csv  CO2-Billing-Referenz (15min)

The 15-min CSV keeps the original resolution for the finest Bilanzraum
calculation. The optimizer always runs at 1h resolution.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT   = Path(__file__).resolve().parents[2]
XLSX   = ROOT / "data" / "2025_04_14_Import_Data_Memmingen_dummy.xlsx"
OUT_1H = ROOT / "data" / "memmingen_bilanz_emissionen_2025_1h.csv"
OUT_15 = ROOT / "data" / "memmingen_bilanz_emissionen_2025_15min.csv"


def main() -> None:
    print(f"Reading {XLSX.name} ...")
    df = pd.read_excel(XLSX, sheet_name="Data")
    df["Datum"] = pd.to_datetime(df["Datum"])
    df = df.set_index("Datum")
    df = df.select_dtypes(include="number")     # drop Zeit/Tag text columns
    df = df.sort_index().loc[~df.index.duplicated()]

    # Filter to 2025 where hourly CO2 data exists
    df = df.loc["2025-01-01":"2025-12-31 23:59"]
    df = df.resample("15min").mean()          # regularise any gap
    print(f"  2025 rows (15-min): {len(df)}")

    demand_cols = [c for c in df.columns if c.startswith("V_") and c.endswith("_demand_MWth")]

    # ── 15-min CSV: CO2 billing reference ────────────────────────────────────
    df_15 = df[["strompreis_EUR_MWh", "grid_co2_kg_MWh"]].copy()
    df_15["total_demand_MWth"] = df[demand_cols].sum(axis=1)
    df_15.index.name = "Datum"
    df_15.to_csv(OUT_15)
    print(f"  15-min CSV: {len(df_15)} rows -> {OUT_15.name}")

    # ── 1h CSV: optimizer input ───────────────────────────────────────────────
    df_1h = df[["strompreis_EUR_MWh", "grid_co2_kg_MWh"] + demand_cols].resample("1h").mean()
    df_1h["total_demand_MWth"] = df_1h[demand_cols].sum(axis=1)
    result = df_1h[["strompreis_EUR_MWh", "grid_co2_kg_MWh", "total_demand_MWth"]].copy()
    result.index.name = "Datum"
    result.to_csv(OUT_1H)

    print(f"  1h CSV:    {len(result)} rows -> {OUT_1H.name}")
    print(f"  Demand  min/mean/max: {result['total_demand_MWth'].min():.2f} / "
          f"{result['total_demand_MWth'].mean():.2f} / "
          f"{result['total_demand_MWth'].max():.2f} MWth")
    print(f"  CO2     min/mean/max: {result['grid_co2_kg_MWh'].min():.1f} / "
          f"{result['grid_co2_kg_MWh'].mean():.1f} / "
          f"{result['grid_co2_kg_MWh'].max():.1f} kg/MWh")


if __name__ == "__main__":
    sys.exit(main())
