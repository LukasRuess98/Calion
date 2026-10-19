<!--
HINWEIS (D1, Auftrag v4): dieser Nachtrag wurde NICHT neu verfasst, sondern unverändert aus dem bereits
existierenden Abschnitt §4ck-§4cp von MODEL_AND_DOE_CONTROL.md auf dem Branch `Loc_TES_Study_P2` extrahiert
(`git show Loc_TES_Study_P2:docs/paper_2/submission_pack/00_statements/MODEL_AND_DOE_CONTROL.md`), wo er bereits
während der referenzierten Arbeitssession geschrieben und laufend dokumentiert wurde. Siehe den Branch-Hinweis am
Anfang von REPORT_Klaerung_2026-10-19.md. NICHT in das Haupt-Dokument eingefügt, wie vom Auftrag gefordert.
-->

## §4ck — 2026-10-12: AA3 — SB-S1 c0-Sweep abgeschlossen (mit zwei OOM-Vorfällen, einem Protokoll-Selbstfehler, und einem offenen Belastbarkeits-Vorbehalt)

**Zwei Windows-Server-Restarts (06.10.) unterbrachen Lauf 3 (c0×0,5) zweimal während des Solves** — kein Mid-Solve-Checkpoint existierte zu diesem Zeitpunkt, beide Male vollständiger Neustart nötig. **Fix:** Gurobis native `SolFiles`-Option in `scripts/paper_2/scenario_runner.py` ergänzt (schreibt nach jedem verbesserten Incumbent einen `.sol`-Snapshot, env-gated via `CALION_NO_SOLFILES`) — ab diesem Zeitpunkt für alle Läufe aktiv.

**Nach dem 2. Restart: Parallelisierung der verbleibenden Läufe (c0×1,3/1,5, dann 2,0) statt sequenziell**, je mit isoliertem `CALION_OUT_BASE`/Log-Pfad (die ursprüngliche Kette teilte sich einen nicht hash-disambiguierten `outdir` je `scen_id` — parallele Läufe hätten sich gegenseitig überschrieben). **Eigener Fehler dabei:** der erste Parallel-Launch übernahm NICHT die Matched-Effort-Overrides (MIPGap/TimeLimit/MIPFocus) der Kette, lief unter Config-Standard (MIPGap=0,5%) und terminierte c0×1,3 fälschlich "optimal" bei 0,47% Gap statt 0,15%. Sofort erkannt (aus dem gedruckten Ergebnis-Dict), Export als `..._INVALID_WRONG_MIPGAP_0.47pct_REDO` markiert, Skript korrigiert, beide Läufe neu gestartet.

**Dann: echter OOM-Crash aller drei gleichzeitig laufenden Jobs** (c0×0,5/1,3/1,5) nach 40-42h — RAM-Wachstum während der Solve-Phase (nicht Build-Phase) war nicht durch die ursprüngliche Beobachtung vorhersehbar (Build-Phase-RAM ~14GB, Solve-Phase-RAM bis 104GB pro Job, kein `NodefileStart` gesetzt). Nutzer-Entscheidung (gefragt, nicht eigenmächtig): c0×1,3/1,5 NICHT aus dem rohen Gurobi-`.sol`-Checkpoint fortsetzen (hätte einen neuen, ungetesteten Loader gebraucht), sondern sauber neu ab dem bewährten `v7_final`-Warmstart — dieses Mal mit `NodefileStart=16`/`NodefileDir` (freie Disk: 745GB, die alte Disk-voll-Beschränkung galt nicht mehr). c0×0,5s Fortsetzung (`c0x0.7`, Teil der automatisch weiterlaufenden Original-Kette) lief weiter OHNE den Fix (Prozess bereits vor dem Fix gestartet) und erreichte ebenfalls ~104GB RAM bei stabilem 0,15%-Gap-Plateau seit 17,5h — auf Nutzeranweisung kontrolliert beendet (Graceful-Interrupt via Windows-Konsolen-API fehlgeschlagen, da der `disown`-Prozess keine eigene Konsole hatte; harter Kill). **c0×0,5 und c0×0,7 haben daher KEINE formale Extraktion** (kein meta.json/cost_breakdown/export_dir), nur die letzte rohe Gurobi-Log-Zeile vor Crash/Kill — auf Nutzeranweisung als für den Zweck ausreichend akzeptiert ("wenn wir genug für das Paper haben, ist das akzeptabel").

