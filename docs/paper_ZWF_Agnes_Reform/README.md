# agnes_p2h — README

Notebook `agnes_p2h.ipynb` (bzw. Quelle `agnes_p2h.py`) rechnet die
Szenariomatrix für den ZWF-Beitrag "Bestellkapazität statt Jahreshöchstlast"
auf Basis von `config.yaml` und den vier Standortordnern.

**Ausführen:** Kernel im Verzeichnis `docs/paper_ZWF_Agnes_Reform/` starten,
Run All. Die Solver-Kampagne (S1-S10, ~350+ LP-Solves) verwendet bis zu
12 parallele Worker; jeder HiGHS-Solve ist auf einen Solver-Thread
begrenzt. Das vermeidet CPU-Überzeichnung und verbessert die
Reproduzierbarkeit bei weiterhin effizienter Nutzung der verfügbaren
Rechenressourcen. Gemessene Gesamtlaufzeit auf der Referenzhardware (66
logische Kerne): ca. 1,5-2,5 Stunden (dominiert von S10 Rolling Horizon und
S7 Break-even mit 25 Bisektionsschritten je Kette).

**Debug/Schnelltest:** Umgebungsvariable `AGNES_DRY_RUN=1` setzen. Der Dry
Run reduziert Standort- und Sweep-Matrix auf einen Standort (Pipeline-Check
in wenigen Minuten); er ersetzt keine vollständige Ergebnisrechnung.

**Ausgabeordner:** `outputs/<run_ts>/` mit `figures/`, `tables/`,
`fixtures/`, allen KPI-Parquets/CSVs, `paper_values.json`,
`draft_filled.md`, `open_issues.md`, `qa_report.md`.

**Wichtigste Abweichungen vom ursprünglichen Auftrag (Dokument 2):** 1h statt
15min als Primärauflösung (Solver-Zeitbudget), ein Prozesswärme-Band statt
LT/HT/VHT (Datenrealität), S6/S7/S9/S11 angepasst bzw. reduziert - Details
in `outputs/<run_ts>/open_issues.md`.

Solver: HiGHS via `linopy` (Dual-Simplex, 1h-Auflösung ~35-110s je Lauf,
Parallelisierung nutzt 12 von 66 Kernen über
Threads, da highspy den GIL beim Lösen freigibt).
