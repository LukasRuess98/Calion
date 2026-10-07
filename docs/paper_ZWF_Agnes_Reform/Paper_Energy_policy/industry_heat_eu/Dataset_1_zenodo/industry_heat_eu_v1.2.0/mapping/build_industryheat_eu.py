# -*- coding: utf-8 -*-
"""Build IndustryHeat-EU from JRC-IDEES-2023 + an externalised process->category mapping.

The mapping lives in ``process_category_mapping.csv`` next to this script, so the whole
dataset can be rebuilt from a clean download of JRC-IDEES-2023 plus that one file.

Usage
-----
    python build_industryheat_eu.py --idees /path/to/JRC-IDEES-2023 --out /path/to/output
    python build_industryheat_eu.py --idees /path/to/JRC-IDEES-2023 --summary-only
"""
import argparse
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
YEAR = 2023
KTOE_TO_TWH = 0.01163

# block -> (sheet stem, first data row (0-based), number of rows)
BLOCKS = {
    "primary_steel":        ("ISI",   5, 46),
    "secondary_steel":      ("ISI",  54, 41),
    "primary_aluminium":    ("NFM",   5, 64),
    "secondary_aluminium":  ("NFM",  72, 42),
    "other_nfm":            ("NFM", 115, 43),
    "basic_chemicals":      ("CHI",   5, 54),
    "other_chemicals":      ("CHI",  61, 46),
    "pharmaceuticals":      ("CHI", 110, 46),
    "cement":               ("NMM",   5, 41),
    "ceramics":             ("NMM",  48, 49),
    "glass":                ("NMM",  99, 29),
    "pulp_and_paper":       ("PPA",   5, 76),
    "food_bev_tobacco":     ("FBT",   5, 76),
    "transport_equipment":  ("TRE",   5, 43),
    "machinery_equipment":  ("MAE",   5, 43),
    "textiles_leather":     ("TEL",   5, 55),
    "wood_products":        ("WWP",   5, 44),
}

# block -> published sub-sector column
SECTOR = {
    "primary_steel": "Primary Steel (TWh)",
    "secondary_steel": "Secondary Steel (TWh)",
    "primary_aluminium": "Non-ferrous Metals (TWh)",
    "secondary_aluminium": "Non-ferrous Metals (TWh)",
    "other_nfm": "Non-ferrous Metals (TWh)",
    "basic_chemicals": "Chemicals (TWh)",
    "other_chemicals": "Chemicals (TWh)",
    "pharmaceuticals": "Chemicals (TWh)",
    "cement": "Cement (TWh)",
    "ceramics": "Ceramics and Glass (TWh)",
    "glass": "Ceramics and Glass (TWh)",
    "pulp_and_paper": "Pulp and Paper (TWh)",
    "food_bev_tobacco": "Food, Beverages and Tobacco (TWh)",
    "transport_equipment": "Transport Equipment (TWh)",
    "machinery_equipment": "Machinery and Equipment (TWh)",
    "textiles_leather": "Textiles and Leather (TWh)",
    "wood_products": "Wood and Wood Products (TWh)",
}

CATEGORY_ORDER = [
    "Electricity Other",
    "Electricity Thermal",
    "Steam (non-electric boilers)",
    "Non-electric process heat (<100 C)",
    "Non-electric process heat (100-400 C)",
    "Non-electric process heat (400-1000 C)",
    "Non-electric process heat (>1000 C)",
]
SECTOR_ORDER = [
    "Primary Steel (TWh)", "Secondary Steel (TWh)", "Chemicals (TWh)", "Cement (TWh)",
    "Pulp and Paper (TWh)", "Food, Beverages and Tobacco (TWh)", "Transport Equipment (TWh)",
    "Machinery and Equipment (TWh)", "Textiles and Leather (TWh)", "Wood and Wood Products (TWh)",
    "Non-ferrous Metals (TWh)", "Ceramics and Glass (TWh)",
]

def load_mapping():
    """Process-to-category mapping: one row per mapped JRC-IDEES process.

    Rows that carry no category (the per-carrier sub-rows under a mapped parent) are absent
    from the file and are therefore not counted, which is what keeps each block sum equal to
    its JRC-IDEES block total.
    """
    return pd.read_csv(os.path.join(HERE, "process_category_mapping.csv"))


