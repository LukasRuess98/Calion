<!-- Entwurf fuer Abschnitte nach §4ck, NICHT in MODEL_AND_DOE_CONTROL.md eingefuegt. Nur Fakten aus
B4_konvergenz_provenienz.csv und den unten zitierten Primaerquellen, keine Interpretation. Stand 2026-10-22. -->

# E1 — Faktensammlung aller Laeufe 2026-10-06 bis 2026-10-22

Quelle: `tables/B4_konvergenz_provenienz.csv` (36 Laeufe), ergaenzt durch direkte Zitate aus
`docs/paper_2/submission_pack/00_statements/MODEL_AND_DOE_CONTROL.md` §4ck-§4cr.

## v7_final (Phase 1, ab 2026-10-02/04)
8 Laeufe: `MM-S0-HK0-PIN0`, `MM-S1-HK0`, `MM-S2-HK0`, `MM-S3-HK0`, `SB-S0-HK0-PIN0`, `SB-S1-HK0`, `SB-S2-HK0`,
`SB-S3-HK0`. Alle Status `optimal` (meta.json), Gaps 0,128%-0,1465%. Kein per-Lauf-Logfile isoliert auffindbar (nur
das gemeinsame, mehrfach-kampagnen-kontaminierte `output/logs/gurobi_<id>.log` — siehe `C4CR_FRAGEN_...md`); fuer
diese 8 Laeufe ist `meta.json` die massgebliche, gegen die Referenztabelle des Auftrags verifizierte Quelle.

## AA3 — SB-S1 c0-Sweep (§4ck, 2026-10-12 abgeschlossen; Vervollstaendigung 2026-10-20/21)
7 Punkte: PIN0 (geteilt mit v7_final), ×0,5/0,7/1,0/1,3/1,5/2,0.
- ×1,0: `v7_final/SB-S1-HK0` (siehe oben).
- ×1,3/×1,5: `output/_parallel_aa3/c0x1.3`/`c0x1.5`, Status `maxTimeLimit`, Gap 0,3372%/0,5692%,
  `Solution count` im Log **1-2** nach MEHRFACHEM Neustart (3 "Loaded user MIP start"-Zeilen mit identischem
  Startwert je Log) — §4ck: "Offener Belastbarkeits-Vorbehalt: c0×1,3/1,5 vermutlich NICHT neu-optimierte
  TES-Groesse" (Zitat, 2026-10-12).
- ×2,0: `output/_parallel_aa3/c0x2.0`, Status `maxTimeLimit`, Gap 0,4355%, `Solution count 10` (einzelner,
  durchgehender Lauf, keine Neustarts im Log).
- ×0,5/×0,7: urspruenglich informell (OOM-Crash bzw. kontrolliert gekillt, §4ck), am 2026-10-20/21 formal
  nachgeloest: `output/_s2/sb_c0x05` (obj_eur=22.981.415,31, Gap 0,2277%, `Solution count 1`, 11.134 Knoten
  exploriert), `output/_s2/sb_c0x07` (obj_eur=23.057.656,99, Gap 0,1529%, `Solution count 1`, 12.669 Knoten).

## Z3 — Tarif-/Preissensitivitaeten (§4cl, 2026-10-13; §4co, 2026-10-14)
Mechanismen MONTHLY (Monatsleistungspreis) und NETZ50 je fuer SB und MM, mit zugehoerigem PIN0:
`sb_free_monthly`/`sb_pin0_monthly`, `mm_free_monthly`/`mm_pin0_monthly`, `sb_free_netz50`/`sb_pin0_netz50`,
`mm_free_netz50`/`mm_pin0_netz50`. `SB-S1-HK0-MONTHLY`: Status `maxTimeLimit`, Gap 0,1828%, `Solution count 1`
(Start=Endwert 2,3172e+07 — identisch zum MIP-Start), 12 zusaetzliche Variablen + 8.760 zusaetzliche Constraints
gegenueber `SB-S1-HK0` (Build-only-Diff, belegt die strukturelle Existenz der Monats-Peak-Tracking-Logik).

