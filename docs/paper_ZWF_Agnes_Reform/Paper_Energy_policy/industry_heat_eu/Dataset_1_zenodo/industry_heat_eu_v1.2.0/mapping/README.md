# IndustryHeat-EU — process-to-category mapping

`process_category_mapping.csv` assigns every JRC-IDEES process row to one of the seven
IndustryHeat-EU demand categories, and `build_industryheat_eu.py` rebuilds the whole
dataset from a clean download of JRC-IDEES-2023 plus that one file.

## Files

| File | Contents |
|---|---|
| `process_category_mapping.csv` | One row per mapped JRC-IDEES process: `sheet_stem, block, row_in_block, excel_row, process, category`. 313 rows. |
| `build_industryheat_eu.py` | Rebuilds `industry_useful_energy_demand/` and `industry_final_energy_consumption/`. |

## Rebuilding

```bash
# point --idees at an unpacked JRC-IDEES-2023 folder (one sub-folder per country code)
python build_industryheat_eu.py --idees /path/to/JRC-IDEES-2023 --out /path/to/output

# headline numbers only, nothing written
python build_industryheat_eu.py --idees /path/to/JRC-IDEES-2023 --summary-only
```

The build raises rather than warns if a workbook row no longer carries the process name the
mapping expects, so a future JRC-IDEES edition that inserts or removes a row fails loudly
instead of silently dropping demand.

## Notes on the mapping

Only the rows that carry a category are listed. The per-carrier sub-rows underneath a mapped
parent are absent from the file and are therefore not counted, which is what keeps each
mapped block equal to its JRC-IDEES sub-sector total — no double counting, no omission.

Rows carrying the category `Feedstock` are read but excluded from the output, because
feedstock use of energy carriers cannot be substituted by a heat supply technology.

The conventions the mapping implements follow the classification of:

Madeddu, S. *et al.* (2020) "The CO2 reduction potential for the European industry via direct
electrification of heat supply (power-to-heat)", *Environ. Res. Lett.* **15** 124004,
doi:10.1088/1748-9326/abbd02.

They are set out in full in Appendix A of the accompanying paper.