### Finale Sweep-Tabelle (alle 7 Punkte)

| c0-Faktor | spez. Kosten* | obj_eur (TAC) | Gap | Status |
|---|---|---|---|---|
| PIN0 (geteilt, §4ce) | — | 23.370.804,48 | 0,1436% | optimal, formal |
| ×0,5 | n/a (kein Export) | ≈22.981.000 | ≈0,23% | **informell** (OOM-Crash) |
| ×0,7 | n/a (kein Export) | ≈23.058.000 | ≈0,156% | **informell** (kontrolliert gekillt) |
| ×1,0 | 179 €/m³ | 23.172.019,51 | 0,1365% | optimal, formal |
| ×1,3 | *(Vorbehalt, s.u.)* | 23.286.382,04 | 0,3372% | formal, aber `Solution count 1` |
| ×1,5 | *(Vorbehalt, s.u.)* | 23.362.623,72 | 0,5692% | formal, aber `Solution count 1` |
| ×2,0 | 752 €/m³ | 23.369.171,04 | 0,4355% | optimal** formal, `Solution count 10` |

\* nach degressivem Kostenmodell (`c0_eur=2,5M`, `v0_m3=10.000`, `exponent_b=0,70`): spez._Kosten(V,mult) = mult·250·(V/v0)^(b−1).
\*\* `maxTimeLimit` erreicht, nicht `optimal`-Status, aber mit echter Lösungsvielfalt.

### Offener Belastbarkeits-Vorbehalt: c0×1,3/1,5 vermutlich NICHT neu-optimierte TES-Größe

Gebaute TES-Größe bei c0×1,0/1,3/1,5 ist BIT-IDENTISCH (30.379,4 m³), UND beide 1,3er/1,5er-Läufe zeigen `Solution count 1` im Gurobi-Log (also: über die vollen 48h wurde NIE eine gegenüber dem Warmstart verbesserte Lösung gefunden — die diskrete Größenentscheidung blieb am Warmstart "kleben"). Bei c0×2,0 (`Solution count 10`, Größe fällt auf 2.566,3 m³) fand dagegen nachweislich echte Exploration statt. **Folge:** die obj_eur-Werte bei ×1,3/×1,5 sind eine valide OBERE Schranke ("Kosten bei Beibehaltung der ×1,0-Größe zum höheren Preis"), aber nicht zwingend das global optimale Re-Design. Auf Nutzeranweisung NICHT neu gerechnet (Zeitdruck Richtung Manuskript) — als dokumentierte Einschränkung festgehalten, nicht stillschweigend als "final" verwendet.

### Wert-Intervalle (Y1-Methodik) für die belastbaren Punkte

- **×1,0 (Basisfall, 179 €/m³):** [165.215; 230.414] EUR/a — strikt positiv (siehe §4cj).
- **×2,0 (752 €/m³, zwischen Hamburg 453 und Perlen 978 €/m³ Referenzband):** [max(0, 23.337.235−23.369.171); 23.370.804−23.267.398] = **[0; 103.407] EUR/a** — Null nicht ausgeschlossen. Das ist die gesuchte Eintrittsschwellen-Zone, auch wenn nicht punktgenau lokalisiert (×1,3/×1,5 dazwischen mit Vorbehalt).

---

## §4cl — 2026-10-13: Z3 — Tarif-/Preissensitivitäten auf SB-S1/MM-S1 (2 von 4 Mechanismen) abgeschlossen