def build(idees_dir, mapping, metric):
    """Return {country: DataFrame(category x sector)} in TWh."""
    sheets = {b: (s + "_" + metric, sk, nr) for b, (s, sk, nr) in BLOCKS.items()}
    out = {}
    for country in sorted(os.listdir(idees_dir)):
        path = os.path.join(idees_dir, country, "JRC-IDEES-%d_Industry_%s.xlsx" % (YEAR, country))
        if not os.path.isfile(path):
            continue
        xl = pd.ExcelFile(path)
        cache = {}
        tab = pd.DataFrame(0.0, index=CATEGORY_ORDER, columns=SECTOR_ORDER)
        for block, (sheet, sk, nr) in sheets.items():
            if sheet not in cache:
                cache[sheet] = xl.parse(sheet, header=None)
            raw = cache[sheet]
            year_cols = [j for j, v in raw.iloc[0].items() if v == YEAR]
            if len(year_cols) != 1:
                raise ValueError("year %d not uniquely found in %s::%s" % (YEAR, path, sheet))
            proc = [str(x).strip() for x in raw.iloc[sk:sk + nr, 0].values]
            val = pd.to_numeric(pd.Series(raw.iloc[sk:sk + nr, year_cols[0]].values),
                                errors="coerce").fillna(0.0).values
            sub = mapping[mapping.block == block]
            for _, r in sub.iterrows():
                i = int(r["row_in_block"])
                if proc[i] != str(r["process"]).strip():
                    raise ValueError(
                        "row drift in %s::%s row %d: workbook has %r, mapping expects %r"
                        % (country, sheet, sk + i + 1, proc[i], r["process"]))
                if r["category"] not in CATEGORY_ORDER:
                    continue  # 'Feedstock' is excluded by design
                tab.loc[r["category"], SECTOR[block]] += val[i] * KTOE_TO_TWH
        out[country] = tab
    return out


def headline(tab):
    total = tab.values.sum()
    heat = total - tab.loc["Electricity Other"].sum()
    sub400 = tab.loc[["Steam (non-electric boilers)",
                      "Non-electric process heat (<100 C)",
                      "Non-electric process heat (100-400 C)"]].values.sum()
    return dict(total=total, heat=heat, sub400=sub400,
                sub400_share_total=100 * sub400 / total,
                sub400_share_heat=100 * sub400 / heat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idees", default="JRC-IDEES-2023",
                    help="unpacked JRC-IDEES-2023 folder, one sub-folder per country code")
    ap.add_argument("--out", default=None)
    ap.add_argument("--summary-only", action="store_true")
    a = ap.parse_args()

    mapping = load_mapping()
    print("mapping: %d process rows, %d categories\n"
          % (len(mapping), mapping["category"].nunique()))

    for metric, folder in (("ued", "industry_useful_energy_demand"),
                           ("fec", "industry_final_energy_consumption")):
        tabs = build(a.idees, mapping, metric)
        if a.out and not a.summary_only:
            d = os.path.join(a.out, folder)
            os.makedirs(d, exist_ok=True)
            for country, tab in tabs.items():
                tab.rename_axis("energy_demand_type").to_csv(
                    os.path.join(d, "%s_%s.csv" % (folder, country)), encoding="utf-8")
        if metric == "ued":
            eu = tabs["EU27"]
            ms = sum(t.values.sum() for c, t in tabs.items() if c != "EU27")
            h = headline(eu)
            print("EU27 useful energy demand")
            print(eu.sum(axis=1).round(2).to_string())
            print("  total %.2f TWh   (27 MS sum %.2f)" % (h["total"], ms))
            print("  process heat %.2f TWh" % h["heat"])
            print("  sub-400 C heat %.2f TWh = %.1f%% of total, %.1f%% of heat"
                  % (h["sub400"], h["sub400_share_total"], h["sub400_share_heat"]))
            print("  sector totals:")
            print(eu.sum(axis=0).sort_values(ascending=False).round(2).to_string())
        else:
            print("\nEU27 final energy consumption total %.2f TWh" % tabs["EU27"].values.sum())
    return 0


if __name__ == "__main__":
    sys.exit(main())
