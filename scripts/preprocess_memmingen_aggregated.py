"""
Preprocess Memmingen demand data: add aggregated columns for L1 and L2 configs.

Reads:  data/2025_04_14_Import_Data_Memmingen.csv  (semicolon-delimited)
Writes: data/2025_04_14_Import_Data_Memmingen_aggregated.csv

Added columns
─────────────
L1:
  total_demand_MWth       — sum of all 27 zone columns

L2 (5 aggregated zones, topology-based grouping):
  zone_A_demand_MWth      — V_1, V_2        (direct from E_1)
  zone_B_demand_MWth      — V_3–V_7         (j_1 → V_3, j_1 → j_2 → V_4–V_7)
  zone_C_demand_MWth      — V_8–V_14        (j_2 → j_3/j_4 subtree)
  zone_D_demand_MWth      — V_15–V_21       (j_1 → j_5 → j_6 subtree)
  zone_E_demand_MWth      — V_22–V_27       (j_6 → j_7 subtree)

Topology reference (Memmingen_L3.yaml):
  E_1 → V_1, V_2
  V_2 → j_1 → {V_3, j_2, j_5}
  j_2  → {V_4, V_5, V_6, V_7, j_3}
  j_3  → {V_8, V_9, j_4}
  j_4  → {V_10, V_11, V_12, V_13 → V_14}
  j_5  → {V_15, V_16, V_17 → V_18 → j_6}
  j_6  → {V_19, V_20, V_21, j_7}
  j_7  → {V_22, V_23, V_24, V_25 → V_26, V_27}
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC  = ROOT / "data" / "2025_04_14_Import_Data_Memmingen.csv"
DST  = ROOT / "data" / "2025_04_14_Import_Data_Memmingen_aggregated.csv"

# ── Zone groupings (L2) ───────────────────────────────────────────────────────
ZONE_GROUPS = {
    "zone_A": [f"V_{i}_demand_MWth" for i in [1, 2]],
    "zone_B": [f"V_{i}_demand_MWth" for i in [3, 4, 5, 6, 7]],
    "zone_C": [f"V_{i}_demand_MWth" for i in [8, 9, 10, 11, 12, 13, 14]],
    "zone_D": [f"V_{i}_demand_MWth" for i in [15, 16, 17, 18, 19, 20, 21]],
    "zone_E": [f"V_{i}_demand_MWth" for i in [22, 23, 24, 25, 26, 27]],
}

ALL_ZONES = [f"V_{i}_demand_MWth" for i in range(1, 28)]


def main() -> None:
    print(f"Reading {SRC} …")
    df = pd.read_csv(SRC, sep=";")

    # sanity check
    missing = [c for c in ALL_ZONES if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # ── L1: total demand ──────────────────────────────────────────────────────
    df["total_demand_MWth"] = df[ALL_ZONES].sum(axis=1)
    print(f"  total_demand_MWth: min={df['total_demand_MWth'].min():.1f}, "
          f"max={df['total_demand_MWth'].max():.1f} MWth")

    # ── L2: zone aggregates ───────────────────────────────────────────────────
    for zone, cols in ZONE_GROUPS.items():
        col = f"{zone}_demand_MWth"
        df[col] = df[cols].sum(axis=1)
        share = df[col].sum() / df["total_demand_MWth"].sum() * 100
        print(f"  {col}: share = {share:.1f}%")

    # ── write ─────────────────────────────────────────────────────────────────
    df.to_csv(DST, sep=",", index=False)
    print(f"\nWritten: {DST}")
    print(f"Columns added: total_demand_MWth + "
          f"{', '.join(z + '_demand_MWth' for z in ZONE_GROUPS)}")


if __name__ == "__main__":
    main()