**Vorab geprüft:** von den vier angeordneten Sensitivitäten (Strompreis-Amplitude, Netzentgelt, Direktvermarktung, Monatsmaxima) existieren nur zwei als Konfigurations-Hebel ohne neuen Code — "Netzentgelt" (`grid.gridcost_eur_mwh` + `grid.demand_charge_eur_per_mw_y`, beide Komponenten halbiert) und "Monatsmaxima" (bereits validierter Y3-Mechanismus, `demand_charge_mode: monthly`). **"Preisspreizung" und "Direktvermarktungsabschlag" existieren NICHT als Mechanismus** — Kauf und Verkauf nutzen dieselbe rohe `strompreis_EUR_MWh`-Spalte ohne Amplituden-Skalierung oder KWK-Vermarktungsabschlag. Nicht implementiert, dem Nutzer vor dem Bau gemeldet statt eigenmächtig entworfen — Rückmeldung ausstehend.

**8 neue Szenarien** (`configs/paper_2/scenarios.yaml`): `{SB,MM}-S1-HK0{,-PIN0}-{NETZ50,MONTHLY}`. Je eine EIGENE PIN0-Lösung pro Sensitivität (§4ce-Vorbehalt: Preis-/Tarifänderungen verändern PIN0s eigene Dispatch-Kosten, anders als der TES-Kostenanker). Alle unter Z-Standardprotokoll (MM TimeLimit=14.400s/SB=28.800s, MIPGap-Ziel 0,15%, MIPFocus=3), mit `NodefileStart`-Schutz, parallel gelaufen (4 SB× 12 Threads + 4 MM×4 Threads = 64/66 Kerne).

### Ergebnistabelle (7 von 8 `optimal`, 1 `maxTimeLimit` bei 0,18%)

| Lauf | obj_eur | Gap | Status |
|---|---|---|---|
| SB PIN0, Netz −50% | 23.344.775,34 | 0,1234% | optimal |
| SB frei, Netz −50% | 23.145.802,72 | 0,1096% | optimal |
| SB PIN0, Monatsmax. | 23.348.317,31 | 0,0350% | optimal |
| SB frei, Monatsmax. | 23.172.019,51 | 0,1828% | maxTimeLimit |
| MM PIN0, Netz −50% | 417.455,08 | 0,1461% | optimal |
| MM frei, Netz −50% | 415.157,63 | 0,1456% | optimal |
| MM PIN0, Monatsmax. | 417.514,36 | 0,0346% | optimal |
| MM frei, Monatsmax. | 415.651,27 | 0,1397% | optimal |

### Wert-Intervalle (Y1-Methodik)

| Netz | Sensitivität | Intervall [EUR/a] | vs. Basisfall [165.215; 230.414] (SB) |
|---|---|---|---|
| SB | Netzentgelt −50% | **[170.167; 224.352]** | praktisch deckungsgleich |
| SB | Monatsmaxima | **[168.120; 218.670]** | praktisch deckungsgleich |
| MM | Netzentgelt −50% | [1.688; 2.902] | winzig, bestätigt §4cf/§4ch (MM-Signal im Rauschen) |
| MM | Monatsmaxima | [1.719; 2.444] | winzig, bestätigt §4cf/§4ch |

**Kernbefund: der SB-TES-Wert ist robust gegen beide getesteten Tarifänderungen** — Intervall bleibt in derselben Größenordnung wie der Basisfall, keine der beiden Sensitivitäten verändert die Schlussfolgerung. MM bleibt durchgängig marginal.

