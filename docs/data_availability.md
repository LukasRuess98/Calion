# Data availability and anonymisation

## Synthetic example dataset

* **Location:** `data/synthetic_site/`
* **Files:** `synthetic_load_profile.csv`
* **Content:** 24 hourly timestamps for 2023-01-01 with day-ahead power prices, aggregated heat demand, CO₂ intensity, and a single waste-heat recovery source (thermal potential and source temperature).

The dataset is generated from smooth sinusoidal patterns and does **not** contain customer or operational data. Values are scaled to sit comfortably within the default EnerGIS component capacities so that PF→RH runs succeed out-of-the-box. The data are stored as CSV (no binary Excel artefacts) so diffs remain text-only.

## Anonymisation approach

The numbers are procedurally generated with deterministic formulae (sine/cosine curves plus offsets). No measurements or confidential parameters from real sites were used. Column names mirror the defaults in `configs/sites/*.site.yaml` so the files can be swapped in without additional cleaning.

## Licence

The synthetic dataset is released under the same permissive terms as the repository (MIT). You may copy, adapt, and redistribute the files, but attribution to this repository is appreciated to help others discover the source of the templates.
