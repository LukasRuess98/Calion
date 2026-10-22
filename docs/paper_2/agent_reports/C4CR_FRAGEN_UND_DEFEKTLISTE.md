# §4cr-Fragen (Meldepflicht, nicht behoben) + Defektliste Nr. 14+15

## 1. Aendert §4cr (2026-10-22, AC-Block AD1/AD2/AD5) bereits berichtete Ergebnisse, oder erzwingt es Neulaeufe?

Alle unten genannten Ergebnisse sind BEREITS GESCHRIEBENE, abgeschlossene Output-Dateien (`geometry.csv`/`meta.json`/
`cost_breakdown.json`), lange bevor §4cr committet wurde (A4-Agent bestaetigte: Code bei seinem Lauf bereits auf
`ddae6db`, NACH §4cr). Ein spaeterer Code-Commit kann bereits geschriebene Dateien nicht rueckwirkend aendern — die
Frage ist daher NICHT "wurden die Zahlen veraendert" (nein, koennen sie nicht), sondern "waeren sie bei einem
NEULAUF mit der heutigen Codebasis noch dieselben".

| Hauptergebnis | Status | Begruendung |
|---|---|---|
| SB-S1 c0×1,0 (`v7_final/SB-S1-HK0`) | **unveraendert** (berichteter Wert steht fest) | Lief weit vor §4cr. Bei Neulauf HEUTE: nicht identisch ohne die 5-Var-Altmodell-Rezeptur (`CALION_TES_RHD=2.0 CALION_TES_P2E_HOURS=4 CALION_TES_POWER_MAX=0` zusaetzlich zu den bisherigen 2), da §4cr die DEFAULTS fuer `r_hd` (neu 1,5 statt 2,0) und `power_to_energy_ratio` (neu praktisch nicht bindend statt 0,25) aenderte (AD2/AD5, `docs/.../MODEL_AND_DOE_CONTROL.md:3361-3367`). Mit der vollen 5-Var-Rezeptur WUERDE der Neulauf dieselbe Geometrie reproduzieren (nicht getestet, **vermutet** nach Formel-Konsistenz). |
| SB-S2/S3 (Stage-2-Re-Solves) | **unveraendert** | Liefen 2026-10-20, vor §4cr. Gleiche Begruendung wie oben — betroffen waere nur ein KUeNFTIGER Neulauf. |
| c0-Sweep (×0,5 bis ×2,0) | **unveraendert** | c0×0,5/0,7 liefen 2026-10-20/21 (vor §4cr), ×1,0/1,3/1,5/2,0 noch frueher (v7_final/AA3-Kampagne, Anfang/Mitte Oktober). Alle vor §4cr. |
| MM-S1 | **unveraendert** | `v7_final`-Lauf, lange vor §4cr. |
| Z3/Z3b (Tarif-/Preissensitivitaeten, MONTHLY/SPREIZ/NETZ50/VERMARKT2) | **unveraendert** | Alle Laeufe aus `_z3`/`_z3b`, Datumsstempel 13.-14.10., vor §4cr. |

**Zusammenfassung:** Kein einziges der oben genannten, bereits berichteten Ergebnisse ist durch §4cr inhaltlich
veraendert — alle sind historische, abgeschlossene Artefakte von vor dem Commit. §4cr betrifft ausschliesslich
KUeNFTIGE Laeufe (z. B. die in §4cr selbst angekuendigten `ac4_mid22k`/`ac4_low9k`/E/P-Sweeps) UND die
Reproduzierbarkeits-Rezeptur (2→5 Env-Variablen fuer "Altmodell"-Verhalten, siehe A5d). Status: belegt (Zeitstempel-
Vergleich Commit vs. Lauf-Datum) + vermutet (dass die 5-Var-Rezeptur bei einem echten Neulauf exakt reproduziert —
nicht getestet).

## 2. Vorschlag: Commit/Tag fuer volle Reproduzierbarkeit

**Vorschlag (nicht ausgefuehrt, wartet auf Freigabe):** Ein Tag `paper2-v5-tranche1-repro` auf dem Commit, der
UNMITTELBAR VOR §4cr liegt (also dem letzten Commit, unter dem die 2-Var-Altmodell-Rezeptur noch ausreichte) — das
waere der Commit, den `output/_s2/sb_c0x07/paper2_runs/SB-S1-HK0/meta.json` als `git_sha` tatsaechlich nennt:
**`342e877`** (bzw. dessen unmittelbarer Nachfolger `812c460`, siehe `A2_A3_findings.md`/git-Historie). ABER: wie in
A5d dokumentiert, ist `git_sha` in `meta.json` bei Laeufen waehrend der gemeinsamen Arbeitsverzeichnis-Phase (ab
2026-10-19) NICHT zuverlaessig (zeigt nur HEAD zum Zeitpunkt des Laufstarts, nicht den tatsaechlichen, ggf.
unsauberen Working-Tree-Zustand). **Ein Tag alleine reicht daher NICHT** fuer vollstaendige Reproduzierbarkeit der
Stage-2/c0-Sweep-Laeufe — zusaetzlich waere je Lauf die VOLLE Env-Variablen-Rezeptur noetig (jetzt in
`B4_konvergenz_provenienz.csv`, Spalten `warmstart_source`/`seed_fill_zero`/`c0_scale`/`env_recipe_other`
dokumentiert, soweit aus `chain.output` rekonstruierbar). **Nicht getaggt, wie angewiesen — wartet auf Freigabe.**