## Z3b — Preisspreizung + Direktvermarktungsabschlag (§4co, 2026-10-14, 12 Laeufe)
SPREIZ15/SPREIZ20/VERMARKT2 je fuer SB und MM, mit zugehoerigem PIN0: 12 Laeufe insgesamt
(`sb_free_spreiz15/20`, `sb_pin0_spreiz15/20`, `mm_free_spreiz15/20`, `mm_pin0_spreiz15/20`,
`sb_free_vermarkt2`, `sb_pin0_vermarkt2`, `mm_free_vermarkt2`, `mm_pin0_vermarkt2`). `SB-S1-HK0-SPREIZ20` baut
TES mit `E_TES_max_MWh=585,0` (V=40.575,2 m³, cap_power=146,25 MW) — groesser als die c0×1,0-Referenzgeometrie
(438 MWh).

## Z4 — unabhaengige Validierung (§4cm, 2026-10-13)
Stale Validierungsformel gefunden+gefixt (Zitat §4cm). Re-Extraktion fuer SB-S2/S3 in
`docs/paper_2/agent_reports/reextractions/validation_SB-S2-S3_Z4fix.json` (aus fruehere Session, nicht Teil dieser
Lieferung) zeigt korrigierten Bilanzschluss 0,269% (vorher 3,305%, fail).

## Z5 — konsolidierte Tabelle (§4cn, 2026-10-13)
Groessen-Preis-Elastizitaet NUR fuer c0×1,0 und c0×2,0 berechnet, ×1,3/×1,5 explizit ausgeschlossen (Zitat §4cn,
"bewusst ausgeschlossen, §4ck-Vorbehalt").

## Stage 2 — koordinierte Re-Solves (diese Lieferung, 2026-10-20/22)
- `SB-S2-HK0` (Re-Solve, `output/_s2/sb_s2_resolve2`): obj_eur=23.318.968,91, Gap 0,1867%, `Solution count 10`
  (Log) — ein vorheriger Versuch `output/_s2/sb_s2_resolve` ist in der Tabelle als FAILED markiert (obj_eur=
  45.916.707,27, Gap 49,31%, nicht verwendet).
- `SB-S3-HK0` (Re-Solve, `output/_s2/sb_s3_resolve`): obj_eur=23.316.918,73, Gap 0,1772%, `Solution count 10`.
- Beide Re-Solves nutzten Warmstart aus einem PIN0-Dump (`CALION_WARMSTART_DUMP`) mit `CALION_SEED_FILL_ZERO=1`
  (belegt aus `chain.output`-Zeilen "inheritance fill-zero: ... 0 size one-hot(s) -> zero rung").

## AC-Block (§4cq 2026-10-19, §4cr 2026-10-22) — Nachbarkampagne, nicht Teil dieser Lieferung
§4cq: TES-Leistung bepreist, Geometrie konsistent gemacht. §4cr (HEUTE): Leistungskosten-Geltungsbereich geprueft,
280.274 €/MW als Primaerquelle zurueckgezogen (jetzt Stresstest-Obergrenze), Ersatzquelle-Spanne 8.800/22.100/76.300
€/MW_th aus DEA/Energinet Kap. 203. "Altmodell-Reproduktion" braucht seitdem 5 statt 2 Env-Variablen
(Zitat §4cr: "Fuer die Altmodell-Laeufe ... jetzt fuenf Env noetig").

## Neue Logging-Defekte (diese Lieferung)
Defekt 14 (TES-Storage-Extraktion liefert 0 trotz echtem Build) und Defekt 15 (`meta.json.solution_count`
unzuverlaessig) — siehe `C4CR_FRAGEN_UND_DEFEKTLISTE.md` fuer vollstaendige Befunde, betroffene Laeufe,
Fixvorschlag und Aufwand.
