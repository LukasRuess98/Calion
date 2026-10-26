# MODEL_V9 — Env-Schalter-Rezeptur (Branch `p2_v9_consolidation`)

Stand 2026-10-23. Neues Modell (v9) ist jetzt der STANDARD (keine Env-Variable nötig, um es zu bekommen).
Jede Env-Variable unten schaltet ein STÜCK des ALTEN (v7/v8) Verhaltens zurück, zum Vergleich/zur Reproduktion.

## E1 — Temperaturbasis
- `CALION_LEGACY_TEMPERATURE_FRAME=1` — überspringt die komplette Injektion von `supply_temp_dict`/
  `return_temp_dict`. Netzphysik nutzt wieder `network.temperature_frame` (SB) bzw. die k-lose
  `calculate_supply_temperature_series`-Formel (MM), getrennt von COP/Maske/ΔT.

## E2 — Speicher-ΔT
- `CALION_TES_DELTA_T_MODE=legacy_floor` — `delta_T_scenario_k` wieder `T_VL_min_effective − return_temp_c`
  (15K-Boden), keine Neuskalierung der Hydraulikkappe.
- `CALION_TES_DELTA_T_MODE=store_max` (Default, muss nicht gesetzt werden) — `t_store_max_c − T_RL,ref`.
- `CALION_TES_DELTA_T_P90=1` — `T_RL,ref` = P90 statt Jahresmittel der Rücklaufreihe (konservativere, kleinere
  ΔT-Sensitivität).

## E3 — Entlademodus
- `CALION_TES_DISCHARGE_MODE=mask` — alte binäre Maske (E3a-Sensitivität), keine Nachheiz-Constraint.
- `CALION_TES_DISCHARGE_MODE=preheat` (Default, muss nicht gesetzt werden) — Vorwärmbetrieb mit
  Nachheiz-Constraint gegen co-lokalisierte Erzeuger.

## E5 — Topologie
- `CALION_LEGACY_TOPOLOGY=1` — `hkw_to_man` wieder einseitig, `ek_sb` wird wieder (zusammen mit `hp_sb`) nach
  j_man verschoben.

## E6 — Kostenmodell
- Kein Schalter nötig für "neu" (bereits Standard in `storage_geometry.yaml`).
- Altmodell-Reproduktion (wie in v7 A5d dokumentiert, jetzt 5 Variablen): `CALION_TES_POWER_CAPEX=0
  CALION_TES_HMAX=0 CALION_TES_RHD=2.0 CALION_TES_P2E_HOURS=4 CALION_TES_POWER_MAX=0`.

## Vollständiges Altmodell (alle sechs E-Punkte zurück)
```
CALION_LEGACY_TEMPERATURE_FRAME=1
CALION_TES_DELTA_T_MODE=legacy_floor
CALION_TES_DISCHARGE_MODE=mask
CALION_LEGACY_TOPOLOGY=1
CALION_TES_POWER_CAPEX=0 CALION_TES_HMAX=0 CALION_TES_RHD=2.0 CALION_TES_P2E_HOURS=4 CALION_TES_POWER_MAX=0
```

## Geänderte/neue Dateien (Commits)
- `55d070f` B1=E1 — `scripts/paper_2/scenario_runner.py`, `configs/paper_2/calibration/sb_hkw_temp_vl_rl_2025_hourly.csv` (neu)
- `9ed2a00` B2=E2 (Teil 1, mit Bugfix-Nachtrag) — `scripts/paper_2/scenario_runner.py`
- `a9ea297` B3=E3b — `scripts/paper_2/scenario_runner.py`, `calion/models/blocks/geometric_storage.py`, `calion/models/component_assembler.py`
- `ac4c0a2` B5=E5 — `scripts/paper_2/scenario_runner.py`
- `7cb1cd6` — E2-Reihenfolge-Fix (t_store_max_c war noch nicht injiziert) + E3b-Fix
  (`_component_fs`-Registrierung fehlte für `thermal_generator`-Assets wie `hkw`, dadurch wurde `hkw` fälschlich
  aus den Nachheiz-Erzeugern ausgeschlossen)

## Bekannte Einschränkungen (nicht in dieser Runde behoben)
- HK1/HK2 sind noch NICHT auf die neue Temperaturbasis umgestellt (B1b, wartet auf Lukas' Rückmeldung zu A3).
- MM-HK0 nutzt weiterhin die alte Formel (A2: Stationsmessdaten unbrauchbar ohne Bereinigung).
- `_q_th_useful` (Dump-aware) wird für die Nachheiz-Constraint NICHT verwendet, nur das rohe `Q_th_out` — nur
  relevant unter `CALION_DUMP_MODE=chp_only` (nicht der Standard).
