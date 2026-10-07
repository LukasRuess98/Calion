# FINAL_RUN_INVALID.md

**Geprüfter Lauf:** `outputs/20260922T150335/`
**Prüfzeitpunkt:** 2026-09-22, Post-Run-Abnahme (Phase A)
**Ergebnis:** **UNGÜLTIG für Paper/submission_pack** — Finalisierung gestoppt gemäß Phase A.4.

## Präzise Begründung

`test_report.md` dieses Laufs enthält nur **T01–T12**, nicht T13. Grund:
Der Produktionslauf wurde gestartet, *bevor* der von euch geforderte
ETA_GB-Regressionstest (T13) zu `agnes_p2h.py` hinzugefügt wurde. Der bereits
laufende Python-Prozess hatte den Skriptstand zu Prozessstart bereits
kompiliert/geladen; ein nachträgliches Hinzufügen von T13 im Quellcode wirkt
sich nicht mehr auf einen schon laufenden Prozess aus (kein Hot-Reload). Ich
habe T13 im Anschluss nur gegen einen separaten `AGNES_DRY_RUN=1`-Lauf
validiert (erfolgreich, s. vorheriger Bericht), **nicht** aber den bereits
laufenden Hauptlauf neu gestartet — genau das ist hier der Fehler.

Dies ist ein reines **Reproduzierbarkeits-/Zeitpunktproblem**, kein
inhaltlicher Bug: T13 selbst wurde bereits unabhängig verifiziert (ETA_GB=0.9,
Verhältnis fuel/useful=1.1111, recon_ok=True). Der aktuelle `agnes_p2h.py`-
Quellstand enthält T13 korrekt.

## Was in diesem Lauf bereits korrekt war (zur Einordnung)

Geprüft direkt aus den Output-Artefakten dieses Laufs, alles bestanden:

| Punkt | Nachweis | Status |
|---|---|---|
| ETA_GB in Zielfunktion/KPI aktiv | Spalte `fuel_gas_mwh_hu` in `kpi_s1_s4.parquet` vorhanden | ✅ |
| Alle Kernläufe optimal | 0/96 nicht-optimale Läufe in `kpi_s1_s4.parquet` | ✅ |
| Keine NaN in `objective_eur` (optimale Läufe) | 0 NaN | ✅ |
| StromNEV-Konsistenzprüfung aktiv (kein Fallback) | T09 lief ohne Absturz, 32/64 als ambiguous geflaggt | ✅ |
| Break-even nutzt config.yaml (max_iter=25, tol_rel dokumentiert) | `breakeven.csv`: max. genutzte Iterationen=16 (≤25), Spalte `tol_rel` vorhanden | ✅ |
| T11b vergleicht BASE+ELEC über LCOH_inc | `test_report.md` T11b-Zeile zeigt `LCOH_inc_delta_pct` (chemistry 0,038 %, paper 0,112 %) | ✅ |
| V-04 (KKT-Konsistenzcheck) vorhanden | `marker_map.csv` enthält V-04 | ✅ |
| V-03/S10 vorhanden (chirurgisch gefixt, nicht gelöscht) | `marker_map.csv` enthält V-03 | ✅ |
| **T13 (ETA_GB-Regressionstest)** | **fehlt in `test_report.md`** | ❌ |

## Konsequenz (gemäß Vorgabe Phase A.4)

- Outputs aus `outputs/20260922T150335/` werden **nicht** für das Paper verwendet.
- Keine Zahlen daraus werden in DOCX oder `submission_pack/` übernommen.
- Phase B, C, D wurden **nicht** ausgeführt.
- `outputs/20260922T150335/` wurde **nicht verändert** (nur gelesen).

## Empfohlene Behebung

`agnes_p2h.py` enthält T13 bereits korrekt (verifiziert). Es ist **kein
Code-Fix nötig**, nur ein sauberer Neustart des vollständigen Laufs mit dem
aktuellen Quellstand:

```
cd docs/paper_ZWF_Agnes_Reform
python agnes_p2h.py
```

Erwartete Laufzeit gemäß letztem vollständigen Lauf: ca. 1,5–2,5 Stunden
(threads=1, MAX_WORKERS=12; S7 mit max_iter=25 und S10 Rolling Horizon sind
die zeitdominanten Abschnitte).

**Warte auf explizite Freigabe, bevor dieser Neustart ausgeführt wird** —
das ist eine erneute mehrstündige Rechenlast, die ich nicht ungefragt
auslöse.

## Weiterer offener Punkt (unabhängig vom obigen Befund)

`20260922_Bestellkapazitaet_ZWF_lkr.docx` wurde weiterhin **nicht** im
Projektordner, im übrigen Repo oder in Desktop/Downloads/Documents
gefunden. Phase C (Paper-Finalisierung) ist dadurch zusätzlich blockiert,
unabhängig vom T13-Befund.