**Nebenbefund (nicht weiter verfolgt, nur notiert):** bei SB ist `obj_eur` für `S1-HK0-MONTHLY` (frei) UND `S1-HK0` (frei, Jahresabrechnung) auf 7 signifikante Stellen IDENTISCH (23.172.019,51 EUR beide) — bei freier Investition macht die Abrechnungsart keinen Unterschied, bei PIN0 (Bestand) spart Monatsabrechnung dagegen real 22.487 EUR/a gegenüber Jahresabrechnung. Interpretation: Investitionsfreiheit glättet die Lastspitze bereits so gut, dass die Abrechnungsart irrelevant wird — nur bei festgelegtem Bestand hilft die feinere Abrechnung noch. Für die Diskussion interessant, nicht weiter verifiziert.

---

## §4cm — 2026-10-13: Z4 — unabhängige Validierung durchgeführt: STALE Validierungs-Formel gefunden+gefixt, Modellbilanz selbst schließt gut

**Ausgangsbefund:** jede `validation.json` im aktuellen Lauf-Set (AA3+Z3, 15 geprüfte Läufe) meldet `closure_pass: false` bei 3,2-3,3 % (SB) bzw. 25,6 % (MM) Schließungsfehler — scheinbar ein ernster, durchgängiger Bilanzdefekt, der die gesamte bisherige Kampagne entwerten würde.

**Ursache gefunden (Code-Vergleich, nicht nur Zahlen-Vergleich):** die Schließungsformel in `scripts/paper/extract_artefacts.py`/`tools/validation_stadtbach.py` (`closure_error_pct = |generation+net_discharge−demand|/demand`) geht von einer "MW-verlustfreien" Bilanz aus (Kommentar: "pipe thermal losses are a separate temperature-field DIAGNOSTIC — NOT subtracted here") — das war die Begründung für eine FRÜHERE Korrektur (Loss-Subtraktion entfernt, da sie damals jeden sauberen Lauf fälschlich als `HIGH_IMBALANCE` meldete). **Direkter Abgleich mit der ECHTEN, aktuell geltenden Constraint** (`calion/models/constraint_builder.py`, Zeile ~594): `supply == demand + charge + network_loss + return_loss + supply_loss` — die Pipe-Verluste SIND seit den Fixes vom 2026-09-03 (Return-Loss) und 2026-09-21 (Supply-Loss, "defect 3") Teil der echten MW-Bilanz. Die Validierungs-Formel wurde bei diesen beiden Fixes nie nachgezogen → meldet seitdem systematisch einen Schließungsfehler ≈ der Verlustquote (SB-Netzverlust ≈3,0 % des Bedarfs, MM ≈27,5 %), nicht einen echten Modelldefekt.

**Fix:** `closure_error_pct = |generation+net_discharge−curtailment−demand−losses|/demand` in beiden Skripten, mit Code-Kommentar auf die exakte Zeile in `constraint_builder.py` verweisend (keine Vermutung, direkt verifiziert). 15 bestehende `validation.json` (AA3- und Z3-Kernergebnisse) rückwirkend korrigiert (alter Wert bleibt als `closure_fix_note` nachvollziehbar erhalten, nichts stillschweigend überschrieben).

**Ergebnis nach Fix — Modellbilanz schließt durchgängig innerhalb des 2-%-Gates:**

| Netz | alt (fehlerhafte Formel) | neu (korrekt, inkl. Verluste) |
|---|---|---|
| SB (alle 11 geprüften Läufe: PIN0, c0×1,0/1,3/1,5/2,0, 4× Z3) | 3,24-3,28 %, `FAIL` | **0,20-0,24 %, `PASS`** |
| MM (alle 4 geprüften Läufe: PIN0, c0×1,0, 2× Z3) | 25,57 %, `FAIL` | **1,96 %, `PASS`** |

