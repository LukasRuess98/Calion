LOCAL ONLY - contains real names. Never commit any of these files.

Unpack into the repository root (the paths are gitignored via data/raw_dhn_a/):
  data/raw_dhn_a/anonymisierung/zuordnung_verbraucher.csv   consumer names <-> V01..V24 (name scan)
  data/raw_dhn_a/anonymisierung/zuordnung_signale.csv       signal names <-> anonymised columns
  data/raw_dhn_a/anonymisierung/klar_phrasen.json           list of real-name phrases for the pre-commit scan
  data/raw_dhn_a/anonymisierung/klar_tokens.json            additional tokens
  data/raw_dhn_a/anonymisierung/*.py                        anonymisation scripts (regenerate data/dhn_a from raw data)

Put your own files next to them (also gitignored):
  data/raw_dhn_a/upload/B_Plaene/   the three operator plan PDFs (sheet 3 of plan 640, plans 650 and 660)
  data/raw_dhn_a/upload/A_Daten/    raw hourly measurements (parquet) and load profiles 2020-2022 (xlsx), optional
  data/local/                       partner A waste-heat file; the energy-model input of the real network if you move it

prompt_local_agent_central_tes.md = the prompt for the coding agent (paste it, do not commit it).