## 3. Defektliste Nr. 14 und 15 (neu, nicht behoben)

### Defekt 14 — `design_helpers`/`result_collector`-Storage-Extraktion liefert fälschlich 0
- **Fundstelle:** `calion/run/result_collector.py:1296-1299` (und eine strukturell identische Kopie in
  `calion/run/design_helpers.py:37-47`, die vermutlich denselben bereits-falschen `summary`-Wert weiterreicht).
- **Ursache:** `getattr(model, "TES_cap_energy"/"TES_cap_power"/"TES_build", None)` sucht generische,
  LEGACY-Variablennamen, die im aktuellen komponentenbasierten Storage-Modell (`geometric_storage.py`, AC1/AC2) nicht
  existieren — `getattr` liefert `None`, Code faellt auf einen Default von 0 zurueck.
- **Betroffene Laeufe/Konsumenten:** Betrifft JEDEN Lauf mit `geometric_storage`-TES (also praktisch alle
  SB-Investitionslaeufe seit dem AC1/AC2-Refactor). Konsument: `summary_sections[f"storage_{name}"]` →
  `_flatten_summary` → `flat` (genauer Zieldateiname NICHT lokalisiert, siehe A5b). **NICHT betroffen:** `geometry.csv`
  (separater, korrekter Extraktionspfad ueber `design_helpers`' direkte Geometrie-Variablen) und `cost_breakdown.json`
  (separate CAPEX-Berechnung) — **die im Paper zitierten Zahlen sind nachweislich NICHT betroffen.**
- **Fixvorschlag:** `getattr`-Ziele in `result_collector.py:1296-1299` auf die echten, komponentenspezifischen
  Pyomo-Variablennamen umstellen (dynamisch ueber `meta["storage"]["name"]`, nicht hartcodiert).
- **Aufwand:** klein-mittel.
- **Berichtetes Ergebnis betroffen?** NEIN (soweit geprueft, siehe A5b).

### Defekt 15 — `meta.json["solution_count"]` unzuverlaessig
- **Fundstelle:** irgendwo in `scripts/paper_2/scenario_runner.py`s meta.json-Writer (genaue Zeile nicht
  lokalisiert — Aufwand fuer A1/A5 war bereits hoch, dies war ein Nebenfund aus A2).
- **Ursache (vermutet):** liest vermutlich ein falsches/konstantes Solver-Attribut statt des echten Gurobi-Modell-
  Attributs `SolCount` zum Zeitpunkt des Laufendes.
- **Betroffene Laeufe/Konsumenten:** Bestaetigt falsch bei `SB-S2-HK0` (Stage-2-Resolve, zeigt `1`, echtes Log zeigt
  `10`) und `SB-S3-HK0` (zeigt `1`, echtes Log zeigt `10`) — siehe `A2_A3_findings.md` A2a. In
  `B4_konvergenz_provenienz.csv` wird dies in der Spalte `solcount_note` je betroffener Zeile vermerkt; die Tabelle
  selbst verwendet den LOG-Wert (`solution_count_log`), nicht `meta.json`, als massgeblich.
- **Fixvorschlag:** Codezeile finden (`grep -rn "solution_count" scripts/paper_2/scenario_runner.py`) und gegen
  `results.solver.statistics`/Gurobi-`SolCount`-Attribut validieren.
- **Aufwand:** klein (vermutlich 1 Zeile, aber Fundstelle noch zu suchen).
- **Berichtetes Ergebnis betroffen?** NEIN direkt (der `solution_count`-Wert selbst fliesst nicht in `obj_eur`/CAPEX
  ein), ABER er ist ein wichtiges INDIREKTES Qualitaetssignal (Solution count 1 vs. 10 = Stuck-Warmstart-Indikator,
  siehe A1/A3) — ein Leser, der sich auf `meta.json` allein verlaesst, wuerde die S2/S3-Re-Solves faelschlich als
  "nie unabhaengig exploriert" einschaetzen, obwohl sie es waren. Das ist eine VERTRAUENSWUeRDIGKEITS-, nicht eine
  Zahlen-Verfaelschung.