**Einordnung:** Z4 ist damit erfüllt — die Modellbilanz selbst ist gesund (SB sehr eng, MM knapp aber klar unter dem Gate), der vorherige "Validierungsfehler" war ein Werkzeugfehler, kein Modellfehler. Dies ist eine ECHTE, gegenüber dem rohen Code verifizierte Korrektur (nicht nur Zahlenvergleich) und sollte bei jeder künftigen Neuberechnung der T5-äquivalenten Tabelle berücksichtigt werden — die alten T5-Zeilen (§4t, vor diesem Fix) sind davon ebenfalls betroffen und bei Bedarf neu zu ziehen, nicht übernommen in dieser Prüfung (Zeitbudget, nur das aktuelle AA3/Z3-Kernset wurde korrigiert).

---

## §4cn — 2026-10-13: Z5 — konsolidierte Ergebnistabelle, Größen-Elastizität, Realprojekt-Bandvergleich

**Tabelle** (`docs/paper_2/submission_pack/02_tables/tab_Z5_sb_mm_s1_sweep_and_sensitivities.csv`, 15 Zeilen): ein Zeile je Lauf mit Config-Hash (`export_dir`-Hash aus `run_export.json`, echt und nachprüfbar, kein erfundener Schlüssel), obj_eur, Gap, Status, gebautes `V_TES_m3`, spez. Kosten €/m³ (wo berechenbar) und Y1-Wert-Intervall gegen die jeweils richtige PIN0-Referenz (geteilte PIN0 für den c0-Sweep, eigene frische PIN0 je Z3-Sensitivität). Alle Zahlen aus den bereits abgeschlossenen AA3/Z3-Läufen, keine neuen Solves.

### Größen-Preis-Elastizität (nur robuste Punkte: c0×1,0 und c0×2,0 — ×1,3/×1,5 bewusst ausgeschlossen, §4ck-Vorbehalt)

Log-log-Elastizität zwischen den beiden einzigen Punkten mit nachgewiesener echter Größen-Exploration:
**dV/dP = −1,723** (179 EUR/m³ → 30.379,4 m³; 751,9 EUR/m³ → 2.566,3 m³). Eine 1-%-Erhöhung des effektiven TES-Preises senkt die optimale Baugröße in diesem Bereich um ≈1,72 % — überproportional elastisch (|Elastizität| > 1), ein genuiner, auf zwei echten Re-Solves beruhender Befund.

### Positionierung des Realprojekt-Kostenbands

| Referenzprojekt | EUR/m³ | Lage relativ zu den Modellpunkten |
|---|---|---|
| Friedrichshafen | 240 | zwischen ×1,0 (179) und ×2,0 (752) |
| Haltikon | 244 | zwischen ×1,0 und ×2,0 |
| Munich | 337 | zwischen ×1,0 und ×2,0 |
| Hamburg | 453 | zwischen ×1,0 und ×2,0 |
| Perlen | 978 | oberhalb ×2,0 |
| Neuköln (Ausreißer) | 2.022 | oberhalb ×2,0 |

**Wichtige Einordnung für die Diskussion:** 4 von 6 realen Referenzprojekten (240-453 EUR/m³) liegen NICHT bei den beiden robusten Modellpunkten, sondern genau im Bereich, den nur ×1,3 (233 EUR/m³) und ×1,5 (269 EUR/m³) abdecken — exakt die zwei Punkte mit dem §4ck-Vorbehalt (Größe vermutlich am Warmstart kleben geblieben). Die ehrliche Aussage: **bei 179 EUR/m³ (unterhalb aller realen Referenzen) ist der TES-Nutzen klar positiv [165.215; 230.414 EUR/a]; bei 752 EUR/m³ (zwischen Hamburg und Perlen) ist der Nutzen nicht mehr von Null zu unterscheiden [0; 103.407 EUR/a]; für den DAZWISCHENLIEGENDEN, für reale Projekte repräsentativsten Bereich (240-453 EUR/m³) liegt nur eine mit Vorbehalt belastete Schätzung vor** [50.853-162.944 EUR/a bei ×1,3; 0-141.167 EUR/a bei ×1,5]. Für eine belastbare Eintrittsschwellen-Aussage im publizierten Bereich wäre ein echter Neu-Solve von ×1,3/×1,5 (anderer Warmstart, um die Stuck-Hypothese zu testen) wünschenswert — auf Autorenweisung aus Zeitgründen zurückgestellt, nicht verschwiegen.

**Datenpaket:** die laufunabhängigen Teile (Scenario-Configs, Config-Hashes, validation.json-Fixes) sind mit diesem Durchgang vollständig; ein Rebuild der Publikationsabbildungen/-tabellen (F1-F9/T1-T5-Äquivalente) gegen den aktuellen V1-V8+AA3+Z3+Z4-Stand ist NICHT Teil von Z5 und steht weiterhin aus (siehe [[project_paper2_figure_program]]).

---

## §4co — 2026-10-14: Z3 VOLLSTÄNDIG — Preisspreizung + Direktvermarktungsabschlag (12 Läufe), ein starker Zusatzbefund

**Korrektur einer eigenen Fehleinschätzung:** "Direktvermarktungsabschlag" existiert bereits vollständig als `grid.sell_spread_eur_mwh` (verdrahtet in `cost_calculator.py::_sell_price`, nie zuvor von einem Szenario aktiviert) — meine frühere Aussage "kein Mechanismus" beruhte auf einer zu engen Codesuche (`vermarktung`/`marketing_discount` statt der tatsächlichen generischen Namen `sell_spread`/`sell_premium`/`sell_haircut`/`sell_fee`). Für "Preisspreizung" gab es dagegen tatsächlich keinen Hebel — neu gebaut: `site.price_amplitude_factor` (`calion/io/loader.py`), mittelwerterhaltende Skalierung der Preis-Schwankungsbreite um den Serienmittelwert, bewusst getrennt vom bestehenden `price_scale_factor` (reiner Niveau-Multiplikator, hätte auch den Mittelwert verschoben — falscher Hebel für eine Volatilitäts-Sensitivität).

**12 neue Läufe** (`SB-S1-HK0{,-PIN0}-{SPREIZ15,SPREIZ20,VERMARKT2}` + MM-Äquivalente), je eigene frische PIN0, Z-Standardprotokoll. 10/12 `optimal`, 2/12 (SB frei ×1,5/×2,0 Spreizung) `maxTimeLimit` bei sehr engem Gap (0,196%/0,267%).

### Ergebnis: Direktvermarktungsabschlag bestätigt die Robustheit — Preisspreizung zeigt einen starken, ökonomisch plausiblen NEUEN Effekt

| Sensitivität | Intervall SB [EUR/a] | Intervall MM [EUR/a] | vs. Basisfall SB [165.215; 230.414] |
|---|---|---|---|
| Vermarktungsabschlag −2 EUR/MWh | [161.647; 230.410] | [1.275; 2.507] | praktisch deckungsgleich — bestätigt erneut die Robustheit |
| Preisspreizung ×1,5 | **[396.832; 469.959]** | [1.478; 2.593] | **≈2× höher** |
| Preisspreizung ×2,0 | **[644.140; 721.324]** | [2.746; 3.316] | **≈3× höher** |

**Einordnung (ökonomisch plausibel, kein Artefakt):** der TES-Wert entsteht primär aus Preisarbitrage (günstig laden, teuer vermeiden/verkaufen) — eine breitere Preisspanne bei GLEICHEM Mittelwert (Preisniveau unverändert, nur Volatilität höher) erhöht diese Arbitragemöglichkeit direkt. Der Vermarktungsabschlag dagegen trifft PIN0 und freie Investition nahezu gleich (beide verkaufen KWK-Strom), hebt sich im Differenzwert fast vollständig auf — folgerichtig kaum Veränderung. **Für die Diskussion im Paper relevant:** unter einem volatileren (z. B. zukünftigen, erneuerbarenreicheren) Preisregime wird der TES-Investitionsfall deutlich stärker, nicht schwächer — ein eigenständiges, publikationswürdiges Zusatzergebnis, nicht nur eine Robustheitsprüfung.

**Tabelle aktualisiert:** `tab_Z5_sb_mm_s1_sweep_and_sensitivities.csv` enthält jetzt alle 27 Zeilen (AA3-Sweep + alle 4 Z3-Sensitivitäten × PIN0/frei). Z3 ist damit vollständig (alle 4 ursprünglich angeordneten Sensitivitäten erledigt), MM bleibt in jeder einzelnen marginal.

---

## §4cp — 2026-10-16: neues Abbildungsprogramm (TES-Investitionswert-Geschichte) — altes F1-F9-Programm bewusst nicht wiederverwendet

**Entscheidung (Autor, nach Rückfrage):** das alte Abbildungsprogramm (August, [[project_paper2_figure_program]]) erzählt die Elektrifizierungs-/Heizkurven-Geschichte (MM-S4/S5, SB-S4/S6, HK0-HK2) — VOR der gesamten V1-V8+AA3+Z3-Kampagne, andere Kostenbasis, andere Kernaussage. Statt F1-F9 mechanisch unter dem neuen Kostenmodell nachzurechnen (Tage an Mehraufwand, siehe altes Memory-§"STILL UNBUILT"), wurde ein neues, schlankeres Abbildungsprogramm direkt aus AA3/Z3/Z4/Z5 gebaut — spiegelt exakt das wider, was diese Session tatsächlich belastbar erarbeitet hat.

**4 neue Abbildungen** (`scripts/paper_2/figures/fig_tes_value_story.py`, Fraunhofer-Stilsystem aus `_style.py` wiederverwendet, Output nach `results/paper2_figures/` + `docs/paper_2/submission_pack/01_figures/`, SVG+PDF+PNG):
- **F\_TES1** Wert-vs-Kosten-Kurve (Intervall je c0-Sprosse, log-Kostenachse, Realprojekt-Referenzlinien, robuste vs. vorbehaltsbehaftete Punkte optisch unterschieden).
- **F\_TES2** Größen-Kosten-Elastizität (log-log, Elastizität −1,72 annotiert, nur die zwei robusten Punkte für die Trendlinie).
- **F\_TES3** Tarif-/Volatilitäts-Sensitivitäts-Tornado (6 Balken, Preisspreizung farblich abgesetzt als dominanter Effekt).
- **F\_TES4** Standort-Vergleich S1 vs. S2/S3 (Balken, PIN0 als Referenz).

**1 neue Tabelle** (`tab_T_TES_value_summary.tex`, 9 Zeilen, Booktabs-Stil konsistent mit T1-T5): kondensierte Fassung der 27-Zeilen-Kampagnentabelle, mit $\dagger$-Fußnotenmarkierung für die ×1,3/×1,5-Vorbehaltspunkte.

**Layout-Nacharbeit bei F\_TES1:** erster Entwurf hatte überlappende Realprojekt-Labels (Friedrichshafen/Haltikon nur 4 EUR/m³ auseinander, bei Log-Skala nicht unterscheidbar) und eine die Daten verdeckende Legende — behoben (Labels zusammengeführt wo <2% log-Abstand, Legende über den Plot verschoben, explizite Log-Achsen-Ticks ergänzt). Alle 4 Abbildungen visuell geprüft (PNG gelesen) vor Übernahme ins Submission-Pack.

**Nicht Teil dieses Durchgangs:** F1/F2 (Architektur-Schema, Netzkarten) und F8/F9 (räumliche Profile, SoC) aus dem alten Programm bleiben bei Bedarf separat verfügbar (zeigen Netzstruktur/Dispatch-Mechanik, nicht die Kostenaussage — nicht direkt vom Datenwechsel betroffen, aber nicht erneut geprüft). Fließtext-Einbindung (§4 Results) steht noch aus.
